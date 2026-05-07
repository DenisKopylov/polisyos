# Observability

- Owner: `team-ops`
- Artifact type: `observability-contracts`

Canonical observability-as-code home for runtime and Data Forge operations.
Component-first bundle drafts live under `ops/components/**`; SLO files in this
directory remain valid type-cut aliases during Wave 6 gate conversion.

Target layout:

```text
observability/
|-- grafana/
|-- prometheus/
|-- otel/
`-- slo/
```

OpenTelemetry is the canonical telemetry API; Prometheus, Grafana, JSONL, and
summary files are exporters or views.

Phase 4 baseline files:

- `otel/baseline.yaml` defines required trace, metric, and log attributes.
- `slo/` keeps owner-tagged SLO source files.
- `../components/<component>/slo.yaml` keeps component-first SLO drafts or
  explicit exceptions that mirror the type-cut SLO source files.
- `prometheus/slo_alerts.yml` and `prometheus/slo_recording_rules.yml`
  are the current alert/rule outputs.
