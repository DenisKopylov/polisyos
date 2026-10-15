# snapshots/connectors — Source-Connector Contract Baseline

This directory contains the data-source contract snapshot used to check drift and validate version bumps.

## Role in the System

- Records the public contracts used by source connectors.
- Checks schema evolution through `SchemaEvolution` (major/minor/patch recommendations).
- Validated in CI (`polisyos-tools connectors check-contracts --check`, workflow `.github/workflows/abi.yml`).

## `contracts.json` Format

- `version`: snapshot-format version (`1`).
- `contracts`: object `{ "<contract_id>": { ...meta... } }`.
- Each contract retains:
  - `connector_id`, `dataset_id`, `schema_version`, `content_hash`;
  - `contract`: normalized `ConnectorSchemaContract` without the runtime timestamp (`created_at`).

## Inspected State (2026-10-14)

Static inspection at snapshot `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`: `contracts.json` and `.github/workflows/abi.yml` were read; the generator and CI were not run.

- Contracts: `5`.
- Keys:
  - `eurostat.data.generic`
  - `sdmx.generic`
  - `ukons.datasets.generic`
  - `worldbank.wdi.generic`
  - `wvs.wave7.generic`
- Current version for all contracts: `schema_version=2.0.0`.

## Sources and Tools

- Contract source: `src/polisyos/fabric/connectors/sources/_contracts`.
- Snapshot check and update: `polisyos-tools connectors check-contracts`.

## Commands (from `policy-engine/`)

```bash
# Check (the script also runs in check mode by default)
uv run polisyos-tools connectors check-contracts --check
```

```bash
# Update the snapshot
uv run polisyos-tools connectors check-contracts --update
```

## Invariants

- Do not edit `contracts.json` manually; use `--update`.
- If `SchemaEvolution` requires a larger version bump, update `schema_version` in the source contract first, then update the snapshot.
