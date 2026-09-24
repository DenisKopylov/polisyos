# Stage 2: native acquisition movement

Stage 1 is preserved. This lane implements GY movement only; numeric VOI and
education are outside this Stage 2 assignment.

## Design agreed before code

Non-test caller: `AcquisitionActionService.handle_job` after the supplier's
durable terminal, including terminal replay and recovery. Container startup
constructs `AcquisitionMovementService` even when institutional policy slots are
empty. The read terminus is the existing
`/api/v1/exports/governed-projections/depth-n-cycle-board` endpoint, with CAS
receipt refs and independent source identities in its composition manifest.

One new movement family module reuses Core CAS, the runtime diagnostic event
log, `AcquisitionRouteLoop`, and GY `QualificationConsumer`. Cycle Board keeps
its existing row enumeration scope. Each native query describes one exact
supplier movement in one row, not an exhaustive history of the world.

Supplier closure and GY admission remain separate acts. Intake reloads the
supplier terminal and predecessor phases, the original compiled source closure,
the reentry artifact and its distinct deeper-terminal event. The candidate
artifact binds the exact row/problem/run, source/new cycle, route, overlay and
epoch. An independent signed GY policy admission selects a typed native owner
relation over that artifact. The movement verifier recomputes the source chain;
signature transport alone does not admit it. The shared chronology owner owns
the native projection persistence extension, implemented by the positive lane.

Empty policy selectors produce a persisted `policy_admission_missing` refusal;
missing or invalid supplier evidence never becomes a movement record. GY
register closure is a separate architect act and is not edited here. Global
N13b's denied row uses remain unchanged.

Mechanism budget: one new movement module plus the two existing Cycle Board
contract/projection modules. Mirrored focused tests and this journal are required
companions outside the mechanism-path count. No database, scheduler, external
institutional subsystem, canonical register, or ledger is introduced.

Pattern pass: P01/P02/P03 require persisted producer → admission → consumer →
surface; P05/P32 require exact content/provenance admission; P07/P08 bind source
and deeper times; P29/P37/P38 require removal probes against source semantics.
The first source counterexample was an existing row-scoped producer merely
omitted by the board; exact and insensitive navigation identified the existing
unconditional empty board and the shared forced projection gap. Neither is
treated as institutional absence. Review bucket: a forged supplier/source
relation is one semantic-intake class, not an instance ladder; an actually
different ownership/persistence escape is classified separately before repair.

## Verification receipt (append after execution)

The test-first focused supplier non-growth counterexample was launched before
the module existed. Complete output is retained under the journal's ignored raw
storage; final paths and hashes are appended after the frozen run.

## Scope and ownership resolved during implementation

The movement predicate is **historical completed movement under scoped supplier
custody**, at `supplier_generated_at`, with exact source/new cycle and native
production receipt references. It does not claim current overlay availability.
Deleting an active overlay later is not a falsifier of the earlier completed
act; the current acquisition route separately requalifies current native epoch
custody. Loss of the historical reentry bytes or the saved GY projection is a
custody failure and must retract the admitted board record.

The supplier fixture declares fixture PA2 authorization and fixture candidate
generation. Its WDI executor, native admission/finalization/activation/readback,
N6 controller, supplier receipt sink, movement verifier, chronology custody and
Cycle Board consumer are real implementations. This witness alone is not a
unified HTTP authorization positive. The separate served authorization witness
belongs to the mandate lane. Board row enumeration still comes from the existing
component owner; the movement witness substitutes its actual completed problem
into the explicit component fixture and checks the production board composition.
No movement event expands that enumeration.

Cross-lane reuse supplied here: `tests/_helpers/semantic_epoch_native.py` signs
an exact real prepared native basis, then uses the concrete epoch owner without
constructing a positive production receipt. `tests/_helpers/acquisition_production.py`
provides a real persisted WDI route and external HTTP-byte interception; its
optional loopback allowance preserves actual local OPA/JWKS transport for the
served witness. `tests/_helpers/acquisition_human_decision.py` preserves the
original source bytes, signs the separate external principal/separation/presentation
facts, and records exact required-evidence delivery through the existing audit
reserve/complete path. It neither creates a human decision nor creates a bound
HTTP permission.

## Review classifications

R-M1 was a **new durable side-effect acknowledgement class**: native activation
could precede aggregate persistence and leave an executing route unable to
recover; reentry persistence could precede the pointer and permit duplicate N6.
R-M2 was a **new snapshot coherence class**: native verification and N6 initially
used different locks from admission. The root lane accepted one durable attempt
and recovery protocol plus the shared admission lock, with an explicit unknown
N6 outcome refusal. This movement lane does not duplicate that protocol.

The bounded read-only review of the concrete epoch owner and activated receipt
reader found no demonstrated blocker: the owner reconstructs canonical ancestry,
exact native manifest bytes and query bindings; the reader requalifies its saved
candidate and demands the original projection/bundle/verifier identities. An
additional direct admission-query-context guard is the same signed-context
class deeper; the shared qualifier already enforces that binding. This is source
review evidence, not a passing runtime receipt.

## Initial diagnostic evidence

These outputs are preserved without replacement. Imports overlapped other
agents' edits, so they are diagnostic receipts rather than the final frozen
source wave or an immutable test-first proof:

- `outliers/raw/stage2-movement-red.txt@sha256:4838bb6b9958e880fc804604b384fcd33d8eabda58997a367c708cda45033c44`:
  module-absent collection failure after the focused tests were written.
- `outliers/raw/stage2-movement-negative-first.txt@sha256:17f1b1f6b26c682cfb892c51d15bbf5c59393112ec9f3cb4881ac3dbfb64fde2`:
  two supplier-no-growth/empty-deployment tests passed; measured 394.51 seconds.
- `outliers/raw/stage2-board-red.txt@sha256:7607e7c60b4a9d998a2b675c2ebe0f40489cced4cc37e4a336b0a8a74ae6e33f`:
  the old board constructor rejected `movement_service`.

The next frozen-wave witnesses are the two explicit selectors in
`tests/unit/runtime/quality/test_acquisition_movement_positive.py`: separate
supplier/GY closing acts reaching Cycle Board, and removal of decisive native
bytes while supplier/intake/movement/qualification markers remain. Until those
results exist the positive chain remains `verification_missing`; no GY register
closure is implied. Targeted Ruff passed for the new witness file and helper
files before handoff. Complete deciding frozen output and hashes are owned by
the root integrated-wave receipt and must be appended before completion.

Delta review of the root R-M1/R-M2 implementation found no demonstrated
at-most-once escape: `acquisition_world_growth.py:232` saves exact evidence and
prestate under the admission lock before activation; `:334` recovers from native
activated owner records and verifies the saved live evidence; `:518` holds that
same lock across native verification and N6. The deterministic result lookup
precedes the durable started fence (`:527` and `:545`), so a fence without a
verified result refuses. `acquisition_surface_execution.py:478` recovery neither
fetches nor activates. A CAS artifact orphaned from its authority event may
still refuse in `_read`/`_persist`; this is a bounded same-class acknowledgement
residual, with no repeated effect and no additional repair requested. Frozen
runtime receipts remain the deciding evidence for these source-review findings.

## First frozen-wave incident: historical board owner

The initial frozen wave reaches the production board loader and fails before
movement composition (`raw/stage2/first-wave.txt`, board failure beginning at
line 631). `src/polisyos/runtime/http/services/cycle_board_sources.py:242` expects
`Producer availability denominator | DS3 measured`; the actual Atlas owner at
`docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:730`
now has a struck, **CLOSED 2026-08-22, re-owned** heading. The historical body still
records 5 available / 7 invalid_source / 1 artifact_missing. The exact heading
proxy no longer matches and the loader raises at line 249.

This is a **new incidental historical-parser class**, destination
`measurements/cycleboardscope`, not a movement semantic-intake repair. Its red
provenance is `not_established`: this lane has not replayed the exact runtime
command on slice base `28b8a1a42`, and does not call it inherited. No source owner,
register or production parser was edited.

`tests/_helpers/acquisition_movement_board.py` isolates the movement witness with
a declared scratch historical row: it preserves the actual measured body and
supplies the parser's earlier heading. DS4 and N13b remain read-only links to
their actual owners. The production board code still runs. This fixture is not
proof that today's Atlas owner loads or that the full real-owner endpoint is
available; that surface has an explicit nonreceipt until the named incidental
owner issue is resolved. The test changes passed targeted Ruff and are frozen
for the next integrated wave.

## Bounded repair of the actual board caller

The architect/root authorized the historical-input parser repair because the
actual movement consumer needs that source. The earlier scratch fixture was
removed. The existing loader now uses `split_markdown_table_row`, enumerates all
actual table cells, selects the exact historical DS3 measured-cell grammar,
requires one complete measurement, and rejects missing, duplicated or malformed
input. It does not depend on mutable debt-title/status decoration. Mirrored
semantic tests change the heading, change a count, preserve an embedded pipe in
an unrelated cell, and falsify absence/ambiguity/malformed input. The board's
original composed test now pins the actual historical counts instead of repeating
the defective heading regex. These tests passed in the second integrated wave.

A successful source retains its actual file ref and raw byte SHA; its manifest
still forbids current readiness/current producer availability use. The existing
failure path raises `ValueError`/`OSError`; its HTTP handler does not carry a
read-receipt-bearing `invalid_source` envelope. That error-output disclosure is
explicitly `unresolved_by_construction`, destination
`measurements/cycleboardscope`, not certified as a complete measurement-format
migration. The original malformed/ambiguous refusal remains effective.

## Canonical cost-slot investigation (no cost-source edits)

The real WDI route exposed a missing appointed cost basis. The complete static
census is `outliers/raw/stage2-cost-selection-census.json@sha256:bbd40e251bc731590f8a5999864b057b74f8dcaa2f187729d73407d48795cd50`.
It read 6,245 nonignored repository Python files and the exact canonical
acquisition registry JSON, with every read bound by SHA, no failed reads and
empty Git/rg enumeration disagreement. Its complete canonical schedule has
`administrative_tax_receipts` and `local_tourism_site_traffic`; the complete
canonical registry has live `government.balance` and `inflation`. Exact and
case-insensitive intersections are empty. AST call receipts identify the actual
planner, GenerationCycle and AcquisitionRouteLoop producer/recomputation chain.
The quote-keyword result is navigation evidence only; arbitrary dynamic dispatch,
non-Python implementations and external owners remain explicitly unselected.

The deciding code is `acquisition_planner.py:3001`: the producer reloads its
canonical schedule, rejects a supplied schedule that differs, and returns no
record without an exact row. `generation_cycle.py:3397` invokes that producer;
`acquisition_route_loop.py:298` excludes a cycle with no cost record, and `:309`
recomputes the cost against the same owner. WDI selection requires the exact
canonical target. This is a specific `producer_missing` cost basis and
`bridge_missing` external cost-selection link, destination
`acquisition-cost-basis admission/selection`, distinct from numeric VOI.

The hypothetical downstream fixture may supply a distinctly labelled example
price row only at the owner input mapping; the producer, canonical-equality test,
route resolver and cost recomputation stay real. A separate unchanged-default
witness must still refuse the WDI cost slot. This proves the downstream mechanism
under a hypothetical appointed input, never the existence of a production price
or the default served route.

Probe source: `cost_selection_probe.py@sha256:30512bec65643c0ad0a90d95187b206bbc0810cef9f4d0047c1315c3444d3e92`.
Its actual caller passed bounded filesystem acceptance for selected evidence,
evidence only outside the selector, an unreadable selected member, and absent
deciding input with receipt markers retained:
`outliers/raw/stage2-cost-census-acceptance.json@sha256:fa50328216e2ab6e96eb6f54a255003aa84482623bfd3d1bddd76f4ae32b8cfa`;
probe driver `outliers/raw/stage2_cost_census_acceptance.py@sha256:9e91dcee7f8c0643ccb63d57a7936d09b78045bdf6b8679a1758b9586fde5cc9`.
The failed/absent cases remain UNRUN with partial coverage; receipt fields cannot
turn the original failure green.

Frozen-wave outputs retained by the root are
`raw/stage2/first-wave.txt@sha256:7c714359828f31f52c1699402ed0f79f1517cf4b82bd7fe509ba42dba685a622` and
`raw/stage2/second-wave.txt@sha256:9fbff3b48b4c42cf0353ab8173a25d7c2f848e74f72b4f07b66a41c6871d22bb`.
The second wave's supplier path stops on an unregistered event type. The next
bounded composition repair reuses registered producer-execution events; the
movement reader additionally requires exact `reentry_terminal` phase and state,
while preserving source/producer/ref/time/scope and distinct-event checks.

## Historical read disclosure and consumer delta review

The architect rejected leaving the touched loader's error disclosure unresolved.
The later bounded repair supersedes that limitation above: every successful
historical measurement now includes a typed actual-read receipt, raw byte hash,
complete table-row denominator and selected-cell count. Failed or undecodable
reads carry the actual attempted source, exception class, any readable byte hash,
`UNRUN` and partial coverage. The receipt explicitly excludes other sources,
non-table sections and current producer availability. Missing, malformed and
ambiguous measured cells still refuse. The actual HTTP route catches only
`HistoricalProducerAvailabilityError` and returns existing structured 503 problem
details with its receipt; no canonical schema or generated artifact was changed.
Changed-input, unreadable-input, absent-input and actual HTTP failure tests were
added to the third frozen wave; their result is pending in this report.

The frontend review found one further instance of the same positive-composition
class: `apps/runtime-dashboard/src/features/runs/api/acquisitionRouteValidators.ts`
strictly accepts only the old negative route fields and excludes the newly
emitted observation delta. `useAcquisitionRoutes.ts` calls that decoder for both
route list and detail. Thus the new zero-delta negative response also rejects.
The canonical generated client merely returns parsed JSON; this is the local
decoder's boundary. A nongenerated typed compatibility adapter is planned,
because canonical client regeneration is explicitly outside this slice.

The Cycle Board has a different actual consumer path: its query adapter checks
the composed packet identifiers and retains the original payload. Presentation
passes through the historical object, movement records and source manifest;
the dashboard renders their JSON. No strict runtime decoder rejects the new
read receipt or movement fields. A focused preservation witness will cover this
path without broadening it into a new Board schema migration.

Here, a deeper terminal means a later completed N6 cycle under the admitted
observations, not an improved grade. The native controller checks the exact
active overlay, passport and observation count, binds the overlay into the value
port, and runs the next cycle. The movement intake reconciles that resulting
receipt and distinct terminal event. It neither compares grades nor grants
promotion, publishability, row completeness or register closure.

## Frozen positive and enforcement receipts

Both actual supplier/GY/Board selectors in
`tests/unit/runtime/quality/test_acquisition_movement_positive.py` passed in the
third frozen Python wave. The XML contains those exact two testcases without
failure/error children; this supersedes the earlier positive `verification_missing`
checkpoint. Complete root output is
`raw/stage2/third-wave.txt@sha256:6fc86b857b320cbee5f23a9b8b195e47093fc9f78f83c394e8ae8c8a93aa153f`,
XML `raw/stage2/third-wave.xml@sha256:1d4ce4ea74b5cfdbfc7866bf7cda073e1719c26f1475d04b4a48b5a14c3eaf84`,
and source freeze `raw/stage2/third-wave-freeze.json@sha256:cda67f16231c3efb029946cb2cff3a258332b1f050f7bcebaaea0fdc595c8e41`.
The wave's historical HTTP test did not reach the route because its environment
setup lacked a catalog. Its narrow fixture correction uses the existing Slice0
catalog builder, real persisted catalog and typed substrate paths before opening
the actual HTTP runtime; root's fourth wave owns its deciding result.

The actual movement enforcement-removal driver also passed, process exit 0.
It creates one real supplier completion and one separately signed GY intake,
deletes the saved GY projection bytes while keeping the supplier/intake/movement/
qualification bytes identical, and calls the actual Board. Baseline refusal gives
assertion exit 0; removing only `project_row`'s prior-custody read loop in memory
gives assertion exit 1; restoring the original loop and the identical missing
input gives exit 0. The missing proof's real `read_raw` failure and the mutant's
original assertion traceback are retained with all three selected projections.

- Deciding output: `outliers/raw/stage2-movement-enforcement-removal-readraw.txt@sha256:b59da434534ee75a09cd2dded75c876fd7fd085773470527a4a2e3aec6ba8bb1`.
- Driver: `outliers/raw/stage2_movement_enforcement_removal_readraw.py@sha256:b7c5332acf8e44962db6444ae32c0af34f1230e2600e9ec693495b96beba9ec9`.
- Earlier successful driver output with only `get_bytes` observation:
  `outliers/raw/stage2-movement-enforcement-removal-first.txt@sha256:6e942adb3fa46be3a1cd53e6953145ed8637b5bca46bc12357fa33f9123cebaf`.
  The later driver extends the read boundary to capture the decisive repository
  failure before CAS byte loading; it does not change the measured predicate.

These witnesses retain the declared hypothetical cost, fixture PA2 decision,
candidate generation, intercepted external HTTP and fixture signed GY policy.
They do not establish an appointed repository-default WDI price or unified
served institutional authorization. They completed before the positive lane's
subsequent legacy stored-receipt compatibility repair; the root owns final
cross-lane integration coverage of that change.

## Nongenerated dashboard compatibility completion

The authorized compatibility repair adds one strict discriminated wire decoder
in `acquisitionRouteValidators.ts` and uses its inferred types in the existing
hook and presentation consumers. The pending branch preserves the negative
posture and allows an older absent delta without inventing it; a supplied delta
must be zero. The activated branch requires the coherent native badge,
independently reconciled predicate, native readback reason and a positive integer
delta. Action authority/execution capability and external nonclosures remain
independent fields. Unknown fields and mixed authority postures refuse. A local
lint comment identifies the zero as a transport-schema discriminator, not a
rendered decision quantity; no rule configuration was weakened.

The root-authorized additions to the original mechanism scope are the historical
source reader/error adapter and this frontend wire adapter. Five frontend hook/
type consumers are mandatory compatibility companions. Canonical OpenAPI,
generated clients, registers and ledgers remain untouched by this lane.

The new test first failed through the actual list/detail decoder on both the
new negative zero-delta response and the native-positive response:
`outliers/raw/stage2-frontend-route-red.txt@sha256:4fee07587ce1871e1a137b1e4ab611ff8fa9009fccddbd1f031a33606a0769db`.
After repair, eight explicitly named Vitest files passed all 62 cases:
`outliers/raw/stage2-frontend-route-green.txt@sha256:13140a85c7aed39aa3c51d2687d7e7e7c3fea4daf41f69f64af76621f667e883`.
One intervening run exposed a test-only comparison of equal bytes from different
JavaScript realms; the final test compares the complete byte sequences.
App `tsc --noEmit` and targeted ESLint both returned 0 with empty output;
their retained `stage2-frontend-types.txt` and `stage2-frontend-lint-final.txt`
each have SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Formatting output is
`outliers/raw/stage2-frontend-format-final.txt@sha256:17aa973d3f004560237d9a95171210b0671deff23d61628eecf7322ff5938f20`.

The separate raw frontend witness disables the single schema execution operation
in memory, leaving the exact response packet and bytes unchanged. The original
invalid-posture assertion produces `[[0,0],[1,1],[0,0]]` for detail/list at
baseline, removal and restoration. Actual Zod refusals, failed assertion stacks,
mutant returned packets and identical wire hashes are retained. This is a
synthetic transport witness, not native admission evidence.

- Output: `outliers/raw/stage2-frontend-decoder-removal.txt@sha256:2d25cfed9c1c726af0019c50163f5114bfe9cb1f7090b75b9a9d73c36650645b`.
- Driver: `outliers/raw/stage2_frontend_decoder_removal.test.ts@sha256:3e6f5a90aab845529039c2fe833b65126bbafe84f279fb0dc4537d202f2b8836`.
- Runner configuration: `outliers/raw/stage2_frontend_decoder_removal.config.ts@sha256:fe5a27c4ba7b687bfc5db9b99a2745165d0694b7cc4ecb2c7dd37d87831e111c`.

## Post-appointment lifecycle adjudication

A later independent read identifies an important limit on the supplier fixture:
`tests/_helpers/acquisition_chain.py:104` wraps the real admission producer with
`appointment_then_production`. It first prepares the actual negative basis,
signs that exact basis, and calls the producer a second time inside the same
port invocation. This is fixture-added institutional sequencing, not an existing
production orchestration hook. The movement tests and removal probe remain
evidence of movement custody conditional on a completed supplier; they do not
prove the production route's post-fetch appointment lifecycle is complete.

The lower mechanism already exists: `acquisition_epoch_admission.run_admission`
and its module CLI accept durable raw/live evidence and an appointed deployment;
`acquisition_executor.py:1785` reuses the pending prepared epoch before real
finalization and activation. However, DS15's port claims its live attempt and
calls admission once. A negative result becomes an immutable quarantined terminal,
terminal replay returns that terminal, the claimed attempt cannot be reused,
and recovery reads only already-active native outcomes. The public growth
projection requires its saved aggregate pointer. Thus the remaining
`bridge_missing` is a distinct action selecting the durable quarantined attempt
for existing owner admission after appointment, with separate new authority and
supplier closure/N6. It must preserve the original terminal and must not refetch,
reset the lease or disguise fresh activation as acknowledgement recovery.

This is the same positive-composition class one level deeper. The root owns its
class-level disposition and any bounded orchestration repair. No additional
movement-family mechanism is proposed.

## Deferred admission and generation checkpoint

The preceding `bridge_missing` adjudication is superseded by the bounded production
link now implemented in `src/polisyos/runtime/quality/acquisition_world_growth.py`.
The original native producer remains the only admission producer. `admit` (line 232)
first retains the immutable attempt and pre-admission membership. An actual persisted
native negative is resolved against its exact prepared epoch, admitted boundary,
passport, original live evidence, selected cutoffs and CAS bytes before the owned
`AcquisitionWorldGrowthDeferral` is written (lines 127, 285, 419). Missing policy
still returns the actual quarantine; an exception or unsupported result is not
invented into resumable evidence.

`WorldBankWDIAcquisitionExecutionPort.require_route_ready` and
`prepare_route_execution` (`acquisition_surface_execution.py:356,381`) recognize
prior selected attempt state before considering a fresh transport reservation.
Eligible known-negative state goes through `resume_deferred_admission` (bridge
line 356), under the same tenant/cell admission lock, using the stored live evidence
and current appointed epoch deployment. It creates and syncs an exclusive started
fence before invoking the existing owner. Only a durably verified subsequent
negative removes that fence. Unknown outcomes retain it; positive growth is
persisted inside the owner lock before delivery. Existing acknowledgement recovery
continues to read already-active native results. These are source-reviewed owner
transitions; the final enforcement-removal replay remains a separate gate.

A second finding belonged to this same deferred positive-composition class: the
service's fixed generation 1 would collide with the original quarantined terminal.
The authorized widening uses the existing durable action identity rather than
reopening that terminal. `ControlPlaneStore.list_acquisition_action_heads`
(`control_plane_store.py:2538`) enumerates every current generation head in the
exact tenant/cell/run/source-job/route scope. The sink's
`resolve_action_generation` (`control/run_lifecycle.py:467`) reuses a unique same-job
generation only after receipt readback and authority-event reconciliation. A new
job requires the latest actual typed terminal to be `quarantined_no_growth`; pending,
positive, ambiguous or unreadable owner state refuses. The existing unique
predecessor insert fences concurrent requests. `AcquisitionActionService.execute`
and `handle_job` call this owner and pass the selected generation through their
phase and terminal receipts (`acquisition_action_service.py:404,490,801`). No new
schema, institutional owner, ledger state or register closure was introduced.

The supplier fixture now calls the actual port once to obtain quarantine, explicitly
appoints the persisted basis, then calls the real port again. It does not patch the
native producer. It verifies unchanged negative owner bytes and no additional
transport calls (`tests/_helpers/acquisition_supplier.py:21-47`). The completed
supplier still uses an explicitly fixture PA2 decision, hypothetical owner-input
cost row, candidate generation, external HTTP bytes and signed GY policy. This
fixture does not itself persist two separate action-job heads; the owner-generation
selectors exercise that identity dimension. It does not establish unified served
institutional authorization or repository-default WDI pricing.

The fourth frozen wave has been read back from its complete XML: 47 testcases,
45 passed, two failed, zero errors and zero skips. The two movement selectors,
the seven new generation/store cases and the historical read-receipt HTTP selector
all passed. The two failures are the served acquisition and its provider replay
witness, both stopping at DS9 approval with `DS9-DECISION-PERMISSION-UNVERIFIED`.
Their destination is the root's served DS9/permission binding work; this lane does
not classify them as inherited. The wave result records exit 1, unchanged frozen
source and no failed source reads. It is not an overall green closeout.

- Complete output: `raw/stage2/fourth-wave.txt@sha256:a48312fef29a57245b3f833d0f29b7befc1cd8858c28c4040d38f39ee0a23ca0`.
- XML: `raw/stage2/fourth-wave.xml@sha256:44dd53629b87d8d8ae12b56631390f1f1a23473c0d0d8925dd06f8e9e5f821b5`.
- Input receipt: `raw/stage2/fourth-wave-inputs.json@sha256:3f770a8b13490921e24f65a44dde949bca9354e7d1e945ed00139038f8cf994f`.
- Freeze: `raw/stage2/fourth-wave-freeze.json@sha256:b70e032a9e269e3e817ef1344d5c1a06110d876a395296cbaada7d143aabfdd1`.
- Result: `raw/stage2/fourth-wave-result.json@sha256:f887e4c2b9cf2f2a0f618c7468c2d4b90eba1bbc6ea97ccdf47fb18926b034e7`.

The first generation raw driver observed both requested `[0,1,0]` sequences but
then failed while resolving metadata for pytest's fixture wrapper. Its overall
receipt is `UNRUN`, partial coverage: a harness failure, not a passing gate and not
a demonstrated product failure. Complete output is
`outliers/raw/stage2-generation-enforcement-removal.txt@sha256:98e4bfe098bfb4b7b7aabe6876fc7a6d6248569207e4449ebd30a7670fff3ea9`.
The preserved v1 driver has hash
`eb09eb988c1aa07baacce64a4d3b59e6821db0449fae2c36bb14558641566a1e`.

The v2 raw driver unwraps the fixture for actual source reads and emits a final
`COMPLETE` receipt only after both original assertions and final metadata complete;
any failure emits `UNRUN`, partial coverage and its actual error. It preserves the
v1 probe and scratch. Driver:
`outliers/raw/stage2_generation_enforcement_removal_v2.py@sha256:38d1af9a0df10c1e2e6345477b452dfa8644532414ca2dc2c8cf5025611a8919`.
At this checkpoint its deciding output and the movement probe against the revised
deferred supplier helper are pending. Root owns the final output hashes and
closeout disposition; the earlier movement proof remains bound to its earlier
recorded source and fixture bytes.

## Final movement settlement

The generation V2 and deferred movement removal probes completed with process
exit 0 and property-removal 0/1/0 results; their complete deciding output is
retained in the root Stage 2 journal. The subsequent eighth wave exercises real
supplier completion, separate native GY admission, Cycle Board projection and
retraction when required evidence is removed. See
[S2-V09](STAGE2.md#s2-v09--served-acquisition-and-separate-gy-movement-exercised)
and final [S2-C01](STAGE2.md#s2-c01--delivered-chain-and-exact-remaining-acts).
The approved generated trust companion has been refreshed and passes its owner
check. Exact Common tokenizer import admission remains with architecture. No
exhaustive inventory, improved design grade or register closure is claimed.
