---
plan_id: atlas-ds15-acquisition-routes
title: "DS15 - Acquisition Routes & Data-Pool Growth Surfaces"
type: slice-plan
status: proposed
created: 2026-08-27
last_verified: 2026-08-27
stability: measured_plan
slice: DS15
baseline_commit: 2525da7306d329ae28fa394690e1c39133eb0d55
branch: codex/ds15-acquisition-routes-plan
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
gy_plan: ../layer3-slices/GY-engine-subordination.md
identity_boundary: ../../../system-design-decisions/policyos-identity-and-custody-boundary.md
failure_register: ../../../reference/policy-design-case-failure-patterns.md
disposition_register: ../../../../architecture/atlas_surfaces/frontend-disposition-register.json
audiences: [REVIEWER, EXPERT, MACHINE]
frontend_owner: team-design
runtime_owner: team-runtime-quality
fabric_owner: team-fabric
depends_on:
  - commit: 74f26ca2d
    slice: DS7
  - commit: 719d7a35a
    slice: GY-N13a
  - commit: b3f11e587
    slice: GY-N13b
waits_for:
  - slice: DS11
    path_prefixes:
      - apps/runtime-dashboard/
      - architecture/atlas_surfaces/
---

# DS15 - Acquisition Routes & Data-Pool Growth Surfaces

## For agentic workers

This is an approval-gated implementation plan, not authorization to implement.
It was prepared in attached worktree branch
`codex/ds15-acquisition-routes-plan` from immutable base
`2525da7306d329ae28fa394690e1c39133eb0d55`. At plan entry,
`git rev-parse --show-prefix` returned `policy-engine/`, `git status -sb`
named the attached branch, and the tree was clean. The three gate commits
`74f26ca2d`, `719d7a35a`, and `b3f11e587` were each independently proved to be
ancestors of `HEAD` with `git merge-base --is-ancestor` exit `0`.

Before every path coordinate, run `git rev-parse --show-prefix`; before every
commit, re-read `git status -sb` and `git symbolic-ref -q HEAD`. Never push,
merge, rebase, reset, or use a stash as storage. Commit each clean cluster
boundary. Use `corepack pnpm`, never bare `pnpm`. Do not run a writer,
regenerator, register lock, or visual snapshot command before its named cluster
and serialized-resource receipt.

The user-supplied DS11 fence is authoritative as a scheduling boundary: DS11
holds the complete prefixes `apps/runtime-dashboard/` and
`architecture/atlas_surfaces/`. The supplied number `63` is not used as a gate
predicate: it could not be independently reproduced as DS11's current path
denominator and also occurs as an older axe-fixture audit count. C00 must derive
the live DS11 path set twice. The wait ends only when DS11's landing commit is an
ancestor of the execution branch and both complete-prefix derivations agree;
matching the number 63 alone cannot release the fence.

For every timed command, capture an `uptime` receipt immediately before and
after and preserve `/usr/bin/time -p`'s `real`, `user`, and `sys` fields. Read
the command exit code into a DS15-specific variable before any pipe; evidence
commands should avoid pipes entirely. A killed or interrupted run is a
non-receipt, not a duration sample. Every set-level count below has two
independent derivations; disagreement stops the dependent cluster and is
reported rather than averaged.

## Mission and binding reality

DS15 is the surface dual of GY-N13. Its distinctive product motion is:

> blocked case -> typed reason -> costed path -> accountable approval -> raw
> acquisition -> passport or quarantine -> one overlay epoch or no growth ->
> the same case re-enters or reaches an honestly deeper terminal.

That is the meaning of **refusal-with-a-path becomes refusal-with-a-button**.
The motion is continuous on the glass, but its facts remain orthogonal. An
approval does not imply an execution; a fetch does not imply admission; an
admitted passport does not imply an active epoch; an active epoch does not imply
case advancement.

Revision 3's reality note is binding. N13a proves two different sets:

- the three current capstone routes are structural `not_a_data_gap` routes; and
- the separate growth-backlog denominator is 15 `binding_gap` residuals, but
  that owner type says only that a binding is absent; it does not classify the
  gap as data-shaped or structural.

The first set never receives an acquisition button. The second set does not
receive one merely because it says `binding_gap`. Across those 15, only
`government.balance` is independently re-established as data-shaped; 14 remain
`gap_class=not_established`, and none is structurally classified. Current
producer, rights, planner, mandate, decision, and execution bindings must also
resolve.

N13b selected `government.balance` for its demanding-stage re-entry because the
L1 availability owner reported zero canonical observations. It is one of the
15 N13a residuals, at recorded interim rank 8, and is not a revived capstone
hypothesis. Its actual execution did **not** grow the world: availability stayed
`0 -> 0`, all live evidence was quarantined or terminal, no overlay epoch was
activated, and re-entry reached
`deeper_terminal_primary_carrier_characterization_failed`. The surface must
show that exact terminal. N13b also selected World Bank CPI
`FP.CPI.TOTL` for a separate real-terms acceptance case; that selection was
data-shaped but is not the case-re-entry/world-growth trace and must not be
spliced into it.

The positive “world grew” claim therefore has no current production receipt and
is not merely waiting for verification. The production-safe N13b execution
port, PA2 signed producers and institutional semantic-epoch qualification owner
are currently missing. DS15 consumes those as typed external inputs; it does
not appoint them or modify N13b's write path. It renders N13b's honest negative
history and **does not close** until those producers exist and a fresh,
currently eligible data-shaped route produces an admitted passport, an active
owner epoch, a positive admitted delta, and an exact same-case re-entry receipt
after accountable approval. A fixture may prove the DS15 consumer/mechanism; it
may not be presented as that production receipt. Until the external producers
land, the slice is `producer_missing + verification_missing` and partial or
blocked, however polished the surface is.

Opening capability states are:

| capability | measured opening state |
| --- | --- |
| N13a census and live-journal read projections | existing `producer + artifact + HTTP + partial Cycle Board consumer/surface + owner negative tests`; DS15's detailed scorecard/backlog/liveness consumer, surface and e2e semantics remain missing |
| recurring carrier liveness | typed persisted artifact consumed by N13b; `bridge_missing + surface_missing` for DS15 |
| actionable cost basis | current planner rates/default fallback are unversioned candidate behavior with no actionable owner ref; `producer_missing` until C01's planner-owned versioned schedule and no-fallback cost record are present in the verified compiled-run closure |
| persisted N13b audit history | 43 registered files include raw terminal evidence, aggregate quarantine facts and a re-entry trace, but no persisted `AdmissionPassport` instance, acquired snapshot or overlay epoch; one existing in-process loader validates the executor contract's global signal, while HTTP exposes only its source-manifest identity and not the signal value; the detailed family/per-row bridge, consumer and surface semantics remain missing |
| in-process passport/overlay capability | existing recomputed passport and overlay owner, with zero current admitted observations and zero epochs; `implemented_but_not_orchestrated + surface_missing` for DS15 |
| live acquisition command | N13b executor/passport/overlay/quarantine logic exists in process, but its only live function has no production caller, is World-Bank/local-filesystem-only, opens a fresh unguarded CAS from raw paths and lacks tenant context; the safe runtime producer handshake is `producer_missing`, then `implemented_but_not_orchestrated + surface_missing` |
| PA2 production dispatch | gateway behavior exists but production composition and signed delegation/admission producers do not; guarded-store integration is missing; `producer_missing + implemented_but_not_orchestrated` |
| semantic-epoch qualification | current adapter/consumer use explicitly unallocated policy authority; institutional owner is `absent/unallocated`, so production admission is `producer_missing` |
| exact per-row acquisition-to-re-entry movement | `absent/unallocated` in the current Cycle Board (`GY-GAP6`); global N13b status cannot substitute |
| successful current world-growth demonstration | `producer_missing + verification_missing`; the safe N13b execution port, signed PA2 inputs and institutional qualification owner are absent, while admitted-observation and active-epoch denominators are both zero |
| INT-R2 `GapAcquisitionCase` union | `absent/unallocated`; DS15 renders current typed refusals and does not invent the union |

## Canonical closure contract

DS15 closes only when every applicable item has a committed-branch receipt.
There is no second closure contract.

- [ ] **CC01** Attached branch, exact base, three gate ancestries, prefix,
      clean-tree predicate, complete path fences, and red witnesses are read
      before every cluster commit.
- [ ] **CC02** The N13a three-output and N13b 43-output families, their logical
      payloads, and their HTTP/contract/in-process partition are derived twice
      and any disagreement is resolved before design changes.
- [ ] **CC03** The 15 residuals are re-derived as `1 data-shaped / 0
      structural / 14 shape not_established`: `binding_gap` alone proves none
      of those classes. The separate capstone denominator remains `3 structural
      / 0 data-shaped`; the two sets cannot be joined by route ID or visual
      proximity.
- [ ] **CC04** One strict acquisition-surface contract carries authority
      purpose, source/content hashes, rule/schema versions, source time,
      observed time, audience, and typed absence for every fact.
- [ ] **CC05** Structural capstone routes render their owner witness and missing
      link with `action_eligibility=not_applicable`; adding catalog rows or a
      client-authored `live_fetchable` field cannot create a button.
- [ ] **CC06** The 15-row board is labelled “interim priority ranking,” carries
      `ranking_only_not_voi`, and never calls its score or order VOI. Numeric VOI
      is available only with a resolved owner decision/ranking reference and
      expected-value/cost inputs.
- [ ] **CC07** Route detail shows typed requirement -> costed plan -> eligible
      and ineligible strategy -> VOI or typed absence -> independent lifecycle
      facets. Cost is a gate predicate: absent, default-zero, internally
      inconsistent or unverified cost basis is visible and blocks decision
      request/execution. VOI may remain typed absent under
      `ranking_only_not_voi` and is never zero-filled.
- [ ] **CC08** The connector scorecard shows all 12 families, the 18 actual live
      network probes inside the 144 journal records, 124 metric resolutions
      (`95 + 20 + 9`), liveness state, tier decay, and current carrier mismatch.
- [ ] **CC09** N13b's historical execution renders 5 attempts, 2 raw responses,
      5 quarantined/terminal outcomes, 0 admissions, 0 epochs, `no_growth`, and
      the deeper terminal without converting it into a success animation.
- [ ] **CC10** An operational route is derived only from a tenant/cell/run/job-
      bound completed `natural_language_run` control-job closure, its exact
      content-verified `runtime.compiled_recursive_generation_cycle` artifact,
      `AcquisitionPlannerReport`, and content-bound costed-plan/basis inputs; a
      Core `RunManifest` or repository N13b artifact cannot substitute for that
      current producer closure.
- [ ] **CC11** Acquisition approval reuses DS9's existing
      `agent_action_authority` PA2 arm and `HumanDecisionRecord`; DS15 adds no
      acquisition-specific decision source kind and no institutional
      appointment producer.
- [ ] **CC12** Decision preparation and execution use existing
      `RuntimePermission.EVIDENCE_ACQUIRE`,
      `StepUpClass.ACQUISITION_APPROVAL`, DS9 human-decision step-up, exact
      resource binding, live re-resolution, and an idempotent sealed effect.
- [ ] **CC13** The effect consumes N13b's existing
      executor -> recomputed `AdmissionPassport` ->
      `CatalogAcquisitionOverlay`/Fabric quarantine chain through an
      owner-supplied tenant-bound `AcquisitionExecutionPort` over the same
      guarded CAS/journal context. Raw `journal_path`/`cas_root` invocation is
      refused. No second journal, quarantine store, overlay table, passport,
      epoch allocator, or world write path exists.
- [ ] **CC14** A fetched response without a complete recomputed passport is
      quarantined; an admitted passport without matching active overlay and
      production receipts cannot emit world growth.
- [ ] **CC15** `world_growth=grew` requires a matching active overlay epoch and
      positive admitted-observation delta. `reentry=advanced` or
      `deeper_terminal` additionally requires the same run, case/design problem,
      requirement gap, execution receipt, and post-epoch re-entry trace.
- [ ] **CC16** Historical selection, expired rule/epoch, changed planner hash,
      changed availability, changed rights, or changed mandate returns
      `revalidation_required` or another typed negative and cannot be revived by
      resubmitting stale selectors.
- [ ] **CC17** REVIEWER/EXPERT HTTP packets and MACHINE exports use one captured
      response byte sequence; the dashboard does no authority recomputation,
      status synthesis, re-ranking, or cross-packet identity guessing.
- [ ] **CC18** Case Workspace displays blocked reason, cost, review/approval,
      execution, passport/quarantine, growth/no-growth, and re-entry as one
      ordered motion while preserving the independent facets.
- [ ] **CC19** Offline and queued acquisition approval/execution are rejected;
      no local storage can create authority, currentness, a passport, or an
      optimistic world-growth state.
- [ ] **CC20** OpenAPI, the five runtime-client files, and dashboard API types are
      regenerated atomically and reproduced byte-for-byte from two clean scratch
      outputs.
- [ ] **CC21** No held DS11 path is touched before its landing ancestry and
      complete-prefix path census agree; backend clusters can land first, but the
      generated family waits because it includes one dashboard file.
- [ ] **CC22** Every cluster's named red-first behavioral falsifier fails for the
      intended missing property, then passes without weakening its mutation
      probe or laundering fixture identity.
- [ ] **CC23** Slice-owned visual, responsive, keyboard, screen-reader, focus,
      and rendered-DOM/MACHINE parity receipts cover structural refusal,
      ranking-only backlog, quarantine/no-growth, and an admitted/re-entry test
      mechanism.
- [ ] **CC24** A fresh non-fixture route, selected from a current tenant/run-bound
      planner only after it is independently re-established as data-shaped,
      visibly completes blocked reason -> cost -> PA2/DS9 approval -> execution
      -> admitted passport -> active overlay epoch -> positive admitted delta ->
      exact same-case re-entry. The receipt must also resolve the external
      production N13b port, signed delegation/admission producers and
      institutional qualification owner. Neither the historical
      `government.balance` ID, a fixture, nor a resurrected capstone hypothesis
      can satisfy this item.
- [ ] **CC25** Freeze -> review -> one expensive verification wave -> register
      transition -> committed-branch readback proves the full capability chain,
      including CC24. An absent positive live receipt blocks DS15 closure; it is
      not an acceptable closed-state non-closure.

## Measured entry census

### Output families and payloads

Two derivations agree on the physical generated sets:

- N13a: generated-family `outputs` length `3`, and all three named paths exist.
- N13b: generated-family `outputs` length `43`; the lifecycle manifest also
  reports 43 registrations and its path set is identical. It partitions as 22
  CAS blob/manifest files + 1 raw journal + 20 top-level typed artifacts. The
  lifecycle manifest reports 41 content-bound and 2 writer-managed outputs.

The N13b execution journal carries a smaller superseded lifecycle note. DS15
cites the current owner manifest and records that historical/current
disagreement without carrying the obsolete counters into the slice census.

| owner output | actual emission | current reachability | DS15 use |
| --- | --- | --- | --- |
| N13a census | 12 `family_scorecards`; 124 `metric_resolutions`; 3 `route_evidence`; 15 `growth_backlog`; 15 reverse residuals; 7 read-only sample `FetchPlan`s with 0 execute/preview calls | HTTP through `GET /api/v1/exports/governed-projections/n13a-acquisition-census` | strict server projection for scorecard, metric map, structural routes and ranking-only backlog |
| N13a journal | 12 family receipts; 144 selected-record rows; 18 actual network calls (12 World Bank + 6 CKAN) | HTTP through `.../n13a-live-probe-journal` | liveness evidence and tier-decay detail; 144 is not relabelled as 144 live probes |
| N13a recurring carrier liveness | World Bank `GC.BAL.CASH.CD`; data `no_data_for_scope`; metadata source 11; `carrier_current_source_profile_mismatch`; missing `source_selector:11` | typed artifact, no HTTP projection ID; consumed by N13b in process | add governed read projection; show deeper connector-contract/config gap, never a fetchable success |
| N13b generated family | 43 files; executor contract, raw journal/CAS, authority provision/registry, selections, live receipts, re-entry trace, derivation artifacts, lifecycle manifest and harness evidence | no member has a direct HTTP route | narrow, typed audit-history projection; do not expose raw CAS bodies by default |
| N13b global movement signal | `typed_deeper_terminal`, derived from the executor contract | validated by the existing in-process loader; the Cycle Board source DTO exposes only manifest identity/availability/hash, drops the value, and therefore does not make the status HTTP-reachable | project it as global history in DS15; never bind it to a row or describe the current source-identity exposure as a status surface |
| N13b row movement | exact acquisition receipt/date -> same DesignProblem/cycle re-entry -> deeper terminal | explicitly denied by the current Cycle Board (`per_row_movement`, `row_enumeration`, `exhaustiveness`) | operational DS15 receipts must produce this binding; current global signal cannot fill it |
| canonical planner | strict hash-bound inline `AcquisitionPlannerReport`, strategy rows and optional expected cost/VOI/rank/owner/next action | nested HTTP today under `acquisition_economics` in `GET .../depth-n-cycle-board`, with existing Cycle Board service/dashboard consumption; optional facts may be absent and there is no dedicated route/detail endpoint | extend the existing partial consumer; resolve the exact report plus DS15's separate cost-basis record only from the completed control job's content-verified compiled-run closure |
| canonical executor/passport | live raw journal/CAS, measured candidate, recomputed `AdmissionPassport`, semantic-epoch admission | in process; no HTTP endpoint | sealed effect; project status/evidence, never accept caller-authored status |
| Data Forge overlay | pending/active epochs, passport snapshots, native membership and semantic/production receipts | in process; no HTTP endpoint | add read-only owner projection; do not change admission/activation methods |
| Fabric quarantine | append-only record/payload load, deterministic list/report/reprocess | in process; no acquisition-specific HTTP endpoint | filter/project canonical acquisition records; no DS15 ledger |

The reachability partition was independently derived from (a) a complete AST
walk of every runtime route decorator, classified by HTTP verb, WebSocket or
non-route kind before comparison; and (b) the emitted OpenAPI path/enum set
plus `ProjectionId`.
Both expose exactly the two N13a projection IDs, neither a liveness nor N13b
projection ID, and no passport/overlay/quarantine/re-entry operation. The
legacy `POST /api/v1/control/data/ingest` exists outside that string census, but
directly invokes generic ingestion and does not consume a DS9-class decision
record or N13b passport/overlay admission. It is not the DS15 action seam.

The emitted set also contains the existing `depth-n-cycle-board` projection,
whose nested `acquisition_economics` is a partial planner read surface. It is
counted as nested HTTP/consumer reachability, not as an acquisition-route
operation and not as proof of cost when its optional owner fields are absent.

That direct-route partition is not a claim of zero consumption. The existing
`CycleBoardProjectionService` resolves both N13a governed projections, uses the
census to build capstone missing-link/acquisition facts, and the current Cycle
Board renders those partial facts. DS15 extends this existing consumer seam for
the complete connector scorecard, ranking-only backlog and liveness detail; it
does not describe the already-rendered subset as `consumer_missing`.

### Independent count receipts

| set-level claim | derivation A | derivation B | result |
| --- | --- | --- | ---: |
| N13a output family | generated-family TOML `outputs` path set | generated-artifacts owner table's complete path set plus existence/readback of each named artifact | 3 |
| connector families | census `family_scorecards` length | journal `family_receipts` length and catalog identity | 12 |
| actual N13a live probes | raw journal-row scan counting network-call receipts and grouping their connector family: World Bank 12 + CKAN 6 | independent sum of the 12 scorecards' `network_call_count` fields | 18 |
| journal records | journal `records` length | sum of the 12 scorecards' selected-probe counts | 144 |
| metric resolutions | `metric_resolutions` length | status partition `95 resolves_exact + 20 resolves_via_alignment + 9 unresolved` | 124 |
| N13a sample FetchPlans | `fetch_plan_generation.plans` and `sample_rows` equal path/row denominators, with execution-fence counters read separately | independent `sample_binding.projected_item_count`/expected catalog-resolution counter plus the forbidden-owner preview/execute counters | 7 plans, 0 preview, 0 execute |
| N13a residuals | `growth_backlog` length and reverse-residual length, both all `binding_gap` | N13b local-lift denominator and row length, both all `binding_gap` | 15 |
| backlog authority/method | complete generated `growth_backlog` scan over `authority_boundary` and `ranking_method` | canonical N13a `derive_growth_backlog` recomputation from the full reverse-residual input, content-bound again by N13b's `census_growth_backlog_projection_sha256` | 15/15 `ranking_only_not_voi` + `interim_binding_confidence_x_route_demand` |
| capstone routes | census route-evidence length, all `not_a_data_gap` | N13b capstone route count/row length, all `not_a_data_gap`, laundered count 0 | 3 |
| N13b outputs | generated TOML output-list length | lifecycle registration count and equal path set | 43 |
| N13b physical roles | classify the generated TOML path set by CAS blob/manifest suffix, raw journal path and top-level artifact path | walk the actual generated tree under the declared roots and pair each CAS digest's blob/manifest before counting the journal and remaining files | 22 CAS + 1 journal + 20 top-level |
| N13b lifecycle bindings | committed lifecycle manifest recomputation fields and registration-status partition | run `derive_lifecycle_manifest(POLICY_ENGINE_ROOT)` over actual bytes: 41 hashes/sizes verify and the executor contract plus lifecycle manifest are the only two self-referential writer-managed rows | 41 content-bound + 2 writer-managed |
| N13b live attempts/responses/terminals | complete raw-journal JSONL scan by attempt ID, raw-response receipt and terminal receipt | executor-contract quarantine counters/failure-code partition plus owner behavioral test | 5 attempts/terminals, 2 raw responses, 0 admitted |
| historical overlay epochs | executor-contract `world_growth` epoch/event/admitted-observation fields | independently persisted re-entry trace `overlay_state` existence/epoch/registration/admitted-observation fields and world-growth event count | 0 epochs, 0 events, 0 admitted observations |

The structural/data split is denominator-qualified and refuses to infer shape
from `binding_gap`:

| denominator | structural | data-shaped | shape not established |
| --- | ---: | ---: | ---: |
| 15 N13a `binding_gap` residuals | 0 | 1 | 14 |
| 3 capstone route-evidence rows | 3 | 0 | 0 |

For the residual denominator, derivation A walks the complete 15-row N13a
backlog and resolves owner gap-shape evidence for every row; only
`government.balance` joins to a data requirement, snapshot-release gap and zero
L1 availability. Derivation B starts from N13b's complete preserved 15-row
local-lift denominator and independently joins its exact re-entry selection/
trace; it finds the same one row, while the other 14 preserve `binding_gap` but
have no data/structural classification. The capstone `3/0/0` result comes
independently from N13a route evidence and N13b's capstone projection.

### N13b selection and why it is honest

The world-growth/re-entry route is
`requirement-gap:data_requirement:l1-variable-availability:82412ae921974345`
for `government.balance`. Two independent artifacts establish its shape:

1. the re-entry trace records `requirement_family=data_requirement`,
   `gap_type=data_snapshot_release`, missing
   `canonical_variable_observations:government.balance`, L1 status
   `unavailable`, and observation count 0; and
2. the executor contract finds exactly one matching N13a backlog row, rank 8,
   `gap_kind=binding_gap`, while listing the separate structural capstone IDs
   `education`, `first_vertical`, and `unseen`.

Execution then discovered a deeper truth: the selected USD carrier
`GC.BAL.CASH.CD` belongs to World Bank source 11 (Africa Development
Indicators), not the catalog-declared WDI profile. The current terminal is a
connector source-profile/configuration gap, not a request to keep fetching the
same stale route. The historical route is rendered with no active button. A
future button requires a freshly resolved data-shaped route and current
producer/rights/mandate evidence.

The separate CPI acceptance selection (`inflation`, `FP.CPI.TOTL`) is shown in
audit detail only. It demonstrates an honest live selection and quarantine, not
the `government.balance` case re-entry and not world growth.

### Producer gates before executable C02

Four current producer gaps are binding, not implementation trivia:

1. `execute_live_catalog_acquisition` has no production caller, accepts raw
   `journal_path`/`cas_root`, constructs a fresh unguarded `FileSystemCAS`
   without tenant context, and supports only `worldbank.wdi`. DS15 will consume
   only an N13b-owner production `AcquisitionExecutionPort` that proves the same
   guarded CAS/journal/tenant/run and reuses the existing passport/overlay/
   quarantine logic. The port's owner lands outside this slice; DS15 never wraps
   the raw-path function with a second scratch/write path.
2. `AgentActionAuthorityGateway` is composed only in tests today. Signed
   `DelegationContract` and `AgentActionAdmissionBundle` producers are absent in
   production, and its exact-`FileSystemCAS` constructor does not accept the
   runtime's guarded artifact-store boundary. DS15 may generalize that consumer
   to the verified ArtifactStore protocol and compose a narrow control-owned
   gateway, but it does not manufacture the signed institutional inputs.
3. the semantic-epoch qualification adapter and consumer explicitly use
   unallocated policy authority, so production admission inevitably refuses
   with `policy_admission_missing`. The institutional qualification appointment
   remains out of scope; DS15 consumes its signed typed evidence if another
   owner supplies it.
4. the current N7 requirement-gap route carries no independent numeric cost
   basis: optional `voi_expected_cost` is absent when N7 calls the planner
   without a VOI report, while the planner's existing hard-coded rates and
   unknown-gap default are unversioned and have no actionable owner ref. C01
   establishes `PlannerAcquisitionCostSchedule@1.0` as a deterministic planning
   estimate produced by the existing planner module, not an external
   institutional appointment. Its named
   `load_planner_acquisition_cost_schedule` loader returns a strict schedule
   with owner, authority purpose `planning_estimate`, currency, effective time,
   rule version, exact named gap-basis rows, rates and content hash. The new
   cost producer accepts only an exact schedule row; the legacy unknown-gap
   fallback remains historical/candidate behavior and can never enable review
   or execution. This is the sole producer gap DS15 owns, and the estimate is
   not represented as a purchase commitment or observed invoice.

C01 may land while the first three remain absent. C02 may build and verify
fail-closed consumers, receipt persistence and a fake-port behavioral harness,
but an executable control and CC24 remain blocked until all external refs
resolve. Their absence renders `producer_missing`; it never authorizes an
institutional appointment, a raw local-filesystem call, or a fixture badge
removal.

## Design rulings

### 1. Facets, not one optimistic status

The canonical packet keeps these independent strict facets:

| facet | values / rule |
| --- | --- |
| `gap_class` | `data_gap`, `structural_gap`, or typed unavailable; only the owner artifact sets it |
| `plan` | requirement, planner status, eligible/ineligible strategies, next action, cost and VOI facts with refs |
| `cost_basis` | `established`, `missing`, `invalid`, `default_zero`, or `revalidation_required`; only `established` can enable review/execute after server recomputation from content-bound basis/rate inputs; an explicit owner-produced zero may be established, an absent/default zero may not |
| `action_eligibility` | `not_applicable`, `producer_missing`, `revalidation_required`, `blocked`, `decision_required`, `executable` |
| `decision_gate` | the existing DS9 precedence: invalid -> artifact missing -> producer missing -> revalidation -> blocked -> available |
| `execution_phase` | coarse surface state `not_started`, `requested`, `executing`, or `terminal`; every non-initial value carries an exact receipt/event ref |
| `receipt_phase` / `recovery_state` | owner detail is `requested`, `executing_acquisition`, `world_committed_reentry_pending`, `reentering`, or `terminal`, plus `none`, `receipt_recovery_required`, or `reentry_recovery_required`; the server maps requested -> requested, all nonterminal execution/recovery detail -> executing, and terminal -> terminal |
| `admission` | `not_reached`, `not_established`, passport `quarantined`, `admitted`, or `admitted_degraded`; no UI derivation |
| `quarantine` | `none`, `raw_terminal`, or `passport_refused`, with exact Fabric refs; this records ledger/effect disposition separately from the passport's admission status |
| `world_growth` | `not_established`, `no_growth`, or `grew`; `grew` requires active epoch + positive admitted delta |
| `reentry` | `not_established`, `pending`, `advanced`, or `deeper_terminal`; exact same-case binding required |

Mixed outcomes are first-class: N13b is `data_gap + terminal + raw_terminal +
admission:not_reached + no_growth + deeper_terminal`; an
`admitted_degraded + grew + reentry_pending` case keeps its limitation and does
not render complete. A recomputed refused passport is
`admission:quarantined + quarantine:passport_refused`; raw evidence that never
reached passporting remains `admission:not_reached`. Approval changes only the
decision facet.

Each predicate is frozen at admission under P37; a declaration or field
presence cannot upgrade it:

| gate predicate | admitted label | decisive proof / fail-closed state |
| --- | --- | --- |
| current data-gap class | `independently_reconciled` | current compiled requirement/gap/L1 owner facts agree; otherwise `not_established` |
| cost schedule applicability and total | `recomputed` | exact versioned schedule row, record hash and server line-item recomputation agree; otherwise `not_established` |
| current route/run closure | `independently_reconciled` | tenant/cell/run/job, completed progress, diagnostic event and compiled CAS ref agree; otherwise `not_established` |
| accountable human approval | `independently_reconciled` | DS9 content/signature/step-up admission succeeds; raw `institutionally_supplied` input alone remains ineligible |
| PA2 delegation/admission | `independently_reconciled` | gateway resolves and admits current signed inputs; caller assertions or absent producers are `not_established` |
| passport disposition | `recomputed` | N13b owner recomputes every decisive check; marker/status presence is `not_established` |
| active world epoch | `independently_reconciled` | pending, production and active overlay owner receipts bind one epoch; otherwise `not_established` |
| positive admitted delta | `recomputed` | owner before/after membership over the active epoch is positive; otherwise `no_growth`/`not_established` |
| same-case re-entry | `independently_reconciled` | prior case/problem/gap and active overlay receipts match the post-epoch trace; otherwise `not_established` |
| DS11 fence release | `recomputed` | landing ancestry plus two complete-prefix censuses agree; supplied `63` remains `not_established` as a gate |

### 2. Structural routes never wear data-acquisition clothing

Until INT-R2 supplies the real `GapAcquisitionCase` union, DS15 projects N13a's
existing `route_class`, `witness_kind`, and `missing_link`. It may present
`estimand_binding_refusal` and owner/grounding-relation missing links distinctly,
but it does not mint legal, capacity, mandate, or human-decision subtypes absent
from the owner. Structural routes show their own sufficiency owner and an
unavailable acquisition action.

The controlling falsifier is:

> mutate a structural capstone route to carry available catalog rows,
> fetchability, cost, or a client-authored data-gap label while retaining its
> owner `not_a_data_gap` witness; server action eligibility and the rendered
> button must remain `not_applicable`.

This catches the attractive false demo: a convincing acquisition loop over a
gap that was never data-shaped.

### 3. Ranking is not VOI

All 15 N13a backlog rows carry `ranking_only_not_voi` and the interim method
`interim_binding_confidence_x_route_demand`. The board title is **Interim
priority ranking**. It shows the method, owner boundary, raw rank and reason,
and states “VOI not established.” It does not use “highest value,” currency,
expected benefit, or VOI colors.

The N13b D2 source-growth row likewise has `voi_numeric_support=false` and no
VOI ranking ref. A route's VOI facet becomes available only when the canonical
planner supplies a content-resolved `voi_decision_ref`/`voi_ranking_ref`,
expected value, expected cost, rule version, and source time. A UI sort override
is local view state only, carries a visible `local_order_override` badge, is
included in exported presentation metadata, and never changes server rank.

### 4. One growing world, one write path

The write spine remains:

```text
raw journal/CAS
  -> measured semantic candidate
  -> prepared semantic epoch
  -> recomputed AdmissionPassport
  -> CatalogAcquisitionOverlay pending admission
  -> admitted-boundary production evidence
  -> activate that same overlay epoch
  -> post-epoch case re-entry
```

Refused passports go only to Fabric's existing quarantine owner. DS15 adds a
read projection and an orchestration receipt; it adds no store. Phase 6 O1/O3
deployment updates later land as a second provenance class in this same overlay
world. No source edit is planned beneath `src/polisyos/fabric/world/` or to
`src/polisyos/runtime/quality/data_state_substrate.py`. If execution proves an
edit to either held unbound-writes path is necessary, C02 stops and sequences
after that lane; it may not widen silently.

### 5. History cannot authorize a current action

N13a/N13b repository artifacts are governed audit inputs whose promotion target
explicitly excludes observation, engine, connector-promotion and publication
authority. The global export can render them. The action route cannot consume
them as current authority.

Operational eligibility resolves one tenant/cell/run/job-bound completed
`natural_language_run` from `ControlPlaneStore`. Its progress
`compiled_recursive_generation_cycle_ref`, capability-manifest ref and the
terminal runtime diagnostic event must agree on job/run and artifact refs. The
loader verifies the guarded CAS sidecar/schema/bytes as
`CompiledRecursiveGenerationCycleRun`, then resolves the exact original
DesignProblem, content-bound `AcquisitionPlannerReport`, cost schedule/record,
current availability, producer route, rights/trust provision and rule/epoch.
Neither `RunIndexService` nor `load_bound_terminal_manifest` owns this path: no
Core `RunManifest` is created for the current natural-language GenerationCycle
job. Missing/ambiguous job or ref binding is `producer_missing`; a changed
hash/time is `revalidation_required`. No route is revived because its
historical ID matches.

The closure demonstration is selected only from that freshly resolved set. It
is not pinned in this plan to `government.balance`, CPI, a backlog rank, or any
other historical identifier. The selected route must start with a current
data-shaped block on one real case, expose its owner-produced cost, pass the
same admission chain the product will use, and return that exact case after the
active epoch. If the fresh set has no eligible route, or every honest attempt
ends in quarantine/no-growth, DS15 reports that result and stays partial or
blocked; the executor may not loosen admission or revive a stale hypothesis to
obtain a green demonstration.

## Target producer, HTTP and approval chain

### HTTP surface

```text
GET  /api/v1/exports/governed-projections/acquisition-growth
GET  /api/v1/runs/{run_id}/acquisition-routes
GET  /api/v1/runs/{run_id}/acquisition-routes/{route_id}
POST /api/v1/runs/{run_id}/acquisition-routes/{route_id}/decision-request
POST /api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute
```

`acquisition-growth` is a new `ProjectionId` on the existing governed-projection
route, not a parallel export endpoint or thin alias. The projection is
REVIEWER/EXPERT/MACHINE only and carries N13a scorecard, liveness, metric
resolution, structural routes, ranking-only backlog, and N13b audit history. It
is not PUBLIC. The four new run-bound operations expose only routes from the
verified run artifact closure. Detail includes one ordered event timeline plus
the independent facets and exact replay pins.

Caller-authored decision-request/execute fields are limited to the current
route projection hash, planner report hash, replay pins, idempotency key, and
the existing human-decision record/ref selector. Callers cannot submit gap
class, cost or cost basis, VOI, action eligibility, decision status, passport status,
rejection codes, epoch, growth, or re-entry outcome.
The source control-job ID, completed-progress ref, diagnostic-event ref and
compiled-run ref are server-owned response/replay pins; a caller cannot select
or replace them in either POST.

GET uses 200 for typed unavailable states; replay-pin mismatch uses 409.
Decision request returns 201 only after the PA2 refusal/request artifact and
audit event are durably read back. Execute returns 202 only after the allowed
PA2 decision, control job, requested phase receipt and route/action head are
durable and read back. It never returns a synchronous terminal 201. Currentness/
eligibility conflicts are 409, malformed caller DTO is 422, auth remains
401/403, and CAS/audit/custody non-receipt is 503.

### Accountable button sequence

1. Detail GET freshly resolves the current route. Structural or historical-only
   rows expose no decision-request control. A data-shaped row also remains
   blocked unless the owner costed-plan artifact resolves, its basis/rate inputs
   and rule/schema identity are content-bound, and the displayed total is
   server-recomputed from its line items. Missing or unverified cost is not
   converted to zero.
2. “Review acquisition” POST constructs the exact operation/invocation/intent
   for action kind `runtime.evidence.acquisition.execute`, runs the existing PA2
   gateway without an effect, and persists the refused decision plus signed
   `HumanDecisionRequest`.
3. The dashboard uses the existing DS9 gate/evidence/decision endpoints with
   `source_kind=agent_action_authority`. Mandate, five rights, evidence exposure,
   accountability, dissent, and human-decision step-up remain DS9-owned.
4. After a current `approve` record, execute POST re-resolves the route and DS9
   record, requires `EVIDENCE_ACQUIRE` plus acquisition step-up, and calls a new
   gateway-owned deferred-effect reservation seam. That seam applies the same
   authority checks as `dispatch_agent_external_action`, persists the exact
   allowed `PersistedAgentActionDecision` and reservation receipt, but invokes
   no effect. Only after decision/ref, requested phase, action head and control
   job all read back may the endpoint return 202.
5. The generic control worker handler uses a new gateway-owned public durable
   loader to resolve and content-bind that decision ref, then passes the
   owner-supplied N13b production port as the exact callback to the existing
   `execute_bound_effect`. No route or worker reimplements private PA2 checks.
   The production port must reconcile/idempotently resume by the decision
   digest, so a crash cannot turn a retry into a second external effect.
   Immutable phase receipts bind route,
   planner/cost, DS9 record, raw terminal, passport/quarantine, overlay receipt,
   original case/design problem and re-entry; the terminal loop receipt is
   written only after the terminal fact exists.
6. `useAcquisitionRoutes` polls the acquisition detail endpoint while the
   server-owned action head is non-terminal, even for an otherwise finished
   run, and stops at terminal. The UI advances only as reconciled owner receipts
   arrive; it never inserts an optimistic epoch or movement row.

The legacy generic ingestion endpoint is unchanged and is not the DS15 button.
Production approval and promotion approval are also distinct and unchanged.

### Loop-receipt persistence and readback

The acquisition sink uses no unnamed substrate and does not overload the
human-decision sink. `control/run_lifecycle.py` adds a narrow
`AcquisitionRouteLoopAuthoritySink` to `ControlPlaneService`, backed by the same
guarded runtime `ArtifactStore`, `RuntimeDiagnosticEventLog` and
`ControlPlaneStore`. It writes strict immutable
`AcquisitionRoutePhaseReceipt@1.0` and terminal
`AcquisitionRouteLoopReceipt@1.0` payloads through
`write_runtime_authority_artifact`, with artifact kinds
`runtime_quality.acquisition_route_phase_receipt` and
`runtime_quality.acquisition_route_loop_receipt`, and event types
`polisyos.runtime.acquisition.route_phase.v1` and
`polisyos.runtime.acquisition.route_loop.v1`.

The existing `ControlPlaneStore` adds only a durable action-head pointer keyed
by tenant/cell/run/source-job/route/action generation. It stores CAS ref/hash, durable
event ID, coarse execution phase, detailed receipt phase, recovery state, job
ID and predecessor head; it stores no passport, observation or world data. The
sink advances the head only after
`reconcile_authority_ref`, exact CAS/manifest/schema readback and strict-model
validation. The detail loader in `acquisition_surface_projection.py` resolves
that exact head and predecessor chain, repeats reconciliation and strict
validation for every payload, then supplies the ordered timeline. It never
scans CAS or infers a head from immutable run roots. No in-memory return value
is a read receipt.

Crash recovery cannot repeat acquisition speculatively. If the authority CAS
and its diagnostic-event CAS exist but the durable event append was interrupted,
the service validates the manifest-linked diagnostic event, appends it
idempotently to the same `RuntimeDiagnosticEventLog`, and reconciles again. If
an active overlay/effect receipt exists but the re-entry/terminal CAS does not,
the action head becomes `reentry_recovery_required`; recovery resumes only
re-entry from that exact active receipt and matching overlay path, then builds
the deterministic terminal receipt from owner refs. It never fetches,
re-passports or reactivates. Any ambiguous/missing predecessor is
`receipt_recovery_required`. Crash mutations at every boundary must prove that
a 201/202 and a visible movement row require CAS, event, head and readback
agreement.

## Red-first behavioral falsifiers

| id | red property and mutation | required result |
| --- | --- | --- |
| `DS15-STRUCTURAL-NOT-DATA` | add available rows, cost and a forged `live_fetchable` label to a `not_a_data_gap` capstone route | server remains `not_applicable`; no button; rows visibly do not advance relation/estimand/owner gap |
| `DS15-BINDING-NOT-DATA` | retain `binding_gap` and ranking fields while removing the owner requirement-family/gap-type/L1 evidence | `gap_class=not_established`; no cost/action/button is inferred |
| `DS15-NO-STALE-REVIVAL` | retain historical N13b IDs while changing/removing current run, planner hash, L1 availability or rule epoch | `revalidation_required`/`producer_missing`; no decision request or execute effect |
| `DS15-RANKING-NOT-VOI` | rename/interpolate interim rank as VOI or reorder rows client-side without override metadata | contract/UI/parity test fails |
| `DS15-COST-BASIS` | retain an expected-cost field while removing/changing its named schedule row, basis ref, rates, rule/hash provenance or line-item equality; leave the legacy unknown-gap fallback present and also try caller zero/default | cost becomes typed unavailable/invalid and decision request/execute stay blocked; the legacy fallback never establishes actionability |
| `DS15-AUTHORITY-PRODUCERS` | keep approval markers while removing signed delegation/admission or institutional qualification evidence | route remains `producer_missing`; no allowed job or admission |
| `DS15-DEFERRED-PA2` | persist an allowed-looking marker but remove/tamper the durable decision, cross-bind its tenant/run/source-job/route/effect, or invoke the port without gateway load + `execute_bound_effect` | no external effect; job fails closed before the port and the action head records no executing receipt |
| `DS15-EXECUTION-PORT` | offer raw journal/CAS paths, a wrong connector, unguarded store, tenantless port or arbitrary data-shaped row | producer handshake refuses before network/world write |
| `DS15-PASSPORT-BOUNDARY` | keep raw bytes and passport marker fields but remove one decisive schema/units/alignment/license/PII/trust check | recomputed passport refuses; quarantine renders; world delta stays zero |
| `DS15-EPOCH-ACTIVATION` | create an admitted-looking passport without matching pending, production and active overlay receipts | no world-growth event; action fails closed |
| `DS15-REENTRY-BINDING` | keep global N13b status/counts but change case/design problem/gap/receipt, bind active overlay A while reading B, or omit post-epoch trace | per-row movement stays empty/invalid; global status cannot substitute |
| `DS15-ACTION-HEAD` | orphan phase CAS/event/head, fork predecessor generation, or crash after active epoch | no false terminal; typed recovery resumes from exact committed phase without reacquisition |
| `DS15-OFFLINE-AUTHORITY` | enqueue/replay decision or execution offline with a formerly valid token | no network dispatch; server rejects stale proof; no optimistic status |
| `DS15-N13B-NEGATIVE-HONESTY` | change historical `no_growth` to `grew` or 0 epochs to 1 without source receipts | projection invalid; visible history remains quarantine/no-growth/deeper-terminal |
| `DS15-MACHINE-PARITY` | mutate/remove/reorder a visible raw field after capture | rendered-DOM/MACHINE parity fails against the one response byte sequence |
| `DS15-SIBLING-CONSUMER` | add another endpoint/component that reads raw N13a/N13b JSON or generic ingest as authority | generic strangle/census test fails |

## Clustered execution plan

Mechanism caps count unique production/tooling paths. Tests; this plan and its
journal; generated OpenAPI/client files; disposition JSON/report; snapshots;
and tests that move a pinned constant are P39 companions outside the caps. Every
authorized companion is named exactly below or, for browser snapshots, by a
complete owned-root rule. No additional moved-constant test is preauthorized:
if execution discovers one, stop for a plan amendment before editing it. One
mechanism is never split across commits to fit a cap.

The complete declaration contains **37 unique mechanism paths**. The hard slice
ceiling is exactly **37**, derived from that declared union; there is no padded
contingency. Path 38 is a stop and plan-amendment request. A path may narrow
away, but an undeclared replacement or companion promoted into mechanism work
requires the same amendment and a fresh union derivation.

Two independent cap derivations must agree before C01 and closeout:

1. cluster arithmetic `6 + 14 + 12 + 4 + 1 = 37`; and
2. a parser union of every bold `Add/Modify (mechanism)` path below, excluding
   P39 companions, with known members
   `src/polisyos/runtime/quality/acquisition_route_loop.py` and
   `apps/runtime-dashboard/src/features/runs/components/AcquisitionGrowthBacklog.tsx`.

The widening budget is **11 repair rounds**, one for each concrete predicate
class below. A round may repair or redistribute work only within the declared
37-path set; it does not buy another path. Narrowing that only removes a way to
be fooled is free. A second finding in one class invokes P40: widen the property
to the quantity it needs inside the ceiling, or declare the bounded residual
and run its falsifier. A new capability, permission, producer arm, writer or
undeclared path is a plan amendment, not a round.

| cluster | property | declared mechanisms | ceiling | widening rounds |
| --- | --- | ---: | ---: | ---: |
| C00 | admit plan, remeasure sets/fences and pin reds | 0 | 0 | 0 |
| C01 | strict owner cost/read contracts over N13a/N13b, overlay and quarantine | 6 | 6 | 2 |
| C02 | run-bound HTTP, PA2 decision request, durable worker and exact re-entry receipt | 14 | 14 | 4 |
| C03 | atomically regenerate/reproduce OpenAPI and both clients | 0 | 0 | 0 |
| C04 | render global scorecard/backlog/structural routes and strict detail | 12 | 12 | 2 |
| C05 | accountable approval, continuous timeline and exact-byte MACHINE export | 4 | 4 | 2 |
| C06 | freeze/review/visual/register/readback closeout | 1 | 1 | 1 |

| round | cluster | predicate boundary | falsifier that prices the round |
| --- | --- | --- | --- |
| R01 | C01 | governed source/content admission | corrupt a registered hash/schema/rule while preserving projection markers |
| R02 | C01 | read-owner purity across overlay/quarantine | make any projection call open a writer or add a raw sibling consumer |
| R03 | C02 | current run/planner/cost closure | stale the manifest/planner or preserve cost while removing its verified basis |
| R04 | C02 | PA2/DS9 resource binding | reuse a decision across tenant/run/source-job/route/effect or remove step-up |
| R05 | C02 | safe N13b port plus CAS/event/action-head receipt | offer raw paths, orphan CAS/event/head, omit an owner receipt, or attempt a second fetch/epoch on recovery |
| R06 | C02 | exact same-case re-entry without N7 rewrite | change case/gap/epoch binding and make the legacy N7 write arm raise |
| R07 | C04 | global structural/ranking truth | add rows/cost labels or rename interim ranking as VOI |
| R08 | C04 | route-detail facet identity | join global status, lose a receipt ref, or synthesize a mixed facet client-side |
| R09 | C05 | online accountable action | replay stale approval or queue/execute offline |
| R10 | C05 | continuous motion and exact-byte parity | mutate captured bytes, timeline order, focus or live-region transition |
| R11 | C06 | evidence-backed disposition transition | remove visual/semantic/CC24 evidence while retaining ready/closed markers |

### C00 - admission, path fences and real reds

**Mechanism cap:** 0. **Widening:** 0.

**P39 only:** this plan and execution journal
`docs/superpowers/journals/2026-08-27-ds15-acquisition-routes.md`. C00 writes no
test shell under either backend or held frontend prefixes. No debt register,
generated artifact, source, disposition register, or snapshot changes.

Rerun the two output, residual, route, HTTP and selection derivations recorded
above. Enumerate DS11's complete held-prefix diff twice: Git diff/name-status
against its execution base and the DS11 plan/committed-branch path declaration.
Report disagreement. Record every named falsifier's executable red
specification in the journal; each later cluster materializes its own reds in
the exact P39 paths declared below before touching its mechanisms. Existing
N13a/N13b owner tests remain byte-identical and green.

**Acceptance:** gate ancestry, branch, prefix, base, output counts, route split,
N13b selection/terminal, DS11 fence and inherited reds have receipts. No
mechanism path changed.

### C01 - owner cost/read contracts and projections

**Add/Modify (mechanism, 6 paths):**

- modify `src/polisyos/runtime/quality/acquisition_planner.py`;
- add `src/polisyos/runtime/http/services/acquisition_surface_contracts.py`;
- add `src/polisyos/runtime/http/services/acquisition_surface_projection.py`;
- modify `src/polisyos/runtime/http/services/governed_projections.py`;
- modify `src/polisyos/data_forge/domains/catalog/knowledge/overlay.py` only to
  add a validated, read-only epoch/passport/event projection; and
- modify `src/polisyos/data_forge/read_api/catalog.py` to expose that owner read
  seam.

The planner extension adds strict `PlannerAcquisitionCostSchedule@1.0`, its
named `load_planner_acquisition_cost_schedule` owner loader, and a separate
versioned `AcquisitionCostBasisRecord` producer independently of VOI. The
schedule carries owner/purpose/effective time/rule/currency, exact named
gap-basis rows, rates and a content hash. The record carries the schedule ref/
hash, chosen basis ref, line items, time/expert estimates and recomputed total;
an implicit/default zero is invalid. No exact schedule row means
`cost_basis=missing`, even if legacy `_cost_basis_for_gap` could manufacture its
unknown-gap default. That legacy candidate path is not removed or rewritten,
so existing `AcquisitionPlannerReport` serializations and N13a/N13b outputs
remain byte-identical. A future runtime route is actionable only when its
compiled-run closure carries the separate record and exact schedule binding.
This extends the existing producer rather than inventing a UI cost calculator.
Fabric's existing `list_quarantine_records`/`build_quarantine_report` are
consumed unchanged. The projection validates N13a/N13b sources through their
registered schema/rule/content identities, adds the missing carrier-liveness and
N13b audit-history governed projection definitions, and composes strict facts.
It does not expose raw quarantined payload bytes, rerun a live probe, execute a
FetchPlan, or write an overlay receipt.

**P39 tests, exact set:** add
`tests/unit/runtime/http/test_acquisition_surface_projection.py` and
`tests/repo_quality/tools/test_ds15_acquisition_surface_strangle.py`; modify
`tests/unit/runtime/http/test_governed_projection_service.py`,
`tests/unit/runtime/http/test_governed_projection_api.py`, and
`tests/unit/data_forge/domains/catalog/knowledge/test_overlay.py`, plus
`tests/unit/runtime/quality/test_acquisition_planner.py`. N13a/N13b
repository-quality tests, artifacts, journals and write-path owner tests remain
byte-identical; DS15 consumer/strangle tests import their public seams.

**Named reds:** `DS15-STRUCTURAL-NOT-DATA`, `DS15-BINDING-NOT-DATA`,
`DS15-RANKING-NOT-VOI`, `DS15-COST-BASIS`,
`DS15-N13B-NEGATIVE-HONESTY`, and the
remove-property/keep-marker passport and active-epoch mutations.

**Acceptance:** strict global packet renders 12/18/144/124/15/3 and N13b
5 attempts/2 raw responses/0 admissions/0 epochs from owner facts; structural
and data denominators remain separate;
ranking-only is unambiguous; a run route has a cost only from the new verified
planner record and cost drift blocks; no read opens a writer transaction or
changes overlay/quarantine bytes.

### C02 - run-bound action and one world-growth bridge

**Add/Modify (mechanism, 14 paths):**

- add `src/polisyos/runtime/quality/acquisition_route_loop.py`;
- modify `src/polisyos/runtime/quality/generation_cycle.py`;
- modify `src/polisyos/runtime/quality/agent_action_authority.py` to admit the
  guarded ArtifactStore protocol with equivalent CAS/signature checks and add
  the gateway-owned deferred reservation/durable decision loader that delegates
  the eventual effect to existing `execute_bound_effect`;
- add `src/polisyos/runtime/http/services/acquisition_action_service.py`;
- modify `src/polisyos/runtime/http/services/control/run_lifecycle.py`;
- modify `src/polisyos/runtime/http/services/control_plane_store.py`;
- modify `src/polisyos/runtime/http/services/_control_contracts.py`;
- modify `src/polisyos/core/contracts/control.py` for the canonical
  `ControlJobKind` literal;
- add `src/polisyos/runtime/http/routes/acquisitions.py`;
- modify `src/polisyos/runtime/http/app.py`;
- modify `src/polisyos/runtime/http/routes/__init__.py`;
- modify `src/polisyos/runtime/http/container.py`;
- modify `src/polisyos/runtime/http/dependencies.py`; and
- modify `src/polisyos/runtime/http/openapi_contract.py`.

`acquisition_route_loop.py` is an orchestrator/receipt owner, not a data writer.
It resolves the verified completed control-job/compiled-run closure, planner
report and established cost basis, builds the exact PA2 operation/invocation/
intent, and seals the
owner-supplied production `AcquisitionExecutionPort`. The new `acquisition`
control-job kind is added once to canonical `ControlJobKind`; the two local
accepted-kind guards in `_control_contracts.py` and `control_plane_store.py`
must derive/validate against that canonical literal rather than become a third
job-kind vocabulary. `control_worker.py` remains unchanged because it already
dispatches a supplied handler generically. The action handler persists strict
requested/executing detail receipts before it acts, loads the durable allowed
decision through the gateway, and supplies the port as the exact
`execute_bound_effect` callback. It consumes the existing passport, Fabric
quarantine and Data Forge overlay owners through that port; it never calls
N13b's raw-path function directly.

For future runs, `generation_cycle.py` attaches C01's separate cost-basis
record and content hash to the terminal closure only when the named planner
schedule loader returns an exact current gap-basis row. It does not recost
historical runs, use the legacy unknown-gap fallback for actionability, or
synthesize a default during GET. The planner report, cost schedule/record and
displayed total all enter the PA2 resource/operation digest and are re-resolved
before the worker starts.

The canonical caller is
`GenerationCycleController._plan_n7_requirement_gap_if_requested`: after the
canonical route is selected, it loads the exact planner-owned schedule, invokes
C01's cost producer with the requirement gap and recommended strategy,
validates the returned record, and places the record plus its independent
content hash in the `GenerationCycleRecord`/terminal `costed_plan`.

The real persistence owner is the existing `natural_language_run` branch in
`ControlPlaneService`: it calls `_put_json_artifact` for the complete
`CompiledRecursiveGenerationCycleRun` as
`runtime.compiled_recursive_generation_cycle`, puts that CAS ref in completed
control-job progress, and emits a terminal diagnostic event whose artifact refs
contain the same compiled ref plus the capability-manifest ref. C02 adds no
Core run and no cost store. `acquisition_surface_projection.py` resolves the
completed job by tenant/cell/run/job, requires progress/event/ref agreement,
verifies the guarded CAS sidecar/schema/bytes, validates the compiled model and
nested record hash, reloads the schedule by its exact version/hash, and
recomputes the total. It treats the CAS byte identity and nested record hash as
decisive; the compiled model's self hash alone is not enough to prove leaf-node
cost content. C01/C02 integration tests prove input condition -> planner/
schedule producer -> compiled-run CAS -> matching completed-job progress and
diagnostic-event refs -> eligible route, plus unknown schedule row, ambiguous
job, missing/ref-drifted record or event -> `producer_missing`/
`revalidation_required`.

After a negative terminal it writes the terminal `AcquisitionRouteLoopReceipt`.
After an admitted active epoch it first persists a
`world_committed_reentry_pending` phase receipt, then invokes a bounded
re-entry-only method added to `generation_cycle.py`, and only then writes the
terminal loop receipt. CAS immutability is preserved: a receipt never claims a
future re-entry. A crash after epoch activation resumes from the exact active
receipt and performs re-entry only; it cannot fetch or activate again.

The re-entry method accepts the exact prior `GenerationCycleRun`/cycle and
original DesignProblem, verifies the `OverlayAdmissionReceipt` through the Data
Forge owner, binds baseline identity plus overlay store/path, epoch, passport
and activation receipt, injects that same overlay path into
`RealValueOwnerGateway`, and calls `_run_cycle` directly. It never calls
`run()`, `_reenter_cycle_after_n7_acquisition`,
`_run_n7_acquisition_if_requested`, the generic
`run_acquisition_closed_loop` world-write arm, or
`POST /control/data/ingest`. It emits a new immutable re-entry receipt and never
mutates the prior run. Do not widen the runtime-quality public `__init__`
surface merely to expose this internal bridge.

No new permission is added. GETs reuse run review. Decision request and execute
reuse `EVIDENCE_ACQUIRE`, request-bound `runtime.evidence.acquisition`, and
acquisition step-up; the human record remains on DS9's route/permission/step-up.
VIEWER/SERVICE/SYSTEM cannot perform the human act. The operation is
idempotent on tenant/run/source-job/route/planner/decision hashes and fails closed on
partial audit, CAS, passport, production or re-entry persistence. Missing
signed producers or the owner execution port keeps the route
`producer_missing`; a fake port is test authority only.

**P39 tests, exact set:** add
`tests/unit/runtime/quality/test_acquisition_route_loop.py`,
`tests/unit/runtime/http/test_acquisition_routes_api.py`, and
`tests/unit/runtime/http/test_acquisition_route_authority_sink.py`,
`tests/unit/runtime/http/test_acquisition_control_worker.py`,
`tests/integration/runtime_frontend/test_ds15_acquisition_route_contract_bridge.py`;
modify
`tests/unit/runtime/quality/test_generation_cycle.py`,
`tests/unit/runtime/quality/test_agent_action_authority.py`,
`tests/unit/runtime/http/test_runtime_service_container.py`,
`tests/unit/runtime/http/test_runtime_api_contract_hardening.py`,
`tests/unit/runtime/http/test_runtime_authorization_access_audit.py`,
`tests/unit/runtime/http/test_control_plane_store.py`,
`tests/unit/runtime/http/test_control_service_di.py`, and
`tests/unit/runtime/http/services/test__control_contracts.py`; modify
`tests/unit/runtime/mirror_contracts/test_control.py` to pin the canonical job
literal and both runtime consumers.
Existing human-decision, acquisition-executor, overlay-visibility and N13b
owner tests are baseline receipts, not DS15 edit targets.

**Named reds:** `DS15-NO-STALE-REVIVAL`, `DS15-COST-BASIS`,
`DS15-DEFERRED-PA2`,
`DS15-PASSPORT-BOUNDARY`, `DS15-EPOCH-ACTIVATION`,
`DS15-REENTRY-BINDING`, sibling-consumer strangle, a
forged client status/body, cross-tenant/cross-run/cross-route record reuse, and
crash-after-passport/before-epoch/readback cases. Bind an active receipt from
overlay A while making re-entry read overlay B: it must fail closed. Crash after
active epoch but before re-entry/terminal receipt must surface
`reentry_recovery_required` and resume re-entry without another fetch or
activation. Patch the legacy N7 acquisition arm and generic ingest seam to
raise: admitted-overlay re-entry must still complete, proving that the bridge
consumes growth rather than writing it again.

**Stop:** if the verified control-job/compiled-run closure cannot supply the
original DesignProblem and exact planner/cost record or its job progress and
diagnostic-event refs disagree; the signed PA2 or institutional qualification
inputs are absent; the N13b owner has not supplied a guarded tenant-bound
execution port; or re-entry cannot consume an already-active catalog overlay without
editing `fabric/world/` or `data_state_substrate.py`, keep execution
`producer_missing`/`bridge_missing`. Do not build a case-data index, scan CAS,
call the raw-path executor, create a second world writer, or use a repository
artifact as authorization. The narrow control-store route/action head declared
above is an action discoverability pointer, not case/world data.

**Acceptance:** a fake-port test route exercises decision request -> DS9 record
-> sealed worker -> quarantine/no-growth, and one admitted behavioral fixture
exercises phase receipts -> real passport/overlay activation -> crash-safe exact
same-case re-entry -> terminal receipt. Missing production inputs remain visibly
`producer_missing`; N13b history remains its real negative. These receipts admit
the fail-closed mechanism into C06 review, but DS15 closure additionally
requires CC24's fresh non-fixture positive receipt.

### C03 - generated ABI transaction

**Mechanism cap:** 0. Generated companions only.

This cluster begins only after C01/C02 source freeze **and DS11 landing**, because
the generated family includes a held dashboard path. Acquire the schema/client
token alone; never co-hold the Atlas register or Playwright lane.

**P39 generated companions, exact set:**
`schemas/runtime_api_v1.openapi.json`,
`packages/runtime-api-client/canonicalRuntimeApiClient.ts`,
`packages/runtime-api-client/canonicalRuntimeApiClient.js`,
`packages/runtime-api-client/runtimeApiClient.ts`,
`packages/runtime-api-client/runtimeApiClient.js`,
`packages/runtime-api-client/types.ts`, and
`apps/runtime-dashboard/src/api/types.ts`. Generate from runtime HTTP source,
then regenerate both clients. Never hand-edit JSON or generated TypeScript.

Generate twice into separate harness scratch roots and compare every output to
the committed family and to its second scratch twin. Corrupt one new facet,
discriminator, replay pin and operation binding in scratch; contract checks must
fail. Run the runtime API contract and architecture guardrails after releasing
the token.

The generated-family denominator has two derivations: the exact enumeration
above is `1 schema + 5 runtime-client files + 1 dashboard type file`, and each
generator output-manifest/scratch-tree walk must return that same seven-path
set. The run-bound operation denominator likewise comes from the four source
route declarations above and an independent emitted-OpenAPI path/operation
diff; disagreement blocks the cluster.

**Acceptance:** OpenAPI and both clients contain the four new run-bound
operations, the new governed `acquisition-growth` projection ID, and strict
facet unions; two clean generations are byte-identical; stale/corrupt outputs
fail; no DS11 byte is overwritten without the landing ancestry receipt.

### C04 - global read surfaces and route detail (after DS11)

**Add/Modify (mechanism, 12 paths):**

- add `apps/runtime-dashboard/src/features/runs/api/useAcquisitionRoutes.ts`;
- add `apps/runtime-dashboard/src/features/runs/domain/acquisitionRoutePresentation.ts`;
- add `apps/runtime-dashboard/src/features/runs/components/AcquisitionGrowthBacklog.tsx`;
- add `apps/runtime-dashboard/src/features/runs/components/AcquisitionRouteDetail.tsx`;
- add `apps/runtime-dashboard/src/features/runs/components/ConnectorAcquisitionScorecard.tsx`;
- add `apps/runtime-dashboard/src/features/runs/components/AcquisitionPassportPanel.tsx`;
- add `apps/runtime-dashboard/src/features/runs/components/AcquisitionQuarantineLedger.tsx`;
- modify `apps/runtime-dashboard/src/features/runs/components/CycleBoard.tsx`;
- modify `apps/runtime-dashboard/src/api/queryKeys.ts`;
- modify `apps/runtime-dashboard/src/api/validators.ts`;
- modify `apps/runtime-dashboard/src/shared/i18n/locales/en.json`; and
- modify `apps/runtime-dashboard/src/shared/i18n/locales/uk.json`.

The hook captures the exact response bytes and uses governed no-authority-cache
semantics. Presentation functions only narrow/format generated contracts. The
Cycle Board adds the global scorecard/backlog and structural route details
without joining N13b global status onto a row. Cost and VOI absences render as
typed states. Tier decay and quarantine are as prominent as any positive.

**P39 tests, exact set:** add
`apps/runtime-dashboard/src/features/runs/api/useAcquisitionRoutes.test.tsx`,
`apps/runtime-dashboard/src/features/runs/domain/acquisitionRoutePresentation.test.ts`,
`apps/runtime-dashboard/src/features/runs/components/AcquisitionGrowthBacklog.test.tsx`,
`apps/runtime-dashboard/src/features/runs/components/AcquisitionGrowthBacklog.a11y.test.tsx`,
`apps/runtime-dashboard/src/features/runs/components/AcquisitionRouteDetail.test.tsx`,
`apps/runtime-dashboard/src/features/runs/components/AcquisitionRouteDetail.a11y.test.tsx`,
`apps/runtime-dashboard/src/features/runs/components/ConnectorAcquisitionScorecard.test.tsx`,
`apps/runtime-dashboard/src/features/runs/components/ConnectorAcquisitionScorecard.a11y.test.tsx`,
`apps/runtime-dashboard/src/features/runs/components/AcquisitionPassportPanel.test.tsx`,
`apps/runtime-dashboard/src/features/runs/components/AcquisitionPassportPanel.a11y.test.tsx`,
`apps/runtime-dashboard/src/features/runs/components/AcquisitionQuarantineLedger.test.tsx`,
`apps/runtime-dashboard/src/features/runs/components/AcquisitionQuarantineLedger.a11y.test.tsx`,
and
`apps/runtime-dashboard/src/features/runs/components/acquisitionRoutes.locale.test.ts`;
modify
`apps/runtime-dashboard/src/features/runs/components/CycleBoard.test.tsx`,
`apps/runtime-dashboard/src/features/runs/routes/CycleBoardPage.test.tsx`,
`apps/runtime-dashboard/src/features/runs/routes/CycleBoardPage.parity.test.tsx`,
`apps/runtime-dashboard/src/features/runs/routes/CycleBoardConsumerCensus.test.ts`,
`apps/runtime-dashboard/src/api/validators.test.ts`, and
`apps/runtime-dashboard/src/api/governedQueryPolicy.test.ts`. The C01 DS15
strangle test supplies a source-derived generic AST/consumer census over the
complete frontend component root, so it automatically includes these paths
after the DS11 handoff without a C04 edit.

**Named reds:** structural rows never show buttons; adding rows changes neither
structural sufficiency nor route status; ranking-only never renders VOI; local
sort shows override; tier decay cannot render healthy; raw response without
passport renders quarantine; global N13b status creates no row movement.

**Acceptance:** REVIEWER/EXPERT see the complete owner truth; MACHINE export and
DOM agree; the board can grow data-only from a new valid row; a structural row
cannot become acquirable through frontend code or extra rows.

### C05 - accountable button and continuous visible motion (after DS11)

**Add/Modify (mechanism, 4 paths):**

- add `apps/runtime-dashboard/src/features/runs/components/AcquisitionExecutionTimeline.tsx`;
- add `apps/runtime-dashboard/src/features/runs/components/AcquisitionApprovalFlow.tsx`;
- add `apps/runtime-dashboard/src/features/runs/components/acquisitionRouteExport.ts`;
- modify `apps/runtime-dashboard/src/features/runs/routes/CaseWorkspacePage.tsx`.

Reuse `useHumanDecisions` and `HumanDecisionGate`; do not clone DS9. The
approval flow performs decision preparation, evidence exposure, DS9 approval,
fresh execute, and governed refresh. Both mutations are `networkMode=always` or
equivalent online-only and fail before fetch when offline. No optimistic cache
update changes authority facets. The timeline is one visual sequence with
independent raw fact blocks and exact receipt links.

**P39 tests, exact set:** add
`apps/runtime-dashboard/src/features/runs/components/AcquisitionExecutionTimeline.test.tsx`,
`apps/runtime-dashboard/src/features/runs/components/AcquisitionExecutionTimeline.a11y.test.tsx`,
`apps/runtime-dashboard/src/features/runs/components/AcquisitionApprovalFlow.test.tsx`,
`apps/runtime-dashboard/src/features/runs/components/AcquisitionApprovalFlow.a11y.test.tsx`,
and
`apps/runtime-dashboard/src/features/runs/components/acquisitionRouteExport.test.ts`;
modify
`apps/runtime-dashboard/src/features/runs/routes/CaseWorkspacePage.test.tsx`,
`apps/runtime-dashboard/src/features/runs/routes/CaseWorkspacePage.parity.test.tsx`,
and `apps/runtime-dashboard/src/api/optimistic.test.ts`. Existing
`useHumanDecisions`/`HumanDecisionGate` tests remain DS9-owned and unchanged.
Add slice-owned visual spec
`apps/runtime-dashboard/e2e/ds15-runtime-dashboard.visual.spec.ts`; its complete
snapshot companion set is every generated file under
`apps/runtime-dashboard/e2e/ds15-runtime-dashboard.visual.spec.ts-snapshots/`.
Do not edit DS6's content-bound visual spec/snapshots.

**Named reds:** `DS15-OFFLINE-AUTHORITY`, stale decision replay, double execute,
approval-without-execution, quarantine/no-growth, admitted/re-entry-pending,
same-case mismatch, and `DS15-MACHINE-PARITY` mutations.

**Acceptance:** a blocked data-shaped test case shows reason -> established,
owner-backed estimated cost -> review -> mandate/evidence -> approved decision
-> executing -> passport/quarantine -> growth/no-growth -> re-entry/deeper
terminal without page or context loss. A missing, default-zero or unverified
cost stops before review. Structural and historical-only rows have no active
flow.

### C06 - freeze, verify and close

**Add/Modify (mechanism, 1 path):**

- modify `architecture/atlas_surfaces/check_frontend_disposition_register.py`
  only if the existing generic checker cannot adjudicate DS15's real new
  operations/surfaces.
If no checker code is needed, the actual mechanism count narrows to 36.

Freeze source, run architecture/backend/frontend review in parallel, batch only
blocking findings, then run the expensive wave once. Before acquiring the Atlas
lock, execute exactly one snapshot-writer visual run followed by two no-writer
runs, Chromium, one worker, zero retries, slice grep only. Verify keyboard
order, focus return, 200% zoom, mobile, dark/light, axe, live-region updates,
reduced motion, snapshot stability and CC24's real receipt. Delta-only rereview
follows any blocking repair.

Only after those receipts exist, acquire the Atlas lock for this exact P39 set:
`architecture/atlas_surfaces/frontend-disposition-register.json`,
`architecture/atlas_surfaces/live-application-readiness-ledger.json`,
`architecture/atlas_surfaces/test_frontend_disposition_register.py`, and the
generated
`docs/reference/frontend/atlas-frontend-disposition-register.md`; never the
debt register. Register only measured DS15 transitions; do not edit other
slices' evidence or the deep-import baseline. If the existing generic checker
already adjudicates the transition, its source path narrows away but its test
remains in this exact companion set.

Re-derive 37 declared/37 ceiling and actual mechanism paths twice; re-derive all
set counts; classify every red under P41 against the slice base; read the final
file set, branch and commits from the committed branch.

**Acceptance:** every CC has its required receipt; target chain is contract ->
producer -> persisted planner/execution artifact -> PA2/DS9 bridge -> N13b
passport/overlay/quarantine -> same-case re-entry -> HTTP -> UI/MACHINE ->
negative/e2e semantic test. CC24 additionally proves the complete continuous
motion with a fresh non-fixture receipt. If it is absent, record the precise
partial/blocked state and do not make the C06 register/commit transition to
closed.

## Declared mechanism file map

| owner family | paths | count |
| --- | --- | ---: |
| owner cost/read contracts/projections | `acquisition_planner.py`, `acquisition_surface_contracts.py`, `acquisition_surface_projection.py`, `governed_projections.py`, catalog `overlay.py`, catalog read API | 6 |
| action/HTTP bridge | `acquisition_route_loop.py`, `generation_cycle.py`, `agent_action_authority.py`, `acquisition_action_service.py`, control lifecycle/store/contracts, canonical `ControlJobKind`, acquisition routes, app/router/container/dependencies/OpenAPI contract | 14 |
| dashboard reads | hook, presentation, five read components, Cycle Board, query keys, validators, two locales | 12 |
| dashboard action/MACHINE | timeline, approval flow, export, Case Workspace | 4 |
| Atlas checker | disposition checker, conditionally narrowed away | 1 |
| **total** | parser union must match | **37** |

Mandatory P39 generated client family is seven files: one OpenAPI schema, five
runtime-client files, and one dashboard types file. Tests, plan/journal,
register/report and the complete slice snapshot root are outside mechanism
caps, but only the exact sets declared in C00-C06 are authorized.

## Parallel and serialized-resource schedule

```text
C00
  -> C01 owner cost/read contract freeze
    -> C02 action bridge                   no DS11-held source paths
                                         |
                       WAIT: DS11 landing ancestry + dual complete-prefix census
                                         |
                       C03 schema/client token (atomic family)
                                         |
                       C04 frontend reads
                         -> C05 approval/timeline
                           -> freeze/review
                             -> C06 visual/a11y lane
                               -> final Atlas lock/register/readback
```

Within C01/C02, read-only research, red scaffolding, logic tests and Ruff/type
checks may run in parallel, but C02 integration and commit consume the read-back
C01 cost/contract hash and therefore follow C01 freeze. Serialize only the
catalog overlay/DuckDB scratch when a test opens it.
The unbound-writes lane remains untouched. C03 schema/client token, C06
Playwright/visual lane, and the final C06 Atlas register writer are three
separate locks and are never co-held. Storybook/fixed-port server, if used for
review, serializes with Playwright.

The frontend wait point is exact: **before C03's committed generated-family
write and before the first C04/C05/C06 path**. Backend C00-C02 may complete
before DS11, with C01 -> C02 ordering. A scratch OpenAPI export may be inspected
before DS11, but no partial generated family is committed.

The append-only ancestry handoff is explicit. Preferred execution starts from
a measured integration head that already contains DS11. If C00-C02 begin early,
commit them on their attached backend branch and stop there. After DS11 lands,
create a fresh attached DS15 execution branch/worktree from the measured head
containing DS11 and locally cherry-pick every read-back pre-wait DS15 commit,
C00 through C02, in order, unless a commit is proved already present in that
head. Re-read each picked commit's file set and content, prove the DS11 landing
commit is now an ancestor, and only then enter C03. Do not merge, rebase, reset,
move the old branch, or wait for ancestry to appear on an already-diverged
branch.

## Verification doctrine and command families

Every command block starts with prefix/branch readback. Record exit codes before
any subsequent formatting/tee operation. Timed invocations use a shape like:

```bash
git rev-parse --show-prefix
git status -sb
ds15_uptime_before="$(uptime)"
/usr/bin/time -p <command>
ds15_command_status=$?
ds15_uptime_after="$(uptime)"
printf '%s\n' "$ds15_command_status" "$ds15_uptime_before" "$ds15_uptime_after"
test "$ds15_command_status" -eq 0
```

Record `real`, `user`, and `sys`; the handoff explicitly reports `user + sys`
and both uptime values. No command is timed by an unmeasured timeout. Measure one
completed run before freezing a ceiling.

During iteration, verify by blast radius:

- focused C01/C02 unit/integration/repo-quality tests;
- real `--check` validators plus corrupt-field/source-flip mutations for each
  newly projected owner artifact;
- Ruff check/format on changed Python paths;
- architecture guardrails and runtime API contract after HTTP changes;
- focused Vitest/parity/a11y tests and TypeScript check after C04/C05;
- exact two-scratch generated-family reproduction;
- slice-only Playwright writer/no-writer/no-writer after source freeze.

At closeout run the backend verify and CI-parity wave once, subject to measured
timeouts, after all reviews. Existing reds are inherited only after replaying
the exact command at base `2525da7306...` and proving the DS15 changed-path set
intersects the command's complete input denominator at zero.

## Issue codes

| code | meaning / surface action |
| --- | --- |
| `DS15-STRUCTURAL-GAP-NOT-ACQUIRABLE` | owner route is structural; render refusal, omit action |
| `DS15-ROUTE-PRODUCER-MISSING` | verified completed control-job/compiled-run closure lacks exact job, planner, DesignProblem or producer binding |
| `DS15-COST-BASIS-MISSING` | no current content-bound owner cost basis; omit action |
| `DS15-EXECUTION-PORT-MISSING` | no tenant-bound guarded N13b production port; raw paths refused |
| `DS15-AUTHORITY-PRODUCER-MISSING` | signed PA2 or institutional qualification producer absent |
| `DS15-ROUTE-REVALIDATION-REQUIRED` | historical/current hash, rule, epoch, availability, rights or mandate differs |
| `DS15-RANKING-ONLY-NOT-VOI` | display interim priority; VOI unavailable |
| `DS15-DECISION-REQUIRED` | PA2 request exists; DS9 record not yet current |
| `DS15-DECISION-INVALID` | wrong run/route/action/record or stale decision |
| `DS15-OFFLINE-ACTION-FORBIDDEN` | decision/execution attempted without live revalidation |
| `DS15-PASSPORT-REFUSED` | raw evidence remains quarantine; never world data |
| `DS15-EPOCH-ACTIVATION-MISSING` | passport/production/overlay receipt chain incomplete |
| `DS15-NO-WORLD-GROWTH` | zero admitted delta; render terminal honestly |
| `DS15-REENTRY-BINDING-MISSING` | no exact same-case post-acquisition trace; no movement row |
| `DS15-REENTRY-RECOVERY-REQUIRED` | world commit exists but exact re-entry/terminal head is incomplete; resume re-entry only |
| `DS15-SHARED-SPINE-DRIFT` | second writer/store/passport/epoch path detected |
| `DS15-GENERATED-DRIFT` | OpenAPI/client family differs from sources or scratch twin |
| `DS15-DS11-FENCE-HELD` | held-prefix ancestry/path census not released |
| `DS15-POSITIVE-RECEIPT-MISSING` | external producers and/or real successful demonstration not established; DS15 cannot close |

## Pattern pass and capability state

Read the failure/repair register again before C01 design and C06 closeout.

| patterns | opening risk | target pattern / acceptance |
| --- | --- | --- |
| P01/P02/P03/P12 | rich N13 artifacts and executor have no DS15 chain | strict owner artifact -> runtime bridge -> HTTP -> UI/MACHINE -> semantic negative |
| P04/P05/P09/P15 | approval/fetch/row presence laundered into admission or success | independent facets; passport and active epoch are decisive; quarantine/no-growth prominent |
| P10/P25/P29 | attractive button over a structural/stale gap | server-recomputed gap class/currentness; add-rows and stale-revival falsifiers |
| P27/P28/P31 | generic ingest, a second passport/store, or per-component raw parsing | one N13b spine; generic strangle and sibling-consumer mutation |
| P32/P37/P38 | `route_id`, status string, record-ref/cost-field presence or rank used as proof | resolve + content-bind + verifier provenance; recompute cost from owner basis; predicate class frozen at admission |
| P33/P34 | teach fixture IDs or marker fields to tests | remove-property/keep-markers, synonyms, malformed, sibling and historical-ID mutations |
| P35/P36 | mix 15 residuals with 3 routes or 18 probes with 144 records | two complete-set derivations, denominator and artifact identity on every count |
| P39 | count plans/tests/generated/register/snapshots as mechanisms | 37 declared mechanisms, exact 37 hard ceiling, companions explicit |
| P40/P41 | patch the second escape or inherit a red from a nearer base | bucket second finding; exact slice-base replay and complete-input disjointness |

Target closure is `typed contract/artifact + producer + persisted
planner/execution/event + PA2/DS9 orchestration bridge + N13b
passport/overlay/quarantine consumer + HTTP/UI/MACHINE surface + negative/e2e
semantic test + fresh non-fixture continuous-motion receipt`. Until a real
admitted acquisition reaches an active epoch with a positive admitted delta and
same-case re-entry through the safe production port and signed external
producers, DS15 remains `producer_missing + verification_missing` and cannot
close, even if every mechanism test is green.

## Opening non-closures and blocking stop states

| non-closure | precise state / boundary | closure signal |
| --- | --- | --- |
| successful live world growth | closure blocker: `producer_missing + verification_missing`; N13b truth is 0 admitted, 0 epochs, no growth | safe N13b production port + signed PA2 producers + institutional qualification owner, then fresh non-fixture terminal receipt binding admitted passport, active epoch, positive delta and same-case re-entry; otherwise DS15 stays partial/blocked |
| current `government.balance` acquisition button | `revalidation_required`/deeper connector-contract terminal; historical source-profile mismatch cannot authorize | fresh planner/rights/route resolution after `source_selector:11` or another honest producer route is current |
| actionable acquisition cost | `producer_missing`; current unversioned hard-coded/default cost path has no actionable owner ref | planner-owned `PlannerAcquisitionCostSchedule@1.0` exact named row + content-bound cost record in a verified completed control-job/compiled-run closure; unknown-gap fallback remains ineligible |
| production N13b execution handshake | `producer_missing`; raw-path local-filesystem World Bank function is in-process, not a guarded tenant-bound port | N13b owner exposes a typed production port over the same journal/CAS/passport/overlay/quarantine spine; DS15 changes no write path |
| PA2 production composition | `producer_missing`; gateway is test-composed and signed delegation/admission producers are absent | guarded-store-compatible gateway plus current signed external inputs resolve through the control owner |
| semantic-epoch qualification authority | institutional owner `absent/unallocated`; production admission fails closed | external owner supplies current signed qualification/consumer evidence; DS15 only verifies and consumes it |
| GY-GAP6 evidence/register closure | out of scope; DS15 consumes/builds operational binding but edits no GY evidence/register | owning GY lane separately admits the DS15 runtime receipt under its own plan |
| institutional principal, mandate, separation and presentation appointments | foreign signed inputs; DS15 does not appoint institutions | deployment-owned DS9 producers supply current signed inputs |
| numeric VOI for N13a backlog or N13b D2 source growth | `producer_missing`; ranking-only, no numeric owner support | canonical planner/VOI owner emits content-bound decision/ranking ref and expected value/cost |
| INT-R2 `GapAcquisitionCase` and full non-data gap union | `absent/unallocated`; current owner witness renders typed refusal | ratified INT-R2 producer/artifact lands and is independently admitted; no DS15 invention |
| PUBLIC acquisition backlog | out of scope until DS12 gate | DS12-owned public projection and disclosure/custody gate |
| automatic or offline acquisition | prohibited | no closure; acquisition remains DS9-class live human decision |
| second world write path or N13b artifact rewrite | prohibited/out of scope | no closure; consume shared overlay/passport/quarantine owners |
| debt register, other slices' evidence, deep-import baseline | explicitly out of scope | owner task, not DS15 execution |
| `fabric/world/` and `data_state_substrate.py` edits | held by unbound-writes lane and not required by declared mechanism | lane release plus approved widening only if the existing read/overlay seam is proven insufficient |
| broad DS11/a11y family migration | out of scope; DS15 touches only its post-landing declared consumers | DS11 owner lands/release; DS15 re-censuses rather than inheriting `63` as a proxy |

An absent future test or receipt is `artifact_missing`, never green. Because the
user excludes the debt register, out-of-scope obligations stay in this plan's
stop-state table and handoff until an owner authorizes separate registration;
CC24 is not one of those deferrable obligations.

## Commit sequence

| boundary | message |
| --- | --- |
| planning hand-back | `docs(atlas): plan DS15 acquisition routes` |
| C00 | `docs(atlas): bind DS15 acquisition surface reds` |
| C01 | `feat(api): bind acquisition cost and owner truth` |
| C02 | `feat(runtime): bind accountable acquisition loop` |
| C03 | `chore(api): regenerate acquisition route ABI` |
| C04 | `feat(atlas): render acquisition growth surfaces` |
| C05 | `feat(atlas): connect acquisition approval and re-entry` |
| C06 closed | `docs(atlas): close DS15 acquisition routes` only after CC24 |
| C06 blocked/partial | `docs(atlas): record blocked DS15 acquisition state` with no ready/closed register transition |

Before each commit: attached branch, prefix, exact dirty-path list, mechanism
union/ceiling, widening receipt, serialized locks and relevant tests. After each
commit, read the commit's path set and representative files from the branch, not
the index. No push or merge.

## Hand-off packet

The executor/architect receives:

- planning commit/base/branch/prefix and all three gate-ancestry receipts;
- N13a 3-output and N13b 43-output physical censuses, each with equal
  independent path-set derivations;
- logical HTTP/contract/in-process partition and the legacy-ingest non-seam;
- independent 12/18/144/124/15/3, 43/41/2 and 22-CAS/1-journal/
  20-top-level derivations;
- independent all-15 ranking-authority/method and zero-overlay-epoch/event/
  admitted-observation derivations;
- `1 data-shaped / 0 structural / 14 shape not_established` residual split and
  separate `3 structural / 0 data-shaped / 0 not_established` capstone split;
- `government.balance` requirement/gap/hash/rank, current source-profile
  mismatch, quarantine/no-growth/deeper-terminal receipts, and the separate CPI
  acceptance selection;
- ranking-only presentation rules and VOI availability proof;
- planner-owned versioned cost schedule, unknown-gap no-action fallback, and
  completed control-job/compiled-run CAS closure with progress/event/ref
  agreement;
- exact PA2/DS9/permission/step-up action sequence, guarded-store composition
  status and missing signed producer refs;
- the N13b raw-path/World-Bank-only limitation, required owner production port,
  absent institutional qualification owner, and why each is
  `producer_missing` rather than a DS15 appointment task;
- one-spine passport/quarantine/overlay/re-entry source refs plus the exact
  CAS/event/action-head receipt owner and crash-recovery phase;
- API packets, generated ABI twins, raw-response/DOM/MACHINE hashes;
- DS11 landing/path-fence release receipt and exact frontend wait point;
- 37-declared/37-ceiling mechanism derivations, 11-round accounting, visual/
  a11y timing with `user + sys` and uptime pairs; and
- every remaining out-of-scope non-closure; if the positive live receipt is
  missing, a partial/blocked handoff that explicitly says DS15 did not close.

Anything that introduces a new permission, decision source kind, acquisition
writer/store/passport/epoch allocator, public audience, current authority from a
repository artifact, client VOI computation, or path 38 requires an approved
plan amendment before code.
