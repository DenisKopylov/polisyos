from __future__ import annotations

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.analytics.causal import CausalEffectReport, CausalMethod, EstimationStatus
from polisyos.ir.analytics.transportability import (
    TransportabilityResult,
    TransportabilityStatus,
)
from polisyos.scientist.governance.passes.transportability_required_pass import (
    TransportabilityRequiredPass,
)


def _external_report(with_transport: bool) -> CausalEffectReport:
    transport = (
        TransportabilityResult(
            status=TransportabilityStatus.TRANSPORTABLE,
            final_confidence=0.8,
            query="P*(Y|do(X))",
        )
        if with_transport
        else None
    )
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
        method_params={"source_type": "external_literature"},
        transport_result=transport,
    )


def test_transportability_required_fast_skips() -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_report": _external_report(with_transport=False)},
        registry_bundle=None,
        profile=ValidationProfile.fast(),
        run_id="R_transport_pass_fast",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert issues == []


def test_transportability_required_mvp_warns_on_missing_transport_result() -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_report": _external_report(with_transport=False)},
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="R_transport_pass_mvp",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REQUIRED_MISSING"
    assert issues[0].severity == IssueSeverity.WARNING


def test_transportability_required_strict_blocks_on_missing_transport_result() -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_report": _external_report(with_transport=False)},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_transport_pass_strict",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REQUIRED_MISSING"
    assert issues[0].severity == IssueSeverity.BLOCKER


def test_transportability_required_passes_when_transport_result_present() -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_report": _external_report(with_transport=True)},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_transport_pass_ok",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert issues == []


def test_transportability_required_accepts_legacy_method_params_transport_result() -> None:
    report = _external_report(with_transport=False).model_copy(
        update={"method_params": {"source_type": "external_literature", "transport_result": {}}}
    )
    ctx = PassContext(
        ir=None,
        state={"causal_report": report},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_transport_pass_legacy",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert issues == []


def test_transportability_required_multireport_only_flags_external_missing_transport() -> None:
    internal = _external_report(with_transport=False).model_copy(
        update={"method_params": {"source_type": "internal_model"}}
    )
    external_without_transport = _external_report(with_transport=False)
    external_with_transport = _external_report(with_transport=True)

    ctx = PassContext(
        ir=None,
        state={
            "causal_effect_reports": [
                internal,
                external_without_transport,
                external_with_transport,
            ]
        },
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="R_transport_pass_multireport",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert len(issues) == 1
    issue = issues[0]
    assert isinstance(issue, ComplianceIssue)
    assert issue.code == "TRANSPORT_REQUIRED_MISSING"
    assert issue.path == ["causal_effect_reports", 1, "transport_result"]
    assert issue.severity == IssueSeverity.WARNING


def test_transportability_required_multireport_priority_skips_single_fallback() -> None:
    ctx = PassContext(
        ir=None,
        state={
            "causal_effect_reports": [],
            "causal_report": _external_report(with_transport=False),
        },
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_transport_pass_multireport_priority",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert issues == []
