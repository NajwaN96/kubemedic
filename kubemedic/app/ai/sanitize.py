"""Last boundary before evidence can leave the process.

Stored investigations are already redacted. This pass runs again on the
AI payload so a provider sees only the sanitized copy.

It is not a complete secret scanner. KubeMedic still does not read
Kubernetes Secret objects.
"""

import re

_PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
)
_URL = re.compile(r"\b([a-zA-Z][a-zA-Z0-9+.-]*://)([^/\s:@]+):([^/\s@]+)@")
_AWS = re.compile(
    r"(?i)\b(aws_secret_access_key|aws_access_key_id|aws_session_token)(\s*[:=]\s*)(\S+)"
)
_KV = re.compile(
    r"(?i)\b(client_secret|access_key|api[_-]?key|apikey|authorization|password|passwd|token|secret)"
    r"(\s*[:=]\s*)((?:bearer\s+)?\S+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+\S+")
_OPENAI = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{16,}\b")
_AKIA = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b")


def sanitize_text(value: str) -> str:
    if not value:
        return ""
    cleaned = _PRIVATE_KEY.sub("[REDACTED]", value)
    cleaned = _URL.sub(r"\1[REDACTED]:[REDACTED]@", cleaned)
    cleaned = _AWS.sub(r"\1\2[REDACTED]", cleaned)
    cleaned = _KV.sub(_redact_assignment, cleaned)
    cleaned = _BEARER.sub("Bearer [REDACTED]", cleaned)
    cleaned = _OPENAI.sub("[REDACTED]", cleaned)
    cleaned = _AKIA.sub("[REDACTED]", cleaned)
    cleaned = _JWT.sub("[REDACTED]", cleaned)
    return cleaned


def sanitize_payload(value: object) -> object:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, dict):
        return {str(key): sanitize_payload(item) for key, item in value.items()}
    return value


def _redact_assignment(match: re.Match) -> str:
    value = match.group(3)
    if value.lower().startswith("bearer "):
        return f"{match.group(1)}{match.group(2)}Bearer [REDACTED]"
    return f"{match.group(1)}{match.group(2)}[REDACTED]"
