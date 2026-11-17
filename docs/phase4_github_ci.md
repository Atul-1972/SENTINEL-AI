# Phase 4: GitHub and continuous integration

Repository: [Atul-1972/SENTINEL-AI](https://github.com/Atul-1972/SENTINEL-AI).

The workflow is [`.github/workflows/ci.yml`](../.github/workflows/ci.yml). It runs on pushes, pull requests and manual dispatch. It uses read-only repository permissions, job timeouts and cancellation of older runs on the same branch. No cloud deployment, registry publishing, full-dataset download or model training is performed.

## What runs

| Job | Checks |
| --- | --- |
| Backend tests and source checks | Tracked-file checks, Python syntax, dependency consistency, API contracts, input validation, risk rules, transactional persistence, history filters and CI preparation |
| Frontend tests and production build | Lockfile installation, 18 unit tests, production build and production dependency audit |
| Docker build and startup check | Build the normal Dockerfile from a separate artifact-free context; verify docs/routes, SQLite startup, empty history and correct 503 responses without models |

Docker starts only after the backend and frontend jobs pass. JUnit results, the frontend build, and container logs/checks are uploaded as seven-day workflow artifacts. An Actions artifact is a downloadable build/test output; it is different from the trained ML files in your local `artifacts/` folder.

The backend CI selection is `pytest -m "not artifacts"`: 28 fixture-based tests at implementation time. The complete local suite has 30 tests, including two optional checks against the real saved models. These tests cover endpoint predictions using small explicit mock models; they do not claim new model accuracy. CI does not run the real-model Playwright suite because the trained artifacts are intentionally absent from GitHub.

## Why CI uses a separate Docker context

The local Docker image needs the trusted exported models, which are excluded from Git. A clean GitHub checkout does not contain them. `scripts/prepare_ci_context.py` copies only the required source/dependency files and small public historical examples into a new directory. It adds a clearly labeled JSON marker instead of copying or generating models. Existing destinations are refused, and your original artifacts are never overwritten.

The Dockerfile is unchanged. The CI image has no deployable model bundle, so `/health`, `/model-info`, `/predict` and `/predict-batch` must return 503 while SQLite and documentation remain available. `scripts/ci_container_smoke.py` checks this behavior and confirms rejected predictions create no history. The temporary container uses a separate port and no demo database volume, and is removed after checking. This verifies packaging and startup, not trained-model inference. The already-verified local demo image continues using the real models.

## Verify the real GitHub run

1. Open [SENTINEL AI CI in Actions](https://github.com/Atul-1972/SENTINEL-AI/actions/workflows/ci.yml).
2. Select the newest run for the current commit on `main`.
3. Confirm all three jobs are green. Open a job to inspect its commands and results.
4. Download `backend-test-results`, `frontend-build`, or `docker-check-results` from the run's Artifacts section when needed.

A workflow file or passing local tests alone do not prove a successful remote run. Phase 4's completion criterion is a real successful run on GitHub. Any confirmed run URL and commit are recorded in `reports/phase4_github_verification.json` when verification finishes.

For later edits, use a topic branch from the project root:

```powershell
git switch -c improve-sentinel
git status --short
git add <files-you-changed>
.\.venv-model\Scripts\python.exe scripts/check_repository.py
git diff --cached --stat
git commit -m "Describe the change"
git push -u origin improve-sentinel
```

Replace `<files-you-changed>` with actual paths. Open a pull request to `main`; its push and pull-request checks will run. Do not force-push to replace remote history. Branch protection is not configured automatically.

To reproduce the fixture checks locally:

```powershell
.\.venv-model\Scripts\python.exe scripts/check_repository.py
.\.venv-model\Scripts\python.exe -m compileall -q backend scripts tests notebooks
.\.venv-model\Scripts\python.exe -m pytest -q -m "not artifacts"
Set-Location .\frontend
npm ci
npm test
npm run build
npm audit --omit=dev --audit-level=high
```

The workflow converts the exact XGBoost requirement to its CPU distribution on Linux, as the Dockerfile already does. It does not change the recorded model versions. Frontend build tools retain the previously documented unpatched development-only matcher advisory; the production audit is the automated audit gate. See [frontend guide](frontend.md).

For scripted read-only verification on this Windows machine, `scripts/github_ci_status.py` can use the existing Git Credential Manager sign-in. It keeps credentials in memory and does not print or save tokens. Obtain the full commit with `git rev-parse HEAD`, then pass it as `--sha` with `--wait`. If GitHub access is unavailable, use the Actions page; do not paste tokens into chat or source files.

## What belongs in Git

Source code, dependency manifests/lockfile, workflows, tests, notebooks, documentation, small historical examples and saved evaluation reports are included. Raw/processed data, trained models, the original ZIP, Python environments, node_modules, frontend builds, SQLite history, local settings and credential files are excluded. The repository checker flags common credential formats and large/private files; it is a useful guard, not a complete secret scanner.

A fresh clone can run fixture CI and build the frontend. For real local predictions, restore the trusted Phase 1 bundle separately before following the backend/Docker guide. Never commit the full dataset to fix missing model errors.

MLflow, Evidently, Airflow, DVC and automated retraining remain future work. Creating this CI workflow does not implement those integrations.

Official references: [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax), [Python build/test workflows](https://docs.github.com/en/actions/tutorials/build-and-test-code/python), and [workflow-run API](https://docs.github.com/en/rest/actions/workflow-runs).
