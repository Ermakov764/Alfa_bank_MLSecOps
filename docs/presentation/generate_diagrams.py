#!/usr/bin/env python3
"""Entry point: render doc-based Mermaid diagrams for presentation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    return subprocess.call([sys.executable, str(ROOT / "render_diagrams.py")])


if __name__ == "__main__":
    raise SystemExit(main())
