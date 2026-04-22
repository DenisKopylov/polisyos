"""Estimate tabular regression models and return prediction/error summaries."""
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

from .protocols import PredictionResult, TabularData


def _tabular_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=TabularData,
        nested_keys=("tabular_data",),
    )


def _prediction_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("prediction", "json"),
                contract_id=PredictionResult.contract_id,
            ),
            SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
        }
    )


def _regression_metrics(target: np.ndarray, predictions: np.ndarray) -> dict[str, float]:
    residual = np.asarray(target, dtype=float) - np.asarray(predictions, dtype=float)
    mse = float(np.mean(residual ** 2))
    denom = float(np.sum((target - np.mean(target)) ** 2))
    r2 = 1.0 - float(np.sum(residual ** 2)) / denom if denom > 1e-12 else 0.0
    return {
        "rmse": float(np.sqrt(mse)),
        "mae": float(np.mean(np.abs(residual))),
        "r_squared": float(r2),
    }


def _feature_names(data: TabularData) -> list[str]:
    if data.feature_names is not None:
        return list(data.feature_names)
    return [f"x{i}" for i in range(data.features.shape[1])]


def _build_prediction_result(
    *,
    method_name: str,
    predictions: np.ndarray,
    target: np.ndarray,
    feature_importances: Mapping[str, float] | None = None,
    coefficients: Mapping[str, float] | None = None,
    model_info: Mapping[str, Any] | None = None,
    embedding_fidelity_certificate: Any | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result = PredictionResult(
        method_name=method_name,
        predictions=np.asarray(predictions, dtype=float),
        target=np.asarray(target, dtype=float),
        feature_importances=dict(feature_importances or {}),
        coefficients=dict(coefficients or {}),
        metrics=_regression_metrics(np.asarray(target, dtype=float), np.asarray(predictions, dtype=float)),
        model_info=dict(model_info or {}),
        embedding_fidelity_certificate=embedding_fidelity_certificate,
        metadata=dict(metadata or {}),
    )
    return {
        "result": result,
        "uncertainty_envelope": result.to_uncertainty_envelope(),
    }


@foundry_method(
    namespace="ml.regression",
    version="1.0.0",
    tags={"ml", "regression", "elastic-net"},
)
class ElasticNetEstimator:
    """Fit sparse linear regression with L1/L2 regularization; avoid strongly nonlinear response surfaces without feature engineering."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("scikit-learn", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="elastic_net",
        namespace="",
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
            ParameterSpec(name="l1_ratio", default=0.5),
            ParameterSpec(name="cv", default=5),
            ParameterSpec(name="random_state", default=0),
            ParameterSpec(name="max_iter", default=3000),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Elastic Net regression with cross-validated regularization.",
        tags=frozenset({"ml", "regression", "elastic-net"}),
        when_to_use="Sparse linear regression; variable selection under multicollinearity; regularized coefficient estimates",
        citations=(
            "Zou, H. & Hastie, T. (2005). Regularization and variable selection via the elastic net. Journal of the Royal Statistical Society B, 67(2), 301-320.",
        ),
        when_not_to_use="Nonlinear relationships; very large feature spaces with complex interactions (use tree methods)",
        output_interpretation="Coefficients with magnitude indicating importance. Alpha and l1_ratio selected by CV. Zero coefficients = excluded variables.",
        typical_min_obs=50,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TabularData:
        payload = _tabular_payload(fallback_state)
        payload.update(bound_inputs)
        return TabularData.model_validate(payload)

    @staticmethod
    def pure_step(state: TabularData, params: Mapping[str, Any]) -> dict[str, Any]:
        from sklearn.linear_model import ElasticNetCV

        data = state if isinstance(state, TabularData) else TabularData.model_validate(state)
        model = ElasticNetCV(
            l1_ratio=float(params.get("l1_ratio", 0.5)),
            cv=max(2, int(params.get("cv", 5))),
            random_state=int(params.get("random_state", 0)),
            max_iter=max(1000, int(params.get("max_iter", 3000))),
        )
        fit_kwargs: dict[str, Any] = {}
        if data.sample_weight is not None:
            fit_kwargs["sample_weight"] = np.asarray(data.sample_weight, dtype=float)
        model.fit(np.asarray(data.features, dtype=float), np.asarray(data.target, dtype=float), **fit_kwargs)
        predictions = model.predict(np.asarray(data.features, dtype=float))
        names = _feature_names(data)
        coefficients = {name: float(value) for name, value in zip(names, model.coef_)}
        coefficients["intercept"] = float(model.intercept_)
        return _build_prediction_result(
            method_name="elastic_net",
            predictions=predictions,
            target=np.asarray(data.target, dtype=float),
            coefficients=coefficients,
            model_info={"library": "scikit-learn", "estimator": "ElasticNetCV"},
            metadata={"alpha": float(model.alpha_), "l1_ratio": float(model.l1_ratio_)},
        )


@foundry_method(
    namespace="ml.regression",
    version="1.0.0",
    tags={"ml", "regression", "random-forest"},
)
class RandomForestEstimator:
    """Fit nonlinear tabular regression with tree ensembles; avoid extrapolation far outside training support."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("scikit-learn", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="random_forest",
        namespace="",
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
            ParameterSpec(name="n_estimators", default=200),
            ParameterSpec(name="max_depth", default=None),
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
        description="Random forest regression baseline with feature importance.",
        tags=frozenset({"ml", "regression", "random-forest"}),
        when_to_use="Nonlinear regression/classification; variable importance; robust to outliers and irrelevant features",
        citations=(
            "Breiman, L. (2001). Random forests. Machine Learning, 45(1), 5-32.",
        ),
        when_not_to_use="Extrapolation beyond training data range; need highly interpretable linear coefficients",
        output_interpretation="Feature importances (Gini/permutation). OOB error as unbiased generalization estimate.",
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
        model = RandomForestRegressor(
            n_estimators=max(50, int(params.get("n_estimators", 200))),
            max_depth=(
                None
                if params.get("max_depth") in {None, "None"}
                else max(1, int(params.get("max_depth")))
            ),
            random_state=int(params.get("random_state", 0)),
        )
        fit_kwargs: dict[str, Any] = {}
        if data.sample_weight is not None:
            fit_kwargs["sample_weight"] = np.asarray(data.sample_weight, dtype=float)
        model.fit(np.asarray(data.features, dtype=float), np.asarray(data.target, dtype=float), **fit_kwargs)
        predictions = model.predict(np.asarray(data.features, dtype=float))
        importances = {
            name: float(value)
            for name, value in zip(_feature_names(data), np.asarray(model.feature_importances_, dtype=float))
        }
        return _build_prediction_result(
            method_name="random_forest",
            predictions=predictions,
            target=np.asarray(data.target, dtype=float),
            feature_importances=importances,
            model_info={"library": "scikit-learn", "estimator": "RandomForestRegressor"},
            metadata={"n_estimators": int(model.n_estimators), "max_depth": model.max_depth},
        )


@foundry_method(
    namespace="ml.regression",
    version="1.0.0",
    tags={"ml", "regression", "gradient-boosting"},
)
class GradientBoostingEstimator:
    """Fit boosted-tree regression for nonlinear tabular structure; avoid tiny noisy datasets that overfit shallow trees."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("scikit-learn", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="gradient_boosting",
        namespace="",
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
            ParameterSpec(name="n_estimators", default=200),
            ParameterSpec(name="learning_rate", default=0.05),
            ParameterSpec(name="max_depth", default=3),
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
        description="Gradient boosting regression baseline for tabular prediction.",
        tags=frozenset({"ml", "regression", "gradient-boosting"}),
        when_to_use="Tabular data; often best single model; handles missing values natively",
        citations=(
            "Friedman, J. (2001). Greedy function approximation: A gradient boosting machine. Annals of Statistics, 29(5), 1189-1232.",
        ),
        when_not_to_use="Small datasets (<100 obs) where overfitting is likely; need fast inference",
        output_interpretation="SHAP values for feature attribution. Partial dependence plots for marginal effects.",
        typical_min_obs=100,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TabularData:
        payload = _tabular_payload(fallback_state)
        payload.update(bound_inputs)
        return TabularData.model_validate(payload)

    @staticmethod
    def pure_step(state: TabularData, params: Mapping[str, Any]) -> dict[str, Any]:
        from sklearn.ensemble import GradientBoostingRegressor

        data = state if isinstance(state, TabularData) else TabularData.model_validate(state)
        model = GradientBoostingRegressor(
            n_estimators=max(50, int(params.get("n_estimators", 200))),
            learning_rate=float(params.get("learning_rate", 0.05)),
            max_depth=max(1, int(params.get("max_depth", 3))),
            random_state=int(params.get("random_state", 0)),
        )
        fit_kwargs: dict[str, Any] = {}
        if data.sample_weight is not None:
            fit_kwargs["sample_weight"] = np.asarray(data.sample_weight, dtype=float)
        model.fit(np.asarray(data.features, dtype=float), np.asarray(data.target, dtype=float), **fit_kwargs)
        predictions = model.predict(np.asarray(data.features, dtype=float))
        importances = {
            name: float(value)
            for name, value in zip(_feature_names(data), np.asarray(model.feature_importances_, dtype=float))
        }
        return _build_prediction_result(
            method_name="gradient_boosting",
            predictions=predictions,
            target=np.asarray(data.target, dtype=float),
            feature_importances=importances,
            model_info={"library": "scikit-learn", "estimator": "GradientBoostingRegressor"},
            metadata={
                "n_estimators": int(model.n_estimators),
                "learning_rate": float(model.learning_rate),
                "max_depth": max(1, int(params.get("max_depth", 3))),
            },
        )


__all__ = [
    "ElasticNetEstimator",
    "GradientBoostingEstimator",
    "RandomForestEstimator",
]
