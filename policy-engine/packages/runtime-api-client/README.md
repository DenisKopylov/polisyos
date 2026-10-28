# Runtime API Client

## Purpose

`runtime-api-client` stores the generated JavaScript and TypeScript client for
Runtime API v1. It is the lightest consumer surface in the frontend tree: a
thin wrapper over the OpenAPI contract that exposes selected runtime operations
without React, Vite, or dashboard-specific state management.

This package is the canonical generated-client home selected by Atlas DS3.
Do not edit `types.ts`, `canonicalRuntimeApiClient.ts`, or
`canonicalRuntimeApiClient.js` by hand. Their
shared source of truth is the runtime OpenAPI schema. The package-root export is
the canonical twin: its generated DTO aliases normally point directly at the
discriminated schema types in `types.ts`. If a schema's generated name collides
with an established package-root support alias, the root alias keeps its existing
contract; the schema remains available through the package's `types.ts`
`components` export. The low-level `runtimeApiClient.*` pair is generated only in
a private scratch directory and handed to the canonicalizer; it is not a
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

- Generators:
  [`scripts/generate-runtime-api-client.sh`](scripts/generate-runtime-api-client.sh)
  and the dashboard's
  [`generate-api-client.sh`](../../apps/runtime-dashboard/scripts/generate-api-client.sh)
  both call [`scripts/generate-openapi-types.mjs`](scripts/generate-openapi-types.mjs)
  for the same source-derived request and response projections. The generator
  preserves OpenAPI presence semantics: a `default: null` property becomes
  optional in generated TypeScript only when its schema admits null and the
  containing schema does not require it. Explicitly required nullable fields
  remain required, and the generator does not rewrite the OpenAPI document or
  server behavior. Null admission is evaluated for OpenAPI 3.1 using boolean
  schemas, local `$ref` targets with sibling conjunctions, `type`, `const`,
  `enum`, `allOf`, `anyOf`, `oneOf`, `not`, and `if`/`then`/`else`. A `oneOf`
  null branch counts only when exactly one branch accepts null. Cyclic/dynamic references, inherited resource scopes (`$id`, `$schema`, `$anchor` and related keywords), custom vocabularies, and non-default document dialects stay required rather than being guessed optional. The resource-context scan covers the complete OpenAPI 3.1 schema graph, including nested `contentSchema` schemas; unresolved or invalid local references retain the
  generator's existing hard error. This is a narrow null-admission decision,
  not a general JSON Schema validator. The runtime entrypoint also composes the
  private raw-client handoff and canonicalizer;
  the dashboard formats its compatibility file with its existing Prettier step.
  Only `types.ts` and the canonical TS/JS pair are written under the output root.

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

## Registered source and cancellation transport

The generated client exposes the Runtime API's registered SQL registration,
materialization, and withdrawal POSTs and control-job cancellation POST from the
server-owned OpenAPI contract. The request bodies and successful response types
come from that contract. Callers provide their existing authentication and tenant
headers through `RuntimeApiClient` options; the client forwards them and does
not create credentials or verify authorization. The Runtime routes retain their
resource-bound permission checks. A forwarded source receipt does not establish
external database currentness. An accepted cancellation fences publication;
submitting a request does not prove that physical work stopped. Failed HTTP responses retain
the existing client error behavior.

Regenerate the client family and dashboard types when the OpenAPI schema or the
client operation allowlist changes. Regeneration alone does not establish a
server grant, a source act, or a complete dashboard workflow.

## Method-metric comparison transport

`getRunMethodMetricComparison` reads the run-scoped candidate comparison. Its
response may contain no comparison or a `verification_missing` or `invalid`
comparison; consumers must carry its status and limitations rather than infer
that a comparison is verified. The comparison is `candidate_only` and requires
revalidation. This client forwards caller-supplied headers; the server owns the
run, tenant, cell, and permission checks. A client transport response alone
does not establish candidate feasibility or independent authority.

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
  override with an isolated schema mutation.

- `corepack pnpm --filter @polisyos/runtime-api-client run contracts:verify`
  `smoke-tested 2026-04-23`

- `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json`
  `conceptual/manual; rewrites the checked-in OpenAPI snapshot`

- `corepack pnpm --dir packages/runtime-api-client run generate -- --openapi schemas/runtime_api_v1.openapi.json`
  Replays schema types, the private raw handoff, and the public canonical twin
  in one command after exporting the OpenAPI schema. Pass
  `--output-root /absolute/scratch/root` to keep the three committed outputs
  isolated.
  Set `POLISYOS_RETAIN_GENERATOR_SCRATCH=1` to retain the intermediate raw
  client files for local evidence. The generator prints their scratch path to
  stderr; set `TMPDIR` to an ignored evidence directory when retaining them.

- `node packages/runtime-api-client/scripts/generate-openapi-types.mjs --openapi schemas/runtime_api_v1.openapi.json --output /absolute/scratch/types.ts`
  Runs the lock-pinned `openapi-typescript` API and shared request-direction
  normalizers. It derives request-only, response-only, and shared schema roles
  from operation and reusable-component references. Defaults do not override a
  request schema's `required` list; shared schemas get private input views while
  their response projection stays on the original component. Required names in
  request-side constraint-only schemas are materialized as required properties
  using the source `additionalProperties` schema, preserving composition
  requiredness instead of emitting an impossible `Record<string, never>`.
  Contradictory required names excluded by `additionalProperties: false`,
  references to non-schema OpenAPI objects, and unresolved external references
  in request or response schema graphs fail explicitly.

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

Last updated: 2026-10-10

The generated runs operation group also includes POST and GET for the run-bound predictive-calibration candidate diagnostic. Regenerate both client surfaces from the OpenAPI schema after changing its request or response contract; the client is transport only and carries no predictive or causal authority.
