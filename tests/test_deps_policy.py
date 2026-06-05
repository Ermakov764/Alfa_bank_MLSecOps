"""G4 dependency policy tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_deps_policy_passes_on_repo_requirements() -> None:
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_deps_policy.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
