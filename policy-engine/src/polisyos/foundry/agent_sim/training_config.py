"""Public agent sim training config module API."""
from __future__ import annotations

from dataclasses import dataclass

from polisyos.foundry.contracts.fidelity import FidelityLevel


@dataclass(frozen=True)
class TrainingConfigBase:
    """Training config base public type."""
    n_episodes: int = 100
    steps_per_episode: int = 64
    horizon: int = 256
    gamma: float = 0.99
    gae_lambda: float = 0.95
    ppo_epochs: int = 4
    clip_epsilon: float = 0.2
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    learning_rate: float = 3e-4
    max_grad_norm: float = 1.0
    utility_type: str = "crra"
    fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID
    include_expectations: bool = True

    def common_kwargs(self) -> dict[str, object]:
        return {
            "n_episodes": self.n_episodes,
            "steps_per_episode": self.steps_per_episode,
            "horizon": self.horizon,
            "gamma": self.gamma,
            "gae_lambda": self.gae_lambda,
            "ppo_epochs": self.ppo_epochs,
            "clip_epsilon": self.clip_epsilon,
            "value_coef": self.value_coef,
            "entropy_coef": self.entropy_coef,
            "learning_rate": self.learning_rate,
            "max_grad_norm": self.max_grad_norm,
            "utility_type": self.utility_type,
            "fidelity": self.fidelity,
            "include_expectations": self.include_expectations,
        }


__all__ = ["TrainingConfigBase"]
