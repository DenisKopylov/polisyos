"""Continuation helpers for fixed-point branch bookkeeping."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from polisyos.core.contracts.foundry import EquilibriumBranch, EquilibriumBranchPoint


@dataclass(frozen=True)
class ContinuationPoint:
    """One solved point on a parameterized fixed-point branch."""

    lambda_value: float
    equilibrium_id: str
    solution: np.ndarray


def pseudo_arclength_predictor(
    previous: ContinuationPoint,
    current: ContinuationPoint,
    *,
    next_lambda: float,
) -> np.ndarray:
    """Predict the next state using the secant in augmented `(x, lambda)` space."""

    delta_lambda = current.lambda_value - previous.lambda_value
    if abs(delta_lambda) <= 1.0e-12:
        return current.solution.copy()
    slope = (current.solution - previous.solution) / delta_lambda
    return current.solution + slope * (next_lambda - current.lambda_value)


def build_nearest_neighbor_branches(
    points_by_lambda: list[tuple[float, list[tuple[str, np.ndarray]]]],
    *,
    merge_tol: float,
) -> list[EquilibriumBranch]:
    """Build lightweight continuation branches by nearest-neighbor matching."""

    branches: dict[str, list[EquilibriumBranchPoint]] = {}
    branch_solutions: dict[str, np.ndarray] = {}
    next_branch_index = 1

    for lambda_value, points in points_by_lambda:
        assigned_branch_ids: set[str] = set()
        for equilibrium_id, solution in points:
            solution_array = np.asarray(solution, dtype=float)
            branch_id = _nearest_branch_id(
                solution_array,
                branch_solutions=branch_solutions,
                assigned_branch_ids=assigned_branch_ids,
                merge_tol=merge_tol,
            )
            if branch_id is None:
                branch_id = f"br_{next_branch_index:03d}"
                next_branch_index += 1
                branches[branch_id] = []
            branches[branch_id].append(
                EquilibriumBranchPoint(
                    lambda_value=float(lambda_value),
                    equilibrium_id=equilibrium_id,
                )
            )
            branch_solutions[branch_id] = solution_array
            assigned_branch_ids.add(branch_id)

    return [
        EquilibriumBranch(
            branch_id=branch_id,
            points=points,
            notes=["nearest_neighbor_continuation"],
        )
        for branch_id, points in branches.items()
    ]


def _nearest_branch_id(
    solution: np.ndarray,
    *,
    branch_solutions: dict[str, np.ndarray],
    assigned_branch_ids: set[str],
    merge_tol: float,
) -> str | None:
    candidates = [
        (float(np.max(np.abs(solution - branch_solution))), branch_id)
        for branch_id, branch_solution in branch_solutions.items()
        if branch_id not in assigned_branch_ids
    ]
    if not candidates:
        return None
    distance, branch_id = min(candidates, key=lambda item: item[0])
    if distance <= max(merge_tol, 1.0e-12):
        return branch_id
    return None
