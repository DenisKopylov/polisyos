"""Public spatial advanced module API."""
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

from .protocols import SpatialData, SpatialResult


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("spatial", "json"),
                contract_id=SpatialResult.contract_id,
            )
        }
    )


def _payload(state: Any) -> dict[str, Any]:
    if isinstance(state, SpatialData):
        return state.model_dump(mode="python")
    if isinstance(state, Mapping):
        nested = state.get("spatial_data")
        if isinstance(nested, SpatialData):
            payload = nested.model_dump(mode="python")
            payload.update({key: value for key, value in state.items() if key != "spatial_data"})
            return payload
        if isinstance(nested, Mapping):
            payload = dict(nested)
            payload.update({key: value for key, value in state.items() if key != "spatial_data"})
            return payload
        return dict(state)
    raise TypeError("spatial advanced methods expect a mapping or SpatialData input")


def _coords(value: Any, label: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"{label} must be a 2D coordinate matrix")
    return arr


def _vector(value: Any, label: str, *, expected: int | None = None) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{label} must be a 1D vector")
    if expected is not None and arr.shape[0] != expected:
        raise ValueError(f"{label} must have length {expected}")
    return arr


def _matrix(value: Any, label: str, *, rows: int | None = None) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"{label} must be a 2D matrix")
    if rows is not None and arr.shape[0] != rows:
        raise ValueError(f"{label} must have {rows} rows")
    return arr


def _distance_matrix(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    diff = left[:, None, :] - right[None, :, :]
    return np.sqrt(np.sum(diff**2, axis=2))


def _row_normalize(weights: np.ndarray) -> np.ndarray:
    normalized = np.asarray(weights, dtype=float)
    row_sums = np.sum(normalized, axis=1, keepdims=True)
    row_sums[row_sums == 0.0] = 1.0
    return normalized / row_sums


def _spatial_weights(payload: Mapping[str, Any], coordinates: np.ndarray) -> np.ndarray:
    if payload.get("weights_matrix") is not None:
        weights = _matrix(payload["weights_matrix"], "weights_matrix", rows=coordinates.shape[0])
        if weights.shape[1] != coordinates.shape[0]:
            raise ValueError("weights_matrix must be square")
        return _row_normalize(weights)
    dist = _distance_matrix(coordinates, coordinates)
    with np.errstate(divide="ignore"):
        weights = 1.0 / np.maximum(dist, 1e-6)
    np.fill_diagonal(weights, 0.0)
    return _row_normalize(weights)


def _rbf_kernel(
    left: np.ndarray,
    right: np.ndarray,
    *,
    length_scale: float,
    signal_variance: float,
) -> np.ndarray:
    sq_dist = np.sum((left[:, None, :] - right[None, :, :]) ** 2, axis=2)
    return float(signal_variance) * np.exp(-0.5 * sq_dist / max(length_scale**2, 1e-9))


@foundry_method(
    namespace="spatial.interpolation",
    version="1.0.0",
    tags={"spatial", "kriging", "gaussian-process"},
)
class GaussianProcessKrigingEstimator:
    """Gaussian process kriging estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "gaussian_process_kriging"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="gaussian_process_kriging",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "coordinates",
                    SlotType.MATRIX,
                    Unit("coordinate", "value"),
                    shape=("n_obs", "n_dims"),
                ),
                SlotSpec("values", SlotType.VECTOR, Unit("value", "value"), shape=("n_obs",)),
                SlotSpec(
                    "prediction_coords",
                    SlotType.MATRIX,
                    Unit("coordinate", "value"),
                    shape=("n_pred", "n_dims"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="length_scale", default=1.0),
            ParameterSpec(name="signal_variance", default=1.0),
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
        description="Gaussian-process kriging over spatial coordinates using an RBF covariance kernel.",
        tags=frozenset({"spatial", "kriging", "gaussian-process"}),
        when_to_use="Interpolate field values at unsampled locations; optimal linear prediction with spatial covariance",
        citations=(
            "Cressie, N. (1993). Statistics for Spatial Data. Wiley.",
            "Rasmussen, C. & Williams, C. (2006). Gaussian Processes for Machine Learning. MIT Press.",
        ),
        when_not_to_use="Very large spatial datasets (>10k points) due to O(n³) cost; non-stationary spatial processes",
        output_interpretation="Kriged surface + prediction variance (kriging SE). Semivariogram fitted to characterize spatial dependence.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _payload(fallback_state)
        payload.update(bound_inputs)
        if payload.get("prediction_coords") is None and payload.get("coordinates") is not None:
            payload["prediction_coords"] = payload["coordinates"]
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _payload(state)
        coordinates = _coords(payload["coordinates"], "coordinates")
        values = _vector(payload["values"], "values", expected=coordinates.shape[0])
        prediction_coords = _coords(payload["prediction_coords"], "prediction_coords")
        if prediction_coords.shape[1] != coordinates.shape[1]:
            raise ValueError("prediction_coords must match coordinates dimensionality")

        length_scale = max(1e-4, float(params.get("length_scale", 1.0)))
        signal_variance = max(1e-6, float(params.get("signal_variance", 1.0)))
        noise_level = max(1e-6, float(params.get("noise_level", 0.05)))
        k_xx = _rbf_kernel(
            coordinates,
            coordinates,
            length_scale=length_scale,
            signal_variance=signal_variance,
        ) + noise_level * np.eye(coordinates.shape[0], dtype=float)
        k_xs = _rbf_kernel(
            coordinates,
            prediction_coords,
            length_scale=length_scale,
            signal_variance=signal_variance,
        )
        k_ss = _rbf_kernel(
            prediction_coords,
            prediction_coords,
            length_scale=length_scale,
            signal_variance=signal_variance,
        )
        alpha = np.linalg.solve(k_xx, values)
        predictions = k_xs.T @ alpha
        projection = np.linalg.solve(k_xx, k_xs)
        predictive_var = np.maximum(np.diag(k_ss - k_xs.T @ projection), 0.0)
        std = np.sqrt(predictive_var)
        in_sample_kernel = _rbf_kernel(
            coordinates,
            coordinates,
            length_scale=length_scale,
            signal_variance=signal_variance,
        )
        fitted = in_sample_kernel @ alpha
        rmse = float(np.sqrt(np.mean((fitted - values) ** 2)))
        return {
            "result": SpatialResult(
                method_name="gaussian_process_kriging",
                statistics={
                    "rmse": rmse,
                    "mean_predictive_std": float(np.mean(std)),
                },
                fitted_values=np.asarray(predictions, dtype=float),
                scores=np.asarray(std, dtype=float),
                metadata={
                    "length_scale": length_scale,
                    "signal_variance": signal_variance,
                    "noise_level": noise_level,
                },
            )
        }


@foundry_method(
    namespace="spatial.interpolation",
    version="1.0.0",
    tags={"spatial", "interpolation", "idw"},
)
class InverseDistanceWeightingEstimator:
    """Inverse distance weighting estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "idw"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="idw",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "coordinates",
                    SlotType.MATRIX,
                    Unit("coordinate", "value"),
                    shape=("n_obs", "n_dims"),
                ),
                SlotSpec("values", SlotType.VECTOR, Unit("value", "value"), shape=("n_obs",)),
                SlotSpec(
                    "prediction_coords",
                    SlotType.MATRIX,
                    Unit("coordinate", "value"),
                    shape=("n_pred", "n_dims"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="power", default=2.0),
            ParameterSpec(name="epsilon", default=1e-6),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Inverse-distance weighting interpolation for spatial prediction baselines and robust fallbacks.",
        tags=frozenset({"spatial", "interpolation", "idw"}),
        when_to_use="Simple spatial interpolation baseline; rapid estimation of field values at unsampled locations",
        when_not_to_use="Need uncertainty estimates (use kriging); highly anisotropic spatial processes",
        output_interpretation="Interpolated values weighted by inverse distance. Decay parameter controls locality. Compare to kriging for accuracy benchmark.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _payload(fallback_state)
        payload.update(bound_inputs)
        if payload.get("prediction_coords") is None and payload.get("coordinates") is not None:
            payload["prediction_coords"] = payload["coordinates"]
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _payload(state)
        coordinates = _coords(payload["coordinates"], "coordinates")
        values = _vector(payload["values"], "values", expected=coordinates.shape[0])
        prediction_coords = _coords(payload["prediction_coords"], "prediction_coords")
        if prediction_coords.shape[1] != coordinates.shape[1]:
            raise ValueError("prediction_coords must match coordinates dimensionality")

        power = max(0.5, float(params.get("power", 2.0)))
        epsilon = max(1e-12, float(params.get("epsilon", 1e-6)))
        distances = _distance_matrix(prediction_coords, coordinates)
        exact_mask = distances <= epsilon
        weights = 1.0 / np.maximum(distances, epsilon) ** power
        weights = weights / np.maximum(np.sum(weights, axis=1, keepdims=True), 1e-12)
        predictions = weights @ values
        if np.any(exact_mask):
            for row_idx in np.where(np.any(exact_mask, axis=1))[0]:
                exact_index = int(np.argmax(exact_mask[row_idx]))
                predictions[row_idx] = values[exact_index]
        neighbor_entropy = -np.sum(weights * np.log(np.maximum(weights, 1e-12)), axis=1)
        return {
            "result": SpatialResult(
                method_name="idw",
                statistics={
                    "mean_neighbor_entropy": float(np.mean(neighbor_entropy)),
                    "power": float(power),
                },
                fitted_values=np.asarray(predictions, dtype=float),
                scores=np.asarray(neighbor_entropy, dtype=float),
                metadata={"epsilon": epsilon},
            )
        }


@foundry_method(
    namespace="spatial.panel",
    version="1.0.0",
    tags={"spatial", "panel", "slx"},
)
class SpatialSLXPanelEstimator:
    """Spatial SLX panel estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "slx"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="slx",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "coordinates",
                    SlotType.MATRIX,
                    Unit("coordinate", "value"),
                    shape=("n_obs", "n_dims"),
                ),
                SlotSpec("values", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec(
                    "features",
                    SlotType.MATRIX,
                    Unit("feature", "value"),
                    shape=("n_obs", "n_features"),
                ),
                SlotSpec("unit_ids", SlotType.VECTOR, Unit("entity", "id"), shape=("n_obs",)),
                SlotSpec("time_ids", SlotType.VECTOR, Unit("time", "index"), shape=("n_obs",)),
                SlotSpec(
                    "weights_matrix",
                    SlotType.MATRIX,
                    Unit("spatial_weight", "value"),
                    shape=("n_obs", "n_obs"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Spatial-lag-of-X panel regression with time fixed effects and spillover coefficients.",
        tags=frozenset({"spatial", "panel", "slx"}),
        when_to_use="Panel regression with spatial spillovers; policy diffusion across jurisdictions; time and unit fixed effects",
        citations=(
            "Halleck Vega, S. & Elhorst, J. (2015). The SLX model. Journal of Regional Science, 55(3), 339-363.",
        ),
        when_not_to_use="No panel structure; spatial weights not available; purely cross-sectional data",
        output_interpretation="ρ (spatial lag): spillover intensity. Direct + indirect (spillover) effects of each regressor.",
        typical_min_obs=50,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        payload = _payload(state)
        coordinates = _coords(payload["coordinates"], "coordinates")
        y = _vector(payload["values"], "values", expected=coordinates.shape[0])
        x = _matrix(payload["features"], "features", rows=coordinates.shape[0])
        time_ids = np.asarray(payload["time_ids"])
        unit_ids = np.asarray(payload["unit_ids"])
        if time_ids.ndim != 1 or unit_ids.ndim != 1:
            raise ValueError("time_ids and unit_ids must be 1D vectors")
        if time_ids.shape[0] != coordinates.shape[0] or unit_ids.shape[0] != coordinates.shape[0]:
            raise ValueError("unit_ids and time_ids must align with coordinates")
        weights = _spatial_weights(payload, coordinates)
        wx = weights @ x
        unique_times = np.unique(time_ids.astype(str))
        time_dummy_columns = []
        for label in unique_times[1:]:
            time_dummy_columns.append((time_ids.astype(str) == label).astype(float))
        design_parts = [np.ones(y.shape[0], dtype=float), x, wx]
        if time_dummy_columns:
            design_parts.append(np.column_stack(time_dummy_columns))
        design = np.column_stack(design_parts)
        coef = np.linalg.pinv(design) @ y
        fitted = design @ coef
        feature_count = x.shape[1]
        direct = coef[1: 1 + feature_count]
        spillover = coef[1 + feature_count: 1 + 2 * feature_count]
        rmse = float(np.sqrt(np.mean((fitted - y) ** 2)))
        direct_norm = float(np.linalg.norm(direct))
        spill_norm = float(np.linalg.norm(spillover))
        names = payload.get("feature_names")
        if not isinstance(names, (list, tuple)) or len(names) != feature_count:
            names = [f"x{idx}" for idx in range(feature_count)]
        return {
            "result": SpatialResult(
                method_name="slx",
                statistics={
                    "rmse": rmse,
                    "direct_effect_norm": direct_norm,
                    "spillover_effect_norm": spill_norm,
                },
                local_coefficients=np.vstack([direct, spillover]),
                fitted_values=np.asarray(fitted, dtype=float),
                metadata={
                    "unit_count": int(np.unique(unit_ids.astype(str)).shape[0]),
                    "time_count": int(unique_times.shape[0]),
                    "coefficients": {
                        name: {
                            "direct": float(direct[idx]),
                            "spillover": float(spillover[idx]),
                        }
                        for idx, name in enumerate(names)
                    },
                },
            )
        }


def _double_demean_vector(values: np.ndarray, unit_labels: np.ndarray, time_labels: np.ndarray) -> np.ndarray:
    unit_mean = np.zeros_like(values, dtype=float)
    time_mean = np.zeros_like(values, dtype=float)
    for label in np.unique(unit_labels):
        mask = unit_labels == label
        unit_mean[mask] = float(np.mean(values[mask]))
    for label in np.unique(time_labels):
        mask = time_labels == label
        time_mean[mask] = float(np.mean(values[mask]))
    grand_mean = float(np.mean(values))
    return values - unit_mean - time_mean + grand_mean


def _double_demean_matrix(matrix: np.ndarray, unit_labels: np.ndarray, time_labels: np.ndarray) -> np.ndarray:
    unit_mean = np.zeros_like(matrix, dtype=float)
    time_mean = np.zeros_like(matrix, dtype=float)
    for label in np.unique(unit_labels):
        mask = unit_labels == label
        unit_mean[mask] = np.mean(matrix[mask], axis=0)
    for label in np.unique(time_labels):
        mask = time_labels == label
        time_mean[mask] = np.mean(matrix[mask], axis=0)
    grand_mean = np.mean(matrix, axis=0, keepdims=True)
    return matrix - unit_mean - time_mean + grand_mean


def _panel_spatial_lag(
    values: np.ndarray,
    *,
    coordinates: np.ndarray,
    unit_ids: np.ndarray,
    time_ids: np.ndarray,
    payload: Mapping[str, Any],
) -> np.ndarray:
    lag = np.zeros_like(values, dtype=float)
    for label in np.unique(time_ids.astype(str)):
        mask = time_ids.astype(str) == label
        weights = _spatial_weights(
            {
                **dict(payload),
                "weights_matrix": None,
            },
            coordinates[mask],
        )
        lag[mask] = weights @ values[mask]
    return lag


@foundry_method(
    namespace="spatial.panel",
    version="1.0.0",
    tags={"spatial", "panel", "sarar"},
)
class SpatialSARARPanelEstimator:
    """Spatial SARAR panel estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "sarar"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="sarar",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "coordinates",
                    SlotType.MATRIX,
                    Unit("coordinate", "value"),
                    shape=("n_obs", "n_dims"),
                ),
                SlotSpec("values", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec(
                    "features",
                    SlotType.MATRIX,
                    Unit("feature", "value"),
                    shape=("n_obs", "n_features"),
                ),
                SlotSpec("unit_ids", SlotType.VECTOR, Unit("entity", "id"), shape=("n_obs",)),
                SlotSpec("time_ids", SlotType.VECTOR, Unit("time", "index"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="max_iter", default=6),
            ParameterSpec(name="ridge", default=1e-6),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Approximate SARAR panel regression with unit and time demeaning plus iterative lag/error updates.",
        tags=frozenset({"spatial", "panel", "sarar"}),
        when_to_use="Regression with both spatial lag and spatial error; panel data with correlated disturbances across units",
        citations=(
            "Anselin, L. (1988). Spatial Econometrics: Methods and Models. Kluwer Academic Publishers.",
            "LeSage, J. & Pace, R. (2009). Introduction to Spatial Econometrics. CRC Press.",
        ),
        when_not_to_use="No spatial structure; purely temporal panel; spatial weights matrix is dense",
        output_interpretation="Spatial autoregressive parameters (ρ for lag, λ for error). Coefficients on covariates are direct effects. RMSE on demeaned data.",
        typical_min_obs=50,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _payload(state)
        coordinates = _coords(payload["coordinates"], "coordinates")
        y = _vector(payload["values"], "values", expected=coordinates.shape[0])
        x = _matrix(payload["features"], "features", rows=coordinates.shape[0])
        unit_ids = np.asarray(payload["unit_ids"]).astype(str)
        time_ids = np.asarray(payload["time_ids"]).astype(str)
        if unit_ids.ndim != 1 or time_ids.ndim != 1:
            raise ValueError("unit_ids and time_ids must be 1D vectors")
        if unit_ids.shape[0] != y.shape[0] or time_ids.shape[0] != y.shape[0]:
            raise ValueError("unit_ids and time_ids must align with observations")

        max_iter = max(3, int(params.get("max_iter", 6)))
        ridge = max(0.0, float(params.get("ridge", 1e-6)))
        y_dm = _double_demean_vector(y, unit_ids, time_ids)
        x_dm = _double_demean_matrix(x, unit_ids, time_ids)
        wy = _panel_spatial_lag(
            y_dm,
            coordinates=coordinates,
            unit_ids=unit_ids,
            time_ids=time_ids,
            payload=payload,
        )
        rho = 0.0
        lambda_ = 0.0
        beta = np.zeros(x.shape[1], dtype=float)
        for _ in range(max_iter):
            design = np.column_stack([x_dm, wy])
            gram = design.T @ design + ridge * np.eye(design.shape[1], dtype=float)
            coef = np.linalg.solve(gram, design.T @ y_dm)
            beta = coef[:-1]
            rho = float(np.clip(coef[-1], -0.95, 0.95))
            residual = y_dm - x_dm @ beta - rho * wy
            we = _panel_spatial_lag(
                residual,
                coordinates=coordinates,
                unit_ids=unit_ids,
                time_ids=time_ids,
                payload=payload,
            )
            denom = float(np.dot(we, we))
            if denom > 1e-9:
                lambda_ = float(np.clip(np.dot(we, residual) / denom, -0.95, 0.95))
            y_dm = _double_demean_vector(y - lambda_ * we, unit_ids, time_ids)
            wy = _panel_spatial_lag(
                y_dm,
                coordinates=coordinates,
                unit_ids=unit_ids,
                time_ids=time_ids,
                payload=payload,
            )

        fitted_dm = x_dm @ beta + rho * wy
        residual = y_dm - fitted_dm
        rmse = float(np.sqrt(np.mean(residual**2)))
        names = payload.get("feature_names")
        if not isinstance(names, (list, tuple)) or len(names) != x.shape[1]:
            names = [f"x{idx}" for idx in range(x.shape[1])]
        return {
            "result": SpatialResult(
                method_name="sarar",
                statistics={
                    "rmse": rmse,
                    "rho": float(rho),
                    "lambda": float(lambda_),
                    "spillover_effect_norm": float(np.linalg.norm(rho * wy)),
                },
                fitted_values=np.asarray(fitted_dm, dtype=float),
                scores=np.asarray(residual, dtype=float),
                metadata={
                    "coefficients": {name: float(beta[idx]) for idx, name in enumerate(names)},
                    "unit_count": int(np.unique(unit_ids).shape[0]),
                    "time_count": int(np.unique(time_ids).shape[0]),
                },
            )
        }


@foundry_method(
    namespace="spatial.accessibility",
    version="1.0.0",
    tags={"spatial", "accessibility", "two-step-fca"},
)
class TwoStepFCAAccessibilityEstimator:
    """Two step FCA accessibility estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "two_step_fca"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="two_step_fca",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "origin_coords",
                    SlotType.MATRIX,
                    Unit("coordinate", "value"),
                    shape=("n_origins", "n_dims"),
                ),
                SlotSpec(
                    "destination_coords",
                    SlotType.MATRIX,
                    Unit("coordinate", "value"),
                    shape=("n_destinations", "n_dims"),
                ),
                SlotSpec(
                    "opportunity_mass",
                    SlotType.VECTOR,
                    Unit("opportunity", "value"),
                    shape=("n_destinations",),
                ),
                SlotSpec(
                    "demand_mass",
                    SlotType.VECTOR,
                    Unit("population", "count"),
                    shape=("n_origins",),
                ),
                SlotSpec(
                    "travel_cost_matrix",
                    SlotType.MATRIX,
                    Unit("travel_cost", "value"),
                    shape=("n_origins", "n_destinations"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="catchment_threshold", default=1.5),
            ParameterSpec(name="distance_decay", default=0.0),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Two-step floating catchment area accessibility model with optional distance decay.",
        tags=frozenset({"spatial", "accessibility", "two-step-fca"}),
        when_to_use="Measure spatial access to services (hospitals, jobs, schools); equity analysis of facility distribution",
        citations=(
            "Luo, W. & Wang, F. (2003). Measures of spatial accessibility to health care in a GIS environment. Environment and Planning B, 30(6), 865-884.",
        ),
        when_not_to_use="No spatial coordinates; travel cost matrix unavailable; binary reachability sufficient",
        output_interpretation="Accessibility score per origin: higher = better access. Two-step accounts for supply capacity and demand competition.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _payload(state)
        origin_coords = _coords(payload["origin_coords"], "origin_coords")
        destination_coords = _coords(payload["destination_coords"], "destination_coords")
        supply = _vector(
            payload["opportunity_mass"],
            "opportunity_mass",
            expected=destination_coords.shape[0],
        )
        demand = _vector(payload["demand_mass"], "demand_mass", expected=origin_coords.shape[0])
        if payload.get("travel_cost_matrix") is None:
            travel_cost = _distance_matrix(origin_coords, destination_coords)
        else:
            travel_cost = _matrix(
                payload["travel_cost_matrix"],
                "travel_cost_matrix",
                rows=origin_coords.shape[0],
            )
        if travel_cost.shape[1] != destination_coords.shape[0]:
            raise ValueError("travel_cost_matrix must match origin/destination grid")

        threshold = max(1e-6, float(params.get("catchment_threshold", 1.5)))
        decay = max(0.0, float(params.get("distance_decay", 0.0)))
        reachability = (travel_cost <= threshold).astype(float)
        if decay > 0.0:
            reachability *= np.exp(-decay * travel_cost)
        reachable_demand = reachability.T @ demand
        provider_ratio = supply / np.maximum(reachable_demand, 1e-9)
        scores = reachability @ provider_ratio
        return {
            "result": SpatialResult(
                method_name="two_step_fca",
                statistics={
                    "mean_accessibility": float(np.mean(scores)),
                    "max_accessibility": float(np.max(scores)),
                    "covered_origins_share": float(np.mean(np.sum(reachability, axis=1) > 0.0)),
                },
                scores=np.asarray(scores, dtype=float),
                metadata={
                    "catchment_threshold": threshold,
                    "distance_decay": decay,
                },
            )
        }


@foundry_method(
    namespace="spatial.microsim",
    version="1.0.0",
    tags={"spatial", "microsim", "smsm"},
)
class SpatialMicrosimulationEstimator:
    """Spatial microsimulation estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "smsm"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="smsm",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "sample_features",
                    SlotType.MATRIX,
                    Unit("constraint", "value"),
                    shape=("n_samples", "n_constraints"),
                ),
                SlotSpec(
                    "area_constraints",
                    SlotType.MATRIX,
                    Unit("constraint", "target"),
                    shape=("n_areas", "n_constraints"),
                ),
                SlotSpec(
                    "area_coordinates",
                    SlotType.MATRIX,
                    Unit("coordinate", "value"),
                    shape=("n_areas", "n_dims"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="max_iter", default=40),
            ParameterSpec(name="tolerance", default=1e-3),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Spatial microsimulation via multiplicative reweighting to match area-level constraints.",
        tags=frozenset({"spatial", "microsim", "smsm"}),
        when_to_use="Align microsimulation outputs to aggregate control totals; demographic projection calibration",
        citations=(
            "Lovelace, R. & Dumont, M. (2016). Spatial Microsimulation with R. CRC Press.",
        ),
        when_not_to_use="Control totals are inconsistent; area-level data unavailable; no spatial granularity needed",
        output_interpretation="Calibrated weights/probabilities. Check alignment tables: model vs target. RMSE across cells.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _payload(state)
        sample_features = np.maximum(
            _matrix(payload["sample_features"], "sample_features"),
            0.0,
        )
        area_constraints = np.maximum(
            _matrix(payload["area_constraints"], "area_constraints"),
            0.0,
        )
        area_coordinates = _coords(payload["area_coordinates"], "area_coordinates")
        if area_constraints.shape[0] != area_coordinates.shape[0]:
            raise ValueError("area_constraints rows must match area_coordinates")
        if area_constraints.shape[1] != sample_features.shape[1]:
            raise ValueError("sample_features columns must match area_constraints columns")

        max_iter = max(4, int(params.get("max_iter", 40)))
        tolerance = max(1e-9, float(params.get("tolerance", 1e-3)))
        base_weights = np.asarray(payload.get("sample_weights", np.ones(sample_features.shape[0])), dtype=float)
        if base_weights.shape != (sample_features.shape[0],):
            raise ValueError("sample_weights must match sample_features rows")

        weights = np.broadcast_to(base_weights[None, :], (area_constraints.shape[0], base_weights.shape[0])).copy()
        normalized_features = sample_features / np.maximum(np.max(sample_features, axis=0, keepdims=True), 1.0)
        delta = float("inf")
        for iteration in range(max_iter):
            previous = weights.copy()
            estimates = weights @ sample_features
            for area_idx in range(area_constraints.shape[0]):
                for constraint_idx in range(area_constraints.shape[1]):
                    current = max(estimates[area_idx, constraint_idx], 1e-9)
                    target = float(area_constraints[area_idx, constraint_idx])
                    ratio = max(target / current, 1e-9)
                    weights[area_idx] *= np.exp(
                        np.log(ratio) * normalized_features[:, constraint_idx]
                    )
                weights[area_idx] = np.maximum(weights[area_idx], 1e-12)
            delta = float(np.max(np.abs(weights - previous)))
            if delta <= tolerance:
                break

        fitted = weights @ sample_features
        absolute_gap = np.abs(fitted - area_constraints)
        return {
            "result": SpatialResult(
                method_name="smsm",
                statistics={
                    "mean_absolute_gap": float(np.mean(absolute_gap)),
                    "max_absolute_gap": float(np.max(absolute_gap)),
                    "iterations": float(iteration + 1),
                },
                scores=np.asarray(weights, dtype=float),
                metadata={
                    "final_delta": delta,
                    "area_count": int(area_constraints.shape[0]),
                    "sample_count": int(sample_features.shape[0]),
                },
            )
        }


@foundry_method(
    namespace="spatial.design",
    version="1.0.0",
    tags={"spatial", "zone-design", "balanced-clustering"},
)
class ZoneBalanceDesignEstimator:
    """Zone balance design estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "zone_balance"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="zone_balance",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "coordinates",
                    SlotType.MATRIX,
                    Unit("coordinate", "value"),
                    shape=("n_obs", "n_dims"),
                ),
                SlotSpec("values", SlotType.VECTOR, Unit("value", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="n_zones", default=3),
            ParameterSpec(name="max_iter", default=24),
            ParameterSpec(name="balance_penalty", default=0.35),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Balanced zone design that trades off spatial compactness and equalized zone totals.",
        tags=frozenset({"spatial", "zone-design", "balanced-clustering"}),
        when_to_use="Design administrative or analytical zones; balance compactness with population equality; electoral or service redistricting",
        citations=(
            "Openshaw, S. (1977). A geographical solution to scale and aggregation problems in region-building, partitioning and spatial modelling. Transactions of the Institute of British Geographers, 2(4), 459-472.",
        ),
        when_not_to_use="Pre-defined fixed zones required; no spatial coordinates; purely aspatial grouping",
        output_interpretation="Zone assignments per unit. Compactness score and balance metric. Compare zone totals to targets.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _payload(state)
        coordinates = _coords(payload["coordinates"], "coordinates")
        values = _vector(payload["values"], "values", expected=coordinates.shape[0])
        n_obs = coordinates.shape[0]
        n_zones = max(1, min(int(params.get("n_zones", 3)), n_obs))
        max_iter = max(4, int(params.get("max_iter", 24)))
        balance_penalty = max(0.0, float(params.get("balance_penalty", 0.35)))

        seed_idx = np.linspace(0, n_obs - 1, num=n_zones, dtype=int)
        centroids = coordinates[seed_idx].copy()
        assignments = np.zeros(n_obs, dtype=int)
        target_total = float(np.sum(values) / n_zones)
        for _ in range(max_iter):
            zone_totals = np.zeros(n_zones, dtype=float)
            for obs_idx in range(n_obs):
                distances = np.sqrt(np.sum((centroids - coordinates[obs_idx]) ** 2, axis=1))
                overload = np.maximum(zone_totals - target_total, 0.0) / max(target_total, 1e-9)
                score = distances + balance_penalty * overload
                zone = int(np.argmin(score))
                assignments[obs_idx] = zone
                zone_totals[zone] += values[obs_idx]
            for zone_idx in range(n_zones):
                zone_mask = assignments == zone_idx
                if np.any(zone_mask):
                    centroids[zone_idx] = np.average(
                        coordinates[zone_mask],
                        axis=0,
                        weights=np.maximum(values[zone_mask], 1e-6),
                    )
            next_totals = np.array(
                [np.sum(values[assignments == zone_idx]) for zone_idx in range(n_zones)],
                dtype=float,
            )
            if np.all(next_totals > 0.0):
                zone_totals = next_totals

        imbalance = float(
            np.mean(np.abs(zone_totals - target_total) / max(target_total, 1e-9))
        )
        return {
            "result": SpatialResult(
                method_name="zone_balance",
                statistics={
                    "imbalance": imbalance,
                    "target_zone_total": target_total,
                },
                scores=assignments.astype(float),
                metadata={
                    "zone_totals": zone_totals.tolist(),
                    "n_zones": n_zones,
                },
            )
        }


def _kmeans_like_assignments(
    coordinates: np.ndarray,
    values: np.ndarray,
    *,
    n_zones: int,
    rng: np.random.Generator,
    max_iter: int = 8,
) -> tuple[np.ndarray, np.ndarray]:
    n_obs = coordinates.shape[0]
    seed_idx = rng.choice(n_obs, size=n_zones, replace=False)
    centroids = coordinates[seed_idx].copy()
    assignments = np.zeros(n_obs, dtype=int)
    for _ in range(max_iter):
        distances = _distance_matrix(coordinates, centroids)
        assignments = np.argmin(distances, axis=1).astype(int)
        for zone_idx in range(n_zones):
            mask = assignments == zone_idx
            if np.any(mask):
                centroids[zone_idx] = np.average(
                    coordinates[mask],
                    axis=0,
                    weights=np.maximum(values[mask], 1e-6),
                )
    return assignments, centroids


@foundry_method(
    namespace="spatial.design",
    version="1.0.0",
    tags={"spatial", "design", "maup"},
)
class MAUPSensitivityProfileEstimator:
    """MAUP sensitivity profile estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "maup_profile"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="maup_profile",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "coordinates",
                    SlotType.MATRIX,
                    Unit("coordinate", "value"),
                    shape=("n_obs", "n_dims"),
                ),
                SlotSpec("values", SlotType.VECTOR, Unit("value", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="min_zones", default=2),
            ParameterSpec(name="max_zones", default=5),
            ParameterSpec(name="n_restarts", default=4),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Profiles MAUP sensitivity by re-aggregating observations into alternative zone systems.",
        tags=frozenset({"spatial", "design", "maup"}),
        when_to_use="Assess sensitivity of spatial analysis results to choice of zone boundaries; MAUP diagnostics",
        citations=(
            "Openshaw, S. & Taylor, P. (1979). A million or so correlation coefficients: Three experiments on the modifiable areal unit problem. In Statistical Applications in the Spatial Sciences, Pion.",
            "Fotheringham, A. & Wong, D. (1991). The modifiable areal unit problem in multivariate statistical analysis. Environment and Planning A, 23(7), 1025-1044.",
        ),
        when_not_to_use="Fixed administrative zones that cannot be altered; no spatial coordinates available",
        output_interpretation="Sensitivity profile across zone systems. High variance across aggregations = MAUP-sensitive result. Guides robustness reporting.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _payload(state)
        coordinates = _coords(payload["coordinates"], "coordinates")
        values = _vector(payload["values"], "values", expected=coordinates.shape[0])
        n_obs = coordinates.shape[0]
        min_zones = max(2, int(params.get("min_zones", 2)))
        max_zones = min(max(min_zones, int(params.get("max_zones", 5))), n_obs)
        n_restarts = max(1, int(params.get("n_restarts", 4)))
        rng = np.random.default_rng(int(params.get("__seed__", 0)))

        profile_rows: list[list[float]] = []
        best_assignments: dict[int, list[int]] = {}
        global_variance = float(np.var(values)) if n_obs > 1 else 0.0
        for n_zones in range(min_zones, max_zones + 1):
            between_values: list[float] = []
            within_values: list[float] = []
            best_score = float("-inf")
            best_row_assignment: np.ndarray | None = None
            for _ in range(n_restarts):
                assignments, _ = _kmeans_like_assignments(
                    coordinates,
                    values,
                    n_zones=n_zones,
                    rng=rng,
                )
                zone_means = np.array(
                    [
                        float(np.mean(values[assignments == zone_idx]))
                        for zone_idx in range(n_zones)
                        if np.any(assignments == zone_idx)
                    ],
                    dtype=float,
                )
                between = float(np.var(zone_means)) if zone_means.size > 1 else 0.0
                within = float(
                    np.mean(
                        [
                            np.var(values[assignments == zone_idx]) if np.sum(assignments == zone_idx) > 1 else 0.0
                            for zone_idx in range(n_zones)
                            if np.any(assignments == zone_idx)
                        ]
                    )
                )
                score = between - within
                if score > best_score:
                    best_score = score
                    best_row_assignment = assignments.copy()
                between_values.append(between)
                within_values.append(within)
            profile_rows.append(
                [
                    float(n_zones),
                    float(np.mean(between_values)),
                    float(np.mean(within_values)),
                    float(np.mean(between_values) / max(global_variance, 1e-9)),
                ]
            )
            if best_row_assignment is not None:
                best_assignments[n_zones] = best_row_assignment.astype(int).tolist()

        profile = np.asarray(profile_rows, dtype=float)
        return {
            "result": SpatialResult(
                method_name="maup_profile",
                statistics={
                    "global_variance": global_variance,
                    "max_relative_between_variance": float(np.max(profile[:, 3])) if profile.size else 0.0,
                },
                scores=profile,
                metadata={
                    "columns": [
                        "n_zones",
                        "between_zone_variance",
                        "within_zone_variance",
                        "relative_between_variance",
                    ],
                    "best_assignments": best_assignments,
                },
            )
        }


__all__ = [
    "GaussianProcessKrigingEstimator",
    "InverseDistanceWeightingEstimator",
    "MAUPSensitivityProfileEstimator",
    "SpatialMicrosimulationEstimator",
    "SpatialSARARPanelEstimator",
    "SpatialSLXPanelEstimator",
    "TwoStepFCAAccessibilityEstimator",
    "ZoneBalanceDesignEstimator",
]
