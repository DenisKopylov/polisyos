"""Algorithm-portfolio runner for discovery-phase graph hypotheses."""

from __future__ import annotations

import math
import warnings
from collections.abc import Mapping
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from polisyos.foundry.calibration.dp_ci import CITestThresholdPolicySet, DPContext
from polisyos.foundry.methods.catalog.causal.protocols import (
    TabularCausalDiscoveryData,
    TimeSeriesCausalData,
)
from polisyos.ir.analytics.causal_discovery import (
    AlgebraicBlockSpec,
    CausalDiscoveryReport,
    DataCharacteristics,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeSource, GraphType
from polisyos.scientist.methods.discovery.schema import (
    ComputeFootprint,
    DiscoveryAlgorithmFamily,
    DiscoveryMethod,
    GraphHypothesis,
    graph_hypothesis_from_report,
)
from polisyos.scientist.methods.search.judge_thresholds import JudgeThresholdRegistry


class PortfolioRunnerConfig(BaseModel):
    """Configuration for Phase-C algorithm portfolio execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    significance_level: float = Field(default=0.05, ge=0.0, le=1.0)
    timeout_seconds: float = Field(default=120.0, gt=0.0)
    max_lag: int = Field(default=5, ge=1)
    random_seed: int = 0
    n_bootstrap: int = Field(default=0, ge=0)
    algebraic_blocks: list[AlgebraicBlockSpec] = Field(default_factory=list)
    method_params: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def params_for(
        self,
        method: DiscoveryMethod,
        *,
        seed_offset: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "significance_level": self.significance_level,
            "timeout_seconds": self.timeout_seconds,
            "n_bootstrap": self.n_bootstrap,
            "__seed__": self.random_seed + seed_offset,
        }
        if method is DiscoveryMethod.PCMCI_PLUS:
            params["max_lag"] = self.max_lag
        if method in {DiscoveryMethod.PC, DiscoveryMethod.FCI, DiscoveryMethod.GES}:
            params.setdefault("discovery_scale_backend", "classic")
        if (
            method
            in {
                DiscoveryMethod.PC,
                DiscoveryMethod.FCI,
                DiscoveryMethod.GES,
                DiscoveryMethod.DAGMA,
            }
            and self.algebraic_blocks
        ):
            params["algebraic_blocks"] = [
                block.model_dump(mode="json") for block in self.algebraic_blocks
            ]
        if method in {DiscoveryMethod.ANM, DiscoveryMethod.PAIRWISE_HEURISTIC}:
            params.setdefault("functional_strength_threshold", 0.20)
            params.setdefault("functional_max_edges", 8)
        overrides = self.method_params.get(method.value, {})
        params.update(dict(overrides))
        return params


class PortfolioCandidate(BaseModel):
    """One concrete portfolio run plus its normalized graph hypothesis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hypothesis: GraphHypothesis
    source_report: CausalDiscoveryReport
    method_params: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class PortfolioRunResult(BaseModel):
    """Portfolio outcome over all compatible discovery methods."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidates: list[PortfolioCandidate] = Field(default_factory=list)
    skipped_families: dict[DiscoveryAlgorithmFamily, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    data_characteristics: DataCharacteristics | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class _ReachabilityTracker:
    """Incremental transitive-closure helper for greedy DAG construction."""

    def __init__(self, nodes: list[str]) -> None:
        self._ancestors: dict[str, set[str]] = {name: set() for name in nodes}
        self._descendants: dict[str, set[str]] = {name: set() for name in nodes}

    def would_create_cycle(self, src: str, dst: str) -> bool:
        return src == dst or src in self._descendants.get(dst, set())

    def add_edge(self, src: str, dst: str) -> None:
        ancestors = {src, *self._ancestors.get(src, set())}
        descendants = {dst, *self._descendants.get(dst, set())}
        for ancestor in ancestors:
            self._descendants.setdefault(ancestor, set()).update(descendants)
        for descendant in descendants:
            self._ancestors.setdefault(descendant, set()).update(ancestors)


def run_discovery_method(
    state: TabularCausalDiscoveryData | TimeSeriesCausalData,
    method: DiscoveryMethod | str,
    params: dict[str, Any],
) -> CausalDiscoveryReport:
    """Execute one supported discovery method through the foundry adapters."""

    normalized = DiscoveryMethod(method)
    params = _inject_resolved_ci_threshold_policies(params)
    if normalized is DiscoveryMethod.PC:
        from polisyos.foundry.methods.catalog.causal.constraint_discovery import PCDiscovery

        return CausalDiscoveryReport.model_validate(PCDiscovery.pure_step(state, params)["report"])
    if normalized is DiscoveryMethod.FCI:
        from polisyos.foundry.methods.catalog.causal.constraint_discovery import FCIDiscovery

        return CausalDiscoveryReport.model_validate(FCIDiscovery.pure_step(state, params)["report"])
    if normalized is DiscoveryMethod.GES:
        from polisyos.foundry.methods.catalog.causal.constraint_discovery import GESDiscovery

        return CausalDiscoveryReport.model_validate(GESDiscovery.pure_step(state, params)["report"])
    if normalized is DiscoveryMethod.DAGMA:
        from polisyos.foundry.methods.catalog.causal.dagma_discovery import run_dagma_discovery

        return CausalDiscoveryReport.model_validate(
            run_dagma_discovery(state=state, params=params)["report"]
        )
    if normalized in {DiscoveryMethod.ANM, DiscoveryMethod.PAIRWISE_HEURISTIC}:
        return _run_functional_discovery(state, normalized, params)
    from polisyos.foundry.methods.catalog.causal.pcmci_discovery import PCMCIDiscovery

    return CausalDiscoveryReport.model_validate(PCMCIDiscovery.pure_step(state, params)["report"])


def _inject_resolved_ci_threshold_policies(params: dict[str, Any]) -> dict[str, Any]:
    """Resolve a Scientist registry path before invoking Foundry methods."""

    prepared = dict(params)
    registry_root = prepared.pop("judge_threshold_registry_root", None)
    if registry_root is None:
        policy_payload = prepared.get("ci_threshold_policies")
        if policy_payload is None:
            return prepared
        policy_set = CITestThresholdPolicySet.model_validate(policy_payload)
        _validate_ci_threshold_policy_set(
            policy_set,
            dp_context=prepared.get("dp_context"),
            readiness_target=str(prepared.get("readiness_target", "diagnostic")),
        )
        prepared["ci_threshold_policies"] = policy_set.model_dump(mode="python")
        return prepared

    registry = JudgeThresholdRegistry(Path(str(registry_root)))
    dp_context = prepared.get("dp_context")
    readiness_target = str(prepared.get("readiness_target", "diagnostic"))
    alpha = float(prepared.get("significance_level", prepared.get("alpha", 0.05)))
    policies = (
        registry.resolve_ci_test_policy(
            family="kernel_ci",
            query_type="hsic",
            estimator="permutation",
            dp_context=dp_context,
            alpha=alpha,
            n_bootstrap=99,
            readiness_target=readiness_target,
        ),
        registry.resolve_ci_test_policy(
            family="kernel_ci",
            query_type="kci",
            estimator="residualized_hsic",
            dp_context=dp_context,
            alpha=alpha,
            n_bootstrap=99,
            readiness_target=readiness_target,
        ),
        registry.resolve_ci_test_policy(
            family="categorical_ci",
            query_type="g2",
            estimator="stratified_counts",
            dp_context=dp_context,
            alpha=alpha,
            n_bootstrap=2000,
            readiness_target=readiness_target,
        ),
        registry.resolve_ci_test_policy(
            family="categorical_ci",
            query_type="chi2",
            estimator="stratified_counts",
            dp_context=dp_context,
            alpha=alpha,
            n_bootstrap=2000,
            readiness_target=readiness_target,
        ),
    )
    policy_set = CITestThresholdPolicySet(policies=policies)
    _validate_ci_threshold_policy_set(
        policy_set,
        dp_context=dp_context,
        readiness_target=readiness_target,
    )
    prepared["ci_threshold_policies"] = policy_set.model_dump(mode="python")
    return prepared


def _validate_ci_threshold_policy_set(
    policy_set: CITestThresholdPolicySet,
    *,
    dp_context: DPContext | Mapping[str, Any] | None,
    readiness_target: str,
) -> None:
    """Fail before dispatch unless every portfolio CI route has an exact policy."""

    for family, query_type, estimator in (
        ("kernel_ci", "hsic", "permutation"),
        ("kernel_ci", "kci", "residualized_hsic"),
        ("categorical_ci", "g2", "stratified_counts"),
        ("categorical_ci", "chi2", "stratified_counts"),
    ):
        policy_set.policy_for(
            family=family,
            query_type=query_type,
            estimator=estimator,
            dp_context=dp_context,
            readiness_target=readiness_target,
        )


class GraphDiscoveryPortfolioRunner:
    """Run the Phase-C portfolio and emit independent graph hypotheses."""

    def __init__(
        self,
        *,
        config: PortfolioRunnerConfig | None = None,
    ) -> None:
        self._config = config or PortfolioRunnerConfig()

    @property
    def config(self) -> PortfolioRunnerConfig:
        return self._config

    def run(
        self,
        state: TabularCausalDiscoveryData | TimeSeriesCausalData,
    ) -> PortfolioRunResult:
        methods, skipped = _select_methods(state)
        data_characteristics = _characterize_data(state, config=self._config)

        candidates: list[PortfolioCandidate] = []
        warnings: list[str] = []
        for index, method in enumerate(methods):
            params = self._config.params_for(method, seed_offset=index)
            started = perf_counter()
            try:
                report = run_discovery_method(state, method, params)
            except Exception as exc:
                report = _failure_report(
                    state=state,
                    method=method,
                    params=params,
                    exc=exc,
                    runtime_seconds=perf_counter() - started,
                )
            hypothesis = graph_hypothesis_from_report(
                report,
                hypothesis_id=f"{method.value}_{index}",
                compute_footprint=_compute_footprint(
                    state=state,
                    report=report,
                    params=params,
                ),
                metadata={
                    "portfolio_method": method.value,
                    "portfolio_index": index,
                },
            )
            candidates.append(
                PortfolioCandidate(
                    hypothesis=hypothesis,
                    source_report=report,
                    method_params=params,
                    warnings=list(report.warnings),
                )
            )
            warnings.extend(report.warnings)

        return PortfolioRunResult(
            candidates=candidates,
            skipped_families=skipped,
            warnings=warnings,
            data_characteristics=data_characteristics,
            metadata={
                "n_candidates": len(candidates),
                "n_skipped_families": len(skipped),
            },
        )


def _select_methods(
    state: TabularCausalDiscoveryData | TimeSeriesCausalData,
) -> tuple[list[DiscoveryMethod], dict[DiscoveryAlgorithmFamily, str]]:
    if isinstance(state, TimeSeriesCausalData):
        return (
            [DiscoveryMethod.PCMCI_PLUS],
            {
                DiscoveryAlgorithmFamily.CONSTRAINT_BASED: (
                    "cross_sectional_only_for_phase_c1_to_c4"
                ),
                DiscoveryAlgorithmFamily.SCORE_BASED: ("cross_sectional_only_for_phase_c1_to_c4"),
                DiscoveryAlgorithmFamily.FUNCTIONAL: ("cross_sectional_only_for_phase_c1_to_c4"),
            },
        )
    functional_methods = [DiscoveryMethod.ANM, DiscoveryMethod.PAIRWISE_HEURISTIC]
    return (
        [
            DiscoveryMethod.PC,
            DiscoveryMethod.FCI,
            DiscoveryMethod.GES,
            DiscoveryMethod.DAGMA,
            *functional_methods,
        ],
        {DiscoveryAlgorithmFamily.TIME_SERIES: ("requires_time_series_causal_data")},
    )


def _characterize_data(
    state: TabularCausalDiscoveryData | TimeSeriesCausalData,
    *,
    config: PortfolioRunnerConfig,
) -> DataCharacteristics:
    from polisyos.foundry.methods.catalog.causal.discovery_pipeline import DataCharacterizer

    time_series = isinstance(state, TimeSeriesCausalData)
    return DataCharacterizer.characterize(
        state.data,
        list(state.variable_names),
        time_series=time_series,
        max_lag=config.max_lag if time_series else None,
    )


def _compute_footprint(
    *,
    state: TabularCausalDiscoveryData | TimeSeriesCausalData,
    report: CausalDiscoveryReport,
    params: dict[str, Any],
) -> ComputeFootprint:
    backend_tokens: list[str] = []
    for key in ("scale_backend_used", "ci_backend_used", "ci_backend_runtime", "optimizer"):
        value = report.metadata.get(key)
        if value is None:
            continue
        backend_tokens.append(f"{key}={value}")
    return ComputeFootprint(
        runtime_seconds=float(report.computation_time_seconds),
        timeout_seconds=float(params.get("timeout_seconds", 0.0)),
        n_samples=(
            int(getattr(state.data, "shape", (0, 0))[0])
            if getattr(state, "data", None) is not None
            else None
        ),
        n_variables=len(state.variable_names),
        n_bootstrap=int(params.get("n_bootstrap", 0) or 0),
        random_seed=int(params.get("__seed__", 0) or 0),
        backend=";".join(backend_tokens) if backend_tokens else None,
        method_params=dict(params),
        metadata={
            "report_method": report.method,
            "graph_type": getattr(report.graph.graph_type, "value", str(report.graph.graph_type)),
        },
    )


def _failure_report(
    *,
    state: TabularCausalDiscoveryData | TimeSeriesCausalData,
    method: DiscoveryMethod,
    params: dict[str, Any],
    exc: Exception,
    runtime_seconds: float,
) -> CausalDiscoveryReport:
    message = f"algorithm_failed:{type(exc).__name__}: {exc}"
    return CausalDiscoveryReport(
        method=method.value,
        graph=CausalGraphModel(
            graph_type=_fallback_graph_type(method),
            nodes=list(state.variable_names),
            edges=[],
            discovery_method=method.value,
        ),
        bootstrap_stability={},
        n_bootstrap=int(params.get("n_bootstrap", 0) or 0),
        significance_level=float(params.get("significance_level", 0.05)),
        computation_time_seconds=max(0.0, float(runtime_seconds)),
        warnings=[message],
        metadata={
            "algorithm_failed": True,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        },
    )


def _fallback_graph_type(method: DiscoveryMethod) -> GraphType:
    if method is DiscoveryMethod.FCI:
        return GraphType.PAG
    if method in {DiscoveryMethod.PC, DiscoveryMethod.GES}:
        return GraphType.CPDAG
    return GraphType.DAG


def _run_functional_discovery(
    state: TabularCausalDiscoveryData | TimeSeriesCausalData,
    method: DiscoveryMethod,
    params: dict[str, Any],
) -> CausalDiscoveryReport:
    if not isinstance(state, TabularCausalDiscoveryData):
        raise ValueError("functional discovery requires cross-sectional tabular data")

    data = np.asarray(state.data, dtype=float)
    variable_names = list(state.variable_names)
    correlation = np.corrcoef(data, rowvar=False)
    threshold = float(params.get("functional_strength_threshold", 0.20))
    max_edges = max(1, int(params.get("functional_max_edges", 8)))

    candidates: list[tuple[float, str, str, dict[str, float | str]]] = []
    for left in range(data.shape[1]):
        for right in range(left + 1, data.shape[1]):
            strength = abs(float(correlation[left, right]))
            if not np.isfinite(strength) or strength < threshold:
                continue
            src, dst, diagnostics = _orient_functional_pair(
                data[:, left],
                data[:, right],
                variable_names[left],
                variable_names[right],
                method,
            )
            candidates.append((strength, src, dst, diagnostics))

    candidates.sort(key=lambda item: item[0], reverse=True)
    reachability = _ReachabilityTracker(variable_names)
    edges: list[CausalEdge] = []
    bootstrap_stability: dict[str, float] = {}
    for strength, src, dst, diagnostics in candidates:
        if len(edges) >= max_edges:
            break
        if reachability.would_create_cycle(src, dst):
            continue
        reachability.add_edge(src, dst)
        orientation_gap = float(diagnostics["orientation_gap"])
        orientation_confidence = _clamp01(0.5 + 0.5 * orientation_gap)
        combined_confidence = _clamp01((strength + orientation_confidence) / 2.0)
        edge = CausalEdge(
            src=src,
            dst=dst,
            sources=[EdgeSource.DATA],
            data_confidence=_clamp01(strength),
            combined_confidence=combined_confidence,
            p_value=_clamp01(1.0 - strength),
            evidence_refs=[f"functional:{method.value}:{src}->{dst}"],
            metadata={
                "functional_method": method.value,
                **diagnostics,
            },
        )
        edges.append(edge)
        bootstrap_stability[f"{src}->{dst}"] = combined_confidence

    warnings_list = [
        (
            "functional_portfolio_runner_uses_builtin_proxy;"
            "treat outputs as heuristic graph hypotheses pending backend-specific calibration"
        )
    ]
    if not edges:
        warnings_list.append(
            f"functional_no_edge_above_threshold:{method.value}:threshold={threshold:.3f}"
        )

    return CausalDiscoveryReport(
        method=method.value,
        graph=CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=variable_names,
            edges=edges,
            discovery_method=method.value,
            metadata={"portfolio_family": DiscoveryAlgorithmFamily.FUNCTIONAL.value},
        ),
        bootstrap_stability=bootstrap_stability,
        n_bootstrap=int(params.get("n_bootstrap", 0) or 0),
        significance_level=float(params.get("significance_level", 0.05)),
        computation_time_seconds=0.0,
        warnings=warnings_list,
        metadata={
            "functional_proxy": True,
            "functional_strength_threshold": threshold,
            "functional_max_edges": max_edges,
        },
    )


def _orient_functional_pair(
    left: np.ndarray,
    right: np.ndarray,
    left_name: str,
    right_name: str,
    method: DiscoveryMethod,
) -> tuple[str, str, dict[str, float | str]]:
    if method is DiscoveryMethod.ANM:
        left_to_right = _finite_or_default(_residual_ratio(left, right, degree=2), default=1.0)
        right_to_left = _finite_or_default(_residual_ratio(right, left, degree=2), default=1.0)
        rule = "anm_quadratic_residual"
    else:
        left_to_right = _finite_or_default(_residual_ratio(left, right, degree=1), default=1.0)
        right_to_left = _finite_or_default(_residual_ratio(right, left, degree=1), default=1.0)
        if abs(left_to_right - right_to_left) < 0.02:
            left_var = _finite_or_default(np.var(left), default=0.0)
            right_var = _finite_or_default(np.var(right), default=0.0)
            if left_var <= right_var:
                return (
                    left_name,
                    right_name,
                    {
                        "orientation_rule": "pairwise_variance_tiebreak",
                        "forward_score": left_to_right,
                        "reverse_score": right_to_left,
                        "orientation_gap": _clamp01(
                            abs(left_var - right_var) / max(left_var + right_var, 1e-8)
                        ),
                    },
                )
            return (
                right_name,
                left_name,
                {
                    "orientation_rule": "pairwise_variance_tiebreak",
                    "forward_score": right_to_left,
                    "reverse_score": left_to_right,
                    "orientation_gap": _clamp01(
                        abs(left_var - right_var) / max(left_var + right_var, 1e-8)
                    ),
                },
            )
        rule = "pairwise_linear_residual"

    gap = _clamp01(abs(left_to_right - right_to_left) / max(left_to_right + right_to_left, 1e-8))
    if left_to_right <= right_to_left:
        return (
            left_name,
            right_name,
            {
                "orientation_rule": rule,
                "forward_score": left_to_right,
                "reverse_score": right_to_left,
                "orientation_gap": gap,
            },
        )
    return (
        right_name,
        left_name,
        {
            "orientation_rule": rule,
            "forward_score": right_to_left,
            "reverse_score": left_to_right,
            "orientation_gap": gap,
        },
    )


def _residual_ratio(cause: np.ndarray, effect: np.ndarray, *, degree: int) -> float:
    if cause.size != effect.size:
        raise ValueError("cause and effect vectors must have the same length")
    if cause.size < 3:
        return 1.0
    fit_degree = min(degree, max(1, int(np.unique(cause).size) - 1))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        coeffs = np.polyfit(cause, effect, deg=fit_degree)
    predicted = np.polyval(coeffs, cause)
    residual = effect - predicted
    residual_var = _finite_or_default(np.var(residual), default=0.0)
    effect_var = max(_finite_or_default(np.var(effect), default=0.0), 1e-8)
    return residual_var / effect_var


def _would_create_cycle(adjacency: dict[str, set[str]], src: str, dst: str) -> bool:
    if src == dst:
        return True
    stack = [dst]
    seen: set[str] = set()
    while stack:
        node = stack.pop()
        if node == src:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency.get(node, ()))
    return False


def _clamp01(value: float) -> float:
    if not math.isfinite(float(value)):
        return 0.0
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return float(value)


def _finite_or_default(value: Any, *, default: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(numeric):
        return default
    return numeric


__all__ = [
    "GraphDiscoveryPortfolioRunner",
    "PortfolioCandidate",
    "PortfolioRunResult",
    "PortfolioRunnerConfig",
    "run_discovery_method",
]
