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

## Entry 5 — Scope adjudication capability

- Register identity correction: the exact node is
  `tests/unit/core/contracts/test_scope_adjudication.py::test_four_way_ruling_is_produced_consumed_and_plane_specific`.
  Two planning paraphrases for other rows were also corrected additively in the plan;
  no register row was edited.
- `uv run --frozen pytest
  tests/unit/core/contracts/test_scope_adjudication.py::test_four_way_ruling_is_produced_consumed_and_plane_specific
  -q` first exited 4 because the module did not exist, then exited 0 after implementation.
- The Core module now supplies a strict one-plane request, three ordered P37 predicate
  receipts, the four-way ruling, a typed nonreceipt with no ruling, exact CAS persistence,
  an injected verifier-evidence resolver, deterministic disposition, and a consumer that
  re-resolves bytes/manifests/lineage and replays the rule before admission.
- Predicate authority is not inferred from the ratified Markdown. The architecture-owned
  resolver is injected, and its verifier appointment, target, rule, evidence, and
  provenance are all content-bound. Only `recomputed` and `independently_reconciled`
  predicates needed to reach the branch may carry a positive ruling.
- `uv run --frozen pytest tests/unit/core/contracts/test_scope_adjudication.py -q`
  exited 0 with four tests: the four-outcome/priority path, mixed-plane nonreceipt,
  consumer-asserted predicate nonreceipt, and shaped-record-ref rejection.
- `.venv/bin/python -m ruff check
  src/polisyos/core/contracts/scope_adjudication.py
  tests/unit/core/contracts/test_scope_adjudication.py` exited 0.
- `uv run --frozen mypy src/polisyos/core/contracts/scope_adjudication.py` exited 0.
- `uv run --frozen pytest
  tests/repo_quality/architecture/test_public_api_facades.py -q` exited 0 over its
  three-test facade blast radius.
- `uv run --frozen polisyos-tools architecture guardrails check` exited 1 only when the
  generated-artifact freshness phase compiled the pre-existing trust-posture register and
  reported `ratified identity basis differs from the admitted closed receipt`. The scope
  module and test are not trust-posture compiler inputs. P41 classification remains
  `not_established` until the exact guardrail command is replayed from the supplied base;
  it is not yet labelled inherited.
- Provisional verdict for `DS11-SCOPE-ADJUDICATION-RECORD`: `closed`. Measured chain:
  typed contract + independently supplied predicate producer port + persisted predicate
  and adjudication artifacts + CAS lineage bridge + replaying consumer + typed
  nonreceipt + audit artifact surface + negative semantic tests.

## Entry 6 — First current page-a11y measurement

- A read-only lane ran exactly
  `corepack pnpm --filter @polisyos/runtime-dashboard run test:a11y:pages` without
  snapshot/update writer flags. It exited 1 after 5.7 minutes with the complete current
  denominator `25 collected = 22 passed + 3 failed`.
- The failing identities were the color-blind distinguishability test, run-report axe
  test, and run-report screen-reader test. In this invocation all three failed before
  their substantive assertions because `waitForDashboardSurface(..., "run-report")`
  timed out after 30 seconds with no `run-report-page` test id.
- This invocation therefore does not establish that the historical token, `dlitem`, or
  export-name predicates currently fail. The immediate root-cause subject is run-report
  fixture/surface availability; source fixes for the historical predicates remain
  unjustified until that shared setup failure is diagnosed.
- The no-update runner wrote only harness evidence beneath
  `_build/apps/runtime-dashboard/`: the fixture runtime JSON, `.last-run.json`, and one
  failure directory per identity containing context, screenshot, trace, and video. No
  dashboard source or snapshot was edited.

## Entry 7 — Bounded public-copy closure node

- `uv run --frozen pytest
  tests/repo_quality/frontend/test_public_claim_copy_inventory.py::test_every_public_capability_assertion_resolves_to_claim_posture
  -q` first exited 4 because the exact row-owned node did not exist.
- The closure node executes four existing behavioral witnesses through the real frontend
  toolchain: strict `/trust` loading/rendering, generic artifact-row free growth, exact
  PUBLIC DOM-twin parity with negative mutations, and route composition with exactly one
  neutral landing entry pointing to `/trust`.
- The complete owned denominator is the rendered `/trust` feature plus that single
  landing entry. The other `/welcome` content and the signed-decision viewer are outside
  this row's declared bounded residual; this node makes no general website-copy claim.
- The exact node then exited 0. No dashboard source was changed to obtain that result.
- Provisional verdict for `DS11-GENERAL-COPY-SEMANTICS`: `closed` for its bounded
  denominator. Arbitrary future public copy remains explicitly outside the predicate.

## Entry 8 — C13 handoff and first a11y root cause

- The exact C13 conjunction node exited 1 at the first stale current-byte binding,
  `AmbientTelemetryHud.tsx`, consistent with task C's complete `5/11 current + 6/11
  stale` receipt census. This is the receipt half of the declared overlap, not evidence
  against the source behavior itself.
- Task C handed the dashboard corridor owner one source repair: Node 22 could not collect
  the governed print selection because the two static locale JSON imports lacked import
  attributes. Both imports now use `with { type: "json" }`; the dashboard typecheck exits
  0. The governed print selection and receipt reissue still remain to be run against the
  final source bytes.
- The first current page-a11y trace independently exposed a different setup defect. The
  generic `core_run_id` is intentionally rejected by `GET /paper` with HTTP 409 because
  its terminal manifest has no unique run-bound `DesignRecord`. The page correctly
  renders an unavailable state, so extending the wait or weakening the endpoint would
  test the wrong property. A real bound paper fixture is required before the three
  substantive accessibility predicates can be measured.

## Entry 9 — Independent review corrections and page-a11y source freeze

- Independent review classified the scope-adjudication exact node as the same P32/P37
  class one level deeper: its fixture self-authored outcomes and labelled them
  `independently_reconciled`; no production resolver, orchestration consumer, or surface
  existed in the complete 2,612-file Python census. A separate P08 finding showed that
  validity time and knowledge time were initially conflated. The time roles were split,
  but that did not close the missing authority chain. The module and exact test were then
  forward-removed so the open row again has its honest unwritten closure signal. The
  exact register node exits 4.
- The copy node was the same P29/P38 class one level deeper: it enumerated four existing
  tests rather than deriving the complete owned copy denominator. An unsupported change
  to untagged frame/methodology/accessibility/non-default-locale copy would remain green.
  The node was forward-removed; the exact register node again exits 4 and the bounded
  residual remains open.
- The lifecycle exact red was independently confirmed as an authority boundary, not a
  fixture omission. The monitor arm always projects an actionable event to
  `review_required`, the completed-batch target has no successor ref/hash, production
  installs an unappointed Claim owner, and `append_verified_owner_event` is a stub. The
  smallest missing capability is a persisted owner adjudication that binds current head,
  predecessor, independently verified successor bytes, provenance, and evidence, plus a
  resolving CAS head advance. The exact node remains red/open.
- The first dashboard fix used different visible and accessible export names. A new P38
  falsifier failed, then the `aria-label` override was removed so both audiences receive
  the truthful visible action `Export MACHINE packet`. The focused Vitest pair passed
  31/31 and the exact screen-reader identity passed 1/1.
- The S2 report fixture initially altered every Playwright/visual run population. A new
  opt-in behavioral test failed before implementation. The fixture is now gated by the
  dedicated `PLAYWRIGHT_INCLUDE_BOUND_RUN_PAPER_FIXTURE=1` ->
  `--include-bound-run-paper-fixture` bridge, enabled only by `test:a11y:pages`; the
  existing visual fixture flag does not enable it. The producer/default-population tests
  pass 2/2, dashboard typecheck exits 0, Ruff exits 0, Prettier exits 0, and the three
  directly affected Playwright identities pass 3/3.
- Dashboard source is frozen at `6af7be1fc`. The current receipt will be the bounded audit
  surface required by the register signal. The existing `/trust` projection remains
  conservatively historical/blocked; the unowned posture compiler and generated posture
  are unchanged, so the audit receipt cannot silently become a broader public claim.
