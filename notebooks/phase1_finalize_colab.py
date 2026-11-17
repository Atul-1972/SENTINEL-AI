import hashlib
import json
import platform
import shutil
from pathlib import Path
from time import perf_counter

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

ROOT = Path("/content/SENTINEL-AI")
LABEL_MAPPING = {"BENIGN": 0, "ATTACK": 1}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, content):
    path.write_text(json.dumps(content, indent=2, allow_nan=False), encoding="utf-8")


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    artifacts = ROOT / "artifacts"
    comparison_path = artifacts / "model_comparison.json"
    if not comparison_path.is_file():
        raise FileNotFoundError("Run Steps 7-10 first; the comparison report is missing.")
    comparison = read_json(comparison_path)
    selected = comparison["recommended_candidate"]
    if selected not in {"random_forest", "xgboost"}:
        raise ValueError("No classifier passed the validation quality gate.")
    if not any(row["candidate"] == selected and row["passes_quality_gate"] for row in comparison["candidates"]):
        raise ValueError("The selected classifier must pass the original validation gate.")

    candidate = artifacts / "candidates" / selected
    anomaly = artifacts / "candidates/isolation_forest"
    required = [candidate / name for name in [
        "model.joblib", "preprocessor.joblib", "feature_schema.json",
        "model_params.json", "label_mapping.json", "evaluation_metrics.json",
    ]] + [anomaly / name for name in [
        "anomaly_model.joblib", "preprocessor.joblib", "model_params.json", "evaluation_metrics.json",
    ]]
    required += [ROOT / "preparation_report.json"]
    required += [ROOT / f"data/processed/{name}.csv" for name in ["train", "validation", "test"]]
    if selected == "xgboost":
        required.append(candidate / "model.ubj")
    if any(not path.is_file() for path in required):
        raise FileNotFoundError("A required split or saved artifact is missing. Complete Steps 7-10.")
    if fingerprint(candidate / "preprocessor.joblib") != fingerprint(anomaly / "preprocessor.joblib"):
        raise ValueError("Classifier and anomaly preprocessing differ. Recreate Step 10 before final evaluation.")

    # Freeze classifier/artifact selection before inspecting any test labels.
    lock_path = artifacts / "selection_lock.json"
    identity = {
        "selected_candidate": selected,
        "quality_gate": comparison["quality_gate"],
        "comparison_sha256": fingerprint(comparison_path),
        "artifact_sha256": {
            str(path.relative_to(ROOT)): fingerprint(path)
            for path in required if path.suffix != ".csv"
        },
    }
    if lock_path.exists():
        if read_json(lock_path) != identity:
            raise ValueError("Selection or artifacts changed after freezing. Keep the original held-out evaluation; do not switch models using its results.")
    else:
        with lock_path.open("x", encoding="utf-8") as handle:
            json.dump(identity, handle, indent=2)

    model = joblib.load(candidate / "model.joblib")
    preprocessor = joblib.load(candidate / "preprocessor.joblib")
    anomaly_model = joblib.load(anomaly / "anomaly_model.joblib")
    schema = read_json(candidate / "feature_schema.json")
    features = schema["feature_names"]
    test_path = ROOT / "data/processed/test.csv"
    test_digest = fingerprint(test_path)
    result_path = artifacts / "final_test_metrics.json"
    started_path = artifacts / "final_test_started.json"

    if result_path.exists():
        result = read_json(result_path)
        if result["test_csv_sha256"] != test_digest:
            raise ValueError("The final test file changed. Cached results belong to the original holdout.")
        print("Reusing saved final test results; no repeat test prediction is performed.")
    else:
        if started_path.exists():
            raise RuntimeError("A previous final evaluation started but did not finish. Preserve this state and share the error before retrying.")
        test = pd.read_csv(test_path)
        if set(test.columns) != set(features) | {"Label"}:
            raise ValueError("Test columns differ from the saved feature schema.")
        if set(test["Label"]) != set(LABEL_MAPPING):
            raise ValueError("Test data must contain both BENIGN and ATTACK labels only.")
        X_test = test[features].apply(pd.to_numeric, errors="raise").replace([np.inf, -np.inf], np.nan)
        y_test = test["Label"].map(LABEL_MAPPING).to_numpy(dtype=int)
        write_json(started_path, {"selected_candidate": selected, "test_csv_sha256": test_digest})
        started = perf_counter()
        prepared = preprocessor.transform(X_test)
        probabilities = model.predict_proba(prepared)
        predictions = model.classes_[probabilities.argmax(axis=1)]
        elapsed = perf_counter() - started
        attack_probabilities = probabilities[:, list(model.classes_).index(1)]
        matrix = confusion_matrix(y_test, predictions, labels=[0, 1])
        tn, fp, fn, tp = matrix.ravel()
        result = {
            "selected_candidate": selected,
            "evaluation_split": "test",
            "test_rows": len(test),
            "test_csv_sha256": test_digest,
            "accuracy": float(accuracy_score(y_test, predictions)),
            "attack_precision": float(precision_score(y_test, predictions, zero_division=0)),
            "attack_recall": float(recall_score(y_test, predictions, zero_division=0)),
            "attack_f1": float(f1_score(y_test, predictions, zero_division=0)),
            "false_positive_rate": float(fp / (fp + tn)),
            "roc_auc": float(roc_auc_score(y_test, attack_probabilities)),
            "confusion_matrix": matrix.tolist(),
            "confusion_matrix_order": ["BENIGN", "ATTACK"],
            "test_batch_ms_per_flow": elapsed * 1000 / len(test),
            "latency_note": "Amortized batch prediction time including preprocessing, not API request latency.",
            "classification_report": classification_report(
                y_test, predictions, labels=[0, 1], target_names=["BENIGN", "ATTACK"],
                output_dict=True, zero_division=0,
            ),
            "limitation": "Random holdout within one capture; results do not establish generalization to new days, networks, or attack types.",
        }
        gate = identity["quality_gate"]
        result["passes_fixed_quality_gate"] = bool(
            result["attack_recall"] >= gate["min_attack_recall"]
            and result["attack_f1"] >= gate["min_attack_f1"]
            and result["false_positive_rate"] <= gate["max_false_positive_rate"]
        )
        write_json(result_path, result)

    # Export the selected, unchanged models. No retraining or threshold tuning here.
    export = ROOT / "phase1_export"
    exported_artifacts = export / "artifacts"
    reports = export / "reports"
    samples = export / "data/sample"
    processed = export / "data/processed"
    for directory in [exported_artifacts, reports, samples, processed]:
        directory.mkdir(parents=True, exist_ok=True)
    for name in ["model.joblib", "preprocessor.joblib", "feature_schema.json", "label_mapping.json"]:
        shutil.copy2(candidate / name, exported_artifacts / name)
    shutil.copy2(anomaly / "anomaly_model.joblib", exported_artifacts / "anomaly_model.joblib")
    if (candidate / "model.ubj").exists():
        shutil.copy2(candidate / "model.ubj", exported_artifacts / "model.ubj")

    model_metadata = read_json(candidate / "model_params.json")
    anomaly_metadata = read_json(anomaly / "model_params.json")
    model_version = f"sentinel-{selected}-1.0.0"
    metadata = {
        **model_metadata,
        "model_version": model_version,
        "selected_candidate": selected,
        "selection_basis": "Validation comparison, frozen before final test labels were inspected.",
        "quality_gate": identity["quality_gate"],
        "eligible_for_api_demo": result["passes_fixed_quality_gate"],
        "anomaly_model": anomaly_metadata,
    }
    write_json(exported_artifacts / "model_params.json", metadata)
    write_json(exported_artifacts / "evaluation_metrics.json", {
        "validation": read_json(candidate / "evaluation_metrics.json"),
        "test": result,
        "anomaly_validation": read_json(anomaly / "evaluation_metrics.json"),
    })
    for path in [comparison_path, lock_path, result_path, ROOT / "preparation_report.json"]:
        shutil.copy2(path, reports / path.name)
    for name in ["train", "validation", "test"]:
        shutil.copy2(ROOT / f"data/processed/{name}.csv", processed / f"{name}.csv")
    for name in ["random_forest", "xgboost", "isolation_forest"]:
        source = artifacts / "candidates" / name
        for filename in ["evaluation_metrics.json", "validation_confusion_matrix.png", "validation_anomaly_scores.png"]:
            if (source / filename).is_file():
                shutil.copy2(source / filename, reports / f"{name}_{filename}")
    if (artifacts / "model_comparison.csv").is_file():
        shutil.copy2(artifacts / "model_comparison.csv", reports / "model_comparison.csv")

    # Demo examples come from validation, not the reserved test set.
    validation = pd.read_csv(ROOT / "data/processed/validation.csv")
    demo = pd.concat([
        validation.loc[validation["Label"].eq(label)].head(5)
        for label in ["BENIGN", "ATTACK"]
    ], ignore_index=True)
    demo.to_csv(samples / "historical_demo_flows.csv", index=False)
    X_demo = demo[features].apply(pd.to_numeric, errors="raise").replace([np.inf, -np.inf], np.nan)
    loaded_model = joblib.load(exported_artifacts / "model.joblib")
    loaded_preprocessor = joblib.load(exported_artifacts / "preprocessor.joblib")
    loaded_anomaly = joblib.load(exported_artifacts / "anomaly_model.joblib")
    demo_prepared = loaded_preprocessor.transform(X_demo)
    demo_predictions = loaded_model.predict(demo_prepared)
    demo_probabilities = loaded_model.predict_proba(demo_prepared)
    demo_scores = -loaded_anomaly.decision_function(demo_prepared)
    assert np.array_equal(demo_predictions, model.predict(preprocessor.transform(X_demo)))
    assert np.allclose(demo_scores, -anomaly_model.decision_function(preprocessor.transform(X_demo)))
    demo_records = X_demo.astype(object).where(X_demo.notna(), None).to_dict(orient="records")
    inverse_labels = {value: key for key, value in LABEL_MAPPING.items()}
    write_json(reports / "inference_smoke_test.json", {
        "source": "Historical validation examples; no live traffic or invented predictions.",
        "model_version": model_version,
        "artifact_reload_passed": True,
        "flows": [
            {
                "features": flow,
                "true_binary_label": str(demo.iloc[index]["Label"]),
                "predicted_class": inverse_labels[int(demo_predictions[index])],
                "attack_probability_uncalibrated": float(demo_probabilities[index, list(loaded_model.classes_).index(1)]),
                "anomaly_score": float(demo_scores[index]),
                "anomaly_flag": bool(demo_scores[index] > 0),
            }
            for index, flow in enumerate(demo_records)
        ],
    })

    versions = model_metadata["versions"]
    requirements = [f"{name}=={version}" for name, version in versions.items() if name != "python"]
    (export / "requirements-model.txt").write_text("\n".join(requirements) + "\n", encoding="utf-8")
    status = "PASSED" if result["passes_fixed_quality_gate"] else "FAILED; review results before API use"
    (export / "README.txt").write_text(
        f"SENTINEL AI Phase 1 export\nModel: {model_version}\nFixed quality gate: {status}\n"
        f"Training Python: {versions['python']}\nExport Python: {platform.python_version()}\n"
        "Install matching package versions from requirements-model.txt. Preserve the training Python version where feasible.\n"
        "Extract artifacts/ into the local project. Keep reports/ and data/ for the college demonstration and monitoring.\n"
        "Demo CSV rows are historical validation data. Predictions are measured, not guaranteed correct.\n"
        "Classifier is binary BENIGN/ATTACK, trained on BENIGN and DDoS only.\n"
        "Anomaly scores are separate and do not identify attack categories or calibrated probabilities.\n"
        "This is an educational prototype, not production network protection.\n", encoding="utf-8",
    )

    matrix = np.asarray(result["confusion_matrix"])
    display = ConfusionMatrixDisplay(matrix, display_labels=["BENIGN", "ATTACK"])
    display.plot(cmap="Blues", values_format="d")
    plt.title(f"{selected} — final test confusion matrix")
    plt.tight_layout()
    plt.savefig(reports / "final_test_confusion_matrix.png", dpi=150)
    plt.show()

    archive = Path(shutil.make_archive(str(ROOT / "sentinel_phase1_bundle"), "zip", export))
    print(json.dumps(result, indent=2))
    print("\nExported model and anomaly reload checks passed on historical validation examples.")
    print("Fixed quality gate:", status)
    print("Download this bundle from Colab's Files panel:", archive)
    print("Phase 2 has not started. Share the final test report before continuing.")


if __name__ == "__main__":
    main()
