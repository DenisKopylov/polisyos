# Observability — telemetry слой core

`core.observability` объединяет tracing, metrics, structured logging, propagation и cost/determinism utilities.
Модуль сделан с graceful degradation: при отсутствии OTel SDK экспорт становится noop, но API остается стабильным.

## Состав

```text
observability/
├── config.py          # OTelConfig + env-based runtime config
├── tracer.py          # tracer singleton + trace context
├── decorators.py      # @traced / @traced_method
├── metrics.py         # MetricsRegistry (Prometheus/OTel)
├── metrics_parts.py   # доменные группы метрик
├── logs.py            # structured logging + trace correlation
├── propagation.py     # context propagation (threads/async/http headers)
├── determinism.py     # DeterminismTier
└── pricing.py         # LLM pricing + cost estimation helpers
```

## Быстрый старт

```python
from polisyos.core.observability import get_metrics, traced

@traced(phase="EXECUTE", node="simulate")
def run_step() -> None:
    with get_metrics().time_simulation({"node": "simulate"}):
        pass
```

## Важные env-параметры

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `POLISYOS_OTEL_ENABLED` | `true` | глобальный toggle OTel |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | endpoint экспортера |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `grpc` | протокол OTLP |
| `POLISYOS_OTEL_CONSOLE_EXPORT` | `false` | console export для отладки |
| `POLISYOS_METRICS_PORT` | `9464` | порт Prometheus exporter |
| `POLISYOS_TRACE_SAMPLING_RATIO` | `1.0` | sampling ratio |
| `POLISYOS_ALWAYS_SAMPLE_ERRORS` | `true` | best-effort sample error spans |
| `POLISYOS_HPC_OBSERVABILITY_ENABLED` | `true` | расширенные CAS/runtime метрики |
| `POLISYOS_DETERMINISM_TIER` | — | `strict_cpu`, `library_deterministic`, `best_effort_gpu`, `statistical`, `nondeterministic` |
| `POLISYOS_LLM_DEFAULT_INPUT_USD` / `POLISYOS_LLM_DEFAULT_OUTPUT_USD` | — | override default LLM pricing |

## Что используется в системе

- `foundry`, `scientist`, `runtime`, `security` пишут span/metrics через общий API.
- `core.resilience` и `core.llm` используют метрики/трейсинг для retry/LLM вызовов.
- `security` дополняет реестр метрик событиями authz, audit chain, TEE, SBOM.

## Determinism tiers

`DeterminismTier` определяет гарантию воспроизводимости симуляции:

- `STRICT_CPU`
- `LIBRARY_DETERMINISTIC`
- `BEST_EFFORT_GPU`
- `STATISTICAL`
- `NONDETERMINISTIC`

## LLM pricing

`pricing.py` и `core.llm.cost` дают единый способ оценивать стоимость токенов для budget-aware workflow.
