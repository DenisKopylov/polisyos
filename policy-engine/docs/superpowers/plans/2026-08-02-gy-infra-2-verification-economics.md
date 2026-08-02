# GY-INFRA-2 Verification Economics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist and publish measured verification timings, package full and delta code reviews deterministically, and either prove a safe cross-process owner cache or close it with a measured negative finding.

**Architecture:** Part A extends the existing `tools.lib.timing` owner: direct GY entrypoints and a generic external-suite runner emit the same backward-compatible JSONL record, while a committed catalog exposes measured p95s before a run and the report surface names missing measurements and overruns. Part B adds one stdlib-only git review-package builder whose full and delta modes share a deterministic renderer; delta mode includes the prior findings as its mandatory checklist. Part C starts with measurement only; no cache contract or implementation is authorized until the dominant cold component is shown both persistable and byte-identically restorable.

**Tech Stack:** Python 3.14, stdlib `argparse`/`subprocess`/`hashlib`/`json`, existing `tools.lib` atomic I/O and timing records, pytest, git CLI, Ruff.

## Global Constraints

- Execute A -> B -> C. Do not begin Part B implementation before Part A is committed and independently reviewed; do not begin Part C Gate 0 before Part B is committed and independently reviewed.
- Parts A and B change no byte under `src/polisyos/**` and trigger no artifact replay.
- Part C changes `src/polisyos/runtime/quality/**` only after Gate 0 passes; its mirrored tests live under `tests/unit/runtime/quality/**`.
- Preserve every validator's direct `python tools/quality/validation/check_*.py ...` invocation and exit/output semantics.
- No validator, gate, denominator, corruption count, flip count, governance number, tolerance, or artifact hash is weakened or redefined.
- New measurements are operational data and never enter a semantic content hash.
- Contended set: `.tmp/gy-s-composed-wmr-world`, its DuckDB FTS index, owner caches, canonical generated artifacts, and the source-flip harness. Playwright/Storybook/fixed-port servers are separately serialized. Lint, typecheck, logic tests, builds, architecture checks, and read-only censuses may run in parallel when they touch none of those resources.
- Source freeze precedes all Part C independent reviews; accepted blocking repairs land before the single replay. Cosmetic post-freeze findings are journaled as debt.
- Verify `git status -sb` and symbolic branch attachment before every commit. No merge, push, rebase, reset, or stash-as-storage.
- Baseline non-receipts remain explicit. The starting `workspace doctor` has one pre-existing generated `docs/reference/ir/schema-catalog.md` drift; runtime API and frontend contracts pass.

## Design Decisions

### Part A

Three approaches were considered:

1. Register and invoke every GY validator only through `tools.cli`. Rejected because the registry already discovers the scripts, but plans and generated-artifact contracts intentionally invoke them directly; changing that surface would cost more than the timing gap saves.
2. Add a shared direct-entry wrapper in `tools.lib.timing`, wire each `check_layer3_gy_*.py` `__main__` guard to it, and add one shell-free timed-suite runner for non-Python suites. Chosen because it preserves commands and centralizes persistence, mode derivation, failure recording, and exit-code preservation.
3. Use Python import/startup hooks to time scripts without touching their guards. Rejected as implicit, environment-dependent, and unable to prove complete wiring from repository source.

The committed timing catalog records literal samples and derives nearest-rank p95. A timeout recommendation is a separate deterministic field; a p95 is never relabeled as an observed timeout. Requested lanes with no sample are surfaced as `unmeasured`, not assigned a guess. Historical samples cite committed journal/plan anchors; Playwright visual and browser-a11y receive fresh local samples through the new runner.

### Part B

Three approaches were considered:

1. Depend on the session/plugin review-packager. Rejected because it disappeared during DS4 and is not repository-owned.
2. Emit raw `git format-patch`/`git diff` only. Rejected because it has no stable package metadata or prior-findings checklist.
3. Add a focused repo-owned Python builder using `git diff --binary --full-index --find-renames`, a stable metadata header, and verbatim prior findings. Chosen. Full mode accepts a base and head; delta mode accepts the prior reviewed point, current head, and prior-findings file. Volatile wall clock and absolute worktree paths are excluded so repeated builds are byte-identical.

### Part C

No implementation approach is selected before Gate 0. The pass condition is conjunctive: the dominant measured cold cost must be content-addressable, persistable, and restorable to the exact owner state needed for byte-identical downstream artifacts. Persisting only a cheap FTS fragment while rebuilding the dominant component is a negative result, not a partial delivery.

## Pattern Pass

- Relevant risks: P29 authorial proof, P31 instance patching, P32 trust-by-form, P33 witness-as-spec, P34 premature exclusion, plus P05/P07/P08 for Part C authority/time provenance.
- Existing Part A state: JSONL producer and summary exist, but canonical direct validators bypass the producer (`artifact_missing` for those runs) and slices cannot query all measured/unmeasured budgets before execution (`surface_missing`).
- Existing Part B state: the delta-only rule has no repo producer or behavioral verification (`producer_missing`, `verification_missing`).
- Existing Part C state: process-local cache is implemented but not cross-process; GY-DI1 lacks the outside-closure negative control (`semantic_test_missing`).
- Target pattern: one timing intake/emission path for the whole direct-validator class; one full/delta renderer; for C, resolve + content-bind + provenance + integrity verification with failure closed on malformed/foreign entries.
- Acceptance signals: direct subprocess records survive process exit; unmeasured and over-budget lanes appear in report output; repeated package generation is byte-identical and typical delta is at most 10% of its full package; Gate 0 records component wall times and serialization verdicts; if C passes, all six cross-process witnesses and cold == warm artifact bytes pass.

---

### Task 1: Establish Plan, Journal, and Baseline

**Files:**
- Create: `docs/superpowers/plans/2026-08-02-gy-infra-2-verification-economics.md`
- Create: `docs/superpowers/journals/2026-08-02-gy-infra-2-verification-economics.md`

**Interfaces:**
- Consumes: GY master plan section 3.5.7, failure/repair register, `CONTRIBUTING.md`.
- Produces: exact execution order, pattern labels, baseline receipts, and a durable checkpoint ledger.

- [ ] **Step 1: Verify branch attachment and clean task worktree**

Run: `git status -sb && git symbolic-ref -q HEAD && git rev-parse HEAD`

Expected: branch `codex/gy-infra-2`, base `4b9e76f20d3ae68d65672faf69493141f158c954`, no task changes before these documents.

- [ ] **Step 2: Record setup receipts and baseline non-receipts in the journal**

Record the successful frozen pnpm install, the pre-commit `core.hooksPath` bootstrap non-receipt, and the doctor schema-catalog drift without changing generated files.

- [ ] **Step 3: Self-review the plan**

Run: `rg -n "T[B]D|T[O]DO|implement la[t]er|appropriate error handl[i]ng|similar to tas[k]" docs/superpowers/plans/2026-08-02-gy-infra-2-verification-economics.md`

Expected: no matches.

- [ ] **Step 4: Commit the planning boundary**

Run branch attachment check, stage only the plan and journal, then commit with `docs(gy-infra-2): plan verification economics work`.

### Task 2: Part A — Direct and External Timing Persistence

**Files:**
- Modify: `tools/lib/timing.py`
- Modify: `tools/lib/__init__.py`
- Modify: `tools/cli.py`
- Create: `tools/quality/testing/run_timed_suite.py`
- Modify: all `tools/quality/validation/check_layer3_gy_*.py` direct guards
- Test: `tests/repo_quality/tools/test_unified_cli.py`
- Create or modify: `tests/repo_quality/tools/test_timing.py`

**Interfaces:**
- Consumes: `ToolRunRecord`, `append_timing_record`, `summarize_timing_records`, `POLISYOS_TOOLS_TIMING_LOG`.
- Produces: `run_timed_entrypoint(entrypoint, *, script_path, argv) -> int`, a mode-aware backward-compatible `ToolRunRecord`, and `run_timed_suite.py --lane <timing-key> [--cwd <repo-relative-dir>] -- <argv...>`.

- [ ] **Step 1: Write failing direct-subprocess and mode tests**

The production break named by the tests is removal/bypass of the shared direct timing wrapper: a real direct invocation exits normally but leaves no record, or records a different mode than the action flag. Use a temporary log via `POLISYOS_TOOLS_TIMING_LOG`; assert real JSONL output, not a mocked append.

- [ ] **Step 2: Run the focused tests and observe RED**

Run: `.venv/bin/python -m pytest tests/repo_quality/tools/test_timing.py tests/repo_quality/tools/test_unified_cli.py -q`

Expected: the direct invocation record and unmeasured-report tests fail because those behaviors do not exist.

- [ ] **Step 3: Implement the minimal shared timing path**

Preserve `SystemExit`, nonzero returns, exceptions, stdout, and stderr. Derive the mode generically from the direct invocation's option flags and use `default` when no action flag exists. A telemetry write failure emits an operational warning and never changes the validator's exit code.

- [ ] **Step 4: Wire the complete GY direct-entry class**

Mechanically replace only each `check_layer3_gy_*.py` `__main__` boundary. Add an AST census test that derives the file set and rejects any direct guard not routed through the wrapper; retain behavioral subprocess tests for successful and expected-nonzero modes.

- [ ] **Step 5: Add the shell-free external-suite runner**

Write a failing test proving a child exit code and output are preserved while one record is persisted, then implement with `subprocess.run(argv, shell=False, cwd=validated_repo_path, check=False)` and no network behavior of its own.

- [ ] **Step 6: Run focused GREEN and Ruff**

Run the two tool test modules, then `.venv/bin/python -m ruff check tools/lib/timing.py tools/lib/__init__.py tools/cli.py tools/quality/testing/run_timed_suite.py tests/repo_quality/tools/test_timing.py tests/repo_quality/tools/test_unified_cli.py`.

Expected: zero failures and zero lint diagnostics.

### Task 3: Part A — Measured Budget Catalog and Reporting Surface

**Files:**
- Create: `tools/quality/timing_budgets.json`
- Modify: `tools/lib/timing.py`
- Modify: `tools/cli.py`
- Modify: `tests/repo_quality/tools/test_timing.py`
- Modify: `docs/superpowers/journals/2026-08-02-gy-infra-2-verification-economics.md`

**Interfaces:**
- Consumes: literal measured samples, committed evidence anchors, fresh JSONL records.
- Produces: validated budget entries with `timing_key`, `command`, `samples_ms`, `measured_p95_ms`, `recommended_timeout_ms`, `source_refs`, and report state `measured`, `unmeasured`, or `over_budget`.

- [ ] **Step 1: Write failing catalog/report tests**

Name these breaks: a catalog p95 disagrees with its literal samples; a requested lane without samples disappears; a duration above measured p95 is not a finding; a slice cannot list budgets before any timing log exists.

- [ ] **Step 2: Run focused tests and observe RED**

Run: `.venv/bin/python -m pytest tests/repo_quality/tools/test_timing.py tests/repo_quality/tools/test_unified_cli.py -q`

- [ ] **Step 3: Populate historical measured samples**

Use only exact committed receipts: GY depth-N/check/rederive/source-flip/write, N11 writer/check/source-flip/closeout modes, CG1 census, second-domain rederive, design-generation/N4, generation-cycle/ledger lanes, Atlas disposition/status/governance suites, full Vitest, and full ESLint. Do not convert policy thresholds or killed default timeouts into samples.

- [ ] **Step 4: Measure missing frontend browser lanes through the runner**

Serialize and run from `apps/runtime-dashboard`: `corepack pnpm run test:visual` and `corepack pnpm run test:a11y:pages`. Preserve honest nonzero semantic results; the runner's job is measurement, not relabeling. Add their exact observed process durations to the catalog and journal.

- [ ] **Step 5: Prove the report surface before an execution**

Run `python3 -m tools.cli report-timing --timing-log <fresh-or-missing-path> --output-format json --include-unmeasured` and assert all requested lanes have either a measured p95 or an explicit unmeasured finding.

- [ ] **Step 6: Verify Part A and commit**

Run focused tests, Ruff, `git diff --check`, and the direct-validator census. Check branch attachment; commit all Part A files and journal receipts with `feat(tools): persist and publish verification timings`.

- [ ] **Step 7: Obtain independent Part A review**

Build a full review package for the Part A commit range using the temporary Superpowers packager, dispatch one independent reviewer, and resolve Critical/Important findings before proceeding. Any fix receives a fix-only re-review; record commits and verdict in the journal.

### Task 4: Part B — Deterministic Full and Delta Review Packages

**Files:**
- Create: `tools/quality/testing/build_review_package.py`
- Create or modify: `tests/repo_quality/tools/test_review_package.py`
- Modify: `docs/superpowers/journals/2026-08-02-gy-infra-2-verification-economics.md`

**Interfaces:**
- Produces full mode: `--base <commit> --head <commit> --output <path>`.
- Produces delta mode: the same range interface plus `--prior-findings <path>` and package metadata declaring `package_kind=delta`.
- Package bytes contain resolved commit IDs, commit list, diff stat, name-status, binary/full-index patch, and for delta the prior findings verbatim with SHA-256.

- [ ] **Step 1: Write failing deterministic full-package test**

Create a temporary git repository with two commits. The break named by the test is volatile output: two builds for the same range differ, omit a changed file, or include the output path/wall clock.

- [ ] **Step 2: Run the focused test and observe RED**

Run: `.venv/bin/python -m pytest tests/repo_quality/tools/test_review_package.py -q`

- [ ] **Step 3: Implement the minimal full builder**

Resolve commits with `git rev-parse --verify <rev>^{commit}`; reject a non-ancestor range; run git with argv and `shell=False`; render LF-normalized sections in stable order; atomically write the result.

- [ ] **Step 4: Write failing delta/checklist tests**

Name these breaks: delta omits or mutates the prior findings; hashes a different checklist; includes already-reviewed changes; or accepts an empty/missing checklist.

- [ ] **Step 5: Implement delta mode and fail-closed inputs**

Use only `prior_review_point..head` for the patch. Include the exact prior-findings bytes and SHA-256. Reject missing, empty, non-file, and outside-repository output/cwd paths without invoking a shell.

- [ ] **Step 6: Prove typical order-of-magnitude reduction**

Build a full package from this branch base through Part A, then create a representative temporary fix commit in a temporary git repo whose initial package is at least ten times its fix delta. Assert `delta_size <= full_size / 10` in the behavioral test and record real branch package sizes separately in the journal without fabricating a ratio if this branch's natural diff is smaller.

- [ ] **Step 7: Verify, commit, and independently review Part B**

Run focused tests, Ruff, `git diff --check`, and architecture guardrails. Check branch attachment and commit with `feat(tools): package full and delta code reviews`. Build the Part B full package with the new tool, dispatch one independent reviewer, and use the new delta mode for every fix re-review. Record all package sizes and verdicts.

### Task 5: Part C Gate 0 — Cold-Build Measurement and Serialization Verdict

**Files:**
- Modify only if measurement instrumentation is necessary and removable before the Gate-0 commit: `src/polisyos/runtime/quality/generation_cycle.py`
- Modify: `docs/superpowers/journals/2026-08-02-gy-infra-2-verification-economics.md`
- Conditionally modify debt row after a positive implementation: `docs/plans/active/layer3-slices/GY-engine-subordination.md`

**Interfaces:**
- Consumes: the real cold owner derivation and existing `_resolve_authority_import_closure`.
- Produces: component wall times for CredalReference, DuckDB FTS/index, composed WMR, and solver/remaining stages; peak/persisted sizes; serializer round-trip result; byte-identity verdict; dominant-share calculation; GO or NEGATIVE.

- [x] **Step 1: Freeze A/B and verify clean branch attachment**

Run `git status -sb`, `git symbolic-ref -q HEAD`, and record the exact Gate-0 source commit.

- [x] **Step 2: Design non-semantic profiling probes**

Use `time.perf_counter()` around existing stage boundaries and write measurements only to the task journal or ignored harness scratch. Do not write timing into canonical artifacts or change a validator decision.

- [x] **Step 3: Run one cold profiled build**

Serialize the `.tmp/gy-s-composed-wmr-world`/DuckDB/owner resource. Record stage seconds, total seconds, percentages, input hashes, process exit, and objective progress evidence.

- [x] **Step 4: Test serializability of every dominant component**

For each component, record whether it has a stable content-addressed representation; write and restore it in ignored scratch; compare the downstream artifact bytes and relevant owner-state digest. “Pickle succeeded” alone is not byte-identity evidence.

- [x] **Step 5: Adjudicate Gate 0 and commit the clean boundary**

If the dominant cost cannot be persisted and restored byte-identically, remove any temporary instrumentation, record `NEGATIVE` with numbers and why a cheap partial cache is rejected, commit the journal, and skip Task 6. If it can, append a concrete measured cache-format/key/integrity design amendment to this plan, self-review it, commit the Gate-0 journal/design boundary, and proceed.

**Gate-0 resolution:** `NEGATIVE`. The sole cold attempt failed closed after `147.703s` of owner
load in N10 provenance drift; provenance consumed `129.939s` (`88.0%`) and the only
byte-identically restored component was the `9.309s` WMR. Independently, the mandated 120-module
closure omits the dynamic producer path and the real owner-cache boundary is under `tools/**`,
outside the Part C fence. No cache implementation or replay is authorized.

### Task 6: Part C Conditional Implementation — Cross-Process Owner Cache

**Status:** skipped by the negative Gate-0 ruling. The unchecked steps below are intentionally not
claimed; none of the six positive-implementation witnesses was run.

**Files:**
- Modify: `src/polisyos/runtime/quality/**` as named by the positive Gate-0 amendment
- Modify: `tests/unit/runtime/quality/**` as named by the positive Gate-0 amendment
- Modify: `docs/plans/active/layer3-slices/GY-engine-subordination.md` only to close the GY-DI1 negative-control debt when witness 3 is green
- Modify: task plan and journal

**Interfaces:**
- Key input: derived authority import closure, deployment identity, schema/rule version, and dominant owner-input content digests.
- Hit output: verified restored owner state with no authoritative claim of its own.
- Refusal output: typed/operational cache-integrity failure; no repair-over, no silent rebuild over a present invalid entry.

- [ ] **Step 1: Add the positive Gate-0 amendment before code**

The amendment must name exact files, types/functions, cache directory ownership, manifest fields, digest algorithm, lock/atomic protocol, disable-cache cold flag, and cleanup/retention behavior. Unresolved serialization questions remain research findings, not code contracts.

- [ ] **Step 2: Write and observe all six RED witnesses**

Run isolated subprocess tests for: cold vs cross-process hit byte identity; inside-closure mutation miss; outside-closure mutation hit; forged/truncated/hand-edited failure closed; foreign deployment identity refusal; racing writers with no torn entry.

- [ ] **Step 3: Implement the smallest correct cache**

Reuse `_resolve_authority_import_closure`; use atomic replacement and a per-key lock; validate manifest, provenance, identity, every content digest, and restored owner digest before returning a hit. A present invalid entry is refused and retained for diagnosis, never overwritten in the same operation.

- [ ] **Step 4: Run focused GREEN, adversarial variants, and cold == warm**

Add malformed manifest, wrong hash algorithm, missing file, swapped payload, sibling outside-closure, and concurrent-loser variants. Compare canonical output bytes and semantic denominators.

- [ ] **Step 5: Freeze source and run all independent reviews**

Commit implementation/tests before replay. Build a full Part C package, obtain independent review, batch every accepted blocking repair, and use Part B delta packages for fix-only re-reviews. Record cosmetic debt after freeze rather than editing source.

- [ ] **Step 6: Pay the single replay and closeout wave**

Run Lane 2 once uncached, then cached redundant lanes, N9 -> generation-cycle -> N11 receipts, corruption/source-flip denominators, importer tests, Ruff, architecture guardrails, runtime API contract, and scoped/full verification required by blast radius. Record before/after wall time, identical artifact hashes, and unchanged counts.

### Task 7: Final Review and Handoff

**Files:**
- Modify: task journal only for final receipts and pattern closeout.

- [x] **Step 1: Re-open the failure/repair register**

Record final P29/P31/P32/P33/P34 assessment and exact capability labels. Do not call a negative Part C implementation complete.

- [x] **Step 2: Run fresh completion verification**

Run every command named by the journal on the exact final commit. Read full output and record exit codes; distinguish baseline failures and non-receipts.

- [ ] **Step 3: Obtain one whole-branch independent review**

Use the Part B full package from merge base to head and point the reviewer at any deferred minor findings. One fix wave maximum; re-review only its delta.

- [ ] **Step 4: Commit the final journal boundary and preserve the branch**

Verify branch attachment, clean tree, commit receipts, and report the preserved `codex/gy-infra-2` worktree. Do not merge or push.
