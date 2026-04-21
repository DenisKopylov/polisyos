"""Estimate conjugate Bayesian regression models with posterior summaries."""
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
from polisyos.foundry.methods.catalog.ml.protocols import PredictionResult, TabularData
from polisyos.foundry.methods.catalog.ml.regression import (
    _build_prediction_result,
    _feature_names,
    _tabular_payload,
)

from .protocols import (
    PosteriorResult,
    augment_sampler_diagnostics,
    metropolis_sample,
    summarize_posterior_samples,
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


@foundry_method(
    namespace="bayesian.regression",
    version="1.0.0",
    tags={"bayesian", "sampling", "regression"},
)
class BayesianLinearRegressionEstimator:
    """Estimate linear-regression posteriors under Gaussian likelihood/priors; avoid strongly nonlinear responses without basis expansion."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    optional_deps: ClassVar[tuple[str, ...]] = ("arviz",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="linear_regression",
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
            ParameterSpec(name="num_warmup", default=96),
            ParameterSpec(name="num_samples", default=128),
            ParameterSpec(name="num_chains", default=1),
            ParameterSpec(name="credible_mass", default=0.9),
            ParameterSpec(name="proposal_scale", default=0.05),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Sampling-based Bayesian linear regression with posterior predictive summaries.",
        tags=frozenset({"bayesian", "sampling", "regression"}),
        declared_truthfulness_tier="asymptotic",
        truthfulness_scope="posterior",
        when_to_use="Regression with prior information; uncertainty quantification; small samples where frequentist CI unreliable",
        citations=(
            "Gelman, A. et al. (2013). Bayesian Data Analysis. 3rd ed. CRC Press.",
        ),
        when_not_to_use="Very large datasets where MCMC is too slow; no interest in full posterior distribution",
        typical_min_obs=20,
        output_interpretation="Posterior distribution over coefficients. Credible interval: 95% probability parameter is in [a,b]. Posterior predictive for new observations.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TabularData:
        payload = _tabular_payload(fallback_state)
        payload.update(bound_inputs)
        return TabularData.model_validate(payload)

    @staticmethod
    def pure_step(state: TabularData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, TabularData) else TabularData.model_validate(state)
        x = np.asarray(data.features, dtype=float)
        y = np.asarray(data.target, dtype=float)
        design = np.column_stack([np.ones(x.shape[0]), x])
        prior_scale = max(1e-3, float(params.get("prior_scale", 1.5)))
        num_warmup = max(32, int(params.get("num_warmup", 96)))
        num_samples = max(32, int(params.get("num_samples", 128)))
        num_chains = max(1, int(params.get("num_chains", 1)))
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)
        proposal_scale = max(1e-4, float(params.get("proposal_scale", 0.05)))
        rng = np.random.default_rng(int(params.get("__seed__", 0)))

        ols_coef = np.linalg.pinv(design) @ y
        resid = y - design @ ols_coef
        sigma0 = max(float(np.std(resid, ddof=max(design.shape[1], 1))), 0.1)
        initial = np.concatenate([np.asarray(ols_coef, dtype=float), np.array([np.log(sigma0)], dtype=float)])

        def log_density(theta: np.ndarray) -> float:
            beta = theta[:-1]
            log_sigma = theta[-1]
            sigma = float(np.exp(log_sigma))
            mean = design @ beta
            residual = y - mean
            log_likelihood = -0.5 * np.sum((residual / sigma) ** 2 + 2.0 * log_sigma + np.log(2.0 * np.pi))
            log_prior_beta = -0.5 * np.sum((beta / prior_scale) ** 2)
            log_prior_scale = -0.5 * (log_sigma / prior_scale) ** 2
            return float(log_likelihood + log_prior_beta + log_prior_scale)

        draws, accept_rate = metropolis_sample(
            log_density=log_density,
            initial_state=initial,
            proposal_scale=np.full(initial.shape, proposal_scale, dtype=float),
            rng=rng,
            num_warmup=num_warmup,
            num_samples=num_samples,
            num_chains=num_chains,
        )
        beta_draws = draws[:, :-1]
        posterior = {
            "intercept": beta_draws[:, 0],
            "coefficients": beta_draws[:, 1:],
            "sigma": np.exp(draws[:, -1]),
        }
        mean_prediction = design @ np.mean(beta_draws, axis=0)

        posterior_means, posterior_stds, credible_intervals = summarize_posterior_samples(
            posterior,
            credible_mass=credible_mass,
        )
        diagnostics = augment_sampler_diagnostics(
            posterior,
            diagnostics={
                "num_warmup": float(num_warmup),
                "num_samples": float(num_samples),
                "num_chains": float(num_chains),
                "credible_mass": float(credible_mass),
                "acceptance_rate": float(accept_rate),
                "proposal_scale": float(proposal_scale),
            },
            num_chains=num_chains,
            num_samples=num_samples,
            credible_mass=credible_mass,
        )

        prediction_output = _build_prediction_result(
            method_name="bayesian_linear_regression",
            predictions=mean_prediction,
            target=y,
            coefficients={
                "intercept": posterior_means.get("intercept", 0.0),
                **{
                    name: posterior_means.get(f"coefficients_{idx}", 0.0)
                    for idx, name in enumerate(_feature_names(data))
                },
            },
            model_info={"library": "numpy", "estimator": "BayesianLinearRegressionMCMC"},
            metadata={
                "num_samples": num_samples,
                "num_warmup": num_warmup,
                "num_chains": num_chains,
            },
        )
        posterior_result = PosteriorResult(
            method_name="bayesian_linear_regression",
            posterior_means=posterior_means,
            posterior_stds=posterior_stds,
            credible_intervals=credible_intervals,
            diagnostics=diagnostics,
            sampler_family="mcmc",
            sampler_kernel="metropolis",
            metadata={"feature_names": _feature_names(data)},
        )
        return {
            "result": posterior_result,
            "prediction_result": prediction_output["result"],
            "uncertainty_envelope": posterior_result.to_uncertainty_envelope(),
        }


__all__ = ["BayesianLinearRegressionEstimator"]
