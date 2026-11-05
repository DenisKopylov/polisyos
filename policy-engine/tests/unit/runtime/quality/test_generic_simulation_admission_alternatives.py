"""Data-only generic NCM alternatives retain their actual selected CAS views."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, ensure_ir_artifact_store
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.ir.analytics.ncm import (
    NCMSpec,
    NCMSpecRef,
    StructuralEquation,
    load_ncm_spec_default_view,
    persist_ncm_spec,
)
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextOwnerError
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleN5RequestProfileV1,
    GenericCycleN5RequestProfileV2,
    GenericCycleSimulationAdmissionOwner,
    GenericCycleSimulationProfileV1,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    HorizonSpec,
    NCMConditionalComparatorProfile,
)
from polisyos.runtime.quality.world_model_record import world_model_artifact_views
from tests._helpers.controlled_candidate_profile import (
    _build_configured_procurement_profile,
    _capture_controlled_skg_source,
    _controlled_direct_ncm_outcome_state_paths,
    _materialize_controlled_world_model_build,
    _problem,
)

_TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_CELL = "generic-ncm-alternatives"


def _profile(fields: dict[str, Any]) -> GenericCycleSimulationProfileV1:
    draft = GenericCycleSimulationProfileV1.model_construct(
        **fields, content_hash="sha256:" + "0" * 64
    )
    return GenericCycleSimulationProfileV1.model_validate(
        {
            **fields,
            "content_hash": gy_content_hash(
                draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )


@pytest.fixture
def alternatives(tmp_path: Path) -> SimpleNamespace:
    """Produce real selected registries, WMR and both default-codec NCMs."""
    store = FileSystemCAS(
        tmp_path / "cas", tenant_id=_TENANT, cell_id=_CELL, ownership_enforced=True
    )
    base, declaration, _built = _build_configured_procurement_profile(
        recorded_problem=_problem("generic_alternative_scope"),
        artifact_store=store,
        tenant_id=_TENANT,
        cell_id=_CELL,
        tmp_path=tmp_path / "base",
    )
    views = world_model_artifact_views(base.context_inputs.world_model_record)
    good_ref = views.ncm_refs[0]
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        good = load_ncm_spec_default_view(
            ensure_ir_artifact_store(store),
            NCMSpecRef.model_validate(good_ref.model_dump(mode="python")),
        )
        cyclic_fields = good.model_dump(mode="python")
        cyclic_fields.update(
            {
                "is_acyclic": False,
                "scm_spec": None,
                "fit_method": "declared_candidate_feedback_alternative",
                "structural_equations": [
                    equation.model_copy(
                        update={
                            "parents": [declaration.outcome_variable],
                            "equation_params": {
                                **equation.equation_params,
                                "coefficients": {declaration.outcome_variable: 0.1},
                            },
                            "is_recursive": False,
                        }
                    )
                    if equation.variable == declaration.target_world_slot
                    else equation.model_copy(update={"is_recursive": False})
                    for equation in good.structural_equations
                ],
            }
        )
        cyclic = NCMSpec.model_validate(cyclic_fields)
        cyclic_ref = ArtifactRef.model_validate(
            persist_ncm_spec(ensure_ir_artifact_store(store), cyclic).model_dump(mode="python")
        )
    assert isinstance(cyclic.structural_equations[0], StructuralEquation)
    selected_source = _capture_controlled_skg_source(
        tmp_path / "base/controlled-candidate-source/academic-skg.duckdb"
    )
    built = _materialize_controlled_world_model_build(
        source_world_model_record=base.context_inputs.world_model_record,
        artifact_store=store,
        tmp_path=tmp_path / "multi-output",
        source_root=selected_source.db_path.parent,
        substrate_registry=base.context_inputs.substrate_registry,
        selected_registry_entry_hashes=base.context_inputs.selected_registry_entry_hashes,
        substrate_registry_ref=views.substrate_registry_ref,
        policy_slot_ids=tuple(
            slot.slot_id for slot in base.context_inputs.world_model_record.policy_slot_map
        ),
        selected_skg_source=selected_source,
        tenant_id=_TENANT,
        cell_id=_CELL,
        ncm_view_refs=(cyclic_ref, good_ref),
        candidate_baseline_state=base.n5.baseline_state,
        candidate_outcome_state_paths=_controlled_direct_ncm_outcome_state_paths(
            declaration.outcome_variable
        ),
        candidate_model_unit_ids={
            declaration.target_world_slot: declaration.target_unit_id,
            declaration.outcome_variable: declaration.outcome_unit_id,
        },
    )
    n5 = GenericCycleN5RequestProfileV2(
        budget_ref=base.n5.budget_ref,
        horizon=base.n5.horizon,
        baseline_state=base.n5.baseline_state,
        comparator_refs=base.n5.comparator_refs,
        seed=base.n5.seed,
        replications=base.n5.replications,
        ncm_plan_refs=(cyclic_ref, good_ref),
    )
    profile = _profile(
        {
            "profile_id": "controlled-ncm-alternatives",
            "profile_selection_ref": base.profile_selection_ref,
            "world_model_record_ref": built.record_ref,
            "substrate_registry_ref": views.substrate_registry_ref,
            "selected_ncm_ref": good_ref,
            "context_inputs": base.context_inputs.model_copy(
                update={"world_model_record": built.record}
            ),
            "n5": n5,
            "limitations": (
                "controlled_inputs_only",
                "currentness_not_established",
                "n5_simulation_not_world_evidence",
                "n9_not_admitted",
                "s8_blocked",
                "source_truth_not_established",
            ),
        }
    )
    return SimpleNamespace(
        store=store,
        profile=profile,
        declaration=declaration,
        good=good,
        cyclic=cyclic,
    )


def test_v1_n5_profile_roundtrip_does_not_invent_an_alternative_field() -> None:
    profile = GenericCycleN5RequestProfileV1(
        budget_ref="budget://controlled-singleton",
        horizon=HorizonSpec(start=0, end=0, step=1),
    )
    expected = {
        "schema_version": "policyos.runtime.generic_cycle_n5_request_profile.v1",
        "resource": "ncm_parallel_worlds",
        "budget_ref": "budget://controlled-singleton",
        "horizon": {
            "start": 0,
            "end": 0,
            "step": 1,
            "valid_time_role": "valid_time",
            "transaction_time_role": "transaction_time",
            "scenario_branch_policy": "hold_world_record_constant",
        },
        "baseline_state": {},
        "comparator_refs": [],
        "seed": 0,
        "replications": 1,
    }
    assert profile.model_dump(mode="json") == expected
    assert profile.model_dump_json() == (
        '{"schema_version":"policyos.runtime.generic_cycle_n5_request_profile.v1",'
        '"resource":"ncm_parallel_worlds","budget_ref":"budget://controlled-singleton",'
        '"horizon":{"start":0,"end":0,"step":1,"valid_time_role":"valid_time",'
        '"transaction_time_role":"transaction_time",'
        '"scenario_branch_policy":"hold_world_record_constant"},"baseline_state":{},'
        '"comparator_refs":[],"seed":0,"replications":1}'
    )
    assert gy_content_hash(profile.model_dump(mode="json")) == gy_content_hash(expected)
    assert GenericCycleN5RequestProfileV1.model_validate(expected) == profile


def test_v1_n5_axes_roundtrip_change_profile_hash_without_changing_legacy_bytes(
    alternatives: SimpleNamespace,
) -> None:
    profile = alternatives.profile
    legacy_body = profile.model_dump(mode="json", exclude={"content_hash"})
    assert not {
        "evidence_state",
        "comparator_profile",
        "engine_variable_map",
    } & set(legacy_body["n5"])
    assert profile.content_hash == gy_content_hash(legacy_body)

    outcome = alternatives.declaration.outcome_variable
    target = alternatives.declaration.target_world_slot
    n5 = profile.n5.model_copy(
        update={
            "evidence_state": {outcome: 0.0},
            "comparator_profile": NCMConditionalComparatorProfile(
                outcome_units={outcome: alternatives.declaration.outcome_unit_id}
            ),
            "engine_variable_map": {target: target},
        }
    )
    fields = profile.model_dump(mode="python", exclude={"content_hash"})
    fields["n5"] = n5
    altered = _profile(fields)
    assert altered.content_hash != profile.content_hash
    restored = GenericCycleSimulationProfileV1.model_validate_json(altered.model_dump_json())
    assert restored == altered
    assert restored.n5.evidence_state == {outcome: 0.0}
    assert restored.n5.comparator_profile == n5.comparator_profile
    assert restored.n5.engine_variable_map == {target: target}


def test_v1_n5_axes_reject_nonfinite_evidence_blank_aliases_and_implicit_comparator_evidence() -> (
    None
):
    common = {
        "budget_ref": "budget://controlled-singleton",
        "horizon": HorizonSpec(start=0, end=0, step=1),
    }
    with pytest.raises(ValueError, match="generic_cycle_n5_evidence_non_finite"):
        GenericCycleN5RequestProfileV1(**common, evidence_state={"outcome": float("inf")})
    with pytest.raises(ValueError, match="generic_cycle_n5_engine_variable_map_invalid"):
        GenericCycleN5RequestProfileV1(**common, engine_variable_map={" ": "numeric_alias"})
    with pytest.raises(ValueError, match="generic_cycle_n5_engine_variable_map_invalid"):
        GenericCycleN5RequestProfileV1(**common, engine_variable_map={"causal.slot": " "})
    with pytest.raises(ValidationError):
        GenericCycleN5RequestProfileV1(**common, engine_variable_map={1: "numeric_alias"})
    with pytest.raises(ValidationError):
        GenericCycleN5RequestProfileV1(**common, engine_variable_map={"causal.slot": 1})
    with pytest.raises(ValueError, match="generic_cycle_n5_comparator_evidence_state_required"):
        GenericCycleN5RequestProfileV1(
            **common,
            baseline_state={"outcome": 1.0},
            comparator_profile=NCMConditionalComparatorProfile(
                outcome_units={"outcome": "synthetic_unit"}
            ),
        )


def test_profile_owner_reopens_all_ordered_views_and_preserves_typed_v2(
    alternatives: SimpleNamespace,
) -> None:
    profile = alternatives.profile
    restored = GenericCycleSimulationProfileV1.model_validate_json(profile.model_dump_json())
    assert type(restored.n5) is GenericCycleN5RequestProfileV2
    assert restored == profile
    owner = GenericCycleSimulationAdmissionOwner(profiles=(restored,), store=alternatives.store)
    outcome = alternatives.declaration.outcome_variable
    variable_map = {
        alternatives.declaration.target_world_slot: alternatives.declaration.target_world_slot,
        outcome: outcome,
    }
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        plans = owner.build_engine_plans(
            profile=restored,
            world_record=restored.context_inputs.world_model_record,
            outcome=outcome,
            variable_map=variable_map,
        )
    assert tuple(plan.ncm_spec for plan in plans) == (alternatives.cyclic, alternatives.good)
    assert all(plan.variable_map == variable_map for plan in plans)
    assert all(plan.objective_ref == f"objective://{outcome}" for plan in plans)
    assert plans[0].ncm_spec.is_acyclic is False
    assert plans[1].ncm_spec.is_acyclic is True
    options = owner._profile_write_options(
        profile=restored, job_id="job", run_id="run", tenant_id=_TENANT, cell_id=_CELL
    )
    assert {item.role for item in options.inputs} >= {"ncm_plan:0", "ncm_plan:1"}

    # Coherent rehashing does not permit hiding or reordering the WMR denominator.
    for refs in (tuple(reversed(restored.n5.ncm_plan_refs)), restored.n5.ncm_plan_refs[1:]):
        fields = {
            name: getattr(restored, name)
            for name in type(restored).model_fields
            if name != "content_hash"
        }
        fields["n5"] = restored.n5.model_copy(update={"ncm_plan_refs": refs})
        altered = _profile(fields)
        with (
            tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL),
            pytest.raises(CycleSubstrateContextOwnerError, match="plan_basis_mismatch"),
        ):
            owner.build_engine_plans(
                profile=altered,
                world_record=restored.context_inputs.world_model_record,
                outcome=outcome,
                variable_map=variable_map,
            )

    with (
        tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL),
        pytest.raises(CycleSubstrateContextOwnerError, match="plan_estimand_mismatch"),
    ):
        owner.build_engine_plans(
            profile=restored,
            world_record=restored.context_inputs.world_model_record,
            outcome=outcome,
            variable_map={**variable_map, "foreign.slot": "foreign.variable"},
        )


def test_profile_engine_variable_map_is_wmr_bound_and_composes_with_atom_aliases(
    alternatives: SimpleNamespace,
) -> None:
    base = alternatives.profile
    outcome = alternatives.declaration.outcome_variable
    target = alternatives.declaration.target_world_slot
    n5 = base.n5.model_copy(
        update={
            "engine_variable_map": {
                target: target,
                outcome: outcome,
            }
        }
    )
    fields = base.model_dump(mode="python", exclude={"content_hash"})
    fields["n5"] = n5
    profile = _profile(fields)
    owner = GenericCycleSimulationAdmissionOwner(profiles=(profile,), store=alternatives.store)
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        plans = owner.build_engine_plans(
            profile=profile,
            world_record=profile.context_inputs.world_model_record,
            outcome=outcome,
            variable_map={target: target},
        )
    expected_map = {target: target, outcome: outcome}
    assert all(plan.variable_map == expected_map for plan in plans)

    invalid_maps = (
        ({"unknown.world.slot": "unknown_alias"}, {target: target}),
        ({target: target}, {target: "atom_alias"}),
        ({target: outcome}, {target: target, outcome: outcome}),
    )
    for engine_variable_map, atom_variable_map in invalid_maps:
        invalid_n5 = base.n5.model_copy(update={"engine_variable_map": engine_variable_map})
        invalid_fields = base.model_dump(mode="python", exclude={"content_hash"})
        invalid_fields["n5"] = invalid_n5
        invalid_profile = _profile(invalid_fields)
        with (
            tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL),
            pytest.raises(CycleSubstrateContextOwnerError, match="plan_basis_mismatch"),
        ):
            owner.build_engine_plans(
                profile=invalid_profile,
                world_record=invalid_profile.context_inputs.world_model_record,
                outcome=outcome,
                variable_map=atom_variable_map,
            )

    missing_model_n5 = base.n5.model_copy(
        update={"engine_variable_map": {target: "missing.ncm.variable"}}
    )
    missing_model_fields = base.model_dump(mode="python", exclude={"content_hash"})
    missing_model_fields["n5"] = missing_model_n5
    missing_model_profile = _profile(missing_model_fields)
    with (
        tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL),
        pytest.raises(CycleSubstrateContextOwnerError, match="plan_estimand_mismatch"),
    ):
        owner.build_engine_plans(
            profile=missing_model_profile,
            world_record=missing_model_profile.context_inputs.world_model_record,
            outcome=outcome,
            variable_map={target: target, outcome: outcome},
        )


@pytest.mark.parametrize(
    "with_comparator",
    [False, True],
    ids=["evidence-only", "evidence-and-comparator"],
)
def test_profile_axes_reject_duplicate_incoming_aliases_with_empty_profile_map(
    alternatives: SimpleNamespace,
    with_comparator: bool,
) -> None:
    base = alternatives.profile
    world = base.context_inputs.world_model_record
    outcome = alternatives.declaration.outcome_variable
    target = alternatives.declaration.target_world_slot
    world_slots = {slot.slot_id for slot in world.policy_slot_map}
    assert target != outcome
    assert {target, outcome} <= world_slots

    # This is an actual endogenous variable in a selected NCM, so the old
    # estimand-coverage check alone would admit both source slots as aliases.
    shared_alias = outcome
    assert shared_alias in alternatives.good.endogenous_vars
    axes: dict[str, Any] = {
        "evidence_state": {outcome: base.n5.baseline_state[outcome]},
        "engine_variable_map": {},
    }
    if with_comparator:
        axes["comparator_profile"] = NCMConditionalComparatorProfile(
            outcome_units={outcome: alternatives.declaration.outcome_unit_id}
        )
    n5 = base.n5.model_copy(update=axes)
    fields = {
        name: getattr(base, name) for name in type(base).model_fields if name != "content_hash"
    }
    fields["n5"] = n5
    profile = _profile(fields)
    assert profile.n5.engine_variable_map == {}

    owner = GenericCycleSimulationAdmissionOwner(profiles=(profile,), store=alternatives.store)
    with (
        tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL),
        pytest.raises(
            CycleSubstrateContextOwnerError,
            match="generic_cycle_simulation_n5_plan_basis_mismatch",
        ),
    ):
        owner.build_engine_plans(
            profile=profile,
            world_record=world,
            outcome=outcome,
            variable_map={target: shared_alias, outcome: shared_alias},
        )


def test_legacy_empty_profile_axes_preserve_noninjective_atom_map_behavior(
    alternatives: SimpleNamespace,
) -> None:
    profile = alternatives.profile
    outcome = alternatives.declaration.outcome_variable
    target = alternatives.declaration.target_world_slot
    world = profile.context_inputs.world_model_record
    variable_map = {target: outcome, outcome: outcome}
    assert profile.n5.evidence_state is None
    assert profile.n5.comparator_profile is None
    assert profile.n5.engine_variable_map == {}

    owner = GenericCycleSimulationAdmissionOwner(profiles=(profile,), store=alternatives.store)
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        plans = owner.build_engine_plans(
            profile=profile,
            world_record=world,
            outcome=outcome,
            variable_map=variable_map,
        )
    assert plans
    assert all(plan.variable_map == variable_map for plan in plans)


@pytest.mark.parametrize("selector", [None, "0" * 64], ids=["profileless", "foreign-profile"])
def test_v2_requires_exact_available_selected_ncm_view(
    alternatives: SimpleNamespace, selector: str | None
) -> None:
    """Same bytes never grant a missing or foreign selected-view capability."""
    profile = alternatives.profile
    altered_ref = profile.n5.ncm_plan_refs[0].model_copy(
        update={"manifest_profile_sha256": selector}
    )
    fields = profile.n5.model_dump(mode="python")
    fields["ncm_plan_refs"] = (altered_ref, *profile.n5.ncm_plan_refs[1:])
    if selector is None:
        with pytest.raises(ValueError, match="plan_ref_kind_or_selector_invalid"):
            GenericCycleN5RequestProfileV2.model_validate(fields)
        return
    # An explicit selector is also an actual read capability, not only syntax.
    # The production admission loop invokes this same owner check for every
    # V2 view before accepting the profile or deriving any engine plan.
    altered = GenericCycleN5RequestProfileV2.model_validate(fields)
    owner = GenericCycleSimulationAdmissionOwner(profiles=(profile,), store=alternatives.store)
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL), pytest.raises((OSError, ValueError)):
        owner._verify_default_ncm(altered.ncm_plan_refs[0])
