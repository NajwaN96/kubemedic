"""Create and update investigations. This module does not call Kubernetes.

Optional AI analysis is delegated to the AI coordinator. Rule fields stay
the authoritative record when that call is skipped or fails.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from app.ai.coordinator import AICoordinator
from app.ai.errors import AIDisabledError
from app.ai.payload import build_ai_payload, evidence_from_investigation, evidence_signature
from app.config import Settings
from app.investigation.analyzer import analyze
from app.investigation.collector import collect_from_snapshot
from app.investigation.models import EventItem, EvidenceItem, Investigation, LogItem, RuleAnalysis, TimelineItem, TransitionItem
from app.investigation.recovery import recovery_signals, restart_count
from app.investigation.repository import InvestigationRepository

logger = logging.getLogger(__name__)

_REPLACEMENT_REASON = "affected Pod was replaced and owning workload is healthy"
_REMOVED_REASON = "affected resource no longer exists"

_RESTART_ISSUES = {"CrashLoopBackOff", "OOMKilled"}


class InvestigationService:
    def __init__(
        self,
        repository: InvestigationRepository,
        settings: Settings,
        ai: AICoordinator | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.ai = ai if ai is not None else AICoordinator(settings, repository)
        from app.remediation.repository import RemediationRepository

        self.remediations = RemediationRepository(settings.db_path)

    def process_snapshot(self, snapshot: dict, now: datetime | None = None) -> Investigation | None:
        moment = _aware(now or datetime.now(timezone.utc))
        evidence = collect_from_snapshot(
            snapshot,
            log_tail_lines=self.settings.log_tail_lines,
            max_log_chars=self.settings.max_log_chars,
            now=now,
            event_freshness_seconds=self.settings.event_freshness_seconds,
        )
        if evidence is None:
            return None
        return self.ingest(evidence, now=moment)

    def observe_healthy(
        self,
        snapshot: dict,
        now: datetime | None = None,
        active: Investigation | None = None,
    ) -> Investigation | None:
        """Advance open incidents whose current resource no longer shows the failure."""
        moment = _aware(now or datetime.now(timezone.utc))
        updated: Investigation | None = None
        for namespace, kind, name in _identities(snapshot):
            for current in self.repository.find_active(namespace, kind, name):
                if _same_failure(current, active):
                    continue
                cleared, lines = recovery_signals(current.detected_issue, snapshot, current.container)
                if not cleared:
                    continue
                updated = self._advance_recovery(current, snapshot, lines, moment)
        return updated

    def ingest(self, evidence: dict, now: datetime | None = None) -> Investigation:
        moment = _aware(now or datetime.now(timezone.utc))
        finding = analyze(evidence)
        fingerprint = _fingerprint(evidence)
        current = self._match(fingerprint, moment)
        items = _evidence_items(evidence)
        events = [EventItem(**item) for item in evidence.get("events") or []]
        logs = _log_items(evidence)
        if current is None:
            seq, investigation_id = self.repository.next_id()
            investigation = Investigation(
                id=investigation_id,
                created_at=moment,
                updated_at=moment,
                namespace=evidence.get("namespace") or self.settings.namespace,
                resource_kind=evidence["resource_kind"],
                resource_name=evidence["resource_name"],
                container=evidence.get("container"),
                severity=finding.severity,
                status="open",
                detected_issue=finding.detected_issue,
                summary=finding.summary,
                likely_root_cause=finding.likely_root_cause,
                evidence=items,
                events=events,
                logs=logs,
                recommended_actions=finding.recommended_actions,
                timeline=_detection_timeline(moment, finding.detected_issue, logs),
                transitions=[TransitionItem(at=moment, status="open", reason="Failure detected")],
                occurrence_count=1,
                analysis_source="rules",
                rule_analysis=_rule_snapshot(finding),
                last_failure_seen_at=moment,
                fingerprint=fingerprint,
            )
            saved = self.repository.insert(investigation, seq)
            saved = self._attach_ai(saved, evidence, moment)
            self._maybe_propose(saved, evidence)
            return saved

        returning = current.status != "open"
        preserved_source = current.analysis_source if current.ai_status == "ok" else "rules"
        current.updated_at = moment
        current.severity = finding.severity
        current.status = "open"
        current.summary = finding.summary
        current.likely_root_cause = finding.likely_root_cause
        current.evidence = items
        current.events = events
        current.logs = logs
        current.recommended_actions = finding.recommended_actions
        current.rule_analysis = _rule_snapshot(finding)
        current.occurrence_count += 1
        current.analysis_source = preserved_source
        current.last_failure_seen_at = moment
        if returning:
            current.last_healthy_seen_at = None
            current.stable_restart_count = None
            current.resolved_at = None
            current.resolution_reason = None
            current.recovery_duration_seconds = None
            _append_timeline(current, moment, "Failure detected")
            _append_timeline(current, moment, f"{finding.detected_issue} observed")
            _append_log_timeline(current, moment, logs)
            current.transitions.append(TransitionItem(at=moment, status="open", reason="Failure detected"))
        saved = self.repository.update(current)
        saved = self._attach_ai(saved, evidence, moment)
        self._maybe_propose(saved, evidence)
        return saved

    def list_investigations(
        self,
        status: str | None = None,
        severity: str | None = None,
        issue: str | None = None,
    ) -> list[Investigation]:
        return self.repository.list_investigations(status=status, severity=severity, issue=issue)

    def get(self, investigation_id: str) -> Investigation | None:
        return self.repository.get(investigation_id)

    def reconcile_absent(
        self,
        namespace: str,
        present_pods: set[str],
        deployments: list[dict],
        now: datetime | None = None,
    ) -> list[Investigation]:
        """Advance active investigations whose Kubernetes object is gone.

        A missing Pod is not treated as a repair. A healthy owning Deployment
        starts the normal stabilization window. An unmanaged Pod is closed
        because the resource was removed. A degraded Deployment stays open.
        """
        moment = _aware(now or datetime.now(timezone.utc))
        by_name = {}
        for deployment in deployments:
            name = (deployment.get("metadata") or {}).get("name")
            if name:
                by_name[name] = deployment
        updated: list[Investigation] = []
        for current in self.repository.list_active(namespace):
            if current.resource_kind == "Pod":
                if current.resource_name in present_pods:
                    continue
                owner = _owning_deployment(current)
                if owner and owner in by_name and _deployment_healthy(by_name[owner]):
                    updated.append(self._advance_replacement(current, moment))
                elif owner and owner in by_name:
                    updated.append(self._note_degraded_absence(current, moment))
                else:
                    updated.append(self._resolve_removed(current, moment))
            elif current.resource_kind == "Deployment":
                if current.resource_name in by_name:
                    continue
                updated.append(self._resolve_removed(current, moment))
        return updated

    def analyze_with_ai(self, investigation_id: str, now: datetime | None = None) -> Investigation | None:
        if not self.ai.enabled:
            raise AIDisabledError()
        current = self.repository.get(investigation_id)
        if current is None:
            return None
        moment = _aware(now or datetime.now(timezone.utc))
        evidence = evidence_from_investigation(current)
        payload = build_ai_payload(evidence, current, self.settings)
        _log_ai_request(self.settings, payload)
        outcome = self.ai.run(payload)
        self._apply_ai(current, outcome, evidence_signature(evidence), moment)
        return self.repository.update(current)

    def resolve(self, investigation_id: str, now: datetime | None = None) -> Investigation | None:
        current = self.repository.get(investigation_id)
        if current is None:
            return None
        moment = _aware(now or datetime.now(timezone.utc))
        _mark_resolved(current, moment, "resolved by operator")
        return self.repository.update(current)

    def _advance_recovery(
        self,
        current: Investigation,
        snapshot: dict,
        lines: list[str],
        moment: datetime,
    ) -> Investigation:
        restarts = restart_count(snapshot, current.container)
        if (
            current.status == "recovering"
            and current.detected_issue in _RESTART_ISSUES
            and current.stable_restart_count is not None
            and restarts is not None
            and restarts > current.stable_restart_count
        ):
            current.status = "open"
            current.updated_at = moment
            current.last_failure_seen_at = moment
            current.last_healthy_seen_at = None
            current.stable_restart_count = None
            _append_timeline(current, moment, "Failure detected")
            _append_timeline(current, moment, "Container restarted during recovery")
            current.transitions.append(TransitionItem(at=moment, status="open", reason="Container restarted during recovery"))
            return self.repository.update(current)

        current.updated_at = moment
        for line in lines:
            _append_timeline(current, moment, line)
        if current.status == "open":
            current.status = "recovering"
            current.last_healthy_seen_at = moment
            current.stable_restart_count = restarts
            current.transitions.append(
                TransitionItem(at=moment, status="recovering", reason="Current resource is healthy")
            )
            return self.repository.update(current)

        started = _aware(current.last_healthy_seen_at or moment)
        window = timedelta(seconds=self.settings.recovery_stabilization_seconds)
        if moment > started and moment - started >= window:
            _mark_resolved(current, moment, "resource remained healthy through the stabilization window")
        return self.repository.update(current)

    def _advance_replacement(self, current: Investigation, moment: datetime) -> Investigation:
        current.updated_at = moment
        _append_timeline(current, moment, "Affected Pod no longer exists")
        _append_timeline(current, moment, "Owning workload is healthy")
        if current.status == "open":
            current.status = "recovering"
            current.last_healthy_seen_at = moment
            current.transitions.append(
                TransitionItem(at=moment, status="recovering", reason=_REPLACEMENT_REASON)
            )
            return self.repository.update(current)
        started = _aware(current.last_healthy_seen_at or moment)
        window = timedelta(seconds=self.settings.recovery_stabilization_seconds)
        if moment > started and moment - started >= window:
            _mark_resolved(current, moment, _REPLACEMENT_REASON)
        return self.repository.update(current)

    def _note_degraded_absence(self, current: Investigation, moment: datetime) -> Investigation:
        previous_status = current.status
        previous_lines = len(current.timeline)
        previous_transitions = len(current.transitions)
        _append_timeline(current, moment, "Affected Pod no longer exists")
        if current.status == "recovering":
            current.status = "open"
            current.last_healthy_seen_at = None
            current.stable_restart_count = None
            _append_timeline(current, moment, "Owning workload is still degraded")
            current.transitions.append(
                TransitionItem(at=moment, status="open", reason="Owning workload is still degraded")
            )
        else:
            _append_timeline(current, moment, "Owning workload is still degraded")
        if (
            current.status == previous_status
            and len(current.timeline) == previous_lines
            and len(current.transitions) == previous_transitions
        ):
            return current
        current.updated_at = moment
        return self.repository.update(current)

    def _resolve_removed(self, current: Investigation, moment: datetime) -> Investigation:
        _append_timeline(current, moment, "Affected resource no longer exists")
        _mark_resolved(current, moment, _REMOVED_REASON)
        return self.repository.update(current)

    def _maybe_propose(self, investigation: Investigation, evidence: dict) -> None:
        try:
            from app.remediation.proposals import record_proposal

            record_proposal(investigation, evidence, self.remediations, self.settings)
        except Exception:
            logger.exception("Remediation proposal was not stored. The investigation is unchanged.")

    def _attach_ai(self, investigation: Investigation, evidence: dict, moment: datetime) -> Investigation:
        if not self.ai.enabled:
            return investigation
        signature = evidence_signature(evidence)
        if investigation.ai_input_signature and investigation.ai_input_signature == signature and investigation.ai_status:
            return investigation
        payload = build_ai_payload(evidence, investigation, self.settings)
        _log_ai_request(self.settings, payload)
        outcome = self.ai.run(payload)
        self._apply_ai(investigation, outcome, signature, moment)
        return self.repository.update(investigation)

    def _apply_ai(self, current: Investigation, outcome, signature: str, moment: datetime) -> None:
        had_success = current.ai_status == "ok" and current.ai_analysis is not None
        current.ai_input_signature = signature
        current.ai_provider = outcome.provider
        current.ai_model = outcome.model
        current.ai_analyzed_at = moment
        current.updated_at = moment
        if outcome.status == "ok" and outcome.analysis is not None:
            current.ai_analysis = outcome.analysis
            current.ai_status = "ok"
            current.analysis_source = "rules+ai"
            return
        if had_success:
            return
        current.ai_status = outcome.status
        current.analysis_source = "rules"

    def _match(self, fingerprint: str, moment: datetime) -> Investigation | None:
        open_match = self.repository.find_open(fingerprint)
        if open_match is not None:
            return open_match
        latest = self.repository.find_latest(fingerprint)
        if latest is None:
            return None
        updated = _aware(latest.updated_at)
        window = timedelta(seconds=self.settings.incident_cooldown_seconds)
        if moment - updated <= window:
            return latest
        return None


def _rule_snapshot(finding) -> RuleAnalysis:
    return RuleAnalysis(
        detected_issue=finding.detected_issue,
        summary=finding.summary,
        likely_root_cause=finding.likely_root_cause,
        recommended_actions=list(finding.recommended_actions),
        severity=finding.severity,
    )


def _owning_deployment(investigation: Investigation) -> str | None:
    for item in investigation.evidence:
        if item.label == "Deployment" and item.value:
            name = item.value.split(" ready ", 1)[0].strip()
            if name:
                return name
        if item.label == "Owner" and item.value.startswith("Deployment "):
            name = item.value[len("Deployment ") :].strip()
            if name:
                return name
    return None


def _deployment_healthy(deployment: dict) -> bool:
    desired = (deployment.get("spec") or {}).get("replicas") or 0
    ready = (deployment.get("status") or {}).get("readyReplicas") or 0
    try:
        return int(desired) > 0 and int(ready) >= int(desired)
    except (TypeError, ValueError):
        return False


def _log_ai_request(settings: Settings, payload: dict) -> None:
    log_lines = 0
    for item in payload.get("recent_logs") or []:
        log_lines += len(str(item.get("content") or "").splitlines())
    logger.info(
        "AI analysis request provider=%s model=%s bytes=%s events=%s log_lines=%s",
        settings.ai_provider,
        settings.openai_model,
        len(json.dumps(payload, default=str).encode()),
        len(payload.get("recent_events") or []),
        log_lines,
    )


def _mark_resolved(current: Investigation, moment: datetime, reason: str) -> None:
    current.status = "resolved"
    current.updated_at = moment
    current.resolved_at = moment
    current.resolution_reason = reason
    anchor = _aware(current.last_failure_seen_at or current.created_at)
    current.recovery_duration_seconds = max(0, int((moment - anchor).total_seconds()))
    _append_timeline(current, moment, "Investigation resolved")
    current.transitions.append(TransitionItem(at=moment, status="resolved", reason=reason))


def _same_failure(current: Investigation, active: Investigation | None) -> bool:
    if active is None:
        return False
    return (
        current.detected_issue == active.detected_issue
        and (current.container or "") == (active.container or "")
        and current.resource_name == active.resource_name
    )


def _identities(snapshot: dict) -> list[tuple[str, str, str]]:
    namespace = snapshot.get("namespace") or ""
    found: list[tuple[str, str, str]] = []
    pod = (snapshot.get("pod") or {}).get("metadata") or {}
    if pod.get("name"):
        found.append((pod.get("namespace") or namespace, "Pod", pod["name"]))
    deployment = (snapshot.get("deployment") or {}).get("metadata") or {}
    if deployment.get("name"):
        found.append((deployment.get("namespace") or namespace, "Deployment", deployment["name"]))
    return found


def _detection_timeline(moment: datetime, issue: str, logs: list[LogItem]) -> list[TimelineItem]:
    items = [
        TimelineItem(at=moment, message="Failure detected"),
        TimelineItem(at=moment, message=f"{issue} observed"),
    ]
    if any(item.source == "previous" and item.content for item in logs):
        items.append(TimelineItem(at=moment, message="Previous logs collected"))
    if any(item.source == "current" and item.content for item in logs):
        items.append(TimelineItem(at=moment, message="Current logs collected"))
    return items


def _append_log_timeline(current: Investigation, moment: datetime, logs: list[LogItem]) -> None:
    if any(item.source == "previous" and item.content for item in logs):
        _append_timeline(current, moment, "Previous logs collected")
    if any(item.source == "current" and item.content for item in logs):
        _append_timeline(current, moment, "Current logs collected")


def _append_timeline(current: Investigation, moment: datetime, message: str) -> None:
    anchor = _aware(current.last_failure_seen_at or current.created_at)
    for item in current.timeline:
        if item.message == message and _aware(item.at) >= anchor:
            return
    current.timeline.append(TimelineItem(at=moment, message=message))


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _fingerprint(evidence: dict) -> str:
    container = evidence.get("container") or ""
    return "|".join(
        [
            evidence.get("namespace") or "",
            evidence.get("resource_kind") or "",
            evidence.get("resource_name") or "",
            evidence.get("detected_issue") or "",
            container,
        ]
    )


def _evidence_items(evidence: dict) -> list[EvidenceItem]:
    rows: list[EvidenceItem] = []

    def add(label: str, value: object) -> None:
        if value is None or value == "":
            return
        rows.append(EvidenceItem(label=label, value=str(value)))

    add("Pod phase", evidence.get("pod_phase"))
    add("Waiting reason", evidence.get("waiting_reason"))
    add("Termination reason", evidence.get("termination_reason"))
    add("Exit code", evidence.get("exit_code"))
    add("Restart count", evidence.get("restart_count"))
    add("Image", evidence.get("image"))
    add("Image ID", evidence.get("image_id"))
    add("Memory limit", evidence.get("memory_limit"))
    add("Node", evidence.get("node_name"))
    if evidence.get("deployment_name"):
        add(
            "Deployment",
            f"{evidence['deployment_name']} ready {evidence.get('deployment_ready')}/{evidence.get('deployment_desired')}",
        )
    for owner in evidence.get("owner_references") or []:
        if owner.get("kind") and owner.get("name"):
            add("Owner", f"{owner['kind']} {owner['name']}")
    return rows


def _log_items(evidence: dict) -> list[LogItem]:
    items: list[LogItem] = []
    if evidence.get("previous_logs"):
        items.append(LogItem(source="previous", content=evidence["previous_logs"]))
    if evidence.get("logs"):
        items.append(LogItem(source="current", content=evidence["logs"]))
    return items
