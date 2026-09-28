"""Expose uncertainty propagation helpers used around Foundry simulation outputs."""

from polisyos.ir.analytics import UncertaintyEnvelope

from .config import AdaptiveStoppingConfig, PropagationConfig
from .fabric_quality import FabricUncertaintyContext, fabric_uncertainty_context_from_decision_data
from .protocol import PropagationResult, PropagationStrategy

try:  # pragma: no cover - optional numeric stack dependency
    from .aggregator import AggregationStrategy, aggregate_envelopes
    from .dispatcher import PropagationDispatcher
    from .quasi_mc import QuasiMCSampler
    from .sensitivity import compute_first_order_indices
except (ImportError, ModuleNotFoundError, SyntaxError, IndentationError):  # pragma: no cover
    AggregationStrategy = None  # type: ignore[assignment]
    aggregate_envelopes = None  # type: ignore[assignment]
    PropagationDispatcher = None  # type: ignore[assignment]
    QuasiMCSampler = None  # type: ignore[assignment]
    compute_first_order_indices = None  # type: ignore[assignment]


def extract_std(env: UncertaintyEnvelope) -> float:
    """Extract scale by delegating to the covariance owner on demand."""
    from .covariance import extract_std as _extract_std

    return _extract_std(env)


__all__ = [
    "AdaptiveStoppingConfig",
    "AggregationStrategy",
    "FabricUncertaintyContext",
    "PropagationConfig",
    "PropagationDispatcher",
    "PropagationResult",
    "PropagationStrategy",
    "QuasiMCSampler",
    "aggregate_envelopes",
    "compute_first_order_indices",
    "extract_std",
    "fabric_uncertainty_context_from_decision_data",
]
