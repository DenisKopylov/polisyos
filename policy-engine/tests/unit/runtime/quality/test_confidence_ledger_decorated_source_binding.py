"""Decorated source routes use the existing loaded-callable proof."""

from __future__ import annotations

import ast
import builtins
import functools
import importlib.util
import sys
import types
import typing
from contextlib import nullcontext
from functools import wraps
from pathlib import Path

import pytest

from polisyos.runtime.quality import confidence_ledger as ledger

_SOURCE = """from __future__ import annotations
from contextlib import contextmanager
from copy import deepcopy
from functools import lru_cache, wraps

SOURCE_VALUE = 4

@contextmanager
def scoped(value=4):
    yield value

@contextmanager
def other_scope(value=4):
    yield value + 7

@contextmanager
def global_scope():
    yield SOURCE_VALUE

@contextmanager
def builtin_scope():
    yield next(iter((4,)))

@lru_cache(maxsize=2, typed=True)
def cached(value=3):
    return value * 2

def local_decorator(offset=1):
    def decorate(method):
        @wraps(method)
        def wrapped(*args, **kwargs):
            if offset == -1:
                raise ValueError("invalid offset")
            return method(*args, **kwargs) + offset
        return wrapped
    return decorate

@local_decorator(offset=1)
def local(value=5):
    return value + 1

@deepcopy
def unsupported_identity(value=9):
    return value
"""


@pytest.fixture
def decorated_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    return _load_decorated_case(tmp_path, monkeypatch, _SOURCE)


def _load_decorated_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str):
    root = tmp_path / "engine"
    package = root / "src" / "polisyos"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    return root, _load_fixture_module(
        root, monkeypatch, "polisyos.decorated_source_fixture", source
    )


def _load_fixture_module(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    source: str,
    *,
    path: Path | None = None,
):
    path = path or root / "src" / "polisyos" / (name.rpartition(".")[2] + ".py")
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def _route(root: Path, module: types.ModuleType, name: str):
    return ledger._source_module_direct_binding_route(
        root,
        module.__name__,
        name,
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        visited=frozenset(),
    )


def _with_captured_builtins(function: types.FunctionType, changed: dict[str, object]):
    namespace = function.__globals__
    original = namespace["__builtins__"]
    try:
        namespace["__builtins__"] = {**vars(builtins), **changed}
        clone = types.FunctionType(
            function.__code__,
            namespace,
            function.__name__,
            function.__defaults__,
            function.__closure__,
        )
    finally:
        namespace["__builtins__"] = original
    clone.__module__ = function.__module__
    clone.__qualname__ = function.__qualname__
    clone.__kwdefaults__ = function.__kwdefaults__
    clone.__dict__.update(function.__dict__)
    return clone


def test_actual_core_export_contextmanager_has_verified_source_route() -> None:
    """The real Core resource owner is selected without invoking an export effect."""
    from polisyos.core.artifacts import _export_admission as provider

    assert _route(ledger._loaded_policy_engine_root(), provider, "_export_target_admission") == (
        "symbol",
        provider.__name__,
        "_export_target_admission",
    )


def test_actual_core_fieldless_canon_dataclass_retains_source_owned_base() -> None:
    from polisyos.core.canon import canon_json

    assert canon_json.to_canonical_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    assert _route(ledger._loaded_policy_engine_root(), canon_json, "CanonSpec") == (
        "symbol",
        canon_json.__name__,
        "CanonSpec",
    )


def test_actual_optional_observability_import_keeps_unresolved_initializer_plane() -> None:
    from polisyos.core import observability

    root = ledger._loaded_policy_engine_root()
    assert observability.get_metrics.__module__ == "polisyos.core.observability.metrics_parts"
    expected = ("symbol", observability.get_metrics.__module__, "get_metrics")
    assert _route(root, observability, "get_metrics") == expected
    candidate = ledger._source_module_import_route_candidate(
        root,
        observability.__name__,
        "get_metrics",
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )
    assert candidate.route == expected
    assert candidate.binding_basis == "direct"
    assert candidate.package_initializer_effect_unknown is True


_OPTIONAL_PROVIDER_SOURCE = """from __future__ import annotations
SOURCE_OFFSET = 0

def selected(value=4):
    return value + SOURCE_OFFSET

def alternate(value=4):
    return value + SOURCE_OFFSET + 1
"""

_OPTIONAL_FACADE_SOURCE = """from __future__ import annotations
try:
    from polisyos.optional_provider_fixture import selected
except ModuleNotFoundError:
    def selected(value=4):
        return value + 95
"""


@pytest.fixture
def optional_import_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    provider = _load_fixture_module(
        root, monkeypatch, "polisyos.optional_provider_fixture", _OPTIONAL_PROVIDER_SOURCE
    )
    facade = _load_fixture_module(
        root, monkeypatch, "polisyos.optional_facade_fixture", _OPTIONAL_FACADE_SOURCE
    )
    return root, provider, facade


def test_optional_import_uses_actual_source_owned_provider(optional_import_case):
    root, provider, facade = optional_import_case
    assert facade.selected is provider.selected
    assert facade.selected() == 4
    assert _route(root, facade, "selected") == ("symbol", provider.__name__, "selected")


def test_optional_import_retains_real_fallback_refusal(tmp_path, monkeypatch):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    source = _OPTIONAL_FACADE_SOURCE.replace(
        "optional_provider_fixture", "missing_optional_provider"
    )
    facade = _load_fixture_module(root, monkeypatch, "polisyos.optional_fallback_fixture", source)
    assert facade.selected() == 99
    assert facade.selected.__module__ == facade.__name__
    with pytest.raises(ledger.ConfidenceLedgerError, match="unsupported direct source binding"):
        _route(root, facade, "selected")


def test_optional_import_refuses_wrong_same_shape_provider(optional_import_case, monkeypatch):
    root, provider, facade = optional_import_case
    monkeypatch.setattr(facade, "selected", provider.alternate)
    assert facade.selected() == 5
    with pytest.raises(ledger.ConfidenceLedgerError, match="unsupported direct source binding"):
        _route(root, facade, "selected")


@pytest.mark.parametrize("change", ["code", "default", "globals"])
def test_optional_import_rechecks_current_loaded_callable(
    optional_import_case, monkeypatch, change
):
    root, provider, facade = optional_import_case
    assert _route(root, facade, "selected") == ("symbol", provider.__name__, "selected")
    if change == "code":
        monkeypatch.setattr(provider.selected, "__code__", provider.alternate.__code__)
        assert facade.selected() == 5
    elif change == "default":
        monkeypatch.setattr(provider.selected, "__defaults__", (99,))
        assert facade.selected() == 99
    else:
        function = provider.selected
        clone = types.FunctionType(
            function.__code__,
            {**function.__globals__, "SOURCE_OFFSET": 95},
            function.__name__,
            function.__defaults__,
        )
        clone.__module__ = function.__module__
        clone.__qualname__ = function.__qualname__
        monkeypatch.setattr(provider, "selected", clone)
        monkeypatch.setattr(facade, "selected", clone)
        assert facade.selected() == 99
    with pytest.raises(ledger.ConfidenceLedgerError, match="unsupported direct source binding"):
        _route(root, facade, "selected")


def test_optional_import_source_removal_and_restoration(optional_import_case):
    root, provider, facade = optional_import_case
    path = Path(facade.__file__)
    assert _route(root, facade, "selected") == ("symbol", provider.__name__, "selected")
    removed = _OPTIONAL_FACADE_SOURCE.replace(
        "    from polisyos.optional_provider_fixture import selected", "    pass  # import removed"
    )
    path.write_text(removed, encoding="utf-8")
    assert facade.selected() == 4
    with pytest.raises(ledger.ConfidenceLedgerError, match="unsupported direct source binding"):
        _route(root, facade, "selected")
    path.write_text(_OPTIONAL_FACADE_SOURCE, encoding="utf-8")
    assert _route(root, facade, "selected") == ("symbol", provider.__name__, "selected")


@pytest.mark.parametrize("change", ["effect", "handler", "ambiguous"])
def test_optional_import_does_not_expand_unsupported_branch_grammar(tmp_path, monkeypatch, change):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    _load_fixture_module(
        root, monkeypatch, "polisyos.optional_provider_fixture", _OPTIONAL_PROVIDER_SOURCE
    )
    if change == "effect":
        source = _OPTIONAL_FACADE_SOURCE.replace(
            "try:\n", "observed = []\ntry:\n    observed.append('ran')\n"
        )
    elif change == "handler":
        source = _OPTIONAL_FACADE_SOURCE.replace("except ModuleNotFoundError", "except Exception")
    else:
        source = _OPTIONAL_FACADE_SOURCE.replace(
            "except ModuleNotFoundError",
            "    from polisyos.optional_provider_fixture import alternate as selected\nexcept ModuleNotFoundError",
        )
    facade = _load_fixture_module(root, monkeypatch, "polisyos.optional_effect_fixture", source)
    if change == "effect":
        assert facade.observed == ["ran"]
    with pytest.raises(ledger.ConfidenceLedgerError, match="unsupported direct source binding"):
        _route(root, facade, "selected")


@pytest.mark.parametrize("kind", ["unhashable", "hostile_hash"])
def test_optional_import_refuses_unknown_handler_without_hashing_it(tmp_path, monkeypatch, kind):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    _load_fixture_module(
        root, monkeypatch, "polisyos.optional_provider_fixture", _OPTIONAL_PROVIDER_SOURCE
    )
    handler_source = (
        "observed = []\nBad = []\n"
        if kind == "unhashable"
        else "observed = []\nclass Handler:\n    def __hash__(self):\n        observed.append('called')\n        return 1\nBad = Handler()\n"
    )
    handler = _load_fixture_module(
        root, monkeypatch, "polisyos.optional_handler_fixture", handler_source
    )
    source = (
        "from polisyos.optional_handler_fixture import Bad\n"
        + _OPTIONAL_FACADE_SOURCE.replace("from __future__ import annotations\n", "").replace(
            "except ModuleNotFoundError", "except Bad"
        )
    )
    facade = _load_fixture_module(root, monkeypatch, "polisyos.optional_unknown_handler", source)
    assert facade.selected() == 4
    with pytest.raises(ledger.ConfidenceLedgerError, match="unsupported direct source binding"):
        _route(root, facade, "selected")
    assert handler.observed == []


def test_optional_import_candidate_does_not_mix_initializer_status_snapshots(tmp_path, monkeypatch):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    _load_fixture_module(
        root, monkeypatch, "polisyos.optional_provider_fixture", _OPTIONAL_PROVIDER_SOURCE
    )
    directory = root / "src" / "polisyos" / "optional_snapshot_package"
    directory.mkdir()
    package = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.optional_snapshot_package",
        _OPTIONAL_FACADE_SOURCE,
        path=directory / "__init__.py",
    )
    initial = "from polisyos.optional_provider_fixture import selected\n"
    Path(package.__file__).write_text(initial, encoding="utf-8")
    original = ledger._source_module_direct_binding_route

    def switch_source_before_direct(*args, **kwargs):
        if args[1] == package.__name__:
            Path(package.__file__).write_text(_OPTIONAL_FACADE_SOURCE, encoding="utf-8")
        return original(*args, **kwargs)

    monkeypatch.setattr(ledger, "_source_module_direct_binding_route", switch_source_before_direct)
    with pytest.raises(ledger.ConfidenceLedgerError, match="source changed during"):
        ledger._source_module_import_route_candidate(
            root,
            package.__name__,
            "selected",
            directory_entries={},
            source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        )


_LOADER_PACKAGE_SOURCE = """from importlib import import_module
from .child import VALUE
MARKER = object()

def __getattr__(name):
    if name in {"Remote"}:
        remote = import_module(".remote", __name__)
        return getattr(remote, name)
    raise AttributeError(name)
"""


@pytest.fixture
def loader_child_case(tmp_path, monkeypatch):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    directory = root / "src" / "polisyos" / "natural_child_fixture"
    directory.mkdir()
    (directory / "child.py").write_text("VALUE = 4\n", encoding="utf-8")
    (directory / "remote.py").write_text("class Remote:\n    pass\nchild = 99\n", encoding="utf-8")
    name = "polisyos.natural_child_fixture"
    child_name = name + ".child"
    previous_child = sys.modules.pop(child_name, None)
    package = _load_fixture_module(
        root, monkeypatch, name, _LOADER_PACKAGE_SOURCE, path=directory / "__init__.py"
    )
    child = sys.modules[child_name]
    try:
        yield root, package, child
    finally:
        if previous_child is None:
            sys.modules.pop(child_name, None)
        else:
            sys.modules[child_name] = previous_child


def _candidate(root, module, name):
    return ledger._source_module_import_route_candidate(
        root,
        module.__name__,
        name,
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )


def test_loader_published_child_is_not_a_missing_lazy_export(loader_child_case):
    root, package, child = loader_child_case
    candidate = _candidate(root, package, "child")
    assert package.child is child
    assert child.VALUE == package.VALUE == 4
    assert candidate.route == ("module", child.__name__, None)
    assert candidate.binding_basis == "loader_child"
    assert candidate.package_initializer_effect_unknown is True
    assert _candidate(root, package, "Remote").binding_basis == "literal_getattr"


def test_loader_published_child_reaches_actual_module_consumer(loader_child_case, monkeypatch):
    root, package, child = loader_child_case
    consumer = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.loader_child_consumer",
        f"from {package.__name__} import child\nRESULT = child.VALUE\n",
    )
    assert consumer.child is child
    assert consumer.child.VALUE == 4
    assert consumer.RESULT == 4
    closure = tuple(
        (module.__name__, Path(module.__file__).relative_to(root).as_posix())
        for module in (package, child, consumer)
    )
    projection, supplemental = ledger._source_facade_runtime_projection(root, closure)
    assert projection
    assert all(name.startswith("polisyos.") for name, _relative in supplemental)


def test_loader_child_candidate_does_not_authorize_coherent_wrong_literal(
    loader_child_case, monkeypatch
):
    root, package, child = loader_child_case
    fake = types.ModuleType(child.__name__)
    fake.__file__, fake.__spec__, fake.__loader__ = child.__file__, child.__spec__, child.__loader__
    fake.__package__ = child.__package__
    fake.VALUE = 99
    monkeypatch.setattr(package, "child", fake)
    monkeypatch.setattr(package, "VALUE", 99)
    sys.modules[child.__name__] = fake
    try:
        # This metadata names a source candidate; it proves neither execution
        # history nor agreement of the consumer's actual scalar read.
        assert _candidate(root, package, "child").binding_basis == "loader_child"
        consumer = _load_fixture_module(
            root,
            monkeypatch,
            "polisyos.loader_forged_consumer",
            f"from {package.__name__} import child\nRESULT = child.VALUE\n",
        )
        assert consumer.RESULT == package.VALUE == fake.VALUE == 99
        assert Path(fake.__file__).read_text(encoding="utf-8") == "VALUE = 4\n"
        closure = tuple(
            (module.__name__, Path(module.__file__).relative_to(root).as_posix())
            for module in (package, fake, consumer)
        )
        with pytest.raises(
            ledger.ConfidenceLedgerError, match="selected source literal binding differs"
        ):
            ledger._source_facade_runtime_projection(root, closure)
    finally:
        sys.modules[child.__name__] = child


def test_loader_child_declaration_cannot_come_from_unreachable_branch(loader_child_case):
    root, package, child = loader_child_case
    source = _LOADER_PACKAGE_SOURCE.replace(
        "from .child import VALUE", "if False:\n    from .child import VALUE"
    )
    Path(package.__file__).write_text(source, encoding="utf-8")
    assert package.child is child
    with pytest.raises(ledger.ConfidenceLedgerError):
        _candidate(root, package, "child")


@pytest.mark.parametrize("shape", ["flat", "nested"])
def test_loader_child_long_immutable_literal_is_checked_without_folding_budget_escape(
    loader_child_case, monkeypatch, shape
):
    root, package, child = loader_child_case
    expected = tuple(range(100)) if shape == "flat" else (tuple(range(50)), tuple(range(50, 100)))
    path = Path(child.__file__)
    source = f"VALUE = {expected!r}\n"
    path.write_text(source, encoding="utf-8")
    assert len(tuple(ast.walk(ast.parse(source).body[0].value))) > 80
    child.__spec__.loader.exec_module(child)
    package.__spec__.loader.exec_module(package)
    consumer_source = f"from {package.__name__} import child\nRESULT = child.VALUE\n"
    consumer = _load_fixture_module(
        root, monkeypatch, "polisyos.loader_long_consumer", consumer_source
    )
    assert expected == consumer.RESULT
    closure = tuple(
        (module.__name__, Path(module.__file__).relative_to(root).as_posix())
        for module in (package, child, consumer)
    )
    assert ledger._source_facade_runtime_projection(root, closure)[0]
    fake = types.ModuleType(child.__name__)
    fake.__dict__.update(vars(child))
    fake.VALUE = (
        (*expected[:-1], 999) if shape == "flat" else (expected[0], (*expected[1][:-1], 999))
    )
    monkeypatch.setattr(package, "child", fake)
    monkeypatch.setattr(package, "VALUE", fake.VALUE)
    sys.modules[child.__name__] = fake
    try:
        assert _candidate(root, package, "child").binding_basis == "loader_child"
        forged_consumer = _load_fixture_module(
            root, monkeypatch, "polisyos.loader_long_consumer", consumer_source
        )
        assert forged_consumer.RESULT == fake.VALUE != expected
        with pytest.raises(
            ledger.ConfidenceLedgerError, match="selected source literal binding differs"
        ):
            ledger._source_facade_runtime_projection(root, closure)
    finally:
        sys.modules[child.__name__] = child


def test_loader_published_child_refuses_foreign_cached_module(loader_child_case, monkeypatch):
    root, package, child = loader_child_case
    foreign = types.ModuleType(child.__name__)
    foreign.VALUE = 99
    monkeypatch.setattr(package, "child", foreign)
    assert package.child.VALUE == 99
    with pytest.raises(ledger.ConfidenceLedgerError):
        _candidate(root, package, "child")


def test_loader_published_child_refuses_forged_origin(loader_child_case, monkeypatch):
    root, package, child = loader_child_case
    monkeypatch.setattr(child.__spec__, "origin", package.__file__)
    with pytest.raises(ledger.ConfidenceLedgerError):
        _candidate(root, package, "child")


def test_loader_published_child_requires_current_source_import(loader_child_case):
    root, package, child = loader_child_case
    path = Path(package.__file__)
    path.write_text(
        _LOADER_PACKAGE_SOURCE.replace("from .child import VALUE", "VALUE = 4"), encoding="utf-8"
    )
    assert package.child is child
    with pytest.raises(ledger.ConfidenceLedgerError):
        _candidate(root, package, "child")
    path.write_text(_LOADER_PACKAGE_SOURCE, encoding="utf-8")
    assert _candidate(root, package, "child").binding_basis == "loader_child"


def test_loader_published_child_does_not_override_competing_lazy_source(loader_child_case):
    root, package, _child = loader_child_case
    changed = _LOADER_PACKAGE_SOURCE.replace('{"Remote"}', '{"Remote", "child"}')
    Path(package.__file__).write_text(changed, encoding="utf-8")
    candidate = _candidate(root, package, "child")
    assert candidate.binding_basis == "literal_getattr"
    assert candidate.route == ("symbol", package.__name__ + ".remote", "child")


_DATACLASS_BASE_SOURCE = """from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class First:
    value: int = 4

@dataclass(frozen=True)
class Second:
    value: int = 99
"""

_DATACLASS_CHILD_SOURCE = '''from __future__ import annotations
from dataclasses import dataclass
from polisyos.dataclass_base_fixture import First as Base

@dataclass(frozen=True)
class Child(Base):
    """A fieldless source-owned extension."""
'''


@pytest.fixture
def inherited_dataclass_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    base = _load_fixture_module(
        root, monkeypatch, "polisyos.dataclass_base_fixture", _DATACLASS_BASE_SOURCE
    )
    child = _load_fixture_module(
        root, monkeypatch, "polisyos.dataclass_child_fixture", _DATACLASS_CHILD_SOURCE
    )
    return root, base, child


def test_generic_fieldless_dataclass_uses_verified_inherited_fields(inherited_dataclass_case):
    root, base, child = inherited_dataclass_case
    assert child.Child().value == base.First().value == 4
    assert child.Child.__bases__ == (base.First,)
    assert _route(root, child, "Child") == ("symbol", child.__name__, "Child")


def test_fieldless_dataclass_proofs_are_linear_per_source_level(
    inherited_dataclass_case, monkeypatch: pytest.MonkeyPatch
):
    root, base, _child = inherited_dataclass_case
    previous_module, previous_name = base.__name__, "First"
    for level in range(8):
        name = f"polisyos.dataclass_level_{level}"
        source = _DATACLASS_CHILD_SOURCE.replace(
            "from polisyos.dataclass_base_fixture import First as Base",
            f"from {previous_module} import {previous_name} as Base",
        )
        child = _load_fixture_module(root, monkeypatch, name, source)
        previous_module, previous_name = name, "Child"
    original = ledger._source_python_dataclass_binding_supported
    calls = []

    def counted(*args, **kwargs):
        calls.append((args[1], args[2]))
        return original(*args, **kwargs)

    monkeypatch.setattr(ledger, "_source_python_dataclass_binding_supported", counted)
    assert child.Child().value == 4
    assert child.Child.__mro__[-2] is base.First
    assert _route(root, child, "Child") == ("symbol", child.__name__, "Child")
    assert len(calls) == len(set(calls)) == 9
    assert calls[-1] == (base.__name__, "First")


def test_fieldless_dataclass_follows_relative_package_reexport(
    inherited_dataclass_case, monkeypatch
):
    root, base, _child = inherited_dataclass_case
    directory = root / "src" / "polisyos" / "dataclass_reexport_pkg"
    directory.mkdir()
    _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.dataclass_reexport_pkg",
        "from ..dataclass_base_fixture import First as Base\n",
        path=directory / "__init__.py",
    )
    source = _DATACLASS_CHILD_SOURCE.replace(
        "from polisyos.dataclass_base_fixture import First as Base",
        "from polisyos.dataclass_reexport_pkg import Base",
    )
    child = _load_fixture_module(root, monkeypatch, "polisyos.dataclass_relative_child", source)
    assert child.Child.__bases__ == (base.First,)
    assert child.Child().value == 4
    assert _route(root, child, "Child") == ("symbol", child.__name__, "Child")


def test_fieldless_dataclass_rechecks_reexport_symlink_target(
    inherited_dataclass_case, monkeypatch
):
    root, base, _child = inherited_dataclass_case
    directory = root / "src" / "polisyos"
    source = "from .dataclass_base_fixture import First as Base\n"
    first, second = directory / "reexport_one.py", directory / "reexport_two.py"
    first.write_text(source, encoding="utf-8")
    second.write_text(source, encoding="utf-8")
    link = directory / "dataclass_reexport_link.py"
    link.symlink_to(first)
    name = "polisyos.dataclass_reexport_link"
    spec = importlib.util.spec_from_file_location(name, link)
    assert spec is not None and spec.loader is not None
    facade = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, facade)
    spec.loader.exec_module(facade)
    child_source = _DATACLASS_CHILD_SOURCE.replace(
        "from polisyos.dataclass_base_fixture import First as Base",
        "from polisyos.dataclass_reexport_link import Base",
    )
    child = _load_fixture_module(
        root, monkeypatch, "polisyos.dataclass_symlink_child", child_source
    )
    original = ledger._source_python_dataclass_binding_supported_body

    def retarget_after_hop_snapshot(*args, **kwargs):
        if args[1] == base.__name__ and args[2] == "First":
            link.unlink()
            link.symlink_to(second)
        return original(*args, **kwargs)

    monkeypatch.setattr(
        ledger, "_source_python_dataclass_binding_supported_body", retarget_after_hop_snapshot
    )
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, child, "Child")


def test_fieldless_dataclass_rechecks_base_source_at_operation_closeout(
    inherited_dataclass_case, monkeypatch: pytest.MonkeyPatch
):
    root, base, child = inherited_dataclass_case
    original = ledger._source_python_dataclass_binding_supported_body

    def change_base_after_snapshot(*args, **kwargs):
        if args[1] == base.__name__ and args[2] == "First":
            path = Path(base.__file__)
            original_source = path.read_text(encoding="utf-8")
            changed = original_source.replace("value: int = 4", "value: int = 99")
            assert changed != original_source
            path.write_text(changed, encoding="utf-8")
        return original(*args, **kwargs)

    monkeypatch.setattr(
        ledger, "_source_python_dataclass_binding_supported_body", change_base_after_snapshot
    )
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, child, "Child")


def test_fieldless_dataclass_route_retains_initial_child_source_snapshot(
    inherited_dataclass_case, monkeypatch: pytest.MonkeyPatch
):
    root, _base, child = inherited_dataclass_case
    original = ledger._source_python_dataclass_binding_supported

    def change_child_after_route_parse(*args, **kwargs):
        if args[1] == child.__name__:
            Path(child.__file__).write_text(
                _DATACLASS_CHILD_SOURCE + "\n# changed snapshot\n", encoding="utf-8"
            )
        return original(*args, **kwargs)

    monkeypatch.setattr(
        ledger, "_source_python_dataclass_binding_supported", change_child_after_route_parse
    )
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, child, "Child")


def test_fieldless_dataclass_rejects_coherently_rebound_valid_foreign_base(
    inherited_dataclass_case, monkeypatch: pytest.MonkeyPatch
):
    root, base, child = inherited_dataclass_case
    monkeypatch.setattr(base, "First", base.Second)
    exec(  # noqa: S102 - execute the exact controlled child fixture under its wrong live import
        compile(_DATACLASS_CHILD_SOURCE, child.__file__, "exec"), vars(child)
    )
    assert child.Child.__bases__ == (base.Second,)
    assert child.Child().value == 99

    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, child, "Child")


def test_fieldless_dataclass_rejects_inherited_hook_before_replay(
    inherited_dataclass_case, monkeypatch: pytest.MonkeyPatch
):
    root, base, child = inherited_dataclass_case
    calls = []

    def hook(cls):
        calls.append(cls.__name__)

    monkeypatch.setattr(base.First, "__init_subclass__", classmethod(hook), raising=False)
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, child, "Child")
    assert calls == []


def test_fieldless_dataclass_rejects_changed_generated_constructor(
    inherited_dataclass_case, monkeypatch: pytest.MonkeyPatch
):
    root, _base, child = inherited_dataclass_case
    assert _route(root, child, "Child") == ("symbol", child.__name__, "Child")
    monkeypatch.setattr(child.Child.__init__, "__defaults__", (99,))
    assert child.Child().value == 99
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, child, "Child")


def test_fieldless_dataclass_does_not_promote_undecorated_base_name_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from dataclasses import dataclass

    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    base_source = "from __future__ import annotations\nclass First:\n    value: int = 4\n"
    base = _load_fixture_module(root, monkeypatch, "polisyos.dataclass_base_fixture", base_source)
    base.First.value = 99
    base.First = dataclass(frozen=True)(base.First)
    child = _load_fixture_module(
        root, monkeypatch, "polisyos.dataclass_child_fixture", _DATACLASS_CHILD_SOURCE
    )
    assert _route(root, base, "First") == ("symbol", base.__name__, "First")
    assert child.Child().value == 99
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, child, "Child")


@pytest.mark.parametrize(
    "body",
    ["    extra: int = 7\n", "    def own(self):\n        return 7\n"],
)
def test_fieldless_dataclass_does_not_admit_broader_inheritance_grammar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str
):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    _load_fixture_module(
        root, monkeypatch, "polisyos.dataclass_base_fixture", _DATACLASS_BASE_SOURCE
    )
    child_source = _DATACLASS_CHILD_SOURCE.replace(
        '    """A fieldless source-owned extension."""\n', body
    )
    child = _load_fixture_module(
        root, monkeypatch, "polisyos.dataclass_child_fixture", child_source
    )
    assert child.Child().value == 4
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, child, "Child")


@pytest.mark.parametrize("name", ["scoped", "other_scope", "local"])
def test_supported_decorator_routes_use_real_source_owned_callables(decorated_case, name: str):
    """Stdlib wrappers and the existing local-decorator proof retain real behavior."""
    root, module = decorated_case
    with module.scoped() as value:
        assert value == 4
    with module.other_scope() as value:
        assert value == 11
    assert module.cached() == 6
    assert module.local() == 7

    assert _route(root, module, name) == ("symbol", module.__name__, name)


def test_contextmanager_route_refuses_changed_terminal_code(decorated_case) -> None:
    root, module = decorated_case
    assert _route(root, module, "scoped") == ("symbol", module.__name__, "scoped")
    module.scoped.__wrapped__.__code__ = module.other_scope.__wrapped__.__code__
    with module.scoped() as value:
        assert value == 11

    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "scoped")


def test_contextmanager_route_refuses_changed_terminal_default(decorated_case) -> None:
    root, module = decorated_case
    assert _route(root, module, "scoped") == ("symbol", module.__name__, "scoped")
    module.scoped.__wrapped__.__defaults__ = (99,)
    with module.scoped() as value:
        assert value == 99

    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "scoped")


def test_contextmanager_route_refuses_changed_wrapper_closure(decorated_case) -> None:
    root, module = decorated_case
    assert _route(root, module, "scoped") == ("symbol", module.__name__, "scoped")
    assert len(module.scoped.__closure__) == 1
    module.scoped.__closure__[0].cell_contents = module.other_scope.__wrapped__
    with module.scoped() as value:
        assert value == 11

    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "scoped")


def test_contextmanager_route_refuses_same_code_terminal_with_foreign_globals(decorated_case):
    root, module = decorated_case
    with module.global_scope() as value:
        assert value == 4
    assert _route(root, module, "global_scope") == ("symbol", module.__name__, "global_scope")
    terminal = module.global_scope.__wrapped__
    clone = types.FunctionType(
        terminal.__code__,
        {**terminal.__globals__, "SOURCE_VALUE": 99},
        terminal.__name__,
        terminal.__defaults__,
        terminal.__closure__,
    )
    clone.__qualname__ = terminal.__qualname__
    clone.__module__ = terminal.__module__
    module.global_scope.__closure__[0].cell_contents = clone
    with module.global_scope() as value:
        assert value == 99

    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "global_scope")


def test_contextmanager_route_refuses_same_code_wrapper_with_foreign_globals(decorated_case):
    root, module = decorated_case
    wrapper = module.global_scope
    clone = types.FunctionType(
        wrapper.__code__,
        {**wrapper.__globals__, "_GeneratorContextManager": lambda *_args: nullcontext(99)},
        wrapper.__name__,
        wrapper.__defaults__,
        wrapper.__closure__,
    )
    functools.update_wrapper(clone, wrapper.__wrapped__)
    module.global_scope = clone
    with module.global_scope() as value:
        assert value == 99

    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "global_scope")


def test_contextmanager_route_refuses_rebound_provider_dispatch(
    decorated_case, monkeypatch: pytest.MonkeyPatch
):
    import contextlib

    root, module = decorated_case
    with monkeypatch.context() as changes:
        changes.setattr(contextlib, "_GeneratorContextManager", lambda *_args: nullcontext(99))
        with module.global_scope() as value:
            assert value == 99

        with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
            _route(root, module, "global_scope")


def test_contextmanager_route_refuses_mutated_provider_factory(
    decorated_case, monkeypatch: pytest.MonkeyPatch
):
    import contextlib

    root, module = decorated_case
    terminal = module.global_scope.__wrapped__

    def replacement(func):
        @wraps(func)
        def helper(*args, **kwargs):
            return nullcontext(99)

        return helper

    with monkeypatch.context() as changes:
        changes.setattr(contextlib.contextmanager, "__code__", replacement.__code__)
        module.global_scope = contextlib.contextmanager(terminal)
        with module.global_scope() as value:
            assert value == 99

        with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
            _route(root, module, "global_scope")


def test_contextmanager_route_refuses_mutated_dispatch_method(
    decorated_case, monkeypatch: pytest.MonkeyPatch
):
    import contextlib

    root, module = decorated_case

    def changed_enter(self):
        next(self.gen)
        return 99

    with monkeypatch.context() as changes:
        changes.setattr(contextlib._GeneratorContextManager, "__enter__", changed_enter)
        with module.global_scope() as value:
            assert value == 99

        with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
            _route(root, module, "global_scope")


def test_contextmanager_route_refuses_changed_context_decorator_wraps(
    decorated_case, monkeypatch: pytest.MonkeyPatch
):
    import contextlib

    root, module = decorated_case

    @module.global_scope()
    def original():
        return 7

    assert original() == 7

    def changed_wraps(_target):
        return lambda _wrapped: lambda: 99

    with monkeypatch.context() as changes:
        changes.setattr(contextlib, "wraps", changed_wraps)

        @module.global_scope()
        def changed():
            return 7

        assert changed() == 99
        with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
            _route(root, module, "global_scope")


def test_contextmanager_route_refuses_coherently_rebound_python_partial(
    decorated_case, monkeypatch: pytest.MonkeyPatch
):
    import _functools

    root, module = decorated_case

    def fake_partial(_cls, *_args, **_kwargs):
        return lambda _wrapped: lambda: 99

    forged = type("partial", (), {"__module__": "functools", "__new__": fake_partial})
    with monkeypatch.context() as changes:
        changes.setattr(functools, "partial", forged)
        changes.setattr(_functools, "partial", forged)

        @module.global_scope()
        def changed():
            return 7

        assert changed() == 99
        with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
            _route(root, module, "global_scope")


def test_contextmanager_route_refuses_terminal_captured_builtins(decorated_case):
    root, module = decorated_case
    assert _route(root, module, "builtin_scope") == ("symbol", module.__name__, "builtin_scope")
    clone = _with_captured_builtins(module.builtin_scope.__wrapped__, {"next": lambda _gen: 99})
    module.builtin_scope.__wrapped__ = clone
    module.builtin_scope.__closure__[0].cell_contents = clone
    with module.builtin_scope() as value:
        assert value == 99

    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "builtin_scope")


def test_contextmanager_route_refuses_dispatch_method_captured_builtins(
    decorated_case, monkeypatch: pytest.MonkeyPatch
):
    import contextlib

    root, module = decorated_case

    def changed_next(generator):
        next(generator)
        return 99

    clone = _with_captured_builtins(
        contextlib._GeneratorContextManager.__enter__, {"next": changed_next}
    )
    with monkeypatch.context() as changes:
        changes.setattr(contextlib._GeneratorContextManager, "__enter__", clone)
        with module.global_scope() as value:
            assert value == 99

        with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
            _route(root, module, "global_scope")


def test_contextmanager_route_refuses_metadata_function_captured_builtins(
    decorated_case, monkeypatch: pytest.MonkeyPatch
):
    root, module = decorated_case

    def changed_getattr(obj, name, *args):
        if name == "__doc__":
            return "forged documentation"
        return getattr(obj, name, *args)

    clone = _with_captured_builtins(functools.update_wrapper, {"getattr": changed_getattr})
    with monkeypatch.context() as changes:
        changes.setattr(functools, "update_wrapper", clone)

        @module.global_scope()
        def changed():
            """Source documentation."""
            return 7

        assert changed.__doc__ == "forged documentation"
        with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
            _route(root, module, "global_scope")


@pytest.mark.parametrize("attribute", ["__module__", "__qualname__"])
def test_contextmanager_route_preserves_wrapper_identity_checks(
    decorated_case, monkeypatch: pytest.MonkeyPatch, attribute: str
):
    root, module = decorated_case
    assert _route(root, module, "global_scope") == ("symbol", module.__name__, "global_scope")
    monkeypatch.setattr(module.global_scope, attribute, "forged")
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "global_scope")


def test_contextmanager_route_refuses_unestablished_generic_terminal_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = _SOURCE + "\n@contextmanager\ndef generic_scope[T]():\n    yield T\n"
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    terminal = module.generic_scope.__wrapped__
    assert terminal.__closure__ is not None
    with module.generic_scope() as value:
        assert value is terminal.__type_params__[0]
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "generic_scope")
    terminal.__closure__[0].cell_contents = 99
    with module.generic_scope() as value:
        assert value == 99
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "generic_scope")


@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        ("def local_decorator(offset=1):\n", "def local_decorator(offset=1):\n    offset = 50\n"),
        ("    return decorate\n", "    offset = 50\n    return decorate\n"),
        ("        return wrapped\n", "        offset = 50\n        return wrapped\n"),
    ],
)
def test_local_factory_effect_is_not_ignored_when_binding_wrapper_cells(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    original: str,
    replacement: str,
):
    root, module = _load_decorated_case(
        tmp_path, monkeypatch, _SOURCE.replace(original, replacement)
    )
    assert module.local() == 56
    for name, cell in zip(module.local.__code__.co_freevars, module.local.__closure__, strict=True):
        if name == "offset":
            cell.cell_contents = 1
            break
    else:
        pytest.fail("real local decorator lacks the source offset closure")
    assert module.local() == 7

    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "local")


def test_decorated_route_never_mixes_source_snapshots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    alternate = _SOURCE.replace("@contextmanager\ndef global_scope", "@deepcopy\ndef global_scope")
    assert alternate != _SOURCE
    root, module = _load_decorated_case(tmp_path, monkeypatch, alternate)
    path = Path(module.__file__)
    path.write_text(_SOURCE, encoding="utf-8")
    original = ledger._source_decorated_callable_binding_supported

    def switch_to_loaded_source(*args, **kwargs):
        path.write_text(alternate, encoding="utf-8")
        return original(*args, **kwargs)

    monkeypatch.setattr(
        ledger, "_source_decorated_callable_binding_supported", switch_to_loaded_source
    )
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "global_scope")


@pytest.mark.parametrize(("maxsize", "typed"), [(1, True), (2, False)])
def test_lru_route_refuses_changed_cache_policy(decorated_case, maxsize: int, typed: bool):
    root, module = decorated_case
    module.cached = functools.lru_cache(maxsize=maxsize, typed=typed)(module.cached.__wrapped__)
    assert module.cached() == 6

    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "cached")


def test_lru_route_retains_unestablished_typed_policy_even_for_normal_wrapper(decorated_case):
    root, module = decorated_case
    assert module.cached() == 6

    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "cached")


def test_lru_route_refuses_spoofed_policy_accessor(decorated_case):
    root, module = decorated_case
    module.cached = functools.lru_cache(maxsize=1, typed=False)(module.cached.__wrapped__)
    module.cached.cache_parameters = lambda: {"maxsize": 2, "typed": True}
    assert type(module.cached).cache_info(module.cached).maxsize == 1
    assert module.cached.cache_parameters() == {"maxsize": 2, "typed": True}

    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "cached")


def test_unknown_identity_decorator_is_not_admitted_by_plain_function_shape(decorated_case):
    root, module = decorated_case
    assert isinstance(module.unsupported_identity, types.FunctionType)
    assert module.unsupported_identity() == 9

    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "unsupported_identity")


def _frozen_source(expression: str) -> str:
    return (
        "from __future__ import annotations\n"
        f"VALUES = {expression}\n"
        "def read_values():\n    return VALUES\n"
        f"def construct_values():\n    return {expression}\n"
    )


def _source_constant_value(root, module, name="VALUES"):
    tree = ast.parse(Path(module.__file__).read_bytes(), filename=module.__file__)
    return ledger._source_dataclass_named_constant(
        name, repo_root=root, tree=tree, module=module, module_name=module.__name__
    )


def test_actual_core_frozenset_source_route_and_value_are_reconciled():
    from polisyos.core.canon import canon_json

    root = ledger._loaded_policy_engine_root()
    expected = frozenset(
        {"array_digest", "bytes", "bytes_hex", "date", "datetime", "decimal", "float", "float_hex"}
    )
    assert _source_constant_value(root, canon_json, "_CANONICAL_TYPES") == expected
    assert _route(root, canon_json, "_CANONICAL_TYPES") == (
        "symbol",
        canon_json.__name__,
        "_CANONICAL_TYPES",
    )
    assert canon_json.to_canonical_bytes({"field": 4}) == b'{"field":4}'


@pytest.mark.parametrize(
    "expression", ["frozenset({'alpha', 'beta'})", "frozenset(('alpha', 'beta'))", "frozenset()"]
)
def test_frozenset_literal_constructor_uses_existing_value_owner(tmp_path, monkeypatch, expression):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _frozen_source(expression))
    expected = frozenset() if expression == "frozenset()" else frozenset({"alpha", "beta"})
    assert expected == module.read_values() == module.construct_values()
    assert _source_constant_value(root, module) == expected
    assert _route(root, module, "VALUES") == ("symbol", module.__name__, "VALUES")


def test_frozenset_constructor_alias_requires_actual_builtin(tmp_path, monkeypatch):
    source = _frozen_source("freeze({'alpha', 'beta'})").replace(
        "from __future__ import annotations\n",
        "from __future__ import annotations\nfrom builtins import frozenset as freeze\n",
    )
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    assert _source_constant_value(root, module) == frozenset({"alpha", "beta"})
    assert _route(root, module, "VALUES") == ("symbol", module.__name__, "VALUES")


@pytest.mark.parametrize("binding", ["module", "builtins"])
def test_frozenset_constructor_refuses_shadow_without_calling_it(tmp_path, monkeypatch, binding):
    root, module = _load_decorated_case(
        tmp_path, monkeypatch, _frozen_source("frozenset({'alpha'})")
    )
    observed = []

    def forbidden(_members):
        observed.append("called")
        return frozenset({"forged"})

    if binding == "module":
        monkeypatch.setattr(module, "frozenset", forbidden, raising=False)
    else:
        monkeypatch.setattr(module, "__builtins__", {**vars(builtins), "frozenset": forbidden})
    assert _source_constant_value(root, module) is ledger._SOURCE_DERIVATION_FAILED
    with pytest.raises(
        ledger.ConfidenceLedgerError, match="side-effecting direct source assignment"
    ):
        _route(root, module, "VALUES")
    assert observed == []


@pytest.mark.parametrize("expression", ["frozenset({'alpha', 'beta'})", "frozenset({1})"])
def test_frozenset_live_members_are_typed_and_source_bound(tmp_path, monkeypatch, expression):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _frozen_source(expression))
    assert _source_constant_value(root, module) is not ledger._SOURCE_DERIVATION_FAILED
    wrong = frozenset({"alpha", "forged"}) if "alpha" in expression else frozenset({True})
    if "alpha" not in expression:
        assert wrong == module.VALUES
        assert type(next(iter(wrong))) is bool
        assert type(next(iter(module.VALUES))) is int
    monkeypatch.setattr(module, "VALUES", wrong)
    assert module.read_values() is wrong
    assert _source_constant_value(root, module) is ledger._SOURCE_DERIVATION_FAILED
    consumer = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.frozen_consumer",
        f"from {module.__name__} import VALUES\nRESULT = VALUES\n",
    )
    assert consumer.RESULT is wrong
    closure = tuple(
        (owner.__name__, Path(owner.__file__).relative_to(root).as_posix())
        for owner in (module, consumer)
    )
    with pytest.raises(
        ledger.ConfidenceLedgerError, match="selected source literal binding differs"
    ):
        ledger._source_facade_runtime_projection(root, closure)


@pytest.mark.parametrize(
    "expression",
    ["frozenset(['alpha'])", "frozenset(TOKEN)", "frozenset((read_values(),))", "set({'alpha'})"],
)
def test_frozenset_literal_profile_refuses_mutable_dynamic_and_call_arguments(
    tmp_path, monkeypatch, expression
):
    source = _frozen_source("frozenset({'alpha'})")
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    observed = []
    monkeypatch.setattr(module, "TOKEN", ("alpha",), raising=False)
    monkeypatch.setattr(module, "read_values", lambda: observed.append("called"))
    changed = source.replace("VALUES = frozenset({'alpha'})", f"VALUES = {expression}")
    Path(module.__file__).write_text(changed, encoding="utf-8")
    assert _source_constant_value(root, module) is ledger._SOURCE_DERIVATION_FAILED
    with pytest.raises(
        ledger.ConfidenceLedgerError, match="side-effecting direct source assignment"
    ):
        _route(root, module, "VALUES")
    assert observed == []


def test_frozenset_constructor_refusal_does_not_hash_unknown_callable(tmp_path, monkeypatch):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    provider = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.frozen_constructor_provider",
        "from builtins import frozenset as Ctor\n",
    )
    source = _frozen_source("Ctor({'alpha'})").replace(
        "from __future__ import annotations\n",
        "from __future__ import annotations\nfrom polisyos.frozen_constructor_provider import Ctor\n",
    )
    module = _load_fixture_module(root, monkeypatch, "polisyos.frozen_hash_control", source)
    observed = []

    class UnverifiedConstructor:
        def __hash__(self):
            observed.append("hash")
            return 1

        def __call__(self, _members):
            observed.append("call")
            return frozenset({"forged"})

    unverified = UnverifiedConstructor()
    monkeypatch.setattr(provider, "Ctor", unverified)
    monkeypatch.setattr(module, "Ctor", unverified)
    tree = ast.parse(source, filename=module.__file__)
    expression = next(item.value for item in tree.body if isinstance(item, ast.Assign))
    assert (
        ledger._source_dataclass_value(
            expression, tree=tree, module=module, module_name=module.__name__, repo_root=root
        )
        is ledger._SOURCE_DERIVATION_FAILED
    )
    assert _source_constant_value(root, module) is ledger._SOURCE_DERIVATION_FAILED
    assert observed == []


def test_frozenset_constructor_cannot_hide_captured_builtin_namespace(tmp_path, monkeypatch):
    _root, module = _load_decorated_case(
        tmp_path, monkeypatch, _frozen_source("frozenset({'alpha'})")
    )
    assert module.construct_values() == frozenset({"alpha"})
    clone = _with_captured_builtins(
        module.construct_values, {"frozenset": lambda _values: frozenset({"forged"})}
    )
    monkeypatch.setattr(module, "construct_values", clone)
    assert module.construct_values() == frozenset({"forged"})
    path = Path(module.__file__).resolve()
    compiled = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    hashes = ledger._loader_code_hashes_by_qualname(compiled)
    slot = next(
        item
        for item in ledger._loader_owned_callable_slots(path)
        if item.binding_name == "construct_values"
    )
    _row, matches = ledger._loader_owned_slot_binding(
        module, module.__name__, path, slot, hashes[slot.qualname], hashes
    )
    assert matches is False


def test_frozenset_member_proof_does_not_invoke_unknown_object_protocols(tmp_path, monkeypatch):
    root, module = _load_decorated_case(
        tmp_path, monkeypatch, _frozen_source("frozenset({'alpha'})")
    )
    observed = []

    class UnverifiedMember:
        def __hash__(self):
            observed.append("hash")
            return 1

        def __getattribute__(self, name):
            if name == "__dict__":
                observed.append("dictionary")
            return object.__getattribute__(self, name)

    wrong = frozenset({UnverifiedMember()})
    observed.clear()
    monkeypatch.setattr(module, "VALUES", wrong)
    assert _source_constant_value(root, module) is ledger._SOURCE_DERIVATION_FAILED
    assert observed == []


def test_frozenset_member_proof_does_not_hash_unknown_metaclass(tmp_path, monkeypatch):
    root, module = _load_decorated_case(
        tmp_path, monkeypatch, _frozen_source("frozenset({'alpha'})")
    )
    observed = []

    class UnverifiedMeta(type):
        def __hash__(cls):
            observed.append("metaclass_hash")
            return 1

    class UnverifiedMember(metaclass=UnverifiedMeta):
        pass

    monkeypatch.setattr(module, "VALUES", frozenset({UnverifiedMember()}))
    observed.clear()
    assert _source_constant_value(root, module) is ledger._SOURCE_DERIVATION_FAILED
    assert observed == []


@pytest.mark.parametrize("shape", ["nested_frozen", "shared_tuple", "large_string", "large_int"])
def test_frozenset_live_member_proof_has_one_expansion_and_scalar_budget(
    tmp_path, monkeypatch, shape
):
    root, module = _load_decorated_case(
        tmp_path, monkeypatch, _frozen_source("frozenset({'alpha'})")
    )
    if shape == "nested_frozen":
        wrong = "alpha"
        for _ in range(50):
            wrong = frozenset({wrong})
    elif shape == "shared_tuple":
        member = "alpha"
        for _ in range(13):
            member = (member, member)
        wrong = frozenset({member})
    elif shape == "large_string":
        wrong = frozenset({"x" * (1024**2)})
    else:
        wrong = frozenset({1 << (8 * 1024**2)})
    # Count expanded references rather than unique objects: normalizing this
    # compact tuple DAG before validation would expand it exponentially.
    budget = [10000, 1024**2]
    assert (
        ledger._source_immutable_member_projection(wrong, budget=budget)
        is ledger._SOURCE_DERIVATION_FAILED
    )
    assert 0 <= budget[0] <= 10000
    assert 0 <= budget[1] <= 1024**2
    monkeypatch.setattr(module, "VALUES", wrong)
    assert _source_constant_value(root, module) is ledger._SOURCE_DERIVATION_FAILED


def test_frozenset_literal_relation_preserves_nested_types_and_float_sign(tmp_path, monkeypatch):
    expression = "frozenset({('alpha', 1, True, b'bytes', -0.0, None)})"
    root, module = _load_decorated_case(tmp_path, monkeypatch, _frozen_source(expression))
    assert _source_constant_value(root, module) is not ledger._SOURCE_DERIVATION_FAILED
    monkeypatch.setattr(module, "VALUES", frozenset({("alpha", True, 1, b"bytes", 0.0, None)}))
    # Python's container equality conflates these values; the source relation
    # preserves member types and the exact finite float representation.
    assert module.construct_values() == module.VALUES
    assert _source_constant_value(root, module) is ledger._SOURCE_DERIVATION_FAILED


@pytest.mark.parametrize("shape", ["scalar_bytes", "member_occurrences"])
def test_frozenset_admitted_budget_boundary_is_verified_by_selected_consumer(
    tmp_path, monkeypatch, shape
):
    expected = frozenset({"a" * 200000}) if shape == "scalar_bytes" else frozenset(range(6000))
    expression = f"frozenset({tuple(expected)!r})"
    root, module = _load_decorated_case(tmp_path, monkeypatch, _frozen_source(expression))
    assert _source_constant_value(root, module) == expected
    consumer = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.frozen_boundary_consumer",
        f"from {module.__name__} import VALUES\nRESULT = VALUES\n",
    )
    closure = tuple(
        (owner.__name__, Path(owner.__file__).relative_to(root).as_posix())
        for owner in (module, consumer)
    )
    ledger._source_facade_runtime_projection(root, closure)
    wrong = frozenset({"b" * 200000}) if shape == "scalar_bytes" else frozenset(range(1, 6001))
    monkeypatch.setattr(module, "VALUES", wrong)
    monkeypatch.setattr(consumer, "VALUES", wrong)
    monkeypatch.setattr(consumer, "RESULT", wrong)
    assert consumer.RESULT is wrong
    with pytest.raises(
        ledger.ConfidenceLedgerError, match="selected source literal binding differs"
    ):
        ledger._source_facade_runtime_projection(root, closure)


def test_frozenset_constructor_source_is_pinned_and_removal_refuses(tmp_path, monkeypatch):
    source = _frozen_source("frozenset({'alpha'})")
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    assert _candidate(root, module, "VALUES").route == ("symbol", module.__name__, "VALUES")
    path = Path(module.__file__)
    path.write_text(
        source.replace("VALUES = frozenset({'alpha'})", "VALUES = {'alpha'}"), encoding="utf-8"
    )
    assert _source_constant_value(root, module) is ledger._SOURCE_DERIVATION_FAILED
    path.write_text(source, encoding="utf-8")
    assert _source_constant_value(root, module) == frozenset({"alpha"})
    original = ledger._source_frozenset_literal_expression

    def change_source_during_proof(*args, **kwargs):
        path.write_text(source + "\n# source changed during proof\n", encoding="utf-8")
        return original(*args, **kwargs)

    monkeypatch.setattr(ledger, "_source_frozenset_literal_expression", change_source_during_proof)
    with pytest.raises(ledger.ConfidenceLedgerError, match="source changed during"):
        _candidate(root, module, "VALUES")


def _typing_literal_source(expression="Literal['alpha']", imports="from typing import Literal"):
    return (
        f"from __future__ import annotations\n{imports}\n"
        f"CHOICE = {expression}\n"
        "def read_choice():\n    return CHOICE\n"
    )


def _typing_literal_expected(module, name="CHOICE"):
    tree = ast.parse(Path(module.__file__).read_bytes(), filename=module.__file__)
    declaration = ledger._module_scope_direct_binding_sites(tree, name)[0][1]
    return ledger._source_typing_literal_expression(
        declaration.value, tree=tree, module=module, module_name=module.__name__
    )


def _typing_literal_consumer(root, module, monkeypatch):
    consumer = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.literal_consumer",
        f"from {module.__name__} import CHOICE\nRESULT = CHOICE\n",
    )
    closure = tuple(
        (owner.__name__, Path(owner.__file__).relative_to(root).as_posix())
        for owner in (module, consumer)
    )
    return consumer, closure


@pytest.mark.parametrize(
    ("expression", "imports"),
    [
        ("Literal['alpha', 'beta']", "from typing import Literal"),
        ("Choice['alpha', 1, True, None, b'bytes', -1]", "from typing import Literal as Choice"),
        ("t.Literal['alpha', 'alpha']", "import typing as t"),
        ("Literal[True, 1]", "from typing import Literal"),
    ],
)
def test_typing_literal_source_route_and_selected_consumer_are_value_bound(
    tmp_path, monkeypatch, expression, imports
):
    root, module = _load_decorated_case(
        tmp_path, monkeypatch, _typing_literal_source(expression, imports)
    )
    expected = _typing_literal_expected(module)
    assert expected is not ledger._SOURCE_DERIVATION_FAILED
    assert ledger._source_typing_literal_value_matches(module.read_choice(), expected)
    assert _route(root, module, "CHOICE") == ("symbol", module.__name__, "CHOICE")
    _consumer, closure = _typing_literal_consumer(root, module, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    profile = ledger._typing_literal_provider_projection()
    assert profile["scope"] == "source_declaration_and_inert_origin_args_only"
    assert profile["construction_history_and_alias_execution"] == "not_established"
    assert profile["independent_transform_verification"] is False


def test_actual_hashing_literal_aliases_have_finite_source_and_value_owners():
    from polisyos.common import hashing

    root = ledger._loaded_policy_engine_root()
    for name in ("HashAlgorithm", "DeprecatedHashAlgorithm"):
        expected = _typing_literal_expected(hashing, name)
        assert expected is not ledger._SOURCE_DERIVATION_FAILED
        assert ledger._source_typing_literal_value_matches(vars(hashing)[name], expected)
        assert _route(root, hashing, name) == ("symbol", hashing.__name__, name)


@pytest.mark.parametrize(
    "mutation", ["values", "primitive_type", "origin", "unknown_args", "reversed", "duplicated"]
)
def test_typing_literal_selected_consumer_refuses_coherent_forgery(tmp_path, monkeypatch, mutation):
    expression = (
        "Literal[1]"
        if mutation == "primitive_type"
        else "Literal['alpha', 'beta']"
        if mutation in {"reversed", "duplicated"}
        else "Literal['alpha']"
    )
    root, module = _load_decorated_case(tmp_path, monkeypatch, _typing_literal_source(expression))
    consumer, closure = _typing_literal_consumer(root, module, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    observed = []

    class UnknownArgument:
        def __hash__(self):
            observed.append("hash")
            return 1

        def __eq__(self, _other):
            observed.append("equality")
            return True

    # A deliberately constructed canonical-type instance is not evidence of
    # creation history. Its inert state must still match the declaration.
    forged = object.__new__(type(module.CHOICE))
    vars(forged).update(vars(module.CHOICE))
    if mutation == "origin":
        vars(forged)["__origin__"] = typing.Union
    elif mutation == "unknown_args":
        vars(forged)["__args__"] = (UnknownArgument(),)
    elif mutation == "reversed":
        vars(forged)["__args__"] = ("beta", "alpha")
    elif mutation == "duplicated":
        vars(forged)["__args__"] = ("alpha", "beta", "alpha")
    else:
        vars(forged)["__args__"] = (True,) if mutation == "primitive_type" else ("forged",)
    monkeypatch.setattr(module, "CHOICE", forged)
    monkeypatch.setattr(consumer, "CHOICE", forged)
    monkeypatch.setattr(consumer, "RESULT", forged)
    with pytest.raises(ledger.ConfidenceLedgerError, match="typing Literal binding differs"):
        ledger._source_facade_runtime_projection(root, closure)
    assert observed == []


def test_typing_literal_fake_alias_is_refused_without_getters_or_protocols(tmp_path, monkeypatch):
    _root, module = _load_decorated_case(tmp_path, monkeypatch, _typing_literal_source())
    expected = _typing_literal_expected(module)
    observed = []

    class UnverifiedAlias:
        def __getattribute__(self, name):
            observed.append(name)
            raise AssertionError("unknown getter must not run")

        def __eq__(self, _other):
            observed.append("equality")
            return True

        def __hash__(self):
            observed.append("hash")
            return 1

    assert not ledger._source_typing_literal_value_matches(UnverifiedAlias(), expected)
    assert observed == []


@pytest.mark.parametrize(
    "expression",
    ["Literal[TOKEN]", "Literal[read_choice()]", "Literal[Literal['alpha']]", "Literal[1.0]"],
)
def test_typing_literal_profile_refuses_dynamic_nested_and_nonprimitive_source(
    tmp_path, monkeypatch, expression
):
    source = _typing_literal_source()
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    observed = []
    monkeypatch.setattr(module, "read_choice", lambda: observed.append("called"))
    monkeypatch.setattr(module, "TOKEN", "alpha", raising=False)
    Path(module.__file__).write_text(
        source.replace("CHOICE = Literal['alpha']", f"CHOICE = {expression}"), encoding="utf-8"
    )
    assert _typing_literal_expected(module) is ledger._SOURCE_DERIVATION_FAILED
    with pytest.raises(ledger.ConfidenceLedgerError, match="side-effecting direct source"):
        _route(root, module, "CHOICE")
    assert observed == []


def test_typing_literal_source_shadow_and_constructor_removal_refuse(tmp_path, monkeypatch):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _typing_literal_source())
    consumer, closure = _typing_literal_consumer(root, module, monkeypatch)
    observed = []

    class UnverifiedForm:
        def __getitem__(self, _arguments):
            observed.append("getitem")
            return module.CHOICE

    monkeypatch.setattr(module, "Literal", UnverifiedForm())
    assert _typing_literal_expected(module) is ledger._SOURCE_DERIVATION_FAILED
    with pytest.raises(ledger.ConfidenceLedgerError, match="side-effecting direct source"):
        ledger._source_facade_runtime_projection(root, closure)
    assert consumer.RESULT is module.CHOICE
    assert observed == []


def test_typing_literal_primitive_budget_boundary_remains_consumer_checked(tmp_path, monkeypatch):
    value = "a" * 200000
    root, module = _load_decorated_case(
        tmp_path, monkeypatch, _typing_literal_source(f"Literal[{value!r}]")
    )
    consumer, closure = _typing_literal_consumer(root, module, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    forged = object.__new__(type(module.CHOICE))
    vars(forged).update(vars(module.CHOICE))
    vars(forged)["__args__"] = ("b" * 200000,)
    monkeypatch.setattr(module, "CHOICE", forged)
    monkeypatch.setattr(consumer, "CHOICE", forged)
    with pytest.raises(ledger.ConfidenceLedgerError, match="typing Literal binding differs"):
        ledger._source_facade_runtime_projection(root, closure)
    assert (
        ledger._source_typing_literal_args_projection(tuple(range(81)))
        is ledger._SOURCE_DERIVATION_FAILED
    )
    assert (
        ledger._source_typing_literal_args_projection(("x" * (1024**2),))
        is ledger._SOURCE_DERIVATION_FAILED
    )


def test_typing_literal_native_name_slot_refuses_unknown_equality(tmp_path, monkeypatch):
    _root, module = _load_decorated_case(tmp_path, monkeypatch, _typing_literal_source())
    observed = []

    class UnverifiedName:
        def __eq__(self, _other):
            observed.append("equality")
            return True

    with monkeypatch.context() as changed:
        changed.setattr(typing.Literal, "_name", UnverifiedName())
        assert _typing_literal_expected(module) is ledger._SOURCE_DERIVATION_FAILED
    assert observed == []


def test_typing_literal_provider_byte_corruption_is_refused_without_execution(monkeypatch):
    path = Path(typing.__file__).resolve()
    original = Path.read_bytes
    source = original(path)
    changed = source.replace(
        b"parameters = _flatten_literal_params(parameters)", b"parameters = ()", 1
    )
    assert changed != source
    monkeypatch.setattr(
        Path, "read_bytes", lambda self: changed if self == path else original(self)
    )
    assert ledger._typing_literal_provider_state() is None


def test_typing_literal_source_snapshot_guard_catches_change_during_projection(
    tmp_path, monkeypatch
):
    source = _typing_literal_source()
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    original = ledger._typing_literal_provider_state
    path = Path(module.__file__)

    def changed_source():
        path.write_text(source + "\n# changed during Literal projection\n", encoding="utf-8")
        return original()

    monkeypatch.setattr(ledger, "_typing_literal_provider_state", changed_source)
    with pytest.raises(ledger.ConfidenceLedgerError, match="source changed during"):
        _candidate(root, module, "CHOICE")


@pytest.mark.parametrize("binding", ["spec", "sys_modules"])
def test_typing_literal_provider_refuses_counterfeit_intake_without_getters(
    tmp_path, monkeypatch, binding
):
    _root, module = _load_decorated_case(tmp_path, monkeypatch, _typing_literal_source())
    observed = []

    class UnverifiedProvider:
        def __getattribute__(self, name):
            observed.append(name)
            raise AssertionError("counterfeit provider getter must not run")

    with monkeypatch.context() as changed:
        if binding == "spec":
            changed.setitem(vars(typing), "__spec__", UnverifiedProvider())
        else:
            changed.setitem(sys.modules, "typing", UnverifiedProvider())
        assert _typing_literal_expected(module) is ledger._SOURCE_DERIVATION_FAILED
        assert ledger._typing_literal_provider_state() is None
    assert observed == []


@pytest.mark.parametrize("capture_scope", ["owned", "outer"])
def test_typing_literal_provider_binds_logical_symlink_before_source_read(
    tmp_path, monkeypatch, capture_scope
):
    original_path = Path(typing.__file__).resolve()
    stdlib = tmp_path / "stdlib"
    stdlib.mkdir()
    logical = stdlib / "typing.py"
    alternate = stdlib / "alternate.py"
    original_bytes = original_path.read_bytes()
    alternate.write_bytes(original_bytes)
    logical.symlink_to(original_path)
    original_get_path = ledger.sysconfig.get_path
    original_codes = ledger._typing_protocol_source_codes
    monkeypatch.setattr(
        ledger.sysconfig,
        "get_path",
        lambda name: str(stdlib) if name == "stdlib" else original_get_path(name),
    )

    def retarget_after_source_read(*args, **kwargs):
        result = original_codes(*args, **kwargs)
        logical.unlink()
        logical.symlink_to(alternate)
        return result

    monkeypatch.setattr(ledger, "_typing_protocol_source_codes", retarget_after_source_read)
    if capture_scope == "owned":
        assert ledger._typing_literal_provider_state() is None
    else:
        analysis = ledger._IntegrityAnalysisContext()
        token = ledger._ACTIVE_INTEGRITY_ANALYSIS.set(analysis)
        try:
            assert ledger._typing_literal_provider_state() is not None
            with pytest.raises(ledger.ConfidenceLedgerError, match="source target changed during"):
                analysis.assert_sources_unchanged()
        finally:
            ledger._ACTIVE_INTEGRITY_ANALYSIS.reset(token)
    assert original_path.read_bytes() == alternate.read_bytes() == original_bytes


@pytest.mark.parametrize(
    "extra_use", ["OTHER = t.Any\n", "def expose():\n    return t\n", "t = object()\n"]
)
def test_typing_literal_module_alias_profile_refuses_other_or_rebound_uses(
    tmp_path, monkeypatch, extra_use
):
    source = _typing_literal_source("t.Literal['alpha']", "import typing as t") + extra_use
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    _consumer, closure = _typing_literal_consumer(root, module, monkeypatch)
    with pytest.raises(ledger.ConfidenceLedgerError, match=r"module alias binding|side-effecting"):
        ledger._source_facade_runtime_projection(root, closure)


def test_typing_literal_module_alias_profile_checks_live_module_identity(tmp_path, monkeypatch):
    root, module = _load_decorated_case(
        tmp_path, monkeypatch, _typing_literal_source("t.Literal['alpha']", "import typing as t")
    )
    _consumer, closure = _typing_literal_consumer(root, module, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    observed = []

    class UnverifiedModule:
        def __getattribute__(self, name):
            observed.append(name)
            raise AssertionError("counterfeit module must not be read")

    monkeypatch.setitem(vars(module), "t", UnverifiedModule())
    with pytest.raises(ledger.ConfidenceLedgerError, match=r"module alias binding|side-effecting"):
        ledger._source_facade_runtime_projection(root, closure)
    assert observed == []
