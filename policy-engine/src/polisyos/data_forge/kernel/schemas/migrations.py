"""Schema migration contracts and deterministic migration planning."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import Field

from polisyos.data_forge.errors import DataForgeValidationError
from polisyos.data_forge.kernel._base import DataForgeModel

SchemaMigration = Callable[[dict[str, object]], dict[str, object]]


class SchemaMigrationPlan(DataForgeModel):
    """Registered migration edge between two schema versions."""

    schema_id: str = Field(min_length=1)
    from_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    to_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    migration_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")


@dataclass(frozen=True, slots=True)
class RegisteredSchemaMigration:
    """Executable schema migration edge."""

    plan: SchemaMigrationPlan
    migration: SchemaMigration


@dataclass(slots=True)
class SchemaMigrationRegistry:
    """In-memory directed graph of schema migrations."""

    _migrations: dict[tuple[str, str, str], RegisteredSchemaMigration] = field(default_factory=dict)

    def register(
        self,
        plan: SchemaMigrationPlan,
        migration: SchemaMigration,
    ) -> RegisteredSchemaMigration:
        """Register one executable migration edge."""
        key = (plan.schema_id, plan.from_version, plan.to_version)
        if key in self._migrations:
            raise DataForgeValidationError(
                "schema migration already registered: "
                f"{plan.schema_id} {plan.from_version}->{plan.to_version}"
            )
        registered = RegisteredSchemaMigration(plan=plan, migration=migration)
        self._migrations[key] = registered
        return registered

    def get(self, schema_id: str, from_version: str, to_version: str) -> RegisteredSchemaMigration:
        """Return one registered migration edge."""
        try:
            return self._migrations[(schema_id, from_version, to_version)]
        except KeyError as exc:
            raise DataForgeValidationError(
                f"schema migration not registered: {schema_id} {from_version}->{to_version}"
            ) from exc

    def plan_path(
        self,
        *,
        schema_id: str,
        from_version: str,
        to_version: str,
    ) -> tuple[SchemaMigrationPlan, ...]:
        """Return the shortest migration path between two schema versions."""
        if from_version == to_version:
            return ()

        queue: deque[tuple[str, tuple[SchemaMigrationPlan, ...]]] = deque([(from_version, ())])
        visited = {from_version}
        while queue:
            current_version, current_path = queue.popleft()
            for registered in self._outgoing(schema_id, current_version):
                next_version = registered.plan.to_version
                next_path = (*current_path, registered.plan)
                if next_version == to_version:
                    return next_path
                if next_version not in visited:
                    visited.add(next_version)
                    queue.append((next_version, next_path))

        raise DataForgeValidationError(
            f"no schema migration path registered: {schema_id} {from_version}->{to_version}"
        )

    def apply(
        self,
        payload: dict[str, object],
        *,
        schema_id: str,
        from_version: str,
        to_version: str,
    ) -> dict[str, object]:
        """Apply registered migrations to a shallow copy of a JSON object payload."""
        migrated = dict(payload)
        for plan in self.plan_path(
            schema_id=schema_id,
            from_version=from_version,
            to_version=to_version,
        ):
            registered = self.get(plan.schema_id, plan.from_version, plan.to_version)
            migrated = registered.migration(dict(migrated))
            if not isinstance(migrated, dict):
                raise DataForgeValidationError(
                    f"schema migration returned non-object payload: {plan.migration_id}"
                )
        return migrated

    def _outgoing(
        self,
        schema_id: str,
        from_version: str,
    ) -> tuple[RegisteredSchemaMigration, ...]:
        migrations = [
            registered
            for key, registered in self._migrations.items()
            if key[0] == schema_id and key[1] == from_version
        ]
        return tuple(
            sorted(
                migrations,
                key=lambda registered: (
                    _semantic_version_key(registered.plan.to_version),
                    registered.plan.migration_id,
                ),
            )
        )


def _semantic_version_key(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".")
    return (int(major), int(minor), int(patch))


__all__ = [
    "RegisteredSchemaMigration",
    "SchemaMigration",
    "SchemaMigrationPlan",
    "SchemaMigrationRegistry",
]
