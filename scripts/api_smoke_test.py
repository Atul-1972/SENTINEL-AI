"""Submit historical demo flows to a running local API and verify actual responses."""

import argparse
import json
from pathlib import Path

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/phase2_api_smoke.json")
    args = parser.parse_args()
    records = json.loads((ROOT / "reports/inference_smoke_test.json").read_text(encoding="utf-8"))["flows"]
    flows = [{"features": row["features"], "source": "historical"} for row in records]
    with httpx.Client(base_url=args.base_url, timeout=30, trust_env=False) as client:
        checks = {}
        for path in ["/", "/health", "/docs", "/openapi.json", "/model-info"]:
            response = client.get(path)
            response.raise_for_status()
            checks[path] = response.status_code
        before = client.get("/stats").json()["total_flows"]
        response = client.post("/predict-batch", json={"flows": flows})
        response.raise_for_status()
        checks["/predict-batch"] = response.status_code
        results = response.json()["results"]
        assert len(results) == len(records)
        assert [r["predicted_class"] for r in results] == [r["predicted_class"] for r in records]
        assert np.allclose([r["attack_probability"] for r in results], [r["attack_probability_uncalibrated"] for r in records], rtol=1e-6)
        assert np.allclose([r["anomaly_score"] for r in results], [r["anomaly_score"] for r in records], rtol=1e-6)
        assert [r["anomaly_flag"] for r in results] == [r["anomaly_flag"] for r in records]
        assert all(r["source"] == "historical" and r["predicted_attack_category"] is None for r in results)
        response = client.post("/predict", json=flows[0])
        response.raise_for_status()
        checks["/predict"] = response.status_code
        assert response.json()["predicted_class"] == records[0]["predicted_class"]
        bad = {"features": {key: value for index, (key, value) in enumerate(flows[0]["features"].items()) if index != 0}}
        invalid = client.post("/predict-batch", json={"flows": [flows[0], bad]})
        assert invalid.status_code == 422
        stats_response = client.get("/stats")
        stats_response.raise_for_status()
        stats = stats_response.json()
        assert stats["total_flows"] == before + len(records) + 1
        checks["/stats"] = stats_response.status_code
        alerts_response = client.get("/alerts?limit=200")
        alerts_response.raise_for_status()
        alert_ids = {r["prediction_id"] for r in alerts_response.json()}
        expected_alerts = {r["id"] for r in results if r["risk_level"] != "LOW"}
        assert expected_alerts <= alert_ids
        checks["/alerts"] = alerts_response.status_code
        report = {
            "status": "passed", "base_url": args.base_url, "http_checks": checks,
            "batch_flows_verified_against_colab": len(records),
            "single_prediction_verified": True, "invalid_batch_status": invalid.status_code,
            "invalid_batch_wrote_no_records": True, "expected_alerts_present": True,
            "flows_before": before, "flows_after": stats["total_flows"],
            "source": "Historical validation demo flows; no network attack was generated.",
        }
    output = args.report if args.report.is_absolute() else ROOT / args.report
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("\nSaved:", output)
    print("The smoke test adds 11 actual historical predictions to the API history on each run.")


if __name__ == "__main__":
    main()
