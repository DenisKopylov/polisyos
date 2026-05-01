#!/usr/bin/env python3
"""Validate Fabric processing-guarantee, dedupe, CDC, and scale contracts."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any

from tools._lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from polisyos.fabric.processing_guarantees import (  # noqa: E402
    ProcessingGuarantee,
)
from tools.quality.validation import fabric_source_contracts  # noqa: E402

REPORT_SCHEMA_VERSION = "fabric.processing_guarantees_report.v1"


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="Print report JSON")
    parser.add_argument("--check", action="store_true", help="Fail on contract gaps")
    return parser.parse_args(argv)


def build_report() -> dict[str, Any]:
    contracts = fabric_source_contracts.build_source_contracts()
    exact_once_claims = [
        contract
        for contract in contracts
        if ProcessingGuarantee(contract.processing.guarantee)
        == ProcessingGuarantee.EXACTLY_ONCE_NARROW
    ]
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "source_contract_count": len(contracts),
        "processing_guarantees": {
            contract.id: contract.processing.guarantee_value
            for contract in sorted(contracts, key=lambda item: item.id)
        },
        "streaming_contracts": [
            _contract_row(contract)
            for contract in contracts
            if contract.processing.guarantee_value
            in {
                ProcessingGuarantee.AT_LEAST_ONCE.value,
                ProcessingGuarantee.AT_LEAST_ONCE_WITH_DEDUPE.value,
                ProcessingGuarantee.EFFECTIVELY_ONCE.value,
                ProcessingGuarantee.EXACTLY_ONCE_NARROW.value,
            }
        ],
        "exactly_once_claim_count": len(exact_once_claims),
        "contracts": [_contract_row(contract) for contract in contracts],
    }


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for row in report.get("contracts", []):
        guarantee = row["guarantee"]
        if guarantee == ProcessingGuarantee.EXACTLY_ONCE_NARROW.value:
            if not row["atomicity_proof_complete"]:
                errors.append(f"exactly_once_narrow lacks atomic proof: {row['id']}")
        if guarantee in {
            ProcessingGuarantee.AT_LEAST_ONCE_WITH_DEDUPE.value,
            ProcessingGuarantee.EFFECTIVELY_ONCE.value,
        }:
            if not row["dedupe_key_fields"]:
                errors.append(f"missing dedupe key policy: {row['id']}")
            if int(row["dedupe_window_seconds"]) <= 0:
                errors.append(f"missing dedupe window: {row['id']}")
        if int(row["replay_retention_days"]) <= 0:
            errors.append(f"missing replay retention: {row['id']}")
        if not row["out_of_order_handling"]:
            errors.append(f"missing out-of-order handling: {row['id']}")
    return errors


def _contract_row(contract: Any) -> dict[str, Any]:
    processing = contract.processing
    atomicity_proof = processing.atomicity_proof
    return {
        "id": contract.id,
        "connector_id": contract.source.connector_id,
        "guarantee": processing.guarantee_value,
        "dedupe_key_fields": list(processing.idempotency.key_fields),
        "dedupe_window_seconds": processing.idempotency.dedupe_window_seconds,
        "max_dedupe_keys": processing.idempotency.max_dedupe_keys,
        "replay_retention_days": processing.idempotency.replay_retention_days,
        "out_of_order_handling": processing.out_of_order.handling.value,
        "late_event_action": processing.out_of_order.late_event_action.value,
        "backpressure_strategy": processing.backpressure.strategy.value,
        "cdc_breaking_change_action": processing.cdc_schema_changes.breaking_change_action,
        "atomicity_proof_complete": (
            bool(atomicity_proof.complete) if atomicity_proof is not None else False
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    report = build_report()
    if args.report:
        print(json.dumps(report, indent=2, sort_keys=True))
    errors = validate_report(report) if args.check else []
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    if args.check:
        print("Fabric processing guarantee check PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
