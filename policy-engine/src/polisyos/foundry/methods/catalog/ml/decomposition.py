"""Project tabular features into low-dimensional linear embeddings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

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

from .protocols import EmbeddingResult, TabularData


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
    namespace="ml.decomposition",
    version="1.0.0",
    tags={"ml", "decomposition", "pca"},
)
class PCAEstimator:
    """Extract orthogonal principal components under linear variance structure; avoid interpreting components causally."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("scikit-learn", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="pca",
        namespace="",
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
                    Unit("embedding", "json"),
                    contract_id=EmbeddingResult.contract_id,
                )
            }
        ),
        parameters=(ParameterSpec(name="n_components", default=2),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Principal component decomposition for tabular features.",
        tags=frozenset({"ml", "decomposition", "pca"}),
        when_to_use="Dimensionality reduction; decorrelation of features; visualization of high-dimensional data",
        citations=("Jolliffe, I. (2002). Principal Component Analysis. Springer.",),
        when_not_to_use="Non-linear structure (use UMAP/t-SNE); non-negative data where parts matter (use NMF)",
        output_interpretation="Explained variance ratio per component. Loadings show variable contributions. Biplot for interpretation.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TabularData:
        payload = _tabular_payload(fallback_state)
        payload.update(bound_inputs)
        return TabularData.model_validate(payload)

    @staticmethod
    def pure_step(state: TabularData, params: Mapping[str, Any]) -> dict[str, Any]:
        from sklearn.decomposition import PCA

        data = state if isinstance(state, TabularData) else TabularData.model_validate(state)
        n_components = max(1, min(int(params.get("n_components", 2)), data.features.shape[1]))
        model = PCA(n_components=n_components)
        transformed = model.fit_transform(np.asarray(data.features, dtype=float))
        return {
            "result": EmbeddingResult(
                method_name="pca",
                transformed=transformed,
                components=np.asarray(model.components_, dtype=float),
                explained_variance_ratio=[
                    float(value) for value in model.explained_variance_ratio_
                ],
                metadata={"library": "scikit-learn", "estimator": "PCA"},
            )
        }


__all__ = ["PCAEstimator"]
