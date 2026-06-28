#!/usr/bin/env python3
"""Validate the Layer 3 GY InterventionAtomBinding contract artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

OUTPUT_PATH = "architecture/policy_design_case/layer3_gy_intervention_atom_binding_contract.json"
SCHEMA_VERSION = (
    "policyos.policy_design_case.layer3_gy.intervention_atom_binding_contract.v1"
)


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def build_live_payload() -> dict[str, Any]:
    """Recompute the InterventionAtomBinding contract from the live model."""

    from polisyos.runtime.quality.intervention_atom_binding import (
        INTERVENTION_ATOM_BINDING_ARTIFACT_KIND,
        INTERVENTION_ATOM_BINDING_SCHEMA_VERSION,
        InterventionAtomBinding,
    )

    schema = InterventionAtomBinding.model_json_schema()
    return {
        "schema_version": SCHEMA_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "contract_id": "policyos.runtime.intervention_atom_binding",
        "intervention_atom_binding_schema_version": INTERVENTION_ATOM_BINDING_SCHEMA_VERSION,
        "artifact_kind": INTERVENTION_ATOM_BINDING_ARTIFACT_KIND,
        "owner": "polisyos.runtime.quality.intervention_atom_binding.InterventionAtomBinding",
        "source_module": "src/polisyos/runtime/quality/intervention_atom_binding.py",
        "existing_halves": [
            "ir.governance.policy_spec.InterventionSpec",
            "ir.linker.LinkedIntervention",
            "ir.analytics.interventions.InterventionExpr",
            "ir.analytics.interventions.QueryTarget",
            "ir.analytics.interventions.InterventionIdentificationPlan",
        ],
        "producer": "build_intervention_atom_binding",
        "consumer": "consume_intervention_atom_for_cycle",
        "content_binding_checks": [
            "target_selector_context_mismatch",
            "world_slot_do_variable_mismatch",
            "mechanism_do_variable_mismatch",
            "operator_kind_mismatch",
            "identification_plan_type_mismatch",
            "content_hash_mismatch",
        ],
        "measurement_expectations_authority": "supporting_metadata",
        "authoritative_action_outcome_link": "intended_downstream_estimand",
        "json_schema": schema,
    }


def validate(repo_root: Path) -> dict[str, Any]:
    """Validate the committed schema artifact against live code."""

    path = repo_root / OUTPUT_PATH
    issues: list[dict[str, Any]] = []
    live = build_live_payload()
    if not path.is_file():
        issues.append({"code": "intervention_atom_binding_contract_missing", "path": OUTPUT_PATH})
        committed: dict[str, Any] | None = None
    else:
        try:
            committed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            committed = None
            issues.append(
                {
                    "code": "intervention_atom_binding_contract_invalid_json",
                    "path": OUTPUT_PATH,
                    "error": str(exc),
                }
            )
    if committed is not None and committed != live:
        issues.append(
            {"code": "intervention_atom_binding_contract_drift", "path": OUTPUT_PATH}
        )
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "outputs": declared_outputs(),
    }


def write(repo_root: Path) -> None:
    """Write the live InterventionAtomBinding contract artifact."""

    path = repo_root / OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_live_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    """Run the InterventionAtomBinding contract validator."""

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
    raise SystemExit(main())
