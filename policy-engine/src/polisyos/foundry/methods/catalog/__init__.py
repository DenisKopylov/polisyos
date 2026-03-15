from __future__ import annotations

from polisyos.foundry.methods.registry import MethodRegistry

from .causal import ensure_causal_methods_registered
from .econometrics import ensure_econometric_methods_registered
from .optimization import ensure_optimization_methods_registered

try:
    from .ml import ensure_ml_methods_registered
except ModuleNotFoundError:  # pragma: no cover - defensive for partial installs
    def ensure_ml_methods_registered(registry: MethodRegistry | None = None) -> None:
        return None


try:
    from .microsim import ensure_microsim_methods_registered
except ModuleNotFoundError:  # pragma: no cover - defensive for partial installs
    def ensure_microsim_methods_registered(registry: MethodRegistry | None = None) -> None:
        return None


try:
    from .spatial import ensure_spatial_methods_registered
except ModuleNotFoundError:  # pragma: no cover - defensive for partial installs
    def ensure_spatial_methods_registered(registry: MethodRegistry | None = None) -> None:
        return None


try:
    from .network import ensure_network_methods_registered
except ModuleNotFoundError:  # pragma: no cover - defensive for partial installs
    def ensure_network_methods_registered(registry: MethodRegistry | None = None) -> None:
        return None


try:
    from .bayesian import ensure_bayesian_methods_registered
except ModuleNotFoundError:  # pragma: no cover - defensive for partial installs
    def ensure_bayesian_methods_registered(registry: MethodRegistry | None = None) -> None:
        return None


def ensure_all_methods_registered(registry: MethodRegistry | None = None) -> None:
    reg = registry or MethodRegistry.get_instance()
    ensure_causal_methods_registered(reg)
    ensure_econometric_methods_registered(reg)
    ensure_optimization_methods_registered(reg)
    ensure_ml_methods_registered(reg)
    ensure_microsim_methods_registered(reg)
    ensure_spatial_methods_registered(reg)
    ensure_network_methods_registered(reg)
    ensure_bayesian_methods_registered(reg)


__all__ = [
    "ensure_all_methods_registered",
    "ensure_causal_methods_registered",
    "ensure_econometric_methods_registered",
    "ensure_optimization_methods_registered",
    "ensure_ml_methods_registered",
    "ensure_microsim_methods_registered",
    "ensure_spatial_methods_registered",
    "ensure_network_methods_registered",
    "ensure_bayesian_methods_registered",
]
