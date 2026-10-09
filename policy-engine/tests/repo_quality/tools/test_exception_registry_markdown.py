from __future__ import annotations

import datetime as dt
import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest

from tools.devx.architecture import guardrails
from tools.quality.lint import compare_baseline


@pytest.mark.parametrize(
    "parser",
    [compare_baseline._parse_registry_ids, guardrails._parse_registry_ids],
    ids=["import-freeze", "architecture-guardrails"],
)
def test_registry_parsers_ignore_empty_and_alignment_rows(
    tmp_path: Path,
    parser: Callable[[Path], set[str]],
) -> None:
    registry = tmp_path / "exceptions.md"
    registry.write_text(
        "\n".join(
            [
                "| id | owner | reason |",
                "| :--- | ---: | :---: |",
                "| ---------------- | --------------- | ---------------- |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert parser(registry) == set()


@pytest.mark.parametrize(
    "parser",
    [compare_baseline._parse_registry_ids, guardrails._parse_registry_ids],
    ids=["import-freeze", "architecture-guardrails"],
)
def test_registry_parsers_preserve_valid_ids_with_pipe_cells(
    tmp_path: Path,
    parser: Callable[[Path], set[str]],
) -> None:
    registry = tmp_path / "exceptions.md"
    registry.write_text(
        "\n".join(
            [
                "| id | owner | reason |",
                "| --- | --- | --- |",
                "| `E-EXAMPLE-1` | team-tools | `left|right` |",
                r"| E-EXAMPLE-2 | team-tools | left\|right |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert parser(registry) == {"E-EXAMPLE-1", "E-EXAMPLE-2"}


def test_import_freeze_consumer_rejects_exception_missing_from_real_registry(
    tmp_path: Path,
) -> None:
    exceptions = tmp_path / "exceptions.toml"
    registry = Path(__file__).resolve().parents[3] / "architecture/imports/exceptions.md"
    expires = dt.date.today() + dt.timedelta(days=14)
    exceptions.write_text(
        textwrap.dedent(
            f"""
            [[exception]]
            id = "E-FAKE-UNREGISTERED"
            owner = "team-tools"
            reason = "negative control for registry membership"
            expires = "{expires.isoformat()}"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    assert compare_baseline._parse_registry_ids(registry) == set()
    assert guardrails._parse_registry_ids(guardrails.DEFAULT_EXCEPTION_REGISTRY) == set()
    findings = compare_baseline._validate_exceptions(
        exceptions,
        registry,
        max_expiry_days=90,
    )

    assert any(
        "E-FAKE-UNREGISTERED" in finding.message and "missing in registry" in finding.message
        for finding in findings
    )


def test_guardrails_consumer_rejects_exception_missing_from_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exceptions = tmp_path / "guardrails.toml"
    registry = tmp_path / "guardrail_exceptions_registry.md"
    expires = dt.date.today() + dt.timedelta(days=14)
    monkeypatch.setattr(guardrails, "REPO_ROOT", tmp_path)
    exceptions.write_text(
        textwrap.dedent(
            f"""
            [[exception]]
            id = "arch-fake-unregistered"
            check = "deep_import"
            owner = "team-tools"
            reason = "negative control for registry membership"
            expires = "{expires.isoformat()}"
            subject_glob = "*"
            detail_glob = "*"
            source_module_glob = "polisyos.ir.*"
            target_module_glob = "polisyos.fabric.*"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    registry.write_text(
        "| id | owner | reason |\n| :--- | ---: | :---: |\n",
        encoding="utf-8",
    )

    violations = guardrails._validate_guardrail_exceptions(
        exceptions,
        registry,
        max_expiry_days=90,
    )

    assert any(
        "arch-fake-unregistered" in violation and "missing from" in violation
        for violation in violations
    )
