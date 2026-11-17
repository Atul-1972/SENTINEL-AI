import json
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.model_selection import train_test_split

SEED = 42
TARGET_ROWS = 20_000
ROOT = Path("/content/SENTINEL-AI")

# Load the same file and unique column names used during inspection.
inspection = json.loads(
    Path("/content/dataset_inspection.json").read_text(encoding="utf-8")
)
CSV_PATH = Path("/content") / inspection["file"]
data = pd.read_csv(CSV_PATH, encoding="utf-8-sig", low_memory=False)
if len(data.columns) != len(inspection["columns"]):
    raise ValueError("The file schema changed. Run inspection again.")
data.columns = inspection["columns"]
original_rows = len(data)

label_column = inspection["label_column"]
labels = data[label_column].astype("string").str.strip().replace("", pd.NA)
missing_labels = int(labels.isna().sum())
data = data.loc[labels.notna()].copy()
labels = labels.loc[labels.notna()].str.upper()

# This first model is specifically BENIGN versus DDoS.
if set(labels.unique()) != {"BENIGN", "DDOS"}:
    raise ValueError("Expected BENIGN and DDoS. Inspect the actual labels before continuing.")

# Exclude identifiers and timestamps from model inputs.
identifier_names = {
    "flowid", "sourceip", "srcip", "destinationip", "dstip",
    "timestamp", "time", "date",
}
excluded = [
    name for name in data.columns
    if name != label_column
    and "".join(c for c in name.lower() if c.isalnum()) in identifier_names
]
features = [
    name for name in data.columns
    if name != label_column and name not in excluded
]
if not features:
    raise ValueError("No candidate features remain.")

# Fixed conversions only: learn no averages or feature-selection rules here.
X = data[features].apply(pd.to_numeric, errors="coerce")
infinite_values = int(np.isinf(X).sum().sum())
X = X.replace([np.inf, -np.inf], np.nan)
clean = X.copy()
clean["Label"] = np.where(labels.eq("BENIGN"), "BENIGN", "ATTACK")

empty_rows = clean[features].isna().all(axis=1)
empty_feature_rows = int(empty_rows.sum())
clean = clean.loc[~empty_rows].copy()

# Remove repeated model-input/label records before any random split.
before = len(clean)
clean = clean.drop_duplicates(subset=features + ["Label"])
duplicate_rows_removed = before - len(clean)

# Remaining identical inputs with different labels are ambiguous.
# Remove both records rather than putting them in different partitions.
conflicting = clean.duplicated(subset=features, keep=False)
conflicting_rows_removed = int(conflicting.sum())
clean = clean.loc[~conflicting].copy()

if set(clean["Label"]) != {"BENIGN", "ATTACK"}:
    raise ValueError("Both classes must remain after cleaning.")

# Preserve the cleaned data's class proportions, rather than forcing 50/50.
if len(clean) > TARGET_ROWS:
    sample, _ = train_test_split(
        clean,
        train_size=TARGET_ROWS,
        stratify=clean["Label"],
        random_state=SEED,
    )
else:
    sample = clean.sample(frac=1, random_state=SEED).copy()

if sample["Label"].value_counts().min() < 5:
    raise ValueError("Too few records in one class for a reliable three-way split.")

# 60% training, 20% validation, 20% untouched final test.
train, remaining = train_test_split(
    sample, test_size=0.4, stratify=sample["Label"], random_state=SEED
)
validation, test = train_test_split(
    remaining, test_size=0.5, stratify=remaining["Label"], random_state=SEED
)

assert set(train.index).isdisjoint(validation.index)
assert set(train.index).isdisjoint(test.index)
assert set(validation.index).isdisjoint(test.index)
assert len(train) + len(validation) + len(test) == len(sample)
assert not sample.duplicated(subset=features).any()

# Missing values remain NaN. Fit the imputer using training data only later.
(ROOT / "data/sample").mkdir(parents=True, exist_ok=True)
(ROOT / "data/processed").mkdir(parents=True, exist_ok=True)
sample.to_csv(ROOT / "data/sample/sentinel_subset.csv", index=False)

splits = {"train": train, "validation": validation, "test": test}
for name, frame in splits.items():
    frame.to_csv(ROOT / f"data/processed/{name}.csv", index=False)

prep_report = {
    "source_file": CSV_PATH.name,
    "original_rows": original_rows,
    "missing_labels_removed": missing_labels,
    "infinite_values_replaced_with_nan": infinite_values,
    "empty_feature_rows_removed": empty_feature_rows,
    "duplicate_rows_removed": duplicate_rows_removed,
    "conflicting_rows_removed": conflicting_rows_removed,
    "cleaned_rows": len(clean),
    "cleaned_class_counts": clean["Label"].value_counts().to_dict(),
    "sample_rows": len(sample),
    "sample_class_counts": sample["Label"].value_counts().to_dict(),
    "excluded_identifier_columns": excluded,
    "candidate_feature_count": len(features),
    "candidate_features": features,
    "splits": {
        name: {
            "rows": len(frame),
            "class_counts": frame["Label"].value_counts().to_dict(),
        }
        for name, frame in splits.items()
    },
    "seed": SEED,
    "label_mapping": {"BENIGN": 0, "ATTACK": 1},
    "supported_attack_labels": ["DDoS"],
    "split_method": "Stratified random split within one capture file",
    "limitation": "Related flows may remain across splits; this is not an independent-day test.",
    "preprocessing": "No imputer or feature selector fitted yet; NaN values retained.",
    "versions": {"pandas": pd.__version__, "numpy": np.__version__, "sklearn": sklearn.__version__},
}

(ROOT / "preparation_report.json").write_text(
    json.dumps(prep_report, indent=2), encoding="utf-8"
)
print(json.dumps(prep_report, indent=2))
print("\nSaved data under:", ROOT)
print("No model has been trained. Do not use the test set to choose a model.")

