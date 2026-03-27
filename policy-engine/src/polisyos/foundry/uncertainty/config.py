from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AdaptiveStoppingConfig(BaseModel):
    """Criteria for adaptive Monte Carlo stopping."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = False
    min_samples: int = Field(default=200, ge=50)
    max_samples: int = Field(default=10_000, le=100_000)
    ci_half_width_target: float = Field(default=0.01, gt=0.0)
    check_interval: int = Field(default=100, ge=10)


class PropagationConfig(BaseModel):
    """Runtime configuration for uncertainty propagation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)

    delta_use_full_covariance: bool = Field(default=True)
    delta_covariance_jitter: float = Field(default=1e-9, ge=0.0)

    mc_n_samples: int = Field(default=1000, ge=100, le=100_000)
    mc_batch_size: int = Field(default=200, ge=10, le=10_000)
    mc_seed: int = Field(default=42)
    mc_min_valid_samples: int = Field(default=50, ge=10)
    mc_sampling_method: str = Field(
        default="random",
        pattern=r"^(random|sobol|halton)$",
    )

    auto_select_strategy: bool = Field(default=True)
    preferred_method: str = Field(default="auto")

    adaptive_stopping: AdaptiveStoppingConfig = Field(
        default_factory=lambda: AdaptiveStoppingConfig(),
    )
    compute_sensitivity: bool = Field(default=True)
