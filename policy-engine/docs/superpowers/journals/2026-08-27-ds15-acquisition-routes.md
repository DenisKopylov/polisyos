# DS15 C00 execution journal — 2026-08-27

## Standing and scope

- Execution branch: attached `codex/ds15-acquisition-routes-execution`.
- Integration base: `f3e3d996bd6710e26f24fd913d4fe0547f1d1a0d`.
- Entry commit: `4709562c4ca67e691b355ec2941cf7d48262291e`, merge parents
  `f3e3d996bd6710e26f24fd913d4fe0547f1d1a0d` and
  `cc71a59945bd5d0d84911e8371bbfcf356d91743`.
- Entry plan blob: `16de6702ab7e79fb0277d9071fdb3b9ded1f7aac`, equal at
  `HEAD`, the second merge parent, and
  `codex/ds15-acquisition-routes-plan` before this C00 edit.
- C00 scope: this journal plus the authoritative DS15 plan; zero source, test,
  generated, snapshot, register, or mechanism paths.
- Intended commit boundary: `docs(atlas): bind DS15 acquisition surface reds`.

`git rev-parse --show-prefix` returned the empty string from the attached
worktree root before every cited path coordinate. `git status -sb` named the
attached branch and was clean at entry; `git symbolic-ref -q HEAD` returned
`refs/heads/codex/ds15-acquisition-routes-execution`.

The following ancestry probes each exited `0` against entry `HEAD`:

| required ancestor | role |
| --- | --- |
| `4ff11db52` | DS11 landing merge and fence-release ancestry |
| `74f26ca2d` | DS7 gate |
| `719d7a35a` | GY-N13a gate |
| `b3f11e587` | GY-N13b gate |

No cited set depends on a shell pipeline. One early controller `rg --files |
rg`, two early DS11-agent pipelines, and three implementer exploration
pipelines lacked a separately captured upstream exit; all of those outputs were
discarded and their claims were re-derived pipe-free. One first DS11/DS15 Ruby
parser used unsupported `filter_map`, exited `1`, and produced no admitted set;
the compatible parser exited `0`. Two transient N13 audit probes selected the
wrong terminal shape before the flat `live_attempt_terminal` discriminator was
re-read; both failed and were discarded before the final counts below.
A first final assertion wrapper also compared a line-wrapped qualification
sentence literally, printed `qualification_preserved=False`, and accidentally
omitted that boolean from its exit predicate. Its nominal exit `0` is discarded;
the corrected wrapper normalizes whitespace and includes every printed
predicate in its exit decision.

## Dependency and baseline receipts

Dependency and long-validator timings in this table were executed by the C00
controller and are retained as `institutionally_supplied` to this journal
holder; they support environment/harness accounting, not product semantics.
The implementer independently re-opened every source coordinate cited by the
plan and re-derived the focused artifact/path counts below.

| receipt | exit / timing | disposition |
| --- | --- | --- |
| frozen Python sync, offline | `1`; `real 0.45`, `user 0.15`, `sys 0.07`; uptime `23:14 up 3 days, 13:28` before/after | non-receipt: `jaxlib==0.8.2` absent from cache |
| lockfile-identical Python sync, online retry | `0`; `real 113.95`, `user 68.25`, `sys 22.73`, `user+sys=90.98`; uptime `23:14 up 3 days, 13:28` -> `23:16 up 3 days, 13:29` | dependency receipt |
| `corepack pnpm install --frozen-lockfile` | `0`; `real 31.30`, `user 7.53`, `sys 16.96`, `user+sys=24.49`; uptime `23:13 up 3 days, 13:26` -> `23:14 up 3 days, 13:27` | dependency receipt |
| six focused N13 owner-test files | `0`; 6 explicit production-catalog witness skips; `real 191.11`, `user 116.73`, `sys 9.56`, `user+sys=126.29`; uptime `23:17 up 3 days, 13:30` -> `23:20 up 3 days, 13:33` | inherited owner family green and byte-identical |
| `test_production_acquisition_invokes_epoch_adapter_and_returns_policy_admission_missing` | `0`; launched untimed | functional qualification receipt only, not a timing baseline |
| N13a recomputing checker `--check`, fresh full rerun | `0`; `real 12.12`, `user 15.91`, `sys 1.12`, `user+sys=17.03`; uptime `23:52 up 3 days, 14:05` -> `23:53 up 3 days, 14:06` | complete current owner timing receipt |
| full N13b checker, fresh full rerun | `1`; `real 317.26`, `user 286.65`, `sys 10.58`, `user+sys=297.23`; uptime `23:53 up 3 days, 14:06` -> `23:58 up 3 days, 14:11`; failure `n13b_acquisition_contract_drift` for the committed N13b acquisition executor contract | current-worktree failure receipt; supersedes the interrupted attempt but does not alone establish inheritance, is never green, and cannot support DS15 closure |
| full N13b checker, exact slice-base replay | `1`; `real 298.25`, `user 273.35`, `sys 10.85`, `user+sys=284.20`; uptime `00:13 up 3 days, 14:27` -> `00:18 up 3 days, 14:31`; failure `n13b_acquisition_contract_drift` | exact-base half of P41 pair; explicit non-receipt |
| full N13b checker, execution replay paired to exact base | `1`; `real 297.36`, `user 272.69`, `sys 10.70`, `user+sys=283.39`; uptime `00:19 up 3 days, 14:32` -> `00:23 up 3 days, 14:37`; failure `n13b_acquisition_contract_drift` | execution half of P41 pair; identical inherited failure, explicit non-receipt |

The entry worktree itself required no writer, dependency change, or expensive
validator rerun for C00.

## N13a dual census and reachability

The generated-family owner in `architecture/generated_artifacts.toml` declares
three N13a outputs and all three exist. The committed generated-artifact
reference table independently lists the same three paths. The census, journal,
and carrier-liveness owners then give these complete-set results:

| fact | derivation A | derivation B | result |
| --- | --- | --- | --- |
| connector families | `family_scorecards` length | `family_receipts` length | `12 / 12` |
| selected journal rows | `records` length | sum of scorecard `selected_probe_count` | `144 / 144` |
| actual network calls | sum of scorecard `network_call_count` | complete journal rows with a request | `18 / 18`: World Bank 12, CKAN 6 |
| metric resolutions | `metric_resolutions` length | status partition | `124 = 95 resolves_exact + 20 resolves_via_alignment + 9 unresolved` |
| residual denominator | `growth_backlog` length | `reverse_demand_residuals` length and N13b local-lift denominator | `15`, all `binding_gap` |
| ranking authority/method | complete backlog grouping | canonical recomputation fields pinned by the owner checker | 15/15 `ranking_only_not_voi`; 15/15 `interim_binding_confidence_x_route_demand` |
| displayed score basis | complete backlog grouping | reverse residual demand-source recomputation | confidence `0.0` 15/15; score `0.0` 15/15; demand `2.0` 3/15 and `1.0` 12/15 |
| VOI owner boundary | complete grouping of three owner fields | strict owner recomputation | all 15: `metric_residual_granularity_not_supported`, `routed_to_gy_n13b`, `polisyos.runtime.quality.acquisition_planner.plan_evidence_acquisition` |
| capstone routes | N13a `route_evidence` | N13b `capstone_routes` | 3/3, all `not_a_data_gap`, zero laundered |
| sample plans | `plans` and `sample_rows` | `sample_binding.projected_item_count` and execution-fence counters | 7 plans, 0 preview, 0 execute |

The residual shape split stays denominator-qualified. The N13b re-entry trace
joins exactly one backlog row, `government.balance`, at rank 8 and establishes
`requirement_family=data_requirement`, `gap_type=data_snapshot_release`, L1
`unavailable`, and zero observations. The other 14 `binding_gap` rows have no
data/structural owner classification. Result: residuals `0 structural / 1
data-shaped / 14 shape not_established`. The separate capstone denominator is
`3 structural / 0 data-shaped / 0 not_established`; no route ID or proximity
joins the two sets.

Carrier liveness remains
`worldbank.wdi / no_data_for_scope / metadata_source_id=11 /
carrier_current_source_profile_mismatch`, with missing lever
`source_selector:11`. It is a deeper connector-contract/configuration terminal,
not an active acquisition authorization.

A complete AST walk of all **100** Python files under
`src/polisyos/runtime/http/` found **106** route decorators: 73 GET, 32 POST,
and 1 WebSocket. The only acquisition/ingest-shaped existing direct route is
`POST /api/v1/control/data/ingest`; its `ingest_data` handler invokes generic
ingestion and is not the DS15/N13b seam. An independent `ProjectionId` AST
census found 13 members, exactly two N13a IDs
(`n13a-acquisition-census`, `n13a-live-probe-journal`), and no carrier-liveness
or N13b ID. The existing Cycle Board is a partial in-process/HTTP consumer; it
does not make N13b row movement reachable.

## N13b physical, logical, and outcome census

The generated-family output list and lifecycle registrations both return 43
physical files. Classification of the complete path set is **22 CAS files**
(11 blob/manifest logical objects) + **1 journal** + **20 top-level JSON**,
hence 32 logical objects. The lifecycle manifest independently reports 43
registrations partitioned as **41 content-bound + 2 writer-managed**.

The raw journal has 44 complete JSONL events:

- 5 requests;
- 5 transport attempts;
- 26 heartbeats;
- 2 raw responses;
- 1 classification; and
- 5 `live_attempt_terminal` events.

All five terminal rows are quarantined and none is admitted. Their failure
partition is `live_raw_response_shape_drift=1`,
`metadata_characterization_complete=1`,
`metadata_retryexhaustederror=1`, and `retry_exhausted_error=2`. The executor
contract independently reports 5 attempts/terminals, 2 raw responses, 0
admissions, and 5 quarantined outcomes.

The executor contract and re-entry trace agree on 0 overlay epochs, 0 growth
events, 0 admitted observations, availability `0 -> 0`,
`world_growth=no_growth`, and
`deeper_terminal_primary_carrier_characterization_failed`. The separate CPI
selection `FP.CPI.TOTL` is an acceptance/audit case only and is not spliced into
the `government.balance` re-entry identity.

The smaller lifecycle counters embedded in the older raw journal are
superseded by the current lifecycle manifest. The disagreement is recorded;
only the current 43/41/2 owner is used.

## Qualification chain and adjacency

Every symbol in the binding qualification ruling was re-opened in source:

1. `QualificationConsumer.from_unallocated_policy_authority()` sets the
   unallocated flag and `qualify()` returns typed
   `status=not_established`, `code=policy_admission_missing` before candidate
   reconciliation.
2. `admit_acquisition_with_semantic_epoch()` verifies raw/CAS evidence, creates
   the semantic candidate, prepares the epoch, builds the passport, writes the
   pending overlay and admitted-boundary evidence, and then invokes
   `SemanticEpochService.finalize_admitted_epoch()`.
3. `finalize_admitted_epoch()` recursively reloads and content-binds the
   prepared/admitted/candidate/passport/pending/native/denominator/provenance
   chain, resolves the owner denominator, and calls `_append_and_qualify()`.
4. `_append_and_qualify()` constructs a staged history view, calls the
   qualification consumer, and returns a negative production receipt before
   `append_if_current()` when qualification is not positive.
5. The acquisition caller returns every non-`appended`/`no_change` receipt
   before `overlay.activate_semantic_epoch()`.
6. The dedicated production-path test pins `activation_calls == 0`, empty
   native history, one `pending_epoch_activation` row, and zero visible
   observations.

C00 therefore authorizes only the exact pending/unqualified projection. It does
not edit or reinterpret the qualification, history, activation, overlay, or
acquisition writer paths.

The live held `codex/unbound-writes` worktree was read at
`d557dc2bd32e8423ae00955d4cfe90dc529f9286`, with merge base
`f3e3d996bd6710e26f24fd913d4fe0547f1d1a0d`. For
`src/polisyos/core/contracts/control.py`, its scoped status was empty, the
base-to-head `git diff --quiet` exited `0`, and the scoped branch log emitted no
commit. C02's declared canonical literal path therefore has no current
status/diff/log intersection with that lane. No edit to `fabric/world/` or
`runtime/quality/data_state_substrate.py` is established.

## DS11 fence and DS15 path derivations

DS11 execution base is `f935e0c2e9359bc1202ce5d36ea706de58f7aaab`,
tip is `8b9b4730915f1c0740b629d15ed9289217071215`, and landing merge
`4ff11db52` carries that tip as its second parent.

Derivation A, a pipe-free `git diff --name-status` from base to tip, returns 65
unique paths: A=31/M=34; file types TSX=21, TS=14, JSON=10, Python=9,
Markdown=8, TOML=1, MJS=1, PNG=1. Derivation B, DS11's committed plan/journal
mechanism/P39 declaration, returns `30 mechanisms + 35 companions = 65`.
They agree.

The pre-C00 DS15 Add/Modify parser returned 37 unique mechanisms by independent
cluster arithmetic `6+14+12+4+1`. Contrary to the supplied expected zero, the
complete DS11/DS15 intersection is three paths:

- `apps/runtime-dashboard/src/shared/i18n/locales/en.json`;
- `apps/runtime-dashboard/src/shared/i18n/locales/uk.json`; and
- `architecture/atlas_surfaces/check_frontend_disposition_register.py`.

For each path, `git diff --quiet` between the DS11 tip and DS15 execution base
exited `0`: DS11's bytes are already reconciled into the base. The DS15 visual
spec and its complete snapshot root are exact-path-disjoint from DS11. The
fence is therefore released by ancestry plus equal complete censuses, not by
the discarded supplied number 63 and not by pretending the intersection is
zero.

## Execution-base source census and C00 plan corrections

Two complete execution-base scans agree on **2,811 tracked `src/` files** and
the same path set. File types are 2,601 Python, 5 Python stubs, 10 JSON, 11
YAML, 164 Markdown, 15 CSV, 2 Cypher, 2 `typed`, and 1 SQL. `rg -l gap_class`
and `git grep -l gap_class` each exited `1` with zero matches; their wrapper
audits exited `0`. This replaces the historical plan-entry 2,810/2,600 count
without changing the ruling that C01 owns the first `gap_class` definition.

The amended Add/Modify parser now returns **39 declared / 39 unique** mechanism
paths with file types Python=22, TSX=9, TS=5, JSON=2, Rego=1. Existence
classification is 24 existing + 15 intended new. Independent cluster arithmetic
is `7+15+12+4+1=39`.

The one-path correction is source-required:
`governed_projection_validation_worker._validate_request()` resolves the
projection ID through `_VALIDATORS`; an otherwise well-formed new ID with
definition/marker bytes but no worker registration returns
`owner_validator_unregistered`. C01 therefore adds the existing worker as its
seventh mechanism and the mirrored worker test as P39. This is a pre-C01 plan
correction, consumes zero of 11 rounds, adds no new projection family beyond
the single planned `acquisition-growth` ID, and moved the interim ceiling to 38.

C00 review established a second mechanism necessity before C01. Derivation A
reads the complete closed `action_contracts["runs.review"]` map in
`ops/policy/policies/action_permission.rego`: it contains exact case-inspection,
governed-projection, human-decision, and run-paper resource classes, but no
acquisition-route class. The same source's `resource_kind_matches` predicate
requires the OPA input kind to equal `resource_class.binding_authority` exactly.
Derivation B reads the existing route-authorization specifications:
`test_rego_action_resource_contracts_match_live_guarded_router` requires the
closed Rego map to equal all live guarded route contracts, while
`test_run_paper_is_review_guarded_before_projection` pins an exact
`runtime.run_paper` resource class and proves denial before projection. The
already-declared C02 API-contract-hardening parity and authorization-access
audit companions can materialize the DS15 mutation without adding a test path.

The target GET contract is therefore exactly `RUNS_REVIEW` /
`runtime.acquisition_route.tenant_collection`; preserving role and permission
while substituting `runtime.case_inspection.tenant_collection`,
`runtime.run_paper.tenant_collection`, or another proxy remains denied. Both
POSTs keep `EVIDENCE_ACQUIRE` /
`runtime.evidence.acquisition.request_bound` plus acquisition step-up. Adding
the existing Rego owner as C02 mechanism 15 moves the union to 39 and the stop
to path 40. It adds no permission enum and spends no widening round.

CONTRIBUTING's nearest-parent README rule and release-fragment governance are
now named as exact P39 companions:

- C01/C02: `src/polisyos/runtime/http/services/README.md`;
- C02: `src/polisyos/runtime/quality/README.md`;
- C02: `src/polisyos/runtime/http/routes/README.md`; and
- C03: `release-fragments/unreleased/2026-08-27-ds15-acquisition-routes.toml`.

These mandatory records remain outside the 39-mechanism ceiling under P39.

The C00 review finding is bucketed as NEW class
`timing_receipt_completeness`, first occurrence. The incomplete N13a timing row
is replaced by the fresh full receipt above; the interrupted N13b attempt is
superseded by the complete failing receipt. This is P39 evidence repair only:
zero mechanism change in C00 and zero widening round.

The second review finding is bucketed as SAME class `baseline_provenance`, one
level deeper. It does not reclassify the prior NEW timing-completeness finding:
the first repair completed the timing record, while this repair proves whose
red it is. It is C00 evidence repair only and spends no widening round.

The temporary verifier checked out exact slice base
`f3e3d996bd6710e26f24fd913d4fe0547f1d1a0d` and used base-first
`PYTHONPATH=$PWD/src:$PWD`. Import-origin readback proved that both `polisyos`
and `tools.lib.timing` resolved inside that base worktree, excluding execution
or ambient module shadowing. With the same catalog/L5 inputs and a 600-second
ceiling, the exact checker exited `1` at base and execution with identical
`n13b_acquisition_contract_drift`; the complete timing pair is recorded above.

The N13b failure is classified under P41 only after that exact-base replay and
two disjointness derivations. First,
`git diff --name-status f3e3d996b..HEAD` exited `0` and
listed only the added DS15 plan and journal; the C00 review worktree likewise
contains only those same two docs. Second,
`git diff --quiet f3e3d996b..HEAD -- policy-engine/src policy-engine/tools
policy-engine/tests policy-engine/architecture policy-engine/ops
policy-engine/schemas` exited `0`: the checker, current owner sources,
registered artifacts, policy and schema roots are byte-identical to the slice
base, and neither changed docs path belongs to that complete input denominator.
The controller's independent external-input hash pass exited `0` with catalog
hash `4a1eab1363a948a875d00b0ae3929f47b763ba429c85776709641d6ca7960dd7`
and L5 hash
`90f341b2e71edb28b6208f580d8a920191d67240c240db9417ba18a225187aff`.
The matching exact-base/execution checker pair plus the zero input intersection
and equal external-input hashes therefore establish a base-owned current
disagreement, not a DS15 mechanism regression. No earlier non-base rerun alone
supports that attribution. DS15 cannot rewrite the N13b generated artifact or
write path; the red remains an explicit baseline non-receipt and is not used for
closure.

## Executable red specifications

C00 materializes no test or mechanism. Each row below is a pinned executable
red for the named later-cluster P39 test path. A later cluster first proves the
mutation fails for the named missing property, then implements without weakening
the mutation or changing fixture authority.

| falsifier | exact mutation / witness | required red and later green property |
| --- | --- | --- |
| `DS15-STRUCTURAL-NOT-DATA` | In C01 projection tests, add rows, established-looking cost, and forged `live_fetchable` to a real `not_a_data_gap` capstone row. | Any button/eligibility or row-count-based advancement is red; server result must remain `not_applicable` with the structural witness/missing link visible. |
| `DS15-BINDING-NOT-DATA` | Preserve one real residual's `binding_gap`, rank, score, and demand, but remove requirement-family/gap-type/L1 owner evidence. | Any inferred `data_gap`, cost, or action is red; recomputed `gap_class` must be `not_established`. |
| `DS15-NO-STALE-REVIVAL` | Preserve historical N13b IDs while changing/removing current run/job, planner hash, L1 availability, rights, mandate, or rule epoch. | Decision preparation or effect execution is red; route becomes `revalidation_required` or `producer_missing`. |
| `DS15-RANKING-NOT-VOI` | Rename/interpolate `ranking_only_not_voi` as VOI or client-sort without explicit override metadata. | Contract, UI, or parity acceptance is red; source order remains interim ranking and numeric VOI stays absent. |
| `DS15-ZERO-SCORE-DISCLOSURE` | Hold the real 15 IDs/order fixed while obscuring 15/15 confidence/score zero or the 3/12 demand split; separately mutate one residual's owner evidence and rerun `derive_growth_backlog`. | Hidden hard-coded copy is red; real packet discloses no nonzero gradient, recomputed mutation becomes 14/15 zero with owner-derived order, and neither packet becomes VOI. |
| `DS15-COST-BASIS` | Keep expected cost while removing/changing the exact schedule row, basis ref, rate/rule/hash provenance, line-item equality, or supply caller/default zero; leave legacy unknown-gap fallback callable. | Actionable cost, review, or execute is red; cost becomes `missing`/`invalid` and legacy/default zero never establishes actionability. |
| `DS15-PA2-AUTHORITY-BANDS` | Independently remove guarded gateway composition, signed v2 delegation/current mandate evidence, or deterministic admission-bundle producer while retaining signatures/approval markers. | Any combined allowed result is red; engineering composition and both external evidence bands fail closed independently, and signer equality cannot establish appointment. |
| `DS15-QUALIFICATION-DISCLOSURE` | Keep pending epoch plus `policy_admission_missing` but remove authority/appointment effect, label active/qualified, or replace typed status with reassuring copy. | Contract/UI/parity acceptance is red; row stays pending `not_established`, names the unappointed policy-admission authority, and states what appointment plus composition would establish. |
| `DS15-DEFERRED-PA2` | Persist an allowed-looking marker but delete/tamper the durable decision, cross-bind tenant/run/job/route/effect, or call the port without gateway load and `execute_bound_effect`. | Any external call or executing head is red; job fails closed before the port with no executing receipt. |
| `DS15-GET-RESOURCE-EXACTNESS` | Preserve the same role and `runs.review` permission but substitute case-inspection, run-paper, or another proxy bound resource kind on either acquisition GET. | OPA denial must occur before projection; only `runtime.acquisition_route.tenant_collection` is admitted. |
| `DS15-EXECUTION-PORT` | Offer raw journal/CAS paths, wrong connector, unguarded store, tenantless port, or arbitrary data-shaped row. | Any network/world write is red; strict production handshake refuses first. |
| `DS15-PASSPORT-BOUNDARY` | Preserve bytes and passport marker fields while removing one decisive schema, units, alignment, license, PII, or trust verification. | Admission/growth is red; recomputed passport refuses, Fabric quarantine renders, delta remains zero. |
| `DS15-EPOCH-ACTIVATION` | Present an admitted-looking passport without matching qualification, native-history, production, and active-overlay receipts. | `grew` or activation is red; no growth event exists and action fails closed. |
| `DS15-REENTRY-BINDING` | Preserve global N13b status/counts while changing case/design-problem/gap/receipt, bind overlay A while reading B, or omit post-epoch trace. | Per-row movement is red/empty; global status cannot substitute for exact same-case binding. |
| `DS15-ACTION-HEAD` | Orphan phase CAS/event/head, fork predecessor generation, or crash after active epoch before re-entry terminal. | False terminal or reacquisition is red; surface shows typed recovery and resumes exact re-entry only. |
| `DS15-OFFLINE-AUTHORITY` | Replay a formerly valid decision/token or queue decision/execution offline. | Network dispatch, optimistic authority, or local replay is red; server rejects stale/offline proof. |
| `DS15-N13B-NEGATIVE-HONESTY` | Change historical `no_growth` to `grew`, zero epochs to one, or deeper terminal to advancement without owner receipts. | Projection validation and visible-source parity are red; history remains quarantine/no-growth/deeper-terminal. |
| `DS15-MACHINE-PARITY` | After one response-byte capture, mutate, remove, or reorder any visible raw field in DOM or MACHINE output. | Parity is red against the captured bytes; UI performs formatting only. |
| `DS15-SIBLING-CONSUMER` | Add another endpoint/component that reads raw N13a/N13b JSON or generic ingest as authority. | Generic AST/consumer census is red; every read routes through the single admitted projection seam. |
| `DS15-OWNER-VALIDATOR-REGISTRATION` | Add the `acquisition-growth` enum/definition and marker strings, but omit its `_VALIDATORS` owner registration. | Worker must return `owner_validator_unregistered`; C01 green requires resolve/content-bind/owner validation through the existing worker, not marker presence. |

Additional C02 mutations remain binding under the named rows: forged client
status/body; cross-tenant/run/route decision reuse; crash after passport before
epoch/readback; active overlay A with re-entry overlay B; and patched legacy N7
world-write/generic ingest arms that raise while admitted-overlay re-entry still
completes. C05 keeps the permanent
`behavioral_fixture_not_production` badge through the full motion.

TDD/red status at C00 is therefore **specification pinned, zero tests written,
zero mechanisms changed**. Existing owner tests remain green; the new reds are
not claimed as executed until their named clusters materialize them.

## Pattern pass and capability standing

| pattern | C00 finding | closure move / acceptance signal |
| --- | --- | --- |
| P01/P02/P03/P12 | N13 richness still lacks the DS15 bridge/surface chain. | Keep bounded state `producer_missing + bridge_missing + surface_missing`; later prove owner artifact -> bridge -> HTTP -> UI/MACHINE -> semantic negative. |
| P04/P05/P09/P15 | Approval, fetch, passport presence, or pending epoch could be laundered into success. | Preserve independent facets and the exact pending/unqualified plus production-negative receipts; no C00 softening. |
| P29/P31/P32/P33 | A new projection enum/marker without worker registration would be contract-only and trust-by-form. | Add the existing validation-worker chokepoint as C01 mechanism and keep the remove-registration/keep-markers falsifier. |
| P35/P36 | Historical 2,810 and expected-zero DS11 overlap were stale/supplied prose, not complete denominators. | Recompute complete path/type sets, record the 65/37/3 disagreement, cite owner artifacts/fields, and amend to the measured 2,811 baseline. |
| P37/P38 | Supplied `63`, an expected zero, or enum presence is a proxy gate. | Fence turns on landing ancestry + dual complete set; availability turns on worker owner validation. Divergent cases are 65 paths despite `63`, three real overlaps despite expected zero, and a defined ID rejected without `_VALIDATORS`. |
| P39 | Contributor/release records, complete timings, the worker, and exact Rego action contract were absent from the declared budget/evidence. | Name README/release companions outside the cap; replace incomplete timing receipts; add worker and Rego owners inside it; 39/39 and 11 rounds. |
| P40/P41 | No repair ladder or unmeasured inherited-red attribution is allowed in C00. | Zero rounds spent; SAME `baseline_provenance` is closed only by the identical exact-base/execution failure plus path/input disjointness and equal external-input hashes. The N13b drift remains a non-receipt and cannot support closure. |

The source-level qualification capability remains
`absent/unallocated + bridge_missing` at the institutional owner/composition
band. The current pending artifact chain is real, but cannot be called qualified
or active. `fresh_positive_production_route` remains external
`absent/unallocated` with `producer_missing + bridge_missing +
verification_missing`; the bounded DS15 mechanism may later close without it,
but no production-growth claim may.

## C00 acceptance

- Attached branch/base/blob/ancestry: read and admitted.
- N13a 3-output and N13b 43-output physical/logical families: dual-derived.
- HTTP/in-process reachability, residual/capstone split, selection, quarantine,
  no-growth, deeper-terminal, and qualification ordering: source-read and
  denominator-qualified.
- DS11 fence: released with a recorded 65/37/3 disagreement and byte-equal
  historical overlap.
- Source baseline: 2,811 tracked files and zero `gap_class` in two equal sets.
- Budget: amended to 39 mechanisms, 11 rounds, path 40 stop; required P39
  README/release companions exact.
- C00 mechanism paths: 0. Widening rounds: 0. Serialized writer locks: none.
- Qualification and fresh-positive-production non-closures: unchanged.
- Timing review: N13a full receipt green; N13b exact-base and execution replays
  both fail identically and, with two disjointness derivations plus equal input
  hashes, preserve a P41-inherited baseline non-receipt.
