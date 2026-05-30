"""Validate refutation coverage and failed falsification tests on causal reports."""

from __future__ import annotations

from polisyos.common.logger import get_logger
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ProfileLevel
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
    RefutationTestType,
    load_causal_effect_report,
)
from polisyos.ir.registry.refs import CausalEffectReportRef
from polisyos.scientist.governance.passes._artifact_resolution import (
    resolve_optional_artifact_model,
)

_REQUIRED_TESTS: frozenset[RefutationTestType] = frozenset(
    {
        RefutationTestType.PLACEBO_TREATMENT,
        RefutationTestType.RANDOM_COMMON_CAUSE,
        RefutationTestType.DATA_SUBSET,
        RefutationTestType.BOOTSTRAP,
    }
)

_DOWHY_METHODS: frozenset[CausalMethod] = frozenset(
    {
        CausalMethod.DOWHY_BACKDOOR,
        CausalMethod.DOWHY_IV,
        CausalMethod.DOWHY_FRONTDOOR,
    }
)
logger = get_logger(__name__)


class RefutationPass(ValidatorPass):
    """Require DoWhy refutation-test evidence before promoting successful estimates.

    Reads `causal_report` directly or through
    `artifacts_index.causal_report_ref` and `_store`. Missing, incomplete, or
    failed required refutation tests emit `REFUTATION_*` findings; STRICT
    profiles emit blockers while other profiles warn.
    """

    @property
    def pass_id(self) -> str:
        return "refutation"

    @property
    def estimated_cost_ms(self) -> int:
        return 10

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        report_resolution = _resolve_report(ctx, severity=_severity_for_profile(ctx))
        report = report_resolution.value
        issues = list(report_resolution.issues)
        if report is None:
            return issues
        if report.status is not EstimationStatus.SUCCESS:
            return issues
        if report.method not in _DOWHY_METHODS:
            return issues

        severity = _severity_for_profile(ctx)
        if not report.refutation_results:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["causal_report", "refutation_results"],
                    message="Refutation results are missing for successful DoWhy estimate.",
                    severity=severity,
                    code="REFUTATION_MISSING",
                    suggestion=(
                        "Enable causal refutation or execute causal.refutation.dowhy_refute@1.0.0."
                    ),
                )
            )
            return issues

        observed_tests = {item.test_type for item in report.refutation_results}
        missing_tests = sorted(item.value for item in (_REQUIRED_TESTS - observed_tests))
        if missing_tests:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["causal_report", "refutation_results"],
                    message=(
                        "Required refutation tests are incomplete: " + ", ".join(missing_tests)
                    ),
                    severity=severity,
                    code="REFUTATION_TESTS_INCOMPLETE",
                    suggestion="Ensure all mandatory DoWhy refuters run and persist.",
                )
            )

        failed_tests = sorted(
            item.test_type.value
            for item in report.refutation_results
            if item.test_type in _REQUIRED_TESTS and not item.passed
        )
        if failed_tests:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["causal_report", "refutation_results"],
                    message="Refutation failed for tests: " + ", ".join(failed_tests),
                    severity=severity,
                    code="REFUTATION_FAILED",
                    suggestion="Review graph assumptions and treatment effect robustness.",
                )
            )

        return issues


def _resolve_report(ctx: PassContext, *, severity: IssueSeverity):
    return resolve_optional_artifact_model(
        ctx=ctx,
        pass_id="refutation",
        direct_key="causal_report",
        ref_key="causal_report_ref",
        model_cls=CausalEffectReport,
        ref_model=CausalEffectReportRef,
        load_model=load_causal_effect_report,
        severity=severity,
        code="REFUTATION_CAUSAL_REPORT_INVALID",
        message=("Refutation pass could not validate or load the causal report artifact."),
        suggestion=("Rebuild the causal report before evaluating refutation coverage."),
        log=logger,
    )


def _severity_for_profile(ctx: PassContext) -> IssueSeverity:
    if ctx.profile.level is ProfileLevel.STRICT:
        return IssueSeverity.BLOCKER
    return IssueSeverity.WARNING


__all__ = ["RefutationPass"]
