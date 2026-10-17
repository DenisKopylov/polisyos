# Onboarding: Backend Engineer

Related reference: [REST API](../../reference/api/index.md),
[IR](../../reference/ir/index.md), [Public Surface](../../reference/public-surface.md),
[Generated Artifacts](../../reference/generated-artifacts.md).

## Goal

Become productive across the runtime/IR/Fabric boundary without unnecessary
frontend work or breaking contract surfaces.

## Inputs

- an installed `runtime` profile or equivalent manual setup;
- an understanding of whether you are changing a route, service, public facade,
  or schema-backed type;
- readiness to follow the generated-artifact and contract checks.

## Output

After this onboarding, you should be able to:

- add a runtime route;
- update a public facade without deep-import drift;
- carry a change through schema/OpenAPI/public-surface checks.

## Canonical Commands

```bash
cd policy-engine
uv run polisyos-tools workspace bootstrap --profile runtime --skip-frontend --skip-doctor
uv run polisyos-tools workspace verify --backend-only --skip-doctor
uv run polisyos-tools architecture guardrails check
uv run --extra ml polisyos-tools diagnostics gen-schema --check
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
```

Backend-only bootstrap skips the Node workspace and automatic `doctor`, but still installs the
pre-commit hook unless you add `--skip-hooks`. If you run a separate preflight, `doctor` still
requires Node `22.x` even with Playwright, lockfile, and contract checks skipped; see
[Installation](../install.md#backend-only-setup) for the narrower invocation.

## Start Here By Task

| Task                                         | Primary doc                                                                                                                      | Why it matters                                           |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| New HTTP endpoint                            | [REST API](../../reference/api/index.md) and `src/polisyos/runtime/http/`                                                        | Route module, app wiring, OpenAPI drift, contract checks |
| New package export or supported import path  | [Public Surface](../../reference/public-surface.md)                                                                              | `__all__`, public-surface manifest, guardrails           |
| New IR model/enum with schema/catalog impact | [Manage Schemas](../manage-schemas.md) and [IR Schema Catalog](../../reference/ir/schema-catalog.md)                             | ABI snapshots, schema catalog, IR docs                   |
| Runtime deploy/debug context                 | [Deploy Runtime](../deploy-runtime.md), [Use Control Plane](../use-control-plane.md), [Debug Failed Run](../debug-failed-run.md) | Deployment and control-plane operating instructions      |

## First Productive Slice

Take one bounded task:

- fix a backend gate that fails in `workspace verify --backend-only`;
- add a small route or DTO and carry the change through the OpenAPI check;
- make one intentional IR/public-surface update and run it through the
  guardrails/schema catalog flow.

## Rollback / Handoff

- if the change turns out to be purely frontend-consumer-facing, hand it to the
  [Frontend Engineer](frontend-engineer.md);

- if the route change should not be public, do not add it to the OpenAPI/client
  path; document that decision in the API reference;

- if the new export surface is not intended to last, do not add it to the
  supported `__all__`.

## Troubleshooting

- `check-runtime-api-contract.py` fails: check whether you updated the OpenAPI
  snapshot and generated clients;

- `guardrails check` fails: the issue is usually in `__all__`, the public-surface
  manifest, or deep-import drift;

- `gen-schema --check` fails: the new IR type is missing from
  `src/polisyos/schemas/abi_models/catalog.py` or was not included in schema catalog and
  documentation generation.
