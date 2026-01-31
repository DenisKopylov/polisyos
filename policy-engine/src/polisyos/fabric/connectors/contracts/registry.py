"""
Schema registry for managing and discovering schemas.

Provides:
- Schema registration and lookup
- Version management
- CAS-based caching
- Schema discovery
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
import threading
import tempfile

from pydantic import BaseModel, ConfigDict, Field

from polisyos.common.logger import get_logger
from polisyos.fabric.connectors.contracts.schema import DataSchema, SchemaVersion
from polisyos.fabric.connectors.contracts.evolution import SchemaEvolution, EvolutionReport

logger = get_logger(__name__)

REGISTRY_SCHEMA_VERSION = "1.0"


class SchemaNotFoundError(Exception):
    """Raised when a schema is not found in the registry."""

    def __init__(self, schema_id: str, version: SchemaVersion | None = None) -> None:
        self.schema_id = schema_id
        self.version = version
        msg = f"Schema '{schema_id}' not found"
        if version:
            msg = f"Schema '{schema_id}' version {version} not found"
        super().__init__(msg)


class SchemaVersionConflictError(Exception):
    """Raised when registering a schema with conflicting version."""

    def __init__(
        self,
        schema_id: str,
        existing_version: SchemaVersion,
        new_version: SchemaVersion,
        existing_hash: str | None = None,
        new_hash: str | None = None,
    ) -> None:
        self.schema_id = schema_id
        self.existing_version = existing_version
        self.new_version = new_version
        self.existing_hash = existing_hash
        self.new_hash = new_hash
        msg = (
            f"Schema '{schema_id}' version {new_version} conflicts with existing {existing_version}"
        )
        if existing_hash and new_hash:
            msg += f" (hash {existing_hash[:8]} != {new_hash[:8]})"
        super().__init__(msg)


class SchemaRegistration(BaseModel):
    """Metadata about a registered schema."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema: DataSchema
    content_hash: str
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    registered_by: str = ""

    @classmethod
    def from_schema(
        cls, schema: DataSchema, registered_by: str = ""
    ) -> "SchemaRegistration":
        return cls(
            schema=schema,
            content_hash=schema.content_hash,
            registered_by=registered_by,
        )


class SchemaRegistry:
    """
    In-memory schema registry with version management.

    Usage:
        registry = SchemaRegistry()

        # Register a schema
        registry.register(my_schema)

        # Get latest version
        schema = registry.get("my.schema.id")

        # Get specific version
        schema = registry.get("my.schema.id", version=SchemaVersion(1, 0, 0))

        # Check compatibility
        compatible = registry.is_compatible_upgrade(old_schema, new_schema)
    """

    def __init__(self) -> None:
        self._schemas: dict[str, dict[SchemaVersion, SchemaRegistration]] = {}
        self._evolution = SchemaEvolution()
        self._lock = threading.Lock()

    def register(
        self,
        schema: DataSchema,
        registered_by: str = "",
        allow_overwrite: bool = False,
    ) -> SchemaRegistration:
        """
        Register a schema in the registry.

        Args:
            schema: Schema to register
            registered_by: Identifier of who registered it
            allow_overwrite: If True, allow overwriting existing version

        Returns:
            SchemaRegistration with metadata

        Raises:
            SchemaVersionConflictError: If version already exists and allow_overwrite=False
        """
        schema_id = schema.schema_id
        version = schema.version

        with self._lock:
            if schema_id not in self._schemas:
                self._schemas[schema_id] = {}

            if version in self._schemas[schema_id] and not allow_overwrite:
                existing = self._schemas[schema_id][version]
                if existing.content_hash != schema.content_hash:
                    raise SchemaVersionConflictError(
                        schema_id,
                        existing.schema.version,
                        version,
                        existing_hash=existing.content_hash,
                        new_hash=schema.content_hash,
                    )
                return existing

            registration = SchemaRegistration.from_schema(schema, registered_by)
            self._schemas[schema_id][version] = registration

        logger.info(
            "Schema registered",
            extra={
                "schema_id": schema_id,
                "version": str(version),
                "content_hash": registration.content_hash,
            },
        )

        return registration

    def get(self, schema_id: str, version: SchemaVersion | None = None) -> DataSchema:
        """
        Get a schema by ID and optional version.

        Args:
            schema_id: Schema identifier
            version: Specific version, or None for latest

        Returns:
            DataSchema

        Raises:
            SchemaNotFoundError: If schema not found
        """
        if schema_id not in self._schemas:
            raise SchemaNotFoundError(schema_id, version)

        versions = self._schemas[schema_id]

        if version is not None:
            if version not in versions:
                raise SchemaNotFoundError(schema_id, version)
            return versions[version].schema

        latest_version = max(versions.keys())
        return versions[latest_version].schema

    def get_registration(
        self, schema_id: str, version: SchemaVersion | None = None
    ) -> SchemaRegistration:
        """Get schema registration with metadata."""
        if schema_id not in self._schemas:
            raise SchemaNotFoundError(schema_id, version)

        versions = self._schemas[schema_id]

        if version is not None:
            if version not in versions:
                raise SchemaNotFoundError(schema_id, version)
            return versions[version]

        latest_version = max(versions.keys())
        return versions[latest_version]

    def list_schemas(self) -> list[str]:
        """List all registered schema IDs."""
        return list(self._schemas.keys())

    def list_versions(self, schema_id: str) -> list[SchemaVersion]:
        """List all versions of a schema."""
        if schema_id not in self._schemas:
            return []
        return sorted(self._schemas[schema_id].keys())

    def contains(self, schema_id: str, version: SchemaVersion | None = None) -> bool:
        """Check if schema exists in registry."""
        if schema_id not in self._schemas:
            return False
        if version is None:
            return True
        return version in self._schemas[schema_id]

    def compare_versions(
        self,
        schema_id: str,
        source_version: SchemaVersion,
        target_version: SchemaVersion,
    ) -> EvolutionReport:
        """Compare two versions of the same schema."""
        source = self.get(schema_id, source_version)
        target = self.get(schema_id, target_version)
        return self._evolution.compare(source, target)

    def is_compatible_upgrade(
        self,
        schema_id: str,
        from_version: SchemaVersion,
        to_version: SchemaVersion,
    ) -> bool:
        """Check if upgrading between versions is backward-compatible."""
        report = self.compare_versions(schema_id, from_version, to_version)
        return report.is_compatible

    def unregister(self, schema_id: str, version: SchemaVersion | None = None) -> bool:
        """
        Remove a schema from the registry.

        Args:
            schema_id: Schema to remove
            version: Specific version, or None to remove all versions

        Returns:
            True if something was removed
        """
        with self._lock:
            if schema_id not in self._schemas:
                return False

            if version is None:
                del self._schemas[schema_id]
                return True

            if version in self._schemas[schema_id]:
                del self._schemas[schema_id][version]
                if not self._schemas[schema_id]:
                    del self._schemas[schema_id]
                return True

        return False

    def __contains__(self, schema_id: str) -> bool:
        return schema_id in self._schemas

    def __len__(self) -> int:
        return sum(len(versions) for versions in self._schemas.values())

    def __iter__(self) -> Iterator[DataSchema]:
        """Iterate over all schema versions."""
        for versions in self._schemas.values():
            for registration in versions.values():
                yield registration.schema


class FileBackedSchemaRegistry(SchemaRegistry):
    """
    Schema registry with file-based persistence.

    Stores schemas as JSON files in a directory structure:

        base_dir/
            schema.id.name/
                1.0.0.json
                1.1.0.json
                2.0.0.json
    """

    def __init__(self, base_dir: Path) -> None:
        super().__init__()
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._load_all()

    def _schema_dir(self, schema_id: str) -> Path:
        """Get directory for a schema."""
        safe_id = schema_id.replace(".", "_")
        return self._base_dir / safe_id

    def _schema_file(self, schema_id: str, version: SchemaVersion) -> Path:
        """Get file path for a specific schema version."""
        return self._schema_dir(schema_id) / f"{version}.json"

    def _load_all(self) -> None:
        """Load all schemas from disk."""
        for schema_dir in self._base_dir.iterdir():
            if not schema_dir.is_dir():
                continue

            for version_file in schema_dir.glob("*.json"):
                try:
                    with open(version_file, "r") as f:
                        data = json.load(f)

                    schema_payload = data.get("schema") or data
                    version_str = version_file.stem
                    version = SchemaVersion.parse(version_str)

                    schema = DataSchema.model_validate(schema_payload)
                    registered_by = data.get("registered_by", "")

                    super().register(schema, registered_by, allow_overwrite=True)

                except Exception as exc:
                    logger.warning(
                        f"Failed to load schema from {version_file}: {exc}"
                    )

    def register(
        self,
        schema: DataSchema,
        registered_by: str = "",
        allow_overwrite: bool = False,
    ) -> SchemaRegistration:
        """Register and persist schema."""
        registration = super().register(schema, registered_by, allow_overwrite)

        schema_dir = self._schema_dir(schema.schema_id)
        schema_dir.mkdir(parents=True, exist_ok=True)

        schema_file = self._schema_file(schema.schema_id, schema.version)
        payload = {
            "registry_schema_version": REGISTRY_SCHEMA_VERSION,
            "schema": schema.model_dump(mode="json"),
            "content_hash": registration.content_hash,
            "registered_at": registration.registered_at.isoformat(),
            "registered_by": registered_by,
        }

        _atomic_write_json(schema_file, payload)

        return registration

    def unregister(self, schema_id: str, version: SchemaVersion | None = None) -> bool:
        """Remove schema and delete from disk."""
        result = super().unregister(schema_id, version)

        if result:
            if version is None:
                schema_dir = self._schema_dir(schema_id)
                if schema_dir.exists():
                    import shutil

                    shutil.rmtree(schema_dir)
            else:
                schema_file = self._schema_file(schema_id, version)
                if schema_file.exists():
                    schema_file.unlink()

        return result


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, dir=path.parent, prefix=path.name, suffix=".tmp"
    ) as tmp:
        json.dump(payload, tmp, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    os.replace(tmp_name, path)
