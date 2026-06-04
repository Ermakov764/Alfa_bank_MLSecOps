#!/usr/bin/env python3
"""Sign pipeline attestation after all gates + train passed."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fortress.attestation import build_attestation, ensure_keypair, save_signed, sign_attestation  # noqa: E402
from fortress.pipeline import record_pipeline_step  # noqa: E402


def _digest(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "local"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    p.add_argument("--model", default="credit-scoring-pd")
    p.add_argument("--model-key", default="m1")
    p.add_argument("--correlation-id", default=os.getenv("CORRELATION_ID", ""))
    args = p.parse_args()

    corr = args.correlation_id or args.run_id
    ensure_keypair()

    dataset = ROOT / "data/datasets/train_clean.csv"
    elements = {
        "data": {
            "status": "passed",
            "gates": ["DATA"],
            "digest": f"sha256:{_digest(dataset)}",
        },
        "code": {
            "status": "passed",
            "gates": ["G0", "G1", "G3", "G3b"],
            "commit": _git_commit(),
        },
        "artifacts": {
            "status": "passed",
            "gates": ["G6", "G7"],
        },
        "train": {
            "status": "passed",
            "gates": [],
            "run_id": args.run_id,
        },
    }

    all_gates = ["G5", "G6", "G7", "G8", "G9", "G10", "G11"]
    if args.model == "all":
        elements["model"] = {
            "status": "passed",
            "gates": all_gates,
            "models": ["m1", "m2", "m3"],
        }
        elements["artifacts"]["gates"] = ["G6", "G7"]
        elements["deploy"] = {"status": "passed", "gates": ["G11"], "note": "Trivy at deploy time"}
    elif args.model_key == "m3":
        elements["model"] = {
            "status": "passed",
            "gates": ["G5", "G10"],
            "artifact": str(ROOT / "models/m3_nlp/artifact"),
        }
    else:
        onnx = (
            ROOT / "artifacts/models/m2_antifraud/onnx/model.onnx"
            if args.model_key == "m2"
            else ROOT / "models/m1_scoring/artifact/onnx/model.onnx"
        )
        elements["model"] = {
            "status": "passed",
            "gates": ["G5", "G8", "G9", "G11"],
            "digest": f"sha256:{_digest(onnx)}",
        }

    payload = build_attestation(corr, elements, model_name=args.model, commit=_git_commit())
    signed = sign_attestation(payload)
    out = ROOT / "artifacts/attestation/fortress-attestation.signed.json"
    save_signed(out, signed)
    print(f"attestation saved: {out}")

    try:
        record_pipeline_step(
            args.run_id, "sign", "passed",
            model_name=args.model,
            report_path=str(out),
            correlation_id=corr,
            details={"algorithm": "ed25519"},
        )
    except Exception as exc:
        print(f"WARN pipeline_runs: {exc}")

    sys.exit(0)


if __name__ == "__main__":
    main()
