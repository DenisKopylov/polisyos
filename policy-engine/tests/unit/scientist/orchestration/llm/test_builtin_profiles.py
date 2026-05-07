"""Tests for built-in model profile config."""

from __future__ import annotations

import importlib

from polisyos.scientist.orchestration.llm.profiles import builtin_profiles


def _qwen_profile():
    return next(
        profile
        for profile in builtin_profiles.BUILTIN_MODEL_PROFILES
        if profile.profile_id == "qwen3_235b_gonka"
    )


def test_qwen_profile_uses_canonical_gonkagate_base_url_by_default():
    importlib.reload(builtin_profiles)
    profile = _qwen_profile()

    assert profile.base_url == "https://api.gonkagate.com/v1"
    assert profile.model_id == "qwen/qwen3-235b-a22b-instruct-2507-fp8"
    assert profile.input_cost_per_mtoken_usd == 0.0006
    assert profile.output_cost_per_mtoken_usd == 0.0006
    assert profile.capabilities == ["json"]


def test_qwen_profile_supports_env_rollback_and_tool_calling_gate(monkeypatch):
    monkeypatch.setenv("POLISYOS_QWEN_GONKA_MODEL_ID", "legacy-qwen-model")
    monkeypatch.setenv(
        "POLISYOS_QWEN_GONKA_BASE_URL",
        "https://gonka-gateway.mingles.ai/v1",
    )
    monkeypatch.setenv("POLISYOS_QWEN_GONKA_TOOL_CALLING_VERIFIED", "true")
    monkeypatch.setenv("POLISYOS_QWEN_GONKA_PRESET_ID", "qwen-agent-stable")

    importlib.reload(builtin_profiles)
    try:
        profile = _qwen_profile()
        assert profile.model_id == "legacy-qwen-model"
        assert profile.base_url == "https://gonka-gateway.mingles.ai/v1"
        assert profile.preset_id == "qwen-agent-stable"
        assert profile.capabilities == ["json", "tool_calling"]
    finally:
        monkeypatch.delenv("POLISYOS_QWEN_GONKA_MODEL_ID", raising=False)
        monkeypatch.delenv("POLISYOS_QWEN_GONKA_BASE_URL", raising=False)
        monkeypatch.delenv(
            "POLISYOS_QWEN_GONKA_TOOL_CALLING_VERIFIED",
            raising=False,
        )
        monkeypatch.delenv("POLISYOS_QWEN_GONKA_PRESET_ID", raising=False)
        importlib.reload(builtin_profiles)
