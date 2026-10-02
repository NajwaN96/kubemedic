from fastapi.testclient import TestClient

from app.demo import scenario_names
from app.investigation.models import ClusterStatus
from app.kubernetes.client import ClusterConnection
from app.main import create_app


class DisconnectedCluster:
    def __init__(self, settings):
        self.settings = settings
        self.connected = False
        self.mode = "disconnected"
        self.error = "no cluster in this test"

    def status(self) -> ClusterStatus:
        return ClusterStatus(
            status="disconnected",
            namespace=self.settings.namespace,
            mode=self.mode,
            demo_mode=self.settings.demo_mode,
        )

    def connect(self):
        return self


def _client(settings, demo_mode=False):
    settings.demo_mode = demo_mode
    application = create_app(settings, cluster_connection=DisconnectedCluster(settings))
    return TestClient(application)


def test_health_stays_up_when_kubernetes_is_disconnected(settings):
    with _client(settings) as client:
        health = client.get("/health")
        ready = client.get("/ready")
        status = client.get("/api/v1/cluster/status")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    body = status.json()
    assert body["status"] == "disconnected"
    assert body["namespace"] == "taskflow"
    assert "fingerprint" not in body


def test_investigation_list_detail_and_resolve(settings):
    with _client(settings, demo_mode=True) as client:
        created = client.post("/api/v1/demo/crashloop")
        assert created.status_code == 200
        investigation = created.json()
        assert investigation["id"] == "INV-000001"
        assert investigation["detected_issue"] == "CrashLoopBackOff"
        assert investigation["analysis_source"] == "rules"
        assert "fingerprint" not in investigation
        assert "super-secret-db-password" not in created.text

        listed = client.get("/api/v1/investigations", params={"issue": "CrashLoopBackOff", "status": "open"})
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == ["INV-000001"]

        detail = client.get("/api/v1/investigations/INV-000001")
        assert detail.status_code == 200
        assert any(item["label"] == "Exit code" and item["value"] == "1" for item in detail.json()["evidence"])

        missing = client.get("/api/v1/investigations/INV-999999")
        assert missing.status_code == 404

        resolved = client.post("/api/v1/investigations/INV-000001/resolve")
        assert resolved.status_code == 200
        assert resolved.json()["status"] == "resolved"
        open_items = client.get("/api/v1/investigations", params={"status": "open"})
        assert open_items.json() == []


def test_demo_endpoint_is_hidden_unless_demo_mode_is_on(settings):
    with _client(settings, demo_mode=False) as client:
        hidden = client.post("/api/v1/demo/crashloop")
        assert hidden.status_code == 404
    with _client(settings, demo_mode=True) as client:
        unknown = client.post("/api/v1/demo/not-a-scenario")
        assert unknown.status_code == 404
        listed = client.get("/api/v1/demo")
        assert listed.status_code == 200
        assert listed.json()["scenarios"] == scenario_names()


def test_metrics_expose_connection_without_resource_labels(settings):
    with _client(settings, demo_mode=True) as client:
        client.post("/api/v1/demo/crashloop")
        response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "kubemedic_kubernetes_connected 0.0" in body or "kubemedic_kubernetes_connected 0" in body
    assert "kubemedic_open_investigations" in body
    assert "CrashLoopBackOff" in body
    assert "taskflow-api-" not in body
    assert "super-secret-db-password" not in body


def test_dashboard_pages(settings):
    with _client(settings, demo_mode=True) as client:
        client.post("/api/v1/demo/oom")
        home = client.get("/")
        detail = client.get("/investigations/INV-000001")
        script = client.get("/static/dashboard.js")
        i18n = client.get("/static/i18n.js")
        investigations = client.get("/investigations")
        remediations = client.get("/remediations")
        observability = client.get("/observability")
        system = client.get("/system")
    assert home.status_code == 200
    assert "KubeMedic" in home.text
    assert "Kubernetes Reliability Investigator" in home.text
    assert detail.status_code == 200
    assert "dashboard.js" in detail.text
    assert "innerHTML" not in script.text
    for response in (investigations, remediations, observability, system):
        assert response.status_code == 200
        assert "KubeMedic" in response.text
    assert i18n.status_code == 200
    assert "innerHTML" not in i18n.text
    assert 'dir: "rtl"' in i18n.text
    assert 'dir: "ltr"' in i18n.text
    assert "لا توجد حوادث نشطة" in i18n.text
    assert "No active incidents" in i18n.text
    assert "المعالجة معطلة حالياً" in i18n.text
    assert "kubemedic.lang" in i18n.text
    assert "documentElement.dir" in i18n.text
    dashboard = script.text
    assert "showModal" in dashboard
    assert "confirm: true" in dashboard
    assert '=== "ar"' not in dashboard


def test_real_client_object_reports_disconnected_without_raising(monkeypatch, settings):
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)

    def fail_load(*_args, **_kwargs):
        raise RuntimeError("kubeconfig is not available in this test")

    import kubernetes.config as kconfig

    monkeypatch.setattr(kconfig, "load_kube_config", fail_load)
    monkeypatch.setattr(kconfig, "load_incluster_config", fail_load)
    cluster = ClusterConnection(settings).connect()
    assert cluster.connected is False
    assert cluster.status().status == "disconnected"
    assert cluster.status().namespace == "taskflow"
