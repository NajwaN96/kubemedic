"""Kubernetes API connection.

In-cluster, KubeMedic uses the pod ServiceAccount. Outside the cluster it
uses kubeconfig. A missing cluster is a status, not a process failure.
"""

import os

from app.config import Settings
from app.investigation.models import ClusterStatus


class ClusterConnection:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.connected = False
        self.mode = "disconnected"
        self.error: str | None = None
        self.core = None
        self.apps = None

    def connect(self) -> "ClusterConnection":
        try:
            from kubernetes import client, config
        except ImportError as exc:
            return self._fail(f"Kubernetes client is not installed ({exc}).")

        try:
            if os.getenv("KUBERNETES_SERVICE_HOST"):
                config.load_incluster_config()
                mode = "in-cluster"
            else:
                config.load_kube_config()
                mode = "kubeconfig"
            self.core = client.CoreV1Api()
            self.apps = client.AppsV1Api()
        except Exception as exc:
            return self._fail(str(exc))

        self.connected = True
        self.mode = mode
        self.error = None
        return self

    def status(self) -> ClusterStatus:
        return ClusterStatus(
            status="connected" if self.connected else "disconnected",
            namespace=self.settings.namespace,
            mode=self.mode,
            demo_mode=self.settings.demo_mode,
        )

    def _fail(self, message: str) -> "ClusterConnection":
        self.connected = False
        self.mode = "disconnected"
        self.error = message
        self.core = None
        self.apps = None
        return self
