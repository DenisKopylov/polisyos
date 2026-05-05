# Workspace DevX (`tools/devx/workspace`)

## Purpose

`tools/devx/workspace` — repo-local tooling surface для bootstrap, workstation
preflight, fast local gates, CI parity и remote acceptance closeout.

## Where to Start

- Bootstrap/install flow: `tools/devx/workspace/bootstrap.py`.
- Machine preflight: `tools/devx/workspace/doctor.py`.
- Fast local gate: `tools/devx/workspace/verify.py`.
- CI-like parity pass: `tools/devx/workspace/ci_parity.py`.
- Repository SOTA closeout: `tools/devx/workspace/repository_sota_closeout.py`.
- Shared baseline/constants: `tools/devx/workspace/_common.py`.

## Public Entrypoints

| Entrypoint                                                                         | Purpose                                                                                                                                       |
| ---------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `uv run polisyos-tools workspace bootstrap`                                        | Подготовить contributor machine и проверить минимальный baseline.                                                                             |
| `uv run polisyos-tools workspace doctor`                                           | Проверить Python/Node/uv, Playwright, lockfiles, generated contracts и optional env surfaces.                                                 |
| `uv run polisyos-tools workspace verify`                                           | Запустить стандартный быстрый локальный gate.                                                                                                 |
| `uv run polisyos-tools workspace docs-style`                                       | Прогнать `markdownlint-cli2` по authored docs и package README/CONTRIBUTING surface.                                                          |
| `uv run polisyos-tools workspace format-check`                                     | Проверить formatter contract для Python, frontend, shell, TOML и Rego.                                                                        |
| `uv run polisyos-tools workspace lint-fast`                                        | Прогнать быстрый authored-file lint sweep по Python/docs/YAML/shell/workflows и optional frontend ESLint.                                     |
| `uv run polisyos-tools workspace python-base-mypy`                                 | Прогнать Phase 3 `mypy` contract по serial base layers: `common -> ir -> core`.                                                               |
| `uv run polisyos-tools workspace python-base-basedpyright`                         | Прогнать Phase 3 `basedpyright` contract по serial base layers: `common -> ir -> core`, с IR baseline ratchet.                                |
| `uv run polisyos-tools workspace runtime-surface`                                  | Прогнать Phase 5B runtime gate: Ruff, source type checks, OpenAPI/client drift и `tests/unit/runtime`.                                             |
| `uv run polisyos-tools workspace lint-full`                                        | Прогнать полный authored lint contract с Phase 3 base-layer type gates, `helm lint` и Rego strict/test pass.                                  |
| `uv run polisyos-tools workspace benchmark-surfaces`                               | Прогнать Phase 8 gate для `benchmarks/**` и `tools/research/**`: Ruff по authored Python и shell/YAML hooks без markdown/result-bundle churn. |
| `uv run polisyos-tools workspace ci-parity`                                        | Запустить более тяжёлый pass, близкий к основным CI jobs.                                                                                     |
| `uv run polisyos-tools workspace acceptance-audit`                                 | Сформировать Phase 7 acceptance evidence.                                                                                                     |
| `uv run polisyos-tools workspace repository-sota-closeout`                         | Проверить fail-closed Repository SOTA policy layer, exception registries и closeout evidence.                                                  |
| `uv run polisyos-tools workspace remote-acceptance`                                | Вести remote Linux runner для тяжёлого closeout.                                                                                              |

## Depends On / Depended On By

- **Depends on:** `pyproject.toml`, `uv.lock`, `frontend/runtime-dashboard`,
  `package-lock.json`, generated contracts, optional env surfaces и `tools`
  validation/lint/runtime categories.

- **Depended on by:** новые contributor-ы, локальный closeout перед PR,
  onboarding docs, acceptance rehearsals и remote platform verification.

## Common Commands

Команды ниже smoke-tested на `2026-04-17`, если явно не помечены как
`conceptual`.

| Command                                                                                                                 | Purpose                                                                               | Status                                      |
| ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------- |
| `uv run polisyos-tools workspace doctor --list-surfaces`                                                                | Показать optional env surfaces, которые может проверять `doctor`.                     | `smoke-tested`                              |
| `uv run polisyos-tools workspace docs-style`                                                                            | Проверить authored docs, README и plan markdown без archive churn.                    | `conceptual`                                |
| `uv run polisyos-tools workspace format-check --skip-rego`                                                              | Прогнать formatter-only contract на машине без локального `opa`.                      | `conceptual`                                |
| `uv run polisyos-tools workspace lint-fast --skip-frontend`                                                             | Прогнать быстрый repo-hygiene lint для Python/docs/config/shell без dashboard ESLint. | `conceptual`                                |
| `uv run polisyos-tools workspace python-base-mypy --layer ir --layer core`                                              | Прогнать только типовой Phase 3 хвост после завершённого `common`.                    | `conceptual`                                |
| `uv run polisyos-tools workspace python-base-basedpyright --layer ir`                                                   | Проверить IR через репозиторный basedpyright baseline.                                | `conceptual`                                |
| `uv run polisyos-tools workspace runtime-surface --skip-tests`                                                          | Проверить Phase 5B lint/type/OpenAPI contract без полного runtime pytest.             | `conceptual`                                |
| `uv run polisyos-tools workspace lint-full --skip-policy --skip-helm`                                                   | Прогнать полный authored lint contract на машине без локальных `opa` и `helm`.        | `conceptual`                                |
| `uv run polisyos-tools workspace benchmark-surfaces`                                                                    | Прогнать точечный benchmark/research hygiene gate без Markdown/JSON/log/result churn. | `conceptual`                                |
| `uv run polisyos-tools workspace repository-sota-closeout --contract-only`                                              | Проверить Phase 5 contract layer без тяжёлых drift subprocesses.                 | `conceptual`                                |
| `uv run polisyos-tools workspace doctor --skip-playwright --skip-lockfile-checks --skip-contract-checks`                | Быстрый workstation preflight без тяжёлых browser/lock/contract checks.               | `smoke-tested`                              |
| `uv run polisyos-tools workspace bootstrap --profile docs --skip-frontend --skip-playwright --skip-hooks --skip-doctor` | Установить docs-oriented baseline на новой машине.                                    | `conceptual` (изменяет локальное окружение) |
| `uv run polisyos-tools workspace verify --backend-only --skip-doctor`                                                   | Прогнать быстрый backend-only gate после локальных правок.                            | `conceptual` (может занять заметное время)  |
| `uv run polisyos-tools workspace ci-parity --skip-browser`                                                              | Прогнать umbrella parity pass с docs checks по умолчанию.                             | `conceptual` (тяжёлый агрегирующий gate)    |

## Test And Verification

| Command                                                                                                                                    | What it verifies                                                                      | Status         |
| ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------- | -------------- |
| `uv run pytest -q tests/tools/test_workspace_phase3.py tests/unit/core/phase0/test_workspace_commands.py tests/tools/test_remote_acceptance.py` | Workspace command contract, compatibility wrappers и remote acceptance orchestration. | `conceptual`   |
| `uv run polisyos-tools validation check-docs-accuracy --repo-root .`                                                                       | README/doc references вокруг workspace tooling остаются publishable.                  | `smoke-tested` |

## Reference Docs

- [Contributor Start Here](../../../docs/reference/contributor-start-here.md)
- [Install How-To](../../../docs/how-to/install.md)
- [CI/CD Platform How-To](../../../docs/how-to/operate-ci-cd-platform.md)
- [Dependency Platform Reference](../../../docs/reference/dependency-platform.md)
- [Environment Matrix Reference](../../../docs/reference/environment-matrix.md)
- [Quality Gates Reference](../../../docs/reference/quality-gates.md)

## Current State

- Contributor baseline: Python `3.14.x`, Node `22.x`, `uv 0.9.21`.
- Repo hygiene contract is documented in
  `docs/reference/repository-hygiene.md` and backed by root
  `.editorconfig`, `.markdownlint-cli2.jsonc`, `.yamllint`, `.taplo.toml`,
  and the `docs-style` / `format-check` / `lint-fast` / `python-base-*` /
  `lint-full` commands.

- Phase 3 Python base layers use serial `common -> ir -> core` wrappers.
  `mypy` stays green via an explicit debt ledger in `pyproject.toml`, and
  `basedpyright` ratchets IR through
  `architecture/baselines/basedpyright/baseline.json`.

- Phase 5B runtime uses `runtime-surface` to combine Ruff, source-only type
  checks, public-facade/runtime policy tests, and OpenAPI/client drift checks.

- Repository SOTA Phase 5 uses `repository-sota-closeout` to enforce topology,
  import, public-surface, generated-artifact, docs-freshness, shim, complexity,
  security, dependency, SBOM, release, and command-registry contracts.

- `ci-parity` по умолчанию включает docs accuracy, strict MkDocs build и
  semantic docstring checks, если не указан `--skip-docs`.

- Remote acceptance path разделяет rsynced worktree, clean checkout и artifact
  root, чтобы closeout на Linux был воспроизводимым.

- Last updated: 2026-05-03
