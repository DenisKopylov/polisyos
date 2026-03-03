from __future__ import annotations

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
from polisyos.foundry.methods.catalog.causal._graph_projection import pag_to_dag_projection
from polisyos.foundry.methods.catalog.causal.ci_backends import (
    CIBackendSelection,
    ci_backend_metadata,
    partial_corr,
    resolve_discovery_ci_backend,
)
from polisyos.foundry.methods.catalog.causal.protocols import TabularCausalDiscoveryData
from polisyos.ir.analytics.causal_discovery import CausalDiscoveryReport
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    EdgeSource,
    GraphType,
    PAGIdentificationPolicy,
)

_VALID_CI_TESTS = frozenset({"fisherz", "chisq", "gsq", "kci"})
_VALID_GES_SCORE_FUNCS = frozenset(
    {
        "local_score_bic",
        "local_score_bdeu",
        "local_score_cv_general",
        "local_score_marginal_general",
        "local_score_cv_multi",
        "local_score_marginal_multi",
    }
)
_VALID_DISCOVERY_SCALE_BACKENDS = frozenset({"auto", "classic", "dagma"})
_ENDPOINT_TO_MARK = {
    -1: EdgeMark.TAIL,
    1: EdgeMark.ARROW,
    2: EdgeMark.CIRCLE,
}


@dataclass(frozen=True)
class _DiscoveryExecutionResult:
    adjacency: np.ndarray | None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    timed_out: bool = False


@dataclass(frozen=True)
class _ScaleBackendSelection:
    requested: str
    used: str
    fallback_reason: str | None = None


def _clamp_probability(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def _edge_key(edge: CausalEdge) -> str:
    return f"{edge.src}|{edge.mark_src.value}>{edge.mark_dst.value}|{edge.dst}"


def _bootstrap_resample(*, data: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    if data.shape[0] == 0:
        return data
    indices = rng.integers(0, data.shape[0], size=data.shape[0])
    return data[indices]


def _resolve_scale_backend(raw: Any, *, n_variables: int) -> _ScaleBackendSelection:
    requested = str(raw).strip().lower() if raw is not None else "auto"
    if not requested:
        requested = "auto"
    if requested not in _VALID_DISCOVERY_SCALE_BACKENDS:
        return _ScaleBackendSelection(
            requested=requested,
            used="classic",
            fallback_reason=(
                f"unsupported_discovery_scale_backend:{requested}; "
                "expected one of auto|classic|dagma"
            ),
        )
    if requested == "classic":
        return _ScaleBackendSelection(requested="classic", used="classic")
    if requested == "dagma":
        return _ScaleBackendSelection(requested="dagma", used="dagma")
    if n_variables > 50:
        return _ScaleBackendSelection(requested="auto", used="dagma")
    return _ScaleBackendSelection(requested="auto", used="classic")


def _resolve_constraint_ci_backend(raw: Any) -> CIBackendSelection:
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
    return CIBackendSelection(
        requested=base.requested,
        used="jax",
        fallback_reason=base.fallback_reason,
    )


def _adjacency_to_edges(
    *,
    adjacency: np.ndarray,
    variable_names: list[str],
) -> tuple[list[CausalEdge], list[str]]:
    if adjacency.ndim != 2:
        raise ValueError(f"adjacency matrix must be 2D, got shape={adjacency.shape}")

    n_variables = len(variable_names)
    if adjacency.shape != (n_variables, n_variables):
        raise ValueError(
            "adjacency matrix dimensions do not match variable names: "
            f"adjacency={adjacency.shape}, variables={n_variables}"
        )

    edges: list[CausalEdge] = []
    warnings: list[str] = []
    for src_idx in range(n_variables):
        for dst_idx in range(src_idx + 1, n_variables):
            code_src = int(adjacency[src_idx, dst_idx])
            code_dst = int(adjacency[dst_idx, src_idx])
            if code_src == 0 and code_dst == 0:
                continue

            mark_src = _ENDPOINT_TO_MARK.get(code_src)
            mark_dst = _ENDPOINT_TO_MARK.get(code_dst)
            if mark_src is None or mark_dst is None:
                warnings.append(
                    "unsupported_endpoint_code_pair: "
                    f"{variable_names[src_idx]}-{variable_names[dst_idx]} "
                    f"codes=({code_src},{code_dst})"
                )
                continue

            src_name = variable_names[src_idx]
            dst_name = variable_names[dst_idx]
            if mark_src is EdgeMark.ARROW and mark_dst is EdgeMark.TAIL:
                src_name, dst_name = dst_name, src_name
                mark_src, mark_dst = EdgeMark.TAIL, EdgeMark.ARROW

            edge = CausalEdge(
                src=src_name,
                dst=dst_name,
                mark_src=mark_src,
                mark_dst=mark_dst,
                sources=[EdgeSource.DATA],
            )
            edges.append(
                edge.model_copy(
                    update={"combined_confidence": edge.compute_combined_confidence()},
                )
            )
    return edges, warnings


def _run_pc(
    *,
    data: np.ndarray,
    variable_names: list[str],
    significance_level: float,
    params: Mapping[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    from causallearn.search.ConstraintBased.PC import pc

    indep_test = str(params.get("indep_test", "fisherz")).strip().lower()
    if indep_test not in _VALID_CI_TESTS:
        raise ValueError(
            f"Unsupported indep_test={indep_test!r}; expected {sorted(_VALID_CI_TESTS)}"
        )

    stable = bool(params.get("stable", True))
    uc_rule = int(params.get("uc_rule", 0))
    uc_priority = int(params.get("uc_priority", 2))

    graph = pc(
        data=np.asarray(data, dtype=float),
        alpha=float(significance_level),
        indep_test=indep_test,
        stable=stable,
        uc_rule=uc_rule,
        uc_priority=uc_priority,
        node_names=list(variable_names),
        show_progress=False,
    )
    return np.asarray(graph.G.graph, dtype=int), {
        "indep_test": indep_test,
        "stable": stable,
        "uc_rule": uc_rule,
        "uc_priority": uc_priority,
    }


def _run_fci(
    *,
    data: np.ndarray,
    variable_names: list[str],
    significance_level: float,
    params: Mapping[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    from causallearn.search.ConstraintBased.FCI import fci

    indep_test = str(params.get("indep_test", "fisherz")).strip().lower()
    if indep_test not in _VALID_CI_TESTS:
        raise ValueError(
            f"Unsupported indep_test={indep_test!r}; expected {sorted(_VALID_CI_TESTS)}"
        )

    depth = int(params.get("depth", -1))
    max_path_length = int(params.get("max_path_length", -1))
    graph, _ = fci(
        dataset=np.asarray(data, dtype=float),
        independence_test_method=indep_test,
        alpha=float(significance_level),
        depth=depth,
        max_path_length=max_path_length,
        verbose=False,
        show_progress=False,
        node_names=list(variable_names),
    )
    return np.asarray(graph.graph, dtype=int), {
        "indep_test": indep_test,
        "depth": depth,
        "max_path_length": max_path_length,
    }


def _run_ges(
    *,
    data: np.ndarray,
    variable_names: list[str],
    params: Mapping[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    from causallearn.search.ScoreBased.GES import ges

    score_func = str(params.get("score_func", "local_score_BIC")).strip()
    normalized_score_func = score_func.lower()
    if normalized_score_func not in _VALID_GES_SCORE_FUNCS:
        raise ValueError(
            f"Unsupported score_func={score_func!r}; expected {sorted(_VALID_GES_SCORE_FUNCS)}"
        )

    max_parents_raw = params.get("max_parents")
    max_parents = None if max_parents_raw is None else float(max_parents_raw)
    score_parameters_raw = params.get("score_parameters")
    score_parameters = (
        dict(score_parameters_raw) if isinstance(score_parameters_raw, Mapping) else None
    )

    record = ges(
        X=np.asarray(data, dtype=float),
        score_func=score_func,
        maxP=max_parents,
        parameters=score_parameters,
        node_names=list(variable_names),
    )
    graph = record.get("G")
    if graph is None:
        raise ValueError("GES returned no graph output")
    return np.asarray(graph.graph, dtype=int), {
        "score_func": score_func,
        "max_parents": max_parents,
        "score": record.get("score"),
    }


def _discovery_worker(
    queue: Any,
    algorithm: str,
    data: np.ndarray,
    variable_names: list[str],
    significance_level: float,
    params: dict[str, Any],
    seed: int,
) -> None:
    try:
        np.random.seed(seed)
        if algorithm == "pc":
            adjacency, metadata = _run_pc(
                data=data,
                variable_names=variable_names,
                significance_level=significance_level,
                params=params,
            )
        elif algorithm == "fci":
            adjacency, metadata = _run_fci(
                data=data,
                variable_names=variable_names,
                significance_level=significance_level,
                params=params,
            )
        elif algorithm == "ges":
            adjacency, metadata = _run_ges(
                data=data,
                variable_names=variable_names,
                params=params,
            )
        else:
            raise ValueError(f"Unsupported discovery algorithm={algorithm!r}")

        queue.put(
            {
                "ok": True,
                "adjacency": adjacency.tolist(),
                "metadata": metadata,
            }
        )
    except Exception as exc:  # pragma: no cover - exercised via parent process behavior
        queue.put({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def _run_discovery_with_timeout(
    *,
    algorithm: str,
    data: np.ndarray,
    variable_names: list[str],
    significance_level: float,
    params: Mapping[str, Any],
    timeout_seconds: float,
    seed: int,
) -> _DiscoveryExecutionResult:
    if timeout_seconds <= 0.0:
        return _DiscoveryExecutionResult(
            adjacency=None,
            metadata={},
            error="discovery timeout budget exhausted",
            timed_out=True,
        )

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    process = ctx.Process(
        target=_discovery_worker,
        args=(
            queue,
            str(algorithm),
            np.asarray(data, dtype=float),
            list(variable_names),
            float(significance_level),
            dict(params),
            int(seed),
        ),
    )
    process.start()
    process.join(timeout=timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(timeout=1.0)
        return _DiscoveryExecutionResult(
            adjacency=None,
            metadata={},
            error=f"{algorithm.upper()} timeout after {timeout_seconds:.2f}s",
            timed_out=True,
        )

    payload: dict[str, Any] | None = None
    if not queue.empty():
        payload = queue.get_nowait()

    if payload is None:
        if process.exitcode == 0:
            return _DiscoveryExecutionResult(
                adjacency=None,
                metadata={},
                error=f"{algorithm.upper()} worker exited without payload",
                timed_out=False,
            )
        return _DiscoveryExecutionResult(
            adjacency=None,
            metadata={},
            error=f"{algorithm.upper()} worker exited with code {process.exitcode}",
            timed_out=False,
        )

    if not bool(payload.get("ok", False)):
        return _DiscoveryExecutionResult(
            adjacency=None,
            metadata={},
            error=str(payload.get("error", f"{algorithm.upper()} failed")),
            timed_out=False,
        )

    adjacency_raw = payload.get("adjacency")
    adjacency = None
    if adjacency_raw is not None:
        adjacency = np.asarray(adjacency_raw, dtype=int)

    metadata_raw = payload.get("metadata")
    metadata = dict(metadata_raw) if isinstance(metadata_raw, Mapping) else {}
    return _DiscoveryExecutionResult(
        adjacency=adjacency,
        metadata=metadata,
        error=None,
        timed_out=False,
    )


def _run_jax_constraint_discovery(
    *,
    algorithm: str,
    data: np.ndarray,
    variable_names: list[str],
    significance_level: float,
) -> _DiscoveryExecutionResult:
    """Deterministic JAX CI runtime path for explicit `discovery_ci_backend=jax`."""
    arr = np.asarray(data, dtype=float)
    if arr.ndim != 2:
        return _DiscoveryExecutionResult(
            adjacency=None,
            metadata={},
            error=f"JAX CI expects 2D data, got shape={arr.shape}",
            timed_out=False,
        )
    n_samples, n_vars = arr.shape
    if n_vars != len(variable_names):
        return _DiscoveryExecutionResult(
            adjacency=None,
            metadata={},
            error=(
                "JAX CI variable mismatch: "
                f"data_cols={n_vars}, variables={len(variable_names)}"
            ),
            timed_out=False,
        )
    if n_samples < 4:
        return _DiscoveryExecutionResult(
            adjacency=None,
            metadata={},
            error=f"JAX CI requires at least 4 samples, got {n_samples}",
            timed_out=False,
        )

    adjacency = np.zeros((n_vars, n_vars), dtype=int)
    threshold = max(0.01, float(significance_level))
    strengths: list[float] = []
    for src_idx in range(n_vars):
        for dst_idx in range(src_idx + 1, n_vars):
            others = [idx for idx in range(n_vars) if idx not in {src_idx, dst_idx}]
            cond = arr[:, others] if others else None
            corr = float(
                partial_corr(
                    arr[:, src_idx],
                    arr[:, dst_idx],
                    cond,
                    backend="jax",
                )
            )
            strength = float(abs(corr))
            strengths.append(strength)
            if strength < threshold:
                continue
            if algorithm == "fci":
                # PAG uncertainty mark (circle -> arrow) in deterministic index order.
                adjacency[src_idx, dst_idx] = 2
                adjacency[dst_idx, src_idx] = 1
            else:
                # Deterministic orientation by index for CPDAG-like path.
                adjacency[src_idx, dst_idx] = -1
                adjacency[dst_idx, src_idx] = 1
    metadata = {
        "ci_runtime": "jax_partial_corr",
        "ci_threshold": threshold,
        "ci_mean_strength": float(np.mean(strengths)) if strengths else 0.0,
        "ci_max_strength": float(np.max(strengths)) if strengths else 0.0,
    }
    return _DiscoveryExecutionResult(
        adjacency=adjacency,
        metadata=metadata,
        error=None,
        timed_out=False,
    )


def _graph_kind_for_algorithm(algorithm: str) -> GraphType:
    if algorithm == "fci":
        return GraphType.PAG
    return GraphType.CPDAG


def _method_name_for_algorithm(algorithm: str) -> str:
    if algorithm == "pc":
        return "pc"
    if algorithm == "fci":
        return "fci"
    if algorithm == "ges":
        return "ges"
    raise ValueError(f"Unsupported discovery algorithm={algorithm!r}")


def _build_graph(
    *,
    algorithm: str,
    adjacency: np.ndarray,
    variable_names: list[str],
    extra_metadata: Mapping[str, Any] | None = None,
) -> tuple[CausalGraphModel, CausalGraphModel | None, list[str]]:
    graph_type = _graph_kind_for_algorithm(algorithm)
    method_name = _method_name_for_algorithm(algorithm)
    edges, conversion_warnings = _adjacency_to_edges(
        adjacency=adjacency,
        variable_names=variable_names,
    )
    metadata = dict(extra_metadata) if extra_metadata else {}
    if graph_type is GraphType.PAG:
        graph = CausalGraphModel(
            graph_type=graph_type,
            nodes=list(variable_names),
            edges=edges,
            discovery_method=method_name,
            pag_identification_policy=PAGIdentificationPolicy.CONSERVATIVE,
            metadata=metadata,
        )
        resolved_graph, _ = pag_to_dag_projection(graph)
        return graph, resolved_graph, conversion_warnings

    graph = CausalGraphModel(
        graph_type=graph_type,
        nodes=list(variable_names),
        edges=edges,
        discovery_method=method_name,
        metadata=metadata,
    )
    return graph, None, conversion_warnings


def _fallback_report(
    *,
    state: TabularCausalDiscoveryData,
    algorithm: str,
    significance_level: float,
    warnings: list[str],
    elapsed_seconds: float,
    params: Mapping[str, Any],
    ci_backend: CIBackendSelection,
    scale_backend: _ScaleBackendSelection,
) -> CausalDiscoveryReport:
    graph_type = _graph_kind_for_algorithm(algorithm)
    method_name = _method_name_for_algorithm(algorithm)
    if graph_type is GraphType.PAG:
        graph = CausalGraphModel(
            graph_type=graph_type,
            nodes=list(state.variable_names),
            edges=[],
            discovery_method=method_name,
            pag_identification_policy=PAGIdentificationPolicy.CONSERVATIVE,
        )
        resolved_graph, _ = pag_to_dag_projection(graph)
    else:
        graph = CausalGraphModel(
            graph_type=graph_type,
            nodes=list(state.variable_names),
            edges=[],
            discovery_method=method_name,
        )
        resolved_graph = None
    return CausalDiscoveryReport(
        method=method_name,
        graph=graph,
        resolved_graph=resolved_graph,
        bootstrap_stability={},
        n_bootstrap=0,
        significance_level=significance_level,
        computation_time_seconds=elapsed_seconds,
        warnings=warnings,
        metadata={
            "fallback": True,
            "requested_n_bootstrap": int(params.get("n_bootstrap", 0) or 0),
            "timeout_seconds": float(params.get("timeout_seconds", 600.0) or 600.0),
            **ci_backend_metadata(ci_backend),
            "scale_backend_requested": scale_backend.requested,
            "scale_backend_used": scale_backend.used,
            "scale_backend_fallback_reason": scale_backend.fallback_reason,
        },
    )


def _run_constraint_discovery(
    *,
    state: TabularCausalDiscoveryData,
    params: Mapping[str, Any],
    algorithm: str,
) -> dict[str, Any]:
    tab_data = (
        state
        if isinstance(state, TabularCausalDiscoveryData)
        else TabularCausalDiscoveryData.model_validate(state)
    )
    significance_level = _clamp_probability(float(params.get("significance_level", 0.05)))
    n_bootstrap_requested = max(0, int(params.get("n_bootstrap", 0)))
    timeout_seconds = max(1.0, float(params.get("timeout_seconds", 600.0)))
    seed = int(params.get("__seed__", 0) or 0)
    ci_backend = _resolve_constraint_ci_backend(params.get("discovery_ci_backend"))
    scale_backend = _resolve_scale_backend(
        params.get("discovery_scale_backend"),
        n_variables=tab_data.n_variables,
    )

    started = time.perf_counter()
    warnings: list[str] = []
    deadline = started + timeout_seconds

    if scale_backend.used == "dagma":
        from polisyos.foundry.methods.catalog.causal.dagma_discovery import run_dagma_discovery

        dagma_params = dict(params)
        dagma_params["timeout_seconds"] = max(1.0, deadline - time.perf_counter())
        dagma_output = run_dagma_discovery(state=tab_data, params=dagma_params)
        dagma_report_raw = dagma_output["report"]
        if isinstance(dagma_report_raw, CausalDiscoveryReport):
            dagma_report = dagma_report_raw
        else:
            dagma_report = CausalDiscoveryReport.model_validate(dagma_report_raw)
        dagma_metadata = dict(dagma_report.metadata)
        dagma_failed = bool(dagma_metadata.get("fallback"))
        if not dagma_failed:
            report = dagma_report.model_copy(
                update={
                    "metadata": {
                        **dagma_metadata,
                        **ci_backend_metadata(ci_backend),
                        "scale_backend_requested": scale_backend.requested,
                        "scale_backend_used": "dagma",
                        "scale_backend_fallback_reason": scale_backend.fallback_reason,
                        "trigger_algorithm": algorithm,
                    }
                }
            )
            return {"report": report, "__determinism_tier__": DeterminismTier.STATISTICAL}

        fallback_reason = "dagma_auto_fallback_to_classic"
        if scale_backend.requested == "dagma":
            report = dagma_report.model_copy(
                update={
                    "metadata": {
                        **dagma_metadata,
                        **ci_backend_metadata(ci_backend),
                        "scale_backend_requested": scale_backend.requested,
                        "scale_backend_used": "dagma",
                        "scale_backend_fallback_reason": dagma_metadata.get("fallback_reason"),
                        "trigger_algorithm": algorithm,
                    }
                }
            )
            return {"report": report, "__determinism_tier__": DeterminismTier.STATISTICAL}
        warnings.append(fallback_reason)
        scale_backend = _ScaleBackendSelection(
            requested=scale_backend.requested,
            used="classic",
            fallback_reason=fallback_reason,
        )

    if ci_backend.used == "jax":
        base_result = _run_jax_constraint_discovery(
            algorithm=algorithm,
            data=tab_data.data,
            variable_names=tab_data.variable_names,
            significance_level=significance_level,
        )
    else:
        base_result = _run_discovery_with_timeout(
            algorithm=algorithm,
            data=tab_data.data,
            variable_names=tab_data.variable_names,
            significance_level=significance_level,
            params=params,
            timeout_seconds=max(0.0, deadline - time.perf_counter()),
            seed=seed,
        )
    if base_result.error is not None or base_result.adjacency is None:
        if base_result.error is not None:
            warnings.append(base_result.error)
        report = _fallback_report(
            state=tab_data,
            algorithm=algorithm,
            significance_level=significance_level,
            warnings=warnings,
            elapsed_seconds=float(time.perf_counter() - started),
            params=params,
            ci_backend=ci_backend,
            scale_backend=scale_backend,
        )
        return {"report": report, "__determinism_tier__": DeterminismTier.STATISTICAL}

    try:
        graph, resolved_graph, conversion_warnings = _build_graph(
            algorithm=algorithm,
            adjacency=base_result.adjacency,
            variable_names=tab_data.variable_names,
            extra_metadata=base_result.metadata,
        )
    except Exception as exc:
        warnings.append(
            f"{_method_name_for_algorithm(algorithm).upper()} graph conversion failed: {exc}"
        )
        report = _fallback_report(
            state=tab_data,
            algorithm=algorithm,
            significance_level=significance_level,
            warnings=warnings,
            elapsed_seconds=float(time.perf_counter() - started),
            params=params,
            ci_backend=ci_backend,
            scale_backend=scale_backend,
        )
        return {"report": report, "__determinism_tier__": DeterminismTier.STATISTICAL}

    warnings.extend(conversion_warnings)

    bootstrap_stability: dict[str, float] = {}
    completed_bootstrap = 0
    base_edge_keys = [_edge_key(edge) for edge in graph.edges]
    if n_bootstrap_requested > 0 and base_edge_keys:
        hit_counts = {key: 0 for key in base_edge_keys}
        bootstrap_rng = np.random.default_rng(seed + 7919)
        for idx in range(n_bootstrap_requested):
            remaining = max(0.0, deadline - time.perf_counter())
            if remaining <= 0.0:
                warnings.append(
                    "bootstrap_truncated: timeout budget exhausted before all runs completed"
                )
                break

            sampled = _bootstrap_resample(data=tab_data.data, rng=bootstrap_rng)
            if ci_backend.used == "jax":
                boot_result = _run_jax_constraint_discovery(
                    algorithm=algorithm,
                    data=sampled,
                    variable_names=tab_data.variable_names,
                    significance_level=significance_level,
                )
            else:
                boot_result = _run_discovery_with_timeout(
                    algorithm=algorithm,
                    data=sampled,
                    variable_names=tab_data.variable_names,
                    significance_level=significance_level,
                    params=params,
                    timeout_seconds=remaining,
                    seed=seed + idx + 1,
                )
            if boot_result.error is not None or boot_result.adjacency is None:
                if boot_result.error is not None:
                    warnings.append(f"bootstrap_run_{idx}: {boot_result.error}")
                if boot_result.timed_out:
                    warnings.append("bootstrap_truncated: timeout during bootstrap")
                    break
                continue

            try:
                boot_graph, _, boot_conversion_warnings = _build_graph(
                    algorithm=algorithm,
                    adjacency=boot_result.adjacency,
                    variable_names=tab_data.variable_names,
                )
            except Exception as exc:
                warnings.append(f"bootstrap_run_{idx}: graph conversion failed: {exc}")
                continue

            for warning in boot_conversion_warnings:
                warnings.append(f"bootstrap_run_{idx}: {warning}")

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
        method=_method_name_for_algorithm(algorithm),
        graph=graph,
        resolved_graph=resolved_graph,
        bootstrap_stability=bootstrap_stability,
        n_bootstrap=completed_bootstrap,
        significance_level=significance_level,
        computation_time_seconds=float(time.perf_counter() - started),
        warnings=warnings,
        metadata={
            **dict(base_result.metadata),
            "requested_n_bootstrap": n_bootstrap_requested,
            "timeout_seconds": timeout_seconds,
            **ci_backend_metadata(ci_backend),
            "ci_backend_runtime": (
                "jax_partial_corr" if ci_backend.used == "jax" else "causallearn"
            ),
            "scale_backend_requested": scale_backend.requested,
            "scale_backend_used": scale_backend.used,
            "scale_backend_fallback_reason": scale_backend.fallback_reason,
        },
    )
    return {"report": report, "__determinism_tier__": DeterminismTier.STATISTICAL}


@foundry_method(
    namespace="causal.discovery",
    version="1.0.0",
    tags={"causal", "discovery", "constraint-based", "pc"},
)
class PCDiscovery:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="pc_discovery",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="tabular_discovery_data",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("observations", "rows"),
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
            ParameterSpec(name="indep_test", default="fisherz"),
            ParameterSpec(name="stable", default=True),
            ParameterSpec(name="uc_rule", default=0),
            ParameterSpec(name="uc_priority", default=2),
            ParameterSpec(name="discovery_scale_backend", default="auto"),
            ParameterSpec(name="discovery_ci_backend", default="auto"),
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
        description="PC algorithm via causal-learn for cross-sectional causal discovery.",
        tags=frozenset({"causal", "discovery", "pc", "constraint-based"}),
        assumptions={
            "causal_sufficiency": "No severe hidden confounding for CPDAG interpretation.",
            "ci_test_validity": "Selected CI test assumptions hold for input data.",
        },
    )

    @staticmethod
    def pure_step(state: TabularCausalDiscoveryData, params: Mapping[str, Any]) -> dict[str, Any]:
        return _run_constraint_discovery(state=state, params=params, algorithm="pc")


@foundry_method(
    namespace="causal.discovery",
    version="1.0.0",
    tags={"causal", "discovery", "constraint-based", "fci"},
)
class FCIDiscovery:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="fci_discovery",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="tabular_discovery_data",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("observations", "rows"),
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
            ParameterSpec(name="indep_test", default="fisherz"),
            ParameterSpec(name="depth", default=-1),
            ParameterSpec(name="max_path_length", default=-1),
            ParameterSpec(name="discovery_scale_backend", default="auto"),
            ParameterSpec(name="discovery_ci_backend", default="auto"),
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
        description="FCI algorithm via causal-learn, preserving PAG uncertainty.",
        tags=frozenset({"causal", "discovery", "fci", "pag"}),
        assumptions={
            "latent_confounding": "Latent confounding may be present; output interpreted as PAG.",
            "ci_test_validity": "Selected CI test assumptions hold for input data.",
        },
    )

    @staticmethod
    def pure_step(state: TabularCausalDiscoveryData, params: Mapping[str, Any]) -> dict[str, Any]:
        return _run_constraint_discovery(state=state, params=params, algorithm="fci")


@foundry_method(
    namespace="causal.discovery",
    version="1.0.0",
    tags={"causal", "discovery", "score-based", "ges"},
)
class GESDiscovery:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ges_discovery",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="tabular_discovery_data",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("observations", "rows"),
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
            ParameterSpec(name="score_func", default="local_score_BIC"),
            ParameterSpec(name="max_parents", default=None),
            ParameterSpec(name="discovery_scale_backend", default="auto"),
            ParameterSpec(name="discovery_ci_backend", default="auto"),
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
        description="GES score-based discovery via causal-learn.",
        tags=frozenset({"causal", "discovery", "ges", "score-based"}),
        assumptions={
            "score_adequacy": "Selected score function is suitable for data generating process.",
            "causal_sufficiency": "No severe hidden confounding for CPDAG interpretation.",
        },
    )

    @staticmethod
    def pure_step(state: TabularCausalDiscoveryData, params: Mapping[str, Any]) -> dict[str, Any]:
        return _run_constraint_discovery(state=state, params=params, algorithm="ges")


__all__ = [
    "PCDiscovery",
    "FCIDiscovery",
    "GESDiscovery",
]
