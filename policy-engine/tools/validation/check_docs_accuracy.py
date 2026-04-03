#!/usr/bin/env python3
"""Validate published docs against current repository reality.

The checker intentionally focuses on lightweight, high-signal accuracy failures:

* placeholder repository URLs such as ``<repo-url>``;
* references to removed or nonexistent GitHub Actions workflows;
* local filesystem links that would break on the published docs site;
* relative Markdown links that no longer resolve;
* absolute docs-site URLs that disagree with ``mkdocs.yml:site_url``.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

PLACEHOLDER_RE = re.compile(r"<repo-url>")
WORKFLOW_PATH_RE = re.compile(r"(?:\.github/workflows|actions/workflows)/([A-Za-z0-9_.-]+\.yml)\b")
URL_RE = re.compile(r"https?://[^\s)>'\"]+")
INLINE_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
LOCAL_FILESYSTEM_RE = re.compile(r"^(?:file://|/Users/|/home/|/tmp/)")
STALE_WORKFLOW_NAMES = {
    "arch.yml",
    "arch-freeze.yml",
    "perf.yml",
    "causal-phases.yml",
    "replay.yml",
}


@dataclass(frozen=True)
class Violation:
    """Represent one docs-accuracy failure with file and line context."""

    file_path: Path
    lineno: int
    message: str


def find_workspace_root(repo_root: Path) -> Path:
    """Return the nearest parent that owns the monorepo `.github/workflows` directory."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        completed = None
    if completed is not None:
        git_root = Path(completed.stdout.strip())
        if (git_root / ".github" / "workflows").is_dir():
            return git_root

    fallback: Path | None = None
    for candidate in (repo_root, *repo_root.parents):
        if (candidate / ".github" / "workflows").is_dir():
            fallback = candidate
    return fallback or repo_root


def published_markdown_files(repo_root: Path) -> list[Path]:
    """Collect README plus published docs pages, excluding archive/planning content."""
    files: list[Path] = []
    for name in ("README.md", "CONTRIBUTING.md"):
        path = repo_root / name
        if path.exists():
            files.append(path)

    docs_root = repo_root / "docs"
    if not docs_root.exists():
        return files

    for path in sorted(docs_root.rglob("*.md")):
        relative = path.relative_to(repo_root)
        if "archive" in relative.parts or "site" in relative.parts:
            continue
        if path.name == "DOCUMENTATION_SOTA_PLAN.md":
            continue
        files.append(path)
    return files


def parse_site_url(mkdocs_path: Path) -> str | None:
    """Read `site_url` from `mkdocs.yml` without extra YAML dependencies."""
    if not mkdocs_path.exists():
        return None
    for line in mkdocs_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("site_url:"):
            return line.split(":", 1)[1].strip()
    return None


def actual_workflow_names(workspace_root: Path) -> set[str]:
    """List real GitHub workflow filenames present in the monorepo root."""
    workflows_dir = workspace_root / ".github" / "workflows"
    if not workflows_dir.exists():
        return set()
    return {path.name for path in workflows_dir.glob("*.yml")}


def normalize_link_target(target: str) -> str:
    """Drop anchors and optional titles from an inline Markdown link target."""
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    if " " in target and not target.startswith(("http://", "https://")):
        target = target.split(" ", 1)[0]
    return target.split("#", 1)[0]


def resolve_relative_link(file_path: Path, target: str) -> bool:
    """Return whether a relative Markdown link points to an existing file/page."""
    if not target:
        return True
    resolved = (file_path.parent / target).resolve()
    candidates = [resolved]
    if target.endswith("/"):
        candidates.append((file_path.parent / target / "index.md").resolve())
    elif resolved.is_dir():
        candidates.append((resolved / "index.md").resolve())
    for candidate in candidates:
        if candidate.exists():
            return True
    return False


def scan_file(
    file_path: Path,
    *,
    site_url: str | None,
    workflow_names: set[str],
) -> list[Violation]:
    """Scan one published Markdown file for accuracy violations."""
    violations: list[Violation] = []
    site_url_value = site_url.rstrip("/") + "/" if site_url else None
    site_url_parts = urlparse(site_url_value) if site_url_value else None

    for lineno, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), start=1):
        if PLACEHOLDER_RE.search(line):
            violations.append(Violation(file_path, lineno, "placeholder `<repo-url>` must be replaced"))

        for stale_name in STALE_WORKFLOW_NAMES:
            if stale_name in line:
                violations.append(
                    Violation(
                        file_path,
                        lineno,
                        f"legacy workflow reference `{stale_name}` no longer matches repo reality",
                    )
                )

        for match in WORKFLOW_PATH_RE.finditer(line):
            workflow_name = match.group(1)
            if workflow_name not in workflow_names:
                violations.append(
                    Violation(
                        file_path,
                        lineno,
                        f"workflow reference `{workflow_name}` does not exist under `.github/workflows/`",
                    )
                )

        for url in URL_RE.findall(line):
            if site_url_parts is None:
                continue
            parsed = urlparse(url)
            if parsed.netloc != site_url_parts.netloc:
                continue
            expected_prefix = site_url_parts.path.rstrip("/") + "/"
            actual_path = parsed.path.rstrip("/") + ("/" if parsed.path else "")
            if expected_prefix and not actual_path.startswith(expected_prefix):
                violations.append(
                    Violation(
                        file_path,
                        lineno,
                        f"docs URL `{url}` disagrees with mkdocs site_url `{site_url_value}`",
                    )
                )

        for link_target in INLINE_LINK_RE.findall(line):
            target = normalize_link_target(link_target)
            if not target or target.startswith(("#", "mailto:")):
                continue
            if LOCAL_FILESYSTEM_RE.match(target):
                violations.append(
                    Violation(
                        file_path,
                        lineno,
                        f"local filesystem link `{target}` is not publishable",
                    )
                )
                continue
            if "://" in target or target.startswith("/"):
                continue
            if target.endswith(".md") or target.endswith("/"):
                if not resolve_relative_link(file_path, target):
                    violations.append(
                        Violation(
                            file_path,
                            lineno,
                            f"relative docs link `{target}` does not resolve",
                        )
                    )

    return violations


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for docs-accuracy validation."""
    parser = argparse.ArgumentParser(description="Check docs accuracy against current repository reality.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root containing README.md, CONTRIBUTING.md, docs/, and mkdocs.yml.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the accuracy checks and return a CI-friendly exit code."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    workspace_root = find_workspace_root(repo_root)
    site_url = parse_site_url(repo_root / "mkdocs.yml")
    workflow_names = actual_workflow_names(workspace_root)

    violations: list[Violation] = []
    for file_path in published_markdown_files(repo_root):
        violations.extend(
            scan_file(
                file_path,
                site_url=site_url,
                workflow_names=workflow_names,
            )
        )

    if violations:
        print("Docs accuracy report")
        print(f"- violations: {len(violations)}")
        for violation in violations:
            try:
                relative = violation.file_path.relative_to(repo_root)
            except ValueError:
                relative = violation.file_path
            print(f"- {relative}:{violation.lineno}: {violation.message}")
        return 1

    print("Docs accuracy report")
    print("- violations: 0")
    print(f"- checked files: {len(published_markdown_files(repo_root))}")
    print(f"- site_url: {site_url or 'missing'}")
    print(f"- workflow inventory: {', '.join(sorted(workflow_names)) or 'none found'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
