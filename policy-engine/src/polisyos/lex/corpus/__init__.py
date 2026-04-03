"""Facade for legal-document ingest, structure, and corpus indexing artifacts."""
from __future__ import annotations

from .index import (
    DocSourcePropsV1,
    ProvisionEntryV1,
    ProvisionIndexV1,
    VersionEntryV1,
    VersionIndexV1,
    load_doc_source_props,
    load_provision_index,
    load_version_index,
    persist_doc_source_props,
    persist_provision_index,
    persist_version_index,
)
from .ingest import ingest_legal_doc_bytes
from .structure import build_legal_structure
from .versioning import build_version_index, resolve_active_version

__all__ = [
    "DocSourcePropsV1",
    "ProvisionEntryV1",
    "ProvisionIndexV1",
    "VersionEntryV1",
    "VersionIndexV1",
    "build_legal_structure",
    "build_version_index",
    "ingest_legal_doc_bytes",
    "load_doc_source_props",
    "load_provision_index",
    "load_version_index",
    "persist_doc_source_props",
    "persist_provision_index",
    "persist_version_index",
    "resolve_active_version",
]
