"""Multiple-testing controls for DDM-15.7 calibration and diagnostics."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MultipleTestingPlan(BaseModel):
    """Documented budget split for a family of monitoring tests."""

    model_config = ConfigDict(extra="forbid")

    strategy: str = Field(min_length=1)
    system_alpha: float = Field(gt=0.0, lt=1.0)
    allocations: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _allocations_inside_budget(self) -> MultipleTestingPlan:
        total = sum(self.allocations.values())
        if total > self.system_alpha + 1e-12:
            raise ValueError("allocated alpha exceeds system_alpha")
        return self


class OnlineFDRDecision(BaseModel):
    """One online FDR test decision."""

    model_config = ConfigDict(extra="forbid")

    test_id: str = Field(min_length=1)
    p_value: float = Field(ge=0.0, le=1.0)
    alpha_spent: float = Field(gt=0.0, lt=1.0)
    rejected: bool
    wealth_after: float = Field(ge=0.0)
    discoveries: int = Field(ge=0)


class OnlineFDRController(BaseModel):
    """Small alpha-wealth controller for diagnostic online FDR streams."""

    model_config = ConfigDict(extra="forbid")

    alpha: float = Field(gt=0.0, lt=1.0)
    wealth: float = Field(default=0.0, ge=0.0)
    reward: float = Field(default=0.0, ge=0.0)
    tests_seen: int = Field(default=0, ge=0)
    discoveries: int = Field(default=0, ge=0)

    @classmethod
    def create(cls, *, alpha: float, initial_wealth: float | None = None) -> OnlineFDRController:
        """Create a conservative alpha-wealth controller."""

        wealth = alpha / 2.0 if initial_wealth is None else initial_wealth
        return cls(alpha=alpha, wealth=wealth, reward=alpha / 2.0)

    def test(self, *, test_id: str, p_value: float) -> OnlineFDRDecision:
        """Spend alpha on one hypothesis and update wealth after the decision."""

        alpha_spent = min(self.alpha, max(self.wealth / 2.0, self.alpha / 1000.0))
        rejected = p_value <= alpha_spent
        self.tests_seen += 1
        self.wealth = max(0.0, self.wealth - alpha_spent)
        if rejected:
            self.discoveries += 1
            self.wealth += self.reward
        return OnlineFDRDecision(
            test_id=test_id,
            p_value=p_value,
            alpha_spent=alpha_spent,
            rejected=rejected,
            wealth_after=self.wealth,
            discoveries=self.discoveries,
        )


def allocate_conservative_budget(
    *,
    system_alpha: float,
    test_ids: list[str],
) -> MultipleTestingPlan:
    """Allocate system alpha with a Bonferroni/union-bound split."""

    if system_alpha <= 0.0 or system_alpha >= 1.0:
        raise ValueError("system_alpha must be inside (0, 1)")
    if not test_ids:
        raise ValueError("at least one test id is required")
    unique_ids = sorted(set(test_ids))
    per_test_alpha = system_alpha / len(unique_ids)
    return MultipleTestingPlan(
        strategy="bonferroni_union_bound",
        system_alpha=system_alpha,
        allocations=dict.fromkeys(unique_ids, per_test_alpha),
    )
