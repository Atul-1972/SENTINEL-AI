# Local frontend guide

The React dashboard connects to the real FastAPI service and SQLite history. It runs locally and does not capture live network traffic. The frontend was built at the user's request after Phase 3, before the pending GitHub/CI and MLOps phases.

## Start the application

Use Node.js 22.12 or newer. Dependencies are already installed in this workspace. For a fresh checkout, run `npm ci` inside `frontend` first.

From the project root in Windows PowerShell, start the Docker API:

```powershell
docker compose up -d --wait --wait-timeout 120 api
```

In a second terminal, from the project root:

```powershell
Set-Location .\frontend
npm run dev
```

Open <http://127.0.0.1:5173>. Keep the terminal open; Ctrl+C stops the frontend. API documentation is at <http://127.0.0.1:8001/docs>.

After changing backend files, rebuild with `docker compose build api` before starting Compose again. The frontend's history endpoints require the updated backend included in this workspace.

To check the production build locally, from `frontend`:

```powershell
npm run build
npm run preview
```

Open <http://127.0.0.1:4173>. Both Vite commands bind to loopback and proxy `/api` to port 8001. The static build alone needs an equivalent API proxy when served elsewhere; publishing or remote deployment is not configured.

To change the API target, copy `frontend/.env.example` to `frontend/.env`, edit `SENTINEL_API_TARGET`, and restart Vite. Using port 8000 requires a Windows API process started with the current backend code; an older running process may lack the new history routes.

## Pages

| Page | Available behavior |
| --- | --- |
| Overview | Actual prediction counts, risk summary, submission activity, recent alerts and model status |
| Detection | CSV upload, historical example, feature validation, batch analysis, progress, stop/resume, filtering and CSV export |
| Threats | Alert/history views, risk distribution and saved flow details with all input features |
| Performance | Saved validation/test metrics, confusion matrices and Random Forest/XGBoost comparison |
| Monitoring | Actual API/database status; explicit pending status for external MLOps integrations |

The sidebar works on mobile. The header provides connection settings, optional 15-second refresh, Swagger access and JSON snapshot export. Connection failures show unavailable or stale data rather than fabricated values.

## Try a CSV

1. Open Detection and choose **Load example** to use ten actual historical validation flows, or select your own compatible CSV.
2. Select the correct source: historical, simulated, or user provided. Loading a file does not submit predictions.
3. Start analysis. Completed requests persist predictions and alerts in SQLite; inspect them on Threats.

The example is also available at `frontend/public/demo-flows.csv`. CSV input must include all 78 model feature columns. Whitespace is trimmed and duplicate headers receive collision-safe suffixes matching preparation. Label/reference and extra columns are excluded from model inputs. Missing and nonfinite numeric values become null for the saved training-fitted imputer. Invalid numeric values, malformed rows and entirely missing feature rows are rejected.

Limits: 25 MB per file, 20,000 data rows per upload, and 1,000 flows per API request. Oversized input is rejected rather than silently truncated. Stop finishes the current request; Resume submits only the remaining rows during the same loaded session. Completed batches remain saved if a later batch fails. A network failure can leave an uncertain submission outcome: inspect history before retrying because the API has no idempotency key. Repeating a completed analysis intentionally adds history.

Confidence is an uncalibrated model probability. Isolation Forest is a separate anomaly signal; it does not identify an attack category. Risk scores follow the backend's fixed priority rules. Performance comes from the preserved single-capture experiment and does not establish performance on other networks or attack types. Submission charts show API submission times, not original packet capture times.

## Implementation and verification

Frontend: React, Vite, Tailwind CSS, Recharts, Lucide and PapaParse. Page modules load on demand. Source is under `frontend/src`; package-lock records the installed dependencies. No cloud account, API key or external publication is needed.

Backend additions are read-only `GET /predictions` (filters and pagination), `GET /predictions/{id}` (saved features), and the saved comparison report in `/model-info`. The Docker image includes that report and has been rebuilt without replacing the persistent volume.

Checks completed:

- 18 frontend unit tests: CSV validation, header collisions, null handling, row limits, safe exports and display calculations.
- 5 browser tests: all pages, real ten-flow analysis and export/detail view, mobile navigation, offline behavior, and stop/resume across requests. The stop/resume fixture is test-only and does not write fake flows to the API.
- 28 backend tests, including history filtering and details.
- Production build and all five production-preview pages at 1440px and 390px widths; no page overflow or JavaScript errors.

Run unit tests and build from `frontend` with `npm test` and `npm run build`. For browser tests, start the Docker API and `npm run dev`, then run `npm run test:e2e`. The Playwright configuration uses installed Chrome/Edge where available. Browser tests submit ten real historical flows per run, so history counts increase. Backend checks from the project root use `.\.venv-model\Scripts\python.exe -m pytest -q`.

Evidence: [verification report](../reports/frontend-verification.json), [production preview checks](../reports/frontend-production-preview.json), [overview screenshot](../reports/frontend-overview.png), [detection screenshot](../reports/frontend-detection.png), [mobile screenshot](../reports/frontend-mobile.png), [performance screenshot](../reports/frontend-performance.png), and [monitoring screenshot](../reports/frontend-monitoring.png).

The final verification database contained 51 real historical submissions. Those include repeated browser checks; they are not live incidents. No retraining or final test reevaluation was performed.

## Dependency limitation and pending work

The production dependency audit reports zero vulnerabilities. The full audit reports five high findings in the development/build dependency chain, rooted in an unpatched picomatch advisory. The advisory currently lists no patched release: [GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf). The dev server binds to loopback, and uploaded CSV data is not passed to glob matchers. The limitation remains recorded for a later dependency update; it has not been described as fixed.

GitHub Actions is now configured separately; see the [Phase 4 guide](phase4_github_ci.md) and [actual workflow runs](https://github.com/Atul-1972/SENTINEL-AI/actions/workflows/ci.yml). The dashboard does not poll GitHub, so it does not display live CI status. MLflow tracking, Evidently drift checks, Airflow orchestration, DVC status and automatic retraining remain unimplemented. Saved model comparisons are historical experiment results, not a live MLflow connection.
