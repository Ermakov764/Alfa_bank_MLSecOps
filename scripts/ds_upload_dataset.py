#!/usr/bin/env python3
"""CLI: CSV → DATA gate → MLflow (опционально, для pipeline FORTRESS)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.dataset_registry import ingest_dataset  # noqa: E402
from fortress.mlflow_datasets import register_from_mlflow_run  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(
        description="Регистрация CSV в FORTRESS (DATA gate + MLflow fortress-datasets)",
    )
    p.add_argument(
        "--tracking-uri",
        default=os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    up = sub.add_parser("upload", help="CSV с любого локального пути")
    up.add_argument("csv_path", type=Path, help="Например C:\\Users\\you\\data.csv")
    up.add_argument("--name", required=True)
    up.add_argument("--version", default="v1")
    up.add_argument(
        "--expected-cols",
        default="",
        help="Колонки через запятую; пусто = только poison/PII/nulls",
    )
    up.add_argument("--actor", default=os.getenv("USERNAME", "ds"))

    val = sub.add_parser("validate-run", help="Проверить MLflow run после Jupyter")
    val.add_argument("run_id")
    val.add_argument("--expected-cols", default="")
    val.add_argument("--actor", default=os.getenv("USERNAME", "ds"))

    args = p.parse_args()
    os.environ["MLFLOW_TRACKING_URI"] = args.tracking_uri

    if args.cmd == "upload":
        ok, msg = ingest_dataset(
            args.csv_path.expanduser().resolve(),
            args.name,
            args.version,
            args.actor,
            expected_cols=args.expected_cols,
        )
        print(msg)
        sys.exit(0 if ok else 1)

    ok, msg, _ = register_from_mlflow_run(
        args.run_id, args.actor, expected_cols=args.expected_cols,
    )
    print(msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
