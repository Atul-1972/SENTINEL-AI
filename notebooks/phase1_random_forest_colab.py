import json
import platform
from pathlib import Path
from time import perf_counter

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import VarianceThreshold
from sklearn.impute import SimpleImputer
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
from sklearn.pipeline import Pipeline

ROOT = Path("/content/SENTINEL-AI")
OUTPUT = ROOT / "artifacts/candidates/random_forest"
SEED = 42
LABEL_MAPPING = {"BENIGN": 0, "ATTACK": 1}

if not (ROOT / "preparation_report.json").is_file():
    raise FileNotFoundError("Run Step 7 first. Its preparation report is missing.")

preparation = json.loads((ROOT / "preparation_report.json").read_text(encoding="utf-8"))
feature_names = preparation["candidate_features"]
if not feature_names or len(feature_names) != len(set(feature_names)):
    raise ValueError("Candidate feature names must be nonempty and unique.")

# Read only training and validation data. Reserve test.csv for final evaluation.
train = pd.read_csv(ROOT / "data/processed/train.csv")
validation = pd.read_csv(ROOT / "data/processed/validation.csv")
expected_columns = set(feature_names) | {"Label"}
for name, frame in {"train": train, "validation": validation}.items():
    if set(frame.columns) != expected_columns:
        raise ValueError(f"{name} columns do not match the preparation report.")
    if set(frame["Label"]) != set(LABEL_MAPPING):
        raise ValueError(f"{name} must contain BENIGN and ATTACK labels only.")

X_train = train[feature_names].apply(pd.to_numeric, errors="raise")
X_validation = validation[feature_names].apply(pd.to_numeric, errors="raise")
X_train = X_train.replace([np.inf, -np.inf], np.nan)
X_validation = X_validation.replace([np.inf, -np.inf], np.nan)
y_train = train["Label"].map(LABEL_MAPPING).to_numpy(dtype=int)
y_validation = validation["Label"].map(LABEL_MAPPING).to_numpy(dtype=int)

# Fit missing-value handling and constant-feature removal on training data only.
# Empty training columns become zero and are removed by VarianceThreshold.
preprocessor = Pipeline([
    ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
    ("constant_filter", VarianceThreshold(threshold=0.0)),
])

model = RandomForestClassifier(
    n_estimators=100,
    max_depth=16,
    min_samples_leaf=2,
    class_weight="balanced_subsample",
    random_state=SEED,
    n_jobs=2,
)

print("Training Random Forest; the test set remains reserved.")
started = perf_counter()
train_prepared = preprocessor.fit_transform(X_train)
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
    "model": "RandomForestClassifier",
    "candidate_version": "rf-baseline-001",
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
    "validation_batch_ms_per_flow": prediction_seconds * 1000 / len(validation),
    "latency_note": "Amortized batch time including preprocessing; not single-request API latency.",
    "probability_note": "Random Forest probabilities are not calibrated confidence scores.",
    "classification_report": classification_report(
        y_validation, predictions, labels=[0, 1],
        target_names=["BENIGN", "ATTACK"], output_dict=True, zero_division=0,
    ),
}

# Candidate artifacts only. Final model selection follows XGBoost comparison.
OUTPUT.mkdir(parents=True, exist_ok=True)
joblib.dump(model, OUTPUT / "model.joblib", compress=3)
joblib.dump(preprocessor, OUTPUT / "preprocessor.joblib", compress=3)
metrics["model_bytes"] = (OUTPUT / "model.joblib").stat().st_size

selected_names = np.asarray(feature_names)[
    preprocessor.named_steps["constant_filter"].get_support()
].tolist()
schema = {
    "feature_names": feature_names,
    "feature_types": {name: "numeric" for name in feature_names},
    "feature_order_required": True,
    "missing_values": "NaN accepted; training-fitted median imputation applied.",
    "selected_feature_names": selected_names,
    "supported_attack_labels": ["DDoS"],
    "label_mapping": LABEL_MAPPING,
}
metadata = {
    "candidate_version": "rf-baseline-001",
    "model_params": model.get_params(),
    "preprocessing": {"imputer": "training median", "constant_filter_threshold": 0.0},
    "seed": SEED,
    "source_file": preparation["source_file"],
    "versions": {
        "python": platform.python_version(), "numpy": np.__version__,
        "pandas": pd.__version__, "scikit-learn": sklearn.__version__, "joblib": joblib.__version__,
    },
}
for filename, content in {
    "feature_schema.json": schema,
    "model_params.json": metadata,
    "label_mapping.json": LABEL_MAPPING,
    "evaluation_metrics.json": metrics,
}.items():
    (OUTPUT / filename).write_text(json.dumps(content, indent=2), encoding="utf-8")

# Verify saved preprocessing and model reproduce predictions on validation rows.
loaded_preprocessor = joblib.load(OUTPUT / "preprocessor.joblib")
loaded_model = joblib.load(OUTPUT / "model.joblib")
reloaded_predictions = loaded_model.predict(loaded_preprocessor.transform(X_validation.iloc[:10]))
assert np.array_equal(reloaded_predictions, predictions[:10])

print(json.dumps(metrics, indent=2))
print("\nSaved candidate artifacts:", OUTPUT)
print("Artifact reload check passed. Final test evaluation has not run.")

display = ConfusionMatrixDisplay(matrix, display_labels=["BENIGN", "ATTACK"])
display.plot(cmap="Blues", values_format="d")
plt.title("Random Forest — validation confusion matrix")
plt.tight_layout()
plt.savefig(OUTPUT / "validation_confusion_matrix.png", dpi=150)
plt.show()
