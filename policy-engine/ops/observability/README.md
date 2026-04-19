# Observability

Canonical observability-as-code home for runtime and Data Forge operations.

Target layout:

```text
observability/
|-- grafana/
|-- prometheus/
|-- otel/
`-- slo/
```

Existing `ops/grafana/` and `ops/prometheus/` should move here during the ops
topology consolidation phase. OpenTelemetry is the canonical telemetry API;
Prometheus, Grafana, JSONL, and summary files are exporters or views.
