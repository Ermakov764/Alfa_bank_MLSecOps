"""Strict verification: platform pipeline gates (DATA + code)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_CODE = ("G0", "G1", "G3", "G3b")
REQUIRED_DATA = ("DATA",)


def _sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pipeline_run_status(run_id: str) -> dict[str, list[dict[str, str]]]:
    from fortress.pipeline import fetch_pipeline_runs

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in fetch_pipeline_runs(run_id, 500):
        el = row.get("element") or ""
        grouped.setdefault(el, []).append(row)
    return grouped


def _last_status(rows: list[dict], gate: str) -> str | None:
    matches = [r for r in rows if (r.get("gate") or "") == gate]
    if not matches:
        return None
    return str(matches[-1].get("status"))


def verify_pipeline_run(
    run_id: str,
    *,
    require_db: bool = False,
    require_data: bool = True,
) -> tuple[bool, list[str]]:
    """Verify DATA + code gates recorded as passed for this run_id."""
    errors: list[str] = []
    try:
        grouped = load_pipeline_run_status(run_id)
    except Exception as exc:
        if require_db:
            return False, [f"pipeline_runs unavailable: {exc}"]
        grouped = {}

    if not grouped:
        from fortress.pipeline import load_local_runs

        local = load_local_runs(run_id)
        if local:
            grouped = {}
            for row in local:
                el = row.get("element") or ""
                grouped.setdefault(el, []).append(row)

    if require_data:
        data_rows = grouped.get("data", [])
        if data_rows:
            st = _last_status(data_rows, "DATA")
            if st != "passed":
                errors.append(f"DATA gate status={st}")
        else:
            errors.append("DATA gate not recorded in pipeline_runs")

    code_rows = grouped.get("code", [])
    for g in REQUIRED_CODE:
        st = _last_status(code_rows, g)
        if st != "passed":
            errors.append(f"{g} status={st}")

    return len(errors) == 0, errors


def build_attestation_elements(
    run_id: str,
    *,
    dataset_path: Path | None = None,
    include_data: bool = True,
) -> dict[str, Any]:
    elements: dict[str, Any] = {
        "code": {
            "status": "passed",
            "gates": list(REQUIRED_CODE),
        },
    }
    if include_data:
        ds = dataset_path or ROOT / "data/datasets/train_clean.csv"
        elements["data"] = {
            "status": "passed",
            "gates": list(REQUIRED_DATA),
            "digest": f"sha256:{_sha256(ds)}",
        }
    elements["platform"] = {
        "status": "passed",
        "note": "model gates run at upload/deploy for user models in MLflow",
        "run_id": run_id,
    }
    return elements
