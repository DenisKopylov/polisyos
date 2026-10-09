from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

import yaml

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


def test_ruff_pre_commit_settings_and_collection_match_product_root() -> None:
    git_root = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=REPO_ROOT, text=True
        ).strip()
    )
    product_prefix = REPO_ROOT.relative_to(git_root).as_posix()
    pre_commit = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    ruff_repositories = [
        repository
        for repository in pre_commit["repos"]
        if repository["repo"] == "https://github.com/astral-sh/ruff-pre-commit"
    ]
    assert len(ruff_repositories) == 1
    ruff_hooks = [
        hook for hook in ruff_repositories[0]["hooks"] if hook["id"] in {"ruff", "ruff-format"}
    ]
    config_arguments = {
        argument
        for hook in ruff_hooks
        for argument in hook.get("args", [])
        if argument.startswith("--config=")
    }
    assert len(ruff_hooks) == 2
    assert len(config_arguments) == 1
    pre_commit_config = next(iter(config_arguments)).removeprefix("--config=")

    def run_ruff(
        cwd: Path, config: str | None, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, "-m", "ruff", "check"]
        if config is not None:
            command.extend(["--config", config])
        command.extend(arguments)
        return subprocess.run(command, cwd=cwd, text=True, capture_output=True)

    product_target = "tests/unit/scientist/search/funnel/test_level4_full.py"
    workspace_target = f"{product_prefix}/{product_target}"
    product_settings_result = run_ruff(REPO_ROOT, None, "--show-settings", product_target)
    workspace_settings_result = run_ruff(
        git_root, pre_commit_config, "--show-settings", workspace_target
    )
    assert product_settings_result.returncode == 0, product_settings_result.stderr
    assert workspace_settings_result.returncode == 0, workspace_settings_result.stderr
    product_settings = product_settings_result.stdout
    workspace_settings = workspace_settings_result.stdout
    product_matchers = set(
        re.findall(r'^\s*absolute_matcher = "([^"]+)"$', product_settings, re.MULTILINE)
    )
    workspace_matchers = set(
        re.findall(r'^\s*absolute_matcher = "([^"]+)"$', workspace_settings, re.MULTILINE)
    )
    assert product_matchers
    assert workspace_matchers == product_matchers
    assert str(REPO_ROOT / "tests/**") in product_matchers
    assert str(REPO_ROOT / "tests/unit/scientist/**") in product_matchers

    product_files_result = run_ruff(
        REPO_ROOT,
        None,
        "--show-files",
        "tests/unit/scientist/search/funnel",
    )
    workspace_files_result = run_ruff(
        git_root,
        pre_commit_config,
        "--show-files",
        f"{product_prefix}/tests/unit/scientist/search/funnel",
    )
    assert product_files_result.returncode == 0, product_files_result.stderr
    assert workspace_files_result.returncode == 0, workspace_files_result.stderr
    assert set(product_files_result.stdout.splitlines()) == set(
        workspace_files_result.stdout.splitlines()
    )

    with tempfile.TemporaryDirectory(
        prefix="ruff-root-probe-", dir=REPO_ROOT / "tests/unit/scientist/search/funnel"
    ) as probe_dir:
        probe = Path(probe_dir) / "test_root_config_probe.py"
        probe.write_text("def test_probe(value):\n    assert value\n", encoding="utf-8")
        product_probe = run_ruff(
            REPO_ROOT,
            None,
            "--output-format=json",
            "--select",
            "ANN001,S101",
            probe.relative_to(REPO_ROOT).as_posix(),
        )
        workspace_probe = run_ruff(
            git_root,
            pre_commit_config,
            "--output-format=json",
            "--select",
            "ANN001,S101",
            probe.relative_to(git_root).as_posix(),
        )
        assert product_probe.returncode == 0, product_probe.stdout + product_probe.stderr
        assert workspace_probe.returncode == 0, workspace_probe.stdout + workspace_probe.stderr
        assert json.loads(product_probe.stdout) == []
        assert json.loads(workspace_probe.stdout) == []


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
        (REPO_ROOT / "architecture/tooling/tool_config_split.toml").read_text(encoding="utf-8")
    )
    generated = tomllib.loads(
        (REPO_ROOT / "architecture/generated_artifacts.toml").read_text(encoding="utf-8")
    )

    assert manifest["tool_config_split"]["status"] == "active"
    families = {family["id"]: family for family in generated["family"]}
    family_ids = set(families)
    assert "tool-config-split-generated-configs" in family_ids
    assert (
        "architecture/tooling/ruff/workspace_root.toml"
        in families["tool-config-split-generated-configs"]["outputs"]
    )
