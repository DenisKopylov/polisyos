# Plugins (`polisyos.foundry.plugins`)

`plugins` - доменная plugin-архитектура поверх Foundry для high-level multi-domain симуляций.

Актуально по коду на 2026-02-10.

## Роль в системе

Подсистема дает расширяемый слой над симулятором:
- домены оформляются как `DomainPlugin`;
- домены объединяются в `CompositeState`;
- запуск/обучение выполняется через `PolisySimulator`.

## Архитектурный поток

```
DomainPlugin protocols (core.py)
        -> PluginRegistry
        -> CompositeState / CompositeExecutor
        -> PolisySimulator API
        -> CLI (plugins/cli.py)
```

## Ключевые модули

- `core.py`
  - контракты `DomainPlugin`, `DomainState`, `MechanismProtocol`, `RewardProtocol`, `ObjectiveProtocol`.
  - `PluginRegistry` и `DomainConfig`.

- `composite.py`
  - `CompositeState` (несколько доменов), cross-domain interactions, `CompositeExecutor`, `CompositeReward`, `CompositeObjective`.

- `api.py`
  - `PolisySimulator` с fluent API: добавление доменов, interactions, run/train/visualize.
  - результаты: `SimulationResult`, `TrainingResult`.

- `discovery.py`
  - автообнаружение builtin, entry points и directory plugins.
  - helper: `auto_register_plugins()`.

- `cli.py`
  - команды: `list`, `run`, `train`, `analyze`.

## Built-in economics plugin

Папка `plugins/economics/` содержит референсный домен:
- `plugin.py` - `EconomicsPlugin`.
- `state.py` - `EconomicState` и связанные state-контракты.
- `mechanisms.py` - taxation/transfers/labor/consumption/savings.
- `objectives.py` - GDP/Gini/unemployment/social-welfare/utilitarian/rawlsian.
- `rewards.py` - `EconomicReward`.

## Связь с другими директориями

`plugins` зависит от:
- `foundry/agent_sim/*` (ActorCritic, training config, distributions, visualization);
- JAX/Equinox для state/execution логики.

`plugins` используется как high-level API для прикладных симуляций, где нужен plugin-based сценарий вместо прямой работы с Trinity compile/execute.

## Текущее состояние и ограничения

- Builtin discovery по умолчанию регистрирует только `polisyos.foundry.plugins.economics`.
- В `PolisySimulator.train()` источник observations берется из первого добавленного домена.
- CLI использует флаг `--domain` (повторяемый), а не `--domains`.
- Подсистема ориентирована на доменные simulation workflows и не заменяет базовый Foundry pipeline (`compile/execute`).
