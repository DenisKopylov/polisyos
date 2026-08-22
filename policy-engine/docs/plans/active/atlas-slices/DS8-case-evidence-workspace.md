---
plan_id: atlas-ds8-case-evidence-workspace
title: "DS8 - Case & Evidence Workspace"
type: slice-plan
status: awaiting_owner_approval_no_implementation
created: 2026-08-21
last_verified: 2026-08-21
stability: measured_review_ready_plan
slice: DS8
baseline_commit: 3d44989c63de564d026004781ae64d92031134ff
execution_base_commit: 3d44989c63de564d026004781ae64d92031134ff
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
identity_boundary: ../../../system-design-decisions/policyos-identity-and-custody-boundary.md
failure_register: ../../../reference/policy-design-case-failure-patterns.md
ds4_closure: ./DS4-status-grammar-rebinding-closure.md
ds6_plan: ./DS6-evidence-workflow.md
disposition_register: ../../../../architecture/atlas_surfaces/frontend-disposition-register.json
audiences: [REVIEWER, EXPERT, MACHINE]
backend_co_owner: team-runtime
feature_flags: none
review_cycles_used: 3_of_3
depends_on:
  - ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
  - ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
  - ../../../reference/policy-design-case-failure-patterns.md
  - ./DS4-status-grammar-rebinding-closure.md
  - ./DS6-evidence-workflow.md
---

# DS8 - Case & Evidence Workspace

## For agentic workers

This is an approval-gated implementation plan, not authorization to implement.
Branch `codex/atlas-ds8-planning` is attached at immutable base/merge-base
`3d44989c63de564d026004781ae64d92031134ff`; verify before writes/commits. Root
alone writes. No merge/push/rebase/stash storage, line-7 edit or revision bump.

After approval, work red-first with local `git`, explicit paths, `corepack pnpm`,
fixed ceilings and one serialized visual lane. A completed failure is a receipt;
a kill/nonreceipt is not. Acquire the register lock only in C07.

## Mission and boundary

DS8 ships a read-only run-anchored case workspace over content-bound artifacts:
DesignRecord/case packet, grounding/admission/promotion, stage trace, and
distinct blocker/limitation/objection/abstention objects. It reuses artifact and
evidence inspectors, closes bounded support-only DS4 rebinds, gives the new
case/report views MACHINE twins, and replaces the print proxy with a typed
paper projection.

LLM, local and frontend-signed material stays candidate state. Laws 3/4/6/7
require typed unknowns, weakest status, limits and complete closed-case pins.

## Canonical Closure Contract

DS8 closes only when every item below is true. No cluster defines a second
closure contract.

- [ ] Branch/base/path fence remains exact.
- [ ] `GET /api/v1/runs/{run_id}/case-inspection` resolves the authorized run's
      persisted closure, content-binds and strictly validates every source, and
      returns an available/unavailable union. Missing, invalid, unbound and
      cross-run sources never become empty green state.
- [ ] The packet carries refs/digests, schema/rule/projection versions,
      authority purpose, provenance, separate time roles, and producer-owned or
      typed-unavailable grounding/admission/promotion facts.
- [ ] Blockers, limitations, objections and abstentions remain distinct strict
      objects; every DesignRecord is resolved, bound and model-validated.
- [ ] One strict replay-query model and canonical href builder carry the complete
      unmixed tuple for closed requests and Cycle Board links; omitted, partial,
      cross-run and cross-generation tuples are typed 409 conflicts.
- [ ] `/runs/{runId}/case` and `/runs/{runId}/report` authorize before fetch,
      consume the case/paper packet without rederivation, and pass DOM parity.
- [ ] Both new DS8 views export their exact one-response bytes—no stringify,
      second request or reconstruction; C04's existing views are support-only.
- [ ] `RunSummary.run_terminality` has a production consumer preserving all
      three states; Cycle Board `lifecycle_terminality` is not substituted.
- [ ] DS1-N002/N003 and sibling falsifiers keep local causal drafts out of
      effect-authority slots and empty what-if arrays out of admissibility.
- [ ] All 207 opening TS/TSX paths and new DS8 paths have exactly one checked
      disposition. The eight named production paths land; all deferrals carry
      owner, capability label and exit signal. No family-complete claim is made.
- [ ] The complete run-detail paper-egress set is closed: `/report` is the sole
      report emitter; `/overview` cannot print a paper payload; poisoned local
      state, telemetry and controls enter neither DOM, PDF nor MACHINE bytes.
- [ ] The P38 full-unbounded-tree pixel-identity proxy is replaced by typed DOM,
      parsed A4 geometry, one bounded raster and a legitimate-growth test.
- [ ] After one bounded first derivation, two consecutive no-writer runs on one
      commit and one host/browser/font receipt are green; 724x2113 is never the
      replacement authority.
- [ ] Post-freeze OpenAPI/client regeneration passes GY-DEF20's two real
      family-level freshness predicates; composite deep-import red is preserved.
- [ ] DS6 receives the C13 receipt below; named standing reds stay owned.
- [ ] Focused tests, corruption probes, typecheck, ruff, architecture/link/diff
      checks pass or retain proven disjoint reds, then the branch is read back.

## Measured entry receipts

### Immutable base and fourth A4 cell

The attached worktree was clean at the pinned base; ports 6006/5173/8000 and
the visual-process census were empty at acquisition and release. This no-writer
command selected one test, zero retries, and fixed 90/240-second ceilings:

```bash
CI=1 PLAYWRIGHT_RETRIES=0 corepack pnpm exec playwright test \
  --config=playwright.visual.config.ts --project=chromium \
  --grep='run detail A4 print$' --timeout=90000
```

It completed exit 1 in 26.7 seconds with both-side uptime. No ceiling widened;
the expectation stayed byte-identical.

| tree | actual |
| --- | ---: |
| neither change | `770x13,269` |
| DS6 signed-target suppression only | `770x12,966` |
| DS7 strangle only | `770x12,949` |
| **both, immutable DS8 base** | **`770x12,646`** |

The fourth cell is measured, not `12,949 - 303`. Actual PNG:
`_build/apps/runtime-dashboard/test-results/runtime-dashboard.visual-r-24fdd-selines-run-detail-A4-print-chromium/run-detail-a4-print-actual.png`.
SHA-256 receipts: actual
`7d7ade4a6df9c850ea6f0e16bacc97174bc98918c74e2ee0c2279f8fb5aae059`;
trace `a61828b97a259d394e2ababb0e6c60e67d5d312ae1f6c52607a3cc3bf67da1b2`;
unchanged expected
`a920f6c95aead95c1126838d2eebd7ed1410fad10cf8f8e6f05d9b848f79217d`.

| receipt field | value |
| --- | --- |
| host | macOS 26.5.2 (25F84), Darwin 25.5.0, arm64 Apple M2 |
| toolchain | Node 22.22.2; pnpm 10.33.2; Playwright 1.59.1 |
| browser | Chromium 147.0.7727.15, Playwright chromium-1217 Chrome for Testing |
| fonts | `document.fonts.ready` completed; Manrope 5.2.8 weights 400-800 and IBM Plex Mono 5.2.7 weights 400/500 loaded from bundled WOFF2 files |

### Paper-semantics adjudication

**Ruling: a distinct typed paper projection, not filtered `RunDetailLayout`.**
Reuse `/runs/:runId/report`, with a server-owned case-packet payload. The
interactive overview is not a decision report.

Threshold, annotations, wallet and onboarding persist in scoped `localStorage`;
the adapter disclaims authority/revalidation and hashes only a frontend
candidate packet. Printing them launders interaction into fact. Cost: a paper
subprojection, report consumer, overview exclusion, PDF/parity tests—not a
local-note server.

Losers:

- as-is prints interactive chrome;
- the split launders browser-local values;
- whole-panel exclusion is safe but leaves an untyped filtered tree;
- a CSS allowlist lets a new sibling cross silently (P31/P37).

HUD and Operator Craft are actually siblings with separate reducers; excluding
HUD does not exclude the panel. That changes CSS cost, not the ruling.

### Governed A4 expectation

The retiring test compares every pixel of the full unbounded overview locator
with `maxDiffPixels: 100`; historical height is only one divergence. It cannot
distinguish legitimate admitted growth from regression and does not test A4
pagination (P38).

After DS8, the expectation is one composed gate:

1. typed print-DOM roster, zero controls and zero poisoned-local-state leakage;
2. Chromium `page.pdf({preferCSSPageSize: true})`, parsed to require every
   MediaBox/CropBox be A4 portrait within 0.5 point;
3. one bounded header/identity raster after font readiness;
4. typed admitted growth forcing `grown_page_count > base_page_count`, unchanged
   A4 geometry and complete DOM rows. Global page count is not pinned.

Use test-only `pdf-lib`; the Node lane has no parser and regex counting violates
P29. Retire the old PNG only after red-to-green semantic/PDF tests, then one
bounded writer derivation and two no-writer runs.

### Producer and seam census

Two independent complete walks agreed on 90 HTTP Python files, seven
PDC/DesignRecord lexical hits, 16 route files/95 decorators, and OpenAPI 93
operations/92 paths—but no case/
DesignRecord operation. Dashboard production has zero `/cases`/`DesignRecord`
hits; `run_terminality` appears only in generated types. Strict persistence has
no run-anchored resolver; the best-effort `None` projection is not authority.
Opening state is
`producer_missing + bridge_missing + consumer_missing + semantic_test_missing`;
canonical lookup is `artifact_missing` without a bound CAS artifact.

The Cycle Board seam is truthful but empty: `stage_trace_href` is an
`AbsentFact` (`not_established` for N10, `artifact_missing` for legacy rows), so
the UI renders no link. DS8 injects the narrow inspection resolver into Cycle
Board composition. Only a resolved packet yields an `AvailableFact` whose href
serializes every replay pin before `#stage-trace`; the pins also enter the board
composition hash. Unresolvable rows remain absent.

## Producer and packet design

Use one run-anchored endpoint; do not invent a global case-id index:

```text
GET /api/v1/runs/{run_id}/case-inspection?{CaseInspectionReplayPins}
GET /runs/{runId}/case
```

`CaseInspectionReplayPins` is one strict query model shared with a canonical
href builder. The service admits only known case, runtime-PDC-graph and
DesignRecord kinds from the authorized run closure. It loads manifests/exact
bytes, verifies identity/hash, validates the owner model and run/case/tenant
binding, and freezes predicate provenance. It never reruns a builder or uses
`None`.

`CaseInspectionResponse` is a strict discriminated union:

- `available`: identity/replay pins, DesignRecord, typed grounding/admission/
  promotion, stage trace, separate issue arrays, artifact/evidence links and a
  paper projection of owner-eligible facts;
- `artifact_missing`, `invalid_source`, or `not_established`: reason,
  `owner_route`, source refs/digests when known, and `may_not_use_for`.

Use 200 for available/typed unavailable, existing 403, 404
`case_inspection_run_not_found`, 409 `case_inspection_replay_pin_mismatch`, and
422 only for malformed syntax. Closed cases require case, graph and DesignRecord
ref/hash plus schema/rule version and projection hash; partial means conflict,
never “latest.”

C00 records a complete role map: artifact kind/schema, closure-edge role,
tenant/run/case binding, content verifier, and producer field for every status
and issue family. A source lacking one row can only produce typed unavailable.
The complete stable paper DTO and server projection land in C01, before ABI
freeze; C06 is DTO-neutral and only consumes/tests it.

Freeze additive DTO/route ABI tests, then run the registered chain once:

```text
FastAPI route + strict DTO
 -> schemas/runtime_api_v1.openapi.json
 -> five packages/runtime-api-client outputs
 -> apps/runtime-dashboard/src/api/types.ts
```

Commit the release fragment and generated companions atomically. Then run
GY-DEF20's real scratch generators and require byte equality for both client
families; the deep-import composite remains a separate red receipt.

## Strangle denominator and scope decision

The supplied `207 files / 28,853 lines` row combines two different sets. At
the immutable base, independent `git ls-tree` and physical filesystem walkers,
with `wc -l` and an independent record counter, agree on:

| set | files | physical lines |
| --- | ---: | ---: |
| tracked `.ts + .tsx` | 207 | 38,544 |
| `.tsx` only | 140 | 28,853 |
| production `.ts + .tsx` | 145 | 26,502 |
| tests | 57 | 11,575 |
| stories | 5 | 467 |
| auxiliary CSS + two OWNER files | 3 | 200 |
| all physical files | 210 | 38,744 |

Thus 28,853 is TSX-only lines, not lines across the 207-file population.
“Lines” here means physical newline records, not occurrences or code-only LOC.

DS4 realized **27 package / 41 rebind / 18 use-as-is / 3 retire = 89**—a
component, not DS8-file, denominator. The current register intersection is 42
objects/138 recursive occurrences/50 unique paths; six overlap root and
supplemental sets, so it does not prove 207-path coverage.

DS8 is not a 38,544-line rewrite. Its opening-base production mechanism scope
is exactly eight of 145 paths:

1. `features/runs/route.tsx`
2. `features/runs/routes/RunsListPage.tsx`
3. `features/runs/routes/RunDetailLayout.tsx`
4. `features/runs/routes/RunReportPage.tsx`
5. `features/artifacts/components/ArtifactViewerRegistry.tsx`
6. `features/artifacts/components/DecisionCardView.tsx`
7. `features/evidence/components/FreshnessBraidPanel.tsx`
8. `features/evidence/components/DataIntelligencePanel.tsx`

The complete declarative map is set-based: those eight are `in_scope`; all 57
tests are `verification_companion`; all five stories are `retained`; new paths
are `new_in_slice`. Every other production path is assigned exactly once:

| cohort | production | in DS8 | deferred |
| --- | ---: | ---: | ---: |
| runs | 86 | 4 | 82 |
| artifacts | 48 | 2 | 46 |
| evidence | 11 | 2 | 9 |
| **total** | **145** | **8** | **137** |

Every deferred set-difference path is owned by `team-design`, labeled
`surface_out_of_scope`, and exits only when an approved named successor slice
moves its row. C07 materializes the map; a generic walk fails missing,
duplicate, stale or nonexistent rows. C04 only
rebinds the four named components as support for existing Artifact Inspector/
Evidence Fabric views: no route, field or DS8 view claim, hence no new MACHINE
obligation. Public packet authority is DS12; mutations DS9; Lex DS10; Clerk
DS14; scientific depth DS16. A family-complete claim waits for all 137 rows to
move under approved successor slices.

## Red-first semantic tests

Backend names:

- `test_case_inspection_resolves_bound_case_graph_and_design_record`
- `test_case_inspection_returns_artifact_missing_without_defaulting_stage_facts`
- `test_case_inspection_rejects_unresolved_digest_or_cross_run_source`
- `test_case_inspection_rejects_candidate_unverified_promotion_as_authority`
- `test_case_inspection_requires_complete_closed_case_replay_tuple`
- `test_case_inspection_rejects_one_field_and_cross_generation_pin_mutations`
- `test_case_inspection_preserves_distinct_negative_object_kinds`
- `test_cycle_board_stage_trace_href_is_available_only_for_resolved_packet`
- `test_cycle_board_stage_trace_href_serializes_complete_packet_pins`
- `test_openapi_exposes_strict_case_inspection_union`

Frontend/browser names:

- `CaseWorkspacePage > authorizes before query and renders exact stage facts`
- `CaseWorkspacePage > closed case mutation fails instead of loading latest`
- `CaseWorkspacePage parity > decoded DOM equals the fetched packet`
- `CaseWorkspacePage MACHINE > download bytes equal the one response bytes`
- `RunsListPage > renders all three run_terminality states without substitution`
- `DS1-N002 > local and blind-cast causal drafts cannot fill effect authority`
- `DS1-N003 > empty issue arrays cannot establish scenario admissibility`
- `RunReportPage > poisoned operator local state cannot enter paper projection`
- `RunReportPage > print DOM contains zero interactive controls or telemetry`
- `RunDetailLayout > overview print emits no report payload or local state`
- `RunReportPage > eligible ordinary URL prints while signed target stays hidden`
- `RunReportPage > no eligible URL is valid and prints no synthetic link`
- `RunReportPage parity > paper DOM preserves packet status time and provenance`
- `RunReportPage MACHINE > download bytes equal the one response bytes`
- `RunReportPage PDF > every page has A4 geometry and admitted growth adds pages`
- `RunReportPage visual > bounded identity region matches first derivation`
- `DS8 disposition coverage > opening and new feature paths are total and unique`

The P15 base replay completed under a fixed 120-second ceiling: two files and
12 tests passed in 3.058 seconds. `CausalTab.test.tsx` rejects local/blind-cast
draft authority; `ScenarioValidationPanel.test.tsx` rejects empty-array
admissibility. Constructor-only and marker-string tests do not count. One test loads
real CAS bytes, corrupts content while preserving shape/refs, and proves both
the producer and consumer fail closed.

## Clustered execution plan

Caps count production mechanism paths; tests, plan/journal, release/generated
companions, register records and forced snapshot are P39 companions outside.
Each cluster gets at most one implementation plus one widening round; C02/C05
get one, C00/C08 none: total 12 mechanism rounds. On a class's second finding,
P40 requires widening or a bounded residual plus falsifier—no third patch.

| cluster | work and acceptance | mechanism cap | rounds |
| --- | --- | ---: | ---: |
| C00 | Bind the approved-plan base; commit red tests and artifact-role preflight without mechanism changes. | 0 | 0 |
| C01 | Stable DTO including paper, resolver/service/route, pin-query/href builder, and resolver-backed Cycle Board bridge. Real-CAS and mutation negatives pass. | 7 | 2 |
| C02 | Freeze OpenAPI, classify ABI, regenerate schema and both client families, then prove GY-DEF20 family freshness. No hand edits to generated output. | 0 | 1 |
| C03 | Authorized Case Workspace, stage-trace anchor, typed unavailable state, exact-byte MACHINE export and real-DOM parity. | 8 | 2 |
| C04 | Support-only rebind of four artifact/evidence components; no route, new field or shipped-view claim. | 4 | 2 |
| C05 | Consume `RunSummary.run_terminality`; replay and strengthen the already-green causal/what-if P15 falsifiers without source churn unless a falsifier is red. | 1 | 1 |
| C06 | Consume frozen paper DTO; close overview/report/MACHINE egress, PDF geometry/growth and bounded derivation. No ABI change. | 5 | 2 |
| C07 | Under the register lock, extend the existing schema/checker and atomically enumerate T0, new paths, deferrals and closure receipts; run corruption probes. | 2 | 2 |
| C08 | Freeze source, run the closeout wave once, take two consecutive no-update visual receipts, release the lane, hand C13 to DS6, and read back the branch. | 0 | 0 |

Only the visual lane and register lock serialize, never together. Generate after
C01 freeze and before C03 imports; stale types cannot become a workaround.

## File Map

| role | planned home |
| --- | --- |
| public strict DTOs | `src/polisyos/runtime/http/services/case_inspection_contracts.py` |
| resolver/projection producer | `src/polisyos/runtime/http/services/case_inspection.py` |
| HTTP route and auth binding | `src/polisyos/runtime/http/routes/case_inspection.py`, `runtime/http/app.py` |
| Cycle Board producer bridge | `src/polisyos/runtime/http/services/cycle_board_projection.py`, `runtime/http/routes/governed_projections.py` |
| backend tests | `tests/unit/runtime/http/test_case_inspection_service.py`, `test_case_inspection_api.py`, Cycle Board tests |
| OpenAPI/client companions | `schemas/runtime_api_v1.openapi.json`, five runtime-client outputs, dashboard `src/api/types.ts`, release fragment |
| dashboard packet/bytes | `features/runs/api/useCaseInspection.ts`, `domain/caseInspectionPresentation.ts`, exact-byte export helper |
| case view | `features/runs/routes/CaseWorkspacePage.tsx`, `features/runs/route.tsx` |
| paper view | `features/runs/routes/RunReportPage.tsx`, `RunDetailLayout.tsx`, `src/styles/print.css` |
| artifact/evidence rebind | the four named support-only component paths |
| terminality | `features/runs/routes/RunsListPage.tsx` |
| frontend tests | colocated page/domain tests, `runtime-dashboard.visual.spec.ts`, DOM twin helper |
| A4 parser/dependency | runtime-dashboard `package.json`, `pnpm-lock.yaml`, test-only PDF helper |
| strangle coverage | existing frontend disposition schema/register/checker/test family |
| work record | this plan plus one DS8 implementation journal created only after approval |

If C01 cannot resolve a real bound DesignRecord from the run artifact closure,
stop with `artifact_missing`; do not add a builder, global index, mock authority
or unrelated orchestration persistence path without owner re-cut.

## Issue Codes

| code | meaning / required result |
| --- | --- |
| `DS8-P01-PRODUCER-MISSING` | no case inspection producer; closed only by C01 e2e chain |
| `DS8-P32-SOURCE-UNVERIFIED` | ref present without resolved content/manifests; fail closed |
| `DS8-CASE-ARTIFACT-MISSING` | required case/DesignRecord source absent; typed unavailable |
| `DS8-CASE-PIN-INVALID` | replay tuple partial, mixed or mismatched; typed 409 |
| `DS8-STAGE-TRACE-UNAVAILABLE` | no validated packet target; retain AbsentFact |
| `DS8-NEGATIVE-KIND-COLLAPSED` | blocker/limitation/objection/abstention conflated; reject packet |
| `DS8-MACHINE-BYTE-DRIFT` | export differs from fetched bytes or triggers second request; fail |
| `DS8-RUN-TERMINALITY-UNCONSUMED` | named producer still has zero dashboard consumers; fail C05 |
| `DS8-P15-AUTHORITY-LEAK` | causal draft or local what-if state fills authority; fail |
| `DS8-PAPER-LEAK` | local state, control or telemetry enters paper; fail |
| `DS8-PAPER-EGRESS-BYPASS` | overview emits report bytes or bypasses `/report`; fail |
| `DS8-A4-EXPECTATION-INVALID` | geometry fails or growth is judged by full height; fail |
| `DS8-STRANGLE-COVERAGE-DRIFT` | denominator row missing/duplicate/stale/unowned; fail |
| `DS8-GENERATED-FRESHNESS` | either GY-DEF20 client family differs from generator bytes; fail |

## DS6 C13 testable handoff

DS8 hands DS6 one immutable commit and a receipt bundle. C13 may transition
only if this conjunction is independently reproduced over the complete
`/overview` browser-print, `/report` PDF/print and MACHINE egress set:

```text
released typed paper projection
AND /report is the sole report emitter and /overview emits no paper payload
AND complete live print-DOM control census == 0 across every egress
AND poisoned local-state sentinel occurrences == 0
AND signed public-decision target pseudo-content occurrences == 0
AND case_with_admitted_evidence_href preserves its exact content-bound URL
AND case_without_eligible_href remains valid with zero synthetic URL content
AND every parsed PDF page is A4 portrait within 0.5 pt
AND admitted-growth PDF page_count > base page_count
AND bounded first-derivation screenshot comparison is GREEN twice,
    consecutively, no writer, same commit/host/browser/font inputs
```

The census walks every rendered egress tree for `button`, `input`, `select`,
`textarea`, `[role=slider]` and editable content—not source markers. No-update
runs are separate completions, not retries. Record selected count, exit,
elapsed/ceiling, page geometry/count, snapshot/artifact/trace hashes and uptime;
release the lane after each. First red suppresses second; C14 stays DS6-owned.

P37: decisive predicates are `recomputed` from packet bytes, live trees, parsed
PDF and comparator; host/browser/font only coordinate receipts. The last three
registered labels cannot green C13.

## Pattern pass and capability state

| patterns | opening risk | smallest correct pattern / acceptance |
| --- | --- | --- |
| P01/P02/P12 | route-shaped contract without bridge | CAS -> resolver -> packet -> route -> two consumers -> e2e negative |
| P04/P05/P15 | local state or projection labels mint authority | typed unavailable/weakest status; localStorage poison and candidate-promotion negatives |
| P07/P08 | “latest” closed case or mixed time roles | complete replay tuple; valid/recorded/generated times remain separate |
| P10/P29/P31/P32 | form tests, per-panel CSS, trust-by-ref | corrupt valid-looking bytes; one resolved seam and complete egress invariant |
| P35/P36 | hybrid 207/28,853 denominator and stale prose premise | independent complete walkers; source-correct HUD/panel sibling finding |
| P37/P38 | author-declared field eligibility and unbounded raster proxy | eligibility from typed source; DOM + parsed PDF + bounded raster + growth mutation |
| P39/P40/P41 | caps count records; repeated instance repair; inherited red guessed | companion accounting; two-round breaker; exact pre-slice-base replay/disjointness |

At approval, case remains `producer_missing`, `bridge_missing`,
`consumer_missing` and `semantic_test_missing`; canonical record may be
`artifact_missing`. Paper is
`implemented_but_not_orchestrated` and `verification_missing`. Neither is
complete before the Closure Contract passes.

## Commit Sequence

1. `docs(atlas): bind DS8 measured slice plan` — this planning pass only.
2. `test(ds8): pin case inspection and replay negatives` — C00 red receipts.
3. `feat(runtime): produce run-bound case inspection packets` — C01.
4. `chore(api): regenerate DS8 inspection clients` — C02, atomic generated set
   plus compatibility release fragment.
5. `feat(atlas): land case workspace and MACHINE parity` — C03.
6. `refactor(atlas): rebind DS8 artifact and evidence support components` — C04.
7. `fix(atlas): consume run terminality and preserve P15 negatives` — C05.
8. `fix(atlas): derive governed A4 paper projection` — C06; snapshot companion
   lands only after semantic/PDF green.
9. `chore(atlas): close DS8 strangle coverage` — C07 under the family lock.
10. `docs(atlas): record DS8 verification and DS6 C13 handoff` — C08 after
    readback and two no-update receipts.

Do not split a mechanism to fit a cap. An unlisted production path requires a
stopped, owner-approved cap change before editing.

## Non-Negotiables

- Before approval: no production code, writer, regeneration or register lock.
- No public/NL/mutation/local-note/public-packet authority lands in DS8.
- No label, localStorage, ref presence, exit, regex page count or pixel dimension
  becomes authority; unknown states never default green/negative.
- No CSS adjustment chases the DS5 run-deck fractional clip or any unrelated
  snapshot.
- The deep-import red, 13 diagnostics, DS6-C11 pin and DS5 delta keep their owners.
- The old 724x2113 expectation remains byte-unmodified in this pass. During
  approved implementation it is retired only as part of the behavioral A4
  replacement, never rewritten to the current 12,646-pixel screen height.
- `run_terminality` is claimed and consumed by DS8; no other inherited debt is
  silently absorbed.
- No merge or push to `main`; hand back an attached review branch and exact
  receipts.

## Explicit non-closure

DS8 does **not** close the full 207-file legacy-family migration, public case
publication, frontend-signed public decisions, approval authority, local
reviewer-note persistence, global case indexing, canonical DesignRecord
creation for runs that never emitted one, Lex/Composer/Clerk authority repair,
or DS16 scientific-depth production. It does not close DS6 itself: it supplies
the C13 conjuncts; DS6 independently verifies them and owns C14. DS9 remains
gated until this plan's actual implementation satisfies the Closure Contract.
