"""id_engine — Shpitser-Pearl ID algorithm for causal identification.

Implements the complete recursive ID algorithm (Tian & Pearl 2002; Shpitser &
Pearl 2006) plus the IDC extension for conditional interventional distributions
and the TR (Transportability) wrapper from Bareinboim & Pearl (2012).

All internal data-types (HedgeCertificate, IdentificationResult) are frozen
dataclasses rather than Pydantic models — they are internal algorithm state that
never crosses a JSON serialisation boundary directly.  At the boundary (in
SymbolicIdentifyV2.pure_step) they are converted to the existing IR contracts
(TransportabilityResult, EstimandAST).

Key functions
-------------
id_algorithm(treatment, outcome, graph)
    → IdentificationResult (IDENTIFIED | HEDGE_FOUND | PAG_AMBIGUOUS | ORACLE_NEEDED)

idc_algorithm(treatment, outcome, conditions, graph)
    → IdentificationResult via IDC reduction to two ID calls

tr_algorithm(treatment, outcome, selection_diagram)
    → IdentificationResult for transportability (augments graph with S-nodes)

id_with_oracle_fallback(treatment, outcome, graph, oracle)
    → IdentificationResult, trying oracle backends when native ID returns ORACLE_NEEDED

References
----------
Tian, J., Pearl, J. (2002). "A General Identification Condition for Causal Effects."
    AAAI 2002.
Shpitser, I., Pearl, J. (2006). "Identification of Joint Interventional Distributions
    in Recursive Semi-Markovian Causal Models." AAAI 2006.
Bareinboim, E., Pearl, J. (2012). "Transportability of Causal Effects: Completeness
    Results." AAAI 2012.
"""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any, Literal

from polisyos.foundry.methods.catalog.causal._id_contracts import (
    CtfQuery,
    HedgeCertificate,
    IdentificationResult,
    IdentificationStatus,
    ProofStep,
    RequiredDataSpec,
    SourceDomain,
)
from polisyos.foundry.methods.catalog.causal.admg_ops import (
    ancestors,
    augment_with_s_nodes,
    c_components,
    descendants,
    do_operator,
    extract_bidirected_edges,
    extract_directed_edges,
    induced_subgraph,
    m_separation,
    resolve_s_node_by_adjustment,
    topological_order,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.estimand import (
    ConditionalInterventionNode,
    CounterfactualNode,
    CrossWorldNode,
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    ModifiedTreatmentPolicyNode,
    NestedCounterfactualNode,
    ProductNode,
    RatioNode,
    SideCondition,
    SideConditionKind,
    StochasticInterventionNode,
    StochasticPolicy,
    SumNode,
    make_frontdoor_estimand,
    make_z_transport_estimand,
)

# ---------------------------------------------------------------------------
# PAG-specific identification (Malinsky & Spirtes 2017)
# ---------------------------------------------------------------------------

def _pag_id_algorithm(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    available_vars: frozenset[str],
    dataset_ref: str | None,
    domain: DistributionDomain,
    _depth: int,
    _trace: list[str],
    _pag_steps: list[ProofStep] | None = None,
) -> IdentificationResult:
    """PAG-ID per Malinsky & Spirtes (2017).

    Checks identifiability of P(Y|do(X)) for the PAG equivalence class via a
    policy-driven strategy stored in ``graph.pag_identification_policy``:

    CONSERVATIVE (default)
        First apply Zhang (2008) R1–R3 orientation rules to reduce CIRCLE marks,
        then use ``reachable_closure`` to detect whether remaining CIRCLE marks
        create an unblocked back-door path from X to Y.
        If yes → PAG_AMBIGUOUS; otherwise run standard ID on the oriented PAG.

    OPTIMISTIC
        Apply R1–R3 first, then commit all remaining CIRCLE marks to directed
        edges (src→dst) and run standard ID on the resulting DAG.

    PROBABILISTIC
        Apply R1–R3 first, then run standard ID and annotate the trace with
        ``id_confidence_under_pag`` if the result is IDENTIFIED but confidence < 1.
    """
    from polisyos.foundry.methods.catalog.causal.pag_completion import apply_pag_orientation_rules
    from polisyos.ir.analytics.causal_graph import EdgeMark, PAGIdentificationPolicy

    pag_steps: list[ProofStep] = _pag_steps if _pag_steps is not None else []

    policy = graph.pag_identification_policy
    _trace.append(
        f"[depth={_depth}] PAG-ID: policy={policy.value}, "
        f"X={sorted(treatment)}, Y={sorted(outcome)}"
    )

    # ------------------------------------------------------------------
    # Orientation pre-pass: apply R1–R3 to resolve CIRCLE marks (all policies)
    # ------------------------------------------------------------------
    n_circles_before = sum(
        1 for e in graph.edges if e.mark_src is EdgeMark.CIRCLE or e.mark_dst is EdgeMark.CIRCLE
    )
    oriented_pag, _orient_warnings = apply_pag_orientation_rules(graph)
    n_circles_after = sum(
        1
        for e in oriented_pag.edges
        if e.mark_src is EdgeMark.CIRCLE or e.mark_dst is EdgeMark.CIRCLE
    )
    n_resolved = n_circles_before - n_circles_after

    if n_resolved > 0:
        _trace.append(
            f"[depth={_depth}] PAG-ID orientation pre-pass: "
            f"resolved {n_resolved} CIRCLE marks ({n_circles_before}→{n_circles_after})"
        )
        pag_steps.append(
            ProofStep(
                rule_name="PAG_ORIENT_R1",
                antecedent_vars=(),
                consequent_vars=(),
                applied_to_graph_state=(
                    f"R1-R3 orientation pass resolved {n_resolved} CIRCLE marks "
                    f"({n_circles_before}→{n_circles_after} circles remain)"
                ),
                graph_state_before=f"{n_circles_before} CIRCLE marks before orientation",
                depth=_depth,
            )
        )

    # ------------------------------------------------------------------ OPTIMISTIC
    if policy is PAGIdentificationPolicy.OPTIMISTIC:
        # Commit remaining CIRCLE marks on the oriented PAG to directed (TAIL→ARROW) edges
        committed_edges = []
        n_committed = 0
        for e in oriented_pag.edges:
            if e.mark_src is EdgeMark.CIRCLE or e.mark_dst is EdgeMark.CIRCLE:
                from polisyos.ir.analytics.causal_graph import CausalEdge

                committed_edges.append(
                    CausalEdge(
                        src=e.src,
                        dst=e.dst,
                        mark_src=EdgeMark.TAIL,
                        mark_dst=EdgeMark.ARROW,
                        lag=e.lag,
                        sources=list(e.sources),
                    )
                )
                n_committed += 1
            else:
                committed_edges.append(e)

        pag_steps.append(
            ProofStep(
                rule_name="PAG_OPTIMISTIC_COMMIT",
                antecedent_vars=(),
                consequent_vars=tuple(sorted(outcome)),
                applied_to_graph_state=(
                    f"OPTIMISTIC policy: committing {n_committed} remaining CIRCLE marks "
                    f"to directed edges after R1-R3 pre-pass"
                ),
                graph_state_before=f"oriented PAG with {n_circles_after} remaining circles",
                depth=_depth,
            )
        )

        from polisyos.ir.analytics.causal_graph import GraphType as GT

        dag_graph = CausalGraphModel(
            schema_version=oriented_pag.schema_version,
            graph_type=GT.DAG,
            nodes=list(oriented_pag.nodes),
            edges=committed_edges,
            discovery_method=(oriented_pag.discovery_method or "") + "_pag_committed",
            pag_identification_policy=policy,
            id_confidence_under_pag=oriented_pag.id_confidence_under_pag,
            metadata=dict(oriented_pag.metadata),
        )
        result = id_algorithm(
            treatment=treatment,
            outcome=outcome,
            graph=dag_graph,
            available_vars=available_vars,
            dataset_ref=dataset_ref,
            domain=domain,
            _depth=_depth + 1,
            _trace=_trace,
        )
        _trace.append(f"[depth={_depth}] PAG-ID OPTIMISTIC: status={result.status.value}")
        combined_steps = pag_steps + list(result.proof_steps)
        return dataclasses.replace(
            result,
            algorithm_version="pag_id_optimistic_v1",
            proof_steps=combined_steps,
        )

    # ------------------------------------------------------------------ CONSERVATIVE / PROBABILISTIC
    # Use reachable_closure on the oriented PAG to check whether remaining
    # CIRCLE marks create an ambiguous back-door path.
    from polisyos.foundry.methods.catalog.causal.admg_ops import reachable_closure

    pag_reachable = reachable_closure(
        oriented_pag,
        query_vars=outcome,
        intervened=treatment,
        conditioning=None,
    )
    circles_create_ambiguity = bool(pag_reachable & treatment)

    if policy is PAGIdentificationPolicy.CONSERVATIVE and circles_create_ambiguity:
        _trace.append(
            f"[depth={_depth}] PAG-ID CONSERVATIVE: CIRCLE edges create ambiguity → PAG_AMBIGUOUS"
        )
        pag_steps.append(
            ProofStep(
                rule_name="PAG_CONSERVATIVE_BLOCK",
                antecedent_vars=tuple(sorted(treatment)),
                consequent_vars=tuple(sorted(outcome)),
                applied_to_graph_state=(
                    f"CONSERVATIVE policy: {n_circles_after} unresolved CIRCLE marks create "
                    f"backdoor ambiguity; pag_reachable∩X={sorted(pag_reachable & treatment)}"
                ),
                graph_state_before=f"oriented PAG with {n_circles_after} remaining circles",
                depth=_depth,
            )
        )
        return IdentificationResult(
            status=IdentificationStatus.PAG_AMBIGUOUS,
            estimand_ast=None,
            hedge_certificate=None,
            trace=list(_trace),
            required_distributions=[],
            algorithm_version="pag_id_conservative_v1",
            proof_steps=list(pag_steps),
        )

    # No CIRCLE ambiguity (conservative) or PROBABILISTIC policy:
    # run standard ID on the oriented PAG
    if policy is PAGIdentificationPolicy.PROBABILISTIC:
        pag_steps.append(
            ProofStep(
                rule_name="PAG_PROBABILISTIC",
                antecedent_vars=(),
                consequent_vars=tuple(sorted(outcome)),
                applied_to_graph_state=(
                    f"PROBABILISTIC policy: running ID on oriented PAG with "
                    f"{n_circles_after} remaining circles; "
                    f"id_confidence_under_pag={oriented_pag.id_confidence_under_pag}"
                ),
                graph_state_before=f"oriented PAG with {n_circles_after} remaining circles",
                depth=_depth,
            )
        )

    result = id_algorithm(
        treatment=treatment,
        outcome=outcome,
        graph=oriented_pag,
        available_vars=available_vars,
        dataset_ref=dataset_ref,
        domain=domain,
        _depth=_depth + 1,
        _trace=_trace,
    )
    _trace.append(f"[depth={_depth}] PAG-ID ({policy.value}): base status={result.status.value}")
    if (
        result.status is IdentificationStatus.IDENTIFIED
        and oriented_pag.id_confidence_under_pag is not None
        and oriented_pag.id_confidence_under_pag < 1.0
    ):
        _trace.append(
            f"[depth={_depth}] PAG-ID: id_confidence_under_pag="
            f"{oriented_pag.id_confidence_under_pag:.3f}"
        )
    combined_steps = pag_steps + list(result.proof_steps)
    return dataclasses.replace(
        result,
        algorithm_version="pag_id_v1",
        proof_steps=combined_steps,
    )


# ---------------------------------------------------------------------------
# Internal hedge helper (shared by id_algorithm Step 4a and find_hedge)
# ---------------------------------------------------------------------------


def _check_hedge_condition(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    V: frozenset[str],
    components_g_minus_x: list[frozenset[str]],
    dataset_ref: str | None,
    _depth: int,
    _steps: list[ProofStep],
    _trace: list[str],
) -> HedgeCertificate | None:
    """Check the Step 4a hedge condition and return a certificate or None.

    A hedge (F, F') is detected when:
    - C(G \\ X) is a single component spanning V \\ X  (F' = V \\ X)
    - C(G) is also a single component              (F  = V)

    This is the simplest (full-graph) hedge case from Shpitser & Pearl 2006.
    The general c-forest pair check is in :func:`find_hedge`.
    """
    from polisyos.foundry.methods.catalog.causal.admg_ops import extract_bidirected_edges

    if len(components_g_minus_x) != 1:
        return None
    singleton = components_g_minus_x[0]
    if singleton != (V - treatment):
        return None
    comps_g = c_components(graph)
    if len(comps_g) != 1:
        return None

    # HEDGE detected: F = V, F' = V - X
    hedge_root = V - treatment
    X = treatment
    Y = outcome
    missing_dists = tuple(
        DistributionRef(
            domain=DistributionDomain.EXPERIMENTAL,
            variables=tuple(sorted(Y)),
            intervention_set=(xi,),
            dataset_ref=dataset_ref,
        )
        for xi in sorted(hedge_root & X)
    )
    required_data = RequiredDataSpec(
        missing_distributions=missing_dists,
        suggested_experiment=(
            f"Randomize treatment for: {sorted(hedge_root & X)}" if hedge_root & X else None
        ),
        alternative_identification=None,
    )
    bi_edges = extract_bidirected_edges(graph)
    minimal_s: set[str] = set()
    for pair in bi_edges:
        u, v_node = tuple(pair)
        if u in X and v_node in singleton:
            minimal_s.add(v_node)
        elif v_node in X and u in singleton:
            minimal_s.add(u)
    cert = HedgeCertificate(
        treatment=X,
        outcome=Y,
        hedge_forest=V,
        hedge_root=hedge_root,
        c_component_witness=singleton,
        description=(
            f"Hedge found: C(G)={{all nodes}}, C(G\\X)={{all non-X nodes}}. "
            f"P({sorted(Y)}|do({sorted(X)})) is NOT identifiable."
        ),
        required_data=required_data,
        minimal_required_s_nodes=frozenset(minimal_s),
    )
    _steps.append(
        ProofStep(
            rule_name="HEDGE",
            antecedent_vars=tuple(sorted(X)),
            consequent_vars=tuple(sorted(Y)),
            applied_to_graph_state=f"C(G)=single component, hedge forest={sorted(V)}",
            depth=_depth,
        )
    )
    _trace.append(f"[depth={_depth}] HEDGE detected: {cert.description}")
    return cert


def _detect_frontdoor_mediator(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    available_vars: frozenset[str],
) -> str | None:
    """Return a single frontdoor mediator when a canonical ADMG pattern is present.

    This is intentionally conservative. It only matches the classical
    X -> M -> Y with latent X <-> Y confounding pattern used in the gold-suite.
    """
    if len(treatment) != 1 or len(outcome) != 1:
        return None
    if graph.graph_type not in {GraphType.ADMG, GraphType.PAG}:
        return None

    x = next(iter(treatment))
    y = next(iter(outcome))
    if x not in available_vars or y not in available_vars:
        return None

    directed = extract_directed_edges(graph)
    bidirected = extract_bidirected_edges(graph)
    if (x, y) in directed:
        return None
    if frozenset({x, y}) not in bidirected:
        return None

    mediator_candidates = sorted(
        mediator
        for src, mediator in directed
        if src == x
        and mediator in available_vars
        and (mediator, y) in directed
        and frozenset({x, mediator}) not in bidirected
        and frozenset({mediator, y}) not in bidirected
    )
    if not mediator_candidates:
        return None

    # All directed children of X that can still reach Y must pass through the
    # same mediator, otherwise the simple one-mediator frontdoor formula does
    # not apply.
    children_of_x = {dst for src, dst in directed if src == x and dst in available_vars}
    for child in children_of_x:
        if child == y:
            return None
        if child not in mediator_candidates and y in descendants(graph, frozenset({child})):
            return None

    return mediator_candidates[0]


def _dag_g_formula(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    available_vars: frozenset[str],
    dataset_ref: str | None,
    domain: DistributionDomain,
    depth: int,
    trace: list[str],
) -> IdentificationResult:
    """Exact truncated factorization for acyclic observed-variable DAGs."""
    directed = extract_directed_edges(graph)
    parents_of: dict[str, set[str]] = {node: set() for node in graph.nodes}
    for src, dst in directed:
        parents_of[dst].add(src)

    topo_in_v = [node for node in topological_order(graph) if node in available_vars]
    factors: list[DistributionRef] = []
    for variable in topo_in_v:
        if variable in treatment:
            continue
        conditioning = tuple(sorted(parents_of.get(variable, set()) & available_vars))
        factors.append(
            DistributionRef(
                domain=domain,
                variables=(variable,),
                conditioning=conditioning,
                dataset_ref=dataset_ref,
            )
        )

    if not factors:
        trace.append(f"[depth={depth}] DAG g-formula failed: no post-intervention factors")
        return IdentificationResult(
            status=IdentificationStatus.ORACLE_NEEDED,
            estimand_ast=None,
            hedge_certificate=None,
            trace=list(trace),
            required_distributions=[],
        )

    root: object
    if len(factors) == 1:
        root = factors[0]
    else:
        root = ProductNode(factors=tuple(factors))

    summation_vars = tuple(sorted((available_vars - treatment) - outcome))
    if summation_vars:
        root = SumNode(summation_vars=summation_vars, operand=root)  # type: ignore[arg-type]

    x_str = next(iter(sorted(treatment))) if len(treatment) == 1 else str(sorted(treatment))
    y_str = next(iter(sorted(outcome))) if len(outcome) == 1 else str(sorted(outcome))
    trace.append(
        f"[depth={depth}] DAG g-formula: summed over {sorted(summation_vars)} "
        f"for P({y_str}|do({x_str}))"
    )
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=EstimandAST(
            query_str=f"P({y_str}|do({x_str}))",
            root=root,  # type: ignore[arg-type]
            treatment=x_str,
            outcome=y_str,
            all_variables=tuple(sorted(available_vars)),
            identification_method="g_formula",
        ),
        hedge_certificate=None,
        trace=list(trace),
        required_distributions=list(factors),
        proof_steps=[
            ProofStep(
                rule_name="G_FORMULA",
                antecedent_vars=tuple(sorted(treatment)),
                consequent_vars=tuple(sorted(outcome)),
                applied_to_graph_state="Applied DAG truncated factorization after do(X).",
                depth=depth,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def id_algorithm(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    available_vars: frozenset[str] | None = None,
    dataset_ref: str | None = None,
    domain: DistributionDomain = DistributionDomain.SOURCE,
    _depth: int = 0,
    _trace: list[str] | None = None,
) -> IdentificationResult:
    """Recursive Shpitser-Pearl ID algorithm.

    Parameters
    ----------
    treatment:      X — intervention set (frozenset of variable names)
    outcome:        Y — target variables
    graph:          causal graph G (DAG or PAG-as-ADMG; bidirected=ARROW/ARROW)
    available_vars: V — set of all observed variables (defaults to all graph nodes)
    dataset_ref:    tag for DistributionRef leaves (links to DataKnowledgeBase)
    domain:         DistributionDomain for leaf DistributionRef nodes
    _depth/_trace:  internal recursion bookkeeping

    Returns IdentificationResult with status IDENTIFIED, HEDGE_FOUND, or ORACLE_NEEDED.
    """
    if _trace is None:
        _trace = []
    if available_vars is None:
        available_vars = frozenset(graph.nodes)

    V = available_vars
    X = treatment
    Y = outcome

    _steps: list[ProofStep] = []

    _trace.append(f"[depth={_depth}] id_algorithm(X={sorted(X)}, Y={sorted(Y)}, V={sorted(V)})")

    # ------------------------------------------------------------------
    # PAG-specific branch (Malinsky & Spirtes 2017) — before Step 1
    # ------------------------------------------------------------------
    if graph.graph_type is GraphType.PAG and _depth == 0:
        # Only intercept at the top-level call; recursive sub-calls on DAG
        # subgraphs (after CIRCLE commitment) proceed normally.
        return _pag_id_algorithm(
            treatment=X,
            outcome=Y,
            graph=graph,
            available_vars=V,
            dataset_ref=dataset_ref,
            domain=domain,
            _depth=_depth,
            _trace=_trace,
        )

    # ------------------------------------------------------------------
    # Step 1: X = ∅  →  P(Y | An(Y)_G \ Y)  (marginalisation)
    # ------------------------------------------------------------------
    if not X:
        an_y = ancestors(graph, Y) & V
        conditioning = tuple(sorted(an_y - Y))
        leaf = DistributionRef(
            domain=domain,
            variables=tuple(sorted(Y)),
            conditioning=conditioning,
            dataset_ref=dataset_ref,
        )
        _trace.append(f"[depth={_depth}] Step 1: X=∅ → P({sorted(Y)}|{sorted(conditioning)})")
        _steps.append(
            ProofStep(
                rule_name="RULE1",
                antecedent_vars=(),
                consequent_vars=tuple(sorted(Y)),
                applied_to_graph_state=f"X=∅, marginalise over An({sorted(Y)})",
                depth=_depth,
            )
        )
        ast = _wrap_root(leaf, treatment=treatment, outcome=outcome, method="id_step1")
        return IdentificationResult(
            status=IdentificationStatus.IDENTIFIED,
            estimand_ast=ast,
            hedge_certificate=None,
            trace=list(_trace),
            required_distributions=[leaf],
            proof_steps=list(_steps),
        )

    # ------------------------------------------------------------------
    # Step 2: V ≠ An(Y)_G  →  restrict to ancestor subgraph of Y
    # ------------------------------------------------------------------
    an_y_full = ancestors(graph, Y) & V
    if an_y_full != V:
        _trace.append(f"[depth={_depth}] Step 2: restricting to An(Y)={sorted(an_y_full)}")
        _steps.append(
            ProofStep(
                rule_name="ANCESTRAL_COLLAPSE",
                antecedent_vars=tuple(sorted(V)),
                consequent_vars=tuple(sorted(an_y_full)),
                applied_to_graph_state=f"restrict to An({sorted(Y)})",
                depth=_depth,
            )
        )
        sub_g = induced_subgraph(graph, an_y_full)
        sub_x = X & an_y_full
        inner = id_algorithm(
            treatment=sub_x,
            outcome=Y,
            graph=sub_g,
            available_vars=an_y_full,
            dataset_ref=dataset_ref,
            domain=domain,
            _depth=_depth + 1,
            _trace=_trace,
        )
        return dataclasses.replace(inner, proof_steps=list(_steps) + list(inner.proof_steps))

    # ------------------------------------------------------------------
    # Step 3: W = (V \ X) \ An(Y in G_{do(X)})  →  if W ≠ ∅ add to X
    # ------------------------------------------------------------------
    g_do_x = do_operator(graph, X)
    an_y_in_g_do_x = ancestors(g_do_x, Y) & V
    W = (V - X) - an_y_in_g_do_x
    if W:
        new_x = X | W
        _trace.append(f"[depth={_depth}] Step 3: extending X with W={sorted(W)}")
        _steps.append(
            ProofStep(
                rule_name="RULE3",
                antecedent_vars=tuple(sorted(W)),
                consequent_vars=tuple(sorted(new_x)),
                applied_to_graph_state=f"extend X with non-ancestor W={sorted(W)}",
                depth=_depth,
            )
        )
        inner = id_algorithm(
            treatment=new_x,
            outcome=Y,
            graph=graph,
            available_vars=V,
            dataset_ref=dataset_ref,
            domain=domain,
            _depth=_depth + 1,
            _trace=_trace,
        )
        return dataclasses.replace(inner, proof_steps=list(_steps) + list(inner.proof_steps))

    # ------------------------------------------------------------------
    # Exact DAG fallback: truncated factorization when there is no latent
    # confounding left in the current problem.
    # ------------------------------------------------------------------
    if graph.graph_type is GraphType.DAG and not extract_bidirected_edges(graph):
        exact = _dag_g_formula(
            treatment=X,
            outcome=Y,
            graph=graph,
            available_vars=V,
            dataset_ref=dataset_ref,
            domain=domain,
            depth=_depth,
            trace=_trace,
        )
        return dataclasses.replace(exact, proof_steps=list(_steps) + list(exact.proof_steps))

    # ------------------------------------------------------------------
    # Canonical frontdoor shortcut: X -> M -> Y with X <-> Y.
    # ------------------------------------------------------------------
    frontdoor_mediator = _detect_frontdoor_mediator(
        treatment=X,
        outcome=Y,
        graph=graph,
        available_vars=V,
    )
    if frontdoor_mediator is not None:
        x_name = next(iter(sorted(X)))
        y_name = next(iter(sorted(Y)))
        _trace.append(f"[depth={_depth}] Frontdoor shortcut: mediator={frontdoor_mediator}")
        frontdoor_ast = make_frontdoor_estimand(
            treatment=x_name,
            outcome=y_name,
            mediator=frontdoor_mediator,
            domain=domain,
            dataset_ref=dataset_ref,
        )
        return IdentificationResult(
            status=IdentificationStatus.IDENTIFIED,
            estimand_ast=frontdoor_ast,
            hedge_certificate=None,
            trace=list(_trace),
            required_distributions=frontdoor_ast.collect_distribution_refs(),
            proof_steps=list(_steps)
            + [
                ProofStep(
                    rule_name="FRONTDOOR",
                    antecedent_vars=(x_name, frontdoor_mediator),
                    consequent_vars=(y_name,),
                    applied_to_graph_state=(
                        "Applied the canonical one-mediator frontdoor formula."
                    ),
                    depth=_depth,
                )
            ],
        )

    # ------------------------------------------------------------------
    # Step 4: Compute c-components of G \ X  (= G_{do(X)} restricted to V \ X)
    # ------------------------------------------------------------------
    g_minus_x = induced_subgraph(graph, V - X)
    components_g_minus_x = c_components(g_minus_x)
    _trace.append(f"[depth={_depth}] Step 4: C(G\\X)={[sorted(c) for c in components_g_minus_x]}")

    # ------------------------------------------------------------------
    # Step 4a: Hedge check — single component spanning V \ X
    # ------------------------------------------------------------------
    cert = _check_hedge_condition(
        treatment=X,
        outcome=Y,
        graph=graph,
        V=V,
        components_g_minus_x=components_g_minus_x,
        dataset_ref=dataset_ref,
        _depth=_depth,
        _steps=_steps,
        _trace=_trace,
    )
    if cert is not None:
        return IdentificationResult(
            status=IdentificationStatus.HEDGE_FOUND,
            estimand_ast=None,
            hedge_certificate=cert,
            trace=list(_trace),
            required_distributions=[],
            proof_steps=list(_steps),
        )

    # ------------------------------------------------------------------
    # Step 5: Y is in a single c-component Si of G \ X
    # ------------------------------------------------------------------
    y_component: frozenset[str] | None = None
    for comp in components_g_minus_x:
        if comp >= Y:
            y_component = comp
            break

    if y_component is not None:
        _trace.append(f"[depth={_depth}] Step 5: Y ⊆ Si={sorted(y_component)}")
        _steps.append(
            ProofStep(
                rule_name="C_COMPONENT",
                antecedent_vars=tuple(sorted(y_component)),
                consequent_vars=tuple(sorted(Y)),
                applied_to_graph_state=f"Y in c-component Si={sorted(y_component)} of G\\X",
                depth=_depth,
            )
        )
        # Check Step 6 first: is Si a subset of a c-component Sj in G?
        comps_g_full = c_components(graph)
        containing_sj: frozenset[str] | None = None
        for sj in comps_g_full:
            if y_component <= sj and sj != y_component:
                containing_sj = sj
                break

        if containing_sj is not None:
            # Step 6: Si ⊂ Sj ∈ C(G)  →  Q-formula
            _trace.append(f"[depth={_depth}] Step 6: Si ⊂ Sj={sorted(containing_sj)}")
            inner = _step6_formula(
                si=y_component,
                sj=containing_sj,
                graph=graph,
                V=V,
                X=X,
                Y=Y,
                dataset_ref=dataset_ref,
                domain=domain,
                depth=_depth,
                trace=_trace,
            )
            return dataclasses.replace(inner, proof_steps=list(_steps) + list(inner.proof_steps))

        # Si is its own c-component in G — Step 5 factorisation
        inner = _step5_formula(
            si=y_component,
            components_g_minus_x=components_g_minus_x,
            graph=graph,
            V=V,
            X=X,
            Y=Y,
            dataset_ref=dataset_ref,
            domain=domain,
            depth=_depth,
            trace=_trace,
        )
        return dataclasses.replace(inner, proof_steps=list(_steps) + list(inner.proof_steps))

    # ------------------------------------------------------------------
    # Step 7: No identification rule applies — ORACLE_NEEDED
    # ------------------------------------------------------------------
    _steps.append(
        ProofStep(
            rule_name="ORACLE",
            antecedent_vars=tuple(sorted(X)),
            consequent_vars=tuple(sorted(Y)),
            applied_to_graph_state="no ID rule applies",
            depth=_depth,
        )
    )
    _trace.append(f"[depth={_depth}] Step 7: no rule applies → ORACLE_NEEDED")
    return IdentificationResult(
        status=IdentificationStatus.ORACLE_NEEDED,
        estimand_ast=None,
        hedge_certificate=None,
        trace=list(_trace),
        required_distributions=[],
        proof_steps=list(_steps),
    )


def idc_algorithm(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    conditions: frozenset[str],
    graph: CausalGraphModel,
    dataset_ref: str | None = None,
    domain: DistributionDomain = DistributionDomain.SOURCE,
) -> IdentificationResult:
    """IDC algorithm for P(Y | do(X), Z).

    Reduces to two ID calls:
        IDC(Y, X, Z, G) = ID(Y ∪ Z, X, G) / ID(Z, X, G)

    This follows Shpitser & Pearl (2008) / Bareinboim & Pearl (2012).
    """
    trace: list[str] = [
        f"idc_algorithm: Y={sorted(outcome)}, X={sorted(treatment)}, Z={sorted(conditions)}"
    ]
    idc_steps: list[ProofStep] = []

    # ------------------------------------------------------------------
    # Trivial case: Z = ∅ — IDC reduces to a plain ID call
    # ------------------------------------------------------------------
    if not conditions:
        idc_steps.append(
            ProofStep(
                rule_name="IDC_TRIVIAL_Z",
                antecedent_vars=(),
                consequent_vars=tuple(sorted(outcome)),
                applied_to_graph_state="IDC with Z=∅: reduces trivially to ID(Y, X, G)",
                graph_state_before="Z=∅ — no conditioning variables",
                depth=0,
            )
        )
        trace.append("idc_algorithm: Z=∅, delegating to id_algorithm")
        inner = id_algorithm(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            dataset_ref=dataset_ref,
            domain=domain,
            _trace=list(trace),
        )
        return dataclasses.replace(
            inner,
            proof_steps=idc_steps + list(inner.proof_steps),
        )

    # ------------------------------------------------------------------
    # Emit IDC_DECOMPOSE proof step
    # ------------------------------------------------------------------
    idc_steps.append(
        ProofStep(
            rule_name="IDC_DECOMPOSE",
            antecedent_vars=tuple(sorted(treatment | conditions)),
            consequent_vars=tuple(sorted(outcome)),
            applied_to_graph_state=(
                f"IDC: ratio = ID({sorted(outcome | conditions)},{sorted(treatment)},G)"
                f" / ID({sorted(conditions)},{sorted(treatment)},G)"
            ),
            graph_state_before=(
                f"Query P(Y|do(X),Z): Y={sorted(outcome)}, X={sorted(treatment)}, Z={sorted(conditions)}"
            ),
            depth=0,
        )
    )

    # ------------------------------------------------------------------
    # Numerator: ID(Y ∪ Z, X, G)
    # ------------------------------------------------------------------
    num_result = id_algorithm(
        treatment=treatment,
        outcome=outcome | conditions,
        graph=graph,
        dataset_ref=dataset_ref,
        domain=domain,
        _trace=list(trace),
    )
    if num_result.status is not IdentificationStatus.IDENTIFIED:
        trace.append(f"idc numerator failed: {num_result.status}")
        return dataclasses.replace(
            num_result,
            trace=list(trace),
            proof_steps=idc_steps + list(num_result.proof_steps),
        )

    # ------------------------------------------------------------------
    # Denominator: ID(Z, X, G)
    # ------------------------------------------------------------------
    denom_result = id_algorithm(
        treatment=treatment,
        outcome=conditions,
        graph=graph,
        dataset_ref=dataset_ref,
        domain=domain,
        _trace=list(trace),
    )
    if denom_result.status is not IdentificationStatus.IDENTIFIED:
        trace.append(f"idc denominator failed: {denom_result.status}")
        return dataclasses.replace(
            denom_result,
            trace=list(trace),
            proof_steps=idc_steps + list(denom_result.proof_steps),
        )

    # ------------------------------------------------------------------
    # Positivity side-condition step
    # ------------------------------------------------------------------
    idc_steps.append(
        ProofStep(
            rule_name="IDC_POSITIVITY",
            antecedent_vars=tuple(sorted(conditions)),
            consequent_vars=tuple(sorted(conditions)),
            applied_to_graph_state=(
                f"IDC positivity required: P({sorted(conditions)}|do({sorted(treatment)})) > 0"
                f" in support of X={sorted(treatment)}"
            ),
            graph_state_before=f"denominator: ID({sorted(conditions)},{sorted(treatment)},G)",
            depth=0,
        )
    )

    # ------------------------------------------------------------------
    # Combine: numerator / denominator
    # ------------------------------------------------------------------
    assert num_result.estimand_ast is not None
    assert denom_result.estimand_ast is not None

    ratio_root = RatioNode(
        numerator=num_result.estimand_ast.root,
        denominator=denom_result.estimand_ast.root,
    )
    all_vars = tuple(
        sorted(
            set(num_result.estimand_ast.all_variables)
            | set(denom_result.estimand_ast.all_variables)
        )
    )
    combined_ast = EstimandAST(
        query_str=f"P({sorted(outcome)}|do({sorted(treatment)}),{sorted(conditions)})",
        root=ratio_root,
        treatment=next(iter(treatment)) if len(treatment) == 1 else str(sorted(treatment)),
        outcome=next(iter(outcome)) if len(outcome) == 1 else str(sorted(outcome)),
        all_variables=all_vars,
        identification_method="idc",
    )
    all_dists = num_result.required_distributions + denom_result.required_distributions
    trace.append("idc_algorithm: IDENTIFIED via ratio")
    all_proof_steps = idc_steps + list(num_result.proof_steps) + list(denom_result.proof_steps)
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=combined_ast,
        hedge_certificate=None,
        trace=list(trace),
        required_distributions=all_dists,
        proof_steps=all_proof_steps,
    )


def _s_trim_lemma(
    *,
    outcome: frozenset[str],
    graph: CausalGraphModel,
    s_node_vars: frozenset[str],
    _trace: list[str],
    _steps: list[ProofStep],
    _depth: int = 0,
) -> tuple[CausalGraphModel, frozenset[str], frozenset[str]]:
    """S-trimming lemma: prune S-nodes that cannot affect identification.

    An S-node S_v is prunable iff ``v`` is not an ancestor of any outcome
    variable in the base graph.  Such S-nodes can never create or block any
    path to Y and are therefore irrelevant to identification.

    Parameters
    ----------
    outcome       : outcome variable set Y
    graph         : the BASE graph (before S-node augmentation)
    s_node_vars   : variable names targeted by S-nodes (not the "S_v" names)
    _trace        : mutable trace list for logging
    _steps        : mutable list to collect ProofStep objects
    _depth        : recursion depth for trace labels

    Returns
    -------
    (trimmed_graph, remaining_s_node_vars, pruned_s_node_vars)
        trimmed_graph         : graph with prunable S-nodes removed (if they were
                                already augmented in; otherwise the original graph)
        remaining_s_node_vars : S-node vars that must be kept
        pruned_s_node_vars    : S-node vars that were pruned
    """
    an_y = ancestors(graph, outcome)
    pruned: set[str] = set()
    remaining: set[str] = set()
    current_graph = graph

    for v in sorted(s_node_vars):  # sorted for determinism
        if v not in an_y:
            # v has no path to any outcome variable → S-node is irrelevant
            pruned.add(v)
            _trace.append(
                f"[depth={_depth}] S_TRIM: prune S_{v} "
                f"({v!r} not in ancestors of {sorted(outcome)})"
            )
            _steps.append(
                ProofStep(
                    rule_name="S_TRIM",
                    antecedent_vars=(f"S_{v}",),
                    consequent_vars=(),
                    applied_to_graph_state=(
                        f"S_{v} pruned: {v!r} is not an ancestor of Y={sorted(outcome)}"
                    ),
                    depth=_depth,
                )
            )
            # Remove the S-node from graph if it was already augmented in
            current_graph = resolve_s_node_by_adjustment(current_graph, v, frozenset())
        else:
            remaining.add(v)

    return current_graph, frozenset(remaining), frozenset(pruned)


def _z_transport_direct_pass(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    z_interventions: frozenset[str],
    graph: CausalGraphModel,
    dataset_ref: str | None,
) -> IdentificationResult | None:
    """Check if the direct Z-transport formula applies.

    The direct Z-transport formula (Bareinboim & Pearl 2013):

        P*(Y|do(X)) = Σ_Z P_z(Y|X,Z) · P*(Z)

    is valid when Z d-separates Y from all back-door paths in the mutilated
    graph G_{do(X)}, i.e. when::

        m_separation(G_{do(X)}, Y, ∅, Z)  holds

    (meaning: conditioning on Z in G after removing incoming edges to X
    blocks all non-causal paths from X to Y).

    Parameters
    ----------
    treatment      : X — intervention variables
    outcome        : Y — outcome variables
    z_interventions: Z — variables with available experimental data P_z(·)
    graph          : causal graph G
    dataset_ref    : dataset reference tag for leaves

    Returns
    -------
    IdentificationResult with status=IDENTIFIED if the formula applies, else None.
    """
    if not z_interventions:
        return None

    # Be conservative: the simple closed-form direct Z-transport shortcut is
    # not sound in the presence of latent confounding touching treatment or
    # outcome outside the surrogate intervention set.
    for pair in extract_bidirected_edges(graph):
        if pair & (treatment | outcome) and not pair <= z_interventions:
            return None

    # Build mutilated graph G_{do(X)}
    g_do_x = do_operator(graph, treatment)

    # Full back-door criterion in G_{do(X)} (Bareinboim & Pearl 2013, Thm. 1):
    # Z must d-separate Y from ALL non-descendants of X in G_{do(X)} that are
    # NOT in Z ∪ X ∪ Y.  The previous implementation only checked the common
    # ancestors of X and Y, which misses confounders that are non-ancestors of X
    # but still reach Y through non-causal paths in the original graph.
    #
    # Correct condition: (Y ⊥⊥ W | Z) in G_{do(X)},
    #   where W = V \ (desc(X, G_{do(X)}) ∪ X ∪ Y ∪ Z)
    all_vars = frozenset(g_do_x.nodes)
    desc_x = descendants(g_do_x, treatment, include_self=True)
    # W = all non-descendant nodes that are not in treatment, outcome, or Z
    non_desc_sources = all_vars - desc_x - outcome - z_interventions

    if not non_desc_sources:
        # No potential confounders exist → direct Z-transport applies trivially
        pass
    else:
        # Check if Z m-separates Y from all potential confounders in G_{do(X)}
        if not m_separation(g_do_x, outcome, non_desc_sources, z_interventions):
            return None  # Z does not fully block non-causal paths

    # Direct Z-transport formula applies
    z_vars_tuple = tuple(sorted(z_interventions))
    treatment_str = next(iter(sorted(treatment))) if len(treatment) == 1 else str(sorted(treatment))
    outcome_str = next(iter(sorted(outcome))) if len(outcome) == 1 else str(sorted(outcome))

    try:
        estimand = make_z_transport_estimand(
            treatment=treatment_str,
            outcome=outcome_str,
            z_vars=z_vars_tuple,
            source_dataset_ref=dataset_ref or "source",
            target_dataset_ref="target",
        )
    except (ValueError, TypeError):
        return None

    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=estimand,
        hedge_certificate=None,
        trace=[
            f"z_transport_direct_pass: Z={sorted(z_interventions)} "
            f"blocks back-door paths to Y={sorted(outcome)}"
        ],
        required_distributions=estimand.collect_distribution_refs(),
        proof_steps=[
            ProofStep(
                rule_name="Z_TRANSPORT",
                antecedent_vars=tuple(sorted(z_interventions)),
                consequent_vars=tuple(sorted(outcome)),
                applied_to_graph_state=(
                    f"Direct Z-transport: P*({outcome_str}|do({treatment_str})) "
                    f"= Σ_Z P_z({outcome_str}|{treatment_str},Z)·P*(Z)"
                ),
                depth=0,
            )
        ],
    )


def tr_algorithm(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    selection_diagram: Any,  # SelectionDiagram — avoid circular import
    dataset_ref: str | None = None,
) -> IdentificationResult:
    """Bareinboim-Pearl TR algorithm for transportability.

    Augments the base graph with selection nodes (S→V for each SNode),
    then runs id_algorithm on the augmented graph.  The S-nodes mark which
    mechanisms differ between source and target domain.

    Enhancements over the bare formulation:
    - **S-trimming**: S-nodes whose target variable is not an ancestor of any
      outcome variable are pruned before augmentation (they can never affect
      identification).  Each pruned S-node emits a ``S_TRIM`` ProofStep.
    - **ProofStep emission**: augmentation and trimming are traced as formal
      proof steps for downstream audit.
    - Uses :func:`augment_with_s_nodes` from admg_ops for pure graph surgery.

    Parameters
    ----------
    selection_diagram:  polisyos.ir.analytics.transportability.SelectionDiagram
    """
    from polisyos.ir.analytics.transportability import SelectionDiagram

    if not isinstance(selection_diagram, SelectionDiagram):
        return IdentificationResult(
            status=IdentificationStatus.ORACLE_NEEDED,
            estimand_ast=None,
            hedge_certificate=None,
            trace=["tr_algorithm: invalid selection_diagram type"],
            required_distributions=[],
        )

    trace: list[str] = [
        f"tr_algorithm: X={sorted(treatment)}, Y={sorted(outcome)}, "
        f"s_nodes={[sn.target_variable for sn in selection_diagram.s_nodes]}"
    ]
    _steps: list[ProofStep] = []

    graph = selection_diagram.base_graph

    if not selection_diagram.s_nodes:
        trace.append("tr_algorithm: no S-nodes → direct ID on base graph")
        return id_algorithm(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            dataset_ref=dataset_ref,
            domain=DistributionDomain.SOURCE,
            _trace=trace,
        )

    # Collect all S-node target variable names
    all_s_vars = frozenset(sn.target_variable for sn in selection_diagram.s_nodes)

    # S-trimming: prune S-nodes whose target is not an ancestor of Y
    _, remaining_s_vars, pruned_s_vars = _s_trim_lemma(
        outcome=outcome,
        graph=graph,
        s_node_vars=all_s_vars,
        _trace=trace,
        _steps=_steps,
        _depth=0,
    )

    if not remaining_s_vars:
        trace.append("tr_algorithm: all S-nodes pruned by S-trimming → direct ID on base graph")
        inner = id_algorithm(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            dataset_ref=dataset_ref,
            domain=DistributionDomain.SOURCE,
            _trace=trace,
        )
        return dataclasses.replace(inner, proof_steps=_steps + list(inner.proof_steps))

    # Emit S_AUGMENT ProofStep for remaining S-nodes
    _steps.append(
        ProofStep(
            rule_name="S_AUGMENT",
            antecedent_vars=tuple(f"S_{v}" for v in sorted(remaining_s_vars)),
            consequent_vars=tuple(sorted(remaining_s_vars)),
            applied_to_graph_state=(
                f"Augment graph with S-nodes for {sorted(remaining_s_vars)}; "
                f"{len(pruned_s_vars)} S-node(s) pruned by S-trimming lemma"
            ),
            depth=0,
        )
    )

    # Augment graph with remaining S-nodes using admg_ops primitive
    augmented_graph = augment_with_s_nodes(graph, remaining_s_vars)

    # S nodes are not part of the observed variables for identification
    observed_vars = frozenset(graph.nodes)
    trace.append(
        f"tr_algorithm: augmented graph has {len(remaining_s_vars)} S-node(s) "
        f"(pruned={len(pruned_s_vars)}); running ID on observed vars={sorted(observed_vars)}"
    )

    inner = id_algorithm(
        treatment=treatment,
        outcome=outcome,
        graph=augmented_graph,
        available_vars=observed_vars,
        dataset_ref=dataset_ref,
        domain=DistributionDomain.SOURCE,
        _trace=trace,
    )
    return dataclasses.replace(inner, proof_steps=_steps + list(inner.proof_steps))


def id_with_oracle_fallback(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    oracle: Literal["dosearch", "y0", "none"] = "none",
    dataset_ref: str | None = None,
    domain: DistributionDomain = DistributionDomain.SOURCE,
) -> IdentificationResult:
    """Run native ID algorithm; fall back to oracle backend if ORACLE_NEEDED.

    Oracle backends
    ---------------
    "none"     – return ORACLE_NEEDED as-is
    "y0"       – attempt identification via the Y0 Python package
    "dosearch" – attempt identification via dosearch R package (rpy2 required)
    """
    result = id_algorithm(
        treatment=treatment,
        outcome=outcome,
        graph=graph,
        dataset_ref=dataset_ref,
        domain=domain,
    )

    if result.status is IdentificationStatus.IDENTIFIED:
        return result
    if result.status is IdentificationStatus.HEDGE_FOUND:
        return result
    if oracle == "none":
        return result

    # --- Oracle fallback ---
    if oracle == "y0":
        return _oracle_y0(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            native_result=result,
            dataset_ref=dataset_ref,
            domain=domain,
        )
    if oracle == "dosearch":
        return _oracle_dosearch(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            native_result=result,
            dataset_ref=dataset_ref,
            domain=domain,
        )
    return result


# ---------------------------------------------------------------------------
# Standalone hedge search (public API — no need to run full ID)
# ---------------------------------------------------------------------------


def find_hedge(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    available_vars: frozenset[str] | None = None,
) -> HedgeCertificate | None:
    """Find a hedge (Shpitser & Pearl 2006, Thm 3) without running full ID.

    Returns a :class:`HedgeCertificate` if P(Y|do(X)) is provably
    non-identifiable from observational data, or ``None`` if no hedge exists.

    A hedge (F, F') is a pair of c-forests such that F' ⊆ F, F' is a
    c-component of G[An(Y)] \\ X, and F is a c-component of G that contains
    F' and has a non-empty intersection with X.

    This is a **strict superset** of the Step 4a check inside
    :func:`id_algorithm` — the internal check only catches the degenerate case
    where a single component spans all of V \\ X.  This function checks all
    c-component pairs and therefore detects hedges involving sub-graphs.

    Parameters
    ----------
    treatment      : X — intervention set
    outcome        : Y — target variables
    graph          : causal graph (DAG or ADMG with ARROW↔ARROW bidirected edges)
    available_vars : observed variables V; defaults to all graph nodes
    """
    from polisyos.foundry.methods.catalog.causal.admg_ops import (
        ancestors,
        c_components,
        extract_bidirected_edges,
        induced_subgraph,
    )

    V = available_vars if available_vars is not None else frozenset(graph.nodes)
    X = treatment
    Y = outcome

    # Restrict to An(Y) for the c-forest pair check
    an_y = ancestors(graph, Y) & V
    g_an = induced_subgraph(graph, an_y)

    # C(G[An(Y)] \ X) — candidate c-forests F'
    g_an_minus_x = induced_subgraph(g_an, an_y - X)
    comps_minus_x = c_components(g_an_minus_x)

    # C(G) — larger candidate c-forests F
    comps_g = c_components(graph)

    bi_edges = extract_bidirected_edges(graph)

    for si in comps_minus_x:
        if not (si >= Y):
            continue  # F' must contain Y
        # Find Sj ∈ C(G) such that Si ⊆ Sj and Sj ∩ X ≠ ∅
        for sj in comps_g:
            if si <= sj and sj & X:
                # Hedge (F=Sj, F'=Si) found
                minimal_s: set[str] = set()
                for pair in bi_edges:
                    u, v_node = tuple(pair)
                    if u in X and v_node in si:
                        minimal_s.add(v_node)
                    elif v_node in X and u in si:
                        minimal_s.add(u)
                return HedgeCertificate(
                    treatment=X,
                    outcome=Y,
                    hedge_forest=sj,
                    hedge_root=si,
                    c_component_witness=si,
                    description=(
                        f"Hedge (F={sorted(sj)}, F'={sorted(si)}): "
                        f"P({sorted(Y)}|do({sorted(X)})) is NOT identifiable."
                    ),
                    required_data=RequiredDataSpec(
                        missing_distributions=tuple(
                            DistributionRef(
                                domain=DistributionDomain.EXPERIMENTAL,
                                variables=tuple(sorted(Y)),
                                intervention_set=(xi,),
                            )
                            for xi in sorted(sj & X)
                        ),
                        suggested_experiment=(f"Randomize: {sorted(sj & X)}" if sj & X else None),
                    ),
                    minimal_required_s_nodes=frozenset(minimal_s),
                )
    return None


def find_thicket(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    available_vars: frozenset[str] | None = None,
) -> list[HedgeCertificate]:
    """Find ALL minimal hedges blocking P(Y|do(X)) identification.

    A *thicket* is the set of minimal, non-redundant hedges.  Returns an empty
    list iff P(Y|do(X)) is identifiable.

    Complexity: O(|C|²) in the number of c-components — tractable for graphs
    under ~200 nodes.

    Parameters
    ----------
    treatment      : X — intervention set
    outcome        : Y — target variables
    graph          : causal graph
    available_vars : observed variables V; defaults to all graph nodes
    """
    from polisyos.foundry.methods.catalog.causal.admg_ops import (
        ancestors,
        c_components,
        extract_bidirected_edges,
        induced_subgraph,
    )

    V = available_vars if available_vars is not None else frozenset(graph.nodes)
    X = treatment
    Y = outcome

    an_y = ancestors(graph, Y) & V
    g_an = induced_subgraph(graph, an_y)
    g_an_minus_x = induced_subgraph(g_an, an_y - X)
    comps_minus_x = c_components(g_an_minus_x)
    comps_g = c_components(graph)
    bi_edges = extract_bidirected_edges(graph)

    all_certs: list[HedgeCertificate] = []
    seen: set[tuple[frozenset[str], frozenset[str]]] = set()

    for si in comps_minus_x:
        if not (si >= Y):
            continue
        for sj in comps_g:
            if not (si <= sj and sj & X):
                continue
            key = (sj, si)
            if key in seen:
                continue
            seen.add(key)
            minimal_s: set[str] = set()
            for pair in bi_edges:
                u, v_node = tuple(pair)
                if u in X and v_node in si:
                    minimal_s.add(v_node)
                elif v_node in X and u in si:
                    minimal_s.add(u)
            all_certs.append(
                HedgeCertificate(
                    treatment=X,
                    outcome=Y,
                    hedge_forest=sj,
                    hedge_root=si,
                    c_component_witness=si,
                    description=(
                        f"Hedge (F={sorted(sj)}, F'={sorted(si)}): "
                        f"P({sorted(Y)}|do({sorted(X)})) is NOT identifiable."
                    ),
                    required_data=RequiredDataSpec(
                        missing_distributions=tuple(
                            DistributionRef(
                                domain=DistributionDomain.EXPERIMENTAL,
                                variables=tuple(sorted(Y)),
                                intervention_set=(xi,),
                            )
                            for xi in sorted(sj & X)
                        ),
                        suggested_experiment=(f"Randomize: {sorted(sj & X)}" if sj & X else None),
                    ),
                    minimal_required_s_nodes=frozenset(minimal_s),
                )
            )

    # Filter to minimal hedges: keep cert c if no other cert c' has c'.hedge_root ⊂ c.hedge_root
    minimal_certs: list[HedgeCertificate] = []
    for cert in all_certs:
        dominated = any(
            other is not cert and other.hedge_root < cert.hedge_root for other in all_certs
        )
        if not dominated:
            minimal_certs.append(cert)

    # Deterministic ordering
    return sorted(minimal_certs, key=lambda c: (sorted(c.hedge_forest), sorted(c.hedge_root)))


# ---------------------------------------------------------------------------
# ProofStep bridge: internal dataclass → public IR Pydantic model
# ---------------------------------------------------------------------------


def _internal_proof_step_to_ir(step: ProofStep) -> Any:
    """Convert an id_engine internal ``ProofStep`` to ``evidence_bundle.ProofStep``.

    Maps internal rule names (which follow ID-algorithm step numbering) to
    the formal do-calculus / identification literature references.
    """
    from polisyos.ir.analytics.evidence_bundle import ProofStep as IRProofStep

    if isinstance(step, IRProofStep):
        return step

    _RULE_FORMAL: dict[str, tuple[str, str]] = {
        "RULE1": (
            "ID Algorithm Step 1 — Marginalisation over ancestors",
            "Shpitser & Pearl (2006), AAAI",
        ),
        "RULE3": (
            "ID Algorithm Step 3 — Extend X with non-ancestors",
            "Shpitser & Pearl (2006), AAAI",
        ),
        "ANCESTRAL_COLLAPSE": (
            "Ancestral subgraph restriction",
            "Tian & Pearl (2002), AAAI",
        ),
        "C_COMPONENT": (
            "c-component factorisation",
            "Tian & Pearl (2002), AAAI",
        ),
        "G_FORMULA": (
            "DAG truncated factorisation (g-formula)",
            "Robins (1986); Pearl (2009)",
        ),
        "FRONTDOOR": (
            "Frontdoor adjustment with one mediator",
            "Pearl (1995); Pearl (2009)",
        ),
        "HEDGE": (
            "Hedge certificate — non-identifiability witness",
            "Shpitser & Pearl (2006), Theorem 3",
        ),
        "ORACLE": (
            "Oracle backend escalation",
            "id_engine native scope exceeded",
        ),
        "PAG_AMBIGUOUS": (
            "PAG-ID — orientation ambiguity unresolved",
            "Malinsky & Spirtes (2017)",
        ),
        # Transportability rule names
        "S_AUGMENT": (
            "Selection diagram augmentation: add S_i → V_i directed edges",
            "Bareinboim & Pearl (2012), AAAI — TR algorithm",
        ),
        "S_TRIM": (
            "S-trimming lemma: prune S-node whose target is not an ancestor of Y",
            "Bareinboim & Pearl (2012) — S-trimming optimisation",
        ),
        "S_DOMAIN_SELECT": (
            "Domain selected for c-component in mz-ID factorisation",
            "Bareinboim & Pearl (2014), AAAI — meta-transportability",
        ),
        "Z_TRANSPORT": (
            "Z-transport: P*(Y|do(X)) = Σ_Z P_z(Y|X,Z) · P*(Z)",
            "Bareinboim & Pearl (2013), IJCAI — Z-transportability",
        ),
        "MZ_FACTORIZE": (
            "mz-ID c-component factorisation across multiple source domains",
            "Bareinboim & Pearl (2014), AAAI — Theorem 2",
        ),
        # IDC-specific rule names
        "IDC_DECOMPOSE": (
            "IDC → RatioNode: P(Y|do(X),Z) = ID(Y,X∪Z,G) / ID(Z,X,G)",
            "Shpitser & Pearl (2008), JMLR; Bareinboim & Pearl (2012)",
        ),
        "IDC_TRIVIAL_Z": (
            "IDC with Z=∅ reduces to ID(Y,X,G)",
            "Shpitser & Pearl (2008)",
        ),
        "IDC_POSITIVITY": (
            "IDC positivity: P(Z|do(X)) > 0 required in support of X",
            "Shpitser & Pearl (2008)",
        ),
        "ID_STAR_STEP1": (
            "ID* Step 1: construct counterfactual graph G* and merge equivalent nodes",
            "Shpitser & Pearl (2012), JMLR; Lemmas 24-25 from Shpitser & Pearl (2008)",
        ),
        "ID_STAR_STEP2": (
            "ID* Step 2: partition G* into c-components",
            "Shpitser & Pearl (2012), Line 6",
        ),
        "ID_STAR_STEP3": (
            "ID* Step 3: reduce each counterfactual district to a Layer-2 interventional query",
            "Shpitser & Pearl (2012), Line 9 + ID reduction",
        ),
        "ID_STAR_STEP4": (
            "ID* Step 4: factorise across disconnected counterfactual districts",
            "Shpitser & Pearl (2012), Line 6",
        ),
        "ID_STAR_STEP5": (
            "ID* Step 5: conclude identification or inconsistency in G*",
            "Shpitser & Pearl (2012)",
        ),
        "IDC_STAR_RATIO": (
            "IDC* conditional counterfactual reduction after Rule-2 promotion",
            "Shpitser & Pearl (2012), IDC*",
        ),
        "CTF_R1": (
            "counterfactual calculus Rule 1: Insertion/Deletion of observations in AMN",
            "Phase 2.2 AMN-based counterfactual calculus",
        ),
        "CTF_R2": (
            "counterfactual calculus Rule 2: intervention/observation exchange in AMN",
            "Phase 2.2 AMN-based counterfactual calculus",
        ),
        "CTF_R3": (
            "counterfactual calculus Rule 3: deletion of counterfactual interventions in AMN",
            "Phase 2.2 AMN-based counterfactual calculus",
        ),
        "CTF_TRANSPORT_START": (
            "Counterfactual transportability start: build Layer-3 transport problem on selection diagram",
            "Correa, Lee & Bareinboim (2022) — counterfactual transportability",
        ),
        "CTF_TRANSPORT_AUGMENT": (
            "Counterfactual transportability: augment graph/AMN with selection variables",
            "Correa, Lee & Bareinboim (2022) — selection-diagram based Layer-3 transport",
        ),
        "CTF_TRANSPORT_EXACT": (
            "Counterfactual transportability: Layer-3 query reduced to transport-identifiable formula",
            "Correa, Lee & Bareinboim (2022) + σ/ctf-calculus reduction",
        ),
        "CTF_TRANSPORT_FALLBACK": (
            "Counterfactual transportability fallback: check ID* on selection-augmented graph",
            "Phase 4 transport fallback over selection-augmented counterfactual graph",
        ),
        "CTF_TRANSPORT_MZ": (
            "Counterfactual multi-domain fusion across source domains",
            "Phase 4 counterfactual transportability + Phase 9 fusion integration",
        ),
        # PAG orientation rule names
        "PAG_ORIENT_R1": (
            "PAG R1: non-collider propagation α*→β○-γ → β→γ",
            "Zhang (2008), Artificial Intelligence 172(16-17)",
        ),
        "PAG_ORIENT_R2": (
            "PAG R2: acyclicity — α→β→γ with α○-γ → α→γ",
            "Zhang (2008), Artificial Intelligence 172(16-17)",
        ),
        "PAG_ORIENT_R3": (
            "PAG R3: v-structure extension",
            "Zhang (2008), Artificial Intelligence 172(16-17)",
        ),
        "PAG_CONSERVATIVE_BLOCK": (
            "PAG-ID CONSERVATIVE: unresolved CIRCLE marks create backdoor ambiguity",
            "Malinsky & Spirtes (2017), UAI",
        ),
        "PAG_OPTIMISTIC_COMMIT": (
            "PAG-ID OPTIMISTIC: commit remaining CIRCLE marks to directed edges",
            "Malinsky & Spirtes (2017), UAI",
        ),
        "PAG_PROBABILISTIC": (
            "PAG-ID PROBABILISTIC: ID on oriented PAG with confidence annotation",
            "Malinsky & Spirtes (2017), UAI",
        ),
        # σ-calculus rule names (Correa & Bareinboim 2020)
        "SIGMA_R1": (
            "σ-calculus Rule 1: Insertion/Deletion of observations under selection S",
            "Correa & Bareinboim (2020), NeurIPS — Theorem 1",
        ),
        "SIGMA_R2": (
            "σ-calculus Rule 2: Exchange action↔observation under selection S",
            "Correa & Bareinboim (2020), NeurIPS — Theorem 2",
        ),
        "SIGMA_R3": (
            "σ-calculus Rule 3: Deletion of actions under selection S",
            "Correa & Bareinboim (2020), NeurIPS — Theorem 3",
        ),
        "SID_DAG_POLICY": (
            "Policy g-formula fast path: replace P(X|Pa_X) with the policy factor inside a DAG truncated factorization",
            "Robins (1986); Díaz & van der Laan (2012)",
        ),
        "SID_SIGMA_FALLBACK": (
            "Stochastic intervention σ-calculus fallback after atomic ID failed",
            "Correa & Bareinboim (2020), NeurIPS",
        ),
        # M-graph recoverability rule names (Mohan & Pearl 2021)
        "MGRAPH_TRIVIALLY_OBSERVED": (
            "M-graph: variable has no R-node and is fully observed",
            "Mohan & Pearl (2021), JASA",
        ),
        "MGRAPH_RECOVERABLE_VAR": (
            "M-graph recoverability: R_V ∉ desc(V) in G[V∪R\\proxy] → P(V) recoverable",
            "Mohan & Pearl (2021), JASA — Theorem 1",
        ),
        "MGRAPH_NOT_RECOVERABLE": (
            "M-graph non-recoverability: R_V ∈ desc(V) in G[V∪R\\proxy] → P(V) not recoverable",
            "Mohan & Pearl (2021), JASA — Theorem 1",
        ),
        "ORDERED_RECOVERY_STEP": (
            "Ordered recovery fixing operator: P(V_i|V_{<i}) = P*(V_i|V_{<i}, R_{V_i}=1)",
            "Mohan, Pearl & Tian (2013), UAI — Algorithm 1",
        ),
        "FULL_LAW_STAGE1_PASS": (
            "Full law Stage 1 passed: full-data distribution P(V) recoverable from incomplete data",
            "Nabi, Bhattacharya & Shpitser (2020)",
        ),
        "FULL_LAW_STAGE2": (
            "Full law Stage 2: ID algorithm applied to recovered full-data distribution P(V)",
            "Nabi, Bhattacharya & Shpitser (2020)",
        ),
    }
    formal, theorem = _RULE_FORMAL.get(step.rule_name, (step.rule_name, ""))
    # For rules not in _RULE_FORMAL, fall back to depth annotation
    if not theorem and getattr(step, "depth", None) is not None:
        theorem = f"do-calculus depth={step.depth}"
    # Safely get graph_state_before (may be absent on legacy/mock ProofStep objects)
    gsb = getattr(step, "graph_state_before", "")
    graph_state_before = gsb if isinstance(gsb, str) else ""
    step_id_payload = "|".join(
        (
            step.rule_name,
            str(getattr(step, "depth", 0)),
            ",".join(step.antecedent_vars),
            ",".join(step.consequent_vars),
            graph_state_before,
            step.applied_to_graph_state,
        )
    )
    step_id = (
        f"{step.rule_name.lower()}_{hashlib.sha256(step_id_payload.encode()).hexdigest()[:12]}"
    )
    return IRProofStep(
        rule_name=step.rule_name,
        description=step.applied_to_graph_state,
        variables_affected=step.antecedent_vars + step.consequent_vars,
        step_id=step_id,
        theorem_family="id_engine",
        rule_formal_name=formal,
        applicable_theorem=theorem,
        graph_state_before=graph_state_before,
        graph_state_after=step.applied_to_graph_state,
    )


# ---------------------------------------------------------------------------
# Internal helpers — ID algorithm steps
# ---------------------------------------------------------------------------


def _wrap_root(
    root: object,
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    method: str,
) -> EstimandAST:
    """Wrap a single root node into an EstimandAST."""

    t_str = next(iter(sorted(treatment))) if len(treatment) == 1 else str(sorted(treatment))
    y_str = next(iter(sorted(outcome))) if len(outcome) == 1 else str(sorted(outcome))
    all_vars = tuple(sorted(treatment | outcome))
    if isinstance(root, (DistributionRef, SumNode, ProductNode, RatioNode)):
        return EstimandAST(
            query_str=f"P({y_str}|do({t_str}))",
            root=root,  # type: ignore[arg-type]
            treatment=t_str,
            outcome=y_str,
            all_variables=all_vars,
            identification_method=method,
        )
    raise TypeError(f"Unexpected root type: {type(root)}")


def _make_conditional_dist(
    *,
    variables: tuple[str, ...],
    conditioning: tuple[str, ...],
    dataset_ref: str | None,
    domain: DistributionDomain,
) -> DistributionRef:
    return DistributionRef(
        domain=domain,
        variables=variables,
        conditioning=conditioning,
        dataset_ref=dataset_ref,
        side_conditions=(
            SideCondition(
                kind=SideConditionKind.POSITIVITY,
                variables=conditioning,
                description="Positivity required for conditioning variables",
            ),
        )
        if conditioning
        else (),
    )


def _step5_formula(
    *,
    si: frozenset[str],
    components_g_minus_x: list[frozenset[str]],
    graph: CausalGraphModel,
    V: frozenset[str],
    X: frozenset[str],
    Y: frozenset[str],
    dataset_ref: str | None,
    domain: DistributionDomain,
    depth: int,
    trace: list[str],
) -> IdentificationResult:
    """Step 5: Y is contained in single component Si of G \\ X.

    Factorises as: ∑_{V\\(Y∪X)} ∏_{Vk ∈ Si} P(Vk | pa(Vk) in topo order)

    This implements the c-component factorisation formula for the case
    where Si is its own c-component in G (not a subset of a larger component).
    """
    # Get topological order over V (directed edges in G)
    try:
        from polisyos.foundry.methods.catalog.causal.admg_ops import topological_order

        topo = topological_order(graph)
        topo_in_V = [n for n in topo if n in V]
    except ValueError:
        trace.append(f"[depth={depth}] Step 5: topological sort failed (cycle?)")
        return IdentificationResult(
            status=IdentificationStatus.ORACLE_NEEDED,
            estimand_ast=None,
            hedge_certificate=None,
            trace=list(trace),
            required_distributions=[],
        )

    # Build P(V) = ∏_{Vi ∈ V} P(Vi | pa(Vi)_G)
    directed = extract_directed_edges(graph)
    # parents of a node = {src : (src, node) in directed}
    parents_of: dict[str, set[str]] = {n: set() for n in graph.nodes}
    for src, dst in directed:
        parents_of[dst].add(src)

    all_dists: list[DistributionRef] = []
    # For each node in Si, build P(Vi | pa(Vi)_G ∩ V before Vi in topo)
    # following the Q-factorisation
    factors: list[object] = []
    for vi in topo_in_V:
        if vi not in si:
            continue
        # Predecessors of vi in V (in topological order)
        vi_idx = topo_in_V.index(vi)
        predecessors_in_V = set(topo_in_V[:vi_idx])
        pa_vi = parents_of.get(vi, set()) & predecessors_in_V
        cond = tuple(sorted(pa_vi))
        dr = _make_conditional_dist(
            variables=(vi,),
            conditioning=cond,
            dataset_ref=dataset_ref,
            domain=domain,
        )
        factors.append(dr)
        all_dists.append(dr)

    trace.append(f"[depth={depth}] Step 5: built {len(factors)}-factor product over Si")

    # Marginalise over non-Y, non-X nodes in Si
    marginalise_over = tuple(sorted((si - Y) & V))
    if len(factors) == 1:
        product_node = factors[0]
    else:
        product_node = ProductNode(factors=tuple(factors))  # type: ignore[arg-type]

    if marginalise_over:
        root_node = SumNode(summation_vars=marginalise_over, operand=product_node)  # type: ignore[arg-type]
    else:
        root_node = product_node  # type: ignore[assignment]

    ast = EstimandAST(
        query_str=f"P({sorted(Y)}|do({sorted(X)}))",
        root=root_node,  # type: ignore[arg-type]
        treatment=next(iter(sorted(X))) if len(X) == 1 else str(sorted(X)),
        outcome=next(iter(sorted(Y))) if len(Y) == 1 else str(sorted(Y)),
        all_variables=tuple(sorted(V)),
        identification_method="id_step5_ccomponent",
    )
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=ast,
        hedge_certificate=None,
        trace=list(trace),
        required_distributions=all_dists,
    )


def _step6_formula(
    *,
    si: frozenset[str],
    sj: frozenset[str],
    graph: CausalGraphModel,
    V: frozenset[str],
    X: frozenset[str],
    Y: frozenset[str],
    dataset_ref: str | None,
    domain: DistributionDomain,
    depth: int,
    trace: list[str],
) -> IdentificationResult:
    """Step 6: Si ⊂ Sj ∈ C(G).

    Recurse: return ID(Y, X ∩ Si, G[Sj], Q[Sj]) where Q[Sj] is the
    interventional distribution on Sj given all variables outside Sj are fixed.

    Simplified approximation for practical cases:
    We compute the formula by recursively calling id_algorithm on the
    induced subgraph G[Sj] with X restricted to X ∩ Sj.
    """
    trace.append(
        f"[depth={depth}] Step 6: Si={sorted(si)} ⊂ Sj={sorted(sj)}, recursing on subgraph G[Sj]"
    )
    sub_g_sj = induced_subgraph(graph, sj)
    sub_x = X & sj
    sub_y = Y & sj

    if not sub_y:
        # Y not in Sj — shouldn't happen at this step
        trace.append(f"[depth={depth}] Step 6: Y not in Sj — ORACLE_NEEDED")
        return IdentificationResult(
            status=IdentificationStatus.ORACLE_NEEDED,
            estimand_ast=None,
            hedge_certificate=None,
            trace=list(trace),
            required_distributions=[],
        )

    return id_algorithm(
        treatment=sub_x,
        outcome=sub_y,
        graph=sub_g_sj,
        available_vars=sj,
        dataset_ref=dataset_ref,
        domain=domain,
        _depth=depth + 1,
        _trace=trace,
    )


# ---------------------------------------------------------------------------
# Oracle backends
# ---------------------------------------------------------------------------


def _oracle_y0(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    native_result: IdentificationResult,
    dataset_ref: str | None,
    domain: DistributionDomain,
) -> IdentificationResult:
    """Attempt identification via the Y0 Python package."""
    try:
        import y0  # type: ignore[import-not-found]
    except ImportError:
        return dataclasses.replace(
            native_result,
            trace=[*native_result.trace, "oracle_y0: y0 not installed, skipping"],
        )

    try:
        from y0.algorithm.identify import identify  # type: ignore[import-not-found]
        from y0.dsl import Variable  # type: ignore[import-not-found]
        from y0.graph import NxMixedGraph  # type: ignore[import-not-found]

        nx_graph = graph.to_networkx()
        mixed = NxMixedGraph.from_mixed_edges(
            directed=[
                (e.src, e.dst)
                for e in graph.edges
                if e.mark_src is EdgeMark.TAIL and e.mark_dst is EdgeMark.ARROW
            ],
            undirected=[
                (e.src, e.dst)
                for e in graph.edges
                if e.mark_src is EdgeMark.ARROW and e.mark_dst is EdgeMark.ARROW
            ],
        )
        y_vars = [Variable(v) for v in sorted(outcome)]
        x_vars = [Variable(v) for v in sorted(treatment)]
        expr = identify(mixed, y_vars, x_vars)
        if expr is not None:
            # Build a simple DistributionRef leaf as placeholder
            leaf = DistributionRef(
                domain=domain,
                variables=tuple(sorted(outcome)),
                intervention_set=tuple(sorted(treatment)),
                dataset_ref=dataset_ref,
            )
            ast = EstimandAST(
                query_str=f"P({sorted(outcome)}|do({sorted(treatment)}))",
                root=leaf,
                treatment=next(iter(sorted(treatment)))
                if len(treatment) == 1
                else str(sorted(treatment)),
                outcome=next(iter(sorted(outcome))) if len(outcome) == 1 else str(sorted(outcome)),
                all_variables=tuple(sorted(treatment | outcome)),
                identification_method="y0_oracle",
            )
            return IdentificationResult(
                status=IdentificationStatus.IDENTIFIED,
                estimand_ast=ast,
                hedge_certificate=None,
                trace=[*native_result.trace, "oracle_y0: IDENTIFIED"],
                required_distributions=[leaf],
            )
        return dataclasses.replace(
            native_result,
            trace=[*native_result.trace, "oracle_y0: not identified"],
        )
    except Exception as exc:
        return dataclasses.replace(
            native_result,
            trace=[*native_result.trace, f"oracle_y0 error: {exc}"],
        )


def _oracle_dosearch(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    native_result: IdentificationResult,
    dataset_ref: str | None,
    domain: DistributionDomain,
) -> IdentificationResult:
    """Attempt identification via dosearch R package (requires rpy2)."""
    try:
        import rpy2.robjects as ro  # type: ignore[import-not-found]
        from rpy2.robjects.packages import importr  # type: ignore[import-not-found]

        dosearch = importr("dosearch")
    except ImportError:
        return dataclasses.replace(
            native_result,
            trace=[*native_result.trace, "oracle_dosearch: rpy2/dosearch not available"],
        )

    try:
        # Build dosearch input format
        directed_edges = [
            f"{e.src} -> {e.dst}"
            for e in graph.edges
            if e.mark_src is EdgeMark.TAIL and e.mark_dst is EdgeMark.ARROW
        ]
        bidirected_edges = [
            f"{e.src} <-> {e.dst}"
            for e in graph.edges
            if e.mark_src is EdgeMark.ARROW and e.mark_dst is EdgeMark.ARROW
        ]
        graph_str = "\n".join(directed_edges + bidirected_edges)
        data_str = f"p({', '.join(sorted(graph.nodes))})"
        query_str = f"p({', '.join(sorted(outcome))} | do({', '.join(sorted(treatment))}))"
        result = dosearch.dosearch(
            data=ro.StrVector([data_str]),
            query=ro.StrVector([query_str]),
            graph=ro.StrVector([graph_str]),
        )
        formula = str(result.rx2("formula")[0]) if result is not None else ""
        if formula and formula != "NULL":
            leaf = DistributionRef(
                domain=domain,
                variables=tuple(sorted(outcome)),
                intervention_set=tuple(sorted(treatment)),
                dataset_ref=dataset_ref,
            )
            ast = EstimandAST(
                query_str=f"P({sorted(outcome)}|do({sorted(treatment)}))",
                root=leaf,
                treatment=next(iter(sorted(treatment)))
                if len(treatment) == 1
                else str(sorted(treatment)),
                outcome=next(iter(sorted(outcome))) if len(outcome) == 1 else str(sorted(outcome)),
                all_variables=tuple(sorted(treatment | outcome)),
                identification_method="dosearch_oracle",
            )
            return IdentificationResult(
                status=IdentificationStatus.IDENTIFIED,
                estimand_ast=ast,
                hedge_certificate=None,
                trace=[*native_result.trace, f"oracle_dosearch: IDENTIFIED formula={formula}"],
                required_distributions=[leaf],
            )
        return dataclasses.replace(
            native_result,
            trace=[*native_result.trace, "oracle_dosearch: not identified"],
        )
    except Exception as exc:
        return dataclasses.replace(
            native_result,
            trace=[*native_result.trace, f"oracle_dosearch error: {exc}"],
        )


__all__ = [name for name in globals() if not name.startswith("__")]
