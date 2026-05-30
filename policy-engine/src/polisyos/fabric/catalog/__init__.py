"""Metric-level data contract catalog for Fabric."""

from .binding import DataContractSchemaBinding, MetricBinding
from .contract import DataContract, DataContractCollection, DataType, Granularity, PIITier
from .data_requirement_adapter import (
    FABRIC_DATA_REQUIREMENT_BINDINGS_SCHEMA_VERSION,
    build_source_contract_requirement_bindings,
)
from .discovery import (
    DatasetCatalogEntry,
    DatasetCatalogStalenessReport,
    DatasetCatalogVectorMetadata,
    DatasetDiscoveryBenchmarkPack,
    DatasetDiscoveryCandidate,
    DatasetDiscoveryEvalCase,
    DatasetDiscoveryEvalOutcome,
    DatasetDiscoveryEvalReport,
    DatasetDiscoveryEvidence,
    DatasetResolutionPlan,
    SemanticDatasetCatalog,
    build_semantic_dataset_catalog,
)
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
    "FABRIC_DATA_REQUIREMENT_BINDINGS_SCHEMA_VERSION",
    "ContractHashMismatchError",
    "ContractNotFoundError",
    "ContractValidationError",
    "DataContract",
    "DataContractCollection",
    "DataContractRegistry",
    "DataContractSchemaBinding",
    "DataType",
    "DatasetCatalogEntry",
    "DatasetCatalogStalenessReport",
    "DatasetCatalogVectorMetadata",
    "DatasetDiscoveryBenchmarkPack",
    "DatasetDiscoveryCandidate",
    "DatasetDiscoveryEvalCase",
    "DatasetDiscoveryEvalOutcome",
    "DatasetDiscoveryEvalReport",
    "DatasetDiscoveryEvidence",
    "DatasetResolutionPlan",
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
    "SemanticDatasetCatalog",
    "SemanticSearchMatch",
    "SemanticVectorMetadata",
    "SourceBinding",
    "SourceBindingCollection",
    "SourceBindingRegistry",
    "build_semantic_dataset_catalog",
    "build_source_contract_requirement_bindings",
    "load_contract_collection",
]
