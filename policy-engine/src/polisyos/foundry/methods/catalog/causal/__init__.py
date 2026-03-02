from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    DiagnosticTest,
    EstimationStatus,
    PlaceboResult,
)

from ._registry_boot import register_causal_methods
from .cate import CausalForestEstimator
from .constraint_discovery import FCIDiscovery, GESDiscovery, PCDiscovery
from .did import DifferenceInDifferences
from .dml import DoubleMachineLearning
from .dowhy_identify_estimate import DoWhyIdentifyEstimate, DoWhyIdentifyEstimateV1
from .dowhy_refute import DoWhyRefute
from .gcm_fit import HybridSCMFit
from .gcm_query import GCMQuery
from .graph_reconciliation import ReconcileCausalGraph, compute_reconciliation_diagnostics
from .literature_prior import BuildLiteraturePrior
from .meta_learners import MetaLearnerEstimator
from .parameter_transfer import ParameterTransfer
from .pcmci_discovery import PCMCIDiscovery
from .policy_learning import OptimalPolicyLearner
from .protocols import (
    CausalEstimator,
    GraphCausalData,
    GraphCausalDataV1,
    GraphReconciliationData,
    HTEObservationalData,
    LiteraturePriorBuildData,
    LLMStructuralHint,
    PanelObservationalData,
    ParameterTransferData,
    RDDObservationalData,
    SCMFitData,
    SCMQueryData,
    TabularCausalDiscoveryData,
    TimeSeriesCausalData,
)
from .rdd import RegressionDiscontinuity
from .sensitivity_metrics import SensitivityMetrics
from .structural_time_series import StructuralTimeSeries
from .synthetic_control import SyntheticControlMethod
from .transport_check import CheckTransportability


def ensure_causal_methods_registered(registry: MethodRegistry | None = None) -> None:
    reg = registry or MethodRegistry.get_instance()
    for method_class in register_causal_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "CausalEffectReport",
    "CausalMethod",
    "DiagnosticTest",
    "EstimationStatus",
    "PlaceboResult",
    "CausalEstimator",
    "PanelObservationalData",
    "HTEObservationalData",
    "GraphCausalData",
    "GraphCausalDataV1",
    "LiteraturePriorBuildData",
    "GraphReconciliationData",
    "LLMStructuralHint",
    "SCMFitData",
    "SCMQueryData",
    "ParameterTransferData",
    "RDDObservationalData",
    "TimeSeriesCausalData",
    "TabularCausalDiscoveryData",
    "SyntheticControlMethod",
    "DifferenceInDifferences",
    "RegressionDiscontinuity",
    "StructuralTimeSeries",
    "DoWhyIdentifyEstimate",
    "DoWhyIdentifyEstimateV1",
    "DoWhyRefute",
    "HybridSCMFit",
    "GCMQuery",
    "ParameterTransfer",
    "BuildLiteraturePrior",
    "ReconcileCausalGraph",
    "compute_reconciliation_diagnostics",
    "PCMCIDiscovery",
    "PCDiscovery",
    "FCIDiscovery",
    "GESDiscovery",
    "SensitivityMetrics",
    "CheckTransportability",
    "CausalForestEstimator",
    "DoubleMachineLearning",
    "MetaLearnerEstimator",
    "OptimalPolicyLearner",
    "register_causal_methods",
    "ensure_causal_methods_registered",
]
