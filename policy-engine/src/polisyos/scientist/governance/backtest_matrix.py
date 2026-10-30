"""Run and summarize required historical backtest slices for promotion review.

The matrix runner groups `BacktestPlanBundle` inputs by `BacktestKind`, executes
them through the backtesting orchestrator, and persists a single
`BacktestReportRef` plus per-kind coverage diagnostics. Calibration governance
uses the resulting gap flags and worst-kind summary to block promotions when a
required observational regime is missing or weak.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.backtest import BacktestReportRef
from polisyos.ir.analytics.backtest import BacktestReport, BacktestScenario, persist_backtest_report
from polisyos.ir.observation.bundles import BacktestPlanBundle
from polisyos.ir.observation.contracts import ObservationFamily
from polisyos.scientist.methods.backtesting.orchestrator import (
    BacktestOrchestrator,
    _collapse_modes,
    _resolve_manifest_inputs,
    _resolve_report_id,
    _trust_scorer_profile,
)
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource
from polisyos.scientist.methods.backtesting.trust_scorer import TrustScorer


class BacktestKind(str, Enum):
    """Required backtest channel in calibration governance.

    The kinds partition historical validation into macro, cell,
    strategic-agent, household, and distress evidence slices so promotion
    decisions can require coverage across distinct observational regimes.
    """

    MACRO = "macro"
    CELL = "cell"
    STRATEGIC_AGENT = "strategic_agent"
    HOUSEHOLD = "household"
    DISTRESS = "distress"


_BACKTEST_KIND_FAMILIES: dict[BacktestKind, tuple[ObservationFamily, ...]] = {
    BacktestKind.MACRO: (ObservationFamily.MACRO_STATE,),
    BacktestKind.CELL: (
        ObservationFamily.BUDGET_FLOWS,
        ObservationFamily.PUBLIC_SERVICE_DOMAIN_FLOWS,
    ),
    BacktestKind.STRATEGIC_AGENT: (ObservationFamily.PROCUREMENT_FLOWS,),
    BacktestKind.HOUSEHOLD: (
        ObservationFamily.HOUSEHOLD_DISTRIBUTION,
        ObservationFamily.LABOR_MARKET,
    ),
    BacktestKind.DISTRESS: (ObservationFamily.DISTRESS_ENFORCEMENT,),
}


class BacktestKindResult(BaseModel):
    """Per-kind summary for one required backtest slice."""

    model_config = ConfigDict(extra="forbid")

    kind: BacktestKind
    status: str = Field(pattern="^(ok|gap|error)$")
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    n_plans: int = Field(default=0, ge=0)
    n_scenarios: int = Field(default=0, ge=0)
    scenario_ids: list[str] = Field(default_factory=list)
    observation_families: list[ObservationFamily] = Field(default_factory=list)
    gap_flag: str | None = None
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BacktestMatrixResult(BaseModel):
    """Aggregate calibration-governance view over all required backtest kinds.

    `gap_flags` enumerates missing evidence channels, `composite_score` provides
    the promotion score, and `backtest_report_ref` links to the persisted replay
    artifact for audit and downstream leaderboard scoring.
    """

    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(min_length=1)
    backtest_report_ref: BacktestReportRef | None = None
    kind_results: list[BacktestKindResult] = Field(default_factory=list)
    composite_score: float | None = Field(default=None, ge=0.0, le=1.0)
    worst_kind: BacktestKind | None = None
    gap_flags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class BacktestTrustProjection:
    """Recomputed TrustScorer result admitted for an exact-zero report."""

    status: str
    eligible: bool
    score: float | None
    grade: str | None
    reason: str | None = None


@dataclass(frozen=True)
class BacktestDiagnosticProjection:
    """Fresh whole-result check with a residual-only fallback for stale inference."""

    status: str
    recomputed: bool
    metric_diagnostics: list[dict[str, Any]] | None
    detected_biases: list[dict[str, Any]] | None
    reason: str | None = None


def _same_optional_float(actual: float | None, expected: float | None) -> bool:
    if expected is None:
        return actual is None
    return bool(
        actual is not None
        and math.isfinite(actual)
        and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
    )


def _residual_only_diagnostic_payloads(
    report: BacktestReport,
    *,
    reason: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    for item in report.metric_diagnostics:
        payload = item.model_dump(mode="json")
        if item.status != "exact_zero":
            payload.update(
                {
                    "status": "unavailable",
                    "method_id": None,
                    "backend_id": None,
                    "backend_version": None,
                    "statistic": None,
                    "p_value": None,
                    "reason": reason,
                }
            )
        diagnostics.append(payload)

    biases: list[dict[str, Any]] = []
    for item in report.detected_biases:
        payload = item.model_dump(mode="json")
        payload["statistical_test"] = "not_recomputed"
        payload["p_value"] = None
        metadata = dict(payload.get("metadata") or {})
        metadata["test_status"] = "unavailable"
        metadata["test_reason"] = reason
        payload["metadata"] = metadata
        biases.append(payload)
    return diagnostics, biases


def verify_backtest_diagnostic_projection(
    report: BacktestReport,
) -> BacktestDiagnosticProjection:
    """Recompute every persisted t-test against source rows before projection.

    Residual counts, signs, magnitudes, scopes, error summaries, and forecast
    interval coverage are reconciled by the IR model. This Scientist-side check
    extends that source binding across the actual SciPy method result, package
    version, test statistic, p-value, status, and descriptive-bias projections.
    A failed or unavailable inference keeps the validated residual description
    but removes every stale test result from reader output.
    """
    if not report.metric_diagnostics_are_source_bound():
        return BacktestDiagnosticProjection(
            status="unavailable",
            recomputed=False,
            metric_diagnostics=None,
            detected_biases=None,
            reason="metric_residuals_not_source_bound",
        )

    errors_by_metric: dict[str, list[float]] = {}
    for scenario in report.scenarios:
        for comparison in scenario.outcome_comparisons:
            errors_by_metric.setdefault(comparison.metric_name, []).append(
                comparison.y_pred - comparison.y_true
            )
    diagnostics = {item.metric_name: item for item in report.metric_diagnostics}
    if set(diagnostics) != set(errors_by_metric):
        return BacktestDiagnosticProjection(
            status="unavailable",
            recomputed=False,
            metric_diagnostics=None,
            detected_biases=None,
            reason="metric_diagnostics_not_source_bound",
        )

    results: dict[str, Any] = {}
    mismatched = False
    backend_unavailable = False
    for metric, values in sorted(errors_by_metric.items()):
        if all(value == 0.0 for value in values):
            continue
        try:
            result = BacktestOrchestrator._two_sided_ttest(np.asarray(values, dtype=float))
        except Exception:
            residuals, biases = _residual_only_diagnostic_payloads(
                report,
                reason="scipy_ttest_1samp_fresh_recompute_failed",
            )
            return BacktestDiagnosticProjection(
                status="unavailable",
                recomputed=False,
                metric_diagnostics=residuals,
                detected_biases=biases,
                reason="scipy_ttest_1samp_fresh_recompute_failed",
            )
        results[metric] = result
        if result.status == "unavailable":
            backend_unavailable = True
        diagnostic = diagnostics[metric]
        if (
            diagnostic.status != result.status
            or diagnostic.method_id != result.method_id
            or diagnostic.backend_id != result.backend_id
            or diagnostic.backend_version != result.backend_version
            or not _same_optional_float(diagnostic.statistic, result.statistic)
            or not _same_optional_float(diagnostic.p_value, result.p_value)
            or diagnostic.reason != result.reason
        ):
            mismatched = True

    bias_by_metric: dict[str, list[Any]] = {}
    for bias in report.detected_biases:
        for metric in bias.affected_metrics:
            bias_by_metric.setdefault(metric, []).append(bias)
    expected_bias_metrics: set[str] = set()
    any_nonzero = False
    for metric, values in errors_by_metric.items():
        mean = math.fsum(values) / len(values)
        exact_zero = all(value == 0.0 for value in values)
        if exact_zero:
            continue
        any_nonzero = True
        if f"metric_direction_not_established:{metric}" not in report.degraded_reasons:
            mismatched = True
        result = results.get(metric)
        if result is None:
            mismatched = True
            continue
        if result.p_value is None:
            expected_reason = f"bias_statistical_test_{result.status}:{metric}:{result.reason}"
            if expected_reason not in report.degraded_reasons:
                mismatched = True
        if mean == 0.0:
            continue
        expected_bias_metrics.add(metric)
        candidates = bias_by_metric.get(metric, [])
        if len(candidates) != 1:
            mismatched = True
            continue
        bias = candidates[0]
        expected_test = result.test_name or result.reason or "not_executed"
        expected_sign = "positive" if mean > 0 else "negative"
        expected_metadata = bias.metadata
        if (
            bias.bias_type != "descriptive_residual"
            or str(getattr(bias.direction, "value", bias.direction)) != "unknown"
            or bias.affected_metrics != [metric]
            or not math.isclose(bias.magnitude, abs(mean), rel_tol=1e-12, abs_tol=1e-12)
            or bias.statistical_test != expected_test
            or not _same_optional_float(bias.p_value, result.p_value)
            or expected_metadata.get("diagnostic") != "descriptive_residual"
            or expected_metadata.get("residual_sign") != expected_sign
            or expected_metadata.get("direction_status") != "not_established"
            or expected_metadata.get("test_status") != result.status
            or expected_metadata.get("test_reason") != result.reason
        ):
            mismatched = True
    if set(bias_by_metric) != expected_bias_metrics:
        mismatched = True
    expected_direction = "unknown" if any_nonzero else "neutral"
    if (
        str(getattr(report.overall_bias_direction, "value", report.overall_bias_direction))
        != expected_direction
    ):
        mismatched = True
    if any_nonzero and not report.degraded:
        mismatched = True

    if mismatched or backend_unavailable:
        reason = (
            "scipy_ttest_1samp_fresh_backend_unavailable"
            if backend_unavailable and not mismatched
            else "scipy_ttest_1samp_fresh_recompute_mismatch"
        )
        residuals, biases = _residual_only_diagnostic_payloads(report, reason=reason)
        return BacktestDiagnosticProjection(
            status="unavailable",
            recomputed=False,
            metric_diagnostics=residuals,
            detected_biases=biases,
            reason=reason,
        )

    return BacktestDiagnosticProjection(
        status="computed",
        recomputed=True,
        metric_diagnostics=[item.model_dump(mode="json") for item in report.metric_diagnostics],
        detected_biases=[item.model_dump(mode="json") for item in report.detected_biases],
    )


def verify_backtest_trust_projection(report: BacktestReport) -> BacktestTrustProjection:
    """Recompute trust before C5b, matrix, or packet projection."""
    if report.metadata.get("purpose") == "candidate_diagnostic":
        return BacktestTrustProjection(
            "unavailable", False, None, None, "candidate_diagnostic_not_for_trust"
        )
    diagnostics = verify_backtest_diagnostic_projection(report)
    if not diagnostics.recomputed:
        return BacktestTrustProjection("unavailable", False, None, None, diagnostics.reason)
    if not report.has_source_bound_exact_zero_metrics():
        return BacktestTrustProjection(
            "unavailable", False, None, None, "source_metrics_not_trust_eligible"
        )
    scorer = TrustScorer()
    profile = _trust_scorer_profile(scorer)
    if profile is None:
        return BacktestTrustProjection(
            "unavailable", False, None, None, "trust_scorer_profile_unavailable"
        )
    if report.metadata.get("trust_scorer_profile") != profile:
        return BacktestTrustProjection(
            "unavailable", False, None, None, "trust_scorer_profile_mismatch"
        )
    score, grade = scorer.compute(scenarios=report.scenarios, biases=report.detected_biases)
    if score is None or grade is None:
        return BacktestTrustProjection(
            "unavailable", False, None, None, "trust_scorer_output_unavailable"
        )
    if (
        report.trust_eligible is not True
        or report.trust_score is None
        or not math.isclose(report.trust_score, score, rel_tol=0.0, abs_tol=1e-12)
        or report.trust_grade != grade
    ):
        return BacktestTrustProjection(
            "unavailable", False, None, None, "trust_score_marker_mismatch"
        )
    return BacktestTrustProjection("recomputed", True, score, grade)


class BacktestMatrixRunner:
    """Runner that executes the required backtest matrix for promotion review.

    It fans out historical validation plans by `BacktestKind`, aggregates the
    resulting `BacktestReport`, and computes a composite score plus gap flags
    for any missing evidence channel.
    """

    def __init__(
        self,
        store: FileSystemCAS,
        *,
        orchestrator: BacktestOrchestrator | None = None,
    ) -> None:
        self._store = store
        self._orchestrator = orchestrator or BacktestOrchestrator(cas=store)

    def run(
        self,
        bundles: dict[BacktestKind, BacktestPlanBundle],
        *,
        report_id: str | None = None,
        inputs: list[InputRef] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> BacktestMatrixResult:
        """Execute all required backtest kinds and persist the aggregate report.

        Args:
            bundles: Backtest plans keyed by the required matrix slice.
            inputs: Optional provenance refs to attach to the persisted report.
            metadata: Additional report metadata propagated into the aggregate
                `BacktestReport`.

        Returns:
            `BacktestMatrixResult` with one `kind_results` item per required
            backtest kind, plus a persisted report ref and composite summary.
        """

        resolved_report_id = _resolve_report_id(
            report_id,
            generated_prefix="BTM_",
            metadata=metadata,
        )
        manifest_inputs = _resolve_manifest_inputs(self._store, inputs)
        role_requests = {
            (
                bundle.selected_training_role,
                bundle.selected_validation_role,
                bundle.selected_holdout_role,
            )
            for bundle in bundles.values()
            if any(
                (
                    bundle.selected_training_role,
                    bundle.selected_validation_role,
                    bundle.selected_holdout_role,
                )
            )
        }
        if len(role_requests) > 1:
            raise ValueError("backtest bundles disagree on the selected split role request")
        selected_roles = next(iter(role_requests), (None, None, None))
        selected_split_roles = {
            key: value
            for key, value in zip(
                ("training", "validation", "holdout"), selected_roles, strict=True
            )
            if value is not None
        }
        supplied_roles = (metadata or {}).get("selected_split_roles")
        if supplied_roles is not None and supplied_roles != selected_split_roles:
            raise ValueError("report request does not match selected split role bundles")

        materialized_plans = {
            kind: [HistoricalValidationPlan.model_validate(payload) for payload in bundle.plans]
            for kind, bundle in bundles.items()
        }
        for plans in materialized_plans.values():
            for plan in plans:
                params = (plan.scientist_state or {}).get("params", {})
                if (
                    plan.prediction_source is PredictionSource.SCIENTIST
                    and isinstance(params, dict)
                    and "backtest_native_forecast" in params
                ):
                    raise ValueError("native replay requires the selected backtest report producer")
        scenario_groups: dict[BacktestKind, list[BacktestScenario]] = defaultdict(list)
        kind_results: list[BacktestKindResult] = []
        report_scenarios: list[BacktestScenario] = []
        gap_flags: list[str] = []
        requested_modes: list[str] = []
        effective_modes: list[str] = []
        degraded_reasons: list[str] = []
        report_plans: list[HistoricalValidationPlan] = []

        for kind in BacktestKind:
            bundle = bundles.get(kind)
            plans = materialized_plans.get(kind, [])
            if bundle is None or not plans:
                gap_flag = (
                    bundle.gap_reason
                    if bundle is not None and bundle.gap_reason
                    else f"missing_backtest_bundle:{kind.value}"
                )
                gap_flags.append(gap_flag)
                kind_results.append(
                    BacktestKindResult(
                        kind=kind,
                        status="gap",
                        gap_flag=gap_flag,
                        observation_families=list(_BACKTEST_KIND_FAMILIES[kind]),
                        notes=[
                            f"Selected split evidence is unavailable: {gap_flag}."
                            if bundle is not None and bundle.gap_reason
                            else "No BacktestPlanBundle was supplied for this required backtest kind."
                        ],
                        metadata={
                            "selected_training_role": None
                            if bundle is None
                            else bundle.selected_training_role,
                            "selected_validation_role": None
                            if bundle is None
                            else bundle.selected_validation_role,
                            "selected_holdout_role": None
                            if bundle is None
                            else bundle.selected_holdout_role,
                            "gap_reason": None if bundle is None else bundle.gap_reason,
                        },
                    )
                )
                continue

            notes: list[str] = []
            for plan in plans:
                scenario_plan = self._decorate_plan(kind, bundle, plan)
                report_plans.append(scenario_plan)
                (
                    scenario,
                    scenario_warnings,
                    requested_mode,
                    effective_mode,
                    scenario_degraded_reasons,
                ) = self._orchestrator._run_single_scenario(scenario_plan)
                scenario.metadata = {
                    **dict(scenario.metadata),
                    "backtest_kind": kind.value,
                    "observation_families": [
                        family.value for family in _BACKTEST_KIND_FAMILIES[kind]
                    ],
                    "source_contract_id": bundle.contract_target.contract_id,
                    "source_contract_fqn": bundle.contract_target.contract_fqn,
                    "holdout_windows": list(bundle.holdout_windows),
                    **{
                        key: value
                        for key, value in (
                            ("selected_training_role", scenario_plan.selected_training_role),
                            ("selected_validation_role", scenario_plan.selected_validation_role),
                            ("selected_holdout_role", scenario_plan.selected_holdout_role),
                        )
                        if value is not None
                    },
                }
                scenario_groups[kind].append(scenario)
                report_scenarios.append(scenario)
                requested_modes.append(requested_mode)
                effective_modes.append(effective_mode)
                degraded_reasons.extend(str(item) for item in scenario_degraded_reasons)
                notes.extend(str(item) for item in scenario_warnings)

            scenarios_for_kind = scenario_groups[kind]
            kind_results.append(
                BacktestKindResult(
                    kind=kind,
                    status="ok",
                    score=_score_backtest_scenarios(scenarios_for_kind),
                    n_plans=len(plans),
                    n_scenarios=len(scenarios_for_kind),
                    scenario_ids=[scenario.scenario_id for scenario in scenarios_for_kind],
                    observation_families=list(_BACKTEST_KIND_FAMILIES[kind]),
                    notes=notes,
                    metadata={
                        "holdout_windows": list(bundle.holdout_windows),
                        "selected_split_roles": dict(selected_split_roles),
                        "historical_payload_keys": sorted(bundle.historical_payloads.keys()),
                    },
                )
            )

        report = self._orchestrator._aggregate(
            report_id=resolved_report_id,
            scenarios=report_scenarios,
            plans=report_plans,
            metadata={
                "backtest_kinds": {
                    result.kind.value: {
                        "status": result.status,
                        "score": result.score,
                        "gap_flag": result.gap_flag,
                    }
                    for result in kind_results
                },
                "required_backtest_kinds": [kind.value for kind in BacktestKind],
                "selected_split_roles": dict(selected_split_roles),
                **dict(metadata or {}),
            },
            prediction_mode_requested=_collapse_modes(requested_modes),
            prediction_mode_effective=_collapse_modes(effective_modes),
            degraded_reasons=degraded_reasons,
        )
        report_ref = persist_backtest_report(
            _ensure_ir_artifact_store(self._store), report, inputs=manifest_inputs
        )
        report.cas_artifact_id = str(report_ref.artifact_id)
        composite_score = _mean_defined(result.score for result in kind_results)
        scored_results = [result for result in kind_results if result.score is not None]
        worst_kind = (
            min(
                scored_results,
                key=lambda item: (item.score if item.score is not None else 1.0, item.kind.value),
            ).kind
            if scored_results
            else None
        )
        trust_projection = verify_backtest_trust_projection(report)
        return BacktestMatrixResult(
            report_id=report.report_id,
            backtest_report_ref=report_ref,
            kind_results=kind_results,
            composite_score=composite_score,
            worst_kind=worst_kind,
            gap_flags=gap_flags,
            metadata={
                "n_present_kinds": sum(1 for result in kind_results if result.status == "ok"),
                "report_degraded": report.degraded or not trust_projection.eligible,
                "report_trust_eligible": trust_projection.eligible,
            },
        )

    def _decorate_plan(
        self,
        kind: BacktestKind,
        bundle: BacktestPlanBundle,
        plan: HistoricalValidationPlan,
    ) -> HistoricalValidationPlan:
        role_updates: dict[str, str] = {}
        for key in (
            "selected_training_role",
            "selected_validation_role",
            "selected_holdout_role",
        ):
            expected = getattr(bundle, key)
            typed = getattr(plan, key)
            described = plan.metadata.get(key)
            if expected is not None and typed is not None and typed != expected:
                raise ValueError(f"{key} plan does not match selected role request")
            if expected is not None and described is not None and described != expected:
                raise ValueError(f"{key} metadata does not match selected role request")
            if typed is not None and described is not None and typed != described:
                raise ValueError(f"{key} plan metadata conflicts with typed role")
            resolved = expected if expected is not None else typed
            if resolved is not None:
                role_updates[key] = resolved
        decorated_metadata = {
            **dict(plan.metadata),
            **role_updates,
            "backtest_kind": kind.value,
            "observation_families": [family.value for family in _BACKTEST_KIND_FAMILIES[kind]],
            "source_contract_id": bundle.contract_target.contract_id,
        }
        return plan.model_copy(
            update={
                "plan_id": f"{kind.value}:{plan.plan_id}",
                "plan_label": f"{kind.value}:{plan.plan_label or plan.plan_id}",
                **role_updates,
                "metadata": decorated_metadata,
            }
        )


def _score_backtest_scenarios(scenarios: list[BacktestScenario]) -> float | None:
    if not scenarios:
        return None
    scenario_scores: list[float] = []
    for scenario in scenarios:
        components: list[float] = []
        if scenario.rmse is not None:
            components.append(1.0 / (1.0 + float(scenario.rmse)))
        if scenario.mae is not None:
            components.append(1.0 / (1.0 + float(scenario.mae)))
        if scenario.mape is not None:
            components.append(1.0 / (1.0 + (float(scenario.mape) / 100.0)))
        if scenario.coverage_probability is not None:
            components.append(float(scenario.coverage_probability))
        if not components:
            continue
        scenario_scores.append(sum(components) / len(components))
    return _clamp(_mean_defined(scenario_scores))


def _mean_defined(values) -> float | None:
    finite = [float(value) for value in values if value is not None]
    if not finite:
        return None
    return sum(finite) / len(finite)


def _clamp(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))


__all__ = [
    "BacktestKind",
    "BacktestKindResult",
    "BacktestMatrixResult",
    "BacktestMatrixRunner",
    "BacktestTrustProjection",
    "verify_backtest_trust_projection",
]
