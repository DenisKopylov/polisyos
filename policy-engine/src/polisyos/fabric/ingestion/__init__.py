"""Fabric ingestion runtime and provider dependencies."""

from __future__ import annotations

from typing import Any

from . import ingestion as _ingestion_module
from .ingestion import ConnectorManifestSpec, DatasetFetchSpec, run_connectors_ingestion
from .ingestion_providers import (
    IngestionDependencies,
    build_filesystem_artifact_store,
    resolve_ingestion_dependencies,
)

__all__ = [
    "ConnectorManifestSpec",
    "DatasetFetchSpec",
    "IngestionDependencies",
    "build_filesystem_artifact_store",
    "resolve_ingestion_dependencies",
    "run_connectors_ingestion",
]


def __getattr__(name: str) -> Any:
    value = getattr(_ingestion_module, name)
    globals()[name] = value
    return value
