"""Canonical connectors ingestion entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from polisyos.core.contracts.fabric import EvidenceBundleRef
from polisyos.fabric.ingestion import ConnectorManifestSpec, DatasetFetchSpec, run_connectors_ingestion

__all__ = [
    "ConnectorManifestSpec",
    "DatasetFetchSpec",
    "run_connectors_ingestion",
    "run",
]


def run(
    *,
    connector_manifest: dict[str, Any] | Path | str | ConnectorManifestSpec,
    source: str,
    license_name: str,
    cas_root: Path | None = Path(".polisyos"),
) -> EvidenceBundleRef | None:
    return run_connectors_ingestion(
        connector_manifest=connector_manifest,
        source=source,
        license_name=license_name,
        cas_root=cas_root,
    )

