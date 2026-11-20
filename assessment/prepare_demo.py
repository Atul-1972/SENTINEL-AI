"""Create labelled replay and separate gate data from the existing validation CSV."""

import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

from assessment.workflow import ASSESSMENT, PROJECT, checksum, ensure_disjoint, validate_csv, write_json


def prepare_demo():
    directory = ASSESSMENT / "data"
    incoming_path = directory / "incoming_replay.csv"
    holdout_path = directory / "gate_holdout.csv"
    manifest_path = directory / "demo_manifest.json"
    source = PROJECT / "data/processed/validation.csv"
    if any(path.exists() for path in (incoming_path, holdout_path, manifest_path)):
        if all(path.is_file() for path in (incoming_path, holdout_path, manifest_path)):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (
                checksum(source) == manifest["source_sha256"]
                and checksum(incoming_path) == manifest["incoming_sha256"]
                and checksum(holdout_path) == manifest["holdout_sha256"]
            ):
                return incoming_path, holdout_path
        raise ValueError("Existing demo files differ or are incomplete. They will not be overwritten.")
    schema = json.loads((PROJECT / "artifacts/feature_schema.json").read_text(encoding="utf-8"))
    features = schema["feature_names"]
    frame, validation = validate_csv(source, features, "historical_validation_source")
    if len(frame) != 4000:
        raise ValueError("This replay setup expects the project's original 4,000-row validation split.")
    incoming_indices, holdout_indices = train_test_split(
        np.arange(len(frame)), train_size=1000, random_state=42, stratify=frame["Label"],
    )
    incoming = frame.iloc[incoming_indices].copy()
    holdout = frame.iloc[holdout_indices].copy()
    incoming["record_id"] = [f"validation-clean-row-{int(index) + 1}" for index in incoming_indices]
    holdout["record_id"] = [f"validation-clean-row-{int(index) + 1}" for index in holdout_indices]
    training, _ = validate_csv(PROJECT / "data/processed/train.csv", features, "training")
    ensure_disjoint(training, incoming, holdout, features)
    directory.mkdir(parents=True, exist_ok=True)
    incoming.to_csv(incoming_path, index=False, na_rep="", float_format="%.17g")
    holdout.to_csv(holdout_path, index=False, na_rep="", float_format="%.17g")
    write_json(manifest_path, {
        "batch_origin": "historical_replay",
        "description": "Replay of labelled validation records, not newly collected traffic.",
        "limitation": "The source validation split was already used for original model selection.",
        "source_file": str(source), "source_sha256": checksum(source), "seed": 42,
        "incoming_rows": len(incoming), "holdout_rows": len(holdout),
        "incoming_distribution": {str(k): int(v) for k, v in incoming["Label"].value_counts().items()},
        "holdout_distribution": {str(k): int(v) for k, v in holdout["Label"].value_counts().items()},
        "incoming_sha256": checksum(incoming_path), "holdout_sha256": checksum(holdout_path),
        "original_final_test_read": False, "source_validation": validation,
    })
    return incoming_path, holdout_path


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    incoming, holdout = prepare_demo()
    print(f"Historical incoming replay: {incoming}")
    print(f"Separate comparison holdout: {holdout}")
    print("No final test CSV was read. Existing source files were not changed.")


if __name__ == "__main__":
    main()
