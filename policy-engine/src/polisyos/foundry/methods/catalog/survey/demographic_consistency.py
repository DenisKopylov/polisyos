"""Public demographic-consistency survey estimators."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from polisyos.core.observability import DeterminismTier
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


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("demography", "json"),
                contract_id=DemographicConsistencyResult.contract_id,
            )
        }
    )


def _to_numpy(value: Any, *, dtype: Any = float) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value.astype(dtype, copy=False)
    return np.asarray(value, dtype=dtype)


def _float_vector(
    state: Mapping[str, Any],
    key: str,
    *,
    expected_length: int | None = None,
    default: Any | None = None,
) -> np.ndarray:
    raw = state[key] if key in state else default
    if raw is None:
        raise ValueError(f"{key} is required")
    arr = _to_numpy(raw, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    if expected_length is not None and arr.shape[0] != expected_length:
        raise ValueError(f"{key} must have length {expected_length}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{key} must contain only finite values")
    return arr


def _index_vector(
    state: Mapping[str, Any],
    key: str,
    *,
    expected_length: int | None = None,
) -> np.ndarray:
    raw = state[key]
    arr = np.asarray(raw)
    if arr.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    if expected_length is not None and arr.shape[0] != expected_length:
        raise ValueError(f"{key} must have length {expected_length}")
    try:
        coerced = arr.astype(np.int64, copy=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must contain integer-like values") from exc
    if not np.allclose(arr, coerced, atol=0.0):
        raise ValueError(f"{key} must contain integer-like values")
    return coerced


def _as_bool_vector(
    state: Mapping[str, Any],
    key: str,
    *,
    expected_length: int | None = None,
    default: bool = False,
) -> np.ndarray:
    raw = state.get(key)
    if raw is None:
        if expected_length is None:
            raise ValueError(f"{key} is required when no default length is available")
        return np.full(expected_length, default, dtype=bool)
    arr = np.asarray(raw, dtype=bool)
    if arr.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    if expected_length is not None and arr.shape[0] != expected_length:
        raise ValueError(f"{key} must have length {expected_length}")
    return arr


def _bincount(indices: np.ndarray, weights: np.ndarray, size: int) -> np.ndarray:
    return np.bincount(indices, weights=weights, minlength=size).astype(float, copy=False)


def _matrix(
    state: Mapping[str, Any],
    key: str,
    *,
    expected_columns: int | None = None,
) -> np.ndarray | None:
    raw = state.get(key)
    if raw is None:
        return None
    arr = _to_numpy(raw, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"{key} must be a 2D matrix")
    if expected_columns is not None and arr.shape[1] != expected_columns:
        raise ValueError(f"{key} must have {expected_columns} columns")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{key} must contain only finite values")
    return arr


class DemographicConsistencyResult(BaseModel):
    """Carry sparse flow calibration outputs plus demographic accounting diagnostics."""

    contract_id: ClassVar[str] = "foundry.survey.demographic_consistency_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    calibrated_flows: Any
    candidate_record_index: Any
    candidate_state_index: Any
    record_survivor_weights: Any
    achieved_row_totals: Any
    target_state_totals: Any
    reconciled_state_totals: Any
    achieved_state_totals: Any
    entrant_state_totals: Any
    exit_weights: Any
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "calibrated_flows",
        "candidate_record_index",
        "candidate_state_index",
        "record_survivor_weights",
        "achieved_row_totals",
        "target_state_totals",
        "reconciled_state_totals",
        "achieved_state_totals",
        "entrant_state_totals",
        "exit_weights",
        mode="before",
    )
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return np.asarray(value)

    @field_serializer(
        "calibrated_flows",
        "candidate_record_index",
        "candidate_state_index",
        "record_survivor_weights",
        "achieved_row_totals",
        "target_state_totals",
        "reconciled_state_totals",
        "achieved_state_totals",
        "entrant_state_totals",
        "exit_weights",
        mode="plain",
        when_used="json",
    )
    def _serialize_numpy(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @model_validator(mode="after")
    def _validate_shapes(self) -> DemographicConsistencyResult:
        flows = _to_numpy(self.calibrated_flows, dtype=float)
        record_index = _to_numpy(self.candidate_record_index, dtype=np.int64)
        state_index = _to_numpy(self.candidate_state_index, dtype=np.int64)
        survivor_weights = _to_numpy(self.record_survivor_weights, dtype=float)
        achieved_rows = _to_numpy(self.achieved_row_totals, dtype=float)
        target_state_totals = _to_numpy(self.target_state_totals, dtype=float)
        reconciled = _to_numpy(self.reconciled_state_totals, dtype=float)
        achieved = _to_numpy(self.achieved_state_totals, dtype=float)
        entrants = _to_numpy(self.entrant_state_totals, dtype=float)
        exits = _to_numpy(self.exit_weights, dtype=float)

        if flows.ndim != 1:
            raise ValueError("calibrated_flows must be a 1D array")
        if record_index.ndim != 1 or state_index.ndim != 1:
            raise ValueError("candidate indices must be 1D arrays")
        if record_index.shape[0] != flows.shape[0] or state_index.shape[0] != flows.shape[0]:
            raise ValueError("candidate indices must align with calibrated_flows")
        if survivor_weights.ndim != 1 or achieved_rows.ndim != 1 or exits.ndim != 1:
            raise ValueError("record-level outputs must be 1D arrays")
        if survivor_weights.shape != achieved_rows.shape or survivor_weights.shape != exits.shape:
            raise ValueError("record-level outputs must have matching shapes")
        if (
            target_state_totals.ndim != 1
            or reconciled.ndim != 1
            or achieved.ndim != 1
            or entrants.ndim != 1
        ):
            raise ValueError("state-level outputs must be 1D arrays")
        if not (target_state_totals.shape == reconciled.shape == achieved.shape == entrants.shape):
            raise ValueError("state-level outputs must have matching shapes")
        return self


def _prepare_problem(
    state: Mapping[str, Any],
    params: Mapping[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    base_weights = _float_vector(state, "base_weights")
    n_records = base_weights.shape[0]
    if np.any(base_weights < 0.0):
        raise ValueError("base_weights must be non-negative")

    target_state_totals = _float_vector(state, "target_state_totals")
    n_states = target_state_totals.shape[0]
    if np.any(target_state_totals < 0.0):
        raise ValueError("target_state_totals must be non-negative")

    entrant_state_totals = _float_vector(
        state,
        "entrant_state_totals",
        expected_length=n_states,
        default=np.zeros(n_states, dtype=float),
    )
    if np.any(entrant_state_totals < 0.0):
        raise ValueError("entrant_state_totals must be non-negative")
    if np.any(entrant_state_totals - target_state_totals > 1e-9):
        raise ValueError("entrant_state_totals cannot exceed target_state_totals")

    exit_weights = _float_vector(
        state,
        "exit_weights",
        expected_length=n_records,
        default=np.zeros(n_records, dtype=float),
    )
    if np.any(exit_weights < 0.0):
        raise ValueError("exit_weights must be non-negative")
    if np.any(exit_weights - base_weights > 1e-9):
        raise ValueError("exit_weights cannot exceed base_weights")

    candidate_record_index = _index_vector(state, "candidate_record_index")
    candidate_state_index = _index_vector(
        state,
        "candidate_state_index",
        expected_length=candidate_record_index.shape[0],
    )
    n_edges = candidate_record_index.shape[0]
    if np.any((candidate_record_index < 0) | (candidate_record_index >= n_records)):
        raise ValueError("candidate_record_index contains out-of-range record ids")
    if np.any((candidate_state_index < 0) | (candidate_state_index >= n_states)):
        raise ValueError("candidate_state_index contains out-of-range state ids")

    prior_flows = _float_vector(
        state,
        "prior_flows",
        expected_length=n_edges,
        default=np.ones(n_edges, dtype=float),
    )
    if np.any(prior_flows < 0.0):
        raise ValueError("prior_flows must be non-negative")

    structural_zero_mask = _as_bool_vector(
        state,
        "structural_zero_mask",
        expected_length=n_edges,
        default=False,
    )
    prior_flows = np.where(structural_zero_mask, 0.0, prior_flows)

    row_targets = np.maximum(base_weights - exit_weights, 0.0)
    survivor_targets = target_state_totals - entrant_state_totals
    if np.any(survivor_targets < -1e-9):
        raise ValueError("entrant_state_totals leave negative survivor targets")
    survivor_targets = np.maximum(survivor_targets, 0.0)

    available_mass = float(np.sum(row_targets))
    requested_survivor_mass = float(np.sum(survivor_targets))
    tolerance = max(0.0, float(params.get("tolerance", 1e-8)))
    reconciliation_mode = str(params.get("reconciliation_mode", "scale_survivor_targets"))
    mass_gap_before = available_mass - requested_survivor_mass
    factor = 1.0
    reconciled = survivor_targets.copy()
    reconciliation_applied = False
    if abs(mass_gap_before) > tolerance:
        if reconciliation_mode == "error":
            raise ValueError(
                "survivor target totals are inconsistent with available survivor mass; "
                "use reconciliation_mode='scale_survivor_targets' or align inputs upstream"
            )
        if reconciliation_mode != "scale_survivor_targets":
            raise ValueError(f"unsupported reconciliation_mode {reconciliation_mode!r}")
        if requested_survivor_mass <= tolerance:
            raise ValueError("cannot scale zero survivor targets to absorb positive survivor mass")
        factor = available_mass / requested_survivor_mass
        reconciled *= factor
        reconciliation_applied = True

    diagnostics = {
        "available_survivor_mass": available_mass,
        "requested_survivor_mass": requested_survivor_mass,
        "mass_gap_before_reconciliation": mass_gap_before,
        "mass_reconciliation_applied": reconciliation_applied,
        "mass_reconciliation_factor": factor,
        "reconciliation_mode": reconciliation_mode,
        "n_records": int(n_records),
        "n_states": int(n_states),
        "n_edges": int(n_edges),
    }

    return (
        row_targets,
        reconciled,
        candidate_record_index,
        candidate_state_index,
        prior_flows,
        entrant_state_totals,
        diagnostics,
    )


def _validate_feasibility(
    row_targets: np.ndarray,
    col_targets: np.ndarray,
    row_index: np.ndarray,
    col_index: np.ndarray,
    prior_flows: np.ndarray,
    *,
    tolerance: float,
) -> None:
    n_records = row_targets.shape[0]
    n_states = col_targets.shape[0]

    row_prior = _bincount(row_index, prior_flows, n_records)
    col_prior = _bincount(col_index, prior_flows, n_states)

    impossible_rows = np.flatnonzero((row_targets > tolerance) & (row_prior <= tolerance))
    if impossible_rows.size:
        preview = ", ".join(map(str, impossible_rows[:5]))
        raise ValueError(f"rows with positive survivor mass have no admissible flows: {preview}")

    impossible_cols = np.flatnonzero((col_targets > tolerance) & (col_prior <= tolerance))
    if impossible_cols.size:
        preview = ", ".join(map(str, impossible_cols[:5]))
        raise ValueError(
            f"states with positive target mass have no admissible donor flows: {preview}"
        )


@dataclass(slots=True)
class _ResidualEdge:
    """One mutable edge in the fractional transportation network."""

    destination: int
    reverse_index: int
    remaining: float


def _add_residual_edge(
    graph: list[list[_ResidualEdge]], source: int, destination: int, capacity: float
) -> int:
    forward_index = len(graph[source])
    reverse_index = len(graph[destination])
    graph[source].append(_ResidualEdge(destination, reverse_index, capacity))
    graph[destination].append(_ResidualEdge(source, forward_index, 0.0))
    return forward_index


def _strongly_connected_components(adjacency: list[list[int]]) -> list[int]:
    """Return component ids using iterative Kosaraju traversal."""
    reverse_adjacency = [[] for _ in adjacency]
    for source, destinations in enumerate(adjacency):
        for destination in destinations:
            reverse_adjacency[destination].append(source)

    visited = [False] * len(adjacency)
    order: list[int] = []
    for root in range(len(adjacency)):
        if visited[root]:
            continue
        visited[root] = True
        stack = [(root, 0)]
        while stack:
            node, next_index = stack[-1]
            if next_index == len(adjacency[node]):
                order.append(node)
                stack.pop()
                continue
            destination = adjacency[node][next_index]
            stack[-1] = (node, next_index + 1)
            if not visited[destination]:
                visited[destination] = True
                stack.append((destination, 0))

    components = [-1] * len(adjacency)
    component_id = 0
    for root in reversed(order):
        if components[root] >= 0:
            continue
        components[root] = component_id
        stack = [root]
        while stack:
            node = stack.pop()
            for destination in reverse_adjacency[node]:
                if components[destination] < 0:
                    components[destination] = component_id
                    stack.append(destination)
        component_id += 1
    return components


def _relative_interior_support(
    row_targets: np.ndarray,
    col_targets: np.ndarray,
    row_index: np.ndarray,
    col_index: np.ndarray,
    prior_flows: np.ndarray,
) -> np.ndarray | None:
    """Find edges that can be positive in a feasible fractional transportation flow.

    A single feasible flow identifies edges already carrying mass. A zero-flow
    edge can carry mass in another feasible flow exactly when its forward
    residual arc lies on an alternating cycle in the row/column residual graph.
    If floating-point residuals make that support proof ambiguous, return None
    and leave the existing IPF path to handle the original support.
    """
    n_rows = row_targets.shape[0]
    n_cols = col_targets.shape[0]
    n_edges = prior_flows.shape[0]
    if row_index.shape != prior_flows.shape or col_index.shape != prior_flows.shape:
        return None
    if (
        not np.all(np.isfinite(row_targets))
        or not np.all(np.isfinite(col_targets))
        or not np.all(np.isfinite(prior_flows))
        or np.any(row_targets < 0.0)
        or np.any(col_targets < 0.0)
        or np.any(prior_flows < 0.0)
        or np.any((row_index < 0) | (row_index >= n_rows))
        or np.any((col_index < 0) | (col_index >= n_cols))
    ):
        return None

    row_mass = float(np.sum(row_targets))
    col_mass = float(np.sum(col_targets))
    if not np.isfinite(row_mass) or not np.isfinite(col_mass) or row_mass != col_mass:
        return None
    if row_mass == 0.0:
        return np.zeros(n_edges, dtype=bool)

    roundoff = (
        np.finfo(float).eps
        * max(1.0, row_mass)
        * max(32, n_rows + n_cols + n_edges)
    )
    if not np.isfinite(roundoff) or roundoff <= 0.0:
        return None
    if np.any((row_targets > 0.0) & (row_targets <= roundoff)):
        return None
    if np.any((col_targets > 0.0) & (col_targets <= roundoff)):
        return None

    edge_capacities = np.minimum(row_targets[row_index], col_targets[col_index])
    supported_edges = prior_flows > 0.0
    if np.any(supported_edges & (edge_capacities > 0.0) & (edge_capacities <= roundoff)):
        return None

    source = 0
    row_offset = 1
    col_offset = row_offset + n_rows
    sink = col_offset + n_cols
    graph: list[list[_ResidualEdge]] = [[] for _ in range(sink + 1)]
    source_edges: list[tuple[int, int]] = []
    sink_edges: list[tuple[int, int]] = []
    for row, target in enumerate(row_targets):
        edge_index = _add_residual_edge(graph, source, row_offset + row, float(target))
        source_edges.append((source, edge_index))
    for col, target in enumerate(col_targets):
        edge_index = _add_residual_edge(graph, col_offset + col, sink, float(target))
        sink_edges.append((col_offset + col, edge_index))

    candidate_edges: list[tuple[int, int, int, float]] = []
    for edge_position, (row, col) in enumerate(zip(row_index, col_index, strict=True)):
        if not supported_edges[edge_position]:
            continue
        capacity = float(edge_capacities[edge_position])
        if capacity <= 0.0:
            candidate_edges.append((edge_position, row_offset + int(row), -1, 0.0))
            continue
        graph_edge_index = _add_residual_edge(
            graph, row_offset + int(row), col_offset + int(col), capacity
        )
        candidate_edges.append(
            (edge_position, row_offset + int(row), graph_edge_index, capacity)
        )

    ambiguous_flow = False

    def _send_one_path(levels: list[int], cursors: list[int]) -> float:
        nonlocal ambiguous_flow
        nodes = [source]
        path: list[tuple[int, int]] = []
        while nodes:
            node = nodes[-1]
            if node == sink:
                amount = min(graph[parent][edge_index].remaining for parent, edge_index in path)
                if amount <= roundoff:
                    ambiguous_flow = True
                    return 0.0
                for parent, edge_index in path:
                    edge = graph[parent][edge_index]
                    reverse = graph[edge.destination][edge.reverse_index]
                    edge.remaining -= amount
                    reverse.remaining += amount
                return amount

            while cursors[node] < len(graph[node]):
                edge_index = cursors[node]
                edge = graph[node][edge_index]
                if edge.remaining > 0.0 and levels[edge.destination] == levels[node] + 1:
                    path.append((node, edge_index))
                    nodes.append(edge.destination)
                    break
                cursors[node] += 1
            else:
                levels[node] = -1
                nodes.pop()
                if path:
                    parent, _ = path.pop()
                    cursors[parent] += 1
        return 0.0

    while True:
        levels = [-1] * len(graph)
        levels[source] = 0
        queue = deque([source])
        while queue:
            node = queue.popleft()
            for edge in graph[node]:
                if edge.remaining > 0.0 and levels[edge.destination] < 0:
                    levels[edge.destination] = levels[node] + 1
                    queue.append(edge.destination)
        if levels[sink] < 0:
            break
        cursors = [0] * len(graph)
        while _send_one_path(levels, cursors) > 0.0:
            pass
        if ambiguous_flow:
            return None

    if any(graph[node][edge_index].remaining != 0.0 for node, edge_index in source_edges):
        return None
    if any(graph[node][edge_index].remaining != 0.0 for node, edge_index in sink_edges):
        return None

    edge_flows = np.zeros(n_edges, dtype=float)
    edge_residuals = np.zeros(n_edges, dtype=float)
    for edge_position, node, edge_index, capacity in candidate_edges:
        if edge_index < 0:
            continue
        edge = graph[node][edge_index]
        reverse = graph[edge.destination][edge.reverse_index]
        edge_flows[edge_position] = reverse.remaining
        edge_residuals[edge_position] = edge.remaining
        if (
            0.0 < reverse.remaining <= roundoff
            or 0.0 < edge.remaining <= roundoff
            or reverse.remaining > capacity + roundoff
        ):
            return None

    if (
        not np.all(np.isfinite(edge_flows))
        or np.any(edge_flows < 0.0)
        or np.any(edge_flows > edge_capacities + roundoff)
        or np.any(edge_flows[~supported_edges] != 0.0)
    ):
        return None
    flow_mass = float(np.sum(edge_flows))
    if not np.isfinite(flow_mass) or abs(flow_mass - row_mass) > roundoff:
        return None

    achieved_rows = _bincount(row_index, edge_flows, n_rows)
    achieved_cols = _bincount(col_index, edge_flows, n_cols)
    if (
        np.max(np.abs(achieved_rows - row_targets), initial=0.0) > roundoff
        or np.max(np.abs(achieved_cols - col_targets), initial=0.0) > roundoff
    ):
        return None

    adjacency = [[] for _ in range(n_rows + n_cols)]
    for edge_position, (row, col) in enumerate(zip(row_index, col_index, strict=True)):
        if not supported_edges[edge_position]:
            continue
        row_node = int(row)
        col_node = n_rows + int(col)
        if edge_flows[edge_position] > 0.0:
            adjacency[col_node].append(row_node)
        if edge_residuals[edge_position] > 0.0:
            adjacency[row_node].append(col_node)

    components = _strongly_connected_components(adjacency)
    relative_support = np.zeros(n_edges, dtype=bool)
    positive_flow = edge_flows > 0.0
    alternating_cycle = np.fromiter(
        (
            components[int(row)] == components[n_rows + int(col)]
            for row, col in zip(row_index, col_index, strict=True)
        ),
        dtype=bool,
        count=n_edges,
    )
    relative_support[supported_edges] = positive_flow[supported_edges] | (
        (edge_residuals[supported_edges] > 0.0) & alternating_cycle[supported_edges]
    )

    retained_flow = np.where(relative_support, edge_flows, 0.0)
    retained_rows = _bincount(row_index, retained_flow, n_rows)
    retained_cols_from_flow = _bincount(col_index, retained_flow, n_cols)
    if (
        np.max(np.abs(retained_rows - row_targets), initial=0.0) > roundoff
        or np.max(np.abs(retained_cols_from_flow - col_targets), initial=0.0) > roundoff
    ):
        return None

    retained_rows = _bincount(
        row_index[relative_support], np.ones(np.count_nonzero(relative_support)), n_rows
    )
    retained_cols = _bincount(
        col_index[relative_support], np.ones(np.count_nonzero(relative_support)), n_cols
    )
    if np.any((row_targets > 0.0) & (retained_rows == 0.0)):
        return None
    if np.any((col_targets > 0.0) & (retained_cols == 0.0)):
        return None
    return relative_support


def _sparse_ipf(
    row_targets: np.ndarray,
    col_targets: np.ndarray,
    row_index: np.ndarray,
    col_index: np.ndarray,
    prior_flows: np.ndarray,
    *,
    max_iterations: int,
    tolerance: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, bool]:
    n_records = row_targets.shape[0]
    n_states = col_targets.shape[0]
    flows = prior_flows.astype(float, copy=True)

    row_sum = _bincount(row_index, flows, n_records)
    row_scale = np.zeros_like(row_targets)
    positive_rows = row_targets > tolerance
    row_scale[positive_rows] = row_targets[positive_rows] / row_sum[positive_rows]
    flows *= row_scale[row_index]

    converged = False
    iterations = 0
    for iterations in range(1, max_iterations + 1):
        col_sum = _bincount(col_index, flows, n_states)
        col_scale = np.zeros_like(col_targets)
        positive_cols = col_targets > tolerance
        col_scale[positive_cols] = col_targets[positive_cols] / col_sum[positive_cols]
        flows *= col_scale[col_index]

        row_sum = _bincount(row_index, flows, n_records)
        row_scale = np.zeros_like(row_targets)
        positive_rows = row_targets > tolerance
        row_scale[positive_rows] = row_targets[positive_rows] / row_sum[positive_rows]
        flows *= row_scale[row_index]

        row_sum = _bincount(row_index, flows, n_records)
        col_sum = _bincount(col_index, flows, n_states)
        max_row_gap = float(np.max(np.abs(row_sum - row_targets), initial=0.0))
        max_col_gap = float(np.max(np.abs(col_sum - col_targets), initial=0.0))
        if max(max_row_gap, max_col_gap) <= tolerance:
            converged = True
            break

    return flows, row_sum, col_sum, iterations, converged


def _solve_soft_constrained_problem(
    row_targets: np.ndarray,
    col_targets: np.ndarray,
    row_index: np.ndarray,
    col_index: np.ndarray,
    prior_flows: np.ndarray,
    soft_constraint_matrix: np.ndarray,
    soft_target_totals: np.ndarray,
    soft_constraint_weights: np.ndarray,
    *,
    max_iterations: int,
    tolerance: float,
    soft_iterations: int,
    soft_tolerance: float,
    soft_step_size: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, bool, dict[str, Any]]:
    adjusted_prior = prior_flows.astype(float, copy=True)
    positive_prior = prior_flows > tolerance
    best_payload: tuple[np.ndarray, np.ndarray, np.ndarray, int, bool] | None = None
    best_soft_gap = float("inf")
    outer_iterations = 0

    for outer_iterations in range(1, soft_iterations + 1):
        flows, row_sum, col_sum, inner_iterations, converged = _sparse_ipf(
            row_targets,
            col_targets,
            row_index,
            col_index,
            adjusted_prior,
            max_iterations=max_iterations,
            tolerance=tolerance,
        )
        achieved_soft = soft_constraint_matrix @ flows
        soft_residual = achieved_soft - soft_target_totals
        soft_gap = float(np.max(np.abs(soft_residual), initial=0.0))
        if soft_gap < best_soft_gap:
            best_soft_gap = soft_gap
            best_payload = (flows, row_sum, col_sum, inner_iterations, converged)
            best_diagnostics = {
                "soft_achieved_totals": achieved_soft.tolist(),
                "soft_target_totals": soft_target_totals.tolist(),
                "soft_residuals": soft_residual.tolist(),
                "soft_max_gap": soft_gap,
            }
        if soft_gap <= soft_tolerance:
            break

        gradient = (soft_constraint_weights * soft_residual) @ soft_constraint_matrix
        gradient = np.clip(gradient, -50.0, 50.0)
        adjustment = np.exp(-soft_step_size * gradient)
        adjusted_prior = adjusted_prior * adjustment
        adjusted_prior[~positive_prior] = 0.0
        adjusted_prior[positive_prior] = np.maximum(adjusted_prior[positive_prior], 1e-300)

    if best_payload is None:
        raise ValueError("soft-constrained demographic balancing could not initialize")

    flows, row_sum, col_sum, inner_iterations, converged = best_payload
    diagnostics = {
        **best_diagnostics,
        "soft_constraint_count": int(soft_target_totals.shape[0]),
        "soft_iterations": int(outer_iterations),
        "soft_tolerance": float(soft_tolerance),
        "soft_step_size": float(soft_step_size),
        "soft_converged": bool(best_soft_gap <= soft_tolerance),
        "inner_iterations_at_best": int(inner_iterations),
        "inner_converged_at_best": bool(converged),
    }
    return flows, row_sum, col_sum, inner_iterations, converged, diagnostics


def _weight_quality_metrics(
    base_weights: np.ndarray, achieved_rows: np.ndarray
) -> dict[str, float]:
    positive = achieved_rows > 0.0
    positive_weights = achieved_rows[positive]
    if positive_weights.size == 0:
        return {
            "effective_sample_size": 0.0,
            "weight_cv": 0.0,
            "weight_max_to_mean_ratio": 0.0,
            "positive_record_share": 0.0,
        }
    ess = float((np.sum(positive_weights) ** 2) / max(np.sum(positive_weights**2), 1e-12))
    mean_weight = float(np.mean(positive_weights))
    weight_cv = float(np.std(positive_weights) / max(mean_weight, 1e-12))
    max_ratio = float(np.max(positive_weights) / max(mean_weight, 1e-12))
    return {
        "effective_sample_size": ess,
        "weight_cv": weight_cv,
        "weight_max_to_mean_ratio": max_ratio,
        "positive_record_share": float(np.mean(positive.astype(float))),
        "survivor_share_of_mass": float(np.sum(achieved_rows) / max(np.sum(base_weights), 1e-12)),
    }


def _entropic_objective(flows: np.ndarray, prior_flows: np.ndarray) -> float:
    mask = (flows > 0.0) & (prior_flows > 0.0)
    if not np.any(mask):
        return 0.0
    return float(np.sum(flows[mask] * np.log(flows[mask] / prior_flows[mask])))


def _solve_demographic_consistency(
    state: Mapping[str, Any],
    params: Mapping[str, Any],
) -> DemographicConsistencyResult:
    (
        row_targets,
        reconciled_survivor_targets,
        row_index,
        col_index,
        prior_flows,
        entrant_state_totals,
        diagnostics,
    ) = _prepare_problem(state, params)
    tolerance = max(0.0, float(params.get("tolerance", 1e-8)))
    max_iterations = max(1, int(params.get("max_iterations", 250)))
    target_state_totals = _float_vector(state, "target_state_totals")
    exit_weights = _float_vector(
        state,
        "exit_weights",
        expected_length=row_targets.shape[0],
        default=np.zeros(row_targets.shape[0], dtype=float),
    )
    base_weights = _float_vector(state, "base_weights", expected_length=row_targets.shape[0])
    soft_constraint_matrix = _matrix(
        state, "soft_constraint_matrix", expected_columns=prior_flows.shape[0]
    )
    soft_diagnostics: dict[str, Any] = {}

    _validate_feasibility(
        row_targets,
        reconciled_survivor_targets,
        row_index,
        col_index,
        prior_flows,
        tolerance=tolerance,
    )
    objective_prior_flows = prior_flows
    relative_support = _relative_interior_support(
        row_targets,
        reconciled_survivor_targets,
        row_index,
        col_index,
        prior_flows,
    )
    if relative_support is not None:
        prior_flows = np.where(relative_support, prior_flows, 0.0)
    if soft_constraint_matrix is None:
        flows, achieved_rows, achieved_survivor_states, iterations, converged = _sparse_ipf(
            row_targets,
            reconciled_survivor_targets,
            row_index,
            col_index,
            prior_flows,
            max_iterations=max_iterations,
            tolerance=tolerance,
        )
    else:
        soft_target_totals = _float_vector(
            state,
            "soft_target_totals",
            expected_length=soft_constraint_matrix.shape[0],
        )
        soft_constraint_weights = _float_vector(
            state,
            "soft_constraint_weights",
            expected_length=soft_constraint_matrix.shape[0],
            default=np.ones(soft_constraint_matrix.shape[0], dtype=float),
        )
        if np.any(soft_constraint_weights < 0.0):
            raise ValueError("soft_constraint_weights must be non-negative")
        (
            flows,
            achieved_rows,
            achieved_survivor_states,
            iterations,
            converged,
            soft_diagnostics,
        ) = _solve_soft_constrained_problem(
            row_targets,
            reconciled_survivor_targets,
            row_index,
            col_index,
            prior_flows,
            soft_constraint_matrix,
            soft_target_totals,
            soft_constraint_weights,
            max_iterations=max_iterations,
            tolerance=tolerance,
            soft_iterations=max(1, int(params.get("soft_iterations", 6))),
            soft_tolerance=max(0.0, float(params.get("soft_tolerance", 1e-4))),
            soft_step_size=max(1e-6, float(params.get("soft_step_size", 0.25))),
        )

    achieved_state_totals = achieved_survivor_states + entrant_state_totals
    max_row_gap = float(np.max(np.abs(achieved_rows - row_targets), initial=0.0))
    max_survivor_gap = float(
        np.max(np.abs(achieved_survivor_states - reconciled_survivor_targets), initial=0.0)
    )
    max_final_gap = float(
        np.max(
            np.abs(achieved_state_totals - (reconciled_survivor_targets + entrant_state_totals)),
            initial=0.0,
        )
    )
    structural_zero_violations = int(
        np.count_nonzero((objective_prior_flows <= tolerance) & (flows > tolerance))
    )
    diagnostics.update(
        {
            "iterations": int(iterations),
            "converged": bool(converged),
            "tolerance": tolerance,
            "max_row_gap": max_row_gap,
            "max_survivor_state_gap": max_survivor_gap,
            "max_final_state_gap": max_final_gap,
            "mass_balance_gap": float(
                np.sum(achieved_rows) + np.sum(exit_weights) - np.sum(base_weights)
            ),
            "entrant_mass_total": float(np.sum(entrant_state_totals)),
            "exit_mass_total": float(np.sum(exit_weights)),
            "entropic_objective": _entropic_objective(
                flows, np.maximum(objective_prior_flows, 1e-300)
            ),
            "structural_zero_violations": structural_zero_violations,
        }
    )
    diagnostics.update(_weight_quality_metrics(base_weights, achieved_rows))
    diagnostics.update(soft_diagnostics)

    require_convergence = bool(params.get("require_convergence", True))
    if require_convergence and not converged:
        raise ValueError(
            "demographic consistency balancing did not converge under hard constraints; "
            f"max_row_gap={max_row_gap:.6g}, max_state_gap={max_final_gap:.6g}"
        )

    return DemographicConsistencyResult(
        calibrated_flows=flows,
        candidate_record_index=row_index,
        candidate_state_index=col_index,
        record_survivor_weights=row_targets,
        achieved_row_totals=achieved_rows,
        target_state_totals=target_state_totals,
        reconciled_state_totals=reconciled_survivor_targets + entrant_state_totals,
        achieved_state_totals=achieved_state_totals,
        entrant_state_totals=entrant_state_totals,
        exit_weights=exit_weights,
        diagnostics=diagnostics,
    )


@foundry_method(
    namespace="survey.demography",
    version="1.0.0",
    tags={"survey", "demography", "microsim", "calibration"},
)
class DemographicConsistencyEstimator:
    """Balance sparse record-to-state flows so micro weights satisfy demographic accounting."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="demographic_consistency",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "base_weights", SlotType.VECTOR, Unit("weight", "mass"), shape=("n_records",)
                ),
                SlotSpec(
                    "candidate_record_index",
                    SlotType.VECTOR,
                    Unit("record", "index"),
                    shape=("n_edges",),
                ),
                SlotSpec(
                    "candidate_state_index",
                    SlotType.VECTOR,
                    Unit("state", "index"),
                    shape=("n_edges",),
                ),
                SlotSpec("prior_flows", SlotType.VECTOR, Unit("flow", "mass"), shape=("n_edges",)),
                SlotSpec(
                    "target_state_totals",
                    SlotType.VECTOR,
                    Unit("state_total", "mass"),
                    shape=("n_states",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="max_iterations", default=250),
            ParameterSpec(name="tolerance", default=1e-8),
            ParameterSpec(name="reconciliation_mode", default="scale_survivor_targets"),
            ParameterSpec(name="require_convergence", default=True),
            ParameterSpec(name="soft_iterations", default=6),
            ParameterSpec(name="soft_tolerance", default=1e-4),
            ParameterSpec(name="soft_step_size", default=0.25),
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
            "Sparse demographic flow calibration with exact survivor-row accounting, "
            "entrant masses, and state-total reconciliation."
        ),
        tags=frozenset({"survey", "demography", "microsim", "calibration"}),
        when_to_use=(
            "Static aging where record weights must remain demographically consistent across "
            "births, deaths, migration, and destination-state totals."
        ),
        citations=(
            "Deville, J. & Sarndal, C. (1992). Calibration estimators in survey sampling. Journal of the American Statistical Association, 87(418), 376-382.",
            "Deming, W. & Stephan, F. (1940). On a least squares adjustment of a sampled frequency table when the expected marginal totals are known. Annals of Mathematical Statistics, 11(4), 427-444.",
        ),
        output_interpretation=(
            "Returns calibrated sparse flows, reconciled demographic totals, and accounting "
            "diagnostics. Structural zeros are represented by missing or zero-prior edges."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        return {"result": _solve_demographic_consistency(state, params)}


@foundry_method(
    namespace="survey.demography",
    version="1.0.0",
    tags={"survey", "demography", "cceb", "entropic-balancing"},
)
class CCEBEstimator:
    """Cohort-component plus entropic balancing estimator over sparse demographic flows."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="cceb",
        namespace="",
        version="0.0.0",
        input_slots=DemographicConsistencyEstimator.signature.input_slots,
        output_slots=_result_slot(),
        parameters=DemographicConsistencyEstimator.signature.parameters,
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Canonical cohort-component plus entropic-balancing estimator for "
            "demographically consistent static aging."
        ),
        tags=frozenset({"survey", "demography", "cceb", "entropic-balancing"}),
        when_to_use=(
            "Preferred deterministic Phase-1 demographic aging core when candidate transitions "
            "are already sparsified and macro demographic targets are available."
        ),
        citations=DemographicConsistencyEstimator.metadata.citations,
        output_interpretation=(
            "Same accounting outputs as demographic_consistency, with the entropic objective "
            "reported in diagnostics for auditability."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        return {"result": _solve_demographic_consistency(state, params)}


__all__ = [
    "CCEBEstimator",
    "DemographicConsistencyEstimator",
    "DemographicConsistencyResult",
]
