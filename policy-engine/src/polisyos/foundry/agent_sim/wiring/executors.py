"""Apply synthetic population, graph, and distribution updates to `GlobalState`.

These executors own simulation dynamics only: they transform an in-memory
state snapshot and return runtime metrics. They do not fetch observations or
compute measurement loss, which keeps the agent-sim dynamics boundary separate
from calibration/reporting code.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jax.numpy as jnp
import numpy as np

from polisyos.foundry.agent_sim.distribution_mechanisms import (
    DistributionAwareTaxMechanism,
    TargetedTransferMechanism,
)
from polisyos.foundry.agent_sim.distributions import (
    DistributionState,
    compute_bottom_share,
    compute_gini_hard,
    compute_palma_ratio,
    compute_percentile_ratios,
    compute_quantiles_hard,
    compute_ranks_hard,
    compute_top_share,
)
from polisyos.foundry.agent_sim.graphs import EdgeList, compute_graph_metrics
from polisyos.foundry.contracts.fidelity import FidelityLevel
from polisyos.foundry.contracts.state import (
    AgentSimRuntimeState,
    GlobalState,
)
from polisyos.ir.observation.contracts import MultiplexGraphLayerId

from .contracts import (
    FirmLifecycleEventBatch,
    FirmLifecycleEventType,
    InterventionMechanismConfig,
    ProcurementShockBatch,
    multiplex_layer_code,
)


def _ensure_runtime(state: GlobalState, *, n_quantiles: int) -> GlobalState:
    if state.agent_sim_runtime is not None:
        return state
    return state.replace(
        agent_sim_runtime=AgentSimRuntimeState.empty(
            state.agents.size,
            state.firms.size,
            n_quantiles=n_quantiles,
        )
    )


def _agent_household_cell_ids(state: GlobalState) -> jnp.ndarray:
    values = state.agents.household_cell_id
    if values is None:
        return jnp.full((state.agents.size,), -1, dtype=jnp.int32)
    return values


def _firm_active(state: GlobalState) -> jnp.ndarray:
    values = state.firms.active
    if values is None:
        return jnp.ones((state.firms.size,), dtype=jnp.bool_)
    return values


def _firm_ids(state: GlobalState) -> jnp.ndarray:
    values = state.firms.firm_id
    if values is None:
        return jnp.arange(state.firms.size, dtype=jnp.int32)
    return values


def _firm_cell_ids(state: GlobalState) -> jnp.ndarray:
    values = state.firms.cell_id
    if values is None:
        return jnp.full((state.firms.size,), -1, dtype=jnp.int32)
    return values


def _firm_type_ids(state: GlobalState) -> jnp.ndarray:
    values = state.firms.firm_type_id
    if values is None:
        return jnp.zeros((state.firms.size,), dtype=jnp.int32)
    return values


def _segment_sum(
    values: jnp.ndarray,
    indices: jnp.ndarray,
    n_segments: int,
    *,
    mask: jnp.ndarray | None = None,
) -> jnp.ndarray:
    if n_segments <= 0:
        return jnp.zeros((0,), dtype=values.dtype)
    if mask is None:
        mask = jnp.ones(indices.shape[0], dtype=jnp.bool_)
    valid = mask & (indices >= 0) & (indices < n_segments)
    safe_indices = jnp.where(valid, indices, 0)
    safe_values = jnp.where(valid, values, 0.0)
    return jnp.bincount(safe_indices, weights=safe_values, length=n_segments)


def _agent_residence_cell_ids(state: GlobalState) -> jnp.ndarray:
    household_cell_ids = _agent_household_cell_ids(state)
    if state.household_cells is None:
        return household_cell_ids
    n_household_cells = int(state.household_cells.size)
    valid = (household_cell_ids >= 0) & (household_cell_ids < n_household_cells)
    safe_ids = jnp.where(valid, household_cell_ids, 0)
    cell_ids = state.household_cells.cell_id[safe_ids]
    return jnp.where(valid, cell_ids, -1)


def _resolve_agent_mask(
    state: GlobalState,
    config: InterventionMechanismConfig,
) -> jnp.ndarray:
    mask = state.agents.active
    household_cell_ids = _agent_household_cell_ids(state)
    residence_cell_ids = _agent_residence_cell_ids(state)
    if config.target_household_cell_ids:
        values = jnp.asarray(config.target_household_cell_ids, dtype=jnp.int32)
        mask = mask & jnp.isin(household_cell_ids, values)
    if config.target_cell_ids:
        values = jnp.asarray(config.target_cell_ids, dtype=jnp.int32)
        mask = mask & jnp.isin(residence_cell_ids, values)
    if config.target_region_codes and state.cells is not None:
        values = jnp.asarray(config.target_region_codes, dtype=jnp.int32)
        valid = (residence_cell_ids >= 0) & (residence_cell_ids < state.cells.size)
        safe_ids = jnp.where(valid, residence_cell_ids, 0)
        regions = state.cells.region_code[safe_ids]
        mask = mask & valid & jnp.isin(regions, values)
    if config.target_sector_ids and state.cells is not None:
        values = jnp.asarray(config.target_sector_ids, dtype=jnp.int32)
        valid = (residence_cell_ids >= 0) & (residence_cell_ids < state.cells.size)
        safe_ids = jnp.where(valid, residence_cell_ids, 0)
        sectors = state.cells.sector_id[safe_ids]
        mask = mask & valid & jnp.isin(sectors, values)
    return mask


def _resolve_firm_mask(
    state: GlobalState,
    config: InterventionMechanismConfig,
) -> jnp.ndarray:
    mask = _firm_active(state)
    firm_ids = _firm_ids(state)
    cell_ids = _firm_cell_ids(state)
    if config.target_firm_ids:
        values = jnp.asarray(config.target_firm_ids, dtype=jnp.int32)
        mask = mask & jnp.isin(firm_ids, values)
    if config.target_cell_ids:
        values = jnp.asarray(config.target_cell_ids, dtype=jnp.int32)
        mask = mask & jnp.isin(cell_ids, values)
    if config.target_region_codes and state.cells is not None:
        values = jnp.asarray(config.target_region_codes, dtype=jnp.int32)
        valid = (cell_ids >= 0) & (cell_ids < state.cells.size)
        safe_ids = jnp.where(valid, cell_ids, 0)
        regions = state.cells.region_code[safe_ids]
        mask = mask & valid & jnp.isin(regions, values)
    if config.target_sector_ids and state.cells is not None:
        values = jnp.asarray(config.target_sector_ids, dtype=jnp.int32)
        valid = (cell_ids >= 0) & (cell_ids < state.cells.size)
        safe_ids = jnp.where(valid, cell_ids, 0)
        sectors = state.cells.sector_id[safe_ids]
        mask = mask & valid & jnp.isin(sectors, values)
    return mask


def _compute_distribution_state(
    state: GlobalState,
    *,
    active_mask: jnp.ndarray | None = None,
    n_quantiles: int,
) -> DistributionState:
    active = state.agents.active if active_mask is None else active_mask
    return DistributionState(
        last_update_step=state.step,
        wealth_quantiles=compute_quantiles_hard(state.agents.savings, active, n_quantiles),
        income_quantiles=compute_quantiles_hard(state.agents.income, active, n_quantiles),
        consumption_quantiles=compute_quantiles_hard(
            state.agents.consumption,
            active,
            n_quantiles,
        ),
        wealth_ranks=compute_ranks_hard(state.agents.savings, active),
        income_ranks=compute_ranks_hard(state.agents.income, active),
        gini_wealth=compute_gini_hard(state.agents.savings, active),
        gini_income=compute_gini_hard(state.agents.income, active),
        top_10_share=compute_top_share(state.agents.income, active, 0.10),
        bottom_50_share=compute_bottom_share(state.agents.income, active, 0.50),
    )


def _project_multiscale(
    state: GlobalState,
    *,
    income_delta: jnp.ndarray | None = None,
    firm_distress: jnp.ndarray | None = None,
) -> GlobalState:
    agents = state.agents
    if income_delta is None:
        income_delta = jnp.zeros_like(agents.income)

    if state.household_cells is not None:
        household_ids = _agent_household_cell_ids(state)
        n_household_cells = int(state.household_cells.size)
        household_mask = agents.active & (household_ids >= 0) & (household_ids < n_household_cells)
        household_count = _segment_sum(
            jnp.ones_like(agents.income),
            household_ids,
            n_household_cells,
            mask=household_mask,
        )
        income_sum = _segment_sum(
            agents.income,
            household_ids,
            n_household_cells,
            mask=household_mask,
        )
        disposable_income = income_sum / jnp.maximum(household_count, 1.0)
        positive_transfer = jnp.maximum(income_delta, 0.0)
        transfer_sum = _segment_sum(
            positive_transfer,
            household_ids,
            n_household_cells,
            mask=household_mask,
        )
        transfer_intensity = transfer_sum / jnp.maximum(household_count, 1.0)
        median_income = compute_quantiles_hard(agents.income, agents.active, 2)[0]
        poverty_threshold = 0.6 * median_income
        poor_sum = _segment_sum(
            (agents.income < poverty_threshold).astype(jnp.float32),
            household_ids,
            n_household_cells,
            mask=household_mask,
        )
        poverty_rate = poor_sum / jnp.maximum(household_count, 1.0)
        state = state.replace(
            household_cells=state.household_cells.replace(
                household_count=household_count,
                disposable_income=disposable_income,
                poverty_rate=poverty_rate,
                transfer_intensity=transfer_intensity,
            )
        )

    if state.cells is None:
        return state

    n_cells = int(state.cells.size)
    residence_cell_ids = _agent_residence_cell_ids(state)
    population_mask = agents.active & (residence_cell_ids >= 0) & (residence_cell_ids < n_cells)
    population = _segment_sum(
        jnp.ones_like(agents.income),
        residence_cell_ids,
        n_cells,
        mask=population_mask,
    )

    firm_mask = _firm_active(state)
    firm_cell_ids = _firm_cell_ids(state)
    valid_firm_cells = firm_mask & (firm_cell_ids >= 0) & (firm_cell_ids < n_cells)
    firm_count = _segment_sum(
        jnp.ones_like(state.firms.cash),
        firm_cell_ids,
        n_cells,
        mask=valid_firm_cells,
    )

    employer_slots = agents.employer_id
    valid_employers = (
        agents.active
        & agents.is_employed
        & (employer_slots >= 0)
        & (employer_slots < state.firms.size)
    )
    safe_employers = jnp.where(valid_employers, employer_slots, 0)
    employer_cells = firm_cell_ids[safe_employers]
    employed_mask = valid_employers & firm_mask[safe_employers]
    employment = _segment_sum(
        jnp.ones_like(agents.income),
        employer_cells,
        n_cells,
        mask=employed_mask,
    )

    output_signal = state.firms.inventory + state.firms.productivity * (1.0 + state.firms.labor_count)
    output = _segment_sum(
        output_signal,
        firm_cell_ids,
        n_cells,
        mask=valid_firm_cells,
    )
    distress_signal = jnp.maximum(-state.firms.cash, 0.0) + 0.01 * jnp.maximum(state.firms.debt, 0.0)
    if firm_distress is not None:
        distress_signal = distress_signal + firm_distress
    distress_sum = _segment_sum(
        distress_signal,
        firm_cell_ids,
        n_cells,
        mask=valid_firm_cells,
    )
    distress_score = distress_sum / jnp.maximum(firm_count, 1.0)

    return state.replace(
        cells=state.cells.replace(
            population=population,
            employment=employment,
            output=output,
            distress_score=distress_score,
            firm_count=firm_count,
        )
    )


class _DistributionMechanismStateAdapter:
    def __init__(self, base_state: GlobalState):
        self.base_state = base_state

    @property
    def agents(self):
        return self.base_state.agents

    @property
    def distributions(self):
        runtime = self.base_state.agent_sim_runtime
        if runtime is None:
            raise ValueError("agent_sim_runtime is required for distribution mechanisms")
        return runtime.household_distribution

    def replace(self, **updates):
        base = self.base_state
        if "agents" in updates:
            base = base.replace(agents=updates["agents"])
        if "distributions" in updates:
            runtime = base.agent_sim_runtime
            if runtime is None:
                raise ValueError("agent_sim_runtime is required for distribution mechanisms")
            base = base.replace(
                agent_sim_runtime=runtime.replace(
                    household_distribution=updates["distributions"]
                )
            )
        return _DistributionMechanismStateAdapter(base)


def _with_distribution(state: GlobalState, distribution: DistributionState) -> GlobalState:
    runtime = state.agent_sim_runtime
    if runtime is None:
        raise ValueError("agent_sim_runtime is required for distribution updates")
    return state.replace(
        agent_sim_runtime=runtime.replace(household_distribution=distribution)
    )


@dataclass
class ContractsPopulationAwareExecutor:
    """Advance demographic and firm-lifecycle state while preserving slot projections.

    The executor updates synthetic agent/firm microstate, optionally projects
    derived cell/household-cell aggregates, and returns operational metrics for
    applied births, migrations, entries, exits, and slot overflow.
    """

    age_increment: int = 1
    birth_income: float = 0.0
    birth_skill_level: float = 1.0

    def apply(
        self,
        state: GlobalState,
        *,
        births_by_household_cell: jnp.ndarray | np.ndarray | None = None,
        migration_targets: jnp.ndarray | np.ndarray | None = None,
        firm_events: FirmLifecycleEventBatch | None = None,
        project: bool = True,
        fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID,
    ) -> tuple[GlobalState, dict[str, Any]]:
        """Apply one demographic/lifecycle update without incrementing `state.step`.

        Args:
            state: Synthetic runtime state to transform.
            births_by_household_cell: Optional birth counts per household cell.
            migration_targets: Optional new household-cell assignment per agent.
            firm_events: Optional entry/exit/type-transition batch.
            project: Whether to refresh derived household/cell aggregates.
            fidelity: Accepted for executor API compatibility; currently
                ignored by this deterministic state update.

        Returns:
            `(next_state, metrics)` with population and firm lifecycle counters.
        """
        del fidelity
        agents = state.agents
        firms = state.firms
        metrics: dict[str, Any] = {}

        agents = agents.replace(
            age=jnp.where(agents.active, agents.age + int(self.age_increment), agents.age)
        )

        household_ids = _agent_household_cell_ids(state)
        if births_by_household_cell is not None:
            birth_counts = np.asarray(births_by_household_cell, dtype=np.int32).reshape(-1)
            available_slots = np.flatnonzero(~np.asarray(agents.active))
            requested = int(birth_counts.sum())
            assigned_household_ids = np.repeat(
                np.arange(birth_counts.shape[0], dtype=np.int32),
                birth_counts,
            )
            applied = min(requested, int(available_slots.shape[0]))
            if applied > 0:
                target_slots = available_slots[:applied]
                new_household_ids = jnp.asarray(assigned_household_ids[:applied], dtype=jnp.int32)
                slot_ids = jnp.asarray(target_slots, dtype=jnp.int32)
                agents = agents.replace(
                    active=jnp.asarray(agents.active).at[slot_ids].set(True),
                    age=jnp.asarray(agents.age).at[slot_ids].set(0),
                    skill_level=jnp.asarray(agents.skill_level).at[slot_ids].set(
                        float(self.birth_skill_level)
                    ),
                    income=jnp.asarray(agents.income).at[slot_ids].set(float(self.birth_income)),
                    reported_income=jnp.asarray(agents.reported_income).at[slot_ids].set(
                        float(self.birth_income)
                    ),
                    savings=jnp.asarray(agents.savings).at[slot_ids].set(0.0),
                    consumption=jnp.asarray(agents.consumption).at[slot_ids].set(0.0),
                    risk_aversion=jnp.asarray(agents.risk_aversion).at[slot_ids].set(0.5),
                    is_employed=jnp.asarray(agents.is_employed).at[slot_ids].set(False),
                    employer_id=jnp.asarray(agents.employer_id).at[slot_ids].set(-1),
                    household_cell_id=jnp.asarray(household_ids).at[slot_ids].set(new_household_ids),
                )
                household_ids = agents.household_cell_id
            metrics["population/births_requested"] = requested
            metrics["population/births_applied"] = applied
            metrics["population/births_dropped"] = requested - applied

        if migration_targets is not None:
            targets = jnp.asarray(migration_targets, dtype=jnp.int32)
            migrate_mask = agents.active & (targets >= 0)
            household_ids = household_ids if household_ids is not None else _agent_household_cell_ids(state)
            household_ids = jnp.where(migrate_mask, targets, household_ids)
            agents = agents.replace(household_cell_id=household_ids)
            metrics["population/migrations_applied"] = jnp.sum(migrate_mask.astype(jnp.int32))

        firm_active = _firm_active(state)
        firm_ids = _firm_ids(state)
        firm_cell_ids = _firm_cell_ids(state)
        firm_type_ids = _firm_type_ids(state)
        if firm_events is not None:
            event_type = np.asarray(firm_events.event_type, dtype=np.int32)
            ext_firm_ids = np.asarray(firm_events.firm_id, dtype=np.int32)
            event_cells = np.asarray(firm_events.cell_id, dtype=np.int32)
            event_types = np.asarray(firm_events.firm_type_id, dtype=np.int32)
            event_sectors = np.asarray(firm_events.sector_id, dtype=np.int32)
            productivity = np.asarray(firm_events.productivity, dtype=np.float32)
            capital = np.asarray(firm_events.capital, dtype=np.float32)
            cash = np.asarray(firm_events.cash, dtype=np.float32)
            inventory = np.asarray(firm_events.inventory, dtype=np.float32)
            debt = np.asarray(firm_events.debt, dtype=np.float32)
            wage_offer = np.asarray(firm_events.wage_offer, dtype=np.float32)
            price = np.asarray(firm_events.price, dtype=np.float32)

            entries = exits = transitions = overflow = 0
            active_np = np.array(firm_active, copy=True)
            firm_ids_np = np.array(firm_ids, copy=True)
            firm_cell_ids_np = np.array(firm_cell_ids, copy=True)
            firm_type_ids_np = np.array(firm_type_ids, copy=True)
            sector_np = np.array(firms.sector_id, copy=True)
            productivity_np = np.array(firms.productivity, copy=True)
            capital_np = np.array(firms.capital, copy=True)
            cash_np = np.array(firms.cash, copy=True)
            inventory_np = np.array(firms.inventory, copy=True)
            debt_np = np.array(firms.debt, copy=True)
            wage_offer_np = np.array(firms.wage_offer, copy=True)
            price_np = np.array(firms.price, copy=True)

            for idx in range(event_type.shape[0]):
                current_type = int(event_type[idx])
                ext_id = int(ext_firm_ids[idx])
                matching = np.flatnonzero(active_np & (firm_ids_np == ext_id))
                slot = int(matching[0]) if matching.size else -1
                if current_type == FirmLifecycleEventType.ENTRY:
                    free_slots = np.flatnonzero(~active_np)
                    if free_slots.size == 0:
                        overflow += 1
                        continue
                    slot = int(free_slots[0])
                    active_np[slot] = True
                    firm_ids_np[slot] = ext_id
                    firm_cell_ids_np[slot] = int(event_cells[idx])
                    firm_type_ids_np[slot] = int(event_types[idx])
                    if event_sectors[idx] >= 0:
                        sector_np[slot] = int(event_sectors[idx])
                    if np.isfinite(productivity[idx]):
                        productivity_np[slot] = float(productivity[idx])
                    if np.isfinite(capital[idx]):
                        capital_np[slot] = float(capital[idx])
                    if np.isfinite(cash[idx]):
                        cash_np[slot] = float(cash[idx])
                    if np.isfinite(inventory[idx]):
                        inventory_np[slot] = float(inventory[idx])
                    if np.isfinite(debt[idx]):
                        debt_np[slot] = float(debt[idx])
                    if np.isfinite(wage_offer[idx]):
                        wage_offer_np[slot] = float(wage_offer[idx])
                    if np.isfinite(price[idx]):
                        price_np[slot] = float(price[idx])
                    entries += 1
                    continue
                if slot < 0:
                    continue
                if current_type == FirmLifecycleEventType.EXIT:
                    active_np[slot] = False
                    cash_np[slot] = 0.0
                    inventory_np[slot] = 0.0
                    exits += 1
                elif current_type == FirmLifecycleEventType.TYPE_TRANSITION:
                    if event_cells[idx] >= 0:
                        firm_cell_ids_np[slot] = int(event_cells[idx])
                    if event_types[idx] >= 0:
                        firm_type_ids_np[slot] = int(event_types[idx])
                    if event_sectors[idx] >= 0:
                        sector_np[slot] = int(event_sectors[idx])
                    transitions += 1

            firm_active = jnp.asarray(active_np, dtype=jnp.bool_)
            firm_ids = jnp.asarray(firm_ids_np, dtype=jnp.int32)
            firm_cell_ids = jnp.asarray(firm_cell_ids_np, dtype=jnp.int32)
            firm_type_ids = jnp.asarray(firm_type_ids_np, dtype=jnp.int32)
            firms = firms.replace(
                active=firm_active,
                firm_id=firm_ids,
                cell_id=firm_cell_ids,
                firm_type_id=firm_type_ids,
                sector_id=jnp.asarray(sector_np, dtype=jnp.int32),
                productivity=jnp.asarray(productivity_np, dtype=jnp.float32),
                capital=jnp.asarray(capital_np, dtype=jnp.float32),
                cash=jnp.asarray(cash_np, dtype=jnp.float32),
                inventory=jnp.asarray(inventory_np, dtype=jnp.float32),
                debt=jnp.asarray(debt_np, dtype=jnp.float32),
                wage_offer=jnp.asarray(wage_offer_np, dtype=jnp.float32),
                price=jnp.asarray(price_np, dtype=jnp.float32),
            )
            exit_mask = agents.employer_id >= 0
            still_active = jnp.where(
                exit_mask,
                firm_active[jnp.clip(agents.employer_id, 0, state.firms.size - 1)],
                True,
            )
            unemployed_mask = exit_mask & ~still_active
            agents = agents.replace(
                is_employed=jnp.where(unemployed_mask, False, agents.is_employed),
                employer_id=jnp.where(unemployed_mask, -1, agents.employer_id),
            )
            metrics["population/firm_entries"] = entries
            metrics["population/firm_exits"] = exits
            metrics["population/firm_type_transitions"] = transitions
            metrics["population/firm_slot_overflow"] = overflow

        labor_count = _segment_sum(
            jnp.ones_like(agents.income),
            agents.employer_id,
            state.firms.size,
            mask=agents.active & agents.is_employed & (agents.employer_id >= 0),
        )
        firms = firms.replace(labor_count=labor_count)

        next_state = state.replace(agents=agents, firms=firms)
        if project:
            next_state = _project_multiscale(next_state)
        return next_state, metrics

    def step(self, state: GlobalState, **kwargs) -> tuple[GlobalState, dict[str, Any]]:
        """Apply one update and increment `state.step` by one."""
        next_state, metrics = self.apply(state, **kwargs)
        return next_state.replace(step=next_state.step + 1), metrics


@dataclass
class ContractsGraphAwareExecutor:
    """Propagate firm-level procurement shocks through the synthetic supply graph.

    Shock propagation mutates firm cash, inventory, and productivity in
    `GlobalState.agent_sim_runtime.procurement_graph` and can refresh cell
    distress projections, but it never reads observed data or loss weights.
    """

    inventory_sensitivity: float = 0.5
    productivity_sensitivity: float = 0.05

    def apply(
        self,
        state: GlobalState,
        *,
        procurement_shocks: ProcurementShockBatch | None = None,
        project: bool = True,
        fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID,
    ) -> tuple[GlobalState, dict[str, Any]]:
        """Apply one procurement-shock propagation pass without incrementing the step."""
        del fidelity
        state = _ensure_runtime(state, n_quantiles=10)
        runtime = state.agent_sim_runtime
        assert runtime is not None
        if procurement_shocks is None or procurement_shocks.origin_firm_id.shape[0] == 0:
            metrics = {
                "graph/n_shocks": jnp.array(0, dtype=jnp.int32),
                "graph/total_propagated_shock": jnp.array(0.0, dtype=jnp.float32),
                "_firm_distress_signal": jnp.zeros((state.firms.size,), dtype=jnp.float32),
            }
            return state, metrics

        graph = runtime.procurement_graph
        active_edges = graph.active
        procurement_code = multiplex_layer_code(MultiplexGraphLayerId.PROCUREMENT)
        procurement_mask = active_edges & (graph.edge_types == procurement_code)
        senders = np.asarray(graph.senders[procurement_mask], dtype=np.int32)
        receivers = np.asarray(graph.receivers[procurement_mask], dtype=np.int32)
        weights = np.asarray(graph.weights[procurement_mask], dtype=np.float32)

        total_impact = jnp.zeros((state.firms.size,), dtype=jnp.float32)
        origin_ids = np.asarray(procurement_shocks.origin_firm_id, dtype=np.int32)
        magnitudes = np.asarray(procurement_shocks.magnitude, dtype=np.float32)
        decays = np.asarray(procurement_shocks.decay, dtype=np.float32)
        max_hops = np.asarray(procurement_shocks.max_hops, dtype=np.int32)
        firm_ids = np.asarray(_firm_ids(state), dtype=np.int32)
        active_firms = np.asarray(_firm_active(state), dtype=bool)

        for idx in range(origin_ids.shape[0]):
            matching = np.flatnonzero(active_firms & (firm_ids == int(origin_ids[idx])))
            if matching.size == 0:
                continue
            signal = jnp.zeros((state.firms.size,), dtype=jnp.float32).at[int(matching[0])].set(
                float(magnitudes[idx])
            )
            total_impact = total_impact + signal
            for _ in range(max(int(max_hops[idx]), 0)):
                if senders.size == 0:
                    break
                edge_signal = signal[jnp.asarray(senders, dtype=jnp.int32)] * jnp.asarray(
                    weights,
                    dtype=jnp.float32,
                )
                propagated = jnp.bincount(
                    jnp.asarray(receivers, dtype=jnp.int32),
                    weights=edge_signal,
                    length=state.firms.size,
                ) * float(decays[idx])
                total_impact = total_impact + propagated
                signal = propagated

        active_mask = _firm_active(state)
        firms = state.firms.replace(
            cash=jnp.where(active_mask, state.firms.cash - total_impact, state.firms.cash),
            inventory=jnp.where(
                active_mask,
                jnp.maximum(
                    state.firms.inventory - self.inventory_sensitivity * total_impact,
                    0.0,
                ),
                state.firms.inventory,
            ),
            productivity=jnp.where(
                active_mask,
                jnp.maximum(
                    state.firms.productivity - self.productivity_sensitivity * total_impact,
                    0.0,
                ),
                state.firms.productivity,
            ),
        )
        runtime = runtime.replace(
            procurement_graph=runtime.procurement_graph.replace(last_update_step=state.step)
        )
        next_state = state.replace(firms=firms, agent_sim_runtime=runtime)
        if project:
            next_state = _project_multiscale(next_state, firm_distress=total_impact)

        metrics: dict[str, Any] = {
            "graph/n_shocks": jnp.array(origin_ids.shape[0], dtype=jnp.int32),
            "graph/total_propagated_shock": jnp.sum(total_impact),
            "graph/n_affected_firms": jnp.sum((total_impact > 0).astype(jnp.int32)),
            "_firm_distress_signal": total_impact,
        }
        if senders.size > 0:
            metrics.update(
                compute_graph_metrics(
                    EdgeList(
                        senders=jnp.asarray(senders, dtype=jnp.int32),
                        receivers=jnp.asarray(receivers, dtype=jnp.int32),
                        weights=jnp.asarray(weights, dtype=jnp.float32),
                        edge_types=jnp.full((senders.size,), procurement_code, dtype=jnp.int32),
                        n_nodes=int(np.asarray(graph.n_nodes).item()),
                        n_edges=int(senders.size),
                        is_directed=True,
                    ),
                    active_mask,
                )
            )
        return next_state, metrics

    def step(self, state: GlobalState, **kwargs) -> tuple[GlobalState, dict[str, Any]]:
        """Apply graph shock propagation and increment `state.step` by one."""
        next_state, metrics = self.apply(state, **kwargs)
        return next_state.replace(step=next_state.step + 1), metrics


@dataclass
class ContractsDistributionAwareExecutor:
    """Compose population, graph, tax, and transfer dynamics in one synthetic step.

    Use this executor when one intervention update must jointly affect firm
    lifecycle, procurement shocks, distribution-aware taxes/transfers, and
    derived inequality metrics. The output metrics are runtime diagnostics, not
    observation-side calibration losses.
    """

    population_executor: ContractsPopulationAwareExecutor | None = None
    graph_executor: ContractsGraphAwareExecutor | None = None
    n_quantiles: int = 10

    def __post_init__(self) -> None:
        if self.population_executor is None:
            self.population_executor = ContractsPopulationAwareExecutor()
        if self.graph_executor is None:
            self.graph_executor = ContractsGraphAwareExecutor()

    def _refresh_distribution(self, state: GlobalState) -> tuple[GlobalState, dict[str, Any]]:
        state = _ensure_runtime(state, n_quantiles=self.n_quantiles)
        distribution = _compute_distribution_state(
            state,
            n_quantiles=self.n_quantiles,
        )
        state = _with_distribution(state, distribution)
        active = state.agents.active
        percentile_ratios = compute_percentile_ratios(state.agents.income, active)
        metrics = {
            "distribution/gini_income": distribution.gini_income,
            "distribution/gini_wealth": distribution.gini_wealth,
            "distribution/palma_ratio": compute_palma_ratio(state.agents.income, active),
            "distribution/top_10_share": distribution.top_10_share,
            "distribution/bottom_50_share": distribution.bottom_50_share,
            "distribution/income_quantiles": distribution.income_quantiles,
            "distribution/p90_p10": percentile_ratios["p90_p10"],
            "distribution/p90_p50": percentile_ratios["p90_p50"],
            "distribution/p50_p10": percentile_ratios["p50_p10"],
        }
        return state, metrics

    def _apply_tax(
        self,
        state: GlobalState,
        config: InterventionMechanismConfig,
        *,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, Any]]:
        if not config.has_tax():
            return state, {}
        target_mask = _resolve_agent_mask(state, config)
        if not bool(np.asarray(jnp.any(target_mask))):
            return state, {"distribution_aware_tax/target_count": jnp.array(0, dtype=jnp.int32)}

        subset_distribution = _compute_distribution_state(
            state,
            active_mask=target_mask & state.agents.active,
            n_quantiles=self.n_quantiles,
        )
        runtime = state.agent_sim_runtime
        assert runtime is not None
        subset_state = state.replace(
            agents=state.agents.replace(active=target_mask & state.agents.active),
            agent_sim_runtime=runtime.replace(household_distribution=subset_distribution),
            tax_rate=jnp.array(config.base_tax_rate, dtype=jnp.float32),
        )
        mechanism = DistributionAwareTaxMechanism(
            base_rate=config.base_tax_rate,
            progressivity=config.tax_progressivity,
            use_cached_ranks=True,
        )
        adapted, metrics = mechanism.apply(
            _DistributionMechanismStateAdapter(subset_state),
            None,
            fidelity,
        )
        updated_income = adapted.base_state.agents.income
        state = state.replace(
            agents=state.agents.replace(
                income=jnp.where(target_mask, updated_income, state.agents.income)
            ),
            government_balance=state.government_balance + metrics["total_tax"],
            tax_rate=jnp.array(config.base_tax_rate, dtype=jnp.float32),
        )
        metrics["target_count"] = jnp.sum(target_mask.astype(jnp.int32))
        return state, {f"distribution_aware_tax/{key}": value for key, value in metrics.items()}

    def _apply_transfer(
        self,
        state: GlobalState,
        config: InterventionMechanismConfig,
        *,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, Any]]:
        if not config.has_transfer():
            return state, {}
        target_mask = _resolve_agent_mask(state, config)
        if not bool(np.asarray(jnp.any(target_mask))):
            return state, {"targeted_transfer/target_count": jnp.array(0, dtype=jnp.int32)}

        subset_distribution = _compute_distribution_state(
            state,
            active_mask=target_mask & state.agents.active,
            n_quantiles=self.n_quantiles,
        )
        runtime = state.agent_sim_runtime
        assert runtime is not None
        subset_state = state.replace(
            agents=state.agents.replace(active=target_mask & state.agents.active),
            agent_sim_runtime=runtime.replace(household_distribution=subset_distribution),
        )
        mechanism = TargetedTransferMechanism(
            total_budget=config.total_transfer_budget,
            target_percentile=config.target_percentile,
            transfer_formula=config.transfer_formula,
        )
        adapted, metrics = mechanism.apply(
            _DistributionMechanismStateAdapter(subset_state),
            None,
            fidelity,
        )
        updated_income = adapted.base_state.agents.income
        state = state.replace(
            agents=state.agents.replace(
                income=jnp.where(target_mask, updated_income, state.agents.income)
            ),
            government_balance=state.government_balance - metrics["total_transferred"],
        )
        metrics["target_count"] = jnp.sum(target_mask.astype(jnp.int32))
        return state, {f"targeted_transfer/{key}": value for key, value in metrics.items()}

    def apply(
        self,
        state: GlobalState,
        *,
        births_by_household_cell: jnp.ndarray | np.ndarray | None = None,
        migration_targets: jnp.ndarray | np.ndarray | None = None,
        firm_events: FirmLifecycleEventBatch | None = None,
        procurement_shocks: ProcurementShockBatch | None = None,
        intervention_config: InterventionMechanismConfig | None = None,
        fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID,
    ) -> tuple[GlobalState, dict[str, Any]]:
        """Apply one composed intervention update and refresh distribution metrics.

        Args:
            state: Synthetic runtime state to update.
            births_by_household_cell: Optional demographic birth counts.
            migration_targets: Optional migration assignments.
            firm_events: Optional firm lifecycle event batch.
            procurement_shocks: Optional shock seeds for graph propagation.
            intervention_config: Optional normalized tax/transfer targeting
                config.
            fidelity: Mechanism fidelity used by tax/transfer mechanisms.

        Returns:
            `(next_state, metrics)` containing population, graph, policy, and
            inequality diagnostics.
        """
        state = _ensure_runtime(state, n_quantiles=self.n_quantiles)
        metrics: dict[str, Any] = {}

        assert self.population_executor is not None
        assert self.graph_executor is not None

        state, population_metrics = self.population_executor.apply(
            state,
            births_by_household_cell=births_by_household_cell,
            migration_targets=migration_targets,
            firm_events=firm_events,
            project=False,
            fidelity=fidelity,
        )
        metrics.update(population_metrics)

        state, graph_metrics = self.graph_executor.apply(
            state,
            procurement_shocks=procurement_shocks,
            project=False,
            fidelity=fidelity,
        )
        firm_distress = graph_metrics.pop("_firm_distress_signal", None)
        metrics.update(graph_metrics)

        pre_policy_income = state.agents.income
        state, _ = self._refresh_distribution(state)

        config = intervention_config or InterventionMechanismConfig()
        state, tax_metrics = self._apply_tax(state, config, fidelity=fidelity)
        metrics.update(tax_metrics)
        state, transfer_metrics = self._apply_transfer(state, config, fidelity=fidelity)
        metrics.update(transfer_metrics)

        income_delta = state.agents.income - pre_policy_income
        state = _project_multiscale(
            state,
            income_delta=income_delta,
            firm_distress=firm_distress,
        )
        state, distribution_metrics = self._refresh_distribution(state)
        metrics.update(distribution_metrics)
        return state, metrics

    def step(self, state: GlobalState, **kwargs) -> tuple[GlobalState, dict[str, Any]]:
        """Apply the composed update and increment `state.step` by one."""
        next_state, metrics = self.apply(state, **kwargs)
        return next_state.replace(step=next_state.step + 1), metrics


__all__ = [
    "ContractsDistributionAwareExecutor",
    "ContractsGraphAwareExecutor",
    "ContractsPopulationAwareExecutor",
]
