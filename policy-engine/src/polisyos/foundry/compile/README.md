# Compile Module (Компилятор политик)

Модуль `compile` предоставляет высокоуровневый компилятор политик из Trinity IR в исполняемые артефакты Foundry. Модуль преобразует декларативные политики в оптимизированные графы выполнения с проверкой конфликтов и оценкой стоимости.

## Архитектура

### Core Components (Основные компоненты)

- **`api.py`** - Высокоуровневый API компилятора
- **`trinity_compiler.py`** - Основной компилятор Trinity политик
- **`_graph.py`** - Построение ProgramGraph и топологической сортировки

## Основные концепции

### CompileRequest (Запрос на компиляцию)

```python
from polisyos.core.contracts.foundry import CompileRequest, CompileConfig

request = CompileRequest(
    policy_ref=ArtifactRef(...),           # Ссылка на Trinity политику
    registry_bundle_ref=ArtifactRef(...),  # Регистры механизмов
    compile_config=CompileConfig(
        determinism_tier="best_effort_gpu", # Уровень детерминизма
        random_seed=42,                     # Seed для RNG
        jit=True,                           # JIT компиляция
        nan_guard_enabled=True,             # Проверка NaN/Inf
    ),
    validation_flags=ValidationFlags(
        strict_link=True,                   # Строгая линковка
        strict_conflict_check=True,         # Проверка конфликтов
        allow_extra_params=False,           # Дополнительные параметры
    ),
)
```

### CompileResult (Результат компиляции)

```python
from polisyos.core.contracts.foundry import CompileResult

result = CompileResult(
    ok=True,                               # Статус компиляции
    exec_plan_ref=ExecPlanRef(...),         # План исполнения
    compile_report_ref=ArtifactRef(...),    # Отчёт компиляции
    derived_refs=[                          # Производные артефакты
        DerivedArtifact(role="program_graph", ref=ProgramGraphRef(...)),
        DerivedArtifact(role="slot_layout", ref=ArtifactRef(...)),
        DerivedArtifact(role="treasury_plan", ref=ArtifactRef(...)),
    ],
    notes=[],                              # Дополнительные замечания
)
```

## Процесс компиляции

### 1. Link Phase (Фаза линковки)

```python
from polisyos.ir.linker import link_trinity

linked_bundle, link_report = link_trinity(
    bundle=bundle,
    registries=registries,
    allow_extra_params=request.validation_flags.allow_extra_params,
    strict=request.validation_flags.strict_link,
)
```

- **Валидация**: Проверка совместимости параметров и типов
- **Разрешение зависимостей**: Связывание механизмов с их реализациями
- **Генерация отчёта**: LinkReport с диагностикой ошибок

### 2. Graph Building (Построение графа)

```python
from polisyos.foundry.compile._graph import build_program_graph

program_graph, params_refs = build_program_graph(
    store=store,
    ir_ref=policy_ref,
    interventions=bundle.policy_spec.interventions,
    resolve_slots=_resolve_slots,
    constraint_ids=constraint_ids,
)
```

#### ProgramGraph (Граф программы)

```python
@chex.dataclass(frozen=True)
class ProgramGraph:
    ir_ref: ArtifactRef                    # Ссылка на исходный IR
    nodes: list[ProgramNode]               # Узлы графа
    edges: list[ProgramEdge]               # Зависимости между узлами
    entrypoints: list[str]                 # Точки входа
    notes: list[str]                       # Дополнительные замечания
```

#### ProgramNode (Узел программы)

```python
@chex.dataclass(frozen=True)
class ProgramNode:
    node_id: str                          # Уникальный ID узла
    node_kind: str                        # Тип узла ("op", "mechanism")
    mechanism_type: str | None            # Тип механизма
    params_ref: ArtifactRef | None        # Параметры механизма
    op: ProgramOp | None                  # Операция узла
    inputs: list[str]                     # Читаемые слоты
    outputs: list[str]                    # Записываемые слоты
```

#### ProgramEdge (Ребро графа)

```python
@chex.dataclass(frozen=True)
class ProgramEdge:
    src: str                              # Исходный узел
    dst: str                              # Целевой узел
    relation: str                         # Тип отношения ("depends_on")
```

### 3. Conflict Detection (Обнаружение конфликтов)

```python
from polisyos.foundry.conflict_checker import CompileTimeConflictChecker

conflict_checker = CompileTimeConflictChecker(
    slot_registry=slot_registry,
    merge_registry=merge_registry,
    strict_mode=request.validation_flags.strict_conflict_check,
)
conflict_report = conflict_checker.check(program_graph)
```

- **Проверка конфликтов записи**: Несколько механизмов пишут в один слот
- **Валидация merge rules**: Проверка допустимости правил слияния
- **Генерация отчёта**: CompileConflictReport с диагностикой

### 4. Cost Estimation (Оценка стоимости)

```python
from polisyos.foundry.cost_model import CostModel, CostBudget

cost_model = CostModel()
estimate = cost_model.estimate(
    program_graph=program_graph,
    n_agents=1000,                         # Размер симуляции
    time_steps=100,                         # Длительность
    budget=CostBudget(                      # Бюджет ограничений
        max_total_ms=60000,
        max_memory_mb=8192,
    ),
)
```

### 5. Execution Plan (План исполнения)

```python
from polisyos.core.contracts.foundry import ExecPlan
from polisyos.foundry.compile._graph import build_exec_order

order = build_exec_order(program_graph)
exec_plan = ExecPlan(
    program_ref=program_graph_ref,
    order=order,                           # Топологический порядок
    determinism_tier=request.compile_config.determinism_tier,
    random_seed=request.compile_config.random_seed,
    nan_guard_enabled=request.compile_config.nan_guard_enabled,
    mode=request.compile_config.mode,
    jit=request.compile_config.jit,
    max_steps=request.compile_config.max_steps,
)
```

### 6. Layout и Treasury Plans (Планы размещения)

```python
from polisyos.foundry.layout import build_slot_layout
from polisyos.foundry.treasury import build_treasury_plan

slot_layout = build_slot_layout(registry_content.slot_registry)
treasury_plan = build_treasury_plan(program_graph)
```

## Основные функции

### compile (Основная функция компиляции)

```python
from polisyos.foundry.compile import compile
from polisyos.core.artifacts.store import FileSystemCAS

store = FileSystemCAS("/path/to/artifacts")
result = compile(store, request)

if result.ok:
    print(f"Compiled successfully: {result.exec_plan_ref}")
else:
    print(f"Compilation failed: {result.notes}")
```

### build_program_graph (Построение графа программы)

```python
from polisyos.foundry.compile._graph import build_program_graph

def resolve_slots(intervention):
    binding = bindings.get(intervention.intervention_id)
    if binding is None:
        return [], []
    return list(binding.reads_slots), list(binding.writes_slots)

graph, params_refs = build_program_graph(
    store=store,
    ir_ref=policy_ref,
    interventions=interventions,
    resolve_slots=resolve_slots,
    constraint_ids=["constraint_1", "constraint_2"],
)
```

### build_exec_order (Построение порядка исполнения)

```python
from polisyos.foundry.compile._graph import build_exec_order

execution_order = build_exec_order(program_graph)
print(f"Execution order: {execution_order}")
```

## Архитектурные особенности

### Топологическая сортировка

Компилятор использует `graphlib.TopologicalSorter` для построения порядка исполнения без циклов:

```python
from graphlib import TopologicalSorter

sorter = TopologicalSorter()
for node_id in node_ids:
    sorter.add(node_id)
for edge in edges:
    sorter.add(edge.dst, edge.src)

execution_order = list(sorter.static_order())
```

### Slot-based зависимости

Автоматическое обнаружение зависимостей через анализ читаемых/записываемых слотов:

```python
def _slot_dependency_edges(nodes):
    for writer in mechanism_nodes:
        for reader in mechanism_nodes:
            if writer_slots.intersection(reader_slots):
                edges.append(ProgramEdge(writer.node_id, reader.node_id, "depends_on"))
```

### Artifact-based хранение

Все артефакты компиляции сохраняются в artifact store с полными метаданными и зависимостями:

```python
program_ref = store.put_json(
    program_graph,
    PutOptions(
        kind="foundry.program_graph",
        inputs=program_inputs,
        schema=SchemaInfo(name="polisyos.core.ProgramGraph", version="0.1.0"),
    ),
)
```

## Связь с другими модулями

- **`ir.linker`**: Линковка Trinity политик
- **`foundry.conflict_checker`**: Проверка конфликтов компиляции
- **`foundry.cost_model`**: Оценка стоимости выполнения
- **`foundry.layout`**: Размещение слотов состояния
- **`foundry.treasury`**: План детерминированного RNG
- **`core.artifacts`**: Хранение скомпилированных артефактов
- **`scientist.compiler`**: Высокоуровневый API компиляции

---

Модуль `compile` - центральный компонент Foundry, преобразующий декларативные политики в оптимизированные исполняемые графы с полной валидацией и трассировкой зависимостей.