"""Small SQLAlchemy/SQLite history store. One transaction per prediction request."""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, create_engine, func, select, text, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool


def utc_now():
    return datetime.now(timezone.utc)


def utc_datetime(value):
    # SQLite does not retain timezone offsets in DateTime columns.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    predicted_class: Mapped[str] = mapped_column(String(16), index=True)
    predicted_attack_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    confidence_type: Mapped[str] = mapped_column(String(64))
    attack_probability: Mapped[float] = mapped_column(Float)
    anomaly_score: Mapped[float] = mapped_column(Float)
    anomaly_flag: Mapped[bool] = mapped_column(Boolean)
    risk_level: Mapped[str] = mapped_column(String(12), index=True)
    risk_score: Mapped[int] = mapped_column(Integer)
    model_version: Mapped[str] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(24))
    features: Mapped[dict] = mapped_column(JSON)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    risk_level: Mapped[str] = mapped_column(String(12), index=True)
    risk_score: Mapped[int] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(String(250))
    model_version: Mapped[str] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(24))


class ModelMetadata(Base):
    __tablename__ = "model_metadata"
    version: Mapped[str] = mapped_column(String(100), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    details: Mapped[dict] = mapped_column(JSON)


class Database:
    def __init__(self, url):
        options = {}
        if url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if url in {"sqlite://", "sqlite:///:memory:"}:
                options["poolclass"] = StaticPool
        self.engine = create_engine(url, **options)

    def initialize(self):
        Base.metadata.create_all(self.engine)

    def ping(self):
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def register_model(self, info):
        with Session(self.engine) as session, session.begin():
            session.execute(update(ModelMetadata).values(active=False))
            if info is not None:
                session.merge(ModelMetadata(
                    version=info["model_version"], active=True, loaded_at=utc_now(), details=info,
                ))

    def save_predictions(self, outputs, flows):
        results = []
        with Session(self.engine) as session, session.begin():
            for output, flow in zip(outputs, flows, strict=True):
                record = Prediction(**output, created_at=utc_now(), features=flow.features)
                session.add(record)
                session.flush()
                results.append({**output, "id": record.id, "created_at": utc_datetime(record.created_at)})
                if record.risk_level != "LOW":
                    message = "Classifier flagged ATTACK traffic."
                    if record.predicted_class == "BENIGN":
                        message = "Unusual flow flagged by Isolation Forest; classifier returned BENIGN."
                    elif record.anomaly_flag:
                        message = "Classifier flagged ATTACK traffic and Isolation Forest flagged an anomaly."
                    session.add(Alert(
                        prediction_id=record.id, created_at=record.created_at,
                        risk_level=record.risk_level, risk_score=record.risk_score,
                        message=message, model_version=record.model_version, source=record.source,
                    ))
        return results

    def alerts(self, limit, offset, risk_level=None):
        with Session(self.engine) as session:
            query = select(Alert)
            if risk_level:
                query = query.where(Alert.risk_level == risk_level)
            rows = session.scalars(query.order_by(Alert.id.desc()).offset(offset).limit(limit)).all()
            return [{
                "id": row.id, "prediction_id": row.prediction_id,
                "created_at": utc_datetime(row.created_at), "risk_level": row.risk_level,
                "risk_score": row.risk_score, "message": row.message,
                "model_version": row.model_version, "source": row.source,
            } for row in rows]

    @staticmethod
    def prediction_dict(row, include_features=False):
        result = {
            column.name: getattr(row, column.name)
            for column in Prediction.__table__.columns if column.name != "features"
        }
        result["created_at"] = utc_datetime(row.created_at)
        if include_features:
            result["features"] = row.features
        return result

    def predictions(self, limit, offset, predicted_class=None, risk_level=None, anomaly_only=False):
        with Session(self.engine) as session:
            query = select(Prediction)
            if predicted_class:
                query = query.where(Prediction.predicted_class == predicted_class)
            if risk_level:
                query = query.where(Prediction.risk_level == risk_level)
            if anomaly_only:
                query = query.where(Prediction.anomaly_flag.is_(True))
            rows = session.scalars(query.order_by(Prediction.id.desc()).offset(offset).limit(limit)).all()
            return [self.prediction_dict(row) for row in rows]

    def prediction_detail(self, prediction_id):
        with Session(self.engine) as session:
            row = session.get(Prediction, prediction_id)
            return self.prediction_dict(row, include_features=True) if row else None

    def stats(self):
        with Session(self.engine) as session:
            total = session.scalar(select(func.count()).select_from(Prediction))
            classes = dict(session.execute(select(Prediction.predicted_class, func.count()).group_by(Prediction.predicted_class)).all())
            risks = dict(session.execute(select(Prediction.risk_level, func.count()).group_by(Prediction.risk_level)).all())
            sources = dict(session.execute(select(Prediction.source, func.count()).group_by(Prediction.source)).all())
            anomalies = session.scalar(select(func.count()).select_from(Prediction).where(Prediction.anomaly_flag.is_(True)))
            hour = func.strftime("%Y-%m-%dT%H:00:00Z", Prediction.created_at)
            trends = session.execute(select(hour, func.count()).group_by(hour).order_by(hour.desc()).limit(24)).all()
            return {
                "total_flows": total,
                "benign_flows": classes.get("BENIGN", 0),
                "attack_flows": classes.get("ATTACK", 0),
                "anomaly_flows": anomalies,
                "suspicious_flows": risks.get("HIGH", 0) + risks.get("MEDIUM", 0),
                "high_risk_alerts": risks.get("HIGH", 0),
                "alerts_total": session.scalar(select(func.count()).select_from(Alert)),
                "class_distribution": {name: classes.get(name, 0) for name in ["BENIGN", "ATTACK"]},
                "risk_distribution": {name: risks.get(name, 0) for name in ["LOW", "MEDIUM", "HIGH"]},
                "source_distribution": sources,
                "traffic_trends": [{"hour_utc": hour_value, "flows": count} for hour_value, count in reversed(trends)],
                "history_scope": "Actual submitted predictions across model versions; no simulated events are preloaded.",
            }

    def close(self):
        self.engine.dispose()
