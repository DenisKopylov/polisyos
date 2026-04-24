"""Public distributional registry boot module API."""

from __future__ import annotations

from collections.abc import Sequence

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
        OrdinalMultidimensionalPovertyEstimator,
        MobilityMatrixEstimator,
        AttritionAdjustedMobilityMatrixEstimator,
        SequentialIPCWLifetimeMobilityEstimator,
        RefreshmentSampleMobilityEstimator,
        IntergenerationalElasticityEstimator,
        EstebanRayEstimator,
        DuclosEstebanRayEstimator,
    )


__all__ = ["register_distributional_methods"]
