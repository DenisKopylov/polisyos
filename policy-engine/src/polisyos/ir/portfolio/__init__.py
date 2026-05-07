"""Represent candidate policy portfolios and pairwise interaction assumptions."""

from __future__ import annotations

from enum import Enum
from functools import cached_property
from typing import TYPE_CHECKING

from pydantic import Field, model_validator

from polisyos.ir.governance.policy_spec import (
    ARTIFACT_ID_PATTERN,
    ID_PATTERN,
    SCHEMA_VERSION_PATTERN,
    PolicySpec,
)
from polisyos.ir.kernel.base import KernelModel

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.ir.types import TranslatableString
else:
    from polisyos.ir.types import TranslatableString


class InteractionType(str, Enum):
    """Qualitative label for how two policies interact in a portfolio."""

    SYNERGY = "synergy"
    NEUTRAL = "neutral"
    CANNIBALIZATION = "cannibalization"
    SUBSTITUTION = "substitution"
    CONFLICT = "conflict"


class InteractionMode(str, Enum):
    """Interaction aggregation mode for portfolio scoring."""

    PAIRWISE_ADDITIVE = "pairwise_additive"
    MULTIPLICATIVE = "multiplicative"


class PolicyInteraction(KernelModel):
    """Pairwise interaction metadata between two portfolio policies."""

    policy_a_id: str = Field(..., pattern=ID_PATTERN)
    policy_b_id: str = Field(..., pattern=ID_PATTERN)
    interaction_type: InteractionType = Field(default=InteractionType.NEUTRAL)
    coefficient: float = Field(
        default=1.0,
        description=(
            "Relative interaction coefficient. 1.0=neutral, >1.0=synergy, <1.0=negative effect."
        ),
    )
    symmetric: bool = Field(default=True)
    evidence_ref: str | None = Field(default=None, pattern=ARTIFACT_ID_PATTERN)
    notes: list[str] = Field(default_factory=list, max_length=10)


class InteractionMatrix(KernelModel):
    """Matrix-like interaction layer with clamped additive pairwise effects."""

    interactions: list[PolicyInteraction] = Field(default_factory=list)
    default_interaction: InteractionType = Field(default=InteractionType.NEUTRAL)
    default_coefficient: float = Field(default=1.0)
    max_pairwise_relative_effect: float = Field(
        default=0.5,
        ge=0.0,
        description=(
            "Clamp for additive pairwise delta as share of average base benefit per pair."
        ),
    )
    legacy_min_multiplier: float = Field(
        default=0.25,
        gt=0.0,
        description="Lower clamp for legacy multiplicative interaction mode.",
    )
    legacy_max_multiplier: float = Field(
        default=2.0,
        gt=0.0,
        description="Upper clamp for legacy multiplicative interaction mode.",
    )

    @cached_property
    def _interaction_index(self) -> dict[tuple[str, str], PolicyInteraction]:
        index: dict[tuple[str, str], PolicyInteraction] = {}
        for interaction in self.interactions:
            key = (interaction.policy_a_id, interaction.policy_b_id)
            index.setdefault(key, interaction)
            if interaction.symmetric:
                reverse_key = (interaction.policy_b_id, interaction.policy_a_id)
                index.setdefault(reverse_key, interaction)
        return index

    def get_interaction(self, policy_a_id: str, policy_b_id: str) -> PolicyInteraction | None:
        return self._interaction_index.get((policy_a_id, policy_b_id))

    def get_coefficient(self, policy_a_id: str, policy_b_id: str) -> float:
        interaction = self.get_interaction(policy_a_id, policy_b_id)
        if interaction is None:
            return self.default_coefficient
        return interaction.coefficient

    def pairwise_delta(
        self,
        *,
        policy_a_id: str,
        policy_b_id: str,
        base_a: float,
        base_b: float,
    ) -> float:
        """Additive pairwise effect with relative clamp.

        Delta_ij = clamp((coef_ij - 1) * avg(base_i, base_j), ± cap).
        """

        coefficient = self.get_coefficient(policy_a_id, policy_b_id)
        average_base = 0.5 * (float(base_a) + float(base_b))
        raw_delta = (coefficient - 1.0) * average_base

        cap = self.max_pairwise_relative_effect * abs(average_base)
        if raw_delta > cap:
            return cap
        if raw_delta < -cap:
            return -cap
        return raw_delta

    def clamp_multiplier(self, multiplier: float) -> float:
        lower = min(self.legacy_min_multiplier, self.legacy_max_multiplier)
        upper = max(self.legacy_min_multiplier, self.legacy_max_multiplier)
        if multiplier < lower:
            return lower
        if multiplier > upper:
            return upper
        return multiplier

    def completeness_warnings(
        self,
        policy_ids: list[str],
        *,
        min_non_neutral_density: float = 0.1,
    ) -> list[str]:
        n = len(policy_ids)
        total_pairs = (n * (n - 1)) // 2
        if total_pairs <= 0:
            return []

        non_neutral_pairs = 0
        seen_pairs: set[tuple[str, str]] = set()
        for interaction in self.interactions:
            pair = tuple(sorted((interaction.policy_a_id, interaction.policy_b_id)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            if abs(interaction.coefficient - self.default_coefficient) > 1e-12:
                non_neutral_pairs += 1

        density = non_neutral_pairs / total_pairs
        if density >= min_non_neutral_density:
            return []
        return [
            (
                "interaction matrix density is low "
                f"({density:.2%}); verify that key synergy/cannibalization pairs were not omitted"
            )
        ]


MAX_PORTFOLIO_POLICIES = 20


class PolicyPortfolio(KernelModel):
    """Bundle a feasible policy set plus pairwise interaction rules for portfolio search.

    Use ``policies`` for inline candidate specs, ``policy_refs`` when candidates
    are stored externally, and ``interaction_matrix`` plus cardinality/exclusion
    constraints to evaluate portfolio feasibility and total benefit.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)

    portfolio_id: str = Field(..., pattern=ID_PATTERN)
    problem_frame_ref: str | None = Field(default=None, pattern=ARTIFACT_ID_PATTERN)

    policies: list[PolicySpec] = Field(default_factory=list, max_length=MAX_PORTFOLIO_POLICIES)
    policy_refs: list[str] = Field(default_factory=list)

    interaction_matrix: InteractionMatrix = Field(default_factory=InteractionMatrix)

    max_active_policies: int | None = Field(default=None, ge=1)
    total_budget_constraint: float | None = Field(default=None, ge=0.0)
    required_policies: list[str] = Field(default_factory=list)
    excluded_pairs: list[tuple[str, str]] = Field(default_factory=list)

    name: TranslatableString | None = None
    description: str | None = Field(default=None, max_length=2000)
    labels: list[str] = Field(default_factory=list, max_length=20)
    notes: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_portfolio(self) -> PolicyPortfolio:
        policy_ids = [policy.policy_id for policy in self.policies]
        unique_ids = set(policy_ids)
        if len(unique_ids) != len(policy_ids):
            raise ValueError("policies contain duplicate policy_id")

        if (
            self.max_active_policies is not None
            and len(self.required_policies) > self.max_active_policies
        ):
            raise ValueError("required_policies cannot exceed max_active_policies")

        if self.policies:
            for req in self.required_policies:
                if req not in unique_ids:
                    raise ValueError(f"required_policy '{req}' not found in policies")

            for left, right in self.excluded_pairs:
                if left not in unique_ids or right not in unique_ids:
                    raise ValueError(f"excluded_pair ({left}, {right}) references unknown policy")

            for interaction in self.interaction_matrix.interactions:
                if interaction.policy_a_id not in unique_ids:
                    raise ValueError(
                        f"interaction references unknown policy: {interaction.policy_a_id}"
                    )
                if interaction.policy_b_id not in unique_ids:
                    raise ValueError(
                        f"interaction references unknown policy: {interaction.policy_b_id}"
                    )

        return self

    @property
    def policy_ids(self) -> list[str]:
        return [policy.policy_id for policy in self.policies]

    @cached_property
    def _excluded_pair_set(self) -> set[frozenset[str]]:
        return {frozenset(pair) for pair in self.excluded_pairs}

    def is_valid_combination(self, active_policy_ids: set[str]) -> bool:
        if (
            self.max_active_policies is not None
            and len(active_policy_ids) > self.max_active_policies
        ):
            return False

        for req in self.required_policies:
            if req not in active_policy_ids:
                return False

        return all(not pair.issubset(active_policy_ids) for pair in self._excluded_pair_set)

    def total_benefit(
        self,
        base_benefits: Mapping[str, float],
        *,
        active_policy_ids: set[str] | None = None,
        interaction_mode: InteractionMode | str = InteractionMode.PAIRWISE_ADDITIVE,
    ) -> float:
        active = set(active_policy_ids or self.policy_ids)
        filtered_active = [policy_id for policy_id in sorted(active) if policy_id in base_benefits]
        try:
            mode = (
                interaction_mode
                if isinstance(interaction_mode, InteractionMode)
                else InteractionMode(interaction_mode)
            )
        except ValueError as exc:
            raise ValueError(
                "interaction_mode must be one of: pairwise_additive, multiplicative"
            ) from exc

        if mode is InteractionMode.PAIRWISE_ADDITIVE:
            base_total = sum(float(base_benefits[policy_id]) for policy_id in filtered_active)
            interaction_total = 0.0

            for idx, policy_a_id in enumerate(filtered_active):
                for policy_b_id in filtered_active[idx + 1 :]:
                    interaction_total += self.interaction_matrix.pairwise_delta(
                        policy_a_id=policy_a_id,
                        policy_b_id=policy_b_id,
                        base_a=float(base_benefits[policy_a_id]),
                        base_b=float(base_benefits[policy_b_id]),
                    )
            return base_total + interaction_total

        if mode is InteractionMode.MULTIPLICATIVE:
            total = 0.0
            for policy_a_id in filtered_active:
                multiplier = 1.0
                for policy_b_id in filtered_active:
                    if policy_b_id == policy_a_id:
                        continue
                    multiplier *= self.interaction_matrix.get_coefficient(policy_a_id, policy_b_id)
                    multiplier = self.interaction_matrix.clamp_multiplier(multiplier)
                total += float(base_benefits[policy_a_id]) * multiplier
            return total

        raise ValueError("interaction_mode must be one of: pairwise_additive, multiplicative")

    def completeness_warnings(self, *, min_non_neutral_density: float = 0.1) -> list[str]:
        return self.interaction_matrix.completeness_warnings(
            self.policy_ids,
            min_non_neutral_density=min_non_neutral_density,
        )


__all__ = [
    "MAX_PORTFOLIO_POLICIES",
    "InteractionMatrix",
    "InteractionType",
    "PolicyInteraction",
    "PolicyPortfolio",
]
