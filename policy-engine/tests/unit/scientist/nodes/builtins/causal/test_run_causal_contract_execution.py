from __future__ import annotations

import logging
from datetime import date
from unittest.mock import patch

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
from polisyos.ir.governance.policy_spec import TemporalInterventionSequence
from polisyos.ir.model_layer.types import TimeFrequency
from polisyos.ir.observation.causal_execution import load_causal_execution_bundle
from polisyos.ir.observation.contract_compilers import (
    DynamicTreatmentCompileSpec,
    ObservationContractCompilerSuite,
)
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    ObservationFamily,
    ObservationPanel,
    ObservationRecord,
    SourceConfidenceTier,
    StrategicResponseChannel,
)
from polisyos.ir.registry.refs import CausalExecutionBundleRef
from polisyos.scientist.nodes.builtins.causal.run_causal_contract_execution import (
    RunCausalContractExecutionNode,
    TemporalInterventionSequenceCompiler,
    _to_dynamic_treatment,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_BOUNDS_BUNDLE_REF,
    ARTIFACT_CAUSAL_EXECUTION_BUNDLE_REF,
    ARTIFACT_DYNAMIC_TREATMENT_REGIME_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _build_ctx(tmp_path, *, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger(f"test.{run_id}"))


def test_temporal_intervention_sequence_compiler_is_scientist_owned() -> None:
    assert TemporalInterventionSequenceCompiler.__module__ == (
        "polisyos.scientist.nodes.builtins.causal.run_causal_contract_execution"
    )


def test_temporal_sequence_materialization_builds_valid_dynamic_treatment_data() -> None:
    sequence = TemporalInterventionSequence(
        sequence_id="ua_wage_support_sequence",
        dynamic_intervention_id="dynamic_wage_support",
        strategic_response_expected=True,
        transmission_channels=[StrategicResponseChannel.LABOR_CHANNEL],
        steps=[
            {"step_id": "s1", "effective_date": "2022-01", "intervention_id": "launch"},
            {"step_id": "s2", "effective_date": "2022-06", "intervention_id": "expand"},
            {"step_id": "s3", "effective_date": "2023-01", "intervention_id": "taper"},
        ],
    )

    dynamic = _to_dynamic_treatment(sequence, n_units=12)

    assert dynamic.treatment_sequence.shape == (12, 4)
    assert dynamic.covariate_sequence.shape == (12, 4, 2)
    assert dynamic.time_ids.tolist() == ["baseline", "2022-01", "2022-06", "2023-01"]
    assert dynamic.treatment_sequence[:, 0].sum() == 0
    assert dynamic.treatment_sequence[:, 1:].min() == 1
    assert dynamic.metadata["data_origin"] == "c6a_synthetic_scaffold"


def test_temporal_sequence_materialization_rejects_short_time_ids() -> None:
    sequence = TemporalInterventionSequence(
        sequence_id="ua_wage_support_sequence",
        dynamic_intervention_id="dynamic_wage_support",
        steps=[
            {"step_id": "s1", "effective_date": "2022-01", "intervention_id": "launch"},
            {"step_id": "s2", "effective_date": "2022-06", "intervention_id": "expand"},
            {"step_id": "s3", "effective_date": "2023-01", "intervention_id": "taper"},
        ],
    )

    with pytest.raises(ValueError, match="at least 4 periods"):
        _to_dynamic_treatment(
            sequence,
            n_units=12,
            time_ids=["baseline", "2022-01", "2022-06"],
        )


def _period(month: int) -> tuple[date, date]:
    return date(2024, month, 1), date(2024, month, 28)


def _dynamic_treatment_panel(n_units: int = 24, n_periods: int = 4) -> ObservationPanel:
    records: list[ObservationRecord] = []
    for unit_idx in range(n_units):
        unit_id = f"hh_{unit_idx:02d}"
        base_cov = 1.0 + unit_idx / 10.0
        for period_idx in range(n_periods):
            period_start, period_end = _period(period_idx + 1)
            treated = 1.0 if unit_idx % 2 == 0 and period_idx >= 1 else 0.0
            outcome = 2.0 + 0.5 * treated + 0.2 * period_idx + 0.05 * unit_idx
            metrics = {
                "outcome_score": outcome,
                "treatment": treated,
                "cov_a": base_cov,
                "cov_b": base_cov + period_idx / 10.0,
            }
            for metric_id, value in metrics.items():
                records.append(
                    ObservationRecord(
                        observation_id=f"obs_{unit_id}_{metric_id}_{period_idx}",
                        family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
                        time_grain=TimeFrequency.MONTH,
                        period_start=period_start,
                        period_end=period_end,
                        entity_scope=EntityScope.HOUSEHOLD,
                        entity_id=unit_id,
                        metric_id=metric_id,
                        observed_value=value,
                        unit="value",
                        coverage_estimate=0.95,
                        measurement_bias_flag=False,
                        censoring_mask=False,
                        trust_weight=1.0,
                        lag_days_estimate=1,
                        source_id="synthetic_dynamic_panel",
                        source_version="1.0",
                        regime_id="ua_2024",
                        shock_mask=False,
                        schema_regime_id="schema_v1",
                        identification_mode=IdentificationMode.SEQUENTIAL,
                        source_confidence_tier=SourceConfidenceTier.VALIDATED,
                    )
                )
    return ObservationPanel(
        panel_id="synthetic_dynamic_panel",
        family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
        time_grain=TimeFrequency.MONTH,
        records=records,
    )


def _direct_dynamic_treatment_data() -> DynamicTreatmentData:
    return DynamicTreatmentData(
        outcome=[1.0 + (idx % 4) for idx in range(24)],
        treatment_sequence=[[0, 1, 1], [0, 0, 1], [0, 1, 1], [0, 0, 1]] * 6,
        covariate_sequence=[
            [[0.1, 0.2], [0.2, 0.3], [0.3, 0.4]],
            [[0.5, 0.2], [0.6, 0.3], [0.7, 0.4]],
            [[0.2, 0.1], [0.3, 0.2], [0.4, 0.3]],
            [[0.8, 0.4], [0.9, 0.5], [1.0, 0.6]],
        ]
        * 6,
        time_ids=["baseline", "step_1", "step_2"],
        variable_names=["cov_a", "cov_b"],
    )


def test_temporal_compiler_runs_three_step_sequence_and_returns_dtr_result(tmp_path) -> None:
    compiler = TemporalInterventionSequenceCompiler(store=FileSystemCAS(tmp_path))

    result = compiler.compile(
        {
            "task_id": "temporal_sequence_task",
            "sequence_id": "ua_wage_support_sequence",
            "dynamic_intervention_id": "dynamic_wage_support",
            "steps": [
                {"effective_date": "2022-01", "intervention_id": "launch"},
                {"effective_date": "2022-06", "intervention_id": "expand"},
                {"effective_date": "2023-01", "intervention_id": "taper"},
            ],
            "n_units": 24,
            "params": {"n_bootstrap": 20},
        }
    )

    assert result.dynamic_treatment_data.treatment_sequence.shape == (24, 4)
    assert result.dtr_result is not None
    assert result.dtr_result.n_stages == 4
    assert result.entry.status == "ok"
    assert result.entry.dynamic_treatment_regime_ref is not None


def test_temporal_compiler_accepts_direct_dynamic_data_and_method_override(tmp_path) -> None:
    compiler = TemporalInterventionSequenceCompiler(store=FileSystemCAS(tmp_path))
    result = compiler.compile(
        {
            "task_id": "temporal_direct_task",
            "dynamic_treatment_data": _direct_dynamic_treatment_data().model_dump(mode="json"),
            "dtr_method": "a_learning",
            "params": {"n_bootstrap": 20},
        }
    )

    assert result.dtr_result is not None
    assert result.dtr_result.method == "a_learning"
    assert result.entry.metadata["source_precedence"] == "dynamic_treatment_data"
    assert result.entry.dynamic_treatment_regime_ref is not None


def test_c3_dynamic_treatment_artifact_flows_into_temporal_compiler(tmp_path) -> None:
    compiled = ObservationContractCompilerSuite().compile_all(
        observation_panel=_dynamic_treatment_panel(),
        dynamic_treatment_spec=DynamicTreatmentCompileSpec(
            spec_id="dynamic_treatment_spec",
            outcome_metric_id="outcome_score",
            treatment_metric_id="treatment",
            covariate_metric_ids=["cov_a", "cov_b"],
        ),
    )
    artifact = compiled.artifacts["dynamic_treatment_data"]
    result = TemporalInterventionSequenceCompiler(store=FileSystemCAS(tmp_path)).compile(
        {
            "task_id": "compiled_dynamic_task",
            "bundle_manifest": artifact.bundle.model_dump(mode="json"),
            "params": {"n_bootstrap": 20},
        }
    )

    assert result.entry.status == "ok"
    assert result.dtr_result is not None
    assert result.entry.dynamic_treatment_regime_ref is not None


def test_run_causal_contract_execution_node_persists_aggregate_and_primary_refs(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_c4b")
    state = ExperimentState(
        run_id="R_c4b",
        artifacts_index={},
        params={
            "bounds_estimation_tasks": [
                {
                    "task_id": "bounds_task",
                    "bounds_input": {
                        "outcome": [0.1, 0.2, 0.8, 0.9],
                        "treatment": [0.0, 0.0, 1.0, 1.0],
                        "instrument": [0.0, 1.0, 0.0, 1.0],
                    },
                    "bundle": {
                        "channels": [
                            {
                                "family": "household_distribution",
                                "bound_strategy": "iv_bounds",
                                "fallback_reason": "synthetic",
                            }
                        ]
                    },
                }
            ],
            "temporal_dtr_tasks": [
                {
                    "task_id": "temporal_task",
                    "sequence_id": "ua_seq",
                    "dynamic_intervention_id": "ua_dyn",
                    "steps": [
                        {"effective_date": "2022-01", "intervention_id": "launch"},
                        {"effective_date": "2022-06", "intervention_id": "expand"},
                        {"effective_date": "2023-01", "intervention_id": "taper"},
                    ],
                    "n_units": 24,
                    "params": {"n_bootstrap": 20},
                }
            ],
        },
    )

    outcome = RunCausalContractExecutionNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_CAUSAL_EXECUTION_BUNDLE_REF in outcome.state.artifacts_index
    assert ARTIFACT_BOUNDS_BUNDLE_REF in outcome.state.artifacts_index
    assert ARTIFACT_DYNAMIC_TREATMENT_REGIME_REF in outcome.state.artifacts_index

    bundle_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_EXECUTION_BUNDLE_REF]
    bundle = load_causal_execution_bundle(
        ctx.store,
        CausalExecutionBundleRef.model_validate(bundle_ref.model_dump(mode="json")),
    )
    assert len(bundle.bounds_results) == 1
    assert len(bundle.temporal_results) == 1
    assert bundle.bounds_results[0].status == "ok"
    assert bundle.temporal_results[0].status == "ok"
    assert isinstance(
        outcome.state.artifacts_index[ARTIFACT_CAUSAL_EXECUTION_BUNDLE_REF], ArtifactRef
    )


def test_run_causal_contract_execution_task_assertion_is_not_swallowed(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_c4b_assert")
    state = ExperimentState(
        run_id="R_c4b_assert",
        params={"bounds_estimation_tasks": [{"task_id": "bounds_task"}]},
    )

    with patch(
        "polisyos.scientist.nodes.builtins.causal.run_causal_contract_execution.BoundsEstimationTask.model_validate",
        side_effect=AssertionError("task validator invariant"),
    ):
        with pytest.raises(AssertionError, match="task validator invariant"):
            RunCausalContractExecutionNode().execute(ctx, state)
