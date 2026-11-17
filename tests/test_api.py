import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from backend.main import create_app


def flow(duration=10, packet_rate=1):
    return {"features": {"duration": duration, "packet_rate": packet_rate}, "source": "historical"}


def test_information_docs_and_empty_history(client):
    assert client.get("/").json()["docs"] == "/docs"
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/", "/health", "/predict", "/predict-batch", "/model-info", "/alerts", "/stats"} <= set(paths)
    assert client.get("/health").json()["model_ready"] is True
    assert client.get("/model-info").json()["model_version"] == "fixture-1"
    assert client.get("/alerts").json() == []
    stats = client.get("/stats").json()
    assert stats["total_flows"] == stats["alerts_total"] == 0
    assert stats["traffic_trends"] == []


def test_single_prediction_is_persisted_with_explicit_probability_label(client):
    response = client.post("/predict", json=flow(100))
    assert response.status_code == 200
    result = response.json()
    assert result["predicted_class"] == "ATTACK"
    assert result["predicted_attack_category"] is None
    assert result["risk_level"] == "HIGH" and result["risk_score"] == 80
    assert result["confidence_type"] == "uncalibrated_model_probability"
    assert result["model_version"] == "fixture-1"
    assert result["created_at"].endswith("Z")
    assert "features" not in result
    alert = client.get("/alerts").json()[0]
    assert alert["prediction_id"] == result["id"]
    assert alert["source"] == "historical"
    assert client.get("/stats").json()["total_flows"] == 1


def test_all_risk_cases_have_consistent_alerts_and_statistics(client):
    response = client.post("/predict-batch", json={"flows": [flow(10, 1), flow(10, -1), flow(100, 1), flow(100, -1)]})
    assert response.status_code == 200
    result = response.json()
    assert result["count"] == 4
    assert [row["risk_score"] for row in result["results"]] == [0, 40, 80, 90]
    assert [row["risk_level"] for row in result["results"]] == ["LOW", "MEDIUM", "HIGH", "HIGH"]
    stats = client.get("/stats").json()
    assert stats["total_flows"] == 4
    assert stats["benign_flows"] == stats["attack_flows"] == stats["anomaly_flows"] == 2
    assert stats["suspicious_flows"] == stats["alerts_total"] == 3
    assert stats["high_risk_alerts"] == 2
    assert stats["class_distribution"] == {"BENIGN": 2, "ATTACK": 2}
    assert stats["risk_distribution"] == {"LOW": 1, "MEDIUM": 1, "HIGH": 2}
    assert stats["source_distribution"] == {"historical": 4}
    assert sum(row["flows"] for row in stats["traffic_trends"]) == 4
    high = client.get("/alerts?risk_level=HIGH&limit=1&offset=1").json()
    assert len(high) == 1 and high[0]["risk_score"] == 80
    medium = client.get("/alerts?risk_level=MEDIUM").json()
    assert len(medium) == 1 and "classifier returned BENIGN" in medium[0]["message"]


@pytest.mark.parametrize("value", ["10", True, 1e40, -1e40])
def test_invalid_numeric_values_do_not_write_history(client, value):
    assert client.post("/predict", json=flow(value)).status_code == 422
    assert client.get("/stats").json()["total_flows"] == 0


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_nonfinite_json_values_return_serializable_errors(client, literal):
    body = '{"features":{"duration":' + literal + ',"packet_rate":1}}'
    response = client.post("/predict", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["detail"]
    assert client.get("/stats").json()["total_flows"] == 0


def test_null_is_supported_but_an_entirely_missing_flow_is_rejected(client):
    assert client.post("/predict", json=flow(None)).status_code == 200
    assert client.post("/predict", json=flow(None, None)).status_code == 422


@pytest.mark.parametrize("features", [{"duration": 1}, {"duration": 1, "packet_rate": 2, "Label": 1}])
def test_missing_and_unknown_features_are_rejected(client, features):
    response = client.post("/predict", json={"features": features})
    assert response.status_code == 422
    assert response.json()["detail"]["errors"][0]["flow_index"] == 0
    assert client.get("/stats").json()["total_flows"] == 0


def test_invalid_second_batch_record_does_not_commit_the_first(client):
    bad = {"features": {"duration": 2}}
    assert client.post("/predict-batch", json={"flows": [flow(100), bad]}).status_code == 422
    assert client.get("/stats").json()["total_flows"] == 0
    assert client.get("/alerts").json() == []


@pytest.mark.parametrize("count", [0, 1001])
def test_batch_limits(client, count):
    assert client.post("/predict-batch", json={"flows": [flow()] * count}).status_code == 422


def test_invalid_wrapper_source_and_query_arguments(client):
    assert client.post("/predict", json={**flow(), "unexpected": 1}).status_code == 422
    assert client.post("/predict", json={**flow(), "source": "live"}).status_code == 422
    assert client.post("/predict", content="broken json", headers={"Content-Type": "application/json"}).status_code == 422
    assert client.get("/alerts?limit=201").status_code == 422
    assert client.get("/alerts?offset=-1").status_code == 422


def test_database_failure_returns_unavailable_without_success_response(client, monkeypatch):
    def fail(*args):
        raise SQLAlchemyError("fixture database unavailable")
    monkeypatch.setattr(client.app.state.database, "save_predictions", fail)
    response = client.post("/predict", json=flow(100))
    assert response.status_code == 503
    assert client.get("/stats").json()["total_flows"] == 0


def test_missing_artifacts_keep_health_and_swagger_available(tmp_path):
    with TestClient(create_app(artifacts_dir=tmp_path, database_url="sqlite://")) as client:
        assert client.get("/health").status_code == 503
        assert client.get("/health").json()["database_ready"] is True
        assert client.get("/docs").status_code == 200
        assert client.get("/model-info").status_code == 503
        assert client.post("/predict", json=flow()).status_code == 503
        assert client.get("/stats").json()["total_flows"] == 0


def test_sqlite_history_survives_restart(tmp_path, fake_service):
    url = "sqlite:///" + (tmp_path / "history.db").as_posix()
    with TestClient(create_app(database_url=url, model_service=fake_service)) as first:
        first.post("/predict", json=flow(100))
    with TestClient(create_app(database_url=url, model_service=fake_service)) as second:
        assert second.get("/stats").json()["total_flows"] == 1
        assert len(second.get("/alerts").json()) == 1


def test_prediction_history_filters_details_and_missing_record(client):
    payload = {"flows": [flow(10, 1), flow(10, -1), flow(100, 1), flow(100, -1)]}
    results = client.post("/predict-batch", json=payload).json()["results"]
    attack = client.get("/predictions?predicted_class=ATTACK&limit=1&offset=1").json()
    assert [row["id"] for row in attack] == [results[2]["id"]]
    anomalies = client.get("/predictions?anomaly_only=true").json()
    assert len(anomalies) == 2 and all(row["anomaly_flag"] for row in anomalies)
    medium = client.get("/predictions?risk_level=MEDIUM").json()
    assert len(medium) == 1 and medium[0]["predicted_class"] == "BENIGN"
    detail = client.get(f"/predictions/{results[0]['id']}").json()
    assert detail["features"] == payload["flows"][0]["features"]
    assert "features" not in client.get("/predictions").json()[0]
    assert client.get("/predictions/999999").status_code == 404
    assert client.get("/predictions?limit=201").status_code == 422
    assert client.get("/stats").json()["total_flows"] == 4
