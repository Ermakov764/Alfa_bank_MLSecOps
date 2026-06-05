#!/usr/bin/env python3
"""CLI wrapper for fortress.promote."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fortress.promote import archive, promote  # noqa: E402


def actor_role(actor: str) -> str:
    return os.getenv("ACTOR_ROLE", "ds")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--actor", default="system")
    p.add_argument("--approve", action="store_true", help="MLSecOps HITL for external models")
    p.add_argument("--archive", action="store_true")
    args = p.parse_args()
    role = actor_role(args.actor)
    if args.archive:
        ok, msg = archive(args.model, args.version, args.actor, actor_role=role)
        print(msg)
        return 0 if ok else 1
    ok, msg = promote(
        args.model, args.version, args.actor,
        actor_role=role, approve=args.approve,
    )
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
