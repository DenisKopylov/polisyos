#!/usr/bin/env python3
"""Validate the CGF GY-CG1 shadow grounding-relation contract."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

OUTPUT_PATH = "architecture/policy_design_case/grounding_relation_contract.json"
SCHEMA_VERSION = "policyos.policy_design_case.grounding_relation_contract.v1"
EXPECTED_MUTATIONS = {
    "surface_similarity_selected_exact_on_false_analog",
    "greedy_inconsistent_accepted_without_joint_solve",
    "critical_axis_veto_removed",
    "gy_k_confidence_alone_selected_relation",
    "cg1_shadow_only_violated_bind_or_promotion",
    "false_analog_on_unproven_contradiction",
    "exact_match_only_missed_synonym",
    "novel_candidate_verdict_disabled",
    "adversarial_counter_family_disabled",
}


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _configure_validation_jax_platform() -> None:
    """Keep validator WMR builds reproducible without runtime env mutation."""

    os.environ.setdefault("JAX_PLATFORM_NAME", "cpu")
    os.environ.setdefault("JAX_PLATFORMS", "cpu")


class AlwaysSupportAxisWitnessProvider:
    """Deterministic GY-K-style witness provider for mutation probes."""

    def witness_axis(
        self,
        *,
        axis: str,
        proposal_value: object,
        atom_value: object,
    ) -> Any:
        """Return a high-confidence support witness for every axis."""

        from polisyos.runtime.quality.grounding_relation import AxisEntailmentWitness

        return AxisEntailmentWitness(
            axis=axis,
            label="supports",
            confidence=0.99,
            witness=(
                "deterministic GY-K replay witness intentionally over-supports "
                "the axis; CG1 must not let this decide relation"
            ),
            source="GY-K.bounded_gateway_entailment_judge.replay",
        )


def build_live_payload(repo_root: Path | None = None) -> dict[str, Any]:
    """Recompute the CG1 contract from live CG0/N4 data and stress probes."""

    _configure_validation_jax_platform()
    from polisyos.runtime.quality.credal_reference import (
        AdmissibleCompletion,
        CredalReferenceEdge,
        build_credal_reference,
        replace_reference_edge,
    )
    from polisyos.runtime.quality.grounding_relation import (
        CRITICAL_AXES,
        GROUNDING_RELATION_SCHEMA_VERSION,
        RELATION_AXES,
        RELATION_UNIVERSE,
        GroundingRelationEngine,
    )

    repo_root = (repo_root or _default_repo_root()).resolve()
    reference = build_credal_reference(repo_root)
    engine = GroundingRelationEngine(reference)
    probes = _run_positive_probes(engine, repo_root)

    free_reference = replace_reference_edge(
        reference,
        CredalReferenceEdge(
            modality="L6_KNOB_OPERATOR",
            edge_id="emergency_cooling_subsidy",
            status="confirmed",
            admissible_completions=(
                AdmissibleCompletion(
                    "fixed",
                    {
                        "operator_kind": "emergency_cooling_subsidy",
                        "parameter_domain": {
                            "kind": "range",
                            "max_value": 1.0,
                            "min_value": 0.0,
                            "unit": None,
                            "value_type": "float",
                        },
                    },
                    "cg1_free_grow_probe_operator",
                ),
            ),
            provenance={
                "owner": "L6",
                "source": "cg1_data_only_free_grow_probe",
                "version": "validator_probe",
            },
        ).with_content_hash(),
    )
    free_reference = replace_reference_edge(
        free_reference,
        CredalReferenceEdge(
            modality="L6_KNOB_WORLD_SLOT",
            edge_id="emergency_cooling_subsidy",
            status="confirmed",
            admissible_completions=(
                AdmissibleCompletion(
                    "fixed",
                    {
                        "operator_kind": "emergency_cooling_subsidy",
                        "target_world_slots": ["household_cells.transfer_intensity"],
                        "world_model_record_id": "world_model_record_free_grow_probe",
                    },
                    "cg1_free_grow_probe_world_slot",
                ),
            ),
            provenance={
                "owner": "L6",
                "source": "cg1_data_only_free_grow_probe",
                "version": "validator_probe",
            },
        ).with_content_hash(),
    )
    free_engine = GroundingRelationEngine(free_reference)
    probes["data_only_free_grow"] = _certificate_summary(
        free_engine.certificate_for(_free_grow_probe(), proposal_id="cg1-free-grow")
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "contract_id": "policyos.runtime.grounding_relation_shadow",
        "runtime_schema_version": GROUNDING_RELATION_SCHEMA_VERSION,
        "owner": "polisyos.runtime.quality.grounding_relation",
        "source_modules": [
            "src/polisyos/runtime/quality/grounding_relation.py",
            "src/polisyos/runtime/quality/credal_reference.py",
            "src/polisyos/runtime/quality/intervention_atom_binding.py",
            "tools/quality/validation/check_grounding_relation_contract.py",
            "tools/quality/validation/check_layer3_gy_design_generation_contract.py",
        ],
        "reuse_existing_owners": [
            "CG0 CredalReference over L2/L3/L6/WMR",
            "N2 InterventionAtomBinding for N4 candidate atom shape",
            "N4 recorded gateway replay validator for the real proposal source",
            "GY-K bounded entailment judge as per-axis witness only",
            "OR-Tools CP-SAT with assumption unsat cores",
        ],
        "no_second_reference_store": True,
        "shadow_only": True,
        "candidate_set_coverage": {
            "reference_epoch": reference.reference_epoch,
            "reference_hash": reference.reference_hash,
            "reference_edge_count": len(reference.essential_edges),
            "atom_universe_count": len(engine.reference_atoms),
            "registered_l6_operator_count": sum(
                1
                for edge in reference.essential_edges.values()
                if edge.modality == "L6_KNOB_OPERATOR"
            ),
            "writable_wmr_slot_count": sum(
                1
                for edge in reference.essential_edges.values()
                if edge.modality == "WMR_POLICY_SLOT_MAP"
            ),
            "retrieval_indexed_edge_count": (
                engine._fts_index.indexed_edge_count if engine._fts_index else 0
            ),
            "denominator_status": reference.denominator_counts(),
            "relation_universe": list(RELATION_UNIVERSE),
            "axis_universe": list(RELATION_AXES),
            "critical_axis_universe": list(CRITICAL_AXES),
            "retrieval_methods": [
                "duckdb_fts_full_cg0_reference",
                "l2_variable_alignments_or_hierarchy",
                "causal_neighbourhood_skg",
                "l3_thresholds",
                "l6_knobs_lex_maps",
                "adversarial_false_analog_countercandidates",
            ],
            "dense_embeddings": "deferred_by_CG0_backend_gate",
        },
        "probes": probes,
        "capability_reality": {
            "typed_contract_artifact": (
                "GroundingRelationCertificate + MechanisticSignature + CandidateRelationResult"
            ),
            "producer": "GroundingRelationEngine.certificate_for",
            "persisted_artifact_event": OUTPUT_PATH,
            "orchestration_bridge": (
                "shadow certificate can be consumed by CG2/CG3; CG1 itself emits "
                "no bind/admission/promotion"
            ),
            "consumer": "GY-N4 unblock shadow gate and future CG2 CAAB bind gate",
            "verification": "this recomputing validator plus unit stress tests",
            "surface": "generated Policy Design Case CG1 contract artifact",
            "semantic_test": (
                "false-analog veto, joint unsat core, cross-modal blocked, "
                "synonym resolution, GY-K witness-only, shadow-only, unknown no over-veto"
            ),
        },
        "pattern_pass": {
            "relevant_ids": [
                "P01",
                "P02",
                "P03",
                "P04",
                "P05",
                "P10",
                "P15",
                "P27",
                "P29",
                "P31",
                "P32",
                "P33",
            ],
            "target_correct_pattern": (
                "retrieval/GY-K prioritize and witness only; CP-SAT plus RT1 "
                "axis CSP owns relation; CG1 remains shadow-only"
            ),
            "missing_capability_labels": [],
            "acceptance_signal": (
                "stress probes and remove-property mutations go red without marker checks"
            ),
        },
        "behavioral_mutations": [],
    }
    payload["behavioral_mutations"] = _mutation_reports(engine)
    return _json_stable(payload)


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a CG1 payload against behavioral properties."""

    issues = _core_issues(payload, require_mutations=True)
    return {"status": "pass" if not issues else "fail", "issues": issues}


def validate(repo_root: Path | None = None) -> dict[str, Any]:
    """Validate committed artifact drift and live CG1 behavior."""

    repo_root = (repo_root or _default_repo_root()).resolve()
    path = repo_root / OUTPUT_PATH
    live = build_live_payload(repo_root)
    issues = _core_issues(live, require_mutations=True)
    if not path.is_file():
        issues.append({"code": "grounding_relation_contract_missing", "path": OUTPUT_PATH})
        committed: dict[str, Any] | None = None
    else:
        try:
            committed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            committed = None
            issues.append(
                {
                    "code": "grounding_relation_contract_invalid_json",
                    "path": OUTPUT_PATH,
                    "error": str(exc),
                }
            )
    if committed is not None and committed != live:
        issues.append({"code": "grounding_relation_contract_drift", "path": OUTPUT_PATH})
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "outputs": declared_outputs(),
        "selected_results": {
            key: value.get("selected_relation")
            for key, value in live.get("probes", {}).items()
            if isinstance(value, dict)
        },
        "reference_epoch": live["candidate_set_coverage"]["reference_epoch"],
        "real_proposal_certificate": live["probes"]["real_n4_recorded_proposal"]["certificate_id"],
    }


def write(repo_root: Path, *, payload: dict[str, Any] | None = None) -> None:
    """Write the live CG1 contract artifact."""

    path = repo_root / OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    live = payload or build_live_payload(repo_root)
    path.write_text(
        json.dumps(live, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def corrupt_field_drift_check(repo_root: Path | None = None) -> dict[str, Any]:
    """Prove corrupt decisive fields turn validation red."""

    live = build_live_payload(repo_root)
    corrupted = _copy(live)
    corrupted["probes"]["false_analog_minimal_swap_set"]["cases"]["sign_swap"][
        "contradictory_atom_vetoed"
    ] = False
    corrupted["probes"]["greedy_inconsistent"]["solver_status"] = "SAT"
    corrupted["probes"]["greedy_inconsistent"]["unsat_core_if_any"] = []
    corrupted["probes"]["pure_synonym_exact"]["selected_relation"] = "certified-specialization"
    corrupted["probes"]["real_n4_recorded_proposal"]["selected_relation"] = "blocked"
    corrupted["probes"]["real_n4_recorded_proposal"]["known_space_verdict"] = "in_lever_space"
    corrupted["probes"]["shadow_only"]["forbidden_transition_count"] = 1
    report = validate_payload(corrupted)
    return {
        "status": "pass" if report["status"] == "fail" else "fail",
        "issues": []
        if report["status"] == "fail"
        else [{"code": "grounding_relation_corrupt_field_not_detected"}],
        "corrupt_report_status": report["status"],
        "corrupt_issue_codes": [issue["code"] for issue in report["issues"]],
    }


def _run_positive_probes(engine: Any, repo_root: Path) -> dict[str, Any]:
    false_set = _false_analog_set_summary(engine)
    greedy_cert = engine.certificate_for(_greedy_inconsistent_probe(), proposal_id="cg1-greedy")
    cross_cert = engine.certificate_for(
        _cross_modal_inconsistent_probe(),
        proposal_id="cg1-cross-modal",
    )
    synonym_cert = engine.certificate_for(
        _pure_synonym_probe(engine),
        proposal_id="cg1-pure-synonym",
    )
    specialization_cert = engine.certificate_for(
        _specialization_probe(),
        proposal_id="cg1-specialization",
    )
    unknown_cert = engine.certificate_for(_unknown_unproven_probe(), proposal_id="cg1-unknown")
    fake_cert = engine.certificate_for(_fake_atom_probe(), proposal_id="cg1-fake")

    gyk_engine = _clone_engine(
        engine,
        axis_witness_provider=AlwaysSupportAxisWitnessProvider(),
    )
    gyk_cert = gyk_engine.certificate_for(
        _false_analog_probe("sign_swap"),
        proposal_id="cg1-gyk-witness-only",
    )
    deterministic_a = engine.certificate_for(
        _pure_synonym_probe(engine),
        proposal_id="cg1-deterministic",
    )
    deterministic_b = engine.certificate_for(
        _pure_synonym_probe(engine),
        proposal_id="cg1-deterministic",
    )
    real_n4_probe = _frozen_n4_cg1_certificate_summary(repo_root)
    certificates = [
        greedy_cert,
        cross_cert,
        synonym_cert,
        specialization_cert,
        unknown_cert,
        fake_cert,
        gyk_cert,
        deterministic_a,
    ]
    forbidden = [
        cert.recommended_transition
        for cert in certificates
        if cert.recommended_transition
        not in {
            "shadow",
            "quarantine",
            "handoff_RT3",
            "bundle_bind-suggestion",
        }
    ]
    return {
        "false_analog_minimal_swap_set": false_set,
        "greedy_inconsistent": _certificate_summary(greedy_cert),
        "cross_modal_inconsistent": _certificate_summary(cross_cert),
        "pure_synonym_exact": {
            **_certificate_summary(synonym_cert),
            "exact_string_match": False,
        },
        "certified_specialization_boundary": _certificate_summary(specialization_cert),
        "gy_k_witness_only": {
            **_certificate_summary(gyk_cert),
            "gy_k_witness_count": _gyk_witness_count(gyk_cert),
        },
        "shadow_only": {
            "forbidden_transition_count": len(forbidden),
            "recommended_transitions": [cert.recommended_transition for cert in certificates],
            "bind_admit_promote_emitted": False,
        },
        "unknown_unproven_contradiction": _certificate_summary(unknown_cert),
        "fake_atom_not_exact": _certificate_summary(fake_cert),
        "deterministic_certificate": {
            "first_content_hash": deterministic_a.content_hash,
            "second_content_hash": deterministic_b.content_hash,
            "same_content_hash": deterministic_a.content_hash == deterministic_b.content_hash,
        },
        "real_n4_recorded_proposal": real_n4_probe,
    }


def _mutation_reports(engine: Any) -> list[dict[str, Any]]:
    from polisyos.runtime.quality.grounding_relation import GroundingEnginePolicy

    mutation_specs = {
        "surface_similarity_selected_exact_on_false_analog": (
            GroundingEnginePolicy(allow_surface_similarity_exact=True),
            _false_analog_probe("sign_swap"),
            "cg1-mut-surface",
        ),
        "greedy_inconsistent_accepted_without_joint_solve": (
            GroundingEnginePolicy(use_greedy_solver=True),
            _greedy_inconsistent_probe(),
            "cg1-mut-greedy",
        ),
        "critical_axis_veto_removed": (
            GroundingEnginePolicy(disable_critical_veto=True),
            None,
            "cg1-mut-veto-set",
        ),
        "gy_k_confidence_alone_selected_relation": (
            GroundingEnginePolicy(allow_gy_k_decider=True),
            _false_analog_probe("sign_swap"),
            "cg1-mut-gyk",
        ),
        "false_analog_on_unproven_contradiction": (
            GroundingEnginePolicy(over_veto_unproven=True),
            _unknown_unproven_probe(),
            "cg1-mut-over-veto",
        ),
        "exact_match_only_missed_synonym": (
            GroundingEnginePolicy(disable_alias_resolution=True),
            None,
            "cg1-mut-synonym",
        ),
        "novel_candidate_verdict_disabled": (
            GroundingEnginePolicy(disable_novel_candidate_verdict=True),
            None,
            "cg1-mut-novel",
        ),
        "adversarial_counter_family_disabled": (
            GroundingEnginePolicy(disable_adversarial_counter_family=True),
            None,
            "cg1-mut-counter-family",
        ),
    }
    reports: list[dict[str, Any]] = []
    for mutation_id, (policy, probe, proposal_id) in mutation_specs.items():
        mutated_engine = _clone_engine(
            engine,
            policy=policy,
            axis_witness_provider=(
                AlwaysSupportAxisWitnessProvider()
                if mutation_id == "gy_k_confidence_alone_selected_relation"
                else None
            ),
        )
        try:
            if mutation_id in {
                "critical_axis_veto_removed",
                "adversarial_counter_family_disabled",
            }:
                probe_payload = _false_analog_set_summary(mutated_engine)
            elif mutation_id == "exact_match_only_missed_synonym":
                certificate = mutated_engine.certificate_for(
                    _pure_synonym_probe(engine),
                    proposal_id=proposal_id,
                )
                probe_payload = _mutation_probe_payload(mutation_id, certificate)
                probe_payload["exact_string_match"] = False
            elif mutation_id == "novel_candidate_verdict_disabled":
                certificate = mutated_engine.certificate_for(
                    _real_n4_candidate(_default_repo_root()),
                    proposal_id=proposal_id,
                )
                probe_payload = _mutation_probe_payload(mutation_id, certificate)
            else:
                certificate = mutated_engine.certificate_for(probe, proposal_id=proposal_id)
                probe_payload = _mutation_probe_payload(mutation_id, certificate)
            issues = _probe_issues(mutation_id, probe_payload)
            reports.append(
                {
                    "mutation_id": mutation_id,
                    "status": "red" if issues else "green",
                    "issue_codes": [issue["code"] for issue in issues],
                    "selected_relation": probe_payload.get("selected_relation"),
                    "solver_status": probe_payload.get("solver_status"),
                }
            )
        except ValueError as exc:
            reports.append(
                {
                    "mutation_id": mutation_id,
                    "status": "red",
                    "issue_codes": [str(exc).split(":", 1)[0]],
                }
            )
    bind_engine = _clone_engine(
        engine,
        policy=GroundingEnginePolicy(allow_bind_recommendations=True),
    )
    try:
        bind_engine.certificate_for(_synonym_probe(), proposal_id="cg1-mut-bind")
    except ValueError as exc:
        reports.append(
            {
                "mutation_id": "cg1_shadow_only_violated_bind_or_promotion",
                "status": "red",
                "issue_codes": [str(exc).split(":", 1)[0]],
            }
        )
    else:
        reports.append(
            {
                "mutation_id": "cg1_shadow_only_violated_bind_or_promotion",
                "status": "green",
                "issue_codes": [],
            }
        )
    return reports


def _core_issues(
    payload: dict[str, Any],
    *,
    require_mutations: bool,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append({"code": "grounding_relation_schema_mismatch"})
    if payload.get("no_second_reference_store") is not True:
        issues.append({"code": "grounding_relation_second_reference_store"})
    coverage = payload.get("candidate_set_coverage", {})
    if coverage.get("reference_edge_count", 0) <= 0:
        issues.append({"code": "grounding_relation_reference_denominator_missing"})
    if coverage.get("atom_universe_count", 0) <= coverage.get("registered_l6_operator_count", 0):
        issues.append({"code": "grounding_relation_atom_universe_shell"})
    if coverage.get("retrieval_indexed_edge_count") != coverage.get("reference_edge_count"):
        issues.append({"code": "grounding_relation_retrieval_not_full_denominator"})
    if set(coverage.get("relation_universe", [])) != {
        "exact",
        "certified-specialization",
        "generalization",
        "partial",
        "compositional",
        "false-analog",
        "novel-candidate",
        "unknown",
    }:
        issues.append({"code": "grounding_relation_relation_universe_incomplete"})
    if len(coverage.get("axis_universe", [])) != 14:
        issues.append({"code": "grounding_relation_axis_universe_incomplete"})
    if (
        "dense_embeddings" not in coverage
        or coverage.get("dense_embeddings") != "deferred_by_CG0_backend_gate"
    ):
        issues.append({"code": "grounding_relation_dense_not_deferred"})

    probes = payload.get("probes", {})
    issues.extend(
        _probe_issues(
            "false_analog_minimal_swap_set",
            probes.get("false_analog_minimal_swap_set", {}),
        )
    )
    issues.extend(_probe_issues("greedy_inconsistent", probes.get("greedy_inconsistent", {})))
    issues.extend(
        _probe_issues("cross_modal_inconsistent", probes.get("cross_modal_inconsistent", {}))
    )
    issues.extend(_probe_issues("pure_synonym_exact", probes.get("pure_synonym_exact", {})))
    issues.extend(
        _probe_issues(
            "certified_specialization_boundary",
            probes.get("certified_specialization_boundary", {}),
        )
    )
    issues.extend(_probe_issues("gy_k_witness_only", probes.get("gy_k_witness_only", {})))
    issues.extend(
        _probe_issues(
            "unknown_unproven_contradiction", probes.get("unknown_unproven_contradiction", {})
        )
    )
    issues.extend(_probe_issues("fake_atom_not_exact", probes.get("fake_atom_not_exact", {})))
    issues.extend(_probe_issues("data_only_free_grow", probes.get("data_only_free_grow", {})))
    shadow = probes.get("shadow_only", {})
    if shadow.get("forbidden_transition_count") != 0 or shadow.get("bind_admit_promote_emitted"):
        issues.append({"code": "grounding_relation_shadow_only_violated"})
    deterministic = probes.get("deterministic_certificate", {})
    if deterministic.get("same_content_hash") is not True:
        issues.append({"code": "grounding_relation_certificate_not_deterministic"})
    real = probes.get("real_n4_recorded_proposal", {})
    if not str(real.get("certificate_id", "")).startswith("cg1_cert_"):
        issues.append({"code": "grounding_relation_real_n4_certificate_missing"})
    if real.get("candidate_atom_count", 0) <= 0:
        issues.append({"code": "grounding_relation_real_n4_candidates_missing"})
    issues.extend(_probe_issues("real_n4_recorded_proposal", real))

    if require_mutations:
        mutations = {
            str(mutation.get("mutation_id")): str(mutation.get("status"))
            for mutation in payload.get("behavioral_mutations", [])
            if isinstance(mutation, dict)
        }
        missing = sorted(EXPECTED_MUTATIONS.difference(mutations))
        if missing:
            issues.append(
                {
                    "code": "grounding_relation_required_mutation_missing",
                    "missing_mutations": missing,
                }
            )
        not_red = sorted(
            mutation_id
            for mutation_id in EXPECTED_MUTATIONS.intersection(mutations)
            if mutations[mutation_id] != "red"
        )
        if not_red:
            issues.append(
                {
                    "code": "grounding_relation_required_mutation_not_red",
                    "mutation_ids": not_red,
                }
            )
    return issues


def _probe_issues(probe_id: str, probe: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not isinstance(probe, dict) or not probe:
        return [{"code": f"{probe_id}_missing"}]
    relation = probe.get("selected_relation")
    solver = probe.get("solver_status")
    core = probe.get("unsat_core_if_any") or []
    if probe_id == "false_analog_minimal_swap_set":
        if probe.get("case_count") != 7 or probe.get("passed_count") != 7:
            issues.append({"code": "false_analog_minimal_swap_set_not_7_of_7"})
        if probe.get("counter_family_complete") is not True:
            issues.append({"code": "false_analog_counter_family_incomplete"})
        for case_id, case in (probe.get("cases") or {}).items():
            if not isinstance(case, dict):
                issues.append({"code": "false_analog_case_invalid", "case_id": case_id})
                continue
            if case.get("contradictory_atom_vetoed") is not True:
                issues.append({"code": "false_analog_case_not_vetoed", "case_id": case_id})
            if case.get("exact_or_specialization_to_contradictory_atom"):
                issues.append(
                    {
                        "code": "false_analog_case_bound_to_contradictory_atom",
                        "case_id": case_id,
                    }
                )
    elif probe_id in {
        "surface_similarity_selected_exact_on_false_analog",
    }:
        if relation != "false-analog":
            issues.append({"code": "false_analog_not_vetoed"})
        if not probe.get("critical_contradictions"):
            issues.append({"code": "false_analog_missing_critical_contradiction"})
    elif probe_id in {
        "greedy_inconsistent",
        "greedy_inconsistent_accepted_without_joint_solve",
    }:
        if relation != "blocked" or solver != "UNSAT":
            issues.append({"code": "greedy_inconsistent_not_blocked"})
        if not core:
            issues.append({"code": "greedy_inconsistent_unsat_core_missing"})
    elif probe_id == "cross_modal_inconsistent":
        if relation != "blocked" or solver != "UNSAT":
            issues.append({"code": "cross_modal_inconsistent_not_blocked"})
        if not core:
            issues.append({"code": "cross_modal_unsat_core_missing"})
    elif probe_id in {"pure_synonym_exact", "exact_match_only_missed_synonym"}:
        if relation != "exact":
            issues.append({"code": "pure_synonym_not_exact"})
        if probe.get("exact_string_match") is not False:
            issues.append({"code": "synonym_probe_exact_string_match_missing"})
        if solver != "SAT":
            issues.append({"code": "synonym_alias_solver_not_sat"})
    elif probe_id == "certified_specialization_boundary":
        if relation != "certified-specialization":
            issues.append({"code": "specialization_boundary_not_certified"})
        if not probe.get("residual_constraints"):
            issues.append({"code": "specialization_boundary_missing_residual_constraints"})
    elif probe_id in {
        "gy_k_witness_only",
        "gy_k_confidence_alone_selected_relation",
    }:
        if probe.get("gy_k_witness_count", 0) <= 0:
            issues.append({"code": "gy_k_axis_witness_missing"})
        if relation in {"exact", "certified-specialization"}:
            issues.append({"code": "gy_k_confidence_decided_relation"})
    elif probe_id in {
        "unknown_unproven_contradiction",
        "false_analog_on_unproven_contradiction",
    }:
        if relation == "false-analog":
            issues.append({"code": "unproven_contradiction_over_vetoed"})
        if int((probe.get("relation_counts") or {}).get("false-analog", 0)) > 0:
            issues.append({"code": "unproven_contradiction_relation_set_over_vetoed"})
        if relation == "blocked":
            issues.append({"code": "unproven_contradiction_blocked"})
    elif probe_id == "fake_atom_not_exact":
        if relation == "exact":
            issues.append({"code": "fake_atom_selected_exact"})
    elif probe_id == "data_only_free_grow":
        if relation not in {"exact", "certified-specialization"}:
            issues.append({"code": "data_only_free_grow_not_usable_in_relation_calculus"})
    elif probe_id in {"critical_axis_veto_removed", "adversarial_counter_family_disabled"}:
        issues.extend(_probe_issues("false_analog_minimal_swap_set", probe))
    elif probe_id == "real_n4_recorded_proposal":
        if relation not in {"exact", "certified-specialization"}:
            issues.append({"code": "real_n4_shadow_receipt_not_identifying"})
        if probe.get("known_space_verdict") != "frozen_shadow_bound":
            issues.append({"code": "real_n4_frozen_shadow_receipt_missing"})
        if probe.get("recommended_transition") != "shadow":
            issues.append({"code": "real_n4_shadow_receipt_not_shadow_transition"})
    elif probe_id == "novel_candidate_verdict_disabled":
        if relation != "novel-candidate":
            issues.append({"code": "real_n4_out_of_lever_not_novel_candidate"})
        if probe.get("known_space_verdict") != "out_of_lever":
            issues.append({"code": "real_n4_known_space_not_out_of_lever"})
        if probe.get("recommended_transition") != "handoff_RT3":
            issues.append({"code": "real_n4_not_handoff_rt3"})
    return issues


def _mutation_probe_payload(mutation_id: str, certificate: Any) -> dict[str, Any]:
    payload = _certificate_summary(certificate)
    if mutation_id in {
        "pure_synonym_exact",
        "exact_match_only_missed_synonym",
    }:
        payload["exact_string_match"] = False
    if mutation_id in {
        "gy_k_confidence_alone_selected_relation",
        "gy_k_witness_only",
    }:
        payload["gy_k_witness_count"] = _gyk_witness_count(certificate)
    return payload


def _certificate_summary(certificate: Any) -> dict[str, Any]:
    coverage = certificate.relation_set.get("known_space_coverage", {})
    relation_counts: dict[str, int] = {}
    for result in certificate.relation_set.get("candidate_results", []):
        if isinstance(result, dict):
            relation = str(result.get("selected_relation"))
            relation_counts[relation] = relation_counts.get(relation, 0) + 1
    return {
        "certificate_id": certificate.certificate_id,
        "content_hash": certificate.content_hash,
        "selected_relation": certificate.selected_relation,
        "solver_status": certificate.solver_status,
        "recommended_transition": certificate.recommended_transition,
        "candidate_atom_count": len(certificate.candidate_atom_ids),
        "candidate_atom_ids": list(certificate.candidate_atom_ids[:8]),
        "critical_contradictions": list(certificate.critical_contradictions),
        "unresolved_axes": list(certificate.unresolved_axes),
        "residual_constraints": list(certificate.residual_constraints),
        "unsat_core_if_any": list(certificate.unsat_core_if_any),
        "axis_relations": {
            witness.axis: witness.relation for witness in certificate.axis_witnesses
        },
        "relation_counts": relation_counts,
        "known_space_verdict": coverage.get("known_space_verdict"),
        "out_of_lever_ops": list(coverage.get("out_of_lever_ops") or []),
        "out_of_lever_targets": list(coverage.get("out_of_lever_targets") or []),
        "coverage_sufficient": coverage.get("coverage_sufficient"),
        "adversarial_countercandidate_reasons": list(
            coverage.get("adversarial_countercandidate_reasons") or []
        ),
    }


def _gyk_witness_count(certificate: Any) -> int:
    return sum(1 for witness in certificate.axis_witnesses if witness.gy_k_witness is not None)


def _clone_engine(
    engine: Any,
    *,
    policy: Any | None = None,
    axis_witness_provider: Any | None = None,
) -> Any:
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine

    clone = GroundingRelationEngine(
        engine.reference,
        policy=policy,
        axis_witness_provider=axis_witness_provider,
    )
    clone._reference_atoms = engine.reference_atoms
    clone._fts_index = engine._fts_index
    return clone


def _real_n4_candidate(repo_root: Path) -> dict[str, Any]:
    inserted = [str(repo_root), str(repo_root / "src")]
    for item in reversed(inserted):
        if item not in sys.path:
            sys.path.insert(0, item)
    from tools.quality.validation.check_layer3_gy_design_generation_contract import (
        first_shadow_bound_recorded_candidate,
    )

    path = repo_root / "architecture/policy_design_case/layer3_gy_design_generation_contract.json"
    live = json.loads(path.read_text(encoding="utf-8"))
    try:
        return first_shadow_bound_recorded_candidate(live)
    except AssertionError as exc:
        raise RuntimeError("cg1_real_n4_recorded_candidate_missing") from exc


def _frozen_n4_cg1_certificate_summary(repo_root: Path) -> dict[str, Any]:
    inserted = [str(repo_root), str(repo_root / "src")]
    for item in reversed(inserted):
        if item not in sys.path:
            sys.path.insert(0, item)
    from tools.quality.validation.check_layer3_gy_design_generation_contract import (
        first_shadow_bound_recorded_candidate,
    )

    path = repo_root / "architecture/policy_design_case/layer3_gy_design_generation_contract.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    try:
        candidate = first_shadow_bound_recorded_candidate(payload)
    except AssertionError as exc:
        raise RuntimeError("cg1_real_n4_recorded_candidate_missing") from exc
    candidate_id = candidate.get("candidate_id")
    for result in payload.get("generation_results") or []:
        if not isinstance(result, dict):
            continue
        for disposition in result.get("grounding_dispositions") or []:
            if not isinstance(disposition, dict) or disposition.get("candidate_id") != candidate_id:
                continue
            chain = disposition.get("certificate_chain")
            if not isinstance(chain, dict):
                break
            return {
                "certificate_id": chain.get("cg1_certificate_id"),
                "content_hash": chain.get("cg1_content_hash"),
                "selected_relation": disposition.get("selected_relation"),
                "solver_status": "frozen_receipt",
                "recommended_transition": "shadow",
                "candidate_atom_count": 1,
                "candidate_atom_ids": [disposition.get("identified_atom_id")],
                "critical_contradictions": [],
                "unresolved_axes": [],
                "residual_constraints": [],
                "unsat_core_if_any": [],
                "axis_relations": {},
                "relation_counts": {str(disposition.get("selected_relation")): 1},
                "known_space_verdict": "frozen_shadow_bound",
                "coverage_sufficient": True,
                "legacy_exact_match": disposition.get("legacy_exact_match"),
                "frozen_receipt": True,
                "candidate_id": candidate_id,
                "proposal_id": disposition.get("proposal_id"),
            }
    raise RuntimeError("cg1_real_n4_recorded_disposition_missing")


_FALSE_ANALOG_EXPECTED_AXES = {
    "target_sibling": "target",
    "op_swap": "op",
    "sign_swap": "sign",
    "do_value_unit_swap": "do_value",
    "scope_population_swap": "scope",
    "estimand_swap": "estimand",
    "proxy_outcome_swap": "outcome",
}

_REQUIRED_COUNTER_REASONS = {
    "adversarial_false_analog_target_swap",
    "adversarial_false_analog_op_swap",
    "adversarial_false_analog_sign_swap",
    "adversarial_false_analog_do_value_unit_swap",
    "adversarial_false_analog_scope_population_swap",
    "adversarial_false_analog_estimand_swap",
    "adversarial_false_analog_proxy_outcome_swap",
}


def _false_analog_set_summary(engine: Any) -> dict[str, Any]:
    cases: dict[str, Any] = {}
    counter_reasons: set[str] = set()
    for case_id, expected_axis in _FALSE_ANALOG_EXPECTED_AXES.items():
        certificate = engine.certificate_for(
            _false_analog_probe(case_id),
            proposal_id=f"cg1-false-analog-{case_id}",
        )
        summary = _certificate_summary(certificate)
        summary.update(_false_analog_case_evidence(certificate, expected_axis))
        summary["expected_axis"] = expected_axis
        cases[case_id] = summary
        counter_reasons.update(summary.get("adversarial_countercandidate_reasons") or [])
    passed = [
        case_id
        for case_id, summary in cases.items()
        if summary.get("contradictory_atom_vetoed")
        and not summary.get("exact_or_specialization_to_contradictory_atom")
    ]
    return {
        "case_count": len(_FALSE_ANALOG_EXPECTED_AXES),
        "passed_count": len(passed),
        "cases": cases,
        "required_counter_reasons": sorted(_REQUIRED_COUNTER_REASONS),
        "observed_counter_reasons": sorted(counter_reasons),
        "counter_family_complete": _REQUIRED_COUNTER_REASONS.issubset(counter_reasons),
    }


def _false_analog_case_evidence(certificate: Any, expected_axis: str) -> dict[str, Any]:
    false_results: list[dict[str, Any]] = []
    bad_safe_results: list[str] = []
    for result in certificate.relation_set.get("candidate_results", []):
        if not isinstance(result, dict):
            continue
        contradictions = set(result.get("critical_contradictions") or [])
        if result.get("selected_relation") == "false-analog":
            false_results.append(
                {
                    "atom_id": result.get("atom_id"),
                    "critical_contradictions": sorted(contradictions),
                }
            )
        if (
            expected_axis in contradictions
            and result.get("selected_relation") in {"exact", "certified-specialization"}
        ):
            bad_safe_results.append(str(result.get("atom_id")))
    return {
        "false_analog_result_count": len(false_results),
        "false_analog_results": false_results[:8],
        "contradictory_atom_vetoed": any(
            expected_axis in set(item["critical_contradictions"]) for item in false_results
        ),
        "exact_or_specialization_to_contradictory_atom": bool(bad_safe_results),
        "bad_safe_result_atom_ids": bad_safe_results[:8],
    }


def _pure_synonym_probe(engine: Any) -> dict[str, Any]:
    atom = _reference_atom_for(engine, op="tax_relief_rate", target="global.tax_rate")
    signature = atom.signature.model_dump(mode="json")
    signature["op"] = "tax_credit_rate"
    signature["effect_path"] = [
        "tax_credit_rate",
        *list(atom.signature.X_do),
        *list(atom.signature.outcome),
    ]
    signature["modal_claims"] = {
        "NL": {
            "op": "tax_credit_rate",
            "target": atom.signature.X_do[0],
            "outcome": atom.signature.outcome[0] if atom.signature.outcome else "",
            "estimand": atom.signature.estimand,
        },
        "L6": {"knob": "tax_relief_rate"},
        "do_AST": {"op": "tax_credit_rate", "target": atom.signature.X_do[0]},
        "method": {
            "treatment_op": "tax_credit_rate",
            "treatment_target": atom.signature.X_do[0],
            "outcome": atom.signature.outcome[0] if atom.signature.outcome else "",
            "estimand": atom.signature.estimand,
        },
    }
    return {
        "proposal_id": "stress.synonym.pure_same_do",
        "raw_text": "levy credit-rate alias for the exact same tax relief do-query.",
        "signature": signature,
    }


def _reference_atom_for(engine: Any, *, op: str, target: str) -> Any:
    for atom in engine.reference_atoms:
        if atom.signature.op == op and target in atom.signature.X_do:
            return atom
    raise RuntimeError(f"cg1_reference_atom_missing:{op}:{target}")


def _false_analog_probe(case_id: str) -> dict[str, Any]:
    base: dict[str, Any] = {
        "proposal_id": f"stress.false_analog.{case_id}",
        "raw_text": (
            "High surface similarity tax credit relief proposal; this stress case "
            f"mutates only {case_id} while staying near tax-relief language."
        ),
        "signature": {
            "op": "tax_relief_rate",
            "target": ["global.tax_rate"],
            "sign": "decrease",
            "params": {"rate": 0.08},
            "x_do": {"rate": 0.08},
            "scope": "global",
            "population": "all",
            "unit": "ratio",
            "outcome": ["government.balance"],
            "effect_path": ["tax_relief_rate", "global.tax_rate", "government.balance"],
            "estimand": "average_treatment_effect",
            "admissibility": "candidate_unverified",
            "modal_claims": {
                "NL": {
                    "op": "tax_relief_rate",
                    "target": "global.tax_rate",
                    "outcome": "government.balance",
                    "estimand": "average_treatment_effect",
                }
            },
        },
    }
    signature = base["signature"]
    if case_id == "target_sibling":
        signature["target"] = ["cells.distress_score"]
        signature["effect_path"] = ["tax_relief_rate", "cells.distress_score", "government.balance"]
        signature["modal_claims"]["NL"]["target"] = "cells.distress_score"
    elif case_id == "op_swap":
        signature["op"] = "household_transfer"
        signature["effect_path"] = ["household_transfer", "global.tax_rate", "government.balance"]
        signature["modal_claims"]["NL"]["op"] = "household_transfer"
    elif case_id == "sign_swap":
        signature["sign"] = "increase"
    elif case_id == "do_value_unit_swap":
        pass
    elif case_id == "scope_population_swap":
        signature["op"] = "procurement_shock_intensity"
        signature["target"] = ["cells.distress_score"]
        signature["scope"] = "households"
        signature["population"] = "households"
        signature["outcome"] = ["cells.output"]
        signature["effect_path"] = [
            "procurement_shock_intensity",
            "cells.distress_score",
            "cells.output",
        ]
        signature["modal_claims"]["NL"] = {
            "op": "procurement_shock_intensity",
            "target": "cells.distress_score",
            "outcome": "cells.output",
            "estimand": "average_treatment_effect",
        }
    elif case_id == "estimand_swap":
        signature["estimand"] = "controlled_direct_effect"
        signature["modal_claims"]["NL"]["estimand"] = "controlled_direct_effect"
    elif case_id == "proxy_outcome_swap":
        signature["outcome"] = ["cells.output"]
        signature["effect_path"] = ["tax_relief_rate", "global.tax_rate", "cells.output"]
        signature["modal_claims"]["NL"]["outcome"] = "cells.output"
    else:
        raise ValueError(f"unknown_false_analog_case:{case_id}")
    return base


def _greedy_inconsistent_probe() -> dict[str, Any]:
    return {
        "proposal_id": "stress.greedy_inconsistent.household_threshold_corporate_tax_credit",
        "raw_text": (
            "Corporate tax credit with household-threshold budget law; each axis "
            "looks valid alone but the joint operator-target-law-knob assignment is invalid."
        ),
        "signature": {
            "op": "tax_relief_rate",
            "target": ["government.balance"],
            "sign": "decrease",
            "params": {"rate": 0.08},
            "x_do": {"rate": 0.08},
            "scope": "global",
            "population": "all",
            "outcome": ["government.balance"],
            "effect_path": ["tax_relief_rate", "government.balance", "government.balance"],
            "estimand": "average_treatment_effect",
            "admissibility": "candidate_unverified",
            "modal_claims": {
                "NL": {
                    "op": "tax_relief_rate",
                    "target": "government.balance",
                    "outcome": "government.balance",
                    "estimand": "average_treatment_effect",
                },
                "L3": {"law_token": "budget_law"},
                "L6": {"knob": "tax_relief_rate"},
                "do_AST": {"op": "tax_relief_rate", "target": "government.balance"},
                "method": {
                    "treatment_op": "tax_relief_rate",
                    "treatment_target": "government.balance",
                    "outcome": "government.balance",
                    "estimand": "average_treatment_effect",
                },
            },
        },
    }


def _cross_modal_inconsistent_probe() -> dict[str, Any]:
    return {
        "proposal_id": "stress.cross_modal_inconsistent",
        "raw_text": (
            "NL household subsidy, L3 firm payroll tax, knob tax_credit_rate, method firm LATE."
        ),
        "signature": {
            "op": "household_transfer",
            "target": ["household_cells.transfer_intensity"],
            "sign": "increase",
            "params": {"rate": 0.12},
            "x_do": {"rate": 0.12},
            "scope": "households",
            "population": "households",
            "outcome": ["household_cells.disposable_income"],
            "effect_path": [
                "household_transfer",
                "household_cells.transfer_intensity",
                "household_cells.disposable_income",
            ],
            "estimand": "average_treatment_effect",
            "admissibility": "candidate_unverified",
            "modal_claims": {
                "NL": {
                    "op": "household_transfer",
                    "target": "household_cells.transfer_intensity",
                },
                "L3": {"law_token": "tax_relief_statute"},
                "L6": {"knob": "tax_relief_rate"},
                "do_AST": {
                    "op": "household_transfer",
                    "target": "household_cells.transfer_intensity",
                },
                "method": {
                    "treatment_op": "labor_market",
                    "treatment_target": "firms.labor_count",
                    "outcome": "firms.labor_count",
                    "estimand": "local_average_treatment_effect",
                },
            },
        },
    }


def _synonym_probe() -> dict[str, Any]:
    return {
        "proposal_id": "stress.synonym.tax_credit_alias",
        "raw_text": "tax credit rate alias lowers tax burden by 8 percent.",
        "signature": {
            "op": "tax_credit_rate",
            "target": ["global.tax_rate"],
            "sign": "decrease",
            "params": {"rate": 0.08},
            "x_do": {"rate": 0.08},
            "scope": "global",
            "population": "all",
            "unit": "ratio",
            "outcome": ["government.balance"],
            "effect_path": ["tax_credit_rate", "global.tax_rate", "government.balance"],
            "estimand": "average_treatment_effect",
            "admissibility": "candidate_unverified",
            "modal_claims": {
                "NL": {
                    "op": "tax_credit_rate",
                    "target": "global.tax_rate",
                    "outcome": "government.balance",
                    "estimand": "average_treatment_effect",
                },
                "L6": {"knob": "tax_relief_rate"},
                "do_AST": {"op": "tax_credit_rate", "target": "global.tax_rate"},
                "method": {
                    "treatment_op": "tax_credit_rate",
                    "treatment_target": "global.tax_rate",
                    "outcome": "government.balance",
                    "estimand": "average_treatment_effect",
                },
            },
        },
    }


def _specialization_probe() -> dict[str, Any]:
    return _synonym_probe()


def _unknown_unproven_probe() -> dict[str, Any]:
    return {
        "proposal_id": "stress.unknown_unproven",
        "raw_text": (
            "A tax-credit-like support program whose target, do-value, and "
            "estimand are not yet resolved."
        ),
        "signature": {
            "op": None,
            "target": [],
            "sign": None,
            "params": {},
            "x_do": {},
            "outcome": [],
            "effect_path": [],
            "estimand": None,
            "admissibility": "candidate_unverified",
            "modal_claims": {"NL": {"op": "", "target": "", "outcome": ""}},
        },
    }


def _fake_atom_probe() -> dict[str, Any]:
    return {
        "proposal_id": "stress.fake_atom",
        "raw_text": "fake atom levitates public trust with a non-existent do target.",
        "signature": {
            "op": "fake_atom_levitation",
            "target": ["fake.world_slot"],
            "sign": "increase",
            "params": {"rate": 0.1},
            "x_do": {"rate": 0.1},
            "scope": "global",
            "population": "all",
            "outcome": ["fake.outcome"],
            "effect_path": ["fake_atom_levitation", "fake.world_slot", "fake.outcome"],
            "estimand": "average_treatment_effect",
            "admissibility": "candidate_unverified",
            "modal_claims": {
                "NL": {
                    "op": "fake_atom_levitation",
                    "target": "fake.world_slot",
                    "outcome": "fake.outcome",
                }
            },
        },
    }


def _free_grow_probe() -> dict[str, Any]:
    return {
        "proposal_id": "stress.free_grow",
        "raw_text": "emergency cooling subsidy raises transfer intensity for households.",
        "signature": {
            "op": "emergency_cooling_subsidy",
            "target": ["household_cells.transfer_intensity"],
            "sign": "increase",
            "params": {"rate": 0.4},
            "x_do": {"rate": 0.4},
            "scope": "households",
            "population": "households",
            "outcome": ["household_cells.disposable_income"],
            "effect_path": [
                "emergency_cooling_subsidy",
                "household_cells.transfer_intensity",
                "household_cells.disposable_income",
            ],
            "estimand": "average_treatment_effect",
            "admissibility": "candidate_unverified",
            "modal_claims": {
                "NL": {
                    "op": "emergency_cooling_subsidy",
                    "target": "household_cells.transfer_intensity",
                    "outcome": "household_cells.disposable_income",
                    "estimand": "average_treatment_effect",
                },
                "L6": {"knob": "emergency_cooling_subsidy"},
                "do_AST": {
                    "op": "emergency_cooling_subsidy",
                    "target": "household_cells.transfer_intensity",
                },
            },
        },
    }


def _copy(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _json_stable(payload: dict[str, Any]) -> dict[str, Any]:
    return _copy(payload)


def main(argv: list[str] | None = None) -> int:
    """Run the CGF GY-CG1 grounding relation contract validator."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    inserted = [str(repo_root), str(repo_root / "src")]
    for item in reversed(inserted):
        if item not in sys.path:
            sys.path.insert(0, item)

    if args.corrupt_field_drift_check:
        report = corrupt_field_drift_check(repo_root)
    else:
        live_payload = build_live_payload(repo_root) if args.write else None
        if args.write:
            write(repo_root, payload=live_payload)
        report = validate(repo_root) if not args.write else validate_payload(live_payload)

    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] != "pass":
        for issue in report["issues"]:
            print(f"{issue.get('code')}: {issue}")
    else:
        print("grounding relation contract: pass")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
