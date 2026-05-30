#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import datetime
import fnmatch
import json
import re
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.lib.cache import (
    baseline_matches,
    cache_path,
    content_addressable_key,
    default_cache_root,
    file_sha256,
    filter_paths_under_root,
    git_changed_files,
    persist_baseline,
    read_json_cache,
    stable_json_hash,
    write_json_cache,
)
from tools.lib.fs import atomic_write_text
from tools.lib.imports import is_type_checking_test
from tools.lib.output import OUTPUT_FORMATS, ToolMessage, ToolResult, format_tool_result

DEFAULT_POLICY_PATH = Path("architecture/imports/policy.toml")
DEFAULT_EXCEPTIONS_PATH = Path("architecture/imports/exceptions.toml")
DEFAULT_TOP_GOD_FILES = 10
CACHE_NAMESPACE = "lint_imports"
CACHE_VERSION = "2026.04.phase5"
DEFAULT_BASELINE_LABEL = "default"
VIOLATION_RULE_RE = re.compile(r"\[(ARCH\d+)\]")


@dataclass(frozen=True)
class ImportRef:
    source_file: Path
    source_module: str
    target_module: str
    lineno: int
    in_type_checking: bool


@dataclass(frozen=True)
class PolicyConfig:
    version: str
    internal_prefix: str
    src_root: Path
    known_roots: set[str]
    internal_allow: dict[str, set[str]]
    external_allow: dict[str, set[str]]
    package_cycle_baselines: frozenset[tuple[str, ...]]


@dataclass(frozen=True)
class ImportException:
    exception_id: str
    owner: str
    reason: str
    expires: datetime.date
    issue: str | None
    source_glob: str
    import_root: str | None
    import_module_prefix: str | None
    source_module_prefix: str | None
    external_module: str | None


@dataclass(frozen=True)
class ExceptionMatch:
    exception: ImportException
    ref: ImportRef
    message: str


@dataclass(frozen=True)
class Violation:
    ref: ImportRef
    code: str
    message: str
    exception: ImportException | None = None
    expired_exception: ImportException | None = None


@dataclass(frozen=True)
class ParsedModuleFile:
    source_file: Path
    source_module: str
    imports: tuple[ImportRef, ...]
    internal_target_count: int
    runtime_internal_targets: tuple[str, ...]


@dataclass
class ParseCacheStats:
    hits: int = 0
    misses: int = 0


@dataclass(frozen=True)
class CompiledExceptions:
    external_by_module: dict[str, tuple[ImportException, ...]]
    internal_by_root: dict[str, tuple[ImportException, ...]]
    internal_prefix_only: tuple[ImportException, ...]


@dataclass(frozen=True)
class LintReportContext:
    config: PolicyConfig
    repo_root: Path
    policy_path: Path
    exceptions_path: Path
    top: int
    fail_on_cycles: bool
    scan_mode: str
    changed_file_count: int
    cache_hits: int
    cache_misses: int
    fixes_applied: int
    enforced_cycle_signatures: frozenset[tuple[str, ...]]


def resolve_import_module(
    current_module: str, is_package: bool, node: ast.ImportFrom
) -> str | None:
    if node.level == 0:
        return node.module
    package_parts = current_module.split(".")
    if not is_package:
        package_parts = package_parts[:-1]
    if node.level - 1 > len(package_parts):
        return None
    base_parts = package_parts[: len(package_parts) - (node.level - 1)]
    if node.module:
        base_parts += node.module.split(".")
    return ".".join(base_parts)


class ImportCollector(ast.NodeVisitor):
    def __init__(
        self,
        source_file: Path,
        source_module: str,
        is_package: bool,
        internal_prefix: str,
    ) -> None:
        self.source_file = source_file
        self.source_module = source_module
        self.is_package = is_package
        self.internal_prefix = internal_prefix
        self.imports: list[ImportRef] = []
        self.internal_targets: set[str] = set()
        self.runtime_internal_targets: set[str] = set()
        self._type_checking_stack: list[bool] = [False]

    @property
    def in_type_checking(self) -> bool:
        return any(self._type_checking_stack)

    def visit_If(self, node: ast.If) -> None:
        if is_type_checking_test(node.test):
            self._type_checking_stack.append(True)
            for child in node.body:
                self.visit(child)
            self._type_checking_stack.pop()
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._record_import(alias.name, node.lineno)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = resolve_import_module(self.source_module, self.is_package, node)
        if not module:
            return
        if module == self.internal_prefix:
            for alias in node.names:
                if alias.name == "*":
                    self._record_import(module, node.lineno)
                    continue
                self._record_import(f"{module}.{alias.name}", node.lineno)
            return
        self._record_import(module, node.lineno)

    def _record_import(self, module: str, lineno: int) -> None:
        ref = ImportRef(
            source_file=self.source_file,
            source_module=self.source_module,
            target_module=module,
            lineno=lineno,
            in_type_checking=self.in_type_checking,
        )
        self.imports.append(ref)
        if module == self.internal_prefix or module.startswith(f"{self.internal_prefix}."):
            self.internal_targets.add(module)
            if not ref.in_type_checking:
                self.runtime_internal_targets.add(module)


def module_name_for_path(
    src_root: Path, file_path: Path, internal_prefix: str
) -> tuple[str, bool] | None:
    relative = file_path.relative_to(src_root)
    parts = list(relative.parts)
    if not parts:
        return None
    if parts[0] != internal_prefix:
        if src_root.name == internal_prefix:
            parts = [internal_prefix] + parts
        else:
            return None
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
        return ".".join(parts), True
    parts[-1] = parts[-1].removesuffix(".py")
    return ".".join(parts), False


def iter_py_files(src_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in src_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        files.append(path)
    return sorted(files)


def _parsed_module_to_payload(parsed: ParsedModuleFile) -> dict[str, Any]:
    return {
        "source_module": parsed.source_module,
        "imports": [
            {
                "target_module": ref.target_module,
                "lineno": ref.lineno,
                "in_type_checking": ref.in_type_checking,
            }
            for ref in parsed.imports
        ],
        "internal_target_count": parsed.internal_target_count,
        "runtime_internal_targets": list(parsed.runtime_internal_targets),
    }


def _parsed_module_from_payload(
    payload: dict[str, Any],
    *,
    source_file: Path,
    source_module: str,
) -> ParsedModuleFile | None:
    imports_any = payload.get("imports")
    if not isinstance(imports_any, list):
        return None
    imports: list[ImportRef] = []
    for item in imports_any:
        if not isinstance(item, dict):
            return None
        target_module = item.get("target_module")
        lineno = item.get("lineno")
        if not isinstance(target_module, str) or not isinstance(lineno, int):
            return None
        imports.append(
            ImportRef(
                source_file=source_file,
                source_module=source_module,
                target_module=target_module,
                lineno=lineno,
                in_type_checking=bool(item.get("in_type_checking", False)),
            )
        )

    runtime_targets = payload.get("runtime_internal_targets") or []
    if not isinstance(runtime_targets, list) or not all(
        isinstance(target, str) for target in runtime_targets
    ):
        return None

    return ParsedModuleFile(
        source_file=source_file,
        source_module=source_module,
        imports=tuple(imports),
        internal_target_count=int(payload.get("internal_target_count") or 0),
        runtime_internal_targets=tuple(runtime_targets),
    )


def _parse_cache_key(config: PolicyConfig, file_path: Path, file_hash: str) -> str:
    return content_addressable_key(
        version=CACHE_VERSION,
        payload={
            "src_root": str(config.src_root),
            "internal_prefix": config.internal_prefix,
            "file": str(file_path.relative_to(config.src_root)),
            "sha256": file_hash,
        },
    )


def _parse_module_file(
    config: PolicyConfig,
    file_path: Path,
    *,
    module_name: str,
    is_package: bool,
) -> ParsedModuleFile:
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    collector = ImportCollector(
        file_path,
        module_name,
        is_package,
        config.internal_prefix,
    )
    collector.visit(tree)
    return ParsedModuleFile(
        source_file=file_path,
        source_module=module_name,
        imports=tuple(collector.imports),
        internal_target_count=len(collector.internal_targets),
        runtime_internal_targets=tuple(sorted(collector.runtime_internal_targets)),
    )


def parse_imports(
    config: PolicyConfig,
    *,
    cache_root: Path | None = None,
) -> tuple[list[ImportRef], dict[Path, int], dict[str, set[str]], dict[Path, str], ParseCacheStats]:
    imports: list[ImportRef] = []
    internal_counts: dict[Path, int] = {}
    module_graph: dict[str, set[str]] = {}
    file_hashes: dict[Path, str] = {}
    cache_stats = ParseCacheStats()

    for file_path in iter_py_files(config.src_root):
        result = module_name_for_path(config.src_root, file_path, config.internal_prefix)
        if result is None:
            continue
        module_name, is_package = result
        module_graph.setdefault(module_name, set())
        file_hash = file_sha256(file_path)
        file_hashes[file_path] = file_hash

        parsed: ParsedModuleFile | None = None
        if cache_root is not None:
            payload = read_json_cache(
                cache_path(
                    cache_root,
                    CACHE_NAMESPACE,
                    _parse_cache_key(config, file_path, file_hash),
                )
            )
            if payload is not None:
                parsed = _parsed_module_from_payload(
                    payload,
                    source_file=file_path,
                    source_module=module_name,
                )
                if parsed is not None:
                    cache_stats.hits += 1

        if parsed is None:
            cache_stats.misses += 1
            parsed = _parse_module_file(
                config,
                file_path,
                module_name=module_name,
                is_package=is_package,
            )
            if cache_root is not None:
                write_json_cache(
                    cache_path(
                        cache_root,
                        CACHE_NAMESPACE,
                        _parse_cache_key(config, file_path, file_hash),
                    ),
                    _parsed_module_to_payload(parsed),
                )

        imports.extend(parsed.imports)
        internal_counts[file_path] = parsed.internal_target_count
        for target in parsed.runtime_internal_targets:
            if target.startswith(f"{config.internal_prefix}."):
                module_graph[module_name].add(target)

    return imports, internal_counts, module_graph, file_hashes, cache_stats


def strongly_connected_components(graph: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    on_stack: set[str] = set()
    result: list[list[str]] = []

    def strongconnect(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for neighbor in sorted(graph.get(node, [])):
            if neighbor not in indices:
                strongconnect(neighbor)
                lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
            elif neighbor in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[neighbor])
        if lowlinks[node] == indices[node]:
            scc: list[str] = []
            while True:
                popped = stack.pop()
                on_stack.remove(popped)
                scc.append(popped)
                if popped == node:
                    break
            result.append(scc)

    for node in sorted(graph):
        if node not in indices:
            strongconnect(node)
    return result


def package_for_module(module: str) -> str:
    parts = module.split(".")
    if len(parts) >= 3 and parts[0] == "polisyos":
        if parts[1] == "scientist" and parts[2] in {"agent", "orchestrator"}:
            return ".".join(parts[:3])
        if parts[1] == "fabric" and parts[2] in {"udf", "io"}:
            return ".".join(parts[:3])
        if parts[1] == "foundry" and parts[2] in {"domain", "engine"}:
            return ".".join(parts[:3])
    if len(parts) >= 2:
        return ".".join(parts[:2])
    return module


def format_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def read_policy(path: Path) -> PolicyConfig:
    if not path.exists():
        raise ValueError(f"Policy file not found: {path}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    policy = data.get("policy") or {}
    internal_prefix = policy.get("internal_prefix")
    src_root_raw = policy.get("src_root")
    version = policy.get("version", "unknown")
    if not internal_prefix or not src_root_raw:
        raise ValueError("policy.internal_prefix and policy.src_root are required")

    src_root = Path(str(src_root_raw))
    if not src_root.is_absolute():
        src_root = (path.parent / src_root).resolve()

    roots = data.get("roots") or {}
    known_list = roots.get("known") or []
    known_roots = set(known_list)
    if not known_roots:
        raise ValueError("roots.known must list at least one root")

    internal_allow = data.get("internal", {}).get("allow", {})
    internal_allow_map: dict[str, set[str]] = {}
    for root in known_roots:
        if root not in internal_allow:
            raise ValueError(f"internal.allow.{root} must be defined")
        internal_allow_map[root] = set(internal_allow.get(root, []))

    external_allow = data.get("external", {}).get("allow", {})
    external_allow_map: dict[str, set[str]] = {}
    for root, values in external_allow.items():
        modules = values.get("modules") if isinstance(values, dict) else values
        external_allow_map[root] = set(modules or [])

    package_cycle_baselines: set[tuple[str, ...]] = set()
    for item in data.get("package_cycle_baseline", []):
        packages = item.get("packages") if isinstance(item, dict) else None
        if not isinstance(packages, list) or not packages:
            raise ValueError(f"package_cycle_baseline entry must define packages: {item}")
        package_cycle_baselines.add(tuple(sorted(str(package) for package in packages)))

    return PolicyConfig(
        version=version,
        internal_prefix=internal_prefix,
        src_root=src_root,
        known_roots=known_roots,
        internal_allow=internal_allow_map,
        external_allow=external_allow_map,
        package_cycle_baselines=frozenset(package_cycle_baselines),
    )


def read_exceptions(path: Path | None) -> list[ImportException]:
    if path is None or not path.exists():
        return []
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    exceptions = data.get("exception", [])
    results: list[ImportException] = []
    seen_ids: set[str] = set()
    for item in exceptions:
        exception_id = item.get("id")
        owner = item.get("owner")
        reason = item.get("reason")
        expires_raw = item.get("expires")
        issue = item.get("issue")
        source_glob = item.get("source_glob")
        import_root = item.get("import_root")
        import_module_prefix = item.get("import_module_prefix")
        source_module_prefix = item.get("source_module_prefix")
        external_module = item.get("external_module")

        if not exception_id or not owner or not reason or not expires_raw or not source_glob:
            raise ValueError(f"Invalid exception entry (missing fields): {item}")
        if exception_id in seen_ids:
            raise ValueError(f"Duplicate exception id: {exception_id}")
        seen_ids.add(exception_id)

        if external_module and (import_root or import_module_prefix):
            raise ValueError(
                f"Exception {exception_id} cannot mix external_module with internal selectors"
            )

        if not external_module and not import_root and not import_module_prefix:
            raise ValueError(
                f"Exception {exception_id} must define import_root, import_module_prefix, or external_module"
            )

        try:
            expires = datetime.date.fromisoformat(str(expires_raw))
        except ValueError as exc:
            raise ValueError(
                f"Exception {exception_id} has invalid expires date: {expires_raw}"
            ) from exc

        results.append(
            ImportException(
                exception_id=exception_id,
                owner=owner,
                reason=reason,
                expires=expires,
                issue=str(issue) if issue else None,
                source_glob=source_glob,
                import_root=import_root,
                import_module_prefix=import_module_prefix,
                source_module_prefix=source_module_prefix,
                external_module=external_module,
            )
        )

    return results


def root_for_module(module: str, internal_prefix: str) -> str | None:
    parts = module.split(".")
    if len(parts) < 2:
        return None
    if parts[0] != internal_prefix:
        return None
    return parts[1]


def is_internal_module(module: str, internal_prefix: str) -> bool:
    return module == internal_prefix or module.startswith(f"{internal_prefix}.")


def stdlib_modules() -> set[str]:
    modules = set(getattr(sys, "stdlib_module_names", set()))
    modules.update(sys.builtin_module_names)
    return modules


def compile_exceptions(exceptions: list[ImportException]) -> CompiledExceptions:
    external_by_module: dict[str, list[ImportException]] = {}
    internal_by_root: dict[str, list[ImportException]] = {}
    internal_prefix_only: list[ImportException] = []

    ordered = sorted(
        exceptions,
        key=lambda item: (
            item.external_module or "",
            item.import_root or "",
            item.import_module_prefix or "",
            item.source_module_prefix or "",
            item.source_glob,
            item.exception_id,
        ),
    )
    for exception in ordered:
        if exception.external_module:
            external_by_module.setdefault(exception.external_module, []).append(exception)
        elif exception.import_root:
            internal_by_root.setdefault(exception.import_root, []).append(exception)
        else:
            internal_prefix_only.append(exception)

    return CompiledExceptions(
        external_by_module={key: tuple(value) for key, value in external_by_module.items()},
        internal_by_root={key: tuple(value) for key, value in internal_by_root.items()},
        internal_prefix_only=tuple(internal_prefix_only),
    )


def exception_matches(
    exception: ImportException,
    ref: ImportRef,
    *,
    rel_path: str,
    target_module: str,
    target_root: str | None,
    external_top: str | None,
) -> bool:
    if not fnmatch.fnmatch(rel_path, exception.source_glob):
        return False
    if exception.source_module_prefix and not ref.source_module.startswith(
        exception.source_module_prefix
    ):
        return False
    if exception.external_module:
        return external_top == exception.external_module
    if exception.import_root and target_root != exception.import_root:
        return False
    if exception.import_module_prefix and not target_module.startswith(
        exception.import_module_prefix
    ):
        return False
    return True


def _exception_candidates(
    compiled: CompiledExceptions,
    *,
    target_root: str | None,
    external_top: str | None,
) -> tuple[ImportException, ...]:
    if external_top is not None:
        return compiled.external_by_module.get(external_top, ())
    if target_root is None:
        return compiled.internal_prefix_only
    return compiled.internal_by_root.get(target_root, ()) + compiled.internal_prefix_only


def format_allowed_internal(allowed: set[str]) -> str:
    if "*" in allowed:
        return "*"
    return "{" + ", ".join(sorted(allowed)) + "}"


def format_allowed_external(allowed: set[str]) -> str:
    if not allowed:
        return "stdlib"
    return "stdlib + {" + ", ".join(sorted(allowed)) + "}"


def _violation_rule_id(message: str) -> str:
    match = VIOLATION_RULE_RE.search(message)
    if match is None:
        return "ARCH000"
    return match.group(1)


def _text_report(
    *,
    context: LintReportContext,
    violations: list[Violation],
    allowed_exceptions: list[ExceptionMatch],
    cycles: list[list[str]],
    internal_counts: dict[Path, int],
) -> str:
    lines = [
        "Import gate report",
        "",
        f"Policy: {format_path(Path.cwd(), context.policy_path)} (v{context.config.version})",
        f"Exceptions: {format_path(Path.cwd(), context.exceptions_path)}",
        f"Scan mode: {context.scan_mode}",
        f"Parse cache: hits={context.cache_hits}, misses={context.cache_misses}",
    ]
    if context.scan_mode == "changed-only":
        lines.append(f"Changed files: {context.changed_file_count}")
    if context.fixes_applied:
        lines.append(f"Autofix: canonicalized exceptions file ({context.fixes_applied} write)")
    lines.append("")

    if violations:
        lines.append("Violations:")
        for violation in violations:
            lines.append(f"- {violation.message}")
            if violation.expired_exception:
                exc = violation.expired_exception
                lines.append(f"  expired exception {exc.exception_id} (expires {exc.expires})")
        lines.append("")
    else:
        lines.extend(["Violations: none", ""])

    if allowed_exceptions:
        lines.append("Allowed exceptions:")
        for match in allowed_exceptions:
            exc = match.exception
            file_path = format_path(context.repo_root, match.ref.source_file)
            lines.append(
                f"- {file_path}:{match.ref.lineno} {exc.exception_id} "
                f"(expires {exc.expires}) {exc.reason}"
            )
        lines.append("")
    else:
        lines.extend(["Allowed exceptions: none", ""])

    if cycles:
        lines.append("Cycles (runtime imports, package-level):")
        for group in cycles:
            lines.append(f"- {', '.join(group)}")
        lines.append("")
    else:
        lines.extend(["Cycles (runtime imports, package-level): none", ""])

    god_files = sorted(internal_counts.items(), key=lambda item: (-item[1], str(item[0])))
    lines.append(f"Top god files (internal import count, top {context.top}):")
    for path, count in god_files[: context.top]:
        if count == 0:
            continue
        lines.append(f"- {format_path(context.repo_root, path)}: {count}")
    lines.append("")
    return "\n".join(lines)


def _structured_result(
    *,
    context: LintReportContext,
    violations: list[Violation],
    allowed_exceptions: list[ExceptionMatch],
    cycles: list[list[str]],
    internal_counts: dict[Path, int],
    exit_code: int,
) -> ToolResult:
    messages: list[ToolMessage] = []
    for violation in violations:
        rule_id = _violation_rule_id(violation.message)
        messages.append(
            ToolMessage(
                level="error",
                message=violation.message,
                path=format_path(context.repo_root, violation.ref.source_file),
                line=violation.ref.lineno,
                rule_id=rule_id,
            )
        )
        if violation.expired_exception is not None:
            messages.append(
                ToolMessage(
                    level="error",
                    message=(
                        f"expired exception {violation.expired_exception.exception_id} "
                        f"(expires {violation.expired_exception.expires})"
                    ),
                    path=format_path(context.repo_root, violation.ref.source_file),
                    line=violation.ref.lineno,
                    rule_id="ARCH_EXCEPTION_EXPIRED",
                )
            )
    for group in cycles:
        cycle_signature = tuple(sorted(group))
        cycle_level = (
            "error"
            if context.fail_on_cycles and cycle_signature in context.enforced_cycle_signatures
            else "warning"
        )
        messages.append(
            ToolMessage(
                level=cycle_level,
                message="Import cycle detected: " + ", ".join(group),
                rule_id="ARCH_CYCLE",
            )
        )

    god_files = sorted(internal_counts.items(), key=lambda item: (-item[1], str(item[0])))
    summary = "import policy passed"
    status = "ok"
    if exit_code != 0:
        summary = "import policy failed"
        status = "failed"

    return ToolResult(
        tool="lint.lint-imports",
        status=status,
        summary=summary,
        exit_code=exit_code,
        messages=tuple(messages),
        data={
            "policy_version": context.config.version,
            "scan_mode": context.scan_mode,
            "changed_file_count": context.changed_file_count,
            "cache_hits": context.cache_hits,
            "cache_misses": context.cache_misses,
            "fixes_applied": context.fixes_applied,
            "violation_count": len(violations),
            "allowed_exception_count": len(allowed_exceptions),
            "cycle_count": len(cycles),
            "cycle_error_count": len(context.enforced_cycle_signatures),
            "cycles_enforced": context.fail_on_cycles,
            "top_god_files": [
                {
                    "path": format_path(context.repo_root, path),
                    "internal_import_count": count,
                }
                for path, count in god_files[: context.top]
                if count > 0
            ],
        },
    )


def _emit_output(content: str, *, output: Path | None) -> None:
    if output is not None:
        atomic_write_text(output, content, encoding="utf-8")
        return
    sys.stdout.write(content)


def _render_toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _canonical_exception_file(exceptions: list[ImportException]) -> str:
    ordered = sorted(
        exceptions,
        key=lambda item: (
            item.source_glob,
            item.source_module_prefix or "",
            item.import_root or "",
            item.import_module_prefix or "",
            item.external_module or "",
            item.exception_id,
        ),
    )
    lines: list[str] = []
    for exception in ordered:
        lines.append("[[exception]]")
        lines.append(f"id = {_render_toml_string(exception.exception_id)}")
        lines.append(f"owner = {_render_toml_string(exception.owner)}")
        lines.append(f"reason = {_render_toml_string(exception.reason)}")
        lines.append(f"expires = {_render_toml_string(exception.expires.isoformat())}")
        if exception.issue is not None:
            lines.append(f"issue = {_render_toml_string(exception.issue)}")
        lines.append(f"source_glob = {_render_toml_string(exception.source_glob)}")
        if exception.import_root is not None:
            lines.append(f"import_root = {_render_toml_string(exception.import_root)}")
        if exception.import_module_prefix is not None:
            lines.append(
                f"import_module_prefix = {_render_toml_string(exception.import_module_prefix)}"
            )
        if exception.source_module_prefix is not None:
            lines.append(
                f"source_module_prefix = {_render_toml_string(exception.source_module_prefix)}"
            )
        if exception.external_module is not None:
            lines.append(f"external_module = {_render_toml_string(exception.external_module)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n" if lines else ""


def _canonicalize_exceptions_file(path: Path, exceptions: list[ImportException]) -> int:
    if not path.exists():
        return 0
    rendered = _canonical_exception_file(exceptions)
    current = path.read_text(encoding="utf-8")
    if current == rendered:
        return 0
    atomic_write_text(path, rendered, encoding="utf-8")
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check internal import boundaries and report cycles."
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_POLICY_PATH,
        help="Path to import policy TOML.",
    )
    parser.add_argument(
        "--exceptions",
        type=Path,
        default=DEFAULT_EXCEPTIONS_PATH,
        help="Path to import exceptions TOML.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP_GOD_FILES,
        help="Show top N god files.",
    )
    parser.add_argument(
        "--fail-on-cycles",
        action="store_true",
        help="Fail on import cycles.",
    )
    parser.add_argument(
        "--allow-type-checking",
        action="store_true",
        help="Ignore violations inside TYPE_CHECKING blocks.",
    )
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="Report only violations and cycles touching files changed relative to git.",
    )
    parser.add_argument(
        "--git-base-ref",
        default="HEAD",
        help="Git base ref used by --changed-only.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Directory for content-addressable parse cache and persisted baselines.",
    )
    parser.add_argument(
        "--skip-if-unchanged",
        action="store_true",
        help="Skip when a persisted successful baseline fingerprint matches current inputs.",
    )
    parser.add_argument(
        "--baseline-label",
        help="Named baseline label used by --skip-if-unchanged and persisted cache state.",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Canonically rewrite architecture/imports/exceptions.toml before linting.",
    )
    parser.add_argument(
        "--output-format",
        choices=list(OUTPUT_FORMATS),
        default="text",
        help="Render the final lint result as text/json/sarif/junit.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output file for the rendered report.",
    )
    return parser


def _emit_tool_result(
    result: ToolResult,
    *,
    output_format: str,
    output: Path | None,
) -> int:
    _emit_output(format_tool_result(result, output_format=output_format), output=output)
    return result.exit_code


def _changed_scan_scope(
    *,
    repo_root: Path,
    config: PolicyConfig,
    policy_path: Path,
    exceptions_path: Path,
    base_ref: str,
) -> tuple[set[Path], bool]:
    changed_paths = git_changed_files(repo_root, base_ref=base_ref)
    if not changed_paths:
        return set(), False

    resolved_policy = policy_path.resolve()
    resolved_exceptions = exceptions_path.resolve()
    sentinel_paths = {
        resolved_policy,
        resolved_exceptions,
        Path(__file__).resolve(),
    }
    if any(path in sentinel_paths for path in changed_paths):
        return set(iter_py_files(config.src_root)), True

    changed_under_src = filter_paths_under_root(changed_paths, config.src_root)
    if any(path.suffix == ".py" and not path.exists() for path in changed_under_src):
        return set(iter_py_files(config.src_root)), True

    changed_python = {
        path.resolve() for path in changed_under_src if path.suffix == ".py" and path.exists()
    }
    return changed_python, False


def _build_fingerprint(
    *,
    config: PolicyConfig,
    policy_path: Path,
    exceptions_path: Path,
    file_hashes: dict[Path, str],
    changed_files: set[Path],
    allow_type_checking: bool,
    fail_on_cycles: bool,
    scan_mode: str,
) -> str:
    return stable_json_hash(
        {
            "cache_version": CACHE_VERSION,
            "policy_version": config.version,
            "policy_sha256": file_sha256(policy_path) if policy_path.exists() else None,
            "exceptions_sha256": file_sha256(exceptions_path) if exceptions_path.exists() else None,
            "tool_sha256": file_sha256(Path(__file__)),
            "allow_type_checking": allow_type_checking,
            "fail_on_cycles": fail_on_cycles,
            "scan_mode": scan_mode,
            "changed_files": sorted(str(path) for path in changed_files),
            "source_hashes": {
                str(path.relative_to(config.src_root)): digest
                for path, digest in sorted(file_hashes.items(), key=lambda item: str(item[0]))
            },
        }
    )


def _filter_cycles_for_changed_files(
    cycles: list[list[str]],
    *,
    config: PolicyConfig,
    changed_files: set[Path],
) -> list[list[str]]:
    changed_packages: set[str] = set()
    for path in changed_files:
        result = module_name_for_path(config.src_root, path, config.internal_prefix)
        if result is None:
            continue
        module_name, _ = result
        changed_packages.add(package_for_module(module_name))
    if not changed_packages:
        return []
    return [group for group in cycles if any(package in changed_packages for package in group)]


def _apply_exceptions(
    ref: ImportRef,
    message: str,
    exceptions: CompiledExceptions,
    rel_path: str,
    target_root: str | None,
    today: datetime.date,
    allowed_exceptions: list[ExceptionMatch],
    expired_exceptions: list[ExceptionMatch],
    *,
    external_top: str | None = None,
) -> Violation | None:
    for exception in _exception_candidates(
        exceptions,
        target_root=target_root,
        external_top=external_top,
    ):
        if not exception_matches(
            exception,
            ref,
            rel_path=rel_path,
            target_module=ref.target_module,
            target_root=target_root,
            external_top=external_top,
        ):
            continue
        if exception.expires < today:
            expired_exceptions.append(ExceptionMatch(exception=exception, ref=ref, message=message))
            return Violation(
                ref=ref,
                code="ARCH000",
                message=message,
                expired_exception=exception,
            )
        allowed_exceptions.append(ExceptionMatch(exception=exception, ref=ref, message=message))
        return None
    return Violation(ref=ref, code="ARCH000", message=message)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        config = read_policy(args.policy)
        exceptions = read_exceptions(args.exceptions)
    except Exception as exc:
        return _emit_tool_result(
            ToolResult.failed(
                "lint.lint-imports",
                f"Config error: {exc}",
                exit_code=2,
            ),
            output_format=args.output_format,
            output=args.output,
        )

    if args.fix:
        fixes_applied = _canonicalize_exceptions_file(args.exceptions, exceptions)
    else:
        fixes_applied = 0

    if not config.src_root.exists():
        return _emit_tool_result(
            ToolResult.failed(
                "lint.lint-imports",
                f"Source root not found: {config.src_root}",
                exit_code=2,
            ),
            output_format=args.output_format,
            output=args.output,
        )

    repo_root = config.src_root.parent.resolve()
    cache_root = args.cache_dir.resolve() if args.cache_dir else default_cache_root(repo_root)

    changed_files: set[Path] = set()
    scan_mode = "full"
    if args.changed_only:
        changed_files, forced_full_scan = _changed_scan_scope(
            repo_root=repo_root,
            config=config,
            policy_path=args.policy,
            exceptions_path=args.exceptions,
            base_ref=args.git_base_ref,
        )
        if not changed_files:
            return _emit_tool_result(
                ToolResult(
                    tool="lint.lint-imports",
                    status="skipped",
                    summary="No changed Python files matched import gate scope.",
                    exit_code=0,
                    messages=(ToolMessage(level="skipped", message="no changed files"),),
                    data={"scan_mode": "changed-only", "changed_file_count": 0},
                ),
                output_format=args.output_format,
                output=args.output,
            )
        if not forced_full_scan:
            scan_mode = "changed-only"

    imports, internal_counts, module_graph, file_hashes, cache_stats = parse_imports(
        config,
        cache_root=cache_root,
    )

    baseline_label = args.baseline_label or (
        DEFAULT_BASELINE_LABEL if args.skip_if_unchanged else None
    )
    fingerprint = _build_fingerprint(
        config=config,
        policy_path=args.policy,
        exceptions_path=args.exceptions,
        file_hashes=file_hashes,
        changed_files=changed_files,
        allow_type_checking=args.allow_type_checking,
        fail_on_cycles=args.fail_on_cycles,
        scan_mode=scan_mode,
    )
    if (
        baseline_label
        and args.skip_if_unchanged
        and baseline_matches(
            cache_root,
            CACHE_NAMESPACE,
            baseline_label,
            fingerprint=fingerprint,
        )
    ):
        return _emit_tool_result(
            ToolResult(
                tool="lint.lint-imports",
                status="skipped",
                summary=f"Import gate unchanged for baseline {baseline_label!r}.",
                exit_code=0,
                messages=(
                    ToolMessage(
                        level="skipped",
                        message=f"baseline {baseline_label!r} matches current fingerprint",
                    ),
                ),
                data={"scan_mode": scan_mode, "baseline_label": baseline_label},
            ),
            output_format=args.output_format,
            output=args.output,
        )

    compiled_exceptions = compile_exceptions(exceptions)
    today = datetime.date.today()
    stdlib = stdlib_modules()
    selected_counts = (
        {path: count for path, count in internal_counts.items() if path in changed_files}
        if scan_mode == "changed-only"
        else internal_counts
    )

    violations: list[Violation] = []
    allowed_exceptions: list[ExceptionMatch] = []
    expired_exceptions: list[ExceptionMatch] = []
    unknown_roots: set[str] = set()

    for ref in imports:
        if scan_mode == "changed-only" and ref.source_file not in changed_files:
            continue
        if ref.in_type_checking and args.allow_type_checking:
            continue

        source_root = root_for_module(ref.source_module, config.internal_prefix)
        if source_root and source_root not in config.known_roots:
            unknown_roots.add(source_root)
            continue

        is_internal = is_internal_module(ref.target_module, config.internal_prefix)
        target_root = None
        external_top = None
        if is_internal:
            target_root = root_for_module(ref.target_module, config.internal_prefix)
            if target_root and target_root not in config.known_roots:
                unknown_roots.add(target_root)
                continue
        else:
            external_top = ref.target_module.split(".")[0]

        if source_root is None:
            continue

        rel_path = format_path(repo_root, ref.source_file)

        if is_internal:
            if target_root is None:
                continue

            target_parts = ref.target_module.split(".")
            if source_root != target_root:
                imports_internal_segment = any(part.startswith("_") for part in target_parts[2:])
                if imports_internal_segment:
                    message = (
                        f"{rel_path}:{ref.lineno} [ARCH006] forbidden internal subpackage import: "
                        f"{ref.source_module} -> {ref.target_module}. "
                        "Cross-root imports must go through public facades."
                    )
                    violation = _apply_exceptions(
                        ref,
                        message,
                        compiled_exceptions,
                        rel_path,
                        target_root,
                        today,
                        allowed_exceptions,
                        expired_exceptions,
                    )
                    if violation is not None:
                        violations.append(violation)
                    continue

            legacy_prefix = f"{config.internal_prefix}.{target_root}._legacy"
            if ref.target_module.startswith(legacy_prefix):
                source_is_legacy = f".{source_root}._legacy" in ref.source_module
                if source_root != target_root and not source_is_legacy:
                    message = (
                        f"{rel_path}:{ref.lineno} [ARCH003] forbidden legacy import: "
                        f"{source_root} -> {target_root}._legacy via {ref.target_module}"
                    )
                    violation = _apply_exceptions(
                        ref,
                        message,
                        compiled_exceptions,
                        rel_path,
                        target_root,
                        today,
                        allowed_exceptions,
                        expired_exceptions,
                    )
                    if violation is not None:
                        violations.append(violation)
                continue

            fabric_legacy_prefixes = (
                f"{config.internal_prefix}.fabric.io.graph_store",
                f"{config.internal_prefix}.fabric.materializer",
                f"{config.internal_prefix}.fabric.schema",
                f"{config.internal_prefix}.fabric.udf",
            )
            if any(
                ref.target_module == prefix or ref.target_module.startswith(f"{prefix}.")
                for prefix in fabric_legacy_prefixes
            ):
                source_is_fabric = ref.source_module.startswith(f"{config.internal_prefix}.fabric")
                if not source_is_fabric:
                    message = (
                        f"{rel_path}:{ref.lineno} [ARCH005] forbidden legacy fabric import: "
                        f"{ref.source_module} -> {ref.target_module}. "
                        "Use polisyos.fabric.world or curated fabric entrypoints."
                    )
                    violation = _apply_exceptions(
                        ref,
                        message,
                        compiled_exceptions,
                        rel_path,
                        target_root,
                        today,
                        allowed_exceptions,
                        expired_exceptions,
                    )
                    if violation is not None:
                        violations.append(violation)
                continue

            is_fabric_world_deep_import = ref.target_module.startswith(
                f"{config.internal_prefix}.fabric.world.store"
            ) or ref.target_module.startswith(f"{config.internal_prefix}.fabric.world.materialize")
            if is_fabric_world_deep_import:
                source_is_allowed = ref.source_module.startswith(
                    f"{config.internal_prefix}.fabric.world"
                )
                if not source_is_allowed:
                    message = (
                        f"{rel_path}:{ref.lineno} [ARCH004] forbidden deep import: "
                        f"{ref.source_module} -> {ref.target_module}. "
                        "Use polisyos.fabric.world facade exports."
                    )
                    violation = _apply_exceptions(
                        ref,
                        message,
                        compiled_exceptions,
                        rel_path,
                        target_root,
                        today,
                        allowed_exceptions,
                        expired_exceptions,
                    )
                    if violation is not None:
                        violations.append(violation)
                continue

            allowed = config.internal_allow.get(source_root, set())
            if "*" in allowed or target_root in allowed:
                continue

            message = (
                f"{rel_path}:{ref.lineno} [ARCH001] forbidden internal import: "
                f"{source_root} -> {target_root} via {ref.target_module} "
                f"(allowed={format_allowed_internal(allowed)})"
            )
            violation = _apply_exceptions(
                ref,
                message,
                compiled_exceptions,
                rel_path,
                target_root,
                today,
                allowed_exceptions,
                expired_exceptions,
            )
            if violation is not None:
                violations.append(violation)
            continue

        if source_root == "ir":
            allowed_external = config.external_allow.get("ir", set())
            if external_top in stdlib or external_top in allowed_external:
                continue
            message = (
                f"{rel_path}:{ref.lineno} [ARCH002] forbidden external import in ir: "
                f"{external_top} (allowed={format_allowed_external(allowed_external)})"
            )
            violation = _apply_exceptions(
                ref,
                message,
                compiled_exceptions,
                rel_path,
                None,
                today,
                allowed_exceptions,
                expired_exceptions,
                external_top=external_top,
            )
            if violation is not None:
                violations.append(violation)

    if unknown_roots:
        return _emit_tool_result(
            ToolResult.failed(
                "lint.lint-imports",
                "Config error: unknown internal roots encountered",
                exit_code=2,
                unknown_roots=sorted(unknown_roots),
            ),
            output_format=args.output_format,
            output=args.output,
        )

    package_graph: dict[str, set[str]] = {}
    for source, targets in module_graph.items():
        source_pkg = package_for_module(source)
        package_graph.setdefault(source_pkg, set())
        for target in targets:
            target_pkg = package_for_module(target)
            if source_pkg == target_pkg:
                continue
            package_graph[source_pkg].add(target_pkg)

    sccs = strongly_connected_components(package_graph)
    cycles = [sorted(group) for group in sccs if len(group) > 1]
    if scan_mode == "changed-only":
        cycles = _filter_cycles_for_changed_files(
            cycles, config=config, changed_files=changed_files
        )
    unregistered_cycle_signatures = frozenset(
        tuple(sorted(group))
        for group in cycles
        if tuple(sorted(group)) not in config.package_cycle_baselines
    )

    exit_code = 0
    if violations:
        exit_code = 1
    if args.fail_on_cycles and unregistered_cycle_signatures:
        exit_code = 1

    context = LintReportContext(
        config=config,
        repo_root=repo_root,
        policy_path=args.policy,
        exceptions_path=args.exceptions,
        top=args.top,
        fail_on_cycles=args.fail_on_cycles,
        scan_mode=scan_mode,
        changed_file_count=len(changed_files),
        cache_hits=cache_stats.hits,
        cache_misses=cache_stats.misses,
        fixes_applied=fixes_applied,
        enforced_cycle_signatures=unregistered_cycle_signatures,
    )

    if baseline_label is not None and exit_code == 0:
        persist_baseline(
            cache_root,
            CACHE_NAMESPACE,
            baseline_label,
            fingerprint=fingerprint,
            exit_code=exit_code,
            metadata={
                "scan_mode": scan_mode,
                "changed_file_count": len(changed_files),
            },
        )

    if args.output_format == "text":
        _emit_output(
            _text_report(
                context=context,
                violations=violations,
                allowed_exceptions=allowed_exceptions,
                cycles=cycles,
                internal_counts=selected_counts,
            ),
            output=args.output,
        )
        return exit_code

    result = _structured_result(
        context=context,
        violations=violations,
        allowed_exceptions=allowed_exceptions,
        cycles=cycles,
        internal_counts=selected_counts,
        exit_code=exit_code,
    )
    _emit_output(format_tool_result(result, output_format=args.output_format), output=args.output)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
