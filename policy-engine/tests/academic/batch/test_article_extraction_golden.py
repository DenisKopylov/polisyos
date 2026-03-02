from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from polisyos.academic.batch.article_extractor import run_article_extract
from polisyos.academic.batch.config import AcademicBatchConfig


class _GoldenFakeGonkaClient:
    def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
        pass

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __aexit__(self, *exc):  # type: ignore[no-untyped-def]
        return None

    async def chat(self, *, model, temperature, prompt):  # type: ignore[no-untyped-def]
        if '"relevant"' in prompt or "screening" in prompt.lower():
            return {"relevant": True, "reason": "policy causal"}, {"prompt_tokens": 8, "completion_tokens": 2}
        return (
            {
                "empirical_parameters": [
                    {
                        "name": "gdp_growth",
                        "value": 0.21,
                        "parameter_type": "quantitative",
                        "evidence_strength": "observational",
                        "geographic_scope": "UA",
                    },
                    {
                        "name": "unemployment_rate",
                        "value": -0.12,
                        "parameter_type": "quantitative",
                        "evidence_strength": "observational",
                        "geographic_scope": "UA",
                    },
                ],
                "causal_claims": [
                    {
                        "cause_variable": "gdp_growth",
                        "effect_variable": "unemployment_rate",
                        "direction": "negative",
                        "evidence_strength": "observational",
                    },
                    {
                        "cause_variable": "government_spending",
                        "effect_variable": "poverty_rate",
                        "direction": "negative",
                        "evidence_strength": "observational",
                    },
                ],
                "boundary_conditions": [
                    {
                        "variable": "income_level",
                        "condition_type": "categorical",
                        "required_value": "lower_middle",
                        "consequence_if_violated": "external validity drop",
                    }
                ],
                "mechanisms": [],
                "methodology": "did",
                "sample_size": 1200,
                "citation_summary": "known fixture article",
                "extraction_confidence": 0.86,
            },
            {"prompt_tokens": 100, "completion_tokens": 50, "total_cost_usd": 0.01},
        )


def _load_fixture(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        loaded = json.load(fh)
    if not isinstance(loaded, dict):
        raise TypeError(f"Fixture payload must be an object: {path}")
    return loaded


def _project_result(payload: dict[str, Any]) -> dict[str, Any]:
    source_context = payload.get("source_context")
    return {
        "openalex_id": payload.get("openalex_id"),
        "doi": payload.get("doi"),
        "title": payload.get("title"),
        "year": payload.get("year"),
        "publication_year": payload.get("publication_year"),
        "methodology": payload.get("methodology"),
        "sample_size": payload.get("sample_size"),
        "extraction_confidence": payload.get("extraction_confidence"),
        "empirical_parameter_names": [
            str(item.get("name"))
            for item in payload.get("empirical_parameters", [])
            if isinstance(item, dict)
        ],
        "causal_claim_pairs": [
            [str(item.get("cause_variable")), str(item.get("effect_variable"))]
            for item in payload.get("causal_claims", [])
            if isinstance(item, dict)
        ],
        "boundary_variables": [
            str(item.get("variable"))
            for item in payload.get("boundary_conditions", [])
            if isinstance(item, dict)
        ],
        "source_context": {
            "context_id": (
                str(source_context.get("context_id"))
                if isinstance(source_context, dict)
                else ""
            ),
            "income_level": (
                str(source_context.get("income_level"))
                if isinstance(source_context, dict)
                else ""
            ),
        },
    }


def test_article_extraction_known_article_golden(monkeypatch, tmp_path: Path) -> None:
    fixtures_root = Path(__file__).resolve().parents[2] / "fixtures" / "phase0"
    input_payload = _load_fixture(fixtures_root / "known_article_input.json")
    expected = _load_fixture(fixtures_root / "known_article_expected_result.json")

    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.gonka_api_key = "fake"
    config.selected_global_works_path.parent.mkdir(parents=True, exist_ok=True)
    config.selected_global_works_path.write_text(
        json.dumps(input_payload, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "polisyos.academic.batch.article_extractor.GonkaChatClient",
        _GoldenFakeGonkaClient,
    )

    async def _fake_fetch_full_text(self, work):  # type: ignore[no-untyped-def]
        return "Known policy article full text for deterministic golden extraction.", "fulltext_html"

    monkeypatch.setattr(
        "polisyos.academic.batch.article_extractor.PolicyArticleExtractor._fetch_full_text",
        _fake_fetch_full_text,
    )

    metrics = asyncio.run(run_article_extract(config))
    assert int(metrics["extracted"]) == 1

    lines = config.article_extraction_results_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    result_payload = json.loads(lines[0])
    projected = _project_result(result_payload)

    assert projected == expected
