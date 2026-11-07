"""Resolve finite source-declared conditional export profiles without imports."""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import dataclass
from itertools import product
from typing import TYPE_CHECKING, Final, Literal

if TYPE_CHECKING:
    from collections.abc import Callable

SOURCE_EXPORT_PROFILE_SCHEMA_VERSION: Final[Literal["policyos.source-export-profile.v1"]] = (
    "policyos.source-export-profile.v1"
)
MAX_CONDITIONAL_EXPORT_PROFILES: Final = 32


@dataclass(frozen=True, slots=True)
class SourceExportCondition:
    """One statically profiled optional-backend condition.

    Attributes:
        expression: Source expression for the importlib ``find_spec`` predicate.
        value: The assumed boolean value for this source-derived profile.
    """

    expression: str
    value: bool


@dataclass(frozen=True, slots=True)
class SourceExportProfile:
    """One source-derived export list under explicit static conditions.

    ``runtime_condition_evaluation`` remains ``UNRUN`` because profiles are
    derived from syntax and never observe backend availability.

    Attributes:
        conditions: Optional-backend predicates and their profiled boolean values.
        exports: Ordered names returned by the caller's export resolver.
        schema_version: Stable profile schema identifier.
        runtime_condition_evaluation: Literal marker that runtime evaluation was not run.
    """

    conditions: tuple[SourceExportCondition, ...]
    exports: tuple[str, ...]
    schema_version: Literal["policyos.source-export-profile.v1"] = (
        SOURCE_EXPORT_PROFILE_SCHEMA_VERSION
    )
    runtime_condition_evaluation: Literal["UNRUN"] = "UNRUN"


@dataclass(frozen=True, slots=True)
class _FindSpecOwner:
    """A source-proven import binding for ``importlib.util.find_spec``."""

    local_name: str
    expression_path: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _PredicateAssignment:
    """A unique top-level name bound to a literal find_spec predicate."""

    name: str
    line: int
    column: int
    expression: str


class _UnknownProfileError(ValueError):
    """The module contains a conditional that this finite reader cannot prove."""


def resolve_conditional_export_profiles(
    tree: ast.Module,
    resolve_exports: Callable[[ast.Module], tuple[str, ...]],
) -> tuple[SourceExportProfile, ...]:
    """Return finite export profiles for recognized optional-backend predicates.

    The reader accepts only unrebound, top-level ``importlib.util.find_spec``
    predicates with one literal dependency name. It substitutes those exact
    predicate values in deep-copied ASTs, flattens module-level branches whose
    boolean values are source-known, and delegates export and binding proof to
    ``resolve_exports``. No source module or backend is imported or executed.

    Unknown branches, unsupported export mutations, invalid callback results,
    callback ``ValueError`` failures, and profile families larger than
    ``MAX_CONDITIONAL_EXPORT_PROFILES`` return an empty tuple. Empty means
    unresolved; callers must not treat it as an empty export declaration.

    Args:
        tree: Parsed source module to inspect without mutating.
        resolve_exports: Existing export resolver called on each flattened profile.

    Returns:
        Ordered source export profiles, or an empty tuple when the total cannot
        be established within the bounded grammar.
    """
    if not isinstance(tree, ast.Module) or not callable(resolve_exports):
        return ()

    try:
        predicates = _predicate_assignments(tree)
    except (AttributeError, TypeError, ValueError):
        return ()

    # This helper inventories explicit optional-backend profiles; it does not
    # turn an unconditional facade into a synthetic one-profile family.
    if not predicates:
        return ()

    profile_count = 1 << len(predicates)
    if profile_count > MAX_CONDITIONAL_EXPORT_PROFILES:
        return ()

    profiles: list[SourceExportProfile] = []
    for values in product((False, True), repeat=len(predicates)):
        condition_rows = tuple(
            SourceExportCondition(expression=predicate.expression, value=value)
            for predicate, value in zip(predicates, values, strict=True)
        )
        substitutions = {
            (predicate.name, predicate.line, predicate.column): value
            for predicate, value in zip(predicates, values, strict=True)
        }

        try:
            profiled_tree = _flatten_profile(
                tree,
                substitutions=substitutions,
            )
            exports = resolve_exports(profiled_tree)
        except (ValueError, TypeError, SyntaxError, _UnknownProfileError):
            return ()

        if (
            not isinstance(exports, tuple)
            or not all(isinstance(name, str) for name in exports)
            or len(exports) != len(set(exports))
        ):
            return ()
        profiles.append(SourceExportProfile(conditions=condition_rows, exports=exports))

    return tuple(profiles)


def _module_scope_nodes(tree: ast.Module) -> tuple[ast.AST, ...]:
    """Return module-executed syntax, excluding function and class bodies."""
    nodes: list[ast.AST] = []

    def visit(node: ast.AST) -> None:
        nodes.append(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            return
        for child in ast.iter_child_nodes(node):
            visit(child)

    for statement in tree.body:
        visit(statement)
    return tuple(nodes)


def _node_binds_name(node: ast.AST, name: str) -> bool:
    """Return whether one module-scope syntax node binds ``name``."""
    if isinstance(node, ast.Import):
        return any((alias.asname or alias.name.split(".", 1)[0]) == name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return any(
            alias.name != "*" and (alias.asname or alias.name) == name for alias in node.names
        )
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name == name
    if isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
        return getattr(node, "name", None) == name

    targets: tuple[ast.AST, ...] = ()
    if isinstance(node, (ast.Assign, ast.Delete)):
        targets = tuple(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr, ast.TypeAlias)):
        targets = (node.target if hasattr(node, "target") else node.name,)
    elif isinstance(node, (ast.For, ast.AsyncFor)):
        targets = (node.target,)
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        targets = tuple(item.optional_vars for item in node.items if item.optional_vars is not None)

    return any(
        isinstance(child, ast.Name)
        and child.id == name
        and isinstance(child.ctx, (ast.Store, ast.Del))
        for target in targets
        for child in ast.walk(target)
    )


def _module_scope_bindings(tree: ast.Module, name: str) -> tuple[ast.AST, ...]:
    """Return every module-scope binding or rebind of ``name``."""
    return tuple(node for node in _module_scope_nodes(tree) if _node_binds_name(node, name))


def _find_spec_owners(tree: ast.Module) -> tuple[_FindSpecOwner, ...]:
    """Find unique unrebound stdlib bindings for literal find_spec calls."""
    owners: list[_FindSpecOwner] = []
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                if alias.name not in {"importlib", "importlib.util"}:
                    continue
                local_name = alias.asname or alias.name.split(".", 1)[0]
                local_bindings = [
                    item
                    for item in statement.names
                    if (item.asname or item.name.split(".", 1)[0]) == local_name
                ]
                if len(local_bindings) != 1 or _module_scope_bindings(tree, local_name) != (
                    statement,
                ):
                    continue
                if alias.asname or alias.name == "importlib":
                    expression_path = (
                        (local_name, "find_spec")
                        if alias.name == "importlib.util"
                        else (
                            local_name,
                            "util",
                            "find_spec",
                        )
                    )
                else:
                    expression_path = (local_name, "util", "find_spec")
                owners.append(_FindSpecOwner(local_name, expression_path))
        elif isinstance(statement, ast.ImportFrom):
            if statement.level != 0 or statement.module != "importlib.util":
                continue
            for alias in statement.names:
                if alias.name != "find_spec":
                    continue
                local_name = alias.asname or alias.name
                local_bindings = [
                    item
                    for item in statement.names
                    if item.name != "*" and (item.asname or item.name) == local_name
                ]
                if len(local_bindings) == 1 and _module_scope_bindings(tree, local_name) == (
                    statement,
                ):
                    owners.append(_FindSpecOwner(local_name, (local_name,)))
    return tuple(owners)


def _attribute_path(node: ast.AST) -> tuple[str, ...] | None:
    """Return a dotted name path for an AST name or attribute expression."""
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        parent = _attribute_path(node.value)
        return (*parent, node.attr) if parent is not None else None
    return None


def _find_spec_dependency(
    expression: ast.AST,
    owners: tuple[_FindSpecOwner, ...],
) -> str | None:
    """Recognize exactly ``find_spec('literal') is not None``."""
    if (
        not isinstance(expression, ast.Compare)
        or len(expression.ops) != 1
        or not isinstance(expression.ops[0], ast.IsNot)
        or len(expression.comparators) != 1
        or not isinstance(expression.comparators[0], ast.Constant)
        or expression.comparators[0].value is not None
        or not isinstance(expression.left, ast.Call)
        or expression.left.keywords
        or len(expression.left.args) != 1
        or not isinstance(expression.left.args[0], ast.Constant)
        or not isinstance(expression.left.args[0].value, str)
        or not expression.left.args[0].value
    ):
        return None
    path = _attribute_path(expression.left.func)
    if path is None or sum(owner.expression_path == path for owner in owners) != 1:
        return None
    return expression.left.args[0].value


def _find_spec_receiver_name(expression: ast.AST) -> ast.Name | None:
    """Return the imported name at the root of a recognized probe receiver."""
    if not isinstance(expression, ast.Compare) or not isinstance(expression.left, ast.Call):
        return None
    receiver = expression.left.func
    while isinstance(receiver, ast.Attribute):
        receiver = receiver.value
    return receiver if isinstance(receiver, ast.Name) else None


def _owners_used_only_as_probe_receivers(
    tree: ast.Module,
    owners: tuple[_FindSpecOwner, ...],
) -> tuple[_FindSpecOwner, ...]:
    """Reject imported find_spec owners that are rebound or escape their probe."""
    allowed_uses: dict[_FindSpecOwner, set[int]] = {owner: set() for owner in owners}
    for statement in tree.body:
        assignment = _assignment_name_and_value(statement)
        if assignment is None:
            continue
        _name, expression = assignment
        for owner in owners:
            if _find_spec_dependency(expression, (owner,)) is None:
                continue
            receiver = _find_spec_receiver_name(expression)
            if receiver is not None and receiver.id == owner.local_name:
                allowed_uses[owner].add(id(receiver))

    all_names = tuple(node for node in ast.walk(tree) if isinstance(node, ast.Name))
    return tuple(
        owner
        for owner in owners
        if allowed_uses[owner]
        and all(
            node.id != owner.local_name
            or (isinstance(node.ctx, ast.Load) and id(node) in allowed_uses[owner])
            for node in all_names
        )
    )


def _assignment_name_and_value(
    node: ast.AST,
) -> tuple[str, ast.expr] | None:
    """Return a single simple assignment target and its value expression."""
    if (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    ):
        return node.targets[0].id, node.value
    if (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.value is not None
    ):
        return node.target.id, node.value
    return None


def _predicate_assignments(tree: ast.Module) -> tuple[_PredicateAssignment, ...]:
    """Find source-unique assignments of literal stdlib availability predicates."""
    owners = _owners_used_only_as_probe_receivers(tree, _find_spec_owners(tree))
    predicates: list[_PredicateAssignment] = []
    for statement in tree.body:
        assignment = _assignment_name_and_value(statement)
        if assignment is None:
            continue
        name, value = assignment
        dependency = _find_spec_dependency(value, owners)
        if dependency is None or _module_scope_bindings(tree, name) != (statement,):
            continue
        if statement.lineno <= 0 or statement.col_offset < 0:
            continue
        predicates.append(
            _PredicateAssignment(
                name=name,
                line=statement.lineno,
                column=statement.col_offset,
                expression=ast.unparse(value),
            )
        )
    return tuple(predicates)


def _known_boolean(expression: ast.AST, values: dict[str, bool]) -> bool | None:
    """Evaluate only boolean literals, source-known names, and boolean operators."""
    if isinstance(expression, ast.Constant) and type(expression.value) is bool:
        return expression.value
    if isinstance(expression, ast.Name):
        return values.get(expression.id)
    if isinstance(expression, ast.UnaryOp) and isinstance(expression.op, ast.Not):
        value = _known_boolean(expression.operand, values)
        return None if value is None else not value
    if isinstance(expression, ast.BoolOp):
        children = tuple(_known_boolean(value, values) for value in expression.values)
        if any(value is None for value in children):
            return None
        if isinstance(expression.op, ast.And):
            return all(children)
        if isinstance(expression.op, ast.Or):
            return any(children)
    return None


def _written_names(node: ast.AST) -> tuple[str, ...]:
    """Return names written by one module-scope statement."""
    return tuple(
        dict.fromkeys(
            child.id
            for child in ast.walk(node)
            if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del))
        )
    )


def _invalidate_known_bindings(statement: ast.stmt, values: dict[str, bool]) -> None:
    """Drop boolean knowledge for bindings whose value is not statically known."""
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        values.pop(statement.name, None)
        return

    if isinstance(statement, (ast.Assign, ast.AnnAssign)):
        assignment = _assignment_name_and_value(statement)
        known = _known_boolean(assignment[1], values) if assignment is not None else None
        names = _written_names(statement)
        for name in names:
            values.pop(name, None)
        if assignment is not None and known is not None:
            values[assignment[0]] = known
        return

    if isinstance(statement, ast.ImportFrom):
        names = tuple(alias.asname or alias.name for alias in statement.names if alias.name != "*")
        for name in names:
            values.pop(name, None)
        if (
            statement.module == "typing"
            and statement.level == 0
            and _has_type_checking_alias(statement)
            and "TYPE_CHECKING" in names
        ):
            values["TYPE_CHECKING"] = False
        return

    if isinstance(statement, ast.Import):
        for alias in statement.names:
            values.pop(alias.asname or alias.name.split(".", 1)[0], None)
        return

    for name in _written_names(statement):
        values.pop(name, None)


def _has_type_checking_alias(statement: ast.ImportFrom) -> bool:
    """Return whether an import binds the unaliased standard TYPE_CHECKING name."""
    return any(
        alias.name == "TYPE_CHECKING" and (alias.asname or alias.name) == "TYPE_CHECKING"
        for alias in statement.names
    )


def _flatten_profile(
    tree: ast.Module,
    *,
    substitutions: dict[tuple[str, int, int], bool],
) -> ast.Module:
    """Copy, substitute recognized probes, and flatten source-known module branches."""
    copied = deepcopy(tree)
    known: dict[str, bool] = {}
    body: list[ast.stmt] = []

    def flatten(statement: ast.stmt) -> None:
        if isinstance(statement, ast.If):
            selected_value = _known_boolean(statement.test, known)
            if selected_value is None:
                raise _UnknownProfileError("module-level conditional is not source-known")
            selected_body = statement.body if selected_value else statement.orelse
            for child in selected_body:
                flatten(child)
            return

        assignment = _assignment_name_and_value(statement)
        if assignment is not None:
            name, _value = assignment
            key = (name, statement.lineno, statement.col_offset)
            if key in substitutions:
                literal = ast.copy_location(ast.Constant(value=substitutions[key]), statement.value)
                statement.value = literal

        body.append(statement)
        _invalidate_known_bindings(statement, known)

    for statement in copied.body:
        flatten(statement)

    if any(_contains_unflattened_module_if(statement) for statement in body):
        raise _UnknownProfileError("module-executed conditional is outside the flattening grammar")

    return ast.fix_missing_locations(ast.Module(body=body, type_ignores=copied.type_ignores))


def _contains_unflattened_module_if(statement: ast.AST) -> bool:
    """Find an unhandled module-executed conditional in retained syntax."""
    if isinstance(statement, ast.If):
        return True
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        return False
    return any(_contains_unflattened_module_if(child) for child in ast.iter_child_nodes(statement))
