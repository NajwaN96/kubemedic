"""Build the small JSON document an AI provider is allowed to see."""

import hashlib
import json

from app.config import Settings
from app.ai.sanitize import sanitize_payload
from app.investigation.models import Investigation


def evidence_signature(evidence: dict) -> str:
    """Identity of the evidence that justifies an AI call.

    Restart count and occurrence count are intentionally absent. A repeated
    poll of the same failure must not spend another request.
    """
    material = {
        "issue": evidence.get("detected_issue") or "",
        "exit_code": _text(evidence.get("exit_code")),
        "waiting_reason": evidence.get("waiting_reason") or "",
        "termination_reason": evidence.get("termination_reason") or "",
        "memory_limit": evidence.get("memory_limit") or "",
        "previous_logs": evidence.get("previous_logs") or "",
    }
    encoded = json.dumps(material, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def evidence_from_investigation(investigation: Investigation) -> dict:
    previous = ""
    current = ""
    for item in investigation.logs:
        if item.source == "previous":
            previous = item.content
        elif item.source == "current":
            current = item.content
    return {
        "detected_issue": investigation.detected_issue,
        "namespace": investigation.namespace,
        "resource_kind": investigation.resource_kind,
        "pod_phase": _evidence_value(investigation, "Pod phase"),
        "waiting_reason": _evidence_value(investigation, "Waiting reason"),
        "termination_reason": _evidence_value(investigation, "Termination reason"),
        "exit_code": _evidence_value(investigation, "Exit code"),
        "restart_count": _evidence_value(investigation, "Restart count"),
        "memory_limit": _evidence_value(investigation, "Memory limit"),
        "events": [item.model_dump() for item in investigation.events],
        "logs": current,
        "previous_logs": previous,
    }


def build_ai_payload(evidence: dict, investigation: Investigation, settings: Settings) -> dict:
    events = []
    for event in (evidence.get("events") or [])[: settings.ai_max_events]:
        if not isinstance(event, dict):
            continue
        events.append(
            {
                "reason": str(event.get("reason") or ""),
                "message": str(event.get("message") or ""),
                "count": event.get("count") or 1,
            }
        )
    logs = []
    for source, key in (("previous", "previous_logs"), ("current", "logs")):
        text = str(evidence.get(key) or "")
        if not text.strip():
            continue
        lines = text.splitlines()[: settings.ai_max_log_lines]
        logs.append({"source": source, "content": "\n".join(lines)})
    rule = investigation.rule_analysis
    payload = {
        "issue": evidence.get("detected_issue") or investigation.detected_issue,
        "severity": investigation.severity,
        "namespace": evidence.get("namespace") or investigation.namespace,
        "resource_kind": evidence.get("resource_kind") or investigation.resource_kind,
        "container_state": {
            "phase": evidence.get("pod_phase"),
            "waiting_reason": evidence.get("waiting_reason"),
            "termination_reason": evidence.get("termination_reason"),
        },
        "exit_code": _number(evidence.get("exit_code")),
        "restart_count": _number(evidence.get("restart_count")),
        "resource_limits": {"memory": evidence.get("memory_limit")},
        "recent_events": events,
        "recent_logs": logs,
        "rule_analysis": {
            "detected_issue": rule.detected_issue if rule else investigation.detected_issue,
            "summary": rule.summary if rule else investigation.summary,
            "likely_root_cause": rule.likely_root_cause if rule else investigation.likely_root_cause,
            "recommended_actions": list(
                rule.recommended_actions if rule else investigation.recommended_actions
            ),
        },
        "current_health": {"investigation_status": investigation.status},
    }
    cleaned = sanitize_payload(payload)
    if not isinstance(cleaned, dict):
        return {}
    return _fit(cleaned, settings.ai_max_payload_bytes)


def _fit(payload: dict, limit: int) -> dict:
    guard = 0
    while _size(payload) > limit and guard < 80:
        guard += 1
        logs = payload.get("recent_logs") or []
        if logs:
            content = str(logs[-1].get("content") or "")
            lines = content.splitlines()
            if len(lines) > 1:
                logs[-1]["content"] = "\n".join(lines[:-1])
            else:
                logs.pop()
            payload["recent_logs"] = logs
            payload["logs_truncated"] = True
            continue
        events = payload.get("recent_events") or []
        if events:
            events.pop()
            payload["recent_events"] = events
            payload["logs_truncated"] = True
            continue
        break
    return payload


def _size(payload: dict) -> int:
    return len(json.dumps(payload, default=str).encode())


def _evidence_value(investigation: Investigation, label: str) -> str | None:
    for item in investigation.evidence:
        if item.label == label:
            return item.value
    return None


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _number(value: object) -> object:
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return value
