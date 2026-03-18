# Methods (`polisyos.foundry.methods`)

`methods` — подсистема Foundry для декларативных вычислительных методов: ABI, unified registry/discovery, композиция DAG-цепочек, capability-aware selection и multi-backend исполнение.

Актуально по коду на 2026-03-03.

## Роль в системе

`methods` используется, когда вычисление оформляется как переиспользуемый typed method с контрактом входов/выходов, независимо от Trinity-механизмов.

## Архитектурный поток

```text
FoundryMethod protocol
        -> MethodRegistry / Discovery
        -> SlotLinker + MethodComposer (DAG)
        -> Backend dispatch (JAX / NumPy / Solver)
        -> optional compile/specialization/artifacts/snapshot
```

## Структура подсистемы

- `base.py`: ABI (`FoundryMethod`, `MethodSignature`, `MethodMetadata`, `SlotSpec`, `ParameterSpec`) и `@foundry_method`.
- `registry.py`: thread-safe singleton `MethodRegistry` с version resolution и query API.
- `discovery.py`: discovery utilities для entry points и dev filesystem scan; production bootstrap идет через `core.components`.
- `linker.py`: проверка совместимости slot-ов (type/unit/shape) и построение bindings.
- `composer.py`: DAG-композиция (`graphlib.TopologicalSorter`) и deterministic order.
- `backends/*`: dispatch и запуск методов в JAX/NumPy/Solver окружениях.
- `compiler.py`, `specialization.py`: optional compile/specialization и кеширование.
- `artifacts.py`, `catalog_snapshot.py`: provenance и снимок каталога методов в CAS.

## Каталог методов

Канонические реализации находятся только в `methods/catalog/*`:

- `methods/catalog/causal/`
- `methods/catalog/econometrics/`
- `methods/catalog/optimization/`
- `methods/catalog/simulation/`
- `methods/catalog/survey/`
- `methods/catalog/distributional/`
- `methods/catalog/forecasting/`
- `methods/catalog/validation/`
- `methods/catalog/sensitivity/`
- `methods/catalog/bayesian/`
- `methods/catalog/spatial/`

Навигация по каталогу: `methods/catalog/README.md`.
Для крупного causal-каталога есть отдельный документ: `methods/catalog/causal/README.md`.

## Public surface после V2

- Пакеты `polisyos.foundry.methods.causal`, `...econometrics`, `...optimization` остаются как flat public API.
- Deep submodules вида `polisyos.foundry.methods.<domain>.<module>` удалены.
- Bootstrap legacy API `bootstrap_registry(...)` удален; runtime должен идти через components index + methods bridge.

## Связь с Foundry и Scientist

- Method-узлы выполняются из execution-графа Foundry через `MethodDispatcher`.
- Снимки каталога используются в `scientist/nodes/builtins/planning/build_method_catalog_snapshot.py`.
- Подсистема подключена к `scientist/compute/runner.py` и method-oriented пакетам.

## Текущее состояние и ограничения

- Много optional deps: `jax`, solver stack, `statsmodels`, `linearmodels`, `econml`, и др.
- При отсутствии зависимостей часть методов доступна, а часть регистрируется условно.
- Snapshot `schema_version=2.0` является canonical capability/runtime truth для planner и scientist.

## Документы V2

- `catalog/AUTHORING.md` — как добавлять новые методы.
- `catalog/NAMING.md` — канонический FQN contract.
- `catalog/MIGRATION_V2.md` — breaking migration note.

## Тестовый контур

`testing/` покрывает:

- protocol/signature checks;
- slot compatibility и composition edge cases;
- backend suites (`numpy`, `jax`, `solver`);
- golden-регрессии и determinism проверки.
