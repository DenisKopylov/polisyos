"""Admission boundary for backtest trust grades."""

from __future__ import annotations

from polisyos.ir.analytics.backtest import BacktestScenario, SystematicBias


class TrustScorer:
    """Withhold trust authority until its owner admits a versioned purpose/profile.

    Descriptive error and empirical coverage remain available in the scenarios.
    A non-significant residual test does not establish equivalence, and perfect
    observed agreement does not establish a population trust grade. The former
    hard-coded weights and grade thresholds had no admitted purpose/profile or
    meaningful-bias margin; they cannot sign an authority-bearing result.
    """

    def compute(
        self,
        *,
        scenarios: list[BacktestScenario],
        biases: list[SystematicBias],
    ) -> tuple[float | None, str | None]:
        """Return unavailable authority without inventing the missing owner policy.

        Args:
            scenarios: Descriptive replay measurements retained by the report.
            biases: Residual diagnostics, not evidence of population equivalence.

        Returns:
            No trust score or grade. A future owner-admitted profile must define
            purpose, sampling assumptions and any equivalence margin before this
            boundary can admit authority.
        """
        return None, None


__all__ = ["TrustScorer"]
