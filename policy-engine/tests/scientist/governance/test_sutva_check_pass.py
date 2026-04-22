from __future__ import annotations

from polisyos.core.contracts.lex import IssueSeverity
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.analytics.causal import CausalEffectReport, CausalMethod, EstimationStatus
from polisyos.scientist.governance.passes.sutva_check_pass import SutvaCheckPass


def _base_report() -> CausalEffectReport:
    return CausalEffectReport(
        method=CausalMethod.DOWHY_BACKDOOR,
        status=EstimationStatus.SUCCESS,
        estimand="ATE",
        point_estimate=1.0,
        confidence_interval=(0.8, 1.2),
        inference_method="backdoor.linear_regression",
        sample_size=100,
        n_treated=50,
        n_control=50,
        pre_periods=0,
        post_periods=0,
    )


def test_sutva_check_warns_for_market_wide_treatment() -> None:
    ctx = PassContext(
        ir=None,
        state={"query_treatment": "tax_rate"},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_sutva_tax",
    )

    issues = SutvaCheckPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "SUTVA_VIOLATION_RISK"
    assert issues[0].severity == IssueSeverity.WARNING
    assert "sbm_stratification" in issues[0].suggestion
    assert "ergm_null" in issues[0].suggestion


def test_sutva_check_no_issue_for_neutral_treatment() -> None:
    ctx = PassContext(
        ir=None,
        state={"query_treatment": "pilot_training_grant"},
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="R_sutva_neutral",
    )

    issues = SutvaCheckPass().validate(ctx)

    assert issues == []


def test_sutva_check_uses_report_risk_when_present() -> None:
    report = _base_report().model_copy(update={"sutva_violation_risk": "high"})
    ctx = PassContext(
        ir=None,
        state={"causal_report": report},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_sutva_report",
    )

    issues = SutvaCheckPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "SUTVA_VIOLATION_RISK"
    assert "sbm_stratification" in issues[0].suggestion


def test_sutva_check_invalid_report_payload_emits_warning() -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_report": {"invalid": True}},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_sutva_invalid",
    )

    issues = SutvaCheckPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "SUTVA_CAUSAL_REPORT_INVALID"
    assert issues[0].severity == IssueSeverity.WARNING
