"""Request validation and public response contracts."""

import math
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, field_validator

Source = Literal["historical", "simulated", "user_provided"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class FlowInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    features: dict[str, StrictFloat | StrictInt | None] = Field(
        min_length=1,
        description="All canonical feature names from /model-info. Use null for a missing value; omit no keys.",
    )
    source: Source = "user_provided"

    @field_validator("features")
    @classmethod
    def finite_numeric_values(cls, features):
        if all(value is None for value in features.values()):
            raise ValueError("At least one feature must have a numeric value.")
        for name, value in features.items():
            if value is not None and (abs(value) > 3.4028234663852886e38 or not math.isfinite(value)):
                raise ValueError(f"{name}: supply a finite number within float32 range, or null.")
        return features


class BatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flows: list[FlowInput] = Field(min_length=1, max_length=1000)


class PredictionResult(BaseModel):
    id: int
    created_at: datetime
    predicted_class: Literal["BENIGN", "ATTACK"]
    predicted_attack_category: str | None = None
    confidence: float = Field(ge=0, le=1)
    confidence_type: Literal["uncalibrated_model_probability"]
    attack_probability: float = Field(ge=0, le=1)
    anomaly_score: float
    anomaly_flag: bool
    risk_level: RiskLevel
    risk_score: int = Field(ge=0, le=100)
    model_version: str
    source: Source


class BatchResult(BaseModel):
    count: int
    results: list[PredictionResult]


class PredictionDetail(PredictionResult):
    features: dict[str, float | None]


class AlertResult(BaseModel):
    id: int
    prediction_id: int
    created_at: datetime
    risk_level: RiskLevel
    risk_score: int
    message: str
    model_version: str
    source: Source
