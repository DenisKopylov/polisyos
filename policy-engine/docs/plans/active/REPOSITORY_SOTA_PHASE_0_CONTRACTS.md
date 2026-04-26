---
title: Repository SOTA Phase 0 Contracts
status: active
owner: team-polisyos
created: 2026-04-24
last_verified: 2026-04-24
stability: snapshot
---

# Repository SOTA Phase 0 Contracts

This is the conservative Phase 0 evidence note for
`REPOSITORY_SOTA_PLAN.md`. Phase 0 is allowed during the Lex production freeze
only when changes are additive and guardrails remain report-only for protected
paths.

## ADR Coverage

The ADR set required by the Repository SOTA plan is present:

| ADR range | Status |
| --------- | ------ |
| ADR-0111 through ADR-0120 | Present |
| ADR-0121 through ADR-0128 | Present |

Repository SOTA Phase 0 depends directly on ADR-0111 through ADR-0120; ADR-0121
through ADR-0128 are already present and support the broader target contracts.

## Machine-Readable Contracts

Existing Phase 0 contracts:

- `architecture/topology.toml`
- `architecture/package_boundaries.toml`
- `architecture/import_contracts.toml`
- `architecture/migration_shims.toml`
- `architecture/complexity_exceptions.toml`
- `architecture/public_surface.toml`
- `architecture/generated_artifacts.toml`
- `schemas/topology/topology.schema.json`
- `schemas/topology/package_boundaries.schema.json`
- `schemas/topology/import_contracts.schema.json`
- `schemas/topology/migration_shims.schema.json`
- `schemas/topology/complexity_exceptions.schema.json`
- `schemas/topology/public_surface.schema.json`
- `schemas/topology/generated_artifacts.schema.json`

Additive overlay contract added during Phase 0:

- `architecture/conservative_overlay.toml`
- `schemas/topology/conservative_overlay.schema.json`

The overlay contract records protected Lex/cloud/data surfaces and the required
`report_only` mode for architecture gates that touch those surfaces. It does not
change target topology or make any guardrail fail-closed.

## Protected Mode

During the overlay, the following classes of checks are allowed only in
report-only mode for protected surfaces:

- import-linter
- deptry
- topology-gate
- shim-audit
- complexity
- schema-drift
- generated-header
- docs-freshness
- loose-file

## Phase 0 Safety Check

Phase 0 did not change:

- `src/polisyos/lex/batch/**`
- `src/polisyos/batch_common/**`
- `src/polisyos/batch_snapshot/**`
- `tools/ops/cloud/**`
- `tools/cloud/**`
- `tools/ops/ukraine_data/pre_shard_lex_corpus.py`
- `tools/ukraine_data/pre_shard_lex_corpus.py`

## Next Safe Work

Safe follow-up work before the overlay ends:

1. Add a report-only validator that reads `architecture/conservative_overlay.toml`
   and emits warnings for protected-path changes.
2. Add docs-only mapping for topology cleanup targets.
3. Keep all protected-path enforcement fail-open until the cutover readiness
   gate records Queue 2 and Queue 3 completion plus merge/QC evidence.
