#!/usr/bin/env python3
"""Report stale mypy and Ruff per-file override debt without failing moves."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
DEFAULT_SOURCE_ROOTS = ("src", "tests", "tools", "benchmarks", "examples", "ops")
GLOB_MARKERS = frozenset("*?[")


@dataclass(frozen=True)
class OverrideEntry:
    tool: str
    kind: str
    subject: str
    config: str
    line: int
    comments: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "kind": self.kind,
            "subject": self.subject,
            "config": self.config,
            "line": self.line,
        }


@dataclass(frozen=True)
class OverrideScope:
    tool: str
    pattern: str
    owner: str
    sunset: str
    permanent_rationale: str
    scope_id: str

    @property
    def has_lifecycle_metadata(self) -> bool:
        return bool(self.owner and (self.sunset or self.permanent_rationale))


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    tool: str
    subject: str
    config: str
    line: int
    message: str
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "severity": self.severity,
            "tool": self.tool,
            "subject": self.subject,
            "config": self.config,
            "line": self.line,
            "message": self.message,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class RepoIndex:
    source_modules: tuple[str, ...]
    files_by_name: dict[str, tuple[str, ...]]
    init_files_by_package: dict[str, tuple[str, ...]]


def build_report(
    repo_root: Path = REPO_ROOT,
    *,
    mypy_config: str | None = None,
    ruff_config: str | None = None,
    metadata_config: str = "architecture/static_analysis_overrides.toml",
) -> dict[str, Any]:
    """Build a Phase 3.6 dead-override report.

    Findings are intentionally warnings. Package moves and deletes should expose
    tool-config debt here while the command remains safe to run mid-refactor.
    """

    repo_root = repo_root.resolve()
    metadata_path = repo_root / metadata_config
    metadata = _load_toml(metadata_path)
    mypy_config = mypy_config or _default_tool_config(metadata, "mypy", "mypy.ini")
    ruff_config = ruff_config or _default_tool_config(metadata, "ruff", "ruff.toml")
    entries = [
        *_collect_mypy_entries(repo_root, mypy_config),
        *_collect_ruff_entries(repo_root, ruff_config),
    ]
    scopes = _load_metadata_scopes(metadata)
    index = _build_repo_index(repo_root)

    findings: list[Finding] = []
    for entry in entries:
        existence = _entry_existence(repo_root, entry, index)
        if not existence["exists"]:
            findings.append(
                Finding(
                    check=f"{entry.tool}-override-path",
                    severity="warning",
                    tool=entry.tool,
                    subject=entry.subject,
                    config=entry.config,
                    line=entry.line,
                    message="override target does not resolve to a live path",
                    detail=str(existence["detail"]),
                )
            )

        metadata = _metadata_match(entry, scopes)
        if not metadata["has_metadata"]:
            findings.append(
                Finding(
                    check="override-metadata",
                    severity="warning",
                    tool=entry.tool,
                    subject=entry.subject,
                    config=entry.config,
                    line=entry.line,
                    message="override is missing owner plus sunset or permanent rationale",
                    detail=str(metadata["detail"]),
                )
            )

    summary = _summary(entries, findings)
    return {
        "phase": "repository-best-in-class-phase-3.6",
        "mode": "report_only",
        "status": "reported",
        "repo_root": str(repo_root),
        "configs": {
            "mypy": mypy_config,
            "ruff": ruff_config,
            "metadata": metadata_config,
        },
        "summary": summary,
        "findings": [finding.as_dict() for finding in findings],
    }


def _collect_mypy_entries(repo_root: Path, config: str) -> list[OverrideEntry]:
    path = repo_root / config
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    entries: list[OverrideEntry] = []
    section_re = re.compile(r"^\[mypy-(?P<modules>.+)]\s*$")
    for index, line in enumerate(lines):
        match = section_re.match(line.strip())
        if match is None:
            continue
        comments = _leading_comment_block(lines, index)
        for module in match.group("modules").split(","):
            subject = module.strip()
            if subject:
                entries.append(
                    OverrideEntry(
                        tool="mypy",
                        kind="mypy-module-override",
                        subject=subject,
                        config=config,
                        line=index + 1,
                        comments=comments,
                    )
                )
    return entries


def _collect_ruff_entries(repo_root: Path, config: str) -> list[OverrideEntry]:
    path = repo_root / config
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []
    per_file_ignores = data.get("lint", {}).get("per-file-ignores", {})
    if not isinstance(per_file_ignores, dict):
        return []

    lines = text.splitlines()
    line_map = _ruff_per_file_ignore_line_map(lines)
    entries: list[OverrideEntry] = []
    for subject in sorted(str(key) for key in per_file_ignores):
        line = line_map.get(subject, 0)
        comments = _leading_comment_block(lines, line - 1) if line else ()
        inline_comment = _inline_comment(lines[line - 1]) if line else ""
        if inline_comment:
            comments = (*comments, inline_comment)
        entries.append(
            OverrideEntry(
                tool="ruff",
                kind="ruff-per-file-ignore",
                subject=subject,
                config=config,
                line=line,
                comments=comments,
            )
        )
    return entries


def _ruff_per_file_ignore_line_map(lines: list[str]) -> dict[str, int]:
    section = False
    line_map: dict[str, int] = {}
    key_re = re.compile(r"^\s*(?:\"(?P<quoted>[^\"]+)\"|(?P<bare>[^=\s]+))\s*=")
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped == "[lint.per-file-ignores]"
            continue
        if not section:
            continue
        match = key_re.match(line)
        if match is not None:
            key = match.group("quoted") or match.group("bare")
            line_map[key] = index + 1
    return line_map


def _leading_comment_block(lines: list[str], index: int) -> tuple[str, ...]:
    comments: list[str] = []
    cursor = index - 1
    while cursor >= 0:
        stripped = lines[cursor].strip()
        if stripped.startswith("#"):
            comments.append(stripped.removeprefix("#").strip())
            cursor -= 1
            continue
        if stripped == "" and comments:
            cursor -= 1
            continue
        break
    comments.reverse()
    return tuple(comments)


def _inline_comment(line: str) -> str:
    escaped = False
    quote: str | None = None
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char in {"'", '"'}:
            quote = None if quote == char else char if quote is None else quote
            continue
        if char == "#" and quote is None:
            return line[index + 1 :].strip()
    return ""


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _default_tool_config(data: dict[str, Any], tool: str, fallback: str) -> str:
    split = data.get("tool_config_split", {})
    if isinstance(split, dict):
        value = split.get(f"{tool}_config")
        if value:
            return str(value)
    baselines = data.get("baselines", {})
    if isinstance(baselines, dict):
        value = baselines.get(f"{tool}_config")
        if value:
            return str(value)
    return fallback


def _load_metadata_scopes(data: dict[str, Any]) -> list[OverrideScope]:
    scopes: list[OverrideScope] = []
    for item in data.get("override_scope", []):
        if not isinstance(item, dict):
            continue
        scopes.append(
            OverrideScope(
                tool=str(item.get("tool", "")),
                pattern=str(item.get("pattern", "")),
                owner=str(item.get("owner", "")),
                sunset=str(item.get("sunset", "")),
                permanent_rationale=str(
                    item.get("permanent_rationale") or item.get("permanent_reason") or ""
                ),
                scope_id=str(item.get("id", "")),
            )
        )
    return scopes


def _entry_existence(repo_root: Path, entry: OverrideEntry, index: RepoIndex) -> dict[str, object]:
    if entry.tool == "mypy":
        return _mypy_entry_existence(repo_root, entry.subject, index)
    return _ruff_entry_existence(repo_root, entry.subject, index)


def _mypy_entry_existence(repo_root: Path, module: str, index: RepoIndex) -> dict[str, object]:
    if any(marker in module for marker in GLOB_MARKERS):
        matches = _matching_source_modules(index, module)
        if matches:
            return {
                "exists": True,
                "detail": f"pattern matches {len(matches)} live module(s)",
            }
        return {
            "exists": False,
            "detail": f"mypy pattern matches no live modules: {module}",
        }

    candidates = _module_candidate_paths(repo_root, module)
    live = [path for path in candidates if path.exists()]
    if live:
        return {
            "exists": True,
            "detail": ", ".join(_relative(path, repo_root) for path in live),
        }

    moved = _mypy_moved_candidates(module, index)
    expected = ", ".join(_relative(path, repo_root) for path in candidates)
    if moved:
        return {
            "exists": False,
            "detail": (
                f"expected one of: {expected}; possible moved file candidates: "
                f"{', '.join(moved)}"
            ),
        }
    return {
        "exists": False,
        "detail": f"expected one of: {expected}; no live file with matching module basename found",
    }


def _ruff_entry_existence(repo_root: Path, subject: str, index: RepoIndex) -> dict[str, object]:
    if any(marker in subject for marker in GLOB_MARKERS):
        matches = _safe_glob(repo_root, subject)
        if matches:
            return {
                "exists": True,
                "detail": f"pattern matches {len(matches)} live path(s)",
            }
        return {
            "exists": False,
            "detail": f"Ruff per-file pattern matches no live paths: {subject}",
        }

    path = repo_root / subject
    if path.exists():
        return {"exists": True, "detail": subject}
    moved = _path_moved_candidates(subject, index)
    if moved:
        return {
            "exists": False,
            "detail": (
                f"expected path is missing: {subject}; possible moved file candidates: "
                f"{', '.join(moved)}"
            ),
        }
    return {
        "exists": False,
        "detail": f"expected path is missing: {subject}; no live file with matching basename found",
    }


def _module_candidate_paths(repo_root: Path, module: str) -> tuple[Path, ...]:
    relative = Path(*module.split("."))
    return (
        repo_root / "src" / relative.with_suffix(".py"),
        repo_root / "src" / relative / "__init__.py",
        repo_root / relative.with_suffix(".py"),
        repo_root / relative / "__init__.py",
    )


def _matching_source_modules(index: RepoIndex, pattern: str) -> tuple[str, ...]:
    modules = []
    for module in index.source_modules:
        if fnmatch.fnmatchcase(module, pattern):
            modules.append(module)
    return tuple(sorted(set(modules)))


def _build_repo_index(repo_root: Path) -> RepoIndex:
    modules: set[str] = set()
    files_by_name: dict[str, set[str]] = {}
    init_files_by_package: dict[str, set[str]] = {}
    for root_name in DEFAULT_SOURCE_ROOTS:
        root = repo_root / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            relative_path = _relative(path, repo_root)
            modules.add(_module_name_from_path(root, path))
            files_by_name.setdefault(path.name, set()).add(relative_path)
            if path.name == "__init__.py":
                init_files_by_package.setdefault(path.parent.name, set()).add(relative_path)
    return RepoIndex(
        source_modules=tuple(sorted(modules)),
        files_by_name={
            name: tuple(sorted(paths)) for name, paths in sorted(files_by_name.items())
        },
        init_files_by_package={
            name: tuple(sorted(paths)) for name, paths in sorted(init_files_by_package.items())
        },
    )


def _module_name_from_path(source_root: Path, path: Path) -> str:
    relative = path.relative_to(source_root)
    relative = relative.parent if relative.name == "__init__.py" else relative.with_suffix("")
    return ".".join(relative.parts)


def _mypy_moved_candidates(module: str, index: RepoIndex) -> tuple[str, ...]:
    basename = module.rsplit(".", maxsplit=1)[-1]
    candidates = [
        *index.files_by_name.get(f"{basename}.py", ()),
        *index.init_files_by_package.get(basename, ()),
    ]
    return tuple(sorted(set(candidates))[:8])


def _path_moved_candidates(subject: str, index: RepoIndex) -> tuple[str, ...]:
    basename = Path(subject).name
    if not basename:
        return ()
    candidates = index.files_by_name.get(basename, ())
    return tuple(sorted(set(candidates))[:8])


def _safe_glob(repo_root: Path, pattern: str) -> tuple[Path, ...]:
    try:
        return tuple(repo_root.glob(pattern))
    except ValueError:
        return ()


def _metadata_match(entry: OverrideEntry, scopes: list[OverrideScope]) -> dict[str, object]:
    matching_scopes = [
        scope
        for scope in scopes
        if scope.tool == entry.tool and scope.pattern and _scope_matches_entry(scope, entry)
    ]
    for scope in matching_scopes:
        if scope.has_lifecycle_metadata:
            return {
                "has_metadata": True,
                "detail": f"covered by override_scope `{scope.scope_id}`",
            }

    comment_metadata = _comment_metadata(entry.comments)
    if comment_metadata["has_metadata"]:
        return {"has_metadata": True, "detail": "covered by adjacent config comment metadata"}

    if matching_scopes:
        scope_ids = ", ".join(f"`{scope.scope_id}`" for scope in matching_scopes)
        return {
            "has_metadata": False,
            "detail": f"matched scope(s) without complete owner/lifecycle metadata: {scope_ids}",
        }
    return {
        "has_metadata": False,
        "detail": "no matching override_scope or adjacent owner/lifecycle comment found",
    }


def _scope_matches_entry(scope: OverrideScope, entry: OverrideEntry) -> bool:
    if entry.tool == "mypy":
        return _module_pattern_matches(scope.pattern, entry.subject)
    return fnmatch.fnmatchcase(entry.subject, scope.pattern)


def _module_pattern_matches(pattern: str, module: str) -> bool:
    if any(marker in pattern for marker in GLOB_MARKERS):
        return fnmatch.fnmatchcase(module, pattern)
    return module == pattern


def _comment_metadata(comments: tuple[str, ...]) -> dict[str, object]:
    text = "\n".join(comments).lower()
    has_owner = bool(re.search(r"\bowner\s*[:=]", text))
    has_sunset = bool(re.search(r"\bsunset(?:_date)?\s*[:=]", text))
    has_permanent_rationale = bool(
        re.search(r"\bpermanent[_ -]rationale\s*[:=]", text)
        or re.search(r"\bpermanent[_ -]reason\s*[:=]", text)
    )
    return {
        "has_metadata": has_owner and (has_sunset or has_permanent_rationale),
        "has_owner": has_owner,
        "has_sunset": has_sunset,
        "has_permanent_rationale": has_permanent_rationale,
    }


def _summary(entries: list[OverrideEntry], findings: list[Finding]) -> dict[str, int]:
    mypy_entries = [entry for entry in entries if entry.tool == "mypy"]
    ruff_entries = [entry for entry in entries if entry.tool == "ruff"]
    return {
        "override_count": len(entries),
        "mypy_override_count": len(mypy_entries),
        "ruff_override_count": len(ruff_entries),
        "finding_count": len(findings),
        "stale_mypy_override_count": _finding_count(findings, "mypy", "mypy-override-path"),
        "stale_ruff_override_count": _finding_count(findings, "ruff", "ruff-override-path"),
        "missing_metadata_count": _finding_count(findings, None, "override-metadata"),
    }


def _finding_count(findings: list[Finding], tool: str | None, check: str) -> int:
    return sum(
        1 for finding in findings if finding.check == check and (tool is None or finding.tool == tool)
    )


def _relative(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report stale mypy/Ruff per-file overrides without failing package moves."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--mypy-config",
        help=(
            "Mypy config to scan. Defaults to architecture/static_analysis_overrides.toml "
            "tool_config_split.mypy_config, then baselines.mypy_config, then mypy.ini."
        ),
    )
    parser.add_argument(
        "--ruff-config",
        help=(
            "Ruff config to scan. Defaults to architecture/static_analysis_overrides.toml "
            "tool_config_split.ruff_config, then baselines.ruff_config, then ruff.toml."
        ),
    )
    parser.add_argument(
        "--metadata-config",
        default="architecture/static_analysis_overrides.toml",
        help="TOML file with [[override_scope]] owner/lifecycle metadata.",
    )
    parser.add_argument("--json-output", type=Path)
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    payload = build_report(
        repo_root,
        mypy_config=args.mypy_config,
        ruff_config=args.ruff_config,
        metadata_config=args.metadata_config,
    )
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.json_output is not None:
        output = args.json_output if args.json_output.is_absolute() else repo_root / args.json_output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    return run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
