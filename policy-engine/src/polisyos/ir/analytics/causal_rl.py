"""Causal reinforcement-learning contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir._validation import ensure_disjoint_sets, ensure_finite_numeric, ensure_unique_ids


class CausalDecisionProcessType(str, Enum):
    """Decision-process families supported by the IR surface."""

    CAUSAL_MDP = "causal_mdp"
    CAUSAL_POMDP = "causal_pomdp"


class PolicyOptimizationObjective(str, Enum):
    """Optimization objective for causal-RL training/evaluation."""

    COUNTERFACTUAL_RETURN = "counterfactual_return"
    SAFE_IMPROVEMENT = "safe_improvement"
    OFF_POLICY_VALUE = "off_policy_value"


class GraphUpdateMode(str, Enum):
    """How online graph learning is incorporated into RL."""

    FROZEN = "frozen"
    PERIODIC = "periodic"
    EVERY_EPISODE = "every_episode"


class CounterfactualPolicyOptimizationSpec(BaseModel):
    """Optimization surface for counterfactual policy search."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    objective: PolicyOptimizationObjective
    evaluation_horizon: int = Field(ge=1)
    risk_aversion: float = Field(default=0.0, ge=0.0)
    rollout_budget: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_spec(self) -> CounterfactualPolicyOptimizationSpec:
        ensure_finite_numeric(self.risk_aversion, field_name="risk_aversion")
        return self


class OnlineGraphLearningSpec(BaseModel):
    """How graph updates happen during online causal-RL execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    update_mode: GraphUpdateMode = GraphUpdateMode.FROZEN
    update_interval_steps: int | None = Field(default=None, ge=1)
    max_graph_edits_per_update: int = Field(default=0, ge=0)
    exploration_budget: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def validate_graph_learning(self) -> OnlineGraphLearningSpec:
        ensure_finite_numeric(self.exploration_budget, field_name="exploration_budget")
        if self.update_mode is GraphUpdateMode.FROZEN:
            if self.update_interval_steps is not None or self.max_graph_edits_per_update != 0:
                raise ValueError(
                    "frozen graph-learning mode cannot declare update cadence or edits"
                )
        elif self.update_interval_steps is None:
            raise ValueError("non-frozen graph-learning mode requires update_interval_steps")
        return self


class CausalRLContract(BaseModel):
    """Contract surface for causal MDP/POMDP policy optimization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    contract_id: str = Field(min_length=1)
    process_type: CausalDecisionProcessType
    state_variables: tuple[str, ...] = Field(..., min_length=1)
    action_variables: tuple[str, ...] = Field(..., min_length=1)
    reward_variable: str = Field(min_length=1)
    latent_state_variables: tuple[str, ...] = ()
    confounder_variables: tuple[str, ...] = ()
    optimization: CounterfactualPolicyOptimizationSpec
    graph_learning: OnlineGraphLearningSpec = Field(default_factory=OnlineGraphLearningSpec)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_contract(self) -> CausalRLContract:
        ensure_unique_ids(self.state_variables, key_fn=lambda item: item, label="state variable")
        ensure_unique_ids(self.action_variables, key_fn=lambda item: item, label="action variable")
        ensure_unique_ids(
            self.latent_state_variables,
            key_fn=lambda item: item,
            label="latent state variable",
        )
        ensure_unique_ids(
            self.confounder_variables,
            key_fn=lambda item: item,
            label="confounder variable",
        )
        ensure_disjoint_sets(
            set(self.state_variables),
            set(self.action_variables),
            label="state and action variables",
        )
        return self


class CausalRLResult(BaseModel):
    """Frozen result contract for causal-RL runs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    contract_id: str = Field(min_length=1)
    policy_value_estimate: float
    off_policy_value: float | None = None
    regret_upper_bound: float | None = Field(default=None, ge=0.0)
    learned_graph_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result(self) -> CausalRLResult:
        for field_name in (
            "policy_value_estimate",
            "off_policy_value",
            "regret_upper_bound",
            "learned_graph_confidence",
        ):
            value = getattr(self, field_name)
            if value is not None:
                ensure_finite_numeric(value, field_name=field_name)
        return self


__all__ = [
    "CausalDecisionProcessType",
    "CausalRLContract",
    "CausalRLResult",
    "CounterfactualPolicyOptimizationSpec",
    "GraphUpdateMode",
    "OnlineGraphLearningSpec",
    "PolicyOptimizationObjective",
]
