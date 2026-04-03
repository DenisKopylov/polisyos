"""Public causal constraint discovery module API."""
from __future__ import annotations

import math
import multiprocessing as mp
import time
from dataclasses import dataclass, field
from itertools import combinations
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
from polisyos.ir.analytics.causal_discovery import (
    AlgebraicBlockSpec,
    AlgebraicConstraintFamily,
    AlgebraicConstraintReport,
    CausalDiscoveryReport,
    ConstraintEvaluationResult,
    ImpliedConstraintSpec,
)
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
_ALGEBRAIC_MAX_CONDITIONING_SET_SIZE = 2
_ALGEBRAIC_BOOTSTRAP_DRAWS = 200
_ALGEBRAIC_SEVERITY_ORDER = {"info": 0, "warning": 1, "blocker": 2}
_CATEGORICAL_UNIQUE_THRESHOLD = 12


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


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _max_severity(values: list[str]) -> str:
    if not values:
        return "info"
    return max(values, key=lambda value: _ALGEBRAIC_SEVERITY_ORDER.get(value, 0))


def _bh_adjust(p_values: list[float]) -> list[float]:
    if not p_values:
        return []
    n = len(p_values)
    order = np.argsort(np.asarray(p_values, dtype=float))
    adjusted = np.empty(n, dtype=float)
    running = 1.0
    for rank in range(n - 1, -1, -1):
        idx = int(order[rank])
        raw = float(p_values[idx])
        candidate = min(1.0, raw * n / float(rank + 1))
        running = min(running, candidate)
        adjusted[idx] = running
    return [float(value) for value in adjusted]


def _validate_algebraic_blocks(raw: Any) -> list[AlgebraicBlockSpec]:
    if raw is None:
        return []
    if isinstance(raw, AlgebraicBlockSpec):
        return [raw]
    if not isinstance(raw, (list, tuple)):
        raise ValueError("algebraic_blocks must be a list of algebraic block specs")
    return [AlgebraicBlockSpec.model_validate(item) for item in raw]


def _inject_algebraic_blocks_metadata(
    graph: CausalGraphModel,
    *,
    algebraic_blocks: list[AlgebraicBlockSpec],
) -> CausalGraphModel:
    if not algebraic_blocks:
        return graph
    metadata = dict(graph.metadata)
    metadata["algebraic_blocks"] = [
        block.model_dump(mode="json") for block in algebraic_blocks
    ]
    return graph.model_copy(update={"metadata": metadata})


def _classify_numeric_series(values: np.ndarray) -> str:
    arr = np.asarray(values, dtype=float).reshape(-1)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return "categorical"
    unique = np.unique(finite)
    if unique.size <= _CATEGORICAL_UNIQUE_THRESHOLD and np.allclose(
        unique,
        np.round(unique),
    ):
        return "categorical"
    return "continuous"


def _encode_for_kernel(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values).reshape(-1)
    if _classify_numeric_series(arr.astype(float)) == "categorical":
        labels = arr.astype(str)
        _, inverse = np.unique(labels, return_inverse=True)
        return np.eye(int(np.max(inverse)) + 1, dtype=float)[inverse]
    return np.asarray(arr, dtype=float).reshape(-1, 1)


def _complete_case_mask(columns: list[np.ndarray]) -> np.ndarray:
    if not columns:
        raise ValueError("at least one column is required")
    mask = np.ones(len(columns[0]), dtype=bool)
    for column in columns:
        arr = np.asarray(column, dtype=float).reshape(-1)
        if len(arr) != len(mask):
            raise ValueError("all columns must have the same length")
        mask &= np.isfinite(arr)
    return mask


def _build_contingency_table(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, int, int]:
    x_labels, x_codes = np.unique(x.astype(str), return_inverse=True)
    y_labels, y_codes = np.unique(y.astype(str), return_inverse=True)
    table = np.zeros((len(x_labels), len(y_labels)), dtype=int)
    np.add.at(table, (x_codes, y_codes), 1)
    return table, len(x_labels), len(y_labels)


def _g_test_from_table(table: np.ndarray) -> tuple[float, float, dict[str, Any]]:
    from scipy.stats import chi2, chi2_contingency

    if table.ndim != 2:
        raise ValueError("contingency table must be 2D")
    if table.shape[0] < 2 or table.shape[1] < 2 or int(table.sum()) == 0:
        return 0.0, 1.0, {"degrees_of_freedom": 0, "degenerate": True}

    try:
        statistic, _, dof, _ = chi2_contingency(
            table,
            correction=False,
            lambda_="log-likelihood",
        )
    except ValueError:
        return 0.0, 1.0, {"degrees_of_freedom": 0, "degenerate": True}

    if dof <= 0:
        return 0.0, 1.0, {"degrees_of_freedom": int(dof), "degenerate": True}
    return float(statistic), float(chi2.sf(float(statistic), int(dof))), {
        "degrees_of_freedom": int(dof),
        "degenerate": False,
    }


def _conditional_g_test(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
) -> tuple[float, float, dict[str, Any]]:
    if z.ndim == 1:
        z = z[:, None]

    strata: dict[tuple[str, ...], list[int]] = {}
    for idx, row in enumerate(z):
        strata.setdefault(tuple(row.astype(str).tolist()), []).append(idx)

    total_statistic = 0.0
    total_dof = 0
    valid_strata = 0
    skipped_strata = 0
    for indices in strata.values():
        x_slice = x[indices]
        y_slice = y[indices]
        table, _, _ = _build_contingency_table(x_slice, y_slice)
        statistic, _, meta = _g_test_from_table(table)
        if meta.get("degenerate"):
            skipped_strata += 1
            continue
        total_statistic += statistic
        total_dof += int(meta["degrees_of_freedom"])
        valid_strata += 1

    if total_dof <= 0 or valid_strata == 0:
        return 0.0, 1.0, {
            "degrees_of_freedom": 0,
            "valid_strata": valid_strata,
            "skipped_strata": skipped_strata,
            "degenerate": True,
        }

    from scipy.stats import chi2

    return float(total_statistic), float(chi2.sf(float(total_statistic), total_dof)), {
        "degrees_of_freedom": int(total_dof),
        "valid_strata": valid_strata,
        "skipped_strata": skipped_strata,
        "degenerate": False,
    }


def _mixed_kernel_test(
    *,
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray | None,
    alpha: float,
) -> dict[str, Any]:
    from polisyos.foundry.methods.catalog.causal.independence_tests import (
        HSICIndependenceTest,
        KCIConditionalTest,
    )

    x_enc = _encode_for_kernel(x)
    y_enc = _encode_for_kernel(y)
    if z is None or z.size == 0:
        raw = HSICIndependenceTest.pure_step(
            {"X": x_enc, "Y": y_enc},
            {"alpha": alpha, "n_bootstrap": 99},
        )["result"]
        return {
            "test_name": "hsic_mixed",
            "statistic": float(raw["statistic"]),
            "p_value": float(raw["p_value"]),
            "metadata": {
                **dict(raw.get("metadata", {})),
                "route": "hsic_mixed",
                "approximation": "kernel_mixed_marginal",
            },
        }

    z_enc = np.column_stack([_encode_for_kernel(z[:, idx]) for idx in range(z.shape[1])])
    raw = KCIConditionalTest.pure_step(
        {"X": x_enc, "Y": y_enc, "Z": z_enc},
        {"alpha": alpha, "n_bootstrap": 99, "ridge": 1e-2},
    )["result"]
    return {
        "test_name": "kci_mixed",
        "statistic": float(raw["statistic"]),
        "p_value": float(raw["p_value"]),
        "metadata": {
            **dict(raw.get("metadata", {})),
            "route": "kci_mixed",
            "approximation": "kernel_conditional_independence",
        },
    }


def _run_ci_test(
    *,
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray | None,
    alpha: float,
) -> dict[str, Any]:
    from polisyos.foundry.methods.catalog.causal.independence_tests import (
        PartialCorrelationTest,
    )

    columns = [np.asarray(x, dtype=float).reshape(-1), np.asarray(y, dtype=float).reshape(-1)]
    if z is not None and z.size > 0:
        z_arr = np.asarray(z, dtype=float)
        if z_arr.ndim == 1:
            z_arr = z_arr[:, None]
        columns.extend(z_arr[:, idx] for idx in range(z_arr.shape[1]))
    else:
        z_arr = None

    mask = _complete_case_mask(columns)
    n_complete = int(mask.sum())
    if n_complete < 8:
        return {
            "status": "skipped",
            "warnings": [f"insufficient_complete_cases:{n_complete}"],
            "metadata": {"n_complete_cases": n_complete},
        }

    x_obs = columns[0][mask]
    y_obs = columns[1][mask]
    z_obs = None if z_arr is None else z_arr[mask]

    x_kind = _classify_numeric_series(x_obs)
    y_kind = _classify_numeric_series(y_obs)
    conditioning_kinds = (
        ()
        if z_obs is None
        else tuple(_classify_numeric_series(z_obs[:, idx]) for idx in range(z_obs.shape[1]))
    )
    all_kinds = (x_kind, y_kind, *conditioning_kinds)
    all_categorical = all(kind == "categorical" for kind in all_kinds)
    all_continuous = all(kind == "continuous" for kind in all_kinds)

    try:
        if z_obs is None or z_obs.size == 0:
            if all_categorical:
                table, _, _ = _build_contingency_table(x_obs, y_obs)
                statistic, p_value, meta = _g_test_from_table(table)
                return {
                    "status": "tested",
                    "test_name": "g_test",
                    "statistic": float(statistic),
                    "p_value": float(p_value),
                    "metadata": {
                        **meta,
                        "route": "g_test",
                        "x_kind": x_kind,
                        "y_kind": y_kind,
                        "conditioning_kinds": (),
                        "n_complete_cases": n_complete,
                    },
                }
            if all_continuous:
                raw = PartialCorrelationTest.pure_step(
                    {"X": x_obs, "Y": y_obs},
                    {"alpha": alpha},
                )["result"]
                return {
                    "status": "tested",
                    "test_name": str(raw["test_name"]),
                    "statistic": float(raw["statistic"]),
                    "p_value": float(raw["p_value"]),
                    "metadata": {
                        **dict(raw.get("metadata", {})),
                        "route": "partial_correlation",
                        "x_kind": x_kind,
                        "y_kind": y_kind,
                        "conditioning_kinds": (),
                        "n_complete_cases": n_complete,
                    },
                }
            raw = _mixed_kernel_test(x=x_obs, y=y_obs, z=None, alpha=alpha)
            return {
                "status": "tested",
                "test_name": str(raw["test_name"]),
                "statistic": float(raw["statistic"]),
                "p_value": float(raw["p_value"]),
                "warnings": [
                    "approximate_ci_route: mixed data used kernel independence approximation"
                ],
                "metadata": {
                    **dict(raw.get("metadata", {})),
                    "x_kind": x_kind,
                    "y_kind": y_kind,
                    "conditioning_kinds": (),
                    "n_complete_cases": n_complete,
                },
            }

        if all_categorical:
            statistic, p_value, meta = _conditional_g_test(x_obs, y_obs, z_obs)
            return {
                "status": "tested",
                "test_name": "conditional_g_test",
                "statistic": float(statistic),
                "p_value": float(p_value),
                "metadata": {
                    **meta,
                    "route": "conditional_g_test",
                    "x_kind": x_kind,
                    "y_kind": y_kind,
                    "conditioning_kinds": conditioning_kinds,
                    "n_complete_cases": n_complete,
                },
            }
        if all_continuous:
            raw = PartialCorrelationTest.pure_step(
                {"X": x_obs, "Y": y_obs, "Z": z_obs},
                {"alpha": alpha},
            )["result"]
            return {
                "status": "tested",
                "test_name": str(raw["test_name"]),
                "statistic": float(raw["statistic"]),
                "p_value": float(raw["p_value"]),
                "metadata": {
                    **dict(raw.get("metadata", {})),
                    "route": "partial_correlation",
                    "x_kind": x_kind,
                    "y_kind": y_kind,
                    "conditioning_kinds": conditioning_kinds,
                    "n_complete_cases": n_complete,
                },
            }
        raw = _mixed_kernel_test(x=x_obs, y=y_obs, z=z_obs, alpha=alpha)
        return {
            "status": "tested",
            "test_name": str(raw["test_name"]),
            "statistic": float(raw["statistic"]),
            "p_value": float(raw["p_value"]),
            "warnings": [
                "approximate_ci_route: mixed data used kernel conditional-independence approximation"
            ],
            "metadata": {
                **dict(raw.get("metadata", {})),
                "x_kind": x_kind,
                "y_kind": y_kind,
                "conditioning_kinds": conditioning_kinds,
                "n_complete_cases": n_complete,
            },
        }
    except Exception as exc:
        return {
            "status": "error",
            "warnings": [f"ci_test_failed:{type(exc).__name__}:{exc}"],
            "metadata": {"n_complete_cases": n_complete},
        }


def _pair_key(src: str, dst: str) -> tuple[str, str]:
    return (src, dst) if src < dst else (dst, src)


def _format_conditioning_set(conditioning: tuple[str, ...]) -> str:
    if not conditioning:
        return "∅"
    return "{" + ", ".join(conditioning) + "}"


def _format_ci_statement(
    left: str,
    right: str,
    conditioning: tuple[str, ...],
) -> str:
    if conditioning:
        return f"{left} ⟂ {right} | {_format_conditioning_set(conditioning)}"
    return f"{left} ⟂ {right}"


def _ci_constraint_id(left: str, right: str, conditioning: tuple[str, ...]) -> str:
    cond_token = ",".join(conditioning) if conditioning else "_"
    lo, hi = _pair_key(left, right)
    return f"ci:{lo}|{hi}|{cond_token}"


def _implied_ci_constraints(
    graph: CausalGraphModel,
    *,
    max_conditioning_set_size: int = _ALGEBRAIC_MAX_CONDITIONING_SET_SIZE,
) -> list[ImpliedConstraintSpec]:
    from polisyos.foundry.methods.catalog.causal.admg_ops import (
        d_separation,
        m_separation,
    )
    from polisyos.foundry.methods.catalog.causal.pag_completion import cpdag_to_pag

    if graph.graph_type is GraphType.DAG:
        query_graph = graph
        separation = d_separation
    elif graph.graph_type is GraphType.CPDAG:
        query_graph = cpdag_to_pag(graph)
        separation = m_separation
    elif graph.graph_type is GraphType.PAG:
        query_graph = graph
        separation = m_separation
    else:
        return []

    adjacent_pairs = {
        _pair_key(edge.src, edge.dst)
        for edge in graph.edges
        if edge.lag in (None, 0)
    }
    constraints: list[ImpliedConstraintSpec] = []
    for left_idx, left in enumerate(query_graph.nodes):
        for right in query_graph.nodes[left_idx + 1 :]:
            if _pair_key(left, right) in adjacent_pairs:
                continue
            candidates = [
                node for node in query_graph.nodes if node not in {left, right}
            ]
            minimal_sets: list[tuple[str, ...]] = []
            for size in range(
                0,
                min(max_conditioning_set_size, len(candidates)) + 1,
            ):
                separated_sets: list[tuple[str, ...]] = []
                for conditioning in combinations(candidates, size):
                    conditioning_set = tuple(sorted(conditioning))
                    if separation(
                        query_graph,
                        frozenset({left}),
                        frozenset({right}),
                        frozenset(conditioning_set),
                    ):
                        separated_sets.append(conditioning_set)
                if separated_sets:
                    minimal_sets = sorted(set(separated_sets))
                    break
            for conditioning_set in minimal_sets:
                constraints.append(
                    ImpliedConstraintSpec(
                        constraint_id=_ci_constraint_id(left, right, conditioning_set),
                        family=AlgebraicConstraintFamily.CI,
                        statement=_format_ci_statement(left, right, conditioning_set),
                        variables=(left, right),
                        conditioning_set=conditioning_set,
                    )
                )
    return constraints


def _covariance(matrix: np.ndarray) -> np.ndarray:
    centered = np.asarray(matrix, dtype=float) - np.mean(matrix, axis=0, keepdims=True)
    return np.cov(centered, rowvar=False, ddof=1)


def _tetrad_value(
    matrix: np.ndarray,
    *,
    left_pairs: tuple[tuple[int, int], tuple[int, int]],
    right_pairs: tuple[tuple[int, int], tuple[int, int]],
) -> float:
    cov = _covariance(matrix)
    return float(
        cov[left_pairs[0]] * cov[left_pairs[1]]
        - cov[right_pairs[0]] * cov[right_pairs[1]]
    )


def _tetrad_pairings() -> tuple[tuple[str, tuple[tuple[int, int], tuple[int, int]], tuple[tuple[int, int], tuple[int, int]]], ...]:
    return (
        ("ab_cd_vs_ac_bd", ((0, 1), (2, 3)), ((0, 2), (1, 3))),
        ("ab_cd_vs_ad_bc", ((0, 1), (2, 3)), ((0, 3), (1, 2))),
        ("ac_bd_vs_ad_bc", ((0, 2), (1, 3)), ((0, 3), (1, 2))),
    )


def _tetrad_statement(variables: tuple[str, str, str, str], label: str) -> str:
    a, b, c, d = variables
    if label == "ab_cd_vs_ac_bd":
        return f"cov({a},{b})cov({c},{d}) - cov({a},{c})cov({b},{d}) = 0"
    if label == "ab_cd_vs_ad_bc":
        return f"cov({a},{b})cov({c},{d}) - cov({a},{d})cov({b},{c}) = 0"
    return f"cov({a},{c})cov({b},{d}) - cov({a},{d})cov({b},{c}) = 0"


def _overcomplete_residual_energy(matrix: np.ndarray, expected_rank: int) -> float:
    cov = _covariance(matrix)
    if cov.ndim != 2:
        raise ValueError("overcomplete covariance matrix must be 2D")
    eigenvalues = np.linalg.eigvalsh(cov)
    eigenvalues = np.clip(np.sort(eigenvalues)[::-1], 0.0, None)
    total = float(np.sum(eigenvalues ** 2))
    if total <= 1e-12:
        return 0.0
    tail = float(np.sum(eigenvalues[expected_rank:] ** 2))
    return float(math.sqrt(max(tail, 0.0) / total))


def _evaluate_ci_family(
    *,
    graph: CausalGraphModel,
    data: np.ndarray,
    variable_names: list[str],
    alpha: float,
) -> dict[str, Any]:
    implied_constraints = _implied_ci_constraints(graph)
    index_by_name = {name: idx for idx, name in enumerate(variable_names)}
    raw_results: list[dict[str, Any]] = []
    warnings: list[str] = []

    for constraint in implied_constraints:
        missing = [
            name
            for name in (*constraint.variables, *constraint.conditioning_set)
            if name not in index_by_name
        ]
        if missing:
            warnings.append(
                f"ci_constraint_skipped:{constraint.constraint_id}:missing_variables={sorted(missing)}"
            )
            continue
        left = data[:, index_by_name[constraint.variables[0]]]
        right = data[:, index_by_name[constraint.variables[1]]]
        conditioning = (
            np.column_stack([data[:, index_by_name[name]] for name in constraint.conditioning_set])
            if constraint.conditioning_set
            else None
        )
        raw = _run_ci_test(x=left, y=right, z=conditioning, alpha=alpha)
        raw_results.append({"constraint": constraint, **raw})
        warnings.extend(raw.get("warnings", []))

    p_values = [
        float(entry["p_value"])
        for entry in raw_results
        if entry.get("status") == "tested" and entry.get("p_value") is not None
    ]
    adjusted = iter(_bh_adjust(p_values))

    violations: list[ConstraintEvaluationResult] = []
    tested_count = 0
    for entry in raw_results:
        if entry.get("status") != "tested" or entry.get("p_value") is None:
            if entry.get("status") in {"error", "unsupported", "skipped"}:
                warnings.append(
                    f"ci_constraint_{entry.get('status')}:{entry['constraint'].constraint_id}"
                )
            continue
        tested_count += 1
        adjusted_p = float(next(adjusted))
        route = str(entry.get("metadata", {}).get("route", ""))
        severity = (
            "blocker"
            if route in {"partial_correlation", "g_test", "conditional_g_test"}
            else "warning"
        )
        if adjusted_p < alpha:
            violations.append(
                ConstraintEvaluationResult(
                    constraint_id=entry["constraint"].constraint_id,
                    family=AlgebraicConstraintFamily.CI,
                    status="violated",
                    statistic=float(entry["statistic"]),
                    p_value=float(entry["p_value"]),
                    adjusted_p_value=adjusted_p,
                    severity=severity,
                    warnings=list(entry.get("warnings", [])),
                    metadata=dict(entry.get("metadata", {})),
                )
            )

    return {
        "family": AlgebraicConstraintFamily.CI,
        "implied_constraints": implied_constraints,
        "violations": violations,
        "tested_count": tested_count,
        "warnings": warnings,
    }


def _evaluate_tetrad_family(
    *,
    blocks: list[AlgebraicBlockSpec],
    data: np.ndarray,
    variable_names: list[str],
    alpha: float,
    seed: int,
) -> dict[str, Any]:
    index_by_name = {name: idx for idx, name in enumerate(variable_names)}
    implied_constraints: list[ImpliedConstraintSpec] = []
    raw_results: list[dict[str, Any]] = []
    warnings: list[str] = []
    tested_count = 0

    rng = np.random.default_rng(seed + 17)
    for block in blocks:
        missing = [name for name in block.variables if name not in index_by_name]
        if missing:
            warnings.append(
                f"tetrad_block_skipped:{block.block_id}:missing_variables={sorted(missing)}"
            )
            continue
        block_matrix = np.column_stack([data[:, index_by_name[name]] for name in block.variables])
        if any(
            _classify_numeric_series(block_matrix[:, idx]) != "continuous"
            for idx in range(block_matrix.shape[1])
        ):
            warnings.append(
                f"tetrad_block_skipped:{block.block_id}:noncontinuous_variables"
            )
            continue

        quadruples = (
            list(block.quadruples)
            if block.quadruples
            else list(combinations(block.variables, 4))
        )
        for quadruple in quadruples:
            quad_indices = tuple(index_by_name[name] for name in quadruple)
            quad_matrix = np.column_stack([data[:, idx] for idx in quad_indices])
            mask = _complete_case_mask([quad_matrix[:, idx] for idx in range(quad_matrix.shape[1])])
            quad_complete = quad_matrix[mask]
            if quad_complete.shape[0] < 8:
                warnings.append(
                    f"tetrad_constraint_skipped:{block.block_id}:{','.join(quadruple)}:insufficient_complete_cases"
                )
                continue
            for label, left_pairs, right_pairs in _tetrad_pairings():
                spec = ImpliedConstraintSpec(
                    constraint_id=(
                        f"tetrad:{block.block_id}:{','.join(quadruple)}:{label}"
                    ),
                    family=AlgebraicConstraintFamily.TETRAD,
                    statement=_tetrad_statement(tuple(quadruple), label),
                    variables=tuple(quadruple),
                    source_block_id=block.block_id,
                    metadata={"pairing": label},
                )
                implied_constraints.append(spec)
                observed = _tetrad_value(
                    quad_complete,
                    left_pairs=left_pairs,
                    right_pairs=right_pairs,
                )
                bootstrap_values = np.zeros(_ALGEBRAIC_BOOTSTRAP_DRAWS, dtype=float)
                for draw in range(_ALGEBRAIC_BOOTSTRAP_DRAWS):
                    sampled = _bootstrap_resample(data=quad_complete, rng=rng)
                    bootstrap_values[draw] = _tetrad_value(
                        sampled,
                        left_pairs=left_pairs,
                        right_pairs=right_pairs,
                    )
                ci_lower, ci_upper = np.quantile(
                    bootstrap_values,
                    [alpha / 2.0, 1.0 - alpha / 2.0],
                )
                std = float(np.std(bootstrap_values, ddof=1))
                if std <= 1e-12:
                    p_value = 1.0 if abs(observed) <= 1e-12 else 0.0
                else:
                    z_score = abs(float(observed)) / std
                    p_value = float(math.erfc(z_score / math.sqrt(2.0)))
                raw_results.append(
                    {
                        "constraint": spec,
                        "statistic": float(observed),
                        "p_value": max(0.0, min(1.0, float(p_value))),
                        "raw_reject": bool(ci_lower > 0.0 or ci_upper < 0.0),
                        "metadata": {
                            "route": "bootstrap_tetrad",
                            "bootstrap_draws": _ALGEBRAIC_BOOTSTRAP_DRAWS,
                            "ci_lower": float(ci_lower),
                            "ci_upper": float(ci_upper),
                            "bootstrap_std": std,
                        },
                    }
                )
                tested_count += 1

    adjusted_values = _bh_adjust([float(entry["p_value"]) for entry in raw_results])
    violations: list[ConstraintEvaluationResult] = []
    for entry, adjusted_p in zip(raw_results, adjusted_values, strict=False):
        if entry["raw_reject"] and adjusted_p < alpha:
            violations.append(
                ConstraintEvaluationResult(
                    constraint_id=entry["constraint"].constraint_id,
                    family=AlgebraicConstraintFamily.TETRAD,
                    status="violated",
                    statistic=float(entry["statistic"]),
                    p_value=float(entry["p_value"]),
                    adjusted_p_value=float(adjusted_p),
                    severity="warning",
                    metadata=dict(entry["metadata"]),
                )
            )

    return {
        "family": AlgebraicConstraintFamily.TETRAD,
        "implied_constraints": implied_constraints,
        "violations": violations,
        "tested_count": tested_count,
        "warnings": warnings,
    }


def _evaluate_overcomplete_family(
    *,
    blocks: list[AlgebraicBlockSpec],
    data: np.ndarray,
    variable_names: list[str],
    alpha: float,
    seed: int,
) -> dict[str, Any]:
    index_by_name = {name: idx for idx, name in enumerate(variable_names)}
    implied_constraints: list[ImpliedConstraintSpec] = []
    raw_results: list[dict[str, Any]] = []
    warnings: list[str] = []
    tested_count = 0

    rng = np.random.default_rng(seed + 29)
    for block in blocks:
        missing = [name for name in block.variables if name not in index_by_name]
        if missing:
            warnings.append(
                f"overcomplete_block_skipped:{block.block_id}:missing_variables={sorted(missing)}"
            )
            continue
        block_matrix = np.column_stack([data[:, index_by_name[name]] for name in block.variables])
        if any(
            _classify_numeric_series(block_matrix[:, idx]) != "continuous"
            for idx in range(block_matrix.shape[1])
        ):
            warnings.append(
                f"overcomplete_block_skipped:{block.block_id}:noncontinuous_variables"
            )
            continue
        mask = _complete_case_mask([block_matrix[:, idx] for idx in range(block_matrix.shape[1])])
        complete = block_matrix[mask]
        if complete.shape[0] <= max(8, int(block.expected_rank or 0) + 2):
            warnings.append(
                f"overcomplete_block_skipped:{block.block_id}:insufficient_complete_cases"
            )
            continue

        threshold = (
            float(block.max_residual_energy)
            if block.max_residual_energy is not None
            else 0.05
        )
        spec = ImpliedConstraintSpec(
            constraint_id=f"overcomplete:{block.block_id}:rank<={block.expected_rank}",
            family=AlgebraicConstraintFamily.OVERCOMPLETE,
            statement=(
                f"residual_energy(cov({', '.join(block.variables)}), "
                f"rank<={block.expected_rank}) <= {threshold:.4f}"
            ),
            variables=tuple(block.variables),
            source_block_id=block.block_id,
            metadata={"expected_rank": block.expected_rank, "max_residual_energy": threshold},
        )
        implied_constraints.append(spec)
        observed = _overcomplete_residual_energy(complete, int(block.expected_rank or 1))
        bootstrap_values = np.zeros(_ALGEBRAIC_BOOTSTRAP_DRAWS, dtype=float)
        for draw in range(_ALGEBRAIC_BOOTSTRAP_DRAWS):
            sampled = _bootstrap_resample(data=complete, rng=rng)
            bootstrap_values[draw] = _overcomplete_residual_energy(
                sampled,
                int(block.expected_rank or 1),
            )
        lower_bound, upper_bound = np.quantile(
            bootstrap_values,
            [alpha / 2.0, 1.0 - alpha / 2.0],
        )
        raw_results.append(
            {
                "constraint": spec,
                "statistic": float(observed),
                "p_value": float(np.mean(bootstrap_values <= threshold)),
                "raw_reject": bool(lower_bound > threshold),
                "metadata": {
                    "route": "bootstrap_overcomplete_rank",
                    "bootstrap_draws": _ALGEBRAIC_BOOTSTRAP_DRAWS,
                    "expected_rank": int(block.expected_rank or 1),
                    "max_residual_energy": threshold,
                    "bootstrap_lower_bound": float(lower_bound),
                    "bootstrap_upper_bound": float(upper_bound),
                },
            }
        )
        tested_count += 1

    adjusted_values = _bh_adjust([float(entry["p_value"]) for entry in raw_results])
    violations: list[ConstraintEvaluationResult] = []
    for entry, adjusted_p in zip(raw_results, adjusted_values, strict=False):
        if entry["raw_reject"] and adjusted_p < alpha:
            violations.append(
                ConstraintEvaluationResult(
                    constraint_id=entry["constraint"].constraint_id,
                    family=AlgebraicConstraintFamily.OVERCOMPLETE,
                    status="violated",
                    statistic=float(entry["statistic"]),
                    p_value=float(entry["p_value"]),
                    adjusted_p_value=float(adjusted_p),
                    severity="warning",
                    metadata=dict(entry["metadata"]),
                )
            )

    return {
        "family": AlgebraicConstraintFamily.OVERCOMPLETE,
        "implied_constraints": implied_constraints,
        "violations": violations,
        "tested_count": tested_count,
        "warnings": warnings,
    }


def _suggested_repairs(
    violations: list[ConstraintEvaluationResult],
) -> list[str]:
    families = {violation.family for violation in violations}
    suggestions: list[str] = []
    if AlgebraicConstraintFamily.CI in families:
        suggestions.append(
            "Revisit missing edges/orientations or rerun discovery with a latent-aware method."
        )
    if AlgebraicConstraintFamily.TETRAD in families:
        suggestions.append(
            "Revisit the declared measurement block behind the violated tetrad constraints."
        )
    if AlgebraicConstraintFamily.OVERCOMPLETE in families:
        suggestions.append(
            "Revisit the declared expected rank or overcomplete block definition."
        )
    return suggestions


def _build_algebraic_metadata_summary(
    report: AlgebraicConstraintReport,
) -> dict[str, Any]:
    return {
        "n_implied_constraints": report.n_implied_constraints,
        "n_violated_constraints": report.n_violated_constraints,
        "tested_by_family": dict(report.tested_by_family),
        "violated_by_family": dict(report.violated_by_family),
        "warnings": list(report.warnings),
    }


def _stamp_algebraic_constraint_audit(
    report: CausalDiscoveryReport,
    *,
    data: np.ndarray,
    variable_names: list[str],
    significance_level: float,
    seed: int,
    algebraic_blocks: list[AlgebraicBlockSpec] | None = None,
    degraded_reason: str | None = None,
) -> CausalDiscoveryReport:
    graph = _inject_algebraic_blocks_metadata(
        report.graph,
        algebraic_blocks=list(algebraic_blocks or ()),
    )
    updated_report = report.model_copy(update={"graph": graph})

    algebraic_report: AlgebraicConstraintReport
    degraded = degraded_reason
    if degraded is None and bool(updated_report.metadata.get("fallback")):
        degraded = "algebraic_audit_degraded:discovery_fallback"

    if degraded is not None:
        algebraic_report = AlgebraicConstraintReport(
            severity="warning",
            warnings=[degraded],
        )
    else:
        try:
            algebraic_report = _run_algebraic_constraint_audit(
                graph=graph,
                data=data,
                variable_names=variable_names,
                significance_level=significance_level,
                seed=seed,
            )
        except Exception as exc:
            warning = f"algebraic_audit_failed:{type(exc).__name__}:{exc}"
            algebraic_report = AlgebraicConstraintReport(
                severity="warning",
                warnings=[warning],
            )
            updated_report = updated_report.model_copy(
                update={"warnings": [*updated_report.warnings, warning]}
            )

    metadata = {
        **dict(updated_report.metadata),
        "algebraic_constraints_summary": _build_algebraic_metadata_summary(algebraic_report),
        "algebraic_constraint_severity": algebraic_report.severity,
        "algebraic_constraint_families_run": [
            family.value for family in algebraic_report.families_run
        ],
    }
    return updated_report.model_copy(
        update={
            "algebraic_constraints": algebraic_report,
            "metadata": metadata,
        }
    )


def _run_algebraic_constraint_audit(
    *,
    graph: CausalGraphModel,
    data: np.ndarray,
    variable_names: list[str],
    significance_level: float,
    seed: int,
) -> AlgebraicConstraintReport:
    implied_constraints: list[ImpliedConstraintSpec] = []
    violations: list[ConstraintEvaluationResult] = []
    warnings: list[str] = []
    families_run: list[AlgebraicConstraintFamily] = []
    tested_by_family: dict[str, int] = {}
    violated_by_family: dict[str, int] = {}

    ci_result = _evaluate_ci_family(
        graph=graph,
        data=data,
        variable_names=variable_names,
        alpha=significance_level,
    )
    families_run.append(AlgebraicConstraintFamily.CI)
    implied_constraints.extend(ci_result["implied_constraints"])
    violations.extend(ci_result["violations"])
    warnings.extend(ci_result["warnings"])
    tested_by_family[AlgebraicConstraintFamily.CI.value] = int(ci_result["tested_count"])
    violated_by_family[AlgebraicConstraintFamily.CI.value] = len(ci_result["violations"])

    raw_blocks = graph.metadata.get("algebraic_blocks")
    algebraic_blocks = _validate_algebraic_blocks(raw_blocks)
    tetrad_blocks = [
        block for block in algebraic_blocks if block.family is AlgebraicConstraintFamily.TETRAD
    ]
    if tetrad_blocks:
        tetrad_result = _evaluate_tetrad_family(
            blocks=tetrad_blocks,
            data=data,
            variable_names=variable_names,
            alpha=significance_level,
            seed=seed,
        )
        families_run.append(AlgebraicConstraintFamily.TETRAD)
        implied_constraints.extend(tetrad_result["implied_constraints"])
        violations.extend(tetrad_result["violations"])
        warnings.extend(tetrad_result["warnings"])
        tested_by_family[AlgebraicConstraintFamily.TETRAD.value] = int(
            tetrad_result["tested_count"]
        )
        violated_by_family[AlgebraicConstraintFamily.TETRAD.value] = len(
            tetrad_result["violations"]
        )

    overcomplete_blocks = [
        block
        for block in algebraic_blocks
        if block.family is AlgebraicConstraintFamily.OVERCOMPLETE
    ]
    if overcomplete_blocks:
        overcomplete_result = _evaluate_overcomplete_family(
            blocks=overcomplete_blocks,
            data=data,
            variable_names=variable_names,
            alpha=significance_level,
            seed=seed,
        )
        families_run.append(AlgebraicConstraintFamily.OVERCOMPLETE)
        implied_constraints.extend(overcomplete_result["implied_constraints"])
        violations.extend(overcomplete_result["violations"])
        warnings.extend(overcomplete_result["warnings"])
        tested_by_family[AlgebraicConstraintFamily.OVERCOMPLETE.value] = int(
            overcomplete_result["tested_count"]
        )
        violated_by_family[AlgebraicConstraintFamily.OVERCOMPLETE.value] = len(
            overcomplete_result["violations"]
        )

    return AlgebraicConstraintReport(
        severity=_max_severity([violation.severity for violation in violations]),
        suggested_repairs=_suggested_repairs(violations),
        families_run=families_run,
        n_implied_constraints=len(implied_constraints),
        n_violated_constraints=len(violations),
        tested_by_family=tested_by_family,
        violated_by_family=violated_by_family,
        warnings=_dedupe_preserve_order(warnings),
        implied_constraints_preview=implied_constraints,
        violated_constraints_preview=violations,
    )


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
    algebraic_blocks = _validate_algebraic_blocks(params.get("algebraic_blocks"))
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
        dagma_params["algebraic_blocks"] = [block.model_dump(mode="json") for block in algebraic_blocks]
        dagma_output = run_dagma_discovery(state=tab_data, params=dagma_params)
        dagma_report_raw = dagma_output["report"]
        dagma_report = (
            dagma_report_raw
            if isinstance(dagma_report_raw, CausalDiscoveryReport)
            else CausalDiscoveryReport.model_validate(dagma_report_raw)
        )
        dagma_report = dagma_report.model_copy(
            update={
                "metadata": {
                    **dict(dagma_report.metadata),
                    **ci_backend_metadata(ci_backend),
                    "scale_backend_requested": scale_backend.requested,
                    "scale_backend_used": "dagma",
                    "scale_backend_fallback_reason": scale_backend.fallback_reason,
                    "trigger_algorithm": algorithm,
                }
            }
        )
        dagma_failed = bool(dagma_report.metadata.get("fallback"))
        if not dagma_failed or scale_backend.requested == "dagma":
            return {"report": dagma_report, "__determinism_tier__": DeterminismTier.STATISTICAL}

        fallback_reason = "dagma_auto_fallback_to_classic"
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
        report = _stamp_algebraic_constraint_audit(
            _fallback_report(
                state=tab_data,
                algorithm=algorithm,
                significance_level=significance_level,
                warnings=warnings,
                elapsed_seconds=float(time.perf_counter() - started),
                params=params,
                ci_backend=ci_backend,
                scale_backend=scale_backend,
            ),
            data=tab_data.data,
            variable_names=tab_data.variable_names,
            significance_level=significance_level,
            seed=seed,
            algebraic_blocks=algebraic_blocks,
        )
        return {"report": report, "__determinism_tier__": DeterminismTier.STATISTICAL}

    try:
        graph, resolved_graph, conversion_warnings = _build_graph(
            algorithm=algorithm,
            adjacency=base_result.adjacency,
            variable_names=tab_data.variable_names,
            extra_metadata=base_result.metadata,
        )
        graph = _inject_algebraic_blocks_metadata(
            graph,
            algebraic_blocks=algebraic_blocks,
        )
    except Exception as exc:
        warnings.append(
            f"{_method_name_for_algorithm(algorithm).upper()} graph conversion failed: {exc}"
        )
        report = _stamp_algebraic_constraint_audit(
            _fallback_report(
                state=tab_data,
                algorithm=algorithm,
                significance_level=significance_level,
                warnings=warnings,
                elapsed_seconds=float(time.perf_counter() - started),
                params=params,
                ci_backend=ci_backend,
                scale_backend=scale_backend,
            ),
            data=tab_data.data,
            variable_names=tab_data.variable_names,
            significance_level=significance_level,
            seed=seed,
            algebraic_blocks=algebraic_blocks,
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

    report = _stamp_algebraic_constraint_audit(
        CausalDiscoveryReport(
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
        ),
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
    tags={"causal", "discovery", "constraint-based", "pc"},
)
class PCDiscovery:
    """PC discovery public type."""
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
            ParameterSpec(name="indep_test", default="fisherz"),
            ParameterSpec(name="stable", default=True),
            ParameterSpec(name="uc_rule", default=0),
            ParameterSpec(name="uc_priority", default=2),
            ParameterSpec(name="algebraic_blocks", default=[]),
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
        when_to_use="Causal structure learning from observational data; recover Markov equivalence class under faithfulness",
        citations=(
            "Spirtes, P., Glymour, C. & Scheines, R. (2000). Causation, Prediction, and Search. MIT Press.",
        ),
        when_not_to_use="Strong selection bias; many latent confounders; very high-dimensional with small N",
        typical_min_obs=200,
        output_interpretation="CPDAG (PC) or PAG (FCI) encoding causal structure. Directed edges = identified directions. Undirected = observationally equivalent.",
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
    """FCI discovery public type."""
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
            ParameterSpec(name="indep_test", default="fisherz"),
            ParameterSpec(name="depth", default=-1),
            ParameterSpec(name="max_path_length", default=-1),
            ParameterSpec(name="algebraic_blocks", default=[]),
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
        when_to_use="Causal structure learning from observational data; recover Markov equivalence class under faithfulness",
        citations=(
            "Spirtes, P., Glymour, C. & Scheines, R. (2000). Causation, Prediction, and Search. MIT Press.",
            "Colombo, D. et al. (2012). Learning high-dimensional directed acyclic graphs with latent and selection variables. Annals of Statistics, 40(1), 294-321.",
        ),
        when_not_to_use="Strong selection bias; many latent confounders; very high-dimensional with small N",
        typical_min_obs=200,
        output_interpretation="CPDAG (PC) or PAG (FCI) encoding causal structure. Directed edges = identified directions. Undirected = observationally equivalent.",
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
    """GES discovery public type."""
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
            ParameterSpec(name="score_func", default="local_score_BIC"),
            ParameterSpec(name="max_parents", default=None),
            ParameterSpec(name="algebraic_blocks", default=[]),
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
        when_to_use="Causal structure learning from observational data; recover Markov equivalence class under faithfulness",
        citations=(
            "Chickering, D. (2002). Optimal structure identification with greedy search. JMLR, 3, 507-554.",
        ),
        when_not_to_use="Strong selection bias; many latent confounders; very high-dimensional with small N",
        typical_min_obs=200,
        output_interpretation="CPDAG (PC) or PAG (FCI) encoding causal structure. Directed edges = identified directions. Undirected = observationally equivalent.",
    )

    @staticmethod
    def pure_step(state: TabularCausalDiscoveryData, params: Mapping[str, Any]) -> dict[str, Any]:
        return _run_constraint_discovery(state=state, params=params, algorithm="ges")


__all__ = [
    "PCDiscovery",
    "FCIDiscovery",
    "GESDiscovery",
]
