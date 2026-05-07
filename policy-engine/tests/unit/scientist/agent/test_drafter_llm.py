"""Tests for polisyos.scientist.agent._drafter_llm — LLM resolution and cost estimation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from polisyos.scientist.agent._drafter_llm import _DrafterLLMMixin
from polisyos.scientist.agent.drafter_models import MultiPassConfig
from polisyos.scientist.orchestration.llm import TracedLLMClient

# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


class _LLMHarness(_DrafterLLMMixin):
    def __init__(self, *, config=None, inner=None, llm=None):
        self._config = config or MultiPassConfig()
        self._inner = inner or MagicMock()
        self._llm = llm


@pytest.fixture
def harness():
    return _LLMHarness()


# ---------------------------------------------------------------------------
# _resolve_llm
# ---------------------------------------------------------------------------


class TestResolveLLM:
    def test_explicit_client_returned(self):
        h = _LLMHarness()
        explicit = MagicMock()
        result = h._resolve_llm(explicit, h._inner)
        assert result is not None

    def test_none_client_falls_back_to_inner(self):
        inner = MagicMock()
        inner._llm = MagicMock()
        h = _LLMHarness(inner=inner)
        result = h._resolve_llm(None, inner)
        assert result is not None

    def test_both_none_returns_none(self):
        inner = MagicMock(spec=[])  # no _llm attribute
        h = _LLMHarness(inner=inner)
        result = h._resolve_llm(None, inner)
        assert result is None


# ---------------------------------------------------------------------------
# _normalize_critique_llm
# ---------------------------------------------------------------------------


class TestNormalizeCritiqueLLM:
    def test_no_critique_model_returns_llm(self):
        h = _LLMHarness(config=MultiPassConfig(critique_model=None))
        llm = MagicMock()
        assert h._normalize_critique_llm(llm) is llm

    def test_with_critique_model_wraps_in_traced(self):
        h = _LLMHarness(config=MultiPassConfig(critique_model="claude-3-haiku"))
        raw = MagicMock()
        result = h._normalize_critique_llm(raw)
        assert isinstance(result, TracedLLMClient)

    def test_traced_client_unwrapped_and_rewrapped(self):
        h = _LLMHarness(config=MultiPassConfig(critique_model="claude-3-haiku"))
        inner_raw = MagicMock()
        traced = TracedLLMClient(inner_raw, model_name="original")
        result = h._normalize_critique_llm(traced)
        assert isinstance(result, TracedLLMClient)


# ---------------------------------------------------------------------------
# _estimate_cost
# ---------------------------------------------------------------------------


class TestEstimateCost:
    def test_delegates_to_core(self, harness):
        with patch(
            "polisyos.scientist.agent._drafter_llm.estimate_cost", return_value=0.05
        ) as mock:
            cost = harness._estimate_cost(
                model="claude-3-sonnet",
                prompt_tokens=100,
                completion_tokens=50,
                raw_response="hello",
            )
            assert cost == 0.05
            mock.assert_called_once_with(
                model="claude-3-sonnet",
                prompt_tokens=100,
                completion_tokens=50,
                response_text="hello",
            )


class TestEstimateCostFromText:
    def test_zero_tokens(self, harness):
        with patch("polisyos.scientist.agent._drafter_llm.estimate_cost", return_value=0.01):
            cost = harness._estimate_cost_from_text("response", model="m")
            assert cost == 0.01


# ---------------------------------------------------------------------------
# _inner_model_name / _critique_model_name
# ---------------------------------------------------------------------------


class TestInnerModelName:
    def test_from_inner_llm(self):
        inner = MagicMock()
        inner._llm = MagicMock()
        inner._llm._model_name = "claude-3-opus"
        h = _LLMHarness(inner=inner)
        assert h._inner_model_name() == "claude-3-opus"

    def test_no_inner_llm(self):
        inner = MagicMock(spec=[])
        h = _LLMHarness(inner=inner)
        assert h._inner_model_name() == "default"


class TestCritiqueModelName:
    def test_config_critique_model(self):
        h = _LLMHarness(config=MultiPassConfig(critique_model="haiku"))
        assert h._critique_model_name() == "haiku"

    def test_from_llm_attribute(self):
        llm = MagicMock()
        llm._model_name = "sonnet"
        h = _LLMHarness(config=MultiPassConfig(critique_model=None), llm=llm)
        assert h._critique_model_name() == "sonnet"

    def test_no_llm_default(self):
        h = _LLMHarness(config=MultiPassConfig(critique_model=None), llm=None)
        assert h._critique_model_name() == "default"
