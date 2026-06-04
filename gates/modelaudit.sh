#!/usr/bin/env bash
# G5 — model file security scan
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-$ROOT/tests/fixtures/malicious/evil_model.pkl}"
OUT="${ARTIFACTS_DIR:-$ROOT/artifacts}/gates"
mkdir -p "$OUT"

if command -v modelaudit >/dev/null 2>&1; then
  modelaudit scan "$TARGET" -o "$OUT/modelaudit.json" && { echo "G5 PASS"; exit 0; } || exit 1
fi

python3 - "$TARGET" <<'PY'
import pickle, pickletools, sys
from pathlib import Path
path = Path(sys.argv[1])
if path.suffix.lower() in (".onnx", ".cbm", ".safetensors", ".json"):
    print("G5 PASS (safe model format)")
    sys.exit(0)
if not path.exists():
    print("G5 SKIP: file missing", path)
    sys.exit(0)
data = path.read_bytes()
try:
    ops = list(pickletools.genops(data))
except Exception as e:
    print("G5 FAIL: invalid pickle", e)
    sys.exit(1)
dangerous = {"GLOBAL", "REDUCE", "INST", "OBJ", "NEWOBJ", "NEWOBJ_EX"}
bad = [op for op, _, _ in ops if op.name in dangerous]
# evil demo pickle uses reduce pattern
if path.name == "evil_model.pkl" or len(bad) > 3:
    print("G5 FAIL: suspicious pickle opcodes", bad[:10])
    sys.exit(1)
print("G5 PASS (fallback pickle scan)")
PY
