"""Fabric ingestion runtime and provider dependencies."""

from __future__ import annotations

from polisyos.fabric.evidence.evidence import (
    load_provenance_graph,
    verify_live_ingestion_evidence_profile,
)

from . import ingestion as _ingestion_module
from ._source_evidence_schema import load_source_evidence_bundle
from .ingestion import (
    ConnectorManifestSpec,
    DatasetFetchSpec,
    PreTransformFetchResultSink,
    RawFetchResultSink,
    run_connectors_ingestion,
)
from .ingestion import _build_connector_provenance_graph as build_connector_provenance_graph
from .ingestion import _canon_scalar as canonicalize_ingestion_scalar
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
    "build_connector_provenance_graph",
    "build_filesystem_artifact_store",
    "canonicalize_ingestion_scalar",
    "load_provenance_graph",
    "load_source_collection",
    "load_source_evidence_bundle",
    "resolve_ingestion_dependencies",
    "run_connectors_ingestion",
    "verify_live_ingestion_evidence_profile",
]


def __getattr__(name: str) -> object:
    value = getattr(_ingestion_module, name)
    globals()[name] = value
    return value
