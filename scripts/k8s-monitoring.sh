#!/usr/bin/env bash
# Deploy Prometheus, Grafana, and kube-state-metrics into namespace monitoring.
# This does not change TaskFlow or KubeMedic workloads.
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

kubectl apply -f k8s/monitoring/namespace.yaml
kubectl apply -f k8s/monitoring/prometheus-rbac.yaml
kubectl apply -f k8s/monitoring/prometheus-config.yaml
kubectl apply -f k8s/monitoring/prometheus.yaml
kubectl apply -f k8s/monitoring/kube-state-metrics.yaml
kubectl create configmap grafana-dashboards -n monitoring \
  --from-file=k8s/monitoring/dashboards/taskflow-service-health.json \
  --from-file=k8s/monitoring/dashboards/kubemedic-reliability.json \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s/monitoring/grafana.yaml
kubectl -n monitoring rollout status deployment/kube-state-metrics --timeout=180s
kubectl -n monitoring rollout status deployment/prometheus --timeout=180s
kubectl -n monitoring rollout status deployment/grafana --timeout=180s
kubectl -n monitoring get pods,svc
echo
echo "Port-forward Prometheus with:"
echo "  kubectl -n monitoring port-forward svc/prometheus 41834:9090"
echo "Port-forward Grafana with:"
echo "  kubectl -n monitoring port-forward svc/grafana 41833:3000"
