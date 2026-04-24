# Validation (`tools/validation`)

## Purpose

`tools/validation` — публичный compatibility anchor для validation ratchets.
Каноническая implementation-зона живёт в `tools/quality/validation/`, но
человеческий и CI entrypoint должен идти через `polisyos-tools validation ...`.

## Where to Start

- Unified CLI boundary: `tools/cli.py` и `tools/registry.py`.
- Canonical implementation: `tools/quality/validation/`.
- Compatibility wrappers: `tools/validation/*.py`.
- Validation policy inputs:
  `tools/quality/validation/docstring_quality_allowlist.txt`,
  `tools/quality/validation/ci_ratchet_allowlist.toml`,
  `mkdocs.yml`, `docs/reference/**`, `architecture/public_surface.toml`.

## Public Entrypoints

| Entrypoint                                                                              | Purpose                                                                                                                                                             |
| --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `uv run polisyos-tools validation check-docs-gate --repo-root . --base-ref origin/main` | Запустить path-aware D6 docs drift gate с route-ами в MkDocs, docs accuracy, public-surface, schema, Runtime API/OpenAPI, generated client drift и evidence checks. |
| `uv run polisyos-tools validation check-docs-accuracy --repo-root .`                    | Проверить published docs against repository reality.                                                                                                                |
| `uv run polisyos-tools validation check-docstring-quality ...`                          | Проверить semantic quality публичных docstrings.                                                                                                                    |
| `uv run polisyos-tools validation check-ci-ratchets --repo-root .`                      | Блокировать новый suppression/cache debt в целевых surfaces.                                                                                                        |
| `uv run polisyos-tools validation fabric-schema-governance --check`                     | Проверить эволюцию Fabric connector contracts против governance policy.                                                                                             |
| `python tools/validation/<tool>.py ...`                                                 | Legacy-compatible wrappers, перенаправляющие в `tools/quality/validation/*`.                                                                                        |

## Depends On / Depended On By

- **Depends on:** `docs/`, `mkdocs.yml`, `.github/workflows/`, package
  facades под `src/`, connector contract snapshots под `schemas/snapshots/`,
  allowlist files и generated docs/reference pages.

- **Depended on by:** `workspace ci-parity`, docs-quality gates, PR closeout,
  Fabric contract governance и publishability checks.

## Common Commands

Команды ниже smoke-tested на `2026-04-17`, если явно не помечены как
`conceptual`.

| Command                                                                                                                                                                                     | Purpose                                                                               | Status                                                                                                                                                                                   |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `uv run polisyos-tools validation check-docs-gate --repo-root . --base-ref origin/main`                                                                                                     | Прогнать единый path-aware docs drift gate для D6 publication/CI policy.              | `smoke-tested` on the full dirty worktree after nested-path normalization and generated-client drift checks                                                                              |
| `uv run polisyos-tools validation check-docs-accuracy --repo-root .`                                                                                                                        | Проверить MkDocs nav, workflow references и markdown links на published docs surface. | `smoke-tested`                                                                                                                                                                           |
| `uv run polisyos-tools validation check-docstring-quality --repo-root . --allowlist tools/validation/docstring_quality_allowlist.txt --coverage-scope public-surface --minimum-coverage 85` | Проверить semantic-docstring coverage публичного API.                                 | `smoke-tested` (currently returns non-zero because existing placeholder debt remains in broader public-surface docs; `check-docs-gate` now scopes this check to changed module prefixes) |
| `uv run polisyos-tools validation check-ci-ratchets --repo-root .`                                                                                                                          | Проверить suppression ratchets и unbounded-cache debt.                                | `smoke-tested` (сейчас возвращает non-zero из-за stale allowlist entries вне L5/L8)                                                                                                      |
| `uv run polisyos-tools validation fabric-schema-governance --check --evidence-out .tmp/fabric-schema-governance.json`                                                                       | Сгенерировать governance evidence без изменения snapshot.                             | `smoke-tested`                                                                                                                                                                           |
| `uv run polisyos-tools workspace ci-parity --skip-browser`                                                                                                                                  | Запустить агрегирующий docs/tooling parity pass.                                      | `conceptual` (тяжёлый umbrella-check)                                                                                                                                                    |

## Test And Verification

| Command                                                                                                                                | What it verifies                                                                    | Status       |
| -------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ------------ |
| `uv run pytest -q tests/tools/test_tools_hardening.py tests/tools/test_fabric_schema_governance.py tests/tools/test_phase7_ratchet.py` | Regression coverage для validation hardening, schema governance и ratchet behavior. | `conceptual` |
| `uv run pytest -q tests/tools/test_unified_cli.py`                                                                                     | Unified CLI surface правильно маршрутизирует validation category.                   | `conceptual` |

## Reference Docs

- [Tool Reference](../../docs/reference/tools.md)
- [Quality Gates Reference](../../docs/reference/quality-gates.md)
- [Documentation Style Guide](../../docs/style-guide.md)
- [CI/CD Platform How-To](../../docs/how-to/operate-ci-cd-platform.md)
- [Docs Publication Failure Runbook](../../docs/runbooks/docs-publication-failure.md)
- [Connector Contributing Guide](../../docs/connectors/CONTRIBUTING.md)

## Current State

- Top-level `tools/validation/*.py` — compatibility wrappers; не дублируйте
  там новую логику.

- Канонические allowlist-файлы и shell helpers живут в
  `tools/quality/validation/`.

- `check-docs-gate` — canonical D6 docs drift entrypoint для CI и локального
  publication-ready pass; при dirty worktree можно сузить scope через
  repeatable `--changed-path`.

- `workspace ci-parity` по умолчанию включает docs accuracy, strict MkDocs
  build и semantic docstring checks, если не указан `--skip-docs`.

- Last updated: 2026-04-17
