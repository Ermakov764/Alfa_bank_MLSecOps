#!/usr/bin/env bash
# G11 — Trivy container scan (CRITICAL = fail)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TAG="${IMAGE_TAG:-latest}"
USER="${DOCKERHUB_USER:-rinakt}"
OUT="${ARTIFACTS_DIR:-$ROOT/artifacts}/gates"
mkdir -p "$OUT"

scan_image() {
  local img="$1"
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    echo "G11 FAIL: image not found: $img (run docker compose build first)"
    return 1
  fi
  local safe="${img//[:\/]/_}"
  local out_json="$OUT/trivy_${safe}.json"
  local trivy_args=(
    image --severity CRITICAL --exit-code 1 --format json
    --pkg-types library
    --ignore-unfixed
    -o "$out_json" "$img"
  )
  if command -v trivy >/dev/null 2>&1; then
    trivy "${trivy_args[@]}"
    return $?
  fi
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$OUT:/out" aquasec/trivy:latest \
    image --severity CRITICAL --exit-code 1 --pkg-types library --ignore-unfixed \
    -o "/out/trivy_${safe}.json" "$img"
}

FAILED=0
for svc in api-scoring api-antifraud litellm; do
  img="${USER}/mlsecops-${svc}:${TAG}"
  if scan_image "$img"; then
    echo "G11 PASS: $img"
  else
    echo "G11 FAIL: CRITICAL CVE in $img"
    FAILED=1
  fi
done
exit $FAILED
