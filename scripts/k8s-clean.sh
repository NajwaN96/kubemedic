#!/usr/bin/env bash
# Delete the taskflow namespace, including the database volume and secret.
set -euo pipefail

if ! command -v kubectl >/dev/null 2>&1; then
  echo "ERROR: kubectl is not installed." >&2
  exit 1
fi

if ! kubectl cluster-info >/dev/null 2>&1; then
  echo "ERROR: kubectl cannot reach a Kubernetes cluster." >&2
  kubectl cluster-info >&2 || true
  exit 1
fi

if ! kubectl get namespace taskflow >/dev/null 2>&1; then
  echo "Namespace taskflow is not present."
  exit 0
fi

echo "Deleting namespace taskflow. This removes pods, the database volume, and the generated secret."
kubectl delete namespace taskflow --wait=true
echo "Namespace taskflow has been removed."
