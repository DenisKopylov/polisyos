"""Data Plane Orchestrator — single-call ingestion + snapshot production.

Solves the double-fetch problem: instead of ingesting data into CAS and then
re-fetching to build a DataSnapshot, the orchestrator reads ingestion artifacts
from CAS and assembles the snapshot directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import (
    DataSnapshot,
    DataSnapshotRef,
    EvidenceBundle,
    EvidenceBundleRef,
)

logger = get_logger(__name__)


@dataclass
class IngestionResult:
    """Unified result from orchestrated ingestion."""

    evidence_bundle_ref: EvidenceBundleRef | None = None
    data_snapshot_ref: DataSnapshotRef | None = None
    datasets_fetched: int = 0
    warnings: list[str] = field(default_factory=list)
    cursor_ref: str | None = None
    mode_effective: str | None = None


def run_orchestrated_ingestion(
    *,
    connector_manifest: Any,
    source: str,
    license_name: str,
    cas_root: Path,
    connection_config: Any | None = None,
    produce_snapshot: bool = True,
) -> IngestionResult:
    """Run ingestion and optionally produce a DataSnapshot.

    This avoids the double-fetch problem: data is fetched once during
    ingestion, cached in CAS, and the snapshot is built from cached
    artifacts.
    """
    from polisyos.fabric.ingestion import run_connectors_ingestion

    evidence_ref = run_connectors_ingestion(
        connector_manifest=connector_manifest,
        source=source,
        license_name=license_name,
        cas_root=cas_root,
        connection_config=connection_config,
    )

    datasets_fetched = 0
    if hasattr(connector_manifest, "datasets"):
        datasets_fetched = len(connector_manifest.datasets)
    elif isinstance(connector_manifest, dict):
        datasets_fetched = len(connector_manifest.get("datasets", []))

    if not produce_snapshot or evidence_ref is None:
        return IngestionResult(
            evidence_bundle_ref=evidence_ref,
            data_snapshot_ref=None,
            datasets_fetched=datasets_fetched,
        )

    cas_store = FileSystemCAS(cas_root)
    snapshot_ref = _build_snapshot_from_evidence(
        store=cas_store,
        evidence_ref=evidence_ref,
        datasets_fetched=datasets_fetched,
        source=source,
    )

    return IngestionResult(
        evidence_bundle_ref=evidence_ref,
        data_snapshot_ref=snapshot_ref,
        datasets_fetched=datasets_fetched,
    )


def _build_snapshot_from_evidence(
    *,
    store: FileSystemCAS,
    evidence_ref: EvidenceBundleRef,
    datasets_fetched: int,
    source: str,
) -> DataSnapshotRef | None:
    """Build a DataSnapshot from evidence bundle artifacts in CAS."""
    evidence_payload = from_canonical_bytes(store.get_bytes(evidence_ref.artifact_id))
    evidence_bundle = EvidenceBundle.model_validate(evidence_payload)

    if not evidence_bundle.sources:
        logger.warning("orchestrator: evidence bundle has no sources, skipping snapshot")
        return None

    # Use the first source artifact as the primary data reference
    data_ref = evidence_bundle.sources[0]

    # Build a quality report from evidence metadata
    quality_payload = {
        "source": f"orchestrated_ingestion:{source}",
        "datasets_count": datasets_fetched,
        "notes": evidence_bundle.notes,
    }
    quality_ref = store.put_json(
        quality_payload,
        PutOptions(
            kind="fabric.quality_report",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.fabric.DataQualityReport", version="1.0"
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    snapshot_inputs = [
        InputRef(artifact_id=evidence_ref.artifact_id, role="evidence_ref"),
        InputRef(artifact_id=data_ref.artifact_id, role="data_ref"),
        InputRef(artifact_id=quality_ref.artifact_id, role="quality_report_ref"),
    ]

    snapshot = DataSnapshot(
        data_ref=data_ref,
        evidence_ref=evidence_ref,
        quality_report_ref=quality_ref,
        stats={
            "datasets_fetched": datasets_fetched,
            "source": f"orchestrated_ingestion:{source}",
        },
        notes=[
            "fabric.data_plane.orchestrator",
            f"datasets={datasets_fetched}",
        ],
    )

    snapshot_art_ref = store.put_json(
        snapshot,
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.DataSnapshot", version="0.2.0"
            ),
            inputs=snapshot_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return DataSnapshotRef(artifact_id=snapshot_art_ref.artifact_id)


__all__ = ["IngestionResult", "run_orchestrated_ingestion"]
