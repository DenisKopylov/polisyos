"""Estimate nonparametric regression, quantile intervals, and learned dynamics models."""
from __future__ import annotations

from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.core.observability.truthfulness import (
    TruthfulnessReceipt,
    TruthfulnessScope,
    TruthfulnessTier,
)
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

from .protocols import PredictionIntervalResult, PredictionResult, TabularData
from .regression import (
    _build_prediction_result,
    _feature_names,
    _prediction_output_slots,
    _tabular_payload,
)


def _time_series_payload(state: Any) -> dict[str, Any]:
    if isinstance(state, Mapping):
        nested = state.get("time_series_data")
        if isinstance(nested, Mapping):
            payload = dict(nested)
            payload.update({k: v for k, v in state.items() if k not in {"time_series_data"}})
            return payload
        return dict(state)
    raise TypeError("state must be a mapping")


@foundry_method(
    namespace="ml.regression",
    version="1.0.0",
    tags={"ml", "regression", "gaussian-process"},
)
class GaussianProcessEstimator:
    """Fit smooth tabular regression with posterior uncertainty; avoid large `n_obs` or very high-dimensional inputs."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("scikit-learn", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="gaussian_process",
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
            ParameterSpec(name="length_scale", default=1.0),
            ParameterSpec(name="noise_level", default=0.05),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Gaussian process regression for smooth non-parametric tabular prediction.",
        tags=frozenset({"ml", "regression", "gaussian-process"}),
        when_to_use="Small datasets requiring uncertainty quantification; smooth functions; Bayesian non-parametric regression",
        citations=(
            "Rasmussen, C. & Williams, C. (2006). Gaussian Processes for Machine Learning. MIT Press.",
        ),
        when_not_to_use="Large datasets (>10k obs) due to O(n³) cost; high-dimensional input spaces",
        output_interpretation="Posterior mean = prediction. Posterior std = epistemic uncertainty. Kernel hyperparameters indicate length scale of variation.",
        typical_min_obs=20,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TabularData:
        payload = _tabular_payload(fallback_state)
        payload.update(bound_inputs)
        return TabularData.model_validate(payload)

    @staticmethod
    def pure_step(state: TabularData, params: Mapping[str, Any]) -> dict[str, Any]:
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import RBF, WhiteKernel

        data = state if isinstance(state, TabularData) else TabularData.model_validate(state)
        kernel = RBF(length_scale=float(params.get("length_scale", 1.0))) + WhiteKernel(
            noise_level=float(params.get("noise_level", 0.05))
        )
        model = GaussianProcessRegressor(kernel=kernel, normalize_y=True, random_state=int(params.get("__seed__", 0)))
        model.fit(np.asarray(data.features, dtype=float), np.asarray(data.target, dtype=float))
        predictions, std = model.predict(np.asarray(data.features, dtype=float), return_std=True)
        result = PredictionResult(
            method_name="gaussian_process",
            predictions=np.asarray(predictions, dtype=float),
            target=np.asarray(data.target, dtype=float),
            metrics={
                "rmse": float(np.sqrt(np.mean((predictions - data.target) ** 2))),
                "mae": float(np.mean(np.abs(predictions - data.target))),
                "mean_predictive_std": float(np.mean(std)),
            },
            model_info={"library": "scikit-learn", "estimator": "GaussianProcessRegressor"},
            metadata={"kernel": str(model.kernel_)},
        )
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(),
        }


@foundry_method(
    namespace="ml.regression",
    version="1.0.0",
    tags={"ml", "regression", "quantile-forest"},
)
class QuantileForestEstimator:
    """Estimate conditional prediction intervals from forest quantiles; avoid expecting exact coverage guarantees without conformal calibration."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("scikit-learn", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="quantile_forest",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("features", SlotType.MATRIX, Unit("feature", "value"), shape=("n_obs", "n_features")),
                SlotSpec("target", SlotType.VECTOR, Unit("target", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("prediction", "json"),
                    contract_id=PredictionResult.contract_id,
                ),
                SlotSpec(
                    "prediction_interval",
                    SlotType.SCALAR,
                    Unit("prediction_interval", "json"),
                    contract_id=PredictionIntervalResult.contract_id,
                ),
                SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="n_estimators", default=200),
            ParameterSpec(name="alpha", default=0.1),
            ParameterSpec(name="random_state", default=0),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Random-forest quantile regression via tree-level predictive distribution.",
        tags=frozenset({"ml", "regression", "quantile-forest"}),
        truthfulness_scope="predictive_calibration",
        when_to_use="Tabular data; prediction intervals without distributional assumptions; heteroscedastic outcomes",
        citations=(
            "Meinshausen, N. (2006). Quantile regression forests. JMLR, 7, 983-999.",
        ),
        when_not_to_use="Need exact coverage guarantees (use conformal prediction); very small datasets",
        output_interpretation="Ensemble mean = point prediction. Quantile bounds define prediction interval. Width reflects heteroscedasticity.",
        typical_min_obs=100,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TabularData:
        payload = _tabular_payload(fallback_state)
        payload.update(bound_inputs)
        return TabularData.model_validate(payload)

    @staticmethod
    def pure_step(state: TabularData, params: Mapping[str, Any]) -> dict[str, Any]:
        from sklearn.ensemble import RandomForestRegressor

        data = state if isinstance(state, TabularData) else TabularData.model_validate(state)
        alpha = float(params.get("alpha", 0.1))
        model = RandomForestRegressor(
            n_estimators=max(50, int(params.get("n_estimators", 200))),
            random_state=int(params.get("random_state", 0)),
        )
        model.fit(np.asarray(data.features, dtype=float), np.asarray(data.target, dtype=float))
        tree_predictions = np.asarray(
            [tree.predict(np.asarray(data.features, dtype=float)) for tree in model.estimators_],
            dtype=float,
        )
        mean_pred = np.mean(tree_predictions, axis=0)
        lower = np.quantile(tree_predictions, alpha / 2.0, axis=0)
        upper = np.quantile(tree_predictions, 1.0 - alpha / 2.0, axis=0)
        base = _build_prediction_result(
            method_name="quantile_forest",
            predictions=mean_pred,
            target=np.asarray(data.target, dtype=float),
            feature_importances={
                name: float(value)
                for name, value in zip(_feature_names(data), np.asarray(model.feature_importances_, dtype=float))
            },
            model_info={"library": "scikit-learn", "estimator": "RandomForestRegressor"},
            metadata={"n_estimators": int(model.n_estimators)},
        )
        return {
            "result": base["result"],
            "prediction_interval": PredictionIntervalResult(
                method_name="quantile_forest",
                predictions=mean_pred,
                lower=lower,
                upper=upper,
                coverage=float(
                    np.mean(
                        (np.asarray(data.target, dtype=float) >= lower)
                        & (np.asarray(data.target, dtype=float) <= upper)
                    )
                ),
                alpha=alpha,
                truthfulness_receipt=TruthfulnessReceipt(
                    runtime_truthfulness_tier=TruthfulnessTier.UNVERIFIED,
                    truthfulness_scope=TruthfulnessScope.PREDICTIVE_CALIBRATION,
                    diagnostics={
                        "observed_coverage": float(
                            np.mean(
                                (np.asarray(data.target, dtype=float) >= lower)
                                & (np.asarray(data.target, dtype=float) <= upper)
                            )
                        ),
                        "alpha": alpha,
                        "interval_constructor": "forest_quantiles",
                    },
                    degradation_reasons=(
                        "interval_not_conformally_calibrated",
                    ),
                ),
                metadata={"base_method": "quantile_forest"},
            ),
            "uncertainty_envelope": base["uncertainty_envelope"],
        }


@foundry_method(
    namespace="ml.dynamics",
    version="1.0.0",
    tags={"ml", "dynamics", "neural-ode"},
)
class NeuralODEEstimator:
    """Learn continuous-time trajectories from observed series; avoid purely discrete dynamics or very short time histories."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("scikit-learn", "scipy", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="neural_ode",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("endog", SlotType.VECTOR, Unit("timeseries", "value"), shape=("n_obs",)),
                SlotSpec("time_index", SlotType.VECTOR, Unit("time", "index"), shape=("n_obs",)),
            }
        ),
        output_slots=_prediction_output_slots(),
        parameters=(
            ParameterSpec(name="hidden_layer_size", default=16),
            ParameterSpec(name="max_iter", default=500),
            ParameterSpec(name="learning_rate_init", default=1e-3),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Neural-ODE-inspired continuous-time dynamics learned via derivative matching and ODE integration.",
        tags=frozenset({"ml", "dynamics", "neural-ode"}),
        when_to_use="Continuous-time dynamics; irregular time series; systems with known ODE structure",
        citations=(
            "Chen, R. et al. (2018). Neural ordinary differential equations. NeurIPS, 31.",
        ),
        when_not_to_use="Short time series (<6 obs); purely discrete processes; no temporal structure",
        output_interpretation="Fitted trajectory from ODE integration. Training score on derivative approximation. Residuals indicate model-data fit.",
        typical_min_obs=30,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _time_series_payload(fallback_state)
        payload.update(bound_inputs)
        payload["endog"] = np.asarray(payload["endog"], dtype=float)
        if "time_index" in payload and payload["time_index"] is not None:
            payload["time_index"] = np.asarray(payload["time_index"], dtype=float)
        else:
            payload["time_index"] = np.arange(np.asarray(payload["endog"]).shape[0], dtype=float)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from scipy.integrate import solve_ivp
        from sklearn.neural_network import MLPRegressor

        if not isinstance(state, Mapping):
            raise TypeError("neural_ode expects mapping input")
        y = np.asarray(state["endog"], dtype=float)
        if y.ndim != 1:
            raise ValueError("neural_ode currently requires 1D endog")
        t = np.asarray(state.get("time_index", np.arange(y.shape[0], dtype=float)), dtype=float)
        if y.shape[0] < 6:
            raise ValueError("neural_ode requires at least 6 observations")
        dt = np.diff(t)
        dt[dt == 0.0] = 1.0
        dy = np.diff(y) / dt
        features = np.column_stack([y[:-1], t[:-1]])
        model = MLPRegressor(
            hidden_layer_sizes=(max(4, int(params.get("hidden_layer_size", 16))),),
            activation="tanh",
            solver="adam",
            learning_rate_init=float(params.get("learning_rate_init", 1e-3)),
            max_iter=max(100, int(params.get("max_iter", 500))),
            random_state=int(params.get("__seed__", 0)),
        )
        model.fit(features, dy)

        def rhs(time_value: float, state_value: np.ndarray) -> np.ndarray:
            current = float(np.asarray(state_value).reshape(-1)[0])
            pred = model.predict(np.array([[current, time_value]], dtype=float))[0]
            return np.array([float(pred)], dtype=float)

        sol = solve_ivp(
            rhs,
            (float(t[0]), float(t[-1])),
            y0=np.array([float(y[0])], dtype=float),
            t_eval=t,
            method="RK45",
        )
        predictions = np.asarray(sol.y[0], dtype=float)
        return _build_prediction_result(
            method_name="neural_ode",
            predictions=predictions,
            target=y,
            model_info={"library": "scikit-learn+scipy", "estimator": "MLPRegressor+solve_ivp"},
            metadata={
                "training_score": float(model.score(features, dy)),
                "n_iterations": int(getattr(model, "n_iter_", 0)),
            },
        )


__all__ = [
    "GaussianProcessEstimator",
    "NeuralODEEstimator",
    "QuantileForestEstimator",
]
