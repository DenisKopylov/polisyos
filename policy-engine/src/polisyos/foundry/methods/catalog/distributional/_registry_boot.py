"""Public distributional registry boot module API."""
from __future__ import annotations

from typing import Sequence

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
    IntergenerationalElasticityEstimator,
    MobilityMatrixEstimator,
)
from .polarization import (
    DuclosEstebanRayEstimator,
    EstebanRayEstimator,
)
from .poverty_advanced import MultidimensionalPovertyEstimator


def register_distributional_methods() -> Sequence[type]:
    """Register distributional methods."""
    return (
        LorenzCurveEstimator,
        AtkinsonIndexEstimator,
        GeneralizedEntropyEstimator,
        FGTPovertyEstimator,
        TheilIndexEstimator,
        PalmaRatioEstimator,
        GeneralizedGiniEstimator,
        MultidimensionalPovertyEstimator,
        MobilityMatrixEstimator,
        IntergenerationalElasticityEstimator,
        EstebanRayEstimator,
        DuclosEstebanRayEstimator,
    )


__all__ = ["register_distributional_methods"]
