"""Public passes refutation pass module API."""
from __future__ import annotations

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


class RefutationPass(ValidatorPass):
    """Refutation pass implementation."""
    @property
    def pass_id(self) -> str:
        return "refutation"

    @property
    def estimated_cost_ms(self) -> int:
        return 10

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        report = _resolve_report(ctx)
        if report is None:
            return []
        if report.status is not EstimationStatus.SUCCESS:
            return []
        if report.method not in _DOWHY_METHODS:
            return []

        severity = _severity_for_profile(ctx)
        issues: list[ComplianceIssue] = []
        if not report.refutation_results:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["causal_report", "refutation_results"],
                    message="Refutation results are missing for successful DoWhy estimate.",
                    severity=severity,
                    code="REFUTATION_MISSING",
                    suggestion=(
                        "Enable causal refutation or execute "
                        "causal.refutation.dowhy_refute@1.0.0."
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
                        "Required refutation tests are incomplete: "
                        + ", ".join(missing_tests)
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


def _severity_for_profile(ctx: PassContext) -> IssueSeverity:
    if ctx.profile.level is ProfileLevel.STRICT:
        return IssueSeverity.BLOCKER
    return IssueSeverity.WARNING


__all__ = ["RefutationPass"]
