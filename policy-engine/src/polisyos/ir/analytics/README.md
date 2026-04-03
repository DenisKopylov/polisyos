# Analytics (`polisyos.ir.analytics`)

`polisyos.ir.analytics` описывает контрактный слой аналитических результатов:
causal effects, transportability, HTE, backtests, uncertainty, cross-graph
alignment и стратегические response артефакты. Пакет задает модели и CAS helpers,
которые downstream-модули используют как общий interchange format между
`foundry`, `scientist`, `fabric` и observation-driven causal workflows.

## Роль в системе

- **Зависит от:** `polisyos.ir.artifacts`, `polisyos.ir.world`, `polisyos.ir.observation`
- **Используется в:** `polisyos.foundry.methods`, `polisyos.scientist`, `polisyos.fabric`, `polisyos.core`
- Пакет связывает execution outputs с canonical IR моделями и хранит reloadable artifact surface через `persist_*` / `load_*`.

## Ключевые концепции

- **Effect reports** — `CausalEffectReport`, `HTEResult`, `DistributionalReport`, `BacktestReport`.
- **Graph and query contracts** — causal graph, SCM, causal queries, discovery and ensemble artifacts.
- **Transport and robustness** — `TransportabilityResult`, sensitivity, partial identification, falsification.
- **Strategic analytics** — `StrategicSCM`, `FiniteStrategicPayoffTable`, `StrategicResponseBundle` и new `persist_strategic_solve_artifacts()`.
- **Temporal and DTR surface** — continuous-time queries, effect trajectories и dynamic regime artifacts.
- **CAS persistence** — almost every publication-grade model имеет typed `persist_*`/`load_*` helpers поверх `ir.artifacts`.

## Public API

| Type/Function | Description |
|---|---|
| `CausalEffectReport` | Канонический causal effect report с diagnostics, refutations и envelope conversion |
| `TransportabilityResult` | Результат переноса между contexts/regimes с data gaps и blockers |
| `HTEResult` | Heterogeneous treatment effects, feature importance и targeting outputs |
| `StructuralCausalModelSpec` | IR форма структурной causal model |
| `StrategicSCM` | Strategic-response SCM для performative and equilibrium analysis |
| `StrategicResponseBundle` | CAS-backed summary strategic closure, equilibria и post-adaptation value |
| `FiniteStrategicPayoffTable` | Таблица payoff profiles для finite strategic analysis |
| `persist_strategic_solve_artifacts()` | Публикует полный набор strategic solve artifacts и bundle refs |

Full reference: [docs/reference/ir/](../../../../docs/reference/ir/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Files: 50 Python files plus `ddl/`
- Exports: facade in `__init__.py` агрегирует 29 star-import modules и targeted named imports
- Recent delta: добавлен `strategic.py` в публичный surface; новые strategic persistence helpers теперь публикуют bundle-level solve lineage
