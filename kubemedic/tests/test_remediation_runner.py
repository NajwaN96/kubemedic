import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.investigation.models import TransitionItem
from app.main import create_app
from app.remediation.models import Remediation
from app.remediation.repository import RemediationRepository
from app.remediation.runner import run_once
from app.remediation.service import RemediationService
from tests.test_api import DisconnectedCluster

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now = self.now + timedelta(seconds=seconds)


class FakeMutator:
    def __init__(self, *, healthy=True, error=None):
        self.calls = []
        self.healthy = healthy
        self.error = error

    def apply(self, remediation, settings):
        self.calls.append(("apply", remediation.action, remediation.approval_reason))
        if self.error:
            raise self.error
        before = {
            "images": ["taskflow-api:bad"],
            "replicas": 2,
            "ready": 0,
            "updated": 1,
            "revision": 4,
            "generation": 4,
            "observed_generation": 4,
        }
        after = {
            "images": ["taskflow-api:local"],
            "replicas": 2,
            "ready": 0,
            "updated": 0,
            "revision": 3,
            "generation": 5,
            "observed_generation": 4,
        }
        return before, after

    def snapshot(self, namespace, name):
        self.calls.append(("snapshot", namespace, name))
        ready = 2 if self.healthy else 0
        updated = 2 if self.healthy else 0
        observed = 5 if self.healthy else 4
        return {
            "images": ["taskflow-api:local"],
            "replicas": 2,
            "ready": ready,
            "updated": updated,
            "revision": 3,
            "generation": 5,
            "observed_generation": observed,
        }


def _approved(repository, **overrides) -> Remediation:
    moment = NOW
    payload = dict(
        id="REM-000007",
        investigation_id="INV-000019",
        created_at=moment,
        updated_at=moment,
        action="rollback_deployment",
        target_kind="Deployment",
        target_name="taskflow-api",
        namespace="taskflow",
        reason="CrashLoopBackOff started on a newer Deployment revision.",
        status="approved",
        approved_by="najwa",
        approved_at=moment,
        approval_reason="checked the evidence",
        transitions=[
            TransitionItem(at=moment, status="proposed", reason="proposed"),
            TransitionItem(at=moment, status="approved", reason="Approved by najwa"),
        ],
    )
    payload.update(overrides)
    remediation = Remediation(**payload)
    return repository.insert(remediation, 7)


def test_disabled_runner_does_not_call_the_executor(settings):
    repository = RemediationRepository(settings.db_path)
    _approved(repository)
    mutator = FakeMutator()
    assert settings.remediation_enabled is False
    assert run_once(repository, settings, mutator, now=NOW) == 0
    assert mutator.calls == []
    assert repository.get("REM-000007").status == "approved"


def test_verified_records_execution_separately_from_recovery(settings):
    settings.remediation_enabled = True
    settings.remediation_verify_seconds = 30
    repository = RemediationRepository(settings.db_path)
    _approved(repository)
    mutator = FakeMutator(healthy=True)
    clock = Clock()
    assert run_once(repository, settings, mutator, now=NOW, clock=clock, sleep=clock.sleep) == 1
    stored = repository.get("REM-000007")
    assert stored.status == "verified"
    assert stored.before_state["images"] == ["taskflow-api:bad"]
    assert stored.after_state["ready"] == 2
    assert [item.status for item in stored.transitions] == [
        "proposed",
        "approved",
        "executing",
        "succeeded",
        "verified",
    ]
    assert mutator.calls[0][2] == "checked the evidence"
    assert "checked the evidence" not in mutator.calls[0][1]


def test_executor_error_is_failed_without_succeeded(settings):
    settings.remediation_enabled = True
    repository = RemediationRepository(settings.db_path)
    _approved(repository)
    mutator = FakeMutator(error=RuntimeError("password=super-secret-db-password"))
    run_once(repository, settings, mutator, now=NOW, clock=Clock(), sleep=lambda _seconds: None)
    stored = repository.get("REM-000007")
    assert stored.status == "failed"
    assert "succeeded" not in [item.status for item in stored.transitions]
    assert "super-secret-db-password" not in (stored.error or "")
    assert "***" in stored.error


def test_verification_timeout_is_failed_after_success(settings):
    settings.remediation_enabled = True
    settings.remediation_verify_seconds = 1
    repository = RemediationRepository(settings.db_path)
    _approved(repository)
    clock = Clock()
    run_once(repository, settings, FakeMutator(healthy=False), now=NOW, clock=clock, sleep=clock.sleep)
    stored = repository.get("REM-000007")
    assert stored.status == "failed"
    assert stored.verified_at is None
    assert [item.status for item in stored.transitions] == [
        "proposed",
        "approved",
        "executing",
        "succeeded",
        "failed",
    ]


def test_unchanged_generation_is_failed_without_succeeded(settings):
    settings.remediation_enabled = True
    repository = RemediationRepository(settings.db_path)
    _approved(repository)

    class NoopMutator(FakeMutator):
        def apply(self, remediation, settings):
            self.calls.append(("apply", remediation.action, None))
            same = {
                "images": ["taskflow-api:bad"],
                "replicas": 2,
                "ready": 2,
                "updated": 2,
                "revision": 3,
                "generation": 3,
                "observed_generation": 3,
            }
            return same, dict(same)

    run_once(repository, settings, NoopMutator(), now=NOW, clock=Clock(), sleep=lambda _seconds: None)
    stored = repository.get("REM-000007")
    assert stored.status == "failed"
    assert "succeeded" not in [item.status for item in stored.transitions]
    assert "generation" in (stored.error or "")


def test_policy_failure_at_execution_does_not_call_the_mutator(settings):
    settings.remediation_enabled = True
    repository = RemediationRepository(settings.db_path)
    _approved(repository, namespace="kube-system")
    mutator = FakeMutator()
    run_once(repository, settings, mutator, now=NOW, clock=Clock(), sleep=lambda _seconds: None)
    assert mutator.calls == []
    assert repository.get("REM-000007").status == "failed"


def test_approval_is_refused_while_remediation_is_disabled(settings):
    settings.demo_mode = True
    application = create_app(settings, cluster_connection=DisconnectedCluster(settings))
    with TestClient(application) as client:
        created = client.post("/api/v1/demo/crashloop")
        assert created.status_code == 200
        status = client.get("/api/v1/remediation/status")
        assert status.json() == {"enabled": False, "approval_required": True}
        listed = client.get("/api/v1/investigations/INV-000001/remediations")
        proposal = listed.json()[0]
        assert proposal["action"] == "restart_deployment"
        assert proposal["status"] == "proposed"
        denied = client.post(
            f"/api/v1/remediations/{proposal['id']}/approve",
            json={"approved_by": "najwa", "confirm": True, "reason": "checked"},
        )
        assert denied.status_code == 409
        assert client.get(f"/api/v1/remediations/{proposal['id']}").json()["status"] == "proposed"
        metrics = client.get("/metrics").text
        assert 'kubemedic_remediations{action="restart_deployment",status="proposed"}' in metrics
        assert "taskflow-api" not in metrics


def test_approval_stores_the_person_and_still_does_not_execute(settings):
    settings.demo_mode = True
    settings.remediation_enabled = True
    application = create_app(settings, cluster_connection=DisconnectedCluster(settings))
    with TestClient(application) as client:
        client.post("/api/v1/demo/crashloop")
        unconfirmed = client.post(
            "/api/v1/remediations/REM-000001/approve",
            json={"approved_by": "najwa", "confirm": False, "reason": "not yet"},
        )
        assert unconfirmed.status_code == 400
        approved = client.post(
            "/api/v1/investigations/INV-000001/remediation/approve",
            json={"approved_by": "najwa", "confirm": True, "reason": "checked the evidence"},
        )
        assert approved.status_code == 200
        body = approved.json()
        assert body["status"] == "approved"
        assert body["approved_by"] == "najwa"
        assert body["approval_reason"] == "checked the evidence"
        assert body["executed_at"] is None
        cancelled = client.post("/api/v1/remediations/REM-000001/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"


def test_service_refuses_a_second_approval(settings):
    repository = RemediationRepository(settings.db_path)
    stored = _approved(repository, status="proposed", approved_by=None, approved_at=None, approval_reason=None)
    settings.remediation_enabled = True
    service = RemediationService(repository, settings)
    approved = service.approve(stored.id, "najwa", True, "checked", now=NOW)
    assert approved.status == "approved"
    try:
        service.approve(stored.id, "najwa", True, "again", now=NOW)
    except Exception as exc:
        assert "proposed" in str(exc)
    else:
        raise AssertionError("a second approval should be rejected")


def test_only_the_executor_patches_deployments():
    root = Path(__file__).resolve().parents[1] / "app"
    hits = []
    for path in root.rglob("*.py"):
        if "patch_namespaced_deployment" in path.read_text():
            hits.append(path.relative_to(root).as_posix())
    assert hits == ["remediation/executor.py"]
    executor = (root / "remediation" / "executor.py").read_text()
    assert set(re.findall(r"patch_namespaced_\w+", executor)) == {"patch_namespaced_deployment"}
    for token in ("subprocess", "os.system", "delete_namespaced", "connect_get_namespaced_pod_exec"):
        assert token not in executor
