# ADR-0101: Runtime Audit Trail Model

## Status
Accepted

## Date
2026-04-12

## Context

Runtime now enforces stronger tenant isolation, write-path idempotency, and
read-time integrity checks. Those controls are incomplete for operators and
compliance reviewers unless the platform can answer:

- who invoked the action;
- under which tenant and request context;
- what resource was read or changed;
- whether the action succeeded, was throttled, was replayed, or was denied.

WS-1D and WS-0B introduced append-only runtime access and mutation audit trails.
This ADR defines the canonical model.

## Decision

1. Runtime audit is split into two append-only streams under the runtime root:
   - mutation audit for state-changing HTTP paths;
   - data-access audit for read/download/preview paths.
2. Mutation audit records include, at minimum:
   - timestamp;
   - `request_id`;
   - `tenant_id`;
   - actor identity;
   - HTTP method and endpoint;
   - logical operation;
   - outcome and status code;
   - affected resource IDs;
   - request hash;
   - before/after hash when applicable;
   - idempotency key when present.
3. Data-access audit records include, at minimum:
   - timestamp;
   - `request_id`;
   - `tenant_id`;
   - actor identity;
   - HTTP method and endpoint;
   - resource kind and resource ID;
   - outcome;
   - route-specific metadata.
4. Audit entries must be correlation-friendly with logs, traces, and metrics via
   `request_id` and tenant/actor context.
5. Audit payloads are operator-facing artifacts, not public API responses. They
   must avoid secret material, raw credentials, and backend-specific sensitive
   diagnostics.

## Consequences

### Positive

- Compliance review no longer depends on reconstructing history from raw logs.
- Incident response has one correlation model for reads, writes, and replay
  behavior.
- Tenant and actor attribution become first-class operating data.

### Negative

- Audit persistence is now part of runtime operational state and must be covered
  by retention and recovery policy.
- Debugging tools must respect the distinction between operator-facing audit
  data and public client-facing responses.
