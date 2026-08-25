# Runtime HTTP Services (`polisyos.runtime.http.services`)

`runtime.http.services` contains the application logic behind the runtime API. It owns run indexing,
timeline/debug views, artifact inspection, lineage traversal, and control-plane orchestration.

## Purpose

Use this package for route-adjacent runtime API behavior that needs shared
business logic, CAS/artifact access, run lifecycle orchestration, or read-side
projections. Route handlers should stay thin and delegate behavior here.

## Role in System

- **Depends on:** `core.artifacts`, `core.contracts`, `core.trace`, `core.security`, and the domain packages used by control-plane calls.
- **Used by:** `runtime.http.routes` and the FastAPI app.
- **Boundary function:** keeps request handlers thin while centralizing runtime business logic.

## Key Concepts

- **Run index** - caches run records from `core_runs_root` and handles pagination/filtering.
- **Timeline/debug** - converts trace records into ordered, inspectable runtime views.
- **Artifact inspection** - renders CAS manifest/content/schema/lineage views with redaction hooks.
- **Lineage traversal** - builds lineage graphs and completeness summaries.
- **Control-plane orchestration** - launches or reissues runs and bridges into `scientist`, `fabric`, and `lex`.
- **Human-decision custody** - resolves signed delegation, principal,
  reviewer-separation, presentation, and evidence-exposure inputs before using
  the existing CAS/event writer and durable one-live-record reservation. Public
  gate results remain non-authoritative projections; operational consumers
  must re-resolve the concrete deployment-attested packet.

## Public API

- `ArtifactInspectorService`
- `AttractorAnalysisService`
- `DebugService`
- `IndexedRunRecord`
- `LineageService`
- `MobilityService`
- `RunIndexService`
- `ScenarioService`
- `TemporalService`
- `TimelineService`

## Internal Layout

- [`__init__.py`](__init__.py) exports the documented service classes used by
  runtime HTTP routes.
- [`run_index.py`](run_index.py), [`timeline.py`](timeline.py),
  [`debug.py`](debug.py), [`artifact_inspector.py`](artifact_inspector.py),
  and [`lineage.py`](lineage.py) own core read-side API behavior.
- [`control.py`](control.py), [`control_worker.py`](control_worker.py), and
  [`control_plane_store.py`](control_plane_store.py) own control-plane run
  lifecycle behavior and are intentionally kept behind route-layer adapters.
- [`human_decision_contracts.py`](human_decision_contracts.py) defines strict
  route/service contracts, while [`human_decisions.py`](human_decisions.py)
  owns signed-input reconciliation, append-only record custody, reservation
  recovery, and operational revalidation. They reuse the access-audit trail and
  control-plane artifact/event path; they do not establish a second log.
- [`adapters/`](adapters/) contains service adapters for core runtime state and
  should stay thin.
- Scenario, temporal, mobility, attractor, feedback, and rendering services own
  domain-specific API projections without adding route logic.

## Extension Points

- Runtime middleware extensions are declared at the parent HTTP layer through
  the `polisyos.runtime_middlewares` entry-point group in
  [architecture/extension_points.toml](../../../../../architecture/extension_points.toml).
- This service package is not itself an extension host. New service behavior
  should be route-owned, covered by OpenAPI tests, and exposed through
  [`../routes/README.md`](../routes/README.md) when public.

## Tests

Run from the repository root:

```bash
uv run pytest tests/unit/runtime/http -q
uv run pytest tests/unit/runtime/http/test_runtime_api_contract_hardening.py tests/unit/runtime/http/test_api_maturity.py -q
```

Focused service tests live under
[tests/unit/runtime/http/](../../../../../tests/unit/runtime/http/). Update the
OpenAPI contract tests whenever response shape or route-visible behavior
changes.

## Operability Links

- [Runtime component SLO](../../../../../ops/components/runtime/slo.yaml)
- [Runtime component runbooks](../../../../../ops/components/runtime/runbooks.md)
- [Runtime API outage runbook](../../../../../docs/runbooks/runtime-api-outage.md)
- [Runtime graceful shutdown and stuck worker runbook](../../../../../docs/runbooks/runtime-graceful-shutdown-and-stuck-worker.md)
- [Use control plane how-to](../../../../../docs/how-to/use-control-plane.md)

## Known Shims/Deprecations

- There are no active package-local shims for `runtime.http.services` in
  `architecture/shims.toml` as of 2026-05-06.
- [`control.py`](control.py) is a high-complexity module tracked in
  [architecture/module_size_budget.toml](../../../../../architecture/module_size_budget.toml)
  with owner `team-runtime` and sunset `2026-12-31`.
- Public response changes must go through OpenAPI snapshot checks and generated
  client compatibility notes before old fields are removed.

## Current State

- Last updated: 2026-08-24
- The tree still centers on `artifact_inspector.py`, `debug.py`, `lineage.py`, `run_index.py`, and `timeline.py`.
- The control service continues to support feedback evaluation, reissue, and data/Lex orchestration surfaces.
