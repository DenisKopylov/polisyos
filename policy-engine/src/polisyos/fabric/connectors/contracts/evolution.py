"""
Schema evolution tracking and migration support.

Handles:
- Detecting schema changes between versions
- Classifying changes (breaking vs non-breaking)
- Generating migration recommendations
- Tracking evolution history
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from polisyos.fabric.connectors.contracts.schema import DataSchema, FieldSpec


class ChangeType(str, Enum):
    """Types of schema changes."""

    # Non-breaking (minor version)
    FIELD_ADDED = "field_added"
    FIELD_MADE_NULLABLE = "field_made_nullable"
    TYPE_WIDENED = "type_widened"
    BOUNDS_RELAXED = "bounds_relaxed"
    ALLOWED_VALUES_EXPANDED = "allowed_values_expanded"
    PRECISION_WIDENED = "precision_widened"
    SCALE_WIDENED = "scale_widened"
    PATTERN_RELAXED = "pattern_relaxed"
    MAX_LENGTH_RELAXED = "max_length_relaxed"
    REQUIRED_COMPLETENESS_RELAXED = "required_completeness_relaxed"
    ALLOWED_NULL_FIELDS_EXPANDED = "allowed_null_fields_expanded"

    # Breaking (major version)
    FIELD_REMOVED = "field_removed"
    FIELD_MADE_REQUIRED = "field_made_required"
    TYPE_NARROWED = "type_narrowed"
    TYPE_CHANGED = "type_changed"
    BOUNDS_TIGHTENED = "bounds_tightened"
    ALLOWED_VALUES_RESTRICTED = "allowed_values_restricted"
    PRECISION_NARROWED = "precision_narrowed"
    SCALE_NARROWED = "scale_narrowed"
    PATTERN_TIGHTENED = "pattern_tightened"
    PATTERN_CHANGED = "pattern_changed"
    MAX_LENGTH_TIGHTENED = "max_length_tightened"
    PRIMARY_KEY_CHANGED = "primary_key_changed"
    UNIT_CHANGED = "unit_changed"
    SEMANTIC_TYPE_CHANGED = "semantic_type_changed"
    ELEMENT_TYPE_CHANGED = "element_type_changed"
    TIME_DIMENSION_CHANGED = "time_dimension_changed"
    TIME_GRANULARITY_CHANGED = "time_granularity_changed"
    GEO_DIMENSION_CHANGED = "geo_dimension_changed"
    GEO_GRANULARITY_CHANGED = "geo_granularity_changed"
    REQUIRED_COMPLETENESS_TIGHTENED = "required_completeness_tightened"
    ALLOWED_NULL_FIELDS_RESTRICTED = "allowed_null_fields_restricted"

    # Patch-level (documentation/metadata)
    DESCRIPTION_UPDATED = "description_updated"
    SOURCE_UPDATED = "source_updated"
    TAGS_UPDATED = "tags_updated"

    def is_breaking(self) -> bool:
        """Check if this change type is breaking."""
        return self in {
            ChangeType.FIELD_REMOVED,
            ChangeType.FIELD_MADE_REQUIRED,
            ChangeType.TYPE_NARROWED,
            ChangeType.TYPE_CHANGED,
            ChangeType.BOUNDS_TIGHTENED,
            ChangeType.ALLOWED_VALUES_RESTRICTED,
            ChangeType.PRECISION_NARROWED,
            ChangeType.SCALE_NARROWED,
            ChangeType.PATTERN_TIGHTENED,
            ChangeType.PATTERN_CHANGED,
            ChangeType.MAX_LENGTH_TIGHTENED,
            ChangeType.PRIMARY_KEY_CHANGED,
            ChangeType.UNIT_CHANGED,
            ChangeType.SEMANTIC_TYPE_CHANGED,
            ChangeType.ELEMENT_TYPE_CHANGED,
            ChangeType.TIME_DIMENSION_CHANGED,
            ChangeType.TIME_GRANULARITY_CHANGED,
            ChangeType.GEO_DIMENSION_CHANGED,
            ChangeType.GEO_GRANULARITY_CHANGED,
            ChangeType.REQUIRED_COMPLETENESS_TIGHTENED,
            ChangeType.ALLOWED_NULL_FIELDS_RESTRICTED,
        }

    def bump_level(self) -> str:
        """Return recommended bump level for this change type."""
        if self.is_breaking():
            return "major"
        if self in {
            ChangeType.DESCRIPTION_UPDATED,
            ChangeType.SOURCE_UPDATED,
            ChangeType.TAGS_UPDATED,
        }:
            return "patch"
        return "minor"


@dataclass(frozen=True)
class SchemaChange:
    """Represents a single change between schema versions."""

    change_type: ChangeType
    field_name: str | None
    old_value: str | None
    new_value: str | None
    description: str

    @property
    def is_breaking(self) -> bool:
        return self.change_type.is_breaking()


class EvolutionReport(BaseModel):
    """Report of differences between two schema versions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_schema_id: str
    source_version: str
    target_schema_id: str
    target_version: str

    changes: tuple[SchemaChange, ...]

    is_compatible: bool = Field(
        description="True if target is backward-compatible with source"
    )
    recommended_version_bump: str = Field(description="major, minor, or patch")

    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def breaking_changes(self) -> list[SchemaChange]:
        return [c for c in self.changes if c.is_breaking]

    @property
    def non_breaking_changes(self) -> list[SchemaChange]:
        return [c for c in self.changes if not c.is_breaking]


class SchemaEvolution:
    """
    Analyzes and tracks schema evolution.

    Usage:
        evolution = SchemaEvolution()
        report = evolution.compare(old_schema, new_schema)

        if not report.is_compatible:
            for change in report.breaking_changes:
                print(f"Breaking: {change.description}")
    """

    def compare(self, source: DataSchema, target: DataSchema) -> EvolutionReport:
        """
        Compare two schemas and generate evolution report.

        Args:
            source: The original/older schema
            target: The new/updated schema

        Returns:
            EvolutionReport with all detected changes
        """
        changes: list[SchemaChange] = []

        source_fields = {f.name: f for f in source.fields}
        target_fields = {f.name: f for f in target.fields}

        for name in source_fields:
            if name not in target_fields:
                changes.append(
                    SchemaChange(
                        change_type=ChangeType.FIELD_REMOVED,
                        field_name=name,
                        old_value=source_fields[name].data_type.value,
                        new_value=None,
                        description=f"Field '{name}' was removed",
                    )
                )

        for name in target_fields:
            if name not in source_fields:
                changes.append(
                    SchemaChange(
                        change_type=ChangeType.FIELD_ADDED,
                        field_name=name,
                        old_value=None,
                        new_value=target_fields[name].data_type.value,
                        description=
                        f"Field '{name}' was added ({target_fields[name].data_type.value})",
                    )
                )

        for name in source_fields:
            if name in target_fields:
                field_changes = self._compare_fields(
                    source_fields[name], target_fields[name]
                )
                changes.extend(field_changes)

        if source.primary_key != target.primary_key:
            changes.append(
                SchemaChange(
                    change_type=ChangeType.PRIMARY_KEY_CHANGED,
                    field_name=None,
                    old_value=str(source.primary_key),
                    new_value=str(target.primary_key),
                    description=
                    f"Primary key changed from {source.primary_key} to {target.primary_key}",
                )
            )

        if source.time_dimension != target.time_dimension:
            changes.append(
                SchemaChange(
                    change_type=ChangeType.TIME_DIMENSION_CHANGED,
                    field_name=None,
                    old_value=source.time_dimension,
                    new_value=target.time_dimension,
                    description=
                    f"Time dimension changed from {source.time_dimension} to {target.time_dimension}",
                )
            )

        if source.time_granularity != target.time_granularity:
            changes.append(
                SchemaChange(
                    change_type=ChangeType.TIME_GRANULARITY_CHANGED,
                    field_name=None,
                    old_value=str(source.time_granularity),
                    new_value=str(target.time_granularity),
                    description=
                    "Time granularity changed from "
                    f"{source.time_granularity} to {target.time_granularity}",
                )
            )

        if source.geo_dimension != target.geo_dimension:
            changes.append(
                SchemaChange(
                    change_type=ChangeType.GEO_DIMENSION_CHANGED,
                    field_name=None,
                    old_value=source.geo_dimension,
                    new_value=target.geo_dimension,
                    description=
                    f"Geo dimension changed from {source.geo_dimension} to {target.geo_dimension}",
                )
            )

        if source.geo_granularity != target.geo_granularity:
            changes.append(
                SchemaChange(
                    change_type=ChangeType.GEO_GRANULARITY_CHANGED,
                    field_name=None,
                    old_value=str(source.geo_granularity),
                    new_value=str(target.geo_granularity),
                    description=
                    "Geo granularity changed from "
                    f"{source.geo_granularity} to {target.geo_granularity}",
                )
            )

        if source.required_completeness != target.required_completeness:
            if target.required_completeness > source.required_completeness:
                change_type = ChangeType.REQUIRED_COMPLETENESS_TIGHTENED
            else:
                change_type = ChangeType.REQUIRED_COMPLETENESS_RELAXED
            changes.append(
                SchemaChange(
                    change_type=change_type,
                    field_name=None,
                    old_value=str(source.required_completeness),
                    new_value=str(target.required_completeness),
                    description=
                    "Required completeness changed from "
                    f"{source.required_completeness} to {target.required_completeness}",
                )
            )

        if source.allowed_null_fields != target.allowed_null_fields:
            if target.allowed_null_fields.issuperset(source.allowed_null_fields):
                change_type = ChangeType.ALLOWED_NULL_FIELDS_EXPANDED
            else:
                change_type = ChangeType.ALLOWED_NULL_FIELDS_RESTRICTED
            changes.append(
                SchemaChange(
                    change_type=change_type,
                    field_name=None,
                    old_value=str(source.allowed_null_fields),
                    new_value=str(target.allowed_null_fields),
                    description=
                    "Allowed null fields changed from "
                    f"{source.allowed_null_fields} to {target.allowed_null_fields}",
                )
            )

        if source.description != target.description:
            changes.append(
                SchemaChange(
                    change_type=ChangeType.DESCRIPTION_UPDATED,
                    field_name=None,
                    old_value=source.description[:50] if source.description else None,
                    new_value=target.description[:50] if target.description else None,
                    description="Schema description updated",
                )
            )

        if source.source != target.source:
            changes.append(
                SchemaChange(
                    change_type=ChangeType.SOURCE_UPDATED,
                    field_name=None,
                    old_value=source.source or None,
                    new_value=target.source or None,
                    description="Schema source updated",
                )
            )

        if source.tags != target.tags:
            changes.append(
                SchemaChange(
                    change_type=ChangeType.TAGS_UPDATED,
                    field_name=None,
                    old_value=str(source.tags),
                    new_value=str(target.tags),
                    description="Schema tags updated",
                )
            )

        # Determine compatibility and version bump
        has_breaking = any(c.is_breaking for c in changes)
        bump_levels = {c.change_type.bump_level() for c in changes}

        if has_breaking:
            is_compatible = False
            version_bump = "major"
        elif "minor" in bump_levels:
            is_compatible = True
            version_bump = "minor"
        else:
            is_compatible = True
            version_bump = "patch"

        return EvolutionReport(
            source_schema_id=source.schema_id,
            source_version=str(source.version),
            target_schema_id=target.schema_id,
            target_version=str(target.version),
            changes=tuple(changes),
            is_compatible=is_compatible,
            recommended_version_bump=version_bump,
        )

    def _compare_fields(self, source: FieldSpec, target: FieldSpec) -> list[SchemaChange]:
        """Compare two field specs and return changes."""
        changes: list[SchemaChange] = []
        name = source.name

        if source.data_type != target.data_type:
            if source.data_type.is_compatible_with(target.data_type):
                changes.append(
                    SchemaChange(
                        change_type=ChangeType.TYPE_WIDENED,
                        field_name=name,
                        old_value=source.data_type.value,
                        new_value=target.data_type.value,
                        description=
                        f"Field '{name}' type widened from {source.data_type.value} to {target.data_type.value}",
                    )
                )
            elif target.data_type.is_compatible_with(source.data_type):
                changes.append(
                    SchemaChange(
                        change_type=ChangeType.TYPE_NARROWED,
                        field_name=name,
                        old_value=source.data_type.value,
                        new_value=target.data_type.value,
                        description=
                        f"Field '{name}' type narrowed from {source.data_type.value} to {target.data_type.value}",
                    )
                )
            else:
                changes.append(
                    SchemaChange(
                        change_type=ChangeType.TYPE_CHANGED,
                        field_name=name,
                        old_value=source.data_type.value,
                        new_value=target.data_type.value,
                        description=
                        f"Field '{name}' type changed from {source.data_type.value} to {target.data_type.value}",
                    )
                )

        if source.element_type != target.element_type:
            changes.append(
                SchemaChange(
                    change_type=ChangeType.ELEMENT_TYPE_CHANGED,
                    field_name=name,
                    old_value=source.element_type.value if source.element_type else None,
                    new_value=target.element_type.value if target.element_type else None,
                    description=
                    f"Field '{name}' element type changed from {source.element_type} to {target.element_type}",
                )
            )

        if source.unit != target.unit:
            changes.append(
                SchemaChange(
                    change_type=ChangeType.UNIT_CHANGED,
                    field_name=name,
                    old_value=source.unit.unit_id if source.unit else None,
                    new_value=target.unit.unit_id if target.unit else None,
                    description=
                    f"Field '{name}' unit changed from {source.unit} to {target.unit}",
                )
            )

        if source.semantic_type != target.semantic_type:
            changes.append(
                SchemaChange(
                    change_type=ChangeType.SEMANTIC_TYPE_CHANGED,
                    field_name=name,
                    old_value=source.semantic_type.value if source.semantic_type else None,
                    new_value=target.semantic_type.value if target.semantic_type else None,
                    description=
                    f"Field '{name}' semantic type changed from {source.semantic_type} to {target.semantic_type}",
                )
            )

        if source.nullable != target.nullable:
            if target.nullable:
                changes.append(
                    SchemaChange(
                        change_type=ChangeType.FIELD_MADE_NULLABLE,
                        field_name=name,
                        old_value="required",
                        new_value="nullable",
                        description=f"Field '{name}' changed from required to nullable",
                    )
                )
            else:
                changes.append(
                    SchemaChange(
                        change_type=ChangeType.FIELD_MADE_REQUIRED,
                        field_name=name,
                        old_value="nullable",
                        new_value="required",
                        description=f"Field '{name}' changed from nullable to required",
                    )
                )

        if source.bounds != target.bounds:
            src_min, src_max = source.bounds
            tgt_min, tgt_max = target.bounds

            relaxed = True
            if tgt_min is not None and (src_min is None or tgt_min > src_min):
                relaxed = False
            if tgt_max is not None and (src_max is None or tgt_max < src_max):
                relaxed = False

            changes.append(
                SchemaChange(
                    change_type=
                    ChangeType.BOUNDS_RELAXED if relaxed else ChangeType.BOUNDS_TIGHTENED,
                    field_name=name,
                    old_value=str(source.bounds),
                    new_value=str(target.bounds),
                    description=
                    f"Field '{name}' bounds {'relaxed' if relaxed else 'tightened'} from {source.bounds} to {target.bounds}",
                )
            )

        if source.allowed_values != target.allowed_values:
            if source.allowed_values and target.allowed_values:
                removed = source.allowed_values - target.allowed_values
                added = target.allowed_values - source.allowed_values

                if removed:
                    changes.append(
                        SchemaChange(
                            change_type=ChangeType.ALLOWED_VALUES_RESTRICTED,
                            field_name=name,
                            old_value=str(removed),
                            new_value=None,
                            description=
                            f"Field '{name}' removed allowed values: {removed}",
                        )
                    )
                if added:
                    changes.append(
                        SchemaChange(
                            change_type=ChangeType.ALLOWED_VALUES_EXPANDED,
                            field_name=name,
                            old_value=None,
                            new_value=str(added),
                            description=
                            f"Field '{name}' added allowed values: {added}",
                        )
                    )
            elif target.allowed_values is None:
                changes.append(
                    SchemaChange(
                        change_type=ChangeType.ALLOWED_VALUES_EXPANDED,
                        field_name=name,
                        old_value=str(source.allowed_values),
                        new_value="any",
                        description=f"Field '{name}' allowed_values constraint removed",
                    )
                )
            else:
                changes.append(
                    SchemaChange(
                        change_type=ChangeType.ALLOWED_VALUES_RESTRICTED,
                        field_name=name,
                        old_value="any",
                        new_value=str(target.allowed_values),
                        description=f"Field '{name}' allowed_values constraint added",
                    )
                )

        if source.precision != target.precision:
            if source.precision is not None and target.precision is not None:
                if target.precision > source.precision:
                    change_type = ChangeType.PRECISION_WIDENED
                else:
                    change_type = ChangeType.PRECISION_NARROWED
            else:
                change_type = ChangeType.PRECISION_NARROWED
            changes.append(
                SchemaChange(
                    change_type=change_type,
                    field_name=name,
                    old_value=str(source.precision),
                    new_value=str(target.precision),
                    description=
                    f"Field '{name}' precision changed from {source.precision} to {target.precision}",
                )
            )

        if source.scale != target.scale:
            if source.scale is not None and target.scale is not None:
                if target.scale > source.scale:
                    change_type = ChangeType.SCALE_WIDENED
                else:
                    change_type = ChangeType.SCALE_NARROWED
            else:
                change_type = ChangeType.SCALE_NARROWED
            changes.append(
                SchemaChange(
                    change_type=change_type,
                    field_name=name,
                    old_value=str(source.scale),
                    new_value=str(target.scale),
                    description=
                    f"Field '{name}' scale changed from {source.scale} to {target.scale}",
                )
            )

        if source.pattern != target.pattern:
            if target.pattern is None and source.pattern is not None:
                change_type = ChangeType.PATTERN_RELAXED
            elif target.pattern is not None and source.pattern is None:
                change_type = ChangeType.PATTERN_TIGHTENED
            else:
                change_type = ChangeType.PATTERN_CHANGED
            changes.append(
                SchemaChange(
                    change_type=change_type,
                    field_name=name,
                    old_value=source.pattern,
                    new_value=target.pattern,
                    description=f"Field '{name}' pattern changed",
                )
            )

        if source.max_length != target.max_length:
            if source.max_length is None and target.max_length is not None:
                change_type = ChangeType.MAX_LENGTH_TIGHTENED
            elif source.max_length is not None and target.max_length is None:
                change_type = ChangeType.MAX_LENGTH_RELAXED
            elif target.max_length is not None and source.max_length is not None:
                if target.max_length > source.max_length:
                    change_type = ChangeType.MAX_LENGTH_RELAXED
                else:
                    change_type = ChangeType.MAX_LENGTH_TIGHTENED
            else:
                change_type = ChangeType.MAX_LENGTH_TIGHTENED
            changes.append(
                SchemaChange(
                    change_type=change_type,
                    field_name=name,
                    old_value=str(source.max_length),
                    new_value=str(target.max_length),
                    description=
                    f"Field '{name}' max_length changed from {source.max_length} to {target.max_length}",
                )
            )

        if source.description != target.description:
            changes.append(
                SchemaChange(
                    change_type=ChangeType.DESCRIPTION_UPDATED,
                    field_name=name,
                    old_value=source.description[:50] if source.description else None,
                    new_value=target.description[:50] if target.description else None,
                    description=f"Field '{name}' description updated",
                )
            )

        return changes

    def can_migrate(self, source: DataSchema, target: DataSchema) -> bool:
        """Check if data can be safely migrated between schemas."""
        report = self.compare(source, target)
        return report.is_compatible

    def generate_migration_sql(
        self,
        source: DataSchema,
        target: DataSchema,
        table_name: str,
    ) -> list[str]:
        """
        Generate DuckDB SQL statements for schema migration.

        Note: This generates ALTER TABLE statements. Review carefully
        before executing as some changes may require data transformation.
        """
        report = self.compare(source, target)
        statements: list[str] = []

        for change in report.changes:
            if change.change_type == ChangeType.FIELD_ADDED:
                field = target.get_field(change.field_name) if change.field_name else None
                if field:
                    col_def = field.to_duckdb_column_def()
                    statements.append(
                        f"ALTER TABLE {table_name} ADD COLUMN {col_def};"
                    )

            elif change.change_type == ChangeType.FIELD_REMOVED:
                statements.append(
                    f"ALTER TABLE {table_name} DROP COLUMN {change.field_name};"
                )

            elif change.change_type == ChangeType.TYPE_WIDENED:
                field = target.get_field(change.field_name) if change.field_name else None
                if field:
                    new_type = field.data_type.to_duckdb_type()
                    statements.append(
                        f"ALTER TABLE {table_name} ALTER COLUMN {change.field_name} TYPE {new_type};"
                    )

        return statements
