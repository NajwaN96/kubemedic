"""Read-only poll of one namespace.

This loop lists pods, deployments, replicasets, and events, then reads pod
logs. It never creates, updates, patches, or deletes Kubernetes objects.
A disconnected API is logged and retried. It does not stop the KubeMedic process.
"""

import logging
import threading
from datetime import datetime, timezone

from app.config import Settings
from app.investigation.service import InvestigationService
from app.kubernetes.client import ClusterConnection
from app.kubernetes.serialize import to_plain

logger = logging.getLogger(__name__)

_POLL_SECONDS = 15


class Watcher:
    def __init__(
        self,
        cluster: ClusterConnection,
        service: InvestigationService,
        settings: Settings,
    ) -> None:
        self.cluster = cluster
        self.service = service
        self.settings = settings
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="kubemedic-watcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        announced = False
        while not self._stop.is_set():
            try:
                if not self.cluster.connected:
                    self.cluster.connect()
                if not self.cluster.connected:
                    if not announced:
                        logger.warning(
                            "Kubernetes Status: Disconnected (%s). "
                            "KubeMedic stays up and will retry.",
                            self.cluster.error or "no credentials",
                        )
                        announced = True
                else:
                    announced = False
                    self.poll_once()
            except Exception:
                logger.exception("KubeMedic watcher pass failed. The next pass will retry.")
            self._stop.wait(_POLL_SECONDS)

    def poll_once(self) -> int:
        """One read-only pass. Returns how many snapshots became investigations."""
        if not self.cluster.connected or self.cluster.core is None or self.cluster.apps is None:
            return 0
        namespace = self.settings.namespace
        pods = _items(self.cluster.core.list_namespaced_pod(namespace))
        events = _items(self.cluster.core.list_namespaced_event(namespace))
        deployments = _items(self.cluster.apps.list_namespaced_deployment(namespace))
        replicasets = _items(self.cluster.apps.list_namespaced_replica_set(namespace))

        opened = 0
        explained: set[str] = set()
        moment = datetime.now(timezone.utc)
        for pod in pods:
            deployment = _deployment_for_pod(pod, deployments, replicasets)
            snapshot = {
                "namespace": namespace,
                "pod": pod,
                "events": _events_for_pod(pod, events),
                "deployment": deployment,
                "logs": self._logs(pod),
            }
            investigation = self.service.process_snapshot(snapshot, now=moment)
            if investigation is not None:
                opened += 1
                if deployment:
                    name = (deployment.get("metadata") or {}).get("name")
                    if name:
                        explained.add(name)
            self.service.observe_healthy(snapshot, now=moment, active=investigation)

        for deployment in deployments:
            name = (deployment.get("metadata") or {}).get("name")
            if not name:
                continue
            snapshot = {"namespace": namespace, "deployment": deployment}
            desired = (deployment.get("spec") or {}).get("replicas") or 0
            ready = (deployment.get("status") or {}).get("readyReplicas") or 0
            investigation = None
            if name not in explained and desired > 0 and ready < desired:
                investigation = self.service.process_snapshot(snapshot, now=moment)
                if investigation is not None:
                    opened += 1
            self.service.observe_healthy(snapshot, now=moment, active=investigation)
        present = {
            (pod.get("metadata") or {}).get("name")
            for pod in pods
            if (pod.get("metadata") or {}).get("name")
        }
        self.service.reconcile_absent(namespace, present, deployments, moment)
        return opened

    def _logs(self, pod: dict) -> dict:
        metadata = pod.get("metadata") or {}
        name = metadata.get("name")
        namespace = metadata.get("namespace") or self.settings.namespace
        if not name or self.cluster.core is None:
            return {}
        containers = (pod.get("spec") or {}).get("containers") or []
        logs: dict[str, dict[str, str]] = {}
        for container in containers:
            container_name = container.get("name")
            if not container_name:
                continue
            logs[container_name] = {
                "current": self._read_log(name, namespace, container_name, previous=False),
                "previous": self._read_log(name, namespace, container_name, previous=True),
            }
        return logs

    def _read_log(self, name: str, namespace: str, container: str, previous: bool) -> str:
        try:
            text = self.cluster.core.read_namespaced_pod_log(
                name=name,
                namespace=namespace,
                container=container,
                tail_lines=self.settings.log_tail_lines,
                previous=previous,
            )
        except Exception:
            return ""
        return text or ""


def _items(listing) -> list[dict]:
    raw = getattr(listing, "items", None) or []
    return [to_plain(item) for item in raw]


def _deployment_for_pod(pod: dict, deployments: list[dict], replicasets: list[dict]) -> dict | None:
    owners = (pod.get("metadata") or {}).get("ownerReferences") or []
    replica_names = {item.get("name") for item in owners if item.get("kind") == "ReplicaSet"}
    deployment_name = None
    for replicaset in replicasets:
        metadata = replicaset.get("metadata") or {}
        if metadata.get("name") not in replica_names:
            continue
        for owner in metadata.get("ownerReferences") or []:
            if owner.get("kind") == "Deployment":
                deployment_name = owner.get("name")
                break
    if deployment_name is None:
        pod_name = (pod.get("metadata") or {}).get("name") or ""
        for deployment in deployments:
            name = (deployment.get("metadata") or {}).get("name") or ""
            if name and pod_name.startswith(name + "-"):
                return deployment
        return None
    for deployment in deployments:
        if (deployment.get("metadata") or {}).get("name") == deployment_name:
            return deployment
    return None


def _events_for_pod(pod: dict, events: list[dict]) -> list[dict]:
    name = (pod.get("metadata") or {}).get("name")
    selected = []
    for event in events:
        involved = event.get("involvedObject") or {}
        if involved.get("kind") == "Pod" and involved.get("name") == name:
            selected.append(event)
    return selected
