"""Normalize symbolic transport formulas and resolve the executable symbolic backend."""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass

_VALID_SYMBOLIC_BACKEND_MODES: frozenset[str] = frozenset({"auto", "y0", "r", "full_auto"})


@dataclass(frozen=True)
class SymbolicBackendResolution:
    """Record which symbolic backend was selected and why a fallback was needed."""

    requested: str
    selected: str | None
    order: tuple[str, ...]
    unavailable_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class NormalizedTransportFormula:
    """Store a transport estimand in backend-normalized text plus metadata form."""

    formula_str: str
    stratification_variables: tuple[str, ...]
    target_quantities: tuple[str, ...]
    source_quantities: tuple[str, ...]


def normalize_symbolic_backend_mode(raw: object) -> str:
    """Normalize symbolic backend mode helper."""
    token = str(raw or "auto").strip().lower()
    if token not in _VALID_SYMBOLIC_BACKEND_MODES:
        return "auto"
    return token


def resolve_symbolic_backend(mode: object) -> SymbolicBackendResolution:
    """Resolve symbolic backend."""
    normalized = normalize_symbolic_backend_mode(mode)
    order = _backend_order(normalized)
    unavailable_reasons: list[str] = []
    for backend in order:
        ok, reason = probe_backend_availability(backend)
        if ok:
            return SymbolicBackendResolution(
                requested=normalized,
                selected=backend,
                order=order,
                unavailable_reasons=tuple(unavailable_reasons),
            )
        if reason:
            unavailable_reasons.append(reason)
    return SymbolicBackendResolution(
        requested=normalized,
        selected=None,
        order=order,
        unavailable_reasons=tuple(unavailable_reasons),
    )


def probe_backend_availability(backend: str) -> tuple[bool, str | None]:
    """Probe backend availability helper."""
    token = str(backend).strip().lower()
    if token == "y0":
        return _probe_y0()
    if token == "r":
        return _probe_r()
    return False, f"unsupported_symbolic_backend:{token}"


def normalize_transport_formula(formula: str) -> NormalizedTransportFormula:
    """Normalize transport formula helper."""
    normalized = _normalize_formula_str(formula)
    return NormalizedTransportFormula(
        formula_str=normalized,
        stratification_variables=_extract_stratification_variables(normalized),
        target_quantities=_extract_quantities(normalized, prefix="P*"),
        source_quantities=_extract_quantities(normalized, prefix="P("),
    )


def _backend_order(mode: str) -> tuple[str, ...]:
    if mode == "y0":
        return ("y0",)
    if mode == "r":
        return ("r",)
    # auto/full_auto probe both backends with deterministic order.
    return ("y0", "r")


def _normalize_formula_str(formula: str) -> str:
    text = str(formula).strip()
    text = text.replace("∑", "Σ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*=\s*", " = ", text)
    text = re.sub(r"\s*,\s*", ",", text)
    return text.strip()


def _extract_stratification_variables(formula: str) -> tuple[str, ...]:
    hits = re.findall(r"Σ_\{([^}]+)\}", formula)
    values: list[str] = []
    for hit in hits:
        for token in hit.split(","):
            name = token.strip()
            if name and name not in values:
                values.append(name)
    return tuple(values)


def _extract_quantities(formula: str, *, prefix: str) -> tuple[str, ...]:
    if prefix == "P*":
        pattern = r"P\*\(([^)]+)\)"
    else:
        pattern = r"P\(([^)]+)\)"
    hits = re.findall(pattern, formula)
    values: list[str] = []
    for hit in hits:
        expr = f"{prefix}({hit})"
        if expr not in values:
            values.append(expr)
    return tuple(values)


def _probe_y0() -> tuple[bool, str | None]:
    if importlib.util.find_spec("y0") is None:
        return False, "y0_unavailable"
    try:
        importlib.import_module("y0")
    except Exception as exc:
        return False, f"y0_import_failed:{type(exc).__name__}:{exc}"
    return True, None


def _probe_r() -> tuple[bool, str | None]:
    if importlib.util.find_spec("rpy2") is None:
        return False, "rpy2_unavailable"
    try:
        from rpy2 import robjects  # type: ignore[import-untyped]

        _ = robjects.r("1+1")
        _ = robjects.r("if ('causaleffect' %in% rownames(installed.packages())) 1 else 0")
        installed_flag = int(_[0]) if len(_) else 0
        if installed_flag != 1:
            return False, "causaleffect_unavailable"
    except Exception as exc:
        return False, f"r_backend_probe_failed:{type(exc).__name__}:{exc}"
    return True, None


__all__ = [
    "NormalizedTransportFormula",
    "SymbolicBackendResolution",
    "normalize_symbolic_backend_mode",
    "normalize_transport_formula",
    "probe_backend_availability",
    "resolve_symbolic_backend",
]
