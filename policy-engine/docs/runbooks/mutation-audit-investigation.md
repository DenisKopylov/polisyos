# Mutation Audit Investigation

Related reference: [Logging and Trace Context](../reference/logging.md),
[Platform Architecture Diagrams](../reference/operations/platform-architecture-diagrams.md).

> Use this runbook when an operator, reviewer, or incident commander needs to
> answer "who changed what, when, and under which request context" for runtime
> mutations.

Owner: `@runtime-owners`
Last tested: `2026-04-17` against audit-chain evidence and current compliance-review docs.
Evidence path: `docs/reference/security-compliance.md`; `docs/archive/reports/core-runtime-closeout.md`; `tests/core/security/test_audit_chain.py`
Rollback path: preserve original audit evidence, separate remediation from historical records, and record any corrective mutation as a new audited action.

## Symptom

- a run, job, or decision-validity event exists and its origin is unclear;
- compliance review requests actor/tenant attribution for a mutation;
- an incident timeline needs proof of whether a write succeeded, replayed, or
  was denied.

## Likely Causes

- mutation succeeded through the normal control path;
- the request was replayed via `X-Idempotency-Key`;
- operator flow performed a corrective action after an earlier failure;
- multiple requests touched the same resource and need correlation.

## Timeline Capture Expectations

- resource IDs involved;
- `request_id` and `tenant_id`;
- actor identity;
- endpoint and operation name;
- before/after hash when present;
- related run/job/artifact references.

## First Triage Steps

1. Start with the mutation audit stream under the runtime root:
   `runtime/audit/mutations.jsonl`.
2. Filter by one of:

   - `request_id`;
   - `resource_ids`;
   - actor;
   - `tenant_id`;
   - `idempotency_key`.
3. Correlate the selected mutation entry with:

   - structured logs;
   - trace spans;
   - control-plane job or run state.
4. If the mutation created downstream artifacts, use the artifact or run ID to
   continue the chain through data-access audit or lineage views.

## Rollback / Mitigation

- preserve the original audit lines before any corrective action;
- if the investigation becomes a remediation, record the operator remediation as
  a new separate action rather than editing history;

- do not copy raw backend diagnostics into customer-facing tickets without
  sanitization.

## Escalation Owner

- primary: `@runtime-owners`
- compliance/security support when tenant or access concerns are involved

## Follow-up Checklist

- confirm the incident ticket links to the actual request and resource IDs;
- note whether audit data alone was sufficient or whether logs/traces were also
  required;

- update the audit schema documentation if a necessary field was missing.

## Blameless Postmortem

### What Went Well

- which fields gave the fastest correlation to the responsible mutation;
- whether the audit trail made replay vs original success obvious.

### What Went Poorly

- where operators needed chat or tribal memory to interpret audit rows;
- whether missing resource IDs or hashes slowed the investigation.

### Action Items

| Action item                                          | Owner              | Due date   | Status |
| ---------------------------------------------------- | ------------------ | ---------- | ------ |
| Add missing correlation field or audit documentation | `@runtime-owners`  | YYYY-MM-DD | open   |
| Improve operator tooling for audit search/export     | `@platform-owners` | YYYY-MM-DD | open   |
