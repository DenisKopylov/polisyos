"""Snapshot transaction contracts."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

import polisyos.data_forge.kernel.artifacts as artifact_contracts
from polisyos.data_forge.kernel._base import DataForgeModel, utc_now
from polisyos.data_forge.kernel.snapshot.merkle import merkle_root

ArtifactRef = artifact_contracts.ArtifactRef


class SnapshotTransactionStatus(str, Enum):
    """Lifecycle status for a snapshot transaction."""

    OPEN = "open"
    COMMITTED = "committed"
    ABORTED = "aborted"


class SnapshotTransaction(DataForgeModel):
    """All-or-nothing publication record for an asset group."""

    snapshot_id: str = Field(min_length=1)
    asset_group: str = Field(min_length=1)
    artifacts: tuple[ArtifactRef, ...] = Field(default_factory=tuple)
    status: SnapshotTransactionStatus = SnapshotTransactionStatus.OPEN
    merkle_root: str | None = None
    created_at: str = Field(default_factory=lambda: utc_now().isoformat())

    @model_validator(mode="after")
    def _committed_requires_merkle(self) -> SnapshotTransaction:
        if self.status == SnapshotTransactionStatus.COMMITTED and not self.merkle_root:
            raise ValueError("committed snapshot transactions must include a merkle root")
        return self

    def commit(self) -> SnapshotTransaction:
        """Return a committed transaction with its Merkle root populated."""
        return self.model_copy(
            update={
                "status": SnapshotTransactionStatus.COMMITTED,
                "merkle_root": merkle_root(self.artifacts),
            }
        )

    def abort(self) -> SnapshotTransaction:
        """Return an aborted transaction."""
        return self.model_copy(update={"status": SnapshotTransactionStatus.ABORTED})


__all__ = ["SnapshotTransaction", "SnapshotTransactionStatus"]
