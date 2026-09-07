# Watcher chain — 2026-09-07

## Final outcome

| Row | Classification | Delivered result / remaining boundary |
| --- | --- | --- |
| 1 — shared hook worktree path | **repaired** | Existing checkout-relative dispatcher verified through regeneration and station changes; original regression now reaches real Lefthook. |
| 2 — runtime config / empty validation | **repaired** | Actual violating commits refused with the declared rule message; stale installer environment, missing prerequisites, and unstaged formatter changes exercised. |
| 3 — declared checker fixture path | **repaired** | Measured defect was relocation of the pnpm launcher, fixed by forwarding at its installed location. Sparse fixture and declared checker unchanged. |
| 4 — dashboard watcher chain | **blocked-and-why** | Exact local coverage completed red and all 50 failures are dispositioned; provisioned replay exposed three additional health failures. CI scheduling/result-consumption repair crosses forbidden `.github/**`; lint's 130 errors and other predecessor failures remain open. No CI closure claimed. |

Hook repair committed at `acd8955be`; this journal completes its evidence and the Row 4 handback. The lane stops at the push boundary. No push, merge, GitHub plugin, other-lane mutation, debt-register/ledger edit, or debt-ledger checker invocation occurred.

## Contract and station

Worktree: `/Users/deniskopylov/polisyos/.worktrees/watchers`; attached branch: `codex/watcher-chain`; slice base: `938ddc32a`. Local ordinary git only; no push, GitHub plugin, ledger reads, or debt-ledger validator. Scope follows the user prompt; this journal is the explicitly required bookkeeping companion.

Property: a declared check executes and its result is read. A refusal must carry the selected rule’s own diagnosis; missing modules and unreached CI steps do not prove that rule. Honest red is retained and dispositioned, never skipped to obtain green.

## Plan and pattern pass

1. Provision the frozen frontend workspace, record unchanged-base gates and complete assertion denominator.
2. Repair Rows 1–3 through the existing hook installer/config and real Git fixtures; test regeneration, runtime binding, missing prerequisites, the violated rule, and removal probes.
3. Diagnose dashboard lint and every failing unit-test file; repair within scope or record exact owner handback. Measure every predecessor of coverage.
4. Freeze edits, review deltas and run targeted final gates, read all results, commit attached boundaries, read back branch delivery, stop before push.

Patterns: P02 (declared suite without reachable orchestration), P29/P32 (execute behavior, not markers), P31/P33 (repair path-resolution class without teaching fixtures the production tree), P35 (enumerate all assertions), P38 (nonzero exit does not prove the intended rule ran), P40 (classify repeat findings before repair), P41 (base before all lane edits). Initial missing labels: hook chain `verification_missing`; CI suite `implemented_but_not_orchestrated` and result consumer `consumer_missing`. Acceptance is independently read execution receipts, including honest red and per-file dispositions. No policy authority semantics are added.

One writer per surface: hook agent owns installer/config/design/hook test; lint agent owns coordinated dashboard lint fixes; suite diagnosis is read-only; root owns integration/journal. Shared hook installation is serialized. Independent lint/typecheck/format/architecture/unit gates may run concurrently. No broad Python suite is permitted.

## Measurements and row dispositions

Initial frozen install: `corepack pnpm install --frozen-lockfile` from `policy-engine`, exit 0, 7.5 s. All 6 declared workspace projects installed; prepare ran `node ../../tools/devx/install_repo_hooks.mjs`. pnpm 10.33.2. Dependency build-script warning retained in install receipt, not treated as product failure.

Rows 1–3: repaired; complete evidence below.

Row 4: blocked at the workflow boundary, with all local receipts and per-file dispositions below. Full Vitest and each CI predecessor began on unchanged dashboard source. Evidence is retained in ignored `policy-engine/.tmp/watcher-chain/`; the durable findings and owners are recorded in this journal.


### Predecessor measurements on the slice base

Node: 22.22.2. All commands below were the only command in their tool invocation (redirection only, no trailing echo). No dashboard source edits preceded them.

- `corepack pnpm run typecheck`: exit 0; all three tsconfig passes returned successfully.
- `corepack pnpm run format:check`: exit 1. Prettier reported 115 distinct existing dashboard paths: 12 `.json`, 11 `.md`, 5 `.mjs`, 48 `.ts`, 39 `.tsx`. This is the complete reported-finding denominator, not a claimed census of all parseable paths. The dashboard has 1,311 tracked paths at the base; raw report: `.tmp/watcher-chain/format-base.log`.
- `corepack pnpm run check:architecture`: exit 1 at the first declared checker. Exact finding: `src/features/trust/routes/TrustPosturePage.route-contract.test.tsx:28` imports `@/features/landing/routes/LandingPage`; trust may import landing only through its public `index.ts` barrel. The subsequent `depcruise` command was **not reached**. Raw report: `.tmp/watcher-chain/architecture-base.log`.

These are measured additional predecessors of `Run coverage suite` in `.github/workflows/ci.yml`, not a theory about the missing ESLint executable. Changing scheduling in `.github/**` is outside this lane. A scheduling handback does not by itself close the separately required lint repair.


## Rows 1–3 — measured hook execution chain

Station: `/Users/deniskopylov/polisyos/.worktrees/watchers`, attached to `codex/watcher-chain`, slice base `938ddc32a`; Node `v22.22.2`, installed Lefthook `2.1.6`, pnpm dependencies installed by root with the frozen lockfile. The lane-local Python 3.14 environment was provisioned with `uv venv --offline`; package installation offline had no cached pytest and failed, so minimal test tooling was installed normally. No product Python dependency or source was modified. Only the named hook module was executed, with `--confcutdir=tests/repo_quality` to avoid importing unrelated backend fixture plugins.

Pattern pass: P29/P33/P38 require an actual rule refusal and its diagnostic, not a generic nonzero result; P31 closes the executable-location class for both fixture entrypoints; P35 enumerates every case in the hook module; P37 classifies execution/refusal predicates as recomputed. Relevant existing defect: the fixture copied the location of a pnpm launcher without preserving the launcher's `$0` resolution, so the real checker was never reached. Target: execute the installed launcher at its installed location and observe the original rule's refusal on isolated repository and linked-worktree stations. Capability was `verification_missing`; the production dispatcher/config bridge already existed. Acceptance is all original semantic assertions green, and removal mutants caught.

The supplied diagnosis was tested rather than inherited. The baseline gate completed **3 failed, 5 passed across all 8 parameterized cases in `tests/repo_quality/tools/test_repo_hooks.py`**, 12.73 seconds, exit 1. The missing path was `.../fixture/policy-engine/apps/runtime-dashboard/node_modules/lefthook/bin/index.js`, **not** `../../tools/design/check-reduced-motion.ts`. The installed `node_modules/.bin/lefthook` is a pnpm shell launcher that uses `dirname "$0"`; symlinking it into the fixture makes `$0` point inside the fixture. This accounts for all three baseline failures, including native hook installation failures before any declared command runs. After fixing only launcher provisioning, every original assertion passed. No checker/config path change was justified by this measurement.

Change: `tests/repo_quality/tools/test_repo_hooks.py` now creates an executable POSIX forwarding script at both fixture entrypoints, invoking the installed real launcher via a shell-quoted absolute path. This is test dependency provisioning; generated shared hooks retain their checkout-relative executable path. The fixture remains sparse, with the same five production source inputs as before (dashboard `package.json`, dashboard `lefthook.yml`, `check-reduced-motion.ts`, `_a11yColor.ts`, and `install_repo_hooks.mjs`). It was not expanded to mirror a full checkout. The declared checker, its command, and every original assertion remain unchanged.

Assertion-change disclosure: **no assertion was removed, replaced, or weakened.** `test_real_commit_refuses_a_declared_reduced_motion_violation` retains the nonzero result, exact rule message, offending filename, no missing-config message, unchanged HEAD count, stable hook bytes, and successful guarded follow-up assertions. Its invocation is stronger: both station commits now originate from the dashboard subdirectory while `LEFTHOOK_CONFIG` names a nonexistent config left by another installer. The dispatcher must override that stale environment at runtime. Both original fixture-launcher symlinks became forwarding scripts; this lets the existing assertions reach the real executable.

- **Row 1 (`shared-git-hook-hardcodes-one-worktree-path`): repaired/verified existing production repair.** The entire declared installed shell-hook set, **2/2 files** (`pre-commit`, `pre-push`) under the configured `/Users/deniskopylov/polisyos/.git/hooks`, was read: both executable, zero worktree-specific absolute paths; both use runtime checkout-relative binary/config binding. Both hash to `45bfd5312ebc736ded74df4131cd00bb41abb0d4c0ddbc2473781d200ad64f66`. The original stability test forces native regeneration then prepare on both station paths in sequence, asserts exact stable bytes, and preserves user hooks/backups. It now passes. Production installer and package prepare were already correct and remain unchanged.
- **Row 2 (`shared-hook-binds-its-config-at-install-time-and-validates-nothing`): repaired/verified existing production repair.** Real violating commits on an isolated repository and its linked worktree are refused with `Imperative motion calls without reduced-motion guards` and the offending file. A linked checkout does not run prepare; it consumes the shared dispatcher plus provisioned real executable. Incoming stale `LEFTHOOK_CONFIG` and nested command cwd do not affect runtime binding. Missing config and binary still fail closed, and formatter success without staged corrected bytes remains refused. Production dispatcher/config were already correct and remain unchanged.
- **Row 3 (`lefthook-declared-check-path-only-resolves-in-the-real-checkout`): repaired at the measured cause.** The real declared checker resolves and runs in both sparse fixture stations after repairing the executable forwarding boundary. A relative checker failure was not reproduced. No instruction was relaxed to accept generic `MODULE_NOT_FOUND`; the original exact-rule assertion is what now passes. The full-checkout witness below independently reproduces the exact rule refusal using the shared installed hook.

Receipts (all gates executed as the only shell command; exit statuses obtained from the execution tool):

- `.venv/bin/python -m pytest --confcutdir=tests/repo_quality tests/repo_quality/tools/test_repo_hooks.py --junitxml=.tmp/watcher-chain/hooks-baseline.xml > .tmp/watcher-chain/hooks-baseline.log 2>&1`: exit 1, all 8 cases: 3 failed / 5 passed, 12.73s.
- Same isolated gate after forwarding-only repair, `hooks-forwarding.{log,xml}`: exit 0, 8/8 passed, 22.90s.
- Same gate with stale-environment/nested-cwd strengthening, `hooks-strengthened.{log,xml}`: exit 0, 8/8 passed, 20.01s.
- `.venv/bin/python -m ruff check tests/repo_quality/tools/test_repo_hooks.py`: exit 0.
- `git diff --check -- policy-engine/tests/repo_quality/tools/test_repo_hooks.py`: exit 0.
- Installed hook full-set census: `.tmp/watcher-chain/installed-hooks.json`, generated by `census_hooks.py`.

Removal probes used isolated copies of the five fixture inputs and the real installed Lefthook/Prettier; no owner source, shared hook, branch or index was mutated. All **6/6 mutants** failed the original relevant assertion; `.tmp/watcher-chain/run_hook_probe.py` and `probe-*.log` preserve replay and diagnostics:

| Removed property (markers retained) | Test | Observed falsifier |
| --- | --- | --- |
| Installed-launcher location, restoring symlink relocation | `test_real_commit_refuses_a_declared_reduced_motion_violation` | exact rule-message assertion fails after `MODULE_NOT_FOUND` |
| Runtime `LEFTHOOK_CONFIG` export | same | violating commit accepted, stale missing config printed; nonzero assertion fails |
| Checker refusal branch (`if (false)`, diagnostic/success strings retained) | same | violating commit accepted and `Reduced-motion checks passed.` printed; nonzero assertion fails |
| Dispatcher invocation (`exit 0` before real exec, marker retained) | same | violating commit accepted; nonzero assertion fails |
| Runtime binary location (installer interpolates its repository path) | `test_shared_hook_contains_no_worktree_specific_path` | shared hook exact byte-stability assertion fails across stations |
| `fail_on_changes: always` | `test_commit_refuses_autofixes_that_are_absent_from_index` | formatter rewrites worktree while commit accepts unfixed index; nonzero assertion fails |

P40 classification: the baseline hook failures are one executable-relocation class, repaired once at the shared fixture provisioning helper. Runtime-binding, checker-enforcement, dispatcher-execution, shared-path, and index probes test separate existing properties; they are intentionally removed in isolation and are not new discovered repair rounds.

Incidental proposed row, owner `team-design`: the reduced-motion checker recognizes guard/provider text lexically (the existing fixture's `// useReducedMotion` makes the current declared rule pass). This task verifies that this declared check executes and its result is consumed; it does not claim semantic soundness of the guard detector. Replacing the scanner with a behavioral/AST proof is distinct scope and has not been attempted.

Full-checkout refusal witness: with an alternate `GIT_INDEX_FILE`, a temporarily added `src/watcher-chain-motion-removal-probe.tsx` containing unguarded `animate()` was staged, and a real `git commit` was invoked from the dashboard directory with stale `LEFTHOOK_CONFIG=/nonexistent/watcher-chain-stale-config.yml`. `LEFTHOOK_EXCLUDE=prettier,eslint,check-contrast` selected the real declared reduced-motion check, as in the sparse regression fixture. The commit exited **1** and named `Imperative motion calls without reduced-motion guards` plus the probe file; hook summary was 0.46 seconds. The original complete checkout was used; neither checker nor configuration was copied/rewritten. After refusal, HEAD remained `938ddc32a5e243267a8fcd578364ff7c8505df9e`, branch remained attached to `codex/watcher-chain`, and the actual index hash remained `54cf4fe06b32acb8de800738478806df712c74ac6a00f61e6613ea2fd51cb8c7`. The injected file was removed only after those read-back checks. No commit occurred. Receipts: `full-checkout-before.json`, `full-checkout-commit.log`, `full-checkout-after.json` under `.tmp/watcher-chain`.

Root independently reviewed the frozen hook diff with no findings and ran all 8 hook cases using `--noconftest`, also passing. Rows 1, 2, and 3 are **repaired** under the prompt's declared execution-and-read property; no hook production source changes were necessary, because the failed witness was the fixture launcher's relocation. The lexical reduced-motion semantics remain the explicitly separate proposed row above.


## Row 4 lint and workflow handback

**Status: blocked-and-why.** The watcher scheduling repair needs `.github/workflows/ci.yml`, which this lane may not change. The exact local lint command completed and its red result was read. Lint remains red; the proposed workflow repair below does not resolve the 130 findings, does not make lint cease being a failure, and is not Row 4 closure. No dashboard source, ESLint rule, test assertion, skip, or suppression changed in this subtask.

### Measured station and artifact denominator

- Station: `/Users/deniskopylov/polisyos/.worktrees/watchers`, attached branch `codex/watcher-chain`, slice base `938ddc32a`; command started while the source tree was unchanged from that base. The coordinator subsequently committed hook-only work, without changing this dashboard lint input set.
- Installed toolchain: Node `v22.22.2`, corepack pnpm `10.33.2`, ESLint `9.39.4`, TypeScript `5.9.3`; frozen workspace install completed before the gate. This station did not suffer an absent `eslint` executable.
- Exact gate, as the sole command in its invocation: `corepack pnpm run lint`, cwd `policy-engine/apps/runtime-dashboard`; **exit 1**, terminal summary **130 errors, 0 warnings**, all parsed and read.
- Timing is a measured bound, not a fabricated exact duration: ESLint started at 2026-09-07 14:42:05 EEST, was alive at elapsed **21m03s**, and was completed by 15:03:35 EEST, so **21m03s–21m31s**. The original invocation did not wrap `/usr/bin/time`. A subsequently requested native `sample` raced completed process 91980 and returned 255 without producing a profile; no hot-rule/profile conclusion is claimed.
- Complete declared CLI input walk: **12 path arguments**, **1,261 visited files**, **1,160 admitted files** after the live ESLint `isPathIgnored` predicate, **101 ignored files**, **0 unreadable/ambiguous cases**. Admitted file-type denominator: **469 `.ts` + 672 `.tsx` + 19 `.mjs` = 1,160**. Findings affect **19/1,160 admitted files**.
- Executing party: watcher lint subagent; P37 label relative to this subagent: `recomputed`. Full evidence: `policy-engine/.tmp/watcher-chain/lint-baseline.log` (untruncated final gate output), `census-eslint-inputs.mjs` (complete path walk + actual ESLint config admission), `lint-input-census.json` (all admitted/ignored paths), `lint-finding-census.json` (all 130 file/line/column/rule/message records). Parsed finding total is reconciled to ESLint's explicit 130-error terminal summary; zero ambiguous output lines.
- This is an exact-command **local reproduction**, not a fetched CI execution receipt. The Ubuntu CI failure mechanism is not independently measured here. The local result establishes real diagnostics after successful dependency installation and invalidates the absent-executable explanation for this station.

### Every affected file

Paths below are relative to `policy-engine/apps/runtime-dashboard/`. Denominator is all 1,160 admitted files of the three file types above; all 19 affected paths are listed, and counts sum to 130 diagnostic instances (including duplicate diagnostics that ESLint actually emitted).

| File | Error instances |
| --- | ---: |
| `src/api/validators.ts` | 1 |
| `src/app/authz/permissions.ts` | 1 |
| `src/features/commandPalette/CommandPalette.test.tsx` | 2 |
| `src/features/commandPalette/CommandPalette.tsx` | 2 |
| `src/features/composer/routes/LaunchRunPage.test.tsx` | 1 |
| `src/features/evidence/components/CapabilityDiscoveryPanel.free-growth.test.tsx` | 2 |
| `src/features/evidence/components/CapabilityDiscoveryPanel.tsx` | 31 |
| `src/features/evidence/export/capabilityDiscoveryTwin.ts` | 1 |
| `src/features/platform/routes/PlatformHealthPage.tsx` | 7 |
| `src/features/trust/components/ClaimPostureRegister.free-growth.test.tsx` | 2 |
| `src/features/trust/domain/posture.test.ts` | 3 |
| `src/features/trust/domain/posture.ts` | 11 |
| `src/features/trust/export/trustPostureTwin.test.ts` | 43 |
| `src/features/trust/export/trustPostureTwin.ts` | 1 |
| `src/features/trust/routes/TrustPosturePage.a11y.test.tsx` | 2 |
| `src/features/trust/routes/TrustPosturePage.route-contract.test.tsx` | 3 |
| `src/features/trust/routes/TrustPosturePage.test.tsx` | 14 |
| `src/shared/ui/trust-view/trust-glyphs.ts` | 1 |
| `src/shared/ui/trust-view/trustViewArchitecture.test.ts` | 2 |

### Every emitted rule

Denominator is all 130 diagnostics in the completed local lint invocation; all 12 rule IDs are listed.

| Rule | Error instances |
| --- | ---: |
| `@typescript-eslint/no-deprecated` | 2 |
| `@typescript-eslint/no-unnecessary-type-arguments` | 1 |
| `@typescript-eslint/no-unnecessary-type-parameters` | 1 |
| `local/no-hardcoded-strings` | 40 |
| `no-control-regex` | 1 |
| `no-regex-spaces` | 7 |
| `policyos/quantity-must-be-wrapped` | 4 |
| `testing-library/no-container` | 9 |
| `testing-library/no-node-access` | 57 |
| `testing-library/prefer-presence-queries` | 2 |
| `unused-imports/no-unused-imports` | 2 |
| `vitest/no-conditional-expect` | 4 |

### Root-cause distinction and remaining owners

The gate is executing configured rules; it is not failing because the executable is absent or because no rules loaded. Its diagnostics mix actual source violations with a mismatch between a rule and the behavior that the test or parser owns:

- The complete hardcoded-text set is **40/130 diagnostics**, across `CapabilityDiscoveryPanel.tsx` (31), `PlatformHealthPage.tsx` (7), and `CommandPalette.tsx` (2). These are literal user-facing strings bypassing `t(...)`. Proposed owner: `team-design` / dashboard package owner. Proper repair needs catalog-backed text with current multilingual parity, not disabling `local/no-hardcoded-strings`.
- The complete quantity-rule set is **4/130 diagnostics**: `capabilityDiscoveryTwin.ts:211` tests `leaf.path.length === 0`; `posture.ts:723` indexes `basis[1]`; `posture.ts:745` indexes `lines[2]`; `posture.ts:772` indexes `bindingLines[index + 1]`. All four perform structural decoding/frontmatter parsing; none emits a decision quantity to a UI. Wrapping these positions or indexes in a decision `QuantityValue` would change their semantics to satisfy a proxy. Proposed owner: `team-design` with `team-architecture` for the local quantity classifier. Pattern `P38`: the property is an emitted decision quantity; the current classifier labels these structural index literals as decision quantities. A repair must distinguish that context behaviorally while retaining real quantity violations.
- `trustPostureTwin.test.ts` contributes **43/130 diagnostics**, comprising **42 no-node-access + 1 no-container**. Its DOM removal, row reordering, and field-forgery mutations test rejection by the actual DOM twin decoder; the test intentionally operates on the representation the parity guard must police. Deleting these mutation paths, skipping the file, or weakening the rejection assertions would lose the removal probes. Proposed owner: `team-design` with `team-devx`; reconcile the lint/testing contract while preserving the negative mutation coverage. The remaining DOM/query diagnostics are fully enumerated in the evidence, not implicitly dismissed.
- The remaining emitted deprecated-API, unused-import, regex, conditional-expect, presence-query, and type-parameter diagnostics also remain open and assigned to the dashboard package owner (`team-design`), with `team-devx` for testing convention decisions. No automatic `--fix`, baseline rewrite, global suppression, or enum/status change was applied.

### Exact workflow handback to the parallel `.github/**` owner

Proposed owner: `team-devx`, coordinating `team-design` for the suite. Current `frontend-quality` has a shared `timeout-minutes: 25` and sequential typecheck → lint → formatting → architecture → coverage → accessibility. Merely running coverage under an unconditional same-job condition would bypass predecessor status but still share their time budget. This station spent over 21 minutes on lint alone; that is measured local scheduling risk, not proof of an actual CI timeout.

In `.github/workflows/ci.yml`:

1. Move the `Run coverage suite` step out of `frontend-quality` into a new independent sibling job (no `needs` on lint/format/architecture), keeping its command and failure status intact:

```yaml
  frontend-unit-coverage:
    name: Standard PR / Frontend unit coverage
    runs-on: ubuntu-latest
    timeout-minutes: 25
    defaults:
      run:
        working-directory: policy-engine/apps/runtime-dashboard
    steps:
      - name: Checkout repository
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
      - name: Setup Policy Engine Python
        uses: ./.github/actions/setup-policy-engine-python
        with:
          profile: runtime
      - name: Setup runtime dashboard
        uses: ./.github/actions/setup-runtime-dashboard
      - name: Run coverage suite
        run: corepack pnpm run test:coverage
```

The dashboard setup defaults to frozen dependency installation and does not need Playwright browsers for this Vitest suite. Keep `frontend-quality`'s typecheck, lint, formatting, architecture, and accessibility steps and their failures intact. The independent job's 25-minute budget is a starting bound matching existing policy; the workflow owner should size it from the coordinator's completed coverage timing, not this lint timing.

2. Add `frontend-unit-coverage` to `standard-pr-gate.needs` (the list currently starts at line 362). The gate already consumes `join(needs.*.result, ',')`; preserve that consumption.
3. Since that existing aggregate only rejects `failure` and `cancelled`, explicitly reject a missing/skipped new coverage result as well. Add a `COVERAGE_RESULT: ${{ needs.frontend-unit-coverage.result }}` environment variable to `Enforce standard tier`, print that result, and before the existing aggregate check add:

```bash
if [[ "${COVERAGE_RESULT}" != "success" ]]; then
  echo "::error::Frontend unit coverage did not complete successfully (${COVERAGE_RESULT})."
  exit 1
fi
```

This keeps a reached red suite visibly red and prevents a skipped suite from being accepted by the aggregate. A red coverage job is evidence that the watcher is working only after the suite actually ran to completion and its diagnostics were read. The new aggregate condition is not permission to equate green with reached: verification must deliberately fail a retained unit assertion, show that the independent job executes despite a lint failure, and show that the standard gate reads/rejects its failed result; restore the assertion afterward. A skipped/cancelled coverage job must also be rejected by the aggregate.

This handback changes scheduling and result consumption only. It does **not** repair the 130 local lint errors, disposition or fix the unit failures by itself, establish a successful remote CI run, or close the whole row. No workflow file was edited in this lane.


## Row 4 baseline suite disposition (historical receipt; superseded where refined below)

The baseline sections preserve what was known at that stage. The completed coverage, provisioned Python replay, and final dependency-census sections below are the current closeout receipt; all earlier pending/replay language is interim and superseded.

Station: `/Users/deniskopylov/polisyos/.worktrees/watchers`, branch `codex/watcher-chain`, baseline checkout `938ddc32a`; no dashboard source edits preceded this run. Root captured the command exit as 1. Artifact: `policy-engine/.tmp/watcher-chain/vitest-base.json`, SHA-256 `f314fd3db4640adadf0a9446bf497196f95299da08494edc4e0b646691787ec3`.

Full file denominator: 403 Vitest result-file records = 381 passed + 22 failed. Full assertion denominator: 1619 collected assertions = 58 failed + 1526 passed + 35 skipped. Vitest `numTotalTestSuites=820` counts suite containers, not files. The failure-bearing assertion files total 18. Four other file records fail setup/collection and are included below.

The prompt’s 1,652-test / 50-failure / 15-file station is not reproduced byte-for-byte here: this artifact has 1,619 collected tests, 58 failed assertions and 22 failed file records. This is an observed station/result-population difference; collection/setup failures prevent calling the missing assertions passed or intentionally skipped. All 58 observed failed assertions are dispositioned below. All 33 setup-skipped assertion identities in the two failed-hook files are also listed. Exact CI coverage replay is a separate receipt; no CI run is claimed from a local test run.

No production or test source was edited by this diagnosis, and no existing assertion was relaxed, deleted or skipped. Proposed repairs are handback items, not claims of implementation.

### R4-F01: `scripts/tokenProjectionParity.test.ts`

Disposition: **blocked by file boundary**. Proposed owner: **team-design + atlas-ui package owner**. This file’s emitted denominator: 11 assertions, statuses `{'passed': 10, 'failed': 1}`.

The complete ordered print-rule collector disagrees between dashboard media.css + print.css + styles.css and packages/atlas-ui/src/generated/tokens.css. The dashboard side adds [data-run-detail-screen-only="true"] hiding, run-paper admitted-link URL-printing and form-hiding rules, and suppression of public-decision link suffixes; the generated package projection lacks them. Scratch print-rules-census.json records the entire ordered-rule set, including source order. Smallest closure: update/regenerate the atlas-ui print projection through its owner and preserve this equality assertion; generated package paths are outside this lane. Removing source print safeguards or relaxing equality is not a repair.

Observed failed assertions (exact JSON reporter names):

- `DTCG token projection parity projects print tokens and export behavior` — `AssertionError: expected { …(2) } to deeply equal { …(2) }` (140.77191700000003 ms).

### R4-F02: `src/app/authz/authzDecisionSurfaces.test.tsx`

Disposition: **test environment integration debt**. Proposed owner: **team-design**. This file’s emitted denominator: 2 assertions, statuses `{'failed': 2}`.

Both failures reach real Header -> useCapabilitySearch -> React Query and throw before the authority assertions. The tree fixture mounts MemoryRouter, InterfaceModeProvider and optionally AuthzProvider but no QueryClientProvider and does not mock useCapabilitySearch. Smallest closure: supply a bounded QueryClient plus a capability-search response, or an explicit hook boundary fixture, then retain all unknown/verified authorization assertions. No product authorization conclusion can be drawn from the current throws.

Observed failed assertions (exact JSON reporter names):

- `current verified Authz decision across application chrome restores the implicit analyst default only after identity becomes verified` — `Error: No QueryClient set, use QueryClientProvider to set one` (165.30575000000044 ms).
- `current verified Authz decision across application chrome test_unknown_authz_decision_never_defaults_authority_surface_to_allow` — `Error: No QueryClient set, use QueryClientProvider to set one` (5.276749999999993 ms).

### R4-F03: `src/app/layout/layoutSurfaces.test.tsx`

Disposition: **test environment integration debt**. Proposed owner: **team-design**. This file’s emitted denominator: 14 assertions, statuses `{'failed': 10, 'passed': 4}`.

The ten failures all identify Header -> useCapabilitySearch -> useQuery with no QueryClient. renderWithRouter supplies only MemoryRouter; existing mocks cover useCapabilities, health and run hooks but omit the newer search query. Smallest closure: mount the application query provider or a bounded query hook fixture and keep all ten UI assertions. Re-run the entire file because a later missing mock/export can be masked by this first throw.

Observed failed assertions (exact JSON reporter names):

- `layout surfaces renders the application shell with sidebar, header, and main content` — `Error: No QueryClient set, use QueryClientProvider to set one` (278.6421250000003 ms).
- `layout surfaces shows counterfactual controls on concrete run routes` — `Error: No QueryClient set, use QueryClientProvider to set one` (91.36316700000043 ms).
- `layout surfaces does not mount run-scoped controls for the global Cycle Board` — `Error: No QueryClient set, use QueryClientProvider to set one` (14.156208000000333 ms).
- `layout surfaces removes command and what-if entry surfaces when rollout flags are false` — `Error: No QueryClient set, use QueryClientProvider to set one` (79.89924999999948 ms).
- `layout surfaces switches to Atlas brand lockups when Atlas v2 is enabled` — `Error: No QueryClient set, use QueryClientProvider to set one` (68.81912499999999 ms).
- `layout surfaces renders bottom navigation only on real mobile widths` — `Error: No QueryClient set, use QueryClientProvider to set one` (51.56029199999921 ms).
- `layout surfaces renders header status badges and responds to theme and locale controls` — `Error: No QueryClient set, use QueryClientProvider to set one` (2.473707999999533 ms).
- `layout surfaces renders an open health label verbatim with neutral clothing` — `Error: No QueryClient set, use QueryClientProvider to set one` (1.559291999999914 ms).
- `layout surfaces uses decision_review_required and never status text for the review count` — `Error: No QueryClient set, use QueryClientProvider to set one` (1.6309999999994034 ms).
- `layout surfaces renders loading and unavailable header states` — `Error: No QueryClient set, use QueryClientProvider to set one` (1.1118329999999332 ms).

### R4-F04: `src/shared/i18n/parity.test.ts`

Disposition: **catalog/declaration integration debt**. Proposed owner: **team-design, with architecture review for new declaration semantics**. This file’s emitted denominator: 38 assertions, statuses `{'passed': 26, 'failed': 12}`.

Read-only execution of this test file’s actual collectors over every leaf of both active locale JSON catalogs yields 2,837 leaves and 373 non-count interpolation uses in each locale. The old pin is 2,733 leaves / 366 uses. Both locales add an unjustified pages.cycleBoard.acquisition.connector.familyCount count message; six undeclared variable names (demandOne, demandTwo, confidenceCount, scoreCount, admitted, raw); and an undeclared numeric use pages.cycleBoard.acquisition.backlog.zeroScoreBasis#{total}. Existing negative controls clone the live catalogs, so those independent new errors pollute their exact expected failure rosters. Scratch locale-census.json contains every collector output and use identity. Smallest closure: adjudicate each new variable/use, implement proper locale agreement or a justified invariant, recompute every frozen declaration/hash from the full catalog, and retain the negative controls. Do not blanket-allow names, delete the negative controls, or merely repin the first leaf assertion.

Observed failed assertions (exact JSON reporter names):

- `locale catalogs justifies exactly every active non-ICU count-message identity` — `AssertionError: expected [ …(21) ] to deeply equal [ …(22) ]` (24.042041000000154 ms).
- `locale catalogs requires every active en count message to be ICU plural or justified` — `AssertionError: expected [ Array(1) ] to deeply equal []` (58.06337499999972 ms).
- `locale catalogs requires every active uk count message to be ICU plural or justified` — `AssertionError: expected [ Array(1) ] to deeply equal []` (24.720957999999882 ms).
- `locale catalogs rejects the certified wrong en blocked output at the gate boundary` — `AssertionError: expected [ …(2) ] to deeply equal [ Array(1) ]` (21.092666999999892 ms).
- `locale catalogs rejects the certified wrong uk blocked output at the gate boundary` — `AssertionError: expected [ …(2) ] to deeply equal [ Array(1) ]` (82.51641600000039 ms).
- `locale catalogs does not use text shape to gate an invariant declaration` — `AssertionError: expected [ Array(1) ] to deeply equal []` (37.78254199999992 ms).
- `locale catalogs rejects a real new active-catalog numeric use until it is declared` — `AssertionError: expected [ …(6) ] to deeply equal []` (26.52862499999992 ms).
- `locale catalogs rejects a stale declaration in one active locale independently` — `AssertionError: expected [ …(2) ] to deeply equal [ Array(1) ]` (24.03845799999999 ms).
- `locale catalogs derives point-use membership from ICU semantics, not brace markers` — `AssertionError: expected [ …(2) ] to deeply equal [ Array(1) ]` (8.304291999999805 ms).
- `locale catalogs freezes the complete quantitative-use declaration set` — `AssertionError: expected [ 2837, 2837 ] to deeply equal [ 2733, 2733 ]` (39.586333000000195 ms).
- `locale catalogs requires complete active en quantitative-use declarations` — `AssertionError: expected [ …(6) ] to deeply equal []` (27.333042000000205 ms).
- `locale catalogs requires complete active uk quantitative-use declarations` — `AssertionError: expected [ …(6) ] to deeply equal []` (30.864707999999155 ms).

### R4-F05: `src/test/evidence/atlasAutomatedEvidenceCapture.test.ts`

Disposition: **fresh-worktree test setup debt**. Proposed owner: **team-devx + team-design**. This file’s emitted denominator: 16 assertions, statuses `{'passed': 15, 'failed': 1}`.

The test calls mkdtempSync on ../../_build/apps/runtime-dashboard/ds6-c08-core-test- without first creating the parent directory. The observed ENOENT happens before the Python/Core persistence adapter is called, so Core corruption handling was not exercised. Smallest setup repair: mkdirSync(scratchParent, {recursive:true}) before mkdtempSync, preserving every persistence/corruption assertion. This is a station setup failure, not a measured Core product defect; no repair was made in this diagnosis.

Observed failed assertions (exact JSON reporter names):

- `Atlas automated evidence capture executes Core put, resolve, lineage, and integrity checks and fails on corruption` — `Error: ENOENT: no such file or directory, mkdtemp '/Users/deniskopylov/polisyos/.worktrees/watchers/policy-engine/_build/apps/runtime-dashboard/ds6-c08-core-test-XXXXXX'` (215.31437499999993 ms).

### R4-F06: `src/test/evidence/atlasHealthMetrics.test.ts`

Disposition: **ambiguous setup failure**. Proposed owner: **team-devx + team-design**. This file’s emitted denominator: 28 assertions, statuses `{'skipped': 28}`.

The file status is failed and all 28 collected assertions are skipped; the JSON reporter’s file message is empty. beforeAll calls measureAtlasHealthMetrics with a 60-second hook timeout; that path reaches local owner/DS18 instruments. This artifact cannot distinguish timeout from instrumentation failure. Required next measurement: read exact default-reporter setup error (or rerun this one file with its required local Python environment and captured child status/stderr) before assigning a root cause. These 28 checks did not run; skipped is not evidence of their properties.

File-level receipt: `ambiguous: reporter omitted the setup/hook error`.

Collected but not executed after setup failed:

- `Atlas health metrics derives the exact seven-metric population and rejects a new identity` — `skipped`.
- `Atlas health metrics records the six current measurements and the seventh protocol seam honestly` — `skipped`.
- `Atlas health metrics derives primitive adoption from the live DS18 outcome instead of a local scalar` — `skipped`.
- `Atlas health metrics derives a synthetic 7/9 primitive-adoption measurement from an admitted outcome` — `skipped`.
- `Atlas health metrics fails closed with bounded raw evidence for malformed DS18 checker output` — `skipped`.
- `Atlas health metrics bounds each raw checker stream independently` — `skipped`.
- `Atlas health metrics preserves nonzero U+001C and U+FEFF stderr as raw fixed-code evidence` — `skipped`.
- `Atlas health metrics drops primitive adoption to not established when its moving denominator is red` — `skipped`.
- `Atlas health metrics keeps unknown, zero, missing, and incomparable structurally distinct` — `skipped`.
- `Atlas health metrics does not turn no observation into zero or an unavailable denominator into missing` — `skipped`.
- `Atlas health metrics produces no ranking for incomparable scopes` — `skipped`.
- `Atlas health metrics keeps every metric on the closed instrument without claiming independence` — `skipped`.
- `Atlas health metrics binds every metric identity to its exact status, basis, state, and facts` — `skipped`.
- `Atlas health metrics rejects measured or zero authority whenever the predicate is not established` — `skipped`.
- `Atlas health metrics binds surface closure to its two target states, not every open state` — `skipped`.
- `Atlas health metrics runs full canonical owner-schema corruption probes without editing owners` — `skipped`.
- `Atlas health metrics rejects duplicate canonical owner identities even when each row is schema-valid` — `skipped`.
- `Atlas health metrics replay comparator degrades a content binding absent from the recorded revision` — `skipped`.
- `Atlas health metrics replays a clean product-relative bound path and degrades an absent path` — `skipped`.
- `Atlas health metrics refuses MACHINE audience and source-level proxy tests as metric passes` — `skipped`.
- `Atlas health metrics registers the unchanged Python persistence adapter as consumer missing` — `skipped`.
- `Atlas health metrics ignores a caller PATH node that emits a schema-valid forged report` — `skipped`.
- `Atlas health metrics does not inherit caller NODE_OPTIONS into the fixed producer` — `skipped`.
- `Atlas health metrics rejects caller-supplied C11 intake field report` — `skipped`.
- `Atlas health metrics rejects caller-supplied C11 intake field repository_root` — `skipped`.
- `Atlas health metrics rejects caller-supplied C11 intake field producer_script` — `skipped`.
- `Atlas health metrics rejects caller-supplied C11 intake field exit_code` — `skipped`.
- `Atlas health metrics rejects caller-supplied C11 intake field basis` — `skipped`.

### R4-F07: `src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts`

Disposition: **ambiguous collection/setup failure**. Proposed owner: **team-devx + team-design, owning readiness/instrumentation lane for backend changes**. This file’s emitted denominator: 0 assertions, statuses `{}`.

The file fails before collecting assertions with Unexpected end of JSON input. Its persistence bridge spawnSync calls .venv/bin/python then immediately JSON.parse(result.stdout) before inspecting child status/stderr. A child failure or missing/empty response is therefore hidden by a parser error. Required next measurement: preserve process.error/status/stderr and locate the producing call in the default-reporter stack; no claim that the absent local venv or CI caused it is established by this JSON alone. Smallest diagnostic repair is to report the subprocess failure before parsing; a backend/owner repair belongs to the owner if the error resolves outside allowed paths.

File-level receipt: `Unexpected end of JSON input`.


### R4-F08: `src/features/runs/domain/confidenceLedgerRiskSpend.test.ts`

Disposition: **open dashboard owner-contract integration debt**. Proposed owner: **team-design/runtime-dashboard owner**. This file’s emitted denominator: 46 assertions, statuses `{'failed': 1, 'passed': 45}`.

This is not only a stale count pin. Running the actual generatedOwnerLiteralInventory walker over all four root packet schemas in schemas/runtime_api_v1.openapi.json yields 110 literal occurrences; evaluating the runtime table yields 99. Multiset reconciliation finds 11 extra generated occurrences and zero unmatched runtime occurrences. The generated anyOf arms now give the same wildcard binding_name path two incompatible values (live_probe_journal_content_sha256 and foundry_dependency_discriminant); relation=semantic_projection also repeats by arm. verifyGeneratedOwnerLiterals currently applies each wildcard equality to every matching value. Appending both arm literals would make any nonempty binding list fail. Smallest correct closure: retain branch/discriminator context through the generated/runtime literal contract, then prove both binding arms and malformed substitutions. Repinning 99 to 110 alone only reaches the second failing equality. Scratch owner-literal-census.json enumerates all 11 occurrences. The existing owner already defines the discriminated union and nullable diagnostic contract. Follow that owner contract in the dashboard validator and test collector; this repair can remain entirely within the allowed dashboard paths and needs no new architect decision. This remains OPEN, not blocked by the lane boundary.

Observed failed assertions (exact JSON reporter names):

- `confidence-ledger risk-spend strict admission covers every generated owner const and single-value enum with the runtime literal table` — `AssertionError: expected [ …(110) ] to have a length of 99 but got 110` (41.36112499999945 ms).

### R4-F09: `src/features/runs/export/confidenceLedgerRiskSpendTwin.browser.test.tsx`

Disposition: **runner routing debt**. Proposed owner: **team-devx + team-design**. This file’s emitted denominator: 0 assertions, statuses `{}`.

The default forks/jsdom suite collects a browser-only file importing vitest/browser and aborts it before assertions are collected. The returned error explicitly requires Browser Mode. Smallest closure is a test-project split/routing that executes this file in the existing browser configuration while executing the unit project normally, and a watcher that reads both results. A bare exclude or skip with no executed browser watcher would discard the coverage and does not close the debt.

File-level receipt: `vitest/browser can be imported only inside the Browser Mode. Your test is running in forks pool. Make sure your regular tests are excluded from the "test.include" glob pattern.`.


### R4-F10: `src/features/runs/export/confidenceLedgerRiskSpendTwin.test.tsx`

Disposition: **ambiguous execution failure**. Proposed owner: **team-design + team-devx**. This file’s emitted denominator: 48 assertions, statuses `{'failed': 1, 'passed': 46, 'skipped': 1}`.

The one failing production-twin assertion has JSON error STACK_TRACE_ERROR and duration 17,699.39675 ms. That exceeds the configured 15,000 ms test timeout, but the reporter omits the actual reason. The assertion executes preflight plus independent DOM reconciliation; no parity mismatch is established by this placeholder. Read the exact coverage/default-reporter result before choosing performance, synchronization or product repair. Preserve the full twin and its removal probes.

Observed failed assertions (exact JSON reporter names):

- `confidence-ledger risk-spend production twin runs the shared preflight then independently reconciles all visible root and dialog text` — `Error: STACK_TRACE_ERROR` (17699.39675 ms).

### R4-F11: `src/features/trust/components/ClaimPostureRegister.free-growth.test.tsx`

Disposition: **open fixture coupling debt**. Proposed owner: **team-design**. This file’s emitted denominator: 1 assertions, statuses `{'failed': 1}`.

The first failure is source = register.claims.find(effective_state === "planned") returning undefined, before any renderer call. The complete public/atlas/trust-claim-posture.v1.json census has 359 claim records = 358 blocked + 1 supported + 0 planned (free-growth-claim-census.json). The test assumes a live authority artifact always has a planned seed row. The test explicitly delegates producer admission to a separate repository-semantic test and owns the generic consumer only. Smallest closure: provide a stable in-dashboard fixture for this consumer test and preserve its generic-growth assertions, without rewriting the published artifact or silently treating a blocked row as planned. This fixture repair is within the allowed dashboard paths; no outside-producer or architect block is established.

Observed failed assertions (exact JSON reporter names):

- `ClaimPostureRegister free growth renders a producer-admitted new row without a subject switch` — `AssertionError: expected undefined to be defined` (817.594 ms).

### R4-F12: `src/features/trust/domain/posture.test.ts`

Disposition: **ambiguous execution failure**. Proposed owner: **team-design + team-devx**. This file’s emitted denominator: 35 assertions, statuses `{'passed': 34, 'failed': 1}`.

The bytes-before-validation assertion reports only STACK_TRACE_ERROR after 24,794.251 ms, above the 15,000 ms default. This does not identify a cache/fallback correctness failure. Obtain the default-reporter reason and repeat this exact case under measured resources before changing any admission logic or timeout.

Observed failed assertions (exact JSON reporter names):

- `trust posture artifact admission captures response bytes before strict validation with no cache or fallback` — `Error: STACK_TRACE_ERROR` (24794.251 ms).

### R4-F13: `src/features/trust/export/trustPostureTwin.test.ts`

Disposition: **ambiguous execution failure**. Proposed owner: **team-design + team-devx**. This file’s emitted denominator: 2 assertions, statuses `{'passed': 1, 'failed': 1}`.

The full public-claim DOM twin reports only STACK_TRACE_ERROR after 91,549.594958 ms. Its duration alone is not a diagnosis of an incorrect claim or DOM drift; the actual failed condition is absent from the JSON. Read the default-reporter result and measure the full 359-claim producer artifact on this station, preserving every ordered public-field/mutation check.

Observed failed assertions (exact JSON reporter names):

- `trust posture MACHINE and DOM twins independently decodes every ordered public claim field and rejects DOM drift` — `Error: STACK_TRACE_ERROR` (91549.594958 ms).

### R4-F14: `src/features/runs/components/ConfidenceLedgerRiskSpend.a11y.test.tsx`

Disposition: **ambiguous execution failure**. Proposed owner: **team-design + team-devx**. This file’s emitted denominator: 1 assertions, statuses `{'failed': 1}`.

The ordered reviewer surface/full-envelope accessibility assertion reports only STACK_TRACE_ERROR after 36,011.087708 ms. The artifact contains no axe violation details; do not classify it as an accessibility violation or a pass. Read exact default-reporter output, then measure this a11y case with normal resource contention; preserve both surface and dialog audits.

Observed failed assertions (exact JSON reporter names):

- `ConfidenceLedgerRiskSpend accessibility has no violations in the ordered reviewer surface or full-envelope dialog` — `Error: STACK_TRACE_ERROR` (36011.087708 ms).

### R4-F15: `src/features/runs/routes/CaseWorkspacePage.parity.test.tsx`

Disposition: **test-double export integration debt**. Proposed owner: **team-design**. This file’s emitted denominator: 5 assertions, statuses `{'failed': 5}`.

All five assertions throw before DOM decoding because their complete LocaleProvider mock exports only useI18n, while the real TimeSemanticsLabel now consumes useOptionalI18n. Smallest closure: retain real module exports through a partial mock or provide the complete current I18n fixture; then run the positive twin and all removal/link probes unchanged. Do not mock away the temporal component or its authority semantics.

Observed failed assertions (exact JSON reporter names):

- `CaseWorkspacePage MACHINE/rendered-DOM parity decodes the complete 'typed unavailable case' DOM from the rendered page` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (90.57299999999941 ms).
- `CaseWorkspacePage MACHINE/rendered-DOM parity decodes the complete 'available structural witness' DOM from the rendered page` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (12.81945799999994 ms).
- `CaseWorkspacePage MACHINE/rendered-DOM parity rejects a removed rendered authority fact` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (5.6001249999999345 ms).
- `CaseWorkspacePage MACHINE/rendered-DOM parity rejects a synthetic artifact link` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (4.848124999999527 ms).
- `CaseWorkspacePage MACHINE/rendered-DOM parity preserves the complete run-paper twin beside the acquisition flow` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (13.07300000000032 ms).

### R4-F16: `src/features/runs/routes/CaseWorkspacePage.test.tsx`

Disposition: **test-double export integration debt**. Proposed owner: **team-design**. This file’s emitted denominator: 8 assertions, statuses `{'failed': 7, 'passed': 1}`.

Seven assertions throw at the missing useOptionalI18n export; the remaining assertion passes. This module similarly replaces LocaleProvider without the new hook consumed by the actual temporal surface. Correct the fixture boundary and retain authorization, MACHINE-byte export, evidence-before-gate and authority-abstention assertions. A passing pre-render denied case is not evidence for the seven blocked paths.

Observed failed assertions (exact JSON reporter names):

- `CaseWorkspacePage authorizes before human-decision query and mutation` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (300.194125 ms).
- `CaseWorkspacePage keeps one run-bound acquisition route in the same case workspace` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (4.212625000000116 ms).
- `CaseWorkspacePage MACHINE export bytes equal the one human-decision response bytes` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (4.457333999999719 ms).
- `CaseWorkspacePage downloads verified evidence bytes before revalidating the action gate` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (9.778250000000298 ms).
- `CaseWorkspacePage renders the typed unavailable refusal and exports the captured bytes` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (4.126666999999543 ms).
- `CaseWorkspacePage keeps available authority states and negative object kinds distinct` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (3.8846250000005966 ms).
- `CaseWorkspacePage renders the bound record and each authority-abstaining nonreceipt` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (2.021582999999737 ms).

### R4-F17: `src/features/runs/routes/CycleBoardConsumerCensus.test.ts`

Disposition: **ambiguous setup failure**. Proposed owner: **team-design + team-devx**. This file’s emitted denominator: 5 assertions, statuses `{'skipped': 5}`.

The file reports failed with all five assertions skipped and an empty JSON message. Its beforeAll runs inspectConsumers(productionPopulation()) with a 45,000 ms timeout; no consumer property was checked. Default-reporter hook output is needed to distinguish a TypeScript census timeout or other setup error. Do not remove the census or infer that consumer counts are zero.

File-level receipt: `ambiguous: reporter omitted the setup/hook error`.

Collected but not executed after setup failed:

- `Cycle Board production consumer census has one acquisition-growth intake and one Cycle Board hook consumer` — `skipped`.
- `Cycle Board production consumer census has one page that owns the sole resolved hook call and renderer` — `skipped`.
- `Cycle Board production consumer census has one generated risk-spend intake, one page host, and one exact-byte exporter` — `skipped`.
- `Cycle Board production consumer census has one run-paper intake and one report-only emitter` — `skipped`.
- `Cycle Board production consumer census has one case-inspection intake, workspace hook and exact-byte exporter` — `skipped`.

### R4-F18: `src/features/runs/routes/CycleBoardPage.parity.test.tsx`

Disposition: **ambiguous execution failures**. Proposed owner: **team-design + team-devx**. This file’s emitted denominator: 16 assertions, statuses `{'passed': 12, 'failed': 4}`.

Four real-response/rendered-risk-spend cases return only STACK_TRACE_ERROR; their measured durations are recorded below. The other twelve assertions pass. The failing mutation family includes removal of a protected denial while caller and server-safe markers remain, hidden raw payload, and test-only proof marker. Their JSON errors do not establish a bad twin verdict; read the exact default-reporter reason and preserve all adversarial variants. Vitest truncates one generated parameter title; its source full name is protected denial while caller and server-safe markers remain.

Observed failed assertions (exact JSON reporter names):

- `CycleBoardPage MACHINE/rendered-DOM parity admits the real response and independently evaluates the visible risk-spend DOM` — `Error: STACK_TRACE_ERROR` (26418.293000000005 ms).
- `CycleBoardPage MACHINE/rendered-DOM parity blocks a 'protected denial while caller and ser…' mutation` — `Error: STACK_TRACE_ERROR` (21631.456583 ms).
- `CycleBoardPage MACHINE/rendered-DOM parity blocks a 'hidden raw payload' mutation` — `Error: STACK_TRACE_ERROR` (16893.02808299999 ms).
- `CycleBoardPage MACHINE/rendered-DOM parity blocks a 'test-only proof marker' mutation` — `Error: STACK_TRACE_ERROR` (20216.11229199999 ms).

### R4-F19: `src/features/runs/routes/RunReportPage.parity.test.tsx`

Disposition: **test-double export integration debt**. Proposed owner: **team-design**. This file’s emitted denominator: 7 assertions, statuses `{'failed': 7}`.

All seven assertions throw before they exercise parity because this file’s whole-module LocaleProvider mock provides useI18n alone and real TimeSemanticsLabel calls useOptionalI18n. Nearby RunReportPage.test.tsx already supplies both hooks. Smallest closure: correct the I18n fixture boundary, retain complete packet equality and every removed/duplicate/localized/synthetic-link removal probe, and re-run this complete file.

Observed failed assertions (exact JSON reporter names):

- `RunReportPage MACHINE/rendered-DOM parity decodes the complete 'typed unavailable case' DOM to the packet presentation` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (251.29904200000055 ms).
- `RunReportPage MACHINE/rendered-DOM parity decodes the complete 'available case with every issue kind' DOM to the packet presentation` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (73.87579100000039 ms).
- `RunReportPage MACHINE/rendered-DOM parity rejects a rendered 'removed fact' mutation` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (113.33958399999938 ms).
- `RunReportPage MACHINE/rendered-DOM parity rejects a rendered 'duplicate fact' mutation` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (81.96087499999976 ms).
- `RunReportPage MACHINE/rendered-DOM parity rejects a rendered 'localized authority fact' mutation` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (101.30987499999992 ms).
- `RunReportPage MACHINE/rendered-DOM parity rejects a rendered 'synthetic link' mutation` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (116.65933399999994 ms).
- `RunReportPage MACHINE/rendered-DOM parity requires an empty admitted-link roster to render zero anchors` — `Error: [vitest] No "useOptionalI18n" export is defined on the "@/shared/i18n/LocaleProvider" mock. Did you forget to return it from "vi.mock"?` (9.531957999999577 ms).

### R4-F20: `src/shared/ui/quantity/Quantity.test.tsx`

Disposition: **stale authority-positive expectation; preserve runtime fail-closed behavior**. Proposed owner: **team-design + team-architecture**. This file’s emitted denominator: 9 assertions, statuses `{'passed': 8, 'failed': 1}`.

The expanded Trust View case expects a button named verified from generated metadata field strings. Current trust-glyphs.ts intentionally produces unknown with content_bound_verification_receipt_missing for those markers, and TrustViewAuthority.test.tsx explicitly proves byte-identical owner markers stay below verified clothing. These tests disagree on the authority contract. Correct the stale positive test to preserve metadata details/one truth while expecting withheld verification, with a removal probe that fails if marker-derived authority is restored. Do not make production emit verified to satisfy this assertion. No assertion was changed here.

Observed failed assertions (exact JSON reporter names):

- `Quantity renders expanded Trust View metadata without fetching a different truth` — `TestingLibraryElementError: Unable to find an accessible element with the role "button" and name "verified"` (446.35591699999895 ms).

### R4-F21: `src/shared/ui/trust-view/trustViewArchitecture.test.ts`

Disposition: **frozen population gate blocks its own semantic census**. Proposed owner: **team-design + team-architecture**. This file’s emitted denominator: 41 assertions, statuses `{'passed': 40, 'failed': 1}`.

The test’s full tracked/physical source equality passes, then the historical 625-file pin blocks its consumer/issuer scan because the current complete production TS/TSX population is 650 = 319 TS + 331 TSX, compared with 625 = 304 + 321. This proves population growth, not a bypass. Smallest closure: reconcile all newly admitted production sources against the semantic consumers/issuer rules, preserve physical-vs-tracked equality, then replace or explicitly re-pin the historical size guard based on the true property. Do not merely accept 650 without executing the consumer and issuer assertions that currently occur after the pin.

Observed failed assertions (exact JSON reporter names):

- `shared Trust View architecture censuses every production consumer over the fixed 625-file C04 denominator` — `AssertionError: expected { all: 650, ts: 319, tsx: 331 } to deeply equal { all: 625, ts: 304, tsx: 321 }` (94.07195799999954 ms).

### R4-F22: `src/features/artifacts/bureaucratic/renderers/shared/BaseBureaucraticRenderer.test.tsx`

Disposition: **stale authority-positive expectation; preserve runtime fail-closed behavior**. Proposed owner: **team-design + team-architecture**. This file’s emitted denominator: 2 assertions, statuses `{'passed': 1, 'failed': 1}`.

The failing case requires verified from lineage.trust_metadata carrying verification_status/verified_by strings. The adjacent negative test and current shared TrustViewAuthority cases prohibit minting verification from projection-only metadata. trust-glyphs returns unknown/content_bound_verification_receipt_missing without a content-bound receipt, so restoring green by emitting verified would violate P32. Correct the positive fixture/expectation with owner-approved authority semantics and a removal probe; preserve visible verifier metadata without claiming receipt authority. No assertion was changed here.

Observed failed assertions (exact JSON reporter names):

- `BureaucraticBlockView Trust View authority renders verification carried by generated owner metadata` — `TestingLibraryElementError: Unable to find an element with the text: verified. This could be because the text is broken up by multiple elements. In this case, you can provide a function for your text matcher to make your matcher more flexible.` (105.31783300000006 ms).

## Row 4 owner-literal handback: complete generated/runtime delta

Denominator: every const/single-value-enum occurrence reached by the existing generatedOwnerLiteralInventory walker under all four packet roots in policy-engine/schemas/runtime_api_v1.openapi.json; compared by the multiset identity (rootSchema, path, value) against every runtime CONFIDENCE_LEDGER_OWNER_LITERAL_RULES entry. Generated110; runtime99; extra generated11; unmatched runtime0. Every extra below belongs to AvailableConfidenceLedgerRiskSpendPacket.

- `/source/related_artifact_bindings/*/binding_name` = `live_probe_journal_content_sha256`.
- `/source/related_artifact_bindings/*/binding_name` = `foundry_dependency_discriminant`.
- `/source/related_artifact_bindings/*/dependency_environment/authority_boundary/authoritative_for/*` = `dependency_environment_diagnosis`.
- `/source/related_artifact_bindings/*/dependency_environment/decision_role` = `ambient_non_decisive`.
- `/source/related_artifact_bindings/*/dependency_environment/predicate_class` = `recomputed`.
- `/source/related_artifact_bindings/*/dependency_environment/profile/resolver_name` = `uv`.
- `/source/related_artifact_bindings/*/dependency_environment/profile/rule_version` = `polisyos.foundry.dependency_discriminant.v1`.
- `/source/related_artifact_bindings/*/dependency_environment/profile/schema_version` = `polisyos.foundry.dependency-discriminant.v1`.
- `/source/related_artifact_bindings/*/relation` = `semantic_projection`.
- `/source/related_artifact_bindings/*/relative_path` = `architecture/policy_design_case/layer3_gy_n8_dependency_discriminant.json`.
- `/source/related_artifact_bindings/*/semantic_hash_rule_version` = `polisyos.foundry.dependency_discriminant.v1`.

The repeated relation occurrence has the same value in separate union arms; the repeated binding_name path has two different values. A branch-blind flat table cannot express the latter. This is the counterexample to an apparent 99→110 count-only repair.


## Row 4 station-provisioning refinement

After the baseline JSON, root independently executed the persistence child as the sole command, `.venv/bin/python apps/runtime-dashboard/scripts/persist_atlas_evidence.py </dev/null`, in `policy-engine`; it exited 1 before reading any request. The complete `policy-engine/.tmp/watcher-chain/python-child-base.log` reports `ModuleNotFoundError: No module named 'jsonschema'` at `persist_atlas_evidence.py:20`. The readiness test uses this same child and parses its stdout before checking status. This establishes a real same-station child failure that can produce the observed parser symptom; the original collection-cause attribution remains unestablished until its default-reporter stack identifies the failing call. Do not equate this separate child replay with that original stack. The first observed masked cause is jsonschema, not pydantic. This is incomplete local runtime provisioning, not a measured inherited product failure or evidence that CI lacks the dependency. Root subsequently synchronized the full runtime environment and completed the affected replay; the completed replay section below supersedes these station-only interim diagnoses.

The health-source validator also imports jsonschema (`scripts/validate_atlas_health_sources.py:16`), and the completed exact-command section below now records the original validator traceback identifying missing jsonschema.
## Row 4 completed exact coverage receipt and per-file disposition

Root executed the unchanged package command `corepack pnpm run test:coverage` as the sole gate invocation. It expands to `vitest run --coverage --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000 && node ./scripts/check-coverage-ratchet.mjs`. The process exited 1 after 789.25 seconds measured wall time; Vitest reports 788.12 seconds. Full log: `policy-engine/.tmp/watcher-chain/coverage-base.log`, SHA-256 `e98ea056d990ab094daaf698677fe3220eb7dd6ee3b80db79c2221cad3571f51`. The Vitest result was reached and read; the following coverage-ratchet command was not reached after the red test result. No remote CI run or push occurred.

Complete exact-command denominator: **403 test-file records = 16 failed + 386 passed + 1 skipped; 1,619 collected assertions = 50 failed + 1,539 passed + 30 skipped**. The 50 assertion failures belong to all 13 files listed in the table; three further file failures are collection/setup failures with no failed assertions. The 50 is this command’s measured result, not the assumption from the prompt.

| Test file | Failed / collected assertions | Disposition |
| --- | ---: | --- |
| `scripts/tokenProjectionParity.test.ts` | 1 / 11 | OPEN projection mismatch; atlas-ui package owner handback (outside allowed package paths). Preserve print safeguards. Full diagnosis: R4-F01. |
| `src/app/authz/authzDecisionSurfaces.test.tsx` | 2 / 2 | OPEN missing query-provider/hook fixture; retain authorization assertions. Full diagnosis: R4-F02. |
| `src/app/layout/layoutSurfaces.test.tsx` | 10 / 14 | OPEN missing query-provider/hook fixture; retain all layout assertions. Full diagnosis: R4-F03. |
| `src/shared/i18n/parity.test.ts` | 12 / 38 | OPEN catalog/declaration drift; adjudicate the enumerated uses and keep negative probes. Full diagnosis: R4-F04. |
| `src/features/trust/components/ClaimPostureRegister.free-growth.test.tsx` | 1 / 1 | OPEN in-dashboard fixture coupling debt; no outside-producer block. Full diagnosis: R4-F11. |
| `src/features/runs/domain/confidenceLedgerRiskSpend.test.ts` | 1 / 46 | OPEN dashboard branch-aware owner-contract integration; existing owner union is the source of truth. Full diagnosis: R4-F08. |
| `src/features/runs/routes/CaseWorkspacePage.parity.test.tsx` | 5 / 5 | OPEN incomplete LocaleProvider mock; retain DOM twin and removal probes. Full diagnosis: R4-F15. |
| `src/features/runs/routes/CaseWorkspacePage.test.tsx` | 7 / 8 | OPEN incomplete LocaleProvider mock; retain authority and export checks. Full diagnosis: R4-F16. |
| `src/features/runs/routes/RunReportPage.parity.test.tsx` | 7 / 7 | OPEN incomplete LocaleProvider mock; retain all seven semantic probes. Full diagnosis: R4-F19. |
| `src/features/runs/routes/CycleBoardConsumerCensus.test.ts` | 1 / 5 | OPEN expected-consumer roster drift: actual AcquisitionApprovalFlow.tsx plus CycleBoard.tsx; see refinement below. Full diagnosis: R4-F17. |
| `src/shared/ui/quantity/Quantity.test.tsx` | 1 / 9 | OPEN stale marker-derived verified expectation; preserve fail-closed runtime. Full diagnosis: R4-F20. |
| `src/shared/ui/trust-view/trustViewArchitecture.test.ts` | 1 / 41 | OPEN fixed historical population pin prevents semantic census from running. Full diagnosis: R4-F21. |
| `src/features/artifacts/bureaucratic/renderers/shared/BaseBureaucraticRenderer.test.tsx` | 1 / 2 | OPEN stale marker-derived verified expectation; preserve fail-closed runtime. Full diagnosis: R4-F22. |

| Additional failed file | Reached result | Final refinement |
| --- | --- | --- |
| `src/test/evidence/atlasHealthMetrics.test.ts` | 28 assertions setup-skipped | Exact log identifies missing jsonschema in validate_atlas_health_sources.py:17. Local provisioning failure, later replaced by the 28-case replay below. |
| `src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts` | No assertions collected | Exact log identifies JSON.parse(result.stdout) at invokePersistence:84 from module-level call:206. Separate child replay identified missing jsonschema; the original empty-output cause is an inference supported by that independent receipt, not a captured original child stderr. Later provisioned replay passes all 33 cases. |
| `src/features/runs/export/confidenceLedgerRiskSpendTwin.browser.test.tsx` | No assertions collected | OPEN browser/forks project-routing defect; preserve execution in Browser Mode and ensure a watcher reads it. |

Every failed assertion in the completed coverage command, grouped by its file (exact default-reporter identities):

**`scripts/tokenProjectionParity.test.ts`**

- `DTCG token projection parity > projects print tokens and export behavior`.

**`src/app/authz/authzDecisionSurfaces.test.tsx`**

- `current verified Authz decision across application chrome > restores the implicit analyst default only after identity becomes verified`.
- `current verified Authz decision across application chrome > test_unknown_authz_decision_never_defaults_authority_surface_to_allow`.

**`src/app/layout/layoutSurfaces.test.tsx`**

- `layout surfaces > renders the application shell with sidebar, header, and main content`.
- `layout surfaces > shows counterfactual controls on concrete run routes`.
- `layout surfaces > does not mount run-scoped controls for the global Cycle Board`.
- `layout surfaces > removes command and what-if entry surfaces when rollout flags are false`.
- `layout surfaces > switches to Atlas brand lockups when Atlas v2 is enabled`.
- `layout surfaces > renders bottom navigation only on real mobile widths`.
- `layout surfaces > renders header status badges and responds to theme and locale controls`.
- `layout surfaces > renders an open health label verbatim with neutral clothing`.
- `layout surfaces > uses decision_review_required and never status text for the review count`.
- `layout surfaces > renders loading and unavailable header states`.

**`src/shared/i18n/parity.test.ts`**

- `locale catalogs > justifies exactly every active non-ICU count-message identity`.
- `locale catalogs > requires every active en count message to be ICU plural or justified`.
- `locale catalogs > requires every active uk count message to be ICU plural or justified`.
- `locale catalogs > rejects the certified wrong en blocked output at the gate boundary`.
- `locale catalogs > rejects the certified wrong uk blocked output at the gate boundary`.
- `locale catalogs > does not use text shape to gate an invariant declaration`.
- `locale catalogs > rejects a real new active-catalog numeric use until it is declared`.
- `locale catalogs > rejects a stale declaration in one active locale independently`.
- `locale catalogs > derives point-use membership from ICU semantics, not brace markers`.
- `locale catalogs > freezes the complete quantitative-use declaration set`.
- `locale catalogs > requires complete active en quantitative-use declarations`.
- `locale catalogs > requires complete active uk quantitative-use declarations`.

**`src/features/trust/components/ClaimPostureRegister.free-growth.test.tsx`**

- `ClaimPostureRegister free growth > renders a producer-admitted new row without a subject switch`.

**`src/features/runs/domain/confidenceLedgerRiskSpend.test.ts`**

- `confidence-ledger risk-spend strict admission > covers every generated owner const and single-value enum with the runtime literal table`.

**`src/features/runs/routes/CaseWorkspacePage.parity.test.tsx`**

- `CaseWorkspacePage MACHINE/rendered-DOM parity > decodes the complete 'typed unavailable case' DOM from the rendered page`.
- `CaseWorkspacePage MACHINE/rendered-DOM parity > decodes the complete 'available structural witness' DOM from the rendered page`.
- `CaseWorkspacePage MACHINE/rendered-DOM parity > rejects a removed rendered authority fact`.
- `CaseWorkspacePage MACHINE/rendered-DOM parity > rejects a synthetic artifact link`.
- `CaseWorkspacePage MACHINE/rendered-DOM parity > preserves the complete run-paper twin beside the acquisition flow`.

**`src/features/runs/routes/CaseWorkspacePage.test.tsx`**

- `CaseWorkspacePage > authorizes before human-decision query and mutation`.
- `CaseWorkspacePage > keeps one run-bound acquisition route in the same case workspace`.
- `CaseWorkspacePage > MACHINE export bytes equal the one human-decision response bytes`.
- `CaseWorkspacePage > downloads verified evidence bytes before revalidating the action gate`.
- `CaseWorkspacePage > renders the typed unavailable refusal and exports the captured bytes`.
- `CaseWorkspacePage > keeps available authority states and negative object kinds distinct`.
- `CaseWorkspacePage > renders the bound record and each authority-abstaining nonreceipt`.

**`src/features/runs/routes/RunReportPage.parity.test.tsx`**

- `RunReportPage MACHINE/rendered-DOM parity > decodes the complete 'typed unavailable case' DOM to the packet presentation`.
- `RunReportPage MACHINE/rendered-DOM parity > decodes the complete 'available case with every issue kind' DOM to the packet presentation`.
- `RunReportPage MACHINE/rendered-DOM parity > rejects a rendered 'removed fact' mutation`.
- `RunReportPage MACHINE/rendered-DOM parity > rejects a rendered 'duplicate fact' mutation`.
- `RunReportPage MACHINE/rendered-DOM parity > rejects a rendered 'localized authority fact' mutation`.
- `RunReportPage MACHINE/rendered-DOM parity > rejects a rendered 'synthetic link' mutation`.
- `RunReportPage MACHINE/rendered-DOM parity > requires an empty admitted-link roster to render zero anchors`.

**`src/features/runs/routes/CycleBoardConsumerCensus.test.ts`**

- `Cycle Board production consumer census > has one acquisition-growth intake and one Cycle Board hook consumer`.

**`src/shared/ui/quantity/Quantity.test.tsx`**

- `Quantity > renders expanded Trust View metadata without fetching a different truth`.

**`src/shared/ui/trust-view/trustViewArchitecture.test.ts`**

- `shared Trust View architecture > censuses every production consumer over the fixed 625-file C04 denominator`.

**`src/features/artifacts/bureaucratic/renderers/shared/BaseBureaucraticRenderer.test.tsx`**

- `BureaucraticBlockView Trust View authority > renders verification carried by generated owner metadata`.

### Exact-command refinement of baseline ambiguities

Comparing every failure identity in the baseline JSON against every failure identity in the completed default-reporter log yields **nine baseline failures not repeated, one newly reached failure: 58 - 9 + 1 = 50**. All nine identities follow; their absence from this command’s complete failure list supersedes carrying them as persistent product failures. The baseline STACK_TRACE_ERROR placeholders remain historically ambiguous, but are not grounds to weaken these passing/reached paths.

- `src/features/runs/components/ConfidenceLedgerRiskSpend.a11y.test.tsx` — `ConfidenceLedgerRiskSpend accessibility > has no violations in the ordered reviewer surface or full-envelope dialog`.
- `src/features/runs/export/confidenceLedgerRiskSpendTwin.test.tsx` — `confidence-ledger risk-spend production twin > runs the shared preflight then independently reconciles all visible root and dialog text`.
- `src/features/runs/routes/CycleBoardPage.parity.test.tsx` — `CycleBoardPage MACHINE/rendered-DOM parity > admits the real response and independently evaluates the visible risk-spend DOM`.
- `src/features/runs/routes/CycleBoardPage.parity.test.tsx` — `CycleBoardPage MACHINE/rendered-DOM parity > blocks a 'hidden raw payload' mutation`.
- `src/features/runs/routes/CycleBoardPage.parity.test.tsx` — `CycleBoardPage MACHINE/rendered-DOM parity > blocks a 'protected denial while caller and ser…' mutation`.
- `src/features/runs/routes/CycleBoardPage.parity.test.tsx` — `CycleBoardPage MACHINE/rendered-DOM parity > blocks a 'test-only proof marker' mutation`.
- `src/features/trust/domain/posture.test.ts` — `trust posture artifact admission > captures response bytes before strict validation with no cache or fallback`.
- `src/features/trust/export/trustPostureTwin.test.ts` — `trust posture MACHINE and DOM twins > independently decodes every ordered public claim field and rejects DOM drift`.
- `src/test/evidence/atlasAutomatedEvidenceCapture.test.ts` — `Atlas automated evidence capture > executes Core put, resolve, lineage, and integrity checks and fails on corruption`.

Eight of those nine had baseline STACK_TRACE_ERROR placeholders; the remaining one was the missing `_build/apps/runtime-dashboard` parent in the Core evidence test. The coverage station now has that parent. No source or assertion repair caused their non-recurrence; command settings, resources and prepared output state differed.

Newly reached: `src/features/runs/routes/CycleBoardConsumerCensus.test.ts` — `Cycle Board production consumer census > has one acquisition-growth intake and one Cycle Board hook consumer`. Its complete TypeScript symbol census runs and observes `features/runs/components/AcquisitionApprovalFlow.tsx` and `features/runs/components/CycleBoard.tsx` calling the canonical `useAcquisitionGrowth`, against a one-consumer expectation. The acquisition client intake assertion immediately above passes; this is a consumer roster disagreement, not evidence of a second producer intake. Proposed owner team-design. Reconcile the approval-flow use (growth history/refetch) with intended consumers, retain the canonical symbol/source scan, and update the roster with a removal/bypass probe. Removing the legitimate flow to fit a historical count is not a repair.

### Provisioned Python replay: newly reached checks

After completing the exact coverage command, root synchronized the full runtime Python environment. The targeted replay did not change source or test assertions. Artifact `policy-engine/.tmp/watcher-chain/python-replay.json`, SHA-256 `e54d54a03abcc61c5731aeaa84fa1b5b5acdcc74c74b05c88d0f8bf799877ad0`: **3 files, 77 assertions = 74 passed + 3 failed + 0 skipped**, exit 1, measured wall time 66.03 seconds.

| Python-dependent test file | Complete replay population | Disposition |
| --- | --- | --- |
| `src/test/evidence/atlasAutomatedEvidenceCapture.test.ts` | 16 = 16 passed | Local provisioning/setup block cleared; all assertions reached and passed. |
| `src/test/evidence/atlasHealthMetrics.test.ts` | 28 = 25 passed + 3 failed | Setup block cleared; three stale persistence-adapter expectations remain OPEN (team-design + team-devx). |
| `src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts` | 33 = 33 passed | Local provisioning/setup block cleared; all assertions reached and passed. |

All three newly reached health failures:

- `Atlas health metrics registers the unchanged Python persistence adapter as consumer missing` — `AssertionError: expected { status: +0, …(2) } to match object { status: 1, stderr: '' }`.
- `Atlas health metrics ignores a caller PATH node that emits a schema-valid forged report` — `AssertionError: expected { status: +0, …(2) } to match object { status: 1, stderr: '' }`.
- `Atlas health metrics does not inherit caller NODE_OPTIONS into the fixed producer` — `AssertionError: expected { status: +0, …(2) } to match object { status: 1, stderr: '' }`.

The existing tests expect persistence exit 1 and a consumer_missing-era error, while the real adapter returns exit 0. The first case’s title and expected envelope are stale. The PATH-forged-node and NODE_OPTIONS-preload cases assert that stale status before they reach `expect(existsSync(marker)).toBe(false)`. Therefore the current red receipt establishes neither injection immunity nor an injection vulnerability: those decisive marker assertions were not reached. Smallest closure: validate the actual persisted, content-bound receipt and the recomputed source binding; keep both adversarial environment inputs and execute their marker/forged-report checks regardless of the revised success envelope. Do not merely change status 1 to 0 or infer that success is authority.

The provisioned readiness file collects 33 assertions that the earlier whole-suite command could not collect. Replacing the three Python file populations in the 403-file baseline with their complete replay populations yields **1,652 declared assertions** (script-summed), reconciling the prompt’s denominator. This is a union of measured local receipts, not a fabricated single full-suite run with a new aggregate result.

## Row 4 complete Python dependency census and final replay scope

Reproducible script: `policy-engine/.tmp/watcher-chain/census-python-tests.mjs`; complete artifact: `policy-engine/.tmp/watcher-chain/python-test-dependency-census.json`. The scanner walked every one of **1173 dashboard `.ts`, `.tsx`, `.js`, `.jsx`, `.mts`, `.cts`, `.mjs`, `.cjs` source files**, excluding dependency/build directories (`node_modules`, `.git`, `dist`, `coverage`, `test-results`, `playwright-report`) and declarations. It mapped **all 403 emitted unit-test file records**, with **0 unmapped test files and 0 unresolved relative/@ runtime imports**. It parsed subprocess imports/calls and recursively followed runtime local imports/re-exports/dynamic literal imports into helpers; type-only imports were excluded.

The complete local import graph reaches subprocess calls from **6 unit-test files**. The Python-executing set is the following **four files**; the other two reachable files (`CycleBoardConsumerCensus.test.ts` and `trustViewArchitecture.test.ts`) execute git only, and do not require a Python replay.

| Python-executing test file | Static call chain / reason | Final replay |
| --- | --- | --- |
| `src/test/evidence/atlasAutomatedEvidenceCapture.test.ts` | Direct `spawnSync("python3", [scripts/persist_atlas_evidence.py])`; imported `captureAtlasEvidence.ts` also reaches the same Python bridge. | 16 / 16 passed after runtime provisioning and output-parent availability. |
| `src/test/evidence/atlasHealthMetrics.test.ts` | Explicit `.venv/bin/python` calls; `atlasHealthMetrics.ts` invokes `validate_atlas_health_sources.py` and the Node DS18 outcome runner, which itself invokes `.venv/bin/python`. | 25 passed / 3 failed / 28 reached; all three failures named above. |
| `src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts` | Explicit `.venv/bin/python` persistence and validator witnesses; imported reconciliation helper invokes the Python source validator. | 33 / 33 passed after full runtime provisioning. |
| `src/shared/lib/domain/workflow.test.ts` | Direct `spawnSync("python3", ["-c", script])`; script imports `architecture.atlas_surfaces.check_status_retirement_inventory` and executes real `validate_inventory` removal probes. | 3 / 3 passed, 0 failed, 0 skipped; exit 0, measured wall time 5.22 seconds. |

The strict set referencing the repository `.venv` directly is health plus readiness; replaying all four Python-executing files also covers the explicit `python3` PATH callers. All four have now completed and their results were read. Script files with subprocess calls but no local runtime-import path from any of the 403 active unit tests are recorded separately in the census artifact, rather than silently added to this unit replay set. The Playwright web-server Python command is configuration for another test runner; the unit visual-regression contract test reads that declaration without launching it.

No additional tests are pending in this diagnosis. No source/test assertion changes were made. OPEN product/test-integration findings retain the owners and closure moves above; the local Python provisioning errors have been superseded by actual executed-case receipts.



## Final verification, provenance, and limits

The changed tracked paths are this required journal and `tests/repo_quality/tools/test_repo_hooks.py`. A complete `git ls-tree -r --name-only 938ddc32a -- policy-engine/apps/runtime-dashboard` denominator has 1,311 tracked paths; the changed-path intersection is zero. The 1,160 admitted lint paths were independently enumerated using the actual ESLint ignore predicate; their changed-path intersection is also zero. `git diff 938ddc32a -- policy-engine/apps/runtime-dashboard policy-engine/tools/design policy-engine/tools/devx/install_repo_hooks.mjs policy-engine/packages policy-engine/pnpm-lock.yaml policy-engine/package.json` was empty. This supports source-level inheritance of the reproduced diagnostics; local missing dependencies, first-use output directories, and ambiguous timing outcomes are separately named, never exported as inherited product defects.

Runtime Python provisioning: offline preflight in a separate environment failed because the pinned jaxlib wheel was absent from cache. Normal frozen sync populated that isolated environment successfully. After the exact coverage run completed, `uv sync --offline --frozen --extra lint --extra test --extra runtime` populated the lane's `.venv`, exit 0. The extras match the CI runtime bootstrap profile. No active gate's interpreter environment was mutated mid-run. Targeted Python-dependent frontend replays and their complete population census are recorded above; no broad Python suite ran.

The initial root hook verification without a fixture cutoff failed during global pytest plugin import because the minimal environment lacked pydantic; it did not execute a hook case. The standalone proof then passed 8/8 with `--noconftest`. After runtime provisioning, the normal repository command `.venv/bin/python -m pytest tests/repo_quality/tools/test_repo_hooks.py -q --junitxml=.tmp/watcher-chain/hooks-runtime-env.xml` passed all **8/8 cases**, zero failures/errors/skips, JUnit wall time **7.946s**. Thus the earlier fixture-cutoff limitation no longer limits hook closeout. Final `ruff check` for the changed Python module passed. Every changed assertion was disclosed above: none was removed or weakened; all six removal mutants were caught.

Independent review checked the hook diff and complete Row 4 population. It corrected two proposed blockers before delivery: owner-literal union admission can be fixed entirely in dashboard code using the existing owner contract; the free-growth consumer fixture also admits an in-dashboard repair. Both are OPEN work, not asserted architect/file-boundary blockers. The actual Row 4 stop is the forbidden CI scheduling surface; proposed scheduling does not itself repair the measured lint/code/test debts. Print projection repair separately needs the forbidden atlas-ui package path. No failure is hidden behind a skipped file or changed assertion.

Pattern register reopened before closeout: P02, P29, P31, P33, P35, P38, P40, P41. Rows 1–3 have an executed-and-read hook chain; no new policy authority capability is claimed. Row 4 remains `implemented_but_not_orchestrated` for guaranteed CI reachability, with a result-consumer bridge handback. Local completed red is evidence only for the local execution, not for an unrun remote workflow. The coverage ratchet after Vitest's `&&` was not reached; no coverage-threshold claim is made.

No further full-suite replay was needed after source freeze: the exact full dashboard command was read to completion, the newly provisioned interpreter's entire affected frontend test set was replayed separately, and the only source change has a fresh normal-environment targeted regression receipt. The targeted-replay union reconciles the declared 1,652 assertions but is not represented as a single green run. The final branch/file readback and clean attached status are required before reporting delivery.
