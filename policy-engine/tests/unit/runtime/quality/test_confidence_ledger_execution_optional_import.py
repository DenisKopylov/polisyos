"""Distinguish retained N5 initializer import evidence from matching live aliases."""

from __future__ import annotations

import hashlib
import importlib
import subprocess
import sys
import types
import zipfile
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "profile",
    [
        "locked-provider",
        "ordinary-fallback",
        "first-party-alias",
        "first-party-loader",
        "package-reexport",
    ],
)
def test_n5_capture_requires_actual_initializer_and_locked_members(
    tmp_path: Path, profile: str
) -> None:
    """Retain the selected import relationship across local and wheel source."""
    root = tmp_path.resolve()
    product = Path(__file__).resolve().parents[4]
    sources = {
        "tools/__init__.py": "",
        "tools/_e02_locked_wrapper.py": (
            "try:\n"
            "    from e02_locked_provider import Model\n"
            "    AVAILABLE = True\n"
            "except ImportError:\n"
            "    AVAILABLE = False\n"
            "    class Model:\n"
            "        def predict(self): return -17\n"
        ),
        "tools/_e02_locked_consumer.py": (
            "from tools._e02_locked_wrapper import AVAILABLE, Model as Selected\n"
            "def observed(): return Selected().predict()\n"
        ),
        "tools/_e02_first_party_optional.py": (
            "try:\n"
            "    from ._e02_first_party_forward import selected\n"
            "except ModuleNotFoundError:\n"
            "    def selected(): return -23\n"
        ),
        "tools/_e02_first_party_forward.py": "from ._e02_first_party_base import selected\n",
        "tools/_e02_first_party_base.py": "def selected(): return 23\n",
        "tools/_e02_package_reexport/__init__.py": (
            "from enum import Enum\n"
            "class Domain(str, Enum):\n    VALUE = 'policy'\n"
            "def measure(): return 29\n"
        ),
        "tools/_e02_package_forward.py": "from ._e02_package_reexport import measure as selected\n",
        "tools/_e02_package_consumer.py": (
            "from ._e02_package_forward import selected as run\ndef observed(): return run()\n"
        ),
    }
    for relative, content in sources.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    wheel_sources = {
        "e02_locked_provider/__init__.py": "from .base import Model\n",
        "e02_locked_provider/base.py": "class Model:\n    def predict(self): return 17\n",
        "e02_locked_provider-1.0.dist-info/METADATA": (
            "Metadata-Version: 2.1\nName: e02-locked-provider\nVersion: 1.0\n\n"
        ),
        "e02_locked_provider-1.0.dist-info/WHEEL": (
            "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n\n"
        ),
        "e02_locked_provider-1.0.dist-info/RECORD": (
            "e02_locked_provider/__init__.py,,\ne02_locked_provider/base.py,,\n"
        ),
    }
    wheel = root / "e02_locked_provider-1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for relative, content in wheel_sources.items():
            archive.writestr(relative, content)
            path = root / "site" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    lock = root / "uv.lock"
    lock.write_text(
        '[[package]]\nname = "e02-locked-provider"\nversion = "1.0"\n'
        f'wheels = [{{ url = "https://example.invalid/{wheel.name}", '
        f'hash = "sha256:{digest}", size = {wheel.stat().st_size} }}]\n',
        encoding="utf-8",
    )
    result = subprocess.run(  # noqa: S603 - fixed local interpreter and source probe
        [sys.executable, "-I", "-S", "-B", "-c", _PROBE, str(product), str(root), profile],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.integration
def test_retained_callable_foundry_facade_maps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bind the real compile/execute maps, cache objects, and callable package classes."""
    host = sys.modules.get("_polisyos_early_host")
    if host is None:
        pytest.skip("requires the selected early authority launcher")

    from polisyos.runtime.quality import confidence_ledger as ledger

    execute = importlib.import_module("polisyos.foundry.execute")
    compile_package = importlib.import_module("polisyos.foundry.compile")
    routes = (
        (execute, "apply_state_delta", "polisyos.foundry.execute._internal.patching"),
        (execute, "admit_execution_source", "polisyos.foundry.execute.api"),
        (compile_package, "compile", "polisyos.foundry.compile.api"),
    )
    for facade, export, provider in routes:
        assert callable(facade)
        assert getattr(facade, export) is vars(importlib.import_module(provider))[export]

    host.handoff_if_ready()
    root = ledger._loaded_policy_engine_root()
    analysis = ledger._IntegrityAnalysisContext()
    observed = ledger._n5_locked_optional_imports(root, analysis)
    assert observed is not None, sys.__dict__["_polisyos_loaded_host_v1"]["last_owner_diagnostic"]
    source_index = ledger._AuthorityImportClosureSourceIndex(
        {}, {}, n5_recorded_optional_imports=observed
    )

    def resolve(facade: types.ModuleType, export: str) -> tuple[str, str, str | None] | None:
        candidate = ledger._source_module_import_route_candidate(
            root,
            facade.__name__,
            export,
            directory_entries={},
            source_index=source_index,
            discovery_only=True,
        )
        assert candidate.package_initializer_effect_unknown
        return candidate.route

    for facade, export, provider in routes:
        assert resolve(facade, export) == ("symbol", provider, export)

    with pytest.raises(ledger.ConfidenceLedgerError, match="unsupported source facade map"):
        ledger._source_module_import_route_candidate(
            root,
            execute.__name__,
            "apply_state_delta",
            directory_entries={},
            source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
            discovery_only=True,
        )

    child = importlib.import_module("polisyos.foundry.execute.api")
    assert execute.__getattr__("api") is child
    with pytest.raises(AttributeError, match="_absent_callable_facade_fixture"):
        execute.__getattr__("_absent_callable_facade_fixture")
    with pytest.raises(ledger.ConfidenceLedgerError, match="missing repository re-export binding"):
        resolve(execute, "api")

    export = "apply_state_delta"
    original = execute.apply_state_delta
    with monkeypatch.context() as mutation:
        alternate = importlib.import_module("polisyos.foundry.execute.executor")
        assert alternate.apply_state_delta is original
        mutation.setitem(vars(execute)["_LAZY_IMPORTS"], export, (alternate.__name__, export))
        assert execute.apply_state_delta is original
        with pytest.raises(ledger.ConfidenceLedgerError, match="map differs from source"):
            resolve(execute, export)
    for facade, export, provider in routes:
        original = getattr(facade, export)
        assert type(original) is types.FunctionType
        replacement = types.FunctionType(
            original.__code__,
            original.__globals__,
            original.__name__,
            original.__defaults__,
            original.__closure__,
        )
        with monkeypatch.context() as mutation:
            mutation.setattr(facade, export, replacement)
            with pytest.raises(
                ledger.ConfidenceLedgerError, match="callable facade cache is unqualified"
            ):
                resolve(facade, export)
        assert resolve(facade, export) == ("symbol", provider, export)

    root_facade = Path("src/polisyos/foundry/__init__.py")
    assert (
        observed.callable_facade_effect_view(
            "polisyos.foundry", root_facade, analysis.source_tree(root / root_facade)
        )
        is None
    )
    analysis.assert_sources_unchanged()

    with monkeypatch.context() as mutation:
        mutation.setattr(compile_package, "__class__", types.ModuleType)
        with pytest.raises(ledger.ConfidenceLedgerError, match="callable facade class or source"):
            resolve(compile_package, "compile")
    assert observed.capture.failure_reason == "retained_module_changed"


_PROBE = r"""
import hashlib
import importlib
import importlib.util
import sys
import types
from importlib.machinery import SourceFileLoader
from pathlib import Path

product, root, profile = sys.argv[1:]
product, root = Path(product), Path(root)
fallback = profile == "ordinary-fallback"
venv_site = Path(sys.prefix) / "lib/python3.14/site-packages"
sys.path[:0] = [str(root), str(product / "src"), str(venv_site)]
plain_import_profile = sys.meta_path[:]


def source_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ledger = source_module(
    "_fixture_ledger", product / "src/polisyos/runtime/quality/confidence_ledger.py"
)
host = source_module("_fixture_host", product / "tools/authority_bootstrap.py")
recorder = source_module("_fixture_recorder", product / "tools/loaded_execution_capture.py")
# The fixture exercises a distinct source root with ordinary Python importers.
# The product setup above registers compatibility finders for its own packages.
# The stock host test retains and qualifies those finders in the real profile.
sys.meta_path[:] = plain_import_profile
assert "tools" not in sys.modules

site = root / "site"
lock = (root / "uv.lock").read_bytes()
wheel = next(root.glob("*.whl")).read_bytes()
host._LockedWheelSourceSelector._archive_bytes = staticmethod(lambda url, size: wheel)
selector = host._LockedWheelSourceSelector(root, site, lock)
consumer = "tools._e02_locked_consumer"
wrapper = "tools._e02_locked_wrapper"
facade = "e02_locked_provider"
terminal = facade + ".base"
first_party = tuple("tools._e02_first_party_" + name for name in ("optional", "forward", "base"))
direct = tuple("tools._e02_package_" + name for name in ("consumer", "forward", "reexport"))
sources = {}
exports = {wrapper: {"AVAILABLE", "Model"}, **dict.fromkeys(first_party, {"selected"})}
for source in (root / "tools").rglob("*.py"):
    relative = source.relative_to(root).as_posix()
    name = host._module_name(relative)
    assert name is not None
    content = source.read_bytes()
    sources[name] = recorder.ExpectedSource(relative, hashlib.sha256(content).hexdigest())
    for provider, names in host._source_export_candidates(name, relative, content).items():
        exports.setdefault(provider, set()).update(names)
capture = recorder.SourceExecutionCapture(
    root,
    sources,
    exports={name: bindings for name, bindings in exports.items() if name in sources},
    external_source_selector=selector.select,
)
capture.install()


def assert_first_party_route_refused(source_index):
    try:
        ledger._source_module_import_route_candidate(
            root, first_party[0], "selected", directory_entries={}, source_index=source_index,
            discovery_only=True,
        )
    except ledger.ConfidenceLedgerError as exc:
        assert exc.code == "canonical_loaded_runtime_mismatch", str(exc)
    else:
        raise AssertionError("unqualified first-party alias accepted")


def observe_first_party():
    modules = [importlib.import_module(name) for name in first_party]
    optional, forwarding, terminal_owner = modules
    original = optional.selected
    assert original is forwarding.selected is terminal_owner.selected
    assert original() == 23
    assert_first_party_route_refused(ledger._AuthorityImportClosureSourceIndex({}, {}))
    analysis = ledger._IntegrityAnalysisContext()
    binding = ledger._N5LockedOptionalImports(root, analysis, capture, lambda _: None)
    source_index = ledger._AuthorityImportClosureSourceIndex(
        {}, {}, n5_recorded_optional_imports=binding,
    )
    candidate = ledger._source_module_import_route_candidate(
        root, optional.__name__, "selected", directory_entries={}, source_index=source_index,
        discovery_only=True,
    )
    assert candidate.route == ("symbol", terminal_owner.__name__, "selected")
    assert candidate.package_initializer_effect_unknown is False
    edges = binding.first_party_rows[(optional.__name__, "selected")]
    assert [edge[0] for edge in edges] == list(first_party[:2])
    assert [edge[3] for edge in edges] == list(first_party[1:])
    analysis.assert_sources_unchanged()
    if profile == "first-party-alias":
        replacement = types.FunctionType(original.__code__, vars(terminal_owner), original.__name__)
        for module in modules:
            module.selected = replacement
        assert optional.selected is forwarding.selected is terminal_owner.selected
    else:
        class LookalikeLoader(SourceFileLoader):
            pass
        optional.__spec__.loader = LookalikeLoader(optional.__name__, optional.__file__)
    assert optional.selected() == 23
    assert_first_party_route_refused(source_index)
    assert capture.failure_reason == (
        "retained_export_changed" if profile == "first-party-alias" else "retained_module_changed"
    ), capture.failure_reason


def observe_package_reexport():
    consumer, forward, package = (importlib.import_module(name) for name in direct)
    original = package.measure
    assert original is forward.selected is consumer.run
    assert consumer.observed() == 29

    def closure(binding=None):
        return ledger._resolve_authority_import_closure(
            root, consumer.__name__, include_tools=True, _n5_optional_imports=binding,
        )

    def assert_refused(binding):
        try:
            closure(binding)
        except ledger.ConfidenceLedgerError as exc:
            assert exc.code == "canonical_loaded_runtime_mismatch", str(exc)
            assert "package initializer namespace effect" in str(exc)
            return exc
        raise AssertionError("unqualified ordinary package reexport accepted")

    assert_refused(None)
    analysis = ledger._IntegrityAnalysisContext()
    binding = ledger._N5LockedOptionalImports(root, analysis, capture, lambda _: None)
    assert set(dict(closure(binding))) == {"tools", *direct}
    edges = binding.first_party_direct_rows[(forward.__name__, "selected")]
    assert len(edges) == 1
    edge = edges[0]
    assert (edge[0], *edge[3:]) == (forward.__name__, package.__name__, "measure", "selected")
    analysis.assert_sources_unchanged()

    without_edge = ledger._N5LockedOptionalImports(root, analysis, capture, lambda _: None)
    without_edge.events.pop((forward.__name__, package.__name__))
    assert str(assert_refused(without_edge).__cause__) == "n5_optional_initializer_edge_not_established"
    assert not without_edge.first_party_direct_rows

    replacement = types.FunctionType(original.__code__, vars(package), original.__name__)
    package.measure = forward.selected = consumer.run = replacement
    assert consumer.observed() == 29
    assert_refused(binding)
    assert capture.failure_reason == "retained_export_changed", capture.failure_reason


if profile == "package-reexport":
    observe_package_reexport()
    raise SystemExit(0)
if profile.startswith("first-party-"):
    observe_first_party()
    raise SystemExit(0)
if not fallback:
    sys.path.insert(0, str(site))
actual = importlib.import_module(consumer)
assert actual.observed() == (-17 if fallback else 17)

try:
    ledger._resolve_authority_import_closure(root, consumer, include_tools=True)
except ledger.ConfidenceLedgerError as exc:
    assert exc.code == "canonical_loaded_runtime_mismatch", str(exc)
else:
    raise AssertionError("the strict closure consumed the N5-specific route")


def selected_member(name):
    retained = selector._selected.get(name)
    if retained is None:
        return None
    completed = capture.completed(name)
    if selector.select(name, completed.origin, _retained_only=True) != retained[:2]:
        return None
    return (name, *retained, hashlib.sha256(lock).hexdigest())


def observe(member):
    analysis = ledger._IntegrityAnalysisContext()
    binding = ledger._N5LockedOptionalImports(root, analysis, capture, member)
    closure = ledger._resolve_authority_import_closure(
        root, consumer, include_tools=True, _n5_optional_imports=binding,
    )
    analysis.assert_sources_unchanged()
    assert set(dict(closure)) == {"tools", consumer, wrapper}
    return [row for _, row in sorted(binding.rows.items())]

def assert_refused(member, failure):
    try:
        observe(member)
    except ledger.ConfidenceLedgerError as exc:
        assert exc.code == "canonical_loaded_runtime_mismatch", str(exc)
        assert str(exc.__cause__) == failure, str(exc.__cause__)
    else:
        raise AssertionError("unqualified optional import was accepted")


if fallback:
    assert_refused(selected_member, "n5_optional_wrapper_success_not_established")
else:
    rows = observe(selected_member)
    assert [row["consumer_import"][-2:] for row in rows] == [
        ("AVAILABLE", "AVAILABLE"), ("Model", "Selected")
    ]
    local, edges, members = rows[1]["locked_class_imports"][0]
    assert local == "Model"
    assert [(edge[0], edge[3:]) for edge in edges] == [
        (wrapper, (facade, "Model", "Model")), (facade, (terminal, "Model", "Model"))
    ]
    assert [row[0] for row in members] == [facade, terminal]
    assert all(row[3] == "sha256:" + hashlib.sha256(wheel).hexdigest() for row in members)
    assert_refused(
        lambda name: None if name == terminal else selected_member(name),
        "n5_optional_locked_python_member_not_established",
    )

    class Model:
        def predict(self): return 17
    Model.__module__ = terminal
    for name in (terminal, facade, wrapper):
        sys.modules[name].Model = Model
    actual.Selected = Model
    assert actual.observed() == 17  # Same name, object agreement and number still prove nothing.
    assert_refused(selected_member, "retained_export_changed")
"""
