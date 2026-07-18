---
plan_id: atlas-ds4-status-grammar-rebinding
title: "DS4 - Status-Grammar Rebinding And Test Harness"
type: slice-plan
status: blocked_before_implementation - architect decision required
created: 2026-07-18
revised: 2026-07-18
last_verified: 2026-07-18
stability: executable_after_c00
slice: DS4
baseline_commit: 71f438ad52f668e1feb7510652ff5fd3b735bd62
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
ds0_record: ../../../brand/ATLAS_SOURCE_OF_TRUTH.md
ds1_report: ../../../reference/frontend/atlas-live-application-audit.md
ds2_ledger: ../../../../architecture/atlas_surfaces/atlas-v15-adoption-ledger.json
ds3_plan: ./DS3-runtime-producers.md
ds19_register: ../../../../architecture/atlas_surfaces/frontend-disposition-register.json
baseline_debt_manifest: ../../../../architecture/atlas_surfaces/frontend-baseline-debt-manifest.json
journal: ./DS4-status-grammar-rebinding-journal.md
audiences: [REVIEWER, EXPERT, MACHINE]
owner: team-frontend
architecture_owner: team-architecture
depends_on:
  - ./DS0-source-of-truth-freeze-and-governing-decisions.md
  - ./DS1-live-application-audit.md
  - ./DS2-atlas-v15-adjudication.md
  - ./DS3-runtime-producers.md
  - ./DS19-false-substrate-strangle-wave-and-frontend-disposition-register.md
  - ../../../reference/policy-design-case-failure-patterns.md
---

# DS4 - Status-Grammar Rebinding And Test Harness

> **For agentic workers:** REQUIRED SUB-SKILLS: use
> `superpowers:test-driven-development` for every behavior change,
> `superpowers:subagent-driven-development` for independent family clusters,
> and `superpowers:verification-before-completion` before every cluster commit.
> Do not start production cluster DS4-C01 until DS4-C00 is resolved in the
> canonical owner. Do not merge or push; close with an architect-review handoff.

**Goal:** Make the runtime's authority vocabulary the only semantic source on
the glass by rebinding the living dashboard families, retiring UI-local
authority definitions, and proving the result through semantic, accessibility,
and visual negatives. This is a strangle-and-rebind slice, not a parallel
component-library build.

**Architecture:** The canonical flow is `runtime owner -> typed HTTP DTO ->`
`@polisyos/runtime-api-client -> one rebound primitive -> living consumer`.
Open authority values remain opaque unless the owner exports a closed type and
composition law. Interaction state is a separate lattice and can never promote
runtime authority. Evidence-bearing `shared/ui` families remain the
transitional winners and rebind in place. Under ratified D3, admitted low-risk
generic primitives may migrate—not copy—into the package one owner and one live
consumer at a time; genuinely new define-once primitives and the DTCG
projection adapter start directly in `@polisyos/atlas-ui`.

**Tech stack:** React 19, TypeScript 5, Pydantic-generated OpenAPI types,
pnpm 10.33.2, Vite, Vitest, Testing Library, Storybook, axe, Playwright,
ESLint, JSON Schema, DTCG JSON, and repository architecture guardrails.

## Binding fence and no-merge posture

- Worktree: `.worktrees/atlas-ds4`; branch:
  `codex/atlas-ds4-status-grammar`; base:
  `71f438ad52f668e1feb7510652ff5fd3b735bd62`.
- Writable: `apps/runtime-dashboard/**`, new `packages/atlas-ui/**`,
  `architecture/atlas_surfaces/**`, `docs/plans/active/atlas-slices/DS4-*`,
  `docs/reference/frontend/**`, and this single DS4 journal.
- Read-only: `packages/runtime-api-client/**`, `design/atlas-v15/**`, and all
  `src/**` backend paths.
- `pnpm-lock.yaml` may change only for the new workspace package. A lockfile
  semantic diff proving zero unrelated version movement is mandatory in C01.
- No backend suite is run because no backend path is writable. Any required
  canonical DTO or OpenAPI change returns to a DS3-class owner.
- Each cluster is one scoped commit after red-first proof and all cluster gates.
  No partial family, unpaired register transition, or uncommitted tail crosses a
  cluster boundary.

## DS4-C00: canonical-contract precondition and stop gate

The Revision-3 plan says DS4 binds terminal kinds, evidence classes, CGF
dispositions, decision grades, and time semantics from the generated client.
The checked-in generated client transports terminal/evidence labels
intentionally as open values, while the composition-bearing CGF, decision-grade,
and cache-age semantics required by DS4 are absent:

| Required vocabulary | Checked-in generated-client fact                                                                                                                                                                                               | Capability state                                                                                                                               |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| terminal kinds      | `terminal_distribution` is `Record<string, ProjectionJsonValue>` (`packages/runtime-api-client/types.ts:4894`); DS3 requires unseen labels to pass through (`tests/unit/runtime/http/test_governed_projection_service.py:649`) | opaque transport is `implemented_but_not_orchestrated`; any known-core composition artifact is `artifact_missing` until the owner declares one |
| evidence classes    | depth-N `evidence_class` is `string` (`packages/runtime-api-client/types.ts:4886`); DS3 tests unseen-value passthrough (`tests/unit/runtime/http/test_governed_projection_service.py:614`)                                     | opaque transport is `implemented_but_not_orchestrated`; semantic styling remains `artifact_missing` rather than inferred                       |
| CGF dispositions    | `GenerationCycleDispositionPayload` is generic projection JSON (`packages/runtime-api-client/types.ts:5850`); CG1/CG2/CG3 owner vocabularies are distinct                                                                      | normalized grammar is `artifact_missing`; typed owner-to-OpenAPI fields are `bridge_missing` and `surface_missing`                             |
| decision grades     | no exported `DecisionGrade`; the owner values live at `src/polisyos/pdc/_impl/layer2_readiness.py:39` and are not represented by a generated closed type                                                                       | owner-to-OpenAPI `bridge_missing`; generated `surface_missing`                                                                                 |
| as-of/freshness     | `ProjectionFreshness` is typed (`packages/runtime-api-client/types.ts:8164`) and distinguishes `observed`, `artifact_missing`, and `invalid_source`; it does not encode roadmap `live/cached/stale/offline_queued`             | source observation is usable; cache-age grammar is `artifact_missing`, `bridge_missing`, and `surface_missing`                                 |

Creating UI enums for these gaps would recreate P04/P05/P06/P27 and violate
DS3's recompute-not-pin law. Open terminal/evidence labels may be displayed
verbatim in a neutral unknown posture, but never ordered, colored, composed, or
promoted. Styling unknown strings as if ordered would launder authority under
P10/P15. Therefore C00 is a hard precondition for the universal authority
grammar, not a local TODO.

Before C01, the architect must choose and record one of these resolutions:

1. **Canonical repair (preferred):** route a DS3-class change through the
   runtime owner, strict DTO, OpenAPI, generated package, and novel-value tests.
   Where the owner has a composable known core, expose a closed known-core type
   plus a quarantined opaque extension; where it intentionally has no ordering,
   declare neutral-only opaque semantics. Never close the extension channel or
   contradict DS3 passthrough tests. Then rebase DS4 and rerun every baseline
   receipt.
2. **Explicit partial re-cut:** authorize only authority-neutral work (token
   adapter, dependency severing, quantity/temporal fields already typed,
   fixture-only treatment, and harness infrastructure), with continuous new
   slice numbering for the deferred authority grammar. DS4 must not be called
   complete under this option.

There is also a test-debt instruction conflict to resolve at C00. The master
debt table assigns the a11y census to DS6 and predicts DS4's temporal repair
changes five failures to four, while the DS4 brief explicitly requires DS4 to
repair the `OperatorDiagnosticPanel` structural a11y gate. Closing both DS4
requirements yields five to three, not five to four. The architect must choose
the owner and expected denominator; the branch will not silently relabel it.

**C00 acceptance signal:** an architect-approved decision record plus either
owner-declared known-core/opaque-extension contracts with composition and novel
value tests, or an explicit partial re-cut. Until then the truthful slice state is
`blocked_before_implementation`, and only this plan/journal cluster may land.

## Measured baseline receipt

All receipts were recorded before any repository edit.

| Gate                 | Command                                                                                                                                 | Receipt at `71f438ad5`                                                                                                                                  |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| install              | `corepack pnpm install --frozen-lockfile --ignore-scripts`                                                                              | PASS; pnpm 10.33.2; frozen lockfile unchanged                                                                                                           |
| typecheck            | `cd apps/runtime-dashboard && corepack pnpm run typecheck`                                                                              | PASS                                                                                                                                                    |
| production build     | `cd apps/runtime-dashboard && corepack pnpm run build`                                                                                  | PASS; 3,871 modules; PWA 101 entries                                                                                                                    |
| full lint            | `cd apps/runtime-dashboard && corepack pnpm run lint`                                                                                   | OBSERVED exit 1: 75 errors, 0 warnings, 22 files; every diagnostic is `policyos/quantity-must-be-wrapped`; exact identities match the checked manifest  |
| full Vitest          | `cd apps/runtime-dashboard && corepack pnpm run test:components`                                                                        | OBSERVED exit 1: 229 files / 674 tests; 226 files / 669 tests pass; 3 files / 5 tests fail; 77.73 s; JSON failure identities match the checked manifest |
| architecture         | `cd apps/runtime-dashboard && corepack pnpm run check:architecture`                                                                     | OBSERVED exit 1: 36 exact violations                                                                                                                    |
| disposition register | `python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --verify-baseline-source-bytes --corruption-probes` | PASS; 261 roots, 200 `rebind_pending`, 23 negatives, 7 censuses                                                                                         |

Exact Vitest failures are three locale-parity assertions for
`panels.agentPipeline.overBudget`, the `OperatorDiagnosticPanel.tsx` structural
a11y census, and `TemporalCursorProvider > commits canonical URL params`. The
temporal failure receives a current timestamp instead of the test's April 2026
cursor, demonstrating a time-dependent root rather than a byte drift.

The worktree has no executable `.venv/bin/python`; Python-only tooling that
requires the worktree venv is a non-receipt until bootstrap creates it. The
standalone register checker runs with `python3` and is a real receipt.

## Pattern pass and capability truth

Relevant repair-register rows are P04 (status lattice), P05 (authority leak),
P06 (duplicate/shim drift), P08 (time-role conflation), P10 (semantic
adequacy), P13 (governance gravity), P15 (speculation laundering), P27/P28
(owner bypass and un-strangled legacy), P29 (marker-only proof), and P31-P34
(instance patching, trust by form, teaching to a probe, dishonest exclusion).

The target correct pattern is:

```text
closed owner contract + producer + persisted packet + generated bridge
  -> one rebound primitive -> real consumer -> negative/e2e semantic proof
  -> audit/API/dashboard surface
```

At C00 the universal composition grammar is `artifact_missing`, with
`bridge_missing`/`surface_missing` for CGF, decision grades, and cache-age
freshness; opaque terminal/evidence transport is
`implemented_but_not_orchestrated`. A local UI grammar would be `contract_only`.
The token adapter is `producer_missing`,
the status-retirement guard is `verification_missing`, and several rich shared
families are `implemented_but_not_orchestrated` because they import app state.
No cluster may upgrade these labels without producer, bridge, consumer, and
semantic-test evidence in the same or an explicitly linked commit.

## Universal cluster protocol

Every implementation cluster follows this order:

1. Record clean status, HEAD, current family rows, and exact baseline deltas.
2. Add the named negative first; run it and save the expected failure reason.
3. Make the smallest rebind/sever/build change. Do not copy a living family.
4. Move each touched DS19 row from `rebind_pending` to `rebound` with successor
   and consumer evidence, or to `use_as_is` with a bounded rationale.
5. Run affected unit, semantic, a11y, and story tests; they must be green.
6. Run package/app typecheck, production build, scoped lint, and the disposition
   register checker. New lint/test/architecture identities are forbidden.
7. At wave boundaries run full lint, full Vitest, architecture, Storybook/a11y,
   visual regressions, package gates, lockfile proof, and fence proof.
8. Update the journal with exact denominators and commit one clean cluster.

If the measured blast radius exceeds the cluster or a new canonical-owner gap
appears, stop at the clean boundary and propose a continuously numbered re-cut.
Never absorb the tail by enlarging a cluster or weakening a gate.

### Register transition map

The register is the disposition authority. These are the exact family rows and
their planned transition boundary; the cited files are the successor/consumer
evidence that must exist before the row moves.

| DS19 row                            | Boundary       | Successor evidence                                                                                                                   | Consumer evidence                                                                                                       |
| ----------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| `ui-primitives-root`                | C03            | `packages/atlas-ui/src/index.ts` plus removed old implementations                                                                    | direct dashboard imports and `primitiveMigration.test.tsx`                                                              |
| `ui-tokens`                         | C17 or pending | package generated token manifest from C04; by C17 `designTokens.ts` is a generated compatibility projection, not an authoring source | final family consumer plus parity/drift tests; if the old TS registry stays authorial, the row remains `rebind_pending` |
| `ui-quantity`                       | C06            | rebound dashboard quantity barrel importing generated runtime types                                                                  | `quantityDecisionProducers.test.tsx` and first real producer                                                            |
| `ui-temporal`                       | C09            | rebound temporal barrel                                                                                                              | cursor and time-role semantic tests                                                                                     |
| `ui-authored-text`                  | C10            | rebound authored-text barrel                                                                                                         | candidate-clothing test and migrated live consumer                                                                      |
| `ui-trust-view`                     | C11            | rebound trust-view barrel                                                                                                            | generated `VerificationMetadata` consumer and fail-closed test                                                          |
| `ui-operator-diagnostics`           | C12            | rebound `OperatorDiagnosticPanel`                                                                                                    | run/clerk consumer plus semantic/a11y test                                                                              |
| `ui-counterfactual`                 | C13            | rebound counterfactual barrel                                                                                                        | scenario consumer and PI-06 negatives                                                                                   |
| `derivation-projection-fail-closed` | C13            | generated-client-only projection adapter                                                                                             | `projectionFailClosed.test.ts`                                                                                          |
| `ui-compounds`                      | C14            | rebound nested compounds barrel                                                                                                      | `RunExplainabilityPanel` consumer and mixed-outcome tests                                                               |
| `ui-compounds-root`                 | C15            | one-owner package exports plus rebound `LineageGraph`                                                                                | direct live imports and package one-owner test                                                                          |
| `ui-patterns`                       | C16            | one-owner package exports                                                                                                            | direct live imports and package one-owner test                                                                          |
| `ui-responsive`                     | C17            | unchanged dashboard barrel                                                                                                           | `use_as_is` rationale plus responsive token parity test                                                                 |

C05 writes `target_cluster` for every one of the 47 DS1 `status-*` rows into
the typed retirement inventory. The inventory checker requires an exact
one-to-one join to the register, permits the one already deleted collaboration
row only as `removed`, and rejects an unassigned or multiply assigned row.
C06-C18 transition only the status rows assigned to that cluster and attach the
exact replacement/consumer refs. Thus no prose list can drift from the machine
queue.

### Wave boundaries

| Wave                  | Clusters | Full-boundary receipt                                                                                                                        |
| --------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| W1 foundation         | C01-C05  | full baseline-relative lint/Vitest/architecture, package gates, register and status corruption probes, build/typecheck, fence/lockfile proof |
| W2 quantity/time      | C06-C09  | same full gates; lint and temporal manifests must shrink                                                                                     |
| W3 authority families | C10-C13  | same full gates plus candidate/fixture semantic and visual negatives                                                                         |
| W4 compounds/severing | C14-C18  | same full gates; architecture manifest must reach target or itemize remainder                                                                |
| W5 harness            | C19      | same full gates plus Storybook/a11y and Playwright visual suite                                                                              |
| closure               | C20      | rerun every W5 gate from a clean tree and produce the architect handoff                                                                      |

## One-owner family and component disposition matrix

`DS2 ID = none` means no v15 material is adopted for that component; it is not
permission to inspect or copy the archive. The listed home is exclusive.
`rebind` means edit the living implementation in place. `package` means the
define-once implementation belongs only to `@polisyos/atlas-ui`. `use_as_is`
means no DS4 semantic claim.

The matrix accounts for all **89** measured implementations: **35** migrate to
the one package home, **42** rebind in the dashboard, and **12** remain
`use_as_is`. The twelve measured families map to clusters as follows:

| Measured family      | Count | Cluster | Calls                                                |
| -------------------- | ----: | ------- | ---------------------------------------------------- |
| `ui-primitives-root` |    29 | C01-C03 | 27 package, 2 rebind                                 |
| token modules        |     3 | C04     | 3 adapter rebinds; outside the 89 TSX denominator    |
| quantity             |     5 | C06-C08 | 5 rebind plus three shrinking debt-manifest clusters |
| temporal             |     5 | C09     | 5 rebind                                             |
| authored-text        |     3 | C10     | 3 rebind                                             |
| trust-view           |     8 | C11     | 8 rebind                                             |
| operator diagnostics |     1 | C12     | 1 rebind                                             |
| counterfactual       |    10 | C13     | 6 rebind, 4 `use_as_is`                              |
| nested compounds     |    15 | C14     | 11 rebind, 4 `use_as_is`                             |
| `ui-compounds-root`  |     6 | C15     | 5 package, 1 rebind                                  |
| patterns             |     3 | C16     | 3 package                                            |
| responsive           |     4 | C17     | 4 `use_as_is`                                        |

### DS4-C01-C03 — package skeleton and primitive-root parity

| Component          | Call and one home                               | DS2 adoption-ledger ID                           |
| ------------------ | ----------------------------------------------- | ------------------------------------------------ |
| `ApiErrorAlert`    | rebind — `apps/runtime-dashboard/src/shared/ui` | none                                             |
| `ProvenanceStrip`  | rebind — `apps/runtime-dashboard/src/shared/ui` | none                                             |
| `AsyncSection`     | package — `@polisyos/atlas-ui`                  | none                                             |
| `Badge`            | package — `@polisyos/atlas-ui`                  | `component-badge` (`wrap_then_strangle`)         |
| `Button`           | package — `@polisyos/atlas-ui`                  | `component-button` (`wrap_then_strangle`)        |
| `Card`             | package — `@polisyos/atlas-ui`                  | `component-card` (`wrap_then_strangle`)          |
| `Checkbox`         | package — `@polisyos/atlas-ui`                  | `component-checkbox` (`wrap_then_strangle`)      |
| `Command`          | package — `@polisyos/atlas-ui`                  | none                                             |
| `Dialog`           | package — `@polisyos/atlas-ui`                  | `component-dialog` (`wrap_then_strangle`)        |
| `DropdownMenu`     | package — `@polisyos/atlas-ui`                  | none                                             |
| `EmptyState`       | package — `@polisyos/atlas-ui`                  | `component-empty-state` (`wrap_then_strangle`)   |
| `Icon`             | package — `@polisyos/atlas-ui`                  | none                                             |
| `Input`            | package — `@polisyos/atlas-ui`                  | `component-text-field` (`wrap_then_strangle`)    |
| `Label`            | package — `@polisyos/atlas-ui`                  | none                                             |
| `Popover`          | package — `@polisyos/atlas-ui`                  | none                                             |
| `Radio`            | package — `@polisyos/atlas-ui`                  | none                                             |
| `ScrollArea`       | package — `@polisyos/atlas-ui`                  | `component-scroll-area` (`admit_after_refactor`) |
| `SegmentedControl` | package — `@polisyos/atlas-ui`                  | none                                             |
| `Select`           | package — `@polisyos/atlas-ui`                  | `component-select-field` (`wrap_then_strangle`)  |
| `Separator`        | package — `@polisyos/atlas-ui`                  | none                                             |
| `Sheet`            | package — `@polisyos/atlas-ui`                  | none                                             |
| `Skeleton`         | package — `@polisyos/atlas-ui`                  | `component-skeleton` (`wrap_then_strangle`)      |
| `Slider`           | package — `@polisyos/atlas-ui`                  | none                                             |
| `Switch`           | package — `@polisyos/atlas-ui`                  | `component-switch` (`wrap_then_strangle`)        |
| `Tabs`             | package — `@polisyos/atlas-ui`                  | `component-tabs` (`wrap_then_strangle`)          |
| `Text`             | package — `@polisyos/atlas-ui`                  | none                                             |
| `Textarea`         | package — `@polisyos/atlas-ui`                  | `component-text-area` (`wrap_then_strangle`)     |
| `ToggleButton`     | package — `@polisyos/atlas-ui`                  | none                                             |
| `Tooltip`          | package — `@polisyos/atlas-ui`                  | none                                             |

C01 creates private package `@polisyos/atlas-ui@0.1.0`, strict exports,
package typecheck/test/lint/architecture scripts, and migrates foundation
primitives: `AsyncSection`, `Badge`, `Button`, `Card`, `EmptyState`, `Icon`,
`Skeleton`, and `Text`, while rebinding `ApiErrorAlert` and `ProvenanceStrip`.
C02 migrates form/control primitives: `Checkbox`, `Input`, `Label`, `Radio`,
`SegmentedControl`, `Select`, `Slider`, `Switch`, `Textarea`, and
`ToggleButton`. C03 migrates overlays/navigation: `Command`, `Dialog`,
`DropdownMenu`, `Popover`, `ScrollArea`, `Separator`, `Sheet`, `Tabs`, and
`Tooltip`. Each cluster moves imports directly, removes the prior implementation
file and barrel export in the same commit, and adds no compatibility shim.
Every exported primitive has a migrated live consumer before its old owner is
removed.
The initial package files are `packages/atlas-ui/package.json`, `tsconfig.json`,
`src/index.ts`, `src/primitives/**`, `tests/**`, and package-local lint and
architecture configuration.

Red-first tests:

- C01: `packages/atlas-ui/tests/oneOwner.test.ts > rejects a duplicate foundation primitive owner while the old path still exports it`.
- C01: `apps/runtime-dashboard/src/shared/ui/primitives/primitiveMigration.test.tsx > renders migrated foundation primitives from the package without compatibility shims`.
- C02: `packages/atlas-ui/tests/oneOwner.test.ts > rejects a duplicate form primitive owner while the old path still exports it`.
- C02: `apps/runtime-dashboard/src/shared/ui/primitives/primitiveMigration.test.tsx > preserves form labels focus and validation after direct package migration`.
- C03: `packages/atlas-ui/tests/oneOwner.test.ts > rejects a duplicate overlay primitive owner while the old path still exports it`.
- C03: `apps/runtime-dashboard/src/shared/ui/primitives/primitiveMigration.test.tsx > preserves overlay focus dismissal and portal behavior after direct package migration`.
- `packages/atlas-ui/tests/publicSurface.test.ts > exports only typed supported primitives`.

### DS4-C04 — D2 token adapter source and parity

| Living unit              | Call and one home                                                                                    | DS2 adoption-ledger IDs                                                                                           |
| ------------------------ | ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `tokens/designTokens.ts` | rebind consumers to generated package projections; remains transitional read-only baseline until DS6 | `token-root-primitive`, `token-root-semantic`, `token-root-theme`, `token-root-responsive`, `token-root-data-viz` |
| `chartTheme.ts`          | rebind to package-generated typed aliases                                                            | `token-root-data-viz`                                                                                             |
| `motion.ts`              | rebind to package-generated motion aliases                                                           | `token-root-primitive`, `token-mode-reduced-motion`, `token-mode-prefers-reduced-motion`                          |

The one-way package topology is
`tokens/source/*.tokens.json + tokens/modes/*.tokens.json ->`
`src/tokens/project.ts -> src/generated/{tokens.css,tokens.ts,tailwind.ts,figma.json,manifest.json}`.
Generated files are never hand edited. `designTokens.ts` is not declared
sunset in DS4; DS6 must still supply replacement evidence.
`token-root-component` has ledger verdict `defer` and is excluded from C04;
component values migrate only through the per-component C01-C03 ledger rows and
their revisit conditions. No v15 component-token bulk material is consumed.

| D2 parity gap            | Ledger IDs                                                                                                                                                                | Exact proof                                                                                |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| warm-dark values         | `token-root-theme`, `token-mode-dark`, `token-mode-prefers-color-scheme-dark`                                                                                             | ADR-047 values byte/semantic parity; no visual identity swap                               |
| z-index                  | `token-root-primitive`                                                                                                                                                    | all eight live layer aliases project exactly; raw Tailwind z-index census remains explicit |
| post-reference aliases   | `token-root-semantic`                                                                                                                                                     | live semantic aliases, including non-blue transport, compare equal                         |
| density/runtime controls | `token-root-responsive`, `token-mode-comfortable-density`, `token-mode-compact-density`, `token-mode-condensed-density`                                                   | comfortable/compact/condensed runtime projections and provider behavior                    |
| breakpoint projection    | `token-root-responsive`; rejected `responsive-breakpoint-taxonomy` is never imported                                                                                      | live five-tier projection has one generated manifest                                       |
| mode provider            | `component-theme-provider`, `component-theme-toggle`, `component-accessibility-mode-panel`, `token-mode-light`, `token-mode-dark`, `token-mode-prefers-color-scheme-dark` | provider/toggle round trip and system fallback                                             |
| forced color             | `token-mode-forced-colors`, `token-mode-high-contrast`, `token-mode-prefers-contrast`                                                                                     | forced-colors and contrast media behavior                                                  |
| motion                   | `token-root-primitive`, reduced-motion IDs                                                                                                                                | reduced-motion removes nonessential motion; duration parity is explicit                    |
| print                    | `token-mode-print`, `responsive-print-export`                                                                                                                             | print projection and Storybook/Playwright print snapshot                                   |

The drift test first proves a deliberate corrupt generated value fails, then
requires live `designTokens.ts` semantics to equal DTCG output for migrated
families. C04 creates the source and projections but does not centrally migrate
all consumers. Each C06-C17 family cluster switches only its own token imports
after the relevant parity case is green. Lockfile verification compares package
keys and resolved versions before/after; only the `@polisyos/atlas-ui`
workspace importer may appear.

After the last C17 consumer migration, `designTokens.ts` may remain only as a
mechanically generated compatibility projection. That closes authoring duality
without claiming file deletion or the DS6-gated full sunset. If conversion to a
generated projection is not proven, `ui-tokens` remains `rebind_pending` and is
reported honestly at C20.

Red-first tests:

- `packages/atlas-ui/tests/tokenProjectionParity.test.ts > preserves ADR-047 warm-dark values across DTCG projections`.
- `packages/atlas-ui/tests/tokenProjectionParity.test.ts > projects every live z-index alias exactly once`.
- `packages/atlas-ui/tests/tokenProjectionParity.test.ts > preserves post-reference semantic aliases`.
- `packages/atlas-ui/tests/tokenProjectionParity.test.ts > switches comfortable compact and condensed density at runtime`.
- `packages/atlas-ui/tests/tokenProjectionParity.test.ts > projects the live five-tier breakpoint contract without the rejected taxonomy`.
- `packages/atlas-ui/tests/tokenProjectionParity.test.ts > round-trips light dark and system through the mode provider`.
- `packages/atlas-ui/tests/tokenProjectionParity.test.ts > applies forced-color and contrast modes without semantic color dependence`.
- `packages/atlas-ui/tests/tokenProjectionParity.test.ts > removes nonessential motion for reduced-motion modes`.
- `packages/atlas-ui/tests/tokenProjectionParity.test.ts > projects print tokens and export behavior`.
- `packages/atlas-ui/tests/tokenProjectionDrift.test.ts > rejects a corrupted generated value while source markers remain intact`.
- `packages/atlas-ui/tests/tokenProjectionDrift.test.ts > rejects hand-edited generated output`.

### DS4-C05 — status-retirement authority and guard

Derive the inventory from current code, never from the measured denominator:

1. Parse named TypeScript aliases/enums/interfaces and inline literal unions
   under dashboard `src`, excluding generated/vendor/build paths.
2. Join definitions to every import, prop, state initializer, comparison, map,
   story, fixture, and test consumer.
3. Classify each item as `lattice_derived`, `interaction_state`, or `removed`.
   `interaction_state` requires a non-authority purpose and a negative proving it
   cannot enter an authority slot.
4. Reconcile all 47 DS1 rows, including deleted rows, and report both the DS1
   denominator and the current authored-code denominator. Never force the live
   count to equal 47.
5. Persist
   `architecture/atlas_surfaces/status-retirement-inventory.json`, typed by
   `status-retirement-inventory.schema.json`, containing source span,
   consumers, owner type, classification, replacement, authority purpose, and
   verification ref.
6. `architecture/atlas_surfaces/check_status_retirement_inventory.py`
   generically derives banned local authority definitions from that artifact
   and the generated-client exports. Corruption probes add a renamed union,
   inline synonym, present-but-fake import, and sibling consumer.

The three `DisputeStatus` definitions become one owner. The generated
`VerificationMetadata` dispute/freshness/verification fields are used where
their declared purpose fits; the `runs/domain/disputes.ts` operational workflow
state remains separately named and cannot masquerade as evidence authority.

Red-first tests:

- `src/shared/lib/domain/statusOwnership.test.ts > rejects a revived UI-local authority status definition` (`DS1-N007`).
- `src/shared/lib/domain/statusOwnership.compile.test.ts > rejects divergent DisputeStatus vocabularies`.
- `src/shared/lib/domain/statusOwnership.test.ts > accepts interaction state only when barred from authority slots`.
- `check_status_retirement_inventory.py --corruption-probes > rejects an inline authority synonym and a sibling consumer`.

### DS4-C06-C08 — quantity family and 75-diagnostic queue

| Component                  | Call and one home                  | DS2 adoption-ledger ID                                       |
| -------------------------- | ---------------------------------- | ------------------------------------------------------------ |
| `Quantity`                 | rebind — dashboard quantity family | `viz-contract-uncertainty-contract` (material only)          |
| `CounterfactualQuantity`   | rebind — dashboard quantity family | `viz-contract-uncertainty-contract`                          |
| `ProvenanceDeepDiveDialog` | rebind — dashboard quantity family | `component-provenance-graph`, `viz-chart-provenance-lineage` |
| `ProvenanceMiniGraph`      | rebind — dashboard quantity family | `component-provenance-graph`, `viz-chart-provenance-lineage` |
| `ProvenancePopover`        | rebind — dashboard quantity family | `component-provenance-graph`, `component-provenance-map`     |

The queue is partitioned without weakening the rule. C06 rebinds the quantity
contract and actual decision producers in `productionSlice.ts`,
`RunExplainabilityPanel.tsx`, `deckTemplate.ts`, `publicSectorReadiness.ts`,
`publicationPacket.ts`, `useRunDetailSummary.ts`, and `simulation.ts`; those
values become `QuantityValue` and render through `Quantity`. C07 handles chart
decision/display semantics in `AnimatedNumber`, `ForestPlot`,
`SpecificationCurveChart`, `BSTSVisualization`, `DiDVisualization`,
`SyntheticControlViz`, `FactorImportanceChart`, and `SensitivityPlot`, while
preserving set/interval/unknown/incomparable structure. C08 closes the remaining
interaction/layout identities in collaboration, causal, evidence, brand,
motion, and responsive files through a typed `layout` classification recognized
structurally by the lint rule.

Each cluster rewrites the exact lint baseline artifact in the same commit and
must strictly reduce both its identity count and touched-file denominator. A
diagnostic cannot move identity and masquerade as removal. Red adversarial tests
prove an effect/confidence value cannot escape by using the layout
classification. Target is 75 -> 0; any honest remainder is re-manifested with
per-identity reason, owner, and closure signal.

Red-first tests:

- C06: `src/shared/ui/quantity/Quantity.test.tsx > preserves unknown and incomparable outer-set values without scalar collapse`.
- C06: `src/shared/ui/quantity/quantityDecisionProducers.test.tsx > emits and consumes every manifest-owned decision-bearing value as QuantityValue`; the cases are derived from the debt artifact rather than hand enumerated.
- C06: `src/shared/ui/quantity/ProvenancePopover.test.tsx > renders generated lineage and verification metadata without a local trust status`.
- C07: `src/shared/charts/quantityChartSemantics.test.tsx > preserves distribution interval unknown and incomparable chart values without scalar collapse`.
- C08: `eslint-plugin-local/rules/quantity-must-be-wrapped.test.cjs > rejects decision values disguised as layout or motion`.
- C08: `eslint-plugin-local/rules/quantity-must-be-wrapped.test.cjs > accepts structurally typed SVG geometry without exempting numeric effect values`.

### DS4-C09 — temporal family and cursor root cause

| Component                  | Call and one home                  | DS2 adoption-ledger ID |
| -------------------------- | ---------------------------------- | ---------------------- |
| `TemporalCapabilityBanner` | rebind — dashboard temporal family | none                   |
| `TemporalCursorMarker`     | rebind — dashboard temporal family | none                   |
| `TemporalLegend`           | rebind — dashboard temporal family | none                   |
| `TemporalScrubber`         | rebind — dashboard temporal family | none                   |
| `withTemporalCursor`       | rebind — dashboard temporal family | none                   |

`component-decision-timeline` is a rejected phantom and is never used. C09
separates `valid_at`, `tx_at`, payload `as_of`, observation time, cached state,
and typed source freshness. The existing temporal failure is reproduced red,
fixed at the root so the committed cursor wins over wall-clock defaults, and
then removed from the baseline manifest.

Red-first tests:

- existing `TemporalCursorProvider.test.tsx > commits canonical URL params`.
- `TemporalSemantics.test.tsx > renders missing epoch and as-of semantics as unknown or stale`.
- `TemporalSemantics.test.tsx > never treats observed_at as source_as_of`.
- `TimeSemanticsLabel.test.tsx > never maps source observation state to cache-age staleness`.

### DS4-C10-C12 — authorship, trust, and operator evidence

| Component                 | Call and one home                       | DS2 adoption-ledger ID                      |
| ------------------------- | --------------------------------------- | ------------------------------------------- |
| `AuthorBadge`             | rebind — dashboard authored-text family | `content-trust-copy` (copy material only)   |
| `AuthoredText`            | rebind — dashboard authored-text family | `content-trust-copy`                        |
| `AuthorshipProvider`      | rebind — dashboard authored-text family | none                                        |
| `DisputeBadge`            | rebind — dashboard trust-view family    | `component-governance-gate` (material only) |
| `HashChip`                | rebind — dashboard trust-view family    | `component-provenance-map`                  |
| `TemporalScopeChip`       | rebind — dashboard trust-view family    | none                                        |
| `TrustInspector`          | rebind — dashboard trust-view family    | `component-provenance-graph`                |
| `TrustMetadata`           | rebind — dashboard trust-view family    | `component-provenance-map`                  |
| `TrustViewBadge`          | rebind — dashboard trust-view family    | `component-governance-gate`                 |
| `TrustViewToggle`         | rebind — dashboard trust-view family    | none                                        |
| `VerificationStatus`      | rebind — dashboard trust-view family    | `component-governance-gate`                 |
| `OperatorDiagnosticPanel` | rebind — dashboard root                 | none                                        |

C10 owns the three authored-text rows and severs their app/provider imports.
C11 owns the eight trust-view rows, the single generated
`VerificationMetadata` binding, and their app/provider severing. C12 owns
`OperatorDiagnosticPanel`, the independent define-once package shells, and the
a11y decision from C00. Family-composed evidence primitives stay with their
source-family clusters below. Each cluster retires only its status rows,
switches only its proven token consumers, and records its own DS19
successor/consumer evidence.

The evidence primitives are assembled by rebinding first:

| Primitive              | Owning cluster | One owner / source family                                                                                                            | Build decision                                                           |
| ---------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| `AuthorityBadge`       | C12            | package wrapper over package `Badge`; semantic posture supplied only by an owner-declared known core, with opaque extensions neutral | new define-once shell, blocked at C00 for missing composition vocabulary |
| `CandidateFrame`       | C14            | dashboard `DecisionCard` + C10-authored-text posture                                                                                 | rebind; never infer human review                                         |
| `BlockerCard`          | C14            | dashboard `NegativeCertificateCard` + C12 `OperatorDiagnosticPanel`                                                                  | rebind                                                                   |
| `EnvelopeChip`         | C12            | `@polisyos/atlas-ui`                                                                                                                 | genuinely new define-once primitive                                      |
| `EvidenceLink`         | C12            | `@polisyos/atlas-ui`                                                                                                                 | genuinely new define-once primitive                                      |
| `ProvenancePopover`    | C06            | existing dashboard quantity family                                                                                                   | rebind; no duplicate package owner                                       |
| `TimeSemanticsLabel`   | C09            | dashboard temporal/trust families using typed `ProjectionFreshness`                                                                  | rebind for declared semantics only                                       |
| `WeakestLinkExplainer` | C14            | dashboard diagnostic/certificate families                                                                                            | rebind; display producer-supplied weakest link verbatim, never recompute |

`fixture_only` is not a new local vocabulary. Its canonical type is the indexed
generated type
`components["schemas"]["LegacyProvingGroundPayload"]["fixture_authority"]`
from `packages/runtime-api-client/types.ts:6189`. Package visual props reuse
that type but remain authority-neutral. The discriminant is visually marked
and rejected at authority-bearing prop boundaries. No string flag, CSS class,
or fixture name is accepted as proof.

Red-first tests:

- C10: `src/shared/ui/authored-text/AuthoredText.test.tsx > renders unverified model prose as candidate and never as human reviewed`.
- C11: `src/shared/ui/trust-view/TrustViewAuthority.test.tsx > never renders verified from missing or projection-only metadata`.
- C12: `src/shared/ui/OperatorDiagnosticPanel.test.tsx > never promotes projection labels when runtime authority is blocked`.
- C12: `src/shared/ui/OperatorDiagnosticPanel.a11y.test.tsx > exposes the real blocker structure and keyboard-readable evidence`; do not add it to an allowlist.
- C12: `packages/atlas-ui/tests/AuthorityBadge.test.tsx > renders an opaque extension in neutral unknown posture`.
- C12: `packages/atlas-ui/tests/EnvelopeChip.test.tsx > preserves the typed authority purpose without inventing a grade`.
- C12: `packages/atlas-ui/tests/EvidenceLink.test.tsx > renders a typed evidence reference without claiming verification`.
- C12: `src/shared/ui/evidence/fixtureOnlyAuthority.compile.test.tsx > rejects fixture_only at an authority-bearing prop boundary`.

### DS4-C13 — counterfactual family and projection negatives

| Component                   | Call and one home                        | DS2 adoption-ledger ID                                                               |
| --------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------ |
| `AssumptionPill`            | rebind — dashboard counterfactual family | none                                                                                 |
| `CounterfactualBadge`       | rebind — dashboard counterfactual family | none                                                                                 |
| `CounterfactualMetricChart` | rebind — dashboard counterfactual family | `component-uncertainty-band`; rejected `viz-chart-uncertainty-band` remains rejected |
| `CounterfactualModeSwitch`  | rebind — dashboard counterfactual family | none                                                                                 |
| `ScenarioManifestPanel`     | rebind — dashboard counterfactual family | none                                                                                 |
| `ScenarioPicker`            | rebind — dashboard counterfactual family | none                                                                                 |
| `CounterfactualDelta`       | use_as_is — dashboard                    | none                                                                                 |
| `DualInput`                 | use_as_is — dashboard                    | none                                                                                 |
| `DualSelector`              | use_as_is — dashboard                    | none                                                                                 |
| `DualSlider`                | use_as_is — dashboard                    | none                                                                                 |

Red-first PI-06 tests land before positive work:

- `features/runs/routes/tabs/CausalTab.test.tsx > keeps local causal drafts out of identified effect authority slots` (`DS1-N002`).
- `features/whatif/ScenarioValidationPanel.test.tsx > does not infer validation readiness from empty local issue arrays` (`DS1-N003`).
- `features/composer/routes/LaunchRunPage.test.tsx > does not raise readiness from local model-count scoring` (`DS1-N005`).
- `shared/lib/domain/projectionFailClosed.test.ts > never infers closeout authority from projection label text` (`DS1-N008`).

### DS4-C14 — compound evidence and deferred DS16 values

| Component                 | Call and one home            | DS2 adoption-ledger ID                                       |
| ------------------------- | ---------------------------- | ------------------------------------------------------------ |
| `DataFreshnessBadge`      | rebind — dashboard compounds | none                                                         |
| `DecisionCard`            | rebind — dashboard compounds | none                                                         |
| `EvidenceChain`           | rebind — dashboard compounds | `viz-domain-evidence-provenance`                             |
| `ExplainabilityCard`      | rebind — dashboard compounds | none                                                         |
| `GovernancePassGrid`      | rebind — dashboard compounds | `component-governance-gate`, `viz-domain-governance-gates`   |
| `MethodologyBadge`        | rebind — dashboard compounds | none                                                         |
| `NegativeCertificateCard` | rebind — dashboard compounds | none                                                         |
| `ProvenanceChain`         | rebind — dashboard compounds | `component-provenance-graph`, `viz-chart-provenance-lineage` |
| `ReasoningChainDisplay`   | rebind — dashboard compounds | none                                                         |
| `StatusTimeline`          | rebind — dashboard compounds | `viz-chart-timeline`; never `component-decision-timeline`    |
| `TrustCalibrationDisplay` | rebind — dashboard compounds | none                                                         |
| `AttributionWaterfall`    | use_as_is pending DS16       | `viz-chart-waterfall`                                        |
| `EvidenceCoverageRadar`   | use_as_is pending DS16       | none                                                         |
| `FactorImportanceChart`   | use_as_is pending DS16       | none                                                         |
| `SensitivityPlot`         | use_as_is pending DS16       | none                                                         |

Red-first tests:

- `DecisionCard.test.tsx > keeps candidate and authority postures visually distinct for the same copy`.
- `CandidateFrame.test.tsx > never promotes model prose without the generated authority purpose`.
- `BlockerCard.test.tsx > preserves the producer blocker and cannot be overridden by local severity`.
- `WeakestLinkExplainer.test.tsx > uses the producer supplied weakest link without recomputing it`.
- `GovernancePassGrid.test.tsx > preserves mixed blocked contested partial and review-required outcomes without flattening`.
- `StatusTimeline.test.tsx > renders recorded events without inventing a DecisionTimeline authority`.

### DS4-C15-C16 — compounds and patterns

| Component        | Call and one home              | DS2 adoption-ledger ID                                            |
| ---------------- | ------------------------------ | ----------------------------------------------------------------- |
| `DataTable`      | package — `@polisyos/atlas-ui` | `component-data-table`                                            |
| `JsonPreview`    | package — `@polisyos/atlas-ui` | none                                                              |
| `MetricCard`     | package — `@polisyos/atlas-ui` | `component-metric-card`                                           |
| `VirtualList`    | package — `@polisyos/atlas-ui` | none                                                              |
| `VirtualTable`   | package — `@polisyos/atlas-ui` | none                                                              |
| `LineageGraph`   | rebind — dashboard compounds   | `component-provenance-graph`, `viz-chart-provenance-lineage`      |
| `DetailLayout`   | package — `@polisyos/atlas-ui` | `responsive-layout-two-pane`, `responsive-layout-supporting-pane` |
| `FilterPanel`    | package — `@polisyos/atlas-ui` | none                                                              |
| `SearchableList` | package — `@polisyos/atlas-ui` | `component-search-field`, `form-search-source-selection`          |

C15 owns the six `ui-compounds-root` rows. C16 owns the three pattern rows.
Each cluster severs its shared→app/API edges by passing typed presentation data
and callbacks into shared components; hooks/providers/adapters remain app-side,
and tests/stories use shared-owned harness adapters. Each cluster must strictly
reduce the exact architecture manifest. The final cross-family and
app/workspace edge closure is C18.

Red-first tests:

- C15: `src/shared/ui/sharedUiArchitecture.test.ts > rejects a compound importing app API or feature state`.
- C15: `packages/atlas-ui/tests/oneOwner.test.ts > rejects a migrated compound with a surviving dashboard implementation`.
- C16: `src/shared/ui/sharedUiArchitecture.test.ts > accepts an app-owned adapter feeding typed pattern presentation props`.
- C16: `packages/atlas-ui/tests/oneOwner.test.ts > rejects a migrated pattern with a surviving dashboard implementation`.

### DS4-C17 — responsive disposition and runtime controls

| Component         | Call and one home             | DS2 adoption-ledger ID        |
| ----------------- | ----------------------------- | ----------------------------- |
| `BottomSheet`     | use_as_is until adapter proof | none                          |
| `MobileNav`       | use_as_is until adapter proof | `responsive-shell-navigation` |
| `PullToRefresh`   | use_as_is until adapter proof | none                          |
| `SwipeableDrawer` | use_as_is until adapter proof | none                          |

C17 updates register rows with bounded `use_as_is` rationale and proves the D2
adapter does not mutate responsive behavior. It does not claim the rejected
`responsive-breakpoint-taxonomy` as an owner.

Red-first test:

- `src/shared/ui/responsive/responsiveTokenParity.test.tsx > preserves live breakpoint density and gesture behavior through the generated adapter`.

### DS4-C18 — architecture remainder closure

C06-C17 sever dependencies family by family. C18 closes only the measured
remainder: chart/shared edges not owned by a component family and
`app/workspaces.ts -> features/runs` through the feature public barrel. Its
red-first tests are:

- `src/shared/ui/sharedUiArchitecture.test.ts > rejects every remaining shared to app API or feature edge from the measured manifest`.
- `src/app/workspaces.test.ts > imports run workspace data only through the feature public surface`.

Target is 36 -> 0. Any honest remainder must name the exact edge, owner,
reason, and closure signal in the debt manifest; the checker is never
suppressed.

### DS4-C19 — Storybook, a11y, visual negatives, and real-panel proof

Extend the existing Storybook harness and
`apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts`; add no route.
Every DS4 primitive has normal, loading/missing, error/blocked, long-copy, keyboard,
forced-color, reduced-motion, print, and small/large viewport evidence as
applicable. Exact visual tests include:

- `renders candidate output in candidate clothing` and proves it does not match
  the human-reviewed/authority baseline.
- `marks fixture-only content and bars it from authority slots`.
- `renders every DS4 evidence primitive`.

The real-panel proof is the existing
`apps/runtime-dashboard/src/features/runs/components/RunExplainabilityPanel.tsx`.
The app-owned
`apps/runtime-dashboard/src/features/runs/api/useDepthNCycleBoardProjection.ts`
adapter imports the canonical runtime client, reads the
`depth-n-cycle-board` governed projection, and passes typed presentation data
into that panel; shared primitives remain API-clean. The panel renders typed
availability, terminal/evidence payload fields, and `ProjectionFreshness`
through the rebound primitives. `artifact_missing` uses a typed, visibly
`fixture_only` fallback and cannot occupy an authority slot.
Open terminal/evidence strings are always displayed opaquely; only a
C00-ratified known-core contract may receive semantic posture. The UI never
orders, recolors, maps, or recomputes opaque extensions. There is no new
product route and no client-side weakest-link calculation.

Red-first integration tests:

- `RunExplainabilityPanel.governedProjection.test.tsx > renders producer terminal evidence and as-of without local reclassification`.
- `RunExplainabilityPanel.governedProjection.test.tsx > marks typed artifact absence as fixture-only and blocks authority posture`.
- `RunExplainabilityPanel.governedProjection.test.tsx > preserves an unseen terminal and evidence label verbatim`.

### DS4-C20 — closure wave

Run fresh full gates in this order:

```bash
cd policy-engine
python3 architecture/atlas_surfaces/check_frontend_disposition_register.py \
  --check --verify-baseline-source-bytes --corruption-probes
cd apps/runtime-dashboard
corepack pnpm run typecheck
corepack pnpm run build
corepack pnpm run lint
corepack pnpm run test:components
corepack pnpm run check:architecture
# package-owned typecheck/test/lint/architecture and Storybook/Playwright commands
# are added in C01/C19 and invoked here by their committed script names.
```

Then prove:

- all touched DS19 rows have successor/consumer evidence or honest `use_as_is`;
- status inventory reconciles the 47 DS1 rows and a revived local authority enum
  fails generically;
- quantity is 75 -> N with every remainder itemized; target zero;
- temporal-cursor is closed; a11y denominator follows the C00 decision;
- architecture is 36 -> N with every remainder itemized; target zero;
- all nine token gaps have closed/open evidence and no unproved sunset claim;
- visual/a11y/semantic negatives exercise runtime properties, not markers;
- `git diff` touches only the writable fence and the bounded lockfile importer;
- worktree is clean after the final scoped commit.

The closure report is a table by family and cluster with call, ledger IDs,
register transitions, consumer evidence, debt deltas, token parity, harness
coverage, real-panel proof, and commits. It references the disposition register
as authority and does not duplicate its row narratives. No merge or push.

## Expected cluster commits

| Cluster | Commit intent                                                    |
| ------- | ---------------------------------------------------------------- |
| C00     | `docs: plan Atlas DS4 status grammar rebinding`                  |
| C01     | `feat(atlas-ui): migrate foundation primitives`                  |
| C02     | `feat(atlas-ui): migrate form primitives`                        |
| C03     | `feat(atlas-ui): migrate overlay primitives`                     |
| C04     | `feat(atlas-ui): project ratified DTCG token parity`             |
| C05     | `test(dashboard): govern the status retirement inventory`        |
| C06     | `refactor(dashboard): wrap decision producers as quantities`     |
| C07     | `refactor(dashboard): preserve chart quantity semantics`         |
| C08     | `fix(dashboard): classify nondecision numeric layout values`     |
| C09     | `fix(dashboard): rebind temporal semantics and cursor`           |
| C10     | `refactor(dashboard): rebind authored candidate posture`         |
| C11     | `refactor(dashboard): rebind trust view authority`               |
| C12     | `refactor(dashboard): rebind operator evidence primitives`       |
| C13     | `refactor(dashboard): fail closed on counterfactual projections` |
| C14     | `refactor(dashboard): rebind compound evidence families`         |
| C15     | `refactor(atlas-ui): migrate root compounds`                     |
| C16     | `refactor(atlas-ui): migrate shared patterns`                    |
| C17     | `docs(dashboard): disposition responsive families`               |
| C18     | `refactor(dashboard): close architecture severing remainder`     |
| C19     | `test(dashboard): prove authority posture on a real panel`       |
| C20     | `docs: close Atlas DS4 for architect review`                     |
