from types import SimpleNamespace

from kubernetes import client

from app.demo import main
from app.kubernetes.serialize import to_plain
from app.kubernetes.watcher import Watcher
from tests.snapshots import pod_snapshot


def test_client_models_serialize_to_api_field_names():
    pod = client.V1Pod(
        metadata=client.V1ObjectMeta(name="taskflow-api-abc", namespace="taskflow"),
        status=client.V1PodStatus(
            phase="Running",
            container_statuses=[
                client.V1ContainerStatus(
                    name="api",
                    ready=False,
                    restart_count=6,
                    image="taskflow-api:local",
                    image_id="sha256:abc",
                    state=client.V1ContainerState(
                        waiting=client.V1ContainerStateWaiting(reason="CrashLoopBackOff")
                    ),
                )
            ],
        ),
    )
    plain = to_plain(pod)
    assert plain["metadata"]["name"] == "taskflow-api-abc"
    assert plain["status"]["containerStatuses"][0]["restartCount"] == 6
    assert plain["status"]["containerStatuses"][0]["state"]["waiting"]["reason"] == "CrashLoopBackOff"


def test_incluster_mode_skips_kubeconfig(monkeypatch, settings):
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.96.0.1")
    calls = []

    def incluster():
        calls.append("in-cluster")

    def kubeconfig():
        calls.append("kubeconfig")

    import kubernetes.config as kconfig

    monkeypatch.setattr(kconfig, "load_incluster_config", incluster)
    monkeypatch.setattr(kconfig, "load_kube_config", kubeconfig)
    from app.kubernetes.client import ClusterConnection

    cluster = ClusterConnection(settings).connect()
    assert cluster.connected is True
    assert cluster.mode == "in-cluster"
    assert calls == ["in-cluster"]


def test_watcher_poll_uses_the_same_pipeline(service, settings):
    snapshot = pod_snapshot(
        name="taskflow-api-7d8f9c6b8-xk2lp",
        waiting="CrashLoopBackOff",
        terminated_reason="Error",
        exit_code=1,
        restart_count=6,
        previous_log="database connection refused\npostgresql://taskflow:super-secret-db-password@db:5432/taskflow\n",
    )
    replicaset = {
        "metadata": {
            "name": "taskflow-api-7d8f9c6b8",
            "namespace": "taskflow",
            "ownerReferences": [{"kind": "Deployment", "name": "taskflow-api"}],
        }
    }

    class Core:
        def list_namespaced_pod(self, namespace):
            assert namespace == "taskflow"
            return SimpleNamespace(items=[snapshot["pod"]])

        def list_namespaced_event(self, namespace):
            return SimpleNamespace(items=[])

        def read_namespaced_pod_log(self, name, namespace, container=None, tail_lines=None, previous=False):
            assert name == "taskflow-api-7d8f9c6b8-xk2lp"
            assert tail_lines == settings.log_tail_lines
            if previous:
                return snapshot["logs"]["api"]["previous"]
            return ""

    class Apps:
        def list_namespaced_deployment(self, namespace):
            return SimpleNamespace(items=[snapshot["deployment"]])

        def list_namespaced_replica_set(self, namespace):
            return SimpleNamespace(items=[replicaset])

    class Cluster:
        connected = True
        core = Core()
        apps = Apps()

    watcher = Watcher(Cluster(), service, settings)
    assert watcher.poll_once() == 1
    investigation = service.get("INV-000001")
    assert investigation.detected_issue == "CrashLoopBackOff"
    assert investigation.occurrence_count == 1
    stored = investigation.model_dump_json()
    assert "super-secret-db-password" not in stored
    assert watcher.poll_once() == 1
    assert service.get("INV-000001").occurrence_count == 2


def test_watcher_reports_a_deployment_with_no_ready_pods(service, settings):
    deployment = {
        "metadata": {"name": "taskflow-frontend", "namespace": "taskflow"},
        "spec": {"replicas": 2},
        "status": {"readyReplicas": 0},
    }

    class Core:
        def list_namespaced_pod(self, namespace):
            return SimpleNamespace(items=[])

        def list_namespaced_event(self, namespace):
            return SimpleNamespace(items=[])

    class Apps:
        def list_namespaced_deployment(self, namespace):
            return SimpleNamespace(items=[deployment])

        def list_namespaced_replica_set(self, namespace):
            return SimpleNamespace(items=[])

    class Cluster:
        connected = True
        core = Core()
        apps = Apps()

    watcher = Watcher(Cluster(), service, settings)
    assert watcher.poll_once() == 1
    investigation = service.list_investigations()[0]
    assert investigation.detected_issue == "UnavailableReplicas"
    assert investigation.severity == "critical"
    assert investigation.resource_kind == "Deployment"


def test_disconnected_watcher_does_not_crash(service, settings):
    class Cluster:
        connected = False
        core = None
        apps = None

    watcher = Watcher(Cluster(), service, settings)
    assert watcher.poll_once() == 0
    assert service.list_investigations() == []


def test_cli_replay_and_unknown_scenario(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("KUBEMEDIC_DB_PATH", str(tmp_path / "kubemedic.db"))
    assert main(["crashloop"]) == 0
    printed = capsys.readouterr().out
    assert "Replaying scenario: CrashLoopBackOff" in printed
    assert "ID: INV-000001" in printed
    assert "Severity: HIGH" in printed
    assert "super-secret-db-password" not in printed
    assert main(["nope"]) == 2


def test_kubernetes_package_has_no_write_calls():
    from pathlib import Path

    text = "\n".join(path.read_text() for path in Path("app/kubernetes").glob("*.py"))
    for token in ("delete_namespaced", "patch_namespaced", "replace_namespaced", "create_namespaced"):
        assert token not in text
