"""Schema evolution checks for Data Forge publication contracts."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import Field

from polisyos.data_forge.errors import DataForgeValidationError, SchemaCompatibilityError
from polisyos.data_forge.kernel._base import DataForgeModel

if TYPE_CHECKING:
    from collections.abc import Iterable

    from polisyos.data_forge.kernel.schemas.registry import SchemaVersion


class SchemaChangeKind(str, Enum):
    """Known schema change families."""

    ADD_OPTIONAL_FIELD = "add_optional_field"
    ADD_REQUIRED_FIELD = "add_required_field"
    REMOVE_FIELD = "remove_field"
    TYPE_CHANGE = "type_change"
    METADATA_ONLY = "metadata_only"


class SchemaEvolutionRule(DataForgeModel):
    """Document why a schema change is allowed."""

    schema_id: str = Field(min_length=1)
    from_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    to_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    change_kind: SchemaChangeKind
    rationale: str = Field(min_length=1)


class SchemaFieldChange(DataForgeModel):
    """One schema-visible change found between two schema versions."""

    schema_id: str = Field(min_length=1)
    from_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    to_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    path: str = Field(min_length=1)
    change_kind: SchemaChangeKind
    allowed: bool = False
    message: str = Field(min_length=1)

    @property
    def breaking(self) -> bool:
        """Return whether this change requires an explicit evolution rule."""
        return self.change_kind in {
            SchemaChangeKind.ADD_REQUIRED_FIELD,
            SchemaChangeKind.REMOVE_FIELD,
            SchemaChangeKind.TYPE_CHANGE,
        }


class SchemaEvolutionCheck(DataForgeModel):
    """Compatibility result for a previous/candidate schema pair."""

    schema_id: str = Field(min_length=1)
    from_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    to_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    compatible: bool
    changes: tuple[SchemaFieldChange, ...] = Field(default_factory=tuple)

    @property
    def violations(self) -> tuple[SchemaFieldChange, ...]:
        """Return breaking changes that were not covered by an evolution rule."""
        return tuple(change for change in self.changes if change.breaking and not change.allowed)


def evaluate_schema_evolution(
    previous: SchemaVersion,
    candidate: SchemaVersion,
    *,
    rules: Iterable[SchemaEvolutionRule] = (),
) -> SchemaEvolutionCheck:
    """Compare two JSON-schema-like contracts and report compatibility.

    The check is intentionally conservative and focused on Data Forge artifact
    boundaries: required additions, field removals, and type changes require a
    matching evolution rule. Optional additions and metadata-only edits remain
    compatible without a rule.
    """
    if previous.schema_id != candidate.schema_id:
        raise DataForgeValidationError(
            f"schema ids differ: {previous.schema_id} != {candidate.schema_id}"
        )

    allowed_rules = tuple(
        rule
        for rule in rules
        if rule.schema_id == previous.schema_id
        and rule.from_version == previous.version
        and rule.to_version == candidate.version
    )
    changes = _field_changes(previous, candidate, allowed_rules)
    compatible = not any(change.breaking and not change.allowed for change in changes)
    return SchemaEvolutionCheck(
        schema_id=previous.schema_id,
        from_version=previous.version,
        to_version=candidate.version,
        compatible=compatible,
        changes=tuple(changes),
    )


def assert_schema_evolution_compatible(
    previous: SchemaVersion,
    candidate: SchemaVersion,
    *,
    rules: Iterable[SchemaEvolutionRule] = (),
) -> SchemaEvolutionCheck:
    """Return an evolution check or raise when a breaking change is uncovered."""
    check = evaluate_schema_evolution(previous, candidate, rules=rules)
    if not check.compatible:
        details = ", ".join(
            f"{violation.change_kind.value}:{violation.path}" for violation in check.violations
        )
        raise SchemaCompatibilityError(
            f"schema evolution is not compatible for {check.schema_id} "
            f"{check.from_version}->{check.to_version}: {details}"
        )
    return check


def _field_changes(
    previous: SchemaVersion,
    candidate: SchemaVersion,
    rules: tuple[SchemaEvolutionRule, ...],
) -> list[SchemaFieldChange]:
    previous_required = _required_fields(previous.json_schema)
    candidate_required = _required_fields(candidate.json_schema)
    previous_properties = _properties(previous.json_schema)
    candidate_properties = _properties(candidate.json_schema)

    changes: list[SchemaFieldChange] = []
    for field_name in sorted(
        (candidate_required - previous_required)
        & previous_properties.keys()
        & candidate_properties.keys()
    ):
        changes.append(
            _change(
                previous,
                candidate,
                path=f"/required/{field_name}",
                change_kind=SchemaChangeKind.ADD_REQUIRED_FIELD,
                message=f"existing field became required: {field_name}",
                rules=rules,
            )
        )

    for field_name in sorted(candidate_properties.keys() - previous_properties.keys()):
        change_kind = (
            SchemaChangeKind.ADD_REQUIRED_FIELD
            if field_name in candidate_required
            else SchemaChangeKind.ADD_OPTIONAL_FIELD
        )
        changes.append(
            _change(
                previous,
                candidate,
                path=f"/properties/{field_name}",
                change_kind=change_kind,
                message=f"field added: {field_name}",
                rules=rules,
            )
        )

    for field_name in sorted(previous_properties.keys() - candidate_properties.keys()):
        changes.append(
            _change(
                previous,
                candidate,
                path=f"/properties/{field_name}",
                change_kind=SchemaChangeKind.REMOVE_FIELD,
                message=f"field removed: {field_name}",
                rules=rules,
            )
        )

    for field_name in sorted(previous_properties.keys() & candidate_properties.keys()):
        previous_type = _schema_type(previous_properties[field_name])
        candidate_type = _schema_type(candidate_properties[field_name])
        if previous_type != candidate_type:
            changes.append(
                _change(
                    previous,
                    candidate,
                    path=f"/properties/{field_name}/type",
                    change_kind=SchemaChangeKind.TYPE_CHANGE,
                    message=f"field type changed: {field_name} {previous_type}->{candidate_type}",
                    rules=rules,
                )
            )

    if not changes and previous.json_schema != candidate.json_schema:
        changes.append(
            _change(
                previous,
                candidate,
                path="/",
                change_kind=SchemaChangeKind.METADATA_ONLY,
                message="schema metadata changed",
                rules=rules,
            )
        )
    return changes


def _change(
    previous: SchemaVersion,
    candidate: SchemaVersion,
    *,
    path: str,
    change_kind: SchemaChangeKind,
    message: str,
    rules: tuple[SchemaEvolutionRule, ...],
) -> SchemaFieldChange:
    allowed = not _requires_rule(change_kind) or any(
        rule.change_kind == change_kind for rule in rules
    )
    return SchemaFieldChange(
        schema_id=previous.schema_id,
        from_version=previous.version,
        to_version=candidate.version,
        path=path,
        change_kind=change_kind,
        allowed=allowed,
        message=message,
    )


def _requires_rule(change_kind: SchemaChangeKind) -> bool:
    return change_kind in {
        SchemaChangeKind.ADD_REQUIRED_FIELD,
        SchemaChangeKind.REMOVE_FIELD,
        SchemaChangeKind.TYPE_CHANGE,
    }


def _required_fields(schema: dict[str, object]) -> set[str]:
    raw_required = schema.get("required", ())
    if not isinstance(raw_required, list | tuple):
        return set()
    return {str(field_name) for field_name in raw_required}


def _properties(schema: dict[str, object]) -> dict[str, dict[str, Any]]:
    raw_properties = schema.get("properties", {})
    if not isinstance(raw_properties, dict):
        return {}
    properties: dict[str, dict[str, Any]] = {}
    for field_name, field_schema in raw_properties.items():
        if isinstance(field_schema, dict):
            properties[str(field_name)] = field_schema
        else:
            properties[str(field_name)] = {}
    return properties


def _schema_type(schema: dict[str, Any]) -> str:
    raw_type = schema.get("type", "")
    if isinstance(raw_type, list | tuple):
        return "|".join(str(item) for item in raw_type)
    return str(raw_type)


__all__ = [
    "SchemaChangeKind",
    "SchemaEvolutionCheck",
    "SchemaEvolutionRule",
    "SchemaFieldChange",
    "assert_schema_evolution_compatible",
    "evaluate_schema_evolution",
]
