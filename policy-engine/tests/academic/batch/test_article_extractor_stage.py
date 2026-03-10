from __future__ import annotations

import asyncio
import json

from polisyos.academic.batch.article_extractor import run_article_extract
from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.batch.fulltext_resolver import FullTextFetchResult
from polisyos.academic.batch.resolve_extract import ProviderResponse, WorkItem, _eligibility_gate
from polisyos.ir.analytics.literature import TextQuality


class _BaseFakePool:
    def __init__(self, config):  # type: ignore[no-untyped-def]
        self._config = config

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __aexit__(self, *exc):  # type: ignore[no-untyped-def]
        return None


class _FakePool(_BaseFakePool):
    async def chat_json(self, *, model, prompt, temperature):  # type: ignore[no-untyped-def]
        return ProviderResponse(
            parsed={
                "paper_relevance": True,
                "paper_relevance_reason": "policy causal",
                "empirical_parameters": [
                    {
                        "name": "gdp growth",
                        "value": 0.2,
                        "parameter_type": "quantitative",
                        "evidence_strength": "observational",
                        "geographic_scope": "OECD",
                    }
                ],
                "causal_claims": [
                    {
                        "claim_type": "causal_claim",
                        "cause_variable": "gdp growth",
                        "effect_variable": "employment",
                        "direction": "positive",
                        "evidence_strength": "observational",
                        "supporting_span_ids": ["r_01"],
                        "method_span_ids": ["m_01"],
                    }
                ],
                "boundary_conditions": [
                    {
                        "variable": "income_level",
                        "condition_type": "categorical",
                        "required_value": "high",
                        "consequence_if_violated": "external validity drop",
                    }
                ],
                "mechanisms": [],
                "methodology_summary": "did",
                "sample_size": 1000,
                "citation_summary": "demo",
                "extraction_confidence": 0.8,
            },
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_cost_usd": 0.01},
            http_status=200,
            finish_reason="stop",
            latency_ms=10.0,
            retry_count=0,
            limiter_wait_ms=0.0,
            backoff_sleep_ms=0.0,
            parse_status="ok",
            error_class="",
            raw_content="{}",
            truncated_output=False,
        )


class _CoercingFakePool(_BaseFakePool):
    async def chat_json(self, *, model, prompt, temperature):  # type: ignore[no-untyped-def]
        return ProviderResponse(
            parsed={
                "paper_relevance": True,
                "paper_relevance_reason": "policy causal",
                "empirical_parameters": [
                    {
                        "parameter": "tax progressivity",
                        "value": "0.35",
                        "parameter_type": "quantitative",
                        "evidence_strength": "observational",
                        "context": "OECD panel",
                    },
                    {
                        "variable": "redistribution salience",
                        "value": "high",
                        "source": "qualitative synthesis",
                    },
                    "drop this string item",
                ],
                "causal_claims": [
                    {
                        "claim_type": "causal_claim",
                        "cause": "tax progressivity",
                        "effect": "income inequality",
                        "direction": "decrease",
                        "effect_size": "low",
                        "supporting_span_ids": ["r_01"],
                        "method_span_ids": ["m_01"],
                        "counterevidence_notes": "redistribution channel",
                    }
                ],
                "boundary_conditions": [
                    {
                        "variable": "income_level",
                        "operator": ">=",
                        "threshold_value": "upper_middle",
                        "scope_text": "more reliable in richer countries",
                    }
                ],
                "mechanisms": [{"description": "Transfers smooth household shocks"}],
                "methodology_summary": "did",
                "sample_size": "G7 countries (7 countries)",
                "citation_summary": "demo",
                "extraction_confidence": "high",
            },
            usage={"prompt_tokens": 120, "completion_tokens": 55, "total_cost_usd": 0.01},
            http_status=200,
            finish_reason="stop",
            latency_ms=11.0,
            retry_count=0,
            limiter_wait_ms=0.0,
            backoff_sleep_ms=0.0,
            parse_status="ok",
            error_class="",
            raw_content="{}",
            truncated_output=False,
        )


class _PartialFailureFakePool(_BaseFakePool):
    async def chat_json(self, *, model, prompt, temperature):  # type: ignore[no-untyped-def]
        return ProviderResponse(
            parsed={
                "paper_relevance": True,
                "paper_relevance_reason": "policy causal",
                "empirical_parameters": [
                    "institutional quality",
                    {"parameter": "fiscal multiplier", "value": "1.2"},
                ],
                "causal_claims": [
                    {
                        "claim_type": "causal_claim",
                        "cause_variable": "government spending",
                        "effect_variable": "output",
                        "direction": "positive",
                        "supporting_span_ids": ["r_01"],
                        "method_span_ids": ["m_01"],
                    }
                ],
                "mechanisms": [],
                "boundary_conditions": [],
                "methodology_summary": "iv",
                "sample_size": {"n": 240},
                "citation_summary": "demo",
                "extraction_confidence": 0.72,
            },
            usage={"prompt_tokens": 90, "completion_tokens": 40, "total_cost_usd": 0.01},
            http_status=200,
            finish_reason="stop",
            latency_ms=9.0,
            retry_count=0,
            limiter_wait_ms=0.0,
            backoff_sleep_ms=0.0,
            parse_status="ok",
            error_class="",
            raw_content="{}",
            truncated_output=False,
        )


class _TrackBContextFakePool(_BaseFakePool):
    async def chat_json(self, *, model, prompt, temperature):  # type: ignore[no-untyped-def]
        if "You are classifying an academic paper for extraction routing." in prompt:
            parsed = {
                "paper_kind": "context_characterization",
                "confidence": 0.96,
                "reason": "systematic institutional comparison",
            }
        elif "Extract context attributes from this evidence bundle." in prompt:
            parsed = {
                "context_attributes": [
                    {
                        "attribute_name": "institutional_quality",
                        "canonical_name": "governance.institutional_quality",
                        "value": 0.81,
                        "unit": "index",
                        "country_codes": ["SE"],
                        "time_period": "2000-2010",
                        "measurement_method": "comparative governance index",
                        "confidence": 0.9,
                    }
                ],
                "cross_context_comparisons": [],
                "temporal_trends": [],
            }
        else:
            parsed = {
                "paper_relevance": True,
                "paper_relevance_reason": "context characterization for policy transportability",
                "empirical_parameters": [],
                "causal_claims": [],
                "boundary_conditions": [],
                "mechanisms": [],
                "methodology_summary": "systematic review",
                "sample_size": None,
                "citation_summary": "Institutional quality differs across OECD democracies",
                "extraction_confidence": 0.81,
            }
        return ProviderResponse(
            parsed=parsed,
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_cost_usd": 0.01},
            http_status=200,
            finish_reason="stop",
            latency_ms=10.0,
            retry_count=0,
            limiter_wait_ms=0.0,
            backoff_sleep_ms=0.0,
            parse_status="ok",
            error_class="",
            raw_content="{}",
            truncated_output=False,
        )


class _TrackBFallbackClassificationFakePool(_BaseFakePool):
    async def chat_json(self, *, model, prompt, temperature):  # type: ignore[no-untyped-def]
        if "You are classifying an academic paper for extraction routing." in prompt:
            parsed = {
                "paper_kind": "empirical_causal",
                "confidence": 0.72,
                "reason": "mentions policy effects",
            }
        elif "Extract context attributes from this evidence bundle." in prompt:
            parsed = {
                "context_attributes": [
                    {
                        "attribute_name": "institutional_quality",
                        "canonical_name": "governance.institutional_quality",
                        "value": 0.77,
                        "unit": "index",
                        "country_codes": ["US"],
                        "time_period": "2015-2020",
                        "measurement_method": "governance index",
                        "confidence": 0.88,
                    }
                ],
                "cross_context_comparisons": [],
                "temporal_trends": [],
            }
        else:
            parsed = {
                "paper_relevance": True,
                "paper_relevance_reason": "policy perspective on cross-country debt exposure",
                "empirical_parameters": [],
                "causal_claims": [],
                "boundary_conditions": [],
                "mechanisms": [],
                "methodology_summary": "policy perspective review",
                "sample_size": 68,
                "citation_summary": "Cross-country policy perspective on sovereign debt risk",
                "extraction_confidence": 0.83,
            }
        return ProviderResponse(
            parsed=parsed,
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_cost_usd": 0.01},
            http_status=200,
            finish_reason="stop",
            latency_ms=10.0,
            retry_count=0,
            limiter_wait_ms=0.0,
            backoff_sleep_ms=0.0,
            parse_status="ok",
            error_class="",
            raw_content="{}",
            truncated_output=False,
        )


class _CanonicalModerationFakePool(_BaseFakePool):
    async def chat_json(self, *, model, prompt, temperature):  # type: ignore[no-untyped-def]
        if "You are classifying an academic paper for extraction routing." in prompt:
            parsed = {
                "paper_kind": "empirical_causal",
                "confidence": 0.95,
                "reason": "panel heterogeneity study",
            }
        elif "Extract moderation and heterogeneity findings from this evidence bundle." in prompt:
            parsed = {
                "moderator_findings": [
                    {
                        "base_cause": "GDP growth",
                        "base_effect": "Employment",
                        "moderator": "Income Level",
                        "direction_of_moderation": "amplifying",
                        "confidence": 0.9,
                        "evidence_text": "The effect is stronger in high-income settings.",
                    }
                ],
                "heterogeneity_mechanisms": [],
            }
        else:
            parsed = {
                "paper_relevance": True,
                "paper_relevance_reason": "empirical heterogeneity study",
                "empirical_parameters": [],
                "causal_claims": [
                    {
                        "claim_type": "causal_claim",
                        "cause_variable": "GDP growth",
                        "effect_variable": "Employment",
                        "direction": "positive",
                        "evidence_strength": "observational",
                        "supporting_span_ids": ["r_01"],
                        "method_span_ids": ["m_01"],
                    }
                ],
                "boundary_conditions": [],
                "mechanisms": [],
                "heterogeneity_results": [
                    {
                        "moderator": "Income Level",
                        "finding": "effect stronger in high-income settings",
                        "confidence": 0.85,
                    }
                ],
                "methodology_summary": "panel fe",
                "sample_size": 100,
                "citation_summary": "heterogeneity study",
                "extraction_confidence": 0.9,
            }
        return ProviderResponse(
            parsed=parsed,
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_cost_usd": 0.01},
            http_status=200,
            finish_reason="stop",
            latency_ms=10.0,
            retry_count=0,
            limiter_wait_ms=0.0,
            backoff_sleep_ms=0.0,
            parse_status="ok",
            error_class="",
            raw_content="{}",
            truncated_output=False,
        )


async def _fake_fetch_full_text(work, **kwargs):  # type: ignore[no-untyped-def]
    return FullTextFetchResult(
        text="We use a difference-in-differences design. Policy increases employment by 0.2.",
        source_kind="fulltext_html",
        source_url="https://example.org/paper",
        fetch_error_class="",
    )


async def _fake_fetch_full_text_result_only(work, **kwargs):  # type: ignore[no-untyped-def]
    return FullTextFetchResult(
        text="Our results show the reform increased tax compliance by 12 percent across municipalities.",
        source_kind="fulltext_html",
        source_url="https://example.org/result-only",
        fetch_error_class="",
    )


async def _fake_fetch_full_text_field_experiment(work, **kwargs):  # type: ignore[no-untyped-def]
    return FullTextFetchResult(
        text=(
            "Using administrative data from employers and tax records, we document how hiring outcomes "
            "change after the reform and provide evidence that callback rates increase."
        ),
        source_kind="fulltext_html",
        source_url="https://example.org/field-experiment",
        fetch_error_class="",
    )


async def _fake_fetch_full_text_login_shell(work, **kwargs):  # type: ignore[no-untyped-def]
    return FullTextFetchResult(
        text=(
            "Choice Reviews | Login Institutional Login Reviews Most Recent Reviews "
            "URL has changed to a different location. Please update your bookmarks."
        ),
        source_kind="fulltext_html",
        source_url="http://choicereviews.org/login",
        fetch_error_class="",
    )


async def _fake_fetch_full_text_context_review(work, **kwargs):  # type: ignore[no-untyped-def]
    return FullTextFetchResult(
        text=(
            "This systematic review documents institutional quality across OECD democracies and compares "
            "governance indicators over time."
        ),
        source_kind="fulltext_html",
        source_url="https://example.org/context-review",
        fetch_error_class="",
    )


class _FailIfCalledPool(_BaseFakePool):
    async def chat_json(self, *, model, prompt, temperature):  # type: ignore[no-untyped-def]
        raise AssertionError("LLM should not be called for rejected review-like papers")


def test_run_article_extract_stage_writes_outputs(monkeypatch, tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.gonka_api_key = "fake"
    config.gonka_api_keys = ["fake"]

    row = {
        "work_id": "https://openalex.org/W1",
        "topic_ids": ["T1"],
        "topic_display_names": ["Economic policy"],
        "work": {
            "id": "https://openalex.org/W1",
            "title": "Effects of Policy",
            "publication_year": 2023,
            "cited_by_count": 50,
            "topics": [{"display_name": "Economic policy"}],
            "abstract_inverted_index": {"policy": [0], "effect": [1], "employment": [2]},
            "authorships": [{"institutions": [{"country_code": "US"}]}],
            "open_access": {"is_oa": False},
        },
    }

    config.selected_global_works_path.parent.mkdir(parents=True, exist_ok=True)
    config.selected_global_works_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    monkeypatch.setattr("polisyos.academic.batch.resolve_extract.GonkaMultiKeyPool", _FakePool)
    monkeypatch.setattr("polisyos.academic.batch.resolve_extract.fetch_full_text_result_for_work", _fake_fetch_full_text)

    metrics = asyncio.run(run_article_extract(config))

    assert int(metrics["records"]) == 1
    assert int(metrics["successful_llm_extractions_per_topic"]) == 1
    assert config.article_extraction_results_path.exists()

    output_path = config.extracted_dir / "resolve_extract.jsonl"
    assert output_path.exists()
    record = output_path.read_text(encoding="utf-8").strip()
    assert '"extraction_mode":"resolve_extract"' in record
    payload = json.loads(config.article_extraction_results_path.read_text(encoding="utf-8").strip())
    assert payload["source_basis"] == "fulltext"
    assert payload["text_quality"] == "extracted_fulltext"
    assert payload["causal_claims"][0]["supporting_spans"]
    assert payload["causal_claims"][0]["supporting_span_ids"] == ["r_01"]


def test_run_article_extract_stage_coerces_relaxed_payloads(monkeypatch, tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.gonka_api_key = "fake"
    config.gonka_api_keys = ["fake"]

    row = {
        "work_id": "https://openalex.org/W2",
        "topic_ids": ["T1"],
        "topic_display_names": ["Fiscal policy"],
        "work": {
            "id": "https://openalex.org/W2",
            "title": "Tax Policy Effects",
            "publication_year": 2021,
            "cited_by_count": 80,
            "topics": [{"display_name": "Fiscal policy and economic growth"}],
            "abstract_inverted_index": {"tax": [0], "policy": [1], "effects": [2]},
            "authorships": [{"institutions": [{"country_code": "US"}]}],
            "open_access": {"is_oa": False},
        },
    }

    config.selected_global_works_path.parent.mkdir(parents=True, exist_ok=True)
    config.selected_global_works_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    monkeypatch.setattr("polisyos.academic.batch.resolve_extract.GonkaMultiKeyPool", _CoercingFakePool)
    monkeypatch.setattr("polisyos.academic.batch.resolve_extract.fetch_full_text_result_for_work", _fake_fetch_full_text)

    metrics = asyncio.run(run_article_extract(config))

    assert int(metrics["successful_llm_extractions_per_topic"]) == 1
    payload = json.loads(config.article_extraction_results_path.read_text(encoding="utf-8").strip())
    assert payload["sample_size"] == 7
    assert payload["extraction_confidence"] == 0.85
    assert len(payload["empirical_parameters"]) == 2
    assert payload["empirical_parameters"][0]["name"] == "tax_progressivity"
    assert payload["empirical_parameters"][0]["display_name"] == "tax progressivity"
    assert payload["empirical_parameters"][1]["value_qualitative"] == "high"
    assert payload["causal_claims"][0]["effect_size"] is None
    assert payload["causal_claims"][0]["magnitude_qualitative"] == "low"
    assert payload["causal_claims"][0]["design_family_hint"] == "unclear"
    assert payload["causal_claims"][0]["supporting_spans"]


def test_run_article_extract_stage_drops_bad_items_without_losing_document(monkeypatch, tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.gonka_api_key = "fake"
    config.gonka_api_keys = ["fake"]

    row = {
        "work_id": "https://openalex.org/W3",
        "topic_ids": ["T1"],
        "topic_display_names": ["Fiscal policy"],
        "work": {
            "id": "https://openalex.org/W3",
            "title": "Spending Effects",
            "publication_year": 2020,
            "cited_by_count": 60,
            "topics": [{"display_name": "Fiscal policy and economic growth"}],
            "abstract_inverted_index": {"government": [0], "spending": [1], "output": [2]},
            "authorships": [{"institutions": [{"country_code": "US"}]}],
            "open_access": {"is_oa": False},
        },
    }

    config.selected_global_works_path.parent.mkdir(parents=True, exist_ok=True)
    config.selected_global_works_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    monkeypatch.setattr("polisyos.academic.batch.resolve_extract.GonkaMultiKeyPool", _PartialFailureFakePool)
    monkeypatch.setattr("polisyos.academic.batch.resolve_extract.fetch_full_text_result_for_work", _fake_fetch_full_text)

    metrics = asyncio.run(run_article_extract(config))

    assert int(metrics["successful_llm_extractions_per_topic"]) == 1
    assert int(metrics["extraction_errors"]) == 0
    payload = json.loads(config.article_extraction_results_path.read_text(encoding="utf-8").strip())
    assert len(payload["empirical_parameters"]) == 1
    assert payload["empirical_parameters"][0]["name"] == "fiscal_multiplier"
    assert payload["empirical_parameters"][0]["display_name"] == "fiscal multiplier"
    assert payload["sample_size"] == 240
    assert len(payload["causal_claims"]) == 1
    assert payload["causal_claims"][0]["supporting_spans"]


def test_run_article_extract_stage_allows_result_only_empirical_signal(monkeypatch, tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.gonka_api_key = "fake"
    config.gonka_api_keys = ["fake"]

    row = {
        "work_id": "https://openalex.org/W4",
        "topic_ids": ["T1"],
        "topic_display_names": ["Tax policy"],
        "work": {
            "id": "https://openalex.org/W4",
            "title": "Tax Reform and Compliance",
            "publication_year": 2022,
            "cited_by_count": 40,
            "topics": [{"display_name": "Taxation and Compliance Studies"}],
            "abstract_inverted_index": {"tax": [0], "reform": [1], "compliance": [2]},
            "authorships": [{"institutions": [{"country_code": "US"}]}],
            "open_access": {"is_oa": False},
        },
    }

    config.selected_global_works_path.parent.mkdir(parents=True, exist_ok=True)
    config.selected_global_works_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    monkeypatch.setattr("polisyos.academic.batch.resolve_extract.GonkaMultiKeyPool", _FakePool)
    monkeypatch.setattr("polisyos.academic.batch.resolve_extract.fetch_full_text_result_for_work", _fake_fetch_full_text_result_only)

    metrics = asyncio.run(run_article_extract(config))

    assert int(metrics["successful_llm_extractions_per_topic"]) == 1
    assert config.article_extraction_results_path.exists()


def test_eligibility_gate_allows_track_b_context_salvage() -> None:
    item = WorkItem(
        row={},
        work={
            "id": "https://openalex.org/WCTX",
            "title": "Systematic Review of Institutional Quality Across OECD Democracies",
            "abstract_inverted_index": {
                "systematic": [0],
                "review": [1],
                "institutional": [2],
                "quality": [3],
            },
        },
        work_id="https://openalex.org/WCTX",
        topic_id="T1",
        topic_ids=["T1"],
        topic_display_names=["Institutional analysis"],
        prefetch_priority=0.0,
        selected_rank=1,
    )
    text = (
        "This systematic review documents institutional quality across OECD democracies "
        "and compares governance indicators over time."
    )

    without_track_b = _eligibility_gate(
        item,
        text=text,
        source_kind="fulltext_html",
        text_quality=TextQuality.EXTRACTED_FULLTEXT.value,
        track_b_enabled=False,
    )
    with_track_b = _eligibility_gate(
        item,
        text=text,
        source_kind="fulltext_html",
        text_quality=TextQuality.EXTRACTED_FULLTEXT.value,
        track_b_enabled=True,
    )

    assert without_track_b.llm_eligible is False
    assert without_track_b.context_eligible is False
    assert without_track_b.rejection_reasons == ["review_like", "missing_empirical_cues"]
    assert with_track_b.llm_eligible is False
    assert with_track_b.context_eligible is True
    assert with_track_b.rejection_reasons == ["review_like", "missing_empirical_cues"]


def test_run_article_extract_stage_rejects_review_like_before_llm(monkeypatch, tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.gonka_api_key = "fake"
    config.gonka_api_keys = ["fake"]

    row = {
        "work_id": "https://openalex.org/W5",
        "topic_ids": ["T1"],
        "topic_display_names": ["Tax policy"],
        "work": {
            "id": "https://openalex.org/W5",
            "title": "Systematic Review of Tax Compliance Research",
            "publication_year": 2021,
            "cited_by_count": 25,
            "topics": [{"display_name": "Taxation and Compliance Studies"}],
            "abstract_inverted_index": {"systematic": [0], "review": [1], "tax": [2], "compliance": [3]},
            "authorships": [{"institutions": [{"country_code": "US"}]}],
            "open_access": {"is_oa": False},
        },
    }

    config.selected_global_works_path.parent.mkdir(parents=True, exist_ok=True)
    config.selected_global_works_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    monkeypatch.setattr("polisyos.academic.batch.resolve_extract.GonkaMultiKeyPool", _FailIfCalledPool)
    monkeypatch.setattr("polisyos.academic.batch.resolve_extract.fetch_full_text_result_for_work", _fake_fetch_full_text)

    metrics = asyncio.run(run_article_extract(config))

    assert int(metrics["successful_llm_extractions_per_topic"]) == 0
    assert int(metrics["rejected"]) == 1
    assert not config.article_extraction_results_path.exists()


def test_run_article_extract_stage_routes_context_review_when_track_b_enabled(monkeypatch, tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.gonka_api_key = "fake"
    config.gonka_api_keys = ["fake"]
    config.track_b_enabled = True

    row = {
        "work_id": "https://openalex.org/W5B",
        "topic_ids": ["T1"],
        "topic_display_names": ["Institutional analysis"],
        "work": {
            "id": "https://openalex.org/W5B",
            "title": "Systematic Review of Institutional Quality Across OECD Democracies",
            "publication_year": 2021,
            "cited_by_count": 25,
            "topics": [{"display_name": "Institutional analysis"}],
            "abstract_inverted_index": {
                "systematic": [0],
                "review": [1],
                "institutional": [2],
                "quality": [3],
                "oecd": [4],
            },
            "authorships": [{"institutions": [{"country_code": "SE"}]}],
            "open_access": {"is_oa": False},
        },
    }

    config.selected_global_works_path.parent.mkdir(parents=True, exist_ok=True)
    config.selected_global_works_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    monkeypatch.setattr("polisyos.academic.batch.resolve_extract.GonkaMultiKeyPool", _TrackBContextFakePool)
    monkeypatch.setattr(
        "polisyos.academic.batch.resolve_extract.fetch_full_text_result_for_work",
        _fake_fetch_full_text_context_review,
    )

    metrics = asyncio.run(run_article_extract(config))

    assert int(metrics["successful_llm_extractions_per_topic"]) == 1
    assert int(metrics["context_eligible"]) == 1
    assert int(metrics["papers_classified"]) == 1
    assert int(metrics["track_b_routed"]) == 1
    assert int(metrics["track_b_only_routed"]) == 1
    assert int(metrics["context_attributes_extracted"]) == 1
    assert config.context_attributes_path.exists()

    context_row = json.loads(config.context_attributes_path.read_text(encoding="utf-8").strip())
    assert context_row["canonical_name"] == "governance.institutional_quality"
    assert context_row["openalex_id"] == "https://openalex.org/W5B"


def test_run_article_extract_stage_overrides_empirical_classification_for_context_track_b(monkeypatch, tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.gonka_api_key = "fake"
    config.gonka_api_keys = ["fake"]
    config.track_b_enabled = True

    row = {
        "work_id": "https://openalex.org/WCTX2",
        "topic_ids": ["T1"],
        "topic_display_names": ["Institutional analysis"],
        "work": {
            "id": "https://openalex.org/WCTX2",
            "title": "Examining the debt implications of the Belt and Road Initiative from a policy perspective",
            "publication_year": 2019,
            "cited_by_count": 50,
            "topics": [{"display_name": "Institutional analysis"}],
            "abstract_inverted_index": {
                "debt": [0],
                "implications": [1],
                "policy": [2],
                "perspective": [3],
                "countries": [4],
            },
            "authorships": [{"institutions": [{"country_code": "US"}]}],
            "open_access": {"is_oa": False},
        },
    }

    config.selected_global_works_path.parent.mkdir(parents=True, exist_ok=True)
    config.selected_global_works_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        "polisyos.academic.batch.resolve_extract.GonkaMultiKeyPool",
        _TrackBFallbackClassificationFakePool,
    )
    monkeypatch.setattr(
        "polisyos.academic.batch.resolve_extract.fetch_full_text_result_for_work",
        _fake_fetch_full_text_context_review,
    )

    metrics = asyncio.run(run_article_extract(config))

    assert int(metrics["track_b_routed"]) == 1
    assert int(metrics["context_attributes_extracted"]) == 1
    payload = json.loads(config.article_extraction_results_path.read_text(encoding="utf-8").strip())
    assert payload["paper_kind"] == "context_characterization"
    assert payload["context_attributes"][0]["canonical_name"] == "governance.institutional_quality"


def test_run_article_extract_stage_canonizes_moderation_edges(monkeypatch, tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.gonka_api_key = "fake"
    config.gonka_api_keys = ["fake"]
    config.track_c_enabled = True

    row = {
        "work_id": "https://openalex.org/WMOD1",
        "topic_ids": ["T1"],
        "topic_display_names": ["Fiscal policy"],
        "work": {
            "id": "https://openalex.org/WMOD1",
            "title": "Tax Policy Effects",
            "publication_year": 2021,
            "cited_by_count": 80,
            "topics": [{"display_name": "Fiscal policy"}],
            "abstract_inverted_index": {"gdp": [0], "growth": [1], "employment": [2]},
            "authorships": [{"institutions": [{"country_code": "US"}]}],
            "open_access": {"is_oa": False},
        },
    }

    config.selected_global_works_path.parent.mkdir(parents=True, exist_ok=True)
    config.selected_global_works_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    monkeypatch.setattr("polisyos.academic.batch.resolve_extract.GonkaMultiKeyPool", _CanonicalModerationFakePool)
    monkeypatch.setattr("polisyos.academic.batch.resolve_extract.fetch_full_text_result_for_work", _fake_fetch_full_text)

    asyncio.run(run_article_extract(config))

    payload = json.loads(config.article_extraction_results_path.read_text(encoding="utf-8").strip())
    assert payload["causal_claims"][0]["cause_variable"] == "gdp_growth"
    assert payload["causal_claims"][0]["effect_variable"] == "employment"
    assert payload["heterogeneity_results"][0]["moderator"] == "income_level"
    assert payload["moderation_edges"][0]["base_cause"] == "gdp_growth"
    assert payload["moderation_edges"][0]["base_effect"] == "employment"
    assert payload["moderation_edges"][0]["moderator"] == "income_level"


def test_run_article_extract_stage_allows_field_experiment_and_admin_data_signal(monkeypatch, tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.gonka_api_key = "fake"
    config.gonka_api_keys = ["fake"]

    row = {
        "work_id": "https://openalex.org/W6",
        "topic_ids": ["T1"],
        "topic_display_names": ["Discrimination research"],
        "work": {
            "id": "https://openalex.org/W6",
            "title": "Hiring Discrimination: Evidence from a Field Experiment",
            "publication_year": 2021,
            "cited_by_count": 35,
            "topics": [{"display_name": "Names, Identity, and Discrimination Research"}],
            "abstract_inverted_index": {
                "administrative": [0],
                "data": [1],
                "callbacks": [2],
                "labor": [3],
                "market": [4],
            },
            "authorships": [{"institutions": [{"country_code": "US"}]}],
            "open_access": {"is_oa": False},
        },
    }

    config.selected_global_works_path.parent.mkdir(parents=True, exist_ok=True)
    config.selected_global_works_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    monkeypatch.setattr("polisyos.academic.batch.resolve_extract.GonkaMultiKeyPool", _FakePool)
    monkeypatch.setattr("polisyos.academic.batch.resolve_extract.fetch_full_text_result_for_work", _fake_fetch_full_text_field_experiment)

    metrics = asyncio.run(run_article_extract(config))

    assert int(metrics["successful_llm_extractions_per_topic"]) == 1
    assert config.article_extraction_results_path.exists()


def test_run_article_extract_stage_rejects_login_shell_before_llm(monkeypatch, tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.gonka_api_key = "fake"
    config.gonka_api_keys = ["fake"]

    row = {
        "work_id": "https://openalex.org/W7",
        "topic_ids": ["T1"],
        "topic_display_names": ["Discrimination research"],
        "work": {
            "id": "https://openalex.org/W7",
            "title": "Obesity, Attractiveness, and Differential Treatment in Hiring: A Field Experiment",
            "publication_year": 2009,
            "cited_by_count": 215,
            "topics": [{"display_name": "Names, Identity, and Discrimination Research"}],
            "abstract_inverted_index": {
                "field": [0],
                "experiment": [1],
                "hiring": [2],
                "discrimination": [3],
            },
            "authorships": [{"institutions": [{"country_code": "SE"}]}],
            "open_access": {"is_oa": False},
        },
    }

    config.selected_global_works_path.parent.mkdir(parents=True, exist_ok=True)
    config.selected_global_works_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    monkeypatch.setattr("polisyos.academic.batch.resolve_extract.GonkaMultiKeyPool", _FailIfCalledPool)
    monkeypatch.setattr("polisyos.academic.batch.resolve_extract.fetch_full_text_result_for_work", _fake_fetch_full_text_login_shell)

    metrics = asyncio.run(run_article_extract(config))

    assert int(metrics["successful_llm_extractions_per_topic"]) == 0
    assert int(metrics["rejected"]) == 1
    assert not config.article_extraction_results_path.exists()
