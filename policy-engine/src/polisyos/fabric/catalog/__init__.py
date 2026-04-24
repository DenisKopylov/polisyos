"""Metric-level data contract catalog for Fabric."""

from .binding import DataContractSchemaBinding, MetricBinding
from .contract import DataContract, DataContractCollection, DataType, Granularity, PIITier
from .registry import ContractHashMismatchError, ContractNotFoundError, DataContractRegistry
from .resolver_fast_lane import FastLaneResolver, FastLaneResolveResult
from .search import MetricSearcher, SearchResponse, SearchResult
from .semantic import (
    SemanticCatalogDocument,
    SemanticCatalogIndex,
    SemanticSearchMatch,
    SemanticVectorMetadata,
)
from .source_bindings import SourceBinding, SourceBindingCollection, SourceBindingRegistry
from .validate import ContractValidationError, load_contract_collection

__all__ = [
    "ContractHashMismatchError",
    "ContractNotFoundError",
    "ContractValidationError",
    "DataContract",
    "DataContractCollection",
    "DataContractRegistry",
    "DataContractSchemaBinding",
    "DataType",
    "FastLaneResolveResult",
    "FastLaneResolver",
    "Granularity",
    "MetricBinding",
    "MetricSearcher",
    "PIITier",
    "SearchResponse",
    "SearchResult",
    "SemanticCatalogDocument",
    "SemanticCatalogIndex",
    "SemanticSearchMatch",
    "SemanticVectorMetadata",
    "SourceBinding",
    "SourceBindingCollection",
    "SourceBindingRegistry",
    "load_contract_collection",
]
