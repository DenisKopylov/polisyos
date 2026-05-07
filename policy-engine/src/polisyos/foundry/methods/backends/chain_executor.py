"""Execute a composed method DAG and convert slot bindings across backend outputs."""

from __future__ import annotations

import asyncio
import re
import threading
import time as _time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol
from uuid import UUID

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods._internal.logging import get_foundry_logger
from polisyos.foundry.methods.backends.adapters import adapt_state
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodTiming,
    ReproducibilityInfo,
)
from polisyos.foundry.methods.backends.runtime_fingerprint import (
    capture_backend_runtime_fingerprint,
    capture_versions,
    compose_observed_tolerance_budgets,
    meet_determinism_tiers,
    runtime_stack_for,
    safe_version,
)
from polisyos.foundry.methods.base import ComputeBackend, _stable_digest
from polisyos.foundry.methods.exceptions import MethodContractError
from polisyos.foundry.methods.components.io import (
    dematerialize_method_output,
    materialize_method_input,
    validate_value_for_slot,
)
from polisyos.foundry.methods.selection.registry import MethodRegistry
from polisyos.foundry.methods.types.checker import ShapeAdapterKind

try:
    from polisyos.foundry.methods.backends.async_chain_executor import AsyncChainExecutor
except Exception:  # pragma: no cover - fallback when optional deps are missing
    AsyncChainExecutor = None  # type: ignore[assignment]

_log = get_foundry_logger("foundry.backends.chain")


ExecutorMode = Literal["auto", "sequential", "async", "ray"]


class FxRateProvider(Protocol):
    """Protocol for runtime FX conversion providers."""

    def get_rate(
        self,
        source_symbol: str,
        target_symbol: str,
        context: Any | None = None,
    ) -> float: ...


@dataclass(frozen=True, slots=True)
class StaticFxRateProvider:
    """Static exchange-rate lookup by unit symbol pairs."""

    rates: Mapping[tuple[str, str] | str, float]

    @staticmethod
    def _coerce_rate_value(value: object) -> float:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise MethodContractError(
                "fx-rate-provider",
                f"FX rate is not numeric: {value!r}",
            ) from exc

    def get_rate(
        self,
        source_symbol: str,
        target_symbol: str,
        context: Any | None = None,
    ) -> float:
        key_tuple = (source_symbol, target_symbol)
        key_arrow = f"{source_symbol}->{target_symbol}"
        key_slash = f"{source_symbol}/{target_symbol}"
        if key_tuple in self.rates:
            return self._coerce_rate_value(self.rates[key_tuple])
        if key_arrow in self.rates:
            return self._coerce_rate_value(self.rates[key_arrow])
        if key_slash in self.rates:
            return self._coerce_rate_value(self.rates[key_slash])
        raise MethodContractError(
            "fx-rate-provider",
            f"No FX rate found for {source_symbol} -> {target_symbol}.",
        )


@dataclass(frozen=True, slots=True)
class TimestampedFxRateProvider:
    """FX rates grouped by timestamp / period."""

    rates_by_period: Mapping[str, Mapping[tuple[str, str] | str, float]]
    period_selector: Callable[[Any], str] | None = None
    fallback_to_single_period: bool = True

    @staticmethod
    def _extract_period(context: Any) -> str | None:
        if context is None:
            return None
        if isinstance(context, Mapping):
            for key in ("timestamp", "time", "date", "period", "as_of"):
                value = context.get(key)
                if value is not None:
                    return str(value)
            for key in ("time_id", "period_id"):
                value = context.get(key)
                if value is not None:
                    return str(value)
        return None

    def _resolve_period(self, context: Any) -> str:
        if self.period_selector is not None:
            return self.period_selector(context)
        resolved = self._extract_period(context)
        if resolved is not None:
            return resolved
        if self.fallback_to_single_period and len(self.rates_by_period) == 1:
            return next(iter(self.rates_by_period))
        raise MethodContractError(
            "fx-rate-provider",
            "Unable to resolve FX rate period from context.",
        )

    def get_rate(
        self,
        source_symbol: str,
        target_symbol: str,
        context: Any | None = None,
    ) -> float:
        period = self._resolve_period(context)
        period_rates = self.rates_by_period.get(period)
        if period_rates is None:
            raise MethodContractError(
                "fx-rate-provider",
                f"No FX rates configured for period '{period}'.",
            )
        return StaticFxRateProvider(period_rates).get_rate(
            source_symbol,
            target_symbol,
            context=context,
        )


@dataclass(frozen=True, slots=True)
class LevelAwareExecutor:
    """Select async mode when a parallel level appears."""

    parallel_threshold: int = 2

    def choose_mode(self, chain: Any) -> Literal["sequential", "async", "ray"]:
        if self.parallel_threshold <= 1:
            return "async"
        try:
            levels = chain.dag.compute_parallel_levels()
        except Exception:
            return "sequential"
        if any(len(level) >= self.parallel_threshold for level in levels):
            return "async"
        return "sequential"


@dataclass(frozen=True, slots=True)
class ChainExecutionResult:
    """Collect the final composed state plus per-node backend results."""

    final_state: Any
    node_results: tuple[tuple[UUID, MethodResult], ...]
    reproducibility_contract: Mapping[str, Any] = field(default_factory=dict)

    @property
    def total_wall_time_ms(self) -> float:
        return sum(result.timing.wall_time_ms for _, result in self.node_results)


def _build_chain_reproducibility_contract(
    node_results: list[tuple[UUID, MethodResult]] | tuple[tuple[UUID, MethodResult], ...],
    *,
    composition_kind: str,
) -> dict[str, Any]:
    budgets = [
        dict(result.reproducibility.observed_tolerance_budget or {}) for _, result in node_results
    ]
    tiers = [result.reproducibility.determinism_tier for _, result in node_results]
    composed_budget = compose_observed_tolerance_budgets(
        budgets,
        determinism_tiers=tiers,
        composition_kind=composition_kind,
    )
    observed_tier = composed_budget.get("downgraded_to") or (
        None if meet_determinism_tiers(tiers) is None else meet_determinism_tiers(tiers).value
    )
    executed_backends = list(
        dict.fromkeys(result.reproducibility.backend.value for _, result in node_results)
    )
    return {
        "determinism_tier": observed_tier,
        "observed_tolerance_budget": composed_budget,
        "executed_backends": executed_backends,
        "node_count": len(node_results),
        "composition_kind": composition_kind,
    }


def _build_level_parallel_reproducibility_contract(
    levels: list[list[UUID]],
    node_results: list[tuple[UUID, MethodResult]] | tuple[tuple[UUID, MethodResult], ...],
) -> dict[str, Any]:
    result_by_node = {node_id: result for node_id, result in node_results}
    level_budgets: list[Mapping[str, Any]] = []
    level_tiers: list[DeterminismTier | None] = []
    for level in levels:
        level_results = [
            (node_id, result_by_node[node_id]) for node_id in level if node_id in result_by_node
        ]
        if not level_results:
            continue
        level_contract = _build_chain_reproducibility_contract(
            level_results,
            composition_kind="concat",
        )
        level_budgets.append(dict(level_contract.get("observed_tolerance_budget") or {}))
        level_tiers.append(
            meet_determinism_tiers(
                [result.reproducibility.determinism_tier for _, result in level_results]
            )
        )
    composed_budget = compose_observed_tolerance_budgets(
        level_budgets,
        determinism_tiers=level_tiers,
        composition_kind="serial",
    )
    observed_tier = composed_budget.get("downgraded_to") or (
        None
        if meet_determinism_tiers(level_tiers) is None
        else meet_determinism_tiers(level_tiers).value
    )
    executed_backends = list(
        dict.fromkeys(result.reproducibility.backend.value for _, result in node_results)
    )
    return {
        "determinism_tier": observed_tier,
        "observed_tolerance_budget": composed_budget,
        "executed_backends": executed_backends,
        "node_count": len(node_results),
        "composition_kind": "level_parallel",
        "level_count": len(levels),
    }


@dataclass(frozen=True)
class _FusedKernelCacheEntry:
    kernel: Callable[[Any, tuple[Any, ...], tuple[Any, ...]], tuple[Any, Any]]
    static_params_a: dict[str, Any]
    static_params_b: dict[str, Any]
    dynamic_names_a: tuple[str, ...]
    dynamic_names_b: tuple[str, ...]
    compile_time_ms: float


class _FusedJitCache:
    """Process-local LRU cache for fused JAX kernels."""

    def __init__(self, max_size: int = 64):
        self._max_size = max_size
        self._entries: OrderedDict[str, _FusedKernelCacheEntry] = OrderedDict()
        self._lock = threading.Lock()

    def _touch(self, key: str) -> None:
        if key in self._entries:
            self._entries.move_to_end(key)

    def get_or_build(
        self,
        key: str,
        builder: Callable[[], _FusedKernelCacheEntry],
    ) -> tuple[_FusedKernelCacheEntry, bool]:
        with self._lock:
            existing = self._entries.get(key)
            if existing is not None:
                self._touch(key)
                return existing, True

        new_entry = builder()
        with self._lock:
            existing = self._entries.get(key)
            if existing is not None:
                self._touch(key)
                return existing, True

            self._entries[key] = new_entry
            self._touch(key)
            while len(self._entries) > self._max_size:
                self._entries.popitem(last=False)
            return new_entry, False


_FUSED_JIT_CACHE = _FusedJitCache()


def _build_node_param_payload(
    node,
    params_per_node: Mapping[UUID, Mapping[str, Any]] | None,
) -> dict[str, Any]:
    combined_params = dict(node.static_params)
    combined_params.update(node.params)
    if params_per_node and node.id in params_per_node:
        combined_params.update(params_per_node[node.id])
    return combined_params


def _resolve_dynamic_payload(
    signature,
    params: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], tuple[str, ...]]:
    from polisyos.foundry.methods.compiler import _resolve_params  # lazy: compiler imports jax

    return _resolve_params(signature, params)


def _pack_dynamic_values(
    dynamic_defaults: Mapping[str, Any],
    dynamic_names: tuple[str, ...],
    params: Mapping[str, Any],
) -> tuple[Any, ...]:
    from polisyos.foundry.methods.compiler import (
        _normalize_dynamic_value,
    )  # lazy: compiler imports jax

    merged = dict(dynamic_defaults)
    merged.update(params)
    return tuple(_normalize_dynamic_value(merged[name]) for name in dynamic_names)


def _make_fused_kernel_key(
    signature_a,
    signature_b,
    static_params_a: Mapping[str, Any],
    static_params_b: Mapping[str, Any],
    dynamic_names_a: tuple[str, ...],
    dynamic_names_b: tuple[str, ...],
    b_input_slot: str,
) -> str:
    payload = {
        "version": "fused-v1",
        "a": signature_a.stable_digest(),
        "b": signature_b.stable_digest(),
        "b_input_slot": b_input_slot,
        "static_a": static_params_a,
        "static_b": static_params_b,
        "dynamic_names_a": dynamic_names_a,
        "dynamic_names_b": dynamic_names_b,
    }
    return _stable_digest(payload)


def _collect_node_inputs(
    chain,
    node_id: UUID,
    reg,
    node_slot_outputs: Mapping[UUID, Mapping[str, Any]],
    fx_rate_provider: FxRateProvider | None,
    current_state: Any,
    signature,
    current_context: Any,
    params_per_node: Mapping[UUID, Mapping[str, Any]] | None,
) -> tuple[Any, Any, Mapping[str, Any], dict[str, Any]]:
    method_class = reg.get(signature.fqn)
    node = chain.get_node(node_id)
    combined_params = _build_node_param_payload(node, params_per_node)

    bound_inputs: dict[str, Any] = {}
    for binding in chain.get_bindings_for_target(node_id):
        source_node_id = binding.source_node_id
        if source_node_id is None:
            raise MethodContractError(
                signature.fqn,
                f"binding for target slot '{binding.target_slot}' is missing source_node_id",
            )
        source_outputs = node_slot_outputs.get(source_node_id)
        if source_outputs is None:
            raise MethodContractError(
                signature.fqn,
                (
                    f"binding source node {source_node_id} for target slot "
                    f"'{binding.target_slot}' has not produced slot outputs"
                ),
            )
        if binding.source_slot not in source_outputs:
            raise MethodContractError(
                signature.fqn,
                (
                    f"source slot '{binding.source_slot}' was not produced by "
                    f"{binding.source_method}"
                ),
            )

        source_value = source_outputs[binding.source_slot]
        source_backend = chain.get_signature(source_node_id).backend
        if source_backend is not signature.backend:
            source_value = adapt_state(
                source_value,
                source_backend=source_backend,
                target_backend=signature.backend,
            )
        source_value = _apply_binding_adapters(
            source_value,
            binding=binding,
            target_backend=signature.backend,
            fx_rate_provider=fx_rate_provider,
            context=current_state,
        )

        target_slot = signature.get_input_slot(binding.target_slot)
        if target_slot is None:
            raise MethodContractError(
                signature.fqn,
                f"target slot '{binding.target_slot}' is not declared by method",
            )
        validate_value_for_slot(
            target_slot,
            source_value,
            method_fqn=signature.fqn,
            label="input",
        )
        bound_inputs[binding.target_slot] = source_value

    materialized_state = materialize_method_input(
        method_class=method_class,
        signature=signature,
        bound_inputs=bound_inputs,
        fallback_state=current_context,
    )
    return method_class, materialized_state, signature, combined_params


def _can_fuse_pair(chain, node_a_id: UUID, node_b_id: UUID) -> bool:
    signature_a = chain.get_signature(node_a_id)
    signature_b = chain.get_signature(node_b_id)
    if signature_a.backend != ComputeBackend.JAX or signature_b.backend != ComputeBackend.JAX:
        return False
    if not signature_a.supports_jit or not signature_b.supports_jit:
        return False
    if chain.dag.predecessors.get(node_b_id) != {node_a_id}:
        return False
    if chain.dag.successors.get(node_a_id) != {node_b_id}:
        return False
    if len(signature_a.output_slot_names) != 1:
        return False
    if len(signature_b.input_slot_names) != 1:
        return False

    bindings = chain.get_bindings_for_target(node_b_id)
    if len(bindings) != 1:
        return False
    if not all(binding.source_node_id == node_a_id for binding in bindings):
        return False

    expected_targets = set(signature_b.input_slot_names)
    provided_targets = {binding.target_slot for binding in bindings}
    if expected_targets != provided_targets:
        return False

    for binding in bindings:
        compatibility = binding.compatibility
        if (
            compatibility.requires_conversion
            or compatibility.requires_fx_rate
            or compatibility.adapter_plan.shape.kind != ShapeAdapterKind.IDENTITY
        ):
            return False

    return True


def _build_fused_result(
    *,
    method_class,
    signature,
    output: Any,
    wall_time_ms: float,
    compile_time_ms: float,
    params: Mapping[str, Any],
    seed: int,
    reproducibility_fingerprint: str,
    deterministic_note: str,
) -> MethodResult:
    slot_outputs = dematerialize_method_output(
        method_class=method_class,
        signature=signature,
        output=output,
    )

    versions = capture_versions(
        base_packages=("jax", "jaxlib"),
        runtime_stack=runtime_stack_for(method_class),
    )
    try:
        import jax  # type: ignore[import-not-found]

        versions.setdefault("jax", str(getattr(jax, "__version__", "")))
        jaxlib_version = safe_version("jaxlib")
        if jaxlib_version:
            versions["jaxlib"] = jaxlib_version
    except Exception:
        pass

    posture = capture_backend_runtime_fingerprint(
        ComputeBackend.JAX,
        method_class=method_class,
        seed=seed,
        extra_versions={k: v for k, v in versions.items() if v},
    )
    reproducibility = ReproducibilityInfo(
        backend=ComputeBackend.JAX,
        determinism_tier=posture.determinism_tier or DeterminismTier.NONDETERMINISTIC,
        seed=seed,
        library_versions={k: v for k, v in versions.items() if v},
        fingerprint=reproducibility_fingerprint,
        observed_tolerance_budget=posture.observed_tolerance_budget,
        note=posture.replay_semantics if posture.available else deterministic_note,
    )
    return MethodResult(
        output=output,
        timing=MethodTiming(
            wall_time_ms=wall_time_ms,
            compile_time_ms=compile_time_ms if compile_time_ms > 0 else None,
        ),
        reproducibility=reproducibility,
        slot_outputs=slot_outputs,
        artifacts={"backend_runtime_fingerprint": posture.as_dict()},
    )


def _compile_fused_pair_kernel(
    method_class_a,
    method_class_b,
    signature_a,
    signature_b,
    b_input_slot: str,
    params_a: Mapping[str, Any],
    params_b: Mapping[str, Any],
) -> _FusedKernelCacheEntry:
    static_a, dynamic_defaults_a, dynamic_names_a = _resolve_dynamic_payload(signature_a, params_a)
    static_b, dynamic_defaults_b, dynamic_names_b = _resolve_dynamic_payload(signature_b, params_b)
    static_a_map = dict(static_a)
    static_b_map = dict(static_b)
    dynamic_names_a_tuple = tuple(dynamic_names_a)
    dynamic_names_b_tuple = tuple(dynamic_names_b)

    try:
        import jax
    except Exception as exc:
        raise MethodContractError(
            signature_a.fqn,
            f"jax is required for fused execution: {exc}",
        ) from exc

    compile_started = _time.perf_counter()

    @jax.jit
    def fused_kernel(
        input_state: Any,
        packed_a: tuple[Any, ...],
        packed_b: tuple[Any, ...],
    ) -> tuple[Any, Any]:
        params_a_internal = dict(static_a_map)
        for index, name in enumerate(dynamic_names_a_tuple):
            params_a_internal[name] = packed_a[index]

        out_a = method_class_a.pure_step(input_state, params_a_internal)
        if isinstance(out_a, Mapping) and b_input_slot in out_a:
            input_for_b = out_a[b_input_slot]
        else:
            input_for_b = out_a

        params_b_internal = dict(static_b_map)
        for index, name in enumerate(dynamic_names_b_tuple):
            params_b_internal[name] = packed_b[index]

        out_b = method_class_b.pure_step(input_for_b, params_b_internal)
        return out_a, out_b

    compile_ms = (_time.perf_counter() - compile_started) * 1000
    return _FusedKernelCacheEntry(
        kernel=fused_kernel,
        static_params_a=static_a_map,
        static_params_b=static_b_map,
        dynamic_names_a=dynamic_names_a_tuple,
        dynamic_names_b=dynamic_names_b_tuple,
        compile_time_ms=compile_ms,
    )


def execute_heterogeneous_chain(
    chain: Any,
    *,
    state: Any,
    params_per_node: Mapping[UUID, Mapping[str, Any]] | None = None,
    seed: int = 0,
    registry: MethodRegistry | None = None,
    dispatcher: MethodDispatcher | None = None,
    fx_rate_provider: FxRateProvider | None = None,
    executor_mode: ExecutorMode = "sequential",
    async_node_timeout_sec: float | None = None,
) -> ChainExecutionResult:
    """Execute heterogeneous chain."""
    if executor_mode == "auto":
        executor_mode = LevelAwareExecutor().choose_mode(chain)

    if executor_mode == "sequential":
        return _execute_sequential_chain(
            chain,
            state=state,
            params_per_node=params_per_node,
            seed=seed,
            registry=registry,
            dispatcher=dispatcher,
            fx_rate_provider=fx_rate_provider,
        )
    if executor_mode == "async":
        return _execute_async_chain(
            chain,
            state=state,
            params_per_node=params_per_node,
            seed=seed,
            registry=registry,
            dispatcher=dispatcher,
            fx_rate_provider=fx_rate_provider,
            async_node_timeout_sec=async_node_timeout_sec,
        )
    if executor_mode == "ray":
        return _execute_ray_chain(
            chain,
            state=state,
            params_per_node=params_per_node,
            seed=seed,
            registry=registry,
        )

    raise ValueError(f"Unknown executor_mode: {executor_mode!r}")


def _execute_sequential_chain(
    chain: Any,
    *,
    state: Any,
    params_per_node: Mapping[UUID, Mapping[str, Any]] | None = None,
    seed: int = 0,
    registry: MethodRegistry | None = None,
    dispatcher: MethodDispatcher | None = None,
    fx_rate_provider: FxRateProvider | None = None,
) -> ChainExecutionResult:
    reg = registry or MethodRegistry.get_instance()
    disp = dispatcher or MethodDispatcher.get_instance()

    node_order = list(chain.execution_order)
    _log.info("chain_start", total_nodes=len(node_order))
    chain_t0 = _time.perf_counter()

    current_state = state
    current_context = state
    prev_backend = None
    node_results: list[tuple[UUID, MethodResult]] = []
    node_slot_outputs: dict[UUID, dict[str, Any]] = {}

    index = 0
    while index < len(node_order):
        node_id = node_order[index]
        next_node_id = node_order[index + 1] if index + 1 < len(node_order) else None

        if next_node_id is not None and _can_fuse_pair(chain, node_id, next_node_id):
            node_a = chain.get_node(node_id)
            node_b = chain.get_node(next_node_id)
            signature_a = chain.get_signature(node_id)
            signature_b = chain.get_signature(next_node_id)
            params_a = _build_node_param_payload(node_a, params_per_node)
            params_b = _build_node_param_payload(node_b, params_per_node)
            b_bindings = chain.get_bindings_for_target(next_node_id)
            b_binding = b_bindings[0] if b_bindings else None

            if prev_backend is not None and prev_backend is not signature_a.backend:
                current_context = _adapt_execution_context(
                    current_context,
                    source_backend=prev_backend,
                    target_backend=signature_a.backend,
                )

            try:
                method_a = reg.get(signature_a.fqn)
                method_b = reg.get(signature_b.fqn)
            except Exception:
                method_a = None
                method_b = None

            fused_supported = (
                method_a is not None
                and method_b is not None
                and b_binding is not None
                and b_binding.source_slot in signature_a.output_slot_names
                and "materialize_input" not in method_a.__dict__
                and "dematerialize_output" not in method_a.__dict__
                and "materialize_input" not in method_b.__dict__
            )

            if fused_supported:
                try:
                    method_a, materialized_state_a, _, prepared_params_a = _collect_node_inputs(
                        chain=chain,
                        node_id=node_id,
                        reg=reg,
                        node_slot_outputs=node_slot_outputs,
                        fx_rate_provider=fx_rate_provider,
                        current_state=current_state,
                        signature=signature_a,
                        current_context=current_context,
                        params_per_node=params_per_node,
                    )
                    static_a, dynamic_defaults_a, dynamic_names_a = _resolve_dynamic_payload(
                        signature_a,
                        prepared_params_a,
                    )
                    static_b, dynamic_defaults_b, dynamic_names_b = _resolve_dynamic_payload(
                        signature_b,
                        params_b,
                    )

                    kernel_key = _make_fused_kernel_key(
                        signature_a=signature_a,
                        signature_b=signature_b,
                        static_params_a=static_a,
                        static_params_b=static_b,
                        dynamic_names_a=dynamic_names_a,
                        dynamic_names_b=dynamic_names_b,
                        b_input_slot=b_binding.source_slot,
                    )
                    kernel_entry, _cache_hit = _FUSED_JIT_CACHE.get_or_build(
                        key=kernel_key,
                        builder=lambda: _compile_fused_pair_kernel(
                            method_a,
                            method_b,
                            signature_a,
                            signature_b,
                            b_binding.source_slot,
                            params_a,
                            params_b,
                        ),
                    )

                    packed_a = _pack_dynamic_values(
                        dynamic_defaults_a,
                        dynamic_names_a,
                        params_a,
                    )
                    packed_b = _pack_dynamic_values(
                        dynamic_defaults_b,
                        dynamic_names_b,
                        params_b,
                    )

                    run_started = _time.perf_counter()
                    out_a, out_b = kernel_entry.kernel(
                        materialized_state_a,
                        packed_a,
                        packed_b,
                    )
                    import jax as _jax

                    out_a = _jax.tree_util.tree_map(
                        lambda x: x.block_until_ready() if hasattr(x, "block_until_ready") else x,
                        out_a,
                    )
                    out_b = _jax.tree_util.tree_map(
                        lambda x: x.block_until_ready() if hasattr(x, "block_until_ready") else x,
                        out_b,
                    )
                    wall_ms = (_time.perf_counter() - run_started) * 1000

                    first_ms = wall_ms * 0.5
                    second_ms = wall_ms - first_ms

                    result_a = _build_fused_result(
                        method_class=method_a,
                        signature=signature_a,
                        output=out_a,
                        wall_time_ms=first_ms,
                        compile_time_ms=kernel_entry.compile_time_ms,
                        params=prepared_params_a,
                        seed=seed,
                        reproducibility_fingerprint=_stable_digest(
                            (
                                "fused-pair-a",
                                signature_a.fqn,
                                signature_b.fqn,
                                _stable_digest(prepared_params_a),
                                seed,
                            )
                        ),
                        deterministic_note=f"fused-with={signature_b.fqn}",
                    )
                    result_b = _build_fused_result(
                        method_class=method_b,
                        signature=signature_b,
                        output=out_b,
                        wall_time_ms=second_ms,
                        compile_time_ms=0.0,
                        params=params_b,
                        seed=seed,
                        reproducibility_fingerprint=_stable_digest(
                            (
                                "fused-pair-b",
                                signature_a.fqn,
                                signature_b.fqn,
                                _stable_digest(params_b),
                                seed,
                            )
                        ),
                        deterministic_note=f"fused-from={signature_a.fqn}",
                    )

                    current_state = out_b
                    current_context = _merge_execution_context(current_context, out_b)
                    prev_backend = signature_b.backend
                    node_results.append((node_id, result_a))
                    node_slot_outputs[node_id] = dict(result_a.slot_outputs)
                    node_results.append((next_node_id, result_b))
                    node_slot_outputs[next_node_id] = dict(result_b.slot_outputs)
                    _log.debug(
                        "chain_node_fused",
                        node_a=signature_a.fqn,
                        node_b=signature_b.fqn,
                        wall_time_ms=round(wall_ms, 2),
                        cache_hit=_cache_hit,
                    )
                    index += 2
                    continue
                except Exception as exc:
                    _log.warning(
                        "chain_pair_fused_fallback",
                        node_a=signature_a.fqn,
                        node_b=signature_b.fqn,
                        error=str(exc),
                    )

        node = chain.get_node(node_id)
        signature = chain.get_signature(node_id)
        method_class = reg.get(signature.fqn)
        if prev_backend is not None and prev_backend is not signature.backend:
            current_context = _adapt_execution_context(
                current_context,
                source_backend=prev_backend,
                target_backend=signature.backend,
            )

        method_class, materialized_state, _signature, combined_params = _collect_node_inputs(
            chain=chain,
            node_id=node_id,
            reg=reg,
            node_slot_outputs=node_slot_outputs,
            fx_rate_provider=fx_rate_provider,
            current_state=current_state,
            signature=signature,
            current_context=current_context,
            params_per_node=params_per_node,
        )

        result = disp.dispatch(
            method_class=method_class,
            signature=_signature,
            state=materialized_state,
            params=combined_params,
            seed=seed,
        )
        current_state = result.output
        current_context = _merge_execution_context(current_context, result.output)
        prev_backend = _signature.backend
        node_results.append((node_id, result))
        node_slot_outputs[node_id] = dict(result.slot_outputs)
        _log.debug(
            "chain_node_complete",
            fqn=_signature.fqn,
            node_index=len(node_results),
            total_nodes=len(node_order),
            wall_time_ms=round(result.timing.wall_time_ms, 2),
        )
        index += 1

    chain_elapsed_ms = (_time.perf_counter() - chain_t0) * 1000
    _log.info(
        "chain_complete",
        total_nodes=len(node_results),
        total_wall_time_ms=round(chain_elapsed_ms, 2),
    )

    return ChainExecutionResult(
        final_state=current_state,
        node_results=tuple(node_results),
        reproducibility_contract=_build_chain_reproducibility_contract(
            node_results,
            composition_kind="serial",
        ),
    )


def _execute_async_chain(
    chain: Any,
    *,
    state: Any,
    params_per_node: Mapping[UUID, Mapping[str, Any]] | None = None,
    seed: int = 0,
    registry: MethodRegistry | None = None,
    dispatcher: MethodDispatcher | None = None,
    fx_rate_provider: FxRateProvider | None = None,
    async_node_timeout_sec: float | None = None,
) -> ChainExecutionResult:
    if AsyncChainExecutor is None:
        raise RuntimeError("AsyncChainExecutor is unavailable in this environment.")
    params_per_node = params_per_node or {}
    reg = registry or MethodRegistry.get_instance()
    disp = dispatcher or MethodDispatcher.get_instance()
    executor = AsyncChainExecutor(registry=reg, dispatcher=disp)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            executor.execute(
                chain,
                initial_state=state,
                params_map=params_per_node,
                fx_rate_provider=fx_rate_provider,
                timeout_per_node=async_node_timeout_sec,
                seed=seed,
            )
        )
    raise RuntimeError(
        "Cannot execute async chain in a running event loop; call "
        "`await execute_heterogeneous_chain_async(...)` instead."
    )


async def execute_heterogeneous_chain_async(
    chain: Any,
    *,
    state: Any,
    params_per_node: Mapping[UUID, Mapping[str, Any]] | None = None,
    seed: int = 0,
    registry: MethodRegistry | None = None,
    dispatcher: MethodDispatcher | None = None,
    fx_rate_provider: FxRateProvider | None = None,
    async_node_timeout_sec: float | None = None,
) -> ChainExecutionResult:
    """Execute heterogeneous chain async."""
    if AsyncChainExecutor is None:
        raise RuntimeError("AsyncChainExecutor is unavailable in this environment.")
    reg = registry or MethodRegistry.get_instance()
    disp = dispatcher or MethodDispatcher.get_instance()
    executor = AsyncChainExecutor(registry=reg, dispatcher=disp)
    return await executor.execute(
        chain,
        initial_state=state,
        params_map=params_per_node,
        fx_rate_provider=fx_rate_provider,
        timeout_per_node=async_node_timeout_sec,
        seed=seed,
    )


def _execute_ray_chain(
    chain: Any,
    *,
    state: Any,
    params_per_node: Mapping[UUID, Mapping[str, Any]] | None = None,
    seed: int = 0,
    registry: MethodRegistry | None = None,
) -> ChainExecutionResult:
    from polisyos.foundry.methods.backends.ray_chain_executor import (
        RayChainExecutor,
    )  # lazy to avoid circular

    del seed
    executor = RayChainExecutor(registry=registry)
    return executor.execute(chain, initial_state=state, params_per_node=params_per_node)


def _adapt_execution_context(
    state: Any,
    *,
    source_backend: ComputeBackend,
    target_backend: ComputeBackend,
) -> Any:
    if isinstance(state, Mapping):
        return state
    return adapt_state(
        state,
        source_backend=source_backend,
        target_backend=target_backend,
    )


def _merge_execution_context(previous_state: Any, output: Any) -> Any:
    if not isinstance(output, Mapping):
        return output

    base_context = _state_context_mapping(previous_state)
    merged = dict(base_context or {})
    merged.update(output)
    return merged


def _state_context_mapping(state: Any) -> dict[str, Any] | None:
    if isinstance(state, Mapping):
        return dict(state)

    aliases = _state_aliases(state)
    if aliases:
        return aliases
    return None


def _state_aliases(state: Any) -> dict[str, Any]:
    if state is None:
        return {}

    class_name = type(state).__name__
    if not class_name:
        return {}

    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower()
    aliases = {snake: state}

    normalized = snake.replace("__", "_")
    if normalized.endswith("panel_data") or "panel_observational_data" in normalized:
        aliases.setdefault("panel_data", state)
    if normalized.endswith("time_series_data"):
        aliases.setdefault("time_series_data", state)
    if normalized.endswith("tabular_data"):
        aliases.setdefault("tabular_data", state)
    if normalized.endswith("survey_micro_data"):
        aliases.setdefault("survey_micro_data", state)
    if normalized.endswith("prediction_result"):
        aliases.setdefault("prediction_result", state)
    if normalized.endswith("graph_causal_data"):
        aliases.setdefault("graph_causal_data", state)

    return aliases


def _apply_binding_adapters(
    value: Any,
    *,
    binding: Any,
    target_backend: ComputeBackend,
    fx_rate_provider: FxRateProvider | None,
    context: Any | None = None,
) -> Any:
    compatibility = binding.compatibility
    if compatibility.requires_fx_rate:
        if fx_rate_provider is None:
            raise MethodContractError(
                binding.target_method,
                (
                    f"binding {binding.source_slot}->{binding.target_slot} requires an "
                    "FX rate adapter, which is not available at execution time"
                ),
            )
        source_symbol = compatibility.unit.source_symbol
        target_symbol = compatibility.unit.target_symbol
        if not source_symbol or not target_symbol:
            raise MethodContractError(
                binding.target_method,
                "FX conversion requested but unit symbols are missing in compatibility plan.",
            )
        try:
            fx_rate = fx_rate_provider.get_rate(
                source_symbol=source_symbol,
                target_symbol=target_symbol,
                context=context,
            )
        except MethodContractError:
            raise
        except Exception as exc:
            raise MethodContractError(
                binding.target_method,
                (f"FX rate lookup failed for {source_symbol}->{target_symbol}: {exc}"),
            ) from exc
        try:
            value = np.asarray(value) * fx_rate
        except Exception as exc:
            raise MethodContractError(
                binding.target_method,
                f"Unable to apply FX rate {fx_rate} to value for "
                f"{binding.source_slot}->{binding.target_slot}: {exc}",
            ) from exc

    factor = compatibility.conversion_factor
    result = value
    if factor not in (None, 1.0):
        try:
            result = result * factor
        except Exception as exc:
            raise MethodContractError(
                binding.target_method,
                (
                    f"failed to apply unit conversion factor {factor!r} for binding "
                    f"{binding.source_slot}->{binding.target_slot}: {exc}"
                ),
            ) from exc

    shape_adapter = compatibility.adapter_plan.shape
    if shape_adapter.kind == ShapeAdapterKind.IDENTITY:
        return result

    array_value = np.asarray(result)
    if shape_adapter.kind == ShapeAdapterKind.BROADCAST_TO:
        target_shape = _runtime_shape(shape_adapter.target_shape, array_value.shape)
        array_value = np.broadcast_to(array_value, target_shape)
    elif shape_adapter.kind == ShapeAdapterKind.EXPAND_DIMS:
        axis = 0 if shape_adapter.axis is None else int(shape_adapter.axis)
        array_value = np.expand_dims(array_value, axis=axis)
    elif shape_adapter.kind == ShapeAdapterKind.UNSAFE_RESHAPE:
        target_shape = _runtime_shape(shape_adapter.target_shape, array_value.shape)
        array_value = np.reshape(array_value, target_shape)

    if target_backend is ComputeBackend.JAX:
        return adapt_state(
            array_value,
            source_backend=ComputeBackend.NUMPY,
            target_backend=target_backend,
        )
    return array_value


def _runtime_shape(
    target_shape: tuple[int | str, ...] | None,
    current_shape: tuple[int, ...],
) -> tuple[int, ...]:
    if target_shape is None:
        return current_shape
    if len(target_shape) != len(current_shape):
        return tuple(dim for dim in current_shape)
    resolved: list[int] = []
    for idx, dim in enumerate(target_shape):
        if isinstance(dim, int):
            resolved.append(dim)
        else:
            resolved.append(int(current_shape[idx]))
    return tuple(resolved)
