# Frontend

Related reference: [REST API](../api/index.md), [Generated Artifacts](../generated-artifacts.md).

Freshness: 2026-04-17
Owner: `@frontend-owners`
Backup owner: `@runtime-owners`
Source of truth: `frontend/**`, `schemas/runtime_api_v1.openapi.json`,
`src/polisyos/runtime/http/**`, and the package READMEs under `frontend/`

> Reference surface for Runtime API consumers: dashboard, generated runtime
> client, and static reference shell.

## Contract Chain

The current frontend path is contract-first:

1. runtime HTTP source in `src/polisyos/runtime/http/**`;
2. committed OpenAPI snapshot in `schemas/runtime_api_v1.openapi.json`;
3. generated JS/TS client in `frontend/runtime-api-client/`;
4. generated dashboard API types in `frontend/runtime-dashboard/src/api/types.ts`;
5. operator UI in `frontend/runtime-dashboard/`.

## Surfaces

| Surface                             | Purpose                             | Primary source                               |
| ----------------------------------- | ----------------------------------- | -------------------------------------------- |
| `frontend/runtime-dashboard/`       | Main operator-facing React/Vite app | `frontend/runtime-dashboard/README.md`       |
| `frontend/runtime-api-client/`      | Generated JS/TS runtime client      | `frontend/runtime-api-client/README.md`      |
| `frontend/runtime-reference-shell/` | Static API diagnostics shell        | `frontend/runtime-reference-shell/README.md` |

## High-Signal Commands

```bash
cd policy-engine/frontend/runtime-dashboard
npm run generate:api
npm run contracts:verify
npm run typecheck
```

Cross-layer runtime check:

```bash
cd policy-engine
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py
```

## Start Pages

| Need                                                    | Start here                                                               |
| ------------------------------------------------------- | ------------------------------------------------------------------------ |
| Role-based onboarding                                   | [Frontend Engineer](../../how-to/onboarding/frontend-engineer.md)        |
| Update generated contract chain                         | [REST API](../api/index.md) plus `frontend/runtime-api-client/README.md` |
| Understand runtime deploy/runtime base URL expectations | [Deploy Runtime](../../how-to/deploy-runtime.md)                         |
| Debug control-plane driven UI states                    | [Use Control Plane](../../how-to/use-control-plane.md)                   |

## Validation Anchors

| Area                          | Validation                                                                                              |
| ----------------------------- | ------------------------------------------------------------------------------------------------------- |
| Runtime/OpenAPI/client drift  | `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py` |
| Dashboard generated API types | `cd frontend/runtime-dashboard && npm run generate:api`                                                 |
| Dashboard contract fixtures   | `cd frontend/runtime-dashboard && npm run contracts:verify`                                             |
| TS correctness                | `cd frontend/runtime-dashboard && npm run typecheck`                                                    |

## Notes

- frontend pages must consume runtime over HTTP and generated artifacts, not by
  reading runtime filesystem state directly;

- route-only runtime endpoints stay out of generated clients and must be handled
  intentionally in docs or ad hoc diagnostics surfaces.
