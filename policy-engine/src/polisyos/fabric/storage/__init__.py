"""Storage abstraction for Fabric consumers."""
from __future__ import annotations

from polisyos.fabric.storage.duckdb_adapter import DuckDBStorageAdapter
from polisyos.fabric.storage.memory_adapter import InMemoryStorageAdapter
from polisyos.fabric.storage.port import StoragePort

__all__ = [
    "StoragePort",
    "DuckDBStorageAdapter",
    "InMemoryStorageAdapter",
]

