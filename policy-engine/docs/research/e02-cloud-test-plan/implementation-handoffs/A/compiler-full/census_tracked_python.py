"""Census retired compiler references in every tracked Python blob at a Git ref."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any


def find_repository_root(script_path: Path) -> Path:
    """Find the worktree root so the committed copy is location-independent."""

    for candidate in script_path.resolve().parents:
        if (candidate / ".git").exists():
            return candidate
    raise RuntimeError(f"could not locate the Git worktree above {script_path}")


REPO_ROOT = find_repository_root(Path(__file__))
COMPILER_MODULE = "polisyos.data_requirement.compiler"
PACKAGE_MODULE = "polisyos.data_requirement"
RETIRED_NAMES = frozenset(
    {
        "_data_families_from_obligation_graph",
        "_data_family_token_from_frontier_item",
        "_nested",
        "_normalised_family",
        "_slug_family",
        "_ordered_data_families",
        "_DATA_FAMILY_ORDER",
        "_digest",
    }
)
TARGET_MODULES = frozenset({COMPILER_MODULE, PACKAGE_MODULE})


def git_bytes(*arguments: str, input_bytes: bytes | None = None) -> bytes:
    """Run a read-only Git command and return its complete stdout bytes."""

    git_executable = shutil.which("git")
    if git_executable is None:
        raise RuntimeError("git executable was not found on PATH")
    # The executable is resolved from PATH; arguments are fixed Git read-only commands.
    result = subprocess.run(  # noqa: S603
        [git_executable, "--no-optional-locks", "-C", str(REPO_ROOT), *arguments],
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"git command failed ({result.returncode}): {arguments!r}\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
    return result.stdout


def selected_tree_entries(ref: str) -> tuple[str, str, list[tuple[str, str, str]]]:
    """Return the resolved commit/tree and every tracked `.py`/`.pyi` blob path."""

    commit = git_bytes("rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()
    tree = git_bytes("rev-parse", "--verify", f"{commit}^{{tree}}").decode().strip()
    listing = git_bytes("ls-tree", "-rz", "--full-tree", commit)
    entries: list[tuple[str, str, str]] = []
    for record in listing.split(b"\0"):
        if not record:
            continue
        header, raw_path = record.split(b"\t", 1)
        mode, kind, object_id = header.decode("ascii").split()
        if kind != "blob" or not raw_path.endswith((b".py", b".pyi")):
            continue
        path = raw_path.decode("utf-8", errors="strict")
        entries.append((path, mode, object_id))
    return commit, tree, entries


def read_blobs(object_ids: set[str]) -> dict[str, bytes]:
    """Read each selected blob once through Git's batch object reader."""

    request = b"".join(f"{object_id}\n".encode("ascii") for object_id in sorted(object_ids))
    output = git_bytes("cat-file", "--batch", input_bytes=request)
    blobs: dict[str, bytes] = {}
    cursor = 0
    while cursor < len(output):
        header_end = output.index(b"\n", cursor)
        object_id, kind, size_text = output[cursor:header_end].decode("ascii").split()
        if kind != "blob":
            raise RuntimeError(f"selected object is not a blob: {object_id} {kind}")
        size = int(size_text)
        content_start = header_end + 1
        content_end = content_start + size
        if content_end >= len(output) or output[content_end : content_end + 1] != b"\n":
            raise RuntimeError(f"truncated Git blob response for {object_id}")
        blobs[object_id] = output[content_start:content_end]
        cursor = content_end + 1
    if blobs.keys() != object_ids:
        raise RuntimeError("Git batch response did not return the complete selected blob set")
    return blobs


def package_context(path: str, package_init_paths: set[str]) -> str:
    """Infer a file's Python package context from tracked `__init__.py` paths."""

    context: list[str] = []
    prefix: list[str] = []
    for part in PurePosixPath(path).parts[:-1]:
        prefix.append(part)
        if "/".join((*prefix, "__init__.py")) in package_init_paths:
            context.append(part)
        else:
            context.clear()
    return ".".join(context)


def dotted_name(node: ast.AST) -> str | None:
    """Return the dotted name represented by a Name/Attribute expression."""

    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


def canonical_name(node: ast.AST, aliases: dict[str, str]) -> str | None:
    """Resolve a dotted expression through statically imported module aliases."""

    raw = dotted_name(node)
    if raw is None:
        return None
    parts = raw.split(".")
    for prefix_length in range(len(parts), 0, -1):
        prefix = ".".join(parts[:prefix_length])
        if prefix in aliases:
            suffix = ".".join(parts[prefix_length:])
            return f"{aliases[prefix]}.{suffix}" if suffix else aliases[prefix]
    return raw


def resolved_import(node: ast.ImportFrom, package: str) -> str:
    """Resolve absolute and relative import statements to a module name."""

    if node.level == 0:
        return node.module or ""
    if not package:
        return ""
    relative = "." * node.level + (node.module or "")
    try:
        return importlib.util.resolve_name(relative, package)
    except ImportError:
        return ""


_REFLECTIVE_APIS = {
    "builtins.getattr": "getattr",
    "builtins.__import__": "__import__",
    "importlib.import_module": "import_module",
}
_BUILTIN_REFLECTIVE_NAMES = {
    "getattr": "builtins.getattr",
    "__import__": "builtins.__import__",
}


def lexical_scope_index(
    tree: ast.AST, package: str
) -> tuple[dict[int, int], dict[int, dict[str, Any]], int]:
    """Index calls by lexical scope and collect statically imported bindings."""

    root_id = id(tree)
    scopes: dict[int, dict[str, Any]] = {
        root_id: {
            "node": tree,
            "kind": "module",
            "parent": None,
            "bindings": {},
            "global_names": set(),
            "nonlocal_names": set(),
        }
    }
    node_scopes: dict[int, int] = {}

    def new_scope(node: ast.AST, parent_id: int, kind: str) -> int:
        scope_id = id(node)
        scopes[scope_id] = {
            "node": node,
            "kind": kind,
            "parent": parent_id,
            "bindings": {},
            "global_names": set(),
            "nonlocal_names": set(),
        }
        return scope_id

    def visit(node: ast.AST, scope_id: int) -> None:
        node_scopes[id(node)] = scope_id
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for expression in (*node.decorator_list, *node.args.defaults):
                visit(expression, scope_id)
            for expression in node.args.kw_defaults:
                if expression is not None:
                    visit(expression, scope_id)
            for argument in (
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
            ):
                if argument.annotation is not None:
                    visit(argument.annotation, scope_id)
            if node.args.vararg and node.args.vararg.annotation:
                visit(node.args.vararg.annotation, scope_id)
            if node.args.kwarg and node.args.kwarg.annotation:
                visit(node.args.kwarg.annotation, scope_id)
            if node.returns is not None:
                visit(node.returns, scope_id)
            child_scope = new_scope(node, scope_id, "function")
            for statement in node.body:
                visit(statement, child_scope)
            return
        if isinstance(node, ast.ClassDef):
            for expression in (*node.decorator_list, *node.bases):
                visit(expression, scope_id)
            for keyword in node.keywords:
                visit(keyword.value, scope_id)
            child_scope = new_scope(node, scope_id, "class")
            for statement in node.body:
                visit(statement, child_scope)
            return
        if isinstance(node, ast.Lambda):
            for expression in (*node.args.defaults, *node.args.kw_defaults):
                if expression is not None:
                    visit(expression, scope_id)
            child_scope = new_scope(node, scope_id, "function")
            visit(node.body, child_scope)
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            if node.generators:
                visit(node.generators[0].iter, scope_id)
            child_scope = new_scope(node, scope_id, "comprehension")
            for index, generator in enumerate(node.generators):
                visit(generator.target, child_scope)
                if index:
                    visit(generator.iter, child_scope)
                for condition in generator.ifs:
                    visit(condition, child_scope)
            if isinstance(node, ast.DictComp):
                visit(node.key, child_scope)
                visit(node.value, child_scope)
            else:
                visit(node.elt, child_scope)
            return
        for child in ast.iter_child_nodes(node):
            visit(child, scope_id)

    visit(tree, root_id)

    def direct_scope_nodes(roots: list[ast.AST]) -> list[ast.AST]:
        result: list[ast.AST] = []
        pending = list(reversed(roots))
        while pending:
            node = pending.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result.append(node)
                pending.extend(reversed(node.decorator_list))
                pending.extend(reversed(node.args.defaults))
                pending.extend(
                    reversed([value for value in node.args.kw_defaults if value is not None])
                )
                if node.returns is not None:
                    pending.append(node.returns)
                continue
            if isinstance(node, ast.ClassDef):
                result.append(node)
                pending.extend(reversed(node.decorator_list))
                pending.extend(reversed(node.bases))
                pending.extend(reversed([keyword.value for keyword in node.keywords]))
                continue
            if isinstance(node, ast.Lambda):
                pending.extend(reversed(node.args.defaults))
                pending.extend(
                    reversed([value for value in node.args.kw_defaults if value is not None])
                )
                continue
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                if node.generators:
                    pending.append(node.generators[0].iter)
                continue
            result.append(node)
            pending.extend(reversed(list(ast.iter_child_nodes(node))))
        return result

    def add_binding(scope: dict[str, Any], name: str, imported_target: str | None) -> None:
        if name in scope["global_names"] or name in scope["nonlocal_names"]:
            return
        binding = scope["bindings"].setdefault(
            name, {"import_targets": set(), "other_binding": False}
        )
        if imported_target is None:
            binding["other_binding"] = True
        else:
            binding["import_targets"].add(imported_target)

    for scope in scopes.values():
        node = scope["node"]
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            roots = list(node.body)
        elif isinstance(node, ast.Lambda):
            roots = [node.body]
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            roots = []
            for index, generator in enumerate(node.generators):
                roots.append(generator.target)
                if index:
                    roots.append(generator.iter)
                roots.extend(generator.ifs)
            roots.extend([node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt])
        else:
            continue

        nodes = direct_scope_nodes(roots)
        scope["global_names"].update(
            name for item in nodes if isinstance(item, ast.Global) for name in item.names
        )
        scope["nonlocal_names"].update(
            name for item in nodes if isinstance(item, ast.Nonlocal) for name in item.names
        )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            arguments = node.args
            for argument in (
                *arguments.posonlyargs,
                *arguments.args,
                *arguments.kwonlyargs,
            ):
                add_binding(scope, argument.arg, None)
            if arguments.vararg:
                add_binding(scope, arguments.vararg.arg, None)
            if arguments.kwarg:
                add_binding(scope, arguments.kwarg.arg, None)

        for item in nodes:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                add_binding(scope, item.name, None)
            elif isinstance(item, ast.Name) and isinstance(item.ctx, (ast.Store, ast.Del)):
                add_binding(scope, item.id, None)
            elif isinstance(item, ast.Import):
                for alias in item.names:
                    local_name = alias.asname or alias.name.split(".", 1)[0]
                    imported_target = alias.name if alias.asname else local_name
                    add_binding(scope, local_name, imported_target)
            elif isinstance(item, ast.ImportFrom):
                module = resolved_import(item, package)
                for alias in item.names:
                    if alias.name != "*":
                        local_name = alias.asname or alias.name
                        target = f"{module}.{alias.name}" if module else alias.name
                        add_binding(scope, local_name, target)
            elif isinstance(item, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and item.name:
                add_binding(scope, item.name, None)
            elif isinstance(item, ast.MatchMapping) and item.rest:
                add_binding(scope, item.rest, None)

    return node_scopes, scopes, root_id


def lexical_parent(scope_id: int, scopes: dict[int, dict[str, Any]]) -> int | None:
    """Return the lexical parent, skipping class namespaces for nested code."""

    parent_id = scopes[scope_id]["parent"]
    while parent_id is not None and scopes[parent_id]["kind"] == "class":
        parent_id = scopes[parent_id]["parent"]
    return parent_id


def lookup_import_binding(
    name: str, scope_id: int, scopes: dict[int, dict[str, Any]], root_id: int
) -> tuple[str | None, str, set[str]]:
    """Resolve an imported name or return an explicit lexical ambiguity state."""

    initial = scopes[scope_id]
    if name in initial["global_names"]:
        scope_id = root_id
    elif name in initial["nonlocal_names"]:
        parent_id = lexical_parent(scope_id, scopes)
        scope_id = parent_id if parent_id is not None else scope_id
    current_id: int | None = scope_id
    while current_id is not None:
        scope = scopes[current_id]
        binding = scope["bindings"].get(name)
        if binding is not None:
            targets = set(binding["import_targets"])
            if len(targets) == 1 and not binding["other_binding"]:
                return next(iter(targets)), "resolved", targets
            if targets:
                return None, "ambiguous", targets
            return None, "shadowed", targets
        current_id = lexical_parent(current_id, scopes)
    return None, "absent", set()


def possible_import_targets(
    name: str, scope_id: int, scopes: dict[int, dict[str, Any]], root_id: int
) -> set[str]:
    """Collect visible import candidates even when a nearer binding shadows them."""

    initial = scopes[scope_id]
    if name in initial["global_names"]:
        scope_id = root_id
    current_id: int | None = scope_id
    candidates: set[str] = set()
    while current_id is not None:
        binding = scopes[current_id]["bindings"].get(name)
        if binding is not None:
            candidates.update(binding["import_targets"])
        current_id = lexical_parent(current_id, scopes)
    return candidates


def resolve_dotted_expression(
    node: ast.AST,
    scope_id: int,
    scopes: dict[int, dict[str, Any]],
    root_id: int,
    *,
    allow_target_path: bool = False,
) -> tuple[str | None, str, set[str]]:
    """Resolve a dotted expression through visible imports, retaining ambiguity."""

    raw = dotted_name(node)
    if raw is None:
        return None, "computed", set()
    parts = raw.split(".")
    imported, state, local_targets = lookup_import_binding(
        parts[0], scope_id, scopes, root_id
    )
    suffix = ".".join(parts[1:])
    if state == "resolved" and imported is not None:
        return (f"{imported}.{suffix}" if suffix else imported), state, local_targets
    if state in {"ambiguous", "shadowed"}:
        candidates = local_targets | possible_import_targets(
            parts[0], scope_id, scopes, root_id
        )
        resolved_candidates = {
            f"{target}.{suffix}" if suffix else target for target in candidates
        }
        if resolved_candidates:
            return None, "UNRESOLVED", resolved_candidates
        return None, state, set()
    if allow_target_path and (
        raw in TARGET_MODULES
        or any(raw.startswith(f"{module}.") for module in TARGET_MODULES)
    ):
        return raw, "resolved", {raw}
    return None, state, set()


def resolve_reflective_api(
    node: ast.AST,
    scope_id: int,
    scopes: dict[int, dict[str, Any]],
    root_id: int,
) -> tuple[tuple[str, ...], str]:
    """Resolve reflective call aliases, returning UNRESOLVED for shadowed imports."""

    candidates: set[str] = set()
    if isinstance(node, ast.Name):
        imported, state, local_targets = lookup_import_binding(
            node.id, scope_id, scopes, root_id
        )
        if state == "resolved" and imported is not None:
            api = _REFLECTIVE_APIS.get(imported)
            return ((api,), "resolved") if api else ((), "not_api")
        candidates.update(local_targets)
        candidates.update(possible_import_targets(node.id, scope_id, scopes, root_id))
        if node.id in _BUILTIN_REFLECTIVE_NAMES and state != "absent":
            candidates.add(_BUILTIN_REFLECTIVE_NAMES[node.id])
        elif node.id in _BUILTIN_REFLECTIVE_NAMES and state == "absent":
            api = _REFLECTIVE_APIS[_BUILTIN_REFLECTIVE_NAMES[node.id]]
            return ((api,), "resolved")
    elif isinstance(node, ast.Attribute):
        imported, state, local_targets = resolve_dotted_expression(
            node, scope_id, scopes, root_id
        )
        if state == "resolved" and imported is not None:
            api = _REFLECTIVE_APIS.get(imported)
            return ((api,), "resolved") if api else ((), "not_api")
        if state == "UNRESOLVED":
            candidates.update(local_targets)
        elif isinstance(node.value, ast.Name):
            candidates.update(
                f"{target}.{node.attr}"
                for target in possible_import_targets(
                    node.value.id, scope_id, scopes, root_id
                )
            )
    possible_apis = tuple(
        sorted({_REFLECTIVE_APIS[target] for target in candidates if target in _REFLECTIVE_APIS})
    )
    return (possible_apis, "UNRESOLVED") if possible_apis else ((), "not_api")


def source_findings(
    path: str,
    source: str,
    package_init_paths: set[str],
) -> dict[str, list[dict[str, Any]]]:
    """Parse and report literal/import/reflection references to retired names."""

    tree = ast.parse(source, filename=path, type_comments=True)
    package = package_context(path, package_init_paths)
    node_scopes, scopes, root_scope = lexical_scope_index(tree, package)
    aliases: dict[str, str] = {}
    findings: dict[str, list[dict[str, Any]]] = {
        "compiler_api_imports": [],
        "imports": [],
        "module_imports": [],
        "qualified_attributes": [],
        "imported_name_uses": [],
        "reflection_literals": [],
        "computed_module_getattr": [],
        "dynamic_import_literals": [],
        "computed_import_targets": [],
        "unresolved_reflective_calls": [],
        "retired_name_literals": [],
        "compiler_path_literals": [],
        "wildcard_imports": [],
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == COMPILER_MODULE or alias.name.startswith(f"{COMPILER_MODULE}."):
                    findings["module_imports"].append(
                        {"path": path, "line": node.lineno, "module": alias.name}
                    )
                    if alias.asname:
                        aliases[alias.asname] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = resolved_import(node, package)
            if module in TARGET_MODULES:
                for alias in node.names:
                    findings["compiler_api_imports"].append(
                        {
                            "path": path,
                            "line": node.lineno,
                            "module": module,
                            "name": alias.name,
                            "alias": alias.asname,
                        }
                    )
                    if module == COMPILER_MODULE and alias.name == "*":
                        findings["wildcard_imports"].append(
                            {"path": path, "line": node.lineno, "module": module}
                        )
                    elif module == COMPILER_MODULE:
                        if alias.name in RETIRED_NAMES:
                            findings["imports"].append(
                                {
                                    "path": path,
                                    "line": node.lineno,
                                    "name": alias.name,
                                    "alias": alias.asname,
                                }
                            )
                        aliases[alias.asname or alias.name] = f"{module}.{alias.name}"
            if module == PACKAGE_MODULE:
                for alias in node.names:
                    if alias.name == "compiler":
                        aliases[alias.asname or alias.name] = COMPILER_MODULE

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and canonical_name(node, aliases) in {
            f"{COMPILER_MODULE}.{name}" for name in RETIRED_NAMES
        }:
            findings["imported_name_uses"].append(
                {"path": path, "line": node.lineno, "name": canonical_name(node, aliases)}
            )
        if isinstance(node, ast.Attribute):
            parent = canonical_name(node.value, aliases)
            if parent in TARGET_MODULES and node.attr in RETIRED_NAMES:
                findings["qualified_attributes"].append(
                    {"path": path, "line": node.lineno, "module": parent, "name": node.attr}
                )
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in RETIRED_NAMES:
                findings["retired_name_literals"].append(
                    {"path": path, "line": node.lineno, "name": node.value}
                )
            if node.value == COMPILER_MODULE or node.value.startswith(f"{COMPILER_MODULE}."):
                findings["compiler_path_literals"].append(
                    {"path": path, "line": node.lineno, "value": node.value}
                )
        if not isinstance(node, ast.Call):
            continue

        scope_id = node_scopes.get(id(node), root_scope)
        api_candidates, api_state = resolve_reflective_api(
            node.func, scope_id, scopes, root_scope
        )
        if api_state == "not_api":
            continue

        if api_state == "UNRESOLVED":
            unresolved_target: str | None = None
            unresolved_name: str | None = None
            relevant = False
            if "getattr" in api_candidates and len(node.args) >= 2:
                target, target_state, target_candidates = resolve_dotted_expression(
                    node.args[0], scope_id, scopes, root_scope, allow_target_path=True
                )
                target_options = target_candidates | ({target} if target else set())
                name_node = node.args[1]
                unresolved_name = (
                    name_node.value
                    if isinstance(name_node, ast.Constant)
                    and isinstance(name_node.value, str)
                    and name_node.value in RETIRED_NAMES
                    else None
                )
                relevant = bool(target_options & TARGET_MODULES) or unresolved_name is not None
                if target in TARGET_MODULES:
                    unresolved_target = target
                elif target_options:
                    unresolved_target = ",".join(sorted(target_options))
                if target_state == "UNRESOLVED" and unresolved_name is None:
                    relevant = bool(target_options & TARGET_MODULES)
            if {"import_module", "__import__"} & set(api_candidates):
                module_arg = node.args[0] if node.args else None
                static_module = (
                    module_arg.value
                    if isinstance(module_arg, ast.Constant)
                    and isinstance(module_arg.value, str)
                    else None
                )
                import_candidate = static_module is None or static_module in TARGET_MODULES or (
                    static_module is not None
                    and static_module.startswith(f"{COMPILER_MODULE}.")
                )
                relevant = relevant or import_candidate
                unresolved_target = unresolved_target or static_module
            if relevant:
                findings["unresolved_reflective_calls"].append(
                    {
                        "path": path,
                        "line": node.lineno,
                        "call": dotted_name(node.func),
                        "possible_apis": list(api_candidates),
                        "classification": "UNRESOLVED",
                        "target": unresolved_target,
                        "retired_name": unresolved_name,
                        "reason": "lexical import alias is shadowed or rebound",
                    }
                )
            continue

        called = api_candidates[0]
        if called == "getattr" and len(node.args) >= 2:
            target, target_state, target_candidates = resolve_dotted_expression(
                node.args[0], scope_id, scopes, root_scope, allow_target_path=True
            )
            target_options = target_candidates | ({target} if target else set())
            name_node = node.args[1]
            if target in TARGET_MODULES:
                if isinstance(name_node, ast.Constant) and isinstance(name_node.value, str):
                    if name_node.value in RETIRED_NAMES:
                        findings["reflection_literals"].append(
                            {
                                "path": path,
                                "line": node.lineno,
                                "module": target,
                                "name": name_node.value,
                            }
                        )
                else:
                    findings["computed_module_getattr"].append(
                        {"path": path, "line": node.lineno, "module": target}
                    )
                    findings["unresolved_reflective_calls"].append(
                        {
                            "path": path,
                            "line": node.lineno,
                            "call": dotted_name(node.func),
                            "possible_apis": [called],
                            "classification": "UNRESOLVED",
                            "target": target,
                            "reason": "reflective attribute name is computed",
                        }
                    )
            elif target_state == "UNRESOLVED" and target_options & TARGET_MODULES:
                findings["unresolved_reflective_calls"].append(
                    {
                        "path": path,
                        "line": node.lineno,
                        "call": dotted_name(node.func),
                        "possible_apis": [called],
                        "classification": "UNRESOLVED",
                        "target": ",".join(sorted(target_options)),
                        "reason": "reflective receiver alias is shadowed or rebound",
                    }
                )

        if called in {"import_module", "__import__"}:
            module_arg = node.args[0] if node.args else None
            static_module = (
                module_arg.value
                if isinstance(module_arg, ast.Constant) and isinstance(module_arg.value, str)
                else None
            )
            is_target_module = static_module in TARGET_MODULES or (
                static_module is not None and static_module.startswith(f"{COMPILER_MODULE}.")
            )
            if is_target_module:
                findings["dynamic_import_literals"].append(
                    {"path": path, "line": node.lineno, "module": static_module}
                )
            elif static_module is None:
                findings["computed_import_targets"].append(
                    {"path": path, "line": node.lineno, "call": called}
                )
                findings["unresolved_reflective_calls"].append(
                    {
                        "path": path,
                        "line": node.lineno,
                        "call": dotted_name(node.func),
                        "possible_apis": [called],
                        "classification": "UNRESOLVED",
                        "reason": "dynamic import target is computed",
                    }
                )
            if called == "__import__":
                fromlist = node.args[3] if len(node.args) >= 4 else None
                fromlist = next(
                    (keyword.value for keyword in node.keywords if keyword.arg == "fromlist"),
                    fromlist,
                )
            else:
                fromlist = None
            if fromlist is not None:
                if isinstance(fromlist, (ast.List, ast.Tuple)):
                    for item in fromlist.elts:
                        if (
                            is_target_module
                            and isinstance(item, ast.Constant)
                            and item.value in RETIRED_NAMES
                        ):
                            findings["reflection_literals"].append(
                                {
                                    "path": path,
                                    "line": node.lineno,
                                    "module": "__import__ fromlist",
                                    "name": item.value,
                                }
                            )
                elif not isinstance(fromlist, ast.Constant):
                    findings["computed_import_targets"].append(
                        {"path": path, "line": node.lineno, "call": "__import__ fromlist"}
                    )
                    if is_target_module:
                        findings["unresolved_reflective_calls"].append(
                            {
                                "path": path,
                                "line": node.lineno,
                                "call": dotted_name(node.func),
                                "possible_apis": [called],
                                "classification": "UNRESOLVED",
                                "target": static_module,
                                "reason": "dynamic import fromlist is computed",
                            }
                        )
    return findings


def self_check() -> None:
    """Prove aliased reflective APIs resolve and lexical shadows stay unresolved."""

    probe = """\
from polisyos.data_requirement.compiler import _digest as old_digest
import polisyos.data_requirement.compiler as compiler
import builtins as builtin_api
from builtins import getattr as reflect_get
from builtins import __import__ as import_alias
from importlib import import_module as load_module
import importlib as import_library
getattr(compiler, "_DATA_FAMILY_ORDER")
reflect_get(compiler, "_digest")
builtin_api.getattr(compiler, "_nested")
load_module("polisyos.data_requirement.compiler")
import_library.import_module("polisyos.data_requirement.compiler")
import_alias("polisyos.data_requirement.compiler", fromlist=["_slug_family"])

def parameter_shadow(reflect_get, load_module, builtin_api):
    reflect_get(compiler, "_digest")
    load_module("polisyos.data_requirement.compiler")
    builtin_api.getattr(compiler, "_nested")

def assignment_shadow():
    reflect_get = object()
    reflect_get(compiler, "_nested")

def receiver_shadow(compiler):
    reflect_get(compiler, "_digest")

def import_then_rebind():
    from builtins import getattr as local_getattr
    local_getattr = object()
    local_getattr(compiler, "_slug_family")
"""
    findings = source_findings(
        "synthetic-positive-control.py",
        probe,
        {"polisyos/__init__.py", "polisyos/data_requirement/__init__.py"},
    )
    if (
        not findings["imports"]
        or not findings["reflection_literals"]
        or len(findings["reflection_literals"]) < 4
        or len(findings["dynamic_import_literals"]) < 2
        or len(findings["unresolved_reflective_calls"]) < 6
        or any(
            row["classification"] != "UNRESOLVED"
            for row in findings["unresolved_reflective_calls"]
        )
    ):
        raise RuntimeError("alias resolution or lexical shadow control did not behave as expected")


def main() -> int:
    ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    scanner_path = Path(__file__).resolve()
    result: dict[str, Any] = {
        "counterexample": (
            "A tracked Python source imports a retired compiler name, qualifies it through the "
            "compiler module, or reflects on it with a static name."
        ),
        "inputs": {
            "repository_root": str(REPO_ROOT),
            "requested_ref": ref,
            "ref_argument": "first positional argument; defaults to HEAD",
            "operations": [
                "git rev-parse --verify <ref>^{commit}",
                "git rev-parse --verify <commit>^{tree}",
                "git ls-tree -rz --full-tree <commit>",
                "git cat-file --batch <unique selected blob IDs>",
                "UTF-8 decode and ast.parse(type_comments=True) for every selected path",
            ],
            "selector": "all tracked Git blob paths ending in .py or .pyi",
            "exclusions": [],
        },
        "scanner_candidate": {
            "path": scanner_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": hashlib.sha256(scanner_path.read_bytes()).hexdigest(),
            "selected_tree_is_recomputed_from_requested_ref": True,
        },
        "lexical_resolution_scope": (
            "Static imports are followed through lexical scopes. Parameters, assignments, and "
            "competing imports shadow an alias; unresolved call bindings remain UNRESOLVED. "
            "Runtime rebinding, computed names, and external consumers are not proven absent."
        ),
        "predicate_class": "recomputed",
        "unresolved_by_construction": [
            "computed_import_or_reflection_name: names assembled at runtime or selected from data",
            "external_or_untracked_consumer: packages, plugins, generated code, and untracked "
            "files",
            "non_python_consumer: configuration, notebooks, shell, and other non-.py/.pyi inputs",
            "exec_eval_native_or_service_dispatch: behavior outside statically parsed Python AST",
        ],
    }
    try:
        commit, tree, entries = selected_tree_entries(ref)
        blobs = read_blobs({object_id for _path, _mode, object_id in entries})
        package_init_paths = {
            path for path, _mode, _object_id in entries if PurePosixPath(path).name == "__init__.py"
        }
        file_types = Counter(PurePosixPath(path).suffix for path, _mode, _object_id in entries)
        all_findings: dict[str, list[dict[str, Any]]] = {}
        parse_errors: list[dict[str, str]] = []
        for path, _mode, object_id in entries:
            try:
                source = blobs[object_id].decode("utf-8", errors="strict")
                file_findings = source_findings(path, source, package_init_paths)
            except (UnicodeDecodeError, SyntaxError) as exc:
                parse_errors.append({"path": path, "error": f"{type(exc).__name__}: {exc}"})
                continue
            for category, rows in file_findings.items():
                all_findings.setdefault(category, []).extend(rows)
        result["source"] = {
            "commit": commit,
            "tree": tree,
            "selected_path_count": len(entries),
            "selected_unique_blob_count": len(blobs),
            "file_type_denominator": {
                ".py": file_types[".py"],
                ".pyi": file_types[".pyi"],
            },
            "read_blob_count": len(blobs),
            "parsed_path_count": len(entries) - len(parse_errors),
            "parse_error_count": len(parse_errors),
            "parse_errors": parse_errors,
        }
        result["findings"] = {
            category: {"count": len(rows), "rows": rows}
            for category, rows in sorted(all_findings.items())
        }
        api_imports = all_findings.get("compiler_api_imports", [])
        from_import_statements = {(row["path"], row["line"]) for row in api_imports}
        module_imports = all_findings.get("module_imports", [])
        module_import_statements = {(row["path"], row["line"]) for row in module_imports}
        import_statements = from_import_statements | module_import_statements
        result["active_api_import_summary"] = {
            "symbol_import_rows": len(api_imports),
            "from_import_statement_count": len(from_import_statements),
            "module_import_statement_count": len(module_import_statements),
            "all_import_statement_count": len(import_statements),
            "unique_path_count": len({path for path, _line in import_statements}),
        }
        unresolved_count = len(all_findings.get("unresolved_reflective_calls", []))
        computed_count = len(all_findings.get("computed_import_targets", [])) + len(
            all_findings.get("computed_module_getattr", [])
        )
        wildcard_count = len(all_findings.get("wildcard_imports", []))
        static_reference_count = sum(
            len(all_findings.get(category, []))
            for category in (
                "imports",
                "qualified_attributes",
                "imported_name_uses",
                "reflection_literals",
            )
        )
        result["unresolved_summary"] = {
            "ambiguous_or_computed_reflective_calls": unresolved_count,
            "computed_import_or_getattr_sites": computed_count,
            "wildcard_compiler_imports": wildcard_count,
            "absence_claim_supported": (
                not parse_errors
                and not unresolved_count
                and not computed_count
                and not wildcard_count
                and not static_reference_count
            ),
        }
        result["verdict"] = (
            "UNRUN"
            if parse_errors
            else "UNRESOLVED"
            if unresolved_count or computed_count or wildcard_count
            else "bounded_static_scan_complete"
        )
        self_check()
        result["positive_control"] = (
            "passed: direct and aliased reflection/import APIs plus parameter, assignment, and "
            "import-rebind shadow controls"
        )
        if parse_errors:
            result["absence_result"] = "partial_coverage; unreadable or unparsable selected member"
            status = 2
        elif unresolved_count or computed_count or wildcard_count:
            result["absence_result"] = (
                "UNRESOLVED; statically classified references are reported, but computed, "
                "ambiguous, or wildcard imports prevent an absence conclusion"
            )
            status = 0
        else:
            result["absence_result"] = (
                "no statically resolved tracked Python caller found"
                if not any(
                    result["findings"][category]["count"]
                    for category in (
                        "imports",
                        "qualified_attributes",
                        "imported_name_uses",
                        "reflection_literals",
                    )
                )
                else "one or more tracked Python references found"
            )
            status = 0
    except Exception as exc:  # The report must distinguish an incomplete run from a zero.
        result["verdict"] = "UNRUN"
        result["absence_result"] = "undecided; Git input, decode, or scanner operation failed"
        result["failure"] = f"{type(exc).__name__}: {exc}"
        status = 2
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
