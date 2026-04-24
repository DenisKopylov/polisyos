"""Runtime helpers shared across benchmark entrypoints."""

from __future__ import annotations

import enum
import importlib
import json
import os
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class BenchmarkMode(str, enum.Enum):
    SMOKE = "smoke"
    ACCEPTANCE = "acceptance"


class BenchmarkTier(str, enum.Enum):
    LOCAL_EVIDENCE = "local_evidence"
    RESEARCH_ACCEPTANCE = "research_acceptance"


@dataclass(frozen=True)
class ModuleProbe:
    module_name: str
    available: bool
    status: str
    error: str | None = None
    python_executable: str | None = None


def resolve_mode(raw: str | None = None) -> BenchmarkMode:
    value = (raw or os.environ.get("BENCH_MODE", BenchmarkMode.SMOKE.value)).strip().lower()
    try:
        return BenchmarkMode(value)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in BenchmarkMode)
        raise ValueError(f"Unknown benchmark mode {value!r}; expected one of: {allowed}") from exc


def resolve_tier(
    raw: str | None = None,
    *,
    mode: BenchmarkMode | str | None = None,
) -> BenchmarkTier:
    if isinstance(mode, str):
        mode = resolve_mode(mode)
    resolved_mode = mode or resolve_mode()
    default_value = (
        BenchmarkTier.RESEARCH_ACCEPTANCE.value
        if resolved_mode is BenchmarkMode.ACCEPTANCE
        else BenchmarkTier.LOCAL_EVIDENCE.value
    )
    value = (raw or os.environ.get("BENCH_TIER", default_value)).strip().lower()
    try:
        return BenchmarkTier(value)
    except ValueError as exc:
        allowed = ", ".join(tier.value for tier in BenchmarkTier)
        raise ValueError(f"Unknown benchmark tier {value!r}; expected one of: {allowed}") from exc


def probe_module(
    module_name: str,
    *,
    python_executable: str | None = None,
) -> ModuleProbe:
    if (
        python_executable is None
        or Path(python_executable).resolve() == Path(sys.executable).resolve()
    ):
        try:
            importlib.import_module(module_name)
            return ModuleProbe(
                module_name=module_name,
                available=True,
                status="available",
                python_executable=sys.executable,
            )
        except ModuleNotFoundError as exc:
            return ModuleProbe(
                module_name=module_name,
                available=False,
                status="missing",
                error=f"{type(exc).__name__}: {exc}",
                python_executable=sys.executable,
            )
        except Exception as exc:
            return ModuleProbe(
                module_name=module_name,
                available=False,
                status="import_error",
                error=f"{type(exc).__name__}: {exc}",
                python_executable=sys.executable,
            )

    python_path = Path(python_executable).expanduser()
    if not python_path.exists():
        return ModuleProbe(
            module_name=module_name,
            available=False,
            status="missing_python",
            error=f"python executable not found: {python_path}",
            python_executable=str(python_path),
        )
    probe_program = (
        "import importlib, json, sys\n"
        "module = sys.argv[1]\n"
        "try:\n"
        "    importlib.import_module(module)\n"
        "    payload = {'available': True, 'status': 'available', 'error': None}\n"
        "except ModuleNotFoundError as exc:\n"
        "    payload = {'available': False, 'status': 'missing', 'error': f'{type(exc).__name__}: {exc}'}\n"
        "except Exception as exc:\n"
        "    payload = {'available': False, 'status': 'import_error', 'error': f'{type(exc).__name__}: {exc}'}\n"
        "print(json.dumps(payload))\n"
    )
    try:
        completed = subprocess.run(
            [str(python_path), "-c", probe_program, module_name],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        return ModuleProbe(
            module_name=module_name,
            available=False,
            status="probe_error",
            error=f"{type(exc).__name__}: {exc}",
            python_executable=str(python_path),
        )
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        return ModuleProbe(
            module_name=module_name,
            available=False,
            status="probe_error",
            error=stderr or f"probe exited with code {completed.returncode}",
            python_executable=str(python_path),
        )
    try:
        payload = json.loads((completed.stdout or "").strip() or "{}")
    except Exception as exc:
        return ModuleProbe(
            module_name=module_name,
            available=False,
            status="probe_error",
            error=f"invalid probe output: {type(exc).__name__}: {exc}",
            python_executable=str(python_path),
        )
    return ModuleProbe(
        module_name=module_name,
        available=bool(payload.get("available", False)),
        status=str(payload.get("status") or "missing"),
        error=str(payload.get("error")) if payload.get("error") else None,
        python_executable=str(python_path),
    )


def module_available(module_name: str, *, python_executable: str | None = None) -> bool:
    try:
        return probe_module(module_name, python_executable=python_executable).available
    except Exception:
        return False


def dependency_status(module_names: Iterable[str]) -> dict[str, str]:
    return {name: probe_module(name).status for name in module_names}


def classify_data_source(
    *, has_real_data: bool, synthetic_label: str = "synthetic", real_label: str = "real"
) -> str:
    return real_label if has_real_data else synthetic_label


def acceptance_gaps(
    mode: BenchmarkMode,
    *,
    tier: BenchmarkTier | None = None,
    require_real_data: bool = False,
    has_real_data: bool = False,
    require_modules: dict[str, bool] | None = None,
) -> list[str]:
    strict_tier = tier or resolve_tier(mode=mode)
    if (
        mode is not BenchmarkMode.ACCEPTANCE
        and strict_tier is not BenchmarkTier.RESEARCH_ACCEPTANCE
    ):
        return []

    gaps: list[str] = []
    if require_real_data and not has_real_data:
        gaps.append("real benchmark dataset is required in acceptance mode")
    for name, available in (require_modules or {}).items():
        if not available:
            gaps.append(f"required comparator/dependency missing: {name}")
    return gaps


def env_path_status(var_name: str) -> dict[str, Any]:
    raw = os.environ.get(var_name, "")
    path = Path(raw).expanduser() if raw else None
    exists = bool(path and path.exists())
    return {
        "env_var": var_name,
        "configured": bool(raw),
        "path": str(path) if path else None,
        "exists": exists,
    }
