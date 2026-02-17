# Agent Simulation (`polisyos.foundry.agent_sim`)

`agent_sim` — подсистема Foundry для агентно-ориентированных симуляций, RL-обучения и динамики популяции/графа.

Актуально по коду на 2026-02-17.

## Роль в системе

`agent_sim` покрывает микроуровень (поведение агентов, обучение, демография, сетевые эффекты) и работает как отдельный execution contour внутри Foundry.

Важно: это не замена базового Trinity pipeline `foundry.compile -> foundry.execute`, а параллельный стек для ABM/RL сценариев.

## Архитектура исполнения

```text
Mechanisms
  -> PureExecutor
  -> DistributionAwareExecutor
  -> GraphAwareExecutor
  -> PopulationAwareExecutor
```

Ключевые исполнители:
- `executor.py` — deterministic ordering механизмов (`MechanismOrder`), `step`/`run`.
- `distribution_executor.py` — обновление distribution-метрик.
- `graph_executor.py` — обновление графа и graph metrics.
- `population_executor.py` — lifecycle (birth/death/migration/inheritance) + sync графа с популяцией.
- `temporal_executor.py` — temporal-aware конфигурация (подменяет/добавляет temporal consumption mechanism).

## Модель состояния

`state.py` задаёт state-of-arrays модель:
- `AgentState` — демография, доходы/богатство, ожидания, связи, статусы активности;
- `PolicyState` — общие policy-параметры;
- `AggregateState` — агрегаты уровня популяции;
- `GlobalState` — композиция agents/policy/aggregates/distributions/graph/population manager/time/rng.

Особенность: динамическая популяция ведётся через fixed-size буферы и `active` маски.

## Механизмы и домены поведения

- `mechanism.py` — базовый контракт `MechanismSpec` + `apply(...)`.
- `mechanisms.py`, `distribution_mechanisms.py` — налоги/трансферы/потребление + distribution-aware логика.
- `graph_mechanisms.py` — diffusion/social influence/network lending/labor network эффекты.
- `temporal_mechanisms.py` — temporal policy/mechanism слой.
- `population_mechanisms.py` — aging/birth/death/migration/inheritance/gifts.

## Обучение и оптимизация

- `actor_critic.py`, `rl.py` — policy/value сети, trajectory, GAE/PPO.
- `training.py` — eager/Python-loop обучение.
- `jit_training.py` — JIT-ориентированный training path.
- `credit_assignment.py` — multi-agent credit assignment.
- `modes.py` — режимы оптимизации/калибровки и bilevel сценарии.
- Альтернативные решатели: `evolution.py` (ES/CMA-ES), `vfi.py`, `mpc.py`.

## Артефакты, анализ, визуализация

- `artifact.py` — policy artifact + environment compatibility/fingerprint.
- `experiment.py` — трекинг экспериментов и воспроизводимость.
- `metrics.py`, `analysis.py`, `demographics.py` — диагностика поведения и популяции.
- `visualization.py`, `dashboard.py` — отчёты и графики.

## Связь с другими директориями

`agent_sim` зависит от:
- `foundry/contracts/fidelity.py`;
- `foundry/runtime/fingerprint.py`;
- `core/artifacts/*` и `core/observability/*`;
- JAX/Equinox/Optax стека.

`agent_sim` используется в:
- `foundry/plugins/*` (встроенный economics plugin и composite execution слой);
- прикладных RL/ABM сценариях.

## Текущее состояние и ограничения

- Для долгих/массовых прогонов предпочтителен `jit_training.py`; `training.py` оставлен как простой и дебажный путь.
- Популяционная динамика опирается на capacity-лимиты (`max_agents`) и allocator-механику.
- Интеграция с Trinity контуром требует явной orchestration на уровне `scientist` или прикладного кода.
