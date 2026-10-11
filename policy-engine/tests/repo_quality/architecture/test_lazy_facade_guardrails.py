from __future__ import annotations

import ast
import importlib
import os
import runpy
import subprocess
import sys
import uuid
from pathlib import Path

from devx.architecture import guardrails


def _guardrails():
    candidate = os.environ.get("POLISYOS_VIRTUAL_GUARDRAILS")
    if not candidate:
        return guardrails
    spec = importlib.util.spec_from_file_location("_e02_virtual_guardrails", candidate)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.REPO_ROOT = REPO_ROOT
    module.SRC_ROOT = REPO_ROOT / "src"
    module.DEFAULT_PUBLIC_MANIFEST = REPO_ROOT / "architecture/public_surface/contract.toml"
    return module


REPO_ROOT = Path(os.environ.get("POLISYOS_TEST_REPO_ROOT", Path(__file__).resolve().parents[3]))
SRC_ROOT = REPO_ROOT / "src" / "polisyos"


LAZY_FACADE_CASES = {
    "polisyos.common": ("async_tools", "logger", "serialization"),
    "polisyos.core": ("discovery", "errors", "registry", "run"),
    "polisyos.core.contracts": ("chronology", "epoch"),
    "polisyos.data_forge.read_api": ("legal",),
}


def _facade_path(module: str) -> Path:
    relative = Path(*module.split("."))
    candidates = (SRC_ROOT / relative / "__init__.py", SRC_ROOT / f"{relative}.py")
    return next(path for path in candidates if path.is_file())


def test_lazy_module_facade_children_are_source_proved_and_not_deep_edges() -> None:
    guardrail_module = _guardrails()
    manifest = Path(
        os.environ.get(
            "POLISYOS_VIRTUAL_MANIFEST",
            REPO_ROOT / "architecture" / "public_surface" / "contract.toml",
        )
    )
    policies = guardrail_module._parse_public_surface(manifest)
    edges = guardrail_module.collect_deep_import_edges(policies)
    unresolved = {
        edge.target_module
        for edge in edges
        if edge.resolution_status == "not_established"
        and edge.resolution_reason == "export_manifest_unresolved"
    }
    expected = {f"{parent}.{name}" for parent, names in LAZY_FACADE_CASES.items() for name in names}
    documented = {
        "polisyos.fabric.connectors",
        "polisyos.fabric.data_plane",
        "polisyos.ir.analytics.calibration_diagnostics",
        "polisyos.ir.governance",
        "polisyos.ir.observation",
    }
    supported = {entrypoint for policy in policies for entrypoint in policy.supported_entrypoints}
    assert expected.isdisjoint(supported)
    assert documented <= supported
    assert "polisyos.fabric.ingestion" not in supported
    assert "polisyos.scientist.policy_design" not in supported
    assert len(expected) == 10
    assert not (unresolved & expected), sorted(unresolved & expected)
    internal_candidates = {
        "polisyos.fabric.ingestion",
        "polisyos.scientist.policy_design",
    }
    assert not (unresolved & internal_candidates), sorted(unresolved & internal_candidates)

    internal_consumers = {
        SRC_ROOT / "policy_grammar" / "_impl" / "schema.py": (
            "polisyos.scientist.policy_design",
            "policy_design",
        ),
        SRC_ROOT / "runtime" / "quality" / "acquisition_executor.py": (
            "polisyos.fabric.ingestion",
            "fabric_ingestion",
        ),
    }
    for source, (module_name, alias_name) in internal_consumers.items():
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        assert any(
            isinstance(node, ast.Import)
            and any(
                alias.name == module_name and alias.asname == alias_name for alias in node.names
            )
            for node in ast.walk(tree)
        ), (source, module_name, alias_name)


def test_loader_proof_follows_the_returned_module_and_rejects_helper_drift() -> None:
    prove = getattr(_guardrails(), "_facade_lazy_child_target", None)
    assert callable(prove), "the source-backed lazy child resolver is missing"
    source = SRC_ROOT / "example_facade" / "__init__.py"
    good = ast.parse(
        """
from importlib import import_module
__all__ = ("child",)
def _load_child(name):
    return import_module(f"{__name__}.{name}")
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    module = _load_child(name)
    return module
"""
    )
    drifted = ast.parse(
        """
from importlib import import_module
__all__ = ("child",)
def _load_child(name):
    return import_module(f"{__name__}.sibling")
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    module = _load_child(name)
    return module
"""
    )
    assert prove("polisyos.example_facade", source, good, "child") == (
        "polisyos.example_facade.child"
    )
    assert prove("polisyos.example_facade", source, drifted, "child") is None
    escaped_manifest = ast.parse(
        """
from importlib import import_module
__all__ = ("child",)
def _mutate(values):
    return values
_mutate(__all__)
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    module = import_module(f"{__name__}.{name}")
    return module
"""
    )
    assert prove("polisyos.example_facade", source, escaped_manifest, "child") is None
    indexed_mutation = ast.parse(
        """
from importlib import import_module
__all__ = ["child"]
__all__[0] = "sibling"
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return import_module(f"{__name__}.{name}")
"""
    )
    assert prove("polisyos.example_facade", source, indexed_mutation, "child") is None
    early_exception = ast.parse(
        """
from importlib import import_module
__all__ = ("child",)
def _load_child(name):
    if name == "child":
        raise AttributeError(name)
    return import_module(f"{__name__}.{name}")
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return _load_child(name)
"""
    )
    assert prove("polisyos.example_facade", source, early_exception, "child") is None

    surfaces = SRC_ROOT / "data_forge" / "read_api" / "surfaces.py"
    records = getattr(_guardrails(), "_read_api_surface_records", None)
    assert callable(records)
    actual_tree = ast.parse(surfaces.read_text(encoding="utf-8"))
    assert records(surfaces, actual_tree)["legal"] == "polisyos.data_forge.read_api.legal"
    mutable_records_tree = ast.parse(
        surfaces.read_text(encoding="utf-8").replace(
            "@dataclass(frozen=True, slots=True)", "@dataclass(slots=True)"
        )
    )
    assert records(surfaces, mutable_records_tree) is None


def test_internal_markdown_is_not_admitted_by_child_existence_or_fromlist_fallback() -> None:
    source = SRC_ROOT / "common" / "__init__.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    prove = getattr(_guardrails(), "_facade_lazy_child_target", None)
    assert callable(prove), "the source-backed lazy child resolver is missing"
    assert (SRC_ROOT / "common" / "markdown.py").is_file()
    assert prove("polisyos.common", source, tree, "markdown") is None

    script = """
import importlib, sys
parent = importlib.import_module('polisyos.common')
assert 'markdown' not in parent.__all__
assert 'polisyos.common.markdown' not in sys.modules
namespace = {}
exec('from polisyos.common import markdown', namespace)
assert namespace['markdown'] is importlib.import_module('polisyos.common.markdown')
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(REPO_ROOT / "src"), str(REPO_ROOT)))
    subprocess.run([sys.executable, "-c", script], cwd=REPO_ROOT, env=env, check=True)


def test_runtime_lazy_facades_return_the_exact_child_objects_in_cold_order() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(REPO_ROOT / "src"), str(REPO_ROOT)))
    for parent_name, names in LAZY_FACADE_CASES.items():
        for name in names:
            child = f"{parent_name}.{name}"
            script = f"""
import importlib, sys
parent = importlib.import_module({parent_name!r})
child = {child!r}
name = {name!r}
assert name in parent.__all__
assert child not in sys.modules
assert name not in vars(parent)
resolved = getattr(parent, name)
assert resolved is importlib.import_module(child)
"""
            subprocess.run(
                [sys.executable, "-c", script],
                cwd=REPO_ROOT,
                env=env,
                check=True,
            )


def _run_synthetic_facade(source_path: Path, source_text: str) -> dict[str, object]:
    real_parent = sys.modules.get("polisyos.common")
    trusted_source = '__name__ = "polisyos.common"\n' + source_text
    source_path.write_text(trusted_source, encoding="utf-8")
    run_name = f"_e02_synthetic_facade_{uuid.uuid4().hex}"
    namespace = runpy.run_path(str(source_path), run_name=run_name)
    assert namespace["__name__"] == "polisyos.common"
    assert sys.modules.get("polisyos.common") is real_parent
    assert real_parent is None or hasattr(real_parent, "__path__")
    return namespace


def test_namespace_reflection_rebinding_and_unproven_loader_effects_are_not_proved(
    tmp_path: Path,
) -> None:
    guardrail_module = _guardrails()
    prove = getattr(guardrail_module, "_facade_lazy_child_target", None)
    assert callable(prove)
    source = SRC_ROOT / "common" / "__init__.py"
    cases = {
        "string_key_rebind": """from importlib import import_module
__all__ = ("logger",)
globals()["__all__"] = ()
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return import_module(f"{__name__}.{name}")
""",
        "aliased_namespace_write": """from importlib import import_module
__all__ = ("logger",)
namespace = globals()
namespace["__all__"] = ()
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return import_module(f"{__name__}.{name}")
""",
        "mutating_helper_before_loader_return": """from importlib import import_module
__all__ = ("logger",)
def _load(name):
    globals()["__all__"] = ()
    return import_module(f"{__name__}.{name}")
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return _load(name)
""",
        "unknown_helper_prefix": """from importlib import import_module
__all__ = ("logger",)
def _touch():
    return None
def __getattr__(name):
    _touch()
    if name not in __all__:
        raise AttributeError(name)
    return import_module(f"{__name__}.{name}")
""",
        "global_export_tuple_rebind": """from importlib import import_module
__all__ = ("logger",)
def _reset_exports():
    global __all__
    __all__ = ()
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return import_module(f"{__name__}.{name}")
""",
        "global_loader_binding_rebind": """from importlib import import_module
__all__ = ("logger",)
def _reset_loader():
    global import_module
    import_module = lambda value: None
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return import_module(f"{__name__}.{name}")
""",
        "nested_global_export_rebind": """from importlib import import_module
__all__ = ("logger",)
def _reset_exports():
    def reset():
        global __all__
        __all__ = ()
    reset()
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return import_module(f"{__name__}.{name}")
""",
        "callable_module_attribute_rebind": """import polisyos.common as facade
from importlib import import_module
__all__ = ("logger",)
def _reset_exports():
    facade.__all__ = ()
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return import_module(f"{__name__}.{name}")
""",
        "module_importer_attribute_rebind": """import importlib
importlib.import_module = lambda name: None
__all__ = ("logger",)
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return importlib.import_module(f"{__name__}.{name}")
""",
        "loader_helper_side_effect": """from importlib import import_module
__all__ = ("logger",)
def _touch():
    return None
def _load(name):
    _touch()
    return import_module(f"{__name__}.{name}")
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return _load(name)
""",
        "returned_export_collection_mutated_through_helper": """from importlib import import_module
__all__ = ["logger"]
def _export_values():
    return __all__
def _reset_exports():
    _export_values().clear()
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return import_module(f"{__name__}.{name}")
""",
        "sys_modules_export_mutator": """import sys
from importlib import import_module
__all__ = ("logger",)
sys.modules[__name__].__all__.clear()
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return import_module(f"{__name__}.{name}")
""",
        "dynamic_sys_modules_export_mutator": """import sys
from importlib import import_module
__all__ = ("logger",)
def _reset_exports():
    getattr(sys, "modules")[__name__].__all__.clear()
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return import_module(f"{__name__}.{name}")
""",
        "dynamic_reflection_alias": """from builtins import globals as namespace
from importlib import import_module
__all__ = ("logger",)
namespace()["__all__"] = ()
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return import_module(f"{__name__}.{name}")
""",
        "getter_reflection_before_membership": """from importlib import import_module
__all__ = ("logger",)
def __getattr__(name):
    globals()["__all__"] = ()
    if name not in __all__:
        raise AttributeError(name)
    return import_module(f"{__name__}.{name}")
""",
        "sys_modules_rebind": """import sys
from importlib import import_module
__all__ = ("logger",)
sys.modules[__name__].__all__ = ()
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return import_module(f"{__name__}.{name}")
""",
        "builtins_registry_lookup": """import builtins
from importlib import import_module
__all__ = ("logger",)
namespace = getattr(builtins, "globals")()
namespace["__all__"] = ()
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    return import_module(f"{__name__}.{name}")
""",
    }
    for label, text in cases.items():
        tree = ast.parse(text)
        assert prove("polisyos.common", source, tree, "logger") is None, label

    safe_cached_child = ast.parse(
        """from importlib import import_module
__all__ = ("logger",)
def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    module = import_module(f"{__name__}.{name}")
    globals()[name] = module
    return module
"""
    )
    assert prove("polisyos.common", source, safe_cached_child, "logger") == (
        "polisyos.common.logger"
    )

    runtime_rebind = cases["global_export_tuple_rebind"]
    namespace = _run_synthetic_facade(tmp_path / "synthetic-facade.py", runtime_rebind)
    assert namespace["__getattr__"]("logger") is importlib.import_module("polisyos.common.logger")
    namespace["_reset_exports"]()
    try:
        namespace["__getattr__"]("logger")
    except AttributeError:
        pass
    else:
        raise AssertionError("the falsifier should reject the child after rebind")

    runtime_alias_mutation = cases["returned_export_collection_mutated_through_helper"]
    alias_namespace = _run_synthetic_facade(
        tmp_path / "synthetic-facade-alias.py", runtime_alias_mutation
    )
    assert alias_namespace["__getattr__"]("logger") is importlib.import_module(
        "polisyos.common.logger"
    )
    alias_namespace["_reset_exports"]()
    try:
        alias_namespace["__getattr__"]("logger")
    except AttributeError:
        pass
    else:
        raise AssertionError("the alias-mutation falsifier should reject the child after mutation")
