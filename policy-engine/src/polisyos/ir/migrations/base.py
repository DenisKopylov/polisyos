"""Public migrations base module API."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

MigrationFn = Callable[[dict[str, Any]], dict[str, Any]]

_MIGRATIONS: dict[str, dict[str, "MigrationEdge"]] = {}
_SCHEMA_REGISTRY: dict[str, dict[str, "SchemaCompatibilityRule"]] = {}


class MigrationError(ValueError):
    """Base error for IR migration compatibility failures."""


class MigrationSchemaVersionError(MigrationError):
    """Raised when a migrator returns an incompatible schema_version."""


class MigrationCompatibilityError(MigrationError):
    """Raised when a migration edge violates declared schema compatibility policy."""


class CompatibilityMode(str, Enum):
    """Declared direct-read compatibility mode for a schema version."""

    FULL = "full"
    BACKWARD = "backward"
    FORWARD = "forward"
    NONE = "none"


@dataclass(frozen=True)
class SchemaCompatibilityRule:
    """Compatibility declaration for one artifact schema version."""

    artifact: str
    version: str
    mode: CompatibilityMode
    readable_versions: frozenset[str] = frozenset()
    writable_versions: frozenset[str] = frozenset()
    additive_optional_fields: frozenset[str] = frozenset()
    removed_fields: frozenset[str] = frozenset()
    renamed_fields: frozenset[tuple[str, str]] = frozenset()
    canonical_defaults: frozenset[tuple[str, str]] = frozenset()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class MigrationEdge:
    """Registered migration edge with its declared compatibility intent."""

    to_version: str
    fn: MigrationFn
    compatibility: CompatibilityMode


@dataclass(frozen=True)
class SchemaCompatibilityDecision:
    """Rule-based answer for producer/consumer schema negotiation."""

    artifact: str
    producer_version: str
    consumer_version: str
    can_read: bool
    mode: CompatibilityMode
    migration_required: bool = False
    reason: str = ""


def register_schema_version(
    artifact: str,
    version: str,
    *,
    compatibility: CompatibilityMode | str = CompatibilityMode.NONE,
    readable_versions: tuple[str, ...] = (),
    writable_versions: tuple[str, ...] = (),
    additive_optional_fields: tuple[str, ...] = (),
    removed_fields: tuple[str, ...] = (),
    renamed_fields: tuple[tuple[str, str], ...] = (),
    canonical_defaults: tuple[tuple[str, str], ...] = (),
    notes: tuple[str, ...] = (),
) -> SchemaCompatibilityRule:
    """Register a schema version and its direct compatibility policy."""

    rule = SchemaCompatibilityRule(
        artifact=str(artifact),
        version=str(version),
        mode=_coerce_compatibility_mode(compatibility),
        readable_versions=frozenset(str(item) for item in readable_versions),
        writable_versions=frozenset(str(item) for item in writable_versions),
        additive_optional_fields=frozenset(str(item) for item in additive_optional_fields),
        removed_fields=frozenset(str(item) for item in removed_fields),
        renamed_fields=frozenset((str(old), str(new)) for old, new in renamed_fields),
        canonical_defaults=frozenset(
            (str(field), str(value)) for field, value in canonical_defaults
        ),
        notes=tuple(str(item) for item in notes),
    )
    _SCHEMA_REGISTRY.setdefault(rule.artifact, {})[rule.version] = rule
    return rule


def get_schema_rule(artifact: str, version: str) -> SchemaCompatibilityRule | None:
    """Return the registered compatibility rule for ``artifact@version``."""

    return _SCHEMA_REGISTRY.get(str(artifact), {}).get(str(version))


def negotiate_schema_version(
    artifact: str,
    producer_version: str,
    consumer_version: str,
) -> SchemaCompatibilityDecision:
    """Return whether a consumer can read a producer payload version.

    The decision distinguishes direct compatibility from migration-required
    compatibility so release checks can fail closed instead of treating all
    schema-version mismatches as equivalent.
    """

    artifact = str(artifact)
    producer_version = str(producer_version)
    consumer_version = str(consumer_version)
    if producer_version == consumer_version:
        return SchemaCompatibilityDecision(
            artifact=artifact,
            producer_version=producer_version,
            consumer_version=consumer_version,
            can_read=True,
            mode=CompatibilityMode.FULL,
            reason="same_version",
        )

    consumer_rule = get_schema_rule(artifact, consumer_version)
    if consumer_rule is None:
        return SchemaCompatibilityDecision(
            artifact=artifact,
            producer_version=producer_version,
            consumer_version=consumer_version,
            can_read=False,
            mode=CompatibilityMode.NONE,
            reason="unknown_consumer_version",
        )

    direct = _direct_compatibility_decision(
        consumer_rule,
        producer_version=producer_version,
    )
    if direct is not None:
        return direct

    if _has_migration_path(artifact, producer_version, consumer_version):
        return SchemaCompatibilityDecision(
            artifact=artifact,
            producer_version=producer_version,
            consumer_version=consumer_version,
            can_read=True,
            mode=consumer_rule.mode,
            migration_required=True,
            reason="migration_available",
        )

    return SchemaCompatibilityDecision(
        artifact=artifact,
        producer_version=producer_version,
        consumer_version=consumer_version,
        can_read=False,
        mode=CompatibilityMode.NONE,
        reason="not_compatible",
    )


def can_read_schema(artifact: str, producer_version: str, consumer_version: str) -> bool:
    """Return whether ``consumer_version`` can read ``producer_version``."""

    return negotiate_schema_version(artifact, producer_version, consumer_version).can_read


def register_migration(
    artifact: str,
    from_version: str,
    to_version: str,
    *,
    compatibility: CompatibilityMode | str = CompatibilityMode.BACKWARD,
) -> Callable[[MigrationFn], MigrationFn]:
    """Register migration."""
    def decorator(fn: MigrationFn) -> MigrationFn:
        mode = _coerce_compatibility_mode(compatibility)
        _MIGRATIONS.setdefault(artifact, {})[from_version] = MigrationEdge(
            to_version=to_version,
            fn=fn,
            compatibility=mode,
        )
        register_schema_version(
            artifact,
            from_version,
            compatibility=CompatibilityMode.FORWARD,
            writable_versions=(to_version,),
        )
        register_schema_version(
            artifact,
            to_version,
            compatibility=mode,
            readable_versions=(from_version,) if mode in _BACKWARD_READ_MODES else (),
        )
        return fn

    return decorator


def _apply_migration(
    data: dict[str, Any],
    *,
    artifact: str,
    from_version: str,
    to_version: str,
    fn: MigrationFn,
) -> dict[str, Any]:
    migrated = fn(data)
    if not isinstance(migrated, dict):
        raise MigrationError(
            f"Migrator for '{artifact}' from {from_version} to {to_version} "
            "must return a dict"
        )

    declared_version = migrated.get("schema_version")
    if declared_version is not None and str(declared_version) != to_version:
        raise MigrationSchemaVersionError(
            f"Migrator for '{artifact}' from {from_version} to {to_version} "
            f"returned schema_version={declared_version!r}"
        )

    result = dict(migrated)
    result["schema_version"] = to_version
    return result


def migrate_artifact(data: dict[str, Any], artifact: str, target_version: str) -> dict[str, Any]:
    """Migrate artifact helper.

    Migration functions may omit ``schema_version`` and let the framework stamp
    the registered ``to_version``. If they return their own ``schema_version``,
    it must match the registered edge; incompatible versions are errors rather
    than being silently overwritten.
    """
    if "schema_version" not in data:
        raise ValueError(f"Missing schema_version for artifact '{artifact}'")
    current_version = str(data["schema_version"])
    if current_version == target_version:
        return data

    visited = set()
    while current_version != target_version:
        if current_version in visited:
            raise ValueError(
                f"Migration loop detected for '{artifact}': {current_version} -> {target_version}"
            )
        visited.add(current_version)

        artifact_migrations = _MIGRATIONS.get(artifact, {})
        if current_version not in artifact_migrations:
            raise ValueError(
                f"No migrator for '{artifact}' from {current_version} to {target_version}"
            )
        edge = artifact_migrations[current_version]
        next_version = edge.to_version
        data = _apply_migration(
            data,
            artifact=artifact,
            from_version=current_version,
            to_version=next_version,
            fn=edge.fn,
        )
        current_version = next_version

    return data


_BACKWARD_READ_MODES = {
    CompatibilityMode.FULL,
    CompatibilityMode.BACKWARD,
}


def _coerce_compatibility_mode(mode: CompatibilityMode | str) -> CompatibilityMode:
    if isinstance(mode, CompatibilityMode):
        return mode
    try:
        return CompatibilityMode(str(mode).lower())
    except ValueError as exc:
        raise MigrationCompatibilityError(f"Unknown compatibility mode: {mode!r}") from exc


def _direct_compatibility_decision(
    consumer_rule: SchemaCompatibilityRule,
    *,
    producer_version: str,
) -> SchemaCompatibilityDecision | None:
    if producer_version in consumer_rule.readable_versions:
        return SchemaCompatibilityDecision(
            artifact=consumer_rule.artifact,
            producer_version=producer_version,
            consumer_version=consumer_rule.version,
            can_read=True,
            mode=consumer_rule.mode,
            reason="declared_readable_version",
        )

    producer_tuple = _parse_version_tuple(producer_version)
    consumer_tuple = _parse_version_tuple(consumer_rule.version)
    if producer_tuple is None or consumer_tuple is None or producer_tuple[0] != consumer_tuple[0]:
        return None

    if consumer_rule.mode is CompatibilityMode.FULL:
        return SchemaCompatibilityDecision(
            artifact=consumer_rule.artifact,
            producer_version=producer_version,
            consumer_version=consumer_rule.version,
            can_read=True,
            mode=CompatibilityMode.FULL,
            reason="same_major_full",
        )
    if consumer_rule.mode is CompatibilityMode.BACKWARD and producer_tuple <= consumer_tuple:
        return SchemaCompatibilityDecision(
            artifact=consumer_rule.artifact,
            producer_version=producer_version,
            consumer_version=consumer_rule.version,
            can_read=True,
            mode=CompatibilityMode.BACKWARD,
            reason="same_major_backward",
        )
    if consumer_rule.mode is CompatibilityMode.FORWARD and producer_tuple >= consumer_tuple:
        return SchemaCompatibilityDecision(
            artifact=consumer_rule.artifact,
            producer_version=producer_version,
            consumer_version=consumer_rule.version,
            can_read=True,
            mode=CompatibilityMode.FORWARD,
            reason="same_major_forward",
        )
    return None


def _has_migration_path(artifact: str, from_version: str, to_version: str) -> bool:
    visited: set[str] = set()
    current = from_version
    while current != to_version:
        if current in visited:
            return False
        visited.add(current)
        edge = _MIGRATIONS.get(artifact, {}).get(current)
        if edge is None:
            return False
        current = edge.to_version
    return True


def _parse_version_tuple(version: str) -> tuple[int, int] | None:
    parts = str(version).split(".")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


__all__ = [
    "CompatibilityMode",
    "MigrationCompatibilityError",
    "MigrationEdge",
    "MigrationError",
    "MigrationFn",
    "MigrationSchemaVersionError",
    "SchemaCompatibilityDecision",
    "SchemaCompatibilityRule",
    "can_read_schema",
    "get_schema_rule",
    "migrate_artifact",
    "negotiate_schema_version",
    "register_migration",
    "register_schema_version",
]
