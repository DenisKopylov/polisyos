"""Actual Causality Engine: PN/PS/PNS and HP actual causality.

Subphase 1.2 — Probability of Necessity and Sufficiency
    Pearl (2000), Ch. 9; Tian & Pearl (2000)

Subphase 1.3 — HP Actual Causality (AC1/AC2/AC3)
    Halpern & Pearl (2005), updated Halpern (2016)
    Chockler & Halpern (2004) for degree of responsibility/blame

References
----------
Pearl, J. (2000). Causality: Models, Reasoning and Inference. CUP.
Tian, J. & Pearl, J. (2000). Probabilities of Causation: Bounds and
    Identification. Ann. Math. AI.
Halpern, J. & Pearl, J. (2005). Causes and Explanations: A Structural-Model
    Approach. BJPS.
Halpern, J. (2016). Actual Causality. MIT Press.
Chockler, H. & Halpern, J. (2004). Responsibility and Blame. JAIR.
"""

from __future__ import annotations

import itertools
import math
import time
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

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
from polisyos.foundry.methods.catalog.causal.ncm_engine import (
    _abduce_exogenous,
    _ncm_parents_map,
    _ncm_topological_order,
    _parallel_worlds,
    _predict_from_abducted,
)
from polisyos.ir.analytics.actual_causality import (
    ContingencySet,
    HPResult,
    PNPSBounds,
    PNResult,
    PNSResult,
    PSResult,
)
from polisyos.ir.analytics.ncm import NCMSpec

# ── Tian-Pearl observational bounds (no SCM required) ─────────────────────────


def _normalize_cause_assignment(
    cause_var: str,
    cause_value: float,
    *,
    cause_vars: list[str] | None = None,
    cause_values: Mapping[str, float] | None = None,
) -> tuple[list[str], dict[str, float]]:
    """Normalize single- and multi-variable cause assignments."""
    if not cause_vars:
        return [cause_var], {cause_var: float(cause_value)}

    ordered_vars = [str(var) for var in cause_vars]
    values: dict[str, float] = {}
    for var in ordered_vars:
        values[var] = (
            float(cause_values[var])
            if cause_values is not None and var in cause_values
            else float(cause_value)
        )
    return ordered_vars, values


def _normalize_counterfactual_assignment(
    cause_vars: Sequence[str],
    counterfactual_cause_value: float,
    *,
    counterfactual_cause_values: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """Normalize counterfactual intervention values for a cause set."""
    cf_values: dict[str, float] = {}
    for var in cause_vars:
        cf_values[str(var)] = (
            float(counterfactual_cause_values[var])
            if counterfactual_cause_values is not None and var in counterfactual_cause_values
            else float(counterfactual_cause_value)
        )
    return cf_values


def _normalize_context_distribution(raw: Any) -> tuple[list[dict[str, float]], list[float]]:
    """Parse a simple epistemic context distribution payload."""
    if raw is None:
        return [], []
    if isinstance(raw, dict) and raw and all(isinstance(v, (int, float)) for v in raw.values()):
        return [{str(k): float(v) for k, v in raw.items()}], [1.0]
    if isinstance(raw, dict):
        contexts = raw.get("contexts")
        weights = raw.get("weights")
        if contexts is None:
            return [], []
        if not isinstance(contexts, list):
            raise ValueError("context_distribution['contexts'] must be a list")
        parsed_contexts = [
            {str(k): float(v) for k, v in ctx.items()} for ctx in contexts if isinstance(ctx, dict)
        ]
        if len(parsed_contexts) != len(contexts):
            raise ValueError("context_distribution['contexts'] must contain mappings")
        if weights is None:
            parsed_weights = (
                [1.0 / len(parsed_contexts)] * len(parsed_contexts) if parsed_contexts else []
            )
        else:
            parsed_weights = [float(w) for w in weights]
            if len(parsed_weights) != len(parsed_contexts):
                raise ValueError("context_distribution['weights'] length must match contexts")
        return parsed_contexts, parsed_weights
    if isinstance(raw, list):
        if not raw:
            return [], []
        if isinstance(raw[0], dict):
            return (
                [{str(k): float(v) for k, v in ctx.items()} for ctx in raw],
                [1.0 / len(raw)] * len(raw),
            )
    raise ValueError("context_distribution must be a mapping or a list of mappings")


def _tian_pearl_pn_bounds(
    p_y1_x1: float,
    p_y1_x0: float,
) -> tuple[float, float]:
    """Sharp PN bounds from observational data (Tian & Pearl 2000, Theorem 1).

    PN_lb = max(0, (P(Y=1|X=1) - P(Y=1|X=0)) / P(Y=1|X=1))   [when P(Y=1|X=1) > 0]
    PN_ub = min(1, (1 - P(Y=1|X=0)) / P(Y=1|X=1))            [when P(Y=1|X=1) > 0]

    These are the tightest bounds achievable from observational data alone,
    under the assumption that X is exogenous (no hidden confounders).
    """
    if p_y1_x1 < 1e-12:
        return 0.0, 1.0  # Uninformative when denominator is zero
    lb = max(0.0, (p_y1_x1 - p_y1_x0) / p_y1_x1)
    ub = min(1.0, (1.0 - p_y1_x0) / p_y1_x1)
    return float(lb), float(ub)


def _tian_pearl_ps_bounds(
    p_y1_x1: float,
    p_y1_x0: float,
) -> tuple[float, float]:
    """Sharp PS bounds from observational data (Tian & Pearl 2000, Theorem 1).

    PS_lb = max(0, (P(Y=1|X=1) - P(Y=1|X=0)) / P(Y=0|X=0))   [when P(Y=0|X=0) > 0]
    PS_ub = min(1, P(Y=1|X=1) / P(Y=0|X=0))
    """
    p_y0_x0 = 1.0 - p_y1_x0
    if p_y0_x0 < 1e-12:
        return 0.0, 1.0
    lb = max(0.0, (p_y1_x1 - p_y1_x0) / p_y0_x0)
    ub = min(1.0, p_y1_x1 / p_y0_x0)
    return float(lb), float(ub)


def _tian_pearl_pns_bounds(
    p_y1_x1: float,
    p_y1_x0: float,
) -> tuple[float, float]:
    """Sharp PNS bounds from observational data (Tian & Pearl 2000).

    PNS_lb = max(0, P(Y=1|X=1) - P(Y=1|X=0))
    PNS_ub = min(P(Y=1|X=1), 1 - P(Y=1|X=0)) = min(P(Y=1|X=1), P(Y=0|X=0))
    """
    lb = max(0.0, p_y1_x1 - p_y1_x0)
    ub = min(p_y1_x1, 1.0 - p_y1_x0)
    ub = max(ub, lb)  # Ensure lb ≤ ub (can occur with near-equal probabilities)
    return float(lb), float(ub)


def _compute_monotonicity_test(
    Y: np.ndarray,
    T: np.ndarray,
) -> tuple[bool, float]:
    """Test compatibility with monotone treatment response.

    Under MTR (Manski 1997), Y_1 ≥ Y_0 for all units, which implies
    P(Y=1|X=1) ≥ P(Y=1|X=0) for binary outcomes.  We use a one-sided
    proportions test as a heuristic.

    Returns (is_compatible, p_value).  p_value < 0.05 suggests violation.
    """
    y = np.asarray(Y, dtype=float)
    t = np.asarray(T, dtype=float)
    t1_mask = t == 1
    t0_mask = t == 0

    if t1_mask.sum() < 5 or t0_mask.sum() < 5:
        return True, 1.0  # Insufficient data — cannot reject monotonicity

    p1 = float(np.mean(y[t1_mask]))
    p0 = float(np.mean(y[t0_mask]))
    n1 = int(t1_mask.sum())
    n0 = int(t0_mask.sum())

    # Standard error under H0: p1 = p0
    p_pool = (p1 * n1 + p0 * n0) / (n1 + n0)
    se = math.sqrt(max(p_pool * (1.0 - p_pool) * (1.0 / n1 + 1.0 / n0), 1e-12))
    z_stat = (p1 - p0) / se

    # One-sided p-value for H0: p1 < p0 (monotonicity violation)
    # Using normal approximation
    from scipy.stats import norm  # type: ignore[import-untyped]

    p_val = float(norm.cdf(-z_stat))  # P(Z < -z) = P(violation)
    is_compatible = p1 >= p0  # Simple check: E[Y|T=1] >= E[Y|T=0]
    return is_compatible, p_val


def compute_pnps_bounds(
    p_y1_x1: float,
    p_y1_x0: float,
    p_x1: float | None = None,
) -> PNPSBounds:
    """Compute Tian-Pearl observational bounds for PN, PS, and PNS.

    Parameters
    ----------
    p_y1_x1:
        P(Y=1 | X=1) from observational data.
    p_y1_x0:
        P(Y=1 | X=0) from observational data.
    p_x1:
        Optional P(X=1) marginal.

    Returns
    -------
    PNPSBounds
        Tight bounds on PN, PS, PNS.
    """
    pn_lb, pn_ub = _tian_pearl_pn_bounds(p_y1_x1, p_y1_x0)
    ps_lb, ps_ub = _tian_pearl_ps_bounds(p_y1_x1, p_y1_x0)
    pns_lb, pns_ub = _tian_pearl_pns_bounds(p_y1_x1, p_y1_x0)

    # Monotone PNS: collapses to point under MTR
    monotone_pns = float(max(0.0, p_y1_x1 - p_y1_x0))
    is_monotone = p_y1_x1 >= p_y1_x0

    return PNPSBounds(
        p_y1_x1=float(p_y1_x1),
        p_y1_x0=float(p_y1_x0),
        p_x1=float(p_x1) if p_x1 is not None else None,
        pn_lower=pn_lb,
        pn_upper=pn_ub,
        ps_lower=ps_lb,
        ps_upper=ps_ub,
        pns_lower=pns_lb,
        pns_upper=pns_ub,
        monotone_pns=monotone_pns,
        is_monotone_compatible=is_monotone,
    )


# ── SCM-based PN/PS/PNS via parallel worlds ───────────────────────────────────


def _pn_from_ncm(
    ncm: NCMSpec,
    treatment: str,
    outcome: str,
    x_factual: float,
    x_counter: float,
    *,
    n_samples: int,
    rng: np.random.Generator,
    warnings: list[str],
    outcome_threshold: float = 0.5,
) -> PNResult:
    """Estimate PN via Monte Carlo twin-network simulation.

    PN = P(Y_{x'} = 0 | X = x, Y = 1)

    Algorithm:
    1. Sample units where X = x, Y = 1 (factual: do(X=x)).
    2. For each sample, abduct U from (X=x, Y=y_obs).
    3. Apply do(X=x') with same U.
    4. PN = mean(Y_{x'} < threshold | X=x, Y=1).
    """
    # Run two parallel worlds: factual (x) and counterfactual (x')
    interventions = [{treatment: x_factual}, {treatment: x_counter}]
    worlds = _parallel_worlds(
        ncm,
        interventions,
        {},
        "exact",
        n_samples=n_samples,
        rng=rng,
        warnings=warnings,
    )
    factual_y = worlds[0][outcome]
    counter_y = worlds[1][outcome]

    # Condition on factual Y = 1
    y_factual_one = factual_y >= outcome_threshold
    n_factual_one = int(y_factual_one.sum())

    if n_factual_one < 5:
        warnings.append(
            f"pn-estimation: only {n_factual_one} samples with Y≥threshold "
            "under factual world; PN estimate may be unreliable"
        )
        pn_val = 0.0
        ci = (0.0, 1.0)
    else:
        counter_y_given_y1 = counter_y[y_factual_one]
        pn_samples = (counter_y_given_y1 < outcome_threshold).astype(float)
        pn_val = float(np.mean(pn_samples))
        se = float(np.std(pn_samples)) / math.sqrt(len(pn_samples))
        ci = (max(0.0, pn_val - 1.96 * se), min(1.0, pn_val + 1.96 * se))

    return PNResult(
        treatment=treatment,
        outcome=outcome,
        treatment_value=x_factual,
        counterfactual_value=x_counter,
        pn=float(np.clip(pn_val, 0.0, 1.0)),
        pn_ci=ci,
        n_samples=n_samples,
        computation_method="simulation",
    )


def _ps_from_ncm(
    ncm: NCMSpec,
    treatment: str,
    outcome: str,
    x_factual: float,
    x_counter: float,
    *,
    n_samples: int,
    rng: np.random.Generator,
    warnings: list[str],
    outcome_threshold: float = 0.5,
) -> PSResult:
    """Estimate PS via Monte Carlo twin-network simulation.

    PS = P(Y_x = 1 | X = x', Y = 0)

    Algorithm: Symmetric to PN — condition on (X=x', Y=0), apply do(X=x).
    """
    interventions = [{treatment: x_counter}, {treatment: x_factual}]
    worlds = _parallel_worlds(
        ncm,
        interventions,
        {},
        "exact",
        n_samples=n_samples,
        rng=rng,
        warnings=warnings,
    )
    counter_y = worlds[0][outcome]  # Y under x'
    factual_y = worlds[1][outcome]  # Y under x (the "treated" world)

    # Condition on X=x', Y=0
    y_counter_zero = counter_y < outcome_threshold
    n_counter_zero = int(y_counter_zero.sum())

    if n_counter_zero < 5:
        warnings.append(
            f"ps-estimation: only {n_counter_zero} samples with Y<threshold "
            "under control world; PS estimate may be unreliable"
        )
        ps_val = 0.0
        ci = (0.0, 1.0)
    else:
        factual_y_given_y0 = factual_y[y_counter_zero]
        ps_samples = (factual_y_given_y0 >= outcome_threshold).astype(float)
        ps_val = float(np.mean(ps_samples))
        se = float(np.std(ps_samples)) / math.sqrt(len(ps_samples))
        ci = (max(0.0, ps_val - 1.96 * se), min(1.0, ps_val + 1.96 * se))

    return PSResult(
        treatment=treatment,
        outcome=outcome,
        treatment_value=x_factual,
        counterfactual_value=x_counter,
        ps=float(np.clip(ps_val, 0.0, 1.0)),
        ps_ci=ci,
        n_samples=n_samples,
        computation_method="simulation",
    )


def _pns_from_ncm(
    ncm: NCMSpec,
    treatment: str,
    outcome: str,
    x_factual: float,
    x_counter: float,
    *,
    n_samples: int,
    rng: np.random.Generator,
    warnings: list[str],
    outcome_threshold: float = 0.5,
) -> PNSResult:
    """Estimate PNS via joint parallel-worlds simulation.

    PNS = P(Y_{x_factual} = 1, Y_{x_counter} = 0)

    Uses K=2 parallel worlds sharing the same abducted U, then computes
    the joint event directly.
    """
    interventions = [{treatment: x_factual}, {treatment: x_counter}]
    worlds = _parallel_worlds(
        ncm,
        interventions,
        {},
        "exact",
        n_samples=n_samples,
        rng=rng,
        warnings=warnings,
    )
    y_fact = worlds[0][outcome]
    y_count = worlds[1][outcome]

    pns_mask = (y_fact >= outcome_threshold) & (y_count < outcome_threshold)
    pn_mask = y_count < outcome_threshold  # among all samples
    ps_mask = y_fact >= outcome_threshold

    pns_val = float(np.mean(pns_mask))
    pn_val = float(np.mean(pn_mask))
    ps_val = float(np.mean(ps_mask))

    se_pns = float(np.std(pns_mask.astype(float))) / math.sqrt(n_samples)
    ci_pns = (
        max(0.0, pns_val - 1.96 * se_pns),
        min(1.0, pns_val + 1.96 * se_pns),
    )

    return PNSResult(
        treatment=treatment,
        outcome=outcome,
        treatment_value=x_factual,
        counterfactual_value=x_counter,
        pns=float(np.clip(pns_val, 0.0, 1.0)),
        pn=float(np.clip(pn_val, 0.0, 1.0)),
        ps=float(np.clip(ps_val, 0.0, 1.0)),
        pns_ci=ci_pns,
        n_samples=n_samples,
        computation_method="simulation",
    )


# ── HP Actual Causality implementation ────────────────────────────────────────


def _forward_simulate(
    ncm: NCMSpec,
    intervention: dict[str, float],
    warnings: list[str],
) -> dict[str, float]:
    """Deterministic forward simulation of NCM under intervention (U = 0)."""
    order = _ncm_topological_order(ncm)
    parents_map = _ncm_parents_map(ncm)
    # Use zero abducted noise for purely deterministic forward pass
    return _predict_from_abducted(ncm, {}, intervention, order, parents_map, warnings)


def _check_ac1(
    ncm: NCMSpec,
    cause_var: str,
    cause_value: float,
    effect_var: str,
    effect_value: float,
    context: dict[str, float],
    outcome_threshold: float,
    warnings: list[str],
    *,
    cause_vars: list[str] | None = None,
    cause_values: dict[str, float] | None = None,
) -> bool:
    """AC1: X=x and Y=y hold in the actual context.

    Simply checks that the cause and effect values match the context.
    """
    # Check factual condition: X = x in context
    x_in_context = context.get(cause_var)
    if x_in_context is None:
        # If not in context, simulate with context as evidence
        x_in_context = cause_value

    y_in_context = context.get(effect_var)
    if y_in_context is None:
        # Simulate NCM with full context as fixed values
        sim_result = _forward_simulate(ncm, context, warnings)
        y_in_context = sim_result.get(effect_var, 0.0)

    cause_vars_norm, _cause_values_norm = _normalize_cause_assignment(
        cause_var,
        cause_value,
        cause_vars=cause_vars,
        cause_values=cause_values,
    )

    if len(cause_vars_norm) == 1 and cause_vars is None and cause_values is None:
        observed = context.get(cause_vars_norm[0], _cause_values_norm[cause_vars_norm[0]])
        cause_ok = abs(float(observed) - float(_cause_values_norm[cause_vars_norm[0]])) < 1e-9
    else:
        cause_ok = True
        for var in cause_vars_norm:
            observed = context.get(var)
            if observed is None:
                cause_ok = False
                break
            if abs(float(observed) - float(_cause_values_norm[var])) >= 1e-9:
                cause_ok = False
                break

    # Check effect matches (binary threshold or exact)
    if outcome_threshold is not None:
        y_val = float(y_in_context)
        effect_ok = (y_val >= outcome_threshold) == (effect_value >= outcome_threshold)
    else:
        effect_ok = abs(float(y_in_context) - effect_value) < 1e-9

    return cause_ok and effect_ok


def _simulate_with_intervention_and_context(
    ncm: NCMSpec,
    cause_intervention: dict[str, float],
    contingency: dict[str, float],
    context: dict[str, float],
    warnings: list[str],
) -> dict[str, float]:
    """Simulate NCM with do(X=x, W=w) given context as evidence.

    Step 1: Abduct exogenous noise U from the full observed context.
    Step 2: Apply intervention do(X=cause_value, W=w) — ONLY the cause and
            contingency variables are intervened upon; other variables propagate
            through their structural equations using the abducted noise.

    IMPORTANT: The outcome variable must NOT be included in the intervention dict,
    or it will be fixed to its observed value and never change.
    """
    order = _ncm_topological_order(ncm)
    parents_map = _ncm_parents_map(ncm)
    # Step 1: Abduct U from context (which may include outcome = factual value)
    abducted = _abduce_exogenous(ncm, context, "exact", warnings=warnings)
    # Step 2: Intervention dict = only do(X=x', W=w), nothing else
    intervention = {**cause_intervention, **contingency}
    return _predict_from_abducted(ncm, abducted, intervention, order, parents_map, warnings)


def _check_ac2_find_contingency(
    ncm: NCMSpec,
    cause_var: str,
    cause_value: float,
    counterfactual_cause_value: float,
    effect_var: str,
    effect_value: float,
    context: dict[str, float],
    outcome_threshold: float,
    *,
    max_contingency_size: int,
    warnings: list[str],
    cause_vars: list[str] | None = None,
    cause_values: dict[str, float] | None = None,
    counterfactual_cause_values: dict[str, float] | None = None,
) -> ContingencySet | None:
    """Search for a contingency set W satisfying AC2.

    AC2: ∃W, ∃x' s.t. do(X=x', W=w) in actual context ⊨ Y ≠ y.

    Search strategy:
    1. W = {} (empty): try do(X=x') alone.
    2. W = {one non-cause context variable}: try all single-variable contingencies.
    3. W = pairs, triples, ... up to max_contingency_size.

    Pruning: only consider non-cause, non-effect context variables as candidates.
    If |candidates| > 10, try parents of effect_var first as heuristic.
    """
    if not ncm.is_acyclic:
        raise ValueError(
            "HP actual cause check requires an acyclic NCM (is_acyclic=True). "
            "Cyclic models are not currently supported."
        )

    cause_vars_norm, cause_values_norm = _normalize_cause_assignment(
        cause_var,
        cause_value,
        cause_vars=cause_vars,
        cause_values=cause_values,
    )
    cf_values = _normalize_counterfactual_assignment(
        cause_vars_norm,
        counterfactual_cause_value,
        counterfactual_cause_values=counterfactual_cause_values,
    )

    # Helper to check if intervention produces Y ≠ y
    def _effect_changes(interv_context: dict[str, float]) -> bool:
        sim = _simulate_with_intervention_and_context(
            ncm, cf_values, interv_context, context, warnings
        )
        y_sim = sim.get(effect_var, effect_value)
        if outcome_threshold is not None:
            factual_bin = effect_value >= outcome_threshold
            sim_bin = float(y_sim) >= outcome_threshold
            return factual_bin != sim_bin
        return abs(float(y_sim) - effect_value) > 1e-6

    # Step 1: Empty contingency W = {}
    if _effect_changes({}):
        return ContingencySet(variables=[], values={}, size=0)

    # Collect candidate variables for contingency (exclude cause and effect)
    all_nodes = set(ncm.endogenous_vars)
    if ncm.scm_spec is not None:
        all_nodes = set(ncm.scm_spec.graph.nodes)
    elif ncm.structural_equations:
        all_nodes = {eq.variable for eq in ncm.structural_equations}
        for eq in ncm.structural_equations:
            all_nodes.update(eq.parents)

    candidates = sorted(all_nodes - set(cause_vars_norm) - {effect_var})

    # Heuristic: if many candidates, try parents of effect first
    if len(candidates) > 10:
        # Get parents of effect_var from graph
        effect_parents: list[str] = []
        if ncm.scm_spec is not None:
            for edge in ncm.scm_spec.graph.edges:
                if edge.dst == effect_var:
                    effect_parents.append(edge.src)
        else:
            for eq in ncm.structural_equations:
                if eq.variable == effect_var:
                    effect_parents = list(eq.parents)
                    break
        # Prioritize parents, then other candidates
        priority = [c for c in effect_parents if c in candidates]
        rest = [c for c in candidates if c not in priority]
        candidates = priority + rest

    # Steps 2+: Try combinations of increasing size
    for size in range(1, min(max_contingency_size + 1, len(candidates) + 1)):
        for combo in itertools.combinations(candidates, size):
            # Use context values for the contingency variables
            w_values = {v: float(context.get(v, 0.0)) for v in combo}
            if _effect_changes(w_values):
                return ContingencySet(
                    variables=list(combo),
                    values=w_values,
                    size=size,
                )

    return None  # No valid contingency found within max_size


def _check_ac3_minimality(
    ncm: NCMSpec,
    cause_var: str,
    cause_value: float,
    counterfactual_cause_value: float,
    effect_var: str,
    effect_value: float,
    context: dict[str, float],
    contingency: ContingencySet | None,
    outcome_threshold: float,
    *,
    max_contingency_size: int,
    warnings: list[str],
    cause_vars: list[str] | None = None,
    cause_values: dict[str, float] | None = None,
    counterfactual_cause_values: dict[str, float] | None = None,
) -> bool:
    """AC3: Check minimality — no proper subset of the cause assignment satisfies AC1+AC2.

    For single-variable causes (the common case), AC3 is trivially True.
    """
    cause_vars_norm, cause_values_norm = _normalize_cause_assignment(
        cause_var,
        cause_value,
        cause_vars=cause_vars,
        cause_values=cause_values,
    )
    if len(cause_vars_norm) <= 1:
        return True

    cf_values = _normalize_counterfactual_assignment(
        cause_vars_norm,
        counterfactual_cause_value,
        counterfactual_cause_values=counterfactual_cause_values,
    )

    # Any proper subset that satisfies AC1+AC2 violates minimality.
    for size in range(len(cause_vars_norm) - 1, 0, -1):
        for subset in itertools.combinations(cause_vars_norm, size):
            subset_vars = list(subset)
            subset_values = {var: cause_values_norm[var] for var in subset_vars}
            subset_cf_values = {var: cf_values[var] for var in subset_vars}

            if not _check_ac1(
                ncm,
                subset_vars[0],
                subset_values[subset_vars[0]],
                effect_var,
                effect_value,
                context,
                outcome_threshold,
                warnings,
                cause_vars=subset_vars,
                cause_values=subset_values,
            ):
                continue

            contingency_subset = _check_ac2_find_contingency(
                ncm,
                subset_vars[0],
                subset_values[subset_vars[0]],
                subset_cf_values[subset_vars[0]],
                effect_var,
                effect_value,
                context,
                outcome_threshold,
                max_contingency_size=max_contingency_size,
                warnings=warnings,
                cause_vars=subset_vars,
                cause_values=subset_values,
                counterfactual_cause_values=subset_cf_values,
            )
            if contingency_subset is not None:
                return False

    return True


def _degree_of_responsibility(
    ncm: NCMSpec,
    cause_var: str,
    cause_value: float,
    counterfactual_cause_value: float,
    effect_var: str,
    effect_value: float,
    context: dict[str, float],
    outcome_threshold: float,
    *,
    max_contingency_size: int,
    warnings: list[str],
    cause_vars: list[str] | None = None,
    cause_values: dict[str, float] | None = None,
    counterfactual_cause_values: dict[str, float] | None = None,
) -> float:
    """Compute Chockler-Halpern degree of responsibility.

    DR(X=x → Y=y) = 1 / (|W_min| + 1)

    where W_min is the smallest contingency set making (X, W) an AC2 witness.
    DR = 1.0 for direct causes (no contingency needed, |W_min| = 0).
    """
    # Find the minimum contingency size
    if not ncm.is_acyclic:
        return 0.0

    cause_vars_norm, _ = _normalize_cause_assignment(
        cause_var,
        cause_value,
        cause_vars=cause_vars,
        cause_values=cause_values,
    )
    cf_values = _normalize_counterfactual_assignment(
        cause_vars_norm,
        counterfactual_cause_value,
        counterfactual_cause_values=counterfactual_cause_values,
    )

    def _effect_changes_with_w(w_dict: dict[str, float]) -> bool:
        sim = _simulate_with_intervention_and_context(ncm, cf_values, w_dict, context, warnings)
        y_sim = sim.get(effect_var, effect_value)
        if outcome_threshold is not None:
            return (effect_value >= outcome_threshold) != (float(y_sim) >= outcome_threshold)
        return abs(float(y_sim) - effect_value) > 1e-6

    # Direct cause check
    if _effect_changes_with_w({}):
        return 1.0

    all_nodes = set(ncm.endogenous_vars)
    if ncm.scm_spec is not None:
        all_nodes = set(ncm.scm_spec.graph.nodes)
    candidates = sorted(all_nodes - set(cause_vars_norm) - {effect_var})

    for size in range(1, min(max_contingency_size + 1, len(candidates) + 1)):
        for combo in itertools.combinations(candidates, size):
            w_vals = {v: float(context.get(v, 0.0)) for v in combo}
            if _effect_changes_with_w(w_vals):
                return 1.0 / (size + 1)

    # No witness found within max_contingency_size
    return 0.0


def _degree_of_blame(
    ncm: NCMSpec,
    cause_var: str,
    cause_value: float,
    counterfactual_cause_value: float,
    effect_var: str,
    effect_value: float,
    context_distribution: list[dict[str, float]],
    outcome_threshold: float,
    *,
    max_contingency_size: int,
    warnings: list[str],
    context_weights: list[float] | None = None,
    bootstrap_samples: int = 200,
    cause_vars: list[str] | None = None,
    cause_values: dict[str, float] | None = None,
    counterfactual_cause_values: dict[str, float] | None = None,
) -> tuple[float, tuple[float, float] | None]:
    """Compute epistemic degree of blame as expected responsibility.

    The returned confidence interval is a bootstrap CI over the supplied
    epistemic contexts.  When only one context is available, the interval
    collapses to a point.
    """
    if not context_distribution:
        return 0.0, None

    weights = context_weights or [1.0 / len(context_distribution)] * len(context_distribution)
    if len(weights) != len(context_distribution):
        raise ValueError("context_weights length must match context_distribution")

    responsibilities: list[float] = []
    for context in context_distribution:
        resp = _degree_of_responsibility(
            ncm,
            cause_var,
            cause_value,
            counterfactual_cause_value,
            effect_var,
            effect_value,
            context,
            outcome_threshold,
            max_contingency_size=max_contingency_size,
            warnings=warnings,
            cause_vars=cause_vars,
            cause_values=cause_values,
            counterfactual_cause_values=counterfactual_cause_values,
        )
        responsibilities.append(float(resp))

    blame = float(
        np.average(
            np.asarray(responsibilities, dtype=float), weights=np.asarray(weights, dtype=float)
        )
    )
    if len(responsibilities) == 1 or bootstrap_samples <= 1:
        return blame, (blame, blame)

    rng = np.random.default_rng(0)
    boot = []
    probs = np.asarray(weights, dtype=float)
    probs = probs / probs.sum() if probs.sum() > 0 else np.full(len(weights), 1.0 / len(weights))
    for _ in range(bootstrap_samples):
        idx = rng.choice(
            len(context_distribution), size=len(context_distribution), replace=True, p=probs
        )
        sample_responsibilities = np.asarray([responsibilities[i] for i in idx], dtype=float)
        sample_weights = np.full(len(idx), 1.0 / len(idx), dtype=float)
        boot.append(float(np.average(sample_responsibilities, weights=sample_weights)))

    lo, hi = np.percentile(np.asarray(boot, dtype=float), [2.5, 97.5]).tolist()
    return blame, (float(lo), float(hi))


# ── Foundry methods ────────────────────────────────────────────────────────────


@foundry_method(
    namespace="causal.counterfactual",
    version="1.0.0",
    tags={"causal", "ncm", "pns", "probability_of_causation", "counterfactual", "structural"},
)
class ActualCausalityEngine:
    """Probability of Necessity and Sufficiency (PN/PS/PNS) engine.

    Computes three measures of actual causation probability:
    - PN: Would Y not have occurred without X?
    - PS: Would Y have occurred with X?
    - PNS: Was X both necessary and sufficient for Y?

    Two computation paths:
    1. NCM-based (``ncm_spec`` provided): Monte Carlo via twin-network AAP.
    2. Observational bounds (no NCM): Tian & Pearl (2000) sharp bounds from
       P(Y=1|X=1) and P(Y=1|X=0).
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="actual_causality",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("ncm_query_data", SlotType.SCALAR, Unit("query", "json")),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec("pns_result", SlotType.SCALAR, Unit("report", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="n_samples", default=2000),
            ParameterSpec(name="compute_bounds", default=True),
            ParameterSpec(name="estimand", default="pns"),
            ParameterSpec(name="outcome_threshold", default=0.5),
            ParameterSpec(name="treatment_value", default=1.0),
            ParameterSpec(name="counterfactual_value", default=0.0),
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
            "Probability of Necessity (PN), Sufficiency (PS), and Necessity+Sufficiency "
            "(PNS) via NCM twin-network simulation or Tian-Pearl observational bounds."
        ),
        tags=frozenset(
            {"causal", "pns", "probability_of_causation", "l3", "counterfactual", "structural"}
        ),
        citations=(
            "Pearl, J. (2000). Causality, Ch. 9. CUP.",
            "Tian, J. & Pearl, J. (2000). Probabilities of Causation: Bounds and Identification. "
            "Ann. Math. AI.",
        ),
        equations={
            "pn": "PN = P(Y_{x'} = 0 | X = x, Y = 1)",
            "ps": "PS = P(Y_x = 1 | X = x', Y = 0)",
            "pns": "PNS = P(Y_x = 1, Y_{x'} = 0)",
            "pns_lb": "PNS_lb = max(0, P(Y=1|X=1) - P(Y=1|X=0))",
            "pns_ub": "PNS_ub = min(P(Y=1|X=1), P(Y=0|X=0))",
        },
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use=(
            "Assess whether X was a necessary and/or sufficient cause of Y in a specific instance. "
            "Use with NCMSpec for point estimates or observational data for bounds."
        ),
        when_not_to_use="Continuous Y without a meaningful binary threshold; no observed outcome.",
        typical_min_obs=500,
        output_interpretation=(
            "PNS close to 1 → X was both necessary and sufficient for Y. "
            "PNS_lb gives the minimum achievable from data alone."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.methods.catalog.causal.protocols import NCMQueryData

        t0 = time.time()
        seed = params.get("__seed__")
        rng = np.random.default_rng(seed)

        n_samples = int(params.get("n_samples", 2000))
        compute_bounds = bool(params.get("compute_bounds", True))
        estimand = str(params.get("estimand", "pns"))
        outcome_threshold = float(params.get("outcome_threshold", 0.5))
        x_val = float(params.get("treatment_value", 1.0))
        x_counter = float(params.get("counterfactual_value", 0.0))

        raw = state.get("ncm_query_data", state)
        if isinstance(raw, NCMQueryData):
            query_data = raw
        else:
            query_data = NCMQueryData.model_validate(raw if isinstance(raw, dict) else dict(raw))

        ncm: NCMSpec = query_data.ncm_spec  # type: ignore[assignment]
        treatment = str(
            params.get("treatment_variable") or query_data.metadata.get("treatment_variable", "T")
        )
        outcome = str(
            params.get("outcome_variable") or query_data.metadata.get("outcome_variable", "Y")
        )

        warnings: list[str] = []
        out: dict[str, Any] = {}

        # NCM-based simulation
        if estimand in ("pn", "all"):
            pn_result = _pn_from_ncm(
                ncm,
                treatment,
                outcome,
                x_val,
                x_counter,
                n_samples=n_samples,
                rng=rng,
                warnings=warnings,
                outcome_threshold=outcome_threshold,
            )
            out["pn_result"] = pn_result.model_dump(mode="json")

        if estimand in ("ps", "all"):
            ps_result = _ps_from_ncm(
                ncm,
                treatment,
                outcome,
                x_val,
                x_counter,
                n_samples=n_samples,
                rng=rng,
                warnings=warnings,
                outcome_threshold=outcome_threshold,
            )
            out["ps_result"] = ps_result.model_dump(mode="json")

        if estimand in ("pns", "all"):
            pns_result = _pns_from_ncm(
                ncm,
                treatment,
                outcome,
                x_val,
                x_counter,
                n_samples=n_samples,
                rng=rng,
                warnings=warnings,
                outcome_threshold=outcome_threshold,
            )
            out["pns_result"] = pns_result.model_dump(mode="json")

        # Observational bounds (from metadata if data provided)
        if compute_bounds:
            p11 = float(query_data.metadata.get("p_y1_x1", 0.0))
            p10 = float(query_data.metadata.get("p_y1_x0", 0.0))
            if p11 > 0 or p10 > 0:
                bounds = compute_pnps_bounds(p11, p10)
                out["pnps_bounds"] = bounds.model_dump(mode="json")

        out["warnings"] = warnings
        out["computation_time_seconds"] = time.time() - t0
        return out


@foundry_method(
    namespace="causal.counterfactual",
    version="1.0.0",
    tags={"causal", "ncm", "actual_causality", "halpern_pearl", "responsibility", "structural"},
)
class HPActualCauseMethod:
    """HP Actual Causality method (Halpern & Pearl 2005, updated 2016).

    Checks three conditions for X=x to be an actual cause of Y=y:
    - AC1: Factual condition — X=x and Y=y hold in context.
    - AC2: Counterfactual condition — ∃W s.t. do(X=x', W=w) → Y≠y.
    - AC3: Minimality — no proper subset satisfies AC1+AC2.

    Also computes degree of responsibility (Chockler & Halpern 2004):
    DR = 1/(|W_min| + 1), where |W_min| is the minimum contingency size.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="hp_actual_cause",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("ncm_query_data", SlotType.SCALAR, Unit("query", "json")),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec("hp_result", SlotType.SCALAR, Unit("report", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="cause_variable", default="X"),
            ParameterSpec(name="cause_value", default=1.0),
            ParameterSpec(name="counterfactual_cause_value", default=0.0),
            ParameterSpec(name="cause_variables", default=None),
            ParameterSpec(name="cause_values", default=None),
            ParameterSpec(name="counterfactual_cause_values", default=None),
            ParameterSpec(name="effect_variable", default="Y"),
            ParameterSpec(name="effect_value", default=1.0),
            ParameterSpec(name="max_contingency_size", default=3),
            ParameterSpec(name="outcome_threshold", default=0.5),
            ParameterSpec(name="compute_responsibility", default=True),
            ParameterSpec(name="context_distribution", default=None),
            ParameterSpec(name="estimate_blame", default=False),
            ParameterSpec(name="bootstrap_samples", default=200),
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
            "HP actual causality check: determines whether X=x is an actual cause of Y=y "
            "via AC1/AC2/AC3 conditions, and computes degree of responsibility."
        ),
        tags=frozenset(
            {"causal", "actual_causality", "halpern_pearl", "responsibility", "l3", "structural"}
        ),
        citations=(
            "Halpern, J. & Pearl, J. (2005). Causes and Explanations: A Structural-Model Approach. BJPS.",
            "Halpern, J. (2016). Actual Causality. MIT Press.",
            "Chockler, H. & Halpern, J. (2004). Responsibility and Blame. JAIR.",
        ),
        equations={
            "ac1": "AC1: X=x ∧ Y=y (factual)",
            "ac2": "AC2: ∃W,x' s.t. do(X=x', W=w) ⊨ Y≠y",
            "ac3": "AC3: X minimal (no proper subset satisfies AC1+AC2)",
            "dr": "DR(X→Y) = 1/(|W_min|+1)",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Determine whether a specific event X=x caused outcome Y=y in an observed context. "
            "Requires a fitted or symbolic NCM."
        ),
        when_not_to_use="Purely interventional or distributional questions; cyclic NCMs.",
        typical_min_obs=1,
        output_interpretation=(
            "is_actual_cause=True → X=x satisfies AC1+AC2+AC3. "
            "degree_of_responsibility=1.0 → direct cause. 0.5 → cause with one contingency variable."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.methods.catalog.causal.protocols import NCMQueryData

        t0 = time.time()

        cause_var = str(params.get("cause_variable", "X"))
        cause_val = float(params.get("cause_value", 1.0))
        cf_cause_val = float(params.get("counterfactual_cause_value", 0.0))
        cause_vars_raw = params.get("cause_variables")
        cause_values_raw = params.get("cause_values")
        cf_cause_values_raw = params.get("counterfactual_cause_values")
        effect_var = str(params.get("effect_variable", "Y"))
        effect_val = float(params.get("effect_value", 1.0))
        max_size = int(params.get("max_contingency_size", 3))
        outcome_threshold = float(params.get("outcome_threshold", 0.5))
        compute_dr = bool(params.get("compute_responsibility", True))
        estimate_blame = bool(params.get("estimate_blame", False))
        bootstrap_samples = int(params.get("bootstrap_samples", 200))

        raw = state.get("ncm_query_data", state)
        if isinstance(raw, NCMQueryData):
            query_data = raw
        else:
            query_data = NCMQueryData.model_validate(raw if isinstance(raw, dict) else dict(raw))

        ncm: NCMSpec = query_data.ncm_spec  # type: ignore[assignment]
        context: dict[str, float] = dict(query_data.evidence)
        cause_vars, cause_values = _normalize_cause_assignment(
            cause_var,
            cause_val,
            cause_vars=list(cause_vars_raw)
            if isinstance(cause_vars_raw, (list, tuple, set, frozenset))
            else None,
            cause_values=cause_values_raw if isinstance(cause_values_raw, Mapping) else None,
        )
        cf_cause_values = _normalize_counterfactual_assignment(
            cause_vars,
            cf_cause_val,
            counterfactual_cause_values=cf_cause_values_raw
            if isinstance(cf_cause_values_raw, Mapping)
            else None,
        )
        cause_assignment_text = ", ".join(f"{var}={cause_values[var]}" for var in cause_vars)

        warnings: list[str] = []

        # AC1
        ac1 = _check_ac1(
            ncm,
            cause_var,
            cause_val,
            effect_var,
            effect_val,
            context,
            outcome_threshold,
            warnings,
            cause_vars=cause_vars if len(cause_vars) > 1 else None,
            cause_values=cause_values if len(cause_vars) > 1 else None,
        )

        ac2 = False
        contingency: ContingencySet | None = None
        ac3 = False
        dr = 0.0

        if ac1:
            # AC2: find contingency
            contingency = _check_ac2_find_contingency(
                ncm,
                cause_var,
                cause_val,
                cf_cause_val,
                effect_var,
                effect_val,
                context,
                outcome_threshold,
                max_contingency_size=max_size,
                warnings=warnings,
                cause_vars=cause_vars if len(cause_vars) > 1 else None,
                cause_values=cause_values if len(cause_vars) > 1 else None,
                counterfactual_cause_values=cf_cause_values if len(cause_vars) > 1 else None,
            )
            ac2 = contingency is not None

        if ac2:
            # AC3: minimality (trivially True for single-variable causes)
            ac3 = _check_ac3_minimality(
                ncm,
                cause_var,
                cause_val,
                cf_cause_val,
                effect_var,
                effect_val,
                context,
                contingency,
                outcome_threshold,
                max_contingency_size=max_size,
                warnings=warnings,
                cause_vars=cause_vars if len(cause_vars) > 1 else None,
                cause_values=cause_values if len(cause_vars) > 1 else None,
                counterfactual_cause_values=cf_cause_values if len(cause_vars) > 1 else None,
            )

        is_actual = ac1 and ac2 and ac3

        # Degree of responsibility
        if is_actual and compute_dr:
            dr = _degree_of_responsibility(
                ncm,
                cause_var,
                cause_val,
                cf_cause_val,
                effect_var,
                effect_val,
                context,
                outcome_threshold,
                max_contingency_size=max_size,
                warnings=warnings,
                cause_vars=cause_vars if len(cause_vars) > 1 else None,
                cause_values=cause_values if len(cause_vars) > 1 else None,
                counterfactual_cause_values=cf_cause_values if len(cause_vars) > 1 else None,
            )
        elif is_actual:
            dr = (
                1.0 / ((contingency.size if contingency else 0) + 1)
                if contingency is not None
                else 1.0
            )

        degree_of_blame: float | None = None
        blame_ci: tuple[float, float] | None = None
        context_dist_raw = params.get(
            "context_distribution", query_data.metadata.get("context_distribution")
        )
        context_distribution, context_weights = _normalize_context_distribution(context_dist_raw)
        if estimate_blame or context_distribution:
            degree_of_blame, blame_ci = _degree_of_blame(
                ncm,
                cause_var,
                cause_val,
                cf_cause_val,
                effect_var,
                effect_val,
                context_distribution or [context],
                outcome_threshold,
                max_contingency_size=max_size,
                warnings=warnings,
                context_weights=context_weights if context_distribution else None,
                bootstrap_samples=bootstrap_samples,
                cause_vars=cause_vars if len(cause_vars) > 1 else None,
                cause_values=cause_values if len(cause_vars) > 1 else None,
                counterfactual_cause_values=cf_cause_values if len(cause_vars) > 1 else None,
            )

        # Build explanation
        if is_actual:
            explanation = (
                f"{cause_assignment_text} is an actual cause of {effect_var}={effect_val}. "
                f"DR={dr:.3f}."
            )
        elif not ac1:
            explanation = (
                f"AC1 failed: {cause_assignment_text} or {effect_var}={effect_val} not in context."
            )
        elif not ac2:
            explanation = (
                f"AC2 failed: no contingency set of size ≤{max_size} makes "
                f"do({cause_assignment_text}) change {effect_var}."
            )
        else:
            explanation = "AC3 minimality check failed."

        result = HPResult(
            cause_variable=cause_var,
            cause_value=cause_val,
            counterfactual_cause_value=cf_cause_val,
            cause_variables=cause_vars if len(cause_vars) > 1 else None,
            cause_values=cause_values if len(cause_vars) > 1 else None,
            counterfactual_cause_values=cf_cause_values if len(cause_vars) > 1 else None,
            effect_variable=effect_var,
            effect_value=effect_val,
            ac1_satisfied=ac1,
            ac2_satisfied=ac2,
            ac3_satisfied=ac3,
            is_actual_cause=is_actual,
            contingency=contingency,
            degree_of_responsibility=float(np.clip(dr, 0.0, 1.0)),
            degree_of_blame=float(np.clip(degree_of_blame, 0.0, 1.0))
            if degree_of_blame is not None
            else None,
            blame_ci=blame_ci,
            explanation=explanation,
            metadata={"warnings": warnings, "computation_time_seconds": time.time() - t0},
        )

        return {"hp_result": result.model_dump(mode="json")}


__all__ = [
    "ActualCausalityEngine",
    "HPActualCauseMethod",
    "_check_ac1",
    "_check_ac2_find_contingency",
    "_check_ac3_minimality",
    "_compute_monotonicity_test",
    "_degree_of_blame",
    "_degree_of_responsibility",
    "_pn_from_ncm",
    "_pns_from_ncm",
    "_ps_from_ncm",
    "_tian_pearl_pn_bounds",
    "_tian_pearl_pns_bounds",
    "_tian_pearl_ps_bounds",
    "compute_pnps_bounds",
]
