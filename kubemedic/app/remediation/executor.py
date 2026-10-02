"""The only Kubernetes writes in KubeMedic.

Each method builds its own patch. Callers cannot pass a shell command, a
kubectl invocation, YAML, or a JSON patch. Audit snapshots keep images,
replica counts, and revision metadata. They do not keep environment
variables, Secret refs, or the Pod template.
"""

import copy
from datetime import datetime, timezone

from app.config import Settings
from app.kubernetes.serialize import to_plain
from app.remediation.errors import ExecutionError, PolicyError
from app.remediation.models import Remediation
from app.remediation.policy import validate_target


class KubernetesDeploymentMutator:
    def __init__(self, apps) -> None:
        self.apps = apps

    def apply(self, remediation: Remediation, settings: Settings) -> tuple[dict, dict]:
        validate_target(remediation, settings)
        before = self.snapshot(remediation.namespace, remediation.target_name)
        if remediation.action == "restart_deployment":
            self._restart(remediation.namespace, remediation.target_name)
        elif remediation.action == "rollback_deployment":
            self._rollback(remediation.namespace, remediation.target_name)
        elif remediation.action == "scale_deployment":
            self._scale(remediation.namespace, remediation.target_name, remediation.replicas, settings)
        else:
            raise PolicyError("Action is not on the remediation allowlist.")
        after = self.snapshot(remediation.namespace, remediation.target_name)
        return before, after

    def snapshot(self, namespace: str, name: str) -> dict:
        plain = to_plain(self.apps.read_namespaced_deployment(name, namespace)) or {}
        return audit_view(plain)

    def _restart(self, namespace: str, name: str) -> None:
        moment = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {"kubectl.kubernetes.io/restartedAt": moment}
                    }
                }
            }
        }
        self._patch(name, namespace, body, "application/strategic-merge-patch+json")

    def _scale(self, namespace: str, name: str, replicas: int | None, settings: Settings) -> None:
        if not isinstance(replicas, int) or isinstance(replicas, bool):
            raise PolicyError("Scale requires an integer replica count.")
        if replicas < 1 or replicas > settings.remediation_max_replicas:
            raise PolicyError(f"Replica count must be from 1 to {settings.remediation_max_replicas}.")
        self._patch(name, namespace, {"spec": {"replicas": replicas}}, "application/strategic-merge-patch+json")

    def _rollback(self, namespace: str, name: str) -> None:
        current = to_plain(self.apps.read_namespaced_deployment(name, namespace)) or {}
        revision = _revision(current)
        template = _previous_template(self.apps, namespace, name, revision)
        # Replace the whole template. A merge would keep fields the previous
        # revision does not have, such as a command added by a bad rollout.
        # The operation list is fixed here. Callers cannot supply one.
        body = [{"op": "replace", "path": "/spec/template", "value": template}]
        self._patch(name, namespace, body, "application/json-patch+json")

    def _patch(self, name: str, namespace: str, body, content_type: str) -> None:
        client = getattr(self.apps, "api_client", None)
        if client is None:
            self.apps.patch_namespaced_deployment(name, namespace, body)
            return
        original = client.select_header_content_type
        client.select_header_content_type = lambda _types: content_type
        try:
            self.apps.patch_namespaced_deployment(name, namespace, body)
        finally:
            client.select_header_content_type = original


def audit_view(plain: dict) -> dict:
    metadata = plain.get("metadata") or {}
    spec = plain.get("spec") or {}
    status = plain.get("status") or {}
    containers = ((spec.get("template") or {}).get("spec") or {}).get("containers") or []
    images = [container.get("image") for container in containers if container.get("image")]
    return {
        "images": images,
        "replicas": spec.get("replicas"),
        "ready": status.get("readyReplicas") or 0,
        "updated": status.get("updatedReplicas") or 0,
        "revision": _revision(plain),
        "generation": metadata.get("generation"),
        "observed_generation": status.get("observedGeneration"),
    }


def recovered(snapshot: dict) -> bool:
    desired = snapshot.get("replicas") or 0
    ready = snapshot.get("ready") or 0
    updated = snapshot.get("updated") or 0
    generation = snapshot.get("generation")
    observed = snapshot.get("observed_generation")
    if not isinstance(desired, int) or isinstance(desired, bool) or desired < 1:
        return False
    if not isinstance(ready, int) or isinstance(ready, bool) or ready < desired:
        return False
    if not isinstance(updated, int) or isinstance(updated, bool) or updated < desired:
        return False
    if generation is None or observed is None:
        return False
    return observed >= generation


def _previous_template(apps, namespace: str, name: str, revision: int | None) -> dict:
    if revision is None or revision < 2:
        raise ExecutionError("No previous Deployment revision is available.")
    listed = to_plain(apps.list_namespaced_replica_set(namespace)) or {}
    items = listed.get("items") if isinstance(listed, dict) else listed
    wanted = str(revision - 1)
    for item in items or []:
        metadata = item.get("metadata") or {}
        owners = metadata.get("ownerReferences") or []
        owned = any(owner.get("kind") == "Deployment" and owner.get("name") == name for owner in owners)
        if not owned:
            continue
        item_revision = (metadata.get("annotations") or {}).get("deployment.kubernetes.io/revision")
        if str(item_revision) != wanted:
            continue
        template = copy.deepcopy((item.get("spec") or {}).get("template") or {})
        labels = (template.get("metadata") or {}).get("labels")
        if isinstance(labels, dict):
            labels.pop("pod-template-hash", None)
        if not template:
            break
        return template
    raise ExecutionError("No previous ReplicaSet was found for this Deployment.")


def _revision(plain: dict) -> int | None:
    raw = ((plain.get("metadata") or {}).get("annotations") or {}).get("deployment.kubernetes.io/revision")
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None
