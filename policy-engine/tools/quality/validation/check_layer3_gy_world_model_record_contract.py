#!/usr/bin/env python3
"""Validate the Layer 3 GY WorldModelRecord contract artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools.lib.timing import run_timed_entrypoint

OUTPUT_PATH = "architecture/policy_design_case/layer3_gy_world_model_record_contract.json"
SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy.world_model_record_contract.v1"


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def build_live_payload() -> dict[str, Any]:
    """Recompute the WorldModelRecord contract from the live model."""

    from polisyos.runtime.quality.world_model_record import (
        WORLD_MODEL_RECORD_ARTIFACT_KIND,
        WORLD_MODEL_RECORD_SCHEMA_VERSION,
        WorldModelRecord,
    )

    schema = WorldModelRecord.model_json_schema()
    return {
        "schema_version": SCHEMA_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "contract_id": "policyos.runtime.world_model_record",
        "world_model_record_schema_version": WORLD_MODEL_RECORD_SCHEMA_VERSION,
        "artifact_kind": WORLD_MODEL_RECORD_ARTIFACT_KIND,
        "owner": "polisyos.runtime.quality.world_model_record.WorldModelRecord",
        "source_module": "src/polisyos/runtime/quality/world_model_record.py",
        "unify_existing_substrates": [
            "fabric.world.query.WorldQueryRequest",
            "data_forge.kernel.snapshot.write_snapshot_binding",
            "ir.model_layer.model_spec.ModelSpec",
            "foundry.data_plane.bindings.build_input_bindings",
            "data_forge.read_api.academic.SKGQuery",
            "runtime.quality.substrate_registry.SubstrateRegistry",
        ],
        "producer": "build_world_model_record",
        "consumers": [
            "consume_world_model_record_for_simulation",
            "resolve_intervention_atom_world_binding",
        ],
        "content_binding_checks": [
            "data_snapshot_version_missing",
            "world_substrate_version_mismatch",
            "data_forge_snapshot_binding_schema_mismatch",
            "data_forge_snapshot_binding_snapshot_mismatch",
            "fabric_world_empty",
            "fabric_world_not_queryable",
            "model_spec_registry_bundle_missing",
            "world_slot_state_path_missing",
            "substrate_entry_unresolved",
            "substrate_registry_entries_missing",
            "content_hash_mismatch",
        ],
        "phase_6_forward_hook": "deployment_update_refs",
        "value_step_naming_deferred_to": "GY-N8",
        "synthetic_world_disposition": "benchmark_only_not_production_world_owner",
        "parallel_world_store_allowed": False,
        "json_schema": schema,
    }


def validate(repo_root: Path) -> dict[str, Any]:
    """Validate the committed schema artifact against live code."""

    path = repo_root / OUTPUT_PATH
    issues: list[dict[str, Any]] = []
    live = build_live_payload()
    if not path.is_file():
        issues.append({"code": "world_model_record_contract_missing", "path": OUTPUT_PATH})
        committed: dict[str, Any] | None = None
    else:
        try:
            committed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            committed = None
            issues.append(
                {
                    "code": "world_model_record_contract_invalid_json",
                    "path": OUTPUT_PATH,
                    "error": str(exc),
                }
            )
    if committed is not None and committed != live:
        issues.append({"code": "world_model_record_contract_drift", "path": OUTPUT_PATH})
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "outputs": declared_outputs(),
    }


def write(repo_root: Path) -> None:
    """Write the live WorldModelRecord contract artifact."""

    path = repo_root / OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_live_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    """Run the WorldModelRecord contract validator."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    inserted = [str(repo_root), str(repo_root / "src")]
    for item in reversed(inserted):
        if item not in sys.path:
            sys.path.insert(0, item)
    if args.write:
        write(repo_root)
    report = validate(repo_root)
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] != "pass":
        for issue in report["issues"]:
            print(f"{issue.get('code')}: {issue}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
