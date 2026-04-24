# Onboarding: Backend Engineer

Related reference: [REST API](../../reference/api/index.md),
[IR](../../reference/ir/index.md), [Public Surface](../../reference/public-surface.md),
[Generated Artifacts](../../reference/generated-artifacts.md).

## Goal

Стать продуктивным на runtime/IR/Fabric boundary без лишнего погружения в
frontend и without breaking contract surfaces.

## Inputs

- установленный профиль `runtime` или эквивалентный manual setup;
- понимание, меняете ли вы route, service, public facade или schema-backed type;
- готовность держаться за generated-artifact and contract checks.

## Output

После этого onboarding вы должны уметь:

- добавить новый runtime route;
- обновить public facade без deep-import drift;
- провести change через schema/OpenAPI/public-surface checks.

## Canonical Commands

```bash
cd policy-engine
python3 -m tools.cli workspace bootstrap --profile runtime --skip-playwright
python3 -m tools.cli workspace verify --backend-only --skip-doctor
uv run polisyos-tools architecture guardrails check
uv run --extra ml polisyos-tools diagnostics gen-schema --check
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py
```

## Start Here By Task

| Task                                         | Primary doc                                                                                                                      | Why it matters                                           |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| Новый HTTP endpoint                          | [REST API](../../reference/api/index.md) and `src/polisyos/runtime/http/`                                                        | Route module, app wiring, OpenAPI drift, contract checks |
| Новый package export / supported import path | [Public Surface](../../reference/public-surface.md)                                                                              | `__all__`, public-surface manifest, guardrails           |
| Новый IR model/enum с schema/catalog impact  | [Manage Schemas](../manage-schemas.md) and [IR Schema Catalog](../../reference/ir/schema-catalog.md)                             | ABI snapshots, schema catalog, IR docs                   |
| Runtime deploy/debug context                 | [Deploy Runtime](../deploy-runtime.md), [Use Control Plane](../use-control-plane.md), [Debug Failed Run](../debug-failed-run.md) | End-to-end operational reality                           |

## First Productive Slice

Возьмите одну bounded задачу:

- починить backend gate, падающий в `workspace verify --backend-only`;
- добавить небольшой route или DTO и довести change до OpenAPI check;
- сделать один intentional IR/public-surface update и провести его через
  guardrails/schema catalog.

## Rollback / Handoff

- если изменение оказалось purely frontend-consumer-facing, передайте его в
  [Frontend Engineer](frontend-engineer.md);

- если route change не должен быть публичным, не добавляйте его в OpenAPI/client
  path и зафиксируйте это в API reference;

- если новая export surface не должна жить долго, не добавляйте ее в supported
  `__all__`.

## Troubleshooting

- `check-runtime-api-contract.py` падает: проверьте, обновили ли вы OpenAPI
  snapshot и generated clients;

- `guardrails check` падает: обычно проблема в `__all__`, public-surface
  manifest или deep-import drift;

- `gen-schema --check` падает: новый IR type не внесен в `schemas/abi_models.py`
  или не прошел через schema catalog/docs generation.
