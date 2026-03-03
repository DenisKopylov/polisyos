# Foundry (`polisyos.foundry`)

Foundry — вычислительный слой Policy Engine: компиляция Trinity-политик, исполнение графа механизмов и выпуск артефактов симуляции в CAS.

Актуально по коду на 2026-03-03.

## Роль в системе

Foundry связывает декларативный IR и исполняемый runtime-контур:

```text
ir.trinity_bundle + core.registry_bundle
          |
          v
   foundry.compile
          |
          v
program_graph + exec_plan (+ slot_layout, treasury_plan)
          |
          v
foundry.data_plane (input bindings + bound state snapshot)
          |
          v
  foundry.execute
          |
          v
state_delta + metrics + state_snapshot + simulation_result
```

## Границы ответственности

### Foundry отвечает за

- компиляцию `ir.trinity_bundle` в `ProgramGraph` и `ExecPlan`;
- patch-first исполнение механизмов и merge по правилам слотов;
- compile/runtime guardrails: link/conflict/cost/constraints;
- выпуск артефактов (`state_delta`, `metrics`, `state_snapshot`, `simulation_result`);
- прикладные подсистемы: `methods`, `calibration`, `uncertainty`, `agent_sim`, `plugins`.

### Foundry не отвечает за

- workflow-оркестрацию и пайплайны экспериментов (`polisyos.scientist`);
- долгосрочное хранение внешних бизнес-данных вне артефактного слоя;
- продуктовый UX/API поверх научных сценариев.

## Основной pipeline

1. `compile/` (`compile.api.compile`)
- Поддерживается только `policy_ref.kind == "ir.trinity_bundle"`.
- Выполняется `link_trinity`, сборка `ProgramGraph`, затем `ExecPlan`.
- Добавляются производные артефакты: `slot_layout`, `treasury_plan`.
- Перед выпуском результата выполняются compile-time conflict check и optional cost gating.

2. `data_plane/` (`build_input_bindings`)
- Из `DataSnapshot` и `RegistryBundle` строится `foundry.input_bindings`.
- Материализуется `bound_state_snapshot_ref` для фактического исполнения.
- Поддерживаются auto-rules биндинга по доступным путям payload.

3. `execute/` (`execute.api.execute`)
- Источник состояния берется из `input_bindings_ref`.
- Запускается `execute_program_graph`, затем применяется `state_delta`.
- Формируется `simulation_result` + ссылки на метрики/constraint report/environment manifest.

4. `executor.py` и `_executor_*`
- Для Trinity-графа используется op-контур: `make_mask -> apply_mechanism -> merge_state -> check_constraints`.
- Для `method`-узлов включается dispatch через `foundry.methods.backends`.
- Ошибки method-узлов фиксируются как события и не валят весь прогон автоматически.

## Карта директорий

### Ядро исполнения

- `compile/`, `execute/`, `executor.py`, `_executor_*.py`: фасады compile/execute и оркестрация ProgramGraph.
- `data_plane/`: преобразование входных data snapshots в bound Foundry state.
- `merge_engine.py`, `patch_vm.py`, `constraints_engine.py`, `conflict_checker.py`, `cost_model.py`: merge и guardrails.
- `registry.py`, `mechanisms/`, `agents.py`, `queue.py`, `specs.py`: реестр механизмов и встроенные реализации.

### Прикладные подсистемы

- `methods/`: typed method ABI, registry/discovery, DAG composition, backend dispatch.
- `calibration/`: подстройка trainable-параметров по целевым рядам.
- `uncertainty/`: propagation неопределенности (delta/monte-carlo).
- `agent_sim/`: отдельный ABM/RL execution contour.
- `plugins/`: plugin-слой поверх `agent_sim` для multi-domain симуляций.
- `analysis/`: пост-метрики распределительных эффектов.

### Служебные зоны

- `runtime/`: JIT-aware instrumentation и runtime helpers.
- `contracts/`, `layout.py`, `trace.py`, `utils.py`: контракты и утилиты.
- `domain/`: заготовки доменной schema-слойки (минимальный объём).
- `engine/`: сейчас фактически пустой каталог (технический резерв).

## Встроенный реестр механизмов

`registry.MECHANISM_REGISTRY` включает:

- `adaptive_agent`
- `tax_subsidy`
- `income_tax`
- `labor_market`
- `queue`

## Ключевые инварианты

- Patch-first: механизмы эмитят патчи, а не мутируют состояние напрямую.
- Merge-rule driven: итоговое значение слота определяется registry-правилом merge.
- Artifact-first: ключевые шаги пайплайна сохраняют CAS-артефакты.
- Determinism-first: seed-driven execution + (опционально) environment fingerprint.
- Public API lazy-export: пакет `polisyos.foundry` экспортирует `compile` и `execute`.

## Связь с другими директориями

Foundry зависит от:

- `polisyos/core/*` (artifacts, compiler report, contracts, registry, observability);
- `polisyos/ir/*` (trinity/linker/kernel/analytics contracts).

Foundry используется в:

- `polisyos/scientist/adapters/foundry_bridge.py`;
- `polisyos/scientist/nodes/builtins/*` (bind inputs, run simulation, uncertainty, method catalog);
- `polisyos/scientist/compute/runner.py`;
- `polisyos/packs/roads/foundry_methods.py`.

## Текущее состояние и ограничения

- `compile` остается Trinity-only.
- `constraints_engine.py` пока placeholder; рабочая проверка ограничений живет в `_executor_ops.check_constraints`.
- `runtime.step()` и scan-утилиты в `runtime/` — вспомогательный контур, не основной production executor.
- `domain/` и `engine/` пока не являются основным execution path Foundry.

## README поддиректорий

- `agent_sim/README.md`
- `calibration/README.md`
- `methods/README.md`
- `methods/catalog/README.md`
- `methods/catalog/causal/README.md`
- `plugins/README.md`
- `uncertainty/README.md`

## Быстрый API-ориентир

- `polisyos.foundry.compile(store, request)`
- `polisyos.foundry.execute(store, request)`
- `polisyos.foundry.data_plane.build_input_bindings(...)`
- `polisyos.foundry.executor.execute_program_graph(...)`
- `polisyos.foundry.executor.apply_state_delta_and_snapshot(...)`
