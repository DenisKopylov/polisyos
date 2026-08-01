---
title: "Atlas DS4 Status-Grammar Rebinding Closure"
type: closure-report
status: implementation_complete_no_merge_baseline_red - architect review pending
created: 2026-08-01
slice: DS4
branch: codex/atlas-ds4-status-grammar
execution_base_commit: 61d354f62023460a45c60c913976cdfc4b779cf5
plan: ./DS4-status-grammar-rebinding.md
journal: ./DS4-status-grammar-rebinding-journal.md
---

# Atlas DS4 Status-Grammar Rebinding Closure

## Decision

DS4 is complete on its isolated branch and is ready for architect review. It is
not merged or pushed. The dashboard now projects producer-owned authority,
time, evidence, provenance, and quantity semantics through rebound living
families and the single `@polisyos/atlas-ui` package owner. It does not create a
parallel status grammar or claim producer contracts that do not exist.

The closure is baseline-red, not falsely green:

- full Vitest retains exactly three DS6-owned i18n parity failures;
- Playwright visual retains exactly one DS8-owned print-product failure;
- the three absent closed waist vocabularies remain explicit DS5 debt;
- readiness/scientific producer binding remains explicit DS16 debt;
- full `designTokens.ts` sunset remains DS6-evidence-gated.

The authoritative row narratives and lifecycle states live in
`architecture/atlas_surfaces/frontend-disposition-register.json`,
`architecture/atlas_surfaces/status-retirement-inventory.json`,
`architecture/atlas_surfaces/ds4-waist-debt-register.json`, and
`architecture/atlas_surfaces/frontend-baseline-debt-manifest.json`. This report
summarizes those artifacts; it does not replace them.

## Final clean-tree receipts

These receipts were recomputed from clean commit `470a802d4` before the
documentation-only C20 commit.

| Gate | Before | Final receipt |
| --- | --- | --- |
| frozen install | required | PASS; six workspace projects, frozen lock current, resolution skipped |
| dashboard typecheck | green | PASS |
| production build | green; 3,871 modules / PWA 101 | PASS; 3,885 modules / PWA 108; postbuild security and atlas-ui Tailwind-source proof pass |
| full lint | 75 errors / 22 files | PASS; 0 errors / 0 warnings; live JSON comparator passes |
| full Vitest | 5 failures / 3 files | BASELINE-GREEN; 312 files / 893 tests, 311 files / 890 tests pass; exactly 3 failures in 1 file |
| custom architecture | 36 violations / 28 files | PASS; 0 violations; live JSON comparator passes |
| dependency architecture | not absolute-green | PASS; 0 violations over 1,019 modules / 4,150 dependencies |
| accessibility | one missing component companion | AUTOMATED-GREEN; static contrast, motion, and color-blind gates; 84 / 84 files and 85 / 85 component tests; 21 / 21 browser tests; four owner-cluster real-browser contrast results remain explicitly `incomplete` below |
| Storybook | existing harness | PASS; 44 / 44 files and 97 / 97 tests; inherited CSS import-order advisories only |
| visual regression | 3 / 18 pass at C19b preflight | HONEST-RED; 17 / 18 pass; only `run detail A4 print` remains red under the DS8 row |
| atlas-ui package | absent | PASS; typecheck, lint, 36-source architecture, 18 / 18 files and 86 / 86 tests |
| DTCG projection | absent | PASS; official 2025.10 schema and generated-output drift check |
| DS19 governance | 261 roots / 23 negatives / 7 censuses | PASS; 261 roots / 13 supplemental / 23 negatives / 8 censuses; source-byte and corruption probes pass |
| status governance | no typed retirement authority | PASS; 47 DS1 rows, 15 current authored definitions, 55 semantic-history exemptions, 0 live retirement debts, 3 waist debts; corruption probes pass |
| Atlas governance unittests | existing checkers | PASS; 98 / 98 across baseline manifest, disposition register, and status inventory |

The only Vitest failures are the untouched
`panels.agentPipeline.overBudget` en/uk/ru identities in
`src/shared/i18n/parity.test.ts`. The temporal-cursor failure is closed by
clock injection without changing product time semantics. The
`OperatorDiagnosticPanel` structural a11y census is closed without an allowlist
entry. The baseline comparator accepts the live failure signatures and rejects
new identities.

The automated accessibility denominator is absolute-green, but it is not a
claim that every translucent or gradient-backed foreground has a computed
contrast result. Axe still reports four reviewed source clusters as
`incomplete`, not violations and not passes: C01 owns the neutral `Badge`
variant; C06 owns `ProvenancePopover` and `ProvenanceMiniGraph` foregrounds;
C09 owns `TimeSemanticsLabel` inheritance; and C14 owns `CandidateFrame`,
`NegativeCertificateCard`, and `WeakestLinkExplainer` foregrounds. They are not
suppressed or counted green. The journal records the exact source identities
and the closure signal: a real-browser opaque-background probe must compute
WCAG-AA contrast without attributing an incomplete node to the source.

The visual red is not suppressed, skipped, quarantined, retried, tolerance-
widened, or blessed. The committed run-detail expectation remains byte-equal to
its predecessor. The current product capture is 770 x 13229 versus 724 x 2113
because the global print link rule emits a long signed URL into the report.
`adjacent-print-export` remains `rebind_pending`, owner DS8, with DS6 independent
verification and an executable closure signal.

## 89-component disposition reconciliation

The approved pre-Ruling-3 matrix was **35 package migrations / 42 dashboard
rebinds / 12 use-as-is = 89**. Ruling 3 superseded five assumed primitive
migrations after the live-consumer and DS2-ledger census:

- `DropdownMenu`, `Separator`, and `Sheet`: package migration -> retirement;
- `ScrollArea` and `Tabs`: package migration -> `use_as_is` under their exact
  DS2 conditions.

Two later live-consumer/ledger censuses also superseded speculative calls:

- C15 changed 5 package + 1 rebind to 3 package + 3 `use_as_is`;
- C16 changed 3 package to 2 package + 1 consumer-missing `use_as_is`.

The authoritative realized accounting is therefore **27 package migrations /
41 dashboard rebinds / 18 use-as-is / 3 retirements = 89**. Reporting the old
35 / 42 / 12 split as completed would contradict the architect's rulings and
the three mixed register receipts.

| Family | Count | Cluster | Final call | DS2 adoption IDs | Register authority |
| --- | ---: | --- | --- | --- | --- |
| `ui-primitives-root` | 29 | C01-C03 | 22 package, 2 rebind, 3 retire, 2 use-as-is | component button/badge/panel/card/text-field/text-area/select/checkbox/switch/tabs/dialog/toast/empty-state/skeleton/card-button/cluster/scroll-area/sidebar-nav/stack/top-bar/visually-hidden rows | `ui-primitives-root` -> `atlas-ui-primitives`; `rebind_pending/strangled`; typed mixed receipt |
| quantity | 5 | C06-C08 | 5 rebind | `viz-contract-uncertainty-contract`, `component-provenance-graph`, `viz-chart-provenance-lineage`, `component-provenance-map` | `ui-quantity` -> `dashboard-quantity-generated-waist-rebind`; strangled |
| temporal | 5 | C09 | 5 rebind | none; rejected `component-decision-timeline` unused | `ui-temporal` -> `dashboard-temporal-generated-waist-rebind`; strangled |
| authored-text | 3 | C10 | 3 rebind | `content-trust-copy` material only | `ui-authored-text` -> `dashboard-authored-candidate-posture`; strangled |
| trust-view | 8 | C11 | 8 rebind | `component-governance-gate`, `component-provenance-map`, `component-provenance-graph` | `ui-trust-view` -> generated verification rebind; strangled |
| operator diagnostics | 1 | C12 | 1 rebind | none | `ui-operator-diagnostics` -> generated-evidence rebind; strangled |
| counterfactual | 10 | C13 | 6 rebind, 4 use-as-is | `component-uncertainty-band`; point-centric `viz-chart-uncertainty-band` remains rejected | `ui-counterfactual` -> generated scenario rebind; strangled |
| nested compounds | 15 | C14 | 11 rebind, 4 use-as-is | governance-gate/provenance/timeline/waterfall rows; phantom decision timeline unused | `ui-compounds` -> generated-waist rebind; strangled |
| `ui-compounds-root` | 6 | C15 | 3 package, 3 use-as-is | `component-data-table`, `component-metric-card`, `component-provenance-graph`, `viz-chart-provenance-lineage` | exact mixed package/transitional-winner receipt; strangled |
| patterns | 3 | C16 | 2 package, 1 consumer-missing use-as-is | two-pane/supporting-pane, search-field, search-source-selection rows remain condition-gated | exact mixed package/SearchableList receipt; strangled |
| responsive | 4 | C17 | 4 use-as-is | `responsive-shell-navigation`; rejected breakpoint taxonomy unused | generated breakpoint adapter; strangled without claiming family replacement |
| **Total** | **89** | C01-C17 | **27 package / 41 rebind / 18 use-as-is / 3 retire** | ledger-gated only | register reconciled |

The three token modules are outside the 89 TSX denominator. C04 rebinds their
values through the package projection, while `ui-tokens` honestly remains
`rebind_pending/pending` until DS6 proves the complete compatibility sunset.

## C03b retirement receipts

The register's `ds4-c03b-ui-primitives-mixed-disposition` receipt is the
authority. Its pre-deletion resurrection commit is
`caa1ee6e3ab49d559b19dbeeda6308c3598e7183`, with an exact blob for each deleted
implementation and a11y companion. The resurrection rule is
`recreate_in_atlas_ui_only_with_a_real_production_consumer_never_restore_in_the_app_tree`.

- `DropdownMenu`, `Separator`, `Sheet`: retired for
  `no_production_consumer`; no exact DS2 adoption row.
- `ScrollArea`: retained `use_as_is` because: “Archive admission alone sunsets
  nothing. DS4 may remove a mapped loser only after generated/source ownership,
  consumer migration, drift checks, and the owning slice's DS6 evidence are
  complete.”
- `Tabs`: retained `use_as_is` because: “Keep the mapped live v4 family as the
  transitional winner until DS4 routes a real consumer through one governed
  replacement, DS6 passes its negative/browser/accessibility evidence, and the
  old import path is removed.”

## Status-retirement and authority closure

The original 47 DS1 definitions reconcile to **15 lattice-derived / 24
interaction-state / 8 removed**. The live scanner finds 15 current authored
definitions and zero live retirement debt. It rejects renamed aliases, inline
synonyms, function-return vocabularies, marker-only generated lookalikes, and
sibling-consumer bypasses.

C21 reduced the corrected 19-definition live retirement queue to 6 by retiring
ten mechanical vocabularies and classifying three genuine presentation
taxonomies. C22 reduced 6 to 0 by removing run-lifecycle guessing, requiring
generated provenance posture, and retiring four return unions. C23 removed all
unsigned readiness and scientific-composition synthesis and renders the values
unavailable/opaque.

The C23 producer capability remains an explicit DS16 row:
`producer-binding-readiness-scientific-depth`, states `producer_missing`,
`artifact_missing`, `bridge_missing`, and `semantic_test_missing`. It closes
only when every named value resolves to a generated field or typed refusal and
the containment negatives remain green. DS4 did not build that producer.

## Debt deltas

| Debt class | Before | After | Ownership/evidence |
| --- | ---: | ---: | --- |
| quantity lint | 75 identities / 22 files | 0 / 0 | C06 20, C07 37, C08 18 exact resolutions; rule remains enabled |
| temporal cursor | 1 failure | 0 | C09 injected test clock; product time meaning unchanged |
| structural a11y census | 1 failure | 0 | C12 added the real companion; no allowlist suppression |
| i18n parity | 3 failures | 3 | untouched DS6 debt, one file |
| architecture | 36 identities / 28 files | 0 / 0 | C06 13, C09 7, C10 1, C11 9, C13 5, C18 1 |
| status retirement | corrected 19 live debts at C14 audit | 0 | C21 19 -> 6; C22 6 -> 0 |

The initial architecture set was one app/workspace feature-internal edge plus
35 shared-to-app/feature edges. Phase A separately observed 23 API/app ownership
breaches, but did not leave DS4 a distinct, provenance-bound 23-item manifest.
DS4 therefore does not claim an independently measured 23 -> 0 denominator.
Insofar as those observations are represented in the governed 36-identity edge
manifest, the class is closed; the exact closure claim is 36 -> 0, and both the
custom and dependency architecture gates are absolute-green.

## Three DS5 waist debts and neutral swap points

All three rows are `bridge_missing` + `surface_missing`, owner `DS5 waist`, and
have estate denominator effect `none`. Each carries
`master_inherited_debt_action = flag_for_architect_insertion_at_c20`; the
architect, not DS4, owns the master-plan table insertion.

| Debt | Generated-client anchor | Single swap module | Current behavior |
| --- | --- | --- | --- |
| CGF disposition | `canonicalRuntimeApiClient.ts:516`; `types.ts:5850-5879`, `GenerationCycleDispositionPayload` | `shared/ui/compounds/cgfDispositionPresentation.ts` | owner JSON passes opaquely; unknown is explicit unrecognized |
| decision grade | export block `canonicalRuntimeApiClient.ts:333-394`; missing `DecisionGrade` export in `types.ts` | `shared/ui/compounds/decisionGradePresentation.ts` | every owner label remains opaque/unrecognized until DS5 supplies a union |
| cache-age lattice | `canonicalRuntimeApiClient.ts:737`; `types.ts:8164-8182`, `ProjectionFreshness` | `shared/ui/temporal/cacheAgePresentation.ts` | source freshness remains source truth; no cache-age inference from timestamps |

Each module has two required negatives: a novel owner label renders explicit
`unrecognized`, and the module exports no value-level vocabulary constants.
Terminal kinds and evidence classes remain opaque extensions end to end; DS4
does not close or order them.

## Token-adapter parity

| Named gap | DS4 state | Evidence / remaining condition |
| --- | --- | --- |
| warm-dark | closed | ADR-047 light/dark values preserved; no identity swap |
| z-index | closed for projection | all eight aliases exact; raw Tailwind census remains explicit |
| post-reference aliases | closed | complete light/dark semantic and chart alias comparison |
| density/runtime controls | closed | all 35 values for comfortable/compact/condensed plus provider behavior |
| breakpoint projection | closed for generated adapter | five live tiers and 1280-token/1281-runtime asymmetry; DS6 still owns full browser evidence |
| mode provider | closed | light/dark/system descriptors drive the living providers |
| forced color | closed | high/contrast-more/forced-color rule graphs preserve cascade order |
| motion | closed | 240 ms CSS / 180 ms helper asymmetry explicit; reduced-motion behavior complete |
| print | closed for token semantics | imported page/utility/shell/deck/export rules compare in order; separate DS8 run-detail product defect remains open |

The official DTCG 2025.10 schema, one-way projector, generated-output hashes,
source/output manifest, semantic parity tests, and adversarial drift tests are
green. `designTokens.ts` is not claimed sunset: full removal still requires DS6
evidence.

## Harness and real-panel proof

The Storybook/a11y harness covers every DS4 evidence primitive. The visual
suite contains live negatives for candidate clothing and fixture-only exclusion
plus an all-primitives surface. Its generic contract derives 18 executable
screenshot calls and 18 committed PNGs, requires all content hashes distinct,
and rejects a synthetic renamed-byte clone. Every reconciled baseline was
visually inspected and rerun without update.

`RunExplainabilityPanel` is the real existing-panel proof. Its app-owned
`useDepthNCycleBoardProjection` adapter calls the generated client's governed
projection endpoint and validates the exact `depth-n-cycle-board` boundary.
The panel renders typed availability, quantity/validity/time,
`ProjectionFreshness`, terminal/evidence payloads, design references, and
producer-supplied weakest links through rebound primitives. It preserves novel
terminal/evidence/domain labels verbatim, never recomputes the weakest link,
and renders typed artifact absence as visibly `fixture_only` with no authority
slot. The former panel-local verdict classification is replaced by the sole
neutral decision-grade presentation module. Quantity semantics preserve
interval/set, unknown, and incomparable values without scalar collapse. No new
product route was added.

## Pattern closure

- P04/P05/P15: no live local authority retirement debt; candidate and
  fixture-only postures cannot occupy authority slots; C23 fails closed.
- P06/P27/P28: package owners are unique, prior owners deleted, no shims; dormant
  resurrection is consumer-gated.
- P08: valid, transaction, observation, payload as-of, and source freshness
  remain distinct; cache age is not guessed.
- P29/P31/P32/P33: register, inventory, quantity, architecture, status-return,
  snapshot, and owner scanners derive from live syntax/bytes and carry
  behavioral corruption witnesses rather than marker lists.
- P34: the one visual failure was independently reproduced on the committed
  state, its expected image stayed untouched, and it remains an owned red debt
  rather than an exclusion-green claim.

## Cluster commit map

| Cluster | Commit | Scope |
| --- | --- | --- |
| C00 | `61d354f62` | plan, baseline, canonical-waist stop |
| C01 | `018328d68` | foundation primitives |
| C02 | `2dbf604e0` | form primitives |
| C03a | `caa1ee6e3` | living overlays |
| C03b | `a2c9ae8b0` | dormant retirement / ledger retention |
| C04 | `5127af28d` | DTCG projection |
| C05 | `e57b241a0` | status inventory/governance |
| C06 | `290bb5e61` | decision-producer quantities |
| C07 | `07ed51c81` | chart quantities |
| C08 | `0ef16da1b` | nondecision layout values |
| C09 | `9c45a240e` | temporal semantics and cursor |
| C10 | `c4e1b97e3` | authored candidate posture |
| C11 | `8a8c8169e` | trust authority |
| C12 | `a59efb3dc` | operator evidence/a11y |
| C13 | `f444ba719` | counterfactual fail-closed projection |
| C14 | `e5730cf6a` | compound evidence families |
| C15 | `b171c4708` | root compounds |
| C16 | `66dcdc0b6` | shared patterns |
| C17 | `4bf425bfa` | generated responsive adapter |
| C18 | `5f63537c2` | architecture remainder |
| C21 | `299fe06e8` | bounded mechanical status retirement |
| C22a | `0e9aa6eef` | semantic-debt governance |
| C22b | `d2dceae95` | run-lifecycle guessing removal |
| C22c | `31134a9fa` | generated provenance posture |
| C22d | `2a9da098e` | return-vocabulary retirement |
| C22e | `810ef6b77` | non-starving generic scanners |
| C23 | `bc1d01001` | readiness/scientific containment |
| C14e | `31aae0c45` | census execution budget |
| C13e | `bfb30c82b` | counterfactual contrast token repair |
| C06e | `2d83e3264` | provenance dialog accessible name |
| C19a | `0faf33e7b` | authority harness and real panel |
| C19b | `470a802d4` | governed visual reconciliation |
| C20 | containing commit | closure report and final receipts |

The architect authorization itself is `7486eaa08` and is not counted as an
implementation cluster. The table is in logical cluster order. Actual Git order
after C22d is C23, then wave-discovered C22e/C14e/C13e/C06e, then C19a/C19b;
the commit IDs preserve that chronology.

## Fence, lock, and handoff

The cumulative branch diff from `main...HEAD` is confined to
`apps/runtime-dashboard/**`, `packages/atlas-ui/**`, owned
`architecture/atlas_surfaces/**`, DS4 plan/journal/closure docs,
`docs/reference/frontend/**`, and `pnpm-lock.yaml`. There are no backend,
schema, generated-runtime-client, v15 archive, frozen-locale, CI, or other-
worktree writes. Including this C20 document, the final path census is 669:
574 dashboard, 76 atlas-ui, 14 Atlas-register artifacts, 3 DS4 docs, 1 generated
frontend-register report, and 1 lockfile.

The cumulative lock delta is **106 additions / 0 deletions**, entirely inside
workspace importers: the dashboard links the two workspace packages and the new
`packages/atlas-ui` importer records already-resolved dependencies. There is no
package/snapshot resolution or version movement. C19b and C20 do not touch the
lockfile.

No merge and no push are performed. Architect review is the next action.
`git diff --check` is green. A repository-local Prettier executable is not
installed, so the attempted Markdown Prettier check is a tooling non-receipt,
not a product failure or a claimed formatting receipt.
