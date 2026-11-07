"""Expose uncertainty propagation helpers used around Foundry simulation outputs."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from polisyos.ir.analytics import UncertaintyEnvelope

from .config import AdaptiveStoppingConfig, PropagationConfig
from .fabric_quality import (
    FabricUncertaintyContext,
    fabric_uncertainty_context_from_decision_data,
)
from .protocol import PropagationResult, PropagationStrategy

if TYPE_CHECKING:
    from .covariance import (
        CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1,
        CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1,
        build_covariance_matrix,
        calibration_covariance_blocks_agree_v1,
        preserve_singular_covariance,
    )
    from .empirical import (
        EmpiricalJointRows,
        EmpiricalNumericResolutionError,
        empirical_indices_from_cdf,
        empirical_joint_moments,
        empirical_weighted_moments,
        normalize_empirical_masses,
        prepare_empirical_cdf,
        prepare_empirical_joint,
    )
    from .evaluation_failures import (
        EXCEPTION_CHAIN_EDGE_LIMIT,
        EXCEPTION_CHAIN_NODE_LIMIT,
        EvaluationFailureClassification,
        classify_evaluation_failure,
    )

try:  # pragma: no cover - optional numeric stack dependency
    from .aggregator import (
        AggregationStrategy,
        aggregate_envelopes,
        aggregate_persisted_envelope_views,
        load_aggregated_envelope_fresh,
        persist_aggregated_envelope,
    )
    from .dispatcher import PropagationDispatcher
    from .monte_carlo import (
        MonteCarloPropagator,
        PosteriorJointInputMatrix,
        PosteriorPushforwardFailure,
        PosteriorPushforwardOutcomeCode,
        PosteriorPushforwardOutputSummary,
        PosteriorPushforwardResult,
    )
    from .quasi_mc import QuasiMCSampler
    from .sensitivity import compute_first_order_indices
except (
    ImportError,
    ModuleNotFoundError,
    SyntaxError,
    IndentationError,
):  # pragma: no cover
    AggregationStrategy = None  # type: ignore[assignment]
    aggregate_envelopes = None  # type: ignore[assignment]
    aggregate_persisted_envelope_views = None  # type: ignore[assignment]
    load_aggregated_envelope_fresh = None  # type: ignore[assignment]
    persist_aggregated_envelope = None  # type: ignore[assignment]
    PropagationDispatcher = None  # type: ignore[assignment]
    MonteCarloPropagator = None  # type: ignore[assignment]
    PosteriorJointInputMatrix = None  # type: ignore[assignment]
    PosteriorPushforwardFailure = None  # type: ignore[assignment]
    PosteriorPushforwardOutcomeCode = None  # type: ignore[assignment]
    PosteriorPushforwardOutputSummary = None  # type: ignore[assignment]
    PosteriorPushforwardResult = None  # type: ignore[assignment]
    QuasiMCSampler = None  # type: ignore[assignment]
    compute_first_order_indices = None  # type: ignore[assignment]


_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "EmpiricalJointRows": (
        "polisyos.foundry.uncertainty.empirical",
        "EmpiricalJointRows",
    ),
    "EmpiricalNumericResolutionError": (
        "polisyos.foundry.uncertainty.empirical",
        "EmpiricalNumericResolutionError",
    ),
    "empirical_indices_from_cdf": (
        "polisyos.foundry.uncertainty.empirical",
        "empirical_indices_from_cdf",
    ),
    "empirical_joint_moments": (
        "polisyos.foundry.uncertainty.empirical",
        "empirical_joint_moments",
    ),
    "empirical_weighted_moments": (
        "polisyos.foundry.uncertainty.empirical",
        "empirical_weighted_moments",
    ),
    "normalize_empirical_masses": (
        "polisyos.foundry.uncertainty.empirical",
        "normalize_empirical_masses",
    ),
    "prepare_empirical_cdf": (
        "polisyos.foundry.uncertainty.empirical",
        "prepare_empirical_cdf",
    ),
    "prepare_empirical_joint": (
        "polisyos.foundry.uncertainty.empirical",
        "prepare_empirical_joint",
    ),
    "CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1": (
        "polisyos.foundry.uncertainty.covariance",
        "CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1",
    ),
    "CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1": (
        "polisyos.foundry.uncertainty.covariance",
        "CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1",
    ),
    "EXCEPTION_CHAIN_EDGE_LIMIT": (
        "polisyos.foundry.uncertainty.evaluation_failures",
        "EXCEPTION_CHAIN_EDGE_LIMIT",
    ),
    "EXCEPTION_CHAIN_NODE_LIMIT": (
        "polisyos.foundry.uncertainty.evaluation_failures",
        "EXCEPTION_CHAIN_NODE_LIMIT",
    ),
    "EvaluationFailureClassification": (
        "polisyos.foundry.uncertainty.evaluation_failures",
        "EvaluationFailureClassification",
    ),
    "build_covariance_matrix": (
        "polisyos.foundry.uncertainty.covariance",
        "build_covariance_matrix",
    ),
    "calibration_covariance_blocks_agree_v1": (
        "polisyos.foundry.uncertainty.covariance",
        "calibration_covariance_blocks_agree_v1",
    ),
    "classify_evaluation_failure": (
        "polisyos.foundry.uncertainty.evaluation_failures",
        "classify_evaluation_failure",
    ),
    "preserve_singular_covariance": (
        "polisyos.foundry.uncertainty.covariance",
        "preserve_singular_covariance",
    ),
}


def __getattr__(name: str) -> Any:
    """Resolve covariance and failure exports without eager owner imports."""
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return loaded globals and deferred public exports."""
    return sorted({*globals(), *__all__, *_LAZY_IMPORTS})


def extract_std(env: UncertaintyEnvelope) -> float:
    """Extract scale by delegating to the covariance owner on demand."""
    from .covariance import extract_std as _extract_std

    return _extract_std(env)


__all__ = [
    "CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1",
    "CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1",
    "EXCEPTION_CHAIN_EDGE_LIMIT",
    "EXCEPTION_CHAIN_NODE_LIMIT",
    "EvaluationFailureClassification",
    "EmpiricalNumericResolutionError",
    "EmpiricalJointRows",
    "build_covariance_matrix",
    "calibration_covariance_blocks_agree_v1",
    "classify_evaluation_failure",
    "preserve_singular_covariance",
    "AdaptiveStoppingConfig",
    "AggregationStrategy",
    "FabricUncertaintyContext",
    "MonteCarloPropagator",
    "PropagationConfig",
    "PropagationDispatcher",
    "PropagationResult",
    "PropagationStrategy",
    "PosteriorJointInputMatrix",
    "PosteriorPushforwardFailure",
    "PosteriorPushforwardOutcomeCode",
    "PosteriorPushforwardOutputSummary",
    "PosteriorPushforwardResult",
    "QuasiMCSampler",
    "aggregate_envelopes",
    "aggregate_persisted_envelope_views",
    "load_aggregated_envelope_fresh",
    "persist_aggregated_envelope",
    "compute_first_order_indices",
    "empirical_indices_from_cdf",
    "empirical_joint_moments",
    "empirical_weighted_moments",
    "extract_std",
    "fabric_uncertainty_context_from_decision_data",
    "normalize_empirical_masses",
    "prepare_empirical_cdf",
    "prepare_empirical_joint",
]
