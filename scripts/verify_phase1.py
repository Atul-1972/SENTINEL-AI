"""Verify exported Colab artifacts locally without retraining or test prediction."""

import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    artifacts = ROOT / "artifacts"
    reports = ROOT / "reports"
    required = [
        "model.joblib", "preprocessor.joblib", "anomaly_model.joblib",
        "feature_schema.json", "model_params.json", "evaluation_metrics.json",
        "label_mapping.json",
    ]
    missing = [name for name in required if not (artifacts / name).is_file()]
    if missing:
        raise FileNotFoundError("Missing exported artifacts: " + ", ".join(missing))

    packages = {}
    for line in (ROOT / "requirements-model.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, expected = line.strip().split("==", maxsplit=1)
        actual = version(name)
        if actual != expected:
            raise RuntimeError(f"Package mismatch: {name} needs {expected}; found {actual}. Use .venv-model.")
        packages[name] = actual

    metadata = read_json(artifacts / "model_params.json")
    evaluation = read_json(artifacts / "evaluation_metrics.json")
    test_result = read_json(reports / "final_test_metrics.json")
    lock = read_json(reports / "selection_lock.json")
    schema = read_json(artifacts / "feature_schema.json")
    label_mapping = read_json(artifacts / "label_mapping.json")
    if label_mapping != {"BENIGN": 0, "ATTACK": 1}:
        raise ValueError("Unexpected binary label mapping.")
    if metadata["selected_candidate"] != lock["selected_candidate"]:
        raise ValueError("Exported model differs from the frozen classifier choice.")
    if evaluation["test"] != test_result:
        raise ValueError("Exported and archived test reports differ.")
    gate = metadata["quality_gate"]
    gate_passed = bool(
        test_result["attack_recall"] >= gate["min_attack_recall"]
        and test_result["attack_f1"] >= gate["min_attack_f1"]
        and test_result["false_positive_rate"] <= gate["max_false_positive_rate"]
    )
    if not gate_passed or not metadata["eligible_for_api_demo"]:
        raise ValueError("This export did not pass the fixed final quality gate.")

    # Compare model bytes with the pre-test selection lock, without loading test records.
    copied_models = {
        f"artifacts/candidates/{metadata['selected_candidate']}/model.joblib": artifacts / "model.joblib",
        f"artifacts/candidates/{metadata['selected_candidate']}/preprocessor.joblib": artifacts / "preprocessor.joblib",
        f"artifacts/candidates/{metadata['selected_candidate']}/feature_schema.json": artifacts / "feature_schema.json",
        f"artifacts/candidates/{metadata['selected_candidate']}/label_mapping.json": artifacts / "label_mapping.json",
        "artifacts/candidates/isolation_forest/anomaly_model.joblib": artifacts / "anomaly_model.joblib",
    }
    if metadata["selected_candidate"] == "xgboost":
        copied_models["artifacts/candidates/xgboost/model.ubj"] = artifacts / "model.ubj"
    for source_name, local_path in copied_models.items():
        if fingerprint(local_path) != lock["artifact_sha256"][source_name]:
            raise ValueError("Artifact checksum differs from the frozen model: " + local_path.name)
    if fingerprint(ROOT / "data/processed/test.csv") != test_result["test_csv_sha256"]:
        raise ValueError("The exported test CSV differs from the evaluated test file.")

    # Predict only the historical validation examples used by the Colab reload check.
    smoke = read_json(reports / "inference_smoke_test.json")
    records = smoke["flows"]
    features = schema["feature_names"]
    if not records or len(features) != len(set(features)):
        raise ValueError("Missing demo records or duplicate feature names.")
    if any(set(record["features"]) != set(features) for record in records):
        raise ValueError("Demo records do not match the model feature schema.")
    flows = pd.DataFrame([record["features"] for record in records], columns=features)
    flows = flows.apply(pd.to_numeric, errors="raise").replace([np.inf, -np.inf], np.nan)
    snapshot_error = None
    snapshot_model = None
    classifier_format = "joblib"
    if metadata["selected_candidate"] == "xgboost":
        # Native model IO is the portable representation. Python memory snapshots
        # can fail across platforms even when the package versions match.
        model = XGBClassifier(n_jobs=2)
        model.load_model(artifacts / "model.ubj")
        classifier_format = "xgboost_ubjson"
        try:
            snapshot_model = joblib.load(artifacts / "model.joblib")
        except Exception as error:
            snapshot_error = f"{type(error).__name__}: {error}"
    else:
        model = joblib.load(artifacts / "model.joblib")
        snapshot_model = model
    preprocessor = joblib.load(artifacts / "preprocessor.joblib")
    anomaly_model = joblib.load(artifacts / "anomaly_model.joblib")
    prepared = preprocessor.transform(flows)
    predictions = model.predict(prepared)
    attack_probabilities = model.predict_proba(prepared)[:, list(model.classes_).index(1)]
    anomaly_scores = -anomaly_model.decision_function(prepared)
    anomaly_flags = anomaly_model.predict(prepared) == -1
    inverse_labels = {value: key for key, value in label_mapping.items()}
    predicted_labels = [inverse_labels[int(value)] for value in predictions]
    if predicted_labels != [record["predicted_class"] for record in records]:
        raise AssertionError("Local classifier predictions differ from Colab demo predictions.")
    if not np.allclose(attack_probabilities, [r["attack_probability_uncalibrated"] for r in records], rtol=1e-6, atol=1e-8):
        raise AssertionError("Local probability outputs differ from the saved Colab outputs.")
    if not np.allclose(anomaly_scores, [r["anomaly_score"] for r in records], rtol=1e-6, atol=1e-8):
        raise AssertionError("Local anomaly scores differ from the saved Colab outputs.")
    if anomaly_flags.tolist() != [record["anomaly_flag"] for record in records]:
        raise AssertionError("Local anomaly flags differ from the saved Colab outputs.")

    native_matches_snapshot = None
    if metadata["selected_candidate"] == "xgboost":
        if snapshot_model is not None and not np.array_equal(snapshot_model.predict(prepared), predictions):
            raise AssertionError("Native XGBoost and joblib predictions differ.")
        native_matches_snapshot = True if snapshot_model is not None else None

    result = {
        "status": "passed",
        "model_version": metadata["model_version"],
        "required_artifacts_present": required,
        "frozen_artifact_checksums_match": True,
        "test_file_checksum_matches": True,
        "test_predictions_repeated": False,
        "demo_source": smoke["source"],
        "demo_flows_verified": len(records),
        "input_feature_count": len(features),
        "prepared_feature_count": int(prepared.shape[1]),
        "classifier_predictions_match_colab": True,
        "classifier_format_used": classifier_format,
        "classifier_joblib_loadable_locally": snapshot_model is not None,
        "classifier_joblib_load_error": snapshot_error,
        "probability_outputs_match_colab": True,
        "anomaly_scores_and_flags_match_colab": True,
        "native_xgboost_matches_joblib": native_matches_snapshot,
        "fixed_quality_gate_passed": gate_passed,
        "recorded_final_test_accuracy": test_result["accuracy"],
        "training_python": metadata["versions"]["python"],
        "local_python": platform.python_version(),
        "packages": packages,
    }
    output = reports / "local_verification.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print("\nLocal verification passed. Saved: reports/local_verification.json")


if __name__ == "__main__":
    main()
