#!/usr/bin/env bash
# Install the pinned CI scanners into /usr/local/bin.
set -euo pipefail

KUBECONFORM_VERSION="${KUBECONFORM_VERSION:-0.6.7}"
GITLEAKS_VERSION="${GITLEAKS_VERSION:-8.24.2}"
TRIVY_VERSION="${TRIVY_VERSION:-0.74.0}"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

if ! command -v kubeconform >/dev/null 2>&1 || [[ "$(kubeconform -v 2>/dev/null || true)" != *"${KUBECONFORM_VERSION}"* ]]; then
  curl -fsSL -o "$tmp/kubeconform.tgz" \
    "https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/kubeconform-linux-amd64.tar.gz"
  tar -xzf "$tmp/kubeconform.tgz" -C "$tmp" kubeconform
  sudo mv "$tmp/kubeconform" /usr/local/bin/kubeconform
fi

if ! command -v gitleaks >/dev/null 2>&1 || [[ "$(gitleaks version 2>/dev/null || true)" != *"${GITLEAKS_VERSION}"* ]]; then
  curl -fsSL -o "$tmp/gitleaks.tgz" \
    "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"
  tar -xzf "$tmp/gitleaks.tgz" -C "$tmp" gitleaks
  sudo mv "$tmp/gitleaks" /usr/local/bin/gitleaks
fi

if ! command -v trivy >/dev/null 2>&1 || [[ "$(trivy --version 2>/dev/null || true)" != *"${TRIVY_VERSION}"* ]]; then
  curl -fsSL -o "$tmp/trivy.tgz" \
    "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz"
  tar -xzf "$tmp/trivy.tgz" -C "$tmp" trivy
  sudo mv "$tmp/trivy" /usr/local/bin/trivy
fi

kubeconform -v
gitleaks version
trivy --version
