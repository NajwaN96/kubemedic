#!/usr/bin/env bash
# Deploy the healthy TaskFlow stack into the taskflow namespace.
# Re-running this script restores that configuration. It does not print the
# database password.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

echo "TaskFlow Kubernetes deploy"
echo

if ! command -v kubectl >/dev/null 2>&1; then
  fail "kubectl is not installed. Install kubectl, point it at a local cluster (Docker Desktop, kind, or minikube), and run make deploy again."
fi

if ! kubectl cluster-info; then
  fail "kubectl cannot reach a Kubernetes cluster. Check the current context with: kubectl config get-contexts"
fi
echo

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  if ! docker image inspect taskflow-api:local >/dev/null 2>&1; then
    fail "Image taskflow-api:local is not in the local Docker engine. Run make build, then make deploy."
  fi
  if ! docker image inspect taskflow-frontend:local >/dev/null 2>&1; then
    fail "Image taskflow-frontend:local is not in the local Docker engine. Run make build, then make deploy."
  fi

  context="$(kubectl config current-context 2>/dev/null || true)"
  if [[ "$context" == kind-* ]] && command -v kind >/dev/null 2>&1; then
    cluster="${context#kind-}"
    echo "Loading local images into kind cluster ${cluster}."
    "$ROOT/scripts/kind-load-image.sh" "$cluster" taskflow-api:local taskflow-frontend:local postgres:16-alpine
  elif command -v minikube >/dev/null 2>&1 && minikube status >/dev/null 2>&1; then
    echo "Loading local images into minikube."
    minikube image load taskflow-api:local
    minikube image load taskflow-frontend:local
  else
    echo "No kind or minikube image loader matches this context (${context:-unknown})."
    echo "Docker Desktop can use taskflow-api:local and taskflow-frontend:local when they were built by the same Docker engine."
    echo "imagePullPolicy is IfNotPresent. Other clusters need those images loaded locally."
  fi
else
  echo "Docker is not reachable. Skipping image load."
  echo "The cluster must already be able to run taskflow-api:local and taskflow-frontend:local."
fi
echo

kubectl apply -f k8s/taskflow/namespace.yaml

if kubectl -n taskflow get secret taskflow-db >/dev/null 2>&1; then
  echo "Secret taskflow-db already exists. Leaving the current password in place."
else
  password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  kubectl -n taskflow create secret generic taskflow-db --from-literal=password="$password"
  unset password
  echo "Created secret taskflow-db. The password was not printed."
fi

kubectl apply -f k8s/taskflow/backend/configmap.yaml
kubectl apply -f k8s/taskflow/database/service.yaml
kubectl apply -f k8s/taskflow/database/pvc.yaml
kubectl apply -f k8s/taskflow/database/statefulset.yaml
kubectl -n taskflow rollout status statefulset/taskflow-postgres --timeout=180s

kubectl apply -f k8s/taskflow/backend/deployment.yaml
kubectl apply -f k8s/taskflow/backend/service.yaml
kubectl -n taskflow rollout status deployment/taskflow-api --timeout=180s

kubectl apply -f k8s/taskflow/frontend/configmap.yaml
kubectl apply -f k8s/taskflow/frontend/deployment.yaml
kubectl apply -f k8s/taskflow/frontend/service.yaml
kubectl -n taskflow rollout status deployment/taskflow-frontend --timeout=180s

echo
echo "Applying Ingress."
if ! kubectl apply -f k8s/taskflow/ingress.yaml; then
  echo "Ingress apply failed. The kubectl error is above."
  echo "TaskFlow is still deployed. Use port-forward to open it."
fi

echo
echo "Workload status"
kubectl -n taskflow get pods,deployments,statefulsets,services,pvc
echo
echo "Open TaskFlow with port-forward:"
echo "  kubectl -n taskflow port-forward svc/taskflow-frontend 41831:8080"
echo "  http://127.0.0.1:41831"
echo
echo "If an ingress-nginx controller is already installed, the Ingress sends / to the frontend and /api to the API."
echo "This script does not install an Ingress controller."
echo
echo "KubeMedic is deployed separately: make deploy-kubemedic"
