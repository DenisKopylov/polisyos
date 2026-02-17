# Plugins (`polisyos.foundry.plugins`)

`plugins` — доменная plugin-архитектура поверх Foundry для composable multi-domain симуляций.

Актуально по коду на 2026-02-17.

## Роль в системе

Подсистема добавляет high-level слой над agent-based execution:
- домены оформляются как `DomainPlugin`;
- доменные состояния объединяются в `CompositeState`;
- исполнение/обучение доступно через `PolisySimulator` API и CLI.

## Архитектурный поток

```text
DomainPlugin protocols (core.py)
        -> PluginRegistry / discovery
        -> CompositeState / CompositeExecutor
        -> PolisySimulator API
        -> CLI (plugins/cli.py)
```

## Ключевые модули

- `core.py`
  - Контракты: `DomainPlugin`, `DomainState`, `MechanismProtocol`, `RewardProtocol`, `ObjectiveProtocol`.
  - `DomainConfig`, `PluginMetadata`, `PluginRegistry`.

- `composite.py`
  - `CompositeState`, cross-domain interactions, `CompositeExecutor`, `CompositeReward`, `CompositeObjective`.

- `api.py`
  - `PolisySimulator` (fluent API: add domain/interactions/objectives, run/train/visualize).
  - Результаты: `SimulationResult`, `TrainingResult`.

- `discovery.py`
  - Автообнаружение builtin, entry points (`polisyos.plugins`) и directory plugins.
  - `auto_register_plugins()` для runtime bootstrap.

- `cli.py`
  - Команды: `list`, `run`, `train`, `analyze`.

## Built-in economics plugin

`plugins/economics/` содержит референсный домен:
- `plugin.py` — `EconomicsPlugin`;
- `state.py` — доменная state-модель;
- `mechanisms.py` — labor/taxation/transfers/consumption/savings;
- `objectives.py` — GDP/Gini/unemployment/social-welfare/utilitarian/rawlsian цели;
- `rewards.py` — reward-функция для обучения.

## Связь с другими директориями

`plugins` зависит от:
- `foundry/agent_sim/*` (executor, training, distributions, visualization);
- JAX/Equinox стека и общих Foundry контрактов.

Используется как высокоуровневый API для сценариев, где удобнее plugin-based orchestration вместо прямой работы с Trinity `compile/execute`.

## Текущее состояние и ограничения

- Built-in discovery по умолчанию регистрирует `polisyos.foundry.plugins.economics`.
- В `PolisySimulator.train()` observation builder берётся из первого добавленного домена.
- CLI использует повторяемый флаг `--domain` (а не `--domains`).
- Подсистема ориентирована на доменные simulation workflows и не заменяет базовый Foundry execution pipeline.
