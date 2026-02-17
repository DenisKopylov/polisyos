# Search Layer (`polisyos.scientist.search`)

`search` — опциональный контур итеративной оптимизации кандидатов политики.

## Роль

- управляет search-loop (`SearchController`);
- оценивает кандидатов через cheap/expensive стадии;
- считает objective и применяет stopping criteria;
- поддерживает stress/adversarial и portfolio сценарии.

Default `run_experiment()` этот слой автоматически не запускает.

## Ключевые модули

- `controller.py` — `SearchController`, `SearchConfig`, `SearchResult`, `SearchIteration`.
- `objective.py` — objective-модели (`CompositeObjective`, пресеты).
- `stages.py` — `CheapStage`, `ExpensiveStage`, `CorrelationTracker`.
- `stopping.py` — `MaxIterations`, `MaxWallTime`, `ImprovementPlateau`, `TargetAchieved`, пресеты.
- `adversarial.py` — `run_stress_test()` (использует DoE `AdversarialPlan`).
- `portfolio.py`, `diversity.py`, `sensitivity_adapter.py` — дополнительные контуры.
- `strategies/` — генерация кандидатов (`random`, `grid`, adapter, resource arbiter, optional Bayesian/MO).

## Минимальный API-контур

`SearchController` ожидает:
- `candidate_generator.generate(history, current_best, context)`;
- `stage_a_evaluator(candidate, context) -> (score, passed)`;
- `stage_b_evaluator(candidate, context) -> dict`.

Запуск: `controller.run(initial_context, initial_candidate=None)`.

## Особенности

- batch-режим включается через `SearchConfig.batch_size` + `generate_batch` у генератора.
- optional diversity enrichment включается `POLISYOS_SEARCH_DIVERSITY_ENABLED`.
- `strategies.bayesian` и `strategies.multi_objective` подключаются только при тяжелых зависимостях (`torch/botorch/gpytorch`).

## Связи

- `doe` — adversarial plans/sampling.
- `core/components/_cli_scientist.py` — команда `scientist stress-test`.
- `workflows.engine_base` — `ExpensiveStage` работает через `WorkflowEngine` protocol.
