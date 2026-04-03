"""Public facade for Fabric world-query, catalog, and ingestion APIs."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "fabric_get_data",
    "execute_world_query",
    "query_claims",
    "query_events",
    "query_world_table",
    "run_connectors_ingestion",
    "WorldQueryError",
    "WorldQueryRequest",
    "world",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "fabric_get_data": ("polisyos.fabric._connector_bridge", "fabric_get_data"),
    "execute_world_query": ("polisyos.fabric.world_query", "execute_world_query"),
    "run_connectors_ingestion": ("polisyos.fabric.ingestion", "run_connectors_ingestion"),
    "query_claims": ("polisyos.fabric.world_query", "query_claims"),
    "query_events": ("polisyos.fabric.world_query", "query_events"),
    "query_world_table": ("polisyos.fabric.world_query", "query_world_table"),
    "WorldQueryError": ("polisyos.fabric.world_query", "WorldQueryError"),
    "WorldQueryRequest": ("polisyos.fabric.world_query", "WorldQueryRequest"),
    "ContractHashMismatchError": ("polisyos.fabric.catalog", "ContractHashMismatchError"),
    "ContractNotFoundError": ("polisyos.fabric.catalog", "ContractNotFoundError"),
    "ContractValidationError": ("polisyos.fabric.catalog", "ContractValidationError"),
    "DataContract": ("polisyos.fabric.catalog", "DataContract"),
    "DataContractCollection": ("polisyos.fabric.catalog", "DataContractCollection"),
    "DataContractRegistry": ("polisyos.fabric.catalog", "DataContractRegistry"),
    "DataContractSchemaBinding": ("polisyos.fabric.catalog", "DataContractSchemaBinding"),
    "DataType": ("polisyos.fabric.catalog", "DataType"),
    "Granularity": ("polisyos.fabric.catalog", "Granularity"),
    "MetricBinding": ("polisyos.fabric.catalog", "MetricBinding"),
    "MetricSearcher": ("polisyos.fabric.catalog", "MetricSearcher"),
    "PIITier": ("polisyos.fabric.catalog", "PIITier"),
    "SearchResponse": ("polisyos.fabric.catalog", "SearchResponse"),
    "SearchResult": ("polisyos.fabric.catalog", "SearchResult"),
    "load_contract_collection": ("polisyos.fabric.catalog", "load_contract_collection"),
}


def __getattr__(name: str) -> Any:
    if name == "world":
        module = importlib.import_module("polisyos.fabric.world")
        globals()[name] = module
        return module
    if name in _LAZY_IMPORTS:
        module_name, attr = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_name)
        value = getattr(module, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'polisyos.fabric' has no attribute '{name}'")


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
