"""Decision-packet strategic projections."""

from __future__ import annotations

from typing import Any

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.ir.analytics.strategic import (
    load_mean_field_equilibrium_certificate,
    load_mean_field_macro_simulation_config,
    load_mean_field_perturbation_spec,
    load_performative_shift_summary,
    load_post_adaptation_policy_value_summary,
    load_strategic_decomposition_failure_card,
    load_strategic_response_bundle,
    load_strategic_scm,
)
from polisyos.ir.registry.refs import StrategicResponseBundleRef, StrategicSCMRef
from polisyos.scientist.nodes.builtins.decide.decision_packet.validation import (
    _DECISION_PACKET_LOAD_ERRORS,
    _record_decision_packet_section_degraded,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
    ARTIFACT_STRATEGIC_SCM_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _build_strategic_section(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    artifacts_index = state.artifacts_index
    strategic_scm_ref = artifacts_index.get(ARTIFACT_STRATEGIC_SCM_REF)
    bundle_ref = artifacts_index.get(ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF)
    strategic_summary = state.params.get("strategic_response")
    if strategic_scm_ref is None and bundle_ref is None and not isinstance(strategic_summary, dict):
        return None

    payload: dict[str, object] = {
        "strategic_scm_ref": (
            None if strategic_scm_ref is None else str(strategic_scm_ref.artifact_id)
        ),
        "strategic_response_bundle_ref": (
            None if bundle_ref is None else str(bundle_ref.artifact_id)
        ),
    }

    _populate_strategic_scm(ctx, strategic_scm_ref, payload, packet_payload)

    if bundle_ref is not None:
        try:
            bundle = load_strategic_response_bundle(
                _ensure_ir_artifact_store(ctx.store),
                StrategicResponseBundleRef(artifact_id=bundle_ref.artifact_id),
            )
            payload.update(
                {
                    "fallback_mode": bundle.fallback_mode.value,
                    "equilibrium_selection_dependence": bundle.equilibrium_selection_dependence,
                    "multiplicity_note": bundle.multiplicity_note,
                    "blocked_reason": bundle.blocked_reason,
                    "decomposition_status": bundle.decomposition_status.value,
                    "decomposition_semantics": bundle.decomposition_semantics.value,
                    "selected_equilibrium_ref": (
                        None
                        if bundle.selected_equilibrium_ref is None
                        else str(bundle.selected_equilibrium_ref.artifact_id)
                    ),
                    "mfg_equilibrium_ref": (
                        None
                        if bundle.mfg_equilibrium_ref is None
                        else str(bundle.mfg_equilibrium_ref.artifact_id)
                    ),
                    "performative_shift_ref": (
                        None
                        if bundle.performative_shift_ref is None
                        else str(bundle.performative_shift_ref.artifact_id)
                    ),
                    "post_adaptation_policy_value_ref": str(
                        bundle.post_adaptation_policy_value_ref.artifact_id
                    ),
                    "causal_component_ref": str(bundle.causal_component_ref.artifact_id),
                    "strategic_closure_ref": str(bundle.strategic_closure_ref.artifact_id),
                    "equilibrium_set_ref": str(bundle.equilibrium_set_ref.artifact_id),
                    "decomposition_certificate_ref": (
                        None
                        if bundle.decomposition_certificate_ref is None
                        else str(bundle.decomposition_certificate_ref.artifact_id)
                    ),
                    "decomposition_failure_card_ref": (
                        None
                        if bundle.decomposition_failure_card_ref is None
                        else str(bundle.decomposition_failure_card_ref.artifact_id)
                    ),
                    "anchor_equilibrium_ref": (
                        None
                        if bundle.anchor_equilibrium_ref is None
                        else str(bundle.anchor_equilibrium_ref.artifact_id)
                    ),
                }
            )
            _populate_strategic_mfg_details(ctx, bundle, payload, packet_payload)
            _populate_performative_shift(ctx, bundle, payload, packet_payload)
            _populate_post_adaptation_value(ctx, bundle, payload, packet_payload)
            _populate_decomposition_failure_card(ctx, bundle, payload, packet_payload)
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["strategic_bundle_parse_warning"] = "strategic_response_bundle_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_strategic_response_bundle",
                reason="strategic_response_bundle_load_failed",
                exc=exc,
                ref=bundle_ref,
                artifact_key=ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
            )
    elif isinstance(strategic_summary, dict):
        for key in (
            "fallback_mode",
            "equilibrium_selection_dependence",
            "multiplicity_note",
            "blocked_reason",
            "selected_equilibrium",
            "performative_shift",
            "performative_loop",
            "post_adaptation_policy_value",
            "warnings",
            "causal_component_ref",
            "strategic_closure_ref",
            "equilibrium_set_ref",
            "post_adaptation_policy_value_ref",
            "selected_equilibrium_ref",
            "performative_shift_ref",
            "decomposition_status",
            "decomposition_semantics",
            "decomposition_failure_code",
            "decomposition_message",
            "decomposition_certificate_ref",
            "decomposition_failure_card_ref",
            "anchor_equilibrium_ref",
        ):
            if strategic_summary.get(key) is not None:
                payload[key] = strategic_summary[key]
        if strategic_summary.get("bounds") is not None:
            payload["post_adaptation_policy_value_bounds"] = strategic_summary["bounds"]

    return payload


def _populate_strategic_scm(
    ctx: ExecutionContext,
    strategic_scm_ref: ArtifactRef | None,
    payload: dict[str, object],
    packet_payload: dict[str, object] | None,
) -> None:
    if strategic_scm_ref is not None:
        try:
            strategic_scm = load_strategic_scm(
                _ensure_ir_artifact_store(ctx.store),
                StrategicSCMRef(artifact_id=strategic_scm_ref.artifact_id),
            )
            payload["equilibrium_concept"] = (
                None
                if strategic_scm.equilibrium_concept is None
                else strategic_scm.equilibrium_concept.value
            )
            if strategic_scm.equilibrium_descriptor is not None:
                payload["strategic_game_class"] = (
                    strategic_scm.equilibrium_descriptor.game_class.value
                )
                payload["strategic_solution_concept"] = (
                    strategic_scm.equilibrium_descriptor.solution_concept.value
                )
                payload["strategic_fallback_default"] = (
                    strategic_scm.equilibrium_descriptor.default_fallback_mode.value
                )
            payload["strategic_agents"] = list(strategic_scm.strategic_agents)
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["strategic_scm_parse_warning"] = "strategic_scm_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_strategic_scm",
                reason="strategic_scm_load_failed",
                exc=exc,
                ref=strategic_scm_ref,
                artifact_key=ARTIFACT_STRATEGIC_SCM_REF,
            )


def _populate_strategic_mfg_details(
    ctx: ExecutionContext,
    bundle: Any,
    payload: dict[str, object],
    packet_payload: dict[str, object] | None,
) -> None:
    if bundle.mfg_equilibrium_ref is not None:
        try:
            mfg_certificate = load_mean_field_equilibrium_certificate(
                _ensure_ir_artifact_store(ctx.store),
                bundle.mfg_equilibrium_ref,
            )
            payload.update(
                {
                    "mfg_intervention_kind": mfg_certificate.intervention_kind.value,
                    "mfg_model_class": mfg_certificate.mean_field_model_class.value,
                    "mfg_uniqueness_status": (
                        mfg_certificate.well_posedness.uniqueness_status.value
                    ),
                    "mfg_selection_rule": (mfg_certificate.identification.selection_rule.value),
                    "mfg_graph_semantics": (mfg_certificate.identification.graph_semantics.value),
                    "mfg_positivity_status": (
                        mfg_certificate.identification.positivity_status.value
                    ),
                    "mfg_stability_bound_type": (mfg_certificate.stability.bound_type.value),
                    "mfg_solver_residual_ref": (
                        None
                        if mfg_certificate.equilibrium_solution is None
                        or mfg_certificate.equilibrium_solution.solver_residual_ref is None
                        else str(
                            mfg_certificate.equilibrium_solution.solver_residual_ref.artifact_id
                        )
                    ),
                    "mfg_mass_conservation_ref": (
                        None
                        if mfg_certificate.equilibrium_solution is None
                        or mfg_certificate.equilibrium_solution.mass_conservation_ref is None
                        else str(
                            mfg_certificate.equilibrium_solution.mass_conservation_ref.artifact_id
                        )
                    ),
                    "mfg_numerics_config_ref": (
                        None
                        if mfg_certificate.provenance is None
                        or mfg_certificate.provenance.numerics_config_ref is None
                        else str(mfg_certificate.provenance.numerics_config_ref.artifact_id)
                    ),
                }
            )
            _populate_mfg_numerics_config(ctx, bundle, mfg_certificate, payload, packet_payload)
            _populate_mfg_perturbation_spec(ctx, bundle, mfg_certificate, payload, packet_payload)
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["mfg_parse_warning"] = "mean_field_equilibrium_certificate_load_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_mean_field_equilibrium_certificate",
                reason="mean_field_equilibrium_certificate_load_failed",
                exc=exc,
                ref=bundle.mfg_equilibrium_ref,
                artifact_key=ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
            )


def _populate_performative_shift(
    ctx: ExecutionContext,
    bundle: Any,
    payload: dict[str, object],
    packet_payload: dict[str, object] | None,
) -> None:
    if bundle.performative_shift_ref is not None:
        try:
            shift_summary = load_performative_shift_summary(
                _ensure_ir_artifact_store(ctx.store),
                bundle.performative_shift_ref,
            )
            if shift_summary.performative_shift is not None:
                payload["performative_shift"] = shift_summary.performative_shift
            payload["performative_loop"] = _performative_loop_payload(shift_summary)
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["performative_shift_parse_warning"] = "performative_shift_summary_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_performative_shift_summary",
                reason="performative_shift_summary_load_failed",
                exc=exc,
                ref=bundle.performative_shift_ref,
            )


def _populate_decomposition_failure_card(
    ctx: ExecutionContext,
    bundle: Any,
    payload: dict[str, object],
    packet_payload: dict[str, object] | None,
) -> None:
    if bundle.decomposition_failure_card_ref is not None:
        try:
            failure_card = load_strategic_decomposition_failure_card(
                _ensure_ir_artifact_store(ctx.store),
                bundle.decomposition_failure_card_ref,
            )
            payload["decomposition_failure_code"] = failure_card.failure_code
            payload["decomposition_message"] = failure_card.message
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["decomposition_failure_parse_warning"] = (
                "strategic_decomposition_failure_card_parse_failed"
            )
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_strategic_decomposition_failure_card",
                reason="strategic_decomposition_failure_card_load_failed",
                exc=exc,
                ref=bundle.decomposition_failure_card_ref,
            )


def _populate_post_adaptation_value(
    ctx: ExecutionContext,
    bundle: Any,
    payload: dict[str, object],
    packet_payload: dict[str, object] | None,
) -> None:
    try:
        value_summary = load_post_adaptation_policy_value_summary(
            _ensure_ir_artifact_store(ctx.store),
            bundle.post_adaptation_policy_value_ref,
        )
        payload["post_adaptation_policy_value"] = value_summary.point_value
        if value_summary.lower_bound is not None and value_summary.upper_bound is not None:
            payload["post_adaptation_policy_value_bounds"] = [
                value_summary.lower_bound,
                value_summary.upper_bound,
            ]
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        payload["post_adaptation_value_parse_warning"] = "post_adaptation_policy_value_parse_failed"
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_post_adaptation_policy_value",
            reason="post_adaptation_policy_value_load_failed",
            exc=exc,
            ref=bundle.post_adaptation_policy_value_ref,
        )


def _populate_mfg_numerics_config(
    ctx: ExecutionContext,
    bundle: Any,
    mfg_certificate: Any,
    payload: dict[str, object],
    packet_payload: dict[str, object] | None,
) -> None:
    if (
        mfg_certificate.provenance is not None
        and mfg_certificate.provenance.numerics_config_ref is not None
        and mfg_certificate.provenance.numerics_config_ref.kind
        == "ir.mean_field_macro_simulation_config"
    ):
        try:
            numerics_config = load_mean_field_macro_simulation_config(
                _ensure_ir_artifact_store(ctx.store),
                mfg_certificate.provenance.numerics_config_ref,
            )
            payload.update(
                {
                    "mfg_numerics_scheme": numerics_config.numerics_scheme.value,
                    "mfg_fixed_point_method": (numerics_config.fixed_point_method.value),
                    "mfg_runtime_mode": numerics_config.runtime_mode.value,
                }
            )
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["mfg_numerics_parse_warning"] = "mean_field_macro_simulation_config_load_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_mean_field_macro_simulation_config",
                reason="mean_field_macro_simulation_config_load_failed",
                exc=exc,
                ref=mfg_certificate.provenance.numerics_config_ref,
                artifact_key=ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
            )


def _populate_mfg_perturbation_spec(
    ctx: ExecutionContext,
    bundle: Any,
    mfg_certificate: Any,
    payload: dict[str, object],
    packet_payload: dict[str, object] | None,
) -> None:
    if (
        bundle.mfg_equilibrium_ref.kind == "ir.mean_field_equilibrium_certificate"
        and mfg_certificate.intervention_spec_ref.kind == "ir.mean_field_perturbation_spec"
    ):
        try:
            perturbation_spec = load_mean_field_perturbation_spec(
                _ensure_ir_artifact_store(ctx.store),
                mfg_certificate.intervention_spec_ref,
            )
            payload.update(
                {
                    "mfg_representative_agent_channels": [
                        channel.value for channel in perturbation_spec.representative_agent_channels
                    ],
                    "mfg_population_channels": [
                        channel.value for channel in perturbation_spec.population_channels
                    ],
                    "mfg_policy_kernel_overlap_required": (
                        perturbation_spec.policy_kernel_overlap_required
                    ),
                }
            )
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["mfg_perturbation_parse_warning"] = "mean_field_perturbation_spec_load_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_mean_field_perturbation_spec",
                reason="mean_field_perturbation_spec_load_failed",
                exc=exc,
                ref=mfg_certificate.intervention_spec_ref,
                artifact_key=ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
            )


def _performative_loop_payload(summary: Any) -> dict[str, object]:
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
