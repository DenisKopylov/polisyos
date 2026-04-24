# CAS or OPA Outage

Related reference: [Platform Architecture Diagrams](../reference/operations/platform-architecture-diagrams.md),
[Observability Topology](../reference/operations/observability-topology.md).

> Use this runbook when runtime starts returning storage/integrity failures or
> fail-closed authorization errors caused by degraded CAS or OPA dependencies.

Owner: `@runtime-owners`
Last tested: `2026-04-17` against runtime authz and resilience checks referenced below.
Evidence path: `docs/archive/reports/core-runtime-closeout.md`; `tests/runtime/http/test_runtime_api_authz.py`; `tests/runtime/http/test_resilience_guards.py`
Rollback path: keep authz fail-closed, move to read-only or reduced-write mode, and restore the last known-good CAS or OPA dependency state without bypassing integrity checks.

## Operational Metadata

| Field              | Value                                                                                                                                          |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Primary owner      | `@runtime-owners`                                                                                                                              |
| Coordination owner | `@platform-owners`                                                                                                                             |
| Security owner     | security/compliance owner when OPA, trust stores, or identity are involved                                                                     |
| Last tested        | 2026-04-17, D1-L1 documentation validation pass                                                                                                |
| Evidence anchors   | `tests/runtime/http/test_runtime_api_authz.py`, `tests/runtime/http/test_control_hardening.py`, `tests/runtime/http/test_resilience_guards.py` |
| Rollback posture   | keep authz fail-closed, move to read-only or reduced-write mode, never bypass integrity verification to restore traffic                        |

## Symptom

- read paths return `503`, `504`, or typed integrity errors;
- write paths fail before durable side effects complete;
- authz starts denying previously healthy traffic because OPA is unavailable or
  its circuit breaker is open;

- `/ready` returns `degraded` and dependency state points to storage/authz
  degradation.

## Likely Causes

- CAS filesystem or object-store backend outage;
- OPA sidecar or policy bundle unavailable;
- dependency timeout or open circuit breaker after repeated failures;
- corrupted artifact blob detected during read-time verification;
- credentials, trust-store, or network regression in a storage/authz path.

## Timeline Capture Expectations

- first failing `request_id`, `trace_id`, and endpoint;
- affected tenant or blast radius statement;
- whether failures are storage, integrity, or authz related;
- `/ready` payload at detection time;
- last deploy/config change within the previous 60 minutes.

## First Triage Steps

1. Confirm health state:

   ```bash
   curl -s http://localhost:8000/ready | jq
   curl -s http://localhost:8000/api/v1/health | jq
   ```

2. Check one known-good read and one authz-protected path with the same token.
3. Determine whether the failing branch is:

   - CAS availability;
   - integrity mismatch;
   - OPA reachability/policy decision shape.
4. Inspect runtime logs and traces by `request_id` rather than by time range
   only.
5. If artifact corruption is suspected, preserve the artifact ID and stop any
   cleanup job that could destroy evidence.

## Rollback / Mitigation

- if OPA is the only failing dependency, keep fail-closed authz posture and
  reduce blast radius by pausing sensitive write workloads rather than bypassing
  policy silently;

- if CAS is degraded, move runtime to read-only or reduced-write posture until
  durability is trustworthy again;

- rollback recent config/credential changes before changing code paths;
- do not disable integrity verification to "get traffic through";
- open the dedicated corruption or key-rotation runbook if the problem is not a
  simple availability outage.

## Escalation Owner

- primary: `@runtime-owners`
- supporting: `@platform-owners`
- security support when OPA/trust-store/identity is involved

## Follow-up Checklist

- confirm whether circuit breakers need retuning or only dependency recovery;
- preserve one failing example with request/tenant/resource context;
- update dependency dashboards or alerts if the outage was discovered manually;
- capture whether read-only mode or write pause was required.

## Blameless Postmortem

### What Went Well

- which signal separated CAS outage from authz outage quickly;
- whether circuit breakers prevented thread or worker exhaustion.

### What Went Poorly

- where dependency state was visible only in logs and not in health/metrics;
- whether operators were tempted to bypass fail-closed security behavior.

### Action Items

| Action item                                                           | Owner              | Due date   | Status |
| --------------------------------------------------------------------- | ------------------ | ---------- | ------ |
| Improve dependency-specific dashboard or alert for the failing branch | `@platform-owners` | YYYY-MM-DD | open   |
| Close the storage/authz reliability gap that caused the outage        | affected owner     | YYYY-MM-DD | open   |
