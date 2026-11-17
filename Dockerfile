FROM python:3.13.18-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OMP_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2 \
    SENTINEL_ARTIFACTS_DIR=/app/artifacts \
    SENTINEL_DATABASE_URL=sqlite:////app/data/sentinel.db

WORKDIR /app

# libgomp supplies OpenMP for the CPU models. No compiler or GPU packages needed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-model.txt ./requirements-model.txt
COPY backend/requirements-api.txt ./backend/requirements-api.txt

# Preserve every trained package version, using the smaller CPU distribution on Linux.
RUN sed 's/^xgboost==/xgboost-cpu==/' requirements-model.txt > /tmp/requirements-model-cpu.txt \
    && python -m pip install -r /tmp/requirements-model-cpu.txt -r backend/requirements-api.txt \
    && python -m pip check

COPY backend/ ./backend/
COPY artifacts/ ./artifacts/
COPY reports/inference_smoke_test.json ./reports/inference_smoke_test.json
COPY reports/model_comparison.json ./reports/model_comparison.json
COPY data/sample/api_request.json data/sample/api_batch_request.json ./examples/

RUN useradd --create-home --user-group --uid 10001 sentinel \
    && mkdir -p /app/data \
    && chown sentinel:sentinel /app/data

USER sentinel
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).close()"]

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
