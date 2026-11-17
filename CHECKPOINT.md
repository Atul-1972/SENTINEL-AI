# SENTINEL AI - saved project checkpoint

Updated: 18 November 2026 (Asia/Calcutta).

## Current state and user instructions

**Phases 1-3 and the requested frontend are complete. The user explicitly requested the frontend before the remaining GitHub/CI and MLOps work. Docker serves the API at localhost:8001 with persistent history.**

Latest authorized work: Phase 4 GitHub and CI. User supplied https://github.com/Atul-1972/SENTINEL-AI. The empty remote was inspected; local Git main initialized and origin connected. CI code and local checks are ready; do not claim Phase 4 complete until a remote run succeeds. See the Phase 4 section below and any verification report for the latest confirmed result.

- Medium-level B.Tech CSE third-year project. Keep the code understandable and the final demonstration local.
- Initial real-data training ran in Google Colab, as requested. Do not retrain or repeat final test prediction.
- Build one phase at a time and explain each step. The user explicitly authorized Phase 2 with "start phase 2" and Phase 3 with "phase 3".
- Those phases are complete: backend, SQLite, Docker, tests, documentation and real HTTP/persistence checks are done.
- The frontend request is implemented and verified. The user subsequently authorized GitHub/CI and supplied their repository. Do not automatically start external MLOps services.
- Binary classification is BENIGN versus ATTACK, with DDoS as the only attack type in the selected dataset.
- Isolation Forest is separate: its scores are neither probabilities nor attack categories.
- Never invent metrics, live events, CI runs, or completed MLOps integrations.

## Confirmed dataset and preparation

The user downloaded Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv and uploaded it directly to /content in Colab.
Full-label scan: 225,745 records, 97,718 BENIGN, 128,027 DDoS, no missing labels.
The first 10,000 preview records were BENIGN only. They had one missing Flow Bytes/s value,
six infinite Flow Bytes/s values, seven infinite Flow Packets/s values, and 73 duplicate rows.
Those are preview counts, not full-file cleaning totals.

Resolved issues: csv import was missing, repeated CSV feature headers needed unique names,
and direct Colab upload needed /content rather than a mandatory Drive mount.
All repeated feature columns were preserved with explicit suffixes.

Preparation converts fixed numeric inputs, replaces infinities with NaN, excludes identifiers/timestamps,
removes empty and duplicate input records, and removes identical feature vectors with conflicting labels.
It samples up to 20,000 rows with cleaned class proportions, then uses seed 42 for a stratified 60/20/20 split:

| Partition | BENIGN | ATTACK | Total |
| --- | ---: | ---: | ---: |
| Training | 5,115 | 6,885 | 12,000 |
| Validation | 1,705 | 2,295 | 4,000 |
| Test | 1,705 | 2,295 | 4,000 |

See reports/preparation_report.json for actual full cleaning counts.
The full 225,745-row raw CSV is not in this workspace, but all 20,000 prepared split records are here.
All learned preprocessing (median imputation and constant-feature removal) was fitted on training only.
The model schema has 78 input features; preprocessing retains 66.

## Confirmed model results

Random Forest validation: matrix [[1704, 1], [5, 2290]], accuracy 99.85%, one false alarm,
five missed attacks, compressed model 124,398 bytes. Saved-artifact reload passed in Colab.

XGBoost validation: matrix [[1705, 0], [3, 2292]], accuracy 99.925%, no false alarms,
three missed attacks, compressed joblib 27,850 bytes, native UBJSON 144,079 bytes.
Both reload formats passed in Colab. The comparison recommended xgboost.

Validation targets fixed before XGBoost: attack recall >= 0.98, attack F1 >= 0.98, FPR <= 0.01.
Both candidates pass. Passing candidates are ranked by recall descending, FPR ascending, F1 descending,
model size ascending, batch latency ascending. Final test results did not select or tune the classifier.

Isolation Forest: 100 estimators, max_samples 256, contamination 0.05, seed 42; trained on the
5,115 BENIGN training flows after shared preprocessing. Score is -decision_function; >0 is an anomaly.
The 5% setting defines a training-reference cutoff, not a validation false-positive guarantee.
Validation matrix [[1611,94],[1928,367]] has true BENIGN/ATTACK rows and NORMAL_FLAG/ANOMALY_FLAG columns.
There were 461 anomaly flags; attack recall 15.9913%, benign FPR 5.5132%, F1 26.6328%, ROC-AUC 0.7428199771273774.
This is a supplementary signal with weaker attack detection, not a replacement for XGBoost.
Anomaly model size is 229,254 bytes; Colab reload checks passed.

Final selected XGBoost test: matrix [[1705,0],[6,2289]], 4,000 records, no false alarms, six missed attacks.
Accuracy 0.9985 (99.85%), attack precision 1.0, recall 0.9973856209150327,
F1 0.9986910994764397, ROC-AUC 0.999589953935305. Fixed quality gate passed.
The selection lock and final test report are preserved. Do not reevaluate the test set or change models using these scores.
All results are from random holdouts within one capture, not independent days, networks, or other attack types.

## Downloaded files and actual local verification

The user moved sentinel_phase1_bundle.zip into this workspace. Its CRC passed, archive paths were
checked before extraction, and the original ZIP was kept. Extracted artifacts/, reports/, data/,
requirements-model.txt and README.txt are present. The notebook remains a separate local project file;
the user should save their Colab notebook too because runtime files are temporary.

All seven required artifacts plus model.ubj are present. scripts/verify_phase1.py verified:

- Model, preprocessing, schema and anomaly bytes match the frozen selection checksums.
- Test CSV checksum matches the evaluated file; no test CSV parsing/predictions were repeated.
- All 10 historical validation class predictions and probability outputs match Colab.
- All 10 anomaly scores and flags match Colab.
- The fixed final quality gate is passed; model version is sentinel-xgboost-1.0.0.
- Result saved at reports/local_verification.json.

## Runtime and compatibility finding

The original .venv/ uses Python 3.11 and synthetic-check dependencies. XGBoost 3.4.1 requires Python >=3.12.
A project-local Python 3.13.15 was installed with uv under .python/, without PATH or registry changes.
The isolated .venv-model/ has exact exported packages: numpy 2.4.6, pandas 2.2.3,
scikit-learn 1.6.1, joblib 1.6.0, xgboost 3.4.1. Colab used Python 3.13.18; do not claim identical patches.
Runtime directories and generated model/archive files are excluded from Git.

Important for Phase 2: classifier model.joblib raises XGBoostError: input stream corrupted locally even
with matching package versions. Native model.ubj loads and reproduces every saved demo output.
Use XGBClassifier.load_model on artifacts/model.ubj for XGBoost, plus joblib for preprocessor and anomaly model.
The original joblib snapshot and archive are preserved unchanged. The native representation is the
portable XGBoost model format; do not overwrite frozen files or retrain to address snapshot portability.

## Source files saved

- notebooks/01_model_training.ipynb: Steps 1-11, with code matching the standalone scripts.
- notebooks/phase1_prepare_colab.py: Step 7 cleaning, sampling and splitting.
- notebooks/phase1_random_forest_colab.py: Step 8 training-only preprocessing and RF baseline.
- notebooks/phase1_xgboost_colab.py: Step 9 XGBoost and measured validation comparison.
- notebooks/phase1_isolation_forest_colab.py: Step 10 separate anomaly model and diagnostics.
- notebooks/phase1_finalize_colab.py: Step 11 selection freeze, cached final evaluation and ZIP export.
- scripts/verify_phase1.py: actual local artifact and historical-inference verification.
- README.md: architecture, scope, dataset/source attribution, setup and exact PowerShell/Colab commands.
- artifacts/, reports/, data/: preserved real export. No raw full dataset or large artifacts should enter Git.

Synthetic checks also passed for preparation, training-only imputation/feature removal, model reloading,
comparison gates, anomaly score semantics, and final export pass/fail cases, cached rerun and changed-artifact rejection.
Real Phase 1 completion is supported by the Colab results plus the downloaded bundle and successful local verification.

## Next action

The frontend is ready to try: start the Docker API, then run `npm run dev` inside frontend and open http://127.0.0.1:5173. See docs/frontend.md. The frontend QA servers were temporary and should be restarted in the user's terminal for normal use.
The user has now authorized GitHub/CI. Finish that phase and verify its actual remote run. The dashboard was explicitly requested out of the original phase order and is complete. External MLOps services still require a later phase request.
Continue using .venv-model/ and native model.ubj for XGBoost. No retraining or final test prediction
is needed for backend/Docker checks.

Optional local recheck from Windows PowerShell in the project root:

```powershell
.\.venv-model\Scripts\python.exe scripts\verify_phase1.py
```

## Phase 2 implementation and verification

Sources:

- backend/main.py: create_app factory, lifespan model/database loading, CORS for local Vite,
  health and all seven required endpoints, serializable input errors and model/database failures.
- backend/model_loader.py: exact model package checks, final gate, native XGBoost loading,
  saved preprocessing/anomaly loading, 78-name schema validation, inference and risk rules.
- backend/schemas.py: strict numeric/null inputs, finite float32 values, no extra fields,
  all-null rejection, 1-1,000 flows per batch, typed public prediction/alert responses.
- backend/database.py: SQLAlchemy SQLite predictions, alerts and model metadata, request-level
  transactions, UTC history, filtering/pagination and actual-history aggregates.
- backend/requirements.txt, requirements.txt, requirements-dev.txt: pinned tested dependencies.
- tests/: fake model/isolated database fixtures plus optional actual-artifact checks.
- scripts/api_smoke_test.py: HTTP checks against a running server using historical validation flows.
- data/sample/api_request.json and api_batch_request.json: actual historical input examples.
- docs/phase2_backend.md: student instructions, API contract, risk rules and validation evidence.

Model response is BENIGN/ATTACK only; predicted_attack_category is null. Raw probabilities
are explicitly labeled uncalibrated. Separate anomaly_score=-decision_function and flag>0
do not identify attack categories. Risk priorities: BENIGN/no anomaly=LOW 0;
BENIGN/anomaly=MEDIUM 40; ATTACK/no anomaly=HIGH 80; ATTACK/anomaly=HIGH 90.
Every MEDIUM/HIGH result creates one alert. An unflagged anomaly result cannot downgrade ATTACK.
Scores are rule-based priorities, not probabilities.

POST /predict and /predict-batch validate all input before inference/persistence. Missing or
unknown feature keys, boolean/string/nonfinite values, all-null flows, invalid sources or
oversized batches return 422. Null values use the training-fitted imputer. JSON key order is restored
to schema order. Invalid batches write nothing; database failures roll back the whole request.
GET /model-info reports saved test/validation metrics, schema, model version and limitations.
GET /stats reports actual history (all versions), source labels and UTC submission-hour buckets,
not fabricated traffic capture times or live model accuracy. No live traffic capture is implemented.

Default database is data/sentinel.db (ignored by Git), with real numeric flow features for later drift
monitoring, prediction results, alerts and model metadata. There is no personal identity/raw packet data.
Monitoring/retraining tables will be added with their actual workflows in Phase 5.
Optional env vars: SENTINEL_ARTIFACTS_DIR and SENTINEL_DATABASE_URL. Models load once at startup.
Missing/bad artifacts keep docs available while /health, /predict and /model-info return unavailable.

Executed automated result: 26 tests passed, including invalid inputs and nonfinite JSON errors,
all risk/alert/count paths, batch atomic rejection, SQLAlchemy transaction rollback, SQLite restart
persistence, missing models, version/quality gates, actual saved predictions and null preprocessing.
One upstream Starlette/httpx TestClient deprecation warning is recorded; it does not fail tests.
The fake model exists only in tests; production loads the real verified artifacts. CI-friendly
tests require no dataset downloads/training; actual-artifact tests skip if the export is absent.

Executed real HTTP smoke: all seven endpoints plus docs/OpenAPI returned 200; all 10 batch
predictions/probabilities/anomaly outputs matched the Colab demo, one single prediction matched,
an invalid second batch record returned 422 with zero additional writes, and expected alerts existed.
Report: reports/phase2_api_smoke.json. This submitted 11 historical flows in total.
At validation time: 6 BENIGN, 5 ATTACK, 1 anomaly flag, 5 high-risk alerts, no medium alerts.
Repeat smoke runs add 11 actual historical predictions each; GET routes do not increment history.

Runtime: FastAPI 0.163.1, Pydantic 2.14.3, Uvicorn 0.54.0, SQLAlchemy 2.0.58,
pytest 9.2.0, httpx 0.28.1, plus unchanged exact model packages.

The verification server is running at 127.0.0.1:8000 (started process PID 26040, exec session 18048).
Open /docs directly. If it is no longer running, start from the project root with:

```powershell
.\.venv-model\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Tests: `.\.venv-model\Scripts\python.exe -m pytest -q`.
HTTP smoke: `.\.venv-model\Scripts\python.exe scripts\api_smoke_test.py` while the server runs.
Do not start a second server on the same port or kill unrelated processes.
At Phase 2 completion Docker/CI/frontend/MLOps were still future work. Docker is now verified
as recorded below; the frontend was subsequently completed. CI and full MLOps integrations remain pending.

## Phase 3 Docker implementation and verification

The user explicitly authorized Phase 3. Docker CLI 29.8.2 and Compose v5.6.0 were installed,
but Docker Desktop's Linux engine was stopped. The installed Desktop was started in the background;
the Linux engine then reported version 29.8.2. No Docker installation or WSL reconfiguration was needed.

Files:

- Dockerfile: Python 3.13.18-slim-bookworm, libgomp1, exact CPU model packages/API pins,
  saved models, historical Swagger example, non-root sentinel UID 10001, /health check.
- docker-compose.yml: project sentinel-ai, one api service, image sentinel-ai-api:phase3,
  localhost:8001 mapped to container port 8000, volume api-data at /app/data, restart unless-stopped.
- .dockerignore: allowlist keeps only backend, manifests, root model artifacts and small examples;
  local runtimes, notebooks, raw/processed data, ZIPs and SQLite files stay out of the image.
- backend/requirements-api.txt: API pins shared between the local and Docker installations.
  backend/requirements.txt now references this plus the unchanged requirements-model.txt.
- backend/model_loader.py: checks the imported xgboost module version, supporting both full
  xgboost and Linux xgboost-cpu distributions with the same recorded version.
- scripts/api_smoke_test.py: accepts --report to keep Phase 3 evidence separate from Phase 2.
- docs/phase3_docker.md: complete commands, beginner explanations and validation results.
- reports/phase3_api_smoke.json and phase3_container_verification.json: actual execution evidence.

Docker installs xgboost-cpu==3.4.1 instead of the larger GPU distribution, without changing any
other trained package version or the original exported requirements-model.txt. Dockerfile creates
a temporary CPU-specific requirements list during build. All model artifacts remain unchanged.

Actual checks passed:

- Updated regression suite: 27 passed (the existing upstream Starlette/httpx warning remains).
- Compose configuration accepted and the image build completed; pip check found no broken requirements.
- Build context about 540 kB; image reported 742,510,873 bytes (about 708 MiB uncompressed).
- Container became healthy with Python 3.13.18, xgboost-cpu 3.4.1, UID 10001.
- All seven endpoints plus Swagger/OpenAPI returned 200 over HTTP at localhost:8001.
- Ten batch historical outputs matched Colab; one single prediction matched; invalid batch 422 wrote no records.
- Named-volume DB held 11 prediction records and five alerts after the smoke test.
- Both docker compose restart and --force-recreate retained the exact complete stats/alerts,
  while recreation produced a different container ID. No final test prediction or retraining occurred.

Current deployment: image sentinel-ai-api:phase3, container sentinel-ai-api-1, healthy.
Container ID at the original persistence check: 45d5d59e7f950b19ba84f0834e25ea6934b9de8ffef9234ff3a20533ca67d43a.
Image Id at that check: sha256:f97ba3894f8fddca21d290166309d15dfcad8e843563457d5267801be9db524d. The frontend integration subsequently rebuilt/recreated the service; see below.
Volume: sentinel-ai_api-data -> /app/data; DB URL sqlite:////app/data/sentinel.db.
The Windows API port 8000 and its local data/sentinel.db are separate from Docker's port 8001/database.
Port can be overridden with SENTINEL_API_PORT; default is 8001.

Useful commands from project root in Windows PowerShell:

```powershell
docker compose up -d --wait --wait-timeout 120 api
docker compose ps
docker compose logs --tail 50 api
docker compose restart --timeout 20 api
```

Docker HTTP check (adds 11 historical predictions per run):

```powershell
.\.venv-model\Scripts\python.exe scripts\api_smoke_test.py --base-url http://127.0.0.1:8001 --report reports/phase3_api_smoke.json
```

Wait for user confirmation before Phase 4. No GitHub repository, published image or successful
GitHub Actions run exists yet. Artifacts are intentionally ignored by Git: Phase 4's Docker build
in CI must prepare small clearly labeled fixtures or another explicit no-real-artifact build context,
not assume real exported models are committed and not download/train the full CIC dataset.

## Frontend implementation and verification

The user's latest request explicitly authorized building the frontend. Implemented locally using the Sites skill's repository/local-preview workflow; nothing was published or registered externally. No subagents were used.

Sources: frontend/ contains React, Vite, Tailwind, Recharts, Lucide and PapaParse, a lockfile, environment example, Node unit tests, and Playwright browser tests. Five responsive pages: Overview, Detection, Threats, Performance, Monitoring. Actual historical examples are provided; no fake live events, identities or integration statuses are seeded.

Detection validates the 78 input columns, preserves duplicate headers with collision-safe names, handles null/nonfinite values, rejects malformed/oversized input, and excludes reference/extra columns from inference. Limits are 25 MB/20,000 rows; API requests use at most 1,000 flows. Stop finishes the current batch; resume sends remaining rows. Completed batches persist across a later failure. No idempotency key exists: review history before retrying an uncertain network request.

Threats includes real alert/history filters, flow feature details, exports and accessible dialogs. Performance displays preserved validation/test metrics and comparisons without predicting the test set again. API polling is optional; failures show stale/unavailable state. MLOps integrations are clearly unconfigured. Risk and uncalibrated probability semantics remain unchanged.

Backend additions: GET /predictions with pagination/class/risk/anomaly filters; GET /predictions/{id} with saved features and 404 for missing IDs; saved model_comparison.json exposed in /model-info. Dockerfile/.dockerignore include that report. Updated Docker build and Compose startup passed; the existing named volume remained intact. New image Id: sha256:846aafcb33355c563b662416acc0b5e8e2ab0fe4733b98b56a0e129fc6063595.

Verification: 18 frontend unit tests, 5 browser tests, 28 backend tests; production build passed. Production preview checked all five pages at 1440px and 390px without JavaScript errors or page overflow. Browser checks cover real ten-flow analysis, saved details/export, mobile, offline state, and stop/resume using a test-only 1001-row intercepted fixture. That fixture does not write fake history. Actual browser submissions brought Docker history to 51 historical flows at verification time; repeated analysis adds records.

Evidence: reports/frontend-verification.json, frontend-production-preview.json, frontend-overview.png, frontend-detection.png, frontend-mobile.png, frontend-performance.png, frontend-monitoring.png. docs/frontend.md contains start commands, limitations and test instructions. Frontend QA used localhost:5173 and :4173; stop owned QA servers at teardown without stopping the intended Docker API.

Runtime: Node 22.12.0; React/ReactDOM 19.3.1; Vite 8.3.8; plugin-react 6.3.0; Tailwind and its Vite plugin 4.3.5; Recharts 3.11.0; PapaParse 5.7.1; Lucide 0.468.0; Playwright 1.65.1. Use npm ci to reproduce the lockfile. The production dependency audit has zero vulnerabilities. Full audit has five high findings from the unpatched picomatch <=4.0.7 development/build dependency chain (GHSA-fc5q-39xc-vjpf); no patched release was available. This is documented rather than claimed fixed; Vite binds to loopback. No user CSV content is used as a glob expression.

Pending: MLflow, Evidently, Airflow, DVC, GitHub Actions and automated retraining. Do not claim these exist because a Monitoring page exists. No retraining, test reevaluation, cloud hosting or GitHub publication was performed.

## Phase 4 GitHub and CI preparation

User requested GitHub and CI and supplied Atul-1972/SENTINEL-AI. git ls-remote confirmed the repository had no branches. Git Credential Manager has the matching Atul-1972 account. The GitHub plugin was discovered but is not connected; existing Git/GCM is the working route. No tokens are printed or saved. An exact-path safe.directory entry was needed for the user account because the sandbox created .git under its own Windows identity; no wildcard trust entry was added.

New sources: .github/workflows/ci.yml, .gitattributes, requirements-test.txt, scripts/check_repository.py, scripts/prepare_ci_context.py, scripts/ci_container_smoke.py, scripts/github_ci_status.py, tests/test_ci.py and docs/phase4_github_ci.md. Ignore rules additionally exclude credential/local settings and CI output/context directories. requirements-dev.txt references shared test-runner pins. Monitoring text says workflow configured without claiming live CI integration.

Workflow triggers: push, pull_request, workflow_dispatch; contents:read only; checkout credentials not persisted; three jobs with timeouts. Backend uses exact CPU model dependencies, tracked-file and Python syntax checks, and pytest -m "not artifacts". Frontend uses Node 22.12.0, npm ci/test/build and production audit. Docker runs after both pass, builds the regular Dockerfile from a new isolated context with a JSON marker in place of models, and checks expected missing-model 503 responses, docs, SQLite and no rejected-request writes. It never trains or claims model readiness. Logs/results and frontend build upload as seven-day artifacts. No image publishing or deployment is configured.

Local verification: complete backend suite 30 passed (same upstream Starlette/httpx warning); fixture-only selection is 28 tests with two real-model checks excluded. Frontend 18 passed and production build passed. Artifact-free image sentinel-ai-api:ci-check built; context about 88 kB, no real model/data copied. Separate sentinel-ci-local-check container at 18001 passed scripts/ci_container_smoke.py and was removed. Main demo API/image/database remained untouched. Report: reports/phase4_local_container_check.json.

Remaining at preparation: stage/review source files, repository guard, first commit, push to origin/main and verify actual Actions success. Record the commit/run URL/jobs in reports/phase4_github_verification.json. Do not claim local checks equal a remote green run. No MLflow/DVC/Airflow/Evidently/retraining is authorized in this phase.
