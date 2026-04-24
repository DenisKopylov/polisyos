"""Algorithmic recourse and explanation contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir._validation import ensure_finite_numeric, ensure_unique_ids


class RecourseActionType(str, Enum):
    """Canonical action types for algorithmic recourse."""

    SET = "set"
    INCREASE = "increase"
    DECREASE = "decrease"
    TOGGLE = "toggle"


class RecourseFeasibility(str, Enum):
    """Feasibility status of a recourse plan."""

    FEASIBLE = "feasible"
    CONDITIONAL = "conditional"
    INFEASIBLE = "infeasible"


class RecourseAction(BaseModel):
    """One actionable change suggested by a recourse engine."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_path: str = Field(min_length=1)
    action_type: RecourseActionType
    from_value: str | int | bool | float | None = None
    to_value: str | int | bool | float | None = None
    cost: float | None = Field(default=None, ge=0.0)
    immutable: bool = False

    @model_validator(mode="after")
    def validate_action(self) -> RecourseAction:
        if self.cost is not None:
            ensure_finite_numeric(self.cost, field_name=f"{self.feature_path}.cost")
        if self.immutable and self.to_value is not None:
            raise ValueError("immutable recourse actions cannot set to_value")
        return self


class CounterfactualExplanation(BaseModel):
    """Counterfactual explanation anchored to a set of recourse actions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    explanation_id: str = Field(min_length=1)
    factual_outcome: str = Field(min_length=1)
    counterfactual_outcome: str = Field(min_length=1)
    changed_features: tuple[str, ...] = ()
    supporting_actions: list[RecourseAction] = Field(default_factory=list)
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_explanation(self) -> CounterfactualExplanation:
        ensure_unique_ids(
            self.changed_features,
            key_fn=lambda item: item,
            label="counterfactual changed_feature",
        )
        action_features = {action.feature_path for action in self.supporting_actions}
        if set(self.changed_features) - action_features:
            raise ValueError("changed_features must be backed by supporting_actions")
        return self


class ContrastiveExplanation(BaseModel):
    """Contrastive explanation for why one outcome happened instead of another."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    explanation_id: str = Field(min_length=1)
    factual_label: str = Field(min_length=1)
    foil_label: str = Field(min_length=1)
    decisive_factors: tuple[str, ...] = ()
    narrative: str | None = Field(None, max_length=600)

    @model_validator(mode="after")
    def validate_contrastive(self) -> ContrastiveExplanation:
        ensure_unique_ids(
            self.decisive_factors,
            key_fn=lambda item: item,
            label="contrastive decisive_factor",
        )
        return self


class RecoursePlan(BaseModel):
    """Actionable recourse plan with cost/robustness annotations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: str = Field(min_length=1)
    feasibility: RecourseFeasibility
    actions: list[RecourseAction] = Field(default_factory=list)
    total_cost: float | None = Field(default=None, ge=0.0)
    robustness_score: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_plan(self) -> RecoursePlan:
        if self.feasibility is not RecourseFeasibility.INFEASIBLE and not self.actions:
            raise ValueError("feasible/conditional recourse plans require at least one action")
        if self.total_cost is not None:
            ensure_finite_numeric(self.total_cost, field_name=f"{self.plan_id}.total_cost")
        if self.robustness_score is not None:
            ensure_finite_numeric(
                self.robustness_score,
                field_name=f"{self.plan_id}.robustness_score",
            )
        return self


class RecourseReport(BaseModel):
    """Frozen report contract for recourse and explanation outputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    subject_id: str | None = None
    plans: list[RecoursePlan] = Field(default_factory=list)
    counterfactual_explanations: list[CounterfactualExplanation] = Field(default_factory=list)
    contrastive_explanations: list[ContrastiveExplanation] = Field(default_factory=list)
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_report(self) -> RecourseReport:
        ensure_unique_ids(self.plans, key_fn=lambda item: item.plan_id, label="recourse plan_id")
        ensure_unique_ids(
            self.counterfactual_explanations,
            key_fn=lambda item: item.explanation_id,
            label="counterfactual explanation_id",
        )
        ensure_unique_ids(
            self.contrastive_explanations,
            key_fn=lambda item: item.explanation_id,
            label="contrastive explanation_id",
        )
        return self


__all__ = [
    "ContrastiveExplanation",
    "CounterfactualExplanation",
    "RecourseAction",
    "RecourseActionType",
    "RecourseFeasibility",
    "RecoursePlan",
    "RecourseReport",
]
