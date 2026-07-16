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

## API Operations: Audited 89 Of 89

The source denominator is every HTTP method under `paths` in the
[checked-in OpenAPI document](../../../schemas/runtime_api_v1.openapi.json#L1).
Three row profiles define the chain once:

- `SC` (45 surface-consumed): `I/I/O/I/I/I/I/M/M`,
  `semantic_test_missing`, beta, `admit_after_refactor`;
- `HC` (7 hook/client definitions with no production component importer):
  `I/I/O/I/M/I/M/M/M`, `consumer_missing`, experimental, `defer`;
- `NC` (37 operations with no dashboard call): the same chain and readiness
  as `HC`, `defer` until a consuming slice explicitly admits or excludes it.

The reference shell consumes eight operations already in the 45-operation
set, so the union remains 45. A no-call row is not automatically product debt.

| Unit ID | Method and path | Profile | Exact UI/schema evidence |
| --- | --- | --- | --- |
| `api-op-analyze-attractors` | POST `/api/v1/analysis/attractors` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L20064) |
| `api-op-persist-basin-map` | POST `/api/v1/analysis/basin-map` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L20418) |
| `api-op-persist-continuation-branch` | POST `/api/v1/analysis/continuation` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L20646) |
| `api-op-analyze-lyapunov-diagnostics` | POST `/api/v1/analysis/lyapunov` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L20874) |
| `api-op-get-attractor-analysis` | GET `/api/v1/analysis/{analysis_id}` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L21180) |
| `api-op-get-analysis-basin-map` | GET `/api/v1/analysis/{analysis_id}/basin/{basin_id}` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L21440) |
| `api-op-get-analysis-continuation-branch` | GET `/api/v1/analysis/{analysis_id}/branch/{branch_id}` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L21706) |
| `api-op-get-artifact-batch` | POST `/api/v1/artifacts/batch` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L21971) |
| `api-op-get-artifact-manifest` | GET `/api/v1/artifacts/{artifact_id}` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/api/hooks/useArtifactManifest.ts#L9) |
| `api-op-get-artifact-content` | GET `/api/v1/artifacts/{artifact_id}/content` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/api/hooks/useArtifactContent.ts#L16) |
| `api-op-download-artifact-content` | GET `/api/v1/artifacts/{artifact_id}/download` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L22788) |
| `api-op-get-artifact-lineage` | GET `/api/v1/artifacts/{artifact_id}/lineage` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/api/hooks/useArtifactLineage.ts#L9) |
| `api-op-get-artifact-schema` | GET `/api/v1/artifacts/{artifact_id}/schema` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/api/hooks/useArtifactSchema.ts#L9) |
| `api-op-export-bureaucratic-artifact` | GET `/api/v1/artifacts/{packet_id}/export` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L23543) |
| `api-op-render-bureaucratic-artifact` | POST `/api/v1/artifacts/{packet_id}/render` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/api/hooks/useBureaucraticRender.ts#L26) |
| `api-op-get-auth-me` | GET `/api/v1/auth/me` | SC; DS5 | [raw API-owner call](../../../apps/runtime-dashboard/src/api/hooks/useAuthMe.ts#L44) |
| `api-op-estimate-causal-frontier-sae` | POST `/api/v1/control/analytics/sae/causal-frontier` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L24406) |
| `api-op-get-control-capabilities` | GET `/api/v1/control/capabilities` | SC; DS10 | [call](../../../apps/runtime-dashboard/src/api/hooks/useCapabilities.ts#L18) |
| `api-op-list-binding-profiles` | GET `/api/v1/control/data/binding-profiles` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L24977) |
| `api-op-get-cache-status` | GET `/api/v1/control/data/cache` | HC; DS3 | [unused hook](../../../apps/runtime-dashboard/src/api/hooks/useCacheStatus.ts#L11) |
| `api-op-search-data-catalog` | GET `/api/v1/control/data/catalog/search` | SC; DS10 | [call](../../../apps/runtime-dashboard/src/api/hooks/useDataCatalogSearch.ts#L23) |
| `api-op-list-connectors` | GET `/api/v1/control/data/connectors` | SC; DS15 | [call](../../../apps/runtime-dashboard/src/api/hooks/useConnectors.ts#L12) |
| `api-op-discover-data-sources` | POST `/api/v1/control/data/discover` | SC; DS15 | [call](../../../apps/runtime-dashboard/src/api/hooks/useDiscoverDataSources.ts#L16) |
| `api-op-get-data-index-stats` | GET `/api/v1/control/data/index/stats` | SC; DS10 | [call](../../../apps/runtime-dashboard/src/api/hooks/useDataIndexStats.ts#L16) |
| `api-op-ingest-data` | POST `/api/v1/control/data/ingest` | HC; DS15 | [unused hook](../../../apps/runtime-dashboard/src/api/hooks/useIngestData.ts#L13) |
| `api-op-preview-fetch-plan` | POST `/api/v1/control/data/preview` | SC; DS15 | [call](../../../apps/runtime-dashboard/src/api/hooks/usePreviewFetchPlan.ts#L12) |
| `api-op-list-source-profiles` | GET `/api/v1/control/data/profiles` | SC; DS15 | [call](../../../apps/runtime-dashboard/src/api/hooks/useSourceProfiles.ts#L13) |
| `api-op-list-data-promotion-candidates` | GET `/api/v1/control/data/promotion/candidates` | SC; DS9 | [call](../../../apps/runtime-dashboard/src/api/hooks/useDataPromotionCandidates.ts#L18) |
| `api-op-approve-data-promotion` | POST `/api/v1/control/data/promotion/{promotion_id}/approve` | SC; DS9 | [call](../../../apps/runtime-dashboard/src/api/hooks/usePromotionDecision.ts#L39) |
| `api-op-reject-data-promotion` | POST `/api/v1/control/data/promotion/{promotion_id}/reject` | SC; DS9 | [call](../../../apps/runtime-dashboard/src/api/hooks/usePromotionDecision.ts#L63) |
| `api-op-resolve-data-needs` | POST `/api/v1/control/data/resolve` | SC; DS15 | [call](../../../apps/runtime-dashboard/src/api/hooks/useResolveDataNeeds.ts#L15) |
| `api-op-get-packet-decision-validity` | GET `/api/v1/control/decision-packets/{decision_packet_ref}/decision-validity` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L28162) |
| `api-op-publish-decision-validity-event` | POST `/api/v1/control/decision-validity/events` | NC; DS9 | [operation](../../../schemas/runtime_api_v1.openapi.json#L28417) |
| `api-op-get-control-job-status` | GET `/api/v1/control/jobs/{job_id}` | SC; DS14 | [call](../../../apps/runtime-dashboard/src/api/hooks/useControlJobStatus.ts#L14) |
| `api-op-get-lex-graph-stats` | GET `/api/v1/control/lex/graph/stats` | SC; DS10 | [call](../../../apps/runtime-dashboard/src/api/hooks/useLexGraphStats.ts#L18) |
| `api-op-search-lex-graph` | POST `/api/v1/control/lex/search` | SC; DS10 | [call](../../../apps/runtime-dashboard/src/api/hooks/useLexSearch.ts#L13) |
| `api-op-get-lex-pipeline-status` | GET `/api/v1/control/lex/status/{pipeline_id}` | SC; DS10 | [call](../../../apps/runtime-dashboard/src/api/hooks/useLexPipelineStatus.ts#L14) |
| `api-op-trigger-lex-pipeline` | POST `/api/v1/control/lex/trigger` | SC; DS10 | [call](../../../apps/runtime-dashboard/src/api/hooks/useLexTrigger.ts#L12) |
| `api-op-list-llm-profiles` | GET `/api/v1/control/llm/profiles` | SC; DS14 | [call](../../../apps/runtime-dashboard/src/api/hooks/useLlmProfiles.ts#L13) |
| `api-op-list-control-outbox` | GET `/api/v1/control/outbox` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L30113) |
| `api-op-launch-run` | POST `/api/v1/control/runs` | SC; DS9 | [call](../../../apps/runtime-dashboard/src/api/hooks/useLaunchRun.ts#L21) |
| `api-op-launch-nl-run` | POST `/api/v1/control/runs/nl` | SC; DS14 | [call](../../../apps/runtime-dashboard/src/api/hooks/useLaunchNlRun.ts#L24) |
| `api-op-get-run-decision-validity` | GET `/api/v1/control/runs/{run_id}/decision-validity` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L30851) |
| `api-op-evaluate-run-feedback` | POST `/api/v1/control/runs/{run_id}/feedback/evaluate` | NC; DS9 | [operation](../../../schemas/runtime_api_v1.openapi.json#L31106) |
| `api-op-reissue-run` | POST `/api/v1/control/runs/{run_id}/reissue` | NC; DS9 | [operation](../../../schemas/runtime_api_v1.openapi.json#L31359) |
| `api-op-list-control-workers` | GET `/api/v1/control/workers` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L31612) |
| `api-op-get-run-compare` | GET `/api/v1/debug/runs/{left_run_id}/compare/{right_run_id}` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L31858) |
| `api-op-get-run-equilibria` | GET `/api/v1/debug/runs/{run_id}/equilibria` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L32162) |
| `api-op-get-run-errors` | GET `/api/v1/debug/runs/{run_id}/errors` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/api/hooks/useRunErrors.ts#L13) |
| `api-op-get-run-feedback` | GET `/api/v1/debug/runs/{run_id}/feedback` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L32729) |
| `api-op-get-governance-debug` | GET `/api/v1/debug/runs/{run_id}/governance` | SC; DS9 | [call](../../../apps/runtime-dashboard/src/api/hooks/useGovernanceDebug.ts#L13) |
| `api-op-get-node-debug` | GET `/api/v1/debug/runs/{run_id}/nodes/{alias}` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/api/hooks/useNodeDebug.ts#L9) |
| `api-op-analyze-fabric-impact` | POST `/api/v1/fabric/impact` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L33728) |
| `api-op-get-fabric-quality-batch` | POST `/api/v1/fabric/quality/batch` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L34098) |
| `api-op-get-fabric-run-replay` | GET `/api/v1/fabric/runs/{run_id}/replay` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L34456) |
| `api-op-get-fabric-source-scorecards` | GET `/api/v1/fabric/source-scorecards` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L34813) |
| `api-op-get-fabric-trust-batch` | POST `/api/v1/fabric/trust/batch` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L35057) |
| `api-op-runtime-api-health` | GET `/api/v1/health` | SC; DS6 | [call](../../../apps/runtime-dashboard/src/api/hooks/useHealth.ts#L15) |
| `api-op-get-lineage-batch` | POST `/api/v1/lineage/batch` | HC; DS3 | [unused hook](../../../apps/runtime-dashboard/src/shared/ui/quantity/useLineageBatch.ts#L29) |
| `api-op-get-lineage` | GET `/api/v1/lineage/{lineage_id}` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/shared/ui/quantity/useLineage.ts#L20) |
| `api-op-export-lineage-openlineage` | GET `/api/v1/lineage/{lineage_id}/export/openlineage` | SC; DS3 | [dynamic call](../../../apps/runtime-dashboard/src/shared/ui/quantity/useLineage.ts#L51) |
| `api-op-export-lineage-prov` | GET `/api/v1/lineage/{lineage_id}/export/prov` | SC; DS3 | [dynamic call](../../../apps/runtime-dashboard/src/shared/ui/quantity/useLineage.ts#L51) |
| `api-op-compute-mobility-bounds` | POST `/api/v1/mobility/bounds` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L37121) |
| `api-op-estimate-mobility` | POST `/api/v1/mobility/estimate` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L37429) |
| `api-op-get-mobility-report` | GET `/api/v1/mobility/reports/{artifact_id}` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L37826) |
| `api-op-get-mobility-report-bounds` | GET `/api/v1/mobility/reports/{artifact_id}/bounds` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L38102) |
| `api-op-get-mobility-report-diagnostics` | GET `/api/v1/mobility/reports/{artifact_id}/diagnostics` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L38376) |
| `api-op-list-runs` | GET `/api/v1/runs` | SC; DS7 | [call](../../../apps/runtime-dashboard/src/api/hooks/useRuns.ts#L27) |
| `api-op-get-runs-batch` | POST `/api/v1/runs/batch` | NC; DS3 | [operation](../../../schemas/runtime_api_v1.openapi.json#L38975) |
| `api-op-compare-runs` | GET `/api/v1/runs/compare` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/api/hooks/useCompareRuns.ts#L29) |
| `api-op-get-run-details` | GET `/api/v1/runs/{run_id}` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/api/hooks/useRunDetails.ts#L24) |
| `api-op-get-run-agents` | GET `/api/v1/runs/{run_id}/agents` | SC; DS14 | [call](../../../apps/runtime-dashboard/src/api/hooks/useRunAgents.ts#L13) |
| `api-op-get-run-compare-candidates` | GET `/api/v1/runs/{run_id}/compare-candidates` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/api/hooks/useCompareRuns.ts#L56) |
| `api-op-get-run-evidence-context` | GET `/api/v1/runs/{run_id}/evidence-context` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/api/hooks/useRunEvidenceContext.ts#L13) |
| `api-op-get-run-fabric-decision-data` | GET `/api/v1/runs/{run_id}/fabric-decision-data` | HC; DS8 | [unused hook](../../../apps/runtime-dashboard/src/api/hooks/useRunFabricDecisionData.ts#L23) |
| `api-op-get-run-lineage` | GET `/api/v1/runs/{run_id}/lineage` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/api/hooks/useRunLineage.ts#L21) |
| `api-op-get-run-counterfactual-metrics` | GET `/api/v1/runs/{run_id}/metrics` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/api/hooks/useCounterfactualMetrics.ts#L30) |
| `api-op-get-run-nodes` | GET `/api/v1/runs/{run_id}/nodes` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/api/hooks/useRunNodes.ts#L13) |
| `api-op-create-run-production-approval` | POST `/api/v1/runs/{run_id}/production-approval` | NC; DS9 | [operation](../../../schemas/runtime_api_v1.openapi.json#L43867) |
| `api-op-get-run-quantities` | GET `/api/v1/runs/{run_id}/quantities` | HC; DS8 | [unused hook](../../../apps/runtime-dashboard/src/api/hooks/useRunQuantities.ts#L21) |
| `api-op-list-run-scenarios` | GET `/api/v1/runs/{run_id}/scenarios` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/api/hooks/useScenarioCapabilities.ts#L35) |
| `api-op-create-run-scenario` | POST `/api/v1/runs/{run_id}/scenarios` | NC; DS8 | [operation](../../../schemas/runtime_api_v1.openapi.json#L45278) |
| `api-op-get-run-timeline` | GET `/api/v1/runs/{run_id}/timeline` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/api/hooks/useRunTimeline.ts#L21) |
| `api-op-get-run-workflow` | GET `/api/v1/runs/{run_id}/workflow` | SC; DS8 | [call](../../../apps/runtime-dashboard/src/api/hooks/useRunWorkflow.ts#L13) |
| `api-op-get-scenario-manifest` | GET `/api/v1/scenarios/{scenario_id}` | HC; DS8 | [unused hook](../../../apps/runtime-dashboard/src/api/hooks/useScenarioManifest.ts#L28) |
| `api-op-get-scenario-capabilities` | GET `/api/v1/scenarios/{scenario_id}/capabilities` | HC; DS8 | [unused hook](../../../apps/runtime-dashboard/src/api/hooks/useScenarioCapabilities.ts#L62) |
| `api-op-get-temporal-capabilities` | GET `/api/v1/temporal/capabilities` | SC; DS18 | [call](../../../apps/runtime-dashboard/src/shared/ui/temporal/useTemporalRange.ts#L25) |
| `api-op-health` | GET `/health` | NC; DS6 | [operation](../../../schemas/runtime_api_v1.openapi.json#L48156) |
| `api-op-ready` | GET `/ready` | NC; DS6 | [operation](../../../schemas/runtime_api_v1.openapi.json#L48369) |

The dashboard therefore calls 52 operations (45 surfaced + 7 hook-only), not
51: the 51 generated-client operations plus `/auth/me` through the sanctioned
API-owned auth fetch. The reference shell uses eight overlapping operations.
The two consumers use different client homes, a live P06 seam for DS3.

## Hand-Written Fetches: Audited 9 Of 9 Production Calls

`AF` is `I/I/O/M/I/M/I/M/M`, `bridge_missing`, experimental,
`wrap_then_strangle` behind a sanctioned transport. Auth-owned calls retain
`admit_after_refactor`; the public telemetry call is `defer`. The tooling-only
tenth call is recorded but is not a production unit.

| Unit ID | Purpose | Evidence | Profile / owner |
| --- | --- | --- | --- |
| `raw-fetch-auth-refresh` | refresh session | [call](../../../apps/runtime-dashboard/src/app/auth/authSession.ts#L172) | AF; `admit_after_refactor`; DS5 |
| `raw-fetch-auth-initial` | authenticated initial request | [call](../../../apps/runtime-dashboard/src/app/auth/authSession.ts#L279) | AF; `admit_after_refactor`; DS5 |
| `raw-fetch-auth-replay` | replay after refresh | [call](../../../apps/runtime-dashboard/src/app/auth/authSession.ts#L312) | AF; `admit_after_refactor`; DS5 |
| `raw-fetch-flag-manifest` | remote feature manifest | [call](../../../apps/runtime-dashboard/src/app/providers/FeatureFlagProvider.tsx#L68) | AF; `admit_after_refactor`; DS5 |
| `raw-fetch-collab-activity` | phantom activity GET | [call](../../../apps/runtime-dashboard/src/features/collaboration/hooks/useActivityFeed.ts#L16) | `M/M/M/M/M/M/M/M/M`; `producer_missing`; `defer`; DS5 |
| `raw-fetch-collab-comments-get` | phantom comments GET | [call](../../../apps/runtime-dashboard/src/features/collaboration/hooks/useComments.ts#L15) | same; `producer_missing`; `defer`; DS5 |
| `raw-fetch-collab-comment-post` | phantom comment POST | [call](../../../apps/runtime-dashboard/src/features/collaboration/hooks/useComments.ts#L27) | same; `producer_missing`; `defer`; DS5 |
| `raw-fetch-collab-resolve` | phantom resolve POST | [call](../../../apps/runtime-dashboard/src/features/collaboration/hooks/useComments.ts#L47) | same; `producer_missing`; `defer`; DS5 |
| `raw-fetch-telemetry` | beacon fallback POST | [call](../../../apps/runtime-dashboard/src/shared/telemetry/pipeline.ts#L74) | AF; `defer`; DS12 |

The recording script adds one non-production call at
[scripts/record-runtime-contracts.mjs:24](../../../apps/runtime-dashboard/scripts/record-runtime-contracts.mjs#L24).

## UI-Local Status Vocabularies: Audited 47 Of 47

`OP` is an operational/interaction state: `I/I/O/I/I/I/I/M/M`,
`semantic_test_missing`, beta, `admit_after_refactor`. `AU` is a domain or
authority-adjacent local vocabulary: `M/I/O/M/I/I/I/M/M`, `contract_only`,
experimental, `wrap_then_strangle`. `OR` is fixture/orphan-only:
`M/M/M/M/M/I/M/M/M`, `consumer_missing`, experimental, `defer`. DS4 owns all
three profiles and must namespace operational states separately from runtime
authority states.

| Unit ID | Definition | Profile | Evidence |
| --- | --- | --- | --- |
| `status-auth-session` | `AuthSessionStatus` | OP | [definition](../../../apps/runtime-dashboard/src/app/auth/authSession.ts#L12) |
| `status-offline-queue-item` | `OfflineQueueItemStatus` | AU | [definition](../../../apps/runtime-dashboard/src/app/offline/offlineQueueRepository.ts#L8) |
| `status-feature-flag` | `FeatureFlagStatus` | OP | [definition](../../../apps/runtime-dashboard/src/app/providers/FeatureFlagProvider.tsx#L26) |
| `status-runs-live` | `RunsLiveStatus` | OP | [definition](../../../apps/runtime-dashboard/src/app/providers/runsLiveMachine.ts#L1) |
| `status-causal-edge-identification` | `EdgeIdentificationStatus` | AU | [definition](../../../apps/runtime-dashboard/src/features/causal/types.ts#L16) |
| `status-causal-pipeline-stage` | `PipelineStageStatus` | AU | [definition](../../../apps/runtime-dashboard/src/features/causal/types.ts#L22) |
| `status-collaboration-session` | `CollaborationSessionStatus` | OR | [definition](../../../apps/runtime-dashboard/src/features/collaboration/types.ts#L95) |
| `status-health-check` | `HealthCheckStatus` | OP | [definition](../../../apps/runtime-dashboard/src/features/dashboard/components/SystemHealthPulse.tsx#L8) |
| `status-share-trust-fixture` | `ShareTrustStatus` | OR | [definition](../../../apps/runtime-dashboard/src/features/export/social/email-fixtures.ts#L2) |
| `status-comparability-api-alias` | `ComparabilityStatus` | OP | [definition](../../../apps/runtime-dashboard/src/features/runs/compare/compare-types.ts#L15) |
| `status-narrative-chapter` | `ChapterStatus` | OP | [definition](../../../apps/runtime-dashboard/src/features/runs/components/narrative/shared/NarrativeChapter.tsx#L7) |
| `status-dispute-run` | run `DisputeStatus` | AU | [definition](../../../apps/runtime-dashboard/src/features/runs/domain/disputes.ts#L3) |
| `status-publication-argument-node` | `ArgumentNodeStatus` | AU | [definition](../../../apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts#L22) |
| `status-stress-scene` | `StressSceneStatus` | AU | [definition](../../../apps/runtime-dashboard/src/features/runs/domain/scientificDepth.ts#L93) |
| `status-agent-step` | `AgentStepStatus` | AU | [definition](../../../apps/runtime-dashboard/src/shared/lib/domain/agents.ts#L9) |
| `status-agent-performance-budget` | `PerformanceBudgetStatus` | AU | [definition](../../../apps/runtime-dashboard/src/shared/lib/domain/agents.ts#L113) |
| `status-workflow-node` | `WorkflowNodeStatus` | AU | [definition](../../../apps/runtime-dashboard/src/shared/lib/domain/workflow.ts#L9) |
| `status-governance-pass` | `GovernancePassStatus` | AU | [definition](../../../apps/runtime-dashboard/src/shared/ui/compounds/GovernancePassGrid.tsx#L11) |
| `status-quantity-provenance` | `QuantityProvenanceStatus` | AU | [definition](../../../apps/runtime-dashboard/src/shared/ui/quantity/Quantity.tsx#L36) |
| `status-scenario` | `ScenarioStatus` | AU | [definition](../../../apps/runtime-dashboard/src/shared/ui/quantity/quantity.types.ts#L140) |
| `status-verification` | `VerificationStatus` | AU | [definition](../../../apps/runtime-dashboard/src/shared/ui/quantity/quantity.types.ts#L1) |
| `status-dispute-quantity` | quantity `DisputeStatus` | AU | [definition](../../../apps/runtime-dashboard/src/shared/ui/quantity/quantity.types.ts#L8) |
| `status-dispute-trust-view` | trust-view `DisputeStatus` | AU | [definition](../../../apps/runtime-dashboard/src/shared/ui/trust-view/trust-glyphs.ts#L7) |
| `status-inline-promotion-decision` | promotion response literal union | AU | [definition](../../../apps/runtime-dashboard/src/api/hooks/usePromotionDecision.ts#L110) |
| `status-inline-queued-promotion` | queued promotion literal union | AU | [definition](../../../apps/runtime-dashboard/src/features/evidence/hooks/useQueuedPromotionDecision.ts#L16) |
| `status-inline-authz-provider` | authz provider state | OP | [definition](../../../apps/runtime-dashboard/src/app/authz/AuthzProvider.tsx#L21) |
| `status-inline-visual-fixture` | visual fixture state | OR | [definition](../../../apps/runtime-dashboard/src/app/surfaces/visualFixtureHarness.ts#L29) |
| `status-inline-review-indicators` | collaboration indicator state | AU | [definition](../../../apps/runtime-dashboard/src/app/realtime/ReviewCollaborationIndicators.tsx#L36) |
| `status-inline-review-surface` | review transport state | AU | [definition](../../../apps/runtime-dashboard/src/app/realtime/useReviewCollaborationSurface.ts#L28) |
| `status-inline-bureaucratic-block` | bureaucratic block status | AU | [definition](../../../apps/runtime-dashboard/src/features/artifacts/bureaucratic/ast/bureaucratic-document-ast.ts#L41) |
| `status-inline-bureaucratic-section` | bureaucratic section status | AU | [definition](../../../apps/runtime-dashboard/src/features/artifacts/bureaucratic/ast/bureaucratic-document-ast.ts#L80) |
| `status-inline-data-freshness` | freshness matrix state | AU | [definition](../../../apps/runtime-dashboard/src/features/dashboard/components/DataFreshnessMatrix.tsx#L13) |
| `status-inline-compliance-badge` | compliance badge state | AU | [definition](../../../apps/runtime-dashboard/src/features/platform/ComplianceBadge.tsx#L19) |
| `status-inline-choreography-stage` | run stage state | AU | [definition](../../../apps/runtime-dashboard/src/features/runs/domain/runChoreography.ts#L8) |
| `status-inline-choreography-transition` | run transition state | AU | [definition](../../../apps/runtime-dashboard/src/features/runs/domain/runChoreography.ts#L21) |
| `status-inline-publication-claim` | publication claim state | AU | [definition](../../../apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts#L131) |
| `status-inline-publication-ground` | publication ground state | AU | [definition](../../../apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts#L136) |
| `status-inline-readiness-evidence` | public-sector evidence state | AU | [definition](../../../apps/runtime-dashboard/src/features/runs/domain/publicSectorReadiness.ts#L119) |
| `status-inline-readiness-gate` | public-sector gate state | AU | [definition](../../../apps/runtime-dashboard/src/features/runs/domain/publicSectorReadiness.ts#L150) |
| `status-inline-readiness-review` | public-sector review state | AU | [definition](../../../apps/runtime-dashboard/src/features/runs/domain/publicSectorReadiness.ts#L157) |
| `status-inline-run-narrative` | narrative view state | AU | [definition](../../../apps/runtime-dashboard/src/features/runs/components/narrative/RunNarrativeView.tsx#L27) |
| `status-inline-governance-comparison-left` | comparison state A | AU | [definition](../../../apps/runtime-dashboard/src/features/runs/components/GovernanceComparison.tsx#L13) |
| `status-inline-governance-comparison-right` | comparison state B | AU | [definition](../../../apps/runtime-dashboard/src/features/runs/components/GovernanceComparison.tsx#L14) |
| `status-inline-small-multiples` | chart state | OP | [definition](../../../apps/runtime-dashboard/src/shared/charts/SmallMultiples.tsx#L12) |
| `status-inline-route-loader` | loader event state | OP | [definition](../../../apps/runtime-dashboard/src/shared/telemetry/routeLoaderEvents.ts#L5) |
| `status-inline-explainability` | explainability card state | AU | [definition](../../../apps/runtime-dashboard/src/shared/ui/compounds/ExplainabilityCard.tsx#L18) |
| `status-inline-counterfactual-badge` | counterfactual badge state | AU | [definition](../../../apps/runtime-dashboard/src/shared/ui/counterfactual/CounterfactualBadge.tsx#L11) |

The three `DisputeStatus` definitions form two vocabularies: run uses
`open|under_review|resolved`; quantity and trust-view independently duplicate
`none|disputed|under_review|resolved`. Other drift includes `warning` versus
`warn`, `pass` versus `ok`, and `block` versus `fail`. These are DS4
retirement inputs, not candidates for a fourth translation layer.

## Feature Flags: Audited 13 Of 13 Paths

`LF` is a live rollout flag: `I/I/I/I/I/M/O/M/M`,
`verification_missing`, beta, `admit_after_refactor`. `MF` is declared but has
no read: the same chain with `consumer: M`, `consumer_missing`, experimental,
`defer` pending wire-or-retire. `AF` is the auth-derived pseudo-flag:
`M/I/I/I/I/M/O/M/M`, `contract_only`, `wrap_then_strangle`. DS5 owns all.

| Unit ID | Flag and consumer | Profile | Evidence |
| --- | --- | --- | --- |
| `flag-enable-atlas-v2` | header/sidebar/mobile/Clerk chrome | LF | [declaration](../../../apps/runtime-dashboard/src/shared/lib/featureFlags.ts#L3), [consumer](../../../apps/runtime-dashboard/src/app/layout/Header.tsx#L44) |
| `flag-enable-clerk-mode` | interface-mode provider | LF | [declaration](../../../apps/runtime-dashboard/src/shared/lib/featureFlags.ts#L4), [consumer](../../../apps/runtime-dashboard/src/app/providers/InterfaceModeProvider.tsx#L43) |
| `flag-enable-dark-mode` | theme provider | LF | [declaration](../../../apps/runtime-dashboard/src/shared/lib/featureFlags.ts#L5), [consumer](../../../apps/runtime-dashboard/src/app/providers/ThemeProvider.tsx#L91) |
| `flag-enable-lex-knowledge` | workspace/boundary/nav/palette | LF | [declaration](../../../apps/runtime-dashboard/src/shared/lib/featureFlags.ts#L6), [consumer](../../../apps/runtime-dashboard/src/app/workspaces.ts#L147) |
| `flag-enable-narrative-view` | decision-card view | LF | [declaration](../../../apps/runtime-dashboard/src/shared/lib/featureFlags.ts#L7), [consumer](../../../apps/runtime-dashboard/src/features/artifacts/components/DecisionCardView.tsx#L148) |
| `flag-enable-platform-health` | platform workspace | LF | [declaration](../../../apps/runtime-dashboard/src/shared/lib/featureFlags.ts#L8), [consumer](../../../apps/runtime-dashboard/src/app/workspaces.ts#L161) |
| `flag-enable-runs-workspace` | runs workspace | LF | [declaration](../../../apps/runtime-dashboard/src/shared/lib/featureFlags.ts#L9), [consumer](../../../apps/runtime-dashboard/src/app/workspaces.ts#L116) |
| `flag-enable-scenario-composer` | composer workspace | LF | [declaration](../../../apps/runtime-dashboard/src/shared/lib/featureFlags.ts#L10), [consumer](../../../apps/runtime-dashboard/src/app/workspaces.ts#L102) |
| `flag-enable-causal-graph` | no production read | MF | [declaration](../../../apps/runtime-dashboard/src/shared/lib/featureFlags.ts#L11) |
| `flag-enable-collaboration` | no production read | MF | [declaration](../../../apps/runtime-dashboard/src/shared/lib/featureFlags.ts#L12) |
| `flag-enable-command-palette` | no production read; feature itself is live | MF | [declaration](../../../apps/runtime-dashboard/src/shared/lib/featureFlags.ts#L13) |
| `flag-enable-what-if-analysis` | no production read; workbench itself is live | MF | [declaration](../../../apps/runtime-dashboard/src/shared/lib/featureFlags.ts#L14) |
| `flag-auth-review-collaboration` | `/auth/me` permission-derived `enableReviewCollaboration` | AF | [fallback](../../../apps/runtime-dashboard/src/api/hooks/useAuthMe.ts#L13), [consumer](../../../apps/runtime-dashboard/src/app/authz/AuthzProvider.tsx#L78), [server derivation](../../../src/polisyos/runtime/http/routes/auth.py#L135) |

All 12 canonical defaults are true. Precedence is defaults/environment, build
manifest, `window.__RUNTIME_DASHBOARD_FLAGS__`, cached/remote manifest, then
provider props ([merge logic](../../../apps/runtime-dashboard/src/shared/lib/featureFlags.ts#L168),
[provider fetch](../../../apps/runtime-dashboard/src/app/providers/FeatureFlagProvider.tsx#L46)).
The loose envelope ignores unknown keys instead of failing closed. The auth
value is permission projection, not a rollout source, and D5's one-registry
implementation must keep exposure separate from authorization.

## Transports, Cache, Workers, And Client Derivations

| Unit ID | Scope | Chain; readiness; maturity | Adoption / owner / evidence |
| --- | --- | --- | --- |
| `transport-openapi-dashboard` | `openapi-fetch` over generated `paths` | `I/I/O/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS3; [client](../../../apps/runtime-dashboard/src/api/client.ts#L1) |
| `transport-openapi-reference-shell` | generated package class | `I/I/O/I/I/M/I/M/M`; `verification_missing`; experimental | `admit_after_refactor`; DS3; [import](../../../apps/runtime-reference-shell/app.js#L1) |
| `transport-rest-collaboration` | four phantom REST method/path pairs | `M/M/M/M/M/I/M/M/M`; `producer_missing`; deprecated | `defer` build-or-remove; DS5; [comments](../../../apps/runtime-dashboard/src/features/collaboration/hooks/useComments.ts#L14) |
| `transport-sse-runs-global` | off-contract global run stream | `M/I/O/I/I/I/I/M/M`; `contract_only`; beta | `admit_after_refactor`; DS3; [client](../../../apps/runtime-dashboard/src/app/realtime/sseTransport.ts#L13), [server](../../../src/polisyos/runtime/http/routes/runs.py#L813) |
| `transport-sse-run-detail` | off-contract per-run stream | `M/I/O/I/I/M/I/M/M`; `contract_only`; experimental | `admit_after_refactor`; DS3; [client](../../../apps/runtime-dashboard/src/app/realtime/sseTransport.ts#L19), [server](../../../src/polisyos/runtime/http/routes/runs.py#L996) |
| `transport-ws-review` | three review channels | `M/I/O/M/I/M/I/M/M`; `bridge_missing`; experimental | `admit_after_refactor`; DS3/DS5; [client](../../../apps/runtime-dashboard/src/app/realtime/websocketTransport.ts#L27), [server](../../../src/polisyos/runtime/http/routes/review.py#L233) |
| `transport-ws-collaboration` | four `/collaboration/live` channels, no server | `M/M/M/M/M/M/M/M/M`; `producer_missing`; deprecated | `defer` build-or-remove; DS5; [client](../../../apps/runtime-dashboard/src/app/realtime/websocketTransport.ts#L15) |
| `worker-data-transform` | sort/filter/client aggregation | `I/I/O/I/M/I/O/M/M`; `consumer_missing`; experimental | `admit_after_refactor` for presentation only; DS9; [worker](../../../apps/runtime-dashboard/src/workers/dataTransform.worker.ts#L13) |
| `worker-dag-layout` | coordinates only | `I/I/O/I/M/I/O/M/M`; `consumer_missing`; experimental | `admit_as_is` once wired; DS4; [worker](../../../apps/runtime-dashboard/src/workers/dagLayout.worker.ts#L41) |
| `worker-json-parse` | JSON parse only | `I/I/O/I/M/I/O/M/M`; `consumer_missing`; experimental | `admit_as_is` behind schema validation; DS5; [worker](../../../apps/runtime-dashboard/src/workers/jsonParse.worker.ts#L20) |
| `cache-service-worker-static` | precache + SPA navigation, API denied | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS5; [rules](../../../apps/runtime-dashboard/src/sw.ts#L16) |
| `offline-queue-promotion-decision` | approve/reject authority action | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; experimental | **`reject`**; DS5; [queue contract](../../../apps/runtime-dashboard/src/app/offline/offlineQueueRepository.ts#L7), [optimism](../../../apps/runtime-dashboard/src/features/evidence/hooks/useQueuedPromotionDecision.ts#L59) |
| `offline-draft-composer` | IndexedDB composer drafts | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS5; [record](../../../apps/runtime-dashboard/src/features/composer/state/composerDraftRepository.ts#L11) |
| `cache-query-memory` | TanStack in-memory query cache | `I/I/I/I/I/M/I/M/M`; `verification_missing`; beta | `admit_after_refactor`; DS5; [defaults](../../../apps/runtime-dashboard/src/api/queryClient.ts#L5) |
| `cache-local-storage-state` | UI preferences and authority-adjacent records | `M/I/I/I/I/M/I/M/M`; `contract_only`; experimental | `wrap_then_strangle`; DS5; [representative store](../../../apps/runtime-dashboard/src/app/state/usePreferencesStore.ts#L15) |
| `cache-clerk-sessions` | up to 50 local LLM/system conversations | `M/I/I/I/I/M/I/M/M`; `contract_only`; experimental | `wrap_then_strangle`; DS14; [store](../../../apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts#L21) |
| `cache-whatif-scenarios` | local projected metrics/scenarios | `M/I/I/I/I/M/I/M/M`; `contract_only`; experimental | `wrap_then_strangle`; DS8; [store](../../../apps/runtime-dashboard/src/features/whatif/state/useWhatIfStore.ts#L6) |
| `cache-causal-drafts` | local graph/run draft | `M/I/I/I/I/M/I/M/M`; `contract_only`; experimental | `wrap_then_strangle`; DS8; [store](../../../apps/runtime-dashboard/src/features/runs/routes/tabs/CausalTab.tsx#L245) |
| `cache-local-disputes` | per-run local dispute records | `M/I/I/I/I/M/I/M/M`; `contract_only`; experimental | `wrap_then_strangle`; DS9; [store](../../../apps/runtime-dashboard/src/features/runs/domain/disputes.ts#L36) |
| `cache-review-attention` | per-run review attention | `M/I/I/I/I/M/I/M/M`; `contract_only`; experimental | `wrap_then_strangle`; DS9; [store](../../../apps/runtime-dashboard/src/features/runs/domain/publicSectorReadiness.ts#L632) |
| `cache-operator-craft` | thresholds, annotations, wallet, onboarding | `M/I/I/I/I/M/I/M/M`; `contract_only`; experimental | `wrap_then_strangle`; DS9; [keys](../../../apps/runtime-dashboard/src/features/runs/domain/operatorCraft.ts#L11) |
| `transport-telemetry-beacon` | configured beacon/fetch destination | `M/I/O/I/I/M/M/M/M`; `surface_missing`; experimental | `defer`; DS12; [payload and egress](../../../apps/runtime-dashboard/src/shared/telemetry/pipeline.ts#L10) |
| `transport-sentry` | production DSN error telemetry | `I/I/O/I/I/M/I/M/M`; `verification_missing`; beta | `admit_after_refactor`; DS12; [config](../../../apps/runtime-dashboard/src/shared/telemetry/sentry.ts#L11) |
| `derivation-projection-fail-closed` | client normalizes publication projection | `M/I/O/M/I/I/I/M/M`; `contract_only`; experimental | `wrap_then_strangle`; DS4; [derivation](../../../apps/runtime-dashboard/src/shared/lib/domain/projectionFailClosed.ts#L1) |
| `derivation-browser-signature` | public salted FNV hash and verifier | `M/I/I/M/I/I/I/M/M`; `contract_only`; experimental | **`reject`**; DS12; [signature](../../../apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts#L1355) |
| `derivation-causal-effects` | multiplies/sums local edge estimates | `M/I/I/M/I/M/I/M/M`; `contract_only`; experimental | `wrap_then_strangle`; DS8; [calculation](../../../apps/runtime-dashboard/src/features/runs/routes/tabs/CausalTab.tsx#L86) |
| `derivation-composer-readiness` | local 18-96 readiness score | `M/I/O/M/I/I/I/M/M`; `contract_only`; experimental | **`reject`**; DS9; [score](../../../apps/runtime-dashboard/src/features/composer/routes/LaunchRunPage.tsx#L60) |
| `derivation-whatif-validation` | empty-warning means validation-ready | `M/I/O/M/I/M/I/M/M`; `contract_only`; experimental | `wrap_then_strangle`; DS8; [rule](../../../apps/runtime-dashboard/src/features/whatif/ScenarioValidationPanel.tsx#L13) |

The three worker modules have zero runtime `new Worker` consumers; the generic
hook is test-only. The service worker precaches build assets and navigation,
explicitly denying `/api/`, `/health`, and `/ready`; it does not cache API
responses. IndexedDB has exactly two stores: composer drafts and the promotion
queue. None of the authority-looking localStorage keys is tenant+user scoped,
expiring, epoch-bound, or server-revalidated.

The review WS server requires bearer authentication or fixture fallback, but
the browser constructor cannot set an Authorization header and supplies no
other credential in the URL. With fixture identity disabled, production
connectivity is therefore a bridge risk unless an undocumented proxy injects
credentials. Collaboration WS and REST are absent server-side; because the
entire feature is orphaned, current live UX does not call them, and DS5 should
decide remove-versus-build before creating producers.

## Adjacent And Non-Web Touchpoints

| Unit ID | Existence check | Chain; readiness; maturity | Adoption / owner / evidence |
| --- | --- | --- | --- |
| `adjacent-cli-styleguide` | formatters/tokens/tests; no production consumer | `I/I/I/I/M/I/O/M/M`; `consumer_missing`; beta | `wrap_then_strangle`; DS4; [package export](../../../packages/cli/package.json#L12) |
| `adjacent-print-export` | print, PNG, CSV/JSON, server bureaucratic render | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS3/DS8; [utility](../../../apps/runtime-dashboard/src/shared/export/printExport.ts#L15) |
| `adjacent-email-og` | fixtures/story/unit test, no product consumer | `I/I/O/O/M/I/M/M/M`; `consumer_missing`; experimental | `defer`, email remains out of scope; DS12; [fixture](../../../apps/runtime-dashboard/src/features/export/social/email-fixtures.ts#L1) |

DOCX is not actually downloadable: the source object is built while the
visible control is disabled
([button](../../../apps/runtime-dashboard/src/features/artifacts/bureaucratic/BureaucraticArtifactView.tsx#L112)).
Five A4 print baselines and one run-deck export baseline exist. These checks
preserve D6's assignments; they do not admit a new surface.

## Test, Story, Accessibility, And E2E Estate

| Unit ID | What exists / proves | Chain; readiness; maturity | Adoption / owner / evidence |
| --- | --- | --- | --- |
| `evidence-unit-tests` | 231 `.test` plus 3 authored source specs; structural/unit claims | `I/I/I/I/I/I/O/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS6; [example API tests](../../../apps/runtime-dashboard/src/api/hooks/runQueries.test.tsx#L1) |
| `evidence-stories` | 44 stories; only four contain `play` interactions | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS6; [discovery](../../../apps/runtime-dashboard/.storybook/main.ts#L7) |
| `evidence-component-a11y` | 63 axe fixtures; structural gate currently red | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS6; [gate](../../../apps/runtime-dashboard/src/shared/ui/A11yCoverage.a11y.test.tsx#L65) |
| `evidence-browser-a11y` | route axe, keyboard, color, DOM screen-reader snapshots | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS6; [route suite](../../../apps/runtime-dashboard/e2e/a11y/routes.a11y.spec.ts#L38) |
| `evidence-e2e-journeys` | 12 files / 23 Chromium fixture cases | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS6; [journey directory](../../../apps/runtime-dashboard/e2e/journeys/run-flow.spec.ts#L1) |
| `evidence-visual` | 15 cases / 16 baselines; pixel stability only | `I/I/I/I/I/I/I/M/M`; `semantic_test_missing`; beta | `admit_after_refactor`; DS6; [visual spec](../../../apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts#L1) |
| `evidence-manual-at` | no NVDA/VoiceOver/JAWS/TalkBack record found | `I/M/M/M/M/M/M/M/M`; `producer_missing`; experimental | `defer` until evidence workflow; DS6; [constitution bar](../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md#accessibility) |

Component a11y sampling was limited to uniform harness proof: ordered first,
median, last, and the structural outlier were inspected, while membership and
existence were counted exhaustively. The inference is only that 63 files call
the same axe harness; it is not keyboard, APG, manual-AT, or semantic proof.
The screen-reader snapshots are DOM-derived, not real assistive technology.

<!-- END AUDIT UNIT INDEX -->

## Coverage And Verdict Distribution

The report index contains 261 unique units: 32 dashboard route objects, 4
reference-shell views, 17 feature modules, 12 UI families, 89 API operations,
9 raw-fetch sites, 47 local status definitions, 13 flag paths, 28
transport/cache/offline/worker/derivation units, 3 adjacent surfaces, and 7
evidence-estate units. The machine ledger contains the same 261 IDs with no
duplicates or set differences.

| Readiness state | Units | Meaning in this audit |
| --- | ---: | --- |
| `contract_only` | 61 | local or off-contract vocabulary/semantics owns the boundary |
| `producer_missing` | 7 | UI/client expectation has no admitted server producer |
| `bridge_missing` | 6 | producer or local behavior bypasses the governed transport/orchestration waist |
| `consumer_missing` | 59 | operation/hook/flag/worker/component family has no production surface reader |
| `verification_missing` | 29 | visible or operational chain lacks risk-proportionate evidence |
| `surface_missing` | 1 | public telemetry posture has no governed audience surface |
| `semantic_test_missing` | 93 | structural behavior exists without the necessary negative/semantic proof |
| `implemented` | 5 | only the five narrow legacy redirects; no broader maturity implication |

Adoption verdicts are 3 `admit_as_is`, 114 `admit_after_refactor`, 74
`wrap_then_strangle`, 6 `reject`, and 64 `defer`. Maturity is 109 beta, 142
experimental, 10 deprecated, and **zero stable**. This distribution is
intentionally dominated by incomplete-chain states; rendering and test count
were not rounded up.

## Named Hotspots

### Public Decision URL: Browser-Forgeable, Blast Radius Bounded But Live

`/public/decisions/:signedId` is not a signature chain. The constant salt is
public ([source](../../../apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts#L273));
`stableHash` is 32-bit FNV-1a
([implementation](../../../apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts#L451));
the signature is `sig:` plus that hash over salt + JSON
([builder](../../../apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts#L1355)).
The payload and signature are base64url-encoded into the URL
([encoder](../../../apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts#L1381)),
and the browser recomputes the same public algorithm
([verifier](../../../apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts#L1395)).
The structural validator checks shape/presence but does not recompute the
packet hash ([validation](../../../apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts#L1437)).
An attacker can therefore author arbitrary claims and packet hash, compute the
known FNV value, and obtain `valid=true`.

The unauthenticated viewer calls only that browser verifier
([load](../../../apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.tsx#L9))
and renders `Verified`
([badge](../../../apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.tsx#L26));
the route sits before the protected application frame
([top-level order](../../../apps/runtime-dashboard/src/app/routes/routes.tsx#L185)).
The packet itself synthesizes a public headline and `certified` / “Published
grounds” claims
([copy and states](../../../apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts#L578))
from run-detail UI projections, then computes a second 32-bit packet hash
([assembly](../../../apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts#L1259)).

Blast radius is exact:

- three builders exist: Publication Readiness
  ([builder](../../../apps/runtime-dashboard/src/features/runs/components/PublicationReadinessPanel.tsx#L17)),
  Operator Craft
  ([builder](../../../apps/runtime-dashboard/src/features/runs/components/OperatorCraftPanel.tsx#L80)),
  and Ambient Telemetry
  ([builder](../../../apps/runtime-dashboard/src/features/runs/components/AmbientTelemetryHud.tsx#L42));
- all three mount in every run-detail layout
  ([mounts](../../../apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx#L336));
- exactly one clickable URL producer exists
  ([link](../../../apps/runtime-dashboard/src/features/runs/components/PublicationPacketPanel.tsx#L102));
- no HTTP public-record producer, verifier, or persistence route matched the
  URL in the 89-operation/server census, so no server-published artifact
  depends on it;
- browser-local Operator Craft does retain the packet hash and signed ID
  ([snapshot fields](../../../apps/runtime-dashboard/src/features/runs/domain/operatorCraft.ts#L45)),
  spreading the projection through annotations/wallet state;
- the private-data check is only a keyword scan
  ([implementation](../../../apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts#L1462))
  and is invoked only by its unit test, not the URL builder.

Verdict: P05/P15/P26, `contract_only`, **`reject` and replace**. DS12 must
strangle the mechanism onto a server-keyed, persisted, auditable record; no
hash-hardening of this format can establish signer identity or record
existence.

### Candidate And Authority Laundering: Five Named Surfaces

| Surface | Current producer/bridge and authority slot at risk | Verdict and owner |
| --- | --- | --- |
| Causal | The tab calls extraction a stub ([comment](../../../apps/runtime-dashboard/src/features/runs/routes/tabs/CausalTab.tsx#L51)), blind-casts a hypothetical `run.artifacts[].payload` ([cast](../../../apps/runtime-dashboard/src/features/runs/routes/tabs/CausalTab.tsx#L145)) even though the parsed run contract exposes `root_artifacts`, then falls back to a local draft/scaffold ([selection](../../../apps/runtime-dashboard/src/features/runs/routes/tabs/CausalTab.tsx#L382)). It classifies paths and multiplies edge estimates client-side ([derivation](../../../apps/runtime-dashboard/src/features/runs/routes/tabs/CausalTab.tsx#L86)); the Path Analysis panel presents direct/indirect/total effect decomposition ([render](../../../apps/runtime-dashboard/src/features/causal/panels/PathAnalysisPanel.tsx#L56)). One top badge says draft versus artifact, but inner identified/effect slots retain authority dress. | Active P05/P04; future P15 if the blind cast becomes populated. `wrap_then_strangle`; DS4/DS8. |
| What-if | The live Scenario Workbench mounts unconditionally in Overview ([mount](../../../apps/runtime-dashboard/src/features/runs/routes/tabs/OverviewTab.tsx#L462)). “Validation ready” is computed solely from empty stale/unsupported arrays ([rule](../../../apps/runtime-dashboard/src/features/whatif/ScenarioValidationPanel.tsx#L13)), ignoring lifecycle status, limitations, constraints, lineage, and authority fields carried by the API. The older local WhatIf panel is latent unless legacy parameters are supplied. | Active P05/P04; `wrap_then_strangle`; DS4/DS8. Strangle the latent panel rather than migrate it. |
| Lex | Users can choose an arbitrary LLM model and trigger the pipeline ([launch fields](../../../apps/runtime-dashboard/src/features/lex/routes/LexKnowledgeGraphPage.tsx#L93)). Results render/export/share subject/predicate/object as facts and obligation/prohibition/permission/definition badges with scalar confidence ([table](../../../apps/runtime-dashboard/src/features/lex/routes/LexKnowledgeGraphPage.tsx#L590)), but no candidate, grounding, hallucination, temporal, or frontier state. The server search DTO drops richer upstream truth, including `search_candidate`, missing-quote grounding, hallucination, quality, jurisdiction, and temporal fields ([DTO](../../../src/polisyos/core/contracts/control.py#L1388), [rich source type](../../../src/polisyos/lex/knowledge/types.py#L184)). | Strongest active P15/P05/P04; `wrap_then_strangle`; DS4/DS10. Extend the truth projection rather than add UI-only warnings. |
| Composer | A local formula gives more “readiness” for more visible capabilities, LLM profiles, and parallel models ([formula](../../../apps/runtime-dashboard/src/features/composer/routes/LaunchRunPage.tsx#L60)); local thresholds turn 18–96 into Ready/Pending/Blocked ([thresholds](../../../apps/runtime-dashboard/src/features/composer/routes/LaunchRunPage.tsx#L105)) and render a governance status/ring ([surface](../../../apps/runtime-dashboard/src/features/composer/routes/LaunchRunPage.tsx#L628)). Capability intent is locally labeled `verified`; there is no readiness producer or evidence artifact. | Active P05/P04/P15; `reject` the score, preserve the launch form; DS4/DS9. |
| Clerk | The live hook launches NL runs with hard-coded preflight/auto-materialization and consumes only SSE status/finished time ([hook](../../../apps/runtime-dashboard/src/features/clerk/hooks/useClerkNlRun.ts#L24)). No live producer fills structured text. The local persisted store nonetheless defines verdict, confidence, key factors, sources, and diff ([contract](../../../apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts#L21)); renderers dress these as a verdict/confidence card ([surface](../../../apps/runtime-dashboard/src/features/clerk/components/ClerkStructuredResponse.tsx#L118)) and local accept/reject/edit decisions ([diff](../../../apps/runtime-dashboard/src/features/clerk/components/AIDiffView.tsx#L140)). | Presently `producer_missing`, not an active LLM-text leak; high-risk dormant P15 substrate. `wrap_then_strangle`; DS14 rebinds the shell to typed candidates and removes dormant authority semantics. |

### Authorization: Audited 29 Of 29 Unsafe-Method Operations

The runtime schema contains 29 POST operations and zero PUT/PATCH/DELETE.
Every one was traced to its handler and UI counterpart. None declares a
per-route action permission, role dependency, or MFA/step-up dependency.
Global path/role OPA, when enabled, is not an action authorization substitute;
selected handlers additionally enforce tenant ownership.

The systemic boundary is weaker than the route count suggests:

- runtime app security middleware defaults off
  ([constructor](../../../src/polisyos/runtime/http/app.py#L75)); with it off,
  optional fixture identity is the only identity layer
  ([wiring](../../../src/polisyos/runtime/http/app.py#L182));
- fixture middleware grants a fixed analyst scope to every non-public request
  ([middleware](../../../src/polisyos/runtime/http/dev_identity_middleware.py#L31)),
  while the fixture security principal has `mfa_verified=True`
  ([principal](../../../src/polisyos/runtime/http/security.py#L50)); a local
  production canary explicitly enables this combination, so reach is not
  test-only;
- OPA reads `request.state.authz_resource` before the handler
  ([read](../../../src/polisyos/runtime/http/authz_middleware.py#L205)), but
  handlers set their resource inside the handler, too late to affect that
  decision; the policy therefore sees a generic same-tenant HTTP resource;
- Rego is coarse path/role policy, and its MFA paths are `/gates/*/decide`,
  `/policies/*/publish`, and `/admin/*`, none of the 29 operations
  ([policy](../../../ops/policy/policies/role_access.rego#L7));
- `/auth/me` defines 12 action-like keys while the client defines 15; exact
  client-only delta is `collaboration.comment`, `collaboration.share`, and
  `collaboration.view`
  ([client keys](../../../apps/runtime-dashboard/src/app/authz/permissions.ts#L4),
  [server keys](../../../src/polisyos/runtime/http/routes/auth.py#L34)); OPA
  consumes none of these keys;
- the client fails open for presentation: the placeholder analyst has 11
  permissions and MFA true
  ([fallback](../../../apps/runtime-dashboard/src/api/hooks/useAuthMe.ts#L13)),
  and AuthzProvider uses it while loading or on error
  ([provider](../../../apps/runtime-dashboard/src/app/authz/AuthzProvider.tsx#L27)).

`T` below means the handler checks an owned run/artifact; `scope` means it only
passes the current request tenant into a new operation. Every row has action
permission = none and step-up = none.

| # | POST operation | Handler tenant check | Live/client posture and exact gap |
| ---: | --- | --- | --- |
| 1 | `/api/v1/analysis/attractors` | scope; [handler](../../../src/polisyos/runtime/http/routes/analysis.py#L52) | no UI; optional persistence has no action permission |
| 2 | `/api/v1/analysis/lyapunov` | scope; [handler](../../../src/polisyos/runtime/http/routes/analysis.py#L64) | no UI; optional persistence has no action permission |
| 3 | `/api/v1/analysis/basin-map` | scope; [handler](../../../src/polisyos/runtime/http/routes/analysis.py#L77) | no UI; persists without action permission |
| 4 | `/api/v1/analysis/continuation` | scope; [handler](../../../src/polisyos/runtime/http/routes/analysis.py#L104) | no UI; persists without action permission |
| 5 | `/api/v1/artifacts/batch` | T each artifact; [handler](../../../src/polisyos/runtime/http/routes/artifacts.py#L67) | read-by-POST; no action permission |
| 6 | `/api/v1/artifacts/{packet_id}/render` | T artifact; [handler](../../../src/polisyos/runtime/http/routes/artifacts.py#L403) | active typed render in ordinary run view; no render/export action permission |
| 7 | `/api/v1/control/runs` | scope; [handler](../../../src/polisyos/runtime/http/routes/control.py#L108) | Composer is presentation-gated `runs.launch`; handler does not enforce it |
| 8 | `/api/v1/control/runs/{run_id}/feedback/evaluate` | T run; [handler](../../../src/polisyos/runtime/http/routes/control.py#L139) | no UI; persists monitoring/report without action permission |
| 9 | `/api/v1/control/runs/nl` | scope; [handler](../../../src/polisyos/runtime/http/routes/control.py#L184) | Clerk directly launches ([call](../../../apps/runtime-dashboard/src/features/clerk/hooks/useClerkNlRun.ts#L24)) although command-center visibility requires only `dashboard.view` |
| 10 | `/api/v1/control/runs/{run_id}/reissue` | T run; [handler](../../../src/polisyos/runtime/http/routes/control.py#L208) | no UI; human-gated durable reissue has neither action permission nor step-up |
| 11 | `/api/v1/control/decision-validity/events` | scope; [handler](../../../src/polisyos/runtime/http/routes/control.py#L324) | no packet/entity tenant binding; durable invalidation/outbox event, no step-up |
| 12 | `/api/v1/control/data/ingest` | scope; [handler](../../../src/polisyos/runtime/http/routes/control.py#L403) | hook-only; connector fetch/persistence lacks acquisition permission/step-up |
| 13 | `/api/v1/control/data/resolve` | scope; [handler](../../../src/polisyos/runtime/http/routes/control.py#L422) | Data Intelligence uses only presentation `evidence.review` |
| 14 | `/api/v1/control/data/discover` | scope; [handler](../../../src/polisyos/runtime/http/routes/control.py#L441) | external discovery uses only presentation `evidence.review` |
| 15 | `/api/v1/control/data/preview` | scope; [handler](../../../src/polisyos/runtime/http/routes/control.py#L460) | context auto-preview mutates before guarded click handlers ([call](../../../apps/runtime-dashboard/src/features/evidence/components/DataIntelligencePanel.tsx#L212)) |
| 16 | `/api/v1/control/analytics/sae/causal-frontier` | scope; [handler](../../../src/polisyos/runtime/http/routes/control.py#L479) | no UI; writes output/optional CAS without action permission |
| 17 | `/api/v1/control/data/promotion/{id}/approve` | scope; [handler](../../../src/polisyos/runtime/http/routes/control.py#L586) | UI visibility only; handler not rechecked and offline replay bypasses live revalidation |
| 18 | `/api/v1/control/data/promotion/{id}/reject` | scope; [handler](../../../src/polisyos/runtime/http/routes/control.py#L610) | same UI-hides-but-server-allows and offline gap |
| 19 | `/api/v1/control/lex/trigger` | scope; [handler](../../../src/polisyos/runtime/http/routes/control.py#L726) | Lex workspace requires only `knowledge.view`; trigger writes/queues LLM pipeline |
| 20 | `/api/v1/control/lex/search` | scope; [handler](../../../src/polisyos/runtime/http/routes/control.py#L787) | read-by-POST; only `knowledge.view` presentation gate |
| 21 | `/api/v1/fabric/quality/batch` | T run; [handler](../../../src/polisyos/runtime/http/routes/fabric.py#L80) | read-by-POST; no action permission |
| 22 | `/api/v1/fabric/trust/batch` | T run; [handler](../../../src/polisyos/runtime/http/routes/fabric.py#L133) | read-by-POST; no action permission |
| 23 | `/api/v1/fabric/impact` | T only if run supplied; [handler](../../../src/polisyos/runtime/http/routes/fabric.py#L238) | derive-by-POST; unscoped branch has no entity authorization |
| 24 | `/api/v1/lineage/batch` | T each ref; [handler](../../../src/polisyos/runtime/http/routes/lineage.py#L105) | hook-only read-by-POST; no action permission |
| 25 | `/api/v1/mobility/estimate` | scope; [handler](../../../src/polisyos/runtime/http/routes/mobility.py#L48) | no UI; optional persistence has no action permission |
| 26 | `/api/v1/mobility/bounds` | scope; [handler](../../../src/polisyos/runtime/http/routes/mobility.py#L80) | no UI; optional persistence has no action permission |
| 27 | `/api/v1/runs/batch` | T each run; [handler](../../../src/polisyos/runtime/http/routes/runs.py#L718) | read-by-POST; no action permission |
| 28 | `/api/v1/runs/{run_id}/production-approval` | T run; [handler](../../../src/polisyos/runtime/http/routes/runs.py#L852) | no UI; persists approval from self-asserted reviewer/signature with no principal binding or step-up |
| 29 | `/api/v1/runs/{run_id}/scenarios` | T run; [handler](../../../src/polisyos/runtime/http/routes/scenarios.py#L118) | persists draft manifest without scenario-create action permission |

The highest-severity P26 instance is production approval. Its request accepts
self-asserted `reviewer_identity` and an optional arbitrary signature
([contract](../../../src/polisyos/core/contracts/control.py#L1099)); the builder
accepts that signature or manufactures a digest from those fields
([builder](../../../src/polisyos/runtime/quality/approval.py#L480)); the route
does not bind reviewer identity, evidence exposure, or step-up to the JWT
principal. Required step-up classes are production approval/override,
promotion approve/reject, decision-validity invalidation, connector
ingestion/acquisition execution, and human-gated reissue.

### Offline And Cache Policy Proposal For DS5

| Class | Current evidence | DS5 policy |
| --- | --- | --- |
| Static shell/assets | Workbox precache; API explicitly denied ([SW](../../../apps/runtime-dashboard/src/sw.ts#L16)) | cacheable by version; visible app-version/update state; never infer data freshness from shell availability |
| Read query data | memory-only TanStack cache with mixed stale windows and fixture placeholders ([defaults](../../../apps/runtime-dashboard/src/api/queryClient.ts#L5)) | cache only with source `as_of`, fetch time, tenant/user, epoch/rule version, visible stale/offline state; revalidate before authority action |
| Never-cache authority | auth/permissions, signatures/public records, approvals, promotion state, decision validity, audit/step-up tokens | no durable browser cache; fail closed when live producer or current permission is unavailable |
| Queueable intent | composer draft and other explicitly non-authority user drafts | tenant+user+run scoped, expiring, timestamped, visibly draft/untrusted; conflicts resolved before submission |
| Barred queue actions | current promotion approve/reject plus future production approval, validity publication, public signing/publication, reissue, and feedback evaluation | no queue row and no optimistic terminal state; a later explicit live action must re-read state, identity, permission, step-up, tenant, and epoch |

The current promotion hook queues while offline and on 5xx/408/429, then
optimistically renders approved/rejected before a server decision
([conditions and optimism](../../../apps/runtime-dashboard/src/features/evidence/hooks/useQueuedPromotionDecision.ts#L26)).
The provider replays on online/visibility/SW events with retry but no live
permission, freshness, step-up, tenant/user epoch, or conflict revalidation
([flush](../../../apps/runtime-dashboard/src/app/providers/OfflineQueueProvider.tsx#L158)).
This action is rejected, not grandfathered.

### Workers And Client-Side Derivations: Law 9 Boundary

The three worker modules have no runtime worker consumer. DAG layout is pure
coordinates and is admissible when wired; JSON parsing is admissible only
before schema validation; data-transform sort/filter is presentation-only,
while average/count/max/min/sum may not feed authority or status slots
([operations](../../../apps/runtime-dashboard/src/workers/dataTransform.worker.ts#L71)).

`normalizeApiProjectionFailClosed` is conservative in outcome, but still
recomputes authority from UI-parsed strings: it detects “missing”, “stale”,
“contested”, etc. with regex
([detection](../../../apps/runtime-dashboard/src/shared/lib/domain/projectionFailClosed.ts#L95)),
removes publishability labels, and manufactures `projection_only`, `blocked`,
and `cannot_closeout` state
([normalization](../../../apps/runtime-dashboard/src/shared/lib/domain/projectionFailClosed.ts#L224)).
Fail-closed intent is good; the client is the wrong semantic owner. DS4/DS3
must bind to a producer-carried projection state and retain only display
masking as defense in depth.

Exact prohibited recomputations found are the causal effect decomposition,
composer readiness score, what-if validation-ready rule, browser signature,
and projection normalization listed in the inventory. Permitted derivations
are layout coordinates, sorting/filtering, formatting, and form-shape
validation when their results cannot occupy authority fields.

### Off-Contract Channels And Silent Degradation

| Channel | Counterpart and checks | Failure posture / disposition |
| --- | --- | --- |
| Global run SSE | client maps `/api/v1/runs/live` ([map](../../../apps/runtime-dashboard/src/app/realtime/sseTransport.ts#L13)); real server route is `include_in_schema=False` with tenant checks/no-cache ([route](../../../src/polisyos/runtime/http/routes/runs.py#L813)) | provider invalidates run caches, retries with jitter, then exposes polling/degraded state; DS3 must type/register it |
| Per-run SSE | client maps `/api/v1/runs/{id}/live` ([map](../../../apps/runtime-dashboard/src/app/realtime/sseTransport.ts#L19)); real hidden server route with run/tenant check ([route](../../../src/polisyos/runtime/http/routes/runs.py#L996)) | error only disconnects; run tab silently loses live invalidation; DS3 types/registers it |
| Review WS | three client channels map to `/api/v1/review/live`; server authenticates connect/subscribe/message ([route](../../../src/polisyos/runtime/http/routes/review.py#L233)) | bearer-handshake bridge is absent/undocumented; failure clears presence/cursors/locks and can make concurrency protection look idle-safe; DS3/DS5 must visibly block/degrade |
| Collaboration WS | four client channels map to absent `/api/v1/collaboration/live` ([map](../../../apps/runtime-dashboard/src/app/realtime/websocketTransport.ts#L15)) | orphan feature only; would show empty live collaboration. Decide removal before building |
| Collaboration REST | GET activity/comments and POST comment/resolve have no OpenAPI/server match | GETs silently return empty arrays on non-OK; writes throw. Orphan feature means no current live degradation; `producer_missing`, build-or-remove |

The collaboration result refines, rather than merely repeats, recon: the paths
are phantom, but the whole feature is currently orphaned. Creating endpoints
without first admitting a consumer would produce a P01 capability.

### Flags And Shadow Shipping

All four DS0 claims are confirmed exactly: `enableCausalGraph`,
`enableCollaboration`, `enableCommandPalette`, and `enableWhatIfAnalysis` have
zero production read. The causal, command-palette, and what-if surfaces are
nonetheless live through other paths, so these flags provide no rollback or
shadow-shipping control. The collaboration feature is orphaned. Unknown
manifest keys are ignored by the loose parser/known-key loop rather than
rejected ([merge](../../../apps/runtime-dashboard/src/shared/lib/featureFlags.ts#L168)).
No current canonical flag directly grants authorization, but the separate
`enableReviewCollaboration` permission projection blurs authz with rollout.
DS5 must make one strict registry authoritative for exposure, preserve server
permissions as a separate input, and require false-state reachability tests.

### Public Telemetry

Telemetry initializes app-wide, including PUBLIC routes. A configured
`VITE_TELEMETRY_BEACON_URL` receives full pathname/query/hash, route ID,
workspace, visibility state, release, and arbitrary event payload
([payload](../../../apps/runtime-dashboard/src/shared/telemetry/pipeline.ts#L31),
[egress](../../../apps/runtime-dashboard/src/shared/telemetry/pipeline.ts#L65)).
Static code cannot identify the destination owner because the URL is
environment-supplied.

Sentry is enabled only in production with a nonempty DSN and sets
`sendDefaultPii:false`
([gate/config](../../../apps/runtime-dashboard/src/shared/telemetry/sentry.ts#L19)),
but scopes and breadcrumbs still attach full path, route ID, workspace, and
arbitrary extras
([route scope](../../../apps/runtime-dashboard/src/shared/telemetry/sentry.ts#L29),
[breadcrumbs](../../../apps/runtime-dashboard/src/shared/telemetry/sentry.ts#L74)).
`sendDefaultPii:false` does not redact signed IDs, artifact IDs, run IDs, URL
queries, or caller-supplied payloads. DS12's no-tracker gate must disable or
redact both transports on public routes and prove that sensitive identifiers
never leave; DS1 does not claim whether any particular deployment currently
sets either environment variable.

## Seeded Red-First Negatives

These are specifications, not test implementations. Each expected-red clause
describes current behavior; the owning slice must first demonstrate that
failure and then repair the real producer/permission boundary. Sibling cases
prevent an instance-only patch.

| ID | Pattern / owner; target | Setup, forbidden outcome, and expected red state | Passing condition and sibling variants |
| --- | --- | --- | --- |
| `DS1-N001` | P05/P15/P26; DS12; extend `features/runs/routes/PublicDecisionViewerPage.test.tsx` and `domain/publicationPacket.test.ts` | Forge arbitrary certified/public claims and arbitrary `packetHash`, compute the public salted FNV signature, open the URL. Forbidden: `Verified` or any public-authority presentation. **Red now:** browser verification returns valid and renders Verified. | Only a server-resolved persisted record signed by a non-browser key may verify; unknown/altered/revoked IDs fail closed. Siblings: one-bit payload change, self-chosen packet hash, expired/revoked record. |
| `DS1-N002` | P05/P04/P15; DS4 + DS8; add `features/runs/routes/tabs/CausalTab.test.tsx` | Supply a run without a typed causal artifact plus a local draft/scaffold containing two estimated edges. Forbidden: identified path or direct/indirect/total effect authority. **Red now:** client multiplies/sums and renders decomposition. | Only typed server artifact/provenance may fill authority slots; local graph stays visibly draft with no identified/effect claim. Siblings: saved draft, fallback scaffold, blind-cast `artifacts.payload`. |
| `DS1-N003` | P05/P04; DS4 + DS8; add `features/whatif/ScenarioValidationPanel.test.tsx` | Scenario has empty stale/unsupported arrays but status draft/unknown, missing lineage, limitation, or violated constraint. Forbidden: “validation ready.” **Red now:** empty arrays produce ready. | Producer-carried validation/admissibility state controls the label and incomplete state blocks. Siblings: each limitation, constraint, stale epoch, and missing lineage independently. |
| `DS1-N004` | P15/P05/P04; DS4 + DS10; extend `features/lex/routes/LexKnowledgeGraphPage.test.tsx` | Return a search candidate with missing quote grounding, hallucination flag, unknown temporal/jurisdiction state, and high fused confidence. Forbidden: unqualified fact/norm badge or export/share as admitted truth. **Red now:** table and exports show fact, norm type, confidence only. | API preserves candidate/grounding/frontier fields and UI/export renders them inseparably. Siblings: all four norm types, CSV, JSON, share URL, zero-result frontier. |
| `DS1-N005` | P15/P05/P04; DS4 + DS9; extend `features/composer/routes/LaunchRunPage.test.tsx` | Increase LLM profiles/capabilities/parallel-model limit without adding evidence or admissibility. Forbidden: readiness score/status improvement. **Red now:** formula increases the ring and can reach Ready. | Remove the local authority score; only a typed producer result may occupy readiness. Siblings: replan bonus, preflight flag, auto-materialization flag. |
| `DS1-N006` | P15/P05; DS14; extend `features/clerk/components/ChatContainer.test.tsx` | Inject browser-store `structured.verdict`, confidence, factors, sources, and diff without a typed candidate envelope. Forbidden: verdict/confidence authority card or actionable accept/apply semantics. **Red now:** renderers display both. | Candidate envelope, model/provenance, limitations, authority purpose, and server-controlled action boundary are required; otherwise plain candidate text or blocked state. Siblings: streamed tokens, saved session replay, AIDiff accept-all/export. |
| `DS1-N007` | P04/P06; DS4; add `shared/lib/domain/statusOwnership.test.ts` plus TypeScript compile fixture | Reintroduce any local `DisputeStatus` definition or divergent member after canonical binding. Forbidden: compile/lint success. **Red now:** three definitions and two vocabularies coexist. | One canonical generated/runtime import; interaction-only state separately namespaced. Siblings: `warn`/`warning`, `pass`/`ok`, `block`/`fail`, all 47 census sites. |
| `DS1-N008` | P04/P05; DS4; extend `shared/lib/domain/projectionFailClosed.test.ts` | Give projection labels containing promotion synonyms while server closeout truth is absent or explicit. Forbidden: client regex becomes the semantic source of closeout/authority state. **Red now:** client manufactures blocked/cannot-closeout and `policy_design_case` source authority. | Server contract supplies state; client may only mask display defensively and may never upgrade. Siblings: synonym, malformed label, nested label, explicit server `can_closeout=false/true`. |
| `DS1-N009` | P26/P05; DS5; extend `tests/unit/runtime/http/test_runtime_api_authz.py` | Auto-enumerate all 29 unsafe-method routes; authenticate a valid tenant principal lacking the route's action permission. Forbidden: handler entry or 2xx. **Red now:** no route has an action-permission dependency; coarse OPA/tenant checks may allow. | Every mutating class resolves a canonical action and returns 403 before producer execution; exemptions are typed read-by-POST and proven side-effect-free. Siblings are generated from OpenAPI so route 30 cannot escape. |
| `DS1-N010` | P26/P05; DS5; extend `app/authz/AuthzProvider.test.tsx` | `/auth/me` loading, network error, malformed response, or 401. Forbidden: analyst permissions/MFA or high-stakes CTA. **Red now:** placeholder fallback grants 11 permissions and MFA true. | Unknown identity is visibly blocked, with no authority CTA. Siblings: cached prior user, tenant switch, review-collaboration pseudo-flag. |
| `DS1-N011` | P26/P05; DS5; extend `tests/integration/core_runtime/test_config_security_startup_bridge.py` | Non-test runtime profile with security off and fixture identity on; call each mutation class and review WS. Forbidden: fixture principal reaches handler. **Red now:** app/canary configuration permits it and fixture MFA is true. | Startup fails closed or rejects every protected request; fixture mode is structurally impossible in production profiles. Siblings: HTTP, WS client-supplied participant, admin/analyst fixtures. |
| `DS1-N012` | P26/P05; DS9; extend `tests/unit/runtime/http/test_runs_api.py` and `tests/unit/runtime/quality/test_approval.py` | Viewer/analyst submits production approval with another reviewer identity and arbitrary or absent signature, no evidence-exposure receipt, MFA false. Forbidden: persisted approval. **Red now:** supplied signature is accepted or a digest is manufactured. | Principal identity, exposure receipt, current permission, step-up, rule/epoch, and signed server record are bound and verified. Siblings: override, replay, cross-tenant run, self-approval. |
| `DS1-N013` | P26/P05; DS5 + DS9; extend `test_runtime_api_authz.py` | MFA false/stale for promotion approve/reject, validity publication, acquisition ingest, reissue. Forbidden: handler execution. **Red now:** current Rego MFA paths do not match any operation. | Step-up purpose and freshness bind to the exact action/resource before execution. Siblings: reject as well as approve, retry/replay, admin role, changed resource. |
| `DS1-N014` | P05/P26; DS5; extend `features/evidence/hooks/useQueuedPromotionDecision.test.tsx` and `app/offline/OfflineQueueProvider.test.tsx` | Offline or 500/408/429 during approve/reject. Forbidden: IndexedDB row, optimistic approved/rejected state, or later replay. **Red now:** all three occur. | Authority action requires an explicit live retry after state/identity/permission/step-up/tenant/epoch re-read. Siblings: all barred actions in the cache policy. |
| `DS1-N015` | P05/P04; DS5; add `app/offline/authorityLocalState.test.ts` | Persist Clerk verdict, what-if metric, causal draft, dispute, review attention, and operator-craft records; switch tenant/user or advance epoch. Forbidden: record reaches current authority slot. **Red now:** keys lack tenant/user/expiry/epoch partition. | Records are inaccessible or visibly untrusted/stale and require server revalidation. Siblings: six named caches plus composer draft; malformed/stale values. |
| `DS1-N016` | P05/P29; DS5; extend `app/providers/FeatureFlagProvider.test.tsx` | Remote/window/provider manifest contains unknown key or wrong type. Forbidden: silent ignore/partial merge. **Red now:** loose envelope and known-key loop ignore unknowns. | Strict governed registry rejects/fails closed with an observable diagnostic. Siblings: every source precedence level, cached old schema, duplicate auth pseudo-flag. |
| `DS1-N017` | P05/P26; DS5; add route reachability cases to flag-provider/workspace tests | Set each of the four `consumer_missing` flags false while its named feature route/control is otherwise reachable. Forbidden: surface remains reachable. **Red now:** causal, command palette, and what-if ignore their flags; collaboration has no live consumer. | Each key is wired to rollback/shadow exposure or retired from registry. Siblings: deep link, keyboard command, cached manifest, interface-mode switch. |
| `DS1-N018` | P26/P05; DS5; extend `tests/unit/runtime/http/test_review_collaboration_api.py` plus `useReviewCollaborationSurface.test.tsx` | Fixture identity false, ordinary browser WS (no Authorization header/proxy), high-stakes review surface open. Forbidden: idle-safe UI or editable action with no live lock/presence channel. **Red now:** handshake cannot prove auth and failure clears concurrency signals. | Authenticated handshake succeeds through a documented mechanism, or surface visibly blocks/degrades before review action. Siblings: reconnect, expired token, each of three review channels. |
| `DS1-N019` | P05/P15; DS9; add `workers/dataTransform.worker.test.ts` integration with authority-slot adapter | Worker aggregate of authority-bearing quantities is passed to status/readiness/approval component. Forbidden: render as runtime fact. **Red now:** generic aggregate contract has no provenance/authority barrier (worker itself is unwired). | Presentation aggregates are branded/non-authoritative or server-verified before authority consumption. Siblings: sum/avg/min/max/count and JSON parser bypassing schema. |
| `DS1-N020` | P05/P26; DS12; extend `shared/telemetry/TelemetryProvider.test.tsx` and add Sentry transport test | Visit public signed decision/artifact route with signed ID, run/artifact refs, query secrets; trigger breadcrumb/error/event. Forbidden: identifier or payload leaves through beacon/fetch/Sentry. **Red now:** full path/context and arbitrary extras are serialized. | Public no-tracker policy disables egress or structurally redacts before transport. Siblings: pathname, query, hash, tags, breadcrumbs, exception extras. |
| `DS1-N021` | P05/P03; DS3; extend `tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py` | Derive every UI method/path plus raw SSE/WS channel and compare to governed contracts. Forbidden: unmatched collaboration calls or unregistered hidden channels pass. **Red now:** four REST + one WS path are phantom and three server channels are off-contract. | One generated/typed registry covers every admitted channel; intentional exclusions are explicit. Siblings: dynamic lineage paths and future raw fetch/EventSource/WebSocket. |
| `DS1-N022` | P15/P05/P04; DS3 + DS10; extend `tests/unit/runtime/http/test_control_api.py` | Upstream Lex `LegalFactResult` has candidate/grounding/hallucination/temporal fields. Forbidden: search DTO drops them while retaining scalar confidence/norm. **Red now:** DTO is lossy. | API and generated client preserve the truth fields through UI/export. Siblings: missing quote, unknown jurisdiction, stale version, low quality, hallucination. |
| `DS1-N023` | P05/P26; DS12; extend `publicationPacket.test.ts` and public-viewer test | Packet contains email, token, tenant/run identifiers, or non-keyword private fields. Forbidden: URL generation or public render. **Red now:** keyword scan is not on builder path and can miss values. | Server publication policy classifies/redacts and rejects before persisted signing. Siblings: encoded value, nested field, synonym, telemetry egress. |

The authz matrix negative (`DS1-N009`) is intentionally generic over the
OpenAPI denominator. Per-endpoint handwritten tests alone would reproduce
P31/P33 and let the thirtieth route bypass the fix.

## Plan-Impact Appendix

This appendix is an input to the post-Phase-A roadmap revision, not authority
to start Phase B. “Decrease” means reuse or delete rather than rebuild; it
does not lower the evidence bar.

| Finding | Slice | Code reality / contradicted assumption | Required scope change | Effort |
| --- | --- | --- | --- | --- |
| `PI-01` | DS3 | Dashboard is not the only generated-client consumer: the reference shell imports the package class, while dashboard uses `openapi-fetch` ([shell import](../../../apps/runtime-reference-shell/app.js#L1), [dashboard client](../../../apps/runtime-dashboard/src/api/client.ts#L1)). | Choose one package/generated-client home and migrate both consumers; parity must cover dynamic paths and auth-owned `/auth/me`. Do not create a third projection client. | re-cut-required |
| `PI-02` | DS3 | 45 OpenAPI operations reach surfaces, 7 stop at unused hooks, 37 have no dashboard call. | Producer/export work must be demand-mapped to admitted DS7-DS18 consumers; delete/retain hook-only code explicitly and do not migrate all 89 by default. | decrease for unused; unchanged for admitted |
| `PI-03` | DS3 | Two real SSE routes and one review WS are outside OpenAPI; collaboration REST/WS is phantom and its feature orphaned. | Add a governed typed channel registry or explicit exclusion for SSE/WS. Decide removal before building collaboration producers; generated REST parity alone is insufficient. | increase |
| `PI-04` | DS4 | Shared/UI is 89 implementations, not about 40; 23 production files violate its no-API/no-app boundary; none is constitutionally stable. | Re-scope from mechanical primitive extraction to dependency severing + 12-family rebinding. Preserve low-risk primitives, rebind quantity/temporal/trust/counterfactual semantics, and keep maturity below stable pending evidence. | increase / re-cut-required |
| `PI-05` | DS4 | Status denominator is 23 named + 24 inline, not at least 8; three DisputeStatus definitions form two vocabularies. | Use a generated canonical status owner plus an explicit namespace for operational interaction states. Retirement test must derive all local definitions, not enumerate eight known names. | increase |
| `PI-06` | DS4 | Causal effects, what-if validation, composer readiness, projection fail-closed, and browser signing recompute semantics client-side. | Add red-first authority-boundary tests before rebinding components. Remove the composer score/browser signature; demote local drafts; producer-bind what-if/causal/projection state. | increase |
| `PI-07` | DS5 | Raw fetch is 9 sites in 5 production files, not about 10 files; three auth calls are an owned adapter, four collaboration calls are orphan/phantom, one flag call and one telemetry call have distinct policies. | The lint needs typed exemptions by owner and path, not a blanket count. First target exactly these nine sites plus raw EventSource/WebSocket construction. | decrease count, increase precision |
| `PI-08` | DS5 | 29/29 POST routes lack action permission and step-up dependencies; OPA resource binding happens too early; fixture identity and UI fallback fail open. | Re-cut audience mapping into one structural server action-authorization intake, production fixture prohibition, strict UI unknown-identity state, resource binding before OPA, and generic 29-route negative. | increase / re-cut-required |
| `PI-09` | DS5 | The promotion authority queue replays without live state/permission/step-up/epoch checks; six authority-looking local caches lack tenant/user/expiry partition. | Implement the cache-policy matrix in this report. Bar authority actions from queue; introduce visible `as_of`/offline state and isolation/revalidation tests across all local stores. | increase |
| `PI-10` | DS5 | Four canonical flags are consumer-missing while three named surfaces are live; auth permission is a thirteenth pseudo-source; unknown keys are ignored. | Strict one-registry exposure contract, wire-or-retire all four flags, keep permission projection separate, and test false-state route reachability. | increase |
| `PI-11` | DS6 | Full evidence estate is 251 tests/specs, 44 stories, 67 a11y files, 17 browser specs, 16 images; the shared/UI structural a11y gate is currently red and no manual AT record exists. | Evidence ingestion must distinguish authored tests, project/test expansions, pixels, fixture semantics, and manual AT. Repair the gate in DS6/DS4 ownership and store evidence/cadence before any stable label. | increase |
| `PI-12` | DS6 | Route axe covers 17/22 leaf patterns; missing public, welcome, legacy compare, deck, and causal. | Coverage validator derives leaf routes from the router, records intentional aliases, and requires public/authority routes before maturity. | increase |
| `PI-13` | DS7 | Runs/dashboard substrate is rich but status/authority is UI-local; no current route is a truthful GY Cycle Board. | Reuse layout/table/navigation only after DS3/DS4 binding; do not treat current run list as an incremental Cycle Board producer. | unchanged, risk increased |
| `PI-14` | DS8 | Artifacts/runs/causal/what-if/quantity/print already exist, but causal runtime graph is bridge-missing, legacy WhatIf is latent, and shared/UI families import API/app owners. | Make DS8 a strangler map per panel: wire typed artifacts, remove latent WhatIf, demote local causal drafts, and reuse print/export only after authority parity. | re-cut-required; less greenfield, more integration |
| `PI-15` | DS9 | UI visibility is not authorization; promotion is offline-queueable; production approval accepts self-asserted reviewer/signature; local Operator Craft mints reviewer-like state. | DS9 must own principal-bound approval/override/step-up/exposure receipts and explicitly strangle local Operator Craft authority semantics. Include promotion/reissue/validity/acquisition classes, not just a new approval screen. | increase |
| `PI-16` | DS10 | Lex is a live search/export surface, not raw-fetch code; the API DTO drops upstream candidate/grounding/hallucination/temporal truth. Command palette is live despite its dead flag. | Extend existing Lex producer/DTO/UI/export end to end; add frontier honesty. Reuse command-palette shell only after strict exposure flag and capability status binding. | decrease UI build; increase contract work |
| `PI-17` | DS11 | `/welcome` exists but has no test/a11y/story coverage; app-wide telemetry initializes on public routes. | Trust/docs posture must include public-route test coverage and a no-tracker/redaction posture, without importing the forgeable decision URL as proof. | increase |
| `PI-18` | DS12 | Public decision is a live decorative mechanism with three builders and one URL link, not a missing screen; no server public record depends on it. Telemetry can emit full signed paths and arbitrary payload. | Keep route frozen; replace browser format with server-keyed persisted record, revocation/expiry, privacy classification, signature verification, public accessibility, and no-tracker negative. Strangle all three builders and local Operator Craft refs. | increase / re-cut-required |
| `PI-19` | DS13 | Current disputes are per-run localStorage and publication history is browser projection; no server public accountability feed exists. | Do not migrate local disputes/history as records. DS13 begins only from DS12 persisted identifiers and governed dispute/consultation producers. | unchanged gate; delete false substrate |
| `PI-20` | DS14 | Clerk's chat shell, history, status streaming, and export exist, but structured verdict/confidence/diff has no live producer; duplicate index route is unreachable; sessions persist locally. | Reuse shell/status transport, delete duplicate route, remove or candidate-bind dormant structured authority, partition/expire storage, and add bounded-agent artifact bridge. | decrease visual build; increase semantic integration |
| `PI-21` | DS15 | Data Intelligence already consumes profile/catalog/connector/discovery/preview/resolve operations; ingest is hook-only. Those mutations have no action permission/step-up. | Reuse read surfaces, bind GY acquisition artifacts, and add DS5 permission/step-up before any execute CTA. Wire-or-delete ingest hook; never infer readiness from current calls. | decrease read UI; increase execution gate |
| `PI-22` | DS16 | Quantity/counterfactual/temporal components already exist but are UI-local and unevenly tested; client aggregation can collapse distributions. | Rebind existing families to set-valued/uncertainty/derived-data contracts; prohibit worker/client point collapse and preserve provenance. | unchanged overall; integration-heavy |
| `PI-23` | DS17 | No consumed operation or component represents the GY risk-spend ledger; Clerk confidence gauge is ungrounded local substrate, not reusable authority. | Keep DS17 producer-gated. Do not count generic confidence visuals as progress until bound to the typed delta ledger and refusal/acquisition rows. | unchanged |
| `PI-24` | DS18 | Temporal capabilities are consumed, but temporal components are contract-local and caches lack epoch/revalidation binding. | Extend DS18 from chrome to a cross-cache invariant: every time-bearing surface receives producer epoch/as-of and cached authority fails closed on epoch advance. | increase |

### Features And Paths With No Admitted Migration Slice

| Item | Current state | Required Phase-A disposition input |
| --- | --- | --- |
| `features/layout` | empty directory/README; real owner is `app/layout` | delete; never create a migration workstream |
| second Clerk index route | redundant after ModeAwareHome | delete under DS14 route cleanup |
| `features/collaboration` | 15 files, phantom REST/WS, zero outside importer | DS5/DS9 explicit reuse-or-retire; default to retire until a consumer contract exists |
| `features/onboarding` | six files, localStorage, zero outside importer; separate Operator Craft onboarding exists | consolidate only after DS9 decides human-integrity flow; otherwise retire both local semantics |
| `features/export/social` | email/OG fixture, story, test, zero consumer | retain as deferred material; email remains `surface_out_of_scope` |
| legacy WhatIf panel | latent unless legacy parameters are passed | strangle rather than migrate in DS8 |
| 7 hook-only API calls | typed definitions but no production component importer | each owning slice wires or removes; hook existence is not consumption |
| 37 no-dashboard-call operations | real server contracts without current UI | remain `defer`; later slice must name audience/use rather than blanket migration |

### Corrected Master-Plan Snapshot Inputs

| Master row / statement | DS1 correction |
| --- | --- |
| Scale & quality | `apps/runtime-dashboard/src` remains 908 TS/TSX and 136,827 LOC; full frontend zone is 944/145,033. Dashboard source has 230 `.test` + 3 `.spec`; full estate 251. There are 44 stories, 89 shared/UI implementations in 12 families, 67 a11y files, 390 `aria-` occurrences, 17 e2e specs, 16 visual baselines; structural a11y gate is red and no manual AT evidence exists. |
| Typed waist | 89 OpenAPI ops: 45 surface-consumed, 7 hook-only, 37 uncalled. Dashboard uses `openapi-fetch`; reference shell also consumes eight via generated package. Raw fetch outside `src/api` is 9 calls/5 production files, not about 10 files. |
| Status semantics | 23 named + 24 inline local status definitions; DisputeStatus remains 3 definitions/2 vocabularies; P04 extends beyond eight known enums. |
| Authz | 29/29 POST operations have no action-permission or step-up dependency. Fixture identity and UI placeholder reach are broader than recon; OPA resource binding is too late. Client has three collaboration permissions absent server-side. |
| Offline | Static API caching is correctly denied, but promotion approve/reject is the only queued mutation class and is optimistically finalized/replayed without live authority revalidation; six authority-looking local caches lack tenant/user/epoch binding. |
| Agent surface | Clerk live path launches and streams run status only; structured verdict/confidence/diff is dormant `producer_missing` substrate. Duplicate direct index route is redundant. |
| Realtime/off-contract | Two SSE endpoints and review WS are real/off-contract; review WS has an auth bridge risk. Collaboration REST/WS is phantom, but its entire feature is currently orphaned, so no live UX calls it. |
| Feature flags | 12 canonical all-true defaults + one auth-derived pseudo-flag; exactly four canonical keys have no reads, while three named surfaces remain live outside those flags. Unknown keys are ignored. |
| Observability | Public routes share app-wide telemetry; beacon and Sentry attach full paths/route context and arbitrary payload/extras when configured. `sendDefaultPii:false` is not identifier redaction. |
| Proving-ground routes | Replace the 14-path snapshot with 32 route objects, 29 effective patterns, 22 leaf UI patterns, five redirects, one catch-all, duplicate root index, and run-detail tab expansion. |
| Strangler decision | Replace “dashboard is the only live generated-client consumer” with the two-consumer reality: dashboard local openapi-fetch client plus reference-shell generated package client. |

The master plan is corrected only for these evidence-backed rows and direct
downstream scope clauses. Its Phase ordering and activation gates are not
changed by DS1; the combined DS0–DS2 revision remains the architect's Phase-A
decision.
