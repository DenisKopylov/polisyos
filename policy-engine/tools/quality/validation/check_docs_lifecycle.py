#!/usr/bin/env python3
"""Validate the Phase 6.4 documentation lifecycle conversion contract."""

from __future__ import annotations

import argparse
import datetime as dt
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tools.lib.imports import repo_root_from
from tools.quality.validation import check_extension_examples, generate_adr_index

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

REPO_ROOT = repo_root_from(__file__)

AUTHORING_SECTIONS = (
    "## Purpose",
    "## Allowed File Categories",
    "## Public/Private Boundary",
    "## Naming Convention",
    "## Test Location",
    "## Fixture/Data Policy",
    "## Generated File Policy",
    "## Extension Points",
    "## Deprecation And Shim Policy",
)

HIGH_VOLUME_SUBTREE_DOCS: dict[str, tuple[str, ...]] = {
    "docs/adr": ("README.md", "AUTHORING.md", "index.md", "by-topic.md", "index.toml"),
    "docs/archive/reports": ("README.md", "AUTHORING.md", "index.md"),
    "schemas/snapshots/ir": ("README.md", "AUTHORING.md", "index.md"),
    "src/polisyos/foundry/methods/catalog/causal": (
        "README.md",
        "AUTHORING.md",
        "index.md",
    ),
    "src/polisyos/ir/analytics": ("README.md", "AUTHORING.md", "index.md"),
    "src/polisyos/foundry/methods": ("README.md", "AUTHORING.md", "index.md"),
    "src/polisyos/data_forge/domains/legal/batch": (
        "README.md",
        "AUTHORING.md",
        "index.md",
    ),
    "src/polisyos/data_forge/domains/catalog/batch": ("README.md", "AUTHORING.md"),
    "src/polisyos/scientist/agent": ("README.md", "AUTHORING.md", "index.md"),
    "src/polisyos/scientist/search": ("README.md", "AUTHORING.md", "index.md"),
    "src/polisyos/scientist/engine": ("README.md", "AUTHORING.md"),
    "src/polisyos/scientist/orchestration/engine": (
        "README.md",
        "AUTHORING.md",
        "index.md",
    ),
    "src/polisyos/runtime/http/services": ("README.md", "AUTHORING.md"),
    "src/polisyos/fabric/connectors/sources": ("README.md", "AUTHORING.md"),
    "apps/runtime-dashboard/src/shared/ui": ("README.md", "AUTHORING.md", "index.md"),
    "apps/runtime-dashboard/src/api": ("README.md", "AUTHORING.md", "index.md"),
    "apps/runtime-dashboard/src/features": ("README.md", "AUTHORING.md", "index.md"),
    "apps/runtime-dashboard/src/test": ("README.md", "AUTHORING.md"),
    "tests/unit/foundry/methods/catalog/causal": (
        "README.md",
        "AUTHORING.md",
        "index.md",
    ),
    "tests/unit/core/security": ("README.md", "AUTHORING.md"),
    "tests/unit/data_forge": ("README.md", "AUTHORING.md", "index.md"),
    "tests/unit/data_forge/domains/academic/batch": ("README.md", "AUTHORING.md"),
    "tests/unit/data_forge/legal_batch": ("README.md", "AUTHORING.md"),
    "tests/unit/foundry/agent_sim": ("README.md", "AUTHORING.md"),
    "tests/unit/foundry/methods": ("README.md", "AUTHORING.md"),
    "tests/unit/ir/analytics": ("README.md", "AUTHORING.md"),
    "tests/unit/runtime/http": ("README.md", "AUTHORING.md"),
    "tests/unit/scientist/agent": ("README.md", "AUTHORING.md"),
    "tests/unit/scientist/governance": ("README.md", "AUTHORING.md"),
    "tests/unit/scientist/orchestration/engine": ("README.md", "AUTHORING.md"),
    "tests/unit/scientist/search": ("README.md", "AUTHORING.md"),
    "tests/unit/scientist/nodes": ("README.md", "AUTHORING.md", "index.md"),
    "tests/_data": ("README.md", "AUTHORING.md", "index.md"),
    "tests/_golden": ("README.md", "AUTHORING.md"),
    "tests/_helpers": ("README.md", "AUTHORING.md"),
}

NAV_REQUIRED_TOKENS = (
    "ADR Index: adr/index.md",
    "ADRs By Topic: adr/by-topic.md",
    "Authoring Contract: adr/AUTHORING.md",
)
KNOWN_REDIRECT_STUBS = (
    "frontend",
)
REDIRECT_REQUIRED_FIELDS = (
    "owner",
    "target_path",
    "reason",
    "created_date",
    "sunset_date",
    "removal_gate",
)
REDIRECT_COMPATIBILITY_ADR_FIELD = "compatibility_adr"
REDIRECT_MAX_LIFETIME_DAYS = 90
REMOVED_REDIRECT_STUBS = {
    "/".join(("tests", "architecture")): "/".join(
        ("tests", "repo_quality", "architecture")
    ),
}
STALE_DIRECT_REFERENCE_TARGETS = {
    **REMOVED_REDIRECT_STUBS,
    "/".join(("frontend", "runtime-dashboard")): "/".join(
        ("apps", "runtime-dashboard")
    ),
    "/".join(("frontend", "runtime-api-client")): "/".join(
        ("packages", "runtime-api-client")
    ),
}
REFERENCE_SCAN_EXCLUDED_DIRS = frozenset(
    (
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "_build",
        "_cache",
        "__pycache__",
        "node_modules",
    )
)
REFERENCE_SCAN_EXCLUDED_FILENAMES = frozenset(("package-lock.json", "pnpm-lock.yaml"))


@dataclass(frozen=True)
class LifecycleFinding:
    check: str
    path: str
    message: str


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root containing docs/, architecture/, and examples/.",
    )
    return parser


def _load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _repo_path(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _front_matter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    data: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return data
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return {}


def _parse_iso_date(value: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def _public_surface_contract(repo_root: Path) -> Path:
    return repo_root / "architecture" / "public_surface" / "contract.toml"


def _is_redirect_stub(path: Path) -> bool:
    metadata = _front_matter(path)
    if metadata.get("redirect_stub", "").lower() == "true":
        return True
    text = path.read_text(encoding="utf-8").lower()
    relative = path.as_posix()
    if relative.endswith("frontend/README.md"):
        return "legacy handoff path" in text or "active javascript workspaces moved" in text
    return False


def _redirect_stub_directory(relative: str) -> str:
    return f"{relative.removesuffix('/README.md')}/"


def _compatibility_adr_finding(
    repo_root: Path,
    relative: str,
    metadata: dict[str, str],
) -> LifecycleFinding | None:
    adr = metadata.get(REDIRECT_COMPATIBILITY_ADR_FIELD, "").strip()
    if not adr:
        return LifecycleFinding(
            "redirect_stub",
            relative,
            "redirect stub sunset exceeds the 90-day policy without `compatibility_adr`.",
        )
    adr_path = repo_root / adr
    if not adr.startswith("docs/adr/") or not adr_path.is_file():
        return LifecycleFinding(
            "redirect_stub",
            relative,
            "redirect stub `compatibility_adr` must reference an existing ADR.",
        )
    stub_directory = _redirect_stub_directory(relative)
    if stub_directory not in adr_path.read_text(encoding="utf-8"):
        return LifecycleFinding(
            "redirect_stub",
            relative,
            f"redirect stub `compatibility_adr` must declare `{stub_directory}`.",
        )
    return None


def check_adr_index(repo_root: Path) -> list[LifecycleFinding]:
    findings: list[LifecycleFinding] = []
    adr_root = repo_root / "docs" / "adr"
    index_toml = adr_root / "index.toml"
    index_md = adr_root / "index.md"
    by_topic = adr_root / "by-topic.md"
    stale_report = repo_root / "docs" / "archive" / "reports" / "ADR_STALE_LINK_REPORT.md"

    if not index_toml.is_file():
        return [
            LifecycleFinding(
                "adr_index",
                _repo_path(repo_root, index_toml),
                "ADR machine-readable index is missing.",
            )
        ]

    data = _load_toml(index_toml)
    rows = data.get("adr", [])
    if not isinstance(rows, list):
        findings.append(
            LifecycleFinding("adr_index", _repo_path(repo_root, index_toml), "adr rows missing.")
        )
        rows = []

    indexed_paths = {str(row.get("path", "")) for row in rows if isinstance(row, dict)}
    expected_paths = {
        _repo_path(repo_root, path) for path in generate_adr_index._markdown_files()
    }
    for path in sorted(expected_paths - indexed_paths):
        findings.append(LifecycleFinding("adr_index", path, "ADR file is not indexed."))
    for path in sorted(indexed_paths - expected_paths):
        findings.append(
            LifecycleFinding("adr_index", path, "ADR index references a missing ADR file.")
        )

    for row in rows:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path", "docs/adr/index.toml"))
        for field in ("id", "title", "status", "topic", "package"):
            if not str(row.get(field, "")).strip():
                findings.append(
                    LifecycleFinding("adr_index", path, f"ADR row missing `{field}`.")
                )

    entries, stale = generate_adr_index._entries()
    generated_on = str(data.get("adr_index", {}).get("generated_on", "source-controlled"))
    expected_outputs = {
        index_toml: generate_adr_index.render_toml(entries, generated_on=generated_on),
        index_md: generate_adr_index.render_index(entries),
        by_topic: generate_adr_index.render_by_topic(entries),
        stale_report: generate_adr_index.render_stale_report(stale, generated_on=generated_on),
    }
    for path, expected in expected_outputs.items():
        if not path.is_file():
            findings.append(
                LifecycleFinding("adr_index", _repo_path(repo_root, path), "generated file missing.")
            )
            continue
        if path.read_text(encoding="utf-8") != expected:
            findings.append(
                LifecycleFinding(
                    "adr_index",
                    _repo_path(repo_root, path),
                    "generated ADR output is stale; run generate-adr-index.",
                )
            )

    return findings


def check_docs_nav(repo_root: Path) -> list[LifecycleFinding]:
    findings: list[LifecycleFinding] = []
    nav_fragment = repo_root / "architecture" / "tooling" / "mkdocs" / "nav" / "70-adrs.yml"
    generated = repo_root / "architecture" / "tooling" / "mkdocs" / "generated.yml"
    for path in (nav_fragment, generated):
        if not path.is_file():
            findings.append(
                LifecycleFinding("docs_nav", _repo_path(repo_root, path), "MkDocs nav file missing.")
            )
            continue
        text = path.read_text(encoding="utf-8")
        for token in NAV_REQUIRED_TOKENS:
            if token not in text:
                findings.append(
                    LifecycleFinding("docs_nav", _repo_path(repo_root, path), f"missing {token}")
                )
    return findings


def check_active_plans(repo_root: Path) -> list[LifecycleFinding]:
    findings: list[LifecycleFinding] = []
    active_root = repo_root / "docs" / "plans" / "active"
    for path in sorted(active_root.glob("*.md")):
        front_matter = _front_matter(path)
        for field in ("status", "owner"):
            if not front_matter.get(field):
                findings.append(
                    LifecycleFinding(
                        "active_plan_metadata",
                        _repo_path(repo_root, path),
                        f"active plan missing `{field}` front matter.",
                    )
                )
        text = path.read_text(encoding="utf-8").lower()
        if "accepted final closeout" in text:
            findings.append(
                LifecycleFinding(
                    "active_plan_metadata",
                    _repo_path(repo_root, path),
                    "active plan contains accepted final closeout evidence; move it to docs/plans/archive.",
                )
            )
    return findings


def check_redirect_stubs(repo_root: Path) -> list[LifecycleFinding]:
    findings: list[LifecycleFinding] = []
    readmes = {
        repo_root / root / "README.md"
        for root in KNOWN_REDIRECT_STUBS
        if (repo_root / root / "README.md").is_file()
    }
    readmes.update(
        path
        for path in repo_root.rglob("README.md")
        if _front_matter(path).get("redirect_stub", "").lower() == "true"
    )

    for readme in sorted(readmes):
        if not _is_redirect_stub(readme):
            continue
        metadata = _front_matter(readme)
        relative = _repo_path(repo_root, readme)
        if not metadata.get("sunset_date"):
            findings.append(
                LifecycleFinding(
                    "redirect_stub",
                    relative,
                    "redirect stub missing `sunset_date` metadata.",
                )
            )
            continue
        missing_required_field = False
        for field in REDIRECT_REQUIRED_FIELDS:
            if not metadata.get(field):
                findings.append(
                    LifecycleFinding(
                        "redirect_stub",
                        relative,
                        f"redirect stub missing `{field}` metadata.",
                    )
                )
                missing_required_field = True
                break
        if missing_required_field:
            continue
        created_date = _parse_iso_date(metadata.get("created_date", ""))
        sunset_date = _parse_iso_date(metadata.get("sunset_date", ""))
        if created_date is None:
            findings.append(
                LifecycleFinding(
                    "redirect_stub",
                    relative,
                    "redirect stub has invalid `created_date` metadata.",
                )
            )
            continue
        if sunset_date is None:
            findings.append(
                LifecycleFinding(
                    "redirect_stub",
                    relative,
                    "redirect stub has invalid `sunset_date` metadata.",
                )
            )
            continue
        if (sunset_date - created_date).days > REDIRECT_MAX_LIFETIME_DAYS:
            compatibility_finding = _compatibility_adr_finding(repo_root, relative, metadata)
            if compatibility_finding is not None:
                findings.append(compatibility_finding)
    return findings


def _iter_reference_scan_files(repo_root: Path) -> Iterable[Path]:
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(repo_root)
        if any(part in REFERENCE_SCAN_EXCLUDED_DIRS for part in relative.parts):
            continue
        if path.name in REFERENCE_SCAN_EXCLUDED_FILENAMES:
            continue
        yield path


def check_removed_stub_references(repo_root: Path) -> list[LifecycleFinding]:
    findings: list[LifecycleFinding] = []
    seen: set[tuple[str, str, str]] = set()

    def add_reference(relative: str, token: str, target: str) -> None:
        message = f"stale direct reference `{token}`; use `{target}`."
        key = ("removed_stub_reference", relative, message)
        if key in seen:
            return
        seen.add(key)
        findings.append(LifecycleFinding(key[0], relative, message))

    for removed_path, target in REMOVED_REDIRECT_STUBS.items():
        absolute = repo_root / removed_path
        if absolute.exists():
            findings.append(
                LifecycleFinding(
                    "removed_stub_path",
                    removed_path,
                    f"removed redirect stub directory still exists; use `{target}`.",
                )
            )
            if absolute.is_file():
                add_reference(_repo_path(repo_root, absolute), removed_path, target)
            else:
                for path in sorted(absolute.rglob("*")):
                    if path.is_file():
                        add_reference(_repo_path(repo_root, path), removed_path, target)

    for path in _iter_reference_scan_files(repo_root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = _repo_path(repo_root, path)
        for token, target in STALE_DIRECT_REFERENCE_TARGETS.items():
            if token in text:
                add_reference(relative, token, target)

    return findings


def check_archive_reports(repo_root: Path) -> list[LifecycleFinding]:
    findings: list[LifecycleFinding] = []
    legacy_archive_plans = repo_root / "docs" / "archive" / "plans"
    if legacy_archive_plans.exists() and any(legacy_archive_plans.rglob("*")):
        findings.append(
            LifecycleFinding(
                "archive_promotion",
                _repo_path(repo_root, legacy_archive_plans),
                "legacy archive plans must be promoted to docs/plans/archive.",
            )
        )

    for path in (repo_root / "docs" / "archive").rglob("*.py"):
        findings.append(
            LifecycleFinding(
                "archive_promotion",
                _repo_path(repo_root, path),
                "retained archive code belongs under tools/archive.",
            )
        )

    report_readme = repo_root / "docs" / "archive" / "reports" / "README.md"
    report_authoring = repo_root / "docs" / "archive" / "reports" / "AUTHORING.md"
    for path in (report_readme, report_authoring, report_readme.parent / "index.md"):
        if not path.is_file():
            findings.append(
                LifecycleFinding(
                    "archive_promotion",
                    _repo_path(repo_root, path),
                    "archive reports lifecycle document missing.",
                )
            )

    if report_readme.is_file():
        text = report_readme.read_text(encoding="utf-8")
        for token in ("Promotion criteria", "Raw logs", "Benchmark evidence"):
            if token not in text:
                findings.append(
                    LifecycleFinding(
                        "archive_promotion",
                        _repo_path(repo_root, report_readme),
                        f"archive reports README missing `{token}`.",
                    )
                )
    return findings


def check_readme_authoring(repo_root: Path) -> list[LifecycleFinding]:
    findings: list[LifecycleFinding] = []
    for subtree, filenames in HIGH_VOLUME_SUBTREE_DOCS.items():
        root = repo_root / subtree
        if not root.is_dir():
            findings.append(LifecycleFinding("authoring", subtree, "documented subtree missing."))
            continue
        for filename in filenames:
            path = root / filename
            if not path.is_file():
                findings.append(
                    LifecycleFinding("authoring", _repo_path(repo_root, path), "doc missing.")
                )
        authoring = root / "AUTHORING.md"
        if not authoring.is_file():
            continue
        text = authoring.read_text(encoding="utf-8")
        for section in AUTHORING_SECTIONS:
            if section not in text:
                findings.append(
                    LifecycleFinding(
                        "authoring",
                        _repo_path(repo_root, authoring),
                        f"missing section {section}",
                    )
                )

    public_surface = _load_toml(_public_surface_contract(repo_root))
    for package in public_surface.get("package", []):
        if not isinstance(package, dict) or package.get("classification") != "public_stable":
            continue
        readme = repo_root / str(package.get("readme", ""))
        if not readme.is_file():
            findings.append(
                LifecycleFinding(
                    "readme_coverage",
                    _repo_path(repo_root, readme),
                    "public-stable package README missing.",
                )
            )

    budget = _load_toml(repo_root / "architecture" / "module_size_budget.toml")
    for item in budget.get("budget", []):
        if not isinstance(item, dict):
            continue
        path = Path(str(item.get("path", "")))
        if len(path.parts) < 3 or path.parts[:2] != ("src", "polisyos"):
            continue
        readme = repo_root / "src" / "polisyos" / path.parts[2] / "README.md"
        if not readme.is_file():
            findings.append(
                LifecycleFinding(
                    "readme_coverage",
                    _repo_path(repo_root, readme),
                    f"high-complexity package README missing for {path.as_posix()}.",
                )
            )

    return findings


def check_extension_example_structure(repo_root: Path) -> list[LifecycleFinding]:
    return [
        LifecycleFinding("extension_examples", "examples/extensions", message)
        for message in check_extension_examples.validate_pyproject(
            repo_root, check_extension_examples.EXAMPLES
        )
    ]


def run_checks(repo_root: Path) -> list[LifecycleFinding]:
    checks: tuple[Iterable[LifecycleFinding], ...] = (
        check_adr_index(repo_root),
        check_docs_nav(repo_root),
        check_active_plans(repo_root),
        check_redirect_stubs(repo_root),
        check_removed_stub_references(repo_root),
        check_archive_reports(repo_root),
        check_readme_authoring(repo_root),
        check_extension_example_structure(repo_root),
    )
    findings: list[LifecycleFinding] = []
    for result in checks:
        findings.extend(result)
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    findings = run_checks(repo_root)
    if findings:
        print("Docs lifecycle gate FAILED:")
        for finding in findings:
            print(f"- [{finding.check}] {finding.path}: {finding.message}")
        return 1
    print("Docs lifecycle gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
