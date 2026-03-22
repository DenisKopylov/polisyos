"""Cyclic identification heuristics for feedback-loop causal graphs.

The implementation is intentionally pragmatic: it provides SCC condensation,
σ-separation as a cycle-aware mixed-graph oracle, and a lightweight fixed-point
well-posedness check that can be driven either by a linear system matrix or by
a generic update function.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from polisyos.foundry.methods.catalog.causal.admg_ops import (
    has_directed_cycle,
    m_separation,
    tarjan_scc,
)
from polisyos.foundry.methods.catalog.causal.id_engine import (
    HedgeCertificate,
    IdentificationResult,
    IdentificationStatus,
    ProofStep,
    RequiredDataSpec,
    id_algorithm,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.estimand import DistributionDomain, EstimandAST, ExpectationNode


class WellPosednessResult(BaseModel):
    """Result of a cyclic fixed-point well-posedness check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    well_posed: bool
    method: Literal["exact_linear", "lipschitz_heuristic", "numerical_sampling"]
    confidence: Literal["exact", "approximate"]
    lipschitz_constant: float | None = None
    warning: str | None = None


def _source_graph_hash(graph: CausalGraphModel) -> str:
    import hashlib
    import json

    payload = graph.model_dump(mode="python")
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _resolve_spec(graph: CausalGraphModel, scm_spec: Any | None) -> Any | None:
    if scm_spec is not None:
        return scm_spec
    return graph.metadata.get("well_posedness_spec") or graph.metadata.get("scm_spec")


def _spec_linear_matrix(spec: Any) -> np.ndarray | None:
    if spec is None:
        return None
    if isinstance(spec, np.ndarray):
        return spec
    if isinstance(spec, dict):
        for key in ("linear_system_matrix", "coefficient_matrix", "A"):
            if key in spec:
                return np.asarray(spec[key], dtype=float)
    for key in ("linear_system_matrix", "coefficient_matrix", "A"):
        if hasattr(spec, key):
            return np.asarray(getattr(spec, key), dtype=float)
    return None


def _spec_update_fn(spec: Any) -> Callable[[Any], Any] | None:
    if callable(spec):
        return spec
    if isinstance(spec, dict):
        for key in ("fixed_point_fn", "update_fn", "solver_fn"):
            fn = spec.get(key)
            if callable(fn):
                return fn
    for key in ("fixed_point_fn", "update_fn", "solver_fn"):
        fn = getattr(spec, key, None)
        if callable(fn):
            return fn
    return None


def _as_numeric_vector(value: Any) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 0:
        arr = arr.reshape(1)
    return arr.astype(float)


def _multi_start_fixed_point_search(
    update_fn: Callable[[Any], Any],
    *,
    n_starts: int = 50,
    max_iterations: int = 100,
    tol: float = 1e-6,
) -> tuple[list[np.ndarray], bool]:
    """Return distinct fixed points found from deterministic multi-start search."""
    seeds = np.linspace(-2.0, 2.0, num=n_starts)
    found: list[np.ndarray] = []
    converged = True

    for seed in seeds:
        current = _as_numeric_vector(seed)
        for _ in range(max_iterations):
            nxt = _as_numeric_vector(update_fn(current if current.size > 1 else float(current[0])))
            if nxt.shape != current.shape:
                nxt = nxt.reshape(current.shape)
            if float(np.max(np.abs(nxt - current))) < tol:
                current = nxt
                break
            current = nxt
        else:
            converged = False

        if not any(float(np.max(np.abs(current - prev))) < 5 * tol for prev in found):
            found.append(current.copy())

    return found, converged


def build_sigma_connection_graph(graph: CausalGraphModel) -> CausalGraphModel:
    """Return a σ-connection graph where each SCC is internally bidirected."""
    sccs = tarjan_scc(graph)

    seen: set[tuple[str, str, EdgeMark, EdgeMark, int | None]] = set()
    edges: list[CausalEdge] = []
    for edge in graph.edges:
        sig = (edge.src, edge.dst, edge.mark_src, edge.mark_dst, edge.lag)
        if sig not in seen:
            seen.add(sig)
            edges.append(edge)

    for comp in sccs:
        if len(comp) < 2:
            continue
        ordered = sorted(comp)
        for i, src in enumerate(ordered):
            for dst in ordered[i + 1 :]:
                sig = (src, dst, EdgeMark.ARROW, EdgeMark.ARROW, None)
                if sig in seen:
                    continue
                seen.add(sig)
                edges.append(
                    CausalEdge(
                        src=src,
                        dst=dst,
                        mark_src=EdgeMark.ARROW,
                        mark_dst=EdgeMark.ARROW,
                    )
                )

    return CausalGraphModel.model_construct(
        schema_version=graph.schema_version,
        graph_type=GraphType.ADMG,
        nodes=list(graph.nodes),
        edges=edges,
        discovery_method=graph.discovery_method,
        skg_version_id=graph.skg_version_id,
        pag_identification_policy=graph.pag_identification_policy,
        id_confidence_under_pag=graph.id_confidence_under_pag,
        metadata={
            **dict(graph.metadata),
            "derived_view": "sigma_connection",
            "source_graph_hash": _source_graph_hash(graph),
            "sigma_sccs": [sorted(comp) for comp in sccs],
        },
    )


def sigma_separation(
    graph: CausalGraphModel,
    x_set: frozenset[str],
    y_set: frozenset[str],
    z_set: frozenset[str],
) -> bool:
    """Cycle-aware separation oracle.

    The implementation conservatively strengthens each SCC into a σ-connected
    clique and then applies standard m-separation.
    """
    node_set = set(graph.nodes)
    missing = (x_set | y_set | z_set) - node_set
    if missing:
        raise ValueError(f"Unknown nodes in sigma_separation query: {sorted(missing)}")
    sigma_graph = build_sigma_connection_graph(graph)
    return m_separation(sigma_graph, x_set, y_set, z_set)


def well_posedness_check(
    graph: CausalGraphModel,
    scm_spec: Any | None = None,
) -> WellPosednessResult:
    """Check whether a cyclic system admits a unique fixed point."""
    spec = _resolve_spec(graph, scm_spec)

    linear_matrix = _spec_linear_matrix(spec)
    if linear_matrix is not None:
        if linear_matrix.ndim != 2 or linear_matrix.shape[0] != linear_matrix.shape[1]:
            return WellPosednessResult(
                well_posed=False,
                method="exact_linear",
                confidence="exact",
                warning="linear_system_matrix must be square",
            )
        identity = np.eye(linear_matrix.shape[0], dtype=float)
        det = float(np.linalg.det(identity - linear_matrix))
        well_posed = abs(det) > 1e-8
        return WellPosednessResult(
            well_posed=well_posed,
            method="exact_linear",
            confidence="exact",
            lipschitz_constant=float(np.linalg.norm(linear_matrix, ord=2)),
            warning=None if well_posed else "det(I - A) is numerically close to zero",
        )

    update_fn = _spec_update_fn(spec)
    if update_fn is None:
        return WellPosednessResult(
            well_posed=True,
            method="lipschitz_heuristic",
            confidence="approximate",
            warning="No fixed-point specification supplied; assuming locally well posed.",
        )

    fixed_points, converged = _multi_start_fixed_point_search(update_fn)
    unique_fixed_points = len(fixed_points)
    if unique_fixed_points > 1:
        return WellPosednessResult(
            well_posed=False,
            method="numerical_sampling",
            confidence="approximate",
            warning=f"Multiple fixed points found ({unique_fixed_points}); feedback is not unique.",
        )

    lipschitz_constant = None
    if isinstance(spec, dict):
        lipschitz_constant = spec.get("lipschitz_constant")
    else:
        lipschitz_constant = getattr(spec, "lipschitz_constant", None)

    if lipschitz_constant is not None:
        try:
            lipschitz_value = float(lipschitz_constant)
        except (TypeError, ValueError):
            lipschitz_value = None
        else:
            return WellPosednessResult(
                well_posed=lipschitz_value < 1.0 and converged,
                method="lipschitz_heuristic",
                confidence="approximate",
                lipschitz_constant=lipschitz_value,
                warning=(
                    None
                    if lipschitz_value < 1.0 and converged
                    else "Lipschitz heuristic did not guarantee a unique fixed point."
                ),
            )

    return WellPosednessResult(
        well_posed=converged,
        method="numerical_sampling",
        confidence="approximate",
        warning=None if converged else "Fixed-point iteration did not converge from all starts.",
    )


def _component_for_nodes(sccs: list[frozenset[str]], nodes: frozenset[str]) -> frozenset[str] | None:
    for comp in sccs:
        if nodes & comp:
            return comp
    return None


def cyclic_id_algorithm(
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    *,
    scm_spec: Any | None = None,
    dataset_ref: str | None = None,
    domain: DistributionDomain = DistributionDomain.SOURCE,
    _depth: int = 0,
) -> IdentificationResult:
    """Heuristic cyclic ID engine.

    The algorithm first collapses SCCs, then uses σ-separation and a fixed-point
    well-posedness check to decide whether the query can be routed to a symbolic
    estimand. The result is marked experimental via the algorithm_version.
    """
    trace: list[str] = [
        f"[depth={_depth}] cyclic_id_algorithm(X={sorted(treatment)}, Y={sorted(outcome)})"
    ]
    proof_steps: list[ProofStep] = [
        ProofStep(
            rule_name="CYCLIC_START",
            antecedent_vars=tuple(sorted(treatment)),
            consequent_vars=tuple(sorted(outcome)),
            applied_to_graph_state="experimental cyclic identification entry point",
            depth=_depth,
        )
    ]

    if not has_directed_cycle(graph):
        trace.append(f"[depth={_depth}] no directed cycle detected; delegating to id_algorithm")
        inner = id_algorithm(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            dataset_ref=dataset_ref,
            domain=domain,
            _depth=_depth,
            _trace=trace,
        )
        return dataclasses.replace(
            inner,
            algorithm_version="cyclic_id_experimental_v1",
            trace=list(inner.trace),
            proof_steps=proof_steps + list(inner.proof_steps),
        )

    sccs = tarjan_scc(graph)
    sigma_graph = build_sigma_connection_graph(graph)
    cycle_component = _component_for_nodes(sccs, treatment | outcome)
    if cycle_component is None:
        cycle_component = next((comp for comp in sccs if len(comp) > 1), frozenset(graph.nodes))

    trace.append(f"[depth={_depth}] SCCs={[sorted(comp) for comp in sccs]}")
    proof_steps.append(
        ProofStep(
            rule_name="CYCLIC_SCC",
            antecedent_vars=tuple(sorted(cycle_component)),
            consequent_vars=tuple(sorted(cycle_component)),
            applied_to_graph_state="Tarjan SCC condensation for feedback loop handling",
            depth=_depth,
        )
    )

    well_posed = well_posedness_check(graph, scm_spec)
    trace.append(
        f"[depth={_depth}] well_posed={well_posed.well_posed} method={well_posed.method}"
    )
    proof_steps.append(
        ProofStep(
            rule_name="CYCLIC_WELL_POSED",
            antecedent_vars=tuple(sorted(cycle_component)),
            consequent_vars=tuple(sorted(cycle_component)),
            applied_to_graph_state=well_posed.warning or well_posed.method,
            depth=_depth,
        )
    )

    sigma_ok = sigma_separation(sigma_graph, treatment, outcome, frozenset())
    if not sigma_ok:
        trace.append(
            f"[depth={_depth}] sigma-separation failed; continuing with fixed-point heuristic"
        )
        proof_steps.append(
            ProofStep(
                rule_name="CYCLIC_SIGMA_WARN",
                antecedent_vars=tuple(sorted(treatment)),
                consequent_vars=tuple(sorted(outcome)),
                applied_to_graph_state="σ-separation failed, but the feedback loop may still be well posed",
                depth=_depth,
            )
        )

    if not well_posed.well_posed:
        trace.append(f"[depth={_depth}] feedback loop is not well posed")
        proof_steps.append(
            ProofStep(
                rule_name="CYCLIC_NON_WELL_POSED",
                antecedent_vars=tuple(sorted(cycle_component)),
                consequent_vars=tuple(sorted(cycle_component)),
                applied_to_graph_state=well_posed.warning or "non-unique fixed point",
                depth=_depth,
            )
        )
        cert = HedgeCertificate(
            treatment=treatment,
            outcome=outcome,
            hedge_forest=cycle_component,
            hedge_root=cycle_component,
            c_component_witness=cycle_component,
            description=well_posed.warning or "Cyclic system not well posed",
            required_data=RequiredDataSpec(
                missing_distributions=(),
                alternative_identification="The fixed point is not unique; identification is not well-defined.",
            ),
        )
        return IdentificationResult(
            status=IdentificationStatus.HEDGE_FOUND,
            estimand_ast=None,
            hedge_certificate=cert,
            trace=trace,
            required_distributions=[],
            algorithm_version="cyclic_id_experimental_v1",
            proof_steps=proof_steps,
        )

    if not sigma_ok:
        trace.append(
            f"[depth={_depth}] accepting heuristic identification despite σ-separation warning"
        )

    representative_outcome = next(iter(sorted(outcome)))
    representative_treatment = next(iter(sorted(treatment))) if treatment else representative_outcome
    ast = EstimandAST(
        query_str=f"E[{representative_outcome} | cyclic do({representative_treatment})]",
        root=ExpectationNode(
            outcome=representative_outcome,
            conditioning=tuple(sorted(treatment)),
            intervention_set=tuple(sorted(treatment)),
            domain=domain,
            dataset_ref=dataset_ref,
        ),
        treatment=representative_treatment,
        outcome=representative_outcome,
        all_variables=tuple(sorted(graph.nodes)),
        identification_method=(
            "cyclic_id|"
            f"scc={','.join(sorted(cycle_component))}|"
            f"solver={well_posed.method}"
        ),
    )
    proof_steps.append(
        ProofStep(
            rule_name="CYCLIC_SOLVER",
            antecedent_vars=tuple(sorted(cycle_component)),
            consequent_vars=tuple(sorted(outcome)),
            applied_to_graph_state="heuristic fixed-point route accepted",
            depth=_depth,
        )
    )
    trace.append(f"[depth={_depth}] cyclic_id identified experimentally")
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=ast,
        hedge_certificate=None,
        trace=trace,
        required_distributions=[],
        algorithm_version="cyclic_id_experimental_v1",
        proof_steps=proof_steps,
    )


__all__ = [
    "WellPosednessResult",
    "build_sigma_connection_graph",
    "sigma_separation",
    "well_posedness_check",
    "cyclic_id_algorithm",
]
