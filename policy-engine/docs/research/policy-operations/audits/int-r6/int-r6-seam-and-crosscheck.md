# INT-R6 Seam And Cross-Check Audit

## D4-A1 And DS5

### Governing seam

D4-A1 governs product UI only: `en` authored primary, `uk` translation, `ru` `legacy_continuity_frozen`, Russian source-content rendering separate, RTL UI unsupported. INT-R6’s `composes` verdict is correct at the architecture boundary.

### Implemented product-locale waist

At package SHA `5e47c868c2c1d4d66fa11fcddcc972dbb55e95d3`, `shared/i18n/locale.ts` admits exactly `en` and `uk` as `ProductLocale`, derives `PRIMARY_LOCALE` as `en`, and keeps `ru` only as `LegacyContinuityLocale`. Stored/browser locale resolution cannot select `ru` as active UI. This matches D4-A1.

### Unclosed decoupling

Both launch builders still serialize the selected UI locale into run requests:

```text
workflow: params.atlas_context.locale_preference = context.locale
NL:       context.locale_preference = context.locale
```

The NL request also sets `dynamic_text_policy = "source_text_only"`, but that string does not identify legal source language, authority-text-set membership, rendition status or requested render language. Therefore DS5 mechanics close the active-`ru` exposure but not the UI/source-content axis crossing INT-R6 is designed to remove.

**Cross-check:** package F-026 calls the crossing a regression hypothesis. Exact code makes the crossing a repository fact in the inspected launch path; only its downstream semantic effect remains a hypothesis.

## DS11 Through DS13

### DS11 trust posture

The live trust twin projects canonical artifact values—including claim ID, effective state, limitations, blocker codes, review dates and source coordinates—into visible DOM and independently decodes the DOM for exact equality. This is a strong existing seam for INT-R6’s rule that localized labels must not replace semantic identity.

What DS11 does not provide:

- authority-text-set membership;
- content-rendition status;
- translation/adaptation certificate;
- cross-language entailment or action-profile evidence;
- jurisdiction-specific co-authentic reconciliation.

INT-R6 is correct to treat MACHINE-like exact projection as a strict consumer, not as proof of multilingual equivalence.

### DS12 and DS13

The exact package-SHA `docs/plans/active/atlas-slices/` directory listing was inspected. No directly named `DS12-*` or `DS13-*` child was present. D4-A1 nevertheless names DS12 as the lane that may publish exactly the locale posture and nothing stronger. That is a documentary seam, not an implemented MAEP consumer.

The audit does not turn code-search misses into absence. The established statement is narrower: no directly named DS12/DS13 slice artifact was present in the complete directory population exposed by the exact contents read, and no INT-R6 package row binds a concrete DS12/DS13 owner contract. Stage 3 must identify the actual owning artifact or leave the seam unallocated.

## Lex

`LegalDocSource` records one `language` string alongside jurisdiction and publisher metadata. `NormPackBuildRequest` selects by jurisdiction/as-of/domain/doc IDs but does not represent:

- designated versus co-authentic relationship;
- several authentic text members;
- prevailing-language rule;
- non-authentic rendition and purpose;
- content render locale;
- divergence/adjudication record.

`SPOCandidate` hard-codes a Ukraine-to-English extraction projection: canonical `subject_en`, `object_en`, English fact text and Ukrainian originals/source quote. This is a concrete de-facto English pivot in the current adapter. The package does **not** smuggle it into the target architecture; it identifies it as the assumption to remove from the authority layer while preserving it as a jurisdiction-specific projection.

**Cross-check result:** T3 is refuted for the research architecture and confirmed as present repository debt.

## MACHINE Twins

The trust twin’s exact identity comparison supports these INT-R6 requirements:

- semantic IDs precede labels;
- blockers/limitations survive display projection;
- visible DOM can be checked independently against the artifact;
- hidden or missing fields fail rather than silently pass.

It does not yet carry `authority_text_set_id`, `content_rendition_id`, `equivalence_certificate_id`, translation/adaptation provenance or purpose-bound validity. The package’s statement that MACHINE twins **must** consume those fields is a protocol requirement; any wording that implies they already do is unearned.

Lex and MACHINE therefore expose the same integration gap from opposite directions: Lex knows document/version but not multilingual authority relation; the trust twin knows canonical system state but not rendition authority/provenance.

## Runtime Namespaced Family Blockers

The live evaluation-safety owner defines:

```text
NamespacedEvalSafetyId = <name>@<semver>
blocker prefix = polisyos.eval_safety
```

and carries typed blocker-code tuples through authority resolutions. Decision validity separately owns `stale`, `superseded`, `withdrawn`, `revoked` and related lifecycle states. Scientist comparison contracts have at least two scoped owners using `LIMITED`. Search contracts type the `may_not_use_for` field but leave its members as strings.

This population supports the package’s second-lattice ban:

- a bare translated word is insufficient;
- namespace/owner/version matter;
- distinct lifecycle states already exist and must not be re-created;
- free-string prohibited-purpose members are a real gap;
- candidate MAEP reason names must map to an existing family or route a vocabulary decision.

### T6 disposition

`refuted with implementation condition`.

The package’s certificate outcomes, risk classes and example refusal names do not by themselves form a second runtime lattice because they are repeatedly labelled conceptual/candidate/mapped. Stage 3 would create the prohibited lattice if it implemented those literals as a new authority owner without mapping each one to the live namespaces.

## Cross-Check Results

| seam | current repository | INT-R6 target | audit result |
|---|---|---|---|
| product UI locale | `en|uk`, `en` primary; `ru` frozen | unchanged | `aligned` |
| UI → run context | UI locale serialized as `locale_preference` | separate UI/source axes | `gap confirmed` |
| legal source | one language plus Ukrainian/English adapter | authority-text set + renditions | `gap confirmed` |
| validity states | distinct typed IDs | preserve IDs in localization | `aligned requirement` |
| use restriction | field typed, members strings | canonical purpose/restriction identity | `gap confirmed` |
| MACHINE/DOM | exact IDs/states/source coords | add source/rendition/certificate provenance | `partial seam` |
| public locale claims | D4 limits claim; DS12 named documentary lane | no stronger claim | `architecture aligned; owner artifact unresolved` |
| RTL | no active UI/direction contract | source admission separate; UI still unsupported | `aligned boundary` |
| holder vacancy | no MAEP chain | typed purpose-scoped refusal | `target only; absent/unallocated` |

## Residual Band

This seam audit did not execute runtime requests, browser tests, Lex ingest or MACHINE round trips. It established owner contracts and data-flow coordinates from exact source reads. A complete implementation audit must follow the request fields through backend consumers, enumerate all MACHINE twins rather than use the trust twin as representative, and identify the actual DS12/DS13 owning records. No code-search count is used as a set-level fact.
