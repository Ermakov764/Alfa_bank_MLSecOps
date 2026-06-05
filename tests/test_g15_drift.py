"""G15 Evidently drift gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("evidently")

ROOT = Path(__file__).resolve().parents[1]


def test_g15_passes_after_telemetry_seed() -> None:
    seed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/ci/seed_inference_telemetry.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert seed.returncode == 0, seed.stderr + seed.stdout
    drift = subprocess.run(
        [sys.executable, str(ROOT / "scripts/gates/g15_drift.py"), "m1"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert drift.returncode == 0, drift.stderr + drift.stdout
    assert "G15 PASS" in drift.stdout
