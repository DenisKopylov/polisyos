"""Tests for source-change impact discovery across tracked Markdown."""

from __future__ import annotations

import base64
import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

import pytest

PRODUCT_ROOT = Path(__file__).resolve().parents[3]
POLISYOS_TOOLS = PRODUCT_ROOT / ".venv/bin/polisyos-tools"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="backslashreplace",
    )
    return result.stdout.strip()


def _git_bytes(root: Path, *args: str, input_bytes: bytes) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        input=input_bytes,
    )
    return result.stdout


def _commit(root: Path, message: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-m", message)
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def impact_repo(tmp_path: Path) -> tuple[Path, str, str]:
    root = tmp_path / "repo"
    product = root / "policy-engine"
    source = product / "src" / "pkg"
    docs = product / "docs"
    source.mkdir(parents=True)
    docs.mkdir(parents=True)
    root.mkdir(exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "docs-impact@example.invalid")
    _git(root, "config", "user.name", "Docs impact test")

    (product / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
    (source / "__init__.py").write_text("\n", encoding="utf-8")
    (source / "changed.py").write_text("value = 1\n", encoding="utf-8")
    (source / "deleted.py").write_text("value = 2\n", encoding="utf-8")
    (product / "unrelated.txt").write_text("before\n", encoding="utf-8")
    (root / "README.md").write_text(
        "# Repository overview\n\n"
        "Source pin: `not-a-resolvable-commit`\n"
        "Source of truth: `repo:policy-engine/src/**/*.py`\n",
        encoding="utf-8",
    )
    (docs / "source-bound.md").write_text(
        "# Source-bound reference\n\n"
        "Source snapshot: `not-a-resolvable-commit`\n"
        "Source of truth: `src/**/*.py`\n",
        encoding="utf-8",
    )
    (docs / "product-namespace.md").write_text(
        "# Explicit product namespace\n\nSource of truth: `product:src/**/*.py`\n",
        encoding="utf-8",
    )
    (docs / "snapshot-only.md").write_text(
        "# Historical snapshot\n\nSource snapshot: `not-a-commit-pin`\n",
        encoding="utf-8",
    )
    (docs / "unsupported-directory.md").write_text(
        "# Unsupported directory declaration\n\nSource of truth: `src/`\n",
        encoding="utf-8",
    )
    (docs / "unsupported-brace.md").write_text(
        "# Unsupported brace declaration\n\nSource of truth: `src/{*.py,*.toml}`\n",
        encoding="utf-8",
    )
    (docs / "partial-binding.md").write_text(
        "# Partially supported declaration\n\n"
        "Source of truth: `src/**/*.py`, `src/{*.py,*.toml}`\n",
        encoding="utf-8",
    )
    base = _commit(root, "fixture baseline")

    (source / "changed.py").write_text("value = 10\n", encoding="utf-8")
    (source / "added.py").write_text("value = 3\n", encoding="utf-8")
    (source / "deleted.py").unlink()
    (product / "unrelated.txt").write_text("after\n", encoding="utf-8")
    head = _commit(root, "fixture source changes")
    return root, base, head


def _run_cli(
    root: Path,
    base: str,
    head: str,
    *extra_args: str,
    write_receipt: bool = True,
) -> subprocess.CompletedProcess[str]:
    if write_receipt and "--output" not in extra_args:
        extra_args = (
            *extra_args,
            "--output",
            str(root.parent / f"impact-receipt-{uuid.uuid4().hex}.json"),
        )
    return subprocess.run(
        [
            str(POLISYOS_TOOLS),
            "validation",
            "check-docs-impact",
            "--repo-root",
            str(root),
            "--base-ref",
            base,
            "--head-ref",
            head,
            "--format",
            "json",
            *extra_args,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _report(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    summary = json.loads(result.stdout)
    return json.loads(Path(summary["receipt_path"]).read_text(encoding="utf-8"))


def test_public_cli_queues_source_changes_for_human_review(
    impact_repo: tuple[Path, str, str],
) -> None:
    root, base, head = impact_repo

    result = _run_cli(root, base, head)

    assert result.returncode == 2
    report = _report(result)
    assert report["status"] == "UNRUN"
    assert report["summary"]["tracked_markdown_count"] == 7
    assert report["coverage"]["unmapped_page_count"] == 1
    assert report["coverage"]["unsupported_page_count"] == 3
    queued_docs = {item["doc"] for item in report["review_queue"]}
    assert queued_docs == {
        "README.md",
        "policy-engine/docs/partial-binding.md",
        "policy-engine/docs/product-namespace.md",
        "policy-engine/docs/source-bound.md",
    }
    source_changes = {
        item["path"]: set(item["change_kinds"]) for item in report["changed_source_paths"]
    }
    assert source_changes == {
        "policy-engine/src/pkg/changed.py": {"content_changed"},
        "policy-engine/src/pkg/added.py": {"added"},
        "policy-engine/src/pkg/deleted.py": {"removed"},
    }
    source_bound = next(
        item for item in report["pages"] if item["path"] == "policy-engine/docs/source-bound.md"
    )
    assert source_bound["classification"] == "supported"
    assert source_bound["source_pin_present"] is False
    assert source_bound["source_snapshot_present"] is True
    readme = next(item for item in report["pages"] if item["path"] == "README.md")
    assert readme["classification"] == "supported"
    assert readme["source_pin_present"] is True
    partial = next(
        item for item in report["pages"] if item["path"] == "policy-engine/docs/partial-binding.md"
    )
    assert partial["classification"] == "unsupported"
    partial_queue = next(item for item in report["review_queue"] if item["doc"] == partial["path"])
    assert partial_queue["coverage"] == "partial_for_declared_patterns"
    source_queue = next(
        item
        for item in report["review_queue"]
        if item["doc"] == "policy-engine/docs/source-bound.md"
    )
    assert source_queue["coverage"] == "complete_for_declared_patterns"


def test_doc_only_change_is_listed_as_document_change_not_source_impact(
    impact_repo: tuple[Path, str, str],
) -> None:
    root, _initial_base, base = impact_repo
    guide = root / "policy-engine" / "docs" / "source-bound.md"
    guide.write_text(
        guide.read_text(encoding="utf-8") + "Editorial clarification.\n", encoding="utf-8"
    )
    head = _commit(root, "documentation-only edit")

    result = _run_cli(root, base, head)

    assert result.returncode == 2
    report = _report(result)
    assert report["changed_source_paths"] == []
    assert report["review_queue"] == []
    assert report["summary"]["changed_markdown_path_count"] == 1
    page = next(
        item for item in report["pages"] if item["path"] == "policy-engine/docs/source-bound.md"
    )
    assert page["document_changed"] is True


def test_zero_queue_with_unmapped_pages_remains_unrun(
    impact_repo: tuple[Path, str, str],
) -> None:
    root, _initial_base, head = impact_repo

    result = _run_cli(root, head, head)

    assert result.returncode == 2
    report = _report(result)
    assert report["review_queue"] == []
    assert (
        report["comparison"]["impact_status_within_declared_bindings"]
        == "NO_DECLARED_SOURCE_IMPACT"
    )
    assert report["status"] == "UNRUN"
    assert report["coverage"]["status"] == "PARTIAL"
    assert report["coverage"]["declared_binding_scan"]["status"] == "PARTIAL"
    assert report["coverage"]["unmapped_page_count"] > 0


def test_complete_declared_scan_keeps_overall_documentation_coverage_partial(
    impact_repo: tuple[Path, str, str],
) -> None:
    root, _base, _head = impact_repo
    docs = root / "policy-engine" / "docs"
    for name in (
        "snapshot-only.md",
        "unsupported-directory.md",
        "unsupported-brace.md",
        "partial-binding.md",
        "product-namespace.md",
    ):
        page = docs / name
        page.write_text(
            f"# {name}\n\nSource of truth: `src/**/*.py`\n",
            encoding="utf-8",
        )
    head = _commit(root, "complete fixture declarations")

    result = _run_cli(root, head, head)

    assert result.returncode == 0
    report = _report(result)
    assert report["status"] == "NO_DECLARED_SOURCE_IMPACT"
    assert report["coverage"]["status"] == "PARTIAL"
    assert report["coverage"]["declared_binding_scan"]["status"] == "COMPLETE"
    assert report["coverage"]["declared_binding_scan"]["denominator"] == 7


def test_snapshot_marker_does_not_replace_source_path_binding(
    impact_repo: tuple[Path, str, str],
) -> None:
    root, base, _head = impact_repo
    guide = root / "policy-engine" / "docs" / "source-bound.md"
    guide.write_text(
        "# Source-bound reference\n\nSource snapshot: `not-a-resolvable-commit`\n",
        encoding="utf-8",
    )
    head = _commit(root, "remove source owner paths but retain snapshot marker")

    result = _run_cli(root, base, head)

    assert result.returncode == 2
    report = _report(result)
    page = next(
        item for item in report["pages"] if item["path"] == "policy-engine/docs/source-bound.md"
    )
    assert page["classification"] == "unmapped"
    assert page["source_snapshot_present"] is True
    assert page["patterns"] == []
    assert "policy-engine/docs/source-bound.md" not in {
        item["doc"] for item in report["review_queue"]
    }
    assert report["status"] == "UNRUN"


@pytest.mark.parametrize(
    "continuation",
    [("  `src/pkg/changed.py`",), ("> `src/pkg/changed.py`",)],
    ids=("indented", "quoted"),
)
def test_source_continuation_paths_are_queued_as_one_field(
    impact_repo: tuple[Path, str, str], continuation: tuple[str, ...]
) -> None:
    root, base, _head = impact_repo
    guide = root / "policy-engine" / "docs" / "source-bound.md"
    guide.write_text(
        "# Continued source declaration\n\n"
        "Source of truth: `src/pkg/__init__.py`\n"
        f"{continuation[0]}\n",
        encoding="utf-8",
    )
    head = _commit(root, "add a continued source declaration")

    result = _run_cli(root, base, head)

    assert result.returncode == 2
    report = _report(result)
    page = next(
        item for item in report["pages"] if item["path"] == "policy-engine/docs/source-bound.md"
    )
    assert page["classification"] == "supported"
    assert page["source_of_truth_field_count"] == 1
    assert [item["status"] for item in page["patterns"]] == ["supported", "supported"]
    queue = next(
        item
        for item in report["review_queue"]
        if item["doc"] == "policy-engine/docs/source-bound.md"
    )
    changed = next(
        item
        for item in report["changed_source_paths"]
        if item["path"] == "policy-engine/src/pkg/changed.py"
    )
    assert changed["id"] in queue["changed_source_ids"]


def test_duplicate_source_of_truth_fields_remain_unsupported(
    impact_repo: tuple[Path, str, str],
) -> None:
    root, base, _head = impact_repo
    guide = root / "policy-engine" / "docs" / "source-bound.md"
    guide.write_text(
        "# Duplicate source declarations\n\n"
        "Source of truth: `src/pkg/__init__.py`\n"
        "Source of truth: `src/pkg/changed.py`\n",
        encoding="utf-8",
    )
    head = _commit(root, "duplicate actual source declarations")

    result = _run_cli(root, base, head)

    assert result.returncode == 2
    report = _report(result)
    page = next(
        item for item in report["pages"] if item["path"] == "policy-engine/docs/source-bound.md"
    )
    assert page["classification"] == "unsupported"
    assert page["source_of_truth_field_count"] == 2


def test_unreadable_markdown_keeps_partial_queue_and_returns_unrun(
    impact_repo: tuple[Path, str, str],
) -> None:
    root, base, _head = impact_repo
    invalid = root / "policy-engine" / "docs" / "invalid-utf8.md"
    invalid.write_bytes(b"# Invalid\n\xff\n")
    head = _commit(root, "add unreadable Markdown")

    result = _run_cli(root, base, head)

    assert result.returncode == 2
    report = _report(result)
    assert report["status"] == "UNRUN"
    assert report["coverage"]["read_unrun_page_count"] == 1
    page = next(
        item for item in report["pages"] if item["path"] == "policy-engine/docs/invalid-utf8.md"
    )
    assert page["classification"] == "read_unrun"
    assert page["read"]["status"] == "PASS"
    assert "not UTF-8" in page["reason"]
    assert report["review_queue"]


def test_missing_base_ref_cannot_be_reported_as_zero_impact(
    impact_repo: tuple[Path, str, str],
) -> None:
    root, _base, head = impact_repo

    result = _run_cli(root, "missing-base-ref", head)

    assert result.returncode == 2
    report = _report(result)
    assert report["status"] == "UNRUN"
    assert report["coverage"]["status"] == "UNRUN"
    assert report["inputs"]["base"]["status"] == "UNRUN"
    assert report["summary"]["tracked_markdown_count"] is None
    assert report["review_queue"] == []


def test_missing_markdown_blob_is_reported_as_read_unrun(
    impact_repo: tuple[Path, str, str],
) -> None:
    root, base, head = impact_repo
    blob = _git(root, "rev-parse", f"{head}:policy-engine/docs/source-bound.md")
    object_path = root / ".git" / "objects" / blob[:2] / blob[2:]
    object_path.unlink()

    result = _run_cli(root, base, head)

    assert result.returncode == 2
    report = _report(result)
    page = next(
        item for item in report["pages"] if item["path"] == "policy-engine/docs/source-bound.md"
    )
    assert page["classification"] == "read_unrun"
    assert page["read"]["status"] == "UNRUN"
    assert report["coverage"]["read_unrun_page_count"] == 1
    assert report["review_queue"]


def test_replace_refs_do_not_change_immutable_tree_impact(
    impact_repo: tuple[Path, str, str],
) -> None:
    root, base, head = impact_repo
    _git(root, "replace", base, head)

    result = _run_cli(root, base, head)

    assert result.returncode == 2
    report = _report(result)
    assert report["comparison"]["changed_repository_path_count"] > 0
    assert report["review_queue"]
    assert "disabled" in report["git_read_policy"]["replacement_refs"]


def test_mode_only_change_is_queued_as_a_source_change(
    impact_repo: tuple[Path, str, str],
) -> None:
    root, _base, base = impact_repo
    mode_path = "policy-engine/src/pkg/changed.py"
    _git(root, "add", "-A")
    _git(root, "update-index", "--chmod=+x", mode_path)
    _git(root, "commit", "-m", "change declared source mode")
    head = _git(root, "rev-parse", "HEAD")

    result = _run_cli(root, base, head)

    assert result.returncode == 2
    report = _report(result)
    change = next(
        item
        for item in report["changed_source_paths"]
        if item["path"] == "policy-engine/src/pkg/changed.py"
    )
    assert change["change_kinds"] == ["mode_changed"]
    assert report["review_queue"]


def test_output_file_contains_full_receipt_and_stdout_stays_compact(
    impact_repo: tuple[Path, str, str], tmp_path: Path
) -> None:
    root, base, head = impact_repo
    output = tmp_path / "impact-receipt.json"

    result = _run_cli(root, base, head, "--output", str(output))

    assert result.returncode == 2
    summary = json.loads(result.stdout)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert summary["status"] == "UNRUN"
    assert summary["receipt_path"] == str(output)
    assert "pages" not in summary
    assert len(report["pages"]) == report["summary"]["tracked_markdown_count"]
    assert report["review_queue"]


def test_text_stdout_is_compact_and_discloses_scope_and_read_counts(
    impact_repo: tuple[Path, str, str],
) -> None:
    root, base, head = impact_repo

    result = _run_cli(root, base, head, "--format", "text", write_receipt=False)

    assert result.returncode == 2
    assert "Tracked Markdown: 7" in result.stdout
    assert "Successful Markdown reads: 7" in result.stdout
    assert "Review pages requiring human review: 4" in result.stdout
    assert "human review required" in result.stdout
    assert "policy-engine/docs/snapshot-only.md" not in result.stdout
    assert "pattern=`src/**/*.py`" not in result.stdout


def test_non_utf8_git_paths_keep_byte_identity_through_impact_queue(
    impact_repo: tuple[Path, str, str],
) -> None:
    root, base, _head = impact_repo
    raw_doc = b"policy-engine/docs/raw-\xff.md"
    raw_source = b"policy-engine/src/pkg/raw-\xff.py"
    doc_blob = _git_bytes(
        root,
        "hash-object",
        "-w",
        "--stdin",
        input_bytes=b"# Byte path page\n\nSource of truth: `src/**/*.py`\n",
    ).strip()
    source_blob = _git_bytes(
        root, "hash-object", "-w", "--stdin", input_bytes=b"value = 1\n"
    ).strip()
    index_records = (
        b"100644 " + doc_blob + b"\t" + raw_doc + b"\0"
        b"100644 " + source_blob + b"\t" + raw_source + b"\0"
    )
    _git_bytes(root, "update-index", "-z", "--index-info", input_bytes=index_records)
    tree = _git(root, "write-tree")
    head = _git(root, "commit-tree", tree, "-p", base, "-m", "add raw byte paths")

    result = _run_cli(root, base, head)

    assert result.returncode == 2
    report = _report(result)
    expected_doc = base64.b64encode(raw_doc).decode("ascii")
    expected_source = base64.b64encode(raw_source).decode("ascii")
    page = next(item for item in report["pages"] if item.get("path_bytes_base64") == expected_doc)
    assert page["classification"] == "supported"
    source = next(
        item
        for item in report["changed_source_paths"]
        if item.get("path_bytes_base64") == expected_source
    )
    queue = next(
        item for item in report["review_queue"] if item.get("doc_path_bytes_base64") == expected_doc
    )
    assert source["id"] in queue["changed_source_ids"]


def test_receipt_refuses_to_overwrite_tracked_comparison_input(
    impact_repo: tuple[Path, str, str],
) -> None:
    root, base, head = impact_repo
    tracked_output = root / "README.md"
    original = tracked_output.read_bytes()

    result = _run_cli(root, base, head, "--output", str(tracked_output))

    assert result.returncode == 2
    summary = json.loads(result.stdout)
    assert summary["status"] == "UNRUN"
    assert summary["output_write"]["status"] == "UNRUN"
    assert tracked_output.read_bytes() == original


def test_receipt_refuses_to_overwrite_path_tracked_only_at_base(
    impact_repo: tuple[Path, str, str],
) -> None:
    root, base, head = impact_repo
    deleted_at_head = root / "policy-engine/src/pkg/deleted.py"

    result = _run_cli(root, base, head, "--output", str(deleted_at_head))

    assert result.returncode == 2
    summary = json.loads(result.stdout)
    assert summary["output_write"]["status"] == "UNRUN"
    assert not deleted_at_head.exists()


def test_receipt_refuses_missing_path_present_only_in_current_index(
    impact_repo: tuple[Path, str, str],
) -> None:
    root, base, head = impact_repo
    indexed_output = root / "policy-engine/uncommitted-output.json"
    indexed_output.write_text("staged input\n", encoding="utf-8")
    _git(root, "add", "policy-engine/uncommitted-output.json")
    indexed_output.unlink()

    result = _run_cli(root, base, head, "--output", str(indexed_output))

    assert result.returncode == 2
    summary = json.loads(result.stdout)
    assert summary["output_write"]["status"] == "UNRUN"
    assert "current Git index" in summary["output_write"]["reason"]
    assert not indexed_output.exists()
