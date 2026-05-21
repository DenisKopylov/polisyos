from __future__ import annotations

from tools.quality.testing import local_integration_stack


def test_local_integration_stack_uses_playwright_fixture_metadata_path() -> None:
    expected = (
        local_integration_stack.REPO_ROOT
        / "_build"
        / "apps"
        / "runtime-dashboard"
        / ".tmp"
        / "fixture-runtime.json"
    )

    assert local_integration_stack.DEFAULT_METADATA_FILE == expected


def test_local_integration_stack_runtime_defaults_to_simulated_llm() -> None:
    assert local_integration_stack._runtime_env_overrides() == {
        "POLISYOS_LLM_SIMULATION_MODE": "1"
    }
