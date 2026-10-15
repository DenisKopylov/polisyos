# Onboarding: Frontend Engineer

Related reference: [REST API](../../reference/api/index.md),
[Generated Artifacts](../../reference/generated-artifacts.md), `apps/runtime-dashboard/README.md`, and `packages/runtime-api-client/README.md`.

## Goal

Quickly become productive with the runtime-consumer surface: the dashboard,
generated API types, contract fixtures, and operator-facing UX.

## Inputs

- `workspace bootstrap --profile runtime` has been run;
- `apps/runtime-dashboard` dependencies are installed through Corepack/pnpm;
- Node `22.x` and pnpm `10.33.2`, pinned in `package.json`, are in use;
- you understand whether you are changing the dashboard UI, generated API types,
  or the runtime contract itself.

## Output

After this onboarding, you should be able to:

- run the dashboard locally;
- update dashboard API types without drift;
- distinguish a frontend bug from a backend contract change.

## Canonical Commands

```bash
cd policy-engine
uv run polisyos-tools workspace bootstrap --profile runtime
uv run polisyos-tools workspace verify --frontend-only --skip-doctor
cd apps/runtime-dashboard
corepack pnpm run generate:api
corepack pnpm run contracts:verify
corepack pnpm run typecheck
```

## Start Here By Task

| Task                                                    | Primary doc                                                                             | Why it matters                                         |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| Contract-first overview of frontend surfaces            | [REST API](../../reference/api/index.md) plus `apps/runtime-dashboard/README.md`        | dashboard, generated API client, and validation chain  |
| Update generated dashboard types after a runtime change | [REST API](../../reference/api/index.md) plus `packages/runtime-api-client/README.md`   | OpenAPI -> generated client -> dashboard type sync     |
| Understand operator UX and runtime boundaries           | [Deploy Runtime](../deploy-runtime.md) and [Use Control Plane](../use-control-plane.md) | UI reflects control-plane reality, not mock-only state |

## First Productive Slice

Good first changes include:

- fix `corepack pnpm run contracts:verify` after an intentional backend contract
  change;
- update one dashboard workspace/query path after a runtime capability is added;
- improve an operator-facing error/loading state without breaking contract
  fixtures.

## Rollback / Handoff

- if the change requires a new endpoint or DTO, hand it off to or coordinate
  with the
  [Backend Engineer](backend-engineer.md);

- if `corepack pnpm run generate:api` should make no changes but produces a diff,
  check whether the committed OpenAPI snapshot has drifted;

- do not patch backend drift with local frontend hacks.

## Troubleshooting

- `generate:api` updates only `src/api/types.ts`; the JS/TS client lives in
  `packages/runtime-api-client/`;

- `contracts:verify` fails: compare the runtime snapshot and fixtures before
  changing expectations blindly;

- a UI issue on `/platform` usually requires reading runtime/control documentation,
  not only the React tree.
