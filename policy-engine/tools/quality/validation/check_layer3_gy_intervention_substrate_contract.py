#!/usr/bin/env python3
"""Validate the Layer 3 GY L6 intervention-substrate lift contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

OUTPUT_PATH = "architecture/policy_design_case/layer3_gy_intervention_substrate_contract.json"
SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy.intervention_substrate_contract.v1"
EXPECTED_REMOVE_PROPERTY_MUTATIONS = {
    "unknown_op_admits",
    "out_of_domain_clamps",
    "dangling_map_binds_anyway",
    "dead_route_succeeds",
    "owner_slot_reference_binds_without_owner_validation",
    "law_provision_reference_binds_without_l3_validation",
    "world_slot_owner_derivation_disabled_drops_coverage",
    "world_slot_hardcoded_bypass_rejected",
    "unknown_family_defaults",
}


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def build_live_payload(repo_root: Path | None = None) -> dict[str, Any]:
    """Recompute the L6 intervention substrate contract from live code/data."""

    from polisyos.runtime.quality.intervention_substrate import (
        INTERVENTION_SUBSTRATE_ARTIFACT_KIND,
        INTERVENTION_SUBSTRATE_SCHEMA_VERSION,
        InterventionLeverResolution,
        InterventionSubstrateBundle,
        LawLeverResolution,
        ObservationMethodRoute,
        intervention_substrate_behavior_report,
    )

    repo_root = (repo_root or _default_repo_root()).resolve()
    behavior = intervention_substrate_behavior_report(repo_root)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "contract_id": "policyos.runtime.intervention_substrate_lift",
        "intervention_substrate_schema_version": INTERVENTION_SUBSTRATE_SCHEMA_VERSION,
        "artifact_kind": INTERVENTION_SUBSTRATE_ARTIFACT_KIND,
        "owner": "polisyos.runtime.quality.intervention_substrate over existing N2/Lex/Foundry/S0 owners",
        "source_modules": [
            "src/polisyos/runtime/quality/intervention_substrate.py",
            "src/polisyos/runtime/quality/intervention_atom_binding.py",
            "src/polisyos/runtime/quality/world_model_record.py",
            "src/polisyos/runtime/quality/substrate_registry.py",
            "src/polisyos/ir/kernel/mechanisms.py",
            "src/polisyos/lex/intervention_artifacts.py",
            "src/polisyos/lex/knowledge/store.py",
            "src/polisyos/foundry/methods/selection/registry.py",
        ],
        "real_l6_substrates": {
            "intervention_knob_dictionary": (
                "production_data/ukraine_agent_simulation_baseline_20260410/"
                "production_bundle/bundles/intervention_bundle_v1/"
                "intervention_knob_dictionary.json"
            ),
            "lex_intervention_map": (
                "production_data/ukraine_agent_simulation_baseline_20260410/"
                "production_bundle/bundles/intervention_bundle_v1/"
                "lex_intervention_map.json"
            ),
            "observation_to_contract_manifest": (
                "production_data/ukraine_agent_simulation_baseline_20260410/"
                "production_bundle/bundles/method_contract_bundle_v1/"
                "observation_to_contract_manifest.json"
            ),
            "policy_scenario_templates": (
                "production_data/ukraine_agent_simulation_baseline_20260410/"
                "production_bundle/bundles/intervention_bundle_v1/"
                "policy_scenario_templates.json"
            ),
            "owner_authority_bindings": (
                "architecture/policy_design_case/"
                "layer3_gy_l6_owner_authority_bindings.json"
            ),
        },
        "reuse_existing_owners": [
            "InterventionAtomBinding/Trinity linker target_world_slots",
            "WorldModelRecord.policy_slot_map",
            "LegalKnowledgeStore.evaluate_rule_threshold",
            "LegalKnowledgeStore.resolve_threshold_temporal_competence",
            "foundry.methods.selection.registry.get_registry().list_all()",
            "SubstrateRegistry L6 entries",
        ],
        "truthful_data_limitations": [],
        "coverage_gate": {
            "world_slot": "bound must equal total over the real L6 knob dictionary",
            "law_trace": "traced must equal total over the real lex_intervention_map",
            "method_route": (
                "unresolved must be zero over the real observation manifest; "
                "available + python314_unavailable must equal total"
            ),
            "free_grow": (
                "a novel knob with a novel owner mechanism must resolve to a real WMR slot "
                "with zero code registration"
            ),
            "no_hardcode_mutation": (
                "removing owner mechanism derivation or supplying raw target_world_slots "
                "must turn the contract red"
            ),
            "owner_validation_mutations": (
                "a non-existent owner slot and a non-existent L3 provision must fail "
                "closed instead of binding from the tracked artifact alone"
            ),
        },
        "measured_coverage": behavior["coverage"],
        "capability_reality": {
            "typed_contract_artifact": (
                "InterventionSubstrateBundle + InterventionLeverResolution + "
                "LawLeverResolution + ObservationMethodRoute"
            ),
            "producer": (
                "load_l6_intervention_substrate + resolve_intervention_lever + "
                "resolve_law_bound_lever + route_observation_family_method"
            ),
            "persisted_artifact_event": OUTPUT_PATH,
            "orchestration_bridge": (
                "N2 atom lever-space resolution, GY-S2 L3 admissibility, "
                "N8/N4 method route input"
            ),
            "consumer": "GY-N2/GY-N8/GY-N4 via existing owner APIs",
            "verification": "intervention_substrate_behavior_report",
            "surface": "GY-S0 substrate registry + generated contract artifact",
            "semantic_test": "real-data behavior cases + remove-property mutation witnesses",
        },
        "patterns_closed": [
            "P01",
            "P02",
            "P03",
            "P04",
            "P05",
            "P07",
            "P08",
            "P10",
            "P12",
            "P15",
            "P27",
            "P29",
            "P31",
            "P32",
            "P33",
            "P34",
        ],
        "missing_capability_labels": [],
        "json_schemas": {
            "intervention_substrate_bundle": InterventionSubstrateBundle.model_json_schema(),
            "intervention_lever_resolution": InterventionLeverResolution.model_json_schema(),
            "law_lever_resolution": LawLeverResolution.model_json_schema(),
            "observation_method_route": ObservationMethodRoute.model_json_schema(),
        },
        "behavior_report": behavior,
    }
    return json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def validate(repo_root: Path | None = None) -> dict[str, Any]:
    """Validate committed artifact drift and live behavior."""

    repo_root = (repo_root or _default_repo_root()).resolve()
    output_path = repo_root / OUTPUT_PATH
    live = build_live_payload(repo_root)
    issues: list[dict[str, Any]] = []
    if live["behavior_report"]["status"] != "pass":
        issues.extend(live["behavior_report"]["issues"])
    coverage = live["behavior_report"].get("coverage", {})
    world = coverage.get("world_slot", {})
    if world.get("bound") != world.get("total"):
        issues.append({"code": "intervention_substrate_world_slot_coverage_below_gate"})
    law = coverage.get("law_trace", {})
    if law.get("traced") != law.get("total"):
        issues.append({"code": "intervention_substrate_law_trace_coverage_below_gate"})
    methods = coverage.get("method_route", {})
    if methods.get("unresolved") != 0 or (
        methods.get("available", 0) + methods.get("unavailable_python314", 0)
        != methods.get("total")
    ):
        issues.append({"code": "intervention_substrate_method_route_coverage_below_gate"})
    mutation_statuses = {
        str(mutation.get("mutation_id")): str(mutation.get("status"))
        for mutation in live["behavior_report"].get("remove_property_mutations", [])
    }
    missing_mutations = sorted(
        EXPECTED_REMOVE_PROPERTY_MUTATIONS.difference(mutation_statuses)
    )
    if missing_mutations:
        issues.append(
            {
                "code": "intervention_substrate_required_mutation_missing",
                "missing_mutations": missing_mutations,
            }
        )
    non_red_required = sorted(
        mutation_id
        for mutation_id in EXPECTED_REMOVE_PROPERTY_MUTATIONS.intersection(mutation_statuses)
        if mutation_statuses[mutation_id] != "red"
    )
    if non_red_required:
        issues.append(
            {
                "code": "intervention_substrate_required_mutation_not_red",
                "mutation_ids": non_red_required,
            }
        )
    if not output_path.exists():
        issues.append({"code": "intervention_substrate_contract_missing", "path": OUTPUT_PATH})
    else:
        committed = json.loads(output_path.read_text(encoding="utf-8"))
        if committed != live:
            issues.append({"code": "intervention_substrate_contract_drift", "path": OUTPUT_PATH})
    return {
        "status": "pass" if not issues else "fail",
        "artifact": OUTPUT_PATH,
        "outputs": declared_outputs(),
        "issues": issues,
        "behavior_status": live["behavior_report"]["status"],
    }


def write(repo_root: Path | None = None) -> dict[str, Any]:
    """Write the recomputed artifact."""

    repo_root = (repo_root or _default_repo_root()).resolve()
    payload = build_live_payload(repo_root)
    output_path = repo_root / OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return validate(repo_root)


def main(argv: list[str] | None = None) -> int:
    """Run the intervention-substrate contract validator."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_default_repo_root())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output-format", choices=("json", "text"), default="text")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    for item in (str(repo_root / "src"), str(repo_root)):
        if item not in sys.path:
            sys.path.insert(0, item)
    if args.write:
        report = write(repo_root)
    else:
        report = validate(repo_root)
    if args.output_format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"{report['status']}: {report['artifact']}")
        for issue in report["issues"]:
            print(f"- {issue['code']}: {issue.get('path', issue.get('case_id', ''))}")
    if args.check or not args.write:
        return 0 if report["status"] == "pass" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
