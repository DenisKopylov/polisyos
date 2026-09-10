# Dashboard measuring apparatus: execution binding and reached verdicts

Stage 1 decision document, 2026-09-10. Workstream B. The user has authorized implementation; the required sequencing boundary is
commit and branch read-back of the Stage 1 decision package before the red-first
implementation sequence below. No further user approval is required. Source baseline: `c49449343`; research
checkout: `.worktrees/apparatus`, branch `codex/measuring-apparatus`. The first
shared commit, `4de45d2b5`, only ignores raw receipts. No register or ledger edit
belongs to this workstream.

## Decision

Keep the existing independent CI coverage watcher and the already implemented
choice to run only typecheck on pre-push. Close the Python execution split by
binding the remaining dashboard Python children to the checkout's provisioned
interpreter, using the existing process-result owner for diagnostics. Repair the
stable-readiness *test fixture* so its producer uses the same Node executable
chosen by the existing production authority. Do not relax executable provenance,
add an environment override to the production authority, increase timeouts, change
product expectations, skip evidence tests, or add a parallel CI workflow.

The register's historical three-failure explanation is refuted by the original CI
log. Two tests failed importing `jsonschema`; the third rejected the wrong Node
executable provenance. The declaration that one dependency line closes all three
is not an admissible design premise. At this baseline `jsonschema` is already in
the `test` extra, which is already included in the CI runtime bootstrap profile.
Provisioning the correct environment and invoking that environment are different
operations. The implementation must bind both.

## Exact debt rows and measurement class

| Debt row | Check-never-ran versus wrong-station | Current repair/closure boundary |
| --- | --- | --- |
| `evidence-tests-launch-python-that-the-station-does-not-provision` | Missing interpreter/package prevents setup or collection; bare Python is the wrong-station mechanism producing that absence | Bind all measured consumers to provisioned project Python, retain failed-child cause, exercise actual consumers |
| `pre-push-hook-runs-the-suite-in-a-configuration-ci-never-uses` | Historical wrong execution station/configuration: local default worker count versus CI serialization | Typecheck-only hook decision is already implemented; add behavioral dispatch proof without pushing |
| `dashboard-unit-suite-has-fifty-failures-nothing-was-running` | Historical predecessor/hook no-op meant check never ran; original reached CI partitions two wrong-Python failures and one wrong-Node fixture | Preserve independent watcher and full suite population; repair apparatus causes; read complete local and eventual authorized remote results separately |

## Scope, owner composition, and unchanged seams

The apparatus owns whether a check executes with its declared inputs and whether
its result is honestly reported. It does not own weaker policy admission,
readiness, authority, or product behavior. The identity-boundary classification is
**own** for our check launch and verdict; **integrate** for Python/Node/browser
provisioners. There is no new public product capability, schema, enum, or gate.

Compose these existing owners:

| Owner | Existing responsibility | Planned use |
| --- | --- | --- |
| `tools/devx/workspace/_common.py::UV_SYNC_PROFILES` and `bootstrap.py` | Runtime profile is `lint`, `test`, `runtime` | Provision the interpreter used by dashboard evidence; no new profile |
| `pyproject.toml` `test` extra | Already declares `jsonschema[format-nongpl]>=4.25.1` | Verify locked runtime-profile import; do not add a duplicate dependency |
| `.github/actions/setup-policy-engine-python/action.yml` | Creates `policy-engine/.venv` through bootstrap | Existing CI environment, consumed by fixed-locator children |
| `.github/actions/setup-runtime-dashboard/action.yml` | Node 22, pinned pnpm, workspace packages, Chromium | Keep these responsibilities, including Browser Mode installation |
| `src/test/evidence/persistenceProcessResult.ts` | Failed child diagnostic, refusal envelope, watchdog ordering | Extend with checkout-bound interpreter locator or launcher; retain diagnostic behavior |
| `scripts/persist_atlas_evidence.py` | Core CAS persistence, trusted Node selection, content/provenance admission | Call unchanged; use `_trusted_node()` in the test fixture preparation, not a test-declared replacement |
| `atlasSurfaceReadinessReconciliation.ts::buildAtlasStableReadinessNegativeControl` | Produces the stable zero-instance negative control with actual executable provenance | Execute under the canonical producer Node for its admission test |
| `apps/runtime-dashboard/lefthook.yml` | Pre-push typecheck only; pre-commit formatting, lint and design checks | Preserve decision and prove actual dispatch |
| `.github/workflows/ci.yml::frontend-unit-coverage` | Independent suite with Chromium and Python | Preserve no predecessor `needs`; retain aggregate requirement that coverage result equals success |
| `tests/repo_quality/tools/test_repo_hooks.py` | Real Git/Lefthook fixture behavior | Add behavioral pre-push decision coverage, without invoking git push |

Paths in this section are relative to `policy-engine/` except `.github/**`.
The Core put/resolve/lineage/integrity implementation, executable allowlist,
readiness status/authority rules, schema ownership, public projections, coverage
ratchet thresholds, Vitest include/exclude populations and existing liveness
watchdogs remain unchanged. Healthy health/readiness Python locators already bind
`.venv/bin/python`; preserve their authority-sensitive fixed environments. Their
unavailable-launch diagnostics may gain the explicit UNRUN indication required
below, without changing their existing refusal codes or admission meaning.

## Pattern pass and capability reality

- **P31/P27**: three bare-Python consumers share one launch class. Bind them through
  one existing process owner, including the production capture CLI sibling. Do
  not fix only the two CI test lines.
- **P29/P32/P33**: test actual child execution, errors, CAS persistence and real
  hook dispatch. A search for `.venv` or `maxWorkers` is not a behavioral proof.
- **P35/P36**: distinguish file denominator from assertion denominator; the
  original CI finding is cited by run and test identity, not the register's aside.
- **P37/P38**: declared provisioning is not executed interpreter identity; a
  skipped suite is not a green suite; a locally passed producer is not the
  executable selected by the authority on another station.
- **P40**: classify a review as a new class or the same class deeper before repair.
  A second execution-binding escape widens the launch mechanism to all measured
  consumers, or establishes a bounded residual with its falsifier. It does not
  start a line-by-line repair ladder.
- **P41/P34**: baseline red attribution uses the slice base and the complete input
  denominator. A red caused by a changed dependency, fixture, script or source is
  ours even if its asserting file is unchanged. No unfinished isolation licenses
  the word inherited.
- **P13**: reuse bootstrap, CI job and error decoder; no new dependency manager,
  result database, duplicate watcher or synthetic governance contract.

Current missing labels: Python execution/provisioning chain is
`verification_missing` for station-independent operation and the capture sibling
has a diagnostic bridge gap; the pre-push decision is implemented but lacks a
specific regression witness (`semantic_test_missing`); CI reaches the suite but
has no successful repaired-tree result (`verification_missing`). The product
surface is `surface_out_of_scope`. Closing this apparatus means input condition →
real child/runner → complete result artifact → existing consumer verdict → log/CI
surface → negative semantic witness, not a new public capability claim.

## Research findings and actual cause partitions

### B-F01: bare Python is a different station from the provisioned Python

Read all direct `node:child_process` consumers in the dashboard source/script
population. A filesystem walk covered 1,173 `.ts`, `.tsx`, `.mjs`, `.js` files under
`apps/runtime-dashboard`, excluding `node_modules` and `.git`; it found 15 direct
child-process import files. The complete exploratory census is in
`../journals/apparatus/dashboard/raw/dashboard-child-process-census.json` (ignored
raw, not an independent source of truth).

Three actual Python launch sites still use the literal `python3`:

1. `src/test/evidence/atlasAutomatedEvidenceCapture.test.ts::invokeCoreAdapter`.
2. `src/shared/lib/domain/workflow.test.ts`, the C22d vocabulary-revival witness.
3. `src/test/evidence/captureAtlasEvidence.ts::invokePersistenceBridge`, the
   production capture sibling.

Health/readiness source validation, their persistence fixtures and the DS18
outcome runner already use the repository locator. `--python synthetic-python`
in an automated-capture refusal test is deliberately rejected input, not another
launcher. `/nonexistent/atlas-python` in the diagnostics test is a deliberate
missing-executable probe. Other child-process consumers execute Git, Node,
Vitest or a package-manager contract-fixture wrapper, not Python.

Present-day generic import probes show ambient station contamination:
`python3` resolves to Homebrew Python 3.14 and imports jsonschema, but a generic
`python3 -c 'import polisyos.core.artifacts'` binds the **main checkout**
`/Users/deniskopylov/polisyos/policy-engine/src`, not this worktree. Both ambient
probes exit 0. `.venv/bin/python` imports jsonschema and Core from the **apparatus
worktree**, exit 0. `/usr/bin/python3` cannot import jsonschema, exit 1. Complete
outputs are `raw/ambient-python-import.log`, `raw/ambient-core-import.log`,
`raw/project-python-import.log`, and `raw/system-python-import.log`.

That generic import is **not evidence that the real persistence consumer imports
wrong source**: `persist_atlas_evidence.py::_ensure_worktree_import_root()` already
inserts its own source root before Core operations. Reuse and preserve this
existing binding owner. Its earlier jsonschema import occurs before that source
bootstrap, which explains why the dependency failure still escapes it. A direct replay of that real bootstrap under ambient Python imports Core from
the apparatus worktree, exit 0 (`raw/ambient-real-import-binding.log`). Verify
actual consumer import binding rather than generalizing the generic import
probe; a zero exit alone does not establish checkout identity.

The repository `.venv/bin/python` must stay the locator, rather than its resolved
base-interpreter realpath: resolving away the venv locator can drop the very
site-packages selection being repaired. Artifact provenance may separately record
the real executable identity where its existing contract requires it.

**Property:** dependency provisioning and child execution refer to one checkout.
**Actual old predicate:** PATH has some executable named `python3`.
**Divergent case:** runtime bootstrap installs jsonschema into `.venv`, then the
frontend process inherits a PATH whose first Python is `/usr/bin/python3`.
The launch still fails before the product assertion. Interpreter choice must be
`recomputed` from the module's checkout, not `consumer_asserted` through an env
variable or PATH fallback.

### B-F02: 28 setup-skipped and collection-empty are not failed product assertions

The older exact-command receipt in
`docs/superpowers/journals/2026-09-07-watcher-chain.md`, section “Row 4 completed
exact coverage receipt”, distinguishes 403 file records from 1,619 assertions:
16 failed + 386 passed + 1 skipped files; 50 failed + 1,539 passed + 30 skipped
assertions. Its health file has 28 setup-skipped assertions and its readiness file
has no collected assertions. That journal explicitly identifies the readiness
jsonschema attribution as an inference from a separate child replay, not captured
original stderr. Preserve that distinction.

Current code verifies the mechanism: health measures in `beforeAll`; readiness
calls persistence inside `describe` before declaring its generated tests. A
missing prerequisite can therefore skip health setup and prevent readiness
collection. The first present-day baseline was interrupted after the root began
provisioning `.venv` concurrently. Its log contains health “28 tests | 28 skipped”
but no completed suite or readiness verdict. Actual interruption exit: **130**.
`raw/baseline-coverage.log` is a non-verdict and must never substantiate a suite
count or closure. A fresh missing-interpreter targeted falsifier is required in
an isolated fixture/station during execution.

The previous masking repair is real: `parsePersistenceProcessResult` names launch
errors, signals, stderr and malformed stdout, while preserving deliberately
refused nonzero JSON envelopes for semantic assertions. The capture CLI sibling
still has its own JSON-first decoder; compose the existing decoder there so a
failed launch reaches the same diagnostic path. A nonzero JSON refusal remains
negative evidence, never success.

### B-F03: original CI gives two causes, not one

Original source: GitHub run **34196405796**, revision
`20082e545ba89cefc2fd913e1723f6ef7c63df39`, job “Standard PR / Frontend unit
coverage”, 2026-09-08. Station lane downloaded the complete failed-job log to
`../journals/apparatus/station/raw/run-34196405796-failed.log`; this workstream read
its failure section and reproduced its summary arithmetic from the full log.

- **Files:** 3 failed + 401 passed + 1 skipped = **405**.
- **Assertions:** 3 failed + 1,787 passed + 2 skipped = **1,792**.
- **Vitest duration:** **1,006.01 seconds**.

| Exact failed test | Actual error | Disposition |
| --- | --- | --- |
| `atlasAutomatedEvidenceCapture.test.ts > Atlas automated evidence capture > executes Core put, resolve, lineage, and integrity checks and fails on corruption` | `persist_atlas_evidence.py:20`, missing `jsonschema` | Wrong interpreter; check body cannot reach Core assertions |
| `workflow.test.ts > workflow domain > source flips reject every C22d return vocabulary revival` | `check_status_retirement_inventory.py:19`, missing `jsonschema` | Wrong interpreter; validator cannot reach semantic assertions |
| `atlasSurfaceReadinessReconciliation.test.ts > Atlas surface-readiness per-claim reconciliation > gates the zero-instance stable arm identically to implemented` | `_require_observed_readiness_basis`: `canonical check executable provenance mismatch` | Test fixture produced with different Node from canonical admission; authority correctly rejects it |

The original CI setup also explicitly installs `jsonschema==4.25.1` and
`jsonschema-specifications==2025.9.1` in its Python environment before those two
children fail to import it. This independently refutes the absent-dependency-line
explanation: provisioner and consumer did not use the same interpreter.

The original CI setup log installs Node from
`/opt/hostedtoolcache/node/22.23.2/x64`; production `_trusted_node()` selects the
first valid Node 22 from `/opt/homebrew/bin/node`, `/usr/local/bin/node`,
`/usr/bin/node`. The stable builder records `realpathSync(process.execPath)`, its
hash and `process.version`, while the direct test admission witness recomputes
`_trusted_node()`. Those can differ. The production persistence chain already
runs its producer under `_trusted_node()`; weakening its equality would turn an
apparatus fixture repair into an authority leak.

The precise third partition is fixture execution provenance. It is neither a
jsonschema import failure nor evidence that stable admission is incorrect.

### B-F04: the pre-push decision already exists in the branch

The current `lefthook.yml` has only `typecheck` in `pre-push.commands`; its comment
records the deliberate no-unit-suite decision and the worker-contention reason.
There is no suite command to remove. The legitimate closure choice in the debt
row has already been made. Do not reintroduce the expensive suite merely to make
a new patch visible, and do not convert timeout inflation into a repair.

The missing piece is a behavioral witness for this choice: execute the installed
pre-push hook directly in the existing isolated Git/Lefthook harness; the actual
typecheck command must run and its nonzero result must fail the hook; a unit
command configured to fail must not be invoked. This is
proof of the declared narrowed local gate, not a claim that typecheck proves unit
behavior. Execute from both repository and dashboard CWDs.

### B-F05: CI reachability is already repaired, completion remains evidence

`ci.yml::frontend-unit-coverage` has no `needs` on frontend lint, formatting or
architecture, provisions Python runtime and Chromium, and calls `test:coverage`.
The aggregate explicitly rejects coverage results other than `success`. Therefore
the old statement that lint must become green before unit evidence can exist no
longer describes this workflow. The original run proves the suite was reached.
A current local run cannot certify a future remote job. The row's external CI
completion conjunct remains unestablished until an ordinary authorized CI run
finishes and the result is read; this workstream does not push.

## Proposed mechanism and file budget

Mechanism paths (not a cap):

1. Extend `src/test/evidence/persistenceProcessResult.ts` with one checkout-bound
   Python locator/launcher, derived from its module location. No ambient Python
   override or fallback. Preserve the venv locator, arguments, fixed CWD, timeout
   and environment options at callers. Do not globally introduce `-I`: the
   workflow `-c` script intentionally imports repository `architecture`, whereas
   authority-sensitive validators already opt into isolation explicitly.
2. Wire all three bare-Python sites from B-F01. Route the capture CLI result
   through the existing decoder; retain its requirement that bridge status is
   zero before accepting persistence results. Emit/consume the workflow test
   witness completion envelope; named UNRUN covers missing launch, timeout and
   unreadable child result, while typed refusals retain their status and body.
3. In `atlasSurfaceReadinessReconciliation.test.ts`, prepare the stable negative
   fixture using the real `_trusted_node()` owner and execute the existing
   `buildAtlasStableReadinessNegativeControl` under that executable via the same
   Vite SSR loader used by the reconciler launcher. The Python admission witness
   continues to call `_trusted_node()` independently. Do not mutate the produced
   executable fields to make a mismatch pass.
4. Preserve the fixed launch environments in `atlasHealthMetrics.ts` and
   `atlasSurfaceReadinessReconciliation.ts`, but name unavailable launch/validator
   output with the shared UNRUN diagnostic. Retain readiness error codes and
   all health/readiness admission checks.
5. Add the pre-push behavioral witness in
   `tests/repo_quality/tools/test_repo_hooks.py`, composing its `_seed`, `_prepare`,
   `_provision_binary` and real Lefthook fixtures. Call the installed hook or `lefthook run pre-push` directly; never invoke
   `git push`, including against a fixture-local remote.

Mandatory companions outside the mechanism count: this spec; lane journal;
regression tests in `persistenceProcessResult.test.ts` and the exact consumer
files; any fixture constant pinned to changed implementation bytes; root-owned
cross-lane plan and read-back receipts. Root owns any shared pyproject, lock,
package.json, lefthook or workflow write. None is currently needed in the
proposed dashboard mechanism. If a bootstrap import check finds an actually
missing dependency, hand the exact import/caller/profile to the dependency lane;
do not add it independently.

## Red-first implementation sequence and exact gates

Begin after the root commits and reads back the Stage 1 package. The user has
already authorized the implementation; this is a sequencing boundary.

1. Preserve the complete current provisioned baseline and actual process exit.
   Split failed file setup/collection, failed assertion, browser launch, coverage
   generation, and ratchet outcomes. Do not compress them into one red count.
2. Add a behavioral PATH-poisoned child witness in the existing process tests:
   put a `python3` executable that writes a unique refusal marker and exits 73
   first on PATH; run the actual capture/validator consumer and verify the
   repository interpreter executes instead. Missing `.venv/bin/python` must
   produce a named UNRUN launch failure and must not consult the poison fallback.
   A real missing-dependency child must also emit UNRUN, while a completed
   deliberate JSON refusal must retain its ordinary semantic result.
   Use fixture copies under harness scratch, not mutations to the shared venv.
3. Run the affected automated-capture Core assertion and workflow source-flip
   assertion with a PATH that resolves Python to the non-project interpreter.
   Before repair retain their exact cause; after repair both must reach their
   unchanged semantic assertions. Test the production capture CLI sibling too,
   with an actual raw runner fixture, CAS root and content-bound result.
4. Add the alternate-Node station falsifier: copy the Node executable into harness
   scratch, preserving its bytes/version but changing its realpath, and run the
   stable-readiness test through that executable. Before repair the mismatch
   should reproduce; after canonical fixture construction it must pass. Mutate
   the resulting claimed executable path, hash and version separately and require
   `canonical check executable provenance mismatch` from real admission.
5. Add pre-push fixture test with real dispatcher/typecheck command resolution and
   no remote or push operation. Make an unselected unit command exit 73: the hook
   succeeds if typecheck passes, fails if typecheck fails, and never runs that
   unit command.
6. Implement only the smallest repairs described above. Run exact focused files,
   consumer assertions, typecheck and lint on touched files. Review the frozen
   source before the expensive complete-suite wave.

All commands below are separate tool invocations, with full stdout/stderr redirected
to a distinct file under `docs/superpowers/journals/apparatus/dashboard/raw/` and
exit status retained from the exec tool. They are commands, not claims of passing.
From the dashboard CWD:

```sh
corepack pnpm exec vitest run src/test/evidence/persistenceProcessResult.test.ts scripts/preserve-vitest-error-cause.test.ts --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000
```

```sh
corepack pnpm exec vitest run src/test/evidence/atlasAutomatedEvidenceCapture.test.ts --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000 -t 'executes Core put, resolve, lineage, and integrity checks and fails on corruption'
```

```sh
corepack pnpm exec vitest run src/shared/lib/domain/workflow.test.ts --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000 -t 'source flips reject every C22d return vocabulary revival'
```

```sh
corepack pnpm exec vitest run src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000 -t 'gates the zero-instance stable arm identically to implemented'
```

```sh
corepack pnpm exec vitest run src/test/evidence/atlasHealthMetrics.test.ts src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts src/test/evidence/atlasAutomatedEvidenceCapture.test.ts src/shared/lib/domain/workflow.test.ts --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000
```

```sh
corepack pnpm run typecheck
```

From the product CWD:

```sh
.venv/bin/python -m pytest tests/repo_quality/tools/test_repo_hooks.py -q
```

Final complete suite (explicitly permitted exception to the file-only rule):

```sh
corepack pnpm run test:coverage
```

That package command includes the coverage ratchet after successful Vitest. A
separate `vitest run --coverage ...` baseline, such as this research baseline, is
only the suite/coverage half and does not prove the ratchet ran.

## Fresh-station acceptance, falsifiers, and closure limits

After mechanism/tests are committed, root creates a **new detached worktree** at
the frozen candidate. Do not reattach or move the implementation checkout HEAD.
Install locked dependencies there with `corepack pnpm install --frozen-lockfile`
and the declared runtime Python profile; do not symlink a warm node_modules or
venv. Browser downloads may be installed normally, but `_cache`, `_build` and
coverage outputs must begin absent. No result cache or prior generated evidence
may supply the verdict. Serialize browser, shared governed scratch and complete
suite execution with other workstreams.

Run the **same literal invocation** twice from each of two external CWDs:
repository root and dashboard root. Use an absolute `corepack pnpm --dir
<fresh-product>/apps/runtime-dashboard ...` invocation so the owned test command
normalizes its CWD identically; changing test root by passing a config file from
another directory is a different invocation and collection contract. Required
focused command is the four exact evidence/consumer files above with the same
worker/timeouts flags. Compare complete test identity/status sets, not elapsed
time or only exit codes. Keep every full log and actual exit. The cold first run
must independently finish; the second run is a stability check, not a substitute.

Required falsifiers and acceptance signals:

| Falsifier | Required observation |
| --- | --- |
| Ambient Python can import packages but binds another checkout | Fixed consumer imports Core from the selected checkout; a zero exit alone is insufficient |
| PATH `python3` is a marker-emitting wrong interpreter | All fixed consumers still run project Python; poison marker absent |
| Repository interpreter absent | Named UNRUN failure identifies missing interpreter; no fallback or skipped-success claim |
| Child exits nonzero with empty stdout | Named UNRUN preserves cause and stderr, no misleading empty JSON result |
| Child exits nonzero with malformed stdout | Named UNRUN preserves nonzero cause before/alongside JSON diagnostic |
| Child returns deliberate nonzero JSON refusal | Refusal status and typed body preserved; cannot become success |
| Child is killed/times out | Named UNRUN preserves cause/signal; outer watchdog does not mask inner one |
| Test executes under an alternate Node realpath | Canonically built stable fixture remains admissible as unavailable |
| Claim executable path/hash/version is tampered | Existing Python admission rejects provenance mismatch |
| Stable reason or attestation scope is forged | Existing unchanged negative semantic tests still reject it |
| Pre-push unit command would fail, typecheck passes | Actual installed fixture hook succeeds and unit command was never dispatched |
| Pre-push typecheck fails | Actual installed fixture hook fails from both CWDs |
| CI coverage result skipped/missing | Existing aggregate rejects it; no new green interpretation |
| Warm outputs removed | Cold station produces its own complete verdict |
| Marker-only repair removal | Restore bare Python while retaining helper names/comments; PATH falsifier turns red |

Do not claim remote CI success without a completed remote result on the repaired
revision. Do not call the old fifty failures reproduced unless the complete new
run identifies the same cases. Newly discovered product failures are classified
and handed back with complete evidence; this apparatus task does not repair
product semantics merely to turn the full suite green. A discovered apparatus
failure remains in scope and is bucketed under P40 before the next change.

## Stage 1 receipt status

The existing `tests/repo_quality/tools/test_repo_hooks.py` command completed with
exit 0 (eight cases; complete `raw/baseline-hook-tests.log`). It verifies current
hook installation/commit behavior, not the new pre-push decision witness. The
provisioned full-suite baseline has now completed with actual tool exit **1**.
Complete log: `raw/baseline-provisioned-coverage.log`, SHA-256
`913987bdfb7b75fa675d36adbb52a9d3d3545bb12df7a46a02246526ea185946`.
Exact command, from `apps/runtime-dashboard`:

```sh
corepack pnpm exec vitest run --coverage --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000
```

Vitest reports **1,291.51 seconds**. Complete denominator arithmetic is
**405 files = 1 failed + 403 passed + 1 skipped** and
**1,792 assertions = 1 failed + 1,789 passed + 2 skipped**. This run reached the
suite; the original Python/Node error signatures are absent. That is a
station-specific result, not proof that the bare-interpreter mechanism is fixed.
The package coverage-ratchet command was not invoked by this direct Vitest gate.
The environment had the root-provisioned lint/test/runtime/ml extras and ambient
Homebrew Python/Node, not a poisoned-PATH or canonical CI-profile acceptance
station. No mechanism/source/test/config changes occurred during this run.

The exact failed identity is
`src/features/runs/components/ConfidenceLedgerRiskSpend.a11y.test.tsx >
ConfidenceLedgerRiskSpend accessibility > has no violations in the ordered
reviewer surface or full-envelope dialog`. The retained error is **Test timed
out in 30000ms** (the test's explicit deadline); its recorded test duration is
37,813ms. There is no emitted axe-violation assertion failure and no emitted
missing-Python error. The file renders the OpenAPI example, awaits axe, opens the
full-envelope dialog and awaits axe again; it declares no local fake-timer setup.
Which operation exhausted the deadline is **not_established**. Do not label it a
product accessibility defect, fake-timer failure, or inherited red from that
stack alone.

Bucket: **NEW execution-availability/deadline class**, distinct from the measured
Python locator and Node fixture provenance classes. Named follow-up owner:
`team-design` dashboard accessibility harness, coordinated here before closeout.
First Stage 2 follow-up is the exact bounded replay below; inspect the completed
output and instrument the actual awaited boundary in harness scratch if it
reproduces. Preserve the test population and its accessibility assertions; do
not raise the deadline as a repair. If it is apparatus/scaffolding, repair that
root cause in scope; if a product problem is actually established, hand it back
with the decisive output and a declared limit. P41 still requires an exact
slice-base replay and complete changed-input disjointness before calling it
inherited.

```sh
corepack pnpm exec vitest run src/features/runs/components/ConfidenceLedgerRiskSpend.a11y.test.tsx --coverage --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000
```

The failure/repair register was reopened before this Stage 1 closeout. No new
pattern is needed: P29/P35/P37/P38/P40/P41 already cover the distinction between a
completed suite, an unavailable individual measurement, station provenance, and
unestablished root cause.

## Stage 2 addendum: native accessibility measurement

The exact single-file coverage replay reproduced the same timeout: exit 1,
47.31s Vitest duration, 37.172s test, `raw/a11y-targeted-baseline.log`. A scratch
copy instrumenting the actual awaited operations measured two JSDOM axe runs at
14.595s and 11.877s over the complete body populations of 2,444 and 2,711 elements;
that run passed in 27.26s against the same 30s test deadline
(`raw/a11y-timing-probe-bound-deps.log`, exit 0, 33.65s Vitest). This is a
measurement station operating near its watchdog, not an established product
accessibility defect or fake-timer problem.

Compose the existing `vitest.confidence-ledger-browser.config.ts` Browser Mode
owner already reached by the full suite and provisioned with Chromium in CI. A
scratch test under that exact owner configuration used the same component, same
OpenAPI example, same dialog interaction, and the same two unfiltered zero-axe-
violation assertions. Browser-native `axe-core` is already declared in the
dashboard package; use it directly because the JSDOM `vitest-axe` wrapper imports
Node `createRequire` and cannot execute in Browser Mode. Do not add a dependency.

Positive browser receipt: `raw/a11y-browser-native-axe-probe.log`, exit 0, test
3.02s, wall 5.31s. Negative control: remove `aria-labelledby` and `aria-label`
from the actual rendered dialog, retaining all measurement/assertion code; the
second assertion fails with `aria-dialog-name`, exit 1, test 3.59s, wall 6.37s
(`raw/a11y-browser-dialog-name-negative.log`). Initial scratch package-resolution
and Node-wrapper-import failures remain explicit probe setup non-receipts in
`raw/a11y-timing-probe.log` and `raw/a11y-browser-probe.log`.

After this addendum is committed and read back by root, rename
`ConfidenceLedgerRiskSpend.a11y.test.tsx` to
`ConfidenceLedgerRiskSpend.a11y.browser.test.tsx` in the same component directory.
Import the identical OpenAPI document statically, following the existing browser
twin test; import `axe-core` and call `axe.run(document.body)`; use browser-safe
visibility matchers. Add that exact filename to the existing browser project's
include array. Keep the **30,000ms** explicit deadline and both assertions; no
rule exclusion, reduced DOM, test deletion or product component change. The
existing unit exclusion for `.browser.test` routes it once into Browser Mode,
while `test:coverage` still includes it through the same projects array. Existing
Chromium setup already covers this additional browser test. All lanes retain
the same suite watcher and coverage ratchet; no package/lock/workflow change.
The native browser project's output directory must stay under ignored `_build`
or this lane's ignored raw scratch, including failure screenshots/attachments.
