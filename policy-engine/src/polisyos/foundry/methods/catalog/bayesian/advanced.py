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
from polisyos.foundry.methods.catalog.ml.protocols import PredictionResult
from polisyos.foundry.methods.catalog.ml.regression import (
    _build_prediction_result,
    _tabular_payload,
)

from .protocols import PosteriorResult, metropolis_sample, summarize_posterior_samples


def _prediction_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("posterior", "json"),
                contract_id=PosteriorResult.contract_id,
            ),
            SlotSpec(
                "prediction_result",
                SlotType.SCALAR,
                Unit("prediction", "json"),
                contract_id=PredictionResult.contract_id,
            ),
            SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
        }
    )


def _mixture_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("posterior", "json"),
                contract_id=PosteriorResult.contract_id,
            ),
            SlotSpec(
                "cluster_assignments",
                SlotType.VECTOR,
                Unit("cluster", "id"),
                shape=("n_obs",),
            ),
            SlotSpec(
                "cluster_probabilities",
                SlotType.MATRIX,
                Unit("probability", "value"),
                shape=("n_obs", "n_components"),
            ),
            SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
        }
    )


def _mapping_payload(state: Any) -> dict[str, Any]:
    if isinstance(state, Mapping):
        return dict(state)
    return _tabular_payload(state)


def _feature_names_from_payload(payload: Mapping[str, Any], n_features: int) -> list[str]:
    raw_names = payload.get("feature_names")
    if isinstance(raw_names, (list, tuple)) and len(raw_names) == n_features:
        return [str(item) for item in raw_names]
    return [f"x{idx}" for idx in range(n_features)]


def _coerce_observations(value: Any) -> np.ndarray:
    observations = np.asarray(value, dtype=float)
    if observations.ndim == 1:
        observations = observations[:, None]
    if observations.ndim != 2:
        raise ValueError("observations must be a 1D or 2D numeric array")
    if observations.shape[0] < 4:
        raise ValueError("mixture models require at least 4 observations")
    return observations


def _linear_regression_log_density_and_grad(
    theta: np.ndarray,
    *,
    x: np.ndarray,
    y: np.ndarray,
    prior_scale: float,
) -> tuple[float, np.ndarray]:
    intercept = float(theta[0])
    beta = np.asarray(theta[1:-1], dtype=float)
    log_sigma = float(theta[-1])
    sigma = float(np.exp(log_sigma))
    mean = intercept + x @ beta
    residual = y - mean
    inv_sigma_sq = 1.0 / max(sigma * sigma, 1e-9)
    log_likelihood = -float(y.shape[0]) * log_sigma - 0.5 * inv_sigma_sq * float(np.sum(residual**2))
    log_prior = -0.5 * float(np.sum((theta / max(prior_scale, 1e-9)) ** 2))
    grad = np.zeros_like(theta, dtype=float)
    grad[0] = float(np.sum(residual) * inv_sigma_sq - intercept / (prior_scale**2))
    grad[1:-1] = (x.T @ residual) * inv_sigma_sq - beta / (prior_scale**2)
    grad[-1] = -float(y.shape[0]) + float(np.sum(residual**2) * inv_sigma_sq) - log_sigma / (prior_scale**2)
    return log_likelihood + log_prior, grad


def _leapfrog(
    position: np.ndarray,
    momentum: np.ndarray,
    *,
    step_size: float,
    n_steps: int,
    x: np.ndarray,
    y: np.ndarray,
    prior_scale: float,
) -> tuple[np.ndarray, np.ndarray, float, np.ndarray]:
    current_position = np.asarray(position, dtype=float).copy()
    current_momentum = np.asarray(momentum, dtype=float).copy()
    log_density, gradient = _linear_regression_log_density_and_grad(
        current_position,
        x=x,
        y=y,
        prior_scale=prior_scale,
    )
    current_momentum = current_momentum + 0.5 * step_size * gradient
    for step_idx in range(max(1, int(n_steps))):
        current_position = current_position + step_size * current_momentum
        log_density, gradient = _linear_regression_log_density_and_grad(
            current_position,
            x=x,
            y=y,
            prior_scale=prior_scale,
        )
        if step_idx != max(1, int(n_steps)) - 1:
            current_momentum = current_momentum + step_size * gradient
    current_momentum = current_momentum + 0.5 * step_size * gradient
    return current_position, -current_momentum, float(log_density), gradient


def _hmc_sample_linear_regression(
    *,
    x: np.ndarray,
    y: np.ndarray,
    initial_state: np.ndarray,
    prior_scale: float,
    step_size: float,
    n_leapfrog: int,
    rng: np.random.Generator,
    num_warmup: int,
    num_samples: int,
    num_chains: int,
) -> tuple[np.ndarray, float]:
    draws: list[np.ndarray] = []
    accepted = 0
    attempted = 0
    for _ in range(max(1, int(num_chains))):
        current = np.asarray(initial_state, dtype=float) + rng.normal(scale=0.05, size=initial_state.shape)
        current_lp, _ = _linear_regression_log_density_and_grad(
            current,
            x=x,
            y=y,
            prior_scale=prior_scale,
        )
        local_step = max(float(step_size), 1e-4)
        chain_draws: list[np.ndarray] = []
        for step_idx in range(max(0, int(num_warmup)) + max(1, int(num_samples))):
            momentum = rng.normal(size=current.shape)
            proposal, proposal_momentum, proposal_lp, _ = _leapfrog(
                current,
                momentum,
                step_size=local_step,
                n_steps=n_leapfrog,
                x=x,
                y=y,
                prior_scale=prior_scale,
            )
            current_energy = -current_lp + 0.5 * float(np.dot(momentum, momentum))
            proposal_energy = -proposal_lp + 0.5 * float(np.dot(proposal_momentum, proposal_momentum))
            accept_prob = min(1.0, float(np.exp(current_energy - proposal_energy)))
            if float(rng.uniform()) <= accept_prob:
                current = proposal
                current_lp = proposal_lp
                accepted += 1
            attempted += 1
            if step_idx < max(0, int(num_warmup)):
                if accept_prob < 0.6:
                    local_step *= 0.92
                elif accept_prob > 0.8:
                    local_step *= 1.04
                local_step = min(max(local_step, 1e-4), 0.25)
                continue
            chain_draws.append(current.copy())
        draws.append(np.asarray(chain_draws, dtype=float))
    return np.concatenate(draws, axis=0), accepted / max(attempted, 1)


def _joint_log_density_linear_regression(
    theta: np.ndarray,
    momentum: np.ndarray,
    *,
    x: np.ndarray,
    y: np.ndarray,
    prior_scale: float,
) -> float:
    log_density, _ = _linear_regression_log_density_and_grad(
        theta,
        x=x,
        y=y,
        prior_scale=prior_scale,
    )
    return float(log_density - 0.5 * np.dot(momentum, momentum))


def _nuts_stop_criterion(
    theta_minus: np.ndarray,
    theta_plus: np.ndarray,
    momentum_minus: np.ndarray,
    momentum_plus: np.ndarray,
) -> bool:
    delta = np.asarray(theta_plus, dtype=float) - np.asarray(theta_minus, dtype=float)
    return bool(
        np.dot(delta, momentum_minus) >= 0.0
        and np.dot(delta, momentum_plus) >= 0.0
    )


def _build_nuts_tree(
    theta: np.ndarray,
    momentum: np.ndarray,
    *,
    log_slice: float,
    direction: int,
    depth: int,
    step_size: float,
    x: np.ndarray,
    y: np.ndarray,
    prior_scale: float,
    joint0: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int, bool, float, int]:
    if depth == 0:
        theta_prime, momentum_prime, _, _ = _leapfrog(
            theta,
            momentum,
            step_size=float(direction) * step_size,
            n_steps=1,
            x=x,
            y=y,
            prior_scale=prior_scale,
        )
        joint = _joint_log_density_linear_regression(
            theta_prime,
            momentum_prime,
            x=x,
            y=y,
            prior_scale=prior_scale,
        )
        n_prime = 1 if log_slice <= joint else 0
        s_prime = bool((log_slice - 1000.0) < joint)
        alpha = min(1.0, float(np.exp(min(0.0, joint - joint0))))
        return (
            theta_prime,
            momentum_prime,
            theta_prime,
            momentum_prime,
            theta_prime,
            n_prime,
            s_prime,
            alpha,
            1,
        )

    (
        theta_minus,
        momentum_minus,
        theta_plus,
        momentum_plus,
        theta_prime,
        n_prime,
        s_prime,
        alpha_sum,
        alpha_count,
    ) = _build_nuts_tree(
        theta,
        momentum,
        log_slice=log_slice,
        direction=direction,
        depth=depth - 1,
        step_size=step_size,
        x=x,
        y=y,
        prior_scale=prior_scale,
        joint0=joint0,
        rng=rng,
    )
    if not s_prime:
        return (
            theta_minus,
            momentum_minus,
            theta_plus,
            momentum_plus,
            theta_prime,
            n_prime,
            s_prime,
            alpha_sum,
            alpha_count,
        )

    if direction < 0:
        (
            theta_minus_2,
            momentum_minus_2,
            _,
            _,
            theta_prime_2,
            n_prime_2,
            s_prime_2,
            alpha_2,
            alpha_count_2,
        ) = _build_nuts_tree(
            theta_minus,
            momentum_minus,
            log_slice=log_slice,
            direction=direction,
            depth=depth - 1,
            step_size=step_size,
            x=x,
            y=y,
            prior_scale=prior_scale,
            joint0=joint0,
            rng=rng,
        )
        theta_minus = theta_minus_2
        momentum_minus = momentum_minus_2
    else:
        (
            _,
            _,
            theta_plus_2,
            momentum_plus_2,
            theta_prime_2,
            n_prime_2,
            s_prime_2,
            alpha_2,
            alpha_count_2,
        ) = _build_nuts_tree(
            theta_plus,
            momentum_plus,
            log_slice=log_slice,
            direction=direction,
            depth=depth - 1,
            step_size=step_size,
            x=x,
            y=y,
            prior_scale=prior_scale,
            joint0=joint0,
            rng=rng,
        )
        theta_plus = theta_plus_2
        momentum_plus = momentum_plus_2

    if (n_prime + n_prime_2) > 0 and float(rng.uniform()) < (n_prime_2 / max(n_prime + n_prime_2, 1)):
        theta_prime = theta_prime_2
    n_prime += n_prime_2
    s_prime = bool(
        s_prime
        and s_prime_2
        and _nuts_stop_criterion(theta_minus, theta_plus, momentum_minus, momentum_plus)
    )
    return (
        theta_minus,
        momentum_minus,
        theta_plus,
        momentum_plus,
        theta_prime,
        n_prime,
        s_prime,
        alpha_sum + alpha_2,
        alpha_count + alpha_count_2,
    )


def _nuts_sample_linear_regression(
    *,
    x: np.ndarray,
    y: np.ndarray,
    initial_state: np.ndarray,
    prior_scale: float,
    step_size: float,
    max_depth: int,
    rng: np.random.Generator,
    num_warmup: int,
    num_samples: int,
    num_chains: int,
    target_accept: float,
) -> tuple[np.ndarray, float]:
    draws: list[np.ndarray] = []
    accepted_weight = 0.0
    total_weight = 0
    for _ in range(max(1, int(num_chains))):
        current = np.asarray(initial_state, dtype=float) + rng.normal(scale=0.03, size=initial_state.shape)
        local_step = max(float(step_size), 1e-4)
        chain_draws: list[np.ndarray] = []
        for step_idx in range(max(0, int(num_warmup)) + max(1, int(num_samples))):
            momentum0 = rng.normal(size=current.shape)
            joint0 = _joint_log_density_linear_regression(
                current,
                momentum0,
                x=x,
                y=y,
                prior_scale=prior_scale,
            )
            log_slice = joint0 - float(rng.exponential(1.0))
            theta_minus = current.copy()
            theta_plus = current.copy()
            momentum_minus = momentum0.copy()
            momentum_plus = momentum0.copy()
            theta_candidate = current.copy()
            depth = 0
            n = 1
            continue_tree = True
            alpha_sum = 0.0
            alpha_count = 0
            while continue_tree and depth < max(1, int(max_depth)):
                direction = -1 if float(rng.uniform()) < 0.5 else 1
                if direction < 0:
                    (
                        theta_minus,
                        momentum_minus,
                        _,
                        _,
                        theta_prime,
                        n_prime,
                        s_prime,
                        alpha_prime,
                        alpha_count_prime,
                    ) = _build_nuts_tree(
                        theta_minus,
                        momentum_minus,
                        log_slice=log_slice,
                        direction=direction,
                        depth=depth,
                        step_size=local_step,
                        x=x,
                        y=y,
                        prior_scale=prior_scale,
                        joint0=joint0,
                        rng=rng,
                    )
                else:
                    (
                        _,
                        _,
                        theta_plus,
                        momentum_plus,
                        theta_prime,
                        n_prime,
                        s_prime,
                        alpha_prime,
                        alpha_count_prime,
                    ) = _build_nuts_tree(
                        theta_plus,
                        momentum_plus,
                        log_slice=log_slice,
                        direction=direction,
                        depth=depth,
                        step_size=local_step,
                        x=x,
                        y=y,
                        prior_scale=prior_scale,
                        joint0=joint0,
                        rng=rng,
                    )
                if s_prime and (n + n_prime) > 0 and float(rng.uniform()) < (n_prime / max(n + n_prime, 1)):
                    theta_candidate = theta_prime.copy()
                n += n_prime
                continue_tree = bool(
                    s_prime
                    and _nuts_stop_criterion(theta_minus, theta_plus, momentum_minus, momentum_plus)
                )
                alpha_sum += alpha_prime
                alpha_count += alpha_count_prime
                depth += 1
            accept_rate = alpha_sum / max(alpha_count, 1)
            accepted_weight += accept_rate
            total_weight += 1
            current = theta_candidate
            if step_idx < max(0, int(num_warmup)):
                if accept_rate < target_accept:
                    local_step *= 0.9
                else:
                    local_step *= 1.03
                local_step = min(max(local_step, 1e-4), 0.25)
                continue
            chain_draws.append(current.copy())
        draws.append(np.asarray(chain_draws, dtype=float))
    return np.concatenate(draws, axis=0), accepted_weight / max(total_weight, 1)


def _diag_gaussian_log_prob(
    observations: np.ndarray,
    means: np.ndarray,
    variances: np.ndarray,
) -> np.ndarray:
    safe_variances = np.maximum(variances, 1e-6)
    diff = observations[:, None, :] - means[None, :, :]
    quadratic = np.sum((diff**2) / safe_variances[None, :, :], axis=2)
    norm = np.sum(np.log(2.0 * np.pi * safe_variances), axis=1)
    return -0.5 * (quadratic + norm[None, :])


def _fit_bayesian_gaussian_mixture(
    observations: np.ndarray,
    *,
    n_components: int,
    concentration: float,
    max_iter: int,
    seed: int,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    x = _coerce_observations(observations)
    n_obs, n_features = x.shape
    n_components = max(1, min(int(n_components), n_obs))

    base_var = np.var(x, axis=0, ddof=1) if n_obs > 1 else np.ones(n_features, dtype=float)
    base_var = np.maximum(base_var, 1e-3)
    init_idx = np.linspace(0, n_obs - 1, num=n_components, dtype=int)
    means = x[init_idx].copy() + rng.normal(scale=1e-3, size=(n_components, n_features))
    variances = np.broadcast_to(base_var, (n_components, n_features)).copy()
    weights = np.full(n_components, 1.0 / n_components, dtype=float)

    log_likelihood = float("-inf")
    for iteration in range(max(5, int(max_iter))):
        log_prob = _diag_gaussian_log_prob(x, means, variances) + np.log(weights + 1e-12)[None, :]
        max_log_prob = np.max(log_prob, axis=1, keepdims=True)
        stabilized = np.exp(log_prob - max_log_prob)
        normalizer = np.sum(stabilized, axis=1, keepdims=True)
        responsibilities = stabilized / np.maximum(normalizer, 1e-12)
        component_mass = np.sum(responsibilities, axis=0) + 1e-6
        weights = np.maximum(component_mass + float(concentration) - 1.0, 1e-6)
        weights = weights / np.sum(weights)
        means = (responsibilities.T @ x) / component_mass[:, None]
        diff = x[:, None, :] - means[None, :, :]
        variances = np.sum(responsibilities[:, :, None] * diff**2, axis=0) / component_mass[:, None]
        variances = np.maximum(variances, 1e-6)
        next_log_likelihood = float(
            np.sum(max_log_prob[:, 0] + np.log(np.maximum(normalizer[:, 0], 1e-12)))
        )
        if abs(next_log_likelihood - log_likelihood) < 1e-6:
            log_likelihood = next_log_likelihood
            break
        log_likelihood = next_log_likelihood

    assignments = np.argmax(responsibilities, axis=1).astype(float)
    entropy = float(
        -np.mean(np.sum(responsibilities * np.log(np.maximum(responsibilities, 1e-12)), axis=1))
    )
    return {
        "weights": weights,
        "means": means,
        "variances": variances,
        "responsibilities": responsibilities,
        "assignments": assignments,
        "component_mass": component_mass,
        "entropy": entropy,
        "log_likelihood": log_likelihood,
        "iterations": float(iteration + 1),
        "n_obs": float(n_obs),
    }


def _mixture_posterior_result(
    *,
    method_name: str,
    fitted: Mapping[str, Any],
    concentration: float,
) -> PosteriorResult:
    weights = np.asarray(fitted["weights"], dtype=float)
    means = np.asarray(fitted["means"], dtype=float)
    variances = np.asarray(fitted["variances"], dtype=float)
    component_mass = np.asarray(fitted["component_mass"], dtype=float)
    n_obs = max(float(fitted.get("n_obs", means.shape[0])), 1.0)

    posterior_means: dict[str, float] = {}
    posterior_stds: dict[str, float] = {}
    credible_intervals: dict[str, tuple[float, float]] = {}
    for component_idx in range(weights.shape[0]):
        weight = float(weights[component_idx])
        weight_std = float(np.sqrt(max(weight * (1.0 - weight), 1e-9) / n_obs))
        posterior_means[f"weight_{component_idx}"] = weight
        posterior_stds[f"weight_{component_idx}"] = weight_std
        credible_intervals[f"weight_{component_idx}"] = (
            max(0.0, weight - 1.96 * weight_std),
            min(1.0, weight + 1.96 * weight_std),
        )
        for feature_idx in range(means.shape[1]):
            label = f"mean_{component_idx}_{feature_idx}"
            mean_value = float(means[component_idx, feature_idx])
            mean_std = float(
                np.sqrt(max(variances[component_idx, feature_idx], 1e-9) / max(component_mass[component_idx], 1.0))
            )
            posterior_means[label] = mean_value
            posterior_stds[label] = mean_std
            credible_intervals[label] = (
                mean_value - 1.96 * mean_std,
                mean_value + 1.96 * mean_std,
            )
            variance_label = f"variance_{component_idx}_{feature_idx}"
            variance_value = float(variances[component_idx, feature_idx])
            variance_std = float(variance_value / np.sqrt(max(component_mass[component_idx], 1.0)))
            posterior_means[variance_label] = variance_value
            posterior_stds[variance_label] = variance_std
            credible_intervals[variance_label] = (
                max(1e-9, variance_value - 1.96 * variance_std),
                variance_value + 1.96 * variance_std,
            )

    return PosteriorResult(
        method_name=method_name,
        posterior_means=posterior_means,
        posterior_stds=posterior_stds,
        credible_intervals=credible_intervals,
        diagnostics={
            "n_components": float(weights.shape[0]),
            "log_likelihood": float(fitted["log_likelihood"]),
            "entropy": float(fitted["entropy"]),
            "iterations": float(fitted["iterations"]),
            "concentration": float(concentration),
            "num_samples": float(fitted["n_obs"]),
        },
        metadata={
            "component_mass": component_mass.tolist(),
            "active_components": int(np.sum(weights > 1e-3)),
        },
    )


@foundry_method(
    namespace="bayesian.regression",
    version="1.0.0",
    tags={"bayesian", "hierarchical", "regression"},
)
class BayesianHierarchicalRegressionEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    optional_deps: ClassVar[tuple[str, ...]] = ("arviz",)
    method_variant: ClassVar[str] = "hierarchical"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="hierarchical",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "features",
                    SlotType.MATRIX,
                    Unit("feature", "value"),
                    shape=("n_obs", "n_features"),
                ),
                SlotSpec("target", SlotType.VECTOR, Unit("target", "value"), shape=("n_obs",)),
                SlotSpec("group_ids", SlotType.VECTOR, Unit("group", "id"), shape=("n_obs",)),
            }
        ),
        output_slots=_prediction_output_slots(),
        parameters=(
            ParameterSpec(name="prior_scale", default=1.5),
            ParameterSpec(name="group_scale_prior", default=1.0),
            ParameterSpec(name="num_warmup", default=128),
            ParameterSpec(name="num_samples", default=192),
            ParameterSpec(name="num_chains", default=1),
            ParameterSpec(name="credible_mass", default=0.9),
            ParameterSpec(name="proposal_scale", default=0.035),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Random-intercept Bayesian hierarchical regression with partial pooling across groups.",
        tags=frozenset({"bayesian", "hierarchical", "regression"}),
        when_to_use="Grouped data with partial pooling; schools, regions, time periods; partial pooling across groups",
        when_not_to_use="No meaningful grouping structure; all groups have large equal samples",
        typical_min_obs=30,
        output_interpretation="Group-level estimates shrink toward grand mean. Shrinkage amount depends on group size and variance.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _mapping_payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _mapping_payload(state)
        x = np.asarray(payload["features"], dtype=float)
        y = np.asarray(payload["target"], dtype=float)
        group_ids = np.asarray(payload["group_ids"])
        if x.ndim != 2:
            raise ValueError("hierarchical regression expects a 2D feature matrix")
        if y.ndim != 1 or group_ids.ndim != 1:
            raise ValueError("target and group_ids must be 1D vectors")
        if x.shape[0] != y.shape[0] or group_ids.shape[0] != y.shape[0]:
            raise ValueError("features, target, and group_ids must have the same number of rows")

        _, group_index = np.unique(group_ids.astype(str), return_inverse=True)
        n_groups = int(np.max(group_index)) + 1
        prior_scale = max(1e-3, float(params.get("prior_scale", 1.5)))
        group_scale_prior = max(1e-3, float(params.get("group_scale_prior", 1.0)))
        num_warmup = max(32, int(params.get("num_warmup", 128)))
        num_samples = max(32, int(params.get("num_samples", 192)))
        num_chains = max(1, int(params.get("num_chains", 1)))
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)
        proposal_scale = max(1e-4, float(params.get("proposal_scale", 0.035)))

        ols_design = np.column_stack([np.ones(x.shape[0]), x])
        ols_coef = np.linalg.pinv(ols_design) @ y
        residuals = y - ols_design @ ols_coef
        sigma0 = max(float(np.std(residuals, ddof=max(ols_design.shape[1], 1))), 0.1)
        group_std = np.array(
            [np.mean(residuals[group_index == idx]) for idx in range(n_groups)],
            dtype=float,
        )
        tau0 = max(float(np.std(group_std, ddof=1)) if n_groups > 1 else 0.25, 0.1)
        initial = np.concatenate(
            [
                np.array([ols_coef[0]], dtype=float),
                np.asarray(ols_coef[1:], dtype=float),
                np.zeros(n_groups, dtype=float),
                np.array([np.log(sigma0), np.log(tau0)], dtype=float),
            ]
        )
        rng = np.random.default_rng(int(params.get("__seed__", 0)))

        def log_density(theta: np.ndarray) -> float:
            intercept = theta[0]
            beta = theta[1: 1 + x.shape[1]]
            group_offsets = theta[1 + x.shape[1]: 1 + x.shape[1] + n_groups]
            log_sigma = theta[-2]
            log_tau = theta[-1]
            sigma = float(np.exp(log_sigma))
            tau = float(np.exp(log_tau))
            mean = intercept + x @ beta + group_offsets[group_index]
            residual = y - mean
            log_likelihood = -0.5 * np.sum(
                (residual / sigma) ** 2 + 2.0 * log_sigma + np.log(2.0 * np.pi)
            )
            log_prior_global = -0.5 * ((intercept / prior_scale) ** 2 + (log_tau / group_scale_prior) ** 2)
            log_prior_beta = -0.5 * np.sum((beta / prior_scale) ** 2)
            log_prior_offsets = -0.5 * np.sum(
                (group_offsets / tau) ** 2 + 2.0 * log_tau + np.log(2.0 * np.pi)
            )
            log_prior_scale = -0.5 * (log_sigma / prior_scale) ** 2
            return float(
                log_likelihood
                + log_prior_global
                + log_prior_beta
                + log_prior_offsets
                + log_prior_scale
            )

        draws, accept_rate = metropolis_sample(
            log_density=log_density,
            initial_state=initial,
            proposal_scale=np.full(initial.shape, proposal_scale, dtype=float),
            rng=rng,
            num_warmup=num_warmup,
            num_samples=num_samples,
            num_chains=num_chains,
        )
        intercept_draws = draws[:, 0]
        beta_draws = draws[:, 1: 1 + x.shape[1]]
        group_offset_draws = draws[:, 1 + x.shape[1]: 1 + x.shape[1] + n_groups]
        posterior = {
            "global_intercept": intercept_draws,
            "coefficients": beta_draws,
            "group_effect": group_offset_draws,
            "sigma": np.exp(draws[:, -2]),
            "group_scale": np.exp(draws[:, -1]),
        }
        posterior_means, posterior_stds, credible_intervals = summarize_posterior_samples(
            posterior,
            credible_mass=credible_mass,
        )
        fitted = (
            posterior_means["global_intercept"]
            + x @ np.asarray(
                [posterior_means.get(f"coefficients_{idx}", 0.0) for idx in range(x.shape[1])],
                dtype=float,
            )
            + np.asarray(
                [posterior_means.get(f"group_effect_{group}", 0.0) for group in group_index],
                dtype=float,
            )
        )
        prediction_output = _build_prediction_result(
            method_name="bayesian_hierarchical_regression",
            predictions=fitted,
            target=y,
            coefficients={
                "intercept": posterior_means["global_intercept"],
                **{
                    name: posterior_means.get(f"coefficients_{idx}", 0.0)
                    for idx, name in enumerate(_feature_names_from_payload(payload, x.shape[1]))
                },
            },
            model_info={"library": "numpy", "estimator": "BayesianHierarchicalRegressionMCMC"},
            metadata={"n_groups": n_groups, "num_samples": num_samples},
        )
        posterior_result = PosteriorResult(
            method_name="bayesian_hierarchical_regression",
            posterior_means=posterior_means,
            posterior_stds=posterior_stds,
            credible_intervals=credible_intervals,
            diagnostics={
                "acceptance_rate": float(accept_rate),
                "credible_mass": float(credible_mass),
                "num_warmup": float(num_warmup),
                "num_samples": float(num_samples),
                "num_chains": float(num_chains),
                "n_groups": float(n_groups),
            },
            metadata={
                "group_labels": [str(item) for item in np.unique(group_ids.astype(str))],
                "feature_names": _feature_names_from_payload(payload, x.shape[1]),
            },
        )
        return {
            "result": posterior_result,
            "prediction_result": prediction_output["result"],
            "uncertainty_envelope": posterior_result.to_uncertainty_envelope(
                param_name="group_scale"
            ),
        }


@foundry_method(
    namespace="bayesian.sampling",
    version="1.0.0",
    tags={"bayesian", "sampling", "hmc"},
)
class BayesianHMCRegressionEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    optional_deps: ClassVar[tuple[str, ...]] = ("arviz",)
    method_variant: ClassVar[str] = "hmc"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="hmc",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "features",
                    SlotType.MATRIX,
                    Unit("feature", "value"),
                    shape=("n_obs", "n_features"),
                ),
                SlotSpec("target", SlotType.VECTOR, Unit("target", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_prediction_output_slots(),
        parameters=(
            ParameterSpec(name="prior_scale", default=2.0),
            ParameterSpec(name="step_size", default=0.02),
            ParameterSpec(name="n_leapfrog", default=12),
            ParameterSpec(name="num_warmup", default=64),
            ParameterSpec(name="num_samples", default=128),
            ParameterSpec(name="num_chains", default=2),
            ParameterSpec(name="credible_mass", default=0.9),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Hamiltonian Monte Carlo sampler for Bayesian linear regression with adaptive warmup step size.",
        tags=frozenset({"bayesian", "sampling", "hmc"}),
        when_to_use="Bayesian regression where Metropolis-Hastings mixes poorly; correlated posteriors; moderate sample sizes",
        when_not_to_use="Very high-dimensional parameter space; gradient computation is expensive",
        typical_min_obs=30,
        output_interpretation="Posterior samples over regression coefficients. Check acceptance rate (target 60–80%). HMC produces less correlated chains than Metropolis.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _mapping_payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _mapping_payload(state)
        x = np.asarray(payload["features"], dtype=float)
        y = np.asarray(payload["target"], dtype=float)
        if x.ndim != 2:
            raise ValueError("hmc regression expects a 2D feature matrix")
        if y.ndim != 1 or y.shape[0] != x.shape[0]:
            raise ValueError("target must be a 1D vector aligned with features")

        prior_scale = max(1e-3, float(params.get("prior_scale", 2.0)))
        step_size = max(1e-4, float(params.get("step_size", 0.02)))
        n_leapfrog = max(4, int(params.get("n_leapfrog", 12)))
        num_warmup = max(32, int(params.get("num_warmup", 64)))
        num_samples = max(32, int(params.get("num_samples", 128)))
        num_chains = max(1, int(params.get("num_chains", 2)))
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)

        ols_design = np.column_stack([np.ones(x.shape[0]), x])
        ols_coef = np.linalg.pinv(ols_design) @ y
        residual = y - ols_design @ ols_coef
        initial = np.concatenate(
            [
                np.asarray(ols_coef, dtype=float),
                np.array([np.log(max(float(np.std(residual, ddof=max(ols_design.shape[1], 1))), 0.1))], dtype=float),
            ]
        )
        rng = np.random.default_rng(int(params.get("__seed__", 0)))
        draws, accept_rate = _hmc_sample_linear_regression(
            x=x,
            y=y,
            initial_state=initial,
            prior_scale=prior_scale,
            step_size=step_size,
            n_leapfrog=n_leapfrog,
            rng=rng,
            num_warmup=num_warmup,
            num_samples=num_samples,
            num_chains=num_chains,
        )
        posterior = {
            "intercept": draws[:, 0],
            "coefficients": draws[:, 1:-1],
            "sigma": np.exp(draws[:, -1]),
        }
        posterior_means, posterior_stds, credible_intervals = summarize_posterior_samples(
            posterior,
            credible_mass=credible_mass,
        )
        coefficients = np.asarray(
            [posterior_means.get(f"coefficients_{idx}", 0.0) for idx in range(x.shape[1])],
            dtype=float,
        )
        predictions = posterior_means["intercept"] + x @ coefficients
        prediction_output = _build_prediction_result(
            method_name="bayesian_hmc_regression",
            predictions=predictions,
            target=y,
            coefficients={
                "intercept": posterior_means["intercept"],
                **{
                    name: posterior_means.get(f"coefficients_{idx}", 0.0)
                    for idx, name in enumerate(_feature_names_from_payload(payload, x.shape[1]))
                },
            },
            model_info={"library": "numpy", "estimator": "BayesianHMCRegression"},
            metadata={"num_samples": num_samples, "num_chains": num_chains},
        )
        posterior_result = PosteriorResult(
            method_name="bayesian_hmc_regression",
            posterior_means=posterior_means,
            posterior_stds=posterior_stds,
            credible_intervals=credible_intervals,
            diagnostics={
                "acceptance_rate": float(accept_rate),
                "credible_mass": float(credible_mass),
                "num_warmup": float(num_warmup),
                "num_samples": float(num_samples),
                "num_chains": float(num_chains),
                "step_size": float(step_size),
                "n_leapfrog": float(n_leapfrog),
            },
            metadata={"feature_names": _feature_names_from_payload(payload, x.shape[1])},
        )
        return {
            "result": posterior_result,
            "prediction_result": prediction_output["result"],
            "uncertainty_envelope": posterior_result.to_uncertainty_envelope(param_name="sigma"),
        }


@foundry_method(
    namespace="bayesian.sampling",
    version="1.0.0",
    tags={"bayesian", "sampling", "nuts"},
)
class BayesianNUTSRegressionEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    optional_deps: ClassVar[tuple[str, ...]] = ("arviz",)
    method_variant: ClassVar[str] = "nuts"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="nuts",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "features",
                    SlotType.MATRIX,
                    Unit("feature", "value"),
                    shape=("n_obs", "n_features"),
                ),
                SlotSpec("target", SlotType.VECTOR, Unit("target", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_prediction_output_slots(),
        parameters=(
            ParameterSpec(name="prior_scale", default=2.0),
            ParameterSpec(name="step_size", default=0.018),
            ParameterSpec(name="max_depth", default=5),
            ParameterSpec(name="target_accept", default=0.75),
            ParameterSpec(name="num_warmup", default=64),
            ParameterSpec(name="num_samples", default=128),
            ParameterSpec(name="num_chains", default=2),
            ParameterSpec(name="credible_mass", default=0.9),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="No-U-Turn Sampler for Bayesian linear regression with dynamic trajectory expansion.",
        tags=frozenset({"bayesian", "sampling", "nuts"}),
        when_to_use="Bayesian regression requiring efficient exploration of curved posteriors; preferred over HMC when step count is hard to tune",
        when_not_to_use="Very high-dimensional or non-differentiable posteriors; speed-critical contexts where VI suffices",
        typical_min_obs=30,
        output_interpretation="Posterior samples with dynamic trajectory length. NUTS typically achieves higher ESS per sample than Metropolis or fixed-step HMC.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _mapping_payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _mapping_payload(state)
        x = np.asarray(payload["features"], dtype=float)
        y = np.asarray(payload["target"], dtype=float)
        if x.ndim != 2:
            raise ValueError("nuts regression expects a 2D feature matrix")
        if y.ndim != 1 or y.shape[0] != x.shape[0]:
            raise ValueError("target must be a 1D vector aligned with features")

        prior_scale = max(1e-3, float(params.get("prior_scale", 2.0)))
        step_size = max(1e-4, float(params.get("step_size", 0.018)))
        max_depth = max(3, int(params.get("max_depth", 5)))
        target_accept = min(max(float(params.get("target_accept", 0.75)), 0.5), 0.95)
        num_warmup = max(32, int(params.get("num_warmup", 64)))
        num_samples = max(32, int(params.get("num_samples", 128)))
        num_chains = max(1, int(params.get("num_chains", 2)))
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)

        ols_design = np.column_stack([np.ones(x.shape[0]), x])
        ols_coef = np.linalg.pinv(ols_design) @ y
        residual = y - ols_design @ ols_coef
        initial = np.concatenate(
            [
                np.asarray(ols_coef, dtype=float),
                np.array([np.log(max(float(np.std(residual, ddof=max(ols_design.shape[1], 1))), 0.1))], dtype=float),
            ]
        )
        rng = np.random.default_rng(int(params.get("__seed__", 0)))
        draws, accept_rate = _nuts_sample_linear_regression(
            x=x,
            y=y,
            initial_state=initial,
            prior_scale=prior_scale,
            step_size=step_size,
            max_depth=max_depth,
            rng=rng,
            num_warmup=num_warmup,
            num_samples=num_samples,
            num_chains=num_chains,
            target_accept=target_accept,
        )
        posterior = {
            "intercept": draws[:, 0],
            "coefficients": draws[:, 1:-1],
            "sigma": np.exp(draws[:, -1]),
        }
        posterior_means, posterior_stds, credible_intervals = summarize_posterior_samples(
            posterior,
            credible_mass=credible_mass,
        )
        coefficients = np.asarray(
            [posterior_means.get(f"coefficients_{idx}", 0.0) for idx in range(x.shape[1])],
            dtype=float,
        )
        predictions = posterior_means["intercept"] + x @ coefficients
        prediction_output = _build_prediction_result(
            method_name="bayesian_nuts_regression",
            predictions=predictions,
            target=y,
            coefficients={
                "intercept": posterior_means["intercept"],
                **{
                    name: posterior_means.get(f"coefficients_{idx}", 0.0)
                    for idx, name in enumerate(_feature_names_from_payload(payload, x.shape[1]))
                },
            },
            model_info={"library": "numpy", "estimator": "BayesianNUTSRegression"},
            metadata={"num_samples": num_samples, "num_chains": num_chains},
        )
        posterior_result = PosteriorResult(
            method_name="bayesian_nuts_regression",
            posterior_means=posterior_means,
            posterior_stds=posterior_stds,
            credible_intervals=credible_intervals,
            diagnostics={
                "acceptance_rate": float(accept_rate),
                "credible_mass": float(credible_mass),
                "num_warmup": float(num_warmup),
                "num_samples": float(num_samples),
                "num_chains": float(num_chains),
                "step_size": float(step_size),
                "max_depth": float(max_depth),
                "target_accept": float(target_accept),
            },
            metadata={"feature_names": _feature_names_from_payload(payload, x.shape[1])},
        )
        return {
            "result": posterior_result,
            "prediction_result": prediction_output["result"],
            "uncertainty_envelope": posterior_result.to_uncertainty_envelope(param_name="sigma"),
        }


@foundry_method(
    namespace="bayesian.nonparametric",
    version="1.0.0",
    tags={"bayesian", "mixture", "gaussian-mixture", "tabular", "estimation", "uncertainty"},
)
class BayesianGaussianMixtureEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "gaussian_mixture"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="gaussian_mixture",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "observations",
                    SlotType.MATRIX,
                    Unit("observation", "value"),
                    shape=("n_obs", "n_features"),
                )
            }
        ),
        output_slots=_mixture_output_slots(),
        parameters=(
            ParameterSpec(name="n_components", default=3),
            ParameterSpec(name="concentration", default=1.0),
            ParameterSpec(name="max_iter", default=64),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Finite Bayesian Gaussian mixture with diagonal covariance and Dirichlet-smoothed EM updates.",
        tags=frozenset({"bayesian", "mixture", "gaussian-mixture"}),
        when_to_use="Known number of latent clusters; density estimation with soft assignments; policy heterogeneity analysis",
        when_not_to_use="Number of components is unknown (use Dirichlet Process); data has non-Gaussian cluster shapes",
        typical_min_obs=100,
        output_interpretation="Component means, weights, and soft cluster assignments per observation. Dirichlet smoothing prevents degenerate components.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _mapping_payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _mapping_payload(state)
        fitted = _fit_bayesian_gaussian_mixture(
            payload["observations"],
            n_components=int(params.get("n_components", 3)),
            concentration=max(1e-3, float(params.get("concentration", 1.0))),
            max_iter=max(8, int(params.get("max_iter", 64))),
            seed=int(params.get("__seed__", 0)),
        )
        posterior_result = _mixture_posterior_result(
            method_name="bayesian_gaussian_mixture",
            fitted=fitted,
            concentration=float(params.get("concentration", 1.0)),
        )
        return {
            "result": posterior_result,
            "cluster_assignments": np.asarray(fitted["assignments"], dtype=float),
            "cluster_probabilities": np.asarray(fitted["responsibilities"], dtype=float),
            "uncertainty_envelope": posterior_result.to_uncertainty_envelope(
                param_name="weight_0"
            ),
        }


@foundry_method(
    namespace="bayesian.nonparametric",
    version="1.0.0",
    tags={"bayesian", "nonparametric", "dirichlet-process", "tabular", "estimation", "uncertainty"},
)
class DirichletProcessMixtureEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "dirichlet_process_mixture"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="dirichlet_process_mixture",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "observations",
                    SlotType.MATRIX,
                    Unit("observation", "value"),
                    shape=("n_obs", "n_features"),
                )
            }
        ),
        output_slots=_mixture_output_slots(),
        parameters=(
            ParameterSpec(name="max_components", default=8),
            ParameterSpec(name="concentration", default=0.75),
            ParameterSpec(name="prune_threshold", default=0.05),
            ParameterSpec(name="max_iter", default=96),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Truncated Dirichlet-process Gaussian mixture with adaptive component pruning.",
        tags=frozenset({"bayesian", "nonparametric", "dirichlet-process"}),
        when_to_use="Unknown number of clusters; flexible density estimation; mixture models with unknown components",
        when_not_to_use="Number of components is known and fixed; small dataset where DP complexity is unwarranted",
        typical_min_obs=100,
        output_interpretation="Posterior distribution over number of clusters and cluster memberships. DP concentration α controls expected number of clusters.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _mapping_payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _mapping_payload(state)
        fitted = _fit_bayesian_gaussian_mixture(
            payload["observations"],
            n_components=int(params.get("max_components", 8)),
            concentration=max(1e-3, float(params.get("concentration", 0.75))),
            max_iter=max(16, int(params.get("max_iter", 96))),
            seed=int(params.get("__seed__", 0)),
        )
        prune_threshold = min(max(float(params.get("prune_threshold", 0.05)), 0.0), 0.5)
        active = np.asarray(fitted["weights"], dtype=float) >= prune_threshold
        if not np.any(active):
            active[np.argmax(np.asarray(fitted["weights"], dtype=float))] = True
        responsibilities = np.asarray(fitted["responsibilities"], dtype=float)[:, active]
        responsibilities = responsibilities / np.maximum(
            np.sum(responsibilities, axis=1, keepdims=True),
            1e-12,
        )
        weights = np.asarray(fitted["weights"], dtype=float)[active]
        weights = weights / np.sum(weights)
        means = np.asarray(fitted["means"], dtype=float)[active]
        variances = np.asarray(fitted["variances"], dtype=float)[active]
        component_mass = np.sum(responsibilities, axis=0)
        pruned = {
            "weights": weights,
            "means": means,
            "variances": variances,
            "responsibilities": responsibilities,
            "assignments": np.argmax(responsibilities, axis=1).astype(float),
            "component_mass": component_mass,
            "entropy": float(fitted["entropy"]),
            "log_likelihood": float(fitted["log_likelihood"]),
            "iterations": float(fitted["iterations"]),
            "n_obs": float(fitted["n_obs"]),
        }
        posterior_result = _mixture_posterior_result(
            method_name="dirichlet_process_mixture",
            fitted=pruned,
            concentration=float(params.get("concentration", 0.75)),
        ).model_copy(
            update={
                "metadata": {
                    "active_components": int(np.sum(active)),
                    "prune_threshold": prune_threshold,
                }
            }
        )
        return {
            "result": posterior_result,
            "cluster_assignments": np.asarray(pruned["assignments"], dtype=float),
            "cluster_probabilities": responsibilities,
            "uncertainty_envelope": posterior_result.to_uncertainty_envelope(
                param_name="weight_0"
            ),
        }


__all__ = [
    "BayesianGaussianMixtureEstimator",
    "BayesianHMCRegressionEstimator",
    "BayesianNUTSRegressionEstimator",
    "BayesianHierarchicalRegressionEstimator",
    "DirichletProcessMixtureEstimator",
]
