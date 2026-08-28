"""Expose Foundry method backends without initializing unrelated runtimes.

The backend layer adapts a protocol-compliant method class to a concrete
runtime stack (`jax`, `numpy`, solver, Bayesian sampler), returning a
`MethodResult` with timing and reproducibility metadata. It is separate from
`MethodSignature`, which declares the ABI, and from specialization/cache,
which governs compilation reuse. Facade exports resolve lazily so importing a
single protocol implementation does not initialize chain executors.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.foundry.methods.backends.async_chain_executor import (
        AsyncChainExecutionError,
        AsyncChainExecutor,
        AsyncNodeError,
    )
    from polisyos.foundry.methods.backends.chain_executor import (
        ChainExecutionResult,
        execute_heterogeneous_chain,
    )
    from polisyos.foundry.methods.backends.circuit_breaker import (
        BackendCircuitOpenError,
        CircuitBreaker,
        CircuitBreakerRegistry,
        CircuitState,
        get_circuit_breaker_registry,
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
    "ChainExecutionResult",
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    "CircuitState",
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
    "execute_heterogeneous_chain",
    "get_circuit_breaker_registry",
    "validated_bound_to_envelopes",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "AsyncChainExecutionError": (
        "polisyos.foundry.methods.backends.async_chain_executor",
        "AsyncChainExecutionError",
    ),
    "AsyncChainExecutor": (
        "polisyos.foundry.methods.backends.async_chain_executor",
        "AsyncChainExecutor",
    ),
    "AsyncNodeError": (
        "polisyos.foundry.methods.backends.async_chain_executor",
        "AsyncNodeError",
    ),
    "BackendCircuitOpenError": (
        "polisyos.foundry.methods.backends.circuit_breaker",
        "BackendCircuitOpenError",
    ),
    "BackendNotAvailableError": (
        "polisyos.foundry.methods.backends.dispatch",
        "BackendNotAvailableError",
    ),
    "ChainExecutionResult": (
        "polisyos.foundry.methods.backends.chain_executor",
        "ChainExecutionResult",
    ),
    "CircuitBreaker": (
        "polisyos.foundry.methods.backends.circuit_breaker",
        "CircuitBreaker",
    ),
    "CircuitBreakerRegistry": (
        "polisyos.foundry.methods.backends.circuit_breaker",
        "CircuitBreakerRegistry",
    ),
    "CircuitState": (
        "polisyos.foundry.methods.backends.circuit_breaker",
        "CircuitState",
    ),
    "MethodDispatcher": (
        "polisyos.foundry.methods.backends.dispatch",
        "MethodDispatcher",
    ),
    "MethodResult": (
        "polisyos.foundry.methods.backends.protocol",
        "MethodResult",
    ),
    "MethodRunner": (
        "polisyos.foundry.methods.backends.protocol",
        "MethodRunner",
    ),
    "MethodTiming": (
        "polisyos.foundry.methods.backends.protocol",
        "MethodTiming",
    ),
    "ReproducibilityInfo": (
        "polisyos.foundry.methods.backends.protocol",
        "ReproducibilityInfo",
    ),
    "SolverStatus": (
        "polisyos.foundry.methods.backends.protocol",
        "SolverStatus",
    ),
    "ValidatedBound": (
        "polisyos.foundry.methods.backends.validated",
        "ValidatedBound",
    ),
    "ValidatedExecutionPolicy": (
        "polisyos.foundry.methods.backends.validated",
        "ValidatedExecutionPolicy",
    ),
    "ValidatedMethodFamily": (
        "polisyos.foundry.methods.backends.validated",
        "ValidatedMethodFamily",
    ),
    "ValidatedMode": (
        "polisyos.foundry.methods.backends.validated",
        "ValidatedMode",
    ),
    "ValidatedStatus": (
        "polisyos.foundry.methods.backends.validated",
        "ValidatedStatus",
    ),
    "execute_heterogeneous_chain": (
        "polisyos.foundry.methods.backends.chain_executor",
        "execute_heterogeneous_chain",
    ),
    "get_circuit_breaker_registry": (
        "polisyos.foundry.methods.backends.circuit_breaker",
        "get_circuit_breaker_registry",
    ),
    "validated_bound_to_envelopes": (
        "polisyos.foundry.methods.backends.validated",
        "validated_bound_to_envelopes",
    ),
}


def __getattr__(name: str) -> object:
    """Resolve one backend facade export or real backend submodule on demand."""
    target = _LAZY_IMPORTS.get(name)
    if target is not None:
        module_name, attr_name = target
        value = getattr(importlib.import_module(module_name), attr_name)
        globals()[name] = value
        return value

    module_name = f"{__name__}.{name}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise AttributeError(f"module '{__name__}' has no attribute '{name}'") from None
        raise
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    """Return loaded globals plus all deferred backend exports."""
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
