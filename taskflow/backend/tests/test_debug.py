import pytest


FAULT_PATHS = [
    "/debug/error",
    "/debug/slow",
    "/debug/memory",
    "/debug/cpu",
    "/debug/crash",
]


@pytest.mark.parametrize("path", FAULT_PATHS)
def test_fault_routes_are_hidden_unless_enabled(client, path):
    response = client.post(path)
    assert response.status_code == 404
    spec = client.get("/openapi.json").json()["paths"]
    assert path not in spec


def test_forced_error_is_marked_as_a_demo(fault_client):
    response = fault_client.post("/debug/error")
    assert response.status_code == 500
    assert response.json()["detail"] == "DEMO / TESTING ONLY: forced server error"


def test_slow_request_respects_the_duration_cap(fault_client):
    ok = fault_client.post("/debug/slow", params={"seconds": 0.01})
    assert ok.status_code == 200
    assert ok.json()["notice"] == "DEMO / TESTING ONLY"
    rejected = fault_client.post("/debug/slow", params={"seconds": 30})
    assert rejected.status_code == 400


def test_memory_allocation_is_capped(fault_client):
    ok = fault_client.post("/debug/memory", params={"megabytes": 1})
    assert ok.status_code == 200
    assert ok.json()["megabytes"] == 1
    assert ok.json()["notice"] == "DEMO / TESTING ONLY"
    rejected = fault_client.post("/debug/memory", params={"megabytes": 256})
    assert rejected.status_code == 400


def test_cpu_load_is_capped(fault_client):
    ok = fault_client.post("/debug/cpu", params={"seconds": 0.05})
    assert ok.status_code == 200
    assert ok.json()["notice"] == "DEMO / TESTING ONLY"
    rejected = fault_client.post("/debug/cpu", params={"seconds": 30})
    assert rejected.status_code == 400


def test_crash_requests_termination_without_killing_the_test_process(fault_client, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr("app.routers.debug.terminate_process", lambda: calls.append("terminate"))
    response = fault_client.post("/debug/crash")
    assert response.status_code == 200
    assert response.json()["notice"] == "DEMO / TESTING ONLY"
    assert calls == ["terminate"]
