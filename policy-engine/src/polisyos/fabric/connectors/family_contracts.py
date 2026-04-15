"""Connector family capability contracts for non-HTTP source surfaces."""
from __future__ import annotations

from dataclasses import dataclass, field

from polisyos.ir.connectors import ConnectorCapability


@dataclass(frozen=True)
class ConnectorFamilyContract:
    """Declarative capability envelope for one connector family."""

    connector_family: str
    description: str
    required_capabilities: tuple[ConnectorCapability, ...]
    optional_capabilities: tuple[ConnectorCapability, ...] = ()
    schema_introspection_modes: tuple[str, ...] = ()
    accepted_schemes: tuple[str, ...] = ()
    lineage_requirements: tuple[str, ...] = ()
    profile_scaffold: dict[str, str] = field(default_factory=dict)


FILE_CONNECTOR_CONTRACT = ConnectorFamilyContract(
    connector_family="files",
    description=(
        "Local and remote file readers must support explicit format selection, "
        "schema inference, content hashing, and deterministic row ordering."
    ),
    required_capabilities=(
        ConnectorCapability.FULL_FETCH,
        ConnectorCapability.SCHEMA_INTROSPECTION,
    ),
    optional_capabilities=(
        ConnectorCapability.STREAMING,
        ConnectorCapability.FRESHNESS_CHECK,
    ),
    schema_introspection_modes=("sample_inference", "format_metadata"),
    accepted_schemes=("file", "http", "https"),
    lineage_requirements=("source_location", "format", "content_hash"),
    profile_scaffold={
        "profile_id": "files_local",
        "connector_family": "files",
        "base_url": "file:///tmp/example.csv",
    },
)

OBJECT_STORAGE_CONNECTOR_CONTRACT = ConnectorFamilyContract(
    connector_family="object_storage",
    description=(
        "Object storage readers must preserve bucket/key provenance, provider "
        "metadata, and object etag/version identifiers when available."
    ),
    required_capabilities=(
        ConnectorCapability.FULL_FETCH,
        ConnectorCapability.SCHEMA_INTROSPECTION,
    ),
    optional_capabilities=(
        ConnectorCapability.FRESHNESS_CHECK,
        ConnectorCapability.INCREMENTAL_FETCH,
    ),
    schema_introspection_modes=("sample_inference", "provider_metadata"),
    accepted_schemes=("file", "s3", "gs", "az"),
    lineage_requirements=("provider", "bucket", "object_key", "etag"),
    profile_scaffold={
        "profile_id": "object_storage_public",
        "connector_family": "object_storage",
        "base_url": "s3://example-bucket/example.jsonl",
    },
)

DATABASE_CONNECTOR_CONTRACT = ConnectorFamilyContract(
    connector_family="sql",
    description=(
        "Database connectors must expose query/table provenance, schema "
        "introspection, and deterministic pagination/query ordering."
    ),
    required_capabilities=(
        ConnectorCapability.FULL_FETCH,
        ConnectorCapability.SCHEMA_INTROSPECTION,
        ConnectorCapability.CUSTOM_QUERY,
    ),
    optional_capabilities=(
        ConnectorCapability.INCREMENTAL_FETCH,
        ConnectorCapability.DATE_RANGE_FILTER,
        ConnectorCapability.FRESHNESS_CHECK,
    ),
    schema_introspection_modes=("information_schema", "query_probe"),
    accepted_schemes=("postgresql", "postgres", "sqlite", "duckdb"),
    lineage_requirements=("database_url", "query", "table", "schema_name"),
    profile_scaffold={
        "profile_id": "sql_local",
        "connector_family": "sql",
        "base_url": "sqlite:///:memory:",
    },
)

API_PROTOCOL_CONNECTOR_CONTRACT = ConnectorFamilyContract(
    connector_family="graphql",
    description=(
        "Protocol-native API connectors must keep transport-specific query "
        "payloads and schema metadata explainable at the connector boundary."
    ),
    required_capabilities=(
        ConnectorCapability.FULL_FETCH,
        ConnectorCapability.CUSTOM_QUERY,
        ConnectorCapability.SCHEMA_INTROSPECTION,
    ),
    optional_capabilities=(
        ConnectorCapability.DATE_RANGE_FILTER,
        ConnectorCapability.INCREMENTAL_FETCH,
        ConnectorCapability.RATE_LIMIT_AWARE,
    ),
    schema_introspection_modes=("protocol_introspection", "sample_inference"),
    accepted_schemes=("http", "https"),
    lineage_requirements=("endpoint", "query_document", "variables"),
    profile_scaffold={
        "profile_id": "graphql_public",
        "connector_family": "graphql",
        "base_url": "https://example.com/graphql",
    },
)

SPATIAL_CONNECTOR_CONTRACT = ConnectorFamilyContract(
    connector_family="geojson",
    description=(
        "Spatial connectors must preserve CRS, geometry type coverage, and "
        "feature lineage alongside tabular property extraction."
    ),
    required_capabilities=(
        ConnectorCapability.FULL_FETCH,
        ConnectorCapability.SCHEMA_INTROSPECTION,
    ),
    optional_capabilities=(
        ConnectorCapability.DATE_RANGE_FILTER,
        ConnectorCapability.STREAMING,
    ),
    schema_introspection_modes=("feature_properties", "spatial_metadata"),
    accepted_schemes=("file", "http", "https"),
    lineage_requirements=("source_location", "crs", "geometry_types"),
    profile_scaffold={
        "profile_id": "geojson_public",
        "connector_family": "geojson",
        "base_url": "file:///tmp/example.geojson",
    },
)

STREAM_CONNECTOR_CONTRACT = ConnectorFamilyContract(
    connector_family="stream",
    description=(
        "Streaming/event connectors must provide chunk/message lineage, "
        "resumable fetch hints where possible, and quarantine-ready message IDs."
    ),
    required_capabilities=(
        ConnectorCapability.FULL_FETCH,
        ConnectorCapability.STREAMING,
        ConnectorCapability.SCHEMA_INTROSPECTION,
    ),
    optional_capabilities=(
        ConnectorCapability.RESUMABLE,
        ConnectorCapability.INCREMENTAL_FETCH,
        ConnectorCapability.RATE_LIMIT_AWARE,
    ),
    schema_introspection_modes=("message_sample", "stream_metadata"),
    accepted_schemes=("file", "http", "https", "nats", "kafka", "pulsar", "kinesis"),
    lineage_requirements=("stream_url", "subject_or_topic", "message_ids"),
    profile_scaffold={
        "profile_id": "stream_local",
        "connector_family": "stream",
        "base_url": "nats://localhost:4222",
    },
)

CONNECTOR_FAMILY_CONTRACTS = {
    contract.connector_family: contract
    for contract in (
        FILE_CONNECTOR_CONTRACT,
        OBJECT_STORAGE_CONNECTOR_CONTRACT,
        DATABASE_CONNECTOR_CONTRACT,
        API_PROTOCOL_CONNECTOR_CONTRACT,
        SPATIAL_CONNECTOR_CONTRACT,
        STREAM_CONNECTOR_CONTRACT,
    )
}


def contract_for_family(connector_family: str) -> ConnectorFamilyContract:
    """Resolve the canonical contract for one connector family."""

    return CONNECTOR_FAMILY_CONTRACTS[str(connector_family)]


__all__ = [
    "API_PROTOCOL_CONNECTOR_CONTRACT",
    "CONNECTOR_FAMILY_CONTRACTS",
    "ConnectorFamilyContract",
    "DATABASE_CONNECTOR_CONTRACT",
    "FILE_CONNECTOR_CONTRACT",
    "OBJECT_STORAGE_CONNECTOR_CONTRACT",
    "SPATIAL_CONNECTOR_CONTRACT",
    "STREAM_CONNECTOR_CONTRACT",
    "contract_for_family",
]
