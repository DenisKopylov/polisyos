"""Content-bound epoch validity transitions and pre-N9 owner query contexts.

This module deliberately separates three facts that must not be collapsed:

* an advisory perturbation is not an owner disposition;
* a completed generation denominator is not a caller supplied sequence; and
* a persisted query selector is not positive epoch or deployment authority.

The concrete runtime composition may therefore persist and replay a complete
negative context while the transition signer and positive lifecycle owners
remain unallocated.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence  # noqa: TC003
from dataclasses import dataclass
from typing import Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, canon
from polisyos.core import contracts as core_contracts
from polisyos.core.contracts.runtime import EpochPerturbationClass  # noqa: TC001
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.generation_cycle import CandidateSummary  # noqa: TC001
from polisyos.runtime.quality.semantic_epoch import (
    SemanticEpochHistoryRepository,
    SemanticEpochManifest,
    SemanticEpochService,
)

ArtifactID = artifacts.ArtifactID
ArtifactRef = artifacts.ArtifactRef
ArtifactStore = artifacts.ArtifactStore
ArtifactWriteOptions = artifacts.ArtifactWriteOptions
Digest = core_contracts.chronology.Digest

_MEDIA_TYPE = "application/vnd.polisyos.chronology+json"
_RUNTIME_CONTEXT_CANON = canon.CanonSpec(forbid_floats=False)
c4_canonical_bytes = core_contracts.c4_canonical_bytes
c4_profile = core_contracts.c4_profile
c4_profile_manifest_is_exact = core_contracts.c4_profile_manifest_is_exact
c4_semantic_digest = core_contracts.c4_semantic_digest


class _StrictModel(BaseModel):
    """Strict immutable base for chronology composition artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _canonical_bytes(value: BaseModel | Mapping[str, object]) -> bytes:
    payload = (
        value.model_dump(mode="json", exclude_none=True)
        if isinstance(value, BaseModel)
        else dict(value)
    )
    return canon.to_canonical_bytes(payload, _RUNTIME_CONTEXT_CANON)


def _raw_hash(payload: bytes) -> Digest:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _semantic_hash(domain: str, value: BaseModel | Mapping[str, object]) -> Digest:
    return _raw_hash(domain.encode("utf-8") + b"\0" + _canonical_bytes(value))


def _framed_semantic_hash(domain: str, value: BaseModel | Mapping[str, object]) -> Digest:
    raw_value = core_contracts.chronology._raw_value(value)
    canonical = core_contracts.chronology._canonical_raw_bytes(raw_value)
    return _raw_hash(domain.encode("utf-8") + b"\0" + len(canonical).to_bytes(8, "big") + canonical)


def promotion_candidate_summary_content_hash(summary: CandidateSummary) -> Digest:
    """Return the fixed semantic identity used by every promotion occurrence."""

    return _semantic_hash("polisyos.promotion-candidate-summary.v1", summary)


def promotion_epoch_query(
    *,
    design_problem_binding_ref: ArtifactRef,
    candidate: PromotionCandidateIdentity,
) -> core_contracts.chronology.NativeChronologyQuery:
    """Derive the epoch-family selector shared by producer and exact verifier."""

    requested_context = _semantic_hash(
        "polisyos.promotion-query.semantic-epoch.context.v1",
        {
            "design_problem_binding_ref": design_problem_binding_ref,
            "candidate": candidate,
        },
    )
    return core_contracts.chronology.NativeChronologyQuery(
        domain=core_contracts.chronology.ChronologyProofDomain(
            format=core_contracts.chronology.FULL_PREFIX_FORMAT,
            profile=core_contracts.chronology.FULL_PREFIX_PROFILE,
            proof_domain="semantic-epoch",
            family="epoch",
            scope_ref=_semantic_hash(
                "polisyos.promotion-query.semantic-epoch.scope.v1",
                {"design_problem_binding_ref": design_problem_binding_ref},
            ),
            authority_purpose="n9_promotion",
        ),
        requested_cutoff_ref=candidate.occurrence_content_hash,
        requested_query_context_ref=requested_context,
    )


def _persist_model(
    *,
    store: ArtifactStore,
    value: BaseModel | Mapping[str, object],
    kind: str | None = None,
    profile_record: str | None = None,
) -> tuple[ArtifactRef, Digest, bytes]:
    if (kind is None) == (profile_record is None):
        raise ValueError("exactly_one_chronology_persistence_profile_required")
    if profile_record is not None:
        profile = c4_profile(profile_record)
        raw = c4_canonical_bytes(profile_record, value)
        options = ArtifactWriteOptions(
            kind=profile.kind,
            media_type=profile.media_type,
            schema=artifacts.SchemaInfo(
                name=profile.schema_name,
                version=profile.schema_version,
            ),
            canon=artifacts.CanonInfo.from_spec(profile.canon_spec),
        )
        semantic = c4_semantic_digest(profile_record, value)
    else:
        if kind is None:  # pragma: no cover - guarded by the exclusive-choice check
            raise ValueError("chronology_persistence_kind_missing")
        raw = _canonical_bytes(value)
        options = ArtifactWriteOptions(kind=kind, media_type=_MEDIA_TYPE)
        semantic = _semantic_hash(kind, value)
    ref = store.put_bytes(
        raw,
        options,
    )
    observed = store.get_bytes(ref.artifact_id)
    report = store.verify(ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    if (
        not report.ok
        or observed != raw
        or _raw_hash(observed) != str(ref.artifact_id)
        or (
            profile_record is not None
            and not c4_profile_manifest_is_exact(
                profile_record,
                ref=ref,
                manifest=manifest,
                raw=observed,
            )
        )
        or (
            profile_record is None
            and (
                manifest.artifact_id != ref.artifact_id
                or manifest.kind != options.kind
                or manifest.media_type != options.media_type
                or manifest.artifact_schema != options.schema
                or manifest.canon != options.canon
            )
        )
    ):
        raise ValueError("chronology_artifact_readback_mismatch")
    return ref, semantic, raw


def _read_model(
    *,
    store: ArtifactStore,
    ref: ArtifactRef,
    model: type[_StrictModel],
    kind: str | None = None,
    profile_record: str | None = None,
) -> _StrictModel:
    if (kind is None) == (profile_record is None):
        raise ValueError("exactly_one_chronology_read_profile_required")
    if profile_record is not None:
        profile = c4_profile(profile_record)
        expected_kind = profile.kind
        expected_media_type = profile.media_type
        expected_schema = artifacts.SchemaInfo(
            name=profile.schema_name,
            version=profile.schema_version,
        )
        expected_canon = artifacts.CanonInfo.from_spec(profile.canon_spec)
    else:
        if kind is None:  # pragma: no cover - guarded by the exclusive-choice check
            raise ValueError("chronology_read_kind_missing")
        expected_kind = kind
        expected_media_type = _MEDIA_TYPE
        expected_schema = None
        expected_canon = None
    if ref.kind != expected_kind or ref.media_type != expected_media_type:
        raise ValueError("chronology_artifact_profile_mismatch")
    report = store.verify(ref.artifact_id)
    raw = store.get_bytes(ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    if (
        not report.ok
        or _raw_hash(raw) != str(ref.artifact_id)
        or (
            profile_record is not None
            and not c4_profile_manifest_is_exact(
                profile_record,
                ref=ref,
                manifest=manifest,
                raw=raw,
            )
        )
        or (
            profile_record is None
            and (
                manifest.artifact_id != ref.artifact_id
                or manifest.kind != expected_kind
                or manifest.media_type != expected_media_type
                or manifest.artifact_schema != expected_schema
                or manifest.canon != expected_canon
            )
        )
    ):
        raise ValueError("chronology_artifact_readback_mismatch")
    value = model.model_validate(canon.from_canonical_bytes(raw))
    if profile_record is not None and c4_canonical_bytes(profile_record, value) != raw:
        raise ValueError("chronology_artifact_canonical_profile_mismatch")
    return value


class DerivationRecipeBinding(_StrictModel):
    """Content binding for a recipe; it intentionally has no execution API."""

    recipe_ref: ArtifactRef
    recipe_content_hash: Digest
    recipe_schema_profile_ref: Digest
    input_roles: tuple[str, ...]


class EpochCertificateBinding(_StrictModel):
    """Bind one immutable certificate to one fixed-semantics epoch."""

    certificate_ref: ArtifactRef
    certificate_content_hash: Digest
    epoch_ref: Digest
    input_certificate_refs: tuple[ArtifactRef, ...]
    recipe: DerivationRecipeBinding
    canonical_producer_ref: str = Field(min_length=1)
    authority_purpose: str = Field(min_length=1)
    native_coordinate_refs: tuple[Digest, ...]
    rule_schema_profile_refs: tuple[Digest, ...]
    binding_content_hash: Digest

    @model_validator(mode="after")
    def _bind_content(self) -> Self:
        expected = _semantic_hash(
            "polisyos.epoch.certificate-binding.v1",
            self.model_dump(mode="json", exclude={"binding_content_hash"}),
        )
        if self.binding_content_hash != expected:
            raise ValueError("epoch_certificate_binding_content_mismatch")
        return self


def bind_certificate_to_epoch(
    *,
    certificate_ref: ArtifactRef,
    certificate_content_hash: Digest,
    epoch: SemanticEpochManifest,
    input_certificate_refs: Sequence[ArtifactRef],
    recipe: DerivationRecipeBinding,
    canonical_producer_ref: str,
    authority_purpose: str,
    native_coordinate_refs: Sequence[Digest],
    rule_schema_profile_refs: Sequence[Digest],
) -> EpochCertificateBinding:
    """Build the fixed binding without projecting a recipe executor."""

    payload = {
        "certificate_ref": certificate_ref,
        "certificate_content_hash": certificate_content_hash,
        "epoch_ref": epoch.epoch_ref,
        "input_certificate_refs": tuple(input_certificate_refs),
        "recipe": recipe,
        "canonical_producer_ref": canonical_producer_ref,
        "authority_purpose": authority_purpose,
        "native_coordinate_refs": tuple(native_coordinate_refs),
        "rule_schema_profile_refs": tuple(rule_schema_profile_refs),
    }
    return EpochCertificateBinding(
        **payload,
        binding_content_hash=_semantic_hash("polisyos.epoch.certificate-binding.v1", payload),
    )


class EpochDependencyEdge(_StrictModel):
    """One immutable dependency edge between bound certificate targets."""

    source_ref: ArtifactRef
    target_ref: ArtifactRef
    relation: str = Field(min_length=1)
    authority_purpose: str = Field(min_length=1)


class EpochDependencyGraph(_StrictModel):
    """Complete owner-enumerated dependency graph."""

    edges: tuple[EpochDependencyEdge, ...]
    denominator_ref: Digest

    @model_validator(mode="after")
    def _unique_edges(self) -> Self:
        identities = tuple(
            (
                _artifact_ref_identity(edge.source_ref),
                _artifact_ref_identity(edge.target_ref),
                edge.relation,
                edge.authority_purpose,
            )
            for edge in self.edges
        )
        if len(identities) != len(set(identities)):
            raise ValueError("epoch_dependency_graph_duplicate_edge")
        expected = _semantic_hash("polisyos.epoch.dependency-graph.v1", {"edges": self.edges})
        if self.denominator_ref != expected:
            raise ValueError("epoch_dependency_graph_denominator_mismatch")
        return self


class AdvisoryPerturbationEvent(_StrictModel):
    """Append-only advisory signal; transport order is never authority."""

    event_ref: ArtifactRef
    target_ref: ArtifactRef
    source_class: EpochPerturbationClass
    scope: Literal["instance", "dependency_descendants"]
    event_kind: Literal["annotation_only", "invalidate", "reissue", "supersede", "withdraw"]
    authority_purpose: str = Field(min_length=1)
    observed_epoch_ref: Digest

    @model_validator(mode="after")
    def _source_scope_is_exact(self) -> Self:
        if self.source_class == "appeal" and self.scope != "instance":
            raise ValueError("appeal_perturbation_requires_instance_scope")
        return self


class OwnerAdjudicatedTargetDisposition(_StrictModel):
    """One target owner's independently reconciled response."""

    target_ref: ArtifactRef
    event_ref: ArtifactRef
    disposition: Literal[
        "annotation_only",
        "invalidate",
        "reissue",
        "supersede",
        "withdraw",
        "contested",
        "review_required",
    ]
    owner_evidence_ref: ArtifactRef
    owner_evidence_content_hash: Digest
    authority_purpose: str = Field(min_length=1)
    predicate_class: Literal["independently_reconciled"]


class TargetDispositionRow(_StrictModel):
    """Resolved append-only disposition for exactly one graph target."""

    target_ref: ArtifactRef
    disposition: Literal[
        "unchanged",
        "annotation_only",
        "invalidate",
        "reissue",
        "supersede",
        "withdraw",
        "contested",
        "review_required",
    ]
    advisory_event_refs: tuple[ArtifactRef, ...]
    source_classes: tuple[EpochPerturbationClass, ...]
    owner_evidence_refs: tuple[ArtifactRef, ...]


class TargetDispositionVector(_StrictModel):
    """Complete target vector independently derived from owner rows."""

    rows: tuple[TargetDispositionRow, ...]
    dependency_denominator_ref: Digest
    vector_content_hash: Digest

    @model_validator(mode="after")
    def _bind_rows(self) -> Self:
        identities = tuple(_artifact_ref_identity(row.target_ref) for row in self.rows)
        if identities != tuple(sorted(identities)) or len(identities) != len(set(identities)):
            raise ValueError("target_disposition_vector_denominator_invalid")
        expected = _semantic_hash(
            "polisyos.epoch.target-disposition-vector.v1",
            self.model_dump(mode="json", exclude={"vector_content_hash"}),
        )
        if self.vector_content_hash != expected:
            raise ValueError("target_disposition_vector_content_mismatch")
        return self


def _artifact_ref_identity(ref: ArtifactRef) -> tuple[str, str, str]:
    return str(ref.artifact_id), ref.kind, ref.media_type


def resolve_owner_target_dispositions(
    *,
    advisory_events: Sequence[AdvisoryPerturbationEvent],
    owner_dispositions: Sequence[OwnerAdjudicatedTargetDisposition],
    dependency_graph: EpochDependencyGraph,
) -> TargetDispositionVector:
    """Resolve mixed history by target, never by transport order or caller status."""

    target_refs = {
        _artifact_ref_identity(edge.target_ref): edge.target_ref for edge in dependency_graph.edges
    }
    purposes_by_target: dict[tuple[str, str, str], set[str]] = {key: set() for key in target_refs}
    nodes_by_purpose: dict[str, set[tuple[str, str, str]]] = {}
    adjacency_by_purpose: dict[str, dict[tuple[str, str, str], set[tuple[str, str, str]]]] = {}
    for edge in dependency_graph.edges:
        source_key = _artifact_ref_identity(edge.source_ref)
        target_key = _artifact_ref_identity(edge.target_ref)
        purposes_by_target[target_key].add(edge.authority_purpose)
        nodes_by_purpose.setdefault(edge.authority_purpose, set()).update((source_key, target_key))
        adjacency_by_purpose.setdefault(edge.authority_purpose, {}).setdefault(
            source_key, set()
        ).add(target_key)
    events_by_target: dict[
        tuple[str, str, str], dict[tuple[str, str, str], AdvisoryPerturbationEvent]
    ] = {key: {} for key in target_refs}
    events_by_identity: dict[tuple[str, str, str], AdvisoryPerturbationEvent] = {}
    for event in advisory_events:
        event_key = _artifact_ref_identity(event.event_ref)
        previous_event = events_by_identity.get(event_key)
        if previous_event is not None and previous_event != event:
            raise ValueError("advisory_event_identity_conflict")
        events_by_identity[event_key] = event
        start_key = _artifact_ref_identity(event.target_ref)
        purpose_nodes = nodes_by_purpose.get(event.authority_purpose, set())
        if start_key not in purpose_nodes:
            if any(start_key in nodes for nodes in nodes_by_purpose.values()):
                raise ValueError("advisory_event_authority_purpose_mismatch")
            raise ValueError("advisory_event_target_outside_dependency_denominator")
        reached = {start_key}
        if event.scope == "dependency_descendants":
            pending = [start_key]
            adjacency = adjacency_by_purpose.get(event.authority_purpose, {})
            while pending:
                source_key = pending.pop()
                for descendant_key in adjacency.get(source_key, set()):
                    if descendant_key not in reached:
                        reached.add(descendant_key)
                        pending.append(descendant_key)
        for key in reached & target_refs.keys():
            previous = events_by_target[key].get(event_key)
            if previous is not None and previous != event:
                raise ValueError("advisory_event_identity_conflict")
            events_by_target[key][event_key] = event
    owners_by_target: dict[
        tuple[str, str, str],
        dict[
            tuple[tuple[str, str, str], tuple[str, str, str], str],
            OwnerAdjudicatedTargetDisposition,
        ],
    ] = {key: {} for key in target_refs}
    for disposition in owner_dispositions:
        key = _artifact_ref_identity(disposition.target_ref)
        if key not in owners_by_target:
            raise ValueError("owner_disposition_target_outside_dependency_denominator")
        event_key = _artifact_ref_identity(disposition.event_ref)
        event = events_by_target[key].get(event_key)
        if event is None:
            raise ValueError("owner_disposition_event_not_in_advisory_denominator")
        if disposition.authority_purpose != event.authority_purpose:
            raise ValueError("owner_disposition_authority_purpose_mismatch")
        owner_key = (
            event_key,
            _artifact_ref_identity(disposition.owner_evidence_ref),
            disposition.disposition,
        )
        previous = owners_by_target[key].get(owner_key)
        if previous is not None and previous != disposition:
            raise ValueError("owner_disposition_identity_conflict")
        owners_by_target[key][owner_key] = disposition

    rows: list[TargetDispositionRow] = []
    for key in sorted(target_refs):
        events = tuple(events_by_target[key][item] for item in sorted(events_by_target[key]))
        owners = tuple(owners_by_target[key][item] for item in sorted(owners_by_target[key]))
        choices = {row.disposition for row in owners}
        selected_purposes = {
            *(event.authority_purpose for event in events),
            *(owner.authority_purpose for owner in owners),
        }
        authority_choices = choices - {"annotation_only", "review_required", "contested"}
        if (
            "contested" in choices
            or len(authority_choices) > 1
            or (authority_choices and "review_required" in choices)
            or len(selected_purposes) > 1
        ):
            resolved = "contested"
        elif authority_choices:
            resolved = next(iter(authority_choices))
        elif "review_required" in choices:
            resolved = "review_required"
        elif "annotation_only" in choices:
            resolved = "annotation_only"
        elif events:
            resolved = "review_required"
        else:
            resolved = "unchanged"
        rows.append(
            TargetDispositionRow(
                target_ref=target_refs[key],
                disposition=resolved,
                advisory_event_refs=tuple(event.event_ref for event in events),
                source_classes=tuple(sorted({event.source_class for event in events})),
                owner_evidence_refs=tuple(row.owner_evidence_ref for row in owners),
            )
        )
    payload = {
        "rows": tuple(rows),
        "dependency_denominator_ref": dependency_graph.denominator_ref,
    }
    return TargetDispositionVector(
        **payload,
        vector_content_hash=_semantic_hash("polisyos.epoch.target-disposition-vector.v1", payload),
    )


class EpochValidityTransitionArtifact(_StrictModel):
    """Canonical old-epoch/new-epoch validity transition."""

    previous_epoch_ref: Digest
    current_epoch_ref: Digest
    certificate_bindings: tuple[EpochCertificateBinding, ...]
    dependency_graph: EpochDependencyGraph
    target_vector: TargetDispositionVector
    dependency_denominator_ref: Digest
    adjudication_denominator_ref: Digest
    requested_query_context_ref: Digest
    authority_purpose: str = Field(min_length=1)
    transition_content_hash: Digest

    @model_validator(mode="after")
    def _bind_transition(self) -> Self:
        if self.previous_epoch_ref == self.current_epoch_ref:
            raise ValueError("epoch_validity_transition_requires_distinct_epochs")
        if self.target_vector.dependency_denominator_ref != self.dependency_graph.denominator_ref:
            raise ValueError("epoch_validity_transition_denominator_mismatch")
        expected = _semantic_hash(
            "polisyos.epoch.validity-transition.v1",
            self.model_dump(mode="json", exclude={"transition_content_hash"}),
        )
        if self.transition_content_hash != expected:
            raise ValueError("epoch_validity_transition_content_mismatch")
        return self


def build_epoch_validity_transition(
    *,
    previous_epoch: SemanticEpochManifest,
    current_epoch: SemanticEpochManifest,
    certificates: Sequence[EpochCertificateBinding],
    dependency_graph: EpochDependencyGraph,
    target_vector: TargetDispositionVector,
    dependency_denominator_ref: Digest,
    adjudication_denominator_ref: Digest,
    requested_query_context_ref: Digest,
    authority_purpose: str,
) -> EpochValidityTransitionArtifact:
    """Build a transition over full immutable owner inputs."""

    if any(row.epoch_ref != previous_epoch.epoch_ref for row in certificates):
        raise ValueError("epoch_certificate_not_bound_to_previous_epoch")
    payload = {
        "previous_epoch_ref": previous_epoch.epoch_ref,
        "current_epoch_ref": current_epoch.epoch_ref,
        "certificate_bindings": tuple(certificates),
        "dependency_graph": dependency_graph,
        "target_vector": target_vector,
        "dependency_denominator_ref": dependency_denominator_ref,
        "adjudication_denominator_ref": adjudication_denominator_ref,
        "requested_query_context_ref": requested_query_context_ref,
        "authority_purpose": authority_purpose,
    }
    return EpochValidityTransitionArtifact(
        **payload,
        transition_content_hash=_semantic_hash("polisyos.epoch.validity-transition.v1", payload),
    )


class EpochDependencyDenominatorReceipt(_StrictModel):
    denominator_ref: Digest
    certificate_bindings: tuple[EpochCertificateBinding, ...]
    dependency_graph: EpochDependencyGraph
    target_refs: tuple[ArtifactRef, ...]
    predicate_class: Literal["independently_reconciled"]

    @model_validator(mode="after")
    def _bind_complete_denominator(self) -> Self:
        expected_targets_by_key = {
            _artifact_ref_identity(edge.target_ref): edge.target_ref
            for edge in self.dependency_graph.edges
        }
        expected_targets = tuple(
            expected_targets_by_key[key] for key in sorted(expected_targets_by_key)
        )
        if self.target_refs != expected_targets:
            raise ValueError("epoch_dependency_target_denominator_mismatch")
        certificate_keys = tuple(
            _artifact_ref_identity(row.certificate_ref) for row in self.certificate_bindings
        )
        if certificate_keys != tuple(sorted(certificate_keys)) or len(certificate_keys) != len(
            set(certificate_keys)
        ):
            raise ValueError("epoch_dependency_certificate_denominator_mismatch")
        expected = _semantic_hash(
            "polisyos.epoch.dependency-denominator.v1",
            {
                "certificate_bindings": self.certificate_bindings,
                "dependency_graph": self.dependency_graph,
                "target_refs": self.target_refs,
            },
        )
        if self.denominator_ref != expected:
            raise ValueError("epoch_dependency_denominator_content_mismatch")
        return self


class EpochDependencyDenominatorProvider(Protocol):
    def resolve_complete_epoch_dependencies(
        self, *, authority_purpose: str, requested_query_context_ref: Digest
    ) -> EpochDependencyDenominatorReceipt: ...


class EpochPerturbationAdjudicationReceipt(_StrictModel):
    denominator_ref: Digest
    advisory_events: tuple[AdvisoryPerturbationEvent, ...]
    owner_dispositions: tuple[OwnerAdjudicatedTargetDisposition, ...]
    predicate_class: Literal["independently_reconciled"]

    @model_validator(mode="after")
    def _bind_complete_denominator(self) -> Self:
        event_keys = tuple(
            (
                _artifact_ref_identity(row.event_ref),
                _artifact_ref_identity(row.target_ref),
                row.authority_purpose,
            )
            for row in self.advisory_events
        )
        owner_keys = tuple(
            (
                _artifact_ref_identity(row.target_ref),
                _artifact_ref_identity(row.event_ref),
                _artifact_ref_identity(row.owner_evidence_ref),
                row.disposition,
                row.authority_purpose,
            )
            for row in self.owner_dispositions
        )
        if event_keys != tuple(sorted(event_keys)) or len(event_keys) != len(set(event_keys)):
            raise ValueError("epoch_perturbation_event_denominator_mismatch")
        if owner_keys != tuple(sorted(owner_keys)) or len(owner_keys) != len(set(owner_keys)):
            raise ValueError("epoch_perturbation_owner_denominator_mismatch")
        events_by_ref = {_artifact_ref_identity(row.event_ref): row for row in self.advisory_events}
        if any(
            (event := events_by_ref.get(_artifact_ref_identity(owner.event_ref))) is None
            or event.authority_purpose != owner.authority_purpose
            for owner in self.owner_dispositions
        ):
            raise ValueError("epoch_perturbation_owner_event_denominator_mismatch")
        expected = _semantic_hash(
            "polisyos.epoch.perturbation-adjudication-denominator.v1",
            {
                "advisory_events": self.advisory_events,
                "owner_dispositions": self.owner_dispositions,
            },
        )
        if self.denominator_ref != expected:
            raise ValueError("epoch_perturbation_adjudication_denominator_mismatch")
        return self


class EpochPerturbationAdjudicationProvider(Protocol):
    def resolve_complete_owner_adjudications(
        self, *, authority_purpose: str, requested_query_context_ref: Digest
    ) -> EpochPerturbationAdjudicationReceipt: ...


class PersistedEpochValidityTransition(_StrictModel):
    transition_artifact_ref: ArtifactRef
    transition_content_hash: Digest
    dependency_denominator_ref: Digest
    adjudication_denominator_ref: Digest
    signed_artifact_evidence_ref: ArtifactRef
    signing_profile_ref: ArtifactRef
    producer_identity_ref: ArtifactRef
    signer_provenance_ref: ArtifactRef
    requested_query_context_ref: Digest
    authority_purpose: str = Field(min_length=1)


class EpochTransitionSigningNonReceipt(_StrictModel):
    status: Literal["not_established", "rejected"]
    code: Literal[
        "epoch_transition_signer_not_established",
        "epoch_transition_signing_profile_mismatch",
        "epoch_transition_exact_evidence_unavailable",
    ]
    predicate_class: Literal["not_established", "independently_reconciled"]


class EpochTransitionSigningAuthority(Protocol):
    def sign_transition(
        self,
        *,
        transition_bytes: bytes,
        authority_purpose: str,
        requested_query_context_ref: Digest,
    ) -> (
        core_contracts.chronology.PersistedSignedArtifactEvidence | EpochTransitionSigningNonReceipt
    ): ...


class NoEpochTransitionSigningAuthority:
    """Explicit production absence; no ambient or self-signed fallback exists."""

    def sign_transition(
        self,
        *,
        transition_bytes: bytes,
        authority_purpose: str,
        requested_query_context_ref: Digest,
    ) -> EpochTransitionSigningNonReceipt:
        del transition_bytes, authority_purpose, requested_query_context_ref
        return EpochTransitionSigningNonReceipt(
            status="not_established",
            code="epoch_transition_signer_not_established",
            predicate_class="not_established",
        )


class EpochTransitionHistoryRepository(SemanticEpochHistoryRepository, Protocol):
    """Epoch-native exact-manifest read seam required by transition issuance."""

    def resolve_transition_manifests(
        self,
        *,
        previous_epoch_ref: ArtifactRef,
        current_epoch_receipt_ref: ArtifactRef,
        authority_purpose: str,
    ) -> tuple[SemanticEpochManifest, SemanticEpochManifest]: ...


class EpochValidityTransitionProducer:
    """Authority-grade transition producer; no signer fallback is possible."""

    def __init__(
        self,
        *,
        dependency_inventory: EpochDependencyDenominatorProvider,
        adjudications: EpochPerturbationAdjudicationProvider,
        epoch_history: EpochTransitionHistoryRepository,
        signed_artifacts: core_contracts.chronology.SignedArtifactEvidenceRepository,
        signing_authority: EpochTransitionSigningAuthority,
    ) -> None:
        self._dependency_inventory = dependency_inventory
        self._adjudications = adjudications
        self._epoch_history = epoch_history
        self._signed_artifacts = signed_artifacts
        self._signing_authority = signing_authority

    def produce_and_persist(
        self,
        *,
        previous_epoch_ref: ArtifactRef,
        current_epoch_receipt_ref: ArtifactRef,
        requested_query_context_ref: Digest,
        authority_purpose: str,
    ) -> PersistedEpochValidityTransition | EpochTransitionSigningNonReceipt:
        """Resolve owner bytes before asking the appointed signer."""

        if type(self._signing_authority) is NoEpochTransitionSigningAuthority:
            return self._signing_authority.sign_transition(
                transition_bytes=b"",
                authority_purpose=authority_purpose,
                requested_query_context_ref=requested_query_context_ref,
            )
        previous, current = self._epoch_history.resolve_transition_manifests(
            previous_epoch_ref=previous_epoch_ref,
            current_epoch_receipt_ref=current_epoch_receipt_ref,
            authority_purpose=authority_purpose,
        )
        dependencies = EpochDependencyDenominatorReceipt.model_validate(
            self._dependency_inventory.resolve_complete_epoch_dependencies(
                authority_purpose=authority_purpose,
                requested_query_context_ref=requested_query_context_ref,
            ).model_dump(mode="json")
        )
        adjudications = EpochPerturbationAdjudicationReceipt.model_validate(
            self._adjudications.resolve_complete_owner_adjudications(
                authority_purpose=authority_purpose,
                requested_query_context_ref=requested_query_context_ref,
            ).model_dump(mode="json")
        )
        vector = resolve_owner_target_dispositions(
            advisory_events=adjudications.advisory_events,
            owner_dispositions=adjudications.owner_dispositions,
            dependency_graph=dependencies.dependency_graph,
        )
        transition = build_epoch_validity_transition(
            previous_epoch=previous,
            current_epoch=current,
            certificates=dependencies.certificate_bindings,
            dependency_graph=dependencies.dependency_graph,
            target_vector=vector,
            dependency_denominator_ref=dependencies.denominator_ref,
            adjudication_denominator_ref=adjudications.denominator_ref,
            requested_query_context_ref=requested_query_context_ref,
            authority_purpose=authority_purpose,
        )
        signed = self._signing_authority.sign_transition(
            transition_bytes=_canonical_bytes(transition),
            authority_purpose=authority_purpose,
            requested_query_context_ref=requested_query_context_ref,
        )
        if isinstance(signed, EpochTransitionSigningNonReceipt):
            return signed
        try:
            exact = self._signed_artifacts.read_exact(
                evidence_record_ref=signed.evidence_record_ref
            )
            records = core_contracts.chronology._split_framed_records(signed.record_bytes)
            if len(records) != 1:
                raise ValueError("epoch transition evidence record frame mismatch")
            record = core_contracts.chronology.SignedArtifactEvidenceRecord.model_validate(
                json.loads(records[0])
            )
            if exact.persisted != signed or exact.blob_bytes != _canonical_bytes(transition):
                raise ValueError("epoch transition exact evidence mismatch")
        except (KeyError, OSError, TypeError, ValueError):
            return EpochTransitionSigningNonReceipt(
                status="not_established",
                code="epoch_transition_exact_evidence_unavailable",
                predicate_class="not_established",
            )
        # The exact signed bytes still cannot appoint their own producer identity.
        # Until an owner-held producer-identity carrier exists, positive issuance
        # remains unavailable rather than copying signer provenance into that role.
        del record
        return EpochTransitionSigningNonReceipt(
            status="not_established",
            code="epoch_transition_exact_evidence_unavailable",
            predicate_class="not_established",
        )


# ---------------------------------------------------------------------------
# Shared pre-N9 owner query context


class PromotionCandidateOccurrenceStatement(_StrictModel):
    ordinal: int = Field(ge=0)
    design_problem_binding_ref: ArtifactRef
    design_problem_binding_content_hash: Digest
    candidate_id: str = Field(min_length=1)
    candidate_content_hash: Digest
    candidate_summary: CandidateSummary
    candidate_summary_content_hash: Digest
    cycle_index: int = Field(ge=0)

    @model_validator(mode="after")
    def _summary_is_exact(self) -> Self:
        if (
            self.candidate_id != self.candidate_summary.candidate_id
            or self.candidate_content_hash != self.candidate_summary.content_hash
            or self.cycle_index != self.candidate_summary.cycle_index
            or self.candidate_summary_content_hash
            != promotion_candidate_summary_content_hash(self.candidate_summary)
        ):
            raise ValueError("promotion_candidate_occurrence_summary_mismatch")
        return self


class PromotionCandidateIdentity(_StrictModel):
    ordinal: int = Field(ge=0)
    occurrence_ref: ArtifactRef
    occurrence_content_hash: Digest
    candidate_id: str = Field(min_length=1)
    candidate_content_hash: Digest
    candidate_summary_content_hash: Digest


class GenerationOwnerSnapshotStatement(_StrictModel):
    """Persisted post-loop observation owned by the generation controller."""

    design_problem_binding_ref: ArtifactRef
    design_problem_binding_content_hash: Digest
    declared_candidate_count: int = Field(ge=0)
    ordered_candidate_ids: tuple[str, ...]
    ordered_candidate_content_hashes: tuple[Digest, ...]
    ordered_candidate_summary_content_hashes: tuple[Digest, ...]
    ordered_cycle_indices: tuple[int, ...]
    predicate_class: Literal["owner_observed_completed_batch"]

    @model_validator(mode="after")
    def _complete(self) -> Self:
        counts = {
            self.declared_candidate_count,
            len(self.ordered_candidate_ids),
            len(self.ordered_candidate_content_hashes),
            len(self.ordered_candidate_summary_content_hashes),
            len(self.ordered_cycle_indices),
        }
        if len(counts) != 1 or len(set(self.ordered_candidate_ids)) != len(
            self.ordered_candidate_ids
        ):
            raise ValueError("generation_owner_snapshot_denominator_mismatch")
        return self


class PromotionCandidateDenominatorStatement(_StrictModel):
    owner_snapshot_ref: ArtifactRef
    owner_snapshot_content_hash: Digest
    design_problem_binding_ref: ArtifactRef
    declared_candidate_count: int = Field(ge=0)
    ordered_occurrence_refs: tuple[ArtifactRef, ...]
    ordered_occurrence_content_hashes: tuple[Digest, ...]
    predicate_class: Literal["recomputed"]

    @model_validator(mode="after")
    def _complete(self) -> Self:
        snapshot_profile = c4_profile("generation_owner_snapshot")
        if (
            self.owner_snapshot_ref.kind != snapshot_profile.kind
            or self.owner_snapshot_ref.media_type != snapshot_profile.media_type
            or self.owner_snapshot_ref.artifact_id == self.design_problem_binding_ref.artifact_id
        ):
            raise ValueError("promotion_owner_snapshot_profile_mismatch")
        if self.declared_candidate_count != len(self.ordered_occurrence_refs):
            raise ValueError("promotion_candidate_denominator_count_mismatch")
        if len(self.ordered_occurrence_refs) != len(self.ordered_occurrence_content_hashes):
            raise ValueError("promotion_candidate_denominator_hash_count_mismatch")
        if len({str(ref.artifact_id) for ref in self.ordered_occurrence_refs}) != len(
            self.ordered_occurrence_refs
        ):
            raise ValueError("promotion_candidate_denominator_duplicate_occurrence")
        return self


class PersistedPromotionCandidateDenominator(_StrictModel):
    denominator_ref: ArtifactRef
    denominator_content_hash: Digest
    statement: PromotionCandidateDenominatorStatement


class EpochPromotionQueryEvidence(_StrictModel):
    family: Literal["semantic_epoch"]
    candidate: PromotionCandidateIdentity
    query_artifact_ref: ArtifactRef
    query_artifact_content_hash: Digest
    native_requested_query_context_ref: Digest
    verifier_provenance_ref: ArtifactRef
    qualification_status: Literal["not_established", "qualified"]
    qualification_failure_codes: tuple[str, ...] = ()
    predicate_class: Literal["independently_reconciled"]


class PersistedEpochPromotionQueryStatement(_StrictModel):
    """Exact query/result bytes reloaded by the pre-N9 gate."""

    schema_version: Literal["polisyos.promotion.semantic-epoch-query.v1"]
    design_problem_binding_ref: ArtifactRef
    candidate: PromotionCandidateIdentity
    qualification_result: core_contracts.chronology.NativeChronologyQualificationResult

    @model_validator(mode="after")
    def _query_is_derived_from_owner_fields(self) -> PersistedEpochPromotionQueryStatement:
        expected = promotion_epoch_query(
            design_problem_binding_ref=self.design_problem_binding_ref,
            candidate=self.candidate,
        )
        result_query = getattr(self.qualification_result, "query", None)
        if result_query != expected:
            raise ValueError("epoch_query_evidence_owner_binding_mismatch")
        return self


class DeploymentPromotionQueryEvidence(_StrictModel):
    family: Literal["deployment_scope"]
    candidate: PromotionCandidateIdentity
    query_artifact_ref: ArtifactRef
    query_artifact_content_hash: Digest
    native_requested_query_context_ref: Digest
    verifier_provenance_ref: ArtifactRef
    predicate_class: Literal["independently_reconciled"]


class PromotionCandidateOwnerContext(_StrictModel):
    candidate: PromotionCandidateIdentity
    epoch_query: EpochPromotionQueryEvidence
    deployment_query: DeploymentPromotionQueryEvidence
    member_query_context_ref: Digest


class PromotionCandidateContextMemberStatement(_StrictModel):
    candidate_occurrence_ref: ArtifactRef
    candidate_occurrence_content_hash: Digest
    epoch_query_evidence_ref: ArtifactRef
    epoch_query_evidence_content_hash: Digest
    epoch_native_query_context_ref: Digest
    deployment_query_evidence_ref: ArtifactRef
    deployment_query_evidence_content_hash: Digest
    deployment_native_query_context_ref: Digest
    authority_purpose: str = Field(min_length=1)


class PromotionOwnerQueryContextStatement(_StrictModel):
    design_problem_binding_ref: ArtifactRef
    design_problem_binding_content_hash: Digest
    authority_purpose: str = Field(min_length=1)
    candidate_denominator_ref: ArtifactRef
    candidate_denominator_content_hash: Digest
    ordered_candidate_contexts: tuple[PromotionCandidateOwnerContext, ...]
    requested_query_context_ref: Digest
    owner_resolution_provenance_ref: ArtifactRef
    predicate_class: Literal["independently_reconciled"]


class PersistedPromotionOwnerQueryContext(_StrictModel):
    context_ref: ArtifactRef
    raw_cas_hash: Digest
    semantic_hash: Digest
    statement: PromotionOwnerQueryContextStatement
    verifier_provenance_ref: ArtifactRef


class BoundPromotionCandidateContextStatement(_StrictModel):
    aggregate_context_ref: ArtifactRef
    aggregate_context_content_hash: Digest
    member_context_ref: ArtifactRef
    member_context_content_hash: Digest
    candidate_occurrence_ref: ArtifactRef
    ordinal: int = Field(ge=0)


class PersistedBoundPromotionCandidateContext(_StrictModel):
    bound_member_ref: ArtifactRef
    bound_member_content_hash: Digest
    statement: BoundPromotionCandidateContextStatement


class PersistedPromotionContextBatch(_StrictModel):
    aggregate_context: PersistedPromotionOwnerQueryContext
    ordered_bound_members: tuple[PersistedBoundPromotionCandidateContext, ...]


class PromotionOwnerQueryContextNonReceipt(_StrictModel):
    status: Literal["not_established", "rejected"]
    code: Literal[
        "promotion_query_context_owner_unavailable",
        "epoch_query_unresolved",
        "deployment_query_unresolved",
        "promotion_query_context_binding_mismatch",
        "promotion_candidate_denominator_mismatch",
        "promotion_query_family_substitution",
    ]


@dataclass(frozen=True, slots=True)
class _CompletedGenerationCandidateBatch:
    """Private post-loop value. Only the generation owner receives the seal."""

    design_problem_ref: ArtifactRef
    design_problem_content_hash: Digest
    owner_snapshot_ref: ArtifactRef
    owner_snapshot_content_hash: Digest
    summaries: tuple[CandidateSummary, ...]
    _seal: object


_COMPLETED_BATCH_SEAL = object()


def _seal_completed_generation_candidate_batch(
    *,
    artifacts: ArtifactStore,
    design_problem_ref: ArtifactRef,
    design_problem_content_hash: Digest,
    summaries: Sequence[CandidateSummary],
) -> _CompletedGenerationCandidateBatch:
    """Persist and seal the generation owner's final post-loop observation."""

    frozen = tuple(summaries)
    snapshot = GenerationOwnerSnapshotStatement(
        design_problem_binding_ref=design_problem_ref,
        design_problem_binding_content_hash=design_problem_content_hash,
        declared_candidate_count=len(frozen),
        ordered_candidate_ids=tuple(row.candidate_id for row in frozen),
        ordered_candidate_content_hashes=tuple(row.content_hash for row in frozen),
        ordered_candidate_summary_content_hashes=tuple(
            promotion_candidate_summary_content_hash(row) for row in frozen
        ),
        ordered_cycle_indices=tuple(row.cycle_index for row in frozen),
        predicate_class="owner_observed_completed_batch",
    )
    snapshot_ref, snapshot_hash, _ = _persist_model(
        store=artifacts,
        value=snapshot,
        profile_record="generation_owner_snapshot",
    )
    return _CompletedGenerationCandidateBatch(
        design_problem_ref=design_problem_ref,
        design_problem_content_hash=design_problem_content_hash,
        owner_snapshot_ref=snapshot_ref,
        owner_snapshot_content_hash=snapshot_hash,
        summaries=frozen,
        _seal=_COMPLETED_BATCH_SEAL,
    )


class PromotionCandidateDenominatorOwner(Protocol):
    def freeze_completed_generation(
        self, *, completed_batch: _CompletedGenerationCandidateBatch
    ) -> PersistedPromotionCandidateDenominator | PromotionOwnerQueryContextNonReceipt: ...


class EpochResolutionQueryOwner(Protocol):
    def resolve_for_promotion(
        self,
        *,
        design_problem_binding_ref: ArtifactRef,
        candidate: PromotionCandidateIdentity,
    ) -> EpochPromotionQueryEvidence | PromotionOwnerQueryContextNonReceipt: ...


class DeploymentScopeQueryOwner(Protocol):
    def resolve_for_promotion(
        self,
        *,
        design_problem_binding_ref: ArtifactRef,
        candidate: PromotionCandidateIdentity,
    ) -> DeploymentPromotionQueryEvidence | PromotionOwnerQueryContextNonReceipt: ...


class PromotionOwnerQueryContextRepository(Protocol):
    def resolve_verified(
        self, *, context_ref: ArtifactRef
    ) -> PersistedPromotionOwnerQueryContext | PromotionOwnerQueryContextNonReceipt: ...

    def resolve_bound_member(
        self, *, bound_member_ref: ArtifactRef
    ) -> PersistedBoundPromotionCandidateContext: ...

    def resolve_occurrence(
        self, *, occurrence_ref: ArtifactRef
    ) -> PromotionCandidateOccurrenceStatement: ...


class PromotionOwnerQueryContextVerifier(Protocol):
    """Independently recompute one aggregate from its exact persisted bytes."""

    def verify_exact(
        self, *, context_ref: ArtifactRef, context_bytes: bytes
    ) -> PersistedPromotionOwnerQueryContext | PromotionOwnerQueryContextNonReceipt: ...


def _load_verified_candidate_denominator(
    *, artifacts: ArtifactStore, denominator_ref: ArtifactRef
) -> tuple[PromotionCandidateDenominatorStatement, GenerationOwnerSnapshotStatement]:
    """Reload one admitted denominator and prove its complete snapshot bijection."""

    denominator_value = _read_model(
        store=artifacts,
        ref=denominator_ref,
        model=PromotionCandidateDenominatorStatement,
        profile_record="candidate_denominator",
    )
    if not isinstance(denominator_value, PromotionCandidateDenominatorStatement):
        raise TypeError("promotion_candidate_denominator_model_mismatch")
    denominator = denominator_value
    snapshot_value = _read_model(
        store=artifacts,
        ref=denominator.owner_snapshot_ref,
        model=GenerationOwnerSnapshotStatement,
        profile_record="generation_owner_snapshot",
    )
    if not isinstance(snapshot_value, GenerationOwnerSnapshotStatement):
        raise TypeError("generation_owner_snapshot_model_mismatch")
    snapshot = snapshot_value
    if (
        denominator.owner_snapshot_content_hash
        != c4_semantic_digest("generation_owner_snapshot", snapshot)
        or denominator.design_problem_binding_ref != snapshot.design_problem_binding_ref
        or denominator.declared_candidate_count != snapshot.declared_candidate_count
        or denominator.declared_candidate_count != len(denominator.ordered_occurrence_refs)
    ):
        raise ValueError("promotion_candidate_denominator_mismatch")
    for ordinal, (occurrence_ref, occurrence_hash) in enumerate(
        zip(
            denominator.ordered_occurrence_refs,
            denominator.ordered_occurrence_content_hashes,
            strict=True,
        )
    ):
        occurrence_value = _read_model(
            store=artifacts,
            ref=occurrence_ref,
            model=PromotionCandidateOccurrenceStatement,
            profile_record="candidate_occurrence",
        )
        if not isinstance(occurrence_value, PromotionCandidateOccurrenceStatement):
            raise TypeError("promotion_candidate_occurrence_model_mismatch")
        occurrence = occurrence_value
        if (
            occurrence_hash != c4_semantic_digest("candidate_occurrence", occurrence)
            or occurrence.ordinal != ordinal
            or occurrence.design_problem_binding_ref != snapshot.design_problem_binding_ref
            or occurrence.design_problem_binding_content_hash
            != snapshot.design_problem_binding_content_hash
            or occurrence.candidate_id != snapshot.ordered_candidate_ids[ordinal]
            or occurrence.candidate_content_hash
            != snapshot.ordered_candidate_content_hashes[ordinal]
            or occurrence.candidate_summary_content_hash
            != snapshot.ordered_candidate_summary_content_hashes[ordinal]
            or occurrence.cycle_index != snapshot.ordered_cycle_indices[ordinal]
        ):
            raise ValueError("promotion_candidate_denominator_mismatch")
    return denominator, snapshot


class ArtifactPromotionCandidateDenominatorOwner:
    """Persist one occurrence per final summary and one complete denominator."""

    def __init__(self, *, artifacts: ArtifactStore) -> None:
        self._artifacts = artifacts
        self._admitted_denominator_refs: set[tuple[str, str, str]] = set()

    def admits_denominator(self, *, denominator_ref: ArtifactRef) -> bool:
        """Return whether this owner instance issued the exact sealed ref."""

        return _artifact_ref_identity(denominator_ref) in self._admitted_denominator_refs

    def _load_snapshot(self, ref: ArtifactRef) -> GenerationOwnerSnapshotStatement:
        value = _read_model(
            store=self._artifacts,
            ref=ref,
            model=GenerationOwnerSnapshotStatement,
            profile_record="generation_owner_snapshot",
        )
        if not isinstance(value, GenerationOwnerSnapshotStatement):
            raise TypeError("generation_owner_snapshot_model_mismatch")
        return value

    def _load_denominator(self, ref: ArtifactRef) -> PromotionCandidateDenominatorStatement:
        value = _read_model(
            store=self._artifacts,
            ref=ref,
            model=PromotionCandidateDenominatorStatement,
            profile_record="candidate_denominator",
        )
        if not isinstance(value, PromotionCandidateDenominatorStatement):
            raise TypeError("promotion_candidate_denominator_model_mismatch")
        return value

    def _has_conflicting_admitted_snapshot(
        self,
        *,
        snapshot: GenerationOwnerSnapshotStatement,
    ) -> bool:
        """Consult only complete denominator artifacts, never orphan candidates."""

        denominator_profile = c4_profile("candidate_denominator")
        for artifact_id in self._artifacts.iter_artifact_ids():
            manifest = self._artifacts.get_manifest(artifact_id)
            if (
                manifest.kind != denominator_profile.kind
                or manifest.media_type != denominator_profile.media_type
            ):
                continue
            denominator_ref = ArtifactRef(
                artifact_id=artifact_id,
                kind=denominator_profile.kind,
                media_type=denominator_profile.media_type,
            )
            try:
                _, admitted_snapshot = _load_verified_candidate_denominator(
                    artifacts=self._artifacts,
                    denominator_ref=denominator_ref,
                )
            except (KeyError, OSError, TypeError, ValueError):
                # Malformed bytes cannot enter the conflict scan. A coherent
                # denominator still forces a fail-closed conflict because this
                # store has no persistent generation-owner admission carrier;
                # it is never promoted to positive provenance here.
                continue
            if (
                admitted_snapshot.design_problem_binding_ref == snapshot.design_problem_binding_ref
                and admitted_snapshot != snapshot
            ):
                return True
        return False

    def freeze_completed_generation(
        self, *, completed_batch: _CompletedGenerationCandidateBatch
    ) -> PersistedPromotionCandidateDenominator | PromotionOwnerQueryContextNonReceipt:
        if completed_batch._seal is not _COMPLETED_BATCH_SEAL:
            return PromotionOwnerQueryContextNonReceipt(
                status="rejected", code="promotion_candidate_denominator_mismatch"
            )
        try:
            snapshot = self._load_snapshot(completed_batch.owner_snapshot_ref)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return PromotionOwnerQueryContextNonReceipt(
                status="rejected", code="promotion_candidate_denominator_mismatch"
            )
        summaries = completed_batch.summaries
        if (
            c4_semantic_digest("generation_owner_snapshot", snapshot)
            != completed_batch.owner_snapshot_content_hash
            or snapshot.design_problem_binding_ref != completed_batch.design_problem_ref
            or snapshot.design_problem_binding_content_hash
            != completed_batch.design_problem_content_hash
            or snapshot.declared_candidate_count != len(summaries)
            or snapshot.ordered_candidate_ids != tuple(row.candidate_id for row in summaries)
            or snapshot.ordered_candidate_content_hashes
            != tuple(row.content_hash for row in summaries)
            or snapshot.ordered_candidate_summary_content_hashes
            != tuple(promotion_candidate_summary_content_hash(row) for row in summaries)
            or snapshot.ordered_cycle_indices != tuple(row.cycle_index for row in summaries)
            or self._has_conflicting_admitted_snapshot(snapshot=snapshot)
        ):
            return PromotionOwnerQueryContextNonReceipt(
                status="rejected", code="promotion_candidate_denominator_mismatch"
            )
        occurrences: list[tuple[ArtifactRef, Digest]] = []
        for ordinal, summary in enumerate(summaries):
            statement = PromotionCandidateOccurrenceStatement(
                ordinal=ordinal,
                design_problem_binding_ref=completed_batch.design_problem_ref,
                design_problem_binding_content_hash=(completed_batch.design_problem_content_hash),
                candidate_id=summary.candidate_id,
                candidate_content_hash=summary.content_hash,
                candidate_summary=summary,
                candidate_summary_content_hash=promotion_candidate_summary_content_hash(summary),
                cycle_index=summary.cycle_index,
            )
            ref, semantic, _ = _persist_model(
                store=self._artifacts,
                value=statement,
                profile_record="candidate_occurrence",
            )
            occurrences.append((ref, semantic))
        statement = PromotionCandidateDenominatorStatement(
            owner_snapshot_ref=completed_batch.owner_snapshot_ref,
            owner_snapshot_content_hash=completed_batch.owner_snapshot_content_hash,
            design_problem_binding_ref=completed_batch.design_problem_ref,
            declared_candidate_count=len(occurrences),
            ordered_occurrence_refs=tuple(ref for ref, _ in occurrences),
            ordered_occurrence_content_hashes=tuple(value for _, value in occurrences),
            predicate_class="recomputed",
        )
        ref, semantic, _ = _persist_model(
            store=self._artifacts,
            value=statement,
            profile_record="candidate_denominator",
        )
        result = PersistedPromotionCandidateDenominator(
            denominator_ref=ref,
            denominator_content_hash=semantic,
            statement=statement,
        )
        if self._has_conflicting_admitted_snapshot(snapshot=snapshot):
            return PromotionOwnerQueryContextNonReceipt(
                status="rejected", code="promotion_candidate_denominator_mismatch"
            )
        self._admitted_denominator_refs.add(_artifact_ref_identity(ref))
        return result


class ArtifactPromotionOwnerQueryContextRepository:
    """Independent exact-byte reader for aggregate/member/occurrence artifacts."""

    def __init__(
        self,
        *,
        artifacts: ArtifactStore,
        verifier: PromotionOwnerQueryContextVerifier | None = None,
    ) -> None:
        self._artifacts = artifacts
        self._verifier = verifier

    def resolve_verified(
        self, *, context_ref: ArtifactRef
    ) -> PersistedPromotionOwnerQueryContext | PromotionOwnerQueryContextNonReceipt:
        try:
            context_bytes = self._artifacts.get_bytes(context_ref.artifact_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return PromotionOwnerQueryContextNonReceipt(
                status="rejected", code="promotion_query_context_binding_mismatch"
            )
        verifier = self._verifier or self
        return verifier.verify_exact(context_ref=context_ref, context_bytes=context_bytes)

    def verify_exact(
        self, *, context_ref: ArtifactRef, context_bytes: bytes
    ) -> PersistedPromotionOwnerQueryContext | PromotionOwnerQueryContextNonReceipt:
        try:
            statement = _read_model(
                store=self._artifacts,
                ref=context_ref,
                model=PromotionOwnerQueryContextStatement,
                profile_record="aggregate_context",
            )
            if not isinstance(statement, PromotionOwnerQueryContextStatement):
                raise TypeError("promotion_owner_query_context_model_mismatch")
            if self._artifacts.get_bytes(context_ref.artifact_id) != context_bytes:
                raise ValueError("promotion_owner_query_context_byte_mismatch")
            self._verify_aggregate(statement)
        except (OSError, TypeError, ValueError):
            return PromotionOwnerQueryContextNonReceipt(
                status="rejected", code="promotion_query_context_binding_mismatch"
            )
        return PersistedPromotionOwnerQueryContext(
            context_ref=context_ref,
            raw_cas_hash=_raw_hash(context_bytes),
            semantic_hash=c4_semantic_digest("aggregate_context", statement),
            statement=statement,
            verifier_provenance_ref=statement.owner_resolution_provenance_ref,
        )

    def resolve_bound_member(
        self, *, bound_member_ref: ArtifactRef
    ) -> PersistedBoundPromotionCandidateContext:
        statement = _read_model(
            store=self._artifacts,
            ref=bound_member_ref,
            model=BoundPromotionCandidateContextStatement,
            profile_record="bound_member",
        )
        if not isinstance(statement, BoundPromotionCandidateContextStatement):
            raise TypeError("bound_promotion_candidate_context_model_mismatch")
        aggregate = self.resolve_verified(context_ref=statement.aggregate_context_ref)
        if isinstance(aggregate, PromotionOwnerQueryContextNonReceipt):
            raise ValueError("bound_member_aggregate_mismatch")
        if statement.aggregate_context_content_hash != aggregate.semantic_hash:
            raise ValueError("bound_member_aggregate_mismatch")
        if statement.ordinal >= len(aggregate.statement.ordered_candidate_contexts):
            raise ValueError("bound_member_ordinal_mismatch")
        context = aggregate.statement.ordered_candidate_contexts[statement.ordinal]
        if statement.candidate_occurrence_ref != context.candidate.occurrence_ref:
            raise ValueError("bound_member_occurrence_mismatch")
        member = _read_model(
            store=self._artifacts,
            ref=statement.member_context_ref,
            model=PromotionCandidateContextMemberStatement,
            profile_record="member_context",
        )
        if not isinstance(member, PromotionCandidateContextMemberStatement):
            raise TypeError("promotion_candidate_context_member_model_mismatch")
        expected_member = PromotionCandidateContextMemberStatement(
            candidate_occurrence_ref=context.candidate.occurrence_ref,
            candidate_occurrence_content_hash=context.candidate.occurrence_content_hash,
            epoch_query_evidence_ref=context.epoch_query.query_artifact_ref,
            epoch_query_evidence_content_hash=(context.epoch_query.query_artifact_content_hash),
            epoch_native_query_context_ref=(context.epoch_query.native_requested_query_context_ref),
            deployment_query_evidence_ref=context.deployment_query.query_artifact_ref,
            deployment_query_evidence_content_hash=(
                context.deployment_query.query_artifact_content_hash
            ),
            deployment_native_query_context_ref=(
                context.deployment_query.native_requested_query_context_ref
            ),
            authority_purpose=aggregate.statement.authority_purpose,
        )
        if member != expected_member or statement.member_context_content_hash != c4_semantic_digest(
            "member_context", member
        ):
            raise ValueError("bound_member_context_mismatch")
        return PersistedBoundPromotionCandidateContext(
            bound_member_ref=bound_member_ref,
            bound_member_content_hash=c4_semantic_digest("bound_member", statement),
            statement=statement,
        )

    def resolve_occurrence(
        self, *, occurrence_ref: ArtifactRef
    ) -> PromotionCandidateOccurrenceStatement:
        statement = _read_model(
            store=self._artifacts,
            ref=occurrence_ref,
            model=PromotionCandidateOccurrenceStatement,
            profile_record="candidate_occurrence",
        )
        if not isinstance(statement, PromotionCandidateOccurrenceStatement):
            raise TypeError("promotion_candidate_occurrence_model_mismatch")
        return statement

    def resolve_denominator(
        self, *, denominator_ref: ArtifactRef
    ) -> PromotionCandidateDenominatorStatement:
        statement = _read_model(
            store=self._artifacts,
            ref=denominator_ref,
            model=PromotionCandidateDenominatorStatement,
            profile_record="candidate_denominator",
        )
        if not isinstance(statement, PromotionCandidateDenominatorStatement):
            raise TypeError("promotion_candidate_denominator_model_mismatch")
        return statement

    def _verify_aggregate(self, statement: PromotionOwnerQueryContextStatement) -> None:
        denominator, owner_snapshot = _load_verified_candidate_denominator(
            artifacts=self._artifacts,
            denominator_ref=statement.candidate_denominator_ref,
        )
        denominator_hash = c4_semantic_digest("candidate_denominator", denominator)
        if (
            denominator_hash != statement.candidate_denominator_content_hash
            or denominator.design_problem_binding_ref != statement.design_problem_binding_ref
            or denominator.owner_snapshot_content_hash
            != c4_semantic_digest("generation_owner_snapshot", owner_snapshot)
            or owner_snapshot.design_problem_binding_ref != statement.design_problem_binding_ref
            or owner_snapshot.design_problem_binding_content_hash
            != statement.design_problem_binding_content_hash
            or denominator.declared_candidate_count != len(statement.ordered_candidate_contexts)
            or owner_snapshot.declared_candidate_count != denominator.declared_candidate_count
        ):
            raise ValueError("promotion_candidate_denominator_mismatch")
        self._verify_design_problem_binding(statement)
        self._verify_provenance(statement.owner_resolution_provenance_ref)

        if tuple(
            context.candidate.ordinal for context in statement.ordered_candidate_contexts
        ) != tuple(range(denominator.declared_candidate_count)):
            raise ValueError("promotion_candidate_denominator_mismatch")

        for ordinal, context in enumerate(statement.ordered_candidate_contexts):
            occurrence_ref = denominator.ordered_occurrence_refs[ordinal]
            occurrence_hash = denominator.ordered_occurrence_content_hashes[ordinal]
            if (
                context.candidate.occurrence_ref != occurrence_ref
                or context.candidate.occurrence_content_hash != occurrence_hash
            ):
                raise ValueError("promotion_candidate_denominator_mismatch")
            occurrence = self.resolve_occurrence(occurrence_ref=occurrence_ref)
            if (
                c4_semantic_digest("candidate_occurrence", occurrence) != occurrence_hash
                or occurrence.ordinal != ordinal
                or occurrence.design_problem_binding_ref != statement.design_problem_binding_ref
                or occurrence.design_problem_binding_content_hash
                != statement.design_problem_binding_content_hash
                or context.candidate.candidate_id != occurrence.candidate_id
                or context.candidate.candidate_content_hash != occurrence.candidate_content_hash
                or context.candidate.candidate_summary_content_hash
                != occurrence.candidate_summary_content_hash
                or owner_snapshot.ordered_candidate_ids[ordinal] != occurrence.candidate_id
                or owner_snapshot.ordered_candidate_content_hashes[ordinal]
                != occurrence.candidate_content_hash
                or owner_snapshot.ordered_candidate_summary_content_hashes[ordinal]
                != occurrence.candidate_summary_content_hash
                or owner_snapshot.ordered_cycle_indices[ordinal] != occurrence.cycle_index
            ):
                raise ValueError("promotion_candidate_occurrence_mismatch")
            self._verify_query_evidence(
                design_problem_binding_ref=statement.design_problem_binding_ref,
                candidate=context.candidate,
                evidence=context.epoch_query,
                authority_purpose=statement.authority_purpose,
                expected_verifier_provenance_ref=(statement.owner_resolution_provenance_ref),
            )
            self._verify_query_evidence(
                design_problem_binding_ref=statement.design_problem_binding_ref,
                candidate=context.candidate,
                evidence=context.deployment_query,
                authority_purpose=statement.authority_purpose,
                expected_verifier_provenance_ref=(statement.owner_resolution_provenance_ref),
            )
            expected_member_ref = _semantic_hash(
                "polisyos.promotion-member-query-context.v1",
                {
                    "design_problem_binding_ref": statement.design_problem_binding_ref,
                    "authority_purpose": statement.authority_purpose,
                    "candidate": context.candidate,
                    "epoch_query_ref": context.epoch_query.query_artifact_ref,
                    "epoch_query_content_hash": (context.epoch_query.query_artifact_content_hash),
                    "epoch_native_query_context_ref": (
                        context.epoch_query.native_requested_query_context_ref
                    ),
                    "deployment_query_ref": context.deployment_query.query_artifact_ref,
                    "deployment_query_content_hash": (
                        context.deployment_query.query_artifact_content_hash
                    ),
                    "deployment_native_query_context_ref": (
                        context.deployment_query.native_requested_query_context_ref
                    ),
                },
            )
            if context.member_query_context_ref != expected_member_ref:
                raise ValueError("promotion_query_context_binding_mismatch")

        expected_requested = _framed_semantic_hash(
            "polisyos.promotion-owner-query-context.v2",
            {
                "design_problem_binding_ref": statement.design_problem_binding_ref,
                "design_problem_binding_content_hash": (
                    statement.design_problem_binding_content_hash
                ),
                "authority_purpose": statement.authority_purpose,
                "candidate_denominator_ref": statement.candidate_denominator_ref,
                "candidate_denominator_content_hash": (
                    statement.candidate_denominator_content_hash
                ),
                "ordered_candidate_contexts": tuple(
                    {
                        "candidate": row.candidate,
                        "member_query_context_ref": row.member_query_context_ref,
                    }
                    for row in statement.ordered_candidate_contexts
                ),
            },
        )
        if statement.requested_query_context_ref != expected_requested:
            raise ValueError("promotion_query_context_binding_mismatch")

    def _verify_design_problem_binding(
        self, statement: PromotionOwnerQueryContextStatement
    ) -> None:
        ref = statement.design_problem_binding_ref
        if ref.kind != "runtime.design_problem" or ref.media_type != "application/json":
            raise ValueError("promotion_design_problem_profile_mismatch")
        raw = self._artifacts.get_bytes(ref.artifact_id)
        manifest = self._artifacts.get_manifest(ref.artifact_id)
        if (
            not self._artifacts.verify(ref.artifact_id).ok
            or _raw_hash(raw) != str(ref.artifact_id)
            or manifest.kind != ref.kind
            or manifest.media_type != ref.media_type
        ):
            raise ValueError("promotion_design_problem_readback_mismatch")
        problem = DesignProblem.model_validate(canon.from_canonical_bytes(raw))
        if (
            _semantic_hash("runtime.design_problem", problem)
            != statement.design_problem_binding_content_hash
        ):
            raise ValueError("promotion_design_problem_content_mismatch")

    def _verify_provenance(self, ref: ArtifactRef) -> None:
        raw = self._artifacts.get_bytes(ref.artifact_id)
        manifest = self._artifacts.get_manifest(ref.artifact_id)
        if (
            not self._artifacts.verify(ref.artifact_id).ok
            or _raw_hash(raw) != str(ref.artifact_id)
            or manifest.artifact_id != ref.artifact_id
            or manifest.kind != ref.kind
            or manifest.media_type != ref.media_type
        ):
            raise ValueError("promotion_query_verifier_provenance_mismatch")

    def _verify_query_evidence(
        self,
        *,
        design_problem_binding_ref: ArtifactRef,
        candidate: PromotionCandidateIdentity,
        evidence: EpochPromotionQueryEvidence | DeploymentPromotionQueryEvidence,
        authority_purpose: str,
        expected_verifier_provenance_ref: ArtifactRef,
    ) -> None:
        if isinstance(evidence, EpochPromotionQueryEvidence):
            profile_record = "epoch_query_evidence"
            context_domain = "polisyos.promotion-query.semantic-epoch.context.v1"
            expected_payload: dict[str, object] | None = None
            expected_native_query_context_ref: Digest | None = None
        else:
            profile_record = "deployment_query_evidence"
            context_domain = "polisyos.promotion-query.deployment-scope.context.v1"
            expected_payload = {
                "schema_version": c4_profile(profile_record).schema_name,
                "design_problem_binding_ref": design_problem_binding_ref.model_dump(mode="json"),
                "candidate": candidate.model_dump(mode="json"),
                "authority_purpose": authority_purpose,
            }
            expected_native_query_context_ref = _semantic_hash(
                context_domain,
                expected_payload,
            )
        profile = c4_profile(profile_record)
        ref = evidence.query_artifact_ref
        if ref.kind != profile.kind or ref.media_type != profile.media_type:
            raise ValueError("promotion_query_family_substitution")
        raw = self._artifacts.get_bytes(ref.artifact_id)
        manifest = self._artifacts.get_manifest(ref.artifact_id)
        observed_payload = canon.from_canonical_bytes(raw)
        if not isinstance(observed_payload, dict):
            raise ValueError("promotion_query_context_binding_mismatch")
        if isinstance(evidence, EpochPromotionQueryEvidence):
            qualification_model = core_contracts.chronology.NativeChronologyPolicyResolutionFailed
            qualification = qualification_model.model_validate(
                observed_payload.get("qualification_result")
            )
            expected_query = promotion_epoch_query(
                design_problem_binding_ref=design_problem_binding_ref,
                candidate=candidate,
            )
            if (
                qualification.query != expected_query
                or qualification.query.domain.authority_purpose != authority_purpose
                or not isinstance(
                    qualification.failure,
                    core_contracts.chronology.PolicyAdmissionMissingFailure,
                )
                or evidence.qualification_status != qualification.failure.status
                or evidence.qualification_failure_codes != (qualification.failure.code,)
            ):
                raise ValueError("promotion_query_context_binding_mismatch")
            expected_payload = {
                "schema_version": profile.schema_name,
                "design_problem_binding_ref": design_problem_binding_ref.model_dump(mode="json"),
                "candidate": candidate.model_dump(mode="json"),
                "qualification_result": qualification.model_dump(mode="json"),
            }
            expected_native_query_context_ref = expected_query.requested_query_context_ref
        if expected_payload is None:
            raise ValueError("promotion_query_context_binding_mismatch")
        if expected_native_query_context_ref is None:
            raise ValueError("promotion_query_context_binding_mismatch")
        if (
            not self._artifacts.verify(ref.artifact_id).ok
            or _raw_hash(raw) != str(ref.artifact_id)
            or manifest.kind != profile.kind
            or manifest.media_type != profile.media_type
            or manifest.artifact_schema
            != artifacts.SchemaInfo(
                name=profile.schema_name,
                version=profile.schema_version,
            )
            or manifest.canon != artifacts.CanonInfo.from_spec(profile.canon_spec)
            or raw != c4_canonical_bytes(profile_record, expected_payload)
            or observed_payload != expected_payload
            or evidence.candidate != candidate
            or evidence.verifier_provenance_ref != expected_verifier_provenance_ref
            or evidence.query_artifact_content_hash
            != c4_semantic_digest(profile_record, expected_payload)
            or evidence.native_requested_query_context_ref != expected_native_query_context_ref
        ):
            raise ValueError("promotion_query_context_binding_mismatch")


class PromotionOwnerQueryContextAuthority:
    """Persist one aggregate and bind every member back to it without a cycle."""

    def __init__(
        self,
        *,
        candidates: ArtifactPromotionCandidateDenominatorOwner,
        epoch_queries: EpochResolutionQueryOwner,
        deployment_queries: DeploymentScopeQueryOwner,
        artifacts: ArtifactStore,
        verifier_provenance_ref: ArtifactRef,
    ) -> None:
        self._candidates = candidates
        self._epoch_queries = epoch_queries
        self._deployment_queries = deployment_queries
        self._artifacts = artifacts
        self._verifier_provenance_ref = verifier_provenance_ref

    def persist_for_promotion(
        self,
        *,
        denominator_ref: ArtifactRef,
    ) -> PersistedPromotionContextBatch | PromotionOwnerQueryContextNonReceipt:
        authority_purpose: Literal["n9_promotion"] = "n9_promotion"
        if not self._candidates.admits_denominator(denominator_ref=denominator_ref):
            return PromotionOwnerQueryContextNonReceipt(
                status="rejected", code="promotion_candidate_denominator_mismatch"
            )
        try:
            denominator_statement, snapshot = _load_verified_candidate_denominator(
                artifacts=self._artifacts,
                denominator_ref=denominator_ref,
            )
        except (KeyError, OSError, TypeError, ValueError):
            return PromotionOwnerQueryContextNonReceipt(
                status="rejected", code="promotion_candidate_denominator_mismatch"
            )
        denominator = PersistedPromotionCandidateDenominator(
            denominator_ref=denominator_ref,
            denominator_content_hash=c4_semantic_digest(
                "candidate_denominator", denominator_statement
            ),
            statement=denominator_statement,
        )
        design_problem_ref = snapshot.design_problem_binding_ref
        design_problem_content_hash = snapshot.design_problem_binding_content_hash
        contexts: list[PromotionCandidateOwnerContext] = []
        member_refs: list[tuple[ArtifactRef, Digest]] = []
        for ordinal, (occurrence_ref, occurrence_hash) in enumerate(
            zip(
                denominator.statement.ordered_occurrence_refs,
                denominator.statement.ordered_occurrence_content_hashes,
                strict=True,
            )
        ):
            occurrence = _read_model(
                store=self._artifacts,
                ref=occurrence_ref,
                model=PromotionCandidateOccurrenceStatement,
                profile_record="candidate_occurrence",
            )
            if not isinstance(occurrence, PromotionCandidateOccurrenceStatement):
                raise TypeError("promotion_candidate_occurrence_model_mismatch")
            identity = PromotionCandidateIdentity(
                ordinal=ordinal,
                occurrence_ref=occurrence_ref,
                occurrence_content_hash=occurrence_hash,
                candidate_id=occurrence.candidate_id,
                candidate_content_hash=occurrence.candidate_content_hash,
                candidate_summary_content_hash=occurrence.candidate_summary_content_hash,
            )
            epoch = self._epoch_queries.resolve_for_promotion(
                design_problem_binding_ref=design_problem_ref,
                candidate=identity,
            )
            deployment = self._deployment_queries.resolve_for_promotion(
                design_problem_binding_ref=design_problem_ref,
                candidate=identity,
            )
            if isinstance(epoch, PromotionOwnerQueryContextNonReceipt):
                return epoch
            if isinstance(deployment, PromotionOwnerQueryContextNonReceipt):
                return deployment
            if epoch.family != "semantic_epoch" or deployment.family != "deployment_scope":
                return PromotionOwnerQueryContextNonReceipt(
                    status="rejected", code="promotion_query_family_substitution"
                )
            member_statement = PromotionCandidateContextMemberStatement(
                candidate_occurrence_ref=occurrence_ref,
                candidate_occurrence_content_hash=occurrence_hash,
                epoch_query_evidence_ref=epoch.query_artifact_ref,
                epoch_query_evidence_content_hash=epoch.query_artifact_content_hash,
                epoch_native_query_context_ref=epoch.native_requested_query_context_ref,
                deployment_query_evidence_ref=deployment.query_artifact_ref,
                deployment_query_evidence_content_hash=(deployment.query_artifact_content_hash),
                deployment_native_query_context_ref=(deployment.native_requested_query_context_ref),
                authority_purpose=authority_purpose,
            )
            member_ref, member_hash, _ = _persist_model(
                store=self._artifacts,
                value=member_statement,
                profile_record="member_context",
            )
            member_refs.append((member_ref, member_hash))
            member_context_ref = _semantic_hash(
                "polisyos.promotion-member-query-context.v1",
                {
                    "design_problem_binding_ref": design_problem_ref,
                    "authority_purpose": authority_purpose,
                    "candidate": identity,
                    "epoch_query_ref": epoch.query_artifact_ref,
                    "epoch_query_content_hash": epoch.query_artifact_content_hash,
                    "epoch_native_query_context_ref": epoch.native_requested_query_context_ref,
                    "deployment_query_ref": deployment.query_artifact_ref,
                    "deployment_query_content_hash": deployment.query_artifact_content_hash,
                    "deployment_native_query_context_ref": (
                        deployment.native_requested_query_context_ref
                    ),
                },
            )
            contexts.append(
                PromotionCandidateOwnerContext(
                    candidate=identity,
                    epoch_query=epoch,
                    deployment_query=deployment,
                    member_query_context_ref=member_context_ref,
                )
            )
        requested = _framed_semantic_hash(
            "polisyos.promotion-owner-query-context.v2",
            {
                "design_problem_binding_ref": design_problem_ref,
                "design_problem_binding_content_hash": (design_problem_content_hash),
                "authority_purpose": authority_purpose,
                "candidate_denominator_ref": denominator.denominator_ref,
                "candidate_denominator_content_hash": (denominator.denominator_content_hash),
                "ordered_candidate_contexts": tuple(
                    {
                        "candidate": row.candidate,
                        "member_query_context_ref": row.member_query_context_ref,
                    }
                    for row in contexts
                ),
            },
        )
        aggregate_statement = PromotionOwnerQueryContextStatement(
            design_problem_binding_ref=design_problem_ref,
            design_problem_binding_content_hash=design_problem_content_hash,
            authority_purpose=authority_purpose,
            candidate_denominator_ref=denominator.denominator_ref,
            candidate_denominator_content_hash=denominator.denominator_content_hash,
            ordered_candidate_contexts=tuple(contexts),
            requested_query_context_ref=requested,
            owner_resolution_provenance_ref=self._verifier_provenance_ref,
            predicate_class="independently_reconciled",
        )
        aggregate_ref, aggregate_hash, raw = _persist_model(
            store=self._artifacts,
            value=aggregate_statement,
            profile_record="aggregate_context",
        )
        aggregate = PersistedPromotionOwnerQueryContext(
            context_ref=aggregate_ref,
            raw_cas_hash=_raw_hash(raw),
            semantic_hash=aggregate_hash,
            statement=aggregate_statement,
            verifier_provenance_ref=self._verifier_provenance_ref,
        )
        bound: list[PersistedBoundPromotionCandidateContext] = []
        for ordinal, ((member_ref, member_hash), context) in enumerate(
            zip(member_refs, contexts, strict=True)
        ):
            statement = BoundPromotionCandidateContextStatement(
                aggregate_context_ref=aggregate_ref,
                aggregate_context_content_hash=aggregate_hash,
                member_context_ref=member_ref,
                member_context_content_hash=member_hash,
                candidate_occurrence_ref=context.candidate.occurrence_ref,
                ordinal=ordinal,
            )
            ref, semantic, _ = _persist_model(
                store=self._artifacts,
                value=statement,
                profile_record="bound_member",
            )
            bound.append(
                PersistedBoundPromotionCandidateContext(
                    bound_member_ref=ref,
                    bound_member_content_hash=semantic,
                    statement=statement,
                )
            )
        return PersistedPromotionContextBatch(
            aggregate_context=aggregate,
            ordered_bound_members=tuple(bound),
        )


class ArtifactEpochValidityPreN9SubjectAuthority:
    """Derive the complete first-decision subject from persisted owner handles."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        contexts: ArtifactPromotionOwnerQueryContextRepository,
    ) -> None:
        self._store = store
        self._contexts = contexts

    def persist_for_n9(
        self, *, bound_member_ref: ArtifactRef
    ) -> core_contracts.decision_validity.PersistedPreN9EpochValiditySubject:
        member = self._contexts.resolve_bound_member(bound_member_ref=bound_member_ref)
        aggregate = self._contexts.resolve_verified(
            context_ref=member.statement.aggregate_context_ref
        )
        if isinstance(aggregate, PromotionOwnerQueryContextNonReceipt):
            raise ValueError("pre_n9_owner_query_context_unresolved")
        occurrence = self._contexts.resolve_occurrence(
            occurrence_ref=member.statement.candidate_occurrence_ref
        )
        candidate = aggregate.statement.ordered_candidate_contexts[member.statement.ordinal]
        if candidate.candidate.occurrence_ref != member.statement.candidate_occurrence_ref:
            raise ValueError("pre_n9_subject_candidate_binding_mismatch")
        statement = core_contracts.decision_validity.PreN9EpochValiditySubjectStatement(
            owner_query_context_ref=aggregate.context_ref,
            owner_query_context_content_hash=aggregate.semantic_hash,
            bound_member_ref=member.bound_member_ref,
            bound_member_content_hash=member.bound_member_content_hash,
            candidate_occurrence_ref=member.statement.candidate_occurrence_ref,
            candidate_occurrence_content_hash=c4_semantic_digest(
                "candidate_occurrence", occurrence
            ),
            decision_packet_lineage_key_ref=_semantic_hash(
                "polisyos.decision-validity.pre-n9-lineage.v1",
                {
                    "design_problem_binding_ref": (aggregate.statement.design_problem_binding_ref),
                    "candidate_id": occurrence.candidate_id,
                },
            ),
            current_decision_packet_ref=None,
            packet_epoch_refs=(),
        )
        subject_ref, subject_hash, _ = _persist_model(
            store=self._store,
            value=statement,
            profile_record="pre_n9_epoch_subject",
        )
        return core_contracts.decision_validity.PersistedPreN9EpochValiditySubject(
            subject_ref=subject_ref,
            subject_content_hash=subject_hash,
        )


class ArtifactEpochValidityAuthorityGate:
    """Reload a subject and return the honest no-policy production result."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        contexts: ArtifactPromotionOwnerQueryContextRepository,
        semantic_epoch_service: SemanticEpochService,
    ) -> None:
        self._store = store
        self._contexts = contexts
        self._semantic_epoch_service = semantic_epoch_service

    def reconcile_before_n9(
        self, *, subject_ref: ArtifactRef
    ) -> (
        core_contracts.decision_validity.PersistedEpochValidityGateEvidence
        | core_contracts.decision_validity.EpochValidityGateNonReceipt
    ):
        try:
            subject = _read_model(
                store=self._store,
                ref=subject_ref,
                model=core_contracts.decision_validity.PreN9EpochValiditySubjectStatement,
                profile_record="pre_n9_epoch_subject",
            )
            if not isinstance(
                subject,
                core_contracts.decision_validity.PreN9EpochValiditySubjectStatement,
            ):
                raise TypeError("pre_n9_epoch_subject_model_mismatch")
            subject_hash = c4_semantic_digest("pre_n9_epoch_subject", subject)
            member = self._contexts.resolve_bound_member(bound_member_ref=subject.bound_member_ref)
            aggregate = self._contexts.resolve_verified(context_ref=subject.owner_query_context_ref)
            if isinstance(aggregate, PromotionOwnerQueryContextNonReceipt):
                raise ValueError("pre_n9_owner_query_context_unresolved")
            if (
                subject.owner_query_context_content_hash != aggregate.semantic_hash
                or subject.bound_member_content_hash != member.bound_member_content_hash
                or subject.candidate_occurrence_ref != member.statement.candidate_occurrence_ref
            ):
                raise ValueError("pre_n9_epoch_subject_binding_mismatch")
            candidate = aggregate.statement.ordered_candidate_contexts[member.statement.ordinal]
            query_statement = _read_model(
                store=self._store,
                ref=candidate.epoch_query.query_artifact_ref,
                model=PersistedEpochPromotionQueryStatement,
                profile_record="epoch_query_evidence",
            )
            if not isinstance(query_statement, PersistedEpochPromotionQueryStatement):
                raise TypeError("epoch_query_evidence_model_mismatch")
            if (
                query_statement.design_problem_binding_ref
                != aggregate.statement.design_problem_binding_ref
                or query_statement.candidate != candidate.candidate
                or c4_semantic_digest("epoch_query_evidence", query_statement)
                != candidate.epoch_query.query_artifact_content_hash
            ):
                raise ValueError("epoch_query_evidence_owner_binding_mismatch")
            stored = query_statement.qualification_result
            fresh = self._semantic_epoch_service.qualify_chronology_query(query=stored.query)
            if fresh != stored:
                raise ValueError("epoch_query_qualification_result_drift")
            query_ref = stored.query.requested_query_context_ref
            expected_codes = (
                (stored.failure.code,)
                if isinstance(
                    stored,
                    core_contracts.chronology.NativeChronologyPolicyResolutionFailed,
                )
                else ()
            )
            if (
                candidate.epoch_query.native_requested_query_context_ref != query_ref
                or candidate.epoch_query.qualification_status
                != getattr(
                    stored,
                    "status",
                    getattr(getattr(stored, "failure", None), "status", None),
                )
                or candidate.epoch_query.qualification_failure_codes != expected_codes
            ):
                raise ValueError("epoch_query_evidence_summary_projection_mismatch")
            if isinstance(
                stored,
                core_contracts.chronology.NativeChronologyPolicyResolutionFailed,
            ) and isinstance(
                stored.failure,
                core_contracts.chronology.PolicyAdmissionMissingFailure,
            ):
                return core_contracts.decision_validity.EpochValidityGateNonReceipt(
                    status="not_established",
                    code="policy_admission_missing",
                    subject_ref=subject_ref,
                    requested_query_context_ref=query_ref,
                )
            del subject_hash
            return core_contracts.decision_validity.EpochValidityGateNonReceipt(
                status="not_established",
                code="epoch_transition_signer_not_established",
                subject_ref=subject_ref,
                requested_query_context_ref=query_ref,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return core_contracts.decision_validity.EpochValidityGateNonReceipt(
                status="rejected",
                code="epoch_validity_subject_unresolved",
                subject_ref=subject_ref,
                requested_query_context_ref=_semantic_hash(
                    "polisyos.decision-validity.unresolved-subject.v1",
                    {"subject_ref": subject_ref},
                ),
            )


class ArtifactEpochValidityN9EvidenceResolver:
    """Independently reload positive subject/gate evidence for canonical N9."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        contexts: ArtifactPromotionOwnerQueryContextRepository,
        verifier_provenance_ref: ArtifactRef,
        completed_batches: (
            core_contracts.decision_validity.EpochValidityCompletedBatchEvidenceResolver | None
        ) = None,
    ) -> None:
        self._store = store
        self._contexts = contexts
        self._verifier_provenance_ref = verifier_provenance_ref
        self._completed_batches = completed_batches

    def resolve_verified(
        self,
        *,
        admission: core_contracts.decision_validity.PreN9AdmittedCandidate,
        expected_design_problem_ref: ArtifactRef,
    ) -> (
        core_contracts.decision_validity.EpochValidityN9Projection
        | core_contracts.decision_validity.EpochValidityGateNonReceipt
    ):
        try:
            subject = _read_model(
                store=self._store,
                ref=admission.subject_ref,
                model=core_contracts.decision_validity.PreN9EpochValiditySubjectStatement,
                profile_record="pre_n9_epoch_subject",
            )
            gate = _read_model(
                store=self._store,
                ref=admission.gate_evidence_ref,
                model=core_contracts.decision_validity.EpochValidityGateReceipt,
                profile_record="epoch_validity_gate_receipt",
            )
            if not isinstance(
                subject,
                core_contracts.decision_validity.PreN9EpochValiditySubjectStatement,
            ) or not isinstance(gate, core_contracts.decision_validity.EpochValidityGateReceipt):
                raise TypeError("epoch_validity_gate_model_mismatch")
            aggregate = self._contexts.resolve_verified(context_ref=admission.aggregate_context_ref)
            member = self._contexts.resolve_bound_member(
                bound_member_ref=admission.bound_member_ref
            )
            if isinstance(aggregate, PromotionOwnerQueryContextNonReceipt):
                raise ValueError("epoch_validity_aggregate_unresolved")
            if (
                aggregate.statement.design_problem_binding_ref != expected_design_problem_ref
                or admission.aggregate_context_content_hash != aggregate.semantic_hash
                or admission.bound_member_content_hash != member.bound_member_content_hash
                or member.statement.aggregate_context_ref != admission.aggregate_context_ref
                or member.statement.candidate_occurrence_ref != admission.candidate_occurrence_ref
                or subject.owner_query_context_ref != admission.aggregate_context_ref
                or subject.bound_member_ref != admission.bound_member_ref
                or subject.candidate_occurrence_ref != admission.candidate_occurrence_ref
                or c4_semantic_digest("pre_n9_epoch_subject", subject)
                != admission.subject_content_hash
                or c4_semantic_digest("epoch_validity_gate_receipt", gate)
                != admission.gate_evidence_content_hash
                or gate.subject_ref != admission.subject_ref
                or gate.subject_content_hash != admission.subject_content_hash
                or gate.status not in {"current", "batch_completed"}
            ):
                raise ValueError("epoch_validity_n9_binding_mismatch")
            if gate.status == "current":
                # A shaped prior-binding ref is not an owner receipt.  The
                # current arm remains closed until an owner reader for that
                # separately persisted binding is installed.
                raise ValueError("epoch_validity_prior_binding_unresolved")
            completed_ref = gate.completed_batch_receipt_ref
            if completed_ref is None or self._completed_batches is None:
                raise ValueError("epoch_validity_completed_batch_unresolved")
            completed = self._completed_batches.resolve_completed_epoch_batch_evidence(
                batch_receipt_ref=completed_ref
            )
            if (
                completed.batch_receipt_ref != completed_ref
                or completed.receipt.requested_query_context_ref != gate.requested_query_context_ref
                or completed.receipt.dependency_denominator_ref != gate.dependency_denominator_ref
                or completed.receipt.adjudication_denominator_ref
                != gate.adjudication_denominator_ref
                or (
                    gate.current_decision_packet_ref is not None
                    and str(gate.current_decision_packet_ref.artifact_id)
                    not in completed.receipt.affected_packet_refs
                )
            ):
                raise ValueError("epoch_validity_completed_batch_binding_mismatch")
            return core_contracts.decision_validity.EpochValidityN9Projection(
                owner_query_context_ref=admission.aggregate_context_ref,
                owner_query_context_content_hash=admission.aggregate_context_content_hash,
                bound_member_ref=admission.bound_member_ref,
                bound_member_content_hash=admission.bound_member_content_hash,
                candidate_occurrence_ref=admission.candidate_occurrence_ref,
                candidate_occurrence_content_hash=(admission.candidate_occurrence_content_hash),
                subject_ref=admission.subject_ref,
                subject_content_hash=admission.subject_content_hash,
                gate_receipt_ref=admission.gate_evidence_ref,
                gate_receipt_content_hash=admission.gate_evidence_content_hash,
                requested_query_context_ref=gate.requested_query_context_ref,
                current_decision_packet_ref=gate.current_decision_packet_ref,
                completed_batch_receipt_ref=gate.completed_batch_receipt_ref,
                verifier_provenance_ref=self._verifier_provenance_ref,
                status=gate.status,
                predicate_class="independently_reconciled",
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return core_contracts.decision_validity.EpochValidityGateNonReceipt(
                status="rejected",
                code="epoch_validity_gate_evidence_unresolved",
                subject_ref=admission.subject_ref,
                requested_query_context_ref=_semantic_hash(
                    "polisyos.decision-validity.unresolved-gate.v1",
                    {"gate_ref": admission.gate_evidence_ref},
                ),
            )

    def resolve_projection_verified(
        self,
        *,
        projection: core_contracts.decision_validity.EpochValidityN9Projection,
        expected_problem_content_hash: Digest,
    ) -> (
        core_contracts.decision_validity.EpochValidityN9Projection
        | core_contracts.decision_validity.EpochValidityGateNonReceipt
    ):
        """Rebuild handles from the projection and re-read every owner artifact."""

        admission = core_contracts.decision_validity.PreN9AdmittedCandidate(
            aggregate_context_ref=projection.owner_query_context_ref,
            aggregate_context_content_hash=projection.owner_query_context_content_hash,
            bound_member_ref=projection.bound_member_ref,
            bound_member_content_hash=projection.bound_member_content_hash,
            candidate_occurrence_ref=projection.candidate_occurrence_ref,
            candidate_occurrence_content_hash=(projection.candidate_occurrence_content_hash),
            subject_ref=projection.subject_ref,
            subject_content_hash=projection.subject_content_hash,
            gate_evidence_ref=projection.gate_receipt_ref,
            gate_evidence_content_hash=projection.gate_receipt_content_hash,
        )
        try:
            aggregate = self._contexts.resolve_verified(
                context_ref=projection.owner_query_context_ref
            )
            if isinstance(aggregate, PromotionOwnerQueryContextNonReceipt):
                raise ValueError("epoch_validity_aggregate_unresolved")
            problem_raw = self._store.get_bytes(
                aggregate.statement.design_problem_binding_ref.artifact_id
            )
            problem = DesignProblem.model_validate(canon.from_canonical_bytes(problem_raw))
            if gy_content_hash(problem.model_dump(mode="json")) != expected_problem_content_hash:
                raise ValueError("epoch_validity_design_problem_binding_mismatch")
            resolved = self.resolve_verified(
                admission=admission,
                expected_design_problem_ref=(aggregate.statement.design_problem_binding_ref),
            )
            if (
                not isinstance(
                    resolved,
                    core_contracts.decision_validity.EpochValidityN9Projection,
                )
                or resolved != projection
            ):
                raise ValueError("epoch_validity_projection_binding_mismatch")
            return resolved
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return core_contracts.decision_validity.EpochValidityGateNonReceipt(
                status="rejected",
                code="epoch_validity_gate_evidence_unresolved",
                subject_ref=projection.subject_ref,
                requested_query_context_ref=(projection.requested_query_context_ref),
            )


def seal_pre_n9_admitted_candidate_batch(
    *,
    store: ArtifactStore,
    denominator: PersistedPromotionCandidateDenominator,
    contexts: PersistedPromotionContextBatch,
    admissions: Sequence[core_contracts.decision_validity.PreN9AdmittedCandidate],
) -> core_contracts.decision_validity.PersistedPreN9AdmittedCandidateBatch:
    """Seal an exact ordered bijection against the completed generation denominator."""

    expected_refs = tuple(
        str(ref.artifact_id) for ref in denominator.statement.ordered_occurrence_refs
    )
    observed_refs = tuple(str(row.candidate_occurrence_ref.artifact_id) for row in admissions)
    if expected_refs != observed_refs or len(admissions) != len(contexts.ordered_bound_members):
        raise ValueError("epoch_validity_admission_denominator_mismatch")
    aggregate = contexts.aggregate_context
    draft = core_contracts.decision_validity.PersistedPreN9AdmittedCandidateBatch(
        aggregate_context_ref=aggregate.context_ref,
        aggregate_context_content_hash=aggregate.semantic_hash,
        candidate_denominator_ref=denominator.denominator_ref,
        candidate_denominator_content_hash=denominator.denominator_content_hash,
        ordered_admissions=tuple(admissions),
        batch_content_hash="sha256:" + "0" * 64,
    )
    batch_hash = c4_semantic_digest("pre_n9_admitted_candidate_batch", draft)
    batch = draft.model_copy(update={"batch_content_hash": batch_hash})
    _, persisted_hash, _ = _persist_model(
        store=store,
        value=batch,
        profile_record="pre_n9_admitted_candidate_batch",
    )
    if persisted_hash != batch_hash:
        raise ValueError("epoch_validity_admission_batch_hash_mismatch")
    return batch


__all__ = [
    "AdvisoryPerturbationEvent",
    "ArtifactEpochValidityAuthorityGate",
    "ArtifactEpochValidityN9EvidenceResolver",
    "ArtifactEpochValidityPreN9SubjectAuthority",
    "ArtifactPromotionCandidateDenominatorOwner",
    "ArtifactPromotionOwnerQueryContextRepository",
    "BoundPromotionCandidateContextStatement",
    "DeploymentPromotionQueryEvidence",
    "DeploymentScopeQueryOwner",
    "DerivationRecipeBinding",
    "EpochCertificateBinding",
    "EpochDependencyDenominatorProvider",
    "EpochDependencyDenominatorReceipt",
    "EpochDependencyEdge",
    "EpochDependencyGraph",
    "EpochPerturbationAdjudicationProvider",
    "EpochPerturbationAdjudicationReceipt",
    "EpochPromotionQueryEvidence",
    "EpochResolutionQueryOwner",
    "EpochTransitionSigningAuthority",
    "EpochTransitionSigningNonReceipt",
    "EpochValidityTransitionArtifact",
    "EpochValidityTransitionProducer",
    "OwnerAdjudicatedTargetDisposition",
    "PersistedBoundPromotionCandidateContext",
    "PersistedEpochValidityTransition",
    "PersistedPromotionCandidateDenominator",
    "PersistedPromotionContextBatch",
    "PersistedPromotionOwnerQueryContext",
    "PromotionCandidateContextMemberStatement",
    "PromotionCandidateDenominatorStatement",
    "PromotionCandidateIdentity",
    "PromotionCandidateOccurrenceStatement",
    "PromotionCandidateOwnerContext",
    "PromotionOwnerQueryContextAuthority",
    "PromotionOwnerQueryContextNonReceipt",
    "PromotionOwnerQueryContextStatement",
    "PromotionOwnerQueryContextVerifier",
    "TargetDispositionVector",
    "bind_certificate_to_epoch",
    "build_epoch_validity_transition",
    "promotion_candidate_summary_content_hash",
    "promotion_epoch_query",
    "resolve_owner_target_dispositions",
    "seal_pre_n9_admitted_candidate_batch",
]
