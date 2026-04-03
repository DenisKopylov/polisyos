"""Public llm protocols module API."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMClientProtocol(Protocol):
    """LLM client protocol public type."""
    async def generate(self, **kwargs: Any) -> Any:  # pragma: no cover - protocol
        ...

    def invoke(self, prompt: str, **kwargs: Any) -> Any:  # pragma: no cover - protocol
        ...

    async def ainvoke(self, prompt: str, **kwargs: Any) -> Any:  # pragma: no cover - protocol
        ...

