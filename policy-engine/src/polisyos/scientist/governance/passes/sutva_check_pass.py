"""Warn when the causal report suggests treatment interference or spillover risk."""

from __future__ import annotations

from typing import Literal

from polisyos.common.logger import get_logger
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ProfileLevel
from polisyos.ir.analytics.causal import CausalEffectReport, load_causal_effect_report
from polisyos.ir.refs import CausalEffectReportRef
from polisyos.scientist.governance.passes._artifact_resolution import (
    resolve_optional_artifact_model,
)

_SutvaRisk = Literal["high", "medium", "low"]
logger = get_logger(__name__)


class SutvaCheckPass(ValidatorPass):
    """Inspect causal diagnostics for spillover/interference risks on the active treatment.

    Reads `query_treatment`, a direct `causal_report`, or
    `artifacts_index.causal_report_ref` via `_store`. FAST profile skips the
    check; other profiles emit `SUTVA_VIOLATION_RISK` warnings so reviewers can
    decide whether the effect remains interpretable.
    """

    MARKET_WIDE_KEYWORDS: frozenset[str] = frozenset(
        {
            "tax_rate",
            "monetary_policy",
            "interest_rate",
            "trade_policy",
            "exchange_rate",
            "minimum_wage",
            "fiscal_policy",
            "subsidy",
            "tariff",
            "regulation",
            "licensing",
            "antitrust",
            "market_wide",
        }
    )

    @property
    def pass_id(self) -> str:
        return "sutva_check"

    @property
    def estimated_cost_ms(self) -> int:
        return 20

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        if ctx.profile.level is ProfileLevel.FAST:
            return []

        report_resolution = _resolve_report(ctx)
        report = report_resolution.value
        treatment = _resolve_treatment(ctx, report=report)
        risk = _resolve_risk(treatment=treatment, report=report)
        issues = list(report_resolution.issues)
        if risk is None or risk == "low":
            return issues

        path: list[str | int] = ["causal_report", "sutva_violation_risk"]
        if treatment:
            path = ["causal_query", "treatment"]
        scope_hint = f"Treatment '{treatment}'" if treatment else "Configured treatment"
        issues.append(
            ComplianceIssue(
                pass_id=self.pass_id,
                path=path,
                message=(
                    f"{scope_hint} appears market-wide. "
                    f"SUTVA may be violated (risk={risk}); estimates assume no interference."
                ),
                severity=IssueSeverity.WARNING,
                code="SUTVA_VIOLATION_RISK",
                suggestion=(
                    "Account for spillovers/general-equilibrium effects; "
                    "consider ABM bridge coverage, network.community.sbm_stratification@0.1.0 "
                    "for design-stage strata, or network.generative.ergm_null@0.1.0 "
                    "for a structural null diagnostic."
                ),
            )
        )
        return issues


def _resolve_treatment(
    ctx: PassContext,
    *,
    report: CausalEffectReport | None = None,
) -> str | None:
    value = ctx.state.get("query_treatment")
    if isinstance(value, str):
        candidate = value.strip()
        if candidate:
            return candidate

    if report is None:
        return None

    for key in ("treatment", "treatment_name"):
        raw = report.method_params.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    raw_meta = report.metadata.get("query_treatment")
    if isinstance(raw_meta, str) and raw_meta.strip():
        return raw_meta.strip()
    return None


def _resolve_report(ctx: PassContext):
    return resolve_optional_artifact_model(
        ctx=ctx,
        pass_id="sutva_check",
        direct_key="causal_report",
        ref_key="causal_report_ref",
        model_cls=CausalEffectReport,
        ref_model=CausalEffectReportRef,
        load_model=load_causal_effect_report,
        severity=IssueSeverity.WARNING,
        code="SUTVA_CAUSAL_REPORT_INVALID",
        message=("SUTVA check could not validate or load the causal report artifact."),
        suggestion=("Rebuild the causal report artifact before running governance validation."),
        log=logger,
    )


def _resolve_risk(
    *,
    treatment: str | None,
    report: CausalEffectReport | None,
) -> _SutvaRisk | None:
    if report is not None and report.sutva_violation_risk is not None:
        return report.sutva_violation_risk

    if not treatment:
        return None
    lowered = treatment.lower()
    if any(keyword in lowered for keyword in SutvaCheckPass.MARKET_WIDE_KEYWORDS):
        return "high"
    return None


__all__ = ["SutvaCheckPass"]
