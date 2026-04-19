# E1.6 (Phase 6) — Scientist: engine skeleton + Node protocol (workflow engine v0 + node registry)

**Repo snapshot date**: 2026-02-03  
**Scope**: `policy-engine/src/polisyos/scientist/engine/*` (+ minimal builtins), `policy-engine/tests/scientist/*`, `policy-engine/tests/contract/*`  
**Primary goal**: превратить Scientist из “набора хардкодных шагов” в **минимальный workflow‑движок**, который исполняет DAG узлов по единому протоколу и может оркестрировать Foundry/Fabric/Scholar/Lex через порты.

---

## 0) Цель фазы (что должно измениться “в ощущениях”)

После E1.6 Scientist получает “скелет” workflow engine:

1) **Единый протокол Node**:
   - Node — “чёрный ящик”: получает `ExecutionContext` + `ExperimentState`, возвращает `NodeOutcome`.
   - Узел не обязан знать про остальной workflow (кроме своих параметров и state).

2) **Единый формат WorkflowSpec (DAG)**:
   - serializable контракт (Pydantic v2), пригодный для будущих declarative workflows (E2/E3),
   - без hardcoded ветвлений внутри engine.

3) **Единый executor v0**:
   - правильное построение DAG, валидация, топологическая сортировка,
   - исполнение (сначала последовательное), минимальная поддержка “resume” через `status=skip`.

4) **Registry/Discovery узлов v0**:
   - in‑process registry + минимум discovery через `polisyos.core.components` (если возможно),
   - без экосистемы пакетов E3 (маркетплейс/pack install — позже).

5) **Минимальные built‑in узлы**:
   - 2–3 “пустых” узла для проверки engine (noop/set_state/emit_artifact),
   - без доменной логики (никакой “compile/simulate/legal” внутри engine).

**Важно:** E1.6 **не** переносит весь текущий business‑код Scientist в Nodes (это E1.7). В этой фазе мы строим фундамент и проверяем, что он исполним и трассируем.

---

## 1) Входные условия (после фаз 1–5)

### 1.1 Порты и ABI уже существуют

Из E1.4:

- `polisyos.core.contracts.*` — “ports” (только DTO/refs/Protocol без реализаций).
- `polisyos.core.components.*` — `ComponentId`, `ComponentMetadata`, `Capability`, `ComponentRegistry`, `Discovery`.
- `polisyos.core.run.context.RunContext` + `polisyos.core.trace.*` — базовый trace артефакт (`core.trace.jsonl`).

Из E1.5:

- Foundry умеет чистый `compile()/execute()` по контрактам `core.contracts.foundry` (CAS‑in/CAS‑out) и не зависит от Scientist.

### 1.2 Текущее состояние Scientist в репозитории (симптомы, которые E1.6 адресует)

На snapshot 2026-02-03:

- Есть хардкод‑оркестрация на LangGraph:
  - `polisyos.scientist.orchestrator.workflow.build_workflow()` собирает граф с условными роутингами,
  - `polisyos.scientist.orchestrator.flow_nodes` содержит большой объём доменной логики и прямых интеграций.
- Есть абстракция `polisyos.scientist.workflows` (engine_simple / engine_langgraph), но:
  - отсутствует единый Node protocol (ctx+state → outcome),
  - отсутствует единый serializable workflow spec (DAG как контракт),
  - отсутствует registry/discovery узлов с `ComponentId`.

E1.6 добавляет новый **канонический** слой: `polisyos.scientist.engine.*`.

---

## 2) Негол (явно вне фазы)

E1.6 **не** делает:

- перенос существующих `flow_nodes.py` в Node‑плагины (это E1.7),
- планирование/оптимизацию/LLM‑агенты/губернатор/рефлексию (они остаются в текущем Scientist до миграции),
- scheduler/parallel execution (только последовательный executor),
- Fabric World Graph / Scholar / Lex как подсистемы (это E2+), но `ExecutionContext` должен иметь порты под них,
- “расширение = установить пакет” (E3): на E1.6 registry/discovery минимальные.

---

## 3) Deliverables (что обязано появиться после E1.6)

### 3.1 Новый пакет engine (скелет)

Добавить пакет:

```
policy-engine/src/polisyos/scientist/engine/
  __init__.py
  errors.py
  state.py
  context.py
  protocol.py
  workflow_spec.py
  executor.py
  registry.py
  telemetry.py
  builtins/
    __init__.py
    noop.py
    set_state.py
    emit_artifact.py
```

Распределение ответственности по файлам (нормативно):

- `engine/errors.py` — только исключения (taxonomy из §4.0).
- `engine/state.py` — `ExperimentState` (Pydantic), без IO.
- `engine/context.py` — `ExecutionContext` + port Protocols, без реализаций портов.
- `engine/protocol.py` — `Node`, `NodeSpec`, `NodeOutcome`, `NodeEvent`, `NodeError`.
- `engine/workflow_spec.py` — `WorkflowSpec` + `NodeInvocation` + валидации (уникальность alias и т.п.).
- `engine/registry.py` — `NodeRegistry` + discovery adapter (entry_points/dev scan).
- `engine/executor.py` — последовательный executor v0 (DAG validate + execute + trace).
- `engine/telemetry.py` — span helpers + атрибуты (не должен импортировать heavy deps при выключенной observability).
- `engine/builtins/*` — только минимальные built‑in Nodes (noop/set_state/emit_artifact).

Инварианты пакета `polisyos.scientist.engine`:

- не импортирует `langgraph` (и любые orchestration-specific зависимости),
- не импортирует конкретные реализации Foundry/Fabric/Scholar/Lex (только контракты + Protocol),
- import side‑effects запрещены (особенно в `__init__.py`).

### 3.2 Тесты

- Unit tests для engine/executor/registry:
  - `policy-engine/tests/scientist/test_engine_executor_v0.py`
  - `policy-engine/tests/scientist/test_engine_registry_v0.py`
- Contract test для WorkflowSpec (serde):
  - `policy-engine/tests/contract/test_scientist_workflow_spec_contract.py`

### 3.3 Artifact kinds (ABI для engine)

Чтобы engine был воспроизводимым и не “жил только в памяти”, на E1.6 фиксируем минимальный набор kinds:

- `scientist.workflow_spec` — `WorkflowSpec` (DAG)
- `scientist.workflow_report` — `WorkflowReport` (execution summary; рекомендовано)
- `scientist.experiment_state` — `ExperimentState` (переиспользуем существующий kind из `core.contracts.scientist.ExperimentStateRef`)

Примечание:

- `core.trace.jsonl` (из `RunContext.finalize()`) остаётся базовым trace артефактом для node‑execution.

### 3.4 Public API surface (что экспортирует `polisyos.scientist.engine`)

Нормативно: `polisyos.scientist.engine.__init__` экспортирует только “готовые” абстракции:

- `Node`, `NodeSpec`, `NodeOutcome`, `NodeStatus`, `NodeEvent`, `NodeError`
- `ExperimentState`
- `WorkflowSpec`, `NodeInvocation`
- `NodeRegistry` (+ минимальный discovery helper)
- `WorkflowExecutor` (последовательный executor v0)
- ошибки `EngineError`‑семейства

Всё остальное (внутренние утилиты, детали telemetry, staging структуры) считается internal.

### 3.5 Документация

- Этот документ (E1.6) является source of truth для ABI engine.
- (Опционально) `policy-engine/src/polisyos/scientist/engine/README.md` — короткий how‑to + пример.

---

## 4) Node protocol (строгий минимум, который не сломает миграцию)

### 4.0 Ошибки (engine error taxonomy)

В `polisyos.scientist.engine.errors` завести минимальную иерархию ошибок:

- `EngineError(Exception)` — базовая
- `WorkflowSpecError(EngineError)` — ошибки валидации/построения DAG
  - `UnknownNodeError` (node_id не найден в registry)
  - `DuplicateAliasError`
  - `MissingDependencyError`
  - `CycleDetectedError`
- `NodeExecutionError(EngineError)` — узел упал (исключение/невалидный outcome)

Нормативно: executor преобразует “сырой exception” узла в `NodeOutcome(status="fail", error=...)` + trace и/или бросает `NodeExecutionError` (см. §8.1/§8.3).

### 4.1 NodeId и версия: используем ComponentId (Core components)

**Нормативно:** `NodeId = polisyos.core.components.ComponentId`.

#### Важная оговорка про формат (существующий ABI E1.4)

`ComponentId` в репозитории валидируется как `namespace.name@semver`, где `namespace` и `name` не содержат точек.  
Поэтому пример вида `scientist.node.plan@1.0.0` **невалиден** для текущей реализации `ComponentId`.

**Нормативная конвенция именования узлов на E1.6:**

- `namespace = "scientist"`
- `name` кодирует категорию через `_`:
  - `scientist.node_noop@1.0.0`
  - `scientist.node_set_state@1.0.0`
  - `scientist.node_emit_artifact@1.0.0`

(Если позже будет принято расширить грамматику ComponentId, эта конвенция останется совместимой — переименование решается через registry aliasing в E3.)

### 4.2 NodeSpec (metadata)

**Цель:** единый “паспорт” узла (для registry/discovery/UI/валидаций), без привязки к реализации.

Нормативно:

- `NodeSpec.metadata` базируется на `polisyos.core.components.ComponentMetadata`
- `capabilities` MUST включать `Capability.SCIENTIST_NODE`
- дополнительные hints допускаются, но не обязательны

Рекомендуемая модель:

```python
from pydantic import BaseModel, ConfigDict, Field
from polisyos.core.components import ComponentMetadata

class NodeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: ComponentMetadata
    # Optional: только hints (не hard contract)
    state_reads: list[str] = Field(default_factory=list)
    state_writes: list[str] = Field(default_factory=list)
    produces: list[str] = Field(default_factory=list, description="Logical artifact keys")
```

### 4.3 Node интерфейс (минимальный)

Нормативная сигнатура:

- `spec` (metadata: id/version/capabilities)
- `execute(ctx, state) -> NodeOutcome`

```python
from typing import Protocol, runtime_checkable
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.protocol import NodeOutcome, NodeSpec

@runtime_checkable
class Node(Protocol):
    @property
    def spec(self) -> NodeSpec: ...

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome: ...
```

**Инварианты:**

- Node не делает side‑effects “в обход” `ExecutionContext` (например, не пишет в произвольные файлы).  
  Пишем артефакты в CAS через `ctx.store` и фиксируем их через state/index + trace.
- Node не импортируется из `polisyos.core.*` (только Scientist вверх).

### 4.4 NodeOutcome (обязательные поля)

Нормативные поля:

- `status: ok|skip|fail`
- `state: ExperimentState` (обновлённый)
- `artifacts: list[ArtifactRef]` (produced)
- `events: list[NodeEvent]` (структурированные события)
- `error: NodeError | None` (envelope)

```python
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.engine.state import ExperimentState

NodeStatus = Literal["ok", "skip", "fail"]

class NodeError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict, description="Must be canonical-json friendly (no float).")

class NodeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: Literal["debug", "info", "warn", "error"] = "info"
    code: str | None = None
    message: str
    attrs: dict[str, str | int | bool] = Field(default_factory=dict)

class NodeOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: NodeStatus
    state: ExperimentState
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    events: list[NodeEvent] = Field(default_factory=list)
    error: NodeError | None = None
```

**Нормативные правила:**

- `status="fail"` ⇒ `error` MUST be non‑null.
- `status="ok"|"skip"` ⇒ `error` SHOULD be null.
- `artifacts` — это “что produced” для trace/observability.  
  Индексация (ключ → ArtifactRef) осуществляется через `state.artifacts_index`/`state.reports_index`.

---

## 5) ExperimentState (минимально полезный контракт)

### 5.1 Назначение

`ExperimentState` — состояние исполнения workflow как артефактно‑ориентированный контейнер:

- фиксирует **входы** (refs) на Trinity/DataSnapshot/RegistryBundle/…,
- ведёт **индекс результатов** (артефакты/отчёты) по логическим ключам,
- держит **params/budgets** как декларативные значения.

### 5.2 Минимальная структура

Нормативно (v0, “достаточно для engine”):

- `run_id: str`
- `inputs: dict[str, ArtifactRef]`
- `artifacts_index: dict[str, ArtifactRef]`
- `reports_index: dict[str, ArtifactRef]`
- `params: dict[str, str|int|bool|Decimal]`
- `budgets: dict[str, Decimal]` (или `params["budgets"]`, но лучше отдельным полем)

### 5.3 Reserved keys в `state.inputs` (конвенция E1.6+)

Чтобы Nodes могли “договариваться” о стандартных входах без жёсткой типизации на уровне engine, вводим зарезервированные ключи `ExperimentState.inputs`:

- `trinity_bundle_ref` — `ArtifactRef.kind in {"ir.trinity_bundle"}`
- `data_snapshot_ref` — `ArtifactRef.kind == "fabric.data_snapshot"`
- `registry_bundle_ref` — `ArtifactRef.kind == "core.registry_bundle"`
- (опционально) `knowledge_bundle_ref` — `ArtifactRef.kind == "scholar.knowledge_bundle"`
- (опционально) `norm_pack_ref` — `ArtifactRef.kind == "ir.norm_pack"` (или port из Lex, если появится)

Нормативно на E1.6:

- engine **не валидирует** содержимое этих артефактов (это ответственность Node),
- engine может валидировать “наличие ключа” через `WorkflowSpec.required_binds`.

Рекомендуемая модель:

```python
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from polisyos.core.artifacts.manifest import ArtifactRef

JsonScalar = str | int | bool | Decimal

class ExperimentState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")
    run_id: str

    inputs: dict[str, ArtifactRef] = Field(default_factory=dict)
    artifacts_index: dict[str, ArtifactRef] = Field(default_factory=dict)
    reports_index: dict[str, ArtifactRef] = Field(default_factory=dict)

    params: dict[str, JsonScalar] = Field(default_factory=dict)
    budgets: dict[str, Decimal] = Field(default_factory=dict)
```

### 5.4 Канонизация и “без float”

По умолчанию `FileSystemCAS.put_json()` использует `CanonSpec(forbid_floats=True)`.  
Нормативно для engine:

- `ExperimentState`, `WorkflowSpec`, `WorkflowReport` должны сериализоваться без float,
- для бюджетов/лимитов использовать `Decimal` или `int` (не `float`).

---

## 6) ExecutionContext (инфраструктура + порты/клиенты)

### 6.1 Назначение

`ExecutionContext` — всё, что нужно Node для исполнения, но **не является state**:

- CAS store,
- RunContext/trace,
- logger/tracer,
- порты (fabric/foundry/scholar/lex) как `Protocol`, чтобы engine не импортировал реализации.

### 6.2 Минимальная структура

```python
from dataclasses import dataclass
import logging
from typing import Protocol, runtime_checkable

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.run.context import RunContext
from polisyos.core.contracts.foundry import CompileRequest, CompileResult, ExecuteRequest, ExecuteResult
from polisyos.core.contracts.fabric import DataViewRequestRef, DataSnapshotRef
from polisyos.core.contracts.scholar import ResearchIntent, KnowledgeBundleRef
from polisyos.core.contracts.lex import LegalContext, LegalReportRef, ChangeProposalRef

@runtime_checkable
class FoundryPort(Protocol):
    def compile(self, store: FileSystemCAS, request: CompileRequest) -> CompileResult: ...
    def execute(self, store: FileSystemCAS, request: ExecuteRequest) -> ExecuteResult: ...

@runtime_checkable
class FabricPort(Protocol):
    def snapshot(self, store: FileSystemCAS, request_ref: DataViewRequestRef) -> DataSnapshotRef: ...

@runtime_checkable
class ScholarPort(Protocol):
    def enrich(self, store: FileSystemCAS, intent: ResearchIntent) -> KnowledgeBundleRef: ...

@runtime_checkable
class LexPort(Protocol):
    def evaluate(self, store: FileSystemCAS, context: LegalContext) -> tuple[LegalReportRef, ChangeProposalRef | None]: ...

@dataclass(frozen=True)
class ExecutionContext:
    store: FileSystemCAS
    run: RunContext
    logger: logging.Logger
    # Optional: OpenTelemetry tracer (если включён observability слой)
    tracer: "Tracer | None" = None

    fabric: FabricPort | None = None
    foundry: FoundryPort | None = None
    scholar: ScholarPort | None = None
    lex: LexPort | None = None
```

**Нормативно:** engine не создаёт реализации портов. Он получает готовые реализации через `ExecutionContext`.

### 6.3 RunContext lifecycle (как engine пишет trace)

`RunContext` в текущем Core API создаётся через:

```python
from polisyos.core.run.context import RunContext

run = RunContext.start(
    store=store,
    registry_bundle=registry_bundle_ref,  # ArtifactRef(kind="core.registry_bundle")
    run_id=state.run_id,
)
```

Нормативно для E1.6:

- `registry_bundle_ref` берём из `state.inputs["registry_bundle_ref"]` (см. §5.3),
- если ключ отсутствует — для тестов/локальных запусков допустимо собрать default bundle через `polisyos.core.registry.build_default_registry_bundle(store)`.

---

## 7) WorkflowSpec (DAG) — контракт исполнения

### 7.1 Требования

WorkflowSpec MUST:

- быть сериализуемым (Pydantic v2) и пригодным для хранения как CAS artifact,
- описывать DAG узлов (без циклов),
- позволять параметризовать узлы (params),
- фиксировать error policy (fail_fast/continue),
- явно декларировать входные binds (минимальная проверка state перед стартом).

### 7.2 Модель WorkflowSpec (v0)

Нормативная модель:

```python
from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from polisyos.core.components import ComponentId

ErrorPolicy = Literal["fail_fast", "continue"]

class NodeInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    node_id: ComponentId
    params: dict[str, str | int | bool | Decimal] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list, description="List of node aliases")

class WorkflowSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")
    workflow_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")

    nodes: list[NodeInvocation] = Field(default_factory=list)

    # Binds: какие ключи/пути должны быть заданы в state до старта
    required_binds: list[str] = Field(default_factory=list)

    error_policy: ErrorPolicy = "fail_fast"
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_aliases(self) -> "WorkflowSpec":
        aliases = [n.alias for n in self.nodes]
        if len(set(aliases)) != len(aliases):
            raise ValueError("NodeInvocation.alias must be unique within workflow")
        return self
```

### 7.3 Серилизация (контракт)

WorkflowSpec должен roundtrip’иться:

- `WorkflowSpec.model_dump_json()` → `WorkflowSpec.model_validate_json(...)`
- без потерь и без floats.

WorkflowSpec хранится в CAS как:

- kind: `scientist.workflow_spec`
- schema: `SchemaInfo(name="polisyos.scientist.engine.WorkflowSpec", version="1.0")`

---

## 8) Engine executor v0 (последовательный, но “правильный”)

### 8.1 Задачи executor

Executor v0 обязан:

1) Построить DAG и валидировать его:
   - отсутствие циклов,
   - `depends_on` ссылаются на существующие `alias`,
   - все `node_id` резолвятся через registry.

2) Исполнять узлы в топологическом порядке (последовательно):
   - создать span/trace вокруг каждого узла,
   - вызвать `node.execute(ctx, state)`,
   - обновить state,
   - записать результат в run trace (через `RunContext.emit`).

3) Обработать `skip` и `fail`:
   - `skip` уважать (узел сам решает resume),
   - `fail_fast` — остановка при первом fail,
   - `continue` — не исполнять downstream узлы, зависящие от упавших (mark skipped_due_to_upstream).

Дополнительно (нормативно):

- Любое необработанное исключение из `node.execute(...)`:
  - перехватывается executor’ом,
  - конвертируется в `NodeOutcome(status="fail", error=NodeError(code="node.exception", ...))`,
  - фиксируется в trace/логах,
  - дальше применяется `error_policy`.

### 8.2 Валидация binds

`required_binds` — список путей, которые должны быть заданы в state до старта.

Нормативно (v0): проверка “значение существует и не None”.

Рекомендуемая реализация:

- простая поддержка dot‑paths (`inputs.trinity_bundle_ref`) опциональна;
- в минимуме допускается только top-level keys (`inputs`, `run_id`, …), а сложные проверки — в Nodes.

### 8.3 Трассировка и артефакты исполнения

Нормативно на E1.6:

- на каждый NodeInvocation executor пишет минимум два события в `RunContext.trace`:
  - `NODE_STARTED`
  - `NODE_OK|NODE_SKIP|NODE_FAIL`
- trace сохраняется как CAS артефакт `core.trace.jsonl` на `RunContext.finalize()`.

Это удовлетворяет “node trace как артефакт” без введения дополнительных форматов.

Ограничение текущего `RunContext.emit()`:

- он не принимает `warnings/errors/events` как структуры, только `metrics` и `refs`.

Поэтому на E1.6:

- `NodeOutcome.events` обязательно попадает в `ctx.logger` (structured log),
- при наличии `ctx.tracer` executor может добавлять события как `span.add_event(...)`,
- `NodeOutcome.error` фиксируется:
  - минимум через `ctx.logger.exception(...)`,
  - и/или через `RunContext.finalize(status="fail", errors=[...])` (run_manifest.errors).

### 8.4 Рекомендуемая форма node trace events (семантика)

Использовать `RunContext.emit(phase, event, inputs, outputs, metrics)`:

- `phase = f"scientist.node.{alias}"` (или `phase="scientist.node"` + поле в event name)
- `event`:
  - `NODE_STARTED`
  - `NODE_OK`
  - `NODE_SKIP`
  - `NODE_FAIL`
- `metrics`:
  - `duration_ms`
  - `status_ok` (0/1)
- `refs.inputs/refs.outputs`:
  - по возможности включать produced `ArtifactRef` из `NodeOutcome.artifacts`.

### 8.4.1 Telemetry conventions (OpenTelemetry spans)

Если `ExecutionContext.tracer` задан, executor создаёт span на каждый узел.

Нормативно:

- span name: `scientist.node` (или `scientist.node.<alias>`, но лучше фиксированное имя + атрибуты)
- атрибуты (минимум):
  - `polisyos.run_id` = `state.run_id`
  - `polisyos.workflow_id` = `workflow.workflow_id`
  - `polisyos.node.alias` = `inv.alias`
  - `polisyos.node.id` = `str(inv.node_id)`
  - `polisyos.node.status` = `outcome.status`
  - `polisyos.node.duration_ms` = `<int>`

Поведение:

- `NodeOutcome.events` добавляются как span events (например `span.add_event(...)`) и/или логируются через `ctx.logger`.

### 8.5 Минимальный WorkflowReport (рекомендуемо, но допустимо как in-memory)

Чтобы “корректно отразить skip/fail” и иметь стабильный артефакт отчёта, рекомендуется добавить `WorkflowReport`:

- содержит список `NodeRunRecord` (alias, node_id, status, duration_ms, error?, produced artifacts keys/refs),
- сохраняется в CAS:
  - kind: `scientist.workflow_report`
  - schema: `polisyos.scientist.engine.WorkflowReport@1.0`
- ref отчёта можно положить в `state.reports_index["workflow_report"]`.

Если нужно минимизировать объём работ, допускается:

- вернуть report из executor как Python object без записи в CAS,
- но тест “observability smoke” тогда обязан проверять хотя бы `core.trace.jsonl`.

### 8.6 Persist workflow inputs/outputs (рекомендуемый “repro path”)

Чтобы workflow был воспроизводимым “по артефактам”, executor должен:

1) persist `WorkflowSpec` в CAS (kind `scientist.workflow_spec`) и добавить как input в `RunContext`:
   - `run.add_input(workflow_spec_ref)`
2) (опционально) persist initial `ExperimentState` как `scientist.experiment_state` и добавить как input.
3) после исполнения:
   - persist final `ExperimentState` (kind `scientist.experiment_state`) и добавить как output,
   - persist `WorkflowReport` (kind `scientist.workflow_report`) и добавить как output,
   - `run.finalize(status="ok"|"fail")`.

Нормативно на E1.6 достаточно пункта (1) + trace; пункты (2–3) настоятельно рекомендованы.

---

## 9) Node registry/discovery v0

### 9.1 Registry API (минимум)

`NodeRegistry` — in‑process registry:

- `register(node)` / `register_provider(provider)`
- `get(node_id)`
- `list(filter)` (capabilities/domain/tag — минимум)

**Conflict policy:** при дубле `node_id` — **fail** (на E1.6 так безопаснее).

Уточнение про версии:

- workflow spec pin’ит `node_id` полностью (включая semver),
- на E1.6 registry **не** делает semver‑резолв автоматически,
- если обнаружены разные версии одного и того же компонента (`namespace.name@...`) — registry должен падать (чтобы workflow был воспроизводим).

Нормативная структура registry (v0):

- primary key: полный `ComponentId` (`str(ComponentId)`)
- secondary index: `component_key = f\"{namespace}.{name}\"` (без версии) → должен быть уникальным

Это даёт:

- воспроизводимость (workflow фиксирует точную версию),
- раннее обнаружение конфликтов (две версии одной ноды в одном процессе).

Рекомендуемый API (точные сигнатуры):

```python
from polisyos.core.components import ComponentId, Capability
from polisyos.scientist.engine.protocol import Node

class NodeRegistry:
    def register(self, node: Node) -> None: ...
    def get(self, node_id: ComponentId | str) -> Node: ...  # raises UnknownNodeError
    def list(self, *, capability: Capability | None = None, tag: str | None = None) -> list[NodeSpec]: ...
```

### 9.2 Интеграция с Core components (если возможно)

В репозитории уже есть:

- `polisyos.core.components.ComponentRegistry`
- `polisyos.core.components.discover_entry_points()` (entry point group `polisyos.components`)

Нормативный путь discovery на E1.6:

1) Вызываем `discover_entry_points()`.
2) Отбираем объекты с `capabilities & Capability.SCIENTIST_NODE`.
3) Если это `ComponentProvider` — создаём node через `create()` и регистрируем.
4) Если это только `ComponentMetadata` — регистрируем metadata (опционально), но без instance (или отклоняем).

**Fallback:** если discovery пока не используется/не настроен, registry грузит builtins напрямую.

---

## 10) Минимальные built‑in узлы (для проверки engine)

На E1.6 достаточно 3 узлов без доменной логики:

### 10.1 `noop`

- NodeId: `scientist.node_noop@1.0.0`
- Поведение: ничего не делает, возвращает `status="ok"`, state без изменений (кроме опциональных events).

### 10.2 `set_state`

- NodeId: `scientist.node_set_state@1.0.0`
- Params:
  - `key: str` (например `"params.foo"`, или просто `"foo"` в `state.params`)
  - `value: str|int|bool` (без float)
- Поведение: записывает значение в state (нормативно: `state.params[key]=value`).

### 10.3 `emit_artifact`

- NodeId: `scientist.node_emit_artifact@1.0.0`
- Params:
  - `key: str` — ключ в `state.artifacts_index`
  - `payload: dict` — небольшая JSON‑структура без float (для теста)
- Поведение:
  1) пишет `payload` в CAS через `ctx.store.put_json(...)` (kind например `scientist.builtin.dummy`),
  2) добавляет `ArtifactRef` в `state.artifacts_index[key]`,
  3) возвращает `NodeOutcome.artifacts=[ref]`.

---

## 11) Тестирование и валидация (обязательная часть фазы)

### 11.1 Unit tests: executor

1) **Executor исполняет DAG из 3 узлов**:
   - workflow: set_state → emit_artifact → noop
   - проверки:
     - порядок выполнения соответствует зависимостям,
     - state.params изменён,
     - state.artifacts_index содержит ref,
     - trace содержит события по каждому узлу (или report отражает статусы).

2) **Unknown node**:
   - workflow с `node_id`, которого нет в registry → ошибка на этапе валидации DAG.

3) **Cycle**:
   - цикл через depends_on → ошибка “cycle detected”.

4) **Skip propagation (continue policy)**:
   - первый узел fail,
   - downstream узел зависит от него,
   - при `error_policy="continue"` downstream помечается как skipped_due_to_upstream (в report/trace).

Рекомендуемые test fixtures:

- `store = FileSystemCAS(tmp_path)` (CAS в temp dir)
- `registry_bundle = build_default_registry_bundle(store).bundle_ref` (или fixture)
- `run = RunContext.start(store, registry_bundle=registry_bundle, run_id="R_test")`
- `ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test"))`
- `registry = NodeRegistry(); registry.register(Builtins...)`

### 11.2 Contract tests: WorkflowSpec serde

- `WorkflowSpec.model_dump_json()` roundtrip без потерь.
- canonical JSON (через `polisyos.core.canon.to_canonical_bytes`) не падает (без float).

### 11.3 Observability smoke

Минимум:

- на каждый узел есть span/trace запись (OpenTelemetry span или `RunContext.trace` record).

Предпочтительно:

- `RunContext.finalize()` создаёт `core.trace.jsonl` артефакт и он содержит `NODE_*` события по всем узлам.

---

## 12) Definition of Done (формально проверяемые критерии)

1) Есть `polisyos.scientist.engine`:
   - Node protocol + WorkflowSpec + executor + registry + minimal telemetry helpers.
2) Есть builtins (noop/set_state/emit_artifact) и тест, который реально прогоняет DAG.
3) Engine не содержит доменной логики:
   - никакого “compile/simulate/legal/data fetch” внутри engine пакета.
4) Есть contract test serde для WorkflowSpec.
5) Наблюдаемость:
   - trace/spans фиксируются на каждый узел (и это проверяется smoke test).

---

## 13) Рекомендуемая последовательность имплементации (чтобы не утонуть)

1) **Модели и ошибки (контракты)**:
   - `engine/errors.py`, `engine/state.py`, `engine/protocol.py`, `engine/workflow_spec.py`
   - добавить contract test для serde WorkflowSpec.
2) **Registry v0**:
   - in‑process registry + регистрация builtins,
   - (опц.) discovery адаптер поверх `polisyos.core.components.discovery`.
3) **Executor v0**:
   - DAG validation + topo sort,
   - исполнение + trace events в `RunContext`,
   - базовая обработка исключений и `error_policy`.
4) **Builtins**:
   - noop/set_state/emit_artifact,
   - unit tests: DAG smoke + cycle/unknown node.
5) **Telemetry helpers**:
   - вынести span/trace атрибуты и names в `engine/telemetry.py`,
   - добавить smoke test на trace/spans.

## Appendix A — Рекомендуемая реализация DAG в executor (псевдокод)

```python
def topo_sort(workflow: WorkflowSpec) -> list[str]:
    # Kahn algorithm over aliases
    ...

def execute_workflow(ctx, registry, workflow, state):
    validate_binds(workflow.required_binds, state)
    order = topo_sort(workflow)

    results = {}
    failed = set()

    for alias in order:
        inv = invocations[alias]

        if any(dep in failed for dep in inv.depends_on):
            results[alias] = {"status": "skip", "reason": "upstream_failed"}
            continue

        node = registry.get(inv.node_id)  # raises if missing
        ctx.run.emit(f"scientist.node.{alias}", "NODE_STARTED")

        started = now()
        outcome = node.execute(ctx, state)
        duration_ms = ms_since(started)

        state = outcome.state
        # record artifacts/events

        if outcome.status == "fail":
            failed.add(alias)
            ctx.run.emit(f"scientist.node.{alias}", "NODE_FAIL", metrics={"duration_ms": duration_ms})
            if workflow.error_policy == "fail_fast":
                break
        elif outcome.status == "skip":
            ctx.run.emit(f"scientist.node.{alias}", "NODE_SKIP", metrics={"duration_ms": duration_ms})
        else:
            ctx.run.emit(f"scientist.node.{alias}", "NODE_OK", metrics={"duration_ms": duration_ms})

    return state, results
```

---

## Appendix B — Пример WorkflowSpec (JSON)

```json
{
  "schema_version": "1.0",
  "workflow_id": "engine_smoke",
  "required_binds": ["run_id"],
  "error_policy": "fail_fast",
  "nodes": [
    {
      "alias": "set",
      "node_id": "scientist.node_set_state@1.0.0",
      "params": {"key": "foo", "value": "bar"},
      "depends_on": []
    },
    {
      "alias": "emit",
      "node_id": "scientist.node_emit_artifact@1.0.0",
      "params": {"key": "dummy"},
      "depends_on": ["set"]
    },
    {
      "alias": "noop",
      "node_id": "scientist.node_noop@1.0.0",
      "params": {},
      "depends_on": ["emit"]
    }
  ]
}
```

## D1-L4 Validation Links

| Link type | Current anchor |
|-----------|----------------|
| Source plan phase | D1-L4 Phase 2 pass/analysis contracts and Phase 5 governance-frontier handoff |
| Contract tests | `tests/contract/test_scientist_workflow_spec_contract.py`, `tests/scientist/nodes/builtins/compile/test_link_trinity.py`, `tests/scientist/governance/test_validation_pipeline.py`, `tests/scientist/governance/test_pass_registry.py` |
| Schema snapshots | `schemas/snapshots/ir/gate_request.schema.json`, `schemas/snapshots/ir/gate_decision.schema.json`, `schemas/snapshots/ir/trinity_bundle.schema.json` |
| Generated reference | [IR Schema Catalog](../reference/ir/schema-catalog.md), [JSON Schema Catalog](../reference/schemas.md) |
