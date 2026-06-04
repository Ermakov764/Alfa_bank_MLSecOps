#!/usr/bin/env python3
"""Record gate result to audit + pipeline_runs (+ optional JSON report)."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fortress.audit import log_event, log_finding  # noqa: E402
from fortress.pipeline import record_pipeline_step  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    p.add_argument("--element", required=True)
    p.add_argument("--gate", default="")
    p.add_argument("--status", choices=("started", "passed", "failed"), required=True)
    p.add_argument("--model", default="")
    p.add_argument("--report", type=Path, default=None)
    p.add_argument("--correlation-id", default="")
    p.add_argument("--actor", default="ci")
    p.add_argument("--message", default="")
    args = p.parse_args()

    corr = args.correlation_id or str(uuid.uuid4())
    details: dict = {}
    if args.message:
        details["message"] = args.message
    if args.report and args.report.exists():
        details["report"] = str(args.report)
        try:
            details["summary"] = json.loads(args.report.read_text(encoding="utf-8"))
        except Exception:
            pass

    try:
        record_pipeline_step(
            args.run_id,
            args.element,
            args.status,
            gate=args.gate or None,
            model_name=args.model or None,
            report_path=str(args.report) if args.report else None,
            details=details,
            correlation_id=corr,
        )
    except Exception as exc:
        print(f"WARN: pipeline_runs insert failed: {exc}", file=sys.stderr)

    action = "gate.passed" if args.status == "passed" else (
        "gate.failed" if args.status == "failed" else "gate.started"
    )
    try:
        log_event(
            args.actor,
            action,
            role="ci",
            resource_type="gate",
            resource_id=args.gate or args.element,
            model_name=args.model or None,
            status=args.status,
            details=details,
            correlation_id=corr,
        )
        if args.status == "failed":
            log_finding(
                args.gate or args.element,
                "pipeline",
                args.run_id,
                args.message or "gate failed",
                severity="high",
                evidence=details,
                correlation_id=corr,
            )
    except Exception as exc:
        print(f"WARN: audit log failed: {exc}", file=sys.stderr)

    if args.report and args.report.parent:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        if not args.report.exists() and details:
            args.report.write_text(json.dumps(details, indent=2), encoding="utf-8")

    sys.exit(0 if args.status != "failed" else 1)


if __name__ == "__main__":
    main()
