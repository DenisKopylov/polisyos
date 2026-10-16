from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb
import pytest

from polisyos.data_forge.domains.legal.source_relation import (
    LegalSourceRelationVerificationMissingError,
)
from polisyos.lex.legal_evaluation.transport_constraints import (
    LegalConstraintBridge,
)

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


def test_candidate_legal_rows_cannot_be_promoted_to_transport_authority(tmp_path: Path) -> None:
    db_path = tmp_path / "candidate_legal_kg.duckdb"
    _prepare_lex_db(db_path)

    with pytest.raises(LegalSourceRelationVerificationMissingError) as refusal:
        LegalConstraintBridge(db_path=db_path).get_constraints_for_policy(
            jurisdiction="UA",
            policy_domain="tax_policy",
            policy_spec={"retroactive": True},
        )

    assert refusal.value.refusal.to_payload() == {
        "code": "legal_source_relation_verification_not_established",
        "status": "verification_missing",
    }


def test_absent_legal_rows_do_not_mean_transport_is_legally_allowed(tmp_path: Path) -> None:
    missing_db = tmp_path / "missing_legal_kg.duckdb"

    with pytest.raises(LegalSourceRelationVerificationMissingError) as refusal:
        LegalConstraintBridge(db_path=missing_db).get_constraints_for_policy(
            jurisdiction="UA",
            policy_domain="tax_policy",
            policy_spec={},
        )

    assert refusal.value.refusal.status == "verification_missing"
