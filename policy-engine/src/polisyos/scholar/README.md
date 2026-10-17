# Scholar (`polisyos.scholar`)

`polisyos.scholar` builds deterministic knowledge bundles from `ResearchIntent` inputs and seed
sources. It orchestrates discover, acquire, docs, claims, reconcile, and bundle persistence while
staying CAS-first and freshness-aware.

## Role in System

- **Depends on:** `core.contracts.scholar`, `core.artifacts`, `fabric.docs`, `fabric.claims`, `fabric.world`, and shared extractor entry points.
- **Used by:** `scientist` nodes, the scholar CLI/component surface, and tests for bundle generation.
- **Boundary function:** keeps knowledge-bundle creation separate from downstream consumers of the bundle.
- **W7.D requirement bridge:** consumes `polisyos.scholar_requirement.ScholarSupportRequirementSpec`
  when binding literature to Policy Design Case claims; publication evidence may
  support or contest academic claims, but it cannot imply affected-person
  representativeness.

## Key Concepts

- **Deterministic pipeline** - the bundle id is derived from intent, document versions, claims, and policy ids.
- **Freshness** - freshness metadata and sidecar state keep bundles refresh-aware.
- **Discovery/acquire** - seed sources are normalized, canonicalized, and fetched from local files, URLs, or bytes.
- **Search citation spans** - snippet text may trim boundary whitespace; its start/end character offsets select exactly the returned text from the input page string.
- **Search source binding** - bundle consumers re-resolve the selected raw-page CAS view, check its manifest and content digest, re-run Scholar's extractor/sanitizer, and require each citation span to equal its exact source substring. Legacy artifact-ID-only bundles use the default manifest view with a profileless warning; unavailable or mismatched raw snapshots cannot verify snippets.
- **Docs/claims/reconcile** - document ingestion and claim extraction feed into conflict resolution and filtering.
- **CAS and world events** - bundles and reports are persisted into CAS and accompanied by world events.
- **Claim-bound Scholar requirements** - search, support links, dependence
  records, and spine bindings can carry per-claim publication tier, recency,
  replication, independence, and participation-boundary requirements.

## Public API

- `ScholarService`
- `enrich_topic`
- `ScholarPolicy`
- `EnrichResultV1`
- `EnrichmentReportV1`
- `KnowledgeBundlePayloadV1`
- `persist_knowledge_bundle_payload` for persisting that typed payload through the canonical Scholar CAS writer.
- error types: `ScholarError`, `ScholarValidationError`, `ScholarDiscoverError`, `ScholarAcquireError`, `ScholarDocsError`, `ScholarClaimsError`, `ScholarReconcileError`, `ScholarBundleError`

The canonical bundle writer preserves the existing `scholar.knowledge_bundle` kind, JSON media type, schema, and declared input references. It admits finite floating-point fields in `KnowledgeBundlePayloadV1`; non-finite values remain refused. Persisting a bundle does not establish source licensing, currentness, or evidentiary quality. Scholar bundle and report persistence uses the versioned JSON artifact contract; Python object pickling is outside the documented persistence boundary.

## Deep-Research Artifact Compatibility

The canonical Scholar `WebEvidenceBundle` has a proposed additive 1.1
provider-attempt trace, pending G selection. Version 1.0 remains readable with
attempt detail absent; old CAS objects are not rewritten. If a legacy bundle is
resumed into a new 1.1 candidate, old free-text errors become
`legacy_error_not_established`, with attempt history still unknown. Every 1.1 query
and frontier error is fixed-category data even when attempt detail is absent. The
candidate producer would write 1.1, but that behavior is not accepted for
publication until G selects it. The trace records
observed calls, causes, and value-free error categories only; exception messages,
request URLs, credentials, search terms copied from exceptions, and response
payloads are not persisted. Legacy public search calls retain their error text.
This does not add a supported Python facade symbol or HTTP endpoint. It is not evidence of a complete provider roster,
global search exhaustion, or absence of relevant knowledge.

## Current State

- Last updated: 2026-10-17
- Discovery remains under `discover/`; enrichment policies, freshness evaluation/state, staged errors, and pipeline support DTOs are owned by `orchestrator/`.
- Persisted Scholar bundle/report contracts are defined in `core.contracts.scholar` and re-exported from this facade.

## Evidence Validation Facade

The root facade exports `SourceSnippet`, `WebEvidenceBundle`, `validate_source_snippet_spans`, and `validate_web_evidence_source_binding`. The same Scholar validators remain the evidence-admissibility predicates used by Scientist consumers; moving their imports does not replace exact source-byte and span verification with shape checks.

## Python Import Compatibility

The supported Python entrypoint is `polisyos.scholar`; its existing 30 root exports retain
their names and object bindings. The six former private module paths
(`polisyos.scholar.errors`, `.freshness`, `.freshness_store`, `.policies`, `.provenance`, and
`.types`) and their 13 class-definition FQNs are retired and unsupported. No compatibility
modules remain at those paths. The moved class identities are `ScholarError`,
`ScholarValidationError`, `ScholarDiscoverError`, `ScholarAcquireError`, `ScholarDocsError`,
`ScholarClaimsError`, `ScholarReconcileError`, `ScholarBundleError`, `ScholarPolicy`,
`ScholarFabricCitation`, `KnowledgeBundlePayloadV1`, `EnrichmentReportV1`, and `EnrichResultV1`.
This does not establish whether external stored pickles or consumers use an old FQN; that remains
`not_established`. The persisted compatibility surface remains the versioned JSON artifact
contract, whose fields, kind, media type, and schema version are unchanged.
