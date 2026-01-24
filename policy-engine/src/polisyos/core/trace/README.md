# Trace Module (Система трассировки)

## Обзор

Модуль `trace` предоставляет унифицированную систему логирования и трассировки операций для обеспечения наблюдаемости, отладки и аудита в системе PolisyOS. Модуль поддерживает структурированное логирование с временными метками, span-based трекинг, ссылки на артефакты и метрики производительности.

## Архитектура

```
trace/
├── record.py     # TraceRecord - структура записей трассировки
├── sink.py       # TraceSink - интерфейс и реализации для вывода
└── __init__.py   # Экспорт основных компонентов
```

## Основные компоненты

### TraceRecord

Структура записи трассировки с полными метаданными.

```python
from polisyos.core.trace.record import TraceRecord, TraceRefs
from polisyos.core.artifacts.manifest import ArtifactRef
from datetime import datetime

# Создание записи трассировки
record = TraceRecord(
    ts=datetime.now(),                    # Временная метка (автоматическая)
    run_id="R_1234567890abcdef",          # ID запуска
    phase="computation",                  # Фаза выполнения
    event="batch_processed",              # Событие
    span_id="process_batch_001",          # ID спана (опционально)
    parent_span_id="main_process",        # Родительский спан (опционально)
    refs=TraceRefs(                       # Ссылки на артефакты
        inputs=[input_data_ref],
        outputs=[result_ref]
    ),
    metrics={                             # Метрики выполнения
        "processing_time_ms": 450,
        "memory_mb": 256,
        "cpu_percent": 85,
        "records_processed": 1000
    },
    warnings=[                            # Предупреждения
        {"code": "PERF_WARNING", "msg": "High memory usage detected"}
    ],
    errors=[                              # Ошибки
        {"code": "VALIDATION_ERROR", "msg": "Invalid data format"}
    ]
)
```

### TraceSink (Протокол)

Интерфейс для вывода записей трассировки.

```python
from polisyos.core.trace.sink import TraceSink
from polisyos.core.trace.record import TraceRecord

class TraceSink(Protocol):
    def emit(self, rec: TraceRecord) -> None:
        """Вывод записи трассировки"""
        ...
```

### JsonlTraceSink

Реализация вывода в JSON Lines формат.

```python
from polisyos.core.trace.sink import JsonlTraceSink
from pathlib import Path

# Создание sink для файла
trace_sink = JsonlTraceSink(Path("/tmp/trace.jsonl"))

# Вывод записи
trace_sink.emit(record)
```

## Формат JSONL

### Структура файла трассировки

```jsonl
{"ts":"2024-01-15T10:30:00Z","run_id":"R_1234567890abcdef","phase":"init","event":"RUN_STARTED"}
{"ts":"2024-01-15T10:30:05Z","run_id":"R_1234567890abcdef","phase":"data_load","event":"batch_loaded","metrics":{"batch_size":1000},"refs":{"inputs":["sha256:abc..."],"outputs":[]}}
{"ts":"2024-01-15T10:31:15Z","run_id":"R_1234567890abcdef","phase":"computation","event":"processing_completed","metrics":{"time_ms":70000,"memory_mb":512},"refs":{"inputs":["sha256:abc..."],"outputs":["sha256:def..."]}}
{"ts":"2024-01-15T10:31:20Z","run_id":"R_1234567890abcdef","phase":"validation","event":"constraint_check_failed","warnings":[{"code":"CONSTRAINT_VIOLATION","msg":"Budget limit exceeded"}],"refs":{"inputs":["sha256:def..."]}}
```

### Поля записи

- **ts**: Временная метка в ISO 8601 формате (UTC)
- **run_id**: Уникальный идентификатор запуска (формат: R_ + 16 hex символов)
- **phase**: Фаза выполнения (init, data_load, computation, validation, etc.)
- **event**: Конкретное событие (batch_loaded, processing_completed, etc.)
- **span_id**: ID спана для распределенной трассировки (опционально)
- **parent_span_id**: ID родительского спана (опционально)
- **refs**: Ссылки на входные/выходные артефакты
- **metrics**: Числовые метрики выполнения
- **warnings**: Список предупреждений
- **errors**: Список ошибок

## Использование в RunContext

### Автоматическая интеграция

```python
from polisyos.core.run.context import RunContext

# RunContext автоматически создает JsonlTraceSink
ctx = RunContext.start(store=store, registry_bundle=bundle_ref)

# Все emit() calls записываются в trace.jsonl
ctx.emit("data_processing", "STARTED")
ctx.emit("computation", "COMPLETED", metrics={"time_ms": 1500})
```

### Ручное использование

```python
from polisyos.core.trace.sink import JsonlTraceSink
from polisyos.core.trace.record import TraceRecord

sink = JsonlTraceSink(Path("my_trace.jsonl"))

# Создание и вывод записей
record = TraceRecord(
    run_id="manual_run_001",
    phase="custom_operation",
    event="operation_completed",
    metrics={"duration": 42}
)

sink.emit(record)
```

## Span-based трассировка

### Иерархическая структура

```python
# Родительская операция
parent_record = TraceRecord(
    run_id="R_1234567890abcdef",
    phase="workflow",
    event="STARTED",
    span_id="workflow_001"
)

# Дочерняя операция
child_record = TraceRecord(
    run_id="R_1234567890abcdef",
    phase="computation",
    event="matrix_multiplication",
    span_id="compute_001",
    parent_span_id="workflow_001",  # Ссылка на родителя
    metrics={"flops": 1_000_000}
)
```

### Пример workflow

```python
def traced_workflow(ctx: RunContext, input_ref: ArtifactRef) -> ArtifactRef:
    """Пример workflow с иерархической трассировкой"""

    # Начало основного workflow
    ctx.emit("workflow", "STARTED", span_id="main_workflow")

    # Этап 1: Загрузка данных
    ctx.emit("data_load", "STARTED", span_id="load_data", parent_span_id="main_workflow")
    data_ref = load_data(ctx, input_ref)
    ctx.emit("data_load", "COMPLETED", span_id="load_data", outputs=[data_ref])

    # Этап 2: Параллельные вычисления
    results = []
    for i in range(3):
        span_id = f"compute_{i}"
        ctx.emit("computation", "STARTED", span_id=span_id, parent_span_id="main_workflow")

        result_ref = compute_partition(ctx, data_ref, partition=i)
        results.append(result_ref)

        ctx.emit("computation", "COMPLETED", span_id=span_id, outputs=[result_ref])

    # Этап 3: Агрегация результатов
    ctx.emit("aggregation", "STARTED", span_id="aggregate", parent_span_id="main_workflow")
    final_result_ref = aggregate_results(ctx, results)
    ctx.emit("aggregation", "COMPLETED", span_id="aggregate", outputs=[final_result_ref])

    # Завершение workflow
    ctx.emit("workflow", "COMPLETED", span_id="main_workflow", outputs=[final_result_ref])

    return final_result_ref
```

## Интеграция с модулями

### Fabric (Обработка данных)

```python
from polisyos.fabric.processor import DataProcessor

processor = DataProcessor(ctx)

# Автоматическая трассировка всех операций
ctx.emit("fabric", "PROCESSING_STARTED", inputs=[query_plan_ref])
result_ref = processor.process(query_plan_ref)
ctx.emit("fabric", "PROCESSING_COMPLETED", outputs=[result_ref])
```

### Foundry (Симуляция)

```python
from polisyos.foundry.execution import SimulationEngine

engine = SimulationEngine(ctx)

# Детальная трассировка симуляции
ctx.emit("foundry", "SIMULATION_STARTED", inputs=[policy_ref, config_ref])
result_ref = engine.run(policy_ref, config_ref)
ctx.emit("foundry", "SIMULATION_COMPLETED", outputs=[result_ref], metrics=engine.metrics)
```

### Scientist (Оркестрация)

```python
from polisyos.scientist.experiment import Experiment

experiment = Experiment(ctx)

# Трассировка всего экспериментального pipeline
ctx.emit("scientist", "EXPERIMENT_STARTED", inputs=[decision_packet_ref])
results = experiment.run(decision_packet_ref)
ctx.emit("scientist", "EXPERIMENT_COMPLETED", outputs=results)
```

## Анализ трассировки

### Загрузка и парсинг

```python
import json
from pathlib import Path
from polisyos.core.trace.record import TraceRecord

def load_trace_records(trace_path: Path) -> list[TraceRecord]:
    """Загрузка записей трассировки из файла"""

    records = []
    with open(trace_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                record = TraceRecord(**data)
                records.append(record)

    return records
```

### Анализ производительности

```python
def analyze_performance(trace_path: Path) -> dict:
    """Анализ производительности из трассировки"""

    records = load_trace_records(trace_path)
    analysis = {
        "total_events": len(records),
        "phases": {},
        "total_duration_ms": 0,
        "artifacts_processed": 0,
        "errors_count": 0
    }

    if records:
        start_time = records[0].ts
        end_time = records[-1].ts
        analysis["total_duration_ms"] = (end_time - start_time).total_seconds() * 1000

    for record in records:
        # Подсчет по фазам
        phase = record.phase
        if phase not in analysis["phases"]:
            analysis["phases"][phase] = 0
        analysis["phases"][phase] += 1

        # Подсчет артефактов
        analysis["artifacts_processed"] += len(record.refs.inputs) + len(record.refs.outputs)

        # Подсчет ошибок
        analysis["errors_count"] += len(record.errors)

    return analysis
```

### Поиск проблем

```python
def find_errors(trace_path: Path) -> list[dict]:
    """Поиск записей с ошибками"""

    records = load_trace_records(trace_path)
    error_records = []

    for record in records:
        if record.errors:
            error_records.append({
                "timestamp": record.ts.isoformat(),
                "phase": record.phase,
                "event": record.event,
                "errors": record.errors,
                "span_id": record.span_id
            })

    return error_records
```

### Восстановление последовательности

```python
def reconstruct_execution_flow(trace_path: Path) -> list[dict]:
    """Восстановление последовательности выполнения"""

    records = load_trace_records(trace_path)
    flow = []

    # Сортировка по времени
    records.sort(key=lambda r: r.ts)

    # Группировка по спанам
    spans = {}
    for record in records:
        span_id = record.span_id or "root"
        if span_id not in spans:
            spans[span_id] = []
        spans[span_id].append(record)

    # Реконструкция иерархии
    for span_id, span_records in spans.items():
        parent_id = span_records[0].parent_span_id if span_records else None
        flow.append({
            "span_id": span_id,
            "parent_span_id": parent_id,
            "events": [r.event for r in span_records],
            "duration_ms": (span_records[-1].ts - span_records[0].ts).total_seconds() * 1000 if len(span_records) > 1 else 0
        })

    return flow
```

## Кастомные TraceSink

### File-based sink

```python
class RotatingTraceSink:
    """Sink с ротацией файлов"""

    def __init__(self, base_path: Path, max_size_mb: int = 100):
        self.base_path = base_path
        self.max_size_mb = max_size_mb
        self.current_file = None
        self._check_rotation()

    def emit(self, rec: TraceRecord) -> None:
        self._check_rotation()
        line = rec.model_dump_json(exclude_none=True) + "\n"

        with open(self.current_file, "a", encoding="utf-8") as f:
            f.write(line)

    def _check_rotation(self) -> None:
        if self.current_file is None or self._file_size_mb() >= self.max_size_mb:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_file = self.base_path.parent / f"{self.base_path.stem}_{timestamp}.jsonl"

    def _file_size_mb(self) -> float:
        if self.current_file and self.current_file.exists():
            return self.current_file.stat().st_size / (1024 * 1024)
        return 0
```

### Database sink

```python
class DatabaseTraceSink:
    """Sink для записи в базу данных"""

    def __init__(self, connection_string: str):
        self.conn = create_database_connection(connection_string)

    def emit(self, rec: TraceRecord) -> None:
        # Вставка в базу данных
        self.conn.execute("""
            INSERT INTO trace_records
            (timestamp, run_id, phase, event, span_id, parent_span_id, refs, metrics, warnings, errors)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rec.ts.isoformat(),
            rec.run_id,
            rec.phase,
            rec.event,
            rec.span_id,
            rec.parent_span_id,
            json.dumps(rec.refs.model_dump()),
            json.dumps(rec.metrics),
            json.dumps(rec.warnings),
            json.dumps(rec.errors)
        ))
        self.conn.commit()
```

### Async sink

```python
import asyncio
import aiofiles

class AsyncJsonlTraceSink:
    """Асинхронный sink для высокопроизводительных систем"""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.queue = asyncio.Queue()
        self._task = None

    async def start(self):
        """Запуск фоновой задачи записи"""
        self._task = asyncio.create_task(self._writer())

    async def stop(self):
        """Остановка записи"""
        await self.queue.put(None)  # Сигнал завершения
        if self._task:
            await self._task

    def emit(self, rec: TraceRecord) -> None:
        """Синхронный интерфейс, асинхронная запись"""
        self.queue.put_nowait(rec)

    async def _writer(self):
        """Фоновая задача записи"""
        async with aiofiles.open(self.path, "a", encoding="utf-8") as f:
            while True:
                rec = await self.queue.get()
                if rec is None:  # Сигнал завершения
                    break

                line = rec.model_dump_json(exclude_none=True) + "\n"
                await f.write(line)
                await f.flush()
```

## Производительность

- **Низкий overhead**: <0.1ms на операцию трассировки
- **Эффективное хранение**: JSONL для потоковой обработки
- **Масштабируемость**: Поддержка миллионов записей
- **Фильтрация**: Легко фильтровать и анализировать

## Лучшие практики

1. **Используйте описательные phase/event**: Для понятной трассировки
2. **Добавляйте метрики**: Для мониторинга производительности
3. **Включайте span_id**: Для сложных workflow
4. **Логируйте ошибки**: С полным контекстом
5. **Добавляйте provenance**: Через refs на артефакты
6. **Регулярно анализируйте**: Трассировки для оптимизации

## Мониторинг и алертинг

### Пороги производительности

```python
def check_performance_thresholds(trace_path: Path, thresholds: dict) -> list[str]:
    """Проверка порогов производительности"""

    records = load_trace_records(trace_path)
    alerts = []

    for record in records:
        for metric_name, threshold in thresholds.items():
            if metric_name in record.metrics:
                value = record.metrics[metric_name]
                if value > threshold:
                    alerts.append(
                        f"Threshold exceeded: {metric_name}={value} > {threshold} "
                        f"in {record.phase}.{record.event}"
                    )

    return alerts
```

### Детекция аномалий

```python
def detect_anomalies(trace_path: Path) -> list[str]:
    """Детекция аномалий в трассировке"""

    records = load_trace_records(trace_path)
    anomalies = []

    # Группировка по фазам
    phase_stats = {}
    for record in records:
        phase = record.phase
        if phase not in phase_stats:
            phase_stats[phase] = {"count": 0, "errors": 0, "warnings": 0}

        phase_stats[phase]["count"] += 1
        phase_stats[phase]["errors"] += len(record.errors)
        phase_stats[phase]["warnings"] += len(record.warnings)

    # Поиск аномалий
    for phase, stats in phase_stats.items():
        error_rate = stats["errors"] / stats["count"] if stats["count"] > 0 else 0
        if error_rate > 0.1:  # >10% ошибок
            anomalies.append(f"High error rate in {phase}: {error_rate:.1%}")

        warning_rate = stats["warnings"] / stats["count"] if stats["count"] > 0 else 0
        if warning_rate > 0.5:  # >50% предупреждений
            anomalies.append(f"High warning rate in {phase}: {warning_rate:.1%}")

    return anomalies
```