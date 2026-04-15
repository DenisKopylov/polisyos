"""Frontier Bayesian interfaces with dependency-aware runtime truthfulness."""
from __future__ import annotations

from dataclasses import replace
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
from polisyos.foundry.methods.catalog.ml.protocols import PredictionResult, TabularData
from polisyos.foundry.methods.catalog.ml.regression import _build_prediction_result, _feature_names
from polisyos.foundry.uncertainty.protocol import UncertaintyDecomposition

from .protocols import PosteriorResult, summarize_posterior_samples


def _posterior_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("posterior", "json"),
                contract_id=PosteriorResult.contract_id,
            ),
            SlotSpec(
                "posterior_samples",
                SlotType.MATRIX,
                Unit("posterior", "draw"),
                shape=("n_samples", "n_parameters"),
            ),
            SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
        }
    )


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


def _coerce_sbi_payload(state: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    parameters = np.asarray(state["parameters"], dtype=float)
    simulations = np.asarray(state["simulations"], dtype=float)
    observed = np.asarray(state["observed_summary"], dtype=float)
    if parameters.ndim == 1:
        parameters = parameters[:, None]
    if simulations.ndim == 1:
        simulations = simulations[:, None]
    if observed.ndim != 1:
        observed = observed.reshape(-1)
    if parameters.ndim != 2 or simulations.ndim != 2:
        raise ValueError("parameters and simulations must be 1D or 2D numeric arrays")
    if parameters.shape[0] != simulations.shape[0]:
        raise ValueError("parameters and simulations must have the same number of rows")
    if simulations.shape[1] != observed.shape[0]:
        raise ValueError("observed_summary dimension must match simulation summary columns")
    if parameters.shape[0] < 16:
        raise ValueError("SBI methods require at least 16 simulated parameter/summary pairs")
    return parameters, simulations, observed


def _runtime_backend(params: Mapping[str, Any]) -> str:
    return str(params.get("__bayesian_runtime_backend__", "unavailable")).strip().lower()


def _require_backend(params: Mapping[str, Any], expected: str) -> None:
    actual = _runtime_backend(params)
    if actual != expected:
        raise RuntimeError(
            f"Bayesian frontier method requires runtime_backend={expected!r}; "
            f"resolved runtime_backend={actual!r}"
        )


def _sbi_infer(
    *,
    algorithm: str,
    parameters: np.ndarray,
    simulations: np.ndarray,
    observed_summary: np.ndarray,
    num_posterior_samples: int,
    num_training_epochs: int,
    seed: int,
) -> np.ndarray:
    _require_numpy_finite("parameters", parameters)
    _require_numpy_finite("simulations", simulations)
    _require_numpy_finite("observed_summary", observed_summary)
    try:
        import torch
        from sbi.inference import SNLE, SNPE, SNRE
    except Exception as exc:  # pragma: no cover - optional runtime dependency
        raise RuntimeError("SBI runtime requires installed 'sbi' and 'torch' packages") from exc

    torch.manual_seed(int(seed))
    theta = torch.as_tensor(parameters, dtype=torch.float32)
    x = torch.as_tensor(simulations, dtype=torch.float32)
    observed = torch.as_tensor(observed_summary, dtype=torch.float32)
    inference_cls = {"npe": SNPE, "nle": SNLE, "nre": SNRE}[algorithm]
    try:
        inference = inference_cls(prior=None)
        estimator = inference.append_simulations(theta, x).train(
            max_num_epochs=max(1, int(num_training_epochs)),
            show_train_summary=False,
        )
        posterior = inference.build_posterior(estimator)
        samples = posterior.sample((max(1, int(num_posterior_samples)),), x=observed)
    except Exception as exc:  # pragma: no cover - optional runtime dependency
        raise RuntimeError(f"SBI {algorithm.upper()} inference failed") from exc
    return np.asarray(samples.detach().cpu().numpy(), dtype=float)


def _require_numpy_finite(label: str, value: np.ndarray) -> None:
    if not np.all(np.isfinite(value)):
        raise ValueError(f"{label} must contain only finite numeric values")


def _posterior_from_samples(
    *,
    method_name: str,
    samples: np.ndarray,
    credible_mass: float,
    parameter_names: list[str],
    metadata: Mapping[str, Any],
) -> PosteriorResult:
    sample_map = {
        name: samples[:, idx]
        for idx, name in enumerate(parameter_names)
    }
    posterior_means, posterior_stds, credible_intervals = summarize_posterior_samples(
        sample_map,
        credible_mass=credible_mass,
    )
    return PosteriorResult(
        method_name=method_name,
        posterior_means=posterior_means,
        posterior_stds=posterior_stds,
        credible_intervals=credible_intervals,
        diagnostics={
            "credible_mass": float(credible_mass),
            "num_samples": float(samples.shape[0]),
            "num_parameters": float(samples.shape[1]),
        },
        metadata=dict(metadata),
    )


def _logsumexp(values: np.ndarray, axis: int | None = None) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    max_value = np.max(arr, axis=axis, keepdims=True)
    stable = np.exp(arr - max_value)
    result = np.log(np.sum(stable, axis=axis, keepdims=True)) + max_value
    if axis is None:
        return np.asarray(result.reshape(()), dtype=float)
    return np.squeeze(result, axis=axis)


def _linear_regression_grad_particles(
    particles: np.ndarray,
    *,
    x: np.ndarray,
    y: np.ndarray,
    prior_scale: float,
) -> np.ndarray:
    gradients = np.zeros_like(particles, dtype=float)
    prior_var = max(prior_scale * prior_scale, 1e-9)
    for idx, theta in enumerate(particles):
        intercept = float(theta[0])
        beta = theta[1:-1]
        log_sigma = float(theta[-1])
        sigma = float(np.exp(np.clip(log_sigma, -20.0, 20.0)))
        residual = y - (intercept + x @ beta)
        inv_sigma_sq = 1.0 / max(sigma * sigma, 1e-9)
        gradients[idx, 0] = float(np.sum(residual) * inv_sigma_sq - intercept / prior_var)
        gradients[idx, 1:-1] = (x.T @ residual) * inv_sigma_sq - beta / prior_var
        gradients[idx, -1] = (
            -float(y.shape[0])
            + float(np.sum(residual**2) * inv_sigma_sq)
            - log_sigma / prior_var
        )
    return gradients


def _median_bandwidth(particles: np.ndarray) -> float:
    diffs = particles[:, None, :] - particles[None, :, :]
    dist_sq = np.sum(diffs * diffs, axis=-1)
    positive = dist_sq[dist_sq > 0.0]
    if positive.size == 0:
        return 1.0
    median = float(np.median(positive))
    return max(median / np.log(particles.shape[0] + 1.0), 1e-6)


@foundry_method(
    namespace="bayesian.approximation",
    version="1.0.0",
    tags={"bayesian", "expectation-propagation", "ep", "structural", "uncertainty"},
)
class ExpectationPropagationGaussianEstimator:
    """Combine Gaussian site approximations into a posterior approximation; this is EP for Gaussian sites, not arbitrary black-box EP."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "ep"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="expectation_propagation_gaussian",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("site_means", SlotType.MATRIX, Unit("parameter", "value"), shape=("n_sites", "n_parameters")),
                SlotSpec("site_variances", SlotType.MATRIX, Unit("variance", "value"), shape=("n_sites", "n_parameters")),
            }
        ),
        output_slots=_posterior_output_slots(),
        parameters=(
            ParameterSpec(name="prior_mean", default=None),
            ParameterSpec(name="prior_variance", default=None),
            ParameterSpec(name="credible_mass", default=0.9),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Expectation-propagation style product of Gaussian site approximations.",
        tags=frozenset({"bayesian", "expectation-propagation", "ep", "structural", "uncertainty"}),
        when_to_use="Distributed or factorized Gaussian site approximations where EP sites are already computed.",
        when_not_to_use="Non-Gaussian site approximations that require iterative moment projection.",
        citations=("Minka, T. P. (2001). Expectation propagation for approximate Bayesian inference. UAI.",),
        output_interpretation="Gaussian posterior approximation obtained by multiplying prior and site precisions.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        site_means = np.asarray(state["site_means"], dtype=float)
        site_vars = np.asarray(state["site_variances"], dtype=float)
        if site_means.ndim != 2 or site_vars.shape != site_means.shape:
            raise ValueError("site_means and site_variances must be aligned 2D arrays")
        if not np.all(np.isfinite(site_means)) or not np.all(np.isfinite(site_vars)):
            raise ValueError("site means/variances must be finite")
        if np.any(site_vars <= 0.0):
            raise ValueError("site_variances must be strictly positive")
        n_params = site_means.shape[1]
        prior_mean = params.get("prior_mean")
        prior_var = params.get("prior_variance")
        prior_mean_arr = (
            np.zeros(n_params, dtype=float)
            if prior_mean is None
            else np.broadcast_to(np.asarray(prior_mean, dtype=float), (n_params,))
        )
        prior_var_arr = (
            np.full(n_params, 1e6, dtype=float)
            if prior_var is None
            else np.broadcast_to(np.asarray(prior_var, dtype=float), (n_params,))
        )
        if np.any(prior_var_arr <= 0.0):
            raise ValueError("prior_variance must be strictly positive")
        precision = (1.0 / prior_var_arr) + np.sum(1.0 / site_vars, axis=0)
        posterior_var = 1.0 / precision
        posterior_mean = posterior_var * (
            prior_mean_arr / prior_var_arr + np.sum(site_means / site_vars, axis=0)
        )
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)
        rng = np.random.default_rng(int(params.get("__seed__", 0)))
        samples = rng.normal(
            loc=posterior_mean,
            scale=np.sqrt(np.maximum(posterior_var, 1e-12)),
            size=(max(64, site_means.shape[0] * 8), n_params),
        )
        names = [str(item) for item in state.get("parameter_names", [f"theta_{idx}" for idx in range(n_params)])]
        if len(names) != n_params:
            names = [f"theta_{idx}" for idx in range(n_params)]
        posterior = _posterior_from_samples(
            method_name="expectation_propagation_gaussian",
            samples=samples,
            credible_mass=credible_mass,
            parameter_names=names,
            metadata={
                "approximation_family": "gaussian_site_product",
                "num_sites": int(site_means.shape[0]),
                "truthfulness_tier": "gaussian_ep_site_approximation",
            },
        )
        return {
            "result": posterior,
            "posterior_samples": samples,
            "uncertainty_envelope": posterior.to_uncertainty_envelope(),
        }


@foundry_method(
    namespace="bayesian.variational",
    version="1.0.0",
    tags={"bayesian", "svgd", "regression", "tabular", "uncertainty"},
)
class SVGDRegressionEstimator:
    """Approximate a Bayesian linear-regression posterior with Stein variational gradient descent particles."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "svgd"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="svgd_regression",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("features", SlotType.MATRIX, Unit("feature", "value"), shape=("n_obs", "n_features")),
                SlotSpec("target", SlotType.VECTOR, Unit("target", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_prediction_output_slots(),
        parameters=(
            ParameterSpec(name="prior_scale", default=1.5),
            ParameterSpec(name="num_particles", default=48),
            ParameterSpec(name="num_steps", default=96),
            ParameterSpec(name="step_size", default=0.01),
            ParameterSpec(name="credible_mass", default=0.9),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Stein variational gradient descent approximation for Bayesian linear regression.",
        tags=frozenset({"bayesian", "svgd", "regression", "tabular", "uncertainty"}),
        when_to_use="Fast particle posterior approximation when MCMC is too slow and linear-Gaussian likelihood is acceptable.",
        when_not_to_use="Strongly multimodal or non-differentiable posteriors; use HMC/NUTS where exactness matters.",
        citations=("Liu, Q. & Wang, D. (2016). Stein variational gradient descent: A general purpose Bayesian inference algorithm. NeurIPS.",),
        output_interpretation="Particles approximate the coefficient posterior; intervals are empirical particle quantiles.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TabularData:
        payload = dict(fallback_state) if isinstance(fallback_state, Mapping) else fallback_state
        if isinstance(payload, Mapping):
            merged = dict(payload)
            merged.update(bound_inputs)
            return TabularData.model_validate(merged)
        return TabularData.model_validate(payload)

    @staticmethod
    def pure_step(state: Mapping[str, Any] | TabularData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, TabularData) else TabularData.model_validate(state)
        x = np.asarray(data.features, dtype=float)
        y = np.asarray(data.target, dtype=float)
        if y.ndim != 1 or y.shape[0] != x.shape[0]:
            raise ValueError("target must be a 1D vector aligned with features")
        _require_numpy_finite("features", x)
        _require_numpy_finite("target", y)
        prior_scale = max(1e-3, float(params.get("prior_scale", 1.5)))
        num_particles = max(8, int(params.get("num_particles", 48)))
        num_steps = max(1, int(params.get("num_steps", 96)))
        step_size = min(max(float(params.get("step_size", 0.01)), 1e-5), 0.2)
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)
        rng = np.random.default_rng(int(params.get("__seed__", 0)))
        design = np.column_stack([np.ones(x.shape[0]), x])
        ols_coef = np.linalg.pinv(design) @ y
        residual = y - design @ ols_coef
        sigma0 = max(float(np.std(residual, ddof=max(design.shape[1], 1))), 0.1)
        center = np.concatenate([ols_coef, np.array([np.log(sigma0)], dtype=float)])
        particles = center + rng.normal(scale=0.15, size=(num_particles, center.shape[0]))
        for _ in range(num_steps):
            gradients = _linear_regression_grad_particles(
                particles,
                x=x,
                y=y,
                prior_scale=prior_scale,
            )
            diffs = particles[:, None, :] - particles[None, :, :]
            bandwidth = _median_bandwidth(particles)
            kernel = np.exp(-np.sum(diffs * diffs, axis=-1) / bandwidth)
            attraction = kernel @ gradients
            repulsion = (2.0 / bandwidth) * np.sum(kernel[:, :, None] * (-diffs), axis=1)
            particles = particles + (step_size / num_particles) * (attraction + repulsion)
        posterior_samples = np.column_stack([particles[:, :-1], np.exp(particles[:, -1])])
        parameter_names = ["intercept", *(_feature_names(data)), "sigma"]
        posterior = _posterior_from_samples(
            method_name="svgd_regression",
            samples=posterior_samples,
            credible_mass=credible_mass,
            parameter_names=parameter_names,
            metadata={
                "num_particles": num_particles,
                "num_steps": num_steps,
                "truthfulness_tier": "particle_variational_approximation",
            },
        )
        coefficients = np.asarray(
            [posterior.posterior_means.get(name, 0.0) for name in _feature_names(data)],
            dtype=float,
        )
        predictions = posterior.posterior_means["intercept"] + x @ coefficients
        prediction_output = _build_prediction_result(
            method_name="svgd_regression",
            predictions=predictions,
            target=y,
            coefficients={
                "intercept": posterior.posterior_means["intercept"],
                **{name: posterior.posterior_means.get(name, 0.0) for name in _feature_names(data)},
            },
            model_info={"library": "numpy", "estimator": "SVGDRegression"},
            metadata={"num_particles": num_particles, "num_steps": num_steps},
        )
        return {
            "result": posterior,
            "prediction_result": prediction_output["result"],
            "uncertainty_envelope": posterior.to_uncertainty_envelope(param_name="sigma"),
        }


@foundry_method(
    namespace="bayesian.flow",
    version="1.0.0",
    tags={"bayesian", "normalizing-flow", "affine-flow", "structural", "uncertainty"},
)
class AffineNormalizingFlowPosteriorAdapter:
    """Fit a truthful affine normalizing-flow surrogate to posterior samples."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "flow"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="affine_normalizing_flow",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "posterior_samples",
                    SlotType.MATRIX,
                    Unit("posterior", "draw"),
                    shape=("n_samples", "n_parameters"),
                )
            }
        ),
        output_slots=_posterior_output_slots(),
        parameters=(
            ParameterSpec(name="num_flow_samples", default=256),
            ParameterSpec(name="credible_mass", default=0.9),
            ParameterSpec(name="jitter", default=1e-6),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Affine normalizing-flow posterior adapter fitted to existing posterior samples.",
        tags=frozenset({"bayesian", "normalizing-flow", "affine-flow", "structural", "uncertainty"}),
        when_to_use="Compress posterior samples into a lightweight affine flow baseline for replay and downstream sampling.",
        when_not_to_use="Need expressive nonlinear flows; use a dedicated trainable flow stack instead.",
        citations=("Rezende, D. & Mohamed, S. (2015). Variational inference with normalizing flows. ICML.",),
        output_interpretation="Generated samples preserve posterior mean/covariance through an affine Gaussianizing map; metadata marks this as an affine-flow baseline.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        samples = np.asarray(state["posterior_samples"], dtype=float)
        if samples.ndim == 1:
            samples = samples[:, None]
        if samples.ndim != 2 or samples.shape[0] < 4:
            raise ValueError("posterior_samples must be a 2D array with at least 4 rows")
        _require_numpy_finite("posterior_samples", samples)
        num_flow_samples = max(16, int(params.get("num_flow_samples", 256)))
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)
        jitter = max(float(params.get("jitter", 1e-6)), 1e-12)
        mean = np.mean(samples, axis=0)
        cov = np.cov(samples, rowvar=False)
        cov = np.atleast_2d(cov) + jitter * np.eye(samples.shape[1])
        rng = np.random.default_rng(int(params.get("__seed__", 0)))
        generated = rng.multivariate_normal(mean=mean, cov=cov, size=num_flow_samples)
        names = [str(item) for item in state.get("parameter_names", [f"theta_{idx}" for idx in range(samples.shape[1])])]
        if len(names) != samples.shape[1]:
            names = [f"theta_{idx}" for idx in range(samples.shape[1])]
        posterior = _posterior_from_samples(
            method_name="affine_normalizing_flow",
            samples=generated,
            credible_mass=credible_mass,
            parameter_names=names,
            metadata={
                "flow_family": "affine_gaussian",
                "truthfulness_tier": "baseline_affine_flow_adapter",
                "source_num_samples": int(samples.shape[0]),
            },
        )
        return {
            "result": posterior,
            "posterior_samples": generated,
            "uncertainty_envelope": posterior.to_uncertainty_envelope(),
        }


@foundry_method(
    namespace="bayesian.graphical",
    version="1.0.0",
    tags={"bayesian", "factor-graph", "belief-propagation", "network", "uncertainty"},
)
class FactorGraphBeliefPropagationEstimator:
    """Run loopy sum-product belief propagation on a pairwise discrete factor graph."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "factor_graph"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="factor_graph_belief_propagation",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("unary_log_potentials", SlotType.MATRIX, Unit("log_potential", "value"), shape=("n_variables", "n_states")),
                SlotSpec("edges", SlotType.MATRIX, Unit("edge", "id"), shape=("n_edges", 2)),
                SlotSpec("pairwise_log_potentials", SlotType.SCALAR, Unit("log_potential", "tensor")),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("posterior", "json"),
                    contract_id=PosteriorResult.contract_id,
                ),
                SlotSpec("marginals", SlotType.MATRIX, Unit("probability", "value"), shape=("n_variables", "n_states")),
                SlotSpec("map_assignment", SlotType.VECTOR, Unit("state", "id"), shape=("n_variables",)),
            }
        ),
        parameters=(
            ParameterSpec(name="max_iter", default=64),
            ParameterSpec(name="damping", default=0.2),
            ParameterSpec(name="tol", default=1e-6),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Pairwise discrete factor-graph inference via loopy belief propagation.",
        tags=frozenset({"bayesian", "factor-graph", "belief-propagation", "network", "uncertainty"}),
        when_to_use="Discrete graphical-model inference where exact junction-tree inference is too expensive.",
        when_not_to_use="Continuous latent variables or graphs requiring guaranteed convergence/exact marginals.",
        citations=("Kschischang, F. R., Frey, B. J. & Loeliger, H. A. (2001). Factor graphs and the sum-product algorithm. IEEE TIT.",),
        output_interpretation="Approximate node marginals and MAP states; diagnostics include convergence delta.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        unary = np.asarray(state["unary_log_potentials"], dtype=float)
        edges = np.asarray(state["edges"], dtype=int)
        pairwise = np.asarray(state["pairwise_log_potentials"], dtype=float)
        if unary.ndim != 2:
            raise ValueError("unary_log_potentials must be a 2D array")
        if edges.ndim != 2 or edges.shape[1] != 2:
            raise ValueError("edges must have shape (n_edges, 2)")
        if pairwise.shape != (edges.shape[0], unary.shape[1], unary.shape[1]):
            raise ValueError("pairwise_log_potentials must have shape (n_edges, n_states, n_states)")
        _require_numpy_finite("unary_log_potentials", unary)
        _require_numpy_finite("pairwise_log_potentials", pairwise)
        if np.any(edges < 0) or np.any(edges >= unary.shape[0]):
            raise ValueError("edges contain variable indexes outside unary_log_potentials")
        max_iter = max(1, int(params.get("max_iter", 64)))
        damping = min(max(float(params.get("damping", 0.2)), 0.0), 0.99)
        tol = max(float(params.get("tol", 1e-6)), 0.0)
        n_edges, n_states = edges.shape[0], unary.shape[1]
        messages_forward = np.full((n_edges, n_states), -np.log(n_states), dtype=float)
        messages_backward = np.full((n_edges, n_states), -np.log(n_states), dtype=float)
        incident: list[list[tuple[int, int]]] = [[] for _ in range(unary.shape[0])]
        for edge_idx, (src, dst) in enumerate(edges):
            incident[int(src)].append((edge_idx, 1))
            incident[int(dst)].append((edge_idx, -1))
        delta = float("inf")
        iterations = 0
        for iterations in range(1, max_iter + 1):
            next_forward = messages_forward.copy()
            next_backward = messages_backward.copy()
            for edge_idx, (src_raw, dst_raw) in enumerate(edges):
                src = int(src_raw)
                dst = int(dst_raw)
                src_belief = unary[src].copy()
                for other_edge, direction in incident[src]:
                    if other_edge == edge_idx:
                        continue
                    src_belief += messages_backward[other_edge] if direction == 1 else messages_forward[other_edge]
                candidate_forward = _logsumexp(src_belief[:, None] + pairwise[edge_idx], axis=0)
                candidate_forward -= _logsumexp(candidate_forward)
                dst_belief = unary[dst].copy()
                for other_edge, direction in incident[dst]:
                    if other_edge == edge_idx:
                        continue
                    dst_belief += messages_backward[other_edge] if direction == 1 else messages_forward[other_edge]
                candidate_backward = _logsumexp(dst_belief[None, :] + pairwise[edge_idx], axis=1)
                candidate_backward -= _logsumexp(candidate_backward)
                next_forward[edge_idx] = (
                    damping * messages_forward[edge_idx] + (1.0 - damping) * candidate_forward
                )
                next_backward[edge_idx] = (
                    damping * messages_backward[edge_idx] + (1.0 - damping) * candidate_backward
                )
            delta = max(
                float(np.max(np.abs(next_forward - messages_forward))),
                float(np.max(np.abs(next_backward - messages_backward))),
            )
            messages_forward = next_forward
            messages_backward = next_backward
            if delta <= tol:
                break
        log_marginals = unary.copy()
        for node_idx, incoming in enumerate(incident):
            for edge_idx, direction in incoming:
                log_marginals[node_idx] += (
                    messages_backward[edge_idx] if direction == 1 else messages_forward[edge_idx]
                )
            log_marginals[node_idx] -= _logsumexp(log_marginals[node_idx])
        marginals = np.exp(log_marginals)
        map_assignment = np.argmax(marginals, axis=1).astype(int)
        posterior = PosteriorResult(
            method_name="factor_graph_belief_propagation",
            posterior_means={
                f"variable_{idx}": float(np.sum(marginals[idx] * np.arange(n_states)))
                for idx in range(marginals.shape[0])
            },
            posterior_stds={
                f"variable_{idx}": float(
                    np.sqrt(
                        np.sum(marginals[idx] * (np.arange(n_states) - np.sum(marginals[idx] * np.arange(n_states))) ** 2)
                    )
                )
                for idx in range(marginals.shape[0])
            },
            credible_intervals={
                f"variable_{idx}": (float(map_assignment[idx]), float(map_assignment[idx]))
                for idx in range(marginals.shape[0])
            },
            diagnostics={
                "iterations": float(iterations),
                "final_delta": float(delta),
                "num_edges": float(n_edges),
                "num_states": float(n_states),
            },
            metadata={"inference_family": "loopy_sum_product", "truthfulness_tier": "approximate_factor_graph"},
        )
        return {
            "result": posterior,
            "marginals": marginals,
            "map_assignment": map_assignment,
        }


class _SBIBase:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("sbi", "torch", "numpy")
    optional_deps: ClassVar[tuple[str, ...]] = ("sbi", "torch")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="sbi_base",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "parameters",
                    SlotType.MATRIX,
                    Unit("parameter", "value"),
                    shape=("n_simulations", "n_parameters"),
                ),
                SlotSpec(
                    "simulations",
                    SlotType.MATRIX,
                    Unit("summary", "value"),
                    shape=("n_simulations", "n_summaries"),
                ),
                SlotSpec(
                    "observed_summary",
                    SlotType.VECTOR,
                    Unit("summary", "value"),
                    shape=("n_summaries",),
                ),
            }
        ),
        output_slots=_posterior_output_slots(),
        parameters=(
            ParameterSpec(name="runtime_backend", default="auto"),
            ParameterSpec(name="num_training_epochs", default=64),
            ParameterSpec(name="num_posterior_samples", default=256),
            ParameterSpec(name="credible_mass", default=0.9),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    @classmethod
    def _run(cls, state: Mapping[str, Any], params: Mapping[str, Any], *, algorithm: str) -> dict[str, Any]:
        _require_backend(params, "sbi")
        parameter_draws, simulations, observed_summary = _coerce_sbi_payload(state)
        num_training_epochs = max(1, int(params.get("num_training_epochs", 64)))
        num_posterior_samples = max(32, int(params.get("num_posterior_samples", 256)))
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)
        samples = _sbi_infer(
            algorithm=algorithm,
            parameters=parameter_draws,
            simulations=simulations,
            observed_summary=observed_summary,
            num_posterior_samples=num_posterior_samples,
            num_training_epochs=num_training_epochs,
            seed=int(params.get("__seed__", 0)),
        )
        parameter_names = [
            str(item)
            for item in state.get(
                "parameter_names",
                [f"theta_{idx}" for idx in range(samples.shape[1])],
            )
        ]
        if len(parameter_names) != samples.shape[1]:
            parameter_names = [f"theta_{idx}" for idx in range(samples.shape[1])]
        posterior = _posterior_from_samples(
            method_name=f"simulation_based_{algorithm}",
            samples=samples,
            credible_mass=credible_mass,
            parameter_names=parameter_names,
            metadata={
                "sbi_algorithm": algorithm.upper(),
                "runtime_backend_used": "sbi",
                "num_training_epochs": num_training_epochs,
                "summary_dimension": int(simulations.shape[1]),
                "observed_summary": observed_summary.tolist(),
            },
        )
        return {
            "result": posterior,
            "posterior_samples": samples,
            "uncertainty_envelope": posterior.to_uncertainty_envelope(),
        }


@foundry_method(
    namespace="bayesian.sbi",
    version="1.0.0",
    tags={"bayesian", "sbi", "npe", "likelihood-free", "structural"},
)
class SimulationBasedNPEEstimator(_SBIBase):
    """Run neural posterior estimation for likelihood-free policy simulators; requires the real `sbi` runtime."""

    method_variant: ClassVar[str] = "npe"
    signature: ClassVar[MethodSignature] = replace(_SBIBase.signature, name="npe")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Simulation-based neural posterior estimation using the installed SBI stack.",
        tags=frozenset({"bayesian", "sbi", "npe", "likelihood-free", "structural"}),
        when_to_use="Likelihood-free calibration where simulator summaries and parameter draws are available.",
        when_not_to_use="Installed runtime lacks sbi/torch, or the prior/simulation design is poorly specified.",
        citations=("Papamakarios, G. & Murray, I. (2016). Fast epsilon-free inference of simulation models with Bayesian conditional density estimation. NeurIPS.",),
        output_interpretation="Posterior samples over simulator parameters conditioned on observed summary statistics.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        return SimulationBasedNPEEstimator._run(state, params, algorithm="npe")


@foundry_method(
    namespace="bayesian.sbi",
    version="1.0.0",
    tags={"bayesian", "sbi", "nle", "likelihood-free", "structural"},
)
class SimulationBasedNLEEstimator(_SBIBase):
    """Run neural likelihood estimation for likelihood-free policy simulators; requires the real `sbi` runtime."""

    method_variant: ClassVar[str] = "nle"
    signature: ClassVar[MethodSignature] = replace(_SBIBase.signature, name="nle")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Simulation-based neural likelihood estimation using the installed SBI stack.",
        tags=frozenset({"bayesian", "sbi", "nle", "likelihood-free", "structural"}),
        when_to_use="Likelihood-free policy models where likelihood estimation is preferable to direct posterior estimation.",
        when_not_to_use="Installed runtime lacks sbi/torch, or posterior sampling through the learned likelihood is ill-conditioned.",
        citations=("Papamakarios, G. et al. (2019). Sequential neural likelihood. AISTATS.",),
        output_interpretation="Posterior samples drawn through the learned likelihood conditioned on observed summaries.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        return SimulationBasedNLEEstimator._run(state, params, algorithm="nle")


@foundry_method(
    namespace="bayesian.sbi",
    version="1.0.0",
    tags={"bayesian", "sbi", "nre", "likelihood-free", "structural"},
)
class SimulationBasedNREEstimator(_SBIBase):
    """Run neural ratio estimation for likelihood-free policy simulators; requires the real `sbi` runtime."""

    method_variant: ClassVar[str] = "nre"
    signature: ClassVar[MethodSignature] = replace(_SBIBase.signature, name="nre")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Simulation-based neural ratio estimation using the installed SBI stack.",
        tags=frozenset({"bayesian", "sbi", "nre", "likelihood-free", "structural"}),
        when_to_use="Likelihood-free policy models where ratio estimation is more stable than density estimation.",
        when_not_to_use="Installed runtime lacks sbi/torch, or simulator coverage around observed summaries is weak.",
        citations=("Hermans, J., Begy, V. & Louppe, G. (2020). Likelihood-free MCMC with amortized approximate ratio estimators. ICML.",),
        output_interpretation="Posterior samples obtained from learned likelihood-to-evidence ratio estimates.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        return SimulationBasedNREEstimator._run(state, params, algorithm="nre")


@foundry_method(
    namespace="bayesian.nonparametric",
    version="1.0.0",
    tags={"bayesian", "bart", "nonparametric", "heterogeneity"},
)
class BayesianBARTRegressorEstimator:
    """Fit Bayesian additive regression trees for nonlinear policy heterogeneity; requires PyMC-BART."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("pymc", "pymc-bart", "arviz", "numpy")
    optional_deps: ClassVar[tuple[str, ...]] = ("pymc", "pymc-bart", "arviz")
    method_variant: ClassVar[str] = "bart"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="bart_regression",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("features", SlotType.MATRIX, Unit("feature", "value"), shape=("n_obs", "n_features")),
                SlotSpec("target", SlotType.VECTOR, Unit("target", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_prediction_output_slots(),
        parameters=(
            ParameterSpec(name="runtime_backend", default="auto"),
            ParameterSpec(name="num_trees", default=50),
            ParameterSpec(name="num_warmup", default=128),
            ParameterSpec(name="num_samples", default=256),
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
        description="Bayesian additive regression trees for nonlinear heterogeneous policy response surfaces.",
        tags=frozenset({"bayesian", "bart", "nonparametric", "heterogeneity"}),
        when_to_use="Nonlinear policy heterogeneity with enough observations and an installed PyMC-BART runtime.",
        when_not_to_use="PyMC-BART is unavailable, exact structural interpretation is required, or dataset is too small for tree ensembles.",
        citations=("Chipman, H. A., George, E. I. & McCulloch, R. E. (2010). BART: Bayesian additive regression trees. Annals of Applied Statistics.",),
        output_interpretation="Posterior predictive draws and credible intervals over nonlinear response surfaces.",
        typical_min_obs=80,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TabularData:
        payload = dict(fallback_state) if isinstance(fallback_state, Mapping) else fallback_state
        if isinstance(payload, Mapping):
            merged = dict(payload)
            merged.update(bound_inputs)
            return TabularData.model_validate(merged)
        return TabularData.model_validate(payload)

    @staticmethod
    def pure_step(state: Mapping[str, Any] | TabularData, params: Mapping[str, Any]) -> dict[str, Any]:
        _require_backend(params, "pymc_bart")
        data = state if isinstance(state, TabularData) else TabularData.model_validate(state)
        x = np.asarray(data.features, dtype=float)
        y = np.asarray(data.target, dtype=float)
        if y.ndim != 1 or y.shape[0] != x.shape[0]:
            raise ValueError("target must be a 1D vector aligned with features")
        _require_numpy_finite("features", x)
        _require_numpy_finite("target", y)
        try:
            import pymc as pm
            import pymc_bart as pmb
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError("BART runtime requires installed 'pymc' and 'pymc_bart' packages") from exc

        num_trees = max(5, int(params.get("num_trees", 50)))
        num_warmup = max(32, int(params.get("num_warmup", 128)))
        num_samples = max(32, int(params.get("num_samples", 256)))
        num_chains = max(1, int(params.get("num_chains", 2)))
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)
        seed = int(params.get("__seed__", 0))
        with pm.Model() as model:
            sigma = pm.HalfNormal("sigma", sigma=max(float(np.std(y, ddof=1)), 1e-3))
            mu = pmb.BART("mu", X=x, Y=y, m=num_trees)
            pm.Normal("obs", mu=mu, sigma=sigma, observed=y)
            idata = pm.sample(
                draws=num_samples,
                tune=num_warmup,
                chains=num_chains,
                random_seed=seed,
                progressbar=False,
                compute_convergence_checks=False,
            )

        mu_draws = np.asarray(idata.posterior["mu"], dtype=float).reshape(-1, x.shape[0])
        sigma_draws = np.asarray(idata.posterior["sigma"], dtype=float).reshape(-1)
        predictions = np.mean(mu_draws, axis=0)
        posterior_means = {
            "posterior_predictive_mean": float(np.mean(predictions)),
            "sigma": float(np.mean(sigma_draws)),
        }
        posterior_stds = {
            "posterior_predictive_mean": float(np.std(np.mean(mu_draws, axis=1), ddof=1)),
            "sigma": float(np.std(sigma_draws, ddof=1)) if sigma_draws.shape[0] > 1 else 0.0,
        }
        alpha = max(1e-6, 1.0 - credible_mass)
        predictive_mean_draws = np.mean(mu_draws, axis=1)
        credible_intervals = {
            "posterior_predictive_mean": tuple(
                float(item) for item in np.quantile(predictive_mean_draws, [alpha / 2.0, 1.0 - alpha / 2.0])
            ),
            "sigma": tuple(
                float(item) for item in np.quantile(sigma_draws, [alpha / 2.0, 1.0 - alpha / 2.0])
            ),
        }
        decomposition = UncertaintyDecomposition.from_gaussian_components(
            metric_id="bart_prediction",
            point_estimate=float(np.mean(predictions)),
            confidence_level=credible_mass,
            epistemic_std=float(np.std(predictive_mean_draws, ddof=1)) if predictive_mean_draws.shape[0] > 1 else 0.0,
            aleatoric_std=float(np.mean(sigma_draws)) if sigma_draws.size else 0.0,
            metadata={"method_name": "bayesian_bart_regression", "runtime_backend_used": "pymc_bart"},
        )
        prediction_output = _build_prediction_result(
            method_name="bayesian_bart_regression",
            predictions=predictions,
            target=y,
            coefficients={},
            model_info={"library": "pymc_bart", "estimator": "BART"},
            metadata={
                "num_trees": num_trees,
                "num_samples": num_samples,
                "num_chains": num_chains,
                "runtime_backend_used": "pymc_bart",
            },
        )
        posterior = PosteriorResult(
            method_name="bayesian_bart_regression",
            posterior_means=posterior_means,
            posterior_stds=posterior_stds,
            credible_intervals=credible_intervals,
            diagnostics={
                "credible_mass": float(credible_mass),
                "num_warmup": float(num_warmup),
                "num_samples": float(num_samples),
                "num_chains": float(num_chains),
                "num_trees": float(num_trees),
            },
            metadata={
                "feature_names": _feature_names(data),
                "uncertainty_decomposition": decomposition.as_dict(),
                "runtime_backend_used": "pymc_bart",
            },
        )
        return {
            "result": posterior,
            "prediction_result": prediction_output["result"],
            "uncertainty_envelope": posterior.to_uncertainty_envelope(
                param_name="posterior_predictive_mean"
            ),
        }


__all__ = [
    "AffineNormalizingFlowPosteriorAdapter",
    "BayesianBARTRegressorEstimator",
    "ExpectationPropagationGaussianEstimator",
    "FactorGraphBeliefPropagationEstimator",
    "SimulationBasedNLEEstimator",
    "SimulationBasedNPEEstimator",
    "SimulationBasedNREEstimator",
    "SVGDRegressionEstimator",
]
