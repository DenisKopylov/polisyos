# Runtime Reference Shell

## Purpose

`runtime-reference-shell` is a static diagnostics UI for Runtime API v1. It is
useful when you need a fast manual read-path check without starting the full
dashboard toolchain: serve three static files, point them at a runtime base URL,
and inspect runs, timelines, node debug payloads, and artifact responses.

This package is intentionally narrow. It is not the product UI and it does not
cover the dashboard's full control-plane surface.

## Where to Start

- Static document and page layout:
  [`index.html`](index.html)

- Browser logic and API bindings:
  [`app.js`](app.js)

- Styling and responsive layout:
  [`styles.css`](styles.css)

- Generated API dependency:
  [`../runtime-api-client/runtimeApiClient.js`](../runtime-api-client/runtimeApiClient.js)

## Public Entrypoints

- Page entry: [`index.html`](index.html)
- UI bootstrap and event wiring: [`app.js`](app.js)
- Imported API client:
  [`../runtime-api-client/runtimeApiClient.js`](../runtime-api-client/runtimeApiClient.js)

- Default runtime base URL in [`app.js`](app.js): `http://127.0.0.1:8000`

## Dependencies

- Depends on:
  [`../runtime-api-client/`](../runtime-api-client/README.md),
  a browser with `fetch`, a static file server, and a reachable Runtime API

- Depended on by:
  manual diagnostics, post-regeneration smoke checks for the generated client,
  and contributors who need an API-only fallback when the full dashboard is not
  the right tool

## Common Commands

- `cd frontend/runtime-reference-shell && npm run lint`
  `smoke-tested 2026-04-23`

- `cd frontend/runtime-reference-shell && npm run format:check`
  `smoke-tested 2026-04-23`

- `cd frontend/runtime-reference-shell && npm run typecheck`
  `smoke-tested 2026-04-23`

- `cd frontend/runtime-reference-shell && npm run check:architecture`
  `smoke-tested 2026-04-23`

- `cd frontend/runtime-reference-shell && python3 -m http.server 4173`
  `smoke-tested 2026-04-17`

- Launch the Runtime API with the local command documented in
  [`../README.md`](../README.md)
  `conceptual/manual; keep the shell pointed at a reachable Runtime API base URL`

## Test And Verification

- `cd frontend/runtime-reference-shell && npm run lint`
  `smoke-tested 2026-04-23`

- `cd frontend/runtime-reference-shell && npm run format:check`
  `smoke-tested 2026-04-23`

- `cd frontend/runtime-reference-shell && npm run typecheck`
  `smoke-tested 2026-04-23`

- `cd frontend/runtime-reference-shell && npm run check:architecture`
  `smoke-tested 2026-04-23`

- `curl -I http://127.0.0.1:4173/index.html`
  `smoke-tested 2026-04-17 while the local shell server was running`

- Open `http://127.0.0.1:4173`, set `API Base URL`, and load `Run List`
  `conceptual/manual`

- After Runtime API changes, re-run the generated client checks in
  [`../runtime-api-client/README.md`](../runtime-api-client/README.md)
  `conceptual/manual`

## Reference Docs

- [`../README.md`](../README.md)
- [`../runtime-api-client/README.md`](../runtime-api-client/README.md)
- [`../../docs/reference/api/index.md`](../../docs/reference/api/index.md)
- [`../../docs/reference/api/runs.md`](../../docs/reference/api/runs.md)
- [`../../docs/reference/api/artifacts.md`](../../docs/reference/api/artifacts.md)

Last updated: 2026-04-23
