# Lex NormPack

Related explanation: [Lex Pipeline](../../explanation/lex-pipeline.md).

Freshness: 2026-10-14
Owner: `@lex-owners` for runtime version reads, NormPack assembly, and legal assessment; `@data-forge-owners` for corpus ingest, structure, and version-index production.
Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
Source of truth: `src/polisyos/lex/api.py`, `src/polisyos/lex/types.py`, `src/polisyos/lex/normpack/**`, `src/polisyos/lex/legal_evaluation/**`, `src/polisyos/data_forge/domains/legal/corpus/versioning.py`, `src/polisyos/core/contracts/epoch.py`, and the named tests below.
Evidence level: source and named test behavior were inspected at the source pin; tests were inspected, not run for this documentation refresh. Test fixtures establish only the paths they exercise, not official-source completeness or issuer authentication.

Lex starts from published Data Forge corpus artifacts. Its public `resolve_active_version()` adapts the Data Forge read API; `assemble_norm_pack()` then selects versions and provisions, extracts claims with the source-pinned `lex.norm_extractor.regex_v1` default or consumes explicit claim-set artifacts, and persists the resulting `NormPack` with world provenance. These extracted or supplied claims are inputs to a derived snapshot, not legal findings. Corpus byte ingestion, structure extraction, batch graph construction, and version-index production belong to Data Forge, not the runtime Lex assembly path.

## Pipeline surface

| Layer | Main contract or operation | Boundary |
| --- | --- | --- |
| Version lookup | `ActiveVersionStrategy`, `ActiveVersionResult`, `resolve_active_version()` | Reads a Data Forge-produced version index. It does not produce or authenticate the legal source. |
| NormPack assembly | `NormPackBuildRequest`, `NormPackBuildResult`, `NormPackBudgets`, `assemble_norm_pack()` | Selects published inputs, resolves claim conflicts and trust assessments, then persists a CAS `NormPack` and an `ASSEMBLE_NORM_PACK` world event. |
| Claim-scoped legal requirement and assessment | `build_legal_authority_requirement_artifact()`, `build_legal_authority_report()` | Compiles and evaluates required authority facets for a policy claim; this is separate from the evaluator-plugin `evaluate_legality()` API. |
| Mutation and diff | `MutationIntent`, `NormChange`, `NormDiff`, `diff_norm_packs()` | Computes a proposed change or comparison between local snapshots. |
| Impact analysis | `NormImpactAnalyzer`, `NormImpactReport`, `ComplianceDelta`, `AffectedKPI` | Reports downstream impact for the supplied comparison. |
| Plugin legal evaluation | `LegalEvaluationRequest`, `LegalReportRef`, `ChangeProposalRef`, `evaluate_legality()` | Dispatches a configured evaluator and returns its persisted report reference and proposals. |

For corpus-backed assembly, `select_active_doc_versions()` tries the version-index reader first. If
that path is not ready, returns no selection, or raises a handled validation error, the assembler
falls back to scanning local world facts and document metadata. The fallback still requires a
parseable `effective_from`, uses the inclusive legal-date window, and does not fall back to
`published_at` alone; it has no selected version-index artifact reference. The primary and fallback
paths both currently treat an invalid nonempty `effective_to` as open-ended.

## Time, identity, and replay

`as_of` is the inclusive legal-time date used to select an active document version. At the source pin, `resolve_active_version()` admits a candidate when `effective_from` parses and is no later than `as_of`, and parsed `effective_to` is absent or no earlier than `as_of`; both date boundaries are inclusive. A malformed nonempty `effective_to` also parses to `None` and currently behaves as open-ended instead of excluding the candidate. This is an unresolved validation gap, not evidence that the legal window is actually open. The direct metadata fallback has the same end-date behavior. The cited versioning tests cover deterministic selection and the no-fallback case for a missing `effective_from`, but omit a malformed-end semantic case. For effective candidates, the tie-break order is `effective_from`, `published_at`, then `doc_version_id`. `published_at` helps break a tie but does not substitute for a missing `effective_from`. Retrieval time and fact-log `tx_time` answer different questions and are not substitutes for legal effect time.

The corpus-backed claim extractor copies document `effective_from` and `effective_to` into claim
`valid_from` and `valid_to` fields. The local applicability builder then uses those as an inclusive
`TimeWindow`. Its datetime parser also converts an invalid nonempty end to `None`, which leaves no
upper bound in that applicability check. This is a second bounded validation gap in the same
metadata path; the cited tests do not exercise malformed end dates through extraction or
applicability. The amendment-window receipt is a separate path: it uses a half-open interval and
keeps invalid nonempty windows unresolved rather than treating them as open.

For the local assembly branch, the stable pack identity includes normalized jurisdiction, `as_of`, domain, selection/conflict/trust policy IDs, selected document-version IDs, canonical claim IDs, and the current extraction/conflict algorithm-version identifiers. Its CAS manifest binds selected provision-index, claim-set, conflict-resolution, and trust-assessment artifacts; the assemble event records the selected source and world references. `tests/unit/fabric/test_normpack.py::test_normpack_phase17_end_to_end` checks repeat assembly with the same fixture inputs produces the same artifact ID and emits an assemble event. This is a bounded fixture-level replay check, not a promise that changed evidence or rules preserve identity.

Static provider output is also supported when local documents and explicit claim sets are absent. That provider branch emits an artifact and assemble event, but it does not carry the same selected local-source lineage; do not generalize the local replay and input-lineage statement to every provider. The exact branch is in `src/polisyos/lex/normpack/assemble_pack.py`.

The amendment-window receipt uses a different interval convention from active-version selection: its effective interval is half-open, `effective_from <= valid_effect_date < effective_to`, with a missing end treated as open. See [Lex Knowledge](knowledge.md#amendment-window-receipt) for the receipt and its consumer-side reconciliation.

## Authority boundary

A `NormPack` is PolicyOS's derived, date-scoped snapshot from supplied corpus and claim artifacts. It is not the institution's legal act, an issuer signature, or proof that the upstream corpus is complete. Quote grounding, trust tiers, a CAS content address, and an `admissible` local grade each establish only the property implemented at their own boundary.

`build_legal_authority_report()` evaluates supplied norm candidates against claim-specific requirements. The adapter checks that version and source-provenance references are nonempty; it does not resolve those references to issuer-verified bytes or verify issuer competence. It marks inputs as `context_only` when caller-supplied `provenance_kind`/`source_class` values or `norm_id` prefixes match its LLM-candidate list; it cannot establish model origin for unmarked inputs. A report's local grade describes the claim-scoped checks over its supplied inputs, not institutional authentication. The institution owns the law or administrative act; PolicyOS integrates typed evidence and owns its own scoped claim reaction and its later validity/reissue consequences.

## API reference

::: polisyos.lex.api

::: polisyos.lex.types

::: polisyos.lex.errors

::: polisyos.lex.simulator.mutator

::: polisyos.lex.normpack.diff

::: polisyos.lex.legal_evaluation.impact_diff

The former `polisyos.lex.simulator.diff`, `report`, and `engine` modules are compatibility facades. Canonical owners are `polisyos.lex.normpack.diff`, `polisyos.lex.legal_evaluation.impact_diff`, and the current evaluator/API modules; see `src/polisyos/lex/simulator/` before extending a facade.

## Code-inspected evidence

- Selection, extraction, applicability, and assembly: `src/polisyos/data_forge/domains/legal/corpus/versioning.py`, `src/polisyos/lex/normpack/select_sources.py`, `src/polisyos/lex/normpack/extract_norm_claims.py`, `src/polisyos/lex/normpack/applicability.py`, `src/polisyos/lex/normpack/assemble_pack.py`, `tests/unit/fabric/test_lex_corpus.py::test_lex_resolve_active_version_is_deterministic`, `tests/unit/fabric/test_lex_corpus.py::test_lex_resolve_active_version_does_not_fallback_to_published_at_only`, `tests/unit/lex/test_normative_applicability_report.py`, and `tests/unit/fabric/test_normpack.py::test_normpack_phase17_end_to_end`.
- Claim-scoped legal assessment and its runtime consumers: `src/polisyos/lex/normpack/legal_authority.py`, `src/polisyos/runtime/quality/semantic_binding.py`, `tests/unit/lex/test_legal_authority_adapter.py`, and `tests/unit/runtime/quality/test_lex_legal_authority_surface.py`.
- Package and ownership boundary: `src/polisyos/lex/README.md`, `src/polisyos/data_forge/domains/legal/corpus/README.md`, and `src/polisyos/data_forge/domains/legal/batch/README.md`.
