import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.investigation.models import TransitionItem
from app.remediation.errors import ExecutionError, PolicyError
from app.remediation.executor import KubernetesDeploymentMutator, audit_view
from app.remediation.models import Remediation
from app.remediation.policy import validate_approval, validate_target


def _record(**overrides) -> Remediation:
    moment = datetime(2026, 10, 1, tzinfo=timezone.utc)
    payload = dict(
        id="REM-000001",
        investigation_id="INV-000001",
        created_at=moment,
        updated_at=moment,
        action="restart_deployment",
        target_kind="Deployment",
        target_name="taskflow-api",
        namespace="taskflow",
        reason="unhealthy",
        status="proposed",
        transitions=[TransitionItem(at=moment, status="proposed", reason="unhealthy")],
    )
    payload.update(overrides)
    return Remediation(**payload)


def test_policy_rejects_shell_yaml_namespace_and_scale_bounds(settings):
    with pytest.raises(PolicyError):
        validate_target(_record(action="kubectl delete pod"), settings)
    with pytest.raises(PolicyError):
        validate_target(_record(action="apply_yaml"), settings)
    with pytest.raises(PolicyError):
        validate_target(_record(namespace="kube-system"), settings)
    with pytest.raises(PolicyError):
        validate_target(_record(target_kind="Secret", action="restart_deployment"), settings)
    with pytest.raises(PolicyError):
        validate_target(_record(action="scale_deployment", replicas=0), settings)
    with pytest.raises(PolicyError):
        validate_target(_record(action="scale_deployment", replicas=6), settings)
    with pytest.raises(ValidationError):
        _record(action="scale_deployment", replicas=True)
    with pytest.raises(PolicyError):
        validate_target(_record(replicas=1), settings)
    with pytest.raises(PolicyError):
        validate_approval("najwa", False, "checked")
    with pytest.raises(PolicyError):
        validate_approval("has space", True, "checked")
    validate_target(_record(action="scale_deployment", replicas=1), settings)
    validate_approval("najwa", True, "checked the evidence")


class FakeApps:
    def __init__(self, replicasets=None):
        self.patches = []
        self.deployment = {
            "metadata": {
                "name": "taskflow-api",
                "namespace": "taskflow",
                "generation": 8,
                "annotations": {"deployment.kubernetes.io/revision": "4"},
            },
            "spec": {
                "replicas": 2,
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "api",
                                "image": "taskflow-api:bad",
                                "command": ["python", "-c", "import sys; sys.exit(1)"],
                                "env": [{"name": "DATABASE_PASSWORD", "valueFrom": {"secretKeyRef": {"name": "taskflow-db", "key": "password"}}}],
                            }
                        ]
                    }
                },
            },
            "status": {"readyReplicas": 0, "observedGeneration": 8},
        }
        self.replicasets = replicasets if replicasets is not None else {"items": [_previous_rs()]}

    def read_namespaced_deployment(self, name, namespace):
        assert name == "taskflow-api"
        assert namespace == "taskflow"
        return self.deployment

    def patch_namespaced_deployment(self, name, namespace, body):
        assert name == "taskflow-api"
        assert namespace == "taskflow"
        self.patches.append(body)
        return self.deployment

    def list_namespaced_replica_set(self, namespace):
        assert namespace == "taskflow"
        return self.replicasets


def _previous_rs():
    return {
        "metadata": {
            "name": "taskflow-api-old",
            "annotations": {"deployment.kubernetes.io/revision": "3"},
            "ownerReferences": [{"kind": "Deployment", "name": "taskflow-api"}],
            "labels": {"pod-template-hash": "oldhash"},
        },
        "spec": {
            "template": {
                "metadata": {"labels": {"app": "api", "pod-template-hash": "oldhash"}},
                "spec": {
                    "containers": [
                        {
                            "name": "api",
                            "image": "taskflow-api:local",
                            "env": [{"name": "DATABASE_PASSWORD", "valueFrom": {"secretKeyRef": {"name": "taskflow-db", "key": "password"}}}],
                        }
                    ]
                },
            }
        },
    }


def test_audit_snapshot_omits_env_and_secrets():
    view = audit_view(FakeApps().deployment)
    encoded = json.dumps(view)
    assert "DATABASE_PASSWORD" not in encoded
    assert "secretKeyRef" not in encoded
    assert "env" not in view
    assert view["images"] == ["taskflow-api:bad"]
    assert view["revision"] == 4
    assert set(view) == {
        "images",
        "replicas",
        "ready",
        "updated",
        "revision",
        "generation",
        "observed_generation",
    }


def test_restart_patch_is_only_the_restart_annotation(settings):
    apps = FakeApps()
    KubernetesDeploymentMutator(apps).apply(_record(), settings)
    body = apps.patches[0]
    assert list(body) == ["spec"]
    annotation = body["spec"]["template"]["metadata"]["annotations"]
    assert list(annotation) == ["kubectl.kubernetes.io/restartedAt"]
    assert "command" not in json.dumps(body)
    assert "env" not in json.dumps(body)


def test_rollback_replaces_the_whole_template(settings):
    apps = FakeApps()
    KubernetesDeploymentMutator(apps).apply(_record(action="rollback_deployment"), settings)
    body = apps.patches[0]
    assert body == [
        {
            "op": "replace",
            "path": "/spec/template",
            "value": body[0]["value"],
        }
    ]
    template = body[0]["value"]
    assert "pod-template-hash" not in template["metadata"]["labels"]
    assert "command" not in template["spec"]["containers"][0]
    assert template["spec"]["containers"][0]["image"] == "taskflow-api:local"


def test_missing_previous_replicaset_does_not_invent_a_template(settings):
    apps = FakeApps(replicasets={"items": []})
    with pytest.raises(ExecutionError):
        KubernetesDeploymentMutator(apps).apply(_record(action="rollback_deployment"), settings)
    assert apps.patches == []


def test_scale_patch_is_only_replicas(settings):
    apps = FakeApps()
    KubernetesDeploymentMutator(apps).apply(_record(action="scale_deployment", replicas=1), settings)
    assert apps.patches == [{"spec": {"replicas": 1}}]
    with pytest.raises(PolicyError):
        KubernetesDeploymentMutator(apps).apply(_record(action="scale_deployment", replicas=9), settings)
    assert len(apps.patches) == 1
