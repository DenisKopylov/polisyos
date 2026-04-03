# Runtime HTTP Services (`polisyos.runtime.http.services`)

`runtime.http.services` contains the application logic behind the runtime API. It owns run indexing,
timeline/debug views, artifact inspection, lineage traversal, and control-plane orchestration.

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

## Public API

- `ArtifactInspectorService`
- `DebugService`
- `IndexedRunRecord`
- `LineageService`
- `RunIndexService`
- `TimelineService`

## Current State

- Last updated: 2026-04-03
- The tree still centers on `artifact_inspector.py`, `debug.py`, `lineage.py`, `run_index.py`, and `timeline.py`.
- The control service continues to support feedback evaluation, reissue, and data/Lex orchestration surfaces.
