"""Optional dependency helpers for strategy modules."""

from __future__ import annotations

from typing import Any

from polisyos.scientist.methods.search.strategies.errors import OptionalDependencyUnavailableError

TORCH_IMPORT_ERROR: Exception | None = None
BOTORCH_IMPORT_ERROR: Exception | None = None

try:  # pragma: no cover - environment dependent
    import torch
except Exception as exc:  # pragma: no cover - environment dependent
    torch = None  # type: ignore[assignment]
    TORCH_IMPORT_ERROR = exc

try:  # pragma: no cover - environment dependent
    if torch is None:  # type: ignore[truthy-function]
        raise RuntimeError("torch is required before botorch import")
    from botorch import fit_gpytorch_mll
    from botorch.acquisition import (
        ExpectedImprovement,
        ProbabilityOfImprovement,
        UpperConfidenceBound,
        qExpectedImprovement,
    )
    from botorch.acquisition.multi_objective import (
        ExpectedHypervolumeImprovement,
        qExpectedHypervolumeImprovement,
    )
    from botorch.models import ModelListGP, SingleTaskGP
    from botorch.models.transforms.input import Normalize
    from botorch.models.transforms.outcome import Standardize
    from botorch.optim import optimize_acqf
    from botorch.utils.multi_objective.box_decompositions import NondominatedPartitioning
    from botorch.utils.multi_objective.pareto import is_non_dominated
    from gpytorch.mlls import ExactMarginalLogLikelihood, SumMarginalLogLikelihood
except Exception as exc:  # pragma: no cover - environment dependent
    fit_gpytorch_mll = None  # type: ignore[assignment]
    ExpectedImprovement = None  # type: ignore[assignment]
    ProbabilityOfImprovement = None  # type: ignore[assignment]
    UpperConfidenceBound = None  # type: ignore[assignment]
    qExpectedImprovement = None  # type: ignore[assignment]
    ExpectedHypervolumeImprovement = None  # type: ignore[assignment]
    qExpectedHypervolumeImprovement = None  # type: ignore[assignment]
    ModelListGP = None  # type: ignore[assignment]
    SingleTaskGP = None  # type: ignore[assignment]
    Normalize = None  # type: ignore[assignment]
    Standardize = None  # type: ignore[assignment]
    optimize_acqf = None  # type: ignore[assignment]
    NondominatedPartitioning = None  # type: ignore[assignment]
    is_non_dominated = None  # type: ignore[assignment]
    ExactMarginalLogLikelihood = None  # type: ignore[assignment]
    SumMarginalLogLikelihood = None  # type: ignore[assignment]
    BOTORCH_IMPORT_ERROR = exc


def require_torch() -> Any:
    """Return torch module or raise informative exception."""
    if torch is None:  # type: ignore[truthy-function]
        raise OptionalDependencyUnavailableError(
            "Torch is required for this strategy. Install extra dependency 'search_bo'."
        ) from TORCH_IMPORT_ERROR
    return torch


def require_botorch() -> None:
    """Ensure BoTorch stack is available."""
    require_torch()
    if fit_gpytorch_mll is None:
        raise OptionalDependencyUnavailableError(
            "BoTorch/GPyTorch is required for Bayesian strategies. "
            "Install extra dependency 'search_bo'."
        ) from BOTORCH_IMPORT_ERROR
