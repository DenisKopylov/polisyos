"""Frontier policy methods for public finance, macro, mean-field equilibrium, and policy-text analysis."""
from __future__ import annotations

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
from polisyos.scientist.agent.embedder import SentenceTransformerEmbedder, TFIDFEmbedder


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


def _coerce_vector(state: Mapping[str, Any], key: str) -> np.ndarray:
    arr = np.asarray(state[key], dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    return arr


def _coerce_matrix(state: Mapping[str, Any], key: str) -> np.ndarray:
    arr = np.asarray(state[key], dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"{key} must be a 2D matrix")
    return arr


def _normalize_weights(weights: np.ndarray) -> np.ndarray:
    positive = np.clip(np.asarray(weights, dtype=float), 0.0, None)
    total = float(np.sum(positive))
    if total <= 1.0e-12:
        raise ValueError("weights must contain positive mass")
    return positive / total


def _gini(values: np.ndarray) -> float:
    arr = np.sort(np.asarray(values, dtype=float))
    if arr.size == 0 or np.allclose(arr, 0.0):
        return 0.0
    index = np.arange(1, arr.size + 1, dtype=float)
    return float((2.0 * np.sum(index * arr) / (arr.size * np.sum(arr))) - (arr.size + 1.0) / arr.size)


def _softmax(values: np.ndarray, axis: int = -1) -> np.ndarray:
    centered = values - np.max(values, axis=axis, keepdims=True)
    exp_values = np.exp(centered)
    return exp_values / np.maximum(np.sum(exp_values, axis=axis, keepdims=True), 1.0e-12)


def _stationary_distribution(transition: np.ndarray, *, max_iter: int = 500, tol: float = 1.0e-10) -> tuple[np.ndarray, bool, int]:
    dist = np.full(transition.shape[0], 1.0 / transition.shape[0], dtype=float)
    for step in range(max_iter):
        next_dist = dist @ transition
        if np.max(np.abs(next_dist - dist)) < tol:
            return next_dist, True, step + 1
        dist = next_dist
    return dist, False, max_iter


def _cosine_similarity(query: np.ndarray, docs: np.ndarray) -> np.ndarray:
    query_norm = np.linalg.norm(query) + 1.0e-12
    doc_norms = np.linalg.norm(docs, axis=1) + 1.0e-12
    return (docs @ query) / (doc_norms * query_norm)


@foundry_method(
    namespace="policy.welfare",
    version="1.0.0",
    tags={"policy", "welfare", "sufficient-statistics", "frontier"},
)
class SufficientStatisticsWelfareEstimator:
    """Approximate welfare changes using sufficient-statistics decomposition."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="sufficient_statistics_welfare",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("mechanical_effects", SlotType.VECTOR, Unit("welfare", "delta"), shape=("n_groups",)),
                SlotSpec("revenue_effects", SlotType.VECTOR, Unit("currency", "delta"), shape=("n_groups",)),
                SlotSpec("elasticities", SlotType.VECTOR, Unit("elasticity", "value"), shape=("n_groups",)),
                SlotSpec("social_weights", SlotType.VECTOR, Unit("weight", "social"), shape=("n_groups",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec("deadweight_scale", default=0.5),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Sufficient-statistics welfare ledger combining mechanical gains, fiscal effects, and behavioral leakage.",
        tags=frozenset({"policy", "welfare", "sufficient-statistics", "frontier"}),
        citations=(
            "Chetty, R. (2009). Sufficient statistics for welfare analysis.",
            "Hendren, N. & Sprung-Keyser, B. (2020). A unified welfare analysis of government policies.",
        ),
        when_to_use="Reduced-form policy evaluation with credible elasticities and social weights but without a full structural general-equilibrium model.",
        when_not_to_use="Need full dynamic incidence, equilibrium feedbacks, or micro-founded welfare under strong distributional dynamics.",
        typical_min_obs=1,
        output_interpretation="welfare_delta aggregates mechanical gains and revenue recycling minus deadweight leakage implied by elasticities.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        mechanical = _coerce_vector(state, "mechanical_effects")
        revenue = _coerce_vector(state, "revenue_effects")
        elasticities = _coerce_vector(state, "elasticities")
        weights = _normalize_weights(_coerce_vector(state, "social_weights"))
        if not (mechanical.shape == revenue.shape == elasticities.shape == weights.shape):
            raise ValueError("all sufficient-statistics vectors must have identical shape")

        mechanical_component = float(np.dot(weights, mechanical))
        revenue_component = float(np.dot(weights, revenue))
        deadweight_scale = float(params.get("deadweight_scale", 0.5))
        behavioral_leakage = float(deadweight_scale * np.dot(weights, np.abs(revenue) * np.abs(elasticities)))
        welfare_delta = mechanical_component + revenue_component - behavioral_leakage
        return {
            "result": {
                "welfare_delta": welfare_delta,
                "mechanical_component": mechanical_component,
                "revenue_component": revenue_component,
                "behavioral_leakage": behavioral_leakage,
                "average_elasticity": float(np.dot(weights, elasticities)),
                "social_weighted_groups": int(weights.shape[0]),
            }
        }


@foundry_method(
    namespace="policy.macro",
    version="1.0.0",
    tags={"policy", "macro", "fiscal-multiplier", "frontier"},
)
class FiscalMultiplierEstimator:
    """Estimate cumulative and state-dependent fiscal multipliers from shock and outcome series."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="fiscal_multiplier",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("output_changes", SlotType.VECTOR, Unit("output", "delta"), shape=("n_periods",)),
                SlotSpec("spending_changes", SlotType.VECTOR, Unit("spending", "delta"), shape=("n_periods",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec("discount_rate", default=0.0),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Discounted cumulative multiplier and local-projection style slope for fiscal shocks.",
        tags=frozenset({"policy", "macro", "fiscal-multiplier", "frontier"}),
        citations=(
            "Ramey, V. (2019). Ten years after the financial crisis: what have we learned from the renaissance in fiscal research?",
        ),
        when_to_use="Need a compact macro summary of spending-to-output transmission under observed or simulated fiscal shocks.",
        when_not_to_use="No exogenous variation in spending, severe anticipation effects, or need for a full DSGE/HANK decomposition.",
        typical_min_obs=8,
        output_interpretation="cumulative_multiplier is the discounted output response per unit of discounted government spending. state_multipliers split the same object across regimes when slack_indicator is provided.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        output = _coerce_vector(state, "output_changes")
        spending = _coerce_vector(state, "spending_changes")
        if output.shape != spending.shape:
            raise ValueError("output_changes and spending_changes must have the same shape")
        discount_rate = float(params.get("discount_rate", 0.0))
        periods = np.arange(output.shape[0], dtype=float)
        discount = 1.0 / np.power(1.0 + discount_rate, periods)
        discounted_output = float(np.sum(output * discount))
        discounted_spending = float(np.sum(spending * discount))
        cumulative_multiplier = discounted_output / max(abs(discounted_spending), 1.0e-12)

        design = np.column_stack([np.ones(output.shape[0]), spending])
        coef, *_ = np.linalg.lstsq(design, output, rcond=None)
        state_multipliers: dict[str, float] = {}
        slack_raw = state.get("slack_indicator")
        if slack_raw is not None:
            slack = np.asarray(slack_raw, dtype=float)
            if slack.shape != output.shape:
                raise ValueError("slack_indicator must align with output_changes")
            for label, mask in (("slack", slack > 0.5), ("tight", slack <= 0.5)):
                if int(np.sum(mask)) >= 2 and np.std(spending[mask]) > 1.0e-12:
                    subset_design = np.column_stack([np.ones(int(np.sum(mask))), spending[mask]])
                    subset_coef, *_ = np.linalg.lstsq(subset_design, output[mask], rcond=None)
                    state_multipliers[label] = float(subset_coef[1])

        return {
            "result": {
                "cumulative_multiplier": cumulative_multiplier,
                "discounted_output": discounted_output,
                "discounted_spending": discounted_spending,
                "local_projection_beta": float(coef[1]),
                "intercept": float(coef[0]),
                "state_multipliers": state_multipliers,
            }
        }


@foundry_method(
    namespace="policy.public_finance",
    version="1.0.0",
    tags={"policy", "public-finance", "optimal-tax", "frontier"},
)
class OptimalLinearTaxEstimator:
    """Saez-style optimal linear tax approximation under observed incomes and social weights."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="optimal_linear_tax",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("incomes", SlotType.VECTOR, Unit("income", "amount"), shape=("n_obs",)),
                SlotSpec("social_weights", SlotType.VECTOR, Unit("weight", "social"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec("elasticity", default=0.25, bounds=(1.0e-6, None)),
            ParameterSpec("lump_sum_rebate_share", default=0.0, bounds=(0.0, 1.0)),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Optimal linear income-tax approximation from sufficient-statistics inputs and social marginal welfare weights.",
        tags=frozenset({"policy", "public-finance", "optimal-tax", "frontier"}),
        citations=(
            "Saez, E. (2001). Using elasticities to derive optimal income tax rates.",
        ),
        when_to_use="Need a fast public-finance recommendation for a linear tax schedule with observed income distribution and social weights.",
        when_not_to_use="Need nonlinear Mirrlees schedules, strong income dynamics, or equilibrium labor-demand feedbacks.",
        typical_min_obs=50,
        output_interpretation="optimal_tax_rate is the welfare-maximizing linear rate under the supplied elasticity and social weights; after_tax_gini reports the implied inequality after applying the rate and rebate.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        incomes = np.clip(_coerce_vector(state, "incomes"), 0.0, None)
        weights = _normalize_weights(_coerce_vector(state, "social_weights"))
        if incomes.shape != weights.shape:
            raise ValueError("incomes and social_weights must have the same shape")
        elasticity = float(params.get("elasticity", 0.25))
        rebate_share = float(params.get("lump_sum_rebate_share", 0.0))

        social_marginal_value = float(np.dot(weights, np.clip(_coerce_vector(state, "social_weights"), 0.0, None)))
        social_marginal_value = social_marginal_value / max(float(np.max(_coerce_vector(state, "social_weights"))), 1.0e-12)
        numerator = max(0.0, 1.0 - social_marginal_value)
        optimal_tax_rate = numerator / max(numerator + elasticity, 1.0e-12)
        optimal_tax_rate = float(np.clip(optimal_tax_rate, 0.0, 1.0))

        tax_revenue = float(optimal_tax_rate * np.mean(incomes))
        rebate = rebate_share * tax_revenue
        after_tax = incomes * (1.0 - optimal_tax_rate) + rebate
        return {
            "result": {
                "optimal_tax_rate": optimal_tax_rate,
                "tax_revenue_per_capita": tax_revenue,
                "rebate_per_capita": rebate,
                "mean_after_tax_income": float(np.mean(after_tax)),
                "before_tax_gini": _gini(incomes),
                "after_tax_gini": _gini(after_tax),
                "elasticity": elasticity,
            }
        }


@foundry_method(
    namespace="policy.agent_sim",
    version="1.0.0",
    tags={"policy", "agent-sim", "mean-field", "frontier"},
)
class MeanFieldEquilibriumEstimator:
    """Solve a discrete mean-field equilibrium with congestion-adjusted rewards."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="mean_field_equilibrium",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("reward_matrix", SlotType.MATRIX, Unit("utility", "value"), shape=("n_states", "n_actions")),
                SlotSpec("transition_tensor", SlotType.TENSOR, Unit("probability", "transition"), shape=("n_actions", "n_states", "n_states")),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec("discount", default=0.95, bounds=(0.0, 0.999)),
            ParameterSpec("temperature", default=0.5, bounds=(1.0e-4, None)),
            ParameterSpec("max_iter", default=200, bounds=(20, 2000)),
            ParameterSpec("tol", default=1.0e-8, bounds=(1.0e-12, 1.0)),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Discrete-state mean-field equilibrium solver with congestion costs and endogenous stationary population mass.",
        tags=frozenset({"policy", "agent-sim", "mean-field", "frontier"}),
        citations=("Lasry, J.-M. & Lions, P.-L. (2007). Mean field games.",),
        when_to_use="Large-population strategic settings where individual value depends on aggregate state congestion or participation rates.",
        when_not_to_use="Strong finite-player strategic complementarities, continuous-time HJB/FPK requirements, or settings needing explicit agent heterogeneity beyond state masses.",
        typical_min_obs=1,
        output_interpretation="stationary_distribution is the equilibrium population mass by state and policy_matrix is the soft best response conditional on that mass.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        reward = _coerce_matrix(state, "reward_matrix")
        transition = np.array(state["transition_tensor"], dtype=float, copy=True)
        if transition.ndim != 3 or transition.shape[1] != reward.shape[0] or transition.shape[2] != reward.shape[0]:
            raise ValueError("transition_tensor must have shape (n_actions, n_states, n_states)")

        n_states, n_actions = reward.shape
        discount = float(params.get("discount", 0.95))
        temperature = float(params.get("temperature", 0.5))
        max_iter = int(params.get("max_iter", 200))
        tol = float(params.get("tol", 1.0e-8))
        congestion_costs = np.asarray(state.get("congestion_costs", np.zeros(n_states)), dtype=float)
        if congestion_costs.shape != (n_states,):
            raise ValueError("congestion_costs must be a vector with n_states elements")

        for action in range(n_actions):
            row_sums = np.sum(transition[action], axis=1, keepdims=True)
            transition[action] = transition[action] / np.maximum(row_sums, 1.0e-12)

        value = np.zeros(n_states, dtype=float)
        dist = np.full(n_states, 1.0 / n_states, dtype=float)
        converged = False
        for step in range(max_iter):
            q_values = np.zeros((n_states, n_actions), dtype=float)
            congestion = congestion_costs * dist
            for action in range(n_actions):
                q_values[:, action] = reward[:, action] - congestion + discount * (transition[action] @ value)
            policy = _softmax(q_values / max(temperature, 1.0e-6), axis=1)
            value_new = np.sum(policy * q_values, axis=1)
            policy_transition = np.einsum("sa,ask->sk", policy, transition)
            dist_new, _, _ = _stationary_distribution(policy_transition, max_iter=100, tol=tol)
            if max(float(np.max(np.abs(value_new - value))), float(np.max(np.abs(dist_new - dist)))) < tol:
                value = value_new
                dist = dist_new
                converged = True
                break
            value = value_new
            dist = dist_new

        return {
            "result": {
                "stationary_distribution": dist.tolist(),
                "policy_matrix": policy.tolist(),
                "value_function": value.tolist(),
                "mean_value": float(np.dot(dist, value)),
                "converged": converged,
                "iterations": step + 1,
            }
        }


@foundry_method(
    namespace="policy.macro",
    version="1.0.0",
    tags={"policy", "macro", "krusell-smith", "heterogeneous-shocks", "frontier"},
)
class KrusellSmithLiteEstimator:
    """Approximate stationary heterogeneous-agent block with idiosyncratic income shocks and a simple savings rule."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="krusell_smith_lite",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("asset_grid", SlotType.VECTOR, Unit("asset", "amount"), shape=("n_assets",)),
                SlotSpec("productivity_states", SlotType.VECTOR, Unit("productivity", "state"), shape=("n_prod",)),
                SlotSpec("productivity_transition", SlotType.MATRIX, Unit("probability", "transition"), shape=("n_prod", "n_prod")),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec("beta", default=0.96, bounds=(0.0, 0.999)),
            ParameterSpec("interest_rate", default=0.03),
            ParameterSpec("wage", default=1.0),
            ParameterSpec("savings_floor", default=0.05, bounds=(0.0, 1.0)),
            ParameterSpec("savings_ceiling", default=0.75, bounds=(0.0, 1.0)),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Krusell-Smith style stationary heterogeneous-shock economy with an explicit but lightweight savings-rule approximation.",
        tags=frozenset({"policy", "macro", "krusell-smith", "heterogeneous-shocks", "frontier"}),
        citations=("Krusell, P. & Smith, A. (1998). Income and wealth heterogeneity in the macroeconomy.",),
        when_to_use="Need a fast heterogeneous-agent macro block for screening tax-transfer proposals before moving to a full HANK/DSGE workflow.",
        when_not_to_use="Need endogenous labor supply, richer aggregate shocks, full market-clearing iteration, or production-side equilibrium closure.",
        typical_min_obs=1,
        output_interpretation="stationary_distribution is the joint mass over asset and productivity states; aggregate_capital and aggregate_consumption summarize the implied macro steady state.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        asset_grid = np.asarray(state["asset_grid"], dtype=float)
        productivity = np.asarray(state["productivity_states"], dtype=float)
        transition = np.array(state["productivity_transition"], dtype=float, copy=True)
        if asset_grid.ndim != 1 or productivity.ndim != 1 or transition.shape != (productivity.shape[0], productivity.shape[0]):
            raise ValueError("asset/productivity inputs must be aligned 1D grids and a square transition matrix")

        beta = float(params.get("beta", 0.96))
        interest_rate = float(params.get("interest_rate", 0.03))
        wage = float(params.get("wage", 1.0))
        savings_floor = float(params.get("savings_floor", 0.05))
        savings_ceiling = float(params.get("savings_ceiling", 0.75))
        transition = transition / np.maximum(np.sum(transition, axis=1, keepdims=True), 1.0e-12)

        n_assets = asset_grid.shape[0]
        n_prod = productivity.shape[0]
        current_assets = asset_grid[:, None]
        labor_income = wage * productivity[None, :]
        cash_on_hand = labor_income + (1.0 + interest_rate) * current_assets
        savings_rate = savings_floor + (savings_ceiling - savings_floor) / (
            1.0 + np.exp(-(beta - 0.5) * (cash_on_hand - np.median(cash_on_hand)))
        )
        next_assets = np.clip(savings_rate * cash_on_hand, asset_grid[0], asset_grid[-1])
        next_asset_index = np.abs(next_assets[:, :, None] - asset_grid[None, None, :]).argmin(axis=2)

        joint_size = n_assets * n_prod
        joint_transition = np.zeros((joint_size, joint_size), dtype=float)
        for asset_idx in range(n_assets):
            for prod_idx in range(n_prod):
                row = asset_idx * n_prod + prod_idx
                target_asset_idx = int(next_asset_index[asset_idx, prod_idx])
                for next_prod_idx in range(n_prod):
                    col = target_asset_idx * n_prod + next_prod_idx
                    joint_transition[row, col] += float(transition[prod_idx, next_prod_idx])

        stationary, converged, iterations = _stationary_distribution(joint_transition)
        stationary_matrix = stationary.reshape(n_assets, n_prod)
        aggregate_capital = float(np.sum(stationary_matrix * asset_grid[:, None]))
        aggregate_consumption = float(np.sum(stationary_matrix * (cash_on_hand - next_assets)))
        return {
            "result": {
                "stationary_distribution": stationary_matrix.tolist(),
                "aggregate_capital": aggregate_capital,
                "aggregate_consumption": aggregate_consumption,
                "mean_productivity": float(np.sum(stationary_matrix * productivity[None, :])),
                "converged": converged,
                "iterations": iterations,
            }
        }


@foundry_method(
    namespace="policy.evaluation",
    version="1.0.0",
    tags={"policy", "evaluation", "foundation-model", "frontier"},
)
class FoundationModelPolicyAnalysisEstimator:
    """Rank policy options against evidence using lexical or embedding backends with explicit runtime disclosure."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "sentence-transformers")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="foundation_model_policy_analysis",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("policy_options", SlotType.SCALAR, Unit("policy", "json")),
                SlotSpec("evidence_snippets", SlotType.SCALAR, Unit("evidence", "json")),
                SlotSpec("policy_query", SlotType.SCALAR, Unit("query", "text")),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec("embedding_backend", default="tfidf"),
            ParameterSpec("max_features", default=256),
            ParameterSpec("top_k_evidence", default=3),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Policy-analysis pipeline that scores policy alternatives against evidence using a truthful embedding backend surface.",
        tags=frozenset({"policy", "evaluation", "foundation-model", "frontier"}),
        optional_deps=("sentence-transformers",),
        fallback_policy="tfidf_backoff",
        citations=("Ni, J. et al. (2021). Sentence-T5: Scalable sentence encoders from pre-trained text-to-text models.",),
        when_to_use="Need a fast planner-facing ranking of policy options against a body of textual evidence before deeper human review.",
        when_not_to_use="Final legal or budgetary decisions, or cases where unsupported semantic ranking would be mistaken for causal evidence.",
        typical_min_obs=1,
        output_interpretation="policy_rankings combine query similarity and evidence support. runtime_backend discloses whether a lexical or sentence-transformer backend was actually used.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        policy_options = [str(item) for item in state["policy_options"]]
        evidence_snippets = [str(item) for item in state["evidence_snippets"]]
        if not policy_options or not evidence_snippets:
            raise ValueError("policy_options and evidence_snippets must both be non-empty")
        query = str(state.get("policy_query", "policy evaluation query"))
        backend = str(params.get("embedding_backend", "tfidf")).lower()
        max_features = int(params.get("max_features", 256))
        top_k = max(1, int(params.get("top_k_evidence", 3)))

        if backend == "sentence_transformer":
            embedder = SentenceTransformerEmbedder()
            runtime_backend = "sentence_transformer"
        else:
            embedder = TFIDFEmbedder(max_features=max_features)
            embedder.fit([query, *policy_options, *evidence_snippets])
            runtime_backend = "tfidf"

        policy_embeddings = np.asarray(embedder.embed(policy_options), dtype=float)
        evidence_embeddings = np.asarray(embedder.embed(evidence_snippets), dtype=float)
        query_embedding = np.asarray(embedder.embed([query])[0], dtype=float)

        policy_scores = _cosine_similarity(query_embedding, policy_embeddings)
        evidence_scores = np.asarray([_cosine_similarity(policy_embeddings[idx], evidence_embeddings) for idx in range(len(policy_options))])
        rankings = []
        for idx, policy_text in enumerate(policy_options):
            top_indices = np.argsort(evidence_scores[idx])[::-1][:top_k]
            support = float(np.mean(evidence_scores[idx, top_indices]))
            combined_score = float(0.6 * policy_scores[idx] + 0.4 * support)
            rankings.append(
                {
                    "policy_index": idx,
                    "policy_text": policy_text,
                    "combined_score": combined_score,
                    "query_similarity": float(policy_scores[idx]),
                    "evidence_support": support,
                    "top_evidence": [evidence_snippets[evidence_idx] for evidence_idx in top_indices.tolist()],
                }
            )
        rankings.sort(key=lambda item: item["combined_score"], reverse=True)
        return {
            "result": {
                "runtime_backend": runtime_backend,
                "policy_rankings": rankings,
                "query": query,
            }
        }


__all__ = [
    "FiscalMultiplierEstimator",
    "FoundationModelPolicyAnalysisEstimator",
    "KrusellSmithLiteEstimator",
    "MeanFieldEquilibriumEstimator",
    "OptimalLinearTaxEstimator",
    "SufficientStatisticsWelfareEstimator",
]
