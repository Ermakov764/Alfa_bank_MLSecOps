"""M3 LiteLLM-style proxy with G13 LLM-Guard middleware + G14 rate limit."""

from __future__ import annotations

import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fortress.audit import log_event  # noqa: E402

app = FastAPI(title="M3 Support NLP", version="1.0.0")
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
GUARD_ENABLED = os.getenv("LLM_GUARD_ENABLED", "true").lower() == "true"
_buckets: dict[str, list[float]] = defaultdict(list)

JAILBREAK_PATTERNS = [
    re.compile(r"ignore\s+previous\s+instructions", re.I),
    re.compile(r"reveal\s+(the\s+)?system\s+prompt", re.I),
    re.compile(r"bypass\s+(all\s+)?safety", re.I),
]


class ChatRequest(BaseModel):
    prompt: str
    model: str = "support-nlp"


class ChatResponse(BaseModel):
    reply: str
    model: str
    guarded: bool


def _rate_limit(client: str) -> None:
    now = time.time()
    w = _buckets[client]
    w[:] = [t for t in w if now - t < 60]
    if len(w) >= RATE_LIMIT:
        log_event("litellm", "api.rate_limited", status="blocked")
        raise HTTPException(429, "rate limit (G14)")
    w.append(now)


def _g13_check(prompt: str) -> tuple[bool, str]:
    if not GUARD_ENABLED:
        return True, ""
    for pat in JAILBREAK_PATTERNS:
        if pat.search(prompt):
            return False, pat.pattern
    if len(prompt) > 4000:
        return False, "prompt_too_long"
    return True, ""


def _mock_llm(prompt: str) -> str:
    p = prompt.lower()
    if "balance" in p or "счет" in p:
        return "Для проверки баланса откройте мобильное приложение → раздел «Счета»."
    if "card" in p or "карт" in p:
        return "По вопросам карты обратитесь в чат поддержки 24/7."
    return "Спасибо за обращение. Оператор уточнит детали в течение 5 минут."


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "guard": GUARD_ENABLED}


@app.post("/v1/chat/completions")
@app.post("/chat")
def chat(req: ChatRequest, request: Request) -> ChatResponse:
    client = request.client.host if request.client else "unknown"
    _rate_limit(client)

    ok, rule = _g13_check(req.prompt)
    if not ok:
        log_event("litellm", "llm.prompt_blocked", resource_type="api",
                  status="blocked", details={"rule": rule, "prompt_len": len(req.prompt)})
        raise HTTPException(403, f"prompt blocked by LLM-Guard (G13): {rule}")

    reply = _mock_llm(req.prompt)
    log_event("litellm", "api.inference", model_name="support-nlp", status="success",
              details={"prompt_len": len(req.prompt)})
    return ChatResponse(reply=reply, model=req.model, guarded=GUARD_ENABLED)
