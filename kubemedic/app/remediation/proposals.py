"""Turn a deterministic finding into a typed proposal.

AI text is ignored. Several issues stay informational because changing the
Deployment would not fix them.
"""

from datetime import datetime, timezone

from app.config import Settings
from app.investigation.models import Investigation, TransitionItem
from app.remediation.models import Remediation
from app.remediation.repository import RemediationRepository

# These need a person to fix configuration, capacity, or a dependency.
_INFORMATIONAL = {
    "FailedScheduling",
    "CreateContainerConfigError",
    "CreateContainerError",
    "ImagePullBackOff",
    "ErrImagePull",
    "FailedMount",
    "DatabaseConnectivity",
    "LivenessProbeFailed",
    "ReadinessProbeFailed",
    "OOMKilled",
}
_RESTARTABLE = {"CrashLoopBackOff", "UnavailableReplicas", "RepeatedRestarts"}


def record_proposal(
    investigation: Investigation,
    evidence: dict,
    repository: RemediationRepository,
    settings: Settings,
    now: datetime | None = None,
) -> Remediation | None:
    draft = propose(investigation, evidence, settings)
    if draft is None:
        return None
    existing = repository.latest_for(investigation.id, draft["action"], draft["target_name"])
    if existing is not None and not _noop_verified(existing):
        return None
    moment = now or datetime.now(timezone.utc)
    seq, remediation_id = repository.next_id()
    remediation = Remediation(
        id=remediation_id,
        investigation_id=investigation.id,
        created_at=moment,
        updated_at=moment,
        action=draft["action"],
        target_kind="Deployment",
        target_name=draft["target_name"],
        namespace=draft["namespace"],
        reason=draft["reason"],
        status="proposed",
        replicas=draft.get("replicas"),
        transitions=[TransitionItem(at=moment, status="proposed", reason=draft["reason"])],
    )
    return repository.insert(remediation, seq)


def propose(investigation: Investigation, evidence: dict, settings: Settings) -> dict | None:
    issue = investigation.detected_issue
    if issue in _INFORMATIONAL:
        return None
    target = evidence.get("deployment_name") or _deployment_from_evidence(investigation)
    if not target:
        return None
    namespace = evidence.get("namespace") or investigation.namespace or settings.namespace
    if namespace != settings.namespace:
        return None
    revision = _int(evidence.get("deployment_revision"))
    desired = evidence.get("deployment_desired")
    if issue == "UnavailableReplicas" and desired == 0:
        return {
            "action": "scale_deployment",
            "target_name": target,
            "namespace": namespace,
            "replicas": 1,
            "reason": "Deployment wants zero replicas. The bounded safe count for this lab is 1.",
        }
    if issue == "CrashLoopBackOff" and revision is not None and revision >= 2:
        return {
            "action": "rollback_deployment",
            "target_name": target,
            "namespace": namespace,
            "reason": "CrashLoopBackOff started on a newer Deployment revision.",
        }
    if issue in _RESTARTABLE:
        return {
            "action": "restart_deployment",
            "target_name": target,
            "namespace": namespace,
            "reason": "The Deployment is unhealthy and a rollout restart is the allowlisted action.",
        }
    return None


def _deployment_from_evidence(investigation: Investigation) -> str | None:
    for item in investigation.evidence:
        if item.label == "Deployment" and item.value:
            return item.value.split(" ready ", 1)[0].strip() or None
    return None


def _noop_verified(existing: Remediation) -> bool:
    """A verified record that did not change the Deployment can be replaced.

    Failed proposals stay put. A verified change also stays put.
    """
    if existing.status != "verified":
        return False
    before = existing.before_state.get("generation")
    after = existing.after_state.get("generation")
    if not isinstance(before, int) or isinstance(before, bool):
        return False
    if not isinstance(after, int) or isinstance(after, bool):
        return False
    return after <= before


def _int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
