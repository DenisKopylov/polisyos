# Engine Module (Исполнительный движок)

Модуль `engine` представляет собой core execution engine Foundry - высокопроизводительный исполнитель скомпилированных ProgramGraph'ов с поддержкой patch-based state management, constraint validation и artifact tracking. Engine является центральным компонентом runtime исполнения политик.

## Архитектура

### Core Components (Основные компоненты)

- **`executor.py`** - Основной исполнитель ProgramGraph с полным runtime

## Основные концепции

### ProgramGraph Execution (Исполнение графа программы)

```python
from polisyos.foundry.executor import execute_program_graph

exec_artifacts = execute_program_graph(
    store=store,
    program_ref=program_graph_ref,         # Ссылка на ProgramGraph
    exec_plan_ref=exec_plan_ref,           # План исполнения
    base_state=initial_state,              # Начальное состояние
    mechanism_registry=mechanism_registry, # Реестр механизмов
    slot_registry=slot_registry,           # Реестр слотов
    merge_registry=merge_registry,         # Правила слияния
    selector_field_registry=selector_field_registry,  # Селекторы полей
    constraint_registry=constraint_registry,  # Ограничения
    step=0,                                # Начальный шаг
    seed=42,                               # Seed для RNG
    base_ref=state_snapshot_ref,           # Базовый snapshot
    capture_env=True,                      # Захватывать environment
)
```

#### ExecArtifacts (Результаты исполнения)

```python
@dataclass
class ExecArtifacts:
    state_delta_ref: ArtifactRef           # Изменения состояния
    metrics_ref: ArtifactRef               # Метрики исполнения
    constraint_report_ref: ArtifactRef | None  # Отчёт о constraints
    environment_ref: ArtifactRef | None    # Environment manifest
    environment_fingerprint: EnvironmentFingerprint  # Fingerprint окружения
```

### State Management (Управление состоянием)

#### State Delta Application (Применение изменений)

```python
from polisyos.foundry.executor import apply_state_delta

new_state = apply_state_delta(
    store=store,
    base_state=initial_state,
    state_delta_ref=exec_artifacts.state_delta_ref,
    slot_registry=slot_registry,
    merge_registry=merge_registry,
)
```

#### State Snapshot Management (Управление snapshot'ами)

```python
from polisyos.foundry.executor import (
    put_state_snapshot,
    load_state_snapshot,
    apply_state_delta_and_snapshot,
)

# Сохранение состояния
snapshot_ref = put_state_snapshot(
    store=store,
    state=current_state,
    step=step,
    base_ref=previous_snapshot_ref,
)

# Загрузка состояния
loaded_state = load_state_snapshot(store, snapshot_ref)

# Применение delta с snapshot
applied, snapshot = apply_state_delta_and_snapshot(
    store=store,
    base_state=base_state,
    state_delta_ref=state_delta_ref,
    slot_registry=slot_registry,
    merge_registry=merge_registry,
    step=step,
    base_ref=base_ref,
)
```

### Patch Operations (Операции патчей)

#### Patch Record Application (Применение записей патчей)

```python
from polisyos.foundry.executor import apply_patch_records

patched_state = apply_patch_records(
    store=store,
    base_state=initial_state,
    patch_records=patch_records,
    slot_registry=slot_registry,
    merge_registry=merge_registry,
)
```

#### Patch Map Application (Применение карты патчей)

```python
from polisyos.foundry.executor import apply_patch_map

patched_state = apply_patch_map(
    store=store,
    base_state=initial_state,
    patch_map=patch_map,  # dict[slot_id, list[PatchOp]]
    slot_registry=slot_registry,
    merge_registry=merge_registry,
)
```

### Constraint Validation (Валидация ограничений)

```python
from polisyos.foundry.executor import _check_constraints

constraint_report = _check_constraints(
    constraint_registry=constraint_registry,
    slot_registry=slot_registry,
    merged_ops=merged_patch_ops,
    state_before=state_before,
    state_after=state_after,
)
```

### Selector Evaluation (Оценка селекторов)

```python
from polisyos.foundry.executor import _evaluate_selector

selected_mask = _evaluate_selector(
    selector_expr=selector,
    state=current_state,
    selector_field_registry=selector_field_registry,
)
```

## Архитектурные особенности

### Patch-based State Updates

Engine использует patch-first архитектуру для всех изменений состояния:

```python
# Механизмы генерируют патчи вместо прямых изменений
def emit_patches(self, state, key, *, target_mask=None):
    # Вычисление изменений
    tax_amounts = state.agents.income * self.tax_rate

    # Генерация патчей
    patches = {
        "agents.income": [PatchOp(delta=-tax_amounts, mask=target_mask)],
        "government.balance": [PatchOp(delta=jnp.sum(tax_amounts))],
    }
    return patches, key
```

### Merge Engine Integration

Интеграция с MergeEngine для разрешения конфликтов:

```python
from polisyos.foundry.merge_engine import MergeEngine

merge_engine = MergeEngine(
    slot_registry=slot_registry,
    merge_registry=merge_registry,
)

merged_records = merge_engine.merge_patch_records(
    store=store,
    patch_records=patch_records,
)
```

### Artifact-based Persistence

Все промежуточные результаты сохраняются как артефакты:

```python
# Сохранение state delta
state_delta_ref = store.put_json(
    state_delta,
    PutOptions(
        kind="foundry.state_delta",
        inputs=[InputRef(artifact_id=base_ref.artifact_id, role="base_state")],
    ),
)

# Сохранение метрик
metrics_ref = store.put_json(
    metrics,
    PutOptions(kind="foundry.metrics", inputs=metrics_inputs),
)
```

### Environment Tracking

Автоматический захват и валидация окружения исполнения:

```python
from polisyos.core.artifacts.environment import capture_environment

if capture_env:
    environment_manifest = capture_environment()
    environment_ref = _persist_environment_manifest(store, environment_manifest)
```

### Performance Optimization

#### JIT Compilation
Все функции автоматически JIT-компилируются для максимальной производительности.

#### Vectorized Operations
Использование JAX для векторизованных операций над массивами агентов.

#### Lazy Loading
Артефакты загружаются только по необходимости.

## Основные функции

### execute_program_graph (Основная функция исполнения)

Главная функция для исполнения ProgramGraph:

```python
def execute_program_graph(
    store: FileSystemCAS,
    program_ref: ProgramGraphRef,
    exec_plan_ref: ExecPlanRef,
    base_state: Any,
    mechanism_registry: MechanismTypeRegistry,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    selector_field_registry: SelectorFieldRegistry,
    constraint_registry: ConstraintRegistry,
    step: int,
    seed: int,
    base_ref: StateSnapshotRef | None = None,
    capture_env: bool = False,
) -> ExecArtifacts:
```

### State Operations (Операции с состоянием)

```python
# Применение патчей к состоянию
patched_state = apply_patch_map(store, base_state, patch_map, slot_registry, merge_registry)

# Создание snapshot состояния
snapshot_ref = put_state_snapshot(store, state, step, base_ref)

# Применение delta с созданием snapshot
applied, snapshot = apply_state_delta_and_snapshot(store, base_state, state_delta_ref, slot_registry, merge_registry, step, base_ref)
```

### Constraint Checking (Проверка ограничений)

```python
constraint_report = _check_constraints(
    constraint_registry, slot_registry, merged_ops, state_before, state_after
)

if not constraint_report.ok:
    for violation in constraint_report.violations:
        print(f"Constraint violation: {violation}")
```

## Связь с другими модулями

- **`foundry.compile`** - Генерация ProgramGraph и ExecPlan
- **`foundry.runtime`** - Низкоуровневые runtime функции
- **`foundry.merge_engine`** - Разрешение конфликтов патчей
- **`foundry.patch_vm`** - Виртуальная машина патчей
- **`foundry.constraints_engine`** - Движок ограничений
- **`core.contracts.foundry`** - Контракты данных
- **`core.artifacts`** - Хранение артефактов

---

Модуль `engine` - сердце Foundry execution engine, обеспечивающий высокопроизводительное исполнение политик с полной traceability и artifact management.