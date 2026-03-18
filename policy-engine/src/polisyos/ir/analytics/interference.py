"""IR models for interference and network causal inference.

Covers partial interference (Hudgens & Halloran 2008), general network AIPW
(Aronow & Samii 2017), spatial spillovers, and bipartite interference
(Zigler & Papadogeorgou 2021).
"""
from __future__ import annotations

import math
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InterferenceMethod(str, Enum):
    """Identifies the interference estimator used."""

    PARTIAL_IPW = "partial_interference_ipw"
    """Clustered partial interference with IPW (Hudgens & Halloran 2008)."""
    NETWORK_AIPW = "network_aipw"
    """General network AIPW via exposure mapping (Aronow & Samii 2017)."""
    SPATIAL_KERNEL = "spatial_kernel"
    """Kernel-weighted geographic spillover estimator."""
    BIPARTITE = "bipartite_interference"
    """Bipartite treatment→outcome graph (Zigler & Papadogeorgou 2021)."""


class ExposureMappingType(str, Enum):
    """How neighborhood treatment is mapped to a unit's exposure level."""

    FRACTIONAL = "fractional"
    """Fraction of cluster/network neighbors who are treated."""
    THRESHOLD = "threshold"
    """Binary: 1 if fractional exposure exceeds a threshold."""
    COUNT = "count"
    """Raw count of treated neighbors."""
    KERNEL = "kernel"
    """Gaussian kernel-weighted sum of neighbor treatments (spatial)."""
    BIPARTITE = "bipartite"
    """Aggregate upstream treatment via bipartite graph."""


class InterferenceEffectDecomposition(BaseModel):
    """Full decomposition of treatment effects under interference.

    Following Hudgens & Halloran (2008) and Tchetgen Tchetgen &
    VanderWeele (2012):

    - direct_effect:   DE(α) = E[Y(1,α)] − E[Y(0,α)]
    - spillover_effect: SE(α₁,α₂) = E[Y(0,α₁)] − E[Y(0,α₂)]
    - total_effect:    TE ≈ DE(α₁) + SE(α₁,α₂)
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    # ── Core effect estimates ────────────────────────────────────────────────
    direct_effect: float
    """DE(α) = E[Y(1,α)] − E[Y(0,α)]: effect of own treatment, holding
    neighbours' allocation α fixed."""
    spillover_effect: float
    """SE(α₁,α₂) = E[Y(0,α₁)] − E[Y(0,α₂)]: effect of changing neighbour
    allocation from α₂ to α₁, own treatment held at 0."""
    total_effect: float
    """TE = E[Y(1,α₁)] − E[Y(0,α₂)]: combined direct + spillover contrast."""
    indirect_effect: float | None = None
    """Alias for spillover_effect in some parameterisations."""

    # ── Reference allocation arms ────────────────────────────────────────────
    alpha_high: float = Field(default=0.5, ge=0.0, le=1.0)
    """High-coverage allocation arm α₁ (fraction of neighbours treated)."""
    alpha_low: float = Field(default=0.0, ge=0.0, le=1.0)
    """Low-coverage allocation arm α₂."""

    # ── Standard errors ──────────────────────────────────────────────────────
    se_direct: float | None = Field(default=None, ge=0.0)
    se_spillover: float | None = Field(default=None, ge=0.0)
    se_total: float | None = Field(default=None, ge=0.0)

    # ── Confidence intervals ─────────────────────────────────────────────────
    ci_direct: tuple[float, float] | None = None
    ci_spillover: tuple[float, float] | None = None
    ci_total: tuple[float, float] | None = None

    # ── Sample info ──────────────────────────────────────────────────────────
    n_units: int = Field(ge=2)
    n_treated: int = Field(ge=0)
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    interference_detected: bool = False
    """True when the spillover effect is statistically significant at 5%."""

    @model_validator(mode="after")
    def _check_consistency(self) -> "InterferenceEffectDecomposition":
        if self.n_treated > self.n_units:
            raise ValueError("n_treated must not exceed n_units")
        if not math.isfinite(self.direct_effect):
            raise ValueError("direct_effect must be finite")
        if not math.isfinite(self.spillover_effect):
            raise ValueError("spillover_effect must be finite")
        if not math.isfinite(self.total_effect):
            raise ValueError("total_effect must be finite")
        if self.ci_direct is not None:
            lo, hi = self.ci_direct
            if lo > hi:
                raise ValueError("ci_direct lower bound must not exceed upper")
        if self.ci_spillover is not None:
            lo, hi = self.ci_spillover
            if lo > hi:
                raise ValueError("ci_spillover lower bound must not exceed upper")
        return self


class NetworkInterferenceReport(BaseModel):
    """Top-level result returned by all interference estimation methods.

    Carries the effect decomposition together with diagnostics, exposure
    mapping metadata, and sample statistics.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    method: InterferenceMethod
    status: Literal["success", "input_invalid", "assumption_failed", "numerical_failure"]
    status_reason: str | None = None

    effects: InterferenceEffectDecomposition | None = None

    # ── Exposure mapping metadata ─────────────────────────────────────────────
    exposure_mapping: ExposureMappingType
    exposure_mapping_params: dict[str, Any] = Field(default_factory=dict)

    # ── Sample statistics ────────────────────────────────────────────────────
    n_units: int = Field(ge=2)
    n_treated: int = Field(ge=0)
    n_clusters: int | None = Field(default=None, ge=1)
    average_cluster_size: float | None = Field(default=None, gt=0.0)

    # ── Diagnostics ──────────────────────────────────────────────────────────
    warnings: list[str] = Field(default_factory=list)
    assumptions: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_effects_on_success(self) -> "NetworkInterferenceReport":
        if self.status == "success" and self.effects is None:
            raise ValueError("effects must be set when status is 'success'")
        return self

    # ── Convenience properties ───────────────────────────────────────────────
    @property
    def direct_effect(self) -> float | None:
        return self.effects.direct_effect if self.effects else None

    @property
    def spillover_effect(self) -> float | None:
        return self.effects.spillover_effect if self.effects else None

    @property
    def total_effect(self) -> float | None:
        return self.effects.total_effect if self.effects else None

    @property
    def is_success(self) -> bool:
        return self.status == "success"


__all__ = [
    "ExposureMappingType",
    "InterferenceEffectDecomposition",
    "InterferenceMethod",
    "NetworkInterferenceReport",
]
