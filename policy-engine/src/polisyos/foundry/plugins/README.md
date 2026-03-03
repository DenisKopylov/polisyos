# Plugins (`polisyos.foundry.plugins`)

`plugins` — доменная plugin-архитектура Foundry для composable multi-domain симуляций поверх `agent_sim`.

Актуально по коду на 2026-03-03.

## Роль в системе

Подсистема добавляет high-level слой над agent-based контуром:

- домены инкапсулируются как `DomainPlugin`;
- состояния доменов объединяются в `CompositeState`;
- исполнение и обучение доступны через `PolisySimulator` API и CLI.

## Архитектурный поток

```text
DomainPlugin protocols (core.py)
        -> PluginRegistry / discovery
        -> CompositeState / CompositeExecutor
        -> PolisySimulator API
        -> CLI (plugins/cli.py)
```

## Ключевые модули

- `core.py`: контракты `DomainPlugin`, `DomainState`, reward/objective protocols, `PluginRegistry`.
- `composite.py`: `CompositeState`, cross-domain interactions, multi-domain executor/reward/objective.
- `api.py`: `PolisySimulator` (добавление доменов, run, train, visualize).
- `discovery.py`: built-in + entry points (`polisyos.plugins`) + directory plugins.
- `cli.py`: команды `list`, `run`, `train`, `analyze`.

## Built-in economics plugin

`plugins/economics/` содержит референсный домен:

- `plugin.py`: `EconomicsPlugin`;
- `state.py`: доменная state-модель;
- `mechanisms.py`: труд, налоги, трансферы, потребление, сбережения;
- `objectives.py`: GDP/Gini/unemployment/social-welfare цели;
- `rewards.py`: reward-функция для обучения.

## Связь с другими директориями

`plugins` зависит от:

- `foundry/agent_sim/*` (executor, training, distributions, visualization);
- JAX/Equinox/Optax стека и контрактов Foundry.

Используется как доменный orchestration-слой, когда plugin-driven сценарий удобнее прямого Trinity `compile/execute`.

## Текущее состояние и ограничения

- По умолчанию автообнаружение регистрирует `polisyos.foundry.plugins.economics`.
- В `PolisySimulator.train()` observation builder берется из первого добавленного домена.
- CLI использует повторяемый `--domain`.
- Подсистема ориентирована на доменные simulation workflows и не заменяет базовый Foundry execution pipeline.
