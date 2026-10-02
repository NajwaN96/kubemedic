import pytest

from app.demo import load_scenario
from app.investigation.analyzer import analyze
from app.investigation.collector import collect_from_snapshot
from tests.snapshots import pod_snapshot


def _finding(snapshot, **limits):
    evidence = collect_from_snapshot(snapshot, **limits)
    assert evidence is not None
    return analyze(evidence), evidence


@pytest.mark.parametrize(
    ("scenario", "issue", "severity"),
    [
        ("crashloop", "CrashLoopBackOff", "high"),
        ("bad-image", "ImagePullBackOff", "high"),
        ("oom", "OOMKilled", "high"),
        ("missing-secret", "CreateContainerConfigError", "high"),
        ("failed-scheduling", "FailedScheduling", "medium"),
        ("readiness", "ReadinessProbeFailed", "medium"),
        ("database", "DatabaseConnectivity", "high"),
    ],
)
def test_fixture_classification(scenario, issue, severity):
    _title, snapshot = load_scenario(scenario)
    finding, evidence = _finding(snapshot)
    assert finding.detected_issue == issue
    assert finding.severity == severity
    assert evidence["namespace"] == "taskflow"
    blob = str(evidence)
    assert "super-secret-db-password" not in blob
    assert "demo-only-password" not in blob
    assert "demo-token-should-not-leak" not in blob


def test_crashloop_explains_startup_and_database_evidence():
    _title, snapshot = load_scenario("crashloop")
    finding, evidence = _finding(snapshot)
    assert finding.likely_root_cause == "The API container repeatedly exits during startup."
    assert evidence["exit_code"] == 1
    assert evidence["restart_count"] == 6
    assert evidence["previous_logs"].splitlines()[0] == "database connection refused"
    assert any("PostgreSQL" in action for action in finding.recommended_actions)
    assert any("hostname" in action for action in finding.recommended_actions)
    assert any("previous container logs" in action for action in finding.recommended_actions)


def test_crashloop_with_database_logs_stays_crashloop():
    snapshot = pod_snapshot(
        waiting="CrashLoopBackOff",
        terminated_reason="Error",
        exit_code=1,
        restart_count=4,
        previous_log="psycopg.OperationalError: database connection refused\n",
    )
    finding, _evidence = _finding(snapshot)
    assert finding.detected_issue == "CrashLoopBackOff"


def test_image_pull_categories():
    missing = pod_snapshot(
        waiting="ErrImagePull",
        waiting_message="failed to resolve reference: not found",
        image="taskflow-api:missing",
    )
    denied = pod_snapshot(
        waiting="ImagePullBackOff",
        waiting_message="unauthorized: authentication required",
        events=[{"type": "Warning", "reason": "Failed", "message": "unauthorized: authentication required", "count": 1}],
    )
    offline = pod_snapshot(
        waiting="ImagePullBackOff",
        waiting_message="dial tcp 10.0.0.8:443: i/o timeout",
    )
    unresolved_host = pod_snapshot(
        waiting="ImagePullBackOff",
        waiting_message=(
            'failed to resolve reference "example.invalid/taskflow:missing": '
            "dial tcp: lookup example.invalid: no such host"
        ),
        events=[
            {
                "type": "Warning",
                "reason": "Failed",
                "message": (
                    'Failed to pull image "example.invalid/taskflow:missing": '
                    'failed to resolve reference "example.invalid/taskflow:missing": '
                    "dial tcp: lookup example.invalid: no such host"
                ),
                "count": 1,
            }
        ],
    )
    assert _finding(missing)[0].likely_root_cause.startswith("The image name or tag")
    assert "registry" in _finding(denied)[0].likely_root_cause
    assert "reach the image registry" in _finding(offline)[0].likely_root_cause
    assert "reach the image registry" in _finding(unresolved_host)[0].likely_root_cause


def test_oom_does_not_only_recommend_raising_memory():
    snapshot = pod_snapshot(
        waiting="CrashLoopBackOff",
        terminated_reason="OOMKilled",
        exit_code=137,
        restart_count=3,
        memory="256Mi",
    )
    finding, evidence = _finding(snapshot)
    assert finding.detected_issue == "OOMKilled"
    assert evidence["memory_limit"] == "256Mi"
    assert evidence["exit_code"] == 137
    joined = " ".join(finding.recommended_actions).lower()
    assert "memory" in joined
    assert "not the whole fix" in joined


def test_missing_configmap_from_event_text():
    snapshot = pod_snapshot(
        waiting="CreateContainerConfigError",
        waiting_message='configmap "taskflow-api-config" not found',
        events=[
            {
                "type": "Warning",
                "reason": "Failed",
                "message": 'Error: configmap "taskflow-api-config" not found',
                "count": 2,
            }
        ],
    )
    finding, _evidence = _finding(snapshot)
    assert finding.detected_issue == "CreateContainerConfigError"
    assert "ConfigMap" in finding.likely_root_cause


def test_failed_mount_uses_the_event():
    snapshot = pod_snapshot(
        phase="Pending",
        events=[
            {
                "type": "Warning",
                "reason": "FailedMount",
                "message": 'MountVolume.SetUp failed for volume "data" : persistentvolumeclaim "taskflow-postgres-data" not found',
                "count": 3,
            }
        ],
    )
    finding, _evidence = _finding(snapshot)
    assert finding.detected_issue == "FailedMount"
    assert "PersistentVolumeClaim" in finding.likely_root_cause


def test_failed_scheduling_uses_the_scheduler_message():
    _title, snapshot = load_scenario("failed-scheduling")
    finding, evidence = _finding(snapshot)
    assert "memory" in finding.likely_root_cause
    assert "Insufficient memory" in evidence["event_text"]


def test_liveness_and_readiness_are_distinct():
    readiness = pod_snapshot(
        events=[
            {
                "type": "Warning",
                "reason": "Unhealthy",
                "message": 'Readiness probe failed: Get "http://10.244.0.12:8000/ready": dial tcp 10.244.0.12:8000: connect: connection refused',
                "count": 4,
            }
        ],
    )
    liveness = pod_snapshot(
        restart_count=2,
        events=[
            {
                "type": "Warning",
                "reason": "Unhealthy",
                "message": 'Liveness probe failed: HTTP probe failed with statuscode: 500',
                "count": 2,
            }
        ],
    )
    ready_finding, ready_evidence = _finding(readiness)
    live_finding, live_evidence = _finding(liveness)
    assert ready_finding.detected_issue == "ReadinessProbeFailed"
    assert ready_finding.severity == "medium"
    assert "8000/ready" in ready_evidence["event_text"]
    assert live_finding.detected_issue == "LivenessProbeFailed"
    assert live_finding.severity == "high"


def test_database_connectivity_classification():
    _title, snapshot = load_scenario("database")
    finding, _evidence = _finding(snapshot)
    assert finding.detected_issue == "DatabaseConnectivity"
    assert "Dependency failure" in finding.summary
    assert all("demo-only-password" not in action for action in finding.recommended_actions)


def test_repeated_restarts_and_unavailable_replicas():
    restarts = pod_snapshot(restart_count=5, desired=2, ready=2)
    finding, _evidence = _finding(restarts)
    assert finding.detected_issue == "RepeatedRestarts"
    assert finding.severity == "medium"

    unavailable = {
        "namespace": "taskflow",
        "deployment": {
            "metadata": {"name": "taskflow-api", "namespace": "taskflow"},
            "spec": {"replicas": 2},
            "status": {"readyReplicas": 0},
        },
    }
    unavailable_finding, evidence = _finding(unavailable)
    assert unavailable_finding.detected_issue == "UnavailableReplicas"
    assert unavailable_finding.severity == "critical"
    assert evidence["resource_kind"] == "Deployment"


def test_total_outage_raises_severity_to_critical():
    snapshot = pod_snapshot(waiting="CrashLoopBackOff", terminated_reason="Error", exit_code=1, restart_count=3, ready=0)
    finding, _evidence = _finding(snapshot)
    assert finding.detected_issue == "CrashLoopBackOff"
    assert finding.severity == "critical"


def test_stale_liveness_event_on_a_ready_pod_is_not_a_finding():
    from datetime import datetime, timedelta, timezone

    event_time = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    snapshot = pod_snapshot(
        restart_count=1,
        desired=2,
        ready=2,
        events=[
            {
                "type": "Warning",
                "reason": "Unhealthy",
                "message": "Liveness probe failed: connection refused",
                "count": 3,
                "lastTimestamp": event_time.isoformat(),
            }
        ],
    )
    snapshot["pod"]["status"]["containerStatuses"][0]["ready"] = True
    snapshot["pod"]["status"]["conditions"] = [{"type": "Ready", "status": "True"}]
    assert (
        collect_from_snapshot(
            snapshot,
            now=event_time + timedelta(seconds=301),
            event_freshness_seconds=300,
        )
        is None
    )
    fresh = collect_from_snapshot(snapshot, now=event_time + timedelta(seconds=10), event_freshness_seconds=300)
    assert fresh is None


def test_fresh_liveness_event_still_opens_when_the_container_is_not_ready():
    from datetime import datetime, timezone

    moment = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    snapshot = pod_snapshot(
        events=[
            {
                "type": "Warning",
                "reason": "Unhealthy",
                "message": "Liveness probe failed: connection refused",
                "count": 2,
                "lastTimestamp": moment.isoformat(),
            }
        ],
    )
    evidence = collect_from_snapshot(snapshot, now=moment, event_freshness_seconds=300)
    assert evidence["detected_issue"] == "LivenessProbeFailed"
    assert evidence["events"][0]["message"].startswith("Liveness probe failed")


def test_recovery_rules_follow_the_current_resource():
    from app.investigation.recovery import recovery_signals

    ready = pod_snapshot()
    ready["pod"]["status"]["containerStatuses"][0]["ready"] = True
    ready["pod"]["status"]["conditions"] = [{"type": "Ready", "status": "True"}]
    assert recovery_signals("ReadinessProbeFailed", ready, "api")[0] is True
    assert recovery_signals("LivenessProbeFailed", ready, "api")[0] is True
    assert recovery_signals("CrashLoopBackOff", ready, "api")[0] is True
    assert recovery_signals("OOMKilled", ready, "api")[0] is True
    assert "Readiness restored" in recovery_signals("ReadinessProbeFailed", ready, "api")[1]

    pulling = pod_snapshot(waiting="ImagePullBackOff")
    assert recovery_signals("ImagePullBackOff", pulling, "api")[0] is False
    running = pod_snapshot()
    assert recovery_signals("ImagePullBackOff", running, "api")[0] is True
    assert recovery_signals("CreateContainerConfigError", running, "api")[0] is True

    pending = pod_snapshot(phase="Pending", node_name=None)
    assert recovery_signals("FailedScheduling", pending, "api")[0] is False
    assert recovery_signals("FailedScheduling", ready, "api")[0] is True

    degraded = {"deployment": {"metadata": {"name": "taskflow-api", "namespace": "taskflow"}, "spec": {"replicas": 2}, "status": {"readyReplicas": 1}}}
    restored = {"deployment": {"metadata": {"name": "taskflow-api", "namespace": "taskflow"}, "spec": {"replicas": 2}, "status": {"readyReplicas": 2}}}
    assert recovery_signals("UnavailableReplicas", degraded, None)[0] is False
    assert recovery_signals("UnavailableReplicas", restored, None)[0] is True

    broken = pod_snapshot(current_log="psycopg.OperationalError: database connection refused\n")
    broken["pod"]["status"]["containerStatuses"][0]["ready"] = True
    broken["pod"]["status"]["conditions"] = [{"type": "Ready", "status": "True"}]
    assert recovery_signals("DatabaseConnectivity", broken, "api")[0] is False
    assert recovery_signals("DatabaseConnectivity", ready, "api")[0] is True


def test_healthy_pod_is_ignored():
    snapshot = pod_snapshot(restart_count=0, desired=2, ready=2)
    assert collect_from_snapshot(snapshot) is None


def test_log_tail_and_char_limit():
    lines = [f"line {index}" for index in range(30)]
    lines.append("password=hunter2")
    snapshot = pod_snapshot(waiting="CrashLoopBackOff", previous_log="\n".join(lines) + "\n")
    _ignored, evidence = _finding(snapshot, log_tail_lines=3, max_log_chars=12000)
    kept = evidence["previous_logs"].splitlines()
    assert kept[-1] == "password=***"
    assert "hunter2" not in evidence["previous_logs"]
    assert len(kept) == 3

    huge = pod_snapshot(waiting="CrashLoopBackOff", previous_log="x" * 500)
    _ignored, truncated = _finding(huge, log_tail_lines=100, max_log_chars=40)
    assert truncated["previous_logs"].startswith("…")
    assert len(truncated["previous_logs"]) <= 42
