import json

import numpy as np
import pytest

from backend.model_loader import ModelLoadError, ModelService, model_package_version
from backend.schemas import FlowInput
from conftest import ROOT


def minimal_metadata(directory, metadata):
    for name, value in {
        "model_params.json": metadata,
        "feature_schema.json": {"feature_names": ["duration"]},
        "evaluation_metrics.json": {},
        "label_mapping.json": {"BENIGN": 0, "ATTACK": 1},
    }.items():
        (directory / name).write_text(json.dumps(value), encoding="utf-8")


def test_loader_rejects_an_export_that_failed_its_gate(tmp_path):
    minimal_metadata(tmp_path, {"eligible_for_api_demo": False})
    with pytest.raises(ModelLoadError, match="quality gate"):
        ModelService(tmp_path)


def test_loader_rejects_package_mismatch_before_model_loading(tmp_path):
    minimal_metadata(tmp_path, {"eligible_for_api_demo": True, "model_version": "fixture", "versions": {"scikit-learn": "0.0.0"}})
    with pytest.raises(ModelLoadError, match="scikit-learn==0.0.0"):
        ModelService(tmp_path)


def test_cpu_xgboost_version_does_not_require_the_full_distribution_metadata(monkeypatch):
    import xgboost
    from importlib.metadata import PackageNotFoundError

    def no_full_distribution(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr("backend.model_loader.version", no_full_distribution)
    assert model_package_version("xgboost") == xgboost.__version__


@pytest.mark.artifacts
def test_real_saved_models_reproduce_all_colab_demo_outputs(real_service):
    records = json.loads((ROOT / "reports/inference_smoke_test.json").read_text(encoding="utf-8"))["flows"]
    # Reverse JSON key order to prove input ordering is restored by the service.
    flows = [FlowInput(features=dict(reversed(list(record["features"].items()))), source="historical") for record in records]
    results = real_service.predict(flows)
    assert [r["predicted_class"] for r in results] == [r["predicted_class"] for r in records]
    assert np.allclose([r["attack_probability"] for r in results], [r["attack_probability_uncalibrated"] for r in records], rtol=1e-6)
    assert np.allclose([r["anomaly_score"] for r in results], [r["anomaly_score"] for r in records], rtol=1e-6)
    assert [r["anomaly_flag"] for r in results] == [r["anomaly_flag"] for r in records]
    assert all(r["predicted_attack_category"] is None for r in results)
    assert real_service.model_format == "xgboost_ubjson"


@pytest.mark.artifacts
def test_real_preprocessing_accepts_a_missing_value(real_service):
    record = json.loads((ROOT / "reports/inference_smoke_test.json").read_text(encoding="utf-8"))["flows"][0]
    features = {**record["features"], "Flow Bytes/s": None}
    result = real_service.predict([FlowInput(features=features)])[0]
    assert np.isfinite(result["confidence"]) and np.isfinite(result["anomaly_score"])
