#!/usr/bin/env python3
"""Check evidence-spine async/batch handoff ledgers in canary bundles."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from polisyos.runtime.quality.evidence_spine_handoff import (
    REQUIRED_HANDOFF_KINDS,
    build_evidence_spine_handoff_ledger,
)

SCHEMA_VERSION = "policyos.evidence_spine_handoff_check.v1"
HANDOFF_LEDGER_REF = "quality_evidence/evidence_spine_handoff_ledger.json"


def inspect_bundle(bundle_dir: str | Path) -> dict[str, Any]:
    """Inspect one evidence bundle for handoff ledger completeness."""

    bundle_path = Path(bundle_dir)
    ledger_path = bundle_path / HANDOFF_LEDGER_REF
    if not ledger_path.exists():
        finding = {
            "status": "fail",
            "severity": "error",
            "code": "evidence_spine_handoff_ledger_missing",
            "message": "Evidence spine handoff ledger is missing from the serious bundle.",
            "artifact_ref": HANDOFF_LEDGER_REF,
            "root_cause_class": "evidence_spine_async_handoff",
            "next_action": (
                "Emit quality_evidence/evidence_spine_handoff_ledger.json during canary "
                "bundle assembly and preserve it through replay, inspection, and readiness."
            ),
        }
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "fail",
            "bundle_dir": str(bundle_path),
            "summary": {"handoff_count": 0, "finding_count": 1},
            "findings": [finding],
            "ledger": None,
        }

    raw_ledger = _load_json(ledger_path)
    handoffs = raw_ledger.get("handoffs") if isinstance(raw_ledger, Mapping) else None
    if not isinstance(handoffs, list):
        handoffs = []
    ledger = build_evidence_spine_handoff_ledger(
        [dict(item) for item in handoffs if isinstance(item, Mapping)],
        required_handoff_kinds=REQUIRED_HANDOFF_KINDS,
    )
    findings = [
        dict(item)
        for item in ledger.get("findings", [])
        if isinstance(item, Mapping) and item.get("status") == "fail"
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if findings else "pass",
        "bundle_dir": str(bundle_path),
        "summary": {
            "handoff_count": ledger.get("summary", {}).get("handoff_count", 0)
            if isinstance(ledger.get("summary"), Mapping)
            else 0,
            "finding_count": len(findings),
        },
        "findings": findings,
        "ledger": ledger,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    bundle_dir = args.bundle_dir
    if not bundle_dir.is_absolute():
        bundle_dir = repo_root / bundle_dir
    report = inspect_bundle(bundle_dir)
    if args.json_output is not None:
        output = args.json_output
        if not output.is_absolute():
            output = repo_root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    if args.require_passing and report["status"] != "pass":
        return 2
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, default=None)
    parser.add_argument("--require-passing", action="store_true")
    return parser.parse_args(argv)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "schema_version": "policyos.invalid_json.v1",
            "status": "fail",
            "handoffs": [],
            "findings": [
                {
                    "code": "evidence_spine_handoff_ledger_invalid_json",
                    "message": f"{path}: {exc}",
                }
            ],
        }
    return payload if isinstance(payload, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
