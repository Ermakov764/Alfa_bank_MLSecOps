#!/usr/bin/env python3
"""CLI: register dataset in Postgres + DATA gate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.dataset_registry import ingest_dataset  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("csv_path", type=Path)
    p.add_argument("--name", required=True)
    p.add_argument("--version", default="v1")
    p.add_argument("--expected-cols", default="amount,age,target")
    p.add_argument("--actor", default="system")
    args = p.parse_args()
    ok, msg = ingest_dataset(
        args.csv_path, args.name, args.version, args.actor,
        expected_cols=args.expected_cols,
    )
    print(msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
