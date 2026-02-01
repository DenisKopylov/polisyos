from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "ContractHashMismatchError",
    "ContractNotFoundError",
    "ContractValidationError",
    "DataContract",
    "DataContractCollection",
    "DataContractRegistry",
    "DataContractSchemaBinding",
    "DataType",
    "Granularity",
    "MetricBinding",
    "MetricSearcher",
    "PIITier",
    "SearchResponse",
    "SearchResult",
    "fabric_get_data",
    "load_contract_collection",
    "run_ingestion",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "fabric_get_data": ("polisyos.fabric._connector_bridge", "fabric_get_data"),
    "run_ingestion": ("polisyos.fabric.ingestion", "run_ingestion"),
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
    if name in _LAZY_IMPORTS:
        module_name, attr = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_name)
        value = getattr(module, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'polisyos.fabric' has no attribute '{name}'")


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
