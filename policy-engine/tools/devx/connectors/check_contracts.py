#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import types
from pathlib import Path
from tools._lib.imports import repo_root_from
from typing import Any

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

_SOURCES_PATH = _CONNECTORS_PATH / "sources"
_SOURCES_PACKAGE = "polisyos.fabric.connectors.sources"
if _SOURCES_PACKAGE not in sys.modules:
    stub = types.ModuleType(_SOURCES_PACKAGE)
    stub.__path__ = [str(_SOURCES_PATH)]  # type: ignore[attr-defined]
    sys.modules[_SOURCES_PACKAGE] = stub

from polisyos.fabric.connectors.contracts.contract import ConnectorSchemaContract  # noqa: E402
from polisyos.fabric.connectors.contracts.evolution import SchemaEvolution  # noqa: E402
from polisyos.fabric.connectors.contracts.schema import SchemaVersion  # noqa: E402
from polisyos.fabric.connectors.sources._contracts import ALL_SOURCE_CONTRACTS  # noqa: E402

DEFAULT_SNAPSHOT = REPO_ROOT / "schemas" / "snapshots" / "connectors" / "contracts.json"
_UNORDERED_LIST_KEYS = {"allowed_null_fields", "allowed_values", "tags"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate connector schema contracts")
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--check", action="store_true", help="Fail when snapshot differs")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Write snapshot from current contracts",
    )
    return parser.parse_args()


def _actual_bump(previous: SchemaVersion, current: SchemaVersion) -> str:
    if current.major > previous.major:
        return "major"
    if current.minor > previous.minor:
        return "minor"
    if current.patch > previous.patch:
        return "patch"
    return "none"


def _build_snapshot_payload() -> dict[str, Any]:
    contracts = sorted(ALL_SOURCE_CONTRACTS, key=lambda row: row.contract_id)
    payload = {
        "version": 1,
        "contracts": {},
    }
    for contract in contracts:
        contract_payload = contract.model_dump(mode="json", exclude={"created_at"})
        contract_payload = _normalize_snapshot_obj(contract_payload)
        payload["contracts"][contract.contract_id] = {
            "connector_id": contract.connector_id,
            "dataset_id": contract.dataset_id,
            "schema_version": str(contract.schema_version),
            "content_hash": contract.content_hash,
            # Exclude runtime timestamp and normalize set-like fields for deterministic snapshots.
            "contract": contract_payload,
        }
    return payload


def _normalize_snapshot_obj(value: Any, parent_key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_snapshot_obj(item, key) for key, item in value.items()}

    if isinstance(value, list):
        normalized = [_normalize_snapshot_obj(item) for item in value]
        if (
            parent_key in _UNORDERED_LIST_KEYS
            and all(not isinstance(item, (dict, list)) for item in normalized)
        ):
            return sorted(normalized, key=lambda item: str(item))
        return normalized

    return value


def _load_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_against_baseline(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    evolution = SchemaEvolution()

    baseline_contracts = baseline.get("contracts", {})
    current_contracts = current.get("contracts", {})
    if not isinstance(baseline_contracts, dict) or not isinstance(current_contracts, dict):
        return ["invalid snapshot format: contracts must be object"]

    for contract_id, current_meta in current_contracts.items():
        previous_meta = baseline_contracts.get(contract_id)
        if previous_meta is None:
            continue
        try:
            previous_contract = ConnectorSchemaContract.model_validate(previous_meta["contract"])
            current_contract = ConnectorSchemaContract.model_validate(current_meta["contract"])
        except Exception as exc:
            errors.append(f"{contract_id}: failed to parse contract snapshot: {exc}")
            continue

        report = evolution.compare(previous_contract.schema, current_contract.schema)
        if not report.changes:
            continue

        required = report.recommended_version_bump
        actual = _actual_bump(previous_contract.schema_version, current_contract.schema_version)
        if required == "major" and actual != "major":
            errors.append(
                f"{contract_id}: breaking changes require major bump "
                f"({previous_contract.schema_version} -> {current_contract.schema_version})"
            )
        elif required == "minor" and actual not in {"minor", "major"}:
            errors.append(
                f"{contract_id}: non-breaking changes require at least minor bump "
                f"({previous_contract.schema_version} -> {current_contract.schema_version})"
            )
        elif required == "patch" and actual == "none":
            errors.append(
                f"{contract_id}: patch-level changes require version bump "
                f"({previous_contract.schema_version} -> {current_contract.schema_version})"
            )

    return errors


def _dump_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, indent=2) + "\n"


def main() -> int:
    args = _parse_args()
    if args.check and args.update:
        print("ERROR: --check and --update are mutually exclusive")
        return 2

    mode_check = args.check or not args.update
    snapshot_path: Path = args.snapshot
    current = _build_snapshot_payload()

    if args.update:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(_dump_json(current), encoding="utf-8")
        print(f"Updated connector contracts snapshot: {snapshot_path}")
        return 0

    if not snapshot_path.exists():
        print(f"ERROR: snapshot not found: {snapshot_path}")
        print("Run with --update to create it.")
        return 1

    baseline = _load_snapshot(snapshot_path)
    errors = _validate_against_baseline(baseline, current)
    if errors:
        print("Connector contract check FAILED")
        for row in errors:
            print(f"- {row}")
        return 1

    if _dump_json(current) != _dump_json(baseline):
        if mode_check:
            print("Connector contract snapshot is out of date.")
            suggested = REPO_ROOT / "tools" / "connectors" / "check_contracts.py"
            print(f"Run: python {suggested} --update")
            return 1

    print("Connector contract check PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
