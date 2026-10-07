from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import ExecPlanRef, MetricsRef, SimulationResult
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.uncertainty.config import AdaptiveStoppingConfig, PropagationConfig
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
from polisyos.scientist.nodes.builtins.simulate import propagate_uncertainty as node_module
from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
    PropagateUncertaintyNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _normal_env(point: float, std: float) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(point - 1.96 * std, point + 1.96 * std),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
        metadata={"param_name": "x"},
    )


def _config(**overrides) -> PropagationConfig:
    config = {
        "mc_n_samples": 1000,
        "mc_batch_size": 200,
        "mc_min_valid_samples": 50,
        "mc_seed": 2424,
        "compute_sensitivity": False,
    }
    config.update(overrides)
    return PropagationConfig(**config)


def _half_fails(x: float) -> dict[str, float]:
    if x < 0:
        raise RuntimeError("input-dependent solver refusal")
    return {"y": float(x)}


def _require_candidate_only(result) -> None:
    assert result.envelope.gate_eligible is False
    assert result.envelope.interval_semantics is IntervalSemantics.HEURISTIC_RANGE
    assert result.envelope.confidence_level is None
    assert result.envelope.metadata["candidate_only"] is True
    assert result.envelope.metadata["distribution_sample_semantics"] == (
        "successful_draws_only_conditional_on_execution"
    )


def test_partial_failures_are_per_draw_provenanced_candidate_only() -> None:
    result = MonteCarloPropagator(_config()).propagate(
        _half_fails,
        {"x": 0.0},
        {"x": _normal_env(0.0, 1.0)},
        ["y"],
    )[0]

    assert result.diagnostics["n_samples"] == 1000
    assert result.diagnostics["n_failed"] == int(
        np.count_nonzero(np.random.default_rng(2424).uniform(size=1000) < 0.5)
    )
    assert result.diagnostics["n_valid"] == 1000 - int(
        np.count_nonzero(np.random.default_rng(2424).uniform(size=1000) < 0.5)
    )
    assert result.diagnostics["missing_output_count"] == 0
    _require_candidate_only(result)
    assert result.envelope.metadata["failure"] == "incomplete_simulation_draws"
    assert result.envelope.sample_size == 1000 - int(
        np.count_nonzero(np.random.default_rng(2424).uniform(size=1000) < 0.5)
    )
    assert len(result.envelope.distribution_payload.samples) == 1000 - int(
        np.count_nonzero(np.random.default_rng(2424).uniform(size=1000) < 0.5)
    )
    outcomes = result.diagnostics["draw_outcome_provenance"]
    assert outcomes["requested_draw_count"] == 1000
    assert outcomes["attempted_draw_count"] == 1000
    assert outcomes["successful_draw_count"] == 1000 - int(
        np.count_nonzero(np.random.default_rng(2424).uniform(size=1000) < 0.5)
    )
    assert outcomes["unattempted_draw_count"] == 0
    assert outcomes["outcome_denominator_complete"] is True
    failures = outcomes["failure_records"]
    assert len(failures) == int(
        np.count_nonzero(np.random.default_rng(2424).uniform(size=1000) < 0.5)
    )
    assert all(
        row["output_outcomes"]
        == [
            {
                "output_metric_id": "y",
                "outcome_code": "simulation_exception",
                "error_type": "RuntimeError",
            }
        ]
        for row in failures
    )
    assert all(len(row["sampled_input_sha256"]) == 64 for row in failures)
    assert len({row["draw_index"] for row in failures}) == int(
        np.count_nonzero(np.random.default_rng(2424).uniform(size=1000) < 0.5)
    )


def test_missing_and_non_finite_outputs_are_also_not_authoritative() -> None:
    envelope = {"x": _normal_env(0.0, 1.0)}
    missing = MonteCarloPropagator(_config()).propagate(
        lambda x: {} if x < 0 else {"y": float(x)},
        {"x": 0.0},
        envelope,
        ["y"],
    )[0]
    _require_candidate_only(missing)
    assert missing.diagnostics["missing_output_count"] == int(
        np.count_nonzero(np.random.default_rng(2424).uniform(size=1000) < 0.5)
    )
    assert {
        row["output_outcomes"][0]["outcome_code"]
        for row in missing.diagnostics["draw_outcome_provenance"]["failure_records"]
    } == {"missing_output"}

    non_finite = MonteCarloPropagator(_config()).propagate(
        lambda x: {"y": float("nan")} if x < 0 else {"y": float(x)},
        {"x": 0.0},
        envelope,
        ["y"],
    )[0]
    _require_candidate_only(non_finite)
    assert non_finite.diagnostics["missing_output_count"] == 0
    assert {
        row["output_outcomes"][0]["outcome_code"]
        for row in non_finite.diagnostics["draw_outcome_provenance"]["failure_records"]
    } == {"non_finite_output"}


def test_one_failed_draw_records_all_affected_outputs_once() -> None:
    def two_outputs(x: float) -> dict[str, float]:
        if x < 0:
            raise RuntimeError("input-dependent solver refusal")
        return {"y": float(x), "z": float(x)}

    results = MonteCarloPropagator(_config()).propagate(
        two_outputs,
        {"x": 0.0},
        {"x": _normal_env(0.0, 1.0)},
        ["y", "z"],
    )

    assert len(results) == 2
    provenance = results[0].diagnostics["draw_outcome_provenance"]
    assert provenance is results[1].diagnostics["draw_outcome_provenance"]
    for result in results:
        assert result.diagnostics["draw_outcome_provenance"] is provenance
    failures = provenance["failure_records"]
    assert len(failures) == int(
        np.count_nonzero(np.random.default_rng(2424).uniform(size=1000) < 0.5)
    )
    assert len({row["draw_index"] for row in failures}) == int(
        np.count_nonzero(np.random.default_rng(2424).uniform(size=1000) < 0.5)
    )
    assert all(
        row["output_outcomes"]
        == [
            {
                "output_metric_id": "y",
                "outcome_code": "simulation_exception",
                "error_type": "RuntimeError",
            },
            {
                "output_metric_id": "z",
                "outcome_code": "simulation_exception",
                "error_type": "RuntimeError",
            },
        ]
        for row in failures
    )


def test_mixed_output_failures_are_one_record_with_each_typed_outcome() -> None:
    def mixed_outputs(x: float) -> dict[str, float | None]:
        if x < 0:
            return {"y": None, "z": float("nan")}
        return {"y": float(x), "z": float(x)}

    result = MonteCarloPropagator(_config()).propagate(
        mixed_outputs,
        {"x": 0.0},
        {"x": _normal_env(0.0, 1.0)},
        ["y", "z"],
    )[0]

    provenance = result.diagnostics["draw_outcome_provenance"]
    failures = provenance["failure_records"]
    assert len(failures) == int(
        np.count_nonzero(np.random.default_rng(2424).uniform(size=1000) < 0.5)
    )
    assert len({row["draw_index"] for row in failures}) == int(
        np.count_nonzero(np.random.default_rng(2424).uniform(size=1000) < 0.5)
    )
    assert all(
        row["output_outcomes"]
        == [
            {"output_metric_id": "y", "outcome_code": "missing_output", "error_type": None},
            {"output_metric_id": "z", "outcome_code": "non_finite_output", "error_type": None},
        ]
        for row in failures
    )


def test_all_failed_multi_output_draws_remain_candidate_without_crashing() -> None:
    def failing_outputs(x: float) -> dict[str, float]:
        del x
        raise RuntimeError("solver refused every draw")

    results = MonteCarloPropagator(_config(mc_n_samples=100, mc_min_valid_samples=50)).propagate(
        failing_outputs,
        {"x": 0.0},
        {"x": _normal_env(0.0, 1.0)},
        ["y", "z"],
    )

    assert len(results) == 2
    for result in results:
        assert result.envelope.gate_eligible is False
        assert result.diagnostics["n_valid"] == 0
        assert result.diagnostics["n_failed"] == 100
        assert result.diagnostics["output_coverage_complete"] is False
        assert result.envelope.metadata["failure"] == "insufficient_valid_samples"
        assert result.envelope.metadata["draw_outcome_status"] == "incomplete"
        assert result.envelope.metadata["candidate_only"] is True
        assert result.envelope.metadata["draw_failure_count"] == 100
    provenance = results[0].diagnostics["draw_outcome_provenance"]
    assert provenance is results[1].diagnostics["draw_outcome_provenance"]
    assert provenance["successful_draw_count"] == 0
    assert len(provenance["failure_records"]) == 100
    assert all(
        [row["output_metric_id"] for row in record["output_outcomes"]] == ["y", "z"]
        for record in provenance["failure_records"]
    )


def test_complete_fixed_draws_preserve_candidate_authority_control() -> None:
    result = MonteCarloPropagator(_config()).propagate(
        lambda x: {"y": float(x)},
        {"x": 0.0},
        {"x": _normal_env(0.0, 1.0)},
        ["y"],
    )[0]

    assert result.envelope.gate_eligible is False
    assert result.envelope.interval_semantics is IntervalSemantics.CONFIDENCE_INTERVAL
    assert result.envelope.confidence_level == pytest.approx(0.95)
    assert result.envelope.sample_size == 1000
    assert result.diagnostics["output_coverage_complete"] is True
    assert result.diagnostics["draw_outcome_provenance"]["failure_records"] == []


def test_legacy_adaptive_settings_complete_fixed_maximum_without_optional_peeking() -> None:
    config = _config(
        mc_n_samples=500,
        adaptive_stopping=AdaptiveStoppingConfig(
            enabled=True,
            min_samples=50,
            max_samples=500,
            ci_half_width_target=1_000_000.0,
            check_interval=50,
        ),
    )
    result = MonteCarloPropagator(config).propagate(
        lambda x: {"y": float(x)},
        {"x": 0.0},
        {"x": _normal_env(0.0, 1.0)},
        ["y"],
    )[0]

    assert result.diagnostics["stopped_early"] is False
    assert result.diagnostics["draw_outcome_provenance"]["requested_draw_count"] == 500
    assert result.diagnostics["draw_outcome_provenance"]["attempted_draw_count"] == 500
    assert result.diagnostics["draw_outcome_provenance"]["unattempted_draw_count"] == 0
    assert result.diagnostics["draw_outcome_provenance"]["outcome_denominator_complete"] is True
    assert result.envelope.sample_size == 500
    assert result.envelope.gate_eligible is False


def _build_node_context(
    tmp_path: Path,
    *,
    run_id: str,
    metric_values: dict[str, float],
    propagation_config: dict[str, Any],
    input_env: UncertaintyEnvelope | None = None,
) -> tuple[FileSystemCAS, ExecutionContext, ExperimentState]:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.b194"))

    input_ref = persist_uncertainty_envelope(store, input_env or _normal_env(0.0, 1.0))
    state_snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=state_snapshot_ref, uncertainty_envelope_ref=input_ref),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.1.0"),
        ),
    )
    exec_plan_ref = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(state_snapshot_ref.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        {"values": metric_values},
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    simulation_result_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    state = ExperimentState(
        run_id=run_id,
        inputs={
            INPUT_DATA_SNAPSHOT_REF: DataSnapshotRef(artifact_id=data_snapshot_ref.artifact_id)
        },
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: simulation_result_ref},
        params={"propagation_config": propagation_config},
    )
    return store, ctx, state


def test_real_node_persists_aggregate_draw_report_and_exact_missing_set(
    tmp_path, monkeypatch
) -> None:
    store, ctx, state = _build_node_context(
        tmp_path,
        run_id="R_b194_mc",
        metric_values={"y": 0, "z": 0},
        propagation_config={
            "mc_n_samples": 1000,
            "mc_batch_size": 200,
            "mc_min_valid_samples": 50,
            "mc_seed": 2424,
            "compute_sensitivity": False,
        },
    )
    historical_report_bytes = (
        b'{"diagnostics":[],"input_envelope_count":0,"mapped_param_count":0,'
        b'"mapped_params":[],"mapping_status":"resolved","methods":[],'
        b'"missing_output_metric_ids":[],"output_metric_count":0,'
        b'"schema_version":"1.0","unmapped_metric_ids":[]}'
    )
    assert to_canonical_bytes(from_canonical_bytes(historical_report_bytes)) == (
        historical_report_bytes
    )
    historical_report_ref = store.put_bytes(
        historical_report_bytes,
        PutOptions(
            kind="foundry.propagation_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.PropagationReport", version="1.0"),
        ),
    )

    def build_failing_fn(params, *, base_metric_values, nominal_params):
        del params, base_metric_values, nominal_params

        def fn(**current_params):
            x = float(current_params["x"])
            if x < 0:
                return {"y": None, "z": float("nan")}
            return {"y": x, "z": x}

        fn._sensitivity_map = {"y": {"x": 1.0}, "z": {"x": 1.0}}
        return fn, {"x"}

    monkeypatch.setattr(node_module, "_build_propagation_fn", build_failing_fn)
    outcome = PropagateUncertaintyNode().execute(ctx, state)

    assert outcome.status == "ok"
    report_ref = outcome.state.artifacts_index["propagation_report_ref"]
    report = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    assert report["schema_version"] == "1.1"
    assert report["missing_output_metric_ids"] == ["y"]
    assert report["incomplete_output_metric_ids"] == ["y", "z"]
    shared_provenance = report["draw_outcome_provenance"]
    assert shared_provenance["requested_draw_count"] == 1000
    assert len(shared_provenance["failure_records"]) == int(
        np.count_nonzero(np.random.default_rng(2424).uniform(size=1000) < 0.5)
    )
    assert len({row["draw_index"] for row in shared_provenance["failure_records"]}) == int(
        np.count_nonzero(np.random.default_rng(2424).uniform(size=1000) < 0.5)
    )
    assert all(
        row["output_outcomes"]
        == [
            {"output_metric_id": "y", "outcome_code": "missing_output", "error_type": None},
            {"output_metric_id": "z", "outcome_code": "non_finite_output", "error_type": None},
        ]
        for row in shared_provenance["failure_records"]
    )
    for row in report["diagnostics"]:
        assert "draw_outcome_provenance" not in row["diagnostics"]
        assert row["diagnostics"]["output_coverage_complete"] is False
    assert [row["diagnostics"]["missing_output"] for row in report["diagnostics"]] == [
        True,
        False,
    ]

    updated_ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    updated_payload = from_canonical_bytes(store.get_bytes(updated_ref.artifact_id))
    updated = SimulationResult.model_validate(updated_payload)
    output_env = load_uncertainty_envelope(store, updated.uncertainty_envelopes["y"])
    assert output_env.gate_eligible is False
    assert output_env.interval_semantics is IntervalSemantics.HEURISTIC_RANGE
    assert output_env.confidence_level is None
    assert output_env.sample_size == 1000 - int(
        np.count_nonzero(np.random.default_rng(2424).uniform(size=1000) < 0.5)
    )
    assert output_env.metadata["candidate_only"] is True
    assert output_env.metadata["draw_failure_count"] == int(
        np.count_nonzero(np.random.default_rng(2424).uniform(size=1000) < 0.5)
    )
    assert store.get_bytes(historical_report_ref.artifact_id) == historical_report_bytes


def test_delta_missing_output_is_reported_as_missing_and_incomplete(tmp_path, monkeypatch) -> None:
    store, ctx, state = _build_node_context(
        tmp_path,
        run_id="R_b194_delta",
        metric_values={"missing": 0},
        propagation_config={"preferred_method": "delta"},
    )

    def build_missing_fn(params, *, base_metric_values, nominal_params):
        del params, base_metric_values, nominal_params

        def fn(**current_params):
            return {"other_metric": current_params["x"]}

        fn._sensitivity_map = {"missing": {"x": 1.0}}
        return fn, {"x"}

    monkeypatch.setattr(node_module, "_build_propagation_fn", build_missing_fn)
    outcome = PropagateUncertaintyNode().execute(ctx, state)

    assert outcome.status == "ok"
    report_ref = outcome.state.artifacts_index["propagation_report_ref"]
    report = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    assert report["methods"] == ["delta_method"]
    assert report["missing_output_metric_ids"] == ["missing"]
    assert report["incomplete_output_metric_ids"] == ["missing"]
    assert report["diagnostics"][0]["diagnostics"]["missing_output"] is True


def test_valid_delta_output_is_not_marked_missing_or_incomplete(tmp_path, monkeypatch) -> None:
    store, ctx, state = _build_node_context(
        tmp_path,
        run_id="R_b194_delta_valid",
        metric_values={"valid": 0},
        propagation_config={"preferred_method": "delta"},
    )

    def build_valid_fn(params, *, base_metric_values, nominal_params):
        del params, base_metric_values, nominal_params

        def fn(**current_params):
            return {"valid": 2.0 * current_params["x"]}

        fn._sensitivity_map = {"valid": {"x": 2.0}}
        return fn, {"x"}

    monkeypatch.setattr(node_module, "_build_propagation_fn", build_valid_fn)
    outcome = PropagateUncertaintyNode().execute(ctx, state)

    assert outcome.status == "ok"
    report_ref = outcome.state.artifacts_index["propagation_report_ref"]
    report = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    assert report["methods"] == ["delta_method"]
    assert report["missing_output_metric_ids"] == []
    assert report["incomplete_output_metric_ids"] == []


def test_real_node_persists_and_replays_independent_pilot_certificate(tmp_path):
    from polisyos.foundry.uncertainty.sampling_admission import verify_mean_certificate

    env = UncertaintyEnvelope(
        point_estimate=0.5,
        confidence_interval=(0, 1),
        confidence_level=None,
        distribution_family=DistributionFamily.UNIFORM,
        source=UncertaintySource.ENSEMBLE,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
        gate_eligible=True,
        metadata={"param_name": "x"},
    )
    store, ctx, state = _build_node_context(
        tmp_path,
        run_id="R_b193_pilot",
        metric_values={"y": 0},
        input_env=env,
        propagation_config={
            "compute_sensitivity": False,
            "mc_seed": 42,
            "bounded_iid_mean": {"metric_id": "y", "response_threshold": 0.001},
        },
    )
    outcome = PropagateUncertaintyNode().execute(ctx, state)
    assert outcome.status == "ok"
    reopened = FileSystemCAS(tmp_path)
    simulation = SimulationResult.model_validate(
        from_canonical_bytes(
            reopened.get_bytes(
                outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF].artifact_id
            )
        )
    )
    output = load_uncertainty_envelope(reopened, simulation.uncertainty_envelopes["y"])
    certificate = verify_mean_certificate(output)
    assert certificate.frozen_main_samples == 408
    assert certificate.pilot_samples == 256
    assert not output.gate_eligible
    report = from_canonical_bytes(reopened.get_bytes(simulation.propagation_report_ref.artifact_id))
    assert len(report["draw_outcome_provenance"]["draw_records"]) == 408
    assert report["incomplete_output_metric_ids"] == []
