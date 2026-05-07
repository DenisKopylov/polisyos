# Runtime Dashboard Test Helpers And Fixtures

Owner: `team-frontend`
Last updated: 2026-05-05

## Purpose

`src/test` contains dashboard-local test helpers, accessibility helpers, MSW
mocks, contract fixtures, and generated-client drift fixtures used by Vitest
and frontend contract checks.

## Public API

Only test code imports this subtree. Production source must not import
`src/test/**`.

## Internal Layout

| Path | Role |
| --- | --- |
| `a11y/` | Accessibility test helpers. |
| `contracts/` | Runtime API fixture and contract verification helpers. |
| `contracts/fixtures/` | Reviewed JSON API payload fixtures. |
| `msw/` | Mock Service Worker setup and handlers. |

## Extension Points

Add fixtures only when a runtime contract, hook, or user journey consumes them.
New mock handlers should mirror generated API types.

## Tests

Consumed by colocated Vitest tests, `pnpm --filter @polisyos/runtime-dashboard run test:contracts`, and frontend smoke checks.

## Operability Links

- `docs/runbooks/broken-contract-generation.md`
- `docs/how-to/update-runtime-dashboard-api-client.md`
- `docs/reference/frontend/workspace-contract.md`

## Known Shims/Deprecations

Fixture shape changes require backend/OpenAPI and generated type updates in the
same change or an explicit compatibility note.
