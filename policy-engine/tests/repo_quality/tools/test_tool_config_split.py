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


def _normalized_ruff_settings(
    settings: dict[str, str], *, caller_root: Path, product_root: Path, git_root: Path
) -> dict[str, str]:
    """Compare settings with relative exclusion globs bound to the actual caller root."""

    normalized: dict[str, str] = {}
    for key, value in settings.items():
        if key in {"file_resolver.project_root", "linter.project_root"}:
            continue
        if key == "file_resolver.extend_exclude":
            patterns = tomllib.loads(f"patterns = {value}")["patterns"]
            value = json.dumps([str(caller_root / pattern) for pattern in patterns])
        normalized[key] = _normalize_ruff_paths(value, product_root=product_root, git_root=git_root)
    return normalized


def _ruff_diagnostic_signature(output: str) -> list[tuple[str, str, int, int, int, int]]:
    """Compare lint findings without treating caller-relative filenames as semantic."""

    signatures: list[tuple[str, str, int, int, int, int]] = []
    for item in json.loads(output):
        location = item["location"]
        end = item.get("end_location") or {}
        signatures.append(
            (
                item["code"],
                item["message"],
                location["row"],
                location["column"],
                end.get("row", 0),
                end.get("column", 0),
            )
        )
    return sorted(signatures)


def test_phase5_5_tool_config_split_roots_are_policy_stubs() -> None:
    mypy = (REPO_ROOT / "mypy.ini").read_text(encoding="utf-8")
    ruff = (REPO_ROOT / "ruff.toml").read_text(encoding="utf-8")
    mkdocs = (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    manifest = tool_configs.load_manifest(REPO_ROOT)["ruff"]

    assert "[mypy-" not in mypy
    assert f'extend = "{manifest["generated_config"]}"' in ruff
    assert "INHERIT: architecture/tooling/mkdocs/generated.yml" in mkdocs


def test_workspace_atlas_s101_allowance_is_generated_and_semantic(tmp_path: Path) -> None:
    manifest = tool_configs.load_manifest(REPO_ROOT)["ruff"]
    rendered = {item.relative_path: item.content for item in tool_configs.render_files(REPO_ROOT)}
    matcher = "architecture/atlas_surfaces/test_*.py"
    workspace_matcher = f"policy-engine/{matcher}"
    product_ignores = tomllib.loads(rendered[manifest["generated_config"]])["lint"][
        "per-file-ignores"
    ]
    workspace_config_text = rendered[manifest["workspace_root_generated_config"]]
    workspace_ignores = tomllib.loads(workspace_config_text)["lint"]["per-file-ignores"]

    assert product_ignores[matcher] == ["S101"]
    assert workspace_ignores[workspace_matcher] == ["S101"]

    config_dir = tmp_path / "architecture/tooling/ruff"
    config_dir.mkdir(parents=True)
    base = (REPO_ROOT / manifest["base_config"]).read_text(encoding="utf-8")
    (config_dir / "base.toml").write_text(base, encoding="utf-8")
    config_path = config_dir / "workspace_root.toml"
    config_path.write_text(workspace_config_text, encoding="utf-8")
    source_root = config_dir / "policy-engine/architecture/atlas_surfaces"
    source_root.mkdir(parents=True)
    test_file = source_root / "test_probe.py"
    sibling_file = source_root / "probe_helper.py"
    test_file.write_text("def probe() -> None:\n    assert True\n", encoding="utf-8")
    sibling_file.write_text("def probe() -> None:\n    assert True\n", encoding="utf-8")

    def run_s101(path: Path, config: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--no-cache",
                "--config",
                str(config),
                "--select",
                "S101",
                "--output-format",
                "json",
                path.relative_to(config_dir).as_posix(),
            ],
            cwd=config_dir,
            check=False,
            capture_output=True,
            text=True,
        )

    assert run_s101(test_file, config_path).returncode == 0
    sibling_result = run_s101(sibling_file, config_path)
    assert sibling_result.returncode == 1
    assert [item["code"] for item in json.loads(sibling_result.stdout)] == ["S101"]

    removed_config = config_dir / "workspace_root_without_atlas_test_allowance.toml"
    removed_config.write_text(
        workspace_config_text.replace(f'"{workspace_matcher}" = ["S101"]\n', ""),
        encoding="utf-8",
    )
    removed_result = run_s101(test_file, removed_config)
    assert removed_result.returncode == 1
    assert [item["code"] for item in json.loads(removed_result.stdout)] == ["S101"]


@pytest.mark.parametrize(
    ("pattern", "prefix", "expected"),
    [
        ("tests/**", "policy-engine/workers/unit", "policy-engine/workers/unit/tests/**"),
        ("./tests/**", "policy-engine/workers/unit", "policy-engine/workers/unit/tests/**"),
        ("/srv/tests/**", "policy-engine", "/srv/tests/**"),
        ("tests/**", "", "tests/**"),
    ],
)
def test_ruff_pattern_prefix_preserves_root_relative_glob_semantics(
    pattern: str, prefix: str, expected: str
) -> None:
    assert tool_configs._ruff_pattern_for_prefix(pattern, prefix) == expected


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        ("tests/**", "policy-engine/workers/unit-a/tests/**"),
        ("tests/test_*.py", "policy-engine/workers/unit-a/tests/test_*.py"),
        ("**/tests/**", "policy-engine/workers/unit-a/**/tests/**"),
    ],
)
def test_nested_ruff_matcher_projection_stays_inside_its_selected_config_scope(
    pattern: str, expected: str
) -> None:
    assert (
        tool_configs._ruff_nested_pattern_for_prefix(
            pattern, "policy-engine/workers/unit-a", config_path=Path("workers/unit-a/.ruff.toml")
        )
        == expected
    )


@pytest.mark.parametrize(
    "project_relative",
    [
        "workers/unit*",
        "workers/unit?",
        "workers/unit[ab]",
        "workers/unit{a,b}",
        "workers/unit}",
        r"workers/unit\pair",
    ],
)
def test_nested_ruff_scope_prefix_rejects_glob_metacharacters_and_backslashes(
    project_relative: str,
) -> None:
    with pytest.raises(ValueError, match="literal workspace-root Ruff glob"):
        tool_configs._ruff_scope_prefix_for_nested_config(
            "policy-engine",
            project_relative,
            config_path=Path(project_relative) / ".ruff.toml",
        )


@pytest.mark.parametrize(
    "pattern",
    [
        "../shared/tests/**",
        "!tests/**",
        "!../shared/tests/**",
        "../../tests/**",
        "foo/../../shared/tests/**",
        "**/../../shared/tests/**",
        "/shared/tests/**",
        r"..\shared\tests\**",
        "{unit-a,../shared}/tests/**",
        "tests/[ab]/**",
        "tests/?.py",
        "tests/{unit,other}/**",
        "tests//nested/**",
        "tests/./nested/**",
        "tests/**/../shared/**",
        "tests/foo**/bar.py",
    ],
)
def test_nested_ruff_matcher_projection_rejects_uncontained_or_unrepresentable_patterns(
    pattern: str,
) -> None:
    with pytest.raises(ValueError, match="selected config scope"):
        tool_configs._ruff_nested_pattern_for_prefix(
            pattern, "policy-engine/workers/unit-a", config_path=Path("workers/unit-a/.ruff.toml")
        )


def test_workspace_renderer_discovers_selected_ruff_config_and_both_ignore_maps() -> None:
    manifest = tool_configs.load_manifest(REPO_ROOT)["ruff"]
    config_filenames = manifest["workspace_nested_ruff_config_filenames"]
    assert config_filenames == [".ruff.toml", "ruff.toml", "pyproject.toml"]

    with tempfile.TemporaryDirectory(
        prefix="ruff-config-discovery-", dir=REPO_ROOT / "architecture"
    ) as temporary_directory:
        root = Path(temporary_directory)
        precedence = root / "precedence"
        ruff_only = root / "ruff-only"
        pyproject_only = root / "pyproject-only"
        for project in (precedence, ruff_only, pyproject_only):
            project.mkdir()

        (precedence / "pyproject.toml").write_text(
            '[tool.ruff]\nextend = ["../../../ruff.toml"]\n'
            '[tool.ruff.lint.per-file-ignores]\n"tests/**" = ["PT001"]\n',
            encoding="utf-8",
        )
        (precedence / "ruff.toml").write_text(
            'extend = "../../../ruff.toml"\n[lint.per-file-ignores]\n"tests/**" = ["ANN"]\n',
            encoding="utf-8",
        )
        (precedence / ".ruff.toml").write_text(
            'extend = "../../../ruff.toml"\n'
            '[lint.per-file-ignores]\n"tests/**" = ["S101"]\n'
            '[lint.extend-per-file-ignores]\n"tests/**" = ["T201", "S101"]\n',
            encoding="utf-8",
        )
        (ruff_only / "ruff.toml").write_text(
            'extend = "../../../ruff.toml"\n'
            '[lint.extend-per-file-ignores]\n"tests/**" = ["PT011"]\n',
            encoding="utf-8",
        )
        (pyproject_only / "pyproject.toml").write_text(
            '[tool.ruff]\nextend = "../../../ruff.toml"\n'
            '[tool.ruff.lint.per-file-ignores]\n"tests/**" = ["E501"]\n',
            encoding="utf-8",
        )

        root_fragments = [
            tool_configs._read_ruff_per_file_ignore_fragment(
                REPO_ROOT, fragment, project_root_prefix=manifest["workspace_root_prefix"]
            )
            for fragment in manifest["per_file_ignore_fragments"]
        ]
        root_ignores = tomllib.loads("[lint.per-file-ignores]\n" + "\n".join(root_fragments))[
            "lint"
        ]["per-file-ignores"]
        fragments = tool_configs._read_nested_ruff_per_file_ignore_fragments(
            REPO_ROOT,
            config_filenames=config_filenames,
            product_root_config=REPO_ROOT / manifest["root_config"],
            workspace_root_prefix=manifest["workspace_root_prefix"],
            root_per_file_ignore_patterns=tuple(root_ignores),
        )
        projected = tomllib.loads("[lint.per-file-ignores]\n" + "\n".join(fragments))["lint"][
            "per-file-ignores"
        ]

        def matcher(project: Path) -> str:
            relative = project.relative_to(REPO_ROOT).as_posix()
            return f"policy-engine/{relative}/tests/**"

        precedence_matcher = matcher(precedence)
        assert projected[precedence_matcher] == ["S101", "T201"]
        assert projected[matcher(ruff_only)] == ["PT011"]
        assert projected[matcher(pyproject_only)] == ["E501"]
        assert "policy-engine/workers/dowhy-014/tests/**" not in projected
        assert "PT001" not in projected[precedence_matcher]
        assert "ANN" not in projected[precedence_matcher]


def test_workspace_renderer_discovers_config_omitted_from_git_file_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(
        prefix="ruff-config-filesystem-", dir=REPO_ROOT / "workers"
    ) as temporary_directory:
        project = Path(temporary_directory) / "filesystem-config"
        project.mkdir()
        config = project / ".ruff.toml"
        config.write_text(
            'extend = "../../../ruff.toml"\n[lint.per-file-ignores]\n"tests/**" = ["S101"]\n',
            encoding="utf-8",
        )
        relative = project.relative_to(REPO_ROOT).as_posix()
        input_paths = (
            f"workers/dowhy-014/tests/test_worker.py\0{relative}/tests/test_probe.py\0"
        ).encode()

        def list_source_inputs(
            *args: object, **kwargs: object
        ) -> subprocess.CompletedProcess[bytes]:
            command = kwargs.get("args", args[0] if args else [])
            return subprocess.CompletedProcess(command, 0, stdout=input_paths, stderr=b"")

        monkeypatch.setattr(tool_configs.subprocess, "run", list_source_inputs)
        fragments = tool_configs._read_nested_ruff_per_file_ignore_fragments(
            REPO_ROOT,
            config_filenames=[".ruff.toml", "ruff.toml", "pyproject.toml"],
            product_root_config=REPO_ROOT / "ruff.toml",
            workspace_root_prefix="policy-engine",
            root_per_file_ignore_patterns=(),
        )
        projected = tomllib.loads("[lint.per-file-ignores]\n" + "\n".join(fragments))["lint"][
            "per-file-ignores"
        ]

        assert projected[f"policy-engine/{relative}/tests/**"] == ["S101"]


@pytest.mark.parametrize(
    ("config_text", "message"),
    [
        ('[tool.ruff.lint]\nper-file-ignores = "S101"\n', "per-file-ignores must be a TOML table"),
        (
            '[tool.ruff.lint]\nextend-per-file-ignores = "T201"\n',
            "extend-per-file-ignores must be a TOML table",
        ),
        (
            '[tool.ruff.lint.per-file-ignores]\n"tests/**" = ["S101", 1]\n',
            "invalid Ruff rules",
        ),
    ],
)
def test_workspace_renderer_rejects_malformed_nested_ignore_fields(
    config_text: str, message: str
) -> None:
    with tempfile.TemporaryDirectory(
        prefix="ruff-invalid-ignore-map-", dir=REPO_ROOT / "workers"
    ) as temporary_directory:
        project = Path(temporary_directory) / "invalid-map"
        project.mkdir()
        (project / "pyproject.toml").write_text(
            '[tool.ruff]\nextend = "../../../ruff.toml"\n' + config_text,
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match=message):
            tool_configs._read_nested_ruff_per_file_ignore_fragments(
                REPO_ROOT,
                config_filenames=[".ruff.toml", "ruff.toml", "pyproject.toml"],
                product_root_config=REPO_ROOT / "ruff.toml",
                workspace_root_prefix="policy-engine",
                root_per_file_ignore_patterns=(),
            )


@pytest.mark.parametrize("extend_value", ['["../../../ruff.toml"]', "7", '""'])
def test_workspace_renderer_rejects_non_string_nested_ruff_extend(
    extend_value: str,
) -> None:
    with tempfile.TemporaryDirectory(
        prefix="ruff-invalid-extend-", dir=REPO_ROOT / "workers"
    ) as temporary_directory:
        project = Path(temporary_directory) / "invalid"
        project.mkdir()
        (project / "pyproject.toml").write_text(
            f"[tool.ruff]\nextend = {extend_value}\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="extend must be a string path"):
            tool_configs._read_nested_ruff_per_file_ignore_fragments(
                REPO_ROOT,
                config_filenames=[".ruff.toml", "ruff.toml", "pyproject.toml"],
                product_root_config=REPO_ROOT / "ruff.toml",
                workspace_root_prefix="policy-engine",
                root_per_file_ignore_patterns=(),
            )


def test_workspace_renderer_fails_closed_on_unsupported_and_overlapping_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory(
        prefix="ruff-config-boundary-", dir=REPO_ROOT / "workers"
    ) as temporary_directory:
        root = Path(temporary_directory)
        config_filenames = [".ruff.toml", "ruff.toml", "pyproject.toml"]

        def select_configs(*paths: Path) -> None:
            selected_paths = tuple(path.relative_to(REPO_ROOT) for path in paths)
            monkeypatch.setattr(
                tool_configs,
                "_workspace_paths_named",
                lambda _repo_root, _filenames: list(selected_paths),
            )

        local = root / "local-only"
        local.mkdir()
        (local / "pyproject.toml").write_text(
            '[tool.ruff.lint.per-file-ignores]\n"tests/**" = ["S101"]\n',
            encoding="utf-8",
        )
        select_configs(local / "pyproject.toml")
        with pytest.raises(ValueError, match="must directly extend"):
            tool_configs._read_nested_ruff_per_file_ignore_fragments(
                REPO_ROOT,
                config_filenames=config_filenames,
                product_root_config=REPO_ROOT / "ruff.toml",
                workspace_root_prefix="policy-engine",
                root_per_file_ignore_patterns=(),
            )

        overlapping = root / "overlap"
        overlapping.mkdir()
        (overlapping / "pyproject.toml").write_text(
            '[tool.ruff]\nextend = "../../../ruff.toml"\n'
            '[tool.ruff.lint.per-file-ignores]\n"tests/**" = ["S101"]\n',
            encoding="utf-8",
        )
        select_configs(overlapping / "pyproject.toml")
        overlapping_root_matcher = (
            f"policy-engine/{overlapping.relative_to(REPO_ROOT).as_posix()}/**"
        )
        with pytest.raises(ValueError, match="may overlap its scope"):
            tool_configs._read_nested_ruff_per_file_ignore_fragments(
                REPO_ROOT,
                config_filenames=config_filenames,
                product_root_config=REPO_ROOT / "ruff.toml",
                workspace_root_prefix="policy-engine",
                root_per_file_ignore_patterns=(overlapping_root_matcher,),
            )

        parent = root / "parent"
        child = parent / "children"
        child.mkdir(parents=True)
        (parent / "pyproject.toml").write_text(
            '[tool.ruff]\nextend = "../../../ruff.toml"\n'
            '[tool.ruff.lint.extend-per-file-ignores]\n"children/**" = ["S101"]\n',
            encoding="utf-8",
        )
        (child / "pyproject.toml").write_text(
            '[tool.ruff]\nextend = "../../../../ruff.toml"\n',
            encoding="utf-8",
        )
        select_configs(parent / "pyproject.toml", child / "pyproject.toml")
        with pytest.raises(ValueError, match="scopes overlap"):
            tool_configs._read_nested_ruff_per_file_ignore_fragments(
                REPO_ROOT,
                config_filenames=config_filenames,
                product_root_config=REPO_ROOT / "ruff.toml",
                workspace_root_prefix="policy-engine",
                root_per_file_ignore_patterns=(),
            )


@pytest.mark.parametrize(
    ("selected_ignore", "expected_codes", "lower_ruff_codes", "lower_pyproject_codes"),
    [
        (
            '[lint.per-file-ignores]\n"tests/**" = ["S101"]\n',
            ["T201"],
            ["T201"],
            ["T201"],
        ),
        (
            '[lint.extend-per-file-ignores]\n"tests/**" = ["T201"]\n',
            ["S101"],
            ["S101"],
            ["S101"],
        ),
        (
            '[lint.per-file-ignores]\n"tests/**" = ["S101"]\n'
            '[lint.extend-per-file-ignores]\n"tests/**" = ["T201"]\n',
            [],
            ["S101"],
            ["T201"],
        ),
    ],
)
def test_nested_ruff_discovery_projection_matches_real_diagnostics_and_removal_probe(
    selected_ignore: str,
    expected_codes: list[str],
    lower_ruff_codes: list[str],
    lower_pyproject_codes: list[str],
) -> None:
    git_root = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=REPO_ROOT, text=True
        ).strip()
    )
    product_prefix = REPO_ROOT.relative_to(git_root).as_posix()
    with tempfile.TemporaryDirectory(
        prefix="ruff-nested-runtime-", dir=REPO_ROOT / "workers"
    ) as temporary_directory:
        fixture_root = Path(temporary_directory)
        project = fixture_root / "project"
        tests = project / "tests"
        tests.mkdir(parents=True)
        root_config = fixture_root / "ruff.toml"
        root_config.write_text('[lint]\nselect = ["S101", "T201"]\n', encoding="utf-8")
        (project / ".ruff.toml").write_text(
            'extend = "../ruff.toml"\n' + selected_ignore, encoding="utf-8"
        )
        (project / "ruff.toml").write_text(
            'extend = "../ruff.toml"\n'
            f'[lint.per-file-ignores]\n"tests/**" = {json.dumps(lower_ruff_codes)}\n',
            encoding="utf-8",
        )
        (project / "pyproject.toml").write_text(
            '[tool.ruff]\nextend = "../ruff.toml"\n'
            "[tool.ruff.lint.per-file-ignores]\n"
            f'"tests/**" = {json.dumps(lower_pyproject_codes)}\n',
            encoding="utf-8",
        )
        probe = tests / "test_probe.py"
        probe.write_text(
            "def test_probe(value):\n    assert value\n    print(value)\n",
            encoding="utf-8",
        )

        fixture_relative = fixture_root.relative_to(REPO_ROOT).as_posix()
        workspace_prefix = f"{product_prefix}/{fixture_relative}"
        manifest = tool_configs.load_manifest(REPO_ROOT)["ruff"]
        fragments = tool_configs._read_nested_ruff_per_file_ignore_fragments(
            fixture_root,
            config_filenames=manifest["workspace_nested_ruff_config_filenames"],
            product_root_config=root_config,
            workspace_root_prefix=workspace_prefix,
            root_per_file_ignore_patterns=(),
        )
        assert len(fragments) == 1
        assert (project / ".ruff.toml").is_file()
        workspace_target = f"{product_prefix}/{fixture_relative}/project/tests/test_probe.py"
        product_target = "tests/test_probe.py"
        workspace_settings = '[lint]\nselect = ["S101", "T201"]\n'
        if fragments:
            workspace_settings += "[lint.per-file-ignores]\n" + "\n".join(fragments)

        def run_ruff(
            cwd: Path, target: str, *, config: Path | None = None
        ) -> subprocess.CompletedProcess[str]:
            command = [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--no-cache",
                "--output-format=json",
                "--select",
                "S101,T201",
            ]
            if config is not None:
                command.extend(["--config", str(config)])
            command.append(target)
            return subprocess.run(command, cwd=cwd, text=True, capture_output=True)

        product = run_ruff(project, product_target)
        assert product.returncode in {0, 1}, product.stdout + product.stderr
        product_codes = sorted(item["code"] for item in json.loads(product.stdout))
        assert product_codes == expected_codes

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=".ruff-workspace-probe-",
            suffix=".toml",
            dir=git_root,
            delete=False,
        ) as workspace_file:
            workspace_file.write(workspace_settings)
            workspace_config = Path(workspace_file.name)
        try:
            workspace = run_ruff(git_root, workspace_target, config=workspace_config)
            assert workspace.returncode in {0, 1}, workspace.stdout + workspace.stderr
            workspace_codes = sorted(item["code"] for item in json.loads(workspace.stdout))
            assert workspace_codes == expected_codes
            assert _ruff_diagnostic_signature(product.stdout) == _ruff_diagnostic_signature(
                workspace.stdout
            )

            # Keep the nested config markers present while removing their projected rules.
            workspace_config.write_text(
                "# Nested source config markers remain; projection is intentionally removed.\n"
                '[lint]\nselect = ["S101", "T201"]\n',
                encoding="utf-8",
            )
            without_projection = run_ruff(git_root, workspace_target, config=workspace_config)
            assert without_projection.returncode in {0, 1}
            assert sorted(item["code"] for item in json.loads(without_projection.stdout)) != (
                expected_codes
            )
        finally:
            workspace_config.unlink(missing_ok=True)


def test_nested_ruff_escape_is_rejected_after_real_sibling_consumer_falsifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git_root = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=REPO_ROOT, text=True
        ).strip()
    )
    product_prefix = REPO_ROOT.relative_to(git_root).as_posix()
    with tempfile.TemporaryDirectory(
        prefix="ruff-config-scope-", dir=REPO_ROOT / "workers"
    ) as temporary_directory:
        fixture_root = Path(temporary_directory)
        unit_a = fixture_root / "unit-a"
        shared = fixture_root / "shared"
        sibling_tests = shared / "tests"
        unit_a.mkdir()
        sibling_tests.mkdir(parents=True)
        unit_probe = unit_a / "probe.py"
        unit_probe.write_text("def test_probe():\n    assert True\n", encoding="utf-8")
        unit_config = unit_a / ".ruff.toml"
        unit_config.write_text(
            'extend = "../../../ruff.toml"\n'
            '[lint.per-file-ignores]\n"../shared/tests/**" = ["S101"]\n',
            encoding="utf-8",
        )
        sibling_config = shared / ".ruff.toml"
        sibling_config.write_text('[lint]\nselect = ["S101"]\n', encoding="utf-8")
        probe = sibling_tests / "test_probe.py"
        probe.write_text("def test_probe():\n    assert True\n", encoding="utf-8")

        fixture_relative = fixture_root.relative_to(REPO_ROOT).as_posix()
        selected_scope = f"{product_prefix}/{fixture_relative}/unit-a"
        workspace_unit_target = f"{product_prefix}/{fixture_relative}/unit-a/probe.py"
        workspace_sibling_target = f"{product_prefix}/{fixture_relative}/shared/tests/test_probe.py"
        projected_escape = tool_configs._ruff_pattern_for_prefix(
            "../shared/tests/**", selected_scope
        )
        assert projected_escape == (f"{product_prefix}/{fixture_relative}/shared/tests/**")

        def run_ruff(
            cwd: Path, target: str, *, config: Path | None = None
        ) -> subprocess.CompletedProcess[str]:
            command = [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--no-cache",
                "--output-format=json",
                "--select",
                "S101",
            ]
            if config is not None:
                command.extend(["--config", str(config)])
            command.append(target)
            return subprocess.run(command, cwd=cwd, text=True, capture_output=True)

        product_unit = run_ruff(unit_a, "probe.py")
        assert product_unit.returncode in {0, 1}, product_unit.stdout + product_unit.stderr
        product_unit_codes = sorted(item["code"] for item in json.loads(product_unit.stdout))
        assert product_unit_codes == ["S101"]

        product_sibling = run_ruff(shared, "tests/test_probe.py")
        assert product_sibling.returncode in {0, 1}, product_sibling.stdout + product_sibling.stderr
        product_sibling_codes = sorted(item["code"] for item in json.loads(product_sibling.stdout))
        assert product_sibling_codes == ["S101"]
        assert '"../shared/tests/**" = ["S101"]' in unit_config.read_text(encoding="utf-8")
        assert sibling_config.is_file()

        workspace_settings = (
            '[lint]\nselect = ["S101"]\n'
            "[lint.per-file-ignores]\n"
            f'{json.dumps(projected_escape)} = ["S101"]\n'
        )
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=".ruff-sibling-scope-probe-",
            suffix=".toml",
            dir=git_root,
            delete=False,
        ) as workspace_file:
            workspace_file.write(workspace_settings)
            workspace_config = Path(workspace_file.name)
        try:
            workspace_unit = run_ruff(git_root, workspace_unit_target, config=workspace_config)
            assert workspace_unit.returncode in {0, 1}, (
                workspace_unit.stdout + workspace_unit.stderr
            )
            workspace_unit_codes = sorted(
                item["code"] for item in json.loads(workspace_unit.stdout)
            )
            assert workspace_unit_codes == product_unit_codes

            workspace_sibling = run_ruff(
                git_root, workspace_sibling_target, config=workspace_config
            )
            assert workspace_sibling.returncode in {0, 1}, (
                workspace_sibling.stdout + workspace_sibling.stderr
            )
            workspace_sibling_codes = sorted(
                item["code"] for item in json.loads(workspace_sibling.stdout)
            )
            assert workspace_sibling_codes == []

            manifest = tool_configs.load_manifest(REPO_ROOT)["ruff"]
            listed_configs = b"unit-a/.ruff.toml\0shared/.ruff.toml\0"

            def list_fixture_configs(
                *args: object, **kwargs: object
            ) -> subprocess.CompletedProcess[bytes]:
                command = kwargs.get("args", args[0] if args else [])
                return subprocess.CompletedProcess(command, 0, stdout=listed_configs, stderr=b"")

            monkeypatch.setattr(tool_configs.subprocess, "run", list_fixture_configs)
            with pytest.raises(ValueError, match="selected config scope"):
                tool_configs._read_nested_ruff_per_file_ignore_fragments(
                    fixture_root,
                    config_filenames=manifest["workspace_nested_ruff_config_filenames"],
                    product_root_config=REPO_ROOT / manifest["root_config"],
                    workspace_root_prefix=f"{product_prefix}/{fixture_relative}",
                    root_per_file_ignore_patterns=(),
                )
        finally:
            workspace_config.unlink(missing_ok=True)


def test_nested_ruff_glob_scope_is_rejected_after_real_sibling_consumer_falsifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git_root = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=REPO_ROOT, text=True
        ).strip()
    )
    product_prefix = REPO_ROOT.relative_to(git_root).as_posix()
    with tempfile.TemporaryDirectory(
        prefix="ruff-config-prefix-glob-", dir=REPO_ROOT / "workers"
    ) as temporary_directory:
        fixture_root = Path(temporary_directory)
        selected = fixture_root / "unit[ab]"
        sibling = fixture_root / "unitb"
        selected_tests = selected / "tests"
        sibling_tests = sibling / "tests"
        selected_tests.mkdir(parents=True)
        sibling_tests.mkdir(parents=True)
        source = "def test_probe():\n    assert True\n"
        (selected_tests / "test_probe.py").write_text(source, encoding="utf-8")
        (sibling_tests / "test_probe.py").write_text(source, encoding="utf-8")
        selected_config = selected / ".ruff.toml"
        selected_config.write_text(
            'extend = "../../../ruff.toml"\n[lint.per-file-ignores]\n"tests/**" = ["S101"]\n',
            encoding="utf-8",
        )
        sibling_config = sibling / ".ruff.toml"
        sibling_config.write_text('[lint]\nselect = ["S101"]\n', encoding="utf-8")

        def run_ruff(cwd: Path, target: str, *, config: Path | None = None):
            command = [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--no-cache",
                "--output-format=json",
                "--select",
                "S101",
            ]
            if config is not None:
                command.extend(["--config", str(config)])
            command.append(target)
            return subprocess.run(command, cwd=cwd, text=True, capture_output=True)

        selected_result = run_ruff(selected, "tests/test_probe.py")
        assert selected_result.returncode in {0, 1}, selected_result.stdout + selected_result.stderr
        selected_codes = sorted(item["code"] for item in json.loads(selected_result.stdout))
        assert selected_codes == []

        sibling_result = run_ruff(sibling, "tests/test_probe.py")
        assert sibling_result.returncode in {0, 1}, sibling_result.stdout + sibling_result.stderr
        sibling_codes = sorted(item["code"] for item in json.loads(sibling_result.stdout))
        assert sibling_codes == ["S101"]

        fixture_relative = fixture_root.relative_to(REPO_ROOT).as_posix()
        scope_prefix = f"{product_prefix}/{fixture_relative}"
        unsafe_pattern = f"{scope_prefix}/unit[ab]/tests/**"
        workspace_selected_target = (
            f"{unsafe_pattern.removesuffix('/tests/**')}/tests/test_probe.py"
        )
        workspace_sibling_target = f"{product_prefix}/{fixture_relative}/unitb/tests/test_probe.py"
        workspace_settings = (
            '[lint]\nselect = ["S101"]\n'
            "[lint.per-file-ignores]\n"
            f'{json.dumps(unsafe_pattern)} = ["S101"]\n'
        )
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=".ruff-prefix-glob-probe-",
            suffix=".toml",
            dir=git_root,
            delete=False,
        ) as workspace_file:
            workspace_file.write(workspace_settings)
            workspace_config = Path(workspace_file.name)
        try:
            workspace_selected = run_ruff(
                git_root, workspace_selected_target, config=workspace_config
            )
            assert workspace_selected.returncode in {0, 1}, (
                workspace_selected.stdout + workspace_selected.stderr
            )
            workspace_selected_codes = sorted(
                item["code"] for item in json.loads(workspace_selected.stdout)
            )
            assert workspace_selected_codes == ["S101"]
            assert workspace_selected_codes != selected_codes

            workspace_sibling = run_ruff(
                git_root, workspace_sibling_target, config=workspace_config
            )
            assert workspace_sibling.returncode in {0, 1}, (
                workspace_sibling.stdout + workspace_sibling.stderr
            )
            assert json.loads(workspace_sibling.stdout) == []

            manifest = tool_configs.load_manifest(REPO_ROOT)["ruff"]
            monkeypatch.setattr(
                tool_configs,
                "_workspace_paths_named",
                lambda *_args, **_kwargs: [Path("unit[ab]/.ruff.toml"), Path("unitb/.ruff.toml")],
            )
            assert '"tests/**" = ["S101"]' in selected_config.read_text(encoding="utf-8")
            assert sibling_config.is_file()
            with pytest.raises(ValueError, match="literal workspace-root Ruff glob"):
                tool_configs._read_nested_ruff_per_file_ignore_fragments(
                    fixture_root,
                    config_filenames=manifest["workspace_nested_ruff_config_filenames"],
                    product_root_config=REPO_ROOT / manifest["root_config"],
                    workspace_root_prefix=scope_prefix,
                    root_per_file_ignore_patterns=(),
                )

            def without_prefix_guard(
                workspace_root_prefix: str, project_relative: str, *, config_path: Path
            ) -> str:
                return f"{workspace_root_prefix}/{project_relative}"

            monkeypatch.setattr(
                tool_configs, "_ruff_scope_prefix_for_nested_config", without_prefix_guard
            )
            fragments = tool_configs._read_nested_ruff_per_file_ignore_fragments(
                fixture_root,
                config_filenames=manifest["workspace_nested_ruff_config_filenames"],
                product_root_config=REPO_ROOT / manifest["root_config"],
                workspace_root_prefix=scope_prefix,
                root_per_file_ignore_patterns=(),
            )
            projected = tomllib.loads("[lint.per-file-ignores]\n" + "\n".join(fragments))["lint"][
                "per-file-ignores"
            ]
            assert unsafe_pattern in projected
            assert projected[unsafe_pattern] == ["S101"]
        finally:
            workspace_config.unlink(missing_ok=True)


def test_workspace_generated_config_drift_rejects_a_corrupt_nested_ignore(tmp_path: Path) -> None:
    manifest = tool_configs.load_manifest(REPO_ROOT)["ruff"]
    generated = next(
        item
        for item in tool_configs.render_files(REPO_ROOT)
        if item.relative_path == manifest["workspace_root_generated_config"]
    )
    rule = '"policy-engine/workers/**/tests/**" = ["ANN", "E501", "PT011", "PT018", "S101", "T201"]'
    assert rule in generated.content
    corrupted_content = generated.content.replace(rule, rule.replace(', "T201"', ""), 1)
    assert corrupted_content != generated.content
    corrupted_path = tmp_path / "workspace_root.toml"
    corrupted_path.write_text(corrupted_content, encoding="utf-8")

    findings = tool_configs.check_drift(
        (
            tool_configs.RenderedFile(
                path=corrupted_path,
                content=generated.content,
                repo_root=tmp_path,
            ),
        )
    )

    assert len(findings) == 1
    assert findings[0]["message"] == "generated config is stale"
    assert "policy-engine/workers/**/tests/**" in findings[0]["diff"]


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

    comparable_product_settings = _normalized_ruff_settings(
        product_settings, caller_root=REPO_ROOT, product_root=REPO_ROOT, git_root=git_root
    )
    comparable_workspace_settings = _normalized_ruff_settings(
        workspace_settings, caller_root=git_root, product_root=REPO_ROOT, git_root=git_root
    )
    assert comparable_workspace_settings == comparable_product_settings
    normalized_product_ignores = {
        _normalize_ruff_paths(matcher, product_root=REPO_ROOT, git_root=git_root): value
        for matcher, value in product_per_file_ignores.items()
    }
    normalized_workspace_ignores = {
        _normalize_ruff_paths(matcher, product_root=REPO_ROOT, git_root=git_root): value
        for matcher, value in workspace_per_file_ignores.items()
    }
    worker_test_scope = "<PRODUCT>/workers/**/tests/**"
    assert worker_test_scope in normalized_product_ignores
    assert normalized_workspace_ignores == normalized_product_ignores

    nested_worker_target = "workers/dowhy-014/tests/test_worker.py"
    nested_workspace_worker_target = f"{product_prefix}/{nested_worker_target}"
    product_worker_settings_result = run_ruff(
        REPO_ROOT, None, "--show-settings", nested_worker_target
    )
    workspace_worker_settings_result = run_ruff(
        git_root, pre_commit_config, "--show-settings", nested_workspace_worker_target
    )
    assert product_worker_settings_result.returncode == 0, product_worker_settings_result.stderr
    assert workspace_worker_settings_result.returncode == 0, workspace_worker_settings_result.stderr
    product_worker_settings, product_worker_ignores = _parse_ruff_settings(
        product_worker_settings_result.stdout
    )
    workspace_worker_settings, workspace_worker_ignores = _parse_ruff_settings(
        workspace_worker_settings_result.stdout
    )
    normalized_product_worker_ignores = {
        _normalize_ruff_paths(matcher, product_root=REPO_ROOT, git_root=git_root): value
        for matcher, value in product_worker_ignores.items()
    }
    normalized_workspace_worker_ignores = {
        _normalize_ruff_paths(matcher, product_root=REPO_ROOT, git_root=git_root): value
        for matcher, value in workspace_worker_ignores.items()
    }
    assert (
        normalized_product_worker_ignores[worker_test_scope]
        == normalized_workspace_worker_ignores[worker_test_scope]
    )
    assert product_worker_settings["linter.unresolved_target_version"] == "3.12"
    assert workspace_worker_settings["linter.unresolved_target_version"] == "3.14"
    assert normalized_product_ignores
    assert comparable_product_settings["cache_dir"] == '"<PRODUCT>/_cache/ruff"'
    assert comparable_product_settings["file_resolver.include"]
    assert comparable_product_settings["file_resolver.exclude"]
    assert comparable_product_settings["file_resolver.extend_include"] == "[]"
    expected_excludes = tool_configs.load_manifest(REPO_ROOT)["ruff"]["product_root_settings"][
        "extend-exclude"
    ]
    assert (
        tomllib.loads(f"patterns = {product_settings['file_resolver.extend_exclude']}")["patterns"]
        == expected_excludes
    )

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

    product_worker = run_ruff(REPO_ROOT, None, "--output-format=json", nested_worker_target)
    workspace_worker = run_ruff(
        git_root,
        pre_commit_config,
        "--output-format=json",
        f"{product_prefix}/{nested_worker_target}",
    )
    assert product_worker.returncode == 0, product_worker.stdout + product_worker.stderr
    assert workspace_worker.returncode == 0, workspace_worker.stdout + workspace_worker.stderr
    assert _ruff_diagnostic_signature(product_worker.stdout) == _ruff_diagnostic_signature(
        workspace_worker.stdout
    )

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
    root_settings = tomllib.loads(rendered[manifest["root_config"]])
    workspace_root_settings = tomllib.loads(rendered[manifest["workspace_root_generated_config"]])
    source_excludes = manifest["product_root_settings"]["extend-exclude"]
    assert root_settings["extend-exclude"] == source_excludes
    assert workspace_root_settings["extend-exclude"] == [
        f"{product_prefix}/{pattern}" for pattern in source_excludes
    ]
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
                _normalized_ruff_settings(
                    settings,
                    caller_root=cwd,
                    product_root=REPO_ROOT,
                    git_root=git_root,
                )
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
    assert expected_subjects
    assert {entry.subject for entry in product_entries} == expected_subjects
    assert {entry.subject for entry in workspace_entries} == expected_subjects
    assert len(product_entries) == len(expected_subjects)
    assert len(workspace_entries) == len(expected_subjects)

    product_report = dead_overrides.build_report(
        REPO_ROOT,
        ruff_config=manifest["generated_config"],
    )
    workspace_report = dead_overrides.build_report(
        REPO_ROOT,
        ruff_config=manifest["workspace_root_generated_config"],
    )
    assert product_report["summary"]["ruff_override_count"] == len(expected_subjects)
    assert workspace_report["summary"]["ruff_override_count"] == len(expected_subjects)
    for report in (product_report, workspace_report):
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
