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
from polisyos.ir.causal import CausalMethod, EstimationStatus
from polisyos.ir.hte import FeatureImportance, HTEResult, SubgroupEffect


def _make_base_model(name: str, seed: int):
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import LassoCV

    key = name.lower()
    if key == "random_forest":
        return RandomForestRegressor(n_estimators=200, random_state=seed)
    if key == "linear":
        return LassoCV(cv=3, random_state=seed)
    return GradientBoostingRegressor(n_estimators=200, random_state=seed)


def _build_learner(
    learner_type: str,
    base_model: Any,
) -> tuple[Any, CausalMethod, str]:
    from econml.metalearners import SLearner, TLearner, XLearner

    kind = learner_type.lower()
    if kind == "s":
        try:
            return (
                SLearner(overall_model=base_model),
                CausalMethod.S_LEARNER,
                "econml.metalearners.SLearner",
            )
        except TypeError:
            return (
                SLearner(model=base_model),
                CausalMethod.S_LEARNER,
                "econml.metalearners.SLearner",
            )
    if kind == "t":
        try:
            return (
                TLearner(models=base_model),
                CausalMethod.T_LEARNER,
                "econml.metalearners.TLearner",
            )
        except TypeError:
            return (
                TLearner(model=base_model),
                CausalMethod.T_LEARNER,
                "econml.metalearners.TLearner",
            )
    if kind == "x":
        try:
            return (
                XLearner(models=base_model),
                CausalMethod.X_LEARNER,
                "econml.metalearners.XLearner",
            )
        except TypeError:
            return (
                XLearner(model=base_model),
                CausalMethod.X_LEARNER,
                "econml.metalearners.XLearner",
            )
    raise ValueError(f"Unknown learner_type={learner_type!r}; expected one of: s, t, x")


@foundry_method(
    namespace="causal.hte",
    version="1.0.0",
    tags={"causal", "hte", "meta-learner"},
)
class MetaLearnerEstimator:
    """Meta-learners (S/T/X) for CATE estimation via EconML."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="meta_learner",
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
            ParameterSpec(name="learner_type", default="x"),
            ParameterSpec(name="base_model", default="auto"),
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
        description="Meta-learner family (S/T/X) for heterogeneous treatment effects.",
        tags=frozenset({"causal", "hte", "meta-learner"}),
        citations=(
            "Künzel, S.R., et al. (2019). Metalearners for estimating heterogeneous "
            "treatment effects using machine learning.",
        ),
        equations={
            "s_learner": "tau(x) = mu(x, 1) - mu(x, 0)",
            "t_learner": "tau(x) = mu_1(x) - mu_0(x)",
            "x_learner": "tau(x) = g(x) * tau_1(x) + (1 - g(x)) * tau_0(x)",
        },
        assumptions={
            "unconfoundedness": "No unobserved confounders conditional on observed variables.",
            "overlap": "Positive probability of treatment/control across covariate support.",
        },
    )

    @staticmethod
    def pure_step(state: HTEObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            require_econml()
        except Exception as exc:
            report = build_failure_report(
                method=CausalMethod.X_LEARNER,
                status=EstimationStatus.NUMERICAL_FAILURE,
                reason=f"Meta-learner backend unavailable: {exc}",
                estimand="ATE_from_CATE",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(MetaLearnerEstimator.metadata.assumptions),
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

        learner_type = str(params.get("learner_type", "x")).lower()
        base_model_name = str(params.get("base_model", "auto"))
        base_model = _make_base_model(base_model_name, seed_int)
        model, method_enum, estimator_fqn = _build_learner(learner_type, base_model)
        model.fit(data.y, data.t, X=data.x)

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
            method=method_enum,
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
                "learner_type": learner_type,
                "base_model": base_model_name,
            },
            feature_display_map={name: name for name in data.feature_names},
            metadata={"warnings": list(extracted["warnings"])},
        )

        report = build_success_report(
            method=method_enum,
            estimand="ATE_from_CATE",
            point_estimate=extracted["ate"],
            confidence_interval=(extracted["ate_ci_lower"], extracted["ate_ci_upper"]),
            confidence_level=float(params.get("confidence_level", 0.95)),
            p_value=extracted["ate_p_value"],
            inference_method=f"meta_learner_{learner_type}",
            sample_size=int(data.y.shape[0]),
            n_treated=int(np.sum(data.t == 1)),
            n_control=int(np.sum(data.t == 0)),
            pre_periods=0,
            post_periods=0,
            assumptions=dict(MetaLearnerEstimator.metadata.assumptions),
            method_params={
                "learner_type": learner_type,
                "base_model": base_model_name,
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


__all__ = ["MetaLearnerEstimator"]
