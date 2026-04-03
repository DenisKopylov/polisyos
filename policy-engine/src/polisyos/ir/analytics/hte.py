"""Define heterogeneous treatment effect estimates and targeting recommendations."""
from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics.causal import CausalMethod
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import HTEResultRef, PolicyRecommendationRef


class SubgroupEffect(BaseModel):
    """Estimated conditional treatment effect for one labeled subgroup."""

    model_config = ConfigDict(extra="forbid")

    subgroup_id: str = Field(min_length=1)
    subgroup_label: str = Field(min_length=1)
    subgroup_query: str = Field(min_length=1)
    subgroup_label_human: str | None = None
    n_units: int = Field(ge=0)
    cate_mean: float
    cate_std: float = Field(ge=0.0)
    cate_ci_lower: float
    cate_ci_upper: float
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    is_significant: bool = False
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_ci(self) -> "SubgroupEffect":
        if not math.isfinite(self.cate_mean):
            raise ValueError("cate_mean must be finite")
        if not math.isfinite(self.cate_std):
            raise ValueError("cate_std must be finite")
        if not math.isfinite(self.cate_ci_lower) or not math.isfinite(self.cate_ci_upper):
            raise ValueError("CI bounds must be finite")
        if self.cate_ci_lower > self.cate_ci_upper:
            raise ValueError("cate_ci_lower must be <= cate_ci_upper")
        return self


class FeatureImportance(BaseModel):
    """Ranking signal for a feature used in heterogeneous-effect modeling."""

    model_config = ConfigDict(extra="forbid")

    feature_name: str = Field(min_length=1)
    importance_score: float
    importance_rank: int = Field(ge=1)
    method: str = "tree_based"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_score(self) -> "FeatureImportance":
        if not math.isfinite(self.importance_score):
            raise ValueError("importance_score must be finite")
        return self


class HTEResult(BaseModel):
    """Canonical artifact for heterogeneous treatment effect estimation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    method: CausalMethod
    ate: float
    ate_ci_lower: float
    ate_ci_upper: float
    ate_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)

    cate_values: list[float] = Field(default_factory=list)
    cate_std_values: list[float] = Field(default_factory=list)
    cate_ci_lower_values: list[float] = Field(default_factory=list)
    cate_ci_upper_values: list[float] = Field(default_factory=list)

    subgroup_effects: list[SubgroupEffect] = Field(default_factory=list)
    feature_importances: list[FeatureImportance] = Field(default_factory=list)

    n_samples: int = Field(default=0, ge=0)
    n_treated: int = Field(default=0, ge=0)
    n_control: int = Field(default=0, ge=0)
    n_features: int = Field(default=0, ge=0)
    feature_names: list[str] = Field(default_factory=list)

    econml_estimator_class: str = ""
    econml_params: dict[str, Any] = Field(default_factory=dict)
    model_fit_metrics: dict[str, float] = Field(default_factory=dict)

    feature_display_map: dict[str, str] = Field(default_factory=dict)
    feature_transformations: dict[str, str] = Field(default_factory=dict)

    causal_effect_report_ref: str | None = None
    cas_artifact_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "HTEResult":
        if self.n_samples == 0 and self.cate_values:
            self.n_samples = len(self.cate_values)
        if self.n_samples != len(self.cate_values):
            raise ValueError("n_samples must match cate_values length")

        if self.cate_std_values and len(self.cate_std_values) != self.n_samples:
            raise ValueError("cate_std_values length must match n_samples")
        if self.cate_ci_lower_values and len(self.cate_ci_lower_values) != self.n_samples:
            raise ValueError("cate_ci_lower_values length must match n_samples")
        if self.cate_ci_upper_values and len(self.cate_ci_upper_values) != self.n_samples:
            raise ValueError("cate_ci_upper_values length must match n_samples")

        if self.ate_ci_lower > self.ate_ci_upper:
            raise ValueError("ate_ci_lower must be <= ate_ci_upper")
        if not math.isfinite(self.ate):
            raise ValueError("ate must be finite")
        if not math.isfinite(self.ate_ci_lower) or not math.isfinite(self.ate_ci_upper):
            raise ValueError("ATE CI bounds must be finite")
        return self


class TargetingRule(BaseModel):
    """Operational rule for targeting treatment to high-value units."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    predicate_human: str | None = None
    priority: int = Field(ge=1)
    expected_cate: float
    expected_cost_per_unit: float = Field(ge=0.0)
    n_eligible_units: int = Field(ge=0)
    cumulative_budget_share: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_numbers(self) -> "TargetingRule":
        if not math.isfinite(self.expected_cate):
            raise ValueError("expected_cate must be finite")
        if not math.isfinite(self.expected_cost_per_unit):
            raise ValueError("expected_cost_per_unit must be finite")
        return self


class PolicyRecommendation(BaseModel):
    """Budget-aware targeting recommendation derived from an HTE result."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    hte_result_ref: str | None = None
    budget_constraint: float | None = Field(default=None, ge=0.0)
    optimization_objective: str = "maximize_total_effect"

    targeting_rules: list[TargetingRule] = Field(default_factory=list)
    total_expected_effect: float = 0.0
    total_cost: float = 0.0
    n_targeted_units: int = Field(default=0, ge=0)
    n_total_units: int = Field(default=0, ge=0)
    targeting_efficiency: float | None = None

    tree_depth: int | None = Field(default=None, ge=1)
    tree_n_leaves: int | None = Field(default=None, ge=1)

    cas_artifact_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_totals(self) -> "PolicyRecommendation":
        if not math.isfinite(self.total_expected_effect):
            raise ValueError("total_expected_effect must be finite")
        if not math.isfinite(self.total_cost):
            raise ValueError("total_cost must be finite")
        if self.n_targeted_units > self.n_total_units and self.n_total_units > 0:
            raise ValueError("n_targeted_units cannot exceed n_total_units")
        if self.targeting_efficiency is None and self.total_cost > 0:
            self.targeting_efficiency = self.total_expected_effect / self.total_cost
        return self


def persist_hte_result(
    store: ArtifactStore,
    result: HTEResult,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.hte_result",
    schema_version: str = "1.0",
) -> HTEResultRef:
    """Persist an HTE result and return its typed artifact reference."""
    ref = put_json_artifact(
        store,
        result.model_dump(mode="json"),
        kind="ir.hte_result",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return HTEResultRef.model_validate(ref)


def load_hte_result(store: ArtifactStore, ref: HTEResultRef) -> HTEResult:
    """Load hte result."""
    payload = get_json_artifact(store, ref.artifact_id)
    return HTEResult.model_validate(payload)


def persist_policy_recommendation(
    store: ArtifactStore,
    recommendation: PolicyRecommendation,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.policy_recommendation",
    schema_version: str = "1.0",
) -> PolicyRecommendationRef:
    """Persist a targeting recommendation derived from an HTE artifact."""
    ref = put_json_artifact(
        store,
        recommendation.model_dump(mode="json"),
        kind="ir.policy_recommendation",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return PolicyRecommendationRef.model_validate(ref)


def load_policy_recommendation(
    store: ArtifactStore,
    ref: PolicyRecommendationRef,
) -> PolicyRecommendation:
    """Load policy recommendation."""
    payload = get_json_artifact(store, ref.artifact_id)
    return PolicyRecommendation.model_validate(payload)


__all__ = [
    "SubgroupEffect",
    "FeatureImportance",
    "HTEResult",
    "TargetingRule",
    "PolicyRecommendation",
    "persist_hte_result",
    "load_hte_result",
    "persist_policy_recommendation",
    "load_policy_recommendation",
]
