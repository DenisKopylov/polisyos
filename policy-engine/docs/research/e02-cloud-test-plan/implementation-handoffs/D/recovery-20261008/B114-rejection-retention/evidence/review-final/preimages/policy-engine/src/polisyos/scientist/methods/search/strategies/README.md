# Search Strategies (`polisyos.scientist.methods.search.strategies`)

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
- **WS-3C policy toolkit** — offline-gated BOHB/ASHA, CMA-ES, learned VOI,
  learned routing, GP surrogate, constraint propagation and PBT helpers.

- **Resource arbitration** — лимиты памяти/ресурсов для дорогих strategy paths.

## Public API

- `SearchStrategy`, `BaseSearchStrategy`, `StrategyAdapter`
- `SearchSpace`, `ParameterCodec`, `ScalarParameterCodec`
- `PolicyCandidate`, `Evaluation`, `StrategyState`
- `RandomSearchStrategy`, `GridSearchStrategy`
- `ResourceArbiter`, `ResourceMode`, `memory_cleanup(...)`
- optional: `BayesianConfig`, `BayesianOptimizer`, `MOConfig`, `MOBayesianOptimizer`
- WS-3C: `AdvancedSearchPolicyConfig`, `ASHAScheduler`, `BOHBSampler`,
  `CMAESExplorer`, `GaussianProcessCheapStageSurrogate`,
  `ExplicitConstraintPropagator`, `LearnedVOIPolicy`, `LearnedRoutingPolicy`,
  `PopulationBasedTrainingScheduler`

Подробности: [Reference →](../../../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
  - WS-3C advanced policy surface обновлён: 2026-04-12
  - Canonical path moved under `polisyos.scientist.methods.search`: 2026-05-05
- Python modules: 24
- Exports: 18 base exports plus optional heavy-dependency strategy exports
- README синхронизирован с текущим lazy/optional import поведением пакета
