# Scholar (`polisyos.scholar`)

`polisyos.scholar` builds deterministic knowledge bundles from `ResearchIntent` inputs and seed
sources. It orchestrates discover, acquire, docs, claims, reconcile, and bundle persistence while
staying CAS-first and freshness-aware.

## Role in System

- **Depends on:** `core.contracts.scholar`, `core.artifacts`, `fabric.docs`, `fabric.claims`, `fabric.world`, and shared extractor entry points.
- **Used by:** `scientist` nodes, the scholar CLI/component surface, and tests for bundle generation.
- **Boundary function:** keeps knowledge-bundle creation separate from downstream consumers of the bundle.

## Key Concepts

- **Deterministic pipeline** - the bundle id is derived from intent, document versions, claims, and policy ids.
- **Freshness** - freshness metadata and sidecar state keep bundles refresh-aware.
- **Discovery/acquire** - seed sources are normalized, canonicalized, and fetched from local files, URLs, or bytes.
- **Docs/claims/reconcile** - document ingestion and claim extraction feed into conflict resolution and filtering.
- **CAS and world events** - bundles and reports are persisted into CAS and accompanied by world events.

## Public API

- `ScholarService`
- `enrich_topic`
- `ScholarPolicy`
- `EnrichResultV1`
- `EnrichmentReportV1`
- `KnowledgeBundlePayloadV1`
- error types: `ScholarError`, `ScholarValidationError`, `ScholarDiscoverError`, `ScholarAcquireError`, `ScholarDocsError`, `ScholarClaimsError`, `ScholarReconcileError`, `ScholarBundleError`

## Current State

- Last updated: 2026-04-03
- The package tree remains organized around `discover/` and `orchestrator/`, with freshness helpers living at the top level.
- Package exports continue to provide the scholar service facade and the staged error types.
