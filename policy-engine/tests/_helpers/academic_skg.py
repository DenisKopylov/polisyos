from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.data_forge.domains.academic.batch.graph_builder import GraphStats
    from polisyos.data_forge.domains.academic.knowledge.types import WorkRecord


def build_synthetic_academic_skg_source(
    *,
    records: Iterable[WorkRecord],
    db_path: Path,
) -> GraphStats:
    """Build a fresh, explicitly scoped synthetic SKG for controlled tests."""
    selected_records = tuple(records)
    if not selected_records:
        raise ValueError("synthetic_academic_skg_requires_explicit_synthetic_records")
    for record in selected_records:
        fixture_scope = record.metadata.get("fixture_scope")
        if (
            record.metadata.get("synthetic") is not True
            or not isinstance(fixture_scope, str)
            or not fixture_scope.strip()
        ):
            raise ValueError("synthetic_academic_skg_requires_explicit_synthetic_records")

    if not db_path.parent.is_dir():
        raise ValueError("synthetic_academic_skg_parent_directory_missing")
    staging_path = db_path.with_suffix(db_path.suffix + ".staging")
    writer_paths = (
        db_path,
        db_path.with_suffix(db_path.suffix + ".wal"),
        staging_path,
    )
    if any(path.exists() or path.is_symlink() for path in writer_paths):
        raise ValueError("synthetic_academic_skg_seed_target_exists")

    from polisyos.data_forge.domains.academic.batch.graph_builder import build_graph

    return build_graph(records=selected_records, db_path=db_path)
