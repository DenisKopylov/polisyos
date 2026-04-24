"""Public agent base module API."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ObjectiveSpec, ProblemDomain, ProblemFrame
from polisyos.ir.model_spec import AgentConfig, EnvironmentConfig, ModelSpec
from polisyos.ir.trinity import TrinityBundle

__all__ = ["BaseAgent", "MockAgent"]


class BaseAgent(ABC):
    """Base agent public type."""

    @abstractmethod
    def decide(self, step: int, context_df) -> TrinityBundle:
        """Produce a canonical TrinityBundle decision artifact."""
        raise NotImplementedError


@dataclass
class MockAgent(BaseAgent):
    """Deterministic fallback agent for local testing."""

    def decide(self, step: int, context_df) -> TrinityBundle:
        # Local fallback stays intentionally simple and deterministic.
        problem_frame = ProblemFrame(
            problem_id=f"problem_step_{step}",
            domain=ProblemDomain.CUSTOM,
            objectives=[
                ObjectiveSpec(
                    objective_id="objective_primary",
                    metric_id="avg_income",
                    direction="maximize",
                )
            ],
            narrative=f"Auto-generated policy draft for step {step}",
            labels=["scientist", "mock"],
        )
        policy_spec = PolicySpec(
            policy_id=f"policy_step_{step}",
            interventions=[
                InterventionSpec(
                    intervention_id=f"intervention_step_{step}",
                    kind="tax_subsidy",
                    target={
                        "kind": "predicate",
                        "field": "id",
                        "operator": "==",
                        "value": "all",
                    },
                    schedule={"start_step": 0, "duration_steps": 1},
                    params={"rate": "0.1"},
                )
            ],
            labels=["scientist", "mock"],
        )
        model_spec = ModelSpec(
            model_id=f"model_step_{step}",
            data_snapshot_ref=f"sha256:{'0' * 64}",
            agent_config=AgentConfig(total_agents=1000, max_agents=1000),
            environment_config=EnvironmentConfig(random_seed=42, stochastic=True),
            labels=["scientist", "mock"],
        )
        return TrinityBundle(
            schema_version="1.0",
            problem_frame=problem_frame,
            policy_spec=policy_spec,
            model_spec=model_spec,
        )
