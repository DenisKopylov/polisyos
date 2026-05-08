#!/usr/bin/env python3
"""Validate the fail-closed docs freshness baseline without running repo-wide gates."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import io
import re
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from tools.lib.imports import repo_root_from
from tools.quality.validation import check_docs_accuracy

if TYPE_CHECKING:
    from collections.abc import Sequence

REPO_ROOT = repo_root_from(__file__)
BASELINE_PATH = Path("architecture/exceptions/docs_freshness.toml")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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


def _extract_violation_count(output: str) -> int:
    match = re.search(r"^- violations:\s+(\d+)$", output, flags=re.MULTILINE)
    if match is None:
        return -1
    return int(match.group(1))


def _run_docs_accuracy(repo_root: Path) -> tuple[int, str]:
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exit_code = check_docs_accuracy.main(["--repo-root", str(repo_root)])
    return exit_code, stdout.getvalue()


def check_baseline(repo_root: Path) -> list[str]:
    baseline = _load_baseline(repo_root)
    findings: list[str] = []

    if baseline.get("mode") != "fail_closed_baseline":
        findings.append("docs freshness mode is not fail_closed_baseline")

    expires = dt.date.fromisoformat(str(baseline.get("expires", "")))
    if expires < dt.date.today():
        findings.append("docs freshness exception baseline expired")

    expected_count = int(baseline.get("expected_violation_count", -1))
    expected_digest = str(baseline.get("baseline_sha256", "")).strip()
    if expected_count < 0:
        findings.append("expected_violation_count must be non-negative")
    if not SHA256_RE.fullmatch(expected_digest):
        findings.append("docs freshness baseline hash is not sha256")

    exit_code, output = _run_docs_accuracy(repo_root)
    observed_count = _extract_violation_count(output)
    observed_digest = hashlib.sha256(output.encode("utf-8")).hexdigest()

    if exit_code == 0:
        if expected_count not in {0, observed_count}:
            findings.append(
                "docs accuracy is clean but baseline still expects "
                f"{expected_count} violation(s)"
            )
        return findings

    if observed_count != expected_count:
        findings.append(
            f"docs freshness violation count changed: expected {expected_count}, "
            f"observed {observed_count}"
        )
    if observed_digest != expected_digest:
        findings.append(
            "docs freshness baseline hash changed: "
            f"expected {expected_digest}, observed {observed_digest}"
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
