# Search Strategies (`polisyos.scientist.search.strategies`)

`search.strategies` содержит candidate generators и runtime helpers для
sample-efficient policy search: от базовых random/grid вариантов до optional
Bayesian и multi-objective контуров.

## Роль в системе

- **Зависит от:** `search`, optional `torch`/`botorch`/`gpytorch`
- **Используется в:** `SearchController`, policy-design optimization loops
- Пакет отделяет пространство параметров и генерацию кандидатов от orchestration-кода `search.controller`.

## Ключевые концепции

- **SearchStrategy** — базовый protocol для генераторов кандидатов.
- **SearchSpace + codecs** — описание параметров и их приведение к runtime форме.
- **Deterministic baselines** — `RandomSearchStrategy`, `GridSearchStrategy`.
- **Advanced optimizers** — optional Bayesian и multi-objective backends.
- **Resource arbitration** — лимиты памяти/ресурсов для дорогих strategy paths.

## Public API

- `SearchStrategy`, `BaseSearchStrategy`, `StrategyAdapter`
- `SearchSpace`, `ParameterCodec`, `ScalarParameterCodec`
- `PolicyCandidate`, `Evaluation`, `StrategyState`
- `RandomSearchStrategy`, `GridSearchStrategy`
- `ResourceArbiter`, `ResourceMode`, `memory_cleanup(...)`
- optional: `BayesianConfig`, `BayesianOptimizer`, `MOConfig`, `MOBayesianOptimizer`

Подробности: [Reference →](../../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Python modules: 24
- Exports: 18 base exports plus optional heavy-dependency strategy exports
- README синхронизирован с текущим lazy/optional import поведением пакета
