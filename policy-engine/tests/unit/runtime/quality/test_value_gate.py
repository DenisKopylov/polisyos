from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.contracts.value_outer_set import DataTrust, ValueOuterSet
from polisyos.foundry.methods.selection import (
    reachable_value_method_fqns,
    select_value_method_for_problem,
)
from polisyos.runtime.quality.design_problem import OutcomeOfInterest
from polisyos.runtime.quality.generation_cycle import (
    FoundryValuePort,
    JointSimulationPort,
    RealValueOwnerGateway,
    SimulationPortObservation,
    ValueCalibrationReceipt,
    ValueGateReceipt,
    ValueTransportReceipt,
    _build_default_selection_diagram,
    _build_s10_forecast_inputs,
    _candidate_transport_outcome_variable,
    _candidate_transport_treatment_variable,
    _s10_calibration_evidence_from_report,
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


@dataclass(frozen=True)
class _TreatmentAtom:
    intervention_id: str
    content_hash: str
    status: str = "candidate_unverified"
    world_model_record_ref: str = "world_model_record_test"
    target_world_slots: tuple[str, ...] = ("avg_income",)
    treated_unit_ids: tuple[str, ...] = ("AM",)
    treatment_period: int = 2020


def _avg_income_problem() -> Any:
    return _problem("value_gate_avg_income_problem").model_copy(
        update={
            "outcome_of_interest": OutcomeOfInterest(
                target_variable="avg_income",
                metric_id="avg_income",
                estimand="average_treatment_effect",
            )
        }
    )


def _avg_income_candidate() -> _Candidate:
    return _Candidate(
        candidate_id="candidate_avg_income_real",
        atom=_TreatmentAtom("candidate_avg_income_real", _hash("8")),
        diversity_key=("grant", "country", "avg_income", "real_panel"),
    )


@dataclass(frozen=True)
class _AdversarialRealPanelGateway:
    forecast_tier: str = "observable_calibrated"
    calibration_status: str | None = "pass"
    expected_policy_context_ref: str | None = None
    selection_diagram: object | None = None

    def load_panel_observational_data(
        self,
        *,
        candidate: object,
        problem: Any,
        world_record: WorldModelRecord,
    ) -> object:
        return RealValueOwnerGateway(repo_root=Path.cwd()).load_panel_observational_data(
            candidate=candidate,
            problem=problem,
            world_record=world_record,
        )

    def produce_forecast_inputs(
        self,
        *,
        candidate: object,
        problem: Any,
        world_record: WorldModelRecord,
        method_result: object,
        selected_method_fqn: str,
    ) -> dict[str, Any]:
        policy_context_ref = f"policy-context://{world_record.world_model_record_id}"
        evidence = _s10_calibration_evidence_from_report(method_result.output.get("report"))
        if self.calibration_status not in {None, "pass"}:
            evidence = {
                **evidence,
                "calibration_status": self.calibration_status,
                "numerator": 0,
                "pass_rate": 0.0,
                "floor_passed": False,
            }
        return dict(
            _build_s10_forecast_inputs(
                candidate=candidate,
                problem=problem,
                world_record=world_record,
                method_result=method_result,
                selected_method_fqn=selected_method_fqn,
                forecast_tier=self.forecast_tier,
                calibration_status=self.calibration_status,
                policy_context_ref=policy_context_ref,
                expected_policy_context_ref=(
                    self.expected_policy_context_ref or policy_context_ref
                ),
                false_clear_counts=evidence["false_clear_counts"],
                calibration_evidence=evidence,
            )
        )

    def build_transport_inputs(
        self,
        *,
        candidate: object,
        problem: Any,
        world_record: WorldModelRecord,
    ) -> dict[str, Any]:
        query_treatment = _candidate_transport_treatment_variable(candidate)
        query_outcome = _candidate_transport_outcome_variable(candidate, problem)
        return {
            "selection_diagram": self.selection_diagram
            if self.selection_diagram is not None
            else _build_default_selection_diagram(
                candidate=candidate,
                problem=problem,
                world_record=world_record,
            ),
            "query_treatment": query_treatment,
            "query_outcome": query_outcome,
        }


def _simulation(world: WorldModelRecord) -> SimulationPortObservation:
    return SimulationPortObservation(
        candidate_id="candidate_value_gate",
        status="joint_simulated",
        simulation_ref=_hash("3"),
        k_world_ref_before=world.content_hash,
        k_world_ref_after=world.content_hash,
        world_model_record=world,
    )


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


def _receipt(world: WorldModelRecord) -> ValueGateReceipt:
    value_set = ValueOuterSet.interval_box(
        coordinates=("difference_in_differences",),
        lower=(1.25,),
        upper=(1.25,),
        identification_mode="point",
        assumptions=("unit_test_receipt",),
        assumption_status="externally_supported",
        calibration_scope={"scope": "unit"},
        data_trust=DataTrust(
            tier="unit",
            trust_cap=1.0,
            trust_multiplier=1.0,
            authority_ref="test",
        ),
        world_model_record_ref=world.content_hash,
        epoch="2026",
        representation_status="certified",
    )
    transport = ValueTransportReceipt(
        status="direct",
        world_model_record_id=world.world_model_record_id,
        world_model_record_content_hash=world.content_hash,
        transport_result_ref=_hash("9"),
        transport_status="identified",
        transport_mode="direct",
        identification_engine="unit",
    )
    calibration = ValueCalibrationReceipt(
        status="pass",
        forecast_tier="observable_calibrated",
        calibration_record_ref="s10://unit",
    )
    value_ref = _hash("a")
    return ValueGateReceipt(
        candidate_id="candidate_value_gate",
        evaluation_mode="simulate_only",
        selected_method_fqn="causal.inference.did.standard@1.0.0",
        method_selection_trace=("causal.inference.did.standard@1.0.0",),
        identification_status=value_set.identification_status,
        value_outer_set=value_set,
        transport_receipt=transport,
        calibration_receipt=calibration,
        world_model_record_id=world.world_model_record_id,
        world_model_record_content_hash=world.content_hash,
        value_ref=value_ref,
        wall_time_ms=1.0,
        wmr_cache_status="built",
        k_world_ref_before=world.content_hash,
        k_world_ref_after=world.content_hash,
    )


def test_hand_set_value_outer_set_width_is_rejected() -> None:
    value_set = _unit_value_set(lower=(1.0,), upper=(1.0,), identification_mode="point")
    payload = value_set.model_dump(mode="json")

    with pytest.raises(ValueError, match="value_outer_set_width_supplied_not_derived"):
        ValueOuterSet.model_validate(payload)


def test_empty_hints_cycle_reaches_value_gate_with_real_boundary_wmr() -> None:
    problem = _avg_income_problem()
    assert problem.runtime_hints == {}
    candidate = _avg_income_candidate()

    simulation = JointSimulationPort(repo_root=Path.cwd())(
        candidate=candidate,
        problem=problem,
        cycle_index=0,
    )
    observation = FoundryValuePort(repo_root=Path.cwd())(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )

    assert simulation.world_model_record is not None
    assert simulation.diagnostics["world_model_source"] == "real_substrate_registry_boundary"
    assert observation.status == "value_ready"
    assert observation.world_model_record_content_hash == simulation.world_model_record.content_hash
    assert observation.selected_method_fqn == "causal.inference.did.standard@1.0.0"
    assert observation.authority_blockers == ()
    assert observation.calibration_receipt is not None
    assert observation.calibration_receipt.status == "pass"
    assert observation.transport_receipt is not None
    assert observation.transport_receipt.status == "transported_limited"
    assert observation.transport_receipt.world_model_record_content_hash == (
        simulation.world_model_record.content_hash
    )
    assert observation.value_receipt is not None
    assert observation.identification_status == "partial"
    assert observation.value_receipt.value_outer_set.lower == (-6016.810766126787,)
    assert observation.value_receipt.value_outer_set.upper == (4094.3096004508484,)
    assert observation.value_receipt.value_outer_set.width == (10111.120366577636,)


def test_candidate_treatment_is_loaded_from_candidate_binding() -> None:
    problem = _avg_income_problem()
    candidate = _avg_income_candidate()
    world = _world_record()

    panel = RealValueOwnerGateway(repo_root=Path.cwd()).load_panel_observational_data(
        candidate=candidate,
        problem=problem,
        world_record=world,
    )

    assert panel.outcome.shape == (16, 4)
    assert panel.treatment.tolist() == [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    assert panel.time_treatment == 2


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
        owner_gateway=RealValueOwnerGateway(repo_root=Path.cwd()),
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
    receipt = _receipt(world)

    payload = receipt.model_dump(mode="python")
    payload["value_outer_set"] = receipt.value_outer_set
    payload["transport_receipt"] = receipt.transport_receipt
    payload["calibration_receipt"] = receipt.calibration_receipt
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
    receipt = _receipt(world)

    payload = receipt.model_dump(mode="python")
    payload["value_outer_set"] = receipt.value_outer_set
    payload["transport_receipt"] = receipt.transport_receipt
    payload["calibration_receipt"] = receipt.calibration_receipt
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
    owner = _AdversarialRealPanelGateway()
    requested_method_fqn = "causal.inference.did.standard@1.0.0"
    if case_name == "uncalibrated":
        owner = _AdversarialRealPanelGateway(
            forecast_tier="simulation_only_advisory",
            calibration_status=None,
        )
    elif case_name == "unsupported":
        requested_method_fqn = "causal.inference.no_such_method@9.9.9"
    elif case_name == "regime_laundered":
        owner = _AdversarialRealPanelGateway(
            expected_policy_context_ref="policy-context://other-regime"
        )
    else:
        owner = _AdversarialRealPanelGateway(selection_diagram={"invalid": "selection-diagram"})
    observation = FoundryValuePort(
        owner_gateway=owner,
        requested_method_fqn=requested_method_fqn,
    )(
        candidate=_avg_income_candidate(),
        simulation=_simulation(world),
        problem=_avg_income_problem(),
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
        owner_gateway=RealValueOwnerGateway(repo_root=Path.cwd()),
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
