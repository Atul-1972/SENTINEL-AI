"""Validate a labelled batch, measure the champion, and train a separate candidate."""

import csv
import hashlib
import html
import json
import platform
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import joblib
import numpy as np
import pandas as pd
import xgboost
from sklearn.base import clone
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from xgboost import XGBClassifier

PROJECT = Path(__file__).resolve().parents[1]
ASSESSMENT = Path(__file__).resolve().parent
LABELS = {"BENIGN": 0, "ATTACK": 1}
TARGET_ALIASES = {"BENIGN": "BENIGN", "ATTACK": "ATTACK", "DDOS": "ATTACK"}
MISSING = {"", "nan", "na", "n/a", "null", "none"}
NONFINITE = {"inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}
DEFAULT_GATE = {"min_recall": 0.98, "min_f1": 0.98, "max_false_positive_rate": 0.01}


class ValidationError(ValueError):
    def __init__(self, message, report=None):
        super().__init__(message)
        self.report = report or {}


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def fingerprints(frame, features):
    # Labels and record IDs cannot hide a duplicate feature vector.
    numeric = frame[features].astype("float64").copy()
    numeric[numeric == 0] = 0.0
    numeric = numeric.where(numeric.notna(), np.nan)
    return pd.util.hash_pandas_object(numeric, index=False)


def canonical_headers(header):
    trimmed = [name.strip().lstrip("\ufeff") for name in header]
    if any(not name for name in trimmed):
        raise ValidationError("Empty column name.")
    if sum(name.casefold() == "label" for name in trimmed) != 1:
        raise ValidationError("Exactly one Label column is required.")
    reserved, used, names, renamed = set(trimmed), set(), [], []
    for index, name in enumerate(trimmed):
        result, suffix = name, 2
        if name in used:
            result = f"{name}__duplicate_{suffix}"
            while result in used or result in reserved:
                suffix += 1
                result = f"{name}__duplicate_{suffix}"
            renamed.append({"position": index + 1, "original": name, "canonical": result})
        used.add(result)
        names.append("Label" if result.casefold() == "label" else result)
    return names, renamed


def validate_csv(path, features, role):
    """Retain missing feature cells for imputation; reject missing/unknown labels."""
    path = Path(path).resolve()
    if path == (PROJECT / "data/processed/test.csv").resolve():
        raise ValidationError("The original final test set must not be used in this assessment.")
    report = {"role": role, "file": str(path), "valid": False}

    def fail(message):
        report["error"] = message
        raise ValidationError(f"{role}: {message}", report)

    if not path.is_file():
        fail("CSV file not found.")
    if path.stat().st_size > 25 * 1024 * 1024:
        fail("Use a CSV no larger than 25 MB for this practical.")
    report["sha256"] = checksum(path)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            names, renamed = canonical_headers(next(reader, []))
        except ValidationError as error:
            fail(str(error))
        missing = sorted(set(features) - set(names))
        extra = sorted(set(names) - set(features) - {"Label", "record_id"})
        report.update({"missing_columns": missing, "unexpected_columns": extra, "renamed_headers": renamed})
        if missing or extra:
            fail(f"Schema mismatch. Missing: {missing}; unexpected: {extra}.")
        rows = []
        for line_number, row in enumerate(reader, start=2):
            if not row or all(not value.strip() for value in row):
                continue
            if len(row) != len(names):
                fail(f"Line {line_number} has {len(row)} cells, expected {len(names)}.")
            rows.append(row)
            if len(rows) > 20000:
                fail("Use at most 20,000 rows per input CSV.")
    if not rows:
        fail("No data records.")
    frame = pd.DataFrame(rows, columns=names)
    report["input_rows"] = len(frame)
    labels = frame["Label"].str.strip().str.upper()
    report["missing_labels"] = int(labels.str.lower().isin(MISSING).sum())
    if report["missing_labels"]:
        fail("Missing target labels cannot be used for supervised evaluation.")
    unknown = sorted(set(labels) - set(TARGET_ALIASES))
    if unknown:
        fail(f"Unsupported labels {unknown}; use BENIGN and ATTACK (DDoS is accepted as ATTACK).")
    frame["Label"] = labels.map(TARGET_ALIASES)
    report["duplicate_ids"] = 0
    if "record_id" in frame:
        frame["record_id"] = frame["record_id"].str.strip()
        if frame["record_id"].str.lower().isin(MISSING).any():
            fail("record_id contains missing IDs.")
        report["duplicate_ids"] = int(frame["record_id"].duplicated().sum())
        if report["duplicate_ids"]:
            fail("Duplicate record_id values; resolve them before running.")
    missing_counts, infinite_counts = {}, {}
    for name in features:
        text = frame[name].str.strip()
        lower = text.str.lower()
        missing_mask, infinite_mask = lower.isin(MISSING), lower.isin(NONFINITE)
        numbers = pd.to_numeric(text.mask(missing_mask | infinite_mask), errors="coerce")
        if ((~(missing_mask | infinite_mask)) & numbers.isna()).any():
            fail(f"{name} contains a nonnumeric value.")
        if (numbers.notna() & (~np.isfinite(numbers) | (numbers.abs() > np.finfo(np.float32).max))).any():
            fail(f"{name} contains a number outside the finite float32 range.")
        if missing_mask.any():
            missing_counts[name] = int(missing_mask.sum())
        if infinite_mask.any():
            infinite_counts[name] = int(infinite_mask.sum())
        frame[name] = numbers.astype("float64")
    report["missing_feature_values"] = missing_counts
    report["infinite_values_replaced_with_missing"] = infinite_counts
    if frame[features].isna().all(axis=1).any():
        fail("A record has no usable feature values.")
    keys = fingerprints(frame, features)
    conflicts = pd.DataFrame({"key": keys, "label": frame["Label"]}).groupby("key")["label"].nunique()
    if conflicts.gt(1).any():
        fail("Identical feature vectors have conflicting labels.")
    duplicate_mask = keys.duplicated()
    report["duplicate_feature_rows_removed"] = int(duplicate_mask.sum())
    frame = frame.loc[~duplicate_mask].reset_index(drop=True)
    report.update({
        "valid": True, "clean_rows": len(frame),
        "target_distribution": {str(k): int(v) for k, v in frame["Label"].value_counts().items()},
        "missing_value_policy": "Training-fitted median imputation; no label imputation.",
    })
    return frame, report


def ensure_disjoint(train, incoming, holdout, features):
    sets = {name: set(fingerprints(frame, features)) for name, frame in {
        "training": train, "incoming": incoming, "holdout": holdout,
    }.items()}
    checks = {}
    for left, right in (("training", "incoming"), ("training", "holdout"), ("incoming", "holdout")):
        checks[f"{left}_{right}_feature_overlap"] = len(sets[left] & sets[right])
        if checks[f"{left}_{right}_feature_overlap"]:
            raise ValidationError(f"{left} and {right} share feature records; use disjoint datasets.", checks)
    for left, right in ((train, incoming), (train, holdout), (incoming, holdout)):
        if "record_id" in left and "record_id" in right:
            if set(left["record_id"]) & set(right["record_id"]):
                raise ValidationError("record_id values overlap across input datasets.")
    checks["passed"] = True
    return checks


def evaluate(model, preprocessor, frame, features):
    truth = frame["Label"].map(LABELS).to_numpy(dtype=int)
    prepared = preprocessor.transform(frame[features])
    predictions = np.asarray(model.predict(prepared), dtype=int)
    matrix = confusion_matrix(truth, predictions, labels=[0, 1])
    tn, fp, fn, tp = matrix.ravel()
    metrics = {
        "rows": len(frame), "accuracy": float(accuracy_score(truth, predictions)),
        "precision": float(precision_score(truth, predictions, zero_division=0)),
        "recall": float(recall_score(truth, predictions, zero_division=0)),
        "f1": float(f1_score(truth, predictions, zero_division=0)),
        "false_positive_rate": float(fp / (tn + fp)) if tn + fp else None,
        "confusion_matrix": matrix.tolist(), "confusion_matrix_order": ["BENIGN", "ATTACK"],
        "positive_class": "ATTACK", "attack_support": int(tp + fn), "benign_support": int(tn + fp),
        "metric_note": "Precision, recall and F1 are for ATTACK; undefined precision/recall use zero.",
    }
    return metrics, predictions


def quality_gate(champion, candidate, criteria=None):
    criteria = dict(DEFAULT_GATE if criteria is None else criteria)
    for value in criteria.values():
        if not np.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Quality thresholds must be finite fractions between zero and one.")
    checks = {
        "attack_recall_at_least_minimum": candidate["recall"] >= criteria["min_recall"],
        "attack_f1_at_least_minimum": candidate["f1"] >= criteria["min_f1"],
        "false_positive_rate_within_limit": (
            candidate["false_positive_rate"] is not None
            and candidate["false_positive_rate"] <= criteria["max_false_positive_rate"]
        ),
        "attack_recall_not_worse_than_champion": candidate["recall"] >= champion["recall"],
        "attack_f1_not_worse_than_champion": candidate["f1"] >= champion["f1"],
    }
    eligible = all(checks.values())
    return {
        "decision": "eligible_for_promotion" if eligible else "retain_champion",
        "eligible_for_promotion": bool(eligible), "champion_replaced": False,
        "criteria": criteria, "checks": {name: bool(passed) for name, passed in checks.items()},
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "primary_metric": "attack_recall",
        "justification": "Missed attacks are costly. F1 and the false-positive limit also control poor precision and excessive alerts.",
        "comparison_scope": "Both models use the same holdout, excluded from all candidate fitting.",
        "promotion_policy": "Eligibility is a recorded recommendation. Deployment remains unchanged; manual review is required.",
    }


def load_champion(directory):
    directory = Path(directory).resolve()
    metadata = json.loads((directory / "model_params.json").read_text(encoding="utf-8"))
    schema = json.loads((directory / "feature_schema.json").read_text(encoding="utf-8"))
    if metadata.get("selected_candidate") != "xgboost" or metadata.get("eligible_for_api_demo") is not True:
        raise ValueError("Expected the approved exported XGBoost champion.")
    mapping = json.loads((directory / "label_mapping.json").read_text(encoding="utf-8"))
    if mapping != LABELS:
        raise ValueError("Champion label mapping does not match BENIGN/ATTACK.")
    for name, expected in metadata["versions"].items():
        actual = xgboost.__version__ if name == "xgboost" else (version(name) if name != "python" else expected)
        if actual != expected:
            raise ValueError(f"Use the project's model environment: expected {name}=={expected}.")
    model = XGBClassifier(n_jobs=2)
    model.load_model(directory / "model.ubj")
    preprocessor = joblib.load(directory / "preprocessor.joblib")
    if len(schema["feature_names"]) != preprocessor.n_features_in_:
        raise ValueError("Champion preprocessing and feature schema differ.")
    return model, preprocessor, schema, metadata


def render_html(report, destination):
    rows = []
    for label, values in (
        ("Champion on incoming batch (before retraining)", report["existing_model_new_batch"]),
        ("Champion on comparison holdout", report["champion_holdout"]),
        ("Candidate on comparison holdout", report["candidate_holdout"]),
    ):
        cells = "".join(f"<td>{values[key]:.4%}</td>" for key in ("accuracy", "precision", "recall", "f1"))
        rows.append(f"<tr><th>{html.escape(label)}</th><td>{values['rows']}</td>{cells}</tr>")
    checks = "".join(f"<li>{html.escape(name)}: {'PASS' if passed else 'FAIL'}</li>"
                     for name, passed in report["quality_gate"]["checks"].items())
    content = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SENTINEL assessment execution report</title>
<style>body{{font:16px system-ui;max-width:1000px;margin:40px auto;padding:0 20px;color:#172333}}
table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:12px;border:1px solid #d6dee5;text-align:left}}
h1,h2{{color:#164b4e}}code{{background:#edf3f5;padding:3px}}li{{margin:8px 0}}.box{{padding:18px;background:#edf6f4}}</style>
<h1>SENTINEL model monitoring and retraining assessment</h1>
<p>Run: <code>{html.escape(report['run_id'])}</code> | Completed: {html.escape(report['completed_at'])}</p>
<p>{html.escape(report['data_scope'])}</p>
<h2>Task A Data validation</h2><p>All input files passed schema, numeric, label and duplicate checks.
Training: {report['training_rows']:,} rows; incoming batch: {report['incoming_rows']:,};
holdout: {report['holdout_rows']:,}. No feature-record overlap across the three inputs.</p>
<h2>Task B Existing model and Task C Candidate evaluation</h2>
<div style="overflow:auto"><table><thead><tr><th>Evaluation</th><th>Rows</th><th>Accuracy</th><th>Attack precision</th><th>Attack recall</th><th>Attack F1</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p>Candidate trained on {report['combined_training_rows']:,} rows, combining original training and the full incoming batch.
The same preprocessing recipe was cloned and fitted only on that combined training data.</p>
<h2>Task D Quality gate</h2><p class="box"><strong>{html.escape(report['quality_gate']['decision'])}</strong>.
The deployed champion was not replaced.</p><ul>{checks}</ul>
<p>{html.escape(report['quality_gate']['justification'])}</p>
<h2>Task E Evidence</h2><p>Candidate: <code>candidate/model.ubj</code> and <code>candidate/preprocessor.joblib</code>.
See the JSON reports and execution.log alongside this page. Native-model reload check passed;
protected source checksums match before and after execution.</p>
<p>MLflow: not used; it is not installed in this project. Run parameters, package versions, input checksums,
metrics and the decision are recorded locally. No Airflow, DVC or drift-test integration is implied.</p>
<p>The original final test CSV was not read. Replay results are not independent-day or future-traffic evidence.</p>
</html>"""
    Path(destination).write_text(content, encoding="utf-8")


def run_workflow(new_data, gate_data, *, origin, training_data=None, artifacts_dir=None,
                 output_root=None, criteria=None):
    artifacts_dir = Path(artifacts_dir or PROJECT / "artifacts").resolve()
    training_data = Path(training_data or PROJECT / "data/processed/train.csv").resolve()
    output_root = Path(output_root or ASSESSMENT / "runs").resolve()
    if not output_root.is_relative_to(ASSESSMENT) or output_root == ASSESSMENT:
        raise ValueError("All execution output must stay in an assessment subdirectory.")
    if origin not in {"historical_replay", "new_labelled_batch"}:
        raise ValueError("Declare historical_replay or new_labelled_batch provenance.")
    final_test = (PROJECT / "data/processed/test.csv").resolve()
    for input_path in (training_data, Path(new_data).resolve(), Path(gate_data).resolve()):
        if input_path == final_test or (input_path.exists() and final_test.exists() and input_path.samefile(final_test)):
            raise ValidationError("The original final test set must not be used or read in this assessment.")
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    log = []

    def note(message):
        log.append(message)
        print(message, flush=True)
        (output / "execution.log").write_text("\n".join(log) + "\n", encoding="utf-8")

    protected = [path for path in artifacts_dir.iterdir() if path.is_file()]
    protected += [training_data, Path(gate_data).resolve(), Path(new_data).resolve()]
    # Hash original validation/report bytes for protection; never open the final test CSV.
    protected += [PROJECT / "data/processed/validation.csv", PROJECT / "reports/final_test_metrics.json"]
    protected = sorted(set(path for path in protected if path.is_file()))
    before = {str(path): checksum(path) for path in protected}
    write_json(output / "protected_sources_before.json", before)
    try:
        champion, original_preprocessor, schema, metadata = load_champion(artifacts_dir)
        features = schema["feature_names"]
        validations, frames = {}, {}
        for role, path in (("training", training_data), ("incoming", new_data), ("holdout", gate_data)):
            frame, validation = validate_csv(path, features, role)
            validations[role], frames[role] = validation, frame
            note(f"A {role}: {len(frame)} valid rows; targets={validation['target_distribution']}; "
                 f"duplicates removed={validation['duplicate_feature_rows_removed']}; "
                 f"missing feature cells={sum(validation['missing_feature_values'].values())}.")
        write_json(output / "data_validation.json", validations)
        train, incoming, holdout = (frames[name] for name in ("training", "incoming", "holdout"))
        if set(train["Label"]) != set(LABELS) or set(holdout["Label"]) != set(LABELS):
            raise ValidationError("Training and comparison holdout must each contain both classes.")
        overlap = ensure_disjoint(train, incoming, holdout, features)
        write_json(output / "split_integrity.json", overlap)
        note("A Split integrity passed: no shared feature records or overlapping record IDs.")
        existing_metrics, _ = evaluate(champion, original_preprocessor, incoming, features)
        write_json(output / "existing_model_evaluation.json", existing_metrics)
        note(f"B Existing model on incoming batch: accuracy={existing_metrics['accuracy']:.6f}, "
             f"precision={existing_metrics['precision']:.6f}, recall={existing_metrics['recall']:.6f}, "
             f"F1={existing_metrics['f1']:.6f}.")
        champion_holdout, _ = evaluate(champion, original_preprocessor, holdout, features)
        write_json(output / "champion_holdout_evaluation.json", champion_holdout)
        combined = pd.concat([train, incoming], ignore_index=True)
        candidate_preprocessor = clone(original_preprocessor)
        started = perf_counter()
        prepared = candidate_preprocessor.fit_transform(combined[features])
        candidate = XGBClassifier(**metadata["model_params"])
        candidate.fit(prepared, combined["Label"].map(LABELS).to_numpy(dtype=int))
        training_seconds = perf_counter() - started
        candidate_metrics, candidate_predictions = evaluate(candidate, candidate_preprocessor, holdout, features)
        write_json(output / "candidate_evaluation.json", candidate_metrics)
        candidate_dir = output / "candidate"
        candidate_dir.mkdir()
        candidate.save_model(candidate_dir / "model.ubj")
        joblib.dump(candidate_preprocessor, candidate_dir / "preprocessor.joblib", compress=3)
        selected = np.asarray(features)[candidate_preprocessor.named_steps["constant_filter"].get_support()].tolist()
        write_json(candidate_dir / "feature_schema.json", {**schema, "selected_feature_names": selected})
        write_json(candidate_dir / "label_mapping.json", LABELS)
        write_json(candidate_dir / "model_params.json", {
            "candidate_version": run_id, "parent_model_version": metadata["model_version"],
            "model_params": metadata["model_params"], "training_rows": len(combined),
            "preprocessing": "Cloned original recipe; fitted on original training plus incoming batch only.",
            "deployment_status": "candidate_only_not_deployed",
        })
        reloaded = XGBClassifier(n_jobs=2)
        reloaded.load_model(candidate_dir / "model.ubj")
        reloaded_preprocessor = joblib.load(candidate_dir / "preprocessor.joblib")
        reloaded_predictions = reloaded.predict(reloaded_preprocessor.transform(holdout[features]))
        if not np.array_equal(reloaded_predictions, candidate_predictions):
            raise RuntimeError("Candidate reload did not reproduce holdout predictions.")
        write_json(output / "candidate_reload_check.json", {
            "passed": True, "rows_checked": len(holdout),
            "model_sha256": checksum(candidate_dir / "model.ubj"),
            "preprocessor_sha256": checksum(candidate_dir / "preprocessor.joblib"),
        })
        note(f"C Candidate trained on {len(combined)} rows in {training_seconds:.3f}s; "
             f"holdout accuracy={candidate_metrics['accuracy']:.6f}, precision={candidate_metrics['precision']:.6f}, "
             f"recall={candidate_metrics['recall']:.6f}, F1={candidate_metrics['f1']:.6f}. Reload passed.")
        decision = quality_gate(champion_holdout, candidate_metrics, criteria)
        write_json(output / "quality_gate_decision.json", decision)
        note(f"D Quality gate: {decision['decision']}; failed checks={decision['failed_checks']}.")
        after = {str(path): checksum(path) for path in protected}
        unchanged = before == after
        write_json(output / "protected_sources_check.json", {
            "unchanged": unchanged, "before": before, "after": after,
        })
        if not unchanged:
            raise RuntimeError("A protected source changed during execution; stop and inspect the checksums.")
        scope = (
            "Historical replay from the original validation capture, previously used for model selection; "
            "not newly collected traffic or an independent generalization test."
            if origin == "historical_replay" else
            "User-declared new labelled batch. File and row-overlap checks do not verify collection provenance."
        )
        report = {
            "status": "completed", "run_id": run_id, "completed_at": datetime.now(UTC).isoformat(),
            "output_directory": str(output), "batch_origin": origin, "data_scope": scope,
            "champion_version": metadata["model_version"],
            "training_rows": len(train), "incoming_rows": len(incoming), "holdout_rows": len(holdout),
            "combined_training_rows": len(combined), "training_seconds": training_seconds,
            "existing_model_new_batch": existing_metrics, "champion_holdout": champion_holdout,
            "candidate_holdout": candidate_metrics, "quality_gate": decision,
            "source_validation": validations, "split_integrity": overlap,
            "candidate_reload_passed": True, "protected_sources_unchanged": True,
            "original_final_test_read": False,
            "versions": {name: (xgboost.__version__ if name == "xgboost" else version(name))
                         for name in ("numpy", "pandas", "scikit-learn", "joblib", "xgboost")},
            "python": platform.python_version(),
            "mlflow": {"status": "not_used", "reason": "Not installed; optional for this assessment. Local run records are saved."},
        }
        write_json(output / "execution_report.json", report)
        render_html(report, output / "report.html")
        note(f"E Completed. Champion and inputs unchanged. Evidence: {output}")
        return report
    except Exception as error:
        write_json(output / "failure_report.json", {
            "status": "failed", "error": str(error),
            "validation_details": getattr(error, "report", {}),
            "champion_replaced": False,
        })
        note(f"FAILED: {error}")
        raise
