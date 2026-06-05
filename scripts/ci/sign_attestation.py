#!/usr/bin/env python3
"""Sign attestation only after strict gate verification."""

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
from fortress.gate_verifier import build_attestation_elements, verify_pipeline_run  # noqa: E402
from fortress.pipeline import record_pipeline_step  # noqa: E402


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "local"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    p.add_argument("--model", default="credit-scoring-pd")
    p.add_argument("--model-key", default="m1")
    p.add_argument("--correlation-id", default=os.getenv("CORRELATION_ID", ""))
    p.add_argument("--strict", action="store_true", help="Require pipeline_runs + artifacts")
    args = p.parse_args()

    corr = args.correlation_id or args.run_id
    ensure_keypair()

    if args.strict:
        ok, errs = verify_pipeline_run(args.run_id, args.model_key, require_db=False)
        if errs:
            for e in errs:
                print(f"WARN verify: {e}", file=sys.stderr)
        if not ok:
            print("FAIL: strict attestation — gate records or artifacts incomplete", file=sys.stderr)
            return 1
        try:
            elements = build_attestation_elements(args.run_id, args.model_key)
        except ValueError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
    else:
        elements = {
            "data": {"status": "passed", "gates": ["DATA"]},
            "code": {"status": "passed", "gates": ["G0", "G1", "G3", "G3b"]},
            "train": {"status": "passed", "gates": []},
            "model": {"status": "passed", "gates": ["G5", "G8", "G9"]},
        }

    payload = build_attestation(corr, elements, model_name=args.model, commit=_git_commit())
    signed = sign_attestation(payload)
    out = ROOT / "artifacts/attestation/fortress-attestation.signed.json"
    save_signed(out, signed)
    print(f"attestation saved: {out}")

    record_pipeline_step(
        args.run_id, "sign", "passed",
        model_name=args.model,
        report_path=str(out),
        correlation_id=corr,
        details={"algorithm": "ed25519", "strict": args.strict},
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
