#!/usr/bin/env python3
"""Validate the fail-closed docs freshness baseline without running repo-wide gates."""

from __future__ import annotations

import argparse
import contextlib
import io
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from tools.lib.docs_freshness import (
    evaluate_docs_freshness_observation,
    extract_docs_freshness_violation_count,
    validate_docs_freshness_baseline,
)
from tools.lib.imports import repo_root_from
from tools.quality.validation import check_docs_accuracy

if TYPE_CHECKING:
    from collections.abc import Sequence

REPO_ROOT = repo_root_from(__file__)
BASELINE_PATH = Path("architecture/exceptions/docs_freshness.toml")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root containing docs and architecture contracts.",
    )
    return parser


def _load_baseline(repo_root: Path) -> dict[str, object]:
    with (repo_root / BASELINE_PATH).open("rb") as stream:
        return tomllib.load(stream)["docs_freshness_exceptions"]


def _extract_violation_count(output: str) -> int | None:
    """Return a single exact checker count, or ``None`` when it is unknown."""
    return extract_docs_freshness_violation_count(output)


def _run_docs_accuracy(repo_root: Path) -> tuple[int, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = check_docs_accuracy.main(["--repo-root", str(repo_root)])
    return exit_code, stdout.getvalue() + stderr.getvalue()


def check_baseline(repo_root: Path) -> list[str]:
    baseline = _load_baseline(repo_root)
    contract = validate_docs_freshness_baseline(baseline)
    findings = list(contract.findings)
    expected_count = contract.expected_violation_count
    if expected_count is None:
        return findings
    if expected_count > 0 and findings:
        return findings

    exit_code, output = _run_docs_accuracy(repo_root)
    findings.extend(
        evaluate_docs_freshness_observation(
            expected_count=expected_count,
            expected_digest=contract.baseline_sha256,
            returncode=exit_code,
            output=output,
        )
    )
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    findings = check_baseline(repo_root)
    if findings:
        print("Docs freshness baseline FAILED:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("Docs freshness baseline passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
