#!/usr/bin/env python3
"""Recompute and verify GY-N13b acquisition-executor artifacts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from tools.quality.validation.layer3_gy_acquisition_executor import (
    DEFAULT_TARGET_AUTHORITY_PROVISION,
    DEFAULT_TARGET_AUTHORITY_REGISTRY,
    DEFAULT_TARGET_HARNESS_RECEIPT,
    bytes_sha256,
    derive_live_attempt_id,
    derive_live_target_selection,
    derive_target_authority_owners,
    derive_target_family_receipt,
)

POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CENSUS_PATH = (
    POLICY_ENGINE_ROOT / "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json"
)
DEFAULT_SUBSTRATE_PATH = (
    POLICY_ENGINE_ROOT
    / "architecture/policy_design_case/layer3_gy_intervention_substrate_contract.json"
)
DEFAULT_CATALOG_OWNER_REF = (
    "repo://production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
)
DEFAULT_L5_OWNER_REF = (
    "repo://production_data/canonical/local_data_20260501/"
    "ukraine_server_support_20260410/runtime_calibration_internals/"
    "calibration/d2/measurement_registry.json"
)


def main() -> int:
    """Run the requested offline target-owner lifecycle mode."""

    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-target-owners", action="store_true")
    mode.add_argument("--write-target-owners", action="store_true")
    parser.add_argument("--catalog-path", type=Path, required=True)
    parser.add_argument("--l5-path", type=Path, required=True)
    parser.add_argument("--census-path", type=Path, default=DEFAULT_CENSUS_PATH)
    parser.add_argument("--substrate-path", type=Path, default=DEFAULT_SUBSTRATE_PATH)
    args = parser.parse_args()

    owners = _recompute_target_owners(
        catalog_path=args.catalog_path,
        l5_path=args.l5_path,
        census_path=args.census_path,
        substrate_path=args.substrate_path,
    )
    second = _recompute_target_owners(
        catalog_path=args.catalog_path,
        l5_path=args.l5_path,
        census_path=args.census_path,
        substrate_path=args.substrate_path,
    )
    if owners.payloads() != second.payloads():
        raise RuntimeError("target_owner_derivation_not_byte_stable")

    if args.write_target_owners:
        for relative in (
            DEFAULT_TARGET_HARNESS_RECEIPT,
            DEFAULT_TARGET_AUTHORITY_REGISTRY,
            DEFAULT_TARGET_AUTHORITY_PROVISION,
        ):
            _write_replace_bytes(POLICY_ENGINE_ROOT / relative, owners.payloads()[relative])
        status = "written"
    else:
        for relative, expected in owners.payloads().items():
            path = POLICY_ENGINE_ROOT / relative
            if not path.is_file():
                raise RuntimeError(f"target_owner_artifact_missing:{relative}")
            if path.read_bytes() != expected:
                raise RuntimeError(f"target_owner_artifact_drift:{relative}")
        status = "ok"

    report: dict[str, Any] = {
        "status": status,
        "attempt_id": derive_live_attempt_id(owners.selection),
        "target_variable": owners.selection.target_variable,
        "request_dataset_id": owners.selection.request_dataset_id,
        "entry_id": owners.entry.entry_id,
        "registry_content_sha256": owners.registry.content_sha256,
        "provision_id": owners.provision.provision_id,
        "payload_file_sha256": {
            relative.as_posix(): bytes_sha256(payload)
            for relative, payload in sorted(
                owners.payloads().items(),
                key=lambda item: item[0].as_posix(),
            )
        },
        "byte_stable_passes": 2,
        "live_network_calls": 0,
    }
    print(json.dumps(report, sort_keys=True))
    return 0


def _recompute_target_owners(
    *,
    catalog_path: Path,
    l5_path: Path,
    census_path: Path,
    substrate_path: Path,
) -> Any:
    selection = derive_live_target_selection(
        catalog_path=catalog_path,
        census_path=census_path,
        substrate_path=substrate_path,
    )
    receipt = derive_target_family_receipt(
        selection,
        catalog_path=catalog_path,
        fixture_root=POLICY_ENGINE_ROOT / ".tmp/gy-n13b-no-replay-fixtures",
    )
    return derive_target_authority_owners(
        selection,
        family_receipt=receipt,
        baseline_path=catalog_path,
        baseline_owner_ref=DEFAULT_CATALOG_OWNER_REF,
        l5_path=l5_path,
        l5_owner_ref=DEFAULT_L5_OWNER_REF,
        receipt_owner_ref=f"repo://{DEFAULT_TARGET_HARNESS_RECEIPT.as_posix()}",
        country_codes=("UKR",),
    )


def _write_replace_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


if __name__ == "__main__":
    raise SystemExit(main())
