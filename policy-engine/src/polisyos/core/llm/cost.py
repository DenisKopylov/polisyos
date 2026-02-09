from __future__ import annotations

from polisyos.core.observability.pricing import estimate_llm_cost_usd


def estimate_cost_from_tokens(
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    return estimate_llm_cost_usd(
        model=model,
        prompt_tokens=max(0, int(prompt_tokens)),
        completion_tokens=max(0, int(completion_tokens)),
    )


def estimate_cost_from_text(
    *,
    model: str,
    response_text: str | None,
) -> float:
    if not response_text:
        return 0.0
    approx_completion = max(1, len(response_text) // 4)
    approx_prompt = approx_completion * 2
    return estimate_cost_from_tokens(
        model=model,
        prompt_tokens=approx_prompt,
        completion_tokens=approx_completion,
    )


def estimate_cost(
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    response_text: str | None = None,
) -> float:
    if prompt_tokens > 0 or completion_tokens > 0:
        return estimate_cost_from_tokens(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    return estimate_cost_from_text(model=model, response_text=response_text)

