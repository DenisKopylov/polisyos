"""Encode tabular records with transformer-style feature representations."""

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

from .protocols import TabularData
from .regression import (
    _build_prediction_result,
    _feature_names,
    _prediction_output_slots,
    _tabular_payload,
)


def _init_transformer_params(
    rng: np.random.Generator,
    *,
    n_features: int,
    d_model: int,
) -> dict[str, Any]:
    feature_scale = rng.normal(scale=0.15, size=(n_features, d_model))
    feature_bias = rng.normal(scale=0.05, size=(n_features, d_model))
    feature_embed = rng.normal(scale=0.08, size=(n_features, d_model))
    q_proj = rng.normal(scale=1.0 / math.sqrt(max(d_model, 1)), size=(d_model, d_model))
    k_proj = rng.normal(scale=1.0 / math.sqrt(max(d_model, 1)), size=(d_model, d_model))
    v_proj = rng.normal(scale=1.0 / math.sqrt(max(d_model, 1)), size=(d_model, d_model))
    return {
        "feature_scale": feature_scale,
        "feature_bias": feature_bias,
        "feature_embed": feature_embed,
        "q_proj": q_proj,
        "k_proj": k_proj,
        "v_proj": v_proj,
    }


def _forward_transformer(params: Mapping[str, Any], x: Any) -> tuple[Any, Any]:
    tokens = (
        x[:, :, None] * params["feature_scale"][None, :, :]
        + params["feature_bias"][None, :, :]
        + params["feature_embed"][None, :, :]
    )
    q = np.einsum("bfd,dh->bfh", tokens, params["q_proj"])
    k = np.einsum("bfd,dh->bfh", tokens, params["k_proj"])
    v = np.einsum("bfd,dh->bfh", tokens, params["v_proj"])
    scores = np.einsum("bqh,bkh->bqk", q, k) / math.sqrt(max(q.shape[-1], 1))
    scores = scores - np.max(scores, axis=-1, keepdims=True)
    attention = np.exp(scores)
    attention = attention / np.maximum(np.sum(attention, axis=-1, keepdims=True), 1e-12)
    context = np.einsum("bqk,bkh->bqh", attention, v)
    pooled = np.mean(context + tokens, axis=1)
    return pooled, attention


def _attention_importance(attention: np.ndarray, feature_names: list[str]) -> dict[str, float]:
    scores = np.asarray(attention, dtype=float)
    importances = np.mean(scores, axis=(0, 1))
    total = float(np.sum(importances))
    if total > 1e-12:
        importances = importances / total
    return {name: float(value) for name, value in zip(feature_names, importances)}


@foundry_method(
    namespace="ml.deep",
    version="1.0.0",
    tags={"ml", "tabular-transformer", "heuristic", "random_feature", "attention"},
)
class TabularTransformerEstimator:
    """Use a frozen attention-style encoder plus ridge head as a fast tabular baseline."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scikit-learn")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="tabular_transformer",
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
            ParameterSpec(name="d_model", default=16, is_static=True),
            ParameterSpec(name="ridge_alpha", default=1.0),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Random-feature transformer-style tabular regressor using a frozen self-attention "
            "encoder with a ridge head."
        ),
        tags=frozenset({"ml", "tabular-transformer", "heuristic", "random_feature", "attention"}),
        when_to_use=(
            "Need a fast attention-shaped tabular baseline with richer interactions than linear models, "
            "without claiming full trainable transformer depth."
        ),
        citations=(
            "Vaswani, A. et al. (2017). Attention is all you need. NeurIPS, 30.",
            "Gorishniy, Y. et al. (2021). Revisiting deep learning models for tabular data. NeurIPS, 34.",
        ),
        when_not_to_use=(
            "Need a fully trainable transformer; need production-grade deep learning capacity; "
            "very small datasets (<50 obs) where even this baseline will be unstable."
        ),
        output_interpretation=(
            "Regression predictions from a ridge head fit on frozen attention-style features. "
            "Attention weights are heuristic diagnostics, not causal explanations."
        ),
        typical_min_obs=50,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TabularData:
        payload = _tabular_payload(fallback_state)
        payload.update(bound_inputs)
        return TabularData.model_validate(payload)

    @staticmethod
    def pure_step(state: TabularData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, TabularData) else TabularData.model_validate(state)
        x_raw = np.asarray(data.features, dtype=float)
        y_raw = np.asarray(data.target, dtype=float)
        x_mean = np.mean(x_raw, axis=0, keepdims=True)
        x_std = np.std(x_raw, axis=0, keepdims=True)
        x_std = np.where(x_std > 1e-6, x_std, 1.0)
        x = (x_raw - x_mean) / x_std
        d_model = max(8, int(params.get("d_model", 16)))
        ridge_alpha = max(1e-6, float(params.get("ridge_alpha", 1.0)))
        rng = np.random.default_rng(int(params.get("__seed__", 0)))
        encoder_params = _init_transformer_params(
            rng,
            n_features=x.shape[1],
            d_model=d_model,
        )
        encoded, attention = _forward_transformer(encoder_params, x)
        fit_kwargs: dict[str, Any] = {}
        if data.sample_weight is not None:
            fit_kwargs["sample_weight"] = np.asarray(data.sample_weight, dtype=float)
        from sklearn.linear_model import Ridge

        head = Ridge(alpha=ridge_alpha)
        head.fit(encoded, y_raw, **fit_kwargs)
        predictions = np.asarray(head.predict(encoded), dtype=float)
        feature_importances = _attention_importance(
            np.asarray(attention, dtype=float), _feature_names(data)
        )
        coefficients = {
            f"latent_{idx}": float(value)
            for idx, value in enumerate(np.asarray(head.coef_, dtype=float))
        }
        coefficients["intercept"] = float(head.intercept_)
        return _build_prediction_result(
            method_name="tabular_transformer",
            predictions=predictions,
            target=y_raw,
            feature_importances=feature_importances,
            coefficients=coefficients,
            model_info={"library": "numpy", "estimator": "TabularTransformerStyleEncoder"},
            metadata={
                "d_model": d_model,
                "ridge_alpha": ridge_alpha,
                "encoder": "self_attention_random_features",
            },
        )
