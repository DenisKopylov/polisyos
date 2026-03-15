from __future__ import annotations

from pathlib import Path

import duckdb

from polisyos.lex.legal_evaluation.transport_constraints import (
    ConstraintSeverity,
    LegalConstraintBridge,
    LegalToDAGMappingType,
    is_transport_blocked,
)


def _prepare_lex_db(db_path: Path) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE lex_facts (
                fact_id VARCHAR,
                fact_text VARCHAR,
                condition_text_uk VARCHAR,
                procedure_text_uk VARCHAR,
                doc_id VARCHAR,
                doc_name VARCHAR,
                doc_reestr_code VARCHAR,
                provision_citation VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE TABLE lex_doc_domains (
                doc_id VARCHAR,
                domain VARCHAR
            )
            """
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
            INSERT INTO lex_facts VALUES (
                'fact_1',
                'Tax code prohibits retroactive tax changes.',
                '',
                'A transition period is recommended for tax policy updates.',
                'doc_1',
                'Tax Code',
                'UA-TAX',
                'Art. 58'
            )
            """
        )
        con.execute("INSERT INTO lex_doc_domains VALUES ('doc_1', 'tax_policy')")
        con.execute("CHECKPOINT")
    finally:
        con.close()


def test_get_constraints_for_policy_marks_retroactive_as_hard(tmp_path: Path) -> None:
    db_path = tmp_path / "lex_kg.duckdb"
    _prepare_lex_db(db_path)
    bridge = LegalConstraintBridge(db_path=db_path)

    result = bridge.get_constraints_for_policy(
        jurisdiction="UA",
        policy_domain="tax_policy",
        policy_spec={"retroactive": True},
    )

    assert result.hard_constraints
    assert result.hard_constraints[0].severity == ConstraintSeverity.HARD


def test_get_constraints_for_policy_marks_short_transition_as_soft(tmp_path: Path) -> None:
    db_path = tmp_path / "lex_kg.duckdb"
    _prepare_lex_db(db_path)
    bridge = LegalConstraintBridge(db_path=db_path)

    result = bridge.get_constraints_for_policy(
        jurisdiction="UA",
        policy_domain="tax_policy",
        policy_spec={"transition_period": "3mo"},
    )

    assert result.soft_constraints
    assert result.soft_constraints[0].severity == ConstraintSeverity.SOFT
    assert result.soft_constraints[0].quantitative_impact == "transition_period >= 6 months"


def test_golden_retroactive_constraint_maps_to_mechanism_node(tmp_path: Path) -> None:
    db_path = tmp_path / "lex_kg.duckdb"
    _prepare_lex_db(db_path)
    bridge = LegalConstraintBridge(db_path=db_path)

    result = bridge.get_constraints_for_policy(
        jurisdiction="UA",
        policy_domain="tax_policy",
        policy_spec={"retroactive": True},
    )

    assert result.legal_dag_mappings
    mapping = result.legal_dag_mappings[0]
    assert mapping.mapping_type == LegalToDAGMappingType.MECHANISM_NODE
    assert mapping.requires_expert_review is True


def test_hard_constraints_represent_blocking_signal(tmp_path: Path) -> None:
    db_path = tmp_path / "lex_kg.duckdb"
    _prepare_lex_db(db_path)
    bridge = LegalConstraintBridge(db_path=db_path)

    result = bridge.get_constraints_for_policy(
        jurisdiction="UA",
        policy_domain="tax_policy",
        policy_spec={"retroactive": True},
    )

    assert len(result.hard_constraints) > 0
    assert is_transport_blocked(result) is True


def test_no_hard_constraints_not_blocked(tmp_path: Path) -> None:
    db_path = tmp_path / "lex_kg.duckdb"
    _prepare_lex_db(db_path)
    bridge = LegalConstraintBridge(db_path=db_path)

    result = bridge.get_constraints_for_policy(
        jurisdiction="UA",
        policy_domain="tax_policy",
        policy_spec={"transition_period": "12mo"},
    )

    assert result.hard_constraints == []
    assert is_transport_blocked(result) is False


def test_domain_only_retrieval_still_uses_legal_provenance(tmp_path: Path) -> None:
    db_path = tmp_path / "lex_domain_only.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE lex_facts (
                fact_id VARCHAR,
                fact_text VARCHAR,
                condition_text_uk VARCHAR,
                procedure_text_uk VARCHAR,
                doc_id VARCHAR,
                doc_name VARCHAR,
                doc_reestr_code VARCHAR,
                provision_citation VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE TABLE lex_doc_domains (
                doc_id VARCHAR,
                domain VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO lex_facts VALUES (
                'fact_climate_1',
                'Sectoral rule with transport implications.',
                '',
                '',
                'doc_climate_1',
                'Climate Code',
                'UA-CLIMATE',
                'Art. 5'
            )
            """
        )
        con.execute("INSERT INTO lex_doc_domains VALUES ('doc_climate_1', 'climate_policy')")
        con.execute("CHECKPOINT")
    finally:
        con.close()

    bridge = LegalConstraintBridge(db_path=db_path)
    result = bridge.get_constraints_for_policy(
        jurisdiction="UA",
        policy_domain="climate_policy",
        policy_spec={"retroactive": True},
    )

    assert result.hard_constraints
    assert result.hard_constraints[0].legal_source == "Climate Code, Art. 5"
