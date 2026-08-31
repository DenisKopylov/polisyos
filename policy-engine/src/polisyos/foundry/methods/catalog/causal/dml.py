"""Public causal dml module API."""

from __future__ import annotations

import inspect
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
from polisyos.foundry.methods.catalog.causal._common import (
    build_failure_report,
    build_success_report,
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal._econml_adapter import (
    build_cate_quantile_subgroups,
    build_hte_data,
    extract_cate_from_estimator,
    require_econml,
)
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.ir.analytics.causal import CausalMethod, EstimationStatus
from polisyos.ir.analytics.hte import FeatureImportance, HTEResult, SubgroupEffect


def _supports_discrete_treatment_kwarg(cls: type) -> bool:
    try:
        return "discrete_treatment" in inspect.signature(cls).parameters
    except (TypeError, ValueError):
        return False


@foundry_method(
    namespace="causal.hte",
    version="1.0.0",
    tags={"causal", "hte", "double-ml"},
)
class DoubleMachineLearning:
    """Double / Debiased ML for CATE via EconML."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="double_ml",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="hte_data",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("observations", "rows"),
                    shape=("n_obs", "n_features"),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="causal_effect_report",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("report", "json"),
                ),
                SlotSpec(
                    name="hte_result",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("report", "json"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="model_type", default="linear"),
            ParameterSpec(name="model_y", default="auto"),
            ParameterSpec(name="model_t", default="auto"),
            ParameterSpec(name="cv_folds", default=3),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="subgroup_quantiles", default=4),
            ParameterSpec(name="feature_importance_method", default="tree_based"),
            ParameterSpec(name="random_state", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Double / Debiased Machine Learning with cross-fitting.",
        tags=frozenset({"causal", "hte", "double-ml"}),
        citations=(
            "Chernozhukov, V., et al. (2018). Double/Debiased Machine Learning "
            "for Treatment and Structural Parameters.",
        ),
        equations={
            "residualization": "Y_res = Y - E[Y|W], T_res = T - E[T|W]",
            "cate": "tau(X) estimated from orthogonalized moments",
        },
        assumptions={
            "unconfoundedness": "No unobserved confounders conditional on observed variables.",
            "overlap": "Propensity score bounded away from 0 and 1.",
        },
        when_to_use="High-dimensional controls; partially linear model with continuous or binary treatment; want Neyman-orthogonal ATE",
        when_not_to_use="Low-dimensional setting where OLS suffices; no nuisance functions to partial out; discrete choice model",
        prerequisites=(),
        diagnostic_checks=("causal.sensitivity.sensemakr@1.0.0",),
        typical_min_obs=200,
        output_interpretation="Theta: ATE/LATE from partialling-out Neyman-orthogonal moments. Asymptotically normal with cross-fitting.",
    )

    @staticmethod
    def pure_step(state: HTEObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            require_econml()
            from econml.dml import KernelDML, LinearDML, SparseLinearDML
        except Exception as exc:
            report = build_failure_report(
                method=CausalMethod.DOUBLE_ML,
                status=EstimationStatus.NUMERICAL_FAILURE,
                reason=f"Double ML backend unavailable: {exc}",
                estimand="ATE_from_CATE",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(DoubleMachineLearning.metadata.assumptions),
            )
            return wrap_causal_output(
                report,
                warnings=[report.status_reason or "backend unavailable"],
            )

        data = build_hte_data(state)
        alpha = 1.0 - float(params.get("confidence_level", 0.95))
        seed = params.get("random_state")
        if seed is None:
            seed = params.get("__seed__", 0)
        seed_int = int(seed)
        rng = np.random.default_rng(seed_int)

        model_type = str(params.get("model_type", "linear")).lower()
        if model_type == "sparse":
            cls = SparseLinearDML
        elif model_type == "kernel":
            cls = KernelDML
        else:
            cls = LinearDML

        model_kwargs: dict[str, Any] = {
            "cv": int(params.get("cv_folds", 3)),
            "model_y": params.get("model_y", "auto"),
            "model_t": params.get("model_t", "auto"),
        }
        if _supports_discrete_treatment_kwarg(cls):
            model_kwargs["discrete_treatment"] = True
        if cls is not KernelDML:
            model_kwargs["random_state"] = seed_int
        model = cls(**model_kwargs)
        model.fit(data.y, data.t, X=data.x, W=data.w)

        extracted = extract_cate_from_estimator(
            model,
            data.x,
            alpha=alpha,
            feature_names=data.feature_names,
            feature_importance_method=str(params.get("feature_importance_method", "tree_based")),
            rng=rng,
        )
        subgroup_payloads = build_cate_quantile_subgroups(
            cate_values=extracted["cate_values"],
            n_quantiles=int(params.get("subgroup_quantiles", 4)),
            alpha=alpha,
        )

        estimator_fqn = (
            "econml.dml.SparseLinearDML"
            if cls is SparseLinearDML
            else "econml.dml.KernelDML"
            if cls is KernelDML
            else "econml.dml.LinearDML"
        )
        hte_result = HTEResult(
            method=CausalMethod.DOUBLE_ML,
            ate=extracted["ate"],
            ate_ci_lower=extracted["ate_ci_lower"],
            ate_ci_upper=extracted["ate_ci_upper"],
            ate_p_value=extracted["ate_p_value"],
            confidence_level=float(params.get("confidence_level", 0.95)),
            cate_values=extracted["cate_values"],
            cate_std_values=extracted["cate_std_values"],
            cate_ci_lower_values=extracted["cate_ci_lower_values"],
            cate_ci_upper_values=extracted["cate_ci_upper_values"],
            subgroup_effects=[SubgroupEffect.model_validate(item) for item in subgroup_payloads],
            feature_importances=[
                FeatureImportance.model_validate(item) for item in extracted["feature_importances"]
            ],
            n_samples=int(data.y.shape[0]),
            n_treated=int(np.sum(data.t == 1)),
            n_control=int(np.sum(data.t == 0)),
            n_features=int(data.x.shape[1]),
            feature_names=list(data.feature_names),
            econml_estimator_class=estimator_fqn,
            econml_params={
                "model_type": model_type,
                "cv_folds": int(params.get("cv_folds", 3)),
            },
            feature_display_map={name: name for name in data.feature_names},
            metadata={
                "warnings": list(extracted["warnings"]),
                "confounder_names": list(data.confounder_names),
            },
        )

        report = build_success_report(
            method=CausalMethod.DOUBLE_ML,
            estimand="ATE_from_CATE",
            point_estimate=extracted["ate"],
            confidence_interval=(extracted["ate_ci_lower"], extracted["ate_ci_upper"]),
            confidence_level=float(params.get("confidence_level", 0.95)),
            p_value=extracted["ate_p_value"],
            inference_method="double_ml",
            sample_size=int(data.y.shape[0]),
            n_treated=int(np.sum(data.t == 1)),
            n_control=int(np.sum(data.t == 0)),
            pre_periods=0,
            post_periods=0,
            assumptions=dict(DoubleMachineLearning.metadata.assumptions),
            method_params={
                "model_type": model_type,
                "feature_importance_method": str(
                    params.get("feature_importance_method", "tree_based")
                ),
            },
            metadata={
                "hte_result_present": True,
                "n_features": int(data.x.shape[1]),
            },
        )

        return wrap_causal_output(
            report,
            warnings=list(extracted["warnings"]),
            extras={"hte_result": hte_result},
        )


__all__ = ["DoubleMachineLearning"]
