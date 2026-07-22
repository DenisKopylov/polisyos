# Atlas DS19 Frontend Disposition Register and Strangle-Wave Report

Status: `implementation_complete_no_merge_baseline_red`; architect review
pending; generated register projection and human verification receipts.

This report projects the typed register. It does not replace DS1/DS2 evidence,
upgrade readiness, or authorize a pending deletion/rebind. The block between
the projection markers is regenerated and exact-compared by the standalone
checker.

## Baseline toolchain receipts

| Gate | Before result | Acceptance law |
| --- | --- | --- |
| Typecheck | PASS, 11.63 s | absolute green |
| Production build + PWA + security | PASS, 22.69 s; 3,880 modules; 102 precache entries | absolute green |
| ESLint | 75 errors, 0 warnings; initial enumeration about 19 min; cached JSON 5.93 s | current diagnostic multiset must be a subset of manifest `atlas-ds19-frontend-baseline-debt` |
| Vitest | 231 files / 678 tests in 181.12 s; 3 files / 5 tests failed | failed-test identity/signature set must be a subset of the parent-reproduced manifest |

Vitest's same five failures reproduced on parent `7b6933770` in 1.96 s. The
baseline repair is `d01eaa572`; the lockfile changed declarations/importer
edges only, with no version movement. Before lock SHA-256:
`d7fb70700c7934771839730af1697fb6be9958b12fdb4a9cdc78d27f4f0ac309`;
after: `111454fc3a69d075418dd93b5afd787fb13ca551511936eb629f9a09e7fe9eed`.

| Repaired declaration | Resolved before | Resolved after | Graph movement |
| --- | --- | --- | --- |
| `axe-core` | `4.11.4` | `4.11.4` | none |
| `intl-messageformat` | `10.7.18` | `10.7.18` | none |
| `workbox-core` | `7.4.0` | `7.4.0` | none |
| `workbox-precaching` | `7.4.0` | `7.4.0` | none |
| `workbox-routing` | `7.4.0` | `7.4.0` | none |
| `workbox-window` (PWA peer) | `7.4.0` | `7.4.0` | none |

The lockfile diff is confined to the dashboard importer/declaration region;
the package-resolution suffix is byte-identical. No package was introduced and
no version moved.

Audience drift classification: the generated
`PolicyDesignCaseProjection.audience` field landed in `da54f58206` on
2026-05-30; the narrow validator fixture helper predated it in `5c4823ee7` on
2026-05-21. The two negative fixture literals were the only authored
projection literals lagging the generated type. Commit `d01eaa572` made those
fixtures consume the generated audience type; generated and runtime code were
not changed.

## Wave reduction measured from the repaired baseline

- Application lines added: **12396**
- Application lines deleted: **12277**
- Net application LOC reduction: **-119**
- Application files deleted: **66**

## Wave-end full verification

| Gate | Wave-end result | Law |
| --- | --- | --- |
| Typecheck | PASS, 33.98 s | absolute green |
| Production build + PWA + security | PASS, 12.66 s; 3,871 modules; 101 precache entries | absolute green; run after the explicit typecheck because a duplicate-typecheck wrapper attempt was host-memory-killed before Vite |
| ESLint | 916 files; inherited 75 errors / 0 warnings in 5.94 s | zero new diagnostic identities; baseline subset PASS |
| Vitest | 228 files / 664 tests in four deterministic batches; 225 files / 659 tests passed; inherited 3 files / 5 tests failed | failed identity/signature baseline subset PASS |
| Register/check | schema, fresh live probes, report parity, source-byte binding, lint/test comparisons, corruption probes PASS | disposition law enforced |

The monolithic Vitest JSON reporter was host-memory-killed before producing a
receipt, so the complete default-config suite was rerun in four two-worker
batches and mechanically merged. ESLint receipt SHA-256:
`22aed9b244038d5e1c0ed0453a7928ad5917dce229f8ee0de823d203ecb9bebb`;
Vitest receipt SHA-256:
`9046b0d0abd603a2919fda35f2dba0698fa92c158ed3eee62b6fbac6b07d2545`.

## Closure verification

| Gate | Closure result | Interpretation |
| --- | --- | --- |
| Typecheck | PASS, 57.65 s | absolute green |
| Production build + PWA + security | PASS, 28.72 s; 3,871 modules; 101 precache entries | absolute green after the separately recorded typecheck |
| ESLint | 916 files; inherited 75 errors / 0 warnings in 5.96 s | zero new diagnostic identities; baseline subset PASS |
| Vitest | 228 files / 664 tests in 236.92 s; 225 files / 659 tests passed; inherited 3 files / 5 tests failed | failed identity/signature baseline subset PASS |
| Dashboard architecture | 36 inherited violations; 0 violation files changed since `d01eaa572` | baseline-red, no regression; no fence expansion |
| Repository guardrails | PASS, 27.05 s under `uv run --isolated` | default worktree `.venv` is invalid; isolated run installed 116 ephemeral packages and changed no repository file |
| Register/check | schema, 261 DS1 roots, 233 DS2 edges, seven live censuses, report parity, links, source hashes, and corruption probes PASS | disposition authority current |
| Fence | 55 paths, 0 violations against `main...HEAD`; `git diff --check` PASS | DS19 fence only |

Closure ESLint receipt SHA-256:
`22aed9b244038d5e1c0ed0453a7928ad5917dce229f8ee0de823d203ecb9bebb`;
closure Vitest receipt SHA-256:
`21a0ab369f7447ab6a69f93de474cc0b34562e3c33a92a3ba159e254aa163dcb`.
The optional focused counterfactual Playwright journey did not execute because
the fixture server hit the invalid default `.venv` before browser startup;
affected Vitest suites passed, and this non-receipt is not presented as green.

The exact terminal state is
`implementation_complete_no_merge_baseline_red`: reviewable but not merge
ready while inherited lint, Vitest, and dashboard architecture debt remains.
No merge or push is performed.

<!-- BEGIN DS19 REGISTER PROJECTION -->
### Register statistics

| Disposition | Root units |
| --- | ---: |
| `deleted` | 15 |
| `rebind_pending` | 200 |
| `retire_disposition` | 25 |
| `use_as_is` | 5 |
| `wire_disposition` | 16 |
| **Total DS1 roots** | **261** |

DS2 evidence reconciliation: **233 = 173 mapped + 60 unbound**. DS2 rows are evidence edges, not 233 additional estate owners.

### Deletion wave

| Cluster | Units | Census result | Disposition | Verification |
| --- | --- | --- | --- | --- |
| collaboration | `feature-collaboration`, `raw-fetch-collab-activity`, `raw-fetch-collab-comment-post`, `raw-fetch-collab-comments-get`, `raw-fetch-collab-resolve`, `status-collaboration-session`, `transport-rest-collaboration`, `transport-ws-collaboration` | zero_consumers | `deleted` | `docs/plans/active/atlas-slices/DS19-false-substrate-strangle-wave-journal.md#2026-07-17---collaboration-cluster-verification` |
| onboarding | `feature-onboarding-orphan` | zero_consumers | `deleted` | `docs/plans/active/atlas-slices/DS19-false-substrate-strangle-wave-journal.md#2026-07-17---onboarding-cluster-verification` |
| layout-placeholder | `feature-layout-empty` | zero_consumers | `deleted` | `docs/plans/active/atlas-slices/DS19-false-substrate-strangle-wave-journal.md#2026-07-17---empty-layout-placeholder-cluster-verification` |
| workers | `worker-dag-layout`, `worker-data-transform`, `worker-json-parse` | zero_consumers | `deleted` | `docs/plans/active/atlas-slices/DS19-false-substrate-strangle-wave-journal.md#2026-07-17---zero-consumer-workers-cluster-verification` |
| clerk-index | `route-home-clerk-duplicate` | zero_consumers | `deleted` | `docs/plans/active/atlas-slices/DS19-false-substrate-strangle-wave-journal.md#2026-07-17---duplicate-clerk-index-cluster-verification` |
| whatif-local | `cache-whatif-scenarios`, `feature-whatif::legacy-local-whatif-subgraph` | zero_consumers | `deleted` | `docs/plans/active/atlas-slices/DS19-false-substrate-strangle-wave-journal.md#2026-07-17---whatif-dead-parameter-subgraph-cluster-verification` |

### DS4 primitive aggregate disposition

| Outcome | Count |
| --- | ---: |
| Package migrated | 22 |
| Dashboard rebound | 2 |
| Retired | 3 |
| Use as-is | 2 |
| **Total** | **29** |

| Dormant primitive | Disposition | DS2 adoption row | Governing condition |
| --- | --- | --- | --- |
| `DropdownMenu` | `retire` | `none` | No exact DS2 row; retirement is not prohibited. |
| `ScrollArea` | `use_as_is` | `component-scroll-area` | Archive admission alone sunsets nothing. DS4 may remove a mapped loser only after generated/source ownership, consumer migration, drift checks, and the owning slice's DS6 evidence are complete. |
| `Separator` | `retire` | `none` | No exact DS2 row; retirement is not prohibited. |
| `Sheet` | `retire` | `none` | No exact DS2 row; retirement is not prohibited. |
| `Tabs` | `use_as_is` | `component-tabs` | Keep the mapped live v4 family as the transitional winner until DS4 routes a real consumer through one governed replacement, DS6 passes its negative/browser/accessibility evidence, and the old import path is removed. |

Pre-deletion resurrection commit: `caa1ee6e3ab49d559b19dbeeda6308c3598e7183`.

Resurrection rule: `recreate_in_atlas_ui_only_with_a_real_production_consumer_never_restore_in_the_app_tree`.

### Wire dispositions — 13 OpenAPI operations

| Unit | Consumer slice | Rationale |
| --- | --- | --- |
| `api-op-create-run-production-approval` | `DS3` | Adopt and harden the existing approval endpoint through the governed DS3 contract. |
| `api-op-create-run-scenario` | `DS3` | Use the server-backed scenario lifecycle that survives deletion of the local WhatIf branch. |
| `api-op-download-artifact-content` | `DS3` | Reuse existing artifact addressing for governed retrieval rather than creating a second export path. |
| `api-op-evaluate-run-feedback` | `DS3` | Adopt governed review-effectiveness evaluation and its event trail through DS3. |
| `api-op-export-bureaucratic-artifact` | `DS3` | Reuse the existing packet export/render producer instead of adding parallel export ownership. |
| `api-op-get-artifact-batch` | `DS3` | Reuse the existing typed batch producer for governed artifact inspection and packet conventions. |
| `api-op-get-fabric-run-replay` | `DS3` | Reuse the existing replay producer for version-pinned inspection. |
| `api-op-get-fabric-source-scorecards` | `DS3` | Reuse the existing source-scorecard producer through one generated client. |
| `api-op-get-packet-decision-validity` | `DS3` | Adopt the existing packet-validity read projection through the typed DS3 client. |
| `api-op-get-run-decision-validity` | `DS3` | Adopt the existing run-validity inspection projection through the DS3 waist. |
| `api-op-list-binding-profiles` | `DS3` | Expose existing registry-derived binding-profile discovery through the DS3 waist. |
| `api-op-publish-decision-validity-event` | `DS3` | Adopt the live-only, principal-bound validity action through the governed DS3 client. |
| `api-op-reissue-run` | `DS3` | Adopt the principal-bound reissue action through the generated DS3 contract. |

### Retire dispositions — 24 OpenAPI operations

Retirement is from frontend adoption only; no endpoint is removed by DS19.

| Unit | Consumer slice | Rationale |
| --- | --- | --- |
| `api-op-analyze-attractors` | `DS3` | No accepted Atlas consumer exists; endpoint presence must not manufacture an analysis UI. |
| `api-op-analyze-fabric-impact` | `DS3` | No named consumer exists; adopting it would create a parallel analytical owner. |
| `api-op-analyze-lyapunov-diagnostics` | `DS3` | Keep this scientific diagnostic server-only until a governed projection is specified. |
| `api-op-compute-mobility-bounds` | `DS3` | This domain-specific computation has no admitted universal Atlas surface. |
| `api-op-estimate-causal-frontier-sae` | `DS3` | This computation is not the DS7 acquisition frontier and has no named consumer. |
| `api-op-estimate-mobility` | `DS3` | This domain-specific computation has no admitted frontend surface. |
| `api-op-get-analysis-basin-map` | `DS3` | The read half of this basin workflow has no admitted frontend consumer. |
| `api-op-get-analysis-continuation-branch` | `DS3` | The read half of this continuation workflow has no admitted frontend consumer. |
| `api-op-get-attractor-analysis` | `DS3` | The read half of this analysis workflow has no independently admitted consumer. |
| `api-op-get-fabric-quality-batch` | `DS3` | No accepted evidence projection names this batch as a consumer dependency. |
| `api-op-get-fabric-trust-batch` | `DS3` | A trust projection contract is required before frontend adoption. |
| `api-op-get-mobility-report` | `DS3` | The mobility report family has no named Atlas consumer. |
| `api-op-get-mobility-report-bounds` | `DS3` | The mobility report detail has no named Atlas consumer. |
| `api-op-get-mobility-report-diagnostics` | `DS3` | The mobility diagnostic has no named Atlas consumer. |
| `api-op-get-run-compare` | `DS3` | The debug projection lacks a governed product contract and must not become UI authority. |
| `api-op-get-run-equilibria` | `DS3` | The debug diagnostic has no named consumer or governed product projection. |
| `api-op-get-run-feedback` | `DS3` | The debug read is not the governed review-effectiveness projection. |
| `api-op-get-runs-batch` | `DS3` | Current run list/detail paths cover admitted surfaces; avoid a second read owner. |
| `api-op-health` | `DS3` | The root health probe is deployment infrastructure; the dashboard already uses governed /api/v1/health. |
| `api-op-list-control-outbox` | `DS3` | Internal delivery substrate is not a product transparency surface. |
| `api-op-list-control-workers` | `DS3` | Internal worker-lease state is runtime infrastructure, not product navigation. |
| `api-op-persist-basin-map` | `DS3` | No named surface or action-authority contract consumes this persistence operation. |
| `api-op-persist-continuation-branch` | `DS3` | No accepted Atlas surface consumes this persistence operation. |
| `api-op-ready` | `DS3` | Deployment readiness is not a product-readiness claim or browser surface. |

### Consumer-missing flag dispositions

| Unit | Decision | Consumer slice | Rationale |
| --- | --- | --- | --- |
| `flag-enable-causal-graph` | `wire_disposition` | `DS5` | The graph is live outside its declared gate; DS5 must wire one whole-surface exposure gate. |
| `flag-enable-collaboration` | `retire_disposition` | `DS5` | The orphan collaboration surface is deleted, so its unused flag cannot remain false continuity. |
| `flag-enable-command-palette` | `wire_disposition` | `DS5` | The live palette must consume its existing key as a genuine launch gate. |
| `flag-enable-what-if-analysis` | `wire_disposition` | `DS5` | The surviving server-backed workbench needs one real whole-surface exposure gate. |

### Subunits and structural findings

| ID | Kind | Disposition | Owner slice | State/reason |
| --- | --- | --- | --- | --- |
| `feature-whatif::legacy-local-whatif-subgraph` | `dead_subgraph` | `deleted` | `DS19` | Fresh DS19 census proved the seven-file local parameter/store branch and its optional workbench edge unreachable; it was deleted while the server-backed ScenarioWorkbench remained live. |
| `route-app-layout::ru-ui-catalog` | `legacy_continuity` | `frozen_legacy_continuity` | `DS0` | Ratified D4 freezes the legacy ru UI catalog in place: not used, not deleted, and not an active-locale claim. |
| `baseline-lint-quantity-debt` | `baseline_lint_debt` | `rebind_pending` | `DS4` | `repaired` — The quantity diagnostic class is derived from the active lint manifest; resolved means all 75 immutable-origin identities have content-bound C06-C08 resolutions. |
| `baseline-test-i18n-count-debt` | `baseline_test_debt` | `rebind_pending` | `DS6` | `open_debt` — The active manifest retains exactly three count-sensitive locale parity identities owned by DS6. |
| `baseline-test-a11y-coverage-debt` | `baseline_test_debt` | `rebind_pending` | `DS4` | `repaired` — The accessibility census state is derived from the active Vitest debt classes; C12 repairs the OperatorDiagnosticPanel companion without an allowlist suppression. |
| `baseline-test-temporal-cursor-debt` | `baseline_test_debt` | `rebind_pending` | `DS4` | `repaired` — The temporal-cursor state is derived from the active Vitest debt classes; C09 closed the time-dependent identity with an injected clock. |
| `dependency-axe-core` | `dependency_declaration` | `use_as_is` | `DS19` | `repaired` — The source or PWA peer was already resolved transitively; DS19 declared the exact locked version without changing the resolved graph. |
| `dependency-intl-messageformat` | `dependency_declaration` | `use_as_is` | `DS19` | `repaired` — The source or PWA peer was already resolved transitively; DS19 declared the exact locked version without changing the resolved graph. |
| `dependency-workbox-core` | `dependency_declaration` | `use_as_is` | `DS19` | `repaired` — The source or PWA peer was already resolved transitively; DS19 declared the exact locked version without changing the resolved graph. |
| `dependency-workbox-precaching` | `dependency_declaration` | `use_as_is` | `DS19` | `repaired` — The source or PWA peer was already resolved transitively; DS19 declared the exact locked version without changing the resolved graph. |
| `dependency-workbox-routing` | `dependency_declaration` | `use_as_is` | `DS19` | `repaired` — The source or PWA peer was already resolved transitively; DS19 declared the exact locked version without changing the resolved graph. |
| `dependency-workbox-window` | `dependency_declaration` | `use_as_is` | `DS19` | `repaired` — The source or PWA peer was already resolved transitively; DS19 declared the exact locked version without changing the resolved graph. |
| `fixture-policy-design-case-audience` | `fixture_contract_drift` | `use_as_is` | `DS19` | `repaired` — The fixtures now type audience from the generated projection contract introduced after the fixture helper; runtime and generated code were not changed. |

### Seeded-negative lifecycle

| Negative | Lifecycle | Affected units | Deletion census |
| --- | --- | --- | --- |
| `DS1-N001` | `still_required` | `derivation-browser-signature` | — |
| `DS1-N002` | `still_required` | — | — |
| `DS1-N003` | `still_required` | — | — |
| `DS1-N004` | `still_required` | — | — |
| `DS1-N005` | `still_required` | — | — |
| `DS1-N006` | `still_required` | — | — |
| `DS1-N007` | `still_required` | — | — |
| `DS1-N008` | `still_required` | — | — |
| `DS1-N009` | `still_required` | — | — |
| `DS1-N010` | `still_required` | — | — |
| `DS1-N011` | `still_required` | — | — |
| `DS1-N012` | `still_required` | — | — |
| `DS1-N013` | `still_required` | — | — |
| `DS1-N014` | `still_required` | — | — |
| `DS1-N015` | `partially_reduced` | `feature-whatif::legacy-local-whatif-subgraph` | `census-whatif-local-subgraph-delete` |
| `DS1-N016` | `still_required` | — | — |
| `DS1-N017` | `partially_reduced` | `flag-enable-causal-graph`, `flag-enable-collaboration`, `flag-enable-command-palette`, `flag-enable-what-if-analysis` | `census-collaboration-delete` |
| `DS1-N018` | `still_required` | — | — |
| `DS1-N019` | `obsolete_by_deletion` | `worker-data-transform`, `worker-dag-layout`, `worker-json-parse` | `census-zero-consumer-workers-delete` |
| `DS1-N020` | `still_required` | — | — |
| `DS1-N021` | `partially_reduced` | `feature-collaboration`, `raw-fetch-collab-activity`, `raw-fetch-collab-comment-post`, `raw-fetch-collab-comments-get`, `raw-fetch-collab-resolve`, `status-collaboration-session`, `transport-rest-collaboration`, `transport-ws-collaboration` | `census-collaboration-delete` |
| `DS1-N022` | `still_required` | — | — |
| `DS1-N023` | `still_required` | — | — |

### Complete DS1-root projection

| Unit | DS1 evidence | DS2 evidence count | Disposition | Strangle | Owner slice | Census/successor |
| --- | --- | ---: | --- | --- | --- | --- |
| `route-welcome` | `route-welcome` | 0 | `rebind_pending` | `pending` | `DS11` | `—` |
| `route-public-decision` | `route-public-decision` | 0 | `rebind_pending` | `pending` | `DS12` | `—` |
| `route-app-layout` | `route-app-layout` | 0 | `rebind_pending` | `pending` | `DS4` | `—` |
| `route-login` | `route-login` | 0 | `rebind_pending` | `pending` | `DS5` | `—` |
| `route-home-mode-aware` | `route-home-mode-aware` | 0 | `rebind_pending` | `pending` | `DS4` | `—` |
| `route-home-clerk-duplicate` | `route-home-clerk-duplicate` | 0 | `deleted` | `strangled` | `DS19` | `census-duplicate-clerk-index-delete` |
| `route-compose` | `route-compose` | 0 | `rebind_pending` | `pending` | `DS9` | `—` |
| `route-runs-list` | `route-runs-list` | 0 | `rebind_pending` | `pending` | `DS7` | `—` |
| `route-runs-compare` | `route-runs-compare` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `route-runs-compare-legacy` | `route-runs-compare-legacy` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `route-run-report` | `route-run-report` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `route-run-deck` | `route-run-deck` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `route-run-detail-layout` | `route-run-detail-layout` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `route-run-detail-index-redirect` | `route-run-detail-index-redirect` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `route-run-overview` | `route-run-overview` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `route-run-causal` | `route-run-causal` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `route-run-governance` | `route-run-governance` | 0 | `rebind_pending` | `pending` | `DS9` | `—` |
| `route-run-evidence` | `route-run-evidence` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `route-run-workflow` | `route-run-workflow` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `route-run-artifacts` | `route-run-artifacts` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `route-run-agents` | `route-run-agents` | 0 | `rebind_pending` | `pending` | `DS14` | `—` |
| `route-run-debug` | `route-run-debug` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `route-artifact` | `route-artifact` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `route-evidence` | `route-evidence` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `route-knowledge` | `route-knowledge` | 0 | `rebind_pending` | `pending` | `DS10` | `—` |
| `route-platform` | `route-platform` | 0 | `rebind_pending` | `pending` | `DS6` | `—` |
| `route-redirect-launch` | `route-redirect-launch` | 0 | `use_as_is` | `not_applicable` | `DS4` | `—` |
| `route-redirect-sources` | `route-redirect-sources` | 0 | `use_as_is` | `not_applicable` | `DS4` | `—` |
| `route-redirect-data` | `route-redirect-data` | 0 | `use_as_is` | `not_applicable` | `DS4` | `—` |
| `route-redirect-lex` | `route-redirect-lex` | 0 | `use_as_is` | `not_applicable` | `DS4` | `—` |
| `route-redirect-health` | `route-redirect-health` | 0 | `use_as_is` | `not_applicable` | `DS4` | `—` |
| `route-catch-all` | `route-catch-all` | 0 | `rebind_pending` | `pending` | `DS4` | `—` |
| `reference-shell-runs` | `reference-shell-runs` | 0 | `rebind_pending` | `pending` | `DS3` | `—` |
| `reference-shell-timeline` | `reference-shell-timeline` | 0 | `rebind_pending` | `pending` | `DS3` | `—` |
| `reference-shell-node-debug` | `reference-shell-node-debug` | 0 | `rebind_pending` | `pending` | `DS3` | `—` |
| `reference-shell-artifacts` | `reference-shell-artifacts` | 0 | `rebind_pending` | `pending` | `DS3` | `—` |
| `feature-artifacts` | `feature-artifacts` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `feature-auth` | `feature-auth` | 0 | `rebind_pending` | `pending` | `DS5` | `—` |
| `feature-causal` | `feature-causal` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `feature-clerk` | `feature-clerk` | 0 | `rebind_pending` | `pending` | `DS14` | `—` |
| `feature-collaboration` | `feature-collaboration` | 0 | `deleted` | `strangled` | `DS19` | `census-collaboration-delete` |
| `feature-command-palette` | `feature-command-palette` | 0 | `rebind_pending` | `pending` | `DS10` | `—` |
| `feature-composer` | `feature-composer` | 0 | `rebind_pending` | `pending` | `DS9` | `—` |
| `feature-dashboard` | `feature-dashboard` | 0 | `rebind_pending` | `pending` | `DS7` | `—` |
| `feature-evidence` | `feature-evidence` | 0 | `rebind_pending` | `pending` | `DS9` | `—` |
| `feature-export` | `feature-export` | 0 | `rebind_pending` | `pending` | `DS12` | `—` |
| `feature-landing` | `feature-landing` | 0 | `rebind_pending` | `pending` | `DS11` | `—` |
| `feature-layout-empty` | `feature-layout-empty` | 0 | `deleted` | `strangled` | `DS19` | `census-layout-placeholder-delete` |
| `feature-lex` | `feature-lex` | 0 | `rebind_pending` | `pending` | `DS10` | `—` |
| `feature-onboarding-orphan` | `feature-onboarding-orphan` | 0 | `deleted` | `strangled` | `DS19` | `census-onboarding-delete` |
| `feature-platform` | `feature-platform` | 0 | `rebind_pending` | `pending` | `DS6` | `—` |
| `feature-runs` | `feature-runs` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `feature-whatif` | `feature-whatif` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `ui-primitives-root` | `ui-primitives-root` | 21 | `rebind_pending` | `strangled` | `DS4` | `census-ds4-c03b-dormant-primitives` |
| `ui-compounds-root` | `ui-compounds-root` | 3 | `rebind_pending` | `pending` | `DS4` | `—` |
| `ui-operator-diagnostics` | `ui-operator-diagnostics` | 0 | `rebind_pending` | `strangled` | `DS4` | `dashboard-operator-diagnostic-generated-evidence-rebind` |
| `ui-authored-text` | `ui-authored-text` | 11 | `rebind_pending` | `strangled` | `DS4` | `dashboard-authored-candidate-posture` |
| `ui-compounds` | `ui-compounds` | 24 | `rebind_pending` | `strangled` | `DS4` | `dashboard-compound-evidence-generated-waist-rebind` |
| `ui-counterfactual` | `ui-counterfactual` | 4 | `rebind_pending` | `strangled` | `DS4` | `dashboard-counterfactual-generated-scenario-rebind` |
| `ui-patterns` | `ui-patterns` | 7 | `rebind_pending` | `pending` | `DS4` | `—` |
| `ui-quantity` | `ui-quantity` | 34 | `rebind_pending` | `strangled` | `DS4` | `dashboard-quantity-generated-waist-rebind` |
| `ui-responsive` | `ui-responsive` | 26 | `rebind_pending` | `pending` | `DS4` | `—` |
| `ui-temporal` | `ui-temporal` | 1 | `rebind_pending` | `strangled` | `DS4` | `dashboard-temporal-generated-waist-rebind` |
| `ui-trust-view` | `ui-trust-view` | 16 | `rebind_pending` | `strangled` | `DS4` | `dashboard-trust-view-generated-verification-rebind` |
| `ui-tokens` | `ui-tokens` | 26 | `rebind_pending` | `pending` | `DS4` | `—` |
| `api-op-analyze-attractors` | `api-op-analyze-attractors` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-persist-basin-map` | `api-op-persist-basin-map` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-persist-continuation-branch` | `api-op-persist-continuation-branch` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-analyze-lyapunov-diagnostics` | `api-op-analyze-lyapunov-diagnostics` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-attractor-analysis` | `api-op-get-attractor-analysis` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-analysis-basin-map` | `api-op-get-analysis-basin-map` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-analysis-continuation-branch` | `api-op-get-analysis-continuation-branch` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-artifact-batch` | `api-op-get-artifact-batch` | 0 | `wire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-artifact-manifest` | `api-op-get-artifact-manifest` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-get-artifact-content` | `api-op-get-artifact-content` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-download-artifact-content` | `api-op-download-artifact-content` | 0 | `wire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-artifact-lineage` | `api-op-get-artifact-lineage` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-get-artifact-schema` | `api-op-get-artifact-schema` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-export-bureaucratic-artifact` | `api-op-export-bureaucratic-artifact` | 0 | `wire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-render-bureaucratic-artifact` | `api-op-render-bureaucratic-artifact` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-get-auth-me` | `api-op-get-auth-me` | 0 | `rebind_pending` | `pending` | `DS5` | `—` |
| `api-op-estimate-causal-frontier-sae` | `api-op-estimate-causal-frontier-sae` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-control-capabilities` | `api-op-get-control-capabilities` | 0 | `rebind_pending` | `pending` | `DS10` | `—` |
| `api-op-list-binding-profiles` | `api-op-list-binding-profiles` | 0 | `wire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-cache-status` | `api-op-get-cache-status` | 0 | `rebind_pending` | `pending` | `DS3` | `—` |
| `api-op-search-data-catalog` | `api-op-search-data-catalog` | 0 | `rebind_pending` | `pending` | `DS10` | `—` |
| `api-op-list-connectors` | `api-op-list-connectors` | 0 | `rebind_pending` | `pending` | `DS15` | `—` |
| `api-op-discover-data-sources` | `api-op-discover-data-sources` | 0 | `rebind_pending` | `pending` | `DS15` | `—` |
| `api-op-get-data-index-stats` | `api-op-get-data-index-stats` | 0 | `rebind_pending` | `pending` | `DS10` | `—` |
| `api-op-ingest-data` | `api-op-ingest-data` | 0 | `rebind_pending` | `pending` | `DS15` | `—` |
| `api-op-preview-fetch-plan` | `api-op-preview-fetch-plan` | 0 | `rebind_pending` | `pending` | `DS15` | `—` |
| `api-op-list-source-profiles` | `api-op-list-source-profiles` | 0 | `rebind_pending` | `pending` | `DS15` | `—` |
| `api-op-list-data-promotion-candidates` | `api-op-list-data-promotion-candidates` | 0 | `rebind_pending` | `pending` | `DS9` | `—` |
| `api-op-approve-data-promotion` | `api-op-approve-data-promotion` | 0 | `rebind_pending` | `pending` | `DS9` | `—` |
| `api-op-reject-data-promotion` | `api-op-reject-data-promotion` | 0 | `rebind_pending` | `pending` | `DS9` | `—` |
| `api-op-resolve-data-needs` | `api-op-resolve-data-needs` | 0 | `rebind_pending` | `pending` | `DS15` | `—` |
| `api-op-get-packet-decision-validity` | `api-op-get-packet-decision-validity` | 0 | `wire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-publish-decision-validity-event` | `api-op-publish-decision-validity-event` | 0 | `wire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-control-job-status` | `api-op-get-control-job-status` | 0 | `rebind_pending` | `pending` | `DS14` | `—` |
| `api-op-get-lex-graph-stats` | `api-op-get-lex-graph-stats` | 0 | `rebind_pending` | `pending` | `DS10` | `—` |
| `api-op-search-lex-graph` | `api-op-search-lex-graph` | 0 | `rebind_pending` | `pending` | `DS10` | `—` |
| `api-op-get-lex-pipeline-status` | `api-op-get-lex-pipeline-status` | 0 | `rebind_pending` | `pending` | `DS10` | `—` |
| `api-op-trigger-lex-pipeline` | `api-op-trigger-lex-pipeline` | 0 | `rebind_pending` | `pending` | `DS10` | `—` |
| `api-op-list-llm-profiles` | `api-op-list-llm-profiles` | 0 | `rebind_pending` | `pending` | `DS14` | `—` |
| `api-op-list-control-outbox` | `api-op-list-control-outbox` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-launch-run` | `api-op-launch-run` | 0 | `rebind_pending` | `pending` | `DS9` | `—` |
| `api-op-launch-nl-run` | `api-op-launch-nl-run` | 0 | `rebind_pending` | `pending` | `DS14` | `—` |
| `api-op-get-run-decision-validity` | `api-op-get-run-decision-validity` | 0 | `wire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-evaluate-run-feedback` | `api-op-evaluate-run-feedback` | 0 | `wire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-reissue-run` | `api-op-reissue-run` | 0 | `wire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-list-control-workers` | `api-op-list-control-workers` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-run-compare` | `api-op-get-run-compare` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-run-equilibria` | `api-op-get-run-equilibria` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-run-errors` | `api-op-get-run-errors` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-get-run-feedback` | `api-op-get-run-feedback` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-governance-debug` | `api-op-get-governance-debug` | 0 | `rebind_pending` | `pending` | `DS9` | `—` |
| `api-op-get-node-debug` | `api-op-get-node-debug` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-analyze-fabric-impact` | `api-op-analyze-fabric-impact` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-fabric-quality-batch` | `api-op-get-fabric-quality-batch` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-fabric-run-replay` | `api-op-get-fabric-run-replay` | 0 | `wire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-fabric-source-scorecards` | `api-op-get-fabric-source-scorecards` | 0 | `wire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-fabric-trust-batch` | `api-op-get-fabric-trust-batch` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-runtime-api-health` | `api-op-runtime-api-health` | 0 | `rebind_pending` | `pending` | `DS6` | `—` |
| `api-op-get-lineage-batch` | `api-op-get-lineage-batch` | 0 | `rebind_pending` | `pending` | `DS3` | `—` |
| `api-op-get-lineage` | `api-op-get-lineage` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-export-lineage-openlineage` | `api-op-export-lineage-openlineage` | 0 | `rebind_pending` | `pending` | `DS3` | `—` |
| `api-op-export-lineage-prov` | `api-op-export-lineage-prov` | 0 | `rebind_pending` | `pending` | `DS3` | `—` |
| `api-op-compute-mobility-bounds` | `api-op-compute-mobility-bounds` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-estimate-mobility` | `api-op-estimate-mobility` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-mobility-report` | `api-op-get-mobility-report` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-mobility-report-bounds` | `api-op-get-mobility-report-bounds` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-mobility-report-diagnostics` | `api-op-get-mobility-report-diagnostics` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-list-runs` | `api-op-list-runs` | 0 | `rebind_pending` | `pending` | `DS7` | `—` |
| `api-op-get-runs-batch` | `api-op-get-runs-batch` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-compare-runs` | `api-op-compare-runs` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-get-run-details` | `api-op-get-run-details` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-get-run-agents` | `api-op-get-run-agents` | 0 | `rebind_pending` | `pending` | `DS14` | `—` |
| `api-op-get-run-compare-candidates` | `api-op-get-run-compare-candidates` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-get-run-evidence-context` | `api-op-get-run-evidence-context` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-get-run-fabric-decision-data` | `api-op-get-run-fabric-decision-data` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-get-run-lineage` | `api-op-get-run-lineage` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-get-run-counterfactual-metrics` | `api-op-get-run-counterfactual-metrics` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-get-run-nodes` | `api-op-get-run-nodes` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-create-run-production-approval` | `api-op-create-run-production-approval` | 0 | `wire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-run-quantities` | `api-op-get-run-quantities` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-list-run-scenarios` | `api-op-list-run-scenarios` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-create-run-scenario` | `api-op-create-run-scenario` | 0 | `wire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-get-run-timeline` | `api-op-get-run-timeline` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-get-run-workflow` | `api-op-get-run-workflow` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-get-scenario-manifest` | `api-op-get-scenario-manifest` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-get-scenario-capabilities` | `api-op-get-scenario-capabilities` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `api-op-get-temporal-capabilities` | `api-op-get-temporal-capabilities` | 0 | `rebind_pending` | `pending` | `DS18` | `—` |
| `api-op-health` | `api-op-health` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `api-op-ready` | `api-op-ready` | 0 | `retire_disposition` | `not_applicable` | `DS3` | `—` |
| `raw-fetch-auth-refresh` | `raw-fetch-auth-refresh` | 0 | `rebind_pending` | `pending` | `DS5` | `—` |
| `raw-fetch-auth-initial` | `raw-fetch-auth-initial` | 0 | `rebind_pending` | `pending` | `DS5` | `—` |
| `raw-fetch-auth-replay` | `raw-fetch-auth-replay` | 0 | `rebind_pending` | `pending` | `DS5` | `—` |
| `raw-fetch-flag-manifest` | `raw-fetch-flag-manifest` | 0 | `rebind_pending` | `pending` | `DS5` | `—` |
| `raw-fetch-collab-activity` | `raw-fetch-collab-activity` | 0 | `deleted` | `strangled` | `DS19` | `census-collaboration-delete` |
| `raw-fetch-collab-comments-get` | `raw-fetch-collab-comments-get` | 0 | `deleted` | `strangled` | `DS19` | `census-collaboration-delete` |
| `raw-fetch-collab-comment-post` | `raw-fetch-collab-comment-post` | 0 | `deleted` | `strangled` | `DS19` | `census-collaboration-delete` |
| `raw-fetch-collab-resolve` | `raw-fetch-collab-resolve` | 0 | `deleted` | `strangled` | `DS19` | `census-collaboration-delete` |
| `raw-fetch-telemetry` | `raw-fetch-telemetry` | 0 | `rebind_pending` | `pending` | `DS12` | `—` |
| `status-auth-session` | `status-auth-session` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-offline-queue-item` | `status-offline-queue-item` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-feature-flag` | `status-feature-flag` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-runs-live` | `status-runs-live` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-causal-edge-identification` | `status-causal-edge-identification` | 0 | `rebind_pending` | `strangled` | `DS4` | `dashboard-causal-draft-identification-display` |
| `status-causal-pipeline-stage` | `status-causal-pipeline-stage` | 0 | `rebind_pending` | `strangled` | `DS4` | `dashboard-causal-pipeline-progress-state` |
| `status-collaboration-session` | `status-collaboration-session` | 0 | `deleted` | `strangled` | `DS19` | `census-collaboration-delete` |
| `status-health-check` | `status-health-check` | 0 | `rebind_pending` | `strangled` | `DS4` | `dashboard-system-health-interaction-state` |
| `status-share-trust-fixture` | `status-share-trust-fixture` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-comparability-api-alias` | `status-comparability-api-alias` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-narrative-chapter` | `status-narrative-chapter` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-dispute-run` | `status-dispute-run` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-publication-argument-node` | `status-publication-argument-node` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-stress-scene` | `status-stress-scene` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-agent-step` | `status-agent-step` | 0 | `rebind_pending` | `strangled` | `DS4` | `generated-agent-pipeline-step-status` |
| `status-agent-performance-budget` | `status-agent-performance-budget` | 0 | `rebind_pending` | `strangled` | `DS4` | `dashboard-performance-budget-interaction-state` |
| `status-workflow-node` | `status-workflow-node` | 0 | `rebind_pending` | `strangled` | `DS4` | `generated-run-workflow-node-status` |
| `status-governance-pass` | `status-governance-pass` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-quantity-provenance` | `status-quantity-provenance` | 0 | `rebind_pending` | `strangled` | `DS4` | `quantity-independent-owner-metadata` |
| `status-scenario` | `status-scenario` | 0 | `rebind_pending` | `strangled` | `DS4` | `runtime-scenario-ref-status` |
| `status-verification` | `status-verification` | 0 | `rebind_pending` | `strangled` | `DS4` | `runtime-lineage-verification-status` |
| `status-dispute-quantity` | `status-dispute-quantity` | 0 | `rebind_pending` | `strangled` | `DS4` | `runtime-verification-metadata-dispute-status` |
| `status-dispute-trust-view` | `status-dispute-trust-view` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-promotion-decision` | `status-inline-promotion-decision` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-queued-promotion` | `status-inline-queued-promotion` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-authz-provider` | `status-inline-authz-provider` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-visual-fixture` | `status-inline-visual-fixture` | 0 | `rebind_pending` | `strangled` | `DS4` | `dashboard-fixture-timeline-playback-state` |
| `status-inline-review-indicators` | `status-inline-review-indicators` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-review-surface` | `status-inline-review-surface` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-bureaucratic-block` | `status-inline-bureaucratic-block` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-bureaucratic-section` | `status-inline-bureaucratic-section` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-data-freshness` | `status-inline-data-freshness` | 0 | `rebind_pending` | `strangled` | `DS4` | `dashboard-data-freshness-interaction-state` |
| `status-inline-compliance-badge` | `status-inline-compliance-badge` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-choreography-stage` | `status-inline-choreography-stage` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-choreography-transition` | `status-inline-choreography-transition` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-publication-claim` | `status-inline-publication-claim` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-publication-ground` | `status-inline-publication-ground` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-readiness-evidence` | `status-inline-readiness-evidence` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-readiness-gate` | `status-inline-readiness-gate` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-readiness-review` | `status-inline-readiness-review` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-run-narrative` | `status-inline-run-narrative` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-governance-comparison-left` | `status-inline-governance-comparison-left` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-governance-comparison-right` | `status-inline-governance-comparison-right` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-small-multiples` | `status-inline-small-multiples` | 0 | `rebind_pending` | `strangled` | `DS4` | `runtime-verification-metadata-small-multiples` |
| `status-inline-route-loader` | `status-inline-route-loader` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-explainability` | `status-inline-explainability` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-counterfactual-badge` | `status-inline-counterfactual-badge` | 0 | `rebind_pending` | `strangled` | `DS4` | `runtime-scenario-ref-status` |
| `flag-enable-atlas-v2` | `flag-enable-atlas-v2` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `flag-enable-clerk-mode` | `flag-enable-clerk-mode` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `flag-enable-dark-mode` | `flag-enable-dark-mode` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `flag-enable-lex-knowledge` | `flag-enable-lex-knowledge` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `flag-enable-narrative-view` | `flag-enable-narrative-view` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `flag-enable-platform-health` | `flag-enable-platform-health` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `flag-enable-runs-workspace` | `flag-enable-runs-workspace` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `flag-enable-scenario-composer` | `flag-enable-scenario-composer` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `flag-enable-causal-graph` | `flag-enable-causal-graph` | 0 | `wire_disposition` | `not_applicable` | `DS5` | `—` |
| `flag-enable-collaboration` | `flag-enable-collaboration` | 0 | `retire_disposition` | `not_applicable` | `DS5` | `—` |
| `flag-enable-command-palette` | `flag-enable-command-palette` | 0 | `wire_disposition` | `not_applicable` | `DS5` | `—` |
| `flag-enable-what-if-analysis` | `flag-enable-what-if-analysis` | 0 | `wire_disposition` | `not_applicable` | `DS5` | `—` |
| `flag-auth-review-collaboration` | `flag-auth-review-collaboration` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `transport-openapi-dashboard` | `transport-openapi-dashboard` | 0 | `rebind_pending` | `pending` | `DS3` | `—` |
| `transport-openapi-reference-shell` | `transport-openapi-reference-shell` | 0 | `rebind_pending` | `pending` | `DS3` | `—` |
| `transport-rest-collaboration` | `transport-rest-collaboration` | 0 | `deleted` | `strangled` | `DS19` | `census-collaboration-delete` |
| `transport-sse-runs-global` | `transport-sse-runs-global` | 0 | `rebind_pending` | `pending` | `DS3` | `—` |
| `transport-sse-run-detail` | `transport-sse-run-detail` | 0 | `rebind_pending` | `pending` | `DS3` | `—` |
| `transport-ws-review` | `transport-ws-review` | 0 | `rebind_pending` | `pending` | `DS5` | `—` |
| `transport-ws-collaboration` | `transport-ws-collaboration` | 0 | `deleted` | `strangled` | `DS19` | `census-collaboration-delete` |
| `worker-data-transform` | `worker-data-transform` | 0 | `deleted` | `strangled` | `DS19` | `census-zero-consumer-workers-delete` |
| `worker-dag-layout` | `worker-dag-layout` | 0 | `deleted` | `strangled` | `DS19` | `census-zero-consumer-workers-delete` |
| `worker-json-parse` | `worker-json-parse` | 0 | `deleted` | `strangled` | `DS19` | `census-zero-consumer-workers-delete` |
| `cache-service-worker-static` | `cache-service-worker-static` | 0 | `rebind_pending` | `pending` | `DS5` | `—` |
| `offline-queue-promotion-decision` | `offline-queue-promotion-decision` | 0 | `rebind_pending` | `pending` | `DS5` | `—` |
| `offline-draft-composer` | `offline-draft-composer` | 0 | `rebind_pending` | `pending` | `DS5` | `—` |
| `cache-query-memory` | `cache-query-memory` | 0 | `rebind_pending` | `pending` | `DS5` | `—` |
| `cache-local-storage-state` | `cache-local-storage-state` | 0 | `rebind_pending` | `pending` | `DS5` | `—` |
| `cache-clerk-sessions` | `cache-clerk-sessions` | 0 | `rebind_pending` | `pending` | `DS14` | `—` |
| `cache-whatif-scenarios` | `cache-whatif-scenarios` | 0 | `deleted` | `strangled` | `DS19` | `census-whatif-local-subgraph-delete` |
| `cache-causal-drafts` | `cache-causal-drafts` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `cache-local-disputes` | `cache-local-disputes` | 0 | `rebind_pending` | `pending` | `DS9` | `—` |
| `cache-review-attention` | `cache-review-attention` | 0 | `rebind_pending` | `pending` | `DS9` | `—` |
| `cache-operator-craft` | `cache-operator-craft` | 0 | `rebind_pending` | `pending` | `DS9` | `—` |
| `transport-telemetry-beacon` | `transport-telemetry-beacon` | 0 | `rebind_pending` | `pending` | `DS12` | `—` |
| `transport-sentry` | `transport-sentry` | 0 | `rebind_pending` | `pending` | `DS12` | `—` |
| `derivation-projection-fail-closed` | `derivation-projection-fail-closed` | 0 | `rebind_pending` | `strangled` | `DS4` | `generated-policy-design-case-projection-pass-through` |
| `derivation-browser-signature` | `derivation-browser-signature` | 0 | `rebind_pending` | `pending` | `DS12` | `census-browser-signing-protected-live` |
| `derivation-causal-effects` | `derivation-causal-effects` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `derivation-composer-readiness` | `derivation-composer-readiness` | 0 | `rebind_pending` | `pending` | `DS9` | `—` |
| `derivation-whatif-validation` | `derivation-whatif-validation` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `adjacent-cli-styleguide` | `adjacent-cli-styleguide` | 0 | `rebind_pending` | `pending` | `DS4` | `—` |
| `adjacent-print-export` | `adjacent-print-export` | 0 | `rebind_pending` | `pending` | `DS8` | `—` |
| `adjacent-email-og` | `adjacent-email-og` | 0 | `rebind_pending` | `pending` | `DS12` | `—` |
| `evidence-unit-tests` | `evidence-unit-tests` | 0 | `rebind_pending` | `pending` | `DS6` | `—` |
| `evidence-stories` | `evidence-stories` | 0 | `rebind_pending` | `pending` | `DS6` | `—` |
| `evidence-component-a11y` | `evidence-component-a11y` | 0 | `rebind_pending` | `pending` | `DS6` | `—` |
| `evidence-browser-a11y` | `evidence-browser-a11y` | 0 | `rebind_pending` | `pending` | `DS6` | `—` |
| `evidence-e2e-journeys` | `evidence-e2e-journeys` | 0 | `rebind_pending` | `pending` | `DS6` | `—` |
| `evidence-visual` | `evidence-visual` | 0 | `rebind_pending` | `pending` | `DS6` | `—` |
| `evidence-manual-at` | `evidence-manual-at` | 0 | `rebind_pending` | `pending` | `DS6` | `—` |
<!-- END DS19 REGISTER PROJECTION -->

## Commits

- `f444ba719 refactor(dashboard): fail closed on counterfactual projections`
- `a59efb3dc refactor(dashboard): rebind operator evidence primitives`
- `8a8c8169e refactor(dashboard): rebind trust view authority`
- `c4e1b97e3 refactor(dashboard): rebind authored candidate posture`
- `9c45a240e fix(dashboard): rebind temporal semantics and cursor`
- `0ef16da1b fix(dashboard): classify nondecision numeric layout values`
- `07ed51c81 refactor(dashboard): preserve chart quantity semantics`
- `290bb5e61 refactor(dashboard): wrap decision producers as quantities`
- `e57b241a0 test(dashboard): govern the status retirement inventory`
- `5127af28d feat(atlas-ui): project ratified DTCG token parity`
- `a2c9ae8b0 chore(dashboard): retire dormant overlay primitives`
- `caa1ee6e3 feat(atlas-ui): migrate living overlay primitives`
- `2dbf604e0 feat(atlas-ui): migrate form primitives`
- `018328d68 feat(atlas-ui): migrate foundation primitives`
- `61d354f62 docs: plan Atlas DS4 status grammar rebinding`
- `71f438ad5 docs: Atlas plan — DS3 closed & merged; debt table extended`
- `e451cec56 merge: land Atlas DS3 — runtime producers & export infrastructure`
- `028ddde5d docs(atlas): close DS3 exact-head review`
- `7050786f2 fix(runtime): close DS3 exact-head review`
- `a906ed7c1 chore(pdc): rebind N13a census route identities`
- `687545824 fix(pdc): rebind N10 capstone context provenance`
- `c9a477a9f docs(atlas): close DS3 second review`
- `202c1e48f test(runtime): consume merged DS19 strangle`
- `18a7e62ba docs: Atlas plan Rev 3.1 — DS19 closed; inherited baseline debt of record`
- `f9f69e807 merge: land Atlas DS19 — false-substrate strangle wave + frontend disposition register`
- `952a52a44 fix(runtime): bind projections to owner validation`
- `ee793cfa9 chore(frontend): close DS19 for architect review`
- `3d245d4fd test(frontend): verify DS19 deletion wave`
- `8a4db34e2 docs(atlas): record DS3 review repairs`
- `4a4f2a56b refactor(frontend): delete dead WhatIf parameter subgraph`
- `42fcabe17 refactor(frontend): delete duplicate Clerk index route`
- `99090d923 fix(runtime): close DS3 producer review findings`
- `b66e77314 refactor(frontend): delete zero-consumer workers`
- `9b25c0ca0 refactor(frontend): delete empty layout placeholder`
- `2bbdfac4e refactor(frontend): delete orphan onboarding`
- `df87559b3 refactor(frontend): delete phantom collaboration substrate`
- `7c648b045 chore(pdc): rebind composition to canonical L6 context`
- `702256135 feat(frontend): establish DS19 disposition authority`
- `46447ae67 chore(pdc): converge second-domain N8 provenance`
- `9a0e2b743 docs(atlas): close DS3 producer evidence`
- `f167adb04 chore(pdc): rebind N8 to canonical L6 context`
- `48118be16 feat(runtime): bind existing exports to replay contract`
- `8eed73d7d chore(pdc): rebind second-domain pack to canonical L6`
- `6e71f9fc3 fix(quality): unblock canonical L6 provenance replay`
- `3b2c2cd91 build(runtime): regenerate shared API client contract`
- `a92fcce6e feat(runtime): preserve Lex truth through HTTP projection`
- `34545cdde feat(runtime): expose governed artifact projections`
- `986a54daa chore(pdc): canonicalize L6 receipt provenance`
- `d01eaa572 chore(frontend): repair dashboard typecheck baseline`
- `e979a5cf4 test(atlas): seed DS3 producer contract negatives`
- `9516d35cb docs(atlas): bind DS3 runtime producer plan`

The final documentation/report commit cannot self-record its own hash. The
architect review handoff includes that hash separately. No merge is performed.
