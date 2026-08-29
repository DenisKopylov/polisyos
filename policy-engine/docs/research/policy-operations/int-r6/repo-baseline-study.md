# INT-R6 Repo Baseline Study

## Measurement frame

- Repository: `DenisKopylov/polisyos`.
- Pinned base: `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`.
- Branch under study: `research/int-r6-research`.
- Measurement party: the commissioned INT-R6 researcher, using the connected GitHub API. Where a result came from a complete Git tree or directory walk, the denominator is stated. Where the connector exposed content but could not hand raw bytes to an executable counter, the result is labelled `measurement_gap`; no historical number is reused as a current measurement.
- Finding classes used in this package: `repo_fact`, `external_practice`, `architecture_requirement`, `engineering_gap`, `institutional_gap`, `measurement_gap`, `open_question`, and `routed_architect_issue`. These are research classifications, not standing vocabularies.

## Complete-walk ledger

| Walk ID | Bounded set | Denominator | Method | What it can establish |
| --- | --- | ---: | --- | --- |
| `WALK-I18N-01` | `apps/runtime-dashboard/src/shared/i18n/**` | 18 blobs | complete recursive walk of the four direct files and the `locales`, `messages`, `formatters`, and `typography` subtrees | all files in the current frontend i18n owner cohort; absence claims limited to this cohort |
| `WALK-CATALOG-01` | `shared/i18n/locales/**` | 3 blobs | complete recursive tree walk | exact catalog blob identities and byte sizes |
| `WALK-CORPUS-01` | `src/polisyos/data_forge/domains/legal/corpus/**` | 6 blobs | complete recursive tree walk | all current legal-corpus structure/versioning files |
| `WALK-LAUNCH-01` | product-locale-to-run-request path | 4 named producer/contract files | complete read of the only locale owner, both request builders, and backend run/capability contracts | whether selected product locale crosses the launch boundary in the inspected canonical path |
| `WALK-STATUS-01` | five falsifier terms and their direct owners/surfaces | 8 named files | symbol-guided read from typed owner through validator/export/render surface | whether a typed ID exists, where free text remains, and how values render |
| `WALK-LEGAL-AXIS-01` | canonical legal source and NormPack contracts | 3 named owner files plus `WALK-CORPUS-01` | complete read of contract/model owners and complete legal-corpus walk | whether source language exists, and whether authenticity, co-authenticity, render language, and translation manifestation are first-class |

`WALK-I18N-01` contains:

- direct files: `LocaleProvider.test.tsx`, `LocaleProvider.tsx`, `locale.ts`, `parity.test.ts`;
- catalog files: `locales/en.json`, `locales/uk.json`, `locales/ru.json`;
- message file: `messages/icu-messages.ts`;
- formatter files: `currency.ts`, `date.ts`, `formatters.test.ts`, `number.ts`, `shared.ts`;
- typography files: `nonBreakingSpaces.ts`, `plexCyrillicFix.css`, `quoteMarks.ts`, `typography.test.ts`, `typography.ts`.

## Governing posture and scope boundary

### `INT-R6-F001` — D4-A1 is a UI-locale decision, not a universal source-language model

- Classification: `repo_fact`.
- Coordinate: `docs/brand/ATLAS_SOURCE_OF_TRUTH.md`, `D4 - Locale And i18n Posture`, amendment `D4-A1`.
- Finding: the ratified product posture is `en` authored/primary, `uk` translated, `ru` `legacy_continuity_frozen`; Russian source-content rendering is expressly separate and RTL is `not_supported` until evidence-backed admission.
- Consequence: INT-R6 must compose with D4-A1 and build the unimplemented source-content/authority-language layer. It must not re-open product UI authorship.

### `INT-R6-F002` — the older INT-R6 register row is superseded on source direction

- Classification: `repo_fact`.
- Coordinate: `docs/research/policy-operations-and-real-world-runtime-backlog.md`, row `INT-R6`, compared with D4-A1.
- Finding: the row still describes the earlier `uk`-primary posture; D4-A1 and this commission bind the direction `en -> uk` for product UI.
- Consequence: the stale row is evidence of historical framing only. It is not an authority source for the protocol.

## Product UI locale

### `INT-R6-F003` — current active product locales are exactly `en` and `uk`

- Classification: `repo_fact`.
- Coordinates:
  - `apps/runtime-dashboard/src/shared/i18n/locale.ts`: `SUPPORTED_LOCALES`, `PRIMARY_LOCALE`, `LEGACY_CONTINUITY_LOCALE`, `isProductLocale`, `resolveLocale`, `readStoredLocale`, `persistLocale`;
  - `src/polisyos/core/contracts/control.py`: `_SUPPORTED_LOCALES`;
  - `src/polisyos/runtime/http/services/control/capabilities.py`: capability response locale fields.
- Finding: frontend and backend admit only `en` and `uk`; `PRIMARY_LOCALE` is `en`; `ru` is named only as legacy continuity.
- Consequence: a normally selected `ru` product UI locale no longer exists in the current path. This closes the specific D4 evidence-snapshot crossing in which selectable `ru` was sent to a run.

### `INT-R6-F004` — product UI locale is still coupled to run semantics

- Classification: `engineering_gap`.
- Coordinates:
  - `apps/runtime-dashboard/src/features/composer/routes/ComposerModeSections.tsx`: `useI18n()` locale passed to launch builders;
  - `apps/runtime-dashboard/src/features/composer/domain/forms.ts`: `buildWorkflowLaunchRequest`, `buildNlLaunchRequest`;
  - `src/polisyos/core/contracts/control.py`: open `params`/`context` request maps.
- Finding: workflow launch writes `params.atlas_context.locale_preference`; NL launch writes `context.locale_preference`, both from the selected product UI locale. NL launch also writes `dynamic_text_policy = "source_text_only"`.
- Consequence: the old `ru` case is closed, but the axis crossing is not. Product chrome preference is still used as an operational content preference, and `source_text_only` does not identify the source language, legal authenticity regime, or requested render language.

### `INT-R6-F005` — the frontend provider has one language axis

- Classification: `engineering_gap`.
- Coordinate: `apps/runtime-dashboard/src/shared/i18n/LocaleProvider.tsx`.
- Finding: the provider imports only `en`/`uk`; selects one `ProductLocale`; falls back target catalog -> authored `en` -> key; gives the same locale to `TextPresentationProvider`; sets `document.documentElement.lang`; and does not expose a separate content-render locale or direction profile.
- Denominator: all 18 files in `WALK-I18N-01` were walked; no second content-language context, authentic-text context, or source-render request contract exists in that owner cohort.
- Consequence: source-content rendering has fragments but no independently selectable, typed, governed frontend axis.

## Catalogues and parity

### `INT-R6-F006` — exact current catalog blob coordinates

- Classification: `repo_fact`.
- Complete set: `WALK-CATALOG-01`, 3/3 blobs.

| Catalog | Blob | Bytes measured by Git tree |
| --- | --- | ---: |
| `en.json` | `c2e9070927213a5bdf3453165ee6825794e02134` | 137,508 |
| `uk.json` | `ded19bfcfbc65e457f1effc04d4ffb13debd8173` | 174,803 |
| `ru.json` | `07a1b4fadded69fc3435be9eca235eb85c4c24d4` | 136,204 |

The byte measure is a storage measure, not a translation-quality measure.

### `INT-R6-F007` — current structural parity proves paths, not meaning

- Classification: `repo_fact`.
- Coordinate: `apps/runtime-dashboard/src/shared/i18n/parity.test.ts`, `collectPaths`, `collectLeafPairs`, test `keeps the legacy-continuity Russian key set frozen`.
- Finding:
  - `PRIMARY_LOCALE` must be `en`;
  - `ukKeys` must equal authored `en` keys;
  - `ru` is frozen independently at 2,449 keys with a fixed key-set digest and fixed leaf-value digest;
  - the test does not compare translated meanings, entailment, modal force, scope, or status injectivity.
- Consequence: active path parity and frozen legacy integrity are useful invariants, but neither is `MultilingualAuthorityEquivalence`.

### `INT-R6-F008` — D4 identity percentages are historical, not current measurements

- Classification: `measurement_gap`.
- D4 snapshot: each catalog had 2,449 string leaves; `uk == en` at 888/2,449 (36.26%); `ru == en` at 1,963/2,449 (80.16%). The executing party recorded by D4 was DS0.
- Current pass: exact current blobs and structural assertions were re-derived, but connector content could not be handed to an executable raw-file counter. Therefore this pass does **not** assert a current `uk`/`ru` identity percentage.
- What identity would mean even if re-measured: a value identical to English is a mixed population — untranslated content, deliberate proper nouns/codes, controlled invariant terminology, or parity padding. Identity alone cannot classify those causes.
- Required closure: a later executable full-file walk must report both denominators, identical leaf count, and a classified sample or manifest; it must not infer “untranslated” from equality alone.

## Message composition and Ukrainian grammar

### `INT-R6-F009` — whole-message ICU support exists, but composition remains semantically unsafe by default

- Classification: `repo_fact`.
- Coordinates:
  - `shared/i18n/messages/icu-messages.ts`;
  - `shared/i18n/parity.test.ts`: count-message allowlist, numeric variable declarations, Ukrainian `one/few/many/other` checks;
  - `LocaleProvider.tsx`: `t`, `rich`, and `label`.
- Finding: the code has meaningful ICU and numerical-agreement controls. It also interpolates generic values and falls back to humanized raw identifiers. The parity tests themselves contain mixed Ukrainian/English outputs such as `review posture`, `packet`, `fleet`, and `needs`.
- Consequence: identical English fragments may be deliberate domain tokens or unfinished translation; generic placeholders may lack case/gender information needed by Ukrainian. A protocol must bind whole propositions and typed placeholder semantics, not approve fragment equality.

### `INT-R6-F010` — interpolation API does not carry grammatical features

- Classification: `engineering_gap`.
- Coordinate: `LocaleProvider.tsx`, `MessageValues` passed into ICU formatting; caller-specific messages in the catalog/parity suite.
- Finding: placeholders are value maps; no common contract supplies grammatical case, gender, animacy, or declension class for named entities.
- Consequence: a translator may be unable to produce a grammatically valid Ukrainian sentence without changing the source message API. The safe response is whole-message redesign or a typed morphology-aware term reference, not post-hoc string concatenation.

## Semantic IDs, statuses, and refusals

### `INT-R6-F011` — `stale`, `superseded`, and `withdrawn` already have distinct canonical IDs

- Classification: `repo_fact`.
- Coordinates:
  - `src/polisyos/core/contracts/decision_validity.py`: `DecisionValidityStatus`;
  - `apps/runtime-dashboard/src/api/validators.ts`: `decisionValidityStatusMembers`.
- Finding: the backend stable wire enum and frontend closed validator both preserve the three IDs separately.
- Consequence: INT-R6 must reuse the existing owner vocabulary. Translation labels must be injective over these IDs and must never create a second lifecycle lattice.

### `INT-R6-F012` — `limited` is not one globally owned semantic

- Classification: `repo_fact`.
- Coordinate: `src/polisyos/scientist/evidence/claims/models.py`: `ComparisonOptionStatus.LIMITED`, `BaselineComparisonStatus.LIMITED`.
- Finding: the same token appears in at least two scoped status owners.
- Consequence: glossary identity must be `(namespace, semantic_id, owner_version)`, not the bare English word `limited`.

### `INT-R6-F013` — `may_not_use_for` is structurally typed but its members are often free text

- Classification: `engineering_gap`.
- Coordinates:
  - `src/polisyos/core/contracts/search.py`: `SearchCandidate.may_not_use_for`;
  - `src/polisyos/scientist/evidence/claims/models.py`: authority-boundary output;
  - `apps/runtime-dashboard/src/features/trust/domain/posture.ts`: trust registry projections;
  - `apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx`: raw member rendering.
- Finding: the field name carries prohibition intent, but individual denied-use values are strings. The run paper localizes the heading and renders each member raw.
- Consequence: the falsifier “prohibition becomes advice” cannot be blocked by catalog parity. High-stakes denied uses need canonical refusal/denied-use IDs or a typed proposition with deontic force, scope, audience, and source owner.

### `INT-R6-F014` — many adjacent statuses remain open strings

- Classification: `engineering_gap`.
- Coordinate: `apps/runtime-dashboard/src/api/validators.ts` outside the closed decision-validity member set.
- Finding: some canonical vocabularies are closed while many status-bearing fields use `z.string()`.
- Consequence: protocol adoption must be owner-by-owner. It cannot claim that “all statuses already have IDs,” and it must not invent duplicate IDs where a canonical owner exists.

## MACHINE twins and Lex projections

### `INT-R6-F015` — the trust MACHINE twin proves artifact-to-DOM exactness, not translation equivalence

- Classification: `repo_fact`.
- Coordinate: `apps/runtime-dashboard/src/features/trust/export/trustPostureTwin.ts`.
- Finding: the twin reconstructs visible DOM semantics and requires exact equality with artifact IDs, limitations, blockers, timestamps, and source coordinates.
- Consequence: this is the strictest present consumer and a useful integration point. Future twins must serialize canonical IDs and source anchors; localized labels remain presentation and cannot replace IDs.

### `INT-R6-F016` — Lex has jurisdiction and document language, but not an authentic-text regime

- Classification: `engineering_gap`.
- Coordinates:
  - `src/polisyos/data_forge/domains/legal/contracts.py`: `LegalDocSource`, `SPOCandidate`;
  - `src/polisyos/lex/types.py`: `NormPackBuildRequest`, `SelectedDocVersion`;
  - complete legal-corpus walk `WALK-CORPUS-01`.
- Finding: `LegalDocSource` has `jurisdiction` and one `language`; NormPack has jurisdiction/time/domain/source IDs. No owner contract represents a designated-source rule, co-authentic member set, prevailing-language rule, translation manifestation, render locale, or divergence-resolution record.
- Consequence: source language is data today; the legal authority relationship among language manifestations is absent.

### `INT-R6-F017` — current legal extraction hard-codes a Ukraine-to-English pivot

- Classification: `engineering_gap`.
- Coordinate: `src/polisyos/data_forge/domains/legal/contracts.py`, `SPOCandidate`.
- Finding: the model declares `subject_en` as canonical English while retaining Ukrainian source fields such as `subject_uk` and `source_quote_uk`; statement identity is built around this two-language shape.
- Consequence: this is deployable for the current Ukraine-specific pipeline but not universal. A jurisdiction with another source language, several co-authentic languages, or no English equivalent cannot enter without schema change. The new architecture must remove this assumption from the authority layer while permitting the current adapter as a jurisdiction-specific projection.

## Source-content rendering and RTL

### `INT-R6-F018` — D4's source-content/UI decoupling has not been implemented as a governed contract

- Classification: `engineering_gap`.
- Evidence set: all 18 i18n files, both launch builders, backend locale/capability contracts, `LegalDocSource`, `SPOCandidate`, and Lex NormPack contracts.
- Finding: fragments exist — generic document language, Ukrainian source quotes, raw source-text policy, read-only legal workflows — but there is no independently admitted `content_render_locale`, no authenticity record, no rendering manifestation contract, and no bridge from such a record to the frontend.
- Capability classification: target multilingual authority layer is `absent/unallocated`; source-text fragments are implemented but not orchestrated into that layer.

### `INT-R6-F019` — RTL remains honestly unsupported and is not admission-ready

- Classification: `repo_fact` plus `engineering_gap`.
- Coordinates: D4-A1; `LocaleProvider.tsx` sets `document.documentElement.lang` but no direction profile.
- Finding: no named RTL jurisdiction or locale is admitted. The current provider exposes no content direction independent of UI locale.
- Consequence: INT-R6 must define a stable admission record and evidence bundle so RTL admission adds evidence/configuration, not a schema redesign. It must not claim runtime support now.

## Boundary census

| Boundary | Verdict | Existing owner or missing prerequisite |
| --- | --- | --- |
| product UI locale posture | `existing` | D4-A1; frontend `locale.ts`/`LocaleProvider`; backend capability contract |
| active catalog structural parity | `existing` | `parity.test.ts`; proves key-path parity only |
| frozen `ru` integrity | `existing` | fixed RU key/value digests in `parity.test.ts` |
| canonical decision-validity IDs | `existing` | `DecisionValidityStatus` and frontend closed validator |
| multilingual authority equivalence | `partial` | IDs/twins/ICU fragments exist; no protocol, evidence artifact, or semantic gate |
| source-content rendering bridge | `missing-bridge` | document language/source text fragments lack independent render/authenticity contract |
| authentic/co-authentic text ownership | `external-institution owner` per jurisdiction | PolicyOS records/integrates authority; it does not create legal authenticity |
| high-stakes linguistic adjudication | `external-institution owner`; currently unbound | no appointed holder; must refuse with missing-role state |
| RTL jurisdiction admission | `missing-bridge` | D4 evidence trigger exists; no admitted profile or runtime proof |

## Baseline conclusion

The repository has stronger ingredients than the task row suggests: active UI locale enforcement, a frozen legacy catalog, ICU plural controls, several typed semantic status vocabularies, source-coordinate machinery, and exact MACHINE-twin comparisons. It does **not** have the language-axis partition or the authority-evidence model required by the commission. Most critically, the legal extraction model currently embeds English as a canonical pivot and cannot represent co-authentic legal texts. These are findings about the layer D4-A1 deliberately left open; none requires changing D4-A1 itself.
