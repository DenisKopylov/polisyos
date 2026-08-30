# INT-R6 Preserve And Recovery Ledger

## Verification Identity

Evidence is pinned to amendment SHA `8137aa31a4bf5e06c6b1abd4e20458295fd5a506`,
audit SHA `bae4f8c2b5e5ef340dda73f17bfe852c1d0d3cee`, and pre-repair SHA
`b612b21272c732d53cfde8569846cfb7a0c73f5a`.

## Twelve Preserve-Property Checks

| # | audit property | verifier evidence | result |
|---:|---|---|---|
| 1 | D4-A1 unchanged | main, partition and `06` retain `en` authored, `uk` translated, `ru` frozen; source rendering separate; RTL UI unsupported | preserved |
| 2 | UI locale never selects legal authority | main/partition/protocol keep `ui_locale` outside authority selection | preserved |
| 3 | authority attaches to versioned jurisdictional text/member/set | external evidence, record model and MAEP-1 bind source members/sets and versions | preserved |
| 4 | co-authentic peers stay peers absent jurisdictional precedence | Canada/EU fixtures and MAEP-1 retain all required members without synthetic source | preserved |
| 5 | English may aid UI/indexing but is not universal legal authority | partition lists rejected and admitted English uses separately | preserved |
| 6 | existing namespaced status/refusal owners reused | proposed reasons must map to existing owners or remain explicit gaps/unallocated | preserved |
| 7 | `stale`, `superseded`, `withdrawn` remain distinct | protocol, fixtures and findings retain three IDs, remedies and projection requirements | preserved |
| 8 | translation and adaptation remain separate | protocol has separate transformations, results, certificates and readability evidence | preserved |
| 9 | three falsifiers remain red-first beyond parity | each malicious target preserves paths/placeholders and fails semantic oracle | preserved |
| 10 | zero holders remain representable and purpose-scoped | role/appointment/decision records remain separate; unrelated functions require separate proof | preserved |
| 11 | history is append-only | certificate invalidation preserves old certificate/source/rendition history | preserved |
| 12 | external practice is evidence, not repository capability | external appendix and protocol status disclaim implementation/authority transfer | preserved |

Result: **12/12 preserved**. None of the closure failures requires weakening a preserved property.

## IR6-A02 Predecessor Population

Connector reads at `b612b212…` established:

- `int-r6/repo-baseline-study.md`: 223 lines and **19 uniquely numbered findings**
  `INT-R6-F001`–`INT-R6-F019`;
- `int-r6-multilingual-authority-equivalence.md`: 139 lines, including three non-duplicative
  delivery/orientation claim families used below;
- successor matrix: `int-r6/01-repository-baseline.md`, amendment SHA, 17 grouped rows.

The numbered-finding denominator is 19, not the successor's row count. The main-file denominator is
three explicit claim families, counted separately to avoid double-counting baseline summaries.

## Predecessor-To-Successor Claim Verification

| predecessor ID | predecessor claim | successor disposition/evidence | verified |
|---|---|---|---|
| F001 | D4-A1 governs UI, not universal legal source language | main D4 composition; matrix active-locale/D4 row | yes |
| F002 | stale Wave-2 INT-R6 row is superseded on source direction | consequence follows D4-A1, but matrix has no individual retain/retract/recompute disposition | **no** |
| F003 | active UI locales exactly `en`,`uk`; `ru` legacy | active-locale row and restored named facts | yes |
| F004 | `locale_preference` still crosses launch boundary | B-04 plus restored named facts, narrowed downstream conclusion | yes |
| F005 | frontend has one language context | B-01, 18-blob denominator, bounded absence wording | yes |
| F006 | exact catalogue blobs and byte sizes | connector table and current census | yes |
| F007 | parity proves structure, not meaning | parity section with exact coordinate | yes |
| F008 | DS0 figures historical, not current | historical DS0 section plus separate current result | yes |
| F009 | ICU/whole-message strengths coexist with composition risk | matrix ICU/morphology row and protocol fixtures | yes |
| F010 | interpolation API lacks common grammatical-feature contract | grouped ICU/morphology disposition and typed-message requirement | yes |
| F011 | `stale`,`superseded`,`withdrawn` have distinct IDs | B-05/restored facts | yes |
| F012 | bare `limited` has multiple scoped owners | B-05/restored facts | yes |
| F013 | `may_not_use_for` members remain free strings | B-05/restored facts and mapping requirement | yes |
| F014 | adjacent status-bearing fields remain open strings | no matrix row or restored named fact preserves this broader `z.string()` observation | **no** |
| F015 | trust MACHINE twin proves artifact/DOM exactness only | restored trust-twin fact | yes |
| F016 | Lex has language/jurisdiction but no authority-text regime | B-06 and bounded capability conclusion | yes |
| F017 | `SPOCandidate` embeds Ukraine→English pivot | restored pivot fact and partition treatment | yes |
| F018 | governed source-content/UI decoupling absent | B-01/B-06 and remaining implementation limits | yes |
| F019 | RTL remains unsupported/not admission-ready | source-content/RTL grouped row and D4/RTL residual | yes |

Numbered baseline result:

```text
accounted 17
unaccounted 2
total 19
```

The 139-line predecessor main contributes three non-duplicative delivery/orientation claims:

| main-file claim family | successor action | verified |
|---|---|---|
| task boundary and baseline/boundary census | restored across substantive main and baseline matrix | yes |
| connector facts displayed under shell framing | explicitly retracted; amended package uses connector labels | yes |
| headings 3–10 presented as substantive but empty | retracted as substantive; retained 27-line scaffold declares navigation/history role | yes |

Main-file result: **3/3 accounted**.

## Recovery Verdict

`IR6-A02 = partially_closed`.

The successor recovers most evidentiary substance and correctly narrows several old claims. It does
not meet the audit's “each claim individually” requirement because 2 of 19 numbered predecessor
findings lack a typed disposition. Calling the matrix complete is therefore stronger than its
population supports.

## Residual Band

This verification does not re-adjudicate whether predecessor F002 or F014 should survive; Stage 4
only records that the amendment did not disposition them. It also does not treat grouping several
claims in one successor row as defective when every grouped claim remains identifiable and bounded.

## Connector Receipts

- Predecessor reads: `GitHub.fetch_file` at `b612b212…`, both removed files.
- Successor read: `GitHub.fetch_file` at `8137aa31…`, `01-repository-baseline.md`.
- No search-index result contributed to the 19-row denominator.
