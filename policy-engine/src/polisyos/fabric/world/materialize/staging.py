"""Public materialize staging module API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from polisyos.ir.fact_log import FactSegmentManifest
from polisyos.ir.world.predicates import WORLD_REL_PREFIX

from .errors import WorldSchemaError

REQUIRED_COLUMNS = {
    "fact_id",
    "schema_version",
    "subject_id",
    "predicate_id",
    "object_value",
    "target_id",
    "valid_time",
    "tx_time",
    "provenance",
    "trust",
    "legal",
}


@dataclass
class StagedWorldSegment:
    """Staged world segment public type."""

    df: pd.DataFrame
    attr_df: pd.DataFrame
    edge_df: pd.DataFrame
    touched_node_ids: list[str]


def stage_world_segment(manifest: FactSegmentManifest) -> StagedWorldSegment:
    """Stage world segment helper."""
    path = Path(manifest.path)
    df = pd.read_parquet(path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise WorldSchemaError(f"world fact segment missing columns: {sorted(missing)}")

    predicate_series = df["predicate_id"].astype(str)
    edge_mask = predicate_series.str.startswith(WORLD_REL_PREFIX) & df["target_id"].notna()
    edge_df = df[edge_mask].copy()
    attr_df = df[df["target_id"].isna()].copy()

    touched: set[str] = set()
    if not df.empty:
        touched.update(df["subject_id"].dropna().astype(str).tolist())
    if not edge_df.empty:
        touched.update(edge_df["target_id"].dropna().astype(str).tolist())

    touched_node_ids = sorted(touched)
    return StagedWorldSegment(
        df=df,
        attr_df=attr_df,
        edge_df=edge_df,
        touched_node_ids=touched_node_ids,
    )


__all__ = [
    "REQUIRED_COLUMNS",
    "StagedWorldSegment",
    "stage_world_segment",
]
