"""Public observability pricing module API."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class LLMPrice:
    """LLM price public type."""
    input_per_token_usd: float
    output_per_token_usd: float


PRICING_DEFAULTS: dict[str, LLMPrice] = {
    "gpt-4o": LLMPrice(input_per_token_usd=2.5e-6, output_per_token_usd=10e-6),
    "gemini-pro": LLMPrice(input_per_token_usd=1e-6, output_per_token_usd=4e-6),
    "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8": LLMPrice(
        input_per_token_usd=6e-10,
        output_per_token_usd=6e-10,
    ),
    "qwen3_235b_gonka": LLMPrice(
        input_per_token_usd=6e-10,
        output_per_token_usd=6e-10,
    ),
    "default": LLMPrice(input_per_token_usd=1e-5, output_per_token_usd=3e-5),
}


def pricing_table() -> Mapping[str, LLMPrice]:
    """
    Return effective pricing table.

    Optional env override for default row:
    - POLISYOS_LLM_DEFAULT_INPUT_USD
    - POLISYOS_LLM_DEFAULT_OUTPUT_USD
    """
    default = PRICING_DEFAULTS["default"]
    try:
        default_input = float(os.getenv("POLISYOS_LLM_DEFAULT_INPUT_USD", str(default.input_per_token_usd)))
    except ValueError:
        default_input = default.input_per_token_usd
    try:
        default_output = float(
            os.getenv("POLISYOS_LLM_DEFAULT_OUTPUT_USD", str(default.output_per_token_usd))
        )
    except ValueError:
        default_output = default.output_per_token_usd

    table = dict(PRICING_DEFAULTS)
    table["default"] = LLMPrice(
        input_per_token_usd=max(default_input, 0.0),
        output_per_token_usd=max(default_output, 0.0),
    )
    return table


def estimate_llm_cost_usd(
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Estimate llm cost usd helper."""
    table = pricing_table()
    price = table.get(model, table["default"])
    prompt_cost = max(prompt_tokens, 0) * price.input_per_token_usd
    completion_cost = max(completion_tokens, 0) * price.output_per_token_usd
    return prompt_cost + completion_cost
