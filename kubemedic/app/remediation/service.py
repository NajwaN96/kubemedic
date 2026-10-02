"""Human approval. This module does not call Kubernetes."""

from datetime import datetime, timezone

from app.config import Settings
from app.investigation.models import TransitionItem
from app.remediation.errors import PolicyError, RemediationDisabled
from app.remediation.models import Remediation
from app.remediation.policy import validate_approval, validate_target
from app.remediation.repository import RemediationRepository


class RemediationService:
    def __init__(self, repository: RemediationRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def status(self) -> dict:
        return {
            "enabled": self.settings.remediation_enabled,
            "approval_required": True,
        }

    def get(self, remediation_id: str) -> Remediation | None:
        return self.repository.get(remediation_id)

    def list_remediations(self, status: str | None = None) -> list[Remediation]:
        return self.repository.list_remediations(status=status)

    def list_for_investigation(self, investigation_id: str) -> list[Remediation]:
        return self.repository.list_for_investigation(investigation_id)

    def approve(
        self,
        remediation_id: str,
        approved_by: str,
        confirm: bool,
        reason: str = "",
        now: datetime | None = None,
    ) -> Remediation | None:
        if not self.settings.remediation_enabled:
            raise RemediationDisabled(
                "Remediation is disabled. A person must approve each action, and execution stays off."
            )
        validate_approval(approved_by, confirm, reason)
        current = self.repository.get(remediation_id)
        if current is None:
            return None
        if current.status != "proposed":
            raise PolicyError("Only a proposed remediation can be approved.")
        validate_target(current, self.settings)
        moment = now or datetime.now(timezone.utc)
        current.status = "approved"
        current.approved_by = approved_by
        current.approved_at = moment
        current.approval_reason = reason or None
        current.updated_at = moment
        current.transitions.append(
            TransitionItem(at=moment, status="approved", reason=f"Approved by {approved_by}")
        )
        return self.repository.update(current)

    def cancel(self, remediation_id: str, now: datetime | None = None) -> Remediation | None:
        current = self.repository.get(remediation_id)
        if current is None:
            return None
        if current.status not in {"proposed", "approved"}:
            raise PolicyError("Only a proposed or approved remediation can be cancelled.")
        moment = now or datetime.now(timezone.utc)
        current.status = "cancelled"
        current.updated_at = moment
        current.transitions.append(TransitionItem(at=moment, status="cancelled", reason="Cancelled before execution"))
        return self.repository.update(current)
