# Performance Tests

Валидация производительности и обнаружение регрессий в ключевых компонентах Policy Engine.

**Последнее обновление:** 1 февраля 2026
**Уровень:** Performance Validation (Phase 3 + Regression Detection)
**Зависимости:** JAX, NumPy, Core Observability, Foundry Runtime

## Архитектурный контекст

Performance тесты обеспечивают что система обсервабилити не создает значительного overhead. Валидируют SLA для workloads: simulation (<2%), CAS I/O (<5%), calibration (<3%). Включают automated regression detection в CI/CD.

## Структура тестов

```
performance/
└── test_overhead.py          # Overhead валидация + regression detection (simulation, CAS I/O, calibration)
```

## Категории тестов

### Overhead Validation (`test_overhead.py`)

**Цель:** Измерение overhead системы обсервабилити и обнаружение регрессий.

**Ключевые тесты:** Simulation overhead (<2%), CAS I/O overhead (<5%), calibration overhead (<3%), statistical benchmarking, regression detection.

**Принципы:** Acceptable thresholds, statistical reliability, reproducible benchmarks, warmup phases, cross-platform consistency.

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

# Regression detection
pytest tests/performance/test_overhead.py::TestRegressionDetection -v
```

### CI Benchmarking & Regression Detection

Для regression сравнения используется `pytest-benchmark` в том же файле:

```bash
pytest tests/performance/test_overhead.py \
  --benchmark-only \
  --benchmark-json=current.json \
  --benchmark-warmup=on \
  --benchmark-min-rounds=10
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

**Tools & Diagnostics** (`tools/`):
- **Performance Regression**: Automated detection с check_perf_regression.py
- **CI/CD Integration**: GitHub Actions workflows для continuous monitoring

### Архитектурные инварианты

- **Закон Q**: Performance SLA (overhead thresholds enforced)
- **Закон R**: Regression Detection (automated performance monitoring в CI/CD)
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
- **Regression Detection**: Automated performance monitoring workflows
- **Historical Tracking**: Performance regression detection с GitHub Actions
- **Environment Consistency**: Reproducible results validation
