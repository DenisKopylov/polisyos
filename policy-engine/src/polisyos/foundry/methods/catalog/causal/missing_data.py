"""missing_data — Foundry methods for M-graph missing data analysis.

Three registered methods in the ``causal.missing_data`` namespace:

  RecoverabilityTest  — test whether P(S) is recoverable from P*(V)
  OrderedRecovery     — build the recovery EstimandAST via ordered fixing operator
  FullLawIdentify     — two-stage pipeline: recover P(V) then identify P(Y|do(X))

All three are thin Foundry wrappers around pure algorithm functions in
``recoverability_engine.py``.

References
----------
Mohan, K. & Pearl, J. (2021). "Graphical Models for Processing Missing Data."
    Journal of the American Statistical Association.
Mohan, K., Pearl, J. & Tian, J. (2013). "Missing Data as a Causal and
    Probabilistic Problem." UAI 2013.
Nabi, R., Bhattacharya, R. & Shpitser, I. (2020). "Full law identification in
    graphical models of missing data."
"""

from __future__ import annotations

import itertools
import logging
from typing import Any, ClassVar, Mapping

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

_logger = logging.getLogger(__name__)

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


def _json_slot(name: str) -> SlotSpec:
    return SlotSpec(name, SlotType.SCALAR, Unit(name, "json"))


class ConditionalIndependence(BaseModel):
    """Testable implication X ⊥ Y | Z extracted from an M-graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    x: str
    y: str
    z: tuple[str, ...] = ()


class ImplicationTestResult(BaseModel):
    """Single CI test result with BH-adjusted significance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    implication: ConditionalIndependence
    statistic: float
    p_value: float
    adjusted_p_value: float
    passed: bool
    test_name: str = "adaptive_mgraph_ci"
    metadata: dict[str, Any] = Field(default_factory=dict)


class TestReport(BaseModel):
    """Aggregated M-graph implication test report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    implications_tested: int
    implications_passed: int
    implications_failed: list[tuple[ConditionalIndependence, float]] = Field(default_factory=list)
    overall_valid: bool
    alpha: float = 0.05
    correction_method: str = "benjamini_hochberg"
    test_method: str = "adaptive_mgraph_ci"
    results: list[ImplicationTestResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _observed_nodes(graph: Any, mgraph_meta: Any) -> list[str]:
    """Return nodes that are observable in the M-graph."""
    observed: set[str] = set(mgraph_meta.fully_observed_vars)
    observed.update(pn.proxy_name for pn in mgraph_meta.proxy_nodes)
    observed.update(f"R_{rn.target_variable}" for rn in mgraph_meta.r_nodes)
    return sorted(node for node in observed if node in set(graph.nodes))


def _bh_adjust(p_values: list[float]) -> list[float]:
    """Benjamini-Hochberg p-value adjustment."""
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
    return [float(v) for v in adjusted]


def _coerce_series(values: Any) -> np.ndarray:
    """Convert a dataset column to a 1D numeric vector."""
    arr = np.asarray(values)
    if arr.ndim == 2 and arr.shape[1] == 1:
        arr = arr[:, 0]
    if arr.ndim != 1:
        raise ValueError("Each data column must be one-dimensional")
    if arr.dtype.kind in {"O", "U", "S"}:
        _, inverse = np.unique(arr.astype(str), return_inverse=True)
        return inverse.astype(float)
    return arr.astype(float)


def _raw_series(values: Any) -> np.ndarray:
    """Return a 1D raw series without coercing categorical values."""
    arr = np.asarray(values)
    if arr.ndim == 2 and arr.shape[1] == 1:
        arr = arr[:, 0]
    if arr.ndim != 1:
        raise ValueError("Each data column must be one-dimensional")
    return arr


def _is_missing_scalar(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (float, np.floating)):
        return bool(np.isnan(value))
    return False


def _complete_case_mask(columns: list[np.ndarray]) -> np.ndarray:
    """Mask rows that are present across every supplied raw series."""
    if not columns:
        raise ValueError("At least one column is required")
    n = len(columns[0])
    mask = np.ones(n, dtype=bool)
    for column in columns:
        arr = np.asarray(column)
        if len(arr) != n:
            raise ValueError("Implication test columns must have matching length")
        if arr.dtype.kind in {"f"}:
            mask &= np.isfinite(arr)
        elif arr.dtype.kind in {"i", "u", "b"}:
            mask &= True
        else:
            mask &= np.array([not _is_missing_scalar(value) for value in arr], dtype=bool)
    return mask


def _series_kind(raw: np.ndarray) -> str:
    """Infer whether a series should be treated as continuous or categorical."""
    arr = np.asarray(raw)
    if arr.ndim != 1:
        raise ValueError("Each data column must be one-dimensional")
    if arr.size == 0:
        return "categorical"
    if arr.dtype.kind in {"O", "U", "S", "b"}:
        return "categorical"

    finite = arr[np.isfinite(arr)] if arr.dtype.kind == "f" else arr
    if finite.size == 0:
        return "categorical"
    unique = np.unique(finite)
    if unique.size <= 12 and np.allclose(unique, np.round(unique)):
        return "categorical"
    return "continuous"


def _encode_for_kernel(raw: np.ndarray) -> np.ndarray:
    """Encode a series as a numeric design matrix for kernel-based tests."""
    arr = np.asarray(raw)
    if arr.ndim != 1:
        raise ValueError("Each data column must be one-dimensional")
    if _series_kind(arr) == "categorical":
        labels = arr.astype(str)
        _, inverse = np.unique(labels, return_inverse=True)
        return np.eye(int(np.max(inverse)) + 1, dtype=float)[inverse]
    return arr.astype(float).reshape(-1, 1)


def _build_contingency_table(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, int, int]:
    x_labels, x_codes = np.unique(x.astype(str), return_inverse=True)
    y_labels, y_codes = np.unique(y.astype(str), return_inverse=True)
    table = np.zeros((len(x_labels), len(y_labels)), dtype=int)
    np.add.at(table, (x_codes, y_codes), 1)
    return table, len(x_labels), len(y_labels)


def _g_test_from_table(table: np.ndarray) -> tuple[float, float, dict[str, Any]]:
    from scipy.stats import chi2, chi2_contingency

    if table.ndim != 2:
        raise ValueError("Contingency table must be 2D")
    if table.shape[0] < 2 or table.shape[1] < 2 or int(table.sum()) == 0:
        return 0.0, 1.0, {"degrees_of_freedom": 0, "degenerate": True}

    try:
        statistic, _, dof, _ = chi2_contingency(table, correction=False, lambda_="log-likelihood")
    except ValueError:
        return 0.0, 1.0, {"degrees_of_freedom": 0, "degenerate": True}

    if dof <= 0:
        return 0.0, 1.0, {"degrees_of_freedom": int(dof), "degenerate": True}
    p_value = float(chi2.sf(float(statistic), int(dof)))
    return float(statistic), p_value, {"degrees_of_freedom": int(dof), "degenerate": False}


def _conditional_g_test(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> tuple[float, float, dict[str, Any]]:
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
        valid_strata += 1
        total_statistic += statistic
        total_dof += int(meta["degrees_of_freedom"])

    if total_dof <= 0 or valid_strata == 0:
        return 0.0, 1.0, {
            "degrees_of_freedom": 0,
            "valid_strata": valid_strata,
            "skipped_strata": skipped_strata,
            "degenerate": True,
        }

    from scipy.stats import chi2

    p_value = float(chi2.sf(float(total_statistic), total_dof))
    return float(total_statistic), p_value, {
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
    """Approximate mixed-data CI via kernel tests on encoded columns."""
    from polisyos.foundry.methods.catalog.causal.independence_tests import (
        HSICIndependenceTest,
        KCIConditionalTest,
    )

    x_enc = _encode_for_kernel(x)
    y_enc = _encode_for_kernel(y)

    if z is None or z.size == 0:
        raw = HSICIndependenceTest.pure_step({"X": x_enc, "Y": y_enc}, {"alpha": alpha, "n_bootstrap": 99})["result"]
        return {
            "test_name": "hsic_mixed",
            "statistic": float(raw["statistic"]),
            "p_value": float(raw["p_value"]),
            "passed": bool(raw["passed"]),
            "critical_value": alpha,
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
        "passed": bool(raw["passed"]),
        "critical_value": alpha,
        "metadata": {
            **dict(raw.get("metadata", {})),
            "route": "kci_mixed",
            "approximation": "kernel_conditional_independence",
        },
    }


def _get_column(
    data: Mapping[str, Any] | np.ndarray,
    variable: str,
    variable_order: tuple[str, ...] | None = None,
) -> np.ndarray:
    if isinstance(data, Mapping):
        if variable not in data:
            raise KeyError(f"Missing data column for variable {variable!r}")
        return _coerce_series(data[variable])
    if variable_order is None:
        raise ValueError(
            "variable_order is required when data is provided as an ndarray"
        )
    try:
        idx = variable_order.index(variable)
    except ValueError as exc:
        raise KeyError(f"Variable {variable!r} not present in variable_order") from exc
    return _coerce_series(data[:, idx])


def _raw_column(
    data: Mapping[str, Any] | np.ndarray,
    variable: str,
    variable_order: tuple[str, ...] | None = None,
) -> np.ndarray:
    """Return a raw 1D column while preserving categorical dtype information."""
    if isinstance(data, Mapping):
        if variable not in data:
            raise KeyError(f"Missing data column for variable {variable!r}")
        return _raw_series(data[variable])
    if variable_order is None:
        raise ValueError(
            "variable_order is required when data is provided as an ndarray"
        )
    try:
        idx = variable_order.index(variable)
    except ValueError as exc:
        raise KeyError(f"Variable {variable!r} not present in variable_order") from exc
    return _raw_series(data[:, idx])


def _minimal_separating_sets(
    *,
    graph: Any,
    observed_nodes: list[str],
    max_conditioning_set_size: int,
) -> list[ConditionalIndependence]:
    from polisyos.foundry.methods.catalog.causal.admg_ops import m_separation

    implications: list[ConditionalIndependence] = []
    for x, y in itertools.combinations(observed_nodes, 2):
        candidates = [node for node in observed_nodes if node not in {x, y}]
        found = False
        for size in range(0, min(max_conditioning_set_size, len(candidates)) + 1):
            for z in itertools.combinations(candidates, size):
                if m_separation(
                    graph,
                    x_set=frozenset({x}),
                    y_set=frozenset({y}),
                    z_set=frozenset(z),
                ):
                    implications.append(
                        ConditionalIndependence(x=x, y=y, z=tuple(sorted(z)))
                    )
                    found = True
                    break
            if found:
                break
    # Deduplicate while preserving order
    seen: set[ConditionalIndependence] = set()
    deduped: list[ConditionalIndependence] = []
    for implication in implications:
        if implication in seen:
            continue
        seen.add(implication)
        deduped.append(implication)
    return deduped


def testable_implications(
    graph: Any,
    mgraph_meta: Any,
    *,
    max_conditioning_set_size: int = 2,
) -> list[ConditionalIndependence]:
    """Derive testable conditional independences from an M-graph."""
    observed = _observed_nodes(graph, mgraph_meta)
    return _minimal_separating_sets(
        graph=graph,
        observed_nodes=observed,
        max_conditioning_set_size=max_conditioning_set_size,
    )


def test_mgraph_implications(
    *,
    graph: Any,
    mgraph_meta: Any,
    data: Mapping[str, Any] | np.ndarray,
    implications: list[ConditionalIndependence] | None = None,
    alpha: float = 0.05,
    max_conditioning_set_size: int = 2,
    variable_order: tuple[str, ...] | None = None,
) -> TestReport:
    """Run CI tests for all supplied or graph-derived M-graph implications."""
    from polisyos.foundry.methods.catalog.causal.independence_tests import (
        PartialCorrelationTest,
    )

    if implications is None:
        implications = testable_implications(
            graph,
            mgraph_meta,
            max_conditioning_set_size=max_conditioning_set_size,
        )

    results: list[ImplicationTestResult] = []
    p_values: list[float] = []
    warnings: list[str] = []
    for implication in implications:
        raw_x = _raw_column(data, implication.x, variable_order)
        raw_y = _raw_column(data, implication.y, variable_order)
        raw_z_cols = [
            _raw_column(data, name, variable_order)
            for name in implication.z
        ]
        all_columns = [raw_x, raw_y, *raw_z_cols]
        mask = _complete_case_mask(all_columns)
        if not np.any(mask):
            raise ValueError("Implication test has no complete cases")

        x = _get_column(data, implication.x, variable_order)[mask]
        y = _get_column(data, implication.y, variable_order)[mask]
        z_numeric = (
            np.column_stack([_get_column(data, name, variable_order)[mask] for name in implication.z])
            if implication.z
            else None
        )
        x_kind = _series_kind(raw_x[mask])
        y_kind = _series_kind(raw_y[mask])
        z_kinds = tuple(_series_kind(col[mask]) for col in raw_z_cols)
        all_kinds = (x_kind, y_kind, *z_kinds)
        all_continuous = all(kind == "continuous" for kind in all_kinds)
        all_categorical = all(kind == "categorical" for kind in all_kinds)

        state: dict[str, Any]
        route: str
        if not implication.z:
            if all_categorical:
                table, _, _ = _build_contingency_table(x, y)
                statistic, p_value, meta = _g_test_from_table(table)
                raw = {
                    "test_name": "g_test",
                    "statistic": statistic,
                    "p_value": p_value,
                    "passed": p_value >= alpha,
                    "critical_value": alpha,
                    "metadata": {
                        **meta,
                        "route": "g_test",
                        "x_kind": x_kind,
                        "y_kind": y_kind,
                        "conditioning_kinds": (),
                        "n_complete_cases": int(mask.sum()),
                    },
                }
                route = "g_test"
            elif all_continuous:
                state = {"X": x, "Y": y}
                raw = PartialCorrelationTest.pure_step(state, {"alpha": alpha})["result"]
                raw = {
                    **raw,
                    "metadata": {
                        **dict(raw.get("metadata", {})),
                        "route": "partial_correlation",
                        "x_kind": x_kind,
                        "y_kind": y_kind,
                        "conditioning_kinds": (),
                        "n_complete_cases": int(mask.sum()),
                    },
                }
                route = "partial_correlation"
            else:
                raw = _mixed_kernel_test(x=x, y=y, z=None, alpha=alpha)
                raw["metadata"] = {
                    **dict(raw.get("metadata", {})),
                    "x_kind": x_kind,
                    "y_kind": y_kind,
                    "conditioning_kinds": (),
                    "n_complete_cases": int(mask.sum()),
                }
                route = raw["test_name"]
        else:
            if all_categorical:
                table_stat, p_value, meta = _conditional_g_test(x, y, z_numeric)
                raw = {
                    "test_name": "conditional_g_test",
                    "statistic": table_stat,
                    "p_value": p_value,
                    "passed": p_value >= alpha,
                    "critical_value": alpha,
                    "metadata": {
                        **meta,
                        "route": "conditional_g_test",
                        "x_kind": x_kind,
                        "y_kind": y_kind,
                        "conditioning_kinds": z_kinds,
                        "n_complete_cases": int(mask.sum()),
                    },
                }
                route = "conditional_g_test"
            elif all_continuous:
                state = {"X": x, "Y": y, "Z": z_numeric}
                raw = PartialCorrelationTest.pure_step(state, {"alpha": alpha})["result"]
                raw = {
                    **raw,
                    "metadata": {
                        **dict(raw.get("metadata", {})),
                        "route": "partial_correlation",
                        "x_kind": x_kind,
                        "y_kind": y_kind,
                        "conditioning_kinds": z_kinds,
                        "n_complete_cases": int(mask.sum()),
                    },
                }
                route = "partial_correlation"
            else:
                raw = _mixed_kernel_test(x=x, y=y, z=z_numeric, alpha=alpha)
                raw["metadata"] = {
                    **dict(raw.get("metadata", {})),
                    "x_kind": x_kind,
                    "y_kind": y_kind,
                    "conditioning_kinds": z_kinds,
                    "n_complete_cases": int(mask.sum()),
                }
                route = raw["test_name"]

        if route in {"hsic_mixed", "kci_mixed"}:
            warnings.append(
                f"{implication.x} ⟂ {implication.y} | {list(implication.z)} used {route} approximation"
            )

        p_values.append(float(raw["p_value"]))
        results.append(
            ImplicationTestResult(
                implication=implication,
                statistic=float(raw["statistic"]),
                p_value=float(raw["p_value"]),
                adjusted_p_value=float(raw["p_value"]),
                passed=bool(raw["passed"]),
                test_name=str(raw["test_name"]),
                metadata=dict(raw.get("metadata", {})),
            )
        )

    adjusted = _bh_adjust(p_values)
    adjusted_results: list[ImplicationTestResult] = []
    failed: list[tuple[ConditionalIndependence, float]] = []
    passed_count = 0
    for result, adj_p in zip(results, adjusted, strict=False):
        passed = bool(adj_p >= alpha)
        if passed:
            passed_count += 1
        else:
            failed.append((result.implication, float(adj_p)))
        adjusted_results.append(
            result.model_copy(
                update={
                    "adjusted_p_value": float(adj_p),
                    "passed": passed,
                }
            )
        )

    return TestReport(
        implications_tested=len(adjusted_results),
        implications_passed=passed_count,
        implications_failed=failed,
        overall_valid=(passed_count == len(adjusted_results)),
        alpha=alpha,
        test_method="adaptive_mgraph_ci",
        results=adjusted_results,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# RecoverabilityTest
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.missing_data",
    version="1.0.0",
    tags={"causal", "missing-data", "recoverability", "m-graph", "structural"},
)
class RecoverabilityTest:
    """Test whether a query P(S) is recoverable from incomplete data.

    Implements the Mohan & Pearl (2021) graphical recoverability criterion
    (Theorem 1): P(S) is recoverable iff no R_V ∈ desc(V) in G' = G[V∪R \\ proxies].

    Input
    -----
    mgraph_data : dict
        Serialised CausalGraphModel with graph_type="mgraph" and
        ``metadata["mgraph"]`` containing the serialised MGraphMetadata.

    Output
    ------
    recoverability_result : dict
        status, query_variables, blocking_r_nodes, proof_steps, algorithm_version.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="recoverability_test",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset({_json_slot("mgraph_data")}),
        output_slots=frozenset({_json_slot("recoverability_result")}),
        parameters=(
            ParameterSpec(name="query_variables", default=[]),
            ParameterSpec(name="dataset_ref", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Test recoverability of a query P(S) from incomplete data using "
            "the Mohan & Pearl (2021) M-graph graphical criterion."
        ),
        tags=frozenset({
            "causal", "missing-data", "recoverability", "m-graph",
            "mcar", "mar", "mnar", "structural",
        }),
        citations=(
            "Mohan, K. & Pearl, J. (2021). Graphical Models for Processing "
            "Missing Data. Journal of the American Statistical Association.",
            "Mohan, K., Pearl, J. & Tian, J. (2013). Missing Data as a Causal "
            "and Probabilistic Problem. UAI 2013.",
        ),
        equations={
            "criterion": (
                "P(S) recoverable iff ∀V_i∈S: R_{V_i} ∉ desc(V_i) "
                "in G[V∪R \\ proxy_nodes]"
            ),
        },
        determinism_tier=DeterminismTier.STRICT_CPU,
        required_deps=("numpy",),
        when_to_use=(
            "Before causal analysis when the dataset has systematic missing values; "
            "to determine whether identification is feasible."
        ),
        when_not_to_use="Data is fully observed (no missing values).",
        output_interpretation=(
            "status='recoverable' → safe to proceed with full law identification. "
            "status='not_recoverable' → blocking_r_nodes identifies MNAR variables "
            "that prevent recovery."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
            test_recoverability,
        )
        from polisyos.ir.analytics.causal_graph import CausalGraphModel
        from polisyos.ir.analytics.mgraph import extract_mgraph_metadata

        raw = state["mgraph_data"]
        graph = (
            CausalGraphModel.model_validate(raw)
            if isinstance(raw, dict)
            else raw
        )
        meta = extract_mgraph_metadata(graph)

        qvars_raw = params.get("query_variables", [])
        query_vars = (
            frozenset(qvars_raw)
            if qvars_raw
            else frozenset(meta.substantive_vars)
        )

        result = test_recoverability(
            query_vars=query_vars,
            graph=graph,
            mgraph_meta=meta,
        )

        return {
            "recoverability_result": {
                "status": result.status.value,
                "query_variables": sorted(result.query_variables),
                "blocking_r_nodes": sorted(result.blocking_r_nodes),
                "proof_steps": [
                    {
                        "rule_name": s.rule_name,
                        "antecedent_vars": list(s.antecedent_vars),
                        "consequent_vars": list(s.consequent_vars),
                        "applied_to_graph_state": s.applied_to_graph_state,
                        "depth": s.depth,
                    }
                    for s in result.proof_steps
                ],
                "trace": result.trace,
                "algorithm_version": result.algorithm_version,
            }
        }


# ---------------------------------------------------------------------------
# OrderedRecovery
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.missing_data",
    version="1.0.0",
    tags={"causal", "missing-data", "ordered-recovery", "m-graph", "structural"},
)
class OrderedRecovery:
    """Recover full-data joint P(V) from incomplete data via topological ordering.

    Implements the Mohan, Pearl & Tian (2013) ordered fixing operator:
        P(V) = Π_i P(V_i | V_{<i})
    Each factor is recovered as P*(V_i | V_{<i}, R_{V_i}=1) for MCAR/MAR variables.

    Input
    -----
    mgraph_data : dict
        Serialised CausalGraphModel with graph_type="mgraph".

    Output
    ------
    recovery_estimand : dict
        Serialised EstimandAST with ProductNode of RecoveredDistNode factors.
    ordered_recovery_steps : list[dict]
        Proof steps for the topological recovery sequence.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ordered_recovery",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset({_json_slot("mgraph_data")}),
        output_slots=frozenset({
            _json_slot("recovery_estimand"),
            _json_slot("ordered_recovery_steps"),
        }),
        parameters=(
            ParameterSpec(name="dataset_ref", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Recover full-data joint P(V) from incomplete data using the "
            "ordered fixing operator (Mohan, Pearl & Tian 2013)."
        ),
        tags=frozenset({
            "causal", "missing-data", "ordered-recovery", "m-graph",
            "estimand", "fixing-operator", "structural",
        }),
        citations=(
            "Mohan, K., Pearl, J. & Tian, J. (2013). Missing Data as a Causal "
            "and Probabilistic Problem. UAI 2013.",
            "Mohan, K. & Pearl, J. (2021). Graphical Models for Processing "
            "Missing Data. Journal of the American Statistical Association.",
        ),
        equations={
            "recovery": "P(V) = Π_i P(V_i | V_{<i})",
            "mcar_mar_factor": "P(V_i | V_{<i}) = P*(V_i | V_{<i}, R_{V_i}=1)",
        },
        determinism_tier=DeterminismTier.STRICT_CPU,
        required_deps=("numpy",),
        when_to_use=(
            "After RecoverabilityTest confirms P(V) is recoverable; "
            "to obtain the explicit recovery formula."
        ),
        when_not_to_use=(
            "RecoverabilityTest returned NOT_RECOVERABLE — ordered recovery "
            "will not produce a valid result."
        ),
        output_interpretation=(
            "recovery_estimand is an EstimandAST with a ProductNode of "
            "RecoveredDistNode factors.  Each factor specifies the data query "
            "(variable, conditioning, missingness_indicator, proxy_variable) "
            "needed to estimate that factor from the incomplete dataset."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
            ordered_recovery,
        )
        from polisyos.ir.analytics.causal_graph import CausalGraphModel
        from polisyos.ir.analytics.mgraph import extract_mgraph_metadata

        raw = state["mgraph_data"]
        graph = (
            CausalGraphModel.model_validate(raw)
            if isinstance(raw, dict)
            else raw
        )
        meta = extract_mgraph_metadata(graph)
        dataset_ref = params.get("dataset_ref")

        estimand = ordered_recovery(
            graph=graph,
            mgraph_meta=meta,
            dataset_ref=dataset_ref,
        )

        # Extract proof steps from the estimand's root factors
        steps = []
        from polisyos.ir.analytics.estimand import ProductNode, RecoveredDistNode
        if isinstance(estimand.root, ProductNode):
            for i, factor in enumerate(estimand.root.factors):
                if isinstance(factor, RecoveredDistNode):
                    steps.append({
                        "rule_name": "ORDERED_RECOVERY_STEP",
                        "variable": factor.variable,
                        "conditioning": list(factor.conditioning),
                        "missingness_kind": factor.missingness_kind,
                        "missingness_indicator": factor.missingness_indicator,
                        "proxy_variable": factor.proxy_variable,
                        "depth": i,
                    })

        return {
            "recovery_estimand": estimand.model_dump(mode="json"),
            "ordered_recovery_steps": steps,
        }


# ---------------------------------------------------------------------------
# FullLawIdentify
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.missing_data",
    version="1.0.0",
    tags={"causal", "missing-data", "full-law", "identification", "m-graph"},
)
class FullLawIdentify:
    """Identify P(Y|do(X)) from incomplete data using the full law pipeline.

    Two-stage pipeline (Nabi, Bhattacharya & Shpitser 2020):
      Stage 1: RecoverabilityTest — check if P(V) is recoverable from P*(V).
      Stage 2: ID algorithm — identify P(Y|do(X)) from recovered P(V).

    Input
    -----
    mgraph_data : dict
        Serialised CausalGraphModel with graph_type="mgraph".

    Output
    ------
    identification_result : dict
        status, estimand_ast, proof_steps, algorithm_version, trace.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="full_law_identify",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset({
            _json_slot("mgraph_data"),
            _json_slot("treatment"),
            _json_slot("outcome"),
        }),
        output_slots=frozenset({_json_slot("identification_result")}),
        parameters=(
            ParameterSpec(name="oracle", default="none"),
            ParameterSpec(name="dataset_ref", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Identify causal effects from incomplete data via the full law pipeline "
            "(Nabi, Bhattacharya & Shpitser 2020): recover P(V) then identify P(Y|do(X))."
        ),
        tags=frozenset({
            "causal", "missing-data", "full-law", "identification",
            "m-graph", "id-algorithm",
        }),
        citations=(
            "Nabi, R., Bhattacharya, R. & Shpitser, I. (2020). Full law identification "
            "in graphical models of missing data.",
            "Mohan, K. & Pearl, J. (2021). Graphical Models for Processing Missing Data. "
            "Journal of the American Statistical Association.",
        ),
        equations={
            "pipeline": "P(Y|do(X)) identified from incomplete data via two-stage pipeline",
            "stage1": "Recover P(V) = Π_i P*(V_i|V_{<i}, R_{V_i}=1)",
            "stage2": "Identify P(Y|do(X)) from P(V) via ID algorithm",
        },
        determinism_tier=DeterminismTier.STRICT_CPU,
        required_deps=("numpy",),
        when_to_use=(
            "Causal identification when input data has systematic missingness "
            "(MCAR/MAR/MNAR patterns confirmed via m-graph analysis)."
        ),
        when_not_to_use="Data is fully observed; use standard ID algorithm instead.",
        output_interpretation=(
            "status='identified' → both stages succeeded; estimand_ast contains "
            "the full identification formula. "
            "status='not_recoverable' → Stage 1 failed; identification is impossible "
            "without additional assumptions. "
            "status='hedge_found' / 'oracle_needed' → Stage 2 failed; the causal query "
            "is non-identifiable even with complete data."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
            full_law_identify,
        )
        from polisyos.ir.analytics.causal_graph import CausalGraphModel
        from polisyos.ir.analytics.mgraph import extract_mgraph_metadata

        raw = state["mgraph_data"]
        graph = (
            CausalGraphModel.model_validate(raw)
            if isinstance(raw, dict)
            else raw
        )
        meta = extract_mgraph_metadata(graph)

        treatment_raw = state["treatment"]
        outcome_raw = state["outcome"]
        treatment = (
            frozenset(treatment_raw)
            if isinstance(treatment_raw, (list, tuple, frozenset, set))
            else frozenset({str(treatment_raw)})
        )
        outcome = (
            frozenset(outcome_raw)
            if isinstance(outcome_raw, (list, tuple, frozenset, set))
            else frozenset({str(outcome_raw)})
        )

        oracle = str(params.get("oracle", "none"))
        dataset_ref = params.get("dataset_ref")

        result = full_law_identify(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            mgraph_meta=meta,
            dataset_ref=dataset_ref,
            oracle=oracle,
        )

        estimand_dict = (
            result.estimand_ast.model_dump(mode="json")
            if result.estimand_ast is not None
            else None
        )

        return {
            "identification_result": {
                "status": result.status.value,
                "estimand_ast": estimand_dict,
                "algorithm_version": result.algorithm_version,
                "trace": result.trace,
                "proof_steps": [
                    {
                        "rule_name": s.rule_name,
                        "antecedent_vars": list(s.antecedent_vars),
                        "consequent_vars": list(s.consequent_vars),
                        "applied_to_graph_state": s.applied_to_graph_state,
                        "depth": s.depth,
                    }
                    for s in result.proof_steps
                ],
            }
        }


# ---------------------------------------------------------------------------
# MGraphImplicationTester
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.missing_data",
    version="1.0.0",
    tags={"causal", "missing-data", "implication-test", "m-graph"},
)
class MGraphImplicationTester:
    """Statistical audit of testable M-graph implications."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="mgraph_implication_test",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset({
            _json_slot("mgraph_data"),
            _json_slot("data"),
        }),
        output_slots=frozenset({_json_slot("test_report")}),
        parameters=(
            ParameterSpec(name="alpha", default=0.05),
            ParameterSpec(name="max_conditioning_set_size", default=2),
            ParameterSpec(name="implications", default=[]),
            ParameterSpec(name="variable_order", default=[]),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Generate testable M-graph implications via m-separation and run a "
            "BH-corrected conditional-independence test suite."
        ),
        tags=frozenset({
            "causal", "missing-data", "m-graph", "implication-test",
            "conditional-independence", "falsification",
        }),
        citations=(
            "Mohan, K. & Pearl, J. (2021). Graphical Models for Processing Missing Data.",
            "Fisher, R.A. (1924). The distribution of the partial correlation coefficient.",
        ),
        equations={
            "bh": "q_(i) = min_{j>=i} p_(j)·m/j",
            "ci": "X ⊥ Y | Z",
        },
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use=(
            "After constructing an M-graph, to falsify missingness assumptions "
            "against observed data."
        ),
        when_not_to_use="When no observed dataset is available.",
        output_interpretation=(
            "overall_valid=True means no graph-derived implication was rejected "
            "after multiple-testing correction."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.ir.analytics.causal_graph import CausalGraphModel
        from polisyos.ir.analytics.mgraph import extract_mgraph_metadata

        raw_graph = state["mgraph_data"]
        graph = (
            CausalGraphModel.model_validate(raw_graph)
            if isinstance(raw_graph, dict)
            else raw_graph
        )
        meta = extract_mgraph_metadata(graph)

        raw_data = state.get("data", state.get("dataset"))
        if raw_data is None:
            raise KeyError("MGraphImplicationTester requires 'data' in state")

        raw_implications = params.get("implications")
        implications: list[ConditionalIndependence] | None = None
        if raw_implications:
            implications = [
                (
                    item
                    if isinstance(item, ConditionalIndependence)
                    else ConditionalIndependence.model_validate(item)
                )
                for item in raw_implications
            ]

        report = test_mgraph_implications(
            graph=graph,
            mgraph_meta=meta,
            data=raw_data,
            implications=implications,
            alpha=float(params.get("alpha", 0.05)),
            max_conditioning_set_size=int(params.get("max_conditioning_set_size", 2)),
            variable_order=tuple(params.get("variable_order", ())) or None,
        )
        return {"test_report": report.model_dump(mode="json")}


__all__ = [
    "ConditionalIndependence",
    "ImplicationTestResult",
    "TestReport",
    "testable_implications",
    "test_mgraph_implications",
    "RecoverabilityTest",
    "OrderedRecovery",
    "FullLawIdentify",
    "MGraphImplicationTester",
]
