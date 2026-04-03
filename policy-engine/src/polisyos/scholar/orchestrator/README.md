# Scholar Orchestrator (`polisyos.scholar.orchestrator`)

`polisyos.scholar.orchestrator` owns the runtime orchestration for scholar enrichment and the final
bundle persistence path.

## Role in System

- **Depends on:** the discover layer, scholar document/claim helpers, `core.artifacts`, and the world/provenance stack.
- **Used by:** `ScholarService` and the scholar package facade.
- **Boundary function:** centralizes pipeline sequencing so callers only need to provide intent and sources.

## Key Concepts

- **Validation and policy merge** - intent, budgets, and thresholds are normalized before work starts.
- **Discover/acquire** - sources are deduplicated and fetched from bytes, files, or URLs.
- **Docs pipeline** - document bytes become normalized, structured, and chunked artifacts.
- **Claims and reconcile** - extractor components produce claims that are then conflict-resolved.
- **Bundle persistence** - bundle ids, reports, CAS artifacts, and world events are persisted together.

## Public API

- `enrich_topic`
- `compute_bundle_id`
- `build_knowledge_bundle_payload`
- `persist_bundle_and_event`

## Current State

- Last updated: 2026-04-03
- `bundle.py` still owns the deterministic bundle id path and CAS/world persistence helpers.
- The orchestrator remains the main integration point between scholar discovery, document processing, and bundle export.
