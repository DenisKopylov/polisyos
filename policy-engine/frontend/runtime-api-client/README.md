# Runtime API Client (v1)

Generated client package for Runtime HTTP API `/api/v1`.

## Artifacts

- `runtimeApiClient.ts` — typed TypeScript client + contract types.
- `runtimeApiClient.js` — ESM client for browser/runtime usage.

## Regeneration

```bash
uv run --extra multi-tenant --extra test python tools/runtime/export_runtime_openapi.py \
  --output schemas/runtime_api_v1.openapi.json

uv run --extra multi-tenant --extra test python tools/runtime/generate_runtime_client.py \
  --openapi schemas/runtime_api_v1.openapi.json \
  --out-ts frontend/runtime-api-client/runtimeApiClient.ts \
  --out-js frontend/runtime-api-client/runtimeApiClient.js
```

Generation is deterministic: same OpenAPI input produces byte-stable client outputs.
