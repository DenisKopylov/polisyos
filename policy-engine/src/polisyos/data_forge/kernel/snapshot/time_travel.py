"""Time-travel artifact resolution contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import Field

import polisyos.data_forge.kernel.artifacts as artifact_contracts
from polisyos.data_forge.errors import DataForgeValidationError
from polisyos.data_forge.kernel._base import DataForgeModel

ArtifactRef = artifact_contracts.ArtifactRef


class SnapshotCoordinate(DataForgeModel):
    """Address one artifact at a specific snapshot and logical timestamp."""

    uri: str = Field(pattern=r"^polisyos://[a-z0-9_.-]+/[a-z0-9_./-]+$")
    snapshot_id: str = Field(min_length=1)
    logical_ts: str | None = None


@dataclass(slots=True)
class SnapshotResolver:
    """Tiny in-memory resolver used by Phase 0A tests and shadow adapters."""

    _refs: dict[tuple[str, str], ArtifactRef] = field(default_factory=dict)

    def add(self, ref: ArtifactRef) -> None:
        """Add an artifact ref to the resolver index."""
        logical_uri, snapshot_id = ref.uri.rsplit("@", 1)
        self._refs[(logical_uri, snapshot_id)] = ref

    def resolve(self, coordinate: SnapshotCoordinate) -> ArtifactRef:
        """Resolve one artifact ref by logical URI and snapshot id."""
        try:
            return self._refs[(coordinate.uri, coordinate.snapshot_id)]
        except KeyError as exc:
            raise DataForgeValidationError(
                f"artifact not found: {coordinate.uri}@{coordinate.snapshot_id}"
            ) from exc


__all__ = ["SnapshotCoordinate", "SnapshotResolver"]
