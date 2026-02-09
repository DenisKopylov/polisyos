"""LLM integration helpers for the multipass drafter.

These are mixed into ``MultiPassLLMDrafter`` via the
``_DrafterLLMMixin`` helper base class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.core.llm import estimate_cost, extract_llm_response_data
from polisyos.scientist.llm import TracedLLMClient

if TYPE_CHECKING:
    from polisyos.scientist.agent.protocols import DrafterAgent

    from .drafter_models import MultiPassConfig

__all__ = ["_DrafterLLMMixin"]


class _DrafterLLMMixin:
    """LLM resolution, cost estimation, and response extraction."""

    # -- Provided by the orchestrator at runtime --
    _config: MultiPassConfig
    _inner: DrafterAgent
    _llm: Any | None

    # ------------------------------------------------------------------
    # LLM resolution
    # ------------------------------------------------------------------

    def _resolve_llm(self, llm_client: Any | None, inner: DrafterAgent) -> Any | None:
        if llm_client is not None:
            return self._normalize_critique_llm(llm_client)
        inner_llm = getattr(inner, "_llm", None)
        if inner_llm is None:
            return None
        return self._normalize_critique_llm(inner_llm)

    def _normalize_critique_llm(self, llm: Any) -> Any:
        if self._config.critique_model is None:
            return llm
        model_name = self._config.critique_model
        if isinstance(llm, TracedLLMClient):
            raw_client = getattr(llm, "_client", llm)
            return TracedLLMClient(raw_client, model_name=model_name)
        return TracedLLMClient(llm, model_name=model_name)

    # ------------------------------------------------------------------
    # Cost estimation
    # ------------------------------------------------------------------

    def _estimate_cost(
        self,
        *,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        raw_response: str,
    ) -> float:
        return estimate_cost(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            response_text=raw_response,
        )

    def _estimate_cost_from_text(self, raw_response: str | None, *, model: str) -> float:
        return estimate_cost(
            model=model,
            prompt_tokens=0,
            completion_tokens=0,
            response_text=raw_response,
        )

    # ------------------------------------------------------------------
    # Response data extraction
    # ------------------------------------------------------------------

    def _extract_response_data(self, response: Any) -> tuple[str, int, int]:
        data = extract_llm_response_data(response)
        return data.content, data.prompt_tokens, data.completion_tokens

    # ------------------------------------------------------------------
    # Model name helpers
    # ------------------------------------------------------------------

    def _inner_model_name(self) -> str:
        if hasattr(self._inner, "_llm"):
            inner_llm = getattr(self._inner, "_llm")
            return str(getattr(inner_llm, "_model_name", "default"))
        return "default"

    def _critique_model_name(self) -> str:
        if self._config.critique_model:
            return self._config.critique_model
        if self._llm is None:
            return "default"
        return str(getattr(self._llm, "_model_name", "default"))
