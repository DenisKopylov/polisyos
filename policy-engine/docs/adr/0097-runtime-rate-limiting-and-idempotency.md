# ADR-0097: Runtime Rate Limiting and Idempotency

## Status
Accepted

## Date
2026-04-12

## Context

Runtime write paths create durable side effects: runs, jobs, reissue events,
feedback evaluation, and related artifact/audit records. Before the hardening
work, retries from clients, proxies, or operators could create duplicate work,
and hot endpoints had no consistent per-tenant backpressure policy.

Phase WS-0B introduced write-path protection, but the behavior must now be part
of the platform contract rather than an implementation detail hidden in
middleware.

## Decision

1. Runtime mutation paths are protected at the HTTP perimeter by one shared
   policy layer that applies:
   - per-tenant and per-endpoint rate limiting for expensive `POST` control
     paths;
   - concurrent plus request-budget limits for live-stream endpoints;
   - idempotency replay for side-effecting `POST` routes.
2. `X-Idempotency-Key` is the canonical replay key for supported mutation
   routes. Scope is:
   - tenant;
   - HTTP method;
   - normalized route path;
   - request payload hash.
3. Reusing the same key with the same payload returns the original successful
   response. Reusing the same key with a different payload is rejected.
4. A key currently in flight is treated as busy rather than as permission to
   launch duplicate work.
5. Rate-limit and idempotency decisions are recorded in audit/telemetry with
   `request_id`, `tenant_id`, endpoint, outcome, and key metadata where
   applicable.
6. The policy is fail-closed for conflicting or ambiguous replay states:
   - mismatched request hash;
   - dependency or persistence failure while finalizing replay state;
   - live-stream concurrency over budget.
7. Clients remain responsible for bounded retry behavior. The server guarantees
   duplicate suppression, not infinite request retention.

## Consequences

### Positive

- Duplicate run/job creation is no longer the default failure mode for retries.
- Operators get one place to inspect throttle, replay, and mutation audit
  outcomes.
- Tenant fairness is enforced close to the perimeter instead of being left to
  downstream workers.

### Negative

- Clients must preserve and reuse idempotency keys intentionally.
- Incident response must now consider replay-state persistence as part of the
  control-plane contract.
- Rate-limit tuning becomes an explicit operational responsibility rather than a
  hidden runtime constant.
