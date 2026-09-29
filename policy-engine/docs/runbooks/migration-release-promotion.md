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
- For API/OpenAPI generated clients and IR schema snapshots, roll back those
  generated surfaces together with the code that produced them. This applies
  to generated clients and snapshots; it does not authorize rewriting
  persisted artifact bytes. Follow the owning migration-class README for
  persisted-artifact recovery.

### B111 Scientist frontier artifact v3

For `PolicyFrontierReport` and `RejectedAlternativesSummary`, follow the
[IR migration guidance](../../ops/migrations/ir/README.md#scientist-frontier-artifact-v3).
The migration-class name `ir` and release-fragment value
`persisted-artifact-format` are separate vocabularies for this change. Schema
v2 was unissued and is rejected; the supported persisted dialects are v1 and
v3, with v1 historical bytes replayed exactly.

Before the first v3 write, hold deployment until every consumer is confirmed
v1/v3-capable. Use a reader-only compatible release or a coordinated no-write
interval before deploying the v3 writer; this slice has no separate
writer-disable switch. If that sequence cannot be established, hold release.
After v3 bytes exist, do not downgrade any consumer to a strict v1-only reader.
Keep v1/v3-capable readers available and repair forward, or hold affected
consumers until compatibility is restored. Do not delete, rewrite, restamp, or
reissue v3 or historical artifacts as a rollback substitute.

The v3 DTO validator can check independently supplied source/unknown
identities, but the ordinary `PolicyArtifactBuilder._build_frontier_report`
path copies the registry projection into the source field and supplies no
independent unknown set. That self-derived equality is not a served
source-population reconciliation and cannot detect candidates omitted before
registry projection. The external candidate-universe and deployed
artifact/reader inventories are not established.

The `ir_migration_review` contract has not accepted B111's no-rewrite
compatibility path or resolved its IR-only operator-doc requirements for these
Scientist DTOs. **Promotion remains held** until the migration owners accept
the no-rewrite evidence contract and the required owner-bound inventory and
compatibility evidence are recorded. A tracked-tree census or this
documentation does not establish deployed-store contents or reader versions.

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
