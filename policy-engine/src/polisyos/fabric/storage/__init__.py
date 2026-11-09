"""Storage abstraction for Fabric consumers."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from polisyos.fabric.storage.port import StoragePort
from polisyos.fabric.storage.tenant_cas import (
    TenantScopedCAS,
    TenantSidecarScope,
    infer_tenant_id_from_cas_root,
    resolve_cas_store,
    tenant_scoped_cas_root,
)

if TYPE_CHECKING:
    from polisyos.fabric.storage.duckdb_adapter import DuckDBStorageAdapter
    from polisyos.fabric.storage.memory_adapter import InMemoryStorageAdapter

__all__ = [
    "DuckDBStorageAdapter",
    "InMemoryStorageAdapter",
    "StoragePort",
    "TenantScopedCAS",
    "TenantSidecarScope",
    "infer_tenant_id_from_cas_root",
    "resolve_cas_store",
    "tenant_scoped_cas_root",
]

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "DuckDBStorageAdapter": (
        "polisyos.fabric.storage.duckdb_adapter",
        "DuckDBStorageAdapter",
    ),
    "InMemoryStorageAdapter": (
        "polisyos.fabric.storage.memory_adapter",
        "InMemoryStorageAdapter",
    ),
}


def __getattr__(name: str) -> object:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(name)
    module_name, attribute_name = _LAZY_EXPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value
