from __future__ import annotations

from pathlib import Path

from tools.devx.workspace import _repo_hygiene, benchmark_surfaces
from tools.devx.workspace._common import CommandSpec


def _spec(label: str, *argv: str) -> CommandSpec:
    return CommandSpec(label=label, argv=argv, cwd=Path("."))


def test_phase8_expand_files_target_only_authored_shell_and_yaml() -> None:
    files = _repo_hygiene.expand_files(
        _repo_hygiene.BENCHMARK_RESEARCH_SCOPE,
        suffixes=(".sh", ".yaml", ".yml"),
    )

    assert "benchmarks/run_all_benchmarks.sh" in files
    assert "tools/research/benchmarks/run_all_benchmarks.sh" in files
    assert "benchmarks/comparators/research_acceptance_environment.yml" in files
    assert all(not file_path.endswith((".json", ".log", ".md")) for file_path in files)


def test_markdownlint_ignores_phase8_benchmark_and_research_markdown() -> None:
    config_text = (_repo_hygiene.PRODUCT_ROOT / ".markdownlint-cli2.jsonc").read_text(
        encoding="utf-8"
    )

    assert '"benchmarks/**/*.md"' in config_text
    assert '"tools/research/**/*.md"' in config_text


def test_benchmark_surfaces_default_sequence(monkeypatch) -> None:
    seen: list[CommandSpec] = []

    monkeypatch.setattr(benchmark_surfaces, "run_command", lambda spec: seen.append(spec))
    monkeypatch.setattr(
        benchmark_surfaces,
        "uv_run",
        lambda label, *argv, cwd=None: _spec(label, *argv),
    )
    monkeypatch.setattr(
        benchmark_surfaces,
        "pre_commit_hook",
        lambda hook_id, *, label, files=None: _spec(label, hook_id, *(files or ())),
    )

    def _fake_expand_files(
        raw_paths: list[str] | tuple[str, ...],
        *,
        suffixes: tuple[str, ...],
        exclude_prefixes: tuple[str, ...] = (),
    ) -> list[str]:
        assert raw_paths == _repo_hygiene.BENCHMARK_RESEARCH_SCOPE
        assert exclude_prefixes == ()
        if suffixes == (".sh",):
            return [
                "benchmarks/run_all_benchmarks.sh",
                "tools/research/benchmarks/run_all_benchmarks.sh",
            ]
        assert suffixes == (".yaml", ".yml")
        return ["benchmarks/comparators/research_acceptance_environment.yml"]

    monkeypatch.setattr(benchmark_surfaces, "expand_files", _fake_expand_files)

    exit_code = benchmark_surfaces.main([])

    assert exit_code == 0
    assert [spec.label for spec in seen] == [
        "ruff check benchmark/research authored Python",
        "ruff format --check benchmark/research authored Python",
        "shfmt benchmark/research shell",
        "shellcheck benchmark/research shell",
        "yamllint benchmark/research YAML",
    ]
    assert seen[0].argv == (
        "ruff",
        "check",
        "--select",
        "E,F,I,UP",
        "--ignore",
        "E402,E501",
        "benchmarks",
        "tools/research",
    )
