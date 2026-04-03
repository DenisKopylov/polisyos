"""Public ml clustering module API."""
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

from .protocols import ClusteringResult, TabularData


def _tabular_payload(state: Any) -> dict[str, Any]:
    if isinstance(state, TabularData):
        return state.model_dump(mode="python")
    if isinstance(state, Mapping):
        nested = state.get("tabular_data")
        if isinstance(nested, TabularData):
            return nested.model_dump(mode="python")
        if isinstance(nested, Mapping):
            payload = dict(nested)
            payload.update({k: v for k, v in state.items() if k not in {"tabular_data"}})
            return payload
        return dict(state)
    raise TypeError("state must be TabularData or mapping")


@foundry_method(
    namespace="ml.clustering",
    version="1.0.0",
    tags={"ml", "clustering", "kmeans"},
)
class KMeansEstimator:
    """K means estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("scikit-learn", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="kmeans",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "features",
                    SlotType.MATRIX,
                    Unit("feature", "value"),
                    shape=("n_obs", "n_features"),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("cluster", "json"),
                    contract_id=ClusteringResult.contract_id,
                )
            }
        ),
        parameters=(
            ParameterSpec(name="n_clusters", default=3),
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
        description="K-means clustering for segmentation of tabular observations.",
        tags=frozenset({"ml", "clustering", "kmeans"}),
        when_to_use="Unsupervised grouping of units; identify latent population segments; input for targeting policy",
        citations=(
            "MacQueen, J. (1967). Some methods for classification and analysis of multivariate observations. Proceedings of the 5th Berkeley Symposium on Mathematical Statistics and Probability, 1, 281-297.",
        ),
        when_not_to_use="Non-spherical clusters; unknown k with no elbow; presence of outliers (use DBSCAN)",
        output_interpretation="Cluster assignments + centroids. Silhouette score: >0.5 = good. Elbow in within-cluster SS for k selection.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TabularData:
        payload = _tabular_payload(fallback_state)
        payload.update(bound_inputs)
        return TabularData.model_validate(payload)

    @staticmethod
    def pure_step(state: TabularData, params: Mapping[str, Any]) -> dict[str, Any]:
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score

        data = state if isinstance(state, TabularData) else TabularData.model_validate(state)
        n_clusters = max(2, min(int(params.get("n_clusters", 3)), data.features.shape[0] - 1))
        model = KMeans(
            n_clusters=n_clusters,
            n_init=10,
            random_state=int(params.get("random_state", 0)),
        )
        labels = model.fit_predict(np.asarray(data.features, dtype=float))
        metrics: dict[str, float] = {}
        if len(np.unique(labels)) > 1:
            metrics["silhouette_score"] = float(
                silhouette_score(np.asarray(data.features, dtype=float), labels)
            )
        return {
            "result": ClusteringResult(
                method_name="kmeans",
                labels=np.asarray(labels, dtype=int),
                centers=np.asarray(model.cluster_centers_, dtype=float),
                metrics=metrics,
                metadata={"library": "scikit-learn", "estimator": "KMeans"},
            )
        }


__all__ = ["KMeansEstimator"]
