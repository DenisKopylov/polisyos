# Agent Simulation (`polisyos.foundry.agent_sim`)

`agent_sim` - подсистема Foundry для агентно-ориентированных симуляций с RL, графовой динамикой и жизненным циклом популяции.

Актуально по коду на 2026-02-10.

## Роль в системе

`agent_sim` решает задачи, где нужна микро-динамика агентов и обучение политик.
Это отдельный вычислительный контур внутри Foundry и не является прямой заменой основного Trinity `compile -> execute` pipeline.

## Архитектура исполнения

```
Mechanisms -> PureExecutor -> DistributionAwareExecutor -> GraphAwareExecutor -> PopulationAwareExecutor
                              (+distribution)             (+graph)             (+lifecycle)
```

Ключевые исполнители:
- `executor.py` - `PureExecutor`, deterministic ordering по reads/writes (`MechanismOrder`), `step` и `run`.
- `distribution_executor.py` - добавляет обновление распределительных метрик.
- `graph_executor.py` - добавляет обновление социального/экономического графа.
- `population_executor.py` - добавляет рождение/смерть/миграцию/наследование и синхронизацию графа.
- `temporal_executor.py` - фабрика temporal-aware конфигурации.

## Модель состояния

Основные типы в `state.py`:
- `AgentState` (state-of-arrays, 28 полей, включая демографию, финансы, связи, ожидания).
- `PolicyState` (глобальные policy-параметры).
- `AggregateState` (агрегаты по популяции).
- `GlobalState` (композит: agents/policy/aggregates/distributions/graph/population_manager/time/rng).

## Механизмы

Базовый контракт в `mechanism.py`: `MechanismSpec` + `apply(state, rng_key, fidelity)`.

Семейства механизмов:
- `mechanisms.py`, `distribution_mechanisms.py` - налоги, потребление, трансферы, distribution-aware поведение.
- `graph_mechanisms.py` - социальное влияние, diffusion, сетевое кредитование и labor-связи.
- `temporal_mechanisms.py` - temporal/RL-driven действия по потреблению.
- `population_mechanisms.py` - aging, births, deaths, migration, inheritance, gifts.

## Обучение и оптимизация

- `actor_critic.py` - ActorCritic/Value/Advantage сети.
- `rl.py` - trajectory структуры, GAE, PPO loss.
- `training.py` - eager (Python-loop) обучение.
- `jit_training.py` - полностью JIT-ориентированное обучение.
- `modes.py` - режимы `AGENTS_ADAPT`, `POLICY_OPTIMIZE`, `CALIBRATE`, `BILEVEL`.
- `credit_assignment.py` - multi-agent credit assignment.

Альтернативные решатели:
- `evolution.py` (ES/CMA-ES)
- `vfi.py` (VFI)
- `mpc.py` (MPC/Hybrid planner)

## Графы, распределения и популяция

- `graphs.py` - структуры графа, генераторы, message passing и graph metrics.
- `distributions.py` - Gini/Palma/quantiles/ranks/mobility и distribution-aware reward.
- `population.py` - slot allocator и операции управления активной популяцией в fixed-size state.

## Артефакты и анализ

- `artifact.py` - `AgentPolicyArtifact`, совместимость/валидация окружения, CAS persistence.
- `experiment.py` - эксперимент-трекинг и воспроизводимость запусков.
- `metrics.py` - JIT-friendly `MetricsCollector`.
- `analysis.py`, `demographics.py` - поведенческий и демографический анализ.
- `visualization.py`, `dashboard.py` - визуализация и отчеты.

## Связь с другими директориями

`agent_sim` зависит от:
- `foundry/contracts/fidelity.py` (общие уровни fidelity);
- `foundry/runtime/fingerprint.py` (environment fingerprint/determinism);
- `core/artifacts/*` (политики и артефакты в CAS);
- `common/logger` и вычислительного стека JAX/Equinox/Optax.

`agent_sim` используется в:
- `foundry/plugins/` (встроенный economics plugin использует части `agent_sim`);
- пользовательских/экспериментальных сценариях обучения и симуляции.

## Текущее состояние и ограничения

- Масштабирование динамической популяции реализовано через fixed-size буферы + `active` masks.
- Для крупных прогонов предпочтителен `jit_training.py`; `training.py` сохраняет Python-loop путь.
- Подсистема независима от Trinity-исполнителя (`foundry.compile/execute`) и требует отдельной оркестрации в смешанных сценариях.
