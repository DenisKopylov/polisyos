from __future__ import annotations

import importlib

import pytest

import polisyos.data_forge as data_forge
import polisyos.data_forge.kernel.schemas as canonical_schemas
from polisyos.data_forge.errors import SchemaCompatibilityError
from polisyos.data_forge.kernel.schemas import (
    CompatibilityMode,
    SchemaChangeKind,
    SchemaEvolutionRule,
    SchemaMigrationPlan,
    SchemaMigrationRegistry,
    SchemaRegistry,
    SchemaVersion,
    assert_schema_evolution_compatible,
    evaluate_schema_evolution,
)
from polisyos.data_forge.kernel.schemas.evolution import (
    SchemaEvolutionRule as EvolutionSchemaEvolutionRule,
)
from polisyos.data_forge.kernel.schemas.migrations import (
    SchemaMigrationPlan as MigrationSchemaMigrationPlan,
)
from polisyos.data_forge.kernel.schemas.migrations import (
    SchemaMigrationRegistry as MigrationSchemaMigrationRegistry,
)
from polisyos.data_forge.kernel.schemas.registry import (
    CompatibilityMode as RegistryCompatibilityMode,
)
from polisyos.data_forge.kernel.schemas.registry import SchemaRegistry as RegistrySchemaRegistry
from polisyos.data_forge.kernel.schemas.registry import SchemaVersion as RegistrySchemaVersion


def test_dfk_01_canonical_schema_exports_preserve_registry_identity() -> None:
    """The canonical Data Forge schema package remains the working owner."""
    assert canonical_schemas.CompatibilityMode is CompatibilityMode
    assert canonical_schemas.SchemaRegistry is SchemaRegistry
    assert canonical_schemas.SchemaVersion is SchemaVersion
    assert CompatibilityMode is RegistryCompatibilityMode
    assert SchemaRegistry is RegistrySchemaRegistry
    assert SchemaVersion is RegistrySchemaVersion
    assert SchemaEvolutionRule is EvolutionSchemaEvolutionRule
    assert SchemaMigrationPlan is MigrationSchemaMigrationPlan
    assert SchemaMigrationRegistry is MigrationSchemaMigrationRegistry
    assert data_forge.CompatibilityMode is CompatibilityMode
    assert data_forge.SchemaRegistry is SchemaRegistry
    assert data_forge.SchemaVersion is SchemaVersion


def test_dfk_01_canonical_registry_evolution_and_migration_behave() -> None:
    """Registry, evolution, and migration behavior survive legacy-surface retirement."""
    schema_id = "dfk.canonical"
    previous = SchemaVersion(
        schema_id=schema_id,
        version="1.0.0",
        compat_mode=CompatibilityMode.BACKWARD,
        json_schema={
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    )
    candidate = SchemaVersion(
        schema_id=schema_id,
        version="2.0.0",
        compat_mode=CompatibilityMode.FULL,
        json_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["id", "title"],
        },
    )

    registry = SchemaRegistry()
    assert registry.register(previous) is previous
    assert registry.register(candidate) is candidate
    assert registry.get(schema_id, "1.0.0") is previous
    assert registry.latest(schema_id) is candidate
    assert registry.list_versions(schema_id) == (previous, candidate)

    breaking = evaluate_schema_evolution(previous, candidate)
    assert breaking.compatible is False
    assert breaking.changes[0].change_kind is SchemaChangeKind.ADD_REQUIRED_FIELD
    with pytest.raises(SchemaCompatibilityError):
        assert_schema_evolution_compatible(previous, candidate)

    rule = SchemaEvolutionRule(
        schema_id=schema_id,
        from_version="1.0.0",
        to_version="2.0.0",
        change_kind=SchemaChangeKind.ADD_REQUIRED_FIELD,
        rationale="the migration supplies title for existing payloads",
    )
    allowed = assert_schema_evolution_compatible(previous, candidate, rules=(rule,))
    assert allowed.compatible is True

    migrations = SchemaMigrationRegistry()
    plan = SchemaMigrationPlan(
        schema_id=schema_id,
        from_version="1.0.0",
        to_version="2.0.0",
        migration_id="dfk.add_title",
    )
    migrations.register(
        plan,
        lambda payload: {**payload, "title": "untitled"},
    )

    assert migrations.plan_path(
        schema_id=schema_id,
        from_version="1.0.0",
        to_version="2.0.0",
    ) == (plan,)
    assert migrations.apply(
        {"id": "record-1"},
        schema_id=schema_id,
        from_version="1.0.0",
        to_version="2.0.0",
    ) == {"id": "record-1", "title": "untitled"}


@pytest.mark.parametrize(
    "legacy_module",
    [
        "polisyos.data_forge.kernel.pipeline.schemas",
        "polisyos.data_forge.kernel.schemas.codegen",
        "polisyos.foundry.domain.schema",
    ],
)
def test_dfk_01_compatibility_pending_surfaces_remain_importable(legacy_module: str) -> None:
    """Keep unresolved public FQNs until census and an owner decision are complete."""
    module = importlib.import_module(legacy_module)
    assert module.__name__ == legacy_module


def test_dfk_01_compatibility_pending_surfaces_preserve_current_identity() -> None:
    """Pending surfaces retain their public and canonical identities for compatibility."""
    pipeline_schemas = importlib.import_module("polisyos.data_forge.kernel.pipeline.schemas")
    assert pipeline_schemas.CompatibilityMode is CompatibilityMode
    assert pipeline_schemas.SchemaRegistry is SchemaRegistry
    assert pipeline_schemas.SchemaVersion is SchemaVersion

    codegen = importlib.import_module("polisyos.data_forge.kernel.schemas.codegen")
    generated_schema_module = codegen.GeneratedSchemaModule
    assert generated_schema_module.__module__ == "polisyos.data_forge.kernel.schemas.codegen"
    assert set(generated_schema_module.model_fields) == {
        "module_name",
        "schema_id",
        "schema_version",
    }

    foundry_schema = importlib.import_module("polisyos.foundry.domain.schema")
    assert foundry_schema.AgentType.__module__ == "polisyos.foundry.domain.schema"
    assert foundry_schema.RegionProfile.__module__ == "polisyos.foundry.domain.schema"
    assert foundry_schema.SimulationConfig.__module__ == "polisyos.foundry.domain.schema"
    assert set(foundry_schema.RegionProfile.model_fields) == {
        "region_id",
        "avg_income",
        "unemployment_rate",
        "tech_level",
    }
    assert set(foundry_schema.SimulationConfig.model_fields) == {
        "n_agents",
        "n_steps",
        "seed",
    }


def test_dfk_01_mechanisms_tombstone_is_not_importable() -> None:
    """The confirmed empty mechanisms tombstone remains an absence contract."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("polisyos.foundry.domain.mechanisms")
