#!/usr/bin/env bash
# Prepare the local TaskFlow stack.
# Kubernetes checks are intentionally not part of this script yet.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

echo "TaskFlow local setup"
echo

if ! command -v python3 >/dev/null 2>&1; then
  fail "python3 is not installed."
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("ERROR: python3 3.11 or newer is required.")
print(f"python3: {sys.version.split()[0]}")
PY

if ! command -v docker >/dev/null 2>&1; then
  fail "Docker is not installed. Install Docker Engine and the Compose plugin, then run make setup again."
fi

if ! docker info >/dev/null 2>&1; then
  fail "Docker is installed, but the daemon is not reachable. Start Docker and run make setup again."
fi
echo "docker: $(docker --version)"

if ! docker compose version >/dev/null 2>&1; then
  fail "Docker Compose v2 is not available (docker compose). Install the Compose plugin."
fi
echo "compose: $(docker compose version --short 2>/dev/null || docker compose version)"

if [[ ! -f taskflow/.env ]]; then
  python3 - <<'PY'
from pathlib import Path
import secrets
example = Path("taskflow/.env.example").read_text()
password = secrets.token_urlsafe(18)
Path("taskflow/.env").write_text(
    example.replace("replace-with-a-local-password", password)
)
print("Created taskflow/.env with a generated local database password.")
PY
else
  echo "taskflow/.env already exists."
fi

if [[ ! -x taskflow/backend/.venv/bin/pytest ]]; then
  python3 -m venv taskflow/backend/.venv
  taskflow/backend/.venv/bin/pip install -q -r taskflow/backend/requirements-dev.txt
  echo "Installed backend test dependencies."
else
  echo "Backend virtualenv already exists."
fi

echo
echo "Local prerequisites look good."
echo "Kubernetes is not required for Docker Compose."
echo "Next: make test"
echo "Then: make local"
echo "Open: http://127.0.0.1:41821"
echo "Cluster deploy, when kubectl can reach a cluster: make deploy"
