# Broken Contract Generation

Related how-to: [Manage Schemas](../how-to/manage-schemas.md). Related reference:
[Schemas](../reference/schemas.md), [REST API](../reference/api/index.md).

> Use this runbook when contract freshness or generation paths
> diverge across the backend, committed snapshots, OpenAPI, and frontend fixtures.

Owner: `@platform-owners`
Historical validation receipt (as recorded by this page): `2026-04-17` — schema, OpenAPI, frontend-contract, and docs-build checks available at that time; this is not a fresh validation.
Evidence path: `docs/reference/quality-gates.md`; `schemas/runtime_api_v1.openapi.json`; `docs/archive/reports/platform-acceptance.md`
Rollback path: revert the unintended contract change or regenerate all affected artifacts and docs in one change set before promotion.

## Symptom

- `uv run --extra ml python tools/quality/diagnostics/gen_schema.py --check` fails;
- `uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py` reports drift;
- `corepack pnpm --filter @polisyos/runtime-dashboard run contracts:verify`
  fails;
- `mkdocs build --strict` or documentation pages refer to a stale API shape;
- CI reports failures in ABI, OpenAPI, or frontend contracts after a seemingly innocent change.

## Likely Causes

- A Pydantic contract, route response, schema model, or generated client changed,
  but committed artifacts were not updated;

- A backend route and frontend fixture were changed independently;
- The OpenAPI or schema snapshots were generated from a stale workspace;
- A runtime contract change was made without updating the docs/reference surface;
- An apparently additive change actually violated compatibility policy.

## Timeline Capture Expectations

Record:

- The failing command and exact message;
- The commit SHA, authoring area, and changed files;
- Which authoritative source is the source of truth:
  Python models, runtime routes, generated frontend fixtures, or schema
  snapshots;

- Which snapshot or file first showed drift;
- Whether the change was already published in the docs or included in a release candidate.

## First Triage Steps

1. Run all three canonical checks separately:

   ```bash
   cd policy-engine
   uv run --extra ml python tools/quality/diagnostics/gen_schema.py --check
   uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
   corepack pnpm --filter @polisyos/runtime-dashboard run contracts:verify
   ```

2. Distinguish source drift from generated-artifact drift:

   - If only the schema check fails, inspect `schemas/snapshots/**`;
   - If only the runtime API check fails, inspect `runtime/http` and the committed
     OpenAPI snapshot;
   - If the frontend contract path fails, inspect the runtime client and fixtures, plus
     dashboard expectations.

3. Check the documentation surface:

   ```bash
   cd policy-engine
   uv run --extra docs python -m mkdocs build --strict
   ```

4. If the change is intentional, regenerate artifacts through the canonical path and confirm
   that the diff is expected and contains no unrelated changes.

## Rollback / Mitigation

- If the drift is unintended, revert the contract-affecting change to the last
  green SHA;

- If the change is intentional, do not merge it without regenerated artifacts and documentation
  updates in the same change set;

- If the frontend and backend diverged, hold deployment temporarily until
  both sides are aligned;

- If compatibility was broken, start an ADR or contract review instead of
  silently forcing a refresh.

## Escalation Owner

- primary: `@platform-owners`;
- Supporting: the owner of the changed boundary surface
  (`@runtime-owners`, `@frontend-owners`, `@ir-owners`, `@core-owners`).

## Follow-up Checklist

- The authoritative source for each drifted artifact was identified;
- Regenerated artifacts were included in the same change set;
- Reference or how-to docs were updated if the behavior surface changed;
- A test or gate that would have caught this drift was added;
- The compatibility narrative was updated for a breaking change.

## Blameless Postmortem

### What Went Well

- Which freshness check first revealed the issue;
- What helped distinguish an intentional change from accidental drift quickly;
- Where the source of truth was unambiguous.

### What Went Poorly

- Where ownership boundaries were blurred;
- Which contract surface was too implicit;
- Why documentation or client drift went undetected for so long.

### Action Items

| Action item                                                       | Owner              | Due date   | Status |
| ----------------------------------------------------------------- | ------------------ | ---------- | ------ |
| Add a stronger freshness gate for the missed drift pattern        | `@platform-owners` | YYYY-MM-DD | open   |
| Update docs and generation instructions for the affected boundary | affected owner     | YYYY-MM-DD | open   |
| Tighten compatibility review for the contract family if needed    | `@platform-owners` | YYYY-MM-DD | open   |
