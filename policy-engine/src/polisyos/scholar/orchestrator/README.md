# Scholar Orchestrator (`polisyos.scholar.orchestrator`)

`polisyos.scholar.orchestrator` owns enrichment sequencing, policy defaults, freshness evaluation and sidecar state, stage errors, and the final bundle persistence path. It also adapts Fabric provenance into Scholar citation views.

## Role in System

- **Depends on:** the discover layer, scholar document/claim helpers, `core.artifacts`, and the world/provenance stack.
- **Used by:** `ScholarService` and the scholar package facade.
- **Boundary function:** centralizes pipeline sequencing so callers only need to provide intent and sources.

## Key Concepts

- **Validation and policy merge** - intent, budgets, and thresholds are normalized before work starts.
- **Discover/acquire** - sources are deduplicated and fetched from bytes, files, or URLs.
- **Docs pipeline** - document bytes become normalized, structured, and chunked artifacts.
- **Claims and reconcile** - extractor components produce claims that are then conflict-resolved.
- **Bundle persistence** - bundle ids, typed report/payload contracts, CAS artifacts, and world events are persisted together.
- **Freshness lifecycle** - policy thresholds and runtime sidecar state drive stale/expired refresh decisions without mutating immutable CAS artifacts.
- **Stage failures** - one Scholar-owned exception family preserves validation/acquire/docs/claims/reconcile/bundle stage identity across discovery and orchestration.

## Public API

- `enrich_topic`
- `compute_bundle_id`
- `build_knowledge_bundle_payload`
- `persist_bundle_and_event`
- Internal modules: `errors`, `freshness`, `freshness_store`, `policies`, `provenance`, and pipeline-only `types`. Their former `polisyos.scholar.*` deep paths are retired and unsupported; use the supported `polisyos.scholar` root facade for package exports.

## Current State

- Last updated: 2026-10-17
- `bundle.py` owns deterministic bundle IDs and CAS/world persistence helpers; public payload and report DTOs live in the canonical `core.contracts.scholar` contract.
- `enrich.py` consumes `discover/` and document/claim processing, then calls the bundle writer. Its package facade is lazy so discovery can reuse the stage error types without eagerly importing the pipeline.
