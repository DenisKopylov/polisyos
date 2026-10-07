from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

import duckdb

ROOT = Path.cwd()
PROBE_DIR = ROOT / ".tmp/e02-C5/raw/dfi-emb-prep/read-only-db-probe"
TEST_PATH = ROOT / "policy-engine/tests/unit/remediation/test_emb_03.py"
SOURCE_PATHS = (
    ROOT / "policy-engine/src/polisyos/lex/knowledge/store.py",
    ROOT / "policy-engine/src/polisyos/data_forge/domains/legal/batch/embedder.py",
    ROOT / "policy-engine/src/polisyos/data_forge/kernel/embeddings.py",
)

def emit(event: str, **values: object) -> None:
    print(json.dumps({"event": event, **values}, sort_keys=True, default=str))

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_test_helpers():
    spec = importlib.util.spec_from_file_location("emb03_readonly_probe", TEST_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load tracked fixture helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

emit(
    "environment",
    executable=sys.executable,
    python=sys.version,
    cwd=str(ROOT),
    pythonpath=os.environ.get("PYTHONPATH"),
    duckdb_version=duckdb.__version__,
    source_hashes={str(path.relative_to(ROOT)): sha(path) for path in SOURCE_PATHS},
)
helpers = load_test_helpers()
fixture_root = PROBE_DIR / "fixture-run2"
fixture_root.mkdir(parents=True, exist_ok=True)
db_path = fixture_root / "lex.duckdb"
helpers._prepare_lex_db(
    db_path,
    entities=[("entity-target", "target entity"), ("entity-decoy", "decoy entity")],
)
helpers._prepare_legal_search_rows(db_path)
encoder = helpers._DirectionalLegalEncoder(revision=0)
helpers.legal_embedder.build_local_embeddings_and_indexes(
    db_path=db_path,
    output_dir=fixture_root,
    embedding_model="legal-fixture-model",
    embedding_device="cpu",
    encoder=encoder,
)

from polisyos.data_forge.kernel.embeddings import resolve_embedding_generation
from polisyos.lex.knowledge.search import LegalKnowledgeGraph

index_dir = fixture_root / ".legal_embedding_generations" / "lex_entity_embeddings"
def selected_generation() -> str | None:
    ref = resolve_embedding_generation(index_dir)
    return ref.generation_id if ref is not None else None

graph = LegalKnowledgeGraph(
    db_path,
    fixture_root,
    query_encoder=helpers._DirectionalLegalEncoder(revision=0),
)
try:
    before_results = graph.search_entities("target", top_k=1, min_similarity=0.0)
    emit(
        "warm_readonly_store",
        results=[{"id": result.entity_id, "name": result.name_en} for result in before_results],
        selected_generation=selected_generation(),
        database_sha256=sha(db_path),
    )

    writer = None
    try:
        writer = duckdb.connect(str(db_path))
        writer.execute(
            "UPDATE lex_entities SET name_en = ?, name_uk = ? WHERE entity_id = ?",
            ["replacement decoy label", "replacement decoy label", "entity-target"],
        )
        writer.execute("COMMIT")
        emit("second_writer_update", outcome="accepted")
    except BaseException as exc:
        emit(
            "second_writer_update",
            outcome="refused",
            exception_type=type(exc).__name__,
            message=str(exc),
        )
        if writer is not None:
            try:
                writer.close()
            except BaseException:
                pass
        writer = None
    if writer is not None:
        writer.close()
        stale_probe_results = graph.search_entities("target", top_k=1, min_similarity=0.0)
        emit(
            "query_after_second_writer",
            results=[{"id": result.entity_id, "name": result.name_en} for result in stale_probe_results],
            selected_generation=selected_generation(),
            database_sha256=sha(db_path),
        )

    pre_builder_generation = selected_generation()
    build_stats = helpers.legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=fixture_root,
        embedding_model="legal-fixture-model",
        embedding_device="cpu",
        encoder=helpers._DirectionalLegalEncoder(revision=0),
        incremental=False,
    )
    post_builder_generation = selected_generation()
    post_builder_results = graph.search_entities("target", top_k=1, min_similarity=0.0)
    emit(
        "supported_embedding_builder_while_store_open",
        outcome="completed",
        pre_builder_generation=pre_builder_generation,
        post_builder_generation=post_builder_generation,
        changed_selector=pre_builder_generation != post_builder_generation,
        stats={
            "entities_embedded": build_stats.entities_embedded,
            "facts_embedded": build_stats.facts_embedded,
            "provisions_embedded": build_stats.provisions_embedded,
        },
        results=[{"id": result.entity_id, "name": result.name_en} for result in post_builder_results],
        database_sha256=sha(db_path),
    )
except BaseException:
    traceback.print_exc()
    raise
finally:
    graph.close()
emit(
    "source_hashes_after",
    source_hashes={str(path.relative_to(ROOT)): sha(path) for path in SOURCE_PATHS},
)
