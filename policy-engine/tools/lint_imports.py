#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path

INTERNAL_PREFIX = "polisyos"

LAYER_BY_PREFIX = {
    "polisyos.ir": "ir",
    "polisyos.foundry": "foundry",
    "polisyos.fabric": "fabric",
    "polisyos.scientist": "scientist",
    "polisyos.runtime": "runtime",
    "polisyos.common": "common",
}

FORBIDDEN_LAYER_EDGES = {
    ("foundry", "fabric"),
    ("fabric", "scientist"),
}


@dataclass(frozen=True)
class ImportRef:
    source_file: Path
    source_module: str
    target_module: str
    lineno: int
    in_type_checking: bool


def is_type_checking_test(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "TYPE_CHECKING"
    if isinstance(node, ast.Attribute):
        return node.attr == "TYPE_CHECKING"
    return False


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
    def __init__(self, source_file: Path, source_module: str, is_package: bool) -> None:
        self.source_file = source_file
        self.source_module = source_module
        self.is_package = is_package
        self.imports: list[ImportRef] = []
        self.internal_targets: set[str] = set()
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
        if module:
            self._record_import(module, node.lineno)

    def _record_import(self, module: str, lineno: int) -> None:
        if module != INTERNAL_PREFIX and not module.startswith(f"{INTERNAL_PREFIX}."):
            return
        self.imports.append(
            ImportRef(
                source_file=self.source_file,
                source_module=self.source_module,
                target_module=module,
                lineno=lineno,
                in_type_checking=self.in_type_checking,
            )
        )
        self.internal_targets.add(module)


def layer_for_module(module: str) -> str | None:
    for prefix, layer in sorted(LAYER_BY_PREFIX.items(), key=lambda item: len(item[0]), reverse=True):
        if module == prefix or module.startswith(f"{prefix}."):
            return layer
    return None


def module_name_for_path(src_root: Path, file_path: Path) -> tuple[str, bool] | None:
    relative = file_path.relative_to(src_root)
    parts = list(relative.parts)
    if not parts:
        return None
    if parts[0] != INTERNAL_PREFIX:
        if src_root.name == INTERNAL_PREFIX:
            parts = [INTERNAL_PREFIX] + parts
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
    return files


def parse_imports(src_root: Path) -> tuple[list[ImportRef], dict[Path, int], dict[str, set[str]]]:
    imports: list[ImportRef] = []
    internal_counts: dict[Path, int] = {}
    module_graph: dict[str, set[str]] = {}

    for file_path in iter_py_files(src_root):
        result = module_name_for_path(src_root, file_path)
        if result is None:
            continue
        module_name, is_package = result
        module_graph.setdefault(module_name, set())
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        collector = ImportCollector(file_path, module_name, is_package)
        collector.visit(tree)
        imports.extend(collector.imports)
        internal_counts[file_path] = len(collector.internal_targets)
        for ref in collector.imports:
            if ref.in_type_checking:
                continue
            module_graph[module_name].add(ref.target_module)

    return imports, internal_counts, module_graph


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

    for node in sorted(graph.keys()):
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Check internal import boundaries and report cycles.")
    parser.add_argument("--src-root", type=Path, default=Path("src"), help="Source root")
    parser.add_argument("--top", type=int, default=10, help="Show top N god files")
    parser.add_argument("--fail-on-cycles", action="store_true", help="Fail on import cycles")
    parser.add_argument(
        "--fail-on-type-checking",
        action="store_true",
        help="Fail on forbidden edges inside TYPE_CHECKING blocks",
    )
    args = parser.parse_args()

    if not args.src_root.exists():
        print(f"Source root not found: {args.src_root}")
        return 2

    imports, internal_counts, module_graph = parse_imports(args.src_root)
    runtime_forbidden: list[ImportRef] = []
    type_checking_forbidden: list[ImportRef] = []

    for ref in imports:
        src_layer = layer_for_module(ref.source_module)
        dst_layer = layer_for_module(ref.target_module)
        if not src_layer or not dst_layer:
            continue
        if (src_layer, dst_layer) in FORBIDDEN_LAYER_EDGES:
            if ref.in_type_checking:
                type_checking_forbidden.append(ref)
            else:
                runtime_forbidden.append(ref)

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

    repo_root = args.src_root.parent

    print("Import gate report")
    print("")
    if runtime_forbidden:
        print("Forbidden edges (runtime):")
        for ref in runtime_forbidden:
            src_layer = layer_for_module(ref.source_module)
            dst_layer = layer_for_module(ref.target_module)
            file_path = format_path(repo_root, ref.source_file)
            print(
                f"- {file_path}:{ref.lineno} {src_layer} -> {dst_layer} via {ref.target_module}"
            )
        print("")
    else:
        print("Forbidden edges (runtime): none")
        print("")

    if type_checking_forbidden:
        print("Forbidden edges (TYPE_CHECKING):")
        for ref in type_checking_forbidden:
            src_layer = layer_for_module(ref.source_module)
            dst_layer = layer_for_module(ref.target_module)
            file_path = format_path(repo_root, ref.source_file)
            print(
                f"- {file_path}:{ref.lineno} {src_layer} -> {dst_layer} via {ref.target_module}"
            )
        print("")
    else:
        print("Forbidden edges (TYPE_CHECKING): none")
        print("")

    if cycles:
        print("Cycles (runtime imports, package-level):")
        for group in cycles:
            print(f"- {', '.join(group)}")
        print("")
    else:
        print("Cycles (runtime imports, package-level): none")
        print("")

    god_files = sorted(internal_counts.items(), key=lambda item: (-item[1], str(item[0])))
    print(f"Top god files (internal import count, top {args.top}):")
    for path, count in god_files[: args.top]:
        if count == 0:
            continue
        print(f"- {format_path(repo_root, path)}: {count}")

    exit_code = 0
    if runtime_forbidden:
        exit_code = 1
    if args.fail_on_type_checking and type_checking_forbidden:
        exit_code = 1
    if args.fail_on_cycles and cycles:
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
