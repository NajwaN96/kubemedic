"""Process health. Kubernetes connectivity does not fail these routes."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.metrics import render_metrics

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "kubemedic"}


@router.get("/ready")
def ready(request: Request):
    repository = request.app.state.repository
    if repository.healthy():
        return {"status": "ready"}
    return JSONResponse(status_code=503, content={"status": "not_ready"})


@router.get("/metrics")
def metrics(request: Request) -> Response:
    payload, content_type = render_metrics(
        request.app.state.repository,
        request.app.state.cluster.connected,
        request.app.state.remediations,
    )
    return Response(content=payload, media_type=content_type)
