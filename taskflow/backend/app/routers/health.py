"""Liveness and readiness."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.db import database_error, ensure_schema
from app.logging_config import get_logger, redact

router = APIRouter(tags=["health"])
logger = get_logger()


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    """Process is up. This does not check PostgreSQL."""
    settings = request.app.state.settings
    return {"status": "ok", "service": settings.service_name}


@router.get("/ready", response_model=None)
def ready(request: Request) -> JSONResponse | dict[str, str]:
    """Ready only when PostgreSQL accepts a query and the schema exists."""
    engine = request.app.state.engine
    failure = database_error(engine)
    if failure is not None:
        _log_database_failure(request, failure)
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "unavailable"},
        )
    try:
        ensure_schema(engine)
        request.app.state.schema_ready = True
    except Exception as exc:  # noqa: BLE001 - schema errors must become a 503
        _log_database_failure(request, exc)
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "unavailable"},
        )
    return {"status": "ready", "database": "connected"}


def _log_database_failure(request: Request, exc: Exception) -> None:
    secret = request.app.state.settings.database_password
    logger.warning(
        "database readiness check failed",
        extra={
            "endpoint": "GET /ready",
            "status_code": 503,
            "error": redact(str(exc), secret),
        },
    )
