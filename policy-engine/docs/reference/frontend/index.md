# Frontend

Related reference: [REST API](../api/index.md),
[Generated Artifacts](../generated-artifacts.md), and
[Workspace Contract](workspace-contract.md).

Freshness: 2026-05-03
Owner: `@frontend-owners`
Backup owner: `@runtime-owners`
Source of truth: `apps/**`, `packages/runtime-api-client/**`,
`schemas/runtime_api_v1.openapi.json`, `src/polisyos/runtime/http/**`, and the
package READMEs under `apps/` and `packages/`

> Reference surface for Runtime API consumers: dashboard, generated runtime
> client, and static reference shell.

## Contract Chain

The current JavaScript workspace path is contract-first:

1. runtime HTTP source in `src/polisyos/runtime/http/**`;
2. committed OpenAPI snapshot in `schemas/runtime_api_v1.openapi.json`;
3. generated JS/TS client in `packages/runtime-api-client/`;
4. generated dashboard API types in `apps/runtime-dashboard/src/api/types.ts`;
5. operator UI in `apps/runtime-dashboard/`.

## Surfaces

| Surface                             | Purpose                             | Primary source                               |
| ----------------------------------- | ----------------------------------- | -------------------------------------------- |
| `apps/runtime-dashboard/`       | Main operator-facing React/Vite app | `apps/runtime-dashboard/README.md`       |
| `packages/runtime-api-client/`      | Generated JS/TS runtime client      | `packages/runtime-api-client/README.md`      |
| `apps/runtime-reference-shell/` | Static API diagnostics shell        | `apps/runtime-reference-shell/README.md` |

## High-Signal Commands

```bash
cd policy-engine
corepack pnpm --filter @polisyos/runtime-dashboard run generate:api
corepack pnpm --filter @polisyos/runtime-dashboard run contracts:verify
corepack pnpm --filter @polisyos/runtime-dashboard run typecheck
```

Cross-layer runtime check:

```bash
cd policy-engine
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
```

## Start Pages

| Need                                                    | Start here                                                               |
| ------------------------------------------------------- | ------------------------------------------------------------------------ |
| Role-based onboarding                                   | [Frontend Engineer](../../how-to/onboarding/frontend-engineer.md)        |
| Update generated contract chain                         | [REST API](../api/index.md) plus `packages/runtime-api-client/README.md` |
| Check workspace ownership and output policy             | [Workspace Contract](workspace-contract.md)                              |
| Understand runtime deploy/runtime base URL expectations | [Deploy Runtime](../../how-to/deploy-runtime.md)                         |
| Debug control-plane driven UI states                    | [Use Control Plane](../../how-to/use-control-plane.md)                   |

## Validation Anchors

| Area                          | Validation                                                                                              |
| ----------------------------- | ------------------------------------------------------------------------------------------------------- |
| Runtime/OpenAPI/client drift  | `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py` |
| Dashboard generated API types | `corepack pnpm --filter @polisyos/runtime-dashboard run generate:api`                                   |
| Dashboard contract fixtures   | `corepack pnpm --filter @polisyos/runtime-dashboard run contracts:verify`                               |
| TS correctness                | `corepack pnpm --filter @polisyos/runtime-dashboard run typecheck`                                      |

## Notes

- frontend pages must consume runtime over HTTP and generated artifacts, not by
  reading runtime filesystem state directly;

- route-only runtime endpoints stay out of generated clients and must be handled
  intentionally in docs or ad hoc diagnostics surfaces.
