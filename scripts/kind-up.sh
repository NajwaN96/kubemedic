#!/usr/bin/env bash
# Create the local kind cluster used by this lab.
# The native snapshotter avoids overlay-on-overlay, which fails in this environment.
set -euo pipefail

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  fail "Docker is not reachable."
fi
if ! command -v kind >/dev/null 2>&1; then
  fail "kind is not installed."
fi
if ! command -v kubectl >/dev/null 2>&1; then
  fail "kubectl is not installed."
fi

export KIND_EXPERIMENTAL_CONTAINERD_SNAPSHOTTER="${KIND_EXPERIMENTAL_CONTAINERD_SNAPSHOTTER:-native}"

if kind get clusters 2>/dev/null | grep -qx taskflow; then
  echo "kind cluster taskflow already exists."
else
  echo "Creating kind cluster taskflow (snapshotter=${KIND_EXPERIMENTAL_CONTAINERD_SNAPSHOTTER})."
  kind create cluster --name taskflow
fi

kubectl config use-context kind-taskflow >/dev/null
kubectl cluster-info
kubectl get nodes

# This kernel rejects the iptables statistic match kube-proxy needs.
# nftables mode programs Service rules without that module.
if kubectl -n kube-system get configmap kube-proxy -o jsonpath='{.data.config\.conf}' | grep -q 'mode: iptables'; then
  echo "Switching kube-proxy to nftables."
  kubectl -n kube-system get configmap kube-proxy -o yaml \
    | sed 's/mode: iptables/mode: nftables/' \
    | kubectl apply -f -
  kubectl -n kube-system delete pod -l k8s-app=kube-proxy --wait=true
  kubectl -n kube-system rollout status daemonset/kube-proxy --timeout=120s
fi
