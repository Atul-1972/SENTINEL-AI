import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import joblib
from sklearn.feature_selection import VarianceThreshold
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

import assessment.workflow as workflow
from assessment.workflow import (
    PROJECT, ValidationError, canonical_headers, ensure_disjoint,
    evaluate, quality_gate, run_workflow, validate_csv,
)

FEATURES = ["duration", "rate"]


def make_csv(tmp_path, rows, columns=None):
    path = tmp_path / "batch.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns or FEATURES + ["Label"])
        writer.writerows(rows)
    return path


def test_validation_reports_missing_values_duplicates_and_class_distribution(tmp_path):
    path = make_csv(tmp_path, [
        [1, "", "BENIGN"], [1, "", "BENIGN"], [2, "Infinity", "DDoS"], [3, 4, "attack"],
    ])
    frame, report = validate_csv(path, FEATURES, "incoming")
    assert len(frame) == 3
    assert report["duplicate_feature_rows_removed"] == 1
    assert report["target_distribution"] == {"ATTACK": 2, "BENIGN": 1}
    assert report["missing_feature_values"] == {"rate": 2}
    assert report["infinite_values_replaced_with_missing"] == {"rate": 1}
    assert frame["rate"].isna().sum() == 2


@pytest.mark.parametrize("rows,columns,message", [
    ([[1, "BENIGN"]], ["duration", "Label"], "Schema mismatch"),
    ([[1, 2, ""]], None, "Missing target"),
    ([[1, 2, "PortScan"]], None, "Unsupported labels"),
    ([[1, "wrong", "BENIGN"]], None, "nonnumeric"),
    ([["", "", "BENIGN"]], None, "no usable feature"),
    ([[1, 2, "BENIGN"], [1, 2, "ATTACK"]], None, "conflicting labels"),
    ([[1, 2, "BENIGN", "x"], [2, 3, "ATTACK", "x"]],
     FEATURES + ["Label", "record_id"], "Duplicate record_id"),
    ([[1, 2, "BENIGN", "extra"]], None, "cells"),
])
def test_validation_rejects_bad_batches(tmp_path, rows, columns, message):
    with pytest.raises(ValidationError, match=message):
        validate_csv(make_csv(tmp_path, rows, columns), FEATURES, "incoming")


def test_duplicate_headers_preserve_values_without_suffix_collisions():
    names, renamed = canonical_headers(["a", "a", "a__duplicate_2", "Label"])
    assert names == ["a", "a__duplicate_3", "a__duplicate_2", "Label"]
    assert renamed[0]["position"] == 2
    with pytest.raises(ValidationError, match="Exactly one Label"):
        canonical_headers(["duration", "Label", "label"])


def test_overlap_checks_features_independently_of_labels_and_ids():
    train = pd.DataFrame({"duration": [1.0], "rate": [2.0], "Label": ["BENIGN"]})
    incoming = pd.DataFrame({"duration": [1.0], "rate": [2.0], "Label": ["ATTACK"]})
    holdout = pd.DataFrame({"duration": [3.0], "rate": [4.0], "Label": ["ATTACK"]})
    with pytest.raises(ValidationError, match="share feature records"):
        ensure_disjoint(train, incoming, holdout, FEATURES)
    incoming.loc[0, "duration"] = 5.0
    assert ensure_disjoint(train, incoming, holdout, FEATURES)["passed"]
    train["record_id"] = incoming["record_id"] = "same"
    with pytest.raises(ValidationError, match="record_id values overlap"):
        ensure_disjoint(train, incoming, holdout, FEATURES)


def test_quality_gate_pass_and_reject_do_not_promote():
    champion = {"recall": 0.99, "f1": 0.99, "false_positive_rate": 0.001}
    decision = quality_gate(champion, champion)
    assert decision["eligible_for_promotion"] is True
    assert decision["champion_replaced"] is False
    candidate = {**champion, "recall": 0.985}
    decision = quality_gate(champion, candidate)
    assert decision["decision"] == "retain_champion"
    assert "attack_recall_not_worse_than_champion" in decision["failed_checks"]
    assert quality_gate(champion, {**champion, "f1": 0.97})["eligible_for_promotion"] is False
    assert quality_gate(champion, {**champion, "false_positive_rate": 0.02})["eligible_for_promotion"] is False
    with pytest.raises(ValueError, match="finite fractions"):
        quality_gate(champion, champion, {"min_recall": 1.2})


def test_metrics_use_attack_as_positive_and_do_not_fit_preprocessing():
    class Preprocessor:
        def transform(self, frame):
            return frame.to_numpy()

        def fit(self, *args):
            raise AssertionError("Evaluation must not fit preprocessing.")

    class Model:
        def predict(self, frame):
            return np.array([0, 0, 1, 1])

    frame = pd.DataFrame({"duration": [1, 2, 3, 4], "rate": [1, 2, 3, 4],
                          "Label": ["BENIGN", "ATTACK", "BENIGN", "ATTACK"]})
    metrics, _ = evaluate(Model(), Preprocessor(), frame, FEATURES)
    assert metrics["accuracy"] == metrics["precision"] == metrics["recall"] == metrics["f1"] == 0.5
    assert metrics["false_positive_rate"] == 0.5
    assert metrics["confusion_matrix"] == [[1, 1], [1, 1]]


def test_original_final_test_is_refused_before_any_read(monkeypatch):
    def forbidden_read(*args, **kwargs):
        raise AssertionError("The final test CSV must not be opened or hashed.")

    monkeypatch.setattr(Path, "open", forbidden_read)
    with pytest.raises(ValidationError, match="final test"):
        validate_csv(PROJECT / "data/processed/test.csv", FEATURES, "incoming")
    with pytest.raises(ValidationError, match="final test"):
        run_workflow(PROJECT / "data/processed/test.csv", PROJECT / "data/processed/validation.csv",
                     origin="historical_replay")


def test_complete_workflow_saves_candidate_and_refits_only_on_combined_training(tmp_path, monkeypatch):
    """Tiny synthetic fixture; no real project models or data are modified."""
    monkeypatch.setattr(workflow, "ASSESSMENT", tmp_path)
    artifact_dir = tmp_path / "champion"
    artifact_dir.mkdir()
    training = pd.DataFrame({"duration": np.arange(6), "rate": np.arange(6) + 2,
                             "Label": ["BENIGN"] * 3 + ["ATTACK"] * 3})
    incoming = pd.DataFrame({"duration": np.arange(6, 10), "rate": np.arange(6, 10) + 2,
                             "Label": ["ATTACK"] * 4})
    holdout = pd.DataFrame({"duration": np.arange(100, 104), "rate": np.arange(100, 104) + 2,
                            "Label": ["BENIGN", "BENIGN", "ATTACK", "ATTACK"]})
    paths = {}
    for name, frame in (("train", training), ("incoming", incoming), ("holdout", holdout)):
        paths[name] = tmp_path / f"{name}.csv"
        frame.to_csv(paths[name], index=False)
    preprocessor = Pipeline([
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("constant_filter", VarianceThreshold()),
    ])
    prepared = preprocessor.fit_transform(training[FEATURES])
    params = {"n_estimators": 3, "max_depth": 1, "n_jobs": 1,
              "min_child_weight": 0, "tree_method": "hist", "random_state": 42}
    champion = XGBClassifier(**params).fit(prepared, np.array([0, 0, 0, 1, 1, 1]))
    champion.save_model(artifact_dir / "model.ubj")
    joblib.dump(preprocessor, artifact_dir / "preprocessor.joblib")
    workflow.write_json(artifact_dir / "feature_schema.json", {"feature_names": FEATURES, "selected_feature_names": FEATURES})
    workflow.write_json(artifact_dir / "label_mapping.json", workflow.LABELS)
    workflow.write_json(artifact_dir / "model_params.json", {
        "selected_candidate": "xgboost", "eligible_for_api_demo": True,
        "model_version": "synthetic-test-champion", "versions": {}, "model_params": params,
    })
    champion_hash = workflow.checksum(artifact_dir / "model.ubj")
    report = run_workflow(paths["incoming"], paths["holdout"], origin="historical_replay",
                          training_data=paths["train"], artifacts_dir=artifact_dir,
                          output_root=tmp_path / "runs")
    output = Path(report["output_directory"])
    saved_preprocessor = joblib.load(output / "candidate/preprocessor.joblib")
    assert saved_preprocessor.named_steps["imputer"].statistics_[0] == 4.5
    assert preprocessor.named_steps["imputer"].statistics_[0] == 2.5
    assert report["combined_training_rows"] == 10
    assert report["candidate_holdout"]["rows"] == 4
    assert report["existing_model_new_batch"]["rows"] == 4
    assert report["candidate_reload_passed"] and report["protected_sources_unchanged"]
    assert workflow.checksum(artifact_dir / "model.ubj") == champion_hash
    assert report["quality_gate"]["champion_replaced"] is False
    for filename in ("existing_model_evaluation.json", "candidate_evaluation.json",
                     "quality_gate_decision.json", "report.html", "execution.log"):
        assert (output / filename).is_file()
