# Run Module (Контексты выполнения)

## Обзор

Модуль `run` предоставляет инфраструктуру для управления контекстами и манифестами выполнения операций в системе PolisyOS. RunContext обеспечивает унифицированный способ запуска операций с автоматической трассировкой, управлением жизненным циклом и сбором метаданных. Модуль интегрируется с системой артефактов и трассировки для обеспечения наблюдаемости и воспроизводимости.

## Архитектура

```
run/
├── context.py     # RunContext - основной класс для управления выполнением
├── manifest.py    # RunManifest - метаданные о запуске
└── __init__.py    # Экспорт основных компонентов
```

## Основные компоненты

### RunManifest

Манифест выполнения содержит метаданные о запуске операции.

```python
from polisyos.core.run.manifest import RunManifest
from polisyos.core.artifacts.manifest import ProducerInfo, EnvInfo, ArtifactRef

manifest = RunManifest(
    run_id="R_1234567890abcdef",
    started_at=datetime.now(),
    producer=ProducerInfo(
        component="policy_simulator",
        version="2.1.0",
        git=GitInfo(commit="abc123def", dirty=False)
    ),
    env=EnvInfo(
        python="3.11.5",
        platform="linux",
        deps_lock_hash="sha256:..."
    ),
    registry_bundle=registry_bundle_ref,
    inputs=[input_data_ref, config_ref],
    outputs=[simulation_result_ref, metrics_ref],
    status="completed",
    trace_ref=trace_artifact_ref
)
```

### RunContext

Основной класс для управления контекстом выполнения с интегрированной трассировкой.

```python
from polisyos.core.run.context import RunContext
from polisyos.core.artifacts.store import FileSystemCAS
from pathlib import Path

store = FileSystemCAS(Path("/tmp/artifacts"))

# Создание контекста выполнения
ctx = RunContext.start(
    store=store,
    registry_bundle=registry_bundle_ref,
    producer=ProducerInfo(component="simulation_engine", version="1.0.0"),
    run_dir=Path("/tmp/runs/my_simulation")
)

print(f"Run ID: {ctx.run_manifest.run_id}")
print(f"Started at: {ctx.run_manifest.started_at}")
```

## Жизненный цикл выполнения

### 1. Инициализация контекста

```python
from polisyos.core.run.context import RunContext

# Автоматическая генерация run_id
ctx = RunContext.start(
    store=store,
    registry_bundle=registry_bundle_ref,
    producer=ProducerInfo(component="my_component", version="1.0.0")
)

# Или с кастомным run_id
ctx = RunContext.start(
    store=store,
    registry_bundle=registry_bundle_ref,
    run_id="custom_run_001"
)
```

### 2. Регистрация входов и выходов

```python
# Регистрация входных артефактов
ctx.add_input(input_data_ref)
ctx.add_input(config_ref)

# Выполнение операций с трассировкой
ctx.emit("data_processing", "STARTED")
processed_data_ref = process_data(ctx, input_data_ref)
ctx.add_output(processed_data_ref)

ctx.emit("simulation", "STARTED", inputs=[processed_data_ref])
result_ref = run_simulation(ctx, processed_data_ref, config_ref)
ctx.add_output(result_ref)
```

### 3. Завершение выполнения

```python
# Автоматическое завершение (рекомендуется)
ctx.finish(success=True)

# Или ручное завершение с кодом
ctx.finish(success=False, error_msg="Simulation diverged")
```

## Трассировка операций

### Автоматическая трассировка

```python
# Трассировка с метриками
ctx.emit(
    "computation",
    "batch_processed",
    inputs=[batch_ref],
    outputs=[result_ref],
    metrics={
        "batch_size": 1000,
        "processing_time_ms": 450,
        "memory_mb": 256,
        "cpu_percent": 85
    }
)

# Трассировка ошибок
ctx.emit(
    "validation",
    "constraint_violation",
    metrics={"violations_count": 5}
)
```

### Структура записей трассировки

Каждая запись содержит:

```python
TraceRecord(
    ts=datetime.now(),                    # Временная метка
    run_id="R_1234567890abcdef",          # ID запуска
    phase="computation",                  # Фаза выполнения
    event="batch_processed",              # Событие
    span_id=None,                         # Для распределенной трассировки
    parent_span_id=None,                  # Иерархия операций
    refs={                                # Ссылки на артефакты
        "inputs": [input_ref],
        "outputs": [output_ref]
    },
    metrics={                             # Метрики выполнения
        "processing_time_ms": 450,
        "memory_mb": 256
    },
    warnings=[],                          # Предупреждения
    errors=[]                             # Ошибки
)
```

## Управление артефактами

### Регистрация входов/выходов

```python
# Ручная регистрация
ctx.run_manifest.inputs.append(data_ref)
ctx.run_manifest.outputs.append(result_ref)

# Или через методы (рекомендуется)
ctx.add_input(data_ref)
ctx.add_output(result_ref)
```

### Автоматическое сохранение трассировки

```python
# При завершении контекста трассировка сохраняется как артефакт
ctx.finish(success=True)

# trace_ref добавляется в manifest
trace_artifact_ref = ctx.run_manifest.trace_ref
```

## Интеграция с другими модулями

### Foundry (Симуляция)
```python
from polisyos.foundry.execution import SimulationEngine

engine = SimulationEngine(ctx)
result = engine.run(policy_graph_ref, exec_config_ref)
```

### Fabric (Обработка данных)
```python
from polisyos.fabric.processor import DataProcessor

processor = DataProcessor(ctx)
result_ref = processor.process(query_plan_ref)
```

### Scientist (Оркестрация)
```python
from polisyos.scientist.experiment import Experiment

experiment = Experiment(ctx)
results = experiment.run(decision_packet_ref)
```

### Runtime (Production)
```python
from polisyos.runtime.executor import PolicyExecutor

executor = PolicyExecutor(ctx)
decision = executor.evaluate(request_data)
```

## Структура файловой системы

### Организация директорий

```
/tmp/artifacts/
├── runs/
│   └── R_1234567890abcdef/
│       ├── trace.jsonl          # Трассировка в JSONL формате
│       └── manifest.json        # Манифест выполнения (опционально)
└── artifacts/
    ├── sha256/ab/cd/trace_hash.blob
    ├── sha256/ab/cd/trace_hash.manifest.json
    └── ...
```

### Формат трассировки

```jsonl
{"ts": "2024-01-15T10:30:00Z", "run_id": "R_1234567890abcdef", "phase": "init", "event": "RUN_STARTED"}
{"ts": "2024-01-15T10:30:05Z", "run_id": "R_1234567890abcdef", "phase": "data_load", "event": "batch_loaded", "metrics": {"batch_size": 1000}}
{"ts": "2024-01-15T10:31:15Z", "run_id": "R_1234567890abcdef", "phase": "computation", "event": "processing_completed", "metrics": {"time_ms": 70000}}
```

## Примеры использования

### Полный рабочий процесс

```python
from pathlib import Path
from polisyos.core.run.context import RunContext
from polisyos.core.artifacts.store import FileSystemCAS

def run_policy_simulation(policy_ref: ArtifactRef, config_ref: ArtifactRef) -> ArtifactRef:
    """Запуск симуляции политики с полным трекингом"""

    store = FileSystemCAS(Path("/tmp/artifacts"))

    # Инициализация контекста
    ctx = RunContext.start(
        store=store,
        registry_bundle=registry_bundle_ref,
        producer=ProducerInfo(component="policy_simulator", version="1.0.0")
    )

    try:
        # Регистрация входов
        ctx.add_input(policy_ref)
        ctx.add_input(config_ref)

        # Этап 1: Загрузка данных
        ctx.emit("data_loading", "STARTED")
        data_ref = load_training_data(ctx)
        ctx.add_output(data_ref)
        ctx.emit("data_loading", "COMPLETED", outputs=[data_ref])

        # Этап 2: Компиляция политики
        ctx.emit("compilation", "STARTED", inputs=[policy_ref])
        compiled_ref = compile_policy(ctx, policy_ref)
        ctx.add_output(compiled_ref)
        ctx.emit("compilation", "COMPLETED", outputs=[compiled_ref])

        # Этап 3: Симуляция
        ctx.emit("simulation", "STARTED", inputs=[compiled_ref, data_ref])
        result_ref = run_simulation(ctx, compiled_ref, data_ref, config_ref)
        ctx.add_output(result_ref)
        ctx.emit("simulation", "COMPLETED", outputs=[result_ref])

        # Успешное завершение
        ctx.finish(success=True)
        return result_ref

    except Exception as e:
        # Обработка ошибок
        ctx.emit("error", "EXECUTION_FAILED", metrics={"error": str(e)})
        ctx.finish(success=False, error_msg=str(e))
        raise
```

### Анализ трассировки

```python
def analyze_run_trace(store: FileSystemCAS, run_id: str) -> dict:
    """Анализ трассировки выполнения"""

    # Поиск трассировки (обычно в runs/{run_id}/trace.jsonl)
    trace_path = store.root / "runs" / run_id / "trace.jsonl"

    if not trace_path.exists():
        return {"error": "Trace file not found"}

    # Загрузка записей трассировки
    records = []
    with open(trace_path) as f:
        for line in f:
            records.append(json.loads(line))

    # Анализ
    analysis = {
        "run_id": run_id,
        "total_events": len(records),
        "phases": {},
        "duration_ms": None,
        "artifacts_created": 0
    }

    if records:
        start_time = datetime.fromisoformat(records[0]["ts"].replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(records[-1]["ts"].replace("Z", "+00:00"))
        analysis["duration_ms"] = (end_time - start_time).total_seconds() * 1000

    # Группировка по фазам
    for record in records:
        phase = record.get("phase", "unknown")
        if phase not in analysis["phases"]:
            analysis["phases"][phase] = 0
        analysis["phases"][phase] += 1

        # Подсчет созданных артефактов
        refs = record.get("refs", {})
        outputs = refs.get("outputs", [])
        analysis["artifacts_created"] += len(outputs)

    return analysis
```

### Управление ресурсами

```python
class ResourceManager:
    """Менеджер ресурсов с RunContext"""

    def __init__(self, ctx: RunContext):
        self.ctx = ctx
        self.resources = []

    def allocate_resource(self, resource_type: str, config: dict) -> str:
        """Выделение ресурса с трассировкой"""

        resource_id = f"{resource_type}_{len(self.resources)}"

        self.ctx.emit(
            "resource_management",
            "RESOURCE_ALLOCATED",
            metrics={
                "resource_type": resource_type,
                "resource_id": resource_id,
                **config
            }
        )

        self.resources.append(resource_id)
        return resource_id

    def release_resources(self):
        """Освобождение всех ресурсов"""

        for resource_id in self.resources:
            self.ctx.emit(
                "resource_management",
                "RESOURCE_RELEASED",
                metrics={"resource_id": resource_id}
            )

        self.resources.clear()
```

## Производительность

- **Низкий overhead**: <0.1ms на операцию трассировки
- **Эффективное хранение**: JSONL формат для потоковой записи
- **Память**: Буферизованная запись для больших объемов трассировки
- **Конкурентность**: Thread-safe для параллельного выполнения

## Лучшие практики

1. **Всегда используйте RunContext**: Для любой нетривиальной операции
2. **Добавляйте входы/выходы**: Для полного provenance tracking
3. **Эмитируйте события**: С описательными phase/event именами
4. **Добавляйте метрики**: Для мониторинга производительности
5. **Обрабатывайте ошибки**: С трассировкой исключений
6. **Завершайте контекст**: Для сохранения трассировки

## Мониторинг и отладка

### Проверка статуса выполнения

```python
def get_run_status(store: FileSystemCAS, run_id: str) -> dict:
    """Получение статуса выполнения"""

    # Поиск манифеста (если сохранен)
    manifest_path = store.root / "runs" / run_id / "manifest.json"

    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest_data = json.load(f)
            return {
                "status": manifest_data.get("status"),
                "started_at": manifest_data.get("started_at"),
                "finished_at": manifest_data.get("finished_at"),
                "inputs_count": len(manifest_data.get("inputs", [])),
                "outputs_count": len(manifest_data.get("outputs", []))
            }

    # Альтернативно: анализ трассировки
    return {"status": "unknown", "run_id": run_id}
```

### Поиск проблемных запусков

```python
def find_failed_runs(store: FileSystemCAS, run_ids: list[str]) -> list[str]:
    """Поиск запусков завершившихся с ошибками"""

    failed_runs = []

    for run_id in run_ids:
        trace_path = store.root / "runs" / run_id / "trace.jsonl"

        if not trace_path.exists():
            continue

        has_error = False
        with open(trace_path) as f:
            for line in f:
                record = json.loads(line)
                if record.get("event") == "EXECUTION_FAILED":
                    has_error = True
                    break

        if has_error:
            failed_runs.append(run_id)

    return failed_runs
```