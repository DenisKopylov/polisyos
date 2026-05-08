# Architecture DevX (`tools/devx/architecture`)

## Purpose

`tools/devx/architecture` хранит machine-readable guardrails и scaffolding для
архитектурных поверхностей репозитория: public surface, generated artifacts,
deep-import baseline, workflow policy и README/runbook/ADR templates.

## Where to Start

- Guardrails engine: `tools/devx/architecture/guardrails.py`.
- Unified scaffold entrypoint: `tools/devx/architecture/scaffold.py`.
- Source-of-truth manifests:
  `architecture/public_surface/contract.toml`,
  `architecture/generated_artifacts.toml`,
  `architecture/baselines/imports/deep_import.json`,
  `architecture/exceptions/guardrails.toml`.

- Generated docs it owns:
  `docs/reference/public-surface.md`,
  `docs/reference/generated-artifacts.md`,
  `architecture/guardrail_exceptions_registry.md`.

## Public Entrypoints

| Entrypoint                                                                                              | Purpose                                                                        |
| ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `uv run polisyos-tools architecture guardrails sync`                                                    | Пересобрать inventories и generated architecture reference pages.              |
| `uv run polisyos-tools architecture guardrails check`                                                   | Проверить manifests, baselines, workflow/toolchain guardrails и README policy. |
| `uv run polisyos-tools architecture scaffold package-readme ...`                                        | Сгенерировать README scaffold по текущему template/policy.                     |
| `uv run polisyos-tools architecture scaffold connector ...`                                             | Делегировать connector scaffold в canonical tooling path.                      |
| `uv run polisyos-tools architecture scaffold {governance-pass,runtime-route,benchmark,adr,runbook} ...` | Создать golden-path шаблоны для новых surfaces.                                |

## Depends On / Depended On By

- **Depends on:** `architecture/*.toml`, generated docs under `docs/reference/`,
  workflow files under `.github/workflows/`, package facades и README policy.

- **Depended on by:** platform maintainers, docs/reference refresh, package
  owners, CI architecture checks и новый subsystem scaffolding.

## Common Commands

Команды ниже smoke-tested на `2026-04-17`, если явно не помечены как
`conceptual`.

| Command                                                                                                                                  | Purpose                                                           | Status                                        |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | --------------------------------------------- |
| `uv run polisyos-tools architecture scaffold package-readme --module polisyos.example --output src/polisyos/example/README.md --dry-run` | Проверить README scaffold без записи файлов.                      | `smoke-tested`                                |
| `uv run polisyos-tools architecture scaffold connector --name MySource --type REST --dry-run`                                            | Проверить connector scaffold через unified architecture surface.  | `smoke-tested`                                |
| `uv run polisyos-tools architecture guardrails check`                                                                                    | Прогнать full guardrail validation по manifests и generated docs. | `conceptual` (широкий repo-wide gate)         |
| `uv run polisyos-tools architecture guardrails sync --skip-deep-import-baseline`                                                         | Регенерировать inventories без переписи deep-import freeze.       | `conceptual` (обновляет checked-in артефакты) |

## Test And Verification

| Command                                                                                                       | What it verifies                                                | Status         |
| ------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- | -------------- |
| `uv run pytest -q tests/repo_quality/tools/test_architecture_phase3.py tests/unit/runtime/http/test_architecture_boundaries.py` | Guardrails, scaffold policy и architecture-boundary invariants. | `conceptual`   |
| `uv run polisyos-tools validation check-docs-accuracy --repo-root .`                                          | Generated architecture reference pages остаются publishable.    | `smoke-tested` |

## Reference Docs

- [Public Surface Reference](../../../docs/reference/public-surface.md)
- [Generated Artifacts Reference](../../../docs/reference/generated-artifacts.md)
- [Documentation Inventory](../../../docs/reference/documentation-inventory.md)
- [Quality Gates Reference](../../../docs/reference/quality-gates.md)
- [Tool Reference](../../../docs/reference/tools.md)

## Current State

- `guardrails.py` — source of truth для public-surface inventory, deep-import
  baseline и README freshness policy.

- `scaffold.py` — единый golden-path scaffold surface; новые README/runbook/ADR
  шаблоны должны идти через него, а не через ad hoc copy-paste.

- Connector scaffold остаётся доступным и из architecture surface, и из
  `polisyos-tools connectors`.

- Last updated: 2026-04-17
