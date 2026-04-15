"""Storage abstraction for Fabric consumers."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.fabric.storage.port import StoragePort
from polisyos.fabric.storage.tenant_cas import (
    TenantScopedCAS,
    infer_tenant_id_from_cas_root,
    resolve_cas_store,
    tenant_scoped_cas_root,
)

if TYPE_CHECKING:
    from polisyos.fabric.storage.duckdb_adapter import DuckDBStorageAdapter
    from polisyos.fabric.storage.memory_adapter import InMemoryStorageAdapter

__all__ = [
    "StoragePort",
    "DuckDBStorageAdapter",
    "InMemoryStorageAdapter",
    "TenantScopedCAS",
    "infer_tenant_id_from_cas_root",
    "resolve_cas_store",
    "tenant_scoped_cas_root",
]


def __getattr__(name: str) -> Any:
    if name == "DuckDBStorageAdapter":
        from polisyos.fabric.storage.duckdb_adapter import DuckDBStorageAdapter

        return DuckDBStorageAdapter
    if name == "InMemoryStorageAdapter":
        from polisyos.fabric.storage.memory_adapter import InMemoryStorageAdapter

        return InMemoryStorageAdapter
    raise AttributeError(name)
