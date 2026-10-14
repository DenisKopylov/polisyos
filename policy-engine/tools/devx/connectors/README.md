# Connector DevX (`tools/devx/connectors`)

## Purpose

`tools/devx/connectors` — tooling surface для lifecycle connector-ов:
проверка schema contracts, контроль snapshot drift и dry-run scaffold для новых
source adapters.

## Where to Start

- Contract drift check: `tools/devx/connectors/check_contracts.py`.
- Scaffold generator: `tools/devx/connectors/scaffold.py`.
- Live contract definitions:
  `src/polisyos/fabric/connectors/sources/_contracts/`.

- Snapshot target:
  `schemas/snapshots/connectors/contracts.json`.

- Connector implementation/tests:
  `src/polisyos/fabric/connectors/sources/` и
  `tests/unit/fabric/connectors/sources/`.

## Public Entrypoints

| Entrypoint                                                                             | Purpose                                                                                    |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `uv run polisyos-tools connectors check-contracts --check`                             | Проверить, что committed snapshot и текущие contracts совпадают и version bumps корректны. |
| `uv run polisyos-tools connectors check-contracts --update`                            | Перезаписать snapshot после осознанного schema change.                                     |
| `uv run polisyos-tools connectors scaffold create --name <Name> --type TYPE --dry-run` | Сгенерировать connector skeleton и тестовый harness preview.                               |

`TYPE` принимает `REST`, `CSV`, `SQL` или `SDMX`.

## Depends On / Depended On By

- **Depends on:** `polisyos.fabric.connectors.contracts.*`,
  `src/polisyos/fabric/connectors/sources/_contracts/`,
  `schemas/snapshots/connectors/contracts.json` и connector test harness.

- **Depended on by:** connector authors, `workspace verify`, Fabric schema
  governance, `architecture scaffold connector` и docs/how-to для добавления
  новых data sources.

## Common Commands

Статусы ниже записывают исторический smoke run от `2026-04-17`. Эти команды
не запускались при данной документационной правке; актуальный статус snapshot
drift не устанавливался.

| Command                                                                                  | Purpose                                                | Status                                                    |
| ---------------------------------------------------------------------------------------- | ------------------------------------------------------ | --------------------------------------------------------- |
| `uv run polisyos-tools connectors check-contracts --check`                               | Проверить contract snapshot drift без записи файлов.   | 2026-04-17: smoke-tested; receipt reported stale snapshot |
| `uv run polisyos-tools connectors scaffold create --name MySource --type REST --dry-run` | Проверить scaffold output для нового REST connector-а. | 2026-04-17: smoke-tested                                  |
| `uv run polisyos-tools connectors check-contracts --update`                              | Обновить committed snapshot после review.              | Conceptual; changes the checked-in snapshot               |

## Test And Verification

| Command                                                                                                                                                                     | What it verifies                                                            | Status                   |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- | ------------------------ |
| `uv run pytest -q tests/unit/fabric/connectors/test_registry.py tests/unit/fabric/connectors/test_contract_system.py tests/repo_quality/tools/test_phase4_consolidation.py` | Registry contract, schema evolution behavior и zoned-tooling consolidation. | `conceptual`             |
| `uv run polisyos-tools validation fabric-schema-governance --check --evidence-out _build/.tmp/fabric-schema-governance.json`                                                | Governance-level compatibility evidence поверх connector contract changes.  | 2026-04-17: smoke-tested |

## Reference Docs

- [Connector Contributing Guide](../../../docs/connectors/CONTRIBUTING.md)
- [Add Data Source How-To](../../../docs/how-to/add-data-source.md)
- [Fabric Connectors Reference](../../../docs/reference/fabric/connectors.md)
- [Schemas Reference](../../../docs/reference/schemas.md)
- [Broken Contract Generation Runbook](../../../docs/runbooks/broken-contract-generation.md)
- [Fabric README](../../../src/polisyos/fabric/README.md)

## Current State

- `check_contracts.py` — canonical drift gate для `schemas/snapshots/connectors/contracts.json`.
- `scaffold.py` генерирует и source file, и базовый test harness skeleton.
- Legacy path-based connector wrappers retired in Phase 1D; use `polisyos-tools connectors ...`.
- Last updated: 2026-10-14
