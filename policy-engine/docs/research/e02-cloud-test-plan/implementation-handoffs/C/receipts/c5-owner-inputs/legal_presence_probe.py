"""Observe only exact selected local Legal bundle paths; never read DB payload."""

from __future__ import annotations

import datetime
import json
import stat
from pathlib import Path


def main() -> None:
    """Print metadata for the exact selected local paths without opening payloads."""
    db = Path(
        "/Users/deniskopylov/polisyos/policy-engine/production_data/lex/"
        "lex-amendment-only-optimized-20260501-v3/finalize/lex_knowledge_graph.duckdb"
    )
    paths = [db]
    for name, index in (
        ("lex_entity_embeddings", "lex_entity_index"),
        ("lex_fact_embeddings", "lex_fact_index"),
        ("lex_provision_embeddings", "lex_provision_index"),
    ):
        paths.extend(
            (
                db.parent / ".legal_embedding_generations" / name / "embedding_generation.json",
                db.parent / f"{name}.npz",
                db.parent / f"{index}.hnsw",
            )
        )
    paths.append(db.parent / "manifests/embed_local.json")
    observations = []
    for path in paths:
        try:
            value = path.lstat()
        except FileNotFoundError:
            observations.append({"path": str(path), "present": False})
            continue
        observations.append(
            {
                "path": str(path),
                "present": True,
                "mode": oct(stat.S_IMODE(value.st_mode)),
                "bytes": value.st_size,
                "mtime_ns": value.st_mtime_ns,
                "inode": value.st_ino,
                "device": value.st_dev,
                "symlink": path.is_symlink(),
            }
        )
    print(  # noqa: T201 - This standalone observer emits its JSON receipt on stdout.
        json.dumps(
            {
                "schema": "policyos.e02.c5.legal-paired-input-presence.v1",
                "captured_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
                "operation": "lstat of exact selected DB/index directory paths only",
                "db_payload_or_row_reads": False,
                "db_hash_computed": False,
                "profile_assumed": False,
                "membership_digest": "not_established: no selected generation at inspected paths",
                "paths": observations,
                "scope": (
                    "Selected bundle and DB-parent index layout; no global model/corpus absence "
                    "claim. C60 fixture query binding does not supply production paired inputs."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
