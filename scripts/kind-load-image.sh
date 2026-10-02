#!/usr/bin/env bash
# Copy local Docker images into the kind node.
# kind's default importer fails on the native snapshotter ("no unpack platforms").
# A local ctr import unpacks those images correctly.
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <cluster> <image> [image...]" >&2
  exit 1
fi

cluster="$1"
shift
node="${cluster}-control-plane"
snapshotter="$(docker exec "$node" awk -F'"' '/^[[:space:]]*snapshotter = /{print $2; exit}' /etc/containerd/config.toml)"

stamp_dir="/tmp/kind-image-stamps/${cluster}"
mkdir -p "$stamp_dir"

for image in "$@"; do
  host_id="$(docker image inspect --format '{{.Id}}' "$image")"
  stamp="${stamp_dir}/$(printf '%s' "$image" | tr '/:' '__')"
  previous=""
  if [[ -f "$stamp" ]]; then
    previous="$(cat "$stamp")"
  fi
  on_node=false
  if docker exec "$node" ctr --namespace=k8s.io images ls -q | grep -qx "docker.io/library/${image}"; then
    on_node=true
  fi
  if [[ "$on_node" == true && "$previous" == "$host_id" ]]; then
    echo "Image ${image} is already on ${node}."
    continue
  fi
  if [[ "$snapshotter" == "native" ]]; then
    echo "Importing ${image} with the native snapshotter."
    docker save "$image" | docker exec -i "$node" ctr --namespace=k8s.io images import --snapshotter native --local -
  else
    kind load docker-image "$image" --name "$cluster"
  fi
  printf '%s\n' "$host_id" > "$stamp"
done
