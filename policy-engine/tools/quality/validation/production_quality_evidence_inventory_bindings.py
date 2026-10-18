#!/usr/bin/env python3
"""Resolve bounded, source-declared quality registry literals and producer paths.

The resolver establishes unique static module bindings from source bytes. It does not
claim arbitrary runtime currentness: runtime mutation, ``exec`` and ``globals`` side
 effects remain outside this source inventory's admitted scope.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.cost_degradation import (  # noqa: E402
    COST_DEGRADATION_TELEMETRY_FILENAME,
    COST_DEGRADATION_TELEMETRY_REPORT_KEY,
)
from polisyos.runtime.quality.cost_gate import (  # noqa: E402
    RUN_COST_GATE_FILENAME,
    RUN_COST_GATE_REPORT_KEY,
)
from polisyos.runtime.quality.data_forge_binding import (  # noqa: E402
    DATA_FORGE_SNAPSHOT_BINDING_FILE,
    DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY,
)
from polisyos.runtime.quality.hypothesis_ledger import (  # noqa: E402
    HYPOTHESIS_LEDGER_FILENAME,
    HYPOTHESIS_LEDGER_REF_KEY,
    HYPOTHESIS_LEDGER_REPORT_KEY,
)
from polisyos.runtime.quality.prompt_tool_ledger import PROMPT_TOOL_LEDGER_FILENAME  # noqa: E402

_KNOWN_LITERAL_NAMES: dict[str, object] = {
    "DATA_FORGE_SNAPSHOT_BINDING_FILE": DATA_FORGE_SNAPSHOT_BINDING_FILE,
    "DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY": DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY,
    "COST_DEGRADATION_TELEMETRY_FILENAME": COST_DEGRADATION_TELEMETRY_FILENAME,
    "COST_DEGRADATION_TELEMETRY_REPORT_KEY": COST_DEGRADATION_TELEMETRY_REPORT_KEY,
    "HYPOTHESIS_LEDGER_FILENAME": HYPOTHESIS_LEDGER_FILENAME,
    "HYPOTHESIS_LEDGER_REF_KEY": HYPOTHESIS_LEDGER_REF_KEY,
    "HYPOTHESIS_LEDGER_REPORT_KEY": HYPOTHESIS_LEDGER_REPORT_KEY,
    "PROMPT_TOOL_LEDGER_FILENAME": PROMPT_TOOL_LEDGER_FILENAME,
    "RUN_COST_GATE_FILENAME": RUN_COST_GATE_FILENAME,
    "RUN_COST_GATE_REPORT_KEY": RUN_COST_GATE_REPORT_KEY,
}


class _LiteralBindingNotFoundError(ValueError):
    """A requested source constant has no supported top-level binding."""


class _ClassGlobalDeclarationVisitor(ast.NodeVisitor):
    """Find selected global declarations in one class suite, not nested scopes."""

    def __init__(self, symbol_name: str) -> None:
        self.symbol_name = symbol_name
        self.declared = False

    def visit_Global(self, node: ast.Global) -> None:
        self.declared = self.declared or self.symbol_name in node.names

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return


class _ModuleBindingVisitor(ast.NodeVisitor):
    """Collect module-executed bindings without entering function/class scopes."""

    def __init__(self, symbol_name: str) -> None:
        self.symbol_name = symbol_name
        self.bindings: list[tuple[ast.AST, str]] = []
        self.has_star_import = False

    def _record(self, name: str, node: ast.AST, kind: str) -> None:
        if name == self.symbol_name:
            self.bindings.append((node, kind))

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self._record(node.id, node, "assignment")

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._record(alias.asname or alias.name.split(".", 1)[0], alias, "import")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*":
                self.has_star_import = True
            else:
                self._record(alias.asname or alias.name, alias, "import")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record(node.name, node, "function")
        for expression in (
            *node.decorator_list,
            *node.args.defaults,
            *node.args.kw_defaults,
        ):
            if expression is not None:
                self.visit(expression)
        for argument in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ):
            if argument.annotation is not None:
                self.visit(argument.annotation)
        for argument in (node.args.vararg, node.args.kwarg):
            if argument is not None and argument.annotation is not None:
                self.visit(argument.annotation)
        if node.returns is not None:
            self.visit(node.returns)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._record(node.name, node, "class")
        for expression in (*node.decorator_list, *node.bases):
            self.visit(expression)
        for keyword in node.keywords:
            self.visit(keyword.value)
        class_globals = _ClassGlobalDeclarationVisitor(self.symbol_name)
        for statement in node.body:
            class_globals.visit(statement)
        if class_globals.declared:
            self._record(self.symbol_name, node, "class-suite global declaration")

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for expression in (*node.args.defaults, *node.args.kw_defaults):
            if expression is not None:
                self.visit(expression)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name is not None:
            self._record(node.name, node, "exception target")
        if node.type is not None:
            self.visit(node.type)
        for statement in node.body:
            self.visit(statement)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.name is not None:
            self._record(node.name, node, "match capture")
        if node.pattern is not None:
            self.visit(node.pattern)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name is not None:
            self._record(node.name, node, "match capture")

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        if node.rest is not None:
            self._record(node.rest, node, "match capture")
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        # Comprehension targets are local; walrus writes still belong to the module.
        self.visit(node.iter)
        for expression in node.ifs:
            self.visit(expression)


def _literal_assignment(
    path: Path,
    name: str,
    *,
    source_root: Path | None = None,
    _seen: frozenset[tuple[Path, str]] = frozenset(),
) -> object:
    """Read a unique static module binding, following bounded source imports.

    This establishes the source's statically selected literal declaration, not
    arbitrary runtime currentness. Rebindings in module-executed control flow
    are rejected; function and class-local bodies are outside this resolver. A
    selected class-suite ``global`` declaration is rejected conservatively.
    """
    root = (_SRC_ROOT if source_root is None else source_root).resolve()
    source_path = path.resolve()
    if not source_path.is_relative_to(root):
        raise ValueError(f"source file is outside the selected source root: {source_path}")

    binding_key = (source_path, name)
    if binding_key in _seen:
        raise ValueError(f"cyclic literal binding for {name} in {source_path}")
    seen = _seen | {binding_key}
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    visitor = _ModuleBindingVisitor(name)
    visitor.visit(tree)
    if visitor.has_star_import:
        raise ValueError(f"{name} may be rebound by a module-level star import in {source_path}")
    if not visitor.bindings:
        raise _LiteralBindingNotFoundError(f"{name} has no top-level binding in {source_path}")
    if len(visitor.bindings) != 1:
        raise ValueError(f"{name} has multiple top-level bindings in module {source_path}")

    direct_bindings: list[tuple[ast.stmt, ast.AST, str]] = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            if len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
                if statement.targets[0].id == name:
                    direct_bindings.append((statement, statement.targets[0], "assignment"))
        elif isinstance(statement, ast.AnnAssign):
            if isinstance(statement.target, ast.Name) and statement.target.id == name:
                direct_bindings.append((statement, statement.target, "assignment"))
        elif isinstance(statement, ast.ImportFrom):
            for alias in statement.names:
                if alias.name != "*" and (alias.asname or alias.name) == name:
                    direct_bindings.append((statement, alias, "import"))

    event, kind = visitor.bindings[0]
    if (
        len(direct_bindings) != 1
        or direct_bindings[0][1] is not event
        or direct_bindings[0][2] != kind
    ):
        raise ValueError(
            f"{name} is not one supported direct module literal or import binding in {source_path}"
        )
    node = direct_bindings[0][0]
    if kind == "import":
        if not isinstance(node, ast.ImportFrom):
            raise ValueError(f"{name} does not use a supported absolute polisyos import")
        imported_name = next(alias.name for alias in node.names if alias is event)
        if (
            node.level != 0
            or not node.module
            or not (node.module == "polisyos" or node.module.startswith("polisyos."))
        ):
            raise ValueError(f"{name} does not use a supported absolute polisyos import")
        owner_path = _source_module_path(node.module, root)
        return _literal_assignment(owner_path, imported_name, source_root=root, _seen=seen)

    value = node.value
    if value is None:
        raise ValueError(f"{name} has no literal value in {source_path}")
    return _literal_eval_with_names(
        value,
        source_path=source_path,
        source_root=root,
        _seen=seen,
    )


def _source_module_path(module_name: str, source_root: Path) -> Path:
    """Resolve a source module to one unambiguous Python file under ``source_root``."""
    module_path = source_root.joinpath(*module_name.split("."))
    file_path = module_path.with_suffix(".py")
    package_path = module_path / "__init__.py"
    candidates = [candidate for candidate in (file_path, package_path) if candidate.is_file()]
    if len(candidates) != 1:
        raise ValueError(
            f"source module {module_name!r} resolves to {len(candidates)} files under {source_root}"
        )
    owner_path = candidates[0].resolve()
    if not owner_path.is_relative_to(source_root.resolve()):
        raise ValueError(f"source module {module_name!r} escaped {source_root}")
    return owner_path


def _literal_eval_with_names(
    node: ast.AST,
    *,
    source_path: Path,
    source_root: Path,
    _seen: frozenset[tuple[Path, str]],
) -> object:
    if isinstance(node, ast.Name):
        try:
            return _literal_assignment(source_path, node.id, source_root=source_root, _seen=_seen)
        except _LiteralBindingNotFoundError:
            if node.id in _KNOWN_LITERAL_NAMES:
                return _KNOWN_LITERAL_NAMES[node.id]
            raise
    if isinstance(node, ast.Dict):
        if any(key is None for key in node.keys):
            raise ValueError("dictionary unpacking is not a supported literal binding")
        return {
            _literal_eval_with_names(
                key, source_path=source_path, source_root=source_root, _seen=_seen
            ): _literal_eval_with_names(
                value, source_path=source_path, source_root=source_root, _seen=_seen
            )
            for key, value in zip(node.keys, node.values, strict=True)
        }
    if isinstance(node, ast.Tuple):
        return tuple(
            _literal_eval_with_names(
                item, source_path=source_path, source_root=source_root, _seen=_seen
            )
            for item in node.elts
        )
    if isinstance(node, ast.List):
        return [
            _literal_eval_with_names(
                item, source_path=source_path, source_root=source_root, _seen=_seen
            )
            for item in node.elts
        ]
    return ast.literal_eval(node)


def _source_exists(repo_root: Path, rel_path: str) -> bool:
    return (repo_root / rel_path).exists()
