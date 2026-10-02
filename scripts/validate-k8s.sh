#!/usr/bin/env bash
# Schema-check Kubernetes manifests. This does not deploy them.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v kubeconform >/dev/null 2>&1; then
  echo "kubeconform is not installed. CI installs v0.6.7." >&2
  exit 1
fi

if ! grep -q 'KUBEMEDIC_REMEDIATION_ENABLED: "false"' k8s/kubemedic/configmap.yaml; then
  echo "KUBEMEDIC_REMEDIATION_ENABLED must stay false in the Git ConfigMap." >&2
  exit 1
fi

if grep -RInE --include='*.yaml' --include='*.yml' 'image:[[:space:]]*[^[:space:]]+:latest([[:space:]]|$)' k8s; then
  echo "Kubernetes manifests must not use the latest tag." >&2
  exit 1
fi

mapfile -t manifests < <(find k8s -type f \( -name '*.yaml' -o -name '*.yml' \) | sort)
if [[ ${#manifests[@]} -eq 0 ]]; then
  echo "No Kubernetes manifests found." >&2
  exit 1
fi

# Grafana dashboard JSON is not a Kubernetes resource. It stays out of this
# check. The ConfigMaps that mount those files are still validated.
kubeconform \
  -strict \
  -summary \
  -kubernetes-version 1.32.0 \
  -schema-location default \
  "${manifests[@]}"

if command -v kubectl >/dev/null 2>&1 && kubectl cluster-info >/dev/null 2>&1; then
  echo "Cluster is reachable. Running kubectl apply --dry-run=client. Nothing is applied."
  args=()
  for manifest in "${manifests[@]}"; do
    if [[ "$manifest" == *secret.example.yaml ]]; then
      continue
    fi
    args+=(-f "$manifest")
  done
  kubectl apply --dry-run=client --validate=true "${args[@]}"
else
  echo "No Kubernetes API is reachable. kubeconform is the deployment gate. Manifests were not applied."
fi
