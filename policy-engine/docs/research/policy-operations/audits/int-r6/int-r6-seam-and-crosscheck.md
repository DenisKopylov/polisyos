# INT-R6 Seam And Cross-Check Audit

## D4-A1 And DS5

D4-A1 governs product UI: `en` authored primary, `uk` translation, `ru` frozen, source rendering separate, RTL UI unsupported. INT-R6’s composition verdict is correct.

At package SHA `5e47c868c2c1d4d66fa11fcddcc972dbb55e95d3`, `locale.ts` admits only `en|uk` as `ProductLocale`, makes `en` primary, and retains `ru` only as legacy continuity. However both launch builders copy UI context into `locale_preference`; NL launch adds `dynamic_text_policy="source_text_only"`, which does not identify source language, authenticity, rendition or render language. DS5 closes active-`ru` exposure but not the UI/source crossing.

Package F-026 calls the crossing a hypothesis. The crossing itself is established in the inspected path; only downstream effect remains open.

## DS11 Through DS13

The trust twin projects claim ID, effective state, limitations, blocker codes, dates and source coordinates into DOM and independently decodes them for exact equality. This supports INT-R6’s ID-before-label rule. It does **not** provide authority-text sets, rendition status, translation/adaptation certificates or cross-language entailment.

The exact `atlas-slices` directory listing contained no directly named DS12/DS13 child. D4 nevertheless names DS12 as the public-locale-claim lane. Narrow result: no direct owning slice artifact was found in that bounded directory; broader absence is not claimed. Stage 3 must identify the actual owner artifact or leave the seam unallocated.

## Lex

`LegalDocSource` stores one language. `NormPackBuildRequest` selects jurisdiction/time/doc IDs but has no designated/co-authentic relation, prevailing rule, rendition purpose, render locale or divergence record. `SPOCandidate` hard-codes canonical English fields beside Ukrainian originals/source quote.

Thus a de-facto English pivot exists in the current adapter. The target architecture does not endorse it; it identifies the assumption to remove from the authority layer while permitting jurisdiction-specific projections. T3 is refuted for the research and confirmed as repository debt.

## MACHINE Twins

The trust twin proves exact artifact→visible projection of IDs/states/source coordinates. It lacks `authority_text_set_id`, `content_rendition_id`, `equivalence_certificate_id` and transformation provenance. INT-R6’s “must consume” claim is a target requirement, not current capability.

Lex knows document/version but not multilingual authority relation; the twin knows system state but not rendition authority. That is the integration seam.

## Runtime Namespaced Family Blockers

Live evaluation safety uses versioned `polisyos.eval_safety.*@1.0.0` IDs. Decision validity separately owns `stale`, `superseded`, `withdrawn` and related states. Two scientist enums use scoped `LIMITED`; `may_not_use_for` members remain strings.

T6 is `refuted with implementation condition`: MAEP relation/result/refusal examples are labelled candidates or mapped values, not a new production owner. Stage 3 would create the prohibited second lattice if it copied those literals instead of mapping/registering them.

## Cross-Check Results

| seam | current | target | result |
|---|---|---|---|
| UI locale | `en|uk`; `ru` frozen | unchanged | aligned |
| UI→run | `locale_preference` crossing | separate axes | gap |
| legal source | one language + EN/UK adapter | authority set/renditions | gap |
| validity | distinct typed IDs | preserve through locale | aligned requirement |
| use restriction | typed field, string members | canonical restriction IDs | gap |
| twin | IDs/states/source coords | add rendition/certificate provenance | partial |
| public claims | D4 limit; DS12 documentary name | no stronger claim | owner unresolved |
| RTL | no active UI contract | source admission separate | aligned boundary |
| vacancy | no MAEP chain | purpose-scoped refusal | target only, absent |

## Residual Band

No runtime request, browser, Lex ingest or twin round trip was executed. A later implementation audit must follow backend consumers, enumerate all twins and identify actual DS12/DS13 owners. Code search was navigation only.
