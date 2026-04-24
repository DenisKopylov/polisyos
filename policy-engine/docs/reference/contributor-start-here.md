# Contributor Start Here

Freshness: 2026-04-17
Owner: `@docs-owners`
Source of truth: `docs/how-to/install.md`, `docs/how-to/onboarding/**`,
`docs/reference/public-surface.md`, `frontend/runtime-dashboard/README.md`,
`docs/reference/security-compliance.md`, `docs/reference/operations/platform-acceptance-audit.md`, `tools/registry.py`, and
`tools/devx/**`

> Быстрый индекс по принципу "если вы меняете X, начните отсюда".

## First 30 Minutes

1. Сверьте supported host surface в
   [Environment Matrix](environment-matrix.md).
2. Пройдите install path из [Installation](../how-to/install.md).
3. Выберите ближайший role track в
   [Onboarding Tracks](../how-to/onboarding/index.md).
4. Запустите scoped local gate через `workspace verify`.
5. Если изменение затрагивает repo-wide policy, release или acceptance surface,
   завершите работу через `workspace ci-parity` или `workspace acceptance-audit`.

## If You Need To Change X

| Surface                                         | Start here                                                                                                                             | Then verify                                                                                                              |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Cross-surface post-refactor cleanup             | [Post-Refactor Migration](../how-to/post-refactor-migration.md)                                                                        | `uv run polisyos-tools validation check-docs-gate --repo-root . --base-ref origin/main` plus the matching subsystem gate |
| Новый runtime route                             | [REST API](api/index.md) plus `src/polisyos/runtime/http/`                                                                             | `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py`                  |
| Public package facade / supported import path   | [Public Surface](public-surface.md)                                                                                                    | `uv run polisyos-tools architecture guardrails check`                                                                    |
| ABI-visible IR type                             | [Manage Schemas](../how-to/manage-schemas.md) and [IR Schema Catalog](ir/schema-catalog.md)                                            | `uv run --extra ml polisyos-tools diagnostics gen-schema --check`                                                        |
| Dashboard API types / generated frontend client | [REST API](api/index.md) plus `frontend/runtime-api-client/README.md`                                                                  | runtime contract check plus `cd frontend/runtime-dashboard && npm run generate:api && npm run contracts:verify`          |
| New connector                                   | [Writing a Connector](../tutorials/writing-a-connector.md) and [Connector Contributing](../connectors/CONTRIBUTING.md)                 | `uv run polisyos-tools lint lint-connectors`                                                                             |
| New governance pass                             | [Creating a Governance Pass](../tutorials/creating-governance-pass.md) and [Write Governance Pass](../how-to/write-governance-pass.md) | targeted `tests/scientist/governance/**`                                                                                 |
| Runtime deployment or operator flow             | [Deploy Runtime](../how-to/deploy-runtime.md) and [Use Control Plane](../how-to/use-control-plane.md)                                  | runtime contract checks plus relevant runbooks                                                                           |
| Security/compliance review packet               | [Security and Compliance Operations](security-compliance.md) and [Platform Acceptance Audit](operations/platform-acceptance-audit.md)  | focused security pytest surface or `workspace acceptance-audit`                                                          |
| First analytical walkthrough                    | [Getting Started](../tutorials/getting-started.md) and [First Policy Analysis](../tutorials/first-policy-analysis.md)                  | local import smoke plus causal/tutorial flow                                                                             |

## Role Entry Points

| Persona                | Start page                                                                             | Typical first verification                                                                           |
| ---------------------- | -------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| New contributor        | [Getting Started](../tutorials/getting-started.md)                                     | `python3 -m tools.cli workspace verify --backend-only --skip-doctor`                                 |
| Backend engineer       | [Backend Engineer](../how-to/onboarding/backend-engineer.md)                           | `python3 -m tools.cli workspace verify --backend-only --skip-doctor`                                 |
| Frontend engineer      | [Frontend Engineer](../how-to/onboarding/frontend-engineer.md)                         | `python3 -m tools.cli workspace verify --frontend-only --skip-doctor`                                |
| Platform / Ops         | [Platform / Ops Engineer](../how-to/onboarding/platform-ops-engineer.md)               | `python3 -m tools.cli workspace doctor --list-surfaces` plus `python3 -m tools.cli workspace verify` |
| Security / Compliance  | [Security / Compliance Reviewer](../how-to/onboarding/security-compliance-reviewer.md) | focused security pytest surface                                                                      |
| Domain / Policy reader | [Domain / Policy Reader](../how-to/onboarding/domain-policy-reader.md)                 | tutorial walkthrough plus run/control inspection                                                     |
