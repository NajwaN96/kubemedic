from sqlalchemy.exc import SQLAlchemyError


def test_task_lifecycle(client):
    empty = client.get("/tasks")
    assert empty.status_code == 200
    assert empty.json() == []

    created = client.post(
        "/tasks",
        json={"title": "  Check readiness  ", "description": "  Confirm PostgreSQL  "},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["title"] == "Check readiness"
    assert body["description"] == "Confirm PostgreSQL"
    assert body["status"] == "pending"
    assert body["created_at"]
    task_id = body["id"]

    listed = client.get("/tasks")
    assert listed.status_code == 200
    assert [task["id"] for task in listed.json()] == [task_id]

    updated = client.put(
        f"/tasks/{task_id}",
        json={"status": "completed", "description": "Readiness probe is green"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "completed"
    assert updated.json()["description"] == "Readiness probe is green"
    assert updated.json()["title"] == "Check readiness"

    deleted = client.delete(f"/tasks/{task_id}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get("/tasks").json() == []


def test_newest_task_is_listed_first(client):
    first = client.post("/tasks", json={"title": "First"}).json()
    second = client.post("/tasks", json={"title": "Second"}).json()
    titles = [task["title"] for task in client.get("/tasks").json()]
    assert titles == ["Second", "First"]
    assert second["id"] > first["id"]


def test_invalid_create_payloads(client):
    assert client.post("/tasks", json={}).status_code == 422
    assert client.post("/tasks", json={"title": "   "}).status_code == 422
    assert client.post("/tasks", json={"title": ""}).status_code == 422
    assert client.post("/tasks", json={"title": "x" * 201}).status_code == 422
    assert client.post("/tasks", json={"title": "Ok", "description": "y" * 2001}).status_code == 422


def test_invalid_updates_and_missing_tasks(client):
    assert client.put("/tasks/not-an-id", json={"status": "completed"}).status_code == 422
    missing = client.put("/tasks/999", json={"status": "completed"})
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Task not found"
    assert client.delete("/tasks/999").status_code == 404
    assert client.put("/tasks/1", json={}).status_code == 422
    created = client.post("/tasks", json={"title": "Keep me"}).json()
    rejected = client.put(f"/tasks/{created['id']}", json={"status": "archived"})
    assert rejected.status_code == 422
    assert client.get("/tasks").json()[0]["status"] == "pending"


def test_list_returns_503_when_the_database_errors(client, monkeypatch):
    def explode(_db):
        raise SQLAlchemyError("connection reset by peer")

    monkeypatch.setattr("app.routers.tasks.list_tasks", explode)
    response = client.get("/tasks")
    assert response.status_code == 503
    assert response.json()["detail"] == "Database unavailable"
    assert "connection reset" not in response.text
    assert "test-password-should-not-leak" not in response.text
