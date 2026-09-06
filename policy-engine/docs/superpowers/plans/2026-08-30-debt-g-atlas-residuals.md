# Atlas Residuals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` to execute this plan task by task.

**Goal:** Close only the Atlas residuals whose measured predicates are now true,
repair the two owned stale bindings, and make the three ownerless DS8 obligations
unmissable whenever DS12, DS13, or DS14 receives a standalone slice plan.

**Architecture:** Keep historical observations immutable. A slice-scope manifest
feeds the existing Atlas enforcement waist and requires an exact frontmatter input
set from every future DS12/DS13/DS14 slice plan; acknowledgement remains
candidate-only and has no closure effect. The Atlas timing receipt binds the exact
historical path-to-node map by Git object and digest instead of comparing its count
with a moving current tree. The DS6 persistence adapter independently replays the
same DS18 time-semantics checker already used by the TypeScript producer and admits
measured coverage only when that checker establishes the complete obligated-root
relation.

**Tech stack:** Python 3.12, pytest/unittest, JSON Schema 2020-12, YAML
frontmatter, TypeScript/Vitest as a read-only blast-radius verifier, Git object
lookups, existing Atlas architecture checkers.

**Spec:** The 2026-08-30 Task G brief and the eleven complete rows in
`docs/plans/active/DEBT-REGISTER.md` are binding. The debt register, Atlas master
plan, generated ledger, GY plan, and published-denominator validator remain
architect-only.

## Global constraints

- Work only in `.worktrees/debt-g-atlas-residuals` on
  `codex/debt-g-atlas-residuals`; verify branch attachment before every commit.
- Never edit `docs/plans/active/DEBT-REGISTER.md`, its generated ledger, the Atlas
  master plan, the GY plan, or `check_debt_ledger.py`.
- Under `apps/runtime-dashboard/**`, edit only
  `scripts/persist_atlas_evidence.py`. Do not edit task D's frontend source or
  `architecture/atlas_surfaces/test_frontend_disposition_register.py`.
- Do not edit task F's import/package policy or lint sources. If its concurrent
  rule changes make a gate red, establish provenance before debugging it.
- State every number with its measure and complete denominator. A disagreement is
  a finding; do not select, average, or silently supersede it.
- Routing is not ownership. The scope gate makes obligations visible; it does not
  close them, appoint an owner, or accept a plan's self-attestation as authority.
- Run exact nodes plus direct blast radius only. Full-suite and directory-wide
  pytest runs are forbidden.
- Mandatory companions outside the mechanism count are this plan, its journal,
  and the final dossier. No mechanism is split merely to fit a path budget.

## Pattern pass

| Pattern | Existing risk found | Target pattern | Acceptance signal |
| --- | --- | --- | --- |
| P01/P02 | A routed row can look handled without a claiming slice or orchestration gate. | Wire the obligation manifest into the existing Atlas enforcement command. | A synthetic DS12/13/14 plan without the exact input set fails; no-plan state remains valid and rows remain open. |
| P03 | Rich DS18 coverage exists but Python persistence projects `unknown`. | Reuse the canonical DS18 checker and expose its established result in the persisted metric. | The persistence path admits the current complete relation and fails closed on a checker rejection. |
| P29/P32 | Marker presence or a declared count can masquerade as the protected property. | Exercise parsed slice frontmatter and the exact historical node mapping. | Remove-the-property/keep-the-marker corruptions fail. |
| P35/P36 | Sampled files and adjacent prose produced competing totals and routing claims. | Complete walks, Git-bound sources, and finding-specific citations. | Journal records the 46/45/zero, 27/58/4, current/historical DS18, and timing maps with denominators. |
| P37/P38 | A plan declaration or AST function count can green an authority-grade gate. | Freeze predicate provenance and test the actual frontmatter set / runnable node identity. | Candidate assertions cannot close rows; a parametrized/current-growth delta cannot rewrite the historical receipt. |
| P39 | The plan, journal, and tests could be counted as mechanism paths. | Declare them as mandatory companions. | Dossier distinguishes mechanism from record. |
| P40/P41 | Repeated count corrections and inherited reds can trigger ladder repairs. | Bucket all timing totals as one workload-identity class and replay exact nodes before attribution. | No further numeric substitution; every red has a base/current provenance note. |

Current capability labels before work: the three DS8 scope rows are
`absent/unallocated`; DS4 remains `surface_missing`; DS6 is
`implemented_but_not_orchestrated` at the Python admission edge; the timing row is
`verification_missing`; the task-C overlap rows retain their producer-side labels
independently of this Atlas-side work.

---

### Task 1: Gate DS12/DS13/DS14 scope setting on the three DS8 residual inputs

**Files:**

- Create: `architecture/atlas_surfaces/slice-scope-obligations.json`
- Create: `architecture/atlas_surfaces/slice-scope-obligations.schema.json`
- Modify: `architecture/atlas_surfaces/check_atlas_enforcement.py`
- Modify: `architecture/atlas_surfaces/test_atlas_enforcement.py`
- Append evidence: `docs/superpowers/journals/2026-08-30-debt-g-atlas-residuals.md`

**Step 1: Write the failing behavioral tests**

Add exact-node tests around a generic scope-obligation validator. Cover all of:

1. no standalone DS12/DS13/DS14 plan exists, so no scope-setting event has occurred;
2. a target slice plan with the right `type` and `slice` but without the required
   frontmatter input set fails;
3. missing, duplicate, unknown, and marker-only obligation variants fail;
4. each of DS12, DS13, and DS14 passes only with the exact three-row set;
5. a non-target slice is unaffected; and
6. the live checker reads every tracked `type: slice-plan` file, not a filename
   prefix proxy.

Run only the new unittest nodes and confirm RED before implementation.

**Step 2: Add the typed manifest and validator**

The manifest is the only enumerated source for:

- `ds8-global-case-index`
- `ds8-local-reviewer-note-persistence`
- `ds8-signed-public-decision-surface`

Each is required at scope setting for DS12, DS13, and DS14. The artifact must say
that acknowledgement is candidate-only and has `closure_effect: none`. The schema
must be strict. Parse complete YAML frontmatter from every tracked Atlas slice plan;
identify plans by `type: slice-plan` plus `slice`, not their filename. For every
target plan, require an exact unique `atlas_residual_inputs` set. Multiple plans for
one target slice fail.

Wire this result into the live `validate_enforcement()` path. Absence of a target
plan is not an error; it keeps the three rows open. A plan's acknowledgement is not
evidence that the obligation was claimed or implemented.

**Step 3: Prove the gate**

Run the new nodes, then the exact Atlas enforcement checker command. Record exit
codes and which three rows the mechanism covers. Commit this coherent mechanism.

### Task 2: Bind the Atlas timing receipt to one historical runnable node map

**Files:**

- Modify: `tests/repo_quality/tools/test_timing.py`
- Append evidence: `docs/superpowers/journals/2026-08-30-debt-g-atlas-residuals.md`

**Step 1: Preserve the red and classify the count disagreement**

Re-run only
`test_atlas_python_governance_lane_names_one_exact_runnable_workload` and record
the current failure. Keep 67, 181, 190, 210, the helper-derived current count, and
the actual current pytest collection distinct, with their derivation names.

**Step 2: Replace the moving-count proxy**

Resolve the timing publication's immutable Git source snapshot and derive the
complete ordered mapping
`test path -> pytest node id` from both historical test blobs. Bind the mapping by
source revision and canonical SHA-256. Assert the catalog command still names the
same two paths and the cited receipt still names the same completed sample. Do not
compare the historical receipt with today's growing test population, and do not
edit the catalog or historical journal.

The helper must reject mapping ambiguity such as duplicate node IDs or a test form
whose runnable cardinality cannot be derived exactly. A digest without its source
revision is insufficient.

**Step 3: Verify the exact selector**

Run the single requested pytest node and confirm `1 passed`. Commit the timing
identity repair separately.

### Task 3: Make DS6 Python persistence consume the established DS18 projection

**Files:**

- Modify: `apps/runtime-dashboard/scripts/persist_atlas_evidence.py`
- Read-only verifier: `apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.test.ts`
- Read-only source: `apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.ts`
- Append evidence: `docs/superpowers/journals/2026-08-30-debt-g-atlas-residuals.md`

**Step 1: Preserve the existing red**

Run only the Vitest cases that prove current primitive-adoption measurement,
predicate provenance, persistence, and red-denominator fallback. Attribute any
fixed-number expectation drift to task D rather than editing its source.

**Step 2: Mirror the existing producer admission**

In the owned Python adapter, invoke
`check_frontend_disposition_register.py --check-ds18-time-semantics-coverage`
with the same repository interpreter, fixed environment, and allowlisted Node 22
executable used by the producer. Strictly validate the five-field JSON packet and
require `covered_root_count == obligated_root_count` before emitting a measured
ratio. Bind the register, schema, checker, and scanner content in the metric basis.

On checker failure or malformed output, preserve `kind: unknown`, use
`predicate_provenance: not_established`, and carry the exact bounded reason. Never
fall back to a frozen count.

**Step 3: Verify producer/admission parity**

Run the exact Vitest nodes again plus the narrow Python persistence path available
in those tests. If task D's fixed count assertions remain red against a newer
current register, record that handoff without changing them. Commit the Python
admission repair if its owned predicate is independently green.

### Task 4: Reconcile all eleven verdicts and produce the register dossier

**Files:**

- Modify: `docs/superpowers/journals/2026-08-30-debt-g-atlas-residuals.md`
- Read-only: all eleven register rows and the Atlas master/slice plans

**Step 1: Re-run the three complete measurements**

Record executable scripts/commands for:

- every `lint.resolution_content_bindings` row: binding rows, unique paths,
  file-type denominator, SHA-256 mismatches, and the six named paths;
- the complete DS5 handoff table: all groups/sites, the six historical handoffs,
  the current planless groups/sites, and planned-but-unabsorbed groups; and
- the timing historical map plus current AST and pytest-collection mappings.

**Step 2: Resolve argument-only rows without pretending they were built**

Record that DS4 has no named generated `DecisionGrade` export; settle the Lex
finding as discovery-versus-mutation scope rather than the false DS10 label
conflict; distinguish the current substantive DS12 master section from a standalone
slice plan; keep the visual instability as ordinary team allocation; and leave
task C's producer halves untouched.

**Step 3: Run targeted closeout verification**

Run changed exact nodes, narrow checkers, Ruff on changed Python, `git diff --check`,
the debt-ledger `--check`, docs lifecycle, and the frontend disposition checker only
if an input to it changed. Record inherited/environment reds with P41 provenance.

**Step 4: Append the Register closure dossier**

End the journal with exactly one block per row. Each block carries verdict
(`closed`/`open`/`blocked`/`ambiguous`), exact command or predicate and exit code,
and exact append-only prose for the architect. Add total arithmetic and core versus
adjacent splits, task C/D handoffs, and named out-of-scope findings. Re-open the
failure register before finalizing. Commit the dossier and verify it from the
attached branch.

## Round 2 execution amendment — 2026-08-31

Round 1 remains the evidentiary base. This amendment executes the architect's
adjudication: every one of the eleven rows must terminate as `closed` or `blocked`;
`open` and argument-only closure are not permitted. A block names a concrete thing
that must land. No architect-owned register, ledger, GY plan, Atlas master plan, or
published-denominator pin is an output of this lane.

Pattern pass: P35 requires complete denominators and exact mappings; P37/P38 require
the DS6 gate to establish the frozen-root property rather than a moving total; P40
treats all historical-lineage escapes as one class; P41 keeps collection and inherited
gate failures distinct from product verdicts. The existing candidate-only scope gate
continues to have `closure_effect: none` and cannot close a row.

### Task 5: Bind DS6 primitive adoption to the 77-root freeze and landing composition

**Files:**

- Modify: `architecture/atlas_surfaces/frontend-disposition-register.json`
- Modify: `architecture/atlas_surfaces/frontend-disposition-register.schema.json`
- Modify: `architecture/atlas_surfaces/check_frontend_disposition_register.py`
- Create: `architecture/atlas_surfaces/test_ds18_time_semantics_lineage.py`
- Append evidence: `docs/superpowers/journals/2026-08-30-debt-g-atlas-residuals.md`
- Read-only: `architecture/atlas_surfaces/test_frontend_disposition_register.py`
- Read-only handoff: `apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.test.ts`

**Step 1: Preserve the scalar-proxy escape**

Add a focused failing test that removes or changes one frozen obligation while adding
an unrelated obligation so the scalar remains constant. The validator must reject the
same-total swap. Add focused failures for an unassigned post-freeze entrant and a
forged historical coordinate; these are examples of the single lineage-admission
class, not separate mechanisms.

**Step 2: Extend the existing DS18 owner artifact with lineage**

Record the content-bound source freeze and the DS15/DS17 reconciliation checkpoints.
Bind each checkpoint to its ordered obligation mapping digest, and bind the two
landing deltas by exact stable selectors, current root identity/digest,
classification, and change kind. Counts are derived summaries only. The asserted
composition at this pin is
`O(current) = O(3011c9584) disjoint-union Delta(DS15) disjoint-union Delta(DS17)`;
it is not a permanent scalar promise.

Extend the focused checker to resolve the pinned Git blobs, derive complete obligated
sets, require full frozen-root equality, verify both exact landing deltas and their
mapping digests, and reject any current member outside the disjoint union. Keep the
existing current-source scanner and evidence checks intact.

**Step 3: Verify the mapping and DS6 consumer**

Run only the new lineage nodes, the focused DS18 checker, and the exact DS6
persistence nodes already used in round 1. Confirm 77 frozen members, 17 DS15
entrants, 32 DS17 entrants, zero exits, and current 126/126 as separately named
measures. Record that the read-only task-D assertions at lines 125, 126, and 170 still
pin 94 while the live composition derives 126; do not edit that file.

### Task 6: Execute the dark-theme scenario probe under a finite ceiling

**Files:**

- Append evidence only: `docs/superpowers/journals/2026-08-30-debt-g-atlas-residuals.md`
- Read-only: `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts`
- Read-only: its committed dark-composer snapshot and dashboard harness

**Step 1: Declare the bounded state**

Assign the routine visual debt to the scoped dashboard E2E owner `team-frontend`.
Use one Chromium desktop viewport at 1440x1200, dark `/compose`, default natural-
language mode, initial render, zero retries, no post-navigation user action, 120
seconds of server readiness plus the 60-second test ceiling, and the existing strict
snapshot tolerance.

**Step 2: Separate harness collection from the rendered property**

Attempt the exact existing Playwright selector first. If its test-module import cannot
collect under the repository Node runtime, record that as a harness non-receipt and
continue with a behaviorally equivalent direct Chromium probe against the same Vite
and fixture servers: identical viewport, fixed clock, local-storage state, reduced
motion, route, heading, theme attribute, and `.workspace-frame` screenshot. Use the
in-app Browser first for live page inspection, then a rerunnable direct browser command
for the evidence receipt. Do not edit dashboard source or its visual baseline.

**Step 3: Terminate on the measured bounded result**

If the exact bounded state mismatches or is unstable, close on a bounded residual with
the workflow-mode route as falsifier and hand repair to task D. If it is stable, close
only as non-reproducing under the stated ceiling with that same workflow-mode
falsifier. If no browser can launch after the servers are proven live, block only on
the concrete task-D harness repair that must land.

### Task 7: Supersede all eleven dossier blocks

**Files:**

- Append only: `docs/superpowers/journals/2026-08-30-debt-g-atlas-residuals.md`
- Read-only: the eleven complete register rows and all slice-plan frontmatter

**Step 1: Name the common slice-plan blocker once**

Re-run the complete active-plan frontmatter census. All six allocation rows name the
same landable object: the standalone DS12/DS13/DS14 `type: slice-plan` set with the
row-specific claims absorbed. Cite the candidate-only scope manifest as the mechanism
that forces the three DS8 inputs to be seen, and state again that it appoints nobody
and closes nothing. Preserve task C's distinct producer halves.

**Step 2: Settle DS4 by vocabulary, not regeneration theatre**

Re-run the complete OpenAPI/generated-family census. Block on the missing
producer-owned normalized `CgfDisposition` grammar and its owner-to-OpenAPI bridge;
the current JSON payload is not that grammar. State that `DecisionGrade` exists as an
owner `Literal` but remains inline rather than a named generated vocabulary, and that
task D's regeneration cannot create the missing semantic bridge. State that `CacheAge`
is retired and its freshness observation is not cache-age authority.

**Step 3: Append the superseding dossier last**

Append exactly eleven blocks, each `closed` or `blocked`, with a rerunnable command or
predicate, exit code, concrete `blocked_by` where applicable, and exact append-only
prose for the architect. Record total and core/adjacent arithmetic, the DS6 mapping,
the scenario result, the task-C overlap remainder, and the exact task-D handoffs.

### Task 8: Targeted closeout and independent review

Run exact changed tests and checkers, Ruff on changed Python, `git diff --check`, docs
lifecycle (expected exit 1 with exactly six findings), and the project-`uv` debt-ledger
check (expected exit 1 with the same 18 unresolved identity blockers). Do not run a
directory or full suite. Re-open the failure register, then request an independent
whole-branch review of the round-2 delta. Correct blocking findings in one batched
round, commit each coherent boundary after checking branch attachment, and read the
delivered files back from `HEAD` before reporting completion.

## Post-freeze resume amendment — 2026-08-31

The pre-merge lineage gate is committed at `e5adb9fc5`; its 621-file / 759-root /
126-obligation result is historical evidence only. Main through `83f69c3c0` is now
merged by an ordinary merge. Task D changed the dashboard source denominator and
landed both the DS9 collection repair and the typed DS18 execution-outcome
envelope. Every measured predicate below is therefore replayed against the merged
tree before it is used.

Constraints added for this resume:

- run one CPU-heavy verifier at a time and let it finish;
- do not communicate with or inspect another lane; unresolved ownership becomes a
  dossier question naming the exact artifact and landing file;
- keep changes to `check_frontend_disposition_register.py` additive and report the
  exact lines because task C has a concurrent narrow edit there;
- do not edit dashboard source beyond the owned
  `scripts/persist_atlas_evidence.py` consumer; and
- retain the scope reminder's `closure_effect: none`: only architect-owned Atlas
  inherited-obligation bullets can establish slice scope.

Pattern pass: P35 forbids carrying the pre-freeze denominator forward; P37/P38
require the lineage gate and Python consumer to validate recomputed producer
artifacts rather than totals or marker fields; P40 requires adopting the typed
execution envelope instead of extending the prior normalization ladder; P41
requires base/current blocker-set comparison for the ledger and explicit carried
programme reds.

### Task 9: Reconcile DS6 lineage against the merged dashboard freeze

Run the focused scanner/checker first and compare the complete stable-selector
mapping with the committed 77 + 17 + 32 composition. If the merged tree contains
new or changed obligations, add one exact content-bound landing checkpoint rather
than changing a count. Extend the same-total, unassigned-entrant, forged-coordinate,
and composition-identity tests as needed. Verify the focused lineage suite and
focused DS18 checker before committing.

### Task 10: Adopt the typed execution-outcome envelope in Python

Read the TypeScript producer, strict schema, runner, and existing Python consumer
end to end. Add focused Python-side tests first for a valid measured outcome and for
both fail-closed sides: producer/checker failure and an invalid or tampered envelope.
Then replace the legacy stdout/stderr interpretation with strict envelope admission,
including per-stream cap evidence, fixed error-code handling, and raw-byte digests.
Keep readiness behavior unchanged. Run only the exact persistence tests and their
direct producer contract nodes; do not edit the frozen dashboard producer.

### Task 11: Replay current row predicates and terminate the dossier

Exercise the now-collecting zero-retry dark-composer Playwright identity under the
declared ceiling. Re-walk all canonical frontend baseline bindings and re-parse the
complete DS5 handoff table against current slice scope. Recheck the generated-client
vocabularies, all five DS8 substantive closure artifacts, and the already-bound
timing workload without replacing historical derivations with current totals.

Append the journal evidence and then the final Register closure dossier as the last
section: exactly eleven row blocks, each `closed` or concretely `blocked`, with
commands, exit codes, append-only prose, arithmetic, post-merge DS6 comparison,
scenario falsifier, Python-envelope evidence, exact checker line spans, and named
architect questions. Run exact changed nodes, narrow checkers, diff checks, the
current-base and branch debt-ledger checks, docs lifecycle, and the two carried
programme-red measurements. Re-open the failure-pattern register before the final
commit and read the result back from `HEAD`.
