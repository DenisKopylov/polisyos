"""Stable Fabric facade for connector ingestion, world-query, and catalog APIs.

The package exports the supported entry points for connector-backed acquisition and materialized
world reads while keeping heavy dependencies lazy. ``__all__`` defines the stable facade; catalog
contracts are still available through lazy attribute loading, and ``world`` is exposed as a lazy
subpackage for lower-level materialization utilities.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "AccessRef",
    "AuthoredText",
    "FabricDecisionData",
    "FabricDecisionDataCoverage",
    "FabricDecisionDataResponse",
    "LineageRef",
    "QualityRef",
    "ReplayRef",
    "SourceContractRef",
    "TemporalRef",
    "TypedGap",
    "UnitRef",
    "WorldQueryError",
    "WorldQueryRequest",
    "execute_world_query",
    "fabric_claim_to_authored_text",
    "fabric_event_to_authored_text",
    "fabric_fact_to_quantity_value",
    "fabric_get_data",
    "query_claims",
    "query_events",
    "query_world_table",
    "run_connectors_ingestion",
    "world",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "AccessRef": ("polisyos.fabric.decision_data", "AccessRef"),
    "AuthoredText": ("polisyos.fabric.decision_data", "AuthoredText"),
    "FabricDecisionData": ("polisyos.fabric.decision_data", "FabricDecisionData"),
    "FabricDecisionDataCoverage": (
        "polisyos.fabric.decision_data",
        "FabricDecisionDataCoverage",
    ),
    "FabricDecisionDataResponse": (
        "polisyos.fabric.decision_data",
        "FabricDecisionDataResponse",
    ),
    "fabric_claim_to_authored_text": (
        "polisyos.fabric.decision_data",
        "fabric_claim_to_authored_text",
    ),
    "fabric_event_to_authored_text": (
        "polisyos.fabric.decision_data",
        "fabric_event_to_authored_text",
    ),
    "fabric_fact_to_quantity_value": (
        "polisyos.fabric.decision_data",
        "fabric_fact_to_quantity_value",
    ),
    "LineageRef": ("polisyos.fabric.decision_data", "LineageRef"),
    "QualityRef": ("polisyos.fabric.decision_data", "QualityRef"),
    "ReplayRef": ("polisyos.fabric.decision_data", "ReplayRef"),
    "SourceContractRef": ("polisyos.fabric.decision_data", "SourceContractRef"),
    "TemporalRef": ("polisyos.fabric.decision_data", "TemporalRef"),
    "TypedGap": ("polisyos.fabric.decision_data", "TypedGap"),
    "UnitRef": ("polisyos.fabric.decision_data", "UnitRef"),
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
    """Load Fabric exports or the ``world`` subpackage lazily.

    Raises:
        AttributeError: If ``name`` is not a supported Fabric facade symbol.
    """
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
    """Return eager globals plus lazily exported Fabric symbols."""
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
