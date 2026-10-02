from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.kubernetes.watcher import Watcher
from tests.snapshots import pod_snapshot


def _deployment(name="taskflow-api", desired=2, ready=2):
    return {
        "metadata": {"name": name, "namespace": "taskflow"},
        "spec": {"replicas": desired},
        "status": {"readyReplicas": ready},
    }


def _open_crash(service, name, start, desired=2, ready=1):
    snapshot = pod_snapshot(
        name=name,
        waiting="CrashLoopBackOff",
        terminated_reason="Error",
        exit_code=1,
        restart_count=4,
        previous_log="startup failed\n",
        desired=desired,
        ready=ready,
    )
    return service.process_snapshot(snapshot, now=start), snapshot


def test_deleted_pod_with_healthy_deployment_stabilizes_before_resolve(service):
    start = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    opened, _snapshot = _open_crash(service, "taskflow-api-oldpod", start)
    evidence = [item.model_dump() for item in opened.evidence]
    logs = [item.model_dump() for item in opened.logs]

    first = service.reconcile_absent("taskflow", set(), [_deployment(ready=2)], start + timedelta(seconds=15))
    assert first[0].id == opened.id
    assert first[0].status == "recovering"
    assert first[0].resolved_at is None
    assert first[0].resolution_reason is None

    same_moment = service.reconcile_absent("taskflow", set(), [_deployment(ready=2)], start + timedelta(seconds=15))
    assert same_moment[0].status == "recovering"

    done = service.reconcile_absent("taskflow", set(), [_deployment(ready=2)], start + timedelta(seconds=80))
    assert done[0].status == "resolved"
    assert done[0].resolution_reason == "affected Pod was replaced and owning workload is healthy"
    assert [item.model_dump() for item in done[0].evidence] == evidence
    assert [item.model_dump() for item in done[0].logs] == logs
    assert any(item.message == "Affected Pod no longer exists" for item in done[0].timeline)
    assert done[0].detected_issue == "CrashLoopBackOff"


def test_deleted_pod_with_degraded_deployment_stays_open(service):
    start = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    opened, _snapshot = _open_crash(service, "taskflow-api-oldpod", start)
    first = service.reconcile_absent("taskflow", set(), [_deployment(desired=2, ready=0)], start + timedelta(seconds=20))
    assert first[0].status == "open"
    assert first[0].resolution_reason is None
    assert first[0].id == opened.id
    second = service.reconcile_absent("taskflow", set(), [_deployment(desired=2, ready=1)], start + timedelta(seconds=40))
    assert second[0].status == "open"
    messages = [item.message for item in second[0].timeline]
    assert messages.count("Owning workload is still degraded") == 1
    assert "affected Pod was replaced and owning workload is healthy" not in (second[0].resolution_reason or "")


def test_deleted_during_recovering_keeps_the_stabilization_window(service):
    start = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    opened, snapshot = _open_crash(service, "taskflow-api-oldpod", start)
    healthy = pod_snapshot(name="taskflow-api-oldpod", restart_count=4, desired=2, ready=2)
    healthy["pod"]["status"]["containerStatuses"][0]["ready"] = True
    healthy["pod"]["status"]["conditions"] = [{"type": "Ready", "status": "True"}]
    recovering = service.observe_healthy(healthy, now=start + timedelta(seconds=10))
    assert recovering.status == "recovering"

    still = service.reconcile_absent(
        "taskflow",
        set(),
        [_deployment(ready=2)],
        start + timedelta(seconds=30),
    )
    assert still[0].status == "recovering"
    assert still[0].id == opened.id

    done = service.reconcile_absent(
        "taskflow",
        set(),
        [_deployment(ready=2)],
        start + timedelta(seconds=80),
    )
    assert done[0].status == "resolved"
    assert done[0].resolution_reason == "affected Pod was replaced and owning workload is healthy"


def test_degraded_replacement_returns_a_recovering_incident_to_open(service):
    start = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    _open_crash(service, "taskflow-api-oldpod", start)
    healthy = pod_snapshot(name="taskflow-api-oldpod", restart_count=4, desired=2, ready=2)
    healthy["pod"]["status"]["containerStatuses"][0]["ready"] = True
    healthy["pod"]["status"]["conditions"] = [{"type": "Ready", "status": "True"}]
    service.observe_healthy(healthy, now=start + timedelta(seconds=10))
    reverted = service.reconcile_absent(
        "taskflow",
        set(),
        [_deployment(desired=2, ready=0)],
        start + timedelta(seconds=20),
    )
    assert reverted[0].status == "open"
    assert reverted[0].last_healthy_seen_at is None
    assert any(item.message == "Owning workload is still degraded" for item in reverted[0].timeline)


def test_unmanaged_pod_deletion_records_removal_not_repair(service):
    start = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    snapshot = pod_snapshot(
        name="phase4-oom",
        waiting="CrashLoopBackOff",
        terminated_reason="Error",
        exit_code=137,
        restart_count=2,
        previous_log="killed\n",
        desired=None,
    )
    opened = service.process_snapshot(snapshot, now=start)
    assert not any(item.label == "Deployment" for item in opened.evidence)
    done = service.reconcile_absent("taskflow", set(), [], start + timedelta(seconds=5))
    assert done[0].status == "resolved"
    assert done[0].resolution_reason == "affected resource no longer exists"
    assert "healthy" not in done[0].resolution_reason
    assert any(item.label == "Exit code" and item.value == "137" for item in done[0].evidence)
    assert done[0].logs
    assert done[0].detected_issue == "CrashLoopBackOff"
    assert any(item.message == "Affected resource no longer exists" for item in done[0].timeline)


def test_missing_deployment_object_is_not_treated_as_healthy(service):
    start = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    opened, _snapshot = _open_crash(service, "taskflow-api-oldpod", start)
    done = service.reconcile_absent("taskflow", set(), [], start + timedelta(seconds=5))
    assert done[0].id == opened.id
    assert done[0].status == "resolved"
    assert done[0].resolution_reason == "affected resource no longer exists"


def test_present_pod_is_not_reconciled(service):
    start = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    opened, _snapshot = _open_crash(service, "taskflow-api-live", start)
    updated = service.reconcile_absent(
        "taskflow",
        {"taskflow-api-live"},
        [_deployment(ready=2)],
        start + timedelta(seconds=90),
    )
    assert updated == []
    assert service.get(opened.id).status == "open"


def test_deleted_deployment_investigation_is_removed_not_repaired(service):
    start = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    snapshot = {
        "namespace": "taskflow",
        "deployment": {
            "metadata": {"name": "taskflow-frontend", "namespace": "taskflow"},
            "spec": {"replicas": 2},
            "status": {"readyReplicas": 0},
        },
    }
    opened = service.process_snapshot(snapshot, now=start)
    assert opened.resource_kind == "Deployment"
    done = service.reconcile_absent("taskflow", set(), [], start + timedelta(seconds=5))
    assert done[0].status == "resolved"
    assert done[0].resolution_reason == "affected resource no longer exists"
    assert done[0].detected_issue == "UnavailableReplicas"


def test_watcher_moves_a_deleted_rollout_pod_to_recovering(service, settings):
    snapshot = pod_snapshot(
        name="taskflow-api-7d8f9c6b8-old",
        waiting="CrashLoopBackOff",
        terminated_reason="Error",
        exit_code=1,
        restart_count=3,
        desired=2,
        ready=1,
    )
    state = {"pods": [snapshot["pod"]], "deployment": snapshot["deployment"]}

    class Core:
        def list_namespaced_pod(self, namespace):
            return SimpleNamespace(items=list(state["pods"]))

        def list_namespaced_event(self, namespace):
            return SimpleNamespace(items=[])

        def read_namespaced_pod_log(self, name, namespace, container=None, tail_lines=None, previous=False):
            return ""

    class Apps:
        def list_namespaced_deployment(self, namespace):
            return SimpleNamespace(items=[state["deployment"]])

        def list_namespaced_replica_set(self, namespace):
            return SimpleNamespace(items=[])

    class Cluster:
        connected = True
        core = Core()
        apps = Apps()

    watcher = Watcher(Cluster(), service, settings)
    assert watcher.poll_once() == 1
    assert service.get("INV-000001").status == "open"

    state["pods"] = []
    state["deployment"]["spec"]["replicas"] = 2
    state["deployment"]["status"]["readyReplicas"] = 2
    assert watcher.poll_once() == 0
    current = service.get("INV-000001")
    assert current.status == "recovering"
    assert current.resolution_reason is None
    assert current.occurrence_count == 1
