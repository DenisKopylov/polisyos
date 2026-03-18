# Methods Catalog (`polisyos.foundry.methods.catalog`)

`methods/catalog` — каноническое дерево реализаций методов Foundry V2.

Актуально по коду на 2026-03-03.

## Роль

Каталог группирует предметные method-реализации, которые регистрируются в `MethodRegistry` и затем доступны:

- напрямую через `polisyos.foundry.methods` API;
- как `method`-узлы в execution graph Foundry;
- через `scientist` planning/runtime узлы.

## Подкаталоги

- `causal/`: причинные методы (discovery, estimation, transportability, sensitivity).
- `econometrics/`: panel, IV, time-series методы.
- `optimization/`: LP/MILP и input-output модели.
- `simulation/`: system dynamics, DES, compartmental и unified `agent_sim` bridge.
- `survey/`, `distributional/`, `forecasting/`, `validation/`, `sensitivity/`: новые V2 family-слои.
- `bayesian/`, `spatial/`, `network/`, `ml/`, `microsim/`: расширенные прикладные домены.

## Регистрация

Каждый подкаталог содержит `_registry_boot.py` с функцией `register_*_methods()`.

Интеграция в runtime выполняется через `ensure_*_methods_registered()` в соответствующих `__init__.py`.

## Public API

- `catalog/*` — единственный источник истины для canonical FQN, registration и capability metadata.
- Пакетные flat surface `polisyos.foundry.methods.{causal,econometrics,optimization}` допустимы как публичный импорт.
- Deep compatibility shims и deprecated bootstrap path удалены.

## Документы V2

- `AUTHORING.md` — guide для новых методов.
- `NAMING.md` — canonical naming contract `domain.family.variant@semver`.
- `MIGRATION_V2.md` — breaking changes и примеры миграции.

## Смежная документация

- `../README.md` — обзор подсистемы `methods`.
- `causal/README.md` — подробная документация causal-каталога.
