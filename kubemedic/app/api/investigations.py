"""Investigation queries. Resolve and AI analysis update SQLite only."""

from fastapi import APIRouter, HTTPException, Request

from app.ai.errors import AIDisabledError
from app.demo import replay, scenario_names
from app.investigation.models import Investigation

router = APIRouter()


@router.get("/api/v1/investigations", response_model=list[Investigation])
def list_investigations(
    request: Request,
    status: str | None = None,
    severity: str | None = None,
    issue: str | None = None,
) -> list[Investigation]:
    return request.app.state.service.list_investigations(
        status=status,
        severity=severity,
        issue=issue,
    )


@router.get("/api/v1/investigations/{investigation_id}", response_model=Investigation)
def get_investigation(investigation_id: str, request: Request) -> Investigation:
    investigation = request.app.state.service.get(investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail=f"Investigation {investigation_id} was not found.")
    return investigation


@router.get("/api/v1/ai/status")
def ai_status(request: Request) -> dict:
    return request.app.state.ai.status()


@router.post("/api/v1/investigations/{investigation_id}/ai/analyze", response_model=Investigation)
def analyze_investigation(investigation_id: str, request: Request) -> Investigation:
    try:
        investigation = request.app.state.service.analyze_with_ai(investigation_id)
    except AIDisabledError as exc:
        raise HTTPException(status_code=409, detail="AI analysis is disabled.") from exc
    if investigation is None:
        raise HTTPException(status_code=404, detail=f"Investigation {investigation_id} was not found.")
    return investigation


@router.post("/api/v1/investigations/{investigation_id}/resolve", response_model=Investigation)
def resolve_investigation(investigation_id: str, request: Request) -> Investigation:
    investigation = request.app.state.service.resolve(investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail=f"Investigation {investigation_id} was not found.")
    return investigation


@router.post("/api/v1/demo/{scenario}", response_model=Investigation)
def replay_demo(scenario: str, request: Request) -> Investigation:
    if not request.app.state.settings.demo_mode:
        raise HTTPException(
            status_code=404,
            detail="Demo replay is disabled. Start KubeMedic with KUBEMEDIC_DEMO_MODE=true.",
        )
    try:
        _title, investigation = replay(scenario, request.app.state.service)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return investigation


@router.get("/api/v1/demo")
def list_demos(request: Request) -> dict:
    if not request.app.state.settings.demo_mode:
        raise HTTPException(
            status_code=404,
            detail="Demo replay is disabled. Start KubeMedic with KUBEMEDIC_DEMO_MODE=true.",
        )
    return {"scenarios": scenario_names()}
