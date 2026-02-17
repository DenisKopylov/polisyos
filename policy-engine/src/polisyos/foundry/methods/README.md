# Methods (`polisyos.foundry.methods`)

`methods` — подсистема Foundry для декларативных вычислительных методов: ABI, регистрация, композиция цепочек и multi-backend исполнение.

Актуально по коду на 2026-02-17.

## Роль в системе

`methods` используется там, где вычисления оформляются как переиспользуемые typed methods (causal/econometrics/optimization и др.) с явным контрактом входов/выходов, независимым от базового Trinity механизма.

## Архитектурный поток

```text
FoundryMethod protocol
        -> MethodRegistry / Discovery
        -> SlotLinker + MethodComposer (DAG)
        -> Backend dispatch (JAX / NumPy / Solver)
        -> optional compile/specialization/artifacts/testing
```

## Ключевые компоненты

- `base.py`
  - ABI (`FoundryMethod`, `MethodSignature`, `MethodMetadata`, `SlotSpec`, `ParameterSpec`).
  - Декоратор `@foundry_method`, semver/FQN проверки, архитектурные инварианты.

- `registry.py`
  - Thread-safe singleton `MethodRegistry`.
  - Регистрация, lazy loading, resolve/query по версиям и критериям.

- `discovery.py`
  - Discovery через entry points и filesystem sources.
  - Bootstrap регистрации методов в runtime.

- `linker.py`
  - Проверка совместимости slot-ов (type/unit/shape), формирование bindings.

- `composer.py`
  - Сборка DAG цепочек (`graphlib.TopologicalSorter`), order/conflict validation.

- `resolution.py`
  - Version policies: `EXACT`, `LATEST_COMPATIBLE`, `LATEST`, `PINNED`.

- `compiler.py`, `specialization.py`
  - JAX compile path, specialization keys, compilation cache.

- `artifacts.py`, `artifacts_parts.py`, `components_bridge.py`
  - Provenance/evidence артефакты и интеграция с `core.components`.

- `catalog_snapshot.py`
  - Снимок текущего каталога методов (`MethodCatalogSnapshot`) и persistence в CAS.

## Backends

- `backends/jax_runner.py` — JAX/JIT path.
- `backends/numpy_runner.py` — NumPy path.
- `backends/solver_runner.py` — solver path (LP/MILP/IO).
- `backends/dispatch.py` — `MethodDispatcher`.
- `backends/chain_executor.py` — heterogeneous chain execution между backend-ами.

## Каталог методов

Основные реализации находятся в `methods/catalog/*`:
- `catalog/causal/`
- `catalog/econometrics/`
- `catalog/optimization/`

Совместимость с legacy import paths:
- `methods/causal/*`, `methods/econometrics/*`, `methods/optimization/*` — compatibility shims, переэкспортирующие `catalog/*`.

## Тестирование

`testing/` включает:
- protocol/signature checks;
- JAX checks (jit/vmap/grad);
- numerical/determinism проверки;
- solver/numpy/jax suite + golden regression records.

## Связь с другими директориями

`methods` зависит от:
- `core/registry`, `core/discovery`, `core/backends`, `core/components`, `core/canon`;
- `ir/analytics/*` для контрактов результатов методов.

Используется в:
- `scientist/compute/runner.py`;
- `scientist/nodes/builtins/planning/build_method_catalog_snapshot.py`;
- `packs/roads/foundry_methods.py` и других method-oriented сценариях.

## Текущее состояние и ограничения

- В дереве много shim/decomposition файлов для миграционной совместимости.
- Существенная часть методов зависит от optional deps (`statsmodels`, `linearmodels`, `econml`, solver libs).
- Строгая проверка slot compatibility и semver resolution применяется до runtime исполнения.
