"""Snapshot contract helpers for Data Forge."""

from __future__ import annotations

from .commit import AtomicCommitResult, CommitPlan, commit_staged_path
from .finalize import (
    DATA_FORGE_PROVENANCE_MANIFEST_FILE,
    DATA_FORGE_SNAPSHOT_BINDING_FILE,
    DEFAULT_PIPELINES,
    PIPELINE_BINDING_SURFACES,
    finalize_snapshot,
    write_snapshot_binding,
)
from .merkle import merkle_root
from .retention import RetentionPolicy
from .time_travel import SnapshotCoordinate, SnapshotResolver
from .transactions import SnapshotTransaction, SnapshotTransactionStatus

__all__ = [
    "DATA_FORGE_PROVENANCE_MANIFEST_FILE",
    "DATA_FORGE_SNAPSHOT_BINDING_FILE",
    "DEFAULT_PIPELINES",
    "PIPELINE_BINDING_SURFACES",
    "AtomicCommitResult",
    "CommitPlan",
    "RetentionPolicy",
    "SnapshotCoordinate",
    "SnapshotResolver",
    "SnapshotTransaction",
    "SnapshotTransactionStatus",
    "commit_staged_path",
    "finalize_snapshot",
    "merkle_root",
    "write_snapshot_binding",
]
