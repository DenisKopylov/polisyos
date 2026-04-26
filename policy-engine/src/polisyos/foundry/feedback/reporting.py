"""Builders for fixed-point multiplicity report payloads."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from polisyos.core.contracts.foundry import (
    BasinEstimate,
    BifurcationCandidate,
    EquilibriumBranch,
    EquilibriumCandidate,
    EquilibriumMultiplicityDiagnostics,
    EquilibriumMultiplicityProvenance,
    EquilibriumMultiplicityReport,
    EquilibriumSearchProtocol,
    UnresolvedEquilibriumStart,
)

from .fixed_point import SolveOutcome


def build_search_protocol(
    *,
    mode: str,
    start_domain: dict[str, object],
    n_attempts: int,
    continuation_parameter: str | None,
    continuation_grid: list[float],
    merge_tol: float | None,
    residual_tol: float | None,
    basin_draws: int,
) -> EquilibriumSearchProtocol:
    """Build public protocol metadata for a multiplicity report."""

    normalized_mode = mode if mode in {"baseline", "research", "continuation"} else "baseline"
    return EquilibriumSearchProtocol(
        mode=normalized_mode,
        start_domain=start_domain,
        n_attempts=max(1, int(n_attempts)),
        continuation_parameter=continuation_parameter,
        continuation_grid=list(continuation_grid),
        merge_tol=merge_tol,
        residual_tol=residual_tol,
        basin_draws=max(0, int(basin_draws)),
    )


def summarize_search_diagnostics(
    outcomes: list[SolveOutcome],
    *,
    num_equilibria: int,
    num_unresolved: int,
) -> EquilibriumMultiplicityDiagnostics:
    """Summarize convergence/failure counts for a multiplicity search."""

    statuses = Counter(outcome.status for outcome in outcomes if not outcome.converged)
    total = len(outcomes)
    return EquilibriumMultiplicityDiagnostics(
        num_attempts=total,
        num_converged=sum(1 for outcome in outcomes if outcome.converged),
        num_equilibria=num_equilibria,
        num_unresolved=num_unresolved,
        two_cycle_failures=statuses.get("oscillating", 0),
        stagnation_failures=statuses.get("stagnated", 0),
        divergence_failures=statuses.get("diverged", 0),
        unresolved_starts_share=(num_unresolved / total if total else None),
        false_merge_risk=0.0,
    )


def build_multiplicity_report(
    *,
    model_id: str,
    parameter_hash: str | None,
    search_protocol: EquilibriumSearchProtocol,
    equilibria: list[EquilibriumCandidate],
    branches: list[EquilibriumBranch],
    bifurcation_candidates: list[BifurcationCandidate],
    basin_estimates: list[BasinEstimate],
    unresolved_starts: list[UnresolvedEquilibriumStart],
    global_diagnostics: EquilibriumMultiplicityDiagnostics,
    runtime_refs: Iterable[str],
    git_sha: str,
    random_seed: int | None,
    notes: list[str],
) -> EquilibriumMultiplicityReport:
    """Assemble the public report DTO in one place."""

    return EquilibriumMultiplicityReport(
        model_id=model_id,
        parameter_hash=parameter_hash,
        search_protocol=search_protocol,
        equilibria=equilibria,
        branches=branches,
        bifurcation_candidates=bifurcation_candidates,
        basin_estimates=basin_estimates,
        unresolved_starts=unresolved_starts,
        global_diagnostics=global_diagnostics,
        provenance=EquilibriumMultiplicityProvenance(
            git_sha=git_sha,
            runtime_refs=[str(ref) for ref in runtime_refs],
            random_seed=random_seed,
        ),
        notes=notes,
    )
