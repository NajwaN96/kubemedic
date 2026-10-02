import json
import logging

from app.logging_config import JsonFormatter, redact


def test_health_is_ok_without_database(offline_client):
    response = offline_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "taskflow-api"


def test_ready_when_database_is_connected(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected"}


def test_ready_fails_when_database_is_down(offline_client):
    response = offline_client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "database": "unavailable"}
    assert "super-secret-db-password" not in response.text


def test_ready_log_does_not_include_the_password(offline_client, caplog):
    caplog.set_level(logging.WARNING, logger="taskflow")
    offline_client.get("/ready")
    assert any(record.message == "database readiness check failed" for record in caplog.records)
    assert "super-secret-db-password" not in caplog.text


def test_request_log_has_investigation_fields(client, caplog):
    caplog.set_level(logging.INFO, logger="taskflow")
    response = client.get("/health")
    assert response.status_code == 200
    matched = [
        record
        for record in caplog.records
        if record.name == "taskflow" and getattr(record, "endpoint", "") == "GET /health"
    ]
    assert matched
    record = matched[-1]
    payload = json.loads(JsonFormatter("taskflow-api").format(record))
    assert payload["level"] == "INFO"
    assert payload["service"] == "taskflow-api"
    assert payload["endpoint"] == "GET /health"
    assert payload["status_code"] == 200
    assert payload["message"]
    assert "timestamp" in payload
    assert "duration_ms" in payload


def test_metrics_use_route_templates_instead_of_task_ids(client):
    created = client.post("/tasks", json={"title": "metrics check", "description": "no id label"})
    assert created.status_code == 201
    task_id = created.json()["id"]
    client.delete(f"/tasks/{task_id}")
    body = client.get("/metrics").text
    assert "taskflow_http_requests_total" in body
    assert "taskflow_http_request_duration_seconds" in body
    assert "taskflow_ready" in body
    assert 'path="/tasks/{task_id}"' in body
    assert f'path="/tasks/{task_id}"' not in body


def test_redact_removes_urls_and_secrets():
    raw = "failed postgresql+psycopg://taskflow:super-secret@db:5432/taskflow"
    cleaned = redact(raw, "super-secret")
    assert "super-secret" not in cleaned
    assert "db:5432" not in cleaned
