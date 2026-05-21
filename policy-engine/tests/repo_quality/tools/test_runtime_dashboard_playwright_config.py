from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_runtime_dashboard_playwright_fixture_server_uses_simulated_llm() -> None:
    config_text = (
        REPO_ROOT / "apps/runtime-dashboard/playwright.config.ts"
    ).read_text(encoding="utf-8")

    assert "serve_fixture_runtime_api.py" in config_text
    assert 'POLISYOS_LLM_SIMULATION_MODE: "1"' in config_text
