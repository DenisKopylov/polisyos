"""Canonical owner input readers for first-execution epoch transitions.

CAS enumeration discovers candidates; exact native history establishes epoch
membership.  Certificate completeness comes from the canonical issuance owner.
Advisory bytes never establish a target owner's adjudicated action.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self

from pydantic import model_validator

from polisyos.core import artifacts
from polisyos.runtime.quality import epoch_validity_cascade as cascade

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.runtime.quality.semantic_epoch import (
        SemanticEpochHistoryRepository,
        SemanticEpochManifest,
    )

ArtifactRef = artifacts.ArtifactRef
Digest = cascade.Digest


class ResolvedEpochTransitionSource(cascade._StrictModel):
    """Exact native owner inputs selected for one fresh transition execution."""

    previous_epoch_manifest_ref: ArtifactRef
    current_epoch_production_receipt_ref: ArtifactRef
    previous_epoch_ref: Digest
    current_epoch_ref: Digest
    authority_purpose: str
    requested_query_context_ref: Digest


def _complete_artifact_refs(store: artifacts.ArtifactStore) -> tuple[ArtifactRef, ...]:
    identities = store.iter_artifact_ids()
    if len(identities) != len(set(map(str, identities))):
        raise ValueError("epoch_input_artifact_index_duplicate")
    refs = []
    for artifact_id in sorted(identities, key=str):
        manifest = store.get_manifest(artifact_id)
        if manifest.artifact_id != artifact_id:
            raise ValueError("epoch_input_artifact_index_mismatch")
        refs.append(
            ArtifactRef(artifact_id=artifact_id, kind=manifest.kind, media_type=manifest.media_type)
        )
    return tuple(refs)


class CanonicalEpochTransitionSourceResolver:
    """Derive a unique receipt/predecessor pair from complete existing owners."""

    def __init__(
        self,
        *,
        artifacts: artifacts.ArtifactStore,
        history: SemanticEpochHistoryRepository,
    ) -> None:
        self._artifacts = artifacts
        self._adapter = cascade.FileSemanticEpochTransitionHistoryAdapter(
            artifacts=artifacts, history=history
        )

    def resolve_transition_source(
        self,
        *,
        requested_query_context_ref: Digest,
        authority_purpose: str,
    ) -> ResolvedEpochTransitionSource:
        """Resolve every receipt candidate; refuse corrupt or ambiguous evidence."""

        candidates = []
        for ref in _complete_artifact_refs(self._artifacts):
            if ref.kind != "epoch.production_receipt":
                continue
            # Validate before filtering, so malformed same-kind records are not
            # quietly dropped from the purported complete source population.
            receipt = self._adapter._read_production_receipt(ref)
            manifest = self._artifacts.get_manifest(ref.artifact_id)
            if manifest.artifact_schema is not None or manifest.canon is not None:
                raise ValueError("epoch_transition_source_receipt_profile_mismatch")
            if receipt.requested_query_context_ref != requested_query_context_ref:
                continue
            if receipt.status not in {"appended", "no_change"}:
                continue
            if receipt.semantic_manifest_ref is None:
                raise ValueError("epoch_transition_source_positive_manifest_missing")
            current = self._adapter._read_semantic_manifest(receipt.semantic_manifest_ref)
            if current.authority_purpose != authority_purpose:
                continue
            if current.requested_query_context_ref != requested_query_context_ref:
                raise ValueError("epoch_transition_source_query_mismatch")
            entries = self._adapter._validate_scope_history(
                current=current, authority_purpose=authority_purpose
            )
            if len(current.predecessor_refs) != 1:
                raise ValueError("epoch_transition_source_predecessor_not_unique")
            previous_rows = [row for row in entries if row.epoch_ref == current.predecessor_refs[0]]
            if len(previous_rows) != 1:
                raise ValueError("epoch_transition_source_predecessor_not_unique")
            previous, checked_current = self._adapter.resolve_transition_manifests(
                previous_epoch_ref=previous_rows[0].manifest_ref,
                current_epoch_receipt_ref=ref,
                authority_purpose=authority_purpose,
            )
            candidates.append(
                ResolvedEpochTransitionSource(
                    previous_epoch_manifest_ref=previous_rows[0].manifest_ref,
                    current_epoch_production_receipt_ref=ref,
                    previous_epoch_ref=previous.epoch_ref,
                    current_epoch_ref=checked_current.epoch_ref,
                    authority_purpose=authority_purpose,
                    requested_query_context_ref=requested_query_context_ref,
                )
            )
        if len(candidates) != 1:
            raise ValueError("epoch_transition_source_absent_or_ambiguous")
        return candidates[0]

    def resolve_transition_manifests(
        self,
        source: ResolvedEpochTransitionSource,
    ) -> tuple[SemanticEpochManifest, SemanticEpochManifest]:
        """Reconcile a selected source against the actual native history again."""

        previous, current = self._adapter.resolve_transition_manifests(
            previous_epoch_ref=source.previous_epoch_manifest_ref,
            current_epoch_receipt_ref=source.current_epoch_production_receipt_ref,
            authority_purpose=source.authority_purpose,
        )
        if (
            previous.epoch_ref != source.previous_epoch_ref
            or current.epoch_ref != source.current_epoch_ref
            or current.requested_query_context_ref != source.requested_query_context_ref
        ):
            raise ValueError("epoch_native_source_binding_mismatch")
        return previous, current


class EpochCertificateIssuanceInventory(Protocol):
    """Canonical issuance owner; its complete durable index is the denominator."""

    def resolve_complete_epoch_dependencies(
        self,
        *,
        previous_epoch_ref: str,
        authority_purpose: str,
    ) -> cascade.EpochDependencyDenominatorReceipt: ...


class CanonicalEpochDependencyDenominatorProvider:
    """Freeze the actual issuance owner's complete previous-epoch population."""

    def __init__(
        self,
        *,
        issuance_owner: EpochCertificateIssuanceInventory,
        source: ResolvedEpochTransitionSource,
    ) -> None:
        self._owner = issuance_owner
        self._source = source
        self._frozen: cascade.EpochDependencyDenominatorReceipt | None = None

    def resolve_complete_epoch_dependencies(
        self,
        *,
        authority_purpose: str,
        requested_query_context_ref: Digest,
    ) -> cascade.EpochDependencyDenominatorReceipt:
        """Bind the transition query without filtering on the older issuance query."""

        if (
            authority_purpose != self._source.authority_purpose
            or requested_query_context_ref != self._source.requested_query_context_ref
        ):
            raise ValueError("epoch_dependency_source_context_mismatch")
        if self._frozen is None:
            receipt = cascade.EpochDependencyDenominatorReceipt.model_validate(
                self._owner.resolve_complete_epoch_dependencies(
                    previous_epoch_ref=self._source.previous_epoch_ref,
                    authority_purpose=authority_purpose,
                ).model_dump(mode="json")
            )
            if not receipt.certificate_bindings or not receipt.target_refs:
                raise ValueError("dependency_denominator_unresolved")
            if any(
                binding.epoch_ref != self._source.previous_epoch_ref
                or binding.authority_purpose != authority_purpose
                for binding in receipt.certificate_bindings
            ):
                raise ValueError("epoch_dependency_issuance_binding_mismatch")
            if any(
                edge.authority_purpose != authority_purpose
                for edge in receipt.dependency_graph.edges
            ):
                raise ValueError("epoch_dependency_edge_purpose_mismatch")
            self._frozen = receipt
        return self._frozen


class EpochOwnerDispositionEvidenceReader(Protocol):
    """Independent purpose-scoped target-owner admission, separate from inventory."""

    def resolve_admitted_owner_disposition(
        self,
        *,
        owner_evidence_ref: ArtifactRef,
        authority_purpose: str,
        requested_query_context_ref: Digest,
    ) -> cascade.OwnerAdjudicatedTargetDisposition: ...


class NativeEpochSemanticBasisDelta(cascade._StrictModel):
    """Exact semantic-value delta for owner-registered full-basis dependents.

    This is native computation evidence.  It is not an advisory event or an
    adjudicated action, and cannot cross those consumer boundaries by itself.
    """

    source: ResolvedEpochTransitionSource
    dependency_receipt_ref: ArtifactRef
    dependency_receipt_content_hash: Digest
    previous_semantic_basis_hash: Digest
    current_semantic_basis_hash: Digest
    affected_target_refs: tuple[ArtifactRef, ...]
    delta_content_hash: Digest

    @model_validator(mode="after")
    def _content_bound(self) -> Self:
        expected = cascade._semantic_hash(
            "polisyos.epoch.native-semantic-basis-delta.v1",
            self.model_dump(mode="json", exclude={"delta_content_hash"}),
        )
        if self.delta_content_hash != expected:
            raise ValueError("epoch_native_basis_delta_content_mismatch")
        return self


class NativeEpochSemanticBasisDeltaProvider:
    """Compute CB-C03A affectedness through actual full-manifest issuance edges."""

    def __init__(
        self,
        *,
        artifacts: artifacts.ArtifactStore,
        source_resolver: CanonicalEpochTransitionSourceResolver,
        dependency_inventory: CanonicalEpochDependencyDenominatorProvider,
    ) -> None:
        self._artifacts = artifacts
        self._sources = source_resolver
        self._dependencies = dependency_inventory

    def produce_and_persist(
        self,
        *,
        authority_purpose: str,
        requested_query_context_ref: Digest,
    ) -> ArtifactRef:
        """Bind owner semantic values and registered exact dependents before emission."""

        source = self._sources.resolve_transition_source(
            authority_purpose=authority_purpose,
            requested_query_context_ref=requested_query_context_ref,
        )
        previous, current = self._sources.resolve_transition_manifests(source)
        dependencies = self._dependencies.resolve_complete_epoch_dependencies(
            authority_purpose=authority_purpose,
            requested_query_context_ref=requested_query_context_ref,
        )
        if not dependencies.certificate_bindings or not dependencies.dependency_graph.edges:
            raise ValueError("epoch_native_full_basis_dependency_not_established")
        if any(
            edge.source_ref != source.previous_epoch_manifest_ref
            or edge.relation != "invalidates_issuance_basis"
            or edge.authority_purpose != authority_purpose
            for edge in dependencies.dependency_graph.edges
        ):
            raise ValueError("epoch_native_full_basis_dependency_not_established")
        if any(
            binding.epoch_ref != previous.epoch_ref
            or binding.authority_purpose != authority_purpose
            for binding in dependencies.certificate_bindings
        ):
            raise ValueError("epoch_native_full_basis_dependency_not_established")

        def semantic_values(manifest: SemanticEpochManifest) -> dict[str, object]:
            # These are the canonical owner's semantic values, rather than raw
            # native member hashes or the epoch identity's query/predecessor data.
            return {
                "boundary_semantic_hashes": manifest.boundary_semantic_hashes,
                "facet_semantic_hashes": manifest.facet_semantic_hashes,
            }

        previous_basis = cascade._semantic_hash(
            "polisyos.epoch.native-semantic-values.v1", semantic_values(previous)
        )
        current_basis = cascade._semantic_hash(
            "polisyos.epoch.native-semantic-values.v1", semantic_values(current)
        )
        changed = previous_basis != current_basis
        if not changed:
            # Equal semantic values do not establish that a different coordinate,
            # registry or an unknown future identity field is irrelevant.  Only
            # query/predecessor bookkeeping is exempt from this comparison.
            omitted = {"requested_query_context_ref", "predecessor_refs"}
            old_context = {
                key: value
                for key, value in previous.identity_payload().items()
                if key not in omitted
            }
            new_context = {
                key: value
                for key, value in current.identity_payload().items()
                if key not in omitted
            }
            if old_context != new_context:
                raise ValueError("epoch_native_basis_comparison_not_established")
        dependency_ref, _, _ = cascade._persist_model(
            store=self._artifacts,
            value=dependencies,
            kind="polisyos.epoch.transition_dependency_receipt",
        )
        payload = {
            "source": source,
            "dependency_receipt_ref": dependency_ref,
            "dependency_receipt_content_hash": str(dependency_ref.artifact_id),
            "previous_semantic_basis_hash": previous_basis,
            "current_semantic_basis_hash": current_basis,
            "affected_target_refs": dependencies.target_refs if changed else (),
        }
        delta = NativeEpochSemanticBasisDelta(
            **payload,
            delta_content_hash=cascade._semantic_hash(
                "polisyos.epoch.native-semantic-basis-delta.v1", payload
            ),
        )
        ref, _, _ = cascade._persist_model(
            store=self._artifacts,
            value=delta,
            kind="polisyos.epoch.native_semantic_basis_delta",
        )
        if self.resolve_exact(delta_ref=ref) != delta:
            raise ValueError("epoch_native_basis_delta_readback_mismatch")
        return ref

    def resolve_exact(self, *, delta_ref: ArtifactRef) -> NativeEpochSemanticBasisDelta:
        """Read frozen computation bytes; this does not admit an action or event."""

        delta = cascade._read_model(
            store=self._artifacts,
            ref=delta_ref,
            model=NativeEpochSemanticBasisDelta,
            kind="polisyos.epoch.native_semantic_basis_delta",
        )
        if not isinstance(delta, NativeEpochSemanticBasisDelta):
            raise ValueError("epoch_native_basis_delta_readback_mismatch")
        return delta


class CanonicalEpochPerturbationAdjudicationProvider:
    """Reconcile all persisted advisories with a configured admitting owner reader.

    An empty owner slot supplies no complete native perturbation basis.  The
    separate advisory reader remains available at candidate/review strength.
    A supplied owner reader is an admission port, not caller-authored DTOs.
    """

    def __init__(
        self,
        *,
        artifacts: artifacts.ArtifactStore,
        dependency_inventory: cascade.EpochDependencyDenominatorProvider,
        owner_admissions: cascade.EpochPerturbationAdjudicationProvider | None = None,
        owner_evidence: EpochOwnerDispositionEvidenceReader | None = None,
        native_basis: NativeEpochSemanticBasisDeltaProvider | None = None,
    ) -> None:
        self._artifacts = artifacts
        self._dependencies = dependency_inventory
        self._owners = owner_admissions
        self._owner_evidence = owner_evidence
        self._native_basis = native_basis

    def resolve_monitor_advisories(
        self,
        *,
        authority_purpose: str,
        requested_query_context_ref: Digest,
    ) -> tuple[cascade.AdvisoryPerturbationEvent, ...]:
        """Read persisted monitor signals without claiming native-basis completeness."""

        from polisyos.scientist import (
            GOVERNANCE_MONITOR_EVENT_KIND,
            resolve_governance_monitor_event,
        )

        dependencies = self._dependencies.resolve_complete_epoch_dependencies(
            authority_purpose=authority_purpose,
            requested_query_context_ref=requested_query_context_ref,
        )
        nodes = {
            cascade._artifact_ref_identity(ref)
            for edge in dependencies.dependency_graph.edges
            for ref in (edge.source_ref, edge.target_ref)
        }
        events: dict[tuple[str, str, str], cascade.AdvisoryPerturbationEvent] = {}
        refs = _complete_artifact_refs(self._artifacts)
        for ref in refs:
            if ref.kind == GOVERNANCE_MONITOR_EVENT_KIND:
                persisted = resolve_governance_monitor_event(self._artifacts, ref)
                if persisted.event.perturbation is None:
                    continue
                advisory = cascade.advisory_perturbation_from_monitor_event(persisted)
            elif ref.kind == cascade._ADVISORY_EVENT_KIND:
                advisory = cascade.resolve_advisory_perturbation_event(
                    store=self._artifacts, ref=ref
                )
                persisted = resolve_governance_monitor_event(self._artifacts, advisory.event_ref)
                if cascade.advisory_perturbation_from_monitor_event(persisted) != advisory:
                    raise ValueError("epoch_advisory_native_source_mismatch")
            else:
                continue
            if cascade._artifact_ref_identity(advisory.target_ref) not in nodes:
                continue
            if advisory.authority_purpose != authority_purpose:
                raise ValueError("epoch_advisory_authority_purpose_mismatch")
            key = cascade._artifact_ref_identity(advisory.event_ref)
            if key in events and events[key] != advisory:
                raise ValueError("epoch_advisory_native_source_conflict")
            events[key] = advisory
            cascade.persist_advisory_perturbation_event(
                store=self._artifacts, persisted_monitor_event=persisted
            )
        event_rows = tuple(
            sorted(
                events.values(),
                key=lambda row: (
                    cascade._artifact_ref_identity(row.event_ref),
                    cascade._artifact_ref_identity(row.target_ref),
                    row.authority_purpose,
                ),
            )
        )
        return event_rows

    def resolve_complete_owner_adjudications(
        self,
        *,
        authority_purpose: str,
        requested_query_context_ref: Digest,
    ) -> cascade.EpochPerturbationAdjudicationReceipt:
        """Require the native/target owners' complete independently resolved basis."""

        if self._native_basis is None:
            raise ValueError("epoch_native_perturbation_basis_not_established")
        delta_ref = self._native_basis.produce_and_persist(
            authority_purpose=authority_purpose,
            requested_query_context_ref=requested_query_context_ref,
        )
        delta = self._native_basis.resolve_exact(delta_ref=delta_ref)
        if delta.affected_target_refs:
            # EP-D04: the existing event union has no native semantic-basis-change
            # member.  Never retag this evidence as correction/legal_change.
            raise ValueError("epoch_native_semantic_change_event_carrier_not_established")
        dependencies = self._dependencies.resolve_complete_epoch_dependencies(
            authority_purpose=authority_purpose,
            requested_query_context_ref=requested_query_context_ref,
        )
        event_rows = self.resolve_monitor_advisories(
            authority_purpose=authority_purpose,
            requested_query_context_ref=requested_query_context_ref,
        )
        owners: tuple[cascade.OwnerAdjudicatedTargetDisposition, ...] = ()
        if self._owners is not None:
            admitted = cascade.EpochPerturbationAdjudicationReceipt.model_validate(
                self._owners.resolve_complete_owner_adjudications(
                    authority_purpose=authority_purpose,
                    requested_query_context_ref=requested_query_context_ref,
                ).model_dump(mode="json")
            )
            if admitted.advisory_events != event_rows:
                raise ValueError("epoch_adjudication_owner_event_denominator_mismatch")
            owners = admitted.owner_dispositions
            if owners and self._owner_evidence is None:
                raise ValueError("epoch_adjudication_independent_owner_reader_missing")
            for row in owners:
                if self._owner_evidence is None:
                    raise ValueError("epoch_adjudication_independent_owner_reader_missing")
                verified = self._owner_evidence.resolve_admitted_owner_disposition(
                    owner_evidence_ref=row.owner_evidence_ref,
                    authority_purpose=authority_purpose,
                    requested_query_context_ref=requested_query_context_ref,
                )
                if (
                    cascade.OwnerAdjudicatedTargetDisposition.model_validate(
                        verified.model_dump(mode="json")
                    )
                    != row
                ):
                    raise ValueError("epoch_adjudication_independent_owner_binding_mismatch")
                evidence = self._artifacts.get_bytes(row.owner_evidence_ref.artifact_id)
                manifest = self._artifacts.get_manifest(row.owner_evidence_ref.artifact_id)
                if (
                    not self._artifacts.verify(row.owner_evidence_ref.artifact_id).ok
                    or cascade._raw_hash(evidence) != row.owner_evidence_content_hash
                    or row.owner_evidence_content_hash != str(row.owner_evidence_ref.artifact_id)
                    or manifest.kind != row.owner_evidence_ref.kind
                    or manifest.media_type != row.owner_evidence_ref.media_type
                    or row.authority_purpose != authority_purpose
                ):
                    raise ValueError("epoch_adjudication_owner_evidence_mismatch")
        # This existing consumer validates graph reachability, mixed outcomes and
        # missing owners; a monitor severity never chooses an owner action.
        cascade.resolve_owner_target_dispositions(
            advisory_events=event_rows,
            owner_dispositions=owners,
            dependency_graph=dependencies.dependency_graph,
        )
        payload = {"advisory_events": event_rows, "owner_dispositions": owners}
        return cascade.EpochPerturbationAdjudicationReceipt(
            **payload,
            predicate_class="independently_reconciled",
            denominator_ref=cascade._semantic_hash(
                "polisyos.epoch.perturbation-adjudication-denominator.v1", payload
            ),
        )


class EpochTransitionProductionBridge:
    """Invoke the canonical producer before first admission of a requested ref."""

    def __init__(
        self,
        *,
        source_resolver: CanonicalEpochTransitionSourceResolver,
        producer_factory: Callable[
            [ResolvedEpochTransitionSource], cascade.EpochValidityTransitionProducer
        ],
    ) -> None:
        self._sources = source_resolver
        self._producer_factory = producer_factory

    def produce_for_requested_transition(
        self,
        *,
        transition_artifact_ref: ArtifactRef,
        requested_query_context_ref: Digest,
        authority_purpose: str,
    ) -> cascade.PersistedEpochValidityTransition | cascade.EpochTransitionSigningNonReceipt:
        """Treat the request ref as an expected output, never as producer authority."""

        try:
            source = self._sources.resolve_transition_source(
                requested_query_context_ref=requested_query_context_ref,
                authority_purpose=authority_purpose,
            )
            producer = self._producer_factory(source)
            result = producer.produce_and_persist(
                previous_epoch_ref=source.previous_epoch_manifest_ref,
                current_epoch_receipt_ref=source.current_epoch_production_receipt_ref,
                requested_query_context_ref=requested_query_context_ref,
                authority_purpose=authority_purpose,
            )
            if isinstance(result, cascade.EpochTransitionSigningNonReceipt):
                return result
            if result.transition_artifact_ref != transition_artifact_ref:
                raise ValueError("epoch_transition_requested_output_mismatch")
            return result
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return cascade.EpochTransitionSigningNonReceipt(
                status="not_established",
                code="epoch_transition_exact_evidence_unavailable",
                predicate_class="not_established",
            )
