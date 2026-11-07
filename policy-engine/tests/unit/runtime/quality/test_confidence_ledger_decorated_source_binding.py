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
from itertools import pairwise
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


def _load_fixture_package(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    path: Path,
):
    spec = importlib.util.spec_from_file_location(
        name,
        path,
        submodule_search_locations=[str(path.parent)],
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, package)
    parent_name, _, child_name = name.rpartition(".")
    if parent_name in sys.modules:
        monkeypatch.setattr(sys.modules[parent_name], child_name, package, raising=False)
    spec.loader.exec_module(package)
    return package


def _route(root: Path, module: types.ModuleType, name: str):
    return ledger._source_module_direct_binding_route(
        root,
        module.__name__,
        name,
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        visited=frozenset(),
    )


def _int_enum_dataclass_source() -> str:
    return (
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "from enum import IntEnum\n\n"
        "class QualityTier(IntEnum):\n"
        "    UNVERIFIED = 0\n"
        "    VERIFIED = 1\n\n"
        "@dataclass(frozen=True, slots=True)\n"
        "class FetchRequest:\n"
        "    min_quality_tier: QualityTier = QualityTier.UNVERIFIED\n"
    )


def test_actual_fetch_request_source_route_supports_its_int_enum_default():
    from polisyos.ir import connectors

    request = connectors.FetchRequest(dataset_id="source-binding-probe")
    assert request.min_quality_tier is connectors.QualityTier.UNVERIFIED
    assert _route(ledger._loaded_policy_engine_root(), connectors, "FetchRequest") == (
        "symbol",
        "polisyos.ir.connectors",
        "FetchRequest",
    )


def test_string_enum_dataclass_route_keeps_alias_defaults_supported(tmp_path, monkeypatch):
    source = (
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "from enum import Enum\n\n"
        "class Kind(str, Enum):\n"
        "    CANONICAL = 'same'\n"
        "    ALIAS = 'same'\n\n"
        "@dataclass(frozen=True, slots=True)\n"
        "class Request:\n"
        "    kind: Kind = Kind.ALIAS\n"
    )
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    assert module.Request().kind is module.Kind.CANONICAL
    assert _route(root, module, "Request") == ("symbol", module.__name__, "Request")


def test_int_enum_dataclass_route_rejects_source_member_value_drift(tmp_path, monkeypatch):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _int_enum_dataclass_source())
    assert _route(root, module, "FetchRequest") == (
        "symbol",
        module.__name__,
        "FetchRequest",
    )
    source_path = Path(module.__file__)
    source_path.write_text(
        _int_enum_dataclass_source().replace("UNVERIFIED = 0", "UNVERIFIED = 2"),
        encoding="utf-8",
    )
    with pytest.raises(
        ledger.ConfidenceLedgerError,
        match="decorated direct source binding is unresolved",
    ):
        _route(root, module, "FetchRequest")


def test_int_enum_dataclass_route_rejects_bool_member_literal(tmp_path, monkeypatch):
    source = _int_enum_dataclass_source().replace("UNVERIFIED = 0", "UNVERIFIED = True")
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    with pytest.raises(
        ledger.ConfidenceLedgerError,
        match="decorated direct source binding is unresolved",
    ):
        _route(root, module, "FetchRequest")


def test_int_enum_dataclass_route_rejects_foreign_live_enum_binding(tmp_path, monkeypatch):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _int_enum_dataclass_source())
    foreign_source = (
        "from enum import IntEnum\n\n"
        "class QualityTier(IntEnum):\n"
        "    UNVERIFIED = 0\n"
        "    VERIFIED = 1\n"
    )
    foreign = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.foreign_quality_tier",
        foreign_source,
    )
    monkeypatch.setattr(module, "QualityTier", foreign.QualityTier)
    with pytest.raises(
        ledger.ConfidenceLedgerError,
        match="decorated direct source binding is unresolved",
    ):
        _route(root, module, "FetchRequest")


def test_int_enum_dataclass_route_rejects_spoofed_origin_with_changed_integer_behavior(
    tmp_path, monkeypatch
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _int_enum_dataclass_source())
    altered_source = _int_enum_dataclass_source().replace(
        "class QualityTier(IntEnum):\n",
        "class QualityTier(IntEnum):\n    def __int__(self):\n        return 99\n",
    )
    foreign = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.foreign_quality_tier_with_int_override",
        altered_source.split("@dataclass", 1)[0],
    )
    type.__setattr__(foreign.QualityTier, "__module__", module.__name__)
    type.__setattr__(foreign.QualityTier, "__qualname__", "QualityTier")
    monkeypatch.setattr(module, "QualityTier", foreign.QualityTier)
    with pytest.raises(
        ledger.ConfidenceLedgerError,
        match="decorated direct source binding is unresolved",
    ):
        _route(root, module, "FetchRequest")


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


def _ordering_source(root="__lt__", *, preserved_method=False):
    operator = {"__lt__": "<", "__le__": "<=", "__gt__": ">", "__ge__": ">="}[root]
    preserved = (
        "    def __le__(self, other):\n        return self.value <= other.value\n"
        if preserved_method
        else ""
    )
    return (
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "from functools import total_ordering as ordered\n\n"
        "@ordered\n@dataclass(frozen=True, slots=True)\nclass Ranked:\n"
        "    value: int\n"
        f"    def {root}(self, other: object) -> bool:\n"
        "        if not isinstance(other, Ranked):\n            return NotImplemented\n"
        f"        return self.value {operator} other.value\n"
        f"{preserved}"
    )


@pytest.mark.parametrize("root_name", ["__lt__", "__le__", "__gt__", "__ge__"])
def test_total_ordering_dataclass_source_reaches_real_comparison_consumer(
    tmp_path, monkeypatch, root_name
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _ordering_source(root_name))
    before = dict(vars(module.Ranked))
    provider_names = {
        name: value.__name__
        for name, value in vars(functools).items()
        if (
            type(value) is types.FunctionType
            and name.endswith(("_from_lt", "_from_le", "_from_gt", "_from_ge"))
        )
    }
    assert _route(root, module, "Ranked") == ("symbol", module.__name__, "Ranked")
    consumer = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.ordering_consumer",
        f"from {module.__name__} import Ranked\n"
        "def compare(left, right):\n"
        "    a, b = Ranked(left), Ranked(right)\n"
        "    return a < b, a <= b, a > b, a >= b\n",
    )
    closure = tuple(
        (owner.__name__, Path(owner.__file__).relative_to(root).as_posix())
        for owner in (module, consumer)
    )
    ledger._source_facade_runtime_projection(root, closure)
    assert consumer.compare(1, 2) == (True, True, False, False)
    assert consumer.compare(2, 2) == (False, True, False, True)
    assert consumer.compare(3, 2) == (False, False, True, True)
    assert vars(module.Ranked) == before
    assert provider_names == {name: vars(functools)[name].__name__ for name in provider_names}


def test_total_ordering_preserves_source_declared_comparison(tmp_path, monkeypatch):
    root, module = _load_decorated_case(
        tmp_path, monkeypatch, _ordering_source("__gt__", preserved_method=True)
    )
    preserved = vars(module.Ranked)["__le__"]
    assert preserved.__module__ == module.__name__
    assert _route(root, module, "Ranked") == ("symbol", module.__name__, "Ranked")
    assert vars(module.Ranked)["__le__"] is preserved
    assert module.Ranked(1) <= module.Ranked(2)


def test_actual_semver_total_ordering_has_source_bound_release_prerelease_and_build():
    from polisyos.core.components import ids

    assert _route(ledger._loaded_policy_engine_root(), ids, "SemVer") == (
        "symbol",
        ids.__name__,
        "SemVer",
    )
    versions = ["1.0.0-alpha", "1.0.0-alpha.2", "1.0.0-alpha.10", "1.0.0", "1.0.1"]
    parsed = [ids.SemVer.parse(value) for value in versions]
    scrambled = list(reversed(parsed))
    assert [str(value) for value in sorted(scrambled)] == versions
    for left, right in pairwise(parsed):
        assert left < right and left <= right and right > left and right >= left
    first, second = ids.SemVer.parse("1.0.0+one"), ids.SemVer.parse("1.0.0+two")
    assert first != second and not first < second and not second < first
    assert first.without_build() == second.without_build() == ids.SemVer.parse("1.0.0")
    profile = ledger._total_ordering_provider_projection()
    assert profile["scope"] == "source_checked_expected_dataclass_transform_only"
    assert profile["actual_class_execution_and_constructor_loader_history"] == "not_established"


@pytest.mark.parametrize("mutation", ["delete", "remove", "replace"])
def test_total_ordering_rechecks_generated_method_after_prior_pass(tmp_path, monkeypatch, mutation):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _ordering_source())
    assert _route(root, module, "Ranked") == ("symbol", module.__name__, "Ranked")
    if mutation == "delete":
        monkeypatch.delattr(module.Ranked, "__ge__")
        # Reflected __le__ preserves this one comparison, but the source-owned
        # complete transform must still reject the missing generated member.
        assert module.Ranked(2) >= module.Ranked(1)
    elif mutation == "remove":
        # Deletion permits the reflected __le__ fallback; an absent callable
        # behind the retained slot distinguishes removal of this operation.
        monkeypatch.setattr(module.Ranked, "__ge__", None)
        with pytest.raises(TypeError):
            _ = module.Ranked(2) >= module.Ranked(1)
    else:
        original = vars(module.Ranked)["__gt__"]
        replacement = types.FunctionType(
            (lambda self, other: True).__code__, original.__globals__, original.__name__
        )
        replacement.__module__ = original.__module__
        replacement.__qualname__ = original.__qualname__
        replacement.__doc__ = original.__doc__
        monkeypatch.setattr(module.Ranked, "__gt__", replacement)
        assert module.Ranked(1) > module.Ranked(2)
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "Ranked")


@pytest.mark.parametrize(
    "target",
    [
        "factory_code",
        "factory_default",
        "helper_code",
        "helper_globals",
        "helper_closure",
        "annotations",
    ],
)
def test_total_ordering_provider_refuses_corrupt_function_without_executing_it(monkeypatch, target):
    observed = []

    def forbidden(*args, **kwargs):
        observed.append("called")
        raise AssertionError("unverified provider must not execute")

    if target == "factory_code":
        monkeypatch.setattr(functools.total_ordering, "__code__", (lambda cls: cls).__code__)
    elif target == "factory_default":
        monkeypatch.setattr(functools.total_ordering, "__defaults__", (1,))
    elif target == "helper_code":
        monkeypatch.setattr(functools._gt_from_lt, "__code__", (lambda self, other: True).__code__)
    elif target == "annotations":
        monkeypatch.setattr(functools._gt_from_lt, "__annotate__", forbidden)
    else:
        original = functools._gt_from_lt
        if target == "helper_closure":
            captured = observed

            def wrong(self, other):
                captured.append("called")
                return True

            replacement = wrong
        else:
            replacement = types.FunctionType(original.__code__, dict(original.__globals__))
        replacement.__name__ = original.__name__
        replacement.__qualname__ = original.__qualname__
        replacement.__module__ = original.__module__
        monkeypatch.setattr(functools, "_gt_from_lt", replacement)
    assert ledger._total_ordering_source_provider() is None
    assert observed == []


@pytest.mark.parametrize("mutation", ["root", "row", "function", "list_subclass", "hostile_key"])
def test_total_ordering_provider_reconciles_complete_conversion_table(monkeypatch, mutation):
    observed = []
    table = {key: list(rows) for key, rows in functools._convert.items()}
    if mutation == "root":
        del table["__lt__"]
    elif mutation == "row":
        table["__lt__"][0] = ("__ge__", functools._gt_from_lt)
    elif mutation == "function":
        table["__lt__"][0] = ("__gt__", functools._gt_from_ge)
    elif mutation == "list_subclass":

        class UnknownList(list):
            def __iter__(self):
                observed.append("iter")
                raise AssertionError("unknown sequence protocol must not run")

        table["__lt__"] = UnknownList(table["__lt__"])
    else:

        class UnknownKey:
            def __hash__(self):
                observed.append("hash")
                return 123

        table[UnknownKey()] = []
        observed.clear()
    monkeypatch.setattr(functools, "_convert", table)
    assert ledger._total_ordering_source_provider() is None
    assert observed == []


@pytest.mark.parametrize("name", ["getattr", "max", "setattr", "type", "NotImplemented"])
def test_total_ordering_provider_refuses_shadowed_consumed_global(monkeypatch, name):
    observed = []

    def forbidden(*args, **kwargs):
        observed.append("called")
        raise AssertionError("unverified global must not execute")

    monkeypatch.setitem(vars(functools), name, forbidden)
    assert ledger._total_ordering_source_provider() is None
    assert observed == []


def test_total_ordering_refuses_coherent_effectful_provider_source_before_replay(
    tmp_path, monkeypatch
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _ordering_source())
    provider_path = Path(functools.__file__).resolve()
    original_read = Path.read_bytes
    source = original_read(provider_path)
    effect = tmp_path / "must-not-be-created"
    poisoned = source.replace(
        b"def total_ordering(cls):\n",
        f"def total_ordering(cls):\n    open({str(effect)!r}, 'w').close()\n".encode(),
        1,
    )
    assert poisoned != source
    code = next(
        item
        for item in ledger._python_provider_source_code_objects(poisoned, str(provider_path))
        if item.co_qualname == "total_ordering"
    )
    # The source and live function agree, and open is a real builtin. Neither
    # is sufficient authorization for the verifier to execute the new effect.
    monkeypatch.setattr(functools.total_ordering, "__code__", code)
    monkeypatch.setattr(
        Path, "read_bytes", lambda self: poisoned if self == provider_path else original_read(self)
    )
    assert ledger._total_ordering_source_provider() is None
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "Ranked")
    assert not effect.exists()


@pytest.mark.parametrize(
    "field",
    [
        "__doc__",
        "__annotations__",
        "__dict__",
        "__type_params__",
        "__name__",
        "__qualname__",
        "__module__",
    ],
)
def test_total_ordering_refuses_hostile_function_metadata_without_callbacks(
    tmp_path, monkeypatch, field
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _ordering_source())
    observed = []

    class UnknownDoc:
        def __ne__(self, other):
            observed.append("compare")
            raise AssertionError("untrusted metadata comparison must not run")

    class UnknownDict(dict):
        def __bool__(self):
            observed.append("bool")
            raise AssertionError("untrusted metadata truthiness must not run")

    class UnknownTuple(tuple):
        def __bool__(self):
            observed.append("bool")
            raise AssertionError("untrusted metadata truthiness must not run")

    class UnknownString(str):
        def __hash__(self):
            observed.append("hash")
            raise AssertionError("untrusted metadata hash must not run")

        def __eq__(self, other):
            observed.append("compare")
            raise AssertionError("untrusted metadata comparison must not run")

    if field in {"__name__", "__qualname__", "__module__"}:
        replacement = UnknownString(getattr(functools._gt_from_lt, field))
    elif field == "__doc__":
        replacement = UnknownDoc()
    elif field == "__type_params__":
        replacement = UnknownTuple()
    else:
        replacement = UnknownDict()
    monkeypatch.setattr(functools._gt_from_lt, field, replacement)
    assert ledger._total_ordering_source_provider() is None
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "Ranked")
    assert observed == []


def test_total_ordering_source_factory_alias_is_not_authority(tmp_path, monkeypatch):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _ordering_source())
    observed = []

    def unknown_factory(cls):
        observed.append("called")
        return cls

    monkeypatch.setattr(module, "ordered", unknown_factory)
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "Ranked")
    assert observed == []


@pytest.mark.parametrize("alias", ["FunctionType", "ModuleType", "CodeType"])
def test_total_ordering_refuses_counterfeit_native_type_alias_before_metadata(monkeypatch, alias):
    observed = []

    class UnknownFunction:
        def __getattribute__(self, name):
            observed.append(name)
            raise AssertionError("counterfeit function metadata must not be read")

    with monkeypatch.context() as changed:
        changed.setattr(types, alias, UnknownFunction)
        # pytest's setattr helper itself introspects replacement values. Use
        # native dictionary storage so only the verifier observes this object.
        changed.setitem(vars(functools), "_gt_from_lt", UnknownFunction())
        assert ledger._total_ordering_source_provider() is None
    assert observed == []


@pytest.mark.parametrize("alias", ["FunctionType", "ModuleType", "CodeType"])
def test_total_ordering_missing_native_type_alias_does_not_call_module_getattr(monkeypatch, alias):
    observed = []

    def forbidden(name):
        observed.append(name)
        raise AssertionError("unknown module getter must not run")

    with monkeypatch.context() as changed:
        changed.delitem(vars(types), alias)
        changed.setitem(vars(types), "__getattr__", forbidden)
        assert ledger._total_ordering_source_provider() is None
    assert observed == []


@pytest.mark.parametrize("alias", ["MappingProxyType", "GetSetDescriptorType"])
def test_total_ordering_uses_intrinsic_passive_storage_when_unneeded_alias_is_missing(
    monkeypatch, alias
):
    observed = []

    def forbidden(name):
        observed.append(name)
        raise AssertionError("unused module getter must not run")

    with monkeypatch.context() as changed:
        changed.delitem(vars(types), alias)
        changed.setitem(vars(types), "__getattr__", forbidden)
        assert ledger._total_ordering_source_provider() is not None
    assert observed == []


@pytest.mark.parametrize("target", ["spec_dictionary", "spec_getter", "loader_getter"])
def test_total_ordering_storage_intake_rejects_unknown_protocols(monkeypatch, target):
    observed = []

    class UnknownDict(dict):
        def __len__(self):
            observed.append("len")
            raise AssertionError("untrusted metadata mapping must not run")

    class UnknownStorage:
        @property
        def __dict__(self):
            observed.append("dict")
            raise AssertionError("untrusted storage getter must not run")

    with monkeypatch.context() as changed:
        if target == "spec_dictionary":
            changed.setattr(functools.__spec__, "__dict__", UnknownDict(vars(functools.__spec__)))
        elif target == "spec_getter":
            changed.setattr(ledger, "ModuleSpec", UnknownStorage)
            changed.setattr(functools, "__spec__", UnknownStorage())
        else:
            changed.setattr(ledger, "SourceFileLoader", UnknownStorage)
            changed.setattr(functools.__spec__, "loader", UnknownStorage())
        assert ledger._total_ordering_source_provider() is None
    assert observed == []


@pytest.mark.parametrize(
    "target", ["types", "provider", "spec", "loader", "class", "origin", "source"]
)
def test_total_ordering_intake_rejects_oversized_metadata_before_unbounded_work(
    monkeypatch, target
):
    with monkeypatch.context() as changed:
        if target in {"types", "provider", "spec", "loader"}:
            namespace = {
                "types": vars(types),
                "provider": vars(functools),
                "spec": vars(functools.__spec__),
                "loader": vars(functools.__spec__.loader),
            }[target]
            for index in range(10001):
                changed.setitem(namespace, f"_extra_{index}", None)
        elif target == "class":
            unknown = type("Oversized", (), {f"_extra_{index}": None for index in range(10001)})
            changed.setattr(ledger, "ModuleSpec", unknown)
            changed.setattr(functools, "__spec__", unknown())
        elif target == "origin":
            changed.setattr(functools, "__file__", "x" * (1024**2 + 1))
        else:
            original = Path.read_bytes
            path = Path(functools.__file__).resolve()
            changed.setattr(
                Path,
                "read_bytes",
                lambda self: b"#" * (1024**2 + 1) if self == path else original(self),
            )
        assert ledger._total_ordering_source_provider() is None


def _hostile_code_constant(kind, observed):
    class UnknownTuple(tuple):
        def __iter__(self):
            observed.append("iter")
            raise AssertionError("untrusted constant iteration must not run")

    class UnknownFloat(float):
        def hex(self):
            observed.append("hex")
            raise AssertionError("untrusted constant conversion must not run")

    class UnknownComplex(complex):
        @property
        def real(self):
            observed.append("real")
            raise AssertionError("untrusted constant descriptor must not run")

    class UnknownString(str):
        def __eq__(self, other):
            observed.append("compare")
            raise AssertionError("untrusted constant comparison must not run")

    class UnknownBytes(bytes):
        def __len__(self):
            observed.append("len")
            raise AssertionError("untrusted constant size must not run")

    class UnknownMeta(type):
        def __getattribute__(cls, name):
            observed.append(name)
            raise AssertionError("untrusted constant class lookup must not run")

    class Unknown(metaclass=UnknownMeta):
        pass

    values = {
        "tuple": UnknownTuple((1, 2)),
        "float": UnknownFloat(1.0),
        "complex": UnknownComplex(1.0),
        "string": UnknownString("value"),
        "bytes": UnknownBytes(b"value"),
        "unknown": Unknown(),
        "slice_member": slice(Unknown()),
    }
    return values[kind]


@pytest.mark.parametrize(
    "kind", ["tuple", "float", "complex", "string", "bytes", "unknown", "slice_member"]
)
def test_code_normalizer_rejects_non_native_constants_without_callbacks(kind):
    observed = []
    value = _hostile_code_constant(kind, observed)
    with pytest.raises(ledger.ConfidenceLedgerError, match="canonical_loaded_runtime_mismatch"):
        ledger._normalize_code_constant(value)
    assert observed == []


@pytest.mark.parametrize(
    "kind", ["tuple", "float", "complex", "unknown", "outer_tuple", "code_name", "code_qualname"]
)
def test_total_ordering_route_refuses_corrupt_native_code_fields_without_callbacks(
    tmp_path, monkeypatch, kind
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _ordering_source())
    observed = []
    code = functools._gt_from_lt.__code__
    if kind == "outer_tuple":
        replacement = code.replace(
            co_consts=type(_hostile_code_constant("tuple", observed))(code.co_consts)
        )
    elif kind in {"code_name", "code_qualname"}:
        field = "co_name" if kind == "code_name" else "co_qualname"
        replacement = code.replace(**{field: _hostile_code_constant("string", observed)})
    else:
        replacement = code.replace(
            co_consts=(*code.co_consts, _hostile_code_constant(kind, observed))
        )
    monkeypatch.setattr(functools._gt_from_lt, "__code__", replacement)
    assert ledger._total_ordering_source_provider() is None
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "Ranked")
    assert observed == []


@pytest.mark.parametrize(
    "shape", ["tuple_dag", "code_dag", "string_bytes", "integer_bytes", "depth"]
)
def test_total_ordering_code_work_is_bounded_before_comparison(tmp_path, monkeypatch, shape):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _ordering_source())
    code = functools._gt_from_lt.__code__
    if shape == "tuple_dag":
        value = (None,)
        for _level in range(17):
            value = (value, value)
    elif shape == "code_dag":
        value = code
        for _level in range(17):
            value = code.replace(co_consts=(value, value))
    elif shape == "string_bytes":
        value = "x" * (1024**2 // 4 + 1)
    elif shape == "integer_bytes":
        value = 1 << (8 * 1024**2)
    else:
        value = None
        for _level in range(41):
            value = (value,)
    replacement = code.replace(co_consts=(*code.co_consts, value))
    monkeypatch.setattr(functools._gt_from_lt, "__code__", replacement)
    with pytest.raises(ledger.ConfidenceLedgerError, match="work budget exhausted"):
        ledger._normalize_code_object(replacement, work_budget=[10000, 1024**2])
    assert ledger._total_ordering_source_provider() is None
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "Ranked")


def test_code_work_budget_counts_every_occurrence_and_keeps_unbounded_callers():
    assert ledger._normalize_code_constant((1, 2), work_budget=[3, 1024]) == {"tuple": [1, 2]}
    with pytest.raises(ledger.ConfidenceLedgerError, match="work budget exhausted"):
        ledger._normalize_code_constant((1, 2), work_budget=[2, 1024])
    values = tuple(range(10001))
    assert len(ledger._normalize_code_constant(values)["tuple"]) == len(values)
    with pytest.raises(ledger.ConfidenceLedgerError, match="work budget exhausted"):
        ledger._normalize_code_constant(values, work_budget=[10000, 1024**2])


def test_code_work_budget_counts_empty_metadata_names_before_traversal():
    source = (lambda: None).__code__
    code = source.replace(co_names=("",) * 3)
    # One code node + three name occurrences + its one None constant.
    assert ledger._normalize_code_object(code, work_budget=[5, 1024**2])["names"] == ["", "", ""]
    with pytest.raises(ledger.ConfidenceLedgerError, match="work budget exhausted"):
        ledger._normalize_code_object(code, work_budget=[4, 1024**2])
    huge = source.replace(co_names=("",) * 100001)
    with pytest.raises(ledger.ConfidenceLedgerError, match="work budget exhausted"):
        ledger._normalize_code_object(huge, work_budget=[10000, 1024**2])


@pytest.mark.parametrize("method", ["__lt__", "__init__", "__eq__"])
def test_total_ordering_rejects_unknown_source_and_generated_annotation_thunks(
    tmp_path, monkeypatch, method
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _ordering_source())
    observed = []

    def forbidden(*args, **kwargs):
        observed.append("annotate")
        raise AssertionError("unverified annotation thunk must not execute")

    monkeypatch.setattr(vars(module.Ranked)[method], "__annotate__", forbidden)
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "Ranked")
    assert observed == []


@pytest.mark.parametrize(
    "target",
    ["defaults", "kwdefaults", "annotation_keys", "dict", "module", "name", "qualname", "doc"],
)
def test_total_ordering_source_method_metadata_rejects_unknown_protocols(
    tmp_path, monkeypatch, target
):
    source = _ordering_source().replace(
        "other: object) -> bool", "other: object, *, permitted: bool = True) -> bool"
    )
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    function = vars(module.Ranked)["__lt__"]
    observed = []

    class UnknownTuple(tuple):
        def __bool__(self):
            observed.append("bool")
            raise AssertionError("unknown defaults truthiness must not run")

    class UnknownDict(dict):
        def __bool__(self):
            observed.append("bool")
            raise AssertionError("unknown function dictionary truthiness must not run")

    class UnknownKey:
        def __hash__(self):
            observed.append("hash")
            return hash("permitted")

    class UnknownString(str):
        def __eq__(self, other):
            observed.append("compare")
            raise AssertionError("unknown function metadata comparison must not run")

    if target == "defaults":
        monkeypatch.setattr(function, "__defaults__", UnknownTuple())
    elif target == "kwdefaults":
        replacement = {UnknownKey(): True}
        observed.clear()
        monkeypatch.setattr(function, "__kwdefaults__", replacement)
    elif target == "annotation_keys":
        replacement = {UnknownKey(): "object", "permitted": "bool", "return": "bool"}
        observed.clear()
        monkeypatch.setattr(function, "__annotations__", replacement)
    elif target == "dict":
        monkeypatch.setattr(function, "__dict__", UnknownDict())
    else:
        field = f"__{target}__"
        monkeypatch.setattr(function, field, UnknownString(getattr(function, field) or ""))
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "Ranked")
    assert observed == []


@pytest.mark.parametrize("mutation", ["reversed", "extra", "metaclass"])
def test_total_ordering_profile_refuses_unknown_transform_chains(tmp_path, monkeypatch, mutation):
    source = _ordering_source()
    if mutation == "reversed":
        source = source.replace(
            "@ordered\n@dataclass(frozen=True, slots=True)",
            "@dataclass(frozen=True, slots=True)\n@ordered",
        )
    elif mutation == "extra":
        source = source.replace("@ordered\n", "@ordered\n@ordered\n")
    else:
        source = source.replace("class Ranked:", "class Ranked(metaclass=type):")
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    with pytest.raises(ledger.ConfidenceLedgerError, match="decorated direct source binding"):
        _route(root, module, "Ranked")


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


def _candidate(root, module, name, *, discovery_only=False):
    return ledger._source_module_import_route_candidate(
        root,
        module.__name__,
        name,
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        discovery_only=discovery_only,
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


def test_lazy_imported_child_has_source_candidate_but_needs_loaded_binding(
    loader_child_case,
):
    root, package, child = loader_child_case
    path = Path(package.__file__)
    path.write_text(
        "from importlib import import_module\n"
        "def __getattr__(name):\n"
        "    if name in {'Remote'}:\n"
        "        from . import child as _child\n"
        "        return getattr(_child, name)\n"
        "    raise AttributeError(name)\n",
        encoding="utf-8",
    )
    sys.modules.pop(child.__name__)
    package.__dict__.pop("child", None)

    candidate = _candidate(root, package, "child", discovery_only=True)
    assert candidate.route == ("module", child.__name__, None)
    assert candidate.binding_basis == "source_expression"
    with pytest.raises(ledger.ConfidenceLedgerError):
        _candidate(root, package, "child")

    __import__(child.__name__)
    loaded = _candidate(root, package, "child")
    assert package.child is sys.modules[child.__name__]
    assert loaded.route == ("module", child.__name__, None)
    assert loaded.binding_basis == "loader_child"


def test_type_alias_route_binds_real_artifact_selector_without_evaluating_value():
    from polisyos.ir.artifacts import contracts

    root = Path(contracts.__file__).parents[4]
    candidate = ledger._source_module_import_route_candidate(
        root,
        contracts.__name__,
        "ArtifactSelector",
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        discovery_only=True,
    )
    assert candidate.route == ("symbol", contracts.__name__, "ArtifactSelector")
    assert candidate.binding_basis == "source_expression"
    assert ledger._source_module_direct_binding_route(
        root,
        contracts.__name__,
        "ArtifactSelector",
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        visited=frozenset(),
    ) == ("symbol", contracts.__name__, "ArtifactSelector")


def test_type_alias_route_does_not_execute_lazy_evaluator(tmp_path, monkeypatch):
    source = (
        "EVENTS = []\n"
        "def touch():\n"
        "    EVENTS.append('evaluated')\n"
        "    return int\n"
        "type Selector = touch()\n"
    )
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    assert module.EVENTS == []
    assert _route(root, module, "Selector") == ("symbol", module.__name__, "Selector")
    assert module.EVENTS == []


def test_type_alias_route_does_not_call_mutable_gc_accessor(tmp_path, monkeypatch):
    root, module = _load_decorated_case(tmp_path, monkeypatch, "type Selector = int\n")

    def unexpected_gc_call(*args, **kwargs):
        pytest.fail("TypeAlias routing must use its owned native evaluator descriptor")

    monkeypatch.setattr(ledger.gc, "get_referents", unexpected_gc_call)
    assert _route(root, module, "Selector") == ("symbol", module.__name__, "Selector")


def test_type_alias_route_refuses_foreign_live_alias(tmp_path, monkeypatch):
    root, module = _load_decorated_case(tmp_path, monkeypatch, "type Selector = int\n")
    foreign = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.foreign_type_alias_fixture",
        "type Selector = str\n",
    )
    monkeypatch.setattr(module, "Selector", foreign.Selector)
    with pytest.raises(ledger.ConfidenceLedgerError, match="unsupported direct source binding"):
        _route(root, module, "Selector")


_CANONICAL_LAZY_EXPORT_SOURCE = """from polisyos.ir.api import EXPORTS, resolve_lazy_export as _resolve

def __getattr__(name):
    return _resolve(name, namespace=globals(), exports=EXPORTS)
"""


def test_resolve_lazy_export_map_recognizes_only_the_canonical_finite_call_shape():
    accepted = ledger._literal_module_getattr_mapping_names(
        ast.parse(_CANONICAL_LAZY_EXPORT_SOURCE)
    )
    assert accepted == frozenset({"EXPORTS"})

    wrong_helper_owner = _CANONICAL_LAZY_EXPORT_SOURCE.replace(
        "polisyos.ir.api", "polisyos.other.api"
    )
    assert (
        ledger._literal_module_getattr_mapping_names(ast.parse(wrong_helper_owner)) == frozenset()
    )

    shadowed_helper = _CANONICAL_LAZY_EXPORT_SOURCE.replace(
        "\ndef __getattr__", "\n_resolve = lambda *args, **kwargs: None\n\ndef __getattr__"
    )
    assert ledger._literal_module_getattr_mapping_names(ast.parse(shadowed_helper)) == frozenset()

    noncanonical_call = _CANONICAL_LAZY_EXPORT_SOURCE.replace("namespace=globals()", "namespace={}")
    assert ledger._literal_module_getattr_mapping_names(ast.parse(noncanonical_call)) == frozenset()


def test_data_forge_lazy_export_map_binds_catalog_selection_error_live():
    from polisyos.data_forge.read_api import catalog

    module_name = "polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection"
    root = Path(ledger.__file__).parents[4]
    catalog_path = Path(catalog.__file__)
    tree = ast.parse(catalog_path.read_bytes(), filename=catalog_path.name)
    index = ledger._source_module_provider_index(
        root,
        catalog.__name__,
        tree,
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )
    assert index.mapping_names == frozenset({"_EXPORTS"})
    assert index.providers_by_export["CatalogSelectionError"] == frozenset({module_name})
    assert index.invalid_exports == frozenset()

    route = ledger._source_module_import_route_candidate(
        root,
        catalog.__name__,
        "CatalogSelectionError",
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )
    assert route.route == ("symbol", module_name, "CatalogSelectionError")
    assert route.binding_basis == "literal_getattr"

    helper = importlib.import_module("polisyos.data_forge.read_api._lazy")
    assert vars(catalog)["load_lazy_export"] is vars(helper)["load_lazy_export"]
    assert vars(catalog)["lazy_dir"] is vars(helper)["lazy_dir"]
    selected = catalog.CatalogSelectionError
    provider = sys.modules[module_name]
    assert (
        vars(catalog)["CatalogSelectionError"]
        is selected
        is vars(provider)["CatalogSelectionError"]
    )


def test_data_forge_lazy_map_profile_rejects_noncanonical_import_and_name_binding():
    source = (
        "from ._lazy import lazy_dir, load_lazy_export\n"
        "_EXPORTS = {'Thing': 'polisyos.fixture.provider'}\n"
        "def __getattr__(name):\n"
        "    return load_lazy_export(name, exports=_EXPORTS, "
        "module_name=__name__, namespace=globals())\n"
        "def __dir__():\n"
        "    return lazy_dir(globals(), _EXPORTS)\n"
    )
    module_name = "polisyos.data_forge.read_api.fixture"

    def names(text: str) -> frozenset[str]:
        return ledger._literal_module_getattr_mapping_names(
            ast.parse(text), source_module_name=module_name
        )

    assert names(source) == frozenset({"_EXPORTS"})
    assert names(source.replace("from ._lazy", "from .other")) == frozenset()
    assert names(source.replace("module_name=__name__", "module_name=__package__")) == frozenset()
    shadowed = source.replace(
        "def __getattr__",
        "load_lazy_export = lambda *a, **k: None\ndef __getattr__",
    )
    assert names(shadowed) == frozenset()
    assert names(source + "__name__ = 'spoofed'\n") == frozenset()


def test_data_forge_lazy_map_allows_only_bounded_sorted_and_constant_reads():
    source = (
        "from ._lazy import lazy_dir, load_lazy_export\n"
        "_EXPORTS = {'Thing': 'polisyos.fixture.provider'}\n"
        "def __getattr__(name):\n"
        "    return load_lazy_export(name, exports=_EXPORTS, "
        "module_name=__name__, namespace=globals())\n"
        "def __dir__():\n"
        "    return lazy_dir(globals(), _EXPORTS)\n"
        "def build():\n"
        "    return load_lazy_export('Thing', exports=_EXPORTS, "
        "module_name=__name__, namespace=globals())\n"
        "__all__ = sorted([*_EXPORTS, 'build'])\n"
    )
    tree = ast.parse(source)
    index = ledger._literal_module_getattr_provider_index(
        tree, source_module_name="polisyos.data_forge.read_api.fixture"
    )
    maps, invalid, _namespace_effect_unknown = ledger._source_declared_facade_mapping_values(
        tree,
        index.mapping_names,
        source_module_name="polisyos.data_forge.read_api.fixture",
    )
    assert index.mapping_names == frozenset({"_EXPORTS"})
    assert index.providers_by_export["Thing"] == frozenset({"polisyos.fixture.provider"})
    assert index.invalid_exports == frozenset()
    assert maps == {"_EXPORTS": {"Thing": "polisyos.fixture.provider"}}
    assert invalid == frozenset()


_DATA_REQUIREMENT_GROUPED_GETTER_SOURCE = """from __future__ import annotations

def __getattr__(name):
    if name in {"ConceptRefs", "Intent", "AuthorityProfile"}:
        from polisyos.policy_grammar import (
            PolicyGrammarConceptSpineRefs,
            PolicyGrammarIntent,
            UniversalAuthorityProfile,
        )
        exports = {
            "ConceptRefs": PolicyGrammarConceptSpineRefs,
            "Intent": PolicyGrammarIntent,
            "AuthorityProfile": UniversalAuthorityProfile,
        }
        return exports[name]

    if name in {"Compiler", "compile_for_slot"}:
        from .compiler import DataRequirementCompiler, compiled_requirements_for_world_slot
        exports = {
            "Compiler": DataRequirementCompiler,
            "compile_for_slot": compiled_requirements_for_world_slot,
        }
        return exports[name]
    raise AttributeError(f"module has no attribute {name!r}")
"""


def test_grouped_local_object_map_getter_resolves_both_exact_import_branches():
    tree = ast.parse(_DATA_REQUIREMENT_GROUPED_GETTER_SOURCE)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
    providers = ledger._literal_module_getattr_direct_providers(
        tree,
        function,
        "name",
        package_module_name="polisyos.data_requirement",
    )
    assert providers == {
        "ConceptRefs": ("polisyos.policy_grammar", "PolicyGrammarConceptSpineRefs"),
        "Intent": ("polisyos.policy_grammar", "PolicyGrammarIntent"),
        "AuthorityProfile": ("polisyos.policy_grammar", "UniversalAuthorityProfile"),
        "Compiler": ("polisyos.data_requirement.compiler", "DataRequirementCompiler"),
        "compile_for_slot": (
            "polisyos.data_requirement.compiler",
            "compiled_requirements_for_world_slot",
        ),
    }
    index = ledger._literal_module_getattr_provider_index(
        tree, package_module_name="polisyos.data_requirement"
    )
    assert index.mapping_names == frozenset()
    assert index.invalid_exports == frozenset()
    assert index.providers_by_export["Compiler"] == frozenset(
        {"polisyos.data_requirement.compiler"}
    )


@pytest.mark.parametrize(
    "replacement",
    [
        (
            '"ConceptRefs": PolicyGrammarConceptSpineRefs,',
            '"ConceptRefs": PolicyGrammarConceptSpineRefs,\n            "ConceptRefs": PolicyGrammarIntent,',
        ),
        ('"ConceptRefs": PolicyGrammarConceptSpineRefs,', '"ConceptRefs": ForeignConceptRefs,'),
        ("        exports = {", "        run_callback()\n        exports = {"),
        (
            'if name in {"Compiler", "compile_for_slot"}:',
            'if name in {"Compiler", "compile_for_slot", "Foreign"}:',
        ),
    ],
    ids=["duplicate-key", "foreign-value", "extra-effect", "branch-map-mismatch"],
)
def test_grouped_local_object_map_getter_rejects_ambiguous_or_effectful_branch(replacement):
    source = _DATA_REQUIREMENT_GROUPED_GETTER_SOURCE.replace(*replacement)
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
    assert (
        ledger._literal_module_getattr_direct_providers(
            tree,
            function,
            "name",
            package_module_name="polisyos.data_requirement",
        )
        is None
    )
    assert "exports" not in ledger._literal_module_getattr_mapping_names(
        tree, source_module_name="polisyos.data_requirement"
    )


def test_data_requirement_grouped_getter_binds_actual_imported_objects():
    from polisyos.data_requirement import DataRequirementCompiler as ImportedCompiler
    from polisyos.data_requirement import (
        PolicyGrammarConceptSpineRefs as ImportedConceptRefs,
    )
    from polisyos.data_requirement.compiler import DataRequirementCompiler
    from polisyos.policy_grammar import PolicyGrammarConceptSpineRefs

    facade = importlib.import_module("polisyos.data_requirement")
    root = Path(ledger.__file__).parents[4]
    data_requirement_path = Path(facade.__file__)
    tree = ast.parse(data_requirement_path.read_bytes(), filename=data_requirement_path.name)
    index = ledger._source_module_provider_index(
        root,
        facade.__name__,
        tree,
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )
    assert index.mapping_names == frozenset()
    assert index.providers_by_export["DataRequirementCompiler"] == frozenset(
        {"polisyos.data_requirement.compiler"}
    )
    assert index.provider_symbols_by_export["DataRequirementCompiler"] == frozenset(
        {"DataRequirementCompiler"}
    )
    assert ImportedCompiler is DataRequirementCompiler
    assert ImportedConceptRefs is PolicyGrammarConceptSpineRefs
    assert "DataRequirementCompiler" not in vars(facade)
    assert "PolicyGrammarConceptSpineRefs" not in vars(facade)
    assert facade.DataRequirementCompiler is ImportedCompiler
    assert facade.PolicyGrammarConceptSpineRefs is ImportedConceptRefs
    for export_name in ("DataRequirementCompiler", "PolicyGrammarConceptSpineRefs"):
        candidate = ledger._source_module_import_route_candidate(
            root,
            facade.__name__,
            export_name,
            directory_entries={},
            source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        )
        expected_module, expected_symbol = (
            index.providers_by_export[export_name],
            (index.provider_symbols_by_export[export_name]),
        )
        assert candidate.route == (
            "symbol",
            next(iter(expected_module)),
            next(iter(expected_symbol)),
        )
        assert candidate.binding_basis == "literal_getattr"


def test_imported_literal_map_survives_only_exact_builtin_sorted_read():
    source = ast.parse("from polisyos.ir.api import EXPORTS\n__all__ = sorted(EXPORTS)\n")
    source_map = {"chosen": ("polisyos.provider", "chosen")}
    maps, invalid, namespace_unknown = ledger._source_declared_facade_mapping_values(
        source,
        frozenset({"EXPORTS"}),
        external_mappings={"EXPORTS": source_map},
    )
    assert maps == {"EXPORTS": source_map}
    assert not invalid
    assert namespace_unknown is False

    extra_key = ast.parse(
        "from polisyos.ir.api import EXPORTS\n__all__ = sorted(EXPORTS, key=str)\n"
    )
    _maps, invalid, _namespace_unknown = ledger._source_declared_facade_mapping_values(
        extra_key,
        frozenset({"EXPORTS"}),
        external_mappings={"EXPORTS": source_map},
    )
    assert "EXPORTS" in invalid

    shadowed = ast.parse(
        "from polisyos.ir.api import EXPORTS\n"
        "sorted = lambda value: value\n"
        "__all__ = sorted(EXPORTS)\n"
    )
    _maps, invalid, _namespace_unknown = ledger._source_declared_facade_mapping_values(
        shadowed,
        frozenset({"EXPORTS"}),
        external_mappings={"EXPORTS": source_map},
    )
    assert "EXPORTS" in invalid


def test_ir_kernel_lazy_export_resolves_to_source_owned_live_provider(monkeypatch):
    kernel = importlib.import_module("polisyos.ir.kernel")
    export_name = "DEFAULT_CONSTRAINT_REGISTRY"
    selected = getattr(kernel, export_name)
    api = importlib.import_module("polisyos.ir.api")
    constraints = importlib.import_module("polisyos.ir.kernel.constraints")
    assert selected is vars(constraints)[export_name]
    assert vars(kernel)["resolve_lazy_export"] is api.resolve_lazy_export
    closure = (
        (
            kernel.__name__,
            Path(kernel.__file__).relative_to(ledger._loaded_policy_engine_root()).as_posix(),
        ),
        (
            api.__name__,
            Path(api.__file__).relative_to(ledger._loaded_policy_engine_root()).as_posix(),
        ),
        (
            constraints.__name__,
            Path(constraints.__file__).relative_to(ledger._loaded_policy_engine_root()).as_posix(),
        ),
    )
    assert ledger._source_facade_runtime_projection(ledger._loaded_policy_engine_root(), closure)[0]

    monkeypatch.setattr(kernel, "resolve_lazy_export", lambda *_args, **_kwargs: None)
    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._source_facade_runtime_projection(ledger._loaded_policy_engine_root(), closure)


def test_ir_analytics_guarded_lazy_export_binds_truthfulness_tier_and_keeps_child_owner():
    from polisyos.ir.analytics import TruthfulnessTier as ImportedTruthfulnessTier
    from polisyos.ir.analytics import _truthfulness as truthfulness_module
    from polisyos.ir.analytics import calibration_diagnostics as imported_child

    facade = importlib.import_module("polisyos.ir.analytics")
    root = Path(ledger.__file__).parents[4]
    facade_path = Path(facade.__file__)
    tree = ast.parse(facade_path.read_bytes(), filename=facade_path.name)
    index = ledger._source_module_provider_index(
        root,
        facade.__name__,
        tree,
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )
    assert "ANALYTICS_FACADE_EXPORTS" in index.mapping_names
    assert index.providers_by_export["TruthfulnessTier"] == frozenset(
        {"polisyos.ir.analytics._truthfulness"}
    )
    assert index.provider_symbols_by_export["TruthfulnessTier"] == frozenset({"TruthfulnessTier"})
    candidate = ledger._source_module_import_route_candidate(
        root,
        facade.__name__,
        "TruthfulnessTier",
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )
    assert candidate.route == (
        "symbol",
        "polisyos.ir.analytics._truthfulness",
        "TruthfulnessTier",
    )
    assert candidate.binding_basis == "literal_getattr"
    assert ImportedTruthfulnessTier is truthfulness_module.TruthfulnessTier
    assert facade.TruthfulnessTier is ImportedTruthfulnessTier

    child_candidate = ledger._source_module_import_route_candidate(
        root,
        facade.__name__,
        "calibration_diagnostics",
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )
    assert child_candidate.route == (
        "module",
        "polisyos.ir.analytics.calibration_diagnostics",
        None,
    )
    assert imported_child is importlib.import_module(child_candidate.route[1])


@pytest.mark.parametrize(
    ("mutate", "map_is_recognized"),
    [
        (
            lambda source: source.replace(
                "if name not in ANALYTICS_FACADE_EXPORTS:",
                "if name in ANALYTICS_FACADE_EXPORTS:",
            ),
            False,
        ),
        (
            lambda source: source.replace(
                "if name not in ANALYTICS_FACADE_EXPORTS:",
                "if name not in OTHER_EXPORTS:",
            ),
            False,
        ),
        (
            lambda source: source.replace(
                'if exc.name != f"{__name__}.{name}":',
                'if exc.name == f"{__name__}.{name}":',
            ),
            False,
        ),
        (
            lambda source: source + "\nresolve_lazy_export = lambda *args, **kwargs: None\n",
            False,
        ),
        (lambda source: source + "\nANALYTICS_FACADE_EXPORTS = {}\n", True),
    ],
    ids=[
        "wrong-membership",
        "foreign-guard-map",
        "wrong-exception-guard",
        "rebound-helper",
        "rebound-map",
    ],
)
def test_ir_analytics_guarded_lazy_export_rejects_malformed_or_rebound_source(
    mutate, map_is_recognized
):
    path = Path(importlib.import_module("polisyos.ir.analytics").__file__)
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(mutate(source))
    names = ledger._literal_module_getattr_mapping_names(
        tree, source_module_name="polisyos.ir.analytics"
    )
    assert (names == frozenset({"ANALYTICS_FACADE_EXPORTS"})) is map_is_recognized
    index = ledger._literal_module_getattr_provider_index(
        tree,
        source_module_name="polisyos.ir.analytics",
    )
    assert index.providers_by_export.get("TruthfulnessTier", frozenset()) == frozenset()
    if map_is_recognized:
        assert "TruthfulnessTier" in index.invalid_exports or "*" in index.invalid_exports


def _guarded_lazy_fixture(tmp_path, monkeypatch):
    root = tmp_path / "guarded-lazy-engine"
    package_root = root / "src" / "polisyos"
    ir_root = package_root / "ir"
    facade_root = ir_root / "analytics_fixture"
    facade_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (ir_root / "__init__.py").write_text("", encoding="utf-8")
    api_path = ir_root / "api.py"
    api_source = """from importlib import import_module

MAP = {"Mapped": ("polisyos.ir.analytics_fixture_provider", "Mapped")}

def resolve_lazy_export(name, *, namespace, exports):
    module_name, symbol_name = exports[name]
    value = getattr(import_module(module_name), symbol_name)
    namespace[name] = value
    return value
"""
    api = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.ir.api",
        api_source,
        path=api_path,
    )
    monkeypatch.setattr(sys.modules["polisyos.ir"], "api", api, raising=False)
    facade_path = facade_root / "__init__.py"
    facade_source = """import importlib
from polisyos.ir.api import MAP, resolve_lazy_export

def __getattr__(name):
    if name not in MAP:
        try:
            module = importlib.import_module(f"{__name__}.{name}")
        except ModuleNotFoundError as exc:
            if exc.name != f"{__name__}.{name}":
                raise
        else:
            globals()[name] = module
            return module
    return resolve_lazy_export(name, namespace=globals(), exports=MAP)
"""
    facade_path.write_text(facade_source, encoding="utf-8")
    facade = _load_fixture_package(
        root,
        monkeypatch,
        "polisyos.ir.analytics_fixture",
        facade_path,
    )
    provider_path = ir_root / "analytics_fixture_provider.py"
    provider = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.ir.analytics_fixture_provider",
        "class Mapped:\n    pass\n",
        path=provider_path,
    )
    return root, facade, facade_path, facade_source, provider


def test_guarded_lazy_child_requires_valid_map_absence_and_preserves_mapped_owner(
    tmp_path, monkeypatch
):
    root, facade, facade_path, _facade_source, provider = _guarded_lazy_fixture(
        tmp_path, monkeypatch
    )
    facade_root = facade_path.parent
    child_path = facade_root / "child.py"
    child_path.write_text("VALUE = 4\n", encoding="utf-8")
    child_name = f"{facade.__name__}.child"
    child = importlib.import_module(child_name)
    facade.__dict__.pop("child", None)
    assert facade.child is child

    child_route = ledger._source_module_import_route_candidate(
        root,
        facade.__name__,
        "child",
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        discovery_only=True,
    )
    assert child_route.route == ("module", child_name, None)
    strict_child_route = ledger._source_module_import_route_candidate(
        root,
        facade.__name__,
        "child",
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )
    assert strict_child_route.route == ("module", child_name, None)
    assert strict_child_route.binding_basis == "loader_child"

    mapped_path = facade_root / "Mapped.py"
    assert not mapped_path.exists()
    mapped_route = ledger._source_module_import_route_candidate(
        root,
        facade.__name__,
        "Mapped",
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )
    assert mapped_route.route == (
        "symbol",
        provider.__name__,
        "Mapped",
    )
    assert mapped_route.binding_basis == "literal_getattr"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda source: source + "\nMAP = {}\n",
        lambda source: source.replace("if name not in MAP:", "if name in MAP:"),
    ],
    ids=["rebound-map", "malformed-fallback-guard"],
)
def test_guarded_lazy_child_needs_source_proven_absence_in_discovery_and_strict_routes(
    tmp_path, monkeypatch, mutate
):
    root, facade, facade_path, facade_source, _provider = _guarded_lazy_fixture(
        tmp_path, monkeypatch
    )
    child_path = facade_path.parent / "child.py"
    child_path.write_text("VALUE = 4\n", encoding="utf-8")
    child_name = f"{facade.__name__}.child"
    child = importlib.import_module(child_name)
    facade.__dict__.pop("child", None)
    assert facade.child is child
    facade_path.write_text(mutate(facade_source), encoding="utf-8")

    for discovery_only in (True, False):
        try:
            candidate = ledger._source_module_import_route_candidate(
                root,
                facade.__name__,
                "child",
                directory_entries={},
                source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
                discovery_only=discovery_only,
            )
        except ledger.ConfidenceLedgerError:
            continue
        assert candidate.route != ("module", child_name, None)


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


def _native_type_source(expression="CALL | tuple[str, CALL | Choice] | Choice", *, extra=""):
    return (
        "from __future__ import annotations\n"
        "from collections.abc import Callable\nfrom dataclasses import dataclass\n"
        "@dataclass(frozen=True)\nclass Choice:\n    value: str\n"
        "CALL = Callable[[], object]\n"
        f"{extra}OUTPUT = {expression}\n"
    )


def _native_type_expected(root, module, name="OUTPUT"):
    tree = ast.parse(Path(module.__file__).read_bytes(), filename=module.__file__)
    expression = ledger._module_scope_direct_binding_sites(tree, name)[0][1].value
    return ledger._source_type_expression_projection(
        expression,
        repo_root=root,
        tree=tree,
        module=module,
        module_name=module.__name__,
        visited=frozenset({(module.__name__, name)}),
    )


@pytest.mark.parametrize(
    "expression",
    [
        "CALL | tuple[str, CALL | Choice] | Choice",
        "tuple[str, int]",
        "Callable[[int, str], object]",
        "str | int | str",
    ],
)
def test_native_type_metadata_source_reaches_real_selected_reader(
    tmp_path, monkeypatch, expression
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _native_type_source(expression))
    expected = _native_type_expected(root, module)
    assert type(expected) is ledger._SourceResolvedAnnotation
    assert ledger._source_resolved_annotation_matches(module.OUTPUT, expected)
    assert _route(root, module, "OUTPUT") == ("symbol", module.__name__, "OUTPUT")
    consumer, closure = _immutable_tuple_consumer(root, module, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    assert consumer.observed() is module.OUTPUT
    profile = ledger._native_type_metadata_provider_projection()
    assert profile["initialization_construction_and_behavior"] == "not_established"
    assert profile["independent_transform_verification"] is False


def test_native_type_metadata_binds_actual_builtin_loader_spec():
    from polisyos.core.components import discovery

    root = ledger._loaded_policy_engine_root()
    for name in ("BuiltinComponentLoader", "BuiltinLoaderSpec"):
        expected = _native_type_expected(root, discovery, name)
        assert type(expected) is ledger._SourceResolvedAnnotation
        assert ledger._source_resolved_annotation_matches(vars(discovery)[name], expected)
        assert _route(root, discovery, name) == ("symbol", discovery.__name__, name)


@pytest.mark.parametrize(
    "mutation", ["callable_args", "tuple_origin", "tuple_args", "class_identity", "union_order"]
)
def test_native_type_metadata_selected_consumer_refuses_same_shape_forgery(
    tmp_path, monkeypatch, mutation
):
    from collections.abc import Callable

    root, module = _load_decorated_case(tmp_path, monkeypatch, _native_type_source())
    consumer, closure = _immutable_tuple_consumer(root, module, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    if mutation == "callable_args":
        wrong = Callable[[int], object] | tuple[str, module.CALL | module.Choice] | module.Choice
    elif mutation == "tuple_origin":
        wrong = module.CALL | list[str, module.CALL | module.Choice] | module.Choice
    elif mutation == "tuple_args":
        wrong = module.CALL | tuple[int, module.CALL | module.Choice] | module.Choice
    elif mutation == "union_order":
        wrong = module.Choice | module.CALL | tuple[str, module.CALL | module.Choice]
    else:
        twin = type("Choice", (), {"__module__": module.__name__})
        wrong = module.CALL | tuple[str, module.CALL | twin] | twin
    monkeypatch.setattr(module, "OUTPUT", wrong)
    monkeypatch.setattr(consumer, "OUTPUT", wrong)
    assert consumer.observed() is wrong
    with pytest.raises(ledger.ConfidenceLedgerError, match="selected source type metadata differs"):
        ledger._source_facade_runtime_projection(root, closure)


def test_native_type_metadata_imported_alias_is_reconciled_to_source(tmp_path, monkeypatch):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    provider = _load_fixture_module(
        root, monkeypatch, "polisyos.native_type_provider", _native_type_source("tuple[str, int]")
    )
    module = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.imported_native_type",
        "from __future__ import annotations\n"
        "from polisyos.native_type_provider import OUTPUT as BASE\n"
        "OUTPUT = BASE | str\n",
    )
    expected = _native_type_expected(root, module)
    assert ledger._source_resolved_annotation_matches(module.OUTPUT, expected)
    consumer, closure = _immutable_tuple_consumer(root, module, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    wrong = tuple[int, int]
    monkeypatch.setattr(provider, "OUTPUT", wrong)
    monkeypatch.setattr(module, "BASE", wrong)
    monkeypatch.setattr(module, "OUTPUT", wrong | str)
    monkeypatch.setattr(consumer, "OUTPUT", module.OUTPUT)
    assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._source_facade_runtime_projection(root, closure)


def test_native_type_metadata_never_calls_fake_alias_or_type_operators(tmp_path, monkeypatch):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _native_type_source())
    expected = _native_type_expected(root, module)
    observed = []

    class UnknownAlias:
        def __getattribute__(self, name):
            observed.append(name)
            raise AssertionError("unknown alias getter must not run")

        def __eq__(self, _other):
            observed.append("equality")
            return True

        def __hash__(self):
            observed.append("hash")
            return 1

    assert not ledger._source_resolved_annotation_matches(UnknownAlias(), expected)

    class UnknownMeta(type):
        def __or__(cls, _other):
            observed.append("or")
            return object

        def __getitem__(cls, _other):
            observed.append("getitem")
            return object

    class UnknownType(metaclass=UnknownMeta):
        pass

    monkeypatch.setattr(module, "Choice", UnknownType)
    assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    monkeypatch.setattr(module, "tuple", UnknownType, raising=False)
    assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    assert observed == []


@pytest.mark.parametrize(
    "expression",
    [
        "list[str]",
        "Callable[..., object]",
        "Callable['args', object]",
        "tuple[unexecuted()]",
        "OUTPUT | str",
    ],
)
def test_native_type_metadata_profile_refuses_unsupported_factories_strings_and_cycles(
    tmp_path, monkeypatch, expression
):
    source = _native_type_source()
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    observed = []
    monkeypatch.setattr(module, "unexecuted", lambda: observed.append("call"), raising=False)
    Path(module.__file__).write_text(
        source.replace(
            "OUTPUT = CALL | tuple[str, CALL | Choice] | Choice", f"OUTPUT = {expression}"
        ),
        encoding="utf-8",
    )
    assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    with pytest.raises(ledger.ConfidenceLedgerError, match="side-effecting direct source"):
        _route(root, module, "OUTPUT")
    assert observed == []


@pytest.mark.parametrize("count", [63, 64])
def test_native_type_metadata_name_budget_refuses_whole_expression(tmp_path, monkeypatch, count):
    expression = "tuple[" + ", ".join("int" for _ in range(count)) + "]"
    root, module = _load_decorated_case(tmp_path, monkeypatch, _native_type_source(expression))
    # The constructor reference consumes one resolution as well as every arg.
    expected = _native_type_expected(root, module)
    if count == 63:
        assert type(expected) is ledger._SourceResolvedAnnotation
        assert ledger._source_resolved_annotation_matches(module.OUTPUT, expected)
    else:
        assert expected is ledger._SOURCE_DERIVATION_FAILED


@pytest.mark.parametrize("target", ["spec", "source_code", "source_bytes"])
def test_native_type_metadata_provider_refuses_unbound_backend_without_callbacks(
    monkeypatch, target
):
    provider = sys.modules["_collections_abc"]
    observed = []

    class UnknownSpec:
        def __getattribute__(self, name):
            observed.append(name)
            raise AssertionError("unknown spec getter must not run")

    with monkeypatch.context() as changed:
        if target == "spec":
            changed.setitem(vars(provider), "__spec__", UnknownSpec())
        elif target == "source_code":
            method = vars(vars(provider)["_CallableGenericAlias"])["__new__"].__func__

            def replacement():
                __class__ = object

                def wrong(cls, origin, args):
                    return __class__

                return wrong

            changed.setattr(method, "__code__", replacement().__code__)
        else:
            path = Path(provider.__file__).resolve()
            original = Path.read_bytes
            source = original(path)
            corrupt = source.replace(
                b"return super().__new__(cls, origin, args)", b"return None", 1
            )
            assert corrupt != source
            changed.setattr(
                Path, "read_bytes", lambda self: corrupt if self == path else original(self)
            )
        assert ledger._native_type_metadata_provider() is None
    assert observed == []


def test_native_type_metadata_union_dedup_is_semantic_but_selected_state_is_ordered(
    tmp_path, monkeypatch
):
    root, module = _load_decorated_case(
        tmp_path, monkeypatch, _native_type_source("tuple[str | int] | tuple[int | str]")
    )
    expected = _native_type_expected(root, module)
    assert type(expected) is ledger._SourceResolvedAnnotation
    assert ledger._source_resolved_annotation_matches(module.OUTPUT, expected)
    assert type(module.OUTPUT) is types.GenericAlias
    consumer, closure = _immutable_tuple_consumer(root, module, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    wrong = tuple[int | str]
    monkeypatch.setattr(module, "OUTPUT", wrong)
    monkeypatch.setattr(consumer, "OUTPUT", wrong)
    with pytest.raises(ledger.ConfidenceLedgerError, match="selected source type metadata differs"):
        ledger._source_facade_runtime_projection(root, closure)


def test_native_type_metadata_rejects_python_union_slot_lookalike_in_both_profiles(
    tmp_path, monkeypatch
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _native_type_source("str | int"))
    consumer, closure = _immutable_tuple_consumer(root, module, monkeypatch)
    legacy = ledger._SourceResolvedAnnotation((str, int))

    class FakeUnion:
        __slots__ = ("__args__",)

    forged = FakeUnion()
    forged.__args__ = (str, int)
    with monkeypatch.context() as changed:
        changed.setattr(types, "UnionType", FakeUnion)
        changed.setattr(typing, "Union", FakeUnion)
        changed.setattr(module, "OUTPUT", forged)
        changed.setattr(consumer, "OUTPUT", forged)
        assert ledger._native_union_witness() is None
        assert ledger._native_type_metadata_provider() is None
        assert not ledger._source_resolved_annotation_matches(forged, legacy)
        with pytest.raises(ledger.ConfidenceLedgerError):
            ledger._source_facade_runtime_projection(root, closure)


def test_native_type_metadata_legacy_matcher_never_calls_counterfeit_descriptor(monkeypatch):
    observed = []

    class FakeDescriptor:
        def __get__(self, _instance, _owner):
            observed.append("descriptor")
            return (str, int)

    class FakeUnion:
        pass

    descriptor = FakeDescriptor()
    descriptor.__objclass__ = FakeUnion
    FakeUnion.__args__ = descriptor
    with monkeypatch.context() as changed:
        changed.setattr(types, "UnionType", FakeUnion)
        changed.setattr(types, "MemberDescriptorType", FakeDescriptor)
        assert not ledger._source_resolved_annotation_matches(
            FakeUnion(), ledger._SourceResolvedAnnotation((str, int))
        )
    assert observed == []


@pytest.mark.parametrize("imported", [False, True])
def test_native_type_metadata_injected_builtin_class_has_no_native_provenance(
    tmp_path, monkeypatch, imported
):
    fake = type("Fake", (), {"__module__": "builtins"})
    monkeypatch.setitem(vars(builtins), "Fake", fake)
    extra = "from builtins import Fake\n" if imported else ""
    root, module = _load_decorated_case(
        tmp_path, monkeypatch, _native_type_source("Fake | str", extra=extra)
    )
    assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    _consumer, closure = _immutable_tuple_consumer(root, module, monkeypatch)
    with pytest.raises(ledger.ConfidenceLedgerError, match="side-effecting direct source"):
        ledger._source_facade_runtime_projection(root, closure)


def test_native_type_metadata_builtin_rebinding_does_not_change_the_source_witness(
    tmp_path, monkeypatch
):
    root, module = _load_decorated_case(
        tmp_path,
        monkeypatch,
        _native_type_source("Blob | str", extra="from builtins import bytes as Blob\n"),
    )
    assert type(_native_type_expected(root, module)) is ledger._SourceResolvedAnnotation
    fake = type("bytes", (), {"__module__": "builtins"})
    with monkeypatch.context() as changed:
        changed.setitem(vars(builtins), "bytes", fake)
        changed.setattr(module, "Blob", fake)
        assert not ledger._native_builtin_type("bytes", fake)
        assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED


@pytest.mark.parametrize("missing", ["absent", "nonmodule"])
def test_native_type_metadata_missing_frozen_importer_never_matches_none_loader(
    monkeypatch, missing
):
    provider = sys.modules["_collections_abc"]
    with monkeypatch.context() as changed:
        changed.setattr(provider.__spec__, "loader", None)
        if missing == "absent":
            changed.delitem(sys.modules, "_frozen_importlib")
        else:
            changed.setitem(sys.modules, "_frozen_importlib", object())
        assert ledger._native_type_metadata_provider() is None


def test_native_type_metadata_does_not_claim_frozen_loader_implementation_or_history(monkeypatch):
    provider = sys.modules["_collections_abc"]
    importer_module = sys.modules["_frozen_importlib"]
    observed = []

    class UnverifiedImporter:
        @classmethod
        def exec_module(cls, _module):
            observed.append("execute")
            raise AssertionError("loader execution is outside this metadata proof")

    with monkeypatch.context() as changed:
        changed.setattr(importer_module, "FrozenImporter", UnverifiedImporter)
        changed.setattr(provider.__spec__, "loader", UnverifiedImporter)
        state = ledger._native_type_metadata_provider()
        assert state is not None
        assert state.projection["frozen_loader_implementation"] == "supported_backend_assumption"
        assert state.projection["loader_execution_and_history"] == "not_established"
        assert (
            "callable_codeobjects_and_closures_against_stdlib_bytes"
            in state.projection["verified_facets"]
        )
    assert observed == []


def _protocol_type_source(expression="Callable[[], Contract]"):
    return (
        "from __future__ import annotations\n"
        "from collections.abc import Callable\n"
        "from typing import Protocol, runtime_checkable\n\n"
        "@runtime_checkable\nclass Contract(Protocol):\n"
        "    @property\n    def name(self) -> str:\n        ...\n"
        "    def make(self) -> object:\n        ...\n"
        f"OUTPUT = {expression}\n"
    )


def test_native_type_metadata_binds_actual_component_factory_protocol():
    from polisyos.core.components import protocols

    root = ledger._loaded_policy_engine_root()
    expected = _native_type_expected(root, protocols, "ComponentFactory")
    assert type(expected) is ledger._SourceResolvedAnnotation
    assert ledger._source_resolved_annotation_matches(protocols.ComponentFactory, expected)
    assert protocols.ComponentFactory.__args__ == (protocols.Component,)
    assert _route(root, protocols, "ComponentFactory") == (
        "symbol",
        protocols.__name__,
        "ComponentFactory",
    )


@pytest.mark.parametrize("route_kind", ["local", "imported", "reexported"])
def test_native_type_metadata_protocol_reference_reaches_selected_reader(
    tmp_path, monkeypatch, route_kind
):
    root, provider = _load_decorated_case(tmp_path, monkeypatch, _protocol_type_source())
    module = provider
    if route_kind != "local":
        source_name = provider.__name__
        if route_kind == "reexported":
            facade = _load_fixture_module(
                root,
                monkeypatch,
                "polisyos.protocol_facade",
                f"from {provider.__name__} import Contract\n",
            )
            source_name = facade.__name__
        module = _load_fixture_module(
            root,
            monkeypatch,
            "polisyos.protocol_alias_consumer",
            "from __future__ import annotations\nfrom collections.abc import Callable\n"
            f"from {source_name} import Contract as Selected\n"
            "OUTPUT = Callable[[], Selected] | tuple[str, Callable[[int], Selected]]\n",
        )
    expected = _native_type_expected(root, module)
    assert type(expected) is ledger._SourceResolvedAnnotation
    assert ledger._source_resolved_annotation_matches(module.OUTPUT, expected)
    assert _route(root, module, "OUTPUT") == ("symbol", module.__name__, "OUTPUT")
    consumer, closure = _immutable_tuple_consumer(root, module, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    assert consumer.observed() is module.OUTPUT


@pytest.mark.parametrize(
    "mutation", ["foreign", "member_code", "withdrawn", "runtime_flag", "annotations"]
)
def test_native_type_metadata_protocol_reference_requires_current_source_owner(
    tmp_path, monkeypatch, mutation
):
    from collections.abc import Callable

    root, module = _load_decorated_case(tmp_path, monkeypatch, _protocol_type_source())
    expected = _native_type_expected(root, module)
    assert type(expected) is ledger._SourceResolvedAnnotation
    consumer, closure = _immutable_tuple_consumer(root, module, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    if mutation == "foreign":
        foreign = _load_fixture_module(
            root,
            monkeypatch,
            "polisyos.foreign_protocol",
            _protocol_type_source().replace("        ...\nOUTPUT", "        return 99\nOUTPUT"),
        ).Contract
        assert foreign.make(None) == 99
        foreign.__module__ = module.__name__
        foreign.__qualname__ = "Contract"
        foreign.make.__module__ = module.__name__
        foreign.make.__qualname__ = "Contract.make"
        monkeypatch.setattr(module, "Contract", foreign)
        wrong = Callable[[], foreign]
        monkeypatch.setattr(module, "OUTPUT", wrong)
        monkeypatch.setattr(consumer, "OUTPUT", wrong)
    elif mutation == "member_code":
        monkeypatch.setattr(module.Contract.make, "__code__", (lambda self: 99).__code__)
        assert module.Contract.make(None) == 99
    elif mutation == "withdrawn":
        monkeypatch.delattr(module, "Contract")
    elif mutation == "runtime_flag":
        monkeypatch.setattr(module.Contract, "_is_runtime_protocol", False)
    else:
        monkeypatch.setattr(module.Contract.make, "__annotations__", {"return": "str"})
    assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    with pytest.raises(ledger.ConfidenceLedgerError, match="side-effecting direct source"):
        ledger._source_facade_runtime_projection(root, closure)


def test_native_type_metadata_protocol_reference_does_not_call_protocol_members(
    tmp_path, monkeypatch
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _protocol_type_source())
    observed = []
    member_codes = (module.Contract.make.__code__, module.Contract.name.fget.__code__)

    def observed_member_call(frame, event, _argument):
        if event == "call" and any(frame.f_code is code for code in member_codes):
            observed.append(frame.f_code.co_name)

    prior = sys.getprofile()
    try:
        sys.setprofile(observed_member_call)
        expected = _native_type_expected(root, module)
    finally:
        sys.setprofile(prior)
    assert type(expected) is ledger._SourceResolvedAnnotation
    assert observed == []
    assert ledger._source_resolved_annotation_matches(module.OUTPUT, expected)
    profile = ledger._native_type_metadata_provider_projection()
    assert profile["initialization_construction_and_behavior"] == "not_established"


def test_native_type_metadata_protocol_reference_rejects_corrupt_provider_before_replay(
    tmp_path, monkeypatch
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _protocol_type_source())
    with monkeypatch.context() as changed:
        changed.setattr(typing.runtime_checkable, "__code__", (lambda cls: cls).__code__)
        assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED


def test_native_type_metadata_protocol_reference_rechecks_source_snapshot(tmp_path, monkeypatch):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _protocol_type_source())
    assert type(_native_type_expected(root, module)) is ledger._SourceResolvedAnnotation
    source = Path(module.__file__)
    source.write_text(
        source.read_text().replace("def make(self) -> object", "def make(self) -> str")
    )
    assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED


def test_protocol_type_projection_never_dispatches_typing_or_member_callbacks():
    """The real context-backed Protocol can be inspected with zero replay calls."""
    import contextlib

    from polisyos.core.artifacts import protocol

    root = ledger._loaded_policy_engine_root()
    path = Path(protocol.__file__).resolve()
    tree = ast.parse(path.read_bytes(), filename=str(path))
    name = "CoreJSONArtifactBoundedMemberAttempt"
    node = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == name)
    meta = type(typing.Protocol)
    watched = [
        typing.runtime_checkable.__code__,
        vars(meta)["__new__"].__func__.__code__,
        vars(meta)["__init__"].__code__,
        vars(contextlib.AbstractContextManager)["__enter__"].__code__,
        vars(contextlib.AbstractContextManager)["__exit__"].__code__,
    ]
    for cls in (
        protocol.CoreJSONArtifactBoundedMemberAttempt,
        protocol.CoreJSONArtifactBoundedMemberStream,
    ):
        for value in vars(cls).values():
            if type(value) is property:
                value = value.fget
            if type(value) is types.FunctionType and value.__module__ == protocol.__name__:
                watched.append(value.__code__)
                if type(value.__annotate__) is types.FunctionType:
                    watched.append(value.__annotate__.__code__)
    observed = []

    def profile(frame, event, _argument):
        if event == "call" and any(frame.f_code is code for code in watched):
            observed.append(frame.f_code.co_qualname)

    prior = sys.getprofile()
    try:
        sys.setprofile(profile)
        supported = ledger._source_python_protocol_binding_supported(
            root, protocol.__name__, name, path.relative_to(root), tree, node
        )
    finally:
        sys.setprofile(prior)
    assert supported
    assert observed == []


@pytest.mark.parametrize("field", ["__bases__", "__dict__", "__mro__", "__module__"])
def test_protocol_provider_refuses_hostile_metaclass_fields_without_callbacks(monkeypatch, field):
    import abc

    observed = []
    armed = [False]

    def poisonous(cls):
        if not armed[0]:
            name = "__dict__" if field == "__module__" else field
            value = type.__dict__[name].__get__(cls, type(cls))
            return value.get("__module__") if field == "__module__" else value
        observed.append(field)
        raise AssertionError("untrusted metaclass data descriptor was invoked")

    namespace = {"__module__": "typing", field: property(poisonous)}
    meta = type("_ProtocolMeta", (abc.ABCMeta,), namespace)
    fake = meta("Protocol", (typing.Generic,), {"__module__": "typing"})
    with monkeypatch.context() as changed:
        changed.setitem(vars(typing), "_ProtocolMeta", meta)
        changed.setitem(vars(typing), "Protocol", fake)
        observed.clear()
        armed[0] = True
        with pytest.raises(ledger.ConfidenceLedgerError):
            ledger._typing_protocol_provider_projection()
        assert observed == []


@pytest.mark.parametrize("field", ["__name__", "__qualname__"])
def test_protocol_type_metadata_refuses_hostile_string_subclasses(tmp_path, monkeypatch, field):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _protocol_type_source())
    observed = []

    class HostileName(str):
        def __eq__(self, _other):
            observed.append("comparison")
            raise AssertionError("untrusted string comparison was invoked")

    original = type.__dict__[field].__get__(module.Contract, type(module.Contract))
    type.__setattr__(module.Contract, field, HostileName(original))
    try:
        assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
        assert observed == []
    finally:
        type.__setattr__(module.Contract, field, original)


@pytest.mark.parametrize("kind", ["changed_cache", "aliased_cache", "poisoned_thunk"])
def test_protocol_type_metadata_refuses_poisoned_annotation_storage_without_callbacks(
    tmp_path, monkeypatch, kind
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _protocol_type_source())
    function = module.Contract.make
    observed = []
    if kind == "changed_cache":
        function.__annotations__["return"] = "str"
    elif kind == "aliased_cache":
        function.__annotations__ = function.__dict__
    else:

        def poison(_format):
            observed.append("annotation thunk")
            raise AssertionError("untrusted annotation thunk was called")

        monkeypatch.setattr(function, "__annotate__", poison)
    assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    assert observed == []


def test_protocol_type_metadata_refuses_colliding_owner_key_without_callbacks(
    tmp_path, monkeypatch
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _protocol_type_source())
    observed = []

    class CollidingKey:
        def __hash__(self):
            return hash("Contract")

        def __eq__(self, _other):
            observed.append("equality")
            raise AssertionError("untrusted key equality was invoked")

    key = CollidingKey()
    # Permit constructing the adversarial dict, then arm its comparator.
    original_eq = CollidingKey.__eq__
    CollidingKey.__eq__ = lambda self, other: False
    module.__dict__[key] = object()
    CollidingKey.__eq__ = original_eq
    try:
        assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
        assert observed == []
    finally:
        CollidingKey.__eq__ = lambda self, other: False
        del module.__dict__[key]


def test_protocol_context_base_refuses_poisoned_generic_getitem_without_calling_it(monkeypatch):
    import contextlib

    from polisyos.core.artifacts import protocol

    root = ledger._loaded_policy_engine_root()
    path = Path(protocol.__file__).resolve()
    tree = ast.parse(path.read_bytes(), filename=str(path))
    name = "CoreJSONArtifactBoundedMemberAttempt"
    node = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == name)
    observed = []

    def poison(_cls, _item):
        observed.append("generic alias")
        raise AssertionError("untrusted generic construction was called")

    with monkeypatch.context() as changed:
        changed.setattr(contextlib.AbstractContextManager, "__class_getitem__", classmethod(poison))
        assert not ledger._source_python_protocol_binding_supported(
            root, protocol.__name__, name, path.relative_to(root), tree, node
        )
        assert observed == []


def test_protocol_context_base_refuses_changed_generic_argument(monkeypatch):
    import contextlib

    from polisyos.core.artifacts import protocol

    root = ledger._loaded_policy_engine_root()
    path = Path(protocol.__file__).resolve()
    tree = ast.parse(path.read_bytes(), filename=str(path))
    name = "CoreJSONArtifactBoundedMemberAttempt"
    node = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == name)
    wrong = contextlib.AbstractContextManager[protocol.ArtifactReader]
    monkeypatch.setattr(
        protocol.CoreJSONArtifactBoundedMemberAttempt, "__orig_bases__", (wrong, typing.Protocol)
    )
    assert not ledger._source_python_protocol_binding_supported(
        root, protocol.__name__, name, path.relative_to(root), tree, node
    )


def test_protocol_provider_rejects_coherently_poisoned_source_without_executing_it(
    tmp_path, monkeypatch
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _protocol_type_source())
    provider = Path(typing.__file__).resolve()
    read_bytes = Path.read_bytes
    source = read_bytes(provider)
    effect = tmp_path / "provider-effect"
    changed = source.replace(
        b"def runtime_checkable(cls):\n",
        f"def runtime_checkable(cls):\n    open({str(effect)!r}, 'w').close()\n".encode(),
        1,
    )
    assert changed != source
    code = next(
        value
        for value in ledger._python_provider_source_code_objects(changed, str(provider))
        if value.co_qualname == "runtime_checkable"
    )
    with monkeypatch.context() as patcher:
        patcher.setattr(
            Path, "read_bytes", lambda path: changed if path == provider else read_bytes(path)
        )
        patcher.setattr(typing.runtime_checkable, "__code__", code)
        with pytest.raises(ledger.ConfidenceLedgerError, match="typing provider source"):
            ledger._typing_protocol_provider_projection()
        assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
        assert not effect.exists()


def test_protocol_class_base_matching_never_compares_hostile_classes():
    observed = []

    class HostileMeta(type):
        def __eq__(cls, _other):
            observed.append("class equality")
            raise AssertionError("untrusted class equality was invoked")

        __hash__ = type.__hash__

    class Foreign(metaclass=HostileMeta):
        pass

    class Candidate(Foreign):
        pass

    assert not ledger._source_native_class_bases_match(Candidate, object)
    assert observed == []


def test_protocol_context_base_refuses_hostile_slots_without_comparison(monkeypatch):
    import contextlib

    from polisyos.core.artifacts import protocol

    root = ledger._loaded_policy_engine_root()
    path = Path(protocol.__file__).resolve()
    tree = ast.parse(path.read_bytes(), filename=str(path))
    name = "CoreJSONArtifactBoundedMemberAttempt"
    node = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == name)
    observed = []

    class HostileSlots:
        def __eq__(self, _other):
            observed.append("comparison")
            raise AssertionError("untrusted slots comparison was invoked")

    monkeypatch.setattr(contextlib.AbstractContextManager, "__slots__", HostileSlots())
    assert not ledger._source_python_protocol_binding_supported(
        root, protocol.__name__, name, path.relative_to(root), tree, node
    )
    assert observed == []


def test_protocol_type_metadata_refuses_hostile_gc_module_name_without_comparison(
    tmp_path, monkeypatch
):
    import gc

    root, module = _load_decorated_case(tmp_path, monkeypatch, _protocol_type_source())
    observed = []

    class HostileName(str):
        def __eq__(self, _other):
            observed.append("comparison")
            raise AssertionError("untrusted builtin metadata comparison was invoked")

    getter = gc.get_referents
    original = getter.__module__
    getter.__module__ = HostileName("gc")
    try:
        assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
        assert observed == []
    finally:
        getter.__module__ = original


@pytest.mark.parametrize("field", ["provider_member", "function_doc", "class_doc"])
def test_protocol_type_metadata_never_compares_untrusted_metadata_types(
    tmp_path, monkeypatch, field
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _protocol_type_source())
    observed = []

    class HostileMeta(type):
        def __eq__(cls, _other):
            observed.append("metaclass equality")
            raise AssertionError("untrusted metadata type was compared")

        __hash__ = type.__hash__

    class Hostile(metaclass=HostileMeta):
        pass

    value = Hostile()
    with monkeypatch.context() as patcher:
        if field == "provider_member":
            patcher.setitem(vars(typing), "_proto_hook", value)
            with pytest.raises(ledger.ConfidenceLedgerError):
                ledger._typing_protocol_provider_projection()
        else:
            target = module.Contract.make if field == "function_doc" else module.Contract
            patcher.setattr(target, "__doc__", value)
            assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
        assert observed == []


def test_protocol_type_metadata_refuses_hostile_doc_constant_without_comparison(
    tmp_path, monkeypatch
):
    source = _protocol_type_source().replace(
        "def make(self) -> object:\n        ...",
        'def make(self) -> object:\n        """A source-owned result."""\n        ...',
    )
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    assert type(_native_type_expected(root, module)) is ledger._SourceResolvedAnnotation
    observed = []

    class Hostile:
        def __eq__(self, _other):
            observed.append("constant comparison")
            raise AssertionError("untrusted code constant was compared")

    function = module.Contract.make
    old = function.__code__
    monkeypatch.setattr(
        function, "__code__", old.replace(co_consts=(Hostile(), *old.co_consts[1:]))
    )
    assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED
    assert observed == []


@pytest.mark.parametrize("field", ["__orig_bases__", "__init__", "__annotate_func__"])
def test_protocol_type_metadata_does_not_treat_stored_sentinel_as_absence(
    tmp_path, monkeypatch, field
):
    root, module = _load_decorated_case(tmp_path, monkeypatch, _protocol_type_source())
    assert type(_native_type_expected(root, module)) is ledger._SourceResolvedAnnotation
    monkeypatch.setattr(module.Contract, field, ledger._NO_EXECUTION_BINDING, raising=False)
    assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED


def test_protocol_provider_rejects_stored_sentinel_shadowing_builtin(monkeypatch):
    monkeypatch.setitem(vars(typing), "getattr", ledger._NO_EXECUTION_BINDING)
    with pytest.raises(ledger.ConfidenceLedgerError, match="typing global"):
        ledger._typing_protocol_provider_projection()


@pytest.mark.parametrize(
    "field", ["allowlist", "helper_code", "helper_defaults", "abc_alias", "wrapper_metadata"]
)
def test_protocol_provider_binds_current_direct_globals_without_calling_them(monkeypatch, field):
    initial = ledger._typing_protocol_provider_projection()
    observed = []

    def forbidden(*_args, **_kwargs):
        observed.append(field)
        raise AssertionError("provider value must not be called by its projection")

    with monkeypatch.context() as changed:
        if field == "allowlist":
            changed.setitem(typing._PROTO_ALLOWLIST, "contextlib", ["NotTheContextManager"])
        elif field == "helper_code":
            changed.setattr(
                typing._allow_reckless_class_checks, "__code__", (lambda depth=2: False).__code__
            )
        elif field == "helper_defaults":
            changed.setattr(typing._allow_reckless_class_checks, "__defaults__", (3,))
        elif field == "abc_alias":
            changed.setitem(vars(typing), "_abc_instancecheck", forbidden)
        else:
            changed.setitem(vars(typing._lazy_load_getattr_static), "__name__", "changed_wrapper")
        try:
            after = ledger._typing_protocol_provider_projection()
        except ledger.ConfidenceLedgerError:
            pass
        else:
            assert (
                after["runtime_direct_globals_sha256"] != initial["runtime_direct_globals_sha256"]
            )
        assert observed == []
    assert ledger._typing_protocol_provider_projection() == initial


def test_protocol_provider_tracks_builtin_metadata_without_comparison():
    initial = ledger._typing_protocol_provider_projection()
    getter = builtins.getattr
    original = getter.__module__
    observed = []

    class HostileName(str):
        def __eq__(self, _other):
            observed.append("comparison")
            raise AssertionError("untrusted builtin metadata was compared")

    getter.__module__ = HostileName("builtins")
    try:
        with pytest.raises(ledger.ConfidenceLedgerError, match="typing global builtin"):
            ledger._typing_protocol_provider_projection()
        assert observed == []
    finally:
        getter.__module__ = original
    assert ledger._typing_protocol_provider_projection() == initial


def test_protocol_provider_projection_shares_work_budget_across_code_and_metadata():
    def selected():
        return None

    with pytest.raises(ledger.ConfidenceLedgerError, match="budget"):
        ledger._source_passive_provider_value([selected], budget=[6, 1024**2])
    with pytest.raises(ledger.ConfidenceLedgerError, match="budget"):
        ledger._source_passive_provider_value({"key": None}, budget=[10, 4])
    with pytest.raises(ledger.ConfidenceLedgerError, match="budget"):
        ledger._source_passive_provider_value(selected, budget=[10000, 1])
    with pytest.raises(ledger.ConfidenceLedgerError, match="budget"):
        ledger._source_passive_builtin_value(builtins.getattr, budget=[10000, 1])


def test_protocol_provider_binds_abc_source_and_loader_origin_without_callbacks(monkeypatch):
    import abc

    initial = ledger._typing_protocol_provider_projection()
    source_path = Path(abc.__file__).resolve()
    original_read = Path.read_bytes
    source = original_read(source_path)
    changed_source = source.replace(
        b"        def __instancecheck__(cls, instance):",
        b"        def __instancecheck__(cls, instance):\n            return False",
        1,
    )
    assert changed_source != source
    with monkeypatch.context() as changed:
        changed.setattr(
            Path,
            "read_bytes",
            lambda path: changed_source if path == source_path else original_read(path),
        )
        with pytest.raises(ledger.ConfidenceLedgerError, match="abc provider source"):
            ledger._typing_protocol_provider_projection()
    observed = []

    class HostileOrigin(str):
        def __eq__(self, _other):
            observed.append("comparison")
            raise AssertionError("untrusted origin was compared")

    with monkeypatch.context() as changed:
        changed.setattr(abc.__spec__, "origin", HostileOrigin("frozen"))
        with pytest.raises(ledger.ConfidenceLedgerError, match="abc provider origin"):
            ledger._typing_protocol_provider_projection()
        assert observed == []
    assert ledger._typing_protocol_provider_projection() == initial


def test_protocol_provider_detects_abc_source_drift_during_one_integrity_pass(monkeypatch):
    import abc

    source_path = Path(abc.__file__).resolve()
    original_read = Path.read_bytes
    reads = []

    def changing(path):
        value = original_read(path)
        if path == source_path:
            reads.append(1)
            if len(reads) > 1:
                return value + b"\n# source changed during integrity check\n"
        return value

    monkeypatch.setattr(Path, "read_bytes", changing)
    with pytest.raises(ledger.ConfidenceLedgerError, match="source changed"):
        ledger._typing_protocol_provider_projection()
    assert len(reads) >= 2


def test_native_type_metadata_binds_actual_registry_annotated_alias():
    from polisyos.ir.registry import registry_fragments

    root = ledger._loaded_policy_engine_root()
    expected = _native_type_expected(root, registry_fragments, "RegistryFragment")
    assert type(expected) is ledger._SourceResolvedAnnotation
    assert ledger._source_resolved_annotation_matches(registry_fragments.RegistryFragment, expected)
    assert _route(root, registry_fragments, "RegistryFragment") == (
        "symbol",
        registry_fragments.__name__,
        "RegistryFragment",
    )
    profile = ledger._native_type_metadata_provider_projection()
    assert profile["pydantic_compiled_validator_schema_coherence"] == "not_established"


def test_native_annotated_fieldinfo_binds_full_actual_registry_metadata():
    from polisyos.ir.registry import registry_fragments

    field = vars(registry_fragments.RegistryFragment)["__metadata__"][0]
    analysis = ledger._IntegrityAnalysisContext()
    assert ledger._source_pydantic_discriminator_field_matches(field, "kind", analysis)
    analysis.assert_sources_unchanged()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("alias", "forged"),
        ("validation_alias", "forged"),
        ("default", 7),
        ("metadata", ["forged"]),
        ("_attributes_set", {"discriminator": "kind", "alias": "forged"}),
        ("_qualifiers", {"forged"}),
        ("_complete", False),
        ("_final", True),
    ],
)
def test_native_annotated_fieldinfo_rejects_other_metadata_tampering(monkeypatch, name, value):
    from polisyos.ir.registry import registry_fragments

    field = vars(registry_fragments.RegistryFragment)["__metadata__"][0]
    monkeypatch.setattr(field, name, value)
    analysis = ledger._IntegrityAnalysisContext()
    assert not ledger._source_pydantic_discriminator_field_matches(field, "kind", analysis)
    analysis.assert_sources_unchanged()


def test_native_annotated_source_reaches_real_selected_reader(tmp_path, monkeypatch):
    source = (
        "from typing import Annotated\n"
        "from pydantic import Field\n"
        "OUTPUT = Annotated[tuple[str, int], Field(discriminator='kind')]\n"
    )
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    expected = _native_type_expected(root, module)
    assert type(expected) is ledger._SourceResolvedAnnotation
    assert ledger._source_resolved_annotation_matches(module.OUTPUT, expected)
    assert _route(root, module, "OUTPUT") == ("symbol", module.__name__, "OUTPUT")
    consumer, closure = _immutable_tuple_consumer(root, module, monkeypatch)
    ledger._source_facade_runtime_projection(root, closure)
    assert consumer.observed() is module.OUTPUT


@pytest.mark.parametrize("mutation", ["origin", "discriminator", "alias", "metadata"])
def test_native_annotated_rejects_wrong_semantics_without_callbacks(
    tmp_path, monkeypatch, mutation
):
    from typing import Annotated

    from pydantic import Field

    source = (
        "from typing import Annotated\n"
        "from pydantic import Field\n"
        "OUTPUT = Annotated[tuple[str, int], Field(discriminator='kind')]\n"
    )
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    expected = _native_type_expected(root, module)
    assert type(expected) is ledger._SourceResolvedAnnotation
    calls = []

    class Poison:
        def __eq__(self, other):
            calls.append("eq")
            raise AssertionError("metadata equality executed")

    if mutation == "origin":
        actual = Annotated[tuple[str, str], Field(discriminator="kind")]
    elif mutation == "discriminator":
        actual = Annotated[tuple[str, int], Field(discriminator="other")]
    else:
        actual = module.OUTPUT
        field = vars(actual)["__metadata__"][0]
        monkeypatch.setattr(field, mutation, Poison() if mutation == "alias" else [Poison()])
    assert not ledger._source_resolved_annotation_matches(actual, expected)
    assert calls == []


def test_native_annotated_projection_does_not_execute_providers(tmp_path, monkeypatch):
    import sys
    import typing

    from pydantic.fields import FieldInfo

    source = (
        "from typing import Annotated\n"
        "from pydantic import Field\n"
        "OUTPUT = Annotated[tuple[str, int], Field(discriminator='kind')]\n"
    )
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    wrapped = typing.Annotated._getitem
    functions = (
        module.Field,
        FieldInfo.__init__,
        typing._AnnotatedAlias.__init__,
        typing._GenericAlias.__init__,
        wrapped,
        wrapped.__wrapped__,
    )
    code_ids = {id(function.__code__) for function in functions}
    observed = []

    def trace(frame, event, arg):
        if event == "call" and id(frame.f_code) in code_ids:
            observed.append(frame.f_code.co_qualname)

    previous = sys.getprofile()
    try:
        sys.setprofile(trace)
        expected = _native_type_expected(root, module)
        assert type(expected) is ledger._SourceResolvedAnnotation
        assert ledger._source_resolved_annotation_matches(module.OUTPUT, expected)
    finally:
        sys.setprofile(previous)
    assert observed == []


@pytest.mark.parametrize("provider", ["field", "alias_init"])
def test_native_annotated_rejects_poisoned_provider_without_calling_it(
    tmp_path, monkeypatch, provider
):
    import typing

    source = (
        "from typing import Annotated\n"
        "from pydantic import Field\n"
        "OUTPUT = Annotated[tuple[str, int], Field(discriminator='kind')]\n"
    )
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    expected = _native_type_expected(root, module)
    assert type(expected) is ledger._SourceResolvedAnnotation

    def poison(*args, **kwargs):
        raise AssertionError("provider executed")

    def make_closed_poison():
        marker = "provider executed"

        def poisoned(*args, **kwargs):
            raise AssertionError(marker)

        return poisoned

    function = module.Field if provider == "field" else typing._AnnotatedAlias.__init__
    replacement = poison if provider == "field" else make_closed_poison()
    assert len(function.__closure__ or ()) == len(replacement.__closure__ or ())
    monkeypatch.setattr(function, "__code__", replacement.__code__)
    assert not ledger._source_resolved_annotation_matches(module.OUTPUT, expected)


def test_native_annotated_registry_rebound_export_refused(monkeypatch):
    from polisyos.ir.registry import registry_fragments as fragments

    root = ledger._loaded_policy_engine_root()
    original_alias = fragments.RegistryFragment
    assert (
        type(_native_type_expected(root, fragments, "RegistryFragment"))
        is ledger._SourceResolvedAnnotation
    )
    monkeypatch.setattr(fragments, "UnitsFragment", fragments.TrustFragment)
    assert fragments.RegistryFragment is original_alias
    assert (
        _native_type_expected(root, fragments, "RegistryFragment")
        is ledger._SOURCE_DERIVATION_FAILED
    )


def test_native_annotated_registry_validator_behavior_is_not_type_identity(monkeypatch):
    from polisyos.ir.registry import registry_fragments as fragments

    root = ledger._loaded_policy_engine_root()
    monkeypatch.setattr(fragments.UnitsFragment, "__pydantic_validator__", object())
    expected = _native_type_expected(root, fragments, "RegistryFragment")
    assert type(expected) is ledger._SourceResolvedAnnotation
    assert ledger._source_resolved_annotation_matches(fragments.RegistryFragment, expected)
    assert (
        ledger._native_type_metadata_provider_projection()[
            "pydantic_compiled_validator_schema_coherence"
        ]
        == "not_established"
    )


def test_native_annotated_rejects_slot_replacement_between_provider_and_read(monkeypatch):
    from pydantic.fields import FieldInfo

    from polisyos.ir.registry import registry_fragments

    field = vars(registry_fragments.RegistryFragment)["__metadata__"][0]
    original = ledger._source_pydantic_fieldinfo_provider
    callbacks = []

    def hostile(instance):
        callbacks.append("property")
        raise AssertionError("property executed")

    def change_after_provider(analysis):
        provider = original(analysis)
        assert provider is not None
        monkeypatch.setattr(FieldInfo, "alias", property(hostile))
        return provider

    monkeypatch.setattr(ledger, "_source_pydantic_fieldinfo_provider", change_after_provider)
    assert not ledger._source_pydantic_discriminator_field_matches(
        field, "kind", ledger._IntegrityAnalysisContext()
    )
    assert callbacks == []


@pytest.mark.parametrize(
    ("field", "attribute", "replacement"),
    [
        ("kind", "default", "forged"),
        ("payload", "annotation", str),
    ],
)
def test_native_annotated_registry_field_state_drift_refused(
    monkeypatch, field, attribute, replacement
):
    from polisyos.ir.registry import registry_fragments as fragments

    root = ledger._loaded_policy_engine_root()
    current = vars(fragments.UnitsFragment)["__pydantic_fields__"][field]
    monkeypatch.setattr(current, attribute, replacement)
    assert (
        _native_type_expected(root, fragments, "RegistryFragment")
        is ledger._SOURCE_DERIVATION_FAILED
    )


def test_pydantic_model_provider_refuses_rebound_name_only_class(monkeypatch):
    import pydantic
    import pydantic.main

    class Forged(pydantic.BaseModel):
        def __init__(self, **kwargs):
            raise AssertionError("must not execute")

    Forged.__module__ = "pydantic.main"
    Forged.__qualname__ = "BaseModel"
    monkeypatch.setattr(pydantic, "BaseModel", Forged)
    monkeypatch.setattr(pydantic.main, "BaseModel", Forged)
    assert not ledger._source_pydantic_model_provider_matches(
        Forged, ledger._IntegrityAnalysisContext()
    )


def test_unloaded_annotated_route_is_only_a_closure_candidate(tmp_path, monkeypatch):
    source = (
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "from typing import Annotated\n"
        "from pydantic import Field\n"
        "@dataclass(frozen=True)\nclass A:\n    value: str\n"
        "@dataclass(frozen=True)\nclass B:\n    value: int\n"
        "OUTPUT = Annotated[A | B, Field(discriminator='kind')]\n"
    )
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    module_name = module.__name__
    monkeypatch.delitem(sys.modules, module_name)
    candidate = ledger._source_module_import_route_candidate(
        root,
        module_name,
        "OUTPUT",
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        discovery_only=True,
    )
    assert candidate.binding_basis == "source_expression"
    assert candidate.route == ("symbol", module_name, "OUTPUT")
    assert module_name not in sys.modules
    with pytest.raises(
        ledger.ConfidenceLedgerError, match="side-effecting direct source assignment"
    ):
        ledger._source_module_import_route(
            root,
            module_name,
            "OUTPUT",
            directory_entries={},
            source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        )
    monkeypatch.setitem(sys.modules, module_name, module)
    expected = _native_type_expected(root, module)
    assert type(expected) is ledger._SourceResolvedAnnotation
    assert ledger._source_resolved_annotation_matches(module.OUTPUT, expected)
    monkeypatch.setattr(module, "A", module.B)
    assert _native_type_expected(root, module) is ledger._SOURCE_DERIVATION_FAILED


def test_source_discovery_candidates_preserve_nested_edges_without_runtime_admission(
    tmp_path, monkeypatch
):
    source = (
        "from dataclasses import dataclass\n"
        "@dataclass(slots=True)\nclass A:\n    value: int\n"
        "def build():\n    return object()\n"
        "OUTPUT = build()\n"
        "ALIAS = OUTPUT\n"
    )
    root, provider = _load_decorated_case(tmp_path, monkeypatch, source)
    provider_name = provider.__name__
    bridge = "polisyos.discovery_bridge_fixture"
    (root / "src/polisyos/discovery_bridge_fixture.py").write_text(
        f"from {provider_name} import ALIAS\n", encoding="utf-8"
    )
    monkeypatch.delitem(sys.modules, provider_name)
    index = ledger._AuthorityImportClosureSourceIndex({}, {})
    for name in ("A", "OUTPUT"):
        candidate = ledger._source_module_import_route_candidate(
            root, provider_name, name, directory_entries={}, source_index=index, discovery_only=True
        )
        assert candidate.binding_basis == "source_expression"
        assert candidate.route == ("symbol", provider_name, name)
        with pytest.raises(ledger.ConfidenceLedgerError):
            ledger._source_module_import_route(
                root, provider_name, name, directory_entries={}, source_index=index
            )
    nested = ledger._source_module_import_route_candidate(
        root, bridge, "ALIAS", directory_entries={}, source_index=index, discovery_only=True
    )
    assert nested.route == ("symbol", provider_name, "OUTPUT")
    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._source_module_import_route(
            root, bridge, "ALIAS", directory_entries={}, source_index=index
        )
    assert provider_name not in sys.modules
    assert bridge not in sys.modules


def test_source_discovery_distinguishes_overload_stubs_from_rebinding(tmp_path, monkeypatch):
    source = (
        "from typing import overload\n"
        "@overload\ndef choose(value: int) -> int: ...\n"
        "@overload\ndef choose(value: str) -> str: ...\n"
        "def choose(value): return value\n"
        "def rebound(): return 1\n"
        "def rebound(): return 2\n"
    )
    root, module = _load_decorated_case(tmp_path, monkeypatch, source)
    module_name = module.__name__
    monkeypatch.delitem(sys.modules, module_name)
    census = set()
    index = ledger._AuthorityImportClosureSourceIndex({}, {}, census)
    candidate = ledger._source_module_import_route_candidate(
        root, module_name, "choose", directory_entries={}, source_index=index, discovery_only=True
    )
    assert candidate.binding_basis == "source_expression"
    assert candidate.route == ("symbol", module_name, "choose")
    assert (module_name, "choose") in census
    # A fresh non-diagnostic index keeps genuine source rebinding fail-closed.
    with pytest.raises(ledger.ConfidenceLedgerError, match="rebound direct source export"):
        ledger._source_module_import_route_candidate(
            root,
            module_name,
            "rebound",
            directory_entries={},
            source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
            discovery_only=True,
        )


def test_actual_optional_observability_class_uses_source_owned_provider():
    from polisyos.core import observability
    from polisyos.core.observability import metrics, metrics_parts

    assert observability.MetricsRegistry is metrics.MetricsRegistry is metrics_parts.MetricsRegistry
    assert _route(ledger._loaded_policy_engine_root(), observability, "MetricsRegistry") == (
        "symbol",
        metrics_parts.__name__,
        "MetricsRegistry",
    )


@pytest.fixture
def optional_class_case(tmp_path, monkeypatch):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    base = _load_fixture_module(
        root, monkeypatch, "polisyos.optional_class_base", "class Base:\n    pass\n"
    )
    provider = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.optional_class_provider",
        "from polisyos.optional_class_base import Base\n"
        "class Selected(Base):\n    def value(self): return 7\n",
    )
    facade = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.optional_class_facade",
        "try:\n    from polisyos.optional_class_provider import Selected\n"
        "except ModuleNotFoundError:\n    class Selected:\n        pass\n",
    )
    return root, base, provider, facade


def test_optional_class_route_binds_source_owned_class(optional_class_case):
    root, _base, provider, facade = optional_class_case
    assert facade.Selected is provider.Selected
    assert _route(root, facade, "Selected") == ("symbol", provider.__name__, "Selected")


@pytest.mark.parametrize("mutation", ["facade", "counterfeit", "base", "method"])
def test_optional_class_route_rejects_foreign_or_drifted_binding(
    optional_class_case, monkeypatch, mutation
):
    root, base, provider, facade = optional_class_case
    assert _route(root, facade, "Selected") == ("symbol", provider.__name__, "Selected")
    if mutation == "facade":
        monkeypatch.setattr(facade, "Selected", type("Selected", (), {}))
    elif mutation == "counterfeit":
        forged = type(
            "Selected", (base.Base,), {"__module__": provider.__name__, "value": lambda self: 7}
        )
        monkeypatch.setattr(provider, "Selected", forged)
        monkeypatch.setattr(facade, "Selected", forged)
    elif mutation == "base":
        monkeypatch.setattr(base, "Base", type("Base", (), {}))
    else:
        monkeypatch.setattr(provider.Selected, "value", lambda self: 7)
    with pytest.raises(ledger.ConfidenceLedgerError, match="unsupported direct source binding"):
        _route(root, facade, "Selected")


def test_optional_class_route_refuses_local_fallback(tmp_path, monkeypatch):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    facade = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.optional_class_fallback",
        "try:\n    from polisyos.optional_class_absent import Selected\n"
        "except ModuleNotFoundError:\n    class Selected:\n        pass\n",
    )
    with pytest.raises(ledger.ConfidenceLedgerError, match="unsupported direct source binding"):
        _route(root, facade, "Selected")


def test_optional_class_route_rejects_hostile_provider_spec_without_callbacks(
    optional_class_case, monkeypatch
):
    root, _base, provider, facade = optional_class_case
    calls = []

    class HostileSpec:
        loader = provider.__spec__.loader

        @property
        def origin(self):
            calls.append("origin")
            raise AssertionError("provider metadata executed")

    monkeypatch.setattr(provider, "__spec__", HostileSpec())
    with pytest.raises(ledger.ConfidenceLedgerError, match="unsupported direct source binding"):
        _route(root, facade, "Selected")
    assert calls == []


def test_optional_class_route_rejects_unrelated_extra_class_state(optional_class_case, monkeypatch):
    root, _base, provider, facade = optional_class_case
    monkeypatch.setattr(provider.Selected, "surprise", object(), raising=False)
    with pytest.raises(ledger.ConfidenceLedgerError, match="unsupported direct source binding"):
        _route(root, facade, "Selected")


def test_actual_optional_class_reference_refuses_wrong_singleton_type(monkeypatch):
    from polisyos.core import observability
    from polisyos.core.observability import metrics_parts

    root = ledger._loaded_policy_engine_root()
    owner = metrics_parts.MetricsRegistry
    monkeypatch.setattr(owner, "_instance", object.__new__(owner), raising=False)
    assert _route(root, observability, "MetricsRegistry") == (
        "symbol",
        metrics_parts.__name__,
        "MetricsRegistry",
    )
    for invalid in (object(), ledger._NO_EXECUTION_BINDING):
        monkeypatch.setattr(owner, "_instance", invalid)
        with pytest.raises(ledger.ConfidenceLedgerError, match="unsupported direct source binding"):
            _route(root, observability, "MetricsRegistry")


def test_optional_class_nested_cls_write_does_not_authorize_extra_state(tmp_path, monkeypatch):
    root, _unused = _load_decorated_case(tmp_path, monkeypatch, _SOURCE)
    _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.optional_nested_base",
        "class Base:\n    extra: object = None\n    def never(self):\n"
        "        def nested(cls): cls.extra = None\n        return nested\n",
    )
    provider = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.optional_nested_provider",
        "from polisyos.optional_nested_base import Base\n"
        "class Selected(Base):\n    def value(self): return 7\n",
    )
    facade = _load_fixture_module(
        root,
        monkeypatch,
        "polisyos.optional_nested_facade",
        "try:\n    from polisyos.optional_nested_provider import Selected\n"
        "except ModuleNotFoundError:\n    class Selected: pass\n",
    )
    assert _route(root, facade, "Selected") == ("symbol", provider.__name__, "Selected")
    monkeypatch.setattr(provider.Selected, "extra", None, raising=False)
    with pytest.raises(ledger.ConfidenceLedgerError, match="unsupported direct source binding"):
        _route(root, facade, "Selected")
