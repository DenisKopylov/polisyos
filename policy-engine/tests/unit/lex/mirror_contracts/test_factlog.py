from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from _helpers.artifacts import put_json_artifact

from polisyos.fabric.world import (
    append_world_segment_index,
    emit_doc_meta_facts,
    load_world_facts,
    write_world_fact_segment,
)
from polisyos.ir.loading.fact_log import FactLegal, FactProvenance
from polisyos.ir.world.doc import DocMeta
from polisyos.lex.types import NormPackBuildRequest

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_normpack_reader_imports_fabric_owner_without_legacy_factlog() -> None:
    """The Lex consumer imports the Fabric-owned reader directly."""

    script = """
        import json
        import sys

        from polisyos.lex.normpack import select_sources

        print(
            json.dumps(
                {
                    "legacy_loaded": "polisyos.lex.factlog" in sys.modules,
                    "fabric_loaded": "polisyos.fabric.world" in sys.modules,
                    "reader_module": select_sources.load_world_facts.__module__,
                }
            )
        )
    """
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(REPO_ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "legacy_loaded": False,
        "fabric_loaded": True,
        "reader_module": "polisyos.fabric.world.store.segments",
    }


def test_fabric_fact_readback_preserves_provenance_for_lex_source_selection(
    tmp_path: Path,
    store,
) -> None:
    """A persisted Fabric record remains readable by Lex with its origin fields intact.

    Lex source selection reads document identity and metadata. This test also reads the
    provenance envelope directly from Fabric to pin preservation; the selector does not
    treat a license/access field as an authorization decision.
    """

    raw_ref = "sha256:" + "0" * 64
    meta = DocMeta(
        doc_source_id="doc.source.hyg18",
        doc_version_id="doc.version.hyg18",
        canonical_url="https://example.test/law",
        official_id=None,
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        mime="text/html",
        license="public",
        raw_ref=raw_ref,
        props={"lex": {"corpus": "lex.corpus"}},
    )
    meta_ref = put_json_artifact(
        store,
        meta.model_dump(mode="json"),
        kind="lex.doc_meta",
        schema_version="1.0",
    )
    provenance = FactProvenance(
        source_id="legal.publisher",
        license="public",
        raw_hash=raw_ref,
        ingestion_run_id="hyg18-run-1",
    )
    legal = FactLegal(access_tier="public", basis="public legal publication")
    facts = emit_doc_meta_facts(
        meta,
        meta_artifact_id=str(meta_ref.artifact_id),
        provenance=provenance,
        legal=legal,
    )
    fact_log_root = tmp_path / "fact-log"
    manifest = write_world_fact_segment(
        facts,
        fact_log_root=fact_log_root,
        segment_name="lex-source-selection",
    )
    append_world_segment_index(manifest, fact_log_root=fact_log_root)

    loaded = load_world_facts(
        fact_log_root,
        columns=["subject_id", "predicate_id", "provenance", "legal"],
    )
    source_facts = loaded[loaded["subject_id"] == meta.doc_source_id]
    assert not source_facts.empty
    first_provenance = source_facts.iloc[0]["provenance"]
    first_legal = source_facts.iloc[0]["legal"]
    if isinstance(first_provenance, str):
        first_provenance = json.loads(first_provenance)
    if isinstance(first_legal, str):
        first_legal = json.loads(first_legal)
    assert first_provenance["source_id"] == provenance.source_id
    assert first_provenance["license"] == provenance.license
    assert first_provenance["raw_hash"] == provenance.raw_hash
    assert first_provenance["ingestion_run_id"] == provenance.ingestion_run_id
    assert first_legal["access_tier"] == legal.access_tier
    assert first_legal["basis"] == legal.basis

    from polisyos.lex.normpack.select_sources import select_doc_sources

    selected = select_doc_sources(
        cas=store,
        fact_log_root=fact_log_root,
        request=NormPackBuildRequest(jurisdiction="UA", as_of="2026-10-06"),
    )

    assert selected == [meta.doc_source_id]
