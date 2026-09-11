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
    (root / "mkdocs.yml").write_text(config, encoding="utf-8")


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


def test_docs_existing_unpublished_target_is_a_real_failure(tmp_path: Path, capsys) -> None:
    _docs(tmp_path)
    (tmp_path / "docs/index.md").write_text("[Unpublished](internal.md)\n", encoding="utf-8")
    (tmp_path / "docs/internal.md").write_text("# Internal\n", encoding="utf-8")

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert "FAILED" in output
    assert "published" in output


@pytest.mark.parametrize("config", [
    "nav: [index.md, 123]\n",
    "nav: [{Section: [index.md, null]}]\n",
    "nav: [index.md]\nnot_in_nav: [123]\n",
    "nav: [index.md]\nexclude_docs: {invalid: shape}\n",
])
def test_docs_partially_malformed_scope_is_unrun(tmp_path: Path, capsys, config: str) -> None:
    _docs(tmp_path, config)

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 2
    assert "UNRUN" in capsys.readouterr().out


def test_docs_unsupported_link_forms_are_explicitly_unmeasured(tmp_path: Path, capsys) -> None:
    _docs(tmp_path)
    (tmp_path / "docs/index.md").write_text(
        ".github/workflows/absent.yaml\n[Asset](missing.svg)\n"
        "![Image](missing.png)\n[Reference][missing]\n[missing]: missing.md\n",
        encoding="utf-8",
    )

    assert check_docs_accuracy.main(["--repo-root", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "declared scope only" in output
    for omitted in ("reference-style links", "images", "asset existence", ".yaml workflows"):
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
        directory_health._tracked_files(tmp_path)
