"""Tests for the bounded documentation source-binding check."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tools.quality.validation import check_docs_source_bindings as checker


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(root: Path, message: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-m", message)
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def source_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "docs-check@example.invalid")
    _git(root, "config", "user.name", "Docs checker test")
    (root / "src" / "nested").mkdir(parents=True)
    (root / "src" / "module.py").write_bytes(b"value = 1\n")
    (root / "src" / "nested" / "other.py").write_bytes(b"value = 2\n")
    pin = _commit(root, "source baseline")
    docs = root / "docs" / "guide.md"
    docs.parent.mkdir()
    docs.write_text(
        "# Guide\n\n"
        f"Source pin: `{pin}`\n"
        "Source of truth: `src/module.py`,\n"
        "  `src/**/*.py`\n\n"
        "This page explains the selected source.\n",
        encoding="utf-8",
    )
    _commit(root, "add source-bound guide")
    return root, docs, pin


def _invoke(
    root: Path, docs: Path, capsys: pytest.CaptureFixture[str], *extra_args: str
) -> tuple[int, dict[str, Any]]:
    code = checker.main(
        [
            "--repo-root",
            str(root),
            "--doc",
            str(docs.relative_to(root)),
            "--against-ref",
            "HEAD",
            "--format",
            "json",
            *extra_args,
        ]
    )
    report = json.loads(capsys.readouterr().out)
    return code, report["documents"][0]


def test_equal_declared_sources_pass_and_disclose_scope(
    source_repo: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    root, docs, pin = source_repo

    code, result = _invoke(root, docs, capsys)

    assert code == 0
    assert result["status"] == "PASS"
    assert result["source_pin"] == pin
    assert result["against_commit"] == _git(root, "rev-parse", "HEAD")
    assert result["matched_path_count"] == 2
    assert result["unchanged_path_count"] == 2
    assert len(result["selected_read_set_sha256"]) == 64
    assert "matched_paths" not in result
    assert "claim coverage and prose truth" in result["unmeasured"]
    assert "test execution and semantic adequacy" in result["unmeasured"]
    assert "test source bytes outside the declared source set" in result["unmeasured"]
    assert result["doc_worktree"]["status"] == "clean"
    assert len(result["doc_worktree"]["sha256"]) == 64


def test_changed_source_bytes_fail_even_when_declared_pattern_is_unchanged(
    source_repo: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    root, docs, _pin = source_repo
    (root / "src" / "module.py").write_bytes(b"value = 999\n")
    _commit(root, "change declared owner")

    code, result = _invoke(root, docs, capsys)

    assert code == 1
    assert result["status"] == "FAILED"
    assert result["content_changed_path_count"] == 1


def test_nul_delimited_tree_handles_newline_paths_and_text_examples_escape_them(
    source_repo: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    root, docs, _old_pin = source_repo
    newline_path = root / "src" / "line\nbreak.py"
    newline_path.write_bytes(b"line_break = True\n")
    pin = _commit(root, "add source path containing newline")
    docs.write_text(
        docs.read_text(encoding="utf-8").replace(_old_pin, pin),
        encoding="utf-8",
    )
    _commit(root, "bind guide to newline source")

    code, result = _invoke(root, docs, capsys)

    assert code == 0
    assert result["matched_path_count"] == 3
    assert len(result["selected_read_set_sha256"]) == 64
    assert checker._changed_examples({b"src/line\nbreak.py"}) == [r"src/line\nbreak.py"]


@pytest.mark.parametrize(
    ("relative_path", "content"),
    [
        ("src/new.py", b"new = True\n"),
        ("src/nested/new.py", b"new = True\n"),
    ],
)
def test_glob_expansion_detects_added_members(
    source_repo: tuple[Path, Path, str],
    relative_path: str,
    content: bytes,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, docs, _pin = source_repo
    new_source = root / relative_path
    new_source.parent.mkdir(parents=True, exist_ok=True)
    new_source.write_bytes(content)
    _commit(root, "add declared source member")

    code, result = _invoke(root, docs, capsys)

    assert code == 1
    assert result["status"] == "FAILED"
    assert result["added_path_count"] == 1


def test_glob_expansion_detects_removed_members(
    source_repo: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    root, docs, _pin = source_repo
    (root / "src" / "nested" / "other.py").unlink()
    _commit(root, "remove declared source member")

    code, result = _invoke(root, docs, capsys)

    assert code == 1
    assert result["status"] == "FAILED"
    assert result["removed_path_count"] == 1


def test_star_does_not_cross_a_slash_but_double_star_does(tmp_path: Path) -> None:
    assert checker.path_matches("src/*.py", "src/a.py")
    assert not checker.path_matches("src/*.py", "src/nested/a.py")
    assert checker.path_matches("src/**/*.py", "src/a.py")
    assert checker.path_matches("src/**/*.py", "src/nested/a.py")
    assert checker.path_matches("src/file?.py", "src/file1.py")
    assert not checker.path_matches("src/file?.py", "src/file10.py")


def test_deep_double_star_pattern_does_not_crash_cli(
    source_repo: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    root, docs, pin = source_repo
    deep_pattern = "/".join(["**"] * 1200 + ["src/module.py"])
    docs.write_text(
        f"# Guide\n\nSource pin: `{pin}`\nSource of truth: `{deep_pattern}`\n",
        encoding="utf-8",
    )

    code, result = _invoke(root, docs, capsys)

    assert code == 0
    assert result["status"] == "PASS"
    assert result["matched_path_count"] == 1


@pytest.mark.parametrize(
    "owner_path",
    [
        "../outside.py",
        "/absolute.py",
        "src/{a,b}.py",
        "src/[ab].py",
        "src\\module.py",
        "other:src/module.py",
    ],
)
def test_unsafe_or_unsupported_source_patterns_return_unrun(
    source_repo: tuple[Path, Path, str], owner_path: str, capsys: pytest.CaptureFixture[str]
) -> None:
    root, docs, pin = source_repo
    docs.write_text(
        f"# Guide\n\nSource pin: `{pin}`\nSource of truth: `{owner_path}`\n",
        encoding="utf-8",
    )

    code, result = _invoke(root, docs, capsys)

    assert code == 2
    assert result["status"] == "UNRUN"


@pytest.mark.parametrize(
    "metadata",
    [
        "Source pin: `abc123`\nSource of truth: `src/module.py`\n",
        "The body mentions `0123456789012345678901234567890123456789`.\n"
        "Source of truth: `src/module.py`\n",
        "Source pin: `0123456789012345678901234567890123456789`\nSource of truth: src/module.py\n",
    ],
)
def test_missing_or_ambiguous_metadata_is_unrun(
    source_repo: tuple[Path, Path, str], metadata: str, capsys: pytest.CaptureFixture[str]
) -> None:
    root, docs, _pin = source_repo
    docs.write_text(f"# Guide\n\n{metadata}", encoding="utf-8")

    code, result = _invoke(root, docs, capsys)

    assert code == 2
    assert result["status"] == "UNRUN"


def test_dirty_markdown_reports_worktree_status_and_hash(
    source_repo: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    root, docs, _pin = source_repo
    docs.write_text(docs.read_text(encoding="utf-8") + "Edited locally.\n", encoding="utf-8")
    expected_hash = hashlib.sha256(docs.read_bytes()).hexdigest()

    code, result = _invoke(root, docs, capsys)

    assert code == 0
    assert result["doc_worktree"]["status"] == "modified"
    assert result["doc_worktree"]["sha256"] == expected_hash


def test_markdown_hash_and_metadata_use_one_buffer_across_worktree_race(
    source_repo: tuple[Path, Path, str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, docs, pin = source_repo
    captured = docs.read_bytes()
    replacement_pin = "f" * 40
    mutated = captured.replace(pin.encode("ascii"), replacement_pin.encode("ascii"))
    original_read_bytes = Path.read_bytes
    reads = 0

    def mutate_after_first_read(path: Path) -> bytes:
        nonlocal reads
        content = original_read_bytes(path)
        if path == docs:
            reads += 1
            if reads == 1:
                docs.write_bytes(mutated)
        return content

    monkeypatch.setattr(Path, "read_bytes", mutate_after_first_read)

    code, result = _invoke(root, docs, capsys)

    assert code == 0
    assert reads == 1
    assert result["source_pin"] == pin
    assert result["doc_worktree"]["sha256"] == hashlib.sha256(captured).hexdigest()
    assert result["doc_worktree"]["read_count"] == 1
    assert "single selected Markdown byte buffer" in result["doc_worktree"]["source"]


def test_executable_mode_change_is_reported(
    source_repo: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    root, docs, _pin = source_repo
    _git(root, "update-index", "--chmod=+x", "src/module.py")
    _git(root, "commit", "-m", "change declared source mode")

    code, result = _invoke(root, docs, capsys)

    assert code == 1
    assert result["mode_changed_path_count"] == 1


def test_replacement_refs_cannot_change_the_pinned_tree_read(
    source_repo: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    root, docs, pin = source_repo
    (root / "src" / "module.py").write_bytes(b"value = replacement\n")
    replacement = _commit(root, "commit replacement source")
    _git(root, "replace", pin, replacement)

    code, result = _invoke(root, docs, capsys)

    assert code == 1
    assert result["status"] == "FAILED"
    assert result["content_changed_path_count"] == 1
    assert result["git_read_policy"]["replacement_refs"].startswith("disabled")


def test_lfs_pointer_is_unrun(
    source_repo: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    root, docs, _pin = source_repo
    pointer = (
        b"version https://git-lfs.github.com/spec/v1\noid sha256:" + b"a" * 64 + b"\nsize 10\n"
    )
    (root / "src" / "module.py").write_bytes(pointer)
    _commit(root, "replace source with LFS pointer")

    code, result = _invoke(root, docs, capsys)

    assert code == 2
    assert result["status"] == "UNRUN"
    assert "LFS" in result["reason"]


def test_symlink_hashes_stored_target_without_following_it(
    source_repo: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    root, docs, _pin = source_repo
    (root / "src" / "link.py").symlink_to("../outside-target")
    pin = _commit(root, "add symlink to source baseline")
    docs.write_text(
        f"# Guide\n\nSource pin: `{pin}`\nSource of truth: `src/link.py`\n",
        encoding="utf-8",
    )
    _commit(root, "add declared symlink")

    code, result = _invoke(root, docs, capsys)

    assert code == 0
    assert result["symlink_path_count"] == 1
    assert (
        "resolved bytes behind symlinks (only the stored target text is compared)"
        in result["unmeasured"]
    )


def test_gitlink_source_set_is_unrun(
    source_repo: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    root, docs, source_pin = source_repo
    _git(root, "update-index", "--add", "--cacheinfo", f"160000,{source_pin},src/submodule")
    _git(root, "commit", "-m", "add gitlink")
    gitlink_pin = _git(root, "rev-parse", "HEAD")
    docs.write_text(
        f"# Guide\n\nSource pin: `{gitlink_pin}`\nSource of truth: `src/submodule`\n",
        encoding="utf-8",
    )
    _commit(root, "bind doc to gitlink")

    code, result = _invoke(root, docs, capsys)

    assert code == 2
    assert result["status"] == "UNRUN"
    assert "gitlink" in result["reason"]


def test_git_root_and_product_root_are_accepted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git_root = tmp_path / "workspace"
    product_root = git_root / "policy-engine"
    git_root.mkdir()
    _git(git_root, "init", "-q")
    _git(git_root, "config", "user.email", "docs-check@example.invalid")
    _git(git_root, "config", "user.name", "Docs checker test")
    product_root.mkdir()
    (product_root / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
    (product_root / "src").mkdir(parents=True)
    (product_root / "src" / "owner.py").write_bytes(b"owner = True\n")
    pin = _commit(git_root, "nested product source")
    docs = product_root / "docs" / "guide.md"
    docs.parent.mkdir()
    docs.write_text(
        f"# Guide\n\nSource pin: `{pin}`\nSource of truth: `src/owner.py`\n",
        encoding="utf-8",
    )
    _commit(git_root, "nested product docs")

    code, result = _invoke(git_root, docs, capsys)
    assert code == 0
    assert result["status"] == "PASS"
    assert result["doc"] == "policy-engine/docs/guide.md"
    repo_root_digest = result["selected_read_set_sha256"]

    code, result = _invoke(product_root, docs, capsys)
    assert code == 0
    assert result["status"] == "PASS"
    assert result["doc"] == "policy-engine/docs/guide.md"
    assert result["selected_read_set_sha256"] == repo_root_digest


def test_repo_namespace_selects_root_file_over_product_shadow_and_is_root_independent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git_root = tmp_path / "workspace"
    product_root = git_root / "policy-engine"
    git_root.mkdir()
    _git(git_root, "init", "-q")
    _git(git_root, "config", "user.email", "docs-check@example.invalid")
    _git(git_root, "config", "user.name", "Docs checker test")
    (git_root / ".github").mkdir()
    (git_root / ".github" / "CODEOWNERS").write_text("root owners\n", encoding="utf-8")
    (product_root / ".github").mkdir(parents=True)
    (product_root / ".github" / "CODEOWNERS").write_text("product shadow\n", encoding="utf-8")
    (product_root / "src").mkdir()
    (product_root / "src" / "owner.py").write_text("owner = True\n", encoding="utf-8")
    pin = _commit(git_root, "root and product source owners")
    docs = product_root / "docs" / "guide.md"
    docs.parent.mkdir()
    docs.write_text(
        f"# Guide\n\nSource pin: `{pin}`\n"
        "Source of truth: `repo:.github/CODEOWNERS`, `product:.github/CODEOWNERS`\n",
        encoding="utf-8",
    )
    _commit(git_root, "add source-bound guide")

    (git_root / ".github" / "CODEOWNERS").write_text("changed root owners\n", encoding="utf-8")
    _commit(git_root, "change repository-root owner only")

    code, repo_result = _invoke(git_root, docs, capsys)
    assert code == 1
    assert repo_result["status"] == "FAILED"
    assert repo_result["content_changed_path_count"] == 1
    assert repo_result["pattern_expansion"]["repo:.github/CODEOWNERS"] == {
        "at_source_pin": 1,
        "at_comparison_commit": 1,
    }
    assert repo_result["pattern_expansion"]["product:.github/CODEOWNERS"] == {
        "at_source_pin": 1,
        "at_comparison_commit": 1,
    }

    code, product_result = _invoke(product_root, docs, capsys)
    assert code == 1
    assert product_result["status"] == "FAILED"
    assert product_result["selected_read_set_sha256"] == repo_result["selected_read_set_sha256"]
