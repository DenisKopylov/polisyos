# Methods (`polisyos.foundry.methods`)

`methods` - подсистема Foundry для декларативных вычислительных методов: описание ABI, регистрация, компоновка цепочек и multi-backend исполнение.

Актуально по коду на 2026-02-10.

## Роль в системе

`methods` нужен для сценариев, где вычисления оформляются как переиспользуемые typed methods (causal/econometrics/optimization и др.) и исполняются вне базового Trinity механизма.

## Архитектурный поток

```
FoundryMethod protocol
        -> MethodRegistry / Discovery
        -> SlotLinker + MethodComposer (DAG)
        -> Backend dispatch (JAX / NumPy / Solver)
        -> optional artifacts + testing
```

## Ключевые компоненты

- `base.py`
  - ABI (`FoundryMethod`, `MethodSignature`, `MethodMetadata`, `SlotSpec`, `ParameterSpec`).
  - декоратор `@foundry_method` и базовые архитектурные проверки.

- `registry.py`
  - thread-safe singleton `MethodRegistry`.
  - регистрация, lazy registration, version-aware resolve/query.

- `discovery.py`
  - bootstrap из entry points и filesystem source.

- `linker.py`
  - связывание output/input slot-ов с type/unit/shape compatibility проверками.

- `composer.py`
  - построение и валидация DAG цепочек методов (`graphlib.TopologicalSorter`).

- `resolution.py`
  - semver resolution policies (`EXACT`, `LATEST_COMPATIBLE`, `LATEST`, `PINNED`).

- `compiler.py`, `specialization.py`
  - JAX compilation path, deterministic specialization keys, compilation cache.

- `artifacts.py`, `artifacts_parts.py`, `components_bridge.py`
  - provenance artifacts и интеграция с `core.components`.

## Backends

- `backends/jax_runner.py` - JAX/JIT исполнение.
- `backends/numpy_runner.py` - NumPy исполнение.
- `backends/solver_runner.py` - solver-путь (LP/MILP классы задач).
- `backends/dispatch.py` - `MethodDispatcher` singleton.
- `backends/chain_executor.py` - heterogeneous chain execution с адаптацией состояния между backend-ами.

## Каталоги методов

Основные реализации находятся в `methods/catalog/*`:
- `catalog/causal/` - causal inference и HTE методы.
- `catalog/econometrics/` - panel/IV/time-series методы.
- `catalog/optimization/` - optimization методы (LP/MILP/IO).

Важно:
- директории `methods/causal`, `methods/econometrics`, `methods/optimization` в текущем состоянии являются compatibility shims и переэкспортируют `catalog/*`.

## Тестирование

`testing/` включает:
- protocol и signature checks;
- JAX checks (jit/vmap/grad);
- numerical/determinism проверки;
- golden regression records.

## Связь с другими директориями

`methods` зависит от:
- `core/registry`, `core/discovery`, `core/backends`, `core/components`, `core/canon`;
- `ir/analytics/*` (контракты для causal/econometrics/optimization результатов).

`methods` используется в:
- `scientist/compute/runner.py`;
- `packs/roads/foundry_methods.py`;
- узлах scientist, где нужны causal/econometric/optimization вычисления.

## Текущее состояние и ограничения

- В дереве много compatibility и decomposition файлов (включая shim-модули) для миграционной совместимости.
- Ряд методов требует optional dependencies (например statsmodels/linearmodels/econml/solver libs); при их отсутствии доступны только совместимые части.
- Строгие правила совместимости slot-ов и semver resolution применяются на этапе композиции/регистрации, до runtime исполнения.
