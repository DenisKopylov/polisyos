from __future__ import annotations

import asyncio
import json
from pathlib import Path

import duckdb

from polisyos.data_forge.domains.legal.batch.config import BatchConfig
from polisyos.data_forge.domains.legal.batch.graph_builder import build_graph
from polisyos.data_forge.domains.legal.batch.pipeline import run_batch_pipeline
from polisyos.data_forge.domains.legal.batch.postprocess import ground_spo_quotes
from polisyos.data_forge.domains.legal.batch.provisions_io import write_provisions


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_pipeline_withholds_unverified_legacy_authority_through_publish(tmp_path: Path) -> None:
    """A source-bound candidate stays useful while old authority exports are withheld."""
    output_dir = tmp_path / "legal-run"
    doc_id = "controlled-source"
    anchor = "body:1/item:0001"
    provision_text = "The Ministry shall publish the annual report by March."
    provisions_dir = output_dir / "provisions"
    raw_spo_dir = output_dir / "spo_results"
    grounded_spo_dir = output_dir / "spo_grounded"
    db_path = output_dir / "lex_knowledge_graph.duckdb"

    write_provisions(
        provisions_dir=provisions_dir,
        doc_id=doc_id,
        provisions=[
            {
                "anchor_path": anchor,
                "kind": "point",
                "text": provision_text,
                "is_fallback_chunk": False,
                "struct_kind": "enumeration_item",
                "section_role": "normative_unit",
                "fallback_allowed_for_reasoning": True,
            }
        ],
    )
    _write_jsonl(
        raw_spo_dir / doc_id[:2] / f"{doc_id}.jsonl",
        [
            {
                "doc_id": doc_id,
                "provision_anchor": anchor,
                "provision_citation": "controlled fixture source; not legal authority",
                "extraction_source": "rule_auto",
                "statements": [
                    {
                        "statement_id": "source-bound-candidate",
                        "subject_en": "Ministry",
                        "subject_uk": "Міністерство",
                        "predicate": "requires",
                        "object_en": "annual report",
                        "object_uk": "річний звіт",
                        "fact_text": "The Ministry must publish the annual report by March.",
                        "confidence": 0.99,
                        "norm_type": "obligation",
                        "norm_type_canon": "obligation",
                        "action_canon": "requires",
                        "canonical_status": "canonicalized",
                        "source_quote_uk": provision_text,
                        "source_quote_start": None,
                        "source_quote_end": None,
                        "grounding_status": "exact_quote",
                        "trust_tier": "normative_fact",
                    }
                ],
            }
        ],
    )
    ground_spo_quotes(
        spo_results_dir=raw_spo_dir,
        provisions_dir=provisions_dir,
        output_dir=grounded_spo_dir,
    )
    build_graph(
        spo_results_dir=grounded_spo_dir,
        provisions_dir=provisions_dir,
        references_dir=None,
        domains_dir=None,
        doc_metadata={},
        db_path=db_path,
    )

    with duckdb.connect(str(db_path), read_only=True) as connection:
        candidate_count = connection.execute("SELECT COUNT(*) FROM lex_fact_candidates").fetchone()[
            0
        ]
        normative_count = connection.execute("SELECT COUNT(*) FROM lex_normative_facts").fetchone()[
            0
        ]
    assert candidate_count == 1
    assert normative_count == 0

    stale_artifacts = {
        "claim_exports/normative_claims.jsonl": b'{"claim_id":"stale"}\n',
        "claim_exports/normative_claims_summary.json": b'{"status":"ok"}',
        "claim_exports/normative_claim_sets_summary.json": b'{"status":"ok"}',
    }
    for relative_path, content in stale_artifacts.items():
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (output_dir / "qc_report.json").write_text(
        json.dumps({"passed": True, "metrics": {"quality_gate_passed": True}}),
        encoding="utf-8",
    )
    (output_dir / "benchmark_report.json").write_text(
        json.dumps({"readiness": {"passed": True, "failed_checks": []}}),
        encoding="utf-8",
    )

    config = BatchConfig(
        cards_path=tmp_path / "cards.jsonl",
        texts_path=tmp_path / "texts",
        output_dir=output_dir,
        stages=frozenset({"export_claims", "publish_bundle"}),
        publish_require_embeddings=False,
    )
    stats = asyncio.run(run_batch_pipeline(config))

    refusal = "legal_source_relation_verification_not_established"
    assert stats.exported_claims == 0
    assert stats.exported_claim_sets == 0
    assert stats.release_passed is False
    assert refusal in stats.release_failed_checks

    manifest = json.loads((output_dir / "publish" / "manifest.json").read_text("utf-8"))
    readiness = json.loads((output_dir / "publish" / "consumer_readiness.json").read_text("utf-8"))
    published_paths = {artifact["path"] for artifact in manifest["artifacts"]}
    assert not any(path in published_paths for path in stale_artifacts)
    assert all(
        (output_dir / path).read_bytes() == content for path, content in stale_artifacts.items()
    )
    assert readiness["readiness"]["candidate_layer_ready"] is True
    assert readiness["readiness"]["normative_layer_ready"] is False
    assert readiness["release_readiness"]["release_ready"] is False
    assert readiness["legal_relation_refusal"] == {
        "code": refusal,
        "status": "verification_missing",
    }
