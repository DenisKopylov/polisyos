"""Frontier ML estimators for tabular deep learning, graph learning, and self-supervision."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability import DeterminismTier
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

from ..network.embedding_fidelity import maybe_compute_embedding_fidelity_certificate
from .protocols import EmbeddingResult, TabularData
from .regression import (
    _build_prediction_result,
    _feature_names,
    _prediction_output_slots,
    _tabular_payload,
)


def _embedding_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("embedding", "json"),
                contract_id=EmbeddingResult.contract_id,
            )
        }
    )


def _normalize_features(x_raw: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = np.mean(x_raw, axis=0, keepdims=True)
    std = np.std(x_raw, axis=0, keepdims=True)
    std = np.where(std > 1.0e-6, std, 1.0)
    return (x_raw - mean) / std, mean, std


def _weighted_linear_head(
    embedding: np.ndarray,
    target: np.ndarray,
    sample_weight: np.ndarray | None = None,
    ridge: float = 1.0e-4,
) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(embedding, dtype=float)
    y = np.asarray(target, dtype=float)
    design = np.column_stack([np.ones(x.shape[0]), x])
    if sample_weight is not None:
        w = np.sqrt(np.clip(np.asarray(sample_weight, dtype=float), 1.0e-12, None))
        design = design * w[:, None]
        y = y * w
    gram = design.T @ design + ridge * np.eye(design.shape[1])
    coef = np.linalg.solve(gram, design.T @ y)
    predictions = np.column_stack([np.ones(x.shape[0]), x]) @ coef
    return coef, predictions


def _softmax(values: np.ndarray, axis: int = -1) -> np.ndarray:
    centered = values - np.max(values, axis=axis, keepdims=True)
    exp_values = np.exp(centered)
    return exp_values / np.maximum(np.sum(exp_values, axis=axis, keepdims=True), 1.0e-12)


def _attention_importance(attention: np.ndarray, feature_names: list[str]) -> dict[str, float]:
    importance = np.mean(np.asarray(attention, dtype=float), axis=(0, 1))
    total = float(np.sum(importance))
    if total > 1.0e-12:
        importance = importance / total
    return {name: float(value) for name, value in zip(feature_names, importance)}


def _metadata_with_embedding_fidelity(
    metadata: Mapping[str, Any],
    embedding_fidelity_certificate: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(metadata)
    if embedding_fidelity_certificate is not None:
        merged.setdefault("embedding_fidelity_certificate", dict(embedding_fidelity_certificate))
    return merged


def _graph_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "node_features",
                SlotType.MATRIX,
                Unit("feature", "value"),
                shape=("n_nodes", "n_features"),
            ),
            SlotSpec(
                "adjacency_matrix",
                SlotType.MATRIX,
                Unit("network", "adjacency"),
                shape=("n_nodes", "n_nodes"),
            ),
            SlotSpec("target", SlotType.VECTOR, Unit("target", "value"), shape=("n_nodes",)),
        }
    )


@foundry_method(
    namespace="ml.deep",
    version="1.0.0",
    tags={"ml", "deep-learning", "ft-transformer", "frontier"},
)
class FTTransformerEstimator:
    """FT-Transformer style regressor with feature-token attention and a linear head."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ft_transformer",
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
            ParameterSpec("d_model", default=24, is_static=True),
            ParameterSpec("ridge_alpha", default=0.1),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Feature-token transformer regressor for tabular prediction with richer interactions than a simple ridge head.",
        tags=frozenset({"ml", "deep-learning", "ft-transformer", "frontier"}),
        citations=(
            "Gorishniy, Y. et al. (2021). Revisiting deep learning models for tabular data.",
        ),
        when_to_use="Tabular prediction with medium-to-large datasets where feature interactions matter and tree baselines are too rigid.",
        when_not_to_use="Very small samples, strict interpretability requirements, or settings needing calibrated uncertainty without extra calibration.",
        typical_min_obs=80,
        output_interpretation="Attention-derived feature_importances summarize which columns were repeatedly selected into the learned token representation.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TabularData:
        payload = _tabular_payload(fallback_state)
        payload.update(bound_inputs)
        return TabularData.model_validate(payload)

    @staticmethod
    def pure_step(state: TabularData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, TabularData) else TabularData.model_validate(state)
        x, _, _ = _normalize_features(np.asarray(data.features, dtype=float))
        y = np.asarray(data.target, dtype=float)
        d_model = max(8, int(params.get("d_model", 24)))
        rng = np.random.default_rng(int(params.get("__seed__", 0)))

        feature_scale = rng.normal(scale=0.12, size=(x.shape[1], d_model))
        feature_bias = rng.normal(scale=0.04, size=(x.shape[1], d_model))
        q_proj = rng.normal(scale=1.0 / math.sqrt(d_model), size=(d_model, d_model))
        k_proj = rng.normal(scale=1.0 / math.sqrt(d_model), size=(d_model, d_model))
        v_proj = rng.normal(scale=1.0 / math.sqrt(d_model), size=(d_model, d_model))
        gate_proj = rng.normal(scale=0.08, size=(d_model, d_model))

        tokens = x[:, :, None] * feature_scale[None, :, :] + feature_bias[None, :, :]
        q = np.einsum("bfd,dh->bfh", tokens, q_proj)
        k = np.einsum("bfd,dh->bfh", tokens, k_proj)
        v = np.einsum("bfd,dh->bfh", tokens, v_proj)
        scores = np.einsum("bqh,bkh->bqk", q, k) / math.sqrt(d_model)
        attention = _softmax(scores, axis=-1)
        attended = np.einsum("bqk,bkh->bqh", attention, v)
        gates = 1.0 / (1.0 + np.exp(-np.einsum("bfd,dh->bfh", tokens, gate_proj)))
        encoded = np.mean(gates * attended + (1.0 - gates) * tokens, axis=1)

        coef, predictions = _weighted_linear_head(
            encoded,
            y,
            sample_weight=data.sample_weight,
            ridge=float(params.get("ridge_alpha", 0.1)),
        )
        feature_importances = _attention_importance(attention, _feature_names(data))
        coefficients = {f"latent_{idx}": float(value) for idx, value in enumerate(coef[1:])}
        coefficients["intercept"] = float(coef[0])
        return _build_prediction_result(
            method_name="ft_transformer",
            predictions=predictions,
            target=y,
            feature_importances=feature_importances,
            coefficients=coefficients,
            model_info={"library": "numpy", "estimator": "FTTransformerStyleRegressor"},
            metadata={"d_model": d_model, "encoder": "feature_token_attention"},
        )


@foundry_method(
    namespace="ml.deep",
    version="1.0.0",
    tags={"ml", "deep-learning", "tabnet", "frontier"},
)
class TabNetEstimator:
    """TabNet style sparse-step regressor for structured tabular data."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="tabnet",
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
            ParameterSpec("n_steps", default=3, is_static=True),
            ParameterSpec("ridge_alpha", default=0.2),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="TabNet style sparse-feature decision steps with interpretable feature masks.",
        tags=frozenset({"ml", "deep-learning", "tabnet", "frontier"}),
        citations=(
            "Arik, S. & Pfister, T. (2021). TabNet: Attentive interpretable tabular learning.",
        ),
        when_to_use="Tabular regression where sparse feature selection per decision step is desirable and feature masks help explanation.",
        when_not_to_use="Data-poor problems, dense smooth functions where Gaussian-process models work better, or tasks needing exact probabilistic calibration.",
        typical_min_obs=80,
        output_interpretation="feature_importances come from average sparse masks across decision steps and approximate which features carried predictive mass.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TabularData:
        payload = _tabular_payload(fallback_state)
        payload.update(bound_inputs)
        return TabularData.model_validate(payload)

    @staticmethod
    def pure_step(state: TabularData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, TabularData) else TabularData.model_validate(state)
        x, _, _ = _normalize_features(np.asarray(data.features, dtype=float))
        y = np.asarray(data.target, dtype=float)
        n_steps = max(2, int(params.get("n_steps", 3)))
        rng = np.random.default_rng(int(params.get("__seed__", 0)))

        feature_signal = np.abs(np.corrcoef(np.column_stack([x, y]).T)[-1, :-1])
        feature_signal = np.nan_to_num(feature_signal, nan=0.0)
        prior = np.ones_like(feature_signal)
        masked_views = []
        masks = []
        for step in range(n_steps):
            logits = (feature_signal + 0.2 * rng.normal(size=feature_signal.shape[0])) * prior
            mask = _softmax(logits[None, :], axis=1)[0]
            masks.append(mask)
            masked_views.append(x * mask[None, :])
            prior = np.clip(prior * (1.0 - 0.35 * mask), 0.1, None)
        encoded = np.concatenate(masked_views, axis=1)

        coef, predictions = _weighted_linear_head(
            encoded,
            y,
            sample_weight=data.sample_weight,
            ridge=float(params.get("ridge_alpha", 0.2)),
        )
        mean_mask = np.mean(np.asarray(masks, dtype=float), axis=0)
        feature_importances = {
            name: float(value)
            for name, value in zip(
                _feature_names(data), mean_mask / max(float(np.sum(mean_mask)), 1.0e-12)
            )
        }
        coefficients = {f"step_feature_{idx}": float(value) for idx, value in enumerate(coef[1:])}
        coefficients["intercept"] = float(coef[0])
        return _build_prediction_result(
            method_name="tabnet",
            predictions=predictions,
            target=y,
            feature_importances=feature_importances,
            coefficients=coefficients,
            model_info={"library": "numpy", "estimator": "TabNetStyleRegressor"},
            metadata={"n_steps": n_steps, "average_mask": mean_mask.tolist()},
        )


@foundry_method(
    namespace="ml.graph",
    version="1.0.0",
    tags={"ml", "graph", "gnn", "frontier"},
)
class GraphNeuralNetworkEstimator:
    """Graph convolution style regressor for node-level prediction tasks."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="graph_conv",
        namespace="",
        version="0.0.0",
        input_slots=_graph_output_slots(),
        output_slots=_prediction_output_slots(),
        parameters=(ParameterSpec("hidden_dim", default=12, is_static=True),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Graph-convolution regressor that propagates neighborhood signal before fitting a node-level prediction head.",
        tags=frozenset({"ml", "graph", "gnn", "frontier"}),
        citations=(
            "Kipf, T. & Welling, M. (2017). Semi-supervised classification with graph convolutional networks.",
        ),
        when_to_use="Node-level prediction where network topology carries predictive information beyond tabular covariates.",
        when_not_to_use="No meaningful graph, highly dynamic edge weights, or tasks demanding deep message-passing stacks.",
        typical_min_obs=30,
        output_interpretation="feature_importances summarize how much each input feature survives graph propagation into the prediction head.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        x = np.asarray(state["node_features"], dtype=float)
        adjacency = np.asarray(state["adjacency_matrix"], dtype=float)
        y = np.asarray(state["target"], dtype=float)
        if x.ndim != 2 or adjacency.shape != (x.shape[0], x.shape[0]) or y.shape != (x.shape[0],):
            raise ValueError(
                "graph payload must contain aligned node_features, adjacency_matrix, and target"
            )

        hidden_dim = max(4, int(params.get("hidden_dim", 12)))
        rng = np.random.default_rng(int(params.get("__seed__", 0)))
        adjacency_hat = adjacency + np.eye(adjacency.shape[0])
        degree = np.sum(adjacency_hat, axis=1)
        d_inv_sqrt = np.diag(1.0 / np.sqrt(np.maximum(degree, 1.0)))
        norm_adj = d_inv_sqrt @ adjacency_hat @ d_inv_sqrt

        w0 = rng.normal(scale=0.2, size=(x.shape[1], hidden_dim))
        hidden = np.maximum(norm_adj @ x @ w0, 0.0)
        embedding = norm_adj @ hidden
        coef, predictions = _weighted_linear_head(embedding, y, ridge=1.0e-4)
        loadings = np.mean(np.abs(norm_adj @ x), axis=0)
        loadings = loadings / max(float(np.sum(loadings)), 1.0e-12)
        feature_importances = {f"x{idx}": float(value) for idx, value in enumerate(loadings)}
        coefficients = {f"latent_{idx}": float(value) for idx, value in enumerate(coef[1:])}
        coefficients["intercept"] = float(coef[0])
        embedding_fidelity_certificate = maybe_compute_embedding_fidelity_certificate(
            state,
            params=params,
            embedding=embedding,
            embedding_family="gcn",
        )
        return _build_prediction_result(
            method_name="graph_conv",
            predictions=predictions,
            target=y,
            feature_importances=feature_importances,
            coefficients=coefficients,
            model_info={"library": "numpy", "estimator": "GraphConvStyleRegressor"},
            embedding_fidelity_certificate=embedding_fidelity_certificate,
            metadata=_metadata_with_embedding_fidelity(
                {"hidden_dim": hidden_dim, "n_nodes": int(x.shape[0])},
                embedding_fidelity_certificate,
            ),
        )


@foundry_method(
    namespace="ml.self_supervised",
    version="1.0.0",
    tags={"ml", "self-supervised", "representation-learning", "frontier"},
)
class MaskedAutoencoderEmbeddingEstimator:
    """Masked self-supervised tabular encoder that returns stable latent representations."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="masked_autoencoder",
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
            }
        ),
        output_slots=_embedding_output_slots(),
        parameters=(
            ParameterSpec("latent_dim", default=6, is_static=True),
            ParameterSpec("mask_fraction", default=0.25),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Masked self-supervised encoder for tabular representation learning with reconstruction diagnostics.",
        tags=frozenset({"ml", "self-supervised", "representation-learning", "frontier"}),
        citations=("He, K. et al. (2022). Masked autoencoders are scalable vision learners.",),
        when_to_use="Need reusable latent features before downstream supervised fine-tuning or when labels are sparse but covariates are plentiful.",
        when_not_to_use="Task is already label-rich and direct supervised regression is simpler, or features are purely categorical without preprocessing.",
        typical_min_obs=50,
        output_interpretation="transformed contains latent embeddings; reconstruction_rmse and augmentation_similarity describe whether the self-supervised representation remained stable under masking.",
    )

    @staticmethod
    def pure_step(
        state: TabularData | Mapping[str, Any], params: Mapping[str, Any]
    ) -> dict[str, Any]:
        payload = _tabular_payload(state)
        data = TabularData.model_validate(payload)
        x, _, _ = _normalize_features(np.asarray(data.features, dtype=float))
        latent_dim = max(2, min(int(params.get("latent_dim", 6)), x.shape[1]))
        mask_fraction = min(max(float(params.get("mask_fraction", 0.25)), 0.05), 0.8)
        rng = np.random.default_rng(int(params.get("__seed__", 0)))

        mask = rng.uniform(size=x.shape) > mask_fraction
        masked = x * mask
        u, s, vt = np.linalg.svd(masked, full_matrices=False)
        transformed = u[:, :latent_dim] * s[:latent_dim]
        reconstructed = transformed @ vt[:latent_dim, :]
        reconstruction_rmse = float(np.sqrt(np.mean((masked - reconstructed) ** 2)))

        noise = rng.normal(scale=0.05, size=x.shape)
        alt_masked = (x + noise) * (rng.uniform(size=x.shape) > mask_fraction)
        alt_u, alt_s, _ = np.linalg.svd(alt_masked, full_matrices=False)
        alt_transformed = alt_u[:, :latent_dim] * alt_s[:latent_dim]
        similarity = float(
            np.mean(
                np.sum(transformed * alt_transformed, axis=1)
                / (
                    np.linalg.norm(transformed, axis=1) * np.linalg.norm(alt_transformed, axis=1)
                    + 1.0e-12
                )
            )
        )
        embedding_fidelity_certificate = maybe_compute_embedding_fidelity_certificate(
            payload,
            params=params,
            embedding=transformed,
            embedding_family="masked_autoencoder",
        )

        return {
            "result": EmbeddingResult(
                method_name="masked_autoencoder",
                transformed=transformed,
                components=vt[:latent_dim, :],
                explained_variance_ratio=[
                    float(value / max(float(np.sum(s**2)), 1.0e-12))
                    for value in (s[:latent_dim] ** 2)
                ],
                embedding_fidelity_certificate=embedding_fidelity_certificate,
                metadata=_metadata_with_embedding_fidelity(
                    {
                        "reconstruction_rmse": reconstruction_rmse,
                        "augmentation_similarity": similarity,
                        "mask_fraction": mask_fraction,
                    },
                    embedding_fidelity_certificate,
                ),
            )
        }


__all__ = [
    "FTTransformerEstimator",
    "GraphNeuralNetworkEstimator",
    "MaskedAutoencoderEmbeddingEstimator",
    "TabNetEstimator",
]
