from polisyos.data_forge.domains.academic.batch.llm_extractor import (
    EXTRACTION_PROMPT,
    parse_llm_result,
    serialize_llm_claim_occurrence_vocabulary,
)
from polisyos.ir.analytics.literature import DesignFamily, EvidenceStrength
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


def test_llm_prompt_and_parser_use_independent_claim_vocabulary_axes() -> None:
    assert '"strength"' not in EXTRACTION_PROMPT
    assert '"design_family_hint"' in EXTRACTION_PROMPT
    assert '"evidence_strength"' in EXTRACTION_PROMPT
    estimates, claims, _ = parse_llm_result(
        {
            "causal_claims": [{
                "cause": "tax rate",
                "effect": "employment",
                "direction": "negative",
                "mechanism": "labour cost",
                "design_family_hint": "ols",
                "evidence_strength": "rct",
            }]
        }
    )
    assert not estimates
    assert len(claims) == 1
    assert claims[0].vocabulary.design_family_hint.value == "ols"
    assert claims[0].vocabulary.evidence_strength.value == "rct"


def test_llm_prompt_names_every_member_of_each_independent_vocabulary() -> None:
    for member in DesignFamily:
        assert member.value in EXTRACTION_PROMPT
    for member in EvidenceStrength:
        assert member.value in EXTRACTION_PROMPT
