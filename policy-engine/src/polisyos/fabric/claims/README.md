# Claims (`polisyos.fabric.claims`)

`claims` - extraction, normalization and conflict-resolution pipeline for claims
derived from documents and external evidence.

## Role in System

- **Depends on:** `polisyos.fabric.docs`, `polisyos.ir.world`, `polisyos.ir.analytics.uncertainty`
- **Used by:** world materialization, evidence/provenance flows and downstream analysis
- Converts document chunks into claim sets that can be persisted and reconciled.

## Key Concepts

- **Extraction** - build claims from chunk context and extractor registry inputs.
- **Normalization** - canonicalize values, units and predicates.
- **Conflict handling** - detect and resolve claim conflicts with trust/quality outputs.
- **Persistence** - store claim sets, evidence bundles and world events.
- **Extractor registry** - legacy plus component extractors and semver-aware resolution.

## Public API

| Type/Function | Description |
|---|---|
| `extract_claims_from_doc()` | Extracts claim candidates from a document. |
| `normalize_claims()` | Canonicalizes extracted claims. |
| `detect_conflicts()` | Detects conflicting claims. |
| `resolve_conflicts()` | Resolves conflicts with policy and diagnostics. |
| `ClaimExtractOptions` | Options for claim extraction. |
| `ClaimNormalizeOptions` | Options for claim normalization. |
| `ChunkContext` | Input context for chunk-level extraction. |

→ Full reference: [docs/reference/fabric/index.md](../../../../docs/reference/fabric/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 23 Python files
- Exports: 14
