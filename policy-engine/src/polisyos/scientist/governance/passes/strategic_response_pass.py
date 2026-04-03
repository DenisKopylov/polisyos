"""Public passes strategic response pass module API."""
from __future__ import annotations

from typing import Any

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ProfileLevel
from polisyos.ir.analytics.strategic import (
    StrategicResponseBundle,
    load_strategic_response_bundle,
)
from polisyos.ir.refs import StrategicResponseBundleRef


class StrategicResponsePass(ValidatorPass):
    """Governance pass that enforces strategic-response evidence requirements.

    The pass blocks promotion when strategic adaptation was required but missing
    or runtime-blocked, warns on approximate fallback modes, and escalates
    multiplicity-sensitive equilibria for human review in strict profiles.
    """

    @property
    def pass_id(self) -> str:
        return "strategic_response"

    @property
    def estimated_cost_ms(self) -> int:
        return 20

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        summary = _resolve_strategic_summary(ctx)
        required = _strategic_response_required(ctx)
        issues: list[ComplianceIssue] = []

        if summary is None:
            if required:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["strategic_response"],
                        message="Strategic response evidence is required but unavailable.",
                        severity=IssueSeverity.BLOCKER,
                        code="STRATEGIC_RESPONSE_MISSING",
                        suggestion="Run strategic response evaluation before governance.",
                    )
                )
            return issues

        fallback_mode = str(summary.get("fallback_mode") or "").strip().lower()
        selection_dependence = str(
            summary.get("equilibrium_selection_dependence") or ""
        ).strip()
        multiplicity_note = summary.get("multiplicity_note")

        if fallback_mode == "blocked":
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["strategic_response", "fallback_mode"],
                    message="Strategic response runtime is blocked.",
                    severity=IssueSeverity.BLOCKER,
                    code="STRATEGIC_RESPONSE_BLOCKED",
                    suggestion="Fix missing or invalid strategic inputs before approval.",
                )
            )
            return issues

        if fallback_mode in {"strategic_bounds", "macro_abstracted"}:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["strategic_response", "fallback_mode"],
                    message=(
                        "Strategic response relied on an approximate fallback "
                        f"({fallback_mode})."
                    ),
                    severity=IssueSeverity.WARNING,
                    code="STRATEGIC_RESPONSE_APPROXIMATE",
                    suggestion="Review approximation assumptions before approval.",
                )
            )

        if multiplicity_note or (
            selection_dependence
            and selection_dependence.lower() not in {"deterministic", "deterministic_selection"}
        ):
            if ctx.profile.level is ProfileLevel.STRICT:
                ctx.state["human_review_request"] = {
                    "items": [
                        {
                            "kind": "strategic_response_multiplicity",
                            "selection_dependence": selection_dependence or None,
                            "multiplicity_note": multiplicity_note,
                        }
                    ],
                    "created_by": "governance.strategic_response",
                    "deadline_hours": 72,
                }
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["strategic_response", "equilibrium_selection_dependence"],
                        message="Strategic response requires human review due to multiplicity.",
                        severity=IssueSeverity.INFO,
                        code="HUMAN_REVIEW_REQUESTED",
                    )
                )
            else:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["strategic_response", "equilibrium_selection_dependence"],
                        message=(
                            "Strategic response depends materially on equilibrium selection."
                        ),
                        severity=IssueSeverity.WARNING,
                        code="STRATEGIC_RESPONSE_MULTIPLICITY",
                        suggestion="Escalate for human review if this policy is promoted.",
                    )
                )
        return issues


def _strategic_response_required(ctx: PassContext) -> bool:
    if bool(ctx.state.get("strategic_response_required")):
        return True
    params = ctx.state.get("params")
    if isinstance(params, dict) and params.get("strategic_scm") is not None:
        return True
    return False


def _resolve_strategic_summary(ctx: PassContext) -> dict[str, Any] | None:
    direct = ctx.state.get("strategic_response")
    if isinstance(direct, dict):
        return dict(direct)

    params = ctx.state.get("params")
    if isinstance(params, dict):
        param_summary = params.get("strategic_response")
        if isinstance(param_summary, dict):
            return dict(param_summary)

    artifacts_index = ctx.state.get("artifacts_index")
    if not isinstance(artifacts_index, dict):
        return None
    raw_ref = artifacts_index.get("strategic_response_bundle_ref")
    if raw_ref is None:
        return None
    store = ctx.state.get("_store")
    if store is None:
        return None
    try:
        ref = StrategicResponseBundleRef.model_validate(raw_ref)
        bundle = load_strategic_response_bundle(store, ref)
    except Exception:
        return None
    return _bundle_summary(bundle)


def _bundle_summary(bundle: StrategicResponseBundle) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "fallback_mode": bundle.fallback_mode.value,
        "equilibrium_selection_dependence": bundle.equilibrium_selection_dependence,
        "multiplicity_note": bundle.multiplicity_note,
        "blocked_reason": bundle.blocked_reason,
    }
    if bundle.metadata:
        closure_summary = bundle.metadata.get("closure_summary")
        if isinstance(closure_summary, dict):
            summary["closure_summary"] = dict(closure_summary)
    return summary


__all__ = ["StrategicResponsePass"]
