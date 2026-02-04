#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import datetime
import fnmatch
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


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


@dataclass(frozen=True)
class ImportException:
    exception_id: str
    owner: str
    reason: str
    expires: datetime.date
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
    def __init__(
        self,
        source_file: Path,
        source_module: str,
        is_package: bool,
        internal_prefix: str,
        known_roots: set[str],
    ) -> None:
        self.source_file = source_file
        self.source_module = source_module
        self.is_package = is_package
        self.internal_prefix = internal_prefix
        self.known_roots = known_roots
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
        self.imports.append(
            ImportRef(
                source_file=self.source_file,
                source_module=self.source_module,
                target_module=module,
                lineno=lineno,
                in_type_checking=self.in_type_checking,
            )
        )
        if module == self.internal_prefix or module.startswith(f"{self.internal_prefix}."):
            self.internal_targets.add(module)


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
    return files


def parse_imports(
    config: PolicyConfig,
) -> tuple[list[ImportRef], dict[Path, int], dict[str, set[str]]]:
    imports: list[ImportRef] = []
    internal_counts: dict[Path, int] = {}
    module_graph: dict[str, set[str]] = {}

    for file_path in iter_py_files(config.src_root):
        result = module_name_for_path(config.src_root, file_path, config.internal_prefix)
        if result is None:
            continue
        module_name, is_package = result
        module_graph.setdefault(module_name, set())
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        collector = ImportCollector(
            file_path, module_name, is_package, config.internal_prefix, config.known_roots
        )
        collector.visit(tree)
        imports.extend(collector.imports)
        internal_counts[file_path] = len(collector.internal_targets)
        for ref in collector.imports:
            if ref.in_type_checking:
                continue
            if ref.target_module.startswith(f"{config.internal_prefix}."):
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


def read_policy(path: Path) -> PolicyConfig:
    if not path.exists():
        raise ValueError(f"Policy file not found: {path}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    policy = data.get("policy") or {}
    internal_prefix = policy.get("internal_prefix")
    src_root = policy.get("src_root")
    version = policy.get("version", "unknown")
    if not internal_prefix or not src_root:
        raise ValueError("policy.internal_prefix and policy.src_root are required")

    roots = data.get("roots") or {}
    known_list = roots.get("known") or []
    known_roots = set(known_list)
    if not known_roots:
        raise ValueError("roots.known must list at least one root")

    internal_allow = data.get("internal", {}).get("allow", {})
    internal_allow_map: dict[str, set[str]] = {}
    for root in known_roots:
        allowed = internal_allow.get(root, [])
        internal_allow_map[root] = set(allowed)

    external_allow = data.get("external", {}).get("allow", {})
    external_allow_map: dict[str, set[str]] = {}
    for root, values in external_allow.items():
        modules = values.get("modules") if isinstance(values, dict) else values
        if modules is None:
            modules = []
        external_allow_map[root] = set(modules)

    return PolicyConfig(
        version=version,
        internal_prefix=internal_prefix,
        src_root=Path(src_root),
        known_roots=known_roots,
        internal_allow=internal_allow_map,
        external_allow=external_allow_map,
    )


def read_exceptions(path: Path | None) -> list[ImportException]:
    if path is None:
        return []
    if not path.exists():
        return []
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    exceptions = data.get("exception", [])
    results: list[ImportException] = []
    for item in exceptions:
        exception_id = item.get("id")
        owner = item.get("owner")
        reason = item.get("reason")
        expires_raw = item.get("expires")
        source_glob = item.get("source_glob")
        import_root = item.get("import_root")
        import_module_prefix = item.get("import_module_prefix")
        source_module_prefix = item.get("source_module_prefix")
        external_module = item.get("external_module")

        if not exception_id or not owner or not reason or not expires_raw or not source_glob:
            raise ValueError(f"Invalid exception entry (missing fields): {item}")

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


def format_allowed_internal(allowed: set[str]) -> str:
    if "*" in allowed:
        return "*"
    return "{" + ", ".join(sorted(allowed)) + "}"


def format_allowed_external(allowed: set[str]) -> str:
    if not allowed:
        return "stdlib"
    return "stdlib + {" + ", ".join(sorted(allowed)) + "}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check internal import boundaries and report cycles."
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("import_policy.toml"),
        help="Path to import policy TOML",
    )
    parser.add_argument(
        "--exceptions",
        type=Path,
        default=Path("import_exceptions.toml"),
        help="Path to import exceptions TOML",
    )
    parser.add_argument("--top", type=int, default=10, help="Show top N god files")
    parser.add_argument(
        "--fail-on-cycles", action="store_true", help="Fail on import cycles"
    )
    parser.add_argument(
        "--allow-type-checking",
        action="store_true",
        help="Ignore violations inside TYPE_CHECKING blocks",
    )
    args = parser.parse_args()

    try:
        config = read_policy(args.policy)
        exceptions = read_exceptions(args.exceptions)
    except Exception as exc:
        print(f"Config error: {exc}")
        return 2

    if not config.src_root.exists():
        print(f"Source root not found: {config.src_root}")
        return 2

    imports, internal_counts, module_graph = parse_imports(config)

    repo_root = config.src_root.parent
    today = datetime.date.today()
    stdlib = stdlib_modules()

    violations: list[Violation] = []
    allowed_exceptions: list[ExceptionMatch] = []
    expired_exceptions: list[ExceptionMatch] = []
    unknown_roots: set[str] = set()

    for ref in imports:
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
                imports_internal_segment = any(
                    part.startswith("_") for part in target_parts[2:]
                )
                if imports_internal_segment:
                    message = (
                        f"{rel_path}:{ref.lineno} [ARCH006] forbidden internal subpackage import: "
                        f"{ref.source_module} -> {ref.target_module}. "
                        "Cross-root imports must go through public facades."
                    )
                    violation = _apply_exceptions(
                        ref,
                        message,
                        exceptions,
                        rel_path,
                        target_root,
                        today,
                        allowed_exceptions,
                        expired_exceptions,
                    )
                    if violation:
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
                        exceptions,
                        rel_path,
                        target_root,
                        today,
                        allowed_exceptions,
                        expired_exceptions,
                    )
                    if violation:
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
                        exceptions,
                        rel_path,
                        target_root,
                        today,
                        allowed_exceptions,
                        expired_exceptions,
                    )
                    if violation:
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
                        exceptions,
                        rel_path,
                        target_root,
                        today,
                        allowed_exceptions,
                        expired_exceptions,
                    )
                    if violation:
                        violations.append(violation)
                continue

            if source_root == "ir":
                allowed = {"ir"}
                if target_root not in allowed:
                    message = (
                        f"{rel_path}:{ref.lineno} [ARCH001] forbidden internal import: "
                        f"{source_root} -> {target_root} via {ref.target_module} "
                        f"(allowed={format_allowed_internal(allowed)})"
                    )
                    violation = _apply_exceptions(
                        ref,
                        message,
                        exceptions,
                        rel_path,
                        target_root,
                        today,
                        allowed_exceptions,
                        expired_exceptions,
                    )
                    if violation:
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
                exceptions,
                rel_path,
                target_root,
                today,
                allowed_exceptions,
                expired_exceptions,
            )
            if violation:
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
                exceptions,
                rel_path,
                None,
                today,
                allowed_exceptions,
                expired_exceptions,
                external_top=external_top,
            )
            if violation:
                violations.append(violation)

    if unknown_roots:
        print("Config error: unknown internal roots encountered:")
        for root in sorted(unknown_roots):
            print(f"- {root}")
        return 2

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

    print("Import gate report")
    print("")
    print(f"Policy: {format_path(Path.cwd(), args.policy)} (v{config.version})")
    print(f"Exceptions: {format_path(Path.cwd(), args.exceptions)}")
    print("")

    if violations:
        print("Violations:")
        for violation in [v for v in violations if v is not None]:
            if violation is None:
                continue
            print(f"- {violation.message}")
            if violation.expired_exception:
                exc = violation.expired_exception
                print(
                    f"  expired exception {exc.exception_id} (expires {exc.expires})"
                )
        print("")
    else:
        print("Violations: none")
        print("")

    if allowed_exceptions:
        print("Allowed exceptions:")
        for match in allowed_exceptions:
            exc = match.exception
            file_path = format_path(repo_root, match.ref.source_file)
            print(
                f"- {file_path}:{match.ref.lineno} {exc.exception_id} "
                f"(expires {exc.expires}) {exc.reason}"
            )
        print("")
    else:
        print("Allowed exceptions: none")
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
    if violations:
        exit_code = 1
    if args.fail_on_cycles and cycles:
        exit_code = 1
    return exit_code


def _apply_exceptions(
    ref: ImportRef,
    message: str,
    exceptions: list[ImportException],
    rel_path: str,
    target_root: str | None,
    today: datetime.date,
    allowed_exceptions: list[ExceptionMatch],
    expired_exceptions: list[ExceptionMatch],
    *,
    external_top: str | None = None,
) -> Violation | None:
    for exc in exceptions:
        if exception_matches(
            exc,
            ref,
            rel_path=rel_path,
            target_module=ref.target_module,
            target_root=target_root,
            external_top=external_top,
        ):
            if exc.expires < today:
                expired_exceptions.append(
                    ExceptionMatch(exception=exc, ref=ref, message=message)
                )
                return Violation(
                    ref=ref,
                    code="ARCH000",
                    message=message,
                    expired_exception=exc,
                )
            allowed_exceptions.append(
                ExceptionMatch(exception=exc, ref=ref, message=message)
            )
            return None
    return Violation(ref=ref, code="ARCH000", message=message)


if __name__ == "__main__":
    raise SystemExit(main())
