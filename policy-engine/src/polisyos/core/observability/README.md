# Observability

This package provides OpenTelemetry-based tracing, metrics, and log correlation for PolicyOS.

## Quick start

```python
from polisyos.core.observability import get_tracer, get_metrics, traced

tracer = get_tracer()
metrics = get_metrics()

@traced(phase="EXECUTE", node="run_sim")
def run_simulation():
    with metrics.time_simulation({"node": "run_sim"}):
        ...
```

## Environment variables

- `POLISYOS_OTEL_ENABLED` (default: `true`)
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `OTEL_EXPORTER_OTLP_PROTOCOL` (`grpc` or `http/protobuf`)
- `POLISYOS_OTEL_CONSOLE_EXPORT` (default: `false`)
- `POLISYOS_METRICS_PORT` (default: `9464`)

## Phase 2 instrumentation

- Scientist flow nodes are instrumented with span attributes derived from `ExperimentState`.
- LLM calls are wrapped by `TracedLLMClient` to capture token usage and status.
- Governance pipeline spans each validation pass and records issue metrics.
- The Scientist entrypoint (`run_experiment`) creates the workflow root span.
