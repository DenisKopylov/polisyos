#!/usr/bin/env python3
"""Validate Fabric connector contract evolution against governance policy."""

from __future__ import annotations

import argparse
import json
import sys
import types
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from tools._lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

_CONNECTORS_PATH = SRC_ROOT / "polisyos" / "fabric" / "connectors"
_CONNECTORS_PACKAGE = "polisyos.fabric.connectors"
if _CONNECTORS_PACKAGE not in sys.modules:
    stub = types.ModuleType(_CONNECTORS_PACKAGE)
    stub.__path__ = [str(_CONNECTORS_PATH)]  # type: ignore[attr-defined]
    sys.modules[_CONNECTORS_PACKAGE] = stub

from polisyos.fabric.connectors.contracts import (  # noqa: E402
    ConnectorSchemaContract,
    ContractGovernanceEvaluation,
    MigrationPlan,
    evaluate_contract_governance,
)
from polisyos.fabric.connectors.sources._contracts import ALL_SOURCE_CONTRACTS  # noqa: E402

DEFAULT_SNAPSHOT = (
    REPO_ROOT / "schemas" / "snapshots" / "fabric" / "connector_contract_registry.json"
)
SNAPSHOT_VERSION = 1
_UNORDERED_LIST_KEYS = {"allowed_null_fields", "allowed_values", "tags", "adr_refs"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--check", action="store_true", help="Fail if snapshot differs")
    parser.add_argument("--update", action="store_true", help="Update snapshot in place")
    parser.add_argument(
        "--evidence-out",
        type=Path,
        default=None,
        help="Optional JSON file path for governance evidence output",
    )
    return parser.parse_args()


def _normalize_snapshot_obj(value: Any, parent_key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_snapshot_obj(item, key) for key, item in value.items()}
    if isinstance(value, list):
        normalized = [_normalize_snapshot_obj(item) for item in value]
        if parent_key in _UNORDERED_LIST_KEYS and all(
            not isinstance(item, (dict, list)) for item in normalized
        ):
            return sorted(normalized, key=lambda item: str(item))
        return normalized
    return value


def build_snapshot_payload(
    contracts: list[ConnectorSchemaContract]
    | tuple[ConnectorSchemaContract, ...] = ALL_SOURCE_CONTRACTS,
) -> dict[str, Any]:
    payload = {
        "version": SNAPSHOT_VERSION,
        "contracts": {},
    }
    for contract in sorted(contracts, key=lambda row: row.contract_id):
        dumped = contract.model_dump(mode="json", exclude={"created_at"})
        payload["contracts"][contract.contract_id] = {
            "connector_id": contract.connector_id,
            "dataset_id": contract.dataset_id,
            "schema_id": contract.schema.schema_id,
            "schema_version": str(contract.schema_version),
            "content_hash": contract.content_hash,
            "contract": _normalize_snapshot_obj(dumped),
        }
    return payload


def _migration_plans_from_evaluations(
    evaluations: dict[str, ContractGovernanceEvaluation],
) -> dict[str, MigrationPlan]:
    plans: dict[str, MigrationPlan] = {}
    for contract_id, evaluation in evaluations.items():
        plan = evaluation.migration_plan
        if plan is not None and evaluation.report.is_compatible and plan.operations:
            plans[contract_id] = plan
    return plans


def _assess_against_baseline(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> tuple[list[str], dict[str, ContractGovernanceEvaluation]]:
    errors: list[str] = []
    evaluations: dict[str, ContractGovernanceEvaluation] = {}

    baseline_contracts = baseline.get("contracts", {})
    current_contracts = current.get("contracts", {})
    if not isinstance(baseline_contracts, dict) or not isinstance(current_contracts, dict):
        return (["invalid snapshot format: contracts must be object"], {})

    for contract_id, current_meta in current_contracts.items():
        previous_meta = baseline_contracts.get(contract_id)
        if previous_meta is None:
            continue
        try:
            previous_contract = ConnectorSchemaContract.model_validate(previous_meta["contract"])
            current_contract = ConnectorSchemaContract.model_validate(current_meta["contract"])
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            errors.append(f"{contract_id}: failed to parse contract snapshot: {exc}")
            continue

        evaluation = evaluate_contract_governance(previous_contract, current_contract)
        if not evaluation.report.changes:
            continue

        evaluations[contract_id] = evaluation
        errors.extend(evaluation.errors)

    return (errors, evaluations)


def validate_against_baseline(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> tuple[list[str], dict[str, MigrationPlan]]:
    errors, evaluations = _assess_against_baseline(baseline, current)
    return (errors, _migration_plans_from_evaluations(evaluations))


def build_evidence_payload(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    errors, evaluations = _assess_against_baseline(baseline, current)
    migrations = _migration_plans_from_evaluations(evaluations)
    baseline_contracts = baseline.get("contracts", {})
    current_contracts = current.get("contracts", {})

    contract_evaluations: dict[str, Any] = {}
    for contract_id, evaluation in sorted(evaluations.items()):
        contract_evaluations[contract_id] = {
            "source_version": str(evaluation.previous_version),
            "target_version": str(evaluation.current_version),
            "recommended_version_bump": evaluation.report.recommended_version_bump,
            "actual_version_bump": evaluation.actual_bump,
            "compatible": evaluation.report.is_compatible,
            "impacted_surfaces": list(evaluation.impacted_surfaces),
            "breaking_change_count": len(evaluation.report.breaking_changes),
            "non_breaking_change_count": len(evaluation.report.non_breaking_changes),
            "changes": [change.description for change in evaluation.report.changes],
            "missing_governance_requirements": list(evaluation.missing_governance_requirements),
            "errors": list(evaluation.errors),
            "migration_plan": (
                {
                    "safe_to_apply": evaluation.migration_plan.safe_to_apply,
                    "sql_statements": list(evaluation.migration_plan.sql_statements),
                    "operations": [
                        operation.model_dump(mode="json")
                        for operation in evaluation.migration_plan.operations
                    ],
                }
                if evaluation.migration_plan is not None and evaluation.migration_plan.operations
                else None
            ),
        }

    return {
        "version": SNAPSHOT_VERSION,
        "baseline_contract_count": len(baseline_contracts)
        if isinstance(baseline_contracts, dict)
        else 0,
        "current_contract_count": len(current_contracts)
        if isinstance(current_contracts, dict)
        else 0,
        "snapshot_out_of_date": dump_json(current) != dump_json(baseline),
        "error_count": len(errors),
        "errors": errors,
        "contract_evaluations": contract_evaluations,
        "compatible_migration_plans": {
            contract_id: {
                "safe_to_apply": plan.safe_to_apply,
                "sql_statements": list(plan.sql_statements),
            }
            for contract_id, plan in sorted(migrations.items())
        },
    }


def dump_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, indent=2) + "\n"


def _load_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = _parse_args()
    if args.check and args.update:
        print("ERROR: --check and --update are mutually exclusive")
        return 2

    current = build_snapshot_payload()
    snapshot_path = args.snapshot

    if args.update:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(dump_json(current), encoding="utf-8")
        print(f"Updated Fabric schema registry snapshot: {snapshot_path}")
        return 0

    if not snapshot_path.exists():
        print(f"ERROR: snapshot not found: {snapshot_path}")
        print("Run with --update to create it.")
        return 1

    baseline = _load_snapshot(snapshot_path)
    errors, migration_plans = validate_against_baseline(baseline, current)
    if args.evidence_out is not None:
        evidence = build_evidence_payload(baseline, current)
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(dump_json(evidence), encoding="utf-8")
    if errors:
        print("Fabric schema governance check FAILED")
        for row in errors:
            print(f"- {row}")
        return 1

    if dump_json(current) != dump_json(baseline):
        print("Fabric schema registry snapshot is out of date.")
        print(f"Run: python {Path(__file__).resolve()} --update")
        if migration_plans:
            print("Compatible migrations:")
            for contract_id, plan in migration_plans.items():
                statements = "; ".join(plan.sql_statements) or "<manual review>"
                print(f"- {contract_id}: {statements}")
        return 1

    print("Fabric schema governance check PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
