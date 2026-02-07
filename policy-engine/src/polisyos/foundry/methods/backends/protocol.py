from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import ComputeBackend, MethodSignature


class SolverStatus(str, Enum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    UNBOUNDED = "unbounded"
    TIMEOUT = "timeout"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MethodTiming:
    wall_time_ms: float
    cpu_time_ms: float | None = None
    compile_time_ms: float | None = None


@dataclass(frozen=True, slots=True)
class ReproducibilityInfo:
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
    output: Any
    timing: MethodTiming
    reproducibility: ReproducibilityInfo
    artifacts: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


class MethodRunner(Protocol):
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
        ...

