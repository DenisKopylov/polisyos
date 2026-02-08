# Observability — Телеметрия и мониторинг

Production-grade телеметрия: OpenTelemetry трассировка, Prometheus метрики, структурированное логирование, determinism tiers, LLM cost estimation. Graceful degradation при недоступности OTel.

## Архитектура

```
observability/
├── config.py          # OTelConfig, ResourceConfig, env-based конфигурация
├── tracer.py          # PolicyOSTracer singleton, get_tracer()
├── decorators.py      # @traced, @traced_method — автоматическая трассировка
├── logs.py            # TraceContextFilter, StructuredFormatter (JSON с trace correlation)
├── metrics.py         # MetricsRegistry — Prometheus метрики (CAS, fabric, foundry, scientist, LLM)
├── propagation.py     # Context propagation через thread/async границы
├── determinism.py     # DeterminismTier — уровни гарантий детерминизма симуляций
└── pricing.py         # LLM cost estimation (GPT-4o, Gemini Pro, configurable defaults)
```

## Быстрый старт

```python
from polisyos.core.observability import get_tracer, get_metrics, traced

@traced(phase="EXECUTE", node="run_sim")
def run_simulation():
    with get_metrics().time_simulation({"node": "run_sim"}):
        pass
```

## Конфигурация

| Переменная | Назначение | По умолчанию |
|------------|------------|--------------|
| `POLISYOS_OTEL_ENABLED` | Включение OTel | `false` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP gRPC/HTTP endpoint | — |
| `POLISYOS_METRICS_PORT` | Prometheus HTTP порт | `9464` |
| `POLISYOS_TRACE_SAMPLING_RATIO` | Сэмплирование трейсов | `1.0` |
| `POLISYOS_HPC_OBSERVABILITY_ENABLED` | HPC метрики для CAS | `false` |
| `POLISYOS_DETERMINISM_TIER` | Уровень детерминизма | — |
| `POLISYOS_LLM_DEFAULT_INPUT_USD` | Override цены input токенов | — |
| `POLISYOS_LLM_DEFAULT_OUTPUT_USD` | Override цены output токенов | — |

## Компоненты

### Tracing

- `PolicyOSTracer` — singleton OTel tracer, `get_tracer()` для доступа
- `@traced(phase="...", node="...")` / `@traced_method` — декораторы для автоматической трассировки функций/методов
- `get_current_trace_context()` — текущий trace context для propagation

### Metrics

`MetricsRegistry` — центральный реестр Prometheus-метрик по категориям:
- CAS: операции, I/O размеры, кеш-хиты
- Fabric: обработка данных
- Foundry: JAX runtime, калибровка
- Scientist: workflow nodes, governance pipeline
- LLM: вызовы, токены, стоимость
- Security/Cell isolation: routing latency/failures, incidents, tenants-per-cell

### Structured Logging

- `TraceContextFilter` — добавляет trace_id/span_id в log records
- `StructuredFormatter` — JSON-формат для ELK, Loki, CloudWatch
- `configure_otel_logging_handler()` — автоматическая настройка

### Context Propagation

- `TracedExecutorWrapper` — propagation через thread pools
- `inject_headers()` / `extract_headers()` — W3C trace context для HTTP
- `with_trace_context` — async decorator для propagation в asyncio

### Determinism Tiers

`DeterminismTier` — уровни гарантий воспроизводимости симуляций:

| Tier | Описание | GPU | Exact reproducible |
|------|----------|-----|-------------------|
| `STRICT_CPU` | Bit-for-bit на одной CPU-архитектуре | нет | да |
| `LIBRARY_DETERMINISTIC` | Deterministic ops в библиотеках | нет | да |
| `BEST_EFFORT_GPU` | Near-deterministic на одной GPU-модели | да | нет |
| `STATISTICAL` | CI-bounded воспроизводимость | да | нет |
| `NONDETERMINISTIC` | Без гарантий | да | нет |

```python
from polisyos.core.observability.determinism import DeterminismTier, get_determinism_tier

tier = get_determinism_tier()  # из POLISYOS_DETERMINISM_TIER
if tier and tier.requires_deterministic_ops():
    use_deterministic_algorithms()
```

### LLM Pricing

Оценка стоимости LLM-вызовов для бюджетирования в Scientist.

```python
from polisyos.core.observability.pricing import estimate_llm_cost_usd, pricing_table

cost = estimate_llm_cost_usd(model="gpt-4o", prompt_tokens=1000, completion_tokens=500)
```

Дефолтные цены: gpt-4o ($2.5e-6 input, $10e-6 output), gemini-pro ($1e-6, $4e-6). Переопределяемы через env.

## Экспортеры

- **OTLP**: gRPC/HTTP → Jaeger, Tempo, DataDog
- **Prometheus**: HTTP на порту 9464
- **Console**: stdout для отладки
- **Structured Logging**: JSON → ELK, Loki, CloudWatch

## Graceful Degradation

При отсутствии OTel SDK модуль предоставляет noop-реализации — `get_tracer()`, `get_metrics()`, `@traced` работают без ошибок, просто не экспортируют данные.
