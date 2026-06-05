"""Production inference feature/score snapshots for G15 drift monitoring."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MON_DIR = Path(os.getenv("FORTRESS_MONITOR_DIR", str(ROOT / "artifacts" / "monitoring")))


def _path(model_key: str) -> Path:
    MON_DIR.mkdir(parents=True, exist_ok=True)
    return MON_DIR / f"inference_{model_key}.jsonl"


def record(
    model_key: str,
    *,
    features: dict[str, Any],
    score: float | None = None,
    label: int | None = None,
    service: str = "api",
) -> None:
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "service": service,
        "features": features,
        "score": score,
        "label": label,
    }
    with _path(model_key).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def load_dataframe(model_key: str):
    import pandas as pd

    p = _path(model_key)
    if not p.exists():
        return pd.DataFrame()
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        flat = {**obj.get("features", {})}
        if obj.get("score") is not None:
            flat["score"] = obj["score"]
        if obj.get("label") is not None:
            flat["label"] = obj["label"]
        rows.append(flat)
    return pd.DataFrame(rows)


def write_baseline_metrics(model_key: str, metrics: dict[str, float]) -> Path:
    MON_DIR.mkdir(parents=True, exist_ok=True)
    p = MON_DIR / f"baseline_{model_key}.json"
    p.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return p


def load_baseline_metrics(model_key: str) -> dict[str, float]:
    p = MON_DIR / f"baseline_{model_key}.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))
