"""M2 antifraud FastAPI inference service."""

from __future__ import annotations

import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fortress.artifact_integrity import verify_manifest  # noqa: E402
from fortress.audit import log_event  # noqa: E402
from fortress.inference_telemetry import record as record_telemetry  # noqa: E402
from fortress.mlflow_client import get_production_version, get_version_tags  # noqa: E402

app = FastAPI(title="M2 Antifraud API", version="1.0.0")
MODEL_NAME = os.getenv("MODEL_NAME", "transaction-antifraud")
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
_buckets: dict[str, list[float]] = defaultdict(list)
_session: ort.InferenceSession | None = None
_model_version: str | None = None


class TxRequest(BaseModel):
    amount: float
    age: int = 35
    velocity: float = 0.5
    merchant_risk: float = 0.3


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_loaded": _session is not None}


def _rate_limit(client: str) -> None:
    now = time.time()
    w = _buckets[client]
    w[:] = [t for t in w if now - t < 60]
    if len(w) >= RATE_LIMIT:
        log_event("api-antifraud", "api.rate_limited", status="blocked")
        raise HTTPException(429, "rate limit (G14)")
    w.append(now)


def _load() -> None:
    global _session, _model_version
    prod = get_production_version(MODEL_NAME)
    if not prod:
        return
    version, _ = prod
    tags = get_version_tags(MODEL_NAME, version)
    if tags.get("security.scan_status") != "passed":
        return
    path = ROOT / "artifacts/models/m2_antifraud/onnx/model.onnx"
    if not path.exists():
        path = ROOT / "models/m2_antifraud/artifact/onnx/model.onnx"
    if path.exists():
        ok, msg = verify_manifest(path)
        if not ok:
            log_event("api-antifraud", "api.integrity_failed", status="failed", details={"error": msg})
            return
        _session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        _model_version = version


@app.on_event("startup")
def startup() -> None:
    try:
        _load()
    except Exception:
        pass


@app.post("/predict")
def predict(req: TxRequest, request: Request) -> dict:
    client = request.client.host if request.client else "unknown"
    _rate_limit(client)
    if _session is None:
        _load()
    if _session is None:
        raise HTTPException(404, "model retired or not in Production")

    x = np.array([[req.amount, req.age, req.velocity, req.merchant_risk]], dtype=np.float32)
    name = _session.get_inputs()[0].name
    out = _session.run(None, {name: x})[0]
    if out.ndim >= 2 and out.shape[1] > 1:
        fraud_prob = float(out[0][1])
    else:
        fraud_prob = float(out.flatten()[0])

    log_event("api-antifraud", "api.inference", model_name=MODEL_NAME,
              model_version=_model_version or "?", status="success")
    record_telemetry(
        "m2",
        features={
            "amount": req.amount,
            "age": req.age,
            "velocity": req.velocity,
            "merchant_risk": req.merchant_risk,
        },
        score=fraud_prob,
        service="api-antifraud",
    )
    return {"fraud_probability": round(fraud_prob, 4), "block": fraud_prob > 0.6}
