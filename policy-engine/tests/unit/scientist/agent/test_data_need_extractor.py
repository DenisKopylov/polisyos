from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("jax")

from polisyos.scientist.agent.data_need_extractor import LLMDataNeedExtractorAgent
from polisyos.scientist.agent.protocols import ProblemFrame


def _run(coro):
    return asyncio.run(coro)


def _problem_frame() -> ProblemFrame:
    return ProblemFrame(
        frame_id="frame-1",
        domain="economic",
        problem_statement="Improve employment outcomes in 2024",
        goals=("Increase employment",),
        constraints=("Budget neutral",),
        success_criteria={},
        assumptions=(),
        context={},
    )


def test_extract_data_needs_json_parse_assertion_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeLLM:
        async def generate(self, **kwargs):
            del kwargs
            return SimpleNamespace(content='{"data_needs": []}')

    def _boom(payload):
        del payload
        raise AssertionError("json parser invariant failed")

    monkeypatch.setattr(
        "polisyos.scientist.agent.data_need_extractor.extract_llm_json_object",
        _boom,
    )

    agent = LLMDataNeedExtractorAgent(_FakeLLM())

    with pytest.raises(AssertionError, match="json parser invariant failed"):
        _run(agent.extract_data_needs(_problem_frame()))


def test_catalog_lookup_assertion_is_not_swallowed() -> None:
    class _FakeLLM:
        async def generate(self, **kwargs):
            del kwargs
            return SimpleNamespace(
                content=(
                    '{"data_needs": [{"metric": "us.macro.gdp_nominal", "quality_min": 0.65}]}'
                )
            )

    class _BrokenCatalog:
        def find_by_polisyos_metric(self, metric, *, top_k):
            del metric, top_k
            raise AssertionError("catalog contract invariant failed")

    agent = LLMDataNeedExtractorAgent(
        _FakeLLM(),
        dataset_catalog=_BrokenCatalog(),
    )

    with pytest.raises(AssertionError, match="catalog contract invariant failed"):
        _run(agent.extract_data_needs(_problem_frame()))


def test_extract_data_needs_parse_error_raises_when_fallback_disallowed() -> None:
    class _FakeLLM:
        async def generate(self, **kwargs):
            del kwargs
            return SimpleNamespace(content="not json")

    agent = LLMDataNeedExtractorAgent(_FakeLLM(), allow_fallback=False)

    with pytest.raises(ValueError, match="llm_data_need_extraction_failed"):
        _run(agent.extract_data_needs(_problem_frame()))


def test_extract_data_needs_parses_think_prefixed_json() -> None:
    class _FakeLLM:
        async def generate(self, **kwargs):
            del kwargs
            return SimpleNamespace(
                content=(
                    '<think>data-need reasoning</think>{"data_needs":['
                    '{"metric":"tertiary_enrollment","quality_min":0.7}]}'
                )
            )

    needs = _run(
        LLMDataNeedExtractorAgent(_FakeLLM(), allow_fallback=False).extract_data_needs(
            _problem_frame()
        )
    )

    assert [need.metric for need in needs] == ["tertiary_enrollment"]


def test_extract_data_needs_empty_result_raises_when_fallback_disallowed() -> None:
    class _FakeLLM:
        async def generate(self, **kwargs):
            del kwargs
            return SimpleNamespace(content='{"data_needs": []}')

    agent = LLMDataNeedExtractorAgent(_FakeLLM(), allow_fallback=False)

    with pytest.raises(ValueError, match="llm_data_need_extraction_returned_no_usable_needs"):
        _run(agent.extract_data_needs(_problem_frame()))


def test_extract_data_needs_missing_llm_raises_when_fallback_disallowed() -> None:
    agent = LLMDataNeedExtractorAgent(None, allow_fallback=False)

    with pytest.raises(RuntimeError, match="data_need_extractor_llm_unavailable"):
        _run(agent.extract_data_needs(_problem_frame()))
