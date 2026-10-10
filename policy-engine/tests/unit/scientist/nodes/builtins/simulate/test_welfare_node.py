from __future__ import annotations

import logging
from pathlib import Path

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    Metrics,
    MetricsRef,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
from polisyos.ir.analytics.welfare import load_welfare_bundle
from polisyos.ir.artifacts import get_json_artifact
from polisyos.scientist.nodes.builtins.simulate.propagate_welfare import PropagateWelfareNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_WELFARE_BUNDLE_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _simulation_result(
    store: FileSystemCAS, *, raw_metrics_payload: dict[str, object] | None = None
) -> SimulationResultRef:
    base = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    plan = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(base.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_payload = (
        Metrics(values={"policy_value": 10.0})
        if raw_metrics_payload is None
        else raw_metrics_payload
    )
    metrics = store.put_json(
        metrics_payload,
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    result = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef.model_validate(plan.model_dump(mode="python")),
            metrics_ref=MetricsRef.model_validate(metrics.model_dump(mode="python")),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return SimulationResultRef.model_validate(result.model_dump(mode="python"))


def _input_snapshot(store: FileSystemCAS) -> DataSnapshotRef:
    source = store.put_json(
        {"source": "controlled-test-input"},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    envelope = UncertaintyEnvelope(
        point_estimate=10.0,
        confidence_interval=(8.0, 12.0),
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.TRUST,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        metadata={"param_name": "policy_value"},
    )
    envelope_ref = persist_uncertainty_envelope(ensure_ir_artifact_store(store), envelope)
    snapshot = store.put_json(
        DataSnapshot(data_ref=source, uncertainty_envelope_ref=envelope_ref),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.1.0"),
        ),
    )
    return DataSnapshotRef.model_validate(snapshot.model_dump(mode="python"))


def _execution_context(store: FileSystemCAS, run_id: str) -> ExecutionContext:
    registry_ref = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    return ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(f"test.welfare.node.{run_id}"),
    )


def test_node_persists_bundle_and_reader_recovers_selected_uncertainty_lineage(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    context = _execution_context(store, "R_welfare_module_node_e2e")
    state = ExperimentState(
        run_id="R_welfare_module_node_e2e",
        inputs={INPUT_DATA_SNAPSHOT_REF: _input_snapshot(store)},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: _simulation_result(store)},
        params={
            "welfare_weights": {"policy_value": 1.0},
            "propagation_config": {"preferred_method": "delta"},
        },
    )

    outcome = PropagateWelfareNode().execute(context, state)

    assert outcome.status == "ok"
    assert ARTIFACT_WELFARE_BUNDLE_REF in outcome.state.artifacts_index
    bundle_ref = outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    fresh_store = FileSystemCAS(tmp_path)
    bundle = load_welfare_bundle(ensure_ir_artifact_store(fresh_store), bundle_ref)
    assert bundle.point_estimate == 10.0
    assert bundle.credible_interval is not None
    assert bundle.method_used.value == "mixed_nested"
    assert bundle.method_config_ref is not None
    method_config = get_json_artifact(
        ensure_ir_artifact_store(fresh_store), bundle.method_config_ref
    )
    assert method_config["preferred_method"] == "delta"
    assert bundle.pe_uncertainty_refs
    selected_envelope = load_uncertainty_envelope(
        ensure_ir_artifact_store(fresh_store), bundle.pe_uncertainty_refs["policy_value"]
    )
    assert selected_envelope.point_estimate == 10.0
    bundle_manifest = fresh_store.get_manifest(bundle_ref)
    assert any(item.role == "pe_uncertainty.policy_value" for item in bundle_manifest.inputs)


def test_node_does_not_turn_a_target_request_without_uncertainty_into_a_bundle(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    context = _execution_context(store, "R_welfare_module_node_no_input")
    state = ExperimentState(
        run_id="R_welfare_module_node_no_input",
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: _simulation_result(store)},
        params={"welfare_weights": {"policy_value": 1.0}},
    )

    outcome = PropagateWelfareNode().execute(context, state)

    assert outcome.status == "skip"
    assert ARTIFACT_WELFARE_BUNDLE_REF not in outcome.state.artifacts_index


def test_node_refuses_present_null_response_instead_of_using_simulation_metric(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    context = _execution_context(store, "R_welfare_module_node_null_response")
    state = ExperimentState(
        run_id="R_welfare_module_node_null_response",
        inputs={INPUT_DATA_SNAPSHOT_REF: _input_snapshot(store)},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: _simulation_result(store)},
        params={
            "welfare_pe_response": None,
            "welfare_metric_order": ["policy_value"],
            "welfare_weights": {"policy_value": 1.0},
        },
    )

    outcome = PropagateWelfareNode().execute(context, state)

    assert outcome.status == "fail", outcome.events
    assert outcome.error is not None
    assert outcome.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"
    assert ARTIFACT_WELFARE_BUNDLE_REF not in outcome.state.artifacts_index


@pytest.mark.parametrize(
    "welfare_params",
    [
        {
            "welfare_pe_response": [True],
            "welfare_metric_order": ["policy_value"],
            "welfare_weights": [1.0],
        },
        {
            "welfare_pe_response": [10.0],
            "welfare_metric_order": ["policy_value"],
            "welfare_weights": [True],
        },
    ],
)
def test_node_refuses_boolean_response_or_weight_values(
    tmp_path: Path, welfare_params: dict[str, object]
) -> None:
    store = FileSystemCAS(tmp_path)
    context = _execution_context(store, "R_welfare_module_node_boolean_numeric_inputs")
    state = ExperimentState(
        run_id="R_welfare_module_node_boolean_numeric_inputs",
        inputs={INPUT_DATA_SNAPSHOT_REF: _input_snapshot(store)},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: _simulation_result(store)},
        params=welfare_params,
    )

    outcome = PropagateWelfareNode().execute(context, state)

    assert outcome.status == "fail", outcome.events
    assert outcome.error is not None
    assert outcome.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"
    assert ARTIFACT_WELFARE_BUNDLE_REF not in outcome.state.artifacts_index


def test_node_refuses_boolean_metric_before_metrics_model_coercion(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    context = _execution_context(store, "R_welfare_module_node_boolean_metric")
    state = ExperimentState(
        run_id="R_welfare_module_node_boolean_metric",
        inputs={INPUT_DATA_SNAPSHOT_REF: _input_snapshot(store)},
        artifacts_index={
            ARTIFACT_SIMULATION_RESULT_REF: _simulation_result(
                store,
                raw_metrics_payload={"values": {"policy_value": 10.0, "unselected_metric": True}},
            )
        },
        params={},
    )

    outcome = PropagateWelfareNode().execute(context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"
    assert ARTIFACT_WELFARE_BUNDLE_REF not in outcome.state.artifacts_index


@pytest.mark.parametrize(
    "welfare_params",
    [
        {
            "welfare_pe_response": {"policy_value": 10.0, "unselected": True},
            "welfare_metric_order": ["policy_value"],
            "welfare_weights": {"policy_value": 1.0},
        },
        {
            "welfare_pe_response": {"policy_value": 10.0},
            "welfare_metric_order": ["policy_value"],
            "welfare_weights": {"policy_value": 1.0, "unselected": True},
        },
    ],
)
def test_node_refuses_boolean_in_unselected_response_or_weight_values(
    tmp_path: Path, welfare_params: dict[str, object]
) -> None:
    store = FileSystemCAS(tmp_path)
    context = _execution_context(store, "R_welfare_module_node_unselected_boolean")
    state = ExperimentState(
        run_id="R_welfare_module_node_unselected_boolean",
        inputs={INPUT_DATA_SNAPSHOT_REF: _input_snapshot(store)},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: _simulation_result(store)},
        params=welfare_params,
    )

    outcome = PropagateWelfareNode().execute(context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"
    assert ARTIFACT_WELFARE_BUNDLE_REF not in outcome.state.artifacts_index


def test_node_refuses_unknown_explicit_method_instead_of_dispatching_monte_carlo(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    context = _execution_context(store, "R_welfare_module_node_unknown_method")
    state = ExperimentState(
        run_id="R_welfare_module_node_unknown_method",
        inputs={INPUT_DATA_SNAPSHOT_REF: _input_snapshot(store)},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: _simulation_result(store)},
        params={
            "welfare_metric_order": ["policy_value"],
            "welfare_weights": {"policy_value": 1.0},
            "welfare_credible_method": "future-method",
            "welfare_method": "delta",
        },
    )

    outcome = PropagateWelfareNode().execute(context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "ERROR_INTERVAL_SEMANTICS_INVALID"
    assert ARTIFACT_WELFARE_BUNDLE_REF not in outcome.state.artifacts_index


@pytest.mark.parametrize(
    "raw_config",
    [
        {"mc_n_samples": -1, "preferred_method": "monte_carlo"},
        {"preferred_method": 42},
        None,
        ["monte_carlo"],
    ],
)
def test_node_rejects_invalid_present_propagation_config_instead_of_using_defaults(
    tmp_path, raw_config
) -> None:
    store = FileSystemCAS(tmp_path)
    context = _execution_context(store, "R_welfare_module_node_invalid_config")
    state = ExperimentState(
        run_id="R_welfare_module_node_invalid_config",
        inputs={INPUT_DATA_SNAPSHOT_REF: _input_snapshot(store)},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: _simulation_result(store)},
        params={
            "welfare_pe_response": {"policy_value": 10.0},
            "welfare_weights": {"policy_value": 1.0},
            "propagation_config": raw_config,
        },
    )

    outcome = PropagateWelfareNode().execute(context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "ERROR_INTERVAL_SEMANTICS_INVALID"
    assert ARTIFACT_WELFARE_BUNDLE_REF not in outcome.state.artifacts_index


@pytest.mark.parametrize(
    "welfare_params",
    [
        {"welfare_pe_response": {}, "welfare_weights": {"policy_value": 1.0}},
        {
            "welfare_pe_response": {"policy_value": 10.0},
            "welfare_weights": {},
        },
    ],
)
def test_node_rejects_empty_present_response_or_weights(tmp_path, welfare_params) -> None:
    store = FileSystemCAS(tmp_path)
    context = _execution_context(store, "R_welfare_module_node_empty_basis")
    state = ExperimentState(
        run_id="R_welfare_module_node_empty_basis",
        inputs={INPUT_DATA_SNAPSHOT_REF: _input_snapshot(store)},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: _simulation_result(store)},
        params=welfare_params,
    )

    outcome = PropagateWelfareNode().execute(context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "ERROR_WELFARE_DIMENSION_MISMATCH"
    assert ARTIFACT_WELFARE_BUNDLE_REF not in outcome.state.artifacts_index
