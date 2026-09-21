"""Test-first witness for SIM-02 output, atom, and trajectory semantics.

The existing N5 tests cover the happy paths of the joint controller.  This
file keeps the three E02 counterexamples together so that a future repair is
driven by the observable controller boundary:

* B18 must not turn a missing/non-finite selected outcome into a numeric zero;
* B20 must not make incompatible atom assignments order-dependent; and
* B22 must not turn uncovered horizon steps into an implicit last-value hold.

The tests deliberately include positive controls for an explicit zero and an
identical assignment.  They are expected to be RED on the current
integration base until the corresponding production contract is repaired.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
from polisyos.foundry.methods.selection.registry import MethodRegistry
from polisyos.runtime.quality.joint_simulation_horizon import (
    EnginePlan,
    HorizonSpec,
    JointSimulationControllerError,
    JointSimulationHorizonController,
    JointSimulationRequest,
)
from tests.unit.runtime.quality.test_joint_simulation_horizon import (
    _atom,
    _request,
)


def _request_with_same_target_assignments(
    *,
    left_value: float,
    right_value: float,
    reverse: bool = False,
) -> JointSimulationRequest:
    """Build an NCM request whose two atoms target the same world variable."""
    request = _request()
    world_record_ref = request.world_model_record.world_model_record_id
    atoms = (
        _atom(
            intervention_id="income_subsidy",
            causal_variable="agents.income",
            engine_variable="income_delta",
            value=left_value,
            world_model_record_ref=world_record_ref,
        ),
        _atom(
            intervention_id="balance_grant",
            causal_variable="agents.income",
            engine_variable="income_delta",
            value=right_value,
            world_model_record_ref=world_record_ref,
        ),
    )
    if reverse:
        atoms = tuple(reversed(atoms))
    return request.model_copy(update={"intervention_atoms": atoms})


@pytest.mark.parametrize(
    "world_summary",
    [
        {},
        {"firm_survival": {}},
        {"firm_survival": {"mean": float("nan")}},
        {"firm_survival": {"mean": float("inf")}},
    ],
    ids=("empty-world", "missing-outcome", "nan-outcome", "infinite-outcome"),
)
def test_ncm_selected_outcome_missing_or_nonfinite_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    world_summary: dict[str, Any],
) -> None:
    """B18: absence and invalid numbers must not become an observed zero."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "counterfactual_result": {
                "world_summaries": [{"world_index": 0, **world_summary}],
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fake_pure_step))

    with pytest.raises(JointSimulationControllerError):
        JointSimulationHorizonController().run(_request())


def test_ncm_explicit_zero_is_preserved_as_a_real_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B18 positive control: an explicit finite zero remains numeric zero."""

    def fake_pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "counterfactual_result": {
                "world_summaries": [
                    {"world_index": 0, "firm_survival": {"mean": 0.0}},
                ],
            }
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(fake_pure_step))

    result = JointSimulationHorizonController().run(_request())

    joint = result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert joint.points[0].outcomes == {"firm_survival": 0.0}


@pytest.mark.parametrize("reverse", [False, True], ids=("left-right", "right-left"))
def test_conflicting_atom_assignments_are_rejected_instead_of_last_wins(
    reverse: bool,
) -> None:
    """B20: different values for one target slot are not list-order semantics."""

    request = _request_with_same_target_assignments(
        left_value=1.0,
        right_value=2.0,
        reverse=reverse,
    )

    with pytest.raises(JointSimulationControllerError):
        JointSimulationHorizonController().run(request)


def test_identical_atom_assignments_are_order_invariant() -> None:
    """B20 positive control: compatible duplicate assignments preserve behavior."""

    left_first = JointSimulationHorizonController().run(
        _request_with_same_target_assignments(left_value=1.0, right_value=1.0)
    )
    right_first = JointSimulationHorizonController().run(
        _request_with_same_target_assignments(
            left_value=1.0,
            right_value=1.0,
            reverse=True,
        )
    )

    left_joint = left_first.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    right_joint = right_first.trajectory_for("joint", ("balance_grant", "income_subsidy"))
    assert left_joint.points == right_joint.points


class _ShortTrajectoryMethod:
    """Tiny registry method that exposes one point for a three-step request."""

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="short_trajectory",
        namespace="tests.sim02",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(
            {SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))}
        ),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="SIM-02 short-trajectory test method.",
        tags=frozenset({"simulation", "sim02"}),
        assumptions={
            "joint_simulation_output_shape": "time_series_trajectory",
            "joint_simulation_equilibrium_semantics": "dynamic_SCM",
        },
    )

    @staticmethod
    def pure_step(state: Any, params: Any) -> dict[str, Any]:
        del state, params
        return {
            "result": {
                "trajectory": [[10.0]],
                "final_stocks": [99.0],
            }
        }


def _short_trajectory_request(method_fqn: str) -> JointSimulationRequest:
    """Build a dynamic request whose runner returns less coverage than asked."""
    request = _request()
    return request.model_copy(
        update={
            "selected_outcomes": ("stock0",),
            "baseline_state": {"stock0": 10.0},
            "horizon": HorizonSpec(start=0, end=2, step=1),
            "engine_plan": (
                EnginePlan(
                    engine_kind="method_registry_estimator",
                    objective_ref="objective://sim02-short-trajectory",
                    method_fqn=method_fqn,
                    variable_map={"stock0": "stock:0"},
                    coupled_state={"queue_length": 0.0},
                ),
            ),
        }
    )


def test_short_trajectory_is_not_silently_extended_by_final_value() -> None:
    """B22: uncovered horizon steps remain partial or fail closed, never hold-last."""

    registry = MethodRegistry._create_fresh()
    method_fqn = registry.register(_ShortTrajectoryMethod)

    with pytest.raises(JointSimulationControllerError):
        JointSimulationHorizonController(method_registry=registry).run(
            _short_trajectory_request(method_fqn)
        )
