from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts import chronology as chronology_contract
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    CatalogAcquisitionOverlay,
)
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.runtime.quality import chronology_qualification
from polisyos.runtime.quality import semantic_epoch as epoch
from polisyos.runtime.quality.acquisition_executor import (
    admit_acquisition_with_semantic_epoch,
)
from polisyos.runtime.quality.semantic_epoch_store import (
    FileSemanticEpochHistoryRepository,
)
from tests.unit.runtime.quality.test_acquisition_executor import _fixture


def _put(store: FileSystemCAS, payload: bytes, *, kind: str) -> ArtifactRef:
    return store.put_bytes(
        payload,
        PutOptions(kind=kind, media_type="application/vnd.polisyos.epoch+json"),
    )


def _digest(label: str) -> str:
    return epoch._sha256(label.encode())


def _query(store: FileSystemCAS) -> epoch.EpochResolutionQuery:
    scope_bytes = json.dumps(
        {"domain": "public-finance", "jurisdiction": "UA"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    scope = epoch.build_epoch_scope_identity(
        schema_profile="polisyos.epoch.test-scope.v1",
        identity_bytes=scope_bytes,
    )
    values = {
        "valid_effect": (b"2025-01-01", "epoch.coordinate.valid-date.v1"),
        "visibility_knowledge_cutoff": (
            b"2025-02-01T00:00:00Z",
            "epoch.coordinate.knowledge-time.v1",
        ),
        "purpose_admission_cutoff": (
            b"2025-02-02T00:00:00Z",
            "epoch.coordinate.admission-time.v1",
        ),
    }
    evidence: dict[str, tuple[ArtifactRef, str]] = {}
    for role, (payload, kind) in values.items():
        ref = _put(store, payload, kind=kind)
        evidence[role] = (
            ref,
            epoch_contract.native_coordinate_ref(
                family="epoch",
                role=role,
                schema_profile=kind,
                coordinate_bytes=payload,
            ),
        )
    context_ref = epoch_contract.epoch_query_context_ref(
        family="epoch",
        scope_bytes=scope_bytes,
        authority_purpose="publication",
        coordinate_refs=tuple(evidence[role][1] for role in values),
    )
    return epoch.EpochResolutionQuery(
        scope_identity=scope,
        authority_purpose="publication",
        valid_effect_coordinate_evidence_ref=evidence["valid_effect"][0],
        valid_effect_coordinate_ref=evidence["valid_effect"][1],
        visibility_knowledge_cutoff_evidence_ref=evidence["visibility_knowledge_cutoff"][0],
        visibility_knowledge_cutoff_ref=evidence["visibility_knowledge_cutoff"][1],
        purpose_admission_cutoff_evidence_ref=evidence["purpose_admission_cutoff"][0],
        purpose_admission_cutoff_ref=evidence["purpose_admission_cutoff"][1],
        requested_query_context_ref=context_ref,
    )


def _chronology_query() -> chronology_contract.NativeChronologyQuery:
    return chronology_contract.NativeChronologyQuery(
        domain=chronology_contract.ChronologyProofDomain(
            format=chronology_contract.FULL_PREFIX_FORMAT,
            profile=chronology_contract.FULL_PREFIX_PROFILE,
            proof_domain="semantic-epoch",
            family="epoch",
            scope_ref=_digest("query-only-scope"),
            authority_purpose="n9_promotion",
        ),
        requested_cutoff_ref=_digest("query-only-cutoff"),
        requested_query_context_ref=_digest("query-only-context"),
    )


class _ResolvedLexAdapter:
    owner_kind = "lex_amendment_window"

    def __init__(self, store: FileSystemCAS) -> None:
        self._store = store

    def resolve_complete_batch(
        self,
        *,
        registration: epoch.EpochBoundarySourceRegistration,
        owner_query: object,
        candidate_refs: tuple[ArtifactRef, ...] = (),
    ) -> epoch.EpochBoundaryOwnerBatch:
        del candidate_refs
        assert isinstance(owner_query, epoch_contract.LegalAmendmentWindowResolutionQuery)
        native = _put(self._store, b"native-amendment", kind="epoch.test.native-amendment")
        snapshot = _put(self._store, b"owner-snapshot", kind="epoch.test.owner-snapshot")
        denominator = _put(
            self._store,
            b"owner-denominator",
            kind="epoch.test.owner-denominator",
        )
        assessments = (
            epoch.EpochBoundaryAssessment(
                native_member_ref=native,
                native_member_content_hash=str(native.artifact_id),
                semantic_value_hash=_digest("amendment-semantic-value"),
                disposition="applicable",
                failure_code=None,
            ),
        )
        return epoch.EpochBoundaryOwnerBatch(
            registration_id=registration.registration_id,
            owner_kind=registration.owner_kind,
            owner_source_ref=registration.owner_source_ref,
            opaque_scope_binding_ref=registration.opaque_scope_binding_ref,
            requested_query_context_ref=owner_query.requested_query_context_ref,
            owner_source_snapshot_ref=snapshot,
            owner_source_snapshot_content_hash=str(snapshot.artifact_id),
            denominator_receipt_ref=denominator,
            denominator_receipt_content_hash=str(denominator.artifact_id),
            declared_member_count=1,
            assessments=assessments,
            denominator_hash=epoch._owner_batch_hash(
                registration_id=registration.registration_id,
                owner_kind=registration.owner_kind,
                owner_source_ref=registration.owner_source_ref,
                opaque_scope_binding_ref=registration.opaque_scope_binding_ref,
                requested_query_context_ref=owner_query.requested_query_context_ref,
                assessments=assessments,
            ),
            status="resolved",
            failure_codes=(),
            predicate_class="independently_reconciled",
        )


class _ResolvedFacetProvider:
    def __init__(self, store: FileSystemCAS) -> None:
        self._store = store

    def resolve_all(
        self,
        *,
        registry: epoch.SemanticFacetRegistry,
        owner_batches: tuple[epoch.EpochBoundaryOwnerBatch, ...],
        query: epoch.EpochResolutionQuery,
    ) -> tuple[epoch.SemanticFacetValue, ...]:
        del owner_batches, query
        source = _put(self._store, b"facet-value", kind="epoch.test.facet")
        return tuple(
            epoch.SemanticFacetValue(
                facet_id=row.facet_id,
                source_record_ref=source,
                source_record_content_hash=str(source.artifact_id),
                semantic_value_hash=_digest("facet-semantic-value"),
                annotation_hash=_digest("facet-annotation"),
                status="resolved",
                failure_code=None,
            )
            for row in registry.registrations
        )


class _RecordingBoundaryAdapter:
    def __init__(
        self,
        *,
        owner_kind: epoch.BoundaryOwnerKind,
        store: FileSystemCAS,
        query: epoch.EpochResolutionQuery,
    ) -> None:
        self.owner_kind = owner_kind
        self._store = store
        self._query = query
        self.calls: list[tuple[str, tuple[ArtifactRef, ...]]] = []

    def resolve_complete_batch(
        self,
        *,
        registration: epoch.EpochBoundarySourceRegistration,
        owner_query: object,
        candidate_refs: tuple[ArtifactRef, ...] = (),
    ) -> epoch.EpochBoundaryOwnerBatch:
        assert owner_query.requested_query_context_ref == (self._query.requested_query_context_ref)
        self.calls.append((registration.registration_id, candidate_refs))
        return _batch(
            self._store,
            registration=registration,
            query=self._query,
            semantic_label=f"semantic:{registration.registration_id}",
        )


class _RecordingFacetProvider(_ResolvedFacetProvider):
    def __init__(self, store: FileSystemCAS) -> None:
        super().__init__(store)
        self.owner_batch_ids: tuple[str, ...] = ()
        self.registry_ids: tuple[str, ...] = ()

    def resolve_all(
        self,
        *,
        registry: epoch.SemanticFacetRegistry,
        owner_batches: tuple[epoch.EpochBoundaryOwnerBatch, ...],
        query: epoch.EpochResolutionQuery,
    ) -> tuple[epoch.SemanticFacetValue, ...]:
        self.owner_batch_ids = tuple(row.registration_id for row in owner_batches)
        self.registry_ids = tuple(row.facet_id for row in registry.registrations)
        return super().resolve_all(
            registry=registry,
            owner_batches=owner_batches,
            query=query,
        )


def _three_owner_service(
    tmp_path: Any,
) -> tuple[
    epoch.SemanticEpochService,
    epoch.EpochResolutionQuery,
    tuple[_RecordingBoundaryAdapter, ...],
    _RecordingFacetProvider,
]:
    store = FileSystemCAS(tmp_path / "cas")
    query = _query(store)
    registrations = (
        epoch.EpochBoundarySourceRegistration(
            registration_id="all-l5",
            owner_kind="l5_schema_regime",
            owner_source_ref=_digest("l5-owner"),
            opaque_scope_binding_ref=_digest("l5-scope"),
        ),
        epoch.EpochBoundarySourceRegistration(
            registration_id="all-lex",
            owner_kind="lex_amendment_window",
            owner_source_ref=_digest("lex-owner"),
            opaque_scope_binding_ref=_digest("lex-scope"),
        ),
        epoch.EpochBoundarySourceRegistration(
            registration_id="all-acquisition",
            owner_kind="catalog_acquisition",
            owner_source_ref=_digest("acquisition-owner"),
            opaque_scope_binding_ref=_digest("acquisition-scope"),
        ),
        epoch.EpochBoundarySourceRegistration(
            registration_id="second-lex-registration",
            owner_kind="lex_amendment_window",
            owner_source_ref=_digest("lex-owner-2"),
            opaque_scope_binding_ref=_digest("lex-scope-2"),
        ),
    )
    adapters = tuple(
        _RecordingBoundaryAdapter(owner_kind=kind, store=store, query=query)
        for kind in (
            "l5_schema_regime",
            "lex_amendment_window",
            "catalog_acquisition",
        )
    )
    facet_provider = _RecordingFacetProvider(store)
    history = FileSemanticEpochHistoryRepository(
        root=tmp_path / "history",
        artifacts=store,
    )
    service = epoch.SemanticEpochService(
        boundary_registry=epoch.build_boundary_registry(registrations),
        boundary_adapters={adapter.owner_kind: adapter for adapter in adapters},
        facet_registry=_facet_registry(),
        facet_provider=facet_provider,
        history=history,
        artifact_store=store,
        qualification_consumer=(
            chronology_qualification.QualificationConsumer.from_unallocated_policy_authority()
        ),
        chronology_adapter=(
            epoch.SemanticEpochQualificationAdapter.from_unallocated_policy_authority(
                history=history,
                artifacts=store,
            )
        ),
    )
    return service, query, adapters, facet_provider


def _registration(label: str = "all-amendments") -> epoch.EpochBoundarySourceRegistration:
    return epoch.EpochBoundarySourceRegistration(
        registration_id=label,
        owner_kind="lex_amendment_window",
        owner_source_ref=_digest(f"owner:{label}"),
        opaque_scope_binding_ref=_digest(f"scope:{label}"),
    )


def _facet_registry() -> epoch.SemanticFacetRegistry:
    return epoch.build_facet_registry(
        (
            epoch.SemanticFacetRegistration(
                facet_id="legal-semantics",
                source_binding_ref=_digest("legal-semantics-source"),
            ),
        )
    )


def _facet_value(
    store: FileSystemCAS,
    *,
    semantic_label: str = "facet-semantic-value",
    annotation_label: str = "facet-annotation",
) -> epoch.SemanticFacetValue:
    source = _put(store, b"facet-source", kind="epoch.test.facet-source")
    return epoch.SemanticFacetValue(
        facet_id="legal-semantics",
        source_record_ref=source,
        source_record_content_hash=str(source.artifact_id),
        semantic_value_hash=_digest(semantic_label),
        annotation_hash=_digest(annotation_label),
        status="resolved",
        failure_code=None,
    )


def _batch(
    store: FileSystemCAS,
    *,
    registration: epoch.EpochBoundarySourceRegistration,
    query: epoch.EpochResolutionQuery,
    semantic_label: str,
    failure_code: str | None = None,
) -> epoch.EpochBoundaryOwnerBatch:
    native = _put(
        store,
        f"native:{registration.registration_id}:{semantic_label}".encode(),
        kind="epoch.test.native",
    )
    snapshot = _put(
        store,
        f"snapshot:{registration.registration_id}:{semantic_label}".encode(),
        kind="epoch.test.owner-snapshot",
    )
    denominator = _put(
        store,
        f"denominator:{registration.registration_id}:{semantic_label}".encode(),
        kind="epoch.test.owner-denominator",
    )
    supporting_roles = {
        "l5_schema_regime": ("scoped_projection",),
        "lex_amendment_window": (),
        "catalog_acquisition": (
            "native_membership",
            "semantic_projection_verification",
        ),
    }[registration.owner_kind]
    supporting_evidence = tuple(
        epoch.EpochOwnerEvidenceBinding(
            role=role,
            artifact_ref=(
                ref := _put(
                    store,
                    f"evidence:{registration.registration_id}:{role}".encode(),
                    kind=f"epoch.test.{role}",
                )
            ),
            content_hash=str(ref.artifact_id),
        )
        for role in supporting_roles
    )
    assessment = epoch.EpochBoundaryAssessment(
        native_member_ref=native,
        native_member_content_hash=str(native.artifact_id),
        semantic_value_hash=None if failure_code else _digest(semantic_label),
        disposition="unresolved" if failure_code else "applicable",
        failure_code=failure_code,
    )
    assessments = (assessment,)
    return epoch.EpochBoundaryOwnerBatch(
        registration_id=registration.registration_id,
        owner_kind=registration.owner_kind,
        owner_source_ref=registration.owner_source_ref,
        opaque_scope_binding_ref=registration.opaque_scope_binding_ref,
        requested_query_context_ref=query.requested_query_context_ref,
        owner_source_snapshot_ref=snapshot,
        owner_source_snapshot_content_hash=str(snapshot.artifact_id),
        denominator_receipt_ref=denominator,
        denominator_receipt_content_hash=str(denominator.artifact_id),
        supporting_evidence=supporting_evidence,
        declared_member_count=1,
        assessments=assessments,
        denominator_hash=epoch._owner_batch_hash(
            registration_id=registration.registration_id,
            owner_kind=registration.owner_kind,
            owner_source_ref=registration.owner_source_ref,
            opaque_scope_binding_ref=registration.opaque_scope_binding_ref,
            requested_query_context_ref=query.requested_query_context_ref,
            assessments=assessments,
        ),
        status="unresolved" if failure_code else "resolved",
        failure_codes=() if failure_code is None else (failure_code,),
        predicate_class="independently_reconciled",
    )


def _resolve(
    store: FileSystemCAS,
    *,
    semantic_label: str,
    prior: tuple[epoch.SemanticEpochManifest, ...] = (),
    annotation_label: str = "facet-annotation",
    failure_code: str | None = None,
) -> epoch.EpochResolutionResult:
    query = _query(store)
    registration = _registration()
    return epoch.resolve_semantic_epoch(
        query=query,
        boundary_registry=epoch.build_boundary_registry((registration,)),
        owner_batches=(
            _batch(
                store,
                registration=registration,
                query=query,
                semantic_label=semantic_label,
                failure_code=failure_code,
            ),
        ),
        facet_registry=_facet_registry(),
        facet_values=(_facet_value(store, annotation_label=annotation_label),),
        prior_manifests=prior,
    )


def test_every_registered_boundary_source_reconciles_a_complete_native_receipt(
    tmp_path: Any,
) -> None:
    service, query, adapters, facet_provider = _three_owner_service(tmp_path)

    receipt = service.resolve_and_persist_epoch(query=query)

    assert receipt.failure_codes == ("policy_admission_missing",)
    assert tuple(call[0] for adapter in adapters for call in adapter.calls) == (
        "all-l5",
        "all-lex",
        "second-lex-registration",
        "all-acquisition",
    )
    assert facet_provider.owner_batch_ids == (
        "all-l5",
        "all-lex",
        "all-acquisition",
        "second-lex-registration",
    )
    # One persisted denominator per registration, plus the owner-kind-specific
    # projection evidence required by the contract: L5=1, Lex=0, acquisition=2.
    assert len(receipt.owner_denominator_receipt_refs) == 7


def test_native_receipt_subset_with_self_consistent_count_fails_source_snapshot() -> None:
    visibility = b"2025-02-01T00:00:00Z"
    admission = b"2025-02-02T00:00:00Z"
    valid = b"2025-01-01"
    query = epoch_contract.L5SchemaRegimeResolutionQuery(
        scope_identity_ref=_digest("l5-scope"),
        authority_purpose="publication",
        valid_effect_value=date.fromisoformat(valid.decode()),
        valid_effect_coordinate_schema_profile="native.valid.v1",
        valid_effect_coordinate_ref=epoch_contract.native_coordinate_ref(
            family="l5_schema_regime",
            role="valid_effect",
            schema_profile="native.valid.v1",
            coordinate_bytes=valid,
        ),
        visibility_knowledge_cutoff_schema_profile="native.knowledge.v1",
        visibility_knowledge_cutoff_bytes=visibility,
        visibility_knowledge_cutoff_ref=epoch_contract.native_coordinate_ref(
            family="l5_schema_regime",
            role="visibility_knowledge_cutoff",
            schema_profile="native.knowledge.v1",
            coordinate_bytes=visibility,
        ),
        purpose_admission_cutoff_schema_profile="native.admission.v1",
        purpose_admission_cutoff_bytes=admission,
        purpose_admission_cutoff_ref=epoch_contract.native_coordinate_ref(
            family="l5_schema_regime",
            role="purpose_admission_cutoff",
            schema_profile="native.admission.v1",
            coordinate_bytes=admission,
        ),
        requested_query_context_ref=_digest("l5-query"),
    )
    regime_rows = {
        "regime-a": {"schema_regime_id": "regime-a", "effective_start": "2020-01-01"},
        "regime-b": {"schema_regime_id": "regime-b", "effective_start": "2021-01-01"},
    }
    assessments = []
    for regime_id, row in regime_rows.items():
        raw = epoch_contract.canonical_epoch_bytes(row)
        digest = epoch._raw_cas_hash(raw)
        assessments.append(
            epoch_contract.L5SchemaRegimeAssessment(
                schema_regime_id=regime_id,
                regime_source_ref=ArtifactRef.model_validate(
                    {
                        "artifact_id": digest,
                        "kind": "l5.schema_regime",
                        "media_type": "application/json",
                    }
                ),
                regime_content_hash=digest,
                scope_relation=None,
                disposition="unresolved",
                failure_code="schema_regime_scope_missing",
            )
        )
    snapshot = epoch_contract.canonical_epoch_bytes(
        {
            "regimes": regime_rows,
            "scope_relations": [],
            "changepoints": [],
        }
    )
    snapshot_hash = epoch._raw_cas_hash(snapshot)
    registry_ref = ArtifactRef.model_validate(
        {
            "artifact_id": _digest("registry"),
            "kind": "l5.schema_regime_registry",
            "media_type": "application/json",
        }
    )
    subset = tuple(assessments[:1])
    denominator_hash = epoch._raw_cas_hash(
        epoch_contract.canonical_epoch_bytes(
            {
                "query": query.model_dump(mode="json"),
                "owner_source_snapshot_content_hash": snapshot_hash,
                "assessments": [row.model_dump(mode="json") for row in subset],
            }
        )
    )
    receipt = epoch_contract.L5SchemaRegimeDenominatorReceipt(
        query=query,
        owner_source_snapshot_ref=ArtifactRef.model_validate(
            {
                "artifact_id": snapshot_hash,
                "kind": "l5.schema_regime_owner_snapshot",
                "media_type": "application/json",
            }
        ),
        owner_source_snapshot_content_hash=snapshot_hash,
        regime_registry_ref=registry_ref,
        regime_registry_content_hash=str(registry_ref.artifact_id),
        scope_registry_ref=registry_ref.model_copy(
            update={"kind": "l5.schema_regime_scope_registry"}
        ),
        scope_registry_content_hash=str(registry_ref.artifact_id),
        declared_regime_count=1,
        assessments=subset,
        denominator_hash=denominator_hash,
        status="unresolved",
        failure_codes=("schema_regime_scope_missing",),
        predicate_class="independently_reconciled",
    )

    with pytest.raises(ValueError, match="not complete over its snapshot"):
        epoch._verify_l5_snapshot(payload=snapshot, receipt=receipt)


def test_service_collects_every_registered_provider_without_caller_batches(
    tmp_path: Any,
) -> None:
    service, query, adapters, facet_provider = _three_owner_service(tmp_path)

    receipt = service.resolve_and_persist_epoch(query=query)

    assert receipt.status == "not_established"
    assert tuple(candidate_refs for adapter in adapters for _, candidate_refs in adapter.calls) == (
        (),
        (),
        (),
        (),
    )
    assert facet_provider.registry_ids == ("legal-semantics",)
    assert set(facet_provider.owner_batch_ids) == {
        "all-l5",
        "all-lex",
        "all-acquisition",
        "second-lex-registration",
    }


def test_native_coordinate_bytes_ref_mismatch_rejects(tmp_path: Any) -> None:
    values = {
        "scope_identity_ref": _digest("scope"),
        "authority_purpose": "publication",
        "valid_effect_coordinate_schema_profile": "native.valid.v1",
        "valid_effect_coordinate_bytes": b"2025-01-01",
        "visibility_knowledge_cutoff_schema_profile": "native.knowledge.v1",
        "visibility_knowledge_cutoff_bytes": b"2025-02-01T00:00:00Z",
        "purpose_admission_cutoff_schema_profile": "native.admission.v1",
        "purpose_admission_cutoff_bytes": b"2025-02-02T00:00:00Z",
        "requested_query_context_ref": _digest("context"),
    }
    for role, field_prefix in (
        ("valid_effect", "valid_effect_coordinate"),
        ("visibility_knowledge_cutoff", "visibility_knowledge_cutoff"),
        ("purpose_admission_cutoff", "purpose_admission_cutoff"),
    ):
        profile = str(values[f"{field_prefix}_schema_profile"])
        raw = values[f"{field_prefix}_bytes"]
        assert isinstance(raw, bytes)
        values[f"{field_prefix}_ref"] = epoch_contract.native_coordinate_ref(
            family="catalog_acquisition",
            role=role,
            schema_profile=profile,
            coordinate_bytes=raw,
        )
    values["valid_effect_coordinate_ref"] = _digest("forged")

    with pytest.raises(ValidationError, match="bytes/ref mismatch"):
        epoch_contract.AcquisitionBoundaryResolutionQuery.model_validate(values)

    store = FileSystemCAS(tmp_path / "cas")
    query = _query(store)
    history = FileSemanticEpochHistoryRepository(
        root=tmp_path / "history",
        artifacts=store,
    )
    registration = _registration()
    service = epoch.SemanticEpochService(
        boundary_registry=epoch.build_boundary_registry((registration,)),
        boundary_adapters={"lex_amendment_window": _ResolvedLexAdapter(store)},
        facet_registry=_facet_registry(),
        facet_provider=_ResolvedFacetProvider(store),
        history=history,
        artifact_store=store,
        qualification_consumer=(
            chronology_qualification.QualificationConsumer.from_unallocated_policy_authority()
        ),
        chronology_adapter=(
            epoch.SemanticEpochQualificationAdapter.from_unallocated_policy_authority(
                history=history,
                artifacts=store,
            )
        ),
    )
    different_valid_bytes = _put(
        store,
        b"2026-01-01",
        kind=query.valid_effect_coordinate_evidence_ref.kind,
    )
    bytes_mismatch = service.resolve_and_persist_epoch(
        query=query.model_copy(
            update={"valid_effect_coordinate_evidence_ref": different_valid_bytes}
        )
    )
    context_mismatch = service.resolve_and_persist_epoch(
        query=query.model_copy(update={"requested_query_context_ref": _digest("forged-context")})
    )

    assert bytes_mismatch.failure_codes == ("epoch_scope_unresolved",)
    assert context_mismatch.failure_codes == ("epoch_scope_unresolved",)


def test_novel_domain_and_facet_rows_require_no_engine_change(tmp_path: Any) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    query = _query(store)
    registration = _registration("novel-domain-row")
    registry = epoch.build_boundary_registry((registration,))
    facets = epoch.build_facet_registry(
        (
            epoch.SemanticFacetRegistration(
                facet_id="novel-policy-facet",
                source_binding_ref=_digest("novel-policy-facet-source"),
            ),
        )
    )
    facet_source = _put(store, b"novel-facet", kind="epoch.test.novel-facet")
    result = epoch.resolve_semantic_epoch(
        query=query,
        boundary_registry=registry,
        owner_batches=(
            _batch(
                store,
                registration=registration,
                query=query,
                semantic_label="novel-domain-semantic",
            ),
        ),
        facet_registry=facets,
        facet_values=(
            epoch.SemanticFacetValue(
                facet_id="novel-policy-facet",
                source_record_ref=facet_source,
                source_record_content_hash=str(facet_source.artifact_id),
                semantic_value_hash=_digest("novel-facet-semantic"),
                annotation_hash=_digest("novel-facet-annotation"),
                status="resolved",
                failure_code=None,
            ),
        ),
        prior_manifests=(),
    )

    assert registry.registrations[0].registration_id == "novel-domain-row"
    assert facets.registrations[0].facet_id == "novel-policy-facet"
    assert result.manifest is not None
    assert result.reconciliation.owner_batches[0].registration_id == "novel-domain-row"
    assert result.reconciliation.facet_values[0].facet_id == "novel-policy-facet"


def test_novel_registration_reuses_owner_kind_without_provider_map_change(
    tmp_path: Any,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    query = _query(store)
    registrations = (_registration("first"), _registration("novel-second"))
    adapter = _ResolvedLexAdapter(store)
    history = FileSemanticEpochHistoryRepository(
        root=tmp_path / "history",
        artifacts=store,
    )
    service = epoch.SemanticEpochService(
        boundary_registry=epoch.build_boundary_registry(registrations),
        boundary_adapters={"lex_amendment_window": adapter},
        facet_registry=_facet_registry(),
        facet_provider=_ResolvedFacetProvider(store),
        history=history,
        artifact_store=store,
        qualification_consumer=(
            chronology_qualification.QualificationConsumer.from_unallocated_policy_authority()
        ),
        chronology_adapter=(
            epoch.SemanticEpochQualificationAdapter.from_unallocated_policy_authority(
                history=history,
                artifacts=store,
            )
        ),
    )

    receipt = service.resolve_and_persist_epoch(query=query)

    assert receipt.failure_codes == ("policy_admission_missing",)


def test_missing_or_novel_owner_kind_fails_closed(tmp_path: Any) -> None:
    with pytest.raises(ValidationError):
        epoch.EpochBoundarySourceRegistration.model_validate(
            {
                "registration_id": "novel-owner",
                "owner_kind": "novel_unappointed_owner",
                "owner_source_ref": _digest("owner"),
                "opaque_scope_binding_ref": _digest("scope"),
            }
        )
    store = FileSystemCAS(tmp_path / "cas")
    history = FileSemanticEpochHistoryRepository(
        root=tmp_path / "history",
        artifacts=store,
    )
    with pytest.raises(ValueError, match="adapter denominator mismatch"):
        epoch.SemanticEpochService(
            boundary_registry=epoch.build_boundary_registry((_registration(),)),
            boundary_adapters={},
            facet_registry=_facet_registry(),
            facet_provider=_ResolvedFacetProvider(store),
            history=history,
            artifact_store=store,
            qualification_consumer=(
                chronology_qualification.QualificationConsumer.from_unallocated_policy_authority()
            ),
            chronology_adapter=(
                epoch.SemanticEpochQualificationAdapter.from_unallocated_policy_authority(
                    history=history,
                    artifacts=store,
                )
            ),
        )


def test_scope_without_regime_or_amendment_is_epoch_scope_unresolved(
    tmp_path: Any,
) -> None:
    result = _resolve(
        FileSystemCAS(tmp_path / "cas"),
        semantic_label="missing-scope",
        failure_code="amendment_scope_unresolved",
    )

    assert result.status == "not_established"
    assert result.failure_codes == ("amendment_scope_unresolved",)
    assert result.manifest is None


def test_retroactive_reissue_at_same_bitemporal_coordinates_changes_epoch_ref(
    tmp_path: Any,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    old = _resolve(store, semantic_label="before-retroactive-reissue")
    assert old.manifest is not None
    new = _resolve(
        store,
        semantic_label="after-retroactive-reissue",
        prior=(old.manifest,),
    )

    assert new.manifest is not None
    assert new.manifest.epoch_ref != old.manifest.epoch_ref
    assert new.manifest.predecessor_refs == (old.manifest.epoch_ref,)


def test_incomparable_branches_fail_closed(tmp_path: Any) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    left = _resolve(store, semantic_label="left")
    right = _resolve(store, semantic_label="right")
    assert left.manifest is not None and right.manifest is not None

    result = _resolve(
        store,
        semantic_label="later",
        prior=(left.manifest, right.manifest),
    )

    assert result.status == "contested"
    assert result.failure_codes == ("epoch_branches_incomparable",)
    assert result.manifest is None


def test_unchanged_semantic_hash_rename_is_annotation_only(tmp_path: Any) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    before = _resolve(
        store,
        semantic_label="same-semantic-value",
        annotation_label="old-name",
    )
    after = _resolve(
        store,
        semantic_label="same-semantic-value",
        annotation_label="new-name",
    )
    assert before.manifest is not None and after.manifest is not None
    assert before.manifest.epoch_ref == after.manifest.epoch_ref


def test_new_semantic_candidate_changes_epoch(tmp_path: Any) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    first = _resolve(store, semantic_label="candidate-a")
    second = _resolve(store, semantic_label="candidate-b")
    assert first.manifest is not None and second.manifest is not None
    assert first.manifest.epoch_ref != second.manifest.epoch_ref


def test_semantic_epoch_service_invokes_policy_free_consumer_and_keeps_head_unmoved(
    tmp_path: Any,
    monkeypatch: Any,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    history = FileSemanticEpochHistoryRepository(
        root=tmp_path / "history",
        artifacts=store,
    )
    query = _query(store)
    registration = epoch.EpochBoundarySourceRegistration(
        registration_id="all-amendments",
        owner_kind="lex_amendment_window",
        owner_source_ref=_digest("lex-owner-source"),
        opaque_scope_binding_ref=_digest("lex-scope-binding"),
    )
    boundary_registry = epoch.build_boundary_registry((registration,))
    facet_registry = epoch.build_facet_registry(
        (
            epoch.SemanticFacetRegistration(
                facet_id="legal-semantics",
                source_binding_ref=_digest("legal-semantics-source"),
            ),
        )
    )
    adapter = epoch.SemanticEpochQualificationAdapter.from_unallocated_policy_authority(
        history=history,
        artifacts=store,
    )
    calls = {"for_history": 0, "reconcile_candidate": 0}
    original_for_history = epoch.SemanticEpochQualificationAdapter.for_history
    original_reconcile_candidate = epoch.SemanticEpochQualificationAdapter.reconcile_candidate

    def observed_for_history(
        self: epoch.SemanticEpochQualificationAdapter,
        staged: epoch.EpochScopeHistory,
    ) -> epoch.SemanticEpochQualificationAdapter:
        calls["for_history"] += 1
        return original_for_history(self, staged)

    def forbidden_reconciliation(
        self: epoch.SemanticEpochQualificationAdapter,
        request: object,
    ) -> Any:
        calls["reconcile_candidate"] += 1
        return original_reconcile_candidate(self, request)  # pragma: no cover

    monkeypatch.setattr(
        epoch.SemanticEpochQualificationAdapter,
        "for_history",
        observed_for_history,
    )
    monkeypatch.setattr(
        epoch.SemanticEpochQualificationAdapter,
        "reconcile_candidate",
        forbidden_reconciliation,
    )
    service = epoch.SemanticEpochService(
        boundary_registry=boundary_registry,
        boundary_adapters={"lex_amendment_window": _ResolvedLexAdapter(store)},
        facet_registry=facet_registry,
        facet_provider=_ResolvedFacetProvider(store),
        history=history,
        artifact_store=store,
        qualification_consumer=(
            chronology_qualification.QualificationConsumer.from_unallocated_policy_authority()
        ),
        chronology_adapter=adapter,
    )

    receipt = service.resolve_and_persist_epoch(query=query)

    assert isinstance(receipt, epoch.PersistedSemanticEpochProductionReceipt)
    assert receipt.status == "not_established"
    assert receipt.failure_codes == ("policy_admission_missing",)
    assert receipt.chronology_bundle_ref is None
    assert receipt.chronology_verification_ref is None
    assert calls == {"for_history": 1, "reconcile_candidate": 0}
    assert (
        history.resolve_scope_history(
            scope=query.scope_identity,
            authority_purpose=query.authority_purpose,
        ).entries
        == ()
    )


def test_production_acquisition_invokes_epoch_adapter_and_returns_policy_admission_missing(
    tmp_path: Any,
    monkeypatch: Any,
) -> None:
    _, store, authority, _, raw_ref = _fixture(tmp_path / "acquisition")
    overlay = CatalogAcquisitionOverlay(
        authority.baseline_path,
        tmp_path / "acquisition-overlay.duckdb",
    )
    overlay.initialize()
    history = FileSemanticEpochHistoryRepository(
        root=tmp_path / "history",
        artifacts=store,
    )
    query = _query(store)
    registration = epoch.EpochBoundarySourceRegistration(
        registration_id="catalog-native-history",
        owner_kind="catalog_acquisition",
        owner_source_ref=_digest("catalog-owner-source"),
        opaque_scope_binding_ref=_digest("catalog-scope-binding"),
    )
    boundary_registry = epoch.build_boundary_registry((registration,))
    facet_registry = epoch.build_facet_registry(
        (
            epoch.SemanticFacetRegistration(
                facet_id="catalog-semantics",
                source_binding_ref=_digest("catalog-facet-source"),
            ),
        )
    )
    chronology_adapter = epoch.SemanticEpochQualificationAdapter.from_unallocated_policy_authority(
        history=history,
        artifacts=store,
    )
    service = epoch.SemanticEpochService(
        boundary_registry=boundary_registry,
        boundary_adapters={
            "catalog_acquisition": epoch.CatalogAcquisitionEpochBoundaryOwnerAdapter(
                owner=overlay,
                artifacts=store,
            )
        },
        facet_registry=facet_registry,
        facet_provider=_ResolvedFacetProvider(store),
        history=history,
        artifact_store=store,
        qualification_consumer=(
            chronology_qualification.QualificationConsumer.from_unallocated_policy_authority()
        ),
        chronology_adapter=chronology_adapter,
    )
    activation_calls = 0
    original_activate = overlay.activate_semantic_epoch

    def forbidden_activation(**kwargs: object) -> object:
        nonlocal activation_calls
        activation_calls += 1
        return original_activate(**kwargs)  # pragma: no cover

    monkeypatch.setattr(overlay, "activate_semantic_epoch", forbidden_activation)

    receipt = admit_acquisition_with_semantic_epoch(
        epoch_id=1,
        raw_evidence_ref=raw_ref,
        artifact_store=store,
        authority=authority,
        overlay=overlay,
        epoch_service=service,
        epoch_query=query,
    )

    assert isinstance(receipt, epoch.PersistedSemanticEpochProductionReceipt)
    assert receipt.status == "not_established"
    assert receipt.failure_codes == ("policy_admission_missing",)
    assert activation_calls == 0
    assert (
        history.resolve_scope_history(
            scope=query.scope_identity,
            authority_purpose=query.authority_purpose,
        ).entries
        == ()
    )
    con = __import__("duckdb").connect(str(overlay.overlay_path), read_only=True)
    try:
        assert con.execute("SELECT epoch_activation_state FROM acquisition_epochs").fetchall() == [
            ("pending_epoch_activation",)
        ]
    finally:
        con.close()
    read_session = catalog_read_api.open_catalog_read_session(
        authority.baseline_path,
        overlay_path=overlay.overlay_path,
    )
    try:
        assert read_session.execute("SELECT count(*) FROM ds_observations").fetchone()[0] == 0
    finally:
        read_session.close()
        overlay.close()


def test_query_only_semantic_epoch_service_cannot_resolve_owner_history(
    tmp_path: Any,
) -> None:
    """The procedural negative never fabricates an empty resolution owner."""

    store = FileSystemCAS(tmp_path / "cas")
    service = epoch.SemanticEpochService.for_unallocated_policy_query(artifact_store=store)

    qualification = service.qualify_chronology_query(query=_chronology_query())

    assert isinstance(
        qualification,
        chronology_contract.NativeChronologyPolicyResolutionFailed,
    )
    assert isinstance(
        qualification.failure,
        chronology_contract.PolicyAdmissionMissingFailure,
    )
    with pytest.raises(
        RuntimeError,
        match="epoch_resolution_owner_components_not_established",
    ):
        service.resolve_and_persist_epoch(query=_query(store))
