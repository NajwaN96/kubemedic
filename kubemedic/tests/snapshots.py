"""Small Kubernetes-shaped snapshots for rule tests."""


def pod_snapshot(
    *,
    name: str = "taskflow-api-abc12",
    namespace: str = "taskflow",
    container: str = "api",
    image: str = "taskflow-api:local",
    waiting: str | None = None,
    waiting_message: str = "",
    terminated_reason: str | None = None,
    exit_code: int | None = None,
    restart_count: int = 0,
    phase: str = "Running",
    events: list | None = None,
    current_log: str = "",
    previous_log: str = "",
    desired: int | None = 2,
    ready: int | None = 1,
    memory: str | None = "256Mi",
    node_name: str | None = "worker-1",
) -> dict:
    state: dict = {}
    if waiting:
        state["waiting"] = {"reason": waiting, "message": waiting_message}
    elif terminated_reason:
        state["terminated"] = {"reason": terminated_reason, "exitCode": exit_code}
    else:
        state["running"] = {"startedAt": "2026-09-30T12:00:00Z"}
    last_state = {}
    if terminated_reason and waiting:
        last_state = {"terminated": {"reason": terminated_reason, "exitCode": exit_code}}
    container_status = {
        "name": container,
        "ready": False,
        "restartCount": restart_count,
        "image": image,
        "imageID": "",
        "state": state,
    }
    if last_state:
        container_status["lastState"] = last_state
    resources = {"limits": {"memory": memory}} if memory else {}
    snapshot = {
        "namespace": namespace,
        "pod": {
            "metadata": {
                "name": name,
                "namespace": namespace,
                "ownerReferences": [{"kind": "ReplicaSet", "name": f"{name.rsplit('-', 1)[0]}", "uid": "rs"}],
            },
            "spec": {
                "nodeName": node_name,
                "containers": [{"name": container, "image": image, "resources": resources}],
            },
            "status": {
                "phase": phase,
                "conditions": [],
                "containerStatuses": [container_status],
            },
        },
        "events": events or [],
        "logs": {container: {"current": current_log, "previous": previous_log}},
    }
    if desired is not None:
        snapshot["deployment"] = {
            "metadata": {"name": "taskflow-api", "namespace": namespace},
            "spec": {"replicas": desired},
            "status": {"readyReplicas": ready or 0},
        }
    return snapshot
