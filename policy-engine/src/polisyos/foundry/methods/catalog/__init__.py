"""Public methods catalog package API."""
from __future__ import annotations

from polisyos.foundry.methods.registry import MethodRegistry

try:
    from .causal import ensure_causal_methods_registered
except ModuleNotFoundError:  # pragma: no cover - defensive for partial installs
    def ensure_causal_methods_registered(registry: MethodRegistry | None = None) -> None:
        return None


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


try:
    from .distributional import ensure_distributional_methods_registered
except ModuleNotFoundError:  # pragma: no cover - defensive for partial installs
    def ensure_distributional_methods_registered(registry: MethodRegistry | None = None) -> None:
        return None


try:
    from .survey import ensure_survey_methods_registered
except ModuleNotFoundError:  # pragma: no cover - defensive for partial installs
    def ensure_survey_methods_registered(registry: MethodRegistry | None = None) -> None:
        return None


try:
    from .forecasting import ensure_forecasting_methods_registered
except ModuleNotFoundError:  # pragma: no cover - defensive for partial installs
    def ensure_forecasting_methods_registered(registry: MethodRegistry | None = None) -> None:
        return None


try:
    from .validation import ensure_validation_methods_registered
except ModuleNotFoundError:  # pragma: no cover - defensive for partial installs
    def ensure_validation_methods_registered(registry: MethodRegistry | None = None) -> None:
        return None


try:
    from .sensitivity import ensure_sensitivity_methods_registered
except ModuleNotFoundError:  # pragma: no cover - defensive for partial installs
    def ensure_sensitivity_methods_registered(registry: MethodRegistry | None = None) -> None:
        return None


try:
    from .mechanism import ensure_mechanism_methods_registered
except ModuleNotFoundError:  # pragma: no cover - defensive for partial installs
    def ensure_mechanism_methods_registered(registry: MethodRegistry | None = None) -> None:
        return None


try:
    from .simulation import ensure_simulation_methods_registered
except ModuleNotFoundError:  # pragma: no cover - defensive for partial installs
    def ensure_simulation_methods_registered(registry: MethodRegistry | None = None) -> None:
        return None


try:
    from .policy import ensure_policy_methods_registered
except ModuleNotFoundError:  # pragma: no cover - defensive for partial installs
    def ensure_policy_methods_registered(registry: MethodRegistry | None = None) -> None:
        return None


def ensure_all_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Ensure all methods registered helper."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    ensure_causal_methods_registered(reg)
    ensure_econometric_methods_registered(reg)
    ensure_optimization_methods_registered(reg)
    ensure_ml_methods_registered(reg)
    ensure_microsim_methods_registered(reg)
    ensure_spatial_methods_registered(reg)
    ensure_network_methods_registered(reg)
    ensure_bayesian_methods_registered(reg)
    ensure_distributional_methods_registered(reg)
    ensure_survey_methods_registered(reg)
    ensure_forecasting_methods_registered(reg)
    ensure_validation_methods_registered(reg)
    ensure_sensitivity_methods_registered(reg)
    ensure_mechanism_methods_registered(reg)
    ensure_simulation_methods_registered(reg)
    ensure_policy_methods_registered(reg)


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
    "ensure_distributional_methods_registered",
    "ensure_survey_methods_registered",
    "ensure_forecasting_methods_registered",
    "ensure_validation_methods_registered",
    "ensure_sensitivity_methods_registered",
    "ensure_mechanism_methods_registered",
    "ensure_simulation_methods_registered",
    "ensure_policy_methods_registered",
]
