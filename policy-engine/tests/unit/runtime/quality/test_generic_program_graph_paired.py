"""Paired-profile numerical projections, without executing an N5 unit.

These tests exercise the complete field-role projection over a real atom
producer. They do not establish current source permission or a numerical result;
the served paired producer and immutable reader must establish those separately.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.runtime.quality.acquisition_evaluation import (
    _generic_paired_atom_numerical_values,
)
from polisyos.runtime.quality.intervention_atom_binding import (
    DirectEffectBundle,
    InterventionAtomBinding,
    intervention_atom_content_hash,
)
from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes
from tests.unit.runtime.quality.test_joint_simulation_horizon import _atom, _request


def _produced_atom() -> InterventionAtomBinding:
    return _atom(
        intervention_id="income_subsidy",
        causal_variable="agents.income",
        engine_variable="income_delta",
        value=1.0,
        world_model_record_ref="world://paired-projection",
    )


def _rebind(atom: InterventionAtomBinding, **updates: object) -> InterventionAtomBinding:
    """Retain the ordinary content-bound atom contract in each contrast."""
    draft = atom.model_copy(update=updates)
    digest = intervention_atom_content_hash(draft)
    return InterventionAtomBinding.model_validate(
        {
            **draft.model_dump(mode="python"),
            "atom_id": "atom_" + digest.removeprefix("sha256:")[:16],
            "content_hash": digest,
        }
    )


def test_paired_atom_projection_resolves_provenance_without_losing_intended_values() -> None:
    """A release/authority label does not become an artificial numeric input."""
    original = _produced_atom()
    relabelled = _rebind(
        original,
        policy_spec_ref="sha256:" + "d" * 64,
        world_model_record_ref="world://same-values-new-release",
        producer_ref="test.paired.next-release",
        provenance_refs=("sha256:" + "e" * 64,),
        status="grounded",
        direct_effect_bundle=original.direct_effect_bundle.model_copy(
            update={"notes": (*original.direct_effect_bundle.notes, "release:next")}
        ),
    )
    assert original.content_hash != relabelled.content_hash
    assert exact_n5_content_bytes(original) != exact_n5_content_bytes(relabelled)
    assert _generic_paired_atom_numerical_values(original) == (
        _generic_paired_atom_numerical_values(relabelled)
    )


@pytest.mark.parametrize("changed_field", ["dose", "schedule", "target", "operator", "do"])
def test_paired_atom_projection_keeps_intended_algorithmic_changes(changed_field: str) -> None:
    """An ignored-by-old-runner intention must still change the new intent."""
    atom = _produced_atom()
    if changed_field == "dose":
        changed = _rebind(
            atom,
            direct_effect_bundle=atom.direct_effect_bundle.model_copy(
                update={"params": {"rate": Decimal("0.125")}}
            ),
        )
    elif changed_field == "schedule":
        changed = _rebind(
            atom,
            direct_effect_bundle=atom.direct_effect_bundle.model_copy(
                update={"schedule": {"start_step": 1, "duration_steps": 4, "end_step": None}}
            ),
        )
    elif changed_field == "target":
        changed = _rebind(atom, target_world_slots=("government.balance",))
    elif changed_field == "operator":
        changed = _rebind(
            atom, operator_kind=atom.operator_kind.model_copy(update={"trinity_kind": "income_tax"})
        )
    else:
        assignment = atom.causal_do_expr.assignments[0].model_copy(update={"value": 2.0})
        changed = _rebind(
            atom,
            causal_do_expr=atom.causal_do_expr.model_copy(
                update={
                    "assignments": (assignment,),
                    "expression_payload": {
                        "intervention_type": "node",
                        "assignments": [assignment.model_dump(mode="json")],
                    },
                }
            ),
        )
    assert _generic_paired_atom_numerical_values(atom) != (
        _generic_paired_atom_numerical_values(changed)
    )


def test_paired_atom_projection_refuses_unclassified_future_fields() -> None:
    """New model axes cannot silently disappear from the intent denominator."""

    class FutureAtom(InterventionAtomBinding):
        entity_axes: tuple[str, ...] = ("households",)

    class FutureDirectEffects(DirectEffectBundle):
        growth_option: bool = True

    atom = _produced_atom()
    with pytest.raises(
        ValueError, match="generic_model_input_paired_atom_field_role_census_mismatch"
    ):
        _generic_paired_atom_numerical_values(FutureAtom.model_construct(**atom.model_dump()))
    with pytest.raises(
        ValueError, match="generic_model_input_paired_direct_effect_field_role_census_mismatch"
    ):
        _generic_paired_atom_numerical_values(
            atom.model_copy(
                update={
                    "direct_effect_bundle": FutureDirectEffects.model_construct(
                        **atom.direct_effect_bundle.model_dump()
                    )
                }
            )
        )


def _physical_budget_request(atom_count: int, *, replications: int = 1):
    """Build a typed descriptor only; no model/source permission is asserted."""
    from polisyos.runtime.quality.joint_simulation_horizon import (
        EngineDecision,
        EnginePlan,
        HorizonSpec,
        JointSimulationRequest,
        ProgramGraphPairedComparatorProfileV4,
    )

    original = _request()
    atoms = original.intervention_atoms
    if atom_count == 3:
        atoms = (
            *atoms,
            _atom(
                intervention_id="third_subsidy",
                causal_variable="agents.income",
                engine_variable="third_delta",
                value=2.0,
                world_model_record_ref=original.world_model_record_ref,
            ),
        )
    plan = EnginePlan(engine_kind="program_graph", objective_ref="objective://budget-only")
    request = JointSimulationRequest.model_validate(
        {
            **original.model_dump(mode="python"),
            "intervention_atoms": atoms[:atom_count],
            "engine_plan": (plan,),
            "horizon": HorizonSpec(start=0, end=0, step=1),
            "replications": replications,
            "program_graph_comparator_profile": ProgramGraphPairedComparatorProfileV4(),
        }
    )
    decision = EngineDecision(
        engine_kind="program_graph",
        objective_ref=plan.objective_ref,
        decision="selected",
        method_fqn="test.budget-only-not-executed",
        equilibrium_semantics="none",
        output_shape="program_state_trajectory",
        reason="budget descriptor, not source admission",
    )
    return request, plan, decision


@pytest.mark.parametrize(("atom_count", "units_per_seed"), [(1, 2), (2, 4), (3, 8)])
def test_paired_physical_denominator_deduplicates_roles_before_counting(
    atom_count: int, units_per_seed: int
) -> None:
    """Count actual unique subsets plus baseline, rather than twice the atom count."""
    from polisyos.runtime.quality.joint_simulation_horizon import _planned_physical_units

    request, plan, decision = _physical_budget_request(atom_count, replications=3)
    assert len(_planned_physical_units(request, plan, decision)) == 3 * units_per_seed


def test_paired_request_cannot_be_projected_as_an_old_unpaired_intent() -> None:
    """The new physical axis must never be silently ignored by a V2/V3 view."""
    from polisyos.runtime.quality.acquisition_evaluation import (
        _GENERIC_REQUEST_FIELD_ROLES,
        _generic_numerical_fields,
    )

    legacy = _request()
    assert "program_graph_comparator_profile" not in legacy.model_dump(mode="json")
    _generic_numerical_fields(legacy, _GENERIC_REQUEST_FIELD_ROLES, scope="request")
    paired, _plan, _decision = _physical_budget_request(1)
    with pytest.raises(ValueError, match=r"^generic_model_input_paired_profile_requires_v4$"):
        _generic_numerical_fields(paired, _GENERIC_REQUEST_FIELD_ROLES, scope="request")


def test_paired_world_release_changes_do_not_replace_the_numeric_mapping() -> None:
    """Full WMR/atom refs change, while their resolved physical projection stays equal."""
    from polisyos.runtime.quality.acquisition_evaluation import _generic_request_numerical_values
    from polisyos.runtime.quality.world_model_record import (
        WorldModelRecord,
        world_model_record_content_hash,
    )

    request, _plan, _decision = _physical_budget_request(1)
    original = request.world_model_record
    draft = original.model_copy(
        update={
            "authority_status": "limited",
            "producer_ref": "test.new-release-same-values",
            "data_forge_binding_ref": original.data_forge_binding_ref.model_copy(
                update={"release_id": "release-next"}
            ),
        }
    )
    digest = world_model_record_content_hash(draft)
    world = WorldModelRecord.model_validate(
        {
            **draft.model_dump(mode="python"),
            "world_model_record_id": "world_model_record_" + digest.removeprefix("sha256:")[:16],
            "content_hash": digest,
        }
    )
    changed = type(request).model_validate(
        {
            **request.model_dump(mode="python"),
            "world_model_record": world,
            "world_model_record_ref": world.world_model_record_id,
            "intervention_atoms": tuple(
                _rebind(atom, world_model_record_ref=world.world_model_record_id)
                for atom in request.intervention_atoms
            ),
        }
    )
    assert original.content_hash != world.content_hash
    assert _generic_request_numerical_values(request) == _generic_request_numerical_values(changed)


def test_paired_world_nested_model_state_requires_a_deliberate_role() -> None:
    """A newly declared model option must not hide inside a resolved WMR ref."""
    from polisyos.runtime.quality.acquisition_evaluation import _generic_request_numerical_values
    from polisyos.runtime.quality.world_model_record import SimulationModelRef

    class FutureModelState(SimulationModelRef):
        growth_option: bool = True

    request, _plan, _decision = _physical_budget_request(1)
    future = FutureModelState.model_construct(
        **request.world_model_record.simulation_model_ref.model_dump(mode="python")
    )
    changed = request.model_copy(
        update={
            "world_model_record": request.world_model_record.model_copy(
                update={"simulation_model_ref": future}
            )
        }
    )
    with pytest.raises(
        ValueError,
        match="generic_model_input_paired_world_simulation_model_ref_field_role_census_mismatch",
    ):
        _generic_request_numerical_values(changed)


def test_paired_capacity_refuses_the_whole_plan_before_a_new_reservation(tmp_path: Path) -> None:
    """A real durable remaining-five quota cannot start a required-six pair set."""
    from polisyos.runtime.quality.joint_simulation_horizon import (
        _PhysicalWorkInterruptedError,
        _run_cached_replicates,
    )
    from tests.unit.scientist.orchestration.engine.test_producer_budget_c49 import (
        _diagnostic_owner,
        _finish_invocation,
    )

    ledger, _store, _binding, policy, observer = _diagnostic_owner(
        tmp_path, total=7, protected=1, purpose="standard"
    )
    _finish_invocation(observer, policy, "previous-budget-unit", "standard")
    before = ledger.snapshot()
    assert observer.observe_standard_invocation_capacity().standard_remaining_units == 5
    request, plan, decision = _physical_budget_request(1, replications=3)
    calls = []

    def forbidden(*_args):
        calls.append("physical")
        raise AssertionError("a partial pair must not dispatch")

    with pytest.raises(
        _PhysicalWorkInterruptedError, match="n5_paired_invocation_capacity_not_established"
    ) as failed:
        _run_cached_replicates(
            request,
            plan,
            decision,
            forbidden,
            comparator_once=forbidden,
            comparator_samples=[],
            producer_budget_observer=observer,
        )
    assert failed.value.observations == ()
    assert failed.value.budget_refusal_basis["required_physical_units"] == 6
    assert calls == []
    assert ledger.snapshot() == before


def _paired_result_envelope() -> dict[str, object]:
    """Reuse the paired descriptor for constructor routing, not CAS/source proof."""
    from datetime import UTC, datetime

    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.contracts.foundry import SimulationResultRef
    from polisyos.runtime.quality.joint_simulation_horizon import (
        PhysicalSimulationWorkObservation,
        ProgramGraphPairedBaselineSampleV4,
        ProgramGraphPairedComparatorV4,
    )

    request, _plan, decision = _physical_budget_request(1)
    seed = 17
    event = PhysicalSimulationWorkObservation(
        invocation_id="a" * 32,
        event_id="b" * 32,
        physical_spec_ref="c" * 64,
        effective_seed=seed,
        status="completed",
        started_at=datetime(2026, 11, 16, tzinfo=UTC),
        completed_at=datetime(2026, 11, 16, tzinfo=UTC),
        duration_seconds=0.0,
        budget_status="not_established",
    )
    baseline = ProgramGraphPairedBaselineSampleV4(
        replication_seed=seed,
        physical_spec_ref=event.physical_spec_ref,
        physical_work_event_id=event.event_id,
        actuation_selection_ref=ArtifactRef(
            artifact_id="sha256:" + "d" * 64,
            kind="foundry.program_graph_actuation_selection",
            media_type="application/json",
            manifest_profile_sha256="sha256:" + "e" * 64,
        ),
        step_result_refs=(
            SimulationResultRef(
                artifact_id="sha256:" + "f" * 64,
                kind="foundry.simulation_result",
                media_type="application/json",
                manifest_profile_sha256="sha256:" + "1" * 64,
            ),
        ),
        outcomes_by_step=(dict.fromkeys(request.selected_outcomes, 1.0),),
    )
    comparator = ProgramGraphPairedComparatorV4(
        selected_outcomes=request.selected_outcomes,
        steps=request.horizon.steps(),
        samples=(baseline,),
    )
    return {
        "schema_version": "policyos.runtime.joint_simulation_horizon.v1",
        "world_model_record_ref": request.world_model_record_ref,
        "world_model_record_content_hash": request.world_model_record.content_hash,
        "atom_ids": [atom.intervention_id for atom in request.intervention_atoms],
        "selected_outcomes": request.selected_outcomes,
        "horizon": request.horizon.model_dump(mode="json"),
        "engine_decisions": [decision.model_dump(mode="json")],
        "equilibrium_semantics": {decision.objective_ref: "none"},
        "trajectories": [],
        "marginal_effects": {},
        "interaction_terms": [],
        "feedback_classification": {"numeric_interaction": "unsupported"},
        "promotion_ready_value_packet": {
            "effect_basis": comparator.estimand,
            "effect_basis_status": "not_applicable_no_trajectory",
            "comparator_refs_status": "selected_manifest_required",
        },
        "diagnostics": {
            "engine_run_claimed": False,
            "requested_replications": 1,
            "replication_seeds": [seed],
            "effect_basis": comparator.estimand,
            "effect_basis_status": "established",
            "comparator_refs_status": "selected_manifest_required",
            "physical_work_capture_status": "observed",
            "physical_work_observations": [event.model_dump(mode="json")],
            "physical_work_units": 1,
            "physical_work_unit": "physical_simulation_invocation",
            "physical_work_usd_cost_status": "not_established",
            "program_graph_paired_comparator": comparator.model_dump(mode="json"),
        },
    }


def _construct_paired_result(payload: dict[str, object], *, engine: str = "program_graph"):
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationResult,
        build_content_bound_simulation_receipt,
    )

    receipt = build_content_bound_simulation_receipt(
        engine_kind=engine, payload=payload, diagnostics=payload["diagnostics"]
    )
    return JointSimulationResult.model_validate({**payload, "receipt": receipt})


def test_program_graph_pair_constructor_uses_its_typed_comparator_family() -> None:
    """The real DTO must not demand an NCM record for a typed graph envelope."""
    result = _construct_paired_result(_paired_result_envelope())
    assert result.diagnostics["effect_basis_status"] == "established"
    assert result.receipt.engine_kind == "program_graph"


def test_ncm_constructor_still_refuses_established_without_its_record() -> None:
    payload = _paired_result_envelope()
    payload["diagnostics"].pop("program_graph_paired_comparator")
    payload["engine_decisions"][0]["engine_kind"] = "ncm_parallel_worlds"
    with pytest.raises(ValueError, match="ncm_comparator_record_missing"):
        _construct_paired_result(payload, engine="ncm_parallel_worlds")


@pytest.mark.parametrize(
    ("changed", "reason"),
    [
        ("missing", "program_graph_paired_comparator_missing"),
        ("mixed", "simulation_comparator_family_conflict"),
        ("engine", "program_graph_paired_comparator_scope_invalid"),
        ("receipt", "program_graph_paired_comparator_scope_invalid"),
        ("effect", "program_graph_paired_comparator_scope_invalid"),
        ("packet_effect", "program_graph_paired_comparator_scope_invalid"),
        ("status", "program_graph_paired_comparator_scope_invalid"),
        ("refs", "program_graph_paired_comparator_scope_invalid"),
        ("outcome", "program_graph_paired_baseline_work_mismatch"),
        ("work", "program_graph_paired_baseline_work_mismatch"),
    ],
)
def test_paired_constructor_refuses_grafted_family_or_unbound_record(
    changed: str, reason: str
) -> None:
    payload = _paired_result_envelope()
    diagnostics = payload["diagnostics"]
    engine = "program_graph"
    if changed == "missing":
        diagnostics.pop("program_graph_paired_comparator")
    elif changed == "mixed":
        diagnostics["ncm_conditional_comparator"] = {}
    elif changed == "engine":
        payload["engine_decisions"][0]["engine_kind"] = "ncm_parallel_worlds"
    elif changed == "receipt":
        engine = "ncm_parallel_worlds"
    elif changed == "effect":
        diagnostics["effect_basis"] = "paired_conditional_model_difference.v1"
    elif changed == "packet_effect":
        payload["promotion_ready_value_packet"]["effect_basis"] = (
            "paired_conditional_model_difference.v1"
        )
    elif changed == "status":
        diagnostics["effect_basis_status"] = "not_established"
    elif changed == "refs":
        diagnostics["comparator_refs_status"] = "not_established"
    elif changed == "outcome":
        record = diagnostics["program_graph_paired_comparator"]
        record["selected_outcomes"] = ["other_outcome"]
        record["samples"][0]["outcomes_by_step"] = [{"other_outcome": 1.0}]
    elif changed == "work":
        diagnostics["program_graph_paired_comparator"]["samples"][0]["physical_work_event_id"] = (
            "9" * 32
        )
    with pytest.raises(ValueError, match=reason):
        _construct_paired_result(payload, engine=engine)


def test_ncm_constructor_still_refuses_an_invalid_record() -> None:
    payload = _paired_result_envelope()
    diagnostics = payload["diagnostics"]
    diagnostics.pop("program_graph_paired_comparator")
    diagnostics["ncm_conditional_comparator"] = {"schema_version": "wrong"}
    payload["engine_decisions"][0]["engine_kind"] = "ncm_parallel_worlds"
    with pytest.raises(ValueError, match="ncm_comparator_record_invalid"):
        _construct_paired_result(payload, engine="ncm_parallel_worlds")


def test_unpaired_legacy_constructor_does_not_acquire_a_comparator_requirement() -> None:
    payload = _paired_result_envelope()
    payload["diagnostics"].pop("program_graph_paired_comparator")
    payload["diagnostics"]["effect_basis_status"] = "not_established"
    result = _construct_paired_result(payload)
    assert result.diagnostics["effect_basis_status"] == "not_established"


def test_graph_family_removal_control_keeps_markers_but_loses_the_typed_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality import joint_simulation_horizon as owner

    payload = _paired_result_envelope()
    payload["engine_decisions"][0]["engine_kind"] = "ncm_parallel_worlds"
    with pytest.raises(ValueError, match="program_graph_paired_comparator_scope_invalid"):
        _construct_paired_result(payload)
    # The same constructor markers/receipt now accept an NCM-selected graph
    # record if the actual family guard is removed. Source/CAS authority is
    # still not established by this deliberately bounded envelope fixture.
    with monkeypatch.context() as removal:
        removal.setattr(owner, "_read_program_graph_paired_comparator", lambda _result: object())
        forged = _construct_paired_result(payload)
        assert forged.engine_decisions[0].engine_kind == "ncm_parallel_worlds"
    with pytest.raises(ValueError, match="program_graph_paired_comparator_scope_invalid"):
        _construct_paired_result(payload)


def test_interrupted_graph_pair_keeps_its_family_without_establishing_completion() -> None:
    payload = _paired_result_envelope()
    payload["diagnostics"]["physical_work_interruption"] = "n5_physical_work_failed"
    payload["diagnostics"]["effect_basis_status"] = "not_established"
    result = _construct_paired_result(payload)
    assert result.diagnostics["effect_basis_status"] == "not_established"
    assert result.diagnostics["effect_basis"] == "same_seed_compiled_intervention_difference.v4"
