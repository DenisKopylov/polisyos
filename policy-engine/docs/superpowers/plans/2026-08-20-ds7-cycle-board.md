# DS7 Cycle Board Hero Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to execute this plan. Root is the only tracked-file
> writer and heavy-process launcher; research agents remain read-only.

**Goal:** Promote the existing governed `depth-n-cycle-board` projection into the sole
REVIEWER/EXPERT hero surface, while preserving producer-owned terminality, owner-recomputed
structural evidence, typed source absence, honest-empty movement, and byte-parity with its MACHINE
twin.

**Architecture:** Keep `ProjectionId.DEPTH_N_CYCLE_BOARD` as the owner identity. A runtime HTTP
compositor calls the existing raw DS3 projection adapter exactly once, joins only producer-signed
siblings and exact-bound `RunSummary.run_terminality`, and emits a versioned v2 packet from a static
authorized operation. The dashboard renders that packet at `/runs/cycle-board`; the old run-detail
renderers are strangled. Presentation formats facts but never recomputes lifecycle terminality,
evidence class, weakest links, route execution, movement, readiness, or global currentness.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2 strict DTOs, TypeScript, React, TanStack Query,
Vitest/Testing Library, Playwright, OpenAPI, generated TypeScript clients, Atlas governed-artifact
validators, pytest, Ruff, ESLint, and architecture guardrails.

**Spec:**
`docs/superpowers/specs/2026-08-20-ds7-cycle-board-design.md` at approved commit `4eec3fb48`.

## Global Constraints

- Work only in `/Users/deniskopylov/polisyos/.worktrees/atlas-ds7/policy-engine` on
  `codex/atlas-ds7-cycle-board`. Every mutating command first checks the absolute path, attached
  branch, and expected tree state. Never touch the root checkout or sibling worktrees.
- History is append-only: no rebase, force-push, reset, branch switch, or stash-as-storage. Do not
  push and do not merge this branch to `main`.
- TDD is binding: write one behavioral RED, run it and record the intended failure, implement the
  minimum owner-respecting mechanism, rerun GREEN, then run the focused regression before commit.
- Freeze source before reviews and run the expensive wave once. Review packages stay delta-only and
  at or below 28 KB. Cluster review rounds begin `0/2`; root buckets findings under P40 before any
  repair. A repeated class one level deeper widens the property mechanism.
- Root alone edits tracked files, merges, generates, opens register-lock windows, or launches heavy
  processes. Read-only agents report evidence and possible finding depth; they neither repair nor
  consume rounds.
- Serialize Playwright/visual, Storybook, fixed-port servers, and writers of the same
  `architecture/atlas_surfaces` artifact. Logic tests, lint, typecheck, build, architecture, and
  read-only censuses may run in parallel.
- Every suite longer than 60 seconds has a preset timeout and an `uptime` sample before and after.
  Completion, not success, admits a duration sample. A kill is a non-receipt and never justifies a
  larger ceiling during that run.
- Locale posture is D4-A1: author new copy in `en`, actively translate to `uk`, and leave `ru`
  `legacy_continuity_frozen`.
- The Atlas register family is held whole and only while writing its receipts and committing them.
  Announce exact open identities, read back the attached branch after commit, record close
  identities, and explicitly relinquish. Reacquire for any later generated-family write.
- Line 7 of the GY owner plan and line 7 of the Atlas master plan are out of scope. Register GAP5/6
  only inside the GY plan's registered-gaps block and assign no revision number.

## Pattern Pass

- Relevant patterns: P03 hidden richness, P04 status-lattice gaps, P05 projection authority leaks,
  P07 replay gaps, P08 time-role conflation, P10 semantic adequacy, P12 producer handshakes, P14
  evidence inflation, P15 LLM/projection laundering, P25 frontier-as-exhaustiveness, P27 parallel
  owners, P28 unstrangled legacy, P29 behavioral proof, P35 sampled denominators, P37 supplied gate
  predicates, P38 proxy gates, P40 ladder repair, and P41 inherited-red provenance.
- Existing anti-patterns to close: a governed global projection is rendered inside run detail; GAP4
  changes the OpenAPI without regenerating either stale-output-fail client; the complete production
  cycle-row denominator and per-row re-entry binding do not exist; historical environment-relative
  producer absence can be mistaken for artifact corruption; terminality can be tempted into local
  proxy derivation.
- Smallest correct pattern: one raw owner adapter, one server compositor, one authorized static
  operation, one generated hook, one human hero renderer, one packet-to-visible projection, one
  byte-identical export, and explicit typed absence for every missing owner chain.
- Starting capability states: existing projection `implemented_but_unbound_to_primary_surface`;
  lifecycle field `producer_complete_client_stale` until Cluster 0; production enumeration and
  per-row movement `absent/unallocated`; current readiness `artifact_missing`; hero and parity
  `surface_missing`/`semantic_test_missing`.
- Acceptance signal: corrupting an owner-recomputed evidence or weakest-link fact fails packet and
  DOM equality; status/timestamp mutations cannot change lifecycle truth; absent remains absent;
  adjacent rows cannot imply structural progress; only the hero fetches/renders; authorized DOM and
  downloaded JSON match the same typed packet.

## Task 0 — Commit the executable plan and merge current `main`

**Files:**

- Create: `docs/superpowers/plans/2026-08-20-ds7-cycle-board.md`
- Verify only: the five governed Atlas family artifacts named in Task 1

**Interfaces:** branch attachment, merge parent identities, and SHA-256 content identities.

- [ ] Commit this plan from the clean DS7 branch.
- [ ] Prove local `main` is exactly `c05475263`, the DS7 branch is attached, and the tree is clean.
- [ ] Merge `main` with `--no-ff`; do not rebase. Stop on an unexpected branch, pre-existing
  modification, or foreign conflict rather than switching, stashing, or cleaning.
- [ ] Read back both merge parents and confirm the approved spec remains byte-identical.
- [ ] Recompute SHA-256 identities for the register, generated report, status inventory, baseline
  manifest, and readiness ledger. Confirm the expected identities rather than inheriting them.
- [ ] Confirm the OpenAPI and both generated clients are byte-identical between `4456bb885` and
  merged `main`, while recording the intervening `temporal.py` change as upstream and untouched.

## Task 1 — Land GAP4 and both generated clients in one atomic Cluster 0 commit

**Files:**

- Merge source: `codex/gy-gap4-run-terminality` (15-file reviewed producer change)
- Regenerate: `schemas/runtime_api_v1.openapi.json`
- Regenerate: `packages/runtime-api-client/types.ts`
- Regenerate owner companions: `packages/runtime-api-client/runtimeApiClient.ts`
- Regenerate owner companions: `packages/runtime-api-client/runtimeApiClient.js`
- Regenerate owner companions: `packages/runtime-api-client/canonicalRuntimeApiClient.ts`
- Regenerate owner companions: `packages/runtime-api-client/canonicalRuntimeApiClient.js`
- Regenerate: `apps/runtime-dashboard/src/api/types.ts`
- Create: `release-fragments/unreleased/2026-08-20-ds7-gap4-run-terminality.toml`
- Re-anchor only when invalidated: `architecture/atlas_surfaces/frontend-disposition-register.json`
- Regenerate only when invalidated: `docs/reference/frontend/atlas-frontend-disposition-register.md`
- Re-anchor only when invalidated: `architecture/atlas_surfaces/status-retirement-inventory.json`
- Verify byte stability unless owner proves movement:
  `architecture/atlas_surfaces/frontend-baseline-debt-manifest.json`
- Verify byte stability unless owner proves movement:
  `architecture/atlas_surfaces/live-application-readiness-ledger.json`

**Interfaces:** `RunSummary.run_terminality`; OpenAPI schema; both generated TypeScript families;
generated client methods; structured release compatibility; structured Atlas reference identities.

- [ ] Bootstrap with `corepack pnpm install --frozen-lockfile`, recording the toolchain gate as a
  receipt only if it completes. Until then, every TypeScript scanner/generated-owner result is a
  non-receipt.
- [ ] Capture baseline bytes and parse both client families with the installed TypeScript runtime.
  Enumerate every exported symbol, normalized field shape, occurrence count, and governed anchor.
- [ ] Run the applicable generated-owner checks against the clean merged-main state. Record baseline
  diagnostics; do not treat an environmental/tooling failure as a finding.
- [ ] Merge GAP4 with `git merge --no-ff --no-commit codex/gy-gap4-run-terminality`. Do not create an
  intermediate merge commit.
- [ ] Regenerate OpenAPI with
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json`.
- [ ] Regenerate the package client with
  `corepack pnpm --filter @polisyos/runtime-api-client run generate`, accepting the complete declared
  output family rather than cherry-picking `types.ts`.
- [ ] Regenerate the dashboard family with
  `corepack pnpm --filter @polisyos/runtime-dashboard run generate:api`.
- [ ] Run the independent client-drift census. For each family publish total before/after symbols,
  pre-existing symbols, unique surviving symbols, unchanged/changed/removed/added symbols,
  unchanged/changed/removed/added fields by containing symbol, every governed anchor line and
  offset, and distinct unaffected/post-insertion offset sets.
- [ ] Stop before acquiring the Atlas lock if any pre-existing symbol/field changes or disappears,
  any symbol duplicates, or anchor movement is non-mechanical. Name this result
  `changed-or-removed`; reserve “semantic drift” for this stop class.
- [ ] Continue only when the enumeration proves `additive-and-declared`: every pre-existing export
  occurs once, all pre-existing normalized fields are unchanged, nothing is removed, and the only
  new producer surface is the intended lifecycle-terminal field/type with uniform offsets.
- [ ] Create the structured unreleased fragment. Declare compatibility for both changed generated
  client families, bind it to the drift receipt and focused tests, and leave release-wide version
  policy to the release owner.
- [ ] Announce the Atlas whole-family lock and read all five opening identities immediately before
  the first governed write. Do not hold the lock during bootstrap, merge preparation, generation,
  or drift proof.
- [ ] Re-anchor every invalidated structured identity surgically; never full-format governed JSON.
  Regenerate the Markdown report from its owner and run all register/status corruption probes.
- [ ] Verify baseline-manifest and readiness-ledger bytes remain identical unless a named owner
  mechanism proves an induced change; if one moves, re-anchor every dependent family identity in
  this same commit.
- [ ] Run focused GAP4 backend tests, runtime contract checks, both client typechecks/tests, release
  compatibility gates, and Atlas register/status checks. Record a completed failure as a finding or
  inherited diagnostic; record a kill as a non-receipt.
- [ ] Recheck path, branch, unresolved merge state, and the exact staged denominator. Commit the
  still-uncommitted GAP4 merge, complete generated families, compatibility fragment, and all receipts
  as the single Cluster 0 merge commit.
- [ ] Read the commit and both parents back from the attached branch; recompute all five closing
  identities; prove no required file remains modified or untracked.
- [ ] Explicitly relinquish the Atlas register lock so DS6 can proceed. Cluster 0 remains `0/2`
  unless root has bucketed a Blocking/Important mechanism finding.

## Task 2 — Prove the three inherited reds before board mechanism

**Files:**

- Record: `docs/superpowers/journals/2026-08-20-ds7-cycle-board.md`
- Verify: DS8 A4 print expectation and visual owner inputs
- Verify: DS5 run-deck governed image/size baseline and current render
- Verify: DS6-C11 component-parity owner inputs

**Interfaces:** P41 slice-base replay, complete input denominator, path intersection, exact red
identity, and completed timing receipt.

- [ ] On detached read-only materializations of slice base `4456bb885`, replay each exact owner
  command with its original bytes. Do not edit the DS7 tree and do not run contended suites together.
- [ ] Record exact commands, preset timeouts, uptime pairs for runs over 60 seconds, complete input
  sets, base results, and the intersection of DS7 changed paths with those input sets.
- [ ] Replay the same commands after Cluster 0. The expected state is DS8 A4 red with unchanged
  expectation; stable DS5 `1094x821` versus governed `1094x820`; and sole DS6-C11 parity red.
- [ ] Stop attribution if a red does not reproduce at the slice base or the complete input
  denominator intersects DS7 changes. Never report an inherited red green.
- [ ] Commit only the baseline-relative journal receipt.

## Task 3 — Register the two real producer capability gaps

**Files:**

- Modify only registered-gaps block:
  `docs/plans/active/layer3-slices/GY-engine-subordination.md`
- Update execution journal: `docs/superpowers/journals/2026-08-20-ds7-cycle-board.md`

**Interfaces:** `GY-GAP5 production_recursive_cycle_run_enumeration` and `GY-GAP6
acquisition_reentry_deeper_terminal_binding`.

- [ ] Add GY-GAP5 as `absent/unallocated`, routed to runtime/quality GY-N12 with deficits
  `artifact_missing + bridge_missing`, non-blocking recording, no second chronology, and the full
  reproduce/current-head/deletion/narrowing closure signal. State that recorder failure never changes
  cycle terminality.
- [ ] Add GY-GAP6 as `absent/unallocated`, routing acquisition/re-entry receipt production to
  GY-N13b and chronology composition to existing GY-N12, with exact row/content/deeper-terminal
  substitution negatives.
- [ ] State the measured owner-plan state without assigning a revision. Verify the diff is entirely
  inside the registered-gaps block and does not touch line 7.
- [ ] Commit the two disjoint registered gap rows and journal receipt.

## Task 4 — Freeze and land REDs by independently reviewable seam

**Frozen basis:**
`docs/superpowers/plans/2026-08-20-ds7-task4-red-closure-basis.md`

During RED, an on-basis test-strengthening finding is convergence and consumes
no mechanism round. Only a finding that changes the production design, or a
genuinely new property absent from the frozen basis, consumes the seam's `0/2`
budget. Each review request quotes this bucket before review begins.

### Task 4a — Composition and fact algebra REDs

**Files:**

- Modify: `tests/unit/runtime/http/test_governed_projection_service.py`
- Add: `tests/unit/runtime/http/test_cycle_board_projection_service.py`
- Add: `tests/unit/runtime/http/test_cycle_board_projection_fact_algebra.py`
- Add: `tests/unit/runtime/http/test_cycle_board_projection_fact_owners.py`

**Interfaces:** strict fact algebra; exact run binding; canonical `DesignProblem`;
owner-recomputed evidence/weakest links; exact 3+13 cohort; GAP5/GAP6; complete
source ledger; historical DS4 disposition.

- [x] Close every `4A-*` basis row, including the composed DesignProblem/route/DS4
  carries, complete per-source time fields, and behavioral N13b denial for row
  membership, known count, exhaustiveness, and movement.
- [x] Keep terminality proxy coverage generic over status, time, raw search,
  distribution, blocker, and acquisition classes; absence remains a branch with
  no value.
- [x] Run the focused 4a files and witness failure because the compositor is
  absent, not because a fixture/import is malformed.
- [x] Freeze, issue the 4a basis to reviewers, repair only on-basis convergence,
  rerun the focused RED witness, and commit the reviewed 4a REDs.

### Task 4b — Access and replay REDs

**Files:**

- Modify: `tests/unit/runtime/http/test_governed_projection_api.py`
- Add: `tests/unit/runtime/http/test_cycle_board_projection_access_replay.py`

**Interfaces:** one static route; direct `RUNS_REVIEW` gate; real unpinned v2;
same-observation raw bytes; complete v1/v2 tuples; typed service and HTTP
conflicts.

- [x] Close every `4B-*` basis row. Run the real unpinned v2 request before
  installing the raw-only frozen adapter; prove viewer denial leaves the raw
  adapter's call count unchanged.
- [x] Exercise authorized HTTP 409 translation for a wrong complete raw tuple
  and partial/mixed generation tuples in addition to service-level conflicts.
- [x] Run the focused 4b files and witness failure at the missing static
  operation/service, then freeze, issue the basis, review, and commit.

### Task 4c — Loading and parity boundary REDs

**Files:**

- Add: `tests/unit/runtime/http/test_cycle_board_projection_loading.py`
- Keep the rendered-DOM residual in the frozen closure-basis record until its
  real Task 9 capability exists.

**Interfaces:** raw-byte-bound N13b loader; schema/rule/producer validation;
typed optional-source failure; control-plane authority; DS8 typed absence;
declared `semantic_test_missing` DOM/MACHINE residual.

- [x] Close `4C-N13B-01` through `4C-DS8-04`, including raw UTF-8 hash equality,
  substituted/malformed owner refusal, and no-value absences.
- [x] Run the recorded complete 971-file dashboard-source two-census falsifier for `4C-DOM-05`;
  retain `semantic_test_missing` and its Task 9 mutation falsifier rather than
  fabricating a server DOM test.
- [x] Run the focused 4c file and witness failure at the missing loader/service,
  then freeze, issue the basis, review, and commit.

## Task 5 — Implement the minimal server compositor and static operation

**Files:**

- Modify: `src/polisyos/runtime/http/services/governed_projections.py`
- Add: `src/polisyos/runtime/http/services/cycle_board_projection.py`
- Modify exact projection route module containing the existing dynamic governed-projection export
- Modify: `src/polisyos/runtime/http/permissions.py` only if wiring reuses, without changing,
  `RuntimePermission.RUNS_REVIEW`
- Modify OpenAPI-facing DTO module identified by existing governed-projection DTO ownership

**Interfaces:** `CycleBoardProjectionService.get_unpinned_v2`, explicit pinned replay adapter,
`policyos.runtime.cycle_board_packet.v1`, `policyos.runtime.depth_n_cycle_board.v2`, ordered source
composition manifest, and projection/dependency hashes.

- [x] Define strict discriminated available/absent facts and `CycleBoardRow`/source/coverage/movement
  DTOs. Cost/VOI `None` becomes `not_established`, never zero.
- [x] Implement one internal raw call and compose only after it returns. Bind exact signed lifecycle
  facts; leave unbound rows absent. Never inspect status or timestamps for terminality.
- [x] Carry full source packet states and per-source `as_of`/freshness. Use transaction time only as
  `projection_observed_at`; emit no aggregate currentness.
- [x] Compose three capstones, thirteen fixture-only legacy cases, board-level GAP5, empty GAP6
  movement, realized DS4 `27/41/18/3`, and no fabricated future rows.
- [x] Add the static authorized route before the dynamic sibling with operation ID
  `get_depth_n_cycle_board_projection` and owner-appropriate collection binding.
- [ ] Rerun Task 4 focused tests to GREEN, then focused Ruff/type checks and architecture import
  guardrails. Commit the server mechanism.

## Task 6 — Regenerate the v2 API/client seam under a fresh short lock

**Files:** same generated families and governed receipts as Task 1.

**Interfaces:** distinct generated `getDepthNCycleBoardProjection`; packet/rule-version union;
legacy replay isolation.

- [ ] Regenerate OpenAPI and both complete client families with Task 1 owner commands.
- [ ] Re-run the full two-family symbol/field/anchor enumeration. Stop on changed/removed or
  non-mechanical drift before acquiring the lock.
- [ ] RED then GREEN the package-client test proving the distinct static method and version
  discriminator. RED then GREEN the dashboard hook contract rejecting v1 on the hero path.
- [ ] Announce and acquire the whole-family lock only for re-anchors, owner report generation,
  verification, commit read-back, and closing hashes; then explicitly relinquish.
- [ ] Commit the generated seam, compatibility fragment update if required, and all induced receipts
  atomically.

## Task 7 — Write dashboard REDs for the hero, strangle, authorization, and honest absence

**Files:**

- Add: `apps/runtime-dashboard/src/features/runs/routes/CycleBoardPage.test.tsx`
- Replace stale assertions in:
  `apps/runtime-dashboard/src/features/runs/components/RunExplainabilityPanel.governedProjection.test.tsx`
- Modify: `apps/runtime-dashboard/src/features/runs/routes/runDetailSurfaces.test.tsx`
- Modify: `apps/runtime-dashboard/src/features/runs/routes/RunsListPage.test.tsx`
- Modify exact route/permission registry tests identified by the complete consumer census

**Interfaces:** static `/runs/cycle-board`; permission-before-query mount; one production fetch/render
consumer; stable raw DOM slots; navigation-only run-detail link.

- [ ] RED: `runs.review` mounts the hero query; settled `runs.view`-only renders denied state and no
  query, board, or export link.
- [ ] RED: run detail neither fetches nor renders the projection; its permission-filtered link only
  navigates and labels the cohort global. Replace, do not retain, tests whose sole purpose was the old
  in-panel rendering.
- [ ] RED: absent lifecycle is visibly and structurally absent, never false/non-terminal/default;
  search terminal remains separate.
- [ ] RED: typed structural gaps retain their grounding/owner-lever/estimand identities and exact
  routes; adjacent counts cannot change presentation or movement.
- [ ] RED: producer environment absence renders the exact `invalid_source`/`artifact_missing` state,
  source-relative times, and limitation; no global fresh/current badge appears.
- [ ] RED: PUBLIC navigation/access stays absent before DS12; only REVIEWER/EXPERT audiences appear.
- [ ] RED: complete TS/TSX census expects exactly one production hook caller and renderer after the
  strangle. Run focused Vitest files and record intended failures. Commit RED tests.

## Task 8 — Implement the hero and strangle both existing renderers

**Files:**

- Add: `apps/runtime-dashboard/src/features/runs/routes/CycleBoardPage.tsx`
- Add: `apps/runtime-dashboard/src/features/runs/components/CycleBoard.tsx`
- Add: `apps/runtime-dashboard/src/features/runs/components/cycleBoardPresentation.ts`
- Modify: `apps/runtime-dashboard/src/features/runs/api/useDepthNCycleBoardProjection.ts`
- Modify static route, prefetch, permission, and surface-registry owners found by the route census
- Modify: `apps/runtime-dashboard/src/features/runs/routes/tabs/OverviewTab.tsx`
- Modify: `apps/runtime-dashboard/src/features/runs/components/RunExplainabilityPanel.tsx`
- Modify authored `en` and active `uk` locale resources; do not edit frozen `ru` copy

**Interfaces:** `packetToVisibleCycleBoard`; source/fact exhaustive issuers; refusal-with-path rows;
coverage and movement typed absences; DS8 drill-down links.

- [ ] Add the static route before `/runs/:runId`, permission boundary before data hook, route/prefetch
  manifest entry, and `permissionKey: "runs.review"` surface entry.
- [ ] Reuse the hook with the distinct generated static client method and accept only unpinned v2.
- [ ] Implement one pure packet-to-visible projection that formats but never derives owner facts.
  Expose stable raw typed data in DOM semantic regions next to localized labels.
- [ ] Render coverage/movement gaps first, the ordered cohorts, terminal facts, recomputed evidence,
  full weakest-link sequence, costed route and execution state, slices, DS8 link, readiness absence,
  public-safe explanation, source ledger, and realized `27/41/18/3` disposition.
- [ ] Remove the Overview hook call and governed projection prop/rendering from
  RunExplainabilityPanel. Retain only the scoped permission-filtered navigation link.
- [ ] Rerun Task 7 GREEN, dashboard typecheck, focused ESLint, architecture checks, and complete
  TS/TSX consumer census. Commit hero and strangle together.

## Task 9 — Add the MACHINE twin and rendered-DOM parity proof

**Files:**

- Add or modify: `apps/runtime-dashboard/src/features/runs/routes/CycleBoardPage.parity.test.tsx`
- Modify: `apps/runtime-dashboard/src/features/runs/components/cycleBoardPresentation.ts`
- Modify: `apps/runtime-dashboard/src/features/runs/routes/CycleBoardPage.tsx`

**Interfaces:** server packet bytes; `packetToVisibleCycleBoard`; raw typed DOM encoding; export
download bytes.

- [ ] Reuse the DS16 rendered-DOM decoding precedent. RED against the real page: decode every stable
  semantic region and compare the complete value to `packetToVisibleCycleBoard(packet)`.
- [ ] Include coverage gap, movement gap/empty denominator, DS4 disposition, all sources, cohorts,
  rows, both terminal facts, evidence, weakest links, routes, readiness, and explanations. Add
  dropped-row, duplicate-row, defaulted-absence, omitted-source, and fabricated-movement negatives.
- [ ] RED then GREEN an export assertion that downloaded bytes equal the exact request packet bytes;
  never reconstruct JSON from DOM/localized state.
- [ ] Run focused parity/Vitest and typecheck. Commit MACHINE parity.

## Task 10 — Freeze, review, run the verification wave once, and close

**Files:**

- Complete: `docs/superpowers/journals/2026-08-20-ds7-cycle-board.md`
- Add closure record in the Atlas DS7 plan/journal location identified by repository convention
- Update generated receipts only inside a newly announced short lock if the final wave proves an
  owner-induced change

**Interfaces:** frozen diff, <=28 KB review package, P40 buckets, measured suite timings, closure
claims, attached-branch read-back.

- [ ] Run pre-freeze focused tests and self-review against every approved spec invariant. Search for
  placeholders, status/timestamp terminality proxies, adjacent-count credit, invented readiness,
  PUBLIC exposure, duplicate projection owners, and stale in-panel fixtures.
- [ ] Freeze source and dispatch independent backend semantics, frontend custody/strangle,
  authorization/API, generated receipts, and DOM-parity reviews. Package only the changed delta and
  keep each package at or below 28 KB.
- [ ] Bucket every Blocking/Important finding before repair. New class consumes a round; same class
  one level deeper widens the mechanism; a proven non-behavioral static diagnostic consumes none.
  Run delta-only re-review after any repair.
- [ ] After all reviews are in, run logic suites, ESLint, typecheck, build, release/runtime contract,
  architecture, and Atlas governance in parallel where uncontended. Serialize Storybook,
  Playwright/visual, fixed-port, and same-artifact writers. Use preset timeouts and uptime pairs.
- [ ] Reconfirm the three inherited reds remain exactly red and no new baseline-relative diagnostic
  exists. Do not relabel a kill as a result.
- [ ] Record that DS7 renders producer values only for status-like/structural fields and renders
  refusals/typed gaps for policy substance; it renders no policy quantity/effect/welfare value and
  therefore does not satisfy DS16 re-entry.
- [ ] Record exact GAP5/GAP6 ownership and closure signals, honest-empty movement, environment-scoped
  5/7/1 debt discharge, one human renderer, v2/MACHINE parity, realized DS4 `27/41/18/3`, locale
  posture, and no PUBLIC gate.
- [ ] Commit closure, then read back HEAD, commit/file denominator, clean status, and branch
  attachment. Confirm no push and no merge to `main` occurred.
