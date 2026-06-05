#!/usr/bin/env python3
"""CLI wrapper for fortress.data_gate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.data_gate import run_gate  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="DATA pre-train gate")
    p.add_argument("csv_path", type=Path)
    p.add_argument("--expected-cols", type=str, default="")
    p.add_argument("--actor", default="system")
    args = p.parse_args()
    cols = [c.strip() for c in args.expected_cols.split(",") if c.strip()] or None
    code, rule = run_gate(args.csv_path, cols, actor=args.actor)
    if rule:
        print(rule, file=sys.stderr)
    sys.exit(code)


if __name__ == "__main__":
    main()
