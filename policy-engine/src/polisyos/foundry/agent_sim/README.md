# Agent Simulation (`polisyos.foundry.agent_sim`)

`agent_sim` — подсистема Foundry для агентно-ориентированных симуляций, RL-обучения и динамики популяции/графа.

Актуально по коду на 2026-03-03.

## Роль в системе

`agent_sim` покрывает микроуровень (поведение агентов, обучение, демография, сетевые эффекты) и работает как отдельный execution contour.

Это параллельный стек к Trinity-пайплайну `foundry.compile -> foundry.execute`, а не его замена.

## Слои исполнения

```text
Mechanisms
  -> PureExecutor
  -> DistributionAwareExecutor
  -> GraphAwareExecutor
  -> PopulationAwareExecutor
```

Ключевые executors:

- `executor.py`: deterministic ordering механизмов, `step`/`run`.
- `distribution_executor.py`: обновление distribution metrics.
- `graph_executor.py`: обновление графа и graph metrics.
- `population_executor.py`: lifecycle (birth/death/migration/inheritance) + sync графа.
- `temporal_executor.py`: temporal-aware конфигурация механизмов потребления.

## Модель состояния

`state.py` реализует state-of-arrays модель:

- `AgentState` (доходы, богатство, ожидания, активность, связи);
- `PolicyState` (policy параметры);
- `AggregateState` (агрегаты популяции);
- `GlobalState` (композиция всех подсистем + time/rng).

Динамическая популяция ведется через fixed-size буферы и `active` маски.

## Механизмы, обучение, аналитика

- Механизмы: `mechanisms.py`, `distribution_mechanisms.py`, `graph_mechanisms.py`, `population_mechanisms.py`, `temporal_mechanisms.py`.
- RL/оптимизация: `actor_critic.py`, `rl.py`, `training.py`, `jit_training.py`, `credit_assignment.py`, `modes.py`.
- Альтернативные решатели: `evolution.py`, `vfi.py`, `mpc.py`.
- Артефакты/репродуцируемость: `artifact.py`, `experiment.py`, `prng.py`.
- Диагностика и визуализация: `metrics.py`, `analysis.py`, `demographics.py`, `visualization.py`, `dashboard.py`.

## Связь с другими директориями

`agent_sim` зависит от:

- `foundry/contracts/fidelity.py`;
- `foundry/runtime/fingerprint.py`;
- `core/artifacts/*`, `core/observability/*`;
- JAX/Equinox/Optax.

Используется напрямую в ABM/RL сценариях и как низкоуровневая база для `foundry/plugins/*`.

## Текущее состояние и ограничения

- Для длинных и массовых прогонов предпочтителен `jit_training.py`; `training.py` остается простым debug-путем.
- Популяционная динамика ограничена `max_agents` и allocator-механикой.
- Интеграция с Trinity-контуром требует явной orchestration на уровне `scientist` или прикладного кода.
