import jax.numpy as jnp

from src.domain.state import GlobalState
from src.foundry.base import Mechanism


class TaxSubsidy(Mechanism):
    rate: float
    target_sector_mask: jnp.ndarray

    # Обновили init: принимаем **kwargs, чтобы игнорировать лишние параметры (например n_firms)
    def __init__(self, rate: float, n_agents: int, **kwargs):
        self.rate = rate
        self.target_sector_mask = jnp.ones(n_agents)

    def __call__(self, state: GlobalState, key) -> GlobalState:
        subsidy_amount = state.agents.income * self.rate * self.target_sector_mask
        total_cost = jnp.sum(subsidy_amount)

        new_income = state.agents.income + subsidy_amount
        new_balance = state.government_balance - total_cost

        new_agents = state.agents.replace(income=new_income)
        # replace работает, так как остальные поля (firms/market) просто копируются
        return state.replace(agents=new_agents, government_balance=new_balance)


class IncomeTax(Mechanism):
    rate: float

    def __init__(self, rate: float, n_agents: int, **kwargs):
        self.rate = rate

    def __call__(self, state: GlobalState, key) -> GlobalState:
        tax_amount = state.agents.income * self.rate
        total_revenue = jnp.sum(tax_amount)

        new_income = state.agents.income - tax_amount
        new_balance = state.government_balance + total_revenue

        new_agents = state.agents.replace(income=new_income)
        return state.replace(agents=new_agents, government_balance=new_balance)
