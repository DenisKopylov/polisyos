# Watcher chain — 2026-09-07

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

Row 4: in progress. Unchanged-base full Vitest and each CI predecessor started before dashboard source edits. Evidence is stored in ignored `policy-engine/.tmp/watcher-chain/`; final durable per-file evidence will be included here.


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
