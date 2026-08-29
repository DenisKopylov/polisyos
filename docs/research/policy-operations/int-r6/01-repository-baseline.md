# INT-R6 repository baseline ledger

This appendix is part of the single INT-R6 Stage 1 research deliverable. It separates repository facts, prior measurements, calculations, and unresolved readback. It does not treat a search-index miss as a repository-wide absence.

## Measurement identity

| field | value |
|---|---|
| repository | `DenisKopylov/polisyos` |
| fixed baseline ref | `dc7bdf79a` |
| target branch | `research/int-r6-research` |
| commissioned measurement party | INT-R6 commissioned researcher |
| prior measurement party | DS0, as quoted in the commission |
| unit for catalogue size | primitive string leaves reached by a complete catalogue walk |
| unit for identity share | leaves whose target-locale string is byte-identical to the `en` string at the same path, divided by all `en` leaves |

## Catalogue measurements: what is and is not established

The commission reports the following DS0 result: each of the `en`, `uk`, and `ru` catalogues contained 2,449 string leaves; 36.26% of `uk` leaves and 80.16% of `ru` leaves were identical to `en`. These are **prior measurements executed by DS0**, not measurements executed by INT-R6.

The integer counts consistent with those reported rounded percentages are 888 `uk == en` leaves and 1,963 `ru == en` leaves:

- commissioned researcher calculation: `888 / 2,449 = 36.2596978…%`, rounded to 36.26%;
- commissioned researcher calculation: `1,963 / 2,449 = 80.1551654…%`, rounded to 80.16%.

Those calculations recover the likely numerators of the DS0 measurement; they do **not** re-walk the current catalogues. Therefore this pass does not silently relabel 2,449/888/1,963 as a current-tree measurement.

An identical leaf has at least four materially different explanations: an untranslated target string; a proper noun, identifier, code, or product name intentionally held constant; an English loan or deliberately shared technical term; or parity padding that preserves the key while leaving the semantic work undone. Identity rate is therefore a triage signal, never translation-quality evidence. The `ru` rate has still less operational significance because D4-A1 classifies the UI catalogue as `legacy_continuity_frozen`; it does not create a new translation obligation.

## What catalogue parity can prove

The contract names `shared/i18n/parity.test.ts`. Its admissible claim is structural: the locale objects expose matching paths (and, to the extent the test checks leaf shape, structurally compatible leaves). Path parity is necessary to prevent a target locale from falling through because a key is absent. It proves none of the following:

- propositional equivalence;
- preservation of negation, exception, modality, temporal scope, numeric uncertainty, or status grade;
- grammatical correctness after interpolation;
- whether an identical target value is deliberate;
- whether the value belongs to product UI, authoritative source content, an informative rendition, or a machine projection;
- whether a rendered sentence licenses the same operator action.

Accordingly, parity is a **catalogue integrity test**, not a `MultilingualAuthorityEquivalenceProtocol` certificate.

## Required complete-walk capture

A reproducible pass must start from the full tracked-tree denominator, not code-search results. The minimum command ledger is:

```text
git ls-tree -r --name-only dc7bdf79a
find shared -type f -path '*i18n*' -print
rg -n --hidden --glob '!node_modules/**' --glob '!.git/**' 'locale_preference|supported.*locale|\ben\b|\buk\b|\bru\b'
rg -n --hidden --glob '!node_modules/**' --glob '!.git/**' 'limited|may_not_use_for|stale|superseded|withdrawn'
rg -n --hidden --glob '!node_modules/**' --glob '!.git/**' 'MACHINE|Lex|machine[-_ ]readable|source[-_ ]content|source[-_ ]language|rendition'
rg -n --hidden --glob '!node_modules/**' --glob '!.git/**' '(\+|join\(|concat|template|interpolat|replace\()'
```

For each set-level zero, the evidence record must include: baseline ref; complete tracked-file count; files walked; parser or matching rule; exclusions; number of candidates inspected; executor; timestamp; and raw result location. A GitHub search-index zero is not admissible as absence because the index is neither a declared complete tree walk nor a stable denominator.

## Baseline coordinates and current evidentiary state

| ID | subject | coordinate or walk | state in this pass | admissible conclusion | class |
|---|---|---|---|---|---|
| B-01 | D4/D4-A1 UI locale posture | `docs/brand/ATLAS_SOURCE_OF_TRUTH.md`, section `D4 - Locale And i18n Posture` and D4-A1 | coordinate supplied by commission | `en` authored UI, `uk` translated UI, `ru` `legacy_continuity_frozen`, source-content rendering separate, RTL `not_supported` | `ratified_repo_fact` |
| B-02 | catalogue parity test | `shared/i18n/parity.test.ts` | coordinate supplied by commission | structural parity only; no semantic-equivalence claim | `bounded_repo_fact` |
| B-03 | catalogue cardinality and identity | complete recursive walk of all three locale catalogues | prior DS0 result only; current re-walk not reproduced in the connector readback available to this pass | prior result may be cited only with DS0 as executor | `reported_measurement` |
| B-04 | runtime capability contract | complete tree search for locale capability schema and validators | exact coordinate not safely recoverable from the available connector readback | no new repository capability claim | `unresolved_repo_baseline` |
| B-05 | frontend capability validator | complete tree search for allowed locale set and validation path | exact coordinate not safely recoverable from the available connector readback | no new repository capability claim | `unresolved_repo_baseline` |
| B-06 | `locale_preference` crossing | complete definition-and-call-site walk from selector through run-request serialization and backend consumption | crossing is reported in D4 evidence snapshot; persistence at `dc7bdf79a` not independently reproduced here | treat the crossing as a regression hypothesis, not a current fact | `reported_repo_risk` |
| B-07 | fragment composition | AST-assisted inventory of message construction plus catalogue interpolation sites | no complete denominator recovered | no absence claim; composition remains a mandatory implementation audit | `unresolved_repo_baseline` |
| B-08 | falsifier vocabulary | definition-to-render walk for `limited`, `may_not_use_for`, `stale`, `superseded`, `withdrawn` | search was commissioned; exact definition and surface coordinates not safely recoverable from connector readback | protocol must not presume existing semantic IDs | `unresolved_repo_baseline` |
| B-09 | MACHINE twins and Lex projections | complete walk for `MACHINE`, Lex, projections, serializers, and exported schemas | exact coordinates not safely recoverable from connector readback | machine consumers are specified as strict future/current consumers, not claimed implemented | `unresolved_repo_baseline` |
| B-10 | source-content decoupling | complete walk for source-language metadata, content rendition, UI locale binding, API fields, and display components | D4 requires decoupling; implementation not independently established | classify as `not_demonstrated`, not `absent` | `unresolved_repo_baseline` |

## Baseline risk register

### F-B01 — identity share is semantically non-diagnostic

**Finding.** Even a perfect three-catalogue path match and a low identity rate cannot demonstrate authority-semantic equivalence.

**Classification.** `architectural_inference`

**Consequence.** Catalogue parity remains in the test suite but cannot issue, upgrade, or contribute to an equivalence certificate.

### F-B02 — `locale_preference` must not select authoritative content

**Finding.** A UI preference may select product chrome; it must not select which legal text is authoritative, choose a legal source language, or silently request a frozen UI locale from a runtime that admits only `en`/`uk`.

**Classification.** `protocol_requirement`

**Consequence.** Run-request validation must type UI locale, source-content language, rendition purpose, and authority status separately.

### F-B03 — fragment composition is a semantic risk, not merely a grammar risk

**Finding.** English fragments can be composable while Ukrainian requires case, gender, number, animacy, aspect, or preposition changes. More importantly, moving a qualifier or exception into a reusable fragment can change its scope.

**Classification.** `external_evidence_supported_inference`

**Consequence.** High-stakes propositions are translated as whole messages or as typed message functions whose variables carry grammatical and semantic roles. Bare concatenation is non-certifiable.

### F-B04 — absence remains unproved

**Finding.** This pass did not obtain a model-visible complete tracked-tree readback sufficient to attach denominators to repository-wide zeros.

**Classification.** `measurement_limitation`

**Consequence.** No statement in INT-R6 uses an index miss as proof that semantic IDs, source-content metadata, or a rendering layer are absent. The implementation stage must execute the command ledger and close B-03 through B-10 before claiming baseline closure.
