from datetime import datetime, timedelta, timezone

from app.demo import load_scenario, render
from app.investigation.repository import InvestigationRepository
from app.investigation.service import InvestigationService
from tests.snapshots import pod_snapshot


def test_ids_are_stable_across_repository_restart(settings, service):
    first, _snapshot = load_scenario("crashloop")
    crash = service.process_snapshot(_snapshot)
    image_title, image_snapshot = load_scenario("bad-image")
    image = service.process_snapshot(image_snapshot)
    assert crash.id == "INV-000001"
    assert image.id == "INV-000002"
    assert first == "CrashLoopBackOff"

    reopened = InvestigationService(InvestigationRepository(settings.db_path), settings)
    again = reopened.process_snapshot(pod_snapshot(waiting="FailedMount", events=[{"reason": "FailedMount", "message": "configmap missing", "type": "Warning", "count": 1}]))
    assert again.id == "INV-000003"
    assert reopened.get("INV-000001").detected_issue == "CrashLoopBackOff"


def test_duplicate_events_update_the_open_investigation(service):
    _title, snapshot = load_scenario("oom")
    start = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    first = service.process_snapshot(snapshot, now=start)
    second = service.process_snapshot(snapshot, now=start + timedelta(seconds=10))
    assert second.id == first.id
    assert second.occurrence_count == 2
    assert len(service.list_investigations()) == 1


def test_resolved_incident_reopens_inside_the_cooldown(service):
    _title, snapshot = load_scenario("readiness")
    start = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    first = service.process_snapshot(snapshot, now=start)
    service.resolve(first.id, now=start + timedelta(seconds=5))
    reopened = service.process_snapshot(snapshot, now=start + timedelta(seconds=30))
    assert reopened.id == first.id
    assert reopened.status == "open"
    assert reopened.occurrence_count == 2


def test_new_investigation_after_the_cooldown(service):
    _title, snapshot = load_scenario("database")
    start = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    first = service.process_snapshot(snapshot, now=start)
    service.resolve(first.id, now=start)
    later = service.process_snapshot(snapshot, now=start + timedelta(seconds=301))
    assert later.id == "INV-000002"
    assert later.occurrence_count == 1
    assert service.get("INV-000001").status == "resolved"


def test_open_investigation_is_updated_even_after_the_cooldown(service):
    snapshot = pod_snapshot(waiting="CrashLoopBackOff", restart_count=4, terminated_reason="Error", exit_code=1)
    start = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    first = service.process_snapshot(snapshot, now=start)
    later = service.process_snapshot(snapshot, now=start + timedelta(seconds=900))
    assert later.id == first.id
    assert later.occurrence_count == 2


def test_resolve_changes_only_the_investigation_record(service):
    _title, snapshot = load_scenario("missing-secret")
    created = service.process_snapshot(snapshot)
    resolved = service.resolve(created.id)
    assert resolved.status == "resolved"
    assert resolved.id == created.id
    assert service.get(created.id).status == "resolved"


def test_filters_and_analysis_source(service):
    for name in ("crashloop", "oom", "readiness"):
        _title, snapshot = load_scenario(name)
        service.process_snapshot(snapshot)
    highs = service.list_investigations(severity="high", status="open")
    assert {item.detected_issue for item in highs} == {"CrashLoopBackOff", "OOMKilled"}
    readiness = service.list_investigations(issue="ReadinessProbeFailed")
    assert len(readiness) == 1
    assert readiness[0].analysis_source == "rules"


def test_stale_liveness_event_does_not_keep_a_healthy_pod_open(service):
    start = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    event = {
        "type": "Warning",
        "reason": "Unhealthy",
        "message": "Liveness probe failed: connection refused",
        "count": 4,
        "lastTimestamp": "2026-09-30T12:00:00Z",
    }
    failing = pod_snapshot(name="taskflow-api-live", restart_count=2, events=[event])
    opened = service.process_snapshot(failing, now=start)
    assert opened.status == "open"
    assert opened.detected_issue == "LivenessProbeFailed"
    saved_event = opened.events[0].message

    healthy = pod_snapshot(name="taskflow-api-live", restart_count=2, desired=2, ready=2, events=[event])
    healthy["pod"]["status"]["containerStatuses"][0]["ready"] = True
    healthy["pod"]["status"]["conditions"] = [{"type": "Ready", "status": "True", "reason": "Ready"}]
    later = start + timedelta(seconds=301)
    assert service.process_snapshot(healthy, now=later) is None
    untouched = service.get(opened.id)
    assert untouched.status == "open"
    assert untouched.occurrence_count == 1
    assert untouched.events[0].message == saved_event

    recovering = service.observe_healthy(healthy, now=later)
    assert recovering.status == "recovering"
    assert recovering.resolved_at is None
    assert any(item.message == "Container running" for item in recovering.timeline)
    assert any(item.message == "Readiness restored" for item in recovering.timeline)
    assert recovering.events[0].message == saved_event

    resolved = service.observe_healthy(healthy, now=later + timedelta(seconds=60))
    assert resolved.id == opened.id
    assert resolved.status == "resolved"
    assert resolved.resolution_reason == "resource remained healthy through the stabilization window"
    assert resolved.recovery_duration_seconds is not None
    assert any(item.message == "Investigation resolved" for item in resolved.timeline)
    assert resolved.evidence
    assert resolved.events[0].message == saved_event


def test_crashloop_waits_for_stabilization_before_resolved(service):
    start = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    failing = pod_snapshot(waiting="CrashLoopBackOff", restart_count=4, terminated_reason="Error", exit_code=1, previous_log="exit 1\n")
    opened = service.process_snapshot(failing, now=start)
    assert any(item.message == "Previous logs collected" for item in opened.timeline)
    healthy = pod_snapshot(restart_count=4)
    healthy["pod"]["status"]["containerStatuses"][0]["ready"] = True
    healthy["pod"]["status"]["conditions"] = [{"type": "Ready", "status": "True"}]
    first = service.observe_healthy(healthy, now=start + timedelta(seconds=20))
    assert first.status == "recovering"
    second = service.observe_healthy(healthy, now=start + timedelta(seconds=40))
    assert second.status == "recovering"
    done = service.observe_healthy(healthy, now=start + timedelta(seconds=80))
    assert done.status == "resolved"
    assert done.id == opened.id


def test_restart_during_recovery_returns_the_incident_to_open(service):
    start = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    failing = pod_snapshot(waiting="CrashLoopBackOff", restart_count=4, terminated_reason="Error", exit_code=1)
    service.process_snapshot(failing, now=start)
    healthy = pod_snapshot(restart_count=4)
    healthy["pod"]["status"]["containerStatuses"][0]["ready"] = True
    healthy["pod"]["status"]["conditions"] = [{"type": "Ready", "status": "True"}]
    service.observe_healthy(healthy, now=start + timedelta(seconds=10))
    bounced = pod_snapshot(restart_count=5)
    bounced["pod"]["status"]["containerStatuses"][0]["ready"] = True
    bounced["pod"]["status"]["conditions"] = [{"type": "Ready", "status": "True"}]
    again = service.observe_healthy(bounced, now=start + timedelta(seconds=20))
    assert again.status == "open"
    assert any(item.message == "Container restarted during recovery" for item in again.timeline)


def test_demo_render_hides_the_database_password(service):
    title, snapshot = load_scenario("crashloop")
    investigation = service.process_snapshot(snapshot)
    text = render(title, investigation)
    assert "INV-000001" in text
    assert "Severity: HIGH" in text
    assert "Exit code: 1" in text
    assert "Restart count: 6" in text
    assert "Previous log: database connection refused" in text
    assert "super-secret-db-password" not in text
    assert "The API container repeatedly exits during startup." in text
