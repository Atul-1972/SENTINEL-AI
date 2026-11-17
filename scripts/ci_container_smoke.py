"""Verify an artifact-free CI image; these checks do not claim model readiness."""

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


def request(base_url, route, expected_status, body=None):
    payload = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base_url.rstrip("/") + route, data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        response = urllib.request.urlopen(req, timeout=5)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        status, raw = response.code, response.read()
    if status != expected_status:
        raise AssertionError(f"{route}: expected {expected_status}, got {status}")
    return json.loads(raw) if route != "/docs" else raw.decode()


def verify(base_url):
    deadline = time.monotonic() + 60
    while True:
        try:
            health = request(base_url, "/health", 503)
            break
        except (OSError, AssertionError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
    assert health["model_ready"] is False and health["database_ready"] is True
    assert health["status"] == "unavailable"
    assert request(base_url, "/", 200)["name"] == "SENTINEL AI"
    assert "swagger" in request(base_url, "/docs", 200).lower()
    paths = request(base_url, "/openapi.json", 200)["paths"]
    assert {"/predict", "/predict-batch", "/predictions", "/predictions/{prediction_id}"} <= set(paths)
    request(base_url, "/model-info", 503)
    assert request(base_url, "/predictions", 200) == []
    request(base_url, "/predictions/1", 404)
    assert request(base_url, "/alerts", 200) == []
    assert request(base_url, "/stats", 200)["total_flows"] == 0
    flow = {"features": {"duration": 1}, "source": "simulated"}
    request(base_url, "/predict", 503, flow)
    request(base_url, "/predict-batch", 503, {"flows": [flow]})
    assert request(base_url, "/stats", 200)["total_flows"] == 0
    return {
        "status": "passed", "mode": "artifact_free_ci_packaging_check",
        "model_ready": False, "database_ready": True,
        "inference_tested": False,
        "checks": ["docs_and_routes", "sqlite_ready", "empty_history", "missing_model_503", "failed_requests_write_nothing"],
        "note": "Mock-model endpoint tests run separately in pytest. Real trained-model checks are local only.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18001")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.base_url)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
