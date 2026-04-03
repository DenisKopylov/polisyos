"""Public econometrics registry boot module API."""
from __future__ import annotations

from typing import Sequence

from .advanced import (
    ChangePointEstimator,
    EventStudyEstimator,
    GARCHEstimator,
    LocalProjectionsEstimator,
    QuantileRegressionEstimator,
)
from .diagnostics import (
    CointegrationTestEstimator,
    ForecastBacktestEstimator,
    HausmanTestEstimator,
    SarganHansenEstimator,
    WeakIVTestEstimator,
)
from .expansion import (
    BayesianVAREstimator,
    SpatialAutoregressiveEstimator,
    SyntheticDiDEstimator,
    VECMEstimator,
)
from .count_data import (
    NegativeBinomialEstimator,
    PoissonRegressionEstimator,
    ZeroInflatedPoissonEstimator,
)
from .discrete_choice import (
    BLPEstimator,
    LogitEstimator,
    MixedLogitEstimator,
    MultinomialLogitEstimator,
    ProbitEstimator,
)
from .high_dimensional import (
    PostDoubleSelectionEstimator,
    PostLASSOEstimator,
)
from .factor_models import DynamicFactorModelEstimator, PrincipalComponentsEstimator
from .iv import GMMEstimator, TwoStageLeastSquaresEstimator
from .panel import FixedEffectsEstimator, RandomEffectsEstimator
from .selection import (
    HeckmanSelectionEstimator,
    TobitEstimator,
    TruncatedRegressionEstimator,
)
from .semiparametric import (
    KernelRegressionEstimator,
    RobinsonEstimator,
)
from .timeseries import ARIMAEstimator, VAREstimator


def register_econometric_methods() -> Sequence[type]:
    """Register econometric methods."""
    return (
        FixedEffectsEstimator,
        RandomEffectsEstimator,
        TwoStageLeastSquaresEstimator,
        GMMEstimator,
        ARIMAEstimator,
        VAREstimator,
        QuantileRegressionEstimator,
        EventStudyEstimator,
        LocalProjectionsEstimator,
        GARCHEstimator,
        ChangePointEstimator,
        VECMEstimator,
        BayesianVAREstimator,
        SyntheticDiDEstimator,
        SpatialAutoregressiveEstimator,
        HausmanTestEstimator,
        WeakIVTestEstimator,
        SarganHansenEstimator,
        CointegrationTestEstimator,
        ForecastBacktestEstimator,
        # Phase 2 additions
        LogitEstimator,
        ProbitEstimator,
        MultinomialLogitEstimator,
        MixedLogitEstimator,
        BLPEstimator,
        HeckmanSelectionEstimator,
        TobitEstimator,
        TruncatedRegressionEstimator,
        PoissonRegressionEstimator,
        NegativeBinomialEstimator,
        ZeroInflatedPoissonEstimator,
        RobinsonEstimator,
        KernelRegressionEstimator,
        PostLASSOEstimator,
        PostDoubleSelectionEstimator,
        # Phase SOTA additions
        PrincipalComponentsEstimator,
        DynamicFactorModelEstimator,
    )


__all__ = ["register_econometric_methods"]
