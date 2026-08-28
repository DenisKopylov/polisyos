---
plan_id: atlas-ds15-acquisition-routes
title: "DS15 - Acquisition Routes & Data-Pool Growth Surfaces"
type: slice-plan
status: execution_c02_closure_resumed_ceiling_40
created: 2026-08-27
last_verified: 2026-08-28
stability: measured_plan
slice: DS15
baseline_commit: 2525da7306d329ae28fa394690e1c39133eb0d55
planning_branch: codex/ds15-acquisition-routes-plan
branch: codex/ds15-acquisition-routes-execution
execution_base_commit: f3e3d996bd6710e26f24fd913d4fe0547f1d1a0d
execution_entry_commit: 4709562c4ca67e691b355ec2941cf7d48262291e
execution_entry_plan_blob: 16de6702ab7e79fb0277d9071fdb3b9ded1f7aac
c00_status: review_repair_timing_and_authz_admitted_zero_mechanisms
c01_status: closed_after_delegated_trust_posture_reconciliation
c02_status: resumed_after_owner_rego_parity_repair
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

### C00 execution standing — 2026-08-27

C00 executes on attached branch `codex/ds15-acquisition-routes-execution` from
integration base `f3e3d996bd6710e26f24fd913d4fe0547f1d1a0d`; entry commit
`4709562c4ca67e691b355ec2941cf7d48262291e` merges the plan without changing its
entry blob `16de6702ab7e79fb0277d9071fdb3b9ded1f7aac`. The DS11 landing merge
`4ff11db52` and the three declared gate commits are ancestors of the execution
branch. C00 changes no mechanism and admits C01 only after the following
measured corrections:

- DS11's base-to-tip Git census and its committed mechanism/P39 declaration
  both return **65 paths** (`30 mechanisms + 35 companions`). The pre-C00 DS15
  parser returns **37 mechanisms**. Contrary to the supplied expected zero,
  their complete intersection is **3**:
  `apps/runtime-dashboard/src/shared/i18n/locales/en.json`,
  `apps/runtime-dashboard/src/shared/i18n/locales/uk.json`, and
  `architecture/atlas_surfaces/check_frontend_disposition_register.py`.
  All three DS11 bytes already equal the execution-base bytes, so this is
  historical overlap, not a live write conflict; the DS11 ancestry/path fence
  is released while the disagreement stays explicit.
- The execution-base `src/` denominator is **2,811 tracked files**, not the
  historical plan-entry 2,810. Independent `rg --files` and `git ls-files`
  sets are identical; independent `rg` and `git grep` searches both find zero
  `gap_class` occurrences. C01 still owns the first strict definition.
- The planned `acquisition-growth` projection cannot pass the existing owner
  worker merely by adding its enum/definition: `_validate_request` consults
  `_VALIDATORS` and otherwise emits `owner_validator_unregistered`. C01
  therefore also modifies
  `governed_projection_validation_worker.py` and its mirrored test. This
  measured pre-C01 correction moves C01 from 6 to 7 mechanisms and the hard
  union from 37 to **38**; it spends no widening round and the budget remains
  **11**.
- C00 review then proved that both acquisition GETs need an exact
  `runs.review` / `runtime.acquisition_route.tenant_collection` contract in
  `ops/policy/policies/action_permission.rego`. The closed Rego map has no
  acquisition-route class and `resource_kind_matches` requires exact equality,
  so reusing `runtime.case_inspection` or `runtime.run_paper` would be a proxy
  authorization. C02 therefore moves from 14 to 15 mechanisms and the hard
  union from 38 to **39**. This is another measured pre-C01 plan correction,
  spends no widening round, and made path 40 the then-current stop.
- P39 now names the three contributor-required README companions and one
  structured release-fragment companion exactly in C01-C03. They are mandatory
  records outside the mechanism ceiling and did not widen the then-39-path union.
- C00 review finding `timing_receipt_completeness` is a NEW class, first
  occurrence, repaired as P39 evidence with no widening round. The fresh N13a
  full rerun is green with complete wall/CPU/uptime fields. The fresh N13b full
  rerun exits `1` with `n13b_acquisition_contract_drift`; that current-worktree
  receipt is an explicit non-receipt and does not by itself establish inherited
  provenance.
- The second C00 review finding is SAME class `baseline_provenance`, one level
  deeper: it challenges the inherited attribution, not the already-completed
  timing fields. A temporary verifier at exact slice base
  `f3e3d996bd6710e26f24fd913d4fe0547f1d1a0d` proved both `polisyos` and
  `tools.lib.timing` imported from that base worktree under base-first
  `PYTHONPATH=$PWD/src:$PWD`. The same N13b checker, catalog/L5 inputs, and 600s
  ceiling then failed at both base and execution with the identical
  `n13b_acquisition_contract_drift`. That exact-base pair, combined with the
  zero changed-input intersection and equal external-input hashes, satisfies
  P41 inherited attribution. It spends no widening round, remains non-green,
  and may not support closure or authorize a generated artifact/write-path edit.

The source-level qualification ruling and `fresh_positive_production_route`
non-closure below are unchanged: C00 admits the real pending/unqualified and
production-negative lanes only; it does not authorize an active-but-unqualified
projection or a production-growth claim.

### Delegated Phase 0 and C01 execution standing — 2026-08-28

The team-architecture owner delegated one bounded repair before C01 closeout.
Commits `c52fb00b2` and `fe53c182e` change exactly the checker, its semantic
test, and the checker-owned generated register. The repair excludes the complete
depth-0 type-annotation span from tokenizer semantic-operator evidence while
preserving genuine RHS set-union and unary evidence. The first review finding
was bucketed SAME class one level deeper: the `not`/`~` shortcut preceded the
annotation rejection. The shared predicate was widened once and focused
re-review returned no Critical, Important, or Minor finding. Final owner
receipts are 50 posture tests passing, canonical writer/check/corrupt-field
drift passing, and architecture guardrails passing; the generated artifact was
byte-identical in the review-fix round. This delegated repair consumes neither
a DS15 mechanism path nor a DS15 widening round.

C01 is now formally closed at implementation commits `25abf5a54` and
`18bd72c2d`. Fresh targeted acceptance on the repaired branch passes 2 strict
cost-owner cases, 10 acquisition projection/read-purity cases, 7 complete
`acquisition-growth` worker-selection cases, and the 2 governed service/API
cases. The prescribed architecture guardrail exits `0` (`real 78.69`,
`user 66.81`, `sys 10.21`; uptime `09:07` to `09:08`) and reports the
trust-claim-posture register plus the runtime API generated families clean.
C01 therefore checks CC02, CC03, CC04, and the already-satisfied DS11 fence in
CC21. Render/action/generated/parity conditions CC05-CC20 and CC22-CC25 remain
unchecked for later clusters. At C01 close, before C02's event-registry
measurement below, the running slice budget was **7/39 mechanism paths** and
**1/11 widening rounds**.

### C02 measured mechanism amendment — 2026-08-28

R05 reached the real `validate_diagnostic_event` registry boundary before its
authority sink could persist the first acquisition phase receipt. The plan
requires exact event types `polisyos.runtime.acquisition.route_phase.v1` and
`polisyos.runtime.acquisition.route_loop.v1`; the registry contains neither.
Reusing the registered generic `polisyos.runtime.diagnostic.cas_write.v1` would
test CAS persistence while claiming acquisition phase/terminal semantics, a P38
proxy at the audit boundary. The narrow owner change is one mechanism path,
`architecture/production_quality/diagnostic_event_types.toml`, registering both
exact event types. `diagnostic_events.py` remains unchanged because the runtime
loader admits registry-defined rows and its expected tuple is a minimum, not a
closed vocabulary.

The first unbounded parser overran C06 prose and returned 44/44; it is retained
as a parser non-receipt. The corrected list-item parser returns the pre-amendment
cluster sets 7/15/12/4/1 and 39 unique paths, with the registry path absent.
Adding the one absent owner path yields 7/16/12/4/1 and **40 unique paths**;
independent cluster arithmetic is `7 + 16 + 12 + 4 + 1 = 40`. C02 therefore has
a **16-path** ceiling, the slice has a **40-path** ceiling, and path 41 is the
next stop. The R05 mechanism class was already budgeted, so the widening budget
remains 11 and current spend remains 1.

### C02 blocked checkpoint and outside-owner stop — 2026-08-28

C02 is preserved but **not formally closed** at attached-branch commit
`b633ea7b75af4d07feaf0690926712353022d21f`, whose parent is the committed
40-path amendment `26d9c8f3b15b3bb60343f2eb1b33219b9bccfb5d`. Post-commit readback
returns exactly 30 paths: the complete 16/16 C02 mechanism set, 11 test
companions, and 3 nearest-parent README companions. An independent
plan-intersection derivation returns the same 16 mechanisms. Cumulative slice
spend is therefore **23/40 mechanism paths** and **5/11 widening rounds**
(`R01`, `R03`, `R04`, `R05`, `R06`). No path or round is inferred from the
three planned test companions that were not started before freeze.

The bounded bridge behavior is green under focused authority, route-loop,
generation, HTTP, store, worker, OpenAPI, access-audit, and integration tests.
It preserves the real production-negative qualification state
`pending_epoch_activation` / `not_established` /
`policy_admission_missing`; it does not synthesize activation and edits neither
the world writer nor `data_state_substrate.py`. C02 nevertheless cannot pass
the complete live-router/Rego parity predicate. Both current and exact slice
base are missing these two pre-DS15 contracts:

- `evidence.discover` /
  `runtime.capability_discovery.search` / `tenant_collection`; and
- `decisions.validity.publish` /
  `runtime.decision_validity.epoch_batch` / `request_bound`.

The omissions reproduce unchanged at `f3e3d996b`, but C02 adds one live guarded
contract and edits the closed Rego map, so its intersection with the gate's
complete input denominator is nonzero. P41 therefore forbids calling the
current failure inherited or passable. Adding the two unrelated grants would
change another owner's authorization contract and would be a P31 instance
patch; weakening set equality would be a P38 proxy repair. This is the declared
serious outside-owner stop. Closure requires that authorization owner to admit
or otherwise govern both existing live contracts, after which DS15 must rerun
the unchanged generic parity falsifier and the remaining C02 companions.

No additional closure item is checked at this checkpoint: C01's CC02, CC03,
CC04 and CC21 remain the only checked items. C03-C06 have not started. DS15
never entered the registered OpenAPI/runtime-client/dashboard-types generation
transaction, and its seven registered outputs have no DS15 worktree delta. The
independent serialization readback nevertheless finds that unbound-writes head
`fe028145f` is already an ancestor of local `main` but is **not** an ancestor of
this branch. Five of the seven outputs differ from the DS15 base: OpenAPI,
canonical-client TypeScript, runtime-client TypeScript, client types, and
dashboard types; both JavaScript outputs are unchanged. C03 therefore remains
fenced until that landed generated family is brought forward append-only and
the seven-output census is rerun. The C02 source seam shared with DS18 and GY-O0
is frozen at `b633ea7b75`; because this task permits neither push nor merge,
that commit is an append-only source-sync coordinate, not an owner-side landing
claim.

### C02 owner repair and forward-merge standing — 2026-08-28

The authorization owner repaired the two pre-existing live-router/Rego mirror
omissions on `main` at `f17c48555809b1166a43ec96f7873f3e6d81e921` without changing
the guarded-router source of truth. DS15 independently reran the unchanged
generic parity falsifier on that clean main worktree and again after the
append-only forward merge; both runs exit `0`. The branch is clean and attached
after merge commit `0687eea2b81a1b56a2d3275f4bb95c178dd65055`, whose first parent
is the preserved DS15 head `a0941b0bc1f492dfb68cb1e59a3f062930f21aae` and second parent
is `f17c48555809b1166a43ec96f7873f3e6d81e921`. The outside-owner parity stop is
therefore cleared, while C02 remains open until its three unstarted companions
and the phase-versus-terminal receipt separation are red-first and green.

The merge also reconciles the landed trust-posture repair generically: the
tokenizer excludes the complete annotation span before unary/conditional
operator classification, genuine value-expression `|` remains semantic, and
the registered writer regenerates the artifact. Independent AST/token walks
agree on 2,603 scanned Python files, 115 candidates, and the complete role and
literal censuses; the writer and `--check` exit `0`, the eight focused
annotation/operator cases pass, and the whole 53-test posture module passes.
Its first declared 360-second ceiling was exceeded by 2.65 seconds (`real
362.65`, `user 276.00`, `sys 32.95`; uptime `12:05` to `12:11`), so that
timing declaration is retained as a disagreement and any replay uses the
measured 480-second ceiling.

The forward-merged seven-output generated-family census remains **5 changed / 2
unchanged** relative to the pre-merge DS15 head by both name-status and blob
comparison. OpenAPI, both TypeScript clients/types, and dashboard types changed;
both JavaScript clients did not. The landed decision-validity epoch-batch
operation is present in OpenAPI and type projections but has no generated
client method because the registered generator's POST allow-set does not name
that operation. This measured partial propagation is not silently treated as a
DS15 change; C03 must re-coordinate with DS18 and rerun the seven-output census
immediately before its registered generator transaction.

### C02 closure and registered-artifact ruling — 2026-08-28

C02 closes after the phase/terminal model is separated at the persisted
boundary. `AcquisitionRoutePhaseReceipt@1.0` can carry only `requested`,
`executing`, or `world_committed_reentry_pending`; the terminal sink accepts
only `AcquisitionRouteLoopReceipt@1.0`, emits the loop event type, and cannot
replace the durable pending head until re-entry returns. The behavioral
falsifier observes the pending head, phase artifact and phase event during the
re-entry callback, then observes the distinct terminal artifact and loop event
afterward. The complete focused C02 lane passes **44 tests** in `real 206.98`,
`user 197.70`, `sys 8.08` seconds (uptime `13:31` to `13:35`), and the unchanged
live-router/Rego set-equality falsifier exits `0` in `real 58.09`, `user 53.75`,
`sys 2.86` seconds (uptime `13:35` to `13:36`).

Two import-boundary derivations close without changing the frozen deep-import
baseline. The injected object remains Core's exported guarded `ArtifactStore`,
while `acquisition_route_loop.py` types only its exact three-method structural
read protocol; importing the facade directly created a new cross-root edge and
failed the generic predicate. For the Fabric edge, direct byte comparison proves
that `core.canon` is not substitutable: its typed float representation changes
both the canonical bytes and SHA-256 identities for the active admission
statement. Data Forge therefore exposes its existing float-aware receipt
validator through `data_forge.read_api.catalog`; runtime consumes that owner
verdict and the separately validated persisted projection instead of copying or
importing Fabric canonicalization. A receipt-body mutation with constant
published ref/hash fails at the owner seam, while a genuine active receipt and
same-case re-entry remain green.

The registered trust-posture writer is run under its published regeneration
command after the admitted-source coordinates move. Its AST/token inventories
agree on 2,603 Python files, 115 candidates and every role/literal count; the
generated payload digest is
`sha256:9141ecaebe24b32e975d283e620cf509b267f932904b5137606ff609ab4c6022`.
Architecture guardrails, including all three generated-family freshness checks,
exit `0` in `real 172.15`, `user 148.82`, `sys 21.51` seconds (uptime `13:27`
to `13:29`). These changes use only already-declared C01/C02 mechanism paths and
registered/P39 companions, so cumulative spend remains **23/40 mechanisms** and
**5/11 widening rounds**. C02 checks CC10 through CC16; C03-C06 remain open.

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
`government.balance` is independently re-established as data-shaped; the DS15
projection classifies 14 as `gap_class=not_established`, and none as structural.
That `gap_class` vocabulary is introduced by DS15; it is not a field emitted by
N13a or N13b. Current producer, rights, planner, mandate, decision, and execution
bindings must also resolve.

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
port, signed PA2 inputs and institutional semantic-epoch qualification owner
are currently missing. DS15 consumes those as typed external inputs; it does
not appoint them or modify N13b's write path.

The institutional qualification band has one source-level qualification. The
current production composition permits a candidate, passport and native overlay
row to reach `pending_epoch_activation`, then
`SemanticEpochService.finalize_admitted_epoch` invokes the deliberately
unallocated `QualificationConsumer`. Its `not_established` /
`policy_admission_missing` result returns before history append and before
`activate_semantic_epoch`; the production test pins zero activation calls, an
empty history and zero admitted observations. Therefore an **active but
institutionally unqualified epoch is not reachable in the consumed code**. It
would require changing the N13b/semantic-epoch write path, which this slice is
forbidden to do and which is absent from the 40-path declaration. DS15 instead
renders the real pending/unqualified state as a first-class typed disclosure,
names the unappointed policy-admission authority and says exactly what its
appointment would establish. It may never copy-upgrade that state to active or
institutionally qualified.

DS15 closes its bounded contract/consumer/surface mechanism after it renders
N13b's honest negative history and proves the admitted/re-entry consumer with a
conspicuously test-only behavioral fixture. The fixture may not be presented as
a production receipt. A fresh positive production route is a named external
non-closure, not an arithmetically impossible DS15 closure criterion: until its
owners emit a current non-fixture receipt, no surface, register or handoff may
claim that the production world grew.

Two independent derivations bind that qualification ruling. Derivation A walks
`admit_acquisition_with_semantic_epoch` end to end: pending overlay admission ->
`finalize_admitted_epoch` -> `_append_and_qualify` -> early non-qualified return
-> caller return before `activate_semantic_epoch`. Derivation B is the dedicated
production-path unit test: it expects `policy_admission_missing`, zero activation
calls, an empty history, one `pending_epoch_activation` row and zero admitted
observations. They agree; the earlier body-only reading stopped at the finalizer
call and missed its nested gate.

Opening capability states are:

| capability | measured opening state |
| --- | --- |
| N13a census and live-journal read projections | existing `producer + artifact + HTTP + partial Cycle Board consumer/surface + owner negative tests`; DS15's detailed scorecard/backlog/liveness consumer, surface and e2e semantics remain missing |
| recurring carrier liveness | typed persisted artifact consumed by N13b; `bridge_missing + surface_missing` for DS15 |
| actionable cost basis | current planner rates/default fallback are unversioned candidate behavior with no actionable owner ref; `producer_missing` until C01's planner-owned versioned schedule and no-fallback cost record are present in the verified compiled-run closure |
| persisted N13b audit history | 43 registered files include raw terminal evidence, aggregate quarantine facts and a re-entry trace, but no persisted `AdmissionPassport` instance, acquired snapshot or overlay epoch; one existing in-process loader validates the executor contract's global signal, while HTTP exposes only its source-manifest identity and not the signal value; the detailed family/per-row bridge, consumer and surface semantics remain missing |
| in-process passport/overlay capability | existing recomputed passport and overlay owner, with zero current admitted observations and zero epochs; `implemented_but_not_orchestrated + surface_missing` for DS15 |
| live acquisition command | N13b executor/passport/overlay/quarantine logic exists in process, but its only live function has no production caller, is World-Bank/local-filesystem-only, opens a fresh unguarded CAS from raw paths and lacks tenant context; the safe runtime producer handshake is `producer_missing`, then `implemented_but_not_orchestrated + surface_missing` |
| PA2 production dispatch | gateway behavior exists but production composition is test-only and guarded-store integration is missing; DS15 owns that engineering bridge. The gateway has no current mandate-owner appointment/revocation resolver, so that authority consumer is also missing. Opening state: `producer_missing + artifact_missing + consumer_missing + bridge_missing + implemented_but_not_orchestrated`; the signed v2 delegation artifact/authority evidence and deterministic admission-bundle producer are separate external inputs |
| semantic-epoch qualification | current adapter/consumer use explicitly unallocated policy authority; pending passport/overlay admission is reachable, but positive semantic production, history append and epoch activation fail closed as `not_established` / `policy_admission_missing`. The institutional owner is `absent/unallocated`, and the production wrapper has no appointed-evidence injection seam: `bridge_missing` |
| exact per-row acquisition-to-re-entry movement | `absent/unallocated` in the current Cycle Board (`GY-GAP6`); global N13b status cannot substitute |
| successful current world-growth demonstration | external non-closure `absent/unallocated`; no successor production-acquisition owner is appointed, and its prerequisites remain `producer_missing + bridge_missing + verification_missing`; admitted-observation and active-epoch denominators are both zero. This limits the production-growth claim but does not block closure of DS15's bounded surface mechanism |
| INT-R2 `GapAcquisitionCase` union | `absent/unallocated`; DS15 renders current typed refusals and does not invent the union |

## Canonical closure contract

DS15 closes only when every applicable item has a committed-branch receipt.
There is no second closure contract.

- [ ] **CC01** Attached branch, exact base, three gate ancestries, prefix,
      clean-tree predicate, complete path fences, and red witnesses are read
      before every cluster commit.
- [x] **CC02** The N13a three-output and N13b 43-output families, their logical
      payloads, and their HTTP/contract/in-process partition are derived twice
      and any disagreement is resolved before design changes.
- [x] **CC03** The 15 residuals are re-derived as `1 data-shaped / 0
      structural / 14 shape not_established`: `binding_gap` alone proves none
      of those classes. The separate capstone denominator remains `3 structural
      / 0 data-shaped`; the two sets cannot be joined by route ID or visual
      proximity. `gap_class` is explicitly a DS15 projection vocabulary, not an
      N13a/N13b source field.
- [x] **CC04** One strict acquisition-surface contract carries authority
      purpose, source/content hashes, rule/schema versions, source time,
      observed time, audience, and typed absence for every fact. The same
      packet carries the source-derived backlog score distribution and the
      epoch qualification disclosure; neither may be synthesized by UI copy.
- [ ] **CC05** Structural capstone routes render their owner witness and missing
      link with `action_eligibility=not_applicable`; adding catalog rows or a
      client-authored `live_fetchable` field cannot create a button.
- [ ] **CC06** The 15-row board is labelled “interim residual ordering — ranking
      only, not VOI,” carries `ranking_only_not_voi`, and discloses the complete
      current basis: `binding_confidence=0.0` on 15/15 rows,
      `ranking_score=0.0` on 15/15, and `route_demand=2.0` on 3/15 versus `1.0`
      on 12/15. Rank is therefore a deterministic route-demand/lexical tie-break,
      not a nonzero priority gradient. It also renders the uniform owner reason
      `metric_residual_granularity_not_supported`, integration
      `routed_to_gy_n13b`, and owner ref
      `polisyos.runtime.quality.acquisition_planner.plan_evidence_acquisition`.
      Numeric VOI is available only with a resolved owner decision/ranking
      reference and expected-value/cost inputs.
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
- [x] **CC10** An operational route is derived only from a tenant/cell/run/job-
      bound completed `natural_language_run` control-job closure, its exact
      content-verified `runtime.compiled_recursive_generation_cycle` artifact,
      `AcquisitionPlannerReport`, and content-bound costed-plan/basis inputs; a
      Core `RunManifest` or repository N13b artifact cannot substitute for that
      current producer closure.
- [x] **CC11** Acquisition approval reuses DS9's existing
      `agent_action_authority` PA2 arm and `HumanDecisionRecord`; DS15 adds no
      acquisition-specific decision source kind and no institutional
      appointment producer.
- [x] **CC12** Decision preparation and execution use existing
      `RuntimePermission.EVIDENCE_ACQUIRE`,
      `StepUpClass.ACQUISITION_APPROVAL`, DS9 human-decision step-up, exact
      resource binding, live re-resolution, and an idempotent sealed effect.
      The two acquisition GETs use existing `RuntimePermission.RUNS_REVIEW`
      with exact resource class `runtime.acquisition_route` and binding
      authority `tenant_collection`; neither a case-inspection nor run-paper
      resource kind can substitute.
- [x] **CC13** The effect consumes N13b's existing executor -> recomputed
      `AdmissionPassport` -> `CatalogAcquisitionOverlay`/Fabric quarantine chain
      only through the strict `AcquisitionExecutionPort` contract. A
      contract-conforming test double may satisfy bounded DS15 semantic proof
      and stays permanently fixture-badged; only the separately owned
      `fresh_positive_production_route` requires an owner-supplied tenant-bound
      port over the real guarded CAS/journal context. Raw
      `journal_path`/`cas_root` invocation is refused in both lanes. No second
      journal, quarantine store, overlay table, passport, epoch allocator, or
      world write path exists.
- [x] **CC14** A fetched response without a complete recomputed passport is
      quarantined; an admitted passport without matching active overlay and
      production receipts cannot emit world growth. A pending epoch with
      qualification `not_established` remains pending and visibly discloses
      `policy_admission_missing`; copy cannot call it active or qualified.
- [x] **CC15** `world_growth=grew` requires a matching active overlay epoch and
      positive admitted-observation delta. `reentry=advanced` or
      `deeper_terminal` additionally requires the same run, case/design problem,
      requirement gap, execution receipt, and post-epoch re-entry trace.
- [x] **CC16** Historical selection, expired rule/epoch, changed planner hash,
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
- [x] **CC21** No held DS11 path is touched before its landing ancestry and
      complete-prefix path census agree; backend clusters can land first, but the
      generated family waits because it includes one dashboard file.
- [ ] **CC22** Every cluster's named red-first behavioral falsifier fails for the
      intended missing property, then passes without weakening its mutation
      probe or laundering fixture identity.
- [ ] **CC23** Slice-owned visual, responsive, keyboard, screen-reader, focus,
      and rendered-DOM/MACHINE parity receipts cover structural refusal,
      all-zero ranking basis, quarantine/no-growth, pending/unqualified
      disclosure, and an admitted/re-entry test mechanism.
- [ ] **CC24** DS15 proves the bounded surface mechanism in two honest lanes. The
      production lane renders the real historical `government.balance` chain as
      quarantine/no-growth/deeper-terminal and renders any current
      `policy_admission_missing` receipt as pending/unqualified, never active.
      The semantic-test lane visibly completes blocked reason -> cost -> PA2/DS9
      approval -> execution -> admitted passport -> active overlay epoch ->
      positive admitted delta -> exact same-case re-entry through the strict
      owner-port contract, with a permanent `behavioral_fixture_not_production`
      authority badge. A fixture, historical ID or resurrected capstone
      hypothesis cannot satisfy or be projected as a production-growth receipt.
      Any future non-fixture production claim is governed by the separately
      owned `fresh_positive_production_route` non-closure, not by this bounded
      criterion.
- [ ] **CC25** Freeze -> review -> one expensive verification wave -> register
      transition -> committed-branch readback proves the bounded capability
      chain, including CC24's source-honest production-negative lane and
      explicitly badged semantic-test lane. DS15 may close that bounded scope
      while `fresh_positive_production_route` remains `absent/unallocated`,
      with its producer/bridge/verification prerequisites unresolved, but no
      register or surface may claim successful production world growth until an
      owner is appointed and the external receipt lands.

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
| backlog score basis | complete 15-row `growth_backlog` grouping over `binding_confidence`, `ranking_score` and `route_demand` | recompute all 15 rows from `reverse_demand_residuals.best_binding_confidence`, complete `demand_sources` cardinality and `derive_growth_backlog`'s score/sort formula, then require equality with the stored backlog | confidence `0.0`: 15/15; score `0.0`: 15/15; demand `2.0`: 3/15, `1.0`: 12/15 |
| backlog VOI-owner boundary | complete 15-row grouping over `voi_owner_fit`, `voi_owner_integration` and `voi_owner_ref` | recompute all rows through `derive_growth_backlog` and validate the strict literal fields before comparing with the stored backlog | all 15: fit `metric_residual_granularity_not_supported`; integration `routed_to_gy_n13b`; ref `polisyos.runtime.quality.acquisition_planner.plan_evidence_acquisition` |
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

At execution base `f3e3d996bd6710e26f24fd913d4fe0547f1d1a0d`, `gap_class`
has zero occurrences in the complete 2,811-file tracked `src/` denominator by
both an `rg --files` plus content scan and an independent `git ls-files` plus
`git grep` scan (2,601 Python, 5 Python stubs, 10 JSON, 11 YAML, 164 Markdown,
15 CSV, 2 Cypher, 2 `typed`, and 1 SQL file). The two path sets are identical.
C01 intentionally changes that execution-entry zero by defining the strict
enum in `acquisition_surface_contracts.py`; only
`acquisition_surface_projection.py` produces `data_gap`, `structural_gap` or
`not_established` after independently reconciling owner evidence. N13a's
`binding_gap`, backlog rank/score, and client input never populate it.

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

### Producer and authority bands before production-positive execution

Five current producer/authority gaps are binding, not implementation trivia:

1. `execute_live_catalog_acquisition` has no production caller, accepts raw
   `journal_path`/`cas_root`, constructs a fresh unguarded `FileSystemCAS`
   without tenant context, and supports only `worldbank.wdi`. DS15 will consume
   only an N13b-owner production `AcquisitionExecutionPort` that proves the same
   guarded CAS/journal/tenant/run and reuses the existing passport/overlay/
   quarantine logic. The port's owner lands outside this slice; DS15 never wraps
   the raw-path function with a second scratch/write path.
2. `AgentActionAuthorityGateway` is composed only in tests today and its
   exact-`FileSystemCAS` constructor does not accept the runtime's guarded
   artifact-store boundary. Generalizing the consumer to the verified
   ArtifactStore protocol, installing it in control composition, registering
   exact effects and loading durable decisions are C02-owned engineering work:
   `implemented_but_not_orchestrated + bridge_missing`.
3. the PA2 inputs split into two external producer bands rather than one vague
   “signed producer” blocker. A persisted signed v2 `DelegationContract` and
   resource-to-contract-head mapping are `producer_missing + artifact_missing`;
   its `mandate_owner_ref` and matching signature are institutional inputs, and
   signature equality alone does not establish a current appointment or
   revocation state. The `AgentActionAdmissionBundle` is different: it requires
   governed deterministic-producer authority, current run/job binding and a
   signed invocation-hash-to-CAS mapping; its absent production emitter is an
   engineering/deployment producer gap, not an unappointed human. C02 will
   verify and consume both bands and may prove refusal/allow behavior with typed
   test doubles, but it does not manufacture either real signed artifact. Because the
   current gateway has no appointment/currentness/revocation resolver, C02 owns
   a narrow fail-closed mandate-authority consumer/bridge; the external human
   appointment remains out of scope and `not_established` until that consumer
   resolves owner evidence.
4. the semantic-epoch qualification adapter and consumer explicitly use
   unallocated policy authority. Pending passport/overlay admission is committed
   first, but finalization returns `not_established` /
   `policy_admission_missing` before native-history append and before overlay
   activation. The production wrapper hard-codes both unallocated constructors,
   so an appointed receipt has no injection seam. The institutional appointment
   and composition replacement remain `absent/unallocated + bridge_missing` and
   out of scope; DS15 renders the typed pending-state disclosure. A successor
   owner must both supply authority and wire/replace that production composition
   before any qualified/active claim.
5. the current N7 requirement-gap route carries no independent numeric cost
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

The PA2 split is also dual-derived. The contract/gateway derivation follows each
strict resolver: gateway installation and guarded store are engineering;
delegation resolution demands a persisted signed v2 contract whose signer
matches `mandate_owner_ref`; admission resolution demands a governed
deterministic-producer bundle bound to invocation/run/job. The independent
construction-site census finds the gateway and bundle composed only in tests,
the existing delegation builder unable to emit the required signed action
envelopes/current mandate authority, and no production admission-bundle emitter.
The derivations agree on three bands and disagree with any single “unappointed
human producer” label.

C01 may land while the external bands remain absent. C02 owns and closes the
gateway/control engineering composition and may verify fail-closed consumers,
receipt persistence and a fake-port behavioral harness. Real external effects
and active production epochs remain `producer_missing + bridge_missing`, and the
`fresh_positive_production_route` claim remains `absent/unallocated`; their
absence does not block the bounded DS15 mechanism or authorize an institutional
appointment, raw local-filesystem call, signature
substitute, or fixture badge removal.

## Design rulings

### 1. Facets, not one optimistic status

The canonical packet keeps these independent strict facets:

| facet | values / rule |
| --- | --- |
| `gap_class` | DS15 projection enum `data_gap`, `structural_gap`, or `not_established`; the server derives it from independently reconciled owner evidence, never from `binding_gap`, rank/score or client input |
| `plan` | requirement, planner status, eligible/ineligible strategies, next action, cost and VOI facts with refs |
| `cost_basis` | `established`, `missing`, `invalid`, `default_zero`, or `revalidation_required`; only `established` can enable review/execute after server recomputation from content-bound basis/rate inputs; an explicit owner-produced zero may be established, an absent/default zero may not |
| `action_eligibility` | `not_applicable`, `producer_missing`, `revalidation_required`, `blocked`, `decision_required`, `executable` |
| `decision_gate` | the existing DS9 precedence: invalid -> artifact missing -> producer missing -> revalidation -> blocked -> available |
| `execution_phase` | coarse surface state `not_started`, `requested`, `executing`, or `terminal`; every non-initial value carries an exact receipt/event ref |
| `receipt_phase` / `recovery_state` | owner detail is `requested`, `executing_acquisition`, `world_committed_reentry_pending`, `reentering`, or `terminal`, plus `none`, `receipt_recovery_required`, or `reentry_recovery_required`; the server maps requested -> requested, all nonterminal execution/recovery detail -> executing, and terminal -> terminal |
| `admission` | `not_reached`, `not_established`, passport `quarantined`, `admitted`, or `admitted_degraded`; no UI derivation |
| `epoch_qualification` | `not_reached`, `not_established`, or `qualified`, plus exact code, authority role/ref, owner appointment state and `appointment_would_establish`; `not_established/policy_admission_missing` binds a pending epoch and cannot be copied into active/qualified |
| `quarantine` | `none`, `raw_terminal`, or `passport_refused`, with exact Fabric refs; this records ledger/effect disposition separately from the passport's admission status |
| `world_growth` | `not_established`, `no_growth`, or `grew`; `grew` requires active epoch + positive admitted delta |
| `reentry` | `not_established`, `pending`, `advanced`, or `deeper_terminal`; exact same-case binding required |

For the current production composition, the strict qualification block is:
`epoch_state=pending_epoch_activation`, `status=not_established`,
`code=policy_admission_missing`, `authority_role=semantic epoch policy-admission
qualifier`, `authority_owner_ref=null`, `appointment_state=unappointed`, and
`appointment_would_establish=authority to qualify native semantic production,
append its history head and permit overlay activation`. It explicitly says that
appointment would **not** establish gap shape, passport validity, positive
delta or re-entry. A later `qualified` block requires a content-bound owner
receipt; localized prose is projection of this block and carries no upgrade
authority.

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
| PA2 delegation/admission | `independently_reconciled` only after C02's mandate-authority consumer resolves external evidence; current authority is `not_established` | gateway resolves the signed v2 contract, separately resolves current mandate-owner appointment/revocation evidence, and admits the deterministic bundle; signature equality, caller assertions or absent producers are `not_established` |
| passport disposition | `recomputed` | N13b owner recomputes every decisive check; marker/status presence is `not_established` |
| epoch qualification | `independently_reconciled` only after an external owner and production bridge exist; current label `not_established` | qualification receipt resolves status/code, appointed authority and source/content identity through the owner-wired production consumer; the hard-coded unallocated composition or absent owner is frozen as `not_established/policy_admission_missing`, never upgraded by copy |
| active world epoch | `independently_reconciled` | qualified production, native-history and active overlay owner receipts bind one epoch; pending admission alone is `not_established` |
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
`interim_binding_confidence_x_route_demand`. They also all carry
`binding_confidence=0.0` and `ranking_score=0.0`; only route demand partitions
the rows (`2.0` on 3, `1.0` on 12), after which the producer falls through to
lexical `variable_id` tie-breaking. The board title is **Interim residual
ordering — ranking only, not VOI**. It shows the complete zero-score basis,
method, owner boundary, raw ordinal and reason, and states both “no nonzero
priority gradient” and “VOI not established.” It does not use “highest value,”
currency, expected benefit, or VOI colors.

The stronger owner disclosure is first-class on every row and summarized on the
board: `voi_owner_fit=metric_residual_granularity_not_supported`,
`voi_owner_integration=routed_to_gy_n13b`, and
`voi_owner_ref=polisyos.runtime.quality.acquisition_planner.plan_evidence_acquisition`.
This is not a generic missing-value message; it names the owner and the exact
granularity limitation.

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
  -> institutional qualification + native-history append
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

The bounded DS15 closure demonstration has no undiscovered real-route premise.
It renders the complete current/historical owner truth, then drives a strictly
badged behavioral fixture through the same consumer/port contract to prove the
continuous visible motion. It is not pinned to `government.balance`, CPI, a
backlog rank, or any historical identifier as production authority. If the
fresh set has no eligible route, or every honest production attempt ends in
quarantine/no-growth/pending qualification, DS15 renders that result and may
still close its bounded surface mechanism; the executor may not loosen
admission, remove the fixture badge or revive a stale hypothesis to obtain a
green production claim.

A later fresh positive receipt is accepted only from the freshly resolved set:
one current data-shaped real case, owner-produced cost, the same admitted
authority chain, active qualified epoch, positive admitted delta and exact
same-case return. Shape establishment across the other 14 residuals is not a
DS15 cluster: the denominator is 14 and an honest investigation may establish
zero. That owner-grade discovery is recorded as
`fresh_positive_production_route`, currently `absent/unallocated` because no
successor N13b production-acquisition/data-gap owner has been appointed. Its
eventual owner must close the producer/bridge/verification gaps before such a
receipt exists.

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
| `DS15-ZERO-SCORE-DISCLOSURE` | with the real 15 row IDs and order held constant, remove/obscure the confidence `0.0` and score `0.0` on 15/15 or the 3/12 demand split; separately mutate one complete residual's owner evidence coherently and recompute the backlog through `derive_growth_backlog`, accepting its resulting order | the unchanged real packet must visibly say its ordinals carry no nonzero score gradient; the producer-valid mutation derives 14/15 zero rather than retaining hard-coded copy, and neither packet becomes VOI |
| `DS15-COST-BASIS` | retain an expected-cost field while removing/changing its named schedule row, basis ref, rates, rule/hash provenance or line-item equality; leave the legacy unknown-gap fallback present and also try caller zero/default | cost becomes typed unavailable/invalid and decision request/execute stay blocked; the legacy fallback never establishes actionability |
| `DS15-PA2-AUTHORITY-BANDS` | keep approval/signature markers while independently removing gateway composition, the signed v2 contract/current mandate-owner authority, or the deterministic admission-bundle producer | engineering composition absence blocks the DS15 bridge; either external input absence keeps real execution `producer_missing`; signature equality cannot stand in for appointment |
| `DS15-QUALIFICATION-DISCLOSURE` | keep the pending passport/epoch row and `policy_admission_missing`, but drop the authority owner/appointment effect, label it active/qualified, or replace the typed status with reassuring copy | contract/UI/parity test fails; the row remains pending with `not_established`, names the unappointed policy-admission authority, and states that appointment would establish native semantic production/history eligibility |
| `DS15-DEFERRED-PA2` | persist an allowed-looking marker but remove/tamper the durable decision, cross-bind its tenant/run/source-job/route/effect, or invoke the port without gateway load + `execute_bound_effect` | no external effect; job fails closed before the port and the action head records no executing receipt |
| `DS15-GET-RESOURCE-EXACTNESS` | keep the same role and `runs.review` permission but substitute `runtime.case_inspection.tenant_collection`, `runtime.run_paper.tenant_collection`, or another proxy kind for either acquisition GET | Rego denies before projection; only exact `runtime.acquisition_route.tenant_collection` is admitted |
| `DS15-EXECUTION-PORT` | offer raw journal/CAS paths, a wrong connector, unguarded store, tenantless port or arbitrary data-shaped row | producer handshake refuses before network/world write |
| `DS15-PASSPORT-BOUNDARY` | keep raw bytes and passport marker fields but remove one decisive schema/units/alignment/license/PII/trust check | recomputed passport refuses; quarantine renders; world delta stays zero |
| `DS15-EPOCH-ACTIVATION` | create an admitted-looking passport without matching qualification, native-history, production and active overlay receipts | no world-growth event; action fails closed |
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

The complete declaration contains **40 unique mechanism paths**. The hard slice
ceiling is exactly **40**, derived from that declared union; there is no padded
contingency. Path 41 is a stop and plan-amendment request. A path may narrow
away, but an undeclared replacement or companion promoted into mechanism work
requires the same amendment and a fresh union derivation.

This amendment chooses the satisfiable CC24 restatement, not a new 14-residual
shape-establishment cluster. Qualification/zero-score disclosures remain inside
C01/C04's declared paths, and `gap_class` ownership is a clarification of C01's
existing contracts/projection. C00 additionally proved that the new governed
projection ID must register an owner validator in the existing validation
worker. That measured prerequisite adds one C01 mechanism, taking the parser
union from 37 to 38. C00 review then proved that the closed Rego action contract
needs one exact acquisition-route resource class for the existing `runs.review`
permission. Adding that existing policy owner as one C02 mechanism takes the
union to 39 while adding no permission enum, capability, writer, or widening
round. C02's measured R05 registry boundary then adds the one exact diagnostic
event-registry owner path and takes the union to **40**; a generic CAS-write
event cannot substitute for the planned acquisition phase/loop types.

Two independent cap derivations must agree before C01 and closeout:

1. cluster arithmetic `7 + 16 + 12 + 4 + 1 = 40`; and
2. a parser union of every bold `Add/Modify (mechanism)` path below, excluding
   P39 companions, with known members
   `src/polisyos/runtime/quality/acquisition_route_loop.py` and
   `apps/runtime-dashboard/src/features/runs/components/AcquisitionGrowthBacklog.tsx`.

The widening budget is **11 repair rounds**, one for each concrete predicate
class below. A round may repair or redistribute work only within the declared
40-path set; it does not buy another path. Narrowing that only removes a way to
be fooled is free. A second finding in one class invokes P40: widen the property
to the quantity it needs inside the ceiling, or declare the bounded residual
and run its falsifier. A new capability, permission, producer arm, writer or
undeclared path is a plan amendment, not a round.

| cluster | property | declared mechanisms | ceiling | widening rounds |
| --- | --- | ---: | ---: | ---: |
| C00 | admit plan, remeasure sets/fences and pin reds | 0 | 0 | 0 |
| C01 | strict owner cost/read contracts over N13a/N13b, overlay and quarantine | 7 | 7 | 2 |
| C02 | run-bound HTTP, PA2 decision request, durable worker and exact re-entry receipt | 16 | 16 | 4 |
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
| R07 | C04 | global structural/ranking truth | add rows/cost labels, hide the all-zero basis or rename interim ordering as VOI |
| R08 | C04 | route-detail facet identity | join global status, lose a receipt/qualification ref, copy-upgrade pending to active, or synthesize a mixed facet client-side |
| R09 | C05 | online accountable action | replay stale approval or queue/execute offline |
| R10 | C05 | continuous motion and exact-byte parity | mutate captured bytes, timeline order, focus or live-region transition |
| R11 | C06 | evidence-backed disposition transition | remove visual/semantic/CC24 bounded-scope evidence while retaining ready/closed markers or add an unsupported production-growth claim |

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

**Add/Modify (mechanism, 7 paths):**

- modify `src/polisyos/runtime/quality/acquisition_planner.py`;
- add `src/polisyos/runtime/http/services/acquisition_surface_contracts.py`;
- add `src/polisyos/runtime/http/services/acquisition_surface_projection.py`;
- modify `src/polisyos/runtime/http/services/governed_projections.py`;
- modify
  `src/polisyos/runtime/http/services/governed_projection_validation_worker.py`;
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
`acquisition_surface_contracts.py` owns the new `gap_class` enum, complete
backlog score/VOI-owner summary and typed epoch-qualification disclosure;
`acquisition_surface_projection.py` derives each from all owner rows/receipts.
Neither contract nor projection claims that N13a emits `gap_class`.
The validation worker registers the single `acquisition-growth` projection with
an owner validator over the complete C01 source family; enum/definition markers
without that registration remain `owner_validator_unregistered`. DS15 adds no
separate carrier-liveness or N13b projection ID.
It does not expose raw quarantined payload bytes, rerun a live probe, execute a
FetchPlan, or write an overlay receipt.

**P39 tests, exact set:** add
`tests/unit/runtime/http/test_acquisition_surface_projection.py` and
`tests/repo_quality/tools/test_ds15_acquisition_surface_strangle.py`; modify
`tests/unit/runtime/http/test_governed_projection_service.py`,
`tests/unit/runtime/http/test_governed_projection_api.py`, and
`tests/unit/runtime/http/test_governed_projection_validation_worker.py`,
`tests/unit/data_forge/domains/catalog/knowledge/test_overlay.py`, plus
`tests/unit/runtime/quality/test_acquisition_planner.py`; modify the mandatory
nearest-parent companion
`src/polisyos/runtime/http/services/README.md`. N13a/N13b
repository-quality tests, artifacts, journals and write-path owner tests remain
byte-identical; DS15 consumer/strangle tests import their public seams.

**Named reds:** `DS15-STRUCTURAL-NOT-DATA`, `DS15-BINDING-NOT-DATA`,
`DS15-RANKING-NOT-VOI`, `DS15-ZERO-SCORE-DISCLOSURE`,
`DS15-QUALIFICATION-DISCLOSURE`, `DS15-COST-BASIS`,
`DS15-N13B-NEGATIVE-HONESTY`, and the
remove-property/keep-marker passport and active-epoch mutations.

**Acceptance:** strict global packet renders 12/18/144/124/15/3 and N13b
5 attempts/2 raw responses/0 admissions/0 epochs from owner facts; structural
and data denominators remain separate;
the DS15-owned `gap_class` provenance is explicit; both complete source scans
are rerun and report the post-C01 denominator/occurrence set, prove the sole enum
definition lives in the strict C01 contract, and prove all server producers
route through `acquisition_surface_projection.py`; the strict global packet
contains confidence/score zero on 15/15, the 3/12 demand split and all three
uniform VOI-owner limitation fields; pending qualification contains exact
status/code/owner/appointment effect; ranking-only is unambiguous; a run route
has a cost only from the new verified
planner record and cost drift blocks; no read opens a writer transaction or
changes overlay/quarantine bytes.

### C02 - run-bound action and one world-growth bridge

**Add/Modify (mechanism, 16 paths):**

- add `src/polisyos/runtime/quality/acquisition_route_loop.py`;
- modify `src/polisyos/runtime/quality/generation_cycle.py`;
- modify `src/polisyos/runtime/quality/agent_action_authority.py` to admit the
  guarded ArtifactStore protocol with equivalent CAS/signature checks and add
  a fail-closed current mandate-owner authority resolver, plus the gateway-owned
  deferred reservation/durable decision loader that delegates the eventual
  effect to existing `execute_bound_effect`;
- add `src/polisyos/runtime/http/services/acquisition_action_service.py`;
- modify `src/polisyos/runtime/http/services/control/run_lifecycle.py`;
- modify `src/polisyos/runtime/http/services/control_plane_store.py`;
- modify `architecture/production_quality/diagnostic_event_types.toml` only to
  register the exact acquisition route phase and loop event types;
- modify `src/polisyos/runtime/http/services/_control_contracts.py`;
- modify `src/polisyos/core/contracts/control.py` for the canonical
  `ControlJobKind` literal;
- add `src/polisyos/runtime/http/routes/acquisitions.py`;
- modify `src/polisyos/runtime/http/app.py`;
- modify `src/polisyos/runtime/http/routes/__init__.py`;
- modify `src/polisyos/runtime/http/container.py`;
- modify `src/polisyos/runtime/http/dependencies.py`;
- modify `src/polisyos/runtime/http/openapi_contract.py`; and
- modify `ops/policy/policies/action_permission.rego` only to add the exact
  acquisition-route GET resource contract under existing `runs.review`.

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

No new permission enum is added. Both GETs use the exact pair
`RUNS_REVIEW` / `runtime.acquisition_route.tenant_collection`. Decision request
and execute keep the exact pair `EVIDENCE_ACQUIRE` /
`runtime.evidence.acquisition.request_bound` plus acquisition step-up; the human
record remains on DS9's route/permission/step-up. The Rego action-contract map
and runtime route requirements must agree byte-for-semantics: preserving a role
and permission while substituting case-inspection, run-paper, or another proxy
resource kind remains denied before projection.
VIEWER/SERVICE/SYSTEM cannot perform the human act. The operation is
idempotent on tenant/run/source-job/route/planner/decision hashes and fails closed on
partial audit, CAS, passport, production or re-entry persistence. Missing
gateway composition keeps the DS15 bridge unavailable; a missing signed v2
delegation contract/current mandate-owner authority, deterministic signed
admission bundle or owner execution port independently keeps real execution
`producer_missing`; the hard-coded unallocated qualification composition keeps
epoch activation `bridge_missing` even if a receipt is merely supplied. A fake
port or signed-input double is test authority only.

C02's mandate-authority resolver is a consumer/integration contract, never an
appointment producer. It resolves content-bound external evidence for the exact
`mandate_owner_ref`, authority purpose, current/effective/revoked state,
schema/rule version and signer provenance independently of the delegation
signature. Missing, stale, mismatched or merely signer-equal evidence freezes
the predicate as `not_established` and prevents a real allowed effect.

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
The already-declared API-contract-hardening parity and authorization-access
audit paths own the GET resource-binding red; no additional authorization test
path is introduced. Existing Rego/router parity tests remain baseline receipts
and prove that the closed policy map must equal the live guarded router.
Modify the mandatory nearest-parent P39 companions
`src/polisyos/runtime/http/services/README.md`,
`src/polisyos/runtime/quality/README.md`, and
`src/polisyos/runtime/http/routes/README.md` for C02's new modules and entry
points. The services README is intentionally shared with C01 and remains one
unique companion path in the slice union.
Existing human-decision, acquisition-executor, overlay-visibility and N13b
owner tests are baseline receipts, not DS15 edit targets.

**Named reds:** `DS15-NO-STALE-REVIVAL`, `DS15-COST-BASIS`,
`DS15-PA2-AUTHORITY-BANDS`, `DS15-DEFERRED-PA2`,
`DS15-GET-RESOURCE-EXACTNESS`,
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
diagnostic-event refs disagree; the gateway cannot fail closed over the
guarded store; or re-entry cannot consume an already-active catalog overlay
without editing `fabric/world/` or `data_state_substrate.py`, keep the owned
bridge `producer_missing`/`bridge_missing`. Absence of the signed external PA2,
qualification owner/composition or N13b-port inputs is not a stop for the
bounded mechanism: it is the typed production-negative state and external
non-closure. Do not build a
case-data index, scan CAS, call the raw-path executor, create a second world
writer, or use a repository artifact as authorization. The narrow control-store
route/action head declared above is an action discoverability pointer, not
case/world data.

**Acceptance:** a fake-port test route exercises decision request -> DS9 record
-> sealed worker -> quarantine/no-growth, and one admitted behavioral fixture
exercises phase receipts -> real passport/overlay activation -> crash-safe exact
same-case re-entry -> terminal receipt. Missing production inputs remain visibly
`producer_missing`; the fixture carries `behavioral_fixture_not_production`, and
signer equality without resolved current mandate authority remains
`not_established`; N13b history remains its real negative. These receipts admit the fail-closed
bounded mechanism into C06 review. A fresh non-fixture positive receipt remains
the separately owned production-growth non-closure.

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
`apps/runtime-dashboard/src/api/types.ts`; add structured release companion
`release-fragments/unreleased/2026-08-27-ds15-acquisition-routes.toml` with the
required surface classification, compatibility and migration notes. Generate
from runtime HTTP source,
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
typed states. The backlog renders the source-derived all-zero score basis,
route-demand split and named VOI-owner granularity refusal; it never relies on
ordinal alone. Passport/epoch detail renders qualification status/code,
unappointed authority and appointment effect beside the pending/active state.
Tier decay and quarantine are as prominent as any positive.

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
structural sufficiency nor route status; `DS15-ZERO-SCORE-DISCLOSURE` preserves
the real IDs/order while testing disclosure removal, then derives the 15/15
versus 14/15 basis from a producer-valid recomputation whose order may change;
ranking-only never renders VOI;
local sort shows override; `DS15-QUALIFICATION-DISCLOSURE` prevents pending/
unqualified copy from becoming active/qualified; tier decay cannot render
healthy; raw response without passport renders quarantine; global N13b status
creates no row movement.

**Acceptance:** REVIEWER/EXPERT see the complete owner truth; MACHINE export and
DOM agree on gap-class provenance, zero-score/demand/VOI-owner disclosure and
qualification state; the board can grow data-only from a new valid row; a
structural row cannot become acquirable through frontend code or extra rows.

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
terminal without page or context loss, and keeps its
`behavioral_fixture_not_production` badge throughout. A pending production epoch
shows `not_established/policy_admission_missing`, the unappointed authority and
what appointment would establish without being relabelled active. A missing,
default-zero or unverified cost stops before review. Structural and
historical-only rows have no active flow.

### C06 - freeze, verify and close

**Add/Modify (mechanism, 1 path):**

- modify `architecture/atlas_surfaces/check_frontend_disposition_register.py`
  only if the existing generic checker cannot adjudicate DS15's real new
  operations/surfaces.
If no checker code is needed, the actual mechanism count narrows to 38.

Freeze source, run architecture/backend/frontend review in parallel, batch only
blocking findings, then run the expensive wave once. Before acquiring the Atlas
lock, execute exactly one snapshot-writer visual run followed by two no-writer
runs, Chromium, one worker, zero retries, slice grep only. Verify keyboard
order, focus return, 200% zoom, mobile, dark/light, axe, live-region updates,
reduced motion, snapshot stability and CC24's honest production-negative plus
badged behavioral receipts. Delta-only rereview follows any blocking repair.

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

Re-derive 40 declared/40 ceiling and actual mechanism paths twice; re-derive all
set counts, including both post-C01 `gap_class` source-tree scans and the single
definition/producer-routing invariant; classify every red under P41 against the
slice base; read the final file set, branch and commits from the committed
branch.

**Acceptance:** every CC has its required receipt; target chain is contract ->
producer -> persisted planner/execution artifact -> PA2/DS9 bridge -> N13b
passport/overlay/quarantine -> same-case re-entry -> HTTP -> UI/MACHINE ->
negative/e2e semantic test. CC24 proves complete continuous motion with an
explicitly test-only authority badge while the production lane renders the real
negative/pending states. If the fresh non-fixture receipt is absent, record
`fresh_positive_production_route` as `absent/unallocated`, with its exact
producer/bridge/verification prerequisites, and make no production-growth
claim; that external non-closure does not prevent the bounded C06 transition.

## Declared mechanism file map

| owner family | paths | count |
| --- | --- | ---: |
| owner cost/read contracts/projections | `acquisition_planner.py`, `acquisition_surface_contracts.py`, `acquisition_surface_projection.py`, `governed_projections.py`, `governed_projection_validation_worker.py`, catalog `overlay.py`, catalog read API | 7 |
| action/HTTP bridge | `acquisition_route_loop.py`, `generation_cycle.py`, `agent_action_authority.py`, `acquisition_action_service.py`, control lifecycle/store/contracts, diagnostic event registry, canonical `ControlJobKind`, acquisition routes, app/router/container/dependencies/OpenAPI contract, exact Rego action contract | 16 |
| dashboard reads | hook, presentation, five read components, Cycle Board, query keys, validators, two locales | 12 |
| dashboard action/MACHINE | timeline, approval flow, export, Case Workspace | 4 |
| Atlas checker | disposition checker, conditionally narrowed away | 1 |
| **total** | parser union must match | **40** |

Mandatory P39 generated client family is seven files: one OpenAPI schema, five
runtime-client files, and one dashboard types file. The three exact README
companions and the C03 structured release fragment are mandatory records too.
Tests, plan/journal, register/report and the complete slice snapshot root are
outside mechanism caps, but only the exact sets declared in C00-C06 are
authorized.

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
| `DS15-PA2-COMPOSITION-MISSING` | DS15-owned guarded gateway/control bridge absent; no DS15 execute path |
| `DS15-DELEGATION-AUTHORITY-MISSING` | no signed v2 delegation artifact/current mandate-owner authority, or C02 authority resolver cannot admit it; signature equality alone is insufficient |
| `DS15-ADMISSION-BUNDLE-PRODUCER-MISSING` | governed deterministic admission-bundle emitter/mapping absent; this is not a human appointment |
| `DS15-EPOCH-QUALIFICATION-NOT-ESTABLISHED` | pending epoch is `policy_admission_missing`; authority is `absent/unallocated` and its production consumer is `bridge_missing`; render the appointment/composition effect, never active/qualified |
| `DS15-ROUTE-REVALIDATION-REQUIRED` | historical/current hash, rule, epoch, availability, rights or mandate differs |
| `DS15-RANKING-ONLY-NOT-VOI` | display interim residual ordering, all-zero score basis and named owner granularity refusal; VOI unavailable |
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
| `DS15-POSITIVE-RECEIPT-MISSING` | successor owner is `absent/unallocated` and producer/bridge/verification receipts are not established; bounded DS15 may close, but production world growth remains an explicit non-closure and cannot be claimed |

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
| P39 | count plans/tests/generated/register/snapshots as mechanisms | 40 declared mechanisms, exact 40 hard ceiling, companions explicit |
| P40/P41 | patch the second escape or inherit a red from a nearer base | bucket second finding; exact slice-base replay and complete-input disjointness |

Target bounded closure is `typed contract/artifact + owned producer + persisted
planner/execution/event + fail-closed PA2/DS9 orchestration bridge + N13b
passport/overlay/quarantine consumer + HTTP/UI/MACHINE surface + negative/e2e
semantic test + source-honest historical/pending projection + permanently
badged continuous-motion fixture`. The separate production-growth claim remains
`absent/unallocated`, with producer/bridge/verification gaps, until an owner is
appointed and a real admitted acquisition
reaches a qualified active epoch with a positive admitted delta and same-case
re-entry through the safe production port and signed external inputs. That
claim limitation must stay visible, but it is not an undiscoverable predicate
on bounded DS15 closure.

## Opening non-closures and stop states

| non-closure | precise state / boundary | closure signal |
| --- | --- | --- |
| `fresh_positive_production_route` | external claim non-closure `absent/unallocated`; no successor lane or accountable owner is appointed. N13b truth is 0 admitted, 0 epochs, no growth. The residual candidate denominator is 1 historical data-shaped (`government.balance`) + 14 shape `not_established`; the separate 3-row capstone denominator is structural and non-row-addressable | owner: **unallocated**; a future allocation must name the N13b production-acquisition/data-gap producer, then close the safe-port, signed-PA2, qualification-composition and receipt-verification gaps. Closure signal is a current independently re-established data-shaped route, qualified active epoch, positive delta and exact same-case re-entry. Bounded DS15 may close without it; production growth may not be claimed |
| current `government.balance` acquisition button | `revalidation_required`/deeper connector-contract terminal; historical source-profile mismatch cannot authorize | fresh planner/rights/route resolution after `source_selector:11` or another honest producer route is current |
| actionable acquisition cost | `producer_missing`; current unversioned hard-coded/default cost path has no actionable owner ref | planner-owned `PlannerAcquisitionCostSchedule@1.0` exact named row + content-bound cost record in a verified completed control-job/compiled-run closure; unknown-gap fallback remains ineligible |
| production N13b execution handshake | `producer_missing`; raw-path local-filesystem World Bank function is in-process, not a guarded tenant-bound port | N13b owner exposes a typed production port over the same journal/CAS/passport/overlay/quarantine spine; DS15 changes no write path |
| PA2 gateway/control composition | DS15-owned `implemented_but_not_orchestrated + bridge_missing`; gateway is test-composed | C02 composes the guarded-store-compatible gateway, exact effects and durable decision loader; this engineering band is a bounded-closure obligation |
| signed v2 delegation + mandate-owner authority | external `producer_missing + artifact_missing`; current builder emits no signed action envelopes, and the opening gateway is `consumer_missing + bridge_missing` for appointment/currentness/revocation because signer equality is its only owner check | C02 closes only the strict authority-consumer bridge; a deployment/DS9 successor owner must still supply the content-bound contract/head mapping plus typed current mandate-owner authority. DS15 never appoints the human owner |
| deterministic admission-bundle producer | external `producer_missing + artifact_missing + bridge_missing`; no governed current run/job invocation-hash emitter exists | runtime/deployment owner emits and signs the governed `AgentActionAdmissionBundle` plus mapping; this is an engineering producer, not an unappointed human |
| semantic-epoch qualification authority | institutional owner `absent/unallocated` and production consumer `bridge_missing`; the wrapper hard-codes unallocated consumer/adapter constructors. Pending passport/overlay admission exists, then finalization returns `not_established/policy_admission_missing` before history append/activation | surface always discloses status/code, unappointed policy-admission authority and what appointment plus composition would establish. A successor owner must supply current qualification evidence **and** wire/replace the production composition before any active/qualified production claim; DS15 changes neither write path |
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
stop-state table and handoff until an owner authorizes separate registration.
CC24's bounded production-negative and badged semantic-test lanes are not
deferrable; `fresh_positive_production_route` is explicitly external and cannot
be silently discharged by either lane.

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
| C06 closed | `docs(atlas): close DS15 acquisition routes` only after bounded CC24; commit/register copy must preserve the external production-growth non-closure |
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
- independent all-15 ranking-authority/method, 15/15 zero-confidence/score,
  3/12 route-demand, uniform VOI-owner boundary and zero-overlay-epoch/event/
  admitted-observation derivations;
- `1 data-shaped / 0 structural / 14 shape not_established` residual split and
  separate `3 structural / 0 data-shaped / 0 not_established` capstone split,
  with `gap_class` named as DS15 vocabulary owned by
  `acquisition_surface_contracts.py` and produced by
  `acquisition_surface_projection.py`, not an N13a/N13b field;
- `government.balance` requirement/gap/hash/rank, current source-profile
  mismatch, quarantine/no-growth/deeper-terminal receipts, and the separate CPI
  acceptance selection;
- ranking-only presentation rules, all-zero basis/owner-granularity disclosure,
  and VOI availability proof;
- planner-owned versioned cost schedule, unknown-gap no-action fallback, and
  completed control-job/compiled-run CAS closure with progress/event/ref
  agreement;
- exact PA2/DS9/permission/step-up action sequence, DS15-owned guarded-store
  composition status, external signed-v2-delegation/current-mandate-owner band,
  and deterministic admission-bundle producer band;
- the N13b raw-path/World-Bank-only limitation, required owner production port,
  absent institutional qualification owner, the real pending
  `not_established/policy_admission_missing` disclosure, and why active but
  unqualified is unreachable without an out-of-scope write-path change;
- one-spine passport/quarantine/overlay/re-entry source refs plus the exact
  CAS/event/action-head receipt owner and crash-recovery phase;
- API packets, generated ABI twins, raw-response/DOM/MACHINE hashes;
- DS11 landing/path-fence release receipt and exact frontend wait point;
- 40-declared/40-ceiling mechanism derivations, 11-round accounting, visual/
  a11y timing with `user + sys` and uptime pairs; and
- every remaining out-of-scope non-closure, including the separately owned
  `fresh_positive_production_route`; if that receipt is missing, a bounded-close
  handoff that explicitly says production world growth was not established.

Anything that introduces a new permission, decision source kind, acquisition
writer/store/passport/epoch allocator, public audience, current authority from a
repository artifact, client VOI computation, or path 41 requires an approved
plan amendment before code.
