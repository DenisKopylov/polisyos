from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

import pytest
import yaml

from tools.devx.workspace import tool_configs
from tools.ops_runners.reports import dead_overrides

REPO_ROOT = Path(__file__).resolve().parents[3]


def _parse_ruff_settings(
    output: str,
) -> tuple[dict[str, str], dict[str, tuple[bool, tuple[str, ...]]]]:
    """Parse Ruff's complete settings report and per-file ignore records."""

    settings: dict[str, str] = {}
    current_key: str | None = None
    current_value: list[str] = []
    setting_line = re.compile(r"^([A-Za-z_][A-Za-z0-9_.-]*) = (.*)$")
    per_file_ignores: dict[str, tuple[bool, tuple[str, ...]]] = {}
    in_ignores = False
    matcher: str | None = None
    negated = False
    codes: list[str] = []
    in_codes = False

    def retain_ignore() -> None:
        if matcher is not None:
            per_file_ignores[matcher] = (negated, tuple(codes))

    for line in output.splitlines():
        if line.startswith("#"):
            continue
        if line == "linter.per_file_ignores = {":
            if current_key is not None:
                settings[current_key] = "\n".join(current_value).rstrip()
                current_key = None
                current_value = []
            in_ignores = True
            continue
        if in_ignores:
            if line == "}":
                retain_ignore()
                in_ignores = False
                continue
            absolute_matcher = re.match(r'\s*absolute_matcher = "([^"]+)"$', line)
            if absolute_matcher is not None:
                retain_ignore()
                matcher = absolute_matcher.group(1)
                negated = False
                codes = []
                in_codes = False
                continue
            negated_match = re.match(r"negated = (true|false)$", line)
            if negated_match is not None:
                negated = negated_match.group(1) == "true"
                continue
            if line == "data = [":
                in_codes = True
                continue
            if in_codes:
                if line == "]":
                    in_codes = False
                else:
                    codes.extend(re.findall(r"\(([A-Z]+\d+)\)", line))
            continue
        match = setting_line.match(line)
        if match is not None:
            if match.group(1) == "linter.per_file_ignores":
                raise AssertionError("Ruff per-file ignore block parser missed its opening brace")
            if current_key is not None:
                settings[current_key] = "\n".join(current_value).rstrip()
            current_key = match.group(1)
            current_value = [match.group(2)]
        elif current_key is not None:
            current_value.append(line)
    if current_key is not None:
        settings[current_key] = "\n".join(current_value).rstrip()
    return settings, per_file_ignores


def _normalize_ruff_paths(value: str, *, product_root: Path, git_root: Path) -> str:
    """Normalize absolute caller paths while preserving their product/workspace relation."""

    return value.replace(str(product_root), "<PRODUCT>").replace(str(git_root), "<WORKSPACE>")


def test_phase5_5_tool_config_split_roots_are_policy_stubs() -> None:
    mypy = (REPO_ROOT / "mypy.ini").read_text(encoding="utf-8")
    ruff = (REPO_ROOT / "ruff.toml").read_text(encoding="utf-8")
    mkdocs = (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    manifest = tool_configs.load_manifest(REPO_ROOT)["ruff"]

    assert "[mypy-" not in mypy
    assert f'extend = "{manifest["generated_config"]}"' in ruff
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

    product_target = "src/polisyos/ddm/contracts/metric_budget.py"
    workspace_target = f"{product_prefix}/{product_target}"
    product_settings_result = run_ruff(REPO_ROOT, None, "--show-settings", product_target)
    workspace_settings_result = run_ruff(
        git_root, pre_commit_config, "--show-settings", workspace_target
    )
    assert product_settings_result.returncode == 0, product_settings_result.stderr
    assert workspace_settings_result.returncode == 0, workspace_settings_result.stderr
    product_settings, product_per_file_ignores = _parse_ruff_settings(
        product_settings_result.stdout
    )
    workspace_settings, workspace_per_file_ignores = _parse_ruff_settings(
        workspace_settings_result.stdout
    )
    caller_root_settings = {"file_resolver.project_root", "linter.project_root"}
    assert caller_root_settings <= product_settings.keys()
    assert caller_root_settings <= workspace_settings.keys()
    assert product_settings["file_resolver.project_root"] == f'"{REPO_ROOT}"'
    assert product_settings["linter.project_root"] == f'"{REPO_ROOT}"'
    assert workspace_settings["file_resolver.project_root"] == f'"{git_root}"'
    assert workspace_settings["linter.project_root"] == f'"{git_root}"'

    comparable_product_settings = {
        key: _normalize_ruff_paths(value, product_root=REPO_ROOT, git_root=git_root)
        for key, value in product_settings.items()
        if key not in caller_root_settings
    }
    comparable_workspace_settings = {
        key: _normalize_ruff_paths(value, product_root=REPO_ROOT, git_root=git_root)
        for key, value in workspace_settings.items()
        if key not in caller_root_settings
    }
    assert comparable_workspace_settings == comparable_product_settings
    normalized_product_ignores = {
        _normalize_ruff_paths(matcher, product_root=REPO_ROOT, git_root=git_root): value
        for matcher, value in product_per_file_ignores.items()
    }
    normalized_workspace_ignores = {
        _normalize_ruff_paths(matcher, product_root=REPO_ROOT, git_root=git_root): value
        for matcher, value in workspace_per_file_ignores.items()
    }
    assert normalized_workspace_ignores == normalized_product_ignores
    assert normalized_product_ignores
    assert comparable_product_settings["cache_dir"] == '"<PRODUCT>/_cache/ruff"'
    assert comparable_product_settings["file_resolver.include"]
    assert comparable_product_settings["file_resolver.exclude"]
    assert comparable_product_settings["file_resolver.extend_include"] == "[]"
    assert comparable_product_settings["file_resolver.extend_exclude"] == "[]"

    product_src = re.findall(r'^\s*"([^"]+)"[,]?$', product_settings["linter.src"], re.MULTILINE)
    workspace_src = re.findall(
        r'^\s*"([^"]+)"[,]?$', workspace_settings["linter.src"], re.MULTILINE
    )
    assert set(product_src) == {str(REPO_ROOT), str(REPO_ROOT / "src")}
    assert set(workspace_src) == {
        str(REPO_ROOT),
        str(REPO_ROOT / "src"),
    }

    product_files_result = run_ruff(
        REPO_ROOT,
        None,
        "--show-files",
        ".",
    )
    workspace_files_result = run_ruff(
        git_root,
        pre_commit_config,
        "--show-files",
        product_prefix,
    )
    assert product_files_result.returncode == 0, product_files_result.stderr
    assert workspace_files_result.returncode == 0, workspace_files_result.stderr
    product_files = {
        str((REPO_ROOT / path).resolve()) for path in product_files_result.stdout.splitlines()
    }
    workspace_files = {
        str((git_root / path).resolve()) for path in workspace_files_result.stdout.splitlines()
    }
    assert product_files
    assert workspace_files == product_files

    product_import_sort = run_ruff(
        REPO_ROOT, None, "--no-cache", "--diff", "--select", "I001", product_target
    )
    workspace_import_sort = run_ruff(
        git_root,
        pre_commit_config,
        "--no-cache",
        "--diff",
        "--select",
        "I001",
        workspace_target,
    )
    assert product_import_sort.returncode == 0, (
        product_import_sort.stdout + product_import_sort.stderr
    )
    assert workspace_import_sort.returncode == 0, (
        workspace_import_sort.stdout + workspace_import_sort.stderr
    )
    assert _normalize_ruff_paths(
        product_import_sort.stdout,
        product_root=REPO_ROOT,
        git_root=git_root,
    ) == _normalize_ruff_paths(
        workspace_import_sort.stdout,
        product_root=REPO_ROOT,
        git_root=git_root,
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


def test_explicit_ruff_callers_preserve_settings_and_lint_behavior() -> None:
    git_root = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=REPO_ROOT, text=True
        ).strip()
    )
    product_prefix = REPO_ROOT.relative_to(git_root).as_posix()
    manifest = tool_configs.load_manifest(REPO_ROOT)["ruff"]
    rendered = {item.relative_path: item.content for item in tool_configs.render_files(REPO_ROOT)}
    root_config = Path(manifest["root_config"])
    generated_config = Path(manifest["generated_config"])
    assert root_config.parent == generated_config.parent
    source_per_file_ignores: dict[str, list[str]] = {}
    for fragment_path in manifest["per_file_ignore_fragments"]:
        fragment = (REPO_ROOT / fragment_path).read_text(encoding="utf-8")
        fragment_settings = tomllib.loads(f"[lint.per-file-ignores]\n{fragment}")
        source_per_file_ignores.update(fragment_settings["lint"]["per-file-ignores"])
    product_per_file_ignores = tomllib.loads(rendered[manifest["generated_config"]])["lint"][
        "per-file-ignores"
    ]
    workspace_per_file_ignores = tomllib.loads(
        rendered[manifest["workspace_root_generated_config"]]
    )["lint"]["per-file-ignores"]
    expected_workspace_ignores = {
        f"{product_prefix}/{pattern}": codes for pattern, codes in source_per_file_ignores.items()
    }
    assert product_per_file_ignores == source_per_file_ignores
    assert workspace_per_file_ignores == expected_workspace_ignores

    def run_ruff(
        cwd: Path, config: str | None, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, "-m", "ruff", "check", "--no-cache"]
        if config is not None:
            command.extend(["--config", config])
        command.extend(arguments)
        return subprocess.run(command, cwd=cwd, text=True, capture_output=True)

    representative_paths = (
        "src/polisyos/calibration/adapters.py",
        "tests/unit/calibration/test_adapters.py",
        "tests/repo_quality/architecture/test_repository_best_in_class_phase4_9_operability_bundles.py",
        "tools/devx/workspace/tool_configs.py",
    )
    caller_modes = (
        ("product discovery", REPO_ROOT, None, str(REPO_ROOT)),
        ("product explicit", REPO_ROOT, manifest["root_config"], str(REPO_ROOT)),
        (
            "workspace explicit",
            git_root,
            f"{product_prefix}/{manifest['workspace_root_generated_config']}",
            str(git_root),
        ),
    )
    caller_root_settings = {"file_resolver.project_root", "linter.project_root"}
    for product_path in representative_paths:
        normalized_settings: list[dict[str, str]] = []
        normalized_ignores: list[dict[str, tuple[bool, tuple[str, ...]]]] = []
        for label, cwd, config, expected_root in caller_modes:
            target = (
                f"{product_prefix}/{product_path}"
                if label == "workspace explicit"
                else product_path
            )
            settings_result = run_ruff(cwd, config, "--show-settings", target)
            assert settings_result.returncode == 0, f"{label}: {settings_result.stderr}"
            settings, ignores = _parse_ruff_settings(settings_result.stdout)
            assert settings["file_resolver.project_root"] == f'"{expected_root}"'
            assert settings["linter.project_root"] == f'"{expected_root}"'
            normalized_settings.append(
                {
                    key: _normalize_ruff_paths(value, product_root=REPO_ROOT, git_root=git_root)
                    for key, value in settings.items()
                    if key not in caller_root_settings
                }
            )
            normalized_ignores.append(
                {
                    _normalize_ruff_paths(matcher, product_root=REPO_ROOT, git_root=git_root): value
                    for matcher, value in ignores.items()
                }
            )
        assert normalized_settings[1:] == normalized_settings[:1] * 2
        assert normalized_ignores[1:] == normalized_ignores[:1] * 2

    product_inputs = (
        "src/polisyos/calibration",
        "tests/unit/calibration/test_adapters.py",
        "tests/repo_quality/tools/test_tool_config_split.py",
        "tests/repo_quality/architecture/test_repository_best_in_class_phase4_9_operability_bundles.py",
        "tools/devx/workspace/tool_configs.py",
    )
    for label, cwd, config, _ in caller_modes:
        inputs = (
            tuple(f"{product_prefix}/{path}" for path in product_inputs)
            if label == "workspace explicit"
            else product_inputs
        )
        result = run_ruff(cwd, config, "--output-format=json", *inputs)
        assert result.returncode == 0, f"{label}: {result.stdout}{result.stderr}"
        assert json.loads(result.stdout) == []

    with tempfile.TemporaryDirectory(
        prefix="ruff-product-source-probe-", dir=REPO_ROOT / "src"
    ) as probe_dir:
        probe = Path(probe_dir) / "product_root_probe.py"
        probe.write_text("assert True\n", encoding="utf-8")
        product_path = probe.relative_to(REPO_ROOT).as_posix()
        for label, cwd, config, _ in caller_modes:
            target = (
                f"{product_prefix}/{product_path}"
                if label == "workspace explicit"
                else product_path
            )
            result = run_ruff(
                cwd,
                config,
                "--output-format=json",
                "--select",
                "S101",
                target,
            )
            diagnostics = json.loads(result.stdout)
            assert result.returncode == 1, f"{label}: {result.stdout}{result.stderr}"
            assert [diagnostic["code"] for diagnostic in diagnostics] == ["S101"]


def test_product_ruff_renderer_rejects_non_colocated_generated_config() -> None:
    manifest = tool_configs.load_manifest(REPO_ROOT)
    manifest["ruff"]["generated_config"] = "architecture/tooling/ruff/generated.toml"

    with pytest.raises(ValueError, match="share a directory"):
        tool_configs._render_ruff(REPO_ROOT, manifest)


def test_phase5_5_tool_config_split_generated_files_are_current() -> None:
    rendered = tool_configs.render_files(REPO_ROOT)

    assert not tool_configs.check_drift(rendered)


def test_phase5_5_dead_override_report_reads_generated_configs() -> None:
    report = dead_overrides.build_report(REPO_ROOT)
    ruff_config = tool_configs.load_manifest(REPO_ROOT)["ruff"]["generated_config"]

    assert report["configs"]["mypy"] == "architecture/tooling/mypy/generated.ini"
    assert report["configs"]["ruff"] == ruff_config
    assert report["summary"]["mypy_override_count"] > 0
    assert report["summary"]["ruff_override_count"] > 0
    assert report["summary"]["stale_mypy_override_count"] == 0
    assert report["summary"]["stale_ruff_override_count"] == 0


def test_phase5_5_dead_override_report_covers_both_generated_ruff_roots() -> None:
    manifest = tool_configs.load_manifest(REPO_ROOT)["ruff"]
    assert not tool_configs.check_drift(tool_configs.render_files(REPO_ROOT))

    source_ignores: dict[str, list[str]] = {}
    for fragment_path in manifest["per_file_ignore_fragments"]:
        fragment = (REPO_ROOT / fragment_path).read_text(encoding="utf-8")
        fragment_ignores = tomllib.loads(f"[lint.per-file-ignores]\n{fragment}")["lint"][
            "per-file-ignores"
        ]
        assert not source_ignores.keys() & fragment_ignores.keys()
        source_ignores.update(fragment_ignores)
    rule_pair_count = sum(len(codes) for codes in source_ignores.values())

    metadata = dead_overrides._load_toml(
        REPO_ROOT / "architecture/tooling/static_analysis_overrides.toml"
    )
    product_entries = dead_overrides._collect_ruff_entries(
        REPO_ROOT,
        manifest["generated_config"],
        project_root=dead_overrides._ruff_project_root(
            REPO_ROOT, manifest["generated_config"], metadata
        ),
    )
    workspace_entries = dead_overrides._collect_ruff_entries(
        REPO_ROOT,
        manifest["workspace_root_generated_config"],
        project_root=dead_overrides._ruff_project_root(
            REPO_ROOT, manifest["workspace_root_generated_config"], metadata
        ),
    )
    expected_subjects = set(source_ignores)
    assert len(expected_subjects) == 239
    assert rule_pair_count == 741
    assert {entry.subject for entry in product_entries} == expected_subjects
    assert {entry.subject for entry in workspace_entries} == expected_subjects

    product_report = dead_overrides.build_report(
        REPO_ROOT,
        ruff_config=manifest["generated_config"],
    )
    workspace_report = dead_overrides.build_report(
        REPO_ROOT,
        ruff_config=manifest["workspace_root_generated_config"],
    )
    for report in (product_report, workspace_report):
        assert report["summary"]["ruff_override_count"] == 239
        assert report["summary"]["stale_ruff_override_count"] == 0
        assert report["summary"]["missing_metadata_count"] == 0


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
        tool_configs.load_manifest(REPO_ROOT)["ruff"]["generated_config"]
        in families["tool-config-split-generated-configs"]["outputs"]
    )
    assert (
        "architecture/tooling/ruff/workspace_root.toml"
        in families["tool-config-split-generated-configs"]["outputs"]
    )
