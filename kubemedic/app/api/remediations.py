"""Approval API. Kubernetes writes stay in the remediator process."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.remediation.errors import PolicyError, RemediationDisabled
from app.remediation.models import Remediation

router = APIRouter()


class ApprovalRequest(BaseModel):
    approved_by: str
    confirm: bool = False
    reason: str = Field(default="", max_length=280)


@router.get("/api/v1/remediation/status")
def remediation_status(request: Request) -> dict:
    return request.app.state.remediation.status()


@router.get("/api/v1/remediations", response_model=list[Remediation])
def list_remediations(request: Request, status: str | None = None) -> list[Remediation]:
    return request.app.state.remediation.list_remediations(status=status)


@router.get("/api/v1/remediations/{remediation_id}", response_model=Remediation)
def get_remediation(remediation_id: str, request: Request) -> Remediation:
    remediation = request.app.state.remediation.get(remediation_id)
    if remediation is None:
        raise HTTPException(status_code=404, detail=f"Remediation {remediation_id} was not found.")
    return remediation


@router.get("/api/v1/investigations/{investigation_id}/remediations", response_model=list[Remediation])
def list_investigation_remediations(investigation_id: str, request: Request) -> list[Remediation]:
    if request.app.state.service.get(investigation_id) is None:
        raise HTTPException(status_code=404, detail=f"Investigation {investigation_id} was not found.")
    return request.app.state.remediation.list_for_investigation(investigation_id)


@router.post("/api/v1/remediations/{remediation_id}/approve", response_model=Remediation)
def approve_remediation(remediation_id: str, body: ApprovalRequest, request: Request) -> Remediation:
    return _approve(request, remediation_id, body)


@router.post("/api/v1/investigations/{investigation_id}/remediation/approve", response_model=Remediation)
def approve_investigation_remediation(
    investigation_id: str,
    body: ApprovalRequest,
    request: Request,
) -> Remediation:
    if request.app.state.service.get(investigation_id) is None:
        raise HTTPException(status_code=404, detail=f"Investigation {investigation_id} was not found.")
    proposed = [
        item
        for item in request.app.state.remediation.list_for_investigation(investigation_id)
        if item.status == "proposed"
    ]
    if not proposed:
        raise HTTPException(status_code=404, detail="No proposed remediation for this investigation.")
    return _approve(request, proposed[-1].id, body)


@router.post("/api/v1/remediations/{remediation_id}/cancel", response_model=Remediation)
def cancel_remediation(remediation_id: str, request: Request) -> Remediation:
    try:
        remediation = request.app.state.remediation.cancel(remediation_id)
    except PolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if remediation is None:
        raise HTTPException(status_code=404, detail=f"Remediation {remediation_id} was not found.")
    return remediation


def _approve(request: Request, remediation_id: str, body: ApprovalRequest) -> Remediation:
    try:
        remediation = request.app.state.remediation.approve(
            remediation_id,
            approved_by=body.approved_by,
            confirm=body.confirm,
            reason=body.reason,
        )
    except RemediationDisabled as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if remediation is None:
        raise HTTPException(status_code=404, detail=f"Remediation {remediation_id} was not found.")
    return remediation
