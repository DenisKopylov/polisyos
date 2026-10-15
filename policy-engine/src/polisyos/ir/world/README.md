# World (`polisyos.ir.world`)

`polisyos.ir.world` defines canonical world-graph contracts: documents,
claims, provenance events, conflict sets, trust assessments, and quality reports.
This is the IR boundary for knowledge/world pipelines; storage and querying remain in
`fabric`, while `world` defines the types and deterministic identifiers.

## Role in the system

- **Depends on:** `polisyos.ir.artifacts` and canonical ID helpers within `polisyos.ir`
- **Used by:** `polisyos.fabric.claims`, `polisyos.fabric.world`, `polisyos.lex`, `polisyos.scholar`, `polisyos.scientist`
- World contracts standardize the evidence graph consumed by trust/conflict and analysis pipelines.

## Key concepts

- **World ABI** — `NodeKind`, `EdgeKind`, and reserved prefixes define graph compatibility.
- **Document and claim contracts** — `DocMeta`, `DocFragment`, and `Claim` form the base evidence units.
- **Conflict resolution** — `ConflictSet` and related resolution models normalize competing claims.
- **Provenance events** — `WorldEvent`, `ProvAgent`, and `ProvActivity` describe change lineage.
- **Trust and quality** — separate contracts record scored assessments and issue ordering.
- **Deterministic IDs** — `ids.py` computes stable identifiers from canonical payloads.

## Public API

| Type/Function                                              | Description                                       |
| ---------------------------------------------------------- | ------------------------------------------------- |
| `DocMeta`, `DocFragment`                                   | Document and canonical-fragment contracts         |
| `Claim`, `ClaimSourceKind`                                 | Evidence claim and source type                    |
| `ConflictSet`, `ConflictSetResolution`                     | Canonical representation claim conflicts          |
| `WorldEvent`, `WorldObjectRef`                             | Provenance events and references to world objects |
| `TrustAssessment`, `QualityReport`                         | Trust/quality evaluation contracts                |
| `claim_id_from_payload()`, `world_event_id_from_payload()` | Deterministic ID builders for core world entities |

Full reference: [docs/reference/ir/](../../../../docs/reference/ir/index.md)

## README snapshot (2026-04-03)

- Files: 11 Python files in the snapshot recorded by this README
- Exports: 43 public names in `__init__.py` in that same snapshot
- These are historical counts, not a current inventory. The current package surface lives under `src/polisyos/ir/world/`, and exported names are declared by `src/polisyos/ir/world/__init__.py`; recensus those sources before publishing a current count or stability claim.
- At that refresh, this README was updated to describe the world ABI and deterministic ID surface.
