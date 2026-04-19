# Workspace DevX (`tools/devx/workspace`)

## Purpose

`tools/devx/workspace` — repo-local tooling surface для bootstrap, workstation
preflight, fast local gates, CI parity и remote acceptance closeout.

## Where to Start

- Bootstrap/install flow: `tools/devx/workspace/bootstrap.py`.
- Machine preflight: `tools/devx/workspace/doctor.py`.
- Fast local gate: `tools/devx/workspace/verify.py`.
- CI-like parity pass: `tools/devx/workspace/ci_parity.py`.
- Shared baseline/constants: `tools/devx/workspace/_common.py`.

## Public Entrypoints

| Entrypoint | Purpose |
| --- | --- |
| `uv run polisyos-tools workspace bootstrap` | Подготовить contributor machine и проверить минимальный baseline. |
| `uv run polisyos-tools workspace doctor` | Проверить Python/Node/uv, Playwright, lockfiles, generated contracts и optional env surfaces. |
| `uv run polisyos-tools workspace verify` | Запустить стандартный быстрый локальный gate. |
| `uv run polisyos-tools workspace ci-parity` | Запустить более тяжёлый pass, близкий к основным CI jobs. |
| `uv run polisyos-tools workspace acceptance-audit` | Сформировать Phase 7 acceptance evidence. |
| `uv run polisyos-tools workspace remote-acceptance` | Вести remote Linux runner для тяжёлого closeout. |
| `./scripts/{bootstrap,doctor,verify,ci-parity,acceptance-audit,remote-acceptance}` | Historical wrappers, retained for compatibility. |

## Depends On / Depended On By

- **Depends on:** `pyproject.toml`, `uv.lock`, `frontend/runtime-dashboard`,
  `package-lock.json`, generated contracts, optional env surfaces и `tools`
  validation/lint/runtime categories.
- **Depended on by:** новые contributor-ы, локальный closeout перед PR,
  onboarding docs, acceptance rehearsals и remote platform verification.

## Common Commands

Команды ниже smoke-tested на `2026-04-17`, если явно не помечены как
`conceptual`.

| Command | Purpose | Status |
| --- | --- | --- |
| `uv run polisyos-tools workspace doctor --list-surfaces` | Показать optional env surfaces, которые может проверять `doctor`. | `smoke-tested` |
| `uv run polisyos-tools workspace doctor --skip-playwright --skip-lockfile-checks --skip-contract-checks` | Быстрый workstation preflight без тяжёлых browser/lock/contract checks. | `smoke-tested` |
| `uv run polisyos-tools workspace bootstrap --profile docs --skip-frontend --skip-playwright --skip-hooks --skip-doctor` | Установить docs-oriented baseline на новой машине. | `conceptual` (изменяет локальное окружение) |
| `uv run polisyos-tools workspace verify --backend-only --skip-doctor` | Прогнать быстрый backend-only gate после локальных правок. | `conceptual` (может занять заметное время) |
| `uv run polisyos-tools workspace ci-parity --skip-browser` | Прогнать umbrella parity pass с docs checks по умолчанию. | `conceptual` (тяжёлый агрегирующий gate) |

## Test And Verification

| Command | What it verifies | Status |
| --- | --- | --- |
| `uv run pytest -q tests/tools/test_workspace_phase3.py tests/core/phase0/test_workspace_commands.py tests/tools/test_remote_acceptance.py` | Workspace command contract, compatibility wrappers и remote acceptance orchestration. | `conceptual` |
| `uv run polisyos-tools validation check-docs-accuracy --repo-root .` | README/doc references вокруг workspace tooling остаются publishable. | `smoke-tested` |

## Reference Docs

- [Contributor Start Here](../../../docs/reference/contributor-start-here.md)
- [Install How-To](../../../docs/how-to/install.md)
- [CI/CD Platform How-To](../../../docs/how-to/operate-ci-cd-platform.md)
- [Dependency Platform Reference](../../../docs/reference/dependency-platform.md)
- [Environment Matrix Reference](../../../docs/reference/environment-matrix.md)
- [Quality Gates Reference](../../../docs/reference/quality-gates.md)

## Current State

- Contributor baseline: Python `3.14.x`, Node `22.x`, `uv 0.9.21`.
- `ci-parity` по умолчанию включает docs accuracy, strict MkDocs build и
  semantic docstring checks, если не указан `--skip-docs`.
- Remote acceptance path разделяет rsynced worktree, clean checkout и artifact
  root, чтобы closeout на Linux был воспроизводимым.
- Last updated: 2026-04-17
