"""Runtime-owned boundary records for the Policy Design concept spine."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.contracts import bounded_liveness_config_from_mapping
from polisyos.runtime.quality.assurance_case import (
    POLICY_DESIGN_CONCEPT_SPINE_SCHEMA_VERSION,
    PolicyDesignCaseAuthorityError,
    build_policy_design_case_concept_spine,
    policy_design_concept_spine_json_schema,
    validate_policy_design_case_concept_spine,
)

CONCEPT_SPINE_BOUNDARY_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.concept_spine_boundary.v1"
)
CONCEPT_SPINE_RECORD_FAMILY = "concept_and_jurisdiction_spine.v1"
CONCEPT_SPINE_PRODUCER_OWNER = "team-policy-semantics"
CONCEPT_SPINE_READER_OWNER = "team-runtime-quality"
CONCEPT_SPINE_HYBRID_CARRIER_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.hybrid_concept_spine_carrier.v1"
)
CONCEPT_SPINE_BRIDGE_AUTHORITY_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.concept_spine_bridge_authority.v1"
)
CONCEPT_SPINE_HANDSHAKE_RECORD_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.producer_handshake_record.v1"
)
CONCEPT_SPINE_HANDSHAKE_LEDGER_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.producer_handshake_ledger.v1"
)

ConceptNamespaceType = Literal[
    "policy_term",
    "metric",
    "data_column",
    "norm",
    "method_requirement",
    "population",
    "geography",
    "time_role",
    "unit",
    "currency",
    "calendar",
    "legal_authority_type",
    "relation_taxonomy",
]
ConceptRelationType = Literal[
    "identity",
    "equivalence",
    "broader",
    "narrower",
    "scope_shifted",
    "authority_shifted",
    "conflicting",
    "deprecated",
    "unresolved",
    "operationalizes",
    "governs",
    "satisfies_method_obligation",
]
ConceptCloseoutEffect = Literal[
    "direct_closure",
    "needs_bridge",
    "discovery_only",
    "limitation",
    "split_claim",
    "transform",
    "blocker",
    "historical_replay",
    "context_only",
]
ReconciledConceptStatus = Literal[
    "resolved",
    "limited",
    "context_only",
    "unresolved",
    "conflicting",
    "blocked",
]
ProducerHandshakeState = Literal[
    "requested",
    "preflighted",
    "waiting_on_spine",
    "waiting_on_peer",
    "emitted_context_only",
    "emitted_binding",
    "blocked",
    "timed_out",
    "degraded",
    "rerun_required",
    "abandoned",
]
ProducerBindingDisposition = Literal[
    "consumed",
    "emitted",
    "selected",
    "rejected",
    "blocked",
    "context_only",
]
ProducerBindingKind = Literal[
    "concept",
    "requirement",
    "dataset",
    "data_column",
    "norm",
    "method",
    "literature",
    "claim",
    "jurisdiction",
    "time",
    "geography",
    "unit",
    "label",
    "spine",
]
BridgeClass = Literal[
    "transport_carrier",
    "handoff_ledger",
    "binding_assertion",
    "producer_attestation",
    "reader_attestation",
    "diagnostic_projection",
    "closeout_evidence",
]
TimeRole = Literal[
    "legal_effective_time",
    "policy_time",
    "data_time",
    "observation_time",
    "valid_time",
    "transaction_time",
    "ingestion_time",
    "publication_time",
    "detection_time",
    "forecast_time",
    "freshness_time",
    "retention_time",
    "replay_time",
]

_CLOSEOUT_ELIGIBLE_BRIDGE_CLASSES = frozenset(
    {
        "handoff_ledger",
        "binding_assertion",
        "producer_attestation",
        "reader_attestation",
        "closeout_evidence",
    }
)
_SPINE_WAIT_FAMILIES = frozenset(
    {
        "scenario_evidence_contract",
        "concept_spine",
        "jurisdiction_spine",
        "authority_profile",
        "semantic_signature",
    }
)
_PASS_HANDSHAKE_STATES = frozenset(
    {"requested", "preflighted", "emitted_context_only", "emitted_binding"}
)
_POLICY_CONSTRUCT_REF_RE = re.compile(r"^construct:[a-z][a-z0-9_]*$")


class ProducerHandshakeValidationError(ValueError):
    """Raised when a W2.A producer handshake would hide coordination failure."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class ConceptNamespaceRef(BaseModel):
    """Governed namespace reference used by the hybrid concept spine carrier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    namespace_id: str = Field(min_length=1)
    namespace_type: ConceptNamespaceType
    scheme_owner: str = Field(min_length=1)
    scheme_version: str = Field(min_length=1)
    definition_ref: str = Field(min_length=1)
    governed: bool = True

    @field_validator("namespace_id", "scheme_owner", "scheme_version", "definition_ref")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)


class ReconciledConcept(BaseModel):
    """Per-run concept meaning reconciled over governed namespace references."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    concept_id: str = Field(min_length=1)
    concept_type: ConceptNamespaceType
    label: str = Field(min_length=1)
    namespace_refs: tuple[str, ...] = Field(default=())
    source_refs: tuple[str, ...] = Field(default=())
    producer_refs: tuple[str, ...] = Field(default=())
    status: ReconciledConceptStatus = "resolved"
    relation_refs: tuple[str, ...] = Field(default=())
    conflict_refs: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    context_only_label_refs: tuple[str, ...] = Field(default=())
    time_roles: Mapping[str, str] = Field(default_factory=dict)
    geography_refs: tuple[str, ...] = Field(default=())
    population_refs: tuple[str, ...] = Field(default=())
    unit_refs: tuple[str, ...] = Field(default=())
    bearing_policy_construct: str | None = None

    @field_validator("concept_id", "label")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("bearing_policy_construct")
    @classmethod
    def _strip_optional_construct_ref(cls, value: str | None) -> str | None:
        text = _optional_text(value)
        if text is not None and not _POLICY_CONSTRUCT_REF_RE.fullmatch(text):
            raise ValueError(
                "bearing_policy_construct must be a governed construct:<id> ref"
            )
        return text

    @field_validator(
        "namespace_refs",
        "source_refs",
        "producer_refs",
        "relation_refs",
        "conflict_refs",
        "blocker_refs",
        "context_only_label_refs",
        "geography_refs",
        "population_refs",
        "unit_refs",
    )
    @classmethod
    def _strip_ref_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _text_tuple(values)

    @field_validator("time_roles")
    @classmethod
    def _validate_time_roles(cls, values: Mapping[str, str]) -> Mapping[str, str]:
        normalized: dict[str, str] = {}
        allowed = set(TimeRole.__args__)  # type: ignore[attr-defined]
        for key, value in values.items():
            role = _required_text(key)
            if role not in allowed:
                raise ValueError(f"unsupported time role: {role}")
            normalized[role] = _required_text(value)
        return normalized


class ConceptRelation(BaseModel):
    """Relation between reconciled concepts with an explicit closeout effect."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relation_id: str = Field(min_length=1)
    source_concept_ref: str = Field(min_length=1)
    target_concept_ref: str | None = None
    relation_type: ConceptRelationType
    closeout_effect: ConceptCloseoutEffect
    namespace_ref: str = Field(min_length=1)
    provenance_ref: str = Field(min_length=1)
    bridge_ref: str | None = None
    time_roles: Mapping[str, str] = Field(default_factory=dict)
    jurisdiction_refs: tuple[str, ...] = Field(default=())
    geography_refs: tuple[str, ...] = Field(default=())
    population_refs: tuple[str, ...] = Field(default=())
    unit_refs: tuple[str, ...] = Field(default=())

    @field_validator(
        "relation_id",
        "source_concept_ref",
        "namespace_ref",
        "provenance_ref",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("target_concept_ref", "bridge_ref")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("jurisdiction_refs", "geography_refs", "population_refs", "unit_refs")
    @classmethod
    def _strip_ref_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _text_tuple(values)

    @field_validator("time_roles")
    @classmethod
    def _validate_time_roles(cls, values: Mapping[str, str]) -> Mapping[str, str]:
        return ReconciledConcept._validate_time_roles(values)


class ProducerHandshakeBinding(BaseModel):
    """One consumed, emitted, selected, rejected, blocked, or context-only binding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    binding_id: str = Field(min_length=1)
    binding_kind: ProducerBindingKind
    disposition: ProducerBindingDisposition
    concept_ref: str | None = None
    requirement_ref: str | None = None
    artifact_ref: str | None = None
    label: str | None = None
    time_role: TimeRole | None = None
    bridge_ref: str | None = None

    @field_validator("binding_id")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("concept_ref", "requirement_ref", "artifact_ref", "label", "bridge_ref")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def _validate_binding_authority(self) -> ProducerHandshakeBinding:
        if self.disposition == "context_only" and self.artifact_ref:
            raise ValueError("context-only bindings cannot carry artifact refs")
        if self.disposition in {"selected", "emitted"} and not (
            self.artifact_ref or self.concept_ref or self.requirement_ref
        ):
            raise ValueError(
                "selected/emitted bindings require a concept, requirement, or artifact"
            )
        return self


class ProducerWaitCondition(BaseModel):
    """Named finite wait condition for producer coordination liveness."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    peer_producer: str | None = None
    artifact_family: str = Field(min_length=1)
    required_fields: tuple[str, ...] = Field(default=())
    deadline_s: float | None = Field(default=None, gt=0.0)
    deadline_at: str | None = None

    @field_validator("peer_producer", "deadline_at")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("artifact_family")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("required_fields")
    @classmethod
    def _strip_ref_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _text_tuple(values)

    @model_validator(mode="after")
    def _validate_deadline(self) -> ProducerWaitCondition:
        if self.deadline_s is None and self.deadline_at is None:
            raise ValueError("wait condition requires deadline_s or deadline_at")
        return self


def build_hybrid_concept_spine_carrier(
    *,
    run_id: str,
    job_id: str,
    tenant_id: str,
    authority_profile: str,
    governed_namespace_refs: Sequence[Mapping[str, Any] | ConceptNamespaceRef],
    reconciled_concepts: Sequence[Mapping[str, Any] | ReconciledConcept],
    concept_spine_ref: str | None = None,
    relations: Sequence[Mapping[str, Any] | ConceptRelation] = (),
    producer_handshake_refs: Sequence[Any] = (),
    generated_at: str | None = None,
    source_concept_spine: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the W2.A hybrid concept-spine carrier.

    The carrier keeps globally governed namespace refs distinct from the
    run-local reconciliation artifact. Unresolved or conflicting concepts are
    first-class blockers, which prevents producers from silently substituting
    local labels for shared meaning.
    """

    namespaces = [_namespace_model(item) for item in governed_namespace_refs]
    concepts = [_reconciled_concept_model(item) for item in reconciled_concepts]
    relation_models = [_relation_model(item) for item in relations]
    ref = _optional_text(concept_spine_ref) or _stable_record_ref(
        "concept-spine",
        {
            "run_id": run_id,
            "job_id": job_id,
            "tenant_id": tenant_id,
            "authority_profile": authority_profile,
            "namespaces": [item.model_dump(mode="json") for item in namespaces],
            "concepts": [
                item.model_dump(mode="json", exclude_none=True) for item in concepts
            ],
            "relations": [item.model_dump(mode="json") for item in relation_models],
        },
    )
    blockers = _hybrid_concept_blockers(concepts, relation_models)
    status = "blocked" if blockers else "pass"
    authority = build_concept_spine_bridge_authority_record(
        bridge_ref=f"bridge.concept_spine.{_required_text(run_id)}",
        bridge_class="reader_attestation" if status == "pass" else "closeout_evidence",
        authoritative_boundary="concept_spine_closeout_input",
        producer_component="runtime.concept_spine",
        consumer_component="runtime.closeout_reader",
        input_refs=[
            *(
                _as_text_refs(
                    (source_concept_spine or {}).get("canonical_concept_ids"),
                )
                if isinstance(source_concept_spine, Mapping)
                else ()
            ),
            *(item.definition_ref for item in namespaces),
        ],
        output_refs=[ref],
        cas_ref=ref,
        same_input_closed=True,
        reader_compatible=True,
        redaction_integrity_status="pass",
    )
    payload = {
        "schema_version": CONCEPT_SPINE_HYBRID_CARRIER_SCHEMA_VERSION,
        "record_family": CONCEPT_SPINE_RECORD_FAMILY,
        "carrier_ref": ref,
        "concept_spine_ref": ref,
        "cas_ref": ref,
        "run_id": _required_text(run_id),
        "job_id": _required_text(job_id),
        "tenant_id": _required_text(tenant_id),
        "authority_profile": _required_text(authority_profile),
        "authority_boundary": "concept_spine_closeout_input",
        "status": status,
        "producer_owner": CONCEPT_SPINE_PRODUCER_OWNER,
        "reader_owner": CONCEPT_SPINE_READER_OWNER,
        "source_concept_spine_ref": _optional_text(
            (source_concept_spine or {}).get("concept_spine_ref")
            if isinstance(source_concept_spine, Mapping)
            else None
        ),
        "governed_namespace_refs": [item.model_dump(mode="json") for item in namespaces],
        "reconciled_concepts": [
            item.model_dump(mode="json", exclude_none=True) for item in concepts
        ],
        "relations": [item.model_dump(mode="json") for item in relation_models],
        "producer_handshake_refs": list(_as_text_refs(producer_handshake_refs)),
        "bridge_authority": authority,
        "blockers": blockers,
        "summary": {
            "governed_namespace_count": len(namespaces),
            "reconciled_concept_count": len(concepts),
            "relation_count": len(relation_models),
            "producer_handshake_ref_count": len(_as_text_refs(producer_handshake_refs)),
            "blocker_count": len(blockers),
        },
    }
    if generated_at:
        payload["generated_at"] = _required_text(generated_at)
    return validate_hybrid_concept_spine_carrier(payload)


def validate_hybrid_concept_spine_carrier(carrier: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a W2.A hybrid concept-spine carrier."""

    payload = dict(carrier)
    if _text(payload.get("schema_version")) != CONCEPT_SPINE_HYBRID_CARRIER_SCHEMA_VERSION:
        raise PolicyDesignCaseAuthorityError(
            "concept_spine_hybrid_carrier_schema_version_invalid",
            "Hybrid concept spine carrier schema_version is invalid.",
        )
    namespaces = [
        _namespace_model(item)
        for item in _mapping_rows(payload.get("governed_namespace_refs"))
    ]
    if not namespaces:
        raise PolicyDesignCaseAuthorityError(
            "concept_spine_governed_namespace_refs_missing",
            "Hybrid concept spine carrier requires governed namespace refs.",
        )
    concepts = [
        _reconciled_concept_model(item)
        for item in _mapping_rows(payload.get("reconciled_concepts"))
    ]
    if not concepts:
        raise PolicyDesignCaseAuthorityError(
            "concept_spine_reconciled_concepts_missing",
            "Hybrid concept spine carrier requires per-run reconciled concepts.",
        )
    relations = [_relation_model(item) for item in _mapping_rows(payload.get("relations"))]
    namespace_ids = {item.namespace_id for item in namespaces}
    missing_namespaces = sorted(
        {
            ref
            for concept in concepts
            for ref in concept.namespace_refs
            if ref not in namespace_ids
        }
        | {
            relation.namespace_ref
            for relation in relations
            if relation.namespace_ref not in namespace_ids
        }
    )
    if missing_namespaces:
        raise PolicyDesignCaseAuthorityError(
            "concept_spine_namespace_ref_unknown",
            "Hybrid concept spine carrier references unknown governed namespaces: "
            + ", ".join(missing_namespaces),
        )
    expected_blockers = _hybrid_concept_blockers(concepts, relations)
    existing_codes = {
        _text(blocker.get("code"))
        for blocker in _mapping_rows(payload.get("blockers"))
        if _text(blocker.get("code"))
    }
    expected_codes = {_text(blocker.get("code")) for blocker in expected_blockers}
    if expected_codes and not expected_codes <= existing_codes:
        raise PolicyDesignCaseAuthorityError(
            "concept_spine_hybrid_carrier_blocker_missing",
            "Unresolved/conflicting concept spine states require typed blockers.",
        )
    status = _status(payload.get("status"))
    if expected_blockers and status != "blocked":
        raise PolicyDesignCaseAuthorityError(
            "concept_spine_hybrid_carrier_status_mismatch",
            "Hybrid concept spine carrier with blockers must be status=blocked.",
        )
    payload["governed_namespace_refs"] = [item.model_dump(mode="json") for item in namespaces]
    payload["reconciled_concepts"] = [
        item.model_dump(mode="json", exclude_none=True) for item in concepts
    ]
    payload["relations"] = [item.model_dump(mode="json") for item in relations]
    payload["status"] = "blocked" if expected_blockers else "pass"
    payload.setdefault("record_family", CONCEPT_SPINE_RECORD_FAMILY)
    payload.setdefault("authority_boundary", "concept_spine_closeout_input")
    payload.setdefault("producer_owner", CONCEPT_SPINE_PRODUCER_OWNER)
    payload.setdefault("reader_owner", CONCEPT_SPINE_READER_OWNER)
    payload.setdefault("blockers", expected_blockers)
    payload.setdefault(
        "summary",
        {
            "governed_namespace_count": len(namespaces),
            "reconciled_concept_count": len(concepts),
            "relation_count": len(relations),
            "producer_handshake_ref_count": len(
                _as_text_refs(payload.get("producer_handshake_refs"))
            ),
            "blocker_count": len(expected_blockers),
        },
    )
    return payload


def build_concept_spine_bridge_authority_record(
    *,
    bridge_ref: str,
    bridge_class: BridgeClass,
    authoritative_boundary: str,
    producer_component: str,
    consumer_component: str,
    input_refs: Sequence[Any],
    output_refs: Sequence[Any],
    cas_ref: str,
    same_input_closed: bool,
    reader_compatible: bool,
    redaction_integrity_status: str,
) -> dict[str, Any]:
    """Build a boundary-scoped bridge authority record.

    The record can prove continuity at the named boundary. It cannot prove
    producer domain truth, and diagnostic/transport classes are explicitly
    barred from runtime closeout authority.
    """

    bridge_class_text = _required_text(bridge_class)
    eligible = (
        bridge_class_text in _CLOSEOUT_ELIGIBLE_BRIDGE_CLASSES
        and same_input_closed
        and reader_compatible
        and _status(redaction_integrity_status) == "pass"
    )
    may_not_use_for = [
        "producer_domain_truth",
        "public_projection_authority",
        "evidence_strength",
    ]
    if not eligible:
        may_not_use_for.append("runtime_closeout_authority")
    return {
        "schema_version": CONCEPT_SPINE_BRIDGE_AUTHORITY_SCHEMA_VERSION,
        "bridge_ref": _required_text(bridge_ref),
        "bridge_class": bridge_class_text,
        "authority_role": "closeout_input" if eligible else "diagnostic_only",
        "provenance_kind": "runtime_emitted" if eligible else "runtime_projection",
        "authoritative_boundary": _required_text(authoritative_boundary),
        "authoritative_for": ["boundary_continuity"] if eligible else [],
        "may_not_use_for": may_not_use_for,
        "producer_component": _required_text(producer_component),
        "consumer_component": _required_text(consumer_component),
        "input_refs": list(_as_text_refs(input_refs)),
        "output_refs": list(_as_text_refs(output_refs)),
        "cas_ref": _required_text(cas_ref),
        "same_input_closed": bool(same_input_closed),
        "reader_compatible": bool(reader_compatible),
        "redaction_integrity_status": _required_text(redaction_integrity_status),
        "closeout_input": eligible,
    }


def build_producer_handshake_record(
    *,
    producer_component: str,
    run_id: str,
    job_id: str,
    tenant_id: str,
    state: ProducerHandshakeState,
    spine_context: Mapping[str, Any] | None = None,
    concept_spine_ref: str | None = None,
    jurisdiction_spine_ref: str | None = None,
    consumed_concept_refs: Sequence[Any] = (),
    consumed_requirement_refs: Sequence[Any] = (),
    bindings: Sequence[Mapping[str, Any] | ProducerHandshakeBinding] = (),
    wait_conditions: Sequence[Mapping[str, Any] | ProducerWaitCondition] = (),
    liveness_config: Mapping[str, Any] | None = None,
    requested_deadline_s: float | None = None,
    requested_retries: int | None = None,
) -> dict[str, Any]:
    """Build one producer handshake record with finite liveness semantics."""

    context = dict(spine_context or {})
    producer = _required_text(producer_component)
    concept_ref = _optional_text(concept_spine_ref) or _optional_text(
        context.get("concept_spine_ref")
    )
    jurisdiction_ref = _optional_text(jurisdiction_spine_ref) or _optional_text(
        context.get("jurisdiction_spine_ref")
    )
    binding_models = [_handshake_binding_model(item) for item in bindings]
    if state == "waiting_on_peer":
        _prevalidate_peer_wait_conditions(wait_conditions)
    wait_models = _wait_condition_models(wait_conditions)
    liveness = bounded_liveness_config_from_mapping(liveness_config).resolve(
        producer,
        requested_deadline_s=requested_deadline_s,
        requested_retries=requested_retries,
    )
    if not wait_models and state == "waiting_on_spine":
        wait_models = (
            ProducerWaitCondition(
                artifact_family="concept_spine",
                required_fields=("concept_spine_ref", "jurisdiction_spine_ref"),
                deadline_s=liveness.deadline_s,
            ),
        )
    consumed_concepts = tuple(
        dict.fromkeys(
            [
                *_as_text_refs(consumed_concept_refs),
                *_as_text_refs(context.get("canonical_concept_refs")),
                *(binding.concept_ref for binding in binding_models if binding.concept_ref),
            ]
        )
    )
    consumed_requirements = tuple(
        dict.fromkeys(
            [
                *_as_text_refs(consumed_requirement_refs),
                *(binding.requirement_ref for binding in binding_models if binding.requirement_ref),
            ]
        )
    )
    selected_refs = tuple(
        binding.binding_id for binding in binding_models if binding.disposition == "selected"
    )
    emitted_refs = tuple(
        binding.binding_id for binding in binding_models if binding.disposition == "emitted"
    )
    rejected_refs = tuple(
        binding.binding_id for binding in binding_models if binding.disposition == "rejected"
    )
    blocked_refs = tuple(
        binding.binding_id for binding in binding_models if binding.disposition == "blocked"
    )
    context_only_refs = tuple(
        binding.binding_id for binding in binding_models if binding.disposition == "context_only"
    )
    _validate_handshake_liveness(
        state=state,
        concept_spine_ref=concept_ref,
        jurisdiction_spine_ref=jurisdiction_ref,
        consumed_concept_refs=consumed_concepts,
        consumed_requirement_refs=consumed_requirements,
        selected_binding_refs=selected_refs,
        emitted_binding_refs=emitted_refs,
        rejected_binding_refs=rejected_refs,
        blocked_binding_refs=blocked_refs,
        context_only_label_refs=context_only_refs,
        wait_conditions=wait_models,
    )
    handshake_id = _stable_record_ref(
        "producer-handshake",
        {
            "producer_component": producer,
            "run_id": run_id,
            "job_id": job_id,
            "tenant_id": tenant_id,
            "state": state,
            "concept_spine_ref": concept_ref,
            "jurisdiction_spine_ref": jurisdiction_ref,
            "bindings": [binding.model_dump(mode="json") for binding in binding_models],
            "wait_conditions": [wait.model_dump(mode="json") for wait in wait_models],
        },
    )
    bridge = build_concept_spine_bridge_authority_record(
        bridge_ref=f"bridge.{producer}.{handshake_id}",
        bridge_class="producer_attestation" if state == "emitted_binding" else "handoff_ledger",
        authoritative_boundary="producer_spine_handshake",
        producer_component=producer,
        consumer_component="runtime.semantic_binding",
        input_refs=[ref for ref in (concept_ref, jurisdiction_ref, *consumed_requirements) if ref],
        output_refs=[*selected_refs, *emitted_refs, *blocked_refs, *context_only_refs],
        cas_ref=handshake_id,
        same_input_closed=True,
        reader_compatible=True,
        redaction_integrity_status="pass",
    )
    status = "pass" if state in _PASS_HANDSHAKE_STATES else "blocked"
    blockers = [
        _handshake_blocker(
            code=f"producer_handshake_{state}_blocker",
            producer_component=producer,
            state=state,
            refs=blocked_refs,
        )
    ] if status == "blocked" else []
    return {
        "schema_version": CONCEPT_SPINE_HANDSHAKE_RECORD_SCHEMA_VERSION,
        "handshake_id": handshake_id,
        "producer_component": producer,
        "run_id": _required_text(run_id),
        "job_id": _required_text(job_id),
        "tenant_id": _required_text(tenant_id),
        "state": state,
        "status": status,
        "consumed_concept_spine_ref": concept_ref,
        "consumed_jurisdiction_spine_ref": jurisdiction_ref,
        "consumed_concept_refs": list(consumed_concepts),
        "consumed_requirement_refs": list(consumed_requirements),
        "selected_binding_refs": list(selected_refs),
        "emitted_binding_refs": list(emitted_refs),
        "rejected_binding_refs": list(rejected_refs),
        "blocked_binding_refs": list(blocked_refs),
        "context_only_label_refs": list(context_only_refs),
        "bindings": [binding.model_dump(mode="json") for binding in binding_models],
        "wait_conditions": [wait.model_dump(mode="json") for wait in wait_models],
        "liveness": liveness.model_dump(mode="json"),
        "bridge_authority": bridge,
        "blockers": blockers,
    }


def build_producer_handshake_ledger(
    records: Sequence[Mapping[str, Any]],
    *,
    required_producers: Sequence[str] = (),
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build the W2.A producer handshake ledger consumed by later readers."""

    normalized = [dict(record) for record in records]
    findings: list[dict[str, Any]] = []
    present = {_text(record.get("producer_component")) for record in normalized}
    for producer in _as_text_refs(required_producers):
        if producer in present:
            continue
        findings.append(
            _handshake_finding(
                "producer_handshake_required_producer_missing",
                f"Required producer handshake is missing for {producer}.",
                producer_component=producer,
            )
        )
    for record in normalized:
        if _text(record.get("schema_version")) != CONCEPT_SPINE_HANDSHAKE_RECORD_SCHEMA_VERSION:
            findings.append(
                _handshake_finding(
                    "producer_handshake_schema_version_invalid",
                    "Producer handshake record has an invalid schema version.",
                    producer_component=_text(record.get("producer_component")),
                )
            )
        if not isinstance(record.get("bridge_authority"), Mapping):
            findings.append(
                _handshake_finding(
                    "producer_handshake_bridge_authority_missing",
                    "Producer handshake record is missing bridge authority.",
                    producer_component=_text(record.get("producer_component")),
                )
            )
    if findings:
        status = "fail"
    elif any(_status(record.get("status")) == "blocked" for record in normalized):
        status = "blocked"
    else:
        status = "pass"
    ledger_ref = _stable_record_ref(
        "producer-handshake-ledger",
        {
            "records": normalized,
            "required_producers": list(_as_text_refs(required_producers)),
            "run_id": run_id,
        },
    )
    return {
        "schema_version": CONCEPT_SPINE_HANDSHAKE_LEDGER_SCHEMA_VERSION,
        "producer_handshake_ledger_ref": ledger_ref,
        "run_id": _optional_text(run_id),
        "status": status,
        "records": normalized,
        "findings": findings,
        "summary": {
            "record_count": len(normalized),
            "required_producer_count": len(_as_text_refs(required_producers)),
            "finding_count": len(findings),
            "blocked_record_count": sum(
                1 for record in normalized if _status(record.get("status")) == "blocked"
            ),
        },
    }


def build_policy_design_concept_spine_boundary_record(
    spine: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return a producer-side residual-boundary record for concept resolution.

    The record deliberately fails when a producer tries to publish unresolved
    concepts as `status=pass`, even if the downstream validator can infer the
    failure. That keeps the first failing artifact at the concept-spine boundary
    instead of letting it surface as a late PDC scorecard surprise.
    """

    if not isinstance(spine, Mapping):
        return _boundary_record(
            source={},
            status="failed",
            issues=[
                _issue(
                    "policy_design_concept_spine_missing",
                    "Policy Design Case concept spine is missing before PDC compilation.",
                )
            ],
        )

    raw_status = _status(spine.get("status"))
    try:
        normalized = validate_policy_design_case_concept_spine(spine)
    except PolicyDesignCaseAuthorityError as exc:
        return _boundary_record(
            source=spine,
            status="failed",
            issues=[_issue(exc.code, str(exc))],
        )

    blockers = _mapping_list(normalized.get("blockers"))
    normalized_status = _status(normalized.get("status"))
    if raw_status == "pass" and normalized_status == "blocked":
        return _boundary_record(
            source=normalized,
            status="failed",
            blockers=blockers,
            issues=[
                _issue(
                    "policy_design_concept_spine_blocker_missing",
                    "Concept spine blockers cannot be hidden behind producer status=pass.",
                )
            ],
        )
    return _boundary_record(
        source=normalized,
        status="blocked" if normalized_status == "blocked" or blockers else "pass",
        blockers=blockers,
    )


def _boundary_record(
    *,
    source: Mapping[str, Any],
    status: str,
    blockers: list[dict[str, Any]] | None = None,
    issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    blockers = blockers or []
    issues = issues or []
    evidence_ref = _first_ref(source, ("cas_ref", "concept_spine_ref")) or _derived_ref(source)
    runtime_event_ref = (
        _text(source.get("runtime_event_ref"))
        or f"event://policy-design-case/concept-spine-boundary/{evidence_ref}"
    )
    authority_status = "runtime_blocker" if status in {"blocked", "failed"} else "runtime_derived"
    return {
        "schema_version": CONCEPT_SPINE_BOUNDARY_SCHEMA_VERSION,
        "source_schema_version": source.get("schema_version")
        or POLICY_DESIGN_CONCEPT_SPINE_SCHEMA_VERSION,
        "record_id": "policy-design-concept-spine-boundary",
        "record_family": CONCEPT_SPINE_RECORD_FAMILY,
        "status": status,
        "producer_owner": CONCEPT_SPINE_PRODUCER_OWNER,
        "reader_owner": CONCEPT_SPINE_READER_OWNER,
        "scorecard_gate": "policy_design_concept_spine_boundary",
        "readiness_gate": "policy_design_case.residual_spine_boundaries",
        "evidence_ref": evidence_ref,
        "cas_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
        "concept_spine_ref": _text(source.get("concept_spine_ref")),
        "source_status": _text(source.get("status")),
        "blockers": blockers,
        "issues": issues,
        "runtime_authority_envelope": {
            "authority_role": "producer_authority",
            "provenance_kind": authority_status,
            "cas_ref": evidence_ref,
            "runtime_event_ref": runtime_event_ref,
        },
    }


def _namespace_model(item: Mapping[str, Any] | ConceptNamespaceRef) -> ConceptNamespaceRef:
    if isinstance(item, ConceptNamespaceRef):
        return item
    return ConceptNamespaceRef.model_validate(dict(item))


def _reconciled_concept_model(
    item: Mapping[str, Any] | ReconciledConcept,
) -> ReconciledConcept:
    if isinstance(item, ReconciledConcept):
        return item
    return ReconciledConcept.model_validate(dict(item))


def _relation_model(item: Mapping[str, Any] | ConceptRelation) -> ConceptRelation:
    if isinstance(item, ConceptRelation):
        return item
    return ConceptRelation.model_validate(dict(item))


def _handshake_binding_model(
    item: Mapping[str, Any] | ProducerHandshakeBinding,
) -> ProducerHandshakeBinding:
    if isinstance(item, ProducerHandshakeBinding):
        return item
    try:
        return ProducerHandshakeBinding.model_validate(dict(item))
    except ValueError as exc:
        raise ProducerHandshakeValidationError(
            "producer_handshake_binding_invalid",
            str(exc),
        ) from exc


def _wait_condition_models(
    items: Sequence[Mapping[str, Any] | ProducerWaitCondition],
) -> tuple[ProducerWaitCondition, ...]:
    models: list[ProducerWaitCondition] = []
    for item in items:
        try:
            models.append(
                item
                if isinstance(item, ProducerWaitCondition)
                else ProducerWaitCondition.model_validate(dict(item))
            )
        except ValueError as exc:
            raise ProducerHandshakeValidationError(
                "producer_handshake_wait_condition_invalid",
                str(exc),
            ) from exc
    return tuple(models)


def _prevalidate_peer_wait_conditions(
    items: Sequence[Mapping[str, Any] | ProducerWaitCondition],
) -> None:
    if not items:
        raise ProducerHandshakeValidationError(
            "producer_handshake_waiting_on_peer_condition_missing",
            "waiting_on_peer requires a named peer wait condition.",
        )
    for item in items:
        if isinstance(item, ProducerWaitCondition):
            if item.peer_producer and item.artifact_family and item.required_fields:
                continue
            raise ProducerHandshakeValidationError(
                "producer_handshake_waiting_on_peer_condition_missing",
                "waiting_on_peer condition is incomplete.",
            )
        raw = dict(item)
        if (
            _optional_text(raw.get("peer_producer"))
            and _optional_text(raw.get("artifact_family"))
            and _as_text_refs(raw.get("required_fields"))
            and (raw.get("deadline_s") is not None or _optional_text(raw.get("deadline_at")))
        ):
            continue
        raise ProducerHandshakeValidationError(
            "producer_handshake_waiting_on_peer_condition_missing",
            (
                "waiting_on_peer must name peer_producer, artifact_family, "
                "required_fields, and deadline."
            ),
        )


def _validate_handshake_liveness(
    *,
    state: str,
    concept_spine_ref: str | None,
    jurisdiction_spine_ref: str | None,
    consumed_concept_refs: Sequence[str],
    consumed_requirement_refs: Sequence[str],
    selected_binding_refs: Sequence[str],
    emitted_binding_refs: Sequence[str],
    rejected_binding_refs: Sequence[str],
    blocked_binding_refs: Sequence[str],
    context_only_label_refs: Sequence[str],
    wait_conditions: Sequence[ProducerWaitCondition],
) -> None:
    if state == "emitted_binding":
        if not concept_spine_ref or not jurisdiction_spine_ref:
            raise ProducerHandshakeValidationError(
                "producer_handshake_spine_ref_missing",
                "emitted_binding requires consumed concept and jurisdiction spine refs.",
            )
        if not consumed_concept_refs or not consumed_requirement_refs:
            raise ProducerHandshakeValidationError(
                "producer_handshake_consumed_refs_missing",
                "emitted_binding requires consumed concept and requirement refs.",
            )
        if not selected_binding_refs and not emitted_binding_refs and not rejected_binding_refs:
            raise ProducerHandshakeValidationError(
                "producer_handshake_emitted_binding_missing",
                "emitted_binding requires selected, rejected, or emitted binding refs.",
            )
    if state == "emitted_context_only":
        if selected_binding_refs or emitted_binding_refs:
            raise ProducerHandshakeValidationError(
                "producer_handshake_context_only_mints_binding",
                "emitted_context_only cannot carry selected or emitted binding refs.",
            )
        if not context_only_label_refs:
            raise ProducerHandshakeValidationError(
                "producer_handshake_context_only_label_missing",
                "emitted_context_only requires context-only label refs.",
            )
    if state == "blocked" and not blocked_binding_refs:
        raise ProducerHandshakeValidationError(
            "producer_handshake_blocker_ref_missing",
            "blocked handshakes require blocked binding refs.",
        )
    if state == "waiting_on_peer":
        if not wait_conditions:
            raise ProducerHandshakeValidationError(
                "producer_handshake_waiting_on_peer_condition_missing",
                "waiting_on_peer requires a named peer wait condition.",
            )
        for condition in wait_conditions:
            if (
                not condition.peer_producer
                or not condition.artifact_family
                or not condition.required_fields
            ):
                raise ProducerHandshakeValidationError(
                    "producer_handshake_waiting_on_peer_condition_missing",
                    (
                        "waiting_on_peer must name peer_producer, artifact_family, "
                        "required_fields, and deadline."
                    ),
                )
    if state == "waiting_on_spine":
        invalid = [
            condition.artifact_family
            for condition in wait_conditions
            if condition.artifact_family not in _SPINE_WAIT_FAMILIES
        ]
        if invalid:
            raise ProducerHandshakeValidationError(
                "producer_handshake_waiting_on_spine_scope_invalid",
                "waiting_on_spine can only wait on shared run-level spine inputs.",
            )


def _hybrid_concept_blockers(
    concepts: Sequence[ReconciledConcept],
    relations: Sequence[ConceptRelation],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    blocked_concept_ids: set[str] = set()
    for concept in concepts:
        if concept.status not in {"unresolved", "conflicting", "blocked"}:
            continue
        blocked_concept_ids.add(concept.concept_id)
        code = {
            "unresolved": "concept_spine_unresolved_concept_blocker",
            "conflicting": "concept_spine_conflicting_concept_blocker",
            "blocked": "concept_spine_blocked_concept_blocker",
        }[concept.status]
        blockers.append(
            {
                "code": code,
                "severity": "fail",
                "phase": "concept_spine",
                "owner": CONCEPT_SPINE_PRODUCER_OWNER,
                "concept_id": concept.concept_id,
                "concept_status": concept.status,
                "conflict_refs": list(concept.conflict_refs),
                "capability_label": "bridge_missing",
                "message": (
                    "Concept spine cannot close while a shared policy concept is "
                    f"{concept.status}."
                ),
                "next_action": (
                    "Resolve the governed namespace relation, split the claim, or emit "
                    "a producer-owned typed blocker before closeout."
                ),
            }
        )
    for relation in relations:
        if relation.closeout_effect != "blocker":
            continue
        if (
            relation.source_concept_ref in blocked_concept_ids
            or relation.target_concept_ref in blocked_concept_ids
        ):
            continue
        code = f"concept_spine_{relation.relation_type}_relation_blocker"
        if any(blocker.get("code") == code for blocker in blockers):
            continue
        blockers.append(
            {
                "code": code,
                "severity": "fail",
                "phase": "concept_spine",
                "owner": CONCEPT_SPINE_PRODUCER_OWNER,
                "relation_id": relation.relation_id,
                "source_concept_ref": relation.source_concept_ref,
                "target_concept_ref": relation.target_concept_ref,
                "capability_label": "bridge_missing",
                "message": "Concept relation has closeout_effect=blocker.",
                "next_action": (
                    "Resolve, transform, limit, or split the relation before using "
                    "producer evidence against this concept scope."
                ),
            }
        )
    return blockers


def _handshake_blocker(
    *,
    code: str,
    producer_component: str,
    state: str,
    refs: Sequence[str],
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "fail",
        "phase": "producer_handshake",
        "producer_component": producer_component,
        "state": state,
        "refs": list(refs),
        "capability_label": "bridge_missing",
        "message": f"Producer handshake stopped in state={state}.",
        "next_action": (
            "Resolve the finite wait, consume the shared spine, emit binding refs, "
            "or preserve a typed blocker for closeout readers."
        ),
    }


def _handshake_finding(
    code: str,
    message: str,
    *,
    producer_component: str | None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "fail",
        "phase": "producer_handshake",
        "producer_component": producer_component,
        "message": message,
        "capability_label": "bridge_missing",
        "next_action": (
            "Emit a complete producer handshake record with bridge authority before "
            "producer evidence can participate in closeout."
        ),
    }


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _as_text_refs(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        text = _optional_text(value)
        return (text,) if text else ()
    if isinstance(value, Mapping):
        refs: list[str] = []
        for key in (
            "ref",
            "id",
            "artifact_ref",
            "cas_ref",
            "concept_id",
            "concept_ref",
            "requirement_id",
            "binding_id",
            "definition_ref",
        ):
            refs.extend(_as_text_refs(value.get(key)))
        return tuple(dict.fromkeys(refs))
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        refs: list[str] = []
        for item in value:
            refs.extend(_as_text_refs(item))
        return tuple(dict.fromkeys(refs))
    return ()


def _stable_record_ref(prefix: str, payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    return f"{prefix}:sha256:{digest}"


def _required_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("required text is missing")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_tuple(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(text for value in values if (text := _optional_text(value))))


def _issue(code: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "fail",
        "phase": "policy_design_concept_spine",
        "message": message,
        "next_action": (
            "Emit concept-spine resolution evidence or a typed blocker before "
            "Policy Design Case compilation."
        ),
    }


def _mapping_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]


def _first_ref(source: Mapping[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        text = _text(source.get(key))
        if text:
            return text
    authority = source.get("runtime_authority_envelope")
    if isinstance(authority, Mapping):
        return _text(authority.get("cas_ref") or authority.get("evidence_ref"))
    return None


def _derived_ref(source: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(source, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def _status(value: object) -> str:
    return str(value or "").strip().casefold()


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "CONCEPT_SPINE_BOUNDARY_SCHEMA_VERSION",
    "CONCEPT_SPINE_BRIDGE_AUTHORITY_SCHEMA_VERSION",
    "CONCEPT_SPINE_HANDSHAKE_LEDGER_SCHEMA_VERSION",
    "CONCEPT_SPINE_HANDSHAKE_RECORD_SCHEMA_VERSION",
    "CONCEPT_SPINE_HYBRID_CARRIER_SCHEMA_VERSION",
    "CONCEPT_SPINE_PRODUCER_OWNER",
    "CONCEPT_SPINE_READER_OWNER",
    "CONCEPT_SPINE_RECORD_FAMILY",
    "ConceptNamespaceRef",
    "ConceptRelation",
    "ProducerHandshakeBinding",
    "ProducerHandshakeValidationError",
    "ProducerWaitCondition",
    "ReconciledConcept",
    "build_concept_spine_bridge_authority_record",
    "build_hybrid_concept_spine_carrier",
    "build_policy_design_case_concept_spine",
    "build_policy_design_concept_spine_boundary_record",
    "build_producer_handshake_ledger",
    "build_producer_handshake_record",
    "policy_design_concept_spine_json_schema",
    "validate_hybrid_concept_spine_carrier",
    "validate_policy_design_case_concept_spine",
]
