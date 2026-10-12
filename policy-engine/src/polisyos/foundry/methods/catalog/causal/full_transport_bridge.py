"""Normalize symbolic transport formulas and resolve the executable symbolic backend."""

from __future__ import annotations

import importlib
import importlib.metadata
import inspect
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_graph import CausalGraphModel

_VALID_SYMBOLIC_BACKEND_MODES: frozenset[str] = frozenset({"auto", "y0", "r", "full_auto"})


class _Y0ProfileInputSentinel(str, Enum):
    """Compiler-safe distinction between an omitted profile and explicit null."""

    ABSENT = "__polisyos_y0_surrogate_data_profile_absent__"


Y0_SURROGATE_DATA_PROFILE_ABSENT = _Y0ProfileInputSentinel.ABSENT


class _Y0PopulationDataProfile(BaseModel):
    """Caller-declared variable availability for one Y0 source population."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    population_id: str = Field(min_length=1)
    outcomes: tuple[str, ...] = Field(min_length=1)
    interventions: tuple[str, ...] = ()

    @field_validator("population_id")
    @classmethod
    def _validate_population_id(cls, value: str) -> str:
        value = value.strip()
        if not value or value == "pi*":
            raise ValueError("population_id must be non-empty and cannot name the target population")
        return value

    @field_validator("outcomes", "interventions", mode="before")
    @classmethod
    def _freeze_variable_names(cls, values: object) -> object:
        if isinstance(values, list):
            return tuple(values)
        return values

    @field_validator("outcomes", "interventions")
    @classmethod
    def _validate_variable_names(cls, values: tuple[str, ...], info: Any) -> tuple[str, ...]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError(f"{info.field_name} contains an empty variable name")
        if len(normalized) != len(set(normalized)):
            raise ValueError(f"{info.field_name} contains duplicate variable names")
        return tuple(normalized)


class _Y0SurrogateDataProfile(BaseModel):
    """Strict method input; its declarations do not establish data or authority."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["policyos.y0.surrogate-data-profile.v1"]
    populations: tuple[_Y0PopulationDataProfile, ...] = Field(min_length=1)

    @field_validator("populations", mode="before")
    @classmethod
    def _freeze_populations(cls, values: object) -> object:
        if isinstance(values, list):
            return tuple(values)
        return values

    @model_validator(mode="after")
    def _unique_population_ids(self) -> _Y0SurrogateDataProfile:
        population_ids = [population.population_id for population in self.populations]
        if len(population_ids) != len(set(population_ids)):
            raise ValueError("population ids must be unique")
        return self


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
    """Probe whether the adapter's required algorithm API is callable."""
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


def parse_y0_surrogate_data_profile(
    raw: object,
) -> tuple[_Y0SurrogateDataProfile | None, Literal["absent", "null", "invalid", "valid"]]:
    """Parse explicit source-data availability without coercion or authority upgrades."""
    if raw is Y0_SURROGATE_DATA_PROFILE_ABSENT:
        return None, "absent"
    if raw is None:
        return None, "null"
    try:
        profile = _Y0SurrogateDataProfile.model_validate(raw)
    except (ValidationError, TypeError, ValueError):
        return None, "invalid"
    return profile, "valid"


def profile_unknown_variables(
    profile: _Y0SurrogateDataProfile,
    graph_nodes: set[str],
) -> tuple[str, ...]:
    """Return profile variables outside the exact admitted graph node set."""
    requested = {
        variable
        for population in profile.populations
        for variable in (*population.outcomes, *population.interventions)
    }
    return tuple(sorted(requested - graph_nodes))


def build_y0_graph(graph: CausalGraphModel) -> Any:
    """Build Y0's mixed graph by reusing the canonical PolicyOS ADMG edge extractors."""
    from y0.dsl import Variable  # type: ignore[import-not-found]
    from y0.graph import NxMixedGraph  # type: ignore[import-not-found]

    from .admg_ops import extract_bidirected_edges, extract_directed_edges

    variables = {name: Variable(name) for name in graph.nodes}
    directed = [
        (variables[src], variables[dst])
        for src, dst in sorted(extract_directed_edges(graph))
    ]
    bidirected = [
        (variables[src], variables[dst])
        for src, dst in sorted(extract_bidirected_edges(graph))
    ]
    return NxMixedGraph.from_edges(
        nodes=[variables[name] for name in graph.nodes],
        directed=directed,
        undirected=bidirected,
    )


def _backend_order(mode: str) -> tuple[str, ...]:
    if mode == "y0":
        return ("y0",)
    if mode == "r":
        return ("r",)
    # auto/full_auto probe deterministic order; callers still own result semantics.
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
        from y0.algorithm.identify import identify_outcomes  # type: ignore[import-not-found]
        from y0.algorithm.transport import (
            identify_target_outcomes,  # type: ignore[import-not-found]
        )
        from y0.dsl import Variable  # type: ignore[import-not-found]
        from y0.graph import NxMixedGraph  # type: ignore[import-not-found]

        required = (
            ("NxMixedGraph.from_edges", getattr(NxMixedGraph, "from_edges", None)),
            ("identify_outcomes", identify_outcomes),
            ("identify_target_outcomes", identify_target_outcomes),
        )
        for name, operation in required:
            if not callable(operation):
                return False, f"y0_required_api_missing:{name}"
        direct_params = inspect.signature(identify_outcomes).parameters
        if not {"graph", "treatments", "outcomes"}.issubset(direct_params):
            return False, "y0_required_api_signature_mismatch:identify_outcomes"
        trso_params = inspect.signature(identify_target_outcomes).parameters
        if not {
            "graph",
            "target_outcomes",
            "target_interventions",
            "surrogate_outcomes",
            "surrogate_interventions",
        }.issubset(trso_params):
            return False, "y0_required_api_signature_mismatch:identify_target_outcomes"
        if not callable(Variable):
            return False, "y0_required_api_missing:Variable"
        return True, None
    except Exception as exc:
        return False, f"y0_api_probe_failed:{type(exc).__name__}:{exc}"


def _probe_r() -> tuple[bool, str | None]:
    # No canonical product-side R result adapter currently binds a causaleffect
    # expression to the typed PolicyOS result. Dependency presence alone cannot
    # advertise an executable symbolic producer.
    return False, "r_causaleffect_execution_adapter_not_implemented"


__all__ = [
    "NormalizedTransportFormula",
    "SymbolicBackendResolution",
    "Y0_SURROGATE_DATA_PROFILE_ABSENT",
    "build_y0_graph",
    "normalize_symbolic_backend_mode",
    "normalize_transport_formula",
    "parse_y0_surrogate_data_profile",
    "probe_backend_availability",
    "profile_unknown_variables",
    "resolve_symbolic_backend",
]
