from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.causal import (
    CausalEffectReport,
    CausalMethod,
    DiagnosticTest,
    EstimationStatus,
    PlaceboResult,
)

from ._registry_boot import register_causal_methods
from .did import DifferenceInDifferences
from .protocols import CausalEstimator, PanelObservationalData, RDDObservationalData
from .rdd import RegressionDiscontinuity
from .scm import SyntheticControlMethod
from .structural_time_series import StructuralTimeSeries


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
    "RDDObservationalData",
    "SyntheticControlMethod",
    "DifferenceInDifferences",
    "RegressionDiscontinuity",
    "StructuralTimeSeries",
    "register_causal_methods",
    "ensure_causal_methods_registered",
]
