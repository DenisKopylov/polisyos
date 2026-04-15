# Onboarding: Frontend Engineer

Related how-to: [Deploy Runtime](../deploy-runtime.md). Related reference:
[REST API](../../reference/api/index.md).

## Understand First

- the runtime dashboard lives in `frontend/runtime-dashboard`;
- frontend work is contract-coupled to runtime API and fixture verification;
- the `/platform` surface is an operational view, not just a visual page;
- route telemetry and Sentry are part of the operator experience, not optional
  decoration.

## Safely Ignore at First

- deep Foundry or Scientist implementation details behind already-stable API
  responses;
- heavy optional Python extras unrelated to dashboard work;
- benchmark internals unless your task changes UX for benchmark consumers.

## Commands and Docs to Use

Canonical setup:

```bash
cd policy-engine
python3 -m tools.cli workspace bootstrap
python3 -m tools.cli workspace verify --frontend-only
cd frontend/runtime-dashboard
npm run dev
```

Useful docs:

- [Deploy Runtime](../deploy-runtime.md)
- [Manage Schemas](../manage-schemas.md)
- [Operations Runbooks](../../runbooks/index.md)
- [Observability Topology](../../reference/operations/observability-topology.md)

## First Productive Task

Make one safe improvement to the operator surface:

- fix a failing `npm run contracts:verify` expectation;
- improve the `/platform` page for a real runtime health state;
- add or repair one route-level error or telemetry affordance backed by tests.

Do not start with visual polish detached from runtime reality.
