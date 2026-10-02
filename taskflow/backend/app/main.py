"""TaskFlow API application factory."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app import __version__
from app.config import Settings
from app.metrics import observe_request, render, route_path, set_ready
from app.db import build_engine, build_session_factory, database_error, ensure_schema
from app.logging_config import configure_logging, get_logger, redact
from app.routers import debug, health, tasks


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level, settings.service_name)
    logger = get_logger()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        failure = database_error(app.state.engine)
        if failure is None:
            try:
                ensure_schema(app.state.engine)
                app.state.schema_ready = True
                logger.info(
                    "database schema is ready",
                    extra={"endpoint": "startup", "status_code": 200},
                )
            except Exception as exc:  # noqa: BLE001
                app.state.schema_ready = False
                logger.error(
                    "schema initialization failed",
                    extra={
                        "endpoint": "startup",
                        "status_code": 503,
                        "error": redact(str(exc), settings.database_password),
                    },
                )
        else:
            app.state.schema_ready = False
            logger.warning(
                "database unavailable at startup; liveness stays up and readiness fails",
                extra={"endpoint": "startup", "status_code": 503},
            )
        yield
        app.state.engine.dispose()

    app = FastAPI(title="TaskFlow API", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = build_engine(settings)
    app.state.session_factory = build_session_factory(app.state.engine)
    app.state.schema_ready = False

    origins = _cors_origins(settings.cors_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "request failed",
                extra={
                    "endpoint": f"{request.method} {request.url.path}",
                    "status_code": 500,
                    "duration_ms": duration_ms,
                },
            )
            raise
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        status_code = response.status_code
        path = route_path(request)
        observe_request(request.method, path, status_code, duration_ms / 1000)
        if path == "/ready":
            set_ready(status_code == 200)
        if status_code >= 500:
            level = logging.ERROR
            message = "request failed"
        elif status_code >= 400:
            level = logging.WARNING
            message = "request rejected"
        else:
            level = logging.INFO
            message = "request completed"
        logger.log(
            level,
            message,
            extra={
                "endpoint": f"{request.method} {request.url.path}",
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    app.include_router(health.router)
    app.include_router(tasks.router)

    @app.get("/metrics")
    def metrics() -> Response:
        payload, content_type = render()
        return Response(content=payload, media_type=content_type)
    if settings.fault_injection_enabled:
        app.include_router(debug.router)
        logger.warning(
            "fault injection is enabled (DEMO / TESTING ONLY)",
            extra={"endpoint": "startup", "status_code": 200},
        )
    return app


def _cors_origins(raw: str) -> list[str]:
    value = raw.strip()
    if value == "*":
        return ["*"]
    return [item.strip() for item in value.split(",") if item.strip()]


app = create_app()
