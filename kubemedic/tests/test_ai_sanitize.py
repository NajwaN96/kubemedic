from app.ai.sanitize import sanitize_payload, sanitize_text


def test_redacts_password_token_and_authorization():
    cleaned = sanitize_text(
        "password=supersecret\n"
        "token: abc.def\n"
        "Authorization: Bearer demo-token-should-not-leak\n"
        "client_secret=client-secret-value\n"
        "access_key=access-key-value\n"
        "api_key=api-key-value\n"
    )
    for secret in (
        "supersecret",
        "abc.def",
        "demo-token-should-not-leak",
        "client-secret-value",
        "access-key-value",
        "api-key-value",
    ):
        assert secret not in cleaned
    assert "password=[REDACTED]" in cleaned
    assert "token: [REDACTED]" in cleaned
    assert "Bearer [REDACTED]" in cleaned


def test_redacts_openai_aws_postgres_and_basic_auth():
    cleaned = sanitize_text(
        "key sk-proj-abcdefghijklmnopqrstuvwxyz was logged\n"
        "aws_secret_access_key=wJalrXUtnFEMI\n"
        "AKIAIOSFODNN7EXAMPLE\n"
        "postgresql://taskflow:super-secret-db-password@db:5432/taskflow\n"
        "https://user:s3cret@example.com/hook\n"
    )
    for secret in (
        "sk-proj-abcdefghijklmnopqrstuvwxyz",
        "wJalrXUtnFEMI",
        "AKIAIOSFODNN7EXAMPLE",
        "super-secret-db-password",
        "s3cret",
    ):
        assert secret not in cleaned
    assert "postgresql://[REDACTED]:[REDACTED]@db:5432/taskflow" in cleaned
    assert "https://[REDACTED]:[REDACTED]@example.com/hook" in cleaned
    assert "[REDACTED]" in cleaned


def test_redacts_private_keys_and_service_account_tokens():
    pem = "-----BEGIN PRIVATE KEY-----\nSECRETDATA\n-----END PRIVATE KEY-----"
    token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJrdWJlbWVkaWMifQ.signaturevalue"
    cleaned = sanitize_text(f"{pem}\n{token}")
    assert "SECRETDATA" not in cleaned
    assert "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9" not in cleaned
    assert cleaned.count("[REDACTED]") == 2


def test_keeps_secret_not_found_wording():
    message = 'Error: secret "taskflow-db" not found'
    assert sanitize_text(message) == message


def test_nested_multiline_payload_is_redacted_before_a_provider_would_see_it():
    payload = {
        "issue": "CrashLoopBackOff",
        "recent_logs": [
            {"source": "previous", "content": "password=supersecret\ntoken=another-token"},
        ],
        "recent_events": [
            {"reason": "BackOff", "message": "Authorization: Bearer header-token"},
        ],
        "nested": {"env": "postgres://app:db-pass@postgres:5432/app"},
    }
    cleaned = sanitize_payload(payload)
    encoded = str(cleaned)
    for secret in ("supersecret", "another-token", "header-token", "db-pass"):
        assert secret not in encoded
    assert cleaned["recent_logs"][0]["content"].splitlines()[0] == "password=[REDACTED]"
    assert cleaned["issue"] == "CrashLoopBackOff"
