# Generated Artifacts

> Generated from `architecture/generated_artifacts.toml`.

Every committed generated artifact family must have a source of truth, a regeneration command, a freshness rule, and an approval owner.

| Family | Commit policy | Drift gate | Owner | Outputs |
| --- | --- | --- | --- | --- |
| `ABI schema snapshots` | `committed` | `automated` | `team-polisyos` | `schemas/snapshots/ir`<br/>`schemas/snapshots/fabric` |
| `Runtime OpenAPI snapshot` | `committed` | `automated` | `team-polisyos` | `schemas/runtime_api_v1.openapi.json` |
| `Generated runtime API client` | `committed` | `automated` | `team-polisyos` | `frontend/runtime-api-client/runtimeApiClient.ts`<br/>`frontend/runtime-api-client/runtimeApiClient.js` |
| `Runtime dashboard generated API types` | `committed` | `automated` | `team-polisyos` | `frontend/runtime-dashboard/src/api/types.ts` |
| `Recorded connector fixtures` | `committed` | `manual_review` | `team-polisyos` | `tests/fabric/connectors/sources/fixtures` |
| `Runtime dashboard contract fixtures` | `committed` | `manual_review` | `team-polisyos` | `frontend/runtime-dashboard/src/test/contracts/fixtures` |
| `Benchmark reports and bundle stats` | `mixed` | `manual_review` | `team-polisyos` | `benchmarks/_reports`<br/>`frontend/runtime-dashboard/dist/bundle-stats.json` |
| `Audit and evidence artifacts` | `mixed` | `manual_review` | `team-polisyos` | `docs/archive/reports`<br/>`frontend/runtime-dashboard/npm-audit-report.json`<br/>`frontend/runtime-dashboard/npm-audit-summary.md` |

## `ABI schema snapshots`

- Family id: `abi-schema-snapshots`
- Source of truth: schemas/abi_models.py + src/polisyos/** Pydantic/Enum contracts
- Commit policy: `committed`
- Freshness rule: Regenerate and commit whenever ABI-visible IR or Fabric contracts change.
- Drift gate: `automated`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `.github/workflows/abi.yml`
- Outputs:
  - `schemas/snapshots/ir`
  - `schemas/snapshots/fabric`

Canonical regeneration commands:
```bash
PYTHONPATH=src:. uv run --extra ml python tools/diagnostics/gen_schema.py
```

## `Runtime OpenAPI snapshot`

- Family id: `runtime-openapi-snapshot`
- Source of truth: src/polisyos/runtime/http/** FastAPI app factory and DTO contracts
- Commit policy: `committed`
- Freshness rule: Regenerate and commit whenever runtime routes, request/response DTOs, or OpenAPI examples change.
- Drift gate: `automated`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `.github/workflows/ci.yml`
- Outputs:
  - `schemas/runtime_api_v1.openapi.json`

Canonical regeneration commands:
```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
```

## `Generated runtime API client`

- Family id: `runtime-api-client`
- Source of truth: schemas/runtime_api_v1.openapi.json
- Commit policy: `committed`
- Freshness rule: Regenerate and commit whenever the runtime OpenAPI snapshot changes.
- Drift gate: `automated`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `.github/workflows/ci.yml`
- Outputs:
  - `frontend/runtime-api-client/runtimeApiClient.ts`
  - `frontend/runtime-api-client/runtimeApiClient.js`

Canonical regeneration commands:
```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/generate_runtime_client.py --openapi schemas/runtime_api_v1.openapi.json --out-ts frontend/runtime-api-client/runtimeApiClient.ts --out-js frontend/runtime-api-client/runtimeApiClient.js
```

## `Runtime dashboard generated API types`

- Family id: `runtime-dashboard-api-types`
- Source of truth: schemas/runtime_api_v1.openapi.json
- Commit policy: `committed`
- Freshness rule: Regenerate and commit whenever runtime OpenAPI changes affect dashboard-facing types.
- Drift gate: `automated`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `.github/workflows/ci.yml`
- Outputs:
  - `frontend/runtime-dashboard/src/api/types.ts`

Canonical regeneration commands:
```bash
cd frontend/runtime-dashboard && npm run generate:api
```

## `Recorded connector fixtures`

- Family id: `connector-recorded-fixtures`
- Source of truth: Live upstream connector responses captured through `polisyos-tools data record-fixtures`
- Commit policy: `committed`
- Freshness rule: Refresh intentionally when connector contracts, source profiles, or upstream response shapes change.
- Drift gate: `manual_review`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `polisyos-tools data record-fixtures`
- Outputs:
  - `tests/fabric/connectors/sources/fixtures`

Canonical regeneration commands:
```bash
uv run polisyos-tools data record-fixtures --wave 1
uv run polisyos-tools data record-fixtures --wave 2
uv run polisyos-tools data record-fixtures --wave 3
```

## `Runtime dashboard contract fixtures`

- Family id: `runtime-dashboard-contract-fixtures`
- Source of truth: Live Runtime API responses captured via frontend/runtime-dashboard/scripts/record-runtime-contracts.mjs
- Commit policy: `committed`
- Freshness rule: Refresh when dashboard contract fixtures are intentionally updated to match runtime API behavior.
- Drift gate: `manual_review`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `frontend/runtime-dashboard/scripts/record-runtime-contracts.mjs`
- Outputs:
  - `frontend/runtime-dashboard/src/test/contracts/fixtures`

Canonical regeneration commands:
```bash
cd frontend/runtime-dashboard && npm run contracts:record
```

## `Benchmark reports and bundle stats`

- Family id: `benchmark-reports-and-bundle-stats`
- Source of truth: benchmarks/** runners, frontend/runtime-dashboard/scripts/emit-bundle-stats.mjs, and benchmark publication helpers
- Commit policy: `mixed`
- Freshness rule: Commit benchmark reports only when they serve as intentional baselines, evidence packs, or review artifacts. `frontend/runtime-dashboard/dist/bundle-stats.json` is local by default and is committed only when reviewers explicitly want a checked-in bundle baseline.
- Drift gate: `manual_review`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `.github/workflows/frontend-nightly.yml`
- Outputs:
  - `benchmarks/_reports`
  - `frontend/runtime-dashboard/dist/bundle-stats.json`

Canonical regeneration commands:
```bash
uv run polisyos-tools benchmarks run-all
cd frontend/runtime-dashboard && npm run bundle:stats
```

## `Audit and evidence artifacts`

- Family id: `audit-and-evidence-artifacts`
- Source of truth: Dedicated audit/report generators such as frontend/runtime-dashboard/scripts/run-audit.mjs and curated evidence/report pipelines
- Commit policy: `mixed`
- Freshness rule: Only intentionally reviewed evidence packs and audit outputs stay committed; transient local diagnostics such as raw audit captures remain ignored.
- Drift gate: `manual_review`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `frontend/runtime-dashboard/scripts/run-audit.mjs`
- Outputs:
  - `docs/archive/reports`
  - `frontend/runtime-dashboard/npm-audit-report.json`
  - `frontend/runtime-dashboard/npm-audit-summary.md`

Canonical regeneration commands:
```bash
cd frontend/runtime-dashboard && npm run audit:ci
```
