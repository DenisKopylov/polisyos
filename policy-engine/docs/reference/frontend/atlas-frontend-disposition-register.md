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

- Application lines added: **47309**
- Application lines deleted: **20420**
- Net application LOC reduction: **-26889**
- Application files deleted: **89**

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
| Register/check | schema, 261 DS1 roots, 233 DS2 edges, 10 live censuses, report parity, links, source hashes, and corruption probes PASS | disposition authority current |
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
| `deleted` | 19 |
| `rebind_pending` | 184 |
| `retire_disposition` | 25 |
| `use_as_is` | 17 |
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
| review-attention | `cache-review-attention` | zero_consumers | `deleted` | `architecture/atlas_surfaces/test_atlas_enforcement.py`, `architecture/atlas_surfaces/test_frontend_disposition_register.py`, `docs/plans/active/atlas-slices/DS5-enforcement-waist-journal.md` |

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
| `flag-enable-causal-graph` | `wire_disposition` | `DS5` | C19 wires enableCausalGraph through the direct-route gate, run-detail tab filtering, and causal command-palette entries; focused route and palette tests prove a false flag hides the route, normal tab, root, and descendants while permissions remain independent. The client loader may prime data before the context gate redirects, but no causal surface is exposed. |
| `flag-enable-collaboration` | `retire_disposition` | `DS5` | C19 removes enableCollaboration from the canonical manifest keys and registry; the environment-boundary test proves the retired key is rejected atomically, while the refreshed zero registry-entry census proves no live construction remains. The separate enableReviewCollaboration authz override is unchanged. |
| `flag-enable-command-palette` | `wire_disposition` | `DS5` | C19 gates both CommandPalette mounting and global shortcut registration with enableCommandPalette; focused layout and palette tests prove a false flag removes UI and keyboard entry without changing permission authority. |
| `flag-enable-what-if-analysis` | `wire_disposition` | `DS5` | C19 gates the AppShell counterfactual rail and the Overview scenario workbench with enableWhatIfAnalysis; focused layout and run-detail tests prove a false flag removes both surfaces and cannot grant or replace permission. |

### Persistence construction census

Declaration-resolved production denominator: **574 TS/TSX sources**, **36 sites / 15 files**. Classes: **14 scoped authority**, **22 interaction benign**, **0 rollout cache pending**; **9 independently content-bound authority factory declarations**. Direct construction facts are `recomputed`; semantic classes are `institutionally_supplied`; exact site-to-owner-instance flow is `not_established`.

Declared bounded residual: site-to-owner-instance provider, receiver, key, and payload value flow is outside the declaration-resolved direct-construction census. Falsifier: `const storage = provider(); storage.setItem(...) preserves a resolved Storage.setItem site while changing the unproved owner-instance flow`. Closing it requires sound whole-program interprocedural data/control-flow with reaching definitions and owner-instance identity; repository capability status: `absent/unallocated`.

| Site | Declared adjudication | Resolved API / operation | Store owner | Source | Fingerprints | Posture |
| --- | --- | --- | --- | --- | --- | --- |
| `storage-site-82510a28616480aab3bb2b282ff9e6b7d0a82a8e1c48b63e1c2a15a44de2df2b` | `scoped_authority` | `typescript/lib/lib.dom.d.ts::Storage.getItem` / `getItem` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` | `fe3dbe8201a7` / `db4d83c5f87f` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` / `authority-local-state-envelope-v1`; authority flow `not_established` |
| `storage-site-4d8f77f82e9ee648e28b94559b50152d8f4f7ef2247044319f61d1c762e6df3c` | `scoped_authority` | `typescript/lib/lib.dom.d.ts::Storage.setItem` / `setItem` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` | `fe3dbe8201a7` / `8c8d9fb61c39` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` / `authority-local-state-envelope-v1`; authority flow `not_established` |
| `storage-site-30109455714193156e695ebb76de40e1dd7c713c37134f93d7e9e2e2d7e9d073` | `scoped_authority` | `idb::get` / `get` | `apps/runtime-dashboard/src/features/composer/state/composerDraftRepository.ts` | `apps/runtime-dashboard/src/app/offline/composerDraftDb.ts` | `1b6e8c724e4c` / `71555bd946dd` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` / `composer-draft-v1`; authority flow `not_established` |
| `storage-site-115f5f50e836a6f341d240bb8b1bcf7d04d8f70035764295eaeda6f5bef58830` | `scoped_authority` | `idb::put` / `put` | `apps/runtime-dashboard/src/features/composer/state/composerDraftRepository.ts` | `apps/runtime-dashboard/src/app/offline/composerDraftDb.ts` | `1b6e8c724e4c` / `cd80d80f674a` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` / `composer-draft-v1`; authority flow `not_established` |
| `storage-site-2812777f4bad3bbbb26690108c006a75d57f72239510ac3fbdda785573596818` | `scoped_authority` | `idb::delete` / `delete` | `apps/runtime-dashboard/src/features/composer/state/composerDraftRepository.ts` | `apps/runtime-dashboard/src/app/offline/composerDraftDb.ts` | `1b6e8c724e4c` / `2da9793449f4` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` / `composer-draft-v1`; authority flow `not_established` |
| `storage-site-a65e9e41c63f480c9ff8f0d4ac322385a2e87c49d48b805e536f350d8a0a9fc9` | `scoped_authority` | `idb::openDB` / `openDB` | `apps/runtime-dashboard/src/features/composer/state/composerDraftRepository.ts` | `apps/runtime-dashboard/src/app/offline/db.ts` | `52f77e69ca89` / `2c26efab04f7` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` / `composer-draft-v1`; authority flow `not_established` |
| `storage-site-a0b9ca9ee8a58915ac642421094f802a3c8420ad57955ccf83a99af37560905c` | `scoped_authority` | `idb::createObjectStore` / `createObjectStore` | `apps/runtime-dashboard/src/features/composer/state/composerDraftRepository.ts` | `apps/runtime-dashboard/src/app/offline/db.ts` | `52f77e69ca89` / `d07aa1e764e5` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` / `composer-draft-v1`; authority flow `not_established` |
| `storage-site-16fd635bf34fe09f73e3b44a31ccfafad75156b796e8859f9b9cbc538cfe0e14` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Storage.getItem` / `getItem` | `apps/runtime-dashboard/src/app/providers/InterfaceModeProvider.tsx` | `apps/runtime-dashboard/src/app/providers/InterfaceModeProvider.tsx` | `e9b75f8537ba` / `0fe71b65d6fa` | `ui_preference` |
| `storage-site-23548efc36e0219011a48a6724ae68ec5d4628af0defc812fc01201a99791e92` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Storage.setItem` / `setItem` | `apps/runtime-dashboard/src/app/providers/InterfaceModeProvider.tsx` | `apps/runtime-dashboard/src/app/providers/InterfaceModeProvider.tsx` | `e9b75f8537ba` / `c3d419e3d41c` | `ui_preference` |
| `storage-site-0dbde606ec251f4e52ff7fd880f30e052ecf4c6e079a27e5687507cc88c2c8f7` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Storage.getItem` / `getItem` | `apps/runtime-dashboard/src/app/providers/ThemeProvider.tsx` | `apps/runtime-dashboard/src/app/providers/ThemeProvider.tsx` | `bf14023a0a5f` / `62482b685c28` | `theme` |
| `storage-site-a74c7659e6f35601921ba6be48de09e484a5f29177a651ea035a32920d370a93` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Storage.setItem` / `setItem` | `apps/runtime-dashboard/src/app/providers/ThemeProvider.tsx` | `apps/runtime-dashboard/src/app/providers/ThemeProvider.tsx` | `bf14023a0a5f` / `51e3d2952a4f` | `theme` |
| `storage-site-329d8de4da47acace6e2e32e15aa05598bed6e289730277a0e5fdc5f96d2a73d` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Storage.getItem` / `getItem` | `apps/runtime-dashboard/src/app/providers/TrustViewProvider.tsx` | `apps/runtime-dashboard/src/app/providers/TrustViewProvider.tsx` | `1ab5964b99bc` / `3d0568d4c661` | `ui_preference` |
| `storage-site-efe95ffd4464c44b760c3a4e1a67ed87a773292648a265c7161bdfe38cc3f2d5` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Storage.setItem` / `setItem` | `apps/runtime-dashboard/src/app/providers/TrustViewProvider.tsx` | `apps/runtime-dashboard/src/app/providers/TrustViewProvider.tsx` | `1ab5964b99bc` / `f0a9f5381eae` | `ui_preference` |
| `storage-site-eff54e9a5215a602daf5630ea95130795ec90cd80ba979fc4ecca71ec9105cc6` | `interaction_benign` | `zustand/middleware::persist` / `persist` | `apps/runtime-dashboard/src/app/state/usePreferencesStore.ts` | `apps/runtime-dashboard/src/app/state/usePreferencesStore.ts` | `994b51046b9f` / `62f491bea38e` | `ui_preference` |
| `storage-site-9cea128f712d1ed1848977ef80db0c50035b69815b6f22862551b98310fe1361` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Storage.getItem` / `getItem` | `apps/runtime-dashboard/src/app/state/usePreferencesStore.ts` | `apps/runtime-dashboard/src/app/state/usePreferencesStore.ts` | `994b51046b9f` / `cf00005078c7` | `ui_preference` |
| `storage-site-e8e788c9df1bdaa180027ca1442ab6b9d9c34161129e39637d9f186a5cf8161b` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Storage.getItem` / `getItem` | `apps/runtime-dashboard/src/app/state/useRunsLivePreferenceStore.ts` | `apps/runtime-dashboard/src/app/state/useRunsLivePreferenceStore.ts` | `9c6d1bb092d4` / `ed0c399486af` | `ui_preference` |
| `storage-site-a9d23a198b0e7b28d1198b170461fd00b37cb2509def77c4fdf0aee2705db1b4` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Storage.removeItem` / `removeItem` | `apps/runtime-dashboard/src/app/state/useRunsLivePreferenceStore.ts` | `apps/runtime-dashboard/src/app/state/useRunsLivePreferenceStore.ts` | `9c6d1bb092d4` / `be87b439881f` | `ui_preference` |
| `storage-site-c2b81c1e937dce9d85c3c2545f0f9f054eb805b8af60ade94e7148a9a605663d` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Storage.setItem` / `setItem` | `apps/runtime-dashboard/src/app/state/useRunsLivePreferenceStore.ts` | `apps/runtime-dashboard/src/app/state/useRunsLivePreferenceStore.ts` | `9c6d1bb092d4` / `83b71b7c882e` | `ui_preference` |
| `storage-site-5319297e1cb3990cd2cff0c2efdda8ba93735cf4fd3c68c28f516a599db01fb3` | `interaction_benign` | `zustand/middleware::persist` / `persist` | `apps/runtime-dashboard/src/app/state/useRunsLivePreferenceStore.ts` | `apps/runtime-dashboard/src/app/state/useRunsLivePreferenceStore.ts` | `9c6d1bb092d4` / `b91459b9e25d` | `ui_preference` |
| `storage-site-2afa9a6f31f495e80927aed7385b39bc2a10dd50f1cd83d511072b54ac9e9f25` | `interaction_benign` | `zustand/middleware::createJSONStorage` / `createJSONStorage` | `apps/runtime-dashboard/src/app/state/useRunsLivePreferenceStore.ts` | `apps/runtime-dashboard/src/app/state/useRunsLivePreferenceStore.ts` | `9c6d1bb092d4` / `51761bc5666a` | `ui_preference` |
| `storage-site-8239d22c7f77a369d97fb6a48bbbfffcf6b8a771634302d4936deb7e48f4cb0f` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Storage.getItem` / `getItem` | `apps/runtime-dashboard/src/app/state/useRunsLivePreferenceStore.ts` | `apps/runtime-dashboard/src/app/state/useRunsLivePreferenceStore.ts` | `9c6d1bb092d4` / `bae4c6206ee3` | `ui_preference` |
| `storage-site-95099d85b2a91ec570611998bec15df4bd314320aaded048a2d2dcadaabbd2ed` | `scoped_authority` | `typescript/lib/lib.dom.d.ts::Window.localStorage` / `acquire` | `apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts` | `apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts` | `394ffec7e8ff` / `4e4aa8087062` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` / `clerk-chat-sessions-v1`; authority flow `not_established` |
| `storage-site-c4b0eec11e781f705082fcf9fcd94b6865cd49ba14670a662165a6378131b628` | `scoped_authority` | `typescript/lib/lib.dom.d.ts::Storage.getItem` / `getItem` | `apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts` | `apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts` | `394ffec7e8ff` / `41673351af3b` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` / `clerk-chat-sessions-v1`; authority flow `not_established` |
| `storage-site-e3197d69b09afa722469ce0e22e3bf01adf7038eddd75de070c1b27c3f64bdef` | `scoped_authority` | `typescript/lib/lib.dom.d.ts::Storage.setItem` / `setItem` | `apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts` | `apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts` | `394ffec7e8ff` / `9254211607da` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` / `clerk-chat-sessions-v1`; authority flow `not_established` |
| `storage-site-978eef015dbbda52cd406bfc44b44295c9384bb63d93531bff09dcb357604878` | `scoped_authority` | `zustand/middleware::persist` / `persist` | `apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts` | `apps/runtime-dashboard/src/features/clerk/state/useChatStore.ts` | `394ffec7e8ff` / `e8de1ebe950f` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` / `clerk-chat-sessions-v1`; authority flow `not_established` |
| `storage-site-c6193aadc4f6a0e690999f7db6d3f30f21872a3c15ce5eb604fed46f020e9d4f` | `interaction_benign` | `zustand/middleware::persist` / `persist` | `apps/runtime-dashboard/src/features/dashboard/state/useDashboardLayoutStore.ts` | `apps/runtime-dashboard/src/features/dashboard/state/useDashboardLayoutStore.ts` | `9cd24ad38d84` / `3b84ad9036f5` | `ui_preference` |
| `storage-site-f51ff807af1565a3557c7e53a8d6c2e4a29f4b66a8dc86806c34ae8ea6e98f70` | `scoped_authority` | `typescript/lib/lib.dom.d.ts::Window.localStorage` / `acquire` | `apps/runtime-dashboard/src/features/runs/domain/disputes.ts` | `apps/runtime-dashboard/src/features/runs/domain/disputes.ts` | `03fe198af004` / `4e4aa8087062` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` / `dispute-topology-v1`; authority flow `not_established` |
| `storage-site-b502f3a54daa6a55ed0116c0556dc83893818684e3743285e82e1aa7b0a30c40` | `scoped_authority` | `typescript/lib/lib.dom.d.ts::Window.localStorage` / `acquire` | `apps/runtime-dashboard/src/features/runs/domain/operatorCraft.ts` | `apps/runtime-dashboard/src/features/runs/domain/operatorCraft.ts` | `c899d4a2acc9` / `f93e6557153c` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` / `operator-craft-family-codecs-v1`; authority flow `not_established` |
| `storage-site-28c02183482a1769a8cdf4e5a4d82e0e4792aa344ee1035b4d41ffcb121706bc` | `scoped_authority` | `typescript/lib/lib.dom.d.ts::Window.localStorage` / `acquire` | `apps/runtime-dashboard/src/features/runs/routes/tabs/CausalTab.tsx` | `apps/runtime-dashboard/src/features/runs/routes/tabs/CausalTab.tsx` | `9d5af744104b` / `4e4aa8087062` | `apps/runtime-dashboard/src/app/offline/authorityLocalState.ts` / `causal-draft-v1`; authority flow `not_established` |
| `storage-site-6e4acc5199d026aaa88c5f2a1c0a0d26a5c49928b150227a5452ff60090dabec` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Storage.getItem` / `getItem` | `apps/runtime-dashboard/src/shared/i18n/locale.ts` | `apps/runtime-dashboard/src/shared/i18n/locale.ts` | `aab3839c5166` / `eede4f6d129d` | `locale` |
| `storage-site-399705a043705ae1f1ec0cc91763cc5ff8043d3c167132da0dff4068050b2607` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Storage.setItem` / `setItem` | `apps/runtime-dashboard/src/shared/i18n/locale.ts` | `apps/runtime-dashboard/src/shared/i18n/locale.ts` | `aab3839c5166` / `901accda25fc` | `locale` |
| `storage-site-b51fd8cf5b5698c0fd273ed568c03273a12b9ebb3cade2a14c162156dec414f4` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Storage.getItem` / `getItem` | `apps/runtime-dashboard/src/shared/i18n/locale.ts` | `apps/runtime-dashboard/src/shared/i18n/locale.ts` | `aab3839c5166` / `eede4f6d129d` | `locale` |
| `storage-site-9d51649078e6303ac8b43ba7a28348c4608225ac5c53369f7fc9c4970400a311` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Window.localStorage` / `acquire` | `apps/runtime-dashboard/src/shared/lib/featureFlags.ts` | `apps/runtime-dashboard/src/shared/lib/featureFlags.ts` | `709491ffcca1` / `4e4aa8087062` | `rollout_exposure_control` |
| `storage-site-65f27f552e5ca38bcdbcfac301937b83d8b244d7d55cd8d6eba94d54268ad19d` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Storage.getItem` / `getItem` | `apps/runtime-dashboard/src/shared/lib/featureFlags.ts` | `apps/runtime-dashboard/src/shared/lib/featureFlags.ts` | `709491ffcca1` / `2a2e19cd3432` | `rollout_exposure_control` |
| `storage-site-cba2f36e647c09f58a91dc4ff652a30b6762ac9294fea79262861ea49d772ac3` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Window.localStorage` / `acquire` | `apps/runtime-dashboard/src/shared/lib/featureFlags.ts` | `apps/runtime-dashboard/src/shared/lib/featureFlags.ts` | `709491ffcca1` / `4e4aa8087062` | `rollout_exposure_control` |
| `storage-site-779df52284e1767610abdfdf8a4ec284a04962a1d6be0d9098944c1ed41031ae` | `interaction_benign` | `typescript/lib/lib.dom.d.ts::Storage.setItem` / `setItem` | `apps/runtime-dashboard/src/shared/lib/featureFlags.ts` | `apps/runtime-dashboard/src/shared/lib/featureFlags.ts` | `709491ffcca1` / `e80a94e64e39` | `rollout_exposure_control` |

### Subunits and structural findings

| ID | Kind | Disposition | Owner slice/team | Capability states | Closure signal | State/reason |
| --- | --- | --- | --- | --- | --- | --- |
| `feature-whatif::legacy-local-whatif-subgraph` | `dead_subgraph` | `deleted` | `DS19` | — | — | Fresh DS19 census proved the seven-file local parameter/store branch and its optional workbench edge unreachable; it was deleted while the server-backed ScenarioWorkbench remained live. |
| `route-app-layout::ru-ui-catalog` | `legacy_continuity` | `frozen_legacy_continuity` | `DS0` | — | — | Ratified D4 freezes the legacy ru UI catalog in place: not used, not deleted, and not an active-locale claim. C05a-R1 proves product resolution, storage, provider state, and catalog selection admit only uk/en while explicit ru formatting remains frozen continuity. |
| `baseline-lint-quantity-debt` | `baseline_lint_debt` | `rebind_pending` | `DS4` | — | — | `repaired` — The quantity diagnostic class is derived from the active lint manifest; resolved means all 75 immutable-origin identities have content-bound C06-C08 resolutions. |
| `baseline-test-i18n-count-debt` | `baseline_test_debt` | `rebind_pending` | `DS6` | — | — | `repaired` — The governed Vitest lifecycle admits exactly the three historical DS6 count-message identities while open or the C16 full-suite empty failure set when repaired. |
| `baseline-test-a11y-coverage-debt` | `baseline_test_debt` | `rebind_pending` | `DS4` | — | — | `repaired` — The accessibility census state is derived from the active Vitest debt classes; C12 repairs the OperatorDiagnosticPanel companion without an allowlist suppression. |
| `baseline-test-temporal-cursor-debt` | `baseline_test_debt` | `rebind_pending` | `DS4` | — | — | `repaired` — The temporal-cursor state is derived from the active Vitest debt classes; C09 closed the time-dependent identity with an injected clock. |
| `dependency-axe-core` | `dependency_declaration` | `use_as_is` | `DS19` | — | — | `repaired` — The source or PWA peer was already resolved transitively; DS19 declared the exact locked version without changing the resolved graph. |
| `dependency-intl-messageformat` | `dependency_declaration` | `use_as_is` | `DS19` | — | — | `repaired` — The source or PWA peer was already resolved transitively; DS19 declared the exact locked version without changing the resolved graph. |
| `dependency-workbox-core` | `dependency_declaration` | `use_as_is` | `DS19` | — | — | `repaired` — The source or PWA peer was already resolved transitively; DS19 declared the exact locked version without changing the resolved graph. |
| `dependency-workbox-precaching` | `dependency_declaration` | `use_as_is` | `DS19` | — | — | `repaired` — The source or PWA peer was already resolved transitively; DS19 declared the exact locked version without changing the resolved graph. |
| `dependency-workbox-routing` | `dependency_declaration` | `use_as_is` | `DS19` | — | — | `repaired` — The source or PWA peer was already resolved transitively; DS19 declared the exact locked version without changing the resolved graph. |
| `dependency-workbox-window` | `dependency_declaration` | `use_as_is` | `DS19` | — | — | `repaired` — The source or PWA peer was already resolved transitively; DS19 declared the exact locked version without changing the resolved graph. |
| `fixture-policy-design-case-audience` | `fixture_contract_drift` | `use_as_is` | `DS19` | — | — | `repaired` — The fixtures now type audience from the generated projection contract introduced after the fixture helper; runtime and generated code were not changed. |
| `producer-binding-readiness-scientific-depth` | `producer_binding_debt` | `rebind_pending` | `DS16` | `producer_missing`, `artifact_missing`, `bridge_missing`, `semantic_test_missing` | each named value resolves to a generated field or registered typed refusal and C23 containment negatives remain green | `open_debt` — dashboard-local synthesis removed because no typed producer field/refusal exists |
| `run-lifecycle-terminal-fact` | `producer_binding_debt` | `rebind_pending` | `DS7` | `consumer_missing`, `surface_missing`, `semantic_test_missing` | DS7 renders the producer-signed RunSummary.run_terminality value without status/timestamp derivation, renders an unbound lifecycle fact as absent rather than false, and keeps the C22 semantic negatives plus DS5 ownership lint green. | `open_debt` — GAP4 now supplies producer-owned lifecycle terminality through RunSummary and both generated clients. The DS7 hero consumer and its absence/proxy semantic tests have not landed yet. |
| `g4-complete-audience-projection-contract` | `integrate_contract_debt` | `rebind_pending` | `team-runtime-quality` | `implemented_but_not_orchestrated`, `bridge_missing`, `consumer_missing`, `surface_missing`, `semantic_test_missing` | uv run python tools/quality/validation/check_policy_design_case_layer3_g4_readiness.py --repo-root . --output-format json exits 0 after owner corruptions prove the canonical projection ID and exact fields, public_export_bundle_route_registered=true, an implemented non-reference-only hook, atomic EXPERT mode.analyst denial, content hashes, owner time, and runtime novelty behavior | `open_debt` — The G4 owner publishes only reduced reference projections; DS5 may not invent or route the complete eight-field audience projection. |
| `authority-presentation-badge-artifact-pipeline-decision-grade` | `authority_presentation_debt` | `rebind_pending` | `DS5` | `producer_missing`, `consumer_missing`, `verification_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after C06 exports DecisionGrade through the generated client and a private exhaustive issuer handles runtime novelty | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-bureaucratic-legal-review` | `authority_presentation_debt` | `rebind_pending` | `DS9` | `consumer_missing`, `verification_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a generated legal-review union enters an exhaustive issuer and runtime novelty renders unrecognized | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-candidate-declared-authority-purpose` | `authority_presentation_debt` | `rebind_pending` | `DS8` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a candidate-purpose issuer cannot grant governed authority | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-candidate-refusal-markers` | `authority_presentation_debt` | `rebind_pending` | `DS8` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after typed candidate and refusal postures cannot be presented as governed output | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-comparability` | `authority_presentation_debt` | `rebind_pending` | `DS16` | `consumer_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a generated comparability union uses an incomparable veto and runtime-novelty tests | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-compound-decision-grade` | `authority_presentation_debt` | `rebind_pending` | `DS5` | `bridge_missing`, `surface_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after C06 generated DecisionGrade and a private exhaustive issuer make raw grade assignment fail typecheck | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-control-approval-quality` | `authority_presentation_debt` | `rebind_pending` | `DS9` | `producer_missing`, `bridge_missing`, `consumer_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after generated approval, calibration, and gate DTOs use weakest-boundary mixed-outcome tests | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-decision-confidence` | `authority_presentation_debt` | `rebind_pending` | `DS16` | `artifact_missing`, `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a typed quantity and uncertainty artifact replaces arbitrary ReactNode confidence | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-evidence-source-freshness` | `authority_presentation_debt` | `rebind_pending` | `DS8` | `producer_missing`, `bridge_missing`, `consumer_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after owner source_as_of and freshness fields enforce oldest-input veto without local SLA authority | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-explainability-governance-counts` | `authority_presentation_debt` | `rebind_pending` | `DS9` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a typed governance summary proves counts cannot synthesize composed authority | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-governance-issue-severity` | `authority_presentation_debt` | `rebind_pending` | `DS9` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a generated owner severity field enters a branded issuer with runtime novelty | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-governed-projection-availability` | `authority_presentation_debt` | `rebind_pending` | `DS7` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a generated availability union enters an exhaustive issuer and novel values render unrecognized | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-governed-projection-rights-bar` | `authority_presentation_debt` | `rebind_pending` | `DS5` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a generated may_not_use_for item enters a branded veto presentation | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-governed-source-validation` | `authority_presentation_debt` | `rebind_pending` | `DS7` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after generated source validation status enters an exhaustive issuer with novelty tests | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-negative-certificate-blocker` | `authority_presentation_debt` | `rebind_pending` | `DS8` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a generated blocker issuer prevents non-blockers from occupying the slot | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-operator-blocker-overridability` | `authority_presentation_debt` | `rebind_pending` | `DS14` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a generated decision or boolean issuer owns clothing and raw slot assignment fails typecheck | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-preflight-readiness` | `authority_presentation_debt` | `rebind_pending` | `DS7` | `producer_missing`, `bridge_missing`, `consumer_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after typed preflight and diagnostic DTOs use mixed fail/warn veto tests and raw preview clothing is absent | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-projection-source-freshness` | `authority_presentation_debt` | `rebind_pending` | `DS18` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after ProjectionFreshness state enters an exhaustive issuer with explicit absence and novelty behavior | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-promotion-candidate-status` | `authority_presentation_debt` | `rebind_pending` | `DS15` | `consumer_missing`, `verification_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a generated promotion union enters a private issuer and novel values render unrecognized | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-provenance-drift` | `authority_presentation_debt` | `rebind_pending` | `DS16` | `consumer_missing`, `verification_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a private invalidation-posture issuer vetoes on every load-bearing provenance change | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-public-anti-authority-role` | `authority_presentation_debt` | `rebind_pending` | `DS12` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a branded refusal from packet authorityRole cannot be upgraded to authority | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-public-integrity-result` | `authority_presentation_debt` | `rebind_pending` | `DS12` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a verifier-private integrity presentation remains explicitly outside closeout authority | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-public-packet-authority-framing` | `authority_presentation_debt` | `rebind_pending` | `DS12` | `producer_missing`, `artifact_missing`, `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after generated packet authority, confidence, and rights fields retain a rights-bar mixed-veto test | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-review-required-aggregate` | `authority_presentation_debt` | `rebind_pending` | `DS9` | `consumer_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a generated review-required fact enters a private issuer and missing or denied inputs cannot present positive | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-run-deck-authority-summary` | `authority_presentation_debt` | `rebind_pending` | `DS7` | `producer_missing`, `bridge_missing`, `consumer_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a live typed run-deck contract rejects fixture_only and prevents local authority synthesis | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-threshold-unavailable` | `authority_presentation_debt` | `rebind_pending` | `DS16` | `artifact_missing`, `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a typed unavailable or refusal artifact replaces the static caller-owned threshold token | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-badge-uncertainty-dispute` | `authority_presentation_debt` | `rebind_pending` | `DS16` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after an owner uncertainty artifact keeps disputed as a mixed-case veto or warning | `open_debt` — C01a classifies this direct authority-bearing Badge group as unbranded typed debt; its owner must replace caller-chosen clothing with the existing private-issuer brand pattern. |
| `authority-presentation-prop-control-approval-readiness` | `authority_presentation_debt` | `rebind_pending` | `DS14` | `producer_missing`, `bridge_missing`, `consumer_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a generated approval-readiness issuer owns clothing and mixed deny/unknown cases remain non-positive | `open_debt` — C01a classifies this authority-bearing prop boundary as unbranded typed debt; its owner must replace structural clothing with the existing private-issuer brand pattern. |
| `authority-presentation-prop-counterfactual-status` | `authority_presentation_debt` | `rebind_pending` | `DS8` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a generated scenario-status issuer owns icon, tone, and label while novel values fail closed | `open_debt` — C01a classifies this authority-bearing prop boundary as unbranded typed debt; its owner must replace structural clothing with the existing private-issuer brand pattern. |
| `authority-presentation-prop-data-freshness` | `authority_presentation_debt` | `rebind_pending` | `DS18` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after ProjectionFreshness enters a private exhaustive issuer and runtime-novel states render unrecognized without cache-age inference | `open_debt` — C01a classifies this authority-bearing prop boundary as unbranded typed debt; its owner must replace structural clothing with the existing private-issuer brand pattern. |
| `authority-presentation-prop-decision-card-confidence` | `authority_presentation_debt` | `rebind_pending` | `DS17` | `artifact_missing`, `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a typed quantity and uncertainty artifact replaces arbitrary ReactNode confidence and rejects structural lookalikes | `open_debt` — C01a classifies this authority-bearing prop boundary as unbranded typed debt; its owner must replace structural clothing with the existing private-issuer brand pattern. |
| `authority-presentation-prop-decision-card-verdict` | `authority_presentation_debt` | `rebind_pending` | `DS5` | `bridge_missing`, `surface_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after C06 generated DecisionGrade and a private issuer replace the raw verdict boundary with novelty tests | `open_debt` — C01a classifies this authority-bearing prop boundary as unbranded typed debt; its owner must replace structural clothing with the existing private-issuer brand pattern. |
| `authority-presentation-prop-decision-grade-presentation` | `authority_presentation_debt` | `rebind_pending` | `DS5` | `bridge_missing`, `surface_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after C06 supplies DecisionGrade through the generated client and a private exhaustive issuer replaces this structural presentation | `open_debt` — C01a classifies this authority-bearing prop boundary as unbranded typed debt; its owner must replace structural clothing with the existing private-issuer brand pattern. |
| `authority-presentation-prop-dispute-status` | `authority_presentation_debt` | `rebind_pending` | `DS11` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a private exhaustive dispute issuer owns clothing and runtime-novel dispute states render unrecognized | `open_debt` — C01a classifies this authority-bearing prop boundary as unbranded typed debt; its owner must replace structural clothing with the existing private-issuer brand pattern. |
| `authority-presentation-prop-explainability-verdict` | `authority_presentation_debt` | `rebind_pending` | `DS5` | `bridge_missing`, `surface_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after C06 generated DecisionGrade and a private issuer replace the nested raw verdict path | `open_debt` — C01a classifies this authority-bearing prop boundary as unbranded typed debt; its owner must replace structural clothing with the existing private-issuer brand pattern. |
| `authority-presentation-prop-lineage-freshness-cue` | `authority_presentation_debt` | `rebind_pending` | `DS16` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a source-owned lineage freshness issuer owns the cue and absence cannot be upgraded | `open_debt` — C01a classifies this authority-bearing prop boundary as unbranded typed debt; its owner must replace structural clothing with the existing private-issuer brand pattern. |
| `authority-presentation-prop-time-semantics-freshness` | `authority_presentation_debt` | `rebind_pending` | `DS18` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after the generated owner freshness value enters an issued temporal presentation with explicit unknown behavior | `open_debt` — C01a classifies this authority-bearing prop boundary as unbranded typed debt; its owner must replace structural clothing with the existing private-issuer brand pattern. |
| `authority-presentation-prop-verification-status-cue` | `authority_presentation_debt` | `rebind_pending` | `DS16` | `bridge_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after a private verification-status issuer owns cue clothing and runtime novelty is explicit | `open_debt` — C01a classifies this authority-bearing prop boundary as unbranded typed debt; its owner must replace structural clothing with the existing private-issuer brand pattern. |
| `authority-presentation-prop-verification-status-icon-tone` | `authority_presentation_debt` | `rebind_pending` | `DS11` | `verification_missing`, `semantic_test_missing` | python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check --corruption-probes exits 0 after the open string tone carrier is replaced by a private issued trust presentation and structural forgery is rejected | `open_debt` — C01a classifies this authority-bearing prop boundary as unbranded typed debt; its owner must replace structural clothing with the existing private-issuer brand pattern. |
| `authority-issuer-generated-semantic-id-coverage` | `producer_binding_debt` | `rebind_pending` | `DS5` | `artifact_missing`, `verification_missing`, `semantic_test_missing` | python3 -m unittest architecture.atlas_surfaces.test_atlas_enforcement.AtlasEnforcementTests.test_authority_issuer_exported_vocabulary_covers_all_consumed_owner_unions exits 0 after runtime_authority and fixture_only export corruptions fail while the unrelated-constant witness remains green | `open_debt` — C01c review proved the scanner protects projection-state IDs but does not yet derive runtime-authority and fixture IDs from every closed generated union consumed by the issuer family. |
| `authority-issuer-parity-operand-binding` | `producer_binding_debt` | `rebind_pending` | `DS5` | `artifact_missing`, `verification_missing`, `semantic_test_missing` | python3 -m unittest architecture.atlas_surfaces.test_atlas_enforcement.AtlasEnforcementTests.test_authority_issuer_parity_operands_are_exact_generated_pairs exits 0 after state and authority self-comparison corruptions fail | `open_debt` — C01c review proved the equality predicate and never branches are bound, but a generated Operator/Run operand can still be replaced by a self-comparison without invalidating the fact packet. |
| `raw-transport-denominator-drift` | `producer_binding_debt` | `rebind_pending` | `DS5` | `contract_only`, `consumer_missing`, `semantic_test_missing` | python3 -c 'import importlib; from architecture.atlas_surfaces import check_frontend_disposition_register as checker; owner_module=importlib.import_module("architecture.atlas_surfaces.test_atlas_enforcement"); drift_module=importlib.import_module("architecture.atlas_surfaces.test_frontend_disposition_register"); raise SystemExit(checker._raw_transport_debt_closure_exit_code(getattr(owner_module, "AtlasEnforcementTests", None), "test_direct_authority_transport_requires_typed_purpose_factory", getattr(drift_module, "RawTransportDriftTests", None), "test_raw_transport_drift_row_binds_historical_and_live_census"))' # exits 0 only when both exact C03b tests execute and pass with the live 7/5 census; 3 means owner test absent, 4 means drift test absent, and 1 means either test failed; all are exit nonzero. | `open_debt` — The DS1 audit recorded four collaboration fetches that DS19 later deleted; historical audit coverage is evidence, not the live C03b direct-call denominator. C03b-R2 exhausted its two-fix-round cap at 54fec7ae9a7282f414da8dc727fa5aa01a17b232 and was forward-reverted by 1d0ff1f539790294d508f97b3e4e4bfe3139f594; the remaining corruption `raw_transport_live_direct_constructor_census_drift` is deferred. |
| `semantic-copy-issuer-panel-consumer-deferral` | `producer_binding_debt` | `rebind_pending` | `DS5` | `bridge_missing`, `consumer_missing`, `verification_missing`, `semantic_test_missing` | python3 -m unittest architecture.atlas_surfaces.test_frontend_disposition_register.AuthorityPresentationCensusTests.test_semantic_copy_panel_consumer_rebinds_direct_badge_census_transition exits 0 after the live RunExplainabilityPanel consumer rebinds the direct-Badge census transition | `open_debt` — C05b-R3 landed the private semantic-copy issuer and generated AvailableGovernedProjectionPacket.may_not_use_for guard. The live RunExplainabilityPanel/direct-Badge census transition remains panel-only debt, and DS6 accepted human semantic-review receipts remain 0. |
| `c06-cgf-public-vocabulary-producer-debt` | `producer_binding_debt` | `rebind_pending` | `DS5` | `producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`, `verification_missing`, `surface_missing`, `semantic_test_missing` | python3 -m unittest architecture.atlas_surfaces.test_atlas_enforcement.AtlasEnforcementTests.test_generated_cgf_disposition_union_tracks_generation_cycle_owner_contract exits 0 after the canonical generation-cycle owner publishes a public typed owner contract through the runtime schema | `open_debt` — C06 cannot project CGF disposition: a private validator set exists and runtime owners remain opaque JsonObjectTuple values, but no public typed owner exists. C06 may not publish or invent that contract; the DS4 bridge/surface row remains open as a distinct plane. |
| `c06-decision-grade-generated-contract-debt` | `producer_binding_debt` | `rebind_pending` | `DS5` | `producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`, `verification_missing`, `surface_missing`, `semantic_test_missing` | python3 -m unittest architecture.atlas_surfaces.test_atlas_enforcement.AtlasEnforcementTests.test_generated_decision_grade_union_tracks_pdc_owner exits 0 after C14 publishes the generated DecisionGrade contract from the PDC owner | `open_debt` — DecisionGrade has a PDC owner but no OpenAPI or generated-client export; the DS4 waist row assigns its singular swap point to C14. C06 records the missing generated producer contract and does not pre-empt C14. |
| `c08b-auth-session-revision-producer-debt` | `producer_binding_debt` | `rebind_pending` | `DS5` | `producer_missing`, `artifact_missing`, `bridge_missing`, `verification_missing`, `semantic_test_missing` | python3 -m unittest architecture.atlas_surfaces.test_atlas_enforcement.AtlasEnforcementTests.test_auth_me_query_key_partitions_tenant_user_and_revision tests.unit.runtime.http.test_auth_api.AuthApiTests.test_auth_me_publishes_auth_session_revision exits 0 after /auth/me and generated AuthMeResponse publish a server-issued auth_session_revision and queryKeys binds it; tenant/user-switch corruption fails | `open_debt` — The runtime HTTP AuthMeResponse, OpenAPI schema, generated client, useAuthMe, and queryKeys all lack auth_session_revision. This is the missing client-bound producer contract, not ownership of server identity. |
| `c07b-dashboard-generated-client-single-owner-debt` | `producer_binding_debt` | `rebind_pending` | `DS5` | `bridge_missing`, `consumer_missing`, `verification_missing`, `semantic_test_missing` | python3 -m unittest architecture.atlas_surfaces.test_frontend_disposition_register.ProducerBindingDebtTests.test_c07b_dashboard_generated_client_has_one_canonical_owner exits 0 after manifest/reference/package cleanup, deletion of apps/runtime-dashboard/src/api/types.ts, and all compiler-resolved dashboard imports directly use @polisyos/runtime-api-client. | `open_debt` — Canonical package client exists, but the dashboard keeps a divergent local generated artifact; this row records the single-owner strangle without a comparator or dashboard change. |
| `baseline-test-a11y-rendered-contrast-incomplete-debt` | `baseline_test_debt` | `rebind_pending` | `DS6` | — | — | `repaired` — C01/C06/C09/C14 comprise seven declared source identities. Axe incomplete nodes are neither passes, source-attributed receipts, nor denominator members; closure requires 7/7 numeric WCAG-AA receipts on an opaque real-browser background. |

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
| `ui-compounds-root` | `ui-compounds-root` | 3 | `rebind_pending` | `strangled` | `DS4` | `atlas-ui-root-compounds-and-dashboard-transitional-winners` |
| `ui-operator-diagnostics` | `ui-operator-diagnostics` | 0 | `rebind_pending` | `strangled` | `DS4` | `dashboard-operator-diagnostic-generated-evidence-rebind` |
| `ui-authored-text` | `ui-authored-text` | 11 | `rebind_pending` | `strangled` | `DS4` | `dashboard-authored-candidate-posture` |
| `ui-compounds` | `ui-compounds` | 24 | `rebind_pending` | `strangled` | `DS4` | `dashboard-compound-evidence-generated-waist-rebind` |
| `ui-counterfactual` | `ui-counterfactual` | 4 | `rebind_pending` | `strangled` | `DS4` | `dashboard-counterfactual-generated-scenario-rebind` |
| `ui-patterns` | `ui-patterns` | 7 | `rebind_pending` | `strangled` | `DS4` | `atlas-ui-shared-patterns-and-dashboard-searchable-list` |
| `ui-quantity` | `ui-quantity` | 34 | `rebind_pending` | `strangled` | `DS4` | `dashboard-quantity-generated-waist-rebind` |
| `ui-responsive` | `ui-responsive` | 26 | `rebind_pending` | `strangled` | `DS4` | `dashboard-responsive-generated-breakpoint-adapter` |
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
| `raw-fetch-flag-manifest` | `raw-fetch-flag-manifest` | 0 | `use_as_is` | `not_applicable` | `DS5` | `—` |
| `raw-fetch-collab-activity` | `raw-fetch-collab-activity` | 0 | `deleted` | `strangled` | `DS19` | `census-collaboration-delete` |
| `raw-fetch-collab-comments-get` | `raw-fetch-collab-comments-get` | 0 | `deleted` | `strangled` | `DS19` | `census-collaboration-delete` |
| `raw-fetch-collab-comment-post` | `raw-fetch-collab-comment-post` | 0 | `deleted` | `strangled` | `DS19` | `census-collaboration-delete` |
| `raw-fetch-collab-resolve` | `raw-fetch-collab-resolve` | 0 | `deleted` | `strangled` | `DS19` | `census-collaboration-delete` |
| `raw-fetch-telemetry` | `raw-fetch-telemetry` | 0 | `rebind_pending` | `pending` | `DS12` | `—` |
| `status-auth-session` | `status-auth-session` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-offline-queue-item` | `status-offline-queue-item` | 0 | `deleted` | `strangled` | `DS1` | `census-c13a-authority-replay-delete` |
| `status-feature-flag` | `status-feature-flag` | 0 | `rebind_pending` | `strangled` | `DS5` | `dashboard-feature-flag-load-interaction-state` |
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
| `status-stress-scene` | `status-stress-scene` | 0 | `rebind_pending` | `strangled` | `DS4` | `c23-readiness-scientific-containment` |
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
| `status-inline-queued-promotion` | `status-inline-queued-promotion` | 0 | `deleted` | `strangled` | `DS1` | `census-c13a-authority-replay-delete` |
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
| `status-inline-readiness-evidence` | `status-inline-readiness-evidence` | 0 | `rebind_pending` | `strangled` | `DS4` | `c23-readiness-scientific-containment` |
| `status-inline-readiness-gate` | `status-inline-readiness-gate` | 0 | `rebind_pending` | `strangled` | `DS4` | `c23-readiness-scientific-containment` |
| `status-inline-readiness-review` | `status-inline-readiness-review` | 0 | `rebind_pending` | `strangled` | `DS4` | `c23-readiness-scientific-containment` |
| `status-inline-run-narrative` | `status-inline-run-narrative` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-governance-comparison-left` | `status-inline-governance-comparison-left` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-governance-comparison-right` | `status-inline-governance-comparison-right` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-small-multiples` | `status-inline-small-multiples` | 0 | `rebind_pending` | `strangled` | `DS4` | `runtime-verification-metadata-small-multiples` |
| `status-inline-route-loader` | `status-inline-route-loader` | 0 | `rebind_pending` | `pending` | `DS1` | `—` |
| `status-inline-explainability` | `status-inline-explainability` | 0 | `rebind_pending` | `strangled` | `DS4` | `dashboard-depth-n-cycle-board-governed-projection` |
| `status-inline-counterfactual-badge` | `status-inline-counterfactual-badge` | 0 | `rebind_pending` | `strangled` | `DS4` | `runtime-scenario-ref-status` |
| `flag-enable-atlas-v2` | `flag-enable-atlas-v2` | 0 | `use_as_is` | `not_applicable` | `DS5` | `—` |
| `flag-enable-clerk-mode` | `flag-enable-clerk-mode` | 0 | `use_as_is` | `not_applicable` | `DS5` | `—` |
| `flag-enable-dark-mode` | `flag-enable-dark-mode` | 0 | `use_as_is` | `not_applicable` | `DS5` | `—` |
| `flag-enable-lex-knowledge` | `flag-enable-lex-knowledge` | 0 | `use_as_is` | `not_applicable` | `DS5` | `—` |
| `flag-enable-narrative-view` | `flag-enable-narrative-view` | 0 | `use_as_is` | `not_applicable` | `DS5` | `—` |
| `flag-enable-platform-health` | `flag-enable-platform-health` | 0 | `use_as_is` | `not_applicable` | `DS5` | `—` |
| `flag-enable-runs-workspace` | `flag-enable-runs-workspace` | 0 | `use_as_is` | `not_applicable` | `DS5` | `—` |
| `flag-enable-scenario-composer` | `flag-enable-scenario-composer` | 0 | `use_as_is` | `not_applicable` | `DS5` | `—` |
| `flag-enable-causal-graph` | `flag-enable-causal-graph` | 0 | `wire_disposition` | `not_applicable` | `DS5` | `—` |
| `flag-enable-collaboration` | `flag-enable-collaboration` | 0 | `retire_disposition` | `not_applicable` | `DS5` | `census-collaboration-delete` |
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
| `cache-service-worker-static` | `cache-service-worker-static` | 0 | `use_as_is` | `not_applicable` | `DS5` | `—` |
| `offline-queue-promotion-decision` | `offline-queue-promotion-decision` | 0 | `deleted` | `strangled` | `DS5` | `census-c13a-authority-replay-delete` |
| `offline-draft-composer` | `offline-draft-composer` | 0 | `use_as_is` | `not_applicable` | `DS5` | `—` |
| `cache-query-memory` | `cache-query-memory` | 0 | `rebind_pending` | `strangled` | `DS5` | `dashboard-governed-query-cache-posture` |
| `cache-local-storage-state` | `cache-local-storage-state` | 0 | `use_as_is` | `not_applicable` | `DS5` | `—` |
| `cache-clerk-sessions` | `cache-clerk-sessions` | 0 | `rebind_pending` | `pending` | `DS14` | `—` |
| `cache-whatif-scenarios` | `cache-whatif-scenarios` | 0 | `deleted` | `strangled` | `DS19` | `census-whatif-local-subgraph-delete` |
| `cache-causal-drafts` | `cache-causal-drafts` | 0 | `rebind_pending` | `strangled` | `DS8` | `dashboard-causal-draft-scoped-local-state` |
| `cache-local-disputes` | `cache-local-disputes` | 0 | `rebind_pending` | `strangled` | `DS9` | `dashboard-dispute-scoped-local-state` |
| `cache-review-attention` | `cache-review-attention` | 0 | `deleted` | `strangled` | `DS9` | `census-review-attention-delete` |
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

- `d17ecd36e fix(runtime): bind cycle board routes to owner artifacts`
- `a70a72b3e Merge commit '0b721454e2f246e89bd084d5e19039c6a1e3d4c5' into codex/atlas-ds7-cycle-board`
- `0184d0bd7 test(runtime): close DS7 owner equality receipt`
- `6f9662eb2 feat(runtime): compose DS7 cycle board projection`
- `0b721454e plan(atlas): Revision 3.22 — DS6 transitions landed; debt-row execution rule corrects a sequencing error`
- `b0249e82d merge(atlas): land DS6 C03/C04/C06 — the three append-only register transitions`
- `95d4d9419 DS6-C06 close rendered-contrast evidence debt`
- `80127b654 Merge commit '1360b1cb592be6a19c162a3ec3ddb5a2e87986c7' into codex/atlas-ds7-cycle-board`
- `39a19c078 DS6-C04 admit rendered-contrast evidence debt`
- `86a2cc1f7 DS6-C03 rebind i18n baseline lifecycle`
- `21699a504 docs: close DS7 task 4 RED basis`
- `38654406f docs: record DS7 task 4c RED receipt`
- `a2b2e113a test: freeze DS7 cycle board loading REDs`
- `981849b99 docs: record DS7 task 4b RED receipt`
- `5b3d8b766 test: freeze DS7 cycle board access replay REDs`
- `043c18117 docs: record DS7 task 4a RED receipt`
- `e36fec44e test: freeze DS7 cycle board fact algebra REDs`
- `d585d2fa0 docs: freeze DS7 task 4 RED closure basis`
- `1360b1cb5 plan(gy): Rev 54 — GY-DI1 closed and the reissue paid once; register GY-DEF22`
- `bb2ce91fb merge(gy): close GY-DI1 — deployment identity is derived, not enumerated`
- `3c1e8201c merge(atlas): land DS7 Cluster 0 — GAP4 with regenerated clients, and the DS7 record boundary`
- `0fc36511d docs(gy): record deployment identity closure`
- `f4e4522e4 chore(gy): reissue deployment-bound confidence artifacts`
- `015a062a8 docs(gy): declare deployment identity reissue delta`
- `f5fd5c66d docs(ds7): register cycle recording gaps`
- `192774f24 docs(ds7): record inherited red provenance`
- `d588b5a13 merge: update main before DS7 board`
- `dc3e50a90 merge(ds7): land GAP4 with regenerated clients`
- `59e4b7c7b fix(runtime): compose owner and runtime closure modes`
- `69aaa1b76 test(runtime): falsify dormant dynamic authority edges`
- `da0c17079 fix(runtime): exclude type-only authority edges`
- `11781974d plan: GY Rev 53 + Atlas Revision 3.21 — GY-PA1 not executable, GY-DEF19 registered, a refuted anchor corrected`
- `0084fc1bf merge(gy): record the GY-PA1 foundability probe — producer_missing`
- `40ef040bd merge current main into DS7 cycle board`
- `e0b0dbe79 docs(superpowers): plan DS7 cycle board implementation`
- `c52bdfb09 fix(runtime): derive deployment identity from authority closure`
- `82474845a plan(gy): Rev 52 — GY-PA2 and the inherited GY-DEF18 closed; ownership is measured, not inferred from a stop`
- `663f2d36a merge(gy): close GY-PA2 delegation gate and the inherited GY-DEF18 provenance defect`
- `6c1a90c33 docs(gy): close PA2 inherited provenance defect`
- `6104d7e17 docs(gy): record PA1 foundability probe`
- `2f6badff0 fix(runtime): keep provenance traversal internal`
- `7cc23675b fix(runtime): govern provenance by owner-declared values`
- `c7c3206da test(runtime): fail closed on opaque provenance carriers`
- `17d5849ef test(runtime): forbid caller-widened memory positions`
- `18d7e058d test(runtime): widen provenance admission falsifiers`
- `4eec3fb48 docs(atlas): approve DS7 cycle board design`
- `8a3e0f763 test(runtime): expose provenance proxy escapes`
- `c05475263 plan(gy): Rev 51 — GY-DEF4 closed; renumber the lane's standing after a concurrent revision collision`
- `42de52dc1 docs(gy): register inherited provenance proxy defect`
- `618de0f69 merge(gy): close GY-DEF4 — the temporal pass token is an owner-declared contract`
- `c106db3c4 plan(gy): Rev 50 — GY-GAP1 closed; the promotion critical path is now institutional only`
- `4180b295b merge(gy): close GY-GAP1 obligation-instance identity, GY-DEF5 and GY-DEF17`
- `29866faf5 plan(gy): Rev 49 — GY-PA3 closed; the sequencing note had expired unnoticed`
- `870ac427d merge(gy): land GY-PA3 compression-loss ledger producer`
- `82a046081 docs(gy): close obligation instance identity gap`
- `cacb5d154 fix(gy): route obligation drafts through pdc facade`
- `4b21458d0 artifacts(gy): reissue obligation instance receipts`
- `940817bf1 docs(gy): record PA2 final audit stop`
- `5774eba7c docs(gy): redeclare repaired obligation artifact transition`
- `a3df41e18 docs(gy): record PA2 standing and receipts`
- `132bcf007 fix(runtime): honor architecture import facades`
- `aeb732851 docs(plan): record GY-PA3 standing`
- `58207ed0e test(architecture): bind stale public surface adversary`
- `6ec57dcbc fix(runtime): seal GY-PA2 request authority inputs`
- `260575a5f chore(architecture): regenerate G6 compression receipts`
- `bd05837fb test(runtime): bind GY-PA2 owner proof and live clock`
- `dbadb872f fix(architecture): register G6 authority-preserving export`
- `1007277ac test(architecture): reject stale G6 public export registration`
- `872899d2c fix(runtime): close GY-PA2 authority owner escapes`
- `4be81772f fix(runtime): bind compression receipts through public export`
- `e6a74ea04 test(runtime): widen compression authority adversaries`
- `4456bb885 plan(atlas): Revision 3.20 — DS5 closed and merged; GAP4 re-sequenced into DS7's opening`
- `c77888b7c merge(atlas): land DS5 enforcement waist — D4-A1 English primary, C21 register release issued`
- `a498f5db3 DS5 close post-main handoff and issue C21 release`
- `ae039824d test(runtime): expose GY-PA2 authority bypasses`
- `5bfcdb5da feat(runtime): validate compression authority preservation`
- `e4c40beac feat(runtime): add mandate-bounded agent action gate`
- `ae04e0a8b feat(runtime): bridge compression receipts through G6`
- `c58ed658f docs(gy): record DEF4 governed reissue closure`
- `3eda73f89 fix(gy): normalize N10a transitions across declared outputs`
- `c3fe58812 test(runtime): add GY-PA2 delegation gate reds`
- `3f6acc300 fix(architecture): keep artifact typing behind runtime protocol`
- `a9423fbe1 docs(gy): refresh GAP1 pre-writer disjointness`
- `88d1f70cf Merge main into DS5 and reconcile D4-A1 parity ownership`
- `7e9111a37 fix(runtime): recompute time-source projection at authority intake`
- `bf42d0108 feat(runtime): add compression-loss receipt owner`
- `04d6cb756 docs(gy): register N10a transition normalization defect`
- `0b45fe60a test(runtime): bind compression completeness gates`
- `208a3b44c fix(runtime): close time-source projection pass intake`
- `3db4c2c39 test(runtime): add compression-loss behavioral reds`
- `bcba9db6c DS5-D4-A1 restore authored English primary and close slice honestly`
- `9ba6935d0 docs(gy): record GAP1 P41 ownership replay`
- `d48a242e9 docs(gy): record obligation artifact freeze stop`
- `f332387bb docs(gy): declare obligation artifact transition`
- `bedd47503 plan(atlas): Revision 3.19 — amend D4 as D4-A1; English is primary, Ukrainian a translation`
- `1de11b8bd fix(gy): admit authentic v2 promotion custody`
- `0f6a01b5b DS5-C20 correct slice-base debt attribution`
- `7ca24cda0 feat(gy): bind decisive obligation instances`
- `1c9f91180 fix(gy): scope the N9 obligation denominator claim`
- `3f7263a9b docs(patterns): register P41 — red of unknown provenance`
- `f000aa1d2 plan(gy): Rev 48 — three repository defects closed, GY-DEF4 stops on a governed artifact`
- `b07148239 merge(gy): land three of four repository defects; GY-DEF4 stops on a governed artifact`
- `5ac5cee63 DS5-C20 close enforcement waist for architect handoff`
- `b66bf3f82 fix(scientist): close GY-DEF3 checkpoint scope`
- `42957f826 fix(legal): close GY-DEF1 jurisdiction fallback`
- `673e81706 docs(gy): record GY-DEF4 artifact stop`
- `07f5fd6ab fix(runtime): close GY-DEF2 public export ref leak`
- `dc816548f docs: record DS5-C20 architecture owner stop`
- `7ee283762 Revert "DS5-C20 preserve architecture-baseline-red closure candidate"`
- `4c20818c3 DS5-C20 preserve architecture-baseline-red closure candidate`
- `068aab9df plan(gy): Rev 47 — the N11 suffix is closed`
- `18f081933 merge(gy): land GY-DEFC-9 — the N11 suffix closes with a zero-issue cold run`
- `e6bcd57fa plan(gy): Rev 46 — sixteen registry entries now state their own standing`
- `cdf2186bb docs(gy): record zero-issue cold N11 suffix`
- `69f3fa39a docs(gy): bind Darwin cold environment`
- `700e3aa14 DS5-C09b-R1 default deny modes and run surfaces`
- `b19f9941d docs(gy): authorize proxy-free cold launch`
- `d894f0bd8 docs(gy): record DEFC-9 cold terminal`
- `0f6c88add docs(gy): authorize owner-path cold preflight`
- `541613965 docs(gy): authorize cold preflight parser repair`
- `cc198b2a4 docs(gy): bind retained cold preflight`
- `a35c5cb68 docs(gy): correct cold authorization coordinate`
- `4c1079373 docs(gy): authorize DEFC-9 cold launch`
- `6002d1eab DS5-C09a-R2 default deny application chrome`
- `91600981c DS5-C15b-R1 mount Clerk identity hydration`
- `4edcf96be DS5-C11b-R1 render governed cache posture`
- `8f59d4c4c DS5 record C09a default-deny recut stop`
- `c64b03dea Revert "DS5-C09a-R1 preserve stopped default-deny candidate"`
- `f240db1b7 DS5-C09a-R1 preserve stopped default-deny candidate`
- `a22cbb0be DS5 record C07a generated-family owner block`
- `9e389a17a DS5-C17b-R3 govern persistence construction`
- `cb868c901 docs(gy): stop DEFC-9 before cold launch`
- `1a16ecef7 docs(gy): record accepted confidence reissue`
- `8ae3facde chore(gy): reissue confidence deployment identity`
- `c84b9262f DS5-C19-R2 wire and retire D5 flags`
- `c5f661323 docs(gy): close confidence acceptance review`
- `5e0a7b2f1 docs(gy): bind confidence acceptance paths`
- `6ce8b468b docs(gy): declare DEFC-9 confidence transition`
- `68bb34762 docs(patterns): register P40 — ladder repair, and the rule that ends it`
- `9eee8affb plan(gy): Rev 45 — GY-DEF9 closed, and with it the whole DEF7–DEF12 cascade`
- `c5aeeedcc merge(gy): land the GY-DEF9 executable witness — five of five producers closed`
- `24cebe3ca DS5 record C19 flag-gate recut stop`
- `5044b8ae9 test: compare depth owner projection bytes`
- `33ea792b5 Revert "DS5-C19-R1 preserve stopped flag-gate candidate"`
- `9b87f0e09 DS5-C19-R1 preserve stopped flag-gate candidate`
- `d9a0beb90 feat(gy): quarantine ambient N8 provenance drift`
- `3af775d8e test: witness governed owner history independence`
- `a447c9721 DS5 record C17b persistence census recut stop`
- `1c9397147 docs(gy): register DEFC-9 suffix execution`
- `eb97981c4 Revert "DS5-C17b-R2 preserve stopped persistence census candidate"`
- `ca1400c55 DS5-C17b-R2 preserve stopped persistence census candidate`
- `3fde27f0d plan(atlas): Revision 3.18 — carry DS6's debt at the programme level`
- `96b0bff85 plan(atlas): record DS6 as blocked_on_another_plan with its executable set exhausted`
- `fa1f3e4d0 merge(atlas): land DS6 C10-R2 per-claim readiness reconciliation`
- `5824bac08 docs(atlas): land C10 R2 readiness reconciliation`
- `8bb10a611 DS5-C18b-R2 bind flag sources to strict registry`
- `9c46d6f67 docs(atlas): record C10 R2 setup nonreceipt`
- `c17ad017d docs(atlas): declare C10 R2 verification wave`
- `c18688501 fix(atlas): align readiness scope with unavailable checks`
- `c1354ec7a feat(atlas): declare readiness intake threat model`
- `593ad6170 DS5 reconcile executable standings`
- `cb0273ba4 docs(atlas): enter DS6 C10-R2 threat model`
- `7fa48a9d9 Merge branch 'main' into codex/atlas-ds6-c10r1-readiness-reconciliation`
- `66d08f287 perf(data-forge): serve catalog graphs from a content-addressed cache`
- `a6190c1c6 plan(gy): Rev 44 — the five unrecorded standings, four closed and one witnessless`
- `eda27b0f2 docs(atlas): stop C10-R1 on terminal finding`
- `6906777f4 fix(atlas): close readiness CI admission`
- `84cb20d20 docs(atlas): record C10-R1 repair round two`
- `2c1df24b4 fix(atlas): bind per-claim readiness evidence`
- `a986295f6 docs(atlas): record C10-R1 repair round one`
- `2120daeeb docs(atlas): describe per-claim readiness bases`
- `b0e557c04 feat(atlas): reconcile readiness claims per basis`
- `e66960215 docs(gy): record DEF7-12 standings`
- `a2aee665f docs(atlas): enter DS6 C10-R1 per-claim reconciliation`
- `f63748684 docs(patterns): register P39 — a budget that counts the record it mandates`
- `fa708f2bc merge(atlas): land DS6 C11 instrumentation and the C18 fixture recut`
- `44276ccd5 plan(gy): Rev 43 — the P30 objective is closed, and the marathon that remains is enumerated`
- `70a3f3d15 merge(gy): land the N11 acceptance milestone and the null-versus-absent projection owner`
- `f6915af3a plan(atlas): Revision 3.17 — the DS16 inherited obligation is not satisfiable as written`
- `4b2904e8a DS6-C18 fix visual fixture and re-anchor C15-R1 deltas`
- `324996652 DS5 record C18b governed recut stop`
- `1464feee1 Revert "DS5-C18b-R1 checkpoint strict flag closeout recut"`
- `52ab21cf6 DS5-C18b-R1 checkpoint strict flag closeout recut`
- `25d7718f6 docs(gy): record pre-cold provenance stop`
- `e3c533d91 Merge branch 'main' into codex/gy-defc-3-retry`
- `5b2c2173b feat(gy): accept confidence ledger reissue`
- `21ae2ba65 plan(atlas): Revision 3.16 — DS16's authority half closed, and DS5 inherits the register reconciliation`
- `88210076e merge(gy): land the GY-DI timing lane — durable substrate, honest admission, derived catalog`
- `e9079bade plan(gy): Rev 42 — close the two items GY-INFRA-2 carried; INFRA-2 itself was already closed`
- `1c6e36067 feat(gy-infra-2b): make a delta package state what it excludes`
- `32cfdfac3 feat(gy-infra-2a): publish a p95 only where the sample count can support one`
- `bd01fbe87 plan(backlog): correct INT-R6's dependency — Atlas D4 is ratified, not unratified`
- `c889ee085 plan(gy): Rev 41 — GY-DI2/DI3/DI4 closed, and DI4 was registered at the wrong severity`
- `7e745391f fix(gy-di2): derive budget lanes from the recorded log and name the unbudgeted ones`
- `ec1a8f055 fix(gy-di3): default the timing log to a durable in-repo path, with a reasoned retention`
- `ee44c5e8d fix(gy-di4): admit a timing sample on completion, not on exit_code == 0`
- `15b41f960 salvage(gy-di3): rescue the perishable tool-timing records before they vanish`
- `01943ed83 merge(gy): land the GY-INFRA-3 step-0 diagnosis journal`
- `49a328854 merge(gy): land the GY-DEFC-3 writer non-receipt journal`
- `b27268df9 merge(research): land the wave-4 consolidation`
- `b910f9841 merge(research): land the S0-GAP-02 P37 vocabulary correction (W4-K02)`
- `cf69a9aa4 merge(research): land the S0-GAP-02 amendment and its conformance verification`
- `b44008a7e merge(research): land S0-GAP-02 research and its independent audit`
- `6ae73fe34 merge(research): land the PAO-R4 census attribution correction (W4-K01)`
- `563fb278f merge(research): land the PAO-R4 amendment and its conformance verification`
- `db8c9b2cb merge(research): land PAO-R4 research and its independent audit`
- `ba566d024 merge(research): land the PAO-R36 census attribution correction (W4-K01)`
- `3bf3f51de merge(research): land the PAO-R36 amendment and its conformance verification`
- `a806e0281 merge(research): land PAO-R36 research and its independent audit`
- `df02cca23 merge(research): land the OPS-R14 bounded remediation and its delta verification`
- `3dbfdb263 merge(research): land the OPS-R14 amendment and its conformance verification`
- `cfd828c04 merge(research): land OPS-R14 research and its independent audit`
- `25d601bcd docs(reference): specify the policy-operations research pipeline`
- `9ebc718eb research(s0-gap-02): reduce the six-way P37 register to the five registered classes under W4-K02`
- `6f48fc83d research(pao-r36): correct census attribution under ratified W4-K01`
- `9b4375c25 research(pao-r4): correct census attribution under ratified W4-K01`
- `2560cb3f4 plan(backlog): Rev 7 — wave 4 closed and ratified; standing axes, absent/unallocated, Pattern Pass to P38`
- `c26cbc9b3 docs(wave4): ratify W4-K01..W4-K06 — what the deciding machinery may turn on`
- `176335d97 docs(patterns): register P38, the P37 fixed-point corollary, the P35 holder rider, and absent/unallocated`
- `29f526527 docs(wave4): add package and wave standing statement`
- `e19c91212 docs(wave4): add orientation audit record`
- `147ce8ee2 docs(wave4): add ratification candidates`
- `f289de7d0 docs(wave4): add deduplicated routing map`
- `cf498d0c6 docs(wave4): add complete disposition ledger`
- `610e48556 docs(wave4): consolidation orientation pack — the audit is not an ancestor of the amendment, and the census gap is closed by recomputation`
- `915ed6031 docs(ops-r14): add bounded remediation delta verification`
- `62de2c5fe docs(ops-r14): add bounded remediation ledger`
- `48031ecc5 docs(ops-r14): apply bounded P37 remediation to primary report`
- `3ff74a782 docs(ops-r14): split F-14 and add red succession probe`
- `1650c1621 docs(ops-r14): split F-14 succession worlds in replay semantics`
- `a7644dfa2 docs(ops-r14): complete R8 currentness refusal`
- `43a497b55 docs(ops-r14): align amendment ledger with bounded remediation`
- `0032adbdf docs(ops-r14): remediate census provenance and denominators`
- `0fe8fe6a0 docs(ops-r14): add independent amendment conformance verification`
- `93571fd3c research(pao-r4): add independent amendment conformance verification`
- `47f0680f4 docs(verification): add PAO-R36 amendment conformance verdict`
- `d8ecdaaac docs(verification): add PAO-R36 amendment orientation ledger`
- `0c7ab71aa audit(s0-gap-02): verify amendment conformance`
- `4147384c8 docs(gy): withdraw the branch plan copy; GY-engine-subordination.md has one owner on main`
- `708003630 plan(gy,atlas): P38, GY-DEF14 as a class, GY-DEFC-4..6, GY-GAP4 landed, DS5 line-address closure, DS-INFRA-2`
- `94e2c8ca0 DS5-C18a make flag exposure registry strict`
- `dec77a050 DS6-C11 instrument Atlas health metrics`
- `a1e6ebcdc DS5-C16b-R2 record final verification`
- `202930742 docs(gy): declare confidence transition`
- `b662d8a81 docs(gy): record GY-GAP4 producer input`
- `1b096b222 test(runtime): isolate terminality schema witness`
- `0cfcf6690 DS5-C16b-R2 bind dispute scope snapshot`
- `03e8fa83d fix(runtime): fail closed on recovery ambiguity`
- `2789b49ea fix(gy): own N11 null representation`
- `09f9e16dc fix(runtime): bind run terminality authority`
- `78ea7c3d7 DS5-C16b-R2 partition dispute interaction state`
- `1775cf8a5 fix(runtime): keep terminality behind the HTTP adapter`
- `ec7228eff feat(runtime): publish producer-signed run terminality`
- `1ac08391b docs(gy): record zero-move null census`
- `3f9c817b2 docs(gy): register null representation defect`
- `e5a190261 DS5-C16b-R1 record structural recut`
- `72522acd9 DS5-C16a-R1 partition causal draft state`
- `b856d4e1f DS6-C10 record stopped readiness reconciliation attempt`
- `7b15ea2df docs(gy): record confidence ledger reprobe stop`
- `a7ae91891 Revert "DS6-C10 checkpoint stopped readiness reconciliation attempt"`
- `573be9598 DS6-C10 checkpoint stopped readiness reconciliation attempt`
- `a67d172e6 docs(gy): close defc6 at owner bundle`
- `96a7e6dff DS5-C15a partition Clerk session codec`
- `4f1f71cd3 DS5-C13b-R7 close scoped composer persistence`
- `07fd56378 Reapply "DS5-C13b-R6 checkpoint composer local state"`
- `19293faaa DS5-C21d retire migration address bindings`
- `ca9bc59b0 docs(gy): authorize single cold n11`
- `b340a8845 fix(gy): close depth corruption diagnostics`
- `a84556865 DS6 attribute C15-R1 visual regressions`
- `dd52314af DS5 record C13b-R6 structural stop`
- `97d0c6208 DS6-C16 close deferred-lane diagnostics`
- `f77850487 Revert "DS5-C13b-R6 checkpoint composer local state"`
- `a3ad1e615 DS5-C13b-R6 checkpoint composer local state`
- `b63e53b05 docs(gy): record depth measurement correction`
- `05bac9e37 DS5 record governed timing ceilings`
- `d095b9feb docs(gy): open defc6 budgeted depth wave`
- `6700ff36e docs(gy): correct depth census predicate`
- `42f60729f docs(gy): record defc5 closeout`
- `4bc138373 docs(gy): close defc5 at depth census cap`
- `93a6ba2d8 docs(gy): record depth census cap nonreceipt`
- `7a259daa6 fix(gy): bind depth migration to proof source`
- `1f7d549c0 fix(gy): migrate depth recording once`
- `c1a4df93b fix(gy): preserve aligned comparison once`
- `974036d4e fix(gy): align legacy comparison before projection`
- `8829bbe9b chore(gy): reissue n10a v2 projection`
- `5e868da0c DS5-C17a-R2 partition operator craft local state`
- `d875a2285 docs(gy): record n10a source-bound nonreceipt`
- `41a2020d5 DS6-C13 verify adjacent print export`
- `075eedb3b DS6-C08 wire automated evidence capture`
- `bc9421163 DS5-C13b-R5 close service-worker authority bridge`
- `b4afdf052 docs(gy): record recurring n10a contention`
- `c6a26e6fb docs(gy): record n10a contention nonreceipt`
- `13ceb3762 docs(gy): declare n10a v2 transition`
- `7e6478b71 Reapply "checkpoint: preserve stopped DS5-C13b-R3 service-worker closure"`
- `8a9e32058 DS6-C05 record serialized evidence wave`
- `f2aa668e3 chore(gy): reissue generation v2 projection`
- `fd2971e73 DS5-C13b-R4 repair offline queue production denominator`
- `2666f5628 docs(gy): record generation acceptance non-receipt`
- `38f11fe00 docs(gy): correct generation contention interval`
- `475815945 docs(gy): declare generation v2 delta`
- `64dbb87cb docs(gy): record contended generation non-receipt`
- `0a288717d chore(gy): reissue promotion v2 projection`
- `fef63760d docs(gy): declare promotion v2 delta`
- `a64391514 docs(gy): record depth migration review gate`
- `cd29ca29d fix(gy): rebind depth migration envelopes`
- `bddbe85d8 fix(gy): bind promotion comparison to semantic ledger`
- `b9fcdbd66 Revert "checkpoint: preserve stopped DS5-C13b-R3 service-worker closure"`
- `efd5ebcba checkpoint: preserve stopped DS5-C13b-R3 service-worker closure`
- `4748b9211 DS6-C15-R1 gate quantitative-use declarations`
- `2e144c048 DS5-C13b-R2 re-anchor composer DB module`
- `769c08b35 DS6-C15 record stopped numeric plural attempt`
- `cf80700bb Reapply "checkpoint: preserve stopped DS5-C13b-R2 rename"`
- `8171ed209 fix(gy): compose depth recording admissions`
- `4d7743f07 Revert "DS6-C15 checkpoint stopped numeric plural attempt"`
- `8fd8f9e5d DS6-C15 checkpoint stopped numeric plural attempt`
- `e7c3b08a7 fix(gy): keep comparison proof custody private`
- `cc4ca6d82 fix(gy): seal promotion comparison proof`
- `f4990b6f5 Revert "checkpoint: preserve stopped DS5-C13b-R2 rename"`
- `56eeef256 checkpoint: preserve stopped DS5-C13b-R2 rename`
- `23a3f364f fix(gy): bind controlled recording comparison`
- `a11b4f4a3 docs: freeze GY-DEFC-5 recording comparator contract`
- `ba18ad7d7 docs(gy): record depth comparison stop`
- `d15681e5d chore(gy): reissue n10a comparison receipts`
- `482c204d9 chore(gy): reissue generation comparison receipt`
- `7d02818a0 chore(gy): reissue promotion comparison receipt`
- `5591eb370 docs(gy): record reviewed def14 census`
- `708d18d6b fix(gy): bind n10a transition source scope`
- `8816df5f4 fix(gy): gate n10a writes on measured transitions`
- `ae3d713d4 fix(gy): bind comparison manifests to owner policy`
- `207069dae fix(gy): bind verification comparison to full receipts`
- `db6c4c350 DS5-C21c bind structured evidence identities`
- `23b421add docs(gy): bind defc4 census to corrected freeze`
- `e2f23c6eb style(gy): clarify depth comparison owner`
- `e1bf84804 fix(gy): bind verification comparison to projection owners`
- `b15747da6 DS6-C12 correct measured path declaration`
- `4e148ec9a DS6-C12 seed honesty comprehension protocol`
- `ceccb0746 DS5-C21b-R1 close TypeScript line-address migration`
- `122208801 DS6-C09 bind manual AT evidence to maturity`
- `d03f0c6e6 fix(gy): exclude declared verification blocks from comparison hashes`
- `7041a433e docs(gy): freeze defc4 predicate contract`
- `055345536 Reapply "checkpoint: preserve stopped DS5-C21b identity migration"`
- `85a839f27 DS6-C07 define evidence artifact storage`
- `b20951668 DS6-C01-R1 justify count exemptions and repair active plurals`
- `f0e138d6b Revert "checkpoint: preserve stopped DS5-C21b identity migration"`
- `3b0b721a4 checkpoint: preserve stopped DS5-C21b identity migration`
- `a9d276177 docs(gy): record DEF14 blast-radius stop`
- `2fc42db92 DS6-C02 add opaque rendered-contrast probe`
- `82cb9ac57 DS6-C01 close count parity and freeze Russian keys`
- `015fb8f08 DS5-C21a establish TypeScript reference identity`
- `b28101e42 DS6-C00 open evidence workflow slice`
- `0ff4ed681 docs(gy): record DEF14 source-fence blocker`
- `9a24a4efa docs(gy): record rejected N10a reissue`
- `74b94f301 docs(gy): record corrupt-lane ruling`
- `60a06701c docs: register DS5 line-address binding defect`
- `e21d2b5e6 docs(gy): record DEFC-3 retry checkpoint`
- `1b34c7f6c fix(tools): derive timing budgets from successful runs`
- `653f12d08 DS5-C13a-R3 delete authority mutation replay`
- `c1a89b6cf plan(gy): register GY-DI2 and GY-DI3 — the timing catalog failed the way INFRA-2 was built to prevent`
- `0fbf3bf7b docs(gy): record DEFC-3 writer nonreceipt`
- `f4f62ca58 Revert "checkpoint: preserve stopped DS5-C13a-R2 governed receipts"`
- `95274a88c checkpoint: preserve stopped DS5-C13a-R2 governed receipts`
- `dac4e28fa plan(gy): register GY-DEF14 and GY-DEFC-3`
- `ec4a9f091 Merge branch 'codex/gy-def13' — the path binding is fixed; the address no longer decides`
- `b49b6e1df docs(gy): record def13 cold boundary`
- `dcd8b073b Revert "checkpoint: preserve blocked DS5-C13a authority replay deletion"`
- `c2a03de41 checkpoint: preserve blocked DS5-C13a authority replay deletion`
- `f015e6631 fix(gy): reissue path-independent provenance`
- `66bad69b0 test(gy): bind provenance witnesses end to end`
- `a352ba1b6 test(gy): prove editable identity through provenance`
- `883febe7f fix(gy): bind editable discovery identity`
- `8794d58c8 docs: correct DS5 C07 drift attribution`
- `8f7a39194 plan(gy): register GY-DEF13 — the provenance manifest binds an address, not an identity`
- `5f19f86b8 Merge branch 'codex/gy-defc-2' — drift failures now self-describing; N11 boundary not_established`
- `06f24a40c DS5-C07b-D1 record generated-client single-owner debt`
- `53fe8a84c DS5-C12b-R1 enforce governed query policy`
- `e988619f5 docs(gy): record DEFC-2 classification`
- `d1a428d15 fix(gy): bind replay drift diagnostics`
- `98514488a fix(gy): describe embedded replay drift`
- `15c89d241 DS5-C12a register query construction debt`
- `125b6d604 docs: bind DS5 mechanism rounds and duplication duty`
- `d8f4bf142 plan(gy): record GY-DEFC-1's standing and register GY-DEFC-2`
- `8d87624db Merge branch 'codex/gy-defc-1-diag' — N11 boundary diagnosed not_established, discriminator named`
- `b0d7dcaa6 Revert "checkpoint: preserve stopped DS5-C07 audience mapping"`
- `3db3f4154 checkpoint: preserve stopped DS5-C07 audience mapping`
- `40fc512ae DS5-C08a isolate auth test fixtures`
- `7fbf1823c DS5-C14a record local-state envelope debt`
- `5acbde148 Revert "checkpoint: preserve rejected DS5-C12a query census"`
- `6e6422540 checkpoint: preserve rejected DS5-C12a query census`
- `4542ec9d0 docs(gy): diagnose N11 cold worker boundary`
- `4a4fadd47 docs: bind DS5 construction residual`
- `e18861d12 Merge branch 'codex/gy-defc-1' — two class owners land, cold closeout still blocked`
- `77356ba98 Revert "DS5-C12a checkpoint query cache policy conflict"`
- `22a8c2f32 DS5-C12a checkpoint query cache policy conflict`
- `f37c3fe9e docs: record DS5 C12a enforcement conflict`
- `b2c2b3347 docs(gy): record cold closeout non-receipt`
- `6782cb546 artifacts(gy): reissue Depth-N receipt`
- `0b811e884 DS5-C08b-D1 record auth-session revision debt`
- `bba532ea2 artifacts(gy): reissue composition certificate`
- `3fa8af6dc artifacts(gy): reissue value and second-domain receipts`
- `431bcd798 feat(gy): bind cold closeout inputs and projections`
- `c8c7a291c DS5-C11a derive cache observation posture`
- `edb8e045f DS5-C08b-R2 fail closed on unsettled identity`
- `5e93edf88 DS5-C04b-R2 restore capability construction lint`
- `c2eeddb2a DS5-C05b-R3 restore semantic-copy issuer`
- `c088c0e3d docs(gy): census cold closeout inputs`
- `355e81be8 plan(gy): register GY-DEFC-1, the cold-closeout restoration task`
- `fe840d3ab Merge branch 'codex/gy-def6' — DEF6 closed on the defect axis, capability still blocked`
- `17e9b70ac docs(gy): close DEF6 and hand off cascade`
- `bffef7881 docs: bind DS5 review bars and waits`
- `c61a4b5fb DS5-C06-D1 record waist producer gaps`
- `2d41f2675 Revert "checkpoint: DS5-C06-D1 oversized owner-debt atom"`
- `d86303b29 checkpoint: DS5-C06-D1 oversized owner-debt atom`
- `aa6924d4a docs: audit DS5 producer existence`
- `0baaeff1d DS5-C05b-D2 record semantic-copy deferral`
- `29860333e docs: correct DS5 deferral closure census`
- `c9f08463e docs: cap DS5 deferral verification`
- `6893f91c7 Revert "DS5-C05b-D1 blocked checkpoint after two fix rounds"`
- `d31ae0e3c DS5-C05b-D1 blocked checkpoint after two fix rounds`
- `216ff491b Revert "DS5-C05b-R2 blocked checkpoint after two fix rounds"`
- `ac24327c3 DS5-C05b-R2 blocked checkpoint after two fix rounds`
- `ba55b71b5 Revert "DS5-C05b-R1 checkpoint stopped semantic-copy attempt"`
- `932d65c4f DS5-C05b-R1 checkpoint stopped semantic-copy attempt`
- `3976c79aa DS5-C05a-R1 separate product and frozen locales`
- `153d0a3c0 DS5-C04b-D1 defer capability construction lint`
- `80c5cc4a8 Revert "DS5-C04b blocked checkpoint after two fix rounds"`
- `32598d109 DS5-C04b blocked checkpoint after two fix rounds`
- `cef274940 DS5-C04a-R1 strangle capability fallback`
- `09d4c1a45 DS5-C03b-D1 defer direct authority transport lint`
- `1d0ff1f53 Revert "DS5-C03b-R2 blocked checkpoint after two fix rounds"`
- `54fec7ae9 DS5-C03b-R2 blocked checkpoint after two fix rounds`
- `6c6c31299 DS5-C03a-R1 record raw transport drift`
- `e708e8f77 fix(gy): bind N8 catalog discovery provenance`
- `e69d95423 docs: recut DS5 content-bound register clusters`
- `90e20d31e Merge branch 'codex/gy-infra-3-step2' — E11 freeze/batch gate, implemented_but_not_orchestrated`
- `c1d711a1c feat(tools): enforce E11 review freeze gate`
- `bf108f897 plan(gy): register GY-DEF6 and adopt the GY-INFRA-3 Step 0 verdict`
- `4afca8b90 docs(gy): record infra-3 step0 diagnosis`
- `c14e3d435 research(s0-gap-02): finalize amendment delivery receipt`
- `10c0b6c09 research(s0-gap-02): finalize orientation ledger`
- `8a2224ac3 research(s0-gap-02): finalize external transfer ledger`
- `d38978c24 research(s0-gap-02): amend falsifier suite`
- `5e34bdbf5 research(s0-gap-02): amend benchmark oracle architecture`
- `0df03f35e research(pao-r4): record final amendment payload readback`
- `04ff572ba research(pao-r4): reset amendment receipt after payload revision`
- `1bd865f85 research(pao-r4): express rule transport with bounded existing verdict`
- `4432a1ace research(pao-r4): keep rule transport outside outcome vocabulary`
- `e5d53dd19 research(s0-gap-02): amend sealed expectation semantics`
- `0223c140a research(s0-gap-02): amend oracle custody and adjudication`
- `ea3c384cb research(s0-gap-02): amend mutation and receipt specification`
- `b2baf118c research(pao-r4): record amendment payload readback`
- `57681aa0d research(s0-gap-02): amend independence model`
- `926326174 docs(pao-r36): amend falsifier suite`
- `9f33c1e10 research(pao-r4): correct P35-P37 orientation anchor`
- `e0cb9395c research(pao-r4): correct P35-P37 anchor`
- `cc7598079 research(s0-gap-02): amend integration handoff`
- `3cb42612c docs(pao-r36): amend primary correction report`
- `e9c2e70ed docs(pao-r36): amend ordered fanout contract`
- `fd0fb177f research(s0-gap-02): amend external transfer ledger`
- `0e988b744 research(s0-gap-02): amend delivery provenance and readback`
- `83539ebf0 docs(ops-r14): add independent-audit amendment ledger`
- `61da3d0d2 research(s0-gap-02): reconcile orientation census`
- `03c61b7a4 docs(ops-r14): consolidate independent-audit amendment`
- `f9f25d408 plan(gy): register GY-INFRA-3 and record GY-INFRA-2's closure`
- `4c5fba015 research(pao-r4): record audit amendment dispositions`
- `dfbc61b4f docs(pao-r36): amend comparative models and hard cases`
- `f3090dde6 docs(pao-r36): amend owner and dependency handoff`
- `57c0a86a0 research(pao-r4): pin external sources and narrow legal comparison`
- `4f9e3b966 research(s0-gap-02): add amendment ledger`
- `69ae9f6ff docs(ops-r14): bound procurement source transfer`
- `d94cfe5d1 docs(pao-r36): settle complete orientation census`
- `279b500ae docs(pao-r36): amend external source transfer limits`
- `36e2f57b9 docs(ops-r14): correct capability labels and handoff`
- `71421c202 docs(ops-r14): amend replay semantics and seam closure`
- `b505ad8bf docs(ops-r14): amend recovery predicate and standing`
- `4049b75ff research(pao-r4): reopen handoff owner placement and predicate provenance`
- `4993680eb research(pao-r4): rewrite falsifiers as exact use-boundary cases`
- `837619f36 docs(ops-r14): extend fixtures and drill evidence`
- `060c7ac1b research(pao-r4): amend comparative firewall selection`
- `e067f8f1a docs(ops-r14): add prospective dependency reconciliation`
- `57ee85fba research(pao-r4): correct complete source census`
- `11c8f4578 research(pao-r4): amend formal boundary and firewall contract`
- `033e3fc72 docs(pao-r36): add post-audit amendment ledger`
- `69cfee072 docs(ops-r14): amend orientation census and standing axes`
- `e089f508b Merge branch 'codex/gy-infra-2' — verification economics A/B green, C closed negative`
- `109ba3f44 docs(patterns): register P37 and make P35 symmetric over search indexes`
- `bc6fd7704 docs(gy-infra-2): close verification economics`
- `5d2d98ddc fix(tools): bind review package ratio receipt`
- `3abbaf8c2 audit(s0-gap-02): add executable revision register`
- `2201d3257 audit(s0-gap-02): add seam and crosscheck audit`
- `89f77d341 audit(s0-gap-02): add formal argument and falsifier audit`
- `c6cb54500 audit(s0-gap-02): add anchor and citation verification`
- `735716c27 audit(s0-gap-02): add claim evidence ledger`
- `e5b019b4b audit(s0-gap-02): add hostile independent audit register`
- `bfb0d8bea audit(s0-gap-02): complete orientation error ledger`
- `34c65a04e docs(audit): deliver OPS-R14 independent audit verdict`
- `60ee971bb docs(audit): add OPS-R14 recommended revision register`
- `0fe8e2397 docs(audit): add OPS-R14 seam and kernel crosscheck`
- `9b6539be4 docs(audit): add OPS-R14 formal argument audit`
- `eaf21b7fa docs(audit): verify OPS-R14 anchors and external sources`
- `e8941473d docs(audit): add OPS-R14 claim-evidence ledger`
- `9bbfd37a2 docs(audit): add PAO-R36 independent audit`
- `9603b3d09 docs(audit): add PAO-R36 recommended revision register`
- `caa5a8451 docs(audit): add PAO-R36 seam and crosscheck`
- `426d6c9a6 docs(audit): add PAO-R36 formal argument audit`
- `7538f694c docs(audit): add PAO-R36 anchor and citation verification`
- `b762cf656 docs(audit): add OPS-R14 orientation error ledger`
- `41020abc8 docs(audit): add PAO-R36 claim evidence ledger`
- `56cc093fd docs(audit): add PAO-R36 orientation error ledger`
- `6cc64e8ad audit(s0-gap-02): canonicalize census extraction request`
- `e487a8b35 audit(s0-gap-02): bind exact census extraction request`
- `69182c079 audit(pao-r4): deliver independent verdict`
- `91baee424 audit(pao-r4): specify required revisions`
- `9edc52e33 audit(pao-r4): map claims to evidence`
- `76e8045f0 audit(pao-r4): crosscheck seams and capability labels`
- `df0efbbf4 audit(pao-r4): attack formal and detection arguments`
- `9a535d24c audit(pao-r4): verify anchors and external sources`
- `c150e607f audit(s0-gap-02): add exact tree retrieval reference`
- `5a58386f5 audit(pao-r4): reproduce orientation census`
- `c8adf0b17 audit(s0-gap-02): establish orientation ledger shell`
- `a27c3da99 docs(pao-r4): record remote delivery readback`
- `4120dc79a research(pao-r4): restore complete falsifier suite`
- `ed9427fa5 research(pao-r4): restore complete comparative survey`
- `9c0f5108e research(pao-r4): restore complete orientation ledger`
- `3ccec71ce docs(pao-r4): record delivery incident`
- `3046f73d7 research(pao-r4): record legal transfer ledger`
- `0f2172cb8 research(pao-r4): map integration handoff`
- `b21c94f76 research(pao-r4): specify firewall falsifiers`
- `d41fd04b5 research(pao-r4): compare firewall control models`
- `12cda9223 research(pao-r4): record orientation census`
- `ba4b48e0d research(pao-r4): define the individual-decision firewall`
- `a7c34cc40 research(s0-gap-02): deliver the independent custody-benchmark oracle architecture`
- `3a694212a docs: deliver OPS-R14 custody resilience research`
- `67b2f72b6 docs: add OPS-R14 integration handoff`
- `44ade2500 docs: add OPS-R14 primary-source transfer ledger`
- `ef0f23013 docs: add OPS-R14 disaster fixtures and drill contract`
- `33a1c804b docs: add OPS-R14 long-term replay semantics`
- `0b7c99009 docs: add OPS-R14 watched dependency semantics`
- `29bab4e64 docs: add OPS-R14 custody recovery objectives`
- `1bccc012b docs(research): complete PAO-R36 Pass I line-count audit`
- `e3d36ad24 docs: add OPS-R14 orientation ledger`
- `a8d40aa3e docs(research): add PAO-R36 public correction report`
- `652b8ea4d docs(research): add PAO-R36 external source transfer ledger`
- `b57adc048 docs(research): add PAO-R36 falsifier suite`
- `350336acb docs(research): add PAO-R36 integration and dependency handoff`
- `42274f1c9 docs(research): add PAO-R36 ordered fan-out contract`
- `a08e693ee docs(research): add PAO-R36 comparative models and hard cases`
- `7df07eab4 docs(research): correct PAO-R36 orientation arithmetic`
- `139282761 docs(research): add PAO-R36 orientation ledger`
- `1a7a2d05e plan(wave2): adopt the execution sequence for the seventeen remaining research tasks`
- `260ae2330 fix(pv): cite INT-R8's controlling head in the GY Rev 26 line`
- `98bb0726c docs(agents): add the delivery read-back rule and index the two ratification acts`
- `acb641dac plan(pv): record DS12 research-input closure and the Wave-2 completion ledger`
- `ce819de57 plan(pv): register GY-GAP3 and route the ratified kernel into GY-N12`
- `391d239cf decide(pv): ratify the nine public-verification and disclosure invariants PV-K01-PV-K09`
- `93a961086 merge(research): land the INT-R7/INT-R8 wave consolidation`
- `77d15b5a0 merge(research): land the INT-R8 bounded remediation and its verification`
- `ead6e5ace merge(research): land the INT-R8 amendment and its conformance verification`
- `31f13f708 merge(research): land INT-R8 research and its independent audit`
- `33d53806a merge(research): land the INT-R7 reachability invariant closure`
- `72d051232 merge(research): land the INT-R7 bounded remediation and its verification`
- `7fb1b2f52 merge(research): land the INT-R7 amendment and its conformance verification`
- `a0def4531 merge(research): land INT-R7 research and its independent audit`
- `a8709a8f7 research: correct repository evidence and FNV source attribution`
- `e1121e0b2 research: correct INT-R7 R8 report path denominator and evidence`
- `b3704476a research: add INT-R7 R8 open questions and next research`
- `61636a067 research: add INT-R7 R8 routing map`
- `d6eb0d4a3 research: add INT-R7 R8 repository findings register`
- `d0626b02e research: add INT-R7 R8 cross-audit finding matrix`
- `44a455a2c research: add INT-R7 R8 ratification candidates`
- `0019aee9a research: add INT-R7 R8 consolidation report`
- `79e64f13e research: add INT-R7 R8 preflight and seam adjudication`
- `3883b4547 docs(research): finalize INT-R7 reachability closure read-back record`
- `75d8c4525 docs(research): add INT-R7 reachability invariant closure ledger`
- `cf05b19ec docs(research): enforce INT-R7 supersession reachability invariant`
- `8a0847ffd docs(verification): confirm INT-R8 bounded remediation`
- `807e6f4cb docs(verification): add INT-R8 remediation conformance ledger`
- `286ade105 docs(research): add INT-R8 bounded remediation ledger`
- `f705c4a7c docs(audit): add INT-R7 remediation conformance ledger`
- `123142b25 docs(research): reconcile INT-R8 remediation denominators`
- `c62b4a0fe docs(audit): verify INT-R7 bounded remediation`
- `a3f493c80 docs(research): close INT-R8 fixture conformance gaps`
- `92c05323e docs(research): finalize INT-R7 remediation read-back record`
- `09cc60105 docs(research): add INT-R7 bounded remediation ledger`
- `00919d94e docs(research): tighten INT-R7 amendment evidence paths`
- `8b487e54e docs(research): repair INT-R7 suite grammar and vectors`
- `ead4aca36 docs(verification): deliver INT-R8 amendment conformance verdict`
- `1a35f61f5 docs(verification): add INT-R8 amendment conformance evidence ledger`
- `538cd0cd7 docs(research): separate issuer and requested-use predicates`
- `c531bdfac docs(research): make INT-R7 primary supersession reachable`
- `92b8773fe docs(research): add INT-R8 post-audit amendment ledger`
- `961ee8cd4 docs(research): correct and compact INT-R8 v2 suite`
- `80e79ee7e docs(research): add atomic INT-R8 v2 falsifiers and honest handoff`
- `c719a16d2 docs(research): operationalize INT-R8 loss boundary and receipt`
- `c6e3e9b7f docs(research): bound INT-R8 reconstruction and prefix discipline`
- `5225f8bf6 docs(audit): add INT-R7 amendment conformance evidence ledger`
- `e717e7684 docs(research): add deterministic QIF transfer models to INT-R8`
- `fc8b7c51d docs(audit): verify INT-R7 amendment conformance`
- `cf8a6beba docs(research): correct INT-R8 orientation censuses and callers`
- `e992d3126 docs(research): amend INT-R8 primary decision after audit`
- `f45f338f9 docs(audit): make INT-R8 finding anchors path-explicit`
- `b4f27bb3b docs(audit): deliver hostile independent audit of INT-R8`
- `2d922813e docs(research): finalize INT-R7 amendment evidence ledger`
- `b52335645 docs(audit): add executable INT-R8 revision register`
- `4065caf91 docs(research): add INT-R7 post-audit amendment ledger`
- `f55ce31f7 docs(audit): add INT-R8 claim and capability evidence ledger`
- `309300c57 docs(audit): add INT-R8 kernel and INT-R7 seam crosscheck`
- `91a5af066 docs(research): amend INT-R7 public verification lifecycle`
- `6d3142af3 docs(audit): add INT-R8 formal argument and falsifier audit`
- `24186c19c docs(audit): verify INT-R8 anchors and primary sources`
- `e836dd22e docs(research): publish exact INT-R7 falsifier suite v2`
- `0422ddcce docs(audit): add INT-R8 orientation error ledger`
- `e252f0503 docs(research): amend INT-R7 citizen verification semantics`
- `61c1a6283 docs(research): amend INT-R7 preservation and recovery gates`
- `f956fb8be docs(research): amend INT-R7 public verification profile`
- `290f4cf84 docs(research): decompose INT-R7 verification dimensions`
- `ae3e1dd14 docs(research): amend INT-R7 comparative transfer boundaries`
- `c6f84a940 docs(research): correct INT-R7 capability and dependency classifications`
- `b2a3c8ac4 docs(research): amend INT-R7 source transfer ledger`
- `539ebafc6 docs(research): amend INT-R7 orientation and reproduction ledger`
- `54e8f41d7 docs(audit): add INT-R7 hostile independent audit verdict`
- `e54f495f2 docs(audit): add INT-R7 formal argument audit`
- `de0d0f574 docs(audit): add INT-R7 executable revision register`
- `977b4330e docs(audit): add INT-R7 anchor and source verification`
- `90b372964 docs(research): deliver INT-R8 compression loss and disclosure composition`
- `67558982a docs(audit): add INT-R7 seam and kernel crosscheck`
- `18dfadebd docs(audit): add INT-R7 claim evidence ledger`
- `05e690d53 docs(audit): add INT-R7 orientation error ledger`
- `06ef1264a docs(research): add INT-R8 primary source and transfer ledger`
- `19585bb3a docs(research): add INT-R8 falsifiers and integration handoff`
- `3fd9f1580 docs(research): formalize INT-R8 reconstruction and disclosure discipline`
- `a1c6bc053 docs(research): define INT-R8 loss contract and materiality boundary`
- `8d028710e docs(research): add INT-R8 orientation audit ledger`
- `f5671253b docs(research): deliver INT-R7 public verification proof lifecycle`
- `cada64849 docs(research): add frozen INT-R7 falsifier suite`
- `ac77d76f0 docs(research): add INT-R7 citizen verification UX requirements`
- `86c3b263d docs(research): add INT-R7 PublicVerificationProfile contract`
- `92d1506af docs(research): add INT-R7 threat model and verification predicates`
- `c2d9df2eb docs(research): add INT-R7 pinned orientation audit ledger`
- `8f88a9ea9 docs(research): add INT-R7 repository integration handoff`
- `a1498dc25 docs(research): add INT-R7 lifecycle migration and preservation profile`
- `f816c5e1d docs(research): add INT-R7 comparative proof models`
- `a9e4501ab docs(research): add INT-R7 external source and transfer ledger`
- `02c5b8d23 docs(patterns): register P35 sampled-denominator generalization and P36 authority by adjacency`
- `295a0898e plan(int-wave): route the ratified claim-semantics kernel into GY, Atlas and the Wave-2 backlog`
- `8128ad919 decide(int-wave): ratify the eight claim-semantics invariants INT-K01-INT-K08`
- `65b0beb72 fix(int-r9): complete the INT-R10 rebinding and close the carried bookkeeping gaps`
- `8cb4b8cf4 merge(research): land the INT-R1/R9/R10 wave consolidation`
- `4ec2250d8 merge(research): land the INT-R9 amendment conformance verification`
- `babf3f606 research: add INT wave next-research register`
- `815076929 research: add INT wave routing map`
- `e9d6644a7 research: add INT wave repository findings`
- `b9dcf893b research: add INT wave cross-audit matrix`
- `8c794950c research: add INT wave consolidation kernel`
- `52dd773a8 verify(int-r9): add amendment conformance ledger`
- `5900b39da verify(int-r9): record amendment conformance verdict`
- `a548a2f93 merge(research): land the INT-R10 revision verification`
- `a45181ef9 verify(int-r10): add finding conformance ledger`
- `982c1fdf7 verify(int-r10): confirm revision conformance`
- `01a9ec884 docs: architect corrections to the INT-R9 and INT-R1 amendments`
- `250a18828 merge(research): land the INT-R10 revision, superseding the audited artifact`
- `ea11e89b0 merge(research): land the INT-R10 independent audit`
- `2b29fb576 merge(research): land INT-R10 family-wise risk composition (as audited)`
- `1a110e792 merge(research): land the INT-R9 post-audit amendment`
- `6e0863392 merge(research): land the INT-R1 amendment verification`
- `558cb41ec merge(research): land the INT-R1 post-audit amendment`
- `a334f7d84 research(int-r10): account for all audited anchor sites`
- `07f74631b research(int-r10): add audit revision ledger`
- `8de272198 research(int-r10): rebuild fixture and demote artifact sketch`
- `56f895563 research(int-r10): revise source and transfer ledger`
- `946667f3c research(int-r10): repair canonical family composition`
- `f5c9103ba docs: pin the GY-GAP2 envelope to the expanded per-class weight`
- `36a052e3e docs: correct the GY-GAP2 arithmetic after the INT-R10 audit`
- `bb322361e docs(int-r9): record amendment closure ledger`
- `58d975246 docs(int-r9): retire executable protocol yaml`
- `5e1a890fa docs(int-r9): add post-audit falsifiers`
- `7bc799fcd docs(int-r9): align state and artifact sketches with adaptive protocol`
- `7f41bf8b7 audit(int-r10): deliver independent adversarial verdict`
- `491f59ff6 docs(int-r9): correct contamination and reviewer census`
- `1038b822d audit(int-r10): record required revisions before consolidation`
- `fa4f1d11b docs(int-r9): withdraw numeric family claim after audit`
- `5e915fdfe audit(int-r10): add exhaustive claim-evidence ledger`
- `84222ccc5 audit(int-r10): grade conformance to the R1 specification`
- `85995fc7b audit(int-r10): verify repository anchors and external sources`
- `16bba69a7 audit(int-r10): verify supplied orientation facts`
- `f2cfd22d6 audit(int-r10): examine the formal arguments`
- `8b8693f05 docs(INT-R1): add amendment conformance ledger`
- `fa50d7448 docs(INT-R1): verify amendment conformance`
- `317fc9c36 research(int-r10): correct fixture repository rule anchors`
- `3ba4e005c research(int-r10): correct source-ledger repository rule anchors`
- `a848f44d4 research(int-r10): correct repository rule line anchors`
- `9db1e75f8 research(int-r10): anchor source-transfer conclusions to pinned owner state`
- `b77f960b1 research(int-r10): anchor fixture baseline to live owner paths`
- `f2fd298ca research(int-r10): make repository anchors fully explicit`
- `ebb6afcf1 research(int-r10): bind family fixtures to precommitted member plan vector`
- `620388370 research(int-r10): tighten fixed-plan and adaptive composition boundary`
- `212864ab9 research(int-r10): conclude family-wise risk composition`
- `66baff37c docs(INT-R1): correct amendment frontmatter ledger summary`
- `c384e462f docs(INT-R1): add post-audit amendment ledger`
- `90dc728bf research(int-r10): add family composition fixture and artifact sketch`
- `36111b152 docs(INT-R1): block OM-01 on GY-GAP1 and preserve red semantics`
- `267d573f5 docs(INT-R1): make artifact sketch refusal-first and one-lattice safe`
- `e68ed7491 research(int-r10): add primary-source transfer ledger`
- `23e12739f docs(INT-R1): separate conditional theorem from admissibility protocol`
- `0d71fee89 docs(INT-R1): repair source attribution and normalize citations`
- `246d507c8 docs(INT-R1): narrow repository census and Rule-12 verdict`
- `50f117e56 docs(INT-R1): narrow theorem and current capability after audit`
- `978e6b958 merge(research): land the INT-R9 independent audit`
- `803417b14 merge(research): land INT-R9 first-promotion evaluation protocol`
- `31f4f73d9 merge(research): land the INT-R1 independent audit`
- `215645be6 merge(research): land INT-R1 obligation coverage and open-world completeness`
- `b56ba4de5 docs: register the repository findings measured by the INT-R1/INT-R9 audits`
- `ce354864f audit(int-r9): add ordered revision requirements`
- `fba1b06c6 audit(int-r9): add orientation error ledger`
- `9ff7dc8a2 audit(int-r9): cross-check S0-GAP-02 and INT-R1 seams`
- `67a1c7600 audit(int-r9): add adversarial protocol reading`
- `4d9469a05 audit(int-r9): verify anchors and external citations`
- `d0ebeca08 audit(int-r9): add claim evidence ledger`
- `a09128e6b audit(int-r9): record independent no-go verdict`
- `887bce985 docs: correct INT-R1 claim disposition summary`
- `0893a739e docs: add INT-R1 independent audit verdict`
- `fbba18ad6 docs: record INT-R1 revision requirements`
- `003b097f4 docs: add INT-R1 claim evidence ledger`
- `f8ae1c5fa docs: verify INT-R1 anchors and sources`
- `e1bca33f5 docs: audit INT-R1 formal arguments`
- `fe9b92ffd docs: audit INT-R1 supplied orientation`
- `14648fa5b fix(tools): close delta review gaps`
- `b9048c185 fix(tools): hermeticize review package inputs`
- `45dc19344 fix(tools): close timing review gaps`
- `f5ad92237 docs(research): deliver INT-R9 first-promotion evaluation protocol`
- `7cba15e56 DS5-C02 make architecture zero recurrent`
- `c935a610f docs(research): add INT-R9 adversarial fixture specifications`
- `82e136a8d docs(INT-R1): deliver obligation coverage and open-world completeness research`
- `c27f2cbaf docs(research): add INT-R9 state machine and artifact contracts`
- `e1644709e docs(research): add structured INT-R9 first-promotion protocol`
- `1a1e908fd docs(INT-R1): specify mutation benchmark and edge fixtures`
- `5ceb8443c docs(gy-infra-2): record closeout verification`
- `daae9ac36 docs(INT-R1): sketch typed artifacts and coverage lifecycle`
- `69b1cf2a0 docs(research): add INT-R9 proving-ground contamination census`
- `f612c2067 docs(INT-R1): formalize open-world impossibility and relative coverage`
- `d47407d1a docs(INT-R1): add primary-source transfer ledger`
- `2583dd2ab docs(gy-infra-2): close Part C review`
- `fe5036663 docs(INT-R1): record repository census and owner anchors`
- `5391639c6 docs(gy-infra-2): reconcile Gate-0 receipts`
- `4c8999334 docs(gy-infra-2): record negative Part C gate zero`
- `33a530d12 DS5-C01c freeze issuer enforcement gaps`
- `1d24793a1 docs(gy-infra-2): close Part B review`
- `ff446d788 docs(gy-infra-2): record Part B round-two repair`
- `6113c5ee8 fix(tools): refuse unbound diff configuration`
- `078c5257f docs(gy-infra-2): record Part B fix review package`
- `495bb0749 fix(tools): make review packages hermetic`
- `c8c02072a feat(tools): package full and delta code reviews`
- `d152565dc docs: annotate the plans and the Wave-2 backlog under the ratified kernel`
- `bfa31770d docs: AGENTS.md — carry S0-K03 plane decomposition and the S0-K06 band split`
- `514e61658 docs: adopt the Custody Time Model as the temporal target spec`
- `d9c5c6a9d docs: ratify the Stage-0 custody kernel S0-K01-S0-K16`
- `923f5ca33 docs(gy-infra-2): record Part A review verdict`
- `dc5ff8505 fix(tools): render catalog lanes in empty timing reports`
- `a14fe9a13 merge(research): land OPS-R4 temporal semantics for policy custody`
- `8a684cf5a merge(research): land the Stage-0 consolidation stack and the S0-GAP-01 decision`
- `a1ccf2936 merge(research): land the OPS-R15 independent audit`
- `24c3cfaea merge(research): land the PAO-R1 independent audit`
- `3febc3f19 merge(research): land the PAO-R0 independent audit`
- `6bcc95bff feat(tools): publish measured verification budgets`
- `53df61d40 docs: GY plan — register GY-DEF4, temporal diagnostic minting the authority pass token`
- `f1d9c5539 docs: GY plan Rev 21 — register three live repository defects outside the sequence`
- `498351be8 fix(tools): preserve timing summary denominators`
- `06b563134 feat(tools): persist direct verification timings`
- `c447d5744 DS5-C01b forbid authority escape hatches`
- `ad2f7585c docs: Atlas plan Rev 3.8 — DS-INFRA-1, restore incrementality where provably safe`
- `f4fc44d73 docs(gy-infra-2): plan verification economics work`
- `4b9e76f20 docs: GY-INFRA-2 — extend to three parts, replay-free work first`
- `1758ac357 docs: GY-DI1 — classify the over-binding as false withdrawal, not unsafe grant`
- `f41d49071 merge: land GY-N11 — honest confidence ledger (anytime-valid promotion risk)`
- `d671cb68a docs(gy-n11): record architect handoff receipts`
- `681d0de2f docs(gy-n11): distinguish no-op reissue receipts`
- `d9a46027d docs(gy-n11): correct closeout row semantics`
- `a8be8be1b docs(gy-n11): reconcile dependency-ordered closeout`
- `b19c33181 DS5-C01a census branded authority sinks`
- `c732eaa58 chore(gy-n11): converge second-domain receipt family`
- `94d10ed41 docs: correct the DS5 W2 evidence — detached worktree, not dropped commits`
- `cd2de8364 docs: record the DS5 work-preservation and history lessons in both plans`
- `ddc746a8f docs: land the verification-economics findings in both plans and AGENTS.md`
- `24e66b44c DS5-C10 defer G4 owner projection contract`
- `b3ad262e9 docs: GY plan Rev 20 — E11/E12 compute-economics gates + GY-DI1 debt from N11`
- `369065e8b chore(gy-n11): converge deployment receipt cascade`
- `2d6a532ed docs: recut DS5 enforcement execution clusters`
- `c08325a08 docs: Atlas plan — add the DS5 execution-order law after the ruling was over-applied`
- `3ffbc7bad chore(gy-n11): reissue depth-N capstone receipt`
- `94121785f chore(gy-n11): reissue grounding receipt chain`
- `636645bec docs: Atlas plan — rule the DS5 enforcement mechanism onto types, not flow analysis`
- `bc3dffcc3 chore(gy-n11): reissue composition certificates`
- `0fc3cd8c7 chore(gy-n11): reissue second-domain owner pack`
- `a03d4d80f chore(gy-n11): reissue N8 value gate receipt`
- `d20a95db9 chore(gy-n11): rederive Fork-B relation census`
- `1335509f7 chore(gy-n11): reissue promotion deployment receipts`
- `86a79fe96 fix(gy-n11): bind ledger accounting to owner provenance`
- `b67084dd6 DS5-C01 enforce canonical status ownership`
- `450bc31f3 chore(gy-n11): finalize deployment-bound receipts`
- `4556fc4c8 docs(gy-n11): reconcile closure evidence`
- `10586702c fix(gy-n10): isolate validator machine output`
- `11ce05571 style(fabric): sort public exports`
- `fcd110334 chore(gy-n11): rebind ledger to N13b route projection`
- `b5ca9af0a fix(gy-n11): honor advancing cold closeout`
- `f3c8e1780 chore(gy-n11): rebind N13b to N13a route projection`
- `8c506eb93 chore(gy-n11): rebind N13a to U3 capstone routes`
- `479533278 chore(gy-n11): rebind N10a gap evidence to N8`
- `1ff19637e chore(gy-n11): rebind N8 to U3 education context`
- `29ab2fc56 docs: Atlas plan — authorize the DS5 schema/contract-test fence; fix DS6 parallelism`
- `f489ba0ee test(gy-n11): restore behavioral source flip matrix`
- `d6b38294e DS5-C00 plan measured enforcement waist`
- `5e6482302 docs: Atlas plan — sync D4 to its ratified state (unblocks DS5 locale lint)`
- `71086ae48 fix(quality): account terminal N11 worker startup`
- `18642c2d6 fix(atlas): re-anchor DS4 status receipts onto the DS20-regenerated client`
- `bf5b76b0b docs: Atlas plan Rev 3.6 — DS4 closed & merged; six debts registered with owners`
- `7f450eb7b merge: land Atlas DS4 — status-grammar rebinding, 12 families, 47 statuses`
- `cb83a4c13 feat(quality): register data-only refusal instrument`
- `fb44ea5a6 docs: close Atlas DS4 for architect review`
- `470a802d4 test(dashboard): reconcile governed visual baselines`
- `5a5d422a8 chore(quality): freeze generic N11 ledger baseline`
- `0faf33e7b test(dashboard): prove authority posture on a real panel`
- `2d83e3264 fix(dashboard): name provenance popover dialog`
- `bfb30c82b fix(dashboard): restore counterfactual text contrast`
- `604b74e80 feat(quality): implement generic N11 confidence ledger`
- `31aae0c45 test(dashboard): budget the C14 decision-grade census`
- `810ef6b77 test(dashboard): stabilize C22 semantic scanners`
- `bc1d01001 fix(dashboard): contain readiness and scientific synthesis`
- `19de04940 feat(gy-n11): isolate verification replay`
- `1697c051d fix(gy-n11): bind live authority callables`
- `2a9da098e refactor(dashboard): retire local return vocabularies`
- `c1922e0a3 fix(gy-n11): bind loaded runtime and recover wal tails`
- `31134a9fa refactor(dashboard): bind provenance posture to generated metadata`
- `828531cf3 fix(gy-n11): preserve durable ledger witnesses`
- `869cb4628 fix(gy-n11): harden confidence ledger durability`
- `d2dceae95 refactor(dashboard): remove run lifecycle guessing`
- `2e9b26183 docs(research): decide S0-GAP-01 subject-reference owner`
- `fd4e32b44 docs(research): finalize external-source audit`
- `eb831318d docs(research): finalize external-source audit`
- `a1c1a0e0c docs(research): finalize external-source audit`
- `34a864373 docs(research): record final Stage-0 audit evidence`
- `6eafee90e docs(research): define OPS-R4 custody temporal semantics`
- `290725446 docs(research): amend Stage-0 anchor reports`
- `a55d33c7a docs(research): consolidate Stage-0 anchor audits`
- `11b0c2129 docs(research): consolidate Stage-0 anchor audits`
- `713cd082e docs(research): consolidate Stage-0 anchor audits`
- `46a7402ea docs(research): consolidate Stage-0 anchor audits`
- `a8e4cf480 docs(research): consolidate Stage-0 anchor audits`
- `fcc9c06e5 docs(research): consolidate Stage-0 anchor audits`
- `f576e3c34 docs(research): consolidate Stage-0 anchor audits`
- `f090887fb docs(research): consolidate Stage-0 anchor audits`
- `c567c1034 docs(research): consolidate Stage-0 anchor audits`
- `42a79a655 docs(research): independently audit OPS-R15 capstone benchmark`
- `566840c33 docs(research): independently audit PAO-R1 boundary register`
- `258aa740e docs(research): independently audit PAO-R0 against repository`
- `0e9aa6eef test(atlas): harden C22 semantic debt governance`
- `299fe06e8 refactor(dashboard): retire bounded status taxonomies`
- `5f63537c2 refactor(dashboard): close architecture severing remainder`
- `4bf425bfa refactor(dashboard): bind generated responsive breakpoints`
- `759f1722a chore(gy-n11): register confidence ledger artifact`
- `66dcdc0b6 refactor(atlas-ui): migrate shared patterns`
- `b171c4708 refactor(atlas-ui): migrate root compounds`
- `de7da6f5c chore(gy): freeze capstone owner supersession`
- `aaf537cc2 fix(gy): preserve refusal obligations across owner reissue`
- `f54902bfc fix(gy): make grounding witness ranking reissue-stable`
- `4813b49f6 docs: ratify PolicyOS identity and custody boundary; reshape Wave-2 research; audit both plans`
- `e5730cf6a refactor(dashboard): rebind compound evidence families`
- `7486eaa08 docs(atlas): authorize DS4 re-cut — clusters C21-C23`
- `650b692e3 fix(gy): chain capstone context rebind receipts`
- `1c05b9387 chore(gy): rebaseline the grounding benchmark`
- `3c16857f8 fix(gy): rebaseline the N11 receipt chain`
- `f444ba719 refactor(dashboard): fail closed on counterfactual projections`
- `a59efb3dc refactor(dashboard): rebind operator evidence primitives`
- `8a8c8169e refactor(dashboard): rebind trust view authority`
- `8bec7ab41 docs: distillation ledger Batch 9 & 10 — Cross-cutting Public Authority CPA-R1..R28`
- `af5cfd758 docs: distillation ledger Batch 8 — Foundry Phase 11 P11.01..P11.15`
- `adb4050f7 docs: distillation ledger Batch 7 — Foundry Phase 10 P10.01..P10.16`
- `9b97dc557 docs: distillation ledger Batch 6 — Foundry Phase 9 P9.01..P9.14`
- `f80f8f9bb docs: distillation ledger Batch 5 — Foundry Phase 8 P8.01..P8.14`
- `6f2a32008 docs: distillation ledger Batch 4 — Foundry Phase 7 P7.01..P7.14`
- `5d89adc3c docs: distillation ledger Batch 3 — Foundry P6.01..P6.17`
- `f8f0ae167 docs: distillation ledger Batch 2 — Fabric FAB-R1..R10`
- `c82db1e5a docs: start deep-research value distillation ledger (Batch 1 — Scientist SCI-R0..R10)`
- `c4e1b97e3 refactor(dashboard): rebind authored candidate posture`
- `9c45a240e fix(dashboard): rebind temporal semantics and cursor`
- `0ef16da1b fix(dashboard): classify nondecision numeric layout values`
- `23d2abed0 docs: Atlas plan — DS20 + DS20-B closed & merged; typed limitations registered as debt`
- `03ebc1ce8 merge: land Atlas DS20 + DS20-B — server authorization enforcement floor`
- `07ed51c81 refactor(dashboard): preserve chart quantity semantics`
- `60d2445cb docs: plan GY-N11 confidence ledger`
- `7fa1b5f27 docs: finalize Atlas DS20 cross-fence closure`
- `5ca5a9979 fix: bind deployment security to application identity`
- `811088d25 fix: preserve review authorization import boundary`
- `c33c4d450 fix: reattest deployment authority at consumption`
- `b3f11e587 merge: land GY-N13b — acquisition executor, honest typed_deeper_terminal, generic derivation engine`
- `290bb5e61 refactor(dashboard): wrap decision producers as quantities`
- `ac4290b3d docs: record N13b universality merge audit`
- `08018888a fix: attest deployment authority composition`
- `d725d19c0 fix: track formatted monotone authority guard`
- `67978371a style: format N13a decay evidence owner`
- `b9720bdb4 evidence: prove second derivation family data-only`
- `78ee33f94 fix: close deployment authorization bypasses`
- `2fe0fa006 fix: keep D6 carrier denominator row-exact`
- `1ec995fe1 test: prove live runtime and Rego parity`
- `3f773d426 fix: wire the canonical derivation owner into D6`
- `a1007951e evidence: freeze first-family derivation audit`
- `b6d8c54d0 docs: close Atlas DS20 cross-fence blockers`
- `fbb32cb54 refactor: make derivation families data-driven`
- `b3f99e37f refactor: preserve authorization import boundaries`
- `23a5d87ae test: prove probe authorization end to end`
- `7e1c6ed31 test: classify PostgreSQL provisioning blocks`
- `3479a206a test: add PostgreSQL authorization linearizability proofs`
- `74d9d92b3 fix: authenticate local runtime probes`
- `e57b241a0 test(dashboard): govern the status retirement inventory`
- `96aad76ca fix: make deployment security bundle factory-only`
- `0c324a911 fix: enforce deployment authorization composition`
- `5b788ff77 feat: bridge deployment authorization through Rego`
- `5127af28d feat(atlas-ui): project ratified DTCG token parity`
- `ebd6b8fc3 evidence: rederive N13a carrier decay census`
- `af7826a54 fix: distinguish carrier decay from transport evidence`
- `45f7733cd docs: amend Atlas DS20 cross-fence closure plan`
- `f61ca7069 docs: align N13b plan with typed terminal`
- `9b5e4f69c docs: close Atlas DS20 server authorization`
- `a4855dd96 fix: harden authorization seal and step-up timing`
- `72e20ff8b docs: close GY-N13b typed terminal`
- `a2c9ae8b0 chore(dashboard): retire dormant overlay primitives`
- `cb471dd09 build: project runtime permission vocabulary`
- `793315655 fix: close authorization review gaps`
- `6280e487f feat: freeze N13b acquisition executor contract`
- `e1931dc33 fix: preserve runtime architecture boundaries`
- `caa1ee6e3 feat(atlas-ui): migrate living overlay primitives`
- `383daaaa7 test: prove runtime authorization deny paths`
- `2b1db431d evidence: freeze N13b demanding-stage reentry`
- `cc1cd4f9f evidence: freeze derived acceptance proof`
- `44d0b650b feat: certify local real-terms acceptance fallback`
- `e9ec08c16 feat: expose structural provenance refusals`
- `76dd452dd evidence: freeze CPI carrier terminal`
- `868fa70bd feat: terminal-close authorized live characterization`
- `2dbf604e0 feat(atlas-ui): migrate form primitives`
- `42351fbef feat: authorize connector-acquired CPI deflator`
- `e32c63cf0 feat: require step-up for high-stakes mutations`
- `d234ffeef feat: derive real-terms acceptance inputs`
- `3438bf2e6 evidence: freeze D6 primary carrier terminal`
- `5e2d6dce1 feat: authorize D6 primary carrier probe`
- `018328d68 feat(atlas-ui): migrate foundation primitives`
- `d2854869e feat: derive certified D6 acquisition route`
- `43114cda1 feat: record World Bank carrier source mismatch`
- `a9243c5ae feat: authorize evidence-driven carrier metadata probe`
- `6c0f32cad feat: enforce mutating route authorization`
- `3a0216877 docs: plan GY-N13b evidence-driven resumption`
- `17639f540 docs: record GY-N13b evidence stop`
- `423dcd606 feat: preserve terminal acquisition evidence`
- `282a33169 fix: reopen terminal-closed acquisition journals`
- `7d6239707 feat: authorize a second exact live acquisition carrier`
- `ecf9bd449 fix: honor open live catalog temporal bounds`
- `353ef21b8 feat: expose one-shot live acquisition command`
- `6515134ac feat: authorize exact live acquisition carrier`
- `78f7820fd feat: derive canonical acquisition execution target`
- `ef1395082 feat: own runtime permission vocabulary`
- `f43173deb feat: derive missing acquisition field edges`
- `0568be335 docs: correct DS20 resource binding authority`
- `c9f3e3fc3 feat: certify content-addressed real-terms derivations`
- `fc33aac7e feat: execute one canonical live acquisition carrier`
- `d165fcc60 docs: plan Atlas DS20 server authorization`
- `e8da2d4c2 feat: persist live acquisition failure terminals`
- `61d354f62 docs: plan Atlas DS4 status grammar rebinding`
- `05e1a758f feat: resolve live harness authority from canonical receipts`
- `aef304bd1 feat: own canonical World Bank response projection`
- `bd4b6d5ac feat: emit bounded live-fetch waiting heartbeats`
- `c57cec1bb fix: bind live execution to transport trace`
- `491b608ea feat: derive live transport calls from journal evidence`
- `a026afdfc fix: provision external L5 acquisition authority`
- `4d9518239 fix: journal raw HTTP before response classification`
- `8a5314c71 fix: fail closed on unauthoritative local acquisition evidence`
- `5858dd829 feat: bind live acquisition evidence carriers`
- `ff7f0d438 feat: enforce journal-first live acquisition carriers`
- `fac755e2b feat: expose acquisition epochs through L1 catalog reads`
- `93bb89288 feat: admit acquisition epochs through canonical passports`
- `d5f83a26b chore: ignore pnpm store and apps/ build outputs`
- `71f438ad5 docs: Atlas plan — DS3 closed & merged; debt table extended`
- `e451cec56 merge: land Atlas DS3 — runtime producers & export infrastructure`
- `028ddde5d docs(atlas): close DS3 exact-head review`
- `7050786f2 fix(runtime): close DS3 exact-head review`
- `cdb99168f feat: consolidate acquisition evidence journal`
- `ade434ba0 feat: wire N7 catalog acquisition plans`
- `98962ca28 docs: plan GY-N13b acquisition executor`
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
