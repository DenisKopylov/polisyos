"""recoverability_engine — M-graph recoverability algorithms.

Implements the two-stage pipeline for causal identification from incomplete data:

  Stage 1 — Recoverability (Mohan & Pearl 2021):
      test_recoverability(): can P(V) be recovered from the observed P*(V)?
      ordered_recovery():    build the recovery EstimandAST via topological ordering.

  Stage 2 — Full Law Identification (Nabi, Bhattacharya & Shpitser 2020):
      full_law_identify():   identify P(Y|do(X)) from incomplete data by combining
                             Stage 1 recovery with the standard ID algorithm.

All functions are pure (no side effects, no Foundry decoration).  They follow the
same pattern as ``id_engine.py``: internal frozen dataclasses, ProofStep traces,
and IdentificationResult as the shared return type for full_law_identify.

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

import dataclasses
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_graph import CausalGraphModel
    from polisyos.ir.analytics.estimand import EstimandAST
    from polisyos.ir.analytics.mgraph import MGraphMetadata


# ---------------------------------------------------------------------------
# Internal result types
# ---------------------------------------------------------------------------


class RecoverabilityStatus(str, Enum):
    """Outcome of the recoverability test (Stage 1)."""

    RECOVERABLE = "recoverable"
    NOT_RECOVERABLE = "not_recoverable"
    PARTIALLY_RECOVERABLE = "partially_recoverable"


@dataclasses.dataclass(frozen=True)
class RecoverabilityResult:
    """Result of ``test_recoverability()``."""

    status: RecoverabilityStatus
    query_variables: frozenset[str]
    proof_steps: list  # list[ProofStep] from id_engine — typed loosely to avoid circular
    trace: list[str]
    blocking_r_nodes: frozenset[str]
    """R-nodes that block recoverability (empty when RECOVERABLE)."""
    recovery_estimand: "EstimandAST | None"
    """Populated only when status == RECOVERABLE."""
    algorithm_version: str = "recover_v1"


# ---------------------------------------------------------------------------
# Algorithm 1: Recoverability Test  (Mohan & Pearl 2021, Theorem 1)
# ---------------------------------------------------------------------------


def test_recoverability(
    *,
    query_vars: frozenset[str],
    graph: "CausalGraphModel",
    mgraph_meta: "MGraphMetadata",
) -> RecoverabilityResult:
    """Test whether P(S) is recoverable from incomplete data.

    Implements the Mohan & Pearl (2021) graphical criterion (Theorem 1):

        P(S) is recoverable from P*(V) iff for every V_i ∈ S:
            R_{V_i} ∉ desc(V_i)  in G' = G[V ∪ R \\ proxy_nodes]

    The intuition: if R_{V_i} is a descendant of V_i (excluding paths through
    proxy nodes), then V_i's missingness is caused by V_i itself (MNAR with a
    self-affecting path), making the distribution non-recoverable.

    Parameters
    ----------
    query_vars:
        Set of substantive variables S in the query P(S).
    graph:
        CausalGraphModel with graph_type=MGRAPH.
    mgraph_meta:
        Parsed MGraphMetadata extracted from graph.metadata["mgraph"].

    Returns
    -------
    RecoverabilityResult
        status=RECOVERABLE → recovery_estimand is populated.
        status=NOT_RECOVERABLE → blocking_r_nodes lists the problematic R-nodes.
    """
    from polisyos.foundry.methods.catalog.causal.admg_ops import descendants
    from polisyos.foundry.methods.catalog.causal.id_engine import ProofStep
    from polisyos.ir.analytics.causal_graph import CausalGraphModel, GraphType

    trace: list[str] = []
    steps: list[ProofStep] = []
    blocking: set[str] = set()

    # Build G' = subgraph excluding proxy nodes.
    # Proxy nodes (X_star) act as "fixed" observations: conditioning them
    # out of path analysis is the graphical equivalent of the fixing operator.
    # We construct a PAG-type graph so validation doesn't enforce MGRAPH naming
    # contracts (which are no longer satisfied after stripping *_star nodes).
    proxy_names: frozenset[str] = frozenset(
        pn.proxy_name for pn in mgraph_meta.proxy_nodes
    )
    all_graph_nodes = frozenset(graph.nodes)
    kept_nodes = [n for n in graph.nodes if n not in proxy_names]
    kept_edges = [
        e for e in graph.edges
        if e.src not in proxy_names and e.dst not in proxy_names
    ]
    g_no_proxies = CausalGraphModel(
        graph_type=GraphType.PAG,  # PAG allows any edge marks; no naming contract
        nodes=kept_nodes,
        edges=kept_edges,
        discovery_method=graph.discovery_method,
    )

    trace.append(
        f"test_recoverability: |query_vars|={len(query_vars)}, "
        f"|proxy_stripped_nodes|={len(g_no_proxies.nodes)}"
    )

    g_nodes = frozenset(g_no_proxies.nodes)

    for vi in sorted(query_vars):
        r_name = f"R_{vi}"

        if r_name not in g_nodes:
            # No R-node → variable is fully observed, trivially recoverable
            steps.append(
                ProofStep(
                    rule_name="MGRAPH_TRIVIALLY_OBSERVED",
                    antecedent_vars=(vi,),
                    consequent_vars=(vi,),
                    applied_to_graph_state=(
                        f"{vi} has no R-node in G': trivially recoverable"
                    ),
                    depth=0,
                )
            )
            trace.append(f"  {vi}: trivially observed (no R-node)")
            continue

        # Check: is R_{V_i} a descendant of V_i in G'?
        # This detects the MNAR pattern where missingness feeds back from the variable.
        desc_vi = descendants(g_no_proxies, frozenset({vi}), include_self=False)

        if r_name in desc_vi:
            blocking.add(r_name)
            steps.append(
                ProofStep(
                    rule_name="MGRAPH_NOT_RECOVERABLE",
                    antecedent_vars=(vi,),
                    consequent_vars=(r_name,),
                    applied_to_graph_state=(
                        f"R_{vi} ∈ desc({vi}) in G[V∪R\\proxy]: "
                        f"P({vi}) not recoverable (MNAR self-affecting path)"
                    ),
                    depth=0,
                )
            )
            trace.append(f"  {vi}: BLOCKED — R_{vi} is descendant of {vi}")
        else:
            steps.append(
                ProofStep(
                    rule_name="MGRAPH_RECOVERABLE_VAR",
                    antecedent_vars=(vi,),
                    consequent_vars=(r_name,),
                    applied_to_graph_state=(
                        f"R_{vi} ∉ desc({vi}) in G[V∪R\\proxy]: "
                        f"P({vi}) is recoverable"
                    ),
                    depth=0,
                )
            )
            trace.append(f"  {vi}: recoverable (R_{vi} not in desc({vi}))")

    if blocking:
        trace.append(
            f"test_recoverability: NOT_RECOVERABLE — blocking={sorted(blocking)}"
        )
        return RecoverabilityResult(
            status=RecoverabilityStatus.NOT_RECOVERABLE,
            query_variables=query_vars,
            proof_steps=steps,
            trace=trace,
            blocking_r_nodes=frozenset(blocking),
            recovery_estimand=None,
        )

    # All variables pass — build recovery estimand
    trace.append("test_recoverability: RECOVERABLE — building ordered recovery estimand")
    estimand = ordered_recovery(graph=graph, mgraph_meta=mgraph_meta)
    return RecoverabilityResult(
        status=RecoverabilityStatus.RECOVERABLE,
        query_variables=query_vars,
        proof_steps=steps,
        trace=trace,
        blocking_r_nodes=frozenset(),
        recovery_estimand=estimand,
    )


# ---------------------------------------------------------------------------
# Algorithm 2: Ordered Recovery  (Mohan, Pearl & Tian 2013, Algorithm 1)
# ---------------------------------------------------------------------------


def ordered_recovery(
    *,
    graph: "CausalGraphModel",
    mgraph_meta: "MGraphMetadata",
    dataset_ref: str | None = None,
) -> "EstimandAST":
    """Recover the full-data joint P(V) from P*(V) using topological ordering.

    Implements the ordered fixing operator from Mohan, Pearl & Tian (2013):

        P(V) = Π_i P(V_i | V_{i-1}, ..., V_1)

    where each factor is recovered as:
      - Fully observed:  P(V_i | V_{<i}) = P*(V_i | V_{<i})
      - MCAR / MAR:     P(V_i | V_{<i}) = P*(V_i | V_{<i}, R_{V_i}=1)
      - MNAR:           P(V_i | V_{<i}) = P*(V_i | V_{<i}, R_{V_i}=1)   [with side-condition]

    The topological order is computed over the subgraph of substantive variables
    only (no R_* or *_star nodes).

    Parameters
    ----------
    graph:
        CausalGraphModel with graph_type=MGRAPH.
    mgraph_meta:
        Parsed MGraphMetadata from graph.metadata["mgraph"].
    dataset_ref:
        Optional pointer to the observed (incomplete) dataset.

    Returns
    -------
    EstimandAST
        Root is a ProductNode of RecoveredDistNode factors.
        identification_method="ordered_recovery".
    """
    from polisyos.foundry.methods.catalog.causal.admg_ops import topological_order
    from polisyos.foundry.methods.catalog.causal.id_engine import ProofStep
    from polisyos.ir.analytics.causal_graph import CausalGraphModel, GraphType
    from polisyos.ir.analytics.estimand import (
        EstimandAST,
        ProductNode,
        RecoveredDistNode,
    )

    subst_set = set(mgraph_meta.substantive_vars)
    # Build a DAG of substantive variables only for topological ordering.
    # Use ADMG type to allow bidirected edges; DAG type would reject them.
    kept_nodes = [n for n in graph.nodes if n in subst_set]
    kept_edges = [
        e for e in graph.edges
        if e.src in subst_set and e.dst in subst_set
    ]
    from polisyos.ir.analytics.causal_graph import EdgeMark
    has_bidirected = any(
        e.mark_src is EdgeMark.ARROW and e.mark_dst is EdgeMark.ARROW
        for e in kept_edges
    )
    subst_graph_type = GraphType.ADMG if has_bidirected else GraphType.DAG
    g_subst = CausalGraphModel(
        graph_type=subst_graph_type,
        nodes=kept_nodes,
        edges=kept_edges,
        discovery_method=graph.discovery_method,
    )

    try:
        order: list[str] = topological_order(g_subst)
    except ValueError as exc:
        raise ValueError(
            f"ordered_recovery: substantive variable subgraph contains a cycle: {exc}"
        ) from exc

    # Index missingness metadata by target variable
    r_node_map = {rn.target_variable: rn for rn in mgraph_meta.r_nodes}
    proxy_map = {pn.target_variable: pn for pn in mgraph_meta.proxy_nodes}

    factors: list[RecoveredDistNode] = []
    steps: list[ProofStep] = []

    for i, vi in enumerate(order):
        predecessors = tuple(order[:i])
        r_info = r_node_map.get(vi)
        proxy_info = proxy_map.get(vi)

        if r_info is None:
            # Fully observed: standard conditional
            kind = "fully_observed"
            r_name = ""
            proxy_name = vi
        else:
            kind = r_info.missingness_kind.value
            r_name = f"R_{vi}"
            proxy_name = proxy_info.proxy_name if proxy_info else f"{vi}_star"

        factors.append(
            RecoveredDistNode(
                variable=vi,
                conditioning=predecessors,
                missingness_indicator=r_name,
                proxy_variable=proxy_name,
                missingness_kind=kind,
                dataset_ref=dataset_ref,
            )
        )
        steps.append(
            ProofStep(
                rule_name="ORDERED_RECOVERY_STEP",
                antecedent_vars=predecessors,
                consequent_vars=(vi,),
                applied_to_graph_state=(
                    f"Recover P({vi} | {list(predecessors)}) "
                    f"via fixing operator [{kind}]"
                ),
                depth=i,
            )
        )

    from polisyos.ir.analytics.estimand import EstimandNode

    root: EstimandNode = ProductNode(factors=tuple(factors))
    treatment = order[0] if order else ""
    outcome = order[-1] if order else ""

    return EstimandAST(
        query_str=f"P({', '.join(order)})",
        root=root,
        treatment=treatment,
        outcome=outcome,
        all_variables=tuple(order),
        identification_method="ordered_recovery",
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _project_to_base_dag(
    graph: "CausalGraphModel",
    mgraph_meta: "MGraphMetadata",
) -> "CausalGraphModel":
    """Extract the causal subgraph (substantive variables only) from an M-graph.

    Strips all R_* and *_star nodes and their incident edges, leaving only
    the causal structure among the full-data variables V.

    Returns a CausalGraphModel with graph_type=DAG if there are no bidirected
    edges, or graph_type=ADMG if bidirected (latent-confounder) edges exist
    among the substantive variables.

    Note: we construct the result directly (not via induced_subgraph) because
    induced_subgraph preserves the MGRAPH graph_type which would fail validation
    when the R-node / proxy-node naming contract is no longer satisfied.
    """
    from polisyos.ir.analytics.causal_graph import CausalGraphModel, EdgeMark, GraphType

    subst_set = set(mgraph_meta.substantive_vars)
    kept_nodes = [n for n in graph.nodes if n in subst_set]
    kept_edges = [
        e for e in graph.edges
        if e.src in subst_set and e.dst in subst_set
    ]

    # Choose graph_type based on whether bidirected edges exist
    has_bidirected = any(
        e.mark_src is EdgeMark.ARROW and e.mark_dst is EdgeMark.ARROW
        for e in kept_edges
    )
    target_type = GraphType.ADMG if has_bidirected else GraphType.DAG

    return CausalGraphModel(
        schema_version=graph.schema_version,
        graph_type=target_type,
        nodes=kept_nodes,
        edges=kept_edges,
        discovery_method=graph.discovery_method,
    )


def _annotate_with_recovery(
    causal_ast: "EstimandAST",
    recovery_ast: "EstimandAST",
) -> "EstimandAST":
    """Annotate a causal EstimandAST with a note that distributions come from
    recovered full-data P(V).  Currently returns causal_ast unchanged
    (the recovery context is captured in proof_steps).  This hook is provided
    for future use when combining both ASTs into a single compound expression.
    """
    # For now, just return the causal AST — the recovery proof steps provide
    # the audit trail and the RecoveredDistNode factors are in recovery_ast.
    return causal_ast


# ---------------------------------------------------------------------------
# Algorithm 3: Full Law Identification  (Nabi, Bhattacharya & Shpitser 2020)
# ---------------------------------------------------------------------------


def full_law_identify(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: "CausalGraphModel",
    mgraph_meta: "MGraphMetadata",
    dataset_ref: str | None = None,
    oracle: str = "none",
) -> object:  # returns IdentificationResult — typed as object to avoid circular imports
    """Identify P(Y|do(X)) from incomplete data in an M-graph.

    Two-stage pipeline (Nabi, Bhattacharya & Shpitser 2020):

    Stage 1 — Recoverability:
        Test whether the full-data joint P(V) is recoverable from the observed
        distribution P*(V).  Uses Mohan & Pearl (2021) graphical criterion.

    Stage 2 — Causal Identification:
        Run the standard ID algorithm on the base DAG (substantive variables only)
        to identify P(Y|do(X)) from P(V).

    Parameters
    ----------
    treatment:
        Set of treatment variable names.
    outcome:
        Set of outcome variable names.
    graph:
        CausalGraphModel with graph_type=MGRAPH.
    mgraph_meta:
        Parsed MGraphMetadata from graph.metadata["mgraph"].
    dataset_ref:
        Optional pointer to the observed (incomplete) dataset.
    oracle:
        Oracle backend to pass to id_with_oracle_fallback ("none" | "y0" | "dosearch").

    Returns
    -------
    IdentificationResult
        status=IDENTIFIED → full pipeline succeeded; estimand_ast populated.
        status=NOT_RECOVERABLE → Stage 1 failed.
        status=HEDGE_FOUND / ORACLE_NEEDED → Stage 2 failed.
    """
    import dataclasses as _dc

    from polisyos.foundry.methods.catalog.causal.id_engine import (
        IdentificationResult,
        IdentificationStatus,
        ProofStep,
        id_with_oracle_fallback,
    )

    all_steps: list[ProofStep] = []
    trace: list[str] = []

    # ------------------------------------------------------------------
    # Stage 1: test recoverability of all substantive variables
    # ------------------------------------------------------------------
    rec = test_recoverability(
        query_vars=frozenset(mgraph_meta.substantive_vars),
        graph=graph,
        mgraph_meta=mgraph_meta,
    )
    all_steps.extend(rec.proof_steps)
    trace.extend(rec.trace)

    if rec.status == RecoverabilityStatus.NOT_RECOVERABLE:
        trace.append(
            "full_law_identify: Stage 1 FAILED — "
            f"blocking R-nodes: {sorted(rec.blocking_r_nodes)}"
        )
        return IdentificationResult(
            status=IdentificationStatus.NOT_RECOVERABLE,
            estimand_ast=None,
            hedge_certificate=None,
            trace=trace,
            required_distributions=[],
            algorithm_version="full_law_v1",
            proof_steps=all_steps,
        )

    # Stage 1 passed
    all_steps.append(
        ProofStep(
            rule_name="FULL_LAW_STAGE1_PASS",
            antecedent_vars=tuple(sorted(mgraph_meta.substantive_vars)),
            consequent_vars=tuple(sorted(mgraph_meta.substantive_vars)),
            applied_to_graph_state=(
                "Full-data P(V) is recoverable from incomplete data via ordered_recovery"
            ),
            depth=0,
        )
    )
    trace.append("full_law_identify: Stage 1 PASSED")

    # ------------------------------------------------------------------
    # Stage 2: ID algorithm on the base DAG
    # ------------------------------------------------------------------
    base_graph = _project_to_base_dag(graph, mgraph_meta)

    # Resolve treatment/outcome to single strings for id_algorithm
    treatment_var = next(iter(treatment)) if len(treatment) == 1 else sorted(treatment)[0]
    outcome_var = next(iter(outcome)) if len(outcome) == 1 else sorted(outcome)[0]

    id_result = id_with_oracle_fallback(
        treatment=frozenset(treatment),
        outcome=frozenset(outcome),
        graph=base_graph,
        oracle=oracle,
        dataset_ref=dataset_ref,
    )

    all_steps.extend(list(id_result.proof_steps))
    all_steps.append(
        ProofStep(
            rule_name="FULL_LAW_STAGE2",
            antecedent_vars=tuple(sorted(treatment)),
            consequent_vars=tuple(sorted(outcome)),
            applied_to_graph_state=(
                f"ID algorithm on base DAG: status={id_result.status.value}"
            ),
            depth=0,
        )
    )
    trace.append(
        f"full_law_identify: Stage 2 status={id_result.status.value}"
    )

    if id_result.status != IdentificationStatus.IDENTIFIED:
        return _dc.replace(
            id_result,
            trace=trace + list(id_result.trace),
            proof_steps=all_steps,
            algorithm_version="full_law_v1",
        )

    # Both stages succeeded — annotate estimand with recovery context
    combined_ast = _annotate_with_recovery(
        id_result.estimand_ast,
        rec.recovery_estimand,
    )
    return _dc.replace(
        id_result,
        estimand_ast=combined_ast,
        trace=trace,
        proof_steps=all_steps,
        algorithm_version="full_law_v1",
    )


__all__ = [
    "RecoverabilityStatus",
    "RecoverabilityResult",
    "test_recoverability",
    "ordered_recovery",
    "full_law_identify",
]
