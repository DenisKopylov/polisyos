"""Behavioral checks for Common's package-preserving implementation routes."""

from __future__ import annotations

import ast
import importlib
import inspect
import pickle
import subprocess
import sys
import textwrap
from pathlib import Path

_PACKAGE_NAMES = ("async_tools", "config", "jax_env", "logger", "serialization", "timestamps")
_PUBLIC_DECLARATIONS = {
    "async_tools": {
        "SharedExecutorConfigurationError",
        "SharedExecutorProfile",
        "SharedExecutorReentrancyError",
        "resolve_shared_executor_profile",
        "configure_shared_executor_profile",
        "get_shared_executor_profile",
        "shutdown_run_coro_sync_executor",
        "get_shared_executor",
        "is_current_shared_executor_worker",
        "run_shared_executor_sync",
        "run_coro_sync",
        "run_blocking_async",
    },
    "config": {
        "EnvVarSpec",
        "ProcessBootstrapConfig",
        "parse_bool",
        "parse_int",
        "get_env_registry",
        "build_process_bootstrap_config",
        "validate_process_bootstrap_config",
        "apply_process_bootstrap",
        "configure_logging",
        "current_runtime_toggles",
    },
    "jax_env": {"apply_jax_env_defaults"},
    "logger": {"get_logger"},
    "serialization": {
        "SerializationError",
        "SerializationCycleError",
        "SerializationDepthError",
        "UnsupportedSerializationError",
        "ArtifactIdentityProjectionError",
        "SerializationPolicy",
        "JsonDataVisitor",
        "artifact_self_identity_projection",
        "to_python_data",
        "strip_none",
        "stable_json_dumps",
        "fast_json_dumps_bytes",
        "fast_json_dumps",
        "decode_json_object",
        "fast_json_loads",
        "extract_llm_json",
        "extract_llm_json_object",
    },
    "text": {"collapse_ws"},
    "timestamps": {
        "utc_now",
        "ensure_utc",
        "to_iso_utc",
        "parse_iso_datetime",
        "parse_iso_date",
        "latest_object_by_subject",
        "to_epoch_seconds",
        "from_epoch_seconds",
    },
}
_EXPLICIT_ALL = {
    "config": {
        "EnvVarSpec",
        "ProcessBootstrapConfig",
        "apply_process_bootstrap",
        "build_process_bootstrap_config",
        "configure_logging",
        "current_runtime_toggles",
        "get_env_registry",
        "validate_process_bootstrap_config",
    },
    "serialization": {
        "JsonDataVisitor",
        "SerializationCycleError",
        "SerializationDepthError",
        "SerializationError",
        "SerializationPolicy",
        "UnsupportedSerializationError",
        "decode_json_object",
        "extract_llm_json",
        "extract_llm_json_object",
        "fast_json_dumps",
        "fast_json_dumps_bytes",
        "fast_json_loads",
        "stable_json_dumps",
        "strip_none",
        "to_python_data",
    },
    "text": {"collapse_ws"},
    "timestamps": {
        "ensure_utc",
        "from_epoch_seconds",
        "latest_object_by_subject",
        "parse_iso_date",
        "parse_iso_datetime",
        "to_epoch_seconds",
        "to_iso_utc",
        "utc_now",
    },
}


def test_common_helper_modules_keep_their_facade_identity_as_packages() -> None:
    """The existing lazy facade resolves each moved owner to its same FQN."""
    common = importlib.import_module("polisyos.common")
    for name in _PACKAGE_NAMES:
        qualified = f"polisyos.common.{name}"
        module = importlib.import_module(qualified)
        assert module.__name__ == qualified
        assert getattr(common, name) is module
        assert module.__spec__ is not None
        assert module.__spec__.submodule_search_locations is not None
        assert module.__file__ is not None
        assert Path(module.__file__).name == "__init__.py"


def test_common_classes_are_defined_and_reflectable_at_their_owner_fqn() -> None:
    """Class source, natural module identity, and pickle lookup use the owner body."""
    for name in _PACKAGE_NAMES:
        module = importlib.import_module(f"polisyos.common.{name}")
        assert module.__file__ is not None
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            cls = getattr(module, node.name)
            assert isinstance(cls, type)
            assert cls.__module__ == module.__name__
            body = inspect.getsource(cls)
            assert any(line.lstrip().startswith(f"class {node.name}") for line in body.splitlines())
            # The object is a local imported class; this round-trip pins its owner binding.
            assert pickle.loads(pickle.dumps(cls)) is cls  # noqa: S301


def test_common_package_public_declarations_and_explicit_all_are_preserved() -> None:
    """Extracted internals do not become new root bindings or public declarations."""
    for name, expected in _PUBLIC_DECLARATIONS.items():
        module = importlib.import_module(f"polisyos.common.{name}")
        tree = ast.parse(Path(module.__file__ or "").read_text(encoding="utf-8"))
        found = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        }
        assert found == expected
    for name, expected in _EXPLICIT_ALL.items():
        assert set(importlib.import_module(f"polisyos.common.{name}").__all__) == expected
    assert not hasattr(importlib.import_module("polisyos.common.config"), "configure_logging_sinks")
    assert not hasattr(
        importlib.import_module("polisyos.common.jax_env"), "should_default_cpu_backend"
    )
    assert not hasattr(importlib.import_module("polisyos.common.serialization"), "load_strict_json")


def test_common_text_facade_is_lazy_and_removal_probe_rejects_missing_route() -> None:
    """The child is lazy, and its actual binding is controlled by the facade list."""
    script = textwrap.dedent(
        """
        import importlib
        import sys

        common = importlib.import_module("polisyos.common")
        assert "polisyos.common.text" not in sys.modules
        assert "text" in common.__all__

        text_module = getattr(common, "text")
        assert text_module is importlib.import_module("polisyos.common.text")
        assert common.text is text_module

        # Keep the module source available but remove the facade property.
        common.__all__.remove("text")
        common.__dict__.pop("text")
        sys.modules.pop("polisyos.common.text")
        try:
            getattr(common, "text")
        except AttributeError:
            pass
        else:
            raise AssertionError("facade admitted a child absent from __all__")
        """
    )
    subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True)
