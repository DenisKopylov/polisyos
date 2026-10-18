from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from tools.quality.validation import (
    directory_health,
    directory_health_dashboard,
    directory_health_inventory,
)


def test_git_path_stream_preserves_newline_names_and_all_records(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    names = ["docs/research/raw/ordinary.txt", "docs/research/raw/line\nbreak.txt"]
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("raw input\n", encoding="utf-8")
    subprocess.run(["git", "add", "--all"], cwd=tmp_path, check=True)

    assert list(directory_health_inventory.iter_git_paths(tmp_path, "ls-files")) == sorted(names)


def test_nul_record_decoder_handles_chunk_boundaries_without_path_filtering() -> None:
    records = directory_health_inventory.iter_nul_records(
        [b"docs/research/raw/a\n", b"me.txt\0tests/fixtures/raw/b\0last"]
    )

    assert list(records) == ["docs/research/raw/a\nme.txt", "tests/fixtures/raw/b", "last"]


def test_scandir_stream_visits_complete_raw_tree_and_only_declared_skips(tmp_path: Path) -> None:
    raw_root = tmp_path / "docs" / "research" / "raw"
    raw_root.mkdir(parents=True)
    expected_files: set[str] = set()
    for index in range(40):
        relative = f"docs/research/raw/record-{index:03}.json"
        path = tmp_path / relative
        path.write_text("{}", encoding="utf-8")
        expected_files.add(relative)
    nested = tmp_path / "docs" / "research" / "raw" / "fixtures" / "case"
    nested.mkdir(parents=True)
    nested_file = nested / "input.bin"
    nested_file.write_bytes(b"input")
    expected_files.add(nested_file.relative_to(tmp_path).as_posix())
    skipped = tmp_path / ".venv" / "ignored.py"
    skipped.parent.mkdir()
    skipped.write_text("pass", encoding="utf-8")

    files = directory_health_inventory.iter_files(tmp_path, skip_dir_names={".venv"})
    directories = directory_health_inventory.iter_directories(tmp_path, skip_dir_names={".venv"})

    assert {path.relative_to(tmp_path).as_posix() for path in files} == expected_files
    assert {path.relative_to(tmp_path).as_posix() for path in directories} == {
        ".",
        "docs",
        "docs/research",
        "docs/research/raw",
        "docs/research/raw/fixtures",
        "docs/research/raw/fixtures/case",
    }


def test_non_product_init_inventory_streams_count_and_keeps_lexical_sample(
    tmp_path: Path,
) -> None:
    root = tmp_path / "tools"
    for index in range(16):
        path = root / f"package-{index:02}" / "__init__.py"
        path.parent.mkdir(parents=True)
        path.write_text("", encoding="utf-8")
    dependencies = SimpleNamespace(
        read_toml=lambda _path: {"non_product_python_root": [{"path": "tools"}]},
        rel=lambda path, repo_root: path.relative_to(repo_root).as_posix(),
    )

    rows = directory_health_dashboard.non_product_python_root_inventory(
        tmp_path, dependencies=dependencies
    )

    assert rows == [
        {
            "root": "tools",
            "exists": True,
            "init_file_count": 16,
            "sample_init_files": [f"tools/package-{index:02}/__init__.py" for index in range(10)],
        }
    ]


class _PrefixReader:
    def __init__(self) -> None:
        self.requested_size: int | None = None

    def __enter__(self) -> _PrefixReader:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int) -> str:
        self.requested_size = size
        return "// GENERATED FILE\n"


class _HeaderPath:
    suffix = ".ts"

    def __init__(self, reader: _PrefixReader) -> None:
        self.reader = reader

    def open(self, *, encoding: str, errors: str) -> _PrefixReader:
        assert encoding == "utf-8"
        assert errors == "ignore"
        return self.reader


def test_generated_api_header_probe_reads_only_its_decision_prefix() -> None:
    reader = _PrefixReader()

    assert directory_health._looks_like_generated_api_file(
        "packages/client/src/api/generated.ts",
        _HeaderPath(reader),  # type: ignore[arg-type]
    )
    assert reader.requested_size == 1000
