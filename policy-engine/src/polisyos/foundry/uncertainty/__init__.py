"""Expose uncertainty propagation helpers used around Foundry simulation outputs."""

from .config import AdaptiveStoppingConfig, PropagationConfig
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

__all__ = [
    "AdaptiveStoppingConfig",
    "AggregationStrategy",
    "PropagationConfig",
    "PropagationDispatcher",
    "PropagationResult",
    "PropagationStrategy",
    "QuasiMCSampler",
    "aggregate_envelopes",
    "compute_first_order_indices",
]
