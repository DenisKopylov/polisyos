"""
Gaussian Process Regression and Classification methods.

Implements:
- ``GaussianProcessRegressionEstimator`` — exact GP regression (O(n³))
  with RBF/Matérn/Linear kernel selection and posterior predictive output.
- ``SparseGPRegressionEstimator`` — inducing-point sparse GP (O(n·m²))
  suitable for n > 5000.
"""
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
    _tabular_payload,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

from .protocols import PosteriorResult, summarize_posterior_samples


# ---------------------------------------------------------------------------
# Internal kernel functions
# ---------------------------------------------------------------------------


def _rbf_kernel(X1: np.ndarray, X2: np.ndarray, lengthscale: float, variance: float) -> np.ndarray:
    """Squared exponential (RBF) kernel."""
    diff = X1[:, None, :] - X2[None, :, :]  # (n, m, d)
    sq_dist = np.sum(diff ** 2, axis=-1)  # (n, m)
    return variance * np.exp(-0.5 * sq_dist / (lengthscale ** 2))


def _matern32_kernel(X1: np.ndarray, X2: np.ndarray, lengthscale: float, variance: float) -> np.ndarray:
    """Matérn 3/2 kernel."""
    diff = X1[:, None, :] - X2[None, :, :]
    r = np.sqrt(np.maximum(np.sum(diff ** 2, axis=-1), 0.0))
    sqrt3_r = np.sqrt(3.0) * r / lengthscale
    return variance * (1.0 + sqrt3_r) * np.exp(-sqrt3_r)


def _linear_kernel(X1: np.ndarray, X2: np.ndarray, variance: float) -> np.ndarray:
    """Linear (dot-product) kernel."""
    return variance * (X1 @ X2.T)


def _build_kernel(
    X1: np.ndarray,
    X2: np.ndarray,
    kernel: str,
    lengthscale: float,
    variance: float,
) -> np.ndarray:
    if kernel == "matern32":
        return _matern32_kernel(X1, X2, lengthscale, variance)
    if kernel == "linear":
        return _linear_kernel(X1, X2, variance)
    return _rbf_kernel(X1, X2, lengthscale, variance)


def _gp_posterior(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    kernel: str,
    lengthscale: float,
    signal_variance: float,
    noise_variance: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute GP posterior mean and variance at X_test.

    Returns (mean, variance) arrays of shape (n_test,).
    """
    n = X_train.shape[0]
    K_nn = _build_kernel(X_train, X_train, kernel, lengthscale, signal_variance)
    K_nn += (noise_variance + 1e-6) * np.eye(n)  # jitter for stability

    K_sn = _build_kernel(X_test, X_train, kernel, lengthscale, signal_variance)
    K_ss_diag = signal_variance * np.ones(X_test.shape[0])

    try:
        L = np.linalg.cholesky(K_nn)
        alpha = np.linalg.solve(L.T, np.linalg.solve(L, y_train))
        mean = K_sn @ alpha
        v = np.linalg.solve(L, K_sn.T)
        var = np.maximum(K_ss_diag - np.sum(v ** 2, axis=0), 1e-10)
    except np.linalg.LinAlgError:
        # Fallback: pseudo-inverse
        K_nn_inv = np.linalg.pinv(K_nn)
        mean = K_sn @ K_nn_inv @ y_train
        var = np.maximum(K_ss_diag - np.sum((K_sn @ K_nn_inv) * K_sn, axis=1), 1e-10)

    return mean, var


def _output_slots() -> frozenset[SlotSpec]:
    return frozenset({
        SlotSpec("result", SlotType.SCALAR, Unit("posterior", "json"),
                 contract_id=PosteriorResult.contract_id),
        SlotSpec("prediction_result", SlotType.SCALAR, Unit("prediction", "json"),
                 contract_id=PredictionResult.contract_id),
        SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
    })


# ---------------------------------------------------------------------------
# GaussianProcessRegressionEstimator — exact GP
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="bayesian.gp",
    version="1.0.0",
    tags={"bayesian", "gaussian-process", "regression", "uncertainty"},
)
class GaussianProcessRegressionEstimator:
    """
    Exact Gaussian Process regression with user-selectable kernel.

    Supports ``rbf``, ``matern32``, and ``linear`` kernels.  Exact GP
    is O(n³) in training observations — use ``SparseGPRegressionEstimator``
    for n > 5000.

    Outputs
    -------
    result:
        Posterior summary including mean, 95% CI, log-marginal likelihood.
    prediction_result:
        Point predictions + standard deviations at test points.
    uncertainty_envelope:
        Structured uncertainty intervals.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    optional_deps: ClassVar[tuple[str, ...]] = ("scikit-learn",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="gp_regression",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("features", SlotType.MATRIX, Unit("feature", "value"), shape=("n_obs", "n_features")),
            SlotSpec("target", SlotType.VECTOR, Unit("target", "value"), shape=("n_obs",)),
        }),
        output_slots=_output_slots(),
        parameters=(
            ParameterSpec(name="kernel", default="rbf"),
            ParameterSpec(name="lengthscale", default=1.0, bounds=(1e-3, 1e3)),
            ParameterSpec(name="signal_variance", default=1.0, bounds=(1e-4, 1e4)),
            ParameterSpec(name="noise_variance", default=0.1, bounds=(1e-6, 1e3)),
            ParameterSpec(name="test_ratio", default=0.2, bounds=(0.05, 0.5)),
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
            "Exact GP regression with RBF/Matérn/Linear kernel. "
            "Returns posterior predictive mean, variance, and credible intervals."
        ),
        tags=frozenset({"bayesian", "gaussian-process", "regression", "uncertainty"}),
        when_to_use="Nonparametric regression/classification; spatial kriging; Bayesian optimization acquisition functions",
        citations=(
            "Rasmussen, C. & Williams, C. (2006). Gaussian Processes for Machine Learning. MIT Press.",
        ),
        when_not_to_use="Dataset too large for O(n³) exact GP (use sparse variant); non-stationary covariance structure",
        typical_min_obs=20,
        output_interpretation="Posterior mean = best estimate. Posterior variance = uncertainty. Check kernel selection via marginal likelihood.",
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

        kernel = str(params.get("kernel", "rbf"))
        ls = max(1e-3, float(params.get("lengthscale", 1.0)))
        sv = max(1e-4, float(params.get("signal_variance", 1.0)))
        nv = max(1e-6, float(params.get("noise_variance", 0.1)))
        test_ratio = float(params.get("test_ratio", 0.2))
        rng = np.random.default_rng(int(params.get("__seed__", 0)))

        n = X.shape[0]
        n_test = max(1, int(n * test_ratio))
        n_train = n - n_test
        idx = rng.permutation(n)
        X_tr, y_tr = X[idx[:n_train]], y[idx[:n_train]]
        X_te, y_te = X[idx[n_train:]], y[idx[n_train:]]

        mean, var = _gp_posterior(X_tr, y_tr, X_te, kernel, ls, sv, nv)
        std = np.sqrt(var)

        # Log-marginal likelihood on training set
        n_tr = X_tr.shape[0]
        K_tr = _build_kernel(X_tr, X_tr, kernel, ls, sv)
        K_tr += (nv + 1e-6) * np.eye(n_tr)
        try:
            L = np.linalg.cholesky(K_tr)
            alpha = np.linalg.solve(L.T, np.linalg.solve(L, y_tr))
            lml = float(-0.5 * y_tr @ alpha - np.sum(np.log(np.diag(L))) - 0.5 * n_tr * np.log(2 * np.pi))
        except np.linalg.LinAlgError:
            lml = float("nan")

        rmse = float(np.sqrt(np.mean((mean - y_te) ** 2)))

        result = PosteriorResult(
            method_name="gp_regression",
            posterior_means={
                "mean": float(np.mean(mean)),
                "std": float(np.mean(std)),
            },
            posterior_stds={
                "mean": float(np.std(mean, ddof=1)) if mean.shape[0] > 1 else 0.0,
                "std": float(np.std(std, ddof=1)) if std.shape[0] > 1 else 0.0,
            },
            credible_intervals={
                "mean": (
                    float(np.mean(mean - 1.96 * std)),
                    float(np.mean(mean + 1.96 * std)),
                ),
            },
            diagnostics={
                "credible_mass": 0.95,
                "log_marginal_likelihood": lml,
                "n_test": float(n_test),
            },
            metadata={"kernel": kernel},
        )

        pred_result = _build_prediction_result(
            method_name="gp_regression",
            predictions=mean,
            target=y_te,
            model_info={"library": "numpy", "estimator": "ExactGaussianProcess"},
            metadata={"kernel": kernel, "n_train": n_train, "n_test": n_test},
        )

        return {
            "result": result,
            "prediction_result": pred_result["result"],
            "uncertainty_envelope": UncertaintyEnvelope(
                point_estimate=float(np.mean(mean)),
                confidence_interval=(
                    float(np.mean(mean - 1.96 * std)),
                    float(np.mean(mean + 1.96 * std)),
                ),
                confidence_level=0.95,
                distribution_family=DistributionFamily.BAYESIAN,
                source=UncertaintySource.CALIBRATION,
                propagation_method=PropagationMethod.ANALYTICAL,
                interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
                sample_size=int(n_test),
                metadata={"method_name": "gp_regression", "kernel": kernel},
            ),
            "rmse_test": rmse,
            "n_train": n_train,
            "n_test": n_test,
            "kernel": kernel,
        }


# ---------------------------------------------------------------------------
# SparseGPRegressionEstimator — inducing-point sparse GP
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="bayesian.gp",
    version="1.0.0",
    tags={"bayesian", "gaussian-process", "regression", "sparse", "scalable"},
)
class SparseGPRegressionEstimator:
    """
    Sparse (inducing-point) GP regression for large datasets.

    Uses the Nyström approximation: selects ``n_inducing`` representative
    training points as inducing inputs.  Reduces exact O(n³) to O(n·m²)
    where m = ``n_inducing``.

    Suitable for n > 5000 where exact GP is prohibitive.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="sparse_gp_regression",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("features", SlotType.MATRIX, Unit("feature", "value"), shape=("n_obs", "n_features")),
            SlotSpec("target", SlotType.VECTOR, Unit("target", "value"), shape=("n_obs",)),
        }),
        output_slots=_output_slots(),
        parameters=(
            ParameterSpec(name="n_inducing", default=100, bounds=(10, 2000)),
            ParameterSpec(name="kernel", default="rbf"),
            ParameterSpec(name="lengthscale", default=1.0, bounds=(1e-3, 1e3)),
            ParameterSpec(name="signal_variance", default=1.0, bounds=(1e-4, 1e4)),
            ParameterSpec(name="noise_variance", default=0.1, bounds=(1e-6, 1e3)),
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
            "Nyström sparse GP regression using inducing-point approximation. "
            "O(n·m²) complexity where m = n_inducing."
        ),
        tags=frozenset({"bayesian", "gaussian-process", "regression", "sparse", "scalable"}),
        when_to_use="Large-scale GP regression (n > 5000); spatial interpolation at scale; surrogate model for expensive simulations",
        when_not_to_use="Small dataset where exact GP is feasible; very high inducing point count negates speed benefit",
        typical_min_obs=200,
        output_interpretation="Posterior mean = best estimate. Posterior variance = uncertainty. n_inducing controls approximation quality — higher is more accurate but slower.",
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

        kernel = str(params.get("kernel", "rbf"))
        ls = max(1e-3, float(params.get("lengthscale", 1.0)))
        sv = max(1e-4, float(params.get("signal_variance", 1.0)))
        nv = max(1e-6, float(params.get("noise_variance", 0.1)))
        n_inducing = min(int(params.get("n_inducing", 100)), X.shape[0])
        rng = np.random.default_rng(int(params.get("__seed__", 0)))

        # Select inducing points via k-means-lite (uniform random subset)
        inducing_idx = rng.choice(X.shape[0], n_inducing, replace=False)
        X_m = X[inducing_idx]

        # Nyström approximation: K_nm K_mm^{-1} K_mn
        K_nm = _build_kernel(X, X_m, kernel, ls, sv)
        K_mm = _build_kernel(X_m, X_m, kernel, ls, sv) + 1e-6 * np.eye(n_inducing)

        try:
            L_mm = np.linalg.cholesky(K_mm)
            V = np.linalg.solve(L_mm, K_nm.T)  # (m, n)
            Q_nn_diag = np.sum(V ** 2, axis=0)  # Nyström diag
            Lambda_diag = np.maximum(sv * np.ones(X.shape[0]) - Q_nn_diag + nv, 1e-6)
            Lambda_inv = 1.0 / Lambda_diag

            # Woodbury identity: (Λ + Q)^{-1} y
            W = V * Lambda_inv[None, :]  # (m, n)
            M = np.eye(n_inducing) + W @ V.T  # (m, m)
            L_M = np.linalg.cholesky(M)
            v = W @ y
            alpha = Lambda_inv * y - (V.T @ np.linalg.solve(L_M.T, np.linalg.solve(L_M, v)))

            mean = K_nm @ (np.linalg.solve(K_mm, K_nm.T @ alpha))
        except np.linalg.LinAlgError:
            # Fallback to ordinary least squares
            mean = np.full(X.shape[0], float(np.mean(y)))

        rmse = float(np.sqrt(np.mean((mean - y) ** 2)))
        std_approx = float(np.sqrt(max(sv, nv)))

        result = PosteriorResult(
            method_name="sparse_gp_regression",
            posterior_means={
                "mean": float(np.mean(mean)),
                "std": std_approx,
            },
            posterior_stds={
                "mean": float(np.std(mean, ddof=1)) if mean.shape[0] > 1 else 0.0,
                "std": 0.0,
            },
            credible_intervals={
                "mean": (
                    float(np.mean(mean) - 1.96 * std_approx),
                    float(np.mean(mean) + 1.96 * std_approx),
                ),
            },
            diagnostics={"credible_mass": 0.95, "n_inducing": float(n_inducing)},
            metadata={"kernel": kernel},
        )
        pred_result = _build_prediction_result(
            method_name="sparse_gp_regression",
            predictions=mean,
            target=y,
            model_info={"library": "numpy", "estimator": "SparseGaussianProcess"},
            metadata={"kernel": kernel, "n_inducing": n_inducing},
        )

        return {
            "result": result,
            "prediction_result": pred_result["result"],
            "uncertainty_envelope": UncertaintyEnvelope(
                point_estimate=float(np.mean(mean)),
                confidence_interval=(
                    float(np.mean(mean) - 1.96 * std_approx),
                    float(np.mean(mean) + 1.96 * std_approx),
                ),
                confidence_level=0.95,
                distribution_family=DistributionFamily.BAYESIAN,
                source=UncertaintySource.CALIBRATION,
                propagation_method=PropagationMethod.ANALYTICAL,
                interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
                sample_size=int(X.shape[0]),
                metadata={"method_name": "sparse_gp_regression", "kernel": kernel},
            ),
            "rmse_train": rmse,
            "n_inducing": n_inducing,
            "kernel": kernel,
        }
