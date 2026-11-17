# Phase 2: FastAPI backend

The API loads the actual exported XGBoost model, preprocessing and separate Isolation Forest.
It records predictions and alerts in SQLite. It does not train a model or read the reserved test
data to make predictions. No dashboard, Docker or MLOps service is required in this phase.

## Start the API in Windows PowerShell

Run from the project folder using the verified Python 3.13 model environment:

```powershell
Set-Location -LiteralPath 'C:\Users\ATUL KUMAR AGRAHARI\OneDrive\Desktop\MSE-2 GENAI'
uv pip install --python .venv-model\Scripts\python.exe --no-cache -r requirements-dev.txt
.\.venv-model\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Expected startup message: `Application startup complete` followed by
`Uvicorn running on http://127.0.0.1:8000`. Stop a server started in your own terminal with Ctrl+C.
If the existing verification server is still running on port 8000, open it directly rather than
starting a second server on the same port.

- Swagger: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/health>
- Model details and exact feature names: <http://127.0.0.1:8000/model-info>

The API uses XGBoost's native `artifacts/model.ubj`, because its Python joblib snapshot did not
load on Windows. It uses joblib for the saved preprocessor and anomaly model. Models load once
at startup. No preprocessing object is fitted during inference.

## Try the endpoints

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET | `/` | API name, version and documentation links |
| GET | `/health` | Model/database readiness; HTTP 503 if unavailable |
| POST | `/predict` | Validate, predict and persist one flow |
| POST | `/predict-batch` | Predict and persist 1-1,000 flows in one transaction |
| GET | `/model-info` | Schema, supported labels, model versions, saved evaluation and risk rules |
| GET | `/alerts` | Latest alerts; `limit`, `offset`, optional `risk_level` |
| GET | `/stats` | Counts and hourly submission trends from actual prediction history |

In Swagger, expand `/predict`, click **Try it out**, and use the prefilled historical validation
flow. Click **Execute**. Expect HTTP 200 with a prediction ID, UTC creation time, classification,
probabilities, anomaly result, risk priority, model version and source.
The example comes from the actual export, not an invented attack event.

Alternatively use these commands in a **second PowerShell terminal**:

```powershell
$flowJson = Get-Content -LiteralPath '.\data\sample\api_request.json' -Raw
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/predict' -Method Post -ContentType 'application/json' -Body $flowJson

$batchJson = Get-Content -LiteralPath '.\data\sample\api_batch_request.json' -Raw
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/predict-batch' -Method Post -ContentType 'application/json' -Body $batchJson

Invoke-RestMethod -Uri 'http://127.0.0.1:8000/alerts?risk_level=HIGH&limit=20'
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/stats'
```

Every successful prediction call adds records. GET requests do not add predictions.

## Input contract

Single request: an object with `features` and optional `source`.
Batch request: an object with `flows`, each following the same single-flow contract.
Complete examples are in `data/sample/api_request.json` and `api_batch_request.json`.

- Supply all 78 canonical feature names shown by `/model-info`. JSON key order does not matter;
  the service restores training order before transformation to 66 selected features.
- Numbers must be finite and within float32 range. Strings such as `"123"`, booleans, NaN,
  Infinity, unknown feature names and unknown wrapper properties return HTTP 422.
- Use JSON `null` for an unavailable feature value. The training-fitted imputer supplies its
  stored value. Omitted keys and flows whose entire feature set is null are rejected.
- Keep the canonical duplicate name `Fwd Header Length__duplicate_2`. Do not silently drop it.
- Do not include a CSV's `Label` column inside `features`. It is a target, not a model input.
- `source` is `historical`, `simulated`, or `user_provided` (default). There is no automatic
  network capture or fabricated live traffic stream.
- A batch is rejected as a whole if any flow is invalid. No earlier valid flow in that batch
  is committed. Database write failures roll back predictions and alerts together.

This phase's batch endpoint consumes JSON. CSV parsing/upload UI will be added with the frontend.

## Meaning of the outputs

The classifier returns BENIGN or ATTACK. `predicted_attack_category` is null: this is a binary
model, even though its only represented attack label was DDoS. `/model-info` reports that training
coverage explicitly. It does not claim support for brute force, port scans or other attacks.

`confidence` is the selected class's raw model probability; `attack_probability` is the raw
probability for ATTACK. Both are explicitly labeled **uncalibrated**. They are not verified
probabilities of a real-world security incident.

`anomaly_score` is negative Isolation Forest `decision_function`. Higher means more unusual;
positive scores set `anomaly_flag=true`. This is a separate signal, not a probability or category.
Its fixed validation attack recall is weaker than XGBoost, so an unflagged anomaly result never
overrides a classifier prediction of ATTACK.

Risk scores are documented rule-based priorities:

| Classifier | Anomaly flag | Score | Level | Alert |
| --- | --- | ---: | --- | --- |
| BENIGN | false | 0 | LOW | No |
| BENIGN | true | 40 | MEDIUM | Yes, unusual flow |
| ATTACK | false | 80 | HIGH | Yes, classifier alert |
| ATTACK | true | 90 | HIGH | Yes, both signals |

These scores are not probabilities and do not depend on arbitrary confidence values.

## SQLite and statistics

Default database: `data/sentinel.db`, created at server startup and excluded from Git.
SQLAlchemy stores predictions, numeric feature values, alerts and model metadata. The schema
does not accept source IP addresses, user identities or arbitrary raw packet payloads.
Numeric features are retained to support later drift monitoring; model monitoring is not yet implemented.

There is one alert per MEDIUM/HIGH prediction. The LOW case creates no alert. Restarting the
server preserves prediction history without preloading demo events or duplicating model metadata.
The verification run submitted 11 actual historical flows; it did not invent events.

`benign_flows` and `attack_flows` count classifier labels. `anomaly_flows` counts the separate
flag. `suspicious_flows` counts the union of ATTACK and flagged anomalies. `high_risk_alerts`
counts classifier ATTACK results. UTC hourly trends summarize request submission times,
not original capture timestamps. Saved model accuracy is historical, not live measured accuracy.

Optional process environment variables (read when the app is created):

- `SENTINEL_ARTIFACTS_DIR`: alternative trusted local artifact folder.
- `SENTINEL_DATABASE_URL`: alternative SQLAlchemy SQLite URL.

## Validation performed

Run automated tests from the project root in PowerShell:

```powershell
.\.venv-model\Scripts\python.exe -m pytest -q
```

Executed result: **26 passed**. Coverage includes strict inputs, NaN/Infinity response handling,
missing/unknown features, batch limits, all risk paths, alerts/statistics consistency, transaction
rollback, SQLite restart persistence, missing artifacts, model quality/version gates and real saved
model prediction/preprocessing checks. There is one upstream Starlette/httpx deprecation warning;
it does not fail the tests. CI-friendly fixtures require no dataset download or training.
Real-artifact checks are marked `artifacts` and skip when the exported files are absent.

Run an actual HTTP check while the server is running:

```powershell
.\.venv-model\Scripts\python.exe scripts\api_smoke_test.py
```

Executed result: all seven required endpoints returned HTTP 200; 10 batch predictions matched
Colab, one single prediction matched, an invalid batch returned 422 with no writes, and alerts/statistics
matched actual submissions. See `reports/phase2_api_smoke.json`.
Each repeat of this smoke test adds 11 historical predictions to the database.

The implementation follows FastAPI's [lifespan](https://fastapi.tiangolo.com/advanced/events/)
and [testing](https://fastapi.tiangolo.com/tutorial/testing/) interfaces and uses
[SQLAlchemy's ORM](https://docs.sqlalchemy.org/en/20/orm/quickstart.html).

Phase 2 is complete. Phase 3 Docker was subsequently authorized and verified; see
[phase3_docker.md](phase3_docker.md). Its added CPU-package compatibility test brings the
current regression total to 27. GitHub CI is still a future phase; no CI success is claimed yet.
