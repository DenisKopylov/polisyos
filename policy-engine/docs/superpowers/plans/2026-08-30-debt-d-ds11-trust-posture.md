# DS11 Trust Posture Debt Closure Implementation Plan

> Execution uses `superpowers:executing-plans`; every closure claim is checked with
> `superpowers:verification-before-completion` before hand-back.

**Goal:** Resolve the ten DS11 trust-posture rows as far as their current authority,
producer, evidence, bridge, consumer, verification, and surface chains permit, without
turning conformance evidence into claims about human behaviour or presentation into
source-language authority.

**Architecture:** Reuse the existing custody, lifecycle, claim-posture, dashboard, and
receipt paths. Add only missing producers or behavioral verification where a complete
chain exists. Preserve `review_required` at the monitor boundary until an independently
resolved successor claim is content-bound. Treat DS12 promotion and external
countersignature as external prerequisites, not states DS11 may synthesize.

**Tech stack:** Python 3.14, Pydantic v2, pytest, TypeScript/React, Vitest,
Playwright, pnpm workspaces, content-addressed artifacts, Atlas disposition receipts.

**Authoritative brief:** User-approved Task D — DS11 trust posture, received
2026-08-30. The debt register is read-only; the architect transcribes the final dossier.

## Global constraints

- Work only on branch `codex/debt-d-ds11-trust-posture` in the supplied worktree at
  base `784d020148c56e9bfb3a3631909ba11232210a9f`.
- Never edit `DEBT-REGISTER.md`, `LEDGER.md`, the GY layer-3 slice, the Atlas master
  plan, or `PUBLISHED_DENOMINATORS`.
- `apps/runtime-dashboard/**` is the exclusive DS11 write corridor for this wave;
  source edits there must remain narrowly tied to the measured page-a11y failures.
- The shared public-export test and dependency module are append-only if needed.
  No shared fixtures, existing tests, or dependency blocks may be reordered.
- Write a named closure test red before implementation. A missing test is evidence of
  an open row, not a repository defect.
- Run exact nodes and importer/blast-radius checks only. Directory-wide and full-suite
  test runs are forbidden.
- Commit at each clean, coherent boundary after verifying branch attachment.
- Receipt and register history is append-only. Reissue into a new content-bound record;
  never rewrite an earlier receipt or register statement.

## Pattern pass

- **P04/P05/P09/P15:** A monitor event may require review, but it cannot itself mint
  authority for a superseding claim. Preserve the status lattice and authority band.
- **P01/P02/P12:** A row closes only with contract, producer, persisted artifact/event,
  orchestration bridge, consumer, verification, and a public/audit surface or an
  explicit `surface_out_of_scope` ruling.
- **P03/P10:** Rich internal state is insufficient; the public projection must expose
  the precise bounded posture and must not imply human comprehension.
- **P29/P32/P33:** Closure tests execute the real production path and resolve,
  content-bind, and verify evidence. No marker, filename, keyword, or self-attestation
  test may stand in for the property.
- **P35/P37/P38:** Set claims state their complete denominator; gate predicates record
  whether they were recomputed or independently reconciled; proxy predicates do not
  carry authority.
- **P39/P40/P41:** Plans, journals, receipts, and tests are mandatory companions rather
  than mechanism-path budget; repeated escapes are classified by failure class; an
  inherited red is accepted only after replay on the supplied base and denominator
  disjointness.
- **W5-K02/W5-K06:** Current page conformance is not human behaviour, and translated or
  presented text is not source-language authority.

## Provisional row classification

| Row | Starting state for execution | Closure condition used in this plan |
| --- | --- | --- |
| `DS11-CLAIM-LIFECYCLE-ORCHESTRATION` | `consumer_present`, `bridge_present`, `authority_input_missing` for supersession | The exact test must prove a verified successor is persisted and the predecessor bytes are unchanged. If the real path only records `review_required`, keep the row open and name the missing successor binding. |
| `DS11-INHERITED-C13-PRINT-RECEIPT` | conjunction test present; receipt reissue owned by task C | Close only if task C's reissued receipt binds the final DS11 source bytes and the exact conjunction node is green. Otherwise leave this half open and state task C's missing half. |
| `DS11-CURRENT-PAGE-A11Y` | current suite has three named failure classes and a historical receipt | Repair the real page semantics, obtain two independent no-update runs with identical collected identities, and append a current content-bound receipt. |
| `DS11-PUBLIC-SIGNATURE-POPULATION` | `blocked` | Keep blocked until task A's EFFECT investigation permits DS12's independent promotion gate; do not substitute a candidate record. |
| `DS11-EXTERNAL-A11Y-COUNTERSIGN` | `artifact_missing`, `verification_missing` | Keep open unless a current, scope-exact, independently issued, content-bound external countersign is actually received. |
| `DS11-PUBLISHED-SIGNATURE-WATCHER` | `producer_missing` and population prerequisite blocked | Close only if a real scheduled producer enumerates a non-vacuous typed population, recomputes staleness, persists an event, crosses the bridge, and reaches the custody surface. |
| `DS11-FULL-TRUST-CENTER-AND-DOCS-IA` | `surface_out_of_scope` | Verify the retained-route disposition against the real route inventory; do not build a new documentation subsystem. |
| `DS11-SCOPE-ADJUDICATION-RECORD` | `absent/unallocated` | Add a strict one-plane, evidence-bound adjudication record, producer, persisted reference, resolving consumer, and negative mixed-plane/unestablished-predicate tests. |
| `DS11-GENERAL-COPY-SEMANTICS` | bounded residual | Verify the real rendered `/trust` and landing entry projections against the admitted posture over their complete owned denominator; do not generalize to arbitrary future copy. |
| `DS11-GROUNDED-PERFORMANCE` | `blocked`, out of DS11 | Keep blocked on task A and the open EFFECT investigation; the exact test, if added, must remain red until a real governed promotion exists. |

## Task 1: Establish the execution record

**Files:**

- Create: `docs/superpowers/plans/2026-08-30-debt-d-ds11-trust-posture.md`
- Create: `docs/superpowers/journals/2026-08-30-debt-d-ds11-trust-posture.md`
- Create: `docs/plans/active/atlas-slices/DS11-trust-posture-debt-closure.md`

1. Record branch, full base SHA, toolchain receipts, all ten debt rows, overlap ownership,
   prohibited files, and the complete named-test census.
2. Record the initial capability labels and W5/Stage-0 authority constraints.
3. Self-review for ambiguous language, proxy gates, incomplete paths, and unstated
   denominators.
4. Verify branch attachment and commit the planning boundary.

## Task 2: Exercise claim lifecycle orchestration first

**Files:**

- Create: `tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py`
- Inspect only unless a lawful bridge defect is found:
  `src/polisyos/scientist/orchestration/orchestrator/run_lifecycle.py`
- Inspect only unless a lawful bridge defect is found:
  `src/polisyos/scientist/governance/lifecycle_bridge.py`

1. Run the exact absent node and record pytest's collection failure.
2. Write
   `test_monitor_event_persists_claim_supersession_without_in_place_edit` against the
   real control-plane producer, same-store bridge, and persisted ledger.
3. Snapshot the predecessor reference and bytes before the monitor event. Require a
   distinct successor/head reference, predecessor linkage, generation advance, and
   unchanged predecessor bytes.
4. Run the exact node red. Diagnose whether the red is an implementation defect or the
   intended authority boundary.
5. Do not make the test green by trusting monitor metadata. If verified completed-batch
   evidence does not establish a successor, retain the honest red/open verdict and name
   the smallest missing authority-bearing input.
6. Record task B's remaining `GY-GAP8` denominator work separately from this row.

## Task 3: Build the scope-adjudication record as a complete small capability

**Files:**

- Create: `tests/unit/core/contracts/test_scope_adjudication.py`
- Create or extend: `src/polisyos/core/contracts/scope_adjudication.py`
- Modify only if required for the public typed surface:
  `src/polisyos/core/contracts/__init__.py`

1. Write the exact test
   `test_scope_adjudication_producer_persists_and_consumes_all_four_outcomes` red.
2. In the same test module add negative cases for mixed planes, caller/institutionally
   supplied gate predicates, content substitution, and reference mismatch.
3. Implement strict enums and DTOs for one adjudication plane, the four-way ruling,
   predicate-establishment class, authority purpose, provenance, schema/rule version,
   and relevant time semantics.
4. Implement a deterministic producer that derives the ruling from the four-way test,
   persists a content-bound record, returns its typed reference, and fails closed on
   unestablished predicates.
5. Implement the resolving consumer that verifies kind, schema, digest, candidate,
   plane, and rule version before returning the ruling.
6. Run the exact node, all new negative nodes, direct importer tests, Ruff on changed
   Python paths, and architecture guardrails for the changed boundary.
7. Commit the complete capability only when the exact behavioral chain is green.

## Task 4: Repair current page accessibility and reissue its evidence

**Files:**

- Modify only as demonstrated by the suite:
  `apps/runtime-dashboard/src/test/a11y/color-blind-simulation.spec.ts`
- Modify only as demonstrated by the suite:
  `apps/runtime-dashboard/e2e/a11y/routes.a11y.spec.ts`
- Modify only as demonstrated by the suite:
  `apps/runtime-dashboard/src/test/a11y/screen-reader-snapshots.spec.ts`
- Modify only as demonstrated by the suite:
  `apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx`
- Modify only as demonstrated by the suite:
  `apps/runtime-dashboard/src/shared/theme/theme-light.css`
- Create: `tests/repo_quality/docs/test_accessibility_evidence.py`
- Append a new receipt under:
  `docs/plans/active/atlas-slices/receipts/`
- Regenerate governed dashboard artifacts through their owner command; never hand-edit
  files under `packages/**`.

1. Run
   `corepack pnpm --filter @polisyos/runtime-dashboard run test:a11y:pages` with no
   snapshot/update writer and retain the full collected identity list and failure output.
2. Use systematic debugging to establish the root cause for each observed failure.
3. Make the smallest semantic fixes: preserve valid `dl` ownership for terms, preserve
   the accurate accessible action name, and increase actual token distinguishability.
4. Run each affected Playwright/Vitest identity directly before rerunning the page suite.
5. Add
   `test_current_page_conformance_receipt_is_fresh_scope_exact_and_content_bound` red
   against a new append-only receipt. Bind the two complete run records, identical
   collected identities, current source/config digests, scope, tool versions, and the
   explicit W5 limitation.
6. Reissue the receipt and the generated/public posture only through existing owners.
   The public text may claim current scoped conformance, never human comprehension or an
   external countersignature.
7. Run two independent no-update page-suite invocations. Both must exit zero and their
   collected identity lists must be byte-identical after canonicalization.
8. Run the exact receipt node and the trust-posture compiler/checker with a corrupt-field
   drift probe that must fail.
9. Record that modifying `RunReportPage.tsx` changes the C13 conjunction bytes and hand
   task C the exact final source dependency for its reissue.

## Task 5: Verify bounded public copy and retained route disposition

**Files:**

- Create: `tests/repo_quality/frontend/test_public_claim_copy_inventory.py`
- Create: `tests/repo_quality/frontend/test_public_surface_claim_ownership.py`
- Modify dashboard tests or components only if the real rendered behavior violates the
  admitted posture.

1. Write `test_all_trust_claim_bearing_copy_uses_the_posture_artifact_or_is_neutral`
   red against the rendered `/trust` page and the complete owned landing-entry
   denominator.
2. Require every rendered claim-bearing row to come from the generated posture artifact;
   allow the single landing entry only when it remains neutral and points to `/trust`.
3. Write `test_retained_ds11_routes_have_public_claim_owners_and_evidence_requirements`
   red against the real route inventory and the ratified retained/disposed route set.
4. Prove no out-of-scope documentation route is made authoritative by mere presence or
   copy. If the current inventory already satisfies the disposition, close by verification;
   otherwise retain `surface_out_of_scope` and name the missing owner/evidence contract.
5. Run both exact pytest nodes and the directly implicated dashboard route-contract tests.

## Task 6: Preserve blocked and externally dependent rows

**Files:**

- Optional red-only closure specifications:
  `tests/integration/runtime_quality/test_first_governed_promotion.py`
- Optional red-only closure specifications:
  `tests/integration/runtime_quality/test_published_signature_custody.py`
- Do not modify public/runtime dependencies merely to make these tests pass.

1. Reconfirm that task A has not closed the EFFECT investigation and that DS12's
   independent promotion gate remains unreachable.
2. Keep `DS11-PUBLIC-SIGNATURE-POPULATION` and
   `DS11-GROUNDED-PERFORMANCE` blocked. If their named nodes are written, execute them
   red and record the exact missing governed promotion chain.
3. Inspect for a current external accessibility countersign over the exact current
   scope. A historical, internal, unsigned, differently scoped, or self-issued artifact
   is inadmissible; keep `DS11-EXTERNAL-A11Y-COUNTERSIGN` open if none exists.
4. Do not implement a vacuous watcher against an empty population. Keep
   `DS11-PUBLISHED-SIGNATURE-WATCHER` open unless a non-vacuous population and the full
   scheduled event-to-surface chain are present.

## Task 7: Reconcile the C13 overlap and close out

**Files:**

- Modify only the DS11 conjunction file if the verifier itself is defective:
  `architecture/atlas_surfaces/test_frontend_disposition_register.py`
- Append final evidence and the ten-row dossier to:
  `docs/superpowers/journals/2026-08-30-debt-d-ds11-trust-posture.md`

1. Run the exact C13 conjunction node before and after dashboard source changes.
2. If task C provides a receipt for the final DS11 bytes, verify it rather than copying
   its assertion. Otherwise record task C's exact remaining reissue obligation.
3. Ask an independent reviewer to classify findings by P40 bucket and perform delta-only
   review after any blocking repair.
4. Run every named node added by this task, the affected dashboard tests, Ruff on changed
   Python files, relevant TypeScript checks, architecture guardrails, and the two required
   repository checks:

   ```bash
   PYTHONPATH=. .venv/bin/python tools/quality/validation/check_debt_ledger.py --check
   PYTHONPATH=. .venv/bin/python tools/quality/validation/check_docs_lifecycle.py
   ```

   The ledger checker must exit zero under the bound interpreter. Docs lifecycle must
   reproduce exactly six findings.
5. Re-read changed files and the branch attachment after writing them. Commit each final
   clean boundary without rewriting history.
6. End the journal with one dossier block for each of the ten rows: verdict, exact
   command or predicate and exit code, and exact append-only prose for the architect.
7. State measured arithmetic as `10 rows = closed + open + blocked + ambiguous`, list
   every changed dashboard file, identify the precise task B and task C overlap residue,
   and name out-of-scope findings without acting on them.

## Execution identity corrections — appended 2026-08-31

The read-only debt register is authoritative for closure-node identity. Three proposed
names above were planning paraphrases, not register identities. Execution uses only:

- `tests/unit/core/contracts/test_scope_adjudication.py::test_four_way_ruling_is_produced_consumed_and_plane_specific`
- `tests/repo_quality/frontend/test_public_claim_copy_inventory.py::test_every_public_capability_assertion_resolves_to_claim_posture`
- `tests/repo_quality/frontend/test_public_surface_claim_ownership.py::test_every_retained_trust_docs_route_has_an_approved_owner_and_evidence_contract`

The earlier proposed names are retained as historical plan text and are not closure
signals.

## Receipt-surface correction — appended 2026-08-31

Execution established that the existing public-posture compiler is hard-bound to the
historical blocked page-a11y receipt and is outside Task D's declared write corridor. The
authoritative debt-row signal is narrower than Task 4 step 6: two independent green
no-writer executions plus a content-bound current-conformance receipt. For this task, the
new receipt is the audit surface and `/trust` remains conservatively historical/blocked.
No generated posture or posture-compiler bytes are changed. This append-only correction
supersedes Task 4 step 6 while retaining its W5 limitations and corrupt-field proof.

## Round-2 terminal execution plan — appended 2026-08-31

Round 2 terminates every row as `closed` or `blocked`; a target count is not a gate. The
measured evidence decides the final arithmetic. The corrected repository baselines are:

- the bound `check_debt_ledger.py --check` invocation exits 1 at base with 18 blocking
  unresolved closure identities; Task D may remove only identities owned by its rows and
  must not grow the blocker set;
- `check_docs_lifecycle.py` exits 1 with exactly six findings;
- the accepted current-page receipt binds 1,308 tracked paths, so any dashboard edit
  invalidates that receipt and requires a complete reissue.

### Round-2 serialization rule

The dashboard tree is one contended evidence denominator. Execution is strictly:

1. Finish every dashboard/source edit: the DS18 composition repair, execution-outcome
   envelope and JS runner, `/trust` copy wrapper/checker, and watcher wiring.
2. Run targeted source checks, commit, read the branch back, and compute the complete
   tracked source set over `apps/runtime-dashboard`, `package.json`, `pnpm-lock.yaml`, and
   `pnpm-workspace.yaml`.
3. Declare the dashboard freeze with its commit, complete changed-path list, path count,
   and canonical source-set digest. No later dashboard edit is permitted.
4. Ask task C to reissue its eleven-binding C13 receipt against that exact freeze. Task D
   closes its half only if C's exact conjunction node and global disposition check pass.
5. Run two new zero-retry/no-writer page-a11y executions at the freeze, byte-compare their
   complete identity populations, append a new receipt, and run all eight receipt verifier
   and falsifier nodes.

### Task R2.1: Replace the DS18 scalar proxy and define one bounded outcome envelope

**Files:**

- Modify: `apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.test.ts`
- Modify: `apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.ts`
- Create: `apps/runtime-dashboard/src/test/evidence/ds18ExecutionOutcome.ts`
- Create: `apps/runtime-dashboard/src/test/evidence/ds18-execution-outcome.schema.json`
- Create: `apps/runtime-dashboard/scripts/run-ds18-time-semantics-outcome.mjs`
- Do not modify task G's `apps/runtime-dashboard/scripts/persist_atlas_evidence.py`.
- Do not modify task C's round-2 frontend-disposition checker or its test.

**Interfaces:**

- `Ds18ExecutionOutcome` is a strict discriminated union. `established` carries the exact
  independently reconciled five-field projection. `not_established` carries only a fixed
  error code, exit code, bounded stream byte count, and `sha256:` byte digest; no decoded
  stderr or whitespace-normalized text is admissible.
- `DS18_MAX_STREAM_BYTES` is exactly 8,388,608 bytes per stdout/stderr stream.
- `primitiveAdoptionFromDs18Coverage(outcome)` derives the metric row from an admitted
  outcome; it never owns a denominator scalar.
- The JS runner invokes the unchanged canonical Python checker, counts raw bytes, decodes
  UTF-8 fatally, validates the five-field packet, and emits the typed envelope.

- [ ] Add failing Vitest cases that replace the old `94/94` and `616/733/94` assertions
  with a live checker-to-report equality and an independent synthetic `7/9` transform.
- [ ] Add failing cases for invalid UTF-8, malformed JSON, extra/wrong fields, stdout and
  stderr at 8 MiB + 1, nonzero U+001C/U+FEFF stderr, and fixed-code/digest equality.
- [ ] Run the exact Vitest file and record the expected failures before implementation.
- [ ] Implement the schema, runner, decoder, and pure transform with no Python-adapter edit.
- [ ] Re-run the exact Vitest file and dashboard typecheck.
- [ ] Record the independently measured historical mapping: DS15's 45 direct + 49
  inherited roots became DS17's 48 direct + 78 inherited roots through the complete
  +3 direct/+29 inherited root delta. The test pins composition and live checker equality,
  not the scalar 126.
- [ ] Register the Python adapter as `consumer_missing` with the same falsifiers unless
  task G adopts the envelope before the final freeze.

### Task R2.2: Build the public-signature watcher mechanism without inventing population authority

**Files:**

- Create: `src/polisyos/scientist/governance/continuous/published_signature_custody.py`
- Modify: `src/polisyos/scientist/governance/continuous/__init__.py`
- Modify: `src/polisyos/runtime/http/services/control_worker.py`
- Modify: `src/polisyos/runtime/http/services/control/run_lifecycle.py`
- Modify: `src/polisyos/runtime/http/container.py`
- Create: `tests/integration/runtime_quality/test_published_signature_custody.py`

**Interfaces:**

- A `PublicSignaturePopulationProvider` returns either one resolved, content-bound snapshot
  or a typed `not_established` nonreceipt. The production default is explicitly unappointed.
- A persisted synthetic test snapshot sets `population_provenance="synthetic_test"`; it may
  prove mechanism behavior but can never establish `DS11-PUBLIC-SIGNATURE-POPULATION`.
- `PublishedSignatureCustodyWatcher.scan_once(now=...)` verifies the population and every
  signature ref, emits a persisted scan receipt, turns stale members into persisted advisory
  monitor events, invokes the real lifecycle bridge, and enqueues only persisted refs in the
  durable control outbox.
- `ControlWorker` receives a bounded periodic maintenance callback, so production startup
  invokes the watcher without a human/API trigger. The callback records nonreceipt rather
  than treating an empty population as an all-clear.

- [ ] Write the exact closure node
  `test_every_public_signature_is_watched_for_staleness` with both branches: a non-empty
  persisted synthetic-but-production-shaped population produces persisted custody,
  lifecycle, and outbox refs; an empty population produces `not_established` and the test
  fails if a pass/all-clear is returned.
- [ ] Add a deterministic worker test proving the production maintenance callback runs
  without a request and is interval-bounded.
- [ ] Run the exact node red and confirm the missing contract/wiring is the cause.
- [ ] Implement the smallest periodic service, same-store validation, persistence, lifecycle
  bridge, and outbox projection.
- [ ] Re-run the exact node, the worker test, and directly affected control-service tests.

### Task R2.3: Derive and enforce the real `/trust` claim-copy closure

**Files:**

- Create: `apps/runtime-dashboard/scripts/check-public-claim-copy.mjs`
- Create: `apps/runtime-dashboard/src/features/trust/copy/useTrustCopy.ts`
- Modify only as required by the checker: the three trust components and trust route.
- Create: `tests/repo_quality/frontend/test_public_claim_copy_inventory.py`

**Interfaces:**

- The checker starts from the `APP_ROUTES` consumption of `trustRoute`, follows the real
  static and lazy TypeScript import graph, and separately derives every production link
  whose literal destination is `/trust`. It reports every local path and file type.
- Visible expressions may come only from strict admitted posture fields, captured MACHINE
  bytes, the typed `tTrust` namespace wrapper, or the literal `PolicyOS` brand. Raw `t(...)`,
  direct claim-bearing JSX, foreign keys, and unbounded dynamic keys are rejected.
- Active locale parity is derived over `SUPPORTED_LOCALES` (`en`, `uk`); legacy `ru` is not
  presented as active source-language authority.

- [ ] Write the exact closure node and first run it red because the checker is absent.
- [ ] Implement import-graph derivation and AST-visible-expression classification.
- [ ] Convert the trust render closure to the typed namespace wrapper without changing the
  intended visible copy or claiming semantic translation authority.
- [ ] Run the exact node green and record the complete path/file-type denominator.
- [ ] In repository-local scratch, inject `PolicyOS guarantees approval.` as direct visible
  JSX inside a derived renderer, run the real checker, and require nonzero exit.

### Task R2.4: Build the candidate-band scope artifact and name the unowned consumer

**Files:**

- Create: `src/polisyos/core/contracts/scope_adjudication.py`
- Modify: `src/polisyos/core/contracts/__init__.py`
- Modify: `src/polisyos/core/contracts/README.md`
- Create: `tests/unit/core/contracts/test_scope_adjudication.py`

**Interfaces:**

- `ScopeAdjudicationCandidate` binds one candidate function, one adjudication plane, the
  identity-rule version, authority purpose, knowledge/validity times, subject and rule-basis
  artifact refs, and the three ordered four-way predicates.
- Each predicate freezes one of the five P37 classes. The artifact is always explicitly
  `candidate_only`; it may compute a proposed four-way disposition but may not authorize a
  scope ruling, claim transition, head advance, publication, or institutional execution.
- Missing or unestablished predicates remain typed limitations rather than stopping the
  candidate-band mechanism. Digest substitution and mixed planes fail validation.

- [ ] Write unit tests red for one-plane enforcement, ordered four-way derivation, mixed
  plane rejection, digest substitution, and fail-closed unestablished predicates.
- [ ] Implement strict DTOs, canonical payload digest, builder, and verifier.
- [ ] Run those unit tests, Ruff, and direct core-contract importer tests.
- [ ] Keep the register's exact closure node absent/red because the unowned production
  scope consumer and appointed predicate resolver do not exist.

The scope and supersession rows are two different blocker objects. Supersession already
has a production bridge but the default and repository Claim Ledger owners both leave
`ClaimLedgerOwnerPort.append_verified_owner_event` unimplemented and no independently
reconciled successor record exists. Scope has no production resolver, bridge, consumer,
or surface at all. A scope ruling cannot authorize successor bytes, predecessor linkage,
or the Claim head CAS advance; sharing those authority objects would repeat P05/P32.

### Task R2.5: Freeze, coordinate, and reissue evidence

- [ ] Complete all source work and targeted tests before the freeze.
- [ ] Verify branch attachment, commit, and read back `HEAD` plus every changed dashboard and
  workspace-manifest path relative to base.
- [ ] Compute canonical tracked-path rows and their digest using the same algorithm as the
  current receipt verifier; record count and digest.
- [ ] Publish the freeze announcement near the top of the journal hand-back.
- [ ] Send task C the freeze commit, complete changed-path set, and source digest. If C's
  receipt is not available by closeout, block the DS11 half on that exact reissue object.
- [ ] Run the page-a11y command twice with separate output directories, `--workers=1`,
  `--retries=0`, `--update-snapshots=none`, and no writer command between them.
- [ ] Byte-compare complete ordered identities, append new raw runs and receipt, then run all
  eight receipt verifier/falsifier tests.
- [ ] Do not alter dashboard or workspace-manifest bytes after the freeze.

### Task R2.6: Terminal verification and dossier

- [ ] Confirm the Trust Center and Docs IA blocker is landable: Atlas master-plan Phase 2.11
  is scoped to trust/legal and Phase 2.15 to docs/support; record the fourth-plan routing.
- [ ] Run every exact changed node plus proportional lint/type/import checks; no directory-wide
  or full-suite run is allowed.
- [ ] Run the debt checker and verify its blocker set did not grow; do not describe expected
  exit 1 as green. Run docs lifecycle and require exactly six findings.
- [ ] Dispatch independent delta review, classify findings by P40, and repair blocking issues
  before the final evidence wave.
- [ ] End the journal with exactly ten `closed`/`blocked` blocks, measured arithmetic, root
  mapping, normalization adoption status, watcher provenance/branches, copy denominator and
  falsifier, C13 residue, and every dashboard path changed.
