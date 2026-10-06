# Runtime API Client

## Purpose

`runtime-api-client` stores the generated JavaScript and TypeScript client for
Runtime API v1. It is the lightest consumer surface in the frontend tree: a
thin wrapper over the OpenAPI contract that exposes read and batch-read runtime
operations without React, Vite, or dashboard-specific state management.

This package is the canonical generated-client home selected by Atlas DS3.
Do not edit `types.ts`, `canonicalRuntimeApiClient.ts`, or
`canonicalRuntimeApiClient.js` by hand. Their
shared source of truth is the runtime OpenAPI schema. The package-root export is
the canonical twin: its DTO aliases point directly at the discriminated schema
types in `types.ts`. The low-level `runtimeApiClient.*` pair is generated only
in a private scratch directory and handed to the canonicalizer; it is not a
committed or public package surface. The dashboard-local generated type file is
a downstream compatibility surface, not a second owner.

## Where to Start

- Public generated TypeScript client:
  [`canonicalRuntimeApiClient.ts`](canonicalRuntimeApiClient.ts)

- Generated OpenAPI schema types:
  [`types.ts`](types.ts)

- Canonical permission vocabulary for authority consumers:
  `components["schemas"]["RuntimePermission"]` in [`types.ts`](types.ts).
  This union is generated from the server-owned OpenAPI enum; consumers must
  not maintain a parallel permission-key list.

- Public generated JavaScript client:
  [`canonicalRuntimeApiClient.js`](canonicalRuntimeApiClient.js)

- Generator:
  [`scripts/generate-runtime-api-client.sh`](scripts/generate-runtime-api-client.sh),
  which composes the schema-type generator, private raw-client handoff, and
  canonicalizer through one output-root-aware entrypoint. Only `types.ts` and
  the canonical TS/JS pair are written under the output root.

- Canonicalizer:
  [`scripts/canonicalize-runtime-client.mjs`](scripts/canonicalize-runtime-client.mjs)

- Contract checker:
  [`../../tools/ops_runners/runtime/check_runtime_api_contract.py`](../../tools/ops_runners/runtime/check_runtime_api_contract.py)

- Upstream OpenAPI source:
  [`../../schemas/runtime_api_v1.openapi.json`](../../schemas/runtime_api_v1.openapi.json)

## Public Entrypoints

- `RuntimeApiClient` class in
  [`canonicalRuntimeApiClient.ts`](canonicalRuntimeApiClient.ts)
- OpenAPI `paths`, `components`, and `operations` in [`types.ts`](types.ts)
- Constructor options: `baseUrl`, `headers`, `fetchImpl`
- Generated method groups for health, runs, debug, artifacts, and control read
  paths in [`canonicalRuntimeApiClient.ts`](canonicalRuntimeApiClient.ts)

- ESM import surface for the reference shell:
  [`canonicalRuntimeApiClient.js`](canonicalRuntimeApiClient.js)

The runtime dashboard and Atlas UI resolve this public package export by name;
dashboard TypeScript does not bypass it with a path alias. The remediation
probe packs the package, installs that tarball into isolated consumer projects,
and exercises both ESM requests and exported types without workspace links.

## Dependencies

- Depends on:
  [`../../schemas/runtime_api_v1.openapi.json`](../../schemas/runtime_api_v1.openapi.json),
  [`../../tools/ops_runners/runtime/export_runtime_openapi.py`](../../tools/ops_runners/runtime/export_runtime_openapi.py),
  [`../../tools/ops_runners/runtime/generate_runtime_client.py`](../../tools/ops_runners/runtime/generate_runtime_client.py),
  and the runtime HTTP contract in
  [`../../src/polisyos/runtime/http/`](../../src/polisyos/runtime/http/)

- Depended on by:
  [`../../apps/runtime-reference-shell/app.js`](../../apps/runtime-reference-shell/app.js),
  ad hoc JS/TS API consumers, and frontend contract drift verification

## DesignProblem v3 outcomes

Current NL-compiled `DesignProblem` records use
`policyos.runtime.design_problem.v3`. A v3 `outcome_of_interest.target_variable`
may name a qualified canonical variable such as `government.balance`. The
schema version is load-bearing: persisted v1 and v2 records keep their
unqualified outcome grammar and must not be rewritten or interpreted as v3.

The Runtime API's governed depth-N Cycle Board can carry a `DesignProblem`
through its `DepthNDomainRunProjection`. Consumers that validate this response
against the previous OpenAPI snapshot must regenerate the client and accept
qualified outcomes only when `schema_version` is v3. Route paths and methods do
not change. A qualified identifier is a syntax-level reference; it does not
prove that the variable is present in the selected world model or that an
acquisition, N5, or authority gate accepted it.

Regenerate the public TypeScript client from the checked-in OpenAPI snapshot
with the owner command in [Common Commands](#common-commands); do not edit the
generated types by hand.

## Common Commands

- `corepack pnpm --filter @polisyos/runtime-api-client run lint`
  `smoke-tested 2026-04-23`

- `corepack pnpm --filter @polisyos/runtime-api-client run format:check`
  `smoke-tested 2026-04-23`

- `corepack pnpm --filter @polisyos/runtime-api-client run typecheck`
  `smoke-tested 2026-04-23`

- `corepack pnpm --filter @polisyos/runtime-api-client run check:architecture`
  `smoke-tested 2026-04-23`

- `corepack pnpm --filter @polisyos/runtime-api-client test`
  `smoke-tested 2026-04-23`

- `corepack pnpm --filter @polisyos/runtime-api-client run test:remediation`
  Exercises the scratch-only generated family and the explicit `--openapi`
  override with an isolated schema mutation, then packs and installs the actual
  package into isolated Dashboard and Atlas ESM/type consumers.

- `corepack pnpm --filter @polisyos/runtime-api-client run contracts:verify`
  `smoke-tested 2026-04-23`

- `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json`
  `conceptual/manual; rewrites the checked-in OpenAPI snapshot`

- `corepack pnpm --dir packages/runtime-api-client run generate -- --openapi schemas/runtime_api_v1.openapi.json`
  Replays schema types, the private raw handoff, and the public canonical twin
  in one command after exporting the OpenAPI schema. Pass
  `--output-root /absolute/scratch/root` to keep the three committed outputs
  isolated.

- `corepack pnpm --dir packages/runtime-api-client exec openapi-typescript ../../schemas/runtime_api_v1.openapi.json -o types.ts`
  Canonical schema-type generation; the exact `7.13.0` tool pin is owned by
  this shared package and does not depend on a dashboard-local installation.
  The package command runs the canonical recursive-type normalizer. Raw standalone
  generator output is not the committed type contract. Byte agreement does not
  establish runtime client behavior or endpoint execution.

## Test And Verification

- `corepack pnpm --filter @polisyos/runtime-api-client run lint`
  `smoke-tested 2026-04-23`

- `corepack pnpm --filter @polisyos/runtime-api-client run format:check`
  `smoke-tested 2026-04-23`

- `corepack pnpm --filter @polisyos/runtime-api-client run typecheck`
  `smoke-tested 2026-04-23`

- `corepack pnpm --filter @polisyos/runtime-api-client run check:architecture`
  `smoke-tested 2026-04-23`

- `corepack pnpm --filter @polisyos/runtime-api-client test`
  `smoke-tested 2026-04-23`

- `corepack pnpm --filter @polisyos/runtime-api-client run test:remediation`
  Checks scratch-only generation, packed Dashboard/Atlas ESM and type imports,
  request serialization, and the binary evidence response.

- `PYTHONPATH=src:. .venv/bin/python -m pytest tests/repo_quality/tools/test_runtime_client_generated_artifact_probe.py -q`
  Regenerates the actual three-file family in a copied workspace, then removes
  a client operation while retaining package exports and verifies the freshness
  checker rejects the missing method.

- `corepack pnpm --filter @polisyos/runtime-api-client run contracts:verify`
  `smoke-tested 2026-04-23`

- `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py`
  `smoke-tested 2026-04-17`

- `corepack pnpm --filter @polisyos/runtime-dashboard run generate:api -- --openapi schemas/runtime_api_v1.openapi.json`
  `smoke-tested 2026-04-17; verifies downstream dashboard type generation still works`

## Reference Docs

- [`../README.md`](../README.md)
- [`../../apps/runtime-reference-shell/README.md`](../../apps/runtime-reference-shell/README.md)
- [`../../docs/reference/api/index.md`](../../docs/reference/api/index.md)
- [`../../docs/reference/api/runs.md`](../../docs/reference/api/runs.md)
- [`../../docs/reference/api/artifacts.md`](../../docs/reference/api/artifacts.md)
- [`../../src/polisyos/runtime/http/README.md`](../../src/polisyos/runtime/http/README.md)

Last updated: 2026-10-06
