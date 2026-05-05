# Idempotency Incident

Related reference: [Runtime API Migration Guide](../reference/api/migration-guide.md),
[Platform Changelog](../reference/changelog.md).

> Use this runbook when retries create apparent duplicate work, or when
> `X-Idempotency-Key` entries become stuck, mismatched, or operationally
> confusing.

Owner: `@runtime-owners`
Last tested: `2026-04-17` against runtime write-path hardening and mutation-policy checks.
Evidence path: `docs/archive/reports/core-runtime-closeout.md`; `tests/unit/runtime/http/test_runtime_api_write_path_hardening.py`; `src/polisyos/runtime/http/mutation_policy.py`
Rollback path: stop retries, identify the authoritative mutation result, and clean up duplicates only as an audited corrective action.

## Operational Metadata

| Field              | Value                                                                                                         |
| ------------------ | ------------------------------------------------------------------------------------------------------------- |
| Primary owner      | `@runtime-owners`                                                                                             |
| Coordination owner | `@platform-owners`                                                                                            |
| Last tested        | 2026-04-17, D1-L1 documentation validation pass                                                               |
| Evidence anchors   | `tests/unit/runtime/http/test_runtime_api_write_path_hardening.py`, `src/polisyos/runtime/http/mutation_policy.py` |
| Rollback posture   | stop retries, identify the authoritative result, then handle duplicate cleanup as an audited operator action  |

## Symptom

- a client reports duplicate run/job creation after retry;
- runtime returns `idempotency_request_in_progress` or
  `idempotency_key_reused`;

- operators see a mutation audit entry but no corresponding completed result;
- a client keeps retrying and receives inconsistent replay behavior.

## Likely Causes

- the client reused one idempotency key with a different payload;
- a request failed after side effects started but before replay state was
  finalized;

- the same logical mutation was retried without preserving the original key;
- an operator is comparing cross-tenant or cross-endpoint events as if they were
  one idempotency namespace.

## Timeline Capture Expectations

- `request_id`
- `tenant_id`
- endpoint and HTTP method
- `X-Idempotency-Key`
- request hash or payload identity
- resulting run/job/resource IDs

## First Triage Steps

1. Pull the mutation audit entries for the affected time window and key.
2. Verify tenant, method, route, and payload are actually the same logical
   operation.
3. Check whether the incident is:

   - correct replay of a prior success;
   - key mismatch;
   - pending/in-flight state;
   - true duplicate side effect.
4. Confirm whether the underlying resource already exists before clearing or
   replaying anything manually.

## Rollback / Mitigation

- stop blind client retries until the first authoritative result is identified;
- if the request truly succeeded, return the original result path to the client
  and keep the recorded replay state;

- if the request is genuinely stuck in pending state, clear it only after
  verifying there is no active worker still processing the same logical action;

- if a duplicate run/job already exists, treat cleanup as a separate audited
  operator action rather than as a silent file deletion.

## Escalation Owner

- primary: `@runtime-owners`
- supporting: `@platform-owners`

## Follow-up Checklist

- document whether the root cause was client misuse, persistence failure, or
  server-side race;

- add or update regression tests for the exact replay edge case;
- update client guidance if the failure came from ambiguous retry behavior.

## Blameless Postmortem

### What Went Well

- which signal proved the authoritative result quickly;
- whether audit entries were sufficient without direct database/file inspection.

### What Went Poorly

- whether pending replay state lacked enough visibility;
- whether operators had to infer identity from raw payloads rather than from
  audit metadata.

### Action Items

| Action item                                                 | Owner              | Due date   | Status |
| ----------------------------------------------------------- | ------------------ | ---------- | ------ |
| Add regression coverage for the reproduced replay edge case | `@runtime-owners`  | YYYY-MM-DD | open   |
| Improve audit or client guidance for idempotency handling   | `@platform-owners` | YYYY-MM-DD | open   |
