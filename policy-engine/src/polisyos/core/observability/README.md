# Observability — telemetry слой core

`core.observability` объединяет tracing, metrics, structured logging, context propagation, determinism и LLM pricing.

Ключевая особенность: graceful degradation. Если OTel SDK недоступен, API остается рабочим через noop-реализации.

## Состав

```text
observability/
├── config.py         # OTelConfig + env-based settings
├── tracer.py         # tracer/sampler/context helpers
├── decorators.py     # @traced / @traced_method
├── metrics.py        # facade -> metrics_parts
├── metrics_parts.py  # MetricsRegistry + domain record_* methods
├── logs.py           # structured logs + trace correlation
├── propagation.py    # trace context propagation (headers/threads/async)
├── determinism.py    # DeterminismTier parsing
└── pricing.py        # model pricing table + estimate_llm_cost_usd
```

## Быстрый сценарий

```python
from polisyos.core.observability import get_metrics, traced

@traced(phase="EXECUTE", node="simulate")
def run_step() -> None:
    with get_metrics().time_simulation({"node": "simulate"}):
        pass
```

## Важные env-параметры

- `POLISYOS_OTEL_ENABLED`
- `POLISYOS_HPC_OBSERVABILITY_ENABLED`
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `OTEL_EXPORTER_OTLP_PROTOCOL`
- `POLISYOS_OTEL_CONSOLE_EXPORT`
- `POLISYOS_METRICS_PORT`
- `POLISYOS_TRACE_SAMPLING_RATIO`
- `POLISYOS_ALWAYS_SAMPLE_ERRORS`
- `POLISYOS_DETERMINISM_TIER`
- `POLISYOS_LLM_DEFAULT_INPUT_USD` / `POLISYOS_LLM_DEFAULT_OUTPUT_USD`

## Интеграции

- `core.llm`: LLM call metrics/traces/cost
- `core.resilience`: retry telemetry
- `core.security`: authz/audit/TEE/SBOM security metrics
- `foundry`/`scientist`/`runtime`: execution traces и SLO/operational метрики
