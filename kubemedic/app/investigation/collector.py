"""Turn a Kubernetes-shaped snapshot into one investigation finding.

Snapshots use the Kubernetes API JSON field names. The live watcher serializes
client objects to that shape before calling this module. Fixtures use the same
shape, so demo replay and a live watch share this code.
"""

from datetime import datetime, timezone

from app.redact import redact_text

# More specific failures beat generic restart noise.
_PRIORITY = [
    "CreateContainerConfigError",
    "CreateContainerError",
    "ImagePullBackOff",
    "ErrImagePull",
    "OOMKilled",
    "CrashLoopBackOff",
    "FailedMount",
    "FailedScheduling",
    "LivenessProbeFailed",
    "ReadinessProbeFailed",
    "DatabaseConnectivity",
    "RepeatedRestarts",
    "UnavailableReplicas",
]
_WAITING = {
    "CreateContainerConfigError",
    "CreateContainerError",
    "ImagePullBackOff",
    "ErrImagePull",
    "CrashLoopBackOff",
    "FailedMount",
}
_RESTART_THRESHOLD = 3


def collect_from_snapshot(
    snapshot: dict,
    log_tail_lines: int = 100,
    max_log_chars: int = 12000,
    now: datetime | None = None,
    event_freshness_seconds: int = 300,
) -> dict | None:
    """Return sanitized evidence for the highest-priority issue, or None.

    ``now`` is the live clock. When it is omitted, event timestamps are not
    aged out, so fixture replay stays stable. The watcher always passes ``now``.
    Stale events stay in the evidence list and do not create a finding by themselves.
    """
    pod = snapshot.get("pod") or {}
    events = [_event(item) for item in snapshot.get("events") or []]
    events = [item for item in events if item["message"] or item["reason"]]
    deployment = _deployment(snapshot.get("deployment"))
    logs_by_container = snapshot.get("logs") or {}

    candidates = _candidates(
        pod,
        events,
        logs_by_container,
        deployment,
        now=now,
        event_freshness_seconds=event_freshness_seconds,
    )
    if not candidates:
        return None
    issue = min(candidates, key=lambda item: _PRIORITY.index(item[0]) if item[0] in _PRIORITY else 99)
    detected_issue, container_status = issue
    metadata = pod.get("metadata") or {}
    spec = pod.get("spec") or {}
    status = pod.get("status") or {}
    container_name = (container_status or {}).get("name")
    container_spec = _container_spec(spec, container_name)
    current_logs, previous_logs = _logs_for(logs_by_container, container_name, log_tail_lines, max_log_chars)
    terminated = _terminated(container_status)
    waiting = ((container_status or {}).get("state") or {}).get("waiting") or {}
    event_text = "\n".join(item["message"] for item in events if item["message"])
    owners = metadata.get("ownerReferences") or []

    evidence = {
        "namespace": metadata.get("namespace") or snapshot.get("namespace") or "",
        "resource_kind": "Pod" if pod else "Deployment",
        "resource_name": metadata.get("name") or (deployment or {}).get("name") or "unknown",
        "container": container_name,
        "detected_issue": detected_issue,
        "pod_phase": status.get("phase"),
        "waiting_reason": waiting.get("reason"),
        "waiting_message": redact_text(waiting.get("message") or ""),
        "termination_reason": terminated.get("reason"),
        "exit_code": terminated.get("exitCode"),
        "restart_count": (container_status or {}).get("restartCount"),
        "image": (container_status or {}).get("image") or (container_spec or {}).get("image"),
        "image_id": (container_status or {}).get("imageID"),
        "node_name": spec.get("nodeName"),
        "memory_limit": _memory_limit(container_spec),
        "conditions": _conditions(status.get("conditions") or []),
        "owner_references": [
            {"kind": item.get("kind"), "name": item.get("name")}
            for item in owners
            if isinstance(item, dict)
        ],
        "deployment_name": (deployment or {}).get("name"),
        "deployment_desired": (deployment or {}).get("desired"),
        "deployment_ready": (deployment or {}).get("ready"),
        "deployment_revision": (deployment or {}).get("revision"),
        "events": events[:20],
        "event_text": redact_text(event_text)[:max_log_chars],
        "logs": current_logs,
        "previous_logs": previous_logs,
        "observed_at": (metadata.get("creationTimestamp") or ""),
    }
    if not pod and deployment:
        evidence["resource_kind"] = "Deployment"
        evidence["resource_name"] = deployment["name"]
        evidence["namespace"] = evidence["namespace"] or deployment.get("namespace") or ""
    return evidence


def _candidates(
    pod: dict,
    events: list[dict],
    logs: dict,
    deployment: dict | None,
    now: datetime | None = None,
    event_freshness_seconds: int = 300,
) -> list[tuple[str, dict | None]]:
    found: list[tuple[str, dict | None]] = []
    statuses = list((pod.get("status") or {}).get("containerStatuses") or [])
    statuses += list((pod.get("status") or {}).get("initContainerStatuses") or [])
    phase = (pod.get("status") or {}).get("phase")
    node_name = (pod.get("spec") or {}).get("nodeName")
    for status in statuses:
        state = status.get("state") or {}
        waiting_reason = (state.get("waiting") or {}).get("reason")
        if waiting_reason in _WAITING:
            found.append((waiting_reason, status))
        terminated = _terminated(status)
        if terminated.get("reason") == "OOMKilled" and not _healthy_container(status):
            found.append(("OOMKilled", status))
        restart_count = status.get("restartCount") or 0
        if restart_count >= _RESTART_THRESHOLD and not waiting_reason and not _healthy_container(status):
            found.append(("RepeatedRestarts", status))

    for event in events:
        if not _event_is_fresh(event, now, event_freshness_seconds):
            continue
        reason = event["reason"]
        message = event["message"]
        status = _status_for_message(statuses, message)
        if reason == "FailedScheduling" and (phase == "Pending" or not node_name):
            found.append(("FailedScheduling", status))
        elif reason == "FailedMount" and not _healthy_container(status or {}):
            found.append(("FailedMount", status))
        elif reason == "Unhealthy" and "Liveness probe" in message and not _healthy_container(status or {}):
            found.append(("LivenessProbeFailed", status))
        elif (
            reason == "Unhealthy"
            and "Readiness probe" in message
            and (status or {}).get("ready") is not True
            and not _pod_ready(pod)
        ):
            found.append(("ReadinessProbeFailed", status))

    current_blob, previous_blob = _log_blobs(logs)
    database_blob = current_blob if _pod_is_serving(pod) else f"{current_blob}\n{previous_blob}"
    if _database_text(database_blob) and not _has_higher(found, "DatabaseConnectivity"):
        container = statuses[0] if statuses else None
        if not any(issue != "RepeatedRestarts" for issue, _status in found):
            found.append(("DatabaseConnectivity", container))
        elif not found:
            found.append(("DatabaseConnectivity", container))

    if (
        deployment
        and deployment["desired"] > 0
        and deployment["ready"] < deployment["desired"]
        and not found
    ):
        found.append(("UnavailableReplicas", None))

    # Database signals on an otherwise running pod with no stronger container failure.
    if _database_text(database_blob) and not any(issue in _PRIORITY[:10] for issue, _status in found):
        if not any(issue == "DatabaseConnectivity" for issue, _status in found):
            found.append(("DatabaseConnectivity", statuses[0] if statuses else None))
    return found


def _healthy_container(status: dict) -> bool:
    state = status.get("state") or {}
    return bool(state.get("running")) and status.get("ready") is True


def _pod_ready(pod: dict) -> bool:
    for condition in (pod.get("status") or {}).get("conditions") or []:
        if condition.get("type") == "Ready" and str(condition.get("status")) == "True":
            return True
    return False


def _pod_is_serving(pod: dict) -> bool:
    statuses = (pod.get("status") or {}).get("containerStatuses") or []
    if not statuses or not all(_healthy_container(status) for status in statuses):
        return False
    return _pod_ready(pod) or all(status.get("ready") is True for status in statuses)


def _event_is_fresh(event: dict, now: datetime | None, freshness_seconds: int) -> bool:
    if now is None:
        return True
    raw = event.get("timestamp")
    if not raw:
        return True
    stamp = _parse_time(str(raw))
    if stamp is None:
        return True
    current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    return (current - stamp).total_seconds() <= freshness_seconds


def _parse_time(value: str) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def _log_blobs(logs: dict) -> tuple[str, str]:
    current_parts: list[str] = []
    previous_parts: list[str] = []
    for item in logs.values():
        if not isinstance(item, dict):
            continue
        current_parts.append(item.get("current") or "")
        previous_parts.append(item.get("previous") or "")
    return "\n".join(current_parts), "\n".join(previous_parts)


def _has_higher(found: list[tuple[str, dict | None]], issue: str) -> bool:
    rank = _PRIORITY.index(issue)
    return any(_PRIORITY.index(name) < rank for name, _status in found if name in _PRIORITY)


def _database_text(logs: str) -> bool:
    text = logs.lower()
    mentions = any(token in text for token in ("postgres", "database", "psycopg", "sqlalchemy"))
    failed = any(
        token in text
        for token in ("connection refused", "could not connect", "connection timeout", "operationalerror")
    )
    return bool(text.strip()) and mentions and failed


def _terminated(status: dict | None) -> dict:
    if not status:
        return {}
    state = status.get("state") or {}
    current = state.get("terminated") or {}
    last = (status.get("lastState") or {}).get("terminated") or {}
    if last.get("reason") == "OOMKilled":
        return last
    return last or current


def _container_spec(spec: dict, name: str | None) -> dict | None:
    containers = list(spec.get("containers") or []) + list(spec.get("initContainers") or [])
    if name:
        for container in containers:
            if container.get("name") == name:
                return container
    return containers[0] if containers else None


def _memory_limit(container: dict | None) -> str | None:
    if not container:
        return None
    limits = ((container.get("resources") or {}).get("limits") or {})
    return limits.get("memory")


def _conditions(raw: list) -> list[dict]:
    cleaned = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        cleaned.append(
            {
                "type": item.get("type"),
                "status": item.get("status"),
                "reason": item.get("reason"),
                "message": redact_text(item.get("message") or ""),
            }
        )
    return cleaned


def _event(raw: dict) -> dict:
    if not isinstance(raw, dict):
        return {"type": "Warning", "reason": "", "message": "", "count": 1, "timestamp": None}
    metadata = raw.get("metadata") or {}
    return {
        "type": raw.get("type") or "Warning",
        "reason": raw.get("reason") or "",
        "message": redact_text(raw.get("message") or ""),
        "count": int(raw.get("count") or 1),
        "timestamp": raw.get("lastTimestamp") or raw.get("eventTime") or metadata.get("creationTimestamp"),
    }


def _deployment(raw: dict | None) -> dict | None:
    if not raw:
        return None
    metadata = raw.get("metadata") or {}
    spec = raw.get("spec") or {}
    status = raw.get("status") or {}
    desired = spec.get("replicas")
    ready = status.get("readyReplicas") or 0
    if desired is None:
        return None
    revision_raw = (metadata.get("annotations") or {}).get("deployment.kubernetes.io/revision")
    revision = int(revision_raw) if str(revision_raw or "").isdigit() else None
    return {
        "name": metadata.get("name"),
        "namespace": metadata.get("namespace"),
        "desired": desired,
        "ready": ready,
        "revision": revision,
    }


def _logs_for(logs: dict, container: str | None, tail_lines: int, max_chars: int) -> tuple[str, str]:
    selected = {}
    if container and isinstance(logs.get(container), dict):
        selected = logs[container]
    elif len(logs) == 1:
        only = next(iter(logs.values()))
        selected = only if isinstance(only, dict) else {}
    current = _tail(selected.get("current") or "", tail_lines, max_chars)
    previous = _tail(selected.get("previous") or "", tail_lines, max_chars)
    return redact_text(current), redact_text(previous)


def _tail(text: str, lines: int, max_chars: int) -> str:
    if not text:
        return ""
    kept = "\n".join(text.splitlines()[-lines:])
    if len(kept) > max_chars:
        kept = "…\n" + kept[-max_chars:]
    return kept


def _status_for_message(statuses: list[dict], message: str) -> dict | None:
    for status in statuses:
        name = status.get("name") or ""
        if name and name in message:
            return status
    return statuses[0] if statuses else None
