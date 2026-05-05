#!/usr/bin/env python3
"""Validate Playwright flaky/quarantine tags against the shared quarantine registry."""

from __future__ import annotations

import argparse
import re
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from tools.lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
DEFAULT_DASHBOARD_ROOT = REPO_ROOT / "frontend" / "runtime-dashboard"
DEFAULT_QUARANTINE_PATH = REPO_ROOT / "tests" / "quarantine.toml"
TEST_CALL_START = re.compile(
    r"\btest(?:\.(?:only|skip|fixme|fail|slow))?\(\s*([\"'`])",
    re.MULTILINE,
)
QUARANTINE_TAGS = ("@flaky", "@quarantine")


@dataclass(frozen=True)
class PlaywrightTaggedTest:
    spec_path: Path
    title: str

    @property
    def normalized_path(self) -> str:
        return self.spec_path.as_posix()


@dataclass(frozen=True)
class QuarantineEntry:
    runner: str
    selector: str
    owner: str
    expires_on: date
    reason: str
    reentry_criteria: str


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ensure Playwright flaky/quarantine tags are backed by tests/quarantine.toml.",
    )
    parser.add_argument("--dashboard-root", type=Path, default=DEFAULT_DASHBOARD_ROOT)
    parser.add_argument("--quarantine", type=Path, default=DEFAULT_QUARANTINE_PATH)
    return parser.parse_args()


def _decode_string_literal(source: str, start: int, quote: str) -> tuple[str, int]:
    cursor = start
    chunks: list[str] = []

    while cursor < len(source):
        char = source[cursor]
        if char == "\\":
            cursor += 1
            if cursor >= len(source):
                break
            escaped = source[cursor]
            escapes = {"n": "\n", "r": "\r", "t": "\t"}
            chunks.append(escapes.get(escaped, escaped))
            cursor += 1
            continue
        if char == quote:
            return "".join(chunks), cursor + 1
        chunks.append(char)
        cursor += 1

    raise ValueError("unterminated Playwright test title string literal")


def _iter_test_titles(spec_path: Path) -> list[str]:
    source = spec_path.read_text(encoding="utf-8")
    titles: list[str] = []
    for match in TEST_CALL_START.finditer(source):
        quote = match.group(1)
        title, _ = _decode_string_literal(source, match.end(), quote)
        titles.append(title)
    return titles


def _collect_tagged_tests(dashboard_root: Path) -> list[PlaywrightTaggedTest]:
    tagged_tests: list[PlaywrightTaggedTest] = []
    for spec_path in sorted((dashboard_root / "e2e").rglob("*.spec.ts*")):
        if spec_path.suffix not in {".ts", ".tsx"}:
            continue
        for title in _iter_test_titles(spec_path):
            if any(tag in title for tag in QUARANTINE_TAGS):
                tagged_tests.append(
                    PlaywrightTaggedTest(
                        spec_path=spec_path.relative_to(dashboard_root),
                        title=title,
                    )
                )
    return tagged_tests


def _load_playwright_entries(quarantine_path: Path) -> list[QuarantineEntry]:
    if not quarantine_path.exists():
        return []

    payload = tomllib.loads(quarantine_path.read_text("utf-8"))
    entries: list[QuarantineEntry] = []
    for raw_entry in payload.get("case", []):
        entry = QuarantineEntry(
            runner=str(raw_entry["runner"]),
            selector=str(raw_entry["selector"]),
            owner=str(raw_entry["owner"]),
            expires_on=date.fromisoformat(str(raw_entry["expires_on"])),
            reason=str(raw_entry["reason"]),
            reentry_criteria=str(raw_entry["reentry_criteria"]),
        )
        if entry.runner == "playwright":
            entries.append(entry)
    return entries


def _render_test_reference(testcase: PlaywrightTaggedTest) -> str:
    return f"{testcase.normalized_path}::{testcase.title}"


def _validate_registry(
    tagged_tests: list[PlaywrightTaggedTest],
    entries: list[QuarantineEntry],
) -> list[str]:
    errors: list[str] = []

    by_title: dict[str, list[PlaywrightTaggedTest]] = {}
    for testcase in tagged_tests:
        by_title.setdefault(testcase.title, []).append(testcase)

    duplicate_titles = {title: cases for title, cases in by_title.items() if len(cases) > 1}
    for title, cases in sorted(duplicate_titles.items()):
        references = ", ".join(case.normalized_path for case in cases)
        errors.append(
            "Playwright quarantine selectors must be unique exact test titles; "
            f"duplicate title `{title}` appears in {references}."
        )

    entry_by_selector: dict[str, QuarantineEntry] = {}
    for entry in entries:
        if entry.selector in entry_by_selector:
            errors.append(
                "Duplicate Playwright quarantine selector "
                f"`{entry.selector}` in tests/quarantine.toml."
            )
        entry_by_selector[entry.selector] = entry

    for testcase in tagged_tests:
        if testcase.title not in entry_by_selector:
            errors.append(
                "Missing Playwright quarantine registry entry for "
                f"`{_render_test_reference(testcase)}`."
            )

    known_titles = set(by_title)
    for entry in entries:
        if entry.selector not in known_titles:
            errors.append(
                "Playwright quarantine selector "
                f"`{entry.selector}` does not match any tagged Playwright test title."
            )

    return errors


def main() -> int:
    args = _parse_args()
    dashboard_root = args.dashboard_root.resolve()
    quarantine_path = args.quarantine.resolve()
    tagged_tests = _collect_tagged_tests(dashboard_root)
    entries = _load_playwright_entries(quarantine_path)
    errors = _validate_registry(tagged_tests, entries)

    if errors:
        print("Playwright quarantine policy check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        "Playwright quarantine policy check passed "
        f"({len(tagged_tests)} tagged test(s), {len(entries)} registry entries)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
