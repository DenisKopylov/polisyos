# Compute Layer: Спецификации задач и execution backends

**Интерфейсы для запуска симуляций и распределенных вычислений**

Compute Layer определяет интерфейсы и спецификации для reproducible выполнения задач симуляции через различные execution backends.

## Структура

```
compute/
├── job_spec.py      # JobSpec, JobKey, JobResult для структурированных задач
└── runner.py        # LocalBackend, RayBackend для выполнения
```

## Ключевые компоненты

- **JobSpec**: Детальные спецификации задач с reproducible SHA256 keys
- **JobKey**: Уникальный идентификатор задачи на основе content hash
- **JobResult**: Результаты выполнения с state deltas и metrics
- **LocalBackend**: Локальное выполнение через Foundry executor
- **RayBackend**: Skeleton для распределенного выполнения (кластеры)

## API Использование

```python
from polisyos.scientist.compute.job_spec import JobSpec, JobKey
from polisyos.scientist.compute.runner import run_job

# Создание спецификации
job_spec = JobSpec(
    program_ref=compiled_program_artifact,
    seed=42,
    required_metrics=["gdp", "unemployment"]
)

# Получение уникального ключа
job_key = JobKey.from_spec(job_spec)

# Выполнение
result = run_job(job_spec, backend=LocalBackend(), ...)
```

## Связи

- Интегрируется с **Foundry** executor для JAX симуляций
- Использует **Core** artifacts для CAS management
- Поддерживает **Runtime** для lifecycle tracking