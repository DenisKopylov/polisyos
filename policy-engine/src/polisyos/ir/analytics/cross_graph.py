from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.transportability import TransportMode
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import CrossGraphEvidenceProfileRef

_SCHEMA_NAME = "ir.cross_graph_evidence_profile"
_SCHEMA_VERSION = "2.0"


class ConceptKind(str, Enum):
    METRIC = "metric"
    VARIABLE = "variable"
    PARAMETER = "parameter"
    LEGAL_CONCEPT = "legal_concept"
    LEGAL_CONSTRAINT = "legal_constraint"
    DATASET = "dataset"
    DATASET_VARIABLE = "dataset_variable"
    SCHOLAR_CLAIM = "scholar_claim"
    CONTEXT_DIMENSION = "context_dimension"


class BridgeRelation(str, Enum):
    METRIC_TO_VARIABLE = "metric_to_variable"
    PARAMETER_TO_VARIABLE = "parameter_to_variable"
    LEGAL_TO_METRIC = "legal_to_metric"
    LEGAL_TO_VARIABLE = "legal_to_variable"
    DATASET_VAR_TO_VARIABLE = "dataset_var_to_variable"
    CLAIM_TO_VARIABLE = "claim_to_variable"
    CLAIM_TO_EDGE = "claim_to_edge"
    CONTEXT_DIMENSION_TO_VARIABLE = "context_dimension_to_variable"


class EvidenceNeedType(str, Enum):
    OBJECTIVE_METRIC = "objective_metric"
    KPI_METRIC = "kpi_metric"
    SUCCESS_CRITERION_METRIC = "success_criterion_metric"
    CONSTRAINT_METRIC_OR_SLOT = "constraint_metric_or_slot"
    PARAMETER_NEED = "parameter_need"
    MECHANISM_NEED = "mechanism_need"
    LEGAL_APPLICABILITY_NEED = "legal_applicability_need"
    CAUSAL_EDGE_NEED = "causal_edge_need"


class LegalStatus(str, Enum):
    ALLOWED = "allowed"
    CONSTRAINED = "constrained"
    PROHIBITED = "prohibited"
    UNKNOWN = "unknown"


class ObservabilityStatus(str, Enum):
    DIRECT = "direct"
    PROXY_ONLY = "proxy_only"
    MISSING = "missing"
    UNKNOWN = "unknown"


class EvidenceStatus(str, Enum):
    SUPPORTED = "supported"
    MIXED = "mixed"
    INSUFFICIENT = "insufficient"
    UNSUPPORTED = "unsupported"


class TransportStatus(str, Enum):
    IDENTIFIED = "identified"
    PARTIALLY_IDENTIFIED = "partially_identified"
    BOUNDED_NON_IDENTIFIED = "bounded_non_identified"
    UNSUPPORTED = "unsupported"


class CanonicalConcept(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    concept_id: str
    concept_kind: ConceptKind
    label: str = ""
    join_keys: dict[str, list[str]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConceptBridge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    src_system: str
    src_kind: str
    src_id: str
    dst_concept_id: str
    relation: BridgeRelation
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: list[str] = Field(default_factory=list)


class EvidenceNeed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    need_id: str
    need_type: EvidenceNeedType
    source_path: str = ""
    metric_id: str | None = None
    kpi_id: str | None = None
    criterion_id: str | None = None
    parameter_name: str | None = None
    param_path: str | None = None
    intervention_id: str | None = None
    intervention_kind: str | None = None
    constraint_id: str | None = None
    slot_id: str | None = None
    jurisdiction: str | None = None
    policy_domain: str | None = None
    geography: str | None = None
    time_window: str | None = None
    target_context_id: str | None = None
    cause: str | None = None
    effect: str | None = None
    labels: list[str] = Field(default_factory=list)


class CrossGraphDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    severity: str = "warn"
    need_id: str | None = None
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class EvidenceNeedAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    need: EvidenceNeed
    resolved_concept_ids: list[str] = Field(default_factory=list)
    legal_status: LegalStatus = LegalStatus.UNKNOWN
    observability_status: ObservabilityStatus = ObservabilityStatus.UNKNOWN
    evidence_status: EvidenceStatus = EvidenceStatus.INSUFFICIENT
    transport_status: TransportStatus = TransportStatus.UNSUPPORTED
    transport_mode: TransportMode = TransportMode.NONE
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_expert_review: bool = False
    blocking_reasons: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)
    diagnostics: list[CrossGraphDiagnostic] = Field(default_factory=list)


class CrossGraphEvidenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = "ok"
    total_needs: int = 0
    requires_expert_review_count: int = 0
    blocking_need_ids: list[str] = Field(default_factory=list)
    legal_status_counts: dict[str, int] = Field(default_factory=dict)
    observability_status_counts: dict[str, int] = Field(default_factory=dict)
    evidence_status_counts: dict[str, int] = Field(default_factory=dict)
    transport_status_counts: dict[str, int] = Field(default_factory=dict)


class CrossGraphSourceRefs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    academic_db_path: str | None = None
    academic_index_dir: str | None = None
    datasets_db_path: str | None = None
    legal_db_path: str | None = None


class CrossGraphEvidenceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("2.0", pattern=r"^\d+\.\d+$")
    summary: CrossGraphEvidenceSummary
    needs: list[EvidenceNeedAssessment] = Field(default_factory=list)
    diagnostics: list[CrossGraphDiagnostic] = Field(default_factory=list)
    ontology_snapshot: list[CanonicalConcept] = Field(default_factory=list)
    bridges: list[ConceptBridge] = Field(default_factory=list)
    source_refs: CrossGraphSourceRefs = Field(default_factory=CrossGraphSourceRefs)
    target_context: ContextProfile | None = None
    notes: list[str] = Field(default_factory=list)


def build_evidence_need_id(
    need_type: EvidenceNeedType,
    *,
    source_path: str,
    payload: dict[str, Any],
) -> str:
    normalized = json.dumps(
        {
            "need_type": need_type.value,
            "source_path": source_path,
            "payload": payload,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{need_type.value}:{digest}"


def persist_cross_graph_evidence_profile(
    store: ArtifactStore,
    profile: CrossGraphEvidenceProfile,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _SCHEMA_NAME,
    schema_version: str = _SCHEMA_VERSION,
) -> CrossGraphEvidenceProfileRef:
    ref = put_json_artifact(
        store,
        profile.model_dump(mode="json"),
        kind=_SCHEMA_NAME,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CrossGraphEvidenceProfileRef.model_validate(ref)


def load_cross_graph_evidence_profile(
    store: ArtifactStore,
    ref: CrossGraphEvidenceProfileRef,
) -> CrossGraphEvidenceProfile:
    payload = get_json_artifact(store, ref.artifact_id)
    return CrossGraphEvidenceProfile.model_validate(payload)


__all__ = [
    "BridgeRelation",
    "CanonicalConcept",
    "ConceptBridge",
    "ConceptKind",
    "CrossGraphDiagnostic",
    "CrossGraphEvidenceProfile",
    "CrossGraphEvidenceSummary",
    "CrossGraphSourceRefs",
    "EvidenceNeed",
    "EvidenceNeedAssessment",
    "EvidenceNeedType",
    "EvidenceStatus",
    "LegalStatus",
    "ObservabilityStatus",
    "TransportStatus",
    "build_evidence_need_id",
    "load_cross_graph_evidence_profile",
    "persist_cross_graph_evidence_profile",
]
