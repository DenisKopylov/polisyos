from __future__ import annotations

from typing import Sequence

from .iv import InstrumentalVariablesEstimator
from .panel import PanelDataEstimator
from .timeseries import TimeSeriesEstimator


def register_econometric_methods() -> Sequence[type]:
    return (
        PanelDataEstimator,
        InstrumentalVariablesEstimator,
        TimeSeriesEstimator,
    )


__all__ = ["register_econometric_methods"]
