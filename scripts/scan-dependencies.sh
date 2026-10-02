#!/usr/bin/env bash
# Fail when a pinned application dependency has a fixed HIGH or CRITICAL CVE.
# Image scans are separate. They report upstream base-image findings and do
# not use this exit code.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v trivy >/dev/null 2>&1; then
  echo "trivy is not installed. CI installs v0.74.0." >&2
  exit 1
fi

trivy fs \
  --scanners vuln \
  --severity HIGH,CRITICAL \
  --ignore-unfixed \
  --exit-code 1 \
  --skip-dirs .venv \
  --skip-dirs node_modules \
  --skip-dirs .git \
  --skip-dirs taskflow/frontend/dist \
  .
