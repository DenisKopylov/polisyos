"""Source and live binding checks for immutable lazy facade maps."""

from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from polisyos.runtime.quality import confidence_ledger as ledger


@pytest.fixture
def security_facade_case(monkeypatch: pytest.MonkeyPatch):
    facade = importlib.import_module("polisyos.core.security")
    provider = importlib.import_module("polisyos.core.security.chronology_anchor")
    selected = {"parse_canonical_statement", "canonical_statement_bytes"}
    # The projection checks every cached export. Keep this test's closure limited
    # to the selected real provider, independent of unrelated test imports.
    for name in set(facade._EXPORTS) - selected:
        monkeypatch.delitem(vars(facade), name, raising=False)
    for name in selected:
        assert getattr(facade, name) is getattr(provider, name)
    root = ledger._loaded_policy_engine_root()
    closure = tuple(
        (module.__name__, Path(module.__file__).relative_to(root).as_posix())
        for module in (facade, provider)
    )
    return root, facade, provider, closure


def test_immutable_security_facade_binds_real_source_and_cached_owner(
    security_facade_case, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, facade, provider, closure = security_facade_case
    source_index = ledger._AuthorityImportClosureSourceIndex({}, {})
    for name in ("parse_canonical_statement", "canonical_statement_bytes"):
        candidate = ledger._source_module_import_route_candidate(
            root,
            facade.__name__,
            name,
            directory_entries={},
            source_index=source_index,
        )
        assert candidate.route == ("symbol", provider.__name__, name)
        assert candidate.binding_basis == "literal_getattr"
    references: list[ledger._FacadeRuntimeBindingReference] = []
    projection, _supplemental = ledger._source_facade_runtime_projection(
        root, closure, runtime_binding_references=references
    )
    rows = json.loads(projection)["facades"]
    assert rows[0]["maps"]["_EXPORTS"].keys() == {"$mappingproxy"}

    with monkeypatch.context() as changed:
        changed.setattr(facade, "_EXPORTS", dict(facade._EXPORTS))
        with pytest.raises(ledger.ConfidenceLedgerError, match="loaded facade map differs"):
            ledger._source_facade_runtime_projection(root, closure)
    with monkeypatch.context() as changed:
        wrong = dict(facade._EXPORTS)
        wrong["parse_canonical_statement"] = (
            provider.__name__,
            "canonical_statement_bytes",
        )
        changed.setattr(facade, "_EXPORTS", MappingProxyType(wrong))
        with pytest.raises(ledger.ConfidenceLedgerError, match="loaded facade map differs"):
            ledger._source_facade_runtime_projection(root, closure)
    with monkeypatch.context() as changed:

        class StringSubclass(str):
            armed = False

            def __hash__(self) -> int:
                if self.armed:
                    raise AssertionError("untrusted key hash called during comparison")
                return super().__hash__()

        wrong_keys = {StringSubclass(key): value for key, value in facade._EXPORTS.items()}
        StringSubclass.armed = True
        changed.setattr(facade, "_EXPORTS", MappingProxyType(wrong_keys))
        with pytest.raises(ledger.ConfidenceLedgerError, match="loaded facade map differs"):
            ledger._source_facade_runtime_projection(root, closure)
    with monkeypatch.context() as changed:
        changed.setattr(facade, "MappingProxyType", lambda value: value)
        with pytest.raises(ledger.ConfidenceLedgerError, match="loaded facade map differs"):
            ledger._source_facade_runtime_projection(root, closure)
    with monkeypatch.context() as changed:
        changed.setattr(facade, "parse_canonical_statement", provider.canonical_statement_bytes)
        with pytest.raises(ledger.ConfidenceLedgerError):
            ledger._source_facade_runtime_projection(root, closure)

    # An equal-valued proxy is a different retained object even if its backing
    # dictionary remains writable by another holder.
    with monkeypatch.context() as changed:
        changed.setattr(facade, "_EXPORTS", MappingProxyType(dict(facade._EXPORTS)))
        rebound: list[ledger._FacadeRuntimeBindingReference] = []
        rebound_projection, _supplemental = ledger._source_facade_runtime_projection(
            root, closure, runtime_binding_references=rebound
        )
        assert rebound_projection == projection
        assert not ledger._runtime_binding_references_match(rebound, tuple(references))


def test_security_http_reexport_needs_retained_proxy_constructor() -> None:
    from polisyos.core.security import identity
    from polisyos.runtime.http import security

    root = ledger._loaded_policy_engine_root()
    source_index = ledger._AuthorityImportClosureSourceIndex({}, {})
    for name in ("PolicyOSRole", "UserIdentityClaims"):
        assert getattr(security, name) is getattr(identity, name)
        with pytest.raises(ledger.ConfidenceLedgerError, match="initializer namespace effect"):
            ledger._source_module_import_route(
                root,
                security.__name__,
                name,
                directory_entries={},
                source_index=source_index,
            )


@pytest.mark.parametrize(
    "extra",
    [
        "mutate_package_globals()",
        "MappingProxyType = dict",
        "__loader__ = None",
        "_EXPORTS = {'PolicyOSRole': ('polisyos.core.security.identity', 'PolicyOSRole')}",
    ],
)
def test_initializer_keeps_unknown_effects_around_a_proxy_facade(extra: str) -> None:
    facade = importlib.import_module("polisyos.core.security")
    source = Path(facade.__file__).read_text(encoding="utf-8")
    assert ledger._source_package_initializer_effect_is_unknown(ast.parse(source))
    assert not ledger._source_package_initializer_effect_is_unknown(
        ast.parse(source), qualified_proxy_map="_EXPORTS"
    )
    assert ledger._source_package_initializer_effect_is_unknown(
        ast.parse(f"{source}\n{extra}\n"), qualified_proxy_map="_EXPORTS"
    )


@pytest.mark.parametrize("transient", [False, True])
def test_proxy_initializer_constructor_reconciles_observed_import(
    tmp_path: Path, transient: bool
) -> None:
    package = tmp_path / "proxy_owner"
    package.mkdir()
    (package / "__init__.py").write_text(
        "from types import MappingProxyType\n"
        "_EXPORTS = MappingProxyType({'selected': ('proxy_leaf', 'selected')})\n",
        encoding="utf-8",
    )
    product = Path(__file__).resolve().parents[4]
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-c",
            """
import hashlib, importlib, importlib.util, sys, types
from pathlib import Path

root, tool = (Path(value).resolve() for value in sys.argv[1:3])
transient = sys.argv[3] == 'True'
spec = importlib.util.spec_from_file_location('_fixture_recorder', tool)
assert spec is not None and spec.loader is not None
recorder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = recorder
spec.loader.exec_module(recorder)
relative = 'proxy_owner/__init__.py'
source = (root / relative).read_bytes()
capture = recorder.SourceExecutionCapture(root, {
    'proxy_owner': recorder.ExpectedSource(relative, hashlib.sha256(source).hexdigest())
}, exports={'proxy_owner': {'_EXPORTS'}})
canonical = type(type.__dict__)

def foreign(value):
    owner = sys.modules['proxy_owner']
    owner.MappingProxyType = canonical
    owner.side_effect = True
    types.MappingProxyType = canonical
    return canonical(value)

capture.install()
try:
    sys.path.insert(0, str(root))
    if transient:
        types.MappingProxyType = foreign
    owner = importlib.import_module('proxy_owner')
    assert owner.MappingProxyType is types.MappingProxyType is canonical
    assert type(owner._EXPORTS) is canonical
    assert getattr(owner, 'side_effect', False) is transient
    event, = (
        item for item in capture.import_events()
        if item.importer_name == 'proxy_owner' and item.provider_name == 'types'
    )
    assert event.caller_code is capture.completed('proxy_owner').code
    assert event.caller_line == 1 and event.route == 'builtin_import'
    assert event.retained_exports['MappingProxyType'] is (foreign if transient else canonical)
    try:
        capture.assert_import_binding(
            event, importer_attribute='MappingProxyType', provider_export='MappingProxyType'
        )
    except recorder.CaptureError as exc:
        assert transient and str(exc) == 'import_event_binding_changed', str(exc)
    else:
        assert not transient, 'restored namespace hid the transient foreign constructor'
finally:
    types.MappingProxyType = canonical
    capture.close()
""",
            str(tmp_path),
            str(product / "tools" / "loaded_execution_capture.py"),
            str(transient),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_core_proxy_constructor_requires_the_exact_retained_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade = importlib.import_module("polisyos.core.security")
    tree = ast.parse(Path(facade.__file__).read_bytes())
    expected_import = next(
        statement
        for statement in tree.body
        if isinstance(statement, ast.ImportFrom)
        and statement.module == "types"
        and any(alias.name == "MappingProxyType" for alias in statement.names)
    )
    calls = []

    def check_edge(_self, module, provider, node, alias, *, expected_export):
        calls.append((module, provider, node, alias.name, expected_export))
        raise ValueError("retained_import_unqualified")

    monkeypatch.setattr(ledger._N5LockedOptionalImports, "_initializer_edge", check_edge)
    capture = SimpleNamespace(import_events=lambda: ())
    binding = ledger._N5LockedOptionalImports(
        ledger._loaded_policy_engine_root(),
        ledger._IntegrityAnalysisContext(),
        capture,
        lambda _: None,
    )
    with pytest.raises(ValueError, match="retained_import_unqualified"):
        binding.reconcile_proxy_constructor(facade.__name__, tree, "_EXPORTS")
    assert calls == [
        (facade.__name__, "types", expected_import, "MappingProxyType", type(type.__dict__))
    ]


def test_immutable_facade_detects_equal_graft_during_reconciliation(
    security_facade_case, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, facade, _provider, closure = security_facade_case
    original = ledger._read_api_surface_runtime_identity_projection
    with monkeypatch.context() as changed:

        def graft(*args, **kwargs):
            result = original(*args, **kwargs)
            changed.setattr(facade, "_EXPORTS", MappingProxyType(dict(facade._EXPORTS)))
            return result

        changed.setattr(ledger, "_read_api_surface_runtime_identity_projection", graft)
        with pytest.raises(ledger.ConfidenceLedgerError, match="changed during reconciliation"):
            ledger._source_facade_runtime_projection(root, closure)


def test_immutable_facade_reconciles_retained_initializer_map(
    security_facade_case, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, facade, _provider, closure = security_facade_case
    captured = facade._EXPORTS

    class Capture:
        def completed_binding(self, module_name: str, name: str) -> object:
            assert (module_name, name) == (facade.__name__, "_EXPORTS")
            return captured

    monkeypatch.setattr(
        ledger, "_retained_n5_host_capture", lambda: (SimpleNamespace(capture=Capture()), {})
    )
    assert ledger._source_facade_runtime_projection(root, closure)[0]
    monkeypatch.setattr(facade, "_EXPORTS", MappingProxyType(dict(captured)))
    with pytest.raises(ledger.ConfidenceLedgerError, match="retained facade map differs"):
        ledger._source_facade_runtime_projection(root, closure)


def test_execution_source_capture_checks_live_proxy_and_leaves_inactive_route_source_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the real source-capture entrypoint with a held-binding recorder."""
    root = tmp_path / "engine"
    package = root / "src/polisyos"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    leaf_name = "polisyos._e02_proxy_leaf"
    facade_name = "polisyos._e02_proxy_facade"
    inactive_name = "polisyos._e02_proxy_inactive"
    consumer_name = "polisyos._e02_proxy_consumer"
    facade_source = (
        "from types import MappingProxyType\n"
        "import importlib\n"
        f"_EXPORTS = MappingProxyType({{'selected': ('{leaf_name}', 'selected')}})\n"
        "def __getattr__(name):\n"
        "    if name in _EXPORTS:\n"
        "        module_name, symbol = _EXPORTS[name]\n"
        "        value = getattr(importlib.import_module(module_name), symbol)\n"
        "        globals()[name] = value\n"
        "        return value\n"
        "    raise AttributeError(name)\n"
    )
    sources = {
        leaf_name: (package / "_e02_proxy_leaf.py", "def selected():\n    return 17\n"),
        facade_name: (package / "_e02_proxy_facade/__init__.py", facade_source),
        inactive_name: (package / "_e02_proxy_inactive/__init__.py", facade_source),
        consumer_name: (
            package / "_e02_proxy_consumer.py",
            f"def run():\n    from {facade_name} import selected\n    return selected()\n"
            f"def dormant():\n    from {inactive_name} import selected\n    return selected()\n",
        ),
    }
    for path, text in sources.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def load(name: str) -> types.ModuleType:
        path, _text = sources[name]
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        return module

    leaf = load(leaf_name)
    facade = load(facade_name)
    consumer = load(consumer_name)
    assert consumer.run() == 17
    assert "selected" in vars(facade)
    assert inactive_name not in sys.modules

    modules = {leaf_name: leaf, facade_name: facade}
    original = {
        (leaf_name, "selected"): leaf.selected,
        (facade_name, "_EXPORTS"): facade._EXPORTS,
        (facade_name, "__getattr__"): vars(facade)["__getattr__"],
    }

    class Recorder:
        def import_events(self) -> tuple[object, ...]:
            return ()

        def completed(self, name: str) -> SimpleNamespace:
            module = modules[name]
            source = Path(module.__file__)
            return SimpleNamespace(
                module=module,
                relative_path=source.relative_to(root).as_posix(),
                origin=str(source),
                source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            )

        def assert_retained(self, _names: frozenset[str]) -> None:
            return None

        def completed_binding(self, name: str, symbol: str) -> object:
            held = original[(name, symbol)]
            if vars(modules[name]).get(symbol) is not held:
                raise ValueError("retained binding changed")
            return held

    recorder = Recorder()
    monkeypatch.setattr(ledger, "_loaded_policy_engine_root", lambda: root)
    monkeypatch.setattr(
        ledger,
        "_n5_locked_optional_imports",
        lambda selected_root, analysis: ledger._N5LockedOptionalImports(
            selected_root, analysis, recorder, lambda _name: None
        ),
    )

    def capture() -> dict[str, object]:
        return ledger.capture_execution_source_bindings(
            (consumer_name,), ((consumer_name, consumer.run.__code__),)
        )

    assert capture()["source_module_count"] >= 4
    assert inactive_name not in sys.modules
    with monkeypatch.context() as changed:
        changed.setattr(facade, "_EXPORTS", MappingProxyType(dict(facade._EXPORTS)))
        with pytest.raises(ledger.ConfidenceLedgerError, match="live proxy facade is unqualified"):
            capture()
    with monkeypatch.context() as changed:
        changed.delitem(vars(facade), "selected")
        changed.setattr(facade, "_EXPORTS", MappingProxyType(dict(facade._EXPORTS)))
        with pytest.raises(ledger.ConfidenceLedgerError, match="live proxy facade is unqualified"):
            capture()
    with monkeypatch.context() as changed:
        changed.setattr(facade, "selected", ledger._NO_EXECUTION_BINDING)
        with pytest.raises(ledger.ConfidenceLedgerError, match="live proxy facade is unqualified"):
            capture()
    with monkeypatch.context() as changed:
        getter = vars(facade)["__getattr__"]
        replacement = types.FunctionType(
            getter.__code__,
            getter.__globals__,
            getter.__name__,
            getter.__defaults__,
            getter.__closure__,
        )
        changed.setattr(facade, "__getattr__", replacement)
        with pytest.raises(ledger.ConfidenceLedgerError, match="live proxy facade is unqualified"):
            capture()
    with monkeypatch.context() as changed:

        class FacadeSubclass(types.ModuleType):
            pass

        replacement_module = FacadeSubclass(facade_name)
        vars(replacement_module).update(vars(facade))
        changed.setitem(sys.modules, facade_name, replacement_module)
        with pytest.raises(ledger.ConfidenceLedgerError, match="live proxy facade is unqualified"):
            capture()
    with monkeypatch.context() as changed:
        changed.setitem(sys.modules, facade_name, ledger._NO_EXECUTION_BINDING)
        with pytest.raises(ledger.ConfidenceLedgerError, match="live proxy facade is unqualified"):
            capture()


@pytest.mark.parametrize(
    ("factory", "assignment"),
    [
        ("from fake_types import MappingProxyType", "MappingProxyType({})"),
        ("from types import MappingProxyType\nMappingProxyType = dict", "MappingProxyType({})"),
        ("from types import MappingProxyType\nbacking = {}", "MappingProxyType(backing)"),
        ("from types import MappingProxyType\nalias = MappingProxyType", "alias({})"),
    ],
)
def test_immutable_facade_rejects_unproven_constructor_or_backing(
    factory: str, assignment: str
) -> None:
    tree = ast.parse(f"{factory}\n_EXPORTS = {assignment}\n")
    names = frozenset({"_EXPORTS"})
    maps, invalid, _unknown = ledger._source_declared_facade_mapping_values(tree, names)
    assert "_EXPORTS" not in ledger._source_literal_proxy_facade_declarations(tree, names)
    assert "_EXPORTS" not in maps or "_EXPORTS" in invalid


def test_immutable_facade_accepts_inline_literal_with_direct_import_alias() -> None:
    tree = ast.parse(
        "from types import MappingProxyType as freeze\n"
        "_EXPORTS = freeze({'item': ('polisyos.example', 'item')})\n"
    )
    names = frozenset({"_EXPORTS"})
    maps, invalid, _unknown = ledger._source_declared_facade_mapping_values(tree, names)
    assert not invalid
    assert maps == {"_EXPORTS": {"item": ("polisyos.example", "item")}}
    assert ledger._source_literal_proxy_facade_declarations(tree, names)["_EXPORTS"][1] == "freeze"
