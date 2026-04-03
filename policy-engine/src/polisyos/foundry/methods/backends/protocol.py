"""Define the runner protocol and result envelope for concrete method backends.

`MethodRunner` is the execution-side counterpart to the declarative
`MethodSignature` ABI. Runners accept a protocol-compliant method class plus
materialized state/params, invoke the implementation on a concrete backend,
and return `MethodResult` with timing, solver status, and reproducibility
metadata.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import ComputeBackend, MethodSignature


class SolverStatus(str, Enum):
    """Normalize solver termination statuses reported by optimization backends."""
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    UNBOUNDED = "unbounded"
    TIMEOUT = "timeout"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MethodTiming:
    """Record wall/CPU/compile timings for one method execution."""

    wall_time_ms: float
    cpu_time_ms: float | None = None
    compile_time_ms: float | None = None


@dataclass(frozen=True, slots=True)
class ReproducibilityInfo:
    """Capture backend, determinism, seed, and solver metadata for replay audits."""

    backend: ComputeBackend
    determinism_tier: DeterminismTier
    seed: int | None = None
    library_versions: Mapping[str, str] = field(default_factory=dict)
    solver_status: SolverStatus | None = None
    solver_gap: float | None = None
    solver_iterations: int | None = None
    fingerprint: str | None = None
    note: str = ""


@dataclass(frozen=True, slots=True)
class MethodResult:
    """Wrap backend output together with declared slot outputs and diagnostics.

    `output` is the backend-native return value from `pure_step`, while
    `slot_outputs` is the optional dematerialized view aligned to
    `MethodSignature.output_slots`. `artifacts` carries backend-specific
    sidecar payloads that can later be persisted as provenance evidence.
    """

    output: Any
    timing: MethodTiming
    reproducibility: ReproducibilityInfo
    slot_outputs: Mapping[str, Any] = field(default_factory=dict)
    artifacts: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


class MethodRunner(Protocol):
    """Execute one method class on a concrete backend runtime.

    Implementations should be deterministic according to the advertised
    `ReproducibilityInfo.determinism_tier` for identical state, params, seed,
    and runtime stack.
    """

    @property
    def supported_backends(self) -> frozenset[ComputeBackend]:
        ...

    def is_available(self) -> bool:
        ...

    def execute(
        self,
        *,
        method_class: type,
        signature: MethodSignature,
        state: Any,
        params: Mapping[str, Any],
        seed: int,
    ) -> MethodResult:
        """Run one method invocation and return a structured result envelope."""
        ...
