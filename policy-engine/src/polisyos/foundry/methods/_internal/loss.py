"""Legacy method facade for the named economics loss baseline."""

from polisyos.foundry.plugins.economics.baselines import normalized_income_budget_loss

policy_loss_fn = normalized_income_budget_loss

__all__ = ["policy_loss_fn"]
