from polisyos.data_forge.domains.academic.batch.llm_extractor import (
    serialize_llm_claim_occurrence_vocabulary,
)
from tests._helpers.mirror_contracts import assert_source_stem_has_static_contract


def test_llm_extractor_source_modules_have_static_contracts() -> None:
    assert_source_stem_has_static_contract('data_forge', 'llm_extractor')


def test_future_llm_claim_serializer_keeps_named_candidate_axes_separate() -> None:
    """Catch an LLM serializer that maps a generic label or loses raw metadata."""

    transport = serialize_llm_claim_occurrence_vocabulary(
        {
            "cause": "tax rate",
            "effect": "employment",
            "direction": "negative",
            "mechanism": "labour cost",
            "design_family_hint": "ols",
            "evidence_strength": "rct",
            "claim_extraction_confidence": 0.23,
            "claim_type": "causal_claim",
            "raw_llm_detail": {"model": "candidate"},
        }
    )

    assert transport.occurrence == {
        "cause": "tax rate",
        "effect": "employment",
        "direction": "negative",
        "mechanism": "labour cost",
        "claim_type": "causal_claim",
        "raw_llm_detail": {"model": "candidate"},
    }
    assert transport.vocabulary.design_family_hint.value == "ols"
    assert transport.vocabulary.evidence_strength.value == "rct"
    assert transport.vocabulary.claim_extraction_confidence == 0.23
    assert transport.vocabulary.source_basis.value == "abstract_only"
