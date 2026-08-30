# INT-R6 repository baseline ledger

This appendix separates current connector observations, historical measurements, calculations, and
unresolved implementation questions. It does not treat a code-search miss as a repository-wide
absence and does not present connector output as a terminal transcript.

## Measurement identity

| field | value |
|---|---|
| repository | `DenisKopylov/polisyos` |
| base main | `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f` |
| package SHA measured | `5e47c868c2c1d4d66fa11fcddcc972dbb55e95d3` |
| pre-repair SHA read | `b612b21272c732d53cfde8569846cfb7a0c73f5a` |
| current catalogue evidence class | `institutionally_supplied` architect walk; not executed by the Stage-3 author or Stage-5 remediator |
| prior measurement party | DS0, for the 2,449/888/1,963 snapshot only |
| catalogue path denominator | exactly the 3 named locale paths below |
| catalogue file-type denominator | 3 JSON files / 3 total files under the pinned locale directory |
| leaf unit | terminal JSON value whose runtime type is `str` |
| identity unit | shared dot-path whose target string is byte-identical to the `en` string |

## Current three-catalogue census

### Connector observations

`GitHub.fetch_blob`, pinned to the package tree, returned these exact blobs:

| path | blob SHA | bytes | file type |
|---|---|---:|---|
| `policy-engine/apps/runtime-dashboard/src/shared/i18n/locales/en.json` | `c2e9070927213a5bdf3453165ee6825794e02134` | 137,508 | JSON |
| `policy-engine/apps/runtime-dashboard/src/shared/i18n/locales/uk.json` | `ded19bfcfbc65e457f1effc04d4ffb13debd8173` | 174,803 | JSON |
| `policy-engine/apps/runtime-dashboard/src/shared/i18n/locales/ru.json` | `07a1b4fadded69fc3435be9eca235eb85c4c24d4` | 136,204 | JSON |

The bounded directory contained exactly those three files. No code-search result contributed to the
path or file-type denominator.

### Institutionally supplied values — Terminal B

The Stage-3 author-execution and independent-parser assertions are withdrawn. The published harness
is not treated as an executed artifact, and no author/auditor independent catalogue measurement is
claimed.

The following values are recorded as `institutionally_supplied` under W4-K01 from the architect walk
of the exact three-path population above:

```text
string leaves: en=2618, uk=2618, ru=2449
uk == en on shared paths: 894 / 2618 = 34.15%
ru == en on shared paths: 1936 / 2449 = 79.05%
en paths absent from ru: 169
uk-only paths: 0
ru-only paths: 0
```

These figures are descriptive inputs, not this package's execution result. Under W4-K01 they settle
no zero: they do not establish repository-wide absence, translation quality, semantic equivalence,
or an independently reproduced census. The exact path and file-type denominators remain connector
observations; the leaf and identity values remain institutionally supplied.

The three catalogues have unequal supplied denominators. Active `en`/`uk` path parity and frozen `ru`
integrity are structural policies, while semantic equivalence is a proposition-level claim. The
unequal denominators make the distinction visible without changing the evidence class.

## Historical DS0 snapshot

DS0 reported 2,449 string leaves in each catalogue, with 888 `uk == en` leaves and 1,963
`ru == en` leaves:

- `888 / 2,449 = 36.2596978…%`, rounded to 36.26%;
- `1,963 / 2,449 = 80.1551654…%`, rounded to 80.16%.

Those values remain attributed to DS0. They are not current values and remain separate from the
institutionally supplied current figures.

An identical leaf has materially different possible causes: untranslated text; a proper noun,
identifier, code, or product name intentionally held constant; an English loan or controlled shared
term; or parity padding. Identity rate is therefore a triage signal, never translation-quality
evidence.

## What catalogue parity can prove

The exact coordinate is
`policy-engine/apps/runtime-dashboard/src/shared/i18n/parity.test.ts`. Its admissible claim is
structural: active `uk` paths equal authored `en` paths, and the frozen `ru` key/value population has
registered integrity digests. It proves none of the following:

- propositional equivalence;
- preservation of negation, exception, modality, temporal scope, numeric uncertainty, or status grade;
- grammatical correctness after interpolation;
- whether an identical target value is deliberate;
- whether a value is UI chrome, authoritative content, an informative rendition, or a machine projection;
- whether a rendered sentence licenses the same operator action.

Accordingly, parity is a catalogue-integrity test, not a MAEP certificate.

## Restored bounded repository coordinates

The repair had removed the following bounded observations. They are restored here with their original
method/denominator and current claim strength; none is promoted into a repository-wide zero.

| ID | bounded set and method | denominator | exact coordinates | amended conclusion |
|---|---|---:|---|---|
| B-01 | frontend i18n owner cohort, recursive connector tree walk | 18 blobs | `apps/runtime-dashboard/src/shared/i18n/**` | one product-locale owner cohort; no complete source-content axis in that bounded cohort at the pre-repair/package baseline |
| B-02 | locale catalogues, recursive connector tree walk | 3 JSON / 3 files | `.../locales/{en,uk,ru}.json` | exact current blob identities; leaf/identity values above are institutionally supplied and settle no zero |
| B-03 | legal corpus subtree, recursive connector tree walk | 6 blobs | `src/polisyos/data_forge/domains/legal/corpus/**` | absence conclusions limited to that bounded corpus owner subtree |
| B-04 | product-locale launch path, complete read of named owner/builders/contracts | 4 named files | `shared/i18n/locale.ts`; `features/composer/routes/ComposerModeSections.tsx`; `features/composer/domain/forms.ts`; `src/polisyos/core/contracts/control.py` | selected product locale crosses request construction as `locale_preference`; downstream semantic effect remains an implementation question |
| B-05 | falsifier terms, symbol-guided owner-to-surface read | 8 named files | decision-validity owner/validator; claims/search owners; trust and run-report surfaces | `stale`/`superseded`/`withdrawn` have distinct canonical IDs; `limited` is namespaced by owner; `may_not_use_for` members remain string-valued in inspected contracts |
| B-06 | legal language axis, owner reads plus B-03 | 3 named owner files + 6 corpus blobs | `data_forge/domains/legal/contracts.py`; `lex/types.py`; legal corpus subtree | language/jurisdiction exist, but authority-set/rendition relation is not a first-class admitted capability |

The 18-file i18n denominator comprised four direct files, three catalogues, one message file, five
formatter files, and five typography files. It is retained as a bounded pre-repair/package observation,
not enlarged into a whole-repository absence claim.

### Restored named facts

- `docs/research/policy-operations-and-real-world-runtime-backlog.md`, row `INT-R6`, retains the stale
  `uk`-primary framing. D4-A1 supersedes that source direction for product UI; the row is historical
  framing only and is not an authority source for this protocol.
- `apps/runtime-dashboard/src/shared/i18n/locale.ts` defines active `en`/`uk`, `PRIMARY_LOCALE=en`,
  and `LEGACY_CONTINUITY_LOCALE=ru`.
- `apps/runtime-dashboard/src/features/composer/domain/forms.ts` serializes product locale into
  workflow/NL request context as `locale_preference`; it does not establish that the backend uses it
  to select legal authority.
- `apps/runtime-dashboard/src/shared/i18n/LocaleProvider.tsx` is a single product-locale provider; a
  second governed source-content selector was not established in the bounded 18-file cohort.
- `src/polisyos/core/contracts/decision_validity.py` owns distinct lifecycle IDs including `stale`,
  `superseded`, and `withdrawn`.
- `src/polisyos/core/contracts/search.py` exposes `SearchCandidate.may_not_use_for`; inspected member
  values are strings, so field naming alone does not prove deontic preservation.
- `src/polisyos/scientist/evidence/claims/models.py` contains separately owned `LIMITED` statuses;
  the bare word is not a global semantic ID.
- `apps/runtime-dashboard/src/api/validators.ts` contains the closed decision-validity member set
  alongside adjacent status-bearing fields validated with `z.string()`. This observation is bounded
  to that one named validator file and requires owner-by-owner protocol adoption.
- `apps/runtime-dashboard/src/features/trust/export/trustPostureTwin.ts` proves exact artifact-to-DOM
  projection for its bounded fields, not translation equivalence.
- `src/polisyos/data_forge/domains/legal/contracts.py` defines `LegalDocSource.language` and the
  Ukraine/English-shaped `SPOCandidate`; this is a concrete current pivot seam, not a universal model.
- `src/polisyos/lex/types.py` carries jurisdiction/version selection but no admitted co-authentic text
  relation or content-render locale.

## Predecessor→successor claim matrix

“Superseded” is not used as a disposition. Every substantive claim in the two removed predecessors
at `b612b21272c732d53cfde8569846cfb7a0c73f5a` is handled below.

| predecessor claim/method | predecessor denominator | successor action | successor location / what is now true |
|---|---:|---|---|
| complete frontend i18n cohort | 18 blobs | **restore as bounded historical/current-baseline observation** | B-01 and restored named facts; no whole-repository absence |
| exact catalogue files/blobs/bytes | 3/3 JSON | **restore; retain supplied numeric census separately** | connector table plus institutionally supplied values; no author-execution claim |
| DS0 2,449/888/1,963 percentages | 3 catalogues in DS0 snapshot | **retain as historical; keep current supplied values separate** | historical DS0 section; never labelled current execution |
| active locale contract (`en`,`uk`; frozen `ru`) | named frontend/backend owners | **restore** | B-01/restored named facts; D4-A1 remains governing |
| `INT-R6-F002` — compare stale Wave-2 `INT-R6` row with governing D4-A1 | 1 named backlog row + 1 governing D4-A1 record | **restore as historical and record supersession boundary** | restored named facts; `en -> uk` governs product UI and the stale row is not protocol authority |
| `locale_preference` crossing | 4 named path files | **restore with narrower conclusion** | B-04; serialization established, downstream authority selection not established |
| one frontend language context | 18-file bounded cohort | **restore with bounded absence language** | B-01/restored named facts |
| structural parity and frozen integrity | named parity test | **restore** | parity section; semantic inference expressly prohibited |
| whole-message/ICU strengths and morphology gap | named message/provider/parity files | **restore** | main report and protocol fixtures; no claim that MAEP is implemented |
| distinct validity IDs and namespaced `limited` | named owners/validator | **restore** | B-05/restored named facts |
| free-string `may_not_use_for` members | four named owners/surfaces | **restore** | B-05; routed to canonical-owner mapping rather than local lattice |
| `INT-R6-F014` — complete read of adjacent status-bearing declarations outside the closed decision-validity set | 1 named validator file; declarations outside the named closed member set | **restore as bounded repository observation** | restored named facts; adoption remains owner-by-owner and no duplicate ID is invented |
| trust MACHINE twin exactness | one named twin | **restore** | restored named facts; limited to artifact/DOM parity |
| Lex language/jurisdiction but no authority relation | 3 owners + 6 corpus blobs | **restore with bounded conclusion** | B-06; capability remains absent/unallocated |
| `SPOCandidate` Ukraine→English pivot | one named owner | **restore** | restored named facts and language-axis appendix |
| source-content/RTL bridge absent in inspected cohort | named owners + bounded walks | **restore as `not_established`/missing bridge, not global absence** | B-01/B-06 and protocol residuals |
| pre-repair main task boundary and boundary census | one 139-line artifact | **restore substance** | substantive report sections and this matrix |
| shell-framed connector receipt in pre-repair main | no shell process for the displayed values | **retract** | no amended package artifact presents connector facts under shell framing |
| incomplete headings 3–10 in pre-repair main | one artifact | **retract as substantive deliverable** | retained scaffold now identifies itself as navigation/history only |

A complete heading read of the pre-repair baseline found **19 unique numbered findings**,
`INT-R6-F001`–`INT-R6-F019`. The prior matrix accounted for F001 and F003–F013 and F015–F019; the two
new rows above individually disposition F002 and F014 with their original bounded methods and
denominators.

```text
numbered predecessor findings 19
individually dispositioned 19
unaccounted 0
```

The three non-duplicative delivery/orientation claims from the removed 139-line main file remain
unchanged and separately accounted in the final three rows.

## Remaining measurement limitations

The exact catalogue paths, blobs, bytes, and 3-JSON/3-file denominator are connector-established.
The leaf and identity figures are `institutionally_supplied` and settle no zero. The following remain
open and must not be used as settled premises:

- independent author/auditor execution of the current catalogue leaf/identity census;
- complete repository-wide fragment/message composition denominator;
- complete owner mapping for all proposed relation/result/refusal values;
- implemented producer/consumer chain for MAEP certificates and vacant-holder refusals;
- named institutional holders and jurisdiction-specific legal reconciliation rules;
- real English→Ukrainian authority-error corpus and behavioural ground truth;
- runtime proof for source-content decoupling or RTL source rendering.

## Baseline conclusion

The repository has useful ingredients: active UI-locale enforcement, a frozen legacy catalogue, ICU
plural controls, typed lifecycle IDs, source-coordinate machinery, and an exact MACHINE-twin pattern.
It does **not** thereby have the commissioned multilingual-authority capability. The language-axis
partition, authority-text-set relation, evidence-bounded certificate, role appointments, and verified
runtime chain remain `absent/unallocated`. These findings concern the layer D4-A1 deliberately left
separate and do not reopen D4-A1.
