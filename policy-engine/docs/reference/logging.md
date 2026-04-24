# Logging and Trace Context

Related reference: [Configuration Environment Registry](configuration-env-registry.md),
[Observability Topology](operations/observability-topology.md).

Owner: `@platform-owners`
Source of truth: `src/polisyos/common/config.py`, `src/polisyos/common/logger.py`, and `src/polisyos/core/observability/{logs,tracer}.py`

> Logging in PolicyOS is explicitly bootstrapped. Importing a library module
> should not mutate global process logging behavior.

## Bootstrap Model

- process-wide logging configuration is applied through
  `polisyos.common.config.apply_process_bootstrap()`;

- `polisyos.common.logger` is safe to import from library code because it does
  not own sink/bootstrap policy;

- entrypoints decide whether to load `.env`, resolve defaults, and initialize
  JSON/file sinks.

## Trace Context Contract

- log enrichment reads OpenTelemetry trace context at log-call time, not at
  import time;

- when a valid span exists, logs include `trace_id` and `span_id`;
- when no span exists, the logger emits placeholder values rather than crashing
  or reusing stale context.

## Operator-Relevant Fields

When available, operators should expect to correlate by:

- `request_id`
- `trace_id`
- `span_id`
- `tenant_id`
- actor identity
- `run_id`, `artifact_id`, or `job_id`

These identifiers appear across logs, problem responses, traces, and runtime
audit trails.

## Logging Posture

- structured logs are preferred for runtime and operator workflows;
- audit trails are append-only records and are not a substitute for general
  application logging;

- backend/SDK diagnostics included in public HTTP responses must be sanitized,
  but logs may preserve the internal detail needed for incident triage.

## Common Failure Modes

| Symptom                                     | Likely cause                                    | Operator action                                                    |
| ------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------ |
| No structured runtime logs                  | bootstrap not applied in entrypoint             | verify `apply_process_bootstrap()` runs before app startup         |
| Missing `trace_id` on request logs          | no active span or exporter disabled             | inspect tracing startup and exporter health                        |
| Duplicate sinks or repeated log lines       | logging configured more than once               | verify single process bootstrap path                               |
| Logs exist but cannot correlate to requests | client or proxy did not preserve `X-Request-ID` | fix ingress/client propagation and update runbook evidence capture |
