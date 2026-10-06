"""Explanation adapter protocols and bundled lightweight adapters."""

from __future__ import annotations

from polisyos.berl.adapters.ale import ALEAdapter
from polisyos.berl.adapters.conditional_shapley import (
    AffineModelProfileResolver,
    BoundedOutputProfileVerifier,
    ConditionalLawBinding,
    ConditionalLawResolver,
    ConditionalModelVerifier,
    ConditionalSHAPAdapter,
    ConditionalShapleyResult,
    GaussianJointLaw,
    ResolvedConditionalLaw,
    VerifiedAffineModelProfile,
    VerifiedModelIdentity,
    VerifiedOutputBounds,
    WeightedFiniteSupportLaw,
    finite_support_conditional_expectation,
    finite_support_conditional_shapley,
    fixed_n_hoeffding_plan,
    gaussian_bounded_conditional_shapley,
    gaussian_conditional_moments,
    gaussian_linear_conditional_shapley,
)
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
    "AffineModelProfileResolver",
    "AssumptionReport",
    "BoundedOutputProfileVerifier",
    "ConditionalLawBinding",
    "ConditionalLawResolver",
    "ConditionalModelVerifier",
    "ConditionalSHAPAdapter",
    "ConditionalShapleyResult",
    "EBMComponentAdapter",
    "ExplanationAdapter",
    "ExplanationContext",
    "FiniteDifferenceGradientAdapter",
    "GaussianJointLaw",
    "KernelSHAPAdapter",
    "LIMEAdapter",
    "PermutationImportanceAdapter",
    "RawExplanation",
    "ResolvedConditionalLaw",
    "ScalarModel",
    "TreeSHAPAdapter",
    "UnavailableAdapter",
    "UncertaintyReport",
    "VerifiedAffineModelProfile",
    "VerifiedModelIdentity",
    "VerifiedOutputBounds",
    "WeightedFiniteSupportLaw",
    "finite_support_conditional_expectation",
    "finite_support_conditional_shapley",
    "fixed_n_hoeffding_plan",
    "gaussian_bounded_conditional_shapley",
    "gaussian_conditional_moments",
    "gaussian_linear_conditional_shapley",
]
