SENTINEL AI Phase 1 export
Model: sentinel-xgboost-1.0.0
Fixed quality gate: PASSED
Training Python: 3.13.18
Export Python: 3.13.18
Install matching package versions from requirements-model.txt. Preserve the training Python version where feasible.
Extract artifacts/ into the local project. Keep reports/ and data/ for the college demonstration and monitoring.
Demo CSV rows are historical validation data. Predictions are measured, not guaranteed correct.
Classifier is binary BENIGN/ATTACK, trained on BENIGN and DDoS only.
Anomaly scores are separate and do not identify attack categories or calibrated probabilities.
This is an educational prototype, not production network protection.
