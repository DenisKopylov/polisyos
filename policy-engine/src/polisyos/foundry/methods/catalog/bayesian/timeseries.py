"""Public bayesian timeseries module API."""
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
from polisyos.foundry.methods.catalog._payloads import extract_model_payload
from polisyos.foundry.methods.catalog.econometrics.protocols import TimeSeriesData
from polisyos.foundry.methods.catalog.ml.protocols import PredictionResult
from polisyos.foundry.methods.catalog.ml.regression import _build_prediction_result

from .protocols import PosteriorResult, metropolis_sample, summarize_posterior_samples


def _time_series_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=TimeSeriesData,
        nested_keys=("time_series_data",),
    )


def _output_slots() -> frozenset[SlotSpec]:
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
    namespace="bayesian.timeseries",
    version="1.0.0",
    tags={"bayesian", "sampling", "time-series"},
)
class BayesianAutoregressionEstimator:
    """Bayesian autoregression estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    optional_deps: ClassVar[tuple[str, ...]] = ("arviz",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="autoregression",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("endog", SlotType.VECTOR, Unit("timeseries", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_output_slots(),
        parameters=(
            ParameterSpec(name="n_lags", default=2),
            ParameterSpec(name="prior_scale", default=1.0),
            ParameterSpec(name="num_warmup", default=96),
            ParameterSpec(name="num_samples", default=128),
            ParameterSpec(name="num_chains", default=1),
            ParameterSpec(name="credible_mass", default=0.9),
            ParameterSpec(name="proposal_scale", default=0.04),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Sampling-based Bayesian autoregression for univariate time series.",
        tags=frozenset({"bayesian", "sampling", "time-series"}),
        when_to_use="Macroeconomic forecasting with priors; univariate time series where uncertainty quantification matters",
        citations=(
            "Gelman, A. et al. (2013). Bayesian Data Analysis. 3rd ed. CRC Press.",
            "West, M. & Harrison, J. (1997). Bayesian Forecasting and Dynamic Models. Springer.",
        ),
        when_not_to_use="Very long series where MCMC is too slow; multivariate VAR needed",
        typical_min_obs=80,
        output_interpretation="Posterior predictive forecasts with full uncertainty. AR coefficient credible intervals show persistence uncertainty.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TimeSeriesData:
        payload = _time_series_payload(fallback_state)
        payload.update(bound_inputs)
        return TimeSeriesData.model_validate(payload)

    @staticmethod
    def pure_step(state: TimeSeriesData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, TimeSeriesData) else TimeSeriesData.model_validate(state)
        series = np.asarray(data.endog, dtype=float)
        if series.ndim == 2:
            if series.shape[1] != 1:
                raise ValueError("bayesian autoregression expects univariate endog")
            series = series[:, 0]
        if series.ndim != 1:
            raise ValueError("bayesian autoregression expects a 1D endog vector")

        n_lags = max(1, int(params.get("n_lags", 2)))
        if series.shape[0] <= n_lags + 4:
            raise ValueError("autoregression requires more observations than lags")
        prior_scale = max(1e-3, float(params.get("prior_scale", 1.0)))
        num_warmup = max(32, int(params.get("num_warmup", 96)))
        num_samples = max(32, int(params.get("num_samples", 128)))
        num_chains = max(1, int(params.get("num_chains", 1)))
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)
        proposal_scale = max(1e-4, float(params.get("proposal_scale", 0.04)))

        x = np.column_stack([series[n_lags - lag - 1: -(lag + 1) if lag + 1 > 0 else None] for lag in range(n_lags)])
        y = series[n_lags:]
        design = np.column_stack([np.ones(x.shape[0]), x])
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
            "phi": beta_draws[:, 1:],
            "sigma": np.exp(draws[:, -1]),
        }
        mean_prediction = design @ np.mean(beta_draws, axis=0)

        posterior_means, posterior_stds, credible_intervals = summarize_posterior_samples(
            posterior,
            credible_mass=credible_mass,
        )
        diagnostics = {
            "num_warmup": float(num_warmup),
            "num_samples": float(num_samples),
            "num_chains": float(num_chains),
            "credible_mass": float(credible_mass),
            "n_lags": float(n_lags),
            "acceptance_rate": float(accept_rate),
            "proposal_scale": float(proposal_scale),
        }

        prediction_output = _build_prediction_result(
            method_name="bayesian_autoregression",
            predictions=mean_prediction,
            target=y,
            coefficients={
                "intercept": posterior_means.get("intercept", 0.0),
                **{f"phi_{idx + 1}": posterior_means.get(f"phi_{idx}", 0.0) for idx in range(n_lags)},
            },
            model_info={"library": "numpy", "estimator": "BayesianAutoregressionMCMC"},
            metadata={"n_lags": n_lags, "num_samples": num_samples},
        )
        posterior_result = PosteriorResult(
            method_name="bayesian_autoregression",
            posterior_means=posterior_means,
            posterior_stds=posterior_stds,
            credible_intervals=credible_intervals,
            diagnostics=diagnostics,
            metadata={"n_lags": n_lags},
        )
        return {
            "result": posterior_result,
            "prediction_result": prediction_output["result"],
            "uncertainty_envelope": posterior_result.to_uncertainty_envelope(param_name="phi_1"),
        }


__all__ = ["BayesianAutoregressionEstimator"]
