#!/usr/bin/env python3
"""Validate published docs against current repository reality.

The checker applies navigation policy from ``nav`` and ``not_in_nav`` while
deriving the scan set from MkDocs' actual ``Files`` collection:

* placeholder repository URLs such as ``<repo-url>`` are rejected;
* workflow references must point to workflow files that actually exist under
  ``.github/workflows`` in this repository;
* inline and reference-style Markdown page links must resolve inside the
  actual MkDocs-included docs surface;
* generated reference pages must advertise a canonical regeneration command;
* published manual reference pages must declare ``Owner:`` and
  ``Source of truth:`` metadata.

The collector uses Python-Markdown's inline processors and supports
single-line inline links, two-line inline labels, full/collapsed/shortcut
reference links, nested link labels and destinations, and escaped/code-span
syntax handled by Python-Markdown. Raw HTML links, images/assets, root-relative
URLs, fragment-anchor existence, unsupported multiline link forms, external URL
availability and rendered deployment remain unresolved by construction. Fenced
and indented code blocks are excluded before link parsing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections import Counter
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig
    from mkdocs.structure.files import Files
from urllib.parse import unquote, urlparse

from tools.lib.fs import measure_file_reads, measured_is_dir, measured_is_file, measured_read_text
from tools.lib.imports import repo_root_from

try:
    import yaml
except ImportError:  # pragma: no cover - fallback only used in broken envs.
    yaml = None

PLACEHOLDER_RE = re.compile(r"<repo-url>")
WORKFLOW_PATH_RE = re.compile(r"(?:\.github/workflows|actions/workflows)/([A-Za-z0-9_.-]+\.yml)\b")
URL_RE = re.compile(r"https?://[^\s)>'\"]+")
LOCAL_FILESYSTEM_RE = re.compile(r"^(?:file://|/Users/|/home/|/tmp/)")
MULTILINE_LINK_HINT_RE = re.compile(
    r"\[[^\]\n]{1,200}\n[^\]\n]{0,200}\][ \t]*(?:\(|\[)"
    r"|\[[^\]\n]{1,200}\][ \t]*\n[ \t]*(?:\(|\[)"
)
PLANNING_DOC_RE = re.compile(r"(^|/).+(?:_PLAN|_ROADMAP|_REMEDIATION_PLAN)\.md$", re.IGNORECASE)
OWNER_RE = re.compile(r"^Owner:\s+\S+", flags=re.MULTILINE)
SOURCE_OF_TRUTH_RE = re.compile(r"^Source of truth:\s+\S+", flags=re.MULTILINE)
REGENERATION_RE = re.compile(
    r"(?:Regenerate this page with|Canonical regeneration command(?:s)?)(?::|\s)",
    flags=re.IGNORECASE,
)
GENERATED_REFERENCE_ALLOWLIST = (
    Path("docs/reference/public-surface.md"),
    Path("docs/reference/generated-artifacts.md"),
    Path("docs/reference/tools.md"),
    Path("docs/reference/schemas.md"),
    Path("docs/reference/ir/schema-catalog.md"),
)
MEASURED = (
    "Measured: navigation policy; actual MkDocs included files; inline and reference-style "
    "Markdown page links (including two-line inline labels); literal .yml workflows; existing "
    "generated-reference publication and regeneration checks; reference metadata."
)
OMISSION = (
    "Not measured: prose truth, runtime behavior, raw HTML links, image/asset existence, "
    "unpublished document contents, root-relative URL targets, fragment-anchor existence, unsupported multiline link forms, "
    "presence of generated-reference allowlist entries absent from the repository, extensionless links with no .md/index.md target, "
    "external URL availability, .yaml workflows, rendered deployment, or hosted CI."
)


@dataclass(frozen=True)
class Violation:
    """Represent one docs-accuracy failure with file and line context."""

    file_path: Path
    lineno: int
    message: str


@dataclass(frozen=True)
class PublishedDocsConfig:
    """Resolved navigation policy and actual MkDocs file selection."""

    site_url: str | None
    nav_files: tuple[Path, ...]
    not_in_nav_files: tuple[Path, ...]
    published_files: tuple[Path, ...]
    docs_root: Path
    mkdocs_path: Path
    exclusion_patterns: tuple[str, ...]
    file_manifest: tuple[dict[str, str], ...]
    selection_summary: dict[str, Any]
    generated_reference_presence: tuple[dict[str, str], ...]

    @property
    def published_markdown_files(self) -> tuple[Path, ...]:
        """Return actual included Markdown pages, excluding assets."""
        return tuple(path for path in self.published_files if path.suffix.lower() == ".md")


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
        for label, item in value.items():
            if not isinstance(label, str):
                raise ValueError("MkDocs nav labels must be strings")
            results.extend(collect_nav_entries(item))
        return results
    raise ValueError(f"MkDocs nav has unsupported entry type: {type(value).__name__}")


def load_mkdocs_data(
    mkdocs_path: Path,
    loader_cls: type[yaml.SafeLoader],
    *,
    seen: frozenset[Path] = frozenset(),
) -> dict[str, Any]:
    """Load MkDocs YAML and merge a single-file ``INHERIT`` chain."""
    resolved_path = mkdocs_path.resolve()
    if resolved_path in seen:
        raise ValueError(f"cyclic MkDocs INHERIT chain at {mkdocs_path}")
    try:
        data = yaml.load(measured_read_text(mkdocs_path), Loader=loader_cls) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"MkDocs YAML unavailable: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("MkDocs configuration must be a mapping")
    inherited_ref = data.get("INHERIT")
    if not inherited_ref:
        return data
    inherited_path = Path(str(inherited_ref))
    if not inherited_path.is_absolute():
        inherited_path = mkdocs_path.parent / inherited_path
    inherited = load_mkdocs_data(
        inherited_path,
        loader_cls,
        seen=seen | frozenset({resolved_path}),
    )
    return {**inherited, **{key: value for key, value in data.items() if key != "INHERIT"}}


def split_exclude_docs(value: Any) -> list[str]:
    """Normalize the ``exclude_docs`` setting into shell-style patterns."""
    if value is None:
        return []
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, list):
        if not all(isinstance(item, str) for item in value):
            raise ValueError("MkDocs publication patterns must contain only strings")
        return [item.strip() for item in value if item.strip()]
    raise ValueError("MkDocs publication patterns must be a string or list of strings")


def _get_files_pruning_excluded_dirs(
    config: MkDocsConfig,
) -> tuple[Files, tuple[str, ...], tuple[dict[str, object], ...], bool]:
    """Build MkDocs files while pruning only directories excluded by its rules.

    MkDocs 1.6.1 applies ``exclude_docs`` after walking every directory. This
    preserves its ``File`` objects and exclusion predicate while avoiding
    traversal of subtrees that cannot contain an included file. Any negated
    rule disables pruning so a descendant cannot be skipped accidentally.
    """
    import mkdocs.structure.files as mkdocs_files

    exclusion = mkdocs_files._default_exclude
    configured_exclusion = config.get("exclude_docs")
    if configured_exclusion is not None:
        exclusion = exclusion + configured_exclusion
    pruning_enabled = all(pattern.include for pattern in exclusion.patterns)

    files: list[Any] = []
    conflicting_files: list[tuple[Any, Any]] = []
    pruned_directories: list[str] = []
    traversed_parent_membership: list[dict[str, object]] = []
    docs_dir = config["docs_dir"]
    for source_dir, dirnames, filenames in os.walk(docs_dir, followlinks=True):
        dirnames.sort()
        relative_dir = os.path.relpath(source_dir, docs_dir)
        if relative_dir == os.curdir:
            relative_dir = ""
        traversed_parent_membership.append(
            {
                "parent": relative_dir or ".",
                "child_directories_before_pruning": list(dirnames),
            }
        )
        if pruning_enabled:
            retained_dirnames: list[str] = []
            for dirname in dirnames:
                relative_path = (Path(relative_dir) / dirname).as_posix()
                if exclusion.match_file(f"{relative_path}/"):
                    pruned_directories.append(relative_path)
                else:
                    retained_dirnames.append(dirname)
            dirnames[:] = retained_dirnames

        filenames.sort(key=mkdocs_files._file_sort_key)
        files_by_dest: dict[str, Any] = {}
        for filename in filenames:
            file = mkdocs_files.File(
                os.path.join(relative_dir, filename),
                docs_dir,
                config["site_dir"],
                config["use_directory_urls"],
            )
            previous_file = files_by_dest.setdefault(file.dest_uri, file)
            if previous_file is not file:
                conflicting_files.append((previous_file, file))
            files.append(file)

    mkdocs_files.set_exclusions(files, config)
    for earlier, later in conflicting_files:
        if later.inclusion.is_included():
            if earlier.inclusion.is_included():
                mkdocs_files.log.warning(
                    "Excluding '%s' from the site because it conflicts with '%s'.",
                    earlier.src_uri,
                    later.src_uri,
                )
            with suppress(ValueError):
                files.remove(earlier)
        else:
            with suppress(ValueError):
                files.remove(later)

    return (
        mkdocs_files.Files(files),
        tuple(pruned_directories),
        tuple(traversed_parent_membership),
        pruning_enabled,
    )


def published_docs_config(repo_root: Path) -> tuple[PublishedDocsConfig, list[Violation]]:
    """Resolve nav policy and MkDocs' actual included source files."""
    mkdocs_path = repo_root / "mkdocs.yml"
    violations: list[Violation] = []

    if yaml is None:
        raise ValueError("PyYAML unavailable: publication membership was not measured")
    measured_read_text(mkdocs_path)
    try:
        from mkdocs.config import load_config

        actual_config = load_config(config_file=str(mkdocs_path))
        docs_root = Path(actual_config["docs_dir"]).resolve()
        docs_root.relative_to(repo_root.resolve())
        (
            all_files,
            pruned_directory_paths,
            traversed_parent_membership,
            pruning_enabled,
        ) = _get_files_pruning_excluded_dirs(actual_config)
    except (ImportError, OSError, ValueError) as exc:
        raise ValueError(
            f"actual MkDocs file selection unavailable: {type(exc).__name__}: {exc}"
        ) from exc
    except Exception as exc:
        # MkDocs reports malformed configuration through its own exception types.
        raise ValueError(
            f"actual MkDocs file selection unavailable: {type(exc).__name__}: {exc}"
        ) from exc

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
    data = load_mkdocs_data(mkdocs_path, MkDocsLoader)
    site_url_value = data.get("site_url")
    site_url = str(actual_config.get("site_url") or site_url_value or "").strip() or None
    nav_paths = collect_nav_entries(data.get("nav", []))
    exclude_patterns = split_exclude_docs(data.get("exclude_docs"))
    not_in_nav_paths = split_exclude_docs(data.get("not_in_nav"))
    if not nav_paths and not not_in_nav_paths:
        raise ValueError("MkDocs publication scope has no nav or not_in_nav entries")

    published: set[Path] = set()
    manifest: list[dict[str, str]] = []
    inclusion_counts: Counter[str] = Counter()
    markdown_count = 0
    included_markdown_count = 0
    for file in all_files:
        inclusion = file.inclusion.name
        included = file.inclusion.is_included()
        inclusion_counts[inclusion] += 1
        markdown_count += int(Path(file.src_uri).suffix.lower() == ".md")
        if not included:
            continue
        source_path = Path(file.abs_src_path).resolve()
        try:
            source_path.relative_to(docs_root)
        except ValueError as exc:
            raise ValueError(
                f"MkDocs file `{file.src_uri}` resolves outside the repository docs root"
            ) from exc
        is_markdown = source_path.suffix.lower() == ".md"
        published.add(source_path)
        included_markdown_count += int(is_markdown)
        manifest.append(
            {
                "path": source_path.relative_to(repo_root.resolve()).as_posix(),
                "type": "markdown" if is_markdown else "asset",
                "inclusion": inclusion,
            }
        )

    declared: set[Path] = set()
    nav_published: set[Path] = set()
    not_in_nav_published: set[Path] = set()

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
        file_path = (docs_root / relative).resolve()
        if not file_path.is_relative_to(docs_root) or not measured_is_file(file_path):
            violations.append(
                Violation(
                    mkdocs_path,
                    1,
                    f"nav entry `{nav_entry}` does not resolve under `docs/`",
                )
            )
            continue
        if file_path not in published:
            violations.append(
                Violation(
                    mkdocs_path,
                    1,
                    f"nav entry `{nav_entry}` is not included by actual MkDocs file selection",
                )
            )
            continue
        declared.add(file_path)
        nav_published.add(file_path)

    for not_in_nav_entry in not_in_nav_paths:
        relative = Path(not_in_nav_entry)
        file_path = (docs_root / relative).resolve()
        if not file_path.is_relative_to(docs_root) or not measured_is_file(file_path):
            violations.append(
                Violation(
                    mkdocs_path,
                    1,
                    f"not_in_nav entry `{not_in_nav_entry}` does not resolve under `docs/`",
                )
            )
            continue
        if file_path not in published:
            violations.append(
                Violation(
                    mkdocs_path,
                    1,
                    f"not_in_nav entry `{not_in_nav_entry}` is not included by actual MkDocs file selection",
                )
            )
            continue
        declared.add(file_path)
        not_in_nav_published.add(file_path)

    generated_reference_presence: list[dict[str, str]] = []
    for relative in GENERATED_REFERENCE_ALLOWLIST:
        path = (repo_root / relative).resolve()
        present = measured_is_file(path)
        generated_reference_presence.append(
            {"path": relative.as_posix(), "status": "present" if present else "absent"}
        )
        if present and path not in declared:
            violations.append(
                Violation(
                    mkdocs_path,
                    1,
                    f"generated reference `{relative.as_posix()}` is not published in `nav`",
                )
            )

    selection_summary: dict[str, Any] = {
        "selector": (
            "mkdocs.config.load_config + MkDocs File/Files/set_exclusions with prewalk pruning; "
            "inclusion.is_included()"
        ),
        "docs_root": docs_root.relative_to(repo_root.resolve()).as_posix(),
        "enumerated_files": len(all_files),
        "enumeration_scope": (
            "files under traversed directories only; matching excluded directories are pruned"
        ),
        "containment_scope": (
            "resolved containment applies to included MkDocs files only; excluded files in "
            "visited parents are not path-resolved by this consumer, and pruned directories "
            "are not traversed"
        ),
        "directory_pruning_enabled": pruning_enabled,
        "pruned_directories": len(pruned_directory_paths),
        "pruned_directory_paths": list(pruned_directory_paths),
        "traversed_parent_membership": list(traversed_parent_membership),
        "included_files": len(published),
        "included_markdown_files": included_markdown_count,
        "enumerated_markdown_files": markdown_count,
        "inclusion_counts": dict(sorted(inclusion_counts.items())),
        "exclude_docs": exclude_patterns,
        "nav_files": len(nav_published),
        "not_in_nav_files": len(not_in_nav_published),
    }

    return (
        PublishedDocsConfig(
            site_url=site_url,
            nav_files=tuple(sorted(nav_published)),
            not_in_nav_files=tuple(sorted(not_in_nav_published)),
            published_files=tuple(sorted(published)),
            docs_root=docs_root,
            mkdocs_path=mkdocs_path,
            exclusion_patterns=tuple(exclude_patterns),
            file_manifest=tuple(manifest),
            selection_summary=selection_summary,
            generated_reference_presence=tuple(generated_reference_presence),
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
    """Convert a local Markdown URL path into a filesystem path."""
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    return unquote(urlparse(target).path)


def resolve_relative_candidates(file_path: Path, target: str) -> list[Path]:
    """Build filesystem candidates for a relative Markdown page target."""
    base = (file_path.parent / target).resolve()
    if target.endswith("/"):
        return [(base / "index.md").resolve()]
    if base.suffix == "":
        return [base.with_suffix(".md").resolve(), (base / "index.md").resolve()]
    return [base]


def _markdown_lines_without_block_code(text: str) -> list[tuple[int, str]]:
    """Keep source lines outside fenced and indented Markdown code blocks."""
    visible: list[tuple[int, str]] = []
    fence_char: str | None = None
    fence_length = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        fence_match = re.match(r"^(?: {0,3}> ?)* {0,3}(`{3,}|~{3,})", line)
        if fence_char is not None:
            closing = re.match(r"^(?: {0,3}> ?)* {0,3}(`+|~+)\s*$", line)
            if (
                closing
                and closing.group(1)[0] == fence_char
                and len(closing.group(1)) >= fence_length
            ):
                fence_char = None
                fence_length = 0
            continue
        if fence_match:
            marker = fence_match.group(1)
            fence_char = marker[0]
            fence_length = len(marker)
            continue
        if line.startswith(("    ", "\t")):
            continue
        visible.append((line_number, line))
    return visible


def _mask_inline_code(text: str) -> str:
    """Blank matched backtick spans while preserving line breaks and offsets."""
    chars = list(text)
    index = 0
    while index < len(text):
        if text[index] != "`":
            index += 1
            continue
        slash_count = 0
        previous = index - 1
        while previous >= 0 and text[previous] == "\\":
            slash_count += 1
            previous -= 1
        if slash_count % 2:
            index += 1
            continue
        run_end = index + 1
        while run_end < len(text) and text[run_end] == "`":
            run_end += 1
        delimiter = text[index:run_end]
        close = text.find(delimiter, run_end)
        if close < 0:
            index = run_end
            continue
        end = close + len(delimiter)
        for position in range(index, end):
            if chars[position] != "\n":
                chars[position] = " "
        index = end
    return "".join(chars)


def markdown_link_targets(text: str) -> list[tuple[int, str]]:
    """Collect supported Markdown link destinations with their source lines."""
    visible_lines = _markdown_lines_without_block_code(text)
    visible_text = "\n".join(line for _, line in visible_lines)
    try:
        import markdown
        from markdown.inlinepatterns import (
            LinkInlineProcessor,
            ReferenceInlineProcessor,
            ShortReferenceInlineProcessor,
        )
    except ImportError as exc:  # pragma: no cover - docs extra is required in CI.
        raise ValueError("Python-Markdown unavailable: Markdown links were not measured") from exc

    link_markdown = markdown.Markdown()
    link_markdown.treeprocessors["inline"].stashed_nodes = {}
    link_parser = LinkInlineProcessor(r"\[", link_markdown)
    code_masked_text = _mask_inline_code(visible_text)
    multiline_spans: list[tuple[int, int, int]] = []
    search_at = 0
    while True:
        start = code_masked_text.find("[", search_at)
        if start < 0:
            break
        search_at = start + 1
        if start and code_masked_text[start - 1] == "!":
            continue
        if start and code_masked_text[start - 1] == "\\":
            continue
        label, after_label, label_closed = link_parser.getText(code_masked_text, start + 1)
        if not label_closed:
            continue
        _href, _title, end, link_closed = link_parser.getLink(code_masked_text, after_label)
        if not link_closed:
            continue
        line_index = code_masked_text[:start].count("\n")
        source_line = visible_lines[line_index][0]
        if "\n" in code_masked_text[after_label:end]:
            raise ValueError(
                f"line {source_line}: unsupported multiline Markdown link destination/title"
            )
        if "\n" in label:
            multiline_spans.append((start, end, source_line))
            search_at = end

    masked_text = list(visible_text)
    for start, end, _line in multiline_spans:
        for position in range(start, end):
            if masked_text[position] != "\n":
                masked_text[position] = " "
    single_line_text = "".join(masked_text)
    multiline_match = MULTILINE_LINK_HINT_RE.search(_mask_inline_code(single_line_text))
    if multiline_match:
        line_index = single_line_text[: multiline_match.start()].count("\n")
        source_line = visible_lines[line_index][0]
        raise ValueError(f"line {source_line}: unsupported multiline Markdown link syntax")

    # Python-Markdown owns reference-label normalization and destination decoding.
    reference_parser = markdown.Markdown()
    reference_parser.convert(visible_text)
    references = dict(reference_parser.references)
    targets: list[tuple[int, str]] = []
    collector = markdown.Markdown()
    priorities = {"link": 160, "reference": 170, "short_reference": 130}

    class RecordingLink(LinkInlineProcessor):
        line_number = 0

        def handleMatch(self, match, data):  # noqa: N802, ANN202 - Python-Markdown override.
            element, start, end = super().handleMatch(match, data)
            if element is not None:
                targets.append((self.line_number, element.get("href", "")))
            return element, start, end

    class RecordingReference(ReferenceInlineProcessor):
        line_number = 0

        def handleMatch(self, match, data):  # noqa: N802, ANN202 - Python-Markdown override.
            element, start, end = super().handleMatch(match, data)
            if element is not None:
                targets.append((self.line_number, element.get("href", "")))
            return element, start, end

    class RecordingShortReference(ShortReferenceInlineProcessor):
        line_number = 0

        def handleMatch(self, match, data):  # noqa: N802, ANN202 - Python-Markdown override.
            element, start, end = super().handleMatch(match, data)
            if element is not None:
                targets.append((self.line_number, element.get("href", "")))
            return element, start, end

    collector.inlinePatterns.register(RecordingLink(r"\[", collector), "link", priorities["link"])
    collector.inlinePatterns.register(
        RecordingReference(r"\[", collector), "reference", priorities["reference"]
    )
    collector.inlinePatterns.register(
        RecordingShortReference(r"\[", collector),
        "short_reference",
        priorities["short_reference"],
    )

    for start, end, line_number in multiline_spans:
        collector.reset()
        collector.references.update(references)
        for name in ("link", "reference", "short_reference"):
            collector.inlinePatterns[name].line_number = line_number
        before = len(targets)
        collector.convert(visible_text[start:end])
        if len(targets) == before:
            raise ValueError(f"line {line_number}: Markdown parser did not resolve multiline link")

    masked_lines = single_line_text.split("\n") if visible_lines else []
    for (line_number, _original_line), line in zip(visible_lines, masked_lines, strict=True):
        collector.reset()
        collector.references.update(references)
        for name in ("link", "reference", "short_reference"):
            collector.inlinePatterns[name].line_number = line_number
        collector.convert(line)
    targets.sort(key=lambda item: item[0])
    return targets


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
    text = measured_read_text(file_path)

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

    try:
        link_targets = markdown_link_targets(text)
    except ValueError as exc:
        raise ValueError(f"{file_path}: {exc}") from exc
    for lineno, link_target in link_targets:
        raw_target = link_target.strip()
        if not raw_target or raw_target.startswith(("#", "mailto:")):
            continue
        if LOCAL_FILESYSTEM_RE.match(raw_target):
            violations.append(
                Violation(
                    file_path,
                    lineno,
                    f"local filesystem link `{raw_target}` is not publishable",
                )
            )
            continue
        if "://" in raw_target or raw_target.startswith("/"):
            continue
        target = normalize_link_target(raw_target)
        if not target:
            continue
        base = (file_path.parent / target).resolve()
        if not base.is_relative_to(config.docs_root.resolve()):
            violations.append(
                Violation(
                    file_path,
                    lineno,
                    f"relative repo link `{raw_target}` points outside the published docs surface; use inline code or a stable external URL",
                )
            )
            continue
        if base.suffix.lower() not in {"", ".md"} and not target.endswith("/"):
            continue

        candidates = resolve_relative_candidates(file_path, target)
        resolved: Path | None = None
        if not target.endswith("/") and base.suffix == "" and measured_is_dir(base):
            candidates = [(base / "index.md").resolve()]
        for candidate in candidates:
            if not candidate.is_relative_to(config.docs_root.resolve()):
                continue
            if measured_is_file(candidate):
                resolved = candidate
                break
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
        if resolved.suffix.lower() == ".md" and resolved not in published_files:
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


def _violation_sort_key(repo_root: Path, violation: Violation) -> tuple[str, int, str]:
    try:
        relative = violation.file_path.relative_to(repo_root).as_posix()
    except ValueError:
        relative = violation.file_path.as_posix()
    return (relative, violation.lineno, violation.message)


def _input_receipt(
    repo_root: Path,
    measurement: Any,
    *,
    complete_verdict: bool,
    config: PublishedDocsConfig | None,
    workflow_names: set[str] | None,
) -> dict[str, Any]:
    """Build the explicit input and selection receipt printed with every verdict."""
    return {
        "complete_verdict": complete_verdict,
        "repo_root": str(repo_root),
        "actual_mkdocs_selection": config.selection_summary if config else None,
        "included_file_manifest": list(config.file_manifest) if config else None,
        "navigation_policy": {
            "nav_files": [path.relative_to(repo_root).as_posix() for path in config.nav_files],
            "not_in_nav_files": [
                path.relative_to(repo_root).as_posix() for path in config.not_in_nav_files
            ],
        }
        if config
        else None,
        "workflow_inventory": sorted(workflow_names) if workflow_names is not None else None,
        "generated_reference_allowlist": (
            list(config.generated_reference_presence) if config else None
        ),
        "workflow_inventory_boundary": (
            "Filename discovery uses Git root resolution and directory enumeration; "
            "those subprocess/directory operations are not in the explicit file-read receipt."
        ),
        "explicit_file_reads": measurement.snapshot(complete_verdict=complete_verdict),
        "unresolved_by_construction": [
            "Raw HTML, image and asset links are not scanned; asset paths appear in the actual MkDocs manifest only.",
            "Unsupported multiline Markdown link forms make the run UNRUN when detected.",
            "Root-relative URLs and fragment-anchor existence are not validated.",
            "Generated-reference allowlist completeness is unestablished for absent candidates; only existing allowlisted files are checked for publication.",
            "External URL availability and rendered deployment are not checked.",
            "MkDocs config loader/plugin internal reads are not observed by measure_file_reads; the resolved source YAML chain is read separately and recorded.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    """Run the accuracy checks and return a CI-friendly exit code."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    print(MEASURED)
    print(OMISSION)
    violations: list[Violation] = []
    config: PublishedDocsConfig | None = None
    workflow_names: set[str] | None = None
    unrun_error: Exception | None = None
    with measure_file_reads(repo_root) as measurement:
        try:
            config, config_violations = published_docs_config(repo_root)
            workflow_names = actual_workflow_names(repo_root)
            published_files = set(config.published_files)
            violations.extend(config_violations)
            for file_path in config.published_markdown_files:
                violations.extend(
                    scan_file(
                        file_path,
                        config=config,
                        published_files=published_files,
                        workflow_names=workflow_names,
                    )
                )
        except (OSError, UnicodeError, ValueError) as exc:
            unrun_error = exc
        complete_verdict = unrun_error is None
        receipt = _input_receipt(
            repo_root,
            measurement,
            complete_verdict=complete_verdict,
            config=config,
            workflow_names=workflow_names,
        )
        print("Input receipt JSON:")
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

    if unrun_error is not None:
        print(f"UNRUN: no complete docs verdict: {type(unrun_error).__name__}: {unrun_error}")
        for violation in violations:
            print(
                f"- partial coverage: {violation.file_path}:{violation.lineno}: {violation.message}"
            )
        return 2

    if violations:
        violations = sorted(violations, key=lambda item: _violation_sort_key(repo_root, item))
        print("Docs accuracy report: FAILED")
        print(f"- violations: {len(violations)}")
        for violation in violations:
            try:
                relative = violation.file_path.relative_to(repo_root)
            except ValueError:
                relative = violation.file_path
            print(f"- {relative}:{violation.lineno}: {violation.message}")
        return 1

    print("Docs accuracy report: passed (actual MkDocs Markdown scope)")
    print("- violations: 0")
    print(f"- checked Markdown files: {len(config.published_markdown_files)}")
    print(f"- actual MkDocs included files: {len(config.published_files)}")
    print(f"- site_url: {config.site_url or 'missing'}")
    print(f"- workflow inventory: {', '.join(sorted(workflow_names)) or 'none found'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
