import json
import platform
from pathlib import Path
from time import perf_counter

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score

ROOT = Path("/content/SENTINEL-AI")
OUTPUT = ROOT / "artifacts/candidates/isolation_forest"
SEED = 42
CONTAMINATION = 0.05

comparison_path = ROOT / "artifacts/model_comparison.json"
if not comparison_path.is_file():
    raise FileNotFoundError("Run Step 9 first. The model comparison report is missing.")
comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
selected = comparison["recommended_candidate"]
if selected not in {"random_forest", "xgboost"}:
    raise ValueError("No supervised candidate was recommended. Review validation results first.")
if not any(row["candidate"] == selected and row["passes_quality_gate"] for row in comparison["candidates"]):
    raise ValueError("The recommended classifier must pass the validation quality gate.")

candidate = ROOT / "artifacts/candidates" / selected
schema = json.loads((candidate / "feature_schema.json").read_text(encoding="utf-8"))
features = schema["feature_names"]
preprocessor = joblib.load(candidate / "preprocessor.joblib")

# Reuse saved training-only preprocessing. Do not fit it again.
train = pd.read_csv(ROOT / "data/processed/train.csv")
validation = pd.read_csv(ROOT / "data/processed/validation.csv")
for name, frame in {"train": train, "validation": validation}.items():
    if set(frame.columns) != set(features) | {"Label"}:
        raise ValueError(f"{name} columns do not match the selected classifier schema.")
    if set(frame["Label"]) != {"BENIGN", "ATTACK"}:
        raise ValueError(f"{name} must contain both BENIGN and ATTACK labels only.")

# Known BENIGN training records define the normal reference distribution.
# Isolation Forest receives features only, not attack labels as training targets.
normal_reference = train.loc[train["Label"].eq("BENIGN"), features]
if len(normal_reference) < 20:
    raise ValueError("Too few BENIGN training records for the anomaly reference.")
normal_reference = normal_reference.apply(pd.to_numeric, errors="raise").replace([np.inf, -np.inf], np.nan)
X_validation = validation[features].apply(pd.to_numeric, errors="raise").replace([np.inf, -np.inf], np.nan)
reference_prepared = preprocessor.transform(normal_reference)
validation_prepared = preprocessor.transform(X_validation)

params = {
    "n_estimators": 100,
    "max_samples": min(256, len(normal_reference)),
    "contamination": CONTAMINATION,
    "random_state": SEED,
    "n_jobs": 2,
}
anomaly_model = IsolationForest(**params)
started = perf_counter()
anomaly_model.fit(reference_prepared)
training_seconds = perf_counter() - started

# Negating decision_function makes larger scores mean more unusual flows.
# A score greater than zero corresponds to Isolation Forest's -1 anomaly flag.
anomaly_scores = -anomaly_model.decision_function(validation_prepared)
anomaly_flags = anomaly_model.predict(validation_prepared) == -1
assert np.array_equal(anomaly_flags, anomaly_scores > 0)
y_validation = validation["Label"].map({"BENIGN": 0, "ATTACK": 1}).to_numpy(dtype=int)
matrix = confusion_matrix(y_validation, anomaly_flags.astype(int), labels=[0, 1])
tn, fp, fn, tp = matrix.ravel()

metrics = {
    "model": "IsolationForest",
    "candidate_version": "if-baseline-001",
    "evaluation_split": "validation",
    "training_reference": "BENIGN records from the training split only",
    "training_reference_rows": len(normal_reference),
    "validation_rows": len(validation),
    "selected_classifier": selected,
    "contamination": CONTAMINATION,
    "threshold_note": "5% is a training reference cutoff setting, not the live attack probability or guaranteed validation false-positive rate.",
    "anomaly_score_definition": "-decision_function; higher is more unusual; > 0 flags an anomaly",
    "score_is_probability": False,
    "predicts_attack_category": False,
    "validation_anomaly_count": int(anomaly_flags.sum()),
    "validation_anomaly_fraction": float(anomaly_flags.mean()),
    "training_seconds": training_seconds,
    "diagnostics_against_known_binary_labels": {
        "note": "Compare anomaly flags with known validation labels for diagnosis only; these flags do not assign attack categories.",
        "precision": float(precision_score(y_validation, anomaly_flags, zero_division=0)),
        "attack_recall": float(recall_score(y_validation, anomaly_flags, zero_division=0)),
        "f1": float(f1_score(y_validation, anomaly_flags, zero_division=0)),
        "benign_false_positive_rate": float(fp / (tn + fp)),
        "roc_auc": float(roc_auc_score(y_validation, anomaly_scores)),
        "confusion_matrix": matrix.tolist(),
        "matrix_true_rows": ["BENIGN", "ATTACK"],
        "matrix_predicted_columns": ["NORMAL_FLAG", "ANOMALY_FLAG"],
    },
}

OUTPUT.mkdir(parents=True, exist_ok=True)
joblib.dump(anomaly_model, OUTPUT / "anomaly_model.joblib", compress=3)
joblib.dump(preprocessor, OUTPUT / "preprocessor.joblib", compress=3)
metrics["model_bytes"] = (OUTPUT / "anomaly_model.joblib").stat().st_size
metadata = {
    "candidate_version": "if-baseline-001",
    "model_params": params,
    "anomaly_score_definition": metrics["anomaly_score_definition"],
    "preprocessing": "Shared unchanged training-fitted pipeline from the selected classifier.",
    "versions": {
        "python": platform.python_version(), "numpy": np.__version__,
        "pandas": pd.__version__, "scikit-learn": sklearn.__version__, "joblib": joblib.__version__,
    },
}
for filename, content in {
    "feature_schema.json": schema,
    "model_params.json": metadata,
    "evaluation_metrics.json": metrics,
}.items():
    (OUTPUT / filename).write_text(json.dumps(content, indent=2), encoding="utf-8")

pd.DataFrame({
    "validation_row": np.arange(len(validation)),
    "true_binary_label": validation["Label"],
    "anomaly_score": anomaly_scores,
    "anomaly_flag": anomaly_flags,
}).to_csv(OUTPUT / "validation_anomaly_scores.csv", index=False)

loaded_model = joblib.load(OUTPUT / "anomaly_model.joblib")
loaded_preprocessor = joblib.load(OUTPUT / "preprocessor.joblib")
reloaded_scores = -loaded_model.decision_function(loaded_preprocessor.transform(X_validation.iloc[:10]))
assert np.allclose(reloaded_scores, anomaly_scores[:10])
assert np.array_equal(loaded_model.predict(validation_prepared[:10]) == -1, anomaly_flags[:10])

print(json.dumps(metrics, indent=2))
print("\nSaved anomaly artifacts:", OUTPUT)
print("Reload checks passed. Classifier recommendation remains:", selected)
print("Anomaly flags are separate from attack classification. No test data was evaluated.")

fig, ax = plt.subplots()
for label in ["BENIGN", "ATTACK"]:
    ax.hist(anomaly_scores[validation["Label"].eq(label).to_numpy()], bins=35, alpha=0.55, label=label)
ax.axvline(0, color="black", linestyle="--", label="Anomaly cutoff")
ax.set_title("Isolation Forest — validation score distributions")
ax.set_xlabel("Anomaly score (not a probability); higher is more unusual")
ax.set_ylabel("Number of validation flows")
ax.legend()
fig.tight_layout()
fig.savefig(OUTPUT / "validation_anomaly_scores.png", dpi=150)
plt.show()
