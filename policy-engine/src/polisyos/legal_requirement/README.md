# Legal Requirement (`polisyos.legal_requirement`)

Last updated: 2026-05-23

`polisyos.legal_requirement` owns the W7.B deterministic compiler that turns
claim, facet, obligation, jurisdiction, and time context into typed
`LegalAuthorityRequirementSpec` records.

The module does not select legal authority. It produces the per-claim contract
that Lex must consume before a norm can be graded as claim-level authority.
Generic jurisdiction or topic matches remain legal context until the Lex
adapter validates competence, hierarchy, instrument, actor, authority type,
fallback policy, and legal-window semantics against the compiled requirement.

## Public API

| Type/Function | Description |
| --- | --- |
| `LegalAuthorityRequirementSpec` | Strict per-claim requirement consumed by Lex. |
| `LegalAuthorityRequirementCompiler` | Deterministic compiler for claim/facet/obligation inputs. |
| `compile_legal_authority_requirements()` | Convenience wrapper around the default compiler. |
| `LegalAdmissibilityGrade` | W7.B legal admissibility grades emitted by the Lex adapter. |

## Authority Boundary

The compiler is authoritative for the requirement contract only. Lex remains
the producer authority for selected, rejected, blocked, contested, limited, and
context-only legal anchors. Public closeout and projection readers must consume
the Lex result rather than this compiler output alone.
