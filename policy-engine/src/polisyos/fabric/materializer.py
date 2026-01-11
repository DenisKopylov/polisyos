from __future__ import annotations

import json
from pathlib import Path

from polisyos.common.logger import get_logger
from polisyos.fabric.io.db import SimulationDB

logger = get_logger(__name__)


def materialize_duckdb_from_fact_log(fact_dir: Path, db: SimulationDB) -> None:
    """
    Placeholder materializer: reads segment manifests and logs their presence.
    Future versions will rebuild DuckDB tables directly from Fact Log.
    """
    index_path = fact_dir / "_segments.jsonl"
    if not index_path.exists():
        logger.info("No fact segments found at %s", fact_dir)
        return
    segments = []
    with index_path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                segments.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    logger.info("Found %d fact segments (materialization stub)", len(segments))
