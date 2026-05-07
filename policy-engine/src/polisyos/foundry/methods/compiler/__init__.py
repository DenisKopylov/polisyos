"""
Method Compiler - compiles Foundry methods to optimized JAX functions.

Implements Law H (deterministic compilation) and Law I (static vs dynamic
parameters) with a deterministic specialization key and a thread-safe
single-flight compilation cache.
"""

from __future__ import annotations

import functools
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol, TypeVar

import jax
import jax.numpy as jnp
import numpy as np

from polisyos.foundry.methods.backends.validated import VALIDATED_EXECUTION_PARAM_NAMES
from polisyos.foundry.methods.base import MethodSignature
from polisyos.foundry.methods.exceptions import CompilationError, ParameterValidationError
from polisyos.foundry.methods.compiler.specialization import (
    BackendSpec,
    Specialization,
    build_specialization,
)

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


class FoundryMethodProtocol(Protocol):
    """Protocol for type checking FoundryMethod classes."""

    signature: MethodSignature

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> Any: ...


# =============================================================================
# Compiled Method
# =============================================================================


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
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._generation = 0

    def current_token(self) -> CacheToken:
        with self._lock:
            return CacheToken(self._generation)

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

            key = (generation, spec.cache_key)
            if key in self._cache:
                self._cache[key] = CacheEntry(
                    compiled=compiled,
                    last_access=time.monotonic(),
                    access_count=1,
                )
                self._cache.move_to_end(key)
                return True

            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
                self._evictions += 1

            self._cache[key] = CacheEntry(
                compiled=compiled,
                last_access=time.monotonic(),
                access_count=1,
            )
            return True

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


@dataclass(slots=True)
class _InFlight:
    event: threading.Event
    error: Exception | None = None


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
        self._inflight_lock = threading.Lock()
        self._inflight: dict[str, _InFlight] = {}

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
    ) -> CompiledMethod:
        """
        Compile a single method.
        """
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
            )

            cached = self._cache.get(spec, token=token)
            if cached is not None:
                return cached

            flight_key = f"{token.generation}:{spec.cache_key}"
            with self._inflight_lock:
                flight = self._inflight.get(flight_key)
                if flight is None:
                    flight = _InFlight(event=threading.Event())
                    self._inflight[flight_key] = flight
                    leader = True
                else:
                    leader = False

            if not leader:
                flight.event.wait()
                cached = self._cache.get(spec, token=token)
                if cached is not None:
                    return cached
                if flight.error is not None:
                    raise CompilationError(sig.fqn, str(flight.error))
                attempts += 1
                if attempts >= 3:
                    raise CompilationError(
                        sig.fqn,
                        "Compilation invalidated before publication",
                    )
                continue

            start_time = time.monotonic()
            try:
                compiled_step = self._compile_method(
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
            except Exception as exc:
                flight.error = exc
                raise CompilationError(sig.fqn, str(exc)) from exc
            finally:
                with self._inflight_lock:
                    self._inflight.pop(flight_key, None)
                    flight.event.set()

            compile_time_ms = (time.monotonic() - start_time) * 1000

            compiled = CompiledMethod(
                method_fqn=sig.fqn,
                signature=sig,
                specialization=spec,
                step_fn=compiled_step,
                dynamic_defaults=MappingProxyType(dict(dynamic_defaults)),
                lowered_hlo=None,
                compile_time_ms=compile_time_ms,
            )

            if self._cache.put(spec, compiled, token=token):
                return compiled

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
    ) -> CompiledStepFn:
        """
        Internal compilation logic.
        """
        pure_step = method_class.pure_step
        dynamic_name_set = set(dynamic_names)
        static_name_set = signature.static_param_names

        def pack_dynamic_params(
            overrides: Mapping[str, Any] | None,
        ) -> tuple[tuple[Any, ...], dict[str, Any]]:
            overrides = overrides or {}
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
            merged = dict(dynamic_defaults)
            merged.update({name: overrides[name] for name in dynamic_names if name in overrides})
            runtime_params = {
                name: overrides[name] for name in _RUNTIME_PARAM_NAMES if name in overrides
            }
            return (
                tuple(_normalize_dynamic_value(merged[name]) for name in dynamic_names),
                runtime_params,
            )

        @functools.wraps(pure_step)
        def step_with_statics(
            state: Any,
            dynamic_values: tuple[Any, ...],
            runtime_params: Mapping[str, Any],
        ) -> Any:
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

        def step_fn(state: Any, params: Mapping[str, Any] | None = None) -> Any:
            dynamic_values, runtime_params = pack_dynamic_params(params)
            return step_core(state, dynamic_values, runtime_params)

        if capture_hlo:
            # Placeholder for optional HLO capture.
            # Requires sample inputs/state to lower; not performed here.
            pass

        return step_fn

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
        current_state = sample_state

        for node_id in chain.execution_order:
            node = chain.get_node(node_id)
            sig = chain.get_signature(node_id)
            method_class = self._registry.get(sig.fqn)

            input_shapes = self._infer_input_shapes(sig, current_state)

            params = dict(node.static_params)
            params.update(node.params)

            compiled = self.compile(
                method_name=sig.fqn,
                params=params,
                sample_inputs=input_shapes,
                jit=jit,
            )
            compiled_methods.append((node, compiled))

            if infer_shapes:
                try:
                    current_state = method_class.pure_step(current_state, params)
                except Exception as exc:
                    raise CompilationError(
                        sig.fqn,
                        f"shape inference failed: {exc}",
                    ) from exc

        return CompiledChainExecutor(
            chain=chain,
            compiled_methods=tuple(compiled_methods),
        )

    def _infer_input_shapes(
        self,
        sig: MethodSignature,
        state: Any,
    ) -> dict[str, jnp.ndarray]:
        result: dict[str, jnp.ndarray] = {}
        for slot in sig.input_slots:
            slot_name = slot.name
            if hasattr(state, slot_name):
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

    def __call__(
        self,
        state: Any,
        params: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> Any:
        params = params or {}
        current_state = state

        for node, compiled in self.compiled_methods:
            method_params = dict(node.params)
            overrides = params.get(node.method_fqn)
            if overrides:
                static_overlap = compiled.signature.static_param_names & overrides.keys()
                if static_overlap:
                    raise ParameterValidationError(
                        param_name=",".join(sorted(static_overlap)),
                        value=list(static_overlap),
                        reason="Static parameters require recompilation",
                    )
                method_params.update(overrides)

            current_state = compiled.step_fn(current_state, method_params)

        return current_state

    def __len__(self) -> int:
        return len(self.compiled_methods)

    @property
    def execution_order(self) -> list[str]:
        return [compiled.method_fqn for _, compiled in self.compiled_methods]

    @property
    def total_compile_time_ms(self) -> float:
        return sum(c.compile_time_ms for _, c in self.compiled_methods)


# =============================================================================
# Utilities
# =============================================================================


def _block_until_ready(value: Any) -> None:
    def _ready(x: Any) -> Any:
        if hasattr(x, "block_until_ready"):
            x.block_until_ready()
        return x

    jax.tree_util.tree_map(_ready, value)
