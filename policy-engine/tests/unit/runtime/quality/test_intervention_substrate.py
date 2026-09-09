from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from polisyos.foundry.extensions import component_for_method
from polisyos.foundry.methods import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.selection.registry import get_registry, registry_scope
from polisyos.ir.kernel import DEFAULT_MECHANISM_REGISTRY
from polisyos.lex.knowledge.store import LegalKnowledgeStore
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.generation_cycle import _build_boundary_world_model_record
from polisyos.runtime.quality.intervention_substrate import (
    InterventionSubstrateError,
    intervention_substrate_behavior_report,
    load_l6_intervention_substrate,
    replace_intervention_substrate_bundle,
    resolve_intervention_lever,
    resolve_law_bound_lever,
    route_observation_family_method,
)
from polisyos.runtime.quality.substrate_registry import SubstrateRegistry
from tools.quality.validation import check_layer3_gy_second_domain_pack as second_domain_pack

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


def test_phase5_n8_default_rejects_every_corrupted_real_route() -> None:
    """The real N8 bridge must consume every real route's target validity."""
    from polisyos.runtime.quality.generation_cycle import _select_value_method

    bundle = load_l6_intervention_substrate(REPO_ROOT)
    identities = {row["family"] for row in bundle.observation_manifest["routes"]}
    for family in sorted(identities):
        broken = copy.deepcopy(bundle.observation_manifest)
        for row in broken["routes"]:
            if row["family"] == family:
                row["target_contract"] = {
                    "contract_id": "phase5.nonexistent.contract",
                    "contract_fqn": "phase5.NonexistentContract",
                }
        result = _select_value_method(
            candidate={"candidate_id": family, "atom": {"target_world_slots": [family]}},
            problem={"outcome_of_interest": {"target_variable": family}},
            inputs={"observation_to_contract_manifest": broken, "observation_family": family},
        )
        assert result["status"] == "blocked", (family, result)


def test_phase5_n8_real_routes_are_constraints_and_explicit_requests_cannot_escape() -> None:
    """All source routes constrain actual selection, including explicit requests."""
    from polisyos.runtime.quality.generation_cycle import _select_value_method

    bundle = load_l6_intervention_substrate(REPO_ROOT)
    for raw in bundle.observation_manifest["routes"]:
        family = raw["family"]
        owner = route_observation_family_method(bundle, family=family)
        inputs = {
            "observation_to_contract_manifest": bundle.observation_manifest,
            "observation_family": family,
        }
        candidate = {"candidate_id": family, "atom": {"target_world_slots": [family]}}
        problem = {"outcome_of_interest": {"target_variable": family}}
        result = _select_value_method(candidate=candidate, problem=problem, inputs=inputs)
        if result["status"] == "selected":
            assert result["selected_method_fqn"] in owner.candidate_method_fqns
        else:
            assert result["blockers"] == ("value_method_route_no_native_value_output",)
        escaped = _select_value_method(
            candidate=candidate,
            problem=problem,
            inputs={**inputs, "method_fqn": "bayesian.gp.gp_regression@1.0.0"},
        )
        assert escaped["status"] == "blocked"
        assert "value_method_request_outside_manifest_route" in escaped["blockers"]


def test_phase5_supplied_manifest_cannot_disappear_from_selection_or_context() -> None:
    """Missing source structure cannot replay the context of absent source input."""
    from polisyos.runtime.quality.generation_cycle import (
        _select_value_method,
        _value_method_route_constraint,
    )

    bundle = load_l6_intervention_substrate(REPO_ROOT)
    missing_routes = copy.deepcopy(bundle.observation_manifest)
    del missing_routes["routes"]
    assert _select_value_method(candidate={}, problem={}, inputs={})["status"] == "selected"
    assert _select_value_method(candidate={}, problem={}, inputs={
        "observation_to_contract_manifest": bundle.observation_manifest,
        "observation_family": "budget_flows",
    })["status"] == "selected"
    for malformed in (missing_routes, None, {}, [], "", 0, {"contracts": [{"data_modality": "panel"}]}):
        inputs = {"observation_to_contract_manifest": malformed,
                  "observation_family": "budget_flows"}
        assert _select_value_method(candidate={}, problem={}, inputs=inputs)["status"] == "blocked", malformed
        # The receipt verification path calls this exact source intake again.
        with pytest.raises(ValueError):
            _value_method_route_constraint(candidate={}, problem={}, inputs=inputs)


def test_phase5_configured_value_port_family_reaches_owner_selection_and_replay(monkeypatch) -> None:
    """Known route scope travels through the real port's configuration bridge."""
    from polisyos.foundry.methods.selection import (
        MethodSelectionReceipt,
        method_selection_context_hash,
    )
    from polisyos.runtime.quality import generation_cycle as runtime
    from tests.unit.runtime.http.test_control_service_di import (
        _explicit_simulation_execution_context,
    )
    from tests.unit.runtime.quality.test_cycle_substrate import _cycle_context
    from tests.unit.runtime.quality.test_generation_cycle import _problem

    problem = _problem()
    context = _explicit_simulation_execution_context(problem)
    source = load_l6_intervention_substrate(REPO_ROOT).observation_manifest

    def port(family: str | None, method: str | None = None):
        return runtime.FoundryValuePort(
            evaluation_context=context, observation_to_contract_manifest=source,
            observation_family=family, requested_method_fqn=method,
        )

    configured = port("budget_flows")
    source_missing = runtime.FoundryValuePort(
        evaluation_context=context, observation_family="budget_flows",
    )
    assert runtime._select_value_method(candidate={}, problem=problem,
        inputs=source_missing._selection_inputs())["status"] == "blocked"
    inputs = configured._selection_inputs()
    positive = runtime._select_value_method(candidate={}, problem=problem, inputs=inputs)
    assert positive["status"] == "selected", positive
    for refused in (port(None), port("unknown_observation_family"),
                    port("budget_flows", "bayesian.gp.gp_regression@1.0.0")):
        result = runtime._select_value_method(candidate={}, problem=problem,
                                               inputs=refused._selection_inputs())
        assert result["status"] == "blocked", result
    receipt = MethodSelectionReceipt.model_validate(positive["selection_receipt"])
    constraint = runtime._value_method_route_constraint(candidate={}, problem=problem, inputs=inputs)
    receipt.verify_selection_context(method_selection_context_hash(
        candidate={}, problem=problem, route_constraint=constraint,
    ))
    changed = runtime._value_method_route_constraint(
        candidate={}, problem=problem, inputs=port("firm_fundamentals")._selection_inputs(),
    )
    with pytest.raises(ValueError):
        receipt.verify_selection_context(method_selection_context_hash(
            candidate={}, problem=problem, route_constraint=changed,
        ))
    controller = runtime.GenerationCycleController(
        repo_root=REPO_ROOT, observation_to_contract_manifest=source,
        observation_family="budget_flows",
    )
    assert controller._value_port.observation_family == "budget_flows"
    # A typed candidate context binds the complete real manifest, with no source
    # override. Its other fixture fields are not a canonical population claim.
    bound = _cycle_context(intervention_substrate=load_l6_intervention_substrate(REPO_ROOT))
    bound_controller = runtime.GenerationCycleController(
        repo_root=REPO_ROOT, cycle_substrate_context=bound, observation_family="budget_flows",
    )
    lazy = bound_controller._value_port
    bound_port = runtime.FoundryValuePort(
        evaluation_context=context, **lazy._selection_configuration(),
    )
    default_inputs = bound_port._selection_inputs()
    assert default_inputs["observation_to_contract_manifest"] == source
    assert runtime._select_value_method(candidate={}, problem=problem,
                                       inputs=default_inputs)["status"] == "selected"
    mismatched = copy.deepcopy(source)
    mismatched["annotation"] = "different source"
    with pytest.raises(ValueError, match="value_method_manifest_context_mismatch"):
        runtime.FoundryValuePort(evaluation_context=context, cycle_substrate_context=bound,
            observation_to_contract_manifest=mismatched, observation_family="budget_flows",
        )._selection_inputs()
    tampered = bound.model_copy(deep=True)
    tampered.intervention_substrate.observation_manifest["routes"] = []
    with pytest.raises(ValueError, match="cycle_substrate_intervention_bundle_hash_mismatch"):
        runtime.FoundryValuePort(evaluation_context=context, cycle_substrate_context=tampered,
                               observation_family="budget_flows")._selection_inputs()
    original = runtime._value_method_selection_inputs

    def remove_family_forwarding(**kwargs):
        result = original(**kwargs)
        result.pop("observation_family", None)
        return result

    monkeypatch.setattr(runtime, "_value_method_selection_inputs", remove_family_forwarding)
    # Constructor/configuration marker remains; removing only the forwarding
    # breaks the unchanged positive control through the actual selection owner.
    assert configured._observation_family == "budget_flows"
    removed = runtime._select_value_method(candidate={}, problem=problem,
                                           inputs=configured._selection_inputs())
    with pytest.raises(AssertionError):
        assert removed["status"] == "selected", removed
    def remove_bound_source_forwarding(**kwargs):
        result = original(**kwargs)
        result.pop("observation_to_contract_manifest", None)
        return result

    monkeypatch.setattr(runtime, "_value_method_selection_inputs", remove_bound_source_forwarding)
    source_removed = runtime._select_value_method(candidate={}, problem=problem,
                                                  inputs=bound_port._selection_inputs())
    with pytest.raises(AssertionError):
        assert source_removed.get("selected_method_fqn") == positive["selected_method_fqn"]


def test_phase5_real_unrelated_law_target_cannot_authorize_a_knob() -> None:
    """Real threshold truth cannot establish a different law/lever correspondence."""
    bundle = load_l6_intervention_substrate(REPO_ROOT)
    lex = _lex_store()
    bundle = _with_subject_spine(bundle, lex)
    positive = resolve_law_bound_lever(
        bundle, law_token=BUDGET_LAW, knob_id="budget_allocation_multiplier",
        parameter_value=0.24, legal_store=lex,
    )
    assert positive.recognition.status == "passed"
    assert positive.legal_threshold_evaluation["status"] == "admitted"
    assert positive.synthetic is True
    assert positive.current_authority_status == "blocked"
    manifest = copy.deepcopy(bundle.lex_authority_manifest)
    entries = {row["law_token"]: row for row in manifest["intervention_map_entries"]}
    budget, tax = entries["budget_law"], entries["tax_relief_statute"]
    budget["provision_ref"], tax["provision_ref"] = tax["provision_ref"], budget["provision_ref"]
    changed = replace_intervention_substrate_bundle(
        bundle,
        update={"lex_authority_manifest": manifest},
    )
    result = resolve_law_bound_lever(
        changed,
        law_token=tax["law_token"],
        knob_id="tax_relief_rate",
        parameter_value=0.24,
        legal_store=lex,
    )
    assert result.recognition.status == "rejected"
    assert result.recognition.reason_code == "legal_subject_mismatch"
    assert result.legal_threshold_evaluation is None
    assert result.numeric_evaluation_status == "not_run"
    assert result.status == "blocked"
    assert result.mapping_evidence_ref is not None
    assert result.mapping_predicate_provenance == "recomputed"


def test_missing_legal_subject_is_ambiguous_before_numeric_units(monkeypatch) -> None:
    """Deleting early subject admission wrongly evaluates an ungrounded unit."""
    bundle = load_l6_intervention_substrate(REPO_ROOT)
    manifest = copy.deepcopy(bundle.lex_authority_manifest)
    for row in manifest["intervention_map_entries"]:
        if row["law_token"] == BUDGET_LAW:
            row["measurement_expectations"]["candidate_unit"] = "corr.invalid.unit"
    bundle = replace_intervention_substrate_bundle(
        bundle, update={"lex_authority_manifest": manifest})
    lex = _lex_store()
    evaluations = []
    evaluate = lex.evaluate_rule_threshold

    def observed_evaluate(**kwargs):
        evaluations.append(kwargs)
        return evaluate(**kwargs)

    monkeypatch.setattr(lex, "evaluate_rule_threshold", observed_evaluate)
    result = resolve_law_bound_lever(
        bundle, law_token=BUDGET_LAW, knob_id="budget_allocation_multiplier",
        parameter_value=1.0, legal_store=lex,
    )
    assert evaluations == []
    assert result.recognition.status == "ambiguous"
    assert result.numeric_evaluation_status == "not_run"
    assert result.legal_threshold_evaluation is None
    assert result.knob_id == "budget_allocation_multiplier"
    assert result.current_authority_status == "blocked"


def test_subject_comparison_removal_turns_real_transposition_gate_red(monkeypatch) -> None:
    from polisyos.foundry.validation import legal_correspondence as owner

    monkeypatch.setattr(owner, "_same_subject", lambda lever, norm: True)
    with pytest.raises(AssertionError):
        test_phase5_real_unrelated_law_target_cannot_authorize_a_knob()


def test_subject_forwarding_removal_turns_real_positive_gate_red(monkeypatch) -> None:
    from polisyos.runtime.quality import intervention_substrate as owner

    original = owner.recognize_legal_correspondence
    monkeypatch.setattr(owner, "recognize_legal_correspondence",
                        lambda store, ref, request: original(store, None, request))
    with pytest.raises(AssertionError):
        test_phase5_real_unrelated_law_target_cannot_authorize_a_knob()


def test_phase5_route_growth_ambiguity_and_source_substitution() -> None:
    from polisyos.runtime.quality.generation_cycle import _select_value_method
    from polisyos.runtime.quality.intervention_substrate import (
        project_value_method_route_constraint,
        resolve_observation_manifest_routes,
    )

    bundle = load_l6_intervention_substrate(REPO_ROOT)
    original = project_value_method_route_constraint(bundle, family="budget_flows")
    manifest = copy.deepcopy(bundle.observation_manifest)
    novel = copy.deepcopy(
        next(row for row in manifest["routes"] if row["family"] == "budget_flows")
    )
    novel["family"] = "new_data_only_observation_family"
    manifest["routes"].append(novel)
    grown = replace_intervention_substrate_bundle(bundle, update={"observation_manifest": manifest})
    assert {route.family for route in resolve_observation_manifest_routes(grown)} == {
        row["family"] for row in manifest["routes"]
    }
    projected = project_value_method_route_constraint(grown, family=novel["family"])
    assert projected.allowed_method_fqns == original.allowed_method_fqns
    result = _select_value_method(
        candidate={},
        problem={},
        inputs={
            "observation_to_contract_manifest": manifest,
            "observation_family": novel["family"],
        },
    )
    assert result["status"] == "selected"
    assert result["selected_method_fqn"] in projected.allowed_method_fqns
    duplicate = copy.deepcopy(manifest)
    duplicate["routes"].append({**novel, "mode": "another_mode"})
    with pytest.raises(InterventionSubstrateError, match="family_route_ambiguous"):
        resolve_observation_manifest_routes(
            replace_intervention_substrate_bundle(
                bundle,
                update={"observation_manifest": duplicate},
            )
        )
    # Leave a valid, caller-authored projection declaration intact; break its source.
    novel["target_contract"] = {"contract_id": "phase5.nonexistent.contract"}
    substituted = _select_value_method(
        candidate={},
        problem={},
        inputs={
            "observation_to_contract_manifest": manifest,
            "observation_family": novel["family"],
            "route_constraint": projected.model_dump(mode="json"),
            "owner_validated": True,
        },
    )
    assert substituted["status"] == "blocked"


def test_phase5_historical_law_record_remains_readable_without_current_authority() -> None:
    import json

    from polisyos.runtime.quality.intervention_substrate import LawLeverResolution

    legacy = json.loads(
        (Path(__file__).parent / "fixtures/intervention_law_lift_v1.json").read_text()
    )
    historical = LawLeverResolution.model_validate(legacy)
    assert historical.status == "admissible"
    assert historical.current_authority_status == "blocked"
    assert historical.mapping_evidence_ref is None


def test_historical_v2_law_record_cannot_be_restamped_with_current_binding() -> None:
    import json

    from polisyos.runtime.quality.intervention_substrate import LawLeverResolution

    payload = json.loads((Path(__file__).parent / "fixtures/intervention_law_lift_v2.json")
                         .read_text())
    historical = LawLeverResolution.model_validate(payload)
    assert historical.content_hash == payload["content_hash"]
    assert historical.current_authority_status == "blocked"
    payload["knob_id"] = "budget_allocation_multiplier"
    with pytest.raises(ValueError, match="historical_epoch_cannot_carry_current_recognition"):
        LawLeverResolution.model_validate(payload)


def test_historical_v2_law_nested_serialization_preserves_original_bytes() -> None:
    import json

    from pydantic import BaseModel

    from polisyos.core import canon
    from polisyos.runtime.quality.intervention_substrate import LawLeverResolution

    class Container(BaseModel):
        law: LawLeverResolution

    raw = json.loads((Path(__file__).parent / "fixtures/intervention_law_lift_v2.json").read_text())
    nested = Container(law=LawLeverResolution.model_validate(raw))
    spec = canon.CanonSpec(forbid_floats=False, exclude_none=False)
    assert canon.to_canonical_bytes(nested.model_dump(mode="json"), spec) == canon.to_canonical_bytes(
        {"law": raw}, spec)


def test_phase5_route_context_binds_source_and_rejects_forged_method_constraint() -> None:
    from polisyos.foundry.methods.selection.advisor import select_value_method_for_problem
    from polisyos.runtime.quality.generation_cycle import _select_value_method
    from polisyos.runtime.quality.intervention_substrate import (
        project_value_method_route_constraint,
    )

    bundle = load_l6_intervention_substrate(REPO_ROOT)
    inputs = {"observation_to_contract_manifest": bundle.observation_manifest,
              "observation_family": "budget_flows"}
    first = _select_value_method(candidate={}, problem={}, inputs=inputs)
    assert first["status"] == "selected"
    changed = copy.deepcopy(bundle.observation_manifest)
    changed["projection_probe_annotation"] = "same method, different manifest content"
    second = _select_value_method(candidate={}, problem={}, inputs={
        **inputs, "observation_to_contract_manifest": changed,
    })
    assert second["status"] == "selected"
    assert first["selected_method_fqn"] == second["selected_method_fqn"]
    assert first["selection_receipt"]["selection_context_hash"] != (
        second["selection_receipt"]["selection_context_hash"])
    constraint = project_value_method_route_constraint(bundle, family="budget_flows")
    fake = constraint.model_copy(update={"allowed_method_fqns": ("bayesian.gp.gp_regression@1.0.0",)})
    result = select_value_method_for_problem(candidate={}, problem={}, route_constraint=fake)
    assert result["status"] == "blocked"
    assert result["blockers"] == ("value_method_route_contract_mismatch",)


@dataclass(frozen=True)
class _AmbientEntryPoint:
    name: str
    value: str
    component: object
    module: str = "ambient_route_plugin"
    attr: str = "plugin"
    dist: None = None

    def load(self) -> object:
        return self.component


@lru_cache(maxsize=1)
def _education_cycle_context() -> tuple[DesignProblem, object]:
    """Load the committed education evidence through the canonical WMR owner."""

    frozen = second_domain_pack._load_frozen_bundle(REPO_ROOT)
    pack = frozen["pack"]
    problem = DesignProblem.model_validate(
        frozen["smoke_problem"]["design_problem"]
    )
    registry = SubstrateRegistry.model_validate(
        pack["owner_query_results"]["s0_registry"]["registry_payload"]
    )
    selected_hashes = tuple(
        pack["components"]["substrate_registry"]["selected_entry_hashes"]
    )
    world = _build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=problem,
        outcome=problem.outcome_of_interest.target_variable,
        policy_slot_ids=(problem.outcome_of_interest.target_variable,),
        substrate_registry=registry,
        selected_registry_entry_hashes=selected_hashes,
    )
    return problem, second_domain_pack.project_second_domain_cycle_substrate_context(
        frozen,
        repo_root=REPO_ROOT,
        design_problem=problem,
        world_model_record=world,
        intervention_substrate=load_l6_intervention_substrate(REPO_ROOT),
    )


def test_pack_lever_resolution_returns_typed_candidate_unbound() -> None:
    """A pack candidate reaches the L6 owner but never enters its writable map."""

    _problem, context = _education_cycle_context()
    bundle = load_l6_intervention_substrate(REPO_ROOT)

    result = resolve_intervention_lever(
        bundle,
        operator_kind="education.teaching_method",
        parameter_value=0,
        cycle_substrate_context=context,
    )

    assert type(result).__name__ == "InterventionLeverRefusal"
    assert result.status == "candidate_unbound"
    assert result.reason_code == "knob_operator_unresolved"
    assert result.operator_kind == "education.teaching_method"
    assert result.context_binding_hash == context.context_binding_hash
    assert result.world_model_record_content_hash == context.world_model_record_content_hash
    assert result.candidate_entry_content_hash in {
        row.entry_content_hash for row in context.candidate_levers
    }
    assert result.operator_kind not in bundle.knob_dictionary


def test_pack_context_fences_first_vertical_knob_fallback() -> None:
    """An education context cannot silently cross-bind a writable L6 knob."""

    _problem, context = _education_cycle_context()
    bundle = load_l6_intervention_substrate(REPO_ROOT)

    with pytest.raises(InterventionSubstrateError) as error:
        resolve_intervention_lever(
            bundle,
            operator_kind="budget_allocation_multiplier",
            parameter_value=1.0,
            cycle_substrate_context=context,
        )

    assert error.value.code == "cycle_substrate_candidate_lever_unresolved"


def _lex_store() -> LegalKnowledgeStore:
    return LegalKnowledgeStore(L3_DB, L3_DB.parent)


def _with_subject_spine(bundle, lex):
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.runtime.quality.intervention_substrate import (
        produce_intervention_legal_subject_spine,
    )

    ref = produce_intervention_legal_subject_spine(
        REPO_ROOT, bundle, legal_store=lex, store=FileSystemCAS(REPO_ROOT / ".polisyos/cas"))
    return replace_intervention_substrate_bundle(bundle, update={
        "owner_authority_manifest": {**bundle.owner_authority_manifest,
                                     "legal_subject_spine_ref": ref.model_dump(mode="json")}})


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
    bundle = _with_subject_spine(bundle, lex)

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

    assert admitted.status == "blocked"
    assert admitted.mapping_evidence_ref is not None
    assert admitted.recognition.status == "passed"
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
        assert isinstance(knob_ids, (list, tuple)), (law_token, knob_ids)
        for knob_id in knob_ids:
            raw_knob = bundle.knob_dictionary[knob_id]
            value = (float(raw_knob["min"]) + float(raw_knob["max"])) / 2.0
            traced[(law_token, knob_id)] = resolve_law_bound_lever(
                bundle,
                law_token=law_token,
                knob_id=knob_id,
                parameter_value=value,
                legal_store=lex,
            )

    owner_pairs = {(row["law_token"], knob_id)
                   for row in bundle.lex_authority_manifest["intervention_map_entries"]
                   for knob_id in row["knob_ids"]}
    assert set(traced) == owner_pairs
    assert {law for law, _knob in traced} == set(bundle.lex_intervention_map)
    assert all(item.provision_ref.startswith("duckdb://") for item in traced.values())
    assert all(item.threshold_id for item in traced.values())
    assert all(item.numeric_evaluation_status == "not_run" for item in traced.values())


def test_frozen_subject_producer_is_invariant_to_the_proposed_law_mapping(tmp_path) -> None:
    from polisyos.core import artifacts
    from polisyos.runtime.quality.intervention_substrate import (
        produce_intervention_legal_subject_spine,
    )

    bundle = load_l6_intervention_substrate(REPO_ROOT)
    store = artifacts.FileSystemCAS(tmp_path)
    lex = _lex_store()
    original = produce_intervention_legal_subject_spine(
        REPO_ROOT, bundle, legal_store=lex, store=store)
    manifest = copy.deepcopy(bundle.lex_authority_manifest)
    entries = manifest["intervention_map_entries"]
    targets = [row["provision_ref"] for row in entries]
    for row, target in zip(entries, targets[1:] + targets[:1], strict=True):
        row["provision_ref"] = target
    changed = replace_intervention_substrate_bundle(bundle, update={
        "lex_authority_manifest": manifest, "lex_intervention_map": {"novel": ["fake_knob"]}})
    assert changed.content_hash != bundle.content_hash
    assert produce_intervention_legal_subject_spine(
        REPO_ROOT, changed, legal_store=lex, store=store) == original


def test_every_real_law_knob_pair_is_recognized_only_relative_to_synthetic_sources() -> None:
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality import intervention_substrate as owner

    bundle = _with_subject_spine(load_l6_intervention_substrate(REPO_ROOT), _lex_store())
    expected = {(law, knob) for law in bundle.lex_intervention_map
                for knob in owner._lex_map_knobs(bundle.lex_intervention_map, law)}
    independently_derived = {(row["law_token"], knob)
                             for row in bundle.lex_authority_manifest["intervention_map_entries"]
                             for knob in row["knob_ids"]}
    assert expected == independently_derived
    observed = set()
    for law, knob in sorted(expected):
        value = owner._representative_knob_value(bundle.knob_dictionary[knob], knob_id=knob)
        result = resolve_law_bound_lever(
            bundle, law_token=law, knob_id=knob, parameter_value=value, legal_store=_lex_store())
        observed.add((result.law_token, result.knob_id))
        assert result.recognition.status == "passed"
        assert result.synthetic is True
        assert result.current_authority_status == "blocked"
        assert result.mapping_evidence_ref is not None
    assert observed == expected
    print({"denominator": "complete L6 law/knob pairs", "total": len(expected),
           "identity_hash": gy_content_hash(sorted(expected)),
           "independent_identity_hash": gy_content_hash(sorted(independently_derived)),
           "identity_symmetric_difference": sorted(expected ^ independently_derived)})


def test_current_law_resolution_rejects_rehashed_recognition_splices() -> None:
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.intervention_substrate import LawLeverResolution

    lex = _lex_store()
    result = resolve_law_bound_lever(
        _with_subject_spine(load_l6_intervention_substrate(REPO_ROOT), lex),
        law_token=BUDGET_LAW, knob_id="budget_allocation_multiplier",
        parameter_value=0.24, legal_store=lex)
    assert result.recognition.status == "passed"
    for key, value in (("lever_ref", "knob:tax_relief_rate"),
                       ("norm_ref", "lex_rule_thresholds:other")):
        payload = result.model_dump(mode="json")
        payload["recognition"]["request"][key] = value
        payload.pop("content_hash")
        payload["content_hash"] = gy_content_hash(payload)
        with pytest.raises(ValueError, match="law_mapping_recognition_entity_mismatch"):
            LawLeverResolution.model_validate(payload)
    for key, value in (("synthetic", False), ("mapping_reason_code", "invented_pass")):
        payload = result.model_dump(mode="json")
        payload[key] = value
        payload.pop("content_hash")
        payload["content_hash"] = gy_content_hash(payload)
        with pytest.raises(ValueError, match="law_mapping_recognition_projection_mismatch"):
            LawLeverResolution.model_validate(payload)


def test_subject_membership_and_actual_law_route_grow_as_data(tmp_path) -> None:
    import json

    from polisyos.core import artifacts
    from polisyos.foundry import LegalSubjectAnnotationSource
    from polisyos.runtime.quality import intervention_substrate as owner

    lex = _lex_store()
    threshold = lex.resolve_rule_threshold(
        threshold_id=FREE_GROW_L3_THRESHOLD_ID, as_of=FREE_GROW_L3_AS_OF)
    assert threshold is not None
    grown = owner._free_grow_bundle(load_l6_intervention_substrate(REPO_ROOT),
                                    threshold=threshold, as_of=FREE_GROW_L3_AS_OF)
    declarations = {}
    for role, entity in (("lever", "knob:" + FREE_GROW_KNOB),
                         ("norm", "lex_rule_thresholds:" + FREE_GROW_L3_THRESHOLD_ID)):
        path = REPO_ROOT / "architecture/policy_design_case" / (
            f"legal_subject_{role}_annotations.synthetic.json")
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["annotations"].append({"entity_ref": entity, "subject": {
            "namespace": "synthetic.legal-subject-controls", "namespace_version": "1",
            "subject_id": "data_only_new_subject", "valid_from": "1990-01-01"}})
        declarations[role] = LegalSubjectAnnotationSource.model_validate(raw)
    store = artifacts.FileSystemCAS(tmp_path)
    ref = owner.produce_intervention_legal_subject_spine(
        REPO_ROOT, grown, legal_store=lex, store=store, annotations=declarations)
    grown = replace_intervention_substrate_bundle(grown, update={
        "owner_authority_manifest": {**grown.owner_authority_manifest,
                                     "legal_subject_spine_ref": ref.model_dump(mode="json")}})
    result = resolve_law_bound_lever(
        grown, law_token=FUTURE_RELIEF_LAW, knob_id=FREE_GROW_KNOB, parameter_value=0.2,
        legal_store=lex, correspondence_store=store)
    assert result.recognition.status == "passed"
    assert result.knob.operator_kind == FREE_GROW_KNOB
    assert result.knob.target_world_slots == (FREE_GROW_SLOT,)
    assert result.synthetic is True
    assert result.current_authority_status == "blocked"
    assert result.mapping_evidence_ref is not None


def test_synthetic_recognition_does_not_authorize_credal_or_atom_consumers() -> None:
    from polisyos.runtime.quality import intervention_substrate as owner

    # This integration positive must share the actual credal consumer's logical
    # evidence identity. An absolute DB URI correctly fails content binding.
    lex = LegalKnowledgeStore(
        L3_DB, L3_DB.parent, canonical_db_ref_path=owner.DEFAULT_L3_LEX_DB_PATH)
    bundle = _with_subject_spine(load_l6_intervention_substrate(REPO_ROOT), lex)
    report = owner._law_credal_consumer_behavior_report(
        REPO_ROOT, bundle, owner.production_composed_world_model_record(REPO_ROOT))
    assert report["source_relative_recognition_passed"] is True
    assert report["status"] == "pass"
    assert not report["law_denominator"]["consumer_identity_difference"]
    assert not report["atom_denominator"]["identity_symmetric_difference"]
    assert report["remove_status_keep_markers_goes_red"] is True
    assert report["remove_association_keep_incomplete_goes_red"] is True


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
                            "contract_fqn": ("polisyos.foundry.methods.catalog.dead.Unregistered"),
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
        },
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
    assert unavailable.reason_code == "method_route_unresolved"
    assert not unavailable.candidate_method_fqns

    with pytest.raises(InterventionSubstrateError) as unknown:
        route_observation_family_method(bundle, family="unknown_family")
    assert unknown.value.code == "family_route_unresolved"


def test_default_method_route_excludes_changed_ambient_entry_points(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A governed route is byte-stable when ambient plugin membership changes."""

    unit = Unit("dimensionless", "1")

    class AmbientRouteMethod:
        signature = MethodSignature(
            name="ambient_route",
            namespace="external.method",
            version="1.0.0",
            input_slots=frozenset({SlotSpec("x", SlotType.SCALAR, unit)}),
            output_slots=frozenset({SlotSpec("y", SlotType.SCALAR, unit)}),
            parameters=(),
            fidelity=FidelityLevel.LOW,
            complexity=ComplexityClass.O_1,
            backend=ComputeBackend.NUMPY,
            supports_jit=False,
            supports_vmap=False,
            supports_grad=False,
        )
        metadata = MethodMetadata(description="Ambient route method")

        @staticmethod
        def pure_step(
            state: Mapping[str, Any],
            params: Mapping[str, Any],
        ) -> Mapping[str, Any]:
            del params
            return {"y": state["x"]}

    plugin = component_for_method(AmbientRouteMethod, domains=["external"])
    entry_point = _AmbientEntryPoint(
        name="external.method.ambient_route",
        value="ambient_route_plugin:plugin",
        component=plugin,
    )
    bundle = load_l6_intervention_substrate(REPO_ROOT)

    monkeypatch.setattr(
        "polisyos.core.components.discovery.list_entry_points",
        lambda *, group: [],
    )
    with registry_scope():
        baseline = route_observation_family_method(
            bundle,
            family="budget_flows",
        )
    assert capsys.readouterr() == ("", "")

    monkeypatch.setattr(
        "polisyos.core.components.discovery.list_entry_points",
        lambda *, group: [entry_point],
    )
    with registry_scope() as explicit_registry:
        ensure_all_methods_registered(explicit_registry)
        capsys.readouterr()
        changed_ambient = route_observation_family_method(
            bundle,
            family="budget_flows",
        )
        assert capsys.readouterr() == ("", "")
        explicitly_extended = route_observation_family_method(
            bundle,
            family="budget_flows",
            registry=explicit_registry,
        )

    assert baseline.registry_method_count > 0
    assert changed_ambient == baseline
    assert explicitly_extended.registry_method_count == (
        baseline.registry_method_count + 1
    )
    assert explicitly_extended.content_hash != baseline.content_hash


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
                        "provenance_refs": ["tests:free-grow-owner-mechanism-writes-real-wmr-slot"],
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
        },
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
    assert law.status == "blocked"
    assert law.mapping_evidence_ref is None
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
        },
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
