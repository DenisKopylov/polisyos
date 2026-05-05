#!/usr/bin/env python3
"""Ratchet targeted CI escapes across common/core/runtime HTTP packages.

This checker blocks *new* debt from re-entering the audited surfaces while
allowing a narrow, explicit allowlist for known legacy suppressions that still
need follow-up work.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import re
import tomllib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from tools.lib.imports import repo_root_from

TYPE_IGNORE_RE = re.compile(r"#\s*type:\s*ignore(?:\[[^\]]+\])?")
NOQA_RE = re.compile(r"#\s*noqa(?::\s*[^#]+)?")
DEFAULT_ROOTS = (
    "src/polisyos/common",
    "src/polisyos/core",
    "src/polisyos/runtime",
)
BOUNDING_HINTS = (
    "ttl",
    "expires",
    "expire",
    "max_",
    "capacity",
    "limit",
    "evict",
    "bounded",
    "refresh_ttl",
)
BOUNDED_CACHE_FACTORIES = {
    "ttlcache",
    "lrucache",
    "cachedproperty",
    "weakvaluedictionary",
    "weakkeydictionary",
}


@dataclass(frozen=True)
class AllowlistEntry:
    """One allowlisted suppression or exception pattern."""

    path: str
    contains: str


@dataclass(frozen=True)
class Finding:
    """One ratchet finding emitted by the checker."""

    kind: str
    path: str
    lineno: int
    detail: str
    message: str

    def render(self) -> str:
        """Return a compact human-readable failure line."""
        return f"{self.path}:{self.lineno}: [{self.kind}] {self.message} :: {self.detail}"


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check CI ratchets for suppressions and unbounded caches."
    )
    parser.add_argument(
        "--repo-root",
        default=repo_root_from(__file__),
        type=Path,
        help="Repository root to scan.",
    )
    parser.add_argument(
        "--allowlist",
        default=Path(__file__).with_name("ci_ratchet_allowlist.toml"),
        type=Path,
        help="TOML allowlist for existing suppressions.",
    )
    parser.add_argument(
        "--root",
        action="append",
        dest="roots",
        default=None,
        help="Relative source root to scan. May be passed multiple times.",
    )
    return parser


def _iter_python_files(repo_root: Path, roots: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        base = repo_root / root
        if not base.exists():
            continue
        files.extend(sorted(path for path in base.rglob("*.py") if "__pycache__" not in path.parts))
    return files


def _load_allowlist(path: Path) -> dict[str, tuple[AllowlistEntry, ...]]:
    if not path.exists():
        return {}
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    result: dict[str, tuple[AllowlistEntry, ...]] = {}
    for kind, payload in raw.items():
        entries_raw = payload.get("entries", [])
        entries: list[AllowlistEntry] = []
        for item in entries_raw:
            entry_path = str(item.get("path", "")).strip()
            contains = str(item.get("contains", "")).strip()
            if not entry_path or not contains:
                continue
            entries.append(AllowlistEntry(path=entry_path, contains=contains))
        result[kind] = tuple(entries)
    return result


def _scan_line_suppressions(
    *,
    repo_root: Path,
    files: list[Path],
    kind: str,
    pattern: re.Pattern[str],
    message: str,
) -> list[Finding]:
    findings: list[Finding] = []
    for file_path in files:
        relative_path = file_path.relative_to(repo_root).as_posix()
        for lineno, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), start=1):
            if pattern.search(line):
                findings.append(
                    Finding(
                        kind=kind,
                        path=relative_path,
                        lineno=lineno,
                        detail=line.strip(),
                        message=message,
                    )
                )
    return findings


def _scan_except_exception_pass(*, repo_root: Path, files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for file_path in files:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        relative_path = file_path.relative_to(repo_root).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for handler in node.handlers:
                if not isinstance(handler.type, ast.Name) or handler.type.id != "Exception":
                    continue
                if handler.name is not None:
                    continue
                if handler.body and all(isinstance(stmt, ast.Pass) for stmt in handler.body):
                    findings.append(
                        Finding(
                            kind="except_exception_pass",
                            path=relative_path,
                            lineno=handler.lineno,
                            detail="except Exception: pass",
                            message="broad exception swallow without logging or typed recovery",
                        )
                    )
    return findings


def _scan_unbounded_caches(*, repo_root: Path, files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for file_path in files:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
        parent_map = _build_parent_map(tree)
        relative_path = file_path.relative_to(repo_root).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign | ast.AnnAssign):
                continue
            value = node.value
            if value is None or not _is_plain_cache_container(value):
                continue
            for target_name, scope_kind in _cache_targets(node):
                if scope_kind == "function":
                    continue
                if _has_bounding_hint(node=node, source=source, parent_map=parent_map):
                    continue
                findings.append(
                    Finding(
                        kind="unbounded_cache",
                        path=relative_path,
                        lineno=node.lineno,
                        detail=target_name,
                        message="cache-like container has no obvious TTL/capacity/eviction guard",
                    )
                )
    return findings


def _build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parent_map: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent_map[child] = node
    return parent_map


def _cache_targets(node: ast.Assign | ast.AnnAssign) -> list[tuple[str, str]]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    result: list[tuple[str, str]] = []
    for target in targets:
        if isinstance(target, ast.Name):
            name = target.id
            if "cache" in name.lower():
                result.append((name, "module"))
        elif (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
        ):
            name = target.attr
            if "cache" in name.lower():
                result.append((f"self.{name}", "instance"))
    return result


def _is_plain_cache_container(value: ast.AST) -> bool:
    if isinstance(value, ast.Dict | ast.List | ast.Set | ast.DictComp | ast.ListComp | ast.SetComp):
        return True
    if not isinstance(value, ast.Call):
        return False
    func_name = _call_name(value)
    if func_name is None:
        return False
    lowered = func_name.lower()
    if lowered in BOUNDED_CACHE_FACTORIES:
        return False
    return lowered in {"dict", "list", "set", "defaultdict"}


def _call_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _has_bounding_hint(
    *,
    node: ast.Assign | ast.AnnAssign,
    source: str,
    parent_map: dict[ast.AST, ast.AST],
) -> bool:
    function_parent = _nearest_parent(node, parent_map, (ast.FunctionDef, ast.AsyncFunctionDef))
    if function_parent is not None and function_parent.name != "__init__":
        return True
    class_parent = _nearest_parent(node, parent_map, (ast.ClassDef,))
    scope_node: ast.AST = class_parent or ast.parse(source)
    segment = ast.get_source_segment(source, scope_node) or source
    lowered = segment.lower()
    return any(hint in lowered for hint in BOUNDING_HINTS)


def _nearest_parent(
    node: ast.AST,
    parent_map: dict[ast.AST, ast.AST],
    node_types: tuple[type[ast.AST], ...],
) -> ast.AST | None:
    current = parent_map.get(node)
    while current is not None:
        if isinstance(current, node_types):
            return current
        current = parent_map.get(current)
    return None


def _is_allowlisted(
    finding: Finding,
    allowlist: dict[str, tuple[AllowlistEntry, ...]],
) -> AllowlistEntry | None:
    for entry in allowlist.get(finding.kind, ()):
        if fnmatch.fnmatch(finding.path, entry.path) and entry.contains in finding.detail:
            return entry
    return None


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    allowlist = _load_allowlist(args.allowlist.resolve())
    roots = tuple(args.roots or DEFAULT_ROOTS)
    files = _iter_python_files(repo_root, roots)

    findings = [
        *_scan_line_suppressions(
            repo_root=repo_root,
            files=files,
            kind="type_ignore",
            pattern=TYPE_IGNORE_RE,
            message="type checker escape hatch present",
        ),
        *_scan_line_suppressions(
            repo_root=repo_root,
            files=files,
            kind="noqa",
            pattern=NOQA_RE,
            message="lint suppression present",
        ),
        *_scan_except_exception_pass(repo_root=repo_root, files=files),
        *_scan_unbounded_caches(repo_root=repo_root, files=files),
    ]

    used_allowlist_entries: set[tuple[str, AllowlistEntry]] = set()
    unexpected: list[Finding] = []
    for finding in findings:
        matched = _is_allowlisted(finding, allowlist)
        if matched is None:
            unexpected.append(finding)
        else:
            used_allowlist_entries.add((finding.kind, matched))

    stale_allowlist: list[str] = []
    for kind, entries in allowlist.items():
        for entry in entries:
            if (kind, entry) not in used_allowlist_entries:
                stale_allowlist.append(f"{kind}: {entry.path} :: {entry.contains}")

    counts = Counter(finding.kind for finding in findings)
    if findings:
        summary = ", ".join(f"{kind}={counts[kind]}" for kind in sorted(counts))
        print(f"CI ratchet scan summary: {summary}")
    else:
        print("CI ratchet scan summary: clean")

    if unexpected:
        print("\nUnexpected ratchet findings:")
        for finding in unexpected:
            print(f"  - {finding.render()}")

    if stale_allowlist:
        print("\nStale allowlist entries:")
        for entry in stale_allowlist:
            print(f"  - {entry}")

    if unexpected or stale_allowlist:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
