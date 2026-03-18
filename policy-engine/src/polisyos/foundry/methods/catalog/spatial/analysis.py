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

from .protocols import AccessibilityData, GravityFlowData, SpatialData, SpatialResult


def _spatial_payload(state: Any) -> dict[str, Any]:
    if isinstance(state, SpatialData):
        return state.model_dump(mode="python")
    if isinstance(state, Mapping):
        nested = state.get("spatial_data")
        if isinstance(nested, SpatialData):
            return nested.model_dump(mode="python")
        if isinstance(nested, Mapping):
            payload = dict(nested)
            payload.update({k: v for k, v in state.items() if k not in {"spatial_data"}})
            return payload
        return dict(state)
    raise TypeError("state must be SpatialData or mapping")


def _gravity_payload(state: Any) -> dict[str, Any]:
    if isinstance(state, GravityFlowData):
        return state.model_dump(mode="python")
    if isinstance(state, Mapping):
        return dict(state)
    raise TypeError("state must be GravityFlowData or mapping")


def _accessibility_payload(state: Any) -> dict[str, Any]:
    if isinstance(state, AccessibilityData):
        return state.model_dump(mode="python")
    if isinstance(state, Mapping):
        return dict(state)
    raise TypeError("state must be AccessibilityData or mapping")


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


def _distance_weights(coordinates: np.ndarray, *, decay: float = 1.0) -> np.ndarray:
    from scipy.spatial.distance import cdist

    dist = cdist(coordinates, coordinates, metric="euclidean")
    with np.errstate(divide="ignore"):
        weights = 1.0 / np.power(np.maximum(dist, 1e-8), decay)
    np.fill_diagonal(weights, 0.0)
    row_sums = np.sum(weights, axis=1, keepdims=True)
    row_sums[row_sums == 0.0] = 1.0
    return weights / row_sums


def _spatial_weights(data: SpatialData, *, decay: float = 1.0) -> np.ndarray:
    if data.weights_matrix is not None:
        weights = np.asarray(data.weights_matrix, dtype=float)
        row_sums = np.sum(weights, axis=1, keepdims=True)
        row_sums[row_sums == 0.0] = 1.0
        return weights / row_sums
    return _distance_weights(np.asarray(data.coordinates, dtype=float), decay=decay)


@foundry_method(
    namespace="spatial.autocorrelation",
    version="1.0.0",
    tags={"spatial", "moran-i"},
)
class MoranIEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scipy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="moran_i",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("coordinates", SlotType.MATRIX, Unit("coordinate", "value"), shape=("n_obs", "n_dims")),
                SlotSpec("values", SlotType.VECTOR, Unit("value", "value"), shape=("n_obs",)),
                SlotSpec("weights_matrix", SlotType.MATRIX, Unit("spatial_weight", "value"), shape=("n_obs", "n_obs")),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="distance_decay", default=1.0),
            ParameterSpec(name="n_permutations", default=0),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Global Moran's I test for spatial autocorrelation.",
        tags=frozenset({"spatial", "moran-i"}),
        when_to_use="Test for spatial clustering; check spatial autocorrelation before regression",
        when_not_to_use="No spatial weights matrix available; data are not spatially indexed",
        output_interpretation="Moran's I ∈ [-1,1]. I>0 = positive spatial clustering. p-value from permutation test.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> SpatialData:
        payload = _spatial_payload(fallback_state)
        payload.update(bound_inputs)
        return SpatialData.model_validate(payload)

    @staticmethod
    def pure_step(state: SpatialData, params: Mapping[str, Any]) -> dict[str, Any]:
        rng = params.get("__rng__")
        if rng is None or not hasattr(rng, "permutation"):
            rng = np.random.default_rng(int(params.get("__seed__", 0)))
        data = state if isinstance(state, SpatialData) else SpatialData.model_validate(state)
        y = np.asarray(data.values, dtype=float)
        weights = _spatial_weights(data, decay=float(params.get("distance_decay", 1.0)))
        z = y - np.mean(y)
        w_sum = float(np.sum(weights))
        statistic = float((y.shape[0] / w_sum) * ((z @ weights @ z) / max(z @ z, 1e-12)))
        p_value = None
        n_perm = max(0, int(params.get("n_permutations", 0)))
        if n_perm > 0:
            perm_stats = []
            for _ in range(n_perm):
                z_perm = rng.permutation(z)
                perm_stats.append(float((y.shape[0] / w_sum) * ((z_perm @ weights @ z_perm) / max(z_perm @ z_perm, 1e-12))))
            p_value = float(np.mean(np.abs(np.asarray(perm_stats)) >= abs(statistic)))
        return {
            "result": SpatialResult(
                method_name="moran_i",
                statistics={"moran_i": statistic, "p_value": float(p_value) if p_value is not None else np.nan},
                metadata={"n_permutations": n_perm},
            )
        }


@foundry_method(
    namespace="spatial.regression",
    version="1.0.0",
    tags={"spatial", "gwr"},
)
class GWREstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scipy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="gwr",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("coordinates", SlotType.MATRIX, Unit("coordinate", "value"), shape=("n_obs", "n_dims")),
                SlotSpec("values", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec("features", SlotType.MATRIX, Unit("feature", "value"), shape=("n_obs", "n_features")),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="bandwidth", default=1.0),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Geographically weighted regression using Gaussian kernel weights.",
        tags=frozenset({"spatial", "gwr"}),
        when_to_use="Regression with spatially varying coefficients; explore local heterogeneity in policy effects",
        when_not_to_use="Global homogeneous relationships; very small spatial datasets; bandwidth selection is unclear",
        output_interpretation="Local coefficients map showing spatial variation. Compare to global OLS to assess non-stationarity.",
        typical_min_obs=50,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> SpatialData:
        payload = _spatial_payload(fallback_state)
        payload.update(bound_inputs)
        return SpatialData.model_validate(payload)

    @staticmethod
    def pure_step(state: SpatialData, params: Mapping[str, Any]) -> dict[str, Any]:
        from scipy.spatial.distance import cdist

        data = state if isinstance(state, SpatialData) else SpatialData.model_validate(state)
        x = np.asarray(data.features, dtype=float)
        y = np.asarray(data.values, dtype=float)
        coords = np.asarray(data.coordinates, dtype=float)
        design = np.column_stack([np.ones(x.shape[0]), x])
        dist = cdist(coords, coords)
        bandwidth = max(1e-6, float(params.get("bandwidth", 1.0)))
        local_betas = np.zeros((x.shape[0], design.shape[1]), dtype=float)
        fitted = np.zeros(x.shape[0], dtype=float)
        for idx in range(x.shape[0]):
            weights = np.exp(-0.5 * (dist[idx] / bandwidth) ** 2)
            w_matrix = np.diag(weights)
            beta = np.linalg.pinv(design.T @ w_matrix @ design) @ design.T @ w_matrix @ y
            local_betas[idx] = beta
            fitted[idx] = float(design[idx] @ beta)
        rmse = float(np.sqrt(np.mean((fitted - y) ** 2)))
        return {
            "result": SpatialResult(
                method_name="gwr",
                statistics={"rmse": rmse},
                local_coefficients=local_betas,
                fitted_values=fitted,
                metadata={"bandwidth": bandwidth},
            )
        }


@foundry_method(
    namespace="spatial.regression",
    version="1.0.0",
    tags={"spatial", "spatial-durbin"},
)
class SpatialDurbinEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("statsmodels", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="spatial_durbin",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("coordinates", SlotType.MATRIX, Unit("coordinate", "value"), shape=("n_obs", "n_dims")),
                SlotSpec("values", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec("features", SlotType.MATRIX, Unit("feature", "value"), shape=("n_obs", "n_features")),
                SlotSpec("weights_matrix", SlotType.MATRIX, Unit("spatial_weight", "value"), shape=("n_obs", "n_obs")),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="distance_decay", default=1.0),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Spatial Durbin regression with outcome and feature spatial lags.",
        tags=frozenset({"spatial", "spatial-durbin"}),
        when_to_use="Regression with spatial spillovers; spatial lag model for policy diffusion; SEM for spatial error",
        when_not_to_use="No spatial structure; spatial weights uncertain; pure time-series data",
        output_interpretation="ρ (spatial lag): spillover intensity. Direct + indirect (spillover) effects of each regressor.",
        typical_min_obs=50,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> SpatialData:
        payload = _spatial_payload(fallback_state)
        payload.update(bound_inputs)
        return SpatialData.model_validate(payload)

    @staticmethod
    def pure_step(state: SpatialData, params: Mapping[str, Any]) -> dict[str, Any]:
        import statsmodels.api as sm

        data = state if isinstance(state, SpatialData) else SpatialData.model_validate(state)
        weights = _spatial_weights(data, decay=float(params.get("distance_decay", 1.0)))
        x = np.asarray(data.features, dtype=float)
        y = np.asarray(data.values, dtype=float)
        wy = weights @ y
        wx = weights @ x
        design = sm.add_constant(np.column_stack([wy, x, wx]), has_constant="add")
        fit = sm.OLS(y, design).fit(cov_type="HC1")
        names = ["const", "rho"] + [f"x{i}" for i in range(x.shape[1])] + [f"wx{i}" for i in range(x.shape[1])]
        statistics = {
            "r_squared": float(getattr(fit, "rsquared", np.nan)),
            "adj_r_squared": float(getattr(fit, "rsquared_adj", np.nan)),
        }
        for idx, name in enumerate(names):
            statistics[name] = float(fit.params[idx])
        return {
            "result": SpatialResult(
                method_name="spatial_durbin",
                statistics=statistics,
                fitted_values=np.asarray(fit.fittedvalues, dtype=float),
                metadata={"cov_type": "HC1"},
            )
        }


@foundry_method(
    namespace="spatial.flows",
    version="1.0.0",
    tags={"spatial", "gravity-model"},
)
class GravityModelEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("statsmodels", "numpy", "scipy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="gravity_model",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("origin_coords", SlotType.MATRIX, Unit("coordinate", "value"), shape=("n_origins", "n_dims")),
                SlotSpec("destination_coords", SlotType.MATRIX, Unit("coordinate", "value"), shape=("n_destinations", "n_dims")),
                SlotSpec("origin_mass", SlotType.VECTOR, Unit("mass", "value"), shape=("n_origins",)),
                SlotSpec("destination_mass", SlotType.VECTOR, Unit("mass", "value"), shape=("n_destinations",)),
                SlotSpec("observed_flows", SlotType.MATRIX, Unit("flow", "value"), shape=("n_origins", "n_destinations")),
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
        description="Log-linear gravity model for trade, migration, or commuting flows.",
        tags=frozenset({"spatial", "gravity-model"}),
        when_to_use="Model bilateral flows (trade, migration, commuting) as function of mass and distance",
        when_not_to_use="Non-bilateral data; zero-inflated flows (use PPML); no distance information available",
        output_interpretation="Distance decay coefficient: elasticity of flow to distance. Origin/destination elasticities: size effects. R² on log scale.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> GravityFlowData:
        payload = _gravity_payload(fallback_state)
        payload.update(bound_inputs)
        return GravityFlowData.model_validate(payload)

    @staticmethod
    def pure_step(state: GravityFlowData, params: Mapping[str, Any]) -> dict[str, Any]:
        import statsmodels.api as sm
        from scipy.spatial.distance import cdist

        del params
        data = state if isinstance(state, GravityFlowData) else GravityFlowData.model_validate(state)
        flows = np.asarray(data.observed_flows, dtype=float)
        dist = cdist(np.asarray(data.origin_coords, dtype=float), np.asarray(data.destination_coords, dtype=float))
        rows = []
        target = []
        for i in range(flows.shape[0]):
            for j in range(flows.shape[1]):
                rows.append(
                    [
                        np.log(max(float(data.origin_mass[i]), 1e-8)),
                        np.log(max(float(data.destination_mass[j]), 1e-8)),
                        np.log(max(float(dist[i, j]), 1e-8)),
                    ]
                )
                target.append(np.log(max(float(flows[i, j]), 1e-8)))
        x = sm.add_constant(np.asarray(rows, dtype=float), has_constant="add")
        fit = sm.OLS(np.asarray(target, dtype=float), x).fit(cov_type="HC1")
        fitted_log = fit.predict(x)
        fitted = np.exp(fitted_log).reshape(flows.shape)
        return {
            "result": SpatialResult(
                method_name="gravity_model",
                statistics={
                    "intercept": float(fit.params[0]),
                    "origin_elasticity": float(fit.params[1]),
                    "destination_elasticity": float(fit.params[2]),
                    "distance_decay": float(-fit.params[3]),
                    "r_squared": float(getattr(fit, "rsquared", np.nan)),
                },
                fitted_values=fitted,
                metadata={"cov_type": "HC1"},
            )
        }


@foundry_method(
    namespace="spatial.accessibility",
    version="1.0.0",
    tags={"spatial", "accessibility-index"},
)
class AccessibilityIndexEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scipy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="accessibility_index",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("origin_coords", SlotType.MATRIX, Unit("coordinate", "value"), shape=("n_origins", "n_dims")),
                SlotSpec("destination_coords", SlotType.MATRIX, Unit("coordinate", "value"), shape=("n_destinations", "n_dims")),
                SlotSpec("opportunity_mass", SlotType.VECTOR, Unit("opportunity", "value"), shape=("n_destinations",)),
                SlotSpec("travel_cost_matrix", SlotType.MATRIX, Unit("cost", "value"), shape=("n_origins", "n_destinations")),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("spatial", "json"),
                    contract_id=SpatialResult.contract_id,
                ),
                SlotSpec("scores", SlotType.VECTOR, Unit("accessibility", "value"), shape=("n_origins",)),
            }
        ),
        parameters=(ParameterSpec(name="decay", default=1.0),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Gravity-style accessibility index from origins to opportunities.",
        tags=frozenset({"spatial", "accessibility-index"}),
        when_to_use="Measure spatial access to services (hospitals, jobs, schools); equity analysis of facility distribution",
        when_not_to_use="No spatial coordinates; travel cost matrix unavailable; binary reachability sufficient",
        output_interpretation="Accessibility score per origin: higher = better access. Decay parameter controls distance penalty. Useful for spatial equity mapping.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> AccessibilityData:
        payload = _accessibility_payload(fallback_state)
        payload.update(bound_inputs)
        return AccessibilityData.model_validate(payload)

    @staticmethod
    def pure_step(state: AccessibilityData, params: Mapping[str, Any]) -> dict[str, Any]:
        from scipy.spatial.distance import cdist

        data = state if isinstance(state, AccessibilityData) else AccessibilityData.model_validate(state)
        decay = max(1e-8, float(params.get("decay", 1.0)))
        travel_cost = (
            np.asarray(data.travel_cost_matrix, dtype=float)
            if data.travel_cost_matrix is not None
            else cdist(np.asarray(data.origin_coords, dtype=float), np.asarray(data.destination_coords, dtype=float))
        )
        scores = np.sum(
            np.asarray(data.opportunity_mass, dtype=float)[None, :] / np.power(np.maximum(travel_cost, 1e-8), decay),
            axis=1,
        )
        return {
            "result": SpatialResult(
                method_name="accessibility_index",
                statistics={
                    "mean_accessibility": float(np.mean(scores)),
                    "max_accessibility": float(np.max(scores)),
                },
                scores=scores,
                metadata={"decay": decay},
            ),
            "scores": scores,
        }


__all__ = [
    "AccessibilityIndexEstimator",
    "GravityModelEstimator",
    "GWREstimator",
    "MoranIEstimator",
    "SpatialDurbinEstimator",
]
