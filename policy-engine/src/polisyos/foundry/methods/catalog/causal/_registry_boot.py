from __future__ import annotations

from typing import Sequence

from polisyos.foundry.methods.catalog.causal.did import DifferenceInDifferences
from polisyos.foundry.methods.catalog.causal.rdd import RegressionDiscontinuity
from polisyos.foundry.methods.catalog.causal.scm import SyntheticControlMethod
from polisyos.foundry.methods.catalog.causal.structural_time_series import StructuralTimeSeries


def register_causal_methods() -> Sequence[type]:
    methods: list[type] = [
        SyntheticControlMethod,
        DifferenceInDifferences,
        RegressionDiscontinuity,
        StructuralTimeSeries,
    ]
    try:
        from polisyos.foundry.methods.catalog.causal.cate import CausalForestEstimator
        from polisyos.foundry.methods.catalog.causal.dml import DoubleMachineLearning
        from polisyos.foundry.methods.catalog.causal.meta_learners import MetaLearnerEstimator
        from polisyos.foundry.methods.catalog.causal.policy_learning import OptimalPolicyLearner

        methods.extend(
            [
                CausalForestEstimator,
                DoubleMachineLearning,
                MetaLearnerEstimator,
                OptimalPolicyLearner,
            ]
        )
    except ModuleNotFoundError as exc:
        if exc.name not in {"econml", "shap"}:
            raise
    return tuple(methods)


__all__ = ["register_causal_methods"]
