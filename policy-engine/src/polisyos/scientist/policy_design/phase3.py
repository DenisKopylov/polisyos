"""Shared Phase 3 certificate resolution and gating for decision-layer flows."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import SimulationResult
from polisyos.core.contracts.ic_verification import (
    ICVerificationCertificateRef,
    ICVerificationReport,
    ICVerificationReportRef,
)
from polisyos.core.contracts.ic_verification import (
    IncentiveCompatibilityCertificate as SemanticICCertificate,
)
from polisyos.foundry.methods.catalog.microsim.protocols import MicrosimResult
from polisyos.foundry.methods.catalog.policy.welfare import (
    register_social_weight_manifest,
    resolve_social_weight_manifest,
)
from polisyos.ir.analytics.decision_layer import (
    FiscalFeedbackLink,
    OptimizationAmbiguityCertificate,
    SocialWeightManifestArtifact,
    build_optimization_ambiguity_certificate,
    load_fiscal_feedback_link,
    load_optimization_ambiguity_certificate,
    persist_fiscal_feedback_link,
    persist_optimization_ambiguity_certificate,
    persist_social_weight_manifest,
)
from polisyos.ir.analytics.mechanism_design import (
    load_incentive_compatibility_certificate as load_mechanism_ic_certificate,
)
from polisyos.ir.analytics.mechanism_design import (
    load_mechanism_welfare_loss_bound,
)
from polisyos.ir.analytics.welfare import (
    WelfareStatus,
    load_channel_decomposition_artifact,
    load_welfare_bundle,
)
from polisyos.ir.refs import (
    ArtifactRefModel,
    FiscalFeedbackLinkRef,
    IncentiveCompatibilityCertificateRef,
    MechanismWelfareLossBoundRef,
    OptimizationAmbiguityCertificateRef,
    SocialWeightManifestRef,
    WelfareBundleRef,
)
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_FISCAL_FEEDBACK_LINK_REF,
    ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_WELFARE_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    load_policy_candidate_schema,
)

_PHASE3_BLOCK_WELFARE_MISSING = "phase3.welfare_missing"
_PHASE3_BLOCK_WELFARE_NOT_OK = "phase3.welfare_not_ok"
_PHASE3_BLOCK_GE_UNCERTAINTY_MISSING = "phase3.ge_uncertainty_missing"
_PHASE3_BLOCK_SOCIAL_WEIGHT_MISSING = "phase3.social_weight_missing"
_PHASE3_BLOCK_AMBIGUITY_MISSING = "phase3.ambiguity_missing"
_PHASE3_BLOCK_MECHANISM_CERTIFICATE_MISSING = "phase3.mechanism_certificate_missing"
_PHASE3_BLOCK_MECHANISM_WELFARE_BOUND_MISSING = "phase3.mechanism_welfare_bound_missing"
_PHASE3_BLOCK_MECHANISM_FAMILY_UNSUPPORTED = "phase3.mechanism_family_unsupported"
_PHASE3_BLOCK_FISCAL_FEEDBACK_MISSING = "phase3.fiscal_feedback_missing"
_SUPPORTED_MECHANISM_FAMILY_IDS = frozenset(
    {
        "bayes_tax_pl_v1",
        "bayes_tax_affine_v1",
        "license_scoring_reserve_v1",
        "license_myerson_score_v1",
    }
)


class Phase3CertificateStatus(BaseModel):
    """Machine-readable Phase 3 gate embedded into readiness and final bundles."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    welfare_bundle_ref: WelfareBundleRef | None = None
    ambiguity_certificate_ref: OptimizationAmbiguityCertificateRef | None = None
    semantic_ic_certificate_ref: ICVerificationCertificateRef | None = None
    mechanism_ic_certificate_ref: IncentiveCompatibilityCertificateRef | None = None
    mechanism_welfare_loss_bound_ref: MechanismWelfareLossBoundRef | None = None
    fiscal_feedback_ref: FiscalFeedbackLinkRef | None = None
    mechanism_required: bool = False
    fiscal_feedback_required: bool = False
    gate_passed: bool = False
    blocking_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_inconsistent_passed_gate(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data
        normalized = dict(data)
        if normalized.get("gate_passed") is not True:
            return normalized

        blockers: list[str] = [str(item) for item in list(normalized.get("blocking_reasons") or [])]
        if normalized.get("welfare_bundle_ref") is None:
            blockers.append(_PHASE3_BLOCK_WELFARE_MISSING)
        if normalized.get("ambiguity_certificate_ref") is None:
            blockers.append(_PHASE3_BLOCK_AMBIGUITY_MISSING)
        if bool(normalized.get("mechanism_required")):
            if (
                normalized.get("semantic_ic_certificate_ref") is None
                or normalized.get("mechanism_ic_certificate_ref") is None
            ):
                blockers.append(_PHASE3_BLOCK_MECHANISM_CERTIFICATE_MISSING)
            if normalized.get("mechanism_welfare_loss_bound_ref") is None:
                blockers.append(_PHASE3_BLOCK_MECHANISM_WELFARE_BOUND_MISSING)
        if (
            bool(normalized.get("fiscal_feedback_required"))
            and normalized.get("fiscal_feedback_ref") is None
        ):
            blockers.append(_PHASE3_BLOCK_FISCAL_FEEDBACK_MISSING)

        if blockers:
            normalized["gate_passed"] = False
            normalized["blocking_reasons"] = list(dict.fromkeys(blockers))
        return normalized

    @classmethod
    def missing(cls) -> Phase3CertificateStatus:
        return cls(
            gate_passed=False,
            blocking_reasons=[
                _PHASE3_BLOCK_WELFARE_MISSING,
                _PHASE3_BLOCK_AMBIGUITY_MISSING,
            ],
        )


def resolve_phase3_gate(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    candidate: PolicyCandidateSchema | None = None,
    create_deterministic_ambiguity: bool = True,
) -> Phase3CertificateStatus:
    """Resolve the complete Phase 3 certificate package from runtime state."""

    resolved_candidate = candidate or _resolve_candidate(ctx, state)
    welfare_bundle_ref = _resolve_welfare_bundle_ref(ctx, state)
    ambiguity_required = phase3_ambiguity_required(ctx, state, candidate=resolved_candidate)
    ambiguity_certificate_ref = ensure_optimization_ambiguity_certificate(
        ctx,
        state,
        create_if_missing=create_deterministic_ambiguity and not ambiguity_required,
    )
    semantic_ic_certificate_ref = _pick_first_ref(
        state.artifacts_index,
        kind="scientist.ic_certificate",
        ref_cls=ICVerificationCertificateRef,
    )
    mechanism_ic_certificate_ref = _pick_first_ref(
        state.artifacts_index,
        kind="ir.incentive_compatibility_certificate",
        ref_cls=IncentiveCompatibilityCertificateRef,
    )
    mechanism_welfare_loss_bound_ref = _pick_first_ref(
        state.artifacts_index,
        kind="ir.mechanism_welfare_loss_bound",
        ref_cls=MechanismWelfareLossBoundRef,
    )
    fiscal_feedback_ref = _resolve_fiscal_feedback_ref(state)

    blocking_reasons: list[str] = []
    fiscal_feedback_required = False
    mechanism_required = bool(
        resolved_candidate is not None
        and resolved_candidate.trinity_bundle.policy_spec.mechanism_design is not None
    )

    welfare_bundle = None
    if welfare_bundle_ref is None:
        blocking_reasons.append(_PHASE3_BLOCK_WELFARE_MISSING)
    else:
        try:
            welfare_bundle = load_welfare_bundle(ctx.store, welfare_bundle_ref)
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            blocking_reasons.append(_PHASE3_BLOCK_WELFARE_MISSING)
        else:
            if welfare_bundle.status is not WelfareStatus.OK:
                blocking_reasons.append(_PHASE3_BLOCK_WELFARE_NOT_OK)
            if welfare_bundle.ge_uncertainty_ref is None:
                blocking_reasons.append(_PHASE3_BLOCK_GE_UNCERTAINTY_MISSING)
            if (
                welfare_bundle.social_weight_ref is None
                or welfare_bundle.social_weight_ref.kind != "ir.social_weight_manifest"
            ):
                blocking_reasons.append(_PHASE3_BLOCK_SOCIAL_WEIGHT_MISSING)
            fiscal_feedback_required = _phase3_fiscal_feedback_required(
                ctx,
                state,
                welfare_bundle=welfare_bundle,
                ambiguity_certificate_ref=ambiguity_certificate_ref,
            )

    if ambiguity_certificate_ref is None:
        blocking_reasons.append(_PHASE3_BLOCK_AMBIGUITY_MISSING)

    if mechanism_required:
        mechanism_coverage = _resolve_mechanism_coverage(
            ctx,
            state,
            candidate=resolved_candidate,
        )
        if mechanism_coverage["unsupported"]:
            blocking_reasons.append(_PHASE3_BLOCK_MECHANISM_FAMILY_UNSUPPORTED)
        if (
            semantic_ic_certificate_ref is None
            or mechanism_ic_certificate_ref is None
            or mechanism_coverage["missing_certificates"]
        ):
            blocking_reasons.append(_PHASE3_BLOCK_MECHANISM_CERTIFICATE_MISSING)
        if mechanism_welfare_loss_bound_ref is None or mechanism_coverage["missing_welfare_bounds"]:
            blocking_reasons.append(_PHASE3_BLOCK_MECHANISM_WELFARE_BOUND_MISSING)

    if fiscal_feedback_required and fiscal_feedback_ref is None and welfare_bundle is not None:
        fiscal_feedback_ref = ensure_fiscal_feedback_link(
            ctx,
            state,
            welfare_bundle=welfare_bundle,
            ambiguity_certificate_ref=ambiguity_certificate_ref,
        )

    if fiscal_feedback_required and fiscal_feedback_ref is None:
        blocking_reasons.append(_PHASE3_BLOCK_FISCAL_FEEDBACK_MISSING)

    return Phase3CertificateStatus(
        welfare_bundle_ref=welfare_bundle_ref,
        ambiguity_certificate_ref=ambiguity_certificate_ref,
        semantic_ic_certificate_ref=semantic_ic_certificate_ref,
        mechanism_ic_certificate_ref=mechanism_ic_certificate_ref,
        mechanism_welfare_loss_bound_ref=mechanism_welfare_loss_bound_ref,
        fiscal_feedback_ref=fiscal_feedback_ref,
        mechanism_required=mechanism_required,
        fiscal_feedback_required=fiscal_feedback_required,
        gate_passed=not blocking_reasons,
        blocking_reasons=list(dict.fromkeys(blocking_reasons)),
    )


def phase3_ambiguity_required(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    candidate: PolicyCandidateSchema | None = None,
) -> bool:
    """Return whether this path must carry a real stochastic/DRO ambiguity payload."""

    if bool(state.params.get("phase3_ambiguity_required")) or bool(
        state.params.get("require_phase3_ambiguity")
    ):
        return True
    if _resolve_ambiguity_payload(ctx, state) is not None:
        return False

    indicator_keys = {
        "moment_dro_result",
        "moment_dro_certificate",
        "moment_dro_certificate_ref",
        "dro_result",
        "stochastic_program_result",
        "robust_optimization_result",
    }
    if any(state.params.get(key) is not None for key in indicator_keys):
        return True

    optimization_result = state.params.get("optimization_result")
    if optimization_result is not None:
        return _container_requires_non_default_ambiguity(optimization_result)

    for key in ("optimization_method", "optimization_method_fqn", "method_fqn"):
        value = state.params.get(key)
        if _text_signals_stochastic_ambiguity(value):
            return True

    if candidate is not None:
        metadata = getattr(candidate, "metadata", {}) or {}
        if any(
            _text_signals_stochastic_ambiguity(metadata.get(key))
            for key in ("optimization_method", "optimization_method_fqn", "method_fqn")
        ):
            return True
    return False


def ensure_optimization_ambiguity_certificate(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    create_if_missing: bool = True,
) -> OptimizationAmbiguityCertificateRef | None:
    """Materialize the canonical persisted ambiguity artifact from runtime state."""

    direct_ref = _coerce_ref(
        state.artifacts_index.get(ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF),
        OptimizationAmbiguityCertificateRef,
    )
    if direct_ref is not None:
        return direct_ref

    direct_ref = _coerce_ref(
        state.params.get("optimization_ambiguity_certificate_ref"),
        OptimizationAmbiguityCertificateRef,
    )
    if direct_ref is not None:
        return direct_ref

    payload = _resolve_ambiguity_payload(ctx, state)
    if payload is None and not create_if_missing:
        return None

    if payload is None:
        certificate = build_optimization_ambiguity_certificate(
            {"mode": "not_applicable", "note": "No stochastic/DRO ambiguity payload was supplied."},
            mode="not_applicable",
            source_kind="deterministic_default",
            overall_status="pass",
            note="No stochastic/DRO ambiguity payload was supplied.",
        )
    else:
        certificate = _build_canonical_ambiguity_certificate(payload)

    return persist_optimization_ambiguity_certificate(
        ctx.store,
        certificate,
        inputs=_ambiguity_inputs(state),
    )


def ensure_fiscal_feedback_link(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    welfare_bundle,
    ambiguity_certificate_ref: OptimizationAmbiguityCertificateRef | None,
) -> FiscalFeedbackLinkRef | None:
    """Materialize the microsim-to-optimization link when enough behavioral evidence exists."""

    existing = _resolve_fiscal_feedback_ref(state)
    if existing is not None:
        return existing
    if ambiguity_certificate_ref is None:
        return None
    microsim = state.params.get("microsim_result")
    if microsim is None:
        return None

    behavior_model_ref = _resolve_behavior_model_ref(state)
    channel_ref = getattr(welfare_bundle, "channel_decomposition_ref", None)
    if behavior_model_ref is None and channel_ref is None:
        return None

    link = FiscalFeedbackLink(
        linkage_mode="behavioral_dro",
        behavior_model_ref=None
        if behavior_model_ref is None
        else ArtifactRefModel.model_validate(behavior_model_ref.model_dump(mode="json")),
        channel_decomposition_ref=None
        if channel_ref is None
        else ArtifactRefModel.model_validate(channel_ref.model_dump(mode="json")),
        ambiguity_certificate_ref=ambiguity_certificate_ref,
        metadata={"source": "phase3_gate_resolver"},
    )
    ref = persist_fiscal_feedback_link(ctx.store, link, inputs=_ambiguity_inputs(state))
    state.artifacts_index[ARTIFACT_FISCAL_FEEDBACK_LINK_REF] = ArtifactRef.model_validate(
        ref.model_dump(mode="json")
    )
    state.params["fiscal_feedback_ref"] = ref.model_dump(mode="json")
    try:
        result = MicrosimResult.model_validate(microsim)
    except (TypeError, ValueError):
        return ref
    state.params["microsim_result"] = result.model_copy(
        update={"fiscal_feedback_ref": ref}
    ).model_dump(mode="json")
    return ref


def phase3_gate_reference_blockers(
    store: Any,
    gate: Phase3CertificateStatus | Mapping[str, Any] | None,
) -> list[str]:
    """Revalidate embedded Phase 3 refs before final recommendation assembly."""

    if gate is None:
        return list(Phase3CertificateStatus.missing().blocking_reasons)
    status = Phase3CertificateStatus.model_validate(
        gate.model_dump(mode="json") if hasattr(gate, "model_dump") else gate
    )
    blockers = list(status.blocking_reasons)
    if not status.gate_passed:
        return list(dict.fromkeys(blockers))

    if status.welfare_bundle_ref is None:
        blockers.append(_PHASE3_BLOCK_WELFARE_MISSING)
    else:
        try:
            welfare = load_welfare_bundle(store, status.welfare_bundle_ref)
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            blockers.append(_PHASE3_BLOCK_WELFARE_MISSING)
        else:
            if welfare.status is not WelfareStatus.OK:
                blockers.append(_PHASE3_BLOCK_WELFARE_NOT_OK)
            if welfare.ge_uncertainty_ref is None:
                blockers.append(_PHASE3_BLOCK_GE_UNCERTAINTY_MISSING)
            if welfare.social_weight_ref is None:
                blockers.append(_PHASE3_BLOCK_SOCIAL_WEIGHT_MISSING)

    if status.ambiguity_certificate_ref is None:
        blockers.append(_PHASE3_BLOCK_AMBIGUITY_MISSING)
    else:
        try:
            load_optimization_ambiguity_certificate(store, status.ambiguity_certificate_ref)
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            blockers.append(_PHASE3_BLOCK_AMBIGUITY_MISSING)

    if status.mechanism_required:
        if status.semantic_ic_certificate_ref is None:
            blockers.append(_PHASE3_BLOCK_MECHANISM_CERTIFICATE_MISSING)
        else:
            try:
                SemanticICCertificate.model_validate(
                    from_canonical_bytes(
                        store.get_bytes(status.semantic_ic_certificate_ref.artifact_id)
                    )
                )
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
                blockers.append(_PHASE3_BLOCK_MECHANISM_CERTIFICATE_MISSING)
        if status.mechanism_ic_certificate_ref is None:
            blockers.append(_PHASE3_BLOCK_MECHANISM_CERTIFICATE_MISSING)
        else:
            try:
                load_mechanism_ic_certificate(store, status.mechanism_ic_certificate_ref)
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
                blockers.append(_PHASE3_BLOCK_MECHANISM_CERTIFICATE_MISSING)
        if status.mechanism_welfare_loss_bound_ref is None:
            blockers.append(_PHASE3_BLOCK_MECHANISM_WELFARE_BOUND_MISSING)
        else:
            try:
                load_mechanism_welfare_loss_bound(store, status.mechanism_welfare_loss_bound_ref)
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
                blockers.append(_PHASE3_BLOCK_MECHANISM_WELFARE_BOUND_MISSING)

    if status.fiscal_feedback_required:
        if status.fiscal_feedback_ref is None:
            blockers.append(_PHASE3_BLOCK_FISCAL_FEEDBACK_MISSING)
        else:
            try:
                load_fiscal_feedback_link(store, status.fiscal_feedback_ref)
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
                blockers.append(_PHASE3_BLOCK_FISCAL_FEEDBACK_MISSING)

    return list(dict.fromkeys(blockers))


def ensure_social_weight_manifest_artifact(
    ctx: ExecutionContext,
    *,
    welfare_params: Mapping[str, Any],
) -> SocialWeightManifestRef | None:
    """Materialize the canonical social-weight artifact from current welfare params."""

    if isinstance(welfare_params.get("welfare_social_weight_manifest"), Mapping):
        manifest_candidate, handle = _resolve_registered_social_weight_manifest(
            welfare_params["welfare_social_weight_manifest"]
        )
    else:
        ref = _coerce_ref(
            welfare_params.get("welfare_social_weight_ref"),
            SocialWeightManifestRef,
        )
        if ref is not None:
            return ref
        manifest_candidate, handle = _resolve_social_weight_handle(
            welfare_params.get("welfare_social_weight_ref")
        )
        if manifest_candidate is None and isinstance(
            welfare_params.get("social_weight_manifest"), Mapping
        ):
            manifest_candidate, handle = _resolve_registered_social_weight_manifest(
                welfare_params["social_weight_manifest"]
            )
        if manifest_candidate is None:
            ref = _coerce_ref(welfare_params.get("social_weight_ref"), SocialWeightManifestRef)
            if ref is not None:
                return ref
            manifest_candidate, handle = _resolve_social_weight_handle(
                welfare_params.get("social_weight_ref")
            )
        if manifest_candidate is None:
            return None

    artifact = SocialWeightManifestArtifact(
        manifest_ref=handle,
        method_fqn=(
            None
            if manifest_candidate.get("method_fqn") is None
            else str(manifest_candidate.get("method_fqn"))
        ),
        normalization=(
            None
            if manifest_candidate.get("normalization") is None
            else str(manifest_candidate.get("normalization"))
        ),
        income_grid=_float_tuple(manifest_candidate.get("income_grid")),
        weights_on_grid=_float_tuple(manifest_candidate.get("weights_on_grid")),
        state_keys=_str_tuple(manifest_candidate.get("state_keys")),
        regime_ids=_str_tuple(manifest_candidate.get("regime_ids")),
        manifest_payload=_json_mapping(manifest_candidate),
        metadata={
            "source_handle": handle,
        },
    )
    return persist_social_weight_manifest(ctx.store, artifact)


def _resolve_candidate(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> PolicyCandidateSchema | None:
    payload = state.params.get("policy_candidate_schema")
    if isinstance(payload, dict):
        try:
            return PolicyCandidateSchema.model_validate(payload)
        except (TypeError, ValueError):
            return None

    candidate_ref = state.params.get("policy_candidate_ref")
    if candidate_ref is not None:
        try:
            return load_policy_candidate_schema(
                ctx.store,
                ArtifactRef.model_validate(candidate_ref),
            )
        except (TypeError, ValueError, OSError, RuntimeError):
            return None

    trinity_ref = state.inputs.get(INPUT_TRINITY_BUNDLE_REF)
    if trinity_ref is None:
        return None
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(trinity_ref.artifact_id))
        return PolicyCandidateSchema.from_trinity_bundle(
            TrinityBundle.model_validate(payload),
            candidate_id=str(state.params.get("policy_candidate_id") or state.run_id),
        )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return None


def _resolve_welfare_bundle_ref(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> WelfareBundleRef | None:
    ref = _coerce_ref(state.artifacts_index.get(ARTIFACT_WELFARE_BUNDLE_REF), WelfareBundleRef)
    if ref is not None:
        return ref
    sim_ref = state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
    if sim_ref is None:
        return None
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(sim_ref.artifact_id))
        result = SimulationResult.model_validate(payload)
    except (OSError, RuntimeError, TypeError, ValueError):
        return None
    return result.welfare_bundle_ref


def _resolve_ambiguity_payload(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> dict[str, Any] | None:
    for key in (
        "ambiguity_certificate_ref",
        "moment_dro_certificate_ref",
    ):
        ref = _coerce_ref(state.params.get(key), ArtifactRef)
        if ref is None:
            continue
        payload = _load_json_mapping(ctx, ref)
        resolved = _extract_ambiguity_payload(payload)
        if resolved is not None:
            return resolved

    for key in (
        "ambiguity_certificate",
        "moment_dro_certificate",
    ):
        resolved = _extract_ambiguity_payload(state.params.get(key))
        if resolved is not None:
            return resolved

    for container_key in (
        "optimization_result",
        "moment_dro_result",
        "result",
        "simulation_results",
    ):
        container = state.params.get(container_key)
        resolved = _extract_ambiguity_payload(container)
        if resolved is not None:
            return resolved
    return None


def _build_canonical_ambiguity_certificate(
    payload: Mapping[str, Any],
) -> OptimizationAmbiguityCertificate:
    json_payload = _json_mapping(payload)
    mode = (
        str(json_payload.get("mode") or json_payload.get("ambiguity_set_type") or "unknown").strip()
        or "unknown"
    )
    overall_status = (
        None
        if json_payload.get("overall_status") is None
        else str(json_payload.get("overall_status"))
    )
    if overall_status is None and mode in {"none", "not_applicable"}:
        overall_status = "pass"
    note = None
    for key in ("note", "support_description", "trigger"):
        if json_payload.get(key) is not None:
            note = str(json_payload.get(key))
            break
    if "mode" in json_payload and "ambiguity_set_type" not in json_payload:
        source_kind = "optimization_payload"
    else:
        source_kind = "dro_payload"
    return build_optimization_ambiguity_certificate(
        json_payload,
        mode=mode,
        source_kind=source_kind,
        overall_status=overall_status,
        note=note,
    )


def _extract_ambiguity_payload(value: Any) -> dict[str, Any] | None:
    if hasattr(value, "to_payload") and callable(value.to_payload):
        return _extract_ambiguity_payload(value.to_payload())
    if isinstance(value, Mapping):
        nested = value.get("ambiguity_certificate")
        if nested is not None:
            nested_payload = _extract_ambiguity_payload(nested)
            if nested_payload is not None:
                return nested_payload
        if "mode" in value or "ambiguity_set_type" in value or "overall_status" in value:
            return _json_mapping(value)
    return None


def _container_requires_non_default_ambiguity(value: Any) -> bool:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="python")
    if hasattr(value, "to_payload") and callable(value.to_payload):
        value = value.to_payload()
    if not isinstance(value, Mapping):
        return False
    for key in (
        "ambiguity_required",
        "dro_required",
        "stochastic",
        "robust",
        "distributionally_robust",
    ):
        if value.get(key) is True:
            return True
    for key in ("method", "method_fqn", "optimizer", "mode", "certificate_kind"):
        if _text_signals_stochastic_ambiguity(value.get(key)):
            return True
    metadata = value.get("metadata")
    if isinstance(metadata, Mapping):
        return _container_requires_non_default_ambiguity(metadata)
    return False


def _text_signals_stochastic_ambiguity(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip().lower()
    return any(
        token in text
        for token in (
            "dro",
            "distributionally_robust",
            "moment_dro",
            "stochastic",
            "robust",
            "ambiguity",
            "bilevel",
        )
    )


def _ambiguity_inputs(state: ExperimentState) -> list[InputRef]:
    candidate_ref = state.params.get("policy_candidate_ref")
    resolved = _coerce_ref(candidate_ref, ArtifactRef)
    if resolved is None:
        return []
    return [InputRef(artifact_id=resolved.artifact_id, role="candidate")]


def _resolve_mechanism_coverage(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    candidate: PolicyCandidateSchema | None,
) -> dict[str, Any]:
    expected, unsupported = _expected_mechanism_family_ids(candidate)
    semantic_ids = _covered_mechanism_ids(
        ctx,
        state,
        kind="scientist.ic_certificate",
        ref_cls=ICVerificationCertificateRef,
    )
    mechanism_ids = _covered_mechanism_ids(
        ctx,
        state,
        kind="ir.incentive_compatibility_certificate",
        ref_cls=IncentiveCompatibilityCertificateRef,
    )
    welfare_bound_ids = _covered_mechanism_ids(
        ctx,
        state,
        kind="ir.mechanism_welfare_loss_bound",
        ref_cls=MechanismWelfareLossBoundRef,
    )
    expected_set = set(expected)
    return {
        "unsupported": unsupported or not expected_set or _mechanism_family_unsupported(ctx, state),
        "missing_certificates": bool(
            expected_set
            and (
                not expected_set.issubset(semantic_ids) or not expected_set.issubset(mechanism_ids)
            )
        ),
        "missing_welfare_bounds": bool(
            expected_set and not expected_set.issubset(welfare_bound_ids)
        ),
    }


def _expected_mechanism_family_ids(
    candidate: PolicyCandidateSchema | None,
) -> tuple[tuple[str, ...], bool]:
    if candidate is None:
        return (), True
    policy = candidate.trinity_bundle.policy_spec
    design = policy.mechanism_design
    if design is None:
        return (), False

    raw_ids: list[str] = []
    raw_ids.extend(str(item) for item in getattr(design, "mechanism_ids", ()) or ())
    raw_ids.extend(
        str(binding.mechanism_id)
        for binding in getattr(policy, "mechanism_bindings", ()) or ()
        if getattr(binding, "mechanism_id", None) is not None
    )
    raw_ids.extend(
        str(intervention.kind)
        for intervention in getattr(policy, "interventions", ()) or ()
        if getattr(intervention, "kind", None) is not None
    )
    supported = tuple(
        dict.fromkeys(
            mechanism_id
            for mechanism_id in raw_ids
            if mechanism_id in _SUPPORTED_MECHANISM_FAMILY_IDS
        )
    )
    design_declared_ids = [str(item) for item in getattr(design, "mechanism_ids", ()) or ()]
    binding_declared_ids = [
        str(binding.mechanism_id)
        for binding in getattr(policy, "mechanism_bindings", ()) or ()
        if getattr(binding, "mechanism_id", None) is not None
    ]
    unsupported = any(
        mechanism_id not in _SUPPORTED_MECHANISM_FAMILY_IDS
        for mechanism_id in (*design_declared_ids, *binding_declared_ids)
    )
    if not supported:
        unsupported = True
    return supported, unsupported


def _covered_mechanism_ids(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    kind: str,
    ref_cls,
) -> set[str]:
    covered: set[str] = set()
    for ref in _refs_by_kind(state.artifacts_index, kind=kind, ref_cls=ref_cls):
        payload = _load_json_mapping(ctx, ref)
        if payload is None:
            continue
        covered.update(_extract_mechanism_ids(payload))
    return covered


def _extract_mechanism_ids(payload: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in ("mechanism_id",):
        value = payload.get(key)
        if value is not None:
            ids.add(str(value))
    for key in ("mechanism_ids", "covered_mechanism_ids"):
        value = payload.get(key)
        if isinstance(value, (list, tuple)):
            ids.update(str(item) for item in value)
    witness = payload.get("witness")
    if isinstance(witness, Mapping):
        ids.update(_extract_mechanism_ids(witness))
    per_family = payload.get("per_family")
    if isinstance(per_family, list):
        for item in per_family:
            if isinstance(item, Mapping):
                ids.update(_extract_mechanism_ids(item))
    for key in (
        "mechanism_ic_certificate_refs",
        "mechanism_welfare_loss_bound_refs",
        "mechanism_family_spec_refs",
    ):
        value = payload.get(key)
        if isinstance(value, Mapping):
            ids.update(str(item) for item in value.keys())
    return ids


def _mechanism_family_unsupported(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> bool:
    if (
        _pick_first_ref(
            state.artifacts_index,
            kind="ir.incentive_compatibility_certificate",
            ref_cls=IncentiveCompatibilityCertificateRef,
        )
        is not None
    ):
        return False
    if (
        _pick_first_ref(
            state.artifacts_index,
            kind="scientist.ic_certificate",
            ref_cls=ICVerificationCertificateRef,
        )
        is not None
    ):
        return True

    report_refs: list[ICVerificationReportRef] = []
    for value in state.artifacts_index.values():
        ref = _coerce_ref(value, ICVerificationReportRef)
        if ref is not None:
            report_refs.append(ref)
    for ref in report_refs:
        try:
            report = ICVerificationReport.model_validate(
                from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
            )
        except (OSError, RuntimeError, TypeError, ValueError):
            continue
        if report.verdict in {"unsupported_fragment", "semantic_validation_failure"}:
            return True
    return False


def _resolve_behavior_model_ref(state: ExperimentState) -> ArtifactRef | None:
    for key in (
        "behavior_model_ref",
        "behavioral_model_ref",
        "behavioral_response_ref",
        "behavioral_source_artifact_ref",
    ):
        ref = _coerce_ref(state.params.get(key), ArtifactRef)
        if ref is not None:
            return ref
    return None


def _resolve_fiscal_feedback_ref(
    state: ExperimentState,
) -> FiscalFeedbackLinkRef | None:
    ref = _coerce_ref(
        state.artifacts_index.get(ARTIFACT_FISCAL_FEEDBACK_LINK_REF), FiscalFeedbackLinkRef
    )
    if ref is not None:
        return ref
    ref = _coerce_ref(state.params.get("fiscal_feedback_ref"), FiscalFeedbackLinkRef)
    if ref is not None:
        return ref
    microsim = state.params.get("microsim_result")
    if microsim is not None:
        try:
            result = MicrosimResult.model_validate(microsim)
        except (TypeError, ValueError):
            return None
        return result.fiscal_feedback_ref
    return None


def _phase3_fiscal_feedback_required(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    welfare_bundle,
    ambiguity_certificate_ref: OptimizationAmbiguityCertificateRef | None,
) -> bool:
    if bool(state.params.get("require_phase3_fiscal_feedback")):
        return True
    if ambiguity_certificate_ref is None:
        return False
    microsim_present = state.params.get("microsim_result") is not None
    if not microsim_present:
        return False
    if _resolve_behavior_model_ref(state) is not None or bool(
        state.params.get("behavioral_microsim")
    ):
        return True
    if welfare_bundle.channel_decomposition_ref is None:
        return False
    try:
        decomposition = load_channel_decomposition_artifact(
            ctx.store,
            welfare_bundle.channel_decomposition_ref,
        )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return False
    return (
        decomposition.behavioral_vector is not None
        or decomposition.fiscal_feedback_vector is not None
    )


def _resolve_social_weight_manifest_candidate(
    welfare_params: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    for key in (
        "welfare_social_weight_manifest",
        "welfare_social_weight_ref",
        "social_weight_manifest",
        "social_weight_ref",
    ):
        value = welfare_params.get(key)
        if isinstance(value, Mapping):
            return _resolve_registered_social_weight_manifest(value)
        resolved, handle = _resolve_social_weight_handle(value)
        if resolved is not None:
            return resolved, handle
    return None, None


def _resolve_registered_social_weight_manifest(
    manifest: Mapping[str, Any],
) -> tuple[dict[str, Any], str | None]:
    registered = register_social_weight_manifest(manifest)
    return dict(registered), str(registered.get("ref"))


def _resolve_social_weight_handle(
    value: Any,
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return None, None
    manifest = resolve_social_weight_manifest(value.strip())
    if manifest is None:
        return None, None
    return dict(manifest), value.strip()


def _pick_first_ref(
    artifacts_index: Mapping[str, Any],
    *,
    kind: str,
    ref_cls,
):
    for key in sorted(artifacts_index):
        value = artifacts_index[key]
        if not isinstance(value, ArtifactRef):
            try:
                value = ArtifactRef.model_validate(value)
            except (TypeError, ValueError):
                continue
        if value.kind != kind:
            continue
        try:
            return ref_cls.model_validate(value.model_dump(mode="json"))
        except (TypeError, ValueError):
            continue
    return None


def _refs_by_kind(
    artifacts_index: Mapping[str, Any],
    *,
    kind: str,
    ref_cls,
) -> list[Any]:
    refs: list[Any] = []
    for key in sorted(artifacts_index):
        value = artifacts_index[key]
        if not isinstance(value, ArtifactRef):
            try:
                value = ArtifactRef.model_validate(value)
            except (TypeError, ValueError):
                continue
        if value.kind != kind:
            continue
        try:
            refs.append(ref_cls.model_validate(value.model_dump(mode="json")))
        except (TypeError, ValueError):
            continue
    return refs


def _coerce_ref(value: Any, ref_cls):
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    try:
        return ref_cls.model_validate(value)
    except (TypeError, ValueError):
        return None


def _load_json_mapping(ctx: ExecutionContext, ref: ArtifactRef) -> dict[str, Any] | None:
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
    except (OSError, RuntimeError, TypeError, ValueError):
        return None
    if isinstance(payload, Mapping):
        return _json_mapping(payload)
    return None


def _json_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_value(item) for key, item in value.items()}


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    if hasattr(value, "model_dump"):
        return _json_value(value.model_dump(mode="json"))
    if hasattr(value, "to_payload") and callable(value.to_payload):
        return _json_value(value.to_payload())
    return value


def _float_tuple(value: Any) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(float(item) for item in value)


def _str_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value)


__all__ = [
    "Phase3CertificateStatus",
    "ensure_fiscal_feedback_link",
    "ensure_optimization_ambiguity_certificate",
    "ensure_social_weight_manifest_artifact",
    "phase3_ambiguity_required",
    "phase3_gate_reference_blockers",
    "resolve_phase3_gate",
]
