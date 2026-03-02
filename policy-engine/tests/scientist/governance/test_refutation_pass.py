from __future__ import annotations

import pytest

from polisyos.core.governance.passes.base import IssueSeverity, PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
    RefutationResult,
    RefutationTestType,
)
from polisyos.scientist.governance.passes.refutation_pass import RefutationPass


def _base_report(method: CausalMethod) -> CausalEffectReport:
    return CausalEffectReport(
        method=method,
        status=EstimationStatus.SUCCESS,
        estimand="ATE",
        point_estimate=1.0,
        confidence_interval=(0.8, 1.2),
        inference_method="backdoor.linear_regression",
        sample_size=200,
        n_treated=100,
        n_control=100,
        pre_periods=0,
        post_periods=0,
    )


def _failed_refutations() -> list[RefutationResult]:
    return [
        RefutationResult(
            test_type=RefutationTestType.PLACEBO_TREATMENT,
            original_estimate=1.0,
            refuted_estimate=1.02,
            p_value=0.3,
            passed=True,
            effect_ratio=1.02,
            details={},
        ),
        RefutationResult(
            test_type=RefutationTestType.RANDOM_COMMON_CAUSE,
            original_estimate=1.0,
            refuted_estimate=0.6,
            p_value=0.01,
            passed=False,
            effect_ratio=0.6,
            details={},
        ),
        RefutationResult(
            test_type=RefutationTestType.DATA_SUBSET,
            original_estimate=1.0,
            refuted_estimate=0.99,
            p_value=0.5,
            passed=True,
            effect_ratio=0.99,
            details={},
        ),
        RefutationResult(
            test_type=RefutationTestType.BOOTSTRAP,
            original_estimate=1.0,
            refuted_estimate=1.01,
            p_value=0.4,
            passed=True,
            effect_ratio=1.01,
            details={},
        ),
    ]


@pytest.mark.parametrize(
    ("report", "expected_code"),
    [
        (_base_report(CausalMethod.DOWHY_BACKDOOR), "REFUTATION_MISSING"),
        (
            _base_report(CausalMethod.DOWHY_BACKDOOR).model_copy(
                update={"refutation_results": _failed_refutations()}
            ),
            "REFUTATION_FAILED",
        ),
    ],
)
def test_refutation_pass_strict_missing_or_failed_yields_blocker(report, expected_code) -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_report": report},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_refutation_strict",
    )

    issues = RefutationPass().validate(ctx)

    assert any(issue.code == expected_code for issue in issues)
    assert all(issue.severity == IssueSeverity.BLOCKER for issue in issues)


@pytest.mark.parametrize(
    ("report", "expected_code"),
    [
        (_base_report(CausalMethod.DOWHY_IV), "REFUTATION_MISSING"),
        (
            _base_report(CausalMethod.DOWHY_FRONTDOOR).model_copy(
                update={"refutation_results": _failed_refutations()}
            ),
            "REFUTATION_FAILED",
        ),
    ],
)
def test_refutation_pass_mvp_missing_or_failed_yields_warning(report, expected_code) -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_report": report},
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="R_refutation_mvp",
    )

    issues = RefutationPass().validate(ctx)

    assert any(issue.code == expected_code for issue in issues)
    assert all(issue.severity == IssueSeverity.WARNING for issue in issues)


def test_refutation_pass_non_dowhy_report_has_no_issues() -> None:
    report = _base_report(CausalMethod.SYNTHETIC_CONTROL)
    ctx = PassContext(
        ir=None,
        state={"causal_report": report},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_refutation_non_dowhy",
    )

    assert RefutationPass().validate(ctx) == []
