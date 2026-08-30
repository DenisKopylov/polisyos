# DS11 Trust Posture Debt Closure Journal

Date: 2026-08-30

Branch: `codex/debt-d-ds11-trust-posture`

Supplied base: `784d020148c56e9bfb3a3631909ba11232210a9f`

Worktree: `.worktrees/debt-d-ds11-trust-posture/policy-engine`

## Entry 1 — Intake and binding

- `git status -sb` exited 0 with
  `## codex/debt-d-ds11-trust-posture`; `git symbolic-ref --short HEAD` returned the
  same branch; `git rev-parse HEAD` returned the supplied full base SHA.
- Read all ten DS11 debt rows in `DEBT-REGISTER.md` without modifying that file.
- Read `CONTRIBUTING.md`, the failure/repair register, the ratified identity/custody
  boundary, Stage-0 custody kernel, Wave-5 evidence-substitution ratification, the DS11
  plan section, DS12 promotion gate, and the DS6/DS9 Atlas slice models.
- The named-test census over the complete ten-row set found eight missing test files and
  one existing C13 test file; the lifecycle row and seven other rows name unwritten
  pytest modules, while the C13 conjunction node exists. This is a closure-work census,
  not a defect census.
- `uv sync --frozen` exited 0 and provisioned the worktree-local `.venv`.
- `corepack pnpm install --frozen-lockfile` exited 0 and provisioned workspace links.

## Entry 2 — Read-only capability audit

### Lifecycle authority boundary

The production control-plane path calls both lifecycle bridges and injects a same-store
`EpochClaimLifecycleBridgeService`. The monitor arm resolves the current ledger and
persists a `LifecycleBridgeResult`, but it intentionally maps a raw monitor event only to
`review_required`. It neither derives nor content-binds a successor claim. Even completed
batches reject a superseded status when the successor is not independently established.

The exact lifecycle closure test therefore must distinguish two properties:

1. monitoring is genuinely orchestrated and persisted; and
2. supersession is authorized by verified successor evidence without editing the
   predecessor in place.

The first property is implemented. The second is not established by a monitor event.
Making it green from event metadata would be P05/P32 and violate W5-K06. The test will be
written against the real path and allowed to expose this boundary.

### Public custody chain

- The published-signature watcher has no scheduled producer that can enumerate a
  non-vacuous typed population, recompute staleness independently, persist an event, and
  reach the public custody surface.
- The first public-signature population is gated by DS12's first governed promotion.
  Task A cannot make that promotion reachable while the EFFECT investigation remains
  open.
- The grounded-performance row is likewise blocked outside DS11 by the same chain:
  EFFECT investigation → GY-PR1 → first governed promotion → DS12 record half.
- A watcher over an empty or caller-declared population would be a vacuous P29/P37 gate
  and will not be implemented.

### Accessibility and public copy

- The recorded external accessibility artifact is historical, internal, and explicitly
  says vendor countersignature is pending. It cannot close the external-countersign row.
- The current page-a11y suite has a measured 25-test scope. The recorded current failure
  classes concern color-token distinguishability, `dlitem` structure, and an accessible
  export-action expectation; the suite will be remeasured before edits.
- `/trust` renders public claim rows from the generated posture artifact, and the landing
  page has one neutral entry to `/trust`. General-copy verification will bind that actual
  owned denominator rather than search arbitrary source strings.
- A `RunReportPage.tsx` edit changes a source member of the C13 receipt conjunction. Task
  C must reissue its receipt against Task D's final bytes; Task D will not claim both
  halves from one side.

### Scope adjudication

No typed scope-adjudication record, producer, persisted artifact, resolving consumer, or
semantic test currently exists. The planned smallest correct capability is a one-plane,
four-way deterministic producer whose authority predicate is recomputed or independently
reconciled, then content-bound and reverified by its consumer. Mixed planes and declared
but unestablished predicates must fail closed.

## Entry 3 — Initial pattern classification

- Lifecycle supersession: `authority_input_missing`; relevant patterns P04, P05, P09,
  P29, P32, P37 and W5-K06.
- Watcher: `producer_missing`, with blocked population prerequisite; P01, P02, P12.
- Population: `blocked` on external promotion gate; P05, P15.
- Scope adjudication: `absent/unallocated`; P01, P05, P32, P37.
- External countersign: `artifact_missing`, `verification_missing`; P14, P32.
- Current page a11y: `artifact_missing`, `verification_missing` for current evidence;
  P03, P10, P29, P35 and W5-K02.
- General copy: bounded residual; P03, P10, P29, P35 and W5-K06.
- Grounded performance: `blocked`; P05, P10, P15.
- C13 receipt: DS11 source half pending final bytes; task C receipt half pending reissue;
  P12, P29, P32.
- Full trust-center/docs IA: `surface_out_of_scope`; P03, P13.

The implementation plan and Atlas slice plan were written before source changes. No
mechanism or test source has been edited at this point.

## Entry 4 — Lifecycle closure node and authority stop

- The first runner probe,
  `.venv/bin/python -m pytest tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py::test_monitor_event_persists_claim_supersession_without_in_place_edit -q`,
  exited 1 before collection because plain `uv sync --frozen` did not install the
  optional `test` extra. The repository baseline in `CONTRIBUTING.md` requires
  `lint + test + runtime`.
- `uv sync --frozen --extra lint --extra test --extra runtime` exited 0. The same exact
  node then exited 4 because the named file did not yet exist, which is the expected
  red-first state for this open debt.
- The named integration test now drives the real authenticated control-plane route,
  same-store lifecycle bridge, persisted monitor event, persisted bridge result, and
  immutable predecessor ledger bytes.
- A first harness run exited 1 because the unit/runtime subtree fixture is not inherited
  by an integration test. The test now wraps the repository's canonical
  `build_runtime_api_env`/`close_runtime_api_env` helpers locally.
- A first model run exited 1 before orchestration because `GovernanceMonitorEvent`
  correctly rejects `metadata.lifecycle_transition` as caller-authored authority. The
  closure test no longer supplies that prohibited field.
- The resulting exact semantic run exited 1 after traversing the production path. The
  predecessor bytes were unchanged and the bridge result resolved from CAS, but the
  persisted lifecycle action was `review_required`; the closure predicate required
  `superseded`.
- Root cause: the monitor arm has no independently resolved, content-bound successor
  claim or owner adjudication. A candidate successor identifier in event metadata is not
  authority. The current behavior is the intended P05/P32 fail-closed boundary, not an
  implementation defect to bypass.
- Provisional verdict for `DS11-CLAIM-LIFECYCLE-ORCHESTRATION`: `open` with
  `authority_input_missing` for supersession. The implemented monitor orchestration and
  persisted `review_required` path remain verified; the row's stronger supersession
  predicate does not.
- Task B retains only the `GY-GAP8` verification-denominator repair and its three named
  tests. Task D made no change to that denominator or to lifecycle production source.
- `.venv/bin/python -m ruff check
  tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py` exited 0
  after import normalization.
