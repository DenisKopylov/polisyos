"""Decision-packet basis projections."""

from __future__ import annotations

from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.decision_validity import (
    DecisionBasisSection,
    DecisionDependencyKind,
    DecisionDependencyRef,
    DecisionTriggerSpec,
    DecisionTriggerType,
)
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.scholar import FreshnessMetadata
from polisyos.ir.analytics.normative_arbitration import (
    NormativeArbitrationResult,
    load_normative_arbitration_result,
)
from polisyos.ir.analytics.sensitivity import (
    load_sensitivity_result,
    persist_sensitivity_analysis_bundle,
    sensitivity_analysis_bundle_from_result,
)
from polisyos.ir.registry.refs import CausalSensitivityResultRef, NormativeArbitrationResultRef
from polisyos.scientist.nodes.builtins.decide.decision_packet.serialization import (
    _dedupe_dependency_refs,
    _dependency_ref,
    _load_json_payload_by_ref,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.validation import (
    _DECISION_PACKET_LOAD_ERRORS,
    _collect_contract_warnings,
    _has_governance_issue_code,
    _load_resolved_fidelity_level,
    _nested_status,
    _record_decision_packet_section_degraded,
    _summarize_governance_issues,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet_support import _path_get
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_ECONOMETRIC_EVIDENCE_REF,
    ARTIFACT_INPUT_BINDING_REPORT_REF,
    ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF,
    ARTIFACT_SENSITIVITY_ANALYSIS_BUNDLE_REF,
    ARTIFACT_SENSITIVITY_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_KNOWLEDGE_BUNDLE_REF,
    INPUT_NORM_PACK_REF,
    INPUT_RESEARCH_INTENT_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_LEGAL_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

logger = get_logger(__name__)


def _load_normative_arbitration(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> NormativeArbitrationResult | None:
    ref = artifacts_index.get(ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF)
    if ref is None:
        return None
    try:
        return load_normative_arbitration_result(
            _ensure_ir_artifact_store(ctx.store),
            NormativeArbitrationResultRef(artifact_id=ref.artifact_id),
        )
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        logger.debug("Failed to parse normative arbitration result from ref %s", ref, exc_info=True)
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_normative_arbitration_result",
            reason="normative_arbitration_load_failed",
            exc=exc,
            ref=ref,
            artifact_key=ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF,
        )
        return None


def _build_aux_artifact_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    key: str,
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    ref = artifacts_index.get(key)
    if ref is None:
        return None
    payload: dict[str, object] = {"ref": str(ref.artifact_id)}
    try:
        artifact_obj = from_canonical_bytes(ctx.store.get_bytes(ref))
        if isinstance(artifact_obj, dict):
            payload["content"] = artifact_obj
        else:
            payload["content_type"] = type(artifact_obj).__name__
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        payload["parse_warning"] = "artifact_parse_failed"
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_aux_artifact",
            reason="aux_artifact_load_failed",
            exc=exc,
            ref=ref,
            artifact_key=key,
        )
    return payload


def _build_sensitivity_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    canonical_ref = artifacts_index.get(ARTIFACT_SENSITIVITY_ANALYSIS_BUNDLE_REF)
    if canonical_ref is not None:
        try:
            artifact_obj = from_canonical_bytes(ctx.store.get_bytes(canonical_ref))
            return {
                "ref": str(canonical_ref.artifact_id),
                "sensitivity_analysis_bundle_ref": str(canonical_ref.artifact_id),
                "content": artifact_obj,
            }
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_sensitivity_analysis_bundle",
                reason="sensitivity_analysis_bundle_load_failed",
                exc=exc,
                ref=canonical_ref,
                artifact_key=ARTIFACT_SENSITIVITY_ANALYSIS_BUNDLE_REF,
            )

    ref = artifacts_index.get(ARTIFACT_SENSITIVITY_RESULT_REF)
    if ref is None:
        return None
    payload: dict[str, object] = {"ref": str(ref.artifact_id)}
    try:
        result = load_sensitivity_result(
            _ensure_ir_artifact_store(ctx.store),
            CausalSensitivityResultRef.model_validate(ref.model_dump(mode="json")),
        )
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_sensitivity_result",
            reason="sensitivity_result_load_failed",
            exc=exc,
            ref=ref,
            artifact_key=ARTIFACT_SENSITIVITY_RESULT_REF,
        )
        try:
            artifact_obj = from_canonical_bytes(ctx.store.get_bytes(ref))
            if isinstance(artifact_obj, dict):
                payload["content"] = artifact_obj
        except _DECISION_PACKET_LOAD_ERRORS as fallback_exc:
            payload["parse_warning"] = "artifact_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_sensitivity_fallback_artifact",
                reason="sensitivity_fallback_artifact_load_failed",
                exc=fallback_exc,
                ref=ref,
                artifact_key=ARTIFACT_SENSITIVITY_RESULT_REF,
            )
        payload.setdefault("parse_warning", "sensitivity_parse_failed")
        return payload

    content = result.model_dump(mode="json")
    try:
        bundle = sensitivity_analysis_bundle_from_result(
            result,
            bundle_id=f"legacy_sensitivity_result_{str(ref.artifact_id)[:12]}",
            source_ref=str(ref.artifact_id),
        )
        bundle_ref = persist_sensitivity_analysis_bundle(
            _ensure_ir_artifact_store(ctx.store),
            bundle,
            inputs=[InputRef(artifact_id=ref.artifact_id, role="legacy_sensitivity_result")],
        )
        payload["sensitivity_analysis_bundle_ref"] = str(bundle_ref.artifact_id)
        payload["sensitivity_analysis_bundle"] = bundle.model_dump(mode="json")
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        payload["parse_warning"] = "sensitivity_bundle_wrap_failed"
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="wrap_sensitivity_analysis_bundle",
            reason="sensitivity_bundle_wrap_failed",
            exc=exc,
            ref=ref,
            artifact_key=ARTIFACT_SENSITIVITY_RESULT_REF,
        )
    content["summary"] = {
        "status": "robust" if result.is_robust else "fragile",
        "e_value": result.e_value,
        "e_value_ci_lower": result.e_value_ci_lower,
        "robustness_value": result.robustness_value,
        "rosenbaum_gamma": result.rosenbaum_gamma,
        "benchmark_covariate_count": len(result.benchmark_covariates),
    }
    payload["content"] = content
    return payload


def _build_diagnostics_summary(
    *,
    ctx: ExecutionContext,
    packet_payload: dict[str, object],
    state: ExperimentState,
) -> dict[str, object]:
    governance = packet_payload.get("governance")
    governance_dict = governance if isinstance(governance, dict) else {}
    issues = governance_dict.get("issues")
    issue_summary = _summarize_governance_issues(issues if isinstance(issues, list) else [])

    causal = packet_payload.get("causal")
    causal_dict = causal if isinstance(causal, dict) else {}
    transport_summary = causal_dict.get("transportability_summary")
    transport_dict = transport_summary if isinstance(transport_summary, dict) else {}
    sensitivity = packet_payload.get("sensitivity")
    sensitivity_dict = sensitivity if isinstance(sensitivity, dict) else {}
    sensitivity_content = sensitivity_dict.get("content")
    sensitivity_content_dict = sensitivity_content if isinstance(sensitivity_content, dict) else {}
    sensitivity_summary = sensitivity_content_dict.get("summary")
    sensitivity_summary_dict = sensitivity_summary if isinstance(sensitivity_summary, dict) else {}
    causal_validity = packet_payload.get("causal_validity")
    causal_validity_dict = causal_validity if isinstance(causal_validity, dict) else {}
    validity_content = causal_validity_dict.get("content")
    validity_content_dict = validity_content if isinstance(validity_content, dict) else {}
    validity_checks = validity_content_dict.get("checks")
    validity_checks_dict = validity_checks if isinstance(validity_checks, dict) else {}

    replay = packet_payload.get("replay")
    replay_dict = replay if isinstance(replay, dict) else {}

    uncertainty = packet_payload.get("uncertainty")
    uncertainty_dict = uncertainty if isinstance(uncertainty, dict) else {}
    uncertainty_bounds = packet_payload.get("uncertainty_bounds")
    normative_result = _load_normative_arbitration(ctx, state.artifacts_index)
    degraded_paths = packet_payload.get("degraded_paths")
    degraded_path_items = (
        [item for item in degraded_paths if isinstance(item, dict)]
        if isinstance(degraded_paths, list)
        else []
    )

    governance_links = governance_dict.get("links")
    legal_ref = None
    if isinstance(governance_links, dict):
        legal_ref = governance_links.get("legal_report_ref")
        if isinstance(legal_ref, dict):
            legal_ref = legal_ref.get("artifact_id")
    if not isinstance(legal_ref, str):
        artifacts = packet_payload.get("artifacts")
        artifacts_dict = artifacts if isinstance(artifacts, dict) else {}
        fallback_legal_ref = artifacts_dict.get(REPORT_LEGAL_REPORT_REF)
        legal_ref = fallback_legal_ref if isinstance(fallback_legal_ref, str) else None

    has_legal_report = legal_ref is not None
    has_distributional_report = bool(packet_payload.get("distributional"))
    has_causal_report = bool(causal_dict)
    has_abstraction_certificate = bool(packet_payload.get("abstraction_certificate"))
    uncertainty_available = bool(uncertainty_dict.get("envelope_count")) or isinstance(
        uncertainty_bounds, dict
    )
    contract_warnings = _collect_contract_warnings(ctx, state)
    resolved_fidelity_level = _load_resolved_fidelity_level(ctx, state)
    requires_expert_review = bool(transport_dict.get("requires_expert_review")) or bool(
        state.params.get("needs_expert_review")
    )
    human_review_needed = (
        bool(state.params.get("require_human_gate"))
        or _has_governance_issue_code(
            issues if isinstance(issues, list) else [],
            code="HUMAN_REVIEW_REQUESTED",
        )
        or requires_expert_review
    )
    rights_violation_count = 0
    residual_dissent_count = 0
    normative_model_completeness = None
    normative_selected_policy = None
    normative_selected_option = None
    if normative_result is not None:
        rights_violation_count = sum(
            1
            for item in normative_result.rights_audit
            if item.status.value == "violated" and "soft_right" not in item.notes
        )
        residual_dissent_count = len(normative_result.residual_dissent)
        normative_model_completeness = normative_result.model_completeness.value
        normative_selected_policy = normative_result.selected_policy.value
        normative_selected_option = normative_result.selected_option.value

    return {
        "governance_verdict": governance_dict.get("verdict"),
        "blocker_count": issue_summary["blocker_count"],
        "warning_count": issue_summary["warning_count"],
        "info_count": issue_summary["info_count"],
        "transport_status": transport_dict.get("status", "not_run"),
        "transport_engine": transport_dict.get("identification_engine", "not_available"),
        "sensitivity_status": sensitivity_summary_dict.get("status"),
        "sensitivity_is_robust": sensitivity_content_dict.get("is_robust"),
        "icp_status": _nested_status(validity_checks_dict, "icp_invariance"),
        "proximal_status": _nested_status(validity_checks_dict, "proximal_bridge"),
        "recoverability_status": _nested_status(validity_checks_dict, "recoverability"),
        "pag_refinement_status": _nested_status(validity_checks_dict, "pag_refinement"),
        "requires_expert_review": requires_expert_review,
        "replay_readiness": replay_dict.get("readiness"),
        "replay_missing_inputs": list(replay_dict.get("missing_refs", []))
        if isinstance(replay_dict.get("missing_refs"), list)
        else [],
        "has_legal_report": has_legal_report,
        "legal_executed": has_legal_report,
        "has_distributional_report": has_distributional_report,
        "has_causal_report": has_causal_report,
        "has_abstraction_certificate": has_abstraction_certificate,
        "uncertainty_available": uncertainty_available,
        "human_review_needed": human_review_needed,
        "has_normative_arbitration": normative_result is not None,
        "normative_selected_policy": normative_selected_policy,
        "normative_selected_option": normative_selected_option,
        "normative_model_completeness": normative_model_completeness,
        "normative_residual_dissent_count": residual_dissent_count,
        "normative_rights_violation_count": rights_violation_count,
        "determinism_tier": replay_dict.get("determinism_tier"),
        "seed_source": replay_dict.get("seed_source"),
        "resolved_fidelity_level": resolved_fidelity_level,
        "contract_warnings": contract_warnings,
        "degraded_path_count": len(degraded_path_items),
        "degraded_reasons": [
            str(item.get("reason", "decision_packet_degraded")) for item in degraded_path_items
        ],
        "has_degraded_paths": bool(degraded_path_items),
    }


def _build_normative_basis(packet_payload: dict[str, object]) -> DecisionBasisSection:
    dependencies: list[DecisionDependencyRef] = []
    summary: dict[str, object] = {}
    norm_pack_ref = _path_get(packet_payload, ("inputs", INPUT_NORM_PACK_REF))
    legal_report_ref = _path_get(packet_payload, ("artifacts", REPORT_LEGAL_REPORT_REF))
    normative_result_ref = _path_get(
        packet_payload,
        ("artifacts", ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF),
    )
    if isinstance(norm_pack_ref, str):
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.NORM_PACK,
                f"norm_pack:{norm_pack_ref}",
                artifact_id=norm_pack_ref,
                label="norm_pack_ref",
            )
        )
        summary["norm_pack_ref"] = norm_pack_ref
    if isinstance(legal_report_ref, str):
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.LEGAL_REPORT,
                f"legal_report:{legal_report_ref}",
                artifact_id=legal_report_ref,
                label="legal_report_ref",
            )
        )
        summary["legal_report_ref"] = legal_report_ref
    if isinstance(normative_result_ref, str):
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.NORMATIVE_ARBITRATION,
                f"normative_arbitration:{normative_result_ref}",
                artifact_id=normative_result_ref,
                label="normative_arbitration_result_ref",
            )
        )
        summary["normative_arbitration_result_ref"] = normative_result_ref
    governance = packet_payload.get("governance")
    if isinstance(governance, dict):
        summary["governance_verdict"] = governance.get("verdict")
    diagnostics = packet_payload.get("diagnostics_summary")
    if isinstance(diagnostics, dict):
        summary["legal_executed"] = bool(diagnostics.get("legal_executed"))
        summary["normative_selected_policy"] = diagnostics.get("normative_selected_policy")
        summary["normative_selected_option"] = diagnostics.get("normative_selected_option")
        summary["normative_model_completeness"] = diagnostics.get("normative_model_completeness")
        summary["normative_residual_dissent_count"] = diagnostics.get(
            "normative_residual_dissent_count"
        )
        summary["normative_rights_violation_count"] = diagnostics.get(
            "normative_rights_violation_count"
        )
    return DecisionBasisSection(dependencies=dependencies, summary=summary)


def _build_data_basis(
    ctx: ExecutionContext,
    packet_payload: dict[str, object],
) -> DecisionBasisSection:
    dependencies: list[DecisionDependencyRef] = []
    summary: dict[str, Any] = {}
    data_snapshot_ref = _path_get(packet_payload, ("inputs", INPUT_DATA_SNAPSHOT_REF))
    binding_report_ref = _path_get(packet_payload, ("artifacts", ARTIFACT_INPUT_BINDING_REPORT_REF))
    if isinstance(data_snapshot_ref, str):
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.DATA_SNAPSHOT,
                f"data_snapshot:{data_snapshot_ref}",
                artifact_id=data_snapshot_ref,
                label="data_snapshot_ref",
            )
        )
        summary["data_snapshot_ref"] = data_snapshot_ref
    if isinstance(binding_report_ref, str):
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.INPUT_BINDING_REPORT,
                f"input_binding_report:{binding_report_ref}",
                artifact_id=binding_report_ref,
                label="input_binding_report_ref",
            )
        )
        summary["input_binding_report_ref"] = binding_report_ref

    snapshot_payload = _load_json_payload_by_ref(
        ctx,
        data_snapshot_ref,
        packet_payload=packet_payload,
        operation="load_decision_basis_data_snapshot",
        reason="decision_basis_data_snapshot_load_failed",
        artifact_key=INPUT_DATA_SNAPSHOT_REF,
    )
    if snapshot_payload is None:
        return DecisionBasisSection(dependencies=dependencies, summary=summary)

    try:
        snapshot = DataSnapshot.model_validate(snapshot_payload)
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="validate_decision_basis_data_snapshot",
            reason="decision_basis_data_snapshot_validate_failed",
            exc=exc,
            artifact_id=data_snapshot_ref,
            artifact_key=INPUT_DATA_SNAPSHOT_REF,
        )
        return DecisionBasisSection(dependencies=dependencies, summary=summary)

    summary["stats"] = dict(snapshot.stats)
    summary["notes"] = list(snapshot.notes)
    summary["pii_scan_summary"] = snapshot.pii_scan_summary
    if snapshot.quality_report_ref is not None:
        quality_report_ref = str(snapshot.quality_report_ref.artifact_id)
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.QUALITY_REPORT,
                f"quality_report:{quality_report_ref}",
                artifact_id=quality_report_ref,
                label="quality_report_ref",
            )
        )
        summary["quality_report_ref"] = quality_report_ref
        quality_payload = _load_json_payload_by_ref(
            ctx,
            quality_report_ref,
            packet_payload=packet_payload,
            operation="load_decision_basis_quality_report",
            reason="decision_basis_quality_report_load_failed",
            artifact_key="quality_report_ref",
        )
        if isinstance(quality_payload, dict):
            dataset_id = quality_payload.get("dataset_id")
            schema_id = quality_payload.get("schema_id")
            if isinstance(dataset_id, str) and dataset_id:
                dataset_dependency = _dependency_ref(
                    DecisionDependencyKind.DATASET,
                    f"dataset:{dataset_id}",
                    label=dataset_id,
                )
                dependencies.append(dataset_dependency)
                summary["dataset_id"] = dataset_id
                summary["dataset_dependency_key"] = dataset_dependency.key
            if isinstance(schema_id, str) and schema_id:
                dependencies.append(
                    _dependency_ref(
                        DecisionDependencyKind.DATA_SCHEMA,
                        f"data_schema:{schema_id}",
                        label=schema_id,
                    )
                )
                summary["schema_id"] = schema_id
            freshness = quality_payload.get("freshness_status")
            if isinstance(freshness, dict):
                summary["freshness_level"] = freshness.get("level")
                summary["is_fresh"] = freshness.get("is_fresh")
                summary["data_age_seconds"] = freshness.get("data_age_seconds")
                summary["freshness_message"] = freshness.get("message")
            quality_flags = quality_payload.get("quality_flags")
            if isinstance(quality_flags, list):
                summary["quality_flags"] = [str(item) for item in quality_flags]
            violations = quality_payload.get("violations")
            if isinstance(violations, list):
                messages = [
                    str(item.get("message", "")).lower()
                    for item in violations
                    if isinstance(item, dict)
                ]
                summary["schema_drift"] = any("schema drift" in msg for msg in messages)
                summary["contract_drift"] = any(
                    "contract drift" in msg or "supersed" in msg for msg in messages
                )

    return DecisionBasisSection(
        dependencies=_dedupe_dependency_refs(dependencies),
        summary=summary,
    )


def _build_knowledge_basis(
    ctx: ExecutionContext,
    packet_payload: dict[str, object],
) -> DecisionBasisSection:
    dependencies: list[DecisionDependencyRef] = []
    summary: dict[str, Any] = {}
    knowledge_bundle_ref = _path_get(packet_payload, ("inputs", INPUT_KNOWLEDGE_BUNDLE_REF))
    research_intent_ref = _path_get(packet_payload, ("inputs", INPUT_RESEARCH_INTENT_REF))
    if isinstance(knowledge_bundle_ref, str):
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.KNOWLEDGE_BUNDLE,
                f"knowledge_bundle:{knowledge_bundle_ref}",
                artifact_id=knowledge_bundle_ref,
                label="knowledge_bundle_ref",
            )
        )
        summary["knowledge_bundle_ref"] = knowledge_bundle_ref
        summary["knowledge_dependency_key"] = f"knowledge_bundle:{knowledge_bundle_ref}"
    if isinstance(research_intent_ref, str):
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.RESEARCH_INTENT,
                f"research_intent:{research_intent_ref}",
                artifact_id=research_intent_ref,
                label="research_intent_ref",
            )
        )
    for artifact_key in (
        ARTIFACT_CAUSAL_REPORT_REF,
        ARTIFACT_CAUSAL_ENSEMBLE_REF,
        ARTIFACT_ECONOMETRIC_EVIDENCE_REF,
    ):
        artifact_ref = _path_get(packet_payload, ("artifacts", artifact_key))
        if isinstance(artifact_ref, str):
            dependencies.append(
                _dependency_ref(
                    DecisionDependencyKind.CAUSAL_EVIDENCE,
                    f"causal_evidence:{artifact_ref}",
                    artifact_id=artifact_ref,
                    label=artifact_key,
                )
            )

    bundle_payload = _load_json_payload_by_ref(
        ctx,
        knowledge_bundle_ref,
        packet_payload=packet_payload,
        operation="load_decision_basis_knowledge_bundle",
        reason="decision_basis_knowledge_bundle_load_failed",
        artifact_key=INPUT_KNOWLEDGE_BUNDLE_REF,
    )
    if isinstance(bundle_payload, dict):
        freshness_payload = bundle_payload.get("freshness")
        if isinstance(freshness_payload, dict):
            try:
                freshness = FreshnessMetadata.model_validate(freshness_payload)
                summary["freshness_status"] = freshness.compute_status().value
                summary["source_freshness_at"] = (
                    freshness.source_freshness_at.isoformat()
                    if freshness.source_freshness_at is not None
                    else None
                )
                summary["enrichment_count"] = freshness.enrichment_count
            except _DECISION_PACKET_LOAD_ERRORS as exc:
                _record_decision_packet_section_degraded(
                    packet_payload,
                    operation="validate_decision_basis_knowledge_freshness",
                    reason="decision_basis_knowledge_freshness_validate_failed",
                    exc=exc,
                    artifact_id=knowledge_bundle_ref,
                    artifact_key=INPUT_KNOWLEDGE_BUNDLE_REF,
                )
                summary["freshness_status"] = "unknown"
        notes = bundle_payload.get("notes")
        if isinstance(notes, list):
            summary["notes"] = [str(item) for item in notes]

    return DecisionBasisSection(
        dependencies=_dedupe_dependency_refs(dependencies),
        summary=summary,
    )


def _build_transportability_basis(
    *,
    state: ExperimentState,
    packet_payload: dict[str, object],
    source_context_fingerprint: str | None,
    target_context_fingerprint: str | None,
) -> DecisionBasisSection:
    dependencies: list[DecisionDependencyRef] = []
    summary: dict[str, Any] = {}
    causal = packet_payload.get("causal")
    causal_dict = causal if isinstance(causal, dict) else {}
    transport = causal_dict.get("transportability_summary")
    transport_dict = dict(transport) if isinstance(transport, dict) else {}
    if transport_dict:
        summary.update(transport_dict)
    summary["source_context_fingerprint"] = source_context_fingerprint
    summary["target_context_fingerprint"] = target_context_fingerprint
    assumptions = state.params.get("transportability_assumptions")
    if isinstance(assumptions, list):
        summary["assumptions"] = list(assumptions)
    elif isinstance(assumptions, dict):
        summary["assumptions"] = assumptions

    capability_hash = transport_dict.get("capability_hash")
    if isinstance(capability_hash, str) and capability_hash:
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.TRANSPORTABILITY,
                f"transportability_capability:{capability_hash}",
                label="transportability_capability_hash",
            )
        )
    if target_context_fingerprint is not None:
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.CONTEXT_PROFILE,
                f"context_profile:{target_context_fingerprint}",
                label="target_context",
            )
        )
    if source_context_fingerprint is not None:
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.CONTEXT_PROFILE,
                f"context_profile:{source_context_fingerprint}",
                label="source_context",
            )
        )

    return DecisionBasisSection(
        dependencies=_dedupe_dependency_refs(dependencies),
        summary=summary,
    )


def _build_watched_triggers(
    *,
    normative_basis: DecisionBasisSection,
    data_basis: DecisionBasisSection,
    knowledge_basis: DecisionBasisSection,
    transportability_basis: DecisionBasisSection,
) -> list[DecisionTriggerSpec]:
    return [
        DecisionTriggerSpec(
            trigger_type=DecisionTriggerType.LAW_CHANGE,
            dependency_keys=[item.key for item in normative_basis.dependencies],
            description="Watch norm/legal dependencies for change or hard invalidation.",
        ),
        DecisionTriggerSpec(
            trigger_type=DecisionTriggerType.DATASET_SUPERSEDED,
            dependency_keys=[item.key for item in data_basis.dependencies],
            description="Watch dataset supersede and cache invalidation signals.",
        ),
        DecisionTriggerSpec(
            trigger_type=DecisionTriggerType.HISTORICAL_SEMANTIC_REVISION,
            dependency_keys=[item.key for item in data_basis.dependencies],
            description="Watch schema or semantic revision of historical data.",
        ),
        DecisionTriggerSpec(
            trigger_type=DecisionTriggerType.CONTRADICTING_EVIDENCE,
            dependency_keys=[item.key for item in knowledge_basis.dependencies],
            description="Watch contradictory evidence, retractions, and stale scholar bundles.",
        ),
        DecisionTriggerSpec(
            trigger_type=DecisionTriggerType.CONTEXT_PROFILE_DRIFT,
            dependency_keys=[item.key for item in transportability_basis.dependencies],
            description="Watch source/target context profile drift.",
        ),
    ]


def _load_normative_frame_payload(
    ctx: ExecutionContext,
    packet_payload: dict[str, object],
) -> dict[str, Any] | None:
    trinity_bundle_ref = _path_get(packet_payload, ("inputs", INPUT_TRINITY_BUNDLE_REF))
    bundle = _load_json_payload_by_ref(
        ctx,
        trinity_bundle_ref,
        packet_payload=packet_payload,
        operation="load_decision_basis_trinity_bundle",
        reason="decision_basis_trinity_bundle_load_failed",
        artifact_key=INPUT_TRINITY_BUNDLE_REF,
    )
    if bundle is None:
        return None
    problem_frame = bundle.get("problem_frame")
    if not isinstance(problem_frame, dict):
        return None
    normative_frame = problem_frame.get("normative_frame")
    return normative_frame if isinstance(normative_frame, dict) else None
