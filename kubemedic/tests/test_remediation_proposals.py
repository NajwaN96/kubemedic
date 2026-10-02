from datetime import datetime, timedelta, timezone

from app.investigation.models import EvidenceItem, Investigation
from app.remediation.proposals import propose, record_proposal
from app.remediation.repository import RemediationRepository
from tests.snapshots import pod_snapshot

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _investigation(issue: str) -> Investigation:
    return Investigation(
        id="INV-000019",
        created_at=NOW,
        updated_at=NOW,
        namespace="taskflow",
        resource_kind="Pod",
        resource_name="taskflow-api-abc",
        severity="high",
        status="open",
        detected_issue=issue,
        summary="summary",
        likely_root_cause="cause",
        evidence=[EvidenceItem(label="Deployment", value="taskflow-api ready 0/2")],
    )


def _evidence(**extra):
    payload = {"namespace": "taskflow", "deployment_name": "taskflow-api", "deployment_desired": 2}
    payload.update(extra)
    return payload


def test_informational_issues_do_not_propose_mutation(settings):
    issues = [
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
    ]
    for issue in issues:
        assert propose(_investigation(issue), _evidence(), settings) is None


def test_crashloop_revision_chooses_rollback_or_restart(settings):
    rollback = propose(_investigation("CrashLoopBackOff"), _evidence(deployment_revision=2), settings)
    assert rollback["action"] == "rollback_deployment"
    restart = propose(_investigation("CrashLoopBackOff"), _evidence(deployment_revision=1), settings)
    assert restart["action"] == "restart_deployment"
    missing = propose(_investigation("CrashLoopBackOff"), _evidence(), settings)
    assert missing["action"] == "restart_deployment"


def test_zero_replicas_scales_to_the_bounded_safe_count(settings):
    draft = propose(
        _investigation("UnavailableReplicas"),
        _evidence(deployment_desired=0),
        settings,
    )
    assert draft["action"] == "scale_deployment"
    assert draft["replicas"] == 1


def test_ai_text_is_not_an_executable_action(settings):
    evidence = _evidence(deployment_revision=3, ai_command="kubectl delete namespace taskflow")
    draft = propose(_investigation("CrashLoopBackOff"), evidence, settings)
    assert draft["action"] == "rollback_deployment"
    assert "kubectl" not in draft["action"]


def test_verified_noop_can_be_proposed_again_and_a_failure_cannot(settings):
    repository = RemediationRepository(settings.db_path)
    investigation = _investigation("CrashLoopBackOff")
    evidence = _evidence(deployment_revision=3)
    first = record_proposal(investigation, evidence, repository, settings, now=NOW)
    first.status = "verified"
    first.before_state = {"generation": 3}
    first.after_state = {"generation": 3}
    repository.update(first)
    second = record_proposal(investigation, evidence, repository, settings, now=NOW + timedelta(seconds=30))
    assert second is not None
    assert second.id == "REM-000002"
    second.status = "failed"
    repository.update(second)
    assert record_proposal(investigation, evidence, repository, settings, now=NOW + timedelta(seconds=40)) is None


def test_duplicate_polls_do_not_duplicate_proposals(settings):
    repository = RemediationRepository(settings.db_path)
    investigation = _investigation("CrashLoopBackOff")
    evidence = _evidence(deployment_revision=3)
    first = record_proposal(investigation, evidence, repository, settings, now=NOW)
    second = record_proposal(investigation, evidence, repository, settings, now=NOW + timedelta(seconds=15))
    assert first is not None
    assert second is None
    assert [item.id for item in repository.list_remediations()] == ["REM-000001"]


def test_live_snapshot_records_one_rollback_proposal(service):
    snapshot = pod_snapshot(waiting="CrashLoopBackOff", restart_count=4, terminated_reason="Error", exit_code=1)
    snapshot["deployment"]["metadata"]["annotations"] = {"deployment.kubernetes.io/revision": "3"}
    service.process_snapshot(snapshot, now=NOW)
    service.process_snapshot(snapshot, now=NOW + timedelta(seconds=15))
    rows = service.remediations.list_remediations()
    assert len(rows) == 1
    assert rows[0].action == "rollback_deployment"
    assert rows[0].status == "proposed"
    assert rows[0].investigation_id == "INV-000001"


def test_image_pull_snapshot_stays_informational(service):
    snapshot = pod_snapshot(waiting="ImagePullBackOff", waiting_message="failed to resolve reference")
    service.process_snapshot(snapshot, now=NOW)
    assert service.remediations.list_remediations() == []
