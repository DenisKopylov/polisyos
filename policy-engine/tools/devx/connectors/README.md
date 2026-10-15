# Connector DevX (`tools/devx/connectors`)

## Purpose

`tools/devx/connectors` is the tooling surface for the connector lifecycle: schema-contract checks, snapshot-drift checks, and dry-run scaffolding for new source adapters.

## Where to Start

- Contract drift check: `tools/devx/connectors/check_contracts.py`.
- Scaffold generator: `tools/devx/connectors/scaffold.py`.
- Live contract definitions:
  `src/polisyos/fabric/connectors/sources/_contracts/`.

- Snapshot target:
  `schemas/snapshots/connectors/contracts.json`.

- Connector implementation/tests:
  `src/polisyos/fabric/connectors/sources/` and
  `tests/unit/fabric/connectors/sources/`.

## Public Entrypoints

| Entrypoint                                                                             | Purpose                                                                                           |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `uv run polisyos-tools connectors check-contracts --check`                             | Check that the committed snapshot matches the current contracts and that version bumps are valid. |
| `uv run polisyos-tools connectors check-contracts --update`                            | Rewrite the snapshot after an intentional schema change.                                          |
| `uv run polisyos-tools connectors scaffold create --name <Name> --type TYPE --dry-run` | Generate a connector skeleton and test-harness preview.                                           |

`TYPE` accepts `REST`, `CSV`, `SQL`, or `SDMX`.

## Depends On / Depended On By

- **Depends on:** `polisyos.fabric.connectors.contracts.*`,
  `src/polisyos/fabric/connectors/sources/_contracts/`,
  `schemas/snapshots/connectors/contracts.json`, and the connector test harness.

- **Depended on by:** connector authors, `workspace verify`, Fabric schema
  governance, `architecture scaffold connector`, and the docs/how-to for adding
  new data sources.

## Common Commands

The statuses below record a historical smoke run from `2026-04-17`. These commands were not run during this documentation change, so the current snapshot-drift status was not established.

| Command                                                                                  | Purpose                                              | Status                                                    |
| ---------------------------------------------------------------------------------------- | ---------------------------------------------------- | --------------------------------------------------------- |
| `uv run polisyos-tools connectors check-contracts --check`                               | Check contract-snapshot drift without writing files. | 2026-04-17: smoke-tested; receipt reported stale snapshot |
| `uv run polisyos-tools connectors scaffold create --name MySource --type REST --dry-run` | Check scaffold output for a new REST connector.      | 2026-04-17: smoke-tested                                  |
| `uv run polisyos-tools connectors check-contracts --update`                              | Update the committed snapshot after review.          | Conceptual; changes the checked-in snapshot               |

## Test And Verification

| Command                                                                                                                                                                     | What it verifies                                                               | Status                   |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ------------------------ |
| `uv run pytest -q tests/unit/fabric/connectors/test_registry.py tests/unit/fabric/connectors/test_contract_system.py tests/repo_quality/tools/test_phase4_consolidation.py` | Registry contract, schema-evolution behavior, and zoned-tooling consolidation. | `conceptual`             |
| `uv run polisyos-tools validation fabric-schema-governance --check --evidence-out _build/.tmp/fabric-schema-governance.json`                                                | Governance-level compatibility evidence for connector-contract changes.        | 2026-04-17: smoke-tested |

## Reference Docs

- [Connector Contributing Guide](../../../docs/connectors/CONTRIBUTING.md)
- [Add Data Source How-To](../../../docs/how-to/add-data-source.md)
- [Fabric Connectors Reference](../../../docs/reference/fabric/connectors.md)
- [Schemas Reference](../../../docs/reference/schemas.md)
- [Broken Contract Generation Runbook](../../../docs/runbooks/broken-contract-generation.md)
- [Fabric README](../../../src/polisyos/fabric/README.md)

## Current State

- `check_contracts.py` is the canonical drift gate for `schemas/snapshots/connectors/contracts.json`.
- `scaffold.py` generates both the source file and a basic test-harness skeleton.
- Legacy path-based connector wrappers retired in Phase 1D; use `polisyos-tools connectors ...`.
- Last updated: 2026-10-14
