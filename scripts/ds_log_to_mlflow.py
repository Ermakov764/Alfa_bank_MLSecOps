#!/usr/bin/env python3
"""
Загрузка с локального компьютера в MLflow (любые пути, любые файлы).

Примеры:
  python scripts/ds_log_to_mlflow.py --file C:\\Users\\me\\data\\train.csv
  python scripts/ds_log_to_mlflow.py --dir ~/projects/my_ds/data --experiment fraud-v2
  python scripts/ds_log_to_mlflow.py --file ./model.onnx --file ./metrics.json --run-name exp-42
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.ds_mlflow_upload import DEFAULT_EXPERIMENT, collect_paths, log_local_files  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Загрузить локальные файлы в MLflow")
    p.add_argument("--file", action="append", default=[], help="Путь к файлу (можно несколько раз)")
    p.add_argument("--dir", action="append", default=[], help="Путь к папке (можно несколько раз)")
    p.add_argument("--experiment", default=DEFAULT_EXPERIMENT, help="Имя эксперимента MLflow")
    p.add_argument("--run-name", default="local-upload", help="Имя run")
    p.add_argument("--owner", default=os.getenv("USER", os.getenv("USERNAME", "ds")))
    p.add_argument(
        "--tracking-uri",
        default=os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"),
        help="MLflow tracking URI",
    )
    args = p.parse_args()

    paths = collect_paths(args.file + args.dir)
    if not paths:
        p.error("Укажите --file и/или --dir")

    os.environ["MLFLOW_TRACKING_URI"] = args.tracking_uri
    os.environ.setdefault("MLFLOW_S3_ENDPOINT_URL", os.getenv("MLFLOW_S3_ENDPOINT_URL", "http://localhost:9000"))
    os.environ.setdefault("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", "minio"))
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", "changeme"))

    run_id, uri = log_local_files(
        paths,
        experiment=args.experiment,
        run_name=args.run_name,
        owner=args.owner,
    )
    print(f"OK run_id={run_id}")
    print(f"artifact_uri={uri}")
    print(f"MLflow UI: {args.tracking_uri.rstrip('/')}/#/experiments")


if __name__ == "__main__":
    main()
