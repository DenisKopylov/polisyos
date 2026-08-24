from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.lex.knowledge.store import LegalKnowledgeStore
from polisyos.runtime.quality import semantic_epoch


def _amendment_query(
    *,
    knowledge_cutoff: bytes,
    admission_cutoff: bytes = b"2026-01-01T00:00:00Z",
) -> epoch_contract.LegalAmendmentWindowResolutionQuery:
    valid = b"2025-01-15"
    profiles = {
        "valid_effect": "epoch.coordinate.valid-date.v1",
        "visibility_knowledge_cutoff": "epoch.coordinate.knowledge-time.v1",
        "purpose_admission_cutoff": "epoch.coordinate.admission-time.v1",
    }
    return epoch_contract.LegalAmendmentWindowResolutionQuery(
        jurisdiction="UA",
        domain="fiscal",
        authority_purpose="publication",
        valid_effect_value=__import__("datetime").date.fromisoformat(valid.decode()),
        valid_effect_coordinate_schema_profile=profiles["valid_effect"],
        valid_effect_coordinate_ref=epoch_contract.native_coordinate_ref(
            family="lex_amendment_window",
            role="valid_effect",
            schema_profile=profiles["valid_effect"],
            coordinate_bytes=valid,
        ),
        visibility_knowledge_cutoff_schema_profile=(profiles["visibility_knowledge_cutoff"]),
        visibility_knowledge_cutoff_bytes=knowledge_cutoff,
        visibility_knowledge_cutoff_ref=epoch_contract.native_coordinate_ref(
            family="lex_amendment_window",
            role="visibility_knowledge_cutoff",
            schema_profile=profiles["visibility_knowledge_cutoff"],
            coordinate_bytes=knowledge_cutoff,
        ),
        purpose_admission_cutoff_schema_profile=profiles["purpose_admission_cutoff"],
        purpose_admission_cutoff_bytes=admission_cutoff,
        purpose_admission_cutoff_ref=epoch_contract.native_coordinate_ref(
            family="lex_amendment_window",
            role="purpose_admission_cutoff",
            schema_profile=profiles["purpose_admission_cutoff"],
            coordinate_bytes=admission_cutoff,
        ),
        requested_query_context_ref=(
            "sha256:1111111111111111111111111111111111111111111111111111111111111111"
        ),
    )


def test_legal_store_evidence_refs_ignore_physical_checkout_path(tmp_path) -> None:
    canonical_path = Path("production_data/lex/canonical/lex_knowledge_graph.duckdb")
    observed = []
    threshold_row = (
        "threshold-1",
        "fact-1",
        "tax_rate",
        "<=",
        0.2,
        "",
        "ratio",
        "firms",
        "doc-1",
        "family-1",
        "version-1",
        "body:1/item:1",
        "article 1",
        "UA",
        "fiscal",
        "obligation",
        "obligation",
        "2024-01-01",
        "",
        "resolved",
        "normative_fact",
    )
    for checkout_name in ("checkout-a", "checkout-b"):
        db_path = tmp_path / checkout_name / "lex_knowledge_graph.duckdb"
        db_path.parent.mkdir()
        with duckdb.connect(str(db_path)):
            pass
        store = LegalKnowledgeStore(
            db_path=db_path,
            index_dir=db_path.parent,
            canonical_db_ref_path=canonical_path,
        )
        try:
            threshold = store._to_rule_threshold_row(threshold_row)
            evaluation = store._threshold_evaluation(
                threshold,
                status="admitted",
                reason="threshold_satisfied",
            )
            observed.append((threshold.provision_ref, evaluation.threshold_ref))
        finally:
            store.close()

    expected_provision_ref = (
        "duckdb://production_data/lex/canonical/lex_knowledge_graph.duckdb"
        "#lex_provisions/doc-1:body:1/item:1"
    )
    expected_threshold_ref = (
        "duckdb://production_data/lex/canonical/lex_knowledge_graph.duckdb"
        "#lex_rule_thresholds/threshold-1"
    )
    assert observed == [
        (expected_provision_ref, expected_threshold_ref),
        (expected_provision_ref, expected_threshold_ref),
    ]


def test_legal_knowledge_store_prefers_high_trust_layers(tmp_path) -> None:
    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            """
            CREATE TABLE lex_facts (
                fact_id VARCHAR,
                subject_id VARCHAR,
                subject_en VARCHAR,
                predicate VARCHAR,
                object_id VARCHAR,
                object_en VARCHAR,
                fact_text VARCHAR,
                confidence REAL,
                norm_type VARCHAR,
                action_canon VARCHAR,
                norm_type_canon VARCHAR,
                condition_text_uk VARCHAR,
                exception_text_uk VARCHAR,
                procedure_text_uk VARCHAR,
                thresholds_json VARCHAR,
                source_quote_uk VARCHAR,
                trust_tier VARCHAR,
                grounding_status VARCHAR,
                canonical_status VARCHAR,
                reference_resolution_status VARCHAR,
                structure_quality VARCHAR,
                constraint_type_canon VARCHAR,
                jurisdiction VARCHAR,
                top_domain VARCHAR,
                effective_from VARCHAR,
                effective_to VARCHAR,
                doc_name VARCHAR,
                doc_reestr_code VARCHAR,
                provision_citation VARCHAR
            )
            """
        )
        con.execute("CREATE TABLE lex_fact_grounded AS SELECT * FROM lex_facts WHERE 1 = 0")
        con.execute("CREATE TABLE lex_normative_facts AS SELECT * FROM lex_facts WHERE 1 = 0")
        con.execute(
            """
            CREATE TABLE lex_rule_thresholds (
                threshold_id VARCHAR,
                fact_id VARCHAR,
                metric VARCHAR
            )
            """
        )
        row = (
            "f1",
            "s1",
            "body",
            "requires",
            "o1",
            "permit",
            "Body requires permit",
            0.9,
            "obligation",
            "requires",
            "obligation",
            "",
            "",
            "",
            '[{"metric":"vat_rate"}]',
            "Орган зобов'язаний надати дозвіл.",
            "normative_fact",
            "exact_quote",
            "canonicalized",
            "resolved",
            "structured_legal_unit",
            "",
            "UA",
            "transport",
            "2024-01-01",
            "",
            "Mock law",
            "123",
            "стаття 1",
        )
        con.execute(
            "INSERT INTO lex_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )
        con.execute(
            "INSERT INTO lex_fact_grounded VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )
        con.execute(
            "INSERT INTO lex_normative_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )
        con.execute("INSERT INTO lex_rule_thresholds VALUES ('t1', 'f1', 'vat_rate')")

    store = LegalKnowledgeStore(db_path=db_path, index_dir=tmp_path)
    try:
        facts = store.text_search_facts("permit", domain="transport")
        assert len(facts) == 1
        assert facts[0].trust_tier == "normative_fact"

        constraints = store.find_constraints(domain="transport", jurisdiction="UA")
        assert len(constraints) == 1

        thresholds = store.search_facts_with_threshold("vat_rate", domain="transport")
        assert len(thresholds) == 1

        norms = store.get_applicable_norms(
            domain="transport", jurisdiction="UA", as_of="2024-02-01"
        )
        assert len(norms) == 1
    finally:
        store.close()


def test_missing_native_table_is_blocked_not_empty(tmp_path: Path) -> None:
    db_path = tmp_path / "missing-owner-tables.duckdb"
    with duckdb.connect(str(db_path)):
        pass
    owner = LegalKnowledgeStore(db_path=db_path, index_dir=tmp_path)
    artifacts = FileSystemCAS(tmp_path / "cas")
    adapter = semantic_epoch.LexEpochBoundaryOwnerAdapter(
        owner=owner,
        artifacts=artifacts,
    )
    registration = semantic_epoch.EpochBoundarySourceRegistration(
        registration_id="all-amendments",
        owner_kind="lex_amendment_window",
        owner_source_ref=(
            "sha256:2222222222222222222222222222222222222222222222222222222222222222"
        ),
        opaque_scope_binding_ref=(
            "sha256:3333333333333333333333333333333333333333333333333333333333333333"
        ),
    )
    try:
        batch = adapter.resolve_complete_batch(
            registration=registration,
            owner_query=_amendment_query(knowledge_cutoff=b"2025-03-01T00:00:00Z"),
        )
    finally:
        owner.close()

    assert batch.status == "unresolved"
    assert batch.declared_member_count == 0
    assert batch.assessments == ()
    assert batch.failure_codes == ("amendment_owner_table_not_established",)
    assert batch.owner_source_snapshot_ref is not None


def test_retroactive_row_differs_before_and_after_knowledge_cutoff(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "retroactive-amendment.duckdb"
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            """
            CREATE TABLE lex_amendments (
                amendment_id VARCHAR,
                amended_doc_id VARCHAR,
                target_anchor VARCHAR,
                effective_from TIMESTAMP,
                created_at TIMESTAMP
            )
            """
        )
        con.execute(
            """
            CREATE TABLE lex_facts (
                doc_id VARCHAR,
                jurisdiction VARCHAR,
                top_domain VARCHAR
            )
            """
        )
        con.execute(
            "INSERT INTO lex_amendments VALUES "
            "('a-1', 'doc-1', 'article-1', '2025-01-01', '2025-02-01')"
        )
        con.execute("INSERT INTO lex_facts VALUES ('doc-1', 'UA', 'fiscal')")
    store = LegalKnowledgeStore(db_path=db_path, index_dir=tmp_path)
    try:
        before = store.resolve_amendment_window_denominator(
            query=_amendment_query(knowledge_cutoff=b"2025-01-31T23:59:59Z")
        )
        after = store.resolve_amendment_window_denominator(
            query=_amendment_query(knowledge_cutoff=b"2025-02-02T00:00:00Z")
        )
    finally:
        store.close()

    assert before.owner_source_snapshot_ref == after.owner_source_snapshot_ref
    assert before.declared_amendment_count == after.declared_amendment_count == 1
    assert before.assessments[0].disposition == "not_applicable"
    assert after.assessments[0].disposition == "applicable"
    assert before.denominator_hash != after.denominator_hash


def test_missing_amendment_effective_window_stays_in_complete_denominator(
    tmp_path: Path,
) -> None:
    """An owner row without a valid/effect coordinate is unresolved, not omitted."""

    db_path = tmp_path / "missing-amendment-window.duckdb"
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            """
            CREATE TABLE lex_amendments (
                amendment_id VARCHAR,
                amended_doc_id VARCHAR,
                target_anchor VARCHAR,
                effective_from VARCHAR,
                created_at TIMESTAMP
            )
            """
        )
        con.execute(
            """
            CREATE TABLE lex_facts (
                doc_id VARCHAR,
                jurisdiction VARCHAR,
                top_domain VARCHAR
            )
            """
        )
        con.execute(
            "INSERT INTO lex_amendments VALUES "
            "('a-missing-window', 'doc-1', 'article-1', '', '2025-02-01')"
        )
        con.execute("INSERT INTO lex_facts VALUES ('doc-1', 'UA', 'fiscal')")
    store = LegalKnowledgeStore(db_path=db_path, index_dir=tmp_path)
    try:
        receipt = store.resolve_amendment_window_denominator(
            query=_amendment_query(knowledge_cutoff=b"2025-02-02T00:00:00Z")
        )
        snapshot = store.load_amendment_owner_snapshot(ref=receipt.owner_source_snapshot_ref)
    finally:
        store.close()

    assert receipt.declared_amendment_count == len(receipt.assessments) == 1
    assert receipt.status == "unresolved"
    assert receipt.failure_codes == ("amendment_valid_effect_window_unresolved",)
    assert receipt.assessments[0].effective_from is None
    assert receipt.assessments[0].failure_code == ("amendment_valid_effect_window_unresolved")
    assert b'"effective_from":""' in snapshot


def test_legal_knowledge_store_supports_quality_band_and_fused_confidence_filters(tmp_path) -> None:
    db_path = tmp_path / "lex_quality_graph.duckdb"
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            """
            CREATE TABLE lex_normative_facts (
                fact_id VARCHAR,
                subject_en VARCHAR,
                predicate VARCHAR,
                object_en VARCHAR,
                fact_text VARCHAR,
                confidence REAL,
                norm_type VARCHAR,
                action_canon VARCHAR,
                norm_type_canon VARCHAR,
                thresholds_json VARCHAR,
                source_quote_uk VARCHAR,
                trust_tier VARCHAR,
                grounding_status VARCHAR,
                canonical_status VARCHAR,
                reference_resolution_status VARCHAR,
                structure_quality VARCHAR,
                constraint_type_canon VARCHAR,
                jurisdiction VARCHAR,
                top_domain VARCHAR,
                effective_from VARCHAR,
                effective_to VARCHAR,
                doc_name VARCHAR,
                doc_reestr_code VARCHAR,
                provision_citation VARCHAR,
                fused_confidence REAL,
                quality_band VARCHAR
            )
            """
        )
        con.execute(
            "CREATE TABLE lex_high_confidence_norms AS SELECT * FROM lex_normative_facts WHERE 1 = 0"
        )
        con.execute(
            """
            CREATE TABLE lex_rule_thresholds (
                threshold_id VARCHAR,
                fact_id VARCHAR,
                metric VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO lex_normative_facts VALUES
            ('low1', 'body', 'requires', 'permit', 'Low confidence permit rule', 0.80, 'obligation', 'requires',
             'obligation', '[{"metric":"permit_rate"}]', 'quote', 'normative_fact', 'exact_quote', 'canonicalized',
             'resolved', 'structured_legal_unit', '', 'UA', 'transport', '2024-01-01', '', 'Low law', 'L-1',
             'стаття 1', 0.42, 'grounded')
            """
        )
        con.execute(
            """
            INSERT INTO lex_high_confidence_norms VALUES
            ('high1', 'body', 'requires', 'permit', 'High confidence permit rule', 0.95, 'obligation', 'requires',
             'obligation', '[{"metric":"permit_rate"}]', 'quote', 'normative_fact', 'exact_quote', 'canonicalized',
             'resolved', 'structured_legal_unit', '', 'UA', 'transport', '2024-01-01', '', 'High law', 'H-1',
             'стаття 2', 0.91, 'high_confidence_norm')
            """
        )
        con.execute("INSERT INTO lex_rule_thresholds VALUES ('t-low', 'low1', 'permit_rate')")
        con.execute("INSERT INTO lex_rule_thresholds VALUES ('t-high', 'high1', 'permit_rate')")

    store = LegalKnowledgeStore(db_path=db_path, index_dir=tmp_path)
    try:
        filtered = store.find_constraints(
            domain="transport",
            jurisdiction="UA",
            min_fused_confidence=0.85,
            quality_band="high_confidence_norm",
        )
        assert [fact.fact_id for fact in filtered] == ["high1"]

        thresholds = store.search_facts_with_threshold(
            "permit_rate",
            domain="transport",
            min_fused_confidence=0.85,
            quality_band="high_confidence_norm",
        )
        assert [fact.fact_id for fact in thresholds] == ["high1"]
        assert thresholds[0].quality_band == "high_confidence_norm"
        assert thresholds[0].fused_confidence == pytest.approx(0.91)
    finally:
        store.close()


def test_legal_knowledge_store_hides_temporal_unknown_rows_for_as_of(tmp_path) -> None:
    db_path = tmp_path / "lex_temporal_graph.duckdb"
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            """
            CREATE TABLE lex_normative_facts (
                fact_id VARCHAR,
                subject_en VARCHAR,
                predicate VARCHAR,
                object_en VARCHAR,
                fact_text VARCHAR,
                confidence REAL,
                norm_type VARCHAR,
                action_canon VARCHAR,
                norm_type_canon VARCHAR,
                thresholds_json VARCHAR,
                source_quote_uk VARCHAR,
                trust_tier VARCHAR,
                grounding_status VARCHAR,
                canonical_status VARCHAR,
                reference_resolution_status VARCHAR,
                structure_quality VARCHAR,
                constraint_type_canon VARCHAR,
                jurisdiction VARCHAR,
                top_domain VARCHAR,
                effective_from VARCHAR,
                effective_to VARCHAR,
                temporal_state VARCHAR,
                temporal_resolution_status VARCHAR,
                temporal_source_scope VARCHAR,
                temporal_source_kind VARCHAR,
                temporal_confidence REAL,
                temporal_provenance_json VARCHAR,
                doc_name VARCHAR,
                doc_reestr_code VARCHAR,
                provision_anchor VARCHAR,
                provision_citation VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO lex_normative_facts VALUES
            ('resolved1', 'body', 'requires', 'permit', 'Resolved rule', 0.9, 'obligation', 'requires',
             'obligation', '[]', 'quote', 'normative_fact', 'exact_quote', 'canonicalized', 'resolved',
             'structured_legal_unit', '', 'UA', 'transport', '2024-01-01', '', 'current', 'resolved',
             'document', 'doc_temporal_inheritance', 0.9, '{}', 'Resolved law', 'R-1', 'art:1', 'стаття 1'),
            ('unknown1', 'body', 'requires', 'permit', 'Unknown temporal rule', 0.9, 'obligation', 'requires',
             'obligation', '[]', 'quote', 'normative_fact', 'exact_quote', 'canonicalized', 'resolved',
             'structured_legal_unit', '', 'UA', 'transport', '', '', 'current', 'unknown',
             'document', 'status_semantics', 0.5, '{}', 'Unknown law', 'U-1', 'art:2', 'стаття 2')
            """
        )
        con.execute(
            "CREATE TABLE lex_rule_thresholds (threshold_id VARCHAR, fact_id VARCHAR, metric VARCHAR)"
        )

    store = LegalKnowledgeStore(db_path=db_path, index_dir=tmp_path)
    try:
        norms = store.get_applicable_norms(
            domain="transport", jurisdiction="UA", as_of="2024-02-01"
        )
        assert [fact.fact_id for fact in norms] == ["resolved1"]
        assert norms[0].temporal_resolution_status == "resolved"
    finally:
        store.close()
