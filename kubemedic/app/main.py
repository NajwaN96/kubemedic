"""KubeMedic HTTP process.

The watcher is optional. If Kubernetes is unreachable, /health, /ready,
the investigation API, and the dashboard still start.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.ai.coordinator import AICoordinator
from app.api import cluster, health, investigations, remediations
from app.config import Settings
from app.investigation.repository import InvestigationRepository
from app.investigation.service import InvestigationService
from app.kubernetes.client import ClusterConnection
from app.kubernetes.watcher import Watcher
from app.remediation.service import RemediationService

logger = logging.getLogger(__name__)
DASHBOARD = Path(__file__).resolve().parent / "web" / "dashboard"


def create_app(
    settings: Settings | None = None,
    cluster_connection: ClusterConnection | None = None,
    ai: AICoordinator | None = None,
) -> FastAPI:
    settings = settings or Settings()
    repository = InvestigationRepository(settings.db_path)
    ai = ai or AICoordinator(settings, repository)
    service = InvestigationService(repository, settings, ai=ai)
    cluster_connection = cluster_connection or ClusterConnection(settings).connect()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        watcher = None
        if settings.watch_enabled:
            watcher = Watcher(cluster_connection, service, settings)
            watcher.start()
            app.state.watcher = watcher
        if not cluster_connection.connected:
            logger.warning(
                "Kubernetes Status: Disconnected. The API and dashboard remain available."
            )
        yield
        if watcher is not None:
            watcher.stop()

    app = FastAPI(title="KubeMedic", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.repository = repository
    app.state.service = service
    app.state.ai = ai
    app.state.cluster = cluster_connection
    app.state.remediations = service.remediations
    app.state.remediation = RemediationService(service.remediations, settings)

    app.include_router(health.router)
    app.include_router(cluster.router)
    app.include_router(investigations.router)
    app.include_router(remediations.router)

    @app.get("/")
    def dashboard_home():
        return FileResponse(DASHBOARD / "index.html")

    @app.get("/investigations")
    def dashboard_investigations():
        return FileResponse(DASHBOARD / "index.html")

    @app.get("/investigations/{investigation_id}")
    def dashboard_detail(investigation_id: str):
        return FileResponse(DASHBOARD / "index.html")

    @app.get("/remediations")
    def dashboard_remediations():
        return FileResponse(DASHBOARD / "index.html")

    @app.get("/remediations/{remediation_id}")
    def dashboard_remediation(remediation_id: str):
        return FileResponse(DASHBOARD / "index.html")

    @app.get("/observability")
    def dashboard_observability():
        return FileResponse(DASHBOARD / "index.html")

    @app.get("/system")
    def dashboard_system():
        return FileResponse(DASHBOARD / "index.html")

    app.mount("/static", StaticFiles(directory=DASHBOARD), name="dashboard-static")
    return app


app = create_app()
