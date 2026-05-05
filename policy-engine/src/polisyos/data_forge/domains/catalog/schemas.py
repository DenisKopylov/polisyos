"""Catalog schema contracts for Data Forge Phase 3."""

from __future__ import annotations

from polisyos.data_forge.kernel.schemas import CompatibilityMode, SchemaRegistry, SchemaVersion

from .source_modules import CORE_CATALOG_SOURCE_MODULES

CATALOG_BASE_SCHEMA_IDS: tuple[str, ...] = (
    "catalog.sources.raw",
    "catalog.sources.modules",
    "catalog.datasets.normalized",
    "catalog.sources.preflight",
    "catalog.observations",
    "catalog.index",
    "catalog.consumer.readiness",
)


def build_catalog_schema_registry() -> SchemaRegistry:
    """Build a registry containing catalog Data Forge schema contracts."""
    registry = SchemaRegistry()
    for schema in CATALOG_SCHEMA_CONTRACTS:
        registry.register(schema)
    return registry


def _schema_contract(schema_id: str, description: str, required: tuple[str, ...]) -> SchemaVersion:
    return SchemaVersion(
        schema_id=schema_id,
        version="1.0.0",
        compat_mode=CompatibilityMode.BACKWARD,
        json_schema={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": schema_id,
            "description": description,
            "type": "object",
            "required": list(required),
            "additionalProperties": True,
        },
    )


CATALOG_BASE_SCHEMA_CONTRACTS: tuple[SchemaVersion, ...] = tuple(
    _schema_contract(schema_id, f"Catalog asset contract for {schema_id}.", ("kind", "version"))
    for schema_id in CATALOG_BASE_SCHEMA_IDS
)

CATALOG_SOURCE_SCHEMA_CONTRACTS: tuple[SchemaVersion, ...] = tuple(
    _schema_contract(
        contract.schema_id,
        f"Catalog source-stage contract for {contract.source_id}:{contract.stage}.",
        ("source_id", "stage", "artifacts"),
    )
    for module in CORE_CATALOG_SOURCE_MODULES
    for contract in module.stage_contracts()
)

CATALOG_SCHEMA_CONTRACTS: tuple[SchemaVersion, ...] = (
    *CATALOG_BASE_SCHEMA_CONTRACTS,
    *CATALOG_SOURCE_SCHEMA_CONTRACTS,
)

__all__ = [
    "CATALOG_BASE_SCHEMA_CONTRACTS",
    "CATALOG_BASE_SCHEMA_IDS",
    "CATALOG_SCHEMA_CONTRACTS",
    "CATALOG_SOURCE_SCHEMA_CONTRACTS",
    "build_catalog_schema_registry",
]
