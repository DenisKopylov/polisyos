"""Explanation adapter protocols and bundled lightweight adapters."""

from __future__ import annotations

from polisyos.berl.adapters.ale import ALEAdapter
from polisyos.berl.adapters.ebm import EBMComponentAdapter
from polisyos.berl.adapters.gradients import FiniteDifferenceGradientAdapter
from polisyos.berl.adapters.lime import LIMEAdapter
from polisyos.berl.adapters.permutation import PermutationImportanceAdapter
from polisyos.berl.adapters.protocol import (
    AdapterUnavailableError,
    AssumptionReport,
    ExplanationAdapter,
    ExplanationContext,
    RawExplanation,
    ScalarModel,
    UnavailableAdapter,
    UncertaintyReport,
)
from polisyos.berl.adapters.shap_kernel import KernelSHAPAdapter
from polisyos.berl.adapters.shap_tree import TreeSHAPAdapter

__all__ = [
    "ALEAdapter",
    "AdapterUnavailableError",
    "AssumptionReport",
    "EBMComponentAdapter",
    "ExplanationAdapter",
    "ExplanationContext",
    "FiniteDifferenceGradientAdapter",
    "KernelSHAPAdapter",
    "LIMEAdapter",
    "PermutationImportanceAdapter",
    "RawExplanation",
    "ScalarModel",
    "TreeSHAPAdapter",
    "UnavailableAdapter",
    "UncertaintyReport",
]
