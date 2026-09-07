# Commit, not station — instruments lane

Binding scope: the four rows in the 2026-09-07 task prompt. Base `a8d323a2f`,
branch `codex/commit-not-station`, worktree `.worktrees/instruments2`. Ordinary
local git only; no push. Neither debt register nor generated ledger is an input;
`check_debt_ledger.py` is excluded in every mode.

## Plan and pattern pass

The property is: a check's verdict depends on the commit, and the check reaches
the behavior it names. Reuse existing generators, composite setup actions and
runtime fixtures. Relevant patterns: P29/P32 (behavior, not markers), P33
(adversarial removal), P35 (complete artifact/finding sets), P38 (a version header
is a proxy for schema compatibility), P41 (measure baseline reds). No new product
capability or DS9 engineering allocation is claimed. Missing verification is
`verification_missing` until the corresponding executable evidence exists.

1. Row 1: compare freshly generated complete ABI model payloads in real git
   worktrees using Python 3.14.0 and 3.14.3, then decide manifest equality policy.
   Exercise both comparison paths and preserve detection of actual payload drift.
2. Row 2: trace every suite invocation and provider; verify the existing error
   propagation with a failing child, then provision at the shared setup boundary.
   Read production before classifying any residual assertion failure.
3. Row 3: compare wheels-only dependency routes with actual vector-search
   behavior. Preserve HNSW availability; compiler installation is not closure.
4. Row 4: reproduce the crash fixture and reservation pair; repair scaffolding
   while preserving assertions unless production proves blocked is the subject.

Parallel ownership: coordinator owns generator, manifest policy, pyproject/lock
and this journal; separate agents own dashboard setup investigation, vector
dependency investigation, and DS9 tests/services. Shared `.venv`, lockfile,
commits and generated schema outputs are serialized. Dashboard JavaScript install
has one owner. Only targeted checks; no directory-wide Python suite.

## Setup receipts

- Setup verified branch attachment and created the requested branch at the exact
  base. A second, detached worktree at the same base is
  `.worktrees/instruments2-python3143`; no commits are made there.
- Python 3.14.0 is Homebrew macOS arm64; Python 3.14.3 was installed using
  `uv python install 3.14.3` (exit 0).
- `uv sync --offline --extra ml --extra test --extra runtime --extra lint --group ci`
  exited 1 because the locked `jaxlib==0.8.2` wheel was not cached. The online,
  frozen equivalent exited 0 and provisioned this local measurement station.
  Its source build of HNSW is explicitly not Row 3 wheels-only evidence.

## Row 1 — schema-manifest-compares-the-generating-interpreter-version

Root **(d) INSTRUMENT**. On base `a8d323a2f`, the complete verdict from
`.venv/bin/python -m tools.quality.diagnostics.gen_schema --check` on macOS arm64,
Homebrew CPython **3.14.0**, Pydantic **2.12.5**, was exit **0**:

```text
ABI schema snapshot check passed (101 models, scan_mode=full)
```

The same command from the detached base worktree on macOS arm64, uv-managed
CPython **3.14.3**, Pydantic **2.12.5**, was exit **1**:

```text
ABI schema snapshot check failed:
- snapshot out of date: /Users/deniskopylov/polisyos/.worktrees/instruments2-python3143/policy-engine/schemas/snapshots/fabric/_manifest.json
- snapshot out of date: /Users/deniskopylov/polisyos/.worktrees/instruments2-python3143/policy-engine/schemas/snapshots/ir/_manifest.json
```

Neither completed run emitted a traceback. The complete finding identity sets are
respectively `{}` and `{fabric/_manifest.json, ir/_manifest.json}`, relative to
`schemas/snapshots/`; neither is inferred from a total. Both stations were
provisioned from frozen `uv.lock`. PATH uv used for these syncs was 0.10.6;
the executors of the schema gates were the two `.venv/bin/python` binaries.
No source dependency was upgraded between these measurements.

Both stations also ran the real generator with fresh output/cache directories:

```text
.venv/bin/python -m tools.quality.diagnostics.gen_schema --output-dir .scratch/commit-not-station-row1/generated3140 --cache-dir .scratch/commit-not-station-row1/cache3140
.venv/bin/python -m tools.quality.diagnostics.gen_schema --output-dir .scratch/commit-not-station-row1/generated3143 --cache-dir .scratch/commit-not-station-row1/cache3143
```

Each exited **0**, with complete output:

```text
Generated ABI schema snapshots for 101 models (103 file updates, scan_mode=full)
```

The denominator is **every generated non-manifest `.json` file** under each fresh
output tree, independently reconciled to **every model entry in both generated
manifests**: **101/101 model paths at each station**, plus **2/2 manifests**.
The comparison parses every payload, recomputes its full canonical hash, verifies
that hash against its manifest entry, and compares both canonical and file-byte
hashes across stations. Complete differing model-path set: **`[]`**.
Both manifests differ only in **`generated_at` and `python_version`**.
The complete path/hash denominator is retained in the local measurement artifact
`policy-engine/.scratch/commit-not-station-row1/generated-payload-comparison.json`.
An independent comparison against all freshly recomputed payload cache entries
from the 3.14.3 `--check` run also agrees; it was the evidence available before
choosing the equality policy. The subsequent written-output comparison confirms it.

Decision: Python/Pydantic version headers remain provenance of the writer, just
like generation time. A common top-level manifest-content projection excludes
these three fields at **both** equality sites. The generator still recomputes and
compares the complete model payloads, full/semantic model hashes, compatibility,
generator version and all other manifest content. A version-induced schema
difference therefore stays red; equality does not imply every future supported
interpreter/Pydantic combination must produce identical schemas. Only 3.14.0 and
3.14.3 with Pydantic 2.12.5 were experimentally compared here.

The new regression cases change each provenance header separately, check a green
verdict and byte-for-byte unchanged manifest on regeneration, then change a real
transitive model field and require both the schema and manifest to be reported.
Both cases failed on the base before the repair. Post-repair targeted gate:
`python -m pytest -q tests/repo_quality/tools/test_schema_station_independence.py
tests/repo_quality/tools/test_diagnostics_phase3.py
tests/repo_quality/tools/test_phase5_tooling.py -k schema` exited **0**.
Mutation and same-commit final station receipts are recorded at closeout below.

## Row 2 — evidence-tests-launch-python-that-the-station-does-not-provision

Disposition: **repaired-with-a-limit**. The station is provisioned through the existing declared dependency path, and the masking repair is verified. A newly measured dashboard-owned scaffolding boundary still stops the unmodified suites; the extended-budget diagnostic below is not a delivered source repair.

Root class: **(c) BROKEN SCAFFOLDING**, plus verification of the already repaired **(a) PRODUCT** masking defect. The station initially had no worktree-local Python environment. The declared `test` extra already supplies `jsonschema[format-nongpl]>=4.25.1` (`pyproject.toml:160-169`), and the documented default/runtime bootstrap profile includes `lint`, `test`, `runtime` (`tools/devx/workspace/_common.py:57-63`). The root lane provisioned the local `.venv`; the Node workspace was installed with `corepack pnpm install --frozen-lockfile`, exit 0, pnpm 10.33.2, 43.4 seconds. The measured interpreter is Python 3.14.0; its jsonschema is 4.25.1. `python -I` successfully imports the real `Draft202012Validator`, `FormatChecker`, and `polisyos.core.artifacts.ArtifactStore`.

CI reachability: the complete census of `.github/workflows` over every `.yml` and `.yaml` file found 12 readable workflow files and 12 calls to `setup-runtime-dashboard` (full identities in `.scratch/commit-not-station-row2/workflow-provisioning.json`). The direct coverage invocation that collects these suites is `.github/workflows/ci.yml` / `frontend-unit-coverage` / `corepack pnpm run test:coverage`. It already runs `setup-policy-engine-python` with `profile: runtime` first. The action installs supported Python and pinned uv, then runs the dependency-free bootstrap package with `python3 -m tools.devx.workspace.bootstrap`; the runtime profile syncs the test extra. The only standalone dashboard-action callers without previous Python setup are `ci.yml/frontend-components` (the separate Storybook config) and `frontend-nightly.yml/frontend-dependency-audit` (dependency audit). Neither invokes the two evidence suites. This is source-backed configuration verification, not a claim that a remote CI job was executed. No necessary workflow edit was found.

The local `pnpm test` / `test:components` / `test:coverage` entrypoints and pre-push still assume the documented bootstrap was run; they do not provision Python themselves. Making bare Node-only invocations automatically provision Python would require the dashboard-owned package/config boundary. No redundant action or dependency declaration was added to hide that distinction.

Masking verification: `corepack pnpm exec vitest run --project unit src/test/evidence/persistenceProcessResult.test.ts --maxWorkers=1` exited 0: all 5 cases in that one file passed (empty failed stdout, malformed failed stdout, ENOENT launch error, a deliberate nonzero JSON refusal, and completed JSON). The real unchanged `parsePersistenceProcessResult` was also invoked with the real `validate_atlas_health_sources.py` child under `.venv/bin/python -I -S`: the removal probe exited 1 and surfaced `Atlas persistence child failed (exit=1, signal=null)` followed by `validate_atlas_health_sources.py:17` and `ModuleNotFoundError: No module named 'jsonschema'`. Removing only `-S` exited 0 and produced the canonical `polisyos.atlas.health-source-projection` v1.0.0. The validator source bytes were identical in the pair (sha256 `64353d796f9de3d2d3ebb44a3802f77c340e99d1755898f035a42292c3e63105`). Thus the dependency-removal check goes red while file/field/marker bytes stay intact; the actual cause reaches the outer process output.

Original two-suite gate, unchanged sources:

```text
corepack pnpm exec vitest run --project unit src/test/evidence/atlasHealthMetrics.test.ts src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000 --reporter=json --outputFile=../../.scratch/commit-not-station-row2/evidence-suites.json
```

Exit 1. Its complete two-file JSON report has 28 collected health cases, 25 passed and 3 failed. Readiness did not finish collection: its file-level child failed, so its case set is **ambiguous**, never zero. Every failure observation names the actual 60,000 ms child cutoff: `exit=null`, `signal=SIGTERM`, `ETIMEDOUT` at the `.venv/bin/python` process. There is no missing-jsonschema or ENOENT failure in this run. The exact failed health identities are:

- `Atlas health metrics persists a content-bound descriptive snapshot while recording its missing consumer`
- `Atlas health metrics ignores a caller PATH node that emits a schema-valid forged report`
- `Atlas health metrics does not inherit caller NODE_OPTIONS into the fixed producer`

The additional file-level failure is `atlasSurfaceReadinessReconciliation.test.ts` during its initial persistence fixture construction, with the same SIGTERM/ETIMEDOUT diagnostic. These are **(c) BROKEN SCAFFOLDING**: the unchanged helpers at health test line 129 and readiness test line 79 abort before their intended assertions. They are not stale assertions. The historical three-test lead was already changed at base by `a4bdb1369`; the current tests assert successful content-bound storage and retain PATH/NODE_OPTIONS isolation. This lane read both the production producer/admission/CAS path and that earlier diff before classifying; it changed no assertion.

Deciding evidence separating scaffolding from product/staleness: the exact real health operation `persist_atlas_health_metrics` completed with exit 0 under an explicit 180-second diagnostic budget in **63.654 seconds**, and readiness `persist_atlas_surface_readiness_claims` completed with exit 0 in **127.341 seconds**. Their report/snapshot and report/projection CAS blobs were independently rehashed and matched the emitted references (all four blobs in the two operation outputs). Health emitted `ok=true` and both verification reports were `ok=true`. The complete readiness projection enumerated `route-redirect-{launch,sources,data,lex,health}:readiness_state:implemented`; all five had observation `observed`, reason null, and canonical assertion status `passed`. These observed durations exceed the current test helper budget. No unsupported claim that CPU contention caused the durations is made.

Direct-operation receipts and raw artifacts are in `.scratch/commit-not-station-row2/{health,readiness}-extended-budget.{receipt.json,stdout.json,stderr.log}`. The explicit diagnostic budget was 180,000 ms; the operations were not unbounded. The ordinary 60-second gate remains red and is the removal counterfactual for the budget experiment.

Extended-budget unchanged-assertion diagnostic completed, exit 1. It collected both requested files: health 28 cases (25 passed, 3 failed) and readiness 33 cases (32 passed, 1 failed), a complete current denominator of 61 cases across these two files. The historical 77-case lead is not used as this run's denominator. The original run's readiness collection was ambiguous, so the comparison reports newly observed identities rather than treating a larger count as a repaired finding. Complete identity sets and file-level errors are in `.scratch/commit-not-station-row2/identity-comparison.json`.

The four diagnostic reds are **(d) INSTRUMENT**, distinct observations from the original child-cutoff **(c)** failures. They name the same three health identities listed above, plus `Atlas surface-readiness per-claim reconciliation ignores inherited process-selection controls on the closed path`. Health durations were 23.271, 28.459, and 24.240 seconds, above the selected 20-second outer budget. That selector is the committed CI coverage command, not an invented harness limit: `apps/runtime-dashboard/package.json:23` has `test:coverage` with `--maxWorkers=1 --testTimeout=20000 --hookTimeout=20000`; `vitest.config.ts:43` has an even shorter default of 15,000 ms. The readiness case took 85.646 seconds against its explicit committed 60,000 ms timeout at test line 776. No assertion was changed, and no assertion mismatch was reported.

The JSON reporter prints `Error: STACK_TRACE_ERROR` for these timeout failures. This was classified by reading the actual locked Vitest 4.1.5 runner: `withAwaitAsyncAssertions` (chunk-artifact.js:1901) waits for the test function and its async assertions; `withTimeout` (2261-2317) sends a rejected function through its rejection path, but after a fulfilled function it also checks elapsed time in `resolve` and rejects if elapsed >= timeout. `makeTimeoutError` (2404-2408) creates the real timeout message but replaces the stack in the wrong direction, leaving the placeholder in a stack-only JSON failure message. Thus these observations must not be reported as product assertion failures or as green tests: the completed computation is being rejected by the enclosing elapsed-time instrument. The containing test budgets must be addressed alongside the child budget. Under P40 this is the same deadline class one level deeper; the lane records a bounded residual rather than attempting another local repair ladder.

The diagnostic command was the original two-suite command plus `NODE_OPTIONS=--import=/Users/deniskopylov/polisyos/.worktrees/instruments2/.scratch/commit-not-station-row2/persistence-budget-preload.mjs`, with output redirected by Vitest itself to `evidence-suites-extended-budget.json`. Scratch-only `persistence-budget-preload.mjs` intercepts only `spawnSync` for this worktree's exact `.venv/bin/python` + exact `persist_atlas_evidence.py` path when `options.timeout === 60000`, and substitutes 180000. Every other option, command, and test assertion stays unchanged. Matched invocations are recorded in `budget-override.jsonl`. Dashboard, action, and workflow files remain byte-identical (`git diff --exit-code -- policy-engine/apps/runtime-dashboard .github/actions .github/workflows`, exit 0).

Proposed residual row: `atlas-evidence-tests-abort-completed-persistence-at-60s`, proposed owner `team-devx` with `team-design`. This is the same scaffolding class one level deeper, not a stale-expectation finding. The source repair belongs to the prohibited dashboard boundary: align the entire persistence-fixture budget: change `timeout: 60_000` in `invokePersistence` in both named evidence test files to an explicit shared child budget consistent with measured complete runs (180,000 ms was the diagnostic candidate); assign the three health persistence cases an explicit containing timeout that exceeds the child budget plus post-child CAS checks; and replace the readiness process-selection test's explicit 60,000 ms containing timeout with that containing budget. Preserve every assertion and the failure parser, then rerun both suites with serialized heavy work. A 240,000 ms containing budget is a concrete proposed bound above the 180,000 ms child budget, not yet a verified patch. The committed CI 20,000 ms/default 15,000 ms limits must not silently override those case-specific fixture budgets. A future semantic budget should be attached to the completed operation being tested, with a separately identified liveness limit; it must not turn a station-speed cutoff into a claimed product rejection. This lane does not change those files.

Pattern pass: P29/P38 (actual dependency and completed behavior, not presence markers or timeout-as-product), P33 (empty/malformed/launch failure variants), P35 (complete workflow and test-result identity sets), P40 (same scaffolding class at the next layer). No ownership appointment or new capability claim is made. The row fits the lane's instrument sentence; broad persistence capability construction is out of this task.


Incidental proposed row: `vitest-4-1-5-json-timeout-stack-hides-cause`, proposed owner `team-devx`. The pinned runner's `makeTimeoutError` sets `error.stack = stackTraceError.stack.replace(error.message, stackTraceError.message)`; the old timeout text is absent from the captured placeholder stack, so JSON reporters consuming only `.stack` emit `STACK_TRACE_ERROR` instead of the timeout cause. Consider a supported Vitest version/patch or a reporter that preserves `.message` as well as `.stack`. No node_modules, lockfile, or reporter edit is delivered for this incidental instrument finding.

No tracked source file was changed by the Row 2 worker. The local provisioning state, real operation receipts, negative dependency probe, ordinary red gate, and diagnostic reached-case set are the delivery evidence. The dashboard-owned deadline repair and a green replay of the ordinary suites remain outstanding; the diagnostic is explicitly not a delivered closure of that residual. The failure/repair register was re-opened before this handback.

Concrete handoff artifact: `.scratch/commit-not-station-row2/dashboard-timeout-handoff.patch` is an **unapplied proposal**, changing only the existing dashboard result helper and the two test files. It shares the 180-second child / 240-second containing budgets and preserves all assertion expressions. `git apply --check .scratch/commit-not-station-row2/dashboard-timeout-handoff.patch` exited 0; this proves patch applicability only. The containing-budget proposal has not been exercised and is not reported as a repair. A final `git diff --exit-code -- policy-engine/apps/runtime-dashboard .github/actions .github/workflows` exited 0.

### Exact unapplied dashboard handoff

Applicability checked only; the source files were not changed.

```diff
--- a/policy-engine/apps/runtime-dashboard/src/test/evidence/persistenceProcessResult.ts
+++ b/policy-engine/apps/runtime-dashboard/src/test/evidence/persistenceProcessResult.ts
@@ -1,4 +1,8 @@
 import type { SpawnSyncReturns } from "node:child_process";
+
+// Persistence fixtures run the complete producer, admission, and CAS checks.
+export const PERSISTENCE_CHILD_TIMEOUT_MS = 180_000;
+export const PERSISTENCE_TEST_TIMEOUT_MS = 240_000;

 export type PersistenceProcessResult = Readonly<{
   status: number | null;
--- a/policy-engine/apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.test.ts
+++ b/policy-engine/apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.test.ts
@@ -1,4 +1,8 @@
-import { parsePersistenceProcessResult } from "./persistenceProcessResult";
+import {
+  parsePersistenceProcessResult,
+  PERSISTENCE_CHILD_TIMEOUT_MS,
+  PERSISTENCE_TEST_TIMEOUT_MS,
+} from "./persistenceProcessResult";
 import { spawnSync } from "node:child_process";
 import { createHash } from "node:crypto";
 import {
@@ -126,7 +130,7 @@
         POLISYOS_CAS_ROOT: casRoot,
         ...environment,
       },
-      timeout: 60_000,
+      timeout: PERSISTENCE_CHILD_TIMEOUT_MS,
     },
   );
   return parsePersistenceProcessResult(result);
@@ -977,7 +981,7 @@
     } finally {
       rmSync(casRoot, { recursive: true, force: true });
     }
-  });
+  }, PERSISTENCE_TEST_TIMEOUT_MS);

   it("ignores a caller PATH node that emits a schema-valid forged report", () => {
     const casRoot = mkdtempSync(path.join(tmpdir(), "atlas-health-path-cas-"));
@@ -1019,7 +1023,7 @@
       rmSync(casRoot, { recursive: true, force: true });
       rmSync(fakeRoot, { recursive: true, force: true });
     }
-  });
+  }, PERSISTENCE_TEST_TIMEOUT_MS);

   it("does not inherit caller NODE_OPTIONS into the fixed producer", () => {
     const casRoot = mkdtempSync(
@@ -1047,7 +1051,7 @@
       rmSync(casRoot, { recursive: true, force: true });
       rmSync(injectionRoot, { recursive: true, force: true });
     }
-  });
+  }, PERSISTENCE_TEST_TIMEOUT_MS);

   it.each([
     "report",
--- a/policy-engine/apps/runtime-dashboard/src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts
+++ b/policy-engine/apps/runtime-dashboard/src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts
@@ -1,4 +1,8 @@
-import { parsePersistenceProcessResult } from "./persistenceProcessResult";
+import {
+  parsePersistenceProcessResult,
+  PERSISTENCE_CHILD_TIMEOUT_MS,
+  PERSISTENCE_TEST_TIMEOUT_MS,
+} from "./persistenceProcessResult";
 import { spawnSync } from "node:child_process";
 import { createHash } from "node:crypto";
 import { mkdtempSync, readFileSync, realpathSync, rmSync } from "node:fs";
@@ -76,7 +80,7 @@
         POLISYOS_CAS_BACKEND: "filesystem",
         POLISYOS_CAS_ROOT: casRoot,
       },
-      timeout: 60_000,
+      timeout: PERSISTENCE_CHILD_TIMEOUT_MS,
     },
   );
   const decoded = parsePersistenceProcessResult(result);
@@ -773,7 +777,7 @@
     } finally {
       rmSync(isolatedCas, { recursive: true, force: true });
     }
-  }, 60_000);
+  }, PERSISTENCE_TEST_TIMEOUT_MS);

   it("content-binds the exact per-row report bytes without a CI verdict", () => {
     expect(persisted.claim_report_ref.artifact_id).toBe(
```

## Row 3 — hnswlib-has-no-wheel-for-the-declared-interpreter

Disposition **blocked-and-why**, root **(d) INSTRUMENT**. No dependency changes.
The core wheels-only closure cannot be achieved by moving HNSW alone; proceeding
would change the default vector capability while leaving the requested gate red.

The existing Pillow branch was read: non-default `ci = ["pillow>=12"]` conflicts
with `table-extraction`; it was not modified. Core export with canonical uv
**0.9.21**, CPython **3.14.0**, macOS arm64, from the base dependency files:

```text
/Users/deniskopylov/.local/bin/uv export --frozen --no-dev --no-emit-project --no-hashes --output-file ../.scratch/commit-not-station-row3/core-before-pinned-uv.txt --quiet
```

Exit **0**. From the worktree root, the actual installation probe was:

```text
/Users/deniskopylov/.local/bin/uv --quiet pip install --python /opt/homebrew/bin/python3.14 --only-binary :all: --no-cache --target .scratch/commit-not-station-row3/core-before-pinned-env --requirements .scratch/commit-not-station-row3/core-before-pinned-uv.txt
```

Exit **1**, complete solver verdict (no traceback):

```text
× No solution found when resolving dependencies:
╰─▶ Because hnswlib==0.8.0 has no usable wheels and you require
    hnswlib==0.8.0, we can conclude that your requirements are
    unsatisfiable.

    hint: Wheels are required for `hnswlib` because building from source is
    disabled for all packages (i.e., with `--no-build`)
```

The same command using a scratch requirement copy omitting **only** HNSW
(`core-without-hnsw.txt`, target `core-without-hnsw-pinned-env`) exited **1**:

```text
× No solution found when resolving dependencies:
╰─▶ Because odfpy==1.4.1 has no usable wheels and you require odfpy==1.4.1,
    we can conclude that your requirements are unsatisfiable.

    hint: Wheels are required for `odfpy` because building from source is
    disabled for all packages (i.e., with `--no-build`)
```

P40 bucket: **the same dependency-artifact class one level deeper**. Instead of
further omissions, `census.py` walked the **116 exported requirement identities**,
evaluated markers (**114 selected per platform**), and enumerated every file in
every selected pinned PyPI release for CPython 3.14 macOS arm64 and Linux x86_64
tags. Both complete incompatible identity sets are exactly:

```text
hnswlib==0.8.0
odfpy==1.4.1
regex==2024.11.6
```

Both ambiguous sets are empty. Linux is a wheel-tag census, not a Linux execution
claim. Evidence: worktree-root
`.scratch/commit-not-station-row3/core-wheel-census.json`, with the enumerator and
both requirement exports beside it. `python -m census` exited **0**. Canonical uv
and PATH uv exports selected the same pinned dependencies.

| Route | Result |
| --- | --- |
| Official HNSW upgrade | Complete [PyPI HNSW](https://pypi.org/project/hnswlib/) artifact census: 11 files over 11 releases, all source distributions; latest 0.8.0. No compatible wheel route established. |
| Chroma HNSW substitution | Complete [PyPI Chroma HNSW](https://pypi.org/project/chroma-hnswlib/) census: 277 wheels among 291 files over 13 releases; none cp314/abi3. |
| Another index | No compatible macOS arm64/Linux x86_64 wheel source established in the bounded search; not a universal absence claim. |
| Explicit `vector-search` extra included by `research`/`all` | An available packaging route for HNSW, but core remains blocked by ODF and regex; not applied or claimed verified. |
| Compiler or dropping HNSW | Fails the requested closure; rejected. |

The [ODF release history](https://pypi.org/project/odfpy/) has 15 files, zero
wheels; latest 1.4.1. Regex has newer cp314 wheels, but a lock update alone cannot
resolve ODF. Selecting an alternative ODF distribution or moving additional
ingestion capability out of core is the remaining packaging decision.

Existing capability was demonstrated through production `VectorMemoryStore` and
real `FileSystemCAS`, using an already installed HNSW binary. From row 3 scratch,
`python -m vector_behavior` exited **0**: adds three cosine vectors, queries ordered
neighbors, overwrites a vector and its metadata without increasing item count,
persists to CAS and restores identical results (`north:0`, updated
`east:0.2928932309150696`, `south:2`). CAS artifact:
`sha256:820fa54f5d369bf1c0348def95f4de55431697d6c4a23ade31c8aa7fd72547ee`.
This is existing behavior evidence, **not** a fresh wheel install.

Removal witnesses retained the module/class/backend names:
`python -m vector_behavior --remove-search` exited **1**, `AssertionError: []`;
`--remove-backend` exited **1** at the production constructor with
`ImportError: hnswlib is required for VectorMemoryStore. Install it with: pip install hnswlib`.
The initial scratch report serializer could not encode `ArtifactID`; converting
that report value to `str` preceded the clean run and changed no product assertion.

Proposed incidental rows, not appointments:

- `core-odfpy-has-no-published-wheel`: proposed team-devx with the Fabric ingestion
  owner; preserve ODF ingestion while resolving packaging.
- `core-regex-lock-selects-pre-cp314-release`: proposed team-devx with the tokenizer
  owner; select a compatible release and verify tokenizer behavior.

## Row 4 — `ds9-human-decision-crash-test-fixture-blocked`

**Disposition: repaired-with-a-limit.** The requested hard-crash witness and reservation pair pass. The same fixture-date defect remains at external gateway-test rebuilds in `tests/unit/runtime/quality/test_agent_action_authority.py`, outside the allowed edit boundary. An ephemeral provisioning probe makes every one of those unchanged tests pass, including the operational persisted-record consumer. No engineering appointment is made; DS9 engineering allocation remains unchanged.

**Station and evidence denominator.** macOS 26.6.2 arm64, Python 3.14.0, Pydantic 2.12.5. Baseline used the original checkout interpreter read-only with this worktree's `PYTHONPATH=src`; final gates used the worktree `.venv`. Evidence is the named tests' fresh signed CAS artifacts and SQLite reservation/event stores. `source-census.json` enumerates every `*.manifest.json` in each of three complete crash-fixture CAS roots (41 manifests per root, no unreadable manifests), preserving the source identity and full refusal/predicate payloads. Results below come from every testcase node in the named complete JUnit XML; none is a crash-truncated count.

**Classification before repair.** Initial red is **(c) BROKEN SCAFFOLDING**: DS9 fixture `NOW` was August 24, but reused mandate-authority evidence defaulted to the helper's August 19 interval. The production current-mandate resolver correctly rejected expired evidence; baseline source had null contract and `current_mandate_authority_not_established` plus `admission_contract_mismatch`. The hard-crash test therefore failed `HumanDecisionUnavailableError: blocked` at `create_record`, before patched `commit`. Both reservation witnesses passed. The fixture now supplies explicit signed-evidence validity from DS9 `NOW - 1 hour` through `NOW + 2 hours`.

The fixture-only replay advanced to **(a) PRODUCT**, classified **NEW class under P40**, not a deeper instance of the temporal defect: the real producer now emitted a correctly bound source with all expected predicates and the canonical refusal tuple `(operation_out_of_envelope, human_decision_missing)`. The common DS9 packet join accepted only the legacy singleton. Producer code appends the first reason at the envelope comparison, attempts human resolution only after every other prerequisite holds, then appends `human_decision_missing` when no first record exists. Its final ordered deduplication fixes order and multiplicity. Requiring a prior record to create the first record is a bootstrap cycle.

**Changes.** The existing `_pa2_packet_join_issues` accepts precisely the legacy singleton or the canonical pair; all other packet, predicate, provenance and signature checks remain intact. The existing arbitrary-refusal test preserves its assertions and gains missing-only, unrelated-third, reversed-order and duplicate inputs. A new positive parameter witness admits review while asserting zero records and zero effects. All original 237 assert statements in the complete `test_human_decision_service.py` AST remain unchanged per function; the new witness adds four assertions. The crash-test body is unchanged. The only mechanism files changed are that test file and `src/polisyos/runtime/http/services/human_decisions.py`.

This second repair is a product compatibility correction needed to reach the named behavior, not a claim of new DS9 capability. Independent delta review found no concrete blocking issue before source freeze. Ruff and `git diff --check` exited 0.

**Acceptance and removal receipts.** `final-targeted.xml` contains 17 passed / 17 testcase nodes, exit 0, wall 226.13 seconds. The removal probe replaces `HumanDecisionWriteFence.commit` with a method that returns the still-reserved record, preserving the method, supplied signed-record ref and durable-event ref. The unchanged crash test reaches replacement reservation version 2, then fails `HumanDecisionPersistenceError` caused by `DS9-RESERVATION-RECOVERY-REQUIRED` at write-fence finalization. Exit 1, wall 203.40 seconds. This is a valid behavioral red; the earlier probe that stopped at `invalid_source` is retained separately and is not cited as removal evidence.

**Bounded residual and falsifier.** The complete five-test external importer run exits 1 (four failed, one passed), wall 213.83 seconds. The four failed identities listed below now reach gateway reconstruction, where its own default evidence is again expired at DS9 time. This is the **same temporal BROKEN SCAFFOLDING class one level deeper under P40**. It is not stale expectation: `row4_current_mandate_probe` changes only the external test helper's default signed-evidence interval, leaves every assertion and production path intact, and the identical five-test identity set passes, exit 0, wall 139.68 seconds. This probe exercises actual dispatch, changed-admission rejection, changed-permission rejection and changed-invocation rejection, thereby reaching the common packet join's persisted-record consumer. The crash test alone does not reach that second consumer.

Proposed incidental row: `ds9-pa2-gateway-rebuild-fixture-uses-expired-mandate-evidence`; proposed routing `team-runtime` with `team-devx` for fixture consistency, not an engineering appointment. Smallest fix: provide current fixture-clock evidence at the external `_prepare_gateway` calls or make that helper explicitly consume the scenario clock. The necessary fixture helper exists, but the required edits are outside this lane's allowed file set. No external test was edited. Historical provenance is `not_established`; these reds are not described as inherited because an exact slice-base replay and disjoint-input proof were not performed.

**Pattern closeout.** P08 preserves authority time roles; P29/P38 require reaching the actual transition; P31 repairs the shared packet join used by gate and persisted-record validation; P32 preserves content/provenance checks; P40 bounds the repeated external scaffold defect; P41 prevents an unproved inherited-red claim. No new capability or owner allocation is asserted.

**Tooling non-receipts.** A duplicate import-heavy pytest startup was interrupted with exit 130; a `--noconftest` / disabled-plugin experiment exited 4 on the configured pytest-benchmark option before collection. Neither is product evidence or a green test receipt. The final commands below use ordinary configured pytest. No GitHub plugin, push, stash, forbidden ledger, or debt-ledger checker was used by this agent.

### Complete verdict identity sets

`final-targeted` — denominator `final-targeted.xml`: all 17 testcase nodes.

| Test identity | Result |
| --- | --- |
| `tests.unit.runtime.http.test_human_decision_service::test_human_decision_hard_crash_reconciles_null_ref_signed_orphan_before_v2` | passed |
| `tests.unit.runtime.http.test_control_plane_store::test_human_decision_crash_reservation_requires_reconciliation_before_reuse` | passed |
| `tests.unit.runtime.http.test_control_plane_store::test_human_decision_reservation_preserves_microsecond_lease_boundary` | passed |
| `tests.unit.runtime.http.test_human_decision_service::test_available_gate_response_exposes_server_resolved_submission_binding` | passed |
| `tests.unit.runtime.http.test_human_decision_service::test_human_decision_wrong_role_is_blocked_with_reason` | passed |
| `tests.unit.runtime.http.test_human_decision_service::test_human_decision_expired_request_is_blocked_with_reason` | passed |
| `tests.unit.runtime.http.test_human_decision_service::test_human_decision_persists_custody_signature_not_actor_signature` | passed |
| `tests.unit.runtime.http.test_human_decision_service::test_human_decision_signed_orphan_is_preserved_as_historical` | passed |
| `tests.unit.runtime.http.test_human_decision_service::test_human_decision_pre_action_refusal_can_request_first_record[refusal_reasons0]` | passed |
| `tests.unit.runtime.http.test_human_decision_service::test_human_decision_pre_action_refusal_can_request_first_record[refusal_reasons1]` | passed |
| `tests.unit.runtime.http.test_human_decision_service::test_human_decision_rejects_arbitrary_source_refusal[refusal_reasons0]` | passed |
| `tests.unit.runtime.http.test_human_decision_service::test_human_decision_rejects_arbitrary_source_refusal[refusal_reasons1]` | passed |
| `tests.unit.runtime.http.test_human_decision_service::test_human_decision_rejects_arbitrary_source_refusal[refusal_reasons2]` | passed |
| `tests.unit.runtime.http.test_human_decision_service::test_human_decision_rejects_arbitrary_source_refusal[refusal_reasons3]` | passed |
| `tests.unit.runtime.http.test_human_decision_service::test_human_decision_rejects_arbitrary_source_refusal[refusal_reasons4]` | passed |
| `tests.unit.runtime.http.test_human_decision_service::test_human_decision_requires_exact_source_predicate_provenance` | passed |
| `tests.unit.runtime.http.test_human_decision_service::test_human_decision_binds_source_to_exact_contract_bytes` | passed |

`final-importers` — denominator `final-importers.xml`: all 5 testcase nodes.

| Test identity | Result |
| --- | --- |
| `tests.unit.runtime.quality.test_agent_action_authority::test_agent_gateway_pa2_arm_re_resolves_s7_without_production_packet` | failed |
| `tests.unit.runtime.quality.test_agent_action_authority::test_agent_gateway_rejects_changed_admission_under_same_request_ref` | failed |
| `tests.unit.runtime.quality.test_agent_action_authority::test_agent_gateway_rejects_changed_live_permission_snapshot_under_same_request_ref` | failed |
| `tests.unit.runtime.quality.test_agent_action_authority::test_currentness_projection_round_trip_cannot_feed_operational_consumer` | passed |
| `tests.unit.runtime.quality.test_agent_action_authority::test_human_approval_cannot_replay_after_invocation_content_changes` | failed |

`provisioned-importers` — denominator `provisioned-importers.xml`: all 5 testcase nodes.

| Test identity | Result |
| --- | --- |
| `tests.unit.runtime.quality.test_agent_action_authority::test_agent_gateway_pa2_arm_re_resolves_s7_without_production_packet` | passed |
| `tests.unit.runtime.quality.test_agent_action_authority::test_agent_gateway_rejects_changed_admission_under_same_request_ref` | passed |
| `tests.unit.runtime.quality.test_agent_action_authority::test_agent_gateway_rejects_changed_live_permission_snapshot_under_same_request_ref` | passed |
| `tests.unit.runtime.quality.test_agent_action_authority::test_currentness_projection_round_trip_cannot_feed_operational_consumer` | passed |
| `tests.unit.runtime.quality.test_agent_action_authority::test_human_approval_cannot_replay_after_invocation_content_changes` | passed |

### Exact final gate commands

All run from `/Users/deniskopylov/polisyos/.worktrees/instruments2/policy-engine` except the explicitly labeled repository-root diff check. Each gate is the sole command in its invocation; `/usr/bin/time` and redirection preserve the child exit status.

final-targeted:

```sh
/usr/bin/time -p env PYTHONPATH=src:tests .venv/bin/python -m pytest tests/unit/runtime/http/test_human_decision_service.py::test_human_decision_hard_crash_reconciles_null_ref_signed_orphan_before_v2 tests/unit/runtime/http/test_control_plane_store.py::test_human_decision_crash_reservation_requires_reconciliation_before_reuse tests/unit/runtime/http/test_control_plane_store.py::test_human_decision_reservation_preserves_microsecond_lease_boundary tests/unit/runtime/http/test_human_decision_service.py::test_available_gate_response_exposes_server_resolved_submission_binding tests/unit/runtime/http/test_human_decision_service.py::test_human_decision_wrong_role_is_blocked_with_reason tests/unit/runtime/http/test_human_decision_service.py::test_human_decision_expired_request_is_blocked_with_reason tests/unit/runtime/http/test_human_decision_service.py::test_human_decision_persists_custody_signature_not_actor_signature tests/unit/runtime/http/test_human_decision_service.py::test_human_decision_signed_orphan_is_preserved_as_historical tests/unit/runtime/http/test_human_decision_service.py::test_human_decision_pre_action_refusal_can_request_first_record tests/unit/runtime/http/test_human_decision_service.py::test_human_decision_rejects_arbitrary_source_refusal tests/unit/runtime/http/test_human_decision_service.py::test_human_decision_requires_exact_source_predicate_provenance tests/unit/runtime/http/test_human_decision_service.py::test_human_decision_binds_source_to_exact_contract_bytes -q --tb=short --junitxml=../.scratch/commit-not-station-row4/final-targeted.xml > ../.scratch/commit-not-station-row4/final-targeted.log 2>&1
```

removal-probe:

```sh
/usr/bin/time -p env PYTHONPATH=src:tests:../.scratch/commit-not-station-row4 .venv/bin/python -m pytest -p row4_probe tests/unit/runtime/http/test_human_decision_service.py::test_human_decision_hard_crash_reconciles_null_ref_signed_orphan_before_v2 -q --tb=short > ../.scratch/commit-not-station-row4/removal-probe.log 2>&1
```

final-importers:

```sh
/usr/bin/time -p env PYTHONPATH=src:tests .venv/bin/python -m pytest tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_pa2_arm_re_resolves_s7_without_production_packet tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_rejects_changed_admission_under_same_request_ref tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_rejects_changed_live_permission_snapshot_under_same_request_ref tests/unit/runtime/quality/test_agent_action_authority.py::test_currentness_projection_round_trip_cannot_feed_operational_consumer tests/unit/runtime/quality/test_agent_action_authority.py::test_human_approval_cannot_replay_after_invocation_content_changes -q --tb=short --junitxml=../.scratch/commit-not-station-row4/final-importers.xml > ../.scratch/commit-not-station-row4/final-importers.log 2>&1
```

provisioned-importers:

```sh
/usr/bin/time -p env PYTHONPATH=src:tests:../.scratch/commit-not-station-row4 .venv/bin/python -m pytest -p row4_current_mandate_probe tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_pa2_arm_re_resolves_s7_without_production_packet tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_rejects_changed_admission_under_same_request_ref tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_rejects_changed_live_permission_snapshot_under_same_request_ref tests/unit/runtime/quality/test_agent_action_authority.py::test_currentness_projection_round_trip_cannot_feed_operational_consumer tests/unit/runtime/quality/test_agent_action_authority.py::test_human_approval_cannot_replay_after_invocation_content_changes -q --tb=short --junitxml=../.scratch/commit-not-station-row4/provisioned-importers.xml > ../.scratch/commit-not-station-row4/provisioned-importers.log 2>&1
```

ruff:

```sh
.venv/bin/python -m ruff check tests/unit/runtime/http/test_human_decision_service.py src/polisyos/runtime/http/services/human_decisions.py
```

diff-check-cwd-repo-root:

```sh
git diff --check -- policy-engine/tests/unit/runtime/http/test_human_decision_service.py policy-engine/src/polisyos/runtime/http/services/human_decisions.py
```

## Final disposition and local delivery

| Row | Disposition | Remaining boundary |
| --- | --- | --- |
| 1 — schema manifest | **repaired** | Experimental matrix is Python 3.14.0 / 3.14.3, both Pydantic 2.12.5. Actual future schema differences remain reportable. |
| 2 — evidence test provisioning | **repaired-with-a-limit** | Local provision and existing CI setup verified; ordinary suites remain red on dashboard-owned deadlines. Exact proposal above is unapplied. |
| 3 — HNSW core wheel | **blocked-and-why** | Core wheel set also lacks compatible ODF and pinned regex wheels; no dependency/capability change made. |
| 4 — DS9 crash witness | **repaired-with-a-limit** | Named crash and reservation witnesses pass; external importing tests still need fixture-clock evidence edits outside the allowed paths. |

All four rows were investigated. The excluded DS15 execution-handshake and Foundry
method-consumer rows were not picked up. No assertion was reclassified as stale
or weakened in this lane. The second DS9 repair serves the lane's sentence by
removing a producer/consumer mismatch that prevented reaching the commit path;
it does not construct or allocate a new DS9 engineering capability.

### Same-commit Row 1 closeout

Both final stations checked **`fc17e4754d41f70168ff8ad571f48e2ce9a7952f`**:

| Station | Working directory | Python / Pydantic | Exit |
| --- | --- | --- | --- |
| A | `/Users/deniskopylov/polisyos/.worktrees/instruments2/policy-engine` | 3.14.0 / 2.12.5 | **0** |
| B | `/Users/deniskopylov/polisyos/.worktrees/instruments2-python3143-final/policy-engine` | 3.14.3 / 2.12.5 | **0** |

Station B is a fresh `git worktree add --detach` at that exact source commit,
with its own frozen-lock virtual environment. Its offline sync first returned 1
for an uncached JAX wheel; the online frozen sync returned 0. This is measurement
provisioning, not Row 3 wheels-only evidence. Station A's only outstanding tracked
edit during the final check was this journal, which is not a schema input.

Each station's sole gate command was:

```sh
.venv/bin/python -m tools.quality.diagnostics.gen_schema --check
```

Complete Station A verdict, exit **0**, no traceback:

```text
ABI schema snapshot check passed (101 models, scan_mode=full)
```

Complete Station B verdict, exit **0**, no traceback:

```text
ABI schema snapshot check passed (101 models, scan_mode=full)
```

Both complete failure identity sets are **`{}`**, across the generator's entire
selected model and reference-document check, not a filtered or cached success.
No committed snapshot header was regenerated to make either station pass.

The post-repair removal probe temporarily changed only the projection's excluded
key set back to `{generated_at}`, preserving all emitted header names and the
new comparison helper. The real two-case provenance regression gate exited **1**,
with both complete failing identities:

```text
tests/repo_quality/tools/test_schema_station_independence.py::test_generator_provenance_does_not_change_verdict_or_rewrite_manifest[python_version]
tests/repo_quality/tools/test_schema_station_independence.py::test_generator_provenance_does_not_change_verdict_or_rewrite_manifest[pydantic_version]
```

The probe restored the fixed source in `finally`, verified byte equality and SHA-256
`cdda1d2c721d13109971d87368b90ca0b370542651d86f583aa87fd352add60d`.
Replaying those exact cases after restoration exited **0**. The broader targeted
schema gate already passed before the mutation, including real payload/hash drift.

### Delivery checks and evidence retention

Local source commits:

- `f02b5f842` — schema equality policy, its behavioral regressions and initial journal.
- `fc17e4754` — DS9 fixture and shared canonical-source join, with preserved assertions
  and added adversarial cases.

Both commits ran the installed pre-commit hook normally; it skipped non-dashboard
paths and returned 0. The pre-push hook was not invoked. No hook was disabled.
No push, rebase, stash, history rewrite or GitHub plugin was used. The final journal
is an append-only documentation commit after the tested source commit.

The complete changed tracked path set contains **5 files** relative to the base:
this journal, the schema generator, its station-independence test, the human-decision
service and its test. Every mechanism file was read back from
`codex/commit-not-station` after commit and matched the tested bytes. No workflow,
dashboard, Foundry, Scientist, dependency declaration, lockfile, snapshot, debt
register or generated ledger was changed. `check_debt_ledger.py` was not invoked.
The failure/repair register was reopened for closeout; relevant P05/P29/P33/P35/
P38/P40/P41 obligations are addressed above. Ruff check and format check passed on
all four changed Python files; targeted tests only were used, as requested.

Raw local evidence was preserved under ignored `_cache`, rather than left as
untracked work. Commands above record their original execution paths. Archive map:

| Original measurement directory | Retained directory |
| --- | --- |
| `instruments2/.scratch/` | `instruments2/policy-engine/_cache/commit-not-station/root-scratch/` |
| `instruments2/policy-engine/.scratch/` | `instruments2/policy-engine/_cache/commit-not-station/product-scratch/` |
| `instruments2-python3143/policy-engine/.scratch/` | `instruments2-python3143/policy-engine/_cache/commit-not-station/baseline-scratch/` |

All prefixes are under `/Users/deniskopylov/polisyos/.worktrees/`. In particular,
the unapplied dashboard patch is retained in
`instruments2/policy-engine/_cache/commit-not-station/root-scratch/commit-not-station-row2/dashboard-timeout-handoff.patch`;
its complete edit is also embedded above. Raw proof producers preserve their
original layouts/commands; the archives are receipts, not additional committed
capability contracts. The worktrees and their local environments are retained.

The closeout whitespace red was **(a) PRODUCT** in the journal artifact: blank
diff-context spaces were embedded as trailing whitespace. Trimming them is document
housekeeping, not an instrument repair; the embedded proposal was checked again
for patch applicability. No source or assertion changed in this cleanup.
