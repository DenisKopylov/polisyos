"""Expose uncertainty propagation helpers used around Foundry simulation outputs."""

from importlib import import_module
from typing import TYPE_CHECKING

from polisyos.ir.analytics import UncertaintyEnvelope

from ..calibration.report import load_calibration_report as load_foundry_calibration_report
from .config import AdaptiveStoppingConfig, PropagationConfig
from .fabric_quality import FabricUncertaintyContext, fabric_uncertainty_context_from_decision_data
from .protocol import PropagationResult, PropagationStrategy
from .sampling_admission import (
    BoundedIndicatorResponse,
    admit_empirical_weights,
    admit_unit_uniform,
    empirical_cdf,
    reconcile_draw_outcomes,
    sampling_content_digest,
    verify_mean_certificate,
)

if TYPE_CHECKING:
    from .covariance import (
        CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1,
        CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1,
        build_covariance_matrix,
        calibration_covariance_blocks_agree_v1,
        preserve_singular_covariance,
    )

_COVARIANCE_EXPORTS = frozenset(
    {
        "CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1",
        "CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1",
        "build_covariance_matrix",
        "calibration_covariance_blocks_agree_v1",
        "preserve_singular_covariance",
    }
)

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


def __getattr__(name: str) -> object:
    """Resolve canonical covariance objects only when the numeric API is requested."""
    if name in _COVARIANCE_EXPORTS:
        value = getattr(import_module(".covariance", __name__), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1",
    "CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1",
    "AdaptiveStoppingConfig",
    "AggregationStrategy",
    "BoundedIndicatorResponse",
    "FabricUncertaintyContext",
    "PropagationConfig",
    "PropagationDispatcher",
    "PropagationResult",
    "PropagationStrategy",
    "QuasiMCSampler",
    "admit_empirical_weights",
    "admit_unit_uniform",
    "aggregate_envelopes",
    "build_covariance_matrix",
    "calibration_covariance_blocks_agree_v1",
    "compute_first_order_indices",
    "empirical_cdf",
    "extract_std",
    "fabric_uncertainty_context_from_decision_data",
    "load_foundry_calibration_report",
    "preserve_singular_covariance",
    "reconcile_draw_outcomes",
    "sampling_content_digest",
    "verify_mean_certificate",
]
