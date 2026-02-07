from __future__ import annotations

import numpy as np

from polisyos.ir.backtest import BacktestScenario, SystematicBias


class TrustScorer:
    """Aggregate backtest quality into trust score/grade."""

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

        weighted = 0.0
        normalizer = 0.0
        if coverage_score is not None:
            weighted += 0.5 * coverage_score
            normalizer += 0.5
        if mape_score is not None:
            weighted += 0.3 * mape_score
            normalizer += 0.3
        weighted += 0.2 * bias_score
        normalizer += 0.2

        if normalizer <= 0:
            return None, None
        trust_score = max(0.0, min(1.0, weighted / normalizer))

        if trust_score >= 0.85:
            grade = "A"
        elif trust_score >= 0.70:
            grade = "B"
        elif trust_score >= 0.50:
            grade = "C"
        elif trust_score >= 0.30:
            grade = "D"
        else:
            grade = "F"

        # Coverage-first gate: under-covered models cannot receive high trust.
        if avg_coverage is not None and avg_coverage < 0.50 and grade in {"A", "B"}:
            grade = "C"
        if avg_coverage is not None and avg_coverage < 0.30 and grade in {"A", "B", "C"}:
            grade = "D"

        return round(trust_score, 4), grade


__all__ = ["TrustScorer"]
