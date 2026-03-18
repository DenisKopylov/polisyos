"""DiagnosticDashboardData — aggregated diagnostic view for a single causal run.

Collects positivity, support mismatch, covariate balance, parallel trends,
sensitivity, and falsification diagnostics into a single machine-readable
object intended for the audit UI and downstream quality scoring.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.covariate_balance import CovariateBalanceReport
from polisyos.ir.analytics.falsification_report import FalsificationReport, FalsificationTest


class DiagnosticDashboardData(BaseModel):
    """Aggregated diagnostic view for one causal analysis run.

    All diagnostic sub-objects are optional — only populated when the
    corresponding diagnostic was executed for this estimand/method combination.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    query_str: str = ""
    created_at: str = ""

    # ------------------------------------------------------------------
    # Individual diagnostics (all optional)
    # ------------------------------------------------------------------

    positivity: dict[str, Any] | None = None
    """PositivityDiagnostic result dict (from node_outputs["result"])."""

    support_mismatch: dict[str, Any] | None = None
    """SupportMismatchDiagnostic result dict."""

    covariate_balance: CovariateBalanceReport | None = None
    """Standardised mean difference report."""

    parallel_trends: FalsificationTest | None = None
    """Single parallel trends check (for DiD estimands)."""

    sensitivity: dict[str, Any] | None = None
    """SensitivityResult serialised as dict."""

    falsification: FalsificationReport | None = None
    """All falsification / refutation tests aggregated."""

    # ------------------------------------------------------------------
    # Aggregate summary
    # ------------------------------------------------------------------

    n_diagnostics_run: int = 0
    """Total number of diagnostic sub-checks executed."""

    n_passed: int = 0
    """Diagnostics that passed their check criterion."""

    n_failed: int = 0
    """Diagnostics that failed their check criterion."""

    n_warnings: int = 0
    """Diagnostics that passed but with warnings."""

    overall_passed: bool = True
    """True when no *critical* diagnostic failed."""

    # ------------------------------------------------------------------
    # UI-facing boolean flags
    # ------------------------------------------------------------------

    has_overlap_issues: bool = False
    has_balance_issues: bool = False
    has_falsification_failures: bool = False
    has_robustness_concerns: bool = False

    @classmethod
    def from_node_outputs(
        cls,
        run_id: str,
        query_str: str,
        node_outputs: dict[str, dict],
        *,
        created_at: str = "",
    ) -> "DiagnosticDashboardData":
        """Build a DiagnosticDashboardData from CausalEngine node_outputs.

        Scans every node output for known diagnostic keys and assembles
        the dashboard object.
        """
        positivity_result: dict[str, Any] | None = None
        support_result: dict[str, Any] | None = None
        sensitivity_result: dict[str, Any] | None = None
        pt_result: dict[str, Any] | None = None
        balance_report: CovariateBalanceReport | None = None

        for outputs in node_outputs.values():
            if not isinstance(outputs, dict):
                continue
            result = outputs.get("result")
            if isinstance(result, dict):
                # PositivityDiagnostic result
                if "passes_positivity" in result and positivity_result is None:
                    positivity_result = result
                # SupportMismatchDiagnostic result
                elif "passes_support_check" in result and support_result is None:
                    support_result = result
                # ParallelTrendsCheck result
                elif result.get("test_name") == "parallel_trends_check" and pt_result is None:
                    pt_result = result

            # SensitivityResult object
            sr = outputs.get("sensitivity_result")
            if sr is not None and sensitivity_result is None:
                sensitivity_result = _serialize_sensitivity(sr)

            # CovariateBalanceReport — from estimators that compute SMDs after weighting
            if balance_report is None:
                cb = outputs.get("covariate_balance")
                if isinstance(cb, CovariateBalanceReport):
                    balance_report = cb
                elif isinstance(cb, dict) and "variable_smd" in cb:
                    try:
                        balance_report = CovariateBalanceReport.model_validate(cb)
                    except Exception:
                        pass

        # Parallel trends → FalsificationTest
        pt_test: FalsificationTest | None = None
        if pt_result is not None:
            from polisyos.ir.analytics.falsification_report import FalsificationTestKind
            pt_test = FalsificationTest(
                test_name="parallel_trends_check",
                test_kind=FalsificationTestKind.PARALLEL_TRENDS,
                passed=bool(pt_result.get("passed", True)),
                statistic=pt_result.get("statistic"),
                p_value=pt_result.get("p_value"),
                interpretation=(
                    "Pre-treatment slope equality: "
                    + ("passed" if pt_result.get("passed", True) else "FAILED")
                ),
                is_critical=True,
            )

        # Falsification report from refutation outputs
        falsification = FalsificationReport.from_dowhy_refute_outputs(node_outputs)
        if falsification.n_passed == 0 and falsification.n_failed == 0:
            falsification = None  # type: ignore[assignment]

        # Aggregate counts
        n_run = 0
        n_pass = 0
        n_fail = 0
        n_warn = 0

        has_overlap = False
        has_balance = False
        has_falsification = False
        has_robustness = False

        if positivity_result is not None:
            n_run += 1
            passes = bool(positivity_result.get("passes_positivity", True))
            ess = float(positivity_result.get("ess_fraction", 1.0))
            if passes:
                if ess < 0.3:
                    n_warn += 1
                else:
                    n_pass += 1
            else:
                n_fail += 1
                has_overlap = True

        if support_result is not None:
            n_run += 1
            if bool(support_result.get("passes_support_check", True)):
                n_pass += 1
            else:
                n_fail += 1
                has_overlap = True

        if pt_test is not None:
            n_run += 1
            if pt_test.passed:
                n_pass += 1
            else:
                n_fail += 1
                has_falsification = True

        if sensitivity_result is not None:
            n_run += 1
            robust = bool(sensitivity_result.get("is_robust", True))
            if robust:
                n_pass += 1
            else:
                n_warn += 1
                has_robustness = True

        if falsification is not None:
            n_run += 1
            if falsification.overall_passed:
                n_pass += 1
            else:
                n_fail += 1
                has_falsification = True

        if balance_report is not None:
            n_run += 1
            if balance_report.passes_balance_check:
                n_pass += 1
            else:
                n_warn += 1
                has_balance = True

        overall = (n_fail == 0)

        return cls(
            run_id=run_id,
            query_str=query_str,
            created_at=created_at,
            positivity=positivity_result,
            support_mismatch=support_result,
            covariate_balance=balance_report,
            parallel_trends=pt_test,
            sensitivity=sensitivity_result,
            falsification=falsification,
            n_diagnostics_run=n_run,
            n_passed=n_pass,
            n_failed=n_fail,
            n_warnings=n_warn,
            overall_passed=overall,
            has_overlap_issues=has_overlap,
            has_balance_issues=has_balance,
            has_falsification_failures=has_falsification,
            has_robustness_concerns=has_robustness,
        )


def _serialize_sensitivity(sr: Any) -> dict[str, Any]:
    """Convert a SensitivityResult (or dict) to a plain dict."""
    if isinstance(sr, dict):
        return sr
    try:
        return sr.model_dump(mode="json")
    except Exception:
        return {
            "e_value": getattr(sr, "e_value", None),
            "robustness_value": getattr(sr, "robustness_value", None),
            "rosenbaum_gamma": getattr(sr, "rosenbaum_gamma", None),
            "is_robust": getattr(sr, "is_robust", False),
        }


__all__ = ["DiagnosticDashboardData"]
