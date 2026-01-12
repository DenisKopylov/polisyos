---
name: One-path consolidation backlog
overview: Консолидация кодовой базы Policy Engine до единственного «официального пути» исполнения (workflow.py + flow_nodes.py + patch VM), с compat window/ADR, удалением/изоляцией legacy модулей и закреплением гейтами (smoke workflow + архитектурные линтеры).
todos:
  - id: adr-compat-window
    content: Добавить docs/adr/ и 3 ADR с compat window и removal point
    status: completed
  - id: scientist-one-entrypoints
    content: "Сделать scientist/__init__.py единственными entrypoints: build_workflow + run_experiment; деприкейт legacy импорты"
    status: completed
  - id: scientist-remove-legacy-nodes-and-logs
    content: Перенести scientist/orchestrator/nodes.py и save_* (logs/) в _legacy или удалить; запретить logs/ на workflow пути; добавить тест 'no logs/'
    status: completed
  - id: foundry-legacy-engine-removal
    content: Перенести foundry/engine и basic_simulation в _legacy; удалить/переписать tests/foundry/test_production_kernel.py; обновить README
    status: completed
  - id: ir-compat-loader
    content: "Добавить ir/loaders.py: load_policy(any)->PolicySurfaceIR; v1->v2 миграция; tools/migrate_ir.py через один путь"
    status: completed
  - id: runner-unify-execution
    content: Реализовать scientist/compute/runner.py (не stub); flow_nodes.run_sim вызывает runner; backend interface Local/Ray stub
    status: completed
  - id: hitl-gate-postflight
    content: Встроить GateRequest/GateDecision в POSTFLIGHT_GOV; integration тест stop/resume
    status: completed
  - id: fabric-evidence-mvp
    content: Сделать evidence_ref обязательным на критическом пути FabricResult; ingestion пишет evidence как CAS; contract gate на отсутствие evidence
    status: in_progress
  - id: trust-two-pass
    content: Сделать TrustRegistry артефактом; реализовать two-pass compare и uncertainty контейнер; протянуть в DecisionPacket
    status: pending
  - id: foundry-batch-and-constraints
    content: Добавить execute_program_batch + deterministic treasury; constraints как артефакты + ConstraintReport + тесты
    status: pending
  - id: runtime-portable-artifactref
    content: Убрать абсолютные пути из runtime ArtifactRef; хранить относительный путь/идентификаторы; миграция старых runs + тест переноса папки
    status: pending
  - id: dependency-leaks-and-ci
    content: Убрать TYPE_CHECKING утечки через вынос общих типов; включить CI гейты (lint_imports, lint_foundry, gen_schema, pytest unit/integration)
    status: pending
---

# План консолидации “one-path” (MVP + зачистка legacy)

## Контекст (факты из текущего кода)

- **Официальная линия Scientist уже есть**: `build_workflow()` в [`policy-engine/src/polisyos/scientist/orchestrator/workflow.py`](policy-engine/src/polisyos/scientist/orchestrator/workflow.py).
```41:66:policy-engine/src/polisyos/scientist/orchestrator/workflow.py
def build_workflow():
    workflow = StateGraph(ExperimentState)
    # ...
    workflow.add_node("run_sim", _with_phase(Phase.EXECUTE, run_sim_node))
    # ...
    return workflow.compile()
```

- **Параллельный legacy-путь Scientist существует**: `scientist/orchestrator/nodes.py` делает прямую симуляцию, использует `print()`, а также пишет артефакты в `logs/` через `save_run_record_json()` / `save_decision_packet()`.
```20:61:policy-engine/src/polisyos/scientist/orchestrator/nodes.py
def simulator_node(state: ExperimentState) -> ExperimentState:
    """Запускает симуляцию..."""
    print("   [Simulator] Initializing UDF connection...")
    # ...
    db.save_run_record(run_record)
    save_run_record_json(run_record)
```

- **Новый workflow-путь уже пишет артефакты через runtime API** (`log_artifact`, `append_audit`) в `runs/<run_id>/...`.
```53:88:policy-engine/src/polisyos/runtime/api.py
def log_artifact(*, run_id: str, artifact_type: str, payload: Any, ...):
    run_dir = _run_dir(base_dir, run_id)
    artifact_dir = run_dir / "artifacts" / artifact_type
    # ...
    ref = ArtifactRef(
        artifact_type=artifact_type,
        path=str(path),
        media_type=media_type,
        schema_version=schema_version,
        step=step,
    )
```

- **Foundry legacy engine существует**: `policy-engine/src/polisyos/foundry/engine/*` и демо `basic_simulation.py`. Есть тест, который прямо зависит от legacy (`tests/foundry/test_production_kernel.py`).
- **IR v2 (Surface IR) уже в употреблении в smoke**: `tests/integration/test_workflow_smoke.py` использует `PolicySurfaceIR` и `build_workflow()`.
- **IR v1 (PolicyRequestIR) живёт в коде и доках**: `polisyos/ir/contract.py`, `polisyos/scientist/orchestrator/compiler.py`.
- **Portability проблема подтверждена**: `runtime/manifest.ArtifactRef.path` хранит строковый путь, который сейчас формируется как `str(path)` (фактически абсолютный/машино-зависимый).

---

## 0) Правило игры: compat window + стратегия удаления

### Задачи

- **0.1. Ввести docs/adr/**
  - Добавить 3 ADR (шаблон: дата/решение/контекст/последствия/точка удаления):
    - “Удаляем legacy Foundry engine”
    - “Сводим Scientist на flow_nodes-only”
    - “IR v1.0 → deprecate → remove”
  - Зафиксировать:
    - **compat window** (например: 2 минорных релиза или 60 дней)
    - правило “сначала `_legacy/` + lint-ban, затем удаление”.

### Где в коде

- Новая папка: `policy-engine/docs/adr/`.

### DoD

- ADR содержат **дату**, **решение**, **последствия**, **точку удаления** (конкретная дата/версия/условие).

### Тесты/гейты

- **Каждый PR**: `tests/integration/test_workflow_smoke.py` зелёный.

---

## 1) Эпик: Удаление legacy и консолидация “одна парадигма”

### 1A) Scientist: выкинуть legacy-оркестрацию и запись в logs/

#### Задачи

- **1A.1. Заморозить публичные entrypoints**
  - В `polisyos/scientist/__init__.py` экспортировать **только**:
    - `build_workflow()` (из `scientist/orchestrator/workflow.py`)
    - официальный `run_experiment()` (добавить тонкую обёртку, если отсутствует), которая:
      - создаёт workflow
      - вызывает `.invoke(state)`
      - возвращает результат
  - Любые legacy-импорты должны эмитить `DeprecationWarning` с явным “use … instead”.

- **1A.2. Удалить/перенести legacy-модули**
  - Переместить в `polisyos/scientist/_legacy/`:
    - `polisyos/scientist/orchestrator/nodes.py` (legacy ноды)
    - `polisyos/scientist/orchestrator/compiler.py` (завязка на `PolicyRequestIR`)
    - любые legacy оптимизационные узлы/скрипты, которые не используются `workflow.py + flow_nodes.py`.
  - Оставить минимальные shims (если нужно) с `DeprecationWarning`.

- **1A.3. Убрать параллельную запись артефактов в logs/**
  - Удалить/задеприкейтить:
    - `save_decision_packet(..., base_dir=Path("logs"))` в `scientist/orchestrator/decision_packet.py`
    - `save_run_record_json(..., base_dir=Path("logs"))` в `scientist/orchestrator/run_record.py`
  - Альтернатива: оставить, но сделать их **внутренними** и по умолчанию писать в `runs/<run_id>/...` через `polisyos.runtime.log_artifact` + `append_audit`.

- **1A.4. Арх-гейт на запрет legacy**
  - Расширить `tools/lint_imports.py`:
    - запрет на импорт `polisyos.scientist._legacy` из runtime/production кода (разрешить только в tests или tools).

#### Где в коде

- [`policy-engine/src/polisyos/scientist/__init__.py`](policy-engine/src/polisyos/scientist/__init__.py)
- [`policy-engine/src/polisyos/scientist/orchestrator/workflow.py`](policy-engine/src/polisyos/scientist/orchestrator/workflow.py)
- [`policy-engine/src/polisyos/scientist/orchestrator/flow_nodes.py`](policy-engine/src/polisyos/scientist/orchestrator/flow_nodes.py)
- Legacy: [`policy-engine/src/polisyos/scientist/orchestrator/nodes.py`](policy-engine/src/polisyos/scientist/orchestrator/nodes.py)
- Линтер: [`policy-engine/tools/lint_imports.py`](policy-engine/tools/lint_imports.py)

#### DoD

- Единственный поддерживаемый путь запуска Scientist: `build_workflow()`/`run_experiment()`.
- Любая попытка импортировать legacy API даёт `DeprecationWarning`.
- Workflow больше **не создаёт** `logs/` и не зависит от `save_*`.

#### Тесты/гейты

- `tests/integration/test_workflow_smoke.py` зелёный.
- Новый integration-тест: “workflow не создаёт `logs/` в tmp_path”.

---

### 1B) Foundry: выкинуть legacy engine (SimulationKernel) и basic_simulation

#### Задачи

- **1B.1. Изолировать legacy Foundry**
  - Переместить:
    - `polisyos/foundry/engine/` → `polisyos/foundry/_legacy/engine/`
    - `polisyos/foundry/basic_simulation.py` → `polisyos/foundry/_legacy/basic_simulation.py`
  - Добавить lint-ban: “в основном коде нет импорта `polisyos.foundry._legacy`”.

- **1B.2. Переработать/удалить legacy тесты**
  - `tests/foundry/test_production_kernel.py`:
    - либо удалить как тест мёртвого кода,
    - либо переписать на новый путь (patch VM / program graph), чтобы не импортировать `foundry.engine`.

- **1B.3. Почистить docs**
  - Убрать из `polisyos/foundry/README.md` примеры импорта `foundry.engine.kernel.SimulationKernel` или пометить как `_legacy`.

#### Где в коде

- Legacy: `policy-engine/src/polisyos/foundry/engine/*`, `policy-engine/src/polisyos/foundry/basic_simulation.py`
- Линтер Foundry: `policy-engine/tools/lint_foundry.py` (дополнить правилом “no legacy imports”).
- Тест: `policy-engine/tests/foundry/test_production_kernel.py`

#### DoD

- В production-коде **нет** импортов `polisyos.foundry.engine`.
- Тесты не требуют legacy модулей.

#### Тесты/гейты

- `pytest` зелёный.
- `tools/lint_foundry.py` зелёный.

---

### 1C) IR: “v2 единственный путь”, v1 = compat → deprecate → remove

#### Задачи

- **1C.1. Один compat loader**
  - Добавить `polisyos/ir/loaders.py`:
    - `load_policy(any_payload) -> PolicySurfaceIR`
    - если вход — v1 (`PolicyRequestIR` или payload с v1-формой) → конвертация/миграция → v2.
  - Вся система (Scientist/Fabric/Foundry) принимает **только** `PolicySurfaceIR`.

- **1C.2. Единый pipeline миграций**
  - `tools/migrate_ir.py` должен дергать ровно тот же путь (`ir/loaders.py` / `ir.migrations.migrate_policy_ir`).

- **1C.3. Постепенная чистка v1**
  - `PolicyRequestIR`:
    - пометить deprecated
    - удалить после выполнения критериев (demos + workflow + тесты используют v2; v1 тесты либо удалены, либо только как migration-tests).

#### Где в коде

- v2: `policy-engine/src/polisyos/ir/surface.py` (`PolicySurfaceIR`, `schema_version="2.0"`)
- v1: `policy-engine/src/polisyos/ir/contract.py` (`PolicyRequestIR`)
- Миграции: `policy-engine/src/polisyos/ir/migrations/__init__.py`
- CLI: `policy-engine/tools/migrate_ir.py`

#### DoD

- Никакие runtime/production функции не принимают `PolicyRequestIR` на вход.
- Миграция реализована один раз и используется и в CLI, и в runtime.

#### Тесты/гейты

- Unit-тесты на `load_policy()` (v1→v2, v2 passthrough).
- Smoke workflow зелёный.

---

## 2) Эпик: Закрыть “частично реализовано” — Evidence/Trust в Fabric

### 2A) EvidenceBundle на критическом пути Fabric

#### Задачи (MVP)

- **2A.1. Определить MVP evidence** (как ты описал):
  - raw hash
  - `DatasetManifest` hash
  - segment hashes
  - reconciliation config hash
  - privacy pass info hash

- **2A.2. Сделать Evidence обязательным результатом Fabric на критическом пути**
  - Сейчас `core/contracts/fabric.FabricResult` уже имеет `evidence_ref`.
```74:86:policy-engine/src/polisyos/core/contracts/fabric.py
class FabricResult(BaseModel):
    # ...
    trust_policy_id: str | None = None
    evidence_ref: EvidenceBundleRef | None = None
```

  - Реализовать “официальный” API Fabric (MVP):
    - новый метод/функция, возвращающий `FabricResult` (а не просто `DataFrame`), и всегда заполняющий `evidence_ref`.

- **2A.3. Протянуть evidence через ingestion**
  - `fabric/ingestion.py`/`fabric/manifest.py`: писать evidence как CAS-артефакт рядом с manifest.

- **2A.4. Gate: без evidence нельзя в production-режиме**
  - Расширить `tests/contract/test_fabric_gates.py` сценарием: evidence отсутствует → блок.

#### Где в коде

- Контракты: `policy-engine/src/polisyos/core/contracts/fabric.py`
- Evidence builder: `policy-engine/src/polisyos/fabric/evidence.py`
- Входная точка UDF: `policy-engine/src/polisyos/fabric/udf/engine.py` (сейчас возвращает DataFrame)

#### DoD

- Любой dataset/query в системе имеет manifest + evidence.
- В “production” режиме отсутствие evidence — hard fail.

#### Тесты/гейты

- Contract: `tests/contract/test_fabric_gates.py` расширен.

---

### 2B) TrustPolicyRegistry + two-pass compare

#### Задачи

- **2B.1. Trust registry как артефакт**
  - Использовать существующую модель `ir/kernel/trust.py` (`TrustRegistry`, `two_pass_compare`).
  - Добавить хранение `TrustRegistry` как CAS-артефакта, аналогично `RegistryBundle`.

- **2B.2. Реальный pass apply_trust_policy(mode=two_pass_compare)**
  - В `fabric/udf/passes/` довести pass, который:
    - строит два плана (optimistic/pessimistic)
    - возвращает bounds/delta в строго типизированном контейнере (не “dict”).
  - Расширить `FabricResult`: `uncertainty: {value, lower, upper, method}` (с `schema_version`).

- **2B.3. Протянуть в Scientist**
  - `DecisionPacket` должен ссылаться на bounds (через артефакт-реф, а не raw dict).

#### DoD

- Two-pass даёт реально отличающиеся результаты на “грязных” данных.
- Bounds сохраняются как артефакт и попадают в decision packet.

#### Тесты

- Unit: “грязные данные → optimistic != pessimistic”.
- Integration: smoke workflow с trust-policy сохраняет bounds.

---

## 3) Эпик: Scientist — runner, HITL-gate, оптимизация как стандартный шаг

### 3A) Compute Runner как единая точка запуска симуляций

#### Задачи

- **3A.1. Реализовать runner поверх текущего Foundry runtime**
  - Сейчас `scientist/compute/runner.py` — заглушка.
  - Новый контракт: `runner.run(job_spec) -> JobResult`:
    - загружает артефакты (`ProgramGraphRef`, `ExecPlanRef`, `RegistryBundleRef`, `StateSnapshotRef`)
    - вызывает `foundry.executor.execute_program_graph` (как сейчас делает `run_sim_node`)
    - пишет refs через `polisyos.runtime.log_artifact` и аудит.

- **3A.2. Flow nodes не вызывают Foundry напрямую**
  - В `flow_nodes.py` заменить прямой вызов Foundry на `runner.run(...)`.

- **3A.3. Backend интерфейс**
  - `RunnerBackend` + `LocalBackend` (текущий путь)
  - `RayBackend` как скелет (без CI включения)

#### Где в коде

- `policy-engine/src/polisyos/scientist/compute/runner.py`
- `policy-engine/src/polisyos/scientist/orchestrator/flow_nodes.py`

#### DoD

- В `flow_nodes.py` нет прямого вызова Foundry.
- Переключение backend через config/ENV.

#### Тесты

- Smoke workflow зелёный.

---

### 3B) HITL реально включается (POSTFLIGHT_GOV)

#### Задачи

- **3B.1. Правила gate** (MVP):
  - legitimacy risk порог
  - PII-tier
  - wide uncertainty bounds
  - чувствительные механизмы выше порога

- **3B.2. Встроить gate в governor**
  - Сейчас `governor_node` в `flow_nodes.py` возвращает verdict, но не переводит workflow в “ожидание”.
  - Встроить `GateRequest`/`GateDecision` из `scientist/kernel/human_gate.py`.

- **3B.3. Тестируемая пауза/возобновление**
  - Для тестов: мок GateDecision.

#### DoD

- Workflow корректно “останавливается/возобновляется” при gate.

#### Тесты

- Integration: сценарий gate-required.
- Contract: сериализация GateRequest/Decision как артефакты.

---

### 3C) Optimization loop — стандартный DoE шаг

#### Задачи

- **3C.1. DoE → list[JobSpec]**
  - `scientist/doe/designs.py`: `compile_design(design) -> list[JobSpec]`.
  - Stable ordering + stable seeds.

- **3C.2. Optimizer как узел workflow**
  - После `analyze`: если objectives заданы → запустить optimizer → получить новую policy → повторить compile/run в рамках budget.
  - Все кандидаты/pareto-front как CAS-артефакты, а `DecisionPacket` ссылается.

#### DoD

- Оптимизация воспроизводима по seed.

#### Тесты

- Unit: стабильный результат/pareto по хэшам.
- Integration: мини-оптимизация 2–3 итерации.

---

## 4) Эпик: Foundry — batch и constraints как артефакты

### 4A) Batch / multi-scenario (vmap-first)

- Добавить `foundry/runtime.py: execute_program_batch(...)` через `jax.vmap`.
- Treasury: детерминированное развертывание ключей `[batch, nodes]`.

**Тесты**: determinism, batch=1 == single.

### 4B) Constraints Engine: расширяемый и компилируемый

- `ConstraintSpec` хранить как артефакт в `RegistryBundle`.
- `ProgramOp.check_constraints` принимает список `constraint_id`.
- Executor выдаёт `ConstraintReport` (артефакт + trace).
- Repair стратегии: clip/penalty/hard-fail.

**Тесты**: `tests/foundry/test_constraints_executor.py` расширить на режимы.

---

## 5) Эпик: Runtime portability — убрать абсолютные пути из ArtifactRef

### Задачи

- **5.1. Переносимый ArtifactRef**
  - В runtime-манифесте хранить:
    - `artifact_id` (CAS hash) + `kind` + `logical_name/type`
    - `relative_path` относительно run root (или отказаться от пути вовсе)
  - `RunManifest` хранит `run_root` отдельно.

- **5.2. Миграция старых runs**
  - Дополнить `tools/migrate.py` миграцией run manifests: `path -> relative`.

### DoD

- Перенос папки `runs/` не ломает чтение `DecisionPacket`/refs.

### Тесты

- `tests/core_phase0/test_run_context.py` + integration: переместить `runs` и прочитать.

---

## 6) Эпик: Устранить архитектурные “утечки” зависимостей

### Задачи

- Вынести общие типы (например, `RunRecord` как концепт) вверх:
  - `polisyos/runtime/contracts.py` или `polisyos/core/contracts/runtime.py`.
- Убрать `TYPE_CHECKING`-импортные костыли, закрепить `tools/lint_imports.py --fail-on-type-checking`.

### DoD

- `tools/lint_imports.py` показывает 0 forbidden edges (включая TYPE_CHECKING).

---

## 7) Эпик: CI/качество — закрепить дисциплину

### Задачи

- **7.1. GitHub Actions (MVP)**
  - jobs:
    - `python -m tools/lint_imports.py --fail-on-cycles --fail-on-type-checking`
    - `python -m tools/lint_foundry.py`
    - `python -m tools/gen_schema.py --check`
    - `pytest -m "not integration"`
    - отдельный job `pytest -m integration` (на main или по расписанию)

- **7.2. Pre-commit**
  - black/ruff + запуск `lint_imports`/`lint_foundry`.

### DoD

- Нельзя смёрджить PR без зелёных гейтов.

---

## Приоритетный порядок (чтобы избежать “рефакторинговой зимы”)

1. **0 + 1A**: ADR + закрыть Scientist legacy и `logs/`.
2. **1B**: вынести Foundry legacy в `_legacy` + удалить/переписать зависимые тесты.
3. **3A + 3B**: runner + HITL (без изменения математики исполнения).
4. **2A + 2B**: Evidence + Trust (перевод “идеи” в артефакты).
5. **4A + 4B**: batch + constraints compile.
6. **5 + 6**: portability + dependency leaks.
7. **7**: CI как цемент (можно запускать параллельно ранним этапам).

---

## Мини-шаблон DoD для любого PR

- ✅ `pytest` (unit+contract) зелёный
- ✅ `tests/integration/test_workflow_smoke.py` зелёный (если PR трогает любую фазу)
- ✅ `tools/lint_imports.py` и `tools/lint_foundry.py` зелёные
- ✅ `tools/gen_schema.py --check` зелёный
- ✅ Не появляется новых файлов в `logs/`
- ✅ Любая новая сущность фиксируется как артефакт-реф (CAS/run manifest), а не “просто dict”