"""Public fabric evidence module API."""
from __future__ import annotations

import json

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import (
    EvidenceBundle,
    EvidenceBundleRef,
    EvidenceStep,
    ProvenanceCoreRefModel,
)
from polisyos.fabric.provenance.core import ProvenanceCoreGraph, ProvenanceCoreRef
from polisyos.fabric.quality import QualityIndicators


def build_evidence_bundle(
    *,
    sources: list[ArtifactRef] | None = None,
    transforms: list[EvidenceStep] | None = None,
    trust_policy_id: str | None = None,
    notes: list[str] | None = None,
    provenance_ref: ProvenanceCoreRef | None = None,
    quality_indicators: dict[str, QualityIndicators] | None = None,
) -> EvidenceBundle:
    """Build evidence bundle."""
    prov_model = None
    if provenance_ref is not None:
        prov_model = ProvenanceCoreRefModel(
            graph_id=provenance_ref.graph_id,
            stable_id=provenance_ref.stable_id,
            artifact_id=provenance_ref.artifact_id,
        )
    quality_payload = None
    if quality_indicators is not None:
        quality_payload = {
            metric_id: indicators.to_dict()
            for metric_id, indicators in quality_indicators.items()
        }
    return EvidenceBundle(
        sources=sources or [],
        transforms=transforms or [],
        trust_policy_id=trust_policy_id,
        notes=notes or [],
        provenance_ref=prov_model,
        quality_indicators=quality_payload,
    )


def persist_provenance_graph(
    store: FileSystemCAS,
    graph: ProvenanceCoreGraph,
    *,
    schema_name: str = "fabric.provenance_graph",
    schema_version: str = "1.0",
) -> ProvenanceCoreRef:
    """
    Persist a ProvenanceCoreGraph to CAS and return a reference.
    """
    payload = graph.to_dict()
    stable_id = payload["stable_id"]
    ref = store.put_json(
        payload,
        opts=PutOptions(
            kind="fabric.provenance_graph",
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
        ),
    )
    return ProvenanceCoreRef(
        graph_id=graph.graph_id,
        stable_id=stable_id,
        artifact_id=str(ref.artifact_id),
    )


def load_provenance_graph(
    store: FileSystemCAS,
    ref: ProvenanceCoreRef,
) -> ProvenanceCoreGraph:
    """
    Load a ProvenanceCoreGraph from CAS by reference.

    Raises:
        ValueError: If stable_id verification fails
    """
    payload = store.get_bytes(ArtifactID.model_validate(ref.artifact_id))
    data = json.loads(payload.decode("utf-8"))
    graph = ProvenanceCoreGraph.from_dict(data)

    computed_stable_id = graph.compute_stable_id()
    if computed_stable_id != ref.stable_id:
        raise ValueError(
            "Provenance graph integrity check failed: "
            f"expected {ref.stable_id}, got {computed_stable_id}"
        )

    return graph


def persist_evidence_bundle(
    store: FileSystemCAS,
    bundle: EvidenceBundle,
    *,
    schema_name: str = "fabric.evidence_bundle",
    schema_version: str = "1.0",
) -> EvidenceBundleRef:
    """
    Сохраняет EvidenceBundle в CAS и возвращает строгий EvidenceBundleRef.
    """
    ref = store.put_json(
        bundle.model_dump(),
        opts=PutOptions(
            kind="fabric.evidence_bundle",
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
        ),
    )
    return EvidenceBundleRef.model_validate(ref.model_dump())


def build_composite_evidence_bundle(
    *,
    source_bundles: list[EvidenceBundle],
    composition_strategy,
    merge_log: list,
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
