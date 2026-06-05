#!/usr/bin/env bash
# G0 — secrets scan
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="${ARTIFACTS_DIR:-$ROOT/artifacts}/gates"
mkdir -p "$OUT"

STRICT="${GATE_STRICT:-false}"

if command -v gitleaks >/dev/null 2>&1; then
  CFG_ARGS=()
  if [ -f ".gitleaks.toml" ]; then
    CFG_ARGS+=(--config ".gitleaks.toml")
  fi
  gitleaks detect --source . --no-git -v "${CFG_ARGS[@]}" --report-path "$OUT/gitleaks.json" || exit 1
  echo "G0 PASS (gitleaks)"
  exit 0
fi

if [ "$STRICT" = "true" ]; then
  echo "G0 FAIL: gitleaks required in GATE_STRICT mode"
  exit 1
fi

# Fallback (non-strict only): scan for obvious secret patterns
python3 - <<'PY'
import re, sys
from pathlib import Path
root = Path(".")
patterns = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"password\s*=\s*['\"][^'\"]+['\"]", re.I),
]
bad = []
for p in list(root.glob("**/*"))[:500]:
    if p.is_file() and p.suffix in {".py", ".env", ".yaml", ".yml", ".sh"}:
        if "node_modules" in str(p) or ".venv" in str(p):
            continue
        try:
            t = p.read_text(errors="ignore")
        except Exception:
            continue
        for pat in patterns:
            if pat.search(t) and ".example" not in p.name:
                bad.append(str(p))
if bad:
    print("G0 FAIL (fallback):", bad[:5])
    sys.exit(1)
print("G0 PASS (fallback scanner)")
PY
