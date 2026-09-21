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

## RunManifest path migration

`polisyos-tools migrations migrate run_manifest` is a path-only normalization
profile. It resolves each artifact against the persisted `run_root`, preserves
nested relative identity, and publishes the converted manifest atomically only
after every artifact reference has been checked. Missing sources, broken or
escaping symlinks, path/relative-path identity conflicts, and absolute paths
outside `run_root` fail closed without changing the requested output.

The profile rejects `--to` with a typed error because it has no versioned
RunManifest schema conversion. It never copies external files implicitly; an
explicit relocation profile must be selected and reviewed before any such
operation. Existing manifests and historical bytes remain untouched because
the CLI writes a separate output path. Re-running the path-only profile is
idempotent for the canonical path representation.
