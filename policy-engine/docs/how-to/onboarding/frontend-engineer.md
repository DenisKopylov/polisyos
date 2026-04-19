# Onboarding: Frontend Engineer

Related reference: [REST API](../../reference/api/index.md),
[Generated Artifacts](../../reference/generated-artifacts.md), `frontend/runtime-dashboard/README.md`, and `frontend/runtime-api-client/README.md`.

## Goal

Быстро войти в runtime-consumer surface: dashboard, generated API types,
contract fixtures и operator-facing UX.

## Inputs

- `workspace bootstrap --profile runtime` уже выполнен;
- `frontend/runtime-dashboard` dependencies установлены;
- вы понимаете, меняете ли вы dashboard UI, generated API types или сам runtime
  contract.

## Output

После этого onboarding вы должны уметь:

- локально поднять dashboard;
- обновить dashboard API types без drift;
- отличать frontend bug от backend contract change.

## Canonical Commands

```bash
cd policy-engine
python3 -m tools.cli workspace bootstrap --profile runtime
python3 -m tools.cli workspace verify --frontend-only --skip-doctor
cd frontend/runtime-dashboard
npm run generate:api
npm run contracts:verify
npm run typecheck
```

## Start Here By Task

| Task | Primary doc | Why it matters |
|---|---|---|
| Contract-first overview of frontend surfaces | [REST API](../../reference/api/index.md) plus `frontend/runtime-dashboard/README.md` | dashboard, generated API client, and validation chain |
| Обновить generated dashboard types после runtime change | [REST API](../../reference/api/index.md) plus `frontend/runtime-api-client/README.md` | OpenAPI -> generated client -> dashboard type sync |
| Понять operator UX и runtime boundaries | [Deploy Runtime](../deploy-runtime.md) and [Use Control Plane](../use-control-plane.md) | UI reflects control-plane reality, not mock-only state |

## First Productive Slice

Хороший первый change:

- исправить `npm run contracts:verify` после intentional backend contract change;
- обновить один dashboard workspace/query path после новой runtime возможности;
- улучшить operator-facing error/loading state, не ломая contract fixtures.

## Rollback / Handoff

- если change требует новый endpoint или DTO, передайте или синхронизируйтесь с
  [Backend Engineer](backend-engineer.md);
- если `npm run generate:api` ничего не должен менять, а diff появился,
  проверьте, не дрейфует ли committed OpenAPI snapshot;
- не исправляйте backend drift локальными frontend hacks.

## Troubleshooting

- `generate:api` обновляет только `src/api/types.ts`; JS/TS client лежит в
  `frontend/runtime-api-client/`;
- `contracts:verify` падает: сначала сверяйте runtime snapshot и fixtures, а не
  переписывайте ожидания вслепую;
- UI issue на `/platform` почти всегда требует чтения runtime/control docs, а
  не только React tree.
