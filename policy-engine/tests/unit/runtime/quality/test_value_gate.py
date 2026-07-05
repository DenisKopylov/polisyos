from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.contracts.value_outer_set import DataTrust, ValueOuterSet
from polisyos.foundry.methods.causal import PanelObservationalData
from polisyos.foundry.methods.selection import (
    reachable_value_method_fqns,
    select_value_method_for_problem,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.transportability import SelectionDiagram
from polisyos.runtime.quality.design_axes.outcome_prediction import (
    build_forecast_calibration_record,
    build_forecast_support,
)
from polisyos.runtime.quality.generation_cycle import (
    FoundryValuePort,
    SimulationPortObservation,
    ValueGateReceipt,
)
from polisyos.runtime.quality.world_model_record import WorldModelRecord

from .test_design_axes_outcome_prediction import (
    _calibration_payload,
    _forecast_support_payload,
)
from .test_generation_cycle import _Atom, _Candidate, _problem


def _hash(char: str) -> str:
    return "sha256:" + char * 64


def _world_record(char: str = "1") -> WorldModelRecord:
    return WorldModelRecord.model_construct(
        world_model_record_id=f"world_model_record_{char * 16}",
        content_hash=_hash(char),
        valid_time_scope="2026",
        producer_ref="tests.unit.runtime.quality.test_value_gate",
    )


def _candidate() -> _Candidate:
    return _Candidate(
        candidate_id="candidate_value_gate",
        atom=_Atom("candidate_value_gate", _hash("2")),
        diversity_key=("grant", "firms", "panel", "value_gate"),
    )


def _simulation(world: WorldModelRecord) -> SimulationPortObservation:
    return SimulationPortObservation(
        candidate_id="candidate_value_gate",
        status="joint_simulated",
        simulation_ref=_hash("3"),
        k_world_ref_before=world.content_hash,
        k_world_ref_after=world.content_hash,
    )


def _panel() -> PanelObservationalData:
    return PanelObservationalData(
        outcome=np.array(
            [
                [10.0, 11.0, 12.0, 13.0, 18.0, 19.0, 20.0, 21.0],
                [8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0],
                [9.0, 9.0, 10.0, 10.0, 10.0, 11.0, 11.0, 12.0],
            ]
        ),
        treatment=np.array([1, 0, 0]),
        time_treatment=4,
    )


def _selection_diagram() -> SelectionDiagram:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    return SelectionDiagram(
        base_graph=graph,
        s_nodes=[],
        source_context=ContextProfile(context_id="source"),
        target_context=ContextProfile(context_id="target"),
    )


def _forecast_support(**overrides: object):
    return build_forecast_support(**_forecast_support_payload(**overrides))


def _calibration_record(**overrides: object):
    return build_forecast_calibration_record(**_calibration_payload(**overrides))


def _value_inputs(world: WorldModelRecord, **overrides: object) -> dict[str, object]:
    inputs: dict[str, object] = {
        "evaluation_mode": "simulate_only",
        "world_model_record": world,
        "forecast_support": _forecast_support(),
        "forecast_calibration_record": _calibration_record(),
        "policy_context_ref": "policy-context://ua-msme/2022",
        "method_state": _panel(),
        "method_fqn": "causal.inference.synthetic_control@1.0.0",
        "selection_diagram": _selection_diagram(),
        "query_treatment": "X",
        "query_outcome": "Y",
    }
    inputs.update(overrides)
    return inputs


def _unit_value_set(
    *,
    lower: tuple[float, ...],
    upper: tuple[float, ...],
    identification_mode: str,
) -> ValueOuterSet:
    return ValueOuterSet.interval_box(
        coordinates=("firm_survival",),
        lower=lower,
        upper=upper,
        identification_mode=identification_mode,
        assumptions=("unit_test",),
        assumption_status="externally_supported",
        calibration_scope={"scope": "unit"},
        data_trust=DataTrust(
            tier="unit",
            trust_cap=1.0,
            trust_multiplier=1.0,
            authority_ref="test",
        ),
        world_model_record_ref=_hash("1"),
        epoch="2026",
        representation_status="certified",
    )


def _problem_with_value_inputs(inputs: dict[str, object]):
    return _problem("value_gate_problem").model_copy(
        update={"runtime_hints": {"value_gate_inputs": inputs}}
    )


def test_hand_set_value_outer_set_width_is_rejected() -> None:
    value_set = _unit_value_set(lower=(1.0,), upper=(1.0,), identification_mode="point")
    payload = value_set.model_dump(mode="json")

    with pytest.raises(ValueError, match="value_outer_set_width_supplied_not_derived"):
        ValueOuterSet.model_validate(payload)


def test_foundry_value_port_mints_value_over_named_world_record() -> None:
    world = _world_record()
    observation = FoundryValuePort()(
        candidate=_candidate(),
        simulation=_simulation(world),
        problem=_problem_with_value_inputs(_value_inputs(world)),
        cycle_index=0,
    )

    assert observation.status == "value_ready"
    assert observation.selected_method_fqn == "causal.inference.synthetic_control@1.0.0"
    assert observation.identification_status == "point"
    assert observation.value_receipt is not None
    assert observation.value_receipt.world_model_record_content_hash == world.content_hash
    assert observation.value_receipt.transport_receipt.world_model_record_content_hash == (
        world.content_hash
    )
    assert observation.value_receipt.value_outer_set.width == (0.0,)
    assert observation.value_receipt.k_world_ref_before == world.content_hash
    assert observation.value_receipt.k_world_ref_after == world.content_hash


def test_value_port_reuses_cached_world_model_record() -> None:
    world = _world_record()
    inputs = _value_inputs(world)
    problem = _problem_with_value_inputs(inputs)
    port = FoundryValuePort()

    first_record, first_status, first_error = port._world_record(problem, inputs=inputs)
    second_record, second_status, second_error = port._world_record(problem, inputs=inputs)

    assert first_record is world
    assert second_record is first_record
    assert first_status == "built"
    assert second_status == "reused"
    assert first_error is None
    assert second_error is None


def test_value_receipt_rejects_world_version_laundering() -> None:
    world = _world_record("1")
    observation = FoundryValuePort()(
        candidate=_candidate(),
        simulation=_simulation(world),
        problem=_problem_with_value_inputs(_value_inputs(world)),
        cycle_index=0,
    )
    assert observation.value_receipt is not None

    payload = observation.value_receipt.model_dump(mode="python")
    payload["value_outer_set"] = observation.value_receipt.value_outer_set
    payload["transport_receipt"] = observation.value_receipt.transport_receipt
    payload["calibration_receipt"] = observation.value_receipt.calibration_receipt
    payload["world_model_record_content_hash"] = _hash("4")
    with pytest.raises(ValueError, match="value_world_version_laundered"):
        ValueGateReceipt.model_validate(payload)


def test_dominance_timeout_returns_unknown() -> None:
    left = _unit_value_set(lower=(3.0,), upper=(4.0,), identification_mode="partial")
    right = _unit_value_set(lower=(1.0,), upper=(2.0,), identification_mode="partial")

    assert left.compare(right) == "dominates"
    assert left.compare(right, force_timeout=True) == "unknown"


def test_simulate_only_receipt_cannot_shrink_k_world() -> None:
    world = _world_record()
    observation = FoundryValuePort()(
        candidate=_candidate(),
        simulation=_simulation(world),
        problem=_problem_with_value_inputs(_value_inputs(world)),
        cycle_index=0,
    )
    assert observation.value_receipt is not None

    payload = observation.value_receipt.model_dump(mode="python")
    payload["value_outer_set"] = observation.value_receipt.value_outer_set
    payload["transport_receipt"] = observation.value_receipt.transport_receipt
    payload["calibration_receipt"] = observation.value_receipt.calibration_receipt
    payload["k_world_ref_after"] = _hash("5")
    with pytest.raises(ValueError, match="simulate_only_shrank_k_world"):
        ValueGateReceipt.model_validate(payload)


@pytest.mark.parametrize(
    ("case_name", "blocker"),
    [
        (
            "uncalibrated",
            "uncalibrated_forecast_minted_value",
        ),
        (
            "unsupported",
            "unsupported_method_unavailable",
        ),
        (
            "regime_laundered",
            "regime_laundered_forecast_minted_value",
        ),
        (
            "untransportable",
            "untransportable_forecast_minted_value",
        ),
    ],
)
def test_bad_forecasts_and_unavailable_methods_fail_closed(
    case_name: str,
    blocker: str,
) -> None:
    world = _world_record()
    case_inputs: dict[str, object]
    if case_name == "uncalibrated":
        case_inputs = {
            "forecast_support": _forecast_support(
                s5_base_origin="simulation_only",
                s5_support_label="simulation_only_system_effect",
                forecast_tier="simulation_only_advisory",
                calibration_record_ref=None,
            )
        }
    elif case_name == "unsupported":
        case_inputs = {"method_fqn": "causal.inference.no_such_method@9.9.9"}
    elif case_name == "regime_laundered":
        case_inputs = {"policy_context_ref": "policy-context://other-regime"}
    else:
        case_inputs = {"selection_diagram": {"invalid": "selection-diagram"}}
    observation = FoundryValuePort()(
        candidate=_candidate(),
        simulation=_simulation(world),
        problem=_problem_with_value_inputs(_value_inputs(world, **case_inputs)),
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.value_receipt is None
    assert observation.authority_blockers[0].startswith(blocker)


@pytest.mark.parametrize(
    "mode",
    ["sandbox_pilot", "field_pilot", "deployment"],
)
def test_pilot_and_deployment_modes_block_pending_eval_safety(mode: str) -> None:
    world = _world_record()
    observation = FoundryValuePort()(
        candidate=_candidate(),
        simulation=_simulation(world),
        problem=_problem_with_value_inputs(_value_inputs(world, evaluation_mode=mode)),
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("eval_safety_gate_unavailable",)


def test_candidate_problem_selection_uses_registry_denominator() -> None:
    denominator = reachable_value_method_fqns()
    selection = select_value_method_for_problem(
        candidate={
            "candidate_id": "candidate_panel_value",
            "atom": {"target_world_slots": ("panel", "firm_survival")},
        },
        problem={
            "design_problem_id": "value_selection_problem",
            "runtime_hints": {
                "value_method_hint": "panel",
                "value_required_data_modalities": ("panel",),
            },
        },
    )

    assert len(denominator) > 1
    assert selection["status"] == "selected"
    assert selection["selection_source"] == "foundry_registry_advisor"
    assert selection["selected_method_fqn"] in denominator
