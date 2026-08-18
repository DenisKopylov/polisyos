# CI Bootstrap Infrastructure Repair Plan

> **Execution rule:** work only in the isolated worktree
> `/workspace/scratch/d479b0fb609b/polisyos-ci-bootstrap` on branch
> `fix/ci-bootstrap-ordering`, based on `main` commit
> `4813b49f6ce14e8debf3aaea096f0967d38d9768`. Keep the research stack and the
> user's unrelated dirty-worktree changes untouched. Every repair is RED-first,
> focused-verified, and then included in one separate infrastructure PR.

**Goal:** Remove the inherited CI/bootstrap failures that block the PAO-R0/PAO-R1
research stack, prove that the repairs are structural rather than
research-document exceptions, and run the smallest review-relevant local and
GitHub verification chain before resuming the research audit. Repository-wide
failures outside this repair remain separately classified base debt.

**Observed failures:**

1. The Python composite action invokes `tools.cli` before dependencies are
   installed, so importing `click` fails on a clean runner.
2. The dashboard composite action asks `actions/setup-node` to query a pnpm
   cache before pnpm exists on `PATH`.
3. The release workflow uses an unguarded `sha256sum *` glob and fails
   actionlint/ShellCheck SC2035.
4. Once the pre-sync Python failure is removed, the universal lock selects
   `Pillow 10.4.0` through `marker-pdf`/`surya-ocr`, although the project
   requires Python 3.14. Pillow 10 does not support Python 3.14 and has no
   CPython 3.14 wheel, so a clean `uv sync --frozen` falls into an unsupported
   source build.
5. The Phase 2A topology test requires generated, ignored `_build` and `_cache`
   directories to exist, so its clean-checkout variant fails even when there is
   no wrong-root state.
6. The `test` dependency extra omits the `ml` and `solvers` extras even though
   the selected unit/repository-quality tests import scikit-learn
   unconditionally and the universality preflight imports OR-Tools.

**Smallest owner-preserving repair:**

- invoke the existing stdlib-only `tools.devx.workspace.bootstrap` module
  directly for the pre-sync Python bootstrap;
- remove the premature pnpm cache request while retaining the repository's
  pinned Corepack/package-manager path;
- pass the release checksum glob after `--` and qualify it with `./`;
- remove the advertised table-extraction extra after proving that no released
  compatible `marker-pdf`/`surya-ocr` chain exists for Python 3.14; preserve the
  existing runtime import boundary as unavailable and document the limitation;
- permit canonical generated roots to be absent while continuing to reject
  every non-canonical occurrence;
- make the `test` profile include the existing `ml` and `solvers` extras needed
  by tests that are collected unconditionally;
- add repository-quality regression tests that fail on the old ordering and
  exercise the dependency-free Python import path.

## Pattern and capability pass

- Relevant failure patterns: P01/P02 (a declared CI capability with a broken
  producer bridge), P10 (workflow shape is not execution adequacy), P27
  (preserve the canonical bootstrap owner), P29 (exercise the real clean-import
  path), P31 (repair the ordering invariant, not one job), P33 (test the
  dependency-absent variant), and P34 (prove the failure is inherited and the
  repair is isolated).
- Canonical owners retained: `tools.devx.workspace.bootstrap` owns profile
  synchronization; Corepack and the root `packageManager` pin own pnpm
  selection; actionlint owns workflow-shell linting.
- No new bootstrapper, dependency manager, workflow status lattice, or
  research-specific bypass is permitted.

## Task 1 — Freeze the clean-runner bootstrap contracts (RED)

**Files:**

- Create:
  `tests/repo_quality/tools/test_ci_bootstrap_contracts.py`

**Steps:**

1. Add a test that extracts the profile-sync command from
   `.github/actions/setup-policy-engine-python/action.yml` and requires it to
   invoke `python3 -m tools.devx.workspace.bootstrap`, never the dependencyful
   `tools.cli` façade.
2. In the same test, run
   `python3 -S -m tools.devx.workspace.bootstrap --help` from `policy-engine`
   so the contract proves the selected module imports without site packages.
3. Add a test that walks dashboard composite-action steps in order and rejects
   any `cache: pnpm` request before an explicit pnpm provisioning step.
4. Add a test that requires the release checksum command to use an
   option-terminating, path-qualified glob.
5. Run:

   ```bash
   uv run --frozen --extra lint --extra test pytest \
     tests/repo_quality/tools/test_ci_bootstrap_contracts.py -q
   ```

   Expected: three failures matching the three confirmed CI root causes.

## Task 2 — Repair the Python bootstrap ordering (GREEN)

**Files:**

- Modify:
  `../.github/actions/setup-policy-engine-python/action.yml`

**Steps:**

1. Replace only the pre-sync `tools.cli workspace bootstrap` invocation with
   `python3 -m tools.devx.workspace.bootstrap`.
2. Preserve the existing profile, frontend, Playwright, hooks, and doctor
   arguments.
3. Run the Python contract test alone and confirm it passes.
4. Run the dependency-free import probe directly:

   ```bash
   python3 -S -m tools.devx.workspace.bootstrap --help
   ```

5. Run existing workspace bootstrap command tests:

   ```bash
   uv run --frozen --extra lint --extra test pytest \
     tests/repo_quality/tools/test_workspace_phase3.py -q
   ```

## Task 3 — Repair the pnpm bootstrap ordering (GREEN)

**Files:**

- Modify:
  `../.github/actions/setup-runtime-dashboard/action.yml`

**Steps:**

1. Remove `cache: "pnpm"` and `cache-dependency-path` from the pre-provision
   `actions/setup-node` step.
2. Preserve Node 22 setup and the existing
   `corepack pnpm install --frozen-lockfile` command, which resolves the pinned
   `pnpm@10.33.2` from the root `packageManager`.
3. Run the dashboard ordering contract test alone and confirm it passes.
4. Run:

   ```bash
   corepack pnpm --version
   corepack pnpm install --frozen-lockfile --ignore-scripts
   ```

   from `policy-engine`, then run the repository's focused frontend checks
   reachable without Playwright browsers.

## Task 4 — Repair release actionlint failure (GREEN)

**Files:**

- Modify:
  `../.github/workflows/release.yml`

**Steps:**

1. Change the checksum command to
   `sha256sum -- ./* > SHA256SUMS`.
2. Run the release glob contract test alone and confirm it passes.
3. Install/run the repository-pinned actionlint 1.7.12 through
   `tools/quality/ci/install_actionlint.sh`; if network policy blocks the
   installer, report that separately and rely only on GitHub Actions for this
   external-tool surface.
4. Run the PolicyOS workflow-policy checker and release topology/operability
   tests.

## Task 4A — Repair Python 3.14 dependency-lock compatibility

**Files:**

- Modify only after a temporary resolver probe demonstrates the narrowest
  supportable result:
  - `pyproject.toml` if a lower bound must be raised;
  - `uv.lock` through the repository-pinned uv 0.9.21 resolver.

**Steps:**

1. Preserve the failed clean-sync output as RED evidence.
2. Resolve only `marker-pdf`, `surya-ocr`, and `pillow` in a temporary copy and
   inspect every lock delta.
3. Prefer a compatible current `marker-pdf`/`surya` chain. Do not downgrade
   Python or invent a no-op extra merely to make CI green.
4. If no compatible released chain exists, preserve the implementation's
   optional import boundary, remove the un-installable project extra, and
   document the unavailable/fail-closed capability state.
5. Regenerate the lock with uv 0.9.21 and verify that Pillow resolves to a
   Python 3.14-supported release.
6. Run a clean `uv sync --frozen --extra lint --extra test` under Python 3.14,
   then import Pillow and report its resolved version.

## Task 4B — Repair clean-checkout topology semantics

**Files:**

- Modify:
  `tests/repo_quality/architecture/test_repository_sota_phase3_topology_cleanup.py`

**Steps:**

1. Preserve the failing clean-checkout test result as RED evidence.
2. Change the singleton invariant from “every generated root must exist” to
   “every occurrence, if present, must equal the canonical product-root path.”
3. Preserve rejection of outer-root or nested duplicates.
4. Re-run the release, supply-chain, and topology contract suites.

## Task 4C — Close the test-profile dependency contract

**Files:**

- Modify:
  - `pyproject.toml`;
  - `uv.lock` through the repository-pinned uv 0.9.21 resolver.

**Steps:**

1. Preserve the collection/import failures for scikit-learn and OR-Tools as
   RED evidence.
2. Add the existing `ml` and `solvers` extras to `test`; do not duplicate their
   package lists.
3. Extend the bootstrap regression test to require both extra references.
4. Run frozen sync and direct import probes for Pillow, scikit-learn, and
   OR-Tools under Python 3.14.

## Task 5 — Targeted local verification for review and research audit

**Files:**

- Modify only if a test exposes a repair-related regression.

**Steps:**

1. Run the new regression suite and existing acceptance/toolchain tests.
2. Run Ruff on the new Python test.
3. Run actionlint and workflow-policy checks.
4. Run the bounded 70-test matrix covering bootstrap contracts, workspace
   bootstrap, acceptance audit, release operability, control-plane supply
   chain, clean-checkout topology, document normalization, and full-text
   resolution.
5. Sample the broader backend suite only far enough to classify the first
   repeatable failure. Do not wait for all 16,576 tests after the user directed
   a targeted review set.
6. Attempt the frontend frozen install twice at most. If the external registry
   proxy prevents a cold install, record the exact limitation and rely on the
   ordered bootstrap contract plus GitHub Actions; do not call frontend checks
   locally green.
7. Run `git diff --check`, inspect the complete diff, and reopen
   `docs/reference/policy-design-case-failure-patterns.md` for the after-state
   pattern pass.
8. Confirm the primary dirty checkout remains unchanged at its two pre-existing
   user modifications.

## Task 6 — Publish and verify the infrastructure PR

**Files:**

- No additional source changes unless GitHub Actions exposes a directly related
  issue.

**Steps:**

1. Review the branch with the verification-before-completion and
   requesting-code-review procedures.
2. Commit the scoped infrastructure repair.
3. Push `fix/ci-bootstrap-ordering` and open a draft PR against `main`,
   explicitly linking the matching failures on base PR #4 and research PR #5.
4. Wait for all GitHub Actions jobs to reach terminal state.
5. If a repair-related job fails, diagnose from the full job log and return to
   RED-first repair. Classify known base-policy/baseline failures separately;
   do not relabel an inherited, skipped, or blocked job as green.
6. Do not merge without explicit user authorization.

## Task 7 — Resume and complete the PAO research audit

1. Audit the research stack against a reproducible tested overlay of the
   infrastructure branch without merging or force-pushing unrelated history.
2. Re-run the review-relevant PR #4 and PR #5 checks on that overlay and
   classify unrelated base-policy/baseline failures separately.
3. Verify the PAO-R0/PAO-R1 files, indexes, source hashes, front matter,
   cross-references, ledger, conformance report, and exact changed-file scope.
4. Distinguish:
   - research-content findings;
   - repository integration findings;
   - infrastructure findings;
   - external/manual checks that cannot be proven in this environment.
5. Produce a final evidence-backed audit receipt. Do not claim merge,
   production authorization, or external institutional performance.
