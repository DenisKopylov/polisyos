"""Finite source-declared export profiles stay non-authoritative and bounded."""

from __future__ import annotations

import ast
from typing import Any

import pytest

from tools.devx.architecture import guardrails
from tools.devx.architecture.conditional_exports import (
    MAX_CONDITIONAL_EXPORT_PROFILES,
    SOURCE_EXPORT_PROFILE_SCHEMA_VERSION,
    SourceExportCondition,
    SourceExportProfile,
    resolve_conditional_export_profiles,
)

_UNKNOWN = object()


def _literal_or_unknown(node: ast.expr) -> Any:
    try:
        return ast.literal_eval(node)
    except (TypeError, ValueError):
        return _UNKNOWN


def _bound_literal_export_reader(tree: ast.Module) -> tuple[str, ...]:
    """Read literal ``__all__`` writes and prove every export is imported."""
    values: dict[str, Any] = {}
    imported: set[str] = set()
    exports: list[str] | None = None

    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom):
            imported.update(
                alias.asname or alias.name for alias in statement.names if alias.name != "*"
            )
        elif isinstance(statement, ast.Import):
            imported.update(
                alias.asname or alias.name.split(".", 1)[0] for alias in statement.names
            )
        elif isinstance(statement, ast.Assign):
            assigned = _literal_or_unknown(statement.value)
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    values[target.id] = assigned
                    if target.id == "__all__":
                        if not isinstance(assigned, (tuple, list)) or not all(
                            isinstance(name, str) for name in assigned
                        ):
                            raise ValueError("__all__ is not a literal string sequence")
                        exports = list(assigned)
        elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
            if (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "__all__"
                and call.func.attr == "extend"
                and len(call.args) == 1
                and not call.keywords
                and exports is not None
            ):
                extension = (
                    values.get(call.args[0].id, _UNKNOWN)
                    if isinstance(call.args[0], ast.Name)
                    else _literal_or_unknown(call.args[0])
                )
                if not isinstance(extension, (tuple, list)) or not all(
                    isinstance(name, str) for name in extension
                ):
                    raise ValueError("dynamic __all__ extension")
                exports.extend(extension)
            elif isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
                if call.func.value.id == "__all__":
                    raise ValueError("unsupported __all__ mutation")

    if exports is None or len(exports) != len(set(exports)):
        raise ValueError("missing or duplicate exports")
    if not set(exports).issubset(imported | set(values)):
        raise ValueError("an export is not bound in this profile")
    return tuple(exports)


def _profile_fixture() -> tuple[ast.Module, tuple[str, ...], tuple[str, ...]]:
    base = tuple(f"Base{index:02d}" for index in range(41))
    optional = tuple(f"Materialize{index:02d}" for index in range(18))
    base_names = ", ".join(base)
    base_literals = ", ".join(repr(name) for name in base)
    optional_names = ", ".join(optional)
    optional_literals = ", ".join(repr(name) for name in optional)
    source = f"""\
import importlib.util as _util
_AVAILABLE = _util.find_spec("duckdb") is not None
from .base import {base_names}
__all__ = ({base_literals},)
if _AVAILABLE:
    from .materialize import {optional_names}
    _MATERIALIZE_EXPORTS = ({optional_literals},)
    _MATERIALIZE_AVAILABLE = True
else:
    _MATERIALIZE_EXPORTS = ()
    _MATERIALIZE_AVAILABLE = False
if _MATERIALIZE_AVAILABLE:
    __all__.extend(_MATERIALIZE_EXPORTS)
"""
    return ast.parse(source), base, optional


def test_actual_ast_profiles_preserve_41_and_59_ordered_bound_exports() -> None:
    tree, base, optional = _profile_fixture()
    original_ast = ast.dump(tree)

    profiles = resolve_conditional_export_profiles(tree, _bound_literal_export_reader)

    assert ast.dump(tree) == original_ast
    assert len(profiles) == 2
    assert all(isinstance(profile, SourceExportProfile) for profile in profiles)
    assert [condition.value for profile in profiles for condition in profile.conditions] == [
        False,
        True,
    ]
    assert profiles[0].exports == base
    assert profiles[1].exports == (*base, *optional)
    assert tuple(map(len, (profile.exports for profile in profiles))) == (41, 59)
    assert all(
        profile.schema_version == SOURCE_EXPORT_PROFILE_SCHEMA_VERSION for profile in profiles
    )
    assert all(profile.runtime_condition_evaluation == "UNRUN" for profile in profiles)
    assert profiles[0].conditions == (
        SourceExportCondition(expression="_util.find_spec('duckdb') is not None", value=False),
    )


def test_world_facade_profiles_use_the_existing_static_export_binding_proof() -> None:
    source = guardrails._facade_source_for("polisyos.fabric.world")
    tree = ast.parse(source.read_bytes())
    base_exports = next(
        ast.literal_eval(statement.value)
        for statement in tree.body
        if isinstance(statement, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in statement.targets
        )
    )
    optional_exports = next(
        ast.literal_eval(statement.value)
        for statement in ast.walk(tree)
        if isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and statement.target.id == "_MATERIALIZE_EXPORTS"
        and statement.value is not None
        and ast.literal_eval(statement.value)
    )

    profiles = resolve_conditional_export_profiles(
        tree, lambda profile_tree: guardrails._extract_exports(profile_tree, source)
    )

    assert [profile.exports for profile in profiles] == [
        tuple(base_exports),
        (*base_exports, *optional_exports),
    ]
    assert [len(profile.exports) for profile in profiles] == [41, 59]


@pytest.mark.parametrize(
    "escape",
    [
        "_importlib_util.find_spec = lambda name: object()",
        "_escaped_finder = _importlib_util.find_spec",
    ],
)
def test_actual_world_find_spec_owner_mutation_or_escape_is_unresolved(escape: str) -> None:
    source = guardrails._facade_source_for("polisyos.fabric.world")
    tree = ast.parse(source.read_bytes())
    predicate_index = next(
        index
        for index, statement in enumerate(tree.body)
        if isinstance(statement, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "_DUCKDB_AVAILABLE"
            for target in statement.targets
        )
    )
    tree.body.insert(predicate_index, ast.parse(escape).body[0])

    assert (
        resolve_conditional_export_profiles(
            tree, lambda profile_tree: guardrails._extract_exports(profile_tree, source)
        )
        == ()
    )


def test_direct_imported_find_spec_function_cannot_escape_as_a_method_object() -> None:
    source = """\
from importlib.util import find_spec as has_spec
_escaped_finder = has_spec
_AVAILABLE = has_spec('duckdb') is not None
from .base import Base
__all__ = ('Base',)
if _AVAILABLE:
    from .optional import Optional
    __all__.extend(('Optional',))
"""

    assert (
        resolve_conditional_export_profiles(ast.parse(source), _bound_literal_export_reader) == ()
    )


@pytest.mark.parametrize(
    "source",
    [
        """\
import importlib.util as util
util = replacement
_AVAILABLE = util.find_spec('duckdb') is not None
if _AVAILABLE:
    __all__ = ('Optional',)
else:
    __all__ = ('Base',)
""",
        """\
from importlib.util import find_spec
_AVAILABLE = find_spec('duckdb') is not None
_AVAILABLE = runtime_override
if _AVAILABLE:
    __all__ = ('Optional',)
else:
    __all__ = ('Base',)
""",
    ],
)
def test_shadowed_or_rebound_probe_is_unresolved(source: str) -> None:
    assert (
        resolve_conditional_export_profiles(ast.parse(source), _bound_literal_export_reader) == ()
    )


def test_function_local_assignment_does_not_rebind_the_module_probe() -> None:
    source = """\
import importlib.util as util
_AVAILABLE = util.find_spec('duckdb') is not None
def helper():
    _AVAILABLE = False
from .base import Base, Optional
__all__ = ('Base',)
if _AVAILABLE:
    __all__.extend(('Optional',))
"""
    profiles = resolve_conditional_export_profiles(ast.parse(source), _bound_literal_export_reader)

    assert [profile.exports for profile in profiles] == [("Base",), ("Base", "Optional")]


def test_supported_find_spec_import_forms_and_boolean_aliases_are_flattened_in_order() -> None:
    source = """\
from importlib.util import find_spec as has_spec
available = has_spec('duckdb') is not None
from .base import Base
__all__ = ('Base',)
if not available:
    _has_materialize = False
else:
    _has_materialize = True
if _has_materialize:
    from .materialize import Later, Earlier
    __all__.extend(('Later', 'Earlier'))
"""
    profiles = resolve_conditional_export_profiles(ast.parse(source), _bound_literal_export_reader)

    assert [profile.exports for profile in profiles] == [("Base",), ("Base", "Later", "Earlier")]
    assert profiles[1].conditions == (
        SourceExportCondition(expression="has_spec('duckdb') is not None", value=True),
    )


def test_only_imported_type_checking_name_is_statically_false_after_binding() -> None:
    source = """\
from importlib.util import find_spec
_AVAILABLE = find_spec('duckdb') is not None
from .base import Base
__all__ = ('Base',)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    __all__ = ('TypingOnly',)
"""
    profiles = resolve_conditional_export_profiles(ast.parse(source), _bound_literal_export_reader)

    assert [profile.exports for profile in profiles] == [("Base",), ("Base",)]

    before_import = ast.parse(
        """\
from importlib.util import find_spec
_AVAILABLE = find_spec('duckdb') is not None
if TYPE_CHECKING:
    __all__ = ('TypingOnly',)
from typing import TYPE_CHECKING
__all__ = ('Base',)
"""
    )
    assert resolve_conditional_export_profiles(before_import, _bound_literal_export_reader) == ()


def test_unknown_module_conditional_and_unflattened_try_conditional_return_unknown() -> None:
    for source in (
        """\
import importlib.util
_AVAILABLE = importlib.util.find_spec('duckdb') is not None
if runtime_flag:
    __all__ = ('Maybe',)
else:
    __all__ = ('Base',)
""",
        """\
import importlib.util
_AVAILABLE = importlib.util.find_spec('duckdb') is not None
try:
    if runtime_flag:
        __all__ = ('Maybe',)
except RuntimeError:
    pass
""",
    ):
        assert (
            resolve_conditional_export_profiles(ast.parse(source), _bound_literal_export_reader)
            == ()
        )


def test_missing_unbound_or_corrupt_export_callback_results_stay_unknown() -> None:
    tree, _base, _optional = _profile_fixture()

    def missing_binding(_tree: ast.Module) -> tuple[str, ...]:
        raise ValueError("unbound export")

    assert resolve_conditional_export_profiles(tree, missing_binding) == ()
    assert resolve_conditional_export_profiles(tree, lambda _tree: ["not-a-tuple"]) == ()  # type: ignore[arg-type]
    assert resolve_conditional_export_profiles(tree, lambda _tree: ("Duplicate", "Duplicate")) == ()
    assert resolve_conditional_export_profiles(tree, lambda _tree: ("bad", 1)) == ()  # type: ignore[arg-type]


def test_opaque_export_mutation_is_refused_by_the_existing_style_callback() -> None:
    source = """\
import importlib.util
_AVAILABLE = importlib.util.find_spec('duckdb') is not None
from .base import Base
__all__ = ('Base',)
if _AVAILABLE:
    __all__.extend(runtime_exports)
"""
    assert (
        resolve_conditional_export_profiles(ast.parse(source), _bound_literal_export_reader) == ()
    )


def test_unconditional_module_is_not_returned_as_a_fake_single_profile() -> None:
    source = "from .base import Base\n__all__ = ('Base',)\n"
    assert (
        resolve_conditional_export_profiles(ast.parse(source), _bound_literal_export_reader) == ()
    )


def test_profile_bound_is_explicit_and_rejects_six_independent_predicates() -> None:
    assert MAX_CONDITIONAL_EXPORT_PROFILES == 32
    predicates = "\n".join(
        f"P{index} = importlib.util.find_spec('backend{index}') is not None" for index in range(6)
    )
    source = f"import importlib.util\n{predicates}\n__all__ = ('Base',)\n"
    assert (
        resolve_conditional_export_profiles(ast.parse(source), _bound_literal_export_reader) == ()
    )
