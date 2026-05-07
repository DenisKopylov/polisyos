"""Validate strategic-response evidence, fallback modes, and multiplicity review state."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ProfileLevel
from polisyos.ir.analytics.strategic import (
    StrategicResponseBundle,
    load_mean_field_equilibrium_certificate,
    load_performative_shift_summary,
    load_strategic_response_bundle,
)
from polisyos.ir.refs import StrategicResponseBundleRef
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path


class StrategicResponsePass(ValidatorPass):
    """Governance pass that enforces strategic-response evidence requirements.

    The pass blocks promotion when strategic adaptation was required but missing
    or runtime-blocked, warns on approximate fallback modes, and escalates
    both multiplicity-sensitive equilibria and uncertified iterative
    performative loops for human review.
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
        selection_dependence = str(summary.get("equilibrium_selection_dependence") or "").strip()
        multiplicity_note = summary.get("multiplicity_note")
        mfg_uniqueness_status = str(summary.get("mfg_uniqueness_status") or "").strip().lower()
        mfg_selection_rule = str(summary.get("mfg_selection_rule") or "").strip().lower()
        has_mfg_numerics_metadata = any(
            key in summary
            for key in (
                "mfg_has_numerics_provenance",
                "mfg_has_solver_residual",
                "mfg_has_mass_conservation",
            )
        )
        mfg_has_numerics_provenance = bool(summary.get("mfg_has_numerics_provenance"))
        mfg_has_solver_residual = bool(summary.get("mfg_has_solver_residual"))
        mfg_has_mass_conservation = bool(summary.get("mfg_has_mass_conservation"))
        performative_loop = _extract_performative_loop(summary)
        decomposition_status = str(summary.get("decomposition_status") or "").strip().lower()
        decomposition_failure_code = str(summary.get("decomposition_failure_code") or "").strip()

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

        if decomposition_status == "blocked":
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["strategic_response", "decomposition_status"],
                    message=(
                        "Strategic response cannot support a point-valued causal/strategic "
                        "decomposition for this policy."
                    ),
                    severity=IssueSeverity.BLOCKER,
                    code="STRATEGIC_DECOMPOSITION_BLOCKED",
                    suggestion=(
                        "Require a decomposition certificate, bounded component artifacts, "
                        f"or an explicit blocked-mode disclosure card. Current reason: {decomposition_failure_code or 'unspecified'}."
                    ),
                )
            )
            return issues

        if decomposition_status == "bounded":
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["strategic_response", "decomposition_status"],
                    message=(
                        "Strategic response exposes only bounded causal/strategic components."
                    ),
                    severity=IssueSeverity.WARNING,
                    code="STRATEGIC_DECOMPOSITION_BOUNDED",
                    suggestion="Use interval disclosure for the two components and avoid point claims.",
                )
            )

        if fallback_mode in {"strategic_bounds", "macro_abstracted"}:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["strategic_response", "fallback_mode"],
                    message=(
                        f"Strategic response relied on an approximate fallback ({fallback_mode})."
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
                _append_human_review_items(
                    ctx,
                    [
                        {
                            "kind": "strategic_response_multiplicity",
                            "selection_dependence": selection_dependence or None,
                            "multiplicity_note": multiplicity_note,
                        }
                    ],
                )
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
                        message=("Strategic response depends materially on equilibrium selection."),
                        severity=IssueSeverity.WARNING,
                        code="STRATEGIC_RESPONSE_MULTIPLICITY",
                        suggestion="Escalate for human review if this policy is promoted.",
                    )
                )

        if (mfg_uniqueness_status and mfg_uniqueness_status != "unique") or (
            mfg_selection_rule and mfg_selection_rule != "none"
        ):
            _append_human_review_items(
                ctx,
                [
                    {
                        "kind": "strategic_response_mfg_equilibrium_selection",
                        "mfg_uniqueness_status": mfg_uniqueness_status or None,
                        "mfg_selection_rule": mfg_selection_rule or None,
                    }
                ],
            )
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["strategic_response", "mfg_equilibrium_ref"],
                    message=(
                        "Strategic response requires human review due to MFG equilibrium selection."
                    ),
                    severity=IssueSeverity.INFO,
                    code="HUMAN_REVIEW_REQUESTED",
                )
            )

        if has_mfg_numerics_metadata and mfg_uniqueness_status and not mfg_has_numerics_provenance:
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["strategic_response", "mfg_equilibrium_ref"],
                    message=(
                        "Mean-field equilibrium evidence is missing reproducible numerics provenance."
                    ),
                    severity=IssueSeverity.WARNING,
                    code="STRATEGIC_MFG_NUMERICS_PROVENANCE_MISSING",
                    suggestion=(
                        "Attach a mean-field macro-simulation config so replay and audit can recover the HJB-FP solve."
                    ),
                )
            )
        elif (
            has_mfg_numerics_metadata
            and mfg_uniqueness_status
            and (not mfg_has_solver_residual or not mfg_has_mass_conservation)
        ):
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["strategic_response", "mfg_equilibrium_ref"],
                    message=(
                        "Mean-field equilibrium evidence is missing solver residual or mass-conservation diagnostics."
                    ),
                    severity=IssueSeverity.WARNING,
                    code="STRATEGIC_MFG_NUMERICS_DIAGNOSTICS_INCOMPLETE",
                    suggestion=(
                        "Publish solver residual and mass-conservation artifacts before approval."
                    ),
                )
            )

        if performative_loop is not None:
            loop_scope = str(performative_loop.get("analysis_scope") or "").strip().lower()
            loop_status = str(performative_loop.get("stability_status") or "").strip().lower()
            loop_action = str(performative_loop.get("recommended_action") or "").strip().lower()
            loop_reason = performative_loop.get("reason_code")
            loop_summary = str(performative_loop.get("human_summary") or "").strip()

            if loop_scope == "iterated_loop":
                if loop_status == "certified_unstable" or loop_action == "block_auto_iteration":
                    issues.append(
                        ComplianceIssue(
                            pass_id=self.pass_id,
                            path=["strategic_response", "performative_loop", "stability_status"],
                            message=loop_summary
                            or "Performative auto-iteration is certified unstable.",
                            severity=IssueSeverity.BLOCKER,
                            code="PERFORMATIVE_LOOP_UNSTABLE",
                            suggestion="Disable automatic retraining or switch the deployment to single-shot mode.",
                        )
                    )
                elif loop_status in {
                    "uncertified",
                    "locally_convergent",
                    "mixed_stable_only",
                } or loop_action in {
                    "allow_with_human_review",
                    "single_shot_only",
                    "switch_to_mixed_no_regret",
                }:
                    _append_human_review_items(
                        ctx,
                        [
                            {
                                "kind": "strategic_performative_loop",
                                "analysis_scope": loop_scope,
                                "stability_status": loop_status or None,
                                "recommended_action": loop_action or None,
                                "reason_code": None if loop_reason is None else str(loop_reason),
                                "human_summary": loop_summary or None,
                            }
                        ],
                    )
                    issues.append(
                        ComplianceIssue(
                            pass_id=self.pass_id,
                            path=["strategic_response", "performative_loop", "stability_status"],
                            message=(
                                loop_summary
                                or "Performative auto-iteration is not yet certified for unattended deployment."
                            ),
                            severity=IssueSeverity.INFO,
                            code="HUMAN_REVIEW_REQUESTED",
                        )
                    )
            elif loop_status in {"certified_unstable", "uncertified", "locally_convergent"}:
                issues.append(
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["strategic_response", "performative_loop", "stability_status"],
                        message=(
                            loop_summary
                            or "Performative loop diagnostics restrict this recommendation to single-shot deployment."
                        ),
                        severity=IssueSeverity.WARNING,
                        code="PERFORMATIVE_LOOP_SINGLE_SHOT_ONLY",
                        suggestion="Keep the current recommendation single-shot unless a reviewed iterative policy loop is approved.",
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
    except (AttributeError, TypeError, ValidationError, ValueError) as exc:
        emit_degraded_path(
            component="governance.strategic_response_pass",
            operation="resolve_strategic_summary",
            reason="artifact_load_failed",
            exc=exc,
            details={"raw_ref": raw_ref},
        )
        return None
    return _bundle_summary(store, bundle)


def _bundle_summary(store: Any, bundle: StrategicResponseBundle) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "fallback_mode": bundle.fallback_mode.value,
        "equilibrium_selection_dependence": bundle.equilibrium_selection_dependence,
        "multiplicity_note": bundle.multiplicity_note,
        "blocked_reason": bundle.blocked_reason,
        "decomposition_status": bundle.decomposition_status.value,
        "decomposition_semantics": bundle.decomposition_semantics.value,
    }
    if bundle.decomposition_failure_card_ref is not None:
        summary["decomposition_failure_card_ref"] = (
            bundle.decomposition_failure_card_ref.model_dump(mode="json")
        )
    if bundle.metadata:
        closure_summary = bundle.metadata.get("closure_summary")
        if isinstance(closure_summary, dict):
            summary["closure_summary"] = dict(closure_summary)
    if bundle.performative_shift_ref is not None:
        try:
            shift_summary = load_performative_shift_summary(store, bundle.performative_shift_ref)
        except (AttributeError, TypeError, ValidationError, ValueError) as exc:
            emit_degraded_path(
                component="governance.strategic_response_pass",
                operation="resolve_performative_loop",
                reason="artifact_load_failed",
                exc=exc,
                details={
                    "performative_shift_ref": bundle.performative_shift_ref.model_dump(mode="json")
                },
            )
        else:
            summary["performative_loop"] = _performative_loop_payload(shift_summary)
    if bundle.mfg_equilibrium_ref is not None:
        try:
            mfg_summary = load_mean_field_equilibrium_certificate(store, bundle.mfg_equilibrium_ref)
        except (AttributeError, TypeError, ValidationError, ValueError) as exc:
            emit_degraded_path(
                component="governance.strategic_response_pass",
                operation="resolve_mfg_equilibrium",
                reason="artifact_load_failed",
                exc=exc,
                details={"mfg_equilibrium_ref": bundle.mfg_equilibrium_ref.model_dump(mode="json")},
            )
        else:
            summary["mfg_uniqueness_status"] = mfg_summary.well_posedness.uniqueness_status.value
            summary["mfg_selection_rule"] = mfg_summary.identification.selection_rule.value
            summary["mfg_graph_semantics"] = mfg_summary.identification.graph_semantics.value
            summary["mfg_positivity_status"] = mfg_summary.identification.positivity_status.value
            summary["mfg_stability_bound_type"] = mfg_summary.stability.bound_type.value
            summary["mfg_has_numerics_provenance"] = bool(
                mfg_summary.provenance is not None
                and mfg_summary.provenance.numerics_config_ref is not None
            )
            summary["mfg_has_solver_residual"] = bool(
                mfg_summary.equilibrium_solution is not None
                and mfg_summary.equilibrium_solution.solver_residual_ref is not None
            )
            summary["mfg_has_mass_conservation"] = bool(
                mfg_summary.equilibrium_solution is not None
                and mfg_summary.equilibrium_solution.mass_conservation_ref is not None
            )
    return summary


def _performative_loop_payload(summary: Any) -> dict[str, Any]:
    return {
        "analysis_scope": summary.analysis_scope.value,
        "proof_family": None if summary.proof_family is None else summary.proof_family.value,
        "stability_status": (
            None if summary.stability_status is None else summary.stability_status.value
        ),
        "reason_code": None if summary.reason_code is None else summary.reason_code.value,
        "contraction_upper_bound": summary.contraction_upper_bound,
        "local_spectral_radius_estimate": summary.local_spectral_radius_estimate,
        "witness_strength": (
            None if summary.witness_strength is None else summary.witness_strength.value
        ),
        "simulation_horizon": summary.simulation_horizon,
        "detected_cycle_period": summary.detected_cycle_period,
        "transient_gain_upper": summary.transient_gain_upper,
        "convergence_rate_upper": summary.convergence_rate_upper,
        "iterations_to_delta_bound": summary.iterations_to_delta_bound,
        "hardness_flag": bool(summary.hardness_flag),
        "recommended_action": (
            None if summary.recommended_action is None else summary.recommended_action.value
        ),
        "human_summary": summary.human_summary,
    }


def _extract_performative_loop(summary: dict[str, Any]) -> dict[str, Any] | None:
    payload = summary.get("performative_loop")
    if isinstance(payload, dict):
        return dict(payload)
    fields = {
        key: summary.get(key)
        for key in (
            "analysis_scope",
            "proof_family",
            "stability_status",
            "reason_code",
            "contraction_upper_bound",
            "local_spectral_radius_estimate",
            "witness_strength",
            "simulation_horizon",
            "detected_cycle_period",
            "transient_gain_upper",
            "convergence_rate_upper",
            "iterations_to_delta_bound",
            "hardness_flag",
            "recommended_action",
            "human_summary",
        )
        if key in summary
    }
    return fields or None


def _append_human_review_items(ctx: PassContext, items: list[dict[str, Any]]) -> None:
    existing = ctx.state.get("human_review_request")
    existing_items: list[dict[str, Any]] = []
    if isinstance(existing, dict):
        raw_items = existing.get("items")
        if isinstance(raw_items, list):
            existing_items = [item for item in raw_items if isinstance(item, dict)]
    ctx.state["human_review_request"] = {
        "items": [*existing_items, *items],
        "created_by": "governance.strategic_response",
        "deadline_hours": 72,
    }


__all__ = ["StrategicResponsePass"]
