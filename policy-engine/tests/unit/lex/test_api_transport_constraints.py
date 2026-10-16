from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb
import pytest

from polisyos.data_forge.domains.legal.source_relation import (
    LegalSourceRelationVerificationMissingError,
)
from polisyos.lex.api import evaluate_transport_constraints

if TYPE_CHECKING:
    from pathlib import Path


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
                'fact_api_1',
                'Tax law forbids retroactive tax increase.',
                '',
                '',
                'doc_api_1',
                'Tax Code',
                'UA-TAX',
                'Art. 58'
            )
            """
        )
        con.execute("INSERT INTO lex_doc_domains VALUES ('doc_api_1', 'tax_policy')")
        con.execute("CHECKPOINT")
    finally:
        con.close()


def test_evaluate_transport_constraints_refuses_unverified_legal_candidate(tmp_path: Path) -> None:
    db_path = tmp_path / "lex_api.duckdb"
    _prepare_lex_db(db_path)

    with pytest.raises(LegalSourceRelationVerificationMissingError) as refusal:
        evaluate_transport_constraints(
            jurisdiction="UA",
            policy_domain="tax_policy",
            policy_spec={"retroactive": True},
            legal_kg_db_path=db_path,
        )

    assert refusal.value.refusal.code == "legal_source_relation_verification_not_established"


def test_evaluate_transport_constraints_does_not_treat_missing_graph_as_no_restriction(
    tmp_path: Path,
) -> None:
    missing_db = tmp_path / "missing_lex_kg.duckdb"

    with pytest.raises(LegalSourceRelationVerificationMissingError) as refusal:
        evaluate_transport_constraints(
            jurisdiction="UA",
            policy_domain="tax_policy",
            policy_spec={},
            legal_kg_db_path=missing_db,
        )

    assert refusal.value.refusal.status == "verification_missing"
