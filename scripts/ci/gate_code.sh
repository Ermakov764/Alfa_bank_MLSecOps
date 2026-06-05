#!/usr/bin/env bash
# Element 2: Code gates G0 G1 G2 G3 G3b G4 (strict — real tools in fortress image)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
export GATE_STRICT="${GATE_STRICT:-true}"
PYTHON="${PYTHON:-python3}"
RUN_ID="${RUN_ID:-local}"
CORR="${CORRELATION_ID:-local}"
OUT="${ARTIFACTS_DIR:-$ROOT/artifacts}/gates"
mkdir -p "$OUT"
chmod +x gates/*.sh

_install_gitleaks() {
  if command -v gitleaks >/dev/null 2>&1; then
    return 0
  fi
  # CI runner does not have gitleaks by default; fallback scanner is too naive.
  # Install a pinned binary so G0 uses real gitleaks rules.
  if ! command -v curl >/dev/null 2>&1; then
    echo "gitleaks install skipped: curl not found" >&2
    return 1
  fi
  local ver="${GITLEAKS_VERSION:-8.18.4}"
  local url="https://github.com/gitleaks/gitleaks/releases/download/v${ver}/gitleaks_${ver}_linux_x64.tar.gz"
  echo "Installing gitleaks v${ver}..."
  tmpdir="$(mktemp -d)"
  curl -fsSL "$url" -o "$tmpdir/gitleaks.tgz"
  tar -xzf "$tmpdir/gitleaks.tgz" -C "$tmpdir"
  install -m 0755 "$tmpdir/gitleaks" /usr/local/bin/gitleaks
  rm -rf "$tmpdir"
  gitleaks version || true
}

_install_gitleaks || true

run_one() {
  local gate="$1" cmd="$2"
  "$PYTHON" scripts/ci/report_gate.py --run-id "$RUN_ID" --element code \
    --gate "$gate" --status started --correlation-id "$CORR" || true
  if eval "$cmd"; then
    "$PYTHON" scripts/ci/report_gate.py --run-id "$RUN_ID" --element code \
      --gate "$gate" --status passed --correlation-id "$CORR" \
      --report "$OUT/${gate}_report.json"
  else
    "$PYTHON" scripts/ci/report_gate.py --run-id "$RUN_ID" --element code \
      --gate "$gate" --status failed --correlation-id "$CORR" --message "$gate failed"
    exit 1
  fi
}

run_one G0 "gates/gitleaks.sh"
run_one G1 "gates/semgrep.sh"
run_one G2 "gates/g2_bandit.sh"
run_one G3 "gates/pip_audit.sh"
run_one G3b "gates/guarddog.sh"
run_one G4 "$PYTHON scripts/check_deps_policy.py"
echo "gate-code: PASS"
