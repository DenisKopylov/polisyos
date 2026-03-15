from __future__ import annotations

import json
from datetime import UTC
from pathlib import Path

import duckdb

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.claims.persist import load_claim, load_doc_meta, load_json_artifact
from polisyos.lex.batch.claim_bridge import _to_datetime_utc, export_normative_claim_sets


def _seed_bridge_db(db_path: Path) -> None:
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            """
            CREATE TABLE lex_normative_facts (
                fact_id VARCHAR,
                doc_id VARCHAR,
                doc_name VARCHAR,
                doc_reestr_code VARCHAR,
                doc_type VARCHAR,
                doc_status VARCHAR,
                jurisdiction VARCHAR,
                top_domain VARCHAR,
                effective_from VARCHAR,
                effective_to VARCHAR,
                provision_anchor VARCHAR,
                provision_citation VARCHAR,
                subject_en VARCHAR,
                subject_uk VARCHAR,
                object_en VARCHAR,
                object_uk VARCHAR,
                predicate VARCHAR,
                action_canon VARCHAR,
                norm_type_canon VARCHAR,
                constraint_type_canon VARCHAR,
                fact_text VARCHAR,
                confidence DOUBLE,
                thresholds_json VARCHAR,
                source_quote_uk VARCHAR,
                source_quote_start INTEGER,
                source_quote_end INTEGER
            )
            """
        )
        con.execute(
            """
            CREATE TABLE lex_provisions (
                doc_id VARCHAR,
                anchor_path VARCHAR,
                kind VARCHAR,
                struct_kind VARCHAR,
                section_role VARCHAR,
                provision_text VARCHAR
            )
            """
        )
        con.executemany(
            """
            INSERT INTO lex_normative_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "fact.speed_50",
                    "law-a",
                    "Road Law A",
                    "0001",
                    "Закон",
                    "active",
                    "UA",
                    "roads",
                    "2025-01-01",
                    None,
                    "article:1",
                    "стаття 1",
                    "road_user",
                    "користувач дороги",
                    "50 km",
                    "50 км",
                    "requires",
                    "speed_limit",
                    "obligation",
                    "speed_limit",
                    "Максимальна швидкість не повинна перевищувати 50 км.",
                    0.91,
                    '[{"metric":"max_speed_kmh","operator":"<=","value_decimal":"50","unit":"km"}]',
                    "Максимальна швидкість не повинна перевищувати 50 км.",
                    0,
                    51,
                ),
                (
                    "fact.speed_60",
                    "law-b",
                    "Road Law B",
                    "0002",
                    "Закон",
                    "active",
                    "UA",
                    "roads",
                    "2025-01-01",
                    None,
                    "article:1",
                    "стаття 1",
                    "road_user",
                    "користувач дороги",
                    "60 km",
                    "60 км",
                    "requires",
                    "speed_limit",
                    "obligation",
                    "speed_limit",
                    "Максимальна швидкість не повинна перевищувати 60 км.",
                    0.89,
                    '[{"metric":"max_speed_kmh","operator":"<=","value_decimal":"60","unit":"km"}]',
                    "Максимальна швидкість не повинна перевищувати 60 км.",
                    0,
                    51,
                ),
            ],
        )
        con.executemany(
            "INSERT INTO lex_provisions VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    "law-a",
                    "article:1",
                    "article",
                    "article",
                    "normative_unit",
                    "Максимальна швидкість не повинна перевищувати 50 км.",
                ),
                (
                    "law-b",
                    "article:1",
                    "article",
                    "article",
                    "normative_unit",
                    "Максимальна швидкість не повинна перевищувати 60 км.",
                ),
            ],
        )


def test_export_normative_claim_sets_writes_claim_sets_and_summary(tmp_path: Path) -> None:
    db_path = tmp_path / "lex.duckdb"
    _seed_bridge_db(db_path)

    cas = FileSystemCAS(tmp_path / "cas")
    bridge_result = export_normative_claim_sets(
        db_path=db_path,
        cas_root=cas.root,
        fact_log_root=tmp_path,
        output_dir=tmp_path / "claim_exports",
    )

    assert len(bridge_result.raw_claim_set_artifact_ids) == 2
    assert len(bridge_result.normalized_claim_set_artifact_ids) == 2
    assert len(bridge_result.claim_ids) == 2
    assert bridge_result.world_segment_manifest is not None
    assert Path(bridge_result.world_segment_manifest.path).exists()

    summary_path = tmp_path / "claim_exports" / "normative_claim_sets_summary.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["normalized_claim_set_artifact_ids"] == bridge_result.normalized_claim_set_artifact_ids

    claim_set_payload = load_json_artifact(cas, bridge_result.normalized_claim_set_artifact_ids[0])
    assert claim_set_payload["doc_source_id"].startswith("doc.")
    assert claim_set_payload["claims"]

    claim = load_claim(cas, claim_set_payload["claims"][0]["claim_artifact_id"])
    assert claim.subject_id == "road_user"
    assert claim.props["lex"]["trust_tier"] == "normative_fact"
    assert claim.jurisdiction == "ua"

    doc_meta = load_doc_meta(cas, claim_set_payload["doc_meta_artifact_id"])
    raw_bytes = cas.get_bytes(ArtifactID.model_validate(doc_meta.raw_ref))
    assert "Максимальна швидкість".encode("utf-8") in raw_bytes


def test_to_datetime_utc_accepts_ukrainian_day_month_year() -> None:
    parsed = _to_datetime_utc("20.02.1997")

    assert parsed is not None
    assert parsed.year == 1997
    assert parsed.month == 2
    assert parsed.day == 20
    assert parsed.tzinfo == UTC
