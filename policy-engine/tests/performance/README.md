# Performance Tests

Валидация производительности и обнаружение регрессий в ключевых компонентах Policy Engine.

**Последнее обновление:** 29 января 2026
**Уровень:** Performance Validation (Phase 3)
**Зависимости:** JAX, NumPy, Core Observability, Foundry Runtime

## Архитектурный контекст

Performance тесты обеспечивают что система обсервабилити не создает значительного overhead на критически важные операции. Тесты валидируют SLA (Service Level Agreements) для различных типов workloads:

- **Simulation Operations**: < 2% overhead
- **CAS I/O Operations**: < 5% overhead
- **Calibration Operations**: < 3% overhead

## Структура тестов

```
performance/
└── test_overhead.py          # Overhead валидация для simulation, CAS I/O, calibration
```

## Категории тестов

### Overhead Validation (`test_overhead.py`)

**Цель:** Измерение и валидация overhead системы обсервабилити на ключевых операциях.

**Ключевые тесты:**
- **Simulation Overhead**: Валидация что tracing/metrics/logging добавляют <2% к simulation операциям
- **CAS I/O Overhead**: Проверка что observability overhead <5% для content-addressable storage операций
- **Calibration Overhead**: Убеждение что overhead <3% для parameter optimization операций
- **Statistical Benchmarking**: Множественные runs с confidence intervals для reliable measurements

**Принципы:**
- **Acceptable Thresholds**: Предопределенные SLA для каждого типа операций
- **Statistical Reliability**: Bootstrap confidence intervals для measurement accuracy
- **Reproducible Benchmarks**: CPU enforcement и deterministic inputs
- **Warmup Phases**: Proper JIT compilation и caching перед measurements
- **Cross-platform Consistency**: Identical results across different environments

## Конфигурация окружения

### JAX Configuration
```python
# CPU enforcement для reproducible benchmarks
os.environ["JAX_PLATFORM_NAME"] = "cpu"
os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
```

### Benchmarking Framework
```python
def benchmark_function(
    func: Callable[[], T],
    warmup_runs: int = 3,
    benchmark_runs: int = 10,
) -> tuple[float, float, T]:
    """
    Returns (mean_time, std_time, last_result)
    """
```

## Запуск тестов

```bash
# Все performance тесты
pytest tests/performance/ -v

# Конкретные overhead тесты
pytest tests/performance/test_overhead.py::TestSimulationOverhead -v
pytest tests/performance/test_overhead.py::TestCASOverhead -v
pytest tests/performance/test_overhead.py::TestCalibrationOverhead -v
```

## Связи с другими модулями

### Зависимости Performance Tests

**Core Observability** (`core/observability/`):
- **Tracer**: Overhead measurement для PolicyOSTracer operations
- **Metrics**: Performance impact от MetricsRegistry
- **@traced Decorator**: Overhead от automatic function tracing

**Foundry Runtime** (`foundry/runtime/`):
- **run_scan**: Simulation execution для overhead validation
- **JIT Operations**: Compilation performance impact

**Core Artifacts** (`core/artifacts/`):
- **CAS Operations**: Content-addressable storage I/O overhead
- **FileSystemCAS**: Artifact persistence performance

### Архитектурные инварианты

- **Закон Q**: Performance SLA (overhead thresholds enforced)
- **Observability Transparency**: Tracing/metrics должны быть performance-neutral
- **Regression Prevention**: Automatic detection performance degradation
- **Benchmark Reproducibility**: Deterministic results across environments

## Разработка и расширение

### Добавление новых performance тестов

1. Определите тип операции и acceptable overhead threshold
2. Создайте baseline function без observability
3. Создайте instrumented function с полной observability
4. Используйте `benchmark_function` для statistical measurement
5. Валидируйте что overhead < threshold с confidence intervals
6. Добавьте regression detection через CI/CD integration

### Overhead Measurement Best Practices

```python
# Правильный паттерн для overhead measurement
def test_operation_overhead():
    # Baseline - без observability
    def baseline():
        return expensive_operation()

    # Instrumented - с полной observability
    @traced
    def instrumented():
        return expensive_operation()

    # Statistical benchmarking
    baseline_time, _, _ = benchmark_function(baseline)
    instrumented_time, _, _ = benchmark_function(instrumented)

    # Overhead calculation
    overhead = (instrumented_time - baseline_time) / baseline_time
    assert overhead < THRESHOLD, f"Overhead {overhead:.1%} exceeds {THRESHOLD:.1%}"
```

## Troubleshooting

### Распространенные проблемы

**Inconsistent benchmark results:**
```bash
# Убедитесь что CPU enforced
export JAX_PLATFORM_NAME=cpu
pytest tests/performance/test_overhead.py -v --tb=short
```

**JIT compilation interference:**
```bash
# Проверьте что warmup достаточный
pytest tests/performance/test_overhead.py::TestSimulationOverhead::test_run_scan_overhead -v -s
```

**Memory allocation overhead:**
```bash
# Отключите preallocation
export XLA_PYTHON_CLIENT_PREALLOCATE=false
pytest tests/performance/test_overhead.py -v
```

## Технологии и зависимости

### Benchmarking Infrastructure
- **JAX**: GPU/CPU operations с deterministic timing
- **NumPy**: Statistical analysis для confidence intervals
- **time.perf_counter**: High-resolution timing measurements

### Performance Validation
- **Statistical Methods**: Bootstrap confidence intervals
- **Regression Detection**: Automatic SLA enforcement
- **Cross-platform Benchmarks**: Environment-independent results

### Integration с CI/CD
- **Threshold Enforcement**: Automatic failure на SLA violations
- **Historical Tracking**: Performance regression detection
- **Environment Consistency**: Reproducible results validation