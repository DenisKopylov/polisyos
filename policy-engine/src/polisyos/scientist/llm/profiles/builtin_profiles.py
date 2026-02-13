"""Built-in model profiles for runtime dashboard selection."""

from __future__ import annotations

from .models import ModelProfile

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
        model_id="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        base_url="https://gonka-gateway.mingles.ai/v1",
        tags=["gonka", "ultra-cheap", "experimental"],
        capabilities=["json"],
    ),
]

__all__ = ["BUILTIN_MODEL_PROFILES"]
