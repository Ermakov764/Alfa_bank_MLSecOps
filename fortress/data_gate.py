"""Pre-train DATA gate (not G1 Semgrep)."""

from __future__ import annotations

import csv
import re
import uuid
from pathlib import Path

from fortress.audit import log_event, log_finding
from fortress.pii_scanner import scan_cell

POISON_MARKERS = ("poison", "backdoor", "malicious", "evil")
PII_PATTERN = re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b")


def run_gate(
    path: Path,
    expected_cols: list[str] | None = None,
    max_null_ratio: float = 0.5,
    actor: str = "system",
) -> tuple[int, str | None]:
    corr = str(uuid.uuid4())
    if not path.exists():
        rule = "file not found"
        log_event(actor, "gate.failed", resource_type="dataset",
                  resource_id="DATA", status="failed", details={"error": rule},
                  correlation_id=corr)
        return 1, rule

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        rows = list(reader)

    if expected_cols:
        missing = [c for c in expected_cols if c not in cols]
        if missing:
            rule = f"missing columns: {missing} (found: {cols[:8]}{'…' if len(cols) > 8 else ''})"
            _fail(path, rule, corr, actor)
            return 1, rule

    for col in cols:
        cl = col.lower()
        if any(m in cl for m in POISON_MARKERS):
            rule = f"poison column detected: {col}"
            _fail(path, rule, corr, actor, severity="critical")
            return 1, rule

    if not rows:
        rule = "empty dataset"
        _fail(path, rule, corr, actor)
        return 1, rule

    # Duplicate rows (data quality)
    seen: set[tuple[str, ...]] = set()
    dupes = 0
    for row in rows:
        key = tuple(str(row.get(c, "")).strip() for c in cols)
        if key in seen:
            dupes += 1
        seen.add(key)
    if dupes > max(1, len(rows) // 4):
        rule = f"too many duplicate rows: {dupes}/{len(rows)}"
        _fail(path, rule, corr, actor)
        return 1, rule

    nulls = 0
    total = len(rows) * max(len(cols), 1)
    for row in rows:
        for v in row.values():
            if v is None or str(v).strip() == "":
                nulls += 1
            else:
                sv = str(v)
                if PII_PATTERN.search(sv):
                    rule = "PII pattern in data (номер карты в ячейках)"
                    _fail(path, rule, corr, actor, severity="high")
                    return 1, rule
                bad, presidio_rule = scan_cell(sv)
                if bad:
                    _fail(path, presidio_rule or "PII in data", corr, actor, severity="high")
                    return 1, presidio_rule

    if total and nulls / total > max_null_ratio:
        rule = f"too many nulls: {nulls}/{total}"
        _fail(path, rule, corr, actor)
        return 1, rule

    # Class balance anti-poisoning (when label column present)
    label_col = next((c for c in cols if c.lower() in ("target", "label", "y")), None)
    if label_col and len(rows) >= 4:
        from collections import Counter

        counts = Counter(str(row.get(label_col, "")).strip() for row in rows)
        counts.pop("", None)
        if len(counts) >= 2:
            n = sum(counts.values())
            min_ratio = min(counts.values()) / n
            max_ratio = max(counts.values()) / n
            if min_ratio <= 0.05:
                rule = f"class imbalance (min class {min_ratio:.1%}) — possible poisoning"
                _fail(path, rule, corr, actor, severity="high")
                return 1, rule
            if max_ratio > 0.95:
                rule = f"class imbalance (dominant class {max_ratio:.1%}) — possible poisoning"
                _fail(path, rule, corr, actor, severity="high")
                return 1, rule

    log_event(
        actor, "gate.passed", resource_type="dataset", resource_id="DATA",
        status="success", details={"path": str(path), "rows": len(rows)},
        correlation_id=corr,
    )
    return 0, None


def _fail(path: Path, rule: str, corr: str, actor: str, severity: str = "medium") -> None:
    log_finding("DATA", "dataset", path.name, rule, severity=severity, correlation_id=corr)
    log_event(
        actor, "gate.failed", resource_type="dataset", resource_id="DATA",
        status="failed", details={"rule": rule, "path": str(path)}, correlation_id=corr,
    )
