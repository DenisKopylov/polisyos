from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.transportability import TransportMode
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import (
    CompositionCertificateRef,
    CrossGraphEvidenceProfileRef,
    InterfaceMappingRef,
    SCMFragmentRef,
)

_SCHEMA_NAME = "ir.cross_graph_evidence_profile"
_SCHEMA_VERSION = "2.1"
_SCM_FRAGMENT_SCHEMA_NAME = "ir.scm_fragment"
_SCM_FRAGMENT_SCHEMA_VERSION = "1.1"
_INTERFACE_MAPPING_SCHEMA_NAME = "ir.interface_mapping"
_INTERFACE_MAPPING_SCHEMA_VERSION = "1.0"
_COMPOSITION_CERTIFICATE_SCHEMA_NAME = "ir.composition_certificate"
_COMPOSITION_CERTIFICATE_SCHEMA_VERSION = "1.1"


class InterfaceRole(str, Enum):
    INPUT = "input"
    OUTPUT = "output"
    SHARED = "shared"


class InterfaceVariableSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    variable_name: str = Field(min_length=1)
    role: InterfaceRole = InterfaceRole.SHARED
    observed: bool = True
    definition: str = ""
    unit: str | None = None
    measurement_model_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FragmentInterfaceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fragment_id: str = Field(min_length=1)
    semantic_namespace: str = Field(min_length=1)
    variables: list[InterfaceVariableSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_variables(self) -> "FragmentInterfaceSchema":
        names = [variable.variable_name for variable in self.variables]
        if len(set(names)) != len(names):
            raise ValueError("FragmentInterfaceSchema variables must be unique")
        return self


class SCMFragment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.1", pattern=r"^\d+\.\d+$")
    fragment_id: str = Field(min_length=1)
    graph_ref: str = Field(min_length=1)
    semantic_namespace: str = Field(min_length=1)
    interface_variables: list[str] = Field(default_factory=list)
    exposed_inputs: list[str] = Field(default_factory=list)
    exposed_outputs: list[str] = Field(default_factory=list)
    latent_summary: dict[str, str] = Field(default_factory=dict)
    measurement_models: dict[str, str] = Field(default_factory=dict)
    variable_definitions: dict[str, str] = Field(default_factory=dict)
    variable_units: dict[str, str] = Field(default_factory=dict)
    variable_metadata: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_interfaces(self) -> "SCMFragment":
        interface_set = set(self.interface_variables)
        if len(interface_set) != len(self.interface_variables):
            raise ValueError("interface_variables must be unique")
        if any(not value.strip() for value in self.interface_variables):
            raise ValueError("interface_variables must not contain empty names")

        for field_name, values in (
            ("exposed_inputs", self.exposed_inputs),
            ("exposed_outputs", self.exposed_outputs),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must be unique")
            unknown = sorted(set(values) - interface_set)
            if unknown:
                raise ValueError(
                    f"{field_name} must be a subset of interface_variables: {unknown}"
                )

        for field_name, mapping in (
            ("measurement_models", self.measurement_models),
            ("variable_definitions", self.variable_definitions),
            ("variable_units", self.variable_units),
            ("variable_metadata", self.variable_metadata),
        ):
            unknown = sorted(set(mapping) - interface_set)
            if unknown:
                raise ValueError(
                    f"{field_name} keys must be a subset of interface_variables: {unknown}"
                )
        return self

    def to_interface_schema(self) -> FragmentInterfaceSchema:
        input_set = set(self.exposed_inputs)
        output_set = set(self.exposed_outputs)
        latent_set = set(self.latent_summary)
        variables: list[InterfaceVariableSchema] = []
        for variable_name in self.interface_variables:
            if variable_name in input_set and variable_name in output_set:
                role = InterfaceRole.SHARED
            elif variable_name in input_set:
                role = InterfaceRole.INPUT
            elif variable_name in output_set:
                role = InterfaceRole.OUTPUT
            else:
                role = InterfaceRole.SHARED
            variables.append(
                InterfaceVariableSchema(
                    variable_name=variable_name,
                    role=role,
                    observed=variable_name not in latent_set,
                    definition=self.variable_definitions.get(variable_name, ""),
                    unit=self.variable_units.get(variable_name),
                    measurement_model_ref=self.measurement_models.get(variable_name),
                    metadata=dict(self.variable_metadata.get(variable_name, {})),
                )
            )
        return FragmentInterfaceSchema(
            fragment_id=self.fragment_id,
            semantic_namespace=self.semantic_namespace,
            variables=variables,
        )


class InterfaceVariableBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fragment_id: str = Field(min_length=1)
    variable_name: str = Field(min_length=1)
    observed: bool = True
    measurement_model_ref: str | None = None
    definition: str = ""
    unit: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InterfaceMappingEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    interface_id: str = Field(min_length=1)
    canonical_node_id: str = Field(min_length=1)
    bindings: list[InterfaceVariableBinding] = Field(default_factory=list)
    observed: bool = True
    alignment_type: Literal["exact", "scale_linked", "proxy", "latent_bridge", "incompatible"] = "exact"
    reviewer: Literal["automated", "pending_review", "human_verified"] = "automated"
    assumptions_introduced: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_bindings(self) -> "InterfaceMappingEntry":
        if len(self.bindings) < 2:
            raise ValueError("InterfaceMappingEntry must contain at least two bindings")
        keys = [(item.fragment_id, item.variable_name) for item in self.bindings]
        if len(set(keys)) != len(keys):
            raise ValueError("InterfaceMappingEntry bindings must be unique")
        return self


class InterfaceMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    fragment_ids: list[str] = Field(default_factory=list)
    entries: list[InterfaceMappingEntry] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_entries(self) -> "InterfaceMapping":
        if len(set(self.fragment_ids)) != len(self.fragment_ids):
            raise ValueError("fragment_ids must be unique")
        entry_ids = [entry.interface_id for entry in self.entries]
        if len(set(entry_ids)) != len(entry_ids):
            raise ValueError("InterfaceMapping entry interface_id values must be unique")
        node_ids = [entry.canonical_node_id for entry in self.entries]
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("InterfaceMapping canonical_node_id values must be unique")
        return self


class CompositionCertificate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.1", pattern=r"^\d+\.\d+$")
    structure_status: Literal["valid", "invalid"] = "valid"
    review_status: Literal["clear", "pending_review"] = "clear"
    status: Literal["preserved", "deferred", "broken", "unknown"] = "unknown"
    composed_graph_ref: str | None = None
    interface_mapping_ref: str = Field(min_length=1)
    alignment_report_ref: str = Field(min_length=1)
    checked_queries: dict[str, Literal["preserved", "broken", "unknown"]] = Field(default_factory=dict)
    newly_required_assumptions: list[str] = Field(default_factory=list)
    structural_assumptions: list[str] = Field(default_factory=list)
    alignment_assumptions: list[str] = Field(default_factory=list)
    source_fragment_refs: dict[str, str] = Field(default_factory=dict)
    source_fragment_graph_refs: dict[str, str] = Field(default_factory=dict)
    failure_card_bundle_ref: str | None = None
    witness_ref: str | None = None
    blocking_reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _backfill_status_fields(cls, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload

        normalized = dict(payload)
        status = str(normalized.get("status", "unknown")).strip().lower()
        blocking_reasons = normalized.get("blocking_reasons", [])
        blocking_present = bool(blocking_reasons)
        if "structure_status" not in normalized:
            normalized["structure_status"] = (
                "invalid"
                if status == "broken" or (status == "unknown" and blocking_present)
                else "valid"
            )
        if "review_status" not in normalized:
            normalized["review_status"] = "pending_review" if status == "deferred" else "clear"
        return normalized


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


class EvidenceSourceKind(str, Enum):
    ACADEMIC = "academic"
    DATASETS = "datasets"
    LEGAL = "legal"
    BENCHMARK = "benchmark"


class EvidenceSourceState(str, Enum):
    AVAILABLE = "available"
    MISSING_CONFIG = "missing_config"
    MISSING_PATH = "missing_path"
    INIT_FAILED = "init_failed"
    QUERY_FAILED = "query_failed"
    DISABLED = "disabled"


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


class EvidenceSourceStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: EvidenceSourceKind
    configured: bool = False
    status: EvidenceSourceState = EvidenceSourceState.MISSING_CONFIG
    path: str | None = None
    detail: str | None = None
    warnings: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)


class CrossGraphEvidenceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("2.1", pattern=r"^\d+\.\d+$")
    summary: CrossGraphEvidenceSummary
    needs: list[EvidenceNeedAssessment] = Field(default_factory=list)
    diagnostics: list[CrossGraphDiagnostic] = Field(default_factory=list)
    ontology_snapshot: list[CanonicalConcept] = Field(default_factory=list)
    bridges: list[ConceptBridge] = Field(default_factory=list)
    source_refs: CrossGraphSourceRefs = Field(default_factory=CrossGraphSourceRefs)
    source_statuses: dict[str, EvidenceSourceStatus] = Field(default_factory=dict)
    benchmark_summary: dict[str, Any] = Field(default_factory=dict)
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


def persist_scm_fragment(
    store: ArtifactStore,
    fragment: SCMFragment,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _SCM_FRAGMENT_SCHEMA_NAME,
    schema_version: str = _SCM_FRAGMENT_SCHEMA_VERSION,
) -> SCMFragmentRef:
    ref = put_json_artifact(
        store,
        fragment.model_dump(mode="json"),
        kind=_SCM_FRAGMENT_SCHEMA_NAME,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return SCMFragmentRef.model_validate(ref)


def load_scm_fragment(
    store: ArtifactStore,
    ref: SCMFragmentRef,
) -> SCMFragment:
    payload = get_json_artifact(store, ref.artifact_id)
    return SCMFragment.model_validate(payload)


def persist_interface_mapping(
    store: ArtifactStore,
    mapping: InterfaceMapping,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _INTERFACE_MAPPING_SCHEMA_NAME,
    schema_version: str = _INTERFACE_MAPPING_SCHEMA_VERSION,
) -> InterfaceMappingRef:
    ref = put_json_artifact(
        store,
        mapping.model_dump(mode="json"),
        kind=_INTERFACE_MAPPING_SCHEMA_NAME,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return InterfaceMappingRef.model_validate(ref)


def load_interface_mapping(
    store: ArtifactStore,
    ref: InterfaceMappingRef,
) -> InterfaceMapping:
    payload = get_json_artifact(store, ref.artifact_id)
    return InterfaceMapping.model_validate(payload)


def persist_composition_certificate(
    store: ArtifactStore,
    certificate: CompositionCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _COMPOSITION_CERTIFICATE_SCHEMA_NAME,
    schema_version: str = _COMPOSITION_CERTIFICATE_SCHEMA_VERSION,
) -> CompositionCertificateRef:
    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind=_COMPOSITION_CERTIFICATE_SCHEMA_NAME,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CompositionCertificateRef.model_validate(ref)


def load_composition_certificate(
    store: ArtifactStore,
    ref: CompositionCertificateRef,
) -> CompositionCertificate:
    payload = get_json_artifact(store, ref.artifact_id)
    return CompositionCertificate.model_validate(payload)


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
    "CompositionCertificate",
    "ConceptBridge",
    "ConceptKind",
    "CrossGraphDiagnostic",
    "CrossGraphEvidenceProfile",
    "CrossGraphEvidenceSummary",
    "CrossGraphSourceRefs",
    "EvidenceSourceKind",
    "EvidenceSourceState",
    "EvidenceSourceStatus",
    "EvidenceNeed",
    "EvidenceNeedAssessment",
    "EvidenceNeedType",
    "EvidenceStatus",
    "FragmentInterfaceSchema",
    "InterfaceRole",
    "InterfaceMapping",
    "InterfaceMappingEntry",
    "InterfaceVariableBinding",
    "InterfaceVariableSchema",
    "LegalStatus",
    "ObservabilityStatus",
    "SCMFragment",
    "TransportStatus",
    "build_evidence_need_id",
    "load_composition_certificate",
    "load_interface_mapping",
    "load_scm_fragment",
    "load_cross_graph_evidence_profile",
    "persist_composition_certificate",
    "persist_interface_mapping",
    "persist_scm_fragment",
    "persist_cross_graph_evidence_profile",
]
