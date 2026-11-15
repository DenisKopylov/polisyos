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
