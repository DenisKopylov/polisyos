"""Gap-coverage tests for RunSimulationNode."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from polisyos.ir.analytics.simulation_proof_bridge import load_simulation_proof_bridge
from polisyos.ir.analytics.strategic import (
    FiniteStrategicPayoffTable,
    StrategicSCM,
    load_strategic_response_bundle,
    persist_strategic_payoff_table,
)
from polisyos.ir.registry.refs import ArtifactRefModel, SimulationProofBridgeRef, StrategicResponseBundleRef
from polisyos.scientist.orchestration.kernel.budgets import ComputeBudget
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.simulate.run_simulation import _SPEC, RunSimulationNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_EVIDENCE_BUNDLE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_EXEC_PLAN_REF,
    ARTIFACT_PROOF_BUNDLE_REF,
    ARTIFACT_SIMULATION_CALIBRATION_RECEIPT_REF,
    ARTIFACT_SIMULATION_PROOF_BRIDGE_REF,
    ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
    ARTIFACT_STRATEGIC_SCM_REF,
    INPUT_INPUT_BINDINGS_REF,
)


def test_fail_when_foundry_port_missing(execution_context, minimal_state, artifact_ref_factory):
    """ctx.foundry is None -> fail with ERROR_FOUNDATION_MISSING."""
    ref = artifact_ref_factory(kind="foundry.exec_plan")
    bindings_ref = artifact_ref_factory(kind="foundry.input_bindings")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = ref
    state.inputs[INPUT_INPUT_BINDINGS_REF] = bindings_ref

    # execution_context has foundry=None by default
    outcome = RunSimulationNode().execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_FOUNDATION_MISSING


def test_run_simulation_spec_reads_performative_loop_spec() -> None:
    assert "params.performative_loop_spec" in _SPEC.state_reads


def test_run_simulation_accepts_injected_metrics(
    execution_context,
    minimal_state,
    artifact_ref_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    class _MetricsStub:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def record_slo_simulation_run(self, status: str, *, method: str) -> None:
            self.calls.append((status, method))

    metrics = _MetricsStub()
    ctx = replace(execution_context, foundry=None, metrics=metrics)
    ref = artifact_ref_factory(kind="foundry.exec_plan")
    bindings_ref = artifact_ref_factory(kind="foundry.input_bindings")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = ref
    state.inputs[INPUT_INPUT_BINDINGS_REF] = bindings_ref

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_simulation._default_metrics",
        lambda: (_ for _ in ()).throw(
            AssertionError("global metrics lookup should not run when metrics are injected")
        ),
    )

    outcome = RunSimulationNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert metrics.calls == [("error", "foundry.execute")]


def test_fail_when_exec_plan_ref_missing(execution_context, minimal_state, artifact_ref_factory):
    """No exec_plan_ref in artifacts_index -> fail with ERROR_MISSING_INPUT."""
    ctx = replace(execution_context, foundry=MagicMock())
    bindings_ref = artifact_ref_factory(kind="foundry.input_bindings")
    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_INPUT_BINDINGS_REF] = bindings_ref

    outcome = RunSimulationNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_MISSING_INPUT
    assert "exec_plan_ref" in outcome.error.message


def test_fail_when_input_bindings_missing(execution_context, minimal_state, artifact_ref_factory):
    """Has exec_plan but no input_bindings_ref -> fail with ERROR_MISSING_INPUT."""
    ctx = replace(execution_context, foundry=MagicMock())
    ref = artifact_ref_factory(kind="foundry.exec_plan")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = ref

    outcome = RunSimulationNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_MISSING_INPUT
    assert "input_bindings_ref" in outcome.error.message


def test_fail_when_foundry_execute_returns_not_ok(
    execution_context, minimal_state, artifact_ref_factory
):
    """When foundry.execute returns ok=False, node returns fail with ERROR_FOUNDRY_EXECUTE_FAILED."""
    mock_foundry = MagicMock()
    mock_result = MagicMock()
    mock_result.ok = False
    mock_result.simulation_result_ref = None
    mock_result.derived_refs = []
    mock_result.notes = ["simulation diverged"]
    mock_foundry.execute.return_value = mock_result

    ctx = replace(execution_context, foundry=mock_foundry)
    ref = artifact_ref_factory(kind="foundry.exec_plan")
    bindings_ref = artifact_ref_factory(kind="foundry.input_bindings")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = ref
    state.inputs[INPUT_INPUT_BINDINGS_REF] = bindings_ref

    outcome = RunSimulationNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_FOUNDRY_EXECUTE_FAILED


def test_ok_when_foundry_execute_succeeds(execution_context, minimal_state, artifact_ref_factory):
    """When foundry.execute returns ok=True, node returns ok."""
    mock_foundry = MagicMock()
    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.simulation_result_ref = artifact_ref_factory(kind="foundry.simulation_result")
    mock_result.derived_refs = []
    mock_result.notes = []
    mock_foundry.execute.return_value = mock_result

    ctx = replace(execution_context, foundry=mock_foundry)
    ref = artifact_ref_factory(kind="foundry.exec_plan")
    bindings_ref = artifact_ref_factory(kind="foundry.input_bindings")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = ref
    state.inputs[INPUT_INPUT_BINDINGS_REF] = bindings_ref

    outcome = RunSimulationNode().execute(ctx, state)
    assert outcome.status == "ok"


def test_run_simulation_calls_phase4_gate_for_long_temporal_queries(
    execution_context,
    minimal_state,
    artifact_ref_factory,
) -> None:
    mock_foundry = MagicMock()
    ctx = replace(execution_context, foundry=mock_foundry)
    ref = artifact_ref_factory(kind="foundry.exec_plan")
    bindings_ref = artifact_ref_factory(kind="foundry.input_bindings")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = ref
    state.inputs[INPUT_INPUT_BINDINGS_REF] = bindings_ref
    state.params["simulation_horizon"] = 13

    outcome = RunSimulationNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "phase4_regime_gate_failed"
    assert outcome.error.details["horizon"] == 13
    mock_foundry.execute.assert_not_called()


def test_run_simulation_allows_long_temporal_queries_with_calibrated_regime_bundle(
    execution_context,
    minimal_state,
    artifact_ref_factory,
) -> None:
    mock_foundry = MagicMock()
    mock_foundry.execute.return_value = SimpleNamespace(
        ok=True,
        simulation_result_ref=None,
        derived_refs=[],
        notes=[],
    )
    ctx = replace(execution_context, foundry=mock_foundry)
    ref = artifact_ref_factory(kind="foundry.exec_plan")
    bindings_ref = artifact_ref_factory(kind="foundry.input_bindings")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = ref
    state.inputs[INPUT_INPUT_BINDINGS_REF] = bindings_ref
    state.params["simulation_horizon"] = 13
    state.params["regime_shift_forecast_bundle"] = {"regime_status": "calibrated"}

    outcome = RunSimulationNode().execute(ctx, state)

    assert outcome.status == "ok"
    mock_foundry.execute.assert_called_once()


def test_run_simulation_materializes_proof_bridge_for_simulation_result(
    execution_context,
    minimal_state,
    artifact_ref_factory,
):
    exec_plan_ref = artifact_ref_factory(kind="foundry.exec_plan")
    input_bindings_ref = artifact_ref_factory(kind="foundry.input_bindings")
    metrics_ref = artifact_ref_factory(
        kind="foundry.metrics",
        data={"values": {"policy_value": "1.0"}, "notes": []},
    )
    simulation_ref = artifact_ref_factory(
        kind="foundry.simulation_result",
        data={
            "schema_version": "1.3",
            "exec_plan_ref": exec_plan_ref.model_dump(mode="json"),
            "metrics_ref": metrics_ref.model_dump(mode="json"),
            "notes": [],
        },
    )
    mock_foundry = MagicMock()
    mock_foundry.execute.return_value = SimpleNamespace(
        ok=True,
        simulation_result_ref=simulation_ref,
        derived_refs=[SimpleNamespace(role="metrics", ref=metrics_ref)],
        notes=[],
    )

    ctx = replace(execution_context, foundry=mock_foundry)
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = exec_plan_ref
    state.inputs[INPUT_INPUT_BINDINGS_REF] = input_bindings_ref

    outcome = RunSimulationNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_SIMULATION_PROOF_BRIDGE_REF in outcome.state.artifacts_index
    assert ARTIFACT_SIMULATION_CALIBRATION_RECEIPT_REF in outcome.state.artifacts_index
    assert ARTIFACT_CAUSAL_EVIDENCE_BUNDLE_REF in outcome.state.artifacts_index
    assert ARTIFACT_PROOF_BUNDLE_REF in outcome.state.artifacts_index
    bridge = load_simulation_proof_bridge(
        ctx.store,
        SimulationProofBridgeRef.model_validate(
            outcome.state.artifacts_index[ARTIFACT_SIMULATION_PROOF_BRIDGE_REF].model_dump(
                mode="json"
            )
        ),
    )
    assert bridge.certification_status.value == "SCENARIO"
    assert str(bridge.simulation_result_ref.artifact_id) == str(simulation_ref.artifact_id)


def test_run_simulation_fails_closed_when_proof_bridge_cannot_materialize(
    execution_context,
    minimal_state,
    artifact_ref_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exec_plan_ref = artifact_ref_factory(kind="foundry.exec_plan")
    input_bindings_ref = artifact_ref_factory(kind="foundry.input_bindings")
    simulation_ref = artifact_ref_factory(kind="foundry.simulation_result")
    mock_foundry = MagicMock()
    mock_foundry.execute.return_value = SimpleNamespace(
        ok=True,
        simulation_result_ref=simulation_ref,
        derived_refs=[],
        notes=[],
    )
    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.run_simulation."
        "build_simulation_proof_bridge_artifacts",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bridge failed")),
    )

    ctx = replace(execution_context, foundry=mock_foundry)
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = exec_plan_ref
    state.inputs[INPUT_INPUT_BINDINGS_REF] = input_bindings_ref

    outcome = RunSimulationNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_SIMULATION_PROOF_BRIDGE_FAILED
    assert ARTIFACT_SIMULATION_PROOF_BRIDGE_REF not in outcome.state.artifacts_index


def test_run_simulation_persists_strategic_artifacts_when_inputs_are_valid(
    execution_context,
    minimal_state,
    artifact_ref_factory,
):
    metrics_ref = artifact_ref_factory(
        kind="foundry.metrics",
        data={"values": {"policy_value": "4.5"}, "notes": []},
    )
    mock_foundry = MagicMock()
    mock_foundry.execute.return_value = SimpleNamespace(
        ok=True,
        simulation_result_ref=None,
        derived_refs=[SimpleNamespace(role="metrics", ref=metrics_ref)],
        notes=[],
    )
    ctx = replace(execution_context, foundry=mock_foundry)

    payoff_tables = _runtime_payoff_tables()
    payoff_refs = {
        agent: persist_strategic_payoff_table(ctx.store, table)
        for agent, table in payoff_tables.items()
    }

    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = artifact_ref_factory(kind="foundry.exec_plan")
    state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF] = artifact_ref_factory(
        kind="ir.causal_effect_report"
    )
    state.inputs[INPUT_INPUT_BINDINGS_REF] = artifact_ref_factory(kind="foundry.input_bindings")
    state.params["strategic_scm"] = StrategicSCM(
        base_graph_ref=_artifact_ref_model("graph", kind="ir.causal_graph_model"),
        strategic_agents=("leader", "follower"),
        utility_refs=payoff_refs,
        policy_rule_ref=_artifact_ref_model("policy", kind="ir.policy_recommendation"),
        equilibrium_concept="stackelberg",
        compute_budget=ComputeBudget(max_llm_calls=0.0, max_sim_runs=16.0, max_wall_time_s=30.0),
    ).model_dump(mode="json")
    state.params["strategic_payoff_tables"] = {
        agent: table.model_dump(mode="json") for agent, table in payoff_tables.items()
    }

    outcome = RunSimulationNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_STRATEGIC_SCM_REF in outcome.state.artifacts_index
    assert ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF in outcome.state.artifacts_index
    assert outcome.state.params["strategic_response_source"] == "run_simulation"
    bundle = load_strategic_response_bundle(
        ctx.store,
        StrategicResponseBundleRef.model_validate(
            outcome.state.artifacts_index[ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF].model_dump(
                mode="json"
            )
        ),
    )
    assert bundle.fallback_mode.value == "exact_equilibrium"


def test_run_simulation_keeps_ok_when_strategic_inputs_are_invalid(
    execution_context,
    minimal_state,
    artifact_ref_factory,
):
    metrics_ref = artifact_ref_factory(
        kind="foundry.metrics",
        data={"values": {"policy_value": "2.0"}, "notes": []},
    )
    mock_foundry = MagicMock()
    mock_foundry.execute.return_value = SimpleNamespace(
        ok=True,
        simulation_result_ref=None,
        derived_refs=[SimpleNamespace(role="metrics", ref=metrics_ref)],
        notes=[],
    )
    ctx = replace(execution_context, foundry=mock_foundry)

    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = artifact_ref_factory(kind="foundry.exec_plan")
    state.inputs[INPUT_INPUT_BINDINGS_REF] = artifact_ref_factory(kind="foundry.input_bindings")
    state.params["strategic_scm"] = {"invalid": True}
    state.params["strategic_payoff_tables"] = {"leader": {"invalid": True}}

    outcome = RunSimulationNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert outcome.state.params["strategic_response"]["fallback_mode"] == "blocked"
    assert outcome.state.params["strategic_response_source"] == "run_simulation"
    assert any(event.level == "warn" for event in outcome.events)


def test_run_simulation_result_assertion_is_not_swallowed(
    execution_context, minimal_state, artifact_ref_factory
):
    mock_foundry = MagicMock()
    sim_ref = artifact_ref_factory(
        kind="foundry.simulation_result",
        data={"schema_version": "1.0", "notes": []},
    )
    mock_foundry.execute.return_value = SimpleNamespace(
        ok=True,
        simulation_result_ref=sim_ref,
        derived_refs=[],
        notes=[],
    )

    ctx = replace(execution_context, foundry=mock_foundry)
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = artifact_ref_factory(kind="foundry.exec_plan")
    state.inputs[INPUT_INPUT_BINDINGS_REF] = artifact_ref_factory(kind="foundry.input_bindings")

    with (
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_simulation.SimulationResult.model_validate",
            side_effect=AssertionError("simulation payload invariant"),
        ),
        pytest.raises(AssertionError, match="simulation payload invariant"),
    ):
        RunSimulationNode().execute(ctx, state)


def _runtime_payoff_tables() -> dict[str, FiniteStrategicPayoffTable]:
    action_spaces = {
        "leader": ("low", "high"),
        "follower": ("stay", "switch"),
    }
    return {
        "leader": FiniteStrategicPayoffTable(
            agent="leader",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs={
                "leader=low|follower=stay": 1.0,
                "leader=low|follower=switch": 0.0,
                "leader=high|follower=stay": 2.0,
                "leader=high|follower=switch": 3.0,
            },
        ),
        "follower": FiniteStrategicPayoffTable(
            agent="follower",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs={
                "leader=low|follower=stay": 2.0,
                "leader=low|follower=switch": 1.0,
                "leader=high|follower=stay": 0.0,
                "leader=high|follower=switch": 3.0,
            },
        ),
    }


def _artifact_ref_model(seed: str, *, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel.model_validate(
        {
            "artifact_id": "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest(),
            "kind": kind,
            "media_type": "application/json",
        }
    )
