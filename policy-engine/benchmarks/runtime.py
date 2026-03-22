"""Runtime helpers shared across benchmark entrypoints."""

from __future__ import annotations

import enum
import importlib
import os
from pathlib import Path
from typing import Any, Iterable


class BenchmarkMode(str, enum.Enum):
    SMOKE = "smoke"
    ACCEPTANCE = "acceptance"


class BenchmarkTier(str, enum.Enum):
    LOCAL_EVIDENCE = "local_evidence"
    RESEARCH_ACCEPTANCE = "research_acceptance"


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


def module_available(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def dependency_status(module_names: Iterable[str]) -> dict[str, str]:
    return {
        name: ("available" if module_available(name) else "missing")
        for name in module_names
    }


def classify_data_source(*, has_real_data: bool, synthetic_label: str = "synthetic", real_label: str = "real") -> str:
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
    if mode is not BenchmarkMode.ACCEPTANCE and strict_tier is not BenchmarkTier.RESEARCH_ACCEPTANCE:
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
