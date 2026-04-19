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
        "polisyos.scientist.agent.data_need_extractor.json.loads",
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
                    '{"data_needs": [{"metric": "us.macro.gdp_nominal", '
                    '"quality_min": 0.65}]}'
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
