from __future__ import annotations

from typing import Sequence

from polisyos.foundry.methods.catalog.causal.constraint_discovery import (
    FCIDiscovery,
    GESDiscovery,
    PCDiscovery,
)
from polisyos.foundry.methods.catalog.causal.did import DifferenceInDifferences
from polisyos.foundry.methods.catalog.causal.dowhy_identify_estimate import (
    DoWhyIdentifyEstimate,
    DoWhyIdentifyEstimateV1,
)
from polisyos.foundry.methods.catalog.causal.dowhy_refute import DoWhyRefute
from polisyos.foundry.methods.catalog.causal.gcm_fit import HybridSCMFit
from polisyos.foundry.methods.catalog.causal.gcm_query import GCMQuery
from polisyos.foundry.methods.catalog.causal.graph_reconciliation import ReconcileCausalGraph
from polisyos.foundry.methods.catalog.causal.literature_prior import BuildLiteraturePrior
from polisyos.foundry.methods.catalog.causal.pcmci_discovery import PCMCIDiscovery
from polisyos.foundry.methods.catalog.causal.parameter_transfer import ParameterTransfer
from polisyos.foundry.methods.catalog.causal.rdd import RegressionDiscontinuity
from polisyos.foundry.methods.catalog.causal.sensitivity_metrics import SensitivityMetrics
from polisyos.foundry.methods.catalog.causal.structural_time_series import StructuralTimeSeries
from polisyos.foundry.methods.catalog.causal.synthetic_control import SyntheticControlMethod
from polisyos.foundry.methods.catalog.causal.transport_check import CheckTransportability


def register_causal_methods() -> Sequence[type]:
    methods: list[type] = [
        SyntheticControlMethod,
        DifferenceInDifferences,
        RegressionDiscontinuity,
        StructuralTimeSeries,
        DoWhyIdentifyEstimateV1,
        DoWhyIdentifyEstimate,
        DoWhyRefute,
        HybridSCMFit,
        GCMQuery,
        ParameterTransfer,
        BuildLiteraturePrior,
        ReconcileCausalGraph,
        SensitivityMetrics,
        CheckTransportability,
        PCMCIDiscovery,
        PCDiscovery,
        FCIDiscovery,
        GESDiscovery,
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
