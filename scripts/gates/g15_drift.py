#!/usr/bin/env python3
"""G15 — production drift (Evidently PSI) + metric degradation vs training baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fortress.inference_telemetry import load_baseline_metrics, load_dataframe  # noqa: E402

PSI_FAIL_THRESHOLD = float(__import__("os").environ.get("G15_PSI_THRESHOLD", "0.2"))
METRIC_DROP_MAX = float(__import__("os").environ.get("G15_METRIC_DROP", "0.15"))


def _reference_frame(model_key: str) -> pd.DataFrame:
    csv_path = ROOT / "data/datasets/train_clean.csv"
    df = pd.read_csv(csv_path)
    if model_key == "m2":
        rng = np.random.default_rng(42)
        df = df.copy()
        df["velocity"] = rng.uniform(0, 1, len(df))
        df["merchant_risk"] = rng.uniform(0, 1, len(df))
        return df[["amount", "age", "velocity", "merchant_risk"]]
    return df[["amount", "age"]]


def _evidently_drift(ref: pd.DataFrame, cur: pd.DataFrame) -> tuple[bool, str, dict]:
    from evidently import ColumnMapping
    from evidently.metric_preset import DataDriftPreset
    from evidently.report import Report

    common = [c for c in ref.columns if c in cur.columns]
    if not common:
        return False, "no common feature columns", {}
    ref = ref[common].copy()
    cur = cur[common].copy()
    for col in common:
        ref[col] = pd.to_numeric(ref[col], errors="coerce")
        cur[col] = pd.to_numeric(cur[col], errors="coerce")
    ref = ref.dropna()
    cur = cur.dropna()
    if len(cur) < 5:
        return False, f"insufficient production samples: {len(cur)} (need >= 5)", {}

    mapping = ColumnMapping(numerical_features=common)
    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=ref, current_data=cur, column_mapping=mapping)
    payload = report.as_dict()
    metrics = payload.get("metrics", [])
    dataset_drift = False
    max_psi = 0.0
    for block in metrics:
        result = block.get("result") or {}
        if block.get("metric") == "DatasetDriftMetric":
            dataset_drift = bool(result.get("dataset_drift"))
        if block.get("metric") == "DataDriftTable":
            drift_by = result.get("drift_by_columns") or {}
            if isinstance(drift_by, dict):
                for row in drift_by.values():
                    psi = row.get("drift_score") if isinstance(row, dict) else None
                    if psi is not None:
                        max_psi = max(max_psi, float(psi))

    stats = {"dataset_drift": dataset_drift, "max_psi": max_psi, "rows": len(cur)}
    if dataset_drift or max_psi >= PSI_FAIL_THRESHOLD:
        return False, f"drift detected (dataset_drift={dataset_drift}, max_psi={max_psi:.3f})", stats
    return True, "ok", stats


def _metric_degradation(model_key: str, cur: pd.DataFrame) -> tuple[bool, str]:
    baseline = load_baseline_metrics(model_key)
    if not baseline or "accuracy" not in baseline:
        return True, "no baseline (skipped)"
    if "label" not in cur.columns or "score" not in cur.columns:
        return True, "no labeled production batch (skipped)"
    labeled = cur.dropna(subset=["label", "score"])
    if len(labeled) < 5:
        return True, "insufficient labeled production rows"
    pred = (labeled["score"].astype(float) >= 0.5).astype(int)
    live_acc = float((pred == labeled["label"].astype(int)).mean())
    base_acc = float(baseline["accuracy"])
    drop = base_acc - live_acc
    if drop > METRIC_DROP_MAX:
        return False, f"metric degradation: baseline={base_acc:.3f} live={live_acc:.3f} drop={drop:.3f}"
    return True, f"live accuracy {live_acc:.3f} vs baseline {base_acc:.3f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", choices=("m1", "m2"), default="m1", nargs="?")
    args = parser.parse_args()

    ref = _reference_frame(args.model)
    cur = load_dataframe(args.model)
    ok, msg, stats = _evidently_drift(ref, cur)
    if not ok:
        print(f"G15 FAIL: {msg}")
        return 1
    m_ok, m_msg = _metric_degradation(args.model, cur)
    if not m_ok:
        print(f"G15 FAIL: {m_msg}")
        return 1

    out = ROOT / "artifacts/gates/g15_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"drift": stats, "metrics": m_msg}, indent=2), encoding="utf-8")
    print(f"G15 PASS: drift {stats}; metrics: {m_msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
