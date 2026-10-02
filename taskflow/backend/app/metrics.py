"""TaskFlow HTTP metrics.

Labels are method, route template, and status code. Task IDs are never labels.
"""

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

REQUESTS = Counter(
    "taskflow_http_requests_total",
    "HTTP requests served by the TaskFlow API.",
    ["method", "path", "status"],
)
LATENCY = Histogram(
    "taskflow_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
)
READY = Gauge(
    "taskflow_ready",
    "1 when the most recent readiness check reached PostgreSQL.",
)
UP = Gauge(
    "taskflow_up",
    "1 when the TaskFlow API process is serving metrics.",
)


def observe_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    status = str(status_code)
    REQUESTS.labels(method=method, path=path, status=status).inc()
    LATENCY.labels(method=method, path=path).observe(duration_seconds)


def set_ready(ready: bool) -> None:
    READY.set(1 if ready else 0)


def render() -> tuple[bytes, str]:
    UP.set(1)
    return generate_latest(), CONTENT_TYPE_LATEST


def route_path(request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return path
    return "unmatched"
