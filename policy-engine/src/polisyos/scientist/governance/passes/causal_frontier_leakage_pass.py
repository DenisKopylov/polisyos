"""Governance pass for causal-frontier boundary leakage diagnostics."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ProfileLevel
from polisyos.foundry.methods.catalog.survey.protocols import SAEResult


class CausalFrontierLeakagePass(ValidatorPass):
    """Escalate when unrestricted smoothing appears to absorb a policy frontier signal."""

    @property
    def pass_id(self) -> str:
        return "causal_frontier_leakage"

    @property
    def estimated_cost_ms(self) -> int:
        return 15

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        if ctx.profile.level is ProfileLevel.FAST:
            return []

        diagnostics = _resolve_diagnostics(ctx.state)
        if diagnostics is None:
            return []

        blr_raw = diagnostics.get("blr")
        if blr_raw is None:
            return []
        blr = float(blr_raw)
        warning_threshold = float(ctx.profile.thresholds.get("causal_frontier_blr_warning", 0.05))
        blocker_threshold = float(ctx.profile.thresholds.get("causal_frontier_blr_blocker", 0.15))
        if blr < warning_threshold:
            return []

        severity = IssueSeverity.WARNING
        if ctx.profile.level is ProfileLevel.STRICT and blr >= blocker_threshold:
            severity = IssueSeverity.BLOCKER

        pli = diagnostics.get("pli")
        variance_inflation = diagnostics.get("variance_inflation_ratio")
        singletons_after_cut = diagnostics.get("singletons_after_cut")
        alert_level = diagnostics.get("alert_level")
        tau_unrestricted = diagnostics.get("tau_unrestricted")
        tau_constrained = diagnostics.get("tau_constrained")

        message = (
            "Boundary leakage diagnostic indicates that unrestricted smoothing is "
            f"absorbing the policy-frontier signal (BLR={blr:.3f}, alert={alert_level or 'unknown'})."
        )
        suggestion = (
            "Use the constrained causal-frontier SAE output for downstream interpretation, "
            "keep frontier edges masked, and add an explicit spillover exposure term if "
            "cross-frontier effects are substantively expected."
        )
        if singletons_after_cut:
            suggestion += " Review small post-cut components because variance can inflate near the boundary."

        return [
            ComplianceIssue(
                pass_id=self.pass_id,
                path=["causal_frontier", "diagnostics", "blr"],
                message=message,
                severity=severity,
                code="CAUSAL_FRONTIER_BOUNDARY_LEAKAGE",
                suggestion=suggestion,
                input_value=str(
                    {
                        "blr": blr,
                        "pli": None if pli is None else float(pli),
                        "variance_inflation_ratio": (
                            None if variance_inflation is None else float(variance_inflation)
                        ),
                        "singletons_after_cut": singletons_after_cut,
                        "tau_unrestricted": tau_unrestricted,
                        "tau_constrained": tau_constrained,
                        "warning_threshold": warning_threshold,
                        "blocker_threshold": blocker_threshold,
                    }
                ),
            )
        ]


def _resolve_diagnostics(state: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in ("causal_frontier_diagnostics", "boundary_leakage_diagnostics"):
        raw = state.get(key)
        if isinstance(raw, Mapping):
            return raw

    for key in ("causal_frontier_result", "sae_result", "survey_result", "result"):
        diagnostics = _diagnostics_from_payload(state.get(key))
        if diagnostics is not None:
            return diagnostics
    return None


def _diagnostics_from_payload(raw_payload: Any) -> Mapping[str, Any] | None:
    if raw_payload is None:
        return None
    if isinstance(raw_payload, SAEResult):
        if "causal_frontier" not in raw_payload.method_name:
            return None
        diagnostics = raw_payload.statistics.get("diagnostics")
        return diagnostics if isinstance(diagnostics, Mapping) else None
    if isinstance(raw_payload, Mapping):
        if "blr" in raw_payload:
            return raw_payload
        nested_diagnostics = raw_payload.get("diagnostics")
        if isinstance(nested_diagnostics, Mapping) and "blr" in nested_diagnostics:
            return nested_diagnostics
        nested_statistics = raw_payload.get("statistics")
        if isinstance(nested_statistics, Mapping):
            diagnostics = nested_statistics.get("diagnostics")
            if isinstance(diagnostics, Mapping) and "blr" in diagnostics:
                return diagnostics
        nested_result = raw_payload.get("result")
        if nested_result is not None:
            return _diagnostics_from_payload(nested_result)
    return None


__all__ = ["CausalFrontierLeakagePass"]
