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
from enum import Enum
from typing import Any, Literal

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
    CounterfactualNode,
    ConditionalInterventionNode,
    CrossWorldNode,
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    ModifiedTreatmentPolicyNode,
    NestedCounterfactualNode,
    ProductNode,
    ProxyAdjustmentNode,
    RatioNode,
    SideCondition,
    SideConditionKind,
    StochasticInterventionNode,
    StochasticPolicy,
    SumNode,
    make_z_transport_estimand,
    make_frontdoor_estimand,
)


# ---------------------------------------------------------------------------
# Internal result types (dataclasses, not Pydantic)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ProofStep:
    """A single deductive step in the ID algorithm proof trace."""

    rule_name: str  # "RULE1"|"RULE2"|"RULE3"|"ANCESTRAL_COLLAPSE"|"C_COMPONENT"|"HEDGE"|"ORACLE"
    antecedent_vars: tuple[str, ...]
    consequent_vars: tuple[str, ...]
    applied_to_graph_state: str
    depth: int = 0
    graph_state_before: str = ""  # pre-step graph description for audit trail


@dataclasses.dataclass(frozen=True)
class RequiredDataSpec:
    """Specification of data needed to achieve identification."""

    missing_distributions: tuple[Any, ...]   # tuple of DistributionRef objects
    suggested_experiment: str | None = None
    alternative_identification: str | None = None


@dataclasses.dataclass(frozen=True)
class HedgeCertificate:
    """Mathematical witness of non-identifiability (Shpitser & Pearl 2006, Thm 3).

    A "hedge" (F, F') is a pair of c-forests such that:
    - F' ⊆ F
    - F' is a c-component of G[An(Y)]
    - F is a c-component of G[V \\ X] that contains F'
    - Every root of F' is also a root of F and in X

    When the ID algorithm detects this structure, the interventional distribution
    P(Y|do(X)) is provably non-identifiable from observational data.
    """

    treatment: frozenset[str]
    outcome: frozenset[str]
    hedge_forest: frozenset[str]        # F  — larger component
    hedge_root: frozenset[str]          # F' — smaller component (⊆ F)
    c_component_witness: frozenset[str] # the c-component triggering non-ID
    description: str = ""
    required_data: "RequiredDataSpec | None" = None
    minimal_required_s_nodes: frozenset[str] = dataclasses.field(default_factory=frozenset)
    # ^ minimum set of S-nodes (selection variables) that, if resolved,
    #   would make transport potentially identifiable via tr_algorithm.
    #   Computed as endpoints in V\X of bidirected edges crossing the X boundary
    #   inside the c_component_witness.


class IdentificationStatus(str, Enum):
    """Classify whether a causal query is identified, blocked, ambiguous, or oracle-gated."""
    IDENTIFIED = "identified"
    HEDGE_FOUND = "hedge_found"       # non-identifiable, certificate returned
    PAG_AMBIGUOUS = "pag_ambiguous"   # PAG input, result depends on orientation
    ORACLE_NEEDED = "oracle_needed"       # beyond native impl scope
    NOT_RECOVERABLE = "not_recoverable"  # M-graph Stage 1 failure: P(V) not recoverable


@dataclasses.dataclass(frozen=True)
class IdentificationResult:
    """Result of running id_algorithm() or idc_algorithm()."""

    status: IdentificationStatus
    estimand_ast: EstimandAST | None
    hedge_certificate: HedgeCertificate | None
    trace: list[str]
    required_distributions: list[DistributionRef]
    algorithm_version: str = "id_v1"
    proof_steps: list["ProofStep"] = dataclasses.field(default_factory=list)
    query_str: str = ""
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class CtfQuery:
    """Counterfactual query container for Layer-3 ID* / IDC* requests."""

    outcome: str
    intervention: tuple[tuple[str, float], ...]
    conditioning: tuple[str, ...] = ()
    evidence: tuple[tuple[str, float], ...] = ()
    kind: str = "generic"
    mediators: tuple[str, ...] = ()
    protected_attribute: str | None = None
    reference_intervention: tuple[tuple[str, float], ...] = ()
    outcome_value: float | None = None


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
    _pag_steps: list["ProofStep"] | None = None,
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
        1 for e in graph.edges
        if e.mark_src is EdgeMark.CIRCLE or e.mark_dst is EdgeMark.CIRCLE
    )
    oriented_pag, _orient_warnings = apply_pag_orientation_rules(graph)
    n_circles_after = sum(
        1 for e in oriented_pag.edges
        if e.mark_src is EdgeMark.CIRCLE or e.mark_dst is EdgeMark.CIRCLE
    )
    n_resolved = n_circles_before - n_circles_after

    if n_resolved > 0:
        _trace.append(
            f"[depth={_depth}] PAG-ID orientation pre-pass: "
            f"resolved {n_resolved} CIRCLE marks ({n_circles_before}→{n_circles_after})"
        )
        pag_steps.append(ProofStep(
            rule_name="PAG_ORIENT_R1",
            antecedent_vars=(),
            consequent_vars=(),
            applied_to_graph_state=(
                f"R1-R3 orientation pass resolved {n_resolved} CIRCLE marks "
                f"({n_circles_before}→{n_circles_after} circles remain)"
            ),
            graph_state_before=f"{n_circles_before} CIRCLE marks before orientation",
            depth=_depth,
        ))

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

        pag_steps.append(ProofStep(
            rule_name="PAG_OPTIMISTIC_COMMIT",
            antecedent_vars=(),
            consequent_vars=tuple(sorted(outcome)),
            applied_to_graph_state=(
                f"OPTIMISTIC policy: committing {n_committed} remaining CIRCLE marks "
                f"to directed edges after R1-R3 pre-pass"
            ),
            graph_state_before=f"oriented PAG with {n_circles_after} remaining circles",
            depth=_depth,
        ))

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
        _trace.append(
            f"[depth={_depth}] PAG-ID OPTIMISTIC: status={result.status.value}"
        )
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
        pag_steps.append(ProofStep(
            rule_name="PAG_CONSERVATIVE_BLOCK",
            antecedent_vars=tuple(sorted(treatment)),
            consequent_vars=tuple(sorted(outcome)),
            applied_to_graph_state=(
                f"CONSERVATIVE policy: {n_circles_after} unresolved CIRCLE marks create "
                f"backdoor ambiguity; pag_reachable∩X={sorted(pag_reachable & treatment)}"
            ),
            graph_state_before=f"oriented PAG with {n_circles_after} remaining circles",
            depth=_depth,
        ))
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
        pag_steps.append(ProofStep(
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
        ))

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
    _trace.append(
        f"[depth={_depth}] PAG-ID ({policy.value}): base status={result.status.value}"
    )
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
    _steps: list["ProofStep"],
    _trace: list[str],
) -> "HedgeCertificate | None":
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
            f"Randomize treatment for: {sorted(hedge_root & X)}"
            if hedge_root & X else None
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
    _steps.append(ProofStep(
        rule_name="HEDGE",
        antecedent_vars=tuple(sorted(X)),
        consequent_vars=tuple(sorted(Y)),
        applied_to_graph_state=f"C(G)=single component, hedge forest={sorted(V)}",
        depth=_depth,
    ))
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
        _steps.append(ProofStep(
            rule_name="RULE1",
            antecedent_vars=(),
            consequent_vars=tuple(sorted(Y)),
            applied_to_graph_state=f"X=∅, marginalise over An({sorted(Y)})",
            depth=_depth,
        ))
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
        _steps.append(ProofStep(
            rule_name="ANCESTRAL_COLLAPSE",
            antecedent_vars=tuple(sorted(V)),
            consequent_vars=tuple(sorted(an_y_full)),
            applied_to_graph_state=f"restrict to An({sorted(Y)})",
            depth=_depth,
        ))
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
        _steps.append(ProofStep(
            rule_name="RULE3",
            antecedent_vars=tuple(sorted(W)),
            consequent_vars=tuple(sorted(new_x)),
            applied_to_graph_state=f"extend X with non-ancestor W={sorted(W)}",
            depth=_depth,
        ))
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
        _trace.append(
            f"[depth={_depth}] Frontdoor shortcut: mediator={frontdoor_mediator}"
        )
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
    _trace.append(
        f"[depth={_depth}] Step 4: C(G\\X)={[sorted(c) for c in components_g_minus_x]}"
    )

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
        if Y <= comp:
            y_component = comp
            break

    if y_component is not None:
        _trace.append(f"[depth={_depth}] Step 5: Y ⊆ Si={sorted(y_component)}")
        _steps.append(ProofStep(
            rule_name="C_COMPONENT",
            antecedent_vars=tuple(sorted(y_component)),
            consequent_vars=tuple(sorted(Y)),
            applied_to_graph_state=f"Y in c-component Si={sorted(y_component)} of G\\X",
            depth=_depth,
        ))
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
    _steps.append(ProofStep(
        rule_name="ORACLE",
        antecedent_vars=tuple(sorted(X)),
        consequent_vars=tuple(sorted(Y)),
        applied_to_graph_state="no ID rule applies",
        depth=_depth,
    ))
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
        idc_steps.append(ProofStep(
            rule_name="IDC_TRIVIAL_Z",
            antecedent_vars=(),
            consequent_vars=tuple(sorted(outcome)),
            applied_to_graph_state="IDC with Z=∅: reduces trivially to ID(Y, X, G)",
            graph_state_before="Z=∅ — no conditioning variables",
            depth=0,
        ))
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
    idc_steps.append(ProofStep(
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
    ))

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
    idc_steps.append(ProofStep(
        rule_name="IDC_POSITIVITY",
        antecedent_vars=tuple(sorted(conditions)),
        consequent_vars=tuple(sorted(conditions)),
        applied_to_graph_state=(
            f"IDC positivity required: P({sorted(conditions)}|do({sorted(treatment)})) > 0"
            f" in support of X={sorted(treatment)}"
        ),
        graph_state_before=f"denominator: ID({sorted(conditions)},{sorted(treatment)},G)",
        depth=0,
    ))

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
    all_proof_steps = (
        idc_steps
        + list(num_result.proof_steps)
        + list(denom_result.proof_steps)
    )
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
    selection_diagram: "Any",  # SelectionDiagram — avoid circular import
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
) -> "HedgeCertificate | None":
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
        if not (Y <= si):
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
                        suggested_experiment=(
                            f"Randomize: {sorted(sj & X)}" if sj & X else None
                        ),
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
) -> list["HedgeCertificate"]:
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
        if not (Y <= si):
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
            all_certs.append(HedgeCertificate(
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
                    suggested_experiment=(
                        f"Randomize: {sorted(sj & X)}" if sj & X else None
                    ),
                ),
                minimal_required_s_nodes=frozenset(minimal_s),
            ))

    # Filter to minimal hedges: keep cert c if no other cert c' has c'.hedge_root ⊂ c.hedge_root
    minimal_certs: list[HedgeCertificate] = []
    for cert in all_certs:
        dominated = any(
            other is not cert and other.hedge_root < cert.hedge_root
            for other in all_certs
        )
        if not dominated:
            minimal_certs.append(cert)

    # Deterministic ordering
    return sorted(minimal_certs, key=lambda c: (sorted(c.hedge_forest), sorted(c.hedge_root)))


# ---------------------------------------------------------------------------
# ProofStep bridge: internal dataclass → public IR Pydantic model
# ---------------------------------------------------------------------------


def _internal_proof_step_to_ir(step: "ProofStep") -> "Any":
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
    return IRProofStep(
        rule_name=step.rule_name,
        description=step.applied_to_graph_state,
        variables_affected=step.antecedent_vars + step.consequent_vars,
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
    from polisyos.ir.analytics.estimand import EstimandNode

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
        ) if conditioning else (),
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
        f"[depth={depth}] Step 6: Si={sorted(si)} ⊂ Sj={sorted(sj)}, "
        f"recursing on subgraph G[Sj]"
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
        import y0  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        return dataclasses.replace(
            native_result,
            trace=[*native_result.trace, "oracle_y0: y0 not installed, skipping"],
        )

    try:
        from y0.graph import NxMixedGraph  # type: ignore[import-not-found]
        from y0.algorithm.identify import identify  # type: ignore[import-not-found]
        from y0.dsl import Variable  # type: ignore[import-not-found]

        nx_graph = graph.to_networkx()
        mixed = NxMixedGraph.from_mixed_edges(
            directed=[(e.src, e.dst) for e in graph.edges
                      if e.mark_src is EdgeMark.TAIL and e.mark_dst is EdgeMark.ARROW],
            undirected=[(e.src, e.dst) for e in graph.edges
                        if e.mark_src is EdgeMark.ARROW and e.mark_dst is EdgeMark.ARROW],
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
                treatment=next(iter(sorted(treatment))) if len(treatment) == 1 else str(sorted(treatment)),
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
    except Exception as exc:  # noqa: BLE001
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
        query_str = (
            f"p({', '.join(sorted(outcome))} | do({', '.join(sorted(treatment))}))"
        )
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
                treatment=next(iter(sorted(treatment))) if len(treatment) == 1 else str(sorted(treatment)),
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
    except Exception as exc:  # noqa: BLE001
        return dataclasses.replace(
            native_result,
            trace=[*native_result.trace, f"oracle_dosearch error: {exc}"],
        )


# ---------------------------------------------------------------------------
# Track A: Z-ID and MZ-ID (Bareinboim-Pearl 2013/2014)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SourceDomain:
    """Descriptor for a source domain in multi-domain transportability."""

    domain_id: str
    s_nodes: frozenset[str] = dataclasses.field(default_factory=frozenset)
    z_interventions: frozenset[str] = dataclasses.field(default_factory=frozenset)
    dataset_ref: str | None = None
    distribution_domain: Any = "source"  # DistributionDomain.SOURCE equivalent


def z_id_algorithm(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    z_interventions: frozenset[str],
    graph: CausalGraphModel,
    available_domains: list[Any] | None = None,
    dataset_ref: str | None = None,
    _depth: int = 0,
    _trace: list[str] | None = None,
) -> IdentificationResult:
    """Bareinboim-Pearl 2013 IJCAI Z-transportability algorithm.

    Extends the ID algorithm to exploit experimental distributions P_z(·|·)
    available from z-interventional studies.

    Parameters
    ----------
    treatment:         X — intervention variables
    outcome:           Y — outcome variables
    z_interventions:   Z — variables for which experimental distributions are available
    graph:             causal graph G
    available_domains: optional list of SourceDomain objects (unused in base impl)
    dataset_ref:       tag for DistributionRef leaves
    """
    if _trace is None:
        _trace = []

    _trace.append(
        f"[depth={_depth}] z_id_algorithm(X={sorted(treatment)}, Y={sorted(outcome)}, "
        f"Z={sorted(z_interventions)})"
    )

    _steps: list[ProofStep] = []

    # Step 0: No z-interventions — fall back to standard ID
    if not z_interventions:
        _trace.append(f"[depth={_depth}] z_id: no Z-interventions → standard id_with_oracle_fallback")
        return id_with_oracle_fallback(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            oracle="none",
            dataset_ref=dataset_ref,
        )

    # Step 1: Try direct Z-transport formula first (most informative, fewest assumptions)
    direct = _z_transport_direct_pass(
        treatment=treatment,
        outcome=outcome,
        z_interventions=z_interventions,
        graph=graph,
        dataset_ref=dataset_ref,
    )
    if direct is not None and direct.status is IdentificationStatus.IDENTIFIED:
        _trace.append(f"[depth={_depth}] z_id: direct Z-transport formula applies")
        _steps.append(
            ProofStep(
                rule_name="Z_TRANSPORT",
                antecedent_vars=tuple(sorted(z_interventions)),
                consequent_vars=tuple(sorted(outcome)),
                applied_to_graph_state=(
                    f"Direct Z-transport: Σ_Z P_z(Y|X,Z)·P*(Z) "
                    f"with Z={sorted(z_interventions)}"
                ),
                depth=_depth,
            )
        )
        return dataclasses.replace(
            direct,
            proof_steps=_steps + list(direct.proof_steps),
        )

    # Step 2: Try ID with EXPERIMENTAL domain (Z-interventions as experimental data)
    available_vars = frozenset(graph.nodes) - z_interventions
    if treatment <= available_vars or not (treatment & z_interventions):
        first_pass = id_algorithm(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            available_vars=frozenset(graph.nodes),
            dataset_ref=dataset_ref,
            domain=DistributionDomain.EXPERIMENTAL,
            _depth=_depth,
            _trace=_trace,
        )
        if first_pass.status is IdentificationStatus.IDENTIFIED:
            _trace.append(f"[depth={_depth}] z_id: first pass IDENTIFIED")
            return dataclasses.replace(
                first_pass,
                proof_steps=_steps + list(first_pass.proof_steps),
            )
    else:
        first_pass = IdentificationResult(
            status=IdentificationStatus.ORACLE_NEEDED,
            estimand_ast=None,
            hedge_certificate=None,
            trace=list(_trace),
            required_distributions=[],
        )

    _trace.append(f"[depth={_depth}] z_id: first pass status={first_pass.status}, trying idc fallback")

    # Step 3: Try IDC with each Z-variable as instrument
    best: IdentificationResult = first_pass
    status_rank = {
        IdentificationStatus.IDENTIFIED: 3,
        IdentificationStatus.ORACLE_NEEDED: 2,
        IdentificationStatus.PAG_AMBIGUOUS: 1,
        IdentificationStatus.HEDGE_FOUND: 0,
        IdentificationStatus.NOT_RECOVERABLE: -1,
    }

    for z in sorted(z_interventions):
        z_set = frozenset({z})
        try:
            candidate = idc_algorithm(
                treatment=treatment,
                outcome=outcome,
                conditions=z_set,
                graph=graph,
                dataset_ref=dataset_ref,
                domain=DistributionDomain.EXPERIMENTAL,
            )
            if status_rank.get(candidate.status, 0) > status_rank.get(best.status, 0):
                best = candidate
                _steps.append(
                    ProofStep(
                        rule_name="Z_TRANSPORT",
                        antecedent_vars=(z,),
                        consequent_vars=tuple(sorted(outcome)),
                        applied_to_graph_state=(
                            f"IDC fallback for Z-transport: P(Y|do(X),{z}) / P({z}|do(X)) "
                            f"with domain=EXPERIMENTAL"
                        ),
                        depth=_depth,
                    )
                )
                if best.status is IdentificationStatus.IDENTIFIED:
                    break
        except Exception:  # noqa: BLE001
            pass

    return dataclasses.replace(best, proof_steps=_steps + list(best.proof_steps))


def _prune_source_domains(
    outcome: frozenset[str],
    graph: CausalGraphModel,
    source_domains: list[SourceDomain],
) -> list[SourceDomain]:
    """Remove source domains that cannot contribute to identifying *outcome*.

    A domain contributes if its z_interventions or s_nodes intersect with any
    c-component that overlaps with the ancestral closure of the outcome.
    Domains with no special information (bare standard-ID fallbacks) are kept
    only if no other domain is available.

    The pruning is greedy (first-fit coverage) and preserves ordering.
    """
    all_comps = c_components(graph)
    relevant_vars = ancestors(graph, outcome)
    relevant_comps = [c for c in all_comps if c & relevant_vars]

    useful: list[SourceDomain] = []
    covered: set[frozenset[str]] = set()
    bare: list[SourceDomain] = []  # domains with no s/z info

    for domain in source_domains:
        domain_vars = domain.z_interventions | domain.s_nodes
        if not domain_vars:
            bare.append(domain)
            continue
        domain_comps = {c for c in relevant_comps if c & domain_vars}
        new_coverage = domain_comps - covered
        if new_coverage:
            useful.append(domain)
            covered |= new_coverage

    if not useful:
        # Fall back to all domains if pruning removes everything
        return source_domains
    # Append one bare domain as a last-resort standard-ID fallback
    if bare:
        useful.append(bare[0])
    return useful


def _mz_factorize_by_c_component(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    source_domains: list[SourceDomain],
    graph: CausalGraphModel,
    dataset_ref: str | None,
    _steps: list[ProofStep],
    _trace: list[str],
) -> IdentificationResult | None:
    """Formal mz-ID factorisation by c-component (Bareinboim & Pearl 2014, Theorem 2).

    Restricts to the ancestral subgraph G[An(Y)], computes c-components of that
    subgraph, and for each c-component that intersects the outcome set tries all
    source domains until one identifies the component.  Combines the per-component
    estimands via a ProductNode.

    Validity condition (Theorem 2):
        For every c-component Si ⊆ C(G[An(Y)]) with Si ∩ Y ≠ ∅:
            ∃ domain d such that id_algorithm on G[Si] identifies Y ∩ Si.
        Combined result: ∏_i Q[Si] covers all of Y.

    Returns None if factorisation fails (some component cannot be identified).
    """
    # Restrict to ancestral subgraph G[An(Y)] per Theorem 2
    an_y = ancestors(graph, outcome)
    ancestral_graph = induced_subgraph(graph, an_y)

    all_comps = c_components(ancestral_graph)
    if len(all_comps) <= 1:
        return None  # No factorisation benefit if there is only one c-component

    comp_results: list[tuple[IdentificationResult, str]] = []  # (result, domain_id)
    all_dists: list[DistributionRef] = []
    factor_nodes: list[Any] = []
    covered_outcomes: set[str] = set()

    for comp in all_comps:
        comp_outcome = outcome & comp
        if not comp_outcome:
            continue  # this component does not intersect Y

        comp_treatment = treatment & comp
        comp_graph = induced_subgraph(ancestral_graph, comp)

        # Try each domain for this component
        best_comp: IdentificationResult | None = None
        best_domain_id: str = ""
        for domain in source_domains:
            # Route through domain-appropriate algorithm
            has_z = bool(domain.z_interventions & comp)
            has_s = bool(domain.s_nodes & comp)
            eff_dataset = dataset_ref or domain.dataset_ref

            try:
                if has_s and has_z:
                    aug_comp = augment_with_s_nodes(comp_graph, domain.s_nodes & comp)
                    comp_result = z_id_algorithm(
                        treatment=comp_treatment if comp_treatment else treatment & frozenset(comp_graph.nodes),
                        outcome=comp_outcome,
                        z_interventions=domain.z_interventions & comp,
                        graph=aug_comp,
                        dataset_ref=eff_dataset,
                    )
                elif has_z:
                    comp_result = z_id_algorithm(
                        treatment=comp_treatment if comp_treatment else treatment & frozenset(comp_graph.nodes),
                        outcome=comp_outcome,
                        z_interventions=domain.z_interventions & comp,
                        graph=comp_graph,
                        dataset_ref=eff_dataset,
                    )
                else:
                    comp_result = id_with_oracle_fallback(
                        treatment=comp_treatment if comp_treatment else treatment & frozenset(comp_graph.nodes),
                        outcome=comp_outcome,
                        graph=comp_graph,
                        oracle="none",
                        dataset_ref=eff_dataset,
                    )
            except Exception:  # noqa: BLE001
                continue

            if comp_result.status is IdentificationStatus.IDENTIFIED:
                best_comp = comp_result
                best_domain_id = domain.domain_id
                break  # First domain that works is sufficient

        if best_comp is None:
            _trace.append(
                f"mz_factorize: c-component {sorted(comp)} not identified by any domain"
            )
            return None  # Factorisation fails

        # Record domain selection for this component
        _steps.append(
            ProofStep(
                rule_name="S_DOMAIN_SELECT",
                antecedent_vars=tuple(sorted(comp)),
                consequent_vars=tuple(sorted(comp_outcome)),
                applied_to_graph_state=(
                    f"Domain {best_domain_id!r} selected for c-component "
                    f"{sorted(comp)} → identifies {sorted(comp_outcome)}"
                ),
                depth=0,
            )
        )
        comp_results.append((best_comp, best_domain_id))
        assert best_comp.estimand_ast is not None
        factor_nodes.append(best_comp.estimand_ast.root)
        all_dists.extend(best_comp.required_distributions)
        covered_outcomes.update(comp_outcome)

    if not factor_nodes:
        return None

    # Completeness check: every outcome variable must be covered
    if not (outcome <= covered_outcomes):
        _trace.append(
            f"mz_factorize: incomplete — covered={sorted(covered_outcomes)}, "
            f"needed={sorted(outcome)}"
        )
        return None

    # Build combined estimand
    combined_root = factor_nodes[0] if len(factor_nodes) == 1 else ProductNode(factors=tuple(factor_nodes))
    combined_ast = EstimandAST(
        query_str=f"P({sorted(outcome)}|do({sorted(treatment)}))",
        root=combined_root,
        treatment=(
            next(iter(sorted(treatment))) if len(treatment) == 1 else str(sorted(treatment))
        ),
        outcome=(
            next(iter(sorted(outcome))) if len(outcome) == 1 else str(sorted(outcome))
        ),
        all_variables=tuple(sorted(treatment | outcome)),
        identification_method="mz_id_factorization",
    )

    # Emit MZ_FACTORIZE ProofStep
    _steps.append(
        ProofStep(
            rule_name="MZ_FACTORIZE",
            antecedent_vars=tuple(sorted(treatment | outcome)),
            consequent_vars=tuple(sorted(outcome)),
            applied_to_graph_state=(
                f"mz-ID factorisation over {len(factor_nodes)} c-component(s) "
                f"of G[An(Y)] succeeded"
            ),
            depth=0,
        )
    )
    _trace.append(
        f"mz_factorize: factorisation succeeded over {len(factor_nodes)} c-component(s)"
    )

    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=combined_ast,
        hedge_certificate=None,
        trace=_trace,
        required_distributions=all_dists,
        proof_steps=list(_steps),
    )


def mz_id_algorithm(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    source_domains: list[SourceDomain],
    graph: CausalGraphModel,
    dataset_ref: str | None = None,
) -> IdentificationResult:
    """Pearl-Bareinboim 2014 AAAI meta-transportability algorithm.

    Combines evidence from multiple source domains (each potentially having
    s-node selections and/or z-interventions) to identify a causal effect
    in the target domain.

    Enhancements:
    - Uses :func:`augment_with_s_nodes` from admg_ops for domain S-node augmentation
    - Fixed :class:`SNode` instantiation (was missing required fields)
    - Formal c-component factorisation via :func:`_mz_factorize_by_c_component`
      (restricted to ancestral subgraph per Bareinboim & Pearl 2014 Theorem 2)
    - ProofStep emission for MZ_FACTORIZE and S_DOMAIN_SELECT

    Parameters
    ----------
    treatment:      X — intervention variables
    outcome:        Y — outcome variables
    source_domains: list of SourceDomain descriptors
    graph:          target-domain causal graph G
    dataset_ref:    tag for DistributionRef leaves
    """
    _trace: list[str] = [
        f"mz_id_algorithm(X={sorted(treatment)}, Y={sorted(outcome)}, "
        f"domains={[d.domain_id for d in source_domains]})"
    ]

    # No source domains — fall back to standard ID
    if not source_domains:
        return id_with_oracle_fallback(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            oracle="none",
            dataset_ref=dataset_ref,
        )

    # Prune source domains that cannot contribute to identifying outcome
    pruned = _prune_source_domains(outcome, graph, source_domains)
    if len(pruned) < len(source_domains):
        _trace.append(
            f"mz_id: pruned {len(source_domains) - len(pruned)} irrelevant domain(s)"
        )
        source_domains = pruned

    identified_results: list[tuple[int, IdentificationResult]] = []  # (domain_idx, result)
    last_result: IdentificationResult | None = None

    for domain_idx, domain in enumerate(source_domains):
        has_s = bool(domain.s_nodes)
        has_z = bool(domain.z_interventions)

        if has_s and has_z:
            # Domain has both S-nodes and Z-interventions: use z_id on S-augmented graph
            augmented = augment_with_s_nodes(graph, domain.s_nodes)
            result = z_id_algorithm(
                treatment=treatment,
                outcome=outcome,
                z_interventions=domain.z_interventions,
                graph=augmented,
                dataset_ref=dataset_ref or domain.dataset_ref,
            )
        elif has_s:
            # Domain has only S-nodes: use tr_algorithm with a minimal SelectionDiagram
            try:
                from polisyos.ir.analytics.context import ContextProfile  # noqa: PLC0415
                from polisyos.ir.analytics.transportability import SelectionDiagram, SNode  # noqa: PLC0415
                s_node_list = [
                    SNode(
                        target_variable=sv,
                        context_dimension="programmatic",
                        source_value=0.0,
                        target_value=1.0,
                        delta=1.0,
                        severity="medium",
                    )
                    for sv in sorted(domain.s_nodes)
                ]
                ctx = ContextProfile()
                sd_obj = SelectionDiagram(
                    base_graph=graph,
                    s_nodes=s_node_list,
                    source_context=ctx,
                    target_context=ctx,
                )
                result = tr_algorithm(
                    treatment=treatment,
                    outcome=outcome,
                    selection_diagram=sd_obj,
                    dataset_ref=dataset_ref or domain.dataset_ref,
                )
            except Exception:  # noqa: BLE001
                result = id_with_oracle_fallback(
                    treatment=treatment,
                    outcome=outcome,
                    graph=graph,
                    oracle="none",
                    dataset_ref=dataset_ref or domain.dataset_ref,
                )
        elif has_z:
            # Domain has only Z-interventions
            result = z_id_algorithm(
                treatment=treatment,
                outcome=outcome,
                z_interventions=domain.z_interventions,
                graph=graph,
                dataset_ref=dataset_ref or domain.dataset_ref,
            )
        else:
            # No special information — standard ID
            result = id_with_oracle_fallback(
                treatment=treatment,
                outcome=outcome,
                graph=graph,
                oracle="none",
                dataset_ref=dataset_ref or domain.dataset_ref,
            )

        last_result = result
        if result.status is IdentificationStatus.IDENTIFIED:
            identified_results.append((domain_idx, result))

    # Return best IDENTIFIED result — prefer the domain with more z_interventions
    # (more experimental information → more reliable estimand).
    if identified_results:
        def _z_count_for_pair(pair: tuple[int, IdentificationResult]) -> int:
            d_idx, _ = pair
            return len(source_domains[d_idx].z_interventions)

        identified_results.sort(key=_z_count_for_pair, reverse=True)
        return identified_results[0][1]

    # Formal cross-domain factorisation (Bareinboim & Pearl 2014, Theorem 2)
    if len(source_domains) > 1:
        factorize_steps: list[ProofStep] = []
        fact_result = _mz_factorize_by_c_component(
            treatment=treatment,
            outcome=outcome,
            source_domains=source_domains,
            graph=graph,
            dataset_ref=dataset_ref,
            _steps=factorize_steps,
            _trace=_trace,
        )
        if fact_result is not None:
            return fact_result

    # Nothing worked — return the last result (ORACLE_NEEDED or HEDGE_FOUND)
    if last_result is not None:
        return last_result
    return id_with_oracle_fallback(
        treatment=treatment,
        outcome=outcome,
        graph=graph,
        oracle="none",
        dataset_ref=dataset_ref,
    )


# ===========================================================================
# PHASE 5: Extended Identification Theory
# ===========================================================================

# ---------------------------------------------------------------------------
# 5.1  Stochastic, Conditional, and Dynamic Interventions
# ---------------------------------------------------------------------------

# Proof-step rule name constants for Phase-5 steps
_SID_POLICY_WRAP = "SID_POLICY_WRAP"
_SID_SHIFT = "SID_SHIFT"
_SID_CONDITIONAL = "SID_CONDITIONAL"
_DYNAMIC_GFORMULA = "DYNAMIC_GFORMULA"
_JOINT_FACTOR_DECOMPOSE = "JOINT_FACTOR_DECOMPOSE"
_MULTI_OUTCOME_SHARED_CCOMP = "MULTI_OUTCOME_SHARED_CCOMP"


def sid_algorithm(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    policy: StochasticPolicy,
    available_vars: frozenset[str] | None = None,
    dataset_ref: str | None = None,
    domain: DistributionDomain = DistributionDomain.SOURCE,
    s_nodes: Any = None,
) -> IdentificationResult:
    """Stochastic intervention identification (Correa & Bareinboim 2020).

    Identifies E_π[Y] = ∫ P(Y|do(X=x)) π(x|Z) dx for a policy π by:

    1. Running the standard ID algorithm to obtain P(Y|do(X=x)).
    2. If identified, wrapping the result in a :class:`StochasticInterventionNode`
       that encodes the policy integration.
    3. For ``shift`` policies (Díaz & van der Laan 2012), a modified-treatment-policy
       wrapper is produced instead of a hard do() node.
    4. For ``conditional`` policies (do(X|Z=z)), delegating to
       :func:`conditional_intervention_id`.

    Parameters
    ----------
    treatment:
        X — the treatment variable(s) being intervened on stochastically.
    outcome:
        Y — the target outcome variable(s).
    graph:
        Causal DAG or PAG.
    policy:
        The stochastic policy π specification.
    available_vars, dataset_ref, domain, s_nodes:
        Forwarded to the inner :func:`id_algorithm` call.

    References
    ----------
    Correa, J. & Bareinboim, E. (2020). "A Calculus for Stochastic
        Interventions: Causal Effect Identification and Surrogate
        Experiments." NeurIPS 2020.
    Díaz, I. & van der Laan, M.J. (2012). "Population Intervention Causal
        Effects Based on Stochastic Interventions." Biometrics 68(2).
    """
    _trace: list[str] = []
    _steps: list[ProofStep] = []

    t_str = next(iter(sorted(treatment))) if len(treatment) == 1 else str(sorted(treatment))
    y_str = next(iter(sorted(outcome))) if len(outcome) == 1 else str(sorted(outcome))

    _trace.append(
        f"[SID] sid_algorithm(X={sorted(treatment)}, Y={sorted(outcome)}, "
        f"policy_type={policy.policy_type})"
    )

    # Delegate conditional-type policy to conditional_intervention_id
    if policy.policy_type == "conditional":
        if not policy.conditioning_vars:
            _trace.append("[SID] conditional policy has empty conditioning_vars → standard ID")
        else:
            cond_result = conditional_intervention_id(
                treatment=treatment,
                outcome=outcome,
                condition_vars=frozenset(policy.conditioning_vars),
                graph=graph,
                available_vars=available_vars,
                dataset_ref=dataset_ref,
                domain=domain,
            )
            _steps.append(ProofStep(
                rule_name=_SID_CONDITIONAL,
                antecedent_vars=tuple(sorted(treatment)),
                consequent_vars=tuple(sorted(outcome)),
                applied_to_graph_state=(
                    f"Conditional policy do(X|Z={sorted(policy.conditioning_vars)}) "
                    f"→ conditional_intervention_id; inner status={cond_result.status.value}"
                ),
                depth=0,
            ))
            return dataclasses.replace(
                cond_result,
                proof_steps=_steps + list(cond_result.proof_steps),
                algorithm_version="sid_conditional_v1",
                metadata={
                    **dict(getattr(cond_result, "metadata", {}) or {}),
                    "policy_type": policy.policy_type,
                    "policy_conditioning_vars": list(policy.conditioning_vars),
                    "policy_expr": policy.policy_expr,
                },
            )

    # Standard path: run base ID algorithm to get P(Y|do(X=x))
    base_result = id_algorithm(
        treatment=treatment,
        outcome=outcome,
        graph=graph,
        dataset_ref=dataset_ref,
        domain=domain,
        available_vars=available_vars,
    )
    _trace.extend(base_result.trace)

    if base_result.status is not IdentificationStatus.IDENTIFIED:
        _trace.append(
            f"[SID] Base ID returned {base_result.status.value} — "
            "stochastic ID inherits non-identifiability"
        )
        return dataclasses.replace(
            base_result,
            trace=_trace,
            algorithm_version="sid_v1",
            metadata={
                **dict(getattr(base_result, "metadata", {}) or {}),
                "policy_type": policy.policy_type,
                "policy_conditioning_vars": list(policy.conditioning_vars),
                "policy_expr": policy.policy_expr,
                "shift_delta": policy.shift_delta,
            },
        )

    # Base ID succeeded — wrap the inner estimand in a stochastic node
    inner_do_node = base_result.estimand_ast.root  # type: ignore[union-attr]
    integration_var = t_str if len(treatment) == 1 else sorted(treatment)[0]

    rule = _SID_SHIFT if policy.policy_type == "shift" else _SID_POLICY_WRAP
    _steps.append(ProofStep(
        rule_name=rule,
        antecedent_vars=tuple(sorted(treatment)),
        consequent_vars=tuple(sorted(outcome)),
        applied_to_graph_state=(
            f"policy_type={policy.policy_type}; "
            f"wrapped P({y_str}|do({t_str})) in StochasticInterventionNode"
        ),
        depth=0,
    ))
    wrapper_kind = (
        "ModifiedTreatmentPolicyNode"
        if policy.policy_type == "shift"
        else "StochasticInterventionNode"
    )
    _trace.append(
        f"[SID] IDENTIFIED — wrapped base estimand in {wrapper_kind} "
        f"(policy_type={policy.policy_type})"
    )

    if policy.policy_type == "shift":
        policy_expr = policy.policy_expr or (
            f"{t_str}+{policy.shift_delta}"
            if policy.shift_delta is not None
            else f"shift({t_str})"
        )
        root_node = ModifiedTreatmentPolicyNode(
            treatment_var=t_str,
            policy_expr=policy_expr,
            natural_treatment_var=t_str,
            covariates=tuple(policy.conditioning_vars),
            inner_node=inner_do_node,
            domain=domain,
            dataset_ref=dataset_ref,
        )
        query_str = f"E_d[{y_str}|mtp({t_str})]"
        identification_method = "mtp_shift"
    else:
        root_node = StochasticInterventionNode(
            treatment_var=t_str,
            policy=policy,
            inner_do_node=inner_do_node,
            integration_var=integration_var,
            domain=domain,
        )
        query_str = f"E_π[{y_str}|do({t_str})]"
        identification_method = f"sid_{policy.policy_type}"

    ast = EstimandAST(
        query_str=query_str,
        root=root_node,
        treatment=t_str,
        outcome=y_str,
        all_variables=tuple(sorted(treatment | outcome)),
        identification_method=identification_method,
    )
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=ast,
        hedge_certificate=None,
        trace=_trace,
        required_distributions=base_result.required_distributions,
        algorithm_version="sid_v1",
        proof_steps=_steps + list(base_result.proof_steps),
        metadata={
            **dict(getattr(base_result, "metadata", {}) or {}),
            "policy_type": policy.policy_type,
            "policy_conditioning_vars": list(policy.conditioning_vars),
            "policy_expr": policy.policy_expr,
            "shift_delta": policy.shift_delta,
        },
    )


def conditional_intervention_id(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    condition_vars: frozenset[str],
    graph: CausalGraphModel,
    available_vars: frozenset[str] | None = None,
    dataset_ref: str | None = None,
    domain: DistributionDomain = DistributionDomain.SOURCE,
) -> IdentificationResult:
    """Identify P(Y | do(X | Z=z)) — conditional intervention (Pearl 2009, §4.2).

    A conditional intervention do(X|Z=z) applies the treatment only within the
    subpopulation where Z=z.  Formally this equals the standard ID estimand
    P(Y|do(X)) evaluated within that stratum.

    Algorithm
    ---------
    1. Run id_algorithm(X, Y, graph) to get P(Y|do(X)).
    2. If identified, wrap the inner estimand in a :class:`ConditionalInterventionNode`
       recording the conditioning variables Z.
    3. Estimation delegates to an AIPW/TMLE restricted to the Z=z stratum.

    Parameters
    ----------
    treatment:
        X — treatment variable(s).
    outcome:
        Y — outcome variable(s).
    condition_vars:
        Z — variables defining the conditioning subpopulation.
    graph, available_vars, dataset_ref, domain:
        Standard ID algorithm inputs.

    References
    ----------
    Pearl, J. (2009). *Causality*, 2nd ed., §4.2. Cambridge University Press.
    """
    _trace: list[str] = []
    _steps: list[ProofStep] = []

    t_str = next(iter(sorted(treatment))) if len(treatment) == 1 else str(sorted(treatment))
    y_str = next(iter(sorted(outcome))) if len(outcome) == 1 else str(sorted(outcome))
    z_sorted = sorted(condition_vars)

    _trace.append(
        f"[COND-DO] conditional_intervention_id("
        f"X={sorted(treatment)}, Y={sorted(outcome)}, Z={z_sorted})"
    )

    # Step 1: standard ID on the full graph
    base_result = id_algorithm(
        treatment=treatment,
        outcome=outcome,
        graph=graph,
        dataset_ref=dataset_ref,
        domain=domain,
        available_vars=available_vars,
    )
    _trace.extend(base_result.trace)

    if base_result.status is not IdentificationStatus.IDENTIFIED:
        _trace.append(
            f"[COND-DO] Base ID returned {base_result.status.value} — "
            "conditional ID inherits non-identifiability"
        )
        return dataclasses.replace(
            base_result,
            trace=_trace,
            algorithm_version="cond_do_v1",
        )

    # Step 2: wrap in ConditionalInterventionNode
    cond_node = ConditionalInterventionNode(
        treatment=t_str,
        outcome=y_str,
        condition_vars=tuple(z_sorted),
        inner_do_node=base_result.estimand_ast.root,  # type: ignore[union-attr]
        domain=domain,
        dataset_ref=dataset_ref,
    )
    _steps.append(ProofStep(
        rule_name=_SID_CONDITIONAL,
        antecedent_vars=tuple(sorted(treatment)),
        consequent_vars=tuple(sorted(outcome)),
        applied_to_graph_state=(
            f"do(X|Z={z_sorted}): standard ID succeeded; "
            f"wrapped in ConditionalInterventionNode(condition_vars={z_sorted})"
        ),
        depth=0,
    ))
    _trace.append(
        f"[COND-DO] IDENTIFIED — wrapped in ConditionalInterventionNode(Z={z_sorted})"
    )

    ast = EstimandAST(
        query_str=f"P({y_str}|do({t_str}|Z={z_sorted}))",
        root=cond_node,
        treatment=t_str,
        outcome=y_str,
        all_variables=tuple(sorted(treatment | outcome | condition_vars)),
        identification_method="conditional_do",
    )
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=ast,
        hedge_certificate=None,
        trace=_trace,
        required_distributions=base_result.required_distributions,
        algorithm_version="cond_do_v1",
        proof_steps=_steps + list(base_result.proof_steps),
    )


def dynamic_intervention_id(
    *,
    treatment_sequence: list[str],
    outcome: str,
    graph: CausalGraphModel,
    time_points: list[int],
    covariate_sequence: list[str] | None = None,
    dataset_ref: str | None = None,
    domain: DistributionDomain = DistributionDomain.SOURCE,
) -> IdentificationResult:
    """Identify P(Y^ā) for a sequential / dynamic treatment regime ā = (A_0,...,A_T).

    The identification reduces to the *g-computation formula* (Robins 1986):

        P(Y^ā) = Σ_{l̄} ∏_t P(L_t | ā_{t-1}, l̄_{t-1}) × E[Y | ā, l̄]

    Sequential ignorability is checked graphically: for each time point t,
    we require L_t ⊥ A_t | (ā_{t-1}, l̄_{t-1}) in G_{do(A_1,...,A_{t-1})}.

    Parameters
    ----------
    treatment_sequence:
        Ordered list of treatment variables [A_0, A_1, ..., A_T].
    outcome:
        Terminal outcome variable Y.
    graph:
        Causal DAG encoding the longitudinal data-generating process.
    time_points:
        Integer time indices corresponding to each treatment in the sequence.
    covariate_sequence:
        Optional ordered list of time-varying covariate variables [L_0, ..., L_T].
        Defaults to all non-treatment, non-outcome graph nodes.
    dataset_ref, domain:
        Standard estimand metadata.

    References
    ----------
    Robins, J.M. (1986). "A New Approach to Causal Inference in Mortality
        Studies with a Sustained Exposure Period." Math Modelling, 7, 1393–1512.
    Hernán, M.A. & Robins, J.M. (2020). *Causal Inference: What If.*
        Chapman & Hall.
    """
    _trace: list[str] = []
    _steps: list[ProofStep] = []

    T = len(treatment_sequence)
    all_nodes = set(graph.nodes)

    if covariate_sequence is None:
        reserved = set(treatment_sequence) | {outcome}
        covariate_sequence = [
            v for v in sorted(all_nodes - reserved)
        ]

    _trace.append(
        f"[DYN-ID] dynamic_intervention_id("
        f"A={treatment_sequence}, Y={outcome}, T={T})"
    )

    # --- Sequential ignorability check (graphical) ---
    si_satisfied = True
    si_warnings: list[str] = []
    for t_idx, at in enumerate(treatment_sequence):
        prev_treatments = frozenset(treatment_sequence[:t_idx])
        # Check A_t ⊥ Y | prev_treatments, covariates in the mutilated graph
        mutilated = do_operator(graph, prev_treatments) if prev_treatments else graph
        y_ancestors = ancestors(mutilated, frozenset({outcome}))
        # A_t should not be an ancestor of Y through a back-door path
        # Simplified check: no unblocked paths from A_t back-doors after mutilation
        at_node_set = frozenset({at})
        # m-separation: A_t independent of time-lagged confounders given history
        remaining_confounders = y_ancestors - frozenset(treatment_sequence) - frozenset({outcome})
        if remaining_confounders:
            sep_ok = m_separation(
                mutilated,
                x_set=at_node_set,
                y_set=frozenset({outcome}),
                z_set=prev_treatments | frozenset(covariate_sequence),
            )
            if not sep_ok:
                si_satisfied = False
                si_warnings.append(
                    f"Sequential ignorability potentially violated at t={t_idx}: "
                    f"A_{t_idx}={at} not m-separated from Y given history"
                )

    if not si_satisfied:
        warning_str = "; ".join(si_warnings)
        _trace.append(f"[DYN-ID] Sequential ignorability check: WARNINGS — {warning_str}")
        _steps.append(ProofStep(
            rule_name=_DYNAMIC_GFORMULA,
            antecedent_vars=tuple(treatment_sequence),
            consequent_vars=(outcome,),
            applied_to_graph_state=f"Sequential ignorability warnings: {warning_str}",
            depth=0,
        ))
        # Still emit the g-formula estimand with a side-condition warning
        # (the estimand is correct *if* the user asserts SI holds)

    # Build g-formula estimand as a ProductNode of sequential conditional factors
    # P(Y^ā) = Σ_{l̄} ∏_t P(L_t|Ā_{t-1},L̄_{t-1}) · E[Y|Ā,L̄]
    factors = []

    # Time-varying covariate densities P(L_t | history)
    for t_idx, lt in enumerate(covariate_sequence):
        history_treatments = tuple(treatment_sequence[:t_idx])
        history_covariates = tuple(covariate_sequence[:t_idx])
        cond_set = history_treatments + history_covariates
        factors.append(DistributionRef(
            domain=domain,
            variables=(lt,),
            conditioning=cond_set,
            dataset_ref=dataset_ref,
            intervention_set=(),
        ))

    # Outcome model E[Y | full treatment + covariate history]
    outcome_factor = DistributionRef(
        domain=domain,
        variables=(outcome,),
        conditioning=tuple(treatment_sequence) + tuple(covariate_sequence),
        dataset_ref=dataset_ref,
        intervention_set=tuple(treatment_sequence),
    )
    factors.append(outcome_factor)

    all_covariate_vars = tuple(covariate_sequence)
    if factors:
        if len(factors) == 1:
            inner_node = factors[0]
        else:
            inner_node = ProductNode(factors=tuple(factors))
    else:
        inner_node = outcome_factor

    root = SumNode(
        summation_vars=all_covariate_vars,
        operand=inner_node,
    ) if all_covariate_vars else inner_node

    si_note = "sequential_ignorability_assumed" if si_satisfied else "sequential_ignorability_warnings"
    _steps.append(ProofStep(
        rule_name=_DYNAMIC_GFORMULA,
        antecedent_vars=tuple(treatment_sequence),
        consequent_vars=(outcome,),
        applied_to_graph_state=(
            f"g-formula T={T}: "
            f"{len(covariate_sequence)} time-varying covariates; {si_note}"
        ),
        depth=0,
    ))
    _trace.append(
        f"[DYN-ID] IDENTIFIED via g-formula (T={T}, {si_note})"
    )

    t_label = str(treatment_sequence)
    ast = EstimandAST(
        query_str=f"P({outcome}^ā; ā={treatment_sequence})",
        root=root,
        treatment=treatment_sequence[0] if treatment_sequence else "",
        outcome=outcome,
        all_variables=tuple(sorted(set(treatment_sequence) | set(covariate_sequence) | {outcome})),
        identification_method="dynamic_g_formula",
    )
    all_dist_refs = [
        DistributionRef(
            domain=domain,
            variables=(v,),
            dataset_ref=dataset_ref,
        )
        for v in sorted(set(treatment_sequence) | set(covariate_sequence) | {outcome})
    ]
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=ast,
        hedge_certificate=None,
        trace=_trace,
        required_distributions=all_dist_refs,
        algorithm_version="dynamic_g_formula_v1",
        proof_steps=_steps,
    )


# ---------------------------------------------------------------------------
# 5.2  Multi-Outcome and Joint Interventions
# ---------------------------------------------------------------------------


def joint_id_algorithm(
    *,
    treatments: frozenset[str],
    outcomes: frozenset[str],
    graph: CausalGraphModel,
    available_vars: frozenset[str] | None = None,
    dataset_ref: str | None = None,
    domain: DistributionDomain = DistributionDomain.SOURCE,
) -> IdentificationResult:
    """Identify P(Y₁,...,Yₖ | do(X₁,...,Xₘ)) via c-component factorisation.

    Implements Tian (2002): factor the joint interventional distribution via
    c-components of G \\ X, then identify each factor independently.  A single
    c-component decomposition is computed and shared across all outcome factors,
    making this more efficient than K independent ID calls.

    Algorithm
    ---------
    1. Compute c-components {S_1,...,S_k} of G[V \\ X].
    2. Partition outcomes Y into groups Y_i = Y ∩ S_i.
    3. For each non-empty Y_i run id_algorithm(X, Y_i, G[S_i ∪ X]).
    4. If all factors are identified, combine via ProductNode over all estimands.

    Parameters
    ----------
    treatments:
        X — set of treatment variable(s) being fixed.
    outcomes:
        Y — set of all target outcome variable(s).
    graph, available_vars, dataset_ref, domain:
        Standard ID algorithm inputs.

    References
    ----------
    Tian, J. (2002). "Studies in Causal Reasoning and Learning." PhD thesis,
        UCLA.  (Joint identification via c-component factorisation.)
    Tian, J. & Pearl, J. (2002). "A General Identification Condition for
        Causal Effects." AAAI 2002.
    """
    _trace: list[str] = []
    _steps: list[ProofStep] = []

    if available_vars is None:
        available_vars = frozenset(graph.nodes)

    t_str = str(sorted(treatments)) if len(treatments) != 1 else next(iter(sorted(treatments)))
    y_str = str(sorted(outcomes)) if len(outcomes) != 1 else next(iter(sorted(outcomes)))

    _trace.append(
        f"[JOINT-ID] joint_id_algorithm("
        f"X={sorted(treatments)}, Y={sorted(outcomes)})"
    )

    # Degenerate case: single treatment, single outcome → standard ID
    if len(outcomes) == 1 and len(treatments) == 1:
        return id_algorithm(
            treatment=treatments,
            outcome=outcomes,
            graph=graph,
            dataset_ref=dataset_ref,
            domain=domain,
            available_vars=available_vars,
        )

    # Step 1: Compute c-components of G \ X
    g_minus_x = induced_subgraph(graph, available_vars - treatments)
    comps = c_components(g_minus_x)  # list[frozenset[str]]

    _trace.append(
        f"[JOINT-ID] c-components of G\\X: {[sorted(c) for c in comps]}"
    )
    _steps.append(ProofStep(
        rule_name=_JOINT_FACTOR_DECOMPOSE,
        antecedent_vars=tuple(sorted(treatments)),
        consequent_vars=tuple(sorted(outcomes)),
        applied_to_graph_state=(
            f"c-components of G\\X computed once: "
            f"{[sorted(c) for c in comps]}"
        ),
        depth=0,
    ))

    # Step 2: group outcomes by c-component
    comp_outcome_groups: list[tuple[frozenset[str], frozenset[str]]] = []
    unassigned = set(outcomes)
    for comp in comps:
        y_in_comp = outcomes & comp
        if y_in_comp:
            comp_outcome_groups.append((comp, y_in_comp))
            unassigned -= y_in_comp

    if unassigned:
        # Outcomes not in any c-component of G\X → they may be in X or unreachable
        _trace.append(
            f"[JOINT-ID] Unassigned outcomes {sorted(unassigned)} — "
            "not in any c-component of G\\X; treating as trivially identified"
        )
        # Add them as trivial factors
        for v in sorted(unassigned):
            comp_outcome_groups.append((frozenset({v}), frozenset({v})))

    # Step 3: identify each factor
    all_identified = True
    factor_estimands: list[Any] = []
    all_required: list[DistributionRef] = []
    last_failed_result: IdentificationResult | None = None

    for comp, y_group in comp_outcome_groups:
        sub_vars = (comp | treatments) & available_vars
        sub_graph = induced_subgraph(graph, sub_vars)
        factor_result = id_algorithm(
            treatment=treatments,
            outcome=y_group,
            graph=sub_graph,
            dataset_ref=dataset_ref,
            domain=domain,
            available_vars=sub_vars,
        )
        _trace.extend(factor_result.trace)
        all_required.extend(factor_result.required_distributions)

        if factor_result.status is not IdentificationStatus.IDENTIFIED:
            _trace.append(
                f"[JOINT-ID] Factor for Y_group={sorted(y_group)} "
                f"FAILED: {factor_result.status.value}"
            )
            all_identified = False
            last_failed_result = factor_result
            break

        factor_estimands.append(factor_result.estimand_ast.root)  # type: ignore[union-attr]
        _trace.append(
            f"[JOINT-ID] Factor for Y_group={sorted(y_group)} IDENTIFIED"
        )

    if not all_identified:
        _trace.append("[JOINT-ID] Joint identification FAILED — returning last failed result")
        return dataclasses.replace(
            last_failed_result,  # type: ignore[arg-type]
            trace=_trace,
            proof_steps=_steps + list(last_failed_result.proof_steps),  # type: ignore[union-attr]
            algorithm_version="joint_id_v1",
        )

    # Step 4: combine factors into joint ProductNode
    if len(factor_estimands) == 1:
        joint_root = factor_estimands[0]
    else:
        joint_root = ProductNode(factors=tuple(factor_estimands))

    _steps.append(ProofStep(
        rule_name=_JOINT_FACTOR_DECOMPOSE,
        antecedent_vars=tuple(sorted(treatments)),
        consequent_vars=tuple(sorted(outcomes)),
        applied_to_graph_state=(
            f"Joint identification SUCCEEDED: "
            f"{len(factor_estimands)} factors combined into ProductNode"
        ),
        depth=0,
    ))
    _trace.append(
        f"[JOINT-ID] IDENTIFIED — {len(factor_estimands)} factor(s) as ProductNode"
    )

    ast = EstimandAST(
        query_str=f"P({y_str}|do({t_str}))",
        root=joint_root,
        treatment=t_str,
        outcome=y_str,
        all_variables=tuple(sorted(treatments | outcomes)),
        identification_method="joint_id_c_component",
    )
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=ast,
        hedge_certificate=None,
        trace=_trace,
        required_distributions=list(dict.fromkeys(
            (str(d), d) for d in all_required
        ).values()) if all_required else [],
        algorithm_version="joint_id_v1",
        proof_steps=_steps,
    )


def multi_outcome_id(
    *,
    treatment: frozenset[str],
    outcomes: list[str],
    graph: CausalGraphModel,
    available_vars: frozenset[str] | None = None,
    dataset_ref: str | None = None,
    domain: DistributionDomain = DistributionDomain.SOURCE,
) -> dict[str, IdentificationResult]:
    """Identify P(Yᵢ|do(X)) for each Yᵢ, sharing one c-component decomposition.

    More efficient than K independent :func:`id_algorithm` calls when all
    outcomes share the same treatment and graph.  The c-components of G \\ X are
    computed once, then each outcome Y_i is resolved within its component.

    Parameters
    ----------
    treatment:
        X — treatment variable(s).
    outcomes:
        List of outcome variable names to identify simultaneously.
    graph, available_vars, dataset_ref, domain:
        Standard ID algorithm inputs.

    Returns
    -------
    dict[str, IdentificationResult]
        Keyed by outcome variable name.  Each value is a standard
        :class:`IdentificationResult` (IDENTIFIED or failure).
    """
    if available_vars is None:
        available_vars = frozenset(graph.nodes)

    _trace: list[str] = []
    _trace.append(
        f"[MULTI-ID] multi_outcome_id("
        f"X={sorted(treatment)}, Y_list={outcomes})"
    )

    # Shared c-component decomposition
    g_minus_x = induced_subgraph(graph, available_vars - treatment)
    comps = c_components(g_minus_x)

    _trace.append(
        f"[MULTI-ID] Shared c-components of G\\X: {[sorted(c) for c in comps]}"
    )

    # Map each outcome to its c-component for efficient sub-graph selection
    outcome_to_comp: dict[str, frozenset[str]] = {}
    for y_var in outcomes:
        for comp in comps:
            if y_var in comp:
                outcome_to_comp[y_var] = comp
                break
        if y_var not in outcome_to_comp:
            # Not in any c-component — treat as singleton
            outcome_to_comp[y_var] = frozenset({y_var})

    results: dict[str, IdentificationResult] = {}
    shared_step = ProofStep(
        rule_name=_MULTI_OUTCOME_SHARED_CCOMP,
        antecedent_vars=tuple(sorted(treatment)),
        consequent_vars=tuple(outcomes),
        applied_to_graph_state=(
            f"Shared c-component decomposition for {len(outcomes)} outcomes: "
            f"{[sorted(c) for c in comps]}"
        ),
        depth=0,
    )

    for y_var in outcomes:
        comp = outcome_to_comp[y_var]
        sub_vars = (comp | treatment) & available_vars
        sub_graph = induced_subgraph(graph, sub_vars)
        result = id_algorithm(
            treatment=treatment,
            outcome=frozenset({y_var}),
            graph=sub_graph,
            dataset_ref=dataset_ref,
            domain=domain,
            available_vars=sub_vars,
        )
        # Prepend the shared c-component step to each result's proof steps
        results[y_var] = dataclasses.replace(
            result,
            proof_steps=[shared_step] + list(result.proof_steps),
            algorithm_version="multi_outcome_id_v1",
        )
        _trace.append(
            f"[MULTI-ID] Y={y_var} → {result.status.value}"
        )

    return results


def _has_bidirected_edge(graph: CausalGraphModel, left: str, right: str) -> bool:
    """Return True when the graph contains a latent-confounding edge left ↔ right."""
    for edge in graph.edges:
        if (
            {edge.src, edge.dst} == {left, right}
            and edge.mark_src is EdgeMark.ARROW
            and edge.mark_dst is EdgeMark.ARROW
        ):
            return True
    return False


@dataclasses.dataclass(frozen=True)
class _CtfWorldSpec:
    key: str
    intervention: tuple[tuple[str, float], ...]


@dataclasses.dataclass(frozen=True)
class _NormalizedCtfQuery:
    target_intervention: tuple[tuple[str, float], ...]
    evidence: tuple[tuple[str, float], ...]
    conditioning: tuple[str, ...]
    worlds: tuple[_CtfWorldSpec, ...]
    outcome_worlds: tuple[tuple[tuple[str, float], ...], ...]
    joint_worlds: bool = False


def _sorted_assignments(
    assignments: tuple[tuple[str, float], ...] | list[tuple[str, float]] | dict[str, float],
) -> tuple[tuple[str, float], ...]:
    if isinstance(assignments, dict):
        items = assignments.items()
    else:
        items = assignments
    return tuple(sorted((str(name), float(value)) for name, value in items))


def _format_assignment(value: float) -> str:
    return f"{value:g}"


def _infer_reference_intervention(
    assignments: tuple[tuple[str, float], ...],
) -> tuple[tuple[str, float], ...]:
    inferred: list[tuple[str, float]] = []
    for name, value in assignments:
        if value in (0.0, 1.0):
            inferred.append((name, 1.0 - value))
        else:
            return ()
    return tuple(inferred)


def _make_world_specs(
    interventions: tuple[tuple[tuple[str, float], ...], ...],
) -> tuple[_CtfWorldSpec, ...]:
    world_specs: list[_CtfWorldSpec] = []
    seen: set[tuple[tuple[str, float], ...]] = set()
    for intervention in interventions:
        if not intervention or intervention in seen:
            continue
        world_specs.append(
            _CtfWorldSpec(
                key=f"w{len(world_specs) + 1}",
                intervention=intervention,
            )
        )
        seen.add(intervention)
    return tuple(world_specs)


def _normalize_counterfactual_query(query: CtfQuery) -> _NormalizedCtfQuery:
    target_intervention = _sorted_assignments(query.intervention)
    reference_intervention = _sorted_assignments(query.reference_intervention)
    evidence = _sorted_assignments(query.evidence)
    conditioning = tuple(sorted(dict.fromkeys(query.conditioning)))
    kind = query.kind.lower()
    outcome_worlds: tuple[tuple[tuple[str, float], ...], ...] = (target_intervention,)
    world_interventions: tuple[tuple[tuple[str, float], ...], ...] = (target_intervention,)
    joint_worlds = False

    if kind == "pn":
        factual = reference_intervention or target_intervention
        alternate = _infer_reference_intervention(factual)
        if alternate:
            target_intervention = alternate
        outcome_worlds = (target_intervention,)
        world_interventions = (target_intervention, factual)
        evidence_dict = dict(evidence)
        for name, value in factual:
            evidence_dict.setdefault(name, value)
        evidence = _sorted_assignments(evidence_dict)
    elif kind == "ps":
        factual = reference_intervention or _infer_reference_intervention(target_intervention)
        outcome_worlds = (target_intervention,)
        world_interventions = (target_intervention, factual)
        if factual:
            evidence_dict = dict(evidence)
            for name, value in factual:
                evidence_dict.setdefault(name, value)
            evidence = _sorted_assignments(evidence_dict)
    elif kind == "pns":
        reference = reference_intervention or _infer_reference_intervention(target_intervention)
        if reference:
            outcome_worlds = (target_intervention, reference)
            world_interventions = (target_intervention, reference)
            joint_worlds = True
        else:
            outcome_worlds = (target_intervention,)
            world_interventions = (target_intervention,)
    elif kind == "ett" and reference_intervention:
        outcome_worlds = (target_intervention,)
        world_interventions = (target_intervention, reference_intervention)

    unique_worlds = _make_world_specs(world_interventions)

    return _NormalizedCtfQuery(
        target_intervention=target_intervention,
        evidence=evidence,
        conditioning=conditioning,
        worlds=unique_worlds,
        outcome_worlds=outcome_worlds,
        joint_worlds=joint_worlds,
    )


def _ctf_world_lookup(
    normalized_query: _NormalizedCtfQuery,
) -> dict[tuple[tuple[str, float], ...], str]:
    return {world.intervention: world.key for world in normalized_query.worlds}


def _ctf_node_name(
    variable: str,
    intervention: tuple[tuple[str, float], ...],
    world_lookup: dict[tuple[tuple[str, float], ...], str],
) -> str:
    if not intervention:
        return variable
    return f"{variable}__{world_lookup[intervention]}"


def _ctf_node_base(node: str) -> str:
    return node.split("__", 1)[0]


def _ctf_node_intervention(
    node: str,
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> tuple[tuple[str, float], ...]:
    return intervention_by_node.get(node, ())


def _ctf_self_intervention_value(
    node: str,
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> float | None:
    base = _ctf_node_base(node)
    for variable, value in _ctf_node_intervention(node, intervention_by_node):
        if variable == base:
            return float(value)
    return None


def _ctf_is_not_self_intervened(
    node: str,
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> bool:
    return _ctf_self_intervention_value(node, intervention_by_node) is None


def _ctf_bidirected_neighbors(graph: CausalGraphModel, node: str) -> set[str]:
    return {
        edge.dst if edge.src == node else edge.src
        for edge in graph.edges
        if edge.mark_src is EdgeMark.ARROW
        and edge.mark_dst is EdgeMark.ARROW
        and node in {edge.src, edge.dst}
    }


def _ctf_parents(graph: CausalGraphModel, node: str) -> set[str]:
    return {
        edge.src
        for edge in graph.edges
        if edge.mark_src is EdgeMark.TAIL
        and edge.mark_dst is EdgeMark.ARROW
        and edge.dst == node
    }


def _ctf_sort_key(
    node: str,
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> tuple[str, tuple[tuple[str, float], ...], str]:
    return (_ctf_node_base(node), _ctf_node_intervention(node, intervention_by_node), node)


def _ctf_has_same_confounders(graph: CausalGraphModel, left: str, right: str) -> bool:
    left_neighbors = _ctf_bidirected_neighbors(graph, left)
    right_neighbors = _ctf_bidirected_neighbors(graph, right)
    return right in left_neighbors or (not left_neighbors and not right_neighbors)


def _ctf_nodes_have_same_domain(
    graph: CausalGraphModel,
    left: str,
    right: str,
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> bool:
    if not _ctf_has_same_confounders(graph, left, right):
        return False
    if _ctf_node_base(left) != _ctf_node_base(right):
        return False
    left_value = _ctf_self_intervention_value(left, intervention_by_node)
    right_value = _ctf_self_intervention_value(right, intervention_by_node)
    if left_value is None and right_value is None:
        return True
    if left_value is None or right_value is None:
        return False
    return left_value == right_value


def _ctf_nodes_attain_same_value(
    graph: CausalGraphModel,
    left: str,
    right: str,
    event_assignments: dict[str, float],
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> bool:
    if left == right:
        return True
    if not _ctf_has_same_confounders(graph, left, right):
        return False
    if _ctf_node_base(left) != _ctf_node_base(right):
        return False
    if left in event_assignments and right in event_assignments:
        return event_assignments[left] == event_assignments[right]
    if left in event_assignments:
        right_value = _ctf_self_intervention_value(right, intervention_by_node)
        return right_value is not None and event_assignments[left] == right_value
    if right in event_assignments:
        left_value = _ctf_self_intervention_value(left, intervention_by_node)
        return left_value is not None and event_assignments[right] == left_value
    left_value = _ctf_self_intervention_value(left, intervention_by_node)
    right_value = _ctf_self_intervention_value(right, intervention_by_node)
    if left_value is not None or right_value is not None:
        return left_value is not None and right_value is not None and left_value == right_value
    return True


def _ctf_parents_attain_same_values(
    graph: CausalGraphModel,
    left: str,
    right: str,
    event_assignments: dict[str, float],
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> bool:
    if not _ctf_has_same_confounders(graph, left, right):
        return False
    parents_left = _ctf_parents(graph, left)
    parents_right = _ctf_parents(graph, right)
    if parents_left == parents_right:
        return True
    remainder_left = sorted(
        parents_left - parents_right,
        key=lambda node: _ctf_sort_key(node, intervention_by_node),
    )
    remainder_right = sorted(
        parents_right - parents_left,
        key=lambda node: _ctf_sort_key(node, intervention_by_node),
    )
    if len(remainder_left) != len(remainder_right):
        return False
    return all(
        _ctf_nodes_attain_same_value(
            graph,
            left_parent,
            right_parent,
            event_assignments,
            intervention_by_node,
        )
        for left_parent, right_parent in zip(remainder_left, remainder_right)
    )


def _ctf_lemma24_holds(
    graph: CausalGraphModel,
    left: str,
    right: str,
    event_assignments: dict[str, float],
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> bool:
    return (
        _ctf_node_base(left) == _ctf_node_base(right)
        and _ctf_is_not_self_intervened(left, intervention_by_node)
        == _ctf_is_not_self_intervened(right, intervention_by_node)
        and _ctf_parents_attain_same_values(
            graph,
            left,
            right,
            event_assignments,
            intervention_by_node,
        )
        and _ctf_nodes_have_same_domain(
            graph,
            left,
            right,
            intervention_by_node,
        )
    )


def _ctf_choose_merge_target(left: str, right: str) -> tuple[str, str]:
    if "__" not in left and "__" in right:
        return left, right
    if "__" not in right and "__" in left:
        return right, left
    return tuple(sorted((left, right)))  # type: ignore[return-value]


def _build_counterfactual_graph(
    graph: CausalGraphModel,
    normalized_query: _NormalizedCtfQuery,
) -> tuple[CausalGraphModel, dict[str, tuple[tuple[str, float], ...]]]:
    nodes = list(graph.nodes)
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]] = {
        node: () for node in graph.nodes
    }
    for world in normalized_query.worlds:
        for node in graph.nodes:
            world_node = f"{node}__{world.key}"
            nodes.append(world_node)
            intervention_by_node[world_node] = world.intervention

    seen_edges: set[tuple[str, str, EdgeMark, EdgeMark]] = set()
    edges: list[Any] = []

    def _add_edge(
        src: str,
        dst: str,
        mark_src: EdgeMark,
        mark_dst: EdgeMark,
    ) -> None:
        key = (src, dst, mark_src, mark_dst)
        if key in seen_edges or src == dst:
            return
        seen_edges.add(key)
        edges.append(
            CausalEdge(
                src=src,
                dst=dst,
                mark_src=mark_src,
                mark_dst=mark_dst,
            )
        )

    for edge in graph.edges:
        if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW:
            _add_edge(edge.src, edge.dst, EdgeMark.TAIL, EdgeMark.ARROW)
            for world in normalized_query.worlds:
                if edge.dst in dict(world.intervention):
                    continue
                _add_edge(f"{edge.src}__{world.key}", f"{edge.dst}__{world.key}", EdgeMark.TAIL, EdgeMark.ARROW)
        elif edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW:
            _add_edge(edge.src, edge.dst, EdgeMark.ARROW, EdgeMark.ARROW)
            for world in normalized_query.worlds:
                if edge.src in dict(world.intervention) or edge.dst in dict(world.intervention):
                    continue
                _add_edge(f"{edge.src}__{world.key}", f"{edge.dst}__{world.key}", EdgeMark.ARROW, EdgeMark.ARROW)

    base_bidirected_pairs = [
        tuple(sorted((edge.src, edge.dst)))
        for edge in graph.edges
        if edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW
    ]

    for world in normalized_query.worlds:
        intervention_vars = {name for name, _ in world.intervention}
        for node in graph.nodes:
            if node in intervention_vars:
                continue
            _add_edge(node, f"{node}__{world.key}", EdgeMark.ARROW, EdgeMark.ARROW)
        for left, right in base_bidirected_pairs:
            if right not in intervention_vars:
                _add_edge(left, f"{right}__{world.key}", EdgeMark.ARROW, EdgeMark.ARROW)
            if left not in intervention_vars:
                _add_edge(right, f"{left}__{world.key}", EdgeMark.ARROW, EdgeMark.ARROW)

    for idx, left_world in enumerate(normalized_query.worlds):
        left_interventions = {name for name, _ in left_world.intervention}
        for right_world in normalized_query.worlds[idx + 1 :]:
            right_interventions = {name for name, _ in right_world.intervention}
            for node in graph.nodes:
                if node in left_interventions or node in right_interventions:
                    continue
                _add_edge(
                    f"{node}__{left_world.key}",
                    f"{node}__{right_world.key}",
                    EdgeMark.ARROW,
                    EdgeMark.ARROW,
                )
            for left, right in base_bidirected_pairs:
                if left not in left_interventions and right not in right_interventions:
                    _add_edge(
                        f"{left}__{left_world.key}",
                        f"{right}__{right_world.key}",
                        EdgeMark.ARROW,
                        EdgeMark.ARROW,
                    )
                if right not in left_interventions and left not in right_interventions:
                    _add_edge(
                        f"{right}__{left_world.key}",
                        f"{left}__{right_world.key}",
                        EdgeMark.ARROW,
                        EdgeMark.ARROW,
                    )

    cf_graph = CausalGraphModel.model_construct(
        schema_version=graph.schema_version,
        graph_type=GraphType.ADMG,
        nodes=nodes,
        edges=edges,
        discovery_method=graph.discovery_method,
        skg_version_id=graph.skg_version_id,
        pag_identification_policy=graph.pag_identification_policy,
        id_confidence_under_pag=graph.id_confidence_under_pag,
        metadata={
            **dict(graph.metadata),
            "derived_view": "counterfactual_graph",
            "counterfactual_worlds": {
                world.key: dict(world.intervention)
                for world in normalized_query.worlds
            },
        },
    )
    return cf_graph, intervention_by_node


def _merge_counterfactual_nodes(
    graph: CausalGraphModel,
    *,
    keep: str,
    drop: str,
) -> CausalGraphModel:
    new_nodes = [node for node in graph.nodes if node != drop]
    seen: set[tuple[str, str, EdgeMark, EdgeMark, int | None]] = set()
    new_edges = []
    for edge in graph.edges:
        src = keep if edge.src == drop else edge.src
        dst = keep if edge.dst == drop else edge.dst
        if src == dst:
            continue
        key = (src, dst, edge.mark_src, edge.mark_dst, edge.lag)
        if key in seen:
            continue
        seen.add(key)
        new_edges.append(edge.model_copy(update={"src": src, "dst": dst}))
    return CausalGraphModel.model_construct(
        schema_version=graph.schema_version,
        graph_type=graph.graph_type,
        nodes=new_nodes,
        edges=new_edges,
        discovery_method=graph.discovery_method,
        skg_version_id=graph.skg_version_id,
        pag_identification_policy=graph.pag_identification_policy,
        id_confidence_under_pag=graph.id_confidence_under_pag,
        metadata=dict(graph.metadata),
    )


def _reduce_counterfactual_graph(
    *,
    graph: CausalGraphModel,
    base_graph: CausalGraphModel,
    focus_nodes: set[str],
    event_assignments: dict[str, float],
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> tuple[CausalGraphModel, set[str], dict[str, float], bool]:
    worlds = sorted(
        {
            intervention
            for intervention in intervention_by_node.values()
            if intervention
        }
    )
    world_lookup = {intervention: idx for idx, intervention in enumerate(worlds)}

    def _copy_name(node: str, intervention: tuple[tuple[str, float], ...]) -> str:
        if not intervention:
            return node
        return f"{node}__w{world_lookup[intervention] + 1}"

    current_graph = graph
    inconsistent = False

    for node in topological_order(base_graph):
        for intervention in worlds:
            copy_node = _copy_name(node, intervention)
            if node in current_graph.nodes and copy_node in current_graph.nodes and _ctf_lemma24_holds(
                current_graph,
                node,
                copy_node,
                event_assignments,
                intervention_by_node,
            ):
                keep, drop = _ctf_choose_merge_target(node, copy_node)
                if (
                    keep in event_assignments
                    and drop in event_assignments
                    and event_assignments[keep] != event_assignments[drop]
                ):
                    inconsistent = True
                    break
                current_graph = _merge_counterfactual_nodes(current_graph, keep=keep, drop=drop)
                if drop in focus_nodes:
                    focus_nodes.discard(drop)
                    focus_nodes.add(keep)
                if drop in event_assignments:
                    event_assignments[keep] = event_assignments[drop]
                    del event_assignments[drop]
        if inconsistent:
            break
        for left_idx, left_intervention in enumerate(worlds):
            left_node = _copy_name(node, left_intervention)
            for right_intervention in worlds[left_idx + 1 :]:
                right_node = _copy_name(node, right_intervention)
                if (
                    left_node in current_graph.nodes
                    and right_node in current_graph.nodes
                    and _ctf_lemma24_holds(
                        current_graph,
                        left_node,
                        right_node,
                        event_assignments,
                        intervention_by_node,
                    )
                ):
                    keep, drop = _ctf_choose_merge_target(left_node, right_node)
                    if (
                        keep in event_assignments
                        and drop in event_assignments
                        and event_assignments[keep] != event_assignments[drop]
                    ):
                        inconsistent = True
                        break
                    current_graph = _merge_counterfactual_nodes(current_graph, keep=keep, drop=drop)
                    if drop in focus_nodes:
                        focus_nodes.discard(drop)
                        focus_nodes.add(keep)
                    if drop in event_assignments:
                        event_assignments[keep] = event_assignments[drop]
                        del event_assignments[drop]
            if inconsistent:
                break
        if inconsistent:
            break

    mentioned = frozenset(focus_nodes | set(event_assignments))
    if mentioned:
        an_mentioned = ancestors(current_graph, mentioned) | mentioned
        current_graph = induced_subgraph(current_graph, an_mentioned)
        focus_nodes = {node for node in focus_nodes if node in an_mentioned}
        event_assignments = {
            node: value
            for node, value in event_assignments.items()
            if node in an_mentioned
        }
    return current_graph, focus_nodes, event_assignments, inconsistent


def _counterfactual_conflicts(
    graph: CausalGraphModel,
    event_assignments: dict[str, float],
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> list[tuple[str, float, float]]:
    conflicts: list[tuple[str, float, float]] = []
    for node in graph.nodes:
        if node not in event_assignments:
            continue
        self_value = _ctf_self_intervention_value(node, intervention_by_node)
        if self_value is not None and self_value != event_assignments[node]:
            conflicts.append((_ctf_node_base(node), self_value, event_assignments[node]))
    return conflicts


def _ctf_c_components(
    graph: CausalGraphModel,
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> list[frozenset[str]]:
    non_self_nodes = frozenset(
        node for node in graph.nodes if _ctf_is_not_self_intervened(node, intervention_by_node)
    )
    if not non_self_nodes:
        return []
    return c_components(induced_subgraph(graph, non_self_nodes))


def _ctf_markov_pillow(
    graph: CausalGraphModel,
    district: frozenset[str],
) -> frozenset[str]:
    district_set = set(district)
    parents = {
        edge.src
        for edge in graph.edges
        if edge.mark_src is EdgeMark.TAIL
        and edge.mark_dst is EdgeMark.ARROW
        and edge.dst in district_set
        and edge.src not in district_set
    }
    return frozenset(parents)


def _ctf_reduction_treatment(
    graph: CausalGraphModel,
    district: frozenset[str],
    intervention_by_node: dict[str, tuple[tuple[str, float], ...]],
) -> frozenset[str]:
    treatment: set[str] = set()
    for node in district:
        for variable, _ in intervention_by_node.get(node, ()):
            treatment.add(variable)
    for pillow_node in _ctf_markov_pillow(graph, district):
        treatment.add(_ctf_node_base(pillow_node))
    return frozenset(treatment)


def _format_counterfactual_query_str(
    outcome: str,
    intervention: tuple[tuple[str, float], ...],
    evidence: tuple[tuple[str, float], ...],
    conditioning: tuple[str, ...],
) -> str:
    head = _format_counterfactual_head(outcome, intervention)
    rhs_terms = [f"{name}={_format_assignment(value)}" for name, value in evidence] + list(conditioning)
    if rhs_terms:
        return f"P({head} | {', '.join(rhs_terms)})"
    return f"P({head})"


def _format_counterfactual_head(
    outcome: str,
    intervention: tuple[tuple[str, float], ...],
) -> str:
    intervention_str = ", ".join(
        f"{name}={_format_assignment(value)}" for name, value in intervention
    )
    if intervention_str:
        return f"{outcome}_{{{intervention_str}}}"
    return outcome


def _format_cross_world_query_str(
    outcome: str,
    interventions: tuple[tuple[tuple[str, float], ...], ...],
    evidence: tuple[tuple[str, float], ...],
    conditioning: tuple[str, ...],
) -> str:
    head = ", ".join(
        _format_counterfactual_head(outcome, intervention)
        for intervention in interventions
    )
    rhs_terms = [f"{name}={_format_assignment(value)}" for name, value in evidence] + list(conditioning)
    if rhs_terms:
        return f"P({head} | {', '.join(rhs_terms)})"
    return f"P({head})"


def _normalized_counterfactual_query_str(
    outcome: str,
    normalized_query: _NormalizedCtfQuery,
) -> str:
    if len(normalized_query.outcome_worlds) > 1:
        return _format_cross_world_query_str(
            outcome,
            normalized_query.outcome_worlds,
            normalized_query.evidence,
            normalized_query.conditioning,
        )
    return _format_counterfactual_query_str(
        outcome,
        normalized_query.target_intervention,
        normalized_query.evidence,
        normalized_query.conditioning,
    )


def _counterfactual_ast(
    *,
    query: CtfQuery,
    normalized_query: _NormalizedCtfQuery,
    identification_method: str,
) -> EstimandAST:
    evidence_vars = tuple(name for name, _ in normalized_query.evidence)
    conditioning = tuple(sorted({*normalized_query.conditioning, *evidence_vars}))
    query_str = _normalized_counterfactual_query_str(query.outcome, normalized_query)
    world_index_lookup = {
        world.intervention: idx for idx, world in enumerate(normalized_query.worlds)
    }
    cf_node = CounterfactualNode(
        variable=query.outcome,
        intervention=dict(normalized_query.target_intervention),
        conditioning=conditioning,
        world_index=world_index_lookup.get(normalized_query.target_intervention, 0),
        domain=DistributionDomain.SOURCE,
    )
    if query.kind.lower() == "nested":
        root = NestedCounterfactualNode(
            outer_variable=query.outcome,
            outer_intervention=dict(normalized_query.target_intervention),
            inner_counterfactual=cf_node,
            world_indices=(0,),
            domain=DistributionDomain.SOURCE,
        )
    elif len(normalized_query.outcome_worlds) > 1:
        root = CrossWorldNode(
            worlds=tuple(
                CounterfactualNode(
                    variable=query.outcome,
                    intervention=dict(outcome_world),
                    conditioning=conditioning,
                    world_index=world_index_lookup.get(outcome_world, idx),
                    domain=DistributionDomain.SOURCE,
                )
                for idx, outcome_world in enumerate(normalized_query.outcome_worlds)
            ),
            joint=normalized_query.joint_worlds,
        )
    else:
        root = cf_node
    all_vars = tuple(
        sorted(
            {
                query.outcome,
                *(name for outcome_world in normalized_query.outcome_worlds for name, _ in outcome_world),
                *(name for name, _ in normalized_query.evidence),
                *normalized_query.conditioning,
            }
        )
    )
    treatment_vars = tuple(
        sorted(
            {
                name
                for outcome_world in normalized_query.outcome_worlds
                for name, _ in outcome_world
            }
        )
    )
    treatment = (
        ",".join(treatment_vars)
        if len(treatment_vars) > 1
        else (treatment_vars[0] if treatment_vars else "counterfactual")
    )
    return EstimandAST(
        query_str=query_str,
        root=root,
        treatment=treatment,
        outcome=query.outcome,
        all_variables=all_vars,
        identification_method=identification_method,
    )


def _counterfactual_negative_certificate(
    *,
    query: CtfQuery,
    treatment: frozenset[str],
    graph: CausalGraphModel,
    description: str,
) -> HedgeCertificate:
    graph_nodes = frozenset(graph.nodes)
    return HedgeCertificate(
        treatment=treatment,
        outcome=frozenset({query.outcome}),
        hedge_forest=graph_nodes,
        hedge_root=graph_nodes,
        c_component_witness=graph_nodes,
        description=description,
    )


def id_star_algorithm(
    counterfactual_query: CtfQuery,
    graph: CausalGraphModel,
    _depth: int = 0,
    _trace: list[str] | None = None,
) -> IdentificationResult:
    """ID* counterfactual identification via G* reduction + Layer-2 subproblems."""
    trace = list(_trace or [])
    normalized_query = _normalize_counterfactual_query(counterfactual_query)
    treatment_vars = frozenset(name for name, _ in normalized_query.target_intervention)
    trace.append(
        f"[ID* depth={_depth}] kind={counterfactual_query.kind}, "
        f"outcome={counterfactual_query.outcome}, "
        f"target_intervention={list(normalized_query.target_intervention)}, "
        f"worlds={len(normalized_query.worlds)}"
    )
    proof_steps: list[ProofStep] = [
        ProofStep(
            rule_name="ID_STAR_STEP1",
            antecedent_vars=tuple(sorted(treatment_vars)),
            consequent_vars=(counterfactual_query.outcome,),
            applied_to_graph_state=(
                "Constructed G* from compact parallel worlds with Lemma-24/25 style node merging."
            ),
            depth=_depth,
        )
    ]

    cf_graph, intervention_by_node = _build_counterfactual_graph(graph, normalized_query)
    world_lookup = _ctf_world_lookup(normalized_query)
    focus_nodes = {
        _ctf_node_name(
            counterfactual_query.outcome,
            outcome_world,
            world_lookup,
        )
        for outcome_world in normalized_query.outcome_worlds
    }
    focus_nodes.update(normalized_query.conditioning)
    event_assignments = {
        _ctf_node_name(name, (), world_lookup): value
        for name, value in normalized_query.evidence
    }
    trace.append(
        f"[ID* depth={_depth}] raw G* has {len(cf_graph.nodes)} nodes and {len(cf_graph.edges)} edges"
    )
    cf_graph, focus_nodes, event_assignments, inconsistent = _reduce_counterfactual_graph(
        graph=cf_graph,
        base_graph=graph,
        focus_nodes=focus_nodes,
        event_assignments=event_assignments,
        intervention_by_node=intervention_by_node,
    )
    trace.append(
        f"[ID* depth={_depth}] reduced G* has {len(cf_graph.nodes)} nodes and {len(cf_graph.edges)} edges"
    )
    if inconsistent:
        cert = _counterfactual_negative_certificate(
            query=counterfactual_query,
            treatment=treatment_vars,
            graph=cf_graph,
            description="Counterfactual event became inconsistent during Lemma-24/25 merging.",
        )
        proof_steps.append(
            ProofStep(
                rule_name="ID_STAR_STEP5",
                antecedent_vars=tuple(sorted(treatment_vars)),
                consequent_vars=(counterfactual_query.outcome,),
                applied_to_graph_state="Merged counterfactual graph became inconsistent.",
                depth=_depth,
            )
        )
        return IdentificationResult(
            status=IdentificationStatus.HEDGE_FOUND,
            estimand_ast=None,
            hedge_certificate=cert,
            trace=[*trace, f"[ID* depth={_depth}] inconsistent after counterfactual graph merge"],
            required_distributions=[],
            algorithm_version="id_star_v2",
            proof_steps=proof_steps,
            query_str=_normalized_counterfactual_query_str(
                counterfactual_query.outcome,
                normalized_query,
            ),
        )

    districts = _ctf_c_components(cf_graph, intervention_by_node)
    proof_steps.append(
        ProofStep(
            rule_name="ID_STAR_STEP2",
            antecedent_vars=tuple(sorted(treatment_vars)),
            consequent_vars=(counterfactual_query.outcome,),
            applied_to_graph_state=(
                f"Partitioned G* into c-components: {[sorted(component) for component in districts]}"
            ),
            depth=_depth,
        )
    )
    if not districts:
        districts = [frozenset(focus_nodes)]

    relevant_districts = [district for district in districts if district & focus_nodes]
    if not relevant_districts:
        relevant_districts = list(districts)

    conflicts = _counterfactual_conflicts(cf_graph, event_assignments, intervention_by_node)
    if conflicts:
        cert = _counterfactual_negative_certificate(
            query=counterfactual_query,
            treatment=treatment_vars,
            graph=cf_graph,
            description=(
                "Counterfactual graph contains intervention/evidence conflicts: "
                + ", ".join(
                    f"{name}: do={_format_assignment(do_value)} vs ev={_format_assignment(ev_value)}"
                    for name, do_value, ev_value in conflicts
                )
            ),
        )
        proof_steps.append(
            ProofStep(
                rule_name="ID_STAR_STEP5",
                antecedent_vars=tuple(sorted(treatment_vars)),
                consequent_vars=(counterfactual_query.outcome,),
                applied_to_graph_state="Counterfactual graph contains intervention/evidence conflicts.",
                depth=_depth,
            )
        )
        return IdentificationResult(
            status=IdentificationStatus.HEDGE_FOUND,
            estimand_ast=None,
            hedge_certificate=cert,
            trace=[*trace, f"[ID* depth={_depth}] conflicts in G*: {conflicts}"],
            required_distributions=[],
            algorithm_version="id_star_v2",
            proof_steps=proof_steps,
            query_str=_normalized_counterfactual_query_str(
                counterfactual_query.outcome,
                normalized_query,
            ),
        )

    if len(relevant_districts) > 1:
        trace.append(
            f"[ID* depth={_depth}] G* disconnected into relevant districts "
            f"{[sorted(component) for component in relevant_districts]}"
        )
        proof_steps.append(
            ProofStep(
                rule_name="ID_STAR_STEP4",
                antecedent_vars=tuple(sorted(treatment_vars)),
                consequent_vars=(counterfactual_query.outcome,),
                applied_to_graph_state="Applied parallel-world factorisation across disconnected districts.",
                depth=_depth,
            )
        )

    required_distributions: list[DistributionRef] = []
    reduced_results: list[IdentificationResult] = []
    for district in relevant_districts:
        base_outcomes = frozenset(sorted({_ctf_node_base(node) for node in district}))
        district_treatment = _ctf_reduction_treatment(
            cf_graph,
            district,
            intervention_by_node,
        )
        trace.append(
            f"[ID* depth={_depth}] Layer-2 reduction on district "
            f"Y={sorted(base_outcomes)}, X={sorted(district_treatment)}"
        )
        base_result = id_algorithm(
            treatment=district_treatment,
            outcome=base_outcomes,
            graph=graph,
            _depth=_depth + 1,
            _trace=trace,
        )
        reduced_results.append(base_result)
        proof_steps.append(
            ProofStep(
                rule_name="ID_STAR_STEP3",
                antecedent_vars=tuple(sorted(district_treatment)),
                consequent_vars=tuple(sorted(base_outcomes)),
                applied_to_graph_state=(
                    f"Reduced district {sorted(district)} to Layer-2 ID with status={base_result.status.value}"
                ),
                depth=_depth,
            )
        )
        if base_result.status is not IdentificationStatus.IDENTIFIED:
            return IdentificationResult(
                status=base_result.status,
                estimand_ast=None,
                hedge_certificate=base_result.hedge_certificate,
                trace=[*trace, *base_result.trace, f"[ID* depth={_depth}] district reduction failed"],
                required_distributions=base_result.required_distributions,
                algorithm_version="id_star_v2",
                proof_steps=[*proof_steps, *base_result.proof_steps],
                query_str=_normalized_counterfactual_query_str(
                    counterfactual_query.outcome,
                    normalized_query,
                ),
            )
        required_distributions.extend(base_result.required_distributions)

    ast = _counterfactual_ast(
        query=counterfactual_query,
        normalized_query=normalized_query,
        identification_method=f"id_star_v2|kind={counterfactual_query.kind}",
    )
    proof_steps.append(
        ProofStep(
            rule_name="ID_STAR_STEP5",
            antecedent_vars=tuple(sorted(treatment_vars)),
            consequent_vars=(counterfactual_query.outcome,),
            applied_to_graph_state=(
                "Counterfactual query reduced to identified Layer-2 subproblems."
            ),
            depth=_depth,
        )
    )
    trace.append(f"[ID* depth={_depth}] identified {counterfactual_query.kind}")
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=ast,
        hedge_certificate=None,
        trace=[*trace, *(step for result in reduced_results for step in result.trace)],
        required_distributions=required_distributions,
        algorithm_version="id_star_v2",
        proof_steps=[*proof_steps, *(step for result in reduced_results for step in result.proof_steps)],
        query_str=ast.query_str,
    )


def idc_star_algorithm(
    counterfactual_query: CtfQuery,
    graph: CausalGraphModel,
    _depth: int = 0,
    _trace: list[str] | None = None,
) -> IdentificationResult:
    """IDC* with counterfactual Rule-2 promotion before the ratio reduction."""
    trace = list(_trace or [])
    trace.append(f"[IDC* depth={_depth}] start")

    if not counterfactual_query.evidence:
        return dataclasses.replace(
            id_star_algorithm(counterfactual_query, graph, _depth=_depth + 1, _trace=trace),
            algorithm_version="idc_star_v2",
            trace=[*trace, "[IDC* depth=0] no evidence supplied; identical to ID*"],
        )

    normalized_query = _normalize_counterfactual_query(counterfactual_query)
    cf_graph, intervention_by_node = _build_counterfactual_graph(graph, normalized_query)
    world_lookup = _ctf_world_lookup(normalized_query)
    target_node = _ctf_node_name(
        counterfactual_query.outcome,
        normalized_query.target_intervention,
        world_lookup,
    )
    promoted_query = counterfactual_query
    promoted_intervention_map = dict(promoted_query.intervention)
    for condition_name, condition_value in normalized_query.evidence:
        condition_node = _ctf_node_name(condition_name, (), world_lookup)
        conditioned_nodes = frozenset(
            node
            for node in cf_graph.nodes
            if not _ctf_is_not_self_intervened(node, intervention_by_node)
        )
        modified_graph = CausalGraphModel.model_construct(
            schema_version=cf_graph.schema_version,
            graph_type=cf_graph.graph_type,
            nodes=list(cf_graph.nodes),
            edges=[
                edge
                for edge in cf_graph.edges
                if not (
                    edge.mark_src is EdgeMark.TAIL
                    and edge.mark_dst is EdgeMark.ARROW
                    and edge.src == condition_node
                )
            ],
            discovery_method=cf_graph.discovery_method,
            skg_version_id=cf_graph.skg_version_id,
            pag_identification_policy=cf_graph.pag_identification_policy,
            id_confidence_under_pag=cf_graph.id_confidence_under_pag,
            metadata=dict(cf_graph.metadata),
        )
        if (
            condition_node in modified_graph.nodes
            and target_node in modified_graph.nodes
            and condition_name not in promoted_intervention_map
            and m_separation(
                modified_graph,
                frozenset({target_node}),
                frozenset({condition_node}),
                conditioned_nodes,
            )
        ):
            promoted_map = dict(promoted_query.intervention)
            promoted_map[condition_name] = condition_value
            promoted_query = dataclasses.replace(
                promoted_query,
                intervention=_sorted_assignments(promoted_map),
                evidence=tuple(
                    (name, value)
                    for name, value in promoted_query.evidence
                    if name != condition_name
                ),
            )
            trace.append(
                f"[IDC* depth={_depth}] Rule-2 promoted {condition_name}={_format_assignment(condition_value)} to intervention"
            )
            return idc_star_algorithm(
                promoted_query,
                graph,
                _depth=_depth + 1,
                _trace=trace,
            )

    numerator_query = promoted_query
    conflicting_treatment_evidence = {
        name
        for name, value in promoted_query.evidence
        if name in promoted_intervention_map
        and float(promoted_intervention_map[name]) != float(value)
    }
    if conflicting_treatment_evidence:
        trace.append(
            f"[IDC* depth={_depth}] preserving conflicting treatment evidence in the conditioning event: "
            f"{sorted(conflicting_treatment_evidence)}"
        )
        numerator_query = dataclasses.replace(
            promoted_query,
            evidence=tuple(
                (name, value)
                for name, value in promoted_query.evidence
                if name not in conflicting_treatment_evidence
            ),
        )

    numerator = id_star_algorithm(numerator_query, graph, _depth=_depth + 1, _trace=trace)
    if numerator.status is not IdentificationStatus.IDENTIFIED:
        return numerator

    evidence_vars = tuple(sorted(name for name, _ in promoted_query.evidence))
    if len(promoted_query.evidence) == 1:
        evidence_var, _ = promoted_query.evidence[0]
        denominator_query = CtfQuery(
            outcome=evidence_var,
            intervention=(),
            conditioning=promoted_query.conditioning,
            kind="generic",
        )
        denominator_result = id_star_algorithm(
            denominator_query,
            graph,
            _depth=_depth + 1,
            _trace=list(trace),
        )
        if denominator_result.status is not IdentificationStatus.IDENTIFIED:
            return denominator_result
        assert denominator_result.estimand_ast is not None
        denominator_root = denominator_result.estimand_ast.root
        denominator_all_vars = denominator_result.estimand_ast.all_variables
    else:
        denominator_root = DistributionRef(
            domain=DistributionDomain.SOURCE,
            variables=evidence_vars,
            intervention_set=(),
            conditioning=tuple(sorted(promoted_query.conditioning)),
        )
        denominator_all_vars = tuple(sorted({*evidence_vars, *promoted_query.conditioning}))

    assert numerator.estimand_ast is not None
    ratio_ast = EstimandAST(
        query_str=_format_counterfactual_query_str(
            counterfactual_query.outcome,
            _normalize_counterfactual_query(promoted_query).target_intervention,
            _sorted_assignments(promoted_query.evidence),
            tuple(sorted(promoted_query.conditioning)),
        ),
        root=RatioNode(
            numerator=numerator.estimand_ast.root,
            denominator=denominator_root,
        ),
        treatment=numerator.estimand_ast.treatment,
        outcome=numerator.estimand_ast.outcome,
        all_variables=tuple(sorted({*numerator.estimand_ast.all_variables, *denominator_all_vars})),
        identification_method="idc_star_v2",
    )
    proof_steps = [
        ProofStep(
            rule_name="IDC_STAR_RATIO",
            antecedent_vars=evidence_vars,
            consequent_vars=(counterfactual_query.outcome,),
            applied_to_graph_state="Constructed IDC* after Rule-2 promotion and counterfactual ratio reduction.",
            depth=_depth,
        ),
    ]
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=ratio_ast,
        hedge_certificate=None,
        trace=[*trace, *numerator.trace, "[IDC* depth=0] identified via ratio construction"],
        required_distributions=numerator.required_distributions,
        algorithm_version="idc_star_v2",
        proof_steps=[*proof_steps, *numerator.proof_steps],
        query_str=ratio_ast.query_str,
    )


__all__ = [
    "CtfQuery",
    "HedgeCertificate",
    "IdentificationStatus",
    "IdentificationResult",
    "ProofStep",
    "RequiredDataSpec",
    "SourceDomain",
    "id_algorithm",
    "idc_algorithm",
    "tr_algorithm",
    "id_with_oracle_fallback",
    "z_id_algorithm",
    "mz_id_algorithm",
    # Phase-5 additions
    "sid_algorithm",
    "conditional_intervention_id",
    "dynamic_intervention_id",
    "joint_id_algorithm",
    "idc_star_algorithm",
    "id_star_algorithm",
    "multi_outcome_id",
]
