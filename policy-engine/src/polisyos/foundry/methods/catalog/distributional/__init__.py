"""Expose distributional methods and register them into the Foundry catalog."""

from __future__ import annotations

from polisyos.foundry.extensions.registry import bootstrap_builtin_foundry_method_family
from polisyos.foundry.methods.selection.registry import MethodRegistry

from ._registry_boot import register_distributional_methods
from .advanced import (
    GeneralizedGiniEstimator,
    PalmaRatioEstimator,
    TheilIndexEstimator,
)
from .metrics import (
    AtkinsonIndexEstimator,
    FGTPovertyEstimator,
    GeneralizedEntropyEstimator,
    LorenzCurveEstimator,
)
from .mobility import (
    AttritionAdjustedMobilityMatrixEstimator,
    IntergenerationalElasticityEstimator,
    MobilityMatrixEstimator,
    RefreshmentSampleMobilityEstimator,
    SequentialIPCWLifetimeMobilityEstimator,
)
from .mobility_latent_adapter import LatentMobilityReportAdapter
from .polarization import (
    DuclosEstebanRayEstimator,
    EstebanRayEstimator,
)
from .poverty_advanced import (
    MultidimensionalPovertyEstimator,
    OrdinalMultidimensionalPovertyEstimator,
)


def ensure_distributional_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Populate `registry` with inequality, poverty, and mobility methods."""
    bootstrap_builtin_foundry_method_family("distributional", registry)


__all__ = [
    "AtkinsonIndexEstimator",
    "AttritionAdjustedMobilityMatrixEstimator",
    "DuclosEstebanRayEstimator",
    "EstebanRayEstimator",
    "FGTPovertyEstimator",
    "GeneralizedEntropyEstimator",
    "GeneralizedGiniEstimator",
    "IntergenerationalElasticityEstimator",
    "LatentMobilityReportAdapter",
    "LorenzCurveEstimator",
    "MobilityMatrixEstimator",
    "MultidimensionalPovertyEstimator",
    "OrdinalMultidimensionalPovertyEstimator",
    "PalmaRatioEstimator",
    "RefreshmentSampleMobilityEstimator",
    "SequentialIPCWLifetimeMobilityEstimator",
    "TheilIndexEstimator",
    "ensure_distributional_methods_registered",
    "register_distributional_methods",
]
