"""Distinguish retained N5 initializer import evidence from matching live aliases."""

from __future__ import annotations

import ast
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
        "unconsumed-alias",
        "guarded-family",
        "guarded-is-not-none",
        "guarded-fallback",
        "guarded-alias",
        "guarded-code",
        "guarded-default",
        "guarded-provider",
        "guarded-source",
        "guarded-prerequisite",
        "guarded-events",
        "guarded-handler",
        "guarded-shadowed-raise",
        "guarded-call-guard",
        "guarded-prerequisite-handler",
        "guarded-none-import",
        "flagged-guard",
        "guarded-class-code",
        "guarded-class-default",
        "guarded-class-state",
        "guarded-class-metaclass",
        "guarded-executed-class-default",
        "flagged-bound-guard",
        "guarded-none-locked",
        "guarded-ambiguous-failure",
        "guarded-class-kwdefault",
        "guarded-class-closure",
        "guarded-class-literal-state",
        "guarded-declared-transform",
        "guarded-undeclared-transform",
        "guarded-dynamic-failure",
        "guarded-builtin-alias",
        "guarded-module-descriptor",
        "guarded-structural-classmethod",
        "guarded-structural-staticmethod",
        "guarded-structural-property",
        "guarded-structural-alias",
        "guarded-structural-unresolved",
        "guarded-transform-factory-rebind",
        "guarded-transform-provider-missing",
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
            "    from e02_locked_provider import Model, SVC\n"
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
    guarded = (
        "try:\n    import e02_locked_provider as backend\n"
        "except Exception as exc:\n    backend = None\n    BACKEND_ERROR = exc\n"
        "try:\n    if backend is None:\n        raise RuntimeError('prerequisite unavailable')\n"
        "    from e02_locked_provider import Model, SVC, calculate\n"
        "except Exception as exc:\n    Model = None\n    SVC = None\n    calculate = None\n    FAMILY_ERROR = exc\n"
    )
    if profile == "guarded-is-not-none":
        guarded = guarded.replace(
            "import e02_locked_provider as backend", "import missing_prerequisite as backend"
        ).replace("if backend is None:", "if backend is not None:")
    elif profile == "guarded-fallback":
        guarded = guarded.replace(
            "import e02_locked_provider as backend", "import missing_prerequisite as backend"
        )
    elif profile == "guarded-prerequisite-handler":
        guarded = "ModuleNotFoundError = BaseException\n" + guarded.replace(
            "import e02_locked_provider as backend", "import missing_prerequisite as backend"
        ).replace("except Exception as exc:", "except ModuleNotFoundError as exc:", 1).replace(
            "if backend is None:", "if backend is not None:"
        )
    elif profile == "guarded-none-locked":
        guarded = guarded.replace(
            "import e02_locked_provider as backend",
            "from e02_locked_provider import SENTINEL as backend",
        ).replace("if backend is None:", "if backend is not None:")
    elif profile in {"guarded-none-import", "guarded-dynamic-failure"}:
        guarded = guarded.replace(
            "import e02_locked_provider as backend",
            "from e02_unlocked_prerequisite import SENTINEL as backend",
        ).replace("if backend is None:", "if backend is not None:")
    elif profile == "guarded-handler":
        guarded = guarded.replace("except Exception as exc:", "except BaseException as exc:")
    elif profile == "guarded-builtin-alias":
        guarded = "from builtins import ValueError as RuntimeError\n" + guarded
    elif profile == "guarded-shadowed-raise":
        guarded = "RuntimeError = lambda message: ValueError(message)\n" + guarded
    elif profile == "guarded-call-guard":
        guarded = guarded.replace("if backend is None:", "if bool(backend):")
    if profile == "guarded-dynamic-failure":
        guarded = (
            "try:\n    __import__('e02_unlocked_prerequisite')\nexcept ImportError:\n    pass\n"
            + guarded
        )
    sources["tools/_e02_guarded_optional.py"] = guarded
    sources["tools/_e02_guarded_consumer.py"] = (
        "from tools._e02_guarded_optional import backend, Model, SVC, calculate\n"
    )
    if profile == "flagged-guard":
        sources["tools/_e02_locked_consumer.py"] += "from tools._e02_locked_wrapper import SVC\n"
        sources["tools/_e02_locked_wrapper.py"] = (
            "unqualified = 1\nRuntimeError = lambda message: ValueError(message)\n"
            + sources["tools/_e02_locked_wrapper.py"].replace(
                "try:\n", "try:\n    if unqualified is None:\n        raise RuntimeError('x')\n", 1
            )
        )
    if profile == "flagged-bound-guard":
        sources["tools/_e02_locked_consumer.py"] += (
            "from tools._e02_locked_wrapper import backend, SVC\n"
        )
        sources["tools/_e02_locked_wrapper.py"] = (
            "import e02_locked_provider as backend\n"
            + sources["tools/_e02_locked_wrapper.py"].replace(
                "try:\n", "try:\n    if backend is None:\n        raise ImportError('x')\n", 1
            )
        )
    if profile == "guarded-executed-class-default":
        sources["tools/_e02_guarded_consumer.py"] = "def observed(): return 17\n"
    for relative, content in sources.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    wheel_sources = {
        "e02_locked_provider/__init__.py": "from .base import Model, SVC, calculate\n",
        "e02_locked_provider/base.py": (
            "class Model:\n    def predict(self, value=17): return value\n"
            "class SVC:\n    def predict(self): return 29\n"
            "def calculate(value=13): return value + 4\n"
        ),
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
    if profile == "guarded-none-locked":
        wheel_sources["e02_locked_provider/__init__.py"] += "SENTINEL = None\n"
    if profile == "guarded-class-kwdefault":
        wheel_sources["e02_locked_provider/base.py"] = wheel_sources[
            "e02_locked_provider/base.py"
        ].replace("def predict(self, value=17)", "def predict(self, *, value=17)")
    if profile == "guarded-class-closure":
        wheel_sources["e02_locked_provider/base.py"] = wheel_sources[
            "e02_locked_provider/base.py"
        ].replace(
            "def predict(self, value=17): return value",
            "def predict(self, value=17): return value + (0 if __class__ is Model else 1)",
        )
    if profile == "guarded-class-literal-state":
        wheel_sources["e02_locked_provider/base.py"] = wheel_sources[
            "e02_locked_provider/base.py"
        ].replace("class Model:\n", "class Model:\n    FACTOR = 17\n")
    if profile.startswith("guarded-structural-"):
        kind = profile.removeprefix("guarded-structural-")
        method = (
            "    @property\n    def predict(self): return 17\n"
            if kind == "property"
            else "    @staticmethod\n    def predict(value=17): return value\n"
            if kind == "staticmethod"
            else "    @classmethod\n    def predict(cls, value=17): return value\n"
        )
        if kind == "unresolved":
            wheel_sources["e02_locked_provider/base.py"] = (
                "classmethod = classmethod\n" + wheel_sources["e02_locked_provider/base.py"]
            )
        if kind == "alias":
            method = method.replace("@classmethod", "@structural")
            wheel_sources["e02_locked_provider/base.py"] = (
                "from builtins import classmethod as structural\n"
                + wheel_sources["e02_locked_provider/base.py"]
            )
        wheel_sources["e02_locked_provider/base.py"] = wheel_sources[
            "e02_locked_provider/base.py"
        ].replace("    def predict(self, value=17): return value\n", method, 1)
    if profile == "guarded-transform-factory-rebind":
        wheel_sources["e02_locked_provider/transforms.py"] = (
            "from builtins import classmethod as borrowed\n"
        )
        wheel_sources["e02_locked_provider/base.py"] = (
            "from .transforms import borrowed as classmethod\n"
            + wheel_sources["e02_locked_provider/base.py"].replace(
                "    def predict(self, value=17): return value\n",
                "    @classmethod\n    def predict(cls, value=17): return value\n",
                1,
            )
        )
    if profile in {"guarded-declared-transform", "guarded-transform-provider-missing"}:
        wheel_sources["e02_locked_provider/base.py"] = (
            "from .transforms import borrowed\n"
            + wheel_sources["e02_locked_provider/base.py"].replace(
                "    def predict(self, value=17)",
                "    @borrowed\n    def predict(self, value=17)",
                1,
            )
        )
        wheel_sources["e02_locked_provider/transforms.py"] = (
            "from functools import wraps\n"
            "def borrowed(function):\n"
            "    @wraps(function)\n"
            "    def wrapped(*args, **kwargs): return function(*args, **kwargs)\n"
            "    return wrapped\n"
        )
    if profile == "guarded-module-descriptor":
        wheel_sources["e02_locked_provider/base.py"] += (
            "from types import ModuleType\nimport sys\neffects = []\n"
            "class ProviderModule(ModuleType):\n"
            "    def __getattribute__(self, name):\n"
            "        if name == '__dict__': effects.append('executed')\n"
            "        return super().__getattribute__(name)\n"
            "sys.modules[__name__].__class__ = ProviderModule\n"
        )
    if profile == "guarded-class-metaclass":
        wheel_sources["e02_locked_provider/base.py"] = (
            "effects = []\n"
            "class Meta(type):\n"
            "    @property\n"
            "    def __module__(cls):\n"
            "        effects.append('executed')\n"
            "        return __name__\n"
            + wheel_sources["e02_locked_provider/base.py"].replace(
                "class Model:", "class Model(metaclass=Meta):", 1
            )
        )
    if (
        "e02_locked_provider/transforms.py" in wheel_sources
        and profile != "guarded-transform-provider-missing"
    ):
        wheel_sources["e02_locked_provider-1.0.dist-info/RECORD"] += (
            "e02_locked_provider/transforms.py,,\n"
        )
    wheel = root / "e02_locked_provider-1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for relative, content in wheel_sources.items():
            archive.writestr(relative, content)
            path = root / "site" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    if profile in {"guarded-none-import", "guarded-dynamic-failure"}:
        prerequisite = "SENTINEL = None\n"
        if profile == "guarded-dynamic-failure":
            prerequisite = (
                "import builtins\n"
                "if not getattr(builtins, '_e02_prerequisite_attempted', False):\n"
                "    builtins._e02_prerequisite_attempted = True\n"
                "    raise ModuleNotFoundError('first attempt')\n" + prerequisite
            )
        (root / "site/e02_unlocked_prerequisite.py").write_text(prerequisite)
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
def test_retained_guarded_optional_native_dependency_family() -> None:
    """Reconcile every real import in the guarded dependency facade without numerical work."""
    host = sys.modules.get("_polisyos_early_host")
    if host is None:
        pytest.skip("requires the selected early authority launcher")
    from polisyos.runtime.quality import confidence_ledger as ledger

    facade = importlib.import_module("polisyos.scientist.methods.search.strategies._deps")
    assert facade.TORCH_IMPORT_ERROR is None
    assert facade.BOTORCH_IMPORT_ERROR is None
    host.handoff_if_ready()
    root = ledger._loaded_policy_engine_root()
    analysis = ledger._IntegrityAnalysisContext()
    recorded = ledger._n5_locked_optional_imports(root, analysis)
    session = sys.__dict__["_polisyos_loaded_host_v1"]
    owner_path = Path(ledger.__file__).resolve()
    assert recorded is not None, {
        "owner_capture_state": session.get("owner_capture_state"),
        "owner_diagnostic": session.get("last_owner_diagnostic"),
        "owner_origin": str(owner_path),
        "owner_source_sha256": hashlib.sha256(owner_path.read_bytes()).hexdigest(),
    }
    assert owner_path == root / "src/polisyos/runtime/quality/confidence_ledger.py"
    assert (
        recorded.capture.completed(ledger.__name__).source_sha256
        == hashlib.sha256(owner_path.read_bytes()).hexdigest()
    )
    tree = analysis.source_tree(Path(facade.__file__))
    arms = ledger._source_locked_optional_arms(tree)
    assert len(arms) == 17  # Complete source-declared family, not a selected GP alias.
    index = ledger._AuthorityImportClosureSourceIndex({}, {}, n5_recorded_optional_imports=recorded)
    for export, arm in sorted(arms.items()):
        selected = vars(facade)[export]
        assert selected is not None
        statement, alias = arm.imports[export]
        provider = alias.name if isinstance(statement, ast.Import) else statement.module
        candidate = ledger._source_module_import_route_candidate(
            root,
            facade.__name__,
            export,
            directory_entries={},
            source_index=index,
            discovery_only=True,
        )
        assert candidate.route == (
            "external",
            provider,
            None if isinstance(statement, ast.Import) else alias.name,
        )
    analysis.assert_sources_unchanged()


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
fallback = profile in {"ordinary-fallback", "guarded-fallback", "guarded-ambiguous-failure"}
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
assert "SVC" in exports[wrapper]
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


def observe_guarded_family():
    if not fallback:
        sys.path.insert(0, str(site))
    selected_consumer = importlib.import_module("tools._e02_guarded_consumer")
    optional = importlib.import_module("tools._e02_guarded_optional")
    source_index = ledger._AuthorityImportClosureSourceIndex({}, {})
    try:
        ledger._resolve_authority_import_closure(root, selected_consumer.__name__, include_tools=True)
    except ledger.ConfidenceLedgerError:
        pass
    else:
        assert profile == "guarded-executed-class-default", "unrecorded guarded binding accepted"

    def member(name):
        retained = selector._selected.get(name)
        if retained is None:
            return None
        completed = capture.completed(name)
        assert selector.select(name, completed.origin, _retained_only=True) == retained[:2]
        return (name, *retained, hashlib.sha256(lock).hexdigest())

    def observe(member_reader=member, drop_events=False):
        analysis = ledger._IntegrityAnalysisContext()
        binding = ledger._N5LockedOptionalImports(root, analysis, capture, member_reader)
        if drop_events:
            binding.events.pop((optional.__name__, facade))
        if profile == "guarded-prerequisite-handler":
            index = ledger._AuthorityImportClosureSourceIndex({}, {}, n5_recorded_optional_imports=binding)
            ledger._source_module_import_route_candidate(root, optional.__name__, "Model", directory_entries={}, source_index=index, discovery_only=True)
            return []
        closure = ledger._resolve_authority_import_closure(root, selected_consumer.__name__, include_tools=True, _n5_optional_imports=binding)
        assert set(dict(closure)) == {"tools", optional.__name__, selected_consumer.__name__}
        index = ledger._AuthorityImportClosureSourceIndex({}, {}, n5_recorded_optional_imports=binding)
        for name in ("backend", "Model", "SVC", "calculate"):
            candidate = ledger._source_module_import_route_candidate(root, optional.__name__, name, directory_entries={}, source_index=index, discovery_only=True)
            value = vars(optional)[name]
            assert candidate.route == (("symbol", optional.__name__, name) if value is None else ("external", facade, None if name == "backend" else name))
        analysis.assert_sources_unchanged()
        return list(binding.rows.values())

    def refused(**kwargs):
        try:
            observe(**kwargs)
        except ledger.ConfidenceLedgerError as exc:
            assert exc.code == "canonical_loaded_runtime_mismatch", str(exc)
        else:
            raise AssertionError("unqualified guarded optional binding accepted")

    if profile in {"guarded-handler", "guarded-shadowed-raise", "guarded-call-guard", "guarded-prerequisite-handler", "guarded-none-import", "guarded-none-locked", "guarded-ambiguous-failure", "guarded-class-metaclass", "guarded-dynamic-failure", "guarded-builtin-alias", "guarded-module-descriptor", "guarded-transform-provider-missing"}:
        if profile in {"guarded-none-import", "guarded-dynamic-failure"}:
            assert optional.backend is None and "BACKEND_ERROR" not in vars(optional)
            assert any(event.importer_name == optional.__name__ and event.provider_name == "e02_unlocked_prerequisite" for event in capture.import_events())
            assert "e02_unlocked_prerequisite" not in selector._selected
        if profile == "guarded-class-metaclass":
            assert vars(sys.modules[terminal])["effects"] == []
        if profile == "guarded-module-descriptor":
            namespace = types.ModuleType.__dict__["__dict__"].__get__(sys.modules[terminal], types.ModuleType)
            before_effects = list(namespace["effects"])
        refused()
        if profile == "guarded-module-descriptor":
            assert namespace["effects"] == before_effects
        if profile == "guarded-class-metaclass":
            assert vars(sys.modules[terminal])["effects"] == []
        return
    if profile.startswith("guarded-structural-") or profile == "guarded-transform-factory-rebind":
        if profile == "guarded-structural-alias":
            refused()
            return
        rows = observe()
        raw = vars(optional.Model)["predict"]
        original = raw.fget if profile.endswith("property") else raw.__func__
        from functools import wraps
        @wraps(original)
        def malicious(*args, **kwargs): return -999
        if profile == "guarded-transform-factory-rebind":
            def replacement(*args, **kwargs): return None
            sys.modules[terminal].classmethod = sys.modules[facade + ".transforms"].borrowed = replacement
        if profile.endswith(("classmethod", "unresolved")) or profile == "guarded-transform-factory-rebind":
            optional.Model.predict = classmethod(malicious)
        elif profile.endswith("staticmethod"):
            optional.Model.predict = staticmethod(malicious)
        else:
            optional.Model.predict = property(malicious)
        assert (optional.Model().predict if profile.endswith("property") else optional.Model().predict()) == -999
        refused()
        return
    if profile == "guarded-executed-class-default":
        function = optional.Model.predict
        assert optional.Model().predict() == 17
        ledger._loaded_policy_engine_root = lambda: root
        ledger._n5_locked_optional_imports = lambda selected_root, analysis: ledger._N5LockedOptionalImports(root, analysis, capture, member)
        original_closure = ledger._resolve_authority_import_closure
        ledger._resolve_authority_import_closure = lambda selected_root, entries, **kwargs: original_closure(selected_root, entries, include_tools=True, **kwargs)
        def consume():
            return ledger.capture_execution_source_bindings((selected_consumer.__name__,), ((terminal, function.__code__),))
        original = consume()
        assert original["executed_code"]
        assert original["loaded_binding_scope"] == "current_source_owned_slots_for_observed_code_only"
        assert original["executed_function_identity"] == "not_established"
        assert original["executed_invocation_default_state"] == "not_established"
        detached = types.FunctionType(function.__code__, function.__globals__, function.__name__, (-999,))
        assert detached(optional.Model()) == -999 and optional.Model().predict() == 17
        assert consume()["executed_function_identity"] == "not_established"
        function.__defaults__ = (-999,)
        assert optional.Model().predict() == -999
        try:
            consume()
        except ledger.ConfidenceLedgerError as exc:
            assert exc.code == "n5_consumed_loaded_binding_mismatch", str(exc)
        else:
            raise AssertionError("changed external executed defaults accepted")
        return
    if profile in {"guarded-class-code", "guarded-class-default", "guarded-class-state", "guarded-class-kwdefault", "guarded-class-closure", "guarded-class-literal-state", "guarded-declared-transform", "guarded-undeclared-transform"}:
        rows = observe()
        if profile == "guarded-class-code":
            optional.Model.predict.__code__ = (lambda self, value=17: -999).__code__
            assert optional.Model().predict() == -999
        elif profile == "guarded-class-default":
            optional.Model.predict.__defaults__ = (-999,)
            assert optional.Model().predict() == -999
        elif profile == "guarded-class-kwdefault":
            optional.Model.predict.__kwdefaults__ = {"value": -999}
            assert optional.Model().predict() == -999
        elif profile == "guarded-class-closure":
            optional.Model.predict.__closure__[0].cell_contents = object
            assert optional.Model().predict() == 18
        elif profile == "guarded-class-literal-state":
            optional.Model.FACTOR = -999
        elif profile == "guarded-declared-transform":
            views = [view for row in rows for view in row.get("class_reference_observations", ())]
            assert any("declared_callable_transform_behavior" in view["unestablished"] for view in views)
            optional.Model.predict.__wrapped__.__defaults__ = (-999,)
            assert optional.Model().predict() == -999
        elif profile == "guarded-undeclared-transform":
            from functools import wraps
            original = optional.Model.predict
            @wraps(original)
            def wrapped(*args, **kwargs): return -999
            optional.Model.predict = wrapped
            assert optional.Model().predict() == -999
        else:
            optional.Model.injected = lambda self: -999
        refused()
        return
    rows = observe()
    assert len(rows) == 4
    expected_fallbacks = 4 if fallback else (1 if profile == "guarded-is-not-none" else 0)
    assert sum(row["wrapper_binding_disposition"] == "local_none_fallback" for row in rows) == expected_fallbacks
    assert all(row["wrapper_availability_export"] is None for row in rows)
    if fallback or profile in {"guarded-family", "guarded-is-not-none"}:
        return
    if profile == "guarded-alias":
        owner = sys.modules[terminal]
        original = owner.Model
        replacement = type("Model", (), {"predict": original.predict, "__module__": terminal})
        owner.Model = sys.modules[facade].Model = optional.Model = selected_consumer.Model = replacement
        refused()
    elif profile == "guarded-code":
        optional.calculate.__code__ = (lambda value=13: value + 99).__code__
        refused()
    elif profile == "guarded-default":
        optional.calculate.__defaults__ = (99,)
        refused()
    elif profile == "guarded-provider":
        refused(member_reader=lambda name: None if name == terminal else member(name))
    elif profile == "guarded-source":
        path = root / "tools/_e02_guarded_optional.py"
        path.write_text(path.read_text().replace("from e02_locked_provider import Model, SVC, calculate", "pass"))
        refused()
    elif profile == "guarded-prerequisite":
        optional.backend = types.ModuleType(facade)
        refused()
    elif profile == "guarded-events":
        refused(drop_events=True)
    else:
        raise AssertionError(profile)


if profile in {"flagged-guard", "flagged-bound-guard"}:
    sys.path.insert(0, str(site))
    importlib.import_module(consumer)
    analysis = ledger._IntegrityAnalysisContext()
    binding = ledger._N5LockedOptionalImports(root, analysis, capture, lambda name: (name, *selector._selected[name], hashlib.sha256(lock).hexdigest()) if name in selector._selected else None)
    try:
        ledger._resolve_authority_import_closure(root, consumer, include_tools=True, _n5_optional_imports=binding)
    except ledger.ConfidenceLedgerError as exc:
        assert profile == "flagged-guard" and exc.code == "canonical_loaded_runtime_mismatch", str(exc)
    else:
        assert profile == "flagged-bound-guard", "unqualified flagged prerequisite accepted"
    raise SystemExit(0)

if profile.startswith("guarded-"):
    observe_guarded_family()
    raise SystemExit(0)


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
    assert [row[0] for row in rows[0]["locked_class_imports"]] == ["Model", "SVC"]
    local, edges, members = rows[1]["locked_class_imports"][0]
    assert local == "Model"
    assert [(edge[0], edge[3:]) for edge in edges] == [
        (wrapper, (facade, "Model", "Model")), (facade, (terminal, "Model", "Model"))
    ]
    assert [row[0] for row in members] == [facade, terminal]
    assert all(row[3] == "sha256:" + hashlib.sha256(wheel).hexdigest() for row in members)
    if profile == "unconsumed-alias":
        wrapper_module = importlib.import_module(wrapper)
        provider_module = importlib.import_module(facade)
        assert "SVC" not in vars(actual)
        assert capture.completed_binding(wrapper, "SVC") is vars(provider_module)["SVC"]

        class ReplacementSVC:
            pass

        wrapper_module.SVC = ReplacementSVC
        try:
            capture.completed_binding(wrapper, "SVC")
        except recorder.CaptureError as exc:
            assert str(exc) == "retained_export_changed", str(exc)
        else:
            raise AssertionError("unconsumed optional alias replacement was not retained")
        raise SystemExit(0)
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
