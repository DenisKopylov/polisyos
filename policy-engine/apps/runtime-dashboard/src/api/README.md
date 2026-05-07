# Dashboard API Boundary

Owner: `team-frontend`
Backup owner: `team-runtime`
Last updated: 2026-05-05

## Purpose

`src/api` owns the dashboard's Runtime API client boundary: HTTP transport,
query keys, React Query hooks, validators, streaming helpers, optimistic
updates, and generated OpenAPI types.

## Public API

Feature modules consume API through `hooks/`, `queryKeys.ts`, and typed exports
from `types.ts`. Direct `fetch` calls and backend deep imports are not allowed
in feature modules.

## Internal Layout

| Path | Role |
| --- | --- |
| `client.ts`, `http.ts`, `url.ts` | HTTP transport and base URL policy. |
| `hooks/` | React Query hooks by runtime endpoint/domain. |
| `queryKeys.ts`, `queryClient.ts` | Cache key and client policy. |
| `types.ts` | Generated OpenAPI type surface. |
| `validators.ts` | Runtime payload validation. |
| `stream.ts`, `runtimeApiEvents.ts` | Streaming and event helpers. |

## Extension Points

New backend endpoints add generated types first, then hook/query-key wrappers.
Route-only diagnostics must be documented if they intentionally bypass the
generated client.

## Tests

Use colocated `*.test.ts(x)` files in `src/api/` or `src/api/hooks/`. Contract
fixture tests use `src/test/contracts/`.

## Operability Links

- `docs/reference/api/index.md`
- `docs/how-to/update-runtime-dashboard-api-client.md`
- `docs/runbooks/broken-contract-generation.md`

## Known Shims/Deprecations

Generated client compatibility follows `architecture/extension_points.toml`
deprecation windows for JS package API. Old hook names need wrappers or release
notes before removal.
