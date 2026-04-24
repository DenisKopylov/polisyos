"""Public econometrics registry boot module API."""

from __future__ import annotations

from collections.abc import Sequence

from .advanced import (
    ChangePointEstimator,
    EventStudyEstimator,
    GARCHEstimator,
    LocalProjectionsEstimator,
    NonstationaryGARCHEstimator,
    QuantileRegressionEstimator,
)
from .count_data import (
    NegativeBinomialEstimator,
    PoissonRegressionEstimator,
    ZeroInflatedPoissonEstimator,
)
from .diagnostics import (
    CointegrationTestEstimator,
    ForecastBacktestEstimator,
    HausmanTestEstimator,
    SarganHansenEstimator,
    WeakIVTestEstimator,
)
from .discrete_choice import (
    BLPEstimator,
    LogitEstimator,
    MixedLogitEstimator,
    MultinomialLogitEstimator,
    ProbitEstimator,
)
from .dynamic_panel import DifferenceGMMEstimator, SystemGMMEstimator
from .expansion import (
    BayesianVAREstimator,
    SpatialAutoregressiveEstimator,
    SyntheticDiDEstimator,
    VECMEstimator,
)
from .factor_models import DynamicFactorModelEstimator, PrincipalComponentsEstimator
from .high_dimensional import (
    PostDoubleSelectionEstimator,
    PostLASSOEstimator,
)
from .high_dimensional_iv import HighDimensionalPostSelectionIVEstimator
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
from .thresholds import (
    StateDependentFRDEstimator,
    StateDependentFRKDEstimator,
    StateDependentKinkEstimator,
    StateDependentThresholdEstimator,
)
from .timeseries import ARIMAEstimator, VAREstimator


def register_econometric_methods() -> Sequence[type]:
    """Register econometric methods."""
    return (
        FixedEffectsEstimator,
        RandomEffectsEstimator,
        DifferenceGMMEstimator,
        SystemGMMEstimator,
        TwoStageLeastSquaresEstimator,
        GMMEstimator,
        ARIMAEstimator,
        VAREstimator,
        QuantileRegressionEstimator,
        EventStudyEstimator,
        LocalProjectionsEstimator,
        GARCHEstimator,
        NonstationaryGARCHEstimator,
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
        HighDimensionalPostSelectionIVEstimator,
        StateDependentThresholdEstimator,
        StateDependentKinkEstimator,
        StateDependentFRDEstimator,
        StateDependentFRKDEstimator,
        # Phase SOTA additions
        PrincipalComponentsEstimator,
        DynamicFactorModelEstimator,
    )


__all__ = ["register_econometric_methods"]
