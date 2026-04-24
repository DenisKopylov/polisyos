"""Public microsim registry boot module API."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from .advanced import (
    BehavioralResponseEstimator,
    DynamicMicrosimEstimator,
    HeterogeneousBehavioralResponseEstimator,
    ImputationModelEstimator,
    TaxBenefitCalculatorEstimator,
)
from .calibration import ReweightingCalibrationEstimator
from .inverse import InverseBehavioralCalibrationEstimator
from .mnar import MNARIncomeBoundsEstimator
from .static import StaticMicrosimEstimator


def register_microsim_methods() -> Sequence[type]:
    """Register microsim methods."""
    return (
        ReweightingCalibrationEstimator,
        InverseBehavioralCalibrationEstimator,
        StaticMicrosimEstimator,
        TaxBenefitCalculatorEstimator,
        BehavioralResponseEstimator,
        HeterogeneousBehavioralResponseEstimator,
        ImputationModelEstimator,
        MNARIncomeBoundsEstimator,
        DynamicMicrosimEstimator,
    )


__all__ = ["register_microsim_methods"]
