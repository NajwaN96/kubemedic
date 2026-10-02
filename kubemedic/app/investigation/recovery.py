"""Decide when a detected issue has cleared.

These checks read the current snapshot only. They do not invent events.
A true result means the failure condition is absent right now.
"""

from app.investigation.collector import _database_text, _log_blobs


def recovery_signals(issue: str, snapshot: dict, container: str | None) -> tuple[bool, list[str]]:
    """Return whether the issue has cleared and which observed lines to record."""
    status = _container(snapshot, container)
    running = _running(status)
    ready = _ready(status, snapshot)
    waiting = _waiting(status)
    phase = ((snapshot.get("pod") or {}).get("status") or {}).get("phase")
    node_name = ((snapshot.get("pod") or {}).get("spec") or {}).get("nodeName")
    deployment = _deployment(snapshot)

    cleared = False
    if issue == "CrashLoopBackOff":
        cleared = running and ready and waiting != "CrashLoopBackOff"
    elif issue == "OOMKilled":
        cleared = running and ready and waiting not in {"OOMKilled", "CrashLoopBackOff"}
    elif issue in {"ImagePullBackOff", "ErrImagePull"}:
        cleared = running and waiting not in {"ImagePullBackOff", "ErrImagePull"}
    elif issue == "ReadinessProbeFailed":
        cleared = ready
    elif issue == "LivenessProbeFailed":
        cleared = running and ready
    elif issue == "UnavailableReplicas":
        cleared = bool(deployment) and deployment["desired"] > 0 and deployment["ready"] >= deployment["desired"]
    elif issue == "FailedScheduling":
        cleared = bool(node_name) and phase in {"Running", "Succeeded"}
    elif issue in {"CreateContainerConfigError", "CreateContainerError"}:
        cleared = running
    elif issue == "FailedMount":
        cleared = running and waiting != "FailedMount"
    elif issue == "DatabaseConnectivity":
        cleared = ready and running and not _current_database_failure(snapshot)
    elif issue == "RepeatedRestarts":
        cleared = running and ready
    else:
        cleared = running and ready

    if not cleared:
        return False, []

    lines: list[str] = []
    if running:
        lines.append("Container running")
    if ready:
        lines.append("Readiness restored")
    if issue == "FailedScheduling" and node_name:
        lines.append("Pod scheduled")
    if issue == "UnavailableReplicas" and deployment:
        lines.append("Deployment replicas are ready")
    return True, lines


def restart_count(snapshot: dict, container: str | None) -> int | None:
    status = _container(snapshot, container)
    if not status or status.get("restartCount") is None:
        return None
    return int(status.get("restartCount") or 0)


def _current_database_failure(snapshot: dict) -> bool:
    current, _previous = _log_blobs(snapshot.get("logs") or {})
    return _database_text(current)


def _container(snapshot: dict, name: str | None) -> dict | None:
    statuses = ((snapshot.get("pod") or {}).get("status") or {}).get("containerStatuses") or []
    if name:
        for status in statuses:
            if status.get("name") == name:
                return status
    return statuses[0] if statuses else None


def _running(status: dict | None) -> bool:
    if not status:
        return False
    return bool((status.get("state") or {}).get("running"))


def _ready(status: dict | None, snapshot: dict) -> bool:
    if status and status.get("ready") is True:
        return True
    for condition in ((snapshot.get("pod") or {}).get("status") or {}).get("conditions") or []:
        if condition.get("type") == "Ready" and str(condition.get("status")) == "True":
            return True
    return False


def _waiting(status: dict | None) -> str:
    if not status:
        return ""
    return ((status.get("state") or {}).get("waiting") or {}).get("reason") or ""


def _deployment(snapshot: dict) -> dict | None:
    raw = snapshot.get("deployment") or {}
    metadata = raw.get("metadata") or {}
    spec = raw.get("spec") or {}
    status = raw.get("status") or {}
    desired = spec.get("replicas")
    if not metadata.get("name") or desired is None:
        return None
    return {"desired": desired, "ready": status.get("readyReplicas") or 0}
