from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.data_forge.domains.legal.contracts import LegalDocSource
from polisyos.data_forge.domains.legal.corpus import (
    build_legal_structure,
    build_version_index,
    ingest_legal_doc_bytes,
)
from polisyos.data_forge.domains.legal.source_relation import (
    LegalSourceRelationVerificationMissingError,
)
from polisyos.data_forge.read_api.legal import export_normative_claim_sets
from polisyos.fabric.claims.persist import load_doc_meta, load_json_artifact
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.world.materialize import materialize_world_duckdb_from_fact_log
from polisyos.ir.loading.citations import CitationRef, DocumentRef
from polisyos.ir.loading.norm_pack import NormPack
from polisyos.ir.world.claim import Claim, ClaimSourceKind
from polisyos.lex.api import assemble_norm_pack
from polisyos.lex.normpack.assemble_pack import claims_to_norm_rules
from polisyos.lex.normpack.types import NormPackBuildRequest


def _ua_source(*, official_id: str, effective_from: str) -> LegalDocSource:
    return LegalDocSource(
        official_id=official_id,
        canonical_url=None,
        license="public",
        jurisdiction="UA",
        language="uk",
        source_type="legal_manual_seed",
        source_url="https://zakon.example/act",
        published_at_iso=effective_from,
        effective_from_iso=effective_from,
        effective_to_iso=None,
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _doc_citation(*, fragment_id: str) -> CitationRef:
    return CitationRef(
        doc=DocumentRef(doc_id="doc.demo", doc_version_id="docv.demo"),
        fragment_id=fragment_id,
    )


def _claim(
    *,
    claim_id: str,
    predicate_id: str,
    value_text: str,
    unit_id: str | None,
    fragment_id: str,
) -> Claim:
    return Claim(
        claim_id=claim_id,
        predicate_id=predicate_id,
        subject_id="lex.norm",
        subject_text=None,
        value_text=value_text,
        value_decimal=Decimal(value_text) if value_text.replace(".", "", 1).isdigit() else None,
        unit_id=unit_id,
        confidence=Decimal("0.6"),
        source_kind=ClaimSourceKind.DOC,
        citations=[_doc_citation(fragment_id=fragment_id)],
        jurisdiction="ua",
        domain="roads",
        qualifiers={"op": "<="},
        props={"lex": {"extractor_id": "lex.norm_extractor.regex_v1"}},
    )


def _load_norm_pack(cas: FileSystemCAS, artifact_id: str) -> NormPack:
    payload = json.loads(cas.get_bytes(ArtifactID.model_validate(artifact_id)))
    return NormPack.model_validate(payload)


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


def test_claim_to_norm_rule_mapping_is_deterministic() -> None:
    claim = Claim(
        claim_id="claim.sample",
        predicate_id="roads.max_speed_kmh",
        subject_id="lex.norm",
        subject_text=None,
        value_text="50",
        value_decimal=Decimal("50"),
        unit_id="km",
        confidence=Decimal("0.6"),
        source_kind=ClaimSourceKind.DOC,
        citations=[
            _doc_citation(fragment_id="frag.b"),
            _doc_citation(fragment_id="frag.a"),
        ],
        jurisdiction="ua",
        domain="roads",
        qualifiers={"op": "<="},
        props={"lex": {"extractor_id": "lex.norm_extractor.regex_v1"}},
    )

    kwargs = {
        "claims_by_id": {claim.claim_id: claim},
        "canonical_claim_ids": [claim.claim_id],
        "jurisdiction_norm": "ua",
        "conflict_set_by_winner": {},
        "trust_by_target": {},
        "extractor_id_by_claim": {claim.claim_id: "lex.norm_extractor.regex_v1"},
    }

    first = claims_to_norm_rules(**kwargs)
    second = claims_to_norm_rules(**kwargs)

    assert first[0].model_dump(mode="python") == second[0].model_dump(mode="python")
    assert first[0].norm_id == claim.claim_id
    assert [ref.provision_id for ref in first[0].provision_refs] == ["frag.a", "frag.b"]
    assert first[0].backend_metadata["operator"] == "<="

    runtime_like = {"started_at", "ended_at", "event_id", "run_id", "trace_id"}
    assert not runtime_like.intersection(first[0].backend_metadata)


def test_norm_rule_sorting_is_deterministic() -> None:
    claims = [
        _claim(
            claim_id="claim.speed_60",
            predicate_id="roads.max_speed_kmh",
            value_text="60",
            unit_id="km",
            fragment_id="frag.speed_60",
        ),
        _claim(
            claim_id="claim.lane_35",
            predicate_id="roads.lane_width_min_m",
            value_text="3.5",
            unit_id="m",
            fragment_id="frag.lane_35",
        ),
        _claim(
            claim_id="claim.speed_50",
            predicate_id="roads.max_speed_kmh",
            value_text="50",
            unit_id="km",
            fragment_id="frag.speed_50",
        ),
    ]
    by_id = {claim.claim_id: claim for claim in claims}

    rules_1 = claims_to_norm_rules(
        claims_by_id=by_id,
        canonical_claim_ids=["claim.speed_60", "claim.lane_35", "claim.speed_50"],
        jurisdiction_norm="ua",
        conflict_set_by_winner={},
        trust_by_target={},
        extractor_id_by_claim={claim.claim_id: "lex.norm_extractor.regex_v1" for claim in claims},
    )
    rules_2 = claims_to_norm_rules(
        claims_by_id=by_id,
        canonical_claim_ids=["claim.speed_50", "claim.speed_60", "claim.lane_35"],
        jurisdiction_norm="ua",
        conflict_set_by_winner={},
        trust_by_target={},
        extractor_id_by_claim={claim.claim_id: "lex.norm_extractor.regex_v1" for claim in claims},
    )

    assert [rule.norm_id for rule in rules_1] == [rule.norm_id for rule in rules_2]


def test_normpack_phase17_end_to_end(tmp_path: Path) -> None:
    """Persist and consume a candidate pack from explicitly manual seed bytes.

    These test-authored inputs exercise candidate computation only; they do not
    establish legal source-relation verification or protected legal authority.
    """
    cas = FileSystemCAS(tmp_path / "cas")
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))

    doc_a_text = """
ЗАКОН УКРАЇНИ

Стаття 1. Дорожній рух
norm: roads.max_speed_kmh <= 50 [km]
norm: roads.lane_width_min_m >= 3.5 [m]
""".strip()

    doc_b_text = """
ЗАКОН УКРАЇНИ

Стаття 1. Дорожній рух
norm: roads.max_speed_kmh <= 60 [km]
""".strip()

    ingest_a = ingest_legal_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=_ua_source(official_id="UA:LAW-A", effective_from="2025-01-01"),
        raw_bytes=doc_a_text.encode("utf-8"),
        mime="text/plain",
    )
    ingest_b = ingest_legal_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=_ua_source(official_id="UA:LAW-B", effective_from="2025-01-01"),
        raw_bytes=doc_b_text.encode("utf-8"),
        mime="text/plain",
    )

    build_legal_structure(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=ingest_a.doc_meta_artifact_id,
    )
    build_legal_structure(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=ingest_b.doc_meta_artifact_id,
    )

    build_version_index(
        cas=cas,
        fact_log_root=tmp_path,
        doc_source_id=ingest_a.doc_source_id,
    )
    build_version_index(
        cas=cas,
        fact_log_root=tmp_path,
        doc_source_id=ingest_b.doc_source_id,
    )

    request = NormPackBuildRequest(
        jurisdiction="ua",
        as_of="2025-06-01",
        domain="roads",
    )

    result_1 = assemble_norm_pack(
        cas=cas,
        fact_log_root=tmp_path,
        request=request,
        db=None,
    )
    result_2 = assemble_norm_pack(
        cas=cas,
        fact_log_root=tmp_path,
        request=request,
        db=None,
    )

    assert result_1.claim_set_artifact_ids
    assert all(
        load_doc_meta(cas, row.doc_meta_artifact_id).props.get("source_type") == "legal_manual_seed"
        for row in result_1.selected_doc_versions
    )
    assert result_1.norm_pack_artifact_id == result_2.norm_pack_artifact_id
    assert cas.has(ArtifactID.model_validate(result_1.norm_pack_artifact_id))

    norm_pack = _load_norm_pack(cas, result_1.norm_pack_artifact_id)
    assert norm_pack.norms

    claim_set_payloads = [
        load_json_artifact(cas, artifact_id) for artifact_id in result_1.claim_set_artifact_ids
    ]
    assert all(payload["claims"] for payload in claim_set_payloads)
    candidate_request = NormPackBuildRequest(
        jurisdiction="ua",
        as_of="2025-06-01",
        domain="roads",
        claim_set_artifact_ids=result_1.claim_set_artifact_ids,
    )
    candidate_result = assemble_norm_pack(
        cas=cas,
        fact_log_root=tmp_path,
        request=candidate_request,
        db=None,
        segment_name="normpack_manual_candidate_claim_set_replay",
    )
    assert candidate_result.claim_set_artifact_ids == result_1.claim_set_artifact_ids
    assert len(candidate_result.selected_doc_versions) == 2
    assert candidate_result.selected_fragment_ids
    assert all(
        "selected_via=claim_set_artifact_ids" in row.explanation
        for row in candidate_result.selected_doc_versions
    )
    candidate_pack = _load_norm_pack(cas, candidate_result.norm_pack_artifact_id)
    assert candidate_pack.norms
    assert set(candidate_pack.metadata["source_doc_version_ids"]) == {
        row.doc_version_id for row in candidate_result.selected_doc_versions
    }

    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    event_count = db.conn.execute(
        "SELECT COUNT(*) FROM world.world_events WHERE event_kind = 'assemble_norm_pack'"
    ).fetchone()[0]
    assert event_count >= 1
    candidate_event_count = db.conn.execute(
        "SELECT COUNT(*) FROM world.world_events WHERE event_id = ? "
        "AND event_kind = 'assemble_norm_pack'",
        [candidate_result.world_event_id],
    ).fetchone()[0]
    assert candidate_event_count == 1

    for rule in norm_pack.norms:
        for provision_ref in rule.provision_refs:
            row = db.conn.execute(
                "SELECT COUNT(*) FROM world.doc_fragments WHERE fragment_id = ?",
                [provision_ref.provision_id],
            ).fetchone()
            assert row is not None
            assert row[0] == 1

    assert result_1.conflict_set_ids
    placeholders = ", ".join(["?"] * len(result_1.conflict_set_ids))
    winners_before = dict(
        db.conn.execute(
            f"""
            SELECT conflict_set_id, winner_claim_id
            FROM world.conflict_sets
            WHERE conflict_set_id IN ({placeholders})
            """,
            result_1.conflict_set_ids,
        ).fetchall()
    )

    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)
    winners_after = dict(
        db.conn.execute(
            f"""
            SELECT conflict_set_id, winner_claim_id
            FROM world.conflict_sets
            WHERE conflict_set_id IN ({placeholders})
            """,
            result_1.conflict_set_ids,
        ).fetchall()
    )
    assert winners_before == winners_after


def test_normpack_export_refuses_unverified_source_relation_before_outputs(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lex.duckdb"
    _seed_bridge_db(db_path)

    with duckdb.connect(str(db_path), read_only=True) as con:
        assert con.execute("SELECT COUNT(*) FROM lex_normative_facts").fetchone()[0] == 2

    cas_root = tmp_path / "cas"
    fact_log_root = tmp_path / "fact_log"
    output_dir = tmp_path / "claim_exports"
    assert not cas_root.exists()
    assert not fact_log_root.exists()
    assert not output_dir.exists()

    before_entries = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}
    before_files = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    with pytest.raises(LegalSourceRelationVerificationMissingError) as refusal:
        export_normative_claim_sets(
            db_path=db_path,
            cas_root=cas_root,
            fact_log_root=fact_log_root,
            output_dir=output_dir,
        )

    assert refusal.value.refusal.code == "legal_source_relation_verification_not_established"
    assert refusal.value.refusal.status == "verification_missing"
    assert not cas_root.exists()
    assert not fact_log_root.exists()
    assert not output_dir.exists()
    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*")} == before_entries
    assert {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    } == before_files
