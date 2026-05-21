# ADR-0154: Diagnostic Event Envelope And Runtime Log Contract

## Status

Accepted

## Date

2026-05-14

## Context

The honest diagnostics substrate requires runtime producer events before CAS
artifacts, scorecard gates, readiness closeout, approval, or public artifacts
can claim production authority. The umbrella design already places the
diagnostic event envelope in the must-now substrate, but without an accepted
event contract implementation work would invent local event shapes in the
runtime, canary, scorecard, dashboard, and readiness layers.

PolicyOS needs a stable runtime diagnostic log contract so retries, duplicated
outbox events, stale lease takeover, partial-state recovery, CAS writes, bundle
assembly, scorecard reads, and dashboard projections all join into one causal
flow.

## Decision

1. Every authority-producing, authority-blocking, authority-consuming, or
   authority-projecting serious-run action must emit a diagnostic event or
   reference a diagnostic event emitted by its owner.
2. Runtime diagnostic events use a stable event envelope:
   `event_id`, `event_source`, `event_type`, `event_time`, `event_subject`,
   `schema_name`, `schema_version`, `trace_id`, `span_id`, `parent_span_id`,
   `run_id`, `job_id`, `tenant_id`, `cell_id`, `producer_component`,
   `producer_version`, `execution_profile`, `phase`, `state_before`,
   `state_after`, `payload_ref`, `artifact_refs`, `input_refs`,
   `blocking_status`, `redaction_policy_ref`, and `duplicate_of`.
3. `trace_id` joins runtime logs, CAS writes, progress projections, bundle
   assembly, scorecard gates, readiness closeout, approval packets, dashboard
   projections, and public artifact publication. Serious-run trace context must
   not be sampled away.
4. `event_id` is idempotency identity. Retrying the same action may reuse an
   event id only when the payload and artifact refs are identical. Same event id
   with different payload or refs is an authority collision.
5. Diagnostic events are append-only authority records. Corrective actions emit
   new events that supersede, withdraw, reconcile, or quarantine earlier events.
   They do not mutate historical event meaning.
6. Event payloads may be stored inline only when small and non-sensitive.
   Authority-bearing payloads, redacted payloads, and large payloads are stored
   through CAS and referenced by `payload_ref`.
7. Event types are registry-scoped. At minimum the registry must distinguish
   producer execution, CAS write, ref publication, phase transition, blocker,
   fallback/degradation, schema migration, scorecard gate read, readiness
   closeout, approval decision, dashboard projection, public artifact
   publication, replay result, and reconciliation result.
8. Bundle assembly may emit packaging events, but packaging events do not become
   runtime producer events and cannot upgrade authority.
9. Public or redacted exports may project diagnostic events only through
   redaction policies that preserve event identity, source, type, phase,
   blocker status, and authority role while protecting secrets, hidden answers,
   provider credentials, and sensitive payloads.

## Consequences

Positive:

- Runtime, CAS, scorecard, readiness, approval, dashboard, and bundle evidence
  can be joined by trace and event identity.
- Crash/retry/partial-state investigations gain deterministic reconciliation
  semantics.
- Bundle-created evidence can be classified as packaging/projection rather than
  confused with runtime producer authority.
- Operators can locate the first meaningful event that produced or blocked a
  gate.

Negative:

- Serious runs produce more durable metadata.
- Event type and schema registries must be maintained.
- Privacy and redaction become part of event design, not only export design.
- Existing code paths that only write CAS artifacts or progress fields must
  learn to emit or link diagnostic events.

## Concrete impact

This ADR does not define an implementation plan. It requires future
implementation work to introduce or update:

- diagnostic event envelope schema;
- diagnostic event type registry;
- runtime diagnostic log writer;
- trace propagation through runtime, CAS, progress, canary, scorecard,
  readiness, approval, dashboard, and publication surfaces;
- event-to-CAS reconciliation checks;
- no-sampling policy for serious-run authority events;
- redacted diagnostic event export contract;
- negative tests for duplicated event collisions, event without CAS, CAS
  without event, sampled-away serious event, bundle event pretending to be
  runtime authority, and redaction that removes authority semantics.

## Related Decisions

- Extends: ADR-0097 Runtime Rate Limiting and Idempotency.
- Extends: ADR-0101 Runtime Audit Trail Model.
- Extends: ADR-0116 OTel-First Observability.
- Extends: ADR-0124 LLM Idempotency and Prompt Versioning.
- Related: ADR-0147 Production Evidence Authority Ordering.
- Related: ADR-0148 Serious Run State Machine And Phase Barriers.
- Related: ADR-0149 Effective Mode And Fallback Degradation Ledger.
- Related: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.
- Related: ADR-0151 Evidence Schema Compatibility And Legacy Quarantine.
- Related: ADR-0153 Diagnostic SLOs, Assurance Case, And Attestation.

