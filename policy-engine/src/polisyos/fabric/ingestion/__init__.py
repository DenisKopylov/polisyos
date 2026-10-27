"""Fabric ingestion runtime and provider dependencies."""

from __future__ import annotations

from . import ingestion as _ingestion_module
from .ingestion import (
    ConnectorManifestSpec,
    DatasetFetchSpec,
    PreTransformFetchResultSink,
    RawFetchResultSink,
    run_connectors_ingestion,
)
from .ingestion_providers import (
    IngestionDependencies,
    build_filesystem_artifact_store,
    resolve_ingestion_dependencies,
)
from .source_collection import SourceCollection, SourceCollectionMember, load_source_collection

__all__ = [
    "ConnectorManifestSpec",
    "DatasetFetchSpec",
    "IngestionDependencies",
    "PreTransformFetchResultSink",
    "RawFetchResultSink",
    "SourceCollection",
    "SourceCollectionMember",
    "build_filesystem_artifact_store",
    "load_source_collection",
    "resolve_ingestion_dependencies",
    "run_connectors_ingestion",
]


def __getattr__(name: str) -> object:
    value = getattr(_ingestion_module, name)
    globals()[name] = value
    return value
