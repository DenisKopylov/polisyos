from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

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

    with pytest.raises(ValueError, match="missing from docs/adr/index.toml"):
        generate_adr_index._entries(index)


def test_phase6_5_by_topic_is_fresh_against_index_toml() -> None:
    rendered = generate_adr_index.render_by_topic(
        generate_adr_index.load_index_entries(generate_adr_index.DEFAULT_TOML)
    )

    assert generate_adr_index.DEFAULT_BY_TOPIC.read_text(encoding="utf-8") == rendered
