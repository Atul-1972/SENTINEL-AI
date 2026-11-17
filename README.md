# SENTINEL AI

## About the project

SENTINEL AI is an educational intrusion detection application that uses machine learning to analyze recorded network traffic. It helps users identify normal and suspicious network flows through a local web dashboard.

The project uses the CIC-IDS2017 Friday DDoS dataset. Its classifier predicts two classes: BENIGN and ATTACK. DDoS is the only attack type represented in the selected dataset. A separate Isolation Forest model flags unusual traffic patterns.

## What it does

- Accepts CSV files containing network flow features and analyzes them in batches.
- Classifies flows as BENIGN or ATTACK using XGBoost.
- Provides separate anomaly flags using Isolation Forest.
- Assigns risk scores and generates alerts for suspicious flows.
- Stores predictions, input features and alerts in SQLite for later review.
- Displays traffic summaries, risk distributions, prediction history and model performance across five dashboard pages: Overview, Detection, Threats, Performance and Monitoring.
- Supports filtering, flow inspection and result exports.
- Uses GitHub Actions to automatically test the backend and frontend and check the Docker build.

The application analyzes uploaded flow records; it does not capture live packets or automatically block attacks. Model probabilities are uncalibrated, and anomaly flags do not identify attack categories.

## Results

A cleaned subset of 20,000 records was prepared from the source CSV containing 225,745 records. The subset was divided into 12,000 training records, 4,000 validation records and 4,000 test records. Learned preprocessing was fitted on training data only.

### Validation comparison

| Classifier | Accuracy | Attack recall | Attack F1 |
| --- | ---: | ---: | ---: |
| Random Forest | 99.85% | 99.78% | 99.87% |
| XGBoost | 99.925% | 99.87% | 99.93% |

XGBoost was selected using validation results before evaluating the held-out test set.

### Final XGBoost test results

| Metric | Result |
| --- | ---: |
| Test records | 4,000 |
| Accuracy | 99.85% |
| Attack precision | 100.00% |
| Attack recall | 99.74% |
| Attack F1 | 99.87% |
| ROC-AUC | 0.99959 |
| False alarms | 0 |
| Missed attacks | 6 |

The model correctly classified all 1,705 benign test records and detected 2,289 of 2,295 attack records. Full results are preserved in the [test report](reports/final_test_metrics.json) and [validation comparison](reports/model_comparison.json).

Isolation Forest had approximately 15.99% attack recall and a 5.51% benign false-positive rate on validation data. It is used as a supplementary anomaly signal alongside XGBoost.

These results come from random holdouts within one traffic capture. They do not establish performance on different networks, capture days or attack types. SENTINEL AI is a college project prototype, not a certified network protection system.

## Technology stack

| Area | Technologies used |
| --- | --- |
| Programming languages | Python, JavaScript, HTML, CSS |
| Data processing | pandas, NumPy |
| Machine learning | XGBoost, scikit-learn, Random Forest, Isolation Forest, joblib |
| Training environment | Google Colab, Jupyter Notebook |
| Backend API | FastAPI, Uvicorn, Pydantic |
| Database | SQLite, SQLAlchemy |
| Frontend | React, Vite, Tailwind CSS |
| Charts, icons and CSV parsing | Recharts, Lucide, PapaParse |
| Containerization | Docker, Docker Compose |
| Version control and CI | Git, GitHub, GitHub Actions |
| Testing | pytest, HTTPX, Node.js test runner, Playwright |
