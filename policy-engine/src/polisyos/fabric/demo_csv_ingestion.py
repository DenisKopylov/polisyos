"""Explicit legacy demo CSV ingestion entrypoint."""

from __future__ import annotations

from pathlib import Path

from polisyos.core.contracts.fabric import EvidenceBundleRef
from polisyos.fabric.ingestion import run_demo_csv_ingestion

__all__ = ["run_demo_csv_ingestion", "run"]


def run(
    *,
    raw_dir: Path,
    staging_dir: Path,
    curated_dir: Path,
    db_path: Path,
    kuzu_path: Path,
    source: str,
    license_name: str,
    clear_on_start: bool = False,
    reconciliation_tolerance: float = 1e-6,
    reconciliation_strict: bool = True,
    cas_root: Path | None = Path(".polisyos"),
) -> EvidenceBundleRef | None:
    return run_demo_csv_ingestion(
        raw_dir=raw_dir,
        staging_dir=staging_dir,
        curated_dir=curated_dir,
        db_path=db_path,
        kuzu_path=kuzu_path,
        source=source,
        license_name=license_name,
        clear_on_start=clear_on_start,
        reconciliation_tolerance=reconciliation_tolerance,
        reconciliation_strict=reconciliation_strict,
        cas_root=cas_root,
    )

