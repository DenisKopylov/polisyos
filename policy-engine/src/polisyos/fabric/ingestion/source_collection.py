"""Reconcile complete finite replay contributions into one consumer-readable view.

This is a namespaced collection, never a guessed row union or cross-source join.
Each namespace retains its source identity and explicit finite replay limitations.
The ordinary single-source live-acquisition cached-result contract is unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts import load_core_json_artifact
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, content_hash, to_canonical_bytes
from polisyos.core.contracts.fabric import EvidenceBundle, EvidenceBundleRef
from polisyos.core.contracts.provenance import ProvenanceCoreGraph, RelationType
from polisyos.ir.connectors import DataVersion

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.fabric.ingestion.source_progress import ReconciledSourceFrame
    from polisyos.ir.connectors import FetchRequest, FetchResult


class SourceCollectionMember(BaseModel):
    """One exact persisted source contribution and its bounded authority scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    connector_id: str
    dataset_id: str
    version: DataVersion
    source_ref: ArtifactRef
    source_progress_witness_ref: ArtifactRef
    transport_identity: dict[str, str]
    transport_sha256: str
    data: list[dict[str, Any]]


class SourceCollection(BaseModel):
    """Versioned JSON view accepted by Foundry's existing plain JSON loader.

    Consumers select a source namespace explicitly with their normal binding
    rules. This contract makes no relationship/join claim between namespaces.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["fabric.source_collection.v1"] = "fabric.source_collection.v1"
    admission_scope: Literal["finite_source_fixture"] = "finite_source_fixture"
    production_currentness: Literal["not_established"] = "not_established"
    external_source_rights: Literal["not_established"] = "not_established"
    production_event_identity_semantics: Literal["not_established"] = "not_established"
    composition_semantics: Literal["namespaced_collection_no_inferred_join"] = (
        "namespaced_collection_no_inferred_join"
    )
    source_evidence_ref: EvidenceBundleRef
    tenant_id: str | None = None
    sources: dict[str, SourceCollectionMember] = Field(min_length=1)


def source_namespace(connector_id: str, dataset_id: str) -> str:
    """Derive a path-safe namespace from exact source identity, independent of order."""
    return content_hash(to_canonical_bytes([connector_id, dataset_id]))


def materialize_source_collection(
    *,
    store: ArtifactStore,
    evidence_ref: EvidenceBundleRef,
    datasets: tuple[tuple[str, str], ...],
    persisted_results: dict[
        tuple[str, str],
        tuple[FetchRequest, FetchResult[Any], FetchResult[Any], ArtifactRef, EvidenceBundleRef],
    ],
    frames: dict[tuple[str, str], ReconciledSourceFrame],
) -> tuple[ArtifactRef, EvidenceBundleRef]:
    """Recompute every source binding before producing a complete snapshot view.

    The denominator is the entire persisted evidence bundle AND the entire
    requested source set. Missing/extra/duplicate sources, source-view mismatch,
    profile mismatch or unresolved transport fails before snapshot publication.
    """
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.fabric.connectors.cache._store_serialization import ResultSerializer
    from polisyos.fabric.ingestion.ingestion import _cache_payload_ref_matches_result

    evidence = EvidenceBundle.model_validate(load_core_json_artifact(store, evidence_ref))
    source_manifest = store.get_manifest(evidence_ref)
    if not datasets or len(datasets) != len(set(datasets)):
        raise ValueError("source collection requires unique actual source identities")
    if set(persisted_results) != set(datasets) or set(frames) != set(datasets):
        raise ValueError("source collection does not cover every actual requested source")
    expected_refs = [persisted_results[key][3] for key in datasets]
    actual_ids = [artifact_ref_identity_key(ref) for ref in evidence.sources]
    expected_ids = [artifact_ref_identity_key(ref) for ref in expected_refs]
    if len(actual_ids) != len(set(actual_ids)) or set(actual_ids) != set(expected_ids):
        raise ValueError("source collection denominator differs from complete evidence sources")
    if evidence.provenance_ref is None:
        raise ValueError("source collection provenance is unavailable")
    graph = ProvenanceCoreGraph.from_dict(
        load_core_json_artifact(
            store, ArtifactID.model_validate(evidence.provenance_ref.artifact_id)
        )
    )
    if (
        graph.graph_id != evidence.provenance_ref.graph_id
        or graph.compute_stable_id() != evidence.provenance_ref.stable_id
    ):
        raise ValueError("source collection provenance does not resolve to its bound graph")
    members: dict[str, SourceCollectionMember] = {}
    inputs = [input_ref_from_artifact_ref(evidence_ref, role="source_evidence")]
    for connector_id, dataset_id in sorted(datasets):
        key = (connector_id, dataset_id)
        request, _source_result, captured, ref, receipt_evidence_ref = persisted_results[key]
        if artifact_ref_identity_key(receipt_evidence_ref) != artifact_ref_identity_key(
            evidence_ref
        ):
            raise ValueError("source contribution belongs to a different evidence view")
        persisted = ResultSerializer.deserialize(store.get_bytes(ref))
        if not _cache_payload_ref_matches_result(
            store, ref, persisted
        ) or not _cache_payload_ref_matches_result(store, ref, captured):
            raise ValueError("source contribution bytes differ from the persisted result")
        frame = frames[key]
        frame.assert_current()
        frame.assert_transport_current()
        frame.verify_materialization(persisted)
        entity_id = f"dataset.{connector_id}.{dataset_id}"
        entity = graph.entities.get(entity_id)
        if (
            entity is None
            or entity.attributes.get("fetch_status") != "complete"
            or entity.attributes.get("cache_key") != request.cache_key
            or entity.attributes.get("data_artifact_id") != ref.artifact_id.hex
            or entity.attributes.get("version_value") != persisted.version.value
            or not any(
                edge.source_id == entity_id
                and edge.target_id == "connector_ingestion_run"
                and edge.relation is RelationType.WAS_GENERATED_BY
                for edge in graph.edges
            )
        ):
            raise ValueError("source collection contribution is not bound to actual provenance")
        witness_ref = frame.witness(store)
        if frame.transport_identity is None or frame.transport_bytes_hash is None:
            raise ValueError("source collection transport admission is absent")
        members[source_namespace(connector_id, dataset_id)] = SourceCollectionMember(
            connector_id=connector_id,
            dataset_id=dataset_id,
            version=persisted.version,
            source_ref=ref,
            source_progress_witness_ref=witness_ref,
            transport_identity=frame.transport_identity,
            transport_sha256=frame.transport_bytes_hash,
            data=[dict(row) for row in frame.current.rows],
        )
        inputs.extend(
            [
                input_ref_from_artifact_ref(ref, role="source_contribution"),
                input_ref_from_artifact_ref(witness_ref, role="source_progress_witness"),
            ]
        )
    tenants = {frame.tenant_id for frame in frames.values()}
    if len(tenants) != 1:
        raise ValueError("source collection cannot mix tenant scopes")
    collection = SourceCollection(
        source_evidence_ref=evidence_ref, tenant_id=next(iter(tenants)), sources=members
    )
    data_ref = store.put_json(
        collection,
        ArtifactWriteOptions(
            kind="fabric.source_collection",
            media_type="application/json",
            schema=SchemaInfo(name="fabric.SourceCollection", version="1.0"),
            inputs=inputs,
            governance=source_manifest.governance,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    if not store.verify(data_ref).ok or load_source_collection(store, data_ref) != collection:
        raise ValueError("materialized source collection did not persist its exact selected view")
    derived = evidence.model_copy(
        update={
            "sources": [data_ref],
            "notes": [
                *(evidence.notes or []),
                (
                    "Finite replay namespaced collection; production currentness, rights and "
                    "event semantics not established; no cross-source join inferred."
                ),
            ],
        }
    )
    materialized_evidence = store.put_json(
        derived,
        ArtifactWriteOptions(
            kind=evidence_ref.kind,
            media_type="application/json",
            schema=source_manifest.schema,
            governance=source_manifest.governance,
            inputs=[
                input_ref_from_artifact_ref(evidence_ref, role="source_evidence"),
                input_ref_from_artifact_ref(data_ref, role="source_collection"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    if (
        not store.verify(materialized_evidence).ok
        or EvidenceBundle.model_validate(load_core_json_artifact(store, materialized_evidence))
        != derived
    ):
        raise ValueError("collection evidence did not persist its exact selected view")
    return data_ref, EvidenceBundleRef.model_validate(
        materialized_evidence.model_dump(mode="python")
    )


def load_source_collection(store: ArtifactStore, ref: ArtifactRef) -> SourceCollection:
    """Verify the whole original denominator and every decoded contribution.

    Foundry's real snapshot loader invokes this reader. Omitting B while keeping
    A/B evidence and completeness declarations is a hard refusal. Namespace
    order, producer flags and constructor validity are never the oracle.
    """
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.fabric.connectors.cache._store_serialization import ResultSerializer
    from polisyos.fabric.ingestion.ingestion import _cache_payload_ref_matches_result
    from polisyos.fabric.ingestion.source_progress import load_source_progress_witness

    if (
        ref.kind != "fabric.source_collection"
        or ref.media_type != "application/json"
        or ref.manifest_profile_sha256 is None
    ):
        raise ValueError("source collection requires its exact JSON view")
    collection = SourceCollection.model_validate(load_core_json_artifact(store, ref))
    evidence = EvidenceBundle.model_validate(
        load_core_json_artifact(store, collection.source_evidence_ref)
    )
    actual = [artifact_ref_identity_key(source) for source in evidence.sources]
    members = list(collection.sources.values())
    selected = [artifact_ref_identity_key(member.source_ref) for member in members]
    if (
        not actual
        or len(actual) != len(set(actual))
        or len(selected) != len(set(selected))
        or set(actual) != set(selected)
    ):
        raise ValueError("source collection omits or duplicates an actual evidence source")
    if evidence.provenance_ref is None:
        raise ValueError("source collection provenance is unavailable")
    graph = ProvenanceCoreGraph.from_dict(
        load_core_json_artifact(
            store, ArtifactID.model_validate(evidence.provenance_ref.artifact_id)
        )
    )
    if (
        graph.graph_id != evidence.provenance_ref.graph_id
        or graph.compute_stable_id() != evidence.provenance_ref.stable_id
    ):
        raise ValueError("source collection provenance graph does not resolve")
    identities: set[tuple[str, str]] = set()
    for namespace, member in collection.sources.items():
        identity = (member.connector_id, member.dataset_id)
        if namespace != source_namespace(*identity) or identity in identities:
            raise ValueError("source collection namespace/source identity differs")
        identities.add(identity)
        result = ResultSerializer.deserialize(store.get_bytes(member.source_ref))
        if not _cache_payload_ref_matches_result(store, member.source_ref, result):
            raise ValueError("source collection contribution bytes do not verify")
        frame = load_source_progress_witness(store, member.source_progress_witness_ref)
        if (
            frame.tenant_id != collection.tenant_id
            or (frame.extension.connector_id, frame.extension.dataset_id) != identity
            or frame.extension.transport_kind != "finite_history_file"
            or frame.transport_identity != member.transport_identity
            or frame.transport_bytes_hash != member.transport_sha256
            or result.version != member.version
        ):
            raise ValueError("source collection member is not bound to its replay proof")
        frame.verify_materialization(result)
        try:
            frame.verify_materialization(
                result.model_copy(update={"data": member.data, "row_count": len(member.data)})
            )
        except ValueError as exc:
            raise ValueError(
                "source collection data differs from complete persisted source"
            ) from exc
        entity_id = f"dataset.{member.connector_id}.{member.dataset_id}"
        entity = graph.entities.get(entity_id)
        if (
            entity is None
            or entity.attributes.get("fetch_status") != "complete"
            or entity.attributes.get("data_artifact_id") != member.source_ref.artifact_id.hex
            or entity.attributes.get("version_value") != member.version.value
            or not any(
                edge.source_id == entity_id
                and edge.target_id == "connector_ingestion_run"
                and edge.relation is RelationType.WAS_GENERATED_BY
                for edge in graph.edges
            )
        ):
            raise ValueError("source collection member is absent from actual provenance")
    return collection
