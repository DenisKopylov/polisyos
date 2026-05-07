"""Define heterogeneous treatment effect estimates and targeting recommendations."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir._internal.validation import (
    ensure_confidence_interval,
    ensure_finite_numeric,
    ensure_unique_ids,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.references import HTEResultRef, PolicyRecommendationRef

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal import CausalMethod
else:
    from polisyos.ir.analytics.causal import CausalMethod


class SubgroupEffect(BaseModel):
    """Estimated conditional treatment effect for one labeled subgroup."""

    model_config = ConfigDict(extra="forbid", frozen=True)

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
    def _validate_ci(self) -> SubgroupEffect:
        ensure_finite_numeric(self.cate_mean, field_name="cate_mean")
        ensure_finite_numeric(self.cate_std, field_name="cate_std")
        ensure_confidence_interval(
            (self.cate_ci_lower, self.cate_ci_upper),
            label="cate_ci",
            point_estimate=self.cate_mean,
            point_label="cate_mean",
        )
        return self


class FeatureImportance(BaseModel):
    """Ranking signal for a feature used in heterogeneous-effect modeling."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_name: str = Field(min_length=1)
    importance_score: float
    importance_rank: int = Field(ge=1)
    method: str = "tree_based"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_score(self) -> FeatureImportance:
        ensure_finite_numeric(self.importance_score, field_name="importance_score")
        return self


class HTEResult(BaseModel):
    """Canonical artifact for heterogeneous treatment effect estimation.

    The contract keeps list/dict containers for ABI compatibility, but derived
    fields are normalized before instantiation rather than by mutating the
    validated model.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, payload: Any) -> Any:
        return cls.normalize_payload(payload)

    @classmethod
    def normalize_payload(cls, payload: Any) -> Any:
        """Return an HTE payload with explicit derived defaults filled.

        This helper is the supported normalization boundary for loaded legacy
        payloads and construction helpers. Validators call it only to preserve
        dual-read compatibility; business code should prefer
        :meth:`from_estimates` when deriving fields such as ``n_samples``.
        """
        if not isinstance(payload, dict):
            return payload
        normalized = dict(payload)
        cate_values = normalized.get("cate_values")
        if (
            isinstance(cate_values, Sequence)
            and not isinstance(cate_values, (str, bytes, bytearray))
            and normalized.get("n_samples", 0) in {None, 0, ""}
        ):
            normalized["n_samples"] = len(cate_values)
        return normalized

    @classmethod
    def from_estimates(cls, **payload: Any) -> HTEResult:
        """Construct an HTE result after applying explicit derived defaults."""

        return cls.model_validate(cls.normalize_payload(payload))

    @model_validator(mode="after")
    def _validate_shapes(self) -> HTEResult:
        if self.n_samples != len(self.cate_values):
            raise ValueError("n_samples must match cate_values length")
        ensure_finite_numeric(self.ate, field_name="ate")
        ensure_confidence_interval(
            (self.ate_ci_lower, self.ate_ci_upper),
            label="ate_ci",
            point_estimate=self.ate,
            point_label="ate",
        )
        for index, cate in enumerate(self.cate_values):
            ensure_finite_numeric(cate, field_name=f"cate_values[{index}]")
        if self.cate_std_values and len(self.cate_std_values) != self.n_samples:
            raise ValueError("cate_std_values length must match n_samples")
        if self.cate_ci_lower_values and len(self.cate_ci_lower_values) != self.n_samples:
            raise ValueError("cate_ci_lower_values length must match n_samples")
        if self.cate_ci_upper_values and len(self.cate_ci_upper_values) != self.n_samples:
            raise ValueError("cate_ci_upper_values length must match n_samples")
        if bool(self.cate_ci_lower_values) != bool(self.cate_ci_upper_values):
            raise ValueError(
                "cate_ci_lower_values and cate_ci_upper_values must be provided together"
            )
        for index, cate_std in enumerate(self.cate_std_values):
            ensure_finite_numeric(cate_std, field_name=f"cate_std_values[{index}]")
        for index, (lower, upper) in enumerate(
            zip(self.cate_ci_lower_values, self.cate_ci_upper_values, strict=False)
        ):
            ensure_confidence_interval(
                (lower, upper),
                label=f"cate_ci[{index}]",
                point_estimate=self.cate_values[index],
                point_label=f"cate_values[{index}]",
            )
        if self.n_treated + self.n_control > self.n_samples:
            raise ValueError("n_treated + n_control cannot exceed n_samples")
        if self.feature_names and len(self.feature_names) != self.n_features:
            raise ValueError("feature_names length must match n_features")
        if not self.feature_names and self.n_features != 0:
            raise ValueError("n_features requires feature_names")
        ensure_unique_ids(self.feature_names, key_fn=lambda item: item, label="feature_name")
        ensure_unique_ids(
            self.subgroup_effects,
            key_fn=lambda item: item.subgroup_id,
            label="subgroup_effect subgroup_id",
        )
        ensure_unique_ids(
            self.feature_importances,
            key_fn=lambda item: item.feature_name,
            label="feature_importance feature_name",
        )
        ensure_unique_ids(
            self.feature_importances,
            key_fn=lambda item: item.importance_rank,
            label="feature_importance importance_rank",
        )
        for metric_name, metric_value in self.model_fit_metrics.items():
            ensure_finite_numeric(metric_value, field_name=f"model_fit_metrics.{metric_name}")
        return self


class TargetingRule(BaseModel):
    """Operational rule for targeting treatment to high-value units."""

    model_config = ConfigDict(extra="forbid", frozen=True)

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
    def _validate_numbers(self) -> TargetingRule:
        if not math.isfinite(self.expected_cate):
            raise ValueError("expected_cate must be finite")
        if not math.isfinite(self.expected_cost_per_unit):
            raise ValueError("expected_cost_per_unit must be finite")
        return self


class PolicyRecommendation(BaseModel):
    """Budget-aware targeting recommendation derived from an HTE result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, payload: Any) -> Any:
        return cls.normalize_payload(payload)

    @classmethod
    def normalize_payload(cls, payload: Any) -> Any:
        """Return a recommendation payload with explicit derived efficiency."""

        if not isinstance(payload, dict):
            return payload
        normalized = dict(payload)
        if normalized.get("targeting_efficiency") is not None:
            return normalized
        try:
            total_cost = float(normalized.get("total_cost", 0.0) or 0.0)
            total_effect = float(normalized.get("total_expected_effect", 0.0) or 0.0)
        except (TypeError, ValueError):
            return normalized
        if total_cost > 0.0:
            normalized["targeting_efficiency"] = total_effect / total_cost
        return normalized

    @classmethod
    def from_totals(cls, **payload: Any) -> PolicyRecommendation:
        """Construct a recommendation after applying explicit derived defaults."""

        return cls.model_validate(cls.normalize_payload(payload))

    @model_validator(mode="after")
    def _validate_totals(self) -> PolicyRecommendation:
        ensure_finite_numeric(self.total_expected_effect, field_name="total_expected_effect")
        ensure_finite_numeric(self.total_cost, field_name="total_cost")
        if self.n_targeted_units > self.n_total_units and self.n_total_units > 0:
            raise ValueError("n_targeted_units cannot exceed n_total_units")
        if self.targeting_efficiency is not None:
            ensure_finite_numeric(self.targeting_efficiency, field_name="targeting_efficiency")
        if self.total_cost == 0.0 and self.targeting_efficiency not in {None, 0.0}:
            raise ValueError("targeting_efficiency must be None or 0.0 when total_cost is zero")
        if self.total_cost > 0.0 and self.targeting_efficiency is not None:
            expected_efficiency = self.total_expected_effect / self.total_cost
            if not math.isclose(
                self.targeting_efficiency,
                expected_efficiency,
                rel_tol=1.0e-12,
                abs_tol=1.0e-12,
            ):
                raise ValueError(
                    "targeting_efficiency must equal total_expected_effect / total_cost"
                )
        if (
            self.budget_constraint is not None
            and self.total_cost > self.budget_constraint + 1.0e-12
        ):
            raise ValueError("total_cost cannot exceed budget_constraint")
        ensure_unique_ids(
            self.targeting_rules,
            key_fn=lambda item: item.rule_id,
            label="targeting_rule rule_id",
        )
        ensure_unique_ids(
            self.targeting_rules,
            key_fn=lambda item: item.priority,
            label="targeting_rule priority",
        )
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
    "FeatureImportance",
    "HTEResult",
    "PolicyRecommendation",
    "SubgroupEffect",
    "TargetingRule",
    "load_hte_result",
    "load_policy_recommendation",
    "persist_hte_result",
    "persist_policy_recommendation",
]
