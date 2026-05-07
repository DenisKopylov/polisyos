from __future__ import annotations

import tomllib
from pathlib import Path

from tools.devx.workspace import tool_configs
from tools.ops_runners.reports import dead_overrides

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase5_5_tool_config_split_roots_are_policy_stubs() -> None:
    mypy = (REPO_ROOT / "mypy.ini").read_text(encoding="utf-8")
    ruff = (REPO_ROOT / "ruff.toml").read_text(encoding="utf-8")
    mkdocs = (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8")

    assert "[mypy-" not in mypy
    assert 'extend = "architecture/tooling/ruff/generated.toml"' in ruff
    assert "INHERIT: architecture/tooling/mkdocs/generated.yml" in mkdocs


def test_phase5_5_tool_config_split_generated_files_are_current() -> None:
    rendered = tool_configs.render_files(REPO_ROOT)

    assert not tool_configs.check_drift(rendered)


def test_phase5_5_dead_override_report_reads_generated_configs() -> None:
    report = dead_overrides.build_report(REPO_ROOT)

    assert report["configs"]["mypy"] == "architecture/tooling/mypy/generated.ini"
    assert report["configs"]["ruff"] == "architecture/tooling/ruff/generated.toml"
    assert report["summary"]["mypy_override_count"] > 0
    assert report["summary"]["ruff_override_count"] > 0
    assert report["summary"]["stale_mypy_override_count"] == 0
    assert report["summary"]["stale_ruff_override_count"] == 0


def test_phase5_5_tool_config_split_contract_is_registered() -> None:
    manifest = tomllib.loads(
        (REPO_ROOT / "architecture/tooling/tool_config_split.toml").read_text(
            encoding="utf-8"
        )
    )
    generated = tomllib.loads(
        (REPO_ROOT / "architecture/generated_artifacts.toml").read_text(encoding="utf-8")
    )

    assert manifest["tool_config_split"]["status"] == "active"
    family_ids = {family["id"] for family in generated["family"]}
    assert "tool-config-split-generated-configs" in family_ids
