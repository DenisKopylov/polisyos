"""Decision-packet serialization and artifact-reference helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError
from pydantic.fields import FieldInfo

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.contracts.decision_validity import (
    DecisionBasisSection,
    DecisionDependencyKind,
    DecisionDependencyRef,
    DecisionValidityEnvelope,
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
    if not isinstance(ref, dict):
        return None
    try:
        selected = SensitivityAnalysisBundleRef.model_validate(ref)
    except ValueError:
        return None
    if selected.manifest_profile_sha256 is None:
        return None
    return selected


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


def _validated_decision_validity_envelope_payload(value: object) -> dict[str, object]:
    """Validate present typed basis sections before generic reference traversal."""
    if not isinstance(value, Mapping):
        raise ValueError("decision_packet_manifest_envelope_invalid")
    payload = dict(value)
    if not payload:
        # The sole producer assigns a typed model dump; a present empty object is malformed.
        raise ValueError("decision_packet_manifest_envelope_invalid")

    for field_name, field_info in DecisionValidityEnvelope.model_fields.items():
        if field_info.annotation is not DecisionBasisSection or field_name not in payload:
            continue
        try:
            DecisionBasisSection.model_validate(payload[field_name])
        except (TypeError, ValueError) as exc:
            raise ValueError("decision_packet_manifest_reference_invalid") from exc

    # The manifest collector needs typed basis references, not defaulted identity fields.
    # Keep the original JSON values so validation cannot synthesize omitted content.
    return payload


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
        if section_name == "decision_validity_envelope" and section_name in packet_payload:
            section = _validated_decision_validity_envelope_payload(section)
        _collect_manifest_refs(
            section,
            prefix,
            collected,
            source_refs_by_id=source_refs_by_id,
            source_refs_by_role=source_refs_by_role,
            allow_bare_reference=section_name == "inputs",
            reference_children=section_name == "inputs",
        )
    return list(collected.values())


def _unique_source_refs(
    artifact_id: ArtifactID,
    source_refs_by_id: Mapping[str, list[ArtifactRef]] | None,
) -> tuple[ArtifactRef, ...]:
    """Return distinct selected source views for one exact artifact id."""
    refs = (source_refs_by_id or {}).get(str(artifact_id), [])
    unique: dict[tuple[str, str, str, str | None], ArtifactRef] = {}
    for ref in refs:
        unique[artifact_ref_identity_key(ref)] = ref
    return tuple(unique.values())


def _input_ref_for_artifact(
    artifact_id: ArtifactID,
    role: str,
    *,
    source_refs_by_id: Mapping[str, list[ArtifactRef]] | None,
    profile_sha256: str | None = None,
    kind: str | None = None,
    media_type: str | None = None,
) -> InputRef:
    """Bind one declared artifact identity to its exact available source view."""
    candidates = _unique_source_refs(artifact_id, source_refs_by_id)
    matching = tuple(
        ref
        for ref in candidates
        if (profile_sha256 is None or ref.manifest_profile_sha256 == profile_sha256)
        and (kind is None or ref.kind == kind)
        and (media_type is None or ref.media_type == media_type)
    )
    if candidates and not matching:
        raise ValueError("decision_packet_manifest_input_profile_mismatch")
    if len(matching) > 1:
        raise ValueError("decision_packet_manifest_input_profile_ambiguous")
    if matching:
        return input_ref_from_artifact_ref(matching[0], role=role)
    return InputRef(
        artifact_id=artifact_id,
        role=role,
        manifest_profile_sha256=profile_sha256,
    )


def _record_manifest_input(
    input_ref: InputRef,
    role: str,
    collected: dict[tuple[str, str], InputRef],
) -> None:
    key = (input_ref.artifact_id.hex, role)
    existing = collected.get(key)
    if existing is not None and existing != input_ref:
        raise ValueError("decision_packet_manifest_input_profile_mismatch")
    collected[key] = input_ref


def _is_ref_field(field_name: str) -> bool:
    """Recognize scalar wire fields whose declared meaning is an artifact reference."""
    return field_name == "artifact_id" or field_name.endswith(
        ("_ref", "_refs", "_reference", "_references")
    )


def _is_ref_collection_field(field_name: str) -> bool:
    """Recognize fields that contain a collection of references."""
    return field_name.endswith(("_refs", "_references"))


def _has_required_reference_fields(
    keys: set[str],
    fields: Mapping[str, FieldInfo],
) -> bool:
    return all(name in keys for name, field in fields.items() if field.is_required())


def _parse_reference_mapping(
    value: Mapping[str, object],
    *,
    declared_reference_context: bool,
) -> InputRef | ArtifactRef | DecisionDependencyRef | None:
    """Parse one complete typed reference variant or refuse malformed records."""
    string_keys = {key for key in value if isinstance(key, str)}
    has_non_string_key = len(string_keys) != len(value)
    has_complete_shape = any(
        _has_required_reference_fields(string_keys, fields)
        for fields in (
            InputRef.model_fields,
            ArtifactRef.model_fields,
            DecisionDependencyRef.model_fields,
        )
    )
    if not declared_reference_context and not has_complete_shape:
        return None
    if has_non_string_key:
        raise ValueError("decision_packet_manifest_reference_invalid")

    payload = dict(value)
    candidates: list[InputRef | ArtifactRef | DecisionDependencyRef] = []
    try:
        candidates.append(InputRef.model_validate(payload))
    except (TypeError, ValueError):
        pass
    try:
        candidates.append(ArtifactRef.model_validate(payload))
    except (TypeError, ValueError):
        pass
    try:
        candidates.append(DecisionDependencyRef.model_validate(payload))
    except (TypeError, ValueError):
        pass

    if len(candidates) != 1:
        raise ValueError("decision_packet_manifest_reference_invalid")
    return candidates[0]


def _collect_dependency_reference(
    dependency: DecisionDependencyRef,
    role_prefix: str,
    collected: dict[tuple[str, str], InputRef],
    *,
    source_refs_by_id: Mapping[str, list[ArtifactRef]] | None,
    source_refs_by_role: Mapping[str, ArtifactRef] | None,
) -> None:
    profile_sha256 = dependency.metadata.get("manifest_profile_sha256")
    if dependency.artifact_id is None:
        if profile_sha256 is not None:
            raise ValueError("decision_packet_manifest_dependency_profile_without_artifact")
    else:
        try:
            artifact_id = ArtifactID.model_validate(dependency.artifact_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("decision_packet_manifest_dependency_ref_invalid") from exc
        if profile_sha256 is not None and not isinstance(profile_sha256, str):
            raise ValueError("decision_packet_manifest_dependency_profile_invalid")
        input_ref = _input_ref_for_artifact(
            artifact_id,
            role_prefix,
            source_refs_by_id=source_refs_by_id,
            profile_sha256=profile_sha256,
        )
        _record_manifest_input(input_ref, role_prefix, collected)

    for key, nested in dependency.metadata.items():
        if key == "manifest_profile_sha256":
            continue
        is_collection = _is_ref_collection_field(key)
        _collect_manifest_refs(
            nested,
            f"{role_prefix}.metadata.{key}",
            collected,
            source_refs_by_id=source_refs_by_id,
            source_refs_by_role=source_refs_by_role,
            allow_bare_reference=_is_ref_field(key),
            reference_context=_is_ref_field(key) and not is_collection,
            reference_children=is_collection,
        )


def _collect_typed_reference(
    reference: InputRef | ArtifactRef | DecisionDependencyRef,
    role_prefix: str,
    collected: dict[tuple[str, str], InputRef],
    *,
    source_refs_by_id: Mapping[str, list[ArtifactRef]] | None,
    source_refs_by_role: Mapping[str, ArtifactRef] | None,
) -> None:
    if isinstance(reference, DecisionDependencyRef):
        _collect_dependency_reference(
            reference,
            role_prefix,
            collected,
            source_refs_by_id=source_refs_by_id,
            source_refs_by_role=source_refs_by_role,
        )
        return

    if isinstance(reference, ArtifactRef):
        input_ref = _input_ref_for_artifact(
            reference.artifact_id,
            role_prefix,
            source_refs_by_id=source_refs_by_id,
            profile_sha256=reference.manifest_profile_sha256,
            kind=reference.kind,
            media_type=reference.media_type,
        )
    else:
        input_ref = _input_ref_for_artifact(
            reference.artifact_id,
            role_prefix,
            source_refs_by_id=source_refs_by_id,
            profile_sha256=reference.manifest_profile_sha256,
        )
    _record_manifest_input(input_ref, role_prefix, collected)


def _collect_manifest_refs(
    value: object,
    role_prefix: str,
    collected: dict[tuple[str, str], InputRef],
    *,
    source_refs_by_id: Mapping[str, list[ArtifactRef]] | None = None,
    source_refs_by_role: Mapping[str, ArtifactRef] | None = None,
    allow_bare_reference: bool = False,
    allow_source_bound_bare_reference: bool = False,
    reference_context: bool = False,
    reference_children: bool = False,
) -> None:
    if isinstance(value, (InputRef, ArtifactRef, DecisionDependencyRef)):
        _collect_typed_reference(
            value,
            role_prefix,
            collected,
            source_refs_by_id=source_refs_by_id,
            source_refs_by_role=source_refs_by_role,
        )
        return

    if isinstance(value, str):
        try:
            artifact_id = ArtifactID.model_validate(value)
        except (ValidationError, ValueError, TypeError):
            return
        source_candidates = _unique_source_refs(artifact_id, source_refs_by_id)
        if not allow_bare_reference and not (
            allow_source_bound_bare_reference and source_candidates
        ):
            return
        selected_ref = (source_refs_by_role or {}).get(role_prefix)
        if selected_ref is not None and selected_ref.artifact_id == artifact_id:
            input_ref = input_ref_from_artifact_ref(selected_ref, role=role_prefix)
        else:
            input_ref = _input_ref_for_artifact(
                artifact_id,
                role_prefix,
                source_refs_by_id=source_refs_by_id,
            )
        _record_manifest_input(input_ref, role_prefix, collected)
        return

    if isinstance(value, (tuple, list)):
        for idx, nested in enumerate(value):
            _collect_manifest_refs(
                nested,
                f"{role_prefix}[{idx}]",
                collected,
                source_refs_by_id=source_refs_by_id,
                source_refs_by_role=source_refs_by_role,
                allow_bare_reference=allow_bare_reference,
                allow_source_bound_bare_reference=allow_source_bound_bare_reference,
                reference_context=reference_context or reference_children,
            )
        return

    if isinstance(value, Mapping):
        reference = _parse_reference_mapping(
            value,
            declared_reference_context=reference_context,
        )
        if reference is not None:
            _collect_typed_reference(
                reference,
                role_prefix,
                collected,
                source_refs_by_id=source_refs_by_id,
                source_refs_by_role=source_refs_by_role,
            )
            return

        for key, nested in value.items():
            key_name = key if isinstance(key, str) else str(key)
            is_collection = _is_ref_collection_field(key_name)
            _collect_manifest_refs(
                nested,
                f"{role_prefix}.{key_name}",
                collected,
                source_refs_by_id=source_refs_by_id,
                source_refs_by_role=source_refs_by_role,
                allow_bare_reference=allow_bare_reference or _is_ref_field(key_name),
                allow_source_bound_bare_reference=(
                    allow_source_bound_bare_reference
                    or key_name == "source"
                    or key_name.endswith("_source")
                ),
                reference_context=(
                    reference_children or (_is_ref_field(key_name) and not is_collection)
                ),
                reference_children=is_collection,
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
