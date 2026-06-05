"""Запуск platform pipeline из приложения."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_pipeline(*, actor: str = "system") -> tuple[bool, str]:
    script = ROOT / "scripts" / "ci" / "run_pipeline.py"
    if not script.exists():
        return False, f"pipeline script not found: {script}"

    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT),
        "PIPELINE_ACTOR": actor,
    }
    r = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=int(os.getenv("PIPELINE_TIMEOUT_SEC", "3600")),
    )
    out = (r.stdout or "") + (r.stderr or "")
    tail = out[-8000:] if len(out) > 8000 else out
    if r.returncode != 0:
        return False, tail or f"pipeline exit {r.returncode}"
    return True, tail or "Pipeline OK"
