"""Replay historical validation plans and aggregate trust calibration/audit outputs."""
from __future__ import annotations

import json
import math
import uuid
from pathlib import Path
from typing import Any

import numpy as np

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.ir.analytics.backtest import (
    BacktestReport,
    BacktestScenario,
    BiasDirection,
    SystematicBias,
    persist_backtest_report,
)
from polisyos.scientist import run_experiment
from polisyos.scientist.backtesting.evaluator import PredictionEvaluator
from polisyos.scientist.backtesting.masking import OutcomeMasker
from polisyos.scientist.backtesting.plan import (
    HistoricalValidationPlan,
    PredictionSource,
)
from polisyos.scientist.backtesting.trust_scorer import TrustScorer


class BacktestOrchestrator:
    """Run scenario replay, score prediction quality, and persist a `BacktestReport`.

    The orchestrator separates masking/evaluation from the prediction source:
    plans may provide forecasts directly, ask Scientist to replay a workflow, or
    fall back to a naive baseline. Degraded Scientist predictions are surfaced in
    report metadata so trust scoring and calibration governance can audit replay
    quality.
    """

    def __init__(self, *, cas: FileSystemCAS | None = None, cas_root: str = ".polisyos") -> None:
        self._cas = cas or FileSystemCAS(Path(cas_root))
        self._masker = OutcomeMasker()
        self._evaluator = PredictionEvaluator()
        self._trust_scorer = TrustScorer()

    def run(
        self,
        plans: list[HistoricalValidationPlan],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> BacktestReport:
        """Execute every historical plan and persist the aggregated report in CAS."""
        report_id = f"BT_{uuid.uuid4().hex[:12]}"
        scenarios: list[BacktestScenario] = []
        warnings: list[str] = []
        requested_modes: list[str] = []
        effective_modes: list[str] = []
        degraded_reasons: list[str] = []

        for plan in plans:
            (
                scenario,
                scenario_warnings,
                prediction_mode_requested,
                prediction_mode_effective,
                scenario_degraded_reasons,
            ) = self._run_single_scenario(plan)
            scenarios.append(scenario)
            warnings.extend([f"{plan.plan_id}: {item}" for item in scenario_warnings])
            requested_modes.append(prediction_mode_requested)
            effective_modes.append(prediction_mode_effective)
            degraded_reasons.extend(
                [f"{plan.plan_id}: {item}" for item in scenario_degraded_reasons]
            )

        report = self._aggregate(
            report_id=report_id,
            scenarios=scenarios,
            metadata={"warnings": warnings, **(metadata or {})},
            prediction_mode_requested=_collapse_modes(requested_modes),
            prediction_mode_effective=_collapse_modes(effective_modes),
            degraded_reasons=degraded_reasons,
        )
        ref = persist_backtest_report(self._cas, report)
        report.cas_artifact_id = str(ref.artifact_id)
        return report

    def _run_single_scenario(
        self,
        plan: HistoricalValidationPlan,
    ) -> tuple[BacktestScenario, list[str], str, str, list[str]]:
        warnings: list[str] = []
        historical_data = self._load_historical_data(plan)
        masked_data = self._masker.mask(historical_data, plan)

        prediction_payload = self._predict(plan, masked_data)
        if prediction_payload.get("warnings"):
            warnings.extend(prediction_payload["warnings"])
        degraded_reasons = [
            str(item)
            for item in prediction_payload.get("degraded_reasons", [])
            if isinstance(item, str)
        ]
        y_pred = prediction_payload["predictions"]
        intervals = prediction_payload.get("intervals")

        scenario = self._evaluator.evaluate(
            scenario_id=plan.plan_id,
            scenario_label=plan.plan_label or plan.plan_id,
            y_pred=y_pred,
            y_true=plan.ground_truth_outcomes,
            intervals=intervals,
            confidence_level=plan.confidence_level,
            jurisdiction=plan.jurisdiction,
            intervention_date=plan.intervention_date,
            data_source=plan.historical_data_ref or plan.historical_data_path or "",
            metadata={
                "prediction_source_requested": plan.prediction_source.value,
                "prediction_source_effective": prediction_payload.get(
                    "prediction_mode_effective",
                    plan.prediction_source.value,
                ),
                "degraded": bool(prediction_payload.get("degraded", False)),
            },
        )
        return (
            scenario,
            warnings,
            plan.prediction_source.value,
            str(prediction_payload.get("prediction_mode_effective", plan.prediction_source.value)),
            degraded_reasons,
        )

    def _load_historical_data(self, plan: HistoricalValidationPlan) -> dict[str, Any]:
        if plan.historical_data_ref:
            artifact_id = ArtifactID.model_validate(plan.historical_data_ref)
            payload = from_canonical_bytes(self._cas.get_bytes(artifact_id))
            if not isinstance(payload, dict):
                raise ValueError(f"historical_data_ref must point to a JSON object: {plan.historical_data_ref}")
            return payload
        assert plan.historical_data_path is not None
        return json.loads(Path(plan.historical_data_path).read_text(encoding="utf-8"))

    def _predict(
        self,
        plan: HistoricalValidationPlan,
        masked_data: dict[str, Any],
    ) -> dict[str, Any]:
        if plan.prediction_source is PredictionSource.PROVIDED:
            return {
                "predictions": plan.predicted_outcomes or {},
                "intervals": plan.prediction_intervals or {},
                "warnings": [],
                "prediction_mode_effective": PredictionSource.PROVIDED.value,
                "degraded": False,
                "degraded_reasons": [],
            }
        if plan.prediction_source is PredictionSource.SCIENTIST:
            return self._predict_with_scientist(plan, masked_data)
        naive = self._predict_with_naive(plan, masked_data)
        naive["prediction_mode_effective"] = PredictionSource.NAIVE.value
        naive["degraded"] = False
        naive["degraded_reasons"] = []
        return naive

    def _predict_with_scientist(
        self,
        plan: HistoricalValidationPlan,
        masked_data: dict[str, Any],
    ) -> dict[str, Any]:
        warnings: list[str] = []
        if plan.scientist_state is None:
            reason = "scientist_state_missing"
            warnings.append("scientist_state missing; using naive predictor fallback")
            naive = self._predict_with_naive(plan, masked_data)
            naive["warnings"] = warnings + naive.get("warnings", [])
            naive["prediction_mode_effective"] = PredictionSource.NAIVE.value
            naive["degraded"] = True
            naive["degraded_reasons"] = [reason]
            return naive

        state_payload = dict(plan.scientist_state)
        params = dict(state_payload.get("params", {}))
        if plan.random_seed is not None:
            params["random_seed"] = plan.random_seed
        state_payload["params"] = params

        result = run_experiment(state_payload)
        artifacts = result.get("artifacts_index", {}) if isinstance(result, dict) else {}
        if not isinstance(artifacts, dict):
            reason = "scientist_artifacts_index_missing"
            warnings.append("scientist result has no artifacts_index; using naive fallback")
            naive = self._predict_with_naive(plan, masked_data)
            naive["warnings"] = warnings + naive.get("warnings", [])
            naive["prediction_mode_effective"] = PredictionSource.NAIVE.value
            naive["degraded"] = True
            naive["degraded_reasons"] = [reason]
            return naive

        metrics_ref_payload = artifacts.get("metrics_ref")
        predictions: dict[str, list[float]] = {}
        if isinstance(metrics_ref_payload, dict) and metrics_ref_payload.get("artifact_id"):
            try:
                artifact_id = ArtifactID.model_validate(metrics_ref_payload["artifact_id"])
                metrics_payload = from_canonical_bytes(self._cas.get_bytes(artifact_id))
                values = metrics_payload.get("values", metrics_payload)
                if isinstance(values, dict):
                    for metric in plan.target_metrics:
                        raw = values.get(metric)
                        horizon = len(plan.ground_truth_outcomes.get(metric, []))
                        if isinstance(raw, list):
                            predictions[metric] = [float(item) for item in raw[:horizon]]
                        elif isinstance(raw, (int, float)):
                            predictions[metric] = [float(raw)] * horizon
            except Exception as exc:
                warnings.append(f"failed to parse scientist metrics output: {exc}")

        intervals = self._extract_intervals_from_simulation_result(artifacts, plan)
        if not predictions:
            reason = "scientist_predictions_missing"
            warnings.append("scientist predictions missing; using naive fallback")
            naive = self._predict_with_naive(plan, masked_data)
            naive["warnings"] = warnings + naive.get("warnings", [])
            naive["prediction_mode_effective"] = PredictionSource.NAIVE.value
            naive["degraded"] = True
            naive["degraded_reasons"] = [reason]
            return naive
        return {
            "predictions": predictions,
            "intervals": intervals,
            "warnings": warnings,
            "prediction_mode_effective": PredictionSource.SCIENTIST.value,
            "degraded": False,
            "degraded_reasons": [],
        }

    def _extract_intervals_from_simulation_result(
        self,
        artifacts: dict[str, Any],
        plan: HistoricalValidationPlan,
    ) -> dict[str, list[tuple[float, float]]]:
        sim_ref_payload = artifacts.get("simulation_result_ref")
        if not isinstance(sim_ref_payload, dict) or not sim_ref_payload.get("artifact_id"):
            return {}

        try:
            sim_id = ArtifactID.model_validate(sim_ref_payload["artifact_id"])
            sim_payload = from_canonical_bytes(self._cas.get_bytes(sim_id))
        except Exception:
            return {}
        envelopes = sim_payload.get("uncertainty_envelopes")
        if not isinstance(envelopes, dict):
            return {}

        intervals: dict[str, list[tuple[float, float]]] = {}
        for metric in plan.target_metrics:
            ref_payload = envelopes.get(metric)
            if not isinstance(ref_payload, dict) or not ref_payload.get("artifact_id"):
                continue
            try:
                env_id = ArtifactID.model_validate(ref_payload["artifact_id"])
                env_payload = from_canonical_bytes(self._cas.get_bytes(env_id))
                ci = env_payload.get("confidence_interval")
                if isinstance(ci, (list, tuple)) and len(ci) == 2:
                    lo = float(ci[0])
                    hi = float(ci[1])
                    if lo > hi:
                        lo, hi = hi, lo
                    horizon = len(plan.ground_truth_outcomes.get(metric, []))
                    intervals[metric] = [(lo, hi)] * horizon
            except Exception:
                continue
        return intervals

    def _predict_with_naive(
        self,
        plan: HistoricalValidationPlan,
        masked_data: dict[str, Any],
    ) -> dict[str, Any]:
        predictions: dict[str, list[float]] = {}
        warnings: list[str] = []
        for metric in plan.target_metrics:
            horizon = len(plan.ground_truth_outcomes.get(metric, []))
            series_raw = masked_data.get(metric)
            if not isinstance(series_raw, (list, tuple)):
                baseline = 0.0
                warnings.append(f"metric '{metric}' missing in historical data; baseline=0 used")
            else:
                series = np.asarray(series_raw, dtype=float)
                finite = series[np.isfinite(series)]
                if finite.size == 0:
                    baseline = 0.0
                    warnings.append(f"metric '{metric}' has no finite pre-intervention values; baseline=0 used")
                elif finite.size == 1:
                    baseline = float(finite[-1])
                else:
                    baseline = float(np.mean(finite[-min(3, finite.size) :]))
            predictions[metric] = [baseline] * horizon
        return {"predictions": predictions, "intervals": {}, "warnings": warnings}

    def _aggregate(
        self,
        *,
        report_id: str,
        scenarios: list[BacktestScenario],
        metadata: dict[str, Any],
        prediction_mode_requested: str | None,
        prediction_mode_effective: str | None,
        degraded_reasons: list[str],
    ) -> BacktestReport:
        rmse_values = [item.rmse for item in scenarios if item.rmse is not None]
        mae_values = [item.mae for item in scenarios if item.mae is not None]
        mape_values = [item.mape for item in scenarios if item.mape is not None]
        coverage_values = [
            item.coverage_probability for item in scenarios if item.coverage_probability is not None
        ]

        biases = self._detect_systematic_biases(scenarios)
        degraded = bool(degraded_reasons)
        trust_eligible = not degraded
        trust_score, trust_grade = (None, None)
        if trust_eligible:
            trust_score, trust_grade = self._trust_scorer.compute(scenarios=scenarios, biases=biases)

        return BacktestReport(
            report_id=report_id,
            scenarios=scenarios,
            overall_rmse=float(np.mean(rmse_values)) if rmse_values else None,
            overall_mae=float(np.mean(mae_values)) if mae_values else None,
            overall_mape=float(np.mean(mape_values)) if mape_values else None,
            overall_coverage_probability=float(np.mean(coverage_values)) if coverage_values else None,
            n_scenarios=len(scenarios),
            n_metrics_evaluated=sum(len(item.outcome_comparisons) for item in scenarios),
            detected_biases=biases,
            overall_bias_direction=self._aggregate_bias_direction(biases),
            prediction_mode_requested=prediction_mode_requested,
            prediction_mode_effective=prediction_mode_effective,
            degraded=degraded,
            degraded_reasons=degraded_reasons,
            trust_eligible=trust_eligible,
            trust_score=trust_score,
            trust_grade=trust_grade,
            metadata=metadata,
        )

    def _detect_systematic_biases(self, scenarios: list[BacktestScenario]) -> list[SystematicBias]:
        errors_by_metric: dict[str, list[float]] = {}
        for scenario in scenarios:
            for comp in scenario.outcome_comparisons:
                errors_by_metric.setdefault(comp.metric_name, []).append(comp.y_pred - comp.y_true)

        biases: list[SystematicBias] = []
        for metric, errors in errors_by_metric.items():
            if len(errors) < 3:
                continue
            arr = np.asarray(errors, dtype=float)
            mean = float(np.mean(arr))
            std = float(np.std(arr, ddof=1))
            if std <= 1e-12:
                continue
            p_value = self._two_sided_ttest_pvalue(arr)
            if p_value is None or p_value >= 0.05:
                continue
            direction = BiasDirection.OPTIMISTIC if mean > 0 else BiasDirection.PESSIMISTIC
            biases.append(
                SystematicBias(
                    bias_type="directional",
                    direction=direction,
                    magnitude=float(abs(mean)),
                    affected_metrics=[metric],
                    description=(
                        f"Model systematically {'overestimates' if mean > 0 else 'underestimates'} "
                        f"metric '{metric}'"
                    ),
                    statistical_test="one-sample t-test H0(mean_error=0)",
                    p_value=float(p_value),
                )
            )
        return biases

    @staticmethod
    def _two_sided_ttest_pvalue(errors: np.ndarray) -> float | None:
        n = int(errors.shape[0])
        if n < 3:
            return None
        mean = float(np.mean(errors))
        std = float(np.std(errors, ddof=1))
        if std <= 1e-12:
            return None
        t_stat = mean / (std / math.sqrt(n))
        try:
            from scipy.stats import t as t_dist

            return float(2.0 * (1.0 - t_dist.cdf(abs(t_stat), df=n - 1)))
        except Exception:
            # Normal approximation fallback.
            from math import erf, sqrt

            z = abs(t_stat)
            cdf = 0.5 * (1.0 + erf(z / sqrt(2.0)))
            return float(2.0 * (1.0 - cdf))

    @staticmethod
    def _aggregate_bias_direction(biases: list[SystematicBias]) -> BiasDirection:
        if not biases:
            return BiasDirection.NEUTRAL
        directions = {item.direction for item in biases}
        if directions == {BiasDirection.OPTIMISTIC}:
            return BiasDirection.OPTIMISTIC
        if directions == {BiasDirection.PESSIMISTIC}:
            return BiasDirection.PESSIMISTIC
        if len(directions) > 1:
            return BiasDirection.MIXED
        return BiasDirection.NEUTRAL


__all__ = ["BacktestOrchestrator"]


def _collapse_modes(values: list[str]) -> str | None:
    unique = sorted({value for value in values if value})
    if not unique:
        return None
    if len(unique) == 1:
        return unique[0]
    return "mixed"
