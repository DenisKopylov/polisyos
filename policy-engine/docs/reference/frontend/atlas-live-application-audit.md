---
title: Atlas Live Application Audit
status: active - inventory checkpoint
owner: team-design
as_of: 2026-07-16
slice: DS1
audiences: [REVIEWER, EXPERT, MACHINE]
authority: classification-only
---

# Atlas Live Application Audit

This is the human twin of the
[live readiness ledger](../../../architecture/atlas_surfaces/live-application-readiness-ledger.json)
and the definitive DS1 map of the checked-out frontend and runtime HTTP zone.
It is authoritative for code-grounded existence, denominator, and gap
classification at `codex/atlas-ds0-source-of-truth`. It is not runtime,
publication, promotion, accessibility-conformance, or product authority. No
finding in this document unfreezes a route, approves a migration, or proves a
surface safe.

The audit executes the [DS1 task plan](../../plans/active/atlas-slices/DS1-live-application-audit.md),
uses the controlled vocabularies frozen by
[DS0](../../brand/ATLAS_SOURCE_OF_TRUTH.md), and judges maturity against the
[surface constitution](../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md).

## Reading The Chain

Every inventory row carries `C/P/A/B/U/V/S/N/T`: typed contract, producer,
persisted artifact/state, orchestration or transport bridge, consumer,
verification, surface, negative test, and semantic test. `I`, `M`, and `O`
mean implemented, missing, and out of scope. The aggregate readiness follows
the DS1 plan's weakest-link rule; the adoption verdict is independent.

## Denominator Reconciliation And Coverage Proof

Counts were recomputed from tracked files and parsed declarations. Physical
LOC is `wc -l`; generated code is included only where the row says so. The
snapshot's 908/137k baseline is exactly the dashboard `src` tree, not the full
frontend zone.

| Dimension | Revision 2 / June claim | Measured 2026-07-16 | Audit coverage and method |
| --- | ---: | ---: | --- |
| Dashboard `src` TS/TSX | 908 | **908; 136,827 LOC** | audited 908/908; `git ls-files apps/runtime-dashboard/src` filtered to `.ts`/`.tsx`, `wc -l` |
| Full frontend TS/TSX | unstated | **944; 145,033 LOC** | audited 944/944 across `apps`, `packages`, `frontend`, `e2e`; includes dashboard 936, generated client 1, CLI 7 |
| Dashboard source tests | 230 | **230 `.test` + 3 authored `.spec`** | audited 233/233 under `src` |
| Full test/spec estate | unstated | **251** | audited 251/251: dashboard 250 plus CLI 1; 231 `.test`, 20 `.spec` |
| Dashboard route inventory | 14 named paths | **32 objects; 29 effective patterns; 22 leaf UI patterns** | audited 32/32 objects; route-object traversal plus factory registry expansion |
| Feature modules | 17 | **17** | audited 17/17 immediate `features/*` directories, including empty `layout` |
| Shared/UI components | about 40 | **89 implementation TSX in 12 families** | audited 12/12 families and 89/89 member files; tests/stories/index files excluded |
| OpenAPI operations | 89 | **89: 45 surface-consumed, 7 hook-only, 37 uncalled** | audited 89/89 by HTTP method + path in the checked-in schema |
| Hand-written fetch outside `src/api` | about 10 files | **9 calls in 5 production files** | audited 9/9; tooling adds one call in a sixth file; Lex no longer raw-fetches |
| UI-local statuses | at least 8 | **23 named + 24 inline literal-union definitions** | audited 47/47 production definitions; generated API types excluded |
| Flags | 12 + auth override | **12 canonical + 1 auth-derived pseudo-flag** | audited 13/13; all four DS0 `consumer_missing` claims confirmed |
| Stories | 44 | **44** | audited 44/44 tracked stories |
| A11y files | per component across about 40 | **67 `.a11y.test`; 64 under shared/UI, only 63 invoke axe** | audited 67/67; shared/UI membership difference recomputed |
| `aria-` occurrences | 388 | **390 in 176 TSX files** | audited 390/390 with ripgrep |
| Browser e2e specs | unstated | **17** | audited 17/17: 4 a11y, 12 journeys, 1 visual |
| Visual baselines | unstated | **16 PNGs** | audited 16/16 tracked Chromium/Darwin snapshots |

Reproduction core:

```sh
git ls-files 'policy-engine/apps/runtime-dashboard/src/**/*.ts' \
  'policy-engine/apps/runtime-dashboard/src/**/*.tsx' | sort -u
git ls-files 'policy-engine/apps/**' 'policy-engine/packages/**' \
  'policy-engine/frontend/**' 'policy-engine/e2e/**' | rg '\.(ts|tsx)$'
rg -n 'fetch\(|new EventSource|new WebSocket' \
  policy-engine/apps/runtime-dashboard --glob '!src/api/**'
rg -o 'aria-' policy-engine/apps/runtime-dashboard --glob '*.tsx'
```

The inventory-table region below is the report-side set used for machine
parity. At closeout, its first-column IDs and the ledger `surface_id` set must
be identical, unique, and have empty differences.

<!-- BEGIN AUDIT UNIT INDEX -->

## Route Objects: Audited 32 Of 32

The 32 objects collapse to 29 effective URL patterns because the root layout
and two sibling index objects all resolve to `/`, while the run-detail layout
and its index redirect both resolve to `/runs/:runId`. The later Clerk index is
redundant: `ModeAwareHome` already selects the Clerk page.

| Unit ID | Object / effective path | Evidence | Chain; readiness; maturity | Adoption / owner |
| --- | --- | --- | --- | --- |
| `route-welcome` | `/welcome` | [landing route](../../../apps/runtime-dashboard/src/features/landing/route.tsx#L4) | `O/O/O/O/I/M/I/M/M`; `verification_missing`; experimental | `admit_after_refactor`; DS11 |
| `route-public-decision` | `/public/decisions/:signedId` | [public route](../../../apps/runtime-dashboard/src/features/runs/route.tsx#L112) | `M/M/M/M/I/I/I/M/I`; `contract_only`; experimental | `wrap_then_strangle`; DS12 |
| `route-app-layout` | `/` provider/layout | [root object](../../../apps/runtime-dashboard/src/app/routes/routes.tsx#L188) | `I/O/O/I/I/I/I/I/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS4 |
| `route-login` | `/login` | [auth route](../../../apps/runtime-dashboard/src/features/auth/route.tsx#L14) | `M/M/O/M/I/I/I/I/M`; `contract_only`; experimental | `admit_after_refactor`; DS5 |
| `route-home-mode-aware` | `/` first index | [inline index](../../../apps/runtime-dashboard/src/app/routes/routes.tsx#L194), [mode selector](../../../apps/runtime-dashboard/src/app/routes/ModeAwareHome.tsx#L6) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS4 |
| `route-home-clerk-duplicate` | `/` second index | [duplicate index](../../../apps/runtime-dashboard/src/features/clerk/route.tsx#L19), [insertion](../../../apps/runtime-dashboard/src/app/routes/routes.tsx#L203) | `I/I/I/I/M/M/M/M/M`; `consumer_missing`; deprecated | `reject`; DS14 |
| `route-compose` | `/compose` | [composer route](../../../apps/runtime-dashboard/src/features/composer/route.tsx#L17) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `wrap_then_strangle`; DS9 |
| `route-runs-list` | `/runs` | [runs list](../../../apps/runtime-dashboard/src/features/runs/route.tsx#L178) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS7 |
| `route-runs-compare` | `/runs/compare` | [compare route](../../../apps/runtime-dashboard/src/features/runs/route.tsx#L189) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS8 |
| `route-runs-compare-legacy` | `/compare/:runA/:runB` | [legacy compare](../../../apps/runtime-dashboard/src/features/runs/route.tsx#L199) | `I/I/I/I/I/M/I/M/M`; `verification_missing`; deprecated | `wrap_then_strangle`; DS8 |
| `route-run-report` | `/runs/:runId/report` | [report route](../../../apps/runtime-dashboard/src/features/runs/route.tsx#L209) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS8 |
| `route-run-deck` | `/runs/:runId/deck` | [deck route](../../../apps/runtime-dashboard/src/features/runs/route.tsx#L219) | `I/I/I/I/I/M/I/M/M`; `verification_missing`; experimental | `admit_after_refactor`; DS8 |
| `route-run-detail-layout` | `/runs/:runId` layout | [detail object](../../../apps/runtime-dashboard/src/features/runs/route.tsx#L229) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS8 |
| `route-run-detail-index-redirect` | `/runs/:runId` to `overview` | [index redirect](../../../apps/runtime-dashboard/src/features/runs/route.tsx#L238) | `I/O/O/O/I/M/I/O/O`; `verification_missing`; beta | `admit_as_is`; DS8 |
| `route-run-overview` | `/runs/:runId/overview` | [tab factory](../../../apps/runtime-dashboard/src/features/runs/route.tsx#L156), [registry](../../../apps/runtime-dashboard/src/app/surfaces/surfaceRegistry.ts#L105) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `wrap_then_strangle`; DS8 |
| `route-run-causal` | `/runs/:runId/causal` | [registry](../../../apps/runtime-dashboard/src/app/surfaces/surfaceRegistry.ts#L122) | `M/I/I/M/I/M/I/M/M`; `contract_only`; experimental | `wrap_then_strangle`; DS8 |
| `route-run-governance` | `/runs/:runId/governance` | [registry](../../../apps/runtime-dashboard/src/app/surfaces/surfaceRegistry.ts#L139) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `wrap_then_strangle`; DS9 |
| `route-run-evidence` | `/runs/:runId/evidence` | [registry](../../../apps/runtime-dashboard/src/app/surfaces/surfaceRegistry.ts#L156) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `wrap_then_strangle`; DS8 |
| `route-run-workflow` | `/runs/:runId/workflow` | [registry](../../../apps/runtime-dashboard/src/app/surfaces/surfaceRegistry.ts#L173) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS8 |
| `route-run-artifacts` | `/runs/:runId/artifacts` | [registry](../../../apps/runtime-dashboard/src/app/surfaces/surfaceRegistry.ts#L190) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS8 |
| `route-run-agents` | `/runs/:runId/agents` | [registry](../../../apps/runtime-dashboard/src/app/surfaces/surfaceRegistry.ts#L206) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `wrap_then_strangle`; DS14 |
| `route-run-debug` | `/runs/:runId/debug` | [registry](../../../apps/runtime-dashboard/src/app/surfaces/surfaceRegistry.ts#L222) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS8 |
| `route-artifact` | `/artifacts/:artifactId` | [artifact route](../../../apps/runtime-dashboard/src/features/artifacts/route.tsx#L23) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS8 |
| `route-evidence` | `/evidence` | [evidence route](../../../apps/runtime-dashboard/src/features/evidence/route.tsx#L17) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `wrap_then_strangle`; DS8 |
| `route-knowledge` | `/knowledge` | [Lex route](../../../apps/runtime-dashboard/src/features/lex/route.tsx#L17) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `wrap_then_strangle`; DS10 |
| `route-platform` | `/platform` | [platform route](../../../apps/runtime-dashboard/src/features/platform/route.tsx#L17) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS6 |
| `route-redirect-launch` | `/launch` to `/compose` | [redirect](../../../apps/runtime-dashboard/src/app/routes/routes.tsx#L210) | `O/O/O/O/I/I/I/O/O`; `implemented`; deprecated | `wrap_then_strangle`; DS4 |
| `route-redirect-sources` | `/sources` to `/evidence` | [redirect](../../../apps/runtime-dashboard/src/app/routes/routes.tsx#L211) | `O/O/O/O/I/I/I/O/O`; `implemented`; deprecated | `wrap_then_strangle`; DS4 |
| `route-redirect-data` | `/data` to `/evidence` | [redirect](../../../apps/runtime-dashboard/src/app/routes/routes.tsx#L212) | `O/O/O/O/I/I/I/O/O`; `implemented`; deprecated | `wrap_then_strangle`; DS4 |
| `route-redirect-lex` | `/lex` to `/knowledge` | [redirect](../../../apps/runtime-dashboard/src/app/routes/routes.tsx#L213) | `O/O/O/O/I/I/I/O/O`; `implemented`; deprecated | `wrap_then_strangle`; DS4 |
| `route-redirect-health` | `/health` to `/platform` | [redirect](../../../apps/runtime-dashboard/src/app/routes/routes.tsx#L214) | `O/O/O/O/I/I/I/O/O`; `implemented`; deprecated | `wrap_then_strangle`; DS4 |
| `route-catch-all` | `*` silently to `/` | [catch-all](../../../apps/runtime-dashboard/src/app/routes/routes.tsx#L215) | `O/O/O/O/I/M/I/M/M`; `verification_missing`; deprecated | `reject`; DS4 |

The route-browser axe matrix covers 17 of the 22 leaf patterns; the missing
five are `/welcome`, the public decision route, legacy compare, run deck, and
run causal ([route list](../../../apps/runtime-dashboard/e2e/helpers/runtime-dashboard.ts#L102)).

## Reference Shell Views: Audited 4 Of 4

The shell has no router. Four buttons switch four sections in one document,
using the package generated client directly.

| Unit ID | View | Evidence | Chain; readiness; maturity | Adoption / owner |
| --- | --- | --- | --- | --- |
| `reference-shell-runs` | Run List | [view](../../../apps/runtime-reference-shell/index.html#L37), [call](../../../apps/runtime-reference-shell/app.js#L183) | `I/I/I/I/I/M/I/M/M`; `verification_missing`; experimental | `admit_after_refactor`; DS3 |
| `reference-shell-timeline` | Timeline + node graph | [view](../../../apps/runtime-reference-shell/index.html#L81), [calls](../../../apps/runtime-reference-shell/app.js#L197) | `I/I/I/I/I/M/I/M/M`; `verification_missing`; experimental | `admit_after_refactor`; DS3 |
| `reference-shell-node-debug` | Node Debug | [view](../../../apps/runtime-reference-shell/index.html#L121), [call](../../../apps/runtime-reference-shell/app.js#L220) | `I/I/I/I/I/M/I/M/M`; `verification_missing`; experimental | `admit_after_refactor`; DS3 |
| `reference-shell-artifacts` | Artifact Inspector | [view](../../../apps/runtime-reference-shell/index.html#L145), [calls](../../../apps/runtime-reference-shell/app.js#L237) | `I/I/I/I/I/M/I/M/M`; `verification_missing`; experimental | `admit_after_refactor`; DS3 |

Its direct import of `RuntimeApiClient` is visible at
[app.js line 1](../../../apps/runtime-reference-shell/app.js#L1). This refutes
the master plan's claim that the dashboard is the only live generated-client
consumer; the dashboard uses `openapi-fetch`, while the diagnostic shell uses
the generated package class.

## Feature Modules: Audited 17 Of 17

Counts are tracked TS/TSX files, physical LOC, colocated test/spec files, and
stories. The chain is the feature aggregate at its weakest boundary.

| Unit ID | Files / LOC / tests / stories | Evidence | Chain; readiness; maturity | Adoption / owner |
| --- | ---: | --- | --- | --- |
| `feature-artifacts` | 60 / 8,234 / 10 / 2 | [route](../../../apps/runtime-dashboard/src/features/artifacts/route.tsx#L23) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS8 |
| `feature-auth` | 8 / 298 / 3 / 0 | [route](../../../apps/runtime-dashboard/src/features/auth/route.tsx#L14), [raw session](../../../apps/runtime-dashboard/src/app/auth/authSession.ts#L134) | `M/M/O/M/I/I/I/I/M`; `contract_only`; experimental | `admit_after_refactor`; DS5 |
| `feature-causal` | 22 / 3,291 / 0 / 0 | [local types](../../../apps/runtime-dashboard/src/features/causal/types.ts#L15), [run consumer](../../../apps/runtime-dashboard/src/features/runs/routes/tabs/CausalTab.tsx#L51) | `M/I/I/M/I/M/I/M/M`; `contract_only`; experimental | `wrap_then_strangle`; DS8 |
| `feature-clerk` | 27 / 4,662 / 3 / 0 | [NL bridge](../../../apps/runtime-dashboard/src/features/clerk/hooks/useClerkNlRun.ts#L24) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `wrap_then_strangle`; DS14 |
| `feature-collaboration` | 15 / 1,996 / 1 / 0 | [phantom comments](../../../apps/runtime-dashboard/src/features/collaboration/hooks/useComments.ts#L15), [barrel](../../../apps/runtime-dashboard/src/features/collaboration/index.ts#L1) | `M/M/M/M/M/I/M/M/M`; `contract_only`; experimental | `defer`; DS5 |
| `feature-command-palette` | 3 / 500 / 1 / 0 | [live palette](../../../apps/runtime-dashboard/src/features/commandPalette/CommandPalette.tsx#L1) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS10 |
| `feature-composer` | 12 / 3,728 / 4 / 0 | [route](../../../apps/runtime-dashboard/src/features/composer/route.tsx#L17), [local readiness](../../../apps/runtime-dashboard/src/features/composer/routes/LaunchRunPage.tsx#L60) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `wrap_then_strangle`; DS9 |
| `feature-dashboard` | 15 / 2,085 / 1 / 0 | [route](../../../apps/runtime-dashboard/src/features/dashboard/route.tsx#L14) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS7 |
| `feature-evidence` | 16 / 4,850 / 5 / 0 | [route](../../../apps/runtime-dashboard/src/features/evidence/route.tsx#L17), [offline authority action](../../../apps/runtime-dashboard/src/features/evidence/hooks/useQueuedPromotionDecision.ts#L59) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `wrap_then_strangle`; DS9 |
| `feature-export` | 6 / 720 / 1 / 1 | [fixture-only trust vocabulary](../../../apps/runtime-dashboard/src/features/export/social/email-fixtures.ts#L1) | `I/I/O/O/M/I/M/M/M`; `consumer_missing`; experimental | `defer`; DS12 |
| `feature-landing` | 7 / 262 / 0 / 0 | [route](../../../apps/runtime-dashboard/src/features/landing/route.tsx#L4) | `O/O/O/O/I/M/I/M/M`; `verification_missing`; experimental | `admit_after_refactor`; DS11 |
| `feature-layout-empty` | 0 / 0 / 0 / 0 | [placeholder README](../../../apps/runtime-dashboard/src/features/layout/components/README.md#L1) | `M/M/M/M/M/M/M/M/M`; `contract_only`; experimental | `reject`; DS4 |
| `feature-lex` | 7 / 1,257 / 3 / 0 | [page](../../../apps/runtime-dashboard/src/features/lex/routes/LexKnowledgeGraphPage.tsx#L93) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `wrap_then_strangle`; DS10 |
| `feature-onboarding-orphan` | 6 / 652 / 1 / 0 | [local provider](../../../apps/runtime-dashboard/src/features/onboarding/OnboardingProvider.tsx#L14), [barrel](../../../apps/runtime-dashboard/src/features/onboarding/index.ts#L1) | `I/I/I/I/M/I/M/M/M`; `consumer_missing`; experimental | `defer`; DS4 |
| `feature-platform` | 13 / 1,104 / 2 / 2 | [route](../../../apps/runtime-dashboard/src/features/platform/route.tsx#L17) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS6 |
| `feature-runs` | 109 / 24,065 / 24 / 3 | [route tree](../../../apps/runtime-dashboard/src/features/runs/route.tsx#L90), [local publication grammar](../../../apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts#L273) | `M/I/I/M/I/I/I/M/M`; `contract_only`; experimental | `wrap_then_strangle`; DS8 |
| `feature-whatif` | 11 / 1,057 / 0 / 0 | [live workbench mount](../../../apps/runtime-dashboard/src/features/runs/routes/tabs/OverviewTab.tsx#L462) | `I/I/I/I/I/M/I/M/M`; `verification_missing`; experimental | `wrap_then_strangle`; DS8 |

`features/collaboration`, `features/export`, and `features/onboarding` have no
production importer outside their own directories. The command-palette
feature is live even though the separately declared `enableCommandPalette`
flag has no consumer. Empty `features/layout` duplicates the real
`app/layout` ownership and should be removed, not migrated.

## Shared/UI Families: Audited 12 Of 12, Owning 89 Of 89 Components

Family membership follows the public barrels and immediate documented
families. `primitives-root` owns 29 root primitives; `compounds-root` owns
`DataTable`, `JsonPreview`, `LineageGraph`, `MetricCard`, `VirtualList`, and
`VirtualTable`; `operator-diagnostics` owns one root file. Nested families own
3 authored-text, 15 compounds, 10 counterfactual, 3 patterns, 5 quantity, 4
responsive, 5 temporal, and 8 trust-view implementations. Tokens are the
non-component twelfth family.

| Unit ID | Members / paired axe / stories | Evidence | Chain; readiness; maturity | Adoption / owner |
| --- | ---: | --- | --- | --- |
| `ui-primitives-root` | 29 / 29 / 16 | [barrel](../../../apps/runtime-dashboard/src/shared/ui/primitives/index.ts#L1) | `I/O/O/O/I/I/I/M/M`; `verification_missing`; beta | `admit_after_refactor`; DS4 |
| `ui-compounds-root` | 6 / 6 / 3 | [UI README](../../../apps/runtime-dashboard/src/shared/ui/README.md#L11) | `I/O/O/O/I/I/I/M/M`; `verification_missing`; beta | `admit_after_refactor`; DS4 |
| `ui-operator-diagnostics` | 1 / 0 / 0 | [component](../../../apps/runtime-dashboard/src/shared/ui/OperatorDiagnosticPanel.tsx#L1) | `I/O/O/O/I/M/I/M/M`; `verification_missing`; experimental | `admit_after_refactor`; DS4 |
| `ui-authored-text` | 3 / 3 / 1 | [barrel](../../../apps/runtime-dashboard/src/shared/ui/authored-text/index.ts#L1) | `I/O/O/O/I/I/I/M/M`; `verification_missing`; beta | `admit_after_refactor`; DS4 |
| `ui-compounds` | 15 / 15 / 1 | [barrel](../../../apps/runtime-dashboard/src/shared/ui/compounds/index.ts#L1) | `I/O/O/O/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS4 |
| `ui-counterfactual` | 10 / 0 / 0 | [barrel](../../../apps/runtime-dashboard/src/shared/ui/counterfactual/index.ts#L1) | `I/O/O/O/I/M/I/M/M`; `verification_missing`; experimental | `wrap_then_strangle`; DS4 |
| `ui-patterns` | 3 / 3 / 1 | [barrel](../../../apps/runtime-dashboard/src/shared/ui/patterns/index.ts#L1) | `I/O/O/O/I/I/I/M/M`; `verification_missing`; beta | `admit_after_refactor`; DS4 |
| `ui-quantity` | 5 / 2 / 1 | [types](../../../apps/runtime-dashboard/src/shared/ui/quantity/quantity.types.ts#L1) | `M/I/O/M/I/I/I/M/M`; `contract_only`; experimental | `wrap_then_strangle`; DS4 |
| `ui-responsive` | 4 / 4 / 0 | [barrel](../../../apps/runtime-dashboard/src/shared/ui/responsive/index.ts#L1) | `I/O/O/O/I/I/I/M/M`; `verification_missing`; experimental | `admit_after_refactor`; DS4 |
| `ui-temporal` | 5 / 1 / 1 | [barrel](../../../apps/runtime-dashboard/src/shared/ui/temporal/index.ts#L1) | `M/I/O/M/I/M/I/M/M`; `contract_only`; experimental | `wrap_then_strangle`; DS4 |
| `ui-trust-view` | 8 / 0 / 0 | [barrel](../../../apps/runtime-dashboard/src/shared/ui/trust-view/index.ts#L1) | `M/I/O/M/I/M/I/M/M`; `contract_only`; experimental | `wrap_then_strangle`; DS4 |
| `ui-tokens` | 3 token modules / n/a / 2 | [barrel](../../../apps/runtime-dashboard/src/shared/ui/tokens/index.ts#L1) | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `wrap_then_strangle`; DS4 |

No family is `stable`: no manual-AT evidence or cadence exists, state and
story coverage is incomplete, and the paired tests are static axe checks. Of
64 shared/UI a11y files, 63 invoke axe and the 64th is the structural coverage
test. Twenty-six implementations lack paired axe coverage. Its allowlist
admits 25 but omits the new operator diagnostic panel
([allowlist](../../../apps/runtime-dashboard/src/shared/ui/A11yCoverage.a11y.test.tsx#L8),
[set assertion](../../../apps/runtime-dashboard/src/shared/ui/A11yCoverage.a11y.test.tsx#L65)),
so the advertised coverage test is red by construction. A targeted run was
attempted from a clean tree, but Vitest dependencies were unavailable; no
install was attempted and the tree remained clean.

Package extraction is also non-mechanical: 23 shared/UI production files
violate the documented no-API/no-app import boundary
([authoring rule](../../../apps/runtime-dashboard/src/shared/ui/AUTHORING.md#L16)).
They span root, authored-text, counterfactual, quantity, temporal, and
trust-view families; DS4 must sever those imports before package migration.

## API Operations, Statuses, Flags, Transports, Adjacent Surfaces, Evidence

The remaining denominator-complete unit tables are populated in the next
audit checkpoint.

<!-- END AUDIT UNIT INDEX -->

## Named Hotspots

The signing, candidate/authority, authorization, offline/cache, worker,
off-contract, flag/shadow, and telemetry sections are populated after their
full server-counterpart census. Findings are classifications only.

## Seeded Red-First Negatives

The complete P04/P05/P15/P26 negative index is populated after hotspot
reconciliation. No test code belongs to DS1.

## Plan-Impact Appendix

The architect-facing DS3-DS18 re-scope table and exact master-plan corrections
are populated only after all report/ledger unit sets close.
