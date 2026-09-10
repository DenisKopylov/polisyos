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
GOLD_PATH = (
    REPO_ROOT / "architecture" / "policy_design_case" / ("layer3_gy_openalex_claim_span_gold.json")
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


def test_extractor_accuracy_is_withheld_while_actual_extraction_changes() -> None:
    gold = ClaimSpanGoldSet.model_validate_json(GOLD_PATH.read_text(encoding="utf-8"))
    report = evaluate_openalex_claim_extractor_accuracy(gold)
    degraded = evaluate_openalex_claim_extractor_accuracy(gold, extractor=lambda work, query: [])
    assert report != degraded
    assert report.precision is None and report.recall is None
    assert report.accuracy_status == "withheld_pending_adjudicator_appointment"
    assert report.measurement_basis == "extractor_execution_and_constructed_negatives"
    assert {row.case_id for row in report.observations} == {
        row.case_id for row in degraded.observations
    }
    assert any(row.predictions for row in report.observations)
    assert all(not row.predictions for row in degraded.observations)


def test_gold_instrument_preserves_capture_and_review_time_roles() -> None:
    gold = ClaimSpanGoldSet.model_validate_json(GOLD_PATH.read_text())
    report = evaluate_openalex_claim_extractor_accuracy(gold)
    expected = {}
    for record in gold.records:
        payload = json.loads((REPO_ROOT / record.source_fixture).read_text())
        expected[(record.openalex_id, record.query)] = payload["_recording"]["captured_at"]
    assert {(row.openalex_id, row.query) for row in report.observations} == set(expected)
    assert all(
        row.recorded_at == expected[(row.openalex_id, row.query)] for row in report.observations
    )
    assert all(
        row.gold_reviewed_at == gold.provenance["reviewed_at"] for row in report.observations
    )


def test_recorded_source_loader_binds_the_exact_single_read(monkeypatch) -> None:
    import hashlib

    from polisyos.ir.analytics import literature

    path = FIXTURE_DIR / "credit_guarantee_firm_survival.json"
    raw = path.read_bytes()
    reads = []
    original = Path.read_bytes

    def read_once(selected):
        if selected == path:
            reads.append(selected)
            assert len(reads) == 1
            return raw
        return original(selected)

    monkeypatch.setattr(Path, "read_bytes", read_once)
    source = literature.load_recorded_openalex_source(path)
    assert reads == [path]
    assert source.payload == json.loads(raw)
    assert source.content_sha256 == "sha256:" + hashlib.sha256(raw).hexdigest()
    assert source.captured_at == source.payload["_recording"]["captured_at"]
    assert source.query == source.payload["_recording"]["query"]


def test_extractor_instrument_observes_actual_default_extractor(monkeypatch) -> None:
    from polisyos.ir.analytics import literature

    gold = ClaimSpanGoldSet.model_validate_json(GOLD_PATH.read_text())
    original = literature.extract_span_grounded_claims_from_openalex_work
    calls = []

    def tracked(work, *, query, **kwargs):
        calls.append((work.openalex_id, query))
        return original(work, query=query, **kwargs)

    monkeypatch.setattr(literature, "extract_span_grounded_claims_from_openalex_work", tracked)
    baseline = literature.evaluate_openalex_claim_extractor_accuracy(
        gold,
        span_support_client=_DeterministicSpanSupportClient(),
    )
    assert calls, "default accuracy instrument never called the actual extractor"
    monkeypatch.setattr(
        literature, "extract_span_grounded_claims_from_openalex_work", lambda *args, **kwargs: []
    )
    removed = literature.evaluate_openalex_claim_extractor_accuracy(
        gold,
        span_support_client=_DeterministicSpanSupportClient(),
    )
    assert baseline != removed
    assert baseline.precision is None and baseline.recall is None
    assert baseline.accuracy_status == "withheld_pending_adjudicator_appointment"
    assert all(row.predictions == [] for row in removed.observations)


def test_extractor_instrument_retains_fabricated_predictions_as_refused() -> None:
    from polisyos.ir.analytics import literature

    gold = ClaimSpanGoldSet.model_validate_json(GOLD_PATH.read_text())

    def fabricated(work, query):
        claims = literature.extract_span_grounded_claims_from_openalex_work(
            work,
            query=query,
            span_support_client=_DeterministicSpanSupportClient(),
        )
        return [
            claim.model_copy(
                update={
                    "claim_text": "Constructed content absent from the selected source.",
                    "supporting_spans": [
                        span.model_copy(update={"text": "Absent constructed supporting text."})
                        for span in claim.supporting_spans
                    ],
                }
            )
            for claim in claims
        ]

    report = literature.evaluate_openalex_claim_extractor_accuracy(gold, extractor=fabricated)
    predictions = [prediction for row in report.observations for prediction in row.predictions]
    assert predictions
    assert all(row["source_binding"]["status"] == "refused" for row in predictions)
    assert report.precision is None and report.recall is None


def test_source_bound_candidate_rejects_mutation_of_any_emitted_claim_leaf() -> None:
    import copy

    from polisyos.ir.analytics import literature

    work = _fixture_work("credit_guarantee_firm_survival.json", "https://openalex.org/W2169693233")
    query = "loan guarantees SMEs firm survival impact evaluation"
    claim = literature.extract_span_grounded_claims_from_openalex_work(
        work, query=query, span_support_client=_DeterministicSpanSupportClient()
    )[0]
    assert (
        literature.validate_openalex_source_bound_candidate(work, claim, query=query).status
        == "source_bound_candidate"
    )

    def leaves(value, path=()):
        if isinstance(value, dict):
            for key, child in value.items():
                yield from leaves(child, (*path, key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from leaves(child, (*path, index))
        else:
            yield path, value

    original = claim.model_dump(mode="json")
    checked = []
    for path, value in leaves(original):
        mutated = copy.deepcopy(original)
        target = mutated
        for key in path[:-1]:
            target = target[key]
        replacement = (
            "constructed mutation"
            if value is None
            else (
                not value
                if isinstance(value, bool)
                else value + 1
                if isinstance(value, (int, float))
                else str(value) + " constructed mutation"
            )
        )
        target[path[-1]] = replacement
        try:
            candidate = literature.CausalClaim.model_validate(mutated)
        except ValueError:
            checked.append((path, "typed_refusal"))
            continue
        result = literature.validate_openalex_source_bound_candidate(work, candidate, query=query)
        assert result.status == "refused", path
        checked.append((path, result.status))
    assert {path for path, _ in checked} == {path for path, _ in leaves(original)}


def test_extractor_instrument_keeps_unreadable_source_explicit() -> None:
    from polisyos.ir.analytics import literature

    case = literature.OpenAlexExtractionCase(
        case_id="unreadable-selected-source",
        openalex_id="https://openalex.org/W1",
        query="recorded query",
        source_ref="absent-selected-source",
        recorded_at="2026-09-08",
        work=None,
        source_error="selected_source_not_available",
    )
    report = literature.evaluate_openalex_claim_extractor_accuracy(cases=[case])
    assert len(report.observations) == 1
    assert report.observations[0].disposition == "source_unavailable"
    assert report.observations[0].reason == "selected_source_not_available"
    assert report.precision is None and report.recall is None


def test_legacy_gold_accuracy_predecessor_refuses_unappointed_numeric_claim() -> None:
    import pytest

    from polisyos.ir.analytics import literature

    gold = ClaimSpanGoldSet.model_validate_json(GOLD_PATH.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="adjudicator_appointment_missing"):
        literature._evaluate_gold_span_support_accuracy(
            gold, span_support_client=_DeterministicSpanSupportClient()
        )


def test_default_extraction_keeps_candidates_without_entailment_authority(monkeypatch) -> None:
    from polisyos.ir.analytics import literature

    def unappointed(*args, **kwargs):
        raise AssertionError("default candidate extraction attempted semantic authority")

    monkeypatch.setattr(literature, "validate_causal_claim_span_grounding", unappointed)
    work = _fixture_work("credit_guarantee_firm_survival.json", "https://openalex.org/W2169693233")
    query = "loan guarantees SMEs firm survival impact evaluation"
    claims = literature.extract_span_grounded_claims_from_openalex_work(work, query=query)
    assert claims and all(claim.publish_to_graph is False for claim in claims)
    assert all(
        literature.validate_openalex_source_bound_candidate(work, claim, query=query).authority_tier
        == "candidate_unverified"
        for claim in claims
    )
