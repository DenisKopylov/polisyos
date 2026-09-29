# IR Schema Migrations

Owner: `team-ir`

This directory owns operator guidance for canonical Policy IR, Trinity bundle,
IR snapshot, and persisted IR artifact migrations. Implementation code remains
in `src/polisyos/ir/migrations/**`; this directory is the operational contract
that release promotion reads.

## Covered Surfaces

- `src/polisyos/ir/migrations/**`
- `schemas/snapshots/ir/**`
- `docs/reference/ir/schema-catalog.md`
- persisted IR artifacts referenced by runtime, Foundry, or Scientist flows

## Operator Checks

- Migrations must be deterministic and version stamped with `schema_version`.
- Major version transitions require explicit owner approval and compatibility
  fixture evidence.
- Legacy non-Trinity payloads must fail closed unless a reviewed migration
  contract explicitly reintroduces them.
- Runtime and data-plane consumers must either read N-1 payloads directly or
  invoke a declared migration helper before promotion.

## Release Gate

`ops/release/promotion-gates.toml#ir_migration_review` blocks IR schema
promotion unless the migration helper, schema catalog, compatibility fixtures,
and runbook evidence are all present.

## Scientist Frontier Artifact v3 (B111)

This migration-class guidance covers the persisted Scientist DTOs
`polisyos.scientist.policy_design.PolicyFrontierReport` and
`polisyos.scientist.policy_design.RejectedAlternativesSummary`. The
`migration-contracts.toml` mapping classifies the change as `ir`; the release
fragment uses `change_class = "persisted-artifact-format"`. Scientist owns the
payload semantics and `team-ir` owns the migration-class/version contract.
This does not cover `ParetoRegistrySnapshot` serialization.

The ordinary new-producer path writes schema `3.0`. These DTOs support v1 and
v3; schema `2.0` was never issued by the integrated path and is unsupported
and rejected. Historical v1 bytes retain their version-specific projection
and are replayed byte-exactly. Do not rewrite, restamp, or reissue historical
v1 artifacts. Each v3 Pareto projection's `eligible_candidate_hashes` is the
identity set for that projection's assessment denominator. The v3
`PolicyFrontierReport` validator checks explicitly supplied
`source_feasible_candidate_hashes` and
`eligibility_unknown_candidate_hashes` against the global projection; a
supplied source mismatch or unknown identity requires `denominator_limited`.
`RejectedAlternativesSummary` has its own v3 `view_projection` and does not
carry those report-level fields.

The ordinary `PolicyArtifactBuilder._build_frontier_report` path has no
independent source-feasible or unknown-eligibility input. It sets
`source_feasible_candidate_hashes` from
`projection.eligible_candidate_hashes` and leaves the unknown set at its empty
default. Its report therefore validates a source set copied from the same
projection; it does not perform an independent observed-source reconciliation
and cannot detect an eligible candidate omitted before registry projection.
A complete registry assessment is scoped to the identities the registry
received and does not establish a complete upstream universe. With no
registry, the report remains basis-limited and unranked. Treat external
population completeness as `not_established` until an owner-bound input and
bridge supply and reconcile it.

### B111 rollout and promotion state

Before the first v3 write, every consumer of either artifact kind must be
confirmed able to read v1 and v3. Use a reader-only compatible release or a
coordinated no-write interval before deploying the v3 writer. This slice adds
no separate writer-disable switch. If consumer readiness or the no-write
interval cannot be established, hold deployment. After v3 bytes exist, do not
downgrade a consumer to a strict v1-only reader; keep v1/v3-capable readers
available and repair forward. Never use deletion, rewriting, restamping, or
reissuance as rollback.

The current `ir_migration_review` contract calls for a deterministic migration
helper, schema-catalog evidence, compatibility fixtures, and runbook evidence.
This B111 path deliberately has no byte-rewrite helper, and the listed IR
schema catalog/how-to describe IR schema types rather than these Scientist
DTOs. The Scientist package README documents their payload semantics, but the
class contract has not yet accepted that as a qualified no-rewrite evidence
path or resolved the operator-doc mismatch. Therefore the gate is **not met**
and production promotion remains **held** until `team-ir` and the Scientist
artifact owner approve a compatible no-rewrite evidence contract and the
required consumer/store inventory is supplied. Do not invent a migration helper
solely to satisfy the current wording.
