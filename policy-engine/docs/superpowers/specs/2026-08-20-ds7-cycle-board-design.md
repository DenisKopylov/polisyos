# DS7 Cycle Board Hero Surface Design

## Status

Approved architecture, corrected 2026-08-20, ready for implementation planning
after review of this committed spec. DS7 promotes the existing DS3
`depth-n-cycle-board` projection from an unbound run-detail rendering to the
REVIEWER/EXPERT hero, strangling both old consumers and adding no parallel
board, owner, or static artifact. The board cannot fail the cycle; Cluster 0
uses `additive-and-declared` versus the `changed-or-removed` stop class and
holds the register lock only for receipt writes/commit. Search `terminal_kind`
and lifecycle `run_terminality` remain separate; `/runs/nl` is not a recursive
cycle; and TypeScript evidence is inadmissible until
`corepack pnpm install --frozen-lockfile` completes.

## Goal

Ship `/runs/cycle-board` as the only human rendering: three validated N10 runs,
then thirteen legacy fixtures, plus a typed coverage gap until the chronology
owner can enumerate future production recursive-cycle runs.

Rows render typed producer values/absences for both terminals, recomputed
evidence, weakest links, N7 route, owners, DS8/readiness, English safe copy and
movement. The visible ledger carries source availability, provenance, `as_of`,
freshness and absence route. MACHINE exports the exact packet; parity reads the
DOM.

## Non-goals

- No new static board artifact, projection identifier, client-side truth join,
  dashboard-owned semantics, chronology, or event log.
- No cycle failure caused by board recording/projection/enumeration; optional
  CAS/diagnostic recording remains non-blocking.
- No `/runs/nl` inflation and no conversion of missing lifecycle binding into
  `false`, `non_terminal`, or producer-signed `not_established`.
- No adjacent-count credit for a structural gap and no movement without a
  per-row acquisition → re-entry → deeper-terminal receipt.
- No PUBLIC surface before DS12, no DS8 workspace, no DS16 value grammar, and
  no edit to Atlas master-plan line 7.

## Measured starting point

At slice base `4456bb885`, `DepthNCycleBoardPayload` and
`ProjectionId.DEPTH_N_CYCLE_BOARD` already project N10 domain runs, terminal
distributions and recomputed evidence classes. The generated hook
`useDepthNCycleBoardProjection.ts` is fetched by `OverviewTab.tsx` and rendered
by `RunExplainabilityPanel.tsx`.

That placement is wrong for a global cohort: a run-detail route supplies no
binding between its `runId` and the global three-row capstone projection. DS7
therefore promotes and rehomes an existing surface; it does not construct a
parallel one.

“Supersedes proving-ground board” is historical: a P35 census must prove the
base has no such live route/component. `LEGACY_PROVING_GROUND` remains an input;
the hero supersedes a plan concept, not an unmeasured UI.

The pinned complete `GY-GAP` census covers one Markdown owner plan and returns
`GY-GAP1`–`GY-GAP4`; repeat it immediately before registering GAP5/GAP6 to
exclude a concurrent collision.

## Governing invariants

1. **Atlas projects, never owns.** Composition cannot manufacture authority,
   terminality, evidence, readiness, movement, or time (`S0-K07`, `P05`).
2. **Terminal facts stay separate.** Search `terminal_kind` and lifecycle
   `run_terminality` cannot derive each other or use status, `finished_at`,
   timestamps, polling, position, or acquisition as proxies.
3. **Absence stays absent.** “No exact row binding” is distinct from a bound
   producer value of `not_established`; neither becomes Boolean false.
4. **Owners recompute.** The N10 owner path recomputes evidence from grounding/
   value observations and validates the terminal; a read-only owner projection
   supplies blocking obligations. React only renders.
5. **Denominators and movement require receipts.** Until chronology is complete,
   the board labels known cohorts and its gap; recording failure cannot change
   a cycle result. Movement requires acquisition date, same-case re-entry, and
   deeper terminal.
6. **Structural gaps get no adjacent-data credit.** N13a's `not_a_data_gap`
   binds the capstone routes. Frontier remains control-plane evidence (`P25`).
7. **Time remains per source.** No synthetic global currentness is emitted.
8. **Server denies, UI reflects.** `RuntimePermission.RUNS_REVIEW` is the
   security boundary.

## Pattern pass and capability state

Relevant failure patterns are `P01`, `P02`, `P03`, `P04`, `P05`, `P08`,
`P10`, `P12`, `P15`, `P25`, `P27`, `P29`, `P31`, `P35`, `P37`, `P38`, `P40`,
and `P41`.

Measured states: the DS3 projection is `implemented`, while the hero and its
property test are `surface_missing`/`semantic_test_missing`; leaving the detail
renderer would be `P27`. Enumeration and per-row movement are
`absent/unallocated` (`artifact_missing` + `bridge_missing`). DS8 drill-down is
`consumer_missing`. Current Revision-3 readiness is `artifact_missing`; frozen
DS1 and worktree-scoped 5 available / 7 `invalid_source` / 1 `artifact_missing`
measurements are historical/environment-relative, never current authority.

## Cluster 0: GAP4 plus generated clients

Cluster 0 precedes all board work. It brings producer-signed lifecycle
terminality onto the DS7 branch without knowingly making the generated estate
stale.

### Toolchain gate

Before trusting any generated-owner scanner or TypeScript AST census, run:

```bash
corepack pnpm install --frozen-lockfile
```

A failed or killed install is a non-receipt. Missing workspace links must not
be converted into product findings.

### Atomic merge and regeneration

Merge `codex/gy-gap4-run-terminality` with `--no-commit`, preserving one final
merge commit for GAP4, generated outputs, and every invalidated receipt. Then
run the canonical owners:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml \
  python tools/ops_runners/runtime/export_runtime_openapi.py \
  --output schemas/runtime_api_v1.openapi.json
corepack pnpm --filter @polisyos/runtime-api-client run generate
corepack pnpm --filter @polisyos/runtime-dashboard run generate:api
```

The package generator's complete declared output family is accepted, including
its canonical/raw companions; the two required TypeScript client families are:

- `packages/runtime-api-client/types.ts`; and
- `apps/runtime-dashboard/src/api/types.ts`.

The existing lack of generated-artifact registry entries for package-side
canonical/raw companions is reported as an ownership-registration gap if the
complete owner census confirms it. DS7 does not silently invent ownership.

### Drift classification

After regeneration, parse both before and after client families with the
installed TypeScript toolchain and publish a table for each family containing:

- total exported-symbol count before and after;
- count of pre-existing exported symbols;
- count of pre-existing symbols occurring exactly once after regeneration;
- unchanged, changed, removed, and added symbol counts;
- unchanged, changed, removed, and added field counts by containing symbol;
- every governed anchor's before/after line and offset; and
- the distinct offset set for unaffected and post-insertion anchors.

Classification is exactly one of:

- **`additive-and-declared`:** the intended GAP4 addition introduces
  `RunSummary.run_terminality` and its producer-owned type surface; every
  pre-existing exported symbol occurs exactly once; every pre-existing field
  keeps the same normalized TypeScript shape; nothing is removed; and all
  affected post-insertion anchors share one mechanical offset while
  pre-insertion anchors remain at zero offset. This class may be re-anchored.
- **`changed-or-removed`:** any pre-existing symbol or field changes shape or
  meaning, disappears, duplicates, or exhibits non-mechanical anchor movement.
  This class stops the slice before any governed register lock is acquired or
  receipt is re-anchored.

“Semantic drift” is reserved for the stop condition and is not used to
describe the intended additive field.

### Register lock window

No register lock is held during dependency installation, merge preparation,
generation, or additive-drift proof. Only after the proof returns
`additive-and-declared` does DS7 announce and acquire the whole Atlas register
family lock.

The window begins immediately before the first governed receipt write. It
ends after the single Cluster 0 commit has been read back from the attached
branch and the governed hashes have been recorded. DS7 then explicitly
relinquishes the lock so DS6 can proceed. If later work needs the family, DS7
must acquire it again explicitly.

The lock begins from these main-tree identities:

- register `8de4da1e…934a65`;
- generated report `699c3b09…4ab72`;
- status inventory `70210513…572b5`;
- baseline manifest `08ae63cb…65d0d`; and
- readiness ledger `4b64f092…e2ae13`.

Within the window, re-anchor every receipt invalidated by the OpenAPI/client
addition, regenerate the register report, and verify all family members. The
register and status inventory may move for the GAP4 producer/client binding;
baseline and readiness bytes are expected to remain unchanged unless their
owners prove an induced change. If any governed member moves, every dependent
hash in the family is re-anchored in the same commit.

The final Cluster 0 commit includes the uncommitted GAP4 merge, OpenAPI, all
owner-generated client files, one structured unreleased fragment declaring
`generated_client_compatibility` for both changed client families, and all
governed receipt changes. The release owner classifies compatibility impact;
the fragment itself is mandatory. No intermediate merge commit is allowed.

## Baseline reds before mechanism

After Cluster 0 is committed and before writing any board mechanism, replay
the three named inherited reds from slice base `4456bb885` under `P41`. Record
the exact command, complete input denominator, base result, post-Cluster-0
result, and path-intersection proof.

The expected honest state remains:

- DS8 A4 print visual red with its expectation byte-unmodified;
- DS5 run-deck stable `1094x821` rendering against the governed `1094x820`
  baseline; and
- DS6-C11, the sole remaining component parity identity.

None may be reported green, skipped, or attributed to DS7 without a measured
change in ownership. A killed replay is a non-receipt, not evidence that a red
persists or clears.

## Projection architecture

### One projection identity, explicit inner/outer seam

Keep `ProjectionId.DEPTH_N_CYCLE_BOARD`, but distinguish its existing raw
owner packet from the promoted composed packet. An internal, non-route adapter
calls the unmodified
`GovernedProjectionService.get(ProjectionId.DEPTH_N_CYCLE_BOARD)` exactly once
and returns the current DS3 MACHINE owner packet. Only after that call returns
does a runtime HTTP `CycleBoardProjectionService` compose the raw packet with
sibling owner packets and signed `RunSummary` facts. It never requests the
static HTTP operation it is producing, so self-composition is impossible.

The outer static operation emits:

- `packet_schema_version = policyos.runtime.cycle_board_packet.v1`;
- `projection_id = depth-n-cycle-board`;
- `projection_rule_version = policyos.runtime.depth_n_cycle_board.v2`;
- the versioned `DepthNCycleBoardPayload` v2; and
- `intended_audiences = [REVIEWER, EXPERT]`.

The raw v1 packet retains `intended_audience = MACHINE`. In the outer v2
contract, “MACHINE twin” names the byte-identical JSON export channel, not a
third audience claim. No packet is asked to carry two incompatible meanings of
the singular v1 field.

The compositor consumes existing depth-N, legacy proving-ground, N13a
census/live-probe and readiness packet states, the realized DS4 disposition
owner (`27 package / 41 rebind / 18 use-as-is / 3 retire`), and exact-bound
`RunSummary.run_terminality` facts.

Every component enters as its full governed packet state: `available`,
`invalid_source`, or `artifact_missing`, including source identity, dependency
hash, `as_of`, and freshness where available. The outer source is explicitly a
composition manifest, never a fake artifact path. Its projection hash binds
the ordered component identities and complete payload; its dependency hash
binds available and absent component states, so missing, stale, or replaced
sources change replay identity.

`projection_observed_at` is only the server transaction time. It is not a
global data `as_of`. The outer packet makes no aggregate currentness claim;
each source ledger entry retains its own `as_of` and freshness.

No optional source failure becomes a whole-board 500 or false empty set. The
payload stays renderable with typed component absences, and `invalid_source`
is never downgraded to `artifact_missing`.

### Replay migration

An unpinned request receives the outer v2 packet. A request carrying the
complete legacy v1 replay-pin tuple is resolved by the internal raw adapter and
returns the byte-equivalent v1 packet under the same authorization gate; it is
never silently reinterpreted as v2. A complete v2 tuple binds the composition
manifest and returns v2. Partial or mixed-generation pins return the existing
typed replay conflict. Stable identity remains `depth-n-cycle-board`; replay
identity distinguishes the rule versions.

### Typed fact algebra

Fields that may be unknown use a discriminated union, not nullable defaults:

```text
AvailableFact[T]
  availability = available
  value = T
  source_ref
  source_as_of

AbsentFact
  availability = not_established | artifact_missing | invalid_source
  reason
  owner_route
  value is structurally absent
```

This algebra distinguishes:

- no lifecycle row binding (`AbsentFact(not_established)`);
- a bound lifecycle producer fact whose value is `not_established`
  (`AvailableFact[RunTerminality]`);
- an absent legacy runtime result (`artifact_missing`); and
- present source bytes rejected by their owner (`invalid_source`).

The generated client must preserve the discriminator. Presentation code may
format a value but cannot insert one into an absent branch.

### Row shape

`CycleBoardRow` carries stable row/cohort identity, typed DesignProblem and
optional cycle-run binding, separate search/lifecycle terminal facts,
recomputed evidence witness, ordered weakest links, the fully typed acquisition
route, responsible slices, DS8/readiness facts, explanation code/copy inputs,
and owner-bound movement records.

Cost and VOI values recorded as `None` in the N7 planner report become typed
`not_established` facts, never zeroes. Planner `ready` is a planning posture,
not proof of acquisition execution. An execution status requires the
acquisition producer's receipt.

## Denominator and cohort semantics

### Known rows

The order is stable:

1. N10 first vertical;
2. N10 education;
3. N10 unseen/no-pack; and
4. the thirteen legacy fixture cases in their owner manifest order.

The N10 rows have producer-owned design-search facts. Lifecycle terminality is
available only for a row with an exact `RunSummary` binding and is otherwise
absent. The legacy cohort is visibly `fixture_only`; legacy terminal,
lifecycle, evidence, route, and movement fields are typed absences because the
fixture manifest carries no persisted validator-confirmed runtime result.

`/runs/nl` jobs are excluded by property, not by a status or name denylist:
their producer does not invoke the canonical recursive generation cycle and
does not emit a bound `DesignProblem` cycle receipt.

### GY-GAP5: production recursive-cycle enumeration

The board cannot currently prove “one row per DesignProblem the cycle has ever
run.” It therefore renders a board-level coverage record before the cohorts:

```text
capability_state: absent/unallocated
missing_link: production_recursive_cycle_run_enumeration
deficits: artifact_missing + bridge_missing
owner_route: GY-GAP5 -> runtime/quality GY-N12 lane
execution_status: not_established
known_scope: N10 capstone + legacy fixture cohort
unknown_scope: future production recursive-cycle DesignProblems
```

Register `GY-GAP5` in the registered-gap section of the GY owner plan. Do not
edit line 7 of the Atlas master plan. Its real owner is the runtime/quality
GY-N12 lane because N12 already owns append-only epochs, current heads,
reissue, and the no-second-chronology rule. The generation-cycle producer may
add non-blocking started/resolved diagnostic events to the existing CAS/log,
but DS7 does not set a new cycle admission or completion gate.

Closure signal: from live production source, the owner can reproduce the
complete recursive-cycle run membership and chronology, bind each event to the
DesignProblem and cycle content identity, project current heads and resolved
terminal refs, detect deletion or post-hoc narrowing, and do so through the
existing chronology. Recorder failure never changes the cycle's terminal.

Until that closure is admitted, future rows are not fabricated and the known
row count is never labeled exhaustive.

### GY-GAP6: per-row movement binding

Movement is a separate plane and therefore a separate gap:

```text
capability_state: absent/unallocated
missing_link: acquisition_reentry_deeper_terminal_binding
deficits: artifact_missing + bridge_missing
producer_route: GY-GAP6 -> GY-N13b
chronology_route: existing GY-N12 append-only epoch owner
execution_status: not_established
movement_records: []
```

Register `GY-GAP6` in the registered-gap section of the GY owner plan. Do not
edit line 7 of the Atlas master plan. GY-N13b owns the acquisition and
same-cycle re-entry receipt; GY-N12 supplies the append-only chronological
composition. This does not assign either owner to Atlas.

Closure signal: one exact row binds an admitted acquisition receipt and date,
the same DesignProblem/cycle re-entry, and its deeper owner terminal; deleting
or substituting any member breaks the chain. The existing N13b global
`typed_deeper_terminal` result cannot be projected as per-row movement until
that binding exists.

## Evidence, missing-link, and acquisition honesty

The N10 owner already recomputes `evidence_witness.kind` from validated
grounding and value observations plus the canonical terminal. The server
projects that admitted witness. It neither trusts a free label nor
re-implements the GY classifier.

The board renders the terminal's ordered `blocking_obligations` as the exact
weakest-link set. It does not choose a convenient single string in React. The
semantic closure test invokes the canonical owner recomputation on the live
artifact, then compares those recomputed evidence and weakest-link values to
the composed packet and rendered DOM.

N13a's live result binds all three capstone routes as `not_a_data_gap`:

- first vertical: grounding relation or owner lever;
- education: estimand binding; and
- unseen/no-pack: grounding relation or owner lever.

The board may display N13a catalog availability in its source ledger, but no
observation, distribution, connector, or row count appears as progress on
those missing links. A decisive negative mutates adjacent counts upward while
holding the structural owner facts fixed; row evidence and movement must remain
byte-identical.

## Source ledger and readiness

The payload and visible hero list each source's identifier, provenance
(`live`/`replay`/`fixture_only`), availability, source/dependency identities,
`as_of`, freshness, authority/denied uses, and exact absence owner route.

The historical DS3 availability result of 5 available / 7 `invalid_source` /
1 `artifact_missing` is labeled as measured in a worktree without
`production_data`. It is never reused as a current denominator and never
called artifact corruption. In an environment without producers, the board
renders `invalid_source` and `artifact_missing` at the affected sources and
keeps its own claim correspondingly limited.

Frozen DS1 readiness, if referenced, is historical. Current readiness remains
`artifact_missing` until its Revision-3 owner and validator exist; route,
component, or board presence cannot derive it.

## Human surface and consumer disposition

### Hero route

Add the static dashboard route `/runs/cycle-board` before the dynamic
`/runs/:runId` route. Add it to the route/prefetch manifest and surface
registry with `permissionKey: "runs.review"`. Wrap the page in an explicit
permission boundary that resolves `usePermission("runs.review")` before the
data hook mounts. A settled `runs.view`-only principal sees the denied state,
triggers no Cycle Board fetch, and receives no hero or export link. The page is
a REVIEWER/EXPERT workspace hero, not a run-detail tab.

The hero shows coverage/movement gaps, both cohorts, source freshness, the
expandable refusal-with-a-path table, honest-empty movement, realized DS4
`27/41/18/3` disposition, and MACHINE export.

New copy is authored in `en`; `uk` receives the active translation; `ru`
remains `legacy_continuity_frozen` and is not silently re-authored.

### Existing consumers

Both existing human renderers are strangled:

1. `OverviewTab.tsx` stops calling `useDepthNCycleBoardProjection`.
2. `RunExplainabilityPanel.tsx` removes the governed projection prop and
   `GovernedDepthProjection` row rendering.

The run overview may retain a permission-filtered navigation link to
`/runs/cycle-board`, with copy explaining that the cohort is global and not a
fact about the current run. A link is not a second rendering or a second data
fetch.

The existing hook is reused by the hero, not cloned. A complete TS/TSX
import/call/render census must prove that exactly one production component
fetches and renders the projection after the strangle. Tests that existed only
to assert the in-panel rendering are replaced with strangle and navigation
proofs; they are not left as stale fixtures.

## Authorization and API shape

The server adds a static operation at the concrete existing URL
`/api/v1/exports/governed-projections/depth-n-cycle-board` before the dynamic
projection route. It returns the composed payload under the same projection
identity and is guarded by `require_action_permission` using the existing
`RuntimePermission.RUNS_REVIEW` and an owner-appropriate collection resource
binding.

Route ordering closes the generic dynamic sibling path for this literal. A
route census and authorization test must prove every HTTP path capable of
returning either raw or composed Cycle Board bytes enforces `runs.review`:
principals granted `RuntimePermission.RUNS_REVIEW` succeed and a
`RuntimePermission.RUNS_VIEW`-only viewer is denied by the server. Hiding the
page or export button is only a reflected UX behavior.

OpenAPI and both generated clients are regenerated for the composed payload
and protected operation. This later regeneration follows the same generated
family and receipt discipline as Cluster 0 and reacquires the Atlas register
lock only if it actually moves that family.

The static operation has the unique operation id
`get_depth_n_cycle_board_projection` and a distinct generated
`getDepthNCycleBoardProjection` method whose response union discriminates on
packet/rule version. `useDepthNCycleBoardProjection` switches from generic
`getGovernedProjection` to that method and accepts only the unpinned v2 branch;
v1 there is a contract error. A separate pinned replay path may return v1 and
never feeds the hero renderer.

## MACHINE twin and DOM parity

The MACHINE export downloads the exact typed packet returned by the server.
It does not reconstruct JSON from localized labels, table state, or a second
client model.

One pure `packetToVisibleCycleBoard` presentation projection maps the outer
packet to visible semantics without recomputing any owner fact. Every rendered
semantic region exposes its stable raw typed data in the DOM alongside
localized text. The parity test renders the real page, decodes the DOM, and
compares the complete result to that projection over coverage gap, movement
gap and empty denominator, DS4 disposition, source ledger, cohorts, rows, and
row facts. A separate assertion keeps the downloaded JSON byte-equivalent to
the request packet.

Parity fails on dropped/duplicate rows, defaulted absences, localized values in
raw slots, omitted sources, unrecorded movement, or export/packet mismatch.

## Required red-first semantic tests

Mechanism work begins only after property tests fail for these reasons:

1. novel status/`finished_at`/time proxies cannot move signed lifecycle truth;
   removing the fact supplies no value;
2. an unbound lifecycle renders absent, never false, `non_terminal`, Boolean,
   or defaulted producer `not_established`;
3. search terminal and lifecycle terminal mutations are independent;
4. canonical recomputation equals packet and DOM evidence/weakest links over
   all N10 rows; corrupting either projection fails;
5. increasing adjacent data counts cannot change structural claims or motion;
6. `/runs/nl` and unbound jobs cannot inflate the explicitly non-exhaustive
   denominator;
7. global N13b state cannot populate an empty per-row movement collection;
8. `runs.review` succeeds, `runs.view`-only server/direct-page access fails,
   and no denied query mounts;
9. run detail neither fetches nor renders the board; its link only navigates;
10. complete visible semantics equal the typed packet/export;
11. environment absence and source times render without synthetic currentness;
12. PUBLIC navigation and viewer/public access stay closed before DS12.

## Values, refusals, and DS16

DS7 renders producer values for status-like and structural fields: terminal
kind, lifecycle terminality when bound, evidence class, missing-link identity,
planner strategy, and source state. It renders typed refusals and gaps for the
three capstone rows, typed absences for legacy/runtime/movement/readiness fields,
and no authorized policy quantity, effect estimate, welfare value, or
`ValueOuterSet` result.

Therefore DS7 does **not** satisfy DS16's re-entry property “a surface exists
that renders policy values rather than refusals.” DS16's grammar is not
scheduled by this slice merely because enum/string fields have values.

## Execution discipline

Commit order is: spec; atomic Cluster 0 and lock release; inherited-red
receipts; GY-GAP5/GAP6 registration outside Atlas line 7; red tests; server
composition/auth; generated clients/receipts under a newly announced lock if
needed; hero plus consumer strangle; MACHINE parity; freeze/review; one wave;
closure/read-back. Corrections append; no rebase, force-push, stash storage,
push, or main merge.

Clusters start `0/2`; bucket P40 findings before repair. Freeze before full
review and keep later packages delta-only near 28KB. Serialize only
Playwright/visual, Storybook, fixed-port server, and the same governed
`atlas_surfaces` writer; run lint, typecheck, logic, build, architecture, and
read-only censuses in parallel. Root alone edits/launches heavy work. Record
completed time, preset timeout, and 1.6-2.0x host contention for every suite;
kills are non-receipts, completion admits a sample, and ceilings never widen
mid-run.

## Closure record

Handback proves: Cluster 0's single commit, two-family counts/receipts, and
short lock window; one human renderer; canonical evidence/weakest equality;
no lifecycle proxy/default; no adjacent-count credit; owned GAP5/GAP6 and empty
movement; source-relative absence/time; DOM/export parity; realized DS4
`27/41/18/3`; unchanged DS8 A4, DS5 `1094x821`, and DS6-C11 reds; no policy
quantity/value and therefore no DS16 re-entry; branch read-back and no push or
main merge. The historical proving-ground claim cites its exact command,
tracked path/file-type denominators and matches, then records
`documentation-only historical concept; no production route/component`.
