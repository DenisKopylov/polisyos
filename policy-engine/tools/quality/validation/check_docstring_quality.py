#!/usr/bin/env python3
"""Fail CI when public API docstrings regress to generic placeholders.

The checker scans two public documentation surfaces without importing package code:

* mkdocstrings references under ``docs/reference/**``;
* symbols exported from package ``__init__.py`` facades via ``__all__``.

It reports placeholder summaries such as ``Public ... module API.``, ``... helper.``,
``... data model.``, and ``... implementation.`` and computes semantic-docstring coverage
for the inspected public symbol set.
"""

from __future__ import annotations

import argparse
import ast
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from tools.lib.imports import repo_root_from

DOCS_REFERENCE_PATTERN = re.compile(r"^:{3,}\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\b")
PLACEHOLDER_SUMMARY_PATTERNS = (
    re.compile(r"^Public\s+.+\s+(?:module|package)\s+API\.$", re.IGNORECASE),
    re.compile(r"^.+\s+helper\.$", re.IGNORECASE),
    re.compile(r"^.+\s+data model\.$", re.IGNORECASE),
    re.compile(r"^.+\s+implementation\.$", re.IGNORECASE),
)
PRAGMA_RE = re.compile(r"#\s*docstring-quality:\s*(?:allow-placeholder|ignore)\b", re.IGNORECASE)


@dataclass(frozen=True)
class TargetRef:
    """Point to the module or symbol that should carry a semantic docstring."""

    module: str
    qualname: str | None

    @property
    def fqname(self) -> str:
        """Return a stable fully qualified name for allowlists and reports."""
        if self.qualname:
            return f"{self.module}.{self.qualname}"
        return self.module


@dataclass(frozen=True)
class DocstringSubject:
    """Describe one inspected public module, class, function, or method."""

    ref: TargetRef
    file_path: Path
    lineno: int
    kind: str
    source: str
    docstring: str | None
    pragma_allowed: bool


@dataclass(frozen=True)
class DocstringViolation:
    """Record one placeholder-docstring violation emitted by the checker."""

    subject: DocstringSubject
    summary: str
    reason: str


@dataclass(frozen=True)
class ResolvedTarget:
    """Represent one public symbol resolved from a facade export or docs target."""

    ref: TargetRef
    origin: str


@dataclass(frozen=True)
class ModuleFile:
    """Cache source metadata for a parsed Python module."""

    module: str
    file_path: Path
    is_package: bool
    source_text: str
    lines: tuple[str, ...]
    tree: ast.Module


@dataclass(frozen=True)
class ModuleFacade:
    """Store static export metadata extracted from one module AST."""

    exported_names: tuple[str, ...] | None
    import_map: Mapping[str, TargetRef]
    nested_export_maps: Mapping[str, tuple[str, ...]]
    top_level_symbols: Mapping[str, ast.AST]
    module_doc_lineno: int


@dataclass(frozen=True)
class CoverageSummary:
    """Summarize semantic-docstring coverage for one reporting scope."""

    scope: str
    total: int
    semantic: int

    @property
    def percent(self) -> float:
        """Return semantic coverage percentage for the scope."""
        if self.total == 0:
            return 100.0
        return self.semantic / self.total * 100.0


def module_name_for_path(src_root: Path, file_path: Path) -> tuple[str, bool] | None:
    """Return the dotted module name for a file under ``src_root``."""
    relative = file_path.relative_to(src_root)
    parts = list(relative.parts)
    if not parts:
        return None
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
        return ".".join(parts), True
    parts[-1] = parts[-1].removesuffix(".py")
    return ".".join(parts), False


def resolve_relative_module(
    current_module: str, is_package: bool, node: ast.ImportFrom
) -> str | None:
    """Resolve an ``ImportFrom`` target without importing the module."""
    if node.level == 0:
        return node.module
    package_parts = current_module.split(".")
    if not is_package:
        package_parts = package_parts[:-1]
    if node.level - 1 > len(package_parts):
        return None
    base_parts = package_parts[: len(package_parts) - (node.level - 1)]
    if node.module:
        base_parts.extend(node.module.split("."))
    return ".".join(part for part in base_parts if part)


def iter_python_modules(src_root: Path) -> dict[str, Path]:
    """Index every importable Python module under ``src_root``."""
    module_paths: dict[str, Path] = {}
    for file_path in src_root.rglob("*.py"):
        if "__pycache__" in file_path.parts:
            continue
        result = module_name_for_path(src_root, file_path)
        if result is None:
            continue
        module_name, _ = result
        module_paths[module_name] = file_path
    return module_paths


def load_module_file(module: str, module_paths: Mapping[str, Path]) -> ModuleFile | None:
    """Parse one module and return reusable source metadata."""
    file_path = module_paths.get(module)
    if file_path is None:
        return None
    source_text = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(file_path))
    return ModuleFile(
        module=module,
        file_path=file_path,
        is_package=file_path.name == "__init__.py",
        source_text=source_text,
        lines=tuple(source_text.splitlines()),
        tree=tree,
    )


def literal_string(value: ast.AST) -> str | None:
    """Evaluate a string AST node when it is a plain constant."""
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def literal_string_sequence(value: ast.AST) -> tuple[str, ...] | None:
    """Evaluate a literal list/tuple/set of strings."""
    if not isinstance(value, ast.List | ast.Tuple | ast.Set):
        return None
    items: list[str] = []
    for elt in value.elts:
        item = literal_string(elt)
        if item is None:
            return None
        items.append(item)
    return tuple(items)


def literal_symbol_map(value: ast.AST) -> dict[str, TargetRef] | None:
    """Evaluate dict literals used by lazy facade maps."""
    if not isinstance(value, ast.Dict):
        return None
    mapping: dict[str, TargetRef] = {}
    for key_node, value_node in zip(value.keys, value.values, strict=True):
        key = literal_string(key_node) if key_node is not None else None
        if key is None:
            return None
        module = literal_string(value_node)
        if module is not None:
            mapping[key] = TargetRef(module=module, qualname=key)
            continue
        if isinstance(value_node, ast.Tuple) and len(value_node.elts) == 2:
            module_name = literal_string(value_node.elts[0])
            attr_name = literal_string(value_node.elts[1])
            if module_name is None or attr_name is None:
                return None
            mapping[key] = TargetRef(module=module_name, qualname=attr_name)
            continue
        return None
    return mapping


def literal_module_symbol_groups(value: ast.AST) -> dict[str, tuple[str, ...]] | None:
    """Evaluate dict literals like ``{".mod": ("Symbol", ...)}``."""
    if not isinstance(value, ast.Dict):
        return None
    mapping: dict[str, tuple[str, ...]] = {}
    for key_node, value_node in zip(value.keys, value.values, strict=True):
        key = literal_string(key_node) if key_node is not None else None
        values = literal_string_sequence(value_node)
        if key is None or values is None:
            return None
        mapping[key] = values
    return mapping


def resolve_sorted_name_expr(value: ast.AST) -> str | None:
    """Return the variable name wrapped by ``sorted(...)`` or ``None``."""
    if not isinstance(value, ast.Call):
        return None
    if not isinstance(value.func, ast.Name) or value.func.id != "sorted":
        return None
    if len(value.args) != 1 or value.keywords:
        return None
    arg = value.args[0]
    if isinstance(arg, ast.Name):
        return arg.id
    return None


def extract_facade(module_file: ModuleFile) -> ModuleFacade:
    """Collect top-level exports, re-export maps, and source aliases from one module."""
    constants: dict[str, tuple[str, ...] | dict[str, TargetRef] | dict[str, tuple[str, ...]]] = {}
    import_map: dict[str, TargetRef] = {}
    exported_names: tuple[str, ...] | None = None
    nested_export_maps: dict[str, tuple[str, ...]] = {}
    top_level_symbols: dict[str, ast.AST] = {}
    module_doc_lineno = 1

    if (
        module_file.tree.body
        and isinstance(module_file.tree.body[0], ast.Expr)
        and isinstance(module_file.tree.body[0].value, ast.Constant)
        and isinstance(module_file.tree.body[0].value.value, str)
    ):
        module_doc_lineno = module_file.tree.body[0].lineno

    for node in module_file.tree.body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            top_level_symbols[node.name] = node
            continue

        if isinstance(node, ast.ImportFrom):
            module_name = resolve_relative_module(module_file.module, module_file.is_package, node)
            if module_name is None:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                local_name = alias.asname or alias.name
                import_map[local_name] = TargetRef(module=module_name, qualname=alias.name)
            continue

        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".")[-1]
                import_map[local_name] = TargetRef(module=alias.name, qualname=None)
            continue

        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue

        targets: list[str] = []
        value = node.value
        if value is None:
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    targets.append(target.id)
        elif isinstance(node.target, ast.Name):
            targets.append(node.target.id)

        if not targets:
            continue

        string_sequence = literal_string_sequence(value)
        symbol_map = literal_symbol_map(value)
        module_groups = literal_module_symbol_groups(value)
        sorted_name = resolve_sorted_name_expr(value)

        for target_name in targets:
            if string_sequence is not None:
                constants[target_name] = string_sequence
                if target_name == "__all__":
                    exported_names = string_sequence
                continue

            if symbol_map is not None:
                constants[target_name] = symbol_map
                for local_name, ref in symbol_map.items():
                    import_map.setdefault(local_name, ref)
                continue

            if module_groups is not None:
                constants[target_name] = module_groups
                nested_export_maps.update(module_groups)
                for rel_module, names in module_groups.items():
                    if rel_module.startswith("."):
                        module_name = f"{module_file.module}{rel_module}"
                    else:
                        module_name = rel_module
                    for export_name in names:
                        import_map.setdefault(
                            export_name,
                            TargetRef(module=module_name, qualname=export_name),
                        )
                continue

            if sorted_name is not None and target_name == "__all__":
                source_value = constants.get(sorted_name)
                if isinstance(source_value, dict) or isinstance(source_value, tuple):
                    exported_names = tuple(sorted(source_value))

    return ModuleFacade(
        exported_names=exported_names,
        import_map=import_map,
        nested_export_maps=nested_export_maps,
        top_level_symbols=top_level_symbols,
        module_doc_lineno=module_doc_lineno,
    )


def parse_allowlist(path: Path | None) -> set[str]:
    """Load fully qualified names exempted from placeholder checks."""
    if path is None:
        return set()
    allowlist: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        allowlist.add(line)
    return allowlist


def has_pragma(module_file: ModuleFile, lineno: int) -> bool:
    """Return whether a symbol has an inline placeholder allow pragma."""
    index = lineno - 1
    for candidate in (index, index - 1, index - 2):
        if 0 <= candidate < len(module_file.lines) and PRAGMA_RE.search(
            module_file.lines[candidate]
        ):
            return True
    return False


def first_docstring_line(docstring: str | None) -> str:
    """Return the first non-empty docstring line for summary checks."""
    if not docstring:
        return ""
    for line in docstring.strip().splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def is_placeholder_docstring(docstring: str | None) -> tuple[bool, str]:
    """Return whether ``docstring`` starts with one of the generic placeholder summaries."""
    summary = first_docstring_line(docstring)
    if not summary:
        return False, ""
    for pattern in PLACEHOLDER_SUMMARY_PATTERNS:
        if pattern.fullmatch(summary):
            return True, summary
    return False, summary


def classify_symbol_kind(node: ast.AST | None, qualname: str | None) -> str:
    """Map an AST node into a user-facing report kind label."""
    if qualname is None:
        return "module"
    if isinstance(node, ast.ClassDef):
        return "class"
    if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
        return "function" if "." not in qualname else "method"
    return "symbol"


def walk_class_methods(
    class_node: ast.ClassDef,
    module_file: ModuleFile,
    class_ref: TargetRef,
    source: str,
) -> Iterable[DocstringSubject]:
    """Yield public method docstrings under one exported class."""
    for node in class_node.body:
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if node.name.startswith("_"):
            continue
        qualname = f"{class_ref.qualname}.{node.name}" if class_ref.qualname else node.name
        yield DocstringSubject(
            ref=TargetRef(module=class_ref.module, qualname=qualname),
            file_path=module_file.file_path,
            lineno=node.lineno,
            kind="method",
            source=source,
            docstring=ast.get_docstring(node, clean=True),
            pragma_allowed=has_pragma(module_file, node.lineno),
        )


def inspect_target(
    target: ResolvedTarget,
    module_paths: Mapping[str, Path],
    module_cache: dict[str, ModuleFile],
    facade_cache: dict[str, ModuleFacade],
) -> list[DocstringSubject]:
    """Inspect one module or symbol target and return public docstring subjects."""
    module_file = module_cache.get(target.ref.module)
    if module_file is None:
        module_file = load_module_file(target.ref.module, module_paths)
        if module_file is None:
            return []
        module_cache[target.ref.module] = module_file

    facade = facade_cache.get(target.ref.module)
    if facade is None:
        facade = extract_facade(module_file)
        facade_cache[target.ref.module] = facade

    subjects: list[DocstringSubject] = []
    if target.ref.qualname is None:
        subjects.append(
            DocstringSubject(
                ref=target.ref,
                file_path=module_file.file_path,
                lineno=facade.module_doc_lineno,
                kind="module",
                source=target.origin,
                docstring=ast.get_docstring(module_file.tree, clean=True),
                pragma_allowed=has_pragma(module_file, facade.module_doc_lineno),
            )
        )
        member_names = facade.exported_names
        if member_names is None:
            member_names = tuple(
                name for name in facade.top_level_symbols if not name.startswith("_")
            )
        for member_name in member_names:
            resolved_member = resolve_exported_symbol(
                target.ref.module,
                member_name,
                module_paths,
                facade,
            )
            member_target = ResolvedTarget(
                ref=resolved_member,
                origin=f"{target.origin} -> {member_name}",
            )
            subjects.extend(
                inspect_symbol_target(
                    member_target,
                    module_paths,
                    module_cache,
                    facade_cache,
                )
            )
        return subjects

    subjects.extend(inspect_symbol_target(target, module_paths, module_cache, facade_cache))
    return subjects


def inspect_symbol_target(
    target: ResolvedTarget,
    module_paths: Mapping[str, Path],
    module_cache: dict[str, ModuleFile],
    facade_cache: dict[str, ModuleFacade],
) -> list[DocstringSubject]:
    """Inspect one concrete module member and recurse into public class methods."""
    module_file = module_cache.get(target.ref.module)
    if module_file is None:
        module_file = load_module_file(target.ref.module, module_paths)
        if module_file is None:
            return []
        module_cache[target.ref.module] = module_file

    facade = facade_cache.get(target.ref.module)
    if facade is None:
        facade = extract_facade(module_file)
        facade_cache[target.ref.module] = facade

    if target.ref.qualname is None:
        return [
            DocstringSubject(
                ref=target.ref,
                file_path=module_file.file_path,
                lineno=facade.module_doc_lineno,
                kind="module",
                source=target.origin,
                docstring=ast.get_docstring(module_file.tree, clean=True),
                pragma_allowed=has_pragma(module_file, facade.module_doc_lineno),
            )
        ]

    root_name = target.ref.qualname.split(".", 1)[0]
    node = facade.top_level_symbols.get(root_name)
    if node is None and root_name in facade.import_map:
        alias_ref = facade.import_map[root_name]
        alias_target = ResolvedTarget(
            ref=TargetRef(module=alias_ref.module, qualname=alias_ref.qualname),
            origin=target.origin,
        )
        return inspect_symbol_target(alias_target, module_paths, module_cache, facade_cache)
    if (
        node is None
        and target.ref.qualname == root_name
        and (target.ref.module + "." + root_name) in module_paths
    ):
        return inspect_symbol_target(
            ResolvedTarget(
                ref=TargetRef(module=f"{target.ref.module}.{root_name}", qualname=None),
                origin=target.origin,
            ),
            module_paths,
            module_cache,
            facade_cache,
        )
    if node is None:
        return []

    subjects = [
        DocstringSubject(
            ref=target.ref,
            file_path=module_file.file_path,
            lineno=node.lineno,
            kind=classify_symbol_kind(node, target.ref.qualname),
            source=target.origin,
            docstring=ast.get_docstring(node, clean=True),
            pragma_allowed=has_pragma(module_file, node.lineno),
        )
    ]
    if isinstance(node, ast.ClassDef) and target.ref.qualname == root_name:
        subjects.extend(walk_class_methods(node, module_file, target.ref, target.origin))
    return subjects


def resolve_exported_symbol(
    package_module: str,
    export_name: str,
    module_paths: Mapping[str, Path],
    facade: ModuleFacade,
) -> TargetRef:
    """Resolve one ``__all__`` entry to its implementation module or object."""
    mapped = facade.import_map.get(export_name)
    if mapped is not None:
        return mapped
    submodule_name = f"{package_module}.{export_name}"
    if submodule_name in module_paths:
        return TargetRef(module=submodule_name, qualname=None)
    return TargetRef(module=package_module, qualname=export_name)


def collect_reference_targets(
    docs_root: Path, module_paths: Mapping[str, Path]
) -> list[ResolvedTarget]:
    """Extract mkdocstrings targets from ``docs/reference/**``."""
    targets: list[ResolvedTarget] = []
    for docs_file in sorted(docs_root.rglob("*.md")):
        for raw_line in docs_file.read_text(encoding="utf-8").splitlines():
            match = DOCS_REFERENCE_PATTERN.match(raw_line.strip())
            if match is None:
                continue
            dotted_target = match.group(1)
            ref = resolve_dotted_target(dotted_target, module_paths)
            if ref is None:
                continue
            origin = f"docs:{docs_file.relative_to(docs_root.parent)}"
            targets.append(ResolvedTarget(ref=ref, origin=origin))
    return dedupe_targets(targets)


def collect_facade_targets(
    src_root: Path, module_paths: Mapping[str, Path]
) -> list[ResolvedTarget]:
    """Collect package facade modules and exports from ``__init__.py`` files."""
    targets: list[ResolvedTarget] = []
    module_cache: dict[str, ModuleFile] = {}
    facade_cache: dict[str, ModuleFacade] = {}

    for init_file in sorted(src_root.rglob("__init__.py")):
        result = module_name_for_path(src_root, init_file)
        if result is None:
            continue
        module_name, _ = result
        targets.append(
            ResolvedTarget(ref=TargetRef(module=module_name, qualname=None), origin="facade")
        )
        module_file = module_cache.get(module_name)
        if module_file is None:
            module_file = load_module_file(module_name, module_paths)
            if module_file is None:
                continue
            module_cache[module_name] = module_file
        facade = facade_cache.get(module_name)
        if facade is None:
            facade = extract_facade(module_file)
            facade_cache[module_name] = facade
        if facade.exported_names is None:
            continue
        for export_name in facade.exported_names:
            ref = resolve_exported_symbol(module_name, export_name, module_paths, facade)
            targets.append(ResolvedTarget(ref=ref, origin=f"facade:{module_name}"))

    return dedupe_targets(targets)


def resolve_dotted_target(target: str, module_paths: Mapping[str, Path]) -> TargetRef | None:
    """Split a mkdocstrings dotted target into module and optional qualname."""
    parts = target.split(".")
    for end in range(len(parts), 0, -1):
        module_name = ".".join(parts[:end])
        if module_name not in module_paths:
            continue
        qualname = ".".join(parts[end:]) or None
        return TargetRef(module=module_name, qualname=qualname)
    return None


def dedupe_targets(targets: Iterable[ResolvedTarget]) -> list[ResolvedTarget]:
    """Deduplicate targets by fqname while preserving the first source label."""
    deduped: dict[str, ResolvedTarget] = {}
    for target in targets:
        deduped.setdefault(target.ref.fqname, target)
    return list(deduped.values())


def package_bucket(fqname: str) -> str:
    """Bucket a symbol into a top-level package for second-pass reporting."""
    parts = fqname.split(".")
    if len(parts) >= 2:
        return ".".join(parts[:2])
    return fqname


def scope_matches(subject: DocstringSubject, scope: str) -> bool:
    """Return whether a subject should count toward the selected coverage scope."""
    if scope == "all":
        return True
    if scope == "public-surface":
        return subject.kind != "method"
    raise ValueError(f"Unsupported coverage scope: {scope}")


def check_docstrings(
    subjects: Iterable[DocstringSubject],
    allowlist: set[str],
) -> tuple[list[DocstringViolation], Counter[str], CoverageSummary, CoverageSummary]:
    """Evaluate placeholder violations and semantic coverage counters."""
    violations: list[DocstringViolation] = []
    needs_second_pass: Counter[str] = Counter()
    total_public_symbols = 0
    semantic_docstrings = 0
    public_surface_total = 0
    public_surface_semantic = 0

    for subject in subjects:
        total_public_symbols += 1
        placeholder, summary = is_placeholder_docstring(subject.docstring)
        has_semantic_docstring = bool(subject.docstring) and not placeholder
        if scope_matches(subject, "public-surface"):
            public_surface_total += 1
            if has_semantic_docstring:
                public_surface_semantic += 1
        if has_semantic_docstring:
            semantic_docstrings += 1
            continue
        needs_second_pass[package_bucket(subject.ref.fqname)] += 1
        if placeholder and subject.ref.fqname not in allowlist and not subject.pragma_allowed:
            violations.append(
                DocstringViolation(
                    subject=subject,
                    summary=summary,
                    reason="placeholder summary matches a banned generic docstring pattern",
                )
            )

    return (
        violations,
        needs_second_pass,
        CoverageSummary(scope="all", total=total_public_symbols, semantic=semantic_docstrings),
        CoverageSummary(
            scope="public-surface",
            total=public_surface_total,
            semantic=public_surface_semantic,
        ),
    )


def format_violation(repo_root: Path, violation: DocstringViolation) -> str:
    """Render one violation line for CLI output."""
    try:
        relative = violation.subject.file_path.relative_to(repo_root)
    except ValueError:
        relative = violation.subject.file_path
    return (
        f"{relative}:{violation.subject.lineno}: {violation.subject.ref.fqname} "
        f"[{violation.subject.kind}] {violation.reason}; "
        f"summary={violation.summary!r}; source={violation.subject.source}"
    )


def inspect_public_subjects(
    docs_root: Path,
    src_root: Path,
) -> list[DocstringSubject]:
    """Collect all inspectable public docstring subjects from docs and facades."""
    module_paths = iter_python_modules(src_root)
    module_cache: dict[str, ModuleFile] = {}
    facade_cache: dict[str, ModuleFacade] = {}
    subjects: dict[str, DocstringSubject] = {}
    targets = collect_reference_targets(docs_root, module_paths) + collect_facade_targets(
        src_root,
        module_paths,
    )
    for target in dedupe_targets(targets):
        for subject in inspect_target(target, module_paths, module_cache, facade_cache):
            subjects.setdefault(subject.ref.fqname, subject)
    return list(subjects.values())


def filter_subjects_by_prefix(
    subjects: Iterable[DocstringSubject],
    module_prefixes: Iterable[str],
) -> list[DocstringSubject]:
    """Keep only subjects rooted under the selected module prefixes."""

    prefixes = tuple(prefix for prefix in module_prefixes if prefix)
    if not prefixes:
        return list(subjects)
    return [
        subject
        for subject in subjects
        if any(subject.ref.fqname.startswith(prefix) for prefix in prefixes)
    ]


def print_report(
    repo_root: Path,
    violations: list[DocstringViolation],
    package_gaps: Counter[str],
    overall_coverage: CoverageSummary,
    public_surface_coverage: CoverageSummary,
    *,
    show_package_limit: int,
) -> None:
    """Print a concise CLI report for docs QA and second-pass planning."""
    print("Semantic docstring quality report")
    print(f"- inspected public symbols: {overall_coverage.total}")
    print(
        "- semantic docstring coverage (all subjects): "
        f"{overall_coverage.semantic}/{overall_coverage.total} ({overall_coverage.percent:.1f}%)"
    )
    print(
        "- semantic docstring coverage (public surface): "
        f"{public_surface_coverage.semantic}/{public_surface_coverage.total} "
        f"({public_surface_coverage.percent:.1f}%)"
    )
    print(f"- placeholder violations: {len(violations)}")
    if package_gaps:
        print("- packages needing second pass:")
        for package_name, count in package_gaps.most_common(show_package_limit):
            print(f"  - {package_name}: {count}")
    if violations:
        print()
        print("Placeholder docstrings:")
        for violation in violations:
            print(f"- {format_violation(repo_root, violation)}")


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the checker CLI parser."""
    parser = argparse.ArgumentParser(
        description="Check semantic quality of public API docstrings without importing package code.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=repo_root_from(__file__),
        help="Repository root containing docs/ and src/ directories.",
    )
    parser.add_argument(
        "--src-root",
        type=Path,
        default=None,
        help="Python source root. Defaults to <repo-root>/src.",
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=None,
        help="Reference docs root. Defaults to <repo-root>/docs/reference.",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=None,
        help="Optional allowlist file with fully qualified names, one per line.",
    )
    parser.add_argument(
        "--show-package-limit",
        type=int,
        default=20,
        help="Maximum number of package buckets shown in the second-pass summary.",
    )
    parser.add_argument(
        "--coverage-scope",
        choices=("all", "public-surface"),
        default="all",
        help="Coverage scope used when applying --minimum-coverage.",
    )
    parser.add_argument(
        "--minimum-coverage",
        type=float,
        default=None,
        help="Optional minimum semantic-docstring coverage percentage for the selected scope.",
    )
    parser.add_argument(
        "--module-prefix",
        action="append",
        default=[],
        help=(
            "Optional dotted module prefix filter. Repeat to scope checks to the "
            "changed public API surface."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the placeholder checker and return a CI-friendly exit code."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    src_root = (args.src_root or repo_root / "src").resolve()
    docs_root = (args.docs_root or repo_root / "docs" / "reference").resolve()
    allowlist_path = args.allowlist.resolve() if args.allowlist is not None else None

    allowlist = parse_allowlist(allowlist_path)
    subjects = inspect_public_subjects(docs_root=docs_root, src_root=src_root)
    subjects = filter_subjects_by_prefix(subjects, args.module_prefix)
    if not subjects:
        if args.module_prefix:
            print("Semantic docstring quality report")
            print("- inspected public symbols: 0")
            print(
                "- note: no public docstring subjects matched "
                f"the requested module prefixes: {', '.join(args.module_prefix)}"
            )
            return 0
    violations, package_gaps, overall_coverage, public_surface_coverage = check_docstrings(
        subjects,
        allowlist,
    )
    print_report(
        repo_root=repo_root,
        violations=violations,
        package_gaps=package_gaps,
        overall_coverage=overall_coverage,
        public_surface_coverage=public_surface_coverage,
        show_package_limit=args.show_package_limit,
    )
    scoped_coverage = overall_coverage if args.coverage_scope == "all" else public_surface_coverage
    coverage_failed = (
        args.minimum_coverage is not None and scoped_coverage.percent < args.minimum_coverage
    )
    if coverage_failed:
        print(
            f"- coverage gate failed: scope={args.coverage_scope!r} "
            f"minimum={args.minimum_coverage:.1f}% actual={scoped_coverage.percent:.1f}%"
        )
    return 1 if violations or coverage_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
