"""
Method Compiler - compiles Foundry methods to optimized JAX functions.

Implements Law H (deterministic compilation) and Law I (static vs dynamic
parameters) with a deterministic specialization key and a thread-safe
single-flight compilation cache.
"""

from __future__ import annotations

import functools
import math
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol, TypeVar
from uuid import UUID

import jax
import jax.numpy as jnp
import numpy as np

from polisyos.foundry.methods.artifacts import (
    SourceIdentityUnavailableError,
    implementation_identity_projection,
)
from polisyos.foundry.methods.backends import (
    collect_chain_node_inputs,
    merge_chain_execution_context,
)
from polisyos.foundry.methods.backends.validated import VALIDATED_EXECUTION_PARAM_NAMES
from polisyos.foundry.methods.base import MethodSignature, _stable_digest
from polisyos.foundry.methods.compiler.specialization import (
    BackendSpec,
    ShapeSpec,
    Specialization,
    build_specialization,
)
from polisyos.foundry.methods.components.io import dematerialize_method_output
from polisyos.foundry.methods.exceptions import CompilationError, ParameterValidationError

__all__ = [
    "CompilationCache",
    "CompiledChainExecutor",
    "CompiledMethod",
    "MethodCompiler",
    "get_global_cache",
    "reset_global_cache",
]


# =============================================================================
# Type Definitions
# =============================================================================

StateT = TypeVar("StateT")
CompiledStepFn = Callable[[Any, Mapping[str, Any]], Any]
KernelStepFn = Callable[[Any, tuple[Any, ...], Mapping[str, Any]], Any]


class FoundryMethodProtocol(Protocol):
    """Protocol for type checking FoundryMethod classes."""

    signature: MethodSignature

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> Any: ...


# =============================================================================
# Compiled Method
# =============================================================================


@dataclass(frozen=True, slots=True)
class _CompiledKernel:
    """Immutable compiled core shared by handles with different defaults."""

    step_core: KernelStepFn
    dynamic_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompiledMethod:
    """
    A compiled method ready for execution.
    """

    method_fqn: str
    signature: MethodSignature
    specialization: Specialization
    step_fn: CompiledStepFn
    dynamic_defaults: Mapping[str, Any]
    lowered_hlo: str | None = None
    compile_time_ms: float = 0.0
    _kernel: _CompiledKernel | None = field(default=None, repr=False, compare=False)

    def __call__(self, state: Any, params: Mapping[str, Any]) -> Any:
        return self.step_fn(state, params)


# =============================================================================
# Compilation Cache
# =============================================================================


@dataclass
class CacheEntry:
    """Cache entry with access tracking for LRU."""

    compiled: CompiledMethod
    last_access: float
    access_count: int = 0


@dataclass(frozen=True, slots=True)
class CacheToken:
    """Snapshot of the cache generation used to detect stale publications."""

    generation: int


@dataclass(slots=True)
class _InFlight:
    event: threading.Event
    error: BaseException | None = None
    result: CompiledMethod | None = None
    invalidated: bool = False


class CompilationCache:
    """
    Thread-safe LRU cache for compiled methods.

    The cache exposes generation tokens so callers can detect when a global
    invalidation happened while compilation was still in-flight. This lets hot
    reload publish a new generation without swapping out the process-global
    cache object underneath concurrent compilers.
    """

    def __init__(self, max_size: int = 1000):
        self._cache: OrderedDict[tuple[int, str], CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.RLock()
        self._flight_lock = threading.Lock()
        self._flights: dict[str, _InFlight] = {}
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._generation = 0

    def current_token(self) -> CacheToken:
        with self._lock:
            return CacheToken(self._generation)

    def claim_flight(
        self, key: str, *, spec: Specialization | None = None, token: CacheToken | None = None
    ) -> tuple[_InFlight, bool]:
        """Reconcile publication/generation before claiming a shared build."""
        with self._lock:
            if token is not None and token.generation != self._generation:
                flight = _InFlight(event=threading.Event(), invalidated=True)
                flight.event.set()
                return flight, False
            if spec is not None:
                cache_key = self._cache_key(spec, token)
                entry = self._cache.get(cache_key)
                if entry is not None:
                    self._hits += 1
                    entry.last_access = time.monotonic()
                    entry.access_count += 1
                    self._cache.move_to_end(cache_key)
                    flight = _InFlight(event=threading.Event(), result=entry.compiled)
                    flight.event.set()
                    return flight, False
            with self._flight_lock:
                flight = self._flights.get(key)
                if flight is not None:
                    return flight, False
                flight = _InFlight(event=threading.Event())
                self._flights[key] = flight
                return flight, True

    def complete_flight(
        self,
        key: str,
        flight: _InFlight,
        *,
        error: BaseException | None = None,
        invalidated: bool = False,
    ) -> None:
        """Publish a failed or invalidated flight and then wake its followers."""
        with self._flight_lock:
            if error is not None:
                flight.error = error
            flight.invalidated = invalidated
            self._flights.pop(key, None)
            flight.event.set()

    def publish_flight(
        self,
        key: str,
        flight: _InFlight,
        spec: Specialization,
        compiled: CompiledMethod,
        *,
        token: CacheToken,
    ) -> bool:
        """Publish cache result and follower notification as one generation step."""
        with self._lock:
            if token.generation != self._generation:
                return False
            self._put_unlocked(spec, compiled, generation=token.generation)
            with self._flight_lock:
                flight.result = compiled
                self._flights.pop(key, None)
                flight.event.set()
            return True

    def get(
        self,
        spec: Specialization,
        *,
        token: CacheToken | None = None,
    ) -> CompiledMethod | None:
        with self._lock:
            key = self._cache_key(spec, token)
            if key in self._cache:
                self._hits += 1
                entry = self._cache[key]
                entry.last_access = time.monotonic()
                entry.access_count += 1
                self._cache.move_to_end(key)
                return entry.compiled
            self._misses += 1
            return None

    def put(
        self,
        spec: Specialization,
        compiled: CompiledMethod,
        *,
        token: CacheToken | None = None,
    ) -> bool:
        with self._lock:
            generation = self._resolve_generation(token)
            if generation != self._generation:
                return False
            self._put_unlocked(spec, compiled, generation=generation)
            return True

    def _put_unlocked(
        self,
        spec: Specialization,
        compiled: CompiledMethod,
        *,
        generation: int,
    ) -> None:
        key = (generation, spec.cache_key)
        if key in self._cache:
            self._cache[key] = CacheEntry(
                compiled=compiled,
                last_access=time.monotonic(),
                access_count=1,
            )
            self._cache.move_to_end(key)
            return

        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)
            self._evictions += 1

        self._cache[key] = CacheEntry(
            compiled=compiled,
            last_access=time.monotonic(),
            access_count=1,
        )

    def contains(
        self,
        spec: Specialization,
        *,
        token: CacheToken | None = None,
    ) -> bool:
        with self._lock:
            return self._cache_key(spec, token) in self._cache

    def invalidate(
        self,
        spec: Specialization,
        *,
        token: CacheToken | None = None,
    ) -> bool:
        with self._lock:
            key = self._cache_key(spec, token)
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> int:
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def invalidate_all(self, *, reset_stats: bool = False) -> int:
        """
        Advance the cache generation and drop all entries atomically.

        Unlike swapping the global cache instance, generation invalidation
        preserves object identity for concurrent readers while preventing stale
        compilations from publishing into the new generation.
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._generation += 1
            if reset_stats:
                self._hits = 0
                self._misses = 0
                self._evictions = 0
            return count

    @property
    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "generation": self._generation,
                "hit_rate": round(hit_rate, 4),
            }

    def reset_stats(self) -> None:
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def _cache_key(
        self,
        spec: Specialization,
        token: CacheToken | None,
    ) -> tuple[int, str]:
        return self._resolve_generation(token), spec.cache_key

    def _resolve_generation(self, token: CacheToken | None) -> int:
        return self._generation if token is None else token.generation


# =============================================================================
# Global Cache Instance
# =============================================================================

_global_cache: CompilationCache | None = None
_global_cache_lock = threading.Lock()


def get_global_cache(max_size: int = 1000) -> CompilationCache:
    """Get or create the global compilation cache."""
    global _global_cache
    with _global_cache_lock:
        if _global_cache is None:
            _global_cache = CompilationCache(max_size=max_size)
        return _global_cache


def reset_global_cache() -> None:
    """Reset the global compilation cache generation (for testing)."""
    with _global_cache_lock:
        if _global_cache is not None:
            _global_cache.invalidate_all(reset_stats=True)


# =============================================================================
# Method Compiler
# =============================================================================


def _normalize_dynamic_value(value: Any) -> Any:
    if isinstance(value, (int, float, bool, np.number)):
        return jnp.asarray(value)
    if hasattr(value, "shape") and hasattr(value, "dtype"):
        return jnp.asarray(value)
    if isinstance(value, (list, tuple)):
        if not value or all(isinstance(v, (int, float, bool, np.number)) for v in value):
            return jnp.asarray(value)
    return value


_RUNTIME_PARAM_NAMES = frozenset({"__seed__", "__rng__", *VALIDATED_EXECUTION_PARAM_NAMES})


def _resolve_params(
    signature: MethodSignature,
    params: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], tuple[str, ...]]:
    params = params or {}
    known = {p.name for p in signature.parameters}
    unknown = set(params.keys()) - known - _RUNTIME_PARAM_NAMES
    if unknown:
        raise ParameterValidationError(
            param_name=",".join(sorted(unknown)),
            value=unknown,
            reason=f"Unknown parameters for {signature.fqn}",
        )

    static_params: dict[str, Any] = {}
    dynamic_defaults: dict[str, Any] = {}
    dynamic_names: list[str] = []

    for spec in signature.parameters:
        value = params.get(spec.name, spec.default)
        if spec.is_static:
            static_params[spec.name] = value
        else:
            dynamic_defaults[spec.name] = value
            dynamic_names.append(spec.name)

    return static_params, dynamic_defaults, tuple(dynamic_names)


def _values_equal(left: Any, right: Any) -> bool:
    """Compare scalar, array, and nested dynamic values without array truthiness."""
    if isinstance(left, Mapping) or isinstance(right, Mapping):
        if not isinstance(left, Mapping) or not isinstance(right, Mapping):
            return False
        if left.keys() != right.keys():
            return False
        return all(_values_equal(left[key], right[key]) for key in left)
    if isinstance(left, (list, tuple)) or isinstance(right, (list, tuple)):
        if not isinstance(left, (list, tuple)) or not isinstance(right, (list, tuple)):
            return False
        return len(left) == len(right) and all(
            _values_equal(left_item, right_item) for left_item, right_item in zip(left, right)
        )
    try:
        return bool(np.array_equal(np.asarray(left), np.asarray(right)))
    except (TypeError, ValueError):
        try:
            return bool(left == right)
        except (TypeError, ValueError):
            return left is right


def _dynamic_defaults_equal(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> bool:
    """Return whether two dynamic bindings are semantically equivalent."""
    if left.keys() != right.keys():
        return False
    return all(_values_equal(left[name], right[name]) for name in left)


def _bind_compiled_method(
    compiled: CompiledMethod,
    dynamic_defaults: Mapping[str, Any],
) -> CompiledMethod:
    """Bind current dynamic defaults to a shared immutable compiled kernel."""
    kernel = compiled._kernel
    if kernel is None:
        return compiled

    dynamic_name_set = set(kernel.dynamic_names)
    static_name_set = compiled.signature.static_param_names
    bound_defaults = MappingProxyType(dict(dynamic_defaults))

    def step_fn(state: Any, params: Mapping[str, Any] | None = None) -> Any:
        overrides = params or {}
        if overrides:
            unknown = set(overrides.keys()) - dynamic_name_set - _RUNTIME_PARAM_NAMES
            if unknown:
                static_overlap = unknown & static_name_set
                if static_overlap:
                    raise ParameterValidationError(
                        param_name=",".join(sorted(static_overlap)),
                        value=list(static_overlap),
                        reason="Static parameters require recompilation",
                    )
                raise ParameterValidationError(
                    param_name=",".join(sorted(unknown)),
                    value=list(unknown),
                    reason="Unknown dynamic parameters",
                )
        merged = dict(bound_defaults)
        merged.update({name: overrides[name] for name in kernel.dynamic_names if name in overrides})
        runtime_params = {
            name: overrides[name] for name in _RUNTIME_PARAM_NAMES if name in overrides
        }
        dynamic_values = tuple(
            _normalize_dynamic_value(merged[name]) for name in kernel.dynamic_names
        )
        return kernel.step_core(state, dynamic_values, runtime_params)

    return CompiledMethod(
        method_fqn=compiled.method_fqn,
        signature=compiled.signature,
        specialization=compiled.specialization,
        step_fn=step_fn,
        dynamic_defaults=bound_defaults,
        lowered_hlo=compiled.lowered_hlo,
        compile_time_ms=compiled.compile_time_ms,
        _kernel=kernel,
    )


def _wait_for_flight(
    flight: _InFlight,
    *,
    timeout: float,
    cancel_event: threading.Event | None,
) -> str:
    """Wait for a flight with a deadline and cooperative cancellation."""
    deadline = time.monotonic() + timeout
    while not flight.event.is_set():
        if cancel_event is not None and cancel_event.is_set():
            return "cancelled"
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return "timeout"
        flight.event.wait(min(remaining, 0.05))
    return "completed"


def _implementation_digest(method_class: type, signature: MethodSignature) -> str:
    try:
        return _stable_digest(
            {
                "signature_digest": signature.stable_digest(),
                "source": implementation_identity_projection(method_class),
            }
        )
    except SourceIdentityUnavailableError as exc:
        raise CompilationError(signature.fqn, str(exc)) from exc


class MethodCompiler:
    """
    Compiles Foundry methods to optimized JAX functions.
    """

    def __init__(
        self,
        registry: Any | None = None,
        cache: CompilationCache | None = None,
    ):
        if registry is None:
            from polisyos.foundry.methods.selection.registry import MethodRegistry

            registry = MethodRegistry.get_instance()

        self._registry = registry
        self._cache = cache or get_global_cache()

    def compile(
        self,
        method_name: str,
        params: Mapping[str, Any] | None = None,
        sample_inputs: Mapping[str, jnp.ndarray] | None = None,
        *,
        static_params: Mapping[str, Any] | None = None,
        dynamic_params: Mapping[str, Any] | None = None,
        jit: bool = True,
        capture_hlo: bool = False,
        vmap_axis: int | None = None,
        donate_argnums: tuple[int, ...] = (),
        backend: BackendSpec | None = None,
        flight_timeout: float = 30.0,
        cancel_event: threading.Event | None = None,
    ) -> CompiledMethod:
        """
        Compile a single method.

        A follower waits at most ``flight_timeout`` for an in-flight build and
        may leave that wait cooperatively through ``cancel_event``. The leader
        remains responsible for completing or publishing the shared flight.
        """
        if not math.isfinite(flight_timeout) or flight_timeout <= 0:
            raise ValueError("flight_timeout must be finite and greater than zero")
        if sample_inputs is None:
            sample_inputs = {}
        attempts = 0

        while True:
            token = self._cache.current_token()
            method_class = self._registry.get(method_name)
            sig = method_class.signature

            combined_params: dict[str, Any] = {}
            if params:
                combined_params.update(params)
            if static_params:
                combined_params.update(static_params)
            if dynamic_params:
                combined_params.update(dynamic_params)

            static_values, dynamic_defaults, dynamic_names = _resolve_params(sig, combined_params)

            spec = build_specialization(
                method_fqn=sig.fqn,
                static_params=static_values,
                input_arrays=sample_inputs,
                backend=backend,
                jit_enabled=jit,
                vmap_axis=vmap_axis,
                donate_argnums=donate_argnums,
                implementation_hash=_implementation_digest(method_class, sig),
            )

            cached = self._cache.get(spec, token=token)
            if cached is not None:
                if _dynamic_defaults_equal(cached.dynamic_defaults, dynamic_defaults):
                    return cached
                return _bind_compiled_method(cached, dynamic_defaults)

            flight_key = f"{token.generation}:{spec.cache_key}"
            flight, leader = self._cache.claim_flight(flight_key, spec=spec, token=token)

            if not leader:
                wait_status = _wait_for_flight(
                    flight,
                    timeout=flight_timeout,
                    cancel_event=cancel_event,
                )
                if wait_status == "timeout":
                    raise CompilationError(sig.fqn, "Compilation wait deadline exceeded")
                if wait_status == "cancelled":
                    raise CompilationError(sig.fqn, "Compilation wait cancelled")
                if flight.error is not None:
                    if isinstance(flight.error, Exception):
                        raise CompilationError(sig.fqn, str(flight.error))
                    raise flight.error
                if flight.result is not None:
                    if self._cache.current_token() != token:
                        attempts += 1
                        if attempts >= 3:
                            raise CompilationError(
                                sig.fqn,
                                "Compilation invalidated before follower result",
                            )
                        continue
                    if _dynamic_defaults_equal(flight.result.dynamic_defaults, dynamic_defaults):
                        return flight.result
                    return _bind_compiled_method(flight.result, dynamic_defaults)
                if not flight.invalidated:
                    cached = self._cache.get(spec, token=token)
                    if cached is not None:
                        if _dynamic_defaults_equal(cached.dynamic_defaults, dynamic_defaults):
                            return cached
                        return _bind_compiled_method(cached, dynamic_defaults)
                attempts += 1
                if attempts >= 3:
                    raise CompilationError(
                        sig.fqn,
                        "Compilation invalidated before publication",
                    )
                continue

            start_time = time.monotonic()
            try:
                kernel = self._compile_method(
                    method_class=method_class,
                    signature=sig,
                    specialization=spec,
                    static_params=dict(static_values),
                    dynamic_defaults=dict(dynamic_defaults),
                    dynamic_names=dynamic_names,
                    jit=jit,
                    capture_hlo=capture_hlo,
                    vmap_axis=vmap_axis,
                    donate_argnums=donate_argnums,
                )
                compile_time_ms = (time.monotonic() - start_time) * 1000
                template = CompiledMethod(
                    method_fqn=sig.fqn,
                    signature=sig,
                    specialization=spec,
                    step_fn=lambda state, params: kernel.step_core(state, (), params),
                    dynamic_defaults=MappingProxyType(dict(dynamic_defaults)),
                    lowered_hlo=None,
                    compile_time_ms=compile_time_ms,
                    _kernel=kernel,
                )
                compiled = _bind_compiled_method(template, dynamic_defaults)
                if _implementation_digest(method_class, sig) != spec.implementation_hash:
                    raise CompilationError(sig.fqn, "Implementation changed during compilation")
                published = self._cache.publish_flight(
                    flight_key,
                    flight,
                    spec,
                    compiled,
                    token=token,
                )
            except BaseException as exc:
                self._cache.complete_flight(flight_key, flight, error=exc)
                if isinstance(exc, Exception):
                    raise CompilationError(sig.fqn, str(exc)) from exc
                raise

            if published:
                if self._cache.current_token() == token:
                    return compiled
                attempts += 1
                if attempts >= 3:
                    raise CompilationError(
                        sig.fqn,
                        "Compilation invalidated after publication",
                    )
                continue

            self._cache.complete_flight(flight_key, flight, invalidated=True)

            attempts += 1
            if attempts >= 3:
                raise CompilationError(
                    sig.fqn,
                    "Compilation invalidated by concurrent cache generation change",
                )

    def _compile_method(
        self,
        method_class: type,
        signature: MethodSignature,
        specialization: Specialization,
        static_params: dict[str, Any],
        dynamic_defaults: dict[str, Any],
        dynamic_names: tuple[str, ...],
        jit: bool,
        capture_hlo: bool,
        vmap_axis: int | None,
        donate_argnums: tuple[int, ...],
    ) -> _CompiledKernel:
        """
        Internal compilation logic.
        """
        del dynamic_defaults
        pure_step = method_class.pure_step

        @functools.wraps(pure_step)
        def step_with_statics(
            state: Any,
            dynamic_values: tuple[Any, ...],
            runtime_params: Mapping[str, Any],
        ) -> Any:
            if specialization.implementation_hash and (
                _implementation_digest(method_class, signature)
                != specialization.implementation_hash
            ):
                raise CompilationError(
                    signature.fqn, "Implementation changed before kernel tracing"
                )
            dynamic_params = {name: value for name, value in zip(dynamic_names, dynamic_values)}
            all_params = {**static_params, **dynamic_params, **runtime_params}
            return pure_step(state, all_params)

        if vmap_axis is not None:
            step_with_statics = jax.vmap(
                step_with_statics,
                in_axes=(vmap_axis, None, None),
            )

        if jit:
            jit_kwargs: dict[str, Any] = {}
            if donate_argnums:
                jit_kwargs["donate_argnums"] = donate_argnums
            step_core = jax.jit(step_with_statics, **jit_kwargs)
        else:
            step_core = step_with_statics

        if capture_hlo:
            # Placeholder for optional HLO capture.
            # Requires sample inputs/state to lower; not performed here.
            pass

        return _CompiledKernel(step_core=step_core, dynamic_names=dynamic_names)

    def compile_chain(
        self,
        chain: Any,
        sample_state: Any,
        *,
        jit: bool = True,
        infer_shapes: bool = True,
    ) -> CompiledChainExecutor:
        """
        Compile an entire method chain.
        """
        from polisyos.foundry.methods.components.composer import CompiledMethodChain, MethodNode

        if not isinstance(chain, CompiledMethodChain):
            raise TypeError(f"Expected CompiledMethodChain, got {type(chain)}")

        compiled_methods: list[tuple[MethodNode, CompiledMethod]] = []
        method_classes = {
            chain.get_signature(node_id).fqn: self._registry.get(chain.get_signature(node_id).fqn)
            for node_id in chain.execution_order
        }
        if infer_shapes:
            shape_values: dict[str, Any] = {}
            for node_id in chain.execution_order:
                shape_values.update(
                    self._infer_input_shapes(chain.get_signature(node_id), sample_state)
                )
        else:
            shape_values = sample_state
        unresolved_outputs: set[str] = set()
        occurrence_shapes: dict[UUID, dict[str, Any]] = {}
        unresolved_by_occurrence: dict[UUID, set[str]] = {}

        for node_id in chain.execution_order:
            node = chain.get_node(node_id)
            sig = chain.get_signature(node_id)
            if method_classes[sig.fqn].signature.stable_digest() != sig.stable_digest():
                raise CompilationError(
                    sig.fqn, "Current method ABI disagrees with the compiled chain"
                )

            input_shapes = self._infer_input_shapes(sig, shape_values)
            bound_unknown: set[str] = set()
            for binding in chain.get_bindings_for_target(node_id):
                source_id = binding.source_node_id
                source_shape = occurrence_shapes.get(source_id, {}).get(binding.source_slot)
                if source_shape is not None:
                    input_shapes[binding.target_slot] = source_shape
                elif binding.source_slot in unresolved_by_occurrence.get(source_id, set()):
                    input_shapes.pop(binding.target_slot, None)
                    bound_unknown.add(binding.target_slot)
            missing_shapes = [
                slot.name
                for slot in sig.input_slots
                if (slot.name in unresolved_outputs or slot.name in bound_unknown)
                and slot.name not in input_shapes
            ]
            if missing_shapes:
                raise CompilationError(
                    sig.fqn,
                    "shape inference unavailable for data-dependent output(s): "
                    + ", ".join(sorted(missing_shapes)),
                )

            params = dict(node.static_params)
            params.update(node.params)

            compiled = self.compile(
                method_name=sig.fqn,
                params=params,
                sample_inputs=input_shapes,
                jit=jit,
            )
            if compiled.specialization.implementation_hash != _implementation_digest(
                method_classes[sig.fqn], sig
            ):
                raise CompilationError(
                    sig.fqn, "Registry implementation changed during chain compilation"
                )
            compiled_methods.append((node, compiled))

            if infer_shapes:
                node_shapes: dict[str, Any] = {}
                node_unknown = self._update_output_shapes(sig, input_shapes, node_shapes, set())
                occurrence_shapes[node_id] = node_shapes
                unresolved_by_occurrence[node_id] = node_unknown
                unresolved_outputs = self._update_output_shapes(
                    sig,
                    input_shapes,
                    shape_values,
                    unresolved_outputs,
                )

        return CompiledChainExecutor(
            chain=chain,
            compiled_methods=tuple(compiled_methods),
            method_classes=MappingProxyType(method_classes),
            _runtime_compiler=MethodCompiler(
                registry=_CompiledMethods(method_classes), cache=self._cache
            ),
        )

    def _infer_input_shapes(
        self,
        sig: MethodSignature,
        state: Any,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for slot in sig.input_slots:
            slot_name = slot.name
            if isinstance(state, Mapping) and slot_name in state:
                arr = state[slot_name]
                if hasattr(arr, "shape"):
                    result[slot_name] = arr
            elif hasattr(state, slot_name):
                arr = getattr(state, slot_name)
                if hasattr(arr, "shape"):
                    result[slot_name] = arr
            elif hasattr(state, "__getitem__"):
                try:
                    arr = state[slot_name]
                    if hasattr(arr, "shape"):
                        result[slot_name] = arr
                except (KeyError, TypeError):
                    pass
        return result

    def _update_output_shapes(
        self,
        sig: MethodSignature,
        input_shapes: Mapping[str, Any],
        shape_values: Mapping[str, Any] | dict[str, Any],
        unresolved_outputs: set[str],
    ) -> set[str]:
        """Propagate declared output shapes without executing a method body."""
        dimensions: dict[str, int] = {}
        for slot in sig.input_slots:
            arr = input_shapes.get(slot.name)
            if arr is None or not hasattr(arr, "shape") or len(slot.shape) != len(arr.shape):
                continue
            for expression, size in zip(slot.shape, arr.shape):
                if isinstance(expression, int):
                    if expression != int(size):
                        raise CompilationError(
                            sig.fqn,
                            f"input shape mismatch for {slot.name}: expected "
                            f"{expression}, got {size}",
                        )
                    continue
                name = getattr(
                    expression,
                    "name",
                    expression if isinstance(expression, str) else None,
                )
                if name is None:
                    continue
                prior = dimensions.get(name)
                if prior is not None and prior != int(size):
                    raise CompilationError(
                        sig.fqn,
                        f"symbolic dimension {name!r} is inconsistent",
                    )
                dimensions[name] = int(size)

        next_unresolved = set(unresolved_outputs)
        for slot in sig.output_slots:
            output_shape: list[int] = []
            known = True
            for expression in slot.shape:
                if isinstance(expression, int):
                    output_shape.append(expression)
                    continue
                name = getattr(
                    expression,
                    "name",
                    expression if isinstance(expression, str) else None,
                )
                if name is None or name not in dimensions:
                    known = False
                    break
                output_shape.append(dimensions[name])
            if not known:
                next_unresolved.add(slot.name)
                if isinstance(shape_values, dict):
                    shape_values.pop(slot.name, None)
                continue

            existing = shape_values.get(slot.name)
            dtype = getattr(existing, "dtype", None)
            if dtype is None:
                dtype = next(
                    (
                        getattr(arr, "dtype", None)
                        for arr in input_shapes.values()
                        if hasattr(arr, "dtype")
                    ),
                    np.float32,
                )
            if isinstance(shape_values, dict):
                shape_values[slot.name] = np.empty(tuple(output_shape), dtype=dtype)
            next_unresolved.discard(slot.name)
        return next_unresolved

    def warmup(
        self,
        method_name: str,
        params: Mapping[str, Any] | None,
        sample_inputs: Mapping[str, jnp.ndarray],
        sample_state: Any,
        n_warmup: int = 3,
    ) -> CompiledMethod:
        """
        Compile and warmup a method.
        """
        compiled = self.compile(
            method_name=method_name,
            params=params,
            sample_inputs=sample_inputs,
        )

        for _ in range(n_warmup):
            out = compiled.step_fn(sample_state, compiled.dynamic_defaults)
            _block_until_ready(out)

        return compiled

    @property
    def cache_stats(self) -> dict[str, Any]:
        return self._cache.stats


# =============================================================================
# Chain Executor
# =============================================================================


@dataclass(frozen=True, slots=True)
class CompiledChainExecutor:
    """
    Executor for a compiled method chain.
    """

    chain: Any
    compiled_methods: tuple[tuple[Any, CompiledMethod], ...]
    method_classes: Mapping[str, type] = field(default_factory=dict)
    _runtime_compiler: MethodCompiler | None = field(default=None, repr=False, compare=False)

    def __call__(
        self,
        state: Any,
        params: Mapping[str | UUID, Mapping[str, Any]] | None = None,
    ) -> Any:
        params = params or {}
        current_state = state
        current_context = state
        node_slot_outputs: dict[UUID, Mapping[str, Any]] = {}
        registry = _CompiledMethods(self.method_classes)

        for node, compiled in self.compiled_methods:
            method_class = registry.get(node.method_fqn)
            if (
                _implementation_digest(method_class, compiled.signature)
                != compiled.specialization.implementation_hash
            ):
                raise CompilationError(
                    node.method_fqn, "Implementation changed before chain execution"
                )
            overrides = params.get(node.id, params.get(node.method_fqn))
            if overrides:
                static_overlap = compiled.signature.static_param_names & overrides.keys()
                if static_overlap:
                    raise ParameterValidationError(
                        param_name=",".join(sorted(static_overlap)),
                        value=list(static_overlap),
                        reason="Static parameters require recompilation",
                    )
            method_class, materialized, signature, payload = collect_chain_node_inputs(
                self.chain,
                node.id,
                registry,
                node_slot_outputs,
                None,
                current_state,
                compiled.signature,
                current_context,
                None if overrides is None else {node.id: overrides},
            )
            dynamic_payload = {
                name: value
                for name, value in payload.items()
                if name not in signature.static_param_names
            }
            # Declared downstream shape/dtype metadata is preparation only.
            # Reconcile the cache key with the real materialized input before
            # executing a node; this does not perform its numerical body twice.
            if self._runtime_compiler is not None:
                actual_inputs = self._runtime_compiler._infer_input_shapes(signature, materialized)
                if (
                    len(signature.input_slots) == 1
                    and hasattr(materialized, "shape")
                    and hasattr(materialized, "dtype")
                ):
                    actual_inputs[next(iter(signature.input_slots)).name] = materialized
                actual_shapes = tuple(
                    (name, ShapeSpec.from_array(value))
                    for name, value in sorted(actual_inputs.items())
                )
                if actual_shapes != compiled.specialization.input_shapes:
                    compiled = self._runtime_compiler.compile(
                        node.method_fqn,
                        params=payload,
                        sample_inputs=actual_inputs,
                        jit=compiled.specialization.jit_enabled,
                        backend=compiled.specialization.backend,
                        vmap_axis=compiled.specialization.vmap_axis,
                        donate_argnums=compiled.specialization.donate_argnums,
                    )
            current_state = compiled.step_fn(materialized, dynamic_payload)
            node_slot_outputs[node.id] = dematerialize_method_output(
                method_class=method_class,
                signature=signature,
                output=current_state,
            )
            current_context = merge_chain_execution_context(current_context, current_state)

        return current_state

    def __len__(self) -> int:
        return len(self.compiled_methods)

    @property
    def execution_order(self) -> list[str]:
        return [compiled.method_fqn for _, compiled in self.compiled_methods]

    @property
    def total_compile_time_ms(self) -> float:
        return sum(c.compile_time_ms for _, c in self.compiled_methods)


@dataclass(frozen=True, slots=True)
class _CompiledMethods:
    methods: Mapping[str, type]

    def get(self, fqn: str) -> type:
        try:
            return self.methods[fqn]
        except KeyError as exc:
            raise CompilationError(fqn, "Compiled chain lacks its owning method class") from exc


# =============================================================================
# Utilities
# =============================================================================


def _block_until_ready(value: Any) -> None:
    def _ready(x: Any) -> Any:
        if hasattr(x, "block_until_ready"):
            x.block_until_ready()
        return x

    jax.tree_util.tree_map(_ready, value)
