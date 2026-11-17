"""Small, explicit test fixtures. The production app never uses this fake model."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.model_loader import ModelService, assess_risk

ROOT = Path(__file__).resolve().parents[1]


class FakeModelService:
    feature_names = ["duration", "packet_rate"]
    model_version = "fixture-1"

    def predict(self, flows):
        ModelService.validate_features(self, flows)
        results = []
        for flow in flows:
            predicted = "ATTACK" if (flow.features["duration"] or 0) > 20 else "BENIGN"
            anomaly = (flow.features["packet_rate"] or 0) < 0
            risk_score, risk_level = assess_risk(predicted, anomaly)
            probability = 0.8 if predicted == "ATTACK" else 0.1
            results.append({
                "predicted_class": predicted, "predicted_attack_category": None,
                "confidence": max(probability, 1 - probability),
                "confidence_type": "uncalibrated_model_probability",
                "attack_probability": probability, "anomaly_score": 0.2 if anomaly else -0.2,
                "anomaly_flag": anomaly, "risk_level": risk_level, "risk_score": risk_score,
                "model_version": self.model_version, "source": flow.source,
            })
        return results

    def info(self):
        return {"active_model": "test_fixture", "model_version": self.model_version, "feature_names": self.feature_names}


@pytest.fixture
def fake_service():
    return FakeModelService()


@pytest.fixture
def client(fake_service):
    with TestClient(create_app(database_url="sqlite://", model_service=fake_service)) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def real_service():
    if not (ROOT / "artifacts/model.ubj").is_file():
        pytest.skip("Real exported artifacts are not present; no download or training is required.")
    return ModelService(ROOT / "artifacts")
