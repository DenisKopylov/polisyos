# Foundry (`polisyos.foundry`)

Foundry - вычислительный backend для компиляции и исполнения политик в формате Trinity IR.
Основной фокус: детерминированное patch-based исполнение, артефактный пайплайн (CAS) и интеграция с `scientist`-оркестрацией.

Актуально по коду на 2026-02-10.

## Роль в системе

Foundry находится между декларативной политикой (`ir/`) и прикладными сценариями (`scientist/`, `packs/`):

```
ir.trinity_bundle + registry_bundle
          |
          v
  foundry.compile
          |
          v
 program_graph + exec_plan (+ slot_layout, treasury_plan)
          |
          v
 foundry.data_plane (input bindings)
          |
          v
  foundry.execute / foundry.executor
          |
          v
 state_delta + metrics + state_snapshot + simulation_result
```

## Границы ответственности

Foundry отвечает за:
- компиляцию Trinity-политики в исполняемый граф;
- выполнение механизмов по patch-first модели;
- применение merge-правил и проверку compile-time конфликтов;
- сохранение промежуточных и итоговых результатов в CAS;
- подсистемы калибровки, распространения неопределенности и распределительного анализа.

Foundry не отвечает за:
- хранение бизнес-данных вне CAS;
- пользовательский UX/оркестрацию экспериментов (это зона `scientist/`);
- сетевую интеграцию/LLM-логику.

## Ключевой execution pipeline

1. `compile/` (`compile.api.compile`)
- Принимает `CompileRequest`.
- В текущей реализации поддерживает только `policy_ref.kind == "ir.trinity_bundle"`.
- Строит `ProgramGraph`, `ExecPlan`, `SlotLayout`, `TreasuryPlan`.
- Делает link (`ir.linker`), compile-time conflict check (`conflict_checker.py`) и optional cost gating (`cost_model.py`).

2. `data_plane/` (`build_input_bindings`)
- Связывает `DataSnapshot` с `SlotRegistry`.
- Материализует `StateSnapshot` для запуска (`bound_state_snapshot_ref`).

3. `execute/` (`execute.api.execute`)
- Разрешает входное состояние через `input_bindings_ref`.
- Вызывает `execute_program_graph`.
- Применяет `StateDelta` к состоянию и сохраняет новый `StateSnapshot` + `SimulationResult`.

4. `_executor_*` (ядро исполнения)
- Обход узлов графа в порядке `ExecPlan.order`.
- Selector evaluation → запуск механизмов → сбор patch records.
- Merge patch records в `PatchOp` (`patch_vm.py`, `merge_engine.py`).
- Constraint check (runtime) и сохранение `metrics`/`state_delta`.

## Архитектура директорий

### Ядро исполнения
- `contracts/` - канонические state/mechanism/fidelity контракты (`GlobalState`, `Mechanism`, `FidelityLevel`).
- `mechanisms/` - встроенные механизмы (fiscal/labor) + `TreasuryPlan`.
- `registry.py`, `specs.py` - реестр и валидация параметров механизмов.
- `compile/` - Trinity IR → `ProgramGraph`/`ExecPlan`.
- `execute/`, `executor.py`, `_executor_*.py` - исполнение графа, патчинг, snapshot IO.
- `merge_engine.py`, `patch_vm.py` - merge semantics и PatchOp materialization.
- `conflict_checker.py` - статический анализ конфликтов записи в слоты.
- `layout.py`, `cost_model.py`, `trace.py` - layout/cost/trace служебные компоненты.
- `data_plane/` - подготовка входных bindings и bound state snapshot.

### Расширения и аналитика
- `calibration/` - градиентная калибровка (JAX + optax, bijectors, Laplace uncertainty).
- `uncertainty/` - propagation неопределенности (Delta / Monte Carlo / Analytical helpers).
- `analysis/` - distributional analytics (Gini, Palma, quintiles, winners/losers).
- `runtime/` - observability + JIT-aware wrappers + environment fingerprint + NaN guard.

### Крупные подсистемы
- `methods/` - отдельная подсистема декларативных вычислительных методов (registry/composer/backends/catalog/testing).
- `agent_sim/` - расширенный RL/agent-based стек для симуляций.
- `plugins/` - plugin API для доменных симуляторов и composable domain setup.

## Встроенные механизмы (текущий registry)

`registry.MECHANISM_REGISTRY` включает:
- `adaptive_agent`
- `tax_subsidy`
- `income_tax`
- `labor_market`
- `queue`

## Инварианты, на которых держится Foundry

- Patch-first updates: механизмы эмитят патчи, а не мутируют состояние напрямую.
- Merge-rule driven application: финальная запись в слот определяется `SUM/OVERRIDE/PRIORITY/ERROR` правилами.
- Artifact-first pipeline: все ключевые этапы фиксируются в CAS ссылками.
- Determinism by design: seed-driven execution + `TreasuryPlan` + environment capture/fingerprint.
- Lazy API surface: `polisyos.foundry` экспортирует `compile` и `execute` через lazy import.

## Связь с другими директориями

Foundry зависит от:
- `polisyos/core/*` (artifacts, contracts, compiler report, registry, observability);
- `polisyos/ir/*` (trinity, kernel registries, analytics contracts, selector/schedule DSL).

Foundry используется в:
- `polisyos/scientist/adapters/foundry_bridge.py`;
- `polisyos/scientist/compute/runner.py`;
- `polisyos/scientist/nodes/builtins/simulate/*` (distributional analysis, uncertainty propagation);
- `polisyos/packs/roads/foundry_methods.py`.

## Отдельные README внутри Foundry

- `agent_sim/README.md`
- `calibration/README.md`
- `methods/README.md`
- `plugins/README.md`

Эти документы покрывают детали конкретных подсистем; данный файл - обзор архитектуры и интеграционных границ Foundry.

## Текущее состояние и ограничения

- `compile` сейчас Trinity-only (другие policy input kinds не поддержаны).
- `constraints_engine.py` остается заглушкой; фактическая runtime-проверка ограничений выполняется в executor (`_executor_ops.check_constraints`).
- `runtime.step()` - placeholder-функция (используется как каркас для JIT/instrumentation pipeline, не как отдельный production executor).

## Быстрый ориентир по API

- Входные точки пакета:
  - `polisyos.foundry.compile(store, request)`
  - `polisyos.foundry.execute(store, request)`
- Для low-level операций исполнения:
  - `polisyos.foundry.executor.execute_program_graph(...)`
  - `polisyos.foundry.executor.apply_state_delta(...)`
  - `polisyos.foundry.executor.load_state_snapshot(...)`
