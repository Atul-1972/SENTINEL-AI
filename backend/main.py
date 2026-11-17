"""Run from the project root: python -m uvicorn backend.main:app."""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from backend.database import Database
from backend.model_loader import FeatureValidationError, ModelService
from backend.schemas import AlertResult, BatchInput, BatchResult, FlowInput, PredictionDetail, PredictionResult, RiskLevel

ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger("sentinel.api")


def create_app(artifacts_dir=None, database_url=None, model_service=None):
    """Tests can supply small fixtures and an isolated database; no training is needed."""
    artifacts_dir = Path(artifacts_dir or os.getenv("SENTINEL_ARTIFACTS_DIR", ROOT / "artifacts"))
    default_db = ROOT / "data/sentinel.db"
    database_url = database_url or os.getenv("SENTINEL_DATABASE_URL")
    if not database_url:
        default_db.parent.mkdir(parents=True, exist_ok=True)
        database_url = "sqlite:///" + default_db.as_posix()

    @asynccontextmanager
    async def lifespan(app):
        database = Database(database_url)
        app.state.database = database
        app.state.model_service = None
        try:
            database.initialize()
            try:
                app.state.model_service = model_service if model_service is not None else ModelService(artifacts_dir)
            except Exception:
                logger.exception("Could not load trusted local model artifacts.")
            service = app.state.model_service
            database.register_model(service.info() if service else None)
            yield
        finally:
            database.close()

    app = FastAPI(
        title="SENTINEL AI",
        version="0.2.0",
        description=(
            "Educational network-flow detection API. Binary BENIGN/ATTACK classification, "
            "a separate anomaly signal, and persistent SQLite prediction history. "
            "Training attack coverage is DDoS only. See /model-info for the exact feature schema."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Exclude raw input and exception contexts, which may contain non-JSON NaN/inf.
        details = [{"loc": item["loc"], "msg": item["msg"], "type": item["type"]} for item in error.errors()]
        return JSONResponse(status_code=422, content={"detail": details})

    def require_model(request):
        service = request.app.state.model_service
        if service is None:
            raise HTTPException(503, "Model unavailable. Check the artifacts, package versions and server logs.")
        return service

    def predict_and_store(request, flows):
        service = require_model(request)
        try:
            outputs = service.predict(flows)
        except FeatureValidationError as error:
            raise HTTPException(422, {"message": str(error), "errors": error.errors}) from error
        except Exception as error:
            logger.exception("Model inference failed.")
            raise HTTPException(500, "Prediction failed. See server logs.") from error
        try:
            return request.app.state.database.save_predictions(outputs, flows)
        except SQLAlchemyError as error:
            logger.exception("Prediction history could not be committed.")
            raise HTTPException(503, "Prediction history unavailable. No results were committed.") from error

    # A real historical flow makes Swagger immediately usable, without fabricated data.
    example = None
    smoke_path = ROOT / "reports/inference_smoke_test.json"
    if smoke_path.is_file():
        try:
            record = json.loads(smoke_path.read_text(encoding="utf-8"))["flows"][0]
            example = {"features": record["features"], "source": "historical"}
        except (ValueError, KeyError, IndexError):
            logger.warning("Historical Swagger example unavailable.")
    single_example = {"requestBody": {"content": {"application/json": {"example": example}}}} if example else None
    batch_example = {"requestBody": {"content": {"application/json": {"example": {"flows": [example]}}}}} if example else None

    @app.get("/")
    def index():
        return {"name": "SENTINEL AI", "version": "0.2.0", "docs": "/docs", "model_info": "/model-info", "mode": "educational prototype"}

    @app.get("/health")
    def health(request: Request):
        database_ready = True
        try:
            request.app.state.database.ping()
        except SQLAlchemyError:
            database_ready = False
        service = request.app.state.model_service
        ready = database_ready and service is not None
        return JSONResponse(status_code=200 if ready else 503, content={
            "status": "ok" if ready else "unavailable",
            "database_ready": database_ready,
            "model_ready": service is not None,
            "model_version": service.model_version if service else None,
        })

    @app.post("/predict", response_model=PredictionResult, openapi_extra=single_example)
    def predict(flow: FlowInput, request: Request):
        return predict_and_store(request, [flow])[0]

    @app.post("/predict-batch", response_model=BatchResult, openapi_extra=batch_example)
    def predict_batch(batch: BatchInput, request: Request):
        results = predict_and_store(request, batch.flows)
        return {"count": len(results), "results": results}

    @app.get("/model-info")
    def model_info(request: Request):
        return require_model(request).info()

    @app.get("/predictions", response_model=list[PredictionResult])
    def predictions(request: Request, limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0), predicted_class: Literal["BENIGN", "ATTACK"] | None = None, risk_level: RiskLevel | None = None, anomaly_only: bool = False):
        try:
            return request.app.state.database.predictions(limit, offset, predicted_class, risk_level, anomaly_only)
        except SQLAlchemyError as error:
            raise HTTPException(503, "Prediction history unavailable.") from error

    @app.get("/predictions/{prediction_id}", response_model=PredictionDetail)
    def prediction_detail(prediction_id: int, request: Request):
        try:
            result = request.app.state.database.prediction_detail(prediction_id)
        except SQLAlchemyError as error:
            raise HTTPException(503, "Prediction history unavailable.") from error
        if result is None:
            raise HTTPException(404, "Prediction not found.")
        return result

    @app.get("/alerts", response_model=list[AlertResult])
    def alerts(request: Request, limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0), risk_level: RiskLevel | None = None):
        try:
            return request.app.state.database.alerts(limit, offset, risk_level)
        except SQLAlchemyError as error:
            raise HTTPException(503, "Alert history unavailable.") from error

    @app.get("/stats")
    def stats(request: Request):
        try:
            result = request.app.state.database.stats()
        except SQLAlchemyError as error:
            raise HTTPException(503, "Prediction history unavailable.") from error
        service = request.app.state.model_service
        return {**result, "active_model_version": service.model_version if service else None}

    return app


app = create_app()
