#!/usr/bin/env bash
# Replay one sanitized fixture through the KubeMedic investigation pipeline.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/kubemedic"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi

export KUBEMEDIC_DB_PATH="${KUBEMEDIC_DB_PATH:-$ROOT/data/kubemedic.db}"
export KUBEMEDIC_DEMO_MODE="${KUBEMEDIC_DEMO_MODE:-true}"
mkdir -p "$(dirname "$KUBEMEDIC_DB_PATH")"

if [[ $# -eq 0 ]]; then
  echo "KubeMedic fixture replay"
  echo
  echo "Usage: ./scripts/kubemedic-demo.sh <scenario>"
  echo
  echo "Scenarios:"
  echo "  crashloop"
  echo "  bad-image"
  echo "  oom"
  echo "  missing-secret"
  echo "  failed-scheduling"
  echo "  readiness"
  echo "  database"
  echo
  echo "Start the dashboard first with: make kubemedic"
  echo "Both commands use $KUBEMEDIC_DB_PATH"
  exit 0
fi

exec .venv/bin/python -m app.demo "$@"
