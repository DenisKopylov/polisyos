"""Characterize complete owner output on explicitly synthetic mechanical controls."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path


def main() -> None:
    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
    from polisyos.data_forge.domains.academic.batch.edge_synthesize import run_edge_synthesize
    from polisyos.data_forge.domains.academic.batch.graph_builder import load_graph
    from tests.unit.data_forge.domains.academic.batch.test_graph_capacity import (
        complete_database_snapshot,
        seed_synthetic_synthesis_inputs,
        synthetic_records,
    )

    with tempfile.TemporaryDirectory() as directory:
        config = AcademicBatchConfig(snapshot_root=Path(directory))
        config.db_path.parent.mkdir(parents=True, exist_ok=True)
        load_graph(records=synthetic_records(), db_path=config.db_path, insert_batch_size=1)
        seed_synthetic_synthesis_inputs(config.db_path)
        metrics = run_edge_synthesize(config, source_provenance={"synthetic": True})
        snapshot = complete_database_snapshot(config.db_path)
        table_digests = {
            table: hashlib.sha256(
                json.dumps(
                    value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
                ).encode()
            ).hexdigest()
            for table, value in snapshot.items()
        }
        print(  # noqa: T201 - captured synthetic characterization output.
            json.dumps(
                {
                    "synthetic": True,
                    "metrics": metrics,
                    "complete_table_count": len(snapshot),
                    "table_digests": table_digests,
                    "review_queue": config.canonical_review_queue_path.read_text(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
