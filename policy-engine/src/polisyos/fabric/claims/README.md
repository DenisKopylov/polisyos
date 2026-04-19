# Claims (`polisyos.fabric.claims`)

`polisyos.fabric.claims` turns normalized document chunks into deterministic
claims, citations, conflict sets, evidence bundles, and world events.

Last updated: 2026-04-17.

## Purpose

Use this package when you need to extract claim candidates from document
artifacts, canonicalize them into stable world claims, and reconcile conflicts
before downstream Scholar or Lex flows consume them.

## Where to Start

- Read [__init__.py](./__init__.py) and [types.py](./types.py) for the exported
  claim pipeline surface.
- Read [extraction.py](./extraction.py) and [normalize.py](./normalize.py) for
  the deterministic `extract -> normalize` stages.
- Read [conflicts/detect.py](./conflicts/detect.py),
  [conflicts/resolve.py](./conflicts/resolve.py), [persist.py](./persist.py),
  and [world_events.py](./world_events.py) for reconciliation, persistence, and
  audit events.
- Follow upstream and downstream links to [../docs/README.md](../docs/README.md)
  and [../world/README.md](../world/README.md), then read the claims contract
  spec linked below.

## Public Entrypoints

| Entrypoint | Description |
|---|---|
| `extract_claims_from_doc()` | Extract claim candidates from a document's chunk artifact. |
| `normalize_claims()` | Canonicalize claims, ids, units, and payload ordering. |
| `detect_conflicts()` / `resolve_conflicts()` | Detect and reconcile conflicting claims with diagnostics and trust context. |
| `ClaimExtractOptions` / `ClaimNormalizeOptions` | Public options for extraction and normalization stages. |
| `ClaimExtractResult` / `ClaimNormalizeResult` | Result wrappers returned by the deterministic pipeline. |
| `ChunkContext` / `ClaimCandidate` | Public chunk-level input and intermediate candidate types. |
| `ClaimPipelineError` and related errors | Typed error surface for unsupported extractors, invalid claims, and incomplete pipeline state. |

## Depends On / Depended On By

- Depends on: `polisyos.fabric.docs`, `polisyos.fabric.world`,
  `polisyos.fabric.data_plane.quarantine`, `polisyos.ir.world`, and CAS
  artifact helpers in `polisyos.core.artifacts`.
- Depended on by: `polisyos.scholar.orchestrator.enrich`,
  `polisyos.scholar.policies`, `polisyos.lex.batch.claim_bridge`, and the
  `polisyos.lex.normpack.*` claim-normalization flows.

## Common Commands

Run from the repository root (`policy-engine/`).

- `rg -n "extract_claims_from_doc|normalize_claims|detect_conflicts|resolve_conflicts" src/polisyos/fabric/claims tests/fabric/test_claims_pipeline.py tests/fabric/test_conflicts.py`
  Jump to the public pipeline and its primary tests. Smoke-tested on
  2026-04-17.
- `rg -n "explicit_lines_v1|regex_numeric_v1|lex_norm_regex_v1" src/polisyos/fabric/claims/backends`
  Inspect the built-in extractor backends. Smoke-tested on 2026-04-17.
- `rg -n "persist_claim_set|write_claims_world_segment|build_claims_world_event" src/polisyos/fabric/claims`
  Follow persistence and audit-event helpers. Smoke-tested on 2026-04-17.

## Test / Verification Commands

Run from the repository root (`policy-engine/`).

- `uv run pytest tests/fabric/test_claims_pipeline.py tests/fabric/test_conflicts.py -q`
  Claims pipeline and conflict-resolution smoke suite. Smoke-tested on
  2026-04-17.
- `uv run pytest tests/fabric/test_conflict_uncertainty_adapter.py tests/fabric/test_trust.py -q`
  Downstream uncertainty and trust integration. Conceptual in this README
  refresh; not run in this pass.

## Reference Docs

- [Fabric data-plane reference](../../../../docs/reference/fabric/data-plane.md)
- [Fabric reference index](../../../../docs/reference/fabric/index.md)
- [E2.6 Fabric Claims Pipeline contract](../../../../docs/contracts/E2_6_FABRIC_CLAIMS_PIPELINE_V1_0.md)
- [IR schema catalog](../../../../docs/reference/ir/schema-catalog.md)
- [Fabric tests map](../../../../tests/fabric/README.md)
