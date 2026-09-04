from __future__ import annotations

import duckdb
import pytest
from pydantic import ValidationError

from polisyos.data_forge.domains.academic.batch.graph_builder import _init_schema
from polisyos.data_forge.domains.academic.knowledge.store import (
    ScholarKnowledgeStore,
    load_causal_claim_results_v2,
)
from polisyos.data_forge.domains.academic.knowledge.types import (
    CausalClaimResultV1,
    CausalClaimResultV2,
    ClaimLineageCursorError,
    ClaimTableSchemaError,
    ClaimVocabularyProjectionBinding,
)


def _make_v1_db(tmp_path, *, duplicate: bool = False):
    path = tmp_path / "claims.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE ac_works (id VARCHAR PRIMARY KEY, title VARCHAR, year INTEGER)")
    con.execute("CREATE TABLE ac_causal_claims_raw (id VARCHAR PRIMARY KEY, work_id VARCHAR NOT NULL, cause VARCHAR NOT NULL, effect VARCHAR NOT NULL, direction VARCHAR, strength VARCHAR, claim_text VARCHAR, claim_explicitness VARCHAR, design_family_hint VARCHAR, source_basis VARCHAR, claim_extraction_confidence FLOAT DEFAULT 0.0, strong_design_evidence BOOLEAN DEFAULT FALSE, design_quality_tier INTEGER, publish_to_graph BOOLEAN DEFAULT FALSE, publish_blockers VARCHAR DEFAULT '', span_contamination_detected BOOLEAN DEFAULT FALSE, mechanism VARCHAR, domain VARCHAR, trust_score FLOAT DEFAULT 0.0)")
    con.execute("CREATE TABLE ac_causal_claims (id VARCHAR PRIMARY KEY, work_id VARCHAR NOT NULL, cause VARCHAR NOT NULL, effect VARCHAR NOT NULL, direction VARCHAR, strength VARCHAR, design_family_hint VARCHAR, claim_extraction_confidence FLOAT DEFAULT 0.0, strong_design_evidence BOOLEAN DEFAULT FALSE, design_quality_tier INTEGER, publish_blockers VARCHAR DEFAULT '', candidate_layer VARCHAR DEFAULT 'candidate', mechanism VARCHAR, domain VARCHAR, trust_score FLOAT DEFAULT 0.0)")
    con.execute("INSERT INTO ac_works VALUES ('w1', 'Work 1', 2024), ('w2', 'Work 2', 2023)")
    rows = [
        ('c1', 'w1', 'cause', 'effect', 'positive', 'moderate', 'text', 'explicit', 'rct', 'fulltext', 0.91, True, 1, True, '', False, 'm', 'd', 0.8),
        ('c2', 'w2', 'cause', 'effect', 'negative', 'rct', 'text', 'explicit', 'theoretical', 'abstract_only', 0.42, False, 4, False, 'blocked', False, 'm2', 'd', 0.4),
        ('c3', 'w1', 'cause2', 'effect2', 'mixed', 'observational', '', '', '', '', 0.0, False, None, False, '', False, '', '', 0.2),
    ]
    con.executemany("INSERT INTO ac_causal_claims_raw VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    con.executemany("INSERT INTO ac_causal_claims VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
        (r[0], r[1], r[2], r[3], r[4], r[5], r[8], r[10], r[11], r[12], r[14], 'candidate', r[16], r[17], r[18]) for r in rows[:2]
    ])
    if duplicate:
        con.execute("CREATE TABLE duplicate_raw (id VARCHAR, work_id VARCHAR, cause VARCHAR, effect VARCHAR, strength VARCHAR)")
    con.close()
    return path


def _make_v2_db(tmp_path):
    path = tmp_path / "claims-v2.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE ac_works (id VARCHAR PRIMARY KEY, title VARCHAR, year INTEGER)")
    con.execute(
        "CREATE TABLE ac_causal_claims ("
        "id VARCHAR PRIMARY KEY, work_id VARCHAR NOT NULL, cause VARCHAR NOT NULL, "
        "effect VARCHAR NOT NULL, direction VARCHAR, mechanism VARCHAR, domain VARCHAR, "
        "trust_score FLOAT DEFAULT 0.0, "
        "claim_vocabulary_schema_version VARCHAR NOT NULL DEFAULT '2.0', "
        "design_family_hint VARCHAR, "
        "design_family_hint_status VARCHAR NOT NULL DEFAULT 'not_established', "
        "evidence_strength VARCHAR, "
        "evidence_strength_status VARCHAR NOT NULL DEFAULT 'not_established', "
        "claim_extraction_confidence FLOAT, "
        "claim_extraction_confidence_status VARCHAR NOT NULL DEFAULT 'not_established', "
        "source_basis VARCHAR, source_basis_status VARCHAR NOT NULL DEFAULT 'not_established', "
        "legacy_strength_label VARCHAR, record_extraction_mode VARCHAR)"
    )
    con.execute("INSERT INTO ac_works VALUES ('w1', 'Work 1', 2024)")
    con.execute(
        "INSERT INTO ac_causal_claims ("
        "id, work_id, cause, effect, direction, mechanism, domain, trust_score, "
        "design_family_hint, design_family_hint_status, evidence_strength, "
        "evidence_strength_status, claim_extraction_confidence, "
        "claim_extraction_confidence_status, source_basis, source_basis_status, "
        "record_extraction_mode) VALUES ("
        "'c1', 'w1', 'cause', 'effect', 'positive', '', '', 0.8, 'ols', 'candidate', "
        "'rct', 'candidate', 0.37, 'candidate', 'abstract_only', 'candidate', 'llm')"
    )
    con.close()
    return path


def _make_v2_raw_db(tmp_path):
    path = tmp_path / "claims-v2-raw.duckdb"
    con = duckdb.connect(str(path))
    _init_schema(con)
    con.execute(
        "INSERT INTO ac_causal_claims_raw ("
        "id, work_id, cause, effect, direction, design_family_hint, "
        "design_family_hint_status, evidence_strength, evidence_strength_status, "
        "claim_extraction_confidence, claim_extraction_confidence_status, source_basis, "
        "source_basis_status, mechanism, trust_score) VALUES ("
        "'c1', 'w1', 'cause', 'effect', 'positive', 'ols', 'candidate', "
        "'rct', 'candidate', 0.37, 'candidate', 'abstract_only', 'candidate', '', 0.8)"
    )
    con.close()
    return path


@pytest.mark.parametrize("label", ["moderate", "rct", "theoretical", "observational", "", " malformed ", "future"])
def test_legacy_claim_projection_keeps_generic_strength_audit_only(tmp_path, label):
    path = _make_v1_db(tmp_path)
    con = duckdb.connect(str(path))
    con.execute("UPDATE ac_causal_claims_raw SET strength = ? WHERE id = 'c1'", [label])
    con.execute("UPDATE ac_causal_claims SET strength = ? WHERE id = 'c1'", [label])
    con.close()
    store = ScholarKnowledgeStore(path, tmp_path)
    result = store.get_causal_claims("cause", "effect")[0]
    assert result.legacy_strength_label == label
    assert result.design_family_hint is None
    assert result.evidence_strength is None
    assert result.claim_extraction_confidence is None
    assert result.source_basis is None
    assert result.design_family_hint_status.value == "not_established"
    assert result.evidence_strength_status.value == "not_established"
    assert result.claim_extraction_confidence_status.value == "not_established"
    assert result.source_basis_status.value == "not_established"


def test_legacy_lookalike_evidence_strength_is_not_admitted_without_discriminator(tmp_path):
    path = _make_v1_db(tmp_path)
    con = duckdb.connect(str(path))
    con.execute("ALTER TABLE ac_causal_claims ADD COLUMN evidence_strength VARCHAR")
    con.execute("UPDATE ac_causal_claims SET evidence_strength = 'rct' WHERE id = 'c1'")
    con.close()
    result = ScholarKnowledgeStore(path, tmp_path).get_causal_claims("cause", "effect")[0]
    assert result.evidence_strength is None
    assert result.legacy_strength_label == "moderate"


def test_explicit_v2_round_trip_preserves_disagreeing_axes(tmp_path):
    path = _make_v2_db(tmp_path)
    result = ScholarKnowledgeStore(path, tmp_path).get_causal_claims("cause", "effect")[0]
    assert isinstance(result, CausalClaimResultV2)
    assert result.design_family_hint.value == "ols"
    assert result.evidence_strength.value == "rct"
    assert result.claim_extraction_confidence == pytest.approx(0.37)
    assert result.source_basis.value == "abstract_only"
    assert result.record_extraction_mode == "llm"


@pytest.mark.parametrize(
    ("assignment", "message"),
    [
        ("claim_vocabulary_schema_version = '3.0'", "invalid explicit_v2 row"),
        ("evidence_strength = NULL", "invalid explicit_v2 row"),
        ("design_family_hint = 'future_design'", "invalid explicit_v2 row"),
    ],
)
def test_explicit_v2_future_or_value_status_mismatch_fails_typed(
    tmp_path,
    assignment,
    message,
):
    path = _make_v2_db(tmp_path)
    con = duckdb.connect(str(path))
    con.execute(
        f"UPDATE ac_causal_claims SET {assignment} WHERE id = 'c1'"  # noqa: S608
    )
    con.close()

    with pytest.raises(ClaimTableSchemaError, match=message):
        ScholarKnowledgeStore(path, tmp_path).get_causal_claims("cause", "effect")


def test_causal_claim_result_v2_forbids_strength():
    with pytest.raises(ValidationError, match="strength"):
        CausalClaimResultV2.model_validate({
            "id": "c",
            "cause": "a",
            "effect": "b",
            "projection_binding": {
                "projection_rule_version": "policyos.academic.claim-vocabulary-projection.v2",
                "subject_kind": "claim_row",
                "source_rows": [{
                    "source_table": "ac_causal_claims",
                    "source_schema_version": "legacy_v1",
                    "source_identity": "c",
                    "source_row_sha256": "0" * 64,
                }],
                "projected_vocabulary_sha256": "1" * 64,
            },
            "strength": "moderate",
        })


def test_deprecated_v1_audit_always_returns_strength_none_with_limitation(tmp_path):
    path = _make_v1_db(tmp_path)
    result = ScholarKnowledgeStore(path, tmp_path).get_causal_claims_v1_audit("cause", "effect")[0]
    assert isinstance(result, CausalClaimResultV1)
    assert result.strength is None
    assert result.limitation.value == "ambiguous_legacy_vocabulary"


def test_raw_claim_audit_paginates_every_fixture_identity_once(tmp_path):
    path = _make_v1_db(tmp_path)
    store = ScholarKnowledgeStore(path, tmp_path)
    page = store.audit_claim_lineage(status="all", limit=2)
    assert page.total_identities == 3
    assert len(page.items) == 2
    assert page.next_cursor
    page2 = store.audit_claim_lineage(status="all", cursor=page.next_cursor, limit=2)
    assert [item.id for item in page.items + page2.items] == ["c1", "c2", "c3"]
    assert page2.next_cursor is None


def test_raw_claim_audit_later_page_uses_keyset_and_skips_total_recount(tmp_path):
    class RecordingConnection:
        def __init__(self, connection):
            self.connection = connection
            self.calls = []

        def execute(self, query, parameters=None):
            self.calls.append((query, parameters))
            if parameters is None:
                return self.connection.execute(query)
            return self.connection.execute(query, parameters)

        def __getattr__(self, name):
            return getattr(self.connection, name)

    path = _make_v1_db(tmp_path)
    store = ScholarKnowledgeStore(path, tmp_path)
    recorder = RecordingConnection(store._con)
    store._con = recorder
    first = store.audit_claim_lineage(status="all", limit=1)
    assert first.next_cursor

    recorder.calls.clear()
    store.audit_claim_lineage(status="all", cursor=first.next_cursor, limit=1)

    statements = [query for query, _ in recorder.calls]
    assert not any("COUNT(" in query.upper() for query in statements)
    assert not any("OFFSET" in query.upper() for query in statements)
    page_query, page_parameters = next(
        (query, parameters)
        for query, parameters in recorder.calls
        if "FROM ac_causal_claims_raw c WHERE" in query
    )
    assert "(c.id, c.work_id) > (?, ?)" in page_query
    assert page_parameters == ["c1", "w1", 2]


def test_raw_claim_audit_candidate_filter_is_empty_for_legacy_rows(tmp_path):
    path = _make_v1_db(tmp_path)
    page = ScholarKnowledgeStore(path, tmp_path).audit_claim_lineage(status="candidate")
    assert page.total_identities == 0
    assert page.items == ()


def test_raw_claim_audit_rejects_cursor_filter_or_schema_mismatch(tmp_path):
    path = _make_v1_db(tmp_path)
    store = ScholarKnowledgeStore(path, tmp_path)
    cursor = store.audit_claim_lineage(status="all", limit=1).next_cursor
    assert cursor
    with pytest.raises(ClaimLineageCursorError):
        store.audit_claim_lineage(status="candidate", cursor=cursor, limit=1)


def test_raw_claim_audit_rejects_cursor_identity_constraint_shape_mismatch(tmp_path, monkeypatch):
    path = _make_v1_db(tmp_path)
    store = ScholarKnowledgeStore(path, tmp_path)
    cursor = store.audit_claim_lineage(status="all", limit=1).next_cursor
    assert cursor
    monkeypatch.setattr(
        store,
        "_identity_constraint_descriptor",
        lambda table: ("memory", "main", f"{table}_different", "UNIQUE", ("id", "work_id")),
    )
    with pytest.raises(ClaimLineageCursorError, match="invalid or incompatible"):
        store.audit_claim_lineage(status="all", cursor=cursor, limit=1)


def test_raw_claim_audit_does_not_borrow_identity_constraint_from_other_schema(
    tmp_path,
):
    path = tmp_path / "schema-shadow.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE SCHEMA shadow")
    for qualified, identity in (
        ("ac_causal_claims_raw", "id VARCHAR"),
        ("shadow.ac_causal_claims_raw", "id VARCHAR PRIMARY KEY"),
    ):
        con.execute(
            f"CREATE TABLE {qualified} ({identity}, work_id VARCHAR NOT NULL, "
            "cause VARCHAR NOT NULL, effect VARCHAR NOT NULL, direction VARCHAR, "
            "strength VARCHAR, mechanism VARCHAR, trust_score FLOAT)"
        )
    con.execute(
        "INSERT INTO ac_causal_claims_raw VALUES "
        "('c1', 'w1', 'a', 'b', 'positive', 'moderate', '', 0.5), "
        "('c1', 'w1', 'a', 'b', 'positive', 'moderate', '', 0.5)"
    )
    con.close()

    store = ScholarKnowledgeStore(path, tmp_path)
    assert store._identity_constraint_descriptor("ac_causal_claims_raw") is None
    with pytest.raises(ClaimLineageCursorError, match="uniqueness constraint"):
        store.audit_claim_lineage()


def test_raw_claim_audit_reconciles_unique_unconstrained_legacy_identities(
    tmp_path,
):
    path = tmp_path / "unconstrained-unique.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE ac_causal_claims_raw ("
        "id VARCHAR, work_id VARCHAR, cause VARCHAR, effect VARCHAR, "
        "direction VARCHAR, strength VARCHAR, mechanism VARCHAR, trust_score FLOAT)"
    )
    con.execute(
        "INSERT INTO ac_causal_claims_raw VALUES "
        "('c1', 'w1', 'a', 'b', 'positive', 'moderate', '', 0.5), "
        "('c2', 'w2', 'a', 'b', 'positive', 'moderate', '', 0.5), "
        "('c3', 'w3', 'a', 'b', 'positive', 'moderate', '', 0.5)"
    )
    con.close()

    store = ScholarKnowledgeStore(path, tmp_path)
    first = store.audit_claim_lineage(limit=2)
    second = store.audit_claim_lineage(cursor=first.next_cursor, limit=2)

    assert first.total_identities == 3
    assert [item.id for item in first.items + second.items] == ["c1", "c2", "c3"]
    assert second.next_cursor is None


def test_filtered_legacy_audit_rejects_duplicate_full_relation_before_empty_candidate_page(
    tmp_path,
):
    path = tmp_path / "unconstrained-duplicate-legacy.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE ac_causal_claims_raw ("
        "id VARCHAR, work_id VARCHAR, cause VARCHAR, effect VARCHAR, "
        "direction VARCHAR, strength VARCHAR, mechanism VARCHAR, trust_score FLOAT)"
    )
    con.execute(
        "INSERT INTO ac_causal_claims_raw VALUES "
        "('duplicate', 'w1', 'a', 'b', 'positive', 'moderate', '', 0.5), "
        "('duplicate', 'w1', 'a', 'b', 'positive', 'moderate', '', 0.5)"
    )
    con.close()

    with pytest.raises(ClaimLineageCursorError, match="duplicate or null identities"):
        ScholarKnowledgeStore(path, tmp_path).audit_claim_lineage(status="candidate")


def test_partial_or_future_claim_table_schema_fails_typed(tmp_path):
    path = _make_v1_db(tmp_path)
    con = duckdb.connect(str(path))
    con.execute("ALTER TABLE ac_causal_claims_raw ADD COLUMN claim_vocabulary_schema_version VARCHAR")
    con.close()
    with pytest.raises(ClaimTableSchemaError):
        ScholarKnowledgeStore(path, tmp_path).audit_claim_lineage()


@pytest.mark.parametrize(
    "assignment",
    [
        "evidence_strength_status = 'future_status'",
        "evidence_strength = NULL",
        "claim_vocabulary_schema_version = '3.0'",
    ],
)
def test_filtered_v2_audit_cannot_hide_invalid_rows(tmp_path, assignment):
    path = _make_v2_raw_db(tmp_path)
    con = duckdb.connect(str(path))
    con.execute(
        f"UPDATE ac_causal_claims_raw SET {assignment} WHERE id = 'c1'"  # noqa: S608
    )
    con.close()

    with pytest.raises(ClaimTableSchemaError, match="invalid explicit_v2 row"):
        ScholarKnowledgeStore(path, tmp_path).audit_claim_lineage(
            status="not_established"
        )


def test_projection_binding_rejects_non_sha256_digests():
    with pytest.raises(ValidationError, match="source_row_sha256"):
        ClaimVocabularyProjectionBinding.model_validate(
            {
                "projection_rule_version": "policyos.academic.claim-vocabulary-projection.v2",
                "subject_kind": "claim_row",
                "source_rows": [{
                    "source_table": "ac_causal_claims",
                    "source_schema_version": "legacy_v1",
                    "source_identity": "c1",
                    "source_row_sha256": "not-a-sha256" + "0" * 53,
                }],
                "projected_vocabulary_sha256": "f" * 64,
            }
        )


def test_projection_binding_distinguishes_physical_and_projected_mutations(tmp_path):
    path = _make_v1_db(tmp_path)

    def binding_for_c1():
        store = ScholarKnowledgeStore(path, tmp_path)
        try:
            return next(
                item.projection_binding
                for item in store.get_causal_claims("cause", "effect")
                if item.id == "c1"
            )
        finally:
            store.close()

    original = binding_for_c1()
    con = duckdb.connect(str(path))
    con.execute("UPDATE ac_causal_claims SET trust_score = 0.73 WHERE id = 'c1'")
    con.close()
    operational_change = binding_for_c1()

    assert (
        operational_change.source_rows[0].source_row_sha256
        != original.source_rows[0].source_row_sha256
    )
    assert (
        operational_change.projected_vocabulary_sha256
        == original.projected_vocabulary_sha256
    )

    con = duckdb.connect(str(path))
    con.execute("UPDATE ac_causal_claims SET strength = 'future-label' WHERE id = 'c1'")
    con.close()
    vocabulary_change = binding_for_c1()

    assert (
        vocabulary_change.source_rows[0].source_row_sha256
        != operational_change.source_rows[0].source_row_sha256
    )
    assert (
        vocabulary_change.projected_vocabulary_sha256
        != operational_change.projected_vocabulary_sha256
    )


def test_edge_projection_binds_physical_row_and_rejects_forged_source_bytes(tmp_path):
    path = tmp_path / "edges.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE ac_skg_edges (edge_id VARCHAR PRIMARY KEY, src VARCHAR, dst VARCHAR, direction VARCHAR, evidence_strength VARCHAR, confidence FLOAT)")
    con.execute("INSERT INTO ac_skg_edges VALUES ('e1', 'a', 'b', 'positive', 'rct', 0.9)")
    con.close()
    store = ScholarKnowledgeStore(path, tmp_path)
    with pytest.raises(ClaimTableSchemaError, match="source row binding mismatch"):
        store.project_edge_summary(
            source_table="ac_skg_edges",
            source_identity="e1",
            source_row={"edge_id": "e1", "src": "a", "dst": "forged"},
            cause="a",
            effect="b",
            direction="positive",
            evidence_strength="rct",
            mechanism="exact_support",
            domain="",
            trust_score=0.9,
            work_title="",
        )


def test_streaming_projection_matches_normal_reader_work_enrichment(tmp_path):
    path = _make_v1_db(tmp_path)
    normal = ScholarKnowledgeStore(path, tmp_path).get_causal_claims("cause", "effect")
    streamed = list(load_causal_claim_results_v2(path))
    assert [(item.id, item.work_title, item.work_year) for item in streamed] == [
        (item.id, item.work_title, item.work_year) for item in normal
    ]
    assert streamed[0].projection_binding.source_rows[0].source_row_sha256 == normal[0].projection_binding.source_rows[0].source_row_sha256


@pytest.mark.parametrize("encoded", ['["review", "missing_basis"]', "review,missing_basis", "review; missing_basis"])
def test_store_preserves_operational_blocker_encodings(tmp_path, encoded):
    path = _make_v1_db(tmp_path)
    con = duckdb.connect(str(path))
    con.execute("UPDATE ac_causal_claims SET publish_blockers = ? WHERE id = 'c1'", [encoded])
    con.close()
    result = ScholarKnowledgeStore(path, tmp_path).get_causal_claims("cause", "effect")[0]
    assert result.publish_blockers == ("review", "missing_basis")


def test_missing_claim_table_and_missing_legacy_base_columns_fail_typed(tmp_path):
    missing_path = tmp_path / "missing.duckdb"
    con = duckdb.connect(str(missing_path))
    con.execute("CREATE TABLE ac_works (id VARCHAR PRIMARY KEY, title VARCHAR, year INTEGER)")
    con.close()
    with pytest.raises(ClaimTableSchemaError, match="claim table is missing"):
        ScholarKnowledgeStore(missing_path, tmp_path).get_causal_claims("a", "b")

    partial_path = tmp_path / "partial.duckdb"
    con = duckdb.connect(str(partial_path))
    con.execute("CREATE TABLE ac_works (id VARCHAR PRIMARY KEY, title VARCHAR, year INTEGER)")
    con.execute(
        "CREATE TABLE ac_causal_claims (id VARCHAR PRIMARY KEY, work_id VARCHAR, "
        "cause VARCHAR, effect VARCHAR, strength VARCHAR)"
    )
    con.close()
    with pytest.raises(ClaimTableSchemaError, match="base columns"):
        ScholarKnowledgeStore(partial_path, tmp_path).get_causal_claims("a", "b")


def test_edge_projection_rejects_semantics_that_do_not_match_physical_row(tmp_path):
    path = tmp_path / "edge-semantics.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE ac_skg_edges (edge_id VARCHAR PRIMARY KEY, src VARCHAR, dst VARCHAR, "
        "direction VARCHAR, evidence_strength VARCHAR, confidence FLOAT)"
    )
    con.execute("INSERT INTO ac_skg_edges VALUES ('e1', 'physical-a', 'physical-b', 'negative', 'rct', 0.9)")
    con.close()

    store = ScholarKnowledgeStore(path, tmp_path)
    with pytest.raises(ClaimTableSchemaError, match="source row semantics mismatch"):
        store.project_edge_summary(
            source_table="ac_skg_edges",
            source_identity="e1",
            cause="forged-a",
            effect="physical-b",
            direction="negative",
            evidence_strength="rct",
            mechanism="exact_support",
            domain="",
            trust_score=0.9,
            work_title="",
        )


@pytest.mark.parametrize("stored", [None, "", "not-an-evidence-enum"])
def test_edge_projection_null_is_absence_and_invalid_nonblank_is_typed(tmp_path, stored):
    path = tmp_path / f"edge-{stored or 'null'}.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE ac_skg_edges (edge_id VARCHAR PRIMARY KEY, src VARCHAR, dst VARCHAR, "
        "direction VARCHAR, evidence_strength VARCHAR, confidence FLOAT)"
    )
    con.execute("INSERT INTO ac_skg_edges VALUES ('e1', 'a', 'b', 'positive', ?, 0.9)", [stored])
    con.close()

    store = ScholarKnowledgeStore(path, tmp_path)
    if stored == "not-an-evidence-enum":
        with pytest.raises(ClaimTableSchemaError, match="invalid evidence_strength"):
            store.project_edge_summary(
                source_table="ac_skg_edges",
                source_identity="e1",
                cause="a",
                effect="b",
                direction="positive",
                evidence_strength=stored,
                mechanism="exact_support",
                domain="",
                trust_score=0.9,
                work_title="",
            )
    else:
        projected = store.project_edge_summary(
            source_table="ac_skg_edges",
            source_identity="e1",
            cause="a",
            effect="b",
            direction="positive",
            evidence_strength=None,
            mechanism="exact_support",
            domain="",
            trust_score=0.9,
            work_title="",
        )
        assert projected.evidence_strength is None
        assert projected.evidence_strength_status.value == "not_established"


def test_edge_projection_preserves_explicit_theoretical_evidence(tmp_path):
    path = tmp_path / "edge-theoretical.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE ac_skg_edges (edge_id VARCHAR PRIMARY KEY, src VARCHAR, dst VARCHAR, "
        "direction VARCHAR, evidence_strength VARCHAR, confidence FLOAT)"
    )
    con.execute(
        "INSERT INTO ac_skg_edges VALUES "
        "('e1', 'a', 'b', 'positive', 'theoretical', 0.4)"
    )
    con.close()

    projected = ScholarKnowledgeStore(path, tmp_path).project_edge_summary(
        source_table="ac_skg_edges",
        source_identity="e1",
        cause="a",
        effect="b",
        direction="positive",
        evidence_strength="theoretical",
        mechanism="exact_support",
        domain="",
        trust_score=0.4,
        work_title="",
    )

    assert projected.evidence_strength is not None
    assert projected.evidence_strength.value == "theoretical"
    assert projected.evidence_strength_status.value == "candidate"
