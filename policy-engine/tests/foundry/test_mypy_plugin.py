"""
Tests for the @foundry_method mypy plugin (T4.1).

Strategy
--------
The plugin runs *during mypy's type-checking phase*, not at pytest time.
Testing mypy plugins directly requires either:
  a) pytest-mypy-plugins (YAML-driven inline type tests), or
  b) Programmatic subprocess invocation of mypy on small test snippets.

We use approach (b) here: each test writes a tiny Python module to a temp
directory and runs mypy on it, then asserts on the exit code and output.

The tests are marked @pytest.mark.integration so they can be skipped in
fast local loops:
    pytest tests/foundry/test_mypy_plugin.py -m integration

Requirements:
    mypy must be installed (it is in the ``dev`` extra).
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_mypy(tmp_path: Path, source: str) -> tuple[int, str]:
    """Write *source* to a temp .py file and run mypy on it.

    Returns (exit_code, combined_stdout+stderr).
    """
    import os

    module_file = tmp_path / "subject.py"
    module_file.write_text(textwrap.dedent(source), encoding="utf-8")

    # mypy 1.x removed --plugins CLI flag; configure via inline config file.
    config_file = tmp_path / "mypy.ini"
    config_file.write_text(
        "[mypy]\nplugins = polisyos.foundry.methods.mypy_plugin\n",
        encoding="utf-8",
    )

    # Include the project src on PYTHONPATH so mypy can resolve polisyos and
    # load the plugin (requires py.typed marker for full FQN resolution).
    src_root = str(Path(__file__).resolve().parents[3] / "src")
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_root}:{existing}" if existing else src_root

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--no-error-summary",
            "--ignore-missing-imports",
            "--config-file",
            str(config_file),
            str(module_file),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    output = result.stdout + result.stderr
    return result.returncode, output


def _mypy_available() -> bool:
    try:
        subprocess.run(
            [sys.executable, "-m", "mypy", "--version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


_SKIP = pytest.mark.skipif(not _mypy_available(), reason="mypy not installed")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@_SKIP
@pytest.mark.integration
class TestFoundryMethodPlugin:
    def test_valid_method_passes(self, tmp_path: Path) -> None:
        """A correctly defined @foundry_method class should pass mypy."""
        code = """
            from polisyos.foundry.methods.base import (
                MethodSignature, MethodMetadata, FidelityLevel, ComplexityClass,
                foundry_method,
            )
            from polisyos.foundry.methods.base import SlotSpec, SlotType, Unit

            _slot = SlotSpec(
                name="outcome",
                slot_type=SlotType.VECTOR,
                unit=Unit("dimensionless", "1"),
            )

            @foundry_method(namespace="test", version="1.0.0")
            class GoodMethod:
                signature = MethodSignature(
                    name="good",
                    namespace="",
                    version="0.0.0",
                    input_slots=frozenset({_slot}),
                    output_slots=frozenset({_slot}),
                    parameters=(),
                    fidelity=FidelityLevel.LOW,
                    complexity=ComplexityClass.O_N,
                )
                metadata = MethodMetadata(author="test", description="ok")

                @staticmethod
                def pure_step(state, params):
                    return {}
        """
        code_rc, output = _run_mypy(tmp_path, code)
        # May have import or other non-plugin errors, but plugin should not add its own
        plugin_errors = [
            line
            for line in output.splitlines()
            if "must define" in line or "must be a @staticmethod" in line
        ]
        assert plugin_errors == [], f"Plugin raised unexpected errors:\n{output}"

    def test_missing_signature_is_flagged(self, tmp_path: Path) -> None:
        """A class missing ``signature`` should get a mypy error."""
        code = """
            from polisyos.foundry.methods.base import (
                MethodMetadata, foundry_method,
            )

            @foundry_method(namespace="test", version="1.0.0")
            class NoSignatureMethod:
                metadata = MethodMetadata(author="x", description="y")

                @staticmethod
                def pure_step(state, params):
                    return {}
        """
        _code_rc, output = _run_mypy(tmp_path, code)
        assert "signature" in output, f"Expected error about missing 'signature', got:\n{output}"

    def test_missing_pure_step_is_flagged(self, tmp_path: Path) -> None:
        """A class missing ``pure_step`` should get a mypy error."""
        code = """
            from polisyos.foundry.methods.base import (
                MethodSignature, MethodMetadata, FidelityLevel, ComplexityClass,
                foundry_method,
            )
            from polisyos.foundry.methods.base import SlotSpec, SlotType, Unit

            _slot = SlotSpec(
                name="outcome",
                slot_type=SlotType.VECTOR,
                unit=Unit("dimensionless", "1"),
            )

            @foundry_method(namespace="test", version="1.0.0")
            class NoPureStepMethod:
                signature = MethodSignature(
                    name="nops",
                    namespace="",
                    version="0.0.0",
                    input_slots=frozenset({_slot}),
                    output_slots=frozenset({_slot}),
                    parameters=(),
                    fidelity=FidelityLevel.LOW,
                    complexity=ComplexityClass.O_N,
                )
                metadata = MethodMetadata(author="x", description="y")
                # no pure_step!
        """
        _code_rc, output = _run_mypy(tmp_path, code)
        assert "pure_step" in output, f"Expected error about missing 'pure_step', got:\n{output}"


class TestPluginImport:
    """Fast non-mypy tests that verify the plugin module can be imported."""

    def test_plugin_function_exists(self) -> None:
        from polisyos.foundry.methods.mypy_plugin import FoundryMethodPlugin, plugin

        assert callable(plugin)
        assert issubclass(FoundryMethodPlugin, object)

    def test_plugin_returns_class(self) -> None:
        from polisyos.foundry.methods.mypy_plugin import FoundryMethodPlugin, plugin

        result = plugin("1.10.0")
        assert result is FoundryMethodPlugin

    def test_hook_returns_none_for_unknown_decorator(self) -> None:
        from mypy.options import Options

        from polisyos.foundry.methods.mypy_plugin import FoundryMethodPlugin

        p = FoundryMethodPlugin(Options())
        result = p.get_class_decorator_hook("some.other.decorator")
        assert result is None

    def test_hook_returns_callable_for_foundry_method(self) -> None:
        from mypy.options import Options

        from polisyos.foundry.methods.mypy_plugin import (
            _FOUNDRY_METHOD_DECORATOR,
            FoundryMethodPlugin,
        )

        p = FoundryMethodPlugin(Options())
        result = p.get_class_decorator_hook(_FOUNDRY_METHOD_DECORATOR)
        assert callable(result)
