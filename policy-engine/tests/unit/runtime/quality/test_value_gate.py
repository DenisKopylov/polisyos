from __future__ import annotations

from pathlib import Path
from typing import Any

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
from polisyos.runtime.quality.generation_cycle import (
    FoundryValuePort,
    RealValueOwnerGateway,
    RecordedValueOwnerGateway,
    SimulationPortObservation,
    ValueGateReceipt,
)
from polisyos.runtime.quality.world_model_record import (
    BranchMode,
    DataForgeBindingRef,
    FabricWorldRef,
    FoundryBindingRef,
    PolicySlotBinding,
    ResolvedSubstrateEntryRef,
    SimulationModelRef,
    SkgCausalPriorRef,
    SubstrateRegistryRef,
    WorldModelRecord,
    world_model_record_content_hash,
)

from .test_generation_cycle import _Atom, _Candidate, _problem


def _hash(char: str) -> str:
    return "sha256:" + char * 64


def _world_record(char: str = "1") -> WorldModelRecord:
    fields: dict[str, Any] = {
        "schema_version": "policyos.runtime.world_model_record.v1",
        "authority_status": "bound",
        "producer_ref": f"tests.unit.runtime.quality.test_value_gate.{char}",
        "region_or_jurisdiction": "UA-30",
        "population_scope": "wartime_msme",
        "policy_domain": "fiscal_credit",
        "valid_time_scope": "2026-05-24/2026-12-31",
        "tx_time_scope": "2026-05-24T12:00:00+00:00",
        "resolution": "firm_month",
        "branch_mode": BranchMode.OBSERVED,
        "fabric_world_ref": FabricWorldRef(
            snapshot_root="/tmp/policyos-value-gate-world",
            snapshot_id=f"snapshot-2026-05-24-{char}",
            branch="main",
            world_query_policy="as_of_valid_and_tx_time",
            provenance_manifest_ref=f"manifest://value-gate/{char}",
            content_query_digest=_hash(char),
            content_query_row_count=3,
        ),
        "data_forge_binding_ref": DataForgeBindingRef(
            snapshot_id=f"snapshot-2026-05-24-{char}",
            release_id=f"release-{char}",
            role="academic",
            read_api_identity="data_forge.read_api.value_gate",
            snapshot_ref=f"snapshot://data-forge/value-gate/{char}",
            merkle_root=f"merkle:value-gate:{char}",
            data_hash=_hash("a"),
            provenance_manifest_ref=f"manifest://data-forge/value-gate/{char}",
        ),
        "simulation_model_ref": SimulationModelRef(
            model_spec_ref=_hash("b"),
            model_spec_hash=_hash("c"),
            model_id="model_ua_msme_value_gate",
            data_snapshot_ref=_hash("d"),
            registry_bundle_ref=_hash("e"),
            ncm_refs=("ncm://fixture/value-gate",),
            fidelity_level="high",
            calibrated=True,
            calibration_ref=_hash("f"),
        ),
        "foundry_binding_ref": FoundryBindingRef(
            input_bindings_ref=_hash("0"),
            bound_state_snapshot_ref=_hash("2"),
            mapping_rules_ref=_hash("3"),
            state_slot_digest=_hash("4"),
        ),
        "skg_causal_prior_ref": SkgCausalPriorRef(
            skg_snapshot_ref=f"skg://value-gate/{char}",
            skg_version_id=f"skg-v{char}",
            source_data_snapshot_id=f"snapshot-2026-05-24-{char}",
        ),
        "substrate_registry_ref": SubstrateRegistryRef(
            substrate_version_id="substrate_version_1111111111111111",
            content_hash=_hash("5"),
            resolved_entries=(
                ResolvedSubstrateEntryRef(
                    source_id="l5_measurement_registry",
                    family_id="firm_fundamentals",
                    layer="L5",
                    coverage_score=0.8,
                    trust_tier="authoritative_partial_coverage",
                    trust_cap=0.85,
                    identification_mode="point_identified",
                    schema_regime_id="ukraine_schema_v2",
                    data_version="l5-calibration-d2",
                    snapshot_id=f"snapshot-2026-05-24-{char}",
                    source_snapshot_id=f"snapshot-2026-05-24-{char}",
                    entry_content_hash=_hash("6"),
                ),
            ),
        ),
        "policy_slot_map": (
            PolicySlotBinding(
                slot_id="firm_survival",
                state_path="firms.survival",
                entity_scope="firm",
                temporal_granularity="month",
            ),
            PolicySlotBinding(
                slot_id="government_balance",
                state_path="government.balance",
                entity_scope="government",
                temporal_granularity="month",
            ),
        ),
    }
    candidate = WorldModelRecord.model_construct(
        world_model_record_id="world_model_record_0000000000000000",
        content_hash=_hash("0"),
        **fields,
    )
    content_hash = world_model_record_content_hash(candidate)
    return WorldModelRecord(
        world_model_record_id=f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **fields,
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
        world_model_record=world,
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


def _recorded_owner(**overrides: object) -> RecordedValueOwnerGateway:
    payload: dict[str, object] = {
        "method_state": _panel(),
        "selection_diagram": _selection_diagram(),
        "policy_context_ref": "policy-context://layer3/gy/n8",
        "expected_policy_context_ref": "policy-context://layer3/gy/n8",
    }
    payload.update(overrides)
    return RecordedValueOwnerGateway(**payload)  # type: ignore[arg-type]


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


def test_hand_set_value_outer_set_width_is_rejected() -> None:
    value_set = _unit_value_set(lower=(1.0,), upper=(1.0,), identification_mode="point")
    payload = value_set.model_dump(mode="json")

    with pytest.raises(ValueError, match="value_outer_set_width_supplied_not_derived"):
        ValueOuterSet.model_validate(payload)


def test_production_value_port_without_value_gate_hints_mints_value() -> None:
    world = _world_record()
    problem = _problem("value_gate_problem")
    assert problem.runtime_hints == {}

    observation = FoundryValuePort(
        owner_gateway=_recorded_owner(),
        requested_method_fqn="causal.inference.synthetic_control@1.0.0",
    )(
        candidate=_candidate(),
        simulation=_simulation(world),
        problem=problem,
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


def test_production_value_block_is_real_data_gap_not_missing_inputs() -> None:
    world = _world_record()
    problem = _problem("value_gate_problem")

    observation = FoundryValuePort(
        owner_gateway=RealValueOwnerGateway(repo_root=Path.cwd()),
        requested_method_fqn="causal.inference.synthetic_control@1.0.0",
    )(
        candidate=_candidate(),
        simulation=_simulation(world),
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.value_receipt is None
    assert observation.authority_blockers == ("acquire_data:value_panel_data_missing",)
    assert "substrate owner" in str(observation.reason)
    assert "dataset_catalog.duckdb#variable/firm_survival" in str(observation.reason)
    assert "value_method_state_missing" not in observation.authority_blockers
    assert "world_model_record_missing" not in observation.authority_blockers


def test_missing_cycle_wmr_is_wiring_error_not_acquire_gap() -> None:
    world = _world_record()
    simulation = _simulation(world).model_copy(update={"world_model_record": None})

    observation = FoundryValuePort(
        owner_gateway=_recorded_owner(),
        requested_method_fqn="causal.inference.synthetic_control@1.0.0",
    )(
        candidate=_candidate(),
        simulation=simulation,
        problem=_problem("value_gate_problem"),
        cycle_index=0,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("value_world_model_record_unwired",)
    assert not observation.authority_blockers[0].startswith("acquire_data:")


def test_value_port_reuses_cached_world_model_record() -> None:
    world = _world_record()
    port = FoundryValuePort()

    first_record, first_status, first_error = port._world_record_from_simulation(
        _simulation(world)
    )
    second_record, second_status, second_error = port._world_record_from_simulation(
        _simulation(world)
    )

    assert first_record is world
    assert second_record is first_record
    assert first_status == "built"
    assert second_status == "reused"
    assert first_error is None
    assert second_error is None


def test_value_receipt_rejects_world_version_laundering() -> None:
    world = _world_record("1")
    observation = FoundryValuePort(
        owner_gateway=_recorded_owner(),
        requested_method_fqn="causal.inference.synthetic_control@1.0.0",
    )(
        candidate=_candidate(),
        simulation=_simulation(world),
        problem=_problem("value_gate_problem"),
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
    observation = FoundryValuePort(
        owner_gateway=_recorded_owner(),
        requested_method_fqn="causal.inference.synthetic_control@1.0.0",
    )(
        candidate=_candidate(),
        simulation=_simulation(world),
        problem=_problem("value_gate_problem"),
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
    owner_overrides: dict[str, object] = {}
    requested_method_fqn = "causal.inference.synthetic_control@1.0.0"
    if case_name == "uncalibrated":
        owner_overrides = {
            "forecast_tier": "simulation_only_advisory",
            "calibration_status": None,
        }
    elif case_name == "unsupported":
        requested_method_fqn = "causal.inference.no_such_method@9.9.9"
    elif case_name == "regime_laundered":
        owner_overrides = {
            "expected_policy_context_ref": "policy-context://other-regime"
        }
    else:
        owner_overrides = {"selection_diagram": {"invalid": "selection-diagram"}}
    observation = FoundryValuePort(
        owner_gateway=_recorded_owner(**owner_overrides),
        requested_method_fqn=requested_method_fqn,
    )(
        candidate=_candidate(),
        simulation=_simulation(world),
        problem=_problem("value_gate_problem"),
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
    observation = FoundryValuePort(
        owner_gateway=_recorded_owner(),
        evaluation_mode=mode,  # type: ignore[arg-type]
        requested_method_fqn="causal.inference.synthetic_control@1.0.0",
    )(
        candidate=_candidate(),
        simulation=_simulation(world),
        problem=_problem("value_gate_problem"),
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
