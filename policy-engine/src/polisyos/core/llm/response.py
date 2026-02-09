from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMResponseData:
    content: str
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def extract_llm_response_data(response: Any) -> LLMResponseData:
    content = response.content if hasattr(response, "content") else str(response)
    prompt_tokens = 0
    completion_tokens = 0

    try:
        usage = getattr(response, "usage", None)
        if usage is not None:
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        elif isinstance(response, dict):
            usage = response.get("usage", {})
            prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
            completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        elif hasattr(response, "input_tokens"):
            prompt_tokens = int(getattr(response, "input_tokens", 0) or 0)
            completion_tokens = int(getattr(response, "output_tokens", 0) or 0)
    except Exception:
        prompt_tokens = 0
        completion_tokens = 0

    return LLMResponseData(
        content=content,
        prompt_tokens=max(0, prompt_tokens),
        completion_tokens=max(0, completion_tokens),
    )

