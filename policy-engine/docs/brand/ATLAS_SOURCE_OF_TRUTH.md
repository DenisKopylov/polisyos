---
title: Atlas Source-Of-Truth And Governing Decisions
status: active
decision_status: accepted_and_ratified
owner: team-design
created: 2026-07-16
last_reviewed: 2026-07-16
authoritative_for:
  - Atlas design-source dispositions
  - Atlas token-pipeline direction
  - Atlas package, versioning, and Figma posture
  - Atlas feature-flag governance direction
  - Atlas non-web surface dispositions
may_not_use_for:
  - v15 token, component, or pattern admission
  - runtime or surface readiness claims
  - loosening the ratified D4 posture (ru stays frozen: not used, not deleted)
master_plan: ../plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
ds0_plan: ../plans/active/atlas-slices/DS0-source-of-truth-freeze-and-governing-decisions.md
ratified_by_owner:
  - D4-locale-and-i18n-posture (2026-07-16, @DenisKopylov — ru frozen: not used, not deleted)
---

# Atlas Source-Of-Truth And Governing Decisions

This is the single DS0 decision record for Atlas. It freezes source ownership
and future direction before DS1 audits the application or DS2 adjudicates the
v15 archive. It does not admit a token, component, pattern, locale claim, or
surface into production.

MACHINE contracts:

- [adoption-ledger schema](../../architecture/atlas_surfaces/adoption-ledger.schema.json)
  and [source-disposition instance](../../architecture/atlas_surfaces/adoption-ledger.example.json);
- [surface-readiness schema](../../architecture/atlas_surfaces/surface-readiness-ledger.schema.json)
  and [19-slice example](../../architecture/atlas_surfaces/surface-readiness-ledger.example.json).

The decisions derive from the
[surface constitution](../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md)
and execute the Phase A closure contract in the
[Revision 2 master plan](../plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md).
If either governing document changes a load-bearing rule, this record must be
reviewed rather than locally patched around it.

## Decision Register

| ID | Decision | Status | Owner | Effective date |
| --- | --- | --- | --- | --- |
| D1 | Canonical source, supersession, and docs lifecycle | `accepted` | `team-design` | 2026-07-16 |
| D2 | Token pipeline | `accepted` | `team-design` | 2026-07-16 |
| D3 | Package home, versioning, and Figma | `accepted` | `team-design` + `team-frontend` | 2026-07-16 |
| D4 | Locale and i18n posture | `ratified` (2026-07-16) | `team-design` product owner; implementation `@frontend-owners` | effective — ru frozen, not used, not deleted |
| D5 | Feature-flag governance | `accepted` | `@architecture-owners`; implementation `@frontend-owners` | 2026-07-16 |
| D6 | Non-web surface dispositions | `accepted` | owners per row | 2026-07-16 |

<a id="atlas-d1"></a>

## D1 - Canonical Source, Supersession, And Docs Lifecycle

### Decision

Atlas has one authority hierarchy, with one owner per purpose:

1. The Universal Policy Design constitution remains the system constitution.
2. The [Atlas surface constitution](../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md)
   owns normative surface law.
3. The [Revision 2 master plan](../plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md)
   owns Atlas execution order, slice boundaries, and GY gates.
4. This record owns DS0 source dispositions; the
   [adoption-ledger schema](../../architecture/atlas_surfaces/adoption-ledger.schema.json)
   and [source-level instance](../../architecture/atlas_surfaces/adoption-ledger.example.json)
   are its MACHINE companion.
5. The living v4 code and CSS remain the **transitional production baseline**
   for what currently ships. They are operational evidence, not a competing
   constitution, and are replaced item by item only after DS2 verdicts and a
   DS4 strangle.

| Source | DS0 disposition | Retention | What DS2 adjudicates / `not_yet` |
| --- | --- | --- | --- |
| Living v4: `apps/runtime-dashboard/src/shared/ui/**`, styles, and `designTokens.ts` | `retained_current_production_baseline`; adoption posture `wrap_then_strangle` | Remains live until admitted replacements have consumers and evidence | Every live counterpart affected by a v15 token/component/pattern verdict; no bulk removal |
| [Atlas design-system v4 doc](./ATLAS_DESIGN_SYSTEM.md) and [v4 adoption record](./ATLAS_V4_ADOPTION.md) | `superseded_as_canonical` | Retained as dated v4 rationale, ADR links, deliberate deltas, and migration evidence | Whether each retained v4 decision survives v15 comparison; ADR-047 stays in force unless superseded through ADR process |
| [v7 product/marketing/client plan](../plans/active/POLICYOS_ATLAS_PRODUCT_MARKETING_CLIENT_SURFACES_MASTER_PLAN.md) | `superseded_as_execution_master` | Retained as material for DS11-DS13 only | Later task plans incorporate or explicitly reject retained trust, publication, and accountability material |
| [v15 archive](../../design/atlas-v15/README.md) | `evidence_source_pending_adjudication`; `implemented_but_not_orchestrated` | Immutable sha256-pinned input | Token sets, 56 components, state matrices, forms, responsive/data-viz grammar, themes/accessibility modes, governance, i18n, Figma, content, security/privacy UX, and product patterns, item by item |

The two vision-superseded frontend plans move to `docs/plans/archive/` under
their original filenames. Narrow active-path disposition stubs preserve links
but carry no execution authority. The historical G-naming Layer-3 plan stays
at its current path as `retained_historical_context`; it has no execution
authority and is superseded in practice by
`docs/plans/active/layer3-slices/GY-engine-subordination.md` Revision 17 for
vocabulary, artifacts, and gates. DS0 does not edit or move either G/GY-owned
path.

### Evidence

- The living `shared/ui` snapshot contains 36 root implementation TSX files,
  89 recursively, 64 accessibility tests, and 26 stories. The v4 system is a
  real production baseline, not an empty predecessor.
- [ATLAS_V4_ADOPTION.md](./ATLAS_V4_ADOPTION.md), dated 2026-04-29, records 13
  deliberate token deltas and the warm-dark posture governed by approved
  ADR-047.
- The v7 plan was created 2026-05-06, last verified 2026-05-20, and spans
  4,518 lines of v7-era public/client/trust/procurement material.
- The v15 zip is 4,855,346 bytes with 1,612 entries and sha256
  `28d3e51dd452a074d30b7a0afa439302c48d4c208307a6a2d09beb935f71a969`.
  Its release metadata says `15.0.0-accessibility-modes`, prepared 2026-06-09,
  and its manifest lists 44 `stable` plus 12 `beta` components. Those are
  archive claims, not PolicyOS production maturity.
- The surface constitution records the missing proof: repo integration,
  browser behavior, manual assistive-technology evidence, public-route
  performance, authority-status compatibility, consumers, and v4/v7
  replacement.

### Strongest Rejected Alternative

Promote v15 wholesale because it is newer, coherent, and carries 56 components
plus a multi-output token pipeline. Rejected: archive completeness does not
prove the PolicyOS capability chain, and bulk promotion would launder
`implemented_but_not_orchestrated` into authority (P05/P10) while creating a
second canonical owner (P06).

Leaving v4/v7 documents active as co-equal roadmaps is also rejected. Their
valuable history is retained, but duplicate execution authority is not.

### Revisit Condition

Review D1 after DS2 has item-level verdicts for every in-scope v15 artifact and
DS4 has wired admitted artifacts through the governed package, real consumers,
browser/accessibility evidence, and a v4 strangle record. Archive the retained
v7 material only after DS11-DS13 task plans have incorporated or explicitly
rejected its usable contents. Any lifecycle move of the historical G plan is a
GY-owner change after protected inbound links are migrated.

## D2 - Token Pipeline

### Decision

DTCG JSON is the sole future **authoring format** for Atlas tokens. The only
permitted generation direction is:

```text
admitted DTCG source -> CSS variables + typed TS facade + Tailwind projection
                     + Figma projection + manifest/audit output
```

This chooses the format and direction, not v15 token values. DS2 still
adjudicates content. DS4 owns implementation under the future Atlas package.
Until that migration closes, live v4 CSS plus the current TS registry remain
the production baseline.

The losing authority is **hand-maintained `designTokens.ts`**, not necessarily
the TS file. DS4 either turns it into a generated compatibility facade or
deletes it after all consumers move. Direct hand edits are barred only when
all of these sunset conditions are proven:

1. DS2 has admitted the values and modes being generated.
2. Generation reproduces ADR-047 warm dark, density, responsive, data-viz,
   contrast, high-contrast, and reduced-motion semantics without loss.
3. Live imports are rebound and generated CSS/TS/Tailwind/Figma artifacts pass
   parity and drift checks.
4. A migration note names any deliberate v4 delta and the compatibility path.

### Evidence

- `apps/runtime-dashboard/src/shared/ui/tokens/designTokens.ts` is 384 lines
  with 74 unique CSS-variable registry entries, while actual values are split
  across `styles.css` (1,685 lines), `theme-light.css` (122), and
  `theme-dark.css` (129). Only one non-test/story direct importer was found.
- The live `design:atlas-v4` check compares the frozen v4 CSS reference with
  live CSS and allowlists the 13 recorded deltas; it proves a real migration
  obligation.
- v15 carries six DTCG-style source families and 16 mode files. Its generated
  manifest reports 711 root tokens/643 root CSS variables, 514 mode
  tokens/505 mode variables, and 258 aliases from 22 source files.
- v15's own token README/delta material still says “Atlas v9” and reports
  188 root/102 mode variables, conflicting with its generated manifest. That
  discrepancy is a DS2 conformance target, not a reason to reject DTCG as a
  format.

### Strongest Rejected Alternative

Keep the live TS registry and CSS files permanently canonical because they are
already shipped and tested. Rejected as the target state: names and values are
split, the path cannot produce Figma/Tailwind/manifests from one contract, and
T6/P06 remains open.

Adopting the v15 generator and values as-is is also rejected. The pipeline is a
candidate implementation; its content and internally inconsistent reports
remain unadmitted until DS2.

### Revisit Condition

Revisit only if DS2/DS4 proves that a secure, reproducible DTCG pipeline cannot
represent the admitted live semantics or cannot satisfy repo toolchain and
drift gates. In that case, retain the live path explicitly as the sole owner;
do not operate dual token authorities.

## D3 - Package Home, Versioning, And Figma

### Decision

Reserve `packages/atlas-ui` with package name `@polisyos/atlas-ui`. It is a
private/internal pnpm workspace package and is not published to a registry.
DS4 creates it by extending and migrating admitted live primitives; it does not
copy the v15 package wholesale.

Start at repository version `0.1.0`; preserve v15 lineage in the adoption
ledger and changelog rather than importing archive version
`15.0.0-accessibility-modes`. Follow the repo
[release policy](../how-to/release-policy.md): before 1.0, breaking supported
surface changes and backward-compatible additions bump MINOR; fixes,
refactors, docs, and internal-only changes bump PATCH. A DS slice cuts a
package version only when it changes the package, with compatibility and
migration notes. `1.0.0` requires a migrated runtime-dashboard consumer, DS6
evidence for every claimed `stable` surface, and no unresolved v4 default path
for the released API.

Figma is a **projection, never a source**. Admitted DTCG generates the token
handoff; governed code manifests/state matrices anchor component mappings.
Figma edits are candidates until the matching code/token decision lands.

Ownership:

- `team-design`: token/component semantics, maturity, and Figma parity;
- `team-frontend`: package integration, build, consumer migration, and
  workspace/lockfile queue;
- per-release parity acceptance: source commit/manifest pinned, every stable
  component mapped or carrying an intentional-gap record, variants/states/
  modes equal to code, owner and review date recorded.

### Evidence

- The [frontend workspace contract](../reference/frontend/workspace-contract.md)
  places shared libraries under `packages/**`; the pnpm workspace already
  discovers that glob. Existing repo packages use `@polisyos/*`, are private,
  and begin at `0.1.0`.
- The v15 package proposes `@policyos/atlas-ui` and an archive-lineage version,
  neither of which matches repository naming or maturity.
- v15 has seven Figma artifacts and a generated token handoff. Its component
  map has 56 entries: all 56 are `needs-figma-audit`, zero are aligned.

### Strongest Rejected Alternative

Import `@policyos/atlas-ui@15.0.0-*` or make Figma co-authoritative because the
archive appears release-ready. Rejected: namespace/version/maturity conflict
with the repo, every Figma component mapping is unaudited, and co-authority
violates Rule 10/P06.

Keeping all primitives app-local indefinitely is also rejected once a governed
package consumer exists; it would prevent a single reusable contract and make
future consumer parity harder.

### Revisit Condition

Consider publication only after at least two independently deployed consumers
or an external SDK need exists and license, support/SLA, provenance,
supply-chain, and release ownership are approved. Reconsider Figma authority
only if a machine-verifiable bidirectional process has one explicit
conflict-resolution owner; otherwise it remains a projection.

## D4 - Locale And i18n Posture

**Status: `ratified` (2026-07-16, product owner `@DenisKopylov`).** The owner
ratified the recommendation as proposed: `uk` primary Ukraine-facing locale;
`en` baseline/fallback; **`ru` UI catalog `legacy_continuity_frozen` — not
used, not deleted** (retained in-tree, excluded from active locale exposure
and from any public locale-support claim); Russian **source-content
rendering** (reading Russian-language source documents) remains a separate
read-only capability; RTL honestly `not_supported`. DS5 implements the
enforcement mechanics; DS12 may publish exactly this posture and nothing
stronger. Revisit triggers unchanged (usage evidence, funded translation
ownership, runtime admission, jurisdictional change).

The 2026-06-11 DS0 draft described `ru` as frozen-but-served, but that text
predated the current constitution's jurisdictional-surface posture and was not
ratified under this decision contract. It carries no sign-off forward.

### Evidence Snapshot (2026-07-16)

Recursive string-leaf inspection of
`apps/runtime-dashboard/src/shared/i18n/locales/{en,uk,ru}.json` found:

| Catalog | String leaves | File size | Identical to `en` | Strings containing Cyrillic |
| --- | ---: | ---: | ---: | ---: |
| `en` | 2,449 | 125,537 B | n/a | 4 |
| `uk` | 2,449 | 157,409 B | 888 (36.26%) | 1,540 |
| `ru` | 2,449 | 135,673 B | 1,963 (80.16%) | 478 |

All leaves are non-empty. `shared/i18n/parity.test.ts` proves identical paths,
not semantic translation completeness. The UI declares and exposes all three
locales; missing messages fall back to English. The runtime capability
contract and frontend capability validator admit only `en`/`uk`, while a
selected `ru` UI locale currently crosses into run requests as
`locale_preference`. The surface constitution starts Ukraine-facing public
coverage with `uk`/`en`. [TYPOGRAPHY_UA_RU.md](./TYPOGRAPHY_UA_RU.md) says
Ukrainian is primary, Russian is a read-only source-content target with no
default Russian writing UI, and English is fallback.

No UI direction contract, `document.dir` management, or RTL visual/a11y test
was found. The honest RTL status is `not_supported`, not ready.

### Recommendation For Owner Ratification

- Supported public/product UI locales: Ukrainian primary for Ukraine-facing
  contexts; English baseline and fallback.
- Classify the existing Russian UI catalog as `legacy_continuity_frozen`, not
  a supported/public translation promise. Preserve it for existing
  authenticated users during a measured transition, remove it from public
  promotion, and accrue no new translation obligation unless the owner funds
  and admits one.
- Permanently retain Russian **source-content rendering and typography** as a
  separate read-only capability. DS5 should decouple selectable UI locale from
  source language rendering.
- DS12 must not publish a claim of Russian UI support without a later explicit
  ratification and evidence update.
- RTL remains `not_supported` until a named RTL locale/jurisdiction is
  admitted. That trigger requires `document.dir`, `dir=auto` for source text,
  bidirectional icon/chart review, and visual/accessibility evidence.

Ratification owner: `team-design` product owner, with `@DenisKopylov` as the
current enforceable owner. Implementation owner after ratification:
`@frontend-owners` (DS5), with DS12 owning public-locale claims.

### Alternatives And Strongest Rejection

| Alternative | Benefit | Cost / reason not selected |
| --- | --- | --- |
| Retain `en`/`uk`/`ru` as fully supported product locales | Maximum continuity; selectors and parity tests already exist | **Strongest rejected alternative for now:** structural parity overstates quality; 80.16% of `ru` equals English, runtime advertises only `en`/`uk`, and this creates an unfunded translation and public-position obligation |
| `legacy_continuity_frozen` Russian UI plus permanent Russian source rendering | Least abrupt; separates user continuity from source-language capability | **Recommended**, subject to owner choice; needs DS5 decoupling and a privacy-safe transition measure |
| Immediate remove/depublish | Clearest public posture and lowest ongoing UI obligation | Risks user discontinuity and accidental loss of source-text rendering while the two concerns remain coupled |
| Retain and invest in full Russian UI | Can become an honest supported locale | Requires funded translation ownership, semantic coverage gates, runtime admission, and an articulated jurisdictional rationale |

### Revisit Condition

Ratification occurred 2026-07-16 (see Status above). Remaining revisit
triggers: privacy-safe evidence of active Russian UI users; funded translation
ownership and semantic-quality gate; runtime admission of `ru`; a
legal/accessibility/jurisdictional requirement; or a material change in the
Ukraine-facing public posture.

## D5 - Feature-Flag Governance

### Decision

Reserve `architecture/atlas_surfaces/feature_flag_registry.json` for DS5 as
the one canonical flag vocabulary. DS0 does not create it. Each DS5 record
must carry key, owner, intent, audiences/profiles, defaults, telemetry,
introduction date, registry/rule version, and sunset or review condition.

Remote manifests, environment injection, window injection, cache, and test
props may become evaluated projections of that registry; none may introduce a
key. Production rejects unknown keys and ungoverned `all_on` profiles.
`/auth/me` carries authorization separately. If it later returns user-specific
flag evaluations, they use the same registry keys and version/provenance.
The separate `enableReviewCollaboration` vocabulary is sunset in DS5;
collaboration exposure composes the canonical rollout flag **and**
`runs.review` permission, with neither substituting for the other.

Flags control visibility/exposure and rollback only. They cannot upgrade
authority, maturity, admissibility, readiness, or authorization. New DS4/DS5
shadow surfaces default off for public/production profiles until the readiness
ledger admits exposure. The four declared keys with no consumer are
`consumer_missing` and cannot count as shadow-shipping controls until DS5
wires or retires them.

### Twelve-Flag Registry Decision

All 12 declared flags currently default `true`; DS0 records the fact but does
not ratify those defaults as future policy.

| Key | Owner | Intent | Current role / shadow-shipping role | Sunset or review condition |
| --- | --- | --- | --- | --- |
| `enableAtlasV2` | `@frontend-owners` + `team-design` | `launch-gate` | Gates Atlas chrome/branding; DS4 strangle rollback | Sunset after ledger-proven Atlas coverage and legacy chrome removal |
| `enableCausalGraph` | `@frontend-owners` | `launch-gate` | `consumer_missing`; graph currently renders unconditionally | DS5 wires a whole-surface gate or retires the key |
| `enableClerkMode` | `@frontend-owners` | `mode` | Forces analyst fallback when off; DS14 legacy-agent strangle control | Sunset when DS14 removes the ungrounded Clerk default/fallback path |
| `enableCollaboration` | `@frontend-owners` + `@runtime-owners` | `launch-gate` | `consumer_missing`; permission-derived collaboration uses another key | DS5 composes it with `runs.review` or retires it and sunsets `enableReviewCollaboration` |
| `enableCommandPalette` | `@frontend-owners` | `launch-gate` | `consumer_missing`; palette currently renders unconditionally | DS5 wires the gate or retires the key |
| `enableDarkMode` | `@frontend-owners` + `team-design` | `mode` | Forces light when off; theming rollback | Reclassify as governed preference or sunset after DS2/DS6 theme parity and accessibility acceptance |
| `enableLexKnowledge` | `@frontend-owners` | `launch-gate` | Gates Knowledge workspace; DS10 rollout | Sunset when DS10 capability discovery is mandatory and rollback-free |
| `enableNarrativeView` | `@frontend-owners` | `launch-gate` | Gates decision-packet reading view; DS8/DS12 projection rollout | Sunset after projection parity and semantic tests pass |
| `enablePlatformHealth` | `@frontend-owners` | `launch-gate` | Gates Platform workspace | Review after the workspace is stable and its rollback window closes |
| `enableRunsWorkspace` | `@frontend-owners` | `launch-gate` | Gates Runs workspace; DS8 strangle rollback | Sunset after governed run surfaces are mandatory and stable |
| `enableScenarioComposer` | `@frontend-owners` | `launch-gate` | Gates Composer workspace; DS4/DS5 candidate-clothing rollout | Sunset after the admitted path is the proved default |
| `enableWhatIfAnalysis` | `@frontend-owners` | `launch-gate` | `consumer_missing`; workbench currently renders unconditionally | DS5 wires the gate or retires the key |

Registry contract owner is `@architecture-owners`; promotion/sunset approval
owner is `@platform-owners`.

### Evidence

- `shared/lib/featureFlags.ts` declares exactly 12 keys and resolves values
  across per-flag environment defaults, inline manifest, window injection,
  optional remote/cache, and provider props. `VITE_FEATURE_FLAGS_URL` may be
  empty; no fixed checked-in production manifest exists.
- The manifest envelope is loose and values are coercively normalized.
- Eight keys have consumers. `enableCausalGraph`, `enableCollaboration`,
  `enableCommandPalette`, and `enableWhatIfAnalysis` do not.
- `/auth/me.feature_overrides` is an unbounded string/boolean map, separate
  from `FeatureFlagProvider`, and today emits only
  `enableReviewCollaboration` from `runs.review` permission.

### Strongest Rejected Alternative

Retain `featureFlags.ts`, its multiple browser inputs, and `/auth/me` as
co-equal authorities because their precedence already works. Rejected: source
precedence is dispersed, authorization is conflated with rollout, unknown
vocabulary is admitted, and four declared flags do not gate their named
features. This is P06 plus a shadow-shipping overclaim.

### Revisit Condition

A future multi-tenant/server-side evaluation service may become the evaluator,
but it must consume the same registry vocabulary and emit versioned
provenance. Retire registry machinery only after every flag is permanently
admitted or retired and no shadow rollout remains.

<a id="atlas-d6"></a>

## D6 - Non-Web Surface Dispositions

### Decision

| Artifact | Disposition and owner | Strongest rejected alternative | Revisit condition |
| --- | --- | --- | --- |
| `packages/cli/src/styleguide/**` + [CLI_STYLEGUIDE.md](./CLI_STYLEGUIDE.md) | Admit to **DS4**, owner `team-frontend`: rebind ASCII/scriptable terminal presentation to generated runtime authority types | `surface_out_of_scope`; rejected because the package already emits authority-suggestive tokens from a divergent local lattice | Reconsider only if CLI output is formally limited to non-authority diagnostics or the package is retired |
| [EMAIL_TEMPLATES.md](./EMAIL_TEMPLATES.md) | **`surface_out_of_scope`** for this 19-slice DAG; retention owner `team-design` | Force into DS12; rejected because no slice owns mail delivery, privacy/redaction, provider behavior, or notification retention (P01/P13) | A successor slice accepts a typed notification producer, redaction/privacy rules, locale coverage, delivery owner, and negative disclosure tests |
| [PRINT_AND_EXPORT.md](./PRINT_AND_EXPORT.md) | Admit to **DS3** shared export machinery; `team-design`, runtime co-owner `team-architecture`; DS8/DS12 consume | DS12-only ownership; rejected because identity, replay pinning, and export conventions must exist before public publication | DS3 task planning explicitly excludes human-readable formats or a separately governed export waist is approved |
| [BUREAUCRATIC_RENDERING.md](./BUREAUCRATIC_RENDERING.md) | Admit to **DS8** existing `artifacts` strangle, owner `@runtime-owners`, with DS3 dependency; DS12 may later admit a public projection | Defer all governance to DS12; rejected because an authenticated renderer already exists outside the future waist | Public projection only after Ukrainian specialist review and DS12 format selection; until then draft-only |
| [GLYPH_SPECIFICATION.md](./GLYPH_SPECIFICATION.md) | Admit to **DS2**, owner `team-design`, under approved ADR-045; DS4 consumes admitted intent mapping | Make DS4 the source; rejected because DS4 binds semantics but does not adjudicate design substrate | ADR-045 is superseded or DS2 finds a v15/live-v4 incompatibility requiring a new ADR |
| [MOTION.md](./MOTION.md) | Admit to **DS2**, owner `team-design`; DS6 later verifies reduced-motion evidence | Treat current prose as already canonical in DS4; rejected because it has legacy/current token-source drift and says four durations while listing five | DS2 adjudication or later browser/AT evidence changes the admitted motion contract |
| [A11Y_CONTRAST.md](./A11Y_CONTRAST.md) | Admit ongoing ownership to **DS6**, owner `team-design`, generator operator `team-frontend`; DS2 consumes the current generated matrix | Give ongoing ownership to DS2; rejected because DS2 is one-time admission while contrast evidence is continuous | A separately governed repo-wide accessibility-evidence program accepts ownership |

The CLI mapping deliberately closes rather than ignores an existing P06 risk:
code defines local trust values and `success`/`warning` severity while the doc
specifies `warn`. Email remains out of scope because a prose template without a
producer/privacy/delivery chain is not a capability. All four Ukrainian
bureaucratic templates remain `pending_external_review`.

### Strongest Rejected Alternative

Force every available brand artifact into the Atlas roadmap so nothing appears
left behind. Rejected: it would manufacture contract-only capabilities and
ceremony (P01/P13). The inverse—declare all non-web work out of scope—is also
rejected because CLI, export, bureaucratic, glyph, motion, and contrast assets
already have real consumers or load-bearing evidence roles.

### Revisit Condition

Revisit each row only on its recorded trigger. A new artifact does not enter a
slice merely because it exists; it needs a producer/consumer/evidence role or
an explicit `surface_out_of_scope` record.

## Pending Owner Ratification

| Decision | Recommendation | Ratification owner | Blocking effect |
| --- | --- | --- | --- |
| D4 `ru` UI retention | `uk` primary + `en` baseline; `ru` UI `legacy_continuity_frozen`; Russian source-content rendering retained | `team-design` product owner (`@DenisKopylov`) | DS5 may prepare mechanics but must not choose the policy; DS12 cannot publish locale support claims |

No other DS0 decision is pending owner ratification.

## Pattern Pass And Capability Truth

- **P04/P06:** vocabularies have one named future owner; legacy sources are
  retained only with a strangle or material-use condition.
- **P05/P10:** v15 archive maturity and parity reports never become PolicyOS
  runtime/accessibility authority by themselves.
- **P13:** one decision record replaces separate memos; email stays honestly
  out of scope rather than creating a producer-less slice obligation.
- **P26:** D4 stays pending; evidence and recommendation do not become human
  sign-off.
- **P29:** schema examples prove shape only. DS6 owns behavioral readiness
  recomputation and CI validation.

At DS0 close, the two ledger schemas are intentionally `contract_only`.
Producer, bridge, consumer, verification, and surface work belongs to the
named later slices; DS0 does not round that state up to `implemented`.
