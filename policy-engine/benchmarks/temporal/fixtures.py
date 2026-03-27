"""Deterministic synthetic fixtures for temporal benchmark suites."""

from __future__ import annotations

from dataclasses import dataclass, field
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from benchmarks.temporal.common import TemporalBenchmarkFixture
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal.dtr import estimate_dtr_trajectory
from polisyos.foundry.methods.catalog.causal.g_computation import (
    estimate_g_computation_trajectory,
)
from polisyos.foundry.methods.catalog.causal.protocols import (
    DynamicTreatmentData,
    PanelObservationalData,
)
from polisyos.foundry.methods.catalog.causal.structural_time_series import (
    TemporalTrajectoryResult,
    estimate_structural_time_series_trajectory,
    solve_temporal_effect_path,
)
from polisyos.foundry.methods.catalog.causal.temporal_estimand_compiler import (
    TemporalCompileError,
    compile_temporal_estimand,
)
from polisyos.ir.artifacts import get_json_artifact
from polisyos.ir.analytics.dynamic_regime import (
    ContinuousTimeQuery,
    DynamicTreatmentRegime,
    InterventionInterpolationPolicy,
    RegimeRule,
    TemporalSamplingScheme,
    TemporalInterventionTrajectory,
    TemporalQueryMode,
    load_continuous_time_query,
    load_dynamic_treatment_regime,
    load_effect_trajectory_bundle,
    load_temporal_intervention_trajectory,
    persist_temporal_intervention_trajectory,
)
from polisyos.ir.refs import (
    ArtifactRefModel,
    DynamicTreatmentRegimeRef,
    EffectTrajectoryBundleRef,
    TemporalInterventionTrajectoryRef,
)
from polisyos.scientist.backtesting.temporal import (
    TemporalThresholds,
    evaluate_temporal_safe_rejection,
    evaluate_temporal_trajectory,
)


@dataclass(frozen=True)
class EngineTemporalExecution:
    trajectory: TemporalTrajectoryResult
    acceptance_checks: dict[str, bool]
    metadata: dict[str, Any] = field(default_factory=dict)


def gold_fixtures() -> list[TemporalBenchmarkFixture]:
    return [
        TemporalBenchmarkFixture(
            case_id="temporal_gold::ode_zero_diffusion_equivalence",
            scenario_label="Zero-diffusion ODE and linear-SDE equivalence",
            runner=_gold_ode_zero_diffusion_equivalence,
            tags=("temporal", "gold", "ode", "linear_sde"),
        ),
        TemporalBenchmarkFixture(
            case_id="temporal_gold::panel_delayed_effect",
            scenario_label="Panel delayed effect vs untreated donor path",
            runner=_gold_panel_delayed_effect,
            tags=("temporal", "gold", "panel"),
        ),
        TemporalBenchmarkFixture(
            case_id="temporal_gold::g_formula_always_vs_never",
            scenario_label="G-formula always-treat trajectory vs never-treat baseline",
            runner=_gold_g_formula_always_vs_never,
            tags=("temporal", "gold", "g_formula"),
        ),
        TemporalBenchmarkFixture(
            case_id="temporal_gold::dtr_optimal_vs_baseline",
            scenario_label="DTR optimal-regime trajectory vs baseline",
            runner=_gold_dtr_optimal_vs_baseline,
            tags=("temporal", "gold", "dtr"),
        ),
        TemporalBenchmarkFixture(
            case_id="temporal_gold::discrete_fallback_alignment",
            scenario_label="Discrete fallback alignment with diagnostics disclosure",
            runner=_gold_discrete_fallback_alignment,
            tags=("temporal", "gold", "fallback"),
        ),
    ]


def hidden_fixtures() -> list[TemporalBenchmarkFixture]:
    return [
        TemporalBenchmarkFixture(
            case_id="temporal_hidden::case_01",
            scenario_label="Hidden temporal stress case 01",
            runner=_hidden_lag_overshoot_plateau_case,
            tags=("temporal", "hidden", "shape"),
        ),
        TemporalBenchmarkFixture(
            case_id="temporal_hidden::case_02",
            scenario_label="Hidden temporal stress case 02",
            runner=_hidden_weak_signal_wide_band_case,
            tags=("temporal", "hidden", "band"),
        ),
        TemporalBenchmarkFixture(
            case_id="temporal_hidden::case_03",
            scenario_label="Hidden temporal stress case 03",
            runner=_hidden_fallback_required_case,
            tags=("temporal", "hidden", "fallback"),
        ),
        TemporalBenchmarkFixture(
            case_id="temporal_hidden::case_04",
            scenario_label="Hidden temporal stress case 04",
            runner=_hidden_diagnostics_omission_trap,
            tags=("temporal", "hidden", "diagnostics"),
        ),
        TemporalBenchmarkFixture(
            case_id="temporal_hidden::case_05",
            scenario_label="Hidden temporal stress case 05",
            runner=_hidden_irregular_grid_safe_rejection,
            tags=("temporal", "hidden", "research_gate"),
        ),
        TemporalBenchmarkFixture(
            case_id="temporal_hidden::case_06",
            scenario_label="Hidden temporal stress case 06",
            runner=_hidden_neural_cde_safe_rejection,
            tags=("temporal", "hidden", "research_gate"),
        ),
        TemporalBenchmarkFixture(
            case_id="temporal_hidden::case_07",
            scenario_label="Hidden temporal stress case 07",
            runner=_hidden_neural_sde_safe_rejection,
            tags=("temporal", "hidden", "research_gate"),
        ),
        TemporalBenchmarkFixture(
            case_id="temporal_hidden::case_08",
            scenario_label="Hidden temporal stress case 08",
            runner=_hidden_adaptive_policy_lineage_case,
            tags=("temporal", "hidden", "adaptive_policy"),
        ),
        TemporalBenchmarkFixture(
            case_id="temporal_hidden::case_09",
            scenario_label="Hidden temporal stress case 09",
            runner=_hidden_reloadable_cas_lineage_case,
            tags=("temporal", "hidden", "persistence"),
        ),
    ]


def _artifact_id(ch: str) -> str:
    return f"sha256:{ch * 64}"


def _artifact_ref(ch: str, *, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=_artifact_id(ch),
        kind=kind,
        media_type="application/json",
    )


def _query(
    *,
    outcome_process: str,
    horizon_end: float,
    intervention_ref: ArtifactRefModel | None,
    preferred_backend: str = "linear_sde",
    sampling_scheme: TemporalSamplingScheme = TemporalSamplingScheme.REGULAR_GRID,
    query_mode: TemporalQueryMode = TemporalQueryMode.FIXED_INTERVENTION,
    metadata: dict[str, Any] | None = None,
) -> ContinuousTimeQuery:
    return ContinuousTimeQuery(
        intervention_trajectory_ref=intervention_ref,
        query_mode=query_mode,
        outcome_process=outcome_process,
        horizon_start=0.0,
        horizon_end=horizon_end,
        time_scale="days",
        sampling_scheme=sampling_scheme,
        interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        metadata={"preferred_backend": preferred_backend, **dict(metadata or {})},
    )


def _intervention(
    *,
    time_points: list[float] | tuple[float, ...],
    values: list[float] | tuple[float, ...],
    interpolation_policy: InterventionInterpolationPolicy = InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
    metadata: dict[str, Any] | None = None,
) -> TemporalInterventionTrajectory:
    return TemporalInterventionTrajectory(
        time_points=tuple(float(value) for value in time_points),
        values=tuple(float(value) for value in values),
        time_scale="days",
        interpolation_policy=interpolation_policy,
        metadata=dict(metadata or {}),
    )


def _panel_delayed_data() -> PanelObservationalData:
    rng = np.random.default_rng(11)
    n_donors, n_periods, t0 = 4, 6, 4
    donors = np.cumsum(rng.normal(0.0, 0.15, size=(n_donors, n_periods)), axis=1)
    treated = donors.mean(axis=0).copy()
    treated[t0:] += np.array([1.2, 1.5], dtype=float)
    return PanelObservationalData(
        outcome=np.vstack([treated, donors]),
        treatment=np.array([1] + [0] * n_donors, dtype=int),
        time_treatment=t0,
        time_index=np.arange(n_periods, dtype=float),
    )


def _dynamic_g_data() -> DynamicTreatmentData:
    rng = np.random.default_rng(21)
    n_units, n_periods = 220, 4
    state = np.zeros((n_units, n_periods), dtype=float)
    treatment = np.zeros((n_units, n_periods), dtype=int)
    state[:, 0] = rng.normal(size=n_units)

    def sigmoid(values: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-values))

    for t in range(n_periods):
        treatment[:, t] = rng.binomial(1, sigmoid(0.5 * state[:, t]))
        if t < n_periods - 1:
            state[:, t + 1] = 0.5 * treatment[:, t] + 0.3 * state[:, t] + rng.normal(
                0.0,
                0.35,
                size=n_units,
            )

    outcome = treatment.sum(axis=1).astype(float) + state[:, 0] + rng.normal(0.0, 0.8, size=n_units)
    return DynamicTreatmentData(
        outcome=outcome,
        treatment_sequence=treatment,
        covariate_sequence=state[:, :, np.newaxis],
        time_ids=np.arange(n_periods, dtype=float),
        variable_names=["state"],
    )


def _dynamic_dtr_data() -> DynamicTreatmentData:
    rng = np.random.default_rng(77)
    n_units, n_periods = 260, 3
    state = np.zeros((n_units, n_periods), dtype=float)
    treatment = np.zeros((n_units, n_periods), dtype=int)
    state[:, 0] = rng.normal(0.0, 0.9, size=n_units)

    for t in range(n_periods):
        logits = 0.1 + 0.2 * state[:, t]
        probs = 1.0 / (1.0 + np.exp(-logits))
        treatment[:, t] = rng.binomial(1, probs)
        if t < n_periods - 1:
            state[:, t + 1] = (
                0.55 * state[:, t]
                + 0.45 * treatment[:, t] * (state[:, t] > 0.0)
                - 0.20 * treatment[:, t] * (state[:, t] <= 0.0)
                + rng.normal(0.0, 0.25, size=n_units)
            )

    stage_reward = (
        1.4 * treatment * (state > 0.0)
        - 0.7 * treatment * (state <= 0.0)
    ).sum(axis=1)
    outcome = stage_reward + 0.25 * state[:, 0] + rng.normal(0.0, 0.30, size=n_units)
    return DynamicTreatmentData(
        outcome=outcome,
        treatment_sequence=treatment,
        covariate_sequence=state[:, :, np.newaxis],
        time_ids=np.arange(n_periods, dtype=float),
        variable_names=["state"],
    )


def _trajectory_plan_panel(*, horizon_end: float, preferred_backend: str = "linear_sde"):
    panel = PanelObservationalData(
        outcome=np.vstack([np.linspace(0.0, max(horizon_end, 1.0), int(max(horizon_end, 1.0)) + 1), np.zeros(int(max(horizon_end, 1.0)) + 1), np.zeros(int(max(horizon_end, 1.0)) + 1)]),
        treatment=np.array([1, 0, 0], dtype=int),
        time_treatment=1,
        time_index=np.arange(int(max(horizon_end, 1.0)) + 1, dtype=float),
    )
    intervention = _intervention(
        time_points=list(np.arange(int(max(horizon_end, 1.0)) + 1, dtype=float)),
        values=[0.0] + [1.0] * int(max(horizon_end, 1.0)),
    )
    query = _query(
        outcome_process="synthetic_state",
        horizon_end=horizon_end,
        intervention_ref=_artifact_ref("a", kind="ir.temporal_intervention_trajectory"),
        preferred_backend=preferred_backend,
    )
    return compile_temporal_estimand(query, data=panel, resolved_intervention=intervention)


def _trajectory_with_custom_effect(
    effect_path: list[float],
    *,
    backend: str = "linear_sde",
    effect_samples: np.ndarray | None = None,
) -> TemporalTrajectoryResult:
    plan = _trajectory_plan_panel(horizon_end=float(len(effect_path) - 1), preferred_backend=backend)
    observed = np.asarray(effect_path, dtype=float)
    controls: dict[str, Any] = {"counterfactual_series": np.zeros_like(observed)}
    if effect_samples is not None:
        controls["effect_samples"] = effect_samples
    return solve_temporal_effect_path(
        plan,
        observed_series=observed,
        controls=controls,
    )


def _engine_temporal_trajectory(
    *,
    data: Any,
    intervention: TemporalInterventionTrajectory | None,
    outcome_process: str,
    horizon_end: float,
    regime: DynamicTreatmentRegime | None = None,
    preferred_backend: str = "linear_sde",
    temporal_estimator_method: str | None = None,
    sampling_scheme: TemporalSamplingScheme = TemporalSamplingScheme.REGULAR_GRID,
    query_mode: TemporalQueryMode = TemporalQueryMode.FIXED_INTERVENTION,
) -> EngineTemporalExecution:
    with tempfile.TemporaryDirectory(prefix="temporal-bench-") as tmpdir:
        store = FileSystemCAS(Path(tmpdir) / "cas")
        intervention_ref = (
            None
            if intervention is None
            else persist_temporal_intervention_trajectory(store, intervention)
        )
        metadata: dict[str, Any] = {}
        if temporal_estimator_method is not None:
            metadata["temporal_estimator_method"] = temporal_estimator_method
        query = _query(
            outcome_process=outcome_process,
            horizon_end=horizon_end,
            intervention_ref=intervention_ref,
            preferred_backend=preferred_backend,
            sampling_scheme=sampling_scheme,
            query_mode=query_mode,
            metadata=metadata,
        )
        engine = CausalEngine(registry=None, artifact_store=store)
        trajectory = engine.temporal_causal_effect(
            data,
            query,
            regime=regime,
            method=preferred_backend,
        )
        acceptance_checks, reload_metadata = _engine_acceptance_checks(
            store,
            trajectory,
            expects_fallback=trajectory.plan.fallback_mode.value == "discrete_time",
            requires_policy_lineage=query_mode is TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY,
        )
    return EngineTemporalExecution(
        trajectory=trajectory,
        acceptance_checks=acceptance_checks,
        metadata=reload_metadata,
    )


def _engine_acceptance_checks(
    store: FileSystemCAS,
    trajectory: TemporalTrajectoryResult,
    *,
    expects_fallback: bool = False,
    requires_policy_lineage: bool = False,
) -> tuple[dict[str, bool], dict[str, Any]]:
    bundle = trajectory.effect_bundle
    effect_bundle_artifact_id = trajectory.metadata.get("effect_bundle_artifact_id")
    artifact_loadability = False
    policy_lineage_complete = True
    reload_summary: dict[str, Any] = {
        "artifacts_expected": True,
        "bundle_artifact_id": effect_bundle_artifact_id,
    }
    if bundle is not None and effect_bundle_artifact_id is not None:
        try:
            bundle_ref = EffectTrajectoryBundleRef(artifact_id=str(effect_bundle_artifact_id))
            restored_bundle = load_effect_trajectory_bundle(store, bundle_ref)
            restored_query = load_continuous_time_query(store, restored_bundle.query_ref)
            get_json_artifact(store, restored_bundle.trajectory_ref.artifact_id)
            get_json_artifact(store, restored_bundle.confidence_band_ref.artifact_id)
            get_json_artifact(store, restored_bundle.solver_diagnostics_ref.artifact_id)

            intervention_payload = restored_bundle.metadata.get("intervention_artifact_ref")
            if intervention_payload is None and restored_query.intervention_trajectory_ref is not None:
                intervention_payload = restored_query.intervention_trajectory_ref.model_dump(
                    mode="python"
                )
            if intervention_payload is not None:
                load_temporal_intervention_trajectory(
                    store,
                    TemporalInterventionTrajectoryRef.model_validate(intervention_payload),
                )

            policy_payload = restored_bundle.metadata.get("policy_artifact_ref")
            derived_schedule_payload = restored_bundle.metadata.get("derived_schedule_ref")
            if policy_payload is not None:
                load_dynamic_treatment_regime(
                    store,
                    DynamicTreatmentRegimeRef.model_validate(policy_payload),
                )
            if derived_schedule_payload is not None:
                load_temporal_intervention_trajectory(
                    store,
                    TemporalInterventionTrajectoryRef.model_validate(derived_schedule_payload),
                )
            policy_lineage_complete = (
                policy_payload is not None and derived_schedule_payload is not None
            ) if (
                requires_policy_lineage
                or restored_bundle.metadata.get("execution_contract_kind")
                == "optimal_policy_discovery"
            ) else True
            artifact_loadability = True
            reload_summary.update(
                {
                    "query_loadable": True,
                    "trajectory_loadable": True,
                    "confidence_band_loadable": True,
                    "diagnostics_loadable": True,
                    "bundle_loadable": True,
                    "intervention_loadable": intervention_payload is not None,
                    "policy_loadable": policy_payload is not None,
                    "derived_schedule_loadable": derived_schedule_payload is not None,
                }
            )
        except Exception as exc:
            reload_summary["reload_error"] = str(exc)
            policy_lineage_complete = False
    else:
        policy_lineage_complete = False

    checks = {
        "engine_route_used": True,
        "bundle_present": bundle is not None,
        "artifact_kinds_valid": bundle is not None
        and bundle.query_ref.kind == "ir.continuous_time_query"
        and bundle.trajectory_ref.kind == "ir.temporal_trajectory"
        and bundle.confidence_band_ref.kind == "ir.temporal_confidence_band"
        and bundle.solver_diagnostics_ref.kind == "ir.temporal_solver_diagnostics",
        "diagnostics_artifact_present": bundle is not None and bundle.solver_diagnostics_ref.kind == "ir.temporal_solver_diagnostics",
        "artifact_loadability": artifact_loadability,
        "policy_lineage_complete": (
            policy_lineage_complete if requires_policy_lineage else True
        ),
        "truthful_fallback_disclosure": (
            trajectory.path_representation.value == "discrete_replay"
            and trajectory.discretization_error is None
            and trajectory.discretization_note == "unavailable_under_discrete_fallback"
            and bundle is not None
            and bundle.path_representation.value == "discrete_replay"
            and bundle.discretization_note == "unavailable_under_discrete_fallback"
            and bundle.continuous_time_degraded is True
        )
        if expects_fallback
        else (
            bundle is not None
            and bundle.path_representation.value != "discrete_replay"
            and bundle.continuous_time_degraded is False
        ),
    }
    return checks, reload_summary


def _gold_ode_zero_diffusion_equivalence():
    panel = PanelObservationalData(
        outcome=np.vstack([np.linspace(0.0, 4.0, 5), np.zeros(5), np.zeros(5)]),
        treatment=np.array([1, 0, 0], dtype=int),
        time_treatment=3,
        time_index=np.arange(5, dtype=float),
    )
    intervention = _intervention(
        time_points=[0.0, 1.0, 2.0, 3.0, 4.0],
        values=[0.0, 0.0, 0.0, 1.0, 1.0],
    )
    linear_run = _engine_temporal_trajectory(
        data=panel,
        intervention=intervention,
        outcome_process="panel_state",
        horizon_end=4.0,
        preferred_backend="linear_sde",
    )
    ode_run = _engine_temporal_trajectory(
        data=panel,
        intervention=intervention,
        outcome_process="panel_state",
        horizon_end=4.0,
        preferred_backend="ode",
    )
    linear = linear_run.trajectory
    ode = ode_run.trajectory
    return evaluate_temporal_trajectory(
        scenario_id="ode_zero_diffusion_equivalence",
        scenario_label="Zero-diffusion ODE and linear-SDE equivalence",
        trajectory=linear,
        expected_effect_path=ode.effect_path,
        expected_integral_effect=ode.integral_effect,
        thresholds=TemporalThresholds(
            max_path_rmse=1e-8,
            max_path_mae=1e-8,
            max_endpoint_abs_error=1e-8,
            max_integral_effect_abs_error=1e-8,
            min_band_coverage=1.0,
        ),
        extra_acceptance_checks={
            "matching_discretization_error": abs(linear.discretization_error - ode.discretization_error) <= 1e-12,
            **linear_run.acceptance_checks,
        },
        metadata={
            "expected_backend": "ode",
            "comparison_backend": "linear_sde",
            "runtime_path": "engine_temporal_causal_effect",
            **linear_run.metadata,
        },
    )


def _gold_panel_delayed_effect():
    execution = _engine_temporal_trajectory(
        data=_panel_delayed_data(),
        intervention=_intervention(
            time_points=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
            values=[0.0, 0.0, 0.0, 0.0, 1.0, 1.0],
        ),
        outcome_process="treated_outcome",
        horizon_end=5.0,
    )
    trajectory = execution.trajectory
    return evaluate_temporal_trajectory(
        scenario_id="panel_delayed_effect",
        scenario_label="Panel delayed effect vs untreated donors",
        trajectory=trajectory,
        expected_effect_path=[0.0, 0.0, 0.0, 0.0, 1.2, 1.5],
        thresholds=TemporalThresholds(
            max_path_rmse=0.25,
            max_integral_effect_abs_error=0.25,
            min_band_coverage=0.80,
        ),
        extra_acceptance_checks=execution.acceptance_checks,
        metadata={"runtime_path": "engine_temporal_causal_effect", **execution.metadata},
    )


def _gold_g_formula_always_vs_never():
    regime = DynamicTreatmentRegime(
        time_points=(0, 1, 2, 3),
        treatment_variables=("A_0", "A_1", "A_2", "A_3"),
        time_varying_covariates=("state",),
        outcome="Y",
        rule=RegimeRule.ALWAYS_TREAT,
    )
    execution = _engine_temporal_trajectory(
        data=_dynamic_g_data(),
        intervention=_intervention(
            time_points=[0.0, 1.0, 2.0, 3.0],
            values=[1.0, 1.0, 1.0, 1.0],
        ),
        outcome_process="state",
        horizon_end=3.0,
        regime=regime,
        temporal_estimator_method="parametric_g",
    )
    trajectory = execution.trajectory
    return evaluate_temporal_trajectory(
        scenario_id="g_formula_always_vs_never",
        scenario_label="G-formula always-treat trajectory vs never-treat baseline",
        trajectory=trajectory,
        expected_effect_path=[0.0, 0.5, 0.65, 0.695],
        expected_integral_effect=1.4975,
        thresholds=TemporalThresholds(
            max_path_rmse=0.35,
            max_integral_effect_abs_error=0.35,
            min_band_coverage=0.75,
        ),
        extra_acceptance_checks=execution.acceptance_checks,
        metadata={"runtime_path": "engine_temporal_causal_effect", **execution.metadata},
    )


def _gold_dtr_optimal_vs_baseline():
    execution = _engine_temporal_trajectory(
        data=_dynamic_dtr_data(),
        intervention=None,
        outcome_process="state",
        horizon_end=2.0,
        temporal_estimator_method="q_learning",
        query_mode=TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY,
    )
    trajectory = execution.trajectory
    return evaluate_temporal_trajectory(
        scenario_id="dtr_optimal_vs_baseline",
        scenario_label="DTR optimal-regime trajectory vs baseline",
        trajectory=trajectory,
        expected_effect_path=[0.0, 0.35, 0.55],
        expected_integral_effect=0.625,
        thresholds=TemporalThresholds(
            max_path_rmse=0.35,
            max_integral_effect_abs_error=0.35,
            min_band_coverage=0.75,
        ),
        extra_acceptance_checks={
            **execution.acceptance_checks,
            "adaptive_policy_rule": trajectory.diagnostics.get("optimal_regime_rule")
            == RegimeRule.THRESHOLD.value,
        },
        metadata={
            "runtime_path": "engine_temporal_causal_effect",
            "requires_policy_lineage": True,
            **execution.metadata,
        },
    )


def _gold_discrete_fallback_alignment():
    regime = DynamicTreatmentRegime(
        time_points=(0, 1, 2, 3),
        treatment_variables=("A_0", "A_1", "A_2", "A_3"),
        time_varying_covariates=("state",),
        outcome="Y",
        rule=RegimeRule.ALWAYS_TREAT,
    )
    execution = _engine_temporal_trajectory(
        data=_dynamic_g_data(),
        intervention=_intervention(
            time_points=[0.0, 1.0, 2.0, 3.0],
            values=[1.0, 1.0, 1.0, 1.0],
        ),
        outcome_process="state",
        horizon_end=2.5,
        regime=regime,
        temporal_estimator_method="parametric_g",
    )
    trajectory = execution.trajectory
    return evaluate_temporal_trajectory(
        scenario_id="discrete_fallback_alignment",
        scenario_label="Discrete fallback alignment with diagnostics completeness",
        trajectory=trajectory,
        expected_effect_path=[0.0, 0.5, 0.65],
        expected_integral_effect=0.825,
        thresholds=TemporalThresholds(
            max_path_rmse=0.35,
            max_integral_effect_abs_error=0.35,
            min_band_coverage=0.75,
        ),
        extra_acceptance_checks={
            "fallback_mode_discrete_time": trajectory.plan.fallback_mode.value == "discrete_time",
            **execution.acceptance_checks,
        },
        metadata={
            "runtime_path": "engine_temporal_causal_effect",
            "expects_fallback": True,
            **execution.metadata,
        },
    )


def _hidden_lag_overshoot_plateau_case():
    expected = [0.0, 0.25, 0.95, 1.25, 1.1, 1.0]
    trajectory = _trajectory_with_custom_effect(expected)
    return evaluate_temporal_trajectory(
        scenario_id="hidden_temporal_case_01",
        scenario_label="Hidden temporal stress case",
        trajectory=trajectory,
        expected_effect_path=expected,
        thresholds=TemporalThresholds(
            max_path_rmse=0.20,
            max_integral_effect_abs_error=0.25,
            min_band_coverage=1.0,
        ),
        metadata={"hidden_case_group": "shape"},
    )


def _hidden_weak_signal_wide_band_case():
    expected = [0.0, 0.05, 0.10, 0.08, 0.05]
    rng = np.random.default_rng(901)
    effect_samples = np.asarray(
        [np.asarray(expected, dtype=float) + rng.normal(0.0, 0.18, size=len(expected)) for _ in range(256)],
        dtype=float,
    )
    trajectory = _trajectory_with_custom_effect(expected, effect_samples=effect_samples)
    return evaluate_temporal_trajectory(
        scenario_id="hidden_temporal_case_02",
        scenario_label="Hidden temporal stress case",
        trajectory=trajectory,
        expected_effect_path=expected,
        thresholds=TemporalThresholds(
            max_path_rmse=0.20,
            max_integral_effect_abs_error=0.20,
            min_band_coverage=0.95,
        ),
        metadata={"hidden_case_group": "uncertainty"},
    )


def _hidden_fallback_required_case():
    regime = DynamicTreatmentRegime(
        time_points=(0, 1, 2, 3),
        treatment_variables=("A_0", "A_1", "A_2", "A_3"),
        time_varying_covariates=("state",),
        outcome="Y",
        rule=RegimeRule.ALWAYS_TREAT,
    )
    execution = _engine_temporal_trajectory(
        data=_dynamic_g_data(),
        intervention=_intervention(
            time_points=[0.0, 1.0, 2.0, 3.0],
            values=[1.0, 1.0, 1.0, 1.0],
        ),
        outcome_process="state",
        horizon_end=2.5,
        regime=regime,
        temporal_estimator_method="parametric_g",
    )
    trajectory = execution.trajectory
    return evaluate_temporal_trajectory(
        scenario_id="hidden_temporal_case_03",
        scenario_label="Hidden temporal stress case",
        trajectory=trajectory,
        expected_effect_path=[0.0, 0.5, 0.65],
        thresholds=TemporalThresholds(
            max_path_rmse=0.35,
            max_integral_effect_abs_error=0.35,
            min_band_coverage=0.70,
        ),
        extra_acceptance_checks={
            "fallback_mode_discrete_time": trajectory.plan.fallback_mode.value == "discrete_time",
            **execution.acceptance_checks,
        },
        metadata={
            "hidden_case_group": "fallback",
            "runtime_path": "engine_temporal_causal_effect",
            **execution.metadata,
        },
    )


def _hidden_diagnostics_omission_trap():
    trajectory = _trajectory_with_custom_effect([0.0, 0.2, 0.3, 0.35])
    malformed = trajectory.model_copy(
        update={
            "diagnostics": {
                "solver_family": trajectory.solver_family,
            }
        }
    )
    return evaluate_temporal_trajectory(
        scenario_id="hidden_temporal_case_04",
        scenario_label="Hidden temporal stress case",
        trajectory=malformed,
        expected_effect_path=[0.0, 0.2, 0.3, 0.35],
        thresholds=TemporalThresholds(
            max_path_rmse=0.20,
            max_integral_effect_abs_error=0.20,
            min_band_coverage=1.0,
        ),
        expected_outcome="diagnostic_failure",
        metadata={"hidden_case_group": "diagnostics_trap"},
    )


def _hidden_irregular_grid_safe_rejection():
    try:
        _engine_temporal_trajectory(
            data=_dynamic_g_data(),
            intervention=_intervention(
                time_points=[0.0, 1.0, 2.0, 3.0],
                values=[1.0, 1.0, 1.0, 1.0],
            ),
            outcome_process="state",
            horizon_end=3.0,
            preferred_backend="linear_sde",
            temporal_estimator_method="parametric_g",
            regime=DynamicTreatmentRegime(
                time_points=(0, 1, 2, 3),
                treatment_variables=("A_0", "A_1", "A_2", "A_3"),
                time_varying_covariates=("state",),
                outcome="Y",
                rule=RegimeRule.ALWAYS_TREAT,
            ),
            sampling_scheme=TemporalSamplingScheme.IRREGULAR_GRID,
        )
    except TemporalCompileError as exc:
        return evaluate_temporal_safe_rejection(
            scenario_id="hidden_temporal_case_05",
            scenario_label="Hidden temporal stress case",
            error=exc,
            expected_reason_code="research_gated_sampling_scheme",
            metadata={"hidden_case_group": "research_gate"},
        )
    raise AssertionError("expected irregular-grid temporal query to be rejected")


def _hidden_neural_cde_safe_rejection():
    try:
        _engine_temporal_trajectory(
            data=_dynamic_g_data(),
            intervention=_intervention(
                time_points=[0.0, 1.0, 2.0, 3.0],
                values=[1.0, 1.0, 1.0, 1.0],
            ),
            outcome_process="state",
            horizon_end=3.0,
            preferred_backend="neural_cde",
            temporal_estimator_method="parametric_g",
            regime=DynamicTreatmentRegime(
                time_points=(0, 1, 2, 3),
                treatment_variables=("A_0", "A_1", "A_2", "A_3"),
                time_varying_covariates=("state",),
                outcome="Y",
                rule=RegimeRule.ALWAYS_TREAT,
            ),
        )
    except TemporalCompileError as exc:
        return evaluate_temporal_safe_rejection(
            scenario_id="hidden_temporal_case_06",
            scenario_label="Hidden temporal stress case",
            error=exc,
            expected_reason_code="research_gated_backend",
            metadata={"hidden_case_group": "research_gate"},
        )
    raise AssertionError("expected neural_cde backend to be rejected")


def _hidden_neural_sde_safe_rejection():
    try:
        _engine_temporal_trajectory(
            data=_dynamic_g_data(),
            intervention=_intervention(
                time_points=[0.0, 1.0, 2.0, 3.0],
                values=[1.0, 1.0, 1.0, 1.0],
            ),
            outcome_process="state",
            horizon_end=3.0,
            preferred_backend="neural_sde",
            temporal_estimator_method="parametric_g",
            regime=DynamicTreatmentRegime(
                time_points=(0, 1, 2, 3),
                treatment_variables=("A_0", "A_1", "A_2", "A_3"),
                time_varying_covariates=("state",),
                outcome="Y",
                rule=RegimeRule.ALWAYS_TREAT,
            ),
        )
    except TemporalCompileError as exc:
        return evaluate_temporal_safe_rejection(
            scenario_id="hidden_temporal_case_07",
            scenario_label="Hidden temporal stress case",
            error=exc,
            expected_reason_code="research_gated_backend",
            metadata={"hidden_case_group": "research_gate"},
        )
    raise AssertionError("expected neural_sde backend to be rejected")


def _hidden_adaptive_policy_lineage_case():
    execution = _engine_temporal_trajectory(
        data=_dynamic_dtr_data(),
        intervention=None,
        outcome_process="state",
        horizon_end=2.0,
        temporal_estimator_method="q_learning",
        query_mode=TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY,
    )
    trajectory = execution.trajectory
    return evaluate_temporal_trajectory(
        scenario_id="hidden_temporal_case_08",
        scenario_label="Hidden temporal stress case",
        trajectory=trajectory,
        expected_effect_path=[0.0, 0.35, 0.55],
        expected_integral_effect=0.625,
        thresholds=TemporalThresholds(
            max_path_rmse=0.40,
            max_integral_effect_abs_error=0.40,
            min_band_coverage=0.70,
        ),
        extra_acceptance_checks={
            **execution.acceptance_checks,
            "adaptive_policy_rule": trajectory.diagnostics.get("optimal_regime_rule")
            == RegimeRule.THRESHOLD.value,
        },
        metadata={
            "hidden_case_group": "adaptive_policy",
            "runtime_path": "engine_temporal_causal_effect",
            "requires_policy_lineage": True,
            **execution.metadata,
        },
    )


def _hidden_reloadable_cas_lineage_case():
    execution = _engine_temporal_trajectory(
        data=_panel_delayed_data(),
        intervention=_intervention(
            time_points=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
            values=[0.0, 0.0, 0.0, 0.0, 1.0, 1.0],
        ),
        outcome_process="treated_outcome",
        horizon_end=5.0,
    )
    trajectory = execution.trajectory
    return evaluate_temporal_trajectory(
        scenario_id="hidden_temporal_case_09",
        scenario_label="Hidden temporal stress case",
        trajectory=trajectory,
        expected_effect_path=[0.0, 0.0, 0.0, 0.0, 1.2, 1.5],
        thresholds=TemporalThresholds(
            max_path_rmse=0.25,
            max_integral_effect_abs_error=0.25,
            min_band_coverage=0.80,
        ),
        extra_acceptance_checks=execution.acceptance_checks,
        metadata={
            "hidden_case_group": "persistence",
            "runtime_path": "engine_temporal_causal_effect",
            **execution.metadata,
        },
    )


__all__ = [
    "gold_fixtures",
    "hidden_fixtures",
]
