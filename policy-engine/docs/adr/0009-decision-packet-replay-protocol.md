# ADR-0009: DecisionPacket Replay Protocol

- Status: Proposed
- Date: 2026-02-07

## Context

Policy OS requires offline, auditable replay from a single `DecisionPacket` reference.
CAS integrity exists, but there was no end-to-end replay contract covering:

- dependency graph completeness checks,
- replay strategy selection (`foundry` vs `scientist`),
- deterministic verification modes,
- offline export/import of CAS subgraphs.

## Decision

1. Introduce `runtime.replay` as layer-safe replay planning and verification API.
2. Introduce `scientist.replay_backend` as execution backend that performs replay runs.
3. Extend DecisionPacket builder to schema `3.0` with:

   - explicit `inputs` and `artifacts` ref maps,
   - replay readiness metadata and strategy hints,
   - complete `InputRef` lineage in CAS manifest.
4. Add CAS subgraph `export_subgraph()` and `import_subgraph()` in `FileSystemCAS`.
5. Add CLI command `polisyos replay` for check/run/export/offline bundle replay.
6. Support dual verification:

   - `bit_exact` for deterministic simulation refs,
   - `ci_bounded` for metric-level tolerance checks.

## Consequences

Positive:

- reproducibility can be validated from one packet reference,
- replay can run offline via portable CAS bundles,
- replay contracts are testable and CI-gated.

Tradeoffs:

- DecisionPacket payload size increases,
- replay correctness depends on captured lineage completeness,
- deterministic guarantees remain backend- and environment-dependent.

Compatibility:

- legacy packets remain readable,
- missing replay metadata degrades gracefully to incomplete checks.
