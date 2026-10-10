#!/usr/bin/env python3
"""Classify source-level artifact-ID selector calls against declared ref models."""

from __future__ import annotations

import ast
import sys
from collections import Counter
from pathlib import Path

SOURCE_ROOT = Path("src/polisyos")
READ_METHODS = {"get_bytes", "get_manifest", "get_manifest_bytes", "verify", "has"}
SELECTOR_FIELDS = {"artifact_id", "kind", "media_type", "manifest_profile_sha256"}


def _emit(value: object) -> None:
    sys.stdout.write(f"{value}\n")


def module_name(path: Path) -> str:
    parts = list(path.with_suffix("").parts)
    parts = parts[parts.index("polisyos") :]
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def relative_module(
    current: str, level: int, module: str | None, *, package_initializer: bool
) -> str:
    remove = max(level - 1, 0) if package_initializer else level
    parts = current.split(".")[: len(current.split(".")) - remove] if remove else current.split(".")
    if module:
        parts.extend(module.split("."))
    return ".".join(parts)


files = sorted(SOURCE_ROOT.rglob("*.py"))
trees: dict[str, ast.Module] = {}
paths: dict[str, Path] = {}
imports: dict[str, dict[str, str]] = {}
classes: dict[str, tuple[dict[str, str], list[str]]] = {}
aliases: dict[str, str] = {}
returns: dict[str, str] = {}
parse_errors: list[str] = []

for path in files:
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError as exc:
        parse_errors.append(f"{path}:{exc.lineno}: {exc.msg}")
        continue
    module = module_name(path)
    trees[module] = tree
    paths[module] = path
    module_imports: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for imported in node.names:
                module_imports[imported.asname or imported.name.split(".")[0]] = imported.name
        elif isinstance(node, ast.ImportFrom):
            package = (
                relative_module(
                    module,
                    node.level,
                    node.module,
                    package_initializer=path.name == "__init__.py",
                )
                if node.level
                else (node.module or "")
            )
            for imported in node.names:
                module_imports[imported.asname or imported.name] = ".".join(
                    part for part in (package, imported.name) if part
                )
    imports[module] = module_imports

for module, tree in trees.items():
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            fields = {
                child.target.id: ast.unparse(child.annotation)
                for child in node.body
                if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name)
            }
            classes[f"{module}.{node.name}"] = (fields, [ast.unparse(base) for base in node.bases])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns:
            returns[f"{module}.{node.name}"] = ast.unparse(node.returns)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            target = (
                node.target
                if isinstance(node, ast.AnnAssign)
                else (node.targets[0] if len(node.targets) == 1 else None)
            )
            value = node.annotation if isinstance(node, ast.AnnAssign) else node.value
            if (
                isinstance(target, ast.Name)
                and value is not None
                and isinstance(value, (ast.Name, ast.Attribute))
            ):
                aliases[f"{module}.{target.id}"] = ast.unparse(value)


def canonical(qualified: str, seen: set[str] | None = None) -> str:
    """Resolve package re-exports to the defining class without importing modules."""
    seen = seen or set()
    if qualified in seen:
        return qualified
    seen.add(qualified)
    if qualified in classes:
        return qualified
    if qualified in aliases:
        alias_module = qualified.rsplit(".", 1)[0]
        expression = aliases[qualified]
        return canonical(resolve(expression, alias_module), seen)
    module, _, name = qualified.rpartition(".")
    target = imports.get(module, {}).get(name)
    if target and target != qualified:
        return canonical(target, seen)
    return qualified


def resolve(expression: str, module: str) -> str:
    expression = expression.strip().split("[", 1)[0]
    if expression in {"None", "Any", "object", "str", "bytes", "int", "bool", "float"}:
        return expression
    parts = expression.split(".")
    target = imports.get(module, {}).get(parts[0])
    if target:
        return canonical(".".join([target, *parts[1:]]))
    return canonical(f"{module}.{expression}")


def annotation_types(node: ast.expr | None, module: str) -> list[str]:
    if node is None:
        return []
    if isinstance(node, ast.Name):
        return (
            []
            if node.id in {"None", "Any", "object", "str", "bytes", "int", "bool", "float"}
            else [resolve(node.id, module)]
        )
    if isinstance(node, ast.Attribute):
        return [resolve(ast.unparse(node), module)]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return annotation_types(node.left, module) + annotation_types(node.right, module)
    if isinstance(node, ast.Subscript):
        items = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        return [item for child in items for item in annotation_types(child, module)]
    return []


def model_fields(qualified: str, seen: set[str] | None = None) -> dict[str, str]:
    qualified = canonical(qualified)
    seen = seen or set()
    if qualified in seen:
        return {}
    seen.add(qualified)
    definition = classes.get(qualified)
    if not definition:
        return {}
    declared, bases = definition
    module = qualified.rsplit(".", 1)[0]
    fields: dict[str, str] = {}
    for base in bases:
        fields.update(model_fields(resolve(base, module), seen))
    fields.update(declared)
    return fields


def field_types(qualified: str, name: str) -> list[str]:
    annotation = model_fields(qualified).get(name)
    if annotation is None:
        return []
    module = canonical(qualified).rsplit(".", 1)[0]
    return annotation_types(ast.parse(annotation, mode="eval").body, module)


def reference_type(qualified: str, seen: set[str] | None = None) -> bool:
    qualified = canonical(qualified)
    short = qualified.rsplit(".", 1)[-1]
    if short == "None" or short.endswith("Ref"):
        return True
    seen = seen or set()
    if qualified in seen:
        return False
    seen.add(qualified)
    if qualified in aliases:
        module = qualified.rsplit(".", 1)[0]
        return any(
            reference_type(item, seen)
            for item in annotation_types(ast.parse(aliases[qualified], mode="eval").body, module)
        )
    definition = classes.get(qualified)
    if not definition:
        return False
    module = qualified.rsplit(".", 1)[0]
    return any(reference_type(resolve(base, module), seen) for base in definition[1])


def infer(
    expression: ast.expr, environment: dict[str, list[str]], module: str, owner: str | None
) -> list[str]:
    if isinstance(expression, ast.Name):
        return environment.get(expression.id, [])
    if isinstance(expression, ast.Attribute):
        if expression.attr == "artifact_id":
            return []
        output = [
            item
            for base in infer(expression.value, environment, module, owner)
            for item in field_types(base, expression.attr)
        ]
        if isinstance(expression.value, ast.Name) and expression.value.id == "self" and owner:
            output.extend(field_types(owner, expression.attr))
        return output
    if isinstance(expression, ast.Call):
        if isinstance(expression.func, ast.Name):
            qualified = resolve(expression.func.id, module)
        elif isinstance(expression.func, ast.Attribute):
            qualified = resolve(ast.unparse(expression.func), module)
        else:
            return []
        if canonical(qualified) in classes:
            return [canonical(qualified)]
        return (
            annotation_types(
                ast.parse(returns[qualified], mode="eval").body, qualified.rsplit(".", 1)[0]
            )
            if qualified in returns
            else []
        )
    return []


rows: list[tuple[str, int, str, str, str, str]] = []
for module, tree in trees.items():
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    for call in ast.walk(tree):
        if not (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr in READ_METHODS
            and call.args
            and isinstance(call.args[0], ast.Attribute)
            and call.args[0].attr == "artifact_id"
        ):
            continue
        function: ast.AST = call
        while function in parents and not isinstance(
            function, (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            function = parents[function]
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        owner: str | None = None
        parent = parents.get(function)
        while parent is not None:
            if isinstance(parent, ast.ClassDef):
                owner = f"{module}.{parent.name}"
                break
            parent = parents.get(parent)
        environment: dict[str, list[str]] = {}
        args = [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]
        for arg in args:
            if arg.annotation:
                environment[arg.arg] = annotation_types(arg.annotation, module)
        assignments: list[tuple[int, str, ast.expr | None, ast.expr | None, bool]] = []
        for node in ast.walk(function):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                assignments.append((node.lineno, node.target.id, node.annotation, None, True))
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assignments.append((node.lineno, target.id, None, node.value, False))
        for line, name, annotation, value, explicit in sorted(assignments):
            if line > call.lineno:
                continue
            if explicit:
                environment[name] = annotation_types(annotation, module)
            elif value is not None:
                inferred = infer(value, environment, module, owner)
                if inferred:
                    environment[name] = inferred
        expression = call.args[0]
        candidates = infer(expression.value, environment, module, owner)
        refs = [item for item in candidates if item != "None" and reference_type(item)]
        full = refs and all(set(model_fields(item)) >= SELECTOR_FIELDS for item in refs)
        if full:
            category = "typed-full-selector"
        elif refs:
            category = "typed-ref-incomplete-schema"
        elif candidates:
            category = "typed-nonref-id"
        else:
            category = "unresolved"
        type_names = ",".join(sorted({item.rsplit(".", 1)[-1] for item in candidates}))
        rendered_arguments = ", ".join(
            arg.arg + (": " + ast.unparse(arg.annotation) if arg.annotation else "") for arg in args
        )
        signature = f"{function.name}({rendered_arguments})"
        rows.append(
            (
                paths[module].as_posix(),
                call.lineno,
                call.func.attr,
                ast.unparse(expression),
                category,
                type_names,
                signature,
            )
        )

_emit(
    f"python_source_files={len(files)} parse_errors={len(parse_errors)} "
    f"direct_selector_calls={len(rows)}"
)
_emit(f"method_counts={dict(Counter(row[2] for row in rows))}")
_emit(f"categories={dict(Counter(row[4] for row in rows))}")
for category in (
    "typed-full-selector",
    "typed-ref-incomplete-schema",
    "typed-nonref-id",
    "unresolved",
):
    _emit(f"\n[{category}]")
    for row in sorted(rows):
        if row[4] == category:
            _emit(f"{row[0]}:{row[1]} {row[2]}({row[3]}) type={row[5]} owner={row[6]}")
