"""Public fabric evidence module API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import (
    EvidenceBundle,
    EvidenceBundleRef,
    EvidenceStep,
    IngestionExecutionContext,
    ProvenanceCoreRefModel,
)
from polisyos.fabric.provenance.core import ProvenanceCoreGraph, ProvenanceCoreRef
from polisyos.fabric.security import DataClassification, RetentionScope, resolve_artifact_governance

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore
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
    """
    Persist a ProvenanceCoreGraph to CAS and return a reference.
    """
    payload = graph.to_dict()
    stable_id = _require_payload_str(payload, "stable_id")
    ref = store.put_json(
        payload,
        opts=PutOptions(
            kind="fabric.provenance_graph",
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
            inputs=inputs,
            governance=resolve_artifact_governance(
                scope=RetentionScope.EVIDENCE_BUNDLE,
                classification=classification,
                encrypted_at_rest=encrypted_at_rest,
                field_level_encrypted=field_level_encrypted,
                encryption_key_reference=encryption_key_reference,
            ),
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
    """
    Persist an ``EvidenceBundle`` to CAS and return a strict ``EvidenceBundleRef``.

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
    selected_provenance = (
        bundle.provenance_ref is not None
        and bundle.provenance_ref.manifest_profile_sha256 is not None
    )
    bound_projection = bundle.execution_context is not None or selected_provenance
    inputs: list[InputRef] | None = None
    if bound_projection:
        inputs = [
            input_ref_from_artifact_ref(ref, role="fabric.ingestion.payload")
            for ref in bundle.sources
        ]
        selected_session = (
            bundle.execution_context.selected_record_session_ref
            if bundle.execution_context is not None
            else None
        )
        if selected_session is not None:
            inputs.append(
                input_ref_from_artifact_ref(
                    selected_session, role="fabric.ingestion.record_session"
                )
            )
        if bundle.provenance_ref is not None:
            inputs.append(
                input_ref_from_artifact_ref(
                    ArtifactRef(
                        artifact_id=ArtifactID.model_validate(bundle.provenance_ref.artifact_id),
                        kind="fabric.provenance_graph",
                        media_type="application/json",
                        manifest_profile_sha256=bundle.provenance_ref.manifest_profile_sha256,
                    ),
                    role="fabric.ingestion.provenance",
                )
            )
    write_options = PutOptions(
        kind="fabric.evidence_bundle",
        media_type="application/json",
        schema=SchemaInfo(
            name=schema_name,
            version="2.0" if bound_projection else schema_version,
        ),
        inputs=inputs,
        governance=resolve_artifact_governance(
            scope=RetentionScope.EVIDENCE_BUNDLE,
            classification=classification,
            encrypted_at_rest=encrypted_at_rest,
            field_level_encrypted=field_level_encrypted,
            encryption_key_reference=encryption_key_reference,
        ),
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
