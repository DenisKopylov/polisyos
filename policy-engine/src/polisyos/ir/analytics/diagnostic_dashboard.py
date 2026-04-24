"""DiagnosticDashboardData — aggregated diagnostic view for a single causal run.

Collects positivity, support mismatch, covariate balance, parallel trends,
sensitivity, and falsification diagnostics into a single machine-readable
object intended for the audit UI and downstream quality scoring.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict

from polisyos.ir.analytics.covariate_balance import CovariateBalanceReport
from polisyos.ir.analytics.falsification_report import (
    FalsificationReport,
    FalsificationTest,
    FalsificationTestKind,
)

logger = logging.getLogger(__name__)


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

    raking_convergence: dict[str, Any] | None = None
    """Survey/microsim raking convergence summary."""

    weight_stability: dict[str, Any] | None = None
    """Survey/microsim weight concentration and positivity summary."""

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
    has_weighting_issues: bool = False
    warnings: tuple[str, ...] = ()

    @classmethod
    def from_node_outputs(
        cls,
        run_id: str,
        query_str: str,
        node_outputs: dict[str, dict],
        *,
        created_at: str = "",
    ) -> DiagnosticDashboardData:
        """Build a DiagnosticDashboardData from CausalEngine node_outputs.

        Scans every node output for known diagnostic keys and assembles
        the dashboard object.
        """
        positivity_result: dict[str, Any] | None = None
        support_result: dict[str, Any] | None = None
        sensitivity_result: dict[str, Any] | None = None
        pt_result: dict[str, Any] | None = None
        balance_report: CovariateBalanceReport | None = None
        raking_result: dict[str, Any] | None = None
        warnings: dict[str, None] = {}

        for node_id, outputs in node_outputs.items():
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

            if raking_result is None:
                raking_result = _serialize_raking(outputs.get("diagnostics", outputs.get("result")))

            # SensitivityResult object
            sr = outputs.get("sensitivity_result")
            if sr is not None and sensitivity_result is None:
                sensitivity_result, warning = _serialize_sensitivity(sr)
                if warning is not None:
                    warnings.setdefault(f"{warning}:{node_id}", None)

            # CovariateBalanceReport — from estimators that compute SMDs after weighting
            if balance_report is None:
                cb = outputs.get("covariate_balance")
                if isinstance(cb, CovariateBalanceReport):
                    balance_report = cb
                elif isinstance(cb, dict) and "variable_smd" in cb:
                    try:
                        balance_report = CovariateBalanceReport.model_validate(cb)
                    except (TypeError, ValueError) as exc:
                        warnings.setdefault(f"covariate_balance_parse_failed:{node_id}", None)
                        logger.warning(
                            "Diagnostic dashboard failed to parse covariate balance for node '%s': %s",
                            node_id,
                            exc,
                        )

        # Parallel trends → FalsificationTest
        pt_test: FalsificationTest | None = None
        if pt_result is not None:
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
        falsification: FalsificationReport | None = FalsificationReport.from_dowhy_refute_outputs(
            node_outputs
        )
        if falsification.n_passed == 0 and falsification.n_failed == 0:
            falsification = None

        # Aggregate counts
        n_run = 0
        n_pass = 0
        n_fail = 0
        n_warn = 0

        has_overlap = False
        has_balance = False
        has_falsification = False
        has_robustness = False
        has_weighting = False

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

        if raking_result is not None:
            n_run += 1
            decision = str(raking_result.get("decision", "pass"))
            if decision == "block":
                n_fail += 1
                has_weighting = True
            elif decision == "warn":
                n_warn += 1
                has_weighting = True
            else:
                n_pass += 1

        overall = n_fail == 0

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
            raking_convergence=_raking_convergence_view(raking_result),
            weight_stability=_weight_stability_view(raking_result),
            n_diagnostics_run=n_run,
            n_passed=n_pass,
            n_failed=n_fail,
            n_warnings=n_warn,
            overall_passed=overall,
            has_overlap_issues=has_overlap,
            has_balance_issues=has_balance,
            has_falsification_failures=has_falsification,
            has_robustness_concerns=has_robustness,
            has_weighting_issues=has_weighting,
            warnings=tuple(warnings),
        )


def _serialize_sensitivity(sr: Any) -> tuple[dict[str, Any], str | None]:
    """Convert a SensitivityResult (or dict) to a plain dict."""
    if isinstance(sr, dict):
        return sr, None
    try:
        return sr.model_dump(mode="json"), None
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        logger.warning(
            "Diagnostic dashboard fell back to attribute-based sensitivity serialization: %s",
            exc,
        )
        return {
            "e_value": getattr(sr, "e_value", None),
            "robustness_value": getattr(sr, "robustness_value", None),
            "rosenbaum_gamma": getattr(sr, "rosenbaum_gamma", None),
            "is_robust": getattr(sr, "is_robust", False),
        }, "sensitivity_serialize_fallback"


def _serialize_raking(value: Any) -> dict[str, Any] | None:
    """Convert a survey raking diagnostic payload to a plain dict when possible."""
    if value is None:
        return None
    if (
        hasattr(value, "contract_id")
        and getattr(value, "contract_id", None) == "ir.survey_raking_diagnostic_report.v1"
    ):
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            return model_dump(mode="json")
    if isinstance(value, dict) and {"decision", "stop_reason", "max_rel_margin_error"} <= set(
        value
    ):
        return dict(value)
    return None


def _raking_convergence_view(raking_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if raking_result is None:
        return None
    keys = (
        "decision",
        "converged",
        "stop_reason",
        "n_sweeps",
        "max_rel_margin_error",
        "rms_rel_margin_error",
        "max_logweight_change",
        "improvement_ratio_5",
        "monotonicity_share",
        "worst_margin",
        "worst_category",
    )
    return {key: raking_result.get(key) for key in keys if key in raking_result}


def _weight_stability_view(raking_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if raking_result is None:
        return None
    keys = (
        "decision",
        "ess",
        "ess_fraction",
        "kish_deff",
        "cv_weights",
        "top1_weight_share",
        "top5_weight_share",
        "max_g_weight_ratio",
        "min_g_weight_ratio",
        "structural_zero_count",
        "sparse_category_count",
        "vif_lb_max",
        "blocking_reasons",
        "warnings",
    )
    return {key: raking_result.get(key) for key in keys if key in raking_result}


__all__ = ["DiagnosticDashboardData"]
