from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb
import pytest

import polisyos.lex as lex
from polisyos.data_forge.domains.legal.source_relation import (
    LegalSourceRelationRefusal as CanonicalRefusal,
)
from polisyos.data_forge.domains.legal.source_relation import (
    LegalSourceRelationVerificationMissingError as CanonicalVerificationMissingError,
)

if TYPE_CHECKING:
    from polisyos.data_forge.domains.legal.source_relation import (
        LegalSourceRelationRefusal,
        LegalSourceRelationVerificationMissingError,
    )
    from polisyos.lex.api import evaluate_transport_constraints
    from polisyos.lex.legal_evaluation.transport_constraints import (
        ConstraintSeverity,
        LegalConstraint,
        LegalConstraintBridge,
        LegalConstraintSet,
        LegalToDAGMapping,
        LegalToDAGMappingType,
        is_transport_blocked,
    )
else:
    from polisyos.lex import (
        ConstraintSeverity,
        LegalConstraint,
        LegalConstraintBridge,
        LegalConstraintSet,
        LegalSourceRelationRefusal,
        LegalSourceRelationVerificationMissingError,
        LegalToDAGMapping,
        LegalToDAGMappingType,
        evaluate_transport_constraints,
        is_transport_blocked,
    )
from polisyos.lex.api import (
    evaluate_transport_constraints as canonical_evaluate_transport_constraints,
)
from polisyos.lex.legal_evaluation.transport_constraints import (
    ConstraintSeverity as CanonicalConstraintSeverity,
)
from polisyos.lex.legal_evaluation.transport_constraints import (
    LegalConstraint as CanonicalLegalConstraint,
)
from polisyos.lex.legal_evaluation.transport_constraints import (
    LegalConstraintBridge as CanonicalLegalConstraintBridge,
)
from polisyos.lex.legal_evaluation.transport_constraints import (
    LegalConstraintSet as CanonicalLegalConstraintSet,
)
from polisyos.lex.legal_evaluation.transport_constraints import (
    LegalToDAGMapping as CanonicalLegalToDAGMapping,
)
from polisyos.lex.legal_evaluation.transport_constraints import (
    LegalToDAGMappingType as CanonicalLegalToDAGMappingType,
)
from polisyos.lex.legal_evaluation.transport_constraints import (
    is_transport_blocked as canonical_is_transport_blocked,
)

if TYPE_CHECKING:
    from pathlib import Path


def _prepare_candidate_fact_db(db_path: Path) -> None:
    connection = duckdb.connect(str(db_path))
    try:
        connection.execute(
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
        connection.execute(
            """
            CREATE TABLE lex_doc_domains (
                doc_id VARCHAR,
                domain VARCHAR
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE lex_rule_thresholds (
                threshold_id VARCHAR,
                fact_id VARCHAR,
                metric VARCHAR
            )
            """
        )
        connection.execute(
            """
            INSERT INTO lex_facts VALUES (
                'candidate_transport_fact',
                'Candidate fact only: retroactive tax increase.',
                '', '', 'candidate_doc', 'Tax Code', 'UA-TAX', 'Art. 58'
            )
            """
        )
        connection.execute("INSERT INTO lex_doc_domains VALUES ('candidate_doc', 'tax_policy')")
        connection.execute("CHECKPOINT")
    finally:
        connection.close()


def test_root_facade_aliases_are_the_canonical_transport_objects() -> None:
    assert lex.__all__
    assert {
        "LegalConstraintBridge",
        "LegalConstraintSet",
        "is_transport_blocked",
        "evaluate_transport_constraints",
        "LegalSourceRelationRefusal",
        "LegalSourceRelationVerificationMissingError",
    }.issubset(lex.__all__)

    assert LegalConstraintBridge is CanonicalLegalConstraintBridge
    assert LegalConstraintSet is CanonicalLegalConstraintSet
    assert is_transport_blocked is canonical_is_transport_blocked
    assert evaluate_transport_constraints is canonical_evaluate_transport_constraints
    assert LegalSourceRelationRefusal is CanonicalRefusal
    assert LegalSourceRelationVerificationMissingError is CanonicalVerificationMissingError

    # Preserve the original four legal transport facade exports by identity.
    assert ConstraintSeverity is CanonicalConstraintSeverity
    assert LegalConstraint is CanonicalLegalConstraint
    assert LegalToDAGMapping is CanonicalLegalToDAGMapping
    assert LegalToDAGMappingType is CanonicalLegalToDAGMappingType


def _assert_root_transport_refusal(db_path: Path) -> None:
    with pytest.raises(LegalSourceRelationVerificationMissingError) as caught:
        evaluate_transport_constraints(
            jurisdiction="UA",
            policy_domain="tax_policy",
            policy_spec={"retroactive": True, "transport_permitted": True},
            legal_kg_db_path=db_path,
        )

    refusal = caught.value.refusal
    assert isinstance(refusal, LegalSourceRelationRefusal)
    assert refusal.code == "legal_source_relation_verification_not_established"
    assert refusal.status == "verification_missing"


def test_root_transport_evaluator_refuses_unverified_candidate_facts(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "candidate-legal.duckdb"
    _prepare_candidate_fact_db(db_path)
    assert db_path.is_file()

    _assert_root_transport_refusal(db_path)


def test_root_transport_evaluator_refuses_missing_legal_database(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "absent-legal.duckdb"
    assert not db_path.exists()

    _assert_root_transport_refusal(db_path)
