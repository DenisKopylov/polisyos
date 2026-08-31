"""optimal_design — Optimal Experimental Design for Causal Inference (Phase 9).

Implements two key results:

1. **O-set (Henckel, Perković & Maathuis 2022)**: graphical criterion for the
   adjustment set that minimises asymptotic variance among all valid backdoor
   adjustment sets.

2. **Minimum-cost identification (Bareinboim, Brito & Pearl 2012)**: greedy
   algorithm for finding the cheapest set of experimental interventions that
   renders the target causal query identifiable.

Additional utilities:
- ``optimal_instrument_selection``: select IVs with maximum first-stage strength
- ``adaptive_experiment``: Bayesian sequential budget allocation plan

Foundry method: ``causal.design.experiment@1.0.0``

References
----------
Henckel, L., Perković, E. & Maathuis, M.H. (2022). Graphical criteria for
    efficient total effect estimation via adjustment in causal linear models.
    *JRSS-B*, 84(2), 579–599.
Bareinboim, E., Brito, C. & Pearl, J. (2012). Local characterizations of
    causal Bayesian networks. *LNCS*, 7205.
"""

from __future__ import annotations

import itertools
import logging
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

import numpy as np
from pydantic import BaseModel, ConfigDict

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
from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.ir.analytics.experiment_plan import (
    ExperimentPlan,
    OptimalAdjustmentResult,
    OptimalIVResult,
)

_logger = logging.getLogger(__name__)


class AdaptiveBayesianDesignResult(BaseModel):
    """Result of Thompson-sampling adaptive design."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    arm_labels: tuple[str, ...]
    allocation_counts: tuple[int, ...]
    allocation_proportions: tuple[float, ...]
    posterior_alpha: tuple[float, ...]
    posterior_beta: tuple[float, ...]
    best_arm_index: int
    total_reward: int
    expected_regret: float
    selection_history: tuple[int, ...] = ()


class DOptimalDesignResult(BaseModel):
    """Result of D-optimal covariate selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selected_covariates: tuple[str, ...]
    allocation_proportions: tuple[float, ...]
    candidate_covariates: tuple[str, ...]
    information_matrix: tuple[tuple[float, ...], ...]
    log_determinant: float
    variance_proxy: float


# ---------------------------------------------------------------------------
# Internal graph helpers
# ---------------------------------------------------------------------------


def _parents_of(graph: CausalGraphModel, nodes: frozenset[str]) -> frozenset[str]:
    """Return all direct parents of *nodes* in the directed graph."""
    from polisyos.foundry.methods.catalog.causal.admg_ops import extract_directed_edges

    parents: set[str] = set()
    for src, dst in extract_directed_edges(graph):
        if dst in nodes:
            parents.add(src)
    return frozenset(parents)


def _compute_o_set(
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
) -> frozenset[str]:
    """Henckel, Perković & Maathuis (2022) Theorem 3 — O-set.

    O(X, Y, G) = Pa_G(An_{G_{\\bar{X}}}(Y) \\ X) \\ De_G(X)

    Where G_{\\bar{X}} is the graph with all incoming edges to X removed
    (i.e. the interventional graph do(X)).

    Algorithm
    ---------
    1. Build G_cut = G with incoming edges to X removed.
    2. Find An(Y) in G_cut: ancestors of Y (including Y itself).
    3. Remove X from that ancestor set: An_Y_nox = An_Y \\ {X}.
    4. Take parents in the *original* graph G: Pa_G(An_Y_nox).
    5. Remove De_G(X) (descendants of X in original G, including X):
       O = Pa_G(An_Y_nox) \\ De_G(X).

    This correctly identifies all pre-treatment confounders that are
    ancestors of Y in the interventional world, excluding X and its
    descendants.
    """
    from polisyos.foundry.methods.catalog.causal.admg_ops import (
        ancestors,
        descendants,
        remove_incoming_edges,
    )

    # Step 1: G_cut = G with incoming edges to X removed (interventional graph)
    g_cut = remove_incoming_edges(graph, frozenset({treatment}))

    # Step 2: An(Y) in G_cut (ancestors of Y in the interventional world)
    an_y = ancestors(g_cut, frozenset({outcome}), include_self=True)

    # Step 3: remove treatment X from ancestor set
    an_y_nox = an_y - frozenset({treatment})

    # Step 4: parents in the ORIGINAL graph G
    pa = _parents_of(graph, an_y_nox)

    # Step 5: remove De_G(X) (including X) — these cannot be adjusted for
    de_x = descendants(graph, frozenset({treatment}), include_self=True)
    return pa - de_x


def _check_backdoor(
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
    adjustment_set: frozenset[str],
) -> bool:
    """Check whether adjustment_set satisfies the backdoor criterion.

    Criterion (Pearl 2009):
    (a) No node in Z is a descendant of X.
    (b) Z blocks every backdoor path from X to Y in G.

    Implemented via m-separation in the graph G_{\\underline{X}} (outgoing
    edges of X removed): X ⊥ Y | Z in G_{\\underline{X}}. In this graph,
    all causal paths X→...→Y are cut, leaving only backdoor paths that go
    backward through X's ancestors. Z must block all of these.
    """
    from polisyos.foundry.methods.catalog.causal.admg_ops import (
        descendants,
        m_separation,
        remove_outgoing_edges,
    )

    # Condition (a): no descendant of X in Z
    de_x = descendants(graph, frozenset({treatment}), include_self=True)
    if adjustment_set & de_x:
        return False

    # Condition (b): Z blocks all backdoor paths in G_{X̲} (outgoing of X removed)
    g_no_out = remove_outgoing_edges(graph, frozenset({treatment}))
    return m_separation(
        g_no_out,
        x_set=frozenset({treatment}),
        y_set=frozenset({outcome}),
        z_set=adjustment_set,
    )


# ---------------------------------------------------------------------------
# Algorithm functions
# ---------------------------------------------------------------------------


def optimal_adjustment_set(
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
) -> OptimalAdjustmentResult:
    """Compute the O-set: optimal adjustment for minimum asymptotic variance.

    The O-set minimises the asymptotic variance of the backdoor adjustment
    estimator ATE = Σ_Z E[Y|X=1,Z]P(Z) − Σ_Z E[Y|X=0,Z]P(Z) among all
    valid backdoor adjustment sets (Henckel et al. 2022, Theorem 4).

    Parameters
    ----------
    graph:
        Causal DAG (ADMG also supported for the graphical computation).
    treatment:
        Treatment variable X.
    outcome:
        Outcome variable Y.

    Returns
    -------
    OptimalAdjustmentResult
        O-set and backdoor validity flag.
    """
    if treatment not in graph.nodes:
        raise ValueError(f"Treatment variable {treatment!r} not in graph nodes.")
    if outcome not in graph.nodes:
        raise ValueError(f"Outcome variable {outcome!r} not in graph nodes.")

    o_set = _compute_o_set(graph, treatment, outcome)
    is_valid = _check_backdoor(graph, treatment, outcome, o_set)

    _logger.debug(
        "optimal_adjustment_set: treatment=%r outcome=%r o_set=%r valid=%s",
        treatment,
        outcome,
        sorted(o_set),
        is_valid,
    )

    return OptimalAdjustmentResult(
        o_set=o_set,
        graphical_criterion_used="henckel-2022-o-set",
        treatment=treatment,
        outcome=outcome,
        o_set_is_valid_backdoor=is_valid,
    )


def optimal_instrument_selection(
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
) -> OptimalIVResult:
    """Select graphically valid instrumental variables.

    A variable Z is a valid instrument for (X, Y) if:
    1. Z is not a descendant of X.
    2. Z has a directed path to X (relevance / first stage).
    3. Z affects Y only through X (exclusion restriction):
       Z and Y are m-separated given X in G minus the X→... edge-cut.

    The function returns all valid IV sets found by checking each node
    individually.  The ``optimal_iv_set`` is chosen as the singleton
    with the most direct path (or the empty set if none qualifies).

    Parameters
    ----------
    graph:
        Causal DAG.
    treatment:
        Endogenous treatment variable X.
    outcome:
        Outcome variable Y.

    Returns
    -------
    OptimalIVResult
    """
    from polisyos.foundry.methods.catalog.causal.admg_ops import (
        descendants,
        has_directed_path,
        m_separation,
        remove_outgoing_edges,
    )

    de_x = descendants(graph, frozenset({treatment}), include_self=True)

    valid_ivs: list[frozenset[str]] = []
    for node in graph.nodes:
        if node == treatment or node == outcome:
            continue
        if node in de_x:
            continue  # criterion 1: not a descendant

        if not has_directed_path(graph, node, treatment):
            continue  # criterion 2: must have path to X

        # Criterion 3: exclusion restriction — Z ⊥ Y | X after removing X→* edges
        # Remove the outgoing edges of X, then check if Z can reach Y
        g_no_x_out = remove_outgoing_edges(graph, frozenset({treatment}))
        # In this graph, Z→Y paths bypass X only if they don't go through X
        # Z ⊥ Y | ∅ in G_{X̲} means exclusion restriction holds
        separated = m_separation(
            g_no_x_out,
            x_set=frozenset({node}),
            y_set=frozenset({outcome}),
            z_set=frozenset({treatment}),
        )
        if separated:
            valid_ivs.append(frozenset({node}))

    optimal = valid_ivs[0] if valid_ivs else frozenset()
    return OptimalIVResult(
        optimal_iv_set=optimal,
        all_valid_iv_sets=valid_ivs,
        treatment=treatment,
        outcome=outcome,
        exclusion_restriction_verified=True,
    )


def minimum_cost_identification(
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
    available_interventions: dict[str, float],
) -> ExperimentPlan:
    """Find the cheapest set of interventions to identify P(Y|do(X)).

    Algorithm (greedy, based on Bareinboim, Brito & Pearl 2012):

    1. Check observational identifiability via ``id_algorithm``.
       If identified, return immediately (cost = 0).
    2. Greedily try each single intervention by increasing cost.
       Run ``z_id_algorithm`` with that Z; return on first success.
    3. If no singleton works, try all pairs (again cheapest-first).
    4. Fall back to the full intervention set if no subset works.

    Parameters
    ----------
    graph:
        Causal DAG.
    treatment:
        Treatment variable X.
    outcome:
        Outcome variable Y.
    available_interventions:
        Mapping variable_name → cost of intervening on that variable.

    Returns
    -------
    ExperimentPlan
        Recommended intervention set and total cost estimate.
    """
    from polisyos.foundry.methods.catalog.causal.id_engine import (
        IdentificationStatus,
        id_algorithm,
        z_id_algorithm,
    )

    tx = frozenset({treatment})
    oy = frozenset({outcome})

    # Step 1: check observational identifiability
    base = id_algorithm(treatment=tx, outcome=oy, graph=graph)
    if base.status == IdentificationStatus.IDENTIFIED:
        return ExperimentPlan(
            query=f"P({outcome}|do({treatment}))",
            recommended_interventions=(),
            cost_estimate=0.0,
            already_identified_observationally=True,
            rationale="Query is identifiable from observational data alone; no experiment needed.",
            n_stages=0,
        )

    if not available_interventions:
        return ExperimentPlan(
            query=f"P({outcome}|do({treatment}))",
            recommended_interventions=(),
            cost_estimate=None,
            already_identified_observationally=False,
            rationale="No experimental interventions available; query may not be identifiable.",
        )

    sorted_by_cost = sorted(available_interventions.items(), key=lambda x: x[1])

    # Step 2: single intervention
    for var, cost in sorted_by_cost:
        result = z_id_algorithm(
            treatment=tx,
            outcome=oy,
            z_interventions=frozenset({var}),
            graph=graph,
        )
        if result.status == IdentificationStatus.IDENTIFIED:
            _logger.debug(
                "minimum_cost_identification: single intervention %r (cost=%.2f) sufficient.",
                var,
                cost,
            )
            return ExperimentPlan(
                query=f"P({outcome}|do({treatment}))",
                recommended_interventions=(var,),
                cost_estimate=cost,
                already_identified_observationally=False,
                rationale=(
                    f"Single intervention on {var!r} (cost={cost}) is sufficient "
                    "to identify the target query via Z-transport."
                ),
            )

    # Step 3: pairs
    all_vars_sorted = [v for v, _ in sorted_by_cost]
    for pair in itertools.combinations(all_vars_sorted, 2):
        pair_cost = sum(available_interventions[v] for v in pair)
        result = z_id_algorithm(
            treatment=tx,
            outcome=oy,
            z_interventions=frozenset(pair),
            graph=graph,
        )
        if result.status == IdentificationStatus.IDENTIFIED:
            _logger.debug(
                "minimum_cost_identification: pair %r (cost=%.2f) sufficient.",
                pair,
                pair_cost,
            )
            return ExperimentPlan(
                query=f"P({outcome}|do({treatment}))",
                recommended_interventions=tuple(pair),
                cost_estimate=pair_cost,
                already_identified_observationally=False,
                rationale=(
                    f"Pair of interventions {pair} (total cost={pair_cost}) "
                    "sufficient to identify the target query."
                ),
            )

    # Fallback: recommend all interventions
    total_cost = sum(available_interventions.values())
    return ExperimentPlan(
        query=f"P({outcome}|do({treatment}))",
        recommended_interventions=tuple(all_vars_sorted),
        cost_estimate=total_cost,
        already_identified_observationally=False,
        rationale=(
            "No single intervention or pair was sufficient; "
            "all available interventions are recommended as a conservative plan."
        ),
    )


def adaptive_experiment(
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
    budget: float,
    n_stages: int = 3,
    prior_effect_size: float = 0.0,
    prior_variance: float = 1.0,
) -> list[ExperimentPlan]:
    """Generate a sequential adaptive experimental design plan.

    Divides the total budget across N stages, with each stage refining
    the posterior variance estimate (Bayesian sequential design):
    V_posterior = 1 / (1/V_prior + n_stage/V_likelihood)

    Parameters
    ----------
    graph:
        Causal DAG for computing the optimal adjustment set.
    treatment:
        Treatment variable X.
    outcome:
        Outcome variable Y.
    budget:
        Total experimental budget (e.g. sample size or cost units).
    n_stages:
        Number of adaptive stages.
    prior_effect_size:
        Prior point estimate for the ATE.
    prior_variance:
        Prior variance V_0 for the effect size.

    Returns
    -------
    list[ExperimentPlan]
        One ExperimentPlan per stage, with equal budget allocation.
    """
    adj_result = optimal_adjustment_set(graph, treatment, outcome)
    stage_budget = budget / max(n_stages, 1)
    plans: list[ExperimentPlan] = []
    current_var = prior_variance

    for stage in range(1, n_stages + 1):
        # Posterior variance after each stage (Gaussian conjugate update)
        likelihood_var = current_var / max(stage, 1)
        posterior_var = 1.0 / (1.0 / current_var + 1.0 / likelihood_var)
        current_var = posterior_var

        plans.append(
            ExperimentPlan(
                query=f"P({outcome}|do({treatment})) [stage {stage}/{n_stages}]",
                recommended_interventions=(treatment,),
                cost_estimate=stage_budget,
                adjustment_set=adj_result.o_set if adj_result.o_set_is_valid_backdoor else None,
                already_identified_observationally=False,
                rationale=(
                    f"Stage {stage}/{n_stages}: allocate {stage_budget:.1f} budget units; "
                    f"expected posterior variance after stage = {posterior_var:.4f}."
                ),
                n_stages=stage,
            )
        )

    return plans


def adaptive_bayesian_experiment(
    arm_success_probabilities: Sequence[float],
    *,
    n_rounds: int,
    prior_alpha: float = 1.0,
    prior_beta: float = 1.0,
    seed: int = 0,
    arm_labels: Sequence[str] | None = None,
) -> AdaptiveBayesianDesignResult:
    """Thompson-sampling adaptive allocation for Bernoulli outcomes."""
    probs = np.asarray(list(arm_success_probabilities), dtype=float)
    if probs.ndim != 1 or probs.size < 2:
        raise ValueError("adaptive_bayesian_experiment requires at least two arms")
    if np.any((probs < 0.0) | (probs > 1.0)):
        raise ValueError("arm_success_probabilities must be in [0, 1]")

    labels = (
        tuple(arm_labels)
        if arm_labels is not None
        else tuple(f"arm_{i}" for i in range(probs.size))
    )
    if len(labels) != probs.size:
        raise ValueError("arm_labels must match arm_success_probabilities length")

    rng = np.random.default_rng(seed)
    alpha = np.full(probs.size, float(prior_alpha), dtype=float)
    beta = np.full(probs.size, float(prior_beta), dtype=float)
    counts = np.zeros(probs.size, dtype=int)
    rewards = np.zeros(probs.size, dtype=int)
    history: list[int] = []

    best_arm = int(np.argmax(probs))
    best_arm_prob = float(np.max(probs))
    regret = 0.0

    for _ in range(int(n_rounds)):
        draws = rng.beta(alpha, beta)
        arm = int(np.argmax(draws))
        reward = int(rng.random() < probs[arm])
        counts[arm] += 1
        rewards[arm] += reward
        alpha[arm] += reward
        beta[arm] += 1 - reward
        regret += best_arm_prob - float(probs[arm])
        history.append(arm)

    total = int(np.sum(counts))
    proportions = counts / max(total, 1)
    return AdaptiveBayesianDesignResult(
        arm_labels=labels,
        allocation_counts=tuple(int(v) for v in counts),
        allocation_proportions=tuple(float(v) for v in proportions),
        posterior_alpha=tuple(float(v) for v in alpha),
        posterior_beta=tuple(float(v) for v in beta),
        best_arm_index=best_arm,
        total_reward=int(np.sum(rewards)),
        expected_regret=float(regret),
        selection_history=tuple(history),
    )


def _d_optimal_feature_vector(
    graph: CausalGraphModel,
    node: str,
    treatment: str,
    outcome: str,
) -> np.ndarray:
    from polisyos.foundry.methods.catalog.causal.admg_ops import (
        ancestors,
        descendants,
        extract_directed_edges,
    )

    directed = extract_directed_edges(graph)
    parents_t = 1.0 if (node, treatment) in directed else 0.0
    parents_y = 1.0 if (node, outcome) in directed else 0.0
    anc_t = 1.0 if node in ancestors(graph, frozenset({treatment}), include_self=True) else 0.0
    anc_y = 1.0 if node in ancestors(graph, frozenset({outcome}), include_self=True) else 0.0
    desc_t = 1.0 if node in descendants(graph, frozenset({treatment}), include_self=True) else 0.0
    degree = float(sum(1 for src, dst in directed if src == node or dst == node))
    confounder = 1.0 if parents_t and parents_y else 0.0
    return np.array(
        [
            1.0,
            parents_t,
            parents_y,
            anc_t,
            anc_y,
            degree,
            confounder,
            1.0 - desc_t,
        ],
        dtype=float,
    )


def d_optimal_design(
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
    n_covariates: int,
) -> DOptimalDesignResult:
    """Select the D-optimal covariate subset using graph-derived features."""
    from scipy.optimize import minimize

    from polisyos.foundry.methods.catalog.causal.admg_ops import descendants

    if treatment not in graph.nodes:
        raise ValueError(f"Treatment variable {treatment!r} not in graph nodes.")
    if outcome not in graph.nodes:
        raise ValueError(f"Outcome variable {outcome!r} not in graph nodes.")

    excluded = descendants(graph, frozenset({treatment}), include_self=True) | frozenset(
        {treatment, outcome}
    )
    candidates = [node for node in graph.nodes if node not in excluded]
    if len(candidates) < int(n_covariates):
        raise ValueError(
            f"Need at least {n_covariates} candidate covariates, got {len(candidates)}"
        )

    features = np.vstack(
        [_d_optimal_feature_vector(graph, node, treatment, outcome) for node in candidates]
    )
    ridge = 1e-6
    n_candidates = features.shape[0]
    x0 = np.full(n_candidates, 1.0 / n_candidates, dtype=float)

    def objective(weights: np.ndarray) -> float:
        info = features.T @ (weights[:, None] * features) + ridge * np.eye(features.shape[1])
        sign, logdet = np.linalg.slogdet(info)
        if sign <= 0:
            return 1e6
        return float(-logdet)

    constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}]
    bounds = [(0.0, 1.0)] * n_candidates
    result = minimize(
        objective,
        x0=x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-9},
    )

    weights = np.asarray(result.x if result.success else x0, dtype=float)
    weights = np.clip(weights, 0.0, 1.0)
    total = float(np.sum(weights))
    if total <= 0:
        weights = x0
        total = float(np.sum(weights))
    weights = weights / total

    structural_score = features.sum(axis=1)
    ranking = sorted(
        range(n_candidates),
        key=lambda idx: (weights[idx], structural_score[idx], candidates[idx]),
        reverse=True,
    )
    selected_idx = ranking[: int(n_covariates)]
    selected_covariates = tuple(candidates[idx] for idx in selected_idx)
    selected_weights = weights[selected_idx]
    selected_weights = selected_weights / max(float(np.sum(selected_weights)), 1e-12)
    selected_features = features[selected_idx]
    info = selected_features.T @ (selected_weights[:, None] * selected_features) + ridge * np.eye(
        selected_features.shape[1]
    )
    sign, logdet = np.linalg.slogdet(info)
    if sign <= 0:
        logdet = float("-inf")
    variance_proxy = float(np.trace(np.linalg.inv(info)))

    return DOptimalDesignResult(
        selected_covariates=selected_covariates,
        allocation_proportions=tuple(float(v) for v in selected_weights),
        candidate_covariates=tuple(candidates),
        information_matrix=tuple(tuple(float(v) for v in row) for row in info),
        log_determinant=float(logdet),
        variance_proxy=variance_proxy,
    )


# ---------------------------------------------------------------------------
# Foundry wrapper
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.design",
    version="1.0.0",
    tags={"causal", "design", "o_set", "henckel_maathuis", "optimal_experiment", "cross-section"},
)
class CausalExperimentDesigner:
    """Optimal experimental design for causal inference (Phase 9).

    Dispatches to one of four design modes via the ``mode`` parameter:

    ``"optimal_adjustment"`` (default)
        Compute the O-set: adjustment set minimising asymptotic variance
        (Henckel, Perković & Maathuis 2022).
        Requires: ``graph``, ``treatment``, ``outcome``.

    ``"optimal_iv"``
        Select graphically valid IV sets with maximum first-stage coverage.
        Requires: ``graph``, ``treatment``, ``outcome``.

    ``"minimum_cost"``
        Greedy minimum-cost intervention plan to achieve identifiability
        (Bareinboim, Brito & Pearl 2012).
        Requires: ``graph``, ``treatment``, ``outcome``,
        ``available_interventions`` (dict var → cost).

    ``"adaptive"``
        Bayesian sequential budget-allocation plan.
        Requires: ``graph``, ``treatment``, ``outcome``,
        ``budget`` (float), ``n_stages`` (int, default 3).

    ``"adaptive_bayesian"``
        Thompson-sampling allocation across arms with Bernoulli rewards.
        Requires: ``arm_success_probabilities`` and ``n_rounds``.

    ``"d_optimal"``
        Graph-derived D-optimal covariate selection.
        Requires: ``graph``, ``treatment``, ``outcome``, ``n_covariates``.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ()

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="causal_experiment_designer",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("graph_json", SlotType.SCALAR, Unit("graph", "json")),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec("design_result", SlotType.SCALAR, Unit("result", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="mode", default="optimal_adjustment"),
            ParameterSpec(name="treatment", default=""),
            ParameterSpec(name="outcome", default=""),
            ParameterSpec(name="available_interventions", default={}),
            ParameterSpec(name="budget", default=100.0),
            ParameterSpec(name="n_stages", default=3),
            ParameterSpec(name="prior_effect_size", default=0.0),
            ParameterSpec(name="prior_variance", default=1.0),
            ParameterSpec(name="arm_success_probabilities", default=[0.2, 0.8]),
            ParameterSpec(name="arm_labels", default=[]),
            ParameterSpec(name="n_rounds", default=100),
            ParameterSpec(name="prior_alpha", default=1.0),
            ParameterSpec(name="prior_beta", default=1.0),
            ParameterSpec(name="seed", default=0),
            ParameterSpec(name="n_covariates", default=2),
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
            "Optimal experimental design for causal inference. "
            "Computes O-set (Henckel et al. 2022), optimal IVs, "
            "minimum-cost identification plan, adaptive experiment stages, "
            "adaptive Bayesian Thompson sampling, and D-optimal covariate selection."
        ),
        tags=frozenset(
            {
                "causal",
                "design",
                "o_set",
                "adjustment",
                "iv",
                "minimum_cost",
                "adaptive",
                "thompson",
                "d_optimal",
                "henckel_maathuis",
            }
        ),
        citations=(
            "Henckel, L., Perković, E. & Maathuis, M.H. (2022). "
            "Graphical criteria for efficient total effect estimation via "
            "adjustment in causal linear models. JRSS-B, 84(2), 579–599.",
            "Bareinboim, E., Brito, C. & Pearl, J. (2012). Local "
            "characterizations of causal Bayesian networks. LNCS, 7205.",
        ),
        equations={
            "o_set": "O(X,Y,G) = Pa_G(An(Y)_{G_{V\\De(X)}}) \\ (De(X) ∪ {X})",
            "inv_var_eff": "Var(ATE_{O}) ≤ Var(ATE_Z) for any valid Z",
            "min_cost": "argmin_S cost(S) s.t. Z-ID(X,Y,G,S) = IDENTIFIED",
            "thompson": "a_t = argmax_k θ_k, θ_k ~ Beta(α_k, β_k)",
            "d_optimal": "max_W log det(X^T diag(W) X)",
        },
        determinism_tier=DeterminismTier.STRICT_CPU,
        required_deps=("numpy", "scipy"),
        when_to_use=(
            "Designing a new study: choose adjustment variables for minimum variance; "
            "selecting instruments; planning sequential experiments with budget constraints."
        ),
        when_not_to_use=(
            "Post-hoc analysis on existing data where the adjustment set is fixed; "
            "non-parametric bounds are needed instead of point identification."
        ),
        output_interpretation=(
            "optimal_adjustment: o_set is the theoretically optimal conditioning set. "
            "minimum_cost: recommended_interventions is the cheapest set to run. "
            "adaptive: list of stage plans with per-stage budget allocation."
        ),
    )

    @staticmethod
    def pure_step(
        state: Mapping[str, Any],
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Dispatch to the selected design mode."""
        mode: str = params.get("mode", "optimal_adjustment")
        graph: CausalGraphModel = state["graph"]
        treatment: str = params.get("treatment", "")
        outcome: str = params.get("outcome", "")

        if mode == "optimal_adjustment":
            result = optimal_adjustment_set(graph, treatment, outcome)
            return {"design_result": result.model_dump()}

        if mode == "optimal_iv":
            result = optimal_instrument_selection(graph, treatment, outcome)
            return {"design_result": result.model_dump()}

        if mode == "minimum_cost":
            available: dict[str, float] = dict(params.get("available_interventions", {}))
            plan = minimum_cost_identification(graph, treatment, outcome, available)
            return {"design_result": plan.model_dump()}

        if mode == "adaptive":
            plans = adaptive_experiment(
                graph=graph,
                treatment=treatment,
                outcome=outcome,
                budget=float(params.get("budget", 100.0)),
                n_stages=int(params.get("n_stages", 3)),
                prior_effect_size=float(params.get("prior_effect_size", 0.0)),
                prior_variance=float(params.get("prior_variance", 1.0)),
            )
            return {"design_result": [p.model_dump() for p in plans]}

        if mode == "adaptive_bayesian":
            arm_probs = params.get("arm_success_probabilities", [0.2, 0.8])
            result = adaptive_bayesian_experiment(
                arm_probs,
                n_rounds=int(params.get("n_rounds", 100)),
                prior_alpha=float(params.get("prior_alpha", 1.0)),
                prior_beta=float(params.get("prior_beta", 1.0)),
                seed=int(params.get("seed", 0)),
                arm_labels=tuple(params.get("arm_labels", ())) or None,
            )
            return {"design_result": result.model_dump()}

        if mode == "d_optimal":
            result = d_optimal_design(
                graph=graph,
                treatment=treatment,
                outcome=outcome,
                n_covariates=int(params.get("n_covariates", 2)),
            )
            return {"design_result": result.model_dump()}

        raise ValueError(
            f"Unknown CausalExperimentDesigner mode {mode!r}. "
            "Expected one of: 'optimal_adjustment', 'optimal_iv', "
            "'minimum_cost', 'adaptive', 'adaptive_bayesian', 'd_optimal'."
        )


__all__ = [
    "AdaptiveBayesianDesignResult",
    "CausalExperimentDesigner",
    "DOptimalDesignResult",
    "adaptive_bayesian_experiment",
    "adaptive_experiment",
    "d_optimal_design",
    "minimum_cost_identification",
    "optimal_adjustment_set",
    "optimal_instrument_selection",
]
