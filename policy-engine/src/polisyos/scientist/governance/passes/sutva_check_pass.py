"""Public passes sutva check pass module API."""
from __future__ import annotations

from typing import Literal

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ProfileLevel
from polisyos.ir.analytics.causal import CausalEffectReport, load_causal_effect_report

_SutvaRisk = Literal["high", "medium", "low"]


class SutvaCheckPass(ValidatorPass):
    """Warn when treatment likely violates SUTVA assumptions."""

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

        treatment = _resolve_treatment(ctx)
        report = _resolve_report(ctx)
        risk = _resolve_risk(treatment=treatment, report=report)
        if risk is None or risk == "low":
            return []

        path: list[str | int] = ["causal_report", "sutva_violation_risk"]
        if treatment:
            path = ["causal_query", "treatment"]
        scope_hint = f"Treatment '{treatment}'" if treatment else "Configured treatment"
        return [
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
                    "consider ABM bridge coverage when available."
                ),
            )
        ]


def _resolve_treatment(ctx: PassContext) -> str | None:
    value = ctx.state.get("query_treatment")
    if isinstance(value, str):
        candidate = value.strip()
        if candidate:
            return candidate

    report = _resolve_report(ctx)
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


def _resolve_report(ctx: PassContext) -> CausalEffectReport | None:
    direct = ctx.state.get("causal_report")
    if isinstance(direct, CausalEffectReport):
        return direct
    if isinstance(direct, dict):
        try:
            return CausalEffectReport.model_validate(direct)
        except Exception:
            return None

    artifacts_index = ctx.state.get("artifacts_index")
    if not isinstance(artifacts_index, dict):
        return None
    ref = artifacts_index.get("causal_report_ref")
    if ref is None:
        return None
    store = ctx.state.get("_store")
    if store is None:
        return None
    try:
        return load_causal_effect_report(store, ref)
    except Exception:
        return None


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
