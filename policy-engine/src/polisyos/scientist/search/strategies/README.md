# Search Strategies (`polisyos.scientist.search.strategies`)

`search/strategies` — генераторы кандидатов и вспомогательные компоненты для `SearchController`.

## Базовые контракты

- `base.py` — `SearchStrategy` protocol и `BaseSearchStrategy`.
- `types.py` — доменные типы (`PolicyCandidate`, `Evaluation`, `StrategyState`, bounds/acquisition enums).
- `space.py` + `codec.py` — описание и кодирование параметрического пространства.

## Стратегии

- `random.py` — случайный поиск.
- `grid.py` — детерминированный grid search.
- `bayesian.py` — Bayesian optimizer (опциональные зависимости `torch/botorch/gpytorch`).
- `multi_objective.py` — multi-objective Bayesian optimizer (также опциональные heavy deps).
- `multi_fidelity.py` — multi-fidelity scheduling (например, successive halving).

## Runtime и интеграция

- `adapter.py` — `StrategyAdapter` для подключения strategy к интерфейсу `SearchController`.
- `objective_adapter.py` — bridge между objective API и strategy представлением целей.
- `resource_arbiter.py` — лимиты/арбитраж ресурсов для дорогих стадий.
- `runtime.py` — runtime-настройки для torch backend.
- `normalization.py`, `surrogate.py`, `acquisition.py`, `rl_wrapper.py` — вспомогательные блоки для продвинутых контуров.

## Связи

- вызывается из `search/controller.py`;
- используется опционально (default `run_experiment()` не включает search loop);
- может работать поверх `workflows.engine_base.WorkflowEngine` через `ExpensiveStage`.
