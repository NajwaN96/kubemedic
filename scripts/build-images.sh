#!/usr/bin/env bash
# Build the three production images. Refuses the floating tag "latest".
# The KubeMedic remediator uses the kubemedic image with a different command.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <immutable-tag> [extra-tag...]" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed." >&2
  exit 1
fi

tags=()
for tag in "$@"; do
  if [[ "$tag" == "latest" || "$tag" == *:latest ]]; then
    echo "Refusing to tag an image as latest." >&2
    exit 1
  fi
  if [[ ! "$tag" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]]; then
    echo "Tag is not an immutable identifier: $tag" >&2
    exit 1
  fi
  tags+=("$tag")
done

build() {
  local name="$1"
  local dockerfile="$2"
  local context="$3"
  local args=()
  local tag
  for tag in "${tags[@]}"; do
    args+=(-t "${name}:${tag}")
  done
  docker build "${args[@]}" -f "$dockerfile" "$context"
}

build taskflow-api taskflow/backend/Dockerfile taskflow/backend
build taskflow-frontend taskflow/frontend/Dockerfile taskflow/frontend
build kubemedic kubemedic/Dockerfile kubemedic

echo "Built images:"
for tag in "${tags[@]}"; do
  echo "  taskflow-api:${tag}"
  echo "  taskflow-frontend:${tag}"
  echo "  kubemedic:${tag}"
done
