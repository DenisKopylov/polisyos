"""Expose backend runners and dispatch helpers for Foundry method execution.

The backend layer adapts a protocol-compliant method class to a concrete
runtime stack (`jax`, `numpy`, solver, Bayesian sampler), returning a
`MethodResult` with timing and reproducibility metadata. It is separate from
`MethodSignature`, which declares the ABI, and from specialization/cache,
which governs compilation reuse.
"""
from __future__ import annotations

from polisyos.foundry.methods.backends.async_chain_executor import (
    AsyncChainExecutionError,
    AsyncChainExecutor,
    AsyncNodeError,
)
from polisyos.foundry.methods.backends.circuit_breaker import (
    BackendCircuitOpenError,
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker_registry,
)
from polisyos.foundry.methods.backends.chain_executor import (
    ChainExecutionResult,
    execute_heterogeneous_chain,
)
from polisyos.foundry.methods.backends.dispatch import (
    BackendNotAvailableError,
    MethodDispatcher,
)
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodRunner,
    MethodTiming,
    ReproducibilityInfo,
    SolverStatus,
)
from polisyos.foundry.methods.backends.validated import (
    ValidatedBound,
    ValidatedExecutionPolicy,
    ValidatedMethodFamily,
    ValidatedMode,
    ValidatedStatus,
    validated_bound_to_envelopes,
)

__all__ = [
    "AsyncChainExecutionError",
    "AsyncChainExecutor",
    "AsyncNodeError",
    "BackendCircuitOpenError",
    "BackendNotAvailableError",
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    "CircuitState",
    "get_circuit_breaker_registry",
    "ChainExecutionResult",
    "MethodDispatcher",
    "MethodResult",
    "MethodRunner",
    "MethodTiming",
    "ReproducibilityInfo",
    "SolverStatus",
    "ValidatedBound",
    "ValidatedExecutionPolicy",
    "ValidatedMethodFamily",
    "ValidatedMode",
    "ValidatedStatus",
    "validated_bound_to_envelopes",
    "execute_heterogeneous_chain",
]
