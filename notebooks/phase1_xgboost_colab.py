import json
import platform
from pathlib import Path
from time import perf_counter

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
import xgboost
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
from xgboost import XGBClassifier

ROOT = Path("/content/SENTINEL-AI")
RF_OUTPUT = ROOT / "artifacts/candidates/random_forest"
OUTPUT = ROOT / "artifacts/candidates/xgboost"
SEED = 42
LABEL_MAPPING = {"BENIGN": 0, "ATTACK": 1}

# Set these educational validation targets before running the new candidate.
QUALITY_GATE = {
    "min_attack_recall": 0.98,
    "min_attack_f1": 0.98,
    "max_false_positive_rate": 0.01,
}

required = [
    ROOT / "preparation_report.json",
    RF_OUTPUT / "model.joblib",
    RF_OUTPUT / "preprocessor.joblib",
    RF_OUTPUT / "feature_schema.json",
    RF_OUTPUT / "evaluation_metrics.json",
]
if any(not path.is_file() for path in required):
    raise FileNotFoundError("Run Steps 7 and 8 first; preparation or Random Forest artifacts are missing.")

preparation = json.loads((ROOT / "preparation_report.json").read_text(encoding="utf-8"))
schema = json.loads((RF_OUTPUT / "feature_schema.json").read_text(encoding="utf-8"))
rf_metrics = json.loads((RF_OUTPUT / "evaluation_metrics.json").read_text(encoding="utf-8"))
feature_names = preparation["candidate_features"]
if schema["feature_names"] != feature_names:
    raise ValueError("The Random Forest schema differs from the prepared dataset. Rerun Step 8.")

train = pd.read_csv(ROOT / "data/processed/train.csv")
validation = pd.read_csv(ROOT / "data/processed/validation.csv")
for name, frame in {"train": train, "validation": validation}.items():
    if set(frame.columns) != set(feature_names) | {"Label"}:
        raise ValueError(f"{name} columns do not match the feature schema.")
    if set(frame["Label"]) != set(LABEL_MAPPING):
        raise ValueError(f"{name} must contain both BENIGN and ATTACK labels only.")
if rf_metrics["training_rows"] != len(train) or rf_metrics["validation_rows"] != len(validation):
    raise ValueError("Split sizes changed since Step 8. Rerun the baseline on the current splits.")

X_train = train[feature_names].apply(pd.to_numeric, errors="raise").replace([np.inf, -np.inf], np.nan)
X_validation = validation[feature_names].apply(pd.to_numeric, errors="raise").replace([np.inf, -np.inf], np.nan)
y_train = train["Label"].map(LABEL_MAPPING).to_numpy(dtype=int)
y_validation = validation["Label"].map(LABEL_MAPPING).to_numpy(dtype=int)

# Reuse the exact preprocessing already fitted on training data in Step 8.
# Never refit it on validation data. No test.csv is read anywhere in this step.
preprocessor = joblib.load(RF_OUTPUT / "preprocessor.joblib")
train_prepared = preprocessor.transform(X_train)
validation_prepared = preprocessor.transform(X_validation)
rf_model = joblib.load(RF_OUTPUT / "model.joblib")
rf_predictions = rf_model.predict(validation_prepared)
rf_matrix = confusion_matrix(y_validation, rf_predictions, labels=[0, 1])
if rf_matrix.tolist() != rf_metrics["confusion_matrix"]:
    raise ValueError("The saved baseline no longer reproduces its validation results. Rerun Step 8.")

params = {
    "n_estimators": 150,
    "max_depth": 4,
    "learning_rate": 0.1,
    "subsample": 0.9,
    "colsample_bytree": 0.9,
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "tree_method": "hist",
    "random_state": SEED,
    "n_jobs": 2,
}
model = XGBClassifier(**params)
print("Training XGBoost on the same training split; final test data stays reserved.")
started = perf_counter()
model.fit(train_prepared, y_train)
training_seconds = perf_counter() - started

started = perf_counter()
validation_prepared = preprocessor.transform(X_validation)
probabilities = model.predict_proba(validation_prepared)
predictions = model.classes_[probabilities.argmax(axis=1)]
prediction_seconds = perf_counter() - started
attack_probabilities = probabilities[:, list(model.classes_).index(1)]
matrix = confusion_matrix(y_validation, predictions, labels=[0, 1])
tn, fp, fn, tp = matrix.ravel()

metrics = {
    "model": "XGBClassifier",
    "candidate_version": "xgb-baseline-001",
    "evaluation_split": "validation",
    "training_rows": len(train),
    "validation_rows": len(validation),
    "input_feature_count": len(feature_names),
    "selected_feature_count": int(train_prepared.shape[1]),
    "accuracy": float(accuracy_score(y_validation, predictions)),
    "attack_precision": float(precision_score(y_validation, predictions, zero_division=0)),
    "attack_recall": float(recall_score(y_validation, predictions, zero_division=0)),
    "attack_f1": float(f1_score(y_validation, predictions, zero_division=0)),
    "false_positive_rate": float(fp / (fp + tn)),
    "roc_auc": float(roc_auc_score(y_validation, attack_probabilities)),
    "confusion_matrix": matrix.tolist(),
    "confusion_matrix_order": ["BENIGN", "ATTACK"],
    "training_seconds": training_seconds,
    "training_time_note": "Classifier fit only; preprocessing was reused from Random Forest.",
    "validation_batch_ms_per_flow": prediction_seconds * 1000 / len(validation),
    "latency_note": "Amortized batch time including preprocessing; not single-request API latency.",
    "probability_note": "XGBoost probabilities are not calibrated confidence scores.",
    "classification_report": classification_report(
        y_validation, predictions, labels=[0, 1],
        target_names=["BENIGN", "ATTACK"], output_dict=True, zero_division=0,
    ),
}

OUTPUT.mkdir(parents=True, exist_ok=True)
joblib.dump(model, OUTPUT / "model.joblib", compress=3)
joblib.dump(preprocessor, OUTPUT / "preprocessor.joblib", compress=3)
model.save_model(OUTPUT / "model.ubj")
metrics["model_bytes"] = (OUTPUT / "model.joblib").stat().st_size
metrics["native_model_bytes"] = (OUTPUT / "model.ubj").stat().st_size
metadata = {
    "candidate_version": "xgb-baseline-001",
    "model_params": params,
    "preprocessing": "Unchanged training-fitted pipeline from the Random Forest baseline.",
    "seed": SEED,
    "source_file": preparation["source_file"],
    "versions": {
        "python": platform.python_version(), "numpy": np.__version__,
        "pandas": pd.__version__, "scikit-learn": sklearn.__version__,
        "joblib": joblib.__version__, "xgboost": xgboost.__version__,
    },
}
for filename, content in {
    "feature_schema.json": schema,
    "model_params.json": metadata,
    "label_mapping.json": LABEL_MAPPING,
    "evaluation_metrics.json": metrics,
}.items():
    (OUTPUT / filename).write_text(json.dumps(content, indent=2), encoding="utf-8")

loaded_preprocessor = joblib.load(OUTPUT / "preprocessor.joblib")
loaded_model = joblib.load(OUTPUT / "model.joblib")
reloaded_predictions = loaded_model.predict(loaded_preprocessor.transform(X_validation.iloc[:10]))
assert np.array_equal(reloaded_predictions, predictions[:10])
native_model = XGBClassifier(n_jobs=2)
native_model.load_model(OUTPUT / "model.ubj")
assert np.array_equal(native_model.predict(validation_prepared[:10]), predictions[:10])

# Compare measured validation results; these targets are educational design choices.
rows = []
for name, result in {"random_forest": rf_metrics, "xgboost": metrics}.items():
    rows.append({
        "candidate": name,
        **{key: result[key] for key in [
            "accuracy", "attack_precision", "attack_recall", "attack_f1",
            "false_positive_rate", "roc_auc", "model_bytes", "validation_batch_ms_per_flow",
        ]},
        "passes_quality_gate": bool(
            result["attack_recall"] >= QUALITY_GATE["min_attack_recall"]
            and result["attack_f1"] >= QUALITY_GATE["min_attack_f1"]
            and result["false_positive_rate"] <= QUALITY_GATE["max_false_positive_rate"]
        ),
    })

comparison = pd.DataFrame(rows)
eligible = comparison.loc[comparison["passes_quality_gate"]].sort_values(
    ["attack_recall", "false_positive_rate", "attack_f1", "model_bytes", "validation_batch_ms_per_flow"],
    ascending=[False, True, False, True, True], kind="stable",
)
recommended = None if eligible.empty else str(eligible.iloc[0]["candidate"])
summary = {
    "evaluation_split": "validation",
    "quality_gate": QUALITY_GATE,
    "ranking": "Among passing candidates: recall descending, FPR ascending, F1 descending, size ascending, latency ascending.",
    "candidates": rows,
    "recommended_candidate": recommended,
    "status": "Recommendation only; final test evaluation and promotion have not run.",
}
comparison.to_csv(ROOT / "artifacts/model_comparison.csv", index=False)
(ROOT / "artifacts/model_comparison.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

print(json.dumps(metrics, indent=2))
print("\nVALIDATION COMPARISON (metric values are fractions, not percentages)")
print(comparison.to_string(index=False))
print("\nValidation recommendation:", recommended or "No candidate passed the quality gate")
print("Saved XGBoost artifacts:", OUTPUT)
print("Both reload checks passed. Final test evaluation has not run.")
display = ConfusionMatrixDisplay(matrix, display_labels=["BENIGN", "ATTACK"])
display.plot(cmap="Blues", values_format="d")
plt.title("XGBoost — validation confusion matrix")
plt.tight_layout()
plt.savefig(OUTPUT / "validation_confusion_matrix.png", dpi=150)
plt.show()
