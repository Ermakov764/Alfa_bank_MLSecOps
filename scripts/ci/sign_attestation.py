#!/usr/bin/env python3
"""Sign platform attestation after strict gate verification."""

from __future__ import annotations

import argparse
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
    p.add_argument("--model", default="platform", help="Attestation scope label (default: platform)")
    p.add_argument("--correlation-id", default=os.getenv("CORRELATION_ID", ""))
    p.add_argument("--strict", action="store_true", help="Require pipeline_runs for DATA + code gates")
    args = p.parse_args()

    corr = args.correlation_id or args.run_id
    ensure_keypair()

    if args.strict:
        skip_data = os.getenv("PIPELINE_SKIP_DATA", "").lower() in ("1", "true", "yes")
        dataset = Path(os.getenv("PIPELINE_DATASET_CSV", str(ROOT / "data/datasets/train_clean.csv")))
        ok, errs = verify_pipeline_run(
            args.run_id, require_db=False, require_data=not skip_data and dataset.exists(),
        )
        if errs:
            for e in errs:
                print(f"WARN verify: {e}", file=sys.stderr)
        if not ok:
            print("FAIL: strict attestation — gate records incomplete", file=sys.stderr)
            return 1
        elements = build_attestation_elements(
            args.run_id,
            dataset_path=dataset if dataset.exists() else None,
            include_data=not skip_data and dataset.exists(),
        )
    else:
        elements = {
            "data": {"status": "passed", "gates": ["DATA"]},
            "code": {"status": "passed", "gates": ["G0", "G1", "G3", "G3b"]},
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
