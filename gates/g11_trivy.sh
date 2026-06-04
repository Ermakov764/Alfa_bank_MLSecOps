#!/usr/bin/env bash
# G11 — Trivy container scan (CRITICAL = fail)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

IMAGE="${1:-alfa_bank_mlsecops-api-scoring:latest}"
OUT="${ARTIFACTS_DIR:-$ROOT/artifacts}/gates"
mkdir -p "$OUT"

scan_image() {
  local img="$1"
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    echo "G11: building $img..."
    docker compose build api-scoring >/dev/null 2>&1 || true
    img="$(docker compose images api-scoring -q 2>/dev/null | head -1)"
    if [ -n "$img" ]; then
      docker tag "$img" "$1" 2>/dev/null || true
    fi
  fi
  local out_json="$OUT/trivy_${1//[:\/]/_}.json"
  local trivy_args=(
    image --severity CRITICAL --exit-code 1 --format json
    --pkg-types library
    --ignore-unfixed
    -o "$out_json" "$1"
  )
  if command -v trivy >/dev/null 2>&1; then
    trivy "${trivy_args[@]}"
    return $?
  fi
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$OUT:/out" aquasec/trivy:latest \
    image --severity CRITICAL --exit-code 1 --pkg-types library --ignore-unfixed \
    -o "/out/trivy_${1//[:\/]/_}.json" "$1"
}

FAILED=0
for img in "${IMAGE}" "alfa_bank_mlsecops-api-antifraud:latest"; do
  if scan_image "$img"; then
    echo "G11 PASS: $img"
  else
    echo "G11 FAIL: CRITICAL CVE in $img"
    FAILED=1
  fi
done
exit $FAILED
