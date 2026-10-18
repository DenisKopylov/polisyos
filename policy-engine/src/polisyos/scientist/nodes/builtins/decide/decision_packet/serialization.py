"""Decision-packet serialization and artifact-reference helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.contracts.decision_validity import (
    DecisionDependencyKind,
    DecisionDependencyRef,
)
from polisyos.ir.registry.refs import (
    SensitivityAnalysisBundleRef,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.validation import (
    _DECISION_PACKET_LOAD_ERRORS,
    _record_decision_packet_section_degraded,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ABM_ALIGNMENT_REPORT_REF,
    ARTIFACT_ABSTRACTION_CERTIFICATE_REF,
    ARTIFACT_BACKTEST_REPORT_REF,
    ARTIFACT_BOUNDS_BUNDLE_REF,
    ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF,
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF,
    ARTIFACT_CLAIMS_REF,
    ARTIFACT_CONTINUOUS_GOVERNANCE_REPORT_REF,
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_DECISION_CARD_REF,
    ARTIFACT_DECISION_READINESS_CONTRACT_REF,
    ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_ECONOMETRIC_ENVELOPE_REF,
    ARTIFACT_ECONOMETRIC_EVIDENCE_REF,
    ARTIFACT_ECONOMETRIC_RESULT_REF,
    ARTIFACT_ENVIRONMENT_MANIFEST_REF,
    ARTIFACT_EXEC_PLAN_REF,
    ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF,
    ARTIFACT_HTE_RESULT_REF,
    ARTIFACT_HUMAN_REVIEW_DECISION_REF,
    ARTIFACT_HUMAN_REVIEW_PACKET_REF,
    ARTIFACT_INPUT_BINDING_REPORT_REF,
    ARTIFACT_LOWERED_IR_REF,
    ARTIFACT_METRIC_OBSERVATION_BUNDLE_REF,
    ARTIFACT_METRIC_VALIDATION_REPORT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_NORM_IMPACT_REPORT_REF,
    ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF,
    ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF,
    ARTIFACT_POLICY_RECOMMENDATION_REF,
    ARTIFACT_PROGRAM_GRAPH_REF,
    ARTIFACT_REISSUE_PACKET_REF,
    ARTIFACT_RESEARCH_DAG_REF,
    ARTIFACT_SENSITIVITY_RESULT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_STATE_SNAPSHOT_REF,
    ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
    ARTIFACT_STRATEGIC_SCM_REF,
    ARTIFACT_STRESS_TEST_REPORT_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
    ARTIFACT_VOI_RUN_REPORT_REF,
    ARTIFACT_WEB_EVIDENCE_BUNDLE_REF,
    ARTIFACT_WELFARE_BUNDLE_REF,
    ARTIFACT_WITHDRAWAL_RECORD_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_KNOWLEDGE_BUNDLE_REF,
    INPUT_NORM_PACK_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_RESEARCH_INTENT_REF,
    INPUT_STATE_SNAPSHOT_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_CHANGE_PROPOSAL_REF,
    REPORT_COMPILE_REPORT_REF,
    REPORT_GOVERNANCE_REPORT_REF,
    REPORT_LEGAL_REPORT_REF,
    REPORT_LINK_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

logger = get_logger(__name__)


def _claim_source_artifact_refs(state: ExperimentState) -> list[ArtifactRef]:
    refs: list[ArtifactRef] = []
    refs.extend(state.inputs.values())
    refs.extend(state.artifacts_index.values())
    refs.extend(state.reports_index.values())
    output: list[ArtifactRef] = []
    seen: set[tuple[str, str, str, str | None]] = set()
    for ref in refs:
        identity = artifact_ref_identity_key(ref)
        if identity in seen:
            continue
        seen.add(identity)
        output.append(ref)
    return output


def _sensitivity_analysis_bundle_ref_from_packet(
    packet_payload: dict[str, object],
) -> SensitivityAnalysisBundleRef | None:
    section = packet_payload.get("sensitivity")
    if not isinstance(section, dict):
        return None
    ref = section.get("sensitivity_analysis_bundle_ref")
    if not isinstance(ref, str):
        return None
    return SensitivityAnalysisBundleRef.model_validate(
        {
            "artifact_id": ref,
            "kind": "scientist.sensitivity_analysis_bundle",
            "media_type": "application/json",
        }
    )


def _build_inputs_section(
    state_inputs: dict[str, ArtifactRef],
    artifacts_index: dict[str, ArtifactRef],
) -> dict[str, str | None]:
    return {
        INPUT_TRINITY_BUNDLE_REF: _ref_from_dict(state_inputs, INPUT_TRINITY_BUNDLE_REF),
        INPUT_DATA_SNAPSHOT_REF: _ref_from_dict(state_inputs, INPUT_DATA_SNAPSHOT_REF),
        INPUT_STATE_SNAPSHOT_REF: _ref_from_dict(state_inputs, INPUT_STATE_SNAPSHOT_REF),
        INPUT_INPUT_BINDINGS_REF: _ref_from_dict(state_inputs, INPUT_INPUT_BINDINGS_REF),
        INPUT_REGISTRY_BUNDLE_REF: _ref_from_dict(state_inputs, INPUT_REGISTRY_BUNDLE_REF),
        INPUT_NORM_PACK_REF: _ref_from_dict(state_inputs, INPUT_NORM_PACK_REF),
        INPUT_KNOWLEDGE_BUNDLE_REF: _ref_from_dict(state_inputs, INPUT_KNOWLEDGE_BUNDLE_REF),
        INPUT_RESEARCH_INTENT_REF: _ref_from_dict(state_inputs, INPUT_RESEARCH_INTENT_REF),
        ARTIFACT_ENVIRONMENT_MANIFEST_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ENVIRONMENT_MANIFEST_REF
        ),
    }


def _build_artifacts_section(
    artifacts_index: dict[str, ArtifactRef],
    reports_index: dict[str, ArtifactRef],
) -> dict[str, str | None]:
    return {
        ARTIFACT_EXEC_PLAN_REF: _ref_from_dict(artifacts_index, ARTIFACT_EXEC_PLAN_REF),
        ARTIFACT_PROGRAM_GRAPH_REF: _ref_from_dict(artifacts_index, ARTIFACT_PROGRAM_GRAPH_REF),
        ARTIFACT_LOWERED_IR_REF: _ref_from_dict(artifacts_index, ARTIFACT_LOWERED_IR_REF),
        ARTIFACT_SIMULATION_RESULT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_SIMULATION_RESULT_REF
        ),
        ARTIFACT_STATE_SNAPSHOT_REF: _ref_from_dict(artifacts_index, ARTIFACT_STATE_SNAPSHOT_REF),
        ARTIFACT_METRICS_REF: _ref_from_dict(artifacts_index, ARTIFACT_METRICS_REF),
        ARTIFACT_METRIC_OBSERVATION_BUNDLE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_METRIC_OBSERVATION_BUNDLE_REF
        ),
        ARTIFACT_METRIC_VALIDATION_REPORT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_METRIC_VALIDATION_REPORT_REF
        ),
        ARTIFACT_WEB_EVIDENCE_BUNDLE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_WEB_EVIDENCE_BUNDLE_REF
        ),
        ARTIFACT_INPUT_BINDING_REPORT_REF: _ref_from_dict(
            artifacts_index,
            ARTIFACT_INPUT_BINDING_REPORT_REF,
        ),
        REPORT_GOVERNANCE_REPORT_REF: _ref_from_dict(reports_index, REPORT_GOVERNANCE_REPORT_REF),
        REPORT_COMPILE_REPORT_REF: _ref_from_dict(reports_index, REPORT_COMPILE_REPORT_REF),
        REPORT_LINK_REPORT_REF: _ref_from_dict(reports_index, REPORT_LINK_REPORT_REF),
        REPORT_LEGAL_REPORT_REF: _ref_from_dict(reports_index, REPORT_LEGAL_REPORT_REF),
        REPORT_CHANGE_PROPOSAL_REF: _ref_from_dict(reports_index, REPORT_CHANGE_PROPOSAL_REF),
        ARTIFACT_CAUSAL_REPORT_REF: _ref_from_dict(artifacts_index, ARTIFACT_CAUSAL_REPORT_REF),
        ARTIFACT_CAUSAL_ENVELOPE_REF: _ref_from_dict(artifacts_index, ARTIFACT_CAUSAL_ENVELOPE_REF),
        ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF
        ),
        ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF
        ),
        ARTIFACT_CAUSAL_ENSEMBLE_REF: _ref_from_dict(artifacts_index, ARTIFACT_CAUSAL_ENSEMBLE_REF),
        ARTIFACT_ABM_ALIGNMENT_REPORT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ABM_ALIGNMENT_REPORT_REF
        ),
        ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF
        ),
        ARTIFACT_ABSTRACTION_CERTIFICATE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ABSTRACTION_CERTIFICATE_REF
        ),
        ARTIFACT_STRATEGIC_SCM_REF: _ref_from_dict(artifacts_index, ARTIFACT_STRATEGIC_SCM_REF),
        ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF
        ),
        ARTIFACT_HTE_RESULT_REF: _ref_from_dict(artifacts_index, ARTIFACT_HTE_RESULT_REF),
        ARTIFACT_POLICY_RECOMMENDATION_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_POLICY_RECOMMENDATION_REF
        ),
        ARTIFACT_BACKTEST_REPORT_REF: _ref_from_dict(artifacts_index, ARTIFACT_BACKTEST_REPORT_REF),
        ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF
        ),
        ARTIFACT_DISTRIBUTIONAL_REPORT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_DISTRIBUTIONAL_REPORT_REF
        ),
        ARTIFACT_WELFARE_BUNDLE_REF: _ref_from_dict(artifacts_index, ARTIFACT_WELFARE_BUNDLE_REF),
        ARTIFACT_ECONOMETRIC_RESULT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ECONOMETRIC_RESULT_REF
        ),
        ARTIFACT_ECONOMETRIC_EVIDENCE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ECONOMETRIC_EVIDENCE_REF
        ),
        ARTIFACT_ECONOMETRIC_ENVELOPE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ECONOMETRIC_ENVELOPE_REF
        ),
        ARTIFACT_DECISION_CARD_REF: _ref_from_dict(artifacts_index, ARTIFACT_DECISION_CARD_REF),
        ARTIFACT_CLAIMS_REF: _ref_from_dict(artifacts_index, ARTIFACT_CLAIMS_REF),
        ARTIFACT_RESEARCH_DAG_REF: _ref_from_dict(artifacts_index, ARTIFACT_RESEARCH_DAG_REF),
        ARTIFACT_VOI_RUN_REPORT_REF: _ref_from_dict(artifacts_index, ARTIFACT_VOI_RUN_REPORT_REF),
        ARTIFACT_CONTINUOUS_GOVERNANCE_REPORT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_CONTINUOUS_GOVERNANCE_REPORT_REF
        ),
        ARTIFACT_REISSUE_PACKET_REF: _ref_from_dict(artifacts_index, ARTIFACT_REISSUE_PACKET_REF),
        ARTIFACT_WITHDRAWAL_RECORD_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_WITHDRAWAL_RECORD_REF
        ),
        ARTIFACT_HUMAN_REVIEW_PACKET_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_HUMAN_REVIEW_PACKET_REF
        ),
        ARTIFACT_HUMAN_REVIEW_DECISION_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_HUMAN_REVIEW_DECISION_REF
        ),
        ARTIFACT_DECISION_READINESS_CONTRACT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_DECISION_READINESS_CONTRACT_REF
        ),
        ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF
        ),
        ARTIFACT_NORM_IMPACT_REPORT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_NORM_IMPACT_REPORT_REF
        ),
        ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF
        ),
        ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF
        ),
        ARTIFACT_SENSITIVITY_RESULT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_SENSITIVITY_RESULT_REF
        ),
        ARTIFACT_STRESS_TEST_REPORT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_STRESS_TEST_REPORT_REF
        ),
        ARTIFACT_BOUNDS_BUNDLE_REF: _ref_from_dict(artifacts_index, ARTIFACT_BOUNDS_BUNDLE_REF),
        ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF
        ),
        ARTIFACT_TRANSPORTABILITY_RESULT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_TRANSPORTABILITY_RESULT_REF
        ),
    }


def _ref_from_dict(index: dict[str, ArtifactRef], key: str) -> str | None:
    ref = index.get(key)
    return str(ref.artifact_id) if ref is not None else None


def _has_meaningful_outline_content(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _build_document_outline(packet_payload: dict[str, object]) -> list[dict[str, str]]:
    outline: list[dict[str, str]] = []

    def add(
        section_id: str,
        title: str,
        section_type: str,
        *values: object,
    ) -> None:
        if any(_has_meaningful_outline_content(value) for value in values):
            outline.append(
                {
                    "section_id": section_id,
                    "section_type": section_type,
                    "title": title,
                }
            )

    add(
        "policy_answer",
        "Recommendation",
        "policy",
        packet_payload.get("policy_answer"),
        packet_payload.get("verified_findings"),
        packet_payload.get("hypotheses"),
    )
    add(
        "policy_summary",
        "Intervention scope",
        "intervention",
        packet_payload.get("policy_summary"),
        packet_payload.get("intervention_count"),
        packet_payload.get("intervention_legal_basis_map"),
    )
    add(
        "evidence",
        "Evidence and uncertainty",
        "evidence",
        packet_payload.get("simulation_results"),
        packet_payload.get("metric_validation_comparisons"),
        packet_payload.get("uncertainty"),
        packet_payload.get("uncertainty_bounds"),
        packet_payload.get("causal"),
    )
    add(
        "distributional",
        "Distributional effects",
        "evidence",
        packet_payload.get("distributional"),
    )
    add(
        "welfare",
        "Welfare aggregation",
        "evidence",
        packet_payload.get("welfare"),
    )
    add(
        "governance",
        "Governance and legal basis",
        "governance",
        packet_payload.get("governance"),
        packet_payload.get("legal_verification"),
        packet_payload.get("source_coverage"),
    )
    add(
        "replay",
        "Replay and runtime contracts",
        "reproducibility",
        packet_payload.get("replay"),
        packet_payload.get("runtime_contracts"),
    )
    add(
        "analysis_limits",
        "Limits and degraded paths",
        "problem",
        packet_payload.get("analysis_limits"),
        packet_payload.get("degraded_paths"),
        packet_payload.get("notes"),
    )
    return outline


def _dependency_ref(
    kind: DecisionDependencyKind,
    key: str,
    *,
    artifact_id: str | None = None,
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> DecisionDependencyRef:
    return DecisionDependencyRef(
        kind=kind,
        key=key,
        artifact_id=artifact_id,
        label=label,
        metadata=metadata or {},
    )


def _dedupe_dependency_refs(
    values: list[DecisionDependencyRef],
) -> list[DecisionDependencyRef]:
    deduped: list[DecisionDependencyRef] = []
    seen: set[tuple[str, str, str | None]] = set()
    for item in values:
        key = (item.kind.value, item.key, item.artifact_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _load_json_payload_by_ref(
    ctx: ExecutionContext,
    ref_value: str | None,
    *,
    packet_payload: dict[str, object] | None = None,
    operation: str | None = None,
    reason: str | None = None,
    artifact_key: str | None = None,
) -> dict[str, Any] | None:
    from polisyos.core.artifacts import load_core_json_artifact

    if not isinstance(ref_value, str) or not ref_value:
        return None
    try:
        artifact_id = ArtifactID.model_validate(ref_value)
        payload = load_core_json_artifact(ctx.store, artifact_id)
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        if operation is not None and reason is not None:
            _record_decision_packet_section_degraded(
                packet_payload,
                operation=operation,
                reason=reason,
                exc=exc,
                artifact_id=ref_value,
                artifact_key=artifact_key,
            )
        return None
    if isinstance(payload, dict):
        return payload
    if operation is not None and reason is not None:
        _record_decision_packet_section_degraded(
            packet_payload,
            operation=operation,
            reason=reason,
            exc=TypeError("artifact payload must decode to a JSON object"),
            artifact_id=ref_value,
            artifact_key=artifact_key,
        )
    return None


def _build_manifest_inputs(
    packet_payload: dict[str, object],
    *,
    source_state: ExperimentState | None = None,
    source_artifact_refs: tuple[ArtifactRef, ...] = (),
) -> list[InputRef]:
    collected: dict[tuple[str, str], InputRef] = {}
    source_refs_by_id: dict[str, list[ArtifactRef]] = {}
    source_refs_by_role: dict[str, ArtifactRef] = {}
    ambiguous_source_roles: set[str] = set()
    if source_state is not None:
        for ref in _claim_source_artifact_refs(source_state):
            source_refs_by_id.setdefault(str(ref.artifact_id), []).append(ref)
        source_maps = (
            ("input", source_state.inputs),
            ("artifact", source_state.artifacts_index),
            ("artifact", source_state.reports_index),
        )
        for prefix, refs_by_name in source_maps:
            for name, ref in refs_by_name.items():
                role = f"{prefix}.{name}"
                previous = source_refs_by_role.get(role)
                if role in ambiguous_source_roles:
                    continue
                if previous is None:
                    source_refs_by_role[role] = ref
                elif artifact_ref_identity_key(previous) != artifact_ref_identity_key(ref):
                    source_refs_by_role.pop(role, None)
                    ambiguous_source_roles.add(role)
    for ref in source_artifact_refs:
        refs = source_refs_by_id.setdefault(str(ref.artifact_id), [])
        if all(
            artifact_ref_identity_key(existing) != artifact_ref_identity_key(ref)
            for existing in refs
        ):
            refs.append(ref)
    for section_name, prefix in (
        ("inputs", "input"),
        ("artifacts", "artifact"),
        ("runtime_contracts", "runtime_contracts"),
        ("decision_validity_envelope", "decision_validity_envelope"),
        ("decision_validity_baseline", "decision_validity_baseline"),
        ("uncertainty", "uncertainty"),
        ("hte", "hte"),
        ("targeting", "targeting"),
        ("abm_alignment", "abm_alignment"),
        ("abstraction_certificate", "abstraction_certificate"),
        ("backtest", "backtest"),
        ("distributional", "distributional"),
        ("econometrics", "econometrics"),
        ("norm_impact", "norm_impact"),
        ("sensitivity", "sensitivity"),
        ("stress_test", "stress_test"),
        ("claims_ref", "claims"),
        ("voi", "voi"),
        ("continuous_governance", "continuous_governance"),
        ("human_review", "human_review"),
        ("validation_report_ref", "validation_report"),
        ("judge_verdict_ref", "judge_verdict"),
    ):
        section = packet_payload.get(section_name)
        _collect_manifest_refs(
            section,
            prefix,
            collected,
            source_refs_by_id=source_refs_by_id,
            source_refs_by_role=source_refs_by_role,
        )
    return list(collected.values())


def _collect_manifest_refs(
    value: object,
    role_prefix: str,
    collected: dict[tuple[str, str], InputRef],
    *,
    source_refs_by_id: Mapping[str, list[ArtifactRef]] | None = None,
    source_refs_by_role: Mapping[str, ArtifactRef] | None = None,
) -> None:
    if isinstance(value, str):
        try:
            artifact_id = ArtifactID.model_validate(value)
        except (ValidationError, ValueError, TypeError):
            return
        selected_ref = (source_refs_by_role or {}).get(role_prefix)
        if selected_ref is not None and selected_ref.artifact_id == artifact_id:
            input_ref = input_ref_from_artifact_ref(selected_ref, role=role_prefix)
        else:
            candidates = (source_refs_by_id or {}).get(str(artifact_id), [])
            if len(candidates) > 1:
                raise ValueError("decision_packet_manifest_input_profile_ambiguous")
            input_ref = (
                input_ref_from_artifact_ref(candidates[0], role=role_prefix)
                if candidates
                else InputRef(artifact_id=artifact_id, role=role_prefix)
            )
        collected[(artifact_id.hex, role_prefix)] = input_ref
        return

    if isinstance(value, list):
        for idx, nested in enumerate(value):
            _collect_manifest_refs(
                nested,
                f"{role_prefix}[{idx}]",
                collected,
                source_refs_by_id=source_refs_by_id,
                source_refs_by_role=source_refs_by_role,
            )
        return

    if isinstance(value, dict):
        ref_fields = {"artifact_id", "kind", "media_type", "manifest_profile_sha256"}
        if {"artifact_id", "kind", "media_type"} <= value.keys():
            ref_payload = {key: value[key] for key in ref_fields if key in value}
            ref = ArtifactRef.model_validate(ref_payload)
            collected[(ref.artifact_id.hex, role_prefix)] = input_ref_from_artifact_ref(
                ref, role=role_prefix
            )
            return
        for key, nested in value.items():
            _collect_manifest_refs(
                nested,
                f"{role_prefix}.{key}",
                collected,
                source_refs_by_id=source_refs_by_id,
                source_refs_by_role=source_refs_by_role,
            )


__all__ = [
    "_build_artifacts_section",
    "_build_document_outline",
    "_build_inputs_section",
    "_build_manifest_inputs",
    "_claim_source_artifact_refs",
    "_collect_manifest_refs",
    "_dedupe_dependency_refs",
    "_dependency_ref",
    "_has_meaningful_outline_content",
    "_load_json_payload_by_ref",
    "_ref_from_dict",
    "_sensitivity_analysis_bundle_ref_from_packet",
]
