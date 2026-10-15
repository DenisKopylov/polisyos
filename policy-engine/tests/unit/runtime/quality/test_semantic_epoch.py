from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core import contracts
from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.artifacts.manifest import ArtifactID, ArtifactRef
from polisyos.core.contracts import chronology as chronology_contract
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    CatalogAcquisitionOverlay,
)
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.fabric.connectors.cache import ConnectorCacheStore, TTLPolicy
from polisyos.ir.connectors import (
    DataVersion,
    FetchRequest,
    FetchResult,
    QualityTier,
    VersionStrategy,
)
from polisyos.runtime.quality import chronology_qualification, substrate_registry
from polisyos.runtime.quality import semantic_epoch as epoch
from polisyos.runtime.quality.acquisition_executor import (
    admit_acquisition_with_semantic_epoch,
)
from polisyos.runtime.quality.semantic_epoch_store import (
    FileSemanticEpochHistoryRepository,
)
from tests._helpers.semantic_epoch_native import _fixture


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
        epoch._verify_l5_snapshot(payload=snapshot, receipt=receipt, expected_query=query)


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
    facet_payload = epoch_contract.canonical_epoch_bytes({"semantic_value": "catalog-semantics"})
    facet_ref = store.put_bytes(
        facet_payload,
        PutOptions(
            kind="epoch.semantic_facet_source.v1",
            media_type="application/vnd.polisyos.epoch+json",
            canon=epoch_contract.epoch_canon_info(),
        ),
        return_selected_profile=True,
    )
    facet_registry = epoch.build_facet_registry(
        (
            epoch.SemanticFacetRegistration(
                facet_id="catalog-semantics",
                source_binding_ref=str(facet_ref.artifact_id),
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
        facet_provider=epoch.ArtifactSemanticFacetProvider(
            artifacts=store, source_refs={str(facet_ref.artifact_id): facet_ref}
        ),
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


def test_selected_epoch_reference_graph_resolves_manifest_profile_and_owner_view(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "selected-reference-graph-cas")
    kind = "epoch.acquisition_semantic_boundary_candidate"
    value = {"candidate": "controlled"}
    canonical = epoch_contract.canonical_epoch_bytes(value)
    payload = len(canonical).to_bytes(8, "big") + canonical
    selected = store.put_bytes(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/vnd.polisyos.epoch+json",
            canon=epoch_contract.epoch_canon_info(),
        ),
        return_selected_profile=True,
    )
    owner_ref = ArtifactRef.model_validate(
        selected.model_dump(mode="json") | {"manifest_profile_sha256": None}
    )
    selected_graph = {"candidate_ref": selected}
    owner_projection = {"candidate_ref": owner_ref}

    selected_profiles = epoch._resolve_selected_reference_graph(store, selected_graph)
    assert selected_profiles is not None
    assert contracts.acquisition_artifact_canon_info(kind) == epoch_contract.epoch_canon_info()
    assert epoch._owner_reference_graph_matches_selected(
        selected_profiles, owner_projection, store=store
    )
    assert epoch._selected_ref_graph_matches_owner_projection(selected_graph, owner_projection)

    profileless_selection = {"candidate_ref": owner_ref}
    assert epoch._resolve_selected_reference_graph(store, profileless_selection) is None
    assert not epoch._selected_ref_graph_matches_owner_projection(
        profileless_selection, owner_projection
    )

    alternate = store.put_bytes(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/vnd.polisyos.epoch+json",
            canon=epoch_contract.external_epoch_statement_canon_info(),
        ),
        return_selected_profile=True,
    )
    assert alternate.artifact_id == selected.artifact_id
    assert alternate.manifest_profile_sha256 != selected.manifest_profile_sha256
    assert epoch._raw_cas_hash(store.get_bytes(alternate)) == str(selected.artifact_id)
    assert (str(alternate.artifact_id), alternate.kind, alternate.media_type) == (
        str(selected.artifact_id),
        selected.kind,
        selected.media_type,
    )
    assert epoch._resolve_selected_reference_graph(store, {"candidate_ref": alternate}) is None
    assert not epoch._selected_ref_graph_matches_owner_projection(
        selected_graph, {"candidate_ref": alternate}
    )

    forged_profile = ArtifactRef.model_validate(
        selected.model_dump(mode="json") | {"manifest_profile_sha256": "sha256:" + "0" * 64}
    )
    assert epoch._resolve_selected_reference_graph(store, {"candidate_ref": forged_profile}) is None
    assert not epoch._owner_reference_graph_matches_selected(
        selected_profiles, {"candidate_ref": forged_profile}, store=store
    )


def test_selected_epoch_reference_graph_resolves_transitive_owner_projections_and_refuses_gaps(
    tmp_path: Path,
) -> None:
    """Resolve every nested ref to a verified current CAS view or refuse the graph."""
    store = FileSystemCAS(tmp_path / "transitive-reference-graph-cas")
    media_type = "application/vnd.polisyos.epoch+json"

    def put_mapping(kind: str, value: dict[str, object], *, canon=None) -> ArtifactRef:
        canonical = epoch_contract.canonical_epoch_bytes(value)
        payload = len(canonical).to_bytes(8, "big") + canonical
        return store.put_bytes(
            payload,
            PutOptions(
                kind=kind,
                media_type=media_type,
                canon=canon or epoch_contract.epoch_canon_info(),
            ),
            return_selected_profile=True,
        )

    def profileless(ref: ArtifactRef) -> ArtifactRef:
        return ArtifactRef.model_validate(
            ref.model_dump(mode="json") | {"manifest_profile_sha256": None}
        )

    deep_snapshot = put_mapping("epoch.acquisition_owner_snapshot", {"owner": "deep"})
    nested_snapshot = put_mapping(
        "epoch.acquisition_owner_snapshot",
        {
            "owner": "nested",
            "source_snapshot_ref": profileless(deep_snapshot).model_dump(mode="json"),
        },
    )
    root_ref = put_mapping(
        "epoch.acquisition_semantic_boundary_candidate",
        {"owner_source_snapshot_ref": profileless(nested_snapshot).model_dump(mode="json")},
    )
    selected_graph = {"candidate_ref": root_ref}
    selected_profiles = epoch._resolve_selected_reference_graph(store, selected_graph)
    assert selected_profiles is not None
    for ref in (nested_snapshot, deep_snapshot):
        identity = (str(ref.artifact_id), ref.kind, ref.media_type)
        assert selected_profiles[identity] == ref.manifest_profile_sha256
    assert epoch._owner_reference_graph_matches_selected(
        selected_profiles,
        {"owner_source_snapshot_ref": profileless(nested_snapshot)},
        store=store,
    )

    # An owner-only profileless leaf may resolve to a real default manifest, but
    # cannot pass merely because its identifier and kind are well-shaped.
    owner_only_snapshot = put_mapping(
        "epoch.acquisition_owner_snapshot", {"owner": "outside-selected-root"}
    )
    assert epoch._owner_reference_graph_matches_selected(
        selected_profiles,
        {"owner_source_snapshot_ref": profileless(owner_only_snapshot)},
        store=store,
    )
    absent = ArtifactRef(
        artifact_id=epoch.ArtifactID.model_validate(epoch._raw_cas_hash(b"absent snapshot")),
        kind="epoch.acquisition_owner_snapshot",
        media_type=media_type,
    )
    assert not epoch._owner_reference_graph_matches_selected(
        selected_profiles, {"owner_source_snapshot_ref": absent}, store=store
    )
    unknown_kind = ArtifactRef(
        artifact_id=owner_only_snapshot.artifact_id,
        kind="epoch.unregistered_owner_snapshot",
        media_type=media_type,
    )
    assert not epoch._owner_reference_graph_matches_selected(
        selected_profiles,
        {"owner_source_snapshot_ref": unknown_kind},
        store=store,
    )

    wrong_profile = ArtifactRef.model_validate(
        owner_only_snapshot.model_dump(mode="json")
        | {"manifest_profile_sha256": "sha256:" + "0" * 64}
    )
    assert not epoch._owner_reference_graph_matches_selected(
        selected_profiles,
        {"owner_source_snapshot_ref": wrong_profile},
        store=store,
    )

    other_canon = put_mapping(
        "epoch.acquisition_owner_snapshot",
        {"owner": "wrong-canon"},
        canon=epoch_contract.external_epoch_statement_canon_info(),
    )
    assert not epoch._owner_reference_graph_matches_selected(
        selected_profiles,
        {"owner_source_snapshot_ref": other_canon},
        store=store,
    )

    missing_nested = ArtifactRef(
        artifact_id=epoch.ArtifactID.model_validate(epoch._raw_cas_hash(b"missing nested")),
        kind="epoch.acquisition_owner_snapshot",
        media_type=media_type,
        manifest_profile_sha256="sha256:" + "1" * 64,
    )
    selected_with_missing_nested = put_mapping(
        "epoch.acquisition_semantic_boundary_candidate",
        {"owner_source_snapshot_ref": missing_nested.model_dump(mode="json")},
    )
    assert (
        epoch._resolve_selected_reference_graph(
            store, {"candidate_ref": selected_with_missing_nested}
        )
        is None
    )

    alternate_canon = put_mapping(
        "epoch.acquisition_owner_snapshot",
        {"owner": "same bytes, another canon"},
        canon=epoch_contract.external_epoch_statement_canon_info(),
    )
    selected_with_alternate_canon = put_mapping(
        "epoch.acquisition_semantic_boundary_candidate",
        {"owner_source_snapshot_ref": alternate_canon.model_dump(mode="json")},
    )
    assert (
        epoch._resolve_selected_reference_graph(
            store, {"candidate_ref": selected_with_alternate_canon}
        )
        is None
    )

    malformed_nested = put_mapping(
        "epoch.acquisition_semantic_boundary_candidate",
        {
            "owner_source_snapshot_ref": {
                "artifact_id": str(owner_only_snapshot.artifact_id),
                "kind": owner_only_snapshot.kind,
                "media_type": owner_only_snapshot.media_type,
                "manifest_profile_sha256": "not-a-profile",
            }
        },
    )
    assert (
        epoch._resolve_selected_reference_graph(store, {"candidate_ref": malformed_nested}) is None
    )

    class CorruptingStore:
        def __init__(self, delegate: FileSystemCAS, corrupted_id: str) -> None:
            self._delegate = delegate
            self._corrupted_id = corrupted_id

        def __getattr__(self, name: str) -> Any:
            return getattr(self._delegate, name)

        def get_bytes(self, selector: ArtifactID | ArtifactRef) -> bytes:
            payload = self._delegate.get_bytes(selector)
            if str(getattr(selector, "artifact_id", selector)) == self._corrupted_id:
                return payload + b"corruption"
            return payload

    corrupting_store = CorruptingStore(store, str(root_ref.artifact_id))
    assert epoch._resolve_selected_reference_graph(corrupting_store, selected_graph) is None


def test_selected_reference_graph_resolves_actual_admitted_and_persisted_candidate(
    tmp_path: Path,
) -> None:
    """Digest-only DTO projections coexist with the persisted typed query."""
    from tests._helpers.semantic_epoch_native import _real_epoch_scenario

    scenario = _real_epoch_scenario(tmp_path)
    admitted_ref = scenario.overlay.emit_admitted_boundary_evidence(
        query=scenario.service.acquisition_owner_query(query=scenario.query),
        passport=scenario.passport,
        prepared_epoch=scenario.prepared,
        boundary_candidate=scenario.candidate,
        pending_receipt=scenario.pending,
        artifact_store=scenario.store,
    )
    admitted_mapping = epoch_contract.load_verified_epoch_statement(
        store=scenario.store,
        ref=admitted_ref,
        expected_kind="epoch.admitted_acquisition_boundary_evidence",
    )
    admitted = epoch_contract.AdmittedAcquisitionBoundaryEvidence.model_validate(admitted_mapping)
    candidate_mapping = epoch_contract.load_verified_epoch_statement(
        store=scenario.store,
        ref=admitted.semantic_candidate_ref,
        expected_kind="epoch.acquisition_semantic_boundary_candidate",
    )
    candidate = epoch_contract.AcquisitionSemanticBoundaryCandidateStatement.model_validate(
        candidate_mapping
    )
    assert epoch._epoch_coordinate_bindings(candidate) == {}
    assert epoch._epoch_coordinate_bindings(admitted.semantic_epoch_stamp) == {}
    selected_profiles = epoch._resolve_selected_reference_graph(scenario.store, admitted)
    assert selected_profiles is not None
    selected_kinds = {kind for _, kind, _ in selected_profiles}
    assert {
        "epoch.semantic_facet_source.v1",
        "epoch.coordinate.valid_effect.v1",
        "epoch.coordinate.visibility_knowledge_cutoff.v1",
        "epoch.coordinate.purpose_admission_cutoff.v1",
        "epoch.acquisition_owner_snapshot",
        "epoch.acquisition_native_membership",
        "epoch.acquisition_native_member",
        "epoch.acquisition_passport_snapshot",
        "epoch.acquisition_semantic_boundary_candidate",
        "epoch.acquisition_semantic_denominator_receipt",
        "epoch.acquisition_semantic_projection_verification_receipt",
        "epoch.acquisition_projection_verifier_provenance",
    } <= selected_kinds
    facet_receipt_mapping = epoch_contract.load_verified_epoch_statement(
        store=scenario.store,
        ref=admitted.semantic_epoch_stamp.facet_denominator_receipt_ref,
        expected_kind="epoch.facet_denominator_receipt",
    )
    facet_source_ref = ArtifactRef.model_validate(
        facet_receipt_mapping["values"][0]["source_record_ref"]
    )
    assert (
        epoch._resolve_selected_reference_graph(
            scenario.store, facet_source_ref.model_copy(update={"media_type": "application/json"})
        )
        is None
    )
    assert (
        epoch._resolve_selected_reference_graph(
            scenario.store,
            facet_source_ref.model_copy(update={"kind": "epoch.semantic_facet_source.v99"}),
        )
        is None
    )
    wrong_profile = "sha256:" + "0" * 64
    if wrong_profile == facet_source_ref.manifest_profile_sha256:
        wrong_profile = "sha256:" + "f" * 64
    assert (
        epoch._resolve_selected_reference_graph(
            scenario.store,
            facet_source_ref.model_copy(update={"manifest_profile_sha256": wrong_profile}),
        )
        is None
    )

    def select_query_refs(query: epoch.EpochResolutionQuery) -> epoch.EpochResolutionQuery:
        updates: dict[str, object] = {}
        for field in (
            "valid_effect_coordinate_evidence_ref",
            "visibility_knowledge_cutoff_evidence_ref",
            "purpose_admission_cutoff_evidence_ref",
        ):
            ref = getattr(query, field)
            manifest = scenario.store.get_manifest(ref)
            updates[field] = ref.model_copy(
                update={
                    "manifest_profile_sha256": epoch.artifacts.artifact_manifest_profile_sha256(
                        manifest
                    )
                }
            )
        return query.model_copy(update=updates)

    legacy_query = select_query_refs(_query(scenario.store))
    assert epoch._resolve_selected_reference_graph(scenario.store, legacy_query) is not None
    selected_query = select_query_refs(scenario.query)
    forged_digest = "sha256:" + "0" * 64
    forged_context = epoch_contract.epoch_query_context_ref(
        family="epoch",
        scope_bytes=selected_query.scope_identity.identity_bytes,
        authority_purpose=selected_query.authority_purpose,
        coordinate_refs=(
            forged_digest,
            selected_query.visibility_knowledge_cutoff_ref,
            selected_query.purpose_admission_cutoff_ref,
        ),
    )
    forged_query = selected_query.model_copy(
        update={
            "valid_effect_coordinate_ref": forged_digest,
            "requested_query_context_ref": forged_context,
        }
    )
    assert epoch._resolve_selected_reference_graph(scenario.store, forged_query) is None

    source_bytes = scenario.store.get_bytes(selected_query.valid_effect_coordinate_evidence_ref)
    unknown_kind = "epoch.coordinate.unregistered.v1"
    unknown_ref = scenario.store.put_bytes(
        source_bytes,
        PutOptions(
            kind=unknown_kind,
            media_type=selected_query.valid_effect_coordinate_evidence_ref.media_type,
        ),
        return_selected_profile=True,
    )
    unknown_digest = epoch_contract.native_coordinate_ref(
        family="epoch",
        role="valid_effect",
        schema_profile=unknown_kind,
        coordinate_bytes=source_bytes,
    )
    unknown_query = selected_query.model_copy(
        update={
            "valid_effect_coordinate_evidence_ref": unknown_ref,
            "valid_effect_coordinate_ref": unknown_digest,
            "requested_query_context_ref": epoch_contract.epoch_query_context_ref(
                family="epoch",
                scope_bytes=selected_query.scope_identity.identity_bytes,
                authority_purpose=selected_query.authority_purpose,
                coordinate_refs=(
                    unknown_digest,
                    selected_query.visibility_knowledge_cutoff_ref,
                    selected_query.purpose_admission_cutoff_ref,
                ),
            ),
        }
    )
    assert epoch._resolve_selected_reference_graph(scenario.store, unknown_query) is None


def test_connector_cache_graph_uses_real_serializer_media_without_pickle_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pickle

    import pandas as pd

    store = FileSystemCAS(tmp_path / "connector-cache-graph-cas")
    values = (
        ({"rows": [{"value": 1.25}]}, "application/json"),
        (pd.DataFrame({"value": [1.25]}), "application/parquet"),
        ("opaque-cache-value", "application/pickle"),
    )
    forbidden_calls: list[bool] = []

    def forbidden_loads(*args: object, **kwargs: object) -> object:
        del args, kwargs
        forbidden_calls.append(True)
        raise AssertionError("selected graph must never execute pickle payloads")

    monkeypatch.setattr(pickle, "loads", forbidden_loads)
    for index, (data, inner_media_type) in enumerate(values):
        now = datetime.now(UTC)
        digest = _digest(f"connector-cache-source-{index}")
        result = FetchResult(
            data=data,
            row_count=1,
            schema_id="test.connector-cache-source",
            schema_version="1.0",
            version=DataVersion(
                strategy=VersionStrategy.CONTENT_HASH,
                value=digest,
                timestamp=now,
                content_hash=digest,
            ),
            fetched_at=now,
            source_updated_at=now,
            completeness=1.0,
            quality_tier=QualityTier.GOLD,
        )
        request = FetchRequest(dataset_id=f"test.connector-cache-{index}")
        with ConnectorCacheStore(store, TTLPolicy(ttl=timedelta(hours=1))) as cache:
            metadata = cache.put(request, result, connector_id="test.connector")
        assert metadata.payload_media_type == (
            "application/vnd.polisyos.cached-result+" + inner_media_type
        )
        profileless = ArtifactRef(
            artifact_id=metadata.payload_artifact_id,
            kind="connector_cache.payload",
            media_type=metadata.payload_media_type,
        )
        selected, envelope = epoch._load_owner_projection_mapping(store, profileless)
        assert selected.manifest_profile_sha256 is not None
        assert envelope["data_media_type"] == inner_media_type
        assert envelope["fetched_at"] == now
        assert envelope["source_updated_at"] == now
        serialized = store.get_bytes(selected)
        envelope_size = int.from_bytes(serialized[:4], "big")
        envelope_end = 4 + envelope_size
        serialized_envelope = epoch.canon.from_canonical_bytes(serialized[4:envelope_end])
        assert isinstance(serialized_envelope, dict)
        normalized_naive = epoch.canon.from_canonical_bytes(
            epoch.canon.to_canonical_bytes(
                datetime(2025, 1, 1), epoch.canon.CanonSpec(forbid_floats=False)
            )
        )
        assert isinstance(normalized_naive, datetime)
        assert normalized_naive.utcoffset() == timedelta(0)
        for field_name, malformed_value, error_text in (
            ("fetched_at", "not-a-datetime", "fields differ from FetchResult"),
            ("source_updated_at", "not-a-datetime", "source update time is malformed"),
        ):
            malformed_envelope = serialized_envelope | {field_name: malformed_value}
            malformed_bytes = epoch.canon.to_canonical_bytes(
                malformed_envelope, epoch.canon.CanonSpec(forbid_floats=False)
            )
            malformed_payload = (
                len(malformed_bytes).to_bytes(4, "big")
                + malformed_bytes
                + serialized[envelope_end:]
            )
            with pytest.raises(ValueError, match=error_text):
                epoch._connector_cache_payload_mapping(
                    malformed_payload, media_type=selected.media_type
                )
        manifest = store.get_manifest(selected)
        assert manifest.artifact_schema.name == "fabric.connector_cache"
        assert manifest.artifact_schema.version == "1.0"
        assert epoch._resolve_selected_reference_graph(store, selected) is not None
        fabricated_prefix = selected.model_copy(update={"kind": "fabric.connector_cache.payload"})
        assert epoch._resolve_selected_reference_graph(store, fabricated_prefix) is None
        serializer_media_types = (
            "application/vnd.polisyos.cached-result+application/json",
            "application/vnd.polisyos.cached-result+application/parquet",
            "application/vnd.polisyos.cached-result+application/pickle",
        )
        other_media = next(
            media for media in serializer_media_types if media != selected.media_type
        )
        assert (
            epoch._resolve_selected_reference_graph(
                store, selected.model_copy(update={"media_type": other_media})
            )
            is None
        )
        wrong_profile = "sha256:" + "0" * 64
        if wrong_profile == selected.manifest_profile_sha256:
            wrong_profile = "sha256:" + "f" * 64
        assert (
            epoch._resolve_selected_reference_graph(
                store, selected.model_copy(update={"manifest_profile_sha256": wrong_profile})
            )
            is None
        )
        if index == 0:
            manifest_for_schema = store.get_manifest(selected)
            altered_schema = manifest_for_schema.artifact_schema.model_copy(
                update={"version": "99.0"}
            )
            altered_manifest = manifest_for_schema.model_copy(
                update={"artifact_schema": altered_schema}
            )
            altered_ref = selected.model_copy(
                update={
                    "manifest_profile_sha256": (
                        epoch.artifacts.artifact_manifest_profile_sha256(altered_manifest)
                    )
                }
            )

            class AlteredSchemaView:
                def __init__(
                    self,
                    delegate: FileSystemCAS,
                    target_artifact_id: ArtifactID,
                    replacement_manifest: Any,
                ) -> None:
                    self._delegate = delegate
                    self._target_artifact_id = target_artifact_id
                    self._replacement_manifest = replacement_manifest

                def get_manifest(self, selector: ArtifactID | ArtifactRef) -> Any:
                    if str(getattr(selector, "artifact_id", selector)) == str(
                        self._target_artifact_id
                    ):
                        return self._replacement_manifest
                    return self._delegate.get_manifest(selector)

                def get_bytes(self, selector: ArtifactID | ArtifactRef) -> bytes:
                    return self._delegate.get_bytes(selector)

                def verify(self, selector: ArtifactID | ArtifactRef) -> Any:
                    return self._delegate.verify(self._target_artifact_id)

            altered_view = AlteredSchemaView(store, selected.artifact_id, altered_manifest)
            assert epoch._resolve_selected_reference_graph(altered_view, altered_ref) is None
        registered_codec = epoch_contract.acquisition_artifact_codec
        monkeypatch.setattr(
            epoch_contract,
            "acquisition_artifact_codec",
            lambda kind,
            *,
            media_type=None,
            expected_kind=profileless.kind,
            expected_media=profileless.media_type,
            registered_codec=registered_codec: (
                None
                if kind == expected_kind and media_type == expected_media
                else registered_codec(kind, media_type=media_type)
            ),
        )
        assert epoch._resolve_selected_reference_graph(store, selected) is None
        monkeypatch.setattr(epoch_contract, "acquisition_artifact_codec", registered_codec)
    assert forbidden_calls == []


def test_registered_codec_keeps_identity_tokens_and_unresolved_refs_distinct(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    identity_ref = ArtifactRef(
        artifact_id=epoch.ArtifactID.model_validate(epoch._raw_cas_hash(b"doc-1")),
        kind="lex.document",
        media_type="text/plain",
    )
    assert (
        epoch_contract.acquisition_artifact_codec("lex.amendment").payload_format
        == "canonical_json"
    )
    assert (
        epoch_contract.acquisition_artifact_codec("lex.document").payload_format == "identity_token"
    )
    assert (
        epoch_contract.acquisition_artifact_codec("l5.schema_regime_scope_relation").payload_format
        == "unresolved_reference"
    )
    row_bytes = epoch_contract.canonical_epoch_bytes(
        {"amendment_id": "a-1", "amended_doc_id": "doc-1"}
    )
    row_ref = store.put_bytes(
        row_bytes,
        PutOptions(
            kind="lex.amendment",
            media_type="application/json",
            canon=epoch_contract.epoch_canon_info(),
        ),
        return_selected_profile=True,
    )
    profiles = epoch._resolve_selected_reference_graph(
        store, {"amendment": row_ref, "document_identity": identity_ref}
    )
    assert profiles == {epoch._selected_ref_identity(row_ref): row_ref.manifest_profile_sha256}
    assert not store.has(identity_ref.artifact_id)

    alternate_canon_ref = store.put_bytes(
        row_bytes,
        PutOptions(
            kind="lex.amendment",
            media_type="application/json",
            canon=epoch_contract.external_epoch_statement_canon_info(),
        ),
        return_selected_profile=True,
    )
    assert alternate_canon_ref.artifact_id == row_ref.artifact_id
    assert alternate_canon_ref.manifest_profile_sha256 != row_ref.manifest_profile_sha256
    assert (
        epoch._resolve_selected_reference_graph(store, {"amendment": alternate_canon_ref}) is None
    )

    raw = chronology_contract._frame_record(
        epoch_contract.canonical_epoch_bytes(
            {
                "relation_provenance_ref": {
                    "artifact_id": "sha256:" + "7" * 64,
                    "kind": "l5.schema_regime_scope_relation",
                    "media_type": "application/json",
                }
            }
        )
    )
    root_ref = store.put_bytes(
        raw,
        PutOptions(
            kind="epoch.acquisition_owner_snapshot",
            media_type="application/vnd.polisyos.epoch+json",
            canon=epoch_contract.epoch_canon_info(),
        ),
        return_selected_profile=True,
    )
    assert epoch._resolve_selected_reference_graph(store, {"snapshot": root_ref}) is None


def test_real_l5_owner_rows_and_registry_files_round_trip_through_cas(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    owner = substrate_registry.load_l5_catalog_authority(
        substrate_registry.default_substrate_catalog_paths(repo_root)
    )
    receipt, projection = substrate_registry.resolve_l5_schema_regime_projection(
        owner,
        scope_identity_ref=owner.schema_regime_scope_relations[0].scope_identity_refs[0],
        valid_effect_value=date(2025, 1, 1),
        authority_purpose="publication",
    )
    store = FileSystemCAS(tmp_path / "cas")
    adapter = epoch.L5EpochBoundaryOwnerAdapter(owner=owner, artifacts=store)
    registration = epoch.EpochBoundarySourceRegistration(
        registration_id="current-l5-owner",
        owner_kind="l5_schema_regime",
        owner_source_ref=_digest("l5-owner"),
        opaque_scope_binding_ref=_digest("l5-scope"),
    )
    batch = adapter.resolve_complete_batch(registration=registration, owner_query=receipt.query)
    snapshot_ref, snapshot = epoch._load_owner_projection_mapping(
        store, receipt.owner_source_snapshot_ref
    )
    assert snapshot_ref.manifest_profile_sha256 is not None
    assert store.get_manifest(snapshot_ref).canon == epoch_contract.epoch_canon_info()
    assert snapshot["regimes"] == {
        key: dict(value) for key, value in sorted(owner.schema_regime_rows.items())
    }
    assert batch.declared_member_count == len(receipt.assessments)
    assert batch.owner_source_snapshot_ref.manifest_profile_sha256 is not None
    assert epoch._selected_cas_ref_matches_owner_projection(
        batch.owner_source_snapshot_ref, projection.owner_source_snapshot_ref
    )
    for source_ref, source_hash in (
        (receipt.regime_registry_ref, receipt.regime_registry_content_hash),
        (receipt.scope_registry_ref, receipt.scope_registry_content_hash),
    ):
        payload = owner.load_schema_regime_source_artifact_bytes(ref=source_ref)
        selected, _ = epoch._load_owner_projection_mapping(store, source_ref)
        assert str(source_ref.artifact_id) == source_hash == epoch._raw_cas_hash(payload)
        assert selected.manifest_profile_sha256 is not None
        assert store.get_bytes(selected) == payload
        assert store.get_manifest(selected).canon is None
    for assessment in receipt.assessments:
        selected, mapping = epoch._load_owner_projection_mapping(
            store, assessment.regime_source_ref
        )
        assert selected.manifest_profile_sha256 is not None
        assert mapping == dict(owner.schema_regime_rows[assessment.schema_regime_id])
        assert store.get_manifest(selected).canon == epoch_contract.epoch_canon_info()
    relation_ref = next(
        row.scope_relation.relation_provenance_ref
        for row in receipt.assessments
        if row.scope_relation is not None
    )
    with pytest.raises(ValueError, match="no registered content resolver"):
        epoch._load_owner_projection_mapping(store, relation_ref)


def test_l5_owner_row_role_is_checked_before_cas_or_projection(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    owner = substrate_registry.load_l5_catalog_authority(
        substrate_registry.default_substrate_catalog_paths(repo_root)
    )
    seed, _ = substrate_registry.resolve_l5_schema_regime_projection(
        owner,
        scope_identity_ref=owner.schema_regime_scope_relations[0].scope_identity_refs[0],
        valid_effect_value=date(2025, 1, 1),
        authority_purpose="publication",
    )

    class RetaggedL5Owner:
        def __init__(self, source: Any) -> None:
            self.source = source
            self.receipt: epoch_contract.L5SchemaRegimeDenominatorReceipt | None = None
            self.project_calls = 0

        def resolve_schema_regime_denominator(self, *, query: Any) -> Any:
            receipt = self.source.resolve_schema_regime_denominator(query=query)
            first = receipt.assessments[0]
            wrong_ref = first.regime_source_ref.model_copy(update={"kind": "lex.amendment"})
            changed = list(receipt.assessments)
            changed[0] = first.model_copy(update={"regime_source_ref": wrong_ref})
            values = receipt.model_dump(mode="python")
            values["assessments"] = tuple(changed)
            denominator = epoch_contract.canonical_epoch_bytes(
                {
                    "query": receipt.query.model_dump(mode="json"),
                    "owner_source_snapshot_content_hash": receipt.owner_source_snapshot_content_hash,
                    "assessments": [row.model_dump(mode="json") for row in changed],
                }
            )
            values["denominator_hash"] = epoch._raw_cas_hash(denominator)
            self.receipt = epoch_contract.L5SchemaRegimeDenominatorReceipt.model_validate(values)
            return self.receipt

        def load_schema_regime_owner_snapshot(self, *, ref: ArtifactRef) -> bytes:
            return self.source.load_schema_regime_owner_snapshot(ref=ref)

        def load_schema_regime_source_artifact_bytes(self, *, ref: ArtifactRef) -> bytes:
            return self.source.load_schema_regime_source_artifact_bytes(ref=ref)

        def project_scoped_schema_regimes(self, *, receipt: Any) -> Any:
            self.project_calls += 1
            return self.source.project_scoped_schema_regimes(receipt=receipt)

    retagged = RetaggedL5Owner(owner)
    store = FileSystemCAS(tmp_path / "cas")
    adapter = epoch.L5EpochBoundaryOwnerAdapter(owner=retagged, artifacts=store)
    registration = epoch.EpochBoundarySourceRegistration(
        registration_id="retagged-l5-owner",
        owner_kind="l5_schema_regime",
        owner_source_ref=_digest("l5-owner"),
        opaque_scope_binding_ref=_digest("l5-scope"),
    )
    with pytest.raises(ValueError, match="owner artifact role mismatch"):
        adapter.resolve_complete_batch(registration=registration, owner_query=seed.query)

    assert retagged.receipt is not None
    original_ref = (
        owner.resolve_schema_regime_denominator(query=seed.query).assessments[0].regime_source_ref
    )
    wrong_ref = retagged.receipt.assessments[0].regime_source_ref
    assert wrong_ref.artifact_id == original_ref.artifact_id
    assert wrong_ref.media_type == original_ref.media_type
    assert wrong_ref.manifest_profile_sha256 == original_ref.manifest_profile_sha256
    assert wrong_ref.kind == "lex.amendment"
    assert retagged.project_calls == 0
    assert not store.has(retagged.receipt.owner_source_snapshot_ref.artifact_id)
    assert not store.has(wrong_ref.artifact_id)


def test_orchestrated_retrieval_summary_resolves_as_selected_snapshot_graph(
    tmp_path: Path,
) -> None:
    import logging
    from unittest.mock import patch

    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.canon import CanonSpec, from_canonical_bytes
    from polisyos.core.contracts.fabric import (
        DataSnapshot,
        DataSnapshotRef,
        EvidenceBundle,
        EvidenceBundleRef,
        RetrievalSummary,
    )
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.fabric.data_plane.orchestrator import run_orchestrated_ingestion
    from polisyos.scientist.nodes.builtins.governance.data_plane_gate import DataPlaneGateNode
    from polisyos.scientist.nodes.builtins.state_keys import INPUT_DATA_SNAPSHOT_REF
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root)
    source_ref = store.put_bytes(
        b'{"rows":[{"x":1}]}',
        PutOptions(kind="fabric.acquisition.raw_evidence", media_type="application/json"),
        return_selected_profile=True,
    )
    evidence_ref = store.put_json(
        EvidenceBundle(sources=[source_ref], notes=["selected source fixture"]),
        PutOptions(
            kind="fabric.evidence_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="fabric.evidence_bundle", version="1.0"),
        ),
        return_selected_profile=True,
    )
    evidence_bundle_ref = EvidenceBundleRef.model_validate(evidence_ref.model_dump(mode="python"))

    with patch(
        "polisyos.fabric.ingestion.run_connectors_ingestion",
        return_value=evidence_bundle_ref,
    ):
        result = run_orchestrated_ingestion(
            connector_manifest={"datasets": [{"connector_id": "test", "dataset_id": "ds1"}]},
            source="semantic-epoch-test",
            license_name="open",
            cas_root=cas_root,
            produce_snapshot=True,
        )

    snapshot_ref = result.data_snapshot_ref
    assert snapshot_ref is not None
    assert snapshot_ref.manifest_profile_sha256 is not None
    snapshot_payload = from_canonical_bytes(store.get_bytes(snapshot_ref))
    snapshot = DataSnapshot.model_validate(snapshot_payload)
    summary_ref = snapshot.quality_report_ref
    assert summary_ref is not None
    assert summary_ref.kind == RetrievalSummary.ARTIFACT_KIND
    assert summary_ref.manifest_profile_sha256 is not None

    summary_manifest = store.get_manifest(summary_ref)
    assert summary_manifest.kind == RetrievalSummary.ARTIFACT_KIND
    assert summary_manifest.media_type == RetrievalSummary.ARTIFACT_MEDIA_TYPE
    assert summary_manifest.artifact_schema == SchemaInfo(
        name=RetrievalSummary.ARTIFACT_SCHEMA_NAME,
        version=RetrievalSummary.ARTIFACT_SCHEMA_VERSION,
    )
    summary = RetrievalSummary.model_validate(from_canonical_bytes(store.get_bytes(summary_ref)))
    assert summary.assessment_status == "not_assessed"
    assert summary.source_refs == [source_ref]
    assert summary.observed_counts == {"datasets_fetched": 1}
    assert not hasattr(summary, "score")

    profiles = epoch._resolve_selected_reference_graph(store, snapshot_ref)
    assert profiles is not None
    summary_identity = (str(summary_ref.artifact_id), summary_ref.kind, summary_ref.media_type)
    assert profiles[summary_identity] == summary_ref.manifest_profile_sha256
    assert profiles[(str(source_ref.artifact_id), source_ref.kind, source_ref.media_type)] == (
        source_ref.manifest_profile_sha256
    )

    registry_ref = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id="R_epoch_summary")
    context = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.semantic_epoch.retrieval_summary"),
    )
    candidate_state = ExperimentState(
        run_id="R_epoch_summary_candidate",
        inputs={INPUT_DATA_SNAPSHOT_REF: snapshot_ref},
        params={"governance_profile": "mvp", "tenant_tier": "shared"},
    )
    candidate_outcome = DataPlaneGateNode().execute(context, candidate_state)
    assert candidate_outcome.status == "ok"
    candidate_issue = next(
        issue
        for issue in candidate_outcome.state.params["data_plane_gate_issues"]
        if issue["code"] == "QUALITY_ASSESSMENT_NOT_ESTABLISHED"
    )
    assert candidate_issue["severity"] == "warning"
    assert candidate_outcome.state.params["data_plane_gate_blocked"] is False

    strict_state = ExperimentState(
        run_id="R_epoch_summary_strict",
        inputs={INPUT_DATA_SNAPSHOT_REF: snapshot_ref},
        params={"governance_profile": "strict", "tenant_tier": "shared"},
    )
    strict_outcome = DataPlaneGateNode().execute(context, strict_state)
    assert strict_outcome.status == "fail"
    assert strict_outcome.error is not None
    assert strict_outcome.error.code == "governance.data_plane_blocked"
    strict_issue = next(
        issue
        for issue in strict_outcome.state.params["data_plane_gate_issues"]
        if issue["code"] == "QUALITY_ASSESSMENT_NOT_ESTABLISHED"
    )
    assert strict_issue["severity"] == "blocker"
    assert strict_outcome.state.params["data_plane_gate_blocked"] is True

    def _persist_variant(ref: ArtifactRef) -> DataSnapshotRef:
        changed = snapshot.model_copy(update={"quality_report_ref": ref})
        selected = store.put_json(
            changed,
            PutOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        return DataSnapshotRef.model_validate(selected.model_dump(mode="python"))

    wrong_kind = ArtifactRef.model_validate(
        summary_ref.model_dump(mode="json") | {"kind": "fabric.data_snapshot"}
    )
    assert epoch._resolve_selected_reference_graph(store, _persist_variant(wrong_kind)) is None

    wrong_schema_ref = store.put_json(
        summary,
        PutOptions(
            kind=RetrievalSummary.ARTIFACT_KIND,
            media_type=RetrievalSummary.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=RetrievalSummary.ARTIFACT_SCHEMA_NAME, version="9.9"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert (
        epoch._resolve_selected_reference_graph(
            store,
            _persist_variant(wrong_schema_ref),
        )
        is None
    )

    wrong_profile = ArtifactRef.model_validate(
        summary_ref.model_dump(mode="json") | {"manifest_profile_sha256": f"sha256:{'0' * 64}"}
    )
    assert epoch._resolve_selected_reference_graph(store, _persist_variant(wrong_profile)) is None


def test_live_source_admission_reconciles_retrieval_summary_and_legacy_quality(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    from polisyos.core.artifacts.async_store import ensure_async_artifact_store
    from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
    from polisyos.core.canon import CanonSpec, from_canonical_bytes
    from polisyos.core.contracts import DataSnapshot, RetrievalSummary
    from polisyos.core.contracts.fabric import DataSnapshotRef
    from polisyos.data_forge.read_api import catalog as catalog_read_api
    from polisyos.fabric.data_plane.orchestrator import _build_snapshot_from_evidence_async
    from polisyos.runtime.quality.acquisition_executor import build_admission_passport
    from tests._helpers.acquisition_production import _run
    from tests._helpers.semantic_epoch_native import _semantic_handshake

    authority, live_evidence, stub, _journal_path = _run(tmp_path, monkeypatch)
    assert stub.cas_root is not None
    store = FileSystemCAS(stub.cas_root)
    prior_snapshot = DataSnapshot.model_validate(
        from_canonical_bytes(store.get_bytes(live_evidence.data_snapshot_ref))
    )
    candidate, prepared = _semantic_handshake(store, source_ref=prior_snapshot.data_ref)

    produced_snapshot_ref = asyncio.run(
        _build_snapshot_from_evidence_async(
            store=ensure_async_artifact_store(store),
            evidence_ref=live_evidence.evidence_bundle_ref,
            datasets_fetched=1,
            source="n8-live-fixture",
        )
    )
    assert produced_snapshot_ref is not None
    snapshot = DataSnapshot.model_validate(
        from_canonical_bytes(store.get_bytes(produced_snapshot_ref))
    )
    summary_ref = snapshot.quality_report_ref
    assert summary_ref is not None
    summary = RetrievalSummary.model_validate(from_canonical_bytes(store.get_bytes(summary_ref)))

    def _matches_with_quality_ref(
        quality_ref: ArtifactRef,
        *,
        snapshot_changes: dict[str, object] | None = None,
        manifest_inputs: list[object] | None = None,
    ) -> bool:
        changed_snapshot = snapshot.model_copy(
            update=dict(snapshot_changes or {}) | {"quality_report_ref": quality_ref}
        )
        if manifest_inputs is None:
            assert changed_snapshot.data_ref is not None
            assert changed_snapshot.evidence_ref is not None
            manifest_inputs = [
                input_ref_from_artifact_ref(changed_snapshot.evidence_ref, role="evidence_ref"),
                input_ref_from_artifact_ref(changed_snapshot.data_ref, role="data_ref"),
                input_ref_from_artifact_ref(quality_ref, role="quality_report_ref"),
            ]
        selected_snapshot = store.put_json(
            changed_snapshot,
            PutOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
                inputs=manifest_inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        selected_snapshot_ref = DataSnapshotRef.model_validate(
            selected_snapshot.model_dump(mode="python")
        )
        proof = catalog_read_api.build_live_source_execution_evidence(
            authorization=live_evidence.authorization,
            family_receipt=live_evidence.family_receipt,
            request_ref=live_evidence.request_ref,
            raw_evidence_ref=live_evidence.raw_evidence_ref,
            transport_trace=live_evidence.transport_trace,
            raw_artifact_id=live_evidence.raw_artifact_id,
            evidence_bundle_ref=live_evidence.evidence_bundle_ref,
            data_snapshot_ref=selected_snapshot_ref,
            normalized_data_artifact_id=live_evidence.normalized_data_artifact_id,
            variable_count=live_evidence.variable_count,
            page_count=live_evidence.page_count,
            baseline_before_sha256=live_evidence.baseline_before_sha256,
            baseline_after_sha256=live_evidence.baseline_after_sha256,
            raw_body_sha256=live_evidence.raw_body_sha256,
            normalized_result_content_sha256=(live_evidence.normalized_result_content_sha256),
        )
        passport = build_admission_passport(
            epoch_id=1,
            raw_evidence_ref=proof.raw_evidence_ref,
            artifact_store=store,
            raw_artifact_id=str(proof.raw_artifact_id),
            authority=authority,
            boundary_candidate=candidate,
            prepared_epoch=prepared,
            live_source_execution=proof,
        )
        return epoch._live_source_candidate_graph_matches(
            store,
            candidate.statement,
            passport.model_dump(mode="json"),
        )

    assert _matches_with_quality_ref(summary_ref)

    forged_summary_label_ref = store.put_json(
        summary.model_copy(update={"source": "forged-descriptive-label"}),
        PutOptions(
            kind=RetrievalSummary.ARTIFACT_KIND,
            media_type=RetrievalSummary.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=RetrievalSummary.ARTIFACT_SCHEMA_NAME,
                version=RetrievalSummary.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert _matches_with_quality_ref(forged_summary_label_ref)
    assert _matches_with_quality_ref(
        summary_ref,
        snapshot_changes={"stats": snapshot.stats | {"source": "different-descriptive-label"}},
    )
    assert _matches_with_quality_ref(
        forged_summary_label_ref,
        snapshot_changes={"stats": snapshot.stats | {"source": "forged-descriptive-label"}},
    )

    assert snapshot.evidence_ref is not None and snapshot.data_ref is not None
    wrong_manifest_roles = [
        input_ref_from_artifact_ref(snapshot.evidence_ref, role="data_ref"),
        input_ref_from_artifact_ref(snapshot.data_ref, role="evidence_ref"),
        input_ref_from_artifact_ref(summary_ref, role="data_ref"),
    ]
    assert not _matches_with_quality_ref(summary_ref, manifest_inputs=wrong_manifest_roles)
    assert not _matches_with_quality_ref(summary_ref, manifest_inputs=[])

    assert snapshot.data_ref is not None
    foreign_source = store.put_bytes(
        b"foreign source",
        PutOptions(kind="fabric.acquisition.raw_evidence", media_type="application/json"),
        return_selected_profile=True,
    )
    wrong_sources_ref = store.put_json(
        summary.model_copy(update={"source_refs": [foreign_source]}),
        PutOptions(
            kind=RetrievalSummary.ARTIFACT_KIND,
            media_type=RetrievalSummary.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=RetrievalSummary.ARTIFACT_SCHEMA_NAME,
                version=RetrievalSummary.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert not _matches_with_quality_ref(wrong_sources_ref)

    wrong_count_ref = store.put_json(
        summary.model_copy(update={"observed_counts": {"datasets_fetched": 2}}),
        PutOptions(
            kind=RetrievalSummary.ARTIFACT_KIND,
            media_type=RetrievalSummary.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=RetrievalSummary.ARTIFACT_SCHEMA_NAME,
                version=RetrievalSummary.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert not _matches_with_quality_ref(wrong_count_ref)

    wrong_notes_ref = store.put_json(
        summary.model_copy(update={"notes": ["forged retrieval note"]}),
        PutOptions(
            kind=RetrievalSummary.ARTIFACT_KIND,
            media_type=RetrievalSummary.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=RetrievalSummary.ARTIFACT_SCHEMA_NAME,
                version=RetrievalSummary.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert not _matches_with_quality_ref(wrong_notes_ref)
    with pytest.raises(ValueError, match="live_source_execution_unresolved") as count_error:
        _matches_with_quality_ref(
            summary_ref,
            snapshot_changes={"stats": snapshot.stats | {"datasets_fetched": 2}},
        )
    assert "live_snapshot_dataset_count_invalid" in str(count_error.value.__cause__)

    wrong_kind_ref = ArtifactRef.model_validate(
        summary_ref.model_dump(mode="json") | {"kind": "fabric.quality_report"}
    )
    assert not _matches_with_quality_ref(wrong_kind_ref)

    wrong_profile_ref = ArtifactRef.model_validate(
        summary_ref.model_dump(mode="json") | {"manifest_profile_sha256": f"sha256:{'0' * 64}"}
    )
    assert not _matches_with_quality_ref(wrong_profile_ref)

    legacy_quality_ref = store.put_json(
        {
            "source": "legacy-descriptive-source-label",
            "datasets_count": 1,
            "notes": ["network-free orchestrated WDI test"],
        },
        PutOptions(
            kind="fabric.quality_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.fabric.DataQualityReport", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert _matches_with_quality_ref(legacy_quality_ref)

    broken_legacy_ref = store.put_json(
        {
            "source": "orchestrated_ingestion:legacy-fixture",
            "datasets_count": 2,
            "notes": ["network-free orchestrated WDI test"],
        },
        PutOptions(
            kind="fabric.quality_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.fabric.DataQualityReport", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert not _matches_with_quality_ref(broken_legacy_ref)
