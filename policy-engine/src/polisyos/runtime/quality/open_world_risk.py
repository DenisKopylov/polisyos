"""Persist and replay OpenWorldRisk without inventing deployment authority.

The production default is intentionally useful and negative: it enumerates the
complete declared comparison denominator, asks an explicitly unallocated
lifecycle owner, persists one ``not_established`` row per component, and then
independently reloads that vector.  A negative vector is evidence that the gate
ran; it is never positive evidence that deployment scope is safe.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence  # noqa: TC003
from dataclasses import dataclass
from typing import Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, canon
from polisyos.core import contracts as core_contracts
from polisyos.pdc import PromotionObligationClass
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.epoch_validity_cascade import (
    ArtifactEpochValidityAuthorityGate,
    ArtifactEpochValidityN9EvidenceResolver,
    ArtifactEpochValidityPreN9SubjectAuthority,
    ArtifactPromotionCandidateDenominatorOwner,
    ArtifactPromotionOwnerQueryContextRepository,
    DeploymentPromotionQueryEvidence,
    EpochPromotionQueryEvidence,
    PersistedBoundPromotionCandidateContext,
    PersistedEpochPromotionQueryStatement,
    PersistedPromotionCandidateDenominator,
    PersistedPromotionContextBatch,
    PromotionCandidateIdentity,
    PromotionOwnerQueryContextAuthority,
    PromotionOwnerQueryContextNonReceipt,
    _persist_model,
    _raw_hash,
    _read_model,
    _seal_completed_generation_candidate_batch,
    _semantic_hash,
    promotion_candidate_summary_content_hash,
    promotion_epoch_query,
)
from polisyos.runtime.quality.generation_cycle import CandidateSummary  # noqa: TC001
from polisyos.runtime.quality.semantic_epoch import SemanticEpochService

ArtifactID = artifacts.ArtifactID
ArtifactRef = artifacts.ArtifactRef
ArtifactStore = artifacts.ArtifactStore
ArtifactWriteOptions = artifacts.ArtifactWriteOptions
Digest = core_contracts.chronology.Digest
DeploymentLifecycleRole = Literal["authorized_intended", "actual"]
c4_profile = core_contracts.c4_profile
c4_semantic_digest = core_contracts.c4_semantic_digest

_VERIFIER_PROVENANCE_BYTES = b"polisyos.open-world-risk.verifier.v1\n"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DeploymentScopeQuery(_StrictModel):
    """Owner query for one declared comparison component."""

    authority_purpose: str = Field(min_length=1)
    requested_query_context_ref: Digest
    aggregate_context_ref: ArtifactRef
    bound_member_ref: ArtifactRef
    candidate_occurrence_ref: ArtifactRef
    component_ref: Digest
    component_kind: Literal["model", "obligation", "calibration", "novel"]


class DeploymentScopeRoleResolution(_StrictModel):
    """Lifecycle-owner role result; the default is a typed unknown."""

    query: DeploymentScopeQuery
    status: Literal["within_scope", "outside_scope", "not_established"]
    role: DeploymentLifecycleRole | None = None
    limitation_code: str = Field(min_length=1)
    evidence_ref: ArtifactRef | None = None
    evidence_content_hash: Digest | None = None
    predicate_class: Literal["independently_reconciled", "not_established"]

    @model_validator(mode="after")
    def _positive_requires_evidence(self) -> Self:
        positive = self.status in {"within_scope", "outside_scope"}
        if positive != (self.evidence_ref is not None):
            raise ValueError("deployment_scope_positive_evidence_shape_invalid")
        if positive != (self.evidence_content_hash is not None):
            raise ValueError("deployment_scope_positive_evidence_hash_shape_invalid")
        if positive and self.predicate_class != "independently_reconciled":
            raise ValueError("deployment_scope_positive_predicate_not_reconciled")
        if not positive:
            if self.predicate_class != "not_established":
                raise ValueError("deployment_scope_negative_predicate_class_invalid")
            if (
                self.role is not None
                or self.evidence_ref is not None
                or self.evidence_content_hash is not None
            ):
                raise ValueError("deployment_scope_negative_authority_fields_present")
        return self


class CompetentDeploymentScopeEvidence(_StrictModel):
    """Positive institutional evidence. No production producer is appointed here."""

    query: DeploymentScopeQuery
    role: DeploymentLifecycleRole
    status: Literal["within_scope", "outside_scope"]
    evidence_ref: ArtifactRef
    evidence_content_hash: Digest
    verifier_provenance_ref: ArtifactRef


class VerifiedDeploymentScopeEvidence(CompetentDeploymentScopeEvidence):
    predicate_class: Literal["independently_reconciled"]


class DeploymentLifecycleQueryOwner(Protocol):
    def resolve_component(
        self, *, query: DeploymentScopeQuery
    ) -> DeploymentScopeRoleResolution: ...


class CompetentDeploymentScopeEvidenceVerifier(Protocol):
    def verify(
        self, *, evidence: CompetentDeploymentScopeEvidence
    ) -> VerifiedDeploymentScopeEvidence | DeploymentScopeRoleResolution: ...


class NoDeploymentLifecycleOwner:
    """Explicit production absence; never derives a role from caller data."""

    def resolve_component(self, *, query: DeploymentScopeQuery) -> DeploymentScopeRoleResolution:
        return DeploymentScopeRoleResolution(
            query=query,
            status="not_established",
            role=None,
            limitation_code="deployment_lifecycle_owner_not_established",
            evidence_ref=None,
            evidence_content_hash=None,
            predicate_class="not_established",
        )


class NoPositiveDeploymentScopeEvidenceVerifier:
    """Fail-closed verifier used while the positive evidence producer is missing."""

    def verify(
        self, *, evidence: CompetentDeploymentScopeEvidence
    ) -> DeploymentScopeRoleResolution:
        return DeploymentScopeRoleResolution(
            query=evidence.query,
            status="not_established",
            role=None,
            limitation_code="competent_deployment_scope_evidence_not_established",
            evidence_ref=None,
            evidence_content_hash=None,
            predicate_class="not_established",
        )


def _independently_resolve_deployment_scope(
    *,
    query: DeploymentScopeQuery,
    lifecycle_owner: DeploymentLifecycleQueryOwner,
    evidence_verifier: CompetentDeploymentScopeEvidenceVerifier,
    verifier_provenance_ref: ArtifactRef,
) -> DeploymentScopeRoleResolution:
    """Resolve one role without trusting either caller or persisted vector fields."""

    resolved = lifecycle_owner.resolve_component(query=query)
    if resolved.query != query:
        return DeploymentScopeRoleResolution(
            query=query,
            status="not_established",
            limitation_code="deployment_scope_owner_query_mismatch",
            predicate_class="not_established",
        )
    if resolved.status == "not_established":
        return resolved
    if (
        resolved.role is None
        or resolved.evidence_ref is None
        or resolved.evidence_content_hash is None
    ):
        return DeploymentScopeRoleResolution(
            query=query,
            status="not_established",
            limitation_code="deployment_lifecycle_owner_not_established",
            predicate_class="not_established",
        )
    evidence = CompetentDeploymentScopeEvidence(
        query=query,
        role=resolved.role,
        status=resolved.status,
        evidence_ref=resolved.evidence_ref,
        evidence_content_hash=resolved.evidence_content_hash,
        verifier_provenance_ref=verifier_provenance_ref,
    )
    verified = evidence_verifier.verify(evidence=evidence)
    if not isinstance(verified, VerifiedDeploymentScopeEvidence) or (
        verified.query != query
        or verified.role != evidence.role
        or verified.status != evidence.status
        or verified.evidence_ref != evidence.evidence_ref
        or verified.evidence_content_hash != evidence.evidence_content_hash
        or verified.verifier_provenance_ref != verifier_provenance_ref
    ):
        return DeploymentScopeRoleResolution(
            query=query,
            status="not_established",
            limitation_code="deployment_lifecycle_owner_not_established",
            predicate_class="not_established",
        )
    return DeploymentScopeRoleResolution(
        query=query,
        status=verified.status,
        role=verified.role,
        limitation_code=(
            "deployment_scope_within_scope"
            if verified.status == "within_scope"
            else "deployment_scope_outside_scope"
        ),
        evidence_ref=verified.evidence_ref,
        evidence_content_hash=verified.evidence_content_hash,
        predicate_class="independently_reconciled",
    )


class DeclaredScopeComponent(_StrictModel):
    """One comparison slot derived from already-bound problem/candidate bytes."""

    component_id: str = Field(min_length=1)
    component_kind: Literal["model", "obligation", "calibration", "novel"]
    component_ref: Digest
    source_status: Literal["present", "declared_absent"]


class DeclaredScopeManifest(_StrictModel):
    """Complete declared denominator for one bound promotion member."""

    aggregate_context_ref: ArtifactRef
    aggregate_context_content_hash: Digest
    bound_member_ref: ArtifactRef
    bound_member_content_hash: Digest
    candidate_occurrence_ref: ArtifactRef
    candidate_occurrence_content_hash: Digest
    requested_query_context_ref: Digest
    authority_purpose: str = Field(min_length=1)
    components: tuple[DeclaredScopeComponent, ...]
    declared_component_denominator_ref: Digest

    @model_validator(mode="after")
    def _denominator_is_exact(self) -> Self:
        ids = tuple(row.component_id for row in self.components)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("declared_scope_component_denominator_invalid")
        expected = _semantic_hash(
            "polisyos.deployment.declared-scope-denominator.v1",
            {"components": self.components},
        )
        if self.declared_component_denominator_ref != expected:
            raise ValueError("declared_scope_component_denominator_mismatch")
        return self


class OpenWorldRiskComponent(_StrictModel):
    """One owner-resolved component; no numeric risk score is admitted."""

    component_id: str = Field(min_length=1)
    component_kind: Literal["model", "obligation", "calibration", "novel"]
    component_ref: Digest
    status: Literal["within_scope", "outside_scope", "not_established"]
    limitation_code: str = Field(min_length=1)
    role: DeploymentLifecycleRole | None = None
    evidence_ref: ArtifactRef | None = None
    evidence_content_hash: Digest | None = None
    predicate_class: Literal["independently_reconciled", "not_established"]


class OpenWorldRiskVector(_StrictModel):
    """Complete non-numeric vector bound to one aggregate/member pair."""

    schema_version: Literal["polisyos.promotion.open-world-risk-vector.v1"] = (
        "polisyos.promotion.open-world-risk-vector.v1"
    )
    aggregate_context_ref: ArtifactRef
    aggregate_context_content_hash: Digest
    bound_member_ref: ArtifactRef
    bound_member_content_hash: Digest
    candidate_occurrence_ref: ArtifactRef
    candidate_occurrence_content_hash: Digest
    requested_query_context_ref: Digest
    declared_component_denominator_ref: Digest
    lifecycle_role_denominator_ref: Digest
    components: tuple[OpenWorldRiskComponent, ...]
    status: Literal["established", "limited", "not_established"]
    limitation_code: str
    vector_content_hash: Digest

    @model_validator(mode="after")
    def _vector_is_derived(self) -> Self:
        ids = tuple(row.component_id for row in self.components)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("open_world_component_denominator_invalid")
        derived = (
            "limited"
            if any(row.status == "outside_scope" for row in self.components)
            else "not_established"
            if any(row.status == "not_established" for row in self.components)
            else "established"
        )
        if self.status != derived:
            raise ValueError("open_world_status_not_derived")
        expected_code = (
            "deployment_scope_not_established"
            if derived == "not_established"
            else "deployment_scope_limited"
            if derived == "limited"
            else "deployment_scope_established"
        )
        if self.limitation_code != expected_code:
            raise ValueError("open_world_limitation_code_not_derived")
        expected = c4_semantic_digest("open_world_risk_vector", self)
        if self.vector_content_hash != expected:
            raise ValueError("open_world_vector_content_mismatch")
        return self


class OpenWorldRiskPublicLimitation(_StrictModel):
    """Minimal safe public projection."""

    status: Literal["limited", "not_established"]
    code: str = Field(min_length=1)
    vector_artifact_ref: ArtifactRef


def resolve_open_world_risk(
    *,
    manifest: DeclaredScopeManifest,
    resolutions: Sequence[DeploymentScopeRoleResolution],
    supplied_low: bool | None = None,
) -> OpenWorldRiskVector:
    """Derive one row per declared component; supplied booleans have no authority."""

    del supplied_low
    by_ref = {row.query.component_ref: row for row in resolutions}
    if len(by_ref) != len(resolutions):
        raise ValueError("deployment_scope_resolution_duplicate_component")
    declared_refs = {row.component_ref for row in manifest.components}
    if set(by_ref) - declared_refs:
        raise ValueError("deployment_scope_resolution_novel_component")
    rows: list[OpenWorldRiskComponent] = []
    for component in manifest.components:
        resolved = by_ref.get(component.component_ref)
        if component.source_status == "declared_absent":
            rows.append(
                OpenWorldRiskComponent(
                    component_id=component.component_id,
                    component_kind=component.component_kind,
                    component_ref=component.component_ref,
                    status="not_established",
                    limitation_code="deployment_scope_component_source_absent",
                    predicate_class="not_established",
                )
            )
            continue
        if resolved is None:
            rows.append(
                OpenWorldRiskComponent(
                    component_id=component.component_id,
                    component_kind=component.component_kind,
                    component_ref=component.component_ref,
                    status="not_established",
                    limitation_code="deployment_scope_component_not_established",
                    predicate_class="not_established",
                )
            )
            continue
        rows.append(
            OpenWorldRiskComponent(
                component_id=component.component_id,
                component_kind=component.component_kind,
                component_ref=component.component_ref,
                status=resolved.status,
                limitation_code=resolved.limitation_code,
                role=resolved.role,
                evidence_ref=resolved.evidence_ref,
                evidence_content_hash=resolved.evidence_content_hash,
                predicate_class=resolved.predicate_class,
            )
        )
    role_denominator = _semantic_hash(
        "polisyos.deployment.lifecycle-role-denominator.v1",
        {"rows": tuple(resolutions)},
    )
    status: Literal["established", "limited", "not_established"] = (
        "limited"
        if any(row.status == "outside_scope" for row in rows)
        else "not_established"
        if any(row.status == "not_established" for row in rows)
        else "established"
    )
    code = (
        "deployment_scope_not_established"
        if status == "not_established"
        else "deployment_scope_limited"
        if status == "limited"
        else "deployment_scope_established"
    )
    payload = {
        "schema_version": c4_profile("open_world_risk_vector").schema_name,
        "aggregate_context_ref": manifest.aggregate_context_ref,
        "aggregate_context_content_hash": manifest.aggregate_context_content_hash,
        "bound_member_ref": manifest.bound_member_ref,
        "bound_member_content_hash": manifest.bound_member_content_hash,
        "candidate_occurrence_ref": manifest.candidate_occurrence_ref,
        "candidate_occurrence_content_hash": manifest.candidate_occurrence_content_hash,
        "requested_query_context_ref": manifest.requested_query_context_ref,
        "declared_component_denominator_ref": (manifest.declared_component_denominator_ref),
        "lifecycle_role_denominator_ref": role_denominator,
        "components": tuple(rows),
        "status": status,
        "limitation_code": code,
    }
    draft = OpenWorldRiskVector.model_construct(
        **payload,
        vector_content_hash="sha256:" + "0" * 64,
    )
    return OpenWorldRiskVector(
        **payload,
        vector_content_hash=c4_semantic_digest("open_world_risk_vector", draft),
    )


class VerifiedOpenWorldRiskVector(_StrictModel):
    vector: OpenWorldRiskVector
    candidate: PromotionCandidateIdentity
    vector_artifact_ref: ArtifactRef
    raw_cas_hash: Digest
    semantic_hash: Digest
    requested_query_context_ref: Digest
    aggregate_context_ref: ArtifactRef
    bound_member_ref: ArtifactRef
    candidate_occurrence_ref: ArtifactRef
    verifier_provenance_ref: ArtifactRef
    predicate_class: Literal["independently_reconciled"]


class OpenWorldRiskResolutionNonReceipt(_StrictModel):
    status: Literal["not_established", "rejected"]
    code: Literal[
        "open_world_vector_unresolved",
        "open_world_vector_content_mismatch",
        "open_world_vector_query_mismatch",
        "open_world_verifier_untrusted",
    ]


class PersistedOpenWorldRiskVector(_StrictModel):
    vector_artifact_ref: ArtifactRef
    raw_cas_hash: Digest
    semantic_hash: Digest
    declared_component_denominator_ref: Digest
    lifecycle_role_denominator_ref: Digest
    verifier_provenance_ref: ArtifactRef
    requested_query_context_ref: Digest
    aggregate_context_ref: ArtifactRef
    aggregate_context_content_hash: Digest
    bound_member_ref: ArtifactRef
    bound_member_content_hash: Digest
    candidate_occurrence_ref: ArtifactRef
    candidate_occurrence_content_hash: Digest


class OpenWorldRiskProductionNonReceipt(_StrictModel):
    status: Literal["not_established", "rejected"]
    code: Literal[
        "declared_scope_manifest_unresolved",
        "declared_scope_component_denominator_mismatch",
        "open_world_vector_persistence_failed",
    ]
    requested_query_context_ref: Digest


class PromotionDeclaredScopeManifestProvider(Protocol):
    def resolve_complete_manifest(
        self, *, member: PersistedBoundPromotionCandidateContext
    ) -> DeclaredScopeManifest | OpenWorldRiskProductionNonReceipt: ...


class OpenWorldRiskArtifactResolver(Protocol):
    def resolve_verified(
        self,
        *,
        vector_artifact_ref: ArtifactRef,
        expected_raw_cas_hash: Digest,
        expected_semantic_hash: Digest,
        requested_query_context_ref: Digest,
        expected_aggregate_context_ref: ArtifactRef,
        expected_bound_member_ref: ArtifactRef,
        expected_candidate_occurrence_ref: ArtifactRef,
        expected_verifier_provenance_ref: ArtifactRef,
    ) -> VerifiedOpenWorldRiskVector | OpenWorldRiskResolutionNonReceipt: ...


class OpenWorldRiskGenerationProjectionResolver(OpenWorldRiskArtifactResolver, Protocol):
    """Replay one vector against the complete generation that exposed it."""

    def resolve_verified_for_generation(
        self,
        *,
        gate: OpenWorldRiskPromotionGate,
        expected_problem: DesignProblem,
        expected_summaries: Sequence[CandidateSummary],
        expected_ordinal: int,
    ) -> VerifiedOpenWorldRiskVector | OpenWorldRiskResolutionNonReceipt: ...


class OpenWorldRiskVectorArtifactRepository:
    """Concrete independent writer/reader over exact vector and provenance bytes."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        lifecycle_owner: DeploymentLifecycleQueryOwner | None = None,
        evidence_verifier: CompetentDeploymentScopeEvidenceVerifier | None = None,
    ) -> None:
        self._store = store
        self._lifecycle_owner = lifecycle_owner or NoDeploymentLifecycleOwner()
        self._evidence_verifier = evidence_verifier or NoPositiveDeploymentScopeEvidenceVerifier()

    def persist_and_verify(
        self,
        *,
        vector: OpenWorldRiskVector,
        declared_manifest: DeclaredScopeManifest,
        lifecycle_role_denominator_ref: Digest,
        verifier_provenance_ref: ArtifactRef,
        requested_query_context_ref: Digest,
    ) -> PersistedOpenWorldRiskVector | OpenWorldRiskProductionNonReceipt:
        if (
            vector.declared_component_denominator_ref
            != declared_manifest.declared_component_denominator_ref
            or vector.lifecycle_role_denominator_ref != lifecycle_role_denominator_ref
            or vector.requested_query_context_ref != requested_query_context_ref
        ):
            return OpenWorldRiskProductionNonReceipt(
                status="rejected",
                code="declared_scope_component_denominator_mismatch",
                requested_query_context_ref=requested_query_context_ref,
            )
        try:
            ref, semantic, raw = _persist_model(
                store=self._store,
                value=vector,
                profile_record="open_world_risk_vector",
            )
            persisted = PersistedOpenWorldRiskVector(
                vector_artifact_ref=ref,
                raw_cas_hash=_raw_hash(raw),
                semantic_hash=semantic,
                declared_component_denominator_ref=(vector.declared_component_denominator_ref),
                lifecycle_role_denominator_ref=vector.lifecycle_role_denominator_ref,
                verifier_provenance_ref=verifier_provenance_ref,
                requested_query_context_ref=vector.requested_query_context_ref,
                aggregate_context_ref=vector.aggregate_context_ref,
                aggregate_context_content_hash=vector.aggregate_context_content_hash,
                bound_member_ref=vector.bound_member_ref,
                bound_member_content_hash=vector.bound_member_content_hash,
                candidate_occurrence_ref=vector.candidate_occurrence_ref,
                candidate_occurrence_content_hash=(vector.candidate_occurrence_content_hash),
            )
            verified = self.resolve_verified(
                vector_artifact_ref=ref,
                expected_raw_cas_hash=persisted.raw_cas_hash,
                expected_semantic_hash=persisted.semantic_hash,
                requested_query_context_ref=persisted.requested_query_context_ref,
                expected_aggregate_context_ref=persisted.aggregate_context_ref,
                expected_bound_member_ref=persisted.bound_member_ref,
                expected_candidate_occurrence_ref=persisted.candidate_occurrence_ref,
                expected_verifier_provenance_ref=verifier_provenance_ref,
            )
            if isinstance(verified, OpenWorldRiskResolutionNonReceipt):
                raise ValueError(verified.code)
            return persisted
        except (OSError, TypeError, ValueError):
            return OpenWorldRiskProductionNonReceipt(
                status="not_established",
                code="open_world_vector_persistence_failed",
                requested_query_context_ref=requested_query_context_ref,
            )

    def resolve_verified(
        self,
        *,
        vector_artifact_ref: ArtifactRef,
        expected_raw_cas_hash: Digest,
        expected_semantic_hash: Digest,
        requested_query_context_ref: Digest,
        expected_aggregate_context_ref: ArtifactRef,
        expected_bound_member_ref: ArtifactRef,
        expected_candidate_occurrence_ref: ArtifactRef,
        expected_verifier_provenance_ref: ArtifactRef,
    ) -> VerifiedOpenWorldRiskVector | OpenWorldRiskResolutionNonReceipt:
        try:
            provenance_report = self._store.verify(expected_verifier_provenance_ref.artifact_id)
            provenance = self._store.get_bytes(expected_verifier_provenance_ref.artifact_id)
            provenance_manifest = self._store.get_manifest(
                expected_verifier_provenance_ref.artifact_id
            )
            if (
                not provenance_report.ok
                or expected_verifier_provenance_ref.kind != "chronology.open_world_risk_verifier"
                or expected_verifier_provenance_ref.media_type != "text/plain"
                or provenance != _VERIFIER_PROVENANCE_BYTES
                or provenance_manifest.artifact_id != expected_verifier_provenance_ref.artifact_id
                or provenance_manifest.kind != "chronology.open_world_risk_verifier"
                or provenance_manifest.media_type != "text/plain"
                or provenance_manifest.byte_size != len(provenance)
                or provenance_manifest.artifact_schema is not None
                or provenance_manifest.canon is not None
                or provenance_manifest.inputs != []
                or provenance_manifest.producer is not None
                or provenance_manifest.env is not None
                or provenance_manifest.governance is not None
                or provenance_manifest.tenant_context is not None
                or provenance_manifest.same_input_closure is not None
                or provenance_manifest.authority is not None
                or provenance_manifest.warnings != []
                or provenance_manifest.integrity.sha256
                != expected_verifier_provenance_ref.artifact_id.hex
                or provenance_manifest.integrity.optional is not None
                or _raw_hash(provenance) != str(expected_verifier_provenance_ref.artifact_id)
            ):
                raise PermissionError("open_world_verifier_untrusted")
            value = _read_model(
                store=self._store,
                ref=vector_artifact_ref,
                model=OpenWorldRiskVector,
                profile_record="open_world_risk_vector",
            )
            if not isinstance(value, OpenWorldRiskVector):
                raise TypeError("open_world_vector_model_mismatch")
            raw = self._store.get_bytes(vector_artifact_ref.artifact_id)
            if (
                _raw_hash(raw) != expected_raw_cas_hash
                or c4_semantic_digest("open_world_risk_vector", value) != expected_semantic_hash
            ):
                return OpenWorldRiskResolutionNonReceipt(
                    status="rejected", code="open_world_vector_content_mismatch"
                )
            if (
                value.requested_query_context_ref != requested_query_context_ref
                or value.aggregate_context_ref != expected_aggregate_context_ref
                or value.bound_member_ref != expected_bound_member_ref
                or value.candidate_occurrence_ref != expected_candidate_occurrence_ref
            ):
                return OpenWorldRiskResolutionNonReceipt(
                    status="rejected", code="open_world_vector_query_mismatch"
                )
            context_verifier = ArtifactPromotionOwnerQueryContextRepository(artifacts=self._store)
            contexts = ArtifactPromotionOwnerQueryContextRepository(
                artifacts=self._store,
                verifier=context_verifier,
            )
            member = contexts.resolve_bound_member(bound_member_ref=expected_bound_member_ref)
            aggregate = contexts.resolve_verified(context_ref=expected_aggregate_context_ref)
            if isinstance(aggregate, PromotionOwnerQueryContextNonReceipt):
                raise ValueError(aggregate.code)
            occurrence = contexts.resolve_occurrence(
                occurrence_ref=expected_candidate_occurrence_ref
            )
            if member.statement.ordinal >= len(aggregate.statement.ordered_candidate_contexts):
                raise ValueError("open_world_vector_query_mismatch")
            candidate = aggregate.statement.ordered_candidate_contexts[
                member.statement.ordinal
            ].candidate
            if (
                value.aggregate_context_content_hash != aggregate.semantic_hash
                or value.bound_member_content_hash != member.bound_member_content_hash
                or value.candidate_occurrence_content_hash
                != c4_semantic_digest("candidate_occurrence", occurrence)
                or candidate.occurrence_ref != expected_candidate_occurrence_ref
                or candidate.candidate_id != occurrence.candidate_id
                or candidate.candidate_content_hash != occurrence.candidate_content_hash
                or candidate.candidate_summary_content_hash
                != occurrence.candidate_summary_content_hash
            ):
                return OpenWorldRiskResolutionNonReceipt(
                    status="rejected", code="open_world_vector_query_mismatch"
                )
            manifest = BoundProblemDeclaredScopeManifestProvider(
                store=self._store,
                contexts=contexts,
            ).resolve_complete_manifest(member=member)
            if isinstance(manifest, OpenWorldRiskProductionNonReceipt):
                raise ValueError(manifest.code)
            recomputed = resolve_open_world_risk(
                manifest=manifest,
                resolutions=tuple(
                    _independently_resolve_deployment_scope(
                        query=DeploymentScopeQuery(
                            authority_purpose=manifest.authority_purpose,
                            requested_query_context_ref=_semantic_hash(
                                "polisyos.deployment.scope-query.v1",
                                {
                                    "bound_member_ref": manifest.bound_member_ref,
                                    "component_ref": component.component_ref,
                                },
                            ),
                            aggregate_context_ref=manifest.aggregate_context_ref,
                            bound_member_ref=manifest.bound_member_ref,
                            candidate_occurrence_ref=manifest.candidate_occurrence_ref,
                            component_ref=component.component_ref,
                            component_kind=component.component_kind,
                        ),
                        lifecycle_owner=self._lifecycle_owner,
                        evidence_verifier=self._evidence_verifier,
                        verifier_provenance_ref=expected_verifier_provenance_ref,
                    )
                    for component in manifest.components
                ),
            )
            if value != recomputed:
                return OpenWorldRiskResolutionNonReceipt(
                    status="rejected", code="open_world_vector_content_mismatch"
                )
            return VerifiedOpenWorldRiskVector(
                vector=value,
                candidate=candidate,
                vector_artifact_ref=vector_artifact_ref,
                raw_cas_hash=expected_raw_cas_hash,
                semantic_hash=expected_semantic_hash,
                requested_query_context_ref=requested_query_context_ref,
                aggregate_context_ref=expected_aggregate_context_ref,
                bound_member_ref=expected_bound_member_ref,
                candidate_occurrence_ref=expected_candidate_occurrence_ref,
                verifier_provenance_ref=expected_verifier_provenance_ref,
                predicate_class="independently_reconciled",
            )
        except PermissionError:
            return OpenWorldRiskResolutionNonReceipt(
                status="rejected", code="open_world_verifier_untrusted"
            )
        except (KeyError, OSError, TypeError, ValueError):
            return OpenWorldRiskResolutionNonReceipt(
                status="not_established", code="open_world_vector_unresolved"
            )

    def resolve_verified_for_generation(
        self,
        *,
        gate: OpenWorldRiskPromotionGate,
        expected_problem: DesignProblem,
        expected_summaries: Sequence[CandidateSummary],
        expected_ordinal: int,
    ) -> VerifiedOpenWorldRiskVector | OpenWorldRiskResolutionNonReceipt:
        """Rebind one verified vector to the full owner-held generation denominator."""

        verified = self.resolve_verified(
            vector_artifact_ref=gate.vector_artifact_ref,
            expected_raw_cas_hash=gate.raw_cas_hash,
            expected_semantic_hash=gate.semantic_hash,
            requested_query_context_ref=gate.requested_query_context_ref,
            expected_aggregate_context_ref=gate.aggregate_context_ref,
            expected_bound_member_ref=gate.bound_member_ref,
            expected_candidate_occurrence_ref=gate.candidate_occurrence_ref,
            expected_verifier_provenance_ref=gate.verifier_provenance_ref,
        )
        if isinstance(verified, OpenWorldRiskResolutionNonReceipt):
            return verified
        try:
            context_verifier = ArtifactPromotionOwnerQueryContextRepository(artifacts=self._store)
            contexts = ArtifactPromotionOwnerQueryContextRepository(
                artifacts=self._store,
                verifier=context_verifier,
            )
            aggregate = contexts.resolve_verified(context_ref=gate.aggregate_context_ref)
            if isinstance(aggregate, PromotionOwnerQueryContextNonReceipt):
                raise ValueError(aggregate.code)
            member = contexts.resolve_bound_member(bound_member_ref=gate.bound_member_ref)
            problem_raw = self._store.get_bytes(
                aggregate.statement.design_problem_binding_ref.artifact_id
            )
            problem = DesignProblem.model_validate(canon.from_canonical_bytes(problem_raw))
            owner_contexts = aggregate.statement.ordered_candidate_contexts
            if (
                problem.model_dump(mode="json") != expected_problem.model_dump(mode="json")
                or len(owner_contexts) != len(expected_summaries)
                or expected_ordinal < 0
                or expected_ordinal >= len(owner_contexts)
                or member.statement.ordinal != expected_ordinal
                or gate.aggregate_context_content_hash != aggregate.semantic_hash
                or gate.bound_member_content_hash != member.bound_member_content_hash
                or gate.status != verified.vector.status
                or gate.limitation_code != verified.vector.limitation_code
            ):
                raise ValueError("open_world_vector_query_mismatch")
            for ordinal, (owner_context, summary) in enumerate(
                zip(owner_contexts, expected_summaries, strict=True)
            ):
                occurrence = contexts.resolve_occurrence(
                    occurrence_ref=owner_context.candidate.occurrence_ref
                )
                if (
                    owner_context.candidate.ordinal != ordinal
                    or owner_context.candidate.candidate_id != summary.candidate_id
                    or owner_context.candidate.candidate_content_hash != summary.content_hash
                    or owner_context.candidate.candidate_summary_content_hash
                    != promotion_candidate_summary_content_hash(summary)
                    or occurrence.candidate_summary != summary
                    or occurrence.candidate_summary_content_hash
                    != promotion_candidate_summary_content_hash(summary)
                ):
                    raise ValueError("open_world_vector_query_mismatch")
            selected = owner_contexts[expected_ordinal].candidate
            occurrence = contexts.resolve_occurrence(occurrence_ref=selected.occurrence_ref)
            if (
                selected != verified.candidate
                or gate.candidate_occurrence_ref != selected.occurrence_ref
                or gate.candidate_occurrence_content_hash
                != c4_semantic_digest("candidate_occurrence", occurrence)
            ):
                raise ValueError("open_world_vector_query_mismatch")
            return verified
        except (KeyError, OSError, TypeError, ValueError):
            return OpenWorldRiskResolutionNonReceipt(
                status="rejected",
                code="open_world_vector_query_mismatch",
            )


class BoundProblemDeclaredScopeManifestProvider:
    """Derive comparison slots from exact problem and occurrence bytes."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        contexts: ArtifactPromotionOwnerQueryContextRepository,
    ) -> None:
        self._store = store
        self._contexts = contexts

    def resolve_complete_manifest(
        self, *, member: PersistedBoundPromotionCandidateContext
    ) -> DeclaredScopeManifest | OpenWorldRiskProductionNonReceipt:
        try:
            aggregate = self._contexts.resolve_verified(
                context_ref=member.statement.aggregate_context_ref
            )
            if isinstance(aggregate, PromotionOwnerQueryContextNonReceipt):
                raise ValueError(aggregate.code)
            if (
                member.statement.aggregate_context_content_hash != aggregate.semantic_hash
                or member.statement.ordinal >= len(aggregate.statement.ordered_candidate_contexts)
            ):
                raise ValueError("bound_member_aggregate_mismatch")
            owner_context = aggregate.statement.ordered_candidate_contexts[member.statement.ordinal]
            if owner_context.candidate.occurrence_ref != member.statement.candidate_occurrence_ref:
                raise ValueError("bound_member_occurrence_mismatch")
            occurrence = self._contexts.resolve_occurrence(
                occurrence_ref=member.statement.candidate_occurrence_ref
            )
            problem_raw = self._store.get_bytes(
                aggregate.statement.design_problem_binding_ref.artifact_id
            )
            problem = DesignProblem.model_validate(canon.from_canonical_bytes(problem_raw))
            model_value = problem.model_spec_ref or "declared_absent"
            calibration_value = occurrence.candidate_summary.value_ref or "declared_absent"
            obligation_denominator = tuple(item.value for item in PromotionObligationClass)
            components = tuple(
                sorted(
                    (
                        DeclaredScopeComponent(
                            component_id="calibration",
                            component_kind="calibration",
                            component_ref=_semantic_hash(
                                "polisyos.deployment.scope-component.calibration.v1",
                                {"value_ref": calibration_value},
                            ),
                            source_status=(
                                "present"
                                if occurrence.candidate_summary.value_ref
                                else "declared_absent"
                            ),
                        ),
                        DeclaredScopeComponent(
                            component_id="model",
                            component_kind="model",
                            component_ref=_semantic_hash(
                                "polisyos.deployment.scope-component.model.v1",
                                {"model_spec_ref": model_value},
                            ),
                            source_status=(
                                "present" if problem.model_spec_ref else "declared_absent"
                            ),
                        ),
                        DeclaredScopeComponent(
                            component_id="obligation",
                            component_kind="obligation",
                            component_ref=_semantic_hash(
                                "polisyos.deployment.scope-component.obligation.v1",
                                {
                                    "constraints": tuple(
                                        row.model_dump(mode="json") for row in problem.constraints
                                    ),
                                    "promotion_obligation_classes": obligation_denominator,
                                },
                            ),
                            source_status="present",
                        ),
                    ),
                    key=lambda row: row.component_id,
                )
            )
            return DeclaredScopeManifest(
                aggregate_context_ref=aggregate.context_ref,
                aggregate_context_content_hash=aggregate.semantic_hash,
                bound_member_ref=member.bound_member_ref,
                bound_member_content_hash=member.bound_member_content_hash,
                candidate_occurrence_ref=member.statement.candidate_occurrence_ref,
                candidate_occurrence_content_hash=owner_context.candidate.occurrence_content_hash,
                requested_query_context_ref=(aggregate.statement.requested_query_context_ref),
                authority_purpose=aggregate.statement.authority_purpose,
                components=components,
                declared_component_denominator_ref=_semantic_hash(
                    "polisyos.deployment.declared-scope-denominator.v1",
                    {"components": components},
                ),
            )
        except (KeyError, OSError, TypeError, ValueError):
            query_ref = _semantic_hash(
                "polisyos.open-world-risk.unresolved-manifest.v1",
                {"bound_member_ref": member.bound_member_ref},
            )
            return OpenWorldRiskProductionNonReceipt(
                status="not_established",
                code="declared_scope_manifest_unresolved",
                requested_query_context_ref=query_ref,
            )


class OpenWorldRiskVectorProducer:
    def __init__(
        self,
        *,
        owner_contexts: ArtifactPromotionOwnerQueryContextRepository,
        manifests: PromotionDeclaredScopeManifestProvider,
        lifecycle_owner: DeploymentLifecycleQueryOwner,
        evidence_verifier: CompetentDeploymentScopeEvidenceVerifier,
        artifacts: OpenWorldRiskVectorArtifactRepository,
        verifier_provenance_ref: ArtifactRef,
    ) -> None:
        self._owner_contexts = owner_contexts
        self._manifests = manifests
        self._lifecycle_owner = lifecycle_owner
        self._evidence_verifier = evidence_verifier
        self._artifacts = artifacts
        self._verifier_provenance_ref = verifier_provenance_ref

    def _resolve_verified_component(
        self,
        *,
        query: DeploymentScopeQuery,
    ) -> DeploymentScopeRoleResolution:
        """Bind any positive owner result to the configured competent verifier."""

        return _independently_resolve_deployment_scope(
            query=query,
            lifecycle_owner=self._lifecycle_owner,
            evidence_verifier=self._evidence_verifier,
            verifier_provenance_ref=self._verifier_provenance_ref,
        )

    def produce_for_candidate(
        self, *, bound_member_ref: ArtifactRef
    ) -> PersistedOpenWorldRiskVector | OpenWorldRiskProductionNonReceipt:
        try:
            member = self._owner_contexts.resolve_bound_member(bound_member_ref=bound_member_ref)
        except (KeyError, OSError, TypeError, ValueError):
            return OpenWorldRiskProductionNonReceipt(
                status="not_established",
                code="declared_scope_manifest_unresolved",
                requested_query_context_ref=_semantic_hash(
                    "polisyos.open-world-risk.unresolved-member.v1",
                    {"bound_member_ref": bound_member_ref},
                ),
            )
        manifest = self._manifests.resolve_complete_manifest(member=member)
        if isinstance(manifest, OpenWorldRiskProductionNonReceipt):
            return manifest
        resolutions = tuple(
            self._resolve_verified_component(
                query=DeploymentScopeQuery(
                    authority_purpose=manifest.authority_purpose,
                    requested_query_context_ref=_semantic_hash(
                        "polisyos.deployment.scope-query.v1",
                        {
                            "bound_member_ref": manifest.bound_member_ref,
                            "component_ref": component.component_ref,
                        },
                    ),
                    aggregate_context_ref=manifest.aggregate_context_ref,
                    bound_member_ref=manifest.bound_member_ref,
                    candidate_occurrence_ref=manifest.candidate_occurrence_ref,
                    component_ref=component.component_ref,
                    component_kind=component.component_kind,
                )
            )
            for component in manifest.components
        )
        vector = resolve_open_world_risk(
            manifest=manifest,
            resolutions=resolutions,
        )
        return self._artifacts.persist_and_verify(
            vector=vector,
            declared_manifest=manifest,
            lifecycle_role_denominator_ref=vector.lifecycle_role_denominator_ref,
            verifier_provenance_ref=self._verifier_provenance_ref,
            requested_query_context_ref=vector.requested_query_context_ref,
        )


class OpenWorldRiskPromotionAuthority:
    def __init__(
        self,
        *,
        producer: OpenWorldRiskVectorProducer,
        resolver: OpenWorldRiskGenerationProjectionResolver,
    ) -> None:
        self._producer = producer
        self._resolver = resolver

    @property
    def resolver(self) -> OpenWorldRiskGenerationProjectionResolver:
        return self._resolver

    def prepare_verified_projection(
        self, *, bound_member_ref: ArtifactRef
    ) -> (
        VerifiedOpenWorldRiskVector
        | OpenWorldRiskResolutionNonReceipt
        | OpenWorldRiskProductionNonReceipt
    ):
        persisted = self._producer.produce_for_candidate(bound_member_ref=bound_member_ref)
        if isinstance(persisted, OpenWorldRiskProductionNonReceipt):
            return persisted
        return self._resolver.resolve_verified(
            vector_artifact_ref=persisted.vector_artifact_ref,
            expected_raw_cas_hash=persisted.raw_cas_hash,
            expected_semantic_hash=persisted.semantic_hash,
            requested_query_context_ref=persisted.requested_query_context_ref,
            expected_aggregate_context_ref=persisted.aggregate_context_ref,
            expected_bound_member_ref=persisted.bound_member_ref,
            expected_candidate_occurrence_ref=persisted.candidate_occurrence_ref,
            expected_verifier_provenance_ref=persisted.verifier_provenance_ref,
        )


class OpenWorldRiskPromotionGate(_StrictModel):
    """Exact N9 projection of one independently reloaded vector."""

    status: Literal["established", "limited", "not_established"]
    limitation_code: str = Field(min_length=1)
    vector_artifact_ref: ArtifactRef
    raw_cas_hash: Digest
    semantic_hash: Digest
    requested_query_context_ref: Digest
    aggregate_context_ref: ArtifactRef
    aggregate_context_content_hash: Digest
    bound_member_ref: ArtifactRef
    bound_member_content_hash: Digest
    candidate_occurrence_ref: ArtifactRef
    candidate_occurrence_content_hash: Digest
    verifier_provenance_ref: ArtifactRef
    predicate_class: Literal["independently_reconciled"]

    @classmethod
    def from_verified(
        cls,
        verified: VerifiedOpenWorldRiskVector,
        *,
        aggregate_context_content_hash: Digest,
        bound_member_content_hash: Digest,
        candidate_occurrence_content_hash: Digest,
    ) -> OpenWorldRiskPromotionGate:
        vector = verified.vector
        return cls(
            status=vector.status,
            limitation_code=vector.limitation_code,
            vector_artifact_ref=verified.vector_artifact_ref,
            raw_cas_hash=verified.raw_cas_hash,
            semantic_hash=verified.semantic_hash,
            requested_query_context_ref=verified.requested_query_context_ref,
            aggregate_context_ref=verified.aggregate_context_ref,
            aggregate_context_content_hash=aggregate_context_content_hash,
            bound_member_ref=verified.bound_member_ref,
            bound_member_content_hash=bound_member_content_hash,
            candidate_occurrence_ref=verified.candidate_occurrence_ref,
            candidate_occurrence_content_hash=candidate_occurrence_content_hash,
            verifier_provenance_ref=verified.verifier_provenance_ref,
            predicate_class="independently_reconciled",
        )


class _PersistedNegativeEpochQueryOwner:
    """Persist the exact no-admission result; it does not self-admit policy."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        provenance_ref: ArtifactRef,
        semantic_epoch_service: SemanticEpochService,
    ) -> None:
        self._store = store
        self._provenance_ref = provenance_ref
        self._semantic_epoch_service = semantic_epoch_service

    def resolve_for_promotion(
        self,
        *,
        design_problem_binding_ref: ArtifactRef,
        candidate: PromotionCandidateIdentity,
    ) -> EpochPromotionQueryEvidence:
        query = promotion_epoch_query(
            design_problem_binding_ref=design_problem_binding_ref,
            candidate=candidate,
        )
        qualification = self._semantic_epoch_service.qualify_chronology_query(
            query=query,
        )
        if not isinstance(
            qualification,
            core_contracts.chronology.NativeChronologyPolicyResolutionFailed,
        ) or not isinstance(
            qualification.failure,
            core_contracts.chronology.PolicyAdmissionMissingFailure,
        ):
            raise ValueError("epoch_policy_missing_result_not_established")
        payload = PersistedEpochPromotionQueryStatement(
            schema_version=c4_profile("epoch_query_evidence").schema_name,
            design_problem_binding_ref=design_problem_binding_ref,
            candidate=candidate,
            qualification_result=qualification,
        )
        ref, semantic_hash, _ = _persist_model(
            store=self._store,
            value=payload,
            profile_record="epoch_query_evidence",
        )
        return EpochPromotionQueryEvidence(
            family="semantic_epoch",
            candidate=candidate,
            query_artifact_ref=ref,
            query_artifact_content_hash=semantic_hash,
            native_requested_query_context_ref=query.requested_query_context_ref,
            verifier_provenance_ref=self._provenance_ref,
            qualification_status=qualification.failure.status,
            qualification_failure_codes=(qualification.failure.code,),
            predicate_class="independently_reconciled",
        )


class _PersistedDeploymentQueryOwner:
    """Persist a selector only; it makes no positive deployment claim."""

    def __init__(self, *, store: ArtifactStore, provenance_ref: ArtifactRef) -> None:
        self._store = store
        self._provenance_ref = provenance_ref

    def resolve_for_promotion(
        self,
        *,
        design_problem_binding_ref: ArtifactRef,
        candidate: PromotionCandidateIdentity,
    ) -> DeploymentPromotionQueryEvidence:
        payload = {
            "schema_version": c4_profile("deployment_query_evidence").schema_name,
            "design_problem_binding_ref": design_problem_binding_ref.model_dump(mode="json"),
            "candidate": candidate.model_dump(mode="json"),
            "authority_purpose": "n9_promotion",
        }
        ref, semantic_hash, _ = _persist_model(
            store=self._store,
            value=payload,
            profile_record="deployment_query_evidence",
        )
        return DeploymentPromotionQueryEvidence(
            family="deployment_scope",
            candidate=candidate,
            query_artifact_ref=ref,
            query_artifact_content_hash=semantic_hash,
            native_requested_query_context_ref=_semantic_hash(
                "polisyos.promotion-query.deployment-scope.context.v1", payload
            ),
            verifier_provenance_ref=self._provenance_ref,
            predicate_class="independently_reconciled",
        )


def persist_and_verify_design_problem_snapshot(
    *, store: ArtifactStore, problem: DesignProblem
) -> tuple[ArtifactRef, Digest]:
    """Reuse the existing ``runtime.design_problem`` profile in every path."""

    raw = core_contracts.chronology._canonical_raw_bytes(problem.model_dump(mode="json"))
    ref = store.put_bytes(
        raw,
        ArtifactWriteOptions(kind="runtime.design_problem", media_type="application/json"),
    )
    report = store.verify(ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    if (
        not report.ok
        or store.get_bytes(ref.artifact_id) != raw
        or str(ref.artifact_id) != _raw_hash(raw)
        or manifest.kind != "runtime.design_problem"
        or manifest.media_type != "application/json"
    ):
        raise ValueError("runtime_design_problem_snapshot_readback_mismatch")
    return ref, _semantic_hash("runtime.design_problem", problem)


@dataclass(frozen=True, slots=True)
class PromotionRuntimeBatch:
    """One complete post-loop context and its freshly reloaded gates."""

    candidate_denominator: PersistedPromotionCandidateDenominator
    contexts: PersistedPromotionContextBatch
    gates_by_candidate_id: Mapping[str, OpenWorldRiskPromotionGate]


class PromotionRuntime:
    """Container-owned negative-path composition shared by direct/recursive/HTTP N9."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        completed_epoch_batches: (
            core_contracts.EpochValidityCompletedBatchEvidenceResolver | None
        ) = None,
    ) -> None:
        self.store = store
        self.verifier_provenance_ref = store.put_bytes(
            _VERIFIER_PROVENANCE_BYTES,
            ArtifactWriteOptions(
                kind="chronology.open_world_risk_verifier", media_type="text/plain"
            ),
        )
        self.candidates = ArtifactPromotionCandidateDenominatorOwner(artifacts=store)
        self.semantic_epoch_service = SemanticEpochService.for_unallocated_policy_query(
            artifact_store=store
        )
        context_verifier = ArtifactPromotionOwnerQueryContextRepository(artifacts=store)
        self.context_repository = ArtifactPromotionOwnerQueryContextRepository(
            artifacts=store,
            verifier=context_verifier,
        )
        self.context_authority = PromotionOwnerQueryContextAuthority(
            candidates=self.candidates,
            epoch_queries=_PersistedNegativeEpochQueryOwner(
                store=store,
                provenance_ref=self.verifier_provenance_ref,
                semantic_epoch_service=self.semantic_epoch_service,
            ),
            deployment_queries=_PersistedDeploymentQueryOwner(
                store=store, provenance_ref=self.verifier_provenance_ref
            ),
            artifacts=store,
            verifier_provenance_ref=self.verifier_provenance_ref,
        )
        self.vector_repository = OpenWorldRiskVectorArtifactRepository(store=store)
        self.vector_producer = OpenWorldRiskVectorProducer(
            owner_contexts=self.context_repository,
            manifests=BoundProblemDeclaredScopeManifestProvider(
                store=store, contexts=self.context_repository
            ),
            lifecycle_owner=NoDeploymentLifecycleOwner(),
            evidence_verifier=NoPositiveDeploymentScopeEvidenceVerifier(),
            artifacts=self.vector_repository,
            verifier_provenance_ref=self.verifier_provenance_ref,
        )
        self.open_world_authority = OpenWorldRiskPromotionAuthority(
            producer=self.vector_producer,
            resolver=OpenWorldRiskVectorArtifactRepository(store=store),
        )
        self.epoch_subject_authority = ArtifactEpochValidityPreN9SubjectAuthority(
            store=store,
            contexts=self.context_repository,
        )
        self.epoch_validity_gate = ArtifactEpochValidityAuthorityGate(
            store=store,
            contexts=self.context_repository,
            semantic_epoch_service=self.semantic_epoch_service,
        )
        self.epoch_n9_evidence_resolver = ArtifactEpochValidityN9EvidenceResolver(
            store=store,
            contexts=self.context_repository,
            verifier_provenance_ref=self.verifier_provenance_ref,
            completed_batches=completed_epoch_batches,
        )

    @property
    def resolver(self) -> OpenWorldRiskGenerationProjectionResolver:
        return self.open_world_authority.resolver

    def resolve_verified_epoch_query(
        self,
        *,
        bound_member_ref: ArtifactRef,
    ) -> EpochPromotionQueryEvidence | PromotionOwnerQueryContextNonReceipt:
        """Reload one member and return its independently verified epoch evidence."""

        try:
            member = self.context_repository.resolve_bound_member(bound_member_ref=bound_member_ref)
            aggregate = self.context_repository.resolve_verified(
                context_ref=member.statement.aggregate_context_ref
            )
            if isinstance(aggregate, PromotionOwnerQueryContextNonReceipt):
                return aggregate
            matches = tuple(
                row
                for row in aggregate.statement.ordered_candidate_contexts
                if row.candidate.occurrence_ref == member.statement.candidate_occurrence_ref
            )
            if len(matches) != 1:
                raise ValueError("promotion_query_context_binding_mismatch")
            return matches[0].epoch_query
        except (KeyError, OSError, TypeError, ValueError):
            return PromotionOwnerQueryContextNonReceipt(
                status="rejected",
                code="promotion_query_context_binding_mismatch",
            )

    def _prepare_completed_generation(
        self, *, problem: DesignProblem, summaries: Sequence[CandidateSummary]
    ) -> PromotionRuntimeBatch | PromotionOwnerQueryContextNonReceipt:
        candidate_ids = tuple(row.candidate_id for row in summaries)
        if len(candidate_ids) != len(set(candidate_ids)):
            return PromotionOwnerQueryContextNonReceipt(
                status="rejected",
                code="promotion_candidate_denominator_mismatch",
            )
        problem_ref, problem_hash = persist_and_verify_design_problem_snapshot(
            store=self.store, problem=problem
        )
        sealed = _seal_completed_generation_candidate_batch(
            artifacts=self.store,
            design_problem_ref=problem_ref,
            design_problem_content_hash=problem_hash,
            summaries=summaries,
        )
        denominator = self.candidates.freeze_completed_generation(completed_batch=sealed)
        if isinstance(denominator, PromotionOwnerQueryContextNonReceipt):
            return denominator
        contexts = self.context_authority.persist_for_promotion(
            denominator_ref=denominator.denominator_ref
        )
        if isinstance(contexts, PromotionOwnerQueryContextNonReceipt):
            return contexts
        gates: dict[str, OpenWorldRiskPromotionGate] = {}
        for bound in contexts.ordered_bound_members:
            verified = self.open_world_authority.prepare_verified_projection(
                bound_member_ref=bound.bound_member_ref
            )
            if not isinstance(verified, VerifiedOpenWorldRiskVector):
                return PromotionOwnerQueryContextNonReceipt(
                    status="not_established",
                    code="deployment_query_unresolved",
                )
            occurrence = self.context_repository.resolve_occurrence(
                occurrence_ref=bound.statement.candidate_occurrence_ref
            )
            gates[occurrence.candidate_id] = OpenWorldRiskPromotionGate.from_verified(
                verified,
                aggregate_context_content_hash=(contexts.aggregate_context.semantic_hash),
                bound_member_content_hash=bound.bound_member_content_hash,
                candidate_occurrence_content_hash=c4_semantic_digest(
                    "candidate_occurrence", occurrence
                ),
            )
        return PromotionRuntimeBatch(
            candidate_denominator=denominator,
            contexts=contexts,
            gates_by_candidate_id=gates,
        )

    def prepare_verified_gate(
        self,
        *,
        batch: PromotionRuntimeBatch,
        ordinal: int,
        summary: CandidateSummary,
    ) -> OpenWorldRiskPromotionGate | PromotionOwnerQueryContextNonReceipt:
        """Freshly reload one exact member and vector immediately before N9."""

        try:
            bound = batch.contexts.ordered_bound_members[ordinal]
            reloaded_bound = self.context_repository.resolve_bound_member(
                bound_member_ref=bound.bound_member_ref
            )
            occurrence = self.context_repository.resolve_occurrence(
                occurrence_ref=reloaded_bound.statement.candidate_occurrence_ref
            )
            if (
                reloaded_bound != bound
                or occurrence.ordinal != ordinal
                or occurrence.candidate_id != summary.candidate_id
                or occurrence.candidate_content_hash != summary.content_hash
                or occurrence.candidate_summary != summary
                or occurrence.candidate_summary_content_hash
                != promotion_candidate_summary_content_hash(summary)
            ):
                raise ValueError("promotion_candidate_binding_mismatch")
            verified = self.open_world_authority.prepare_verified_projection(
                bound_member_ref=bound.bound_member_ref
            )
            if not isinstance(verified, VerifiedOpenWorldRiskVector):
                raise ValueError("open_world_vector_unresolved")
            gate = OpenWorldRiskPromotionGate.from_verified(
                verified,
                aggregate_context_content_hash=(batch.contexts.aggregate_context.semantic_hash),
                bound_member_content_hash=bound.bound_member_content_hash,
                candidate_occurrence_content_hash=c4_semantic_digest(
                    "candidate_occurrence", occurrence
                ),
            )
            if gate != batch.gates_by_candidate_id.get(summary.candidate_id):
                raise ValueError("open_world_projection_binding_mismatch")
            return gate
        except (IndexError, KeyError, OSError, TypeError, ValueError):
            return PromotionOwnerQueryContextNonReceipt(
                status="rejected",
                code="promotion_query_context_binding_mismatch",
            )


__all__ = [
    "BoundProblemDeclaredScopeManifestProvider",
    "CompetentDeploymentScopeEvidence",
    "CompetentDeploymentScopeEvidenceVerifier",
    "DeclaredScopeComponent",
    "DeclaredScopeManifest",
    "DeploymentLifecycleQueryOwner",
    "DeploymentScopeQuery",
    "DeploymentScopeRoleResolution",
    "NoDeploymentLifecycleOwner",
    "OpenWorldRiskArtifactResolver",
    "OpenWorldRiskComponent",
    "OpenWorldRiskGenerationProjectionResolver",
    "OpenWorldRiskProductionNonReceipt",
    "OpenWorldRiskPromotionAuthority",
    "OpenWorldRiskPromotionGate",
    "OpenWorldRiskPublicLimitation",
    "OpenWorldRiskResolutionNonReceipt",
    "OpenWorldRiskVector",
    "OpenWorldRiskVectorArtifactRepository",
    "OpenWorldRiskVectorProducer",
    "PersistedOpenWorldRiskVector",
    "PromotionDeclaredScopeManifestProvider",
    "PromotionRuntime",
    "PromotionRuntimeBatch",
    "VerifiedDeploymentScopeEvidence",
    "VerifiedOpenWorldRiskVector",
    "persist_and_verify_design_problem_snapshot",
    "resolve_open_world_risk",
]
