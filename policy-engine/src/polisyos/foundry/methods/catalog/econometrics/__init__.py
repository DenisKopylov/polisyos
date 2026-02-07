from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_econometric_methods
from .iv import InstrumentalVariablesEstimator
from .panel import PanelDataEstimator
from .protocols import EconometricEstimator, EconometricResult, PanelData, TimeSeriesData
from .timeseries import TimeSeriesEstimator


def ensure_econometric_methods_registered(registry: MethodRegistry | None = None) -> None:
    reg = registry or MethodRegistry.get_instance()
    for method_class in register_econometric_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "EconometricEstimator",
    "EconometricResult",
    "PanelData",
    "TimeSeriesData",
    "PanelDataEstimator",
    "InstrumentalVariablesEstimator",
    "TimeSeriesEstimator",
    "register_econometric_methods",
    "ensure_econometric_methods_registered",
]
