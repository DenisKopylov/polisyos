from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from pydantic import BaseModel, ValidationError

import polisyos.foundry.uncertainty as uncertainty_facade
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import ExecPlanRef, MetricsRef, SimulationResult
from polisyos.core.errors import ErrorCategory, PolicyOSError
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.catalog.bayesian.protocols import canonical_draws_artifact
from polisyos.foundry.uncertainty import (
    MonteCarloPropagator,
    PosteriorJointInputMatrix,
    PosteriorPushforwardOutcomeCode,
)
from polisyos.foundry.uncertainty.config import AdaptiveStoppingConfig, PropagationConfig
from polisyos.foundry.uncertainty.evaluation_failures import EXCEPTION_CHAIN_NODE_LIMIT
from polisyos.ir.analytics import uncertainty as uncertainty_module
from polisyos.ir.analytics.normative_arbitration import (
    ArbitrationOption,
    NormativeAuditStatus,
    NormativeModelCompleteness,
    load_normative_arbitration_result,
)
from polisyos.ir.analytics.posterior_summary import (
    PosteriorPointRole,
    PosteriorSummaryV11,
    summarize_posterior_draw_artifact,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import (
    NormativeArbitrationPolicy,
    NormativeFrame,
    NormativeOutcomeChannel,
    ObjectiveSpec,
    ProblemDomain,
    ProblemFrame,
    StakeholderOutcomeBinding,
    StakeholderRightSpec,
    StakeholderSpec,
    StakeholderUtilityTerm,
)
from polisyos.ir.model_layer.model_spec import FidelityLevel, ModelSpec
from polisyos.ir.model_layer.types import EntityType, OptimizationDirection
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.nodes.builtins.governance.run_normative_arbitration import (
    RunNormativeArbitrationNode,
)
from polisyos.scientist.nodes.builtins.simulate import propagate_uncertainty as node_module
from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
    PropagateUncertaintyNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_TRINITY_BUNDLE_REF,
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


def _posterior_summary(
    samples: dict[str, np.ndarray],
    *,
    point_role: PosteriorPointRole = PosteriorPointRole.POSTERIOR_MEAN,
) -> PosteriorSummaryV11:
    artifact_ref, payload, artifact_hash, _layout = canonical_draws_artifact(
        samples,
        method_name="test_monte_carlo_posterior_consumer",
        sampler_kernel="hmc",
        stage="posterior",
    )
    return summarize_posterior_draw_artifact(
        artifact_ref=artifact_ref,
        artifact_payload=payload,
        artifact_hash=artifact_hash,
        credible_mass=0.9,
        point_role=point_role,
    )


def test_posterior_summary_consumer_types_are_in_supported_facade() -> None:
    names = {
        "MonteCarloPropagator",
        "PosteriorJointInputMatrix",
        "PosteriorPushforwardFailure",
        "PosteriorPushforwardOutcomeCode",
        "PosteriorPushforwardOutputSummary",
        "PosteriorPushforwardResult",
    }

    assert names.issubset(set(uncertainty_facade.__all__))
    assert all(getattr(uncertainty_facade, name) is not None for name in names)
    result_schema = uncertainty_facade.PosteriorPushforwardResult.model_json_schema()
    assert {
        "simulation_attempt_count",
        "retry_attempt_count",
    }.issubset(result_schema["properties"])
    assert {
        "simulation_attempt_count",
        "retry_attempt_count",
    }.issubset(result_schema["required"])
    assert set(result_schema["properties"]["row_evaluation_semantics"]["enum"]) == {
        "one_evaluator_call_per_source_draw",
        "one_logical_result_per_source_draw_with_one_bounded_typed_transient_retry",
    }


def test_b201_versioned_posterior_consumer_keeps_mean_outside_equal_tail_interval() -> None:
    summary = _posterior_summary({"theta": np.asarray([[0.0] * 99 + [100.0]], dtype=np.float64)})

    calls: list[float] = []

    def evaluator(theta: float) -> dict[str, float]:
        calls.append(theta)
        return {"metric": theta}

    result = MonteCarloPropagator(_config()).propagate_posterior_summary(
        summary,
        simulation_fn=evaluator,
        nominal_params={},
        parameter_names=("theta",),
        output_metric_ids=("metric",),
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )

    metric = result.output_summaries["metric"]
    assert metric.selected_point_value == 1.0
    assert metric.posterior_mean == 1.0
    assert metric.posterior_median == 0.0
    assert metric.equal_tail_interval == (0.0, 0.0)
    assert metric.draw_values == (0.0,) * 99 + (100.0,)
    assert result.point_role is PosteriorPointRole.POSTERIOR_MEAN
    assert result.gate_eligible is False
    assert result.chain_count == 1
    assert result.draws_per_chain == 100
    assert result.source_weight_status == "not_supplied_by_source"
    assert result.row_evaluation_semantics == "one_evaluator_call_per_source_draw"
    assert result.simulation_attempt_count == 101
    assert result.retry_attempt_count == 0
    assert len(calls) == 101
    assert result.simulation_attempt_count == len(calls)
    assert result.simulation_attempt_count == 1 + len(result.joint_input_matrix.rows)
    historical_payload = result.model_dump(mode="python")
    historical_payload.pop("simulation_attempt_count")
    historical_payload.pop("retry_attempt_count")
    with pytest.raises(ValidationError, match="simulation_attempt_count"):
        uncertainty_facade.PosteriorPushforwardResult.model_validate(historical_payload)
    assert result.joint_input_matrix.content_sha256.startswith("sha256:")
    assert result.joint_input_matrix.chain_count * result.joint_input_matrix.draws_per_chain == len(
        result.joint_input_matrix.rows
    )
    changed_matrix = result.joint_input_matrix.model_dump(mode="python")
    changed_matrix["rows"] = ((1.0,),) + changed_matrix["rows"][1:]
    with pytest.raises(ValidationError, match="digest does not match"):
        PosteriorJointInputMatrix.model_validate(changed_matrix)
    with pytest.raises(ValueError, match="legacy propagate cannot consume"):
        MonteCarloPropagator(_config()).propagate(
            lambda **_params: {"metric": 0.0},
            {},
            summary,  # type: ignore[arg-type]
            ["metric"],
        )


def test_b202_versioned_posterior_consumer_preserves_joint_row_pairing() -> None:
    same = _posterior_summary(
        {
            "x": np.asarray([[-1.0, 1.0, -1.0, 1.0]], dtype=np.float64),
            "y": np.asarray([[-1.0, 1.0, -1.0, 1.0]], dtype=np.float64),
        }
    )
    reversed_pairing = _posterior_summary(
        {
            "x": np.asarray([[-1.0, 1.0, -1.0, 1.0]], dtype=np.float64),
            "y": np.asarray([[1.0, -1.0, 1.0, -1.0]], dtype=np.float64),
        }
    )
    assert same.parameters["x"].posterior_mean == reversed_pairing.parameters["x"].posterior_mean
    assert (
        same.parameters["x"].posterior_median == reversed_pairing.parameters["x"].posterior_median
    )
    assert same.parameters["y"].posterior_mean == reversed_pairing.parameters["y"].posterior_mean
    assert (
        same.parameters["y"].posterior_median == reversed_pairing.parameters["y"].posterior_median
    )

    def product(*, x: float, y: float) -> dict[str, float]:
        return {"product": x * y}

    propagator = MonteCarloPropagator(_config())
    same_result = propagator.propagate_posterior_summary(
        same,
        simulation_fn=product,
        nominal_params={},
        parameter_names=("x", "y"),
        output_metric_ids=("product",),
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )
    reversed_result = propagator.propagate_posterior_summary(
        reversed_pairing,
        simulation_fn=product,
        nominal_params={},
        parameter_names=("x", "y"),
        output_metric_ids=("product",),
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )

    assert same_result.joint_input_matrix.rows == (
        (-1.0, -1.0),
        (1.0, 1.0),
        (-1.0, -1.0),
        (1.0, 1.0),
    )
    assert reversed_result.joint_input_matrix.rows == (
        (-1.0, 1.0),
        (1.0, -1.0),
        (-1.0, 1.0),
        (1.0, -1.0),
    )
    assert (
        same_result.joint_input_matrix.content_sha256
        != reversed_result.joint_input_matrix.content_sha256
    )
    assert same_result.output_summaries["product"].draw_values == (1.0, 1.0, 1.0, 1.0)
    assert reversed_result.output_summaries["product"].draw_values == (-1.0, -1.0, -1.0, -1.0)
    assert same_result.output_summaries["product"].posterior_mean == 1.0
    assert reversed_result.output_summaries["product"].posterior_mean == -1.0
    assert same_result.gate_eligible is False
    assert reversed_result.gate_eligible is False


def test_versioned_posterior_consumer_requires_explicit_matching_point_role() -> None:
    summary = _posterior_summary(
        {"theta": np.asarray([[1.0, 2.0, 3.0]], dtype=np.float64)},
        point_role=PosteriorPointRole.POSTERIOR_MEDIAN,
    )
    called = False

    def evaluator(theta: float) -> dict[str, float]:
        nonlocal called
        called = True
        return {"metric": theta}

    with pytest.raises(ValueError, match="point_role must match"):
        MonteCarloPropagator(_config()).propagate_posterior_summary(
            summary,
            simulation_fn=evaluator,
            nominal_params={},
            parameter_names=("theta",),
            output_metric_ids=("metric",),
            point_role=PosteriorPointRole.POSTERIOR_MEAN,
        )
    assert called is False


def test_versioned_posterior_consumer_recomputes_summary_before_evaluation() -> None:
    summary = _posterior_summary({"theta": np.asarray([[1.0, 2.0, 3.0]], dtype=np.float64)})
    changed_parameter = summary.parameters["theta"].model_copy(update={"draws": (1.0, 2.0, 99.0)})
    tampered = summary.model_copy(update={"parameters": {"theta": changed_parameter}})
    called = False

    def evaluator(theta: float) -> dict[str, float]:
        nonlocal called
        called = True
        return {"metric": theta}

    with pytest.raises(ValueError, match="does not match its source draw payload"):
        MonteCarloPropagator(_config()).propagate_posterior_summary(
            tampered,
            simulation_fn=evaluator,
            nominal_params={},
            parameter_names=("theta",),
            output_metric_ids=("metric",),
            point_role=PosteriorPointRole.POSTERIOR_MEAN,
        )
    assert called is False


def test_posterior_typed_transient_retries_same_source_row_without_adding_a_row() -> None:
    summary = _posterior_summary({"theta": np.asarray([[1.0, 2.0, 3.0]], dtype=np.float64)})
    calls: list[float] = []
    transient_raised = False

    def intermittent(theta: float) -> dict[str, float]:
        nonlocal transient_raised
        calls.append(theta)
        if theta == 1.0 and not transient_raised:
            transient_raised = True
            raise PolicyOSError("temporary evaluator outage", category=ErrorCategory.TRANSIENT)
        return {"metric": theta}

    result = MonteCarloPropagator(_config()).propagate_posterior_summary(
        summary,
        simulation_fn=intermittent,
        nominal_params={},
        parameter_names=("theta",),
        output_metric_ids=("metric",),
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )

    assert calls == [2.0, 1.0, 1.0, 2.0, 3.0]
    assert result.joint_input_matrix.rows == ((1.0,), (2.0,), (3.0,))
    assert result.output_summaries["metric"].draw_values == (1.0, 2.0, 3.0)
    assert result.output_summaries["metric"].successful_draw_count == 3
    assert result.output_summaries["metric"].failure_records == ()
    assert result.row_evaluation_semantics == (
        "one_logical_result_per_source_draw_with_one_bounded_typed_transient_retry"
    )
    assert result.simulation_attempt_count == 5
    assert result.retry_attempt_count == 1
    assert result.simulation_attempt_count == len(calls)
    assert result.simulation_attempt_count == (
        1 + len(result.joint_input_matrix.rows) + result.retry_attempt_count
    )

    inconsistent_count = result.model_dump(mode="python")
    inconsistent_count["simulation_attempt_count"] -= 1
    with pytest.raises(ValidationError, match="attempt counts"):
        uncertainty_facade.PosteriorPushforwardResult.model_validate(inconsistent_count)
    inconsistent_semantics = result.model_dump(mode="python")
    inconsistent_semantics["row_evaluation_semantics"] = "one_evaluator_call_per_source_draw"
    with pytest.raises(ValidationError, match="retry semantics"):
        uncertainty_facade.PosteriorPushforwardResult.model_validate(inconsistent_semantics)
    erased_retry_history = result.model_dump(mode="python")
    erased_retry_history.pop("simulation_attempt_count")
    erased_retry_history.pop("retry_attempt_count")
    erased_retry_history["row_evaluation_semantics"] = "one_evaluator_call_per_source_draw"
    with pytest.raises(ValidationError, match="simulation_attempt_count"):
        uncertainty_facade.PosteriorPushforwardResult.model_validate(erased_retry_history)


def test_versioned_posterior_consumer_retains_failed_rows_and_limits_summary_basis() -> None:
    summary = _posterior_summary({"theta": np.asarray([[-2.0, -1.0, 1.0, 2.0]], dtype=np.float64)})

    def partial(theta: float) -> dict[str, float]:
        if theta < 0:
            raise RuntimeError("predictive evaluator refused this candidate draw")
        return {"metric": theta}

    result = MonteCarloPropagator(_config()).propagate_posterior_summary(
        summary,
        simulation_fn=partial,
        nominal_params={},
        parameter_names=("theta",),
        output_metric_ids=("metric",),
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )
    metric = result.output_summaries["metric"]

    assert result.joint_input_matrix.rows == ((-2.0,), (-1.0,), (1.0,), (2.0,))
    assert metric.draw_values == (None, None, 1.0, 2.0)
    assert [record.draw_index for record in metric.failure_records] == [0, 1]
    assert [record.outcome_code.value for record in metric.failure_records] == [
        "simulation_exception",
        "simulation_exception",
    ]
    assert all(
        record.outcome_code is PosteriorPushforwardOutcomeCode.SIMULATION_EXCEPTION
        for record in metric.failure_records
    )
    assert metric.successful_draw_count == 2
    assert metric.posterior_mean == 1.5
    assert metric.equal_tail_interval == (1.0, 2.0)
    assert metric.distribution_sample_semantics == "successful_draws_only_conditional_on_execution"
    assert metric.gate_eligible is False
    assert result.gate_eligible is False


def test_posterior_pushforward_does_not_record_global_failure_as_failed_row() -> None:
    summary = _posterior_summary({"theta": np.asarray([[1.0, 2.0]], dtype=np.float64)})

    def inaccessible_source(theta: float) -> dict[str, float]:
        del theta
        raise PermissionError("global posterior source is not readable")

    with pytest.raises(PermissionError, match="global posterior source is not readable"):
        MonteCarloPropagator(_config()).propagate_posterior_summary(
            summary,
            simulation_fn=inaccessible_source,
            nominal_params={},
            parameter_names=("theta",),
            output_metric_ids=("metric",),
            point_role=PosteriorPointRole.POSTERIOR_MEAN,
        )


def test_partial_failures_are_per_draw_provenanced_candidate_only() -> None:
    sampled_values: list[float] = []

    def record_then_half_fails(x: float) -> dict[str, float]:
        sampled_values.append(x)
        return _half_fails(x)

    result = MonteCarloPropagator(_config()).propagate(
        record_then_half_fails,
        {"x": 0.0},
        {"x": _normal_env(0.0, 1.0)},
        ["y"],
    )[0]
    draw_values = sampled_values[1:]  # The first call is the nominal-point evaluation.
    assert len(draw_values) == 1000
    expected_failed_indices = tuple(index for index, value in enumerate(draw_values) if value < 0.0)

    assert result.diagnostics["n_samples"] == 1000
    assert result.diagnostics["n_failed"] == len(expected_failed_indices)
    assert result.diagnostics["n_valid"] == 1000 - len(expected_failed_indices)
    assert result.diagnostics["missing_output_count"] == 0
    _require_candidate_only(result)
    assert result.envelope.metadata["failure"] == "incomplete_simulation_draws"
    assert result.envelope.sample_size == 1000 - len(expected_failed_indices)
    assert len(result.envelope.distribution_payload.samples) == 1000 - len(expected_failed_indices)
    outcomes = result.diagnostics["draw_outcome_provenance"]
    assert outcomes["requested_draw_count"] == 1000
    assert outcomes["attempted_draw_count"] == 1000
    assert outcomes["successful_draw_count"] == 1000 - len(expected_failed_indices)
    assert outcomes["unattempted_draw_count"] == 0
    assert outcomes["outcome_denominator_complete"] is True
    failures = outcomes["failure_records"]
    assert len(failures) == len(expected_failed_indices)
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
    assert tuple(row["draw_index"] for row in failures) == expected_failed_indices


def test_missing_and_non_finite_outputs_are_also_not_authoritative() -> None:
    envelope = {"x": _normal_env(0.0, 1.0)}

    missing_samples: list[float] = []

    def missing_output(x: float) -> dict[str, float]:
        missing_samples.append(x)
        return {} if x < 0 else {"y": float(x)}

    missing = MonteCarloPropagator(_config()).propagate(
        missing_output,
        {"x": 0.0},
        envelope,
        ["y"],
    )[0]
    _require_candidate_only(missing)
    expected_missing = sum(value < 0.0 for value in missing_samples[1:])
    assert missing.diagnostics["missing_output_count"] == expected_missing
    assert {
        row["output_outcomes"][0]["outcome_code"]
        for row in missing.diagnostics["draw_outcome_provenance"]["failure_records"]
    } == {"missing_output"}

    non_finite_samples: list[float] = []

    def non_finite_output(x: float) -> dict[str, float]:
        non_finite_samples.append(x)
        return {"y": float("nan")} if x < 0 else {"y": float(x)}

    non_finite = MonteCarloPropagator(_config()).propagate(
        non_finite_output,
        {"x": 0.0},
        envelope,
        ["y"],
    )[0]
    _require_candidate_only(non_finite)
    assert non_finite.diagnostics["missing_output_count"] == 0
    assert non_finite.diagnostics["n_failed"] == sum(
        value < 0.0 for value in non_finite_samples[1:]
    )
    assert {
        row["output_outcomes"][0]["outcome_code"]
        for row in non_finite.diagnostics["draw_outcome_provenance"]["failure_records"]
    } == {"non_finite_output"}


def test_one_failed_draw_records_all_affected_outputs_once() -> None:
    sampled_values: list[float] = []

    def two_outputs(x: float) -> dict[str, float]:
        sampled_values.append(x)
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
    draw_values = sampled_values[1:]  # The first call is the nominal-point evaluation.
    assert len(draw_values) == 1000
    expected_failed_indices = tuple(index for index, value in enumerate(draw_values) if value < 0.0)
    assert tuple(row["draw_index"] for row in failures) == expected_failed_indices
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
    sampled_values: list[float] = []

    def mixed_outputs(x: float) -> dict[str, float | None]:
        sampled_values.append(x)
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
    draw_values = sampled_values[1:]
    assert len(draw_values) == 1000
    expected_failed_indices = tuple(index for index, value in enumerate(draw_values) if value < 0.0)
    assert tuple(row["draw_index"] for row in failures) == expected_failed_indices
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

    assert result.envelope.gate_eligible is True
    assert result.envelope.interval_semantics is IntervalSemantics.CONFIDENCE_INTERVAL
    assert result.envelope.confidence_level == pytest.approx(0.95)
    assert result.envelope.sample_size == 1000
    assert result.diagnostics["output_coverage_complete"] is True
    assert result.diagnostics["draw_outcome_provenance"]["failure_records"] == []


def test_adaptively_stopped_candidate_is_not_a_confidence_interval() -> None:
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

    assert result.diagnostics["stopped_early"] is True
    _require_candidate_only(result)
    assert result.diagnostics["draw_outcome_provenance"]["requested_draw_count"] == 500
    assert result.diagnostics["draw_outcome_provenance"]["attempted_draw_count"] == 50
    assert result.diagnostics["draw_outcome_provenance"]["unattempted_draw_count"] == 450
    assert result.diagnostics["draw_outcome_provenance"]["outcome_denominator_complete"] is False
    assert result.envelope.sample_size == 50


def _build_node_context(
    tmp_path: Path,
    *,
    run_id: str,
    metric_values: dict[str, float],
    propagation_config: dict[str, Any],
    propagation_sensitivity: dict[str, dict[str, float]] | None = None,
) -> tuple[FileSystemCAS, ExecutionContext, ExperimentState]:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.b194"))

    input_ref = persist_uncertainty_envelope(
        _ensure_ir_artifact_store(store), _normal_env(0.0, 1.0)
    )
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
        params={
            "propagation_config": propagation_config,
            **(
                {"propagation_sensitivity": propagation_sensitivity}
                if propagation_sensitivity is not None
                else {}
            ),
        },
    )
    return store, ctx, state


def _persist_uncertainty_normative_frame(store: FileSystemCAS):
    problem_frame = ProblemFrame(
        problem_id="b194_uncertainty_consumer",
        domain=ProblemDomain.SOCIAL,
        objectives=[
            ObjectiveSpec(
                objective_id="uncertainty_objective",
                metric_id="y",
                direction=OptimizationDirection.MINIMIZE,
            )
        ],
        stakeholders=[
            StakeholderSpec(
                stakeholder_id="workers",
                entity_type=EntityType.AGENT,
                priority=1,
            )
        ],
        normative_frame=NormativeFrame(
            default_policy=NormativeArbitrationPolicy.WEIGHTED_WELFARE,
            enabled_policies=[NormativeArbitrationPolicy.WEIGHTED_WELFARE],
            stakeholder_bindings=[
                StakeholderOutcomeBinding(
                    binding_id="workers_uncertainty",
                    stakeholder_id="workers",
                    channel=NormativeOutcomeChannel.UNCERTAINTY_CI_WIDTH_RATIO,
                    outcome_key="y",
                )
            ],
            utility_terms=[
                StakeholderUtilityTerm(
                    term_id="workers_uncertainty_utility",
                    stakeholder_id="workers",
                    binding_refs=["workers_uncertainty"],
                    welfare_weight=1,
                )
            ],
            rights_catalog=[
                StakeholderRightSpec(
                    right_id="workers_uncertainty_is_known",
                    stakeholder_id="workers",
                    binding_ref="workers_uncertainty",
                    operator=">=",
                    threshold=0,
                )
            ],
        ),
    )
    trinity_ref = store.put_json(
        TrinityBundle(
            problem_frame=problem_frame,
            policy_spec=PolicySpec(policy_id="b194_policy", interventions=[]),
            model_spec=ModelSpec(
                model_id="b194_model",
                data_snapshot_ref="sha256:" + "0" * 64,
                fidelity_level=FidelityLevel.HYBRID,
            ),
        ),
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    return trinity_ref


def test_complete_persisted_draws_remain_limited_in_fresh_normative_consumer(tmp_path) -> None:
    store, ctx, state = _build_node_context(
        tmp_path,
        run_id="R_b194_normative_complete",
        metric_values={"y": 10},
        propagation_config={
            "preferred_method": "monte_carlo",
            "mc_n_samples": 100,
            "mc_batch_size": 50,
            "mc_min_valid_samples": 50,
            "mc_seed": 811,
            "compute_sensitivity": False,
        },
        propagation_sensitivity={"y": {"x": 1.0}},
    )

    produced = PropagateUncertaintyNode().execute(ctx, state)
    assert produced.status == "ok"
    sim_result_ref = produced.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    sim_result = SimulationResult.model_validate(
        from_canonical_bytes(store.get_bytes(sim_result_ref.artifact_id))
    )
    output_env = load_uncertainty_envelope(
        _ensure_ir_artifact_store(store), sim_result.uncertainty_envelopes["y"]
    )
    report = from_canonical_bytes(store.get_bytes(sim_result.propagation_report_ref.artifact_id))
    assert output_env.gate_eligible is True
    assert report["draw_outcome_provenance"]["outcome_denominator_complete"] is True
    assert report["draw_outcome_provenance"]["requested_draw_count"] == 100
    assert report["draw_outcome_provenance"]["attempted_draw_count"] == 100
    assert report["draw_outcome_provenance"]["successful_draw_count"] == 100
    assert report["draw_outcome_provenance"]["failure_records"] == []

    trinity_ref = _persist_uncertainty_normative_frame(store)
    normative_state = ExperimentState(
        run_id="R_b194_normative_complete",
        inputs={INPUT_TRINITY_BUNDLE_REF: trinity_ref},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: sim_result_ref},
    )
    outcome = RunNormativeArbitrationNode().execute(ctx, normative_state)

    assert outcome.status == "ok"
    result_ref = outcome.state.artifacts_index[ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF]
    result = load_normative_arbitration_result(_ensure_ir_artifact_store(store), result_ref)
    assert result.model_completeness is NormativeModelCompleteness.PARTIAL
    assert any(
        warning.startswith("uncertainty_admission_limited:workers_uncertainty:")
        for warning in result.warnings
    )
    assert any("draw_basis_verifier_missing" in warning for warning in result.warnings)
    proposal = next(
        item for item in result.option_matrix if item.option is ArbitrationOption.PROPOSAL
    )
    assert "workers_uncertainty" not in proposal.binding_values
    assert result.rights_audit[0].status is NormativeAuditStatus.UNEVALUATED


def test_b194_transient_retry_survives_fresh_cas_normative_consumption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, ctx, state = _build_node_context(
        tmp_path,
        run_id="R_b194_transient_recovery",
        metric_values={"y": 0},
        propagation_config={
            "preferred_method": "monte_carlo",
            "mc_n_samples": 100,
            "mc_batch_size": 100,
            "mc_min_valid_samples": 10,
            "mc_seed": 194,
            "compute_sensitivity": False,
        },
        propagation_sensitivity={"y": {"x": 1.0}},
    )
    _draws, offset = _install_fixed_symmetric_draws(monkeypatch)
    sampled_vectors: list[tuple[float, str]] = []
    transient_raised = False

    from polisyos.foundry.uncertainty.monte_carlo import _sampled_input_digest

    def build_intermittent_fn(params, *, base_metric_values, nominal_params):
        del params, base_metric_values, nominal_params

        def fn(**current_params):
            nonlocal transient_raised
            x = float(current_params["x"])
            sampled_vectors.append((x, _sampled_input_digest(current_params)))
            if x < 0 and not transient_raised:
                transient_raised = True
                raise PolicyOSError("temporary evaluator outage", category=ErrorCategory.TRANSIENT)
            return {"y": x}

        fn._sensitivity_map = {"y": {"x": 1.0}}
        return fn, {"x"}

    monkeypatch.setattr(node_module, "_build_propagation_fn", build_intermittent_fn)
    produced = PropagateUncertaintyNode().execute(ctx, state)

    assert produced.status == "ok"
    sim_result_ref = produced.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    sim_result = SimulationResult.model_validate(
        from_canonical_bytes(store.get_bytes(sim_result_ref.artifact_id))
    )
    output_env = load_uncertainty_envelope(
        _ensure_ir_artifact_store(store), sim_result.uncertainty_envelopes["y"]
    )
    report = from_canonical_bytes(store.get_bytes(sim_result.propagation_report_ref.artifact_id))
    ledger = report["draw_outcome_provenance"]
    assert output_env.gate_eligible is True
    assert ledger["requested_draw_count"] == 100
    assert ledger["attempted_draw_count"] == 100
    assert ledger["successful_draw_count"] == 100
    assert ledger["failure_records"] == []
    assert ledger["simulation_attempt_count"] == 102
    assert ledger["retry_attempt_count"] == 1
    assert offset == [100]
    repeated_first_sample = [row for row in sampled_vectors if row[0] == -1.0]
    assert len(repeated_first_sample) == 2
    assert repeated_first_sample[0] == repeated_first_sample[1]

    trinity_ref = _persist_uncertainty_normative_frame(store)
    fresh_state = ExperimentState(
        run_id="R_b194_transient_recovery",
        inputs={INPUT_TRINITY_BUNDLE_REF: trinity_ref},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: sim_result_ref},
    )
    consumed = RunNormativeArbitrationNode().execute(ctx, fresh_state)
    result_ref = consumed.state.artifacts_index[ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF]
    result = load_normative_arbitration_result(_ensure_ir_artifact_store(store), result_ref)
    assert consumed.status == "ok"
    assert result.model_completeness is NormativeModelCompleteness.PARTIAL
    assert not any(
        "propagation_draw_denominator_mismatch" in warning for warning in result.warnings
    )
    proposal = next(
        item for item in result.option_matrix if item.option is ArbitrationOption.PROPOSAL
    )
    assert "workers_uncertainty" not in proposal.binding_values
    assert result.rights_audit[0].status is NormativeAuditStatus.UNEVALUATED


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
    sampled_values: list[float] = []

    def build_failing_fn(params, *, base_metric_values, nominal_params):
        del params, base_metric_values, nominal_params

        def fn(**current_params):
            x = float(current_params["x"])
            sampled_values.append(x)
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
    # The node evaluates its nominal baseline before the Monte Carlo method performs
    # its own nominal-point preflight; neither is a posterior/sample draw.
    draw_values = sampled_values[2:]
    assert len(draw_values) == 1000
    expected_failed_indices = tuple(index for index, value in enumerate(draw_values) if value < 0.0)
    assert (
        tuple(row["draw_index"] for row in shared_provenance["failure_records"])
        == expected_failed_indices
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
    output_env = load_uncertainty_envelope(
        _ensure_ir_artifact_store(store), updated.uncertainty_envelopes["y"]
    )
    assert output_env.gate_eligible is False
    assert output_env.interval_semantics is IntervalSemantics.HEURISTIC_RANGE
    assert output_env.confidence_level is None
    assert output_env.sample_size == 1000 - len(expected_failed_indices)
    assert output_env.metadata["candidate_only"] is True
    assert output_env.metadata["draw_failure_count"] == len(expected_failed_indices)
    assert store.get_bytes(historical_report_ref.artifact_id) == historical_report_bytes

    trinity_ref = _persist_uncertainty_normative_frame(store)
    normative_state = ExperimentState(
        run_id="R_b194_mc",
        inputs={INPUT_TRINITY_BUNDLE_REF: trinity_ref},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: updated_ref},
    )
    normative = RunNormativeArbitrationNode().execute(ctx, normative_state)
    normative_ref = normative.state.artifacts_index[ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF]
    normative_result = load_normative_arbitration_result(
        _ensure_ir_artifact_store(store), normative_ref
    )
    assert normative_result.model_completeness is NormativeModelCompleteness.PARTIAL
    assert any(
        "propagation_metric_output_incomplete" in warning for warning in normative_result.warnings
    )
    proposal = next(
        item for item in normative_result.option_matrix if item.option is ArbitrationOption.PROPOSAL
    )
    assert "workers_uncertainty" not in proposal.binding_values
    assert normative_result.rights_audit[0].status is NormativeAuditStatus.UNEVALUATED


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


def test_normative_admission_recomputes_denominator_while_markers_stay_true(tmp_path) -> None:
    store, ctx, state = _build_node_context(
        tmp_path,
        run_id="R_b194_normative_falsified_denominator",
        metric_values={"y": 10},
        propagation_config={
            "preferred_method": "monte_carlo",
            "mc_n_samples": 100,
            "mc_batch_size": 50,
            "mc_min_valid_samples": 50,
            "mc_seed": 812,
            "compute_sensitivity": False,
        },
        propagation_sensitivity={"y": {"x": 1.0}},
    )
    produced = PropagateUncertaintyNode().execute(ctx, state)
    assert produced.status == "ok"
    original_sim_ref = produced.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    original_sim_payload = from_canonical_bytes(store.get_bytes(original_sim_ref.artifact_id))
    sim_result = SimulationResult.model_validate(original_sim_payload)
    envelope = load_uncertainty_envelope(
        _ensure_ir_artifact_store(store), sim_result.uncertainty_envelopes["y"]
    )
    report = from_canonical_bytes(store.get_bytes(sim_result.propagation_report_ref.artifact_id))
    assert envelope.gate_eligible is True
    assert report["diagnostics"][0]["diagnostics"]["output_coverage_complete"] is True
    ledger = report["draw_outcome_provenance"]
    assert ledger["outcome_denominator_complete"] is True
    assert ledger["failure_records"] == []
    producer_before = store.get_manifest(sim_result.propagation_report_ref.artifact_id).producer

    # Keep all eligibility/completeness markers and producer identity unchanged,
    # but falsify the successful denominator the consumer is meant to recompute.
    ledger["successful_draw_count"] -= 1
    forged_report_ref = store.put_json(
        report,
        PutOptions(
            kind="foundry.propagation_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.PropagationReport", version="1.1"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    assert store.get_manifest(forged_report_ref.artifact_id).producer == producer_before
    forged_sim_ref = store.put_json(
        sim_result.model_copy(update={"propagation_report_ref": forged_report_ref}),
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.1"),
        ),
    )
    trinity_ref = _persist_uncertainty_normative_frame(store)
    normative_state = ExperimentState(
        run_id="R_b194_normative_falsified_denominator",
        inputs={INPUT_TRINITY_BUNDLE_REF: trinity_ref},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: forged_sim_ref},
    )
    outcome = RunNormativeArbitrationNode().execute(ctx, normative_state)
    result_ref = outcome.state.artifacts_index[ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF]
    result = load_normative_arbitration_result(_ensure_ir_artifact_store(store), result_ref)

    assert result.model_completeness is NormativeModelCompleteness.PARTIAL
    assert any("propagation_draw_denominator_mismatch" in item for item in result.warnings)
    proposal = next(
        item for item in result.option_matrix if item.option is ArbitrationOption.PROPOSAL
    )
    assert "workers_uncertainty" not in proposal.binding_values
    assert result.rights_audit[0].status is NormativeAuditStatus.UNEVALUATED


def test_persisted_uncertainty_admission_preserves_selected_manifest_refs(monkeypatch) -> None:
    simulation_id = "sha256:" + "a" * 64
    envelope_id = "sha256:" + "b" * 64
    report_id = "sha256:" + "c" * 64
    simulation_ref = {
        "artifact_id": simulation_id,
        "kind": "foundry.simulation_result",
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + "1" * 64,
    }
    envelope_ref = {
        "artifact_id": envelope_id,
        "kind": "ir.uncertainty_envelope",
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + "2" * 64,
    }
    report_ref = {
        "artifact_id": report_id,
        "kind": "foundry.propagation_report",
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + "3" * 64,
    }
    simulation_payload = {
        "schema_version": "1.3",
        "uncertainty_envelopes": {"metric": envelope_ref},
        "propagation_report_ref": report_ref,
    }
    report_payload = {
        "schema_version": "1.1",
        "diagnostics": [
            {
                "metric_id": "metric",
                "diagnostics": {
                    "output_coverage_complete": True,
                    "n_samples": 1,
                    "n_valid": 1,
                    "n_failed": 0,
                },
            }
        ],
        "missing_output_metric_ids": [],
        "incomplete_output_metric_ids": [],
        "draw_outcome_provenance": {
            "schema_version": "1.0",
            "requested_draw_count": 1,
            "attempted_draw_count": 1,
            "successful_draw_count": 1,
            "unattempted_draw_count": 0,
            "failure_records": [],
            "outcome_denominator_complete": True,
            "sampling_recipe": {
                "input_param_names": [],
                "input_envelope_sha256": {},
                "sample_axis": "draw",
            },
            "implementation_identity_status": "verified",
        },
    }
    envelope_payload = _normal_env(10.0, 1.0).model_dump(mode="json")
    payload_by_id = {
        simulation_id: simulation_payload,
        envelope_id: envelope_payload,
        report_id: report_payload,
    }
    schema_by_id = {
        simulation_id: ("polisyos.core.SimulationResult", "1.3"),
        envelope_id: ("ir.uncertainty_envelope", "1.1"),
        report_id: ("polisyos.foundry.PropagationReport", "1.1"),
    }

    def input_ref(role: str, artifact_id: str) -> SimpleNamespace:
        return SimpleNamespace(role=role, artifact_id=artifact_id)

    manifest_by_id = {
        simulation_id: SimpleNamespace(
            artifact_id=simulation_id,
            kind="foundry.simulation_result",
            media_type="application/json",
            artifact_schema=SimpleNamespace(name=schema_by_id[simulation_id][0], version="1.3"),
            producer=None,
            inputs=[
                input_ref("metric_envelope.metric", envelope_id),
                input_ref("propagation_report", report_id),
                input_ref("base_simulation_result", "sha256:" + "d" * 64),
                input_ref("propagation_config", "sha256:" + "e" * 64),
            ],
        ),
        envelope_id: SimpleNamespace(
            artifact_id=envelope_id,
            kind="ir.uncertainty_envelope",
            media_type="application/json",
            artifact_schema=SimpleNamespace(name=schema_by_id[envelope_id][0], version="1.1"),
            producer=None,
            inputs=[],
        ),
        report_id: SimpleNamespace(
            artifact_id=report_id,
            kind="foundry.propagation_report",
            media_type="application/json",
            artifact_schema=SimpleNamespace(name=schema_by_id[report_id][0], version="1.1"),
            producer=None,
            inputs=[
                input_ref("metric_envelope.metric", envelope_id),
                input_ref("input_envelope.x", "sha256:" + "f" * 64),
            ],
        ),
    }

    def selector_id(selector: object) -> str:
        if isinstance(selector, dict):
            return str(selector["artifact_id"])
        return str(selector)

    class SelectedViewStore:
        def __init__(self) -> None:
            self.manifest_selectors: list[object] = []

        def get_manifest(self, selector: object) -> SimpleNamespace:
            self.manifest_selectors.append(selector)
            return manifest_by_id[selector_id(selector)]

    store = SelectedViewStore()
    read_selectors: list[object] = []

    def read_json(_store: object, selector: object) -> object:
        read_selectors.append(selector)
        return payload_by_id[selector_id(selector)]

    monkeypatch.setattr(uncertainty_module, "get_json_artifact", read_json)
    admission = uncertainty_module.load_simulation_result_uncertainty_admission(
        _ensure_ir_artifact_store(store),
        simulation_ref,
        metric_id="metric",
    )

    expected = [simulation_ref, envelope_ref, report_ref]
    assert [
        selector.get("manifest_profile_sha256") if isinstance(selector, dict) else None
        for selector in store.manifest_selectors
    ] == [ref["manifest_profile_sha256"] for ref in expected]
    assert [
        selector.get("manifest_profile_sha256") if isinstance(selector, dict) else None
        for selector in read_selectors
    ] == [ref["manifest_profile_sha256"] for ref in expected]
    assert admission.envelope is None
    assert "draw_basis_verifier_missing" in admission.limitation_codes


def _install_fixed_symmetric_draws(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[np.ndarray, list[int]]:
    """Feed the exact 100-point symmetric B194 witness through the real sampler seam."""
    draws = np.linspace(-1.0, 1.0, 100, dtype=np.float64)
    offset = [0]

    def sample_fixed_values(_rng, _envelope, n: int) -> np.ndarray:
        start = offset[0]
        selected = draws[start : start + n]
        assert selected.shape == (n,)
        offset[0] += n
        return selected

    monkeypatch.setattr(
        MonteCarloPropagator,
        "_sample_from_envelope",
        staticmethod(sample_fixed_values),
    )
    return draws, offset


def test_b194_exact_symmetric_partial_draws_stay_candidate_and_retain_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draws = np.linspace(-1.0, 1.0, 100, dtype=np.float64)
    config = _config(mc_n_samples=100, mc_batch_size=100, mc_min_valid_samples=10)
    envelopes = {"x": _normal_env(0.0, 1.0)}

    complete_draws, complete_offset = _install_fixed_symmetric_draws(monkeypatch)
    complete = MonteCarloPropagator(config).propagate(
        lambda x: {"y": float(x)},
        {"x": 0.0},
        envelopes,
        ["y"],
    )[0]
    assert np.array_equal(complete_draws, draws)
    assert complete_offset == [100]
    assert complete.envelope.point_estimate == pytest.approx(0.0, abs=1e-7)
    assert complete.envelope.gate_eligible is True
    assert complete.envelope.confidence_level == pytest.approx(0.95)
    assert complete.envelope.sample_size == 100
    assert complete.diagnostics["n_valid"] == 100
    assert complete.diagnostics["draw_outcome_provenance"]["failure_records"] == []

    sampled: list[float] = []

    def refuse_negative_half(x: float) -> dict[str, float]:
        sampled.append(float(x))
        if x < 0.0:
            raise RuntimeError("input-dependent solver refusal")
        return {"y": float(x)}

    fixed_draws, offset = _install_fixed_symmetric_draws(monkeypatch)
    # Exercise the public propagator with the hand-specified rows, not a random sign count.
    partial = MonteCarloPropagator(config).propagate(
        refuse_negative_half,
        {"x": 0.0},
        envelopes,
        ["y"],
    )[0]

    assert np.array_equal(fixed_draws, draws)
    assert offset == [100]
    actual_draws = sampled[1:]  # First callback is the nominal-point preflight.
    assert actual_draws == pytest.approx(draws.tolist())
    assert len(actual_draws) == 100
    assert sum(value < 0.0 for value in actual_draws) == 50
    assert sum(value >= 0.0 for value in actual_draws) == 50

    # The 50 successful values have mean 50/99, while the complete matched run has mean 0.
    # The conditional value remains visible only as a candidate diagnostic, with no CI claim.
    assert partial.envelope.point_estimate == pytest.approx(50.0 / 99.0, abs=1e-6)
    assert partial.envelope.point_estimate != pytest.approx(0.0, abs=1e-3)
    assert partial.envelope.sample_size == 50
    assert partial.envelope.distribution_payload is not None
    assert partial.envelope.distribution_payload.samples == pytest.approx(tuple(draws[50:]))
    _require_candidate_only(partial)
    assert partial.diagnostics["n_samples"] == 100
    assert partial.diagnostics["n_valid"] == 50
    assert partial.diagnostics["n_failed"] == 50
    assert partial.diagnostics["output_coverage_complete"] is False
    provenance = partial.diagnostics["draw_outcome_provenance"]
    assert provenance["requested_draw_count"] == 100
    assert provenance["attempted_draw_count"] == 100
    assert provenance["successful_draw_count"] == 50
    assert provenance["unattempted_draw_count"] == 0
    assert provenance["outcome_denominator_complete"] is True
    assert tuple(row["draw_index"] for row in provenance["failure_records"]) == tuple(range(50))
    assert all(
        row["output_outcomes"]
        == [
            {
                "output_metric_id": "y",
                "outcome_code": "simulation_exception",
                "error_type": "RuntimeError",
            }
        ]
        for row in provenance["failure_records"]
    )


def test_b194_exact_symmetric_partial_draws_reach_fresh_normative_consumer(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, ctx, state = _build_node_context(
        tmp_path,
        run_id="R_b194_exact_symmetric_partial",
        metric_values={"y": 0},
        propagation_config={
            "preferred_method": "monte_carlo",
            "mc_n_samples": 100,
            "mc_batch_size": 100,
            "mc_min_valid_samples": 10,
            "mc_seed": 194,
            "compute_sensitivity": False,
        },
        propagation_sensitivity={"y": {"x": 1.0}},
    )
    fixed_draws, offset = _install_fixed_symmetric_draws(monkeypatch)

    def build_failing_fn(params, *, base_metric_values, nominal_params):
        del params, base_metric_values, nominal_params

        def fn(**current_params):
            x = float(current_params["x"])
            if x < 0.0:
                raise RuntimeError("input-dependent solver refusal")
            return {"y": x}

        fn._sensitivity_map = {"y": {"x": 1.0}}
        return fn, {"x"}

    monkeypatch.setattr(node_module, "_build_propagation_fn", build_failing_fn)
    produced = PropagateUncertaintyNode().execute(ctx, state)

    assert produced.status == "ok"
    assert offset == [100]
    simulation_ref = produced.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    simulation = SimulationResult.model_validate(
        from_canonical_bytes(store.get_bytes(simulation_ref.artifact_id))
    )
    envelope = load_uncertainty_envelope(
        _ensure_ir_artifact_store(store), simulation.uncertainty_envelopes["y"]
    )
    report = from_canonical_bytes(store.get_bytes(simulation.propagation_report_ref.artifact_id))
    assert envelope.point_estimate == pytest.approx(50.0 / 99.0, abs=1e-6)
    assert envelope.sample_size == 50
    assert envelope.gate_eligible is False
    assert envelope.interval_semantics is IntervalSemantics.HEURISTIC_RANGE
    assert envelope.confidence_level is None
    assert envelope.metadata["distribution_sample_semantics"] == (
        "successful_draws_only_conditional_on_execution"
    )
    assert report["incomplete_output_metric_ids"] == ["y"]
    provenance = report["draw_outcome_provenance"]
    assert provenance["requested_draw_count"] == 100
    assert provenance["attempted_draw_count"] == 100
    assert provenance["successful_draw_count"] == 50
    assert provenance["outcome_denominator_complete"] is True
    assert tuple(row["draw_index"] for row in provenance["failure_records"]) == tuple(range(50))

    trinity_ref = _persist_uncertainty_normative_frame(store)
    fresh_state = ExperimentState(
        run_id="R_b194_exact_symmetric_partial",
        inputs={INPUT_TRINITY_BUNDLE_REF: trinity_ref},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: simulation_ref},
    )
    consumed = RunNormativeArbitrationNode().execute(ctx, fresh_state)
    assert consumed.status == "ok"
    result_ref = consumed.state.artifacts_index[ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF]
    result = load_normative_arbitration_result(_ensure_ir_artifact_store(store), result_ref)
    assert result.model_completeness is NormativeModelCompleteness.PARTIAL
    assert any("propagation_metric_output_incomplete" in warning for warning in result.warnings)
    proposal = next(
        item for item in result.option_matrix if item.option is ArbitrationOption.PROPOSAL
    )
    assert "workers_uncertainty" not in proposal.binding_values
    assert result.rights_audit[0].status is NormativeAuditStatus.UNEVALUATED


def test_b194_typed_transient_retries_the_same_draw_without_changing_its_denominator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.foundry.uncertainty.monte_carlo import _sampled_input_digest

    _draws, offset = _install_fixed_symmetric_draws(monkeypatch)
    call_vectors: list[tuple[float, str]] = []
    transient_raised = False

    def intermittent(x: float) -> dict[str, float]:
        nonlocal transient_raised
        call_vectors.append((x, _sampled_input_digest({"x": x})))
        if x < 0 and not transient_raised:
            transient_raised = True
            raise PolicyOSError("temporary evaluator outage", category=ErrorCategory.TRANSIENT)
        return {"y": x}

    result = MonteCarloPropagator(
        _config(mc_n_samples=100, mc_batch_size=100, mc_min_valid_samples=10)
    ).propagate(
        intermittent,
        {"x": 0.0},
        {"x": _normal_env(0.0, 1.0)},
        ["y"],
    )[0]

    first_draw_attempts = call_vectors[1:3]
    assert len(first_draw_attempts) == 2
    assert first_draw_attempts[0] == first_draw_attempts[1]
    assert len(call_vectors) == 102  # One nominal call, 100 draws, and one same-draw retry.
    assert offset == [100]
    assert result.diagnostics["n_samples"] == 100
    assert result.diagnostics["n_valid"] == 100
    assert result.diagnostics["n_failed"] == 0
    provenance = result.diagnostics["draw_outcome_provenance"]
    assert provenance["requested_draw_count"] == 100
    assert provenance["attempted_draw_count"] == 100
    assert provenance["successful_draw_count"] == 100
    assert provenance["failure_records"] == []
    assert provenance["simulation_attempt_count"] == 102
    assert provenance["retry_attempt_count"] == 1


def test_b194_nominal_typed_transient_retry_does_not_consume_a_sample_draw() -> None:
    calls: list[float] = []
    transient = PolicyOSError("temporary nominal outage", category=ErrorCategory.TRANSIENT)

    def intermittent_nominal(x: float) -> dict[str, float]:
        calls.append(x)
        if len(calls) == 1:
            raise transient
        return {"y": x}

    result = MonteCarloPropagator(
        _config(mc_n_samples=100, mc_batch_size=100, mc_min_valid_samples=10)
    ).propagate(
        intermittent_nominal,
        {"x": 0.0},
        {"x": _normal_env(0.0, 1.0)},
        ["y"],
    )[0]

    assert calls[:2] == [0.0, 0.0]
    assert len(calls) == 102
    assert result.diagnostics["n_samples"] == 100
    assert result.diagnostics["n_valid"] == 100
    provenance = result.diagnostics["draw_outcome_provenance"]
    assert provenance["attempted_draw_count"] == 100
    assert provenance["simulation_attempt_count"] == 102
    assert provenance["retry_attempt_count"] == 1


def test_b194_sampler_transient_is_not_retried_as_an_evaluator_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transient = PolicyOSError("temporary sampler outage", category=ErrorCategory.TRANSIENT)
    sample_requests: list[int] = []
    evaluator_calls: list[float] = []

    def unavailable_sampler(_rng, _envelope, n: int) -> np.ndarray:
        sample_requests.append(n)
        raise transient

    def evaluator(x: float) -> dict[str, float]:
        evaluator_calls.append(x)
        return {"y": x}

    monkeypatch.setattr(
        MonteCarloPropagator, "_sample_from_envelope", staticmethod(unavailable_sampler)
    )
    with pytest.raises(PolicyOSError, match="temporary sampler outage") as raised:
        MonteCarloPropagator(
            _config(mc_n_samples=100, mc_batch_size=100, mc_min_valid_samples=10)
        ).propagate(
            evaluator,
            {"x": 0.0},
            {"x": _normal_env(0.0, 1.0)},
            ["y"],
        )

    assert raised.value is transient
    assert evaluator_calls == [0.0]
    assert sample_requests == [100]


def test_b194_exhausted_typed_transient_fails_closed_after_one_same_draw_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _draws, offset = _install_fixed_symmetric_draws(monkeypatch)
    transient = PolicyOSError("persistent evaluator outage", category=ErrorCategory.TRANSIENT)
    call_vectors: list[float] = []

    def unavailable_after_nominal(x: float) -> dict[str, float]:
        call_vectors.append(x)
        if len(call_vectors) == 1:
            return {"y": x}
        raise transient

    with pytest.raises(PolicyOSError, match="persistent evaluator outage") as raised:
        MonteCarloPropagator(
            _config(mc_n_samples=100, mc_batch_size=100, mc_min_valid_samples=10)
        ).propagate(
            unavailable_after_nominal,
            {"x": 0.0},
            {"x": _normal_env(0.0, 1.0)},
            ["y"],
        )

    assert raised.value is transient
    assert call_vectors == [0.0, -1.0, -1.0]
    assert offset == [100]


def test_b194_global_access_error_is_not_recorded_as_a_draw_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _draws, offset = _install_fixed_symmetric_draws(monkeypatch)

    def inaccessible_source(x: float) -> dict[str, float]:
        del x
        raise PermissionError("global model source is not readable")

    with pytest.raises(PermissionError, match="global model source is not readable"):
        MonteCarloPropagator(
            _config(mc_n_samples=100, mc_batch_size=100, mc_min_valid_samples=10)
        ).propagate(
            inaccessible_source,
            {"x": 0.0},
            {"x": _normal_env(0.0, 1.0)},
            ["y"],
        )

    assert offset == [0]


def test_b194_global_permission_error_after_nominal_preflight_escapes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _draws, offset = _install_fixed_symmetric_draws(monkeypatch)
    calls = 0

    def permission_fails_on_sampled_call(x: float) -> dict[str, float]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"y": float(x)}
        raise PermissionError("sampled call cannot read global model source")

    with pytest.raises(PermissionError, match="sampled call cannot read global model source"):
        MonteCarloPropagator(
            _config(mc_n_samples=100, mc_batch_size=100, mc_min_valid_samples=10)
        ).propagate(
            permission_fails_on_sampled_call,
            {"x": 0.0},
            {"x": _normal_env(0.0, 1.0)},
            ["y"],
        )

    assert calls == 2
    assert offset == [100]


def test_b194_global_and_unknown_causes_fail_closed_at_sampled_call_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ValidationPayload(BaseModel):
        value: int

    def invalid_payload_error() -> BaseException:
        try:
            _ValidationPayload.model_validate({"value": "invalid"})
        except ValidationError as exc:
            return exc
        raise AssertionError("invalid payload unexpectedly validated")

    def wrapped_source_error() -> BaseException:
        error = RuntimeError("wrapped source failure")
        error.__cause__ = OSError("source unavailable")
        return error

    def grouped_source_error() -> BaseException:
        return ExceptionGroup(
            "combined evaluation failure",
            [RuntimeError("solver refusal"), PermissionError("source denied")],
        )

    def wrapped_transient_error() -> BaseException:
        error = RuntimeError("wrapped temporary failure")
        error.__cause__ = PolicyOSError(
            "temporary evaluator outage", category=ErrorCategory.TRANSIENT
        )
        return error

    def cyclic_unknown_error() -> BaseException:
        error = RuntimeError("cyclic error context")
        error.__cause__ = error
        return error

    def truncated_unknown_error() -> BaseException:
        chain = [
            RuntimeError(f"wrapped-{index}") for index in range(EXCEPTION_CHAIN_NODE_LIMIT + 1)
        ]
        for index, outer in enumerate(chain[:-1]):
            outer.__cause__ = chain[index + 1]
        return chain[0]

    failures = (
        PermissionError("source denied"),
        wrapped_source_error(),
        invalid_payload_error(),
        grouped_source_error(),
        wrapped_transient_error(),
        cyclic_unknown_error(),
        truncated_unknown_error(),
        PolicyOSError("fatal service failure", category=ErrorCategory.FATAL),
        PolicyOSError("invalid service contract", category=ErrorCategory.VALIDATION),
    )
    for failure in failures:
        _draws, offset = _install_fixed_symmetric_draws(monkeypatch)
        calls = 0

        def evaluator(x: float, *, _failure: BaseException = failure) -> dict[str, float]:
            nonlocal calls
            calls += 1
            if calls == 1:  # The nominal preflight is available; the sampled call is not.
                return {"y": float(x)}
            raise _failure

        with pytest.raises(Exception) as raised:
            MonteCarloPropagator(
                _config(mc_n_samples=100, mc_batch_size=100, mc_min_valid_samples=10)
            ).propagate(
                evaluator,
                {"x": 0.0},
                {"x": _normal_env(0.0, 1.0)},
                ["y"],
            )

        assert raised.value is failure
        assert calls == 2
        assert offset == [100]


def test_b194_global_permission_error_does_not_persist_partial_node_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, ctx, state = _build_node_context(
        tmp_path,
        run_id="R_b194_global_permission_refusal",
        metric_values={"y": 0},
        propagation_config={
            "preferred_method": "monte_carlo",
            "mc_n_samples": 100,
            "mc_batch_size": 100,
            "mc_min_valid_samples": 10,
            "mc_seed": 194,
            "compute_sensitivity": False,
        },
        propagation_sensitivity={"y": {"x": 1.0}},
    )
    _draws, offset = _install_fixed_symmetric_draws(monkeypatch)
    original_ref = state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    original_bytes = store.get_bytes(original_ref.artifact_id)

    def build_inaccessible_fn(params, *, base_metric_values, nominal_params):
        del params, base_metric_values, nominal_params

        def fn(**current_params):
            x = float(current_params["x"])
            if x == 0.0:
                return {"y": 0.0}
            raise PermissionError("global model source is not readable")

        fn._sensitivity_map = {"y": {"x": 1.0}}
        return fn, {"x"}

    monkeypatch.setattr(node_module, "_build_propagation_fn", build_inaccessible_fn)

    with pytest.raises(PermissionError, match="global model source is not readable"):
        PropagateUncertaintyNode().execute(ctx, state)

    assert offset == [100]
    assert store.get_bytes(original_ref.artifact_id) == original_bytes
    unchanged = SimulationResult.model_validate(from_canonical_bytes(original_bytes))
    assert unchanged.uncertainty_envelopes is None
    assert unchanged.propagation_config_ref is None
    assert unchanged.propagation_report_ref is None
