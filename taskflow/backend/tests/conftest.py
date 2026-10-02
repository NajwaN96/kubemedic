import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client():
    app = create_app(
        Settings(
            sqlalchemy_url="sqlite+pysqlite:///:memory:",
            fault_injection_enabled=False,
            database_password="test-password-should-not-leak",
        )
    )
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def fault_client():
    app = create_app(
        Settings(
            sqlalchemy_url="sqlite+pysqlite:///:memory:",
            fault_injection_enabled=True,
        )
    )
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def offline_client():
    app = create_app(
        Settings(
            database_host="127.0.0.1",
            database_port=1,
            database_name="taskflow",
            database_user="taskflow",
            database_password="super-secret-db-password",
            database_connect_timeout=1,
            fault_injection_enabled=False,
        )
    )
    with TestClient(app) as test_client:
        yield test_client
