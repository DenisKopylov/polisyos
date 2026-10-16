from __future__ import annotations

from importlib import import_module

import pytest

import polisyos.lex as lex
from polisyos.data_forge.read_api import legal


def test_legal_read_api_exports_canonical_source_relation_contracts() -> None:
    canonical = import_module("polisyos.data_forge.domains.legal.source_relation")

    assert set(canonical.__all__).issubset(legal.__all__)
    for name in canonical.__all__:
        assert getattr(legal, name) is getattr(canonical, name)

    assert lex.LegalSourceRelationRefusal is legal.LegalSourceRelationRefusal
    assert (
        lex.LegalSourceRelationVerificationMissingError
        is legal.LegalSourceRelationVerificationMissingError
    )


def test_legal_read_api_preserves_candidate_disposition_and_refuses_authority() -> None:
    disposition = legal.current_legal_source_relation_disposition()

    assert disposition is legal.CURRENT_LEGAL_SOURCE_RELATION_DISPOSITION
    assert disposition.trust_tier == "search_candidate"
    assert disposition.refusal == legal.LEGAL_SOURCE_RELATION_REFUSAL
    assert disposition.refusal.status == "verification_missing"

    with pytest.raises(legal.LegalSourceRelationVerificationMissingError) as caught:
        legal.require_legal_source_relation_verification()

    assert caught.value.refusal is legal.LEGAL_SOURCE_RELATION_REFUSAL
    assert caught.value.refusal.to_payload() == {
        "code": "legal_source_relation_verification_not_established",
        "status": "verification_missing",
    }
