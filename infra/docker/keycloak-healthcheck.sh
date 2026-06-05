#!/usr/bin/env bash
# Keycloak 24 dev mode: /health/* needs KC_HEALTH_ENABLED + kc build; realm probe works out of the box.
set -euo pipefail
PROBE_PATH="${KEYCLOAK_HEALTH_PATH:-/realms/mlsecops}"
exec 3<>/dev/tcp/127.0.0.1/8080
printf 'GET %s HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n' "$PROBE_PATH" >&3
read -r line <&3 || true
exec 3<&-
exec 3>&-
echo "$line" | grep -q '200'
