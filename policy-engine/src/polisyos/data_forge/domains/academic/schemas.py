"""Academic schema contracts for Data Forge Phase 2."""

from __future__ import annotations

from polisyos.data_forge.kernel.schemas import CompatibilityMode, SchemaRegistry, SchemaVersion

from .batch_assets import ACADEMIC_BATCH_STAGE_ORDER


def _schema_contract(
    schema_id: str,
    description: str,
    *,
    required: tuple[str, ...],
) -> SchemaVersion:
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
            "properties": {
                field: {
                    "type": [
                        "string",
                        "number",
                        "integer",
                        "boolean",
                        "array",
                        "object",
                    ]
                }
                for field in required
            },
            "additionalProperties": True,
        },
    )


ACADEMIC_ASSET_SCHEMA_CONTRACTS: tuple[SchemaVersion, ...] = (
    _schema_contract(
        "academic.works.raw",
        "Raw harvested academic works.",
        required=("work_id", "source"),
    ),
    _schema_contract(
        "academic.works.normalized",
        "Normalized academic work metadata.",
        required=("work_id", "title", "publication_year"),
    ),
    _schema_contract(
        "academic.works.fulltext",
        "Resolved academic fulltext payloads and provenance.",
        required=("work_id", "resolver", "fulltext_ref"),
    ),
    _schema_contract(
        "academic.claims.extracted",
        "Extracted academic claims before publish filtering.",
        required=("claim_id", "work_id", "claim_type", "evidence"),
    ),
    _schema_contract(
        "academic.claims.published",
        "Published academic claims consumed by runtime readers.",
        required=("claim_id", "canonical_variable", "support_score"),
    ),
    _schema_contract(
        "academic.skg",
        "Scholar knowledge graph DuckDB artifact contract.",
        required=("db_path", "schema_version", "tables"),
    ),
    _schema_contract(
        "academic.pipeline.readiness",
        "Academic consumer readiness report.",
        required=("readiness", "benchmark_metrics", "qc_metrics"),
    ),
)

ACADEMIC_BATCH_SCHEMA_CONTRACTS: tuple[SchemaVersion, ...] = tuple(
    _schema_contract(
        f"academic.batch.{stage_id}",
        f"Academic batch stage artifact contract for {stage_id}.",
        required=("stage", "status", "artifacts"),
    )
    for stage_id in ACADEMIC_BATCH_STAGE_ORDER
)

ACADEMIC_SCHEMA_CONTRACTS: tuple[SchemaVersion, ...] = (
    *ACADEMIC_ASSET_SCHEMA_CONTRACTS,
    *ACADEMIC_BATCH_SCHEMA_CONTRACTS,
)


def build_academic_schema_registry() -> SchemaRegistry:
    """Build a registry containing all academic Data Forge schema contracts."""
    registry = SchemaRegistry()
    for schema in ACADEMIC_SCHEMA_CONTRACTS:
        registry.register(schema)
    return registry


__all__ = [
    "ACADEMIC_ASSET_SCHEMA_CONTRACTS",
    "ACADEMIC_BATCH_SCHEMA_CONTRACTS",
    "ACADEMIC_SCHEMA_CONTRACTS",
    "build_academic_schema_registry",
]
