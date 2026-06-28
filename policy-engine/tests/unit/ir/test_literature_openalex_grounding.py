"""Tests for OpenAlex span-grounded literature extraction and accuracy."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from polisyos.ir.analytics.literature import (
    ClaimSpanGoldSet,
    EvidenceSpan,
    OpenAlexWorkText,
    evaluate_openalex_claim_extractor_accuracy,
    extract_span_grounded_claims_from_openalex_work,
    validate_causal_claim_span_grounding,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "scholar" / "openalex"
GOLD_PATH = REPO_ROOT / "architecture" / "policy_design_case" / (
    "layer3_gy_openalex_claim_span_gold.json"
)


class _DeterministicSpanSupportClient:
    async def generate(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        temperature: float | None = None,
        seed: int | None = None,
    ) -> SimpleNamespace:
        del messages, tools, temperature, seed
        return SimpleNamespace(
            content="",
            tool_calls=[
                SimpleNamespace(
                    id="call-span-support",
                    name="layer3_gy_record_span_support_judgment",
                    arguments={
                        "decision": "entails",
                        "confidence": 0.91,
                        "rationale": "deterministic test support",
                    },
                )
            ],
            usage=SimpleNamespace(total_tokens=5),
            raw={"deterministic_replay_key": "test-only"},
        )


def _fixture_work(fixture_name: str, openalex_id: str) -> OpenAlexWorkText:
    payload = json.loads((FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"))
    work_payload = next(row for row in payload["results"] if row["id"] == openalex_id)
    return OpenAlexWorkText.from_openalex_work(work_payload)


def test_span_grounding_requires_resolving_supporting_source_text() -> None:
    client = _DeterministicSpanSupportClient()
    work = _fixture_work(
        "minimum_wage_employment.json",
        "https://openalex.org/W2942870997",
    )
    claims = extract_span_grounded_claims_from_openalex_work(
        work,
        query="minimum wage employment effect",
        span_support_client=client,
    )
    assert claims

    positive = validate_causal_claim_span_grounding(
        work,
        claims[0],
        span_support_client=client,
    )
    assert positive.status == "validated_supporting"
    assert positive.authority_tier == "design_tier_l2"

    poisoned_claim = claims[0].model_copy(
        update={
            "supporting_spans": [
                EvidenceSpan(
                    span_id="fake-span",
                    text="This asserted span is not present in the OpenAlex abstract.",
                    source_ref=work.openalex_id,
                    start_char=0,
                    end_char=64,
                )
            ],
            "supporting_span_ids": ["fake-span"],
        }
    )

    rejected = validate_causal_claim_span_grounding(
        work,
        poisoned_claim,
        span_support_client=client,
    )
    assert rejected.status == "rejected_unresolved_span"
    assert rejected.authority_tier == "candidate_unverified"

    title_span = work.title
    non_supporting_claim = claims[0].model_copy(
        update={
            "claim_id": f"{claims[0].claim_id}.non_supporting_title",
            "claim_text": "Minimum wages substantially increase low-wage employment.",
            "cause_variable": "minimum wages",
            "effect_variable": "low-wage employment",
            "supporting_spans": [
                EvidenceSpan(
                    span_id="title-present",
                    text=title_span,
                    source_ref=work.openalex_id,
                    start_char=0,
                    end_char=len(title_span),
                    content_sha256=work.content_sha256,
                )
            ],
            "supporting_span_ids": ["title-present"],
        }
    )

    non_supporting = validate_causal_claim_span_grounding(
        work,
        non_supporting_claim,
        span_support_client=client,
    )
    assert non_supporting.status == "rejected_non_supporting"
    assert non_supporting.authority_tier == "candidate_unverified"


def test_extractor_accuracy_is_measured_against_governed_gold_and_degrades() -> None:
    gold = ClaimSpanGoldSet.model_validate_json(GOLD_PATH.read_text(encoding="utf-8"))
    client = _DeterministicSpanSupportClient()

    report = evaluate_openalex_claim_extractor_accuracy(
        gold,
        span_support_client=client,
    )
    degraded = evaluate_openalex_claim_extractor_accuracy(
        gold,
        extractor=lambda work, query: [],
    )

    assert report.gold_record_count >= 4
    assert report.precision > degraded.precision
    assert report.recall > degraded.recall
    assert report.measurement_basis == "human_labeled_gold_set"
    assert degraded.recall == 0.0
