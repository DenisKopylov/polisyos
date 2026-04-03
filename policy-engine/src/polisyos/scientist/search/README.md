# Search (`polisyos.scientist.search`)

`search` реализует итеративный policy-optimization контур Scientist: candidate
generation, evaluation stages, readiness/promotion gating, lesson registries,
benchmark registries и optional stress/diversity logic.

## Роль в системе

- **Зависит от:** `doe`, `governance`, `workflows`, `policy_design`, `core.artifacts`
- **Используется в:** policy-design/promotion flows, stress-test CLI, candidate-ranking surfaces
- Пакет не входит в mandatory `run_experiment()` path, но становится upstream для
  policy promotion, benchmarking и advanced search loops.

## Ключевые концепции

- **SearchController** — основной loop orchestration для cheap/expensive evaluation.
- **Decision readiness** — readiness caps и governance-aware promotion eligibility.
- **Judge stack** — typed failure cards, latent governance handling и promotion metadata.
- **Registries** — benchmark, lesson, pareto, champion и discovery registry contracts.
- **Funnel** — staged screening pipeline для candidate promotion.
- **Strategies** — random/grid/Bayesian/MO search adapters и resource arbitration.

## Public API

- `SearchController`, `SearchConfig`, `SearchResult`, `SearchIteration`
- Objective/stage/stopping contracts: `CompositeObjective`, `CheapStage`,
  `ExpensiveStage`, `StoppingPresets`
- Registry and lesson surfaces: `BenchmarkRegistry`, `LessonRegistry`,
  `LessonCard`, `ParetoRegistryContract`, `ChampionRegistryContract`
- Stress and readiness helpers: `run_stress_test(...)`, `SensitivityAwareCandidateGenerator`,
  `scientist_blueprint_compliance_audit(...)`

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Python modules: 64
- Exports: 107
- Недавний delta: README теперь отражает изменения в `judge_stack.py`,
  `readiness.py` и `latent_governance.py`, включая latent discovery degradation path
