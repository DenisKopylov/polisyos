from __future__ import annotations

from typing import Any, List

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.ir.analytics.distributional import DistributionalReport, MetricUnit, load_distributional_report
from polisyos.scientist.governance.profiles import ProfileLevel

from .base import PassContext, ValidatorPass


class EquityPass(ValidatorPass):
    @property
    def pass_id(self) -> str:
        return "equity"

    @property
    def estimated_cost_ms(self) -> int:
        return 25

    def validate(self, ctx: PassContext) -> List[ComplianceIssue]:
        if self.pass_id not in ctx.profile.pass_ids:
            return []

        report = self._resolve_report(ctx)
        if report is None:
            return []

        issues: list[ComplianceIssue] = []
        severity = self._resolve_severity(ctx)

        gini_threshold = float(ctx.profile.thresholds.get("equity_gini_increase_max", 0.02))
        vulnerable_threshold_pct = float(
            ctx.profile.thresholds.get("equity_vulnerable_loss_max_pct", -5.0)
        )
        max_losers_share = float(ctx.profile.thresholds.get("equity_max_losers_share", 0.60))

        if report.overall_gini_delta is not None and report.overall_gini_delta > gini_threshold:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["distributional_report", "overall_gini_delta"],
                    message=(
                        f"Gini increase {report.overall_gini_delta:.4f} exceeds threshold "
                        f"{gini_threshold:.4f}."
                    ),
                    severity=severity,
                    code="EQUITY_GINI_INCREASE",
                    suggestion=(
                        "Reduce regressive effects or add compensatory transfers "
                        "for lower-income cohorts."
                    ),
                )
            )

        for breakdown in report.breakdowns:
            for cohort in breakdown.cohorts:
                if not cohort.is_vulnerable:
                    continue
                raw_delta = cohort.metric_deltas.get(breakdown.primary_metric, 0.0)
                normalized = _normalize_percent_delta(raw_delta, breakdown.primary_metric_unit)
                if normalized is None:
                    continue
                if normalized < vulnerable_threshold_pct:
                    issues.append(
                        ComplianceIssue(
                            pass_id=self.pass_id,
                            path=[
                                "distributional_report",
                                "breakdowns",
                                breakdown.dimension.value,
                                cohort.cohort_id,
                            ],
                            message=(
                                f"Vulnerable cohort '{cohort.cohort_label}' has "
                                f"{normalized:+.2f}% impact ({breakdown.primary_metric})."
                            ),
                            severity=severity,
                            code="EQUITY_VULNERABLE_DISPROPORTIONATE",
                            suggestion=(
                                f"Review policy parameters for cohort '{cohort.cohort_label}' "
                                "or introduce targeted mitigation."
                            ),
                        )
                    )

        losers_share = report.winners_losers.total_losers_share
        if losers_share > max_losers_share:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["distributional_report", "winners_losers", "total_losers_share"],
                    message=(
                        f"Losers share {losers_share:.1%} exceeds threshold {max_losers_share:.1%}."
                    ),
                    severity=severity if ctx.profile.level == ProfileLevel.STRICT else IssueSeverity.WARNING,
                    code="EQUITY_EXCESSIVE_LOSERS",
                    suggestion="Narrow intervention scope or add transition support.",
                )
            )

        return issues

    @staticmethod
    def _resolve_severity(ctx: PassContext) -> IssueSeverity:
        if ctx.profile.level == ProfileLevel.STRICT:
            return IssueSeverity.BLOCKER
        return IssueSeverity.WARNING

    @staticmethod
    def _resolve_report(ctx: PassContext) -> DistributionalReport | None:
        direct = ctx.state.get("distributional_report")
        if isinstance(direct, DistributionalReport):
            return direct
        if isinstance(direct, dict):
            try:
                return DistributionalReport.model_validate(direct)
            except Exception:
                return None

        artifacts_index = ctx.state.get("artifacts_index")
        if not isinstance(artifacts_index, dict):
            return None

        ref = artifacts_index.get("distributional_report_ref")
        if ref is None:
            return None

        store = ctx.state.get("_store")
        if store is None:
            return None
        try:
            return load_distributional_report(store, ref)
        except Exception:
            return None


def _normalize_percent_delta(value: float, unit: MetricUnit) -> float | None:
    if unit == MetricUnit.PERCENT:
        return value
    if unit == MetricUnit.RATIO:
        return value * 100.0
    return None


__all__ = ["EquityPass"]
