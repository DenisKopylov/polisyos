# Generated Index: Dashboard API

Owner: `team-frontend`
Source of truth: `schemas/runtime_api_v1.openapi.json`
Last updated: 2026-05-05

## Files

| Path | Role |
| --- | --- |
| `types.ts` | Generated OpenAPI types. |
| `client.ts`, `http.ts`, `url.ts` | Transport and URL policy. |
| `queryClient.ts`, `queryKeys.ts`, `queryRetryPolicy.ts` | React Query cache policy. |
| `hooks/` | Endpoint/domain hooks consumed by features. |
| `validators.ts` | Runtime validation helpers. |
| `stream.ts`, `runtimeApiEvents.ts` | Streaming/EventSource helpers. |
| `optimistic.ts` | Optimistic mutation helpers. |

## Regeneration

```bash
cd policy-engine
corepack pnpm --filter @polisyos/runtime-dashboard run generate:api
corepack pnpm --filter @polisyos/runtime-dashboard run contracts:verify
```
