"""Shared bootstrap-stability layer for discovery hypotheses."""

from __future__ import annotations

from enum import Enum
from itertools import combinations
from typing import Any
from zlib import crc32

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.scientist import BootstrapStabilityReportRef
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal.id_engine import (
    IdentificationResult,
    IdentificationStatus,
)
from polisyos.foundry.methods.catalog.causal.optimal_design import optimal_adjustment_set
from polisyos.foundry.methods.catalog.causal.protocols import (
    TabularCausalDiscoveryData,
    TimeSeriesCausalData,
)
from polisyos.ir.analytics.causal_queries import CausalQuery
from polisyos.scientist.methods.discovery.portfolio import PortfolioCandidate, run_discovery_method
from polisyos.scientist.methods.discovery.schema import (
    edge_key_for_edge,
    orientation_key_for_edge,
    skeleton_key_for_edge,
)
from polisyos.scientist.methods.search.artifact_minimality import (
    ArtifactFunction,
    ArtifactMinimalityMixin,
    artifact_functions_field,
)

BOOTSTRAP_STABILITY_REPORT_SCHEMA_NAME = "polisyos.scientist.methods.discovery.BootstrapStabilityReport"


class BootstrapMode(str, Enum):
    """Bootstrap resampling mode chosen by the analyzer."""

    ROW = "row"
    MOVING_BLOCK = "moving_block"


class BootstrapStabilityConfig(BaseModel):
    """Configuration for shared discovery bootstrap replay."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    n_resamples: int = Field(default=20, ge=1)
    seed: int = 0
    block_length: int | None = Field(default=None, ge=1)


class HypothesisStabilitySummary(BaseModel):
    """Bootstrap-derived stability metrics for one hypothesis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hypothesis_id: str = Field(min_length=1)
    edge_selection_frequency: dict[str, float] = Field(default_factory=dict)
    orientation_frequency: dict[str, float] = Field(default_factory=dict)
    skeleton_frequency: dict[str, float] = Field(default_factory=dict)
    mean_edge_stability: float | None = Field(default=None, ge=0.0, le=1.0)
    identifiable_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    adjustment_set_stability: float | None = Field(default=None, ge=0.0, le=1.0)
    completed_resamples: int = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)


class BootstrapStabilityReport(ArtifactMinimalityMixin):
    """Persisted stability report over a portfolio of graph hypotheses."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.PROMOTION_GATING,
            ArtifactFunction.CROSS_RUN_LEARNING,
        )
    )
    bootstrap_mode: BootstrapMode
    config: BootstrapStabilityConfig
    summaries: list[HypothesisStabilitySummary] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def summary_for(self, hypothesis_id: str) -> HypothesisStabilitySummary | None:
        for summary in self.summaries:
            if summary.hypothesis_id == hypothesis_id:
                return summary
        return None


class BootstrapStabilityAnalyzer:
    """Replay discovery candidates under shared resampling."""

    def __init__(
        self,
        *,
        config: BootstrapStabilityConfig | None = None,
    ) -> None:
        self._config = config or BootstrapStabilityConfig()

    @property
    def config(self) -> BootstrapStabilityConfig:
        return self._config

    def analyze(
        self,
        candidates: list[PortfolioCandidate],
        state: TabularCausalDiscoveryData | TimeSeriesCausalData,
        *,
        causal_query: CausalQuery | None = None,
    ) -> BootstrapStabilityReport:
        mode = _resolve_bootstrap_mode(state)
        summaries = [
            self._analyze_candidate(
                candidate,
                state,
                causal_query=causal_query,
                mode=mode,
            )
            for candidate in candidates
        ]
        return BootstrapStabilityReport(
            bootstrap_mode=mode,
            config=self._config,
            summaries=summaries,
            metadata={
                "n_candidates": len(candidates),
                "query_present": causal_query is not None,
            },
        )

    def _analyze_candidate(
        self,
        candidate: PortfolioCandidate,
        state: TabularCausalDiscoveryData | TimeSeriesCausalData,
        *,
        causal_query: CausalQuery | None,
        mode: BootstrapMode,
    ) -> HypothesisStabilitySummary:
        rng = np.random.default_rng(
            self._config.seed + (crc32(candidate.hypothesis.hypothesis_id.encode("utf-8")) % 10_000)
        )
        base_edges = list(candidate.hypothesis.graph.edges)
        selection_counts = {edge_key_for_edge(edge): 0 for edge in base_edges}
        orientation_counts = {orientation_key_for_edge(edge): 0 for edge in base_edges}
        skeleton_counts = {skeleton_key_for_edge(edge): 0 for edge in base_edges}
        warnings: list[str] = []
        completed = 0
        identifiable_hits = 0
        adjustment_sets: list[frozenset[str]] = []

        for resample_idx in range(self._config.n_resamples):
            resampled_state = _resample_state(
                state,
                mode=mode,
                rng=rng,
                block_length=self._config.block_length,
            )
            rerun_params = dict(candidate.method_params)
            rerun_params["n_bootstrap"] = 0
            rerun_params["__seed__"] = int(rerun_params.get("__seed__", 0) or 0) + resample_idx + 1
            try:
                rerun_report = run_discovery_method(
                    resampled_state,
                    candidate.hypothesis.method,
                    rerun_params,
                )
            except Exception as exc:  # pragma: no cover - defensive, validated in tests
                warnings.append(f"bootstrap_run_{resample_idx}: {type(exc).__name__}: {exc}")
                continue

            completed += 1
            discovered_edges = {edge_key_for_edge(edge) for edge in rerun_report.graph.edges}
            discovered_orientations = {
                orientation_key_for_edge(edge) for edge in rerun_report.graph.edges
            }
            discovered_skeleton = {skeleton_key_for_edge(edge) for edge in rerun_report.graph.edges}

            for key in selection_counts:
                selection_counts[key] += int(key in discovered_edges)
            for key in orientation_counts:
                orientation_counts[key] += int(key in discovered_orientations)
            for key in skeleton_counts:
                skeleton_counts[key] += int(key in discovered_skeleton)

            if causal_query is None:
                continue

            graph_for_analysis, graph_warnings = _graph_for_analysis(rerun_report)
            warnings.extend(graph_warnings)
            identifiability = _evaluate_identifiability(graph_for_analysis, causal_query)
            if identifiability:
                identifiable_hits += 1
            adjustment = _evaluate_adjustment_set(graph_for_analysis, causal_query)
            if adjustment is not None:
                adjustment_sets.append(adjustment)

        edge_frequency = _finalize_frequency(selection_counts, completed)
        orientation_frequency = _finalize_frequency(orientation_counts, completed)
        skeleton_frequency = _finalize_frequency(skeleton_counts, completed)
        mean_edge = float(np.mean(list(edge_frequency.values()))) if edge_frequency else None
        identifiable_rate = (
            float(identifiable_hits / completed)
            if causal_query is not None and completed > 0
            else None
        )
        adjustment_stability = _pairwise_jaccard_mean(adjustment_sets)

        if completed < self._config.n_resamples:
            warnings.append(
                f"bootstrap_truncated: completed {completed}/{self._config.n_resamples} resamples"
            )

        return HypothesisStabilitySummary(
            hypothesis_id=candidate.hypothesis.hypothesis_id,
            edge_selection_frequency=edge_frequency,
            orientation_frequency=orientation_frequency,
            skeleton_frequency=skeleton_frequency,
            mean_edge_stability=mean_edge,
            identifiable_rate=identifiable_rate,
            adjustment_set_stability=adjustment_stability,
            completed_resamples=completed,
            warnings=warnings,
        )


def persist_bootstrap_stability_report(
    store: FileSystemCAS,
    report: BootstrapStabilityReport,
    *,
    inputs: list[InputRef] | None = None,
) -> BootstrapStabilityReportRef:
    """Persist the bootstrap stability report used to judge discovery robustness."""
    ref = store.put_json(
        report,
        PutOptions(
            kind="scientist.bootstrap_stability_report",
            media_type="application/json",
            schema=SchemaInfo(
                name=BOOTSTRAP_STABILITY_REPORT_SCHEMA_NAME,
                version=report.schema_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return BootstrapStabilityReportRef.model_validate(ref.model_dump(mode="json"))


def load_bootstrap_stability_report(
    store: FileSystemCAS,
    ref: BootstrapStabilityReportRef,
) -> BootstrapStabilityReport:
    """Load bootstrap stability report."""
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return BootstrapStabilityReport.model_validate(payload)


def _resolve_bootstrap_mode(
    state: TabularCausalDiscoveryData | TimeSeriesCausalData,
) -> BootstrapMode:
    if isinstance(state, TimeSeriesCausalData):
        return BootstrapMode.MOVING_BLOCK
    return BootstrapMode.ROW


def _resample_state(
    state: TabularCausalDiscoveryData | TimeSeriesCausalData,
    *,
    mode: BootstrapMode,
    rng: np.random.Generator,
    block_length: int | None,
) -> TabularCausalDiscoveryData | TimeSeriesCausalData:
    data = np.asarray(state.data, dtype=float)
    if data.size == 0:
        return state
    time_index = getattr(state, "time_index", None)
    sampled_time_index = None
    if mode is BootstrapMode.ROW:
        indices = rng.integers(0, data.shape[0], size=data.shape[0])
        sampled = data[indices]
        if time_index is not None:
            sampled_time_index = np.asarray(time_index)[indices]
    else:
        n_rows = data.shape[0]
        window = min(max(block_length or 5, 1), n_rows)
        n_blocks = max(1, int(np.ceil(n_rows / window)))
        max_start = max(1, n_rows - window + 1)
        starts = rng.integers(0, max_start, size=n_blocks)
        blocks = [data[start : start + window] for start in starts]
        sampled = np.concatenate(blocks, axis=0)[:n_rows]
        if time_index is not None:
            index_blocks = [np.asarray(time_index)[start : start + window] for start in starts]
            sampled_time_index = np.concatenate(index_blocks, axis=0)[:n_rows]
    update: dict[str, Any] = {"data": sampled}
    if sampled_time_index is not None:
        update["time_index"] = sampled_time_index
    return state.model_copy(update=update)


def _graph_for_analysis(
    report: Any,
) -> tuple[Any, list[str]]:
    warnings: list[str] = []
    graph = getattr(report, "resolved_graph", None) or report.graph
    if getattr(graph, "graph_type", None) is not None and getattr(
        report.graph, "graph_type", None
    ) != getattr(graph, "graph_type", None):
        warnings.append("resolved_graph_used_for_bootstrap_analysis")
    elif getattr(report.graph.graph_type, "value", "") in {"pag", "cpdag"}:
        warnings.append("structural_uncertainty_limited_bootstrap_analysis")
    return graph, warnings


def _evaluate_identifiability(
    graph: Any,
    causal_query: CausalQuery,
) -> bool:
    engine = CausalEngine()
    result = engine.identify(
        treatment=causal_query.treatment_variable,
        outcome=causal_query.outcome_variable,
        graph=graph,
    )
    return (
        isinstance(result, IdentificationResult)
        and result.status is IdentificationStatus.IDENTIFIED
    )


def _evaluate_adjustment_set(
    graph: Any,
    causal_query: CausalQuery,
) -> frozenset[str] | None:
    graph_type = getattr(getattr(graph, "graph_type", None), "value", "")
    if graph_type not in {"dag", "admg"}:
        return None
    result = optimal_adjustment_set(
        graph,
        treatment=causal_query.treatment_variable,
        outcome=causal_query.outcome_variable,
    )
    if not result.o_set_is_valid_backdoor:
        return None
    return frozenset(result.o_set)


def _finalize_frequency(
    counts: dict[str, int],
    completed: int,
) -> dict[str, float]:
    if completed <= 0:
        return {}
    return {key: float(value / completed) for key, value in counts.items()}


def _pairwise_jaccard_mean(sets: list[frozenset[str]]) -> float | None:
    if not sets:
        return None
    if len(sets) == 1:
        return 1.0
    scores: list[float] = []
    for left, right in combinations(sets, 2):
        union = left | right
        if not union:
            scores.append(1.0)
            continue
        scores.append(float(len(left & right) / len(union)))
    return float(np.mean(scores)) if scores else None


__all__ = [
    "BOOTSTRAP_STABILITY_REPORT_SCHEMA_NAME",
    "BootstrapMode",
    "BootstrapStabilityAnalyzer",
    "BootstrapStabilityConfig",
    "BootstrapStabilityReport",
    "HypothesisStabilitySummary",
    "load_bootstrap_stability_report",
    "persist_bootstrap_stability_report",
]
