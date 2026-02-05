# Run (Контексты выполнения)

Инфраструктура управления контекстами выполнения с автоматической трассировкой, жизненным циклом и метаданными. Обеспечивает наблюдаемость и provenance.

## Архитектура

```
run/
├── context.py     # RunContext - управление выполнением
├── manifest.py    # RunManifest - метаданные запусков
└── __init__.py    # Экспорт компонентов
```

## Компоненты

- **RunManifest**: Метаданные запуска (run_id, timestamps, producer, inputs/outputs, trace_ref)
- **RunContext**: Управление выполнением с интегрированной трассировкой

## Жизненный цикл

1. **Инициализация**: `RunContext.start()` с генерацией run_id
2. **Регистрация**: `ctx.add_input()`, `ctx.add_output()` для provenance
3. **Трассировка**: `ctx.emit(phase, event, metrics={}, inputs=[], outputs=[])`
4. **Завершение**: `ctx.finish(success=True/False)`

## Трассировка

Автоматическая трассировка через `ctx.emit()` с метриками, артефактными ссылками, warnings/errors. Создает TraceRecord.

## Управление артефактами

### Регистрация входов/выходов

```python
# Ручная регистрация
ctx.run_manifest.inputs.append(data_ref)
ctx.run_manifest.outputs.append(result_ref)

# Рекомендуемый способ
ctx.add_input(data_ref)
ctx.add_output(result_ref)
```

### Автоматическое сохранение трассировки

```python
# Трассировка сохраняется как артефакт при завершении
ctx.finish(success=True)
trace_ref = ctx.run_manifest.trace_ref
```

## Интеграция с модулями

- **Foundry**: `SimulationEngine(ctx)` для симуляций
- **Fabric**: `DataProcessor(ctx)` для обработки данных
- **Scientist**: `Experiment(ctx)` для оркестрации
- **Runtime**: `PolicyExecutor(ctx)` для production исполнения

## Структура файловой системы

```
/artifacts/runs/R_{run_id}/
├── trace.jsonl          # Трассировка в JSONL формате
└── manifest.json        # Манифест выполнения (опционально)
```

### Формат трассировки

```jsonl
{"ts": "2024-01-15T10:30:00Z", "run_id": "R_123", "phase": "init", "event": "RUN_STARTED"}
{"ts": "2024-01-15T10:30:05Z", "run_id": "R_123", "phase": "data_load", "event": "batch_loaded", "metrics": {"batch_size": 1000}}
```

## Примеры использования

### Полный рабочий процесс

```python
def run_policy_simulation(policy_ref, config_ref):
    store = FileSystemCAS(Path("/tmp/artifacts"))
    ctx = RunContext.start(store=store, registry_bundle=registry_ref)

    try:
        ctx.add_input(policy_ref)
        ctx.add_input(config_ref)

        # Этапы выполнения с трассировкой
        ctx.emit("data_loading", "STARTED")
        data_ref = load_training_data(ctx)
        ctx.emit("data_loading", "COMPLETED", outputs=[data_ref])

        ctx.emit("simulation", "STARTED", inputs=[policy_ref, data_ref])
        result_ref = run_simulation(ctx, policy_ref, data_ref)
        ctx.emit("simulation", "COMPLETED", outputs=[result_ref])

        ctx.finish(success=True)
        return result_ref

    except Exception as e:
        ctx.emit("error", "EXECUTION_FAILED", metrics={"error": str(e)})
        ctx.finish(success=False)
        raise
```

### Анализ трассировки

```python
def analyze_run_trace(store, run_id):
    trace_path = store.root / "runs" / run_id / "trace.jsonl"
    records = [json.loads(line) for line in open(trace_path)]
    
    analysis = {
        "run_id": run_id,
        "total_events": len(records),
        "phases": {},
        "artifacts_created": sum(len(r.get("refs", {}).get("outputs", [])) for r in records)
    }
    
    # Группировка по фазам
    for record in records:
        phase = record.get("phase", "unknown")
        analysis["phases"][phase] = analysis["phases"].get(phase, 0) + 1
    
    return analysis
```

## Производительность

- **Overhead**: <0.1ms на операцию трассировки
- **Хранение**: JSONL формат для потоковой записи
- **Память**: Буферизованная запись для больших объемов
- **Конкурентность**: Thread-safe

## Лучшие практики

- Всегда используйте RunContext для нетривиальных операций
- Добавляйте входы/выходы для provenance tracking
- Эмитируйте события с описательными именами
- Добавляйте метрики производительности
- Обрабатывайте ошибки с трассировкой
- Завершайте контекст для сохранения трассировки

## Мониторинг

### Проверка статуса

```python
def get_run_status(store, run_id):
    manifest_path = store.root / "runs" / run_id / "manifest.json"
    if manifest_path.exists():
        data = json.load(open(manifest_path))
        return {
            "status": data.get("status"),
            "started_at": data.get("started_at"),
            "inputs_count": len(data.get("inputs", [])),
            "outputs_count": len(data.get("outputs", []))
        }
    return {"status": "unknown"}
```

### Поиск неудачных запусков

```python
def find_failed_runs(store, run_ids):
    failed = []
    for run_id in run_ids:
        trace_path = store.root / "runs" / run_id / "trace.jsonl"
        if trace_path.exists():
            for line in open(trace_path):
                if json.loads(line).get("event") == "EXECUTION_FAILED":
                    failed.append(run_id)
                    break
    return failed
```