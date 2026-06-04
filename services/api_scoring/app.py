"""M1 credit-scoring FastAPI — Production models only + G14 rate limit."""

from __future__ import annotations

import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fortress.audit import log_event  # noqa: E402
from fortress.mlflow_client import get_production_version, get_version_tags  # noqa: E402

app = FastAPI(title="M1 Credit Scoring API", version="1.0.0")
MODEL_NAME = os.getenv("MODEL_NAME", "credit-scoring-pd")
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
_buckets: dict[str, list[float]] = defaultdict(list)
_session: ort.InferenceSession | None = None
_model_version: str | None = None


class PredictRequest(BaseModel):
    amount: float = Field(..., gt=0)
    age: int = Field(..., ge=18, le=100)


class PredictResponse(BaseModel):
    score: float
    decision: str
    model: str
    version: str


def _rate_limit(client: str) -> None:
    now = time.time()
    window = _buckets[client]
    window[:] = [t for t in window if now - t < 60]
    if len(window) >= RATE_LIMIT:
        log_event("api-scoring", "api.rate_limited", resource_type="api",
                  resource_id=client, status="blocked")
        raise HTTPException(429, "rate limit exceeded (G14)")
    window.append(now)


def _load_model() -> None:
    global _session, _model_version
    prod = get_production_version(MODEL_NAME)
    if not prod:
        _session = None
        return
    version, _ = prod
    tags = get_version_tags(MODEL_NAME, version)
    if tags.get("security.scan_status") != "passed":
        _session = None
        return
    onnx_local = ROOT / "models/m1_scoring/artifact/onnx/model.onnx"
    if not onnx_local.exists():
        _session = None
        return
    _session = ort.InferenceSession(str(onnx_local), providers=["CPUExecutionProvider"])
    _model_version = version


@app.on_event("startup")
def startup() -> None:
    try:
        _load_model()
    except Exception:
        pass


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model_loaded": str(_session is not None)}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest, request: Request) -> PredictResponse:
    client = request.client.host if request.client else "unknown"
    _rate_limit(client)

    prod = get_production_version(MODEL_NAME)
    if not prod:
        global _session, _model_version
        _session = None
        raise HTTPException(404, "model not in Production or retired")
    if _session is None or _model_version != prod[0]:
        _load_model()
    if _session is None:
        raise HTTPException(404, "model not in Production or not loaded")

    inp = np.array([[req.amount, req.age]], dtype=np.float32)
    input_name = _session.get_inputs()[0].name
    out = _session.run(None, {input_name: inp})[0]
    if out.ndim >= 2 and out.shape[1] > 1:
        score = float(out[0][1])
    elif out.ndim >= 1:
        score = float(out.flatten()[0])
    else:
        score = float(out)
    decision = "approve" if score < 0.5 else "review"

    log_event("api-scoring", "api.inference", resource_type="api",
              model_name=MODEL_NAME, model_version=_model_version or "?",
              status="success", details={"decision": decision})

    return PredictResponse(
        score=round(score, 4),
        decision=decision,
        model=MODEL_NAME,
        version=_model_version or "0",
    )
