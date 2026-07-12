from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.selection.registry import get_registry, registry_scope
from polisyos.ir.kernel import DEFAULT_MECHANISM_REGISTRY
from polisyos.lex.knowledge.store import LegalKnowledgeStore
from polisyos.runtime.quality.intervention_substrate import (
    InterventionSubstrateError,
    intervention_substrate_behavior_report,
    load_l6_intervention_substrate,
    replace_intervention_substrate_bundle,
    resolve_intervention_lever,
    resolve_law_bound_lever,
    route_observation_family_method,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
L3_THRESHOLD_ID = "a5429abb6621acb11ed10b20"
FREE_GROW_L3_THRESHOLD_ID = "00000109f781085bd1736cf1"
FREE_GROW_L3_AS_OF = "2026-04-10"
L3_DB = (
    REPO_ROOT
    / "production_data/lex/lex-amendment-only-optimized-20260501-v3"
    / "finalize/lex_knowledge_graph.duckdb"
)
BUDGET_LAW = "budget_law"
DANGLING_LAW = "dangling_law"
FUTURE_RELIEF_LAW = "future_relief_law"
UNKNOWN_LAW_MODALITY = "unknown_legal_modality"
L6_MECHANISM_IDS = {
    "budget_allocation_multiplier",
    "procurement_shock_intensity",
    "tax_relief_rate",
}
FREE_GROW_KNOB = "future_child_benefit_intensity"
FREE_GROW_MECHANISM = "future_child_benefit_transfer"
FREE_GROW_SLOT = "household_cells.transfer_intensity"


def _lex_store() -> LegalKnowledgeStore:
    return LegalKnowledgeStore(L3_DB, L3_DB.parent)


def test_l6_world_slot_authority_is_not_hardcoded_in_default_mechanisms() -> None:
    assert L6_MECHANISM_IDS.isdisjoint(DEFAULT_MECHANISM_REGISTRY.mechanisms)


def test_real_knob_dictionary_resolves_domain_and_fails_closed_for_unknown_or_out_of_range() -> None:
    bundle = load_l6_intervention_substrate(REPO_ROOT)

    resolved = resolve_intervention_lever(
        bundle,
        operator_kind="budget_allocation_multiplier",
        parameter_value=1.25,
    )

    assert resolved.operator_kind == "budget_allocation_multiplier"
    assert resolved.parameter_value == 1.25
    assert resolved.domain.model_dump(mode="json") == {
        "kind": "range",
        "max_value": 2.0,
        "min_value": 0.0,
        "unit": None,
        "value_type": "float",
    }
    assert resolved.target_world_slots == ("government.balance",)
    assert resolved.content_hash.startswith("sha256:")

    with pytest.raises(InterventionSubstrateError) as out_of_domain:
        resolve_intervention_lever(
            bundle,
            operator_kind="budget_allocation_multiplier",
            parameter_value=2.25,
        )
    assert out_of_domain.value.code == "knob_parameter_out_of_domain"

    with pytest.raises(InterventionSubstrateError) as unknown:
        resolve_intervention_lever(
            bundle,
            operator_kind="unknown_budget_knob",
            parameter_value=1.0,
        )
    assert unknown.value.code == "knob_operator_unresolved"


def test_all_real_knobs_bind_world_slots_through_owner_without_injected_authority() -> None:
    bundle = load_l6_intervention_substrate(REPO_ROOT)
    resolved = {}
    for knob_id, raw in bundle.knob_dictionary.items():
        value = (float(raw["min"]) + float(raw["max"])) / 2.0
        resolved[knob_id] = resolve_intervention_lever(
            bundle,
            operator_kind=knob_id,
            parameter_value=value,
        )

    assert set(resolved) == set(bundle.knob_dictionary)
    assert all(item.target_world_slots for item in resolved.values())
    assert all(item.owner_resolution["atom_id"].startswith("atom_") for item in resolved.values())
    assert all(item.owner_resolution["world_model_record_id"] for item in resolved.values())


def test_law_bound_lever_traces_real_l3_threshold_and_blocks_violating_value() -> None:
    bundle = load_l6_intervention_substrate(REPO_ROOT)
    lex = _lex_store()

    admitted = resolve_law_bound_lever(
        bundle,
        law_token=BUDGET_LAW,
        knob_id="budget_allocation_multiplier",
        parameter_value=0.24,
        legal_store=lex,
    )
    blocked = resolve_law_bound_lever(
        bundle,
        law_token=BUDGET_LAW,
        knob_id="budget_allocation_multiplier",
        parameter_value=0.26,
        legal_store=lex,
    )

    assert admitted.status == "admissible"
    assert admitted.legal_threshold_evaluation["status"] == "admitted"
    assert admitted.provision_ref.startswith("duckdb://")
    assert admitted.knob.operator_kind == "budget_allocation_multiplier"
    assert admitted.temporal_competence["status"] in {"in_force", "partial"}
    assert blocked.status == "blocked"
    assert blocked.legal_threshold_evaluation["reason"] == "threshold_violated"


def test_all_real_law_map_entries_trace_to_l3_provision_without_injected_authority() -> None:
    bundle = load_l6_intervention_substrate(REPO_ROOT)
    assert all(
        not (
            isinstance(raw, dict)
            and (raw.get("provision_ref") or raw.get("threshold_id"))
        )
        for raw in bundle.lex_intervention_map.values()
    )
    lex = _lex_store()
    traced = {}
    for law_token, raw_knobs in bundle.lex_intervention_map.items():
        if isinstance(raw_knobs, dict):
            knob_ids = raw_knobs.get("knob_ids") or raw_knobs.get("knobs") or raw_knobs.get("knob_id")
        else:
            knob_ids = raw_knobs
        knob_id = knob_ids[0]
        raw_knob = bundle.knob_dictionary[knob_id]
        value = (float(raw_knob["min"]) + float(raw_knob["max"])) / 2.0
        traced[law_token] = resolve_law_bound_lever(
            bundle,
            law_token=law_token,
            knob_id=knob_id,
            parameter_value=value,
            legal_store=lex,
        )

    assert set(traced) == set(bundle.lex_intervention_map)
    assert all(item.provision_ref.startswith("duckdb://") for item in traced.values())
    assert all(item.threshold_id for item in traced.values())


def test_law_bound_lever_fails_closed_for_dangling_map_entries() -> None:
    base_bundle = load_l6_intervention_substrate(REPO_ROOT)
    bundle = replace_intervention_substrate_bundle(
        base_bundle,
        update={
            "lex_intervention_map": {
                **base_bundle.lex_intervention_map,
                DANGLING_LAW: ("not_a_real_knob",),
            }
        }
    )

    with pytest.raises(InterventionSubstrateError) as dangling_knob:
        resolve_law_bound_lever(
            bundle,
            law_token=DANGLING_LAW,
            knob_id="not_a_real_knob",
            parameter_value=0.1,
            legal_store=_lex_store(),
        )
    assert dangling_knob.value.code == "lex_map_knob_unresolved"

    with pytest.raises(InterventionSubstrateError) as missing_law_authority:
        resolve_law_bound_lever(
            bundle,
            law_token=UNKNOWN_LAW_MODALITY,
            knob_id="budget_allocation_multiplier",
            parameter_value=0.1,
            legal_store=_lex_store(),
        )
    assert missing_law_authority.value.code == "law_modality_unresolved"


def test_family_method_routing_uses_real_manifest_registry_and_python314_blockers() -> None:
    bundle = load_l6_intervention_substrate(REPO_ROOT)
    dead_contract = "foundry.dead.unregistered_contract.v1"
    unavailable_contract = "foundry.bayesian.bart_regression.v1"
    dead_bundle = replace_intervention_substrate_bundle(
        bundle,
        update={
            "observation_manifest": {
                **bundle.observation_manifest,
                "routes": [
                    *bundle.observation_manifest["routes"],
                    {
                        "family": "dead_route_family",
                        "identification_mode": "point_identified",
                        "target_contract": {
                            "contract_id": dead_contract,
                            "contract_fqn": (
                                "polisyos.foundry.methods.catalog.dead.Unregistered"
                            ),
                        },
                    },
                    {
                        "family": "python314_unavailable_route_family",
                        "identification_mode": "point_identified",
                        "target_contract": {
                            "contract_id": unavailable_contract,
                            "contract_fqn": (
                                "polisyos.foundry.methods.catalog.bayesian.protocols."
                                "BartRegressionData"
                            ),
                        },
                    },
                ],
                "artifacts": [
                    *bundle.observation_manifest["artifacts"],
                    {
                        "artifact_ref": "in_memory://dead_route_contract",
                        "status": "compiled",
                        "target_contract": {"contract_id": dead_contract},
                    },
                    {
                        "artifact_ref": "in_memory://python314_unavailable_route_contract",
                        "status": "compiled",
                        "target_contract": {"contract_id": unavailable_contract},
                    },
                ],
            }
        }
    )
    with registry_scope():
        registry = get_registry()
        ensure_all_methods_registered(registry)

        routed = route_observation_family_method(
            bundle,
            family="budget_flows",
            registry=registry,
        )
        blocked = route_observation_family_method(
            bundle,
            family="firm_fundamentals",
            registry=registry,
        )
        unresolved = route_observation_family_method(
            dead_bundle,
            family="dead_route_family",
            registry=registry,
        )
        unavailable = route_observation_family_method(
            dead_bundle,
            family="python314_unavailable_route_family",
            registry=registry,
        )

    assert routed.status == "routed"
    assert routed.target_contract_id == "foundry.causal.panel_observational_data.v1"
    assert routed.selected_method_fqn is not None
    assert routed.selected_method_fqn.startswith("causal.inference.did.")
    assert routed.registry_method_count >= 1
    assert blocked.target_contract_id == "foundry.ml.survival_data.v1"
    assert blocked.reason_code != "method_route_unresolved"
    assert any("survival" in fqn for fqn in blocked.candidate_method_fqns)
    if blocked.status == "routed":
        assert blocked.selected_method_fqn is not None
        assert "survival" in blocked.selected_method_fqn
    else:
        assert blocked.reason_code == "method_unavailable_python314"
        assert blocked.selected_method_fqn is None
    assert unresolved.status == "blocked"
    assert unresolved.reason_code == "method_route_unresolved"
    assert unresolved.selected_method_fqn is None
    assert unavailable.status == "blocked"
    assert unavailable.reason_code == "method_unavailable_python314"
    assert any("bart" in fqn for fqn in unavailable.candidate_method_fqns)
    assert any("bart" in fqn for fqn in unavailable.unavailable_method_fqns)

    with pytest.raises(InterventionSubstrateError) as unknown:
        route_observation_family_method(bundle, family="unknown_family")
    assert unknown.value.code == "family_route_unresolved"


def test_intervention_substrate_free_grows_knobs_laws_and_families_without_code_branches() -> None:
    bundle = load_l6_intervention_substrate(REPO_ROOT)
    threshold = _lex_store().resolve_rule_threshold(
        threshold_id=FREE_GROW_L3_THRESHOLD_ID,
        as_of=FREE_GROW_L3_AS_OF,
    )
    assert threshold is not None
    grown = replace_intervention_substrate_bundle(
        bundle,
        update={
            "knob_dictionary": {
                **bundle.knob_dictionary,
                FREE_GROW_KNOB: {
                    "default": 0.0,
                    "type": "float",
                    "min": 0.0,
                    "max": 0.4,
                    "mechanism_id": FREE_GROW_MECHANISM,
                    "param_path": "params.intensity",
                },
            },
            "world_mechanism_manifest": {
                **getattr(bundle, "world_mechanism_manifest", {}),
                "mechanisms": {
                    **getattr(bundle, "world_mechanism_manifest", {}).get(
                        "mechanisms",
                        {},
                    ),
                    FREE_GROW_MECHANISM: {
                        "mechanism_id": FREE_GROW_MECHANISM,
                        "params": {
                            "intensity": {
                                "param_id": "intensity",
                                "required": True,
                                "value_type": "decimal",
                                "min_value": 0,
                                "max_value": 0.4,
                                "unit_id": "ratio",
                            }
                        },
                        "reads_slots": [FREE_GROW_SLOT],
                        "writes_slots": [FREE_GROW_SLOT],
                        "default_merge": {FREE_GROW_SLOT: "override"},
                        "provenance_refs": [
                            "tests:free-grow-owner-mechanism-writes-real-wmr-slot"
                        ],
                    },
                },
            },
            "lex_intervention_map": {
                **bundle.lex_intervention_map,
                FUTURE_RELIEF_LAW: {
                    "knob_ids": [FREE_GROW_KNOB],
                },
            },
            "lex_authority_manifest": {
                **getattr(bundle, "lex_authority_manifest", {}),
                "intervention_map_entries": [
                    *getattr(bundle, "lex_authority_manifest", {}).get(
                        "intervention_map_entries",
                        (),
                    ),
                    {
                        "law_token": FUTURE_RELIEF_LAW,
                        "provision_ref": f"lex_rule_thresholds:{threshold.threshold_id}",
                        "intervention_kind": FREE_GROW_MECHANISM,
                        "knob_ids": [FREE_GROW_KNOB],
                        "measurement_expectations": {
                            "applies_to": threshold.applies_to,
                            "as_of": FREE_GROW_L3_AS_OF,
                            "candidate_unit": "ratio",
                        },
                        "metadata": {
                            "law_token": FUTURE_RELIEF_LAW,
                            "provenance": "test owner artifact, not lex map authority",
                        },
                    },
                ],
            },
            "observation_manifest": {
                **bundle.observation_manifest,
                "routes": [
                    *bundle.observation_manifest["routes"],
                    {
                        "family": "future_budget_flows",
                        "identification_mode": "point_identified",
                        "target_contract": {
                            "contract_id": "foundry.causal.panel_observational_data.v1",
                            "contract_fqn": (
                                "polisyos.foundry.methods.catalog.causal.protocols."
                                "PanelObservationalData"
                            ),
                        },
                    },
                ],
            },
        }
    )

    lever = resolve_intervention_lever(
        grown,
        operator_kind=FREE_GROW_KNOB,
        parameter_value=0.2,
    )
    law = resolve_law_bound_lever(
        grown,
        law_token=FUTURE_RELIEF_LAW,
        knob_id=FREE_GROW_KNOB,
        parameter_value=0.2,
        legal_store=_lex_store(),
    )
    with registry_scope():
        registry = get_registry()
        ensure_all_methods_registered(registry)
        route = route_observation_family_method(
            grown,
            family="future_budget_flows",
            registry=registry,
        )

    assert lever.target_world_slots == (FREE_GROW_SLOT,)
    assert law.status == "admissible"
    assert route.status == "routed"

    malformed = replace_intervention_substrate_bundle(
        grown,
        update={
            "knob_dictionary": {
                **grown.knob_dictionary,
                "future_unresolved_intensity": {
                    "default": 0.0,
                    "type": "float",
                    "min": 0.0,
                    "max": 0.4,
                    "mechanism_id": "future_missing_owner_mechanism",
                    "param_path": "params.intensity",
                },
            }
        }
    )
    with pytest.raises(InterventionSubstrateError) as missing_owner:
        resolve_intervention_lever(
            malformed,
            operator_kind="future_unresolved_intensity",
            parameter_value=0.2,
        )
    assert missing_owner.value.code == "knob_owner_mechanism_unresolved"


def test_intervention_substrate_behavior_report_exercises_real_space_and_mutations() -> None:
    report = intervention_substrate_behavior_report(REPO_ROOT)

    assert report["status"] == "pass"
    assert report["coverage"]["world_slot"]["bound"] == report["coverage"]["world_slot"]["total"]
    assert report["coverage"]["law_trace"]["traced"] == report["coverage"]["law_trace"]["total"]
    assert report["coverage"]["method_route"]["available"] == report["coverage"]["method_route"]["total"]
    assert report["coverage"]["method_route"]["unresolved"] == 0
    assert {
        "all_real_knobs_resolve_world_slots",
        "knob_out_of_domain_and_unknown_operator_fail_closed",
        "all_real_laws_trace_l3_thresholds",
        "dangling_law_map_fails_closed",
        "family_method_route_real_available_and_truthful_blockers",
        "family_method_route_python314_unavailable_truthful_blocker",
        "unknown_family_fails_closed",
        "free_grow_knob_law_family_routes",
        "s0_registers_l6_agent_sim_bundle",
    } <= {case["case_id"] for case in report["cases"]}
    mutation_statuses = {
        mutation["mutation_id"]: mutation["status"]
        for mutation in report["remove_property_mutations"]
    }
    mutation_signals = {
        mutation["mutation_id"]: mutation["actual_signal"]
        for mutation in report["remove_property_mutations"]
    }
    assert mutation_statuses == {
        "unknown_op_admits": "red",
        "out_of_domain_clamps": "red",
        "dangling_map_binds_anyway": "red",
        "dead_route_succeeds": "red",
        "owner_slot_reference_binds_without_owner_validation": "red",
        "law_provision_reference_binds_without_l3_validation": "red",
        "world_slot_owner_derivation_disabled_drops_coverage": "red",
        "world_slot_hardcoded_bypass_rejected": "red",
        "unknown_family_defaults": "red",
    }
    assert (
        mutation_signals["owner_slot_reference_binds_without_owner_validation"]
        == "world_slot_unresolved"
    )
    assert (
        mutation_signals["law_provision_reference_binds_without_l3_validation"]
        == "law_threshold_unresolved"
    )
