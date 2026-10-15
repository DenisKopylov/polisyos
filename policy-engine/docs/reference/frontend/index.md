# Frontend

Related references: [Current Surface Map](current-surface-map.md),
[REST API](../api/index.md), [Generated Artifacts](../generated-artifacts.md),
and [Workspace Contract](workspace-contract.md).

Freshness: 2026-10-14

Owner: `team-frontend`

Backup owner: `team-runtime`

Source of truth: `architecture/frontend_workspaces.toml`,
`architecture/generated_artifacts.toml`, `schemas/runtime_api_v1.openapi.json`,
`src/polisyos/runtime/http/**`, `apps/runtime-dashboard/**`,
`packages/runtime-api-client/**`, and `apps/runtime-reference-shell/**`.

> Reference entrypoint for the Runtime API dashboard, generated API surfaces,
> and the static diagnostics shell. The current source-backed route, transport,
> ownership, and status map is in [Current Surface Map](current-surface-map.md).

## Contract And Client Paths

Runtime HTTP routes are projected into the committed
`schemas/runtime_api_v1.openapi.json` snapshot. That snapshot has two generated
TypeScript consumers: the canonical runtime client package and the dashboard's
`src/api/types.ts` compatibility output. The dashboard's normal HTTP transport
uses its local typed `openapi-fetch` client, auth-aware fetch, query hooks, and
response validators; it does not use the package's canonical JavaScript client
as that transport. The static reference shell imports the canonical JavaScript
client. A small number of dashboard surfaces intentionally use direct fetches,
including public decision verification and the generated trust-posture asset.

The source-to-consumer chain is therefore:

1. Runtime route and DTO source in `src/polisyos/runtime/http/**`.
2. Committed OpenAPI projection in `schemas/runtime_api_v1.openapi.json`.
3. Generated package outputs in `packages/runtime-api-client/` and generated
   dashboard types in `apps/runtime-dashboard/src/api/types.ts`.
4. Dashboard transport, validators, query hooks, and route consumers in
   `apps/runtime-dashboard/`; package-client consumers such as
   `apps/runtime-reference-shell/`.

The [Current Surface Map](current-surface-map.md) records the distinctions
between generated-file owners, workspace owners, and UI-level candidate or
authority semantics. This is a repository-source map, not proof of what a
running or visually inspected application renders.

## Surfaces

| Surface | Purpose | Primary source |
| --- | --- | --- |
| `apps/runtime-dashboard/` | Main operator-facing React/Vite app | `apps/runtime-dashboard/README.md` |
| `packages/runtime-api-client/` | Generated Runtime API v1 types and canonical TS/JS client | `packages/runtime-api-client/README.md` |
| `apps/runtime-reference-shell/` | Static API diagnostics shell; not the product UI | `apps/runtime-reference-shell/README.md` |

## Start Pages

| Need | Start here |
| --- | --- |
| Current route, transport, status, and audience behavior | [Current Surface Map](current-surface-map.md) |
| Role-based onboarding | [Frontend Engineer](../../how-to/onboarding/frontend-engineer.md) |
| Update the generated contract chain | [API client update procedure](../../how-to/update-runtime-dashboard-api-client.md), [REST API](../api/index.md), and `packages/runtime-api-client/README.md` |
| Check workspace ownership and generated-output policy | [Workspace Contract](workspace-contract.md) |
| Understand runtime base-URL expectations | [Deploy Runtime](../../how-to/deploy-runtime.md) |
| Debug control-plane-driven UI states | [Use Control Plane](../../how-to/use-control-plane.md) |

## Validation Anchors

| Area | Command |
| --- | --- |
| Registered generated-output freshness | `uv run polisyos-tools architecture guardrails check` |
| Runtime/OpenAPI/client drift | `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py` |
| Dashboard generated API types | `corepack pnpm --filter @polisyos/runtime-dashboard run generate:api` |
| Dashboard contract fixtures | `corepack pnpm --filter @polisyos/runtime-dashboard run contracts:verify` |
| Dashboard TypeScript | `corepack pnpm --filter @polisyos/runtime-dashboard run typecheck` |

## Boundary Notes

- Frontend pages use Runtime API HTTP and registered generated artifacts; they
  must not read runtime filesystem state directly.
- Route-only endpoints, static public artifacts, and server-verified public
  records have distinct contracts. Consult the [Current Surface Map](current-surface-map.md)
  before extending a generated client or treating a rendered status as
  authority.
- Generated files must be changed through their registered generators and
  checked against the source-of-truth policy in the
  [Workspace Contract](workspace-contract.md) and
  [Generated Artifacts](../generated-artifacts.md).
