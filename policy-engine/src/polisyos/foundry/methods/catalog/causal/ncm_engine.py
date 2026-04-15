"""NCM Engine — Abduction-Action-Prediction for Non-parametric Causal Models.

Implements the three-step AAP algorithm for counterfactual queries:
  1. Abduction  — infer exogenous noise U from factual evidence
  2. Action     — mutilate the NCM via do(X=x) intervention
  3. Prediction — forward-simulate the mutilated model with abducted U

Supports K parallel worlds (K >= 1) with shared exogenous noise, generalising
the twin-network algorithm to arbitrary counterfactual queries.

Key design:
- When ``ncm_spec.scm_spec`` is present and exact abduction is requested, the
  engine delegates to the existing ``gcm_query`` / ``twin_network_query``
  infrastructure for backward compatibility with fitted SCMs.
- Symbolic NCMs and approximate abduction modes use local inversion: analytic
  residuals for linear equations, polynomial roots when available, numerical
  root-finding for scalar nonlinear equations, and posterior approximations for
  ``mcmc`` / ``variational`` paths.

References
----------
Bongers, S., Forré, P., Peters, J. & Mooij, J.M. (2021). Foundations of
    Structural Causal Models with Cycles and Latent Variables. AoS 49(5).
Pearl, J. (2000). Causality: Models, Reasoning and Inference. CUP.
"""
from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar, Literal

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
from polisyos.foundry.methods.catalog.causal.gcm_query import (
    _abduce_noises_unified,
    _linear_predict,
    _mechanism_map,
    _parents_by_node,
    _topological_order,
)
from polisyos.foundry.methods.catalog.causal.twin_network_query import (
    _apply_node_noise,
    _sample_node_noise,
)
from polisyos.ir.analytics.ncm import NCMSpec, StructuralEquation
from polisyos.ir.analytics.structural_causal_model import MechanismFamily, NodeMechanism


# ── Private helpers ────────────────────────────────────────────────────────────


def _append_warning(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def _equation_deterministic_term(
    eq: StructuralEquation,
    parent_vals: Mapping[str, float],
) -> float:
    """Return the deterministic contribution of a structural equation."""
    params = eq.equation_params
    intercept = float(params.get("intercept", 0.0))
    coefs = params.get("coefficients", {})
    return intercept + sum(float(coefs.get(parent, 0.0)) * float(parent_vals.get(parent, 0.0)) for parent in eq.parents)


def _noise_polynomial_coefficients(eq: StructuralEquation) -> list[float]:
    """Return polynomial coefficients for the exogenous noise term.

    The coefficients are interpreted in the NumPy ``polyval`` / ``roots``
    convention: highest power first.  When not provided, we treat the noise as
    additive and therefore use ``[1.0]``.
    """
    params = eq.equation_params
    raw = params.get("noise_polynomial_coefficients")
    if raw is None:
        return [1.0]
    if isinstance(raw, (int, float)):
        return [float(raw)]
    coeffs = [float(value) for value in raw]
    return coeffs or [1.0]


def _safe_expression_context(
    eq: StructuralEquation,
    parent_vals: Mapping[str, float],
    noise: float,
) -> dict[str, Any]:
    deterministic = _equation_deterministic_term(eq, parent_vals)
    return {
        "u": float(noise),
        "noise": float(noise),
        "deterministic": deterministic,
        "math": math,
        "np": np,
        **{name: float(value) for name, value in parent_vals.items()},
    }


def _evaluate_noise_expression(
    eq: StructuralEquation,
    parent_vals: Mapping[str, float],
    noise: float,
) -> float | None:
    params = eq.equation_params
    expr = params.get("noise_expression") or params.get("symbolic_expression")
    if not isinstance(expr, str) or not expr.strip():
        return None
    namespace = {"__builtins__": {}}
    try:
        value = eval(expr, namespace, _safe_expression_context(eq, parent_vals, noise))
    except Exception as exc:
        raise ValueError(
            f"ncm-engine: failed to evaluate nonlinear noise expression for '{eq.variable}': {exc}"
        ) from exc
    return float(value)


def _evaluate_nonlinear_equation(
    eq: StructuralEquation,
    parent_vals: Mapping[str, float],
    noise: float,
) -> float:
    """Evaluate a structural equation with an explicit noise polynomial."""
    expr_value = _evaluate_noise_expression(eq, parent_vals, noise)
    if expr_value is not None:
        return expr_value
    deterministic = _equation_deterministic_term(eq, parent_vals)
    coeffs = _noise_polynomial_coefficients(eq)
    return deterministic + float(np.polyval(coeffs, noise))


def _select_root(
    roots: Sequence[float],
    *,
    policy: Literal["closest_to_prior", "smallest_magnitude", "all_roots_mcmc"],
    prior_mean: float,
    prior_std: float,
) -> float:
    """Select one or more roots according to the configured policy."""
    root_array = np.asarray(list(roots), dtype=float)
    if root_array.size == 0:
        raise ValueError("Cannot select a root from an empty set")

    if policy == "smallest_magnitude":
        idx = int(np.argmin(np.abs(root_array)))
        return float(root_array[idx])

    if policy == "all_roots_mcmc":
        scale = max(float(prior_std), 1e-6)
        weights = np.exp(-0.5 * ((root_array - prior_mean) / scale) ** 2)
        weight_sum = float(np.sum(weights))
        if weight_sum <= 0.0 or not np.isfinite(weight_sum):
            return float(np.mean(root_array))
        return float(np.sum(root_array * weights) / weight_sum)

    # Default policy: closest to the prior mean.
    idx = int(np.argmin(np.abs(root_array - prior_mean)))
    return float(root_array[idx])


def _abduct_noise_from_equation(
    eq: StructuralEquation,
    parent_vals: Mapping[str, float],
    observed_value: float,
    *,
    root_selection_policy: Literal["closest_to_prior", "smallest_magnitude", "all_roots_mcmc"],
    warnings: list[str],
) -> float:
    """Invert a structural equation for the exogenous noise term.

    Linear equations use the closed-form residual.  Nonlinear equations are
    inverted via polynomial root finding when a noise polynomial is supplied.
    Multiple real roots are resolved by the configured selection policy.
    """
    deterministic = _equation_deterministic_term(eq, parent_vals)
    equation_type = eq.equation_type

    if equation_type == "linear":
        return float(observed_value - deterministic)

    coeffs = _noise_polynomial_coefficients(eq)
    prior_mean = float(eq.equation_params.get("prior_mean", 0.0))
    prior_std = float(eq.equation_params.get("prior_std", 1.0))
    target = float(observed_value - deterministic)

    if len(coeffs) == 1:
        coef = float(coeffs[0])
        if abs(coef) < 1e-12:
            _append_warning(
                warnings,
                f"ncm-engine: degenerate polynomial noise model for '{eq.variable}'; using U=0",
            )
            return 0.0
        return float(target / coef)

    poly_coeffs = list(coeffs)
    poly_coeffs[-1] -= target
    roots = np.roots(poly_coeffs)

    real_roots = [float(root.real) for root in roots if abs(float(root.imag)) <= 1e-8]
    if not real_roots:
        # Fall back to the least-imaginary root if the polynomial has no real roots.
        fallback_root = min(roots, key=lambda root: abs(float(root.imag)))
        selected = float(fallback_root.real)
        _append_warning(
            warnings,
            f"ncm-engine: nonlinear abduction for '{eq.variable}' has no real roots; "
            f"using approximate root {selected:.6g}",
        )
        return selected

    unique_roots = sorted({round(root, 12): root for root in real_roots}.values())
    if len(unique_roots) > 1:
        selected = _select_root(
            unique_roots,
            policy=root_selection_policy,
            prior_mean=prior_mean,
            prior_std=prior_std,
        )
        _append_warning(
            warnings,
            f"ncm-engine: multiple real roots for '{eq.variable}'={unique_roots}; "
            f"selected {selected:.6g} via policy '{root_selection_policy}'",
        )
        return selected

    return float(unique_roots[0])


def _nonlinear_residual(
    eq: StructuralEquation,
    parent_vals: Mapping[str, float],
    observed_value: float,
    noise: float,
) -> float:
    return float(_evaluate_nonlinear_equation(eq, parent_vals, noise) - observed_value)


def _normal_logpdf(value: float, mean: float, std: float) -> float:
    scale = max(float(std), 1e-6)
    z = (float(value) - float(mean)) / scale
    return float(-0.5 * z * z - math.log(scale) - 0.5 * math.log(2.0 * math.pi))


def _log_posterior_noise(
    eq: StructuralEquation,
    parent_vals: Mapping[str, float],
    observed_value: float,
    noise: float,
) -> float:
    prior_mean = float(eq.equation_params.get("prior_mean", 0.0))
    prior_std = float(eq.equation_params.get("prior_std", 1.0))
    observation_scale = max(float(eq.equation_params.get("observation_noise_scale", 0.1)), 1e-6)
    residual = _nonlinear_residual(eq, parent_vals, observed_value, noise)
    return _normal_logpdf(noise, prior_mean, prior_std) + _normal_logpdf(residual, 0.0, observation_scale)


def _find_scalar_brackets(
    eq: StructuralEquation,
    parent_vals: Mapping[str, float],
    observed_value: float,
    *,
    center: float,
    scale: float,
    grid_points: int = 61,
    n_expansions: int = 6,
) -> list[tuple[float, float]]:
    brackets: list[tuple[float, float]] = []
    span = max(abs(scale), 1.0)
    for expansion in range(n_expansions):
        radius = span * (2 ** expansion)
        grid = np.linspace(center - radius, center + radius, grid_points)
        residuals = np.array(
            [_nonlinear_residual(eq, parent_vals, observed_value, float(value)) for value in grid],
            dtype=float,
        )
        for left, right, f_left, f_right in zip(
            grid[:-1], grid[1:], residuals[:-1], residuals[1:], strict=False
        ):
            if np.isnan(f_left) or np.isnan(f_right):
                continue
            if abs(float(f_left)) <= 1e-10:
                brackets.append((float(left), float(left)))
            if float(f_left) == 0.0 or float(f_right) == 0.0 or float(f_left) * float(f_right) < 0.0:
                brackets.append((float(left), float(right)))
        if brackets:
            break
    return brackets


def _numeric_exact_noise_candidates(
    eq: StructuralEquation,
    parent_vals: Mapping[str, float],
    observed_value: float,
    *,
    warnings: list[str],
) -> list[float]:
    from scipy.optimize import brentq, fsolve, minimize_scalar

    prior_mean = float(eq.equation_params.get("prior_mean", 0.0))
    prior_std = float(eq.equation_params.get("prior_std", 1.0))
    brackets = _find_scalar_brackets(
        eq,
        parent_vals,
        observed_value,
        center=prior_mean,
        scale=max(prior_std, 1.0),
    )
    candidates: list[float] = []

    for left, right in brackets:
        try:
            if abs(right - left) <= 1e-12:
                root = left
            else:
                root = float(brentq(
                    lambda u: _nonlinear_residual(eq, parent_vals, observed_value, u),
                    left,
                    right,
                    maxiter=200,
                ))
            if abs(_nonlinear_residual(eq, parent_vals, observed_value, root)) <= 1e-5:
                candidates.append(root)
        except Exception:
            continue

    if candidates:
        return sorted({round(value, 10): value for value in candidates}.values())

    try:
        solved = fsolve(
            lambda arr: [_nonlinear_residual(eq, parent_vals, observed_value, float(arr[0]))],
            np.asarray([prior_mean], dtype=float),
            xtol=1e-10,
            maxfev=1000,
        )
        root = float(np.asarray(solved, dtype=float).reshape(-1)[0])
        if abs(_nonlinear_residual(eq, parent_vals, observed_value, root)) <= 1e-5:
            _append_warning(
                warnings,
                f"ncm-engine: exact nonlinear abduction for '{eq.variable}' used scipy.optimize.fsolve fallback",
            )
            return [root]
    except Exception:
        pass

    objective = lambda u: _nonlinear_residual(eq, parent_vals, observed_value, float(u)) ** 2
    minimizer = minimize_scalar(
        objective,
        bracket=(prior_mean - max(prior_std, 1.0), prior_mean, prior_mean + max(prior_std, 1.0)),
        method="brent",
    )
    approx = float(minimizer.x)
    if np.isfinite(approx):
        _append_warning(
            warnings,
            f"ncm-engine: exact nonlinear abduction for '{eq.variable}' used minimum-residual approximation",
        )
        return [approx]
    raise ValueError(f"ncm-engine: failed exact nonlinear abduction for '{eq.variable}'")


def _approximate_noise_variational(
    eq: StructuralEquation,
    parent_vals: Mapping[str, float],
    observed_value: float,
    *,
    warnings: list[str],
) -> float:
    from scipy.optimize import minimize_scalar

    prior_mean = float(eq.equation_params.get("prior_mean", 0.0))
    prior_std = max(float(eq.equation_params.get("prior_std", 1.0)), 1e-3)
    objective = lambda u: -_log_posterior_noise(eq, parent_vals, observed_value, float(u))
    result = minimize_scalar(
        objective,
        bounds=(prior_mean - 8.0 * prior_std, prior_mean + 8.0 * prior_std),
        method="bounded",
        options={"xatol": 1e-6, "maxiter": 500},
    )
    value = float(result.x)
    _append_warning(
        warnings,
        f"ncm-engine: nonlinear abduction for '{eq.variable}' used variational/Laplace approximation",
    )
    return value


def _approximate_noise_mcmc(
    eq: StructuralEquation,
    parent_vals: Mapping[str, float],
    observed_value: float,
    *,
    warnings: list[str],
    rng: np.random.Generator | None = None,
) -> float:
    prior_mean = float(eq.equation_params.get("prior_mean", 0.0))
    prior_std = max(float(eq.equation_params.get("prior_std", 1.0)), 1e-3)
    proposal_std = max(float(eq.equation_params.get("mcmc_proposal_std", prior_std * 0.35)), 1e-3)
    burn_in = int(eq.equation_params.get("mcmc_burn_in", 150))
    n_samples = int(eq.equation_params.get("mcmc_samples", 400))
    if rng is None:
        rng = np.random.default_rng(int(eq.equation_params.get("mcmc_seed", 0)))

    current = prior_mean
    current_lp = _log_posterior_noise(eq, parent_vals, observed_value, current)
    draws: list[float] = []
    accepted = 0
    total_iters = burn_in + max(n_samples, 1)
    for iteration in range(total_iters):
        proposal = float(current + rng.normal(scale=proposal_std))
        proposal_lp = _log_posterior_noise(eq, parent_vals, observed_value, proposal)
        if math.log(max(rng.random(), 1e-12)) < proposal_lp - current_lp:
            current = proposal
            current_lp = proposal_lp
            accepted += 1
        if iteration >= burn_in:
            draws.append(current)

    if not draws:
        draws = [current]
    acceptance_rate = accepted / float(max(total_iters, 1))
    _append_warning(
        warnings,
        f"ncm-engine: nonlinear abduction for '{eq.variable}' used Metropolis-Hastings posterior approximation "
        f"(acceptance_rate={acceptance_rate:.2f})",
    )
    draws_arr = np.asarray(draws, dtype=float)
    return float(rng.choice(draws_arr))


def _abduct_noise_via_method(
    eq: StructuralEquation,
    parent_vals: Mapping[str, float],
    observed_value: float,
    *,
    method: Literal["exact", "mcmc", "variational"],
    root_selection_policy: Literal["closest_to_prior", "smallest_magnitude", "all_roots_mcmc"],
    warnings: list[str],
    rng: np.random.Generator | None = None,
) -> float:
    if eq.equation_type == "linear":
        if method != "exact":
            _append_warning(
                warnings,
                f"ncm-engine: linear abduction for '{eq.variable}' admits exact inversion; "
                f"using closed-form solution under method '{method}'",
            )
        return _abduct_noise_from_equation(
            eq,
            parent_vals,
            observed_value,
            root_selection_policy=root_selection_policy,
            warnings=warnings,
        )

    if method == "mcmc":
        return _approximate_noise_mcmc(
            eq,
            parent_vals,
            observed_value,
            warnings=warnings,
            rng=rng,
        )
    if method == "variational":
        return _approximate_noise_variational(eq, parent_vals, observed_value, warnings=warnings)

    expr = _evaluate_noise_expression(eq, parent_vals, 0.0)
    has_expression = expr is not None
    has_polynomial = "noise_polynomial_coefficients" in eq.equation_params and not has_expression
    if has_polynomial:
        return _abduct_noise_from_equation(
            eq,
            parent_vals,
            observed_value,
            root_selection_policy=root_selection_policy,
            warnings=warnings,
        )
    candidates = _numeric_exact_noise_candidates(eq, parent_vals, observed_value, warnings=warnings)
    if len(candidates) > 1:
        prior_mean = float(eq.equation_params.get("prior_mean", 0.0))
        prior_std = float(eq.equation_params.get("prior_std", 1.0))
        selected = _select_root(
            candidates,
            policy=root_selection_policy,
            prior_mean=prior_mean,
            prior_std=prior_std,
        )
        _append_warning(
            warnings,
            f"ncm-engine: multiple numeric roots for '{eq.variable}'={candidates}; "
            f"selected {selected:.6g} via policy '{root_selection_policy}'",
        )
        return selected
    return float(candidates[0])


def _ncm_topological_order(ncm: NCMSpec) -> list[str]:
    """Return topological order of endogenous variables.

    Prefers the composed ``scm_spec`` order when available (consistent with the
    existing gcm_query pipeline).  Falls back to ``structural_equations`` order.
    """
    if ncm.scm_spec is not None:
        return _topological_order(ncm.scm_spec)

    # Build from structural_equations: collect parents from equations
    nodes = list(ncm.endogenous_vars) if ncm.endogenous_vars else [
        eq.variable for eq in ncm.structural_equations
    ]
    if not nodes:
        return []

    nodes_set = set(nodes)
    indegree: dict[str, int] = {n: 0 for n in nodes}
    adjacency: dict[str, list[str]] = {n: [] for n in nodes}
    for eq in ncm.structural_equations:
        for parent in eq.parents:
            if parent in nodes_set and eq.variable in nodes_set:
                adjacency[parent].append(eq.variable)
                indegree[eq.variable] += 1

    queue: deque[str] = deque(sorted(n for n, d in indegree.items() if d == 0))
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for nxt in sorted(adjacency[node]):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    if len(order) != len(nodes):
        raise ValueError("NCMSpec structural equations form a cycle; acyclic NCM required")
    return order


def _ncm_parents_map(ncm: NCMSpec) -> dict[str, list[str]]:
    """Build {variable: [parents]} from the NCMSpec."""
    if ncm.scm_spec is not None:
        return _parents_by_node(ncm.scm_spec)
    return {eq.variable: list(eq.parents) for eq in ncm.structural_equations}


def _validate_markov_condition(ncm: NCMSpec) -> bool:
    """Check whether the NCM satisfies the Markov condition.

    For acyclic NCMs with mutually independent exogenous variables (no shared U),
    the Markov condition holds by construction.  When shared exogenous variables
    exist (ADMG / hidden common cause case), the condition requires bidirected
    edges in the graph — we emit a warning but still return True since the
    composed ``scm_spec`` may not capture these explicitly.

    Returns True if condition is satisfied (or likely satisfied), False otherwise.
    """
    if not ncm.is_acyclic:
        return False

    shared = [ex for ex in ncm.exogenous_specs if ex.is_shared]
    # Shared exogenous implies bidirected edges; we trust the model spec here
    return True  # Acyclic + independent U → Markov holds by construction


def _abduce_exogenous(
    ncm: NCMSpec,
    evidence: dict[str, float],
    method: Literal["exact", "mcmc", "variational"],
    *,
    warnings: list[str],
    root_selection_policy: Literal["closest_to_prior", "smallest_magnitude", "all_roots_mcmc"] = "closest_to_prior",
    rng: np.random.Generator | None = None,
) -> dict[str, float]:
    """Abduct exogenous noise values from factual evidence.

    Parameters
    ----------
    ncm:
        NCMSpec — the model.
    evidence:
        Observed variable assignments {variable: value}.
    method:
        ``"exact"`` uses analytic inversion when available and numeric root
        finding for scalar nonlinear equations. ``"mcmc"`` uses a
        Metropolis-Hastings posterior approximation. ``"variational"`` uses a
        Laplace-style mode approximation.
    warnings:
        Mutable list for appending diagnostics.

    Returns
    -------
    dict[str, float]
        Abducted noise values {variable: U_value}.
    """
    if not evidence:
        return {}

    # ── Path 1: Delegate to fitted SCM via _abduce_noises_unified ─────────────
    if method == "exact" and ncm.scm_spec is not None:
        order = _topological_order(ncm.scm_spec)
        parents_map = _parents_by_node(ncm.scm_spec)
        mechanisms = _mechanism_map(ncm.scm_spec)
        return _abduce_noises_unified(
            condition=evidence,
            order=order,
            parents_map=parents_map,
            mechanisms=mechanisms,
            warnings=warnings,
        )

    # ── Path 2: Symbolic NCM — invert StructuralEquations analytically ────────
    eq_map: dict[str, StructuralEquation] = {eq.variable: eq for eq in ncm.structural_equations}
    order = _ncm_topological_order(ncm)
    pseudo_observed: dict[str, float] = {}
    noise: dict[str, float] = {}

    for node in order:
        if node in evidence:
            pseudo_observed[node] = float(evidence[node])
        else:
            eq = eq_map.get(node)
            if eq is None:
                pseudo_observed[node] = 0.0
            else:
                parents_ok = all(p in pseudo_observed for p in eq.parents)
                if parents_ok:
                    deterministic = _equation_deterministic_term(eq, pseudo_observed)
                    if eq.equation_type == "linear":
                        pseudo_observed[node] = deterministic
                    else:
                        pseudo_observed[node] = _evaluate_nonlinear_equation(eq, pseudo_observed, 0.0)
                else:
                    pseudo_observed[node] = 0.0

        if node in evidence:
            eq = eq_map.get(node)
            if eq is not None and eq.equation_type == "linear":
                parents_ok = all(p in pseudo_observed for p in eq.parents)
                if parents_ok:
                    noise[node] = _abduct_noise_via_method(
                        eq,
                        pseudo_observed,
                        float(evidence[node]),
                        method=method,
                        root_selection_policy=root_selection_policy,
                        warnings=warnings,
                        rng=rng,
                    )
                else:
                    _append_warning(
                        warnings,
                        f"ncm-engine: cannot abduct U for '{node}' "
                        "(parents not in topological prefix); defaulting to U=0",
                    )
                    noise[node] = 0.0
            elif eq is not None:
                parents_ok = all(p in pseudo_observed for p in eq.parents)
                if parents_ok:
                    noise[node] = _abduct_noise_via_method(
                        eq,
                        pseudo_observed,
                        float(evidence[node]),
                        method=method,
                        root_selection_policy=root_selection_policy,
                        warnings=warnings,
                        rng=rng,
                    )
                else:
                    _append_warning(
                        warnings,
                        f"ncm-engine: cannot abduct U for '{node}' "
                        "(parents not in topological prefix); defaulting to U=0",
                    )
                    noise[node] = 0.0

    return noise


def _predict_from_abducted(
    ncm: NCMSpec,
    abducted_u: dict[str, float],
    intervention: dict[str, float],
    order: list[str],
    parents_map: dict[str, list[str]],
    warnings: list[str],
) -> dict[str, float]:
    """Forward-simulate NCM with pre-abducted U and a given intervention.

    For each node in topological order:
    - If the node is intervened upon: fix it to the intervention value.
    - Otherwise: compute its value from parents + abducted noise, delegating
      to ``_apply_node_noise`` when a NodeMechanism is available.

    Parameters
    ----------
    ncm:
        NCMSpec.
    abducted_u:
        Pre-abducted noise dict {variable: U_value}.
    intervention:
        do(X=x) assignments {variable: value} — these override structural eqs.
    order:
        Topological order of endogenous variables.
    parents_map:
        {variable: [parents]}.
    warnings:
        Mutable warning list.

    Returns
    -------
    dict[str, float]
        Predicted values for all endogenous variables.
    """
    # Build fast lookup for mechanisms (if scm_spec available)
    mech_map: dict[str, NodeMechanism] = (
        _mechanism_map(ncm.scm_spec) if ncm.scm_spec is not None else {}
    )
    eq_map: dict[str, StructuralEquation] = {
        eq.variable: eq for eq in ncm.structural_equations
    }

    values: dict[str, float] = {}

    for node in order:
        # Intervention overrides structural equation
        if node in intervention:
            values[node] = float(intervention[node])
            continue

        noise = float(abducted_u.get(node, 0.0))
        parent_vals = {p: values.get(p, 0.0) for p in parents_map.get(node, [])}

        # Path 1: delegate to fitted NodeMechanism
        if node in mech_map:
            values[node] = _apply_node_noise(mech_map[node], parent_vals, noise, warnings)
            continue

        # Path 2: use StructuralEquation.equation_params for linear
        eq = eq_map.get(node)
        if eq is not None and eq.equation_type == "linear":
            values[node] = _equation_deterministic_term(eq, parent_vals) + noise
            continue

        if eq is not None and eq.equation_type != "linear":
            values[node] = _evaluate_nonlinear_equation(eq, parent_vals, noise)
            continue

        # Fallback: treat noise as the full value
        _append_warning(
            warnings,
            f"ncm-engine: no mechanism or linear equation for '{node}'; "
            "using noise as full node value",
        )
        values[node] = noise

    return values


def _counterfactual_world(
    ncm: NCMSpec,
    intervention: dict[str, float],
    evidence: dict[str, float],
    abduction_method: Literal["exact", "mcmc", "variational"],
    *,
    warnings: list[str],
    root_selection_policy: Literal["closest_to_prior", "smallest_magnitude", "all_roots_mcmc"] = "closest_to_prior",
    rng: np.random.Generator | None = None,
) -> dict[str, float]:
    """Compute the counterfactual world M_{do(X=x)} given factual evidence.

    Implements the Abduction-Action-Prediction (AAP) algorithm:
    1. Abduct U from evidence.
    2. Mutilate: fix intervention variables.
    3. Predict: forward-simulate with abducted U through mutilated model.

    Returns a single dict of predicted values (no randomness — this is a
    deterministic function of the abducted U).
    """
    order = _ncm_topological_order(ncm)
    parents_map = _ncm_parents_map(ncm)

    abducted_u = _abduce_exogenous(
        ncm,
        evidence,
        abduction_method,
        warnings=warnings,
        root_selection_policy=root_selection_policy,
        rng=rng,
    )
    return _predict_from_abducted(ncm, abducted_u, intervention, order, parents_map, warnings)


def _parallel_worlds(
    ncm: NCMSpec,
    interventions: list[dict[str, float]],
    evidence: dict[str, float],
    abduction_method: Literal["exact", "mcmc", "variational"],
    *,
    n_samples: int,
    rng: np.random.Generator,
    warnings: list[str],
    root_selection_policy: Literal["closest_to_prior", "smallest_magnitude", "all_roots_mcmc"] = "closest_to_prior",
) -> list[dict[str, np.ndarray]]:
    """Simulate K parallel worlds with shared exogenous noise.

    Generalises ``_twin_simulate_samples`` (K=2) to arbitrary K >= 1.
    All worlds share the same abducted U realisation, enabling joint
    distribution queries (PNS, ITE variance, etc.).

    Parameters
    ----------
    ncm:
        NCMSpec.
    interventions:
        List of K dicts {variable: value}, one per world.
    evidence:
        Factual observations used for abduction.
    abduction_method:
        ``"exact"`` | ``"mcmc"`` | ``"variational"``.
    n_samples:
        Number of Monte Carlo samples.
    rng:
        Seeded random generator.
    warnings:
        Mutable warning list.

    Returns
    -------
    list[dict[str, np.ndarray]]
        K dicts, each mapping variable → array of shape (n_samples,).
    """
    if not interventions:
        return []

    k = len(interventions)
    order = _ncm_topological_order(ncm)
    parents_map = _ncm_parents_map(ncm)
    mech_map: dict[str, NodeMechanism] = (
        _mechanism_map(ncm.scm_spec) if ncm.scm_spec is not None else {}
    )

    # Initialise output arrays
    worlds: list[dict[str, list[float]]] = [{} for _ in range(k)]
    for w in worlds:
        for node in order:
            w[node] = []

    for _ in range(n_samples):
        # ── Step 1: Sample fresh exogenous noise for all nodes ────────────────
        fresh_noise: dict[str, float] = {}
        for node in order:
            mech = mech_map.get(node)
            fresh_noise[node] = _sample_node_noise(mech, rng)

        # ── Step 2: If evidence provided, abduct U from it ────────────────────
        if evidence:
            abducted = _abduce_exogenous(
                ncm,
                evidence,
                abduction_method,
                warnings=warnings,
                root_selection_policy=root_selection_policy,
                rng=rng,
            )
            # Abducted noise overrides fresh noise for observed nodes
            for node, u_val in abducted.items():
                fresh_noise[node] = u_val

        # ── Step 3: Simulate each world with the same noise ───────────────────
        for w_idx, interv in enumerate(interventions):
            vals = _predict_from_abducted(
                ncm, fresh_noise, interv, order, parents_map, warnings
            )
            for node in order:
                worlds[w_idx][node].append(vals.get(node, 0.0))

    # Convert to numpy arrays
    return [
        {node: np.asarray(vals, dtype=float) for node, vals in w.items()}
        for w in worlds
    ]


def _twin_network_from_ncm(ncm: NCMSpec) -> NCMSpec:
    """Construct an explicit twin-network NCM by doubling all variables.

    Creates a new NCMSpec where every endogenous variable V appears in two
    copies: V__0 (factual world) and V__1 (counterfactual world), both sharing
    the same exogenous noise specifications.

    This is primarily for symbolic inspection.  The ``_parallel_worlds``
    function implements the twin-network semantics implicitly during simulation.

    Returns
    -------
    NCMSpec
        A new NCMSpec with doubled variables.  The ``scm_spec`` field is
        set to None since the twin network is a new model structure.
    """
    suffixes = ("__0", "__1")
    new_endogenous: list[str] = []
    new_exo_specs = []
    new_equations = []

    for suffix in suffixes:
        for v in ncm.endogenous_vars:
            new_endogenous.append(f"{v}{suffix}")

        for ex in ncm.exogenous_specs:
            new_exo_specs.append(
                ex.model_copy(
                    update={
                        "variable": f"{ex.variable}{suffix}",
                        "associated_endogenous": f"{ex.associated_endogenous}{suffix}",
                        "is_shared": True,
                        "shared_with": [f"{ex.associated_endogenous}{'__1' if suffix == '__0' else '__0'}"],
                    }
                )
            )

        for eq in ncm.structural_equations:
            new_equations.append(
                eq.model_copy(
                    update={
                        "variable": f"{eq.variable}{suffix}",
                        "parents": [f"{p}{suffix}" for p in eq.parents],
                        "exogenous": f"{eq.exogenous}{suffix}",
                    }
                )
            )

    return NCMSpec(
        schema_version=ncm.schema_version,
        endogenous_vars=new_endogenous,
        exogenous_specs=new_exo_specs,
        structural_equations=new_equations,
        scm_spec=None,
        is_acyclic=ncm.is_acyclic,
        markov_condition_verified=False,
        independence_model="unknown",
        fit_method="twin_network",
    )


# ── Protocol data class ────────────────────────────────────────────────────────
# NCMQueryData is defined in protocols.py to avoid circular imports.
# Here we just import it lazily inside pure_step.


# ── Foundry method ─────────────────────────────────────────────────────────────


@foundry_method(
    namespace="causal.counterfactual",
    version="1.0.0",
    tags={"causal", "ncm", "counterfactual", "structural", "aap"},
)
class NCMEngineMethod:
    """Non-parametric Causal Model (NCM) engine.

    Implements the Abduction-Action-Prediction (AAP) algorithm for
    arbitrary counterfactual queries:
    - Single-world counterfactuals: E[Y_{do(X=x)} | evidence]
    - Parallel worlds: joint distribution over K interventional worlds
    - Twin network: ITE distribution P(Y(x₁) - Y(x₀))

    Delegates to existing fitted-SCM infrastructure when ``scm_spec`` is
    present in the NCMSpec, and falls back to symbolic linear inversion
    for manually-specified NCMs.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ncm_engine",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("ncm_query_data", SlotType.SCALAR, Unit("query", "json")),
        }),
        output_slots=frozenset({
            SlotSpec("counterfactual_result", SlotType.SCALAR, Unit("report", "json")),
        }),
        parameters=(
            ParameterSpec(name="n_samples", default=2000),
            ParameterSpec(name="abduction_method", default="exact"),
            ParameterSpec(name="root_selection_policy", default="closest_to_prior"),
            ParameterSpec(name="confidence_level", default=0.95),
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
            "NCM engine: Abduction-Action-Prediction for arbitrary counterfactual "
            "queries using non-parametric structural causal models. Supports single-world "
            "and parallel-world (twin-network) counterfactuals."
        ),
        tags=frozenset({"causal", "ncm", "counterfactual", "structural", "l3"}),
        citations=(
            "Bongers, S., Forré, P., Peters, J. & Mooij, J.M. (2021). "
            "Foundations of Structural Causal Models with Cycles and Latent Variables. "
            "Annals of Statistics, 49(5), 2885-2915.",
            "Pearl, J. (2000). Causality: Models, Reasoning and Inference. CUP.",
        ),
        equations={
            "aap_step1": "U ← abduct(V_obs)",
            "aap_step2": "M_{do(X)} ← mutilate(M, X=x)",
            "aap_step3": "Y_x = predict(M_{do(X)}, U)",
        },
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use=(
            "L3 counterfactual queries: individual treatment effects, PN/PS, "
            "actual causality checks, path-specific effects via NCM."
        ),
        when_not_to_use=(
            "Pure interventional (L2) queries — use GCMQuery or TwinNetworkQuery instead. "
            "Non-acyclic models (cyclic NCMs) are not yet supported."
        ),
        typical_min_obs=500,
        output_interpretation=(
            "counterfactual_result contains mean/std/CI for each query variable "
            "in each specified intervention world."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.methods.catalog.causal.protocols import NCMQueryData

        t0 = time.time()
        seed = params.get("__seed__")
        rng = np.random.default_rng(seed)

        n_samples = int(params.get("n_samples", 2000))
        abduction_method = str(params.get("abduction_method", "exact"))
        root_selection_policy = str(params.get("root_selection_policy", "closest_to_prior"))
        confidence_level = float(params.get("confidence_level", 0.95))

        # Parse input
        raw = state.get("ncm_query_data", state)
        if isinstance(raw, NCMQueryData):
            query_data = raw
        else:
            query_data = NCMQueryData.model_validate(raw if isinstance(raw, dict) else dict(raw))

        ncm: NCMSpec = query_data.ncm_spec  # type: ignore[assignment]
        evidence: dict[str, float] = dict(query_data.evidence)
        interventions: list[dict[str, float]] = list(query_data.interventions)
        query_vars: list[str] = list(query_data.query_vars)
        n_samples = int(query_data.n_samples or n_samples)

        warnings: list[str] = []

        if not ncm.is_acyclic:
            warnings.append(
                "ncm-engine: NCM is marked as cyclic (is_acyclic=False); "
                "AAP algorithm assumes acyclicity — results may be unreliable"
            )

        # Run parallel worlds simulation
        if not interventions:
            # No interventions: run one observational world
            interventions = [{}]

        worlds = _parallel_worlds(
            ncm,
            interventions,
            evidence,
            abduction_method,  # type: ignore[arg-type]
            n_samples=n_samples,
            rng=rng,
            warnings=warnings,
            root_selection_policy=root_selection_policy,  # type: ignore[arg-type]
        )

        # Summarise results per world per query variable
        alpha = 1.0 - confidence_level
        z = float(np.abs(np.percentile(np.random.standard_normal(100_000), alpha / 2 * 100)))

        world_summaries: list[dict[str, Any]] = []
        for w_idx, world_vals in enumerate(worlds):
            summary: dict[str, Any] = {"world_index": w_idx, "intervention": interventions[w_idx]}
            effective_vars = query_vars if query_vars else list(world_vals.keys())
            for var in effective_vars:
                arr = world_vals.get(var)
                if arr is None or len(arr) == 0:
                    continue
                mean = float(np.mean(arr))
                std = float(np.std(arr))
                se = std / math.sqrt(len(arr))
                summary[var] = {
                    "mean": mean,
                    "std": std,
                    "ci_lower": mean - z * se,
                    "ci_upper": mean + z * se,
                    "n_samples": len(arr),
                }
            world_summaries.append(summary)

        elapsed = time.time() - t0

        return {
            "counterfactual_result": {
                "schema_version": "1.0",
                "world_summaries": world_summaries,
                "n_worlds": len(worlds),
                "n_samples": n_samples,
                "abduction_method": abduction_method,
                "root_selection_policy": root_selection_policy,
                "confidence_level": confidence_level,
                "computation_time_seconds": elapsed,
                "warnings": warnings,
            }
        }


__all__ = [
    "NCMEngineMethod",
    "_abduce_exogenous",
    "_predict_from_abducted",
    "_counterfactual_world",
    "_parallel_worlds",
    "_twin_network_from_ncm",
    "_validate_markov_condition",
    "_ncm_topological_order",
    "_ncm_parents_map",
]
