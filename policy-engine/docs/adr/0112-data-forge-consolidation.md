# ADR-0112: Data Forge Consolidation

## Status

Proposed

## Date

2026-04-18

## Context

Offline acquisition and preprocessing currently live across `academic`,
`datasets`, `ukraine_data`, `batch_common`, `batch_snapshot`, and `lex.batch`.
These packages duplicate orchestration, manifests, caching, LLM extraction,
quality gates, snapshot publishing, and benchmarking.

## Decision

Create `polisyos.data_forge` as the build-time package for offline pipelines.
Data Forge writes versioned artifacts and snapshots. Runtime packages consume
stable artifact contracts and `polisyos.data_forge.read_api`; they must not
import Data Forge kernel or domain pipeline internals.

Target layout:

```text
polisyos/data_forge/
|-- kernel/
|-- domains/
`-- read_api/
```

## Consequences

- Batch code has one shared framework and one set of lifecycle rules.
- Runtime imports become stricter.
- Old package paths require migration shims with sunset dates.

## Phase 0 Implementation Note

Repository SOTA Phase 0 validated the Data Forge contract posture on
2026-05-02: `polisyos.data_forge.read_api` remains the runtime-safe surface, and
Data Forge artifact/manifest JSON Schemas are registered in
`architecture/generated_artifacts.toml` as committed contract outputs.
