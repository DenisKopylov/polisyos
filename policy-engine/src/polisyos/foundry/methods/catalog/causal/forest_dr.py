"""Public causal forest dr module API."""

from __future__ import annotations

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


@foundry_method(
    namespace="causal.hte",
    version="1.0.0",
    tags={"causal", "hte", "forest-dr", "doubly-robust"},
)
class ForestDRLearnerEstimator:
    """ForestDRLearner wrapper for robust heterogeneous treatment effects."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="forest_dr",
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
            ParameterSpec(name="n_estimators", default=500),
            ParameterSpec(name="min_samples_leaf", default=5),
            ParameterSpec(name="max_depth", default=None),
            ParameterSpec(name="max_samples", default=0.45),
            ParameterSpec(name="honest", default=True),
            ParameterSpec(name="subforest_size", default=4),
            ParameterSpec(name="min_propensity", default=1e-3),
            ParameterSpec(name="cv_folds", default=3),
            ParameterSpec(name="mc_iters", default=1),
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
        description="Doubly-robust forest learner for CATE estimation via EconML ForestDRLearner.",
        tags=frozenset({"causal", "hte", "forest-dr", "doubly-robust"}),
        citations=(
            "Oprescu, M., Syrgkanis, V., Wu, Z.S. (2019). Orthogonal Random Forest for Causal Inference.",
            "Athey, S., Tibshirani, J., Wager, S. (2019). Generalized Random Forests.",
        ),
        equations={
            "cate": "tau(x) = E[Y(1) - Y(0) | X = x]",
            "dr": "Orthogonal moments combine outcome and propensity nuisance fits.",
        },
        assumptions={
            "unconfoundedness": "No unobserved confounders conditional on observed covariates.",
            "overlap": "Treatment propensity is bounded away from 0 and 1.",
            "consistency": "Observed outcome equals the corresponding potential outcome.",
        },
        when_to_use="Robust heterogeneous treatment effects on observational data with nonlinear confounding.",
        when_not_to_use="Very small samples (<150) or when only an average effect is needed.",
        typical_min_obs=200,
        output_interpretation="CATE estimates with forest-based doubly-robust orthogonalization; mean CATE approximates ATE.",
    )

    @staticmethod
    def pure_step(
        state: HTEObservationalData | Mapping[str, Any], params: Mapping[str, Any]
    ) -> dict[str, Any]:
        try:
            require_econml()
            from econml.dr import ForestDRLearner
        except Exception as exc:
            report = build_failure_report(
                method=CausalMethod.FOREST_DR,
                status=EstimationStatus.NUMERICAL_FAILURE,
                reason=f"ForestDR backend unavailable: {exc}",
                estimand="ATE_from_CATE",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(ForestDRLearnerEstimator.metadata.assumptions),
            )
            return wrap_causal_output(
                report, warnings=[report.status_reason or "backend unavailable"]
            )

        data = build_hte_data(state)
        alpha = 1.0 - float(params.get("confidence_level", 0.95))
        seed = params.get("random_state")
        if seed is None:
            seed = params.get("__seed__", 0)
        seed_int = int(seed)
        rng = np.random.default_rng(seed_int)

        model = ForestDRLearner(
            n_estimators=int(params.get("n_estimators", 500)),
            min_samples_leaf=int(params.get("min_samples_leaf", 5)),
            max_depth=params.get("max_depth"),
            max_samples=float(params.get("max_samples", 0.45)),
            honest=bool(params.get("honest", True)),
            subforest_size=int(params.get("subforest_size", 4)),
            min_propensity=float(params.get("min_propensity", 1e-3)),
            cv=int(params.get("cv_folds", 3)),
            mc_iters=int(params.get("mc_iters", 1)),
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
            method=CausalMethod.FOREST_DR,
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
            econml_estimator_class="econml.dr.ForestDRLearner",
            econml_params={
                "n_estimators": int(params.get("n_estimators", 500)),
                "min_samples_leaf": int(params.get("min_samples_leaf", 5)),
                "max_depth": params.get("max_depth"),
                "max_samples": float(params.get("max_samples", 0.45)),
                "honest": bool(params.get("honest", True)),
                "subforest_size": int(params.get("subforest_size", 4)),
                "min_propensity": float(params.get("min_propensity", 1e-3)),
                "cv_folds": int(params.get("cv_folds", 3)),
                "mc_iters": int(params.get("mc_iters", 1)),
            },
            feature_display_map={name: name for name in data.feature_names},
            metadata={
                "warnings": list(extracted["warnings"]),
                "confounder_names": list(data.confounder_names),
            },
        )

        report = build_success_report(
            method=CausalMethod.FOREST_DR,
            estimand="ATE_from_CATE",
            point_estimate=extracted["ate"],
            confidence_interval=(extracted["ate_ci_lower"], extracted["ate_ci_upper"]),
            confidence_level=float(params.get("confidence_level", 0.95)),
            p_value=extracted["ate_p_value"],
            inference_method="forest_dr",
            sample_size=int(data.y.shape[0]),
            n_treated=int(np.sum(data.t == 1)),
            n_control=int(np.sum(data.t == 0)),
            pre_periods=0,
            post_periods=0,
            assumptions=dict(ForestDRLearnerEstimator.metadata.assumptions),
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


__all__ = ["ForestDRLearnerEstimator"]
