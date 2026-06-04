#!/usr/bin/env python3
"""G6 — format policy: no .pkl in production bundles."""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.audit import log_event, log_finding  # noqa: E402

ALLOWED_SUFFIXES = {".onnx", ".cbm", ".json", ".safetensors", ".txt", ".yaml", ".yml"}
FORBIDDEN = {".pkl", ".pickle", ".joblib"}


def check(path: Path, actor: str = "system") -> int:
    corr = str(uuid.uuid4())
    if path.is_file():
        files = [path]
    else:
        files = list(path.rglob("*"))

    for f in files:
        if not f.is_file():
            continue
        suf = f.suffix.lower()
        if suf in FORBIDDEN:
            log_finding(
                "G6", "model", f.name, "forbidden_format_pkl",
                severity="critical", evidence={"path": str(f)}, correlation_id=corr,
            )
            log_event(
                actor, "gate.failed", resource_type="gate", resource_id="G6",
                status="failed", details={"file": str(f)}, correlation_id=corr,
            )
            print(f"G6 FAIL: forbidden format {f}")
            return 1

    log_event(
        actor, "gate.passed", resource_type="gate", resource_id="G6",
        status="success", details={"path": str(path)}, correlation_id=corr,
    )
    print("G6 PASS: format policy OK")
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("artifact_path", type=Path)
    p.add_argument("--actor", default="ds1")
    args = p.parse_args()
    sys.exit(check(args.artifact_path, args.actor))


if __name__ == "__main__":
    main()
