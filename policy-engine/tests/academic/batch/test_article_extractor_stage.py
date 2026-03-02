from __future__ import annotations

import asyncio
import json

from polisyos.academic.batch.article_extractor import run_article_extract
from polisyos.academic.batch.config import AcademicBatchConfig


class _FakeGonkaClient:
    def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
        pass

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __aexit__(self, *exc):  # type: ignore[no-untyped-def]
        return None

    async def chat(self, *, model, temperature, prompt):  # type: ignore[no-untyped-def]
        if '"relevant"' in prompt or "screening" in prompt.lower():
            return {"relevant": True, "reason": "policy causal"}, {"prompt_tokens": 10, "completion_tokens": 2}

        return (
            {
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
                        "cause_variable": "gdp growth",
                        "effect_variable": "employment",
                        "direction": "positive",
                        "evidence_strength": "observational",
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
                "methodology": "did",
                "sample_size": 1000,
                "citation_summary": "demo",
                "extraction_confidence": 0.8,
            },
            {"prompt_tokens": 100, "completion_tokens": 50, "total_cost_usd": 0.01},
        )


def test_run_article_extract_stage_writes_outputs(monkeypatch, tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.gonka_api_key = "fake"

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

    monkeypatch.setattr("polisyos.academic.batch.article_extractor.GonkaChatClient", _FakeGonkaClient)

    async def _fake_fetch_full_text(self, work):  # type: ignore[no-untyped-def]
        return "Policy increases employment by 0.2", "fulltext_html"

    monkeypatch.setattr(
        "polisyos.academic.batch.article_extractor.PolicyArticleExtractor._fetch_full_text",
        _fake_fetch_full_text,
    )

    metrics = asyncio.run(run_article_extract(config))

    assert int(metrics["records"]) == 1
    assert int(metrics["extracted"]) == 1
    assert config.article_extraction_results_path.exists()

    output_path = config.extracted_dir / "article_extract.jsonl"
    assert output_path.exists()
    record = output_path.read_text(encoding="utf-8").strip()
    assert '"extraction_mode":"article_extract"' in record
