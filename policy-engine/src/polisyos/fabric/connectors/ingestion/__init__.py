"""Connector-bounded Fabric ingestion entrypoints."""

from .connectors_ingestion import (
    ConnectorManifestSpec,
    DatasetFetchSpec,
    run,
    run_connectors_ingestion,
)

__all__ = [
    "ConnectorManifestSpec",
    "DatasetFetchSpec",
    "run",
    "run_connectors_ingestion",
]

