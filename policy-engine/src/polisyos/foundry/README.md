# Foundry (`polisyos.foundry`)

Foundry — вычислительный слой Policy Engine для компиляции и исполнения Trinity-политик, плюс набор расширений для калибровки, агентных симуляций, методов и uncertainty-аналитики.

Актуально по коду на 2026-02-17.

## Роль в системе

Foundry связывает декларативное описание политики (`ir/`) с исполняемыми симуляционными артефактами в CAS:

```text
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
- компиляцию Trinity IR в `ProgramGraph`/`ExecPlan`;
- patch-first исполнение механизмов и merge semantics по слотам;
- материализацию `state_delta`, `metrics`, `state_snapshot`, `simulation_result` в CAS;
- compile/runtime проверки (link/conflict/cost/constraints);
- прикладные подсистемы `calibration`, `uncertainty`, `analysis`, `methods`, `agent_sim`, `plugins`.

Foundry не отвечает за:
- workflow-оркестрацию экспериментов (`scientist/`);
- хранение внешних бизнес-данных вне артефактного слоя;
- UX и внешние интеграционные интерфейсы.

## Ключевой execution pipeline

1. `compile/` (`compile.api.compile`)
- Сейчас поддерживается только `policy_ref.kind == "ir.trinity_bundle"`.
- Выполняется `link_trinity`, затем строятся `ProgramGraph` и `ExecPlan`.
- Дополнительно формируются `slot_layout` и `treasury_plan`.
- Перед выпуском результата идут compile-time conflict check и optional cost gating.

2. `data_plane/` (`build_input_bindings`)
- Из `DataSnapshot` и `RegistryBundle` строит deterministic `foundry.input_bindings`.
- Материализует `bound_state_snapshot_ref` для исполнения.
- Поддерживает auto-rules (если правила биндинга не переданы явно).

3. `execute/` (`execute.api.execute`)
- Разрешает входное состояние через `input_bindings_ref`.
- Запускает `execute_program_graph`.
- Применяет `state_delta`, создает новый `state_snapshot` и `simulation_result`.

4. `executor.py` + `_executor_*`
- Выполняет graph-order обход.
- Для Trinity-графов использует op-узлы `make_mask -> apply_mechanism -> merge_state -> check_constraints`.
- Патчи сливаются в `PatchOp` и применяются через merge rules.
- Поддерживает и `method`-узлы (dispatch через `foundry.methods.backends`).

## Архитектура директорий

### Ядро исполнения
- `compile/`, `execute/`, `executor.py`, `_executor_*.py` — compile/execute фасады и оркестрация графа.
- `registry.py`, `specs.py`, `mechanisms/`, `agents.py`, `queue.py` — реестр и встроенные механизмы.
- `merge_engine.py`, `patch_vm.py` — merge-политики и материализация patch ops.
- `conflict_checker.py`, `cost_model.py`, `constraints_engine.py` — preflight/runtime guardrails.
- `data_plane/` — связывание входных данных с Foundry state.
- `contracts/`, `layout.py`, `trace.py`, `utils.py` — контракты и служебные типы.

### Аналитика и runtime-утилиты
- `analysis/` — distributional analytics (gini/palma/quintiles/winners-losers).
- `runtime/` — JIT-aware instrumentation, environment fingerprint, NaN guard.
- `uncertainty/` — propagation неопределенности (delta/monte-carlo + aggregation).

### Крупные подсистемы
- `methods/` — typed methods ABI, registry/discovery, DAG composition, backend dispatch.
- `agent_sim/` — отдельный agent-based/RL контур (graph/population/distribution dynamics).
- `calibration/` — градиентная калибровка параметров и uncertainty из Hessian/Laplace.
- `plugins/` — plugin-архитектура доменных симуляторов поверх agent_sim.

## Встроенные механизмы (текущий registry)

`registry.MECHANISM_REGISTRY` включает:
- `adaptive_agent`
- `tax_subsidy`
- `income_tax`
- `labor_market`
- `queue`

## Инварианты Foundry

- Patch-first updates: механизмы эмитят патчи, а не мутируют state напрямую.
- Merge-rule driven application: итог для каждого слота определяется merge-правилом.
- Artifact-first pipeline: ключевые результаты фиксируются в CAS ссылками.
- Determinism by design: seed-driven execution + environment capture/fingerprint.
- Lazy package API: `polisyos.foundry` публично экспортирует `compile` и `execute`.

## Связь с другими директориями

Foundry зависит от:
- `polisyos/core/*` (artifacts, contracts, compiler report, registry, observability);
- `polisyos/ir/*` (trinity, kernel registries, selector/schedule DSL, analytics contracts).

Foundry используется в:
- `polisyos/scientist/adapters/foundry_bridge.py`;
- `polisyos/scientist/nodes/builtins/*` (compile, run_simulation, bind_foundry_inputs, uncertainty/distributional passes);
- `polisyos/scientist/compute/runner.py`;
- `polisyos/packs/roads/foundry_methods.py`.

## README внутри Foundry

- `agent_sim/README.md`
- `calibration/README.md`
- `methods/README.md`
- `plugins/README.md`
- `uncertainty/README.md`

## Текущее состояние и ограничения

- `compile` остаётся Trinity-only.
- `constraints_engine.py` — placeholder; фактическая runtime проверка ограничений идёт в executor (`_executor_ops.check_constraints`).
- `runtime.step()` — каркасная функция для JIT/instrumentation path, не отдельный production executor.
- `domain/` пока содержит только базовые schema-типы и не является основным execution path Foundry.

## Быстрый ориентир по API

- `polisyos.foundry.compile(store, request)`
- `polisyos.foundry.execute(store, request)`
- `polisyos.foundry.executor.execute_program_graph(...)`
- `polisyos.foundry.executor.apply_state_delta_and_snapshot(...)`
- `polisyos.foundry.data_plane.build_input_bindings(...)`
