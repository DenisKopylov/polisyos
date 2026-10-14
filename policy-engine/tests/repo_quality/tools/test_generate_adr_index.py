from __future__ import annotations

import json
import re
import subprocess
import tomllib
from typing import TYPE_CHECKING

import pytest

from polisyos.common.markdown import split_markdown_table_row
from tools.quality.validation import generate_adr_index

if TYPE_CHECKING:
    from pathlib import Path


def test_phase6_5_stable_topics_cover_required_navigation_surfaces() -> None:
    assert generate_adr_index.STABLE_TOPICS == (
        "repository-structure",
        "observation",
        "security",
        "runtime-state",
        "schemas",
        "testing",
        "release",
        "frontend",
        "product-domain",
    )


def test_phase6_5_by_topic_is_rendered_from_index_toml(tmp_path: Path) -> None:
    index = tmp_path / "index.toml"
    index.write_text(
        "\n".join(
            (
                "[adr_index]",
                "schema_version = 1",
                'generated_on = "source-controlled"',
                'source = "docs/adr"',
                "",
                "[[adr]]",
                'id = "0001"',
                'title = "CAS Signing"',
                'status = "accepted"',
                'topic = "security"',
                'package = "repository"',
                'path = "docs/adr/0001-cas-signing.md"',
                "supersedes = []",
                "superseded_by = []",
                "related = []",
                "",
                "[[adr]]",
                'id = "0002"',
                'title = "Runtime Audit Trail"',
                'status = "accepted"',
                'topic = "runtime-state"',
                'package = "polisyos.runtime"',
                'path = "docs/adr/0002-runtime-audit-trail.md"',
                "supersedes = []",
                "superseded_by = []",
                'related = ["0001"]',
            )
        )
        + "\n",
        encoding="utf-8",
    )

    rendered = generate_adr_index.render_by_topic(generate_adr_index.load_index_entries(index))

    assert "### security" in rendered
    assert "### runtime-state" in rendered
    expected_security_row = (
        "| [0001](0001-cas-signing.md) | `accepted` | `repository` | CAS Signing | - |"
    )
    expected_runtime_row = (
        "| [0002](0002-runtime-audit-trail.md) | `accepted` | `polisyos.runtime` | "
        "Runtime Audit Trail | 0001 |"
    )
    assert expected_security_row in rendered
    assert expected_runtime_row in rendered


def test_phase6_5_index_entries_require_topic_classification(tmp_path: Path) -> None:
    index = tmp_path / "index.toml"
    index.write_text(
        "\n".join(
            (
                "[adr_index]",
                "schema_version = 1",
                'generated_on = "source-controlled"',
                'source = "docs/adr"',
                "",
                "[[adr]]",
                'id = "0001"',
                'title = "Unclassified ADR"',
                'status = "proposed"',
                'package = "repository"',
                'path = "docs/adr/0001-unclassified.md"',
                "supersedes = []",
                "superseded_by = []",
                "related = []",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing `topic`"):
        generate_adr_index.load_index_entries(index)


def test_phase6_5_new_adr_files_require_an_index_topic_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adr_root = tmp_path / "docs" / "adr"
    adr_root.mkdir(parents=True)
    (adr_root / "0001-new-decision.md").write_text(
        "\n".join(
            (
                "# ADR-0001: New Decision",
                "",
                "## Status",
                "",
                "Proposed",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    index = adr_root / "index.toml"
    index.write_text(
        "\n".join(
            (
                "[adr_index]",
                "schema_version = 1",
                'generated_on = "source-controlled"',
                'source = "docs/adr"',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(generate_adr_index, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(generate_adr_index, "ADR_DIR", adr_root)

    with pytest.raises(ValueError, match=r"missing from docs/adr/index\.toml"):
        generate_adr_index._entries(index)


def test_phase6_5_by_topic_is_fresh_against_index_toml() -> None:
    rendered = generate_adr_index.render_by_topic(
        generate_adr_index.load_index_entries(generate_adr_index.DEFAULT_TOML)
    )

    assert generate_adr_index.DEFAULT_BY_TOPIC.read_text(encoding="utf-8") == rendered


def test_rendered_adr_tables_keep_literal_pipe_titles_in_one_cell() -> None:
    entries, _ = generate_adr_index._entries(generate_adr_index.DEFAULT_TOML)
    indexed_entries = {
        entry.id: entry
        for entry in generate_adr_index.load_index_entries(generate_adr_index.DEFAULT_TOML)
    }
    rendered_toml_entries = tomllib.loads(generate_adr_index.render_toml(entries))["adr"]
    rendered_toml_titles = {entry["id"]: entry["title"] for entry in rendered_toml_entries}
    pipe_title_entries = [entry for entry in entries if "|" in entry.title]
    assert pipe_title_entries

    rendered_index = generate_adr_index.render_index(entries)
    rendered_by_topic = generate_adr_index.render_by_topic(entries)
    for entry in pipe_title_entries:
        assert indexed_entries[entry.id].title == rendered_toml_titles[entry.id] == entry.title
        expected_title = entry.title.replace("|", r"\|")
        for rendered, expected_columns, title_column in (
            (rendered_index, 6, 4),
            (rendered_by_topic, 5, 3),
        ):
            row = next(
                split_markdown_table_row(line)
                for line in rendered.splitlines()
                if line.startswith("|")
                and split_markdown_table_row(line)[0].strip().startswith(f"[{entry.id}](")
            )
            assert len(row) == expected_columns
            assert re.sub(r"\\([\\|])", r"\1", row[title_column].strip()) == entry.title
            assert row[title_column].strip() == expected_title


def test_adr_link_escapes_pipe_in_table_label_and_destination() -> None:
    entry = generate_adr_index.AdrEntry(
        id="ADR|0001",
        title="Sample",
        status="proposed",
        topic="schemas",
        package="repository",
        path="docs/adr/0001-sample|case.md",
        supersedes=(),
        superseded_by=(),
        related=(),
    )

    link_cell, title_cell = split_markdown_table_row(
        f"| {generate_adr_index._link(entry)} | Sample |"
    )

    assert link_cell.strip() == r"[ADR\|0001](0001-sample%7Ccase.md)"
    assert re.sub(r"\\([\\|])", r"\1", link_cell.strip().split("]", 1)[0] + "]") == "[ADR|0001]"
    assert title_cell.strip() == "Sample"


def _entries_from_documents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    documents: list[tuple[str, str, str]],
) -> dict[str, generate_adr_index.AdrEntry]:
    adr_root = tmp_path / "docs" / "adr"
    adr_root.mkdir(parents=True)
    index_lines = [
        "[adr_index]",
        "schema_version = 1",
        'generated_on = "source-controlled"',
        'source = "docs/adr"',
    ]

    for adr_id, slug, body in documents:
        filename = f"{adr_id}-{slug}.md"
        (adr_root / filename).write_text(
            f"# ADR-{adr_id}: {slug.replace('-', ' ').title()}\n\n{body.strip()}\n",
            encoding="utf-8",
        )
        index_lines.extend(
            (
                "",
                "[[adr]]",
                f'id = "{adr_id}"',
                f'title = "{slug.replace("-", " ").title()}"',
                'status = "proposed"',
                'topic = "schemas"',
                'package = "repository"',
                f'path = "docs/adr/{filename}"',
                "supersedes = []",
                "superseded_by = []",
                "related = []",
            )
        )

    index = adr_root / "index.toml"
    index.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(generate_adr_index, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(generate_adr_index, "ADR_DIR", adr_root)
    entries, _ = generate_adr_index._entries(index)
    return {entry.id: entry for entry in entries}


def test_entries_keep_superseded_by_direction_when_body_says_replaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entries = _entries_from_documents(
        tmp_path,
        monkeypatch,
        [
            (
                "0001",
                "historical",
                "## Status\n\nSuperseded by ADR-0002\n\n"
                "The successor formula that replaces this approach is ADR-0002.",
            ),
            ("0002", "successor", "## Status\n\nProposed"),
        ],
    )

    assert entries["0001"].status == "superseded"
    assert entries["0001"].supersedes == ()
    assert entries["0001"].superseded_by == ("0002",)
    assert entries["0002"].superseded_by == ()


def test_entries_read_explicit_supersedes_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entries = _entries_from_documents(
        tmp_path,
        monkeypatch,
        [
            (
                "0001",
                "replacement",
                "## Status\n\nAccepted\n\n- Supersedes: ADR-0002 (prior),\n  ADR-0003 (older).",
            ),
            ("0002", "prior", "## Status\n\nAccepted"),
            ("0003", "older", "## Status\n\nAccepted"),
        ],
    )

    assert entries["0001"].supersedes == ("0002", "0003")
    assert entries["0001"].superseded_by == ()


def test_entries_read_explicit_relation_label_variants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entries = _entries_from_documents(
        tmp_path,
        monkeypatch,
        [
            (
                "0001",
                "current",
                "## Status\n\nAccepted\n\n## Related Decisions\n\n"
                "- Extends [ADR-0002](0002-prior.md).\n"
                "- Related to [ADR-0003](0003-prior.md).\n\n"
                "- Binds under a ratification. Related: ADR-0004.",
            ),
            ("0002", "prior", "## Status\n\nAccepted"),
            ("0003", "prior", "## Status\n\nAccepted"),
            ("0004", "prior", "## Status\n\nAccepted"),
        ],
    )

    assert entries["0001"].related == ("0002", "0003", "0004")


def test_entries_do_not_infer_relations_from_prose_without_a_relation_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entries = _entries_from_documents(
        tmp_path,
        monkeypatch,
        [
            (
                "0001",
                "historical",
                "## Status\n\nSuperseded\n\n"
                "The successor formula replaces this approach in ADR-0002.",
            ),
            ("0002", "successor", "## Status\n\nProposed"),
        ],
    )

    assert entries["0001"].status == "superseded"
    assert entries["0001"].supersedes == ()
    assert entries["0001"].superseded_by == ()
    assert entries["0001"].related == ()


def test_entries_preserve_supported_status_forms_and_unknown_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entries = _entries_from_documents(
        tmp_path,
        monkeypatch,
        [
            ("0001", "heading", "## Status\n\nAccepted"),
            ("0002", "russian-field", "- **Статус**: Accepted"),
            ("0003", "list-field", "- Status: Completed"),
            ("0004", "inline-field", "Status: Approved"),
            ("0005", "missing-field", "## Decision\n\nA decision without a status."),
            ("0006", "unrecognized-field", "## Status\n\nAwaiting review"),
            ("0007", "deprecated-field", "**Status:** Deprecated"),
        ],
    )

    assert {adr_id: entry.status for adr_id, entry in entries.items()} == {
        "0001": "accepted",
        "0002": "accepted",
        "0003": "completed",
        "0004": "approved",
        "0005": "unknown",
        "0006": "unknown",
        "0007": "deprecated",
    }


def _generator_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    adr_root = tmp_path / "docs" / "adr"
    adr_root.mkdir(parents=True)
    document = adr_root / "0001-sample-policy.md"
    document.write_text(
        "# ADR-0001: Sample Policy\n\n## Status\n\nProposed\n",
        encoding="utf-8",
    )
    (adr_root / "README.md").write_text("# ADR routing\n", encoding="utf-8")
    index = adr_root / "index.toml"
    index.write_text(
        "\n".join(
            (
                "[adr_index]",
                "schema_version = 1",
                'generated_on = "source-controlled"',
                'source = "docs/adr"',
                "",
                "[[adr]]",
                'id = "0001"',
                'title = "Sample Policy"',
                'status = "proposed"',
                'topic = "schemas"',
                'package = "repository"',
                'path = "docs/adr/0001-sample-policy.md"',
                "supersedes = []",
                "superseded_by = []",
                "related = []",
                "",
            )
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        [
            "git",
            "add",
            "docs/adr/0001-sample-policy.md",
            "docs/adr/README.md",
            "docs/adr/index.toml",
        ],
        cwd=tmp_path,
        check=True,
    )
    monkeypatch.setattr(generate_adr_index, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(generate_adr_index, "ADR_DIR", adr_root)
    monkeypatch.setattr(generate_adr_index, "DEFAULT_TOML", index)
    monkeypatch.setattr(generate_adr_index, "DEFAULT_INDEX", adr_root / "index.md")
    monkeypatch.setattr(generate_adr_index, "DEFAULT_BY_TOPIC", adr_root / "by-topic.md")
    monkeypatch.setattr(
        generate_adr_index,
        "DEFAULT_STALE_REPORT",
        tmp_path / "docs" / "archive" / "reports" / "ADR_STALE_LINK_REPORT.md",
    )
    return document, index


def _receipt_from_stdout(capsys: pytest.CaptureFixture[str]) -> tuple[str, dict[str, object]]:
    output = capsys.readouterr().out
    receipt_text = output.split("Input receipt JSON:\n", 1)[1]
    return output, json.loads(receipt_text)


def test_main_receipt_reports_tracked_inputs_and_untracked_outside_selector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    document, _ = _generator_repository(tmp_path, monkeypatch)
    outside_selector = tmp_path / "docs" / "adr" / "0002-untracked.md"
    outside_selector.write_text(
        "# ADR-0002: Untracked\n\n## Status\n\nSuperseded by ADR-9999\n",
        encoding="utf-8",
    )

    assert generate_adr_index.main([]) == 0
    writer_output, writer_receipt = _receipt_from_stdout(capsys)
    assert "Input receipt JSON:" in writer_output
    assert writer_receipt["execution_status"] == "COMPLETE"
    assert writer_receipt["selection"]["selected_paths"] == ["docs/adr/0001-sample-policy.md"]
    assert writer_receipt["selection"]["candidate_count"] == 2
    assert writer_receipt["selection"]["excluded_paths"] == ["docs/adr/README.md"]
    assert writer_receipt["selection"]["enumerated_denominator"] >= 3
    assert "not selected" in " ".join(writer_receipt["unresolved_by_construction"])
    assert len(writer_receipt["output_operations"]) == 4
    assert all(item["status"] == "written" for item in writer_receipt["output_operations"])
    read_paths = {
        item["path"]
        for item in writer_receipt["explicit_file_reads"]["inputs"]
        if item.get("operation") == "read_text" and item.get("status") == "read"
    }
    assert "docs/adr/0001-sample-policy.md" in read_paths
    assert "docs/adr/0002-untracked.md" not in read_paths
    stale_report = generate_adr_index.DEFAULT_STALE_REPORT.read_text(encoding="utf-8")
    assert writer_receipt["source_inventory"]["sha256"] in stale_report
    assert "untracked worktree paths are not selected" in stale_report

    assert generate_adr_index.main(["--check"]) == 0
    check_output, check_receipt = _receipt_from_stdout(capsys)
    assert "up to date" in check_output
    assert check_receipt["execution_status"] == "COMPLETE"
    assert check_receipt["output_operations"] == []
    assert outside_selector.exists()
    assert document.exists()


@pytest.mark.parametrize("unavailable", ["unreadable", "absent"])
def test_main_unrun_for_unavailable_selected_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    unavailable: str,
) -> None:
    document, _ = _generator_repository(tmp_path, monkeypatch)
    if unavailable == "unreadable":
        document.write_bytes(b"\xff\xfe")
    else:
        document.unlink()

    assert generate_adr_index.main(["--check"]) == 2
    output, receipt = _receipt_from_stdout(capsys)
    assert output.startswith("UNRUN:")
    assert receipt["execution_status"] == "UNRUN"
    assert receipt["explicit_file_reads"]["complete_verdict"] is False
    source_records = [
        item
        for item in receipt["explicit_file_reads"]["inputs"]
        if item["path"] == "docs/adr/0001-sample-policy.md"
    ]
    if unavailable == "unreadable":
        failed_read = next(item for item in source_records if item["operation"] == "read_text")
        assert failed_read["status"] == "unreadable"
    else:
        missing_probe = next(item for item in source_records if item["operation"] == "is_file")
        assert missing_probe["status"] == "absent"


def test_main_check_binds_changed_source_and_preserves_nonzero_drift_predicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    document, _ = _generator_repository(tmp_path, monkeypatch)
    assert generate_adr_index.main([]) == 0
    _, baseline = _receipt_from_stdout(capsys)

    document.write_text(
        "# ADR-0001: Changed Policy\n\n## Status\n\nProposed\n",
        encoding="utf-8",
    )
    assert generate_adr_index.main(["--check"]) == 1
    output, changed = _receipt_from_stdout(capsys)
    assert "out of date: docs/adr/index.toml" in output
    assert changed["execution_status"] == "COMPLETE"
    assert changed["verdict"] == "drift"
    assert changed["source_inventory"]["sha256"] != baseline["source_inventory"]["sha256"]


def test_main_check_fails_for_tampered_output_while_receipt_markers_remain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _generator_repository(tmp_path, monkeypatch)
    assert generate_adr_index.main([]) == 0
    capsys.readouterr()

    generate_adr_index.DEFAULT_INDEX.write_text("# Tampered output\n", encoding="utf-8")
    assert generate_adr_index.main(["--check"]) == 1
    output, receipt = _receipt_from_stdout(capsys)
    assert "out of date: docs/adr/index.md" in output
    assert receipt["schema_version"] == "adr-index-input-receipt/v1"
    assert receipt["explicit_file_reads"]["complete_verdict"] is True
