"""Expose distributional methods and register them into the Foundry catalog."""
from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

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
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_distributional_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "AtkinsonIndexEstimator",
    "AttritionAdjustedMobilityMatrixEstimator",
    "DuclosEstebanRayEstimator",
    "EstebanRayEstimator",
    "FGTPovertyEstimator",
    "GeneralizedEntropyEstimator",
    "GeneralizedGiniEstimator",
    "IntergenerationalElasticityEstimator",
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
