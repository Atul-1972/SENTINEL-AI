# SENTINEL AI monitoring and retraining practical

This separate assessment implements Tasks A-E using your existing SENTINEL classifier and dataset. It measures model quality on labelled records, retrains a candidate, and records whether that candidate is eligible for promotion. Everything added for the assessment stays in this folder.

The demonstration completed on **20 November 2026**. The candidate **matched the champion on the comparison holdout** and passed the predefined gate. It was marked **eligible for promotion**, while the existing deployed model remained unchanged.

## Run the complete demonstration

Run this from the main project folder, where `assessment/` and `.venv-model/` are located:

```powershell
.\.venv-model\Scripts\python.exe -m assessment.run_assessment --demo
```

The existing `.venv-model` already has the required libraries. There are no new mandatory dependencies or servers to start. The assessment does not require the frontend or Docker to be running.

Open the latest human-readable report:

```powershell
$assessmentRun = Get-Content .\assessment\runs\latest.json -Raw | ConvertFrom-Json
Start-Process (Join-Path $assessmentRun.directory 'report.html')
```

Display the decision and the actual saved candidate files:

```powershell
Get-Content (Join-Path $assessmentRun.directory 'quality_gate_decision.json')
Get-ChildItem (Join-Path $assessmentRun.directory 'candidate')
```

Each execution creates a new timestamped run directory. Completed run outputs and candidate files are preserved separately. The first run prepares replay CSVs; later demo runs reuse them only if their checksums still match.

## Data used in the demonstration

The incoming batch is a **historical replay**, selected from the original validation split. It is not newly collected traffic. That validation split was previously used to select the original model, so these results do not establish independent generalization.

| Input | Records | BENIGN | ATTACK | Purpose |
| --- | ---: | ---: | ---: | --- |
| Original training data | 12,000 | 5,115 | 6,885 | Existing training reference |
| Incoming labelled replay | 1,000 | 426 | 574 | Evaluate the champion, then add to candidate training |
| Separate comparison holdout | 3,000 | 1,279 | 1,721 | Compare both models without fitting on these records |
| Combined candidate training | 13,000 | 5,541 | 7,459 | Train the candidate |

The replay files and provenance manifest are in `assessment/data/`. The script refuses to read the original `data/processed/test.csv`. The existing training and validation files are read-only inputs; none is rewritten.

## Task A Prepare and validate the labelled batch

`prepare_demo.py` selects the incoming and holdout records using a reproducible stratified split with seed 42. `workflow.py` validates each input and reports:

- Required feature columns, the Label column, and unexpected columns.
- Numeric values, missing feature cells, and infinities converted to missing values.
- Missing or unsupported target labels, which are rejected.
- Duplicate optional `record_id` values, which are rejected.
- Identical feature records, which are deduplicated if labels agree and rejected if labels conflict.
- Dataset size and target distribution.

The expected input is the saved 78-feature schema plus `Label`, with optional `record_id`. Labels may be BENIGN or ATTACK; DDoS is normalized to ATTACK. Other attack categories are rejected because this classifier's training scope is DDoS. Duplicate feature headers receive the same collision-safe naming convention used during original preparation.

Missing feature values are retained for training-fitted median imputation. Entirely missing records and invalid numeric values are rejected. Feature-record and ID overlap checks prevent the incoming batch or holdout from being reused across training and comparison partitions.

## Task B Evaluate the existing model

The script loads `artifacts/model.ubj` using native XGBoost model IO, plus the existing saved preprocessor, feature schema, label mapping and metadata. It measures Accuracy, attack Precision, attack Recall and attack F1 on the incoming batch **before retraining**.

The executed demonstration produced:

| Metric | Champion on incoming 1,000 records |
| --- | ---: |
| Accuracy | 99.90% |
| Attack precision | 100.00% |
| Attack recall | 99.83% |
| Attack F1 | 99.91% |

These results are saved in `existing_model_evaluation.json`. Confusion matrix: `[[426, 0], [1, 573]]`, with true BENIGN/ATTACK rows and predicted BENIGN/ATTACK columns.

## Task C Train a separate candidate

The candidate combines all 12,000 original training records with all 1,000 incoming records. It uses the original XGBoost hyperparameters and the same preprocessing recipe: median imputation followed by constant-feature removal.

The preprocessing recipe is cloned and fitted on combined training data only. The champion's fitted preprocessor is not refitted. The holdout is excluded from preprocessing and classifier fitting.

Saved candidate files include:

- `candidate/model.ubj`
- `candidate/preprocessor.joblib`
- `candidate/feature_schema.json`
- `candidate/label_mapping.json`
- `candidate/model_params.json`

The saved candidate was reloaded and reproduced all 3,000 holdout predictions. Native UBJSON is used because the original classifier joblib snapshot is not portable in this Windows environment.

MLflow is not installed in this project, so it is not used. The assessment records parameters, runtime versions, input checksums, metrics and the decision in local JSON files. Tracking is optional in the assessment.

## Task D Apply the quality gate

Both models are compared on exactly the same 3,000-record holdout:

| Metric | Champion | Candidate |
| --- | ---: | ---: |
| Accuracy | 99.93% | 99.93% |
| Attack precision | 100.00% | 100.00% |
| Attack recall | 99.88% | 99.88% |
| Attack F1 | 99.94% | 99.94% |
| False-positive rate | 0.00% | 0.00% |

Each model had zero false alarms and two missed attacks on this holdout. The candidate matched the champion; it did not demonstrate an improvement.

The gate is declared in `DEFAULT_GATE` before execution:

1. Attack recall must be at least 98%.
2. Attack F1 must be at least 98%.
3. False-positive rate must be at most 1%.
4. Candidate attack recall must not be worse than the champion.
5. Candidate attack F1 must not be worse than the champion.

Recall is the primary metric because missed attacks are costly. F1 and the false-positive limit help prevent poor precision and excessive alerts. Ties are eligible under this non-regression policy; eligibility does not automatically replace the champion.

The actual decision was `eligible_for_promotion`, with `champion_replaced: false`. A failed check produces `retain_champion` and records the failed criteria. SHA-256 checks confirmed all protected original model and input files were unchanged.

The candidate package contains the supervised classifier and its preprocessing. Any future deployment needs a separate compatibility review, including the deployed Isolation Forest's preprocessing requirements.

## Task E Execution evidence and demonstration

The fixed evidence for the completed run is in `assessment/evidence/`:

| Evidence | What to show |
| --- | --- |
| [demo_report.html](evidence/demo_report.html) | Readable report of Tasks A-E |
| [demo_execution.log](evidence/demo_execution.log) | Actual task-by-task terminal output |
| [demo_execution_report.json](evidence/demo_execution_report.json) | Metrics, provenance, validation and run metadata |
| [demo_quality_gate.json](evidence/demo_quality_gate.json) | The eligibility decision and every gate check |
| [test_results.xml](evidence/test_results.xml) | 45 passing tests across the original project and assessment |

The actual candidate for this recorded run is in `runs/20261120T045241Z-f45ffecc/candidate/`. Generated datasets and models remain local and are ignored by Git. The fixed evidence files are small reviewable records; `runs/latest.json` points to the most recent execution.

For the practical demonstration:

1. Run the one-command demo and show the printed sizes, distributions and metrics.
2. Open the HTML report and explain the incoming batch and separate holdout.
3. Display the candidate directory to prove that a new model was saved separately.
4. Open `quality_gate_decision.json` and explain why the gate passed.
5. Show `protected_sources_check.json` from the run: `unchanged` is true.

Run the assessment tests separately:

```powershell
.\.venv-model\Scripts\python.exe -m pytest assessment/tests -q
```

Run the original and assessment tests together:

```powershell
.\.venv-model\Scripts\python.exe -m pytest tests assessment/tests -q
```

Executed results: **15 assessment tests passed; 45 total tests passed**. Tests cover invalid schemas, missing labels and values, duplicate records and IDs, conflicting labels, split overlap, gate pass/reject cases, final-test protection, and a complete tiny-fixture retraining run proving preprocessing uses combined training only.

## Use a genuinely new labelled CSV later

Supply your new labelled batch and a separate compatible labelled holdout:

```powershell
.\.venv-model\Scripts\python.exe -m assessment.run_assessment `
  --new-data 'C:\path\incoming_labelled.csv' `
  --gate-data 'C:\path\separate_holdout.csv' `
  --batch-origin new_labelled_batch
```

Both files must follow the model schema. Training and comparison holdout must contain both classes. No input feature record may overlap another partition. Use trusted true labels, not the champion's own predictions as labels. The provenance declaration is recorded but does not prove how an external CSV was collected.

## Short explanation for the examiner

“My deployed model is the champion. I validate an incoming labelled batch and measure its accuracy, precision, recall and F1. I combine that batch with the old training data and train a separate candidate using the same preprocessing recipe. I compare both models on a holdout excluded from candidate training. My gate prioritizes attack recall and also checks F1 and false alarms. The candidate matched the champion and met the thresholds, so it was marked eligible for review. The existing deployment was kept unchanged.”

This is labelled model-quality monitoring and controlled retraining. Statistical feature-drift detection, Airflow orchestration, DVC and automatic deployment are outside this separate assessment.

References: [scikit-learn guidance on data leakage](https://scikit-learn.org/1.6/common_pitfalls.html#data-leakage), [cloning an unfitted preprocessing recipe](https://scikit-learn.org/1.6/modules/generated/sklearn.base.clone.html), and [XGBoost native model IO](https://xgboost.readthedocs.io/en/stable/tutorials/saving_model.html).
