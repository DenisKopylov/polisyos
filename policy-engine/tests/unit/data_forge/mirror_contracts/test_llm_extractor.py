import asyncio
import json
from typing import Any
from unittest.mock import create_autospec

import pytest

from polisyos.data_forge.domains.academic.batch.llm_extractor import (
    AcademicLLMClient,
    extract_with_llm,
    parse_llm_result,
    serialize_llm_claim_occurrence_vocabulary,
)
from polisyos.ir.analytics.literature import DesignFamily, EvidenceStrength
from tests._helpers.mirror_contracts import assert_source_stem_has_static_contract


def _extract_with_stub(abstract: str) -> tuple[str, dict[str, Any]]:
    """Capture the actual model-facing request without constructing a network client."""
    response = {
        "causal_claims": [{
            "cause": "tax rate",
            "effect": "employment",
            "direction": "negative",
            "mechanism": "labour cost",
            "design_family_hint": "ols",
            "evidence_strength": "rct",
        }]
    }
    client = create_autospec(AcademicLLMClient, instance=True)
    client.chat_completion.return_value = {"content": json.dumps(response)}
    result = asyncio.run(extract_with_llm(
        abstract=abstract,
        topic="unused-topic-must-not-appear",
        work_id="synthetic:prompt-regression",
        client=client,
    ))
    client.chat_completion.assert_awaited_once()
    (message,) = client.chat_completion.call_args.kwargs["messages"]
    assert message["role"] == "user"
    assert result == response
    return message["content"], result


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
    prompt, result = _extract_with_stub("Tax rates reduce employment.")
    assert '"strength"' not in prompt
    assert '"design_family_hint"' in prompt
    assert '"evidence_strength"' in prompt
    estimates, claims, _ = parse_llm_result(result)
    assert not estimates
    assert len(claims) == 1
    assert claims[0].vocabulary.design_family_hint.value == "ols"
    assert claims[0].vocabulary.evidence_strength.value == "rct"
    assert claims[0].vocabulary.evidence_strength_status.value == "candidate"


def test_llm_prompt_names_every_member_of_each_independent_vocabulary() -> None:
    prompt, _ = _extract_with_stub("Tax rates reduce employment.")
    for member in DesignFamily:
        assert member.value in prompt
    for member in EvidenceStrength:
        assert member.value in prompt


@pytest.mark.parametrize(
    "abstract",
    [
        "Tax rates reduce employment.",
        'Input contains {abstract}, {topic}, $abstract, {{nested}} and {"value": 3}.',
        "A" * 4100,
    ],
    ids=["plain", "literal-placeholders", "truncated"],
)
def test_llm_request_renders_single_json_braces_and_literal_abstract(abstract: str) -> None:
    """A renderable prompt must preserve the JSON scaffold and insert input only once."""
    prompt, _ = _extract_with_stub(abstract)
    instructions, separator, rendered_abstract = prompt.partition("\nAbstract:\n")
    assert separator == "\nAbstract:\n"
    assert rendered_abstract == abstract[:4000] + "\n"
    assert "unused-topic-must-not-appear" not in instructions
    assert "{abstract}" not in instructions
    assert "{{" not in instructions
    assert "}}" not in instructions
    assert 'fields:\n{\n  "estimates": [\n    {\n' in instructions
    assert '"causal_claims": [\n    {\n' in instructions
    assert '"boundary_conditions": [\n    {\n' in instructions
    assert instructions.endswith("    }\n  ]\n}\n")
