#!/usr/bin/env bash
# Deploy KubeMedic into namespace kubemedic.
# The watcher ServiceAccount is read-only. The remediator ServiceAccount is
# separate, and KUBEMEDIC_REMEDIATION_ENABLED stays false in Git.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

if ! command -v kubectl >/dev/null 2>&1; then
  fail "kubectl is not installed."
fi
if ! kubectl cluster-info >/dev/null 2>&1; then
  fail "kubectl cannot reach a cluster."
fi
if ! docker image inspect kubemedic:local >/dev/null 2>&1; then
  fail "Image kubemedic:local is missing. Build it from kubemedic/Dockerfile first."
fi

context="$(kubectl config current-context 2>/dev/null || true)"
if [[ "$context" == kind-* ]] && command -v kind >/dev/null 2>&1; then
  cluster="${context#kind-}"
  echo "Loading kubemedic:local into kind cluster ${cluster}."
  "$ROOT/scripts/kind-load-image.sh" "$cluster" kubemedic:local
fi

kubectl apply -f k8s/kubemedic/namespace.yaml
kubectl apply -f k8s/kubemedic/serviceaccount.yaml
kubectl apply -f k8s/kubemedic/rbac.yaml
kubectl apply -f k8s/kubemedic/configmap.yaml
kubectl apply -f k8s/kubemedic/pvc.yaml
kubectl apply -f k8s/kubemedic/deployment.yaml
kubectl apply -f k8s/kubemedic/remediator.yaml
kubectl apply -f k8s/kubemedic/service.yaml
kubectl -n kubemedic rollout status deployment/kubemedic --timeout=180s
kubectl -n kubemedic rollout status deployment/kubemedic-remediator --timeout=180s
kubectl -n kubemedic get pods,svc,pvc
echo
echo "The watcher is read-only. Remediation stays off until KUBEMEDIC_REMEDIATION_ENABLED=true, and a person must still approve each action."
echo "Port-forward the dashboard with:"
echo "  kubectl -n kubemedic port-forward svc/kubemedic 41832:80"
