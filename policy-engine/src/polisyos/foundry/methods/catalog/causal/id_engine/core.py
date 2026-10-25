"""Bounded native Shpitser-Pearl ID with explicit optional oracle fallback.

Implements supported native ID branches plus the IDC extension for conditional
interventional distributions and the TR (Transportability) wrapper. Native Step
6 returns ORACLE_NEEDED when recursive Q[S] input-kernel semantics are not
represented. Native ID also requires available_vars to equal the full graph-node
set; this module does not infer latent projections or marginalize omitted graph
mechanisms. Public ID/IDC/TR/fallback entrypoints admit treatment, outcome,
and conditioning roles against actual graph nodes before shortcuts; empty
treatment and conditioning sets are supported, while outcome must be non-empty.
id_with_oracle_fallback may delegate the complete admitted query to an
explicitly selected backend and records that backend's provenance.

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
    → bounded S-admissibility cases; otherwise ORACLE_NEEDED

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
    _validate_static_admg,
    _validate_static_id_graph,
    ancestors,
    c_components,
    canonical_scalar_selection_diagram,
    descendants,
    do_operator,
    extract_bidirected_edges,
    extract_directed_edges,
    induced_subgraph,
    m_separation,
    resolve_s_node_by_adjustment,
    topological_order,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    graph_content_sha256,
)
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
) -> IdentificationResult:
    """Orient a PAG and delegate only a resolved graph to static ID.

    Policy and confidence values remain trace diagnostics. They do not create
    proof steps, select endpoint completions, or change ordinary static-ID
    results. This adapter does not identify over a PAG equivalence class.
    """
    from polisyos.foundry.methods.catalog.causal.pag_completion import apply_pag_orientation_rules
    from polisyos.ir.analytics.causal_graph import EdgeMark, GraphType, PAGIdentificationPolicy

    graph = _validate_static_admg(graph)

    policy = graph.pag_identification_policy
    _trace.append(
        f"[depth={_depth}] PAG-ID: policy={policy.value}, "
        f"X={sorted(treatment)}, Y={sorted(outcome)}"
    )

    n_circles_before = sum(
        1
        for edge in graph.edges
        if edge.mark_src is EdgeMark.CIRCLE or edge.mark_dst is EdgeMark.CIRCLE
    )
    oriented_pag, _orient_warnings = apply_pag_orientation_rules(graph)
    n_circles_after = sum(
        1
        for edge in oriented_pag.edges
        if edge.mark_src is EdgeMark.CIRCLE or edge.mark_dst is EdgeMark.CIRCLE
    )
    n_resolved = n_circles_before - n_circles_after
    if n_resolved > 0:
        _trace.append(
            f"[depth={_depth}] PAG-ID orientation pre-pass: "
            f"resolved {n_resolved} CIRCLE endpoints "
            f"({n_circles_before}→{n_circles_after} remain)"
        )

    # Static ID has no interpretation for unresolved PAG endpoints. This gate
    # precedes every policy path, so no policy can supply a completion choice.
    oriented_pag = _validate_static_admg(oriented_pag)

    if policy is PAGIdentificationPolicy.CONSERVATIVE:
        _trace.append(
            f"[depth={_depth}] PAG-ID CONSERVATIVE diagnostic: "
            "resolved graph delegated to static ID; no completion-set test performed"
        )
    elif policy is PAGIdentificationPolicy.OPTIMISTIC:
        _trace.append(
            f"[depth={_depth}] PAG-ID OPTIMISTIC diagnostic: "
            "resolved graph delegated to static ID; no endpoints committed"
        )
    elif policy is PAGIdentificationPolicy.PROBABILISTIC:
        _trace.append(
            f"[depth={_depth}] PAG-ID PROBABILISTIC diagnostic: "
            "resolved graph delegated to static ID; declared confidence is non-authoritative"
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
    _trace.append(
        f"[depth={_depth}] PAG-ID ({policy.value}): resolved static ID status={result.status.value}"
    )
    if policy is PAGIdentificationPolicy.PROBABILISTIC:
        confidence = oriented_pag.id_confidence_under_pag
        if confidence is not None:
            _trace.append(
                f"[depth={_depth}] PAG-ID PROBABILISTIC diagnostic only: "
                f"id_confidence_under_pag={confidence:.3f}"
            )
    return dataclasses.replace(result, trace=list(_trace))


# ---------------------------------------------------------------------------
# Internal hedge helper (shared by id_algorithm Step 4a and find_hedge)
# ---------------------------------------------------------------------------


def _c_forest_roots(
    graph: CausalGraphModel,
    component: frozenset[str],
) -> frozenset[str] | None:
    """Return sink roots when a bidirected component is a rooted C-forest.

    In the ID hedge criterion a C-forest is a C-component in which each
    observed vertex has at most one directed child. Its roots are the vertices
    with no directed child. A component that branches is not a C-forest.
    """
    children: dict[str, set[str]] = {node: set() for node in component}
    for source, target in extract_directed_edges(graph):
        if source in component and target in component:
            children[source].add(target)
    if any(len(node_children) > 1 for node_children in children.values()):
        return None
    return frozenset(node for node, node_children in children.items() if not node_children)


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
    comps_g = c_components(induced_subgraph(graph, V))
    if len(comps_g) != 1:
        return None

    # A hedge pair needs two rooted C-forests with shared roots that remain
    # ancestors of the outcome after intervention.
    small_roots = _c_forest_roots(graph, singleton)
    large_roots = _c_forest_roots(graph, comps_g[0])
    roots_in_do_ancestors = ancestors(do_operator(graph, treatment), outcome) & V
    if (
        small_roots is None
        or large_roots is None
        or small_roots != large_roots
        or not small_roots <= roots_in_do_ancestors
    ):
        return None

    # HEDGE detected: F = V, F' = V - X
    hedge_root = small_roots
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
    if len(mediator_candidates) != 1:
        return None

    mediator = mediator_candidates[0]
    active_directed = {
        (src, dst) for src, dst in directed if src in available_vars and dst in available_vars
    }
    active_bidirected = {pair for pair in bidirected if pair <= available_vars}
    if (
        available_vars != frozenset({x, mediator, y})
        or active_directed != {(x, mediator), (mediator, y)}
        or active_bidirected != {frozenset({x, y})}
    ):
        return None

    return mediator


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


def _native_query_admission_issue(
    *,
    treatment: object,
    outcome: object,
    conditions: object,
    graph_nodes: frozenset[str],
) -> tuple[str, str] | None:
    """Return a typed refusal unless X/Y/Z form a supported graph query.

    Empty treatment is supported as a marginal query, and empty conditions
    reduce IDC to ID. The outcome must be non-empty. Every role must be a
    frozenset of non-empty graph variable names, and treatment, outcome, and
    conditions must be pairwise disjoint. This is the set-valued form of the
    causal query validator's membership and non-self-effect rules.
    """
    role_sets = (
        ("treatment", treatment),
        ("outcome", outcome),
        ("conditions", conditions),
    )
    for role, variables in role_sets:
        if not isinstance(variables, frozenset):
            return f"{role} must be a frozenset[str] query set", "query_shape"
        if any(not isinstance(name, str) or not name for name in variables):
            return (
                f"{role} query set must contain only non-empty string names",
                "query_shape",
            )
    if not outcome:
        return "the native causal-effect query requires a non-empty outcome set", "query_shape"

    for index, (left_role, left_variables) in enumerate(role_sets):
        for right_role, right_variables in role_sets[index + 1 :]:
            overlap = left_variables & right_variables
            if overlap:
                return (
                    "query roles must be pairwise disjoint; "
                    f"{left_role}/{right_role} overlap={sorted(overlap)}",
                    "query_shape",
                )

    missing = (treatment | outcome | conditions) - graph_nodes
    if missing:
        return (
            f"query variables are absent from the actual graph: {sorted(missing)}",
            "query_identity",
        )
    return None


def _native_query_refusal_result(
    *,
    caller: str,
    reason: str,
    gate: str,
    trace: list[str] | None = None,
) -> IdentificationResult:
    """Build the typed, formula-free refusal shared by native ID/TR entry gates."""
    refusal = f"{caller}: ORACLE_NEEDED: query admission failed: {reason}"
    proof = ProofStep(
        rule_name="ORACLE",
        antecedent_vars=(),
        consequent_vars=(),
        applied_to_graph_state=f"Native query admission failed: {reason}",
        depth=0,
    )
    return IdentificationResult(
        status=IdentificationStatus.ORACLE_NEEDED,
        estimand_ast=None,
        hedge_certificate=None,
        trace=[*(trace or []), refusal],
        required_distributions=[],
        algorithm_version="native_query_admission_v1",
        proof_steps=[proof],
        metadata={
            "backend_id": caller,
            "limitation_reason": reason,
            "gate_predicates": {gate: "recomputed_false"},
        },
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
    """Run supported native ID branches and fail closed when Q[S] is unavailable.

    Parameters
    ----------
    treatment:      X — intervention set (frozenset of variable names)
    outcome:        Y — target variables
    graph:          resolved DAG or acyclic ADMG (bidirected=ARROW/ARROW)
    available_vars: V must equal all graph nodes; subsets require a separately
                    validated latent-projection graph, which this path does not build
    query sets:     non-empty outcome, disjoint treatment/outcome, both in graph.nodes
    dataset_ref:    tag for DistributionRef leaves (links to DataKnowledgeBase)
    domain:         DistributionDomain for leaf DistributionRef nodes
    _depth/_trace:  internal recursion bookkeeping

    Returns IdentificationResult with status IDENTIFIED, HEDGE_FOUND, or ORACLE_NEEDED.
    Subset profiles require a separately validated latent-projection graph.
    """
    graph = _validate_static_id_graph(graph)
    if _trace is None:
        _trace = []
    query_issue = _native_query_admission_issue(
        treatment=treatment,
        outcome=outcome,
        conditions=frozenset(),
        graph_nodes=frozenset(graph.nodes),
    )
    if query_issue is not None:
        reason, gate = query_issue
        return _native_query_refusal_result(
            caller="id_algorithm",
            reason=reason,
            gate=gate,
            trace=list(_trace),
        )
    if available_vars is None:
        available_vars = frozenset(graph.nodes)

    V = available_vars
    X = treatment
    Y = outcome

    _steps: list[ProofStep] = []

    _trace.append(f"[depth={_depth}] id_algorithm(X={sorted(X)}, Y={sorted(Y)}, V={sorted(V)})")

    # Native ID consumes the full observational kernel represented by graph.
    # A caller-supplied subset is not a latent projection: bidirected paths may
    # preserve dependence through omitted nodes even when directed ancestry does
    # not. Require an exact node-set match before every algorithmic shortcut.
    graph_node_profile = frozenset(graph.nodes)
    omitted_graph_nodes = graph_node_profile - V
    extra_available_vars = V - graph_node_profile
    if omitted_graph_nodes or extra_available_vars:
        omitted = sorted(omitted_graph_nodes)
        extra = sorted(extra_available_vars)
        _trace.append(
            f"[depth={_depth}] Native ID requires a full observed-node kernel "
            "with available_vars equal to the complete graph-node profile; "
            f"omitted graph nodes={omitted}, extra available variables={extra}. "
            "A separately validated latent-projection graph is required for a subset."
        )
        _steps.append(
            ProofStep(
                rule_name="ORACLE",
                antecedent_vars=tuple(sorted(omitted_graph_nodes | extra_available_vars)),
                consequent_vars=tuple(sorted(Y)),
                applied_to_graph_state=(
                    "Native ID accepts only the complete graph-node profile. This path "
                    "does not marginalize omitted nodes or construct a validated latent projection."
                ),
                depth=_depth,
            )
        )
        return IdentificationResult(
            status=IdentificationStatus.ORACLE_NEEDED,
            estimand_ast=None,
            hedge_certificate=None,
            trace=list(_trace),
            required_distributions=[],
            proof_steps=list(_steps),
        )

    # ------------------------------------------------------------------
    # PAG-specific branch (Malinsky & Spirtes 2017) before Step 1
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

    # Step 1: X = ∅ → the marginal distribution P(Y)
    # ------------------------------------------------------------------
    if not X:
        marginal = DistributionRef(
            domain=domain,
            variables=tuple(sorted(Y)),
            dataset_ref=dataset_ref,
        )
        _trace.append(f"[depth={_depth}] Step 1: X=∅ → marginal P({sorted(Y)}) from P(V)")
        _steps.append(
            ProofStep(
                rule_name="RULE1",
                antecedent_vars=(),
                consequent_vars=tuple(sorted(Y)),
                applied_to_graph_state=(
                    f"X=∅, marginal P({sorted(Y)}) from P(V) over V={sorted(V)}"
                ),
                depth=_depth,
            )
        )
        ast = EstimandAST(
            query_str=_query_text(treatment, outcome),
            root=marginal,
            treatment=_query_var_label(treatment),
            outcome=_query_var_label(outcome),
            all_variables=tuple(sorted(V)),
            identification_method="id_step1",
        )
        return IdentificationResult(
            status=IdentificationStatus.IDENTIFIED,
            estimand_ast=ast,
            hedge_certificate=None,
            trace=list(_trace),
            required_distributions=[marginal],
            proof_steps=list(_steps),
        )

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
        return _rebind_result_query(
            dataclasses.replace(inner, proof_steps=list(_steps) + list(inner.proof_steps)),
            treatment=X,
            outcome=Y,
        )

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
        return _rebind_result_query(
            dataclasses.replace(inner, proof_steps=list(_steps) + list(inner.proof_steps)),
            treatment=X,
            outcome=Y,
        )

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
    # Step 4b: factorise the truncated graph across every c-component.
    # ------------------------------------------------------------------
    if len(components_g_minus_x) > 1:
        factorization_step = ProofStep(
            rule_name="C_COMPONENT",
            antecedent_vars=tuple(sorted(V - X)),
            consequent_vars=tuple(sorted(Y)),
            applied_to_graph_state=(
                "ID Step 4: factorise over all c-components of G\\X and "
                "marginalise variables outside X∪Y"
            ),
            depth=_depth,
        )
        component_results: list[IdentificationResult] = []
        for component in components_g_minus_x:
            _trace.append(
                f"[depth={_depth}] Step 4: identifying Q[{sorted(component)}] "
                f"as ID({sorted(component)}, {sorted(V - component)}, G)"
            )
            component_result = id_algorithm(
                treatment=V - component,
                outcome=component,
                graph=graph,
                available_vars=V,
                dataset_ref=dataset_ref,
                domain=domain,
                _depth=_depth + 1,
                _trace=_trace,
            )
            if component_result.status is not IdentificationStatus.IDENTIFIED:
                outer_hedge = find_hedge(
                    treatment=X,
                    outcome=Y,
                    graph=graph,
                    available_vars=V,
                )
                if outer_hedge is not None:
                    _trace.append(f"[depth={_depth}] Step 4: validated outer-query hedge")
                    return IdentificationResult(
                        status=IdentificationStatus.HEDGE_FOUND,
                        estimand_ast=None,
                        hedge_certificate=outer_hedge,
                        trace=list(_trace),
                        required_distributions=[],
                        proof_steps=list(_steps)
                        + [
                            factorization_step,
                            ProofStep(
                                rule_name="HEDGE",
                                antecedent_vars=tuple(sorted(X)),
                                consequent_vars=tuple(sorted(Y)),
                                applied_to_graph_state=outer_hedge.description,
                                depth=_depth,
                            ),
                        ],
                    )
                _trace.append(
                    f"[depth={_depth}] Step 4: Q[{sorted(component)}] did not yield "
                    f"an identified kernel; returning {component_result.status.value}"
                )
                refusal_step = ProofStep(
                    rule_name="ORACLE",
                    antecedent_vars=tuple(sorted(X)),
                    consequent_vars=tuple(sorted(Y)),
                    applied_to_graph_state=(
                        f"ID Step 4 kernel Q[{sorted(component)}] was not established"
                    ),
                    depth=_depth,
                )
                return IdentificationResult(
                    status=(
                        IdentificationStatus.ORACLE_NEEDED
                        if component_result.status is IdentificationStatus.HEDGE_FOUND
                        else component_result.status
                    ),
                    estimand_ast=None,
                    hedge_certificate=None,
                    trace=list(_trace),
                    required_distributions=[],
                    proof_steps=list(_steps) + [refusal_step],
                )
            if component_result.estimand_ast is None:
                _trace.append(
                    f"[depth={_depth}] Step 4: Q[{sorted(component)}] has no AST; "
                    "returning ORACLE_NEEDED"
                )
                return IdentificationResult(
                    status=IdentificationStatus.ORACLE_NEEDED,
                    estimand_ast=None,
                    hedge_certificate=None,
                    trace=list(_trace),
                    required_distributions=[],
                    proof_steps=list(_steps)
                    + [
                        ProofStep(
                            rule_name="ORACLE",
                            antecedent_vars=tuple(sorted(X)),
                            consequent_vars=tuple(sorted(Y)),
                            applied_to_graph_state=(
                                f"ID Step 4 kernel Q[{sorted(component)}] has no AST"
                            ),
                            depth=_depth,
                        )
                    ],
                )
            component_results.append(component_result)

        component_roots = tuple(
            component_result.estimand_ast.root
            for component_result in component_results
            if component_result.estimand_ast is not None
        )
        product_root: object = ProductNode(
            factors=component_roots  # type: ignore[arg-type]
        )
        marginalise_over = tuple(sorted(V - (X | Y)))
        if marginalise_over:
            product_root = SumNode(
                summation_vars=marginalise_over,
                operand=product_root,  # type: ignore[arg-type]
            )
        ast = EstimandAST(
            query_str=_query_text(X, Y),
            root=product_root,  # type: ignore[arg-type]
            treatment=_query_var_label(X),
            outcome=_query_var_label(Y),
            all_variables=tuple(sorted(V)),
            identification_method="id_step4_factorization",
        )
        child_steps = [
            step for component_result in component_results for step in component_result.proof_steps
        ]
        required = [
            distribution
            for component_result in component_results
            if component_result.estimand_ast is not None
            for distribution in component_result.estimand_ast.collect_distribution_refs()
        ]
        return IdentificationResult(
            status=IdentificationStatus.IDENTIFIED,
            estimand_ast=ast,
            hedge_certificate=None,
            trace=list(_trace),
            required_distributions=required,
            proof_steps=list(_steps) + [factorization_step] + child_steps,
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
            return _rebind_result_query(
                dataclasses.replace(inner, proof_steps=list(_steps) + list(inner.proof_steps)),
                treatment=X,
                outcome=Y,
            )

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
    graph = _validate_static_id_graph(graph)
    query_issue = _native_query_admission_issue(
        treatment=treatment,
        outcome=outcome,
        conditions=conditions,
        graph_nodes=frozenset(graph.nodes),
    )
    if query_issue is not None:
        reason, gate = query_issue
        return _native_query_refusal_result(
            caller="idc_algorithm",
            reason=reason,
            gate=gate,
        )
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
    """Emit a directed-ancestor diagnostic for typed selection targets.

    This legacy screen is not a transportability gate: directed ancestry does
    not account for active bidirected paths. Its output is diagnostic only;
    positive identification uses the typed transport solver's m-separation
    check, and unsupported cases fail closed.
    """
    graph = _validate_static_admg(graph)
    an_y = ancestors(graph, outcome)
    pruned: set[str] = set()
    remaining: set[str] = set()
    current_graph = graph

    for v in sorted(s_node_vars):  # sorted for determinism
        if v not in an_y:
            # No directed path is found; the typed TR adapter checks mixed paths.
            pruned.add(v)
            _trace.append(
                f"[depth={_depth}] S_TRIM diagnostic: {v!r} is not in the directed "
                f"ancestors of {sorted(outcome)}"
            )
            _steps.append(
                ProofStep(
                    rule_name="S_TRIM",
                    antecedent_vars=(f"S_{v}",),
                    consequent_vars=(),
                    applied_to_graph_state=(
                        f"S_{v} is a directed-ancestor diagnostic only: "
                        f"{v!r} is not an ancestor of Y={sorted(outcome)}"
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
    graph = _validate_static_admg(graph)
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
    selection_diagram: Any,
    dataset_ref: str | None = None,
) -> IdentificationResult:
    """Identify bounded transport cases using typed selection semantics.

    Native TR delegates to the base graph when every selected mechanism is
    intervened on. Other scalar queries use the existing transport solver's
    recomputed S-admissibility source-law branch. The directed S-trim pass is
    diagnostic only; it cannot establish transportability. Unsupported or
    unverified shifts return ORACLE_NEEDED without a source-only formula.
    """
    from polisyos.foundry.methods.catalog.causal.transport_engine import (
        _candidate_member_sha256,
        solve_transportability,
    )
    from polisyos.ir.analytics.estimand import EstimandAST
    from polisyos.ir.analytics.transportability import (
        SelectionDiagram,
        transportability_candidate_query_sha256,
    )

    if not isinstance(selection_diagram, SelectionDiagram):
        return IdentificationResult(
            status=IdentificationStatus.ORACLE_NEEDED,
            estimand_ast=None,
            hedge_certificate=None,
            trace=["tr_algorithm: invalid selection_diagram type"],
            required_distributions=[],
        )

    selection_diagram = canonical_scalar_selection_diagram(selection_diagram)
    graph = selection_diagram.base_graph
    query_issue = _native_query_admission_issue(
        treatment=treatment,
        outcome=outcome,
        conditions=frozenset(),
        graph_nodes=frozenset(graph.nodes),
    )
    if query_issue is not None:
        reason, gate = query_issue
        return _native_query_refusal_result(
            caller="tr_algorithm",
            reason=reason,
            gate=gate,
        )

    trace: list[str] = [
        f"tr_algorithm: X={sorted(treatment)}, Y={sorted(outcome)}, "
        f"s_nodes={[sn.target_variable for sn in selection_diagram.s_nodes]}"
    ]
    _steps: list[ProofStep] = []

    if not selection_diagram.s_nodes:
        trace.append("tr_algorithm: no S-nodes; direct ID on complete base graph")
        return id_algorithm(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            dataset_ref=dataset_ref,
            domain=DistributionDomain.SOURCE,
            _trace=trace,
        )

    selection_targets = frozenset(sn.target_variable for sn in selection_diagram.s_nodes)

    # Synthetic names derive only from typed SNode targets. Reject graph identity
    # collisions before trimming or treatment-cut delegation can erase ambiguity.
    synthetic_s_names = frozenset(f"S_{variable}" for variable in selection_targets)
    name_collisions = synthetic_s_names & frozenset(graph.nodes)
    if name_collisions:
        collisions = sorted(name_collisions)
        trace.append(
            "tr_algorithm: ORACLE_NEEDED because synthetic selection-node names "
            f"collide with base graph nodes {collisions}"
        )
        _steps.append(
            ProofStep(
                rule_name="ORACLE",
                antecedent_vars=tuple(collisions),
                consequent_vars=tuple(sorted(outcome)),
                applied_to_graph_state=(
                    "A typed SNode target maps to a generated identity already used "
                    "by the base graph; selection-node identity is ambiguous."
                ),
                depth=0,
            )
        )
        return IdentificationResult(
            status=IdentificationStatus.ORACLE_NEEDED,
            estimand_ast=None,
            hedge_certificate=None,
            trace=list(trace),
            required_distributions=[],
            proof_steps=list(_steps),
            algorithm_version="tr_identity_refusal_v1",
            metadata={
                "backend_id": "native_tr",
                "gate_predicates": {"selection_node_identity": "not_established"},
            },
        )

    if selection_targets <= treatment:
        # Every typed selection mechanism enters an intervened variable, so
        # do(X) cuts those mechanisms. Use the original base graph's full kernel.
        trace.append(
            "tr_algorithm: every typed selection target is in do(X); "
            "selection mechanisms are cut and native ID uses the original base graph"
        )
        _steps.append(
            ProofStep(
                rule_name="S_AUGMENT",
                antecedent_vars=tuple(sorted(synthetic_s_names)),
                consequent_vars=tuple(sorted(selection_targets)),
                applied_to_graph_state=(
                    "Typed S_v->v selection edges are cut by do(X); delegate the "
                    "source effect to ID on the original complete base graph."
                ),
                depth=0,
            )
        )
        inner = id_algorithm(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            dataset_ref=dataset_ref,
            domain=DistributionDomain.SOURCE,
            _trace=trace,
        )
        return dataclasses.replace(inner, proof_steps=_steps + list(inner.proof_steps))

    # This legacy directed screen is diagnostic only. The proper adapter below
    # checks the actual typed selection diagram using do-graph m-separation.
    _, remaining_s_vars, _ = _s_trim_lemma(
        outcome=outcome,
        graph=graph,
        s_node_vars=selection_targets,
        _trace=trace,
        _steps=_steps,
        _depth=0,
    )
    if remaining_s_vars:
        _steps.append(
            ProofStep(
                rule_name="S_AUGMENT",
                antecedent_vars=tuple(f"S_{v}" for v in sorted(remaining_s_vars)),
                consequent_vars=tuple(sorted(remaining_s_vars)),
                applied_to_graph_state=(
                    "Nonintervened typed selection mechanisms remain; native ID "
                    "does not treat synthetic S variables as source observations."
                ),
                depth=0,
            )
        )
    trace.append(
        "tr_algorithm: directed S-trim is diagnostic only; it does not prove selection invariance"
    )

    def oracle_needed(reason: str, gates: dict[str, str]) -> IdentificationResult:
        trace.append(f"tr_algorithm: ORACLE_NEEDED: {reason}")
        _steps.append(
            ProofStep(
                rule_name="ORACLE",
                antecedent_vars=tuple(sorted(selection_targets)),
                consequent_vars=tuple(sorted(outcome)),
                applied_to_graph_state=reason,
                depth=0,
            )
        )
        return IdentificationResult(
            status=IdentificationStatus.ORACLE_NEEDED,
            estimand_ast=None,
            hedge_certificate=None,
            trace=list(trace),
            required_distributions=[],
            proof_steps=list(_steps),
            algorithm_version="tr_s_admissibility_limited_v1",
            metadata={
                "backend_id": "transport_engine.solve_transportability:simplified",
                "gate_predicates": gates,
                "selection_targets": sorted(selection_targets),
            },
        )

    if len(treatment) != 1 or len(outcome) != 1:
        return oracle_needed(
            "The reusable S-admissibility source-law adapter is bounded to scalar "
            "treatment and outcome; multivariate nonintervened shifts are not established.",
            {
                "s_admissibility": "not_established",
                "source_effect_identification": "not_established",
            },
        )

    try:
        transport_result = solve_transportability(
            selection_diagram=selection_diagram,
            query_treatment=next(iter(treatment)),
            query_outcome=next(iter(outcome)),
            solver_mode="simplified",
        )
    except Exception as exc:
        return oracle_needed(
            f"Existing typed transport adapter was unavailable: {type(exc).__name__}.",
            {
                "s_admissibility": "not_established",
                "source_effect_identification": "not_established",
            },
        )

    trace.extend(transport_result.identification_trace)
    gates = dict(transport_result.metadata).get("gate_predicates", {})
    expected_graph_sha256 = graph_content_sha256(graph)
    treatment_name = next(iter(treatment))
    outcome_name = next(iter(outcome))
    expected_transport_query = f"P*({outcome_name}|do({treatment_name}))"
    transport_query_identity = (
        transport_result.query == expected_transport_query
        and transport_result.source_graph_type is graph.graph_type
        and transport_result.source_graph_sha256 == expected_graph_sha256
        and transport_result.source_context_id == selection_diagram.source_context.context_id
        and transport_result.target_context_id == selection_diagram.target_context.context_id
    )
    candidate_diagnostic = getattr(transport_result, "candidate_diagnostics", None)
    candidate_inputs = getattr(candidate_diagnostic, "inputs", None)
    if candidate_inputs is not None:
        try:
            expected_query_sha256 = transportability_candidate_query_sha256(
                treatment_name, outcome_name
            )
            expected_selection_sha256 = _candidate_member_sha256(
                selection_diagram.model_dump(mode="json")
            )
            expected_source_context_sha256 = _candidate_member_sha256(
                selection_diagram.source_context.model_dump(mode="json")
            )
            expected_target_context_sha256 = _candidate_member_sha256(
                selection_diagram.target_context.model_dump(mode="json")
            )
        except (TypeError, ValueError):
            transport_query_identity = False
        else:
            transport_query_identity = transport_query_identity and (
                candidate_inputs.query_treatment == treatment_name
                and candidate_inputs.query_outcome == outcome_name
                and candidate_inputs.query_sha256 == expected_query_sha256
                and candidate_inputs.graph_type is graph.graph_type
                and candidate_inputs.graph_sha256 == expected_graph_sha256
                and candidate_inputs.selection_diagram_sha256 == expected_selection_sha256
                and candidate_inputs.model_plan_relation is None
                and candidate_inputs.source_context_id
                == selection_diagram.source_context.context_id
                and candidate_inputs.source_context_sha256 == expected_source_context_sha256
                and candidate_inputs.target_context_id
                == selection_diagram.target_context.context_id
                and candidate_inputs.target_context_sha256 == expected_target_context_sha256
            )
    adapter_ast_raw = transport_result.estimand_ast
    adapter_status = getattr(transport_result.status, "value", str(transport_result.status))
    positive_adapter = (
        transport_query_identity
        and adapter_status == "identified"
        and transport_result.algorithm_version == "s_admissibility_source_id_v1"
        and gates.get("s_admissibility") == "recomputed"
        and gates.get("source_effect_identification") == "recomputed"
        and transport_result.source_graph_sha256 == expected_graph_sha256
        and type(adapter_ast_raw) is dict
    )
    if positive_adapter:
        try:
            adapter_ast = EstimandAST.model_validate(adapter_ast_raw)
        except Exception:
            positive_adapter = False
        else:
            refs = adapter_ast.collect_distribution_refs()
            treatment_is_ancestor = treatment_name in ancestors(graph, frozenset({outcome_name}))
            treatment_matches = adapter_ast.treatment == treatment_name or (
                not treatment_is_ancestor and adapter_ast.treatment == "[]"
            )
            positive_adapter = (
                treatment_matches
                and adapter_ast.outcome == outcome_name
                and bool(refs)
                and all(ref.domain is DistributionDomain.SOURCE for ref in refs)
            )

    if positive_adapter:
        # The adapter does not carry dataset_ref. Reproduce the admitted source
        # ID with the caller's binding before returning the formula.
        source_result = id_algorithm(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            dataset_ref=dataset_ref,
            domain=DistributionDomain.SOURCE,
            _trace=trace,
        )
        source_ast = source_result.estimand_ast
        source_refs = source_ast.collect_distribution_refs() if source_ast is not None else []
        if (
            source_result.status is IdentificationStatus.IDENTIFIED
            and type(source_ast) is EstimandAST
            and bool(source_refs)
            and all(ref.domain is DistributionDomain.SOURCE for ref in source_refs)
        ):
            trace.append(
                "tr_algorithm: identified through transport_engine "
                "s_admissibility_source_id_v1 with recomputed graph binding and source ID"
            )
            admissibility_step = ProofStep(
                rule_name="S_ADMISSIBILITY",
                antecedent_vars=tuple(sorted(synthetic_s_names)),
                consequent_vars=tuple(sorted(outcome)),
                applied_to_graph_state=(
                    "The typed transport adapter recomputed S-node m-separation after "
                    "do(X), validated the full source ID AST, and bound it to the base graph."
                ),
                depth=0,
            )
            return dataclasses.replace(
                source_result,
                trace=list(trace),
                proof_steps=_steps + [admissibility_step] + list(source_result.proof_steps),
                algorithm_version="tr_s_admissibility_source_id_v1",
                metadata={
                    **source_result.metadata,
                    "backend_id": (
                        "transport_engine.solve_transportability:s_admissibility_source_id_v1"
                    ),
                    "backend_algorithm_version": transport_result.algorithm_version,
                    "source_graph_sha256": expected_graph_sha256,
                    "gate_predicates": {
                        "s_admissibility": "recomputed",
                        "source_effect_identification": "recomputed",
                        "source_graph_binding": "recomputed",
                        "transport_result_query_identity": "recomputed",
                    },
                    "selection_targets": sorted(selection_targets),
                },
            )

    if not transport_query_identity:
        adapter_reason = (
            "The transport result query/type/context or returned selection-input binding "
            "does not match the current typed SelectionDiagram and query."
        )
    else:
        adapter_reason = (
            transport_result.unsupported_reason
            or "The typed adapter did not establish an S-admissibility source law."
        )
    reason = (
        f"Existing transport adapter status={adapter_status}, "
        f"algorithm_version={transport_result.algorithm_version}: {adapter_reason}"
    )
    return oracle_needed(
        reason,
        {
            "s_admissibility": gates.get("s_admissibility", "not_established"),
            "source_effect_identification": gates.get(
                "source_effect_identification", "not_established"
            ),
            "transport_result_query_identity": (
                "recomputed" if transport_query_identity else "recomputed_false"
            ),
        },
    )


def id_with_oracle_fallback(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    oracle: Literal["dosearch", "y0", "none"] = "none",
    dataset_ref: str | None = None,
    domain: DistributionDomain = DistributionDomain.SOURCE,
    force_y0: bool = False,
) -> IdentificationResult:
    """Run native ID algorithm; fall back to oracle backend if ORACLE_NEEDED.

    Oracle backends
    ---------------
    "none"     – return ORACLE_NEEDED as-is
    "y0"       – attempt identification via the Y0 Python package
    "dosearch" – attempt identification via dosearch R package (rpy2 required)
    """
    # Freeze one graph for native ID and any selected oracle fallback. Invalid
    # query identities are refused before either native or external solvers.
    graph = _validate_static_id_graph(graph)
    query_issue = _native_query_admission_issue(
        treatment=treatment,
        outcome=outcome,
        conditions=frozenset(),
        graph_nodes=frozenset(graph.nodes),
    )
    if query_issue is not None:
        reason, gate = query_issue
        return _native_query_refusal_result(
            caller="id_with_oracle_fallback",
            reason=reason,
            gate=gate,
        )
    result = id_algorithm(
        treatment=treatment,
        outcome=outcome,
        graph=graph,
        dataset_ref=dataset_ref,
        domain=domain,
    )

    if force_y0 and oracle == "y0":
        # A selected Y0 backend must execute Y0 even when native ID has an answer.
        # A native hedge remains a valid stronger refusal and is never overwritten.
        if result.status is IdentificationStatus.HEDGE_FOUND:
            return result
        y0_input = IdentificationResult(
            status=IdentificationStatus.ORACLE_NEEDED,
            estimand_ast=None,
            hedge_certificate=None,
            trace=[*result.trace, "oracle_y0:explicit_backend_requested"],
            required_distributions=[],
            algorithm_version="y0",
            query_str=f"P({sorted(outcome)}|do({sorted(treatment)}))",
        )
        return _oracle_y0(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            native_result=y0_input,
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
    """Find a hedge witness for a query without running full ID.

    Returns a HedgeCertificate when a valid witness is constructed.
    None means this candidate search did not establish a hedge; it is not
    an identifiability proof because subset queries are not enumerated here.

    A hedge (F, F') is a pair of rooted C-forests with equal root sets such
    that F' lies among ancestors of Y after intervention, F' is contained
    in F, and F intersects X.

    Parameters
    ----------
    treatment      : X — intervention set
    outcome        : Y — target variables
    graph          : resolved DAG or acyclic ADMG
    available_vars : observed variables V; defaults to all graph nodes
    """
    graph = _validate_static_id_graph(graph)
    from polisyos.foundry.methods.catalog.causal.admg_ops import (
        ancestors,
        c_components,
        extract_bidirected_edges,
        induced_subgraph,
    )

    V = available_vars if available_vars is not None else frozenset(graph.nodes)
    X = treatment
    Y = outcome

    # F' must be a c-forest over ancestors of Y after the intervention.
    an_y_do_x = ancestors(do_operator(graph, X), Y) & V
    g_an_minus_x = induced_subgraph(graph, an_y_do_x - X)
    comps_minus_x = c_components(g_an_minus_x)

    # F must be a containing c-forest in the admitted variable universe.
    graph_v = induced_subgraph(graph, V)
    comps_g = c_components(graph_v)
    bi_edges = extract_bidirected_edges(graph_v)

    for si in comps_minus_x:
        if not (si >= Y):
            continue  # F' must contain Y
        small_roots = _c_forest_roots(graph_v, si)
        if small_roots is None or not small_roots <= an_y_do_x:
            continue
        # F is a containing c-forest with the same root set and treatment.
        for sj in comps_g:
            if not (si <= sj and sj & X):
                continue
            large_roots = _c_forest_roots(graph_v, sj)
            if large_roots is None or large_roots != small_roots:
                continue
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
                hedge_root=small_roots,
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

    A thicket is the set of minimal, non-redundant hedge witnesses found
    for the supplied query. An empty list means this search established no
    hedge; it does not prove identifiability because subset queries are not
    enumerated here.

    Complexity: O(|C|²) in the number of c-components — tractable for graphs
    under ~200 nodes.

    Parameters
    ----------
    treatment      : X — intervention set
    outcome        : Y — target variables
    graph          : causal graph
    available_vars : observed variables V; defaults to all graph nodes
    """
    graph = _validate_static_id_graph(graph)
    from polisyos.foundry.methods.catalog.causal.admg_ops import (
        ancestors,
        c_components,
        extract_bidirected_edges,
        induced_subgraph,
    )

    V = available_vars if available_vars is not None else frozenset(graph.nodes)
    X = treatment
    Y = outcome

    an_y_do_x = ancestors(do_operator(graph, X), Y) & V
    g_an_minus_x = induced_subgraph(graph, an_y_do_x - X)
    comps_minus_x = c_components(g_an_minus_x)
    graph_v = induced_subgraph(graph, V)
    comps_g = c_components(graph_v)
    bi_edges = extract_bidirected_edges(graph_v)

    all_certs: list[HedgeCertificate] = []
    seen: set[tuple[frozenset[str], frozenset[str]]] = set()

    for si in comps_minus_x:
        if not (si >= Y):
            continue
        small_roots = _c_forest_roots(graph_v, si)
        if small_roots is None or not small_roots <= an_y_do_x:
            continue
        for sj in comps_g:
            if not (si <= sj and sj & X):
                continue
            large_roots = _c_forest_roots(graph_v, sj)
            if large_roots is None or large_roots != small_roots:
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
                    hedge_root=small_roots,
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


def _query_var_label(variables: frozenset[str]) -> str:
    """Render a variable set for the scalar query metadata fields."""
    return next(iter(sorted(variables))) if len(variables) == 1 else str(sorted(variables))


def _query_text(treatment: frozenset[str], outcome: frozenset[str]) -> str:
    """Render the intervention query without inventing do() for an empty set."""
    outcome_label = _query_var_label(outcome)
    if not treatment:
        return f"P({outcome_label})"
    return f"P({outcome_label}|do({_query_var_label(treatment)}))"


def _rebind_result_query(
    result: IdentificationResult,
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
) -> IdentificationResult:
    """Restore the caller's query metadata after a valid recursive reduction."""
    ast = result.estimand_ast
    if ast is None:
        return result
    all_variables = set(ast.all_variables) | treatment | outcome
    rebound = ast.model_copy(
        update={
            "query_str": _query_text(treatment, outcome),
            "treatment": _query_var_label(treatment),
            "outcome": _query_var_label(outcome),
            "all_variables": tuple(sorted(all_variables)),
        }
    )
    return dataclasses.replace(result, estimand_ast=rebound)


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
    """Build the Step 5 Q[Si] kernel using the observational chain rule.

    Factorises as: ∑_{V\\(X∪Y)} ∏_{Vk ∈ Si} P(Vk | V^(k-1)).

    Each factor conditions on all preceding variables in a topological order.
    The caller reaches Step 5 only when Si is the full c-component of G\\X.
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

    all_dists: list[DistributionRef] = []
    # Q[Si] factors each Si variable against every preceding variable in the
    # observational topological order, not only its directed graph parents.
    # Non-parent predecessors can carry latent dependence into this kernel.
    factors: list[object] = []
    for vi_idx, vi in enumerate(topo_in_V):
        if vi not in si:
            continue
        predecessors_in_V = set(topo_in_V[:vi_idx])
        cond = tuple(sorted(predecessors_in_V))
        dr = _make_conditional_dist(
            variables=(vi,),
            conditioning=cond,
            dataset_ref=dataset_ref,
            domain=domain,
        )
        factors.append(dr)
        all_dists.append(dr)

    trace.append(f"[depth={depth}] Step 5: built {len(factors)}-factor product over Si")

    # Sum every non-treatment, non-outcome variable in the reduced problem.
    marginalise_over = tuple(sorted(V - (X | Y)))
    if len(factors) == 1:
        product_node = factors[0]
    else:
        product_node = ProductNode(factors=tuple(factors))  # type: ignore[arg-type]

    if marginalise_over:
        root_node = SumNode(summation_vars=marginalise_over, operand=product_node)  # type: ignore[arg-type]
    else:
        root_node = product_node  # type: ignore[assignment]

    ast = EstimandAST(
        query_str=_query_text(X, Y),
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
    """Refuse Step 6 until the recursive Q[Sj] kernel can be carried.

    Standard ID recurses on ID(Y, X ∩ Si, G[Sj], Q[Sj]). The current
    public input is observational P(V); calling id_algorithm on G[Sj] would
    silently replace the required kernel with P(Sj) and can return a false
    identified formula. Keep this branch fail-closed so the explicit oracle
    bridge can evaluate the complete query with its own backend provenance.
    """
    trace.append(
        f"[depth={depth}] Step 6: Si={sorted(si)} ⊂ Sj={sorted(sj)} requires Q[Sj]; "
        "native Q-kernel input is unavailable — ORACLE_NEEDED"
    )
    proof = ProofStep(
        rule_name="ORACLE",
        antecedent_vars=tuple(sorted(X)),
        consequent_vars=tuple(sorted(Y)),
        applied_to_graph_state=(
            f"Step 6 requires Q[Sj] for Sj={sorted(sj)}; native ID only has P(V)"
        ),
        depth=depth,
    )
    return IdentificationResult(
        status=IdentificationStatus.ORACLE_NEEDED,
        estimand_ast=None,
        hedge_certificate=None,
        trace=list(trace),
        required_distributions=[],
        proof_steps=[proof],
        query_str=_query_text(X, Y),
    )


# ---------------------------------------------------------------------------
# Oracle backends
# ---------------------------------------------------------------------------


def _y0_expression_to_node(
    expression: Any,
    *,
    dataset_ref: str | None,
    domain: DistributionDomain,
) -> Any:
    """Convert the supported Y0 ID expression grammar into the existing typed AST."""
    from y0.dsl import Fraction, PopulationProbability, Probability, Product, Sum, Variable

    if isinstance(expression, Sum):
        return SumNode(
            summation_vars=tuple(sorted(variable.name for variable in expression.ranges)),
            operand=_y0_expression_to_node(
                expression.expression,
                dataset_ref=dataset_ref,
                domain=domain,
            ),
        )
    if isinstance(expression, Product):
        return ProductNode(
            factors=tuple(
                _y0_expression_to_node(
                    factor,
                    dataset_ref=dataset_ref,
                    domain=domain,
                )
                for factor in expression.expressions
            ),
        )
    if isinstance(expression, Fraction):
        return RatioNode(
            numerator=_y0_expression_to_node(
                expression.numerator,
                dataset_ref=dataset_ref,
                domain=domain,
            ),
            denominator=_y0_expression_to_node(
                expression.denominator,
                dataset_ref=dataset_ref,
                domain=domain,
            ),
        )
    if isinstance(expression, PopulationProbability):
        raise TypeError("y0_population_probability_not_supported_by_direct_id_ast")
    if isinstance(expression, Probability):
        distribution = expression.distribution
        variables = (*distribution.children, *distribution.parents)
        if any(type(variable) is not Variable for variable in variables):
            raise TypeError("y0_nonstandard_variable_not_supported_by_direct_id_ast")
        return DistributionRef(
            domain=domain,
            variables=tuple(variable.name for variable in distribution.children),
            conditioning=tuple(variable.name for variable in distribution.parents),
            dataset_ref=dataset_ref,
        )
    raise TypeError(f"y0_expression_type_not_supported:{type(expression).__name__}")


def _y0_oracle_needed(
    native_result: IdentificationResult,
    *,
    reason: str,
    version: str | None,
    backend_call_attempted: bool = False,
    backend_call_established: bool = False,
    backend_result: str = "not_returned",
) -> IdentificationResult:
    return dataclasses.replace(
        native_result,
        status=IdentificationStatus.ORACLE_NEEDED,
        estimand_ast=None,
        hedge_certificate=None,
        trace=[*native_result.trace, f"oracle_y0:limited:{reason}"],
        required_distributions=[],
        algorithm_version=f"y0_{version}" if version else "y0_api_unavailable",
        metadata={
            "backend_id": "y0",
            "backend_version": version,
            "backend_operation": "identify_outcomes",
            "backend_call_attempted": backend_call_attempted,
            "backend_call_established": backend_call_established,
            "backend_result": backend_result,
            "result_status_origin": "actual_backend_result_not_identified",
            "limitation_reason": reason,
            "gate_predicates": {
                "backend_operation_result": (
                    "recomputed" if backend_call_established else "not_established"
                ),
                "source_data_exists": "not_established",
                "source_data_currentness": "not_established",
                "source_data_authority": "not_established",
            },
        },
    )


def _oracle_y0(
    *,
    treatment: frozenset[str],
    outcome: frozenset[str],
    graph: CausalGraphModel,
    native_result: IdentificationResult,
    dataset_ref: str | None,
    domain: DistributionDomain,
) -> IdentificationResult:
    """Run Y0's locked direct-ID API and preserve its returned expression in typed IR."""
    version: str | None = None
    backend_call_attempted = False
    backend_call_established = False
    try:
        from importlib.metadata import version as package_version

        from y0.algorithm.identify import identify_outcomes  # type: ignore[import-not-found]
        from y0.dsl import Variable  # type: ignore[import-not-found]

        from polisyos.foundry.methods.catalog.causal.full_transport_bridge import build_y0_graph

        version = package_version("y0")
        mixed = build_y0_graph(graph)
        y_vars = {Variable(name) for name in sorted(outcome)}
        x_vars = {Variable(name) for name in sorted(treatment)}
        backend_call_attempted = True
        expression = identify_outcomes(
            graph=mixed,
            treatments=x_vars,
            outcomes=y_vars,
        )
        backend_call_established = True
        if expression is None:
            return _y0_oracle_needed(
                native_result,
                reason="identify_outcomes_returned_none",
                version=version,
                backend_call_attempted=backend_call_attempted,
                backend_call_established=True,
                backend_result="none_returned",
            )
        try:
            root = _y0_expression_to_node(
                expression,
                dataset_ref=dataset_ref,
                domain=domain,
            )
        except (TypeError, ValueError) as exc:
            return _y0_oracle_needed(
                native_result,
                reason=f"returned_expression_not_representable:{type(exc).__name__}",
                version=version,
                backend_call_attempted=backend_call_attempted,
                backend_call_established=True,
                backend_result="expression_not_representable",
            )
        variables = {
            name
            for distribution in _collect_y0_distribution_refs(root)
            for name in (
                *distribution.variables,
                *distribution.conditioning,
                *distribution.intervention_set,
            )
        }
        query_str = f"P({','.join(sorted(outcome))}|do({','.join(sorted(treatment))}))"
        ast = EstimandAST(
            query_str=query_str,
            root=root,
            treatment=next(iter(sorted(treatment)))
            if len(treatment) == 1
            else str(sorted(treatment)),
            outcome=next(iter(sorted(outcome))) if len(outcome) == 1 else str(sorted(outcome)),
            all_variables=tuple(sorted(variables | set(treatment) | set(outcome))),
            identification_method="y0_oracle",
        )
        expression_latex = expression.to_latex()
        return IdentificationResult(
            status=IdentificationStatus.IDENTIFIED,
            estimand_ast=ast,
            hedge_certificate=None,
            trace=[
                *native_result.trace,
                "oracle_y0:api_called:identify_outcomes",
                f"oracle_y0:version:{version}",
                f"oracle_y0:expression_latex:{expression_latex}",
            ],
            required_distributions=ast.collect_distribution_refs(),
            algorithm_version=f"y0_{version}",
            proof_steps=[],
            query_str=query_str,
            metadata={
                "backend_id": "y0",
                "backend_version": version,
                "backend_operation": "identify_outcomes",
                "backend_call_attempted": True,
                "backend_call_established": True,
                "backend_result": "expression_returned",
                "backend_expression_latex": expression_latex,
                "backend_expression_y0": expression.to_y0(),
                "profile_origin": "not_applicable_direct_id",
                "source_data_exists": "not_established",
                "source_data_currentness": "not_established",
                "source_data_authority": "not_established",
                "gate_predicates": {
                    "graph_input": "recomputed",
                    "backend_operation_result": "recomputed",
                    "source_data_exists": "not_established",
                    "source_data_currentness": "not_established",
                    "source_data_authority": "not_established",
                },
            },
        )
    except Exception as exc:
        return _y0_oracle_needed(
            native_result,
            reason=f"api_error:{type(exc).__name__}",
            version=version,
            backend_call_attempted=backend_call_attempted,
            backend_call_established=backend_call_established,
            backend_result="not_returned",
        )


def _collect_y0_distribution_refs(root: Any) -> list[DistributionRef]:
    """Walk the PolicyOS AST produced from Y0's direct-ID expression."""
    if isinstance(root, DistributionRef):
        return [root]
    if isinstance(root, SumNode):
        return _collect_y0_distribution_refs(root.operand)
    if isinstance(root, ProductNode):
        return [
            reference
            for factor in root.factors
            for reference in _collect_y0_distribution_refs(factor)
        ]
    if isinstance(root, RatioNode):
        return [
            *_collect_y0_distribution_refs(root.numerator),
            *_collect_y0_distribution_refs(root.denominator),
        ]
    raise TypeError(f"unsupported_policyos_y0_ast_node:{type(root).__name__}")


def _dosearch_oracle_needed(
    native_result: IdentificationResult,
    *,
    reason: str,
    backend_call_attempted: bool,
    backend_call_established: bool,
    backend_result: str,
    backend_formula: str | None = None,
) -> IdentificationResult:
    """Keep dosearch outcomes non-authoritative until a typed AST exists."""
    metadata: dict[str, Any] = {
        "backend_id": "dosearch",
        "backend_operation": "dosearch",
        "backend_call_attempted": backend_call_attempted,
        "backend_call_established": backend_call_established,
        "backend_result": backend_result,
        "result_status_origin": "backend_formula_not_imported",
        "limitation_reason": reason,
        "gate_predicates": {
            "backend_operation_result": (
                "recomputed" if backend_call_established else "not_established"
            ),
            "typed_formula_import": "not_established",
            "source_data_exists": "not_established",
            "source_data_currentness": "not_established",
            "source_data_authority": "not_established",
        },
    }
    if backend_formula is not None:
        metadata["backend_formula"] = backend_formula
    return dataclasses.replace(
        native_result,
        status=IdentificationStatus.ORACLE_NEEDED,
        estimand_ast=None,
        hedge_certificate=None,
        trace=[*native_result.trace, f"oracle_dosearch:limited:{reason}"],
        required_distributions=[],
        algorithm_version="dosearch_oracle",
        metadata=metadata,
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
    """Attempt dosearch, failing closed until its formula has a typed importer."""
    backend_call_attempted = False
    backend_call_established = False
    try:
        import rpy2.robjects as ro  # type: ignore[import-not-found]
        from rpy2.robjects.packages import importr  # type: ignore[import-not-found]

        dosearch = importr("dosearch")
    except ImportError:
        return _dosearch_oracle_needed(
            native_result,
            reason="rpy2_or_dosearch_unavailable",
            backend_call_attempted=False,
            backend_call_established=False,
            backend_result="not_called",
        )

    try:
        directed_edges = [
            f"{edge.src} -> {edge.dst}"
            for edge in graph.edges
            if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW
        ]
        bidirected_edges = [
            f"{edge.src} <-> {edge.dst}"
            for edge in graph.edges
            if edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW
        ]
        graph_str = "\n".join(directed_edges + bidirected_edges)
        data_str = f"p({', '.join(sorted(graph.nodes))})"
        query_str = f"p({', '.join(sorted(outcome))} | do({', '.join(sorted(treatment))}))"
        backend_call_attempted = True
        result = dosearch.dosearch(
            data=ro.StrVector([data_str]),
            query=ro.StrVector([query_str]),
            graph=ro.StrVector([graph_str]),
        )
        backend_call_established = True
        formula = str(result.rx2("formula")[0]).strip() if result is not None else ""
        if formula and formula.upper() != "NULL":
            return _dosearch_oracle_needed(
                native_result,
                reason="returned_formula_cannot_be_imported_to_typed_ast",
                backend_call_attempted=True,
                backend_call_established=True,
                backend_result="formula_returned",
                backend_formula=formula,
            )
        return _dosearch_oracle_needed(
            native_result,
            reason="no_formula_returned",
            backend_call_attempted=True,
            backend_call_established=True,
            backend_result="no_formula_returned",
        )
    except Exception as exc:
        return _dosearch_oracle_needed(
            native_result,
            reason=f"api_error:{type(exc).__name__}",
            backend_call_attempted=backend_call_attempted,
            backend_call_established=backend_call_established,
            backend_result="not_returned",
        )


__all__ = [name for name in globals() if not name.startswith("__")]
