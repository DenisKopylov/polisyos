"""Public fabric evidence module API."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from polisyos.core.artifacts import (
    artifact_manifest_profile_projection,
    artifact_manifest_profile_sha256,
    expected_artifact_manifest_for_write,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    CanonInfo,
    InputRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts.fabric import (
    EvidenceBundle,
    EvidenceBundleRef,
    EvidenceStep,
    IngestionExecutionContext,
    ProvenanceCoreRefModel,
    evidence_bundle_manifest_input_refs,
)
from polisyos.fabric.provenance.core import ProvenanceCoreGraph, ProvenanceCoreRef
from polisyos.fabric.security import DataClassification, RetentionScope, resolve_artifact_governance

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactReader, ArtifactStore
    from polisyos.core.artifacts.manifest import ArtifactManifest
    from polisyos.fabric.connectors.federation.types import CompositionStrategy, MergeLogEntry
    from polisyos.fabric.quality.quality import QualityIndicators


class EvidencePayloadError(ValueError):
    """Raised when a persisted Fabric evidence payload is malformed."""


def _require_payload_str(payload: dict[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise EvidencePayloadError(
            f"Provenance graph payload missing required string field: {field}"
        )
    return value


def build_evidence_bundle(
    *,
    sources: list[ArtifactRef] | None = None,
    transforms: list[EvidenceStep] | None = None,
    trust_policy_id: str | None = None,
    notes: list[str] | None = None,
    provenance_ref: ProvenanceCoreRef | None = None,
    quality_indicators: dict[str, QualityIndicators] | None = None,
    execution_context: IngestionExecutionContext | None = None,
) -> EvidenceBundle:
    """Build evidence bundle."""
    prov_model = None
    if provenance_ref is not None:
        prov_model = ProvenanceCoreRefModel(
            graph_id=provenance_ref.graph_id,
            stable_id=provenance_ref.stable_id,
            artifact_id=provenance_ref.artifact_id,
            manifest_profile_sha256=provenance_ref.manifest_profile_sha256,
        )
    quality_payload = None
    if quality_indicators is not None:
        quality_payload = {
            metric_id: indicators.to_dict() for metric_id, indicators in quality_indicators.items()
        }
    return EvidenceBundle(
        sources=sources or [],
        transforms=transforms or [],
        trust_policy_id=trust_policy_id,
        notes=notes or [],
        provenance_ref=prov_model,
        quality_indicators=quality_payload,
        execution_context=execution_context,
    )


def _provenance_graph_write_options(
    *,
    schema_name: str,
    schema_version: str,
    classification: DataClassification | str | None,
    encrypted_at_rest: bool,
    field_level_encrypted: bool,
    encryption_key_reference: str | None,
    inputs: list[InputRef] | None,
) -> PutOptions:
    """Derive the complete provenance graph writer options from its inputs."""
    return PutOptions(
        kind="fabric.provenance_graph",
        media_type="application/json",
        schema=SchemaInfo(name=schema_name, version=schema_version),
        inputs=inputs,
        canon=CanonInfo.from_spec(CanonSpec()),
        governance=resolve_artifact_governance(
            scope=RetentionScope.EVIDENCE_BUNDLE,
            classification=classification,
            encrypted_at_rest=encrypted_at_rest,
            field_level_encrypted=field_level_encrypted,
            encryption_key_reference=encryption_key_reference,
        ),
    )


def persist_provenance_graph(
    store: ArtifactStore,
    graph: ProvenanceCoreGraph,
    *,
    schema_name: str = "fabric.provenance_graph",
    schema_version: str = "1.0",
    classification: DataClassification | str | None = None,
    encrypted_at_rest: bool = False,
    field_level_encrypted: bool = False,
    encryption_key_reference: str | None = None,
    inputs: list[InputRef] | None = None,
    return_selected_profile: bool = False,
) -> ProvenanceCoreRef:
    """Persist a ProvenanceCoreGraph to CAS and return a reference."""
    payload = graph.to_dict()
    stable_id = _require_payload_str(payload, "stable_id")
    ref = store.put_json(
        payload,
        opts=_provenance_graph_write_options(
            schema_name=schema_name,
            schema_version=schema_version,
            classification=classification,
            encrypted_at_rest=encrypted_at_rest,
            field_level_encrypted=field_level_encrypted,
            encryption_key_reference=encryption_key_reference,
            inputs=inputs,
        ),
        return_selected_profile=return_selected_profile,
    )
    return ProvenanceCoreRef(
        graph_id=graph.graph_id,
        stable_id=stable_id,
        artifact_id=str(ref.artifact_id),
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )


def load_provenance_graph(
    store: ArtifactStore,
    ref: ProvenanceCoreRef,
    *,
    require_selected_profile: bool = False,
) -> ProvenanceCoreGraph:
    """
    Load a ProvenanceCoreGraph from CAS by reference.

    Args:
        store: Artifact store containing the graph.
        ref: Exact graph reference, or a legacy default-view reference.
        require_selected_profile: Require an explicit selected view for source binding.

    Raises:
        ValueError: If a required selected profile is absent or stable_id verification fails.
    """
    from polisyos.core.artifacts import load_core_json_artifact

    if require_selected_profile and ref.manifest_profile_sha256 is None:
        raise ValueError("source provenance requires an explicit selected manifest profile")

    selector = ArtifactRef(
        artifact_id=ArtifactID.model_validate(ref.artifact_id),
        kind="fabric.provenance_graph",
        media_type="application/json",
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )
    data = load_core_json_artifact(store, selector)
    graph = ProvenanceCoreGraph.from_dict(data)

    computed_stable_id = graph.compute_stable_id()
    if computed_stable_id != ref.stable_id:
        raise ValueError(
            "Provenance graph integrity check failed: "
            f"expected {ref.stable_id}, got {computed_stable_id}"
        )

    return graph


def _evidence_bundle_write_options(
    bundle: EvidenceBundle,
    *,
    schema_name: str,
    schema_version: str,
    classification: DataClassification | str | None,
    encrypted_at_rest: bool,
    field_level_encrypted: bool,
    encryption_key_reference: str | None,
) -> PutOptions:
    """Derive the complete evidence writer options from its explicit inputs."""
    input_refs = evidence_bundle_manifest_input_refs(bundle)
    bound_projection = input_refs is not None
    inputs = list(input_refs) if input_refs is not None else None
    return PutOptions(
        kind="fabric.evidence_bundle",
        media_type="application/json",
        schema=SchemaInfo(
            name=schema_name,
            version="2.0" if bound_projection else schema_version,
        ),
        inputs=inputs,
        canon=CanonInfo.from_spec(CanonSpec()),
        governance=resolve_artifact_governance(
            scope=RetentionScope.EVIDENCE_BUNDLE,
            classification=classification,
            encrypted_at_rest=encrypted_at_rest,
            field_level_encrypted=field_level_encrypted,
            encryption_key_reference=encryption_key_reference,
        ),
    )


def persist_evidence_bundle(
    store: ArtifactStore,
    bundle: EvidenceBundle,
    *,
    return_selected_profile: bool = False,
    schema_name: str = "fabric.evidence_bundle",
    schema_version: str = "1.0",
    classification: DataClassification | str | None = None,
    encrypted_at_rest: bool = False,
    field_level_encrypted: bool = False,
    encryption_key_reference: str | None = None,
) -> EvidenceBundleRef:
    """Persist an ``EvidenceBundle`` and return its typed reference.

    Args:
        store: Artifact store receiving the bundle.
        bundle: Evidence bundle to persist.
        return_selected_profile: Include the exact profile selected by this write.
        schema_name: Artifact schema name.
        schema_version: Artifact schema version.
        classification: Optional data classification for storage governance.
        encrypted_at_rest: Whether storage encryption is enabled.
        field_level_encrypted: Whether field-level encryption is enabled.
        encryption_key_reference: Optional reference to the encryption key.

    Returns:
        EvidenceBundleRef: The persisted bundle reference.
    """
    write_options = _evidence_bundle_write_options(
        bundle,
        schema_name=schema_name,
        schema_version=schema_version,
        classification=classification,
        encrypted_at_rest=encrypted_at_rest,
        field_level_encrypted=field_level_encrypted,
        encryption_key_reference=encryption_key_reference,
    )
    if return_selected_profile:
        ref = store.put_json(
            bundle.model_dump(),
            opts=write_options,
            return_selected_profile=True,
        )
    else:
        ref = store.put_json(bundle.model_dump(), opts=write_options)
    return EvidenceBundleRef.model_validate(ref.model_dump())


def _read_selected_input(store: ArtifactReader, ref: ArtifactRef) -> tuple[ArtifactManifest, bytes]:
    """Verify one exact input view and its bytes without asserting owner authority."""
    selected = ArtifactRef.model_validate(ref.model_dump(mode="python"))
    if selected.manifest_profile_sha256 is None:
        raise EvidencePayloadError("live_evidence_input_profile_unselected")
    try:
        manifest = store.get_manifest(selected)
        body = store.get_bytes(selected)
    except (OSError, TypeError, ValueError) as exc:
        raise EvidencePayloadError("live_evidence_input_unavailable") from exc
    digest = hashlib.sha256(body).hexdigest()
    if (
        manifest.artifact_id != selected.artifact_id
        or manifest.kind != selected.kind
        or manifest.media_type != selected.media_type
        or artifact_manifest_profile_sha256(manifest) != selected.manifest_profile_sha256
        or selected.artifact_id.hex != digest
        or manifest.integrity.sha256 != digest
        or manifest.byte_size != len(body)
    ):
        raise EvidencePayloadError("live_evidence_input_integrity_mismatch")
    return manifest, body


def verify_live_ingestion_evidence_profile(
    store: ArtifactReader,
    ref: ArtifactRef,
    bundle: EvidenceBundle,
) -> None:
    """Verify the selected live-ingestion bundle against the actual Fabric writer.

    This verifies exact bytes, writer metadata, and selected input custody. It
    does not establish the producer authority, validity, or freshness of inputs.

    Args:
        store: Reader for the selected bundle and each selected input.
        ref: Exact selected EvidenceBundle view emitted by Fabric ingestion.
        bundle: Typed bundle read from that view.

    Raises:
        EvidencePayloadError: If a selected profile, byte identity, owner writer
            profile, or required input cannot be established.
    """
    if type(bundle) is not EvidenceBundle:
        raise EvidencePayloadError("live_evidence_bundle_untyped")
    bundle = EvidenceBundle.model_validate(bundle.model_dump(mode="python"))
    selected = ArtifactRef.model_validate(ref.model_dump(mode="python"))
    if (
        selected.manifest_profile_sha256 is None
        or selected.kind != "fabric.evidence_bundle"
        or selected.media_type != "application/json"
    ):
        raise EvidencePayloadError("live_evidence_profile_unselected_or_invalid")
    provenance = bundle.provenance_ref
    if not bundle.sources or provenance is None or provenance.manifest_profile_sha256 is None:
        raise EvidencePayloadError("live_evidence_selected_inputs_missing")
    inputs = list(bundle.sources)
    if bundle.execution_context is not None:
        session = bundle.execution_context.selected_record_session_ref
        if session is not None:
            inputs.append(session)
    provenance_ref = ArtifactRef(
        artifact_id=ArtifactID.model_validate(provenance.artifact_id),
        kind="fabric.provenance_graph",
        media_type="application/json",
        manifest_profile_sha256=provenance.manifest_profile_sha256,
    )
    for item in inputs:
        _read_selected_input(store, item)
    provenance_manifest, provenance_body = _read_selected_input(store, provenance_ref)
    try:
        payload = from_canonical_bytes(provenance_body)
        if not isinstance(payload, dict):
            raise ValueError("provenance graph payload is not a mapping")
        graph = ProvenanceCoreGraph.from_dict(payload)
        if (
            graph.graph_id != provenance.graph_id
            or payload.get("stable_id") != provenance.stable_id
            or graph.compute_stable_id() != provenance.stable_id
            or to_canonical_bytes(graph.to_dict(), CanonSpec()) != provenance_body
        ):
            raise ValueError("provenance graph identity drift")
    except (KeyError, TypeError, ValueError) as exc:
        raise EvidencePayloadError("live_evidence_provenance_payload_mismatch") from exc
    graph_inputs = [
        input_ref_from_artifact_ref(source, role="fabric.ingestion.payload")
        for source in bundle.sources
    ]
    if bundle.execution_context is not None:
        session = bundle.execution_context.selected_record_session_ref
        if session is not None:
            graph_inputs.append(
                input_ref_from_artifact_ref(session, role="fabric.ingestion.record_session")
            )
    expected_provenance = expected_artifact_manifest_for_write(
        artifact_id=provenance_ref.artifact_id,
        data=provenance_body,
        opts=_provenance_graph_write_options(
            schema_name="fabric.provenance_graph",
            schema_version="1.0",
            classification=None,
            encrypted_at_rest=False,
            field_level_encrypted=False,
            encryption_key_reference=None,
            inputs=graph_inputs,
        ),
        created_at=provenance_manifest.created_at,
    )
    if artifact_manifest_profile_projection(
        provenance_manifest
    ) != artifact_manifest_profile_projection(expected_provenance):
        raise EvidencePayloadError("live_evidence_provenance_writer_profile_mismatch")
    manifest, body = _read_selected_input(store, selected)
    if body != to_canonical_bytes(bundle.model_dump(), CanonSpec()):
        raise EvidencePayloadError("live_evidence_bundle_payload_mismatch")
    expected = expected_artifact_manifest_for_write(
        artifact_id=selected.artifact_id,
        data=body,
        opts=_evidence_bundle_write_options(
            bundle,
            schema_name="fabric.evidence_bundle",
            schema_version="1.0",
            classification=None,
            encrypted_at_rest=False,
            field_level_encrypted=False,
            encryption_key_reference=None,
        ),
        created_at=manifest.created_at,
    )
    if artifact_manifest_profile_projection(manifest) != artifact_manifest_profile_projection(
        expected
    ):
        raise EvidencePayloadError("live_evidence_writer_profile_mismatch")


def build_composite_evidence_bundle(
    *,
    source_bundles: list[EvidenceBundle],
    composition_strategy: CompositionStrategy,
    merge_log: list[MergeLogEntry],
    store: FileSystemCAS,
    composed_by: str = "FederationEngine",
    deterministic: bool = True,
    deterministic_seed: str | None = None,
) -> EvidenceBundle:
    """
    Create a composite evidence bundle from multiple source bundles.

    Delegates to federation.evidence_aggregation for implementation.
    """
    from polisyos.fabric.connectors.federation.evidence_aggregation import (
        build_composite_evidence_bundle as _build_composite,
    )

    return _build_composite(
        source_bundles=source_bundles,
        composition_strategy=composition_strategy,
        merge_log=merge_log,
        store=store,
        composed_by=composed_by,
        deterministic=deterministic,
        deterministic_seed=deterministic_seed,
    )
