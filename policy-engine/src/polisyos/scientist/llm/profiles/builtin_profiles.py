"""Built-in model profiles for runtime dashboard selection."""

from __future__ import annotations

import os

from polisyos.scientist.llm.provider_verification import is_provider_capability_verified

from .models import ModelProfile


def _env_text(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped or default


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


_QWEN_GONKA_MODEL_ID = _env_text(
    "POLISYOS_QWEN_GONKA_MODEL_ID",
    "qwen/qwen3-235b-a22b-instruct-2507-fp8",
)
_QWEN_GONKA_BASE_URL = _env_text(
    "POLISYOS_QWEN_GONKA_BASE_URL",
    "https://api.gonkagate.com/v1",
)
_QWEN_GONKA_PRESET_ID = _env_text(
    "POLISYOS_QWEN_GONKA_PRESET_ID",
    "",
)
_QWEN_GONKA_CAPABILITIES = ["json"]
if (
    _env_bool("POLISYOS_QWEN_GONKA_TOOL_CALLING_EMERGENCY_OVERRIDE", default=False)
    or _env_bool(
        "POLISYOS_QWEN_GONKA_TOOL_CALLING_VERIFIED",
        default=False,
    )
    or is_provider_capability_verified(
        provider="gonka",
        model_id=_QWEN_GONKA_MODEL_ID,
        capability="tool_calling",
    )
):
    _QWEN_GONKA_CAPABILITIES.append("tool_calling")

BUILTIN_MODEL_PROFILES: list[ModelProfile] = [
    ModelProfile(
        profile_id="gpt5_mini_gateway",
        display_name="GPT-5 mini (Gateway)",
        description="Balanced OpenAI frontier model via OpenAI-compatible gateway.",
        provider="openai",
        model_id="gpt-5-mini",
        base_url="https://api.gonkagate.com/v1",
        tags=["frontier", "balanced"],
        capabilities=["json", "tool_calling"],
    ),
    ModelProfile(
        profile_id="claude_sonnet_gateway",
        display_name="Claude Sonnet 4.5 (Gateway)",
        description="High-quality Anthropic model routed through gateway.",
        provider="anthropic",
        model_id="claude-sonnet-4-5-20250929",
        base_url="https://api.gonkagate.com/v1",
        tags=["frontier", "reasoning"],
        capabilities=["json", "tool_calling"],
    ),
    ModelProfile(
        profile_id="gemini_flash_gateway",
        display_name="Gemini 2.5 Flash (Gateway)",
        description="Fast cost-efficient Gemini profile routed through gateway.",
        provider="google",
        model_id="gemini-2.5-flash",
        base_url="https://api.gonkagate.com/v1",
        tags=["fast", "economy"],
        capabilities=["json"],
    ),
    ModelProfile(
        profile_id="llama4_scout_gateway",
        display_name="Llama 4 Scout (Gateway)",
        description="Open-weights speed profile for regression and load runs.",
        provider="groq",
        model_id="meta-llama/llama-4-scout-17b-16e-instruct",
        base_url="https://api.gonkagate.com/v1",
        tags=["open-weights", "fast", "cheap"],
        capabilities=["json"],
    ),
    ModelProfile(
        profile_id="qwen3_235b_gonka",
        display_name="Qwen3-235B (Gonka)",
        description="Gonka-focused ultra-cheap profile for bulk experiment runs.",
        provider="gonka",
        model_id=_QWEN_GONKA_MODEL_ID,
        base_url=_QWEN_GONKA_BASE_URL,
        preset_id=_QWEN_GONKA_PRESET_ID or None,
        tags=["gonka", "ultra-cheap", "experimental"],
        capabilities=_QWEN_GONKA_CAPABILITIES,
        input_cost_per_mtoken_usd=0.0006,
        output_cost_per_mtoken_usd=0.0006,
    ),
]

__all__ = ["BUILTIN_MODEL_PROFILES"]
