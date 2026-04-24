"""Learn budget-constrained treatment assignment rules from estimated CATEs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np

from polisyos.common.logger import get_logger
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
    build_hte_data,
    require_econml,
)
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.foundry.methods.catalog.causal.strategic import evaluate_strategic_hook
from polisyos.ir.analytics.causal import CausalMethod, EstimationStatus
from polisyos.ir.analytics.hte import PolicyRecommendation, TargetingRule

logger = get_logger(__name__)


def _extract_policy_tree_rules(
    policy_tree: Any,
    *,
    x: np.ndarray,
    feature_names: list[str],
    cost_per_unit: float,
    cate_values: np.ndarray,
    treatment_decisions: np.ndarray,
) -> list[TargetingRule]:
    if not hasattr(policy_tree, "tree_"):
        selected = np.where(treatment_decisions == 1)[0]
        if selected.size == 0:
            return []
        return [
            TargetingRule(
                rule_id="ranked_uplift_1",
                predicate=f"predicted_policy=1 AND cate_rank<= {selected.size}",
                predicate_human="Target units with highest predicted uplift",
                priority=1,
                expected_cate=float(np.mean(cate_values[selected])),
                expected_cost_per_unit=float(cost_per_unit),
                n_eligible_units=int(selected.size),
                cumulative_budget_share=1.0,
            )
        ]

    tree = policy_tree.tree_
    left = tree.children_left
    right = tree.children_right
    features = tree.feature
    thresholds = tree.threshold
    values = tree.value
    try:
        leaf_ids = np.asarray(policy_tree.apply(x), dtype=int).ravel()
    except Exception as exc:
        logger.debug(
            "PolicyTree.apply failed, using fallback leaf_ids: %s",
            exc,
        )
        leaf_ids = np.full(shape=(x.shape[0],), fill_value=-1, dtype=int)

    rules: list[TargetingRule] = []
    stack: list[tuple[int, list[str]]] = [(0, [])]
    total_targeted = max(int(np.sum(treatment_decisions == 1)), 1)
    emitted = 0
    targeted_cumulative = 0
    while stack:
        node_idx, conds = stack.pop()
        is_leaf = left[node_idx] == right[node_idx]
        if is_leaf:
            leaf_val = float(np.asarray(values[node_idx]).ravel()[0])
            if leaf_val <= 0:
                continue
            leaf_selected = (leaf_ids == node_idx) & (treatment_decisions == 1)
            n_eligible = int(np.sum(leaf_selected))
            if n_eligible == 0:
                continue
            emitted += 1
            targeted_cumulative += n_eligible
            expected_cate = float(np.mean(cate_values[leaf_selected]))
            rules.append(
                TargetingRule(
                    rule_id=f"tree_leaf_{emitted}",
                    predicate=" AND ".join(conds) if conds else "TRUE",
                    predicate_human=" and ".join(conds).replace("<=", "below").replace(">", "above")
                    if conds
                    else "All units",
                    priority=emitted,
                    expected_cate=expected_cate,
                    expected_cost_per_unit=float(cost_per_unit),
                    n_eligible_units=n_eligible,
                    cumulative_budget_share=min(1.0, targeted_cumulative / total_targeted),
                )
            )
            continue

        feat_idx = int(features[node_idx])
        feat_name = (
            feature_names[feat_idx] if 0 <= feat_idx < len(feature_names) else f"x{feat_idx}"
        )
        thr = float(thresholds[node_idx])
        stack.append((right[node_idx], [*conds, f"{feat_name} > {thr:.6g}"]))
        stack.append((left[node_idx], [*conds, f"{feat_name} <= {thr:.6g}"]))
    return rules


@foundry_method(
    namespace="causal.targeting",
    version="1.0.0",
    tags={"causal", "policy-learning", "targeting"},
)
class OptimalPolicyLearner:
    """Learn a targeting rule under overlap and budget constraints from CATE estimates.

    Use this method when observational CATEs are credible and policy actions
    can be encoded as a binary allocation rule. Avoid it when overlap is weak,
    algorithmic targeting is prohibited, or treated sample size is too small
    for a stable first-stage CATE fit.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="policy_tree",
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
                    name="policy_recommendation",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("report", "json"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="max_depth", default=3),
            ParameterSpec(name="min_samples_leaf", default=50),
            ParameterSpec(name="budget_fraction", default=1.0),
            ParameterSpec(name="cost_per_unit", default=1.0),
            ParameterSpec(name="cate_n_estimators", default=300),
            ParameterSpec(name="confidence_level", default=0.95),
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
        description="Policy learning with CATE estimation and budget-constrained targeting.",
        tags=frozenset({"causal", "policy-learning", "targeting"}),
        citations=("Athey, S., & Wager, S. (2021). Policy Learning with Observational Data.",),
        equations={
            "value": "V(pi) = E[tau(X) * pi(X)] - E[c(X) * pi(X)]",
            "constraint": "E[c(X) * pi(X)] <= B",
        },
        assumptions={
            "valid_cate": "First-stage CATE estimates are informative and consistent.",
            "overlap": "Positivity of treatment assignment over covariate support.",
            "budget_constraint": "Cost-per-unit estimate is stable for target allocation.",
        },
        when_to_use="Learn optimal treatment assignment rule from data to maximize expected welfare",
        when_not_to_use="Ethical constraints disallow algorithmic treatment assignment; very small treated sample",
        typical_min_obs=200,
        output_interpretation="Decision rule/tree assigning treatment based on covariates. Policy value = E[Y(d(X))] under learned policy.",
    )

    @staticmethod
    def pure_step(state: HTEObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            require_econml()
            from econml.dml import CausalForestDML
            from econml.policy import PolicyTree

        except Exception as exc:
            report = build_failure_report(
                method=CausalMethod.POLICY_TREE,
                status=EstimationStatus.NUMERICAL_FAILURE,
                reason=f"Policy learner backend unavailable: {exc}",
                estimand="Optimal_Policy_Value",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(OptimalPolicyLearner.metadata.assumptions),
            )
            return wrap_causal_output(
                report,
                warnings=[report.status_reason or "backend unavailable"],
            )

        data = build_hte_data(state)
        seed = params.get("random_state")
        if seed is None:
            seed = params.get("__seed__", 0)
        seed_int = int(seed)

        cate_model = CausalForestDML(
            n_estimators=int(params.get("cate_n_estimators", 300)),
            cv=3,
            random_state=seed_int,
        )
        cate_model.fit(data.y, data.t, X=data.x, W=data.w)
        cate_estimates = np.asarray(cate_model.effect(data.x), dtype=float).ravel()

        budget_fraction = float(params.get("budget_fraction", 1.0))
        budget_fraction = float(np.clip(budget_fraction, 0.0, 1.0))
        cost_per_unit = float(params.get("cost_per_unit", 1.0))
        n_budget = int(np.floor(budget_fraction * data.y.shape[0]))
        n_budget = max(0, min(n_budget, int(data.y.shape[0])))

        warnings: list[str] = []
        policy_tree = PolicyTree(
            max_depth=int(params.get("max_depth", 3)),
            min_samples_leaf=int(params.get("min_samples_leaf", 50)),
            random_state=seed_int,
        )
        try:
            policy_tree.fit(data.x, cate_estimates)
            raw_decisions = np.asarray(policy_tree.predict(data.x), dtype=int).ravel()
        except Exception as exc:
            warnings.append(
                f"PolicyTree fit failed ({type(exc).__name__}); using uplift ranking fallback"
            )
            raw_decisions = np.ones_like(cate_estimates, dtype=int)

        treatment_decisions = np.zeros_like(raw_decisions, dtype=int)
        if n_budget > 0:
            candidates = np.where((raw_decisions == 1) & (cate_estimates > 0))[0]
            if candidates.size == 0:
                candidates = np.where(cate_estimates > 0)[0]
            if candidates.size > n_budget:
                top_idx = candidates[np.argsort(-cate_estimates[candidates])[:n_budget]]
            else:
                top_idx = candidates
                if top_idx.size < n_budget:
                    remaining = np.setdiff1d(np.arange(cate_estimates.shape[0]), top_idx)
                    if remaining.size > 0:
                        fill = remaining[
                            np.argsort(-cate_estimates[remaining])[: n_budget - top_idx.size]
                        ]
                        top_idx = np.concatenate([top_idx, fill])
            treatment_decisions[top_idx] = 1

        feature_names = list(data.feature_names)
        rules = _extract_policy_tree_rules(
            policy_tree,
            x=data.x,
            feature_names=feature_names,
            cost_per_unit=cost_per_unit,
            cate_values=cate_estimates,
            treatment_decisions=treatment_decisions,
        )
        if not rules and int(np.sum(treatment_decisions == 1)) > 0:
            selected = np.where(treatment_decisions == 1)[0]
            rules = [
                TargetingRule(
                    rule_id="ranked_uplift_1",
                    predicate=f"top {selected.size} by estimated CATE",
                    predicate_human="Target highest-uplift units within budget",
                    priority=1,
                    expected_cate=float(np.mean(cate_estimates[selected])),
                    expected_cost_per_unit=cost_per_unit,
                    n_eligible_units=int(selected.size),
                    cumulative_budget_share=1.0,
                )
            ]

        treated_mask = treatment_decisions == 1
        total_effect = float(np.sum(cate_estimates[treated_mask])) if treated_mask.any() else 0.0
        total_cost = float(np.sum(treated_mask)) * cost_per_unit
        budget_constraint = float(n_budget) * cost_per_unit

        recommendation = PolicyRecommendation(
            budget_constraint=budget_constraint,
            optimization_objective="maximize_total_effect",
            targeting_rules=rules,
            total_expected_effect=total_effect,
            total_cost=total_cost,
            n_targeted_units=int(np.sum(treated_mask)),
            n_total_units=int(data.y.shape[0]),
            targeting_efficiency=(total_effect / total_cost) if total_cost > 0 else None,
            tree_depth=int(params.get("max_depth", 3)),
            tree_n_leaves=len(rules) if rules else None,
            metadata={
                "feature_names": feature_names,
                "warnings": warnings,
            },
        )

        alpha = 1.0 - float(params.get("confidence_level", 0.95))
        ci = (
            float(np.percentile(cate_estimates, 100.0 * alpha / 2.0)),
            float(np.percentile(cate_estimates, 100.0 * (1.0 - alpha / 2.0))),
        )
        report = build_success_report(
            method=CausalMethod.POLICY_TREE,
            estimand="Optimal_Policy_Value",
            point_estimate=total_effect,
            confidence_interval=ci,
            confidence_level=float(params.get("confidence_level", 0.95)),
            inference_method="policy_tree",
            sample_size=int(data.y.shape[0]),
            n_treated=int(np.sum(data.t == 1)),
            n_control=int(np.sum(data.t == 0)),
            pre_periods=0,
            post_periods=0,
            assumptions=dict(OptimalPolicyLearner.metadata.assumptions),
            method_params={
                "budget_fraction": budget_fraction,
                "cost_per_unit": cost_per_unit,
                "max_depth": int(params.get("max_depth", 3)),
                "min_samples_leaf": int(params.get("min_samples_leaf", 50)),
            },
            metadata={
                "policy_recommendation_present": True,
                "targeted_units": int(np.sum(treated_mask)),
            },
        )
        extras: dict[str, Any] = {
            "policy_recommendation": recommendation,
            "cate_estimates": cate_estimates.tolist(),
            "treatment_decisions": treatment_decisions.tolist(),
        }
        strategic_summary, strategic_warnings, _strategic_bundle = evaluate_strategic_hook(
            params=params,
            baseline_policy_value=total_effect,
        )
        if strategic_summary is not None:
            warnings.extend(warning for warning in strategic_warnings if warning not in warnings)
            recommendation.metadata["strategic_response"] = strategic_summary
            report.metadata["strategic_response"] = strategic_summary
            report.metadata["strategic_response_present"] = True
            extras["strategic_response_summary"] = strategic_summary
        return wrap_causal_output(
            report,
            warnings=warnings,
            extras=extras,
        )


__all__ = ["OptimalPolicyLearner"]
