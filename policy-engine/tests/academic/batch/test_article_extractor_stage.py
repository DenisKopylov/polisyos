from __future__ import annotations

import asyncio
import json

from polisyos.academic.batch.article_extractor import run_article_extract
from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.batch.fulltext_resolver import FullTextFetchResult
from polisyos.academic.batch.resolve_extract import ProviderResponse


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
