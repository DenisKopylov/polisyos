"""Discover lagged causal parents in multivariate time series with PCMCI-style tests."""
from __future__ import annotations

import multiprocessing as mp
import time
from dataclasses import dataclass
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
from polisyos.foundry.methods.catalog.causal.ci_backends import (
    CIBackendSelection,
    ci_backend_metadata,
    partial_corr,
    resolve_discovery_ci_backend,
)
from polisyos.foundry.methods.catalog.causal.protocols import TimeSeriesCausalData
from polisyos.ir.analytics.causal_discovery import CausalDiscoveryReport
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeSource, GraphType

_VALID_COND_IND_TESTS = frozenset({"par_corr", "gpdc", "cmi"})


@dataclass(frozen=True)
class _PCMCIExecutionResult:
    edges: list[CausalEdge]
    error: str | None
    timed_out: bool


def _resolve_pcmci_ci_backend(raw: Any, *, cond_ind_test: str) -> CIBackendSelection:
    base = resolve_discovery_ci_backend(raw)
    if base.used != "jax":
        return base
    # Keep auto conservative for backward compatibility and deterministic baselines.
    if base.requested == "auto":
        return CIBackendSelection(
            requested=base.requested,
            used="numpy",
            fallback_reason="auto_defaults_numpy_for_stability",
        )
    reason = ""
    if cond_ind_test != "par_corr":
        reason = f"jax_backend_only_par_corr_supported:{cond_ind_test}"
        if base.fallback_reason:
            reason = f"{base.fallback_reason};{reason}"
        return CIBackendSelection(
            requested=base.requested,
            used="numpy",
            fallback_reason=reason,
        )
    if base.fallback_reason:
        reason = f"{base.fallback_reason};{reason}"
    return CIBackendSelection(requested=base.requested, used="jax", fallback_reason=reason or None)


def _clamp_probability(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def _is_directed_to_target(mark: str) -> bool:
    normalized = mark.strip()
    if len(normalized) < 3:
        return False
    return normalized[0] in {"-", "o"} and normalized[-1] == ">"


def _edge_key(edge: CausalEdge) -> str:
    return f"{edge.src}->{edge.dst}@lag={edge.lag}"


def _build_cond_ind_test(name: str) -> Any:
    normalized = name.strip().lower()
    if normalized == "par_corr":
        from tigramite.independence_tests.parcorr import ParCorr

        return ParCorr(significance="analytic")
    if normalized == "gpdc":
        from tigramite.independence_tests.gpdc import GPDC

        return GPDC(significance="analytic")
    if normalized == "cmi":
        from tigramite.independence_tests.cmiknn import CMIknn

        return CMIknn(significance="shuffle_test")
    raise ValueError(
        f"Unsupported cond_ind_test={name!r}; expected one of {sorted(_VALID_COND_IND_TESTS)}"
    )


def _extract_edges_payload(
    *,
    graph: np.ndarray,
    p_matrix: np.ndarray | None,
    variable_names: list[str],
    tau_max: int,
) -> list[dict[str, Any]]:
    if graph.ndim != 3:
        raise ValueError(f"PCMCI graph must be 3D, got shape={graph.shape}")

    n_variables = len(variable_names)
    if graph.shape[0] != n_variables or graph.shape[1] != n_variables:
        raise ValueError(
            "PCMCI graph dimensions do not match variable names: "
            f"graph={graph.shape}, variables={n_variables}"
        )

    max_lag_in_graph = graph.shape[2] - 1
    max_lag = min(int(tau_max), max_lag_in_graph)

    edges: list[dict[str, Any]] = []
    for lag in range(1, max_lag + 1):
        for src_idx, src_name in enumerate(variable_names):
            for dst_idx, dst_name in enumerate(variable_names):
                if src_idx == dst_idx:
                    continue
                raw_mark = graph[src_idx, dst_idx, lag]
                mark = raw_mark.decode("utf-8") if isinstance(raw_mark, bytes) else str(raw_mark)
                if not _is_directed_to_target(mark):
                    continue

                p_value: float | None = None
                if p_matrix is not None:
                    try:
                        p_candidate = float(p_matrix[src_idx, dst_idx, lag])
                    except (TypeError, ValueError):
                        p_candidate = float("nan")
                    if np.isfinite(p_candidate):
                        p_value = _clamp_probability(p_candidate)

                data_confidence = None if p_value is None else _clamp_probability(1.0 - p_value)
                edges.append(
                    {
                        "src": src_name,
                        "dst": dst_name,
                        "lag": int(lag),
                        "p_value": p_value,
                        "data_confidence": data_confidence,
                    }
                )
    return edges


def _pcmci_worker(
    queue: Any,
    data: np.ndarray,
    variable_names: list[str],
    max_lag: int,
    significance_level: float,
    cond_ind_test: str,
    seed: int,
) -> None:
    started = time.perf_counter()
    try:
        np.random.seed(seed)

        from tigramite.data_processing import DataFrame
        from tigramite.pcmci import PCMCI

        dataframe = DataFrame(np.asarray(data, dtype=float), var_names=variable_names)
        pcmci = PCMCI(
            dataframe=dataframe,
            cond_ind_test=_build_cond_ind_test(cond_ind_test),
            verbosity=0,
        )
        result = pcmci.run_pcmciplus(
            tau_min=1,
            tau_max=max_lag,
            pc_alpha=significance_level,
        )

        graph = result.get("graph")
        p_matrix = result.get("p_matrix")
        if graph is None and p_matrix is not None:
            graph = pcmci.get_graph_from_pmatrix(
                p_matrix=p_matrix,
                alpha_level=significance_level,
                tau_min=1,
                tau_max=max_lag,
            )
        if graph is None:
            raise ValueError("PCMCI returned no graph output")

        edges = _extract_edges_payload(
            graph=np.asarray(graph),
            p_matrix=None if p_matrix is None else np.asarray(p_matrix),
            variable_names=variable_names,
            tau_max=max_lag,
        )
        queue.put(
            {
                "ok": True,
                "edges": edges,
                "runtime_seconds": float(time.perf_counter() - started),
            }
        )
    except Exception as exc:  # pragma: no cover - exercised via parent process behavior
        queue.put(
            {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "runtime_seconds": float(time.perf_counter() - started),
            }
        )


def _run_pcmci_with_timeout(
    *,
    data: np.ndarray,
    variable_names: list[str],
    max_lag: int,
    significance_level: float,
    cond_ind_test: str,
    timeout_seconds: float,
    seed: int,
) -> _PCMCIExecutionResult:
    if timeout_seconds <= 0.0:
        return _PCMCIExecutionResult(
            edges=[],
            error="PCMCI timeout budget exhausted",
            timed_out=True,
        )

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    process = ctx.Process(
        target=_pcmci_worker,
        args=(
            queue,
            np.asarray(data, dtype=float),
            list(variable_names),
            int(max_lag),
            float(significance_level),
            str(cond_ind_test),
            int(seed),
        ),
    )

    process.start()
    process.join(timeout=timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(timeout=1.0)
        return _PCMCIExecutionResult(
            edges=[],
            error=f"PCMCI timeout after {timeout_seconds:.2f}s",
            timed_out=True,
        )

    payload: dict[str, Any] | None = None
    if not queue.empty():
        payload = queue.get_nowait()

    if payload is None:
        if process.exitcode == 0:
            return _PCMCIExecutionResult(
                edges=[],
                error="PCMCI worker exited without payload",
                timed_out=False,
            )
        return _PCMCIExecutionResult(
            edges=[],
            error=f"PCMCI worker exited with code {process.exitcode}",
            timed_out=False,
        )

    if not bool(payload.get("ok", False)):
        return _PCMCIExecutionResult(
            edges=[],
            error=str(payload.get("error", "PCMCI failed")),
            timed_out=False,
        )

    edges: list[CausalEdge] = []
    for raw in payload.get("edges", []):
        edge = CausalEdge(
            src=str(raw["src"]),
            dst=str(raw["dst"]),
            lag=int(raw["lag"]),
            p_value=raw.get("p_value"),
            data_confidence=raw.get("data_confidence"),
            sources=[EdgeSource.DATA],
        )
        edges.append(
            edge.model_copy(
                update={"combined_confidence": edge.compute_combined_confidence()},
            )
        )
    return _PCMCIExecutionResult(edges=edges, error=None, timed_out=False)


def _run_pcmci_jax_surrogate(
    *,
    data: np.ndarray,
    variable_names: list[str],
    max_lag: int,
    significance_level: float,
) -> _PCMCIExecutionResult:
    """Fallback-free JAX CI runtime path for `discovery_ci_backend=jax`.

    This deterministic surrogate estimates lagged dependencies using partial
    correlations computed by the JAX backend from `ci_backends.py`.
    """
    rows = int(data.shape[0])
    cols = int(data.shape[1]) if data.ndim == 2 else 0
    if cols != len(variable_names):
        return _PCMCIExecutionResult(
            edges=[],
            error=(
                "PCMCI JAX surrogate shape mismatch: "
                f"data_cols={cols}, variables={len(variable_names)}"
            ),
            timed_out=False,
        )
    if rows <= max_lag + 2:
        return _PCMCIExecutionResult(
            edges=[],
            error=(
                "PCMCI JAX surrogate requires more timesteps: "
                f"rows={rows}, max_lag={max_lag}"
            ),
            timed_out=False,
        )

    arr = np.asarray(data, dtype=float)
    edges: list[CausalEdge] = []
    threshold = max(0.01, float(significance_level))
    for lag in range(1, max_lag + 1):
        x_block = arr[:-lag, :]
        y_block = arr[lag:, :]
        for src_idx, src_name in enumerate(variable_names):
            x = x_block[:, src_idx]
            for dst_idx, dst_name in enumerate(variable_names):
                if src_idx == dst_idx:
                    continue
                y = y_block[:, dst_idx]
                cond_parts: list[np.ndarray] = []
                others = [idx for idx in range(cols) if idx not in {src_idx, dst_idx}]
                if others:
                    cond_parts.append(x_block[:, others])
                    cond_parts.append(y_block[:, others])
                cond = None
                if cond_parts:
                    cond = np.column_stack(cond_parts)
                corr = float(partial_corr(x, y, cond, backend="jax"))
                strength = float(abs(corr))
                if strength < threshold:
                    continue
                p_value = _clamp_probability(1.0 - strength)
                edge = CausalEdge(
                    src=src_name,
                    dst=dst_name,
                    lag=int(lag),
                    p_value=p_value,
                    data_confidence=_clamp_probability(strength),
                    sources=[EdgeSource.DATA],
                )
                edges.append(
                    edge.model_copy(
                        update={"combined_confidence": edge.compute_combined_confidence()},
                    )
                )
    return _PCMCIExecutionResult(edges=edges, error=None, timed_out=False)


def _block_bootstrap_resample(
    *,
    data: np.ndarray,
    block_length: int,
    rng: np.random.Generator,
) -> np.ndarray:
    n_timesteps = data.shape[0]
    if n_timesteps == 0:
        return data

    block = max(1, int(block_length))
    if block == 1:
        indices = rng.integers(0, n_timesteps, size=n_timesteps)
        return data[indices]

    max_start = max(1, n_timesteps - block + 1)
    n_blocks = int(np.ceil(n_timesteps / block))
    starts = rng.integers(0, max_start, size=n_blocks)
    sampled = np.vstack([data[start : start + block] for start in starts])
    return sampled[:n_timesteps]


def _fallback_report(
    *,
    state: TimeSeriesCausalData,
    significance_level: float,
    warnings: list[str],
    elapsed_seconds: float,
    cond_ind_test: str,
    max_lag: int,
    timeout_seconds: float,
    n_bootstrap: int,
    ci_backend: CIBackendSelection,
) -> CausalDiscoveryReport:
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=list(state.variable_names),
        edges=[],
        discovery_method="pcmci+",
    )
    return CausalDiscoveryReport(
        method="pcmci+",
        graph=graph,
        bootstrap_stability={},
        n_bootstrap=0,
        significance_level=significance_level,
        computation_time_seconds=elapsed_seconds,
        warnings=warnings,
        metadata={
            "fallback": True,
            "cond_ind_test": cond_ind_test,
            "max_lag": max_lag,
            "requested_n_bootstrap": n_bootstrap,
            "timeout_seconds": timeout_seconds,
            **ci_backend_metadata(ci_backend),
        },
    )


@foundry_method(
    namespace="causal.discovery",
    version="1.0.0",
    tags={"causal", "discovery", "time-series", "pcmci"},
)
class PCMCIDiscovery:
    """Estimate lagged links under a fixed lag window and causal sufficiency; avoid very short time series."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="pcmci_discovery",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="timeseries_data",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("observations", "timesteps"),
                    shape=("n_obs", "n_series"),
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
            ParameterSpec(name="max_lag", default=5),
            ParameterSpec(name="significance_level", default=0.05),
            ParameterSpec(name="cond_ind_test", default="par_corr"),
            ParameterSpec(name="discovery_ci_backend", default="auto"),
            ParameterSpec(name="n_bootstrap", default=100),
            ParameterSpec(name="timeout_seconds", default=600),
            ParameterSpec(name="block_length", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="PCMCI+ causal discovery for multivariate time-series via Tigramite.",
        tags=frozenset({"causal", "discovery", "time-series", "pcmci"}),
        citations=(
            "Runge, J. et al. (2019). Detecting and quantifying causal associations in large "
            "nonlinear time series datasets.",
        ),
        assumptions={
            "stationarity": "Time-series is sufficiently stationary over the analysis window.",
            "causal_sufficiency": "No severe hidden confounding beyond algorithm tolerance.",
        },
        when_to_use="Causal discovery in multivariate time series; detect lagged causal links with false discovery control",
        when_not_to_use="Cross-sectional data; fewer than 100 time steps; no time-series structure",
        typical_min_obs=200,
        output_interpretation="Causal graph of lagged links with p-values and effect sizes. MCI link = conditional independence of Xt given parents.",
    )

    @staticmethod
    def pure_step(state: TimeSeriesCausalData, params: Mapping[str, Any]) -> dict[str, Any]:
        if isinstance(state, TimeSeriesCausalData):
            ts_data = state
        else:
            ts_data = TimeSeriesCausalData.model_validate(state)

        max_lag = max(1, int(params.get("max_lag", 5)))
        significance_level = _clamp_probability(float(params.get("significance_level", 0.05)))
        cond_ind_test = str(params.get("cond_ind_test", "par_corr")).strip().lower()
        ci_backend = _resolve_pcmci_ci_backend(
            params.get("discovery_ci_backend"),
            cond_ind_test=cond_ind_test,
        )
        n_bootstrap_requested = max(0, int(params.get("n_bootstrap", 100)))
        timeout_seconds = max(1.0, float(params.get("timeout_seconds", 600.0)))
        default_block_length = max(max_lag + 1, 5)
        block_length_raw = params.get("block_length")
        block_length = default_block_length if block_length_raw is None else int(block_length_raw)
        block_length = max(1, block_length)
        seed = int(params.get("__seed__", 0) or 0)

        started = time.perf_counter()
        warnings: list[str] = []

        if cond_ind_test not in _VALID_COND_IND_TESTS:
            warnings.append(
                "Unsupported cond_ind_test "
                f"{cond_ind_test!r}; expected one of {sorted(_VALID_COND_IND_TESTS)}"
            )
            report = _fallback_report(
                state=ts_data,
                significance_level=significance_level,
                warnings=warnings,
                elapsed_seconds=float(time.perf_counter() - started),
                cond_ind_test=cond_ind_test,
                max_lag=max_lag,
                timeout_seconds=timeout_seconds,
                n_bootstrap=n_bootstrap_requested,
                ci_backend=ci_backend,
            )
            return {"report": report, "__determinism_tier__": DeterminismTier.STATISTICAL}

        deadline = started + timeout_seconds
        remaining = max(0.0, deadline - time.perf_counter())
        if ci_backend.used == "jax":
            base_result = _run_pcmci_jax_surrogate(
                data=ts_data.data,
                variable_names=ts_data.variable_names,
                max_lag=max_lag,
                significance_level=significance_level,
            )
        else:
            base_result = _run_pcmci_with_timeout(
                data=ts_data.data,
                variable_names=ts_data.variable_names,
                max_lag=max_lag,
                significance_level=significance_level,
                cond_ind_test=cond_ind_test,
                timeout_seconds=remaining,
                seed=seed,
            )

        if base_result.error is not None:
            warnings.append(base_result.error)
            report = _fallback_report(
                state=ts_data,
                significance_level=significance_level,
                warnings=warnings,
                elapsed_seconds=float(time.perf_counter() - started),
                cond_ind_test=cond_ind_test,
                max_lag=max_lag,
                timeout_seconds=timeout_seconds,
                n_bootstrap=n_bootstrap_requested,
                ci_backend=ci_backend,
            )
            return {"report": report, "__determinism_tier__": DeterminismTier.STATISTICAL}

        graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=list(ts_data.variable_names),
            edges=base_result.edges,
            discovery_method="pcmci+",
        )

        bootstrap_stability: dict[str, float] = {}
        completed_bootstrap = 0

        base_edge_keys = [_edge_key(edge) for edge in graph.edges]
        if n_bootstrap_requested > 0 and base_edge_keys:
            hit_counts = {key: 0 for key in base_edge_keys}
            bootstrap_rng = np.random.default_rng(seed + 17)

            for idx in range(n_bootstrap_requested):
                remaining = max(0.0, deadline - time.perf_counter())
                if remaining <= 0.0:
                    warnings.append(
                        "bootstrap_truncated: timeout budget exhausted before all runs completed"
                    )
                    break

                sampled = _block_bootstrap_resample(
                    data=ts_data.data,
                    block_length=block_length,
                    rng=bootstrap_rng,
                )
                if ci_backend.used == "jax":
                    boot_result = _run_pcmci_jax_surrogate(
                        data=sampled,
                        variable_names=ts_data.variable_names,
                        max_lag=max_lag,
                        significance_level=significance_level,
                    )
                else:
                    boot_result = _run_pcmci_with_timeout(
                        data=sampled,
                        variable_names=ts_data.variable_names,
                        max_lag=max_lag,
                        significance_level=significance_level,
                        cond_ind_test=cond_ind_test,
                        timeout_seconds=remaining,
                        seed=seed + idx + 1,
                    )
                if boot_result.error is not None:
                    warnings.append(f"bootstrap_run_{idx}: {boot_result.error}")
                    if boot_result.timed_out:
                        warnings.append("bootstrap_truncated: timeout during bootstrap")
                        break
                    continue

                completed_bootstrap += 1
                boot_keys = {_edge_key(edge) for edge in boot_result.edges}
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
            method="pcmci+",
            graph=graph,
            bootstrap_stability=bootstrap_stability,
            n_bootstrap=completed_bootstrap,
            significance_level=significance_level,
            computation_time_seconds=float(time.perf_counter() - started),
            warnings=warnings,
            metadata={
                "cond_ind_test": cond_ind_test,
                "max_lag": max_lag,
                "requested_n_bootstrap": n_bootstrap_requested,
                "block_length": block_length,
                "timeout_seconds": timeout_seconds,
                **ci_backend_metadata(ci_backend),
                "ci_backend_runtime": (
                    "jax_partial_corr_surrogate"
                    if ci_backend.used == "jax"
                    else "tigramite"
                ),
            },
        )
        return {"report": report, "__determinism_tier__": DeterminismTier.STATISTICAL}


__all__ = ["PCMCIDiscovery"]
