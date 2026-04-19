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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_graph import CausalGraphModel
    from polisyos.ir.analytics.estimand import EstimandAST
    from polisyos.ir.analytics.mgraph import MGraphMetadata
    from polisyos.ir.analytics.negative_certificate import NegativeCertificate
    from polisyos.ir.analytics.recoverability import (
        JointDecisionCertificate,
        RecoverabilityCertificate,
        RecoverabilityCertificateStatus,
        RecoveryScope,
        RecoveryStep,
    )


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
    recovery_estimand: EstimandAST | None
    """Populated only when status == RECOVERABLE."""
    algorithm_version: str = "recover_v1"


# ---------------------------------------------------------------------------
# Algorithm 1: Recoverability Test  (Mohan & Pearl 2021, Theorem 1)
# ---------------------------------------------------------------------------


def test_recoverability(
    *,
    query_vars: frozenset[str],
    graph: CausalGraphModel,
    mgraph_meta: MGraphMetadata,
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
    graph: CausalGraphModel,
    mgraph_meta: MGraphMetadata,
    dataset_ref: str | None = None,
) -> EstimandAST:
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
    graph: CausalGraphModel,
    mgraph_meta: MGraphMetadata,
) -> CausalGraphModel:
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
    causal_ast: EstimandAST,
    recovery_ast: EstimandAST,
) -> EstimandAST:
    """Annotate a causal EstimandAST with a note that distributions come from
    recovered full-data P(V).  Currently returns causal_ast unchanged
    (the recovery context is captured in proof_steps).  This hook is provided
    for future use when combining both ASTs into a single compound expression.
    """
    # For now, just return the causal AST — the recovery proof steps provide
    # the audit trail and the RecoveredDistNode factors are in recovery_ast.
    return causal_ast


def _target_query(treatment: frozenset[str], outcome: frozenset[str]) -> str:
    return f"P({', '.join(sorted(outcome))}|do({', '.join(sorted(treatment))}))"


def _dump_estimand(ast: object) -> dict[str, Any] | None:
    if ast is None:
        return None
    if hasattr(ast, "model_dump"):
        return ast.model_dump(mode="json")
    if isinstance(ast, dict):
        return dict(ast)
    return {"repr": str(ast)}


def _step_to_recovery_step(step: object, *, theorem: str = "") -> RecoveryStep:
    from polisyos.ir.analytics.recoverability import RecoveryStep

    variables = tuple(
        sorted(
            set(getattr(step, "antecedent_vars", ()) or ())
            | set(getattr(step, "consequent_vars", ()) or ())
        )
    )
    return RecoveryStep(
        rule_name=str(getattr(step, "rule_name", "") or "RECOVERY_STEP"),
        rule_formal_name=str(getattr(step, "rule_formal_name", "") or ""),
        applicable_theorem=theorem,
        description=str(getattr(step, "applied_to_graph_state", "") or ""),
        variables_affected=variables,
        depth=int(getattr(step, "depth", 0) or 0),
    )


def _minimal_repair_sets(blocking_r_nodes: frozenset[str]) -> tuple[Any, ...]:
    from polisyos.ir.analytics.recoverability import (
        MinimalRepairSet,
        RepairSetTestability,
        RepairSetType,
    )

    repairs: list[MinimalRepairSet] = []
    for r_node in sorted(blocking_r_nodes):
        target = r_node[2:] if r_node.startswith("R_") else r_node
        repairs.append(
            MinimalRepairSet(
                repair_type=RepairSetType.ASSUMPTION,
                items=(
                    f"remove_edge({target} -> {r_node})",
                    f"assume {r_node} independent_of {target} given Pa({r_node})\\{{{target}}}",
                ),
                testability=RepairSetTestability.NOT_TESTABLE,
                notes=(
                    "Structural MAR-like strengthening for the blocking "
                    f"missingness mechanism of {target}."
                ),
            )
        )
        repairs.append(
            MinimalRepairSet(
                repair_type=RepairSetType.DATA,
                items=(
                    f"collect_complete_case({target})",
                    f"measure_auxiliary_variable_for({r_node})",
                ),
                testability=RepairSetTestability.UNKNOWN,
                notes=(
                    "Additional observed data can block or audit the MNAR "
                    f"path into {r_node}."
                ),
            )
        )
    return tuple(repairs)


def _recoverability_certificate_from_result(
    *,
    result: RecoverabilityResult,
    graph: CausalGraphModel,
    target_query: str,
    scope: RecoveryScope,
    expression_ast: object = None,
    status_override: RecoverabilityCertificateStatus | None = None,
    warnings: tuple[str, ...] = (),
    computable_functionals: tuple[str, ...] = (),
    theorem_family: str = "Mohan-Pearl-Tian-2013",
    completeness_regime: str = "sound_incomplete",
    metadata: dict[str, Any] | None = None,
) -> RecoverabilityCertificate:
    from polisyos.ir.analytics.recoverability import (
        RecoverabilityCertificate,
        RecoverabilityCertificateStatus,
        RecoverabilityEstimatorFamily,
        mgraph_fingerprint,
    )

    if status_override is not None:
        status = status_override
    elif result.status is RecoverabilityStatus.RECOVERABLE:
        status = RecoverabilityCertificateStatus.RECOVERABLE
    elif result.status is RecoverabilityStatus.PARTIALLY_RECOVERABLE:
        status = RecoverabilityCertificateStatus.RECOVERABLE_UNDER_ASSUMPTIONS
    else:
        repairs = _minimal_repair_sets(result.blocking_r_nodes)
        status = (
            RecoverabilityCertificateStatus.RECOVERABLE_UNDER_ASSUMPTIONS
            if repairs
            else RecoverabilityCertificateStatus.NOT_RECOVERABLE
        )

    expression = expression_ast
    if expression is None and result.recovery_estimand is not None:
        expression = result.recovery_estimand

    blocking = tuple(sorted(result.blocking_r_nodes))
    estimator = None
    if status is RecoverabilityCertificateStatus.RECOVERABLE:
        estimator = RecoverabilityEstimatorFamily.G_FORMULA_REWEIGHT

    return RecoverabilityCertificate(
        target_query=target_query,
        mgraph_fingerprint=mgraph_fingerprint(graph),
        status=status,
        recovery_scope=scope,
        recovery_expression_ast=_dump_estimand(expression),
        recovery_steps=tuple(
            _step_to_recovery_step(step, theorem=theorem_family)
            for step in result.proof_steps
        ),
        blocking_r_nodes=blocking,
        blocking_explanation=(
            "Blocking R-nodes indicate self-affecting missingness paths."
            if blocking
            else ""
        ),
        minimal_repair_sets=_minimal_repair_sets(result.blocking_r_nodes),
        recommended_estimator_family=estimator,
        computable_functionals=computable_functionals,
        warnings=warnings,
        completeness_regime=completeness_regime,  # type: ignore[arg-type]
        theorem_family=theorem_family,
        metadata=metadata or {},
    )


def _negative_certificate_from_recoverability(
    certificate: RecoverabilityCertificate,
) -> NegativeCertificate:
    from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate

    missing_vars = tuple(
        sorted(
            {
                node[2:] if node.startswith("R_") else node
                for node in certificate.blocking_r_nodes
            }
        )
    )
    suggested = NegativeCertificate.auto_suggest_experiments(
        BlockingType.MISSINGNESS_NOT_RECOVERABLE,
        missing_vars=missing_vars,
    )
    return NegativeCertificate(
        blocking_type=BlockingType.MISSINGNESS_NOT_RECOVERABLE,
        blocking_description=(
            f"Missingness graph blocks recovery of {certificate.target_query}."
        ),
        technical_detail=certificate.blocking_explanation,
        suggested_experiments=suggested,
        quantitative_diagnostics={
            "identification_status": "identified",
            "recoverability": certificate.to_summary_dict(),
            "blocking_r_nodes_count": float(len(certificate.blocking_r_nodes)),
        },
        constructive_message=(
            "Use one of the missingness repair sets: add complete-case or "
            "auxiliary data, or record the explicit structural missingness "
            "assumption before estimation."
        ),
    )


def _attach_recoverability_to_negative_certificate(
    certificate: NegativeCertificate,
    *,
    recoverability: RecoverabilityCertificate,
    verdict: JointDecisionStatus,
    computable_functionals: tuple[str, ...] = (),
) -> NegativeCertificate:
    diagnostics = {
        **dict(certificate.quantitative_diagnostics or {}),
        "recoverability": recoverability.to_summary_dict(),
        "joint_decision_verdict": verdict.value,
    }
    if computable_functionals:
        diagnostics["computable_functionals"] = list(computable_functionals)

    constructive_message = str(getattr(certificate, "constructive_message", "") or "").strip()
    if computable_functionals:
        computable_note = (
            "Computable functionals under current missingness assumptions: "
            f"{', '.join(computable_functionals)}."
        )
        if computable_note not in constructive_message:
            constructive_message = (
                f"{constructive_message} {computable_note}".strip()
                if constructive_message
                else computable_note
            )

    return certificate.model_copy(
        update={
            "quantitative_diagnostics": diagnostics,
            "constructive_message": constructive_message,
        }
    )


def _negative_certificate_from_id_failure(
    *,
    result: object,
    treatment: frozenset[str],
    outcome: frozenset[str],
) -> NegativeCertificate:
    from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate

    status = str(getattr(getattr(result, "status", None), "value", "") or "non_identified")
    hedge = getattr(result, "hedge_certificate", None)
    treatment_str = ", ".join(sorted(treatment))
    outcome_str = ", ".join(sorted(outcome))
    if hedge is not None:
        missing_vars = tuple(sorted(getattr(hedge, "minimal_required_s_nodes", frozenset()) or ()))
        return NegativeCertificate(
            blocking_type=BlockingType.HEDGE_STRUCTURE,
            blocking_description=(
                f"Non-identifiable: hedge blocks P({outcome_str}|do({treatment_str}))."
            ),
            technical_detail=str(getattr(hedge, "description", "") or ""),
            suggested_experiments=NegativeCertificate.auto_suggest_experiments(
                BlockingType.HEDGE_STRUCTURE,
                missing_vars=missing_vars,
            ),
            quantitative_diagnostics={
                "identification_status": status,
                "algorithm_version": str(getattr(result, "algorithm_version", "") or ""),
                "proof_trace": list(getattr(result, "trace", []) or []),
            },
            constructive_message=(
                "The causal effect is not nonparametrically identifiable from "
                "the available observational law. Consider randomized or "
                "oracle-backed evidence, or compute bounds."
            ),
        )
    return NegativeCertificate(
        blocking_type=BlockingType.MISSING_DISTRIBUTION,
        blocking_description=(
            f"Could not identify P({outcome_str}|do({treatment_str}))."
        ),
        technical_detail=status,
        quantitative_diagnostics={
            "identification_status": status,
            "algorithm_version": str(getattr(result, "algorithm_version", "") or ""),
            "proof_trace": list(getattr(result, "trace", []) or []),
        },
        constructive_message=(
            "Provide the missing identifying distributions or use an oracle-backed "
            "identification backend."
        ),
    )


def _identification_result_payload(result: object) -> dict[str, Any]:
    return {
        "status": str(getattr(getattr(result, "status", None), "value", "") or ""),
        "estimand_ast": _dump_estimand(getattr(result, "estimand_ast", None)),
        "algorithm_version": str(getattr(result, "algorithm_version", "") or ""),
        "trace": list(getattr(result, "trace", []) or []),
        "required_distributions_count": len(getattr(result, "required_distributions", []) or []),
        "proof_steps": [
            {
                "rule_name": str(getattr(step, "rule_name", "") or ""),
                "antecedent_vars": list(getattr(step, "antecedent_vars", ()) or ()),
                "consequent_vars": list(getattr(step, "consequent_vars", ()) or ()),
                "applied_to_graph_state": str(
                    getattr(step, "applied_to_graph_state", "") or ""
                ),
                "depth": int(getattr(step, "depth", 0) or 0),
            }
            for step in getattr(result, "proof_steps", []) or []
        ],
    }


def _strings_from_estimand_payload(payload: object) -> set[str]:
    interesting_keys = {
        "all_variables",
        "conditioning",
        "integration_vars",
        "intervention_set",
        "outcome",
        "summation_vars",
        "treatment",
        "variable",
        "variables",
    }
    found: set[str] = set()
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in interesting_keys:
                if isinstance(value, str):
                    found.add(value)
                elif isinstance(value, (list, tuple)):
                    found.update(str(item) for item in value if isinstance(item, str))
            found.update(_strings_from_estimand_payload(value))
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            found.update(_strings_from_estimand_payload(item))
    return found


def _required_vars_for_identification(
    *,
    id_result: object,
    fallback: frozenset[str],
    substantive_vars: tuple[str, ...],
) -> frozenset[str]:
    substantive = set(substantive_vars)
    variables = _strings_from_estimand_payload(getattr(id_result, "estimand_ast", None))
    variables = {var for var in variables if var in substantive}
    if not variables:
        variables = set(fallback)
    return frozenset(sorted(variables))


# ---------------------------------------------------------------------------
# Algorithm 3: Full Law Identification  (Nabi, Bhattacharya & Shpitser 2020)
# ---------------------------------------------------------------------------


def full_law_identify(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    mgraph_meta: MGraphMetadata,
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
        from polisyos.ir.analytics.recoverability import RecoveryScope

        certificate = _recoverability_certificate_from_result(
            result=rec,
            graph=graph,
            target_query=_target_query(treatment, outcome),
            scope=RecoveryScope.FULL_LAW,
            theorem_family="Mohan-Pearl-2021",
            completeness_regime="complete",
            warnings=("full_law_not_recoverable",),
        )
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
            metadata={"recoverability_certificate": certificate.to_summary_dict()},
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
        from polisyos.ir.analytics.recoverability import RecoveryScope

        certificate = _recoverability_certificate_from_result(
            result=rec,
            graph=graph,
            target_query="P(V)",
            scope=RecoveryScope.FULL_LAW,
            computable_functionals=("P(V)",),
            theorem_family="Nabi-Bhattacharya-Shpitser-2020",
            completeness_regime="complete",
        )
        return _dc.replace(
            id_result,
            trace=trace + list(id_result.trace),
            proof_steps=all_steps,
            algorithm_version="full_law_v1",
            metadata={
                **dict(getattr(id_result, "metadata", {}) or {}),
                "recoverability_certificate": certificate.to_summary_dict(),
                "computable_functionals": ["P(V)"],
            },
        )

    # Both stages succeeded — annotate estimand with recovery context
    combined_ast = _annotate_with_recovery(
        id_result.estimand_ast,
        rec.recovery_estimand,
    )
    from polisyos.ir.analytics.recoverability import RecoveryScope

    certificate = _recoverability_certificate_from_result(
        result=rec,
        graph=graph,
        target_query=_target_query(treatment, outcome),
        scope=RecoveryScope.FULL_LAW,
        expression_ast=rec.recovery_estimand,
        computable_functionals=("P(V)", _target_query(treatment, outcome)),
        theorem_family="Nabi-Bhattacharya-Shpitser-2020",
        completeness_regime="complete",
    )
    return _dc.replace(
        id_result,
        estimand_ast=combined_ast,
        trace=trace,
        proof_steps=all_steps,
        algorithm_version="full_law_v1",
        metadata={
            **dict(getattr(id_result, "metadata", {}) or {}),
            "recoverability_certificate": certificate.to_summary_dict(),
            "identification_estimand_ast": _dump_estimand(combined_ast),
        },
    )


def identify_joint_recoverability(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    mgraph_meta: MGraphMetadata,
    dataset_ref: str | None = None,
    oracle: str = "none",
) -> JointDecisionCertificate:
    """Joint ID + recoverability decision procedure for M-graphs.

    The implementation is a certified cascade:
      1. full-law recoverability fast path;
      2. standard ID on the projected causal graph;
      3. sound-incomplete direct recovery of variables used by the ID estimand;
      4. observational-query fallback for non-ID cases.

    The direct layer is intentionally conservative. It only returns
    ``IdentifiedAndRecoverable`` when every substantive variable referenced by
    the identified estimand passes the M-graph recoverability screen.
    """
    from polisyos.foundry.methods.catalog.causal.id_engine import (
        IdentificationStatus,
        ProofStep,
        id_with_oracle_fallback,
    )
    from polisyos.ir.analytics.estimand import (
        DistributionDomain,
        DistributionRef,
        EstimandAST,
    )
    from polisyos.ir.analytics.recoverability import (
        JointDecisionCertificate,
        JointDecisionStatus,
        RecoverabilityCertificateStatus,
        RecoveryScope,
    )

    target_query = _target_query(treatment, outcome)
    base_graph = _project_to_base_dag(graph, mgraph_meta)
    id_result = id_with_oracle_fallback(
        treatment=treatment,
        outcome=outcome,
        graph=base_graph,
        oracle=oracle,
        dataset_ref=dataset_ref,
    )
    id_status = str(id_result.status.value)

    full_rec = test_recoverability(
        query_vars=frozenset(mgraph_meta.substantive_vars),
        graph=graph,
        mgraph_meta=mgraph_meta,
    )
    full_law_computable = (
        ("P(V)",) if full_rec.status is RecoverabilityStatus.RECOVERABLE else ()
    )
    full_cert = _recoverability_certificate_from_result(
        result=full_rec,
        graph=graph,
        target_query="P(V)",
        scope=RecoveryScope.FULL_LAW,
        computable_functionals=full_law_computable,
        theorem_family="Nabi-Bhattacharya-Shpitser-2020",
        completeness_regime="complete",
        warnings=()
        if full_rec.status is RecoverabilityStatus.RECOVERABLE
        else ("full_law_not_recoverable",),
    )

    if full_rec.status is RecoverabilityStatus.RECOVERABLE:
        if id_result.status is IdentificationStatus.IDENTIFIED:
            cert = _recoverability_certificate_from_result(
                result=full_rec,
                graph=graph,
                target_query=target_query,
                scope=RecoveryScope.FULL_LAW,
                expression_ast=full_rec.recovery_estimand,
                computable_functionals=("P(V)", target_query),
                theorem_family="Nabi-Bhattacharya-Shpitser-2020",
                completeness_regime="complete",
            )
            return JointDecisionCertificate(
                verdict=JointDecisionStatus.IDENTIFIED_AND_RECOVERABLE,
                target_query=target_query,
                id_status=id_status,
                recoverability=cert,
                identification_result=_identification_result_payload(id_result),
                computable_functionals=("P(V)", target_query),
                recommended_estimator_family=cert.recommended_estimator_family,
                metadata={
                    "cascade_level": "full_law",
                    "identification_estimand_ast": _dump_estimand(id_result.estimand_ast),
                },
            )

        negative = _negative_certificate_from_id_failure(
            result=id_result,
            treatment=treatment,
            outcome=outcome,
        )
        negative = _attach_recoverability_to_negative_certificate(
            negative,
            recoverability=full_cert,
            verdict=JointDecisionStatus.RECOVERABLE_BUT_NOT_IDENTIFIED,
            computable_functionals=("P(V)",),
        )
        return JointDecisionCertificate(
            verdict=JointDecisionStatus.RECOVERABLE_BUT_NOT_IDENTIFIED,
            target_query=target_query,
            id_status=id_status,
            recoverability=full_cert,
            identification_result=_identification_result_payload(id_result),
            negative_certificate=negative,
            computable_functionals=("P(V)",),
            recommended_estimator_family=full_cert.recommended_estimator_family,
            metadata={"cascade_level": "full_law_non_id"},
        )

    if id_result.status is IdentificationStatus.IDENTIFIED:
        required_vars = _required_vars_for_identification(
            id_result=id_result,
            fallback=treatment | outcome,
            substantive_vars=mgraph_meta.substantive_vars,
        )
        direct_rec = test_recoverability(
            query_vars=required_vars,
            graph=graph,
            mgraph_meta=mgraph_meta,
        )
        direct_steps = list(direct_rec.proof_steps)
        direct_steps.extend(
            [
                ProofStep(
                    rule_name="DIRECT_CAUSAL_RECOVERY_SCREEN",
                    antecedent_vars=tuple(sorted(required_vars)),
                    consequent_vars=tuple(sorted(outcome)),
                    applied_to_graph_state=(
                        "Sound-incomplete direct recovery: every substantive "
                        "variable referenced by the identified estimand is recoverable."
                    ),
                    depth=0,
                )
            ]
        )
        direct_result = dataclasses.replace(direct_rec, proof_steps=direct_steps)
        if direct_rec.status is RecoverabilityStatus.RECOVERABLE:
            cert = _recoverability_certificate_from_result(
                result=direct_result,
                graph=graph,
                target_query=target_query,
                scope=RecoveryScope.CAUSAL_QUERY,
                expression_ast=id_result.estimand_ast,
                computable_functionals=(target_query,),
                theorem_family="Mohan-Pearl-2014 + ID-v1",
                completeness_regime="sound_incomplete",
                metadata={"required_recoverable_variables": sorted(required_vars)},
            )
            return JointDecisionCertificate(
                verdict=JointDecisionStatus.IDENTIFIED_AND_RECOVERABLE,
                target_query=target_query,
                id_status=id_status,
                recoverability=cert,
                identification_result=_identification_result_payload(id_result),
                computable_functionals=(target_query,),
                recommended_estimator_family=cert.recommended_estimator_family,
                metadata={
                    "cascade_level": "direct_query",
                    "full_law_recoverability": full_cert.to_summary_dict(),
                },
            )

        cert = _recoverability_certificate_from_result(
            result=direct_result,
            graph=graph,
            target_query=target_query,
            scope=RecoveryScope.CAUSAL_QUERY,
            expression_ast=id_result.estimand_ast,
            status_override=RecoverabilityCertificateStatus.RECOVERABLE_UNDER_ASSUMPTIONS,
            warnings=("assumption_dependent_missingness_recovery",),
            theorem_family="Mohan-Pearl-2014 + ID-v1",
            completeness_regime="sound_incomplete",
            metadata={
                "required_recoverable_variables": sorted(required_vars),
                "full_law_recoverability": full_cert.to_summary_dict(),
            },
        )
        negative = _negative_certificate_from_recoverability(cert)
        negative = _attach_recoverability_to_negative_certificate(
            negative,
            recoverability=cert,
            verdict=JointDecisionStatus.IDENTIFIED_BUT_NOT_RECOVERABLE,
        )
        return JointDecisionCertificate(
            verdict=JointDecisionStatus.IDENTIFIED_BUT_NOT_RECOVERABLE,
            target_query=target_query,
            id_status=id_status,
            recoverability=cert,
            identification_result=_identification_result_payload(id_result),
            negative_certificate=negative,
            metadata={"cascade_level": "direct_query_repairs"},
        )

    obs_vars = treatment | outcome
    obs_rec = test_recoverability(
        query_vars=obs_vars,
        graph=graph,
        mgraph_meta=mgraph_meta,
    )
    y_vars = tuple(sorted(outcome))
    x_vars = tuple(sorted(treatment))
    obs_ast = EstimandAST(
        query_str=f"P({', '.join(y_vars)}|{', '.join(x_vars)})",
        root=DistributionRef(
            domain=DistributionDomain.SOURCE,
            variables=y_vars,
            conditioning=x_vars,
            dataset_ref=dataset_ref,
        ),
        treatment=x_vars[0] if x_vars else "",
        outcome=y_vars[0] if y_vars else "",
        all_variables=tuple(sorted(obs_vars)),
        identification_method="observational_recoverability_fallback",
    )
    negative = _negative_certificate_from_id_failure(
        result=id_result,
        treatment=treatment,
        outcome=outcome,
    )
    if obs_rec.status is RecoverabilityStatus.RECOVERABLE:
        obs_cert = _recoverability_certificate_from_result(
            result=obs_rec,
            graph=graph,
            target_query=obs_ast.query_str,
            scope=RecoveryScope.OBSERVATIONAL_QUERY,
            expression_ast=obs_ast,
            computable_functionals=(obs_ast.query_str,),
            theorem_family="Mohan-Pearl-2014",
            completeness_regime="sound_incomplete",
        )
        negative = _attach_recoverability_to_negative_certificate(
            negative,
            recoverability=obs_cert,
            verdict=JointDecisionStatus.RECOVERABLE_BUT_NOT_IDENTIFIED,
            computable_functionals=(obs_ast.query_str,),
        )
        return JointDecisionCertificate(
            verdict=JointDecisionStatus.RECOVERABLE_BUT_NOT_IDENTIFIED,
            target_query=target_query,
            id_status=id_status,
            recoverability=obs_cert,
            identification_result=_identification_result_payload(id_result),
            negative_certificate=negative,
            computable_functionals=(obs_ast.query_str,),
            recommended_estimator_family=obs_cert.recommended_estimator_family,
            metadata={
                "cascade_level": "observational_fallback",
                "full_law_recoverability": full_cert.to_summary_dict(),
            },
        )

    obs_cert = _recoverability_certificate_from_result(
        result=obs_rec,
        graph=graph,
        target_query=obs_ast.query_str,
        scope=RecoveryScope.OBSERVATIONAL_QUERY,
        status_override=RecoverabilityCertificateStatus.RECOVERABLE_UNDER_ASSUMPTIONS,
        warnings=("observational_query_recovery_requires_repairs",),
        theorem_family="Mohan-Pearl-2014",
        completeness_regime="sound_incomplete",
        metadata={"full_law_recoverability": full_cert.to_summary_dict()},
    )
    negative = _attach_recoverability_to_negative_certificate(
        negative,
        recoverability=obs_cert,
        verdict=JointDecisionStatus.NOT_IDENTIFIED,
    )
    return JointDecisionCertificate(
        verdict=JointDecisionStatus.NOT_IDENTIFIED,
        target_query=target_query,
        id_status=id_status,
        recoverability=obs_cert,
        identification_result=_identification_result_payload(id_result),
        negative_certificate=negative,
        metadata={"cascade_level": "not_identified"},
    )


__all__ = [
    "RecoverabilityResult",
    "RecoverabilityStatus",
    "full_law_identify",
    "identify_joint_recoverability",
    "ordered_recovery",
    "test_recoverability",
]
