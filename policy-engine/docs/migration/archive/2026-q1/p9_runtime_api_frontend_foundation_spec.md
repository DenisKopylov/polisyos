# P9 Runtime API + Frontend Foundation - Detailed Specification

- Status: Implemented
- Version: 0.1
- Effective phase: P9 (`2026-05-25` -> `2026-06-07`)
- Hard deadline for legacy dashboard cutover from critical path: `2026-08-31`
- Scope: `policy-engine`
- Owners: `team-runtime` (primary), `team-scientist`, `team-core`, `team-security`, `team-platform-ui`
- Related docs:
  - `p8_foundry_data_plane_spec.md`
  - `p7_connector_platform_hardening_spec.md`
  - `p1_refactor_queue.md`
  - `src/polisyos/runtime/README.md`
  - `src/polisyos/runtime/http/cell_router_middleware.py`
  - `src/polisyos/runtime/http/jwt_auth_middleware.py`
  - `src/polisyos/runtime/http/authz_middleware.py`
  - `src/polisyos/core/run/context.py`
  - `src/polisyos/scientist/engine/executor.py`
  - `src/polisyos/core/artifacts/store.py`
  - `dashboard.py`

Implementation closure: `2026-02-10`

## 1. Context and Problem Statement

After P8, data-plane contracts and replay completeness are in place, but runtime observability surfaces for product-level debugging are still fragmented.

Current hard gaps:

| Area | Current state | Impact |
| --- | --- | --- |
| Runtime HTTP surface | `src/polisyos/runtime/http/*` provides only middleware (auth, tenant routing, authz), no API routes | UI cannot consume stable run/debug data via HTTP |
| Run metadata model split | Legacy runtime manifests (`runs/<id>/manifest.json`) coexist with CAS-native `core.run_manifest` + `trace.jsonl` | Run exploration requires format-specific file parsing |
| Debug workflow introspection | Node outcomes/errors/governance details are spread across `trace.jsonl`, `scientist.workflow_report`, and DecisionPacket payloads | Engineers rely on manual log/artifact digging |
| Artifact inspection | CAS manifests and payload previews are not exposed via tenant-scoped API | No safe UI path for artifact metadata/content inspection |
| Frontend entrypoint | Top-level `dashboard.py` is a direct DB/script path | Critical debugging path bypasses runtime contracts and access controls |

Observed baseline (`2026-02-10`, local scan):

1. Architecture snapshot from `tools/lint/collect_arch_metrics.py`:
   - `package_cycles_count = 0`
   - `import_violations_count = 0`
   - `test_collect_errors_count = 46`
   - `stale_sources_missing_paths_count = 40`
2. Freeze compare against historical baseline (`summary.json`) currently fails only on:
   - `delta_test_collect_errors = +4` (pre-existing, not P9-specific)
3. Runtime HTTP route surface:
   - middleware modules present: `3`
   - API routers/endpoints under `src/polisyos/runtime/http`: `0`
4. Legacy runtime run sample exists:
   - `runs/test_004/manifest.json` (legacy schema with `artifacts[]`, `run_root`, `budgets`)

Net effect: architecture-level import DAG is clean, but there is no stable API contract for run explorer, node debugging, and artifact inspection that a production frontend can depend on.

## 2. Goals and Non-Goals

### 2.1 Goals (MUST)

1. Introduce a versioned, tenant-scoped Runtime HTTP API (`/api/v1`) that supports:
   - Run Explorer (`runs`, `timeline`, `nodes`, `lineage`),
   - Debug (`node inputs/outputs/errors/governance details`),
   - Artifact Inspector (`manifest`, `content preview`, `transitive lineage`).
2. Define typed API contracts in `core/contracts` for request/response payloads (no ad-hoc dict responses).
3. Provide a canonical run read model that merges CAS-native and legacy runtime run formats via explicit adapters.
4. Ensure API-only frontend debugging path (no direct FS/DB access in UI critical path).
5. Move top-level `dashboard.py` to demo-only status and remove it from critical runtime workflow guidance.
6. Preserve one-release compatibility for legacy run metadata shape and legacy runtime helper flows.
7. Enforce security invariants through existing runtime middleware and explicit resource-level checks.

### 2.2 Non-Goals (P9)

1. Full redesign of Scientist execution engine or node protocol.
2. Replacing Grafana/Prometheus operational dashboards in `ops/`.
3. Introducing write/mutate runtime APIs for workflow execution control (P9 is read-first).
4. Migrating all legacy runtime APIs (`polisyos.runtime.api`) out of tree in this phase.
5. Building a full product frontend; P9 delivers foundation and reference shell.

## 3. Normative Language

This document uses:

- `MUST` / `MUST NOT` for hard requirements.
- `SHOULD` / `SHOULD NOT` for strong recommendations.
- `MAY` for optional behavior.

## 4. Target Architecture Contract

### 4.1 Runtime HTTP service contract

P9 MUST introduce a runtime API application factory under `src/polisyos/runtime/http/`:

1. API prefix: `/api/v1`.
2. Read-only scope in P9: `GET` endpoints only for run/debug/artifact views.
3. Middleware stack integration:
   - `JWTAuthMiddleware`
   - `CellRouterMiddleware`
   - `AuthzMiddleware`
4. Public paths remain limited to readiness/health/metrics.

### 4.2 Canonical run read model

P9 MUST define `RunRecordV1` as canonical response shape independent of storage source.

Supported source adapters:

1. CAS-native run:
   - `core.run_manifest` (loaded from CAS via run trace resolution),
   - run-local `trace.jsonl` for timeline and event drilldown.
2. Legacy runtime run:
   - `runs/<run_id>/manifest.json` (`polisyos.runtime.manifest.RunManifest` shape).

Hard requirements:

1. Responses MUST include a `source_kind` marker (`core_run` or `legacy_runtime`).
2. Source adapters MUST produce consistent normalized fields:
   - `run_id`, `status`, `started_at`, `finished_at`, `duration_ms`, `tenant_id`, `cell_id`.
3. Run listing order MUST be deterministic (`started_at desc`, tie-breaker `run_id asc`).

### 4.3 Run Explorer API contract

P9 MUST provide the following endpoints:

1. `GET /api/v1/runs`
   - query: `limit`, `cursor`, `status`, `from_ts`, `to_ts`
   - response: paged `RunSummary` list.
2. `GET /api/v1/runs/{run_id}`
   - response: `RunDetails` (normalized run metadata + key refs).
3. `GET /api/v1/runs/{run_id}/timeline`
   - response: timeline summary + ordered events.
4. `GET /api/v1/runs/{run_id}/nodes`
   - response: node run records (status/duration/errors/artifacts).
5. `GET /api/v1/runs/{run_id}/lineage`
   - response: condensed transitive dependency graph for selected root artifact(s).

### 4.4 Debug API contract

P9 MUST expose node-level and governance-oriented debugging endpoints:

1. `GET /api/v1/debug/runs/{run_id}/nodes/{alias}`
   - includes node status, error payload, emitted artifacts, timeline spans, cache diagnostics.
2. `GET /api/v1/debug/runs/{run_id}/governance`
   - includes governance verdict/issues/notes plus validation-trace summary when available.
3. `GET /api/v1/debug/runs/{run_id}/errors`
   - includes structured run-level and node-level error list with trace correlations.

Debug data MUST come from canonical artifacts (`scientist.workflow_report`, DecisionPacket, governance report, trace records), not ad-hoc parsing of raw logs only.

### 4.5 Artifact Inspector API contract

P9 MUST expose CAS artifact metadata and safe preview surfaces:

1. `GET /api/v1/artifacts/{artifact_id}`
   - manifest metadata, schema info, integrity fields, producer/environment details.
2. `GET /api/v1/artifacts/{artifact_id}/content`
   - content preview with strict size limits and truncation metadata.
3. `GET /api/v1/artifacts/{artifact_id}/lineage`
   - transitive graph summary (`nodes`, `edges`, missing/corrupted flags).
4. `GET /api/v1/artifacts/{artifact_id}/schema`
   - normalized schema descriptor for UI rendering/inspection.

### 4.6 Security and isolation invariants

1. All non-public endpoints MUST enforce authenticated access scope.
2. Run/artifact access MUST be tenant-scoped:
   - cross-tenant access MUST return deny response (`403` or obscured `404`, policy-defined).
3. API MUST NOT expose arbitrary filesystem paths in responses.
4. Artifact content preview MUST enforce configurable byte cap and redaction hooks for sensitive payload classes.
5. Debug responses MUST avoid leaking raw secrets/tokens from node error details.

### 4.7 Frontend foundation contract

P9 frontend foundation MUST include:

1. OpenAPI-described runtime API surface (`runtime_api_v1`).
2. Generated typed client package for UI consumption (single source of truth from OpenAPI/contracts).
3. Reference UI shell with pages:
   - Run list,
   - Run timeline + node graph,
   - Node debug panel,
   - Artifact inspector panel.
4. No direct DB (`duckdb`) or direct filesystem access in reference UI runtime path.

## 5. Detailed Technical Design

### 5.1 Contract layer additions

Required new module:

- `src/polisyos/core/contracts/runtime.py`

Required model groups:

1. Common:
   - `RuntimeApiError`
   - `CursorPage`
   - `ApiMeta` (request id, timestamp, source markers).
2. Run Explorer:
   - `RunSummary`
   - `RunDetails`
   - `RunTimelineSummary`
   - `RunTimelineEvent`
   - `RunNodeRecord`.
3. Debug:
   - `NodeDebugView`
   - `GovernanceDebugView`
   - `RunErrorView`.
4. Artifact Inspector:
   - `ArtifactManifestView`
   - `ArtifactContentPreview`
   - `ArtifactLineageView`.

Constraints:

1. Contracts MUST be `pydantic` models with `extra="forbid"`.
2. JSON-friendly scalar-only fields for event attrs/metrics where possible.
3. Artifact references in responses SHOULD preserve typed `ArtifactRef` semantics.

### 5.2 Runtime HTTP application structure

Required modules (recommended split):

1. `src/polisyos/runtime/http/app.py`
   - FastAPI app factory,
   - middleware wiring,
   - route registration.
2. `src/polisyos/runtime/http/dependencies.py`
   - CAS/store/run-index dependency providers,
   - access-scope enforcement helpers.
3. `src/polisyos/runtime/http/routes/runs.py`
4. `src/polisyos/runtime/http/routes/debug.py`
5. `src/polisyos/runtime/http/routes/artifacts.py`
6. `src/polisyos/runtime/http/routes/health.py`
7. `src/polisyos/runtime/http/errors.py`
   - deterministic error envelope mapping.

### 5.3 Run indexing and adapter layer

Required new service modules:

1. `src/polisyos/runtime/http/services/run_index.py`
   - discover run directories,
   - normalize run records via adapters,
   - provide cursor-based listing.
2. `src/polisyos/runtime/http/services/adapters/core_run.py`
3. `src/polisyos/runtime/http/services/adapters/legacy_runtime.py`

Hard requirements:

1. No implicit mutation of run metadata during read.
2. Adapter failures MUST be isolated per run and surfaced as warning diagnostics.
3. Listing latency SHOULD be bounded via index caching with explicit invalidation policy.

### 5.4 Timeline and node debug assembly

Required service modules:

1. `src/polisyos/runtime/http/services/timeline.py`
2. `src/polisyos/runtime/http/services/debug.py`

Timeline requirements:

1. Trace parsing MUST preserve event order by timestamp, then file position.
2. Node duration derivation MUST be deterministic.
3. Summary MUST include:
   - `duration_ms`,
   - event count,
   - node status counts,
   - cache hit/store/bypass counts when present.

Debug requirements:

1. Node debug view MUST combine:
   - workflow report record,
   - matching trace events,
   - node artifacts (inputs/outputs),
   - normalized error details.
2. Governance endpoint MUST prefer canonical governance artifact, with DecisionPacket fallback.

### 5.5 Artifact inspector services

Required service modules:

1. `src/polisyos/runtime/http/services/artifact_inspector.py`
2. `src/polisyos/runtime/http/services/lineage.py`

Requirements:

1. Manifest endpoint MUST resolve and return `ArtifactManifest` fields exactly.
2. Content preview endpoint MUST:
   - enforce max-bytes threshold,
   - provide `truncated=true|false`,
   - indicate parse mode (`json`, `text`, `binary`).
3. Lineage endpoint MUST build graph via `resolve_dependency_graph(...)` with configurable bounds (`max_depth`, `max_nodes`).

### 5.6 API observability and reliability

P9 runtime API MUST emit request-level telemetry:

1. request duration,
2. endpoint status code counts,
3. error code distribution,
4. tenant/cell dimensions (where policy allows),
5. route-level saturation metrics.

Failure handling requirements:

1. Typed error envelopes for all handled exceptions.
2. Timeouts and cancellation propagation for heavy lineage queries.
3. Payload-size limits and response compression policy for timeline endpoints.

### 5.7 Frontend foundation deliverables

Required artifacts:

1. OpenAPI export for runtime v1.
2. Typed client generation script (deterministic output, checked in or reproducibly generated).
3. Reference UI shell (workspace path to be agreed during implementation) with:
   - list/detail navigation for runs,
   - timeline visualization,
   - node debug panel,
   - artifact inspector.

Contract requirements:

1. UI data layer MUST only call runtime HTTP API.
2. UI MUST tolerate missing optional artifacts (graceful degraded states).
3. UI MUST show explicit source marker for legacy-adapted runs.

### 5.8 Dashboard cutover and compatibility

P9 compatibility path:

1. `dashboard.py` remains available as demo utility for one release.
2. Production docs and critical runbook paths MUST point to runtime API + reference UI.
3. Any new debugging feature MUST land in runtime API first; dashboard script MAY consume API but MUST NOT become source of truth.

## 6. Migration Plan (2 Weeks)

### 6.1 Milestones

1. `M1` (`2026-05-25` -> `2026-05-27`):
   - contract models + app skeleton + run adapters.
2. `M2` (`2026-05-27` -> `2026-05-31`):
   - Run Explorer endpoints (`runs`, `details`, `timeline`, `nodes`).
3. `M3` (`2026-05-31` -> `2026-06-04`):
   - Debug + Artifact Inspector endpoints + authz hardening + lineage limits.
4. `M4` (`2026-06-05` -> `2026-06-07`):
   - frontend typed client + reference shell + docs/CI/governance closure.

### 6.2 PR slicing (recommended)

1. `PR-A`: contracts + app bootstrap + adapter layer.
2. `PR-B`: run explorer and timeline services/routes/tests.
3. `PR-C`: debug and artifact inspector routes/services/tests.
4. `PR-D`: frontend foundation, docs cutover, CI/lint/governance updates.

## 7. CI and Governance Updates

### 7.1 Mandatory artifact updates

1. `p1_refactor_queue.md`
   - add/track P9 work item (recommended `Q10`) with owner and due date.
2. `p9_runtime_api_frontend_foundation_spec.md`
   - status progression (`Proposed` -> `Implemented`) with implementation evidence section when closed.
3. `README.md`
   - runtime/debugging guidance updated to API-first path; `dashboard.py` marked demo-only.
4. `src/polisyos/runtime/README.md`
   - add runtime HTTP route map and API usage examples.

### 7.2 Required verification commands

Architecture/freeze checks:

```bash
python3 tools/lint/collect_arch_metrics.py \
  --repo-root . \
  --output-dir .tmp/p9_metrics \
  --summary-path .tmp/p9_metrics/summary.json \
  --print-summary

python3 tools/lint/compare_baseline.py \
  --baseline summary.json \
  --current .tmp/p9_metrics/summary.json \
  --mode blocking \
  --exceptions import_exceptions.toml \
  --exceptions-registry import_exceptions_registry.md \
  --baseline-import-gate import_gate.txt \
  --current-import-gate .tmp/p9_metrics/import_gate.txt \
  --debt-register import_debt_register.csv
```

Runtime API test suite (minimum):

```bash
python3 -m pytest \
  tests/runtime/http/test_runs_api.py \
  tests/runtime/http/test_timeline_api.py \
  tests/runtime/http/test_debug_api.py \
  tests/runtime/http/test_artifact_inspector_api.py \
  tests/runtime/http/test_runtime_api_authz.py \
  tests/runtime/http/test_legacy_manifest_adapter.py
```

Existing middleware regression suite (must remain green):

```bash
python3 -m pytest \
  tests/core/security/test_router.py \
  tests/core/security/test_auth_middlewares.py
```

## 8. Acceptance Criteria and DoD

P9 is complete only if all criteria are met:

1. Runtime HTTP API v1 exposes Run Explorer, Debug, and Artifact Inspector endpoints with typed contracts.
2. UI foundation can render run timeline and node debug data using API only (no direct FS/DB reads).
3. Artifact inspector provides deterministic manifest and lineage views with bounded payload behavior.
4. Tenant and authz checks are enforced end-to-end on runtime API resources.
5. Legacy run manifests are supported through adapter path with explicit source markers.
6. `dashboard.py` is no longer in critical-path docs and is clearly marked demo-only.
7. P9-targeted tests and middleware regression tests pass.
8. Architecture freeze shows no additional regressions relative to pre-P9 current state.

## 9. Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Dual run formats drift (`core_run` vs `legacy_runtime`) | High | Explicit adapters, source markers, contract tests per format |
| Large traces/artifact graphs overload API | High | Cursor pagination, max-depth/max-node guards, timeout/cancellation policies |
| Sensitive data leakage via preview/debug endpoints | High | Authz filters, redaction hooks, payload-size caps, deny-by-default content modes |
| Optional FastAPI deps absent in some envs | Medium | Optional dependency guard + clear startup diagnostics + CI job with `multi-tenant` extras |
| Freeze baseline mismatch due historical `summary.json` | Medium | Track known `delta_test_collect_errors +4` as pre-existing and block further regressions |

## 10. Post-P9 Follow-Ups (Out of Scope)

1. Add write APIs for controlled replay execution and run orchestration (`POST /replay`, `POST /runs`) after security review.
2. Remove legacy `polisyos.runtime.api` manifest path once cutover window closes.
3. Promote reference UI shell to product UI with SSO/session flows and role-based feature gating.
4. Expand artifact inspector with schema-aware diff and side-by-side replay comparison.

## 11. Baseline Snapshot for P9 Planning (`2026-02-10`)

Reference snapshot (fresh local scan, `tools/lint/collect_arch_metrics.py`):

- `package_cycles_count = 0`
- `import_violations_count = 0`
- `test_collect_errors_count = 46`
- `stale_sources_missing_paths_count = 40`

Freeze compare status against historical `summary.json`:

- `compare_baseline.py --mode blocking`: `FAIL`
- reason: `delta_test_collect_errors = +4` (pre-existing debt outside P9 scope)

P9-specific baseline observations:

1. `src/polisyos/runtime/http/*` contains middleware only; no API routers/endpoints are implemented.
2. Runtime run metadata is split between:
   - legacy file manifests (`runs/<id>/manifest.json`),
   - CAS-native `core.run_manifest` + `trace.jsonl` workflow outputs.
3. Node-level debug information is present but fragmented:
   - `scientist.workflow_report` artifacts,
   - run trace events in `trace.jsonl`,
   - DecisionPacket partial summaries.
4. Top-level `dashboard.py` remains a direct script/DB dashboard and is still referenced in docs.

## 12. Implementation Evidence (`2026-02-10`)

Implemented artifacts:

1. Runtime API application + routes:
   - `src/polisyos/runtime/http/app.py`
   - `src/polisyos/runtime/http/dependencies.py`
   - `src/polisyos/runtime/http/errors.py`
   - `src/polisyos/runtime/http/routes/runs.py`
   - `src/polisyos/runtime/http/routes/debug.py`
   - `src/polisyos/runtime/http/routes/artifacts.py`
   - `src/polisyos/runtime/http/routes/health.py`
2. Canonical contracts:
   - `src/polisyos/core/contracts/runtime.py`
3. Adapters/services:
   - `src/polisyos/runtime/http/services/run_index.py`
   - `src/polisyos/runtime/http/services/adapters/core_run.py`
   - `src/polisyos/runtime/http/services/adapters/legacy_runtime.py`
   - `src/polisyos/runtime/http/services/timeline.py`
   - `src/polisyos/runtime/http/services/debug.py`
   - `src/polisyos/runtime/http/services/artifact_inspector.py`
   - `src/polisyos/runtime/http/services/lineage.py`
4. Frontend foundation:
   - OpenAPI export: `schemas/runtime_api_v1.openapi.json`
   - Client generation scripts:
     - `tools/runtime/export_runtime_openapi.py`
     - `tools/runtime/generate_runtime_client.py`
   - Generated typed client:
     - `frontend/runtime-api-client/runtimeApiClient.ts`
     - `frontend/runtime-api-client/runtimeApiClient.js`
   - Reference UI shell:
     - `frontend/runtime-reference-shell/index.html`
     - `frontend/runtime-reference-shell/app.js`
     - `frontend/runtime-reference-shell/styles.css`
5. Test coverage:
   - `tests/runtime/http/test_runs_api.py`
   - `tests/runtime/http/test_timeline_api.py`
   - `tests/runtime/http/test_debug_api.py`
   - `tests/runtime/http/test_artifact_inspector_api.py`
   - `tests/runtime/http/test_runtime_api_authz.py`
   - `tests/runtime/http/test_legacy_manifest_adapter.py`

Verification status (`2026-02-10`):

- Runtime API suite (required P9 tests): `PASS` (20 tests).
- Middleware regression suite:
  - `tests/core/security/test_router.py`: `PASS`
  - `tests/core/security/test_auth_middlewares.py`: `PASS`
- Architecture freeze checks:
  - `collect_arch_metrics.py`: completed
  - `compare_baseline.py --mode blocking`: `FAIL` only on `delta_test_collect_errors = +4` (historical debt); additional non-blocking delta observed in `ruff_total_issues` (`+87`) in current workspace state.
