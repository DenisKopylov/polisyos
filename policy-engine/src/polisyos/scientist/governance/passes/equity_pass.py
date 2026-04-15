"""Validate distributional fairness and vulnerable-group losses after simulation."""
from __future__ import annotations

from typing import List

from polisyos.common.logger import get_logger
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ProfileLevel
from polisyos.ir.analytics.distributional import (
    DistributionalReport,
    MetricUnit,
    load_distributional_report,
)
from polisyos.ir.refs import DistributionalReportRef
from polisyos.scientist.governance.accountability import resolve_governance_threshold
from polisyos.scientist.governance.passes._artifact_resolution import (
    resolve_optional_artifact_model,
)

logger = get_logger(__name__)


class EquityPass(ValidatorPass):
    """Evaluate the distributional report against profile-specific equity thresholds.

    Reads `distributional_report` directly from state or via
    `artifacts_index.distributional_report_ref` and `_store`. Threshold keys
    `equity_gini_increase_max`, `equity_vulnerable_loss_max_pct`, and
    `equity_max_losers_share` determine warning/blocker decisions; STRICT
    profiles emit blockers while other profiles downgrade most findings to
    warnings.
    """
    @property
    def pass_id(self) -> str:
        return "equity"

    @property
    def estimated_cost_ms(self) -> int:
        return 25

    def validate(self, ctx: PassContext) -> List[ComplianceIssue]:
        if self.pass_id not in ctx.profile.pass_ids:
            return []

        severity = self._resolve_severity(ctx)
        report_resolution = self._resolve_report(ctx, severity=severity)
        report = report_resolution.value
        if report is None:
            return list(report_resolution.issues)

        issues: list[ComplianceIssue] = list(report_resolution.issues)

        gini_threshold = resolve_governance_threshold(
            "equity_gini_increase_max",
            ctx.profile.thresholds,
        )
        vulnerable_threshold_pct = resolve_governance_threshold(
            "equity_vulnerable_loss_max_pct",
            ctx.profile.thresholds,
        )
        max_losers_share = resolve_governance_threshold(
            "equity_max_losers_share",
            ctx.profile.thresholds,
        )

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
    def _resolve_report(
        ctx: PassContext,
        *,
        severity: IssueSeverity,
    ):
        return resolve_optional_artifact_model(
            ctx=ctx,
            pass_id="equity",
            direct_key="distributional_report",
            ref_key="distributional_report_ref",
            model_cls=DistributionalReport,
            ref_model=DistributionalReportRef,
            load_model=load_distributional_report,
            severity=severity,
            code="EQUITY_REPORT_INVALID",
            message=(
                "Equity pass could not validate or load the distributional report."
            ),
            suggestion=(
                "Rebuild the distributional report before fairness governance checks."
            ),
            log=logger,
        )


def _normalize_percent_delta(value: float, unit: MetricUnit) -> float | None:
    if unit == MetricUnit.PERCENT:
        return value
    if unit == MetricUnit.RATIO:
        return value * 100.0
    return None


__all__ = ["EquityPass"]
