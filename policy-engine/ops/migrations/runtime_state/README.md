# Runtime-State Migrations

Runtime-state migrations describe compatibility rules for local `.polisyos`
state. They are not SQL migrations and they must preserve cleanup safety:
production snapshots, local key material, security evidence, audits, and
persisted state require owner approval before destructive cleanup.

## Required Slots

- `run_records`
- `reports`
- `audit`
- `artifact_cas`
- `artifact_cache`
- `validation_artifacts`
- `production_snapshot`
- `provider_verification`
- `idempotency`
- `decision_validity`
- `search_registry`
- `runtime_component_state`
- `security_evidence`
- `evicted_legacy_state`
- `fact_logs`
- `key_material`
- `persisted_local_state`

## Operator Checks

- Read `architecture/runtime_state_layout.toml` before changing a slot path,
  retention class, cleanup command, or promotion rule.
- Keep N-1 readers for state that affects replay, audit, idempotency, decision
  validity, or production snapshots.
- Export or summarize state before a breaking migration; raw local state remains
  ignored unless a reviewed redacted evidence file is promoted.
- Destructive cleanup requires the owning slot README, a dry-run inventory, and
  owner approval in release evidence.

## Release Gate

`ops/release/promotion-gates.toml#runtime_state_migration_review` blocks
runtime-state format promotion unless the changed slot has current guidance and
`docs/runbooks/migration-release-promotion.md` covers the operator action.
