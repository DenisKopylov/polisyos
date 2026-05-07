"""Public backtesting trust scorer module API."""

from __future__ import annotations

import numpy as np

from polisyos.core.evaluation import ThresholdBand, ThresholdMapper, WeightedScorer
from polisyos.ir.analytics.backtest import BacktestScenario, SystematicBias


class TrustScorer:
    """Aggregate backtest quality into trust score/grade."""

    _scorer = WeightedScorer({"coverage": 0.5, "mape": 0.3, "bias": 0.2})
    _grade_mapper = ThresholdMapper[str](
        [
            ThresholdBand(0.85, "A"),
            ThresholdBand(0.70, "B"),
            ThresholdBand(0.50, "C"),
            ThresholdBand(0.30, "D"),
            ThresholdBand(0.00, "F"),
        ],
        default="F",
    )

    def compute(
        self,
        *,
        scenarios: list[BacktestScenario],
        biases: list[SystematicBias],
    ) -> tuple[float | None, str | None]:
        if not scenarios:
            return None, None

        coverage_values = [
            scenario.coverage_probability
            for scenario in scenarios
            if scenario.coverage_probability is not None
        ]
        mape_values = [scenario.mape for scenario in scenarios if scenario.mape is not None]

        coverage_score = None
        avg_coverage = None
        if coverage_values:
            avg_coverage = float(np.mean(coverage_values))
            coverage_score = max(0.0, min(1.0, avg_coverage / 0.95))

        mape_score = None
        if mape_values:
            avg_mape = float(np.mean(mape_values))
            mape_score = max(0.0, 1.0 - avg_mape / 60.0)

        bias_penalty = 0.0
        for bias in biases:
            if bias.p_value is not None and bias.p_value < 0.01:
                bias_penalty += 0.15
            elif bias.p_value is not None and bias.p_value < 0.05:
                bias_penalty += 0.08
        bias_score = max(0.0, 1.0 - bias_penalty)

        result = self._scorer.score(
            {
                "coverage": coverage_score,
                "mape": mape_score,
                "bias": bias_score,
            }
        )
        if not result.effective_weights:
            return None, None
        trust_score = result.score
        grade = self._grade_mapper.map(trust_score)

        # Coverage-first gate: under-covered models cannot receive high trust.
        if avg_coverage is not None and avg_coverage < 0.50 and grade in {"A", "B"}:
            grade = "C"
        if avg_coverage is not None and avg_coverage < 0.30 and grade in {"A", "B", "C"}:
            grade = "D"

        return round(trust_score, 4), grade


__all__ = ["TrustScorer"]
