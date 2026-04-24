#!/usr/bin/env python3
"""Validate published docs against current repository reality.

The checker intentionally focuses on the published MkDocs surface defined by
``mkdocs.yml`` and enforces the D2 reference contract:

* published pages come from ``nav`` and must not be excluded by
  ``exclude_docs``;
* placeholder repository URLs such as ``<repo-url>`` are rejected;
* workflow references must point to workflow files that actually exist under
  ``.github/workflows`` in this repository;
* relative Markdown links from published docs must stay inside the published
  docs surface, or use inline-code / stable external links instead;
* generated reference pages must advertise a canonical regeneration command;
* published manual reference pages must declare ``Owner:`` and
  ``Source of truth:`` metadata.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from tools._lib.imports import repo_root_from

try:
    import yaml
except ImportError:  # pragma: no cover - fallback only used in broken envs.
    yaml = None

PLACEHOLDER_RE = re.compile(r"<repo-url>")
WORKFLOW_PATH_RE = re.compile(r"(?:\.github/workflows|actions/workflows)/([A-Za-z0-9_.-]+\.yml)\b")
URL_RE = re.compile(r"https?://[^\s)>'\"]+")
INLINE_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
LOCAL_FILESYSTEM_RE = re.compile(r"^(?:file://|/Users/|/home/|/tmp/)")
PLANNING_DOC_RE = re.compile(r"(^|/).+(?:_PLAN|_ROADMAP|_REMEDIATION_PLAN)\.md$", re.IGNORECASE)
OWNER_RE = re.compile(r"^Owner:\s+\S+", flags=re.MULTILINE)
SOURCE_OF_TRUTH_RE = re.compile(r"^Source of truth:\s+\S+", flags=re.MULTILINE)
REGENERATION_RE = re.compile(
    r"(?:Regenerate this page with|Canonical regeneration command(?:s)?)(?::|\s)",
    flags=re.IGNORECASE,
)
NON_DOC_SEGMENTS = {
    ".github",
    "benchmarks",
    "frontend",
    "release",
    "schemas",
    "src",
    "tests",
    "tools",
}
GENERATED_REFERENCE_ALLOWLIST = {
    Path("docs/reference/public-surface.md"),
    Path("docs/reference/generated-artifacts.md"),
    Path("docs/reference/tools.md"),
    Path("docs/reference/schemas.md"),
    Path("docs/reference/ir/schema-catalog.md"),
}


@dataclass(frozen=True)
class Violation:
    """Represent one docs-accuracy failure with file and line context."""

    file_path: Path
    lineno: int
    message: str


@dataclass(frozen=True)
class PublishedDocsConfig:
    """Resolved published-docs configuration from ``mkdocs.yml``."""

    site_url: str | None
    published_files: tuple[Path, ...]
    docs_root: Path
    mkdocs_path: Path


def collect_nav_entries(value: Any) -> list[str]:
    """Collect markdown paths from a MkDocs ``nav`` structure."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        results: list[str] = []
        for item in value:
            results.extend(collect_nav_entries(item))
        return results
    if isinstance(value, dict):
        results = []
        for item in value.values():
            results.extend(collect_nav_entries(item))
        return results
    return []


def parse_site_url(mkdocs_path: Path) -> str | None:
    """Read ``site_url`` from ``mkdocs.yml`` without extra assumptions."""
    if not mkdocs_path.exists():
        return None
    for line in mkdocs_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("site_url:"):
            return line.split(":", 1)[1].strip()
    return None


def split_exclude_docs(value: Any) -> list[str]:
    """Normalize the ``exclude_docs`` setting into shell-style patterns."""
    if value is None:
        return []
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def is_excluded_docs_path(relative_to_docs: Path, patterns: list[str]) -> bool:
    """Return whether a docs path matches MkDocs ``exclude_docs`` patterns."""
    candidate = relative_to_docs.as_posix()
    for pattern in patterns:
        if fnmatch.fnmatch(candidate, pattern):
            return True
    return False


def published_docs_config(repo_root: Path) -> tuple[PublishedDocsConfig, list[Violation]]:
    """Resolve the published MkDocs surface from ``mkdocs.yml``."""
    mkdocs_path = repo_root / "mkdocs.yml"
    docs_root = repo_root / "docs"
    violations: list[Violation] = []
    site_url = parse_site_url(mkdocs_path)

    if yaml is None:
        files = tuple(sorted(path.resolve() for path in docs_root.rglob("*.md")))
        return (
            PublishedDocsConfig(
                site_url=site_url,
                published_files=files,
                docs_root=docs_root,
                mkdocs_path=mkdocs_path,
            ),
            violations,
        )

    class MkDocsLoader(yaml.SafeLoader):
        pass

    def _unknown_tag(loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node) -> Any:
        if isinstance(node, yaml.ScalarNode):
            return loader.construct_scalar(node)
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node)
        if isinstance(node, yaml.MappingNode):
            return loader.construct_mapping(node)
        return None

    MkDocsLoader.add_multi_constructor("tag:yaml.org,2002:python/name:", _unknown_tag)
    data = yaml.load(mkdocs_path.read_text(encoding="utf-8"), Loader=MkDocsLoader) or {}
    nav_paths = collect_nav_entries(data.get("nav", []))
    exclude_patterns = split_exclude_docs(data.get("exclude_docs"))
    published: set[Path] = set()

    for nav_entry in nav_paths:
        relative = Path(nav_entry)
        if relative.parts and relative.parts[0] == "archive":
            violations.append(
                Violation(
                    mkdocs_path,
                    1,
                    f"nav entry `{nav_entry}` points into `docs/archive/`; archived content must stay unpublished",
                )
            )
            continue
        if PLANNING_DOC_RE.search(nav_entry):
            violations.append(
                Violation(
                    mkdocs_path,
                    1,
                    f"nav entry `{nav_entry}` is a planning/remediation document; keep planning docs out of the published nav",
                )
            )
            continue
        if is_excluded_docs_path(relative, exclude_patterns):
            violations.append(
                Violation(
                    mkdocs_path,
                    1,
                    f"nav entry `{nav_entry}` is excluded by `exclude_docs`",
                )
            )
            continue
        file_path = (docs_root / relative).resolve()
        if not file_path.exists():
            violations.append(
                Violation(
                    mkdocs_path,
                    1,
                    f"nav entry `{nav_entry}` does not resolve under `docs/`",
                )
            )
            continue
        published.add(file_path)

    for relative in GENERATED_REFERENCE_ALLOWLIST:
        path = (repo_root / relative).resolve()
        if path.exists() and path not in published:
            violations.append(
                Violation(
                    mkdocs_path,
                    1,
                    f"generated reference `{relative.as_posix()}` is not published in `nav`",
                )
            )

    return (
        PublishedDocsConfig(
            site_url=site_url,
            published_files=tuple(sorted(published)),
            docs_root=docs_root,
            mkdocs_path=mkdocs_path,
        ),
        violations,
    )


def actual_workflow_names(repo_root: Path) -> set[str]:
    """List real GitHub workflow filenames present in this repository."""
    roots = {repo_root}
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        completed = None
    if completed is not None:
        roots.add(Path(completed.stdout.strip()))

    names: set[str] = set()
    for root in roots:
        workflows_dir = root / ".github" / "workflows"
        if workflows_dir.exists():
            names.update(path.name for path in workflows_dir.glob("*.yml"))
    return names


def normalize_link_target(target: str) -> str:
    """Drop anchors and optional titles from an inline Markdown link target."""
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    if " " in target and not target.startswith(("http://", "https://")):
        target = target.split(" ", 1)[0]
    return target.split("#", 1)[0]


def looks_like_relative_repo_link(target: str) -> bool:
    """Return whether a relative target obviously points outside published docs."""
    parts = {part for part in PurePosixPath(target).parts if part not in {".", ".."}}
    return bool(parts & NON_DOC_SEGMENTS)


def resolve_relative_candidates(file_path: Path, target: str) -> list[Path]:
    """Build candidate paths for a relative Markdown target."""
    base = (file_path.parent / target).resolve()
    candidates: list[Path] = [base]
    if target.endswith("/") or base.is_dir():
        candidates.append((base / "index.md").resolve())
    elif base.suffix == "":
        candidates.append(base.with_suffix(".md").resolve())
        candidates.append((base / "index.md").resolve())
    return candidates


def first_existing_candidate(file_path: Path, target: str) -> Path | None:
    """Resolve a relative target to the first existing candidate path."""
    for candidate in resolve_relative_candidates(file_path, target):
        if candidate.exists():
            return candidate
    return None


def scan_file(
    file_path: Path,
    *,
    config: PublishedDocsConfig,
    published_files: set[Path],
    workflow_names: set[str],
) -> list[Violation]:
    """Scan one published Markdown file for accuracy violations."""
    violations: list[Violation] = []
    site_url_value = config.site_url.rstrip("/") + "/" if config.site_url else None
    site_url_parts = urlparse(site_url_value) if site_url_value else None
    text = file_path.read_text(encoding="utf-8")

    for lineno, line in enumerate(text.splitlines(), start=1):
        if PLACEHOLDER_RE.search(line):
            violations.append(
                Violation(file_path, lineno, "placeholder `<repo-url>` must be replaced")
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
                        file_path, lineno, f"local filesystem link `{target}` is not publishable"
                    )
                )
                continue
            if "://" in target or target.startswith("/"):
                continue
            if looks_like_relative_repo_link(target):
                violations.append(
                    Violation(
                        file_path,
                        lineno,
                        f"relative repo link `{target}` points outside the published docs surface; use inline code or a stable external URL",
                    )
                )
                continue
            resolved = first_existing_candidate(file_path, target)
            if resolved is None:
                if target.endswith(".md") or target.endswith("/"):
                    violations.append(
                        Violation(
                            file_path,
                            lineno,
                            f"relative docs link `{target}` does not resolve",
                        )
                    )
                continue
            if resolved.suffix.lower() == ".md":
                if not resolved.is_relative_to(config.docs_root.resolve()):
                    violations.append(
                        Violation(
                            file_path,
                            lineno,
                            f"relative repo link `{target}` points outside the published docs surface; use inline code or a stable external URL",
                        )
                    )
                    continue
                if resolved not in published_files:
                    try:
                        unpublished = resolved.relative_to(config.docs_root.resolve()).as_posix()
                    except ValueError:
                        unpublished = target
                    violations.append(
                        Violation(
                            file_path,
                            lineno,
                            f"relative docs link `{target}` points to unpublished or excluded page `{unpublished}`",
                        )
                    )

    repo_relative = file_path.relative_to(config.docs_root.parent)
    if repo_relative in GENERATED_REFERENCE_ALLOWLIST:
        if not REGENERATION_RE.search(text):
            violations.append(
                Violation(
                    file_path,
                    1,
                    "generated reference is missing a canonical regeneration command",
                )
            )
    elif repo_relative.parts[:2] == ("docs", "reference"):
        if not OWNER_RE.search(text):
            violations.append(
                Violation(file_path, 1, "manual reference page is missing `Owner:` metadata")
            )
        if not SOURCE_OF_TRUTH_RE.search(text):
            violations.append(
                Violation(
                    file_path, 1, "manual reference page is missing `Source of truth:` metadata"
                )
            )

    return violations


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for docs-accuracy validation."""
    parser = argparse.ArgumentParser(
        description="Check docs accuracy against current repository reality."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=repo_root_from(__file__),
        help="Repository root containing docs/, mkdocs.yml, and .github/workflows/.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the accuracy checks and return a CI-friendly exit code."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    config, config_violations = published_docs_config(repo_root)
    workflow_names = actual_workflow_names(repo_root)
    published_files = set(config.published_files)

    violations: list[Violation] = list(config_violations)
    for file_path in config.published_files:
        violations.extend(
            scan_file(
                file_path,
                config=config,
                published_files=published_files,
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
    print(f"- checked files: {len(config.published_files)}")
    print(f"- site_url: {config.site_url or 'missing'}")
    print(f"- workflow inventory: {', '.join(sorted(workflow_names)) or 'none found'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
