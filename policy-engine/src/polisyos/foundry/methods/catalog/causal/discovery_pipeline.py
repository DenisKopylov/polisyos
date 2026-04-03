"""
Track 3 — Task 1.3: Unified Constraint Discovery Pipeline

Runs PC / FCI / GES / DAGMA / PCMCI based on data characteristics and
combines their outputs into a single PAG via weighted edge-mark voting.
The resulting CausalGraphModel (graph_type=PAG) is ready for id_algorithm().
"""
from __future__ import annotations

import concurrent.futures
import dataclasses
import time
from collections import defaultdict
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
from polisyos.foundry.methods.catalog.causal.protocols import (
    TabularCausalDiscoveryData,
    TimeSeriesCausalData,
    UnifiedDiscoveryData,
)
from polisyos.ir.analytics.causal_discovery import (
    CausalDiscoveryReport,
    DataCharacteristics,
    DataType,
    DimensionRegime,
    DiscoveryPipelineReport,
    EdgeAgreement,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    EdgeSource,
    GraphType,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_MARK_VOTE_ORDER: list[EdgeMark] = [EdgeMark.TAIL, EdgeMark.ARROW, EdgeMark.CIRCLE]


def _detect_mixed_types(data: np.ndarray) -> bool:
    """Return True if data appears to contain discrete columns alongside continuous ones."""
    n_continuous = 0
    n_discrete = 0
    for col_idx in range(data.shape[1]):
        col = data[:, col_idx]
        unique_vals = np.unique(col)
        if len(unique_vals) <= 10:
            n_discrete += 1
        else:
            n_continuous += 1
    return n_continuous > 0 and n_discrete > 0


def _suspect_latent_confounders(data: np.ndarray) -> bool:
    """
    Heuristic: large mean absolute partial-residual correlation suggests
    unexplained shared variance, pointing to likely hidden common causes.
    """
    n_vars = data.shape[1]
    if n_vars < 3:
        return False
    try:
        corr = np.corrcoef(data.T)
        # Paranoia: clip to valid correlation range
        corr = np.clip(corr, -1.0 + 1e-8, 1.0 - 1e-8)
        try:
            inv_corr = np.linalg.inv(corr)
        except np.linalg.LinAlgError:
            return False
        # Partial correlations from inverse
        d = np.sqrt(np.abs(np.diag(inv_corr)))
        d = np.where(d < 1e-12, 1e-12, d)
        partial = -inv_corr / np.outer(d, d)
        np.fill_diagonal(partial, 0.0)
        # Many high partial correlations after partialing out all others
        # suggest systematic hidden structure
        return float(np.mean(np.abs(partial) > 0.3)) > 0.2
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# DataCharacterizer
# ---------------------------------------------------------------------------


class DataCharacterizer:
    """Inspects raw data to determine appropriate discovery strategy."""

    @staticmethod
    def characterize(
        data: np.ndarray,
        variable_names: list[str],
        *,
        time_series: bool = False,
        max_lag: int | None = None,
    ) -> DataCharacteristics:
        n_samples, n_vars = data.shape

        if n_vars <= 20:
            dim_regime = DimensionRegime.LOW_DIM
        elif n_vars <= 50:
            dim_regime = DimensionRegime.MED_DIM
        else:
            dim_regime = DimensionRegime.HIGH_DIM

        has_mixed = _detect_mixed_types(data)

        # Estimated edge density via correlation threshold
        corr = np.abs(np.corrcoef(data.T))
        mask = np.ones((n_vars, n_vars), dtype=bool)
        np.fill_diagonal(mask, False)
        estimated_density = float(np.mean(corr[mask] > 0.1)) if n_vars > 1 else 0.0
        estimated_density = max(0.0, min(1.0, estimated_density))

        suspected_latent = _suspect_latent_confounders(data)

        return DataCharacteristics(
            data_type=DataType.TIME_SERIES if time_series else DataType.CROSS_SECTIONAL,
            n_samples=n_samples,
            n_variables=n_vars,
            dimension_regime=dim_regime,
            estimated_density=estimated_density,
            has_mixed_types=has_mixed,
            suspected_latent_confounders=suspected_latent,
            is_stationary=None if not time_series else True,
            max_lag=max_lag,
        )


# ---------------------------------------------------------------------------
# AlgorithmSelector
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class DiscoveryAlgorithmSpec:
    """Discovery algorithm spec data model."""
    name: str    # "pc" | "fci" | "ges" | "dagma" | "pcmci"
    weight: float
    required: bool


class AlgorithmSelector:
    """Selects discovery algorithms and assigns consensus weights."""

    @staticmethod
    def select(
        dc: DataCharacteristics,
        force_algorithms: list[str] | None = None,
    ) -> list[DiscoveryAlgorithmSpec]:
        if force_algorithms:
            w = 1.0 / len(force_algorithms)
            return [DiscoveryAlgorithmSpec(name=a, weight=w, required=True) for a in force_algorithms]

        if dc.data_type == DataType.TIME_SERIES:
            return [DiscoveryAlgorithmSpec("pcmci", weight=1.0, required=True)]

        # Cross-sectional routing
        if dc.dimension_regime == DimensionRegime.HIGH_DIM:
            specs: list[DiscoveryAlgorithmSpec] = [
                DiscoveryAlgorithmSpec("dagma", weight=0.7, required=True),
            ]
            if dc.n_samples > 2 * dc.n_variables:
                specs.append(DiscoveryAlgorithmSpec("pc", weight=0.3, required=False))
            return specs

        # Low / med dim: PC + GES + optional FCI
        specs = [
            DiscoveryAlgorithmSpec("pc", weight=0.35, required=True),
            DiscoveryAlgorithmSpec("ges", weight=0.35, required=True),
        ]
        if dc.suspected_latent_confounders:
            specs.append(DiscoveryAlgorithmSpec("fci", weight=0.30, required=True))
        else:
            specs.append(DiscoveryAlgorithmSpec("fci", weight=0.15, required=False))
        return specs


# ---------------------------------------------------------------------------
# Algorithm runner helpers
# ---------------------------------------------------------------------------


def _run_single_algorithm(
    algo: str,
    state: UnifiedDiscoveryData,
    dc: DataCharacteristics,
    params: Mapping[str, Any],
) -> CausalDiscoveryReport | None:
    """Run one discovery algorithm and return its CausalDiscoveryReport, or None on failure."""
    significance_level = float(params.get("significance_level", 0.05))
    n_bootstrap = int(params.get("n_bootstrap", 50))
    timeout_seconds = float(params.get("timeout_seconds", 120.0))
    ci_backend = str(params.get("ci_backend", "auto"))

    try:
        if algo == "pcmci":
            from polisyos.foundry.methods.catalog.causal.pcmci_discovery import PCMCIDiscovery

            ts_state = TimeSeriesCausalData(data=state.data, variable_names=state.variable_names)
            result = PCMCIDiscovery.pure_step(
                ts_state,
                {
                    "max_lag": dc.max_lag or 2,
                    "significance_level": significance_level,
                    "discovery_ci_backend": ci_backend,
                    "n_bootstrap": n_bootstrap,
                    "timeout_seconds": timeout_seconds,
                },
            )
            return result["report"]

        tab_state = TabularCausalDiscoveryData(data=state.data, variable_names=state.variable_names)

        if algo in ("pc", "fci", "ges"):
            from polisyos.foundry.methods.catalog.causal.constraint_discovery import (
                _run_constraint_discovery,
            )

            result = _run_constraint_discovery(
                state=tab_state,
                params={
                    "significance_level": significance_level,
                    "discovery_ci_backend": ci_backend,
                    "discovery_scale_backend": "classic",
                    "algebraic_blocks": params.get("algebraic_blocks", []),
                    "n_bootstrap": n_bootstrap,
                    "timeout_seconds": timeout_seconds,
                },
                algorithm=algo,
            )
            return result["report"]

        if algo == "dagma":
            from polisyos.foundry.methods.catalog.causal.dagma_discovery import run_dagma_discovery

            result = run_dagma_discovery(
                state=tab_state,
                params={
                    "significance_level": significance_level,
                    "algebraic_blocks": params.get("algebraic_blocks", []),
                    "n_bootstrap": n_bootstrap,
                    "timeout_seconds": timeout_seconds,
                },
            )
            return result["report"]

    except Exception as exc:  # noqa: BLE001
        # Return a minimal fallback report so the pipeline can continue
        fallback_report = CausalDiscoveryReport(
            method=algo,
            graph=CausalGraphModel(
                graph_type=GraphType.PAG,
                nodes=state.variable_names,
                edges=[],
                discovery_method=algo,
            ),
            warnings=[f"algorithm_failed: {algo}: {exc!r}"],
        )
        if not bool(params.get("is_time_series", False)):
            from polisyos.foundry.methods.catalog.causal.constraint_discovery import (
                _stamp_algebraic_constraint_audit,
                _validate_algebraic_blocks,
            )

            fallback_report = _stamp_algebraic_constraint_audit(
                fallback_report,
                data=np.asarray(state.data),
                variable_names=list(state.variable_names),
                significance_level=float(params.get("significance_level", 0.05) or 0.05),
                seed=int(params.get("__seed__", 0) or 0),
                algebraic_blocks=_validate_algebraic_blocks(params.get("algebraic_blocks")),
                degraded_reason="algebraic_audit_degraded:algorithm_failed_before_audit",
            )
        return fallback_report

    return None


def _run_algorithms_parallel(
    state: UnifiedDiscoveryData,
    dc: DataCharacteristics,
    algo_specs: list[DiscoveryAlgorithmSpec],
    params: Mapping[str, Any],
) -> tuple[list[CausalDiscoveryReport], dict[str, float]]:
    """Run algorithm specs concurrently; return (results, weights_used)."""
    results: list[CausalDiscoveryReport] = []
    weights_used: dict[str, float] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(algo_specs)) as executor:
        futures = {
            executor.submit(_run_single_algorithm, spec.name, state, dc, params): spec
            for spec in algo_specs
        }
        for future, spec in futures.items():
            try:
                report = future.result(timeout=float(params.get("timeout_seconds", 120.0)) + 30.0)
                if report is not None:
                    results.append(report)
                    weights_used[spec.name] = spec.weight
            except Exception as exc:  # noqa: BLE001
                if spec.required:
                    fallback = CausalDiscoveryReport(
                        method=spec.name,
                        graph=CausalGraphModel(
                            graph_type=GraphType.PAG,
                            nodes=state.variable_names,
                            edges=[],
                            discovery_method=spec.name,
                        ),
                        warnings=[f"executor_failed: {spec.name}: {exc!r}"],
                    )
                    results.append(fallback)
                    weights_used[spec.name] = spec.weight

    # Normalize weights to sum to 1.0 based on algorithms that actually ran
    total_w = sum(weights_used.values())
    if total_w > 0:
        weights_used = {k: v / total_w for k, v in weights_used.items()}

    return results, weights_used


# ---------------------------------------------------------------------------
# PAG Consensus builder
# ---------------------------------------------------------------------------


def _canonical_edge_pair(src: str, dst: str) -> tuple[str, str]:
    """Return (lo, hi) canonical ordering for undirected pair lookup."""
    return (src, dst) if src < dst else (dst, src)


def _build_consensus_pag(
    results: list[CausalDiscoveryReport],
    algorithm_weights: dict[str, float],
    variable_names: list[str],
    *,
    min_presence_score: float = 0.3,
) -> tuple[CausalGraphModel, list[EdgeAgreement], dict[str, float], list[str], list[str], list[CausalEdge]]:
    """
    Combine multiple discovery reports into a single PAG via weighted edge-mark voting.

    Returns
    -------
    (unified_pag, edge_agreements, skeleton_agreement, pag_validity_violations,
     orientation_warnings, temporal_edges)

    Four-phase process
    ------------------
    Phase 0: Temporal segregation — PCMCI lag>0 edges go to temporal_edges, not the PAG.
    Phase 1: Skeleton consensus — weighted presence scoring per edge pair, with CPDAG
             upcast to PAG form before voting.
    Phase 2: V-structure detection — unshielded triples voted collider/non-collider.
    Phase 3: Mark consensus — weighted voting for per-endpoint marks.
    Phase 4: PAG completion — Zhang R1-R3 orientation rules + validity check.

    Voting scheme (Phase 3)
    -----------------------
    For each ordered pair (A, B) reported as an edge by at least one algorithm:
      - presence_score  = sum of weights of algorithms reporting (A,B) or (B,A)
      - mark_src vote   = weighted tally of src marks (TAIL / ARROW / CIRCLE)
      - mark_dst vote   = weighted tally of dst marks
      - Reverse edge (B,A) contributes swapped marks, pushing conflicts toward CIRCLE.
      - If presence_score < min_presence_score: omit
      - Winning mark = mode; if winning weight < 0.5 of presence_score: CIRCLE
    """
    from polisyos.foundry.methods.catalog.causal.pag_completion import (
        apply_pag_orientation_rules,
        cpdag_to_pag,
        extract_unshielded_triples,
        validate_pag,
    )

    # ------------------------------------------------------------------
    # Phase 0: Temporal segregation
    # PCMCI edges with lag>0 are moved to temporal_edges; only lag=0/None
    # contemporaneous edges enter the consensus.
    # ------------------------------------------------------------------
    temporal_edges: list[CausalEdge] = []
    processed_results: list[CausalDiscoveryReport] = []

    for report in results:
        if report.method == "pcmci+":
            lag_edges = [e for e in report.graph.edges if e.lag is not None and e.lag > 0]
            contemp_edges = [
                e for e in report.graph.edges if e.lag is None or e.lag == 0
            ]
            temporal_edges.extend(lag_edges)
            if lag_edges or contemp_edges:
                contemp_graph = CausalGraphModel(
                    schema_version=report.graph.schema_version,
                    graph_type=report.graph.graph_type,
                    nodes=list(report.graph.nodes),
                    edges=contemp_edges,
                    discovery_method=report.graph.discovery_method,
                    pag_identification_policy=report.graph.pag_identification_policy,
                    metadata=dict(report.graph.metadata),
                )
                processed_results.append(
                    CausalDiscoveryReport(
                        method=report.method,
                        graph=contemp_graph,
                        bootstrap_stability=report.bootstrap_stability,
                        n_bootstrap=report.n_bootstrap,
                        significance_level=report.significance_level,
                        computation_time_seconds=report.computation_time_seconds,
                        warnings=report.warnings,
                        metadata=report.metadata,
                    )
                )
            else:
                processed_results.append(report)
        else:
            processed_results.append(report)

    # ------------------------------------------------------------------
    # Phase 1: Skeleton consensus — weighted presence scoring
    # CPDAGs are upcasted to PAG form before mark votes are accumulated.
    # ------------------------------------------------------------------
    votes: dict[tuple[str, str], dict[str, Any]] = {}

    def _add_vote(
        src: str,
        dst: str,
        mark_src: EdgeMark,
        mark_dst: EdgeMark,
        weight: float,
        algo: str,
    ) -> None:
        key = (src, dst)
        if key not in votes:
            votes[key] = {
                "presence": 0.0,
                "src_marks": defaultdict(float),
                "dst_marks": defaultdict(float),
                "algos": [],
            }
        entry = votes[key]
        entry["presence"] += weight
        entry["src_marks"][mark_src] += weight
        entry["dst_marks"][mark_dst] += weight
        if algo not in entry["algos"]:
            entry["algos"].append(algo)

    for report in processed_results:
        algo = report.method
        weight = algorithm_weights.get(algo, 0.0)
        if weight == 0.0:
            continue

        # Upcast CPDAG → PAG before voting so marks are comparable
        report_graph = (
            cpdag_to_pag(report.graph)
            if report.graph.graph_type is GraphType.CPDAG
            else report.graph
        )

        for edge in report_graph.edges:
            mark_s = edge.mark_src
            mark_d = edge.mark_dst

            _add_vote(edge.src, edge.dst, mark_s, mark_d, weight, algo)

            # For symmetric/uncertain edges also add reverse so direction conflicts
            # naturally push toward CIRCLE
            if mark_s in (EdgeMark.TAIL, EdgeMark.CIRCLE) and mark_d in (
                EdgeMark.TAIL,
                EdgeMark.CIRCLE,
            ):
                _add_vote(edge.dst, edge.src, mark_d, mark_s, weight, algo)

    # Deduplicate: for pairs (A,B) and (B,A) both present, keep the one with
    # higher presence and merge marks.
    canonical_votes: dict[tuple[str, str], dict[str, Any]] = {}

    for (src, dst), entry in votes.items():
        rev = (dst, src)
        if rev in votes and rev not in canonical_votes and (src, dst) not in canonical_votes:
            rev_entry = votes[rev]
            if entry["presence"] >= rev_entry["presence"]:
                fwd = (src, dst)
            else:
                fwd = rev
                entry, rev_entry = rev_entry, entry

            merged_presence = max(entry["presence"], rev_entry["presence"])
            src_marks: dict[EdgeMark, float] = defaultdict(float, entry["src_marks"])
            for m, w in rev_entry["dst_marks"].items():
                src_marks[m] += w
            dst_marks: dict[EdgeMark, float] = defaultdict(float, entry["dst_marks"])
            for m, w in rev_entry["src_marks"].items():
                dst_marks[m] += w

            merged_algos = list(set(entry["algos"] + rev_entry["algos"]))
            canonical_votes[fwd] = {
                "presence": merged_presence,
                "src_marks": src_marks,
                "dst_marks": dst_marks,
                "algos": merged_algos,
            }
        elif (src, dst) not in canonical_votes and rev not in canonical_votes:
            canonical_votes[(src, dst)] = entry

    # Collect skeleton_agreement: presence score per edge pair that met threshold
    skeleton_agreement: dict[str, float] = {
        f"{src}|{dst}": round(entry["presence"], 4)
        for (src, dst), entry in canonical_votes.items()
        if entry["presence"] >= min_presence_score
    }

    # ------------------------------------------------------------------
    # Phase 2: V-structure detection on the consensus skeleton
    # For each unshielded triple (α, β, γ): tally collider vs non-collider
    # votes; force β-ends to ARROW if majority says collider.
    # ------------------------------------------------------------------
    skeleton_edges: list[CausalEdge] = [
        CausalEdge(
            src=src,
            dst=dst,
            mark_src=EdgeMark.CIRCLE,
            mark_dst=EdgeMark.CIRCLE,
            sources=[EdgeSource.DATA],
        )
        for (src, dst), entry in canonical_votes.items()
        if entry["presence"] >= min_presence_score
    ]
    skeleton_graph = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=variable_names,
        edges=skeleton_edges,
    )
    unshielded_triples = extract_unshielded_triples(skeleton_graph)

    # For each unshielded triple, vote collider vs non-collider
    for alpha, beta, gamma in unshielded_triples:
        collider_weight = 0.0
        noncollider_weight = 0.0

        for report in processed_results:
            w = algorithm_weights.get(report.method, 0.0)
            if w == 0.0:
                continue
            # Use the upcasted graph for mark queries
            report_graph = (
                cpdag_to_pag(report.graph)
                if report.graph.graph_type is GraphType.CPDAG
                else report.graph
            )
            # Find mark at beta-end of alpha-beta edge
            beta_mark_from_alpha: EdgeMark | None = None
            for e in report_graph.edges:
                if e.src == alpha and e.dst == beta:
                    beta_mark_from_alpha = e.mark_dst
                    break
                if e.src == beta and e.dst == alpha:
                    beta_mark_from_alpha = e.mark_src
                    break

            # Find mark at beta-end of beta-gamma edge
            beta_mark_from_gamma: EdgeMark | None = None
            for e in report_graph.edges:
                if e.src == beta and e.dst == gamma:
                    beta_mark_from_gamma = e.mark_src
                    break
                if e.src == gamma and e.dst == beta:
                    beta_mark_from_gamma = e.mark_dst
                    break

            if beta_mark_from_alpha is None or beta_mark_from_gamma is None:
                continue

            if (
                beta_mark_from_alpha is EdgeMark.ARROW
                and beta_mark_from_gamma is EdgeMark.ARROW
            ):
                collider_weight += w
            else:
                noncollider_weight += w

        total = collider_weight + noncollider_weight
        if total > 0 and collider_weight / total > 0.5:
            # Force collider at beta: set β-end marks to ARROW for both edges
            key_ab = (alpha, beta)
            key_ba = (beta, alpha)
            key_bg = (beta, gamma)
            key_gb = (gamma, beta)

            if key_ab in canonical_votes:
                canonical_votes[key_ab]["dst_marks"] = defaultdict(
                    float, {EdgeMark.ARROW: 1.0}
                )
                canonical_votes[key_ab]["src_marks"] = defaultdict(
                    float, {EdgeMark.TAIL: 1.0}
                )
            elif key_ba in canonical_votes:
                canonical_votes[key_ba]["src_marks"] = defaultdict(
                    float, {EdgeMark.ARROW: 1.0}
                )
                canonical_votes[key_ba]["dst_marks"] = defaultdict(
                    float, {EdgeMark.TAIL: 1.0}
                )

            if key_bg in canonical_votes:
                canonical_votes[key_bg]["src_marks"] = defaultdict(
                    float, {EdgeMark.TAIL: 1.0}
                )
                canonical_votes[key_bg]["dst_marks"] = defaultdict(
                    float, {EdgeMark.ARROW: 1.0}
                )
                # Fix: collider means β-end of β-γ is ARROW (mark_src of (β,γ) = TAIL, mark_dst = ARROW)
                # Actually: collider means mark at β in β-γ edge: if stored as (β→γ), mark_src is β-end
                # We want the mark at γ's end to go ARROW, and β's end to be TAIL (non-collider at γ)
                # Wait: collider AT β means both incoming arrows point TO β.
                # α→β: mark at β-end of α-β = ARROW
                # γ→β: mark at β-end of γ-β = ARROW
                # So for edge (β, γ) we want: β-end (mark_src) = from β perspective...
                # Let me reconsider: edge stored as (β,γ): mark_src is at β-end, mark_dst is at γ-end
                # We want: γ→β means mark at β-end is ARROW and γ-end is TAIL
                # So for the (β,γ) edge: mark_src (β-end)=ARROW, mark_dst (γ-end)=TAIL means γ→β
                canonical_votes[key_bg]["src_marks"] = defaultdict(
                    float, {EdgeMark.ARROW: 1.0}
                )
                canonical_votes[key_bg]["dst_marks"] = defaultdict(
                    float, {EdgeMark.TAIL: 1.0}
                )
            elif key_gb in canonical_votes:
                # Edge stored as (γ, β): mark_src is at γ-end, mark_dst is at β-end
                # γ→β collider at β: mark_dst (β-end) = ARROW, mark_src (γ-end) = TAIL
                canonical_votes[key_gb]["dst_marks"] = defaultdict(
                    float, {EdgeMark.ARROW: 1.0}
                )
                canonical_votes[key_gb]["src_marks"] = defaultdict(
                    float, {EdgeMark.TAIL: 1.0}
                )

    # ------------------------------------------------------------------
    # Phase 3: Mark consensus — derive final marks from vote tallies
    # ------------------------------------------------------------------
    def _vote_mark(marks: dict[EdgeMark, float], total_presence: float) -> EdgeMark:
        if not marks:
            return EdgeMark.CIRCLE
        best_mark = max(marks, key=lambda m: marks[m])
        best_weight = marks[best_mark]
        if best_weight >= 0.5 * total_presence:
            return best_mark
        return EdgeMark.CIRCLE

    output_edges: list[CausalEdge] = []
    edge_agreements: list[EdgeAgreement] = []

    for (src, dst), entry in canonical_votes.items():
        presence = entry["presence"]
        if presence < min_presence_score:
            continue

        mark_s = _vote_mark(entry["src_marks"], presence)
        mark_d = _vote_mark(entry["dst_marks"], presence)

        winning_src_w = entry["src_marks"].get(mark_s, 0.0)
        winning_dst_w = entry["dst_marks"].get(mark_d, 0.0)
        orientation_confidence = (
            (winning_src_w + winning_dst_w) / (2.0 * presence) if presence > 0 else 0.0
        )

        edge_stabilities: list[float] = []
        for report in processed_results:
            algo = report.method
            if algo not in entry["algos"]:
                continue
            for boot_edge in report.graph.edges:
                if boot_edge.src == src and boot_edge.dst == dst:
                    key = f"{src}|{boot_edge.mark_src.value}>{boot_edge.mark_dst.value}|{dst}"
                    stab = report.bootstrap_stability.get(key)
                    if stab is not None:
                        edge_stabilities.append(stab)

        avg_stability = float(np.mean(edge_stabilities)) if edge_stabilities else None

        edge_meta: dict[str, Any] = {
            "presence_score": round(presence, 4),
            "orientation_confidence": round(orientation_confidence, 4),
            "contributing_algorithms": sorted(entry["algos"]),
        }
        if avg_stability is not None:
            edge_meta["bootstrap_stability"] = round(avg_stability, 4)

        output_edges.append(
            CausalEdge(
                src=src,
                dst=dst,
                mark_src=mark_s,
                mark_dst=mark_d,
                sources=[EdgeSource.DATA],
                data_confidence=min(1.0, presence),
                combined_confidence=min(1.0, presence * orientation_confidence),
                metadata=edge_meta,
            )
        )

        edge_agreements.append(
            EdgeAgreement(
                edge_key=f"{src}|{mark_s.value}>{mark_d.value}|{dst}",
                presence_score=round(presence, 4),
                orientation_confidence=round(orientation_confidence, 4),
                mark_src=mark_s.value,
                mark_dst=mark_d.value,
                contributing_algorithms=sorted(entry["algos"]),
            )
        )

    assembled_pag = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=variable_names,
        edges=output_edges,
        discovery_method="unified_consensus_pag",
        metadata={
            "n_algorithms": len(results),
            "min_presence_score": min_presence_score,
        },
    )

    # ------------------------------------------------------------------
    # Phase 4: PAG orientation rules + validity check
    # ------------------------------------------------------------------
    oriented_pag, orientation_warnings = apply_pag_orientation_rules(
        assembled_pag, max_iter=10
    )
    violations = validate_pag(oriented_pag)

    return (
        oriented_pag,
        edge_agreements,
        skeleton_agreement,
        violations,
        orientation_warnings,
        temporal_edges,
    )


# ---------------------------------------------------------------------------
# Optional reconciliation step
# ---------------------------------------------------------------------------


def _maybe_reconcile(
    pag: CausalGraphModel,
    state: UnifiedDiscoveryData,
    params: Mapping[str, Any],
) -> CausalGraphModel:
    """If literature_prior or llm_hints are provided, run graph reconciliation."""
    if state.literature_prior is None and not state.llm_hints:
        return pag

    try:
        from polisyos.foundry.methods.catalog.causal.graph_reconciliation import ReconcileCausalGraph
        from polisyos.foundry.methods.catalog.causal.protocols import GraphReconciliationData

        recon_data = GraphReconciliationData(
            data_graph=pag,
            literature_prior=state.literature_prior,
            llm_hints=list(state.llm_hints),
        )
        result = ReconcileCausalGraph.pure_step(recon_data, {})
        reconciled: CausalGraphModel = result["reconciled_graph"]
        # ReconcileCausalGraph may return a DAG; lift back to PAG type
        if reconciled.graph_type != GraphType.PAG:
            reconciled = CausalGraphModel(
                graph_type=GraphType.PAG,
                nodes=reconciled.nodes,
                edges=reconciled.edges,
                discovery_method=reconciled.discovery_method,
                skg_version_id=reconciled.skg_version_id,
                metadata=reconciled.metadata,
            )
        return reconciled
    except Exception:  # noqa: BLE001
        return pag


def _pipeline_dispute_summary(
    reports: list[CausalDiscoveryReport],
) -> dict[str, Any]:
    support: dict[tuple[str, str], dict[str, set[str]]] = {}
    for report in reports:
        for edge in report.graph.edges:
            skeleton = tuple(sorted((edge.src, edge.dst)))
            bucket = support.setdefault(
                skeleton,
                {"directions": set(), "orientations": set()},
            )
            bucket["directions"].add(f"{edge.src}->{edge.dst}")
            bucket["orientations"].add(
                f"{edge.src}|{edge.mark_src.value}>{edge.mark_dst.value}|{edge.dst}"
            )

    disputed_edges = sorted(
        f"{src}--{dst}"
        for (src, dst), bucket in support.items()
        if len(bucket["directions"]) > 1 or len(bucket["orientations"]) > 1
    )
    total_skeletons = len(support)
    disputed_edge_fraction = (
        float(len(disputed_edges) / total_skeletons)
        if total_skeletons > 0
        else 0.0
    )
    return {
        "disputed_edges": disputed_edges,
        "disputed_edge_count": len(disputed_edges),
        "disputed_edge_fraction": round(disputed_edge_fraction, 4),
    }


def _pipeline_algebraic_summary(
    reports: list[CausalDiscoveryReport],
) -> dict[str, Any]:
    violated_by_family: dict[str, int] = defaultdict(int)
    severity_by_method: dict[str, str] = {}
    families_with_blockers: set[str] = set()
    reports_with_constraints = 0
    blocker_reports = 0

    for report in reports:
        algebraic = report.algebraic_constraints
        if algebraic is None:
            continue
        reports_with_constraints += 1
        severity_by_method[report.method] = algebraic.severity
        for family, count in algebraic.violated_by_family.items():
            violated_by_family[str(family)] += int(count)
        if algebraic.severity == "blocker":
            blocker_reports += 1
            if algebraic.violated_by_family:
                families_with_blockers.update(
                    family
                    for family, count in algebraic.violated_by_family.items()
                    if int(count) > 0
                )
            else:
                families_with_blockers.update(
                    family.value if hasattr(family, "value") else str(family)
                    for family in algebraic.families_run
                )

    return {
        "algebraic_violation_summary": {
            "reports_with_constraints": reports_with_constraints,
            "blocker_reports": blocker_reports,
            "violated_by_family": dict(sorted(violated_by_family.items())),
            "severity_by_method": severity_by_method,
        },
        "families_with_blockers": sorted(families_with_blockers),
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def _run_unified_discovery(
    state: UnifiedDiscoveryData,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    t0 = time.perf_counter()
    warnings: list[str] = []

    # 1. Characterize data
    dc = DataCharacterizer.characterize(
        state.data,
        state.variable_names,
        time_series=bool(params.get("is_time_series", False)),
        max_lag=params.get("max_lag"),
    )

    # 2. Select algorithms
    force_algos = params.get("force_algorithms")
    if isinstance(force_algos, str):
        force_algos = [a.strip() for a in force_algos.split(",") if a.strip()]
    algo_specs = AlgorithmSelector.select(dc, force_algorithms=force_algos or None)

    # 3. Run algorithms in parallel
    individual_results, algorithm_weights = _run_algorithms_parallel(
        state=state, dc=dc, algo_specs=algo_specs, params=params
    )

    # Collect warnings from individual runs
    for r in individual_results:
        warnings.extend(r.warnings)

    if not individual_results:
        # All algorithms failed – return empty PAG
        empty_pag = CausalGraphModel(
            graph_type=GraphType.PAG,
            nodes=state.variable_names,
            edges=[],
            discovery_method="unified_consensus_pag_empty",
        )
        report = DiscoveryPipelineReport(
            unified_pag=empty_pag,
            individual_results=[],
            algorithm_weights={},
            edge_agreements=[],
            data_characteristics=dc,
            n_algorithms_run=0,
            warnings=warnings + ["all_algorithms_failed"],
            computation_time_seconds=time.perf_counter() - t0,
            metadata={
                "disputed_edges": [],
                "disputed_edge_count": 0,
                "disputed_edge_fraction": 0.0,
                "algebraic_violation_summary": {
                    "reports_with_constraints": 0,
                    "blocker_reports": 0,
                    "violated_by_family": {},
                    "severity_by_method": {},
                },
                "families_with_blockers": [],
            },
        )
        return {"report": report, "__determinism_tier__": DeterminismTier.STATISTICAL}

    # 4. Build consensus PAG (4-phase: temporal segregation, skeleton, v-structures, completion)
    min_presence_score = float(params.get("min_presence_score", 0.3))
    (
        unified_pag,
        edge_agreements,
        skeleton_agreement,
        pag_validity_violations,
        orientation_warnings,
        temporal_edges,
    ) = _build_consensus_pag(
        individual_results,
        algorithm_weights,
        state.variable_names,
        min_presence_score=min_presence_score,
    )
    warnings.extend(orientation_warnings)

    # Build temporal_dag from PCMCI lag>0 edges (if any)
    temporal_dag: CausalGraphModel | None = None
    if temporal_edges:
        try:
            temporal_dag = CausalGraphModel(
                graph_type=GraphType.DAG,
                nodes=state.variable_names,
                edges=temporal_edges,
                discovery_method="pcmci_temporal_dag",
            )
        except Exception:  # noqa: BLE001
            temporal_dag = None
            warnings.append("temporal_dag_construction_failed: could not build temporal DAG from PCMCI lag edges")

    # 5. Optional reconciliation with priors
    unified_pag = _maybe_reconcile(unified_pag, state, params)

    # 5b. Re-validate PAG after reconciliation (prior injection may introduce
    # orientation conflicts that violate PAG invariants — e.g. new v-structures
    # conflicting with existing orientations).
    from polisyos.foundry.methods.catalog.causal.pag_completion import validate_pag as _validate_pag
    post_reconcile_violations = _validate_pag(unified_pag)
    if post_reconcile_violations:
        pag_validity_violations.extend(post_reconcile_violations)
        warnings.extend(
            f"post_reconcile_violation: {v}" for v in post_reconcile_violations
        )

    pipeline_metadata = {
        **_pipeline_dispute_summary(individual_results),
        **_pipeline_algebraic_summary(individual_results),
    }

    report = DiscoveryPipelineReport(
        unified_pag=unified_pag,
        individual_results=individual_results,
        algorithm_weights=algorithm_weights,
        edge_agreements=edge_agreements,
        skeleton_agreement=skeleton_agreement,
        temporal_dag=temporal_dag,
        pag_validity_violations=pag_validity_violations,
        data_characteristics=dc,
        n_algorithms_run=len(individual_results),
        warnings=warnings,
        computation_time_seconds=time.perf_counter() - t0,
        metadata=pipeline_metadata,
    )
    return {"report": report, "__determinism_tier__": DeterminismTier.STATISTICAL}


# ---------------------------------------------------------------------------
# FoundryMethod
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.discovery",
    version="1.1.0",
    tags={"causal", "discovery", "pipeline", "pag", "unified"},
)
class UnifiedCausalDiscovery:
    """
    Unified causal discovery pipeline (Track 3, Task 1.3).

    Auto-selects PC / FCI / GES / DAGMA / PCMCI based on data characteristics,
    runs the selected algorithms concurrently, and combines their outputs into a
    single PAG via weighted edge-mark voting.  The unified PAG is ready for
    consumption by id_algorithm().
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="unified_causal_discovery",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="discovery_data",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("observations", "rows"),
                    shape=("n_obs", "n_vars"),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="discovery_pipeline_report",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("report", "json"),
                )
            }
        ),
        parameters=(
            ParameterSpec(name="significance_level", default=0.05),
            ParameterSpec(name="n_bootstrap", default=50),
            ParameterSpec(name="force_algorithms", default=None),
            ParameterSpec(name="min_presence_score", default=0.3),
            ParameterSpec(name="algebraic_blocks", default=None),
            ParameterSpec(name="ci_backend", default="auto"),
            ParameterSpec(name="timeout_seconds", default=120),
            ParameterSpec(name="is_time_series", default=False),
            ParameterSpec(name="max_lag", default=None),
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
            "Unified causal discovery pipeline: auto-selects PC/FCI/GES/DAGMA/PCMCI "
            "based on data characteristics (dimensionality, sample size, suspected latents, "
            "time-series flag) and combines outputs into a PAG via weighted edge-mark voting "
            "with bootstrap stability scores. Output suitable for id_algorithm()."
        ),
        tags=frozenset({"causal", "discovery", "pipeline", "pag", "unified"}),
        assumptions={
            "faithfulness": "Faithfulness of the data-generating process.",
            "markov": "Causal Markov condition holds.",
            "acyclicity": "Acyclicity (or lagged acyclicity for time-series).",
        },
        citations=(
            "Spirtes, P., Glymour, C. & Scheines, R. (2000). Causation, Prediction, and Search. MIT Press.",
            "Chickering, D. (2002). Optimal structure identification with greedy search. JMLR, 3, 507-554.",
        ),
        when_to_use=(
            "Use when you want a single PAG that pools evidence from multiple discovery "
            "algorithms. Particularly useful when you are uncertain which algorithm is "
            "best suited for your data. Output is ready for id_algorithm() with any "
            "pag_identification_policy."
        ),
        when_not_to_use=(
            "When you have strong domain knowledge about the correct algorithm, "
            "prefer calling that algorithm directly to avoid unnecessary computation."
        ),
        typical_min_obs=200,
        output_interpretation=(
            "Returns a weighted PAG (partial ancestral graph) with bootstrap stability "
            "scores on each edge mark.  Edges with stability > 0.5 are robust across "
            "algorithms.  Feed the PAG to id_algorithm() for causal identification."
        ),
    )

    @staticmethod
    def pure_step(state: UnifiedDiscoveryData, params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, UnifiedDiscoveryData):
            state = UnifiedDiscoveryData.model_validate(state)
        return _run_unified_discovery(state=state, params=params)


__all__ = [
    "DataCharacterizer",
    "AlgorithmSelector",
    "DiscoveryAlgorithmSpec",
    "UnifiedCausalDiscovery",
    "_build_consensus_pag",
]
