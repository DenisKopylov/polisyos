"""
Foundry Methods Core Types & Protocol.

This module defines the Application Binary Interface (ABI) for all economic
simulation methods in PolicyOS. Changes to this file require an ADR.

Architecture laws enforced:
    F: Units, SlotSpecs, metadata -> Python only. pure_step receives only arrays.
    H: Deterministic compile cache key via stable digests (not __hash__).
    I: Static vs Dynamic parameters explicitly declared.
"""
from __future__ import annotations

import dataclasses
import functools
import inspect
import json
import os
import re
from dataclasses import dataclass, field, replace
from enum import Enum, auto
from types import MappingProxyType
from typing import Any, Callable, ClassVar, Mapping, Protocol, TypeVar, runtime_checkable

import numpy as np

from polisyos.core.canon import content_hash
from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.exceptions import LawViolationError, MethodDefinitionError

_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def is_valid_semver(version: str) -> bool:
    """Return True if version is valid SemVer 2.0.0."""
    return bool(_SEMVER_RE.match(version))


def parse_fqn(fqn: str) -> tuple[str, str, str]:
    """
    Parse a fully qualified name of the form "namespace.name@version".

    Returns (namespace, name, version). Raises ValueError on invalid input.
    """
    if "@" not in fqn:
        raise ValueError(f"Invalid FQN (missing '@'): {fqn!r}")
    left, version = fqn.rsplit("@", 1)
    if "." not in left:
        raise ValueError(f"Invalid FQN (missing namespace): {fqn!r}")
    namespace, name = left.rsplit(".", 1)
    if not namespace or not name:
        raise ValueError(f"Invalid FQN (empty namespace/name): {fqn!r}")
    if not is_valid_semver(version):
        raise ValueError(f"Invalid FQN (bad semver): {fqn!r}")
    return namespace, name, version


def _strict_mode_enabled() -> bool:
    value = os.getenv("POLISYOS_STRICT", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _normalize_metadata_tags(
    namespace: str,
    signature: "MethodSignature",
    tags: set[str] | frozenset[str],
) -> frozenset[str]:
    normalized = {str(tag).strip() for tag in tags if str(tag).strip()}
    normalized |= _infer_affinity_tags(namespace, signature)
    normalized |= _infer_task_tags(namespace, signature)
    return frozenset(sorted(normalized))


def _infer_affinity_tags(namespace: str, signature: "MethodSignature") -> set[str]:
    ns = namespace.lower()
    slot_names = {slot.name for slot in signature.input_slots} | {
        slot.name for slot in signature.output_slots
    }
    inferred: set[str] = set()

    if "panel" in ns or {"panel_data", "outcome_panel", "entity_ids", "time_ids"} & slot_names:
        inferred.add("panel")
    if (
        {"outcome", "treatment", "time_treatment"} <= slot_names
        or {"outcome", "treatment", "treatment_timing"} <= slot_names
        or {"panel_observational_data"} & slot_names
    ):
        inferred.add("panel")
    if any(token in ns for token in ("cross_section", "cross-section")):
        inferred.add("cross-section")
    if {
        "outcome",
        "treatment",
        "running_variable",
        "covariates",
        "confounders",
        "hte_data",
        "graph_causal_data",
    } & slot_names:
        inferred.add("cross-section")
    if any(token in ns for token in ("timeseries", "time_series", "time-series")) or {
        "time_series_data",
        "endog",
        "time_index",
    } & slot_names:
        inferred.add("time-series")
    if "spatial" in ns or "geo" in ns:
        inferred.add("spatial")
    if "network" in ns or "graph" in ns:
        inferred.add("network")
    if "survey" in ns:
        inferred.add("survey")
    if "optimization" in ns:
        inferred.add("optimization")
    if "structural" in ns:
        inferred.add("structural")
    if any(token in ns for token in ("causal.discovery", "causal.prior", "causal.transport")) or {
        "selection_diagram",
        "scm_query_data",
        "scm_fit_data",
        "graph_causal_data",
        "graph_reconciliation_data",
        "literature_prior_build_data",
    } & slot_names:
        inferred.add("structural")
    if any(token in ns for token in ("ml", "machine_learning")) or {"covariates", "exog"} & slot_names:
        inferred.add("tabular")
    if {
        "features",
        "target",
        "tabular_data",
        "tabular_discovery_data",
        "hte_data",
        "graph_causal_data",
    } & slot_names:
        inferred.add("tabular")
    return inferred


def _normalize_string_tuple(values: Any) -> tuple[str, ...]:
    if isinstance(values, str):
        values = (values,)
    if values is None:
        return ()
    if not isinstance(values, (list, tuple, set, frozenset)):
        raise TypeError("expected iterable of strings")
    normalized = [str(value).strip() for value in values if str(value).strip()]
    return tuple(dict.fromkeys(normalized))


def _infer_data_modalities(namespace: str, signature: "MethodSignature") -> frozenset[str]:
    modalities: set[str] = set()
    affinity_tags = _infer_affinity_tags(namespace, signature)
    for tag in ("panel", "cross-section", "time-series", "spatial", "network", "survey", "tabular"):
        if tag in affinity_tags:
            modalities.add(tag)
    if "optimization" in namespace.lower():
        modalities.add("optimization")
    return frozenset(sorted(modalities))


def _infer_task_tags(namespace: str, signature: "MethodSignature") -> set[str]:
    ns = namespace.lower()
    output_slot_names = {slot.name for slot in signature.output_slots}
    inferred: set[str] = set()

    if any(token in ns for token in ("discovery", "identify")):
        inferred.add("discovery")
    if "diagnostic" in ns or "diagnostics" in ns:
        inferred.add("diagnostics")
    if "forecast" in ns:
        inferred.add("forecasting")
    if "simulation" in ns or "microsim" in ns:
        inferred.add("simulation")
    if "policy_learning" in ns or "targeting" in ns:
        inferred.add("policy-learning")
    if "selection" in ns:
        inferred.add("feature-selection")
    if "uncertainty" in ns or "uncertainty_envelope" in output_slot_names:
        inferred.add("uncertainty")

    primary_tasks = inferred - {"uncertainty"}
    if not primary_tasks:
        inferred.add("estimation")
    return inferred


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class FidelityLevel(Enum):
    """Simulation fidelity tiers supporting Law L (multi-fidelity)."""

    LOW = auto()      # Heuristic / proxy
    MEDIUM = auto()   # Statistical / aggregate
    HIGH = auto()     # Agent-based / micro-simulation


class ComplexityClass(Enum):
    """Algorithmic complexity classification for cost estimation."""

    O_1 = auto()       # Constant time
    O_LOG_N = auto()   # Logarithmic
    O_N = auto()       # Linear in agents
    O_N2 = auto()      # Quadratic
    O_EXP = auto()     # Exponential


class SlotType(Enum):
    """Data dimensionality classification for slots."""

    SCALAR = auto()    # ()
    VECTOR = auto()    # (n_agents,)
    MATRIX = auto()    # Generic 2D shape
    TENSOR = auto()    # Arbitrary shape


class ComputeBackend(str, Enum):
    """Compute backend used to execute a method."""

    JAX = "jax"
    NUMPY = "numpy"
    SOLVER = "solver"
    BAYESIAN = "bayesian"


class MethodKind(str, Enum):
    """Execution contour of a Foundry method."""

    PURE = "pure"
    MECHANISM = "mechanism"
    SIMULATION = "simulation"


class SideEffectProfile(str, Enum):
    """Runtime side effects visible outside the pure method output."""

    NONE = "none"
    PATCH_EMISSION = "patch_emission"
    ARTIFACT_EMISSION = "artifact_emission"
    TRAINING = "training"


# ---------------------------------------------------------------------------
# Core data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Unit:
    """
    Algebraic unit representation for dimensional analysis.

    Units exist only in Python layer (Law F). They are used for labeling,
    compatibility checking, and documentation. Units are not used for runtime
    conversion (exchange rates are data).
    """

    dimension: str
    symbol: str
    scale: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, str) or not self.dimension:
            raise ValueError("Unit.dimension must be a non-empty string")
        if not isinstance(self.symbol, str):
            raise ValueError("Unit.symbol must be a string")
        if not isinstance(self.scale, (int, float)):
            raise TypeError("Unit.scale must be a number")
        scale = float(self.scale)
        if scale <= 0.0:
            raise ValueError("Unit.scale must be > 0")
        object.__setattr__(self, "scale", scale)

    def is_compatible(self, other: Unit) -> bool:
        """Check if this unit can be connected to another (same dimension)."""
        return self.dimension == other.dimension

    def stable_digest(self) -> str:
        """Stable digest for persistent cache keys (Law H)."""
        return _stable_digest(self._stable_dict())

    def _stable_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "symbol": self.symbol,
            "scale": _stable_float(self.scale),
        }

    def __hash__(self) -> int:
        """Process-local hash (do not use for persistent cache keys)."""
        return hash((self.dimension, self.symbol, self.scale))

    def __repr__(self) -> str:
        if self.scale != 1.0:
            return f"Unit({self.dimension!r}, {self.symbol!r}, scale={self.scale})"
        return f"Unit({self.dimension!r}, {self.symbol!r})"


# ---------------------------------------------------------------------------
# Symbolic dimension algebra (T3.1)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DimVar:
    """
    Named symbolic dimension variable for use in ``SlotSpec.shape``.

    A ``DimVar`` represents a named axis whose concrete size is unknown at
    definition time but must be consistent across linked slots.

    Example::

        n_obs = DimVar("n_obs")
        n_vars = DimVar("n_vars")

        outcome_slot = SlotSpec(
            name="outcome",
            slot_type=SlotType.VECTOR,
            unit=Unit("dimensionless", "-"),
            shape=(n_obs,),
        )
        covariate_slot = SlotSpec(
            name="covariates",
            slot_type=SlotType.MATRIX,
            unit=Unit("dimensionless", "-"),
            shape=(n_obs, n_vars),
        )

    Compatibility rules enforced by :func:`types.checker.check_slot_compatibility`:
    - ``DimVar("n_obs")`` × ``DimVar("n_obs")`` → compatible (same symbolic name)
    - ``DimVar("n_obs")`` × ``DimVar("n_rows")`` → warning (may differ at runtime)
    - ``DimVar("n_obs")`` × ``int`` → compatible (concrete satisfies symbolic)
    - ``int`` × ``DimVar("n_obs")`` → compatible with warning (fixed vs symbolic)
    """

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("DimVar.name must be a non-empty string")

    def __repr__(self) -> str:
        return f"DimVar({self.name!r})"

    def __str__(self) -> str:
        return self.name


# Type aliases for symbolic shape specifications
DimExpr = int | str | DimVar | None
"""A single dimension: concrete int, legacy str, typed DimVar, or None (wildcard)."""

Shape = tuple[DimExpr, ...]
"""A shape tuple using symbolic or concrete dimension expressions."""


@dataclass(frozen=True, slots=True)
class SlotSpec:
    """
    Specification for a method's input or output data slot.

    SlotSpecs define the ports through which methods exchange data. They are
    used by the Slot Linker (Phase 3.3) to verify compatibility.
    """

    name: str
    slot_type: SlotType
    unit: Unit
    contract_id: str | None = None
    shape: tuple[int | str, ...] = ()
    description: str = ""
    bounds: tuple[float | int | None, float | int | None] = (None, None)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("SlotSpec.name must be a non-empty string")
        if not isinstance(self.slot_type, SlotType):
            raise TypeError("SlotSpec.slot_type must be a SlotType")
        if not isinstance(self.unit, Unit):
            raise TypeError("SlotSpec.unit must be a Unit")
        if self.contract_id is not None and (
            not isinstance(self.contract_id, str) or not self.contract_id.strip()
        ):
            raise TypeError("SlotSpec.contract_id must be None or a non-empty string")
        if not isinstance(self.shape, tuple):
            raise TypeError("SlotSpec.shape must be a tuple")
        for dim in self.shape:
            if dim is not None and not isinstance(dim, (int, str, DimVar)):
                raise TypeError(
                    "SlotSpec.shape entries must be int, str, DimVar, or None"
                )
        if self.slot_type is SlotType.SCALAR and self.shape != ():
            raise ValueError("SlotType.SCALAR requires shape=()")
        _validate_bounds("SlotSpec.bounds", self.bounds)

    def stable_digest(self) -> str:
        """Stable digest for persistent cache keys (Law H)."""
        return _stable_digest(self._stable_dict())

    def _stable_dict(self) -> dict[str, Any]:
        def _serialise_dim(d: DimExpr) -> str | int | None:
            if d is None:
                return None
            if isinstance(d, DimVar):
                return f"$DimVar:{d.name}"
            return d  # int or str

        return {
            "name": self.name,
            "slot_type": self.slot_type.name,
            "unit": self.unit._stable_dict(),
            "contract_id": self.contract_id,
            "shape": [_serialise_dim(d) for d in self.shape],
        }

    def __hash__(self) -> int:
        """
        Hash for inclusion in frozenset (identity fields only).

        Note: description and bounds are excluded as they do not affect
        slot identity for linking purposes.
        """
        return hash((self.name, self.slot_type, self.unit, self.contract_id, self.shape))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SlotSpec):
            return NotImplemented
        return (
            self.name == other.name
            and self.slot_type == other.slot_type
            and self.unit == other.unit
            and self.contract_id == other.contract_id
            and self.shape == other.shape
        )


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    """
    Specification for a tunable method parameter.

    Static vs Dynamic (Law I):
        - Static params affect array shapes or control flow -> compile cache key
        - Dynamic params are traced through JAX -> can change without recompile
    """

    name: str
    default: Any
    is_static: bool = False
    bounds: tuple[float | int | None, float | int | None] = (None, None)
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("ParameterSpec.name must be a non-empty string")
        if not isinstance(self.is_static, bool):
            raise TypeError("ParameterSpec.is_static must be a bool")
        _validate_bounds("ParameterSpec.bounds", self.bounds)
        _ensure_stable_value("ParameterSpec.default", self.default)

    def stable_digest(self) -> str:
        """Stable digest for persistent cache keys (Law H)."""
        return _stable_digest(self._stable_dict())

    def _stable_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "default": _stable_value(self.default),
            "is_static": self.is_static,
            "bounds": _stable_value(self.bounds),
        }

    def __hash__(self) -> int:
        """Process-local hash for in-memory caches."""
        if hasattr(self.default, "tobytes"):
            default_hash = hash(self.default.tobytes())
        else:
            default_hash = hash(self.default)
        return hash((self.name, default_hash, self.is_static))


@dataclass(frozen=True, slots=True)
class MethodSignature:
    """
    The immutable ABI contract of a Foundry method.

    FQN format: "{namespace}.{name}@{version}"

    Notes:
        - commutes_with/conflicts_with/requires must be FQNs.
        - namespace and version may be empty placeholders before decoration.
    """

    name: str
    namespace: str
    version: str

    input_slots: frozenset[SlotSpec]
    output_slots: frozenset[SlotSpec]
    parameters: tuple[ParameterSpec, ...]

    fidelity: FidelityLevel
    complexity: ComplexityClass
    backend: ComputeBackend = ComputeBackend.JAX
    kind: MethodKind = MethodKind.PURE
    family: str = ""
    variant: str = ""
    data_modalities: frozenset[str] = frozenset()
    fidelity_tier: FidelityLevel | None = None

    commutes_with: frozenset[str] = frozenset()
    conflicts_with: frozenset[str] = frozenset()
    requires: frozenset[str] = frozenset()

    supports_jit: bool = True
    supports_vmap: bool = True
    supports_grad: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("MethodSignature.name must be a non-empty string")
        if not isinstance(self.namespace, str):
            raise TypeError("MethodSignature.namespace must be a string")
        if not isinstance(self.version, str):
            raise TypeError("MethodSignature.version must be a string")
        if self.version and not is_valid_semver(self.version):
            raise ValueError(f"Invalid semver version: {self.version!r}")
        if not isinstance(self.input_slots, frozenset):
            raise TypeError("input_slots must be a frozenset")
        if not isinstance(self.output_slots, frozenset):
            raise TypeError("output_slots must be a frozenset")
        if not isinstance(self.parameters, tuple):
            raise TypeError("parameters must be a tuple")
        if not isinstance(self.backend, ComputeBackend):
            raise TypeError("backend must be a ComputeBackend")
        if not isinstance(self.kind, MethodKind):
            raise TypeError("kind must be a MethodKind")
        if not isinstance(self.commutes_with, frozenset):
            raise TypeError("commutes_with must be a frozenset")
        if not isinstance(self.conflicts_with, frozenset):
            raise TypeError("conflicts_with must be a frozenset")
        if not isinstance(self.requires, frozenset):
            raise TypeError("requires must be a frozenset")
        if not isinstance(self.data_modalities, frozenset):
            object.__setattr__(self, "data_modalities", frozenset(self.data_modalities))
        if self.fidelity_tier is None:
            object.__setattr__(self, "fidelity_tier", self.fidelity)
        if not self.family:
            object.__setattr__(self, "family", self.namespace or self.name)
        if not self.variant:
            object.__setattr__(self, "variant", self.name)
        for slot in self.input_slots:
            if not isinstance(slot, SlotSpec):
                raise TypeError("input_slots must contain SlotSpec")
        for slot in self.output_slots:
            if not isinstance(slot, SlotSpec):
                raise TypeError("output_slots must contain SlotSpec")
        for param in self.parameters:
            if not isinstance(param, ParameterSpec):
                raise TypeError("parameters must contain ParameterSpec")
        _ensure_unique_names("input_slots", [slot.name for slot in self.input_slots])
        _ensure_unique_names("output_slots", [slot.name for slot in self.output_slots])
        _ensure_unique_names("parameters", [param.name for param in self.parameters])
        _validate_method_refs("commutes_with", self.commutes_with)
        _validate_method_refs("conflicts_with", self.conflicts_with)
        _validate_method_refs("requires", self.requires)
        if self.backend is not ComputeBackend.JAX:
            if self.supports_jit or self.supports_vmap or self.supports_grad:
                raise ValueError(
                    "Non-JAX backend methods must set supports_jit=False, "
                    "supports_vmap=False, supports_grad=False"
                )

    @property
    def fqn(self) -> str:
        """Fully Qualified Name for registry lookup."""
        return f"{self.namespace}.{self.name}@{self.version}"

    @property
    def execution_backend(self) -> ComputeBackend:
        """Explicit execution backend for capability reporting."""
        return self.backend

    @property
    def static_param_names(self) -> frozenset[str]:
        """Names of parameters that affect compilation (Law H)."""
        return frozenset(p.name for p in self.parameters if p.is_static)

    @property
    def dynamic_param_names(self) -> frozenset[str]:
        """Names of parameters that do not require recompilation."""
        return frozenset(p.name for p in self.parameters if not p.is_static)

    @property
    def input_slot_names(self) -> frozenset[str]:
        """Convenience accessor for input slot names."""
        return frozenset(s.name for s in self.input_slots)

    @property
    def output_slot_names(self) -> frozenset[str]:
        """Convenience accessor for output slot names."""
        return frozenset(s.name for s in self.output_slots)

    def get_input_slot(self, name: str) -> SlotSpec | None:
        """Get input slot by name."""
        for slot in self.input_slots:
            if slot.name == name:
                return slot
        return None

    def get_output_slot(self, name: str) -> SlotSpec | None:
        """Get output slot by name."""
        for slot in self.output_slots:
            if slot.name == name:
                return slot
        return None

    def abi_digest(self) -> str:
        """Stable ABI digest for persistent cache keys (Law H)."""
        return _stable_digest(self._stable_dict())

    def stable_digest(self) -> str:
        """Alias for abi_digest()."""
        return self.abi_digest()

    def _stable_dict(self) -> dict[str, Any]:
        payload = {
            "name": self.name,
            "namespace": self.namespace,
            "version": self.version,
            "input_slots": _stable_set([slot._stable_dict() for slot in self.input_slots]),
            "output_slots": _stable_set([slot._stable_dict() for slot in self.output_slots]),
            "parameters": _stable_list([param._stable_dict() for param in self.parameters]),
            "fidelity": self.fidelity.name,
            "fidelity_tier": self.fidelity_tier.name if self.fidelity_tier else None,
            "complexity": self.complexity.name,
            "kind": self.kind.value,
            "family": self.family,
            "variant": self.variant,
            "data_modalities": sorted(self.data_modalities),
            "commutes_with": sorted(self.commutes_with),
            "conflicts_with": sorted(self.conflicts_with),
            "requires": sorted(self.requires),
            "supports_jit": self.supports_jit,
            "supports_vmap": self.supports_vmap,
            "supports_grad": self.supports_grad,
        }
        # Keep digest stable for legacy methods.
        if self.backend is not ComputeBackend.JAX:
            payload["backend"] = self.backend.value
        return payload

    def __hash__(self) -> int:
        """Process-local hash based on identity fields only."""
        return hash((self.name, self.namespace, self.version, self.backend))


@dataclass(frozen=True)
class MethodContracts:
    """
    Declarative Design-by-Contract specification for a Foundry method.

    Contracts are strings that are ``eval``'d in strict mode
    (``POLISYOS_STRICT=1``) before and after ``pure_step``.

    Eval namespace for preconditions / invariants::

        {"state": state, "params": params, "np": np}

    Eval namespace for postconditions::

        {"state": state, "params": params, "result": result, "np": np}

    Any expression that evaluates to ``False`` raises
    :class:`~polisyos.foundry.methods.exceptions.ContractViolationError`.

    Example
    -------
    ::

        @foundry_method(...)
        class MyMethod:
            metadata = MethodMetadata(
                description="...",
                contracts=MethodContracts(
                    preconditions=["len(state['outcome']) >= 2"],
                    postconditions=["not np.any(np.isnan(result['ate']))"],
                    invariants=["params['alpha'] > 0"],
                ),
            )
    """

    preconditions: tuple[str, ...] = ()
    """Expressions checked *before* ``pure_step`` (state + params namespace)."""

    postconditions: tuple[str, ...] = ()
    """Expressions checked *after* ``pure_step`` (state + params + result namespace)."""

    invariants: tuple[str, ...] = ()
    """Expressions checked both before and after ``pure_step``."""

    def __post_init__(self) -> None:
        object.__setattr__(self, "preconditions", tuple(self.preconditions))
        object.__setattr__(self, "postconditions", tuple(self.postconditions))
        object.__setattr__(self, "invariants", tuple(self.invariants))


@dataclass(frozen=True, slots=True)
class MethodMetadata:
    """
    Non-functional metadata for documentation and discovery.

    This data is not used in compilation or execution. It is captured in
    provenance artifacts and catalog generation.
    """

    description: str
    tags: frozenset[str] = frozenset()
    citations: tuple[str, ...] = ()
    equations: Mapping[str, str] = field(default_factory=dict)
    assumptions: Mapping[str, str] = field(default_factory=dict)
    determinism_tier: DeterminismTier | None = None
    required_deps: tuple[str, ...] = ()
    optional_deps: tuple[str, ...] = ()
    fallback_policy: str = "none"
    side_effect_profile: SideEffectProfile = SideEffectProfile.NONE
    contracts: MethodContracts | None = None
    when_to_use: str = ""
    """LLM-readable guidance: when this method is the right choice."""
    when_not_to_use: str = ""
    """LLM-readable guidance: common pitfalls and exclusion criteria."""
    prerequisites: tuple[str, ...] = ()
    """FQNs of methods recommended to run *before* this one (validation, diagnostics)."""
    diagnostic_checks: tuple[str, ...] = ()
    """FQNs of methods recommended to run *after* this one (sensitivity, robustness)."""
    typical_min_obs: int | None = None
    """Minimum number of observations for reliable results (for scoring/filtering)."""
    output_interpretation: str = ""
    """LLM-readable guide to interpreting the primary output metric."""

    def __post_init__(self) -> None:
        if not isinstance(self.description, str):
            raise TypeError("MethodMetadata.description must be a string")
        if not isinstance(self.tags, frozenset):
            object.__setattr__(self, "tags", frozenset(self.tags))
        if not isinstance(self.citations, tuple):
            object.__setattr__(self, "citations", tuple(self.citations))
        object.__setattr__(self, "required_deps", _normalize_string_tuple(self.required_deps))
        object.__setattr__(self, "optional_deps", _normalize_string_tuple(self.optional_deps))
        object.__setattr__(self, "prerequisites", _normalize_string_tuple(self.prerequisites))
        object.__setattr__(self, "diagnostic_checks", _normalize_string_tuple(self.diagnostic_checks))
        if self.determinism_tier is not None and not isinstance(self.determinism_tier, DeterminismTier):
            raise TypeError("MethodMetadata.determinism_tier must be a DeterminismTier")
        if not isinstance(self.side_effect_profile, SideEffectProfile):
            object.__setattr__(
                self,
                "side_effect_profile",
                SideEffectProfile(str(self.side_effect_profile)),
            )
        if not isinstance(self.equations, MappingProxyType):
            equations_copy = dict(self.equations)
            object.__setattr__(self, "equations", MappingProxyType(equations_copy))
        if not isinstance(self.assumptions, MappingProxyType):
            assumptions_copy = dict(self.assumptions)
            object.__setattr__(self, "assumptions", MappingProxyType(assumptions_copy))

    def stable_digest(self) -> str:
        """Stable digest for provenance artifacts."""
        return _stable_digest(self._stable_dict())

    def _stable_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "tags": sorted(self.tags),
            "citations": list(self.citations),
            "equations": _stable_mapping(self.equations),
            "assumptions": _stable_mapping(self.assumptions),
            "determinism_tier": (
                self.determinism_tier.value if self.determinism_tier is not None else None
            ),
            "required_deps": list(self.required_deps),
            "optional_deps": list(self.optional_deps),
            "fallback_policy": self.fallback_policy,
            "side_effect_profile": self.side_effect_profile.value,
            "when_to_use": self.when_to_use,
            "when_not_to_use": self.when_not_to_use,
            "prerequisites": list(self.prerequisites),
            "diagnostic_checks": list(self.diagnostic_checks),
            "typical_min_obs": self.typical_min_obs,
            "output_interpretation": self.output_interpretation,
        }

    def __hash__(self) -> int:
        return hash(
            (
                self.description,
                self.tags,
                self.citations,
                tuple(self.assumptions.items()),
                self.determinism_tier,
                self.required_deps,
                self.optional_deps,
                self.fallback_policy,
                self.side_effect_profile,
                self.when_to_use,
                self.when_not_to_use,
                self.prerequisites,
                self.diagnostic_checks,
                self.typical_min_obs,
                self.output_interpretation,
            )
        )


# ---------------------------------------------------------------------------
# The protocol
# ---------------------------------------------------------------------------

StateT = TypeVar("StateT")
ParamsT = TypeVar("ParamsT", bound=Mapping[str, Any])


@runtime_checkable
class FoundryMethod(Protocol[StateT, ParamsT]):
    """
    Protocol for all economic simulation methods in PolicyOS.

    Law F enforcement:
        - pure_step is a @staticmethod (no self)
        - pure_step receives only arrays and primitives
        - Units, SlotSpecs, metadata exist in class attributes only
    """

    signature: ClassVar[MethodSignature]
    metadata: ClassVar[MethodMetadata]

    @staticmethod
    def pure_step(state: StateT, params: ParamsT) -> StateT:
        """Execute one simulation step (pure function)."""
        ...

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> Any:
        """Optional hook to materialize bound slot values into runtime state."""
        ...

    @staticmethod
    def dematerialize_output(output: Any) -> Mapping[str, Any]:
        """Optional hook to map runtime output back to declared slots."""
        ...


# ---------------------------------------------------------------------------
# Registration decorator
# ---------------------------------------------------------------------------

def foundry_method(
    *,
    namespace: str,
    version: str = "1.0.0",
    tags: set[str] | None = None,
) -> Callable[[type], type]:
    """
    Registration decorator for Foundry methods.

    This decorator:
        1. Validates protocol compliance (signature, pure_step staticmethod)
        2. Updates signature with namespace/version using dataclasses.replace()
        3. Provides default metadata if missing
        4. Optionally wraps pure_step with strict Law F checks
    """

    def decorator(cls: type) -> type:
        if not hasattr(cls, "signature"):
            raise MethodDefinitionError(
                f"{cls.__name__} missing 'signature'. "
                "FoundryMethod requires a MethodSignature class attribute."
            )
        if not isinstance(cls.signature, MethodSignature):
            raise MethodDefinitionError(
                f"{cls.__name__}.signature must be a MethodSignature, "
                f"got {type(cls.signature).__name__}"
            )
        if not hasattr(cls, "pure_step"):
            raise MethodDefinitionError(
                f"{cls.__name__} missing 'pure_step'. "
                "FoundryMethod requires a pure_step @staticmethod."
            )
        pure_step_attr = inspect.getattr_static(cls, "pure_step")
        if not isinstance(pure_step_attr, staticmethod):
            raise MethodDefinitionError(
                f"{cls.__name__}.pure_step must be a @staticmethod. "
                "Law F: pure_step cannot use 'self'."
            )
        if hasattr(cls, "metadata") and not isinstance(cls.metadata, MethodMetadata):
            raise MethodDefinitionError(
                f"{cls.__name__}.metadata must be a MethodMetadata, "
                f"got {type(cls.metadata).__name__}"
            )

        if not isinstance(namespace, str) or not namespace:
            raise MethodDefinitionError("namespace must be a non-empty string")
        if not isinstance(version, str) or not is_valid_semver(version):
            raise MethodDefinitionError("version must be valid semver")

        original_sig = cls.signature
        inferred_sig = replace(
            original_sig,
            namespace=namespace,
            version=version,
        )
        inferred_family = str(getattr(cls, "method_family", "")).strip() or inferred_sig.namespace
        inferred_variant = str(getattr(cls, "method_variant", "")).strip() or inferred_sig.name
        inferred_kind = getattr(cls, "method_kind", inferred_sig.kind)
        if not isinstance(inferred_kind, MethodKind):
            inferred_kind = MethodKind(str(inferred_kind))
        inferred_modalities = inferred_sig.data_modalities or _infer_data_modalities(
            namespace,
            inferred_sig,
        )
        cls.signature = replace(
            inferred_sig,
            kind=inferred_kind,
            family=inferred_family,
            variant=inferred_variant,
            data_modalities=frozenset(inferred_modalities),
            fidelity_tier=inferred_sig.fidelity_tier or inferred_sig.fidelity,
        )

        if not hasattr(cls, "metadata"):
            cls.metadata = MethodMetadata(
                description=f"{cls.__name__} - auto-generated metadata",
                tags=_normalize_metadata_tags(namespace, cls.signature, tags or set()),
            )
        else:
            existing = cls.metadata
            merged_tags = set(tags or set()) | {
                str(tag)
                for tag in existing.tags
                if not str(tag).startswith("deprecated:")
            }
            cls.metadata = MethodMetadata(
                description=existing.description,
                tags=_normalize_metadata_tags(
                    namespace,
                    cls.signature,
                    merged_tags,
                ),
                citations=existing.citations,
                equations=existing.equations,
                assumptions=existing.assumptions,
                determinism_tier=existing.determinism_tier,
                required_deps=existing.required_deps,
                optional_deps=existing.optional_deps,
                fallback_policy=existing.fallback_policy,
                side_effect_profile=existing.side_effect_profile,
                contracts=existing.contracts,
                when_to_use=existing.when_to_use,
                when_not_to_use=existing.when_not_to_use,
                prerequisites=existing.prerequisites,
                diagnostic_checks=existing.diagnostic_checks,
                typical_min_obs=existing.typical_min_obs,
                output_interpretation=existing.output_interpretation,
            )

        current_metadata = cls.metadata
        runtime_stack = _normalize_string_tuple(getattr(cls, "runtime_stack", ()))
        required_deps = current_metadata.required_deps or _normalize_string_tuple(
            getattr(cls, "required_deps", runtime_stack)
        )
        optional_deps = current_metadata.optional_deps or _normalize_string_tuple(
            getattr(cls, "optional_deps", ())
        )
        determinism_tier = current_metadata.determinism_tier or getattr(cls, "determinism_tier", None)
        fallback_policy = current_metadata.fallback_policy
        if fallback_policy == "none":
            fallback_policy = str(getattr(cls, "fallback_policy", "none"))
        side_effect_profile = current_metadata.side_effect_profile
        if side_effect_profile is SideEffectProfile.NONE:
            side_effect_profile = getattr(cls, "side_effect_profile", SideEffectProfile.NONE)
        if not isinstance(side_effect_profile, SideEffectProfile):
            side_effect_profile = SideEffectProfile(str(side_effect_profile))
        cls.metadata = MethodMetadata(
            description=current_metadata.description,
            tags=current_metadata.tags,
            citations=current_metadata.citations,
            equations=current_metadata.equations,
            assumptions=current_metadata.assumptions,
            determinism_tier=determinism_tier,
            required_deps=required_deps,
            optional_deps=optional_deps,
            fallback_policy=fallback_policy,
            side_effect_profile=side_effect_profile,
            contracts=current_metadata.contracts,
            when_to_use=current_metadata.when_to_use,
            when_not_to_use=current_metadata.when_not_to_use,
            prerequisites=current_metadata.prerequisites,
            diagnostic_checks=current_metadata.diagnostic_checks,
            typical_min_obs=current_metadata.typical_min_obs,
            output_interpretation=current_metadata.output_interpretation,
        )

        if _strict_mode_enabled():
            original_fn = cls.pure_step
            _contracts: MethodContracts | None = cls.metadata.contracts
            _fqn: str = cls.signature.fqn

            @functools.wraps(original_fn)
            def strict_pure_step(state: Any, params: Any) -> Any:
                _validate_pure_step_args(state, params)
                if _contracts is not None:
                    _check_contracts_pre(_fqn, _contracts, state, params)
                result = original_fn(state, params)
                if _contracts is not None:
                    _check_contracts_post(_fqn, _contracts, state, params, result)
                return result

            cls.pure_step = staticmethod(strict_pure_step)

        # Beartype runtime shape checking (opt-in via env var)
        if _beartype_enabled():
            _wrap_pure_step_with_beartype(cls)

        return cls

    return decorator


def _beartype_enabled() -> bool:
    """Return True when beartype wrapping is requested AND beartype is available."""
    value = os.getenv("FOUNDRY_SHAPE_CHECK", "").strip().lower()
    if value in {"0", "false", "no", "off"}:
        return False
    # Default on when beartype is installed (dev / test environments)
    try:
        import beartype  # noqa: F401
        return True
    except ImportError:
        return False


def _wrap_pure_step_with_beartype(cls: type) -> None:
    """
    Wrap ``cls.pure_step`` with ``beartype`` for runtime type annotation checks.

    This is a no-op if beartype is not installed or if ``pure_step`` has no
    annotations worth checking.  The wrapper is skipped silently on import
    error so production environments that don't install beartype are unaffected.
    """
    try:
        from beartype import beartype as _beartype
    except ImportError:
        return

    original_fn = cls.pure_step
    try:
        wrapped = _beartype(original_fn)
        cls.pure_step = staticmethod(wrapped)
    except Exception:
        # beartype may refuse to wrap functions with non-annotated args — skip gracefully
        pass


# ---------------------------------------------------------------------------
# Contract enforcement helpers
# ---------------------------------------------------------------------------


def _check_contracts_pre(
    fqn: str,
    contracts: "MethodContracts",
    state: Any,
    params: Any,
) -> None:
    """Evaluate preconditions and invariants before pure_step."""
    _ns = {"state": state, "params": params, "np": np}
    for expr in contracts.preconditions:
        try:
            ok = eval(expr, _ns)  # noqa: S307 — internal, developer-authored only
        except Exception as exc:
            from polisyos.foundry.methods.exceptions import ContractViolationError
            raise ContractViolationError(fqn, "precondition", expr) from exc
        if not ok:
            from polisyos.foundry.methods.exceptions import ContractViolationError
            raise ContractViolationError(fqn, "precondition", expr)
    for expr in contracts.invariants:
        try:
            ok = eval(expr, _ns)  # noqa: S307
        except Exception as exc:
            from polisyos.foundry.methods.exceptions import ContractViolationError
            raise ContractViolationError(fqn, "invariant", expr) from exc
        if not ok:
            from polisyos.foundry.methods.exceptions import ContractViolationError
            raise ContractViolationError(fqn, "invariant", expr)


def _check_contracts_post(
    fqn: str,
    contracts: "MethodContracts",
    state: Any,
    params: Any,
    result: Any,
) -> None:
    """Evaluate postconditions and invariants after pure_step."""
    _ns = {"state": state, "params": params, "result": result, "np": np}
    for expr in contracts.postconditions:
        try:
            ok = eval(expr, _ns)  # noqa: S307
        except Exception as exc:
            from polisyos.foundry.methods.exceptions import ContractViolationError
            raise ContractViolationError(fqn, "postcondition", expr) from exc
        if not ok:
            from polisyos.foundry.methods.exceptions import ContractViolationError
            raise ContractViolationError(fqn, "postcondition", expr)
    _ns_inv = {"state": state, "params": params, "np": np}
    for expr in contracts.invariants:
        try:
            ok = eval(expr, _ns_inv)  # noqa: S307
        except Exception as exc:
            from polisyos.foundry.methods.exceptions import ContractViolationError
            raise ContractViolationError(fqn, "invariant", expr) from exc
        if not ok:
            from polisyos.foundry.methods.exceptions import ContractViolationError
            raise ContractViolationError(fqn, "invariant", expr)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def check_protocol_compliance(cls: type) -> list[str]:
    """Validate that a class correctly implements FoundryMethod protocol."""
    errors = []

    if not hasattr(cls, "signature"):
        errors.append(f"{cls.__name__} missing 'signature' class attribute")
    elif not isinstance(cls.signature, MethodSignature):
        errors.append(f"{cls.__name__}.signature is not a MethodSignature")

    if not hasattr(cls, "pure_step"):
        errors.append(f"{cls.__name__} missing 'pure_step' method")
    else:
        if not isinstance(inspect.getattr_static(cls, "pure_step"), staticmethod):
            errors.append(f"{cls.__name__}.pure_step must be a @staticmethod")

    if hasattr(cls, "metadata") and not isinstance(cls.metadata, MethodMetadata):
        errors.append(f"{cls.__name__}.metadata is not a MethodMetadata")

    return errors


# ---------------------------------------------------------------------------
# Fail-fast base class (optional mixin for __init_subclass__ ABI enforcement)
# ---------------------------------------------------------------------------


class FoundryMethodBase:
    """
    Optional base class for Foundry methods that enforces ABI at *class
    definition time* rather than at registration time.

    Inherit from this class to get an immediate ``MethodDefinitionError`` if
    your class is missing ``pure_step`` (as a ``@staticmethod``) or if
    ``signature`` is not a ``MethodSignature`` instance.

    The decorator ``@foundry_method`` handles namespace / version injection and
    is still required.  This base class only provides the fail-fast structural
    check so that import-time errors are surfaced earlier.

    Example
    -------
    ::

        @foundry_method(namespace="causal.did", version="1.0.0")
        class MyDID(FoundryMethodBase):
            signature = MethodSignature(name="my_did", ...)
            metadata = MethodMetadata(...)

            @staticmethod
            def pure_step(state, params):
                ...

    To skip the check (e.g. for abstract intermediaries) pass
    ``skip_abi_check=True``::

        class _AbstractBase(FoundryMethodBase, skip_abi_check=True):
            ...
    """

    def __init_subclass__(cls, skip_abi_check: bool = False, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        if skip_abi_check or getattr(cls, "_skip_abi_check", False):
            return

        # pure_step must be a @staticmethod
        pure_step_attr = inspect.getattr_static(cls, "pure_step", None)
        if pure_step_attr is None:
            raise MethodDefinitionError(
                f"{cls.__qualname__} inherits from FoundryMethodBase but is missing "
                "'pure_step'. Add a @staticmethod pure_step(state, params) -> state."
            )
        if not isinstance(pure_step_attr, staticmethod):
            raise MethodDefinitionError(
                f"{cls.__qualname__}.pure_step must be a @staticmethod (Law F). "
                "Remove 'self' and add the @staticmethod decorator."
            )

        # signature must be a MethodSignature if already set
        if hasattr(cls, "signature") and not isinstance(cls.signature, MethodSignature):
            raise MethodDefinitionError(
                f"{cls.__qualname__}.signature must be a MethodSignature instance, "
                f"got {type(cls.signature).__name__}."
            )

        # metadata must be a MethodMetadata if already set
        if hasattr(cls, "metadata") and not isinstance(cls.metadata, MethodMetadata):
            raise MethodDefinitionError(
                f"{cls.__qualname__}.metadata must be a MethodMetadata instance, "
                f"got {type(cls.metadata).__name__}."
            )


# ---------------------------------------------------------------------------
# Stable digest helpers (Law H)
# ---------------------------------------------------------------------------

def _stable_float(value: float) -> str:
    return float(value).hex()


def _stable_digest(data: Any) -> str:
    payload = _canonicalize(data)
    encoded = _canonical_json(payload).encode("utf-8")
    return content_hash(encoded, algorithm="blake2b", digest_size=32)


def _canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _stable_list(items: list[Any]) -> list[Any]:
    return items


def _stable_set(items: list[Any]) -> list[Any]:
    return sorted(items, key=_canonical_json)


def _stable_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    items: dict[str, Any] = {}
    for key, value in sorted(mapping.items(), key=lambda kv: str(kv[0])):
        if not isinstance(key, str):
            raise TypeError("mapping keys must be strings")
        items[key] = _canonicalize(value)
    return items


def _canonicalize(value: Any) -> Any:
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        return value
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        return {"__float__": _stable_float(value)}
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    if isinstance(value, Enum):
        return {"__enum__": f"{value.__class__.__name__}.{value.name}"}
    if isinstance(value, Mapping):
        return {"__map__": _stable_mapping(value)}
    if isinstance(value, tuple):
        return {"__tuple__": [_canonicalize(v) for v in value]}
    if isinstance(value, list):
        return {"__list__": [_canonicalize(v) for v in value]}
    if isinstance(value, (set, frozenset)):
        items = [_canonicalize(v) for v in value]
        return {"__set__": _stable_set(items)}
    if _is_array_like(value):
        if not hasattr(value, "tobytes"):
            raise TypeError("array-like values must support tobytes()")
        arr = np.asarray(value)
        if arr.dtype == object:
            raise TypeError("object dtype arrays are not supported")
        arr = np.ascontiguousarray(arr)
        return {
            "__ndarray__": {
                "dtype": str(arr.dtype),
                "shape": list(arr.shape),
                "data": arr.tobytes().hex(),
            }
        }
    if isinstance(value, Unit):
        return {"__unit__": value._stable_dict()}
    if isinstance(value, SlotSpec):
        return {"__slot__": value._stable_dict()}
    if isinstance(value, ParameterSpec):
        return {"__param__": value._stable_dict()}
    if isinstance(value, MethodSignature):
        return {"__signature__": value._stable_dict()}
    if isinstance(value, MethodMetadata):
        return {"__metadata__": value._stable_dict()}
    raise TypeError(f"Unsupported type for stable digest: {type(value).__name__}")


def _ensure_stable_value(label: str, value: Any) -> None:
    try:
        _stable_value(value)
    except TypeError as exc:
        raise TypeError(f"{label} is not stable-serializable: {exc}") from exc


def _stable_value(value: Any) -> Any:
    if isinstance(value, (Unit, SlotSpec, ParameterSpec, MethodSignature, MethodMetadata)):
        raise TypeError("Foundry types are not allowed as parameter defaults")
    return _canonicalize(value)


def _is_array_like(value: Any) -> bool:
    return hasattr(value, "shape") and hasattr(value, "dtype")


def _validate_bounds(label: str, bounds: tuple[float | int | None, float | int | None]) -> None:
    if not isinstance(bounds, tuple) or len(bounds) != 2:
        raise TypeError(f"{label} must be a 2-tuple")
    low, high = bounds
    for bound in (low, high):
        if bound is None:
            continue
        if not isinstance(bound, (int, float)):
            raise TypeError(f"{label} bounds must be int, float, or None")
    if low is not None and high is not None and low > high:
        raise ValueError(f"{label} lower bound must be <= upper bound")


def _ensure_unique_names(label: str, names: list[str]) -> None:
    if len(names) != len(set(names)):
        raise ValueError(f"Duplicate names in {label}")


def _validate_method_refs(label: str, refs: frozenset[str]) -> None:
    for ref in refs:
        if not isinstance(ref, str) or not ref:
            raise TypeError(f"{label} must contain non-empty strings")
        parse_fqn(ref)


def _validate_pure_step_args(state: Any, params: Any) -> None:
    if isinstance(state, (Unit, SlotSpec, MethodSignature, MethodMetadata)):
        raise LawViolationError("F", "state contains Foundry types")
    if isinstance(params, (Unit, SlotSpec, MethodSignature, MethodMetadata)):
        raise LawViolationError("F", "params contains Foundry types")
    _walk_and_validate("state", state)
    _walk_and_validate("params", params)


def _walk_and_validate(label: str, value: Any) -> None:
    if _is_allowed_leaf(value):
        return
    if isinstance(value, Mapping):
        for v in value.values():
            _walk_and_validate(label, v)
        return
    if dataclasses.is_dataclass(value):
        for field in dataclasses.fields(value):
            _walk_and_validate(label, getattr(value, field.name))
        return
    if isinstance(value, tuple) and hasattr(value, "_fields"):
        for v in value:
            _walk_and_validate(label, v)
        return
    if isinstance(value, (list, tuple)):
        for v in value:
            _walk_and_validate(label, v)
        return
    if hasattr(value, "__dict__"):
        for v in value.__dict__.values():
            _walk_and_validate(label, v)
        return
    raise LawViolationError("F", f"{label} contains unsupported type: {type(value).__name__}")


def _is_allowed_leaf(value: Any) -> bool:
    if isinstance(value, (Unit, SlotSpec, MethodSignature, MethodMetadata)):
        return False
    if isinstance(value, (bool, int, float, str)) or value is None:
        return True
    if _is_array_like(value):
        return True
    return False
