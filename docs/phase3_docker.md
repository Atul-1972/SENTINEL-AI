# Phase 3: Docker deployment

The FastAPI prediction service now runs in one Linux container. Saved models are included in
the image; SQLite history lives in a Docker named volume. No training job, frontend, MLflow
or Airflow service runs in this phase.

## Current working deployment

- Docker Swagger: <http://127.0.0.1:8001/docs>
- Health: <http://127.0.0.1:8001/health>
- Image: `sentinel-ai-api:phase3`.
- Compose service: `api`; current container name: `sentinel-ai-api-1`.
- SQLite volume: `sentinel-ai_api-data`, mounted at `/app/data`.
- The original Windows API on port 8000 uses its separate local `data/sentinel.db`.

The image built successfully and the container health check passed. An HTTP smoke test matched
all 10 historical batch outputs with Colab, verified one single prediction, and rejected an invalid
batch without writes. Eleven actual historical predictions and five alerts survived both a
container restart and a replacement with a new container ID.

Evidence: [phase3_api_smoke.json](../reports/phase3_api_smoke.json) and
[phase3_container_verification.json](../reports/phase3_container_verification.json).

## Student explanation

- A **Docker image** packages Python, application dependencies, code and saved models.
- A **container** is a running instance of that image.
- **Docker Compose** records how to build/run it, map the port and attach persistent storage.
- A **named volume** keeps the database when the container is restarted or replaced.
- The **health check** calls `/health`, which checks both loaded models and database access.

The container uses Python 3.13.18, matching the training runtime's recorded Python version,
and the original exact model package versions. It installs the CPU-only XGBoost 3.4.1 distribution
instead of GPU-enabled XGBoost. Both provide the `xgboost` module; the loader checks that module's
version so the CPU distribution passes the same compatibility gate.
See the [official CPU-only installation guide](https://xgboost.readthedocs.io/en/stable/install.html#minimal-installation-cpu-only).

XGBoost loads `model.ubj`. The preprocessor and Isolation Forest load their saved joblib objects.
There is no retraining, new threshold selection or repeat evaluation of the final test set.

## Build and run — Windows PowerShell

Start Docker Desktop and wait for its Linux engine. It is already running for this verified demo.
From the project root:

```powershell
Set-Location -LiteralPath 'C:\Users\ATUL KUMAR AGRAHARI\OneDrive\Desktop\MSE-2 GENAI'
docker version
docker compose version
docker info --format '{{.OSType}}'
```

Expected engine type: `linux`. If the named-pipe connection fails, Docker Desktop's Linux engine
is not ready; check Desktop status before building. Do not switch to Windows containers.

Build the image and start the API:

```powershell
docker compose build api
docker compose up -d --wait --wait-timeout 120 api
docker compose ps
Invoke-RestMethod -Uri 'http://127.0.0.1:8001/health'
```

`build` installs dependencies and packages code/models. `up -d` starts the service in the background.
`--wait` waits for the image's health check. Expect the service to be healthy and `/health` to return
`status: ok`, `database_ready: true`, `model_ready: true` and the actual model version.
The first build needs internet for the base image, libgomp and Python packages. Later builds reuse
cached dependency layers when their input files have not changed.

The API listens on port 8000 inside the container. Compose maps it to **localhost:8001** so it can
coexist with the Windows development server. To use a different host port:

```powershell
$env:SENTINEL_API_PORT = '8002'
docker compose up -d --wait --wait-timeout 120 api
```

Use that selected port in browser URLs and smoke-test commands. The default applies when
`SENTINEL_API_PORT` is unset.

## Test predictions

Open Swagger on port 8001, expand POST `/predict`, choose **Try it out**, then **Execute**.
The prefilled example is historical data from the verified export. The same strict Phase 2 input
contract and rule-based risk priorities apply.

From PowerShell, submit the complete historical batch example:

```powershell
$batchJson = Get-Content -LiteralPath '.\data\sample\api_batch_request.json' -Raw
Invoke-RestMethod -Uri 'http://127.0.0.1:8001/predict-batch' -Method Post -ContentType 'application/json' -Body $batchJson
Invoke-RestMethod -Uri 'http://127.0.0.1:8001/stats'
```

Run the automated HTTP smoke test against Docker, keeping its evidence separate from Phase 2:

```powershell
.\.venv-model\Scripts\python.exe scripts\api_smoke_test.py --base-url http://127.0.0.1:8001 --report reports/phase3_api_smoke.json
```

Each smoke run adds 11 actual historical prediction records. GET requests add no predictions.
No synthetic security events are preloaded. The container's database starts separately from the
Windows API database and is not copied into the image.

## Logs, stop and restart

```powershell
docker compose logs --tail 50 api
docker compose logs -f api
```

Ctrl+C exits the log viewer without stopping the service.

```powershell
docker compose restart --timeout 20 api
docker compose up -d --wait --wait-timeout 120 api
docker compose ps
```

To stop and start the existing container:

```powershell
docker compose stop api
docker compose start api
```

To replace the container while retaining its named-volume database:

```powershell
docker compose up -d --force-recreate --wait --wait-timeout 120 api
```

This replacement was actually tested: all 11 prediction records and all five alerts remained.
The named volume persists independently of the container. `docker compose down` stops/removes
the service and its network while retaining this volume. See the [Compose volume documentation](https://docs.docker.com/reference/compose-file/volumes/).

## What is packaged

The Dockerfile copies only the backend, exact dependency manifests, exported artifacts, one
historical Swagger reference report and small JSON examples. `.dockerignore` uses an allowlist,
excluding raw/processed training data, notebooks, local Python runtimes, ZIPs, SQLite files and
test-only dependencies. Docker reported about 540 kB of build context.

The resulting image's reported size is 742,510,873 bytes (approximately 708 MiB, uncompressed).
It runs as user `sentinel`, UID 10001. `/app/data` is writable for SQLite; the models are packaged
in `/app/artifacts`. `libgomp1` supplies OpenMP for the CPU libraries. No GPU runtime is needed.

`requirements-model.txt` remains the original Colab export. The Docker build generates a temporary
CPU variant of that list without changing version pins. `backend/requirements-api.txt` holds the
shared API package pins, used by both Windows installation and the Docker build.

## Checks actually completed

- Compose configuration accepted; image build completed with no broken Python requirements.
- Container reached healthy state and exposed all seven required endpoints.
- Native XGBoost model and saved preprocessing/anomaly outputs matched Colab's 10 demo flows.
- Invalid batch returned HTTP 422 and wrote no records.
- Restart and new-container replacement both retained the full prediction and alert history.
- CPU XGBoost 3.4.1, Python 3.13.18 and non-root UID 10001 verified inside the container.
- Updated regression suite: **27 tests passed**, with the previously documented upstream
  Starlette/httpx deprecation warning.

Phase 3 is complete. Phase 4 GitHub and CI begins after the user's confirmation.
No GitHub repository, workflow run or published image is claimed in this phase.
