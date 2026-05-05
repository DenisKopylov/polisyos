from __future__ import annotations

import numpy as np
from polisyos.foundry.agent_sim.distributions import compute_gini_hard, compute_palma_ratio
from polisyos.foundry.agent_sim.wiring import (
    ContractsDistributionAwareExecutor,
    ContractsGraphAwareExecutor,
    ContractsPopulationAwareExecutor,
    FirmLifecycleEventBatch,
    FirmLifecycleEventType,
    InterventionMechanismConfig,
    ProcurementShockBatch,
    multiplex_layer_code,
)
from polisyos.foundry.contracts.state import (
    AgentSimRuntimeState,
    CellState,
    GlobalState,
    HouseholdCellState,
    ProcurementGraphState,
)
from polisyos.ir.governance.policy_spec import InterventionSpec
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.observation.contracts import MultiplexGraphLayerId
from polisyos.ir.types import SelectorOperator
from polisyos.lex.interventions import CompiledLexIntervention


def _base_multiscale_state(*, n_agents: int = 4, n_firms: int = 3) -> GlobalState:
    return GlobalState.empty(
        n_agents=n_agents,
        n_firms=n_firms,
        n_cells=3,
        n_household_cells=2,
    ).replace(
        cells=CellState.empty(3),
        household_cells=HouseholdCellState.empty(2).replace(
            cell_id=np.asarray([0, 1], dtype=np.int32)
        ),
    )


def test_population_executor_updates_cell_firm_count_from_firm_events() -> None:
    state = _base_multiscale_state(n_agents=2, n_firms=3).replace(
        agents=GlobalState.empty(n_agents=2, n_firms=3).agents.replace(
            active=np.asarray([True, True]),
            household_cell_id=np.asarray([0, 1], dtype=np.int32),
            is_employed=np.asarray([True, False]),
            employer_id=np.asarray([1, -1], dtype=np.int32),
        ),
        firms=GlobalState.empty(n_agents=2, n_firms=3).firms.replace(
            active=np.asarray([True, True, False]),
            firm_id=np.asarray([10, 20, -1], dtype=np.int32),
            cell_id=np.asarray([0, 1, -1], dtype=np.int32),
            firm_type_id=np.asarray([1, 2, 0], dtype=np.int32),
            sector_id=np.asarray([1, 2, 0], dtype=np.int32),
        ),
    )
    executor = ContractsPopulationAwareExecutor()
    firm_events = FirmLifecycleEventBatch.from_records(
        [
            {
                "event_type": FirmLifecycleEventType.ENTRY,
                "firm_id": 30,
                "cell_id": 0,
                "firm_type_id": 3,
                "sector_id": 3,
                "cash": 5000.0,
            },
            {
                "event_type": FirmLifecycleEventType.EXIT,
                "firm_id": 20,
            },
        ]
    )

    next_state, metrics = executor.step(state, firm_events=firm_events)

    assert np.allclose(np.asarray(next_state.cells.firm_count), np.asarray([2.0, 0.0, 0.0]))
    assert bool(np.asarray(next_state.agents.is_employed[0])) is False
    assert int(np.asarray(next_state.agents.employer_id[0])) == -1
    assert int(metrics["population/firm_entries"]) == 1
    assert int(metrics["population/firm_exits"]) == 1


def test_population_executor_updates_household_counts_for_births_and_migration() -> None:
    state = _base_multiscale_state(n_agents=3, n_firms=1).replace(
        agents=GlobalState.empty(n_agents=3, n_firms=1).agents.replace(
            active=np.asarray([True, False, True]),
            age=np.asarray([10, 0, 20], dtype=np.int32),
            household_cell_id=np.asarray([0, -1, 0], dtype=np.int32),
        )
    )
    executor = ContractsPopulationAwareExecutor()
    migration_targets = np.asarray([1, -1, -1], dtype=np.int32)

    next_state, metrics = executor.step(
        state,
        births_by_household_cell=np.asarray([0, 1], dtype=np.int32),
        migration_targets=migration_targets,
    )

    assert np.allclose(
        np.asarray(next_state.household_cells.household_count), np.asarray([1.0, 2.0])
    )
    assert np.allclose(np.asarray(next_state.cells.population), np.asarray([1.0, 2.0, 0.0]))
    assert int(metrics["population/births_applied"]) == 1
    assert int(np.asarray(next_state.agents.age[0])) == 11


def test_graph_executor_propagates_procurement_shock_only_through_procurement_layer() -> None:
    procurement_code = multiplex_layer_code(MultiplexGraphLayerId.PROCUREMENT)
    budget_code = multiplex_layer_code(MultiplexGraphLayerId.BUDGET)
    state = _base_multiscale_state(n_agents=1, n_firms=3).replace(
        firms=GlobalState.empty(n_agents=1, n_firms=3).firms.replace(
            active=np.asarray([True, True, True]),
            firm_id=np.asarray([101, 102, 103], dtype=np.int32),
            cell_id=np.asarray([0, 1, 2], dtype=np.int32),
            cash=np.asarray([100.0, 100.0, 100.0], dtype=np.float32),
            inventory=np.asarray([10.0, 10.0, 10.0], dtype=np.float32),
            productivity=np.asarray([1.0, 1.0, 1.0], dtype=np.float32),
            labor_count=np.asarray([1.0, 1.0, 1.0], dtype=np.float32),
        ),
        agent_sim_runtime=AgentSimRuntimeState.empty(n_agents=1, n_firms=3).replace(
            procurement_graph=ProcurementGraphState(
                senders=np.asarray([0, 1, 0], dtype=np.int32),
                receivers=np.asarray([1, 2, 2], dtype=np.int32),
                weights=np.asarray([1.0, 1.0, 10.0], dtype=np.float32),
                edge_types=np.asarray(
                    [procurement_code, procurement_code, budget_code], dtype=np.int32
                ),
                active=np.asarray([True, True, True]),
                n_nodes=np.asarray(3, dtype=np.int32),
                last_update_step=np.asarray(-1, dtype=np.int32),
            )
        ),
    )
    executor = ContractsGraphAwareExecutor()
    shocks = ProcurementShockBatch.from_records(
        [{"origin_firm_id": 101, "magnitude": 5.0, "decay": 0.5, "max_hops": 2}]
    )

    next_state, metrics = executor.step(state, procurement_shocks=shocks)

    assert np.allclose(
        np.asarray(next_state.firms.cash),
        np.asarray([95.0, 97.5, 98.75], dtype=np.float32),
        atol=1e-5,
    )
    assert float(np.asarray(metrics["graph/total_propagated_shock"])) == 8.75
    assert float(np.asarray(next_state.cells.distress_score[2])) > 0.0


def test_distribution_executor_updates_gini_and_palma_after_transfer() -> None:
    state = _base_multiscale_state(n_agents=4, n_firms=1).replace(
        agents=GlobalState.empty(n_agents=4, n_firms=1).agents.replace(
            active=np.asarray([True, True, True, True]),
            income=np.asarray([10.0, 20.0, 100.0, 200.0], dtype=np.float32),
            household_cell_id=np.asarray([0, 0, 1, 1], dtype=np.int32),
        ),
        firms=GlobalState.empty(n_agents=4, n_firms=1).firms.replace(
            active=np.asarray([True]),
            firm_id=np.asarray([10], dtype=np.int32),
            cell_id=np.asarray([0], dtype=np.int32),
        ),
        cells=CellState.empty(3),
        household_cells=HouseholdCellState.empty(2).replace(
            cell_id=np.asarray([0, 1], dtype=np.int32)
        ),
    )
    baseline_gini = float(compute_gini_hard(state.agents.income, state.agents.active))
    baseline_palma = float(compute_palma_ratio(state.agents.income, state.agents.active))
    executor = ContractsDistributionAwareExecutor()
    config = InterventionMechanismConfig.from_params(
        {
            "total_transfer_budget": 60.0,
            "target_percentile": 0.5,
            "transfer_formula": "uniform",
        }
    )

    next_state, metrics = executor.step(state, intervention_config=config)

    assert np.allclose(
        np.asarray(next_state.agents.income),
        np.asarray([40.0, 50.0, 100.0, 200.0], dtype=np.float32),
    )
    assert float(np.asarray(metrics["distribution/gini_income"])) < baseline_gini
    assert float(np.asarray(metrics["distribution/palma_ratio"])) < baseline_palma
    assert np.allclose(
        np.asarray(next_state.household_cells.disposable_income),
        np.asarray([45.0, 150.0], dtype=np.float32),
    )
    assert np.allclose(
        np.asarray(next_state.household_cells.transfer_intensity),
        np.asarray([30.0, 0.0], dtype=np.float32),
    )


def test_intervention_config_from_compiled_tax_intervention_drives_expected_tax_amounts() -> None:
    compiled = CompiledLexIntervention(
        intervention=InterventionSpec(
            intervention_id="tax_demo",
            kind="tax_rate_change",
            target=SelectorPredicate(
                field="agent_id",
                operator=SelectorOperator.GREATER_EQUAL,
                value=0,
            ),
            schedule=ScheduleSpec(start_step=0, duration_steps=1),
            params={"tax_rate": "0.1", "progressivity": "0.2"},
        ),
        metadata={"target_household_cell_ids": [0]},
    )
    config = InterventionMechanismConfig.from_compiled_intervention(compiled)
    state = _base_multiscale_state(n_agents=3, n_firms=1).replace(
        agents=GlobalState.empty(n_agents=3, n_firms=1).agents.replace(
            active=np.asarray([True, True, True]),
            income=np.asarray([100.0, 200.0, 300.0], dtype=np.float32),
            household_cell_id=np.asarray([0, 0, 1], dtype=np.int32),
        )
    )
    executor = ContractsDistributionAwareExecutor()

    next_state, metrics = executor.step(state, intervention_config=config)

    assert config.base_tax_rate == 0.1
    assert config.tax_progressivity == 0.2
    assert np.allclose(
        np.asarray(next_state.agents.income),
        np.asarray([90.0, 140.0, 300.0], dtype=np.float32),
    )
    assert float(np.asarray(metrics["distribution_aware_tax/total_tax"])) == 70.0


def test_c6b_wiring_runs_full_synthetic_step() -> None:
    procurement_code = multiplex_layer_code(MultiplexGraphLayerId.PROCUREMENT)
    state = _base_multiscale_state().replace(
        agents=GlobalState.empty(n_agents=4, n_firms=3).agents.replace(
            active=np.asarray([True, False, True, True]),
            age=np.asarray([35, 0, 48, 29], dtype=np.int32),
            income=np.asarray([100.0, 0.0, 50.0, 300.0], dtype=np.float32),
            is_employed=np.asarray([True, False, True, True]),
            employer_id=np.asarray([0, -1, 1, 1], dtype=np.int32),
            household_cell_id=np.asarray([0, -1, 1, 1], dtype=np.int32),
        ),
        firms=GlobalState.empty(n_agents=4, n_firms=3).firms.replace(
            active=np.asarray([True, True, False]),
            firm_id=np.asarray([10, 20, -1], dtype=np.int32),
            cell_id=np.asarray([0, 1, -1], dtype=np.int32),
            labor_count=np.asarray([1.0, 2.0, 0.0], dtype=np.float32),
            cash=np.asarray([100.0, 100.0, 0.0], dtype=np.float32),
        ),
        agent_sim_runtime=AgentSimRuntimeState.empty(n_agents=4, n_firms=3).replace(
            procurement_graph=ProcurementGraphState(
                senders=np.asarray([0], dtype=np.int32),
                receivers=np.asarray([1], dtype=np.int32),
                weights=np.asarray([1.0], dtype=np.float32),
                edge_types=np.asarray([procurement_code], dtype=np.int32),
                active=np.asarray([True]),
                n_nodes=np.asarray(3, dtype=np.int32),
                last_update_step=np.asarray(-1, dtype=np.int32),
            )
        ),
    )
    executor = ContractsDistributionAwareExecutor()
    firm_events = FirmLifecycleEventBatch.from_records(
        [
            {
                "event_type": FirmLifecycleEventType.ENTRY,
                "firm_id": 30,
                "cell_id": 0,
                "firm_type_id": 3,
            }
        ]
    )
    procurement_shocks = ProcurementShockBatch.from_records(
        [{"origin_firm_id": 10, "magnitude": 4.0, "decay": 0.5, "max_hops": 1}]
    )
    config = InterventionMechanismConfig.from_params(
        {"total_transfer_budget": 40.0, "target_percentile": 0.5}
    )

    next_state, metrics = executor.step(
        state,
        births_by_household_cell=np.asarray([1, 0], dtype=np.int32),
        migration_targets=np.asarray([1, -1, -1, -1], dtype=np.int32),
        firm_events=firm_events,
        procurement_shocks=procurement_shocks,
        intervention_config=config,
    )

    assert int(np.asarray(next_state.step)) == 1
    assert float(np.asarray(next_state.cells.firm_count[0])) == 2.0
    assert float(np.asarray(next_state.cells.distress_score[1])) > 0.0
    assert "distribution/palma_ratio" in metrics
    assert float(np.asarray(next_state.household_cells.household_count.sum())) == 4.0
