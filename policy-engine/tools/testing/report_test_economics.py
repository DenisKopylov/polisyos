#!/usr/bin/env python3
"""Summarize slow suites and unstable tests from JUnit XML plus quarantine metadata."""
from __future__ import annotations

import argparse
import tomllib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUARANTINE_PATH = REPO_ROOT / "tests" / "quarantine.toml"


@dataclass(frozen=True)
class ReportInput:
    label: str
    path: Path


@dataclass(frozen=True)
class SuiteSummary:
    label: str
    tests: int
    failures: int
    skipped: int
    time_seconds: float


@dataclass(frozen=True)
class TestCaseSummary:
    suite_label: str
    name: str
    time_seconds: float
    status: str


@dataclass(frozen=True)
class QuarantineEntry:
    runner: str
    selector: str
    owner: str
    expires_on: date
    reason: str
    reentry_criteria: str


def _parse_report_argument(raw_value: str) -> ReportInput:
    if "=" not in raw_value:
        raise argparse.ArgumentTypeError(
            "report arguments must look like label=/path/to/report.xml"
        )
    label, raw_path = raw_value.split("=", 1)
    if not label.strip():
        raise argparse.ArgumentTypeError("report label cannot be empty")
    return ReportInput(label=label.strip(), path=Path(raw_path).resolve())


def _iter_suites(root: ElementTree.Element) -> Iterable[ElementTree.Element]:
    if root.tag == "testsuite":
        yield root
        return
    if root.tag == "testsuites":
        yield from root.findall("testsuite")
        return
    raise ValueError(f"Unsupported JUnit root tag: {root.tag}")


def _parse_junit_report(report: ReportInput) -> tuple[list[SuiteSummary], list[TestCaseSummary]]:
    tree = ElementTree.parse(report.path)
    root = tree.getroot()
    suites: list[SuiteSummary] = []
    testcases: list[TestCaseSummary] = []
    total_tests = 0
    total_failures = 0
    total_skipped = 0
    total_time_seconds = 0.0

    for suite in _iter_suites(root):
        tests = int(suite.attrib.get("tests", "0"))
        failures = int(suite.attrib.get("failures", "0")) + int(suite.attrib.get("errors", "0"))
        skipped = int(suite.attrib.get("skipped", "0"))
        time_seconds = float(suite.attrib.get("time", "0") or "0")
        total_tests += tests
        total_failures += failures
        total_skipped += skipped
        total_time_seconds += time_seconds

        for testcase in suite.findall("testcase"):
            classname = testcase.attrib.get("classname", "").strip()
            name = testcase.attrib.get("name", "").strip()
            qualified_name = f"{classname}::{name}" if classname else name
            status = "passed"
            if testcase.find("failure") is not None or testcase.find("error") is not None:
                status = "failed"
            elif testcase.find("skipped") is not None:
                status = "skipped"
            testcases.append(
                TestCaseSummary(
                    suite_label=report.label,
                    name=qualified_name,
                    time_seconds=float(testcase.attrib.get("time", "0") or "0"),
                    status=status,
                )
            )

    suites.append(
        SuiteSummary(
            label=report.label,
            tests=total_tests,
            failures=total_failures,
            skipped=total_skipped,
            time_seconds=total_time_seconds,
        )
    )
    return suites, testcases


def _load_quarantines(path: Path) -> list[QuarantineEntry]:
    if not path.exists():
        return []

    payload = tomllib.loads(path.read_text("utf-8"))
    entries: list[QuarantineEntry] = []
    for raw_entry in payload.get("case", []):
        entries.append(
            QuarantineEntry(
                runner=str(raw_entry["runner"]),
                selector=str(raw_entry["selector"]),
                owner=str(raw_entry["owner"]),
                expires_on=date.fromisoformat(str(raw_entry["expires_on"])),
                reason=str(raw_entry["reason"]),
                reentry_criteria=str(raw_entry["reentry_criteria"]),
            )
        )
    return entries


def _render_suite_table(suites: list[SuiteSummary]) -> list[str]:
    lines = [
        "## Suite Totals",
        "",
        "| suite | tests | failures | skipped | time (s) |",
        "|---|---:|---:|---:|---:|",
    ]
    for suite in sorted(suites, key=lambda item: item.time_seconds, reverse=True):
        lines.append(
            f"| `{suite.label}` | {suite.tests} | {suite.failures} | "
            f"{suite.skipped} | {suite.time_seconds:.2f} |"
        )
    return lines


def _render_slowest_tests(testcases: list[TestCaseSummary], *, top: int) -> list[str]:
    lines = [
        "## Top Slowest Tests",
        "",
        "| seconds | suite | testcase | status |",
        "|---:|---|---|---|",
    ]
    for testcase in sorted(testcases, key=lambda item: item.time_seconds, reverse=True)[:top]:
        lines.append(
            f"| {testcase.time_seconds:.2f} | `{testcase.suite_label}` | "
            f"`{testcase.name}` | {testcase.status} |"
        )
    return lines


def _render_quarantine_section(quarantines: list[QuarantineEntry]) -> list[str]:
    today = date.today()
    active_entries = [entry for entry in quarantines if entry.expires_on >= today]
    expired_entries = [entry for entry in quarantines if entry.expires_on < today]

    lines = ["## Unstable and Quarantined Tests", ""]
    lines.append(f"- Active quarantines: {len(active_entries)}")
    lines.append(f"- Expired quarantines: {len(expired_entries)}")
    lines.append("")

    if not quarantines:
        lines.append("No quarantine entries are registered.")
        return lines

    lines.extend(
        [
            "| runner | selector | owner | expires | reason | re-entry criteria |",
            "|---|---|---|---|---|---|",
        ]
    )
    for entry in sorted(
        quarantines,
        key=lambda item: (item.expires_on, item.runner, item.selector),
    ):
        lines.append(
            "| "
            f"`{entry.runner}` | `{entry.selector}` | `{entry.owner}` | "
            f"{entry.expires_on.isoformat()} | "
            f"{entry.reason} | {entry.reentry_criteria} |"
        )
    return lines


def _render_summary(
    reports: list[ReportInput],
    suites: list[SuiteSummary],
    testcases: list[TestCaseSummary],
    quarantines: list[QuarantineEntry],
    missing_reports: list[ReportInput],
    *,
    top: int,
) -> str:
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    total_tests = sum(suite.tests for suite in suites)
    total_failures = sum(suite.failures for suite in suites)
    total_skipped = sum(suite.skipped for suite in suites)
    total_time = sum(suite.time_seconds for suite in suites)

    lines = [
        "# Test Economics Report",
        "",
        f"Generated at `{generated_at}`.",
        "",
        f"- Reports parsed: {len(reports) - len(missing_reports)} / {len(reports)}",
        f"- Total tests: {total_tests}",
        f"- Total failures/errors: {total_failures}",
        f"- Total skipped: {total_skipped}",
        f"- Aggregate suite time: {total_time:.2f}s",
    ]
    if missing_reports:
        lines.append(
            "- Missing reports: "
            + ", ".join(f"`{report.label}`" for report in missing_reports)
        )
    lines.append("")
    lines.extend(_render_suite_table(suites))
    lines.append("")
    lines.extend(_render_slowest_tests(testcases, top=top))
    lines.append("")
    lines.extend(_render_quarantine_section(quarantines))
    lines.append("")
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a markdown summary from test runner reports."
    )
    parser.add_argument(
        "--report",
        action="append",
        type=_parse_report_argument,
        default=[],
        help="label=/absolute/or/relative/path/to/junit.xml",
    )
    parser.add_argument("--quarantine", type=Path, default=DEFAULT_QUARANTINE_PATH)
    parser.add_argument("--top", type=int, default=15, help="number of slow tests to include")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="write markdown to this file instead of stdout",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="skip missing junit reports instead of failing",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.report:
        raise SystemExit("At least one --report label=path argument is required.")

    suites: list[SuiteSummary] = []
    testcases: list[TestCaseSummary] = []
    missing_reports: list[ReportInput] = []
    for report in args.report:
        if not report.path.exists():
            if args.allow_missing:
                missing_reports.append(report)
                continue
            raise SystemExit(f"JUnit report not found: {report.path}")
        report_suites, report_cases = _parse_junit_report(report)
        suites.extend(report_suites)
        testcases.extend(report_cases)

    summary = _render_summary(
        args.report,
        suites,
        testcases,
        _load_quarantines(args.quarantine.resolve()),
        missing_reports,
        top=args.top,
    )
    if args.output is None:
        print(summary)
        return 0

    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(summary, encoding="utf-8")
    print(f"Wrote summary to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
