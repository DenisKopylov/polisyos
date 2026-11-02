"""Public agent sim training config module API."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.foundry.contracts.fidelity import FidelityLevel


class _UnsupportedTrainingFidelityError(ValueError):
    """Refuse a trajectory whose execution law lacks a matching PPO likelihood."""

    code = "training_fidelity_unsupported"


def _require_supported_training_fidelity(fidelity: FidelityLevel) -> None:
    """Keep deterministic HARD evaluation separate from sampled-action training."""
    if type(fidelity) not in (FidelityLevel, str):
        raise _UnsupportedTrainingFidelityError("Training fidelity must name a supported profile")
    if fidelity not in (FidelityLevel.SURROGATE_FLUID, FidelityLevel.RELAXED_DISCRETE):
        raise _UnsupportedTrainingFidelityError(
            "Training requires fluid or relaxed fidelity. HARD_DISCRETE's deterministic mean "
            "transition does not execute the sampled action whose PPO likelihood is recorded. "
            "HARD evaluation and fluid/relaxed training remain available."
        )


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
