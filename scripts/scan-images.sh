#!/usr/bin/env bash
# Write HIGH and CRITICAL image reports and CycloneDX SBOMs.
# Upstream base-image findings do not fail this script. The reports are the
# supply-chain record. See the CI section of the README for that choice.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <image-tag>" >&2
  exit 1
fi
if ! command -v trivy >/dev/null 2>&1; then
  echo "trivy is not installed. CI installs v0.74.0." >&2
  exit 1
fi

tag="$1"
if [[ "$tag" == "latest" ]]; then
  echo "Refusing to scan a latest tag as the release identifier." >&2
  exit 1
fi

out="${ROOT}/ci-reports"
rm -rf "$out"
mkdir -p "$out"

images=(taskflow-api taskflow-frontend kubemedic)
for name in "${images[@]}"; do
  ref="${name}:${tag}"
  if ! docker image inspect "$ref" >/dev/null 2>&1; then
    echo "Image ${ref} is not present." >&2
    exit 1
  fi
  trivy image \
    --severity HIGH,CRITICAL \
    --exit-code 0 \
    --format json \
    --output "${out}/${name}.vuln.json" \
    "$ref"
  trivy image \
    --format cyclonedx \
    --exit-code 0 \
    --output "${out}/${name}.cdx.json" \
    "$ref"
  python3 - "$out/${name}.vuln.json" "$ref" <<'PY'
import json
import sys
from collections import Counter

path, ref = sys.argv[1], sys.argv[2]
data = json.load(open(path))
counts = Counter()
for result in data.get("Results") or []:
    for item in result.get("Vulnerabilities") or []:
        state = "fixed" if item.get("FixedVersion") else "unfixed"
        counts[(item.get("Severity") or "UNKNOWN", state)] += 1
print(ref)
for key in sorted(counts):
    print(f"  {key[0]} {key[1]}: {counts[key]}")
if not counts:
    print("  no HIGH or CRITICAL findings")
PY
done

{
  echo "tag=${tag}"
  for name in "${images[@]}"; do
    digest="$(docker image inspect --format '{{.Id}}' "${name}:${tag}")"
    echo "${name}:${tag} ${digest}"
  done
} > "${out}/image-ids.txt"

echo "Reports written to ${out}"
