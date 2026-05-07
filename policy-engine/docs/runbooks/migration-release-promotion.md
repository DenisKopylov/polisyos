# Migration Release Promotion

Related contracts: `ops/migrations/migration-contracts.toml`,
`ops/release/deployment-topology.toml`, and
`ops/release/promotion-gates.toml`.

Owner: `@platform-owners`
Last tested: `2026-05-06` against Phase 5.6 migration and release topology contracts.
Evidence path: release candidate evidence bundle plus the owning migration class README under `ops/migrations/`.
Rollback path: hold promotion, keep the previous artifact/config pair active, and use the affected surface runbook for recovery.

## Symptom

- a release candidate changes DB schema, runtime-state format, API schema
  including Runtime API/OpenAPI, IR schema, or persisted artifact schema;
- staging promotion is blocked by a migration review gate;
- production promotion needs operator action that is not yet documented;
- a migration helper exists, but the owning operational contract does not name
  its class, release gate, or rollback expectations.

## Likely Causes

- migration implementation landed without updating `ops/migrations/**`;
- OpenAPI, generated client, or IR snapshot changed without compatibility
  classification;
- runtime-state cleanup or reader behavior changed without N-1/read/export
  guidance;
- persisted artifacts require a helper run, but release evidence does not tell
  operators when and how to run it.

## Timeline Capture Expectations

Record:

- release candidate version, commit SHA, and artifact IDs;
- affected migration class: `db`, `runtime_state`, `api_schemas`, or `ir`;
- compatibility classification: additive, compatible-breaking, or breaking;
- exact helper command, dry-run output location, and owner approval;
- rollback or hold decision with UTC timestamp.

## First Triage Steps

1. Identify the changed migration class in
   `ops/migrations/migration-contracts.toml`.
2. Confirm the class README exists and describes operator checks for the changed
   surface.
3. Confirm the relevant gate in `ops/release/promotion-gates.toml` names the
   required evidence.
4. For Python helpers, confirm the `helper_binding` entry maps the CLI artifact
   to the migration class and contract path.
5. If the change is breaking, stop promotion until release notes,
   migration-guide material, and this runbook cover the operator action.

## Rollback / Mitigation

- Hold promotion before applying a breaking migration to production.
- Keep the previous artifact/config pair live until dry-run evidence and owner
  approval are present.
- For DB changes, do not run rollback SQL unless `db/README.md` and the release
  incident owner both classify it as emergency rollback.
- For runtime-state changes, prefer export/dual-read compatibility over
  destructive cleanup.
- For API and IR schema changes, roll back generated clients/snapshots together
  with the code that produced them.

## Escalation Owner

- primary: `@platform-owners`;
- DB: `@platform-owners`;
- runtime-state and Runtime API: `@runtime-owners`;
- IR: `@ir-owners`;
- persisted artifacts/data-plane: affected component owner joins the review.

## Follow-up Checklist

- owning `ops/migrations/<class>/README.md` updated;
- `helper_binding` updated for any Python migration helper;
- release notes include migration and compatibility notes;
- migration-guide or schema docs explain consumer/operator action;
- promotion gate evidence links to dry-run, backup, or compatibility fixture
  output;
- post-release cleanup date and owner are recorded when temporary dual-read
  behavior is introduced.
