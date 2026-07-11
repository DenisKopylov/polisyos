#!/usr/bin/env python3
"""Validate Layer 2 S2 grammar/candidate/search DesignRecord wiring."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import tomllib
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.pdc import (  # noqa: E402
    Layer2S2DesignSearchInput,
    project_s2_design_search,
    run_s2_shadow_design_loop,
)
from polisyos.runtime.quality.proving_ground.pinned_route_demand_home import (  # noqa: E402
    read_layer3_gx_pinned_case_id,
)

DEFAULT_MANIFEST_PATH = Path(
    "architecture/policy_design_case/layer2_s2_design_search_manifest.json"
)
DEFAULT_FIRST_PROVING_CASE_PATH = Path(
    "architecture/policy_design_case/layer2_first_proving_case.json"
)
DEFAULT_CLUSTER_MAP_PATH = Path("architecture/policy_design_case/cluster_ownership_map.toml")
DEFAULT_FLOOR_GOVERNANCE_PATH = Path(
    "architecture/policy_design_case/layer2_floor_governance.toml"
)
DEFAULT_INVENTORY_PATH = Path("architecture/policy_design_case/inventory.json")
DEFAULT_CANONICAL_CASE_PATH = (
    Path("tests/fixtures/universal-corpus/cases")
    / f"{read_layer3_gx_pinned_case_id(REPO_ROOT)}.json"
)
DEFAULT_PRODUCER_STUB_DIR = Path("tests/fixtures/universal-corpus/producer_stubs")

_EXPECTED_CLOSED_CELLS = [
    "INTERVENTION.design_grammar",
    "INTERVENTION.design_candidate",
]
_COUNTEREXAMPLE_VOCABULARY = [
    "real_design_blocker",
    "substrate_gap",
    "a_spec_gap",
    "abstraction_gap",
    "value_gap",
    "budget_gap",
]
_REQUIRED_ARTIFACTS = {
    "DesignGrammarExpansion",
    "DesignCandidateV0",
    "ConstraintStoreSnapshot",
    "CounterexampleRecord",
    "RefinementDecision",
    "SearchLedger",
    "ClusterInterfaceContract",
    "ClusterHandoffRecord",
    "DesignRecordV0",
}
_S2_CANONICAL_ROUTE_ALLOWED_STATUSES = {
    "shadow_ready",
    "acquisition_required",
    "governance_required",
    "blocked",
}


def validate_s2_design_search(repo_root: Path | str = REPO_ROOT) -> dict[str, Any]:
    """Validate S2 design search from manifest through canonical corpus wiring."""

    root = Path(repo_root).resolve()
    manifest = _load_json(root / DEFAULT_MANIFEST_PATH)
    manifest_validation = validate_s2_manifest_payload(manifest)
    if manifest_validation["status"] != "pass":
        return manifest_validation

    input_row = _first_proving_case_input(root)
    run = run_s2_shadow_design_loop(input_row)
    a_spec_run = run_s2_shadow_design_loop(
        input_row.model_copy(update={"forced_counterexample_class": "a_spec_gap"})
    )
    substrate_gap_run = run_s2_shadow_design_loop(
        input_row.model_copy(update={"forced_counterexample_class": "substrate_gap"})
    )
    budget_gap_run = run_s2_shadow_design_loop(
        input_row.model_copy(update={"forced_counterexample_class": "budget_gap"})
    )
    projections = project_s2_design_search(run, audiences=("MACHINE", "REVIEWER"))
    cluster_summary = _cluster_summary(root)
    canonical_status = _canonical_route_status(root)
    governed_floor_ids = _floor_governance_ids(root)
    inventory_registered = _inventory_has_s2_manifest(root)
    expected_open_count = int(manifest["expected_current_open_cell_count"])
    cluster_cells_closed = not (
        set(manifest.get("cells_closed", [])) & cluster_summary["current_open_cells"]
    )

    issues: list[dict[str, str]] = []
    _expect(
        _run_artifact_names(run) >= set(manifest["required_artifacts"]),
        "s2_required_artifacts_missing",
        issues,
    )
    _expect(
        run.search_ledger.counterexample_conversion_rate == 1.0,
        "s2_counterexample_conversion_floor_failed",
        issues,
    )
    _expect(
        "s2_counterexample_conversion" in governed_floor_ids,
        "s2_counterexample_conversion_floor_not_governed",
        issues,
    )
    _expect(
        run.search_ledger.grammar_diversity_minimum == len(input_row.instrument_families)
        and run.search_ledger.instrument_family_coverage == list(input_row.instrument_families)
        and run.grammar_expansion.instrument_families == list(input_row.instrument_families)
        and run.candidates[0].instrument_family == input_row.instrument_families[0]
        and run.candidates[0].parameterization
        == {dimension: values[0] for dimension, values in input_row.parameter_space.items()},
        "s2_grammar_diversity_adequacy_failed",
        issues,
    )
    _expect(
        run.refinement_decisions[0].value_of_information.estimate_id
        == "s2_shadow_refinement_voi"
        and run.refinement_decisions[0].budget_refs
        and run.refinement_decisions[0].stakes_band,
        "s2_refinement_voi_missing",
        issues,
    )
    _expect(
        a_spec_run.status == "governance_required"
        and a_spec_run.refinement_decisions[0].governance_decision_class_ref == "a_spec_gap"
        and a_spec_run.refinement_decisions[0].governance_decision_class is not None,
        "s2_governance_decision_class_invalid",
        issues,
    )
    _expect(
        substrate_gap_run.status == "acquisition_required"
        and substrate_gap_run.search_ledger.acquisition_branch_state == "bridge_missing",
        "s2_substrate_gap_acquisition_bridge_invalid",
        issues,
    )
    _expect(
        budget_gap_run.status == "abstained"
        and "best_known_shadow_frontier"
        in budget_gap_run.search_ledger.search_incompleteness_note,
        "s2_budget_gap_abstention_invalid",
        issues,
    )
    _expect(
        run.search_ledger.acquisition_branch_state == "bridge_missing",
        "s2_acquisition_branch_not_bridge_missing",
        issues,
    )
    _expect(
        list(projections) == ["MACHINE", "REVIEWER"],
        "s2_projection_audiences_missing",
        issues,
    )
    _expect(
        cluster_cells_closed,
        "s2_cluster_open_cell_count_unexpected",
        issues,
    )
    _expect(canonical_status == "pass", "s2_canonical_route_missing", issues)
    if cluster_cells_closed:
        _expect(inventory_registered, "s2_inventory_registration_missing", issues)

    return _result(
        issues,
        summary={
            "slice": "S2",
            "first_proving_case_id": input_row.case_id,
            "current_open_cell_count": cluster_summary["current_open_cell_count"],
            "expected_current_open_cell_count": expected_open_count,
            "cells_closed": list(manifest["cells_closed"]),
            "counterexample_conversion_rate": run.search_ledger.counterexample_conversion_rate,
            "grammar_diversity_minimum": run.search_ledger.grammar_diversity_minimum,
            "governance_decision_classes_verified": list(
                manifest["required_governance_decision_classes"]
            ),
            "voi_sites_verified": list(manifest["required_voi_sites"]),
            "acquisition_branch_state": run.search_ledger.acquisition_branch_state,
            "projection_audiences_verified": list(projections),
            "canonical_route_status": canonical_status,
        },
    )


def validate_s2_manifest_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the S2 manifest without touching runtime producers."""

    issues: list[dict[str, str]] = []
    _expect(
        payload.get("schema_version")
        == "policyos.policy_design_case.layer2_s2_design_search_manifest.v1",
        "s2_manifest_schema_version_invalid",
        issues,
    )
    _expect(payload.get("slice") == "S2", "s2_manifest_slice_invalid", issues)
    _expect(
        payload.get("acquisition_branch_state") == "bridge_missing",
        "s2_acquisition_branch_must_remain_bridge_missing",
        issues,
    )
    _expect(
        list(payload.get("cells_closed") or []) == _EXPECTED_CLOSED_CELLS,
        "s2_cells_closed_invalid",
        issues,
    )
    _expect(
        payload.get("expected_current_open_cell_count") == 15,
        "s2_expected_open_cell_count_invalid",
        issues,
    )
    _expect(
        list(payload.get("counterexample_class_vocabulary") or [])
        == _COUNTEREXAMPLE_VOCABULARY,
        "s2_counterexample_class_vocabulary_invalid",
        issues,
    )
    _expect(
        set(payload.get("required_artifacts") or []) == _REQUIRED_ARTIFACTS,
        "s2_required_artifacts_invalid",
        issues,
    )
    candidate_space = payload.get("candidate_space")
    candidate_space_payload = (
        candidate_space if isinstance(candidate_space, Mapping) else {}
    )
    _expect(
        candidate_space_payload.get("authority_purpose")
        == "shadow_first_proving_case_evidence",
        "s2_candidate_space_authority_purpose_invalid",
        issues,
    )
    families = list(candidate_space_payload.get("instrument_families") or [])
    parameter_space = candidate_space_payload.get("parameter_space")
    parameter_payload = parameter_space if isinstance(parameter_space, Mapping) else {}
    _expect(
        len(families) >= 3
        and len(set(families)) == len(families)
        and all(isinstance(item, str) and item.strip() for item in families),
        "s2_candidate_instrument_families_invalid",
        issues,
    )
    _expect(
        bool(parameter_payload)
        and all(
            isinstance(dimension, str)
            and dimension.strip()
            and isinstance(values, list)
            and bool(values)
            and all(isinstance(value, str) and value.strip() for value in values)
            for dimension, values in parameter_payload.items()
        ),
        "s2_candidate_parameter_space_invalid",
        issues,
    )
    floor_ids = {str(row.get("floor_id")) for row in payload.get("floors") or []}
    _expect(
        floor_ids == {"s2_counterexample_conversion"},
        "s2_floor_set_invalid",
        issues,
    )
    adequacy_rows = list(payload.get("shadow_adequacy_checks") or [])
    adequacy_ids = {str(row.get("check_id")) for row in adequacy_rows}
    _expect(
        adequacy_ids == {"s2_shadow_grammar_diversity"},
        "s2_shadow_adequacy_check_set_invalid",
        issues,
    )
    diversity_rows = [
        row
        for row in adequacy_rows
        if row.get("check_id") == "s2_shadow_grammar_diversity"
    ]
    diversity_required = (
        diversity_rows[0].get("required_value") if len(diversity_rows) == 1 else None
    )
    _expect(
        isinstance(diversity_required, int)
        and diversity_required >= 3
        and len(families) >= diversity_required,
        "s2_shadow_grammar_diversity_floor_invalid",
        issues,
    )
    _expect(
        list(payload.get("required_governance_decision_classes") or []) == ["a_spec_gap"],
        "s2_required_governance_decision_classes_invalid",
        issues,
    )
    _expect(
        list(payload.get("required_voi_sites") or []) == ["s2_refinement_policy"],
        "s2_required_voi_sites_invalid",
        issues,
    )
    layer_contributions = list(payload.get("layer_contributions") or [])
    _expect(
        len(layer_contributions) == 1
        and layer_contributions[0].get("cell_ref")
        == "CROSS_CUTTING.scientist_orchestration"
        and layer_contributions[0].get("closure_owner_slice") == "S7",
        "s2_scientist_orchestration_must_remain_split",
        issues,
    )
    return _result(issues, summary={"slice": str(payload.get("slice", ""))})


def validate_llm_only_candidate_negative_control() -> None:
    """Raise when an LLM-only candidate has no grammar derivation."""

    run_s2_shadow_design_loop(
        _first_proving_case_input(REPO_ROOT).model_copy(
            update={
                "candidate_source_authority": "llm_candidate",
                "omit_grammar_derivation": True,
            }
        )
    )


def _first_proving_case_input(repo_root: Path) -> Layer2S2DesignSearchInput:
    manifest = _load_json(repo_root / DEFAULT_MANIFEST_PATH)
    proving_case = _load_json(repo_root / DEFAULT_FIRST_PROVING_CASE_PATH)
    candidate_space = dict(manifest["candidate_space"])
    constructs = tuple(str(item) for item in proving_case.get("constructs", []))
    return Layer2S2DesignSearchInput(
        case_id=str(manifest["first_proving_case_id"]),
        intent_ref="repo://architecture/policy_design_case/layer2_first_proving_case.json",
        grammar_ref="repo://src/polisyos/policy_grammar",
        instrument_families=tuple(candidate_space["instrument_families"]),
        parameter_space={
            str(dimension): tuple(values)
            for dimension, values in dict(candidate_space["parameter_space"]).items()
        },
        actor_ref="actor://ua/ministry-of-economy",
        domain="ukrainian_msme_credit",
        objective_refs=tuple(f"objective://{item}" for item in constructs),
        construct_refs=tuple(f"construct://{item}" for item in constructs),
        authority_profile_ref="authority_profile.shadow",
        requested_posture="shadow",
        generated_at=datetime(2026, 5, 30, tzinfo=UTC),
        rule_version_ref="policyos.layer2.s2.design_search.v1",
    )


def _run_artifact_names(run: object) -> set[str]:
    return {
        run.grammar_expansion.__class__.__name__,
        run.candidates[0].__class__.__name__,
        run.constraint_store.__class__.__name__,
        run.counterexamples[0].__class__.__name__,
        run.refinement_decisions[0].__class__.__name__,
        run.search_ledger.__class__.__name__,
        run.cluster_interface_contracts[0].__class__.__name__,
        run.handoff_records[0].__class__.__name__,
        run.design_record.__class__.__name__,
    }


def _cluster_summary(repo_root: Path) -> dict[str, object]:
    payload = _load_toml(repo_root / DEFAULT_CLUSTER_MAP_PATH)
    open_cells = {
        f"{cluster}.{axis}"
        for cluster, axes in payload.get("open_cell_closure", {}).items()
        for axis in axes
    }
    return {"current_open_cell_count": len(open_cells), "current_open_cells": open_cells}


def _floor_governance_ids(repo_root: Path) -> set[str]:
    payload = _load_toml(repo_root / DEFAULT_FLOOR_GOVERNANCE_PATH)
    return {str(row.get("floor_id")) for row in payload.get("floor", [])}


def _inventory_has_s2_manifest(repo_root: Path) -> bool:
    payload = _load_json(repo_root / DEFAULT_INVENTORY_PATH)
    return any(
        row.get("id") == "layer2_s2_design_search_manifest"
        and row.get("path") == DEFAULT_MANIFEST_PATH.as_posix()
        for row in payload.get("artifacts", [])
    )


def _canonical_route_status(repo_root: Path) -> str:
    from tools.quality.validation import run_universal_outcome_corpus as w12d

    with tempfile.TemporaryDirectory() as temp_dir:
        scratch = Path(temp_dir)
        report = w12d.run_w12d_universal_outcome_corpus(
            repo_root=repo_root,
            corpus_path=repo_root / DEFAULT_CANONICAL_CASE_PATH,
            graph_output_dir=scratch / "graphs",
            hypothesis_ledger_output_dir=scratch / "ledgers",
            mode="corpus_stub",
            producer_stub_dir=repo_root / DEFAULT_PRODUCER_STUB_DIR,
        )
    cases = list(report.get("cases") or [])
    if not cases:
        return "fail"
    s2 = cases[0].get("s2_design_search")
    if not isinstance(s2, Mapping):
        return "fail"
    constraint_store = s2.get("constraint_store")
    if (
        s2.get("status") in _S2_CANONICAL_ROUTE_ALLOWED_STATUSES
        and s2.get("canonical_outcome_effect") == "none_shadow_only"
        and isinstance(constraint_store, Mapping)
        and constraint_store.get("constraint_records")
        and s2.get("design_record")
    ):
        return "pass"
    return "fail"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _expect(
    condition: bool,
    code: str,
    issues: list[dict[str, str]],
) -> None:
    if not condition:
        issues.append(_issue(code, code.replace("_", " ")))


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _result(issues: list[dict[str, str]], *, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "fail" if issues else "pass",
        **summary,
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the S2 design-search validator."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--json-output", default="")
    args = parser.parse_args(argv)

    result = validate_s2_design_search(args.repo_root)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.json_output:
        Path(args.json_output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
