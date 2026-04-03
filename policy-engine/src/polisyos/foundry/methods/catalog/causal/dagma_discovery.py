"""Estimate smooth DAGMA graph structures with optional backend fallbacks."""
from __future__ import annotations

import importlib
import inspect
import multiprocessing as mp
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog.causal.protocols import TabularCausalDiscoveryData
from polisyos.ir.analytics.causal_discovery import CausalDiscoveryReport
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeSource, GraphType


@dataclass(frozen=True)
class _DAGMAExecutionResult:
    weights: np.ndarray | None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    timed_out: bool = False


def _clamp_probability(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def _edge_key(edge: CausalEdge) -> str:
    return f"{edge.src}->{edge.dst}"


def _bootstrap_resample(*, data: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    if data.shape[0] == 0:
        return data
    indices = rng.integers(0, data.shape[0], size=data.shape[0])
    return data[indices]


def _resolve_estimator_class() -> type[Any]:
    linear_module: Any
    try:
        linear_module = importlib.import_module("dagma.linear")
    except ModuleNotFoundError:
        linear_module = importlib.import_module("dagma")

    for name in ("DagmaLinear", "DAGMALinear", "DAGMA", "Dagma"):
        candidate = getattr(linear_module, name, None)
        if isinstance(candidate, type):
            return candidate
    raise RuntimeError("DAGMA estimator class not found (expected DagmaLinear-like class)")


def _extract_weight_matrix(result: Any, model: Any | None = None) -> np.ndarray:
    if isinstance(result, np.ndarray):
        return np.asarray(result, dtype=float)
    if isinstance(result, Mapping):
        for key in ("W", "W_est", "w_est", "weight_matrix", "adjacency"):
            candidate = result.get(key)
            if candidate is not None:
                return np.asarray(candidate, dtype=float)
    if model is not None:
        for attr in ("W_est", "w_est", "weight_matrix_", "adjacency_"):
            candidate = getattr(model, attr, None)
            if candidate is not None:
                return np.asarray(candidate, dtype=float)
    raise RuntimeError("DAGMA did not return a weight matrix")


def _fit_dagma_weights(
    *,
    data: np.ndarray,
    lambda1: float,
    weight_threshold: float,
    max_iter: int,
    warm_iter: int,
    seed: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    dagma_module = importlib.import_module("dagma")
    estimator_cls = _resolve_estimator_class()
    init_kwargs: dict[str, Any] = {}
    init_sig = inspect.signature(estimator_cls.__init__)
    if "loss_type" in init_sig.parameters:
        init_kwargs["loss_type"] = "l2"
    if "verbose" in init_sig.parameters:
        init_kwargs["verbose"] = False
    if "seed" in init_sig.parameters:
        init_kwargs["seed"] = int(seed)
    model = estimator_cls(**init_kwargs)

    fit = getattr(model, "fit", None)
    if not callable(fit):
        raise RuntimeError("DAGMA estimator has no callable fit()")

    fit_kwargs: dict[str, Any] = {}
    fit_sig = inspect.signature(fit)
    if "lambda1" in fit_sig.parameters:
        fit_kwargs["lambda1"] = float(lambda1)
    elif "lambda_1" in fit_sig.parameters:
        fit_kwargs["lambda_1"] = float(lambda1)
    if "w_threshold" in fit_sig.parameters:
        fit_kwargs["w_threshold"] = float(weight_threshold)
    if "max_iter" in fit_sig.parameters:
        fit_kwargs["max_iter"] = int(max_iter)
    if "warm_iter" in fit_sig.parameters:
        fit_kwargs["warm_iter"] = int(warm_iter)
    if "seed" in fit_sig.parameters:
        fit_kwargs["seed"] = int(seed)

    raw_result = fit(np.asarray(data, dtype=float), **fit_kwargs)
    weights = _extract_weight_matrix(raw_result, model=model)
    meta = {
        "optimizer": f"{estimator_cls.__module__}.{estimator_cls.__name__}",
        "dagma_version": getattr(dagma_module, "__version__", None),
        "converged": bool(getattr(model, "converged", True)),
        "num_steps": getattr(model, "num_steps", None),
        "fit_kwargs": fit_kwargs,
    }
    return weights, meta


def _dagma_worker(
    queue: Any,
    data: np.ndarray,
    lambda1: float,
    weight_threshold: float,
    max_iter: int,
    warm_iter: int,
    seed: int,
) -> None:
    started = time.perf_counter()
    try:
        np.random.seed(seed)
        weights, metadata = _fit_dagma_weights(
            data=np.asarray(data, dtype=float),
            lambda1=lambda1,
            weight_threshold=weight_threshold,
            max_iter=max_iter,
            warm_iter=warm_iter,
            seed=seed,
        )
        queue.put(
            {
                "ok": True,
                "weights": weights.tolist(),
                "metadata": metadata,
                "runtime_seconds": float(time.perf_counter() - started),
            }
        )
    except Exception as exc:  # pragma: no cover - exercised through parent behavior
        queue.put(
            {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "runtime_seconds": float(time.perf_counter() - started),
            }
        )


def _run_dagma_with_timeout(
    *,
    data: np.ndarray,
    lambda1: float,
    weight_threshold: float,
    max_iter: int,
    warm_iter: int,
    timeout_seconds: float,
    seed: int,
) -> _DAGMAExecutionResult:
    if timeout_seconds <= 0.0:
        return _DAGMAExecutionResult(
            weights=None,
            metadata={},
            error="DAGMA timeout budget exhausted",
            timed_out=True,
        )

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    process = ctx.Process(
        target=_dagma_worker,
        args=(
            queue,
            np.asarray(data, dtype=float),
            float(lambda1),
            float(weight_threshold),
            int(max_iter),
            int(warm_iter),
            int(seed),
        ),
    )
    process.start()
    process.join(timeout=timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(timeout=1.0)
        return _DAGMAExecutionResult(
            weights=None,
            metadata={},
            error=f"DAGMA timeout after {timeout_seconds:.2f}s",
            timed_out=True,
        )

    payload: dict[str, Any] | None = None
    if not queue.empty():
        payload = queue.get_nowait()

    if payload is None:
        if process.exitcode == 0:
            return _DAGMAExecutionResult(
                weights=None,
                metadata={},
                error="DAGMA worker exited without payload",
                timed_out=False,
            )
        return _DAGMAExecutionResult(
            weights=None,
            metadata={},
            error=f"DAGMA worker exited with code {process.exitcode}",
            timed_out=False,
        )

    if not bool(payload.get("ok", False)):
        return _DAGMAExecutionResult(
            weights=None,
            metadata={},
            error=str(payload.get("error", "DAGMA failed")),
            timed_out=False,
        )

    raw_weights = payload.get("weights")
    if raw_weights is None:
        return _DAGMAExecutionResult(
            weights=None,
            metadata={},
            error="DAGMA worker returned no weights",
            timed_out=False,
        )

    metadata_raw = payload.get("metadata")
    metadata = dict(metadata_raw) if isinstance(metadata_raw, Mapping) else {}
    return _DAGMAExecutionResult(
        weights=np.asarray(raw_weights, dtype=float),
        metadata=metadata,
        error=None,
        timed_out=False,
    )


def _weights_to_graph(
    *,
    weights: np.ndarray,
    variable_names: list[str],
    weight_threshold: float,
) -> CausalGraphModel:
    n_variables = len(variable_names)
    if weights.ndim != 2 or weights.shape != (n_variables, n_variables):
        raise ValueError(
            "DAGMA weight matrix dimensions do not match variable names: "
            f"weights={weights.shape}, variables={n_variables}"
        )

    max_abs = float(np.max(np.abs(weights))) if weights.size > 0 else 0.0
    normalizer = max(max_abs, float(weight_threshold), 1e-12)
    edges: list[CausalEdge] = []
    for src_idx, src_name in enumerate(variable_names):
        for dst_idx, dst_name in enumerate(variable_names):
            if src_idx == dst_idx:
                continue
            weight = float(weights[src_idx, dst_idx])
            if abs(weight) < weight_threshold:
                continue
            confidence = _clamp_probability(abs(weight) / normalizer)
            edge = CausalEdge(
                src=src_name,
                dst=dst_name,
                sources=[EdgeSource.DATA],
                data_confidence=confidence,
                metadata={"weight": weight},
            )
            edges.append(
                edge.model_copy(
                    update={"combined_confidence": edge.compute_combined_confidence()},
                )
            )

    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=list(variable_names),
        edges=edges,
        discovery_method="dagma",
    )


def _fallback_report(
    *,
    state: TabularCausalDiscoveryData,
    significance_level: float,
    warnings: list[str],
    elapsed_seconds: float,
    params: Mapping[str, Any],
) -> CausalDiscoveryReport:
    return CausalDiscoveryReport(
        method="dagma",
        graph=CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=list(state.variable_names),
            edges=[],
            discovery_method="dagma",
        ),
        bootstrap_stability={},
        n_bootstrap=0,
        significance_level=significance_level,
        computation_time_seconds=elapsed_seconds,
        warnings=warnings,
        metadata={
            "fallback": True,
            "timeout_seconds": float(params.get("timeout_seconds", 600.0) or 600.0),
            "weight_threshold": float(params.get("weight_threshold", 0.05) or 0.05),
            "lambda1": float(params.get("lambda1", 0.02) or 0.02),
        },
    )


def run_dagma_discovery(
    *,
    state: TabularCausalDiscoveryData | Mapping[str, Any],
    params: Mapping[str, Any],
) -> dict[str, Any]:
    """Run dagma discovery."""
    from polisyos.foundry.methods.catalog.causal.constraint_discovery import (
        _stamp_algebraic_constraint_audit,
        _validate_algebraic_blocks,
    )

    tab_data = (
        state
        if isinstance(state, TabularCausalDiscoveryData)
        else TabularCausalDiscoveryData.model_validate(state)
    )
    significance_level = _clamp_probability(float(params.get("significance_level", 0.05)))
    n_bootstrap_requested = max(0, int(params.get("n_bootstrap", 0) or 0))
    timeout_seconds = max(1.0, float(params.get("timeout_seconds", 600.0) or 600.0))
    weight_threshold = max(0.0, float(params.get("weight_threshold", 0.05) or 0.05))
    lambda1 = max(0.0, float(params.get("lambda1", 0.02) or 0.02))
    max_iter = max(1, int(params.get("max_iter", 20_000) or 20_000))
    warm_iter = max(1, int(params.get("warm_iter", 1_000) or 1_000))
    seed = int(params.get("__seed__", 0) or 0)
    algebraic_blocks = _validate_algebraic_blocks(params.get("algebraic_blocks"))

    started = time.perf_counter()
    warnings: list[str] = []
    deadline = started + timeout_seconds

    base_result = _run_dagma_with_timeout(
        data=tab_data.data,
        lambda1=lambda1,
        weight_threshold=weight_threshold,
        max_iter=max_iter,
        warm_iter=warm_iter,
        timeout_seconds=max(0.0, deadline - time.perf_counter()),
        seed=seed,
    )
    if base_result.error is not None or base_result.weights is None:
        if base_result.error is not None:
            warnings.append(base_result.error)
        report = _fallback_report(
            state=tab_data,
            significance_level=significance_level,
            warnings=warnings,
            elapsed_seconds=float(time.perf_counter() - started),
            params=params,
        )
        report = _stamp_algebraic_constraint_audit(
            report,
            data=tab_data.data,
            variable_names=tab_data.variable_names,
            significance_level=significance_level,
            seed=seed,
            algebraic_blocks=algebraic_blocks,
        )
        return {"report": report, "__determinism_tier__": DeterminismTier.STATISTICAL}

    try:
        graph = _weights_to_graph(
            weights=base_result.weights,
            variable_names=tab_data.variable_names,
            weight_threshold=weight_threshold,
        )
    except Exception as exc:
        warnings.append(f"DAGMA graph conversion failed: {exc}")
        report = _fallback_report(
            state=tab_data,
            significance_level=significance_level,
            warnings=warnings,
            elapsed_seconds=float(time.perf_counter() - started),
            params=params,
        )
        report = _stamp_algebraic_constraint_audit(
            report,
            data=tab_data.data,
            variable_names=tab_data.variable_names,
            significance_level=significance_level,
            seed=seed,
            algebraic_blocks=algebraic_blocks,
        )
        return {"report": report, "__determinism_tier__": DeterminismTier.STATISTICAL}

    bootstrap_stability: dict[str, float] = {}
    completed_bootstrap = 0
    base_edge_keys = [_edge_key(edge) for edge in graph.edges]
    if n_bootstrap_requested > 0 and base_edge_keys:
        hit_counts = {key: 0 for key in base_edge_keys}
        rng = np.random.default_rng(seed + 101)
        for idx in range(n_bootstrap_requested):
            remaining = max(0.0, deadline - time.perf_counter())
            if remaining <= 0.0:
                warnings.append(
                    "bootstrap_truncated: timeout budget exhausted before all runs completed"
                )
                break
            sampled = _bootstrap_resample(data=tab_data.data, rng=rng)
            boot_result = _run_dagma_with_timeout(
                data=sampled,
                lambda1=lambda1,
                weight_threshold=weight_threshold,
                max_iter=max_iter,
                warm_iter=warm_iter,
                timeout_seconds=remaining,
                seed=seed + idx + 1,
            )
            if boot_result.error is not None or boot_result.weights is None:
                if boot_result.error is not None:
                    warnings.append(f"bootstrap_run_{idx}: {boot_result.error}")
                if boot_result.timed_out:
                    warnings.append("bootstrap_truncated: timeout during bootstrap")
                    break
                continue
            try:
                boot_graph = _weights_to_graph(
                    weights=boot_result.weights,
                    variable_names=tab_data.variable_names,
                    weight_threshold=weight_threshold,
                )
            except Exception as exc:
                warnings.append(f"bootstrap_run_{idx}: graph conversion failed: {exc}")
                continue
            completed_bootstrap += 1
            boot_keys = {_edge_key(edge) for edge in boot_graph.edges}
            for key in hit_counts:
                if key in boot_keys:
                    hit_counts[key] += 1
        if completed_bootstrap > 0:
            bootstrap_stability = {
                key: float(hit_counts[key] / completed_bootstrap) for key in base_edge_keys
            }
        else:
            bootstrap_stability = {key: 0.0 for key in base_edge_keys}

    report = CausalDiscoveryReport(
        method="dagma",
        graph=graph,
        bootstrap_stability=bootstrap_stability,
        n_bootstrap=completed_bootstrap,
        significance_level=significance_level,
        computation_time_seconds=float(time.perf_counter() - started),
        warnings=warnings,
        metadata={
            **dict(base_result.metadata),
            "requested_n_bootstrap": n_bootstrap_requested,
            "timeout_seconds": timeout_seconds,
            "weight_threshold": weight_threshold,
            "lambda1": lambda1,
            "max_iter": max_iter,
            "warm_iter": warm_iter,
        },
    )
    report = _stamp_algebraic_constraint_audit(
        report,
        data=tab_data.data,
        variable_names=tab_data.variable_names,
        significance_level=significance_level,
        seed=seed,
        algebraic_blocks=algebraic_blocks,
    )
    return {"report": report, "__determinism_tier__": DeterminismTier.STATISTICAL}


@foundry_method(
    namespace="causal.discovery",
    version="1.0.0",
    tags={"causal", "discovery", "dagma", "scale"},
)
class DAGMADiscovery:
    """Learn a weighted acyclic graph with DAGMA optimization; avoid when cycles are substantively required."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="dagma_discovery",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="tabular_discovery_data",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("observations", "rows"),
                    shape=("n_obs", "n_vars"),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="causal_discovery_report",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("report", "json"),
                )
            }
        ),
        parameters=(
            ParameterSpec(name="significance_level", default=0.05),
            ParameterSpec(name="weight_threshold", default=0.05),
            ParameterSpec(name="lambda1", default=0.02),
            ParameterSpec(name="max_iter", default=20000),
            ParameterSpec(name="warm_iter", default=1000),
            ParameterSpec(name="algebraic_blocks", default=None),
            ParameterSpec(name="n_bootstrap", default=0),
            ParameterSpec(name="timeout_seconds", default=600),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "DAGMA continuous optimization causal discovery for high-dimensional tabular data."
        ),
        tags=frozenset({"causal", "discovery", "dagma", "scale"}),
        citations=(
            "Bello, K. et al. (2022). DAGMA: Learning DAGs via M-matrices and a log-det acyclicity.",
        ),
        when_to_use="Continuous differentiable DAG structure learning; faster than combinatorial search for dense graphs",
        when_not_to_use="Very small samples; known domain graph priors should dominate data; cycles expected in data-generating process",
        typical_min_obs=500,
        output_interpretation="Weighted adjacency matrix of learned DAG. Threshold to get graph skeleton. Compare to prior knowledge.",
    )

    @staticmethod
    def pure_step(state: TabularCausalDiscoveryData, params: Mapping[str, Any]) -> dict[str, Any]:
        return run_dagma_discovery(state=state, params=params)


__all__ = [
    "DAGMADiscovery",
    "run_dagma_discovery",
]
