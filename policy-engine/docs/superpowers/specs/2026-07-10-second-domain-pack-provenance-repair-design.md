# GY-N10a Provenance Repair Design

## Goal

Repair the three adversarial-audit findings without changing any
`src/polisyos/**` module, owner query, domain selection, pack entry, or N6
smoke behavior. The checker remains the canonical producer of the generated
pack artifacts.

## Design

The N7 engine receipt remains an operational record because its existing
engine-level `content_hash` binds `generated_at`. The checker projects a
separate, content-addressed N7 owner-evidence receipt that excludes only
operational capture times (`generated_at` and nested
`capture_provenance.captured_at`) and the engine receipt hash derived from
them. The complete engine receipt, its actual capture times, and its engine
hash live in the manifest's explicitly excluded `runtime_metrics` envelope.
Validation recomputes the stable projection from that real receipt and fails
if a time field appears in the content-bound projection.

Source identity is `repo-relative path + source bytes`; no absolute checkout
path participates. Gap reports use a generic source-symbol witness with a
hash of the exact AST function segment, rather than a whole module. Every
one of the seven gaps carries such a witness. A missing or ambiguous symbol is
a typed `gap_witness_target_missing` failure, and a changed segment is a
typed witness drift rather than a silent empty call list.

## Boundaries and pattern pass

- No `src/polisyos/**` change; the engine's timestamp-bound receipt contract
  is consumed as operational evidence rather than rewritten.
- P07/P08: operational capture time is distinct from content-bound owner
  facts and is excluded from all pack content hashes.
- P29: every named gap seam resolves to a real function and fails closed if
  it cannot be found.
- P31: one generic witness builder/validator protects all seven gaps, rather
  than an N5-only special case.
- Acceptance: fresh rederivation observes current time while content hashes
  stay stable; equivalent local paths hash identically; each gap has a real
  segment witness; corrupt-mode detects time re-entry, path dependence, and a
  missing witness symbol.
