"""Public bayesian protocols module API."""
from __future__ import annotations

from typing import Any, ClassVar, Mapping

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


class PosteriorResult(BaseModel):
    """Posterior result data model."""
    contract_id: ClassVar[str] = "foundry.bayesian.posterior_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    method_name: str
    posterior_means: dict[str, float] = Field(default_factory=dict)
    posterior_stds: dict[str, float] = Field(default_factory=dict)
    credible_intervals: dict[str, tuple[float, float]] = Field(default_factory=dict)
    diagnostics: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_uncertainty_envelope(self, *, param_name: str | None = None) -> UncertaintyEnvelope | None:
        candidate = param_name
        if candidate is None:
            ordered = [
                name for name in sorted(self.posterior_means)
                if name not in {"sigma", "obs_noise", "noise_scale"}
            ]
            if not ordered:
                ordered = sorted(self.posterior_means)
            if not ordered:
                return None
            candidate = ordered[0]
        if candidate not in self.posterior_means:
            return None
        interval = self.credible_intervals.get(candidate)
        if interval is None:
            return None
        lower, upper = interval
        return UncertaintyEnvelope(
            point_estimate=float(self.posterior_means[candidate]),
            confidence_interval=(float(lower), float(upper)),
            confidence_level=float(self.diagnostics.get("credible_mass", 0.9)),
            distribution_family=DistributionFamily.UNKNOWN,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.MONTE_CARLO,
            interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
            sample_size=int(self.diagnostics.get("num_samples", 0)),
            metadata={
                "method_name": self.method_name,
                "parameter": candidate,
                "num_chains": self.diagnostics.get("num_chains"),
            },
        )


def credible_interval(samples: np.ndarray, *, credible_mass: float) -> tuple[float, float]:
    """Credible interval helper."""
    arr = np.asarray(samples, dtype=float)
    try:
        import arviz as az

        interval = np.asarray(az.hdi(arr, hdi_prob=credible_mass), dtype=float)
        if interval.shape == (2,):
            return float(interval[0]), float(interval[1])
    except Exception:
        pass
    alpha = max(1e-6, 1.0 - float(credible_mass))
    lower, upper = np.quantile(arr, [alpha / 2.0, 1.0 - alpha / 2.0])
    return float(lower), float(upper)


def summarize_posterior_samples(
    samples: Mapping[str, Any],
    *,
    credible_mass: float,
) -> tuple[dict[str, float], dict[str, float], dict[str, tuple[float, float]]]:
    """Summarize posterior samples helper."""
    means: dict[str, float] = {}
    stds: dict[str, float] = {}
    intervals: dict[str, tuple[float, float]] = {}

    for name, value in samples.items():
        arr = np.asarray(value, dtype=float)
        if arr.ndim == 0:
            arr = arr.reshape(1)
        flat = arr.reshape(arr.shape[0], -1)
        labels = [name] if flat.shape[1] == 1 else [f"{name}_{idx}" for idx in range(flat.shape[1])]
        for idx, label in enumerate(labels):
            column = flat[:, idx]
            means[label] = float(np.mean(column))
            stds[label] = float(np.std(column, ddof=1)) if column.shape[0] > 1 else 0.0
            intervals[label] = credible_interval(column, credible_mass=credible_mass)
    return means, stds, intervals


def metropolis_sample(
    *,
    log_density: Any,
    initial_state: np.ndarray,
    proposal_scale: float | np.ndarray,
    rng: np.random.Generator,
    num_warmup: int,
    num_samples: int,
    num_chains: int,
) -> tuple[np.ndarray, float]:
    """Metropolis sample helper."""
    initial = np.asarray(initial_state, dtype=float)
    scale = np.broadcast_to(np.asarray(proposal_scale, dtype=float), initial.shape)
    draws: list[np.ndarray] = []
    accepted = 0
    attempted = 0
    for _ in range(max(1, int(num_chains))):
        current = initial + rng.normal(scale=np.maximum(scale * 0.25, 1e-6), size=initial.shape)
        current_lp = float(log_density(current))
        chain_draws: list[np.ndarray] = []
        for step in range(max(0, int(num_warmup)) + max(1, int(num_samples))):
            proposal = current + rng.normal(scale=np.maximum(scale, 1e-6), size=current.shape)
            proposal_lp = float(log_density(proposal))
            if np.log(max(rng.uniform(), 1e-12)) < (proposal_lp - current_lp):
                current = proposal
                current_lp = proposal_lp
                accepted += 1
            attempted += 1
            if step >= max(0, int(num_warmup)):
                chain_draws.append(current.copy())
        draws.append(np.asarray(chain_draws, dtype=float))
    return np.concatenate(draws, axis=0), accepted / max(attempted, 1)


__all__ = [
    "PosteriorResult",
    "credible_interval",
    "metropolis_sample",
    "summarize_posterior_samples",
]
