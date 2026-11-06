"""Decorated source routes use the existing loaded-callable proof."""

from __future__ import annotations

import ast
import builtins
import functools
import importlib.util
import json
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


def _registry_keys_source(
    *,
    constants="KEY_A = 'alpha'\nKEY_B = 'beta'\n",
    mapping="{KEY_B: Kind.B, KEY_A: Kind.A}",
    expression="tuple(sorted(REGISTRY.keys()))",
    imports="",
):
    return (
        "from __future__ import annotations\nfrom enum import Enum\n"
        f"{imports}"
        "class Kind(Enum):\n    A = 'a'\n    B = 'b'\n"
        f"{constants}REGISTRY = {mapping}\nDEFAULTS = {expression}\n"
        "def read_defaults():\n    return DEFAULTS\n"
    )


def _registry_keys_expected(root, module, name="DEFAULTS"):
    tree = ast.parse(Path(module.__file__).read_bytes(), filename=module.__file__)
    declaration = ledger._module_scope_direct_binding_sites(tree, name)[0][1]
    return ledger._source_registry_keys_projection(
        declaration.value,
        repo_root=root,
        tree=tree,
        module=module,
        module_name=module.__name__,
    )


def _registry_keys_consumer(root, module, monkeypatch):
    consumer = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.registry_keys_consumer",
        f"from {module.__name__} import DEFAULTS\nRESULT = DEFAULTS\n",
    )
    closure = tuple(
        (owner.__name__, Path(owner.__file__).relative_to(root).as_posix())
        for owner in (module, consumer)
    )
    return consumer, closure


def test_registry_keys_projection_binds_actual_component_default_domain():
    from polisyos.core.components import discovery

    expected = (
        "polisyos.data_forge_domains",
        "polisyos.fabric_connectors",
        "polisyos.foundry_methods",
        "polisyos.ir_fragments",
        "polisyos.lex_evaluators",
        "polisyos.lex_extractors",
        "polisyos.lex_normpacks",
        "polisyos.norm_pack_providers",
        "polisyos.runtime_middlewares",
        "polisyos.scholar_extractors",
        "polisyos.scientist_nodes",
    )
    root = ledger._loaded_policy_engine_root()
    projected = _registry_keys_expected(root, discovery, "DEFAULT_ENTRY_POINT_GROUPS")
    assert projected.keys == expected
    assert expected == discovery.DEFAULT_ENTRY_POINT_GROUPS
    assert ledger._source_registry_keys_value_matches(
        discovery.DEFAULT_ENTRY_POINT_GROUPS, projected, discovery
    )
    assert _route(root, discovery, "DEFAULT_ENTRY_POINT_GROUPS") == (
        "symbol",
        discovery.__name__,
        "DEFAULT_ENTRY_POINT_GROUPS",
    )


@pytest.mark.parametrize(
    "source",
    [
        _registry_keys_source(),
        _registry_keys_source(mapping="{'beta': Kind.B, 'alpha': Kind.A}"),
        _registry_keys_source(
            imports="from builtins import tuple as pack, sorted as order\n",
            expression="pack(order(REGISTRY.keys()))",
        ),
    ],
)
def test_registry_keys_source_tuple_reaches_selected_consumer(tmp_path, monkeypatch, source):
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    expected = _registry_keys_expected(root, module)
    assert expected.keys == ("alpha", "beta")
    assert module.read_defaults() == expected.keys
    assert _route(root, module, "DEFAULTS") == ("symbol", module.__name__, "DEFAULTS")
    _consumer, closure = _registry_keys_consumer(root, module, monkeypatch)
    projection, _supplemental = ledger._source_facade_runtime_projection(root, closure)
    bindings = json.loads(projection)["bindings"]
    selected = [row for row in bindings if row["attribute"] == "DEFAULTS"]
    assert selected
    assert all(
        row["source_value_projection"]["whole_map_values_and_state"] == "not_established"
        for row in selected
    )


@pytest.mark.parametrize("mutation", ["extra", "missing", "foreign", "tuple", "order"])
def test_registry_keys_selected_consumer_rejects_changed_domain_or_tuple(
    tmp_path, monkeypatch, mutation
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _registry_keys_source())
    consumer, closure = _registry_keys_consumer(root, module, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    if mutation == "extra":
        module.REGISTRY["forged"] = module.Kind.A
    elif mutation == "missing":
        module.REGISTRY.pop("beta")
    elif mutation == "foreign":
        module.REGISTRY["forged"] = module.REGISTRY.pop("beta")
    else:
        wrong = ("alpha", "forged") if mutation == "tuple" else ("beta", "alpha")
        monkeypatch.setattr(module, "DEFAULTS", wrong)
        monkeypatch.setattr(consumer, "DEFAULTS", wrong)
        monkeypatch.setattr(consumer, "RESULT", wrong)
    with pytest.raises(
        ledger.ConfidenceLedgerError,
        match=r"registry key tuple differs|side-effecting direct source",
    ):
        ledger._source_facade_runtime_projection(root, closure)


def test_registry_keys_value_projection_rechecks_map_identity_and_keys(tmp_path, monkeypatch):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _registry_keys_source())
    expected = _registry_keys_expected(root, module)
    original = module.REGISTRY
    monkeypatch.setattr(module, "REGISTRY", dict(original))
    assert not ledger._source_registry_keys_value_matches(module.DEFAULTS, expected, module)
    monkeypatch.setattr(module, "REGISTRY", original)
    original["forged"] = module.Kind.A
    assert not ledger._source_registry_keys_value_matches(module.DEFAULTS, expected, module)


def test_registry_keys_values_remain_unknown_and_are_never_inspected(tmp_path, monkeypatch):
    source = _registry_keys_source()
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    observed = []

    class UnknownValue:
        def __getattribute__(self, name):
            observed.append(name)
            raise AssertionError("registry values are outside this projection")

        def __eq__(self, _other):
            observed.append("equality")
            raise AssertionError("registry values are outside this projection")

    for key in module.REGISTRY:
        module.REGISTRY[key] = UnknownValue()
    # Even an unexecuted value call in source has no key-domain meaning. The
    # projection must keep its initializer/value limitations explicit.
    Path(module.__file__).write_text(
        source.replace("Kind.B, KEY_A: Kind.A", "unexecuted(), KEY_A: unexecuted()"),
        encoding="utf-8",
    )
    expected = _registry_keys_expected(root, module)
    assert expected.keys == module.DEFAULTS
    _consumer, closure = _registry_keys_consumer(root, module, monkeypatch)
    projection, _supplemental = ledger._source_facade_runtime_projection(root, closure)
    assert "whole_map_values_and_state" in projection
    assert "not_established" in projection
    with pytest.raises(ledger.ConfidenceLedgerError, match="side-effecting direct source"):
        _route(root, module, "REGISTRY")
    assert observed == []


@pytest.mark.parametrize("binding", ["tuple", "sorted", "builtins"])
def test_registry_keys_shadowed_builtins_refuse_without_calls(tmp_path, monkeypatch, binding):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _registry_keys_source())
    observed = []

    def unverified(_value):
        observed.append("called")
        return module.DEFAULTS

    if binding == "builtins":
        monkeypatch.setattr(module, "__builtins__", {**vars(builtins), "sorted": unverified})
    else:
        monkeypatch.setattr(module, binding, unverified, raising=False)
    assert _registry_keys_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    with pytest.raises(ledger.ConfidenceLedgerError, match="side-effecting direct source"):
        _route(root, module, "DEFAULTS")
    assert observed == []


@pytest.mark.parametrize(
    ("mapping", "expression"),
    [
        ("{KEY_A: Kind.A, KEY_A: Kind.B}", "tuple(sorted(REGISTRY.keys()))"),
        ("{1: Kind.A}", "tuple(sorted(REGISTRY.keys()))"),
        ("{KEY_A: Kind.A}", "tuple(REGISTRY.keys())"),
        ("{KEY_A: Kind.A}", "tuple(sorted(REGISTRY.items()))"),
        ("{KEY_A: Kind.A}", "tuple(sorted(REGISTRY.keys(), reverse=True))"),
    ],
)
def test_registry_keys_profile_refuses_duplicate_keys_and_unsupported_expressions(
    tmp_path, monkeypatch, mapping, expression
):
    root, module = _load_decorated_case(
        tmp_path, monkeypatch, _registry_keys_source(mapping=mapping, expression=expression)
    )
    assert _registry_keys_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    with pytest.raises(ledger.ConfidenceLedgerError, match="side-effecting direct source"):
        _route(root, module, "DEFAULTS")


@pytest.mark.parametrize("binding", ["key", "mapping"])
def test_registry_keys_ambiguous_source_declarations_are_refused(tmp_path, monkeypatch, binding):
    source = _registry_keys_source()
    extra = "KEY_A = 'alpha'\n" if binding == "key" else "REGISTRY = {'alpha': Kind.A}\n"
    source = source.replace("DEFAULTS =", extra + "DEFAULTS =")
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    assert _registry_keys_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED


@pytest.mark.parametrize("binding", ["dict_subclass", "unknown_key"])
def test_registry_keys_unknown_live_protocols_are_refused_before_calling_them(
    tmp_path, monkeypatch, binding
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _registry_keys_source())
    observed = []

    class UnknownDict(dict):
        def __iter__(self):
            observed.append("iter")
            raise AssertionError("unknown iterator must not run")

        def __len__(self):
            observed.append("len")
            return 2

        def keys(self):
            observed.append("keys")
            raise AssertionError("unknown keys must not run")

    class UnknownMeta(type):
        def __hash__(cls):
            observed.append("metaclass_hash")
            return 1

    class UnknownKey(metaclass=UnknownMeta):
        def __hash__(self):
            observed.append("hash")
            return 1

        def __eq__(self, _other):
            observed.append("equality")
            return False

    wrong = (
        UnknownDict(module.REGISTRY)
        if binding == "dict_subclass"
        else {"alpha": module.Kind.A, UnknownKey(): module.Kind.B}
    )
    monkeypatch.setattr(module, "REGISTRY", wrong)
    observed.clear()
    assert _registry_keys_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    assert observed == []


def test_registry_keys_imported_constant_source_is_reconciled(tmp_path, monkeypatch):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    provider = _load_fixture_module(
        root, monkeypatch, "polisyos.registry_key_provider", "KEY_A = 'alpha'\n"
    )
    source = _registry_keys_source(
        imports="from polisyos.registry_key_provider import KEY_A\n",
        constants="KEY_B = 'beta'\n",
    )
    module = _load_fixture_module(root, monkeypatch, "polisyos.imported_registry_keys", source)
    assert _registry_keys_expected(root, module).keys == ("alpha", "beta")
    monkeypatch.setattr(provider, "KEY_A", "forged")
    monkeypatch.setattr(module, "KEY_A", "forged")
    module.REGISTRY["forged"] = module.REGISTRY.pop("alpha")
    assert _registry_keys_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED


@pytest.mark.parametrize("binding", ["spec", "sys_modules"])
def test_registry_keys_imported_source_refuses_unknown_provider_getters(
    tmp_path, monkeypatch, binding
):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    provider = _load_fixture_module(
        root, monkeypatch, "polisyos.registry_key_provider", "KEY_A = 'alpha'\n"
    )
    source = _registry_keys_source(
        imports="from polisyos.registry_key_provider import KEY_A\n",
        constants="KEY_B = 'beta'\n",
    )
    module = _load_fixture_module(root, monkeypatch, "polisyos.imported_registry_keys", source)
    observed = []

    class UnknownProvider:
        def __getattribute__(self, name):
            observed.append(name)
            raise AssertionError("unverified provider must not be inspected")

    if binding == "spec":
        monkeypatch.setitem(vars(provider), "__spec__", UnknownProvider())
    else:
        monkeypatch.setitem(sys.modules, provider.__name__, UnknownProvider())
    assert _registry_keys_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    assert observed == []


def test_registry_keys_imported_constant_symlink_is_bound_for_the_whole_projection(
    tmp_path, monkeypatch
):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    package = root / "src" / "polisyos"
    first = package / "key_first.py"
    second = package / "key_second.py"
    logical = package / "registry_key_provider.py"
    first.write_text("KEY_A = 'alpha'\n", encoding="utf-8")
    second.write_text("KEY_A = 'alpha'\n", encoding="utf-8")
    logical.symlink_to(first)
    spec = importlib.util.spec_from_file_location("polisyos.registry_key_provider", logical)
    provider = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, provider.__name__, provider)
    spec.loader.exec_module(provider)
    module = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.imported_registry_keys",
        _registry_keys_source(
            imports="from polisyos.registry_key_provider import KEY_A\n",
            constants="KEY_B = 'beta'\n",
        ),
    )
    original = ledger._source_dataclass_named_constant_body

    def retarget_after_read(name, **kwargs):
        result = original(name, **kwargs)
        if kwargs["module"] is provider:
            logical.unlink()
            logical.symlink_to(second)
        return result

    monkeypatch.setattr(ledger, "_source_dataclass_named_constant_body", retarget_after_read)
    with pytest.raises(ledger.ConfidenceLedgerError, match="source target changed during"):
        _registry_keys_expected(root, module)
    assert first.read_bytes() == second.read_bytes()


def test_registry_keys_source_and_current_map_cannot_change_after_projection(tmp_path, monkeypatch):
    source = _registry_keys_source()
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    path = Path(module.__file__)
    original = ledger._source_dataclass_named_constant

    def change_source(name, **kwargs):
        result = original(name, **kwargs)
        path.write_text(source + "\n# changed during source key projection\n", encoding="utf-8")
        return result

    monkeypatch.setattr(ledger, "_source_dataclass_named_constant", change_source)
    with pytest.raises(ledger.ConfidenceLedgerError, match="source changed during"):
        _candidate(root, module, "DEFAULTS")


def test_registry_keys_byte_budget_boundary_remains_a_checked_domain(tmp_path, monkeypatch):
    value = "a" * 200000
    root, module = _load_decorated_case(
        tmp_path,
        monkeypatch,
        _registry_keys_source(constants=f"KEY_A = {value!r}\n", mapping="{KEY_A: Kind.A}"),
    )
    expected = _registry_keys_expected(root, module)
    assert expected.keys == module.DEFAULTS
    consumer, closure = _registry_keys_consumer(root, module, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    wrong_key = "b" * 200000
    module.REGISTRY[wrong_key] = module.REGISTRY.pop(value)
    wrong_tuple = (wrong_key,)
    monkeypatch.setattr(module, "DEFAULTS", wrong_tuple)
    monkeypatch.setattr(consumer, "DEFAULTS", wrong_tuple)
    with pytest.raises(ledger.ConfidenceLedgerError, match="side-effecting direct source"):
        ledger._source_facade_runtime_projection(root, closure)
    assert (
        ledger._source_registry_key_domain({"x" * (1024**2): None})
        is ledger._SOURCE_DERIVATION_FAILED
    )


def test_registry_keys_package_relative_import_uses_the_same_source_provider(tmp_path, monkeypatch):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    package = root / "src" / "polisyos" / "registry_package"
    package.mkdir()
    _load_fixture_module(root, monkeypatch, "polisyos.keys", "KEY_A = 'alpha'\n")
    provider = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.registry_package.keys",
        "KEY_A = 'alpha'\n",
        path=package / "keys.py",
    )
    owner = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.registry_package",
        _registry_keys_source(imports="from .keys import KEY_A\n", constants="KEY_B = 'beta'\n"),
        path=package / "__init__.py",
    )
    assert _registry_keys_expected(root, owner).keys == ("alpha", "beta")
    _consumer, closure = _registry_keys_consumer(root, owner, monkeypatch)
    candidate = _candidate(root, owner, "DEFAULTS")
    assert candidate.route == ("symbol", owner.__name__, "DEFAULTS")
    assert candidate.package_initializer_effect_unknown is True
    assert ledger._source_registry_keys_value_matches(
        owner.DEFAULTS, _registry_keys_expected(root, owner), owner
    )
    with pytest.raises(ledger.ConfidenceLedgerError, match="unreconciled package initializer"):
        ledger._source_facade_runtime_projection(root, closure)
    # The competing parent provider still says 'alpha'. Only this actual
    # relative-import provider changes source; all live/import ends stay alpha.
    Path(provider.__file__).write_text("KEY_A = 'wrong'\n", encoding="utf-8")
    assert owner.KEY_A is provider.KEY_A
    assert _registry_keys_expected(root, owner) is ledger._SOURCE_DERIVATION_FAILED
    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._source_facade_runtime_projection(root, closure)


def test_registry_keys_imported_provider_cannot_substitute_another_repository_file(
    tmp_path, monkeypatch
):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    provider = _load_fixture_module(root, monkeypatch, "polisyos.keys", "KEY_A = 'alpha'\n")
    owner = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.imported_registry_keys",
        _registry_keys_source(
            imports="from polisyos.keys import KEY_A\n", constants="KEY_B = 'beta'\n"
        ),
    )
    assert _registry_keys_expected(root, owner).keys == ("alpha", "beta")
    consumer, closure = _registry_keys_consumer(root, owner, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    Path(provider.__file__).write_text("KEY_A = 'other'\n", encoding="utf-8")
    # Names, native spec and loader agree with one another, but point to a
    # different repository file than the requested canonical provider name.
    foreign = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.keys",
        "KEY_A = 'alpha'\n",
        path=root / "src" / "polisyos" / "foreign.py",
    )
    monkeypatch.setattr(owner, "KEY_A", foreign.KEY_A)
    assert consumer.RESULT is owner.DEFAULTS
    assert _registry_keys_expected(root, owner) is ledger._SOURCE_DERIVATION_FAILED
    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._source_facade_runtime_projection(root, closure)


@pytest.mark.parametrize("field", ["module_name", "spec_name", "loader_name", "loader_path"])
def test_registry_keys_imported_owner_reconciles_native_module_spec_and_loader_fields(
    tmp_path, monkeypatch, field
):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    provider = _load_fixture_module(root, monkeypatch, "polisyos.keys", "KEY_A = 'alpha'\n")
    owner = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.imported_registry_keys",
        _registry_keys_source(
            imports="from polisyos.keys import KEY_A\n", constants="KEY_B = 'beta'\n"
        ),
    )
    assert _registry_keys_expected(root, owner).keys == ("alpha", "beta")
    if field == "module_name":
        monkeypatch.setitem(vars(provider), "__name__", "polisyos.foreign")
    elif field == "spec_name":
        monkeypatch.setattr(provider.__spec__, "name", "polisyos.foreign")
    elif field == "loader_name":
        monkeypatch.setattr(provider.__spec__.loader, "name", "polisyos.foreign")
    else:
        foreign_path = root / "src" / "polisyos" / "foreign.py"
        foreign_path.write_text("KEY_A = 'alpha'\n", encoding="utf-8")
        monkeypatch.setattr(provider.__spec__.loader, "path", str(foreign_path))
    assert _registry_keys_expected(root, owner) is ledger._SOURCE_DERIVATION_FAILED


@pytest.mark.parametrize("count", [32, 64, 65])
def test_registry_keys_named_resolution_work_is_explicitly_bounded(tmp_path, monkeypatch, count):
    constants = "".join(f"KEY_{index} = 'k_{index}'\n" for index in range(count))
    mapping = "{" + ", ".join(f"KEY_{index}: Kind.A" for index in range(count)) + "}"
    root, module = _load_decorated_case(
        tmp_path, monkeypatch, _registry_keys_source(constants=constants, mapping=mapping)
    )
    original_body = ledger._source_dataclass_named_constant_body
    original_sites = ledger._module_scope_direct_binding_sites
    proofs = []
    queries = []

    def counted_body(name, **kwargs):
        proofs.append(name)
        return original_body(name, **kwargs)

    def counted_sites(tree, name):
        queries.append(name)
        return original_sites(tree, name)

    monkeypatch.setattr(ledger, "_source_dataclass_named_constant_body", counted_body)
    monkeypatch.setattr(ledger, "_module_scope_direct_binding_sites", counted_sites)
    projected = _registry_keys_expected(root, module)
    if count <= 64:
        assert projected.keys == module.DEFAULTS
        assert len(proofs) == count
        assert len(queries) <= 2 * count + 2
    else:
        assert projected is ledger._SOURCE_DERIVATION_FAILED
        assert proofs == []
        assert len(queries) <= 2


def test_registry_keys_nested_name_work_exhaustion_refuses_the_whole_projection(
    tmp_path, monkeypatch
):
    constants = []
    for name, value in (("A", "alpha"), ("B", "beta")):
        constants.append(f"{name}_BASE = {value!r}\n")
        prior = f"{name}_BASE"
        for index in range(32):
            constants.append(f"{name}_{index} = {prior}\n")
            prior = f"{name}_{index}"
    root, module = _load_decorated_case(
        tmp_path,
        monkeypatch,
        _registry_keys_source(constants="".join(constants), mapping="{A_31: Kind.A, B_31: Kind.B}"),
    )
    original = ledger._source_dataclass_named_constant_body
    proofs = []

    def counted_body(name, **kwargs):
        proofs.append(name)
        return original(name, **kwargs)

    monkeypatch.setattr(ledger, "_source_dataclass_named_constant_body", counted_body)
    assert _registry_keys_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    assert len(proofs) == 64


def test_registry_keys_unknown_source_root_is_refused_instead_of_guessing_a_provider(
    tmp_path, monkeypatch
):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    package = root / "foreign"
    package.mkdir()
    _load_fixture_module(root, monkeypatch, "foreign", "", path=package / "__init__.py")
    canonical_unknown = package / "keys.py"
    canonical_unknown.write_text("KEY_A = 'wrong'\n", encoding="utf-8")
    foreign = _load_fixture_module(
        root,
        monkeypatch,
        "foreign.keys",
        "KEY_A = 'alpha'\n",
        path=root / "foreign.py",
    )
    owner = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.imported_registry_keys",
        _registry_keys_source(
            imports="from foreign.keys import KEY_A\n", constants="KEY_B = 'beta'\n"
        ),
    )
    assert owner.KEY_A is foreign.KEY_A
    assert owner.DEFAULTS == ("alpha", "beta")
    assert _registry_keys_expected(root, owner) is ledger._SOURCE_DERIVATION_FAILED
    _consumer, closure = _registry_keys_consumer(root, owner, monkeypatch)
    with pytest.raises(ledger.ConfidenceLedgerError, match="side-effecting direct source"):
        ledger._source_facade_runtime_projection(root, closure)


def test_registry_keys_relative_owner_uses_canonical_package_path_after_file_alias(
    tmp_path, monkeypatch
):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    package = root / "src" / "polisyos" / "registry_package"
    package.mkdir()
    _load_fixture_module(root, monkeypatch, "polisyos.keys", "KEY_A = 'alpha'\n")
    provider = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.registry_package.keys",
        "KEY_A = 'alpha'\n",
        path=package / "keys.py",
    )
    body = root / "src" / "polisyos" / "registry_body.py"
    body.write_text(
        _registry_keys_source(imports="from .keys import KEY_A\n", constants="KEY_B = 'beta'\n"),
        encoding="utf-8",
    )
    initializer = package / "__init__.py"
    initializer.symlink_to(body)
    spec = importlib.util.spec_from_file_location("polisyos.registry_package", initializer)
    owner = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, owner.__name__, owner)
    spec.loader.exec_module(owner)
    # Both names identify exactly the same bytes. Package status comes from
    # the canonical repository path, rather than this mutable display field.
    monkeypatch.setattr(owner, "__file__", str(body))
    assert _registry_keys_expected(root, owner).keys == ("alpha", "beta")
    Path(provider.__file__).write_text("KEY_A = 'wrong'\n", encoding="utf-8")
    assert owner.KEY_A is provider.KEY_A
    assert _registry_keys_expected(root, owner) is ledger._SOURCE_DERIVATION_FAILED


def _immutable_tuple_source(expression="(VALUE, NUMBER, SIGNED, VALUE)", *, constants=None):
    if constants is None:
        constants = "VALUE = 'alpha'\nNUMBER = 1\nSIGNED = -0.0\nPAIR = (VALUE, NUMBER)\n"
    return (
        "from __future__ import annotations\n"
        f"{constants}OUTPUT = {expression}\n"
        "def read_output():\n    return OUTPUT\n"
    )


def _immutable_tuple_expected(root, module, name="OUTPUT", **kwargs):
    tree = ast.parse(Path(module.__file__).read_bytes(), filename=module.__file__)
    expression = ledger._module_scope_direct_binding_sites(tree, name)[0][1].value
    return ledger._source_immutable_tuple_expression(
        expression,
        repo_root=root,
        tree=tree,
        module=module,
        module_name=module.__name__,
        visited=frozenset({(module.__name__, name)}),
        **kwargs,
    )


def _immutable_tuple_consumer(root, module, monkeypatch):
    consumer = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.immutable_tuple_consumer",
        f"from {module.__name__} import OUTPUT\ndef observed():\n    return OUTPUT\n",
    )
    closure = tuple(
        (owner.__name__, Path(owner.__file__).relative_to(root).as_posix())
        for owner in (module, consumer)
    )
    return consumer, closure


def test_immutable_tuple_source_binds_actual_component_extension_groups():
    from polisyos.core.components import discovery

    root = ledger._loaded_policy_engine_root()
    expected = (
        "polisyos.fabric_connectors",
        "polisyos.scientist_governance_passes",
        "polisyos.foundry_methods",
        "polisyos.scientist_nodes",
        "polisyos.data_forge_domains",
        "polisyos.lex_normpacks",
        "polisyos.runtime_middlewares",
    )
    assert _immutable_tuple_expected(root, discovery, "EXTENSION_ENTRY_POINT_GROUPS") == expected
    assert expected == discovery.EXTENSION_ENTRY_POINT_GROUPS
    assert _source_constant_value(root, discovery, "EXTENSION_ENTRY_POINT_GROUPS") == expected
    assert _route(root, discovery, "EXTENSION_ENTRY_POINT_GROUPS") == (
        "symbol",
        discovery.__name__,
        "EXTENSION_ENTRY_POINT_GROUPS",
    )


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("(VALUE, NUMBER, SIGNED, VALUE)", ("alpha", 1, -0.0, "alpha")),
        ("((VALUE, NUMBER), (SIGNED, (VALUE,)))", (("alpha", 1), (-0.0, ("alpha",)))),
        ("(PAIR, VALUE)", (("alpha", 1), "alpha")),
        ("(2**3, VALUE)", (8, "alpha")),
        ("()", ()),
    ],
)
def test_immutable_tuple_source_owner_preserves_order_and_reaches_consumer(
    tmp_path, monkeypatch, expression, expected
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _immutable_tuple_source(expression))
    assert _immutable_tuple_expected(root, module) == expected
    assert _source_constant_value(root, module, "OUTPUT") == expected
    assert _route(root, module, "OUTPUT") == ("symbol", module.__name__, "OUTPUT")
    consumer, closure = _immutable_tuple_consumer(root, module, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    assert consumer.observed() == expected
    if expression == "(VALUE, NUMBER, SIGNED, VALUE)":
        assert consumer.observed()[0] == consumer.observed()[-1] == "alpha"
        assert consumer.observed()[1] == 1
        assert consumer.observed()[2].hex() == "-0x0.0p+0"


@pytest.mark.parametrize(
    "mutation", ["order", "duplicate", "primitive_type", "float_sign", "value"]
)
def test_immutable_tuple_selected_consumer_rejects_coherent_typed_changes(
    tmp_path, monkeypatch, mutation
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _immutable_tuple_source())
    consumer, closure = _immutable_tuple_consumer(root, module, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    wrong = {
        "order": ("alpha", -0.0, 1, "alpha"),
        "duplicate": ("alpha", 1, -0.0),
        "primitive_type": ("alpha", True, -0.0, "alpha"),
        "float_sign": ("alpha", 1, 0.0, "alpha"),
        "value": ("forged", 1, -0.0, "alpha"),
    }[mutation]
    monkeypatch.setattr(module, "OUTPUT", wrong)
    monkeypatch.setattr(consumer, "OUTPUT", wrong)
    assert consumer.observed() is wrong
    with pytest.raises(
        ledger.ConfidenceLedgerError, match="selected source literal binding differs"
    ):
        ledger._source_facade_runtime_projection(root, closure)


def test_immutable_tuple_live_source_name_and_imported_tuple_are_reconciled(tmp_path, monkeypatch):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    provider = _load_fixture_module(
        root, monkeypatch, "polisyos.immutable_pair_provider", "PAIR = ('alpha', 1, -0.0)\n"
    )
    module = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.imported_immutable_tuple",
        _immutable_tuple_source(
            "(PAIR, PAIR)", constants="from polisyos.immutable_pair_provider import PAIR\n"
        ),
    )
    expected = (("alpha", 1, -0.0), ("alpha", 1, -0.0))
    assert _immutable_tuple_expected(root, module) == expected
    consumer, closure = _immutable_tuple_consumer(root, module, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    assert consumer.observed()[0][0] == "alpha"
    forged = ("forged", 1, -0.0)
    monkeypatch.setattr(provider, "PAIR", forged)
    monkeypatch.setattr(module, "PAIR", forged)
    monkeypatch.setattr(module, "OUTPUT", (forged, forged))
    monkeypatch.setattr(consumer, "OUTPUT", module.OUTPUT)
    assert _immutable_tuple_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    with pytest.raises(ledger.ConfidenceLedgerError, match="side-effecting direct source"):
        ledger._source_facade_runtime_projection(root, closure)


@pytest.mark.parametrize(
    "expression", ["([VALUE],)", "(unexecuted(),)", "(VALUE.upper(),)", "(obj.value,)", "(OUTPUT,)"]
)
def test_immutable_tuple_source_profile_refuses_mutability_calls_attributes_and_cycles(
    tmp_path, monkeypatch, expression
):
    source = _immutable_tuple_source()
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    observed = []
    monkeypatch.setattr(module, "unexecuted", lambda: observed.append("called"), raising=False)
    Path(module.__file__).write_text(
        source.replace("OUTPUT = (VALUE, NUMBER, SIGNED, VALUE)", f"OUTPUT = {expression}"),
        encoding="utf-8",
    )
    assert _immutable_tuple_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    with pytest.raises(ledger.ConfidenceLedgerError, match="side-effecting direct source"):
        _route(root, module, "OUTPUT")
    assert observed == []


def test_immutable_tuple_forward_and_rebound_source_names_are_refused(tmp_path, monkeypatch):
    source = _immutable_tuple_source()
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    path = Path(module.__file__)
    path.write_text(source + "VALUE = 'alpha'\n", encoding="utf-8")
    assert _immutable_tuple_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    path.write_text(source.replace("VALUE = 'alpha'\n", "") + "VALUE = 'alpha'\n", encoding="utf-8")
    assert _immutable_tuple_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED


@pytest.mark.parametrize("count", [64, 65])
def test_immutable_tuple_named_resolution_budget_is_shared_and_never_truncates(
    tmp_path, monkeypatch, count
):
    constants = "".join(f"KEY_{index} = {index}\n" for index in range(count))
    expression = "(" + ", ".join(f"KEY_{index}" for index in range(count)) + ",)"
    root, module = _load_decorated_case(
        tmp_path, monkeypatch, _immutable_tuple_source(expression, constants=constants)
    )
    work = [64]
    result = _immutable_tuple_expected(root, module, work_remaining=work)
    if count == 64:
        assert result == tuple(range(count))
        assert work == [0]
    else:
        assert result is ledger._SOURCE_DERIVATION_FAILED
        assert work == [0]


@pytest.mark.parametrize("members", [4998, 4999])
def test_immutable_tuple_expanded_node_budget_is_shared_across_named_values(
    tmp_path, monkeypatch, members
):
    value = "(" + "0," * members + ")"
    root, module = _load_decorated_case(
        tmp_path,
        monkeypatch,
        _immutable_tuple_source("(PAIR, PAIR)", constants=f"PAIR = {value}\n"),
    )
    budget = [10000, 1024**2]
    result = _immutable_tuple_expected(root, module, value_budget=budget)
    if members == 4998:
        assert result == module.OUTPUT
        assert budget[0] == 1
    else:
        assert result is ledger._SOURCE_DERIVATION_FAILED
    assert budget[0] >= 0


def test_immutable_tuple_scalar_budget_and_source_depth_refuse_whole_value(tmp_path, monkeypatch):
    value = "a" * 200000
    root, module = _load_decorated_case(
        tmp_path,
        monkeypatch,
        _immutable_tuple_source("(VALUE, VALUE)", constants=f"VALUE = {value!r}\n"),
    )
    assert _immutable_tuple_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    nested = "VALUE"
    for _ in range(41):
        nested = f"({nested},)"
    Path(module.__file__).write_text(_immutable_tuple_source(nested), encoding="utf-8")
    assert _immutable_tuple_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED


def test_immutable_tuple_live_shared_dag_and_unknown_protocols_are_bounded(tmp_path, monkeypatch):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _immutable_tuple_source("(VALUE,)"))
    consumer, closure = _immutable_tuple_consumer(root, module, monkeypatch)
    nested = "alpha"
    for _ in range(13):
        nested = (nested, nested)
    monkeypatch.setattr(module, "OUTPUT", (nested,))
    monkeypatch.setattr(consumer, "OUTPUT", module.OUTPUT)
    with pytest.raises(
        ledger.ConfidenceLedgerError, match="selected source literal binding differs"
    ):
        ledger._source_facade_runtime_projection(root, closure)
    observed = []

    class UnknownMeta(type):
        def __hash__(cls):
            observed.append("metaclass_hash")
            return 1

    class UnknownValue(metaclass=UnknownMeta):
        def __getattribute__(self, name):
            observed.append(name)
            raise AssertionError("unknown tuple member must not be inspected")

        def __eq__(self, _other):
            observed.append("equality")
            return True

    monkeypatch.setattr(module, "OUTPUT", (UnknownValue(),))
    monkeypatch.setattr(consumer, "OUTPUT", module.OUTPUT)
    with pytest.raises(
        ledger.ConfidenceLedgerError, match="selected source literal binding differs"
    ):
        ledger._source_facade_runtime_projection(root, closure)
    assert observed == []


def test_immutable_tuple_name_rebinding_does_not_rewrite_the_source_premise(tmp_path, monkeypatch):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _immutable_tuple_source())
    consumer, closure = _immutable_tuple_consumer(root, module, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    wrong = ("forged", 1, -0.0, "forged")
    monkeypatch.setattr(module, "VALUE", "forged")
    monkeypatch.setattr(module, "OUTPUT", wrong)
    monkeypatch.setattr(consumer, "OUTPUT", wrong)
    assert _immutable_tuple_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    with pytest.raises(ledger.ConfidenceLedgerError, match="side-effecting direct source"):
        ledger._source_facade_runtime_projection(root, closure)


def test_immutable_tuple_standalone_reader_uses_current_source_in_one_snapshot(
    tmp_path, monkeypatch
):
    source = _immutable_tuple_source()
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    path = Path(module.__file__)
    old_tree = ast.parse(source, filename=str(path))
    old_expression = ledger._module_scope_direct_binding_sites(old_tree, "OUTPUT")[0][1].value
    path.write_text(source.replace("VALUE = 'alpha'", "VALUE = 'wrong'"), encoding="utf-8")
    assert (
        ledger._source_immutable_tuple_expression(
            old_expression,
            repo_root=root,
            tree=old_tree,
            module=module,
            module_name=module.__name__,
        )
        is ledger._SOURCE_DERIVATION_FAILED
    )
    path.write_text(source, encoding="utf-8")
    original = ledger._source_dataclass_named_constant

    def change_source_after_name(name, **kwargs):
        value = original(name, **kwargs)
        path.write_text(source + "\n# changed during tuple derivation\n", encoding="utf-8")
        return value

    monkeypatch.setattr(ledger, "_source_dataclass_named_constant", change_source_after_name)
    with pytest.raises(ledger.ConfidenceLedgerError, match="source changed during"):
        _immutable_tuple_expected(root, module)


@pytest.mark.parametrize("binding", ["local", "imported"])
def test_immutable_tuple_name_profile_does_not_reach_older_frozenset_constructor(
    tmp_path, monkeypatch, binding
):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    if binding == "imported":
        _load_fixture_module(
            root,
            monkeypatch,
            "polisyos.immutable_frozen_provider",
            "VALUE = frozenset({'alpha'})\n",
        )
        constants = "from polisyos.immutable_frozen_provider import VALUE\nALIAS = VALUE\n"
    else:
        constants = "VALUE = frozenset({'alpha'})\nALIAS = VALUE\n"
    module = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.named_frozen_tuple",
        _immutable_tuple_source("(ALIAS,)", constants=constants),
    )
    original = ledger._source_frozenset_literal_expression
    calls = []

    def observe_constructor(node, **kwargs):
        if isinstance(node, ast.Call):
            calls.append("constructor")
        return original(node, **kwargs)

    monkeypatch.setattr(ledger, "_source_frozenset_literal_expression", observe_constructor)
    assert _immutable_tuple_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    _consumer, closure = _immutable_tuple_consumer(root, module, monkeypatch)
    with pytest.raises(ledger.ConfidenceLedgerError, match="side-effecting direct source"):
        ledger._source_facade_runtime_projection(root, closure)
    assert calls == []
    # The earlier standalone frozenset profile remains available independently.
    assert _source_constant_value(root, module, "VALUE") == frozenset({"alpha"})
    assert calls == ["constructor"]


def test_immutable_tuple_mutable_literal_candidate_does_not_establish_selected_value(
    tmp_path, monkeypatch
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _immutable_tuple_source("([1],)"))
    # Legacy literal discovery names a declaration. It does not establish the
    # immutable tuple profile or qualify the selected runtime binding.
    assert _candidate(root, module, "OUTPUT").route == ("symbol", module.__name__, "OUTPUT")
    assert _immutable_tuple_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    consumer, closure = _immutable_tuple_consumer(root, module, monkeypatch)
    assert consumer.observed() == ([1],)
    with pytest.raises(ledger.ConfidenceLedgerError, match="immutable tuple is unresolved"):
        ledger._source_facade_runtime_projection(root, closure)
