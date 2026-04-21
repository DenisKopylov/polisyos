"""Typed IR contracts for survey raking / IPF convergence diagnostics."""
from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


class SurveyRakingIteration(BaseModel):
    """One sweep-level trace record for iterative proportional fitting."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sweep: int = Field(ge=1)
    max_rel_margin_error: float = Field(ge=0.0)
    rms_rel_margin_error: float = Field(ge=0.0)
    max_logweight_change: float = Field(ge=0.0)
    improvement_ratio: float | None = Field(default=None, ge=0.0)
    worst_margin: str | None = None
    worst_category: str | None = None


class SurveyRakingCategoryDiagnostic(BaseModel):
    """Category-level support and positivity diagnostic emitted before/after IPF."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    margin_name: str = Field(min_length=1)
    category_name: str = Field(min_length=1)
    sample_count: int = Field(ge=0)
    sample_share: float = Field(ge=0.0, le=1.0)
    sample_weight_total: float = Field(ge=0.0)
    target_total: float = Field(ge=0.0)
    target_share: float = Field(ge=0.0, le=1.0)
    achieved_total: float = Field(ge=0.0)
    vif_lower_bound: float | None = Field(default=None, ge=0.0)
    structural_zero: bool = False
    sparse_level: Literal["ok", "warn", "block", "structural_zero"] = "ok"


class SurveyRakingDiagnosticReport(BaseModel):
    """Top-level typed report for survey/microsim IPF convergence and positivity."""

    contract_id: ClassVar[str] = "ir.survey_raking_diagnostic_report.v1"
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    decision: Literal["pass", "warn", "block"]
    converged: bool
    stop_reason: Literal[
        "converged_exact",
        "converged_warn_tolerance",
        "stagnation",
        "max_iter_exceeded",
        "structural_zero",
        "inconsistent_targets",
        "invalid_margin_design",
        "fallback_collapsed_categories",
        "fallback_bounded_logit",
        "fallback_penalized",
        "bounded_infeasible",
    ]
    n_obs: int = Field(ge=0)
    population_total: float = Field(ge=0.0)
    n_sweeps: int = Field(ge=0)
    max_rel_margin_error: float = Field(ge=0.0)
    rms_rel_margin_error: float = Field(ge=0.0)
    max_logweight_change: float = Field(ge=0.0)
    improvement_ratio_5: float | None = Field(default=None, ge=0.0)
    monotonicity_share: float = Field(ge=0.0, le=1.0)
    worst_margin: str | None = None
    worst_category: str | None = None
    ess: float = Field(ge=0.0)
    ess_fraction: float = Field(ge=0.0, le=1.0)
    kish_deff: float = Field(ge=0.0)
    cv_weights: float = Field(ge=0.0)
    top1_weight_share: float = Field(ge=0.0, le=1.0)
    top5_weight_share: float = Field(ge=0.0, le=1.0)
    max_g_weight_ratio: float = Field(ge=0.0)
    min_g_weight_ratio: float = Field(ge=0.0)
    structural_zero_count: int = Field(ge=0)
    sparse_category_count: int = Field(ge=0)
    vif_lb_max: float = Field(ge=0.0)
    target_totals: dict[str, float] = Field(default_factory=dict)
    achieved_totals: dict[str, float] = Field(default_factory=dict)
    blocking_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    recommendations: tuple[str, ...] = ()
    categories: tuple[SurveyRakingCategoryDiagnostic, ...] = ()
    trace: tuple[SurveyRakingIteration, ...] = ()
    fallback_used: str | None = None


__all__ = [
    "SurveyRakingCategoryDiagnostic",
    "SurveyRakingDiagnosticReport",
    "SurveyRakingIteration",
]
