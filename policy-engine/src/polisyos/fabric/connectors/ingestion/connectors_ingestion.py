"""Canonical connectors ingestion entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from polisyos.fabric.ingestion import (
    ConnectorManifestSpec,
    DatasetFetchSpec,
    run_connectors_ingestion,
)

if TYPE_CHECKING:
    from polisyos.core.contracts.fabric import EvidenceBundleRef

__all__ = [
    "ConnectorManifestSpec",
    "DatasetFetchSpec",
    "run",
    "run_connectors_ingestion",
]


def run(
    *,
    connector_manifest: dict[str, Any] | Path | str | ConnectorManifestSpec,
    source: str,
    license_name: str,
    cas_root: Path | None = Path(".polisyos/cas"),
) -> EvidenceBundleRef | None:
    """Run connector ingestion and return its evidence-bundle reference.

    This public entrypoint forwards the manifest and source metadata to the
    canonical Fabric ingestion implementation.

    Args:
        connector_manifest: Manifest mapping, filesystem path, path string, or
            parsed :class:`ConnectorManifestSpec`.
        source: Source label recorded for the ingested data.
        license_name: License label recorded for the ingested data.
        cas_root: Optional local CAS root forwarded to the implementation.

    Returns:
        The evidence-bundle reference produced by ingestion, or ``None`` when
        the canonical implementation returns no bundle.
    """
    return run_connectors_ingestion(
        connector_manifest=connector_manifest,
        source=source,
        license_name=license_name,
        cas_root=cas_root,
    )
