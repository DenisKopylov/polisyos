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


@foundry_method(
    namespace="causal.hte",
    version="1.0.0",
    tags={"causal", "hte", "causal-forest", "cate"},
)
class CausalForestEstimator:
    """Causal Forest via EconML CausalForestDML."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="causal_forest",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="hte_data",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("observations", "rows"),
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
            ParameterSpec(name="n_estimators", default=500),
            ParameterSpec(name="max_depth", default=None),
            ParameterSpec(name="min_samples_leaf", default=5),
            ParameterSpec(name="max_samples", default=0.5),
            ParameterSpec(name="honest", default=True),
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
        description=(
            "Causal Forest (Generalized Random Forest) for heterogeneous treatment effects."
        ),
        tags=frozenset({"causal", "hte", "causal-forest"}),
        citations=(
            "Wager, S., & Athey, S. (2018). Estimation and Inference of Heterogeneous "
            "Treatment Effects using Random Forests.",
            "Athey, S., Tibshirani, J., & Wager, S. (2019). Generalized Random Forests.",
        ),
        equations={
            "cate": "tau(x) = E[Y(1) - Y(0) | X = x]",
            "ate": "ATE = E[tau(X)]",
        },
        assumptions={
            "unconfoundedness": "No unobserved confounders conditional on observed covariates.",
            "overlap": "0 < P(T=1|X) < 1 across support.",
            "consistency": "Observed outcome equals potential outcome under observed treatment.",
        },
    )

    @staticmethod
    def pure_step(state: HTEObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            require_econml()
            from econml.dml import CausalForestDML
        except Exception as exc:
            report = build_failure_report(
                method=CausalMethod.CAUSAL_FOREST,
                status=EstimationStatus.NUMERICAL_FAILURE,
                reason=f"Causal forest backend unavailable: {exc}",
                estimand="ATE_from_CATE",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(CausalForestEstimator.metadata.assumptions),
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

        model = CausalForestDML(
            n_estimators=int(params.get("n_estimators", 500)),
            max_depth=params.get("max_depth"),
            min_samples_leaf=int(params.get("min_samples_leaf", 5)),
            max_samples=float(params.get("max_samples", 0.5)),
            honest=bool(params.get("honest", True)),
            cv=int(params.get("cv_folds", 3)),
            random_state=seed_int,
        )
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

        hte_result = HTEResult(
            method=CausalMethod.CAUSAL_FOREST,
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
            econml_estimator_class="econml.dml.CausalForestDML",
            econml_params={
                "n_estimators": int(params.get("n_estimators", 500)),
                "max_depth": params.get("max_depth"),
                "min_samples_leaf": int(params.get("min_samples_leaf", 5)),
                "max_samples": float(params.get("max_samples", 0.5)),
                "honest": bool(params.get("honest", True)),
                "cv_folds": int(params.get("cv_folds", 3)),
            },
            feature_display_map={name: name for name in data.feature_names},
            metadata={
                "warnings": list(extracted["warnings"]),
                "confounder_names": list(data.confounder_names),
            },
        )

        report = build_success_report(
            method=CausalMethod.CAUSAL_FOREST,
            estimand="ATE_from_CATE",
            point_estimate=extracted["ate"],
            confidence_interval=(extracted["ate_ci_lower"], extracted["ate_ci_upper"]),
            confidence_level=float(params.get("confidence_level", 0.95)),
            p_value=extracted["ate_p_value"],
            inference_method="causal_forest_dml",
            sample_size=int(data.y.shape[0]),
            n_treated=int(np.sum(data.t == 1)),
            n_control=int(np.sum(data.t == 0)),
            pre_periods=0,
            post_periods=0,
            assumptions=dict(CausalForestEstimator.metadata.assumptions),
            method_params={
                "n_estimators": int(params.get("n_estimators", 500)),
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


__all__ = ["CausalForestEstimator"]
