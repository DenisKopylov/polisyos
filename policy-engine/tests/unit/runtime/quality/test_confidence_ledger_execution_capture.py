"""Execution-source capture reuses derivations without reusing live trust."""

from __future__ import annotations

import ast
import builtins
import importlib.util
import sys
import types
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from polisyos.runtime.quality import confidence_ledger as ledger

_SOURCE = (
    "OFFSET = 3\n"
    "def first(value=1):\n"
    "    return value + OFFSET\n"
    "def second(value):\n"
    "    return value * 2\n"
    "def third(value):\n"
    "    return first(second(value))\n"
)


@pytest.fixture
def capture_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Load real Python source through its normal selected file loader."""
    root = tmp_path / "engine"
    package = root / "src" / "polisyos"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(ledger, "_loaded_policy_engine_root", lambda: root)

    def load(name: str = "execution_capture_fixture", *, source: str = _SOURCE) -> types.ModuleType:
        module_name = "polisyos." + name
        source_path = package / (name + ".py")
        source_path.write_text(source, encoding="utf-8")
        spec = importlib.util.spec_from_file_location(module_name, source_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, module_name, module)
        spec.loader.exec_module(module)
        assert module.third(4) == 11
        return module

    return load


def _capture(*modules: types.ModuleType) -> dict[str, object]:
    executed = tuple(
        (module.__name__, getattr(module, name).__code__)
        for module in modules
        for name in ("first", "second", "third")
    )
    return ledger.capture_execution_source_bindings(
        tuple(module.__name__ for module in modules),
        executed,
        bound_entry_code=((modules[0].__name__, modules[0].third.__code__),),
    )


def _count_source_derivations(monkeypatch: pytest.MonkeyPatch):
    compiles: Counter[str] = Counter()
    indexes: Counter[str] = Counter()
    original_index = ledger._loader_code_hashes_by_qualname

    def counted_compile(source: object, filename: str, *args: Any, **kwargs: Any):
        if Path(filename).name.startswith("execution_capture_fixture"):
            compiles[filename] += 1
        return builtins.compile(source, filename, *args, **kwargs)

    def counted_index(code: types.CodeType):
        if Path(code.co_filename).name.startswith("execution_capture_fixture"):
            indexes[code.co_filename] += 1
        return original_index(code)

    monkeypatch.setattr(ledger, "compile", counted_compile, raising=False)
    monkeypatch.setattr(ledger, "_loader_code_hashes_by_qualname", counted_index)
    return compiles, indexes


def test_execution_capture_indexes_each_source_once_per_capture(
    capture_case, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Three executed functions plus one bound entry need one source index."""
    module = capture_case()
    path = str(Path(module.__file__).resolve())
    compiles, indexes = _count_source_derivations(monkeypatch)

    first = _capture(module)

    assert len(first["executed_code"]) == 3
    assert len(first["bound_entry_code"]) == 1
    assert compiles == {path: 1}
    assert indexes == {path: 1}
    assert ledger._active_integrity_analysis() is None

    second = _capture(module)

    assert second == first
    assert compiles == {path: 2}
    assert indexes == {path: 2}
    assert ledger._active_integrity_analysis() is None


def test_execution_capture_keeps_distinct_source_filenames(
    capture_case, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Equal source bytes in distinct loader files retain separate identities."""
    first = capture_case("execution_capture_fixture_first")
    second = capture_case("execution_capture_fixture_second")
    paths = {str(Path(module.__file__).resolve()) for module in (first, second)}
    assert len(paths) == 2
    compiles, indexes = _count_source_derivations(monkeypatch)

    captured = _capture(first, second)

    assert len(captured["executed_code"]) == 6
    assert compiles == dict.fromkeys(paths, 1)
    assert indexes == dict.fromkeys(paths, 1)


def test_execution_capture_rereads_source_between_captures(capture_case) -> None:
    """A prior capture cannot hide changed source bytes from the next capture."""
    module = capture_case()
    first = _capture(module)
    path = Path(module.__file__)
    path.write_text(_SOURCE + "\n# next source snapshot\n", encoding="utf-8")

    second = _capture(module)

    assert second["source_closure_hash"] != first["source_closure_hash"]


def test_execution_capture_refuses_source_drift_during_capture(
    capture_case, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mid-pass file edit cannot be hidden by a reused compiled source."""
    module = capture_case()
    path = Path(module.__file__).resolve()
    original_index = ledger._loader_code_hashes_by_qualname
    changed = False

    def mutate_after_index(code: types.CodeType):
        nonlocal changed
        result = original_index(code)
        if Path(code.co_filename).resolve() == path and not changed:
            path.write_text(_SOURCE + "\n# changed during capture\n", encoding="utf-8")
            changed = True
        return result

    monkeypatch.setattr(ledger, "_loader_code_hashes_by_qualname", mutate_after_index)

    with pytest.raises(ledger.ConfidenceLedgerError, match="canonical_loaded_runtime_mismatch"):
        _capture(module)

    assert changed
    assert ledger._active_integrity_analysis() is None


def test_execution_capture_refuses_source_symlink_retarget(
    capture_case, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stable physical files cannot hide a changed logical loader source target."""
    module = capture_case()
    logical = Path(module.__file__)
    original_target = logical.with_name("execution_capture_fixture_original.py")
    replacement_target = logical.with_name("execution_capture_fixture_replacement.py")
    logical.replace(original_target)
    replacement_target.write_text(_SOURCE + "\n# distinct source bytes\n", encoding="utf-8")
    logical.symlink_to(original_target.name)
    original_bindings = ledger._execution_loaded_slot_bindings

    def retarget_after_bindings(*args: Any, **kwargs: Any):
        result = original_bindings(*args, **kwargs)
        logical.unlink()
        logical.symlink_to(replacement_target.name)
        return result

    monkeypatch.setattr(ledger, "_execution_loaded_slot_bindings", retarget_after_bindings)

    with pytest.raises(ledger.ConfidenceLedgerError, match="canonical_loaded_runtime_mismatch"):
        _capture(module)

    assert original_target.read_text() == _SOURCE
    assert replacement_target.read_text() == _SOURCE + "\n# distinct source bytes\n"
    assert logical.resolve() == replacement_target.resolve()


def test_execution_capture_keeps_live_bindings_fresh(capture_case) -> None:
    """Same-code changed defaults cannot reuse the prior captured binding hash."""
    module = capture_case()
    first = _capture(module)
    module.first.__defaults__ = (17,)
    assert module.first() == 20

    second = _capture(module)

    assert second["loaded_binding_hash"] != first["loaded_binding_hash"]


def test_execution_capture_refuses_changed_live_code(capture_case) -> None:
    """A live slot with different code cannot borrow its unchanged source file."""
    module = capture_case()
    _capture(module)
    replacement = compile("def first(value=1):\n    return 42\n", module.__file__, "exec")
    module.first.__code__ = next(
        item for item in replacement.co_consts if isinstance(item, types.CodeType)
    )
    assert module.first() == 42

    with pytest.raises(ledger.ConfidenceLedgerError, match="n5_consumed_loaded_binding_mismatch"):
        _capture(module)


def test_execution_source_index_preserves_compile_optimization(tmp_path: Path) -> None:
    """Compilation policy remains part of the pass-local derivation identity."""
    path = tmp_path / "debug_policy.py"
    path.write_text("def enabled():\n    return __debug__\n", encoding="utf-8")
    analysis = ledger._IntegrityAnalysisContext()

    normal, normal_index = analysis.compiled_source_index(path, optimize=0)
    optimized, optimized_index = analysis.compiled_source_index(path, optimize=1)
    repeated, repeated_index = analysis.compiled_source_index(path, optimize=0)

    normal_function = next(item for item in normal.co_consts if isinstance(item, types.CodeType))
    optimized_function = next(
        item for item in optimized.co_consts if isinstance(item, types.CodeType)
    )
    assert normal_function.co_consts[-1] is True
    assert optimized_function.co_consts[-1] is False
    assert normal_index["enabled"] != optimized_index["enabled"]
    assert repeated is normal and repeated_index is normal_index


def test_execution_capture_does_not_reuse_an_enclosing_capture(capture_case) -> None:
    """Nested use restores its caller without sharing source trust across captures."""
    module = capture_case()
    enclosing = ledger._IntegrityAnalysisContext()
    token = ledger._ACTIVE_INTEGRITY_ANALYSIS.set(enclosing)
    try:
        first = _capture(module)
        assert ledger._active_integrity_analysis() is enclosing
        Path(module.__file__).write_text(_SOURCE + "\n# next capture\n", encoding="utf-8")
        second = _capture(module)
        assert second["source_closure_hash"] != first["source_closure_hash"]
        assert ledger._active_integrity_analysis() is enclosing
        assert enclosing._source_code_indexes == {}
    finally:
        ledger._ACTIVE_INTEGRITY_ANALYSIS.reset(token)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [("1024**3", 1073741824), ("2 * 1024 * 1024", 2097152), ("-(3 + 5)", -8)],
)
def test_compiler_folded_source_constants_use_the_existing_inert_reader(
    expression: str, expected: int
) -> None:
    """Pure computed integer defaults are source values, not an unknown call."""
    node = ast.parse(expression, mode="eval").body

    assert ledger._source_immutable_constant_expression(node) == expected
    assert ledger._source_literal(node) == expected
    assert not ledger._exact_literal_equal(True, expected)


@pytest.mark.parametrize(
    "expression",
    [
        "unknown_name",
        "side_effect()",
        "provider.value",
        "1 if True else side_effect()",
        "1024 ** 10000",
        "[1, 2]",
        "1e309 - 1e309",
        "(1e309 - 1e309,)",
    ],
)
def test_source_constants_keep_unresolved_and_nonconstant_expressions_closed(
    expression: str,
) -> None:
    """No name, call, attribute, huge runtime operation or mutable default is evaluated."""
    node = ast.parse(expression, mode="eval").body

    assert ledger._source_immutable_constant_expression(node) is ledger._SOURCE_DERIVATION_FAILED
    assert ledger._source_literal(node) is ledger._UNSUPPORTED_SOURCE_LITERAL


def test_source_literal_preserves_existing_literal_tuple_size() -> None:
    """The bounded folding fallback does not narrow already-supported literals."""
    expected = tuple(range(100))
    node = ast.parse(repr(expected), mode="eval").body

    assert len(tuple(ast.walk(node))) > 80
    assert ledger._source_literal(node) == expected


def test_actual_export_limit_source_route_and_live_value_remain_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real computed Core export limit resolves, while altered runtime values refuse."""
    from polisyos.core.artifacts import _export_admission as provider

    root = ledger._loaded_policy_engine_root()
    name = "DEFAULT_MAX_RETAINED_BYTES"
    tree = ast.parse(Path(provider.__file__).read_bytes(), filename=provider.__file__)
    route = ledger._source_module_direct_binding_route(
        root,
        provider.__name__,
        name,
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        visited=frozenset(),
    )
    assert route == ("symbol", provider.__name__, name)

    def loaded_value():
        return ledger._source_dataclass_named_constant(
            name,
            repo_root=root,
            tree=tree,
            module=provider,
            module_name=provider.__name__,
        )

    assert loaded_value() == 1073741824
    monkeypatch.setattr(provider, name, 1073741825)
    assert loaded_value() is ledger._SOURCE_DERIVATION_FAILED
    monkeypatch.setattr(provider, name, True)
    assert loaded_value() is ledger._SOURCE_DERIVATION_FAILED


@pytest.mark.parametrize("expression", ["1024**3", "2 * 1024 * 1024"])
def test_folded_default_reaches_actual_function_default_consumer(
    capture_case, expression: str
) -> None:
    """The real loaded callable's folded default is accepted, then mismatch refuses."""
    module = capture_case(source=_SOURCE.replace("value=1", f"value={expression}"))
    tree = ast.parse(Path(module.__file__).read_bytes(), filename=module.__file__)
    declaration = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "first"
    )
    original_default = module.first.__defaults__[0]
    assert type(original_default) is int
    assert module.first() == original_default + 3
    assert ledger._source_function_defaults_match(module.first, declaration)

    module.first.__defaults__ = (original_default + 1,)
    assert module.first() == original_default + 4
    assert not ledger._source_function_defaults_match(module.first, declaration)
    module.first.__defaults__ = (True,)
    assert not ledger._source_function_defaults_match(module.first, declaration)


def test_computed_float_default_preserves_sign_through_actual_consumer(capture_case) -> None:
    """Changing -0 to +0 changes a callable's behavior and must break the binding."""
    source = _SOURCE + (
        "\nimport math\ndef classify(value=-(1.0 * 0.0)):\n    return math.copysign(1.0, value)\n"
    )
    module = capture_case(source=source)
    tree = ast.parse(source, filename=module.__file__)
    declaration = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "classify"
    )
    assert module.classify() == -1.0
    assert ledger._source_function_defaults_match(module.classify, declaration)

    module.classify.__defaults__ = (0.0,)

    assert module.classify() == 1.0
    assert not ledger._source_function_defaults_match(module.classify, declaration)
    assert not ledger._exact_literal_equal((-0.0,), (0.0,))


def test_compiler_folded_nan_default_remains_unestablished(capture_case) -> None:
    """A compiler-produced NaN cannot pass an exact source-default gate."""
    source = _SOURCE + ("\ndef not_a_number(value=1e309 - 1e309):\n    return value != value\n")
    module = capture_case(source=source)
    tree = ast.parse(source, filename=module.__file__)
    declaration = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "not_a_number"
    )
    original = module.not_a_number.__defaults__[0]
    assert type(original) is float and original != original
    assert module.not_a_number()
    assert not ledger._source_function_defaults_match(module.not_a_number, declaration)
    assert not ledger._exact_literal_equal(original, original)


def test_actual_export_report_dataclass_keeps_imported_constant_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Core's real source-replayed report accepts its default and rejects alias drift."""
    from polisyos.core.artifacts import _export_admission as constants
    from polisyos.core.artifacts import _transfer_ops as provider

    root = ledger._loaded_policy_engine_root()
    path = Path(provider.__file__).resolve()
    tree = ast.parse(path.read_bytes(), filename=str(path))
    declaration = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ExportReport"
    )

    def matches():
        return ledger._source_python_dataclass_binding_supported(
            root,
            provider.__name__,
            "ExportReport",
            path.relative_to(root),
            tree,
            declaration,
        )

    assert matches()
    for changed in (1073741825, True):
        monkeypatch.setattr(constants, "DEFAULT_MAX_RETAINED_BYTES", changed)
        monkeypatch.setattr(provider, "DEFAULT_MAX_RETAINED_BYTES", changed)
        assert provider.DEFAULT_MAX_RETAINED_BYTES is constants.DEFAULT_MAX_RETAINED_BYTES
        assert not matches()
