"""
Variational Inference methods for the Bayesian catalog.

Implements:
- ``MeanFieldVIEstimator``   — Mean-field ADVI for Bayesian linear regression
  (coordinate-ascent VI: CAVI).  Closed-form updates for conjugate priors.
- ``BBVIEstimator``          — Black-Box VI using reparameterisation gradients
  (BBVI / ADVI-style) with Adam optimiser.  Applicable to any differentiable
  log-joint via NumPy auto-diff (finite-difference approx for generality).
"""
from __future__ import annotations

from statistics import NormalDist
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
    _tabular_payload,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

from .protocols import (
    PosteriorResult,
    extract_truthfulness_hints,
    pareto_tail_shape,
    relative_interval_shift_max,
    split_truthfulness_hints,
    weighted_quantile,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _elbo_linear(
    X: np.ndarray,
    y: np.ndarray,
    mu_q: np.ndarray,
    log_sigma_q: np.ndarray,
    prior_scale: float,
) -> float:
    """ELBO for Bayesian linear regression under mean-field Gaussian variational family."""
    sigma_q = np.exp(log_sigma_q)
    n, d = X.shape
    # Likelihood term (approximate with current mean)
    y_pred = X @ mu_q
    ll = -0.5 * float(np.sum((y - y_pred) ** 2)) - 0.5 * float(np.sum(np.diag(X.T @ X) * sigma_q ** 2))
    # KL term: KL[N(mu, sigma^2) || N(0, prior_scale^2)]
    kl = 0.5 * float(np.sum(
        (sigma_q ** 2 + mu_q ** 2) / prior_scale ** 2
        - 1.0
        - 2 * log_sigma_q
        + 2 * np.log(prior_scale)
    ))
    return ll - kl


def _output_slots() -> frozenset[SlotSpec]:
    return frozenset({
        SlotSpec("result", SlotType.SCALAR, Unit("posterior", "json"),
                 contract_id=PosteriorResult.contract_id),
        SlotSpec("prediction_result", SlotType.SCALAR, Unit("prediction", "json"),
                 contract_id=PredictionResult.contract_id),
        SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
    })


def _reference_linear_gaussian_posterior(
    X: np.ndarray,
    y: np.ndarray,
    *,
    prior_scale: float,
    noise_variance: float,
) -> tuple[np.ndarray, np.ndarray]:
    tau2 = max(float(prior_scale) ** 2, 1e-12)
    sigma2 = max(float(noise_variance), 1e-12)
    precision = (X.T @ X) / sigma2 + np.eye(X.shape[1]) / tau2
    try:
        covariance = np.linalg.inv(precision)
    except np.linalg.LinAlgError:
        covariance = np.linalg.pinv(precision)
    mean = covariance @ (X.T @ y) / sigma2
    return mean, np.atleast_2d(covariance)


def _gaussian_intervals(
    *,
    mean: np.ndarray,
    std: np.ndarray,
    credible_mass: float,
) -> dict[str, tuple[float, float]]:
    alpha = max(1e-6, 1.0 - float(credible_mass))
    z_score = NormalDist().inv_cdf(1.0 - alpha / 2.0)
    return {
        f"beta_{idx}": (
            float(mean[idx] - z_score * std[idx]),
            float(mean[idx] + z_score * std[idx]),
        )
        for idx in range(mean.shape[0])
    }


def _diag_gaussian_log_density(
    samples: np.ndarray,
    *,
    mean: np.ndarray,
    std: np.ndarray,
) -> np.ndarray:
    centered = samples - mean[None, :]
    variance = np.maximum(std**2, 1e-12)
    return -0.5 * (
        np.sum((centered**2) / variance[None, :], axis=1)
        + np.sum(np.log(2.0 * np.pi * variance))
    )


def _full_gaussian_log_density(
    samples: np.ndarray,
    *,
    mean: np.ndarray,
    covariance: np.ndarray,
) -> np.ndarray:
    centered = samples - mean[None, :]
    safe_cov = np.atleast_2d(covariance) + 1e-12 * np.eye(covariance.shape[0])
    sign, logdet = np.linalg.slogdet(safe_cov)
    if sign <= 0:
        safe_cov = safe_cov + 1e-6 * np.eye(safe_cov.shape[0])
        sign, logdet = np.linalg.slogdet(safe_cov)
    precision = np.linalg.pinv(safe_cov)
    quadratic = np.einsum("ni,ij,nj->n", centered, precision, centered)
    return -0.5 * (quadratic + logdet + safe_cov.shape[0] * np.log(2.0 * np.pi))


def _variational_truthfulness_payload(
    *,
    X: np.ndarray,
    y: np.ndarray,
    posterior_mean: np.ndarray,
    posterior_std: np.ndarray,
    credible_mass: float,
    prior_scale: float,
    noise_variance: float,
    seed: int,
    credible_intervals: Mapping[str, tuple[float, float]],
    params: Mapping[str, Any],
) -> tuple[dict[str, float], dict[str, Any]]:
    reference_mean, reference_cov = _reference_linear_gaussian_posterior(
        X,
        y,
        prior_scale=prior_scale,
        noise_variance=noise_variance,
    )
    reference_std = np.sqrt(np.maximum(np.diag(reference_cov), 1e-12))
    reference_intervals = _gaussian_intervals(
        mean=reference_mean,
        std=reference_std,
        credible_mass=credible_mass,
    )
    rng = np.random.default_rng(seed)
    importance_sample_size = max(512, 64 * X.shape[1])
    q_samples = rng.normal(
        loc=posterior_mean[None, :],
        scale=np.maximum(posterior_std[None, :], 1e-9),
        size=(importance_sample_size, X.shape[1]),
    )
    log_q = _diag_gaussian_log_density(
        q_samples,
        mean=posterior_mean,
        std=np.maximum(posterior_std, 1e-9),
    )
    log_p = _full_gaussian_log_density(
        q_samples,
        mean=reference_mean,
        covariance=reference_cov,
    )
    log_weights = log_p - log_q
    weights = np.exp(log_weights - float(np.max(log_weights)))
    weights = weights / np.maximum(np.sum(weights), 1e-12)
    alpha = max(1e-6, 1.0 - float(credible_mass))
    corrected_intervals = {
        f"beta_{idx}": tuple(
            float(value) for value in weighted_quantile(
                q_samples[:, idx],
                [alpha / 2.0, 1.0 - alpha / 2.0],
                sample_weight=weights,
            )
        )
        for idx in range(X.shape[1])
    }
    coverage_gaps: list[float] = []
    tail_gaps: list[float] = []
    nd = NormalDist()
    for idx in range(X.shape[1]):
        label = f"beta_{idx}"
        lower, upper = credible_intervals[label]
        mean_ref = float(reference_mean[idx])
        std_ref = max(float(reference_std[idx]), 1e-12)
        lower_tail = nd.cdf((float(lower) - mean_ref) / std_ref)
        upper_tail = 1.0 - nd.cdf((float(upper) - mean_ref) / std_ref)
        coverage = 1.0 - lower_tail - upper_tail
        coverage_gaps.append(abs(coverage - float(credible_mass)))
        tail_gaps.append(max(abs(lower_tail - alpha / 2.0), abs(upper_tail - alpha / 2.0)))
    diagonal_cov = np.diag(np.maximum(posterior_std**2, 1e-12))
    precision_ref = np.linalg.pinv(reference_cov + 1e-12 * np.eye(reference_cov.shape[0]))
    sign_ref, logdet_ref = np.linalg.slogdet(reference_cov + 1e-12 * np.eye(reference_cov.shape[0]))
    sign_q, logdet_q = np.linalg.slogdet(diagonal_cov)
    diff = reference_mean - posterior_mean
    kl_q_to_ref = 0.5 * float(
        np.trace(precision_ref @ diagonal_cov)
        + diff.T @ precision_ref @ diff
        - X.shape[1]
        + logdet_ref
        - logdet_q
    ) if sign_ref > 0 and sign_q > 0 else float("inf")
    corr = reference_cov / np.sqrt(
        np.maximum(np.diag(reference_cov), 1e-12)[:, None]
        * np.maximum(np.diag(reference_cov), 1e-12)[None, :]
    )
    offdiag_mask = ~np.eye(corr.shape[0], dtype=bool)
    base_diagnostics = {
        "importance_sample_size": float(importance_sample_size),
        "joint_psis_pareto_k": pareto_tail_shape(log_weights),
        "posthoc_interval_shift_max": relative_interval_shift_max(
            dict(credible_intervals),
            corrected_intervals,
        ),
        "psis_interval_shift_max": relative_interval_shift_max(
            dict(credible_intervals),
            corrected_intervals,
        ),
        "reference_interval_shift_max": relative_interval_shift_max(
            dict(credible_intervals),
            reference_intervals,
        ),
        "reference_mean_shift_max": float(
            np.max(np.abs(posterior_mean - reference_mean) / np.maximum(reference_std, 1e-12))
        ),
        "reference_correlation_max": float(np.max(np.abs(corr[offdiag_mask]))) if np.any(offdiag_mask) else 0.0,
        "joint_kl_q_to_reference": kl_q_to_ref,
        "offline_coverage_error_max": float(max(coverage_gaps)) if coverage_gaps else 0.0,
        "offline_tail_coverage_error_max": float(max(tail_gaps)) if tail_gaps else 0.0,
    }
    base_metadata = {
        "benchmark_regime": "linear_gaussian_conjugate",
        "coverage_tolerance": 0.05,
        "reference_noise_variance": float(noise_variance),
    }
    hints = extract_truthfulness_hints(params)
    hint_diagnostics, hint_metadata = split_truthfulness_hints(hints)
    base_diagnostics.update(hint_diagnostics)
    base_metadata.update(hint_metadata)
    return base_diagnostics, base_metadata


# ---------------------------------------------------------------------------
# MeanFieldVIEstimator — CAVI for Bayesian linear regression
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="bayesian.variational",
    version="1.0.0",
    tags={"bayesian", "variational-inference", "mean-field", "regression"},
)
class MeanFieldVIEstimator:
    """
    Mean-field Variational Inference (CAVI) for Bayesian linear regression.

    Uses closed-form Coordinate Ascent VI updates under conjugate
    Normal–Normal–InvGamma model:

    y   ~ N(X β, σ² I)
    β   ~ N(0, τ² I)    — prior

    Variational family: q(β) = ∏ N(μ_j, σ²_j)

    Converges in O(n_features × n_iter) time.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="mean_field_vi",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("features", SlotType.MATRIX, Unit("feature", "value"), shape=("n_obs", "n_features")),
            SlotSpec("target", SlotType.VECTOR, Unit("target", "value"), shape=("n_obs",)),
        }),
        output_slots=_output_slots(),
        parameters=(
            ParameterSpec(name="prior_scale", default=1.0, bounds=(1e-3, 100.0)),
            ParameterSpec(name="noise_variance", default=1.0, bounds=(1e-6, 1e6)),
            ParameterSpec(name="max_iter", default=100, bounds=(10, 2000)),
            ParameterSpec(name="tol", default=1e-5, bounds=(1e-10, 1e-1)),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Coordinate Ascent VI (CAVI) for Bayesian linear regression. "
            "Closed-form mean-field updates under conjugate Normal-Normal prior. "
            "Faster than MCMC; approximate posterior."
        ),
        tags=frozenset({"bayesian", "variational-inference", "mean-field", "regression"}),
        truthfulness_scope="posterior",
        when_to_use="Approximate Bayesian inference in large models where MCMC is too slow; scalable inference",
        citations=(
            "Blei, D., Kucukelbir, A. & McAuliffe, J. (2017). Variational inference: A review for statisticians. Journal of the American Statistical Association, 112(518), 859-877.",
        ),
        when_not_to_use="Posterior is highly multimodal; mean-field assumption is too restrictive for the application",
        typical_min_obs=500,
        output_interpretation="ELBO (Evidence Lower BOund) as convergence diagnostic. Variational posterior approximates true posterior. Check against MCMC on small sample.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TabularData:
        payload = _tabular_payload(fallback_state)
        payload.update(bound_inputs)
        return TabularData.model_validate(payload)

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, TabularData) else TabularData.model_validate(state)
        X = np.asarray(data.features, dtype=float)
        y = np.asarray(data.target, dtype=float)
        n, d = X.shape

        tau2 = float(params.get("prior_scale", 1.0)) ** 2
        sigma2 = float(params.get("noise_variance", 1.0))
        max_iter = int(params.get("max_iter", 100))
        tol = float(params.get("tol", 1e-5))

        # CAVI closed-form updates for Normal-Normal conjugate model:
        # q(beta) = N(mu_q, Sigma_q)
        # Sigma_q = (X'X/sigma2 + I/tau2)^{-1}
        # mu_q = Sigma_q @ X' y / sigma2
        XtX = X.T @ X
        Xty = X.T @ y
        precision_posterior = XtX / sigma2 + np.eye(d) / tau2

        elbos: list[float] = []
        mu_q = np.zeros(d)
        log_sigma_q = np.zeros(d)

        for _ in range(max_iter):
            old_mu = mu_q.copy()
            try:
                Sigma_q = np.linalg.inv(precision_posterior)
            except np.linalg.LinAlgError:
                Sigma_q = np.linalg.pinv(precision_posterior)
            mu_q = Sigma_q @ Xty / sigma2
            log_sigma_q = 0.5 * np.log(np.maximum(np.diag(Sigma_q), 1e-15))
            elbo = _elbo_linear(X, y, mu_q, log_sigma_q, float(params.get("prior_scale", 1.0)))
            elbos.append(elbo)
            if np.max(np.abs(mu_q - old_mu)) < tol:
                break

        sigma_q = np.exp(log_sigma_q)
        y_pred = X @ mu_q
        credible_intervals = _gaussian_intervals(
            mean=mu_q,
            std=sigma_q,
            credible_mass=0.95,
        )
        truthfulness_diagnostics, truthfulness_metadata = _variational_truthfulness_payload(
            X=X,
            y=y,
            posterior_mean=mu_q,
            posterior_std=sigma_q,
            credible_mass=0.95,
            prior_scale=float(params.get("prior_scale", 1.0)),
            noise_variance=sigma2,
            seed=int(params.get("__seed__", 0)),
            credible_intervals=credible_intervals,
            params=params,
        )

        result = PosteriorResult(
            method_name="mean_field_vi",
            diagnostics={
                "credible_mass": 0.95,
                "final_elbo": float(elbos[-1]) if elbos else float("nan"),
                "n_iter": float(len(elbos)),
                "converged": float(
                    len(elbos) <= 1
                    or abs(elbos[-1] - elbos[-2]) < 100 * tol
                ),
                **truthfulness_diagnostics,
            },
            posterior_means={f"beta_{i}": float(mu_q[i]) for i in range(d)},
            posterior_stds={f"beta_{i}": float(sigma_q[i]) for i in range(d)},
            credible_intervals=credible_intervals,
            metadata={
                "noise_variance": sigma2,
                **truthfulness_metadata,
            },
        )

        pred_result = _build_prediction_result(
            method_name="mean_field_vi",
            predictions=y_pred,
            target=y,
            coefficients={
                name: float(mu_q[idx])
                for idx, name in enumerate(
                    list(getattr(data, "feature_names", None) or [f"x{idx}" for idx in range(d)])
                )
            },
            model_info={"library": "numpy", "estimator": "MeanFieldVI"},
            metadata={"final_elbo": float(elbos[-1]) if elbos else float("nan")},
        )

        beta0_interval = result.credible_intervals.get("beta_0")
        return {
            "result": result,
            "prediction_result": pred_result["result"],
            "uncertainty_envelope": (
                None
                if beta0_interval is None
                else UncertaintyEnvelope(
                    point_estimate=float(result.posterior_means["beta_0"]),
                    confidence_interval=beta0_interval,
                    confidence_level=0.95,
                    distribution_family=DistributionFamily.BAYESIAN,
                    source=UncertaintySource.CALIBRATION,
                    propagation_method=PropagationMethod.ANALYTICAL,
                    interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
                    sample_size=int(X.shape[0]),
                    metadata={"method_name": "mean_field_vi", "parameter": "beta_0"},
                )
            ),
            "posterior_mean": mu_q.tolist(),
            "posterior_std": sigma_q.tolist(),
            "elbo_history": elbos,
        }


# ---------------------------------------------------------------------------
# BBVIEstimator — Black-Box VI with reparameterisation gradients
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="bayesian.variational",
    version="1.0.0",
    tags={"bayesian", "variational-inference", "black-box", "advi", "gradient"},
)
class BBVIEstimator:
    """
    Black-Box Variational Inference (BBVI) with reparameterisation trick.

    Optimises the ELBO using Adam with reparameterised Monte Carlo gradient
    estimates.  Finite-difference approximation of the log-joint gradient
    enables use with any (smooth) model without symbolic differentiation.

    Suitable when CAVI closed-form updates are unavailable (non-conjugate
    priors or non-linear models).
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="bbvi",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("features", SlotType.MATRIX, Unit("feature", "value"), shape=("n_obs", "n_features")),
            SlotSpec("target", SlotType.VECTOR, Unit("target", "value"), shape=("n_obs",)),
        }),
        output_slots=_output_slots(),
        parameters=(
            ParameterSpec(name="prior_scale", default=1.0, bounds=(1e-3, 100.0)),
            ParameterSpec(name="n_samples", default=32, bounds=(4, 512)),
            ParameterSpec(name="n_iter", default=200, bounds=(10, 5000)),
            ParameterSpec(name="lr", default=0.01, bounds=(1e-5, 1.0)),
            ParameterSpec(name="grad_eps", default=1e-4, bounds=(1e-6, 0.1)),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Black-Box VI with reparameterisation gradients and Adam optimiser. "
            "Approximates posterior for any log-joint model; uses finite-difference "
            "gradients so no symbolic differentiation is required."
        ),
        tags=frozenset({"bayesian", "variational-inference", "black-box", "advi", "gradient"}),
        truthfulness_scope="posterior",
        when_to_use="Approximate Bayesian inference in large models where MCMC is too slow; non-conjugate priors; scalable inference",
        when_not_to_use="Posterior is highly multimodal; mean-field assumption is too restrictive for the application",
        typical_min_obs=500,
        output_interpretation="ELBO (Evidence Lower BOund) as convergence diagnostic. Variational posterior approximates true posterior. Check against MCMC on small sample.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TabularData:
        payload = _tabular_payload(fallback_state)
        payload.update(bound_inputs)
        return TabularData.model_validate(payload)

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, TabularData) else TabularData.model_validate(state)
        X = np.asarray(data.features, dtype=float)
        y = np.asarray(data.target, dtype=float)
        n, d = X.shape

        tau = float(params.get("prior_scale", 1.0))
        n_samples = int(params.get("n_samples", 32))
        n_iter = int(params.get("n_iter", 200))
        lr = float(params.get("lr", 0.01))
        grad_eps = float(params.get("grad_eps", 1e-4))
        rng = np.random.default_rng(int(params.get("__seed__", 0)))

        # Variational parameters: mu (d,) and log_sigma (d,)
        mu = np.zeros(d)
        log_sigma = np.zeros(d)

        # Adam state
        m_mu = np.zeros(d)
        v_mu = np.zeros(d)
        m_ls = np.zeros(d)
        v_ls = np.zeros(d)
        beta1, beta2, adam_eps = 0.9, 0.999, 1e-8

        def log_joint(beta: np.ndarray) -> float:
            """Log p(y|X,beta) + log p(beta)."""
            ll = -0.5 * float(np.sum((y - X @ beta) ** 2))
            lp = -0.5 * float(np.sum(beta ** 2)) / tau ** 2
            return ll + lp

        elbos: list[float] = []

        for step in range(1, n_iter + 1):
            sigma = np.exp(log_sigma)
            # Reparameterised samples
            eps = rng.standard_normal((n_samples, d))
            betas = mu + sigma * eps  # (S, d)

            # ELBO estimate: E[log p(y,β)] + entropy
            ll_samples = np.array([log_joint(betas[s]) for s in range(n_samples)])
            elbo = float(np.mean(ll_samples)) + float(np.sum(log_sigma)) + 0.5 * d

            # Gradient of ELBO w.r.t. mu via finite differences
            g_mu = np.zeros(d)
            g_ls = np.zeros(d)
            for j in range(d):
                mu_p = mu.copy()
                mu_p[j] += grad_eps
                mu_m = mu.copy()
                mu_m[j] -= grad_eps
                lj_p = float(np.mean([log_joint(mu_p + sigma * eps[s]) for s in range(n_samples)]))
                lj_m = float(np.mean([log_joint(mu_m + sigma * eps[s]) for s in range(n_samples)]))
                g_mu[j] = (lj_p - lj_m) / (2 * grad_eps)

                # Gradient w.r.t. log_sigma_j
                ls_p = log_sigma.copy()
                ls_p[j] += grad_eps
                ls_m = log_sigma.copy()
                ls_m[j] -= grad_eps
                sig_p = np.exp(ls_p)
                sig_m = np.exp(ls_m)
                lj_sp = float(np.mean([log_joint(mu + sig_p * eps[s]) for s in range(n_samples)]))
                lj_sm = float(np.mean([log_joint(mu + sig_m * eps[s]) for s in range(n_samples)]))
                g_ls[j] = (lj_sp - lj_sm) / (2 * grad_eps) + 1.0  # + entropy gradient

            # Adam update
            m_mu = beta1 * m_mu + (1 - beta1) * g_mu
            v_mu = beta2 * v_mu + (1 - beta2) * g_mu ** 2
            m_ls = beta1 * m_ls + (1 - beta1) * g_ls
            v_ls = beta2 * v_ls + (1 - beta2) * g_ls ** 2
            m_mu_hat = m_mu / (1 - beta1 ** step)
            v_mu_hat = v_mu / (1 - beta2 ** step)
            m_ls_hat = m_ls / (1 - beta1 ** step)
            v_ls_hat = v_ls / (1 - beta2 ** step)
            mu = mu + lr * m_mu_hat / (np.sqrt(v_mu_hat) + adam_eps)
            log_sigma = log_sigma + lr * m_ls_hat / (np.sqrt(v_ls_hat) + adam_eps)
            elbos.append(elbo)

        sigma_final = np.exp(log_sigma)
        y_pred = X @ mu
        credible_intervals = _gaussian_intervals(
            mean=mu,
            std=sigma_final,
            credible_mass=0.95,
        )
        truthfulness_diagnostics, truthfulness_metadata = _variational_truthfulness_payload(
            X=X,
            y=y,
            posterior_mean=mu,
            posterior_std=sigma_final,
            credible_mass=0.95,
            prior_scale=tau,
            noise_variance=1.0,
            seed=int(params.get("__seed__", 0)),
            credible_intervals=credible_intervals,
            params=params,
        )

        result = PosteriorResult(
            method_name="bbvi",
            diagnostics={
                "credible_mass": 0.95,
                "final_elbo": float(elbos[-1]) if elbos else float("nan"),
                "n_iter": float(n_iter),
                "num_samples": float(n_samples),
                **truthfulness_diagnostics,
            },
            posterior_means={f"beta_{i}": float(mu[i]) for i in range(d)},
            posterior_stds={f"beta_{i}": float(sigma_final[i]) for i in range(d)},
            credible_intervals=credible_intervals,
            metadata=truthfulness_metadata,
        )

        pred_result = _build_prediction_result(
            method_name="bbvi",
            predictions=y_pred,
            target=y,
            coefficients={
                name: float(mu[idx])
                for idx, name in enumerate(
                    list(getattr(data, "feature_names", None) or [f"x{idx}" for idx in range(d)])
                )
            },
            model_info={"library": "numpy", "estimator": "BlackBoxVI"},
            metadata={"final_elbo": float(elbos[-1]) if elbos else float("nan")},
        )

        beta0_interval = result.credible_intervals.get("beta_0")
        return {
            "result": result,
            "prediction_result": pred_result["result"],
            "uncertainty_envelope": (
                None
                if beta0_interval is None
                else UncertaintyEnvelope(
                    point_estimate=float(result.posterior_means["beta_0"]),
                    confidence_interval=beta0_interval,
                    confidence_level=0.95,
                    distribution_family=DistributionFamily.BAYESIAN,
                    source=UncertaintySource.CALIBRATION,
                    propagation_method=PropagationMethod.ANALYTICAL,
                    interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
                    sample_size=int(X.shape[0]),
                    metadata={"method_name": "bbvi", "parameter": "beta_0"},
                )
            ),
            "posterior_mean": mu.tolist(),
            "posterior_std": sigma_final.tolist(),
            "elbo_history": elbos,
        }
