#!/usr/bin/env bash
# Keycloak image has no curl; probe /health/ready via bash TCP or curl if present.
set -euo pipefail
URL="http://127.0.0.1:8080/health/ready"
if command -v curl >/dev/null 2>&1; then
  curl -fsS "$URL" >/dev/null
  exit 0
fi
exec 3<>/dev/tcp/127.0.0.1/8080
printf 'GET /health/ready HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n' >&3
read -r line <&3 || true
exec 3<&-
exec 3>&-
echo "$line" | grep -q '200'
