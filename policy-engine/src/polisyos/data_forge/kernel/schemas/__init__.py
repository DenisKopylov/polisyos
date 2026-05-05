"""Versioned schema registry contracts for Data Forge."""

from __future__ import annotations

from .evolution import (
    SchemaChangeKind,
    SchemaEvolutionCheck,
    SchemaEvolutionRule,
    SchemaFieldChange,
    assert_schema_evolution_compatible,
    evaluate_schema_evolution,
)
from .migrations import (
    RegisteredSchemaMigration,
    SchemaMigration,
    SchemaMigrationPlan,
    SchemaMigrationRegistry,
)
from .registry import CompatibilityMode, SchemaRegistry, SchemaVersion

__all__ = [
    "CompatibilityMode",
    "RegisteredSchemaMigration",
    "SchemaChangeKind",
    "SchemaEvolutionCheck",
    "SchemaEvolutionRule",
    "SchemaFieldChange",
    "SchemaMigration",
    "SchemaMigrationPlan",
    "SchemaMigrationRegistry",
    "SchemaRegistry",
    "SchemaVersion",
    "assert_schema_evolution_compatible",
    "evaluate_schema_evolution",
]
