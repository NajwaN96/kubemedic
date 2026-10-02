"""Best-effort redaction before evidence is stored or shown.

KubeMedic does not read Kubernetes Secret data. This layer catches
credentials that leak into logs or event messages. It is not a guarantee
that every secret pattern will be recognized.
"""

import re

_KV = re.compile(
    r"(?i)\b(password|passwd|token|authorization|api[_-]?key|secret)\b(\s*[:=]\s*)((?:bearer\s+)?\S+)"
)
_AWS = re.compile(
    r"(?i)\b(aws_secret_access_key|aws_access_key_id|aws_session_token)(\s*[:=]\s*)(\S+)"
)
_AKIA = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*")
_URL = re.compile(r"\b([a-zA-Z][a-zA-Z0-9+.-]*://)([^/\s:@]+):([^/\s@]+)@")
_OPENAI = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{16,}\b")


def redact_text(value: str) -> str:
    if not value:
        return ""
    cleaned = _URL.sub(r"\1***:***@", value)
    cleaned = _AWS.sub(r"\1\2***", cleaned)
    cleaned = _KV.sub(_redact_assignment, cleaned)
    cleaned = _BEARER.sub("Bearer ***", cleaned)
    cleaned = _AKIA.sub("AKIA***", cleaned)
    cleaned = _OPENAI.sub("***", cleaned)
    return cleaned


def _redact_assignment(match: re.Match) -> str:
    value = match.group(3)
    if value.lower().startswith("bearer "):
        return f"{match.group(1)}{match.group(2)}Bearer ***"
    return f"{match.group(1)}{match.group(2)}***"
