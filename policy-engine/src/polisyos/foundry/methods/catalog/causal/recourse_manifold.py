"""Optimal recourse intervention solver over a causal intervention manifold.

Implements the Stage 13.4 two-level solver sketched in the research plan:

1. **Proof level** — ``identify_or_bound(query, scm)`` decides the
   recoverability status of the success functional ``g(a)`` under the selected
   semantics. If ``nonrecoverable`` and no bounds are available, the kernel
   returns a blocked :class:`OptimalRecourseInterventionBundle`.
2. **Planner level** — three branches are dispatched based on the atlas
   flavour:

   * ``exact_graph_search`` — uniform-cost search over a discrete finite
     action library, reducing the problem to shortest path over equivalence
     classes on the causal manifold.
   * ``branch_and_bound_over_supports`` — fixed-support convex subproblems
     enumerated in best-first order, using a finite interval chart
     approximation for continuous domains.
   * ``best_first_support_search`` — general nonlinear heuristic over a
     sampled finite atlas for mixed / non-convex domains.

For the MVP we ship the discrete branch in production quality (suitable for
finite action libraries — the setting most policy-engine consumers face) and
add honest approximate pathways for continuous domains. The convex branch uses
support-wise branch-and-bound over a sampled interval chart and therefore
returns ``epsilon_optimal`` rather than ``exact``. The fallback branch
constructs a coarse sampled atlas and returns a ``heuristic`` result.

The solver consumes an ``SCMAdapter`` protocol rather than a concrete SCM
implementation so callers can plug in ``Hybrid SCM``, ``NCMSpec``, or a mock
in tests. The adapter needs just three capabilities: compute the success
functional ``g(a)`` for an action, canonicalise an action within its causal
equivalence class, and replay ``do(a)`` structurally so the feasibility
certificate can record ``structural_consistency_ok``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from heapq import heappop, heappush
from itertools import combinations, product
from typing import Any, Literal, Protocol

from polisyos.ir.analytics.recourse_manifold import (
    ActionDomain,
    CanonicalizationPolicy,
    CouplingCost,
    InterventionCostManifold,
    InterventionProgram,
    OptimalRecourseInterventionBundle,
    OptimalRecourseInterventionQuery,
    PrimitiveAction,
    PrimitiveCost,
    RecourseComplexityClass,
    RecourseFeasibilityCertificate,
    RecourseOptimalityCertificateKind,
    RecourseProofBundle,
    RecourseReadinessCap,
    RecourseRecoverabilityStatus,
    RecourseSolverStatus,
    RecourseTractableSubfamily,
    RecourseUniquenessStatus,
    build_feasibility_certificate,
    build_recourse_proof_bundle,
)
from polisyos.ir.refs import (
    OptimalRecourseInterventionQueryRef,
    RecourseFeasibilityCertificateRef,
    RecourseProofBundleRef,
)


class SCMAdapter(Protocol):
    """Minimum capability surface the recourse solver needs from an SCM."""

    def identify_success_functional(
        self,
        query: OptimalRecourseInterventionQuery,
    ) -> tuple[RecourseRecoverabilityStatus, str | None, list[str]]:
        """Return recoverability status, estimand ref (optional), and proof trace."""

    def success_value(
        self,
        query: OptimalRecourseInterventionQuery,
        action: InterventionProgram,
    ) -> float:
        """Evaluate ``g(a)`` under the semantics/success-mode of the query."""

    def canonicalise(
        self,
        manifold: InterventionCostManifold,
        action: InterventionProgram,
    ) -> InterventionProgram:
        """Map ``a`` to its canonical representative inside ``[a]``."""

    def replay_structural_consistency(
        self,
        action: InterventionProgram,
    ) -> bool:
        """Replay SCM after ``do(a)`` and return whether the post-state is consistent."""


@dataclass(frozen=True)
class PlannerOptions:
    """Tunable search knobs shared across planner branches."""

    max_expansions: int = 10000
    support_budget: int | None = None
    epsilon: float = 0.0
    interval_grid_size: int = 9
    heuristic_interval_grid_size: int | None = None


@dataclass
class DiscreteActionAtlas:
    """Discrete action library indexed by mutable node.

    Materialises ``(node, target_value)`` atoms that can appear inside an
    :class:`InterventionProgram`. Graph search explores supports by extending
    a frontier of programs by one atom at a time.
    """

    atoms: tuple[PrimitiveAction, ...]
    primitive_cost_lookup: dict[str, PrimitiveCost]
    coupling_costs: tuple[CouplingCost, ...]
    canonicalization_policy: CanonicalizationPolicy

    @property
    def is_finite_discrete(self) -> bool:
        return bool(self.atoms)


def _interval_grid(domain: ActionDomain, *, points: int) -> tuple[float, ...]:
    lower = float(domain.lower or 0.0)
    upper = float(domain.upper or 0.0)
    if points <= 1 or lower == upper:
        return (lower,)
    step = (upper - lower) / float(points - 1)
    values = [lower + step * index for index in range(points)]
    deduped = dict.fromkeys(round(value, 12) for value in values)
    return tuple(float(value) for value in deduped)


def _enumerate_atoms(
    manifold: InterventionCostManifold,
    *,
    interval_grid_size: int | None = None,
) -> tuple[PrimitiveAction, ...]:
    atoms: list[PrimitiveAction] = []
    channel_by_node = {c.node: c.channel for c in manifold.action_channels}
    for domain in manifold.domains:
        channel = channel_by_node.get(domain.node)
        if domain.kind == "discrete":
            for value in domain.values:
                atoms.append(
                    PrimitiveAction(
                        node=domain.node,
                        target_value=value,
                        channel=channel,
                    )
                )
        elif domain.kind == "finite_policy":
            for policy_ref in domain.policy_refs:
                atoms.append(
                    PrimitiveAction(
                        node=domain.node,
                        policy_ref=policy_ref,
                        channel=channel,
                    )
                )
        elif domain.kind == "interval" and interval_grid_size is not None:
            for value in _interval_grid(domain, points=max(2, interval_grid_size)):
                atoms.append(
                    PrimitiveAction(
                        node=domain.node,
                        target_value=value,
                        channel=channel,
                    )
                )
    return tuple(atoms)


def build_discrete_atlas(manifold: InterventionCostManifold) -> DiscreteActionAtlas:
    """Build a finite action atlas from a manifold's discrete / finite-policy domains.

    Continuous (``interval``) domains are skipped — the caller must route those
    through a convex or gradient-based inner solver.
    """
    atoms = _enumerate_atoms(manifold)
    lookup = {cost.node: cost for cost in manifold.primitive_costs}
    return DiscreteActionAtlas(
        atoms=atoms,
        primitive_cost_lookup=lookup,
        coupling_costs=manifold.coupling_costs,
        canonicalization_policy=manifold.canonicalization_policy,
    )


def _build_sampled_atlas(
    manifold: InterventionCostManifold,
    *,
    interval_grid_size: int,
) -> DiscreteActionAtlas:
    atoms = _enumerate_atoms(
        manifold,
        interval_grid_size=max(2, interval_grid_size),
    )
    lookup = {cost.node: cost for cost in manifold.primitive_costs}
    return DiscreteActionAtlas(
        atoms=atoms,
        primitive_cost_lookup=lookup,
        coupling_costs=manifold.coupling_costs,
        canonicalization_policy=manifold.canonicalization_policy,
    )


def _primitive_atom_cost(action: PrimitiveAction, cost_spec: PrimitiveCost | None) -> float:
    if cost_spec is None:
        return 0.0
    if cost_spec.cost_kind == "constant":
        return float(cost_spec.base_cost)
    if cost_spec.cost_kind == "linear":
        slope = cost_spec.slope or 0.0
        scale = _numeric_magnitude(action)
        return float(cost_spec.base_cost + slope * scale)
    if cost_spec.cost_kind == "quadratic":
        slope = cost_spec.slope or 0.0
        curvature = cost_spec.curvature or 0.0
        scale = _numeric_magnitude(action)
        return float(cost_spec.base_cost + slope * scale + curvature * scale * scale)
    if cost_spec.cost_kind == "tabular":
        key = _tabular_key(action)
        if key in cost_spec.table:
            return float(cost_spec.table[key])
        return float(cost_spec.base_cost)
    return float(cost_spec.base_cost)


def _numeric_magnitude(action: PrimitiveAction) -> float:
    value = action.target_value
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 1.0


def _tabular_key(action: PrimitiveAction) -> str:
    if action.policy_ref:
        return f"policy:{action.policy_ref}"
    return str(action.target_value)


def _coupling_cost(
    action: InterventionProgram,
    coupling_costs: Iterable[CouplingCost],
) -> float:
    support = set(action.support)
    total = 0.0
    for coupling in coupling_costs:
        if coupling.kind == "complementarity":
            if set(coupling.nodes).issubset(support):
                total -= coupling.limit or 0.0
        elif coupling.kind == "sequencing":
            if set(coupling.nodes) & support:
                total += coupling.limit or 0.0
    return total


def program_cost(
    action: InterventionProgram,
    manifold: InterventionCostManifold,
) -> float:
    """Compute ``C_0(b)`` for a concrete representative."""
    immutable = set(manifold.immutable_nodes)
    support = set(action.support)
    if support & immutable or any(node not in manifold.mutable_nodes for node in support):
        return float("inf")
    cost_lookup = {c.node: c for c in manifold.primitive_costs}
    atom_cost = sum(
        _primitive_atom_cost(step, cost_lookup.get(step.node)) for step in action.actions
    )
    budget_ok = True
    for coupling in manifold.coupling_costs:
        if coupling.kind == "budget" and coupling.limit is not None:
            restricted_nodes = set(coupling.nodes) & support
            restricted_cost = sum(
                _primitive_atom_cost(step, cost_lookup.get(step.node))
                for step in action.actions
                if step.node in restricted_nodes
            )
            if restricted_cost > coupling.limit:
                budget_ok = False
                break
    if not budget_ok:
        return float("inf")
    return atom_cost + _coupling_cost(action, manifold.coupling_costs)


def _extend(program: InterventionProgram, atom: PrimitiveAction) -> InterventionProgram | None:
    if atom.node in program.support:
        return None
    return InterventionProgram(actions=(*program.actions, atom))


def _program_key(program: InterventionProgram) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((step.node, step.stable_value) for step in program.actions))


def _has_interval_domains(manifold: InterventionCostManifold) -> bool:
    return any(domain.kind == "interval" for domain in manifold.domains)


def _candidate_actions_by_node(
    manifold: InterventionCostManifold,
    *,
    interval_grid_size: int,
) -> dict[str, tuple[PrimitiveAction, ...]]:
    atoms = _enumerate_atoms(
        manifold,
        interval_grid_size=max(2, interval_grid_size),
    )
    cost_lookup = {cost.node: cost for cost in manifold.primitive_costs}
    grouped: dict[str, list[PrimitiveAction]] = {}
    for atom in atoms:
        grouped.setdefault(atom.node, []).append(atom)
    return {
        node: tuple(
            sorted(
                node_atoms,
                key=lambda atom: (
                    _primitive_atom_cost(atom, cost_lookup.get(atom.node)),
                    atom.stable_value,
                ),
            )
        )
        for node, node_atoms in grouped.items()
    }


def _minimum_domain_cost(
    *,
    domain: ActionDomain,
    channel: str | None,
    cost_spec: PrimitiveCost | None,
) -> float:
    if domain.kind == "discrete":
        return min(
            _primitive_atom_cost(
                PrimitiveAction(node=domain.node, target_value=value, channel=channel),
                cost_spec,
            )
            for value in domain.values
        )
    if domain.kind == "finite_policy":
        return min(
            _primitive_atom_cost(
                PrimitiveAction(node=domain.node, policy_ref=policy_ref, channel=channel),
                cost_spec,
            )
            for policy_ref in domain.policy_refs
        )
    lower = float(domain.lower or 0.0)
    upper = float(domain.upper or 0.0)
    candidates = [lower, upper]
    if cost_spec is not None and cost_spec.cost_kind == "quadratic":
        slope = cost_spec.slope or 0.0
        curvature = cost_spec.curvature or 0.0
        if curvature != 0.0:
            stationary = -slope / (2.0 * curvature)
            if lower <= stationary <= upper:
                candidates.append(stationary)
    return min(
        _primitive_atom_cost(
            PrimitiveAction(node=domain.node, target_value=value, channel=channel),
            cost_spec,
        )
        for value in candidates
    )


def _support_lower_bound(
    support: tuple[str, ...],
    *,
    manifold: InterventionCostManifold,
) -> float:
    cost_lookup = {cost.node: cost for cost in manifold.primitive_costs}
    channel_by_node = {channel.node: channel.channel for channel in manifold.action_channels}
    domain_by_node = {domain.node: domain for domain in manifold.domains}
    support_set = set(support)

    minimum_costs: dict[str, float] = {}
    for node in support:
        domain = domain_by_node.get(node)
        if domain is None:
            return float("inf")
        minimum_costs[node] = _minimum_domain_cost(
            domain=domain,
            channel=channel_by_node.get(node),
            cost_spec=cost_lookup.get(node),
        )

    lower_bound = sum(minimum_costs.values())
    for coupling in manifold.coupling_costs:
        coupling_nodes = set(coupling.nodes)
        active_nodes = coupling_nodes & support_set
        if coupling.kind == "budget" and coupling.limit is not None:
            if sum(minimum_costs.get(node, 0.0) for node in active_nodes) > coupling.limit:
                return float("inf")
        elif coupling.kind == "complementarity" and coupling_nodes.issubset(support_set):
            lower_bound -= coupling.limit or 0.0
        elif coupling.kind == "sequencing" and active_nodes:
            lower_bound += coupling.limit or 0.0
    return lower_bound


def _solve_support_via_grid(
    support: tuple[str, ...],
    *,
    query: OptimalRecourseInterventionQuery,
    manifold: InterventionCostManifold,
    scm: SCMAdapter,
    candidate_actions_by_node: dict[str, tuple[PrimitiveAction, ...]],
    max_evaluations: int,
    incumbent_cost: float,
    epsilon: float,
) -> tuple[tuple[InterventionProgram, float, float] | None, int]:
    if not support:
        initial = InterventionProgram(actions=())
        success = scm.success_value(query, initial)
        if success >= query.threshold_tau:
            return (initial, 0.0, success), 1
        return None, 1

    choices_per_node = [candidate_actions_by_node.get(node, ()) for node in support]
    if any(not choices for choices in choices_per_node):
        return None, 0

    best: tuple[InterventionProgram, float, float] | None = None
    seen: set[tuple[tuple[str, str], ...]] = set()
    explored = 0

    for selected_atoms in product(*choices_per_node):
        if explored >= max_evaluations:
            break
        explored += 1
        candidate = InterventionProgram(actions=tuple(selected_atoms))
        canonical = scm.canonicalise(manifold, candidate)
        key = _program_key(canonical)
        if key in seen:
            continue
        seen.add(key)
        cost = program_cost(canonical, manifold)
        if cost == float("inf") or cost > incumbent_cost - epsilon:
            continue
        success = scm.success_value(query, canonical)
        if success >= query.threshold_tau:
            if best is None or cost < best[1] - epsilon:
                best = (canonical, cost, success)
    return best, explored


@dataclass(order=True)
class _FrontierEntry:
    priority: float
    order: int
    program: InterventionProgram = field(compare=False)


def exact_graph_search(
    *,
    query: OptimalRecourseInterventionQuery,
    manifold: InterventionCostManifold,
    atlas: DiscreteActionAtlas,
    scm: SCMAdapter,
    options: PlannerOptions,
) -> tuple[InterventionProgram, float, float, int] | None:
    """Uniform-cost search over the discrete causal action atlas.

    Returns ``(action, cost, achieved_success, candidates_explored)`` when a
    program satisfying ``success_value >= threshold_tau`` exists, otherwise
    ``None``.
    """
    if not atlas.is_finite_discrete:
        return None

    tau = query.threshold_tau
    support_budget = options.support_budget or query.support_budget
    initial = InterventionProgram(actions=())

    initial_success = scm.success_value(query, initial)
    if initial_success >= tau:
        return initial, 0.0, initial_success, 1

    frontier: list[_FrontierEntry] = []
    visited: set[tuple[tuple[str, str], ...]] = {_program_key(initial)}
    counter = 0
    heappush(frontier, _FrontierEntry(0.0, counter, initial))

    explored = 0
    while frontier and explored < options.max_expansions:
        entry = heappop(frontier)
        program = entry.program
        explored += 1
        if support_budget is not None and len(program.support) >= support_budget:
            continue
        for atom in atlas.atoms:
            candidate = _extend(program, atom)
            if candidate is None:
                continue
            canonical = scm.canonicalise(manifold, candidate)
            key = _program_key(canonical)
            if key in visited:
                continue
            visited.add(key)
            cost = program_cost(canonical, manifold)
            if cost == float("inf"):
                continue
            success = scm.success_value(query, canonical)
            if success >= tau:
                return canonical, cost, success, explored + 1
            counter += 1
            heappush(frontier, _FrontierEntry(cost, counter, canonical))
    return None


def _branch_and_bound_over_supports(
    *,
    query: OptimalRecourseInterventionQuery,
    manifold: InterventionCostManifold,
    atlas: DiscreteActionAtlas,
    scm: SCMAdapter,
    options: PlannerOptions,
) -> tuple[InterventionProgram, float, float, int] | None:
    """Support search for interval charts with cost-based lower bounds.

    This branch approximates the continuous chart of each interval domain with
    a finite grid, then solves each support's fixed-support subproblem exactly
    inside that approximation. Because the interval chart is sampled rather
    than solved analytically, the result is marked ``epsilon_optimal`` by the
    caller.
    """
    initial = InterventionProgram(actions=())
    initial_success = scm.success_value(query, initial)
    if initial_success >= query.threshold_tau:
        return initial, 0.0, initial_success, 1

    interval_grid_size = max(2, options.interval_grid_size)
    candidate_actions_by_node = _candidate_actions_by_node(
        manifold,
        interval_grid_size=interval_grid_size,
    )
    support_budget = options.support_budget or query.support_budget or len(manifold.mutable_nodes)
    mutable_nodes = tuple(
        node for node in manifold.mutable_nodes if candidate_actions_by_node.get(node)
    )

    frontier: list[tuple[float, int, tuple[str, ...]]] = []
    counter = 0
    for size in range(1, min(len(mutable_nodes), support_budget) + 1):
        for support in combinations(mutable_nodes, size):
            lower_bound = _support_lower_bound(support, manifold=manifold)
            if lower_bound == float("inf"):
                continue
            heappush(frontier, (lower_bound, counter, support))
            counter += 1

    best: tuple[InterventionProgram, float, float] | None = None
    incumbent_cost = float("inf")
    explored = 1
    while frontier and explored < options.max_expansions:
        lower_bound, _, support = heappop(frontier)
        if lower_bound > incumbent_cost - options.epsilon:
            continue
        remaining_budget = options.max_expansions - explored
        result, used = _solve_support_via_grid(
            support,
            query=query,
            manifold=manifold,
            scm=scm,
            candidate_actions_by_node=candidate_actions_by_node,
            max_evaluations=max(0, remaining_budget),
            incumbent_cost=incumbent_cost,
            epsilon=options.epsilon,
        )
        explored += used
        if result is None:
            continue
        program, cost, success = result
        if best is None or cost < best[1] - options.epsilon:
            best = (program, cost, success)
            incumbent_cost = cost

    if best is None:
        return None
    program, cost, success = best
    return program, cost, success, explored


def _best_first_support_search(
    *,
    query: OptimalRecourseInterventionQuery,
    manifold: InterventionCostManifold,
    atlas: DiscreteActionAtlas,
    scm: SCMAdapter,
    options: PlannerOptions,
) -> tuple[InterventionProgram, float, float, int] | None:
    """Heuristic fallback over a coarsely sampled mixed-domain atlas."""
    heuristic_grid_size = options.heuristic_interval_grid_size
    if heuristic_grid_size is None:
        heuristic_grid_size = max(3, (options.interval_grid_size + 1) // 2)
    sampled_atlas = _build_sampled_atlas(
        manifold,
        interval_grid_size=heuristic_grid_size,
    )
    return exact_graph_search(
        query=query,
        manifold=manifold,
        atlas=sampled_atlas,
        scm=scm,
        options=options,
    )


branch_and_bound_over_supports = _branch_and_bound_over_supports
best_first_support_search = _best_first_support_search


def _fixed_support_is_convex(manifold: InterventionCostManifold) -> bool:
    return any(domain.kind == "interval" for domain in manifold.domains) and all(
        cost.cost_kind in {"constant", "linear", "quadratic"} for cost in manifold.primitive_costs
    )


def _solver_contract_surface(
    solver_status: RecourseSolverStatus,
    *,
    explored: int | None = None,
) -> dict[str, Any]:
    if solver_status is RecourseSolverStatus.EXACT:
        return {
            "tractable_subfamily": RecourseTractableSubfamily.FINITE_DISCRETE_ATLAS,
            "complexity_class": RecourseComplexityClass.POLYNOMIAL_GRAPH_SEARCH,
            "uniqueness_status": RecourseUniquenessStatus.UNKNOWN,
            "optimality_certificate_kind": RecourseOptimalityCertificateKind.EXACT_GRAPH_SEARCH,
            "kill_rule_decision": None,
            "metadata": {
                "tractable_scope": "finite_discrete_atlas",
                "supports_explored": explored,
            },
        }
    if solver_status is RecourseSolverStatus.EPSILON_OPTIMAL:
        return {
            "tractable_subfamily": RecourseTractableSubfamily.FIXED_SUPPORT_CONVEX_INTERVAL,
            "complexity_class": RecourseComplexityClass.EPSILON_BRANCH_AND_BOUND,
            "uniqueness_status": RecourseUniquenessStatus.UNKNOWN,
            "optimality_certificate_kind": RecourseOptimalityCertificateKind.EPSILON_BRANCH_AND_BOUND,
            "kill_rule_decision": None,
            "metadata": {
                "tractable_scope": "fixed_support_convex_interval",
                "supports_explored": explored,
            },
        }
    return {
        "tractable_subfamily": RecourseTractableSubfamily.HEURISTIC_FRONTIER,
        "complexity_class": RecourseComplexityClass.NP_HARD_GENERAL_CASE,
        "uniqueness_status": RecourseUniquenessStatus.NOT_CERTIFIED,
        "optimality_certificate_kind": RecourseOptimalityCertificateKind.HEURISTIC_FRONTIER,
        "kill_rule_decision": "heuristic_general_case_deferred",
        "metadata": {
            "tractable_scope": "heuristic_frontier",
            "supports_explored": explored,
            "kill_rule": "heuristic_only",
        },
    }


def _blocked_bundle(
    *,
    query_ref: OptimalRecourseInterventionQueryRef,
    proof_ref: RecourseProofBundleRef,
    readiness_cap: RecourseReadinessCap,
    reason: str,
    status: RecourseSolverStatus,
    metadata: dict[str, Any] | None = None,
) -> OptimalRecourseInterventionBundle:
    return OptimalRecourseInterventionBundle(
        query_ref=query_ref,
        proof_ref=proof_ref,
        action=InterventionProgram(actions=()),
        achieved_cost=0.0,
        achieved_success_value=0.0,
        feasibility_certificate_ref=None,
        solver_status=status,
        readiness_cap=readiness_cap,
        blocked_reason=reason,
        candidate_supports_explored=0,
        metadata=dict(metadata or {}),
    )


def optimal_recourse_intervention(
    *,
    query: OptimalRecourseInterventionQuery,
    query_ref: OptimalRecourseInterventionQueryRef,
    manifold: InterventionCostManifold,
    scm: SCMAdapter,
    options: PlannerOptions | None = None,
    feasibility_certificate_ref: RecourseFeasibilityCertificateRef | None = None,
) -> tuple[
    RecourseProofBundle,
    OptimalRecourseInterventionBundle,
    RecourseFeasibilityCertificate | None,
]:
    """End-to-end optimal-recourse intervention solver.

    Returns the proof bundle, the planning bundle, and the feasibility
    certificate (when the planner succeeded). The caller is responsible for
    persisting each artifact and plugging the certificate ref back into the
    planning bundle if needed.
    """
    options = options or PlannerOptions(support_budget=query.support_budget)

    status, functional_ref, proof_trace = scm.identify_success_functional(query)
    proof_bundle = build_recourse_proof_bundle(
        query_ref=query_ref,
        scm_ref=manifold.scm_ref,
        semantics=query.semantics,
        success_mode=query.success_mode,
        recoverability_status=status,
        mutable_nodes=manifold.mutable_nodes,
        immutable_nodes=manifold.immutable_nodes,
        success_functional_ref=functional_ref,
        proof_trace=tuple(proof_trace),
    )

    if status is RecourseRecoverabilityStatus.NONRECOVERABLE:
        proof_bundle = proof_bundle.model_copy(
            update={
                "kill_rule_decision": "nonrecoverable_success_functional_deferred",
                "metadata": {
                    **proof_bundle.metadata,
                    "failure_surface_code": "nonrecoverable_success_functional",
                    "kill_rule": "nonrecoverable_success_functional_deferred",
                },
            }
        )
        proof_ref = RecourseProofBundleRef(
            artifact_id="sha256:" + "0" * 64,
            kind="ir.recourse_proof_bundle",
            media_type="application/json",
        )
        bundle = _blocked_bundle(
            query_ref=query_ref,
            proof_ref=proof_ref,
            readiness_cap=proof_bundle.readiness_cap,
            reason="nonrecoverable_success_functional",
            status=RecourseSolverStatus.BLOCKED_NONRECOVERABLE,
            metadata={
                "failure_surface_code": "nonrecoverable_success_functional",
                "kill_rule": "nonrecoverable_success_functional_deferred",
            },
        )
        return proof_bundle, bundle, None

    atlas = build_discrete_atlas(manifold)
    has_interval_domains = _has_interval_domains(manifold)

    if atlas.is_finite_discrete and not has_interval_domains:
        result = exact_graph_search(
            query=query,
            manifold=manifold,
            atlas=atlas,
            scm=scm,
            options=options,
        )
        solver_status_if_found = RecourseSolverStatus.EXACT
    elif _fixed_support_is_convex(manifold):
        result = _branch_and_bound_over_supports(
            query=query,
            manifold=manifold,
            atlas=atlas,
            scm=scm,
            options=options,
        )
        solver_status_if_found = RecourseSolverStatus.EPSILON_OPTIMAL
    else:
        result = _best_first_support_search(
            query=query,
            manifold=manifold,
            atlas=atlas,
            scm=scm,
            options=options,
        )
        solver_status_if_found = RecourseSolverStatus.HEURISTIC

    placeholder_proof_ref = RecourseProofBundleRef(
        artifact_id="sha256:" + "0" * 64,
        kind="ir.recourse_proof_bundle",
        media_type="application/json",
    )

    if result is None:
        proof_bundle = proof_bundle.model_copy(
            update={
                "kill_rule_decision": "no_feasible_action_found",
                "metadata": {
                    **proof_bundle.metadata,
                    "failure_surface_code": "no_feasible_action_found",
                },
            }
        )
        bundle = _blocked_bundle(
            query_ref=query_ref,
            proof_ref=placeholder_proof_ref,
            readiness_cap=proof_bundle.readiness_cap,
            reason="no_feasible_action_found",
            status=RecourseSolverStatus.BLOCKED_INFEASIBLE,
            metadata={"failure_surface_code": "no_feasible_action_found"},
        )
        return proof_bundle, bundle, None

    action, cost, achieved_success, explored = result
    structural_consistency_ok = scm.replay_structural_consistency(action)
    surface = _solver_contract_surface(solver_status_if_found, explored=explored)

    optimality_status: Literal["exact", "epsilon_optimal", "heuristic"]
    if solver_status_if_found is RecourseSolverStatus.EXACT:
        optimality_status = "exact"
    elif solver_status_if_found is RecourseSolverStatus.EPSILON_OPTIMAL:
        optimality_status = "epsilon_optimal"
    else:
        optimality_status = "heuristic"

    proof_readiness_cap = (
        RecourseReadinessCap.PROOF_ONLY
        if solver_status_if_found is RecourseSolverStatus.HEURISTIC
        else proof_bundle.readiness_cap
    )
    proof_bundle = proof_bundle.model_copy(
        update={
            "readiness_cap": proof_readiness_cap,
            "tractable_subfamily": surface["tractable_subfamily"],
            "complexity_class": surface["complexity_class"],
            "uniqueness_status": surface["uniqueness_status"],
            "optimality_certificate_kind": surface["optimality_certificate_kind"],
            "kill_rule_decision": surface["kill_rule_decision"],
            "metadata": {
                **proof_bundle.metadata,
                **surface["metadata"],
                **(
                    {"failure_surface_code": "heuristic_only"}
                    if solver_status_if_found is RecourseSolverStatus.HEURISTIC
                    else {}
                ),
            },
        }
    )

    certificate = build_feasibility_certificate(
        action=action,
        factual_unit_ref=query.factual_unit_ref,
        scm_ref=manifold.scm_ref,
        semantics=query.semantics,
        manifold=manifold,
        achieved_success_value=achieved_success,
        threshold_tau=query.threshold_tau,
        success_measure=query.success_mode,
        structural_consistency_ok=structural_consistency_ok,
        optimality_status=optimality_status,
        optimality_gap=0.0 if optimality_status == "exact" else None,
        tractable_subfamily=surface["tractable_subfamily"],
        complexity_class=surface["complexity_class"],
        uniqueness_status=surface["uniqueness_status"],
        optimality_certificate_kind=surface["optimality_certificate_kind"],
        kill_rule_decision=surface["kill_rule_decision"],
        metadata={
            **surface["metadata"],
            **(
                {"failure_surface_code": "heuristic_only"}
                if solver_status_if_found is RecourseSolverStatus.HEURISTIC
                else {}
            ),
        },
    )

    placeholder_certificate_ref = feasibility_certificate_ref or RecourseFeasibilityCertificateRef(
        artifact_id="sha256:" + "0" * 64,
        kind="ir.recourse_feasibility_certificate",
        media_type="application/json",
    )

    bundle = OptimalRecourseInterventionBundle(
        query_ref=query_ref,
        proof_ref=placeholder_proof_ref,
        action=action,
        achieved_cost=cost,
        achieved_success_value=achieved_success,
        feasibility_certificate_ref=placeholder_certificate_ref,
        solver_status=solver_status_if_found,
        readiness_cap=proof_readiness_cap,
        candidate_supports_explored=explored,
        metadata={
            **surface["metadata"],
            **(
                {"failure_surface_code": "heuristic_only"}
                if solver_status_if_found is RecourseSolverStatus.HEURISTIC
                else {}
            ),
        },
    )
    return proof_bundle, bundle, certificate


__all__ = [
    "DiscreteActionAtlas",
    "PlannerOptions",
    "SCMAdapter",
    "best_first_support_search",
    "branch_and_bound_over_supports",
    "build_discrete_atlas",
    "exact_graph_search",
    "optimal_recourse_intervention",
    "program_cost",
]
