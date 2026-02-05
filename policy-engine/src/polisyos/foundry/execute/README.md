# Execute Module (Исполнитель программ)

Модуль `execute` предоставляет высокоуровневый API для исполнения скомпилированных ProgramGraph'ов с поддержкой state management, constraint validation и artifact tracking. Модуль служит основным интерфейсом между скомпилированными политиками и runtime execution engine.

## Архитектура

### Core Components (Основные компоненты)

- **`api.py`** - Высокоуровневый API исполнения программ
- **`__init__.py`** - Экспорт основной функции execute

## Основные концепции

### ExecuteRequest (Запрос на исполнение)

```python
from polisyos.core.contracts.foundry import ExecuteRequest, ExecuteConfig

request = ExecuteRequest(
    exec_plan_ref=ExecPlanRef(...),        # Ссылка на план исполнения
    registry_bundle_ref=ArtifactRef(...),  # Регистры механизмов
    state_snapshot_ref=StateSnapshotRef(...),  # Начальное состояние (или)
    data_snapshot_ref=DataSnapshotRef(...),    # Альтернативный формат состояния
    exec_config=ExecuteConfig(
        seed=42,                          # Seed для RNG
        capture_env=True,                 # Захватывать environment fingerprint
    ),
)
```

### ExecuteResult (Результат исполнения)

```python
from polisyos.core.contracts.foundry import ExecuteResult

result = ExecuteResult(
    ok=True,                              # Статус исполнения
    simulation_result_ref=SimulationResultRef(...),  # Результат симуляции
    derived_refs=[                        # Производные артефакты
        DerivedArtifact(role="metrics", ref=ArtifactRef(...)),
        DerivedArtifact(role="state_delta", ref=ArtifactRef(...)),
        DerivedArtifact(role="constraint_report", ref=ArtifactRef(...)),
    ],
    notes=[],                            # Дополнительные замечания
)
```

### SimulationResult (Результат симуляции)

```python
from polisyos.core.contracts.foundry import SimulationResult

sim_result = SimulationResult(
    exec_plan_ref=ExecPlanRef(...),       # План исполнения
    metrics_ref=ArtifactRef(...),         # Метрики исполнения
    state_snapshot_ref=StateSnapshotRef(...),  # Финальное состояние
    environment_ref=ArtifactRef(...),     # Environment manifest
    environment_fingerprint=EnvironmentFingerprint(...),  # Fingerprint окружения
)
```

## Процесс исполнения

### 1. Разрешение состояния (State Resolution)

```python
def _resolve_state_snapshot(store, request):
    if request.state_snapshot_ref is not None:
        return request.state_snapshot_ref
    if request.data_snapshot_ref is None:
        raise ValueError("Either state_snapshot_ref or data_snapshot_ref must be set")

    # Конвертация DataSnapshot в StateSnapshot
    snapshot_payload = from_canonical_bytes(store.get_bytes(request.data_snapshot_ref.artifact_id))
    snapshot = DataSnapshot.model_validate(snapshot_payload)
    if snapshot.data_ref.kind != "foundry.state_snapshot":
        raise ValueError(f"Invalid data_ref.kind: {snapshot.data_ref.kind}")

    return StateSnapshotRef(artifact_id=snapshot.data_ref.artifact_id)
```

### 2. Загрузка состояния и регистров

```python
from polisyos.core.registry import load_registry_bundle_content
from polisyos.foundry.executor import load_state_snapshot

registry_content = load_registry_bundle_content(store, registry_bundle_ref)
base_state = load_state_snapshot(store, snapshot_ref=state_snapshot_ref)
```

### 3. Исполнение ProgramGraph

```python
from polisyos.foundry.executor import execute_program_graph

exec_artifacts = execute_program_graph(
    store=store,
    program_ref=exec_plan.program_ref,
    exec_plan_ref=request.exec_plan_ref,
    base_state=base_state,
    mechanism_registry=registry_content.mechanism_registry,
    slot_registry=registry_content.slot_registry,
    merge_registry=registry_content.merge_registry,
    selector_field_registry=registry_content.selector_field_registry,
    constraint_registry=registry_content.constraint_registry,
    step=int(getattr(base_state, "step", 0)),
    seed=request.exec_config.seed,
    base_ref=state_snapshot_ref,
    capture_env=request.exec_config.capture_env,
)
```

#### ExecArtifacts (Артефакты исполнения)

```python
@dataclass
class ExecArtifacts:
    state_delta_ref: ArtifactRef          # Изменения состояния
    metrics_ref: ArtifactRef              # Метрики исполнения
    constraint_report_ref: ArtifactRef | None  # Отчёт о constraints
    environment_ref: ArtifactRef | None   # Environment manifest
    environment_fingerprint: EnvironmentFingerprint  # Fingerprint окружения
```

### 4. Применение изменений состояния

```python
from polisyos.foundry.executor import apply_state_delta_and_snapshot

_, applied = apply_state_delta_and_snapshot(
    store=store,
    base_state=base_state,
    state_delta_ref=exec_artifacts.state_delta_ref,
    slot_registry=registry_content.slot_registry,
    merge_registry=registry_content.merge_registry,
    step=int(getattr(base_state, "step", 0)),
    base_ref=state_snapshot_ref,
)
```

### 5. Формирование результата

```python
sim_result = SimulationResult(
    exec_plan_ref=request.exec_plan_ref,
    metrics_ref=exec_artifacts.metrics_ref,
    state_snapshot_ref=StateSnapshotRef(artifact_id=applied.state_snapshot_ref.artifact_id),
    environment_ref=exec_artifacts.environment_ref,
    environment_fingerprint=exec_artifacts.environment_fingerprint,
)

sim_result_ref = store.put_json(
    sim_result,
    PutOptions(
        kind="foundry.simulation_result",
        inputs=sim_inputs,
        schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.0"),
    ),
)
```

## Основные функции

### execute (Основная функция исполнения)

```python
from polisyos.foundry.execute import execute
from polisyos.core.artifacts.store import FileSystemCAS

store = FileSystemCAS("/path/to/artifacts")
result = execute(store, request)

if result.ok:
    print(f"Execution successful: {result.simulation_result_ref}")
    # Доступ к результатам
    sim_result = store.get_json(result.simulation_result_ref.artifact_id)
    final_state = store.get_json(sim_result.state_snapshot_ref.artifact_id)
else:
    print(f"Execution failed: {result.notes}")
```

### State Resolution (Разрешение состояния)

Модуль поддерживает два формата входного состояния:

#### StateSnapshotRef (Прямой)
```python
request = ExecuteRequest(
    exec_plan_ref=exec_plan_ref,
    registry_bundle_ref=registry_bundle_ref,
    state_snapshot_ref=StateSnapshotRef(artifact_id=state_id),
    exec_config=ExecuteConfig(seed=42),
)
```

#### DataSnapshotRef (Через DataSnapshot)
```python
request = ExecuteRequest(
    exec_plan_ref=exec_plan_ref,
    registry_bundle_ref=registry_bundle_ref,
    data_snapshot_ref=DataSnapshotRef(artifact_id=data_snapshot_id),
    exec_config=ExecuteConfig(seed=42),
)
```

### Environment Capture (Захват окружения)

```python
exec_config = ExecuteConfig(
    seed=42,
    capture_env=True,  # Захватывать environment fingerprint
)
```

Когда `capture_env=True`, создается `EnvironmentFingerprint` для обеспечения воспроизводимости результатов.

## Архитектурные особенности

### Artifact-based workflow

Все данные в execute модуле хранятся как артефакты с полными метаданными:

```python
sim_inputs = [
    InputRef(artifact_id=request.exec_plan_ref.artifact_id, role="exec_plan"),
    InputRef(artifact_id=exec_artifacts.metrics_ref.artifact_id, role="metrics"),
    InputRef(artifact_id=exec_artifacts.state_delta_ref.artifact_id, role="state_delta"),
    InputRef(artifact_id=applied.state_snapshot_ref.artifact_id, role="state_snapshot"),
]
```

### State Delta Application

Изменения состояния применяются через delta-based механизм:

1. **State Delta**: Разница между начальным и конечным состоянием
2. **Merge Rules**: Применение правил слияния для конфликтующих изменений
3. **State Snapshot**: Финальное состояние после применения всех изменений

### Constraint Validation

После каждого шага исполнения проверяются ограничения:

```python
if exec_artifacts.constraint_report_ref is not None:
    constraint_report = store.get_json(exec_artifacts.constraint_report_ref.artifact_id)
    if not constraint_report.ok:
        # Обработка нарушений ограничений
        pass
```

### Metrics Collection

Автоматический сбор метрик исполнения:

- **Performance metrics**: Время выполнения, использование памяти
- **State metrics**: Изменения в ключевых показателях
- **Constraint metrics**: Статистика по проверкам ограничений

## Связь с другими модулями

- **`foundry.executor`**: Низкоуровневый executor для ProgramGraph
- **`foundry.runtime`**: Runtime компоненты для исполнения
- **`core.contracts.foundry`**: Типы данных для исполнения
- **`core.artifacts`**: Хранение результатов исполнения
- **`scientist.executor`**: Высокоуровневый API для экспериментов

---

Модуль `execute` - основной интерфейс для запуска скомпилированных политик с полным tracking всех артефактов и результатов исполнения.