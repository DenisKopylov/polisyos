"""Strict consumers for the registered and structural Foundry compiler contracts."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

PRODUCT_ROOT = Path(__file__).resolve().parents[3]

_POSITIVE_CLIENT = """\
from collections.abc import Mapping
from typing import Any, ClassVar, assert_type
from polisyos.foundry.methods.base import FoundryMethod, MethodMetadata, MethodSignature
from polisyos.foundry.methods.compiler import FoundryMethodProtocol, MethodCompiler
from polisyos.foundry.methods.compiler.specialization import Specialization
from polisyos.foundry.methods.selection.registry import MethodRegistry

class SpecializedRegistered:
    signature: ClassVar[MethodSignature]
    metadata: ClassVar[MethodMetadata]

    @staticmethod
    def pure_step(state: int, params: dict[str, int]) -> int:
        return state + params["delta"]

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> Any:
        return bound_inputs if bound_inputs else fallback_state

    @staticmethod
    def dematerialize_output(output: Any) -> Mapping[str, Any]:
        return {"value": output}

class LegacyStructural:
    signature: MethodSignature

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> Any:
        return state

def witness(registry: MethodRegistry, compiler: MethodCompiler, signature: MethodSignature,
            specialization: Specialization) -> None:
    registry.register(SpecializedRegistered)
    registered = registry.get(signature.fqn)
    assert_type(registered, type[FoundryMethod[Any, Any]])
    legacy: type[FoundryMethodProtocol] = LegacyStructural
    compiler._compile_method(registered, signature, specialization, {}, {}, (), False, False, None, ())
    compiler._compile_method(legacy, signature, specialization, {}, {}, (), False, False, None, ())
"""

_NEGATIVE_CLIENT = """\
from polisyos.foundry.methods.base import MethodSignature
from polisyos.foundry.methods.compiler import MethodCompiler
from polisyos.foundry.methods.compiler.specialization import Specialization

class WrongStep:
    @staticmethod
    def pure_step(state: str) -> str:
        return state

def witness(compiler: MethodCompiler, signature: MethodSignature,
            specialization: Specialization) -> None:
    compiler._compile_method(WrongStep, signature, specialization, {}, {}, (), False, False, None, ())
"""


def _run_mypy(
    tmp_path: Path, name: str, source: str, *, owners: bool
) -> subprocess.CompletedProcess[bytes]:
    client = tmp_path / (name + ".py")
    client.write_text(source, encoding="utf-8")
    command = [
        sys.executable,
        "-B",
        "-m",
        "mypy",
        "--no-fast-exit",
        "--config-file",
        str(PRODUCT_ROOT / "mypy.ini"),
        "--strict",
        "--cache-dir",
        str(tmp_path / "mypy-cache"),
    ]
    if owners:
        command += [
            "src/polisyos/foundry/methods/backends/chain_executor.py",
            "src/polisyos/foundry/methods/compiler/__init__.py",
        ]
    command.append(str(client))
    try:
        result = subprocess.run(
            command, cwd=PRODUCT_ROOT, capture_output=True, check=False, timeout=120
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        stdout = exc.stdout if isinstance(exc, subprocess.TimeoutExpired) else None
        stderr = exc.stderr if isinstance(exc, subprocess.TimeoutExpired) else None
        (tmp_path / (name + ".stdout.txt")).write_bytes(stdout or b"")
        (tmp_path / (name + ".stderr.txt")).write_bytes(stderr or b"")
        (tmp_path / (name + ".invocation.json")).write_text(
            json.dumps(
                {
                    "argv": command,
                    "cwd": str(PRODUCT_ROOT),
                    "status": "ERROR",
                    "exception": repr(exc),
                    "client_sha256": hashlib.sha256(client.read_bytes()).hexdigest(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        raise
    (tmp_path / (name + ".stdout.txt")).write_bytes(result.stdout)
    (tmp_path / (name + ".stderr.txt")).write_bytes(result.stderr)
    receipt = {
        "argv": command,
        "cwd": str(PRODUCT_ROOT),
        "returncode": result.returncode,
        "client": str(client),
        "client_sha256": hashlib.sha256(client.read_bytes()).hexdigest(),
        "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
    }
    (tmp_path / (name + ".invocation.json")).write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    return result


def test_actual_registry_compiler_and_fusion_owners_pass_strict_consumers(tmp_path: Path) -> None:
    """The real owners and specialized/legacy consumers remain strict-compatible."""
    positive = _run_mypy(tmp_path, "positive", _POSITIVE_CLIENT, owners=True)
    positive_output = (positive.stdout + positive.stderr).decode("utf-8", errors="replace")
    assert positive.returncode == 0, positive_output

    negative = _run_mypy(tmp_path, "negative", _NEGATIVE_CLIENT, owners=False)
    negative_output = (negative.stdout + negative.stderr).decode("utf-8", errors="replace")
    errors = [
        line
        for line in negative.stdout.decode("utf-8", errors="replace").splitlines()
        if ": error:" in line
    ]
    assert negative.returncode == 1, negative_output
    assert len(errors) == 1, negative_output
    assert "negative.py:" in errors[0] and '"_compile_method"' in errors[0]
    assert "[arg-type]" in errors[0], errors[0]
