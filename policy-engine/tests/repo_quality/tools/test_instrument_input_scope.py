"""Prove unavailable inputs cannot produce clean docs or directory verdicts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tools.quality.validation import check_docs_accuracy, directory_health


def _docs(root: Path, config: str = "nav:\n  - index.md\n") -> None:
    (root / "docs").mkdir()
    (root / "docs/index.md").write_text("# Index\n", encoding="utf-8")
    (root / "mkdocs.yml").write_text("site_name: Demo\n" + config, encoding="utf-8")


def test_docs_without_yaml_reports_unrun(tmp_path: Path, monkeypatch, capsys) -> None:
    _docs(tmp_path)
    monkeypatch.setattr(check_docs_accuracy, "yaml", None)

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 2
    output = capsys.readouterr().out
    assert "UNRUN" in output
    assert "PyYAML" in output
    assert "Not measured:" in output


@pytest.mark.parametrize("config", ["[not: valid", "site_name: No publication scope\n"])
def test_docs_invalid_publication_scope_is_unrun(tmp_path: Path, capsys, config: str) -> None:
    _docs(tmp_path, config)

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 2
    assert "UNRUN" in capsys.readouterr().out


def test_docs_clean_output_names_unmeasured_semantics(tmp_path: Path, capsys) -> None:
    _docs(tmp_path)

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "passed" in output
    assert "Not measured:" in output
    assert "prose truth" in output
    assert "unpublished" in output


def test_docs_command_receipt_discloses_absent_generated_reference_candidates(
    tmp_path: Path, capsys
) -> None:
    _docs(tmp_path)

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    receipt = json.loads(
        output.split("Input receipt JSON:\n", 1)[1].split("\nDocs accuracy report", 1)[0]
    )
    expected = {path.as_posix() for path in check_docs_accuracy.GENERATED_REFERENCE_ALLOWLIST}

    candidates = receipt["generated_reference_allowlist"]
    assert {entry["path"] for entry in candidates} == expected
    assert {entry["path"] for entry in candidates if entry["status"] == "absent"} == expected
    assert any(
        item.startswith(
            "Generated-reference allowlist completeness is unestablished for absent candidates"
        )
        for item in receipt["unresolved_by_construction"]
    )
    assert "presence of generated-reference allowlist entries absent from the repository" in output

    included_paths = {entry["path"] for entry in receipt["included_file_manifest"]}
    assert not expected.intersection(included_paths)
    absence_probes = {
        entry["path"]
        for entry in receipt["explicit_file_reads"]["inputs"]
        if entry["operation"] == "is_file" and entry["status"] == "absent"
    }
    assert expected <= absence_probes
    assert "- violations: 0" in output


def test_docs_existing_unpublished_target_is_a_real_failure(tmp_path: Path, capsys) -> None:
    _docs(tmp_path)
    (tmp_path / "mkdocs.yml").write_text(
        "site_name: Demo\nnav: [index.md]\nexclude_docs: |\n  internal.md\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/index.md").write_text("[Unpublished](internal.md)\n", encoding="utf-8")
    (tmp_path / "docs/internal.md").write_text("# Internal\n", encoding="utf-8")

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert "FAILED" in output
    assert "published" in output


def test_docs_command_resolves_actual_mkdocs_membership_not_path_segments(
    tmp_path: Path, capsys
) -> None:
    _docs(tmp_path)
    (tmp_path / "docs/reference/frontend").mkdir(parents=True)
    (tmp_path / "docs/reference/frontend/workspace.md").write_text(
        "# Frontend workspace\n\nOwner: docs\n\nSource of truth: frontend docs\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/unlisted.md").write_text(
        "# MkDocs included, absent from nav\n", encoding="utf-8"
    )
    (tmp_path / "docs/index.md").write_text(
        "[Frontend](reference/frontend/workspace.md) and [Unlisted](unlisted.md).\n",
        encoding="utf-8",
    )

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "docs/reference/frontend/workspace.md" in output
    assert "docs/unlisted.md" in output
    assert "actual MkDocs included files" in output


def test_docs_command_rejects_nav_page_excluded_by_mkdocs_defaults(tmp_path: Path, capsys) -> None:
    _docs(tmp_path, "nav: [index.md, .hidden.md]\n")
    (tmp_path / "docs/.hidden.md").write_text("# Hidden\n", encoding="utf-8")

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert "nav entry `.hidden.md` is not included by actual MkDocs file selection" in output


def test_docs_command_accepts_actual_mkdocs_negated_exclusion(tmp_path: Path, capsys) -> None:
    _docs(
        tmp_path,
        "nav: [index.md, private/published.md]\n"
        "exclude_docs: |\n  private/**\n  !private/published.md\n",
    )
    (tmp_path / "docs/private").mkdir()
    (tmp_path / "docs/private/published.md").write_text("# Published\n", encoding="utf-8")

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert '"path":"docs/private/published.md"' in output


def test_docs_command_rejects_reference_style_links_to_excluded_pages(
    tmp_path: Path, capsys
) -> None:
    _docs(tmp_path, "nav: [index.md]\nexclude_docs: |\n  private.md\n")
    (tmp_path / "docs/private.md").write_text("# Private\n", encoding="utf-8")
    (tmp_path / "docs/index.md").write_text(
        "[Private page][PRIVATE   PAGE]\n\n[private page]: private.md\n",
        encoding="utf-8",
    )

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert "unpublished or excluded page `private.md`" in output


def test_docs_command_rejects_reference_style_links_outside_docs(tmp_path: Path, capsys) -> None:
    _docs(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src/outside.md").write_text("# Outside docs\n", encoding="utf-8")
    (tmp_path / "docs/index.md").write_text(
        "[Source][outside]\n\n[outside]: ../src/outside.md\n", encoding="utf-8"
    )

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert "outside the published docs surface" in output


def test_docs_command_receipt_binds_scanned_page_content_and_missing_target(
    tmp_path: Path, capsys
) -> None:
    _docs(tmp_path)
    target = tmp_path / "docs/target.md"
    target.write_text("# Version one\n", encoding="utf-8")
    (tmp_path / "docs/index.md").write_text("[Target](target.md)\n", encoding="utf-8")

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 0
    first_output = capsys.readouterr().out
    assert '"path":"docs/target.md"' in first_output
    first_receipt = json.loads(
        first_output.split("Input receipt JSON:\n", 1)[1].split("\nDocs accuracy report", 1)[0]
    )
    first_digest = next(
        item["text_sha256"]
        for item in first_receipt["explicit_file_reads"]["inputs"]
        if item["path"] == "docs/target.md" and item["operation"] == "read_text"
    )

    target.write_text("# Version two\n", encoding="utf-8")
    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 0
    second_output = capsys.readouterr().out
    assert first_output != second_output
    assert '"text_sha256"' in second_output
    second_receipt = json.loads(
        second_output.split("Input receipt JSON:\n", 1)[1].split("\nDocs accuracy report", 1)[0]
    )
    second_digest = next(
        item["text_sha256"]
        for item in second_receipt["explicit_file_reads"]["inputs"]
        if item["path"] == "docs/target.md" and item["operation"] == "read_text"
    )
    assert first_digest != second_digest

    target.unlink()
    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 1
    missing_output = capsys.readouterr().out
    assert "relative docs link `target.md` does not resolve" in missing_output
    assert '"path":"docs/target.md"' in missing_output
    assert '"status":"absent"' in missing_output


def test_docs_command_is_unrun_for_unreadable_included_markdown(tmp_path: Path, capsys) -> None:
    _docs(tmp_path)
    (tmp_path / "docs/index.md").write_bytes(b"\xff\xfe")

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 2
    output = capsys.readouterr().out
    assert "UNRUN" in output
    assert '"path":"docs/index.md"' in output
    assert '"status":"unreadable"' in output


def test_docs_command_is_unrun_for_multiline_link_destination(tmp_path: Path, capsys) -> None:
    _docs(tmp_path)
    (tmp_path / "docs/index.md").write_text("[Target](\nmissing.md\n)\n", encoding="utf-8")

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 2
    output = capsys.readouterr().out
    assert "UNRUN" in output
    assert "unsupported multiline Markdown link destination/title" in output


def test_markdown_link_collector_handles_nested_escaped_code_and_reference_variants() -> None:
    text = (
        "[inline [nested]](target_(nested).md)\n"
        "[multiline label with\nsecond line](multi-line.md)\n"
        "`[code](missing.md)` and \\[escaped](missing.md) and [valid](valid.md)\n"
        "[Named][MiXeD   Label] [Collapsed][] [shortcut]\n"
        "```markdown\n[code-block](missing-in-fence.md)\n[hidden]: not-a-reference.md\n```\n"
        "    [indented-code](missing-indented.md)\n"
        "\n[MiXeD Label]: one.md\n[Collapsed]: two.md\n[shortcut]: three.md\n"
    )

    assert check_docs_accuracy.markdown_link_targets(text) == [
        (1, "target_(nested).md"),
        (2, "multi-line.md"),
        (4, "valid.md"),
        (5, "one.md"),
        (5, "two.md"),
        (5, "three.md"),
    ]


@pytest.mark.parametrize(
    "config",
    [
        "nav: [index.md, 123]\n",
        "nav: [{Section: [index.md, null]}]\n",
        "nav: [index.md]\nnot_in_nav: [123]\n",
        "nav: [index.md]\nexclude_docs: {invalid: shape}\n",
    ],
)
def test_docs_partially_malformed_scope_is_unrun(tmp_path: Path, capsys, config: str) -> None:
    _docs(tmp_path, config)

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 2
    assert "UNRUN" in capsys.readouterr().out


def test_docs_asset_link_forms_remain_explicitly_unmeasured(tmp_path: Path, capsys) -> None:
    _docs(tmp_path)
    (tmp_path / "docs/index.md").write_text(
        ".github/workflows/absent.yaml\n[Asset](missing.svg)\n![Image](missing.png)\n",
        encoding="utf-8",
    )

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    for omitted in ("raw HTML links", "image/asset existence", ".yaml workflows"):
        assert omitted in output


def test_directory_missing_contract_is_unrun(tmp_path: Path, capsys) -> None:
    assert directory_health.main(["--repo-root", str(tmp_path)]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "UNRUN"
    assert payload["complete_verdict"] is False
    assert payload["finding_coverage"] == "partial"
    assert "Not measured:" in payload["measurement"]["omission"]


def test_directory_git_failure_is_not_an_empty_inventory(tmp_path: Path) -> None:
    with pytest.raises(subprocess.CalledProcessError):
        list(directory_health._tracked_files(tmp_path))
