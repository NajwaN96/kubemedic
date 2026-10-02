from app.redact import redact_text


def test_redacts_database_url_userinfo():
    cleaned = redact_text("postgresql://taskflow:super-secret-db-password@taskflow-postgres:5432/taskflow")
    assert "super-secret-db-password" not in cleaned
    assert "postgresql://***:***@taskflow-postgres:5432/taskflow" in cleaned


def test_redacts_password_assignment_bearer_and_aws_keys():
    cleaned = redact_text(
        "password=super-secret-db-password token: abc.def "
        "Authorization: Bearer demo-token-should-not-leak "
        "aws_secret_access_key=wJalrXUt"
    )
    assert "super-secret-db-password" not in cleaned
    assert "demo-token-should-not-leak" not in cleaned
    assert "wJalrXUt" not in cleaned
    assert "Bearer ***" in cleaned
    assert "password=***" in cleaned


def test_redacts_bare_access_key_id():
    cleaned = redact_text("key AKIAIOSFODNN7EXAMPLE was in the log")
    assert "AKIAIOSFODNN7EXAMPLE" not in cleaned


def test_keeps_secret_not_found_wording():
    message = 'Error: secret "taskflow-db" not found'
    assert redact_text(message) == message
