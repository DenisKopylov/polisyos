# `runtime-dashboard` — Runtime API frontend (Phases 0-8)

`runtime-dashboard` is the React/TypeScript frontend entrypoint for Runtime API v1.

## Implemented scope (Phases 0-8)

- App shell with sidebar/header/content layout.
- Health status indicator (`GET /api/v1/health`).
- Run explorer (`GET /api/v1/runs`) with:
  - filters (`status`, `from`, `to`, local `run_id` search),
  - cursor pagination (`next/prev`),
  - empty/error states.
- Run detail (`GET /api/v1/runs/{run_id}`) with tabs:
  - `Timeline` (`GET /api/v1/runs/{run_id}/timeline`),
  - `Nodes` (`GET /api/v1/runs/{run_id}/nodes`),
  - `Lineage` (`GET /api/v1/runs/{run_id}/lineage`) + graph view,
  - `Agents` (`GET /api/v1/runs/{run_id}/agents`) with attempt timeline and prompt/response drill-down,
  - `Workflow` (`GET /api/v1/runs/{run_id}/workflow`) with DAG + timing heatmap + dependency table,
  - `Governance` (`GET /api/v1/debug/runs/{run_id}/governance`) with issue drill-down,
  - `Debug` (`GET /api/v1/debug/runs/{run_id}/nodes/{alias}` + `.../errors`),
  - `Decision` (decision artifact rendering from run roots, with linked `decision_card_ref` fallback).
- Artifact inspector (`GET /api/v1/artifacts/{artifact_id}`) with tabs:
  - `Content` (`.../content`) + preview-size controls via `max_bytes`,
  - `Schema` (`.../schema`),
  - `Lineage` (`.../lineage`) + graph view.
- Trinity Visualizer (Phase 3):
  - dedicated `TrinityCard` WHY/WHAT/HOW view,
  - intervention drill-down,
  - best-effort intervention diff when prior bundle is present in payload.
- Simulation Results Viewer (Phase 4):
  - normalized metrics extraction across simulation artifact kinds,
  - time-series charts (single, baseline/policy, observed/fitted),
  - uncertainty overlay toggle,
  - distributional panel (gini + cohort delta chart),
  - calibration report panel (loss, fit quality, params, observed vs fitted).
- Governance & Debug Panel (Phase 5):
  - governance verdict + issue severity summary,
  - node-level debug panel with cache/timeline/artifact context,
  - run errors panel grouped by source.
- Decision Dashboard (Phase 6):
  - run-level decision card rendering (from `scientist.decision_card` or derived from `scientist.decision_packet`),
  - overview dashboard with success rate, duration trend, status ratio,
  - quick links to failed runs and direct governance/debug/decision tabs.
- Agent Pipeline Viewer (Phase 7):
  - best-effort extraction from `decision_packet.audit_trail` with timeline fallback,
  - attempt grouping and verdict derivation,
  - step-level prompt/response + token/latency inspector.
- Workflow DAG Viewer (Phase 8):
  - DAG extracted from `scientist.workflow_spec` + merged statuses from `scientist.workflow_report` and timeline,
  - computed depth + critical path duration,
  - heat overlay by node duration and direct links to node debug.
- Typed API layer via `openapi-fetch` + generated OpenAPI types.
- Runtime response validation with `zod` on all active read paths.
- Unified frontend error handling for `application/problem+json`.

## Commands

```bash
npm install
npm run generate:api
npm run typecheck
npm run dev
```

Optional mock mode:

```bash
npm run dev:mock
```

## API type generation

`src/api/types.ts` must be generated from the canonical OpenAPI file:

```bash
./scripts/generate-api-client.sh
```

The script reads:

- `schemas/runtime_api_v1.openapi.json`

And writes:

- `frontend/runtime-dashboard/src/api/types.ts`

## Runtime API URL

- Dev proxy target defaults to `http://127.0.0.1:8000`.
- Override with environment variable `RUNTIME_API_URL` for Vite proxy.
- For direct fetch base URL, set `VITE_RUNTIME_API_URL` when needed.

## Contract guardrails

- API calls are typed at compile-time.
- `zod` schemas enforce runtime payload shape for early drift detection.
- Backend CI also runs `tools/runtime/check_runtime_api_contract.py`.
