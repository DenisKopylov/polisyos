# ADR-0116: OTel-First Observability

## Status

Proposed

## Date

2026-04-18

## Context

Data Forge and runtime workflows currently discuss multiple telemetry sinks:
JSONL, Prometheus, OpenTelemetry, and summary files. SOTA practice is to make
OpenTelemetry the canonical trace/metrics/logs API and treat files as exporters
or fallbacks.

## Decision

Make OpenTelemetry first-class:

1. Stages, materializers, LLM calls, retries, and snapshot commits propagate W3C
   trace context.
2. `trace_id` and `span_id` are recorded in stage manifests, lineage records,
   and ArtifactRefs.
3. Prometheus textfile, JSONL, and summaries are exporters from OTel state.
4. SLOs live under `ops/observability/slo/`.

## Consequences

- Artifacts can be connected to traces and logs.
- Local/offline workflows still get file exporters.
- Observability configuration becomes code-reviewed alongside the system.

## Related Decisions

- Extends: ADR-0006 (SLO definitions for Scientist DAG), ADR-0101 (runtime
  audit trail model).

- Related: ADR-0122 (lakehouse snapshots), ADR-0123 (ArtifactRef governance).
