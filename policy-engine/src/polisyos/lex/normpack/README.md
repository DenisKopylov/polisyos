# NormPack (`polisyos.lex.normpack`)

`polisyos.lex.normpack` assembles a `NormPack` for the specified `jurisdiction`,
`as_of`, and optional domain filters. It can use either a provider path or a
local claims/provisions pipeline, and always returns a `NormPackBuildResult`
with provenance, warnings, and a deterministic `pack_id`.

## Role in the system

- **Depends on:** `polisyos.data_forge.read_api.legal`, `polisyos.fabric.claims`, `polisyos.core.components`, `polisyos.ir.loading.norm_pack`
- **Used by:** `polisyos.lex.legal_evaluation`, `polisyos.lex.simulator`, and policy validation flows
- The package turns selected local corpus/provision/claim inputs into date-scoped claims and applicability records for local evaluation and what-if flows. These are derived runtime inputs, not an executable copy of the law, a legal act, or proof that the selected version is current.

## Key concepts

- **Provider vs. pipeline path** — if a `NormPackProvider` is available, the package can return a ready-made pack; otherwise it runs the local assembly pipeline.
- **Source selection** — `select_sources.py` selects documents and active versions through Data Forge corpus indexes or a temporal fallback from the fact log.
- **Claim extraction** — `extract_norm_claims.py` builds `lex.norms.claim_set`, deduplicates claims, and records degradation warnings.
- **Applicability windows** — `applicability.py` computes `NormApplicability` from claim validity intervals.
- **Conflict resolution** — competing claims go through `fabric.claims.resolve_conflicts` rather than being overwritten locally.
- **Budgeted assembly** — `max_docs`, `max_provisions`, and `max_claims` keep assembly within predictable resource limits.
- **Legal authority requirements** — W7.B authority evaluation consumes
  `polisyos.legal_requirement.LegalAuthorityRequirementSpec`; broad
  jurisdiction/topic hits remain `context_only` until claim-level competence
  facets satisfy the compiled requirement.

## Source and currency limits

This description was checked by reading the implementation at source pin
`bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; tests were not run for this edit.

`as_of` selects by effective-date metadata supplied with local source artifacts.
This is distinct from retrieval time and fact-log transaction time; the
selection result does not authenticate the publisher or prove that the selected
version is the version currently in force.
In the implementation reviewed, `src/polisyos/data_forge/domains/legal/corpus/versioning.py::resolve_active_version()`
and `src/polisyos/lex/normpack/select_sources.py::_fallback_select_active_version()`
currently treat a non-empty but invalid `effective_to` as an unbounded upper
bound because it parses as `None`. `src/polisyos/lex/normpack/extract_norm_claims.py::_to_datetime_utc()`
also returns `None` for an invalid end date, so the upper bound is absent in
`src/polisyos/lex/normpack/applicability.py::applies_to_context()`. This is a
bounded validation gap, not evidence that the legal interval is actually open.
Amendment-window receipts use a separate path and leave invalid non-empty
windows unresolved. Details:
[NormPack reference](../../../../docs/reference/lex/normpack.md#time-identity-and-replay)
and [Lex Pipeline explanation](../../../../docs/explanation/lex-pipeline.md#unresolved-integration).

When an upstream process identifies a new publication, amendment, or correction
to source bytes or metadata, use that as a manual prompt to update the affected
corpus artifacts, version index, and `NormPack`, then repeat the scoped
assessment. A new claim requirement or Lex rule requires reassessment; rebuild
source artifacts only when the input or extraction/selection basis changes.
These are operational signals, not package triggers: the package does not poll
external sources, authenticate publisher signatures, or provide a complete
automatic cascade from source staleness to reissue.

## Public API

| Type/Function                                 | Description                                                    |
| --------------------------------------------- | -------------------------------------------------------------- |
| `assemble_norm_pack()`                        | Main provider-or-pipeline builder for `NormPack`               |
| `NormPackBuildRequest`, `NormPackBuildResult` | Input/output contracts for pack assembly                       |
| `NormPackBudgets`                             | Resource budgets for doc/provision/claim selection             |
| `select_sources.py`                           | Source and active-version selection logic                      |
| `legal_authority.py`                          | Claim-level authority adapter over compiled legal requirements |

Full reference: [docs/reference/lex/](../../../../docs/reference/lex/index.md)

## Current State

- Package files: follow the source tree at `src/polisyos/lex/normpack/`.
- Public exports: `src/polisyos/lex/normpack/__init__.py` is the canonical export list.
- The package-layout and export pointers were checked at source revision
  `36ac90f829b95e9874c5340fc2f1d0e595adf6d7` on 2026-10-14. The provider and
  runtime behavior described above was not executed or revalidated here; no
  deployment was observed.
- Historical note (2026-05-02): active-version selection was documented as
  going through `polisyos.data_forge.read_api.legal` plus fact-log fallback.
