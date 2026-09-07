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

## Continuation after the architect's merged verification (2026-09-07)

The branch was attached and clean before `git merge main`, which fast-forwarded
to `44b81e211a56a2ccffeb0893d3d38dd969e96a11`. The architect has closed original
Rows 1 and 4 on their named witnesses. The work below extends their residuals
and the widened wheels-only denominator; the earlier stop descriptions above
remain historical receipts, not current file restrictions.

The execution plan is to profile Row A's real producer/admission work before
changing budgets, preserve real timeout causes through the JSON reporter, replay
Row B's exact external importer set at the original slice base before attribution,
and start Row C with an isolated regex lock candidate and actual consumer tests.
Rows A/B/C run in parallel with disjoint edits. Shared `.venv` synchronization and
dependency declaration/lock integration are serialized: health evidence content
binds those files. Root owns integration, this journal, and attached-branch commits.

Pattern pass: P29/P32 require behavioral removal probes; P35 requires complete
artifact and test identity sets; P38 distinguishes genuine work from a deadline
proxy; P40 bounds unresolved packaging routes; P41 requires the slice-base replay
and actual input intersection before using an inherited attribution. These are
instrument and scaffolding repairs, not new capability or engineering appointments.
Dashboard files and the two external-importer test files now have explicit grants.
The debt register, generated ledger, workflow files, other lanes' checkouts, and
the prohibited capability-construction rows remain outside this work.

### Continuation Row A — real evidence suites and readable timeout causes

Continuation base: `44b81e211a56a2ccffeb0893d3d38dd969e96a11`, branch `codex/commit-not-station`, macOS arm64, dashboard workspace with the pinned Vitest 4.1.5 and the root-managed Python environment. The dashboard boundary was explicitly reopened by the continuation grant. This section supersedes the earlier unapplied timeout proposal; it does not reclassify the earlier ambiguous collection as zero cases or the earlier red diagnostic as a green gate.

Pattern pass: P29 requires exercising the real child and reporter; P35 requires complete identity sets; P37 requires retaining independent recomputation; P38 distinguishes a latency watchdog from the persistence property; P40 buckets the outer timeout as the same watchdog class one level deeper. The existing Python failure parser remains the same mechanism and retains its original assertions. No capability owner was appointed.

**Why the work was slow, before choosing a budget.** The actual instruments were profiled through their production Vite configuration, SSR module load, and real operation. The phase profiler and complete payloads are under `_cache/commit-not-station/continuation/row-a/`. On this station, health had Vite import 142.156 ms, server startup 404.601 ms, SSR load 204.245 ms, real measurement 4,777.051 ms, close 1.178 ms; readiness had 178.186 ms, 499.448 ms, 212.359 ms, 9,168.402 ms, and 1.867 ms respectively. Both invocations exited 0. Full app setup was under one second in both of the two complete instrument profiles; stripping the production Vite configuration would duplicate configuration without addressing the dominant work, so neither launcher changed.

The root's separate real health persistence profile exited 0 in 12.380 seconds: `_run_health_metric_producer` 9.756 s, its Node producer 7.921 s, independent DS18 verification 4.643 s in parallel, then independent health validation 1.577 s. The remaining 2.624 s included Python imports 1.155 s and revision-byte checking 0.642 s. All 37 subprocess events and the actual CAS/result were retained in `root-row-a/health-profile.json` and its companions. This code deliberately runs the producer and independent verification; caching or replacing one with the other's answer would weaken the authority predicate. The previous actual complete runs were health 63.654 s and readiness 127.341 s while other repository work was active. These timings establish variation and complete semantic results, not a causal benchmark attributing that variation to CPU load. The five producer/launcher/persistence module paths were byte-identical between the original slice base and continuation base (explicit git diff returned no changes); the whole transitive input set is not asserted identical.

**Classification.** The original absent interpreter/dependency remains class (c), repaired by the declared bootstrap/test environment; the previous masking product repair is verified without being rewritten. The previous 60-second child cutoff is class (d), INSTRUMENT: after provisioning, legitimate work existed and its completion depended on station wall time, so the cutoff prevented the live persistence result from arriving. The enclosing 20-second coverage/default 15-second Vitest watchdog (plus readiness's explicit 60-second case budget) was the same timing class one level deeper, classified (d): the same real computation and unchanged assertions completed but the runner rejected elapsed wall time. These are liveness cutoffs, not contractual latency assertions. The complete direct runs beyond the old cutoff distinguish this from a product defect; the real persisted payload/CAS checks distinguish it from a stale assertion. The exact old three missing-adapter expectations had already changed deliberately before this slice; this continuation changes none of the assertion expressions in either suite. An AST census compares the complete two-file set at `44b81e211` and the delivered candidate: 83/83 health assertion expression statements and 58/58 readiness assertion expression statements are identical after normalization; the full statements are in `assertion-census.json`.

The unreadable `STACK_TRACE_ERROR` is a separate (d) reporting defect in pinned Vitest 4.1.5, not a new persistence failure. Its runner's `makeTimeoutError` replaces text in the wrong direction when combining a captured stack with the real timeout Error; its JSON reporter chooses stack before message. The actual error still carries `Test timed out in ...` as its message. A local additive reporter now ensures every actual result error's message is preserved in the stack when absent, retaining the original frames and verdict. Enrollment happens in `configureVitest`, after command-line reporter selection, so the coverage/route callers using `--reporter=json` cannot silently bypass it. The same mechanism walks case, suite/module, and unhandled errors; it does not key on the placeholder marker.

**Change.** `persistenceProcessResult.ts` now owns shared child and enclosing watchdog constants. The measured 127.341-second maximum plus 25% headroom is 159.17625 seconds; rounding up to the next minute gives a 180-second child watchdog. The enclosing cases receive 240 seconds, so the child's failure can be reported before an outer timeout obscures it. Only the three real health persistence cases and the real readiness process-selection case use the enclosing budget. Both persistence invocation helpers use the child budget. Recomputing producers, independent validators, dynamic readiness claim enumeration, CAS checks, and original assertions remain intact. Canonical Prettier indentation expands the four newly three-argument test calls; it does not change their assertions. The new reporter is enrolled in `vitest.config.ts` and has a real nested-Vitest regression test.

The policy is bounded: a station that cannot finish within the measured watchdog still fails with its actual process/test cause; no finite watchdog proves arbitrary-load performance. A further cutoff of this declared timing class is a worked example of the limitation, not permission to keep increasing numbers or remove recomputation. This closes the tested supported environment's gate reachability while retaining a readable refusal outside the budget.

**Removal and failure probes.** Before reporter enrollment, `scripts/preserve-vitest-error-cause.test.ts` failed (exit 1) because the actual configured JSON reporter lost the timeout message for two real cases, one asynchronous and one synchronous. After enrollment, the same regression passed: both nested cases still failed with their own names and `Test timed out in 5ms`; the enclosing oracle passed. A scratch-only clone then replaced `preserveCause` with a no-op while preserving the reporter's class, plugin/name markers, methods, enrollment, two fixture identities, and timeout failures. The clone's two-case set had failed status for both cases but preserved the real cause for 0/2; the cause oracle exited 1. Artifacts: `reporter-before.log`, `reporter-after.log`, `reporter-removal-oracle.json`, and `reporter-removal/{report.json,reporter.ts,slow.test.ts,vitest.config.ts,stdout.log,stderr.log}`.

A separate scratch Vite transform changed only `PERSISTENCE_TEST_TIMEOUT_MS`'s value to 1 ms, retaining both constant names, parser, invocation, and every health assertion. The exact real snapshot case reached 13.933 seconds and became red with the actual `Test timed out in 1ms` cause visible in JSON. This selected 1/28 collected health cases; the other 27/28 were deliberately excluded by the selector, not setup-skipped. The runner source establishes that this synchronous timeout is applied after the callback and its assertions return successfully; a thrown assertion follows the separate rejection branch. The probe therefore distinguishes a healthy semantic callback from its intentionally broken enclosing watchdog. Artifacts: `budget-removal.config.ts`, `budget-removal.json`, `budget-removal.log`.

**Commands already completed.** Each gate was the only command in its shell invocation; redirected log output did not replace its exit code. Dashboard cwd was `policy-engine/apps/runtime-dashboard` except where stated.

- Product cwd: `node _cache/commit-not-station/continuation/row-a/profile-instrument.mjs health app > _cache/commit-not-station/continuation/row-a/health-app.log 2>&1` — exit 0. The corresponding `readiness app` invocation — exit 0.
- `corepack pnpm exec vitest run --project unit scripts/preserve-vitest-error-cause.test.ts --maxWorkers=1 > ../../_cache/commit-not-station/continuation/row-a/reporter-before.log 2>&1` — exit 1 before enrollment; same gate to `reporter-after.log` — exit 0 after enrollment.
- `node ../../_cache/commit-not-station/continuation/row-a/reporter-removal-probe.mjs > ../../_cache/commit-not-station/continuation/row-a/reporter-removal-oracle.json` — exit 1, expected missing-cause oracle red for both actual timeout cases.
- `corepack pnpm exec vitest run src/test/evidence/atlasHealthMetrics.test.ts --config ../../_cache/commit-not-station/continuation/row-a/budget-removal.config.ts --maxWorkers=1 --testNamePattern='persists a content-bound descriptive snapshot while recording its missing consumer' --reporter=json --outputFile=../../_cache/commit-not-station/continuation/row-a/budget-removal.json > ../../_cache/commit-not-station/continuation/row-a/budget-removal.log 2>&1` — exit 1, expected timeout red for the selected real persistence case.
- `corepack pnpm exec vitest run --project unit src/test/evidence/persistenceProcessResult.test.ts scripts/preserve-vitest-error-cause.test.ts --maxWorkers=1 --reporter=json --outputFile=../../_cache/commit-not-station/continuation/row-a/process-and-reporter.json > ../../_cache/commit-not-station/continuation/row-a/process-and-reporter.log 2>&1` — exit 0; 6/6 cases across 2/2 files passed. The five existing parser cases cover actual failed children with empty/malformed stdout, actual ENOENT launch failure, structured nonzero refusal, and success. The new reporter case executes the two genuine timeout failures as its negative witnesses.
- Repo cwd: `node policy-engine/_cache/commit-not-station/continuation/row-a/assertion-census.mjs > policy-engine/_cache/commit-not-station/continuation/row-a/assertion-census.json` — exit 0, both complete assertion sets unchanged.
- `corepack pnpm exec eslint scripts/preserve-vitest-error-cause.ts scripts/preserve-vitest-error-cause.test.ts src/test/evidence/persistenceProcessResult.ts src/test/evidence/atlasHealthMetrics.test.ts src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts vitest.config.ts` — exit 0.
- `corepack pnpm exec prettier --check` with the same six path arguments — exit 0.
- `corepack pnpm exec tsc --noEmit --module ESNext --moduleResolution Bundler --target ES2022 --skipLibCheck --esModuleInterop scripts/preserve-vitest-error-cause.ts scripts/preserve-vitest-error-cause.test.ts vitest.config.ts` — exit 0.
- Repo cwd: `git diff --check` — exit 0.

### Row A final checkpoint receipt

Disposition: **repaired**, with the explicit finite-watchdog limitation recorded above. The ordinary two-suite command now reaches and passes every collected assertion at source checkpoint `753e0458ad41ef362a5dd9e8ee126621c2cd1c1c`. This is the delivered replay, not the earlier scratch timeout diagnostic. The actual station was macOS 26.6.2 arm64, Node 22.22.2, pnpm 10.33.2, Python 3.14.0, jsonschema 4.25.1, with the root's freshly frozen new-lock environment. `NODE_OPTIONS` was absent. Before and after the wave, `git status -sb` reported the attached `codex/commit-not-station` branch and a clean working tree; `git rev-parse HEAD` returned the checkpoint above.

Exact gate, cwd `policy-engine/apps/runtime-dashboard`:

```sh
corepack pnpm exec vitest run --project unit src/test/evidence/atlasHealthMetrics.test.ts src/test/evidence/atlasSurfaceReadinessReconciliation.test.ts --maxWorkers=1 --testTimeout=20000 --hookTimeout=20000 --reporter=json --outputFile=../../_cache/commit-not-station/continuation/row-a/evidence-final.json > ../../_cache/commit-not-station/continuation/row-a/evidence-final.log 2>&1
```

Exit **0**. Complete requested denominator: 2/2 files; `atlasHealthMetrics.test.ts` passed 28/28 cases and `atlasSurfaceReadinessReconciliation.test.ts` passed 33/33 cases, hence 61/61 passed cases. Failed, skipped, and ambiguous case sets are each empty over that complete 61-case denominator. Vitest's recorded span from its `startTime` to the final file's `endTime` is 64.794 seconds; this is the runner's reported span, not a separately measured OS process wall time. The complete stdout is `evidence-final.log`; the complete JSON is `evidence-final.json` in `_cache/commit-not-station/continuation/row-a/`.

The full identity comparison was then run as its own gate from the product root:

```sh
node _cache/commit-not-station/continuation/row-a/compare-final-identities.mjs > _cache/commit-not-station/continuation/row-a/final-identity-comparison.json
```

Exit **0**. The comparator enumerated every file and case in the original ordinary run, original extended-child diagnostic, and final ordinary run. Neither compared complete report contained a Python traceback, and neither did the final log. Against the complete original diagnostic's 61-case identity set, added and removed sets are both empty. The original ordinary readiness collection remains explicitly **ambiguous**; the comparator never treats that unreadable file as a zero-case baseline. All four previously failing identities are now passed, with their unchanged assertions:

| Complete prior-failure identity | Final status | Final case duration |
| --- | --- | --- |
| `atlasHealthMetrics.test.ts::Atlas health metrics does not inherit caller NODE_OPTIONS into the fixed producer` | passed | 7.354 s |
| `atlasHealthMetrics.test.ts::Atlas health metrics ignores a caller PATH node that emits a schema-valid forged report` | passed | 7.404 s |
| `atlasHealthMetrics.test.ts::Atlas health metrics persists a content-bound descriptive snapshot while recording its missing consumer` | passed | 7.185 s |
| `atlasSurfaceReadinessReconciliation.test.ts::Atlas surface-readiness per-claim reconciliation ignores inherited process-selection controls on the closed path` | passed | 7.359 s |

The comparison artifact retains all 61 final case identities, all 61 complete diagnostic identities, their statuses/durations/failure messages, and the original collection limitation. No assertions or dashboard source were changed after the checkpoint. The existing parser regression's 5/5 cases and new real reporter regression's 1/1 case had already passed on the exact dashboard source bytes admitted in that checkpoint; the nested reporter test's two deliberately slow cases retain their failed status and actual cause. Those successful checks are not confused with the markers-preserving removal probes, whose oracles deliberately exited 1.

No further Row A source work remains. Future liveness failures outside the declared finite watchdog remain readable failed checks, not evidence that this lane proves a station performance benchmark. The failure/repair register was re-opened at closeout; P29, P35, P37, P38, P40, and P41 were checked. No ledger/register entry or workflow was changed, and no push was attempted.

## Continuation B — ds9-pa2-gateway-rebuild-fixture-uses-expired-mandate-evidence (2026-09-07)

**Disposition: repaired-with-a-limit.** The five importer cases and the original crash/reservation witnesses are green. The limit is retention of historical raw evidence: the authorized detached baseline disappeared after its completed replays and after its complete JUnit identity sets had been read and exported. Its original logs/XML and full input-audit file are now unavailable. This does not turn any unreadable historical file into a zero, and no inherited-red exemption is claimed.

### Station, scope, and classification

The slice base was `a8d323a2f63f1e4a02693215d1c6aead8e8802b0` at `/Users/deniskopylov/polisyos/.worktrees/instruments2-python3143/policy-engine`; continuation entry was `44b81e211a56a2ccffeb0893d3d38dd969e96a11` at `/Users/deniskopylov/polisyos/.worktrees/instruments2/policy-engine`. Both exact gate commands used the primary `.venv/bin/python`, Python 3.14.0, with identical relative `PYTHONPATH`, cache and pytest arguments. The baseline was a real detached Git worktree, not an archive. The current branch remained `codex/commit-not-station`. No production code, assertion, ownership assignment, or operational authorization rule changed in this continuation.

All four failing importer identities are **(c) BROKEN SCAFFOLDING**. The primary producer correctly reads signed `CurrentMandateOwnerEvidence` and requires `effective_from <= evaluated_at < effective_until`, current status, correct authority purpose, owner/rule/signature binding, and independently reconciled provenance (`agent_action_authority.py`, `_resolve_current_mandate_authority`). The helper default was anchored at 2026-08-19, ending at 14:00Z; DS9 records and the replay scenarios are at 2026-08-24 12:00Z. Reconstruction therefore lost the resolved contract and produced `current_mandate_authority_not_established;admission_contract_mismatch` before the intended human-decision consumer behavior. The two negative tests were not stale: provisioning current signed evidence makes their unchanged `DS9-DECISION-SOURCE-INVALID` expectations pass. The positive and invocation-replay tests likewise reach their unchanged effect assertions.

P40 bucket: this is the **same temporal scaffolding class one level deeper**, previously bounded by the now-expanded file permission. The repair widens the helper to an explicit `mandate_authority_at` scenario instant (defaulting to the original fixture `NOW`) and passes the actual scenario instant at every affected gateway reconstruction. Explicit negative evidence stays untouched. It does not call the production clock merely to build test evidence.

A reviewer found a targeted companion outside the original five: `test_envelope_expiring_after_decision_is_rechecked_before_effect`. The initial candidate helper read the production clock and exhausted its two-item iterator earlier; this candidate failed with `StopIteration` at decision-time contract resolution. Exact slice-base replay independently failed with `StopIteration` at effect-time contract resolution. Production reads the clock for decision time, mandate currentness during contract resolution, mandate revalidation before effect, and envelope currentness before effect. Counting two reads did not express its intended lifecycle. This is another instance of the **same BROKEN SCAFFOLDING class**, not a stale expectation or a new production defect. The bounded widening holds an explicit scenario time during real production/persistence, calls the original `persist_decision` with its original arguments and preserves its return, then advances time after persistence completes. Signed mandate evidence covers both phases. The original `pytest.raises` exception and message, original dispatch call, and effect assertion remain intact.

Only `policy-engine/tests/unit/runtime/quality/test_agent_action_authority.py` changed for B. The complete one-file AST census retains all 52/52 original `assert` nodes, unchanged per all 66/66 top-level functions, and all 11/11 original `pytest.raises` calls. Frozen/tested SHA-256: `5f21739085a7172a6df49bd4f8fb735780653c336c40bc727a4f56e217d48eb5`. Root and independent delta review found no concrete blocking issue before the final wave. P08, P29, P34, P35, P38, P40 and P41 were checked against the failure-pattern register before closeout.

### Complete case identity sets and verdicts

All counts below come from complete JUnit testcase enumerations, with no collection errors, setup skips, or harness-level traceback. Individual failing-test tracebacks are accounted for in the reports; no crashed run is treated as a smaller finding set. `entry-verdicts.json` preserves all baseline testcase identities, outcome messages and JUnit suite metadata exported before worktree loss; `verdicts.json` labels which raw files remain available.

| Gate | Tool exit | Complete outcome denominator | Wall seconds |
| --- | --- | --- | --- |
| `slice_base` | 1 | 4 failure, 1 passed / 5 cases | 60.68 |
| `merged_entry` | 1 | 4 failure, 1 passed / 5 cases | 58.08 |
| `audited_slice_base` | 1 | 4 failure, 1 passed / 5 cases | 59.08 |
| `audited_final` | 0 | 5 passed / 5 cases | 159.12 |
| `companion_slice_base` | 1 | 1 failure / 1 cases | 95.55 |
| `companion_initial_candidate` | 1 | 1 failure / 1 cases | 92.13 |
| `final_companions` | 0 | 6 passed / 6 cases | 154.56 |
| `removal` | 1 | 5 failure, 1 passed / 6 cases | 155.39 |

The exact original five-case set is:

| Complete test identity | Slice base | Merged entry | Final | Removal |
| --- | --- | --- | --- | --- |
| `tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_pa2_arm_re_resolves_s7_without_production_packet` | failure | failure | passed | failure |
| `tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_rejects_changed_admission_under_same_request_ref` | failure | failure | passed | failure |
| `tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_rejects_changed_live_permission_snapshot_under_same_request_ref` | failure | failure | passed | failure |
| `tests/unit/runtime/quality/test_agent_action_authority.py::test_currentness_projection_round_trip_cannot_feed_operational_consumer` | passed | passed | passed | passed |
| `tests/unit/runtime/quality/test_agent_action_authority.py::test_human_approval_cannot_replay_after_invocation_content_changes` | failure | failure | passed | failure |

The four failed identities are the same on base and merged entry, but their deciding causes differ: all four base failures are `HumanDecisionUnavailableError: blocked` during `create_record`; the merged-entry failures occur later when the reconstructed gateway consumes expired mandate evidence. Equal identities do not imply equal provenance.

The complete six-case companion set is:

- `tests/unit/runtime/http/test_control_plane_store.py::test_human_decision_crash_reservation_requires_reconciliation_before_reuse` — passed.
- `tests/unit/runtime/http/test_control_plane_store.py::test_human_decision_reservation_preserves_microsecond_lease_boundary` — passed.
- `tests/unit/runtime/http/test_human_decision_service.py::test_human_decision_hard_crash_reconciles_null_ref_signed_orphan_before_v2` — passed.
- `tests/unit/runtime/quality/test_agent_action_authority.py::test_current_mandate_evidence_is_rechecked_immediately_before_effect` — passed.
- `tests/unit/runtime/quality/test_agent_action_authority.py::test_envelope_expiring_after_decision_is_rechecked_before_effect` — passed.
- `tests/unit/runtime/quality/test_agent_action_authority.py::test_matching_contract_signer_without_current_mandate_evidence_refuses` — passed.

The named crash witness still exercises recovery and the committed transition. Both reservation witnesses remain green. The two mandate-authority negatives prove that missing evidence and explicit evidence that expires immediately before effect are still rejected. The new companion fixture now reaches the real envelope revalidation instead of failing on a finite clock iterator.

### Removal probes and artifact denominator

`row_b_remove_clock.py` is an ignored, ephemeral pytest plugin. For the five importer cases it replaces only default fixture provisioning with the old signed interval while retaining schema/kind, `current=True`, authority purpose, signer identity and provenance markers. Real signing, storage, resolution and verification still run. It produces the same four named expiry failures; the read-side-projection rejection case remains green. For the companion it freezes the real producer clock at the earlier instant while leaving the source clock-transition code and markers present. Real dispatch then completes without the expected recording error, so the unchanged `pytest.raises` fails with `DID NOT RAISE`. The complete six-case removal set has five failures and one pass; removal exit is 1. The plugin makes no tracked edits.

The retained artifact census walks every `*.manifest.json` in each declared root and reads every selected mandate `.blob`; it does not infer authority from the presence of a signature file. The real runtime gates above verify the signed artifacts. `artifact_census.py` / `artifact-census.json` enumerate: merged-entry `pytest` 265/265 readable manifests, final `audit-pytest` 261/261, final `companion-pytest` 93/93, and `removal-pytest` 281/281. The corresponding complete selected mandate payload denominators are 10, 7, 3 and 11, with no unreadable case in those four retained sets. These are separate artifact sets, not a claim that a smaller total means improvement. Exact finding identities were compared above.

### Historical provenance and retention limit

P41 does **not** permit “inherited.” The exact slice-base command completed, but the positive changed-input intersection defeats the required disjointness condition. The observation-only runner started a Python audit hook before running pytest, recorded the complete observed tracked read/import/directory-entry sets, and preserved pytest’s actual exit. Before loss, the baseline audit reported 6,408 observed tracked inputs / 10,592 tracked repository files and 1,535 imported tracked modules. The current full audit retains 6,408 observed tracked inputs / 10,593 tracked repository files and 1,535 imported tracked modules. In both observations the direct imported intersection with the complete eight-path `a8d323a2f..44b81e211` changed set contains these two exact paths:

- `policy-engine/src/polisyos/runtime/http/services/human_decisions.py`
- `policy-engine/tests/unit/runtime/http/test_human_decision_service.py`

This positive overlap is conclusive even though a global input denominator is not established: integer file-descriptor identities are `ambiguous`, and subprocess file reads are outside the Python hook. No cross-station repository reads were observed in the reported hook scope. Source reads by repository-wide AST discovery are data reads; no debt-ledger checker was executed. The current full audit and intersection report remain at `audited-inputs.json` and `input-intersection.json`.

After the baseline replays and exported full testcase identity sets, its path unexpectedly disappeared and Git reported its gitdir pointer as prunable. No reconstruction, pruning, reset or cleanup was attempted. The full baseline audit identity file is now **unavailable/ambiguous**, not empty. Its previously read two-path direct overlap and complete JUnit identity/outcome export remain as receipts; its raw logs/XML and full audit cannot now be independently re-read. That is the handback limit. The behavior has been repaired; the raw historical receipt retention is partial.

Proposed incidental row: `disposable-measurement-worktree-receipts-not-exported-before-cleanup`, proposed owner `team-devx`. A completed measurement should export raw gate logs, JUnit and complete audit identity files to the primary lane before its disposable station can disappear. Cleanup provenance here is not established, so this is a retention proposal rather than attribution to another actor.

### Exact commands and remaining boundary

All commands below were separate invocations. Shell redirection did not append an echo or mask the gate status. `commands.json` stores the exact command strings and both working directories; `analyze_evidence.py` enumerates the reports and preserves the missing-baseline distinction. No shared environment mutation was made by B. Final tests finished before the root was told that the environment was released.

Exact original five, run at slice base and merged entry:

```sh
/usr/bin/time -p env PYTHONPATH=src:tests POLISYOS_CACHE_HOME=_cache/commit-not-station/continuation/row-b/cache /Users/deniskopylov/polisyos/.worktrees/instruments2/policy-engine/.venv/bin/python -m pytest tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_pa2_arm_re_resolves_s7_without_production_packet tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_rejects_changed_admission_under_same_request_ref tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_rejects_changed_live_permission_snapshot_under_same_request_ref tests/unit/runtime/quality/test_agent_action_authority.py::test_currentness_projection_round_trip_cannot_feed_operational_consumer tests/unit/runtime/quality/test_agent_action_authority.py::test_human_approval_cannot_replay_after_invocation_content_changes --basetemp=_cache/commit-not-station/continuation/row-b/pytest --junitxml=_cache/commit-not-station/continuation/row-b/gate.xml -q --tb=short > _cache/commit-not-station/continuation/row-b/gate.log 2>&1
```

Exact audited five, run at slice base and final tree:

```sh
/usr/bin/time -p env PYTHONPATH=_cache/commit-not-station/continuation/row-b:src:tests POLISYOS_CACHE_HOME=_cache/commit-not-station/continuation/row-b/audit-cache /Users/deniskopylov/polisyos/.worktrees/instruments2/policy-engine/.venv/bin/python -m row_b_audited_pytest tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_pa2_arm_re_resolves_s7_without_production_packet tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_rejects_changed_admission_under_same_request_ref tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_rejects_changed_live_permission_snapshot_under_same_request_ref tests/unit/runtime/quality/test_agent_action_authority.py::test_currentness_projection_round_trip_cannot_feed_operational_consumer tests/unit/runtime/quality/test_agent_action_authority.py::test_human_approval_cannot_replay_after_invocation_content_changes --basetemp=_cache/commit-not-station/continuation/row-b/audit-pytest --junitxml=_cache/commit-not-station/continuation/row-b/audited-gate.xml -q --tb=short > _cache/commit-not-station/continuation/row-b/audited-gate.log 2>&1
```

Companion falsification, run at slice base and initial candidate:

```sh
/usr/bin/time -p env PYTHONPATH=src:tests POLISYOS_CACHE_HOME=_cache/commit-not-station/continuation/row-b/candidate-regression-cache /Users/deniskopylov/polisyos/.worktrees/instruments2/policy-engine/.venv/bin/python -m pytest tests/unit/runtime/quality/test_agent_action_authority.py::test_envelope_expiring_after_decision_is_rechecked_before_effect --basetemp=_cache/commit-not-station/continuation/row-b/candidate-regression-pytest --junitxml=_cache/commit-not-station/continuation/row-b/candidate-regression.xml -q --tb=short > _cache/commit-not-station/continuation/row-b/candidate-regression.log 2>&1
```

Final six companions:

```sh
/usr/bin/time -p env PYTHONPATH=src:tests POLISYOS_CACHE_HOME=_cache/commit-not-station/continuation/row-b/companion-cache /Users/deniskopylov/polisyos/.worktrees/instruments2/policy-engine/.venv/bin/python -m pytest tests/unit/runtime/http/test_human_decision_service.py::test_human_decision_hard_crash_reconciles_null_ref_signed_orphan_before_v2 tests/unit/runtime/http/test_control_plane_store.py::test_human_decision_crash_reservation_requires_reconciliation_before_reuse tests/unit/runtime/http/test_control_plane_store.py::test_human_decision_reservation_preserves_microsecond_lease_boundary tests/unit/runtime/quality/test_agent_action_authority.py::test_matching_contract_signer_without_current_mandate_evidence_refuses tests/unit/runtime/quality/test_agent_action_authority.py::test_current_mandate_evidence_is_rechecked_immediately_before_effect tests/unit/runtime/quality/test_agent_action_authority.py::test_envelope_expiring_after_decision_is_rechecked_before_effect --basetemp=_cache/commit-not-station/continuation/row-b/companion-pytest --junitxml=_cache/commit-not-station/continuation/row-b/companion-gate.xml -q --tb=short > _cache/commit-not-station/continuation/row-b/companion-gate.log 2>&1
```

Removal six:

```sh
/usr/bin/time -p env PYTHONPATH=_cache/commit-not-station/continuation/row-b:src:tests POLISYOS_CACHE_HOME=_cache/commit-not-station/continuation/row-b/removal-cache /Users/deniskopylov/polisyos/.worktrees/instruments2/policy-engine/.venv/bin/python -m pytest -p row_b_remove_clock tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_pa2_arm_re_resolves_s7_without_production_packet tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_rejects_changed_admission_under_same_request_ref tests/unit/runtime/quality/test_agent_action_authority.py::test_agent_gateway_rejects_changed_live_permission_snapshot_under_same_request_ref tests/unit/runtime/quality/test_agent_action_authority.py::test_currentness_projection_round_trip_cannot_feed_operational_consumer tests/unit/runtime/quality/test_agent_action_authority.py::test_human_approval_cannot_replay_after_invocation_content_changes tests/unit/runtime/quality/test_agent_action_authority.py::test_envelope_expiring_after_decision_is_rechecked_before_effect --basetemp=_cache/commit-not-station/continuation/row-b/removal-pytest --junitxml=_cache/commit-not-station/continuation/row-b/removal-gate.xml -q --tb=short > _cache/commit-not-station/continuation/row-b/removal-gate.log 2>&1
```

Final lint:

```sh
.venv/bin/python -m ruff check tests/unit/runtime/quality/test_agent_action_authority.py
```

Diff whitespace check:

```sh
git diff --check -- tests/unit/runtime/quality/test_agent_action_authority.py
```

No engineering appointment was made. No production repair remains for the named B behavior; the only B limit is partial historical raw-receipt retention. All primary artifacts and complete final case identities remain in `_cache/commit-not-station/continuation/row-b`. Root owns journal integration, branch verification and commits. B made no commit and no push.

# Row C / Row 3 continuation — core wheel installation and preserved consumers

Status: **repaired-with-a-limit**. Root class **INSTRUMENT (d)**. The complete core dependency set now installs from wheels on declared CPython 3.14; optional vector search remains available through the existing HNSW implementation and real CAS persistence. Optional/all/research installations retain HNSW source-build dependence. Presidio's own matching path remains blocked before matching on Python 3.14; its available production fallback was separately measured by root.

Artifact root for every relative path below: `policy-engine/_cache/commit-not-station/continuation/row-c/`. Product working directory: `/Users/deniskopylov/polisyos/.worktrees/instruments2/policy-engine`. All commands below were sole commands in their invocations; redirecting each command's output retained that command's exit status. No GitHub plugin, push, stash, compiler installation, workflow edit, forbidden production edit, ledger read, or ledger checker was used by this subagent.

## Root evidence and decision

The earlier complete core export had 116 requirement lines / 114 selected identities on both macOS arm64 and Linux x86_64 CPython 3.14. Its exact incompatibility set was `{hnswlib==0.8.0, odfpy==1.4.1, regex==2024.11.6}`, zero ambiguous cases; see the preserved initial `root-scratch/commit-not-station-row3/core-wheel-census.json` and `row3-report.md`. This is one dependency-instrument class: installation depends on station compiler capability, although the declared interpreter and dependency tree are unchanged. The continuation widened the artifact denominator instead of stopping after HNSW's first solver refusal (P35/P38/P40).

A blanket regex upgrade was actually attempted and refused: `uv lock --upgrade-package regex==2026.9.3` exited 1 (`regex-lock.log`). Marker 1.10.2 requires regex<2025, so the repair reuses the existing Pillow conflict: `ci = ["pillow>=12", "regex>=2026.9.3"]`, mutually exclusive with `table-extraction`. Default core and core+ci select regex2026.9.3; Marker/table-extraction keep regex2024.11.6. No Marker upgrade or broader redesign was introduced.

HNSW comparison: official `hnswlib` publication history contains no wheels (11/11 published artifacts); `chroma-hnswlib` has 277 wheel files / 291 total files, with zero compatible cp314/abi3 candidates in its complete history. A complete PyPI project-name census (886,796 project names, all 25 names containing hnsw inspected) is retained in `pypi-hnsw-projects.json` and `pypi-hnsw-artifacts.json`. One indexed project returned404 and is **ambiguous**, not zero. Other ABI-compatible named projects are different distributions/APIs and do not establish a drop-in replacement for VectorMemoryStore. We chose the authorized optional-extra route, retaining exact hnswlib0.8.0. `vector-search` is explicit; `research` includes it; `all` includes research; cloud `--all-extras --dev` includes it automatically.

ODF comparison: PyPI's odfpy1.4.1 is source-only, but piwheels publishes a universal `py2.py3-none-any` wheel. The wheel SHA256 is `1d1c3ea36a422d3c5cd4c2457ea0e0be59841d6c26d28bd3d5e43f060565d11b`; upstream PyPI sdist SHA256 is `db766a6e59c5103212f3cc92ec8dd50a0f3a02790233ed0b52148b70d3c438ec`. Both download hashes were checked against registry metadata. The COMPLETE odf/ package subtree is byte-identical: 34 source files / 34 wheel files, missing-source=[], missing-wheel=[], changed=[]. `odfpy-source-comparison.json` records the whole result. ODF stays core, same version and source payload, via package-scoped direct wheel URL in `[tool.uv.sources]` and locked SHA256. We initially tried a package-scoped named index. Actual product uv.toml caused an index-precedence warning; lock checks and an actual relock still exited0, so we do not call that a failed resolver. The direct URL removes that precedence ambiguity while selecting the same verified artifact. No uv.toml edit was needed.

Sources: https://pypi.org/project/hnswlib/0.8.0/ ; https://pypi.org/project/chroma-hnswlib/0.7.6/ ; https://pypi.org/project/regex/2026.9.3/ ; https://pypi.org/project/odfpy/1.4.1/ ; https://www.piwheels.org/project/odfpy/ .

## Final installation receipts

Canonical uv: `/Users/deniskopylov/.local/bin/uv` 0.9.21. Interpreter: `/Users/deniskopylov/.local/share/uv/python/cpython-3.14-macos-aarch64-none/bin/python3.14` (CPython3.14.3). Native station macOS arm64. The Linux installation below is an actual installation of Linux wheel artifacts using uv's target selection; it is **not** a Linux runtime execution claim.

Each of the following actual-product invocations used a fresh independent environment, disabled all source builds, disabled uv cache reads/writes, and excluded only the local project build. Each exited0 and installed113/113 selected package identities; every log was parsed to confirm no traceback. The complete identities, not only totals, are in `final-install-identities.json`.

```sh
env UV_PROJECT_ENVIRONMENT=_cache/commit-not-station/continuation/row-c/final-core-env /Users/deniskopylov/.local/bin/uv sync --frozen --no-dev --no-install-project --no-build --no-cache --python /Users/deniskopylov/.local/share/uv/python/cpython-3.14-macos-aarch64-none/bin/python3.14 > _cache/commit-not-station/continuation/row-c/final-core-wheel-sync.log 2>&1
```

Core+ci used the same flags with `UV_PROJECT_ENVIRONMENT=.../final-ci-env` and `--group ci`, log `final-ci-wheel-sync.log`, exit0. Linux used `UV_PROJECT_ENVIRONMENT=.../final-linux-core-env` and `--python-platform x86_64-manylinux_2_28`, log `final-linux-core-wheel-sync.log`, exit0.

A fourth native installation established the literal compiler-free PATH condition, not just uv's no-build policy:

```sh
/usr/bin/env PATH=/Users/deniskopylov/polisyos/.worktrees/instruments2/policy-engine/_cache/commit-not-station/continuation/row-c/empty-bin UV_PROJECT_ENVIRONMENT=_cache/commit-not-station/continuation/row-c/final-compiler-free-core-env /Users/deniskopylov/.local/bin/uv sync --frozen --no-dev --no-install-project --no-build --no-cache --python /Users/deniskopylov/.local/share/uv/python/cpython-3.14-macos-aarch64-none/bin/python3.14 > _cache/commit-not-station/continuation/row-c/final-compiler-free-core-wheel-sync.log 2>&1
```

`empty-bin/` is empty. Exit0,113/113 installed identities. Log SHA256 `a5251f5e64c8a2dbd8fe3a7856c9d53e8016290eda33866bf912d77eea460c1d`. No compiler or system headers were added. Core+ci install set equals core install set. Source-build-only HNSW is absent from these core receipts, as intended by the explicit extra selection.

Final lock verification `/Users/deniskopylov/.local/bin/uv lock --check` exited0 from actual product root. Final pyproject SHA256 `b420723ef2454bce7685b01ff11d7cf29399be8f31399366a2559ffae34a9c48`; final lock SHA256 `d409a3d90e1ddbf72ec5c64fd3031a203d3963495fc8ca5079e716b3960c6ffd`. Complete lock identity comparison417->418 records only ODF's source change and the added regex2026.9.3 branch; no unrelated package version changes. Resolver-generated marker changes are retained. See `final-lock-identity-diff.json`.

## Runtime consumers and removal witnesses

Tracked file: `tests/repo_quality/test_dependency_runtime_witnesses.py`. The final command `env PYTHONPATH=src _cache/commit-not-station/continuation/row-c/core-env/bin/python -m unittest tests.repo_quality.test_dependency_runtime_witnesses -v` exited0: **3/3 tests, zero skipped**,1.570seconds; full log `final-tracked-runtime-tests.log`. That independent environment was provisioned with core, actual optional vector-search, then test dependencies. Ruff check, Ruff format --check, git diff --check, and integrated uv lock --check all exited0. No existing assertion was weakened.

**Regex/tiktoken:** actual library matching and normal special-token admission were exercised, plus production `_tiktoken_count`. Normal BPE segmentation is Rust, so only ordinary encoding would miss the Python regex boundary. The test instead exercises Python regex segmentation against the independent Rust encoder, and real normal encode's regex-based rejection of forbidden tokens. The test enumerates all7/7 `tiktoken.list_encoding_names()` entries and all1105/1105 special-token entries, plus35/35 declared corpus/encoding pairs; the corpus covers numeric punctuation, Ukrainian/emoji, Arabic/Hindi/Chinese, combining marks and whitespace, and a near-miss special spelling. All actual special tokens are rejected by default and accepted with their exact registered ID when explicitly allowed. Oldregex2024.11.6 on CPython3.14.0 vs newregex2026.9.3 on CPython3.14.3 produced identical1140/1140 declared finding/result identities. Neither run traced back. Full receipts `baseline-regex-full-registry.log`, `candidate-regex-full-registry.log`.

**ODF:** real pandas odf writer emits a two-sheet workbook; actual CKANResourceConnector `_parse_resource(...,"ods")` consumes its bytes. Expected complete frame has3rows/4columns, Unicode names, signed floating amounts, booleans and source-sheet labels. Corrupt ZIP input and max_rows2 against the3-row workbook both raise the production FetchError. This is not the older mocked pd.read_excel fixture. `candidate-ods-behavior.log` records the actual frame and both negative identities.

**HNSW:** before extra installation the unchanged VectorMemoryStore constructor fails with the explicit missing-hnswlib cause (exit1, `vector-before-extra.log`). Fresh optional sync `env UV_PROJECT_ENVIRONMENT=../core-env /Users/deniskopylov/.local/bin/uv sync --frozen --no-dev --extra vector-search --no-install-project --no-cache --python <managed3.14.3>` from candidate-all actually built hnswlib0.8.0 from upstream source, installed1new package, exit0 (`vector-extra-sync.log`,12.84sec preparation). This is an availability receipt on an existing developer compiler station, **not** a core-wheel receipt. Real cosine search orders north/east/south at distances0/1/2; overwriting east preserves cardinality and updates metadata; actual FileSystemCAS save+reload preserves complete ranked results. `vector-after-extra.log` records the source path, data and artifact reference. No replacement implementation or capability deletion was introduced.

**Tracked removal probes:** scratch `tracked_removal_runner.py` imports the unchanged tracked test and changes runtime behavior in that process, leaving tracked source, function names and marker strings intact. `python -m tracked_removal_runner regex` replaces actual special-token matching with an impossible pattern: exit1, DID NOT RAISE ValueError (`tracked-regex-removal-clean.log`). `... ods` removes production spreadsheet parsing but keeps the method: exit1, actual frame0x0 vs expected3x4 (`tracked-ods-removal-clean.log`). `... vector` removes actual query results but keeps method/metadata: exit1, [] vs north/east/south (`tracked-vector-removal-clean.log`). Initial unittest subTest/pytest.raises interaction added reporting errors after the expected failed rejection; scaffolding was corrected by removing subTest suppression, and the final probes each name one actual semantic failure. No production repair was inferred from those deliberate mutations.

## Optional regex consumers and bounded residuals

The complete lock's regex consumer package set is exactly4/4: tiktoken0.12.0, marker-pdf1.10.2, presidio-analyzer2.2.360, transformers4.57.6. Marker keeps oldregex; it is not silently upgraded.

Actual Transformers4.57.6 was installed with no source builds and all selected helper dependency versions constrained to this lock (`transformers-locked-install.log`, exit0). The real imported GPT2Tokenizer, Qwen2Tokenizer and Whisper EnglishNumberNormalizer were run without model downloads.15/15 declared cases over those3named consumers are identical with old/new regex; both exits0, no traceback. `transformers-locked-baseline.log`, `transformers-locked-candidate.log`, `transformers-differential.json`. A matching-removal mutation made nonempty GPT2 input decode empty, exit1 (`transformers-locked-removal.log`). The old regex module was copied alone from the original station into isolated old-regex-layer, so the installed Transformers/dependency set stayed fixed between differential runs. This proves the named behavior set, not every model: a complete wheel-source AST census found regex imports in25/2214 Transformers Python files, no unreadable files (`optional-regex-consumer-census.json`).

Root's Presidio receipts: actual frozen core+security+test installation193/193 packages exited0, but real Presidio import failed before matching for **both** regex versions with spaCy3.8.11 -> pydantic.v1 ConfigError `unable to infer type for attribute "REGEX"` on CPython3.14.3. Matching is **ambiguous**, never zero. Root also ran actual PresidioDetector fallback for both versions:4/4 declared input finding-identity sets unchanged, including benign input; both exits0 and `_presidio_available=False`. `presidio-runtime-comparison.json`, `presidio-old-regex-runtime.json`, `presidio-new-regex-runtime.json`, sibling stderr files; root owns full install/import logs. Complete Presidio wheel AST census4regex-importing files/90Pythonfiles, no unreadable files. Proposed residual row `presidio-spacy-import-blocked-before-matching-on-declared-python`, proposed owners team-devx with security owner. Do not claim Presidio matching is repaired or appoint an owner. This is a NEW scaffolding/dependency finding relative to the core wheel mechanism; its repeat with the old regex separates it from the regex bump. Slice-base inherited attribution remains subject to root's P41 measurement.

## CI selection and limits

Complete workflow walk:12/12 YAML files,53jobs,302steps,29setup-policy-engine-python action selectors, zero ambiguous.28/29 action selectors omit vector-search/research/all; minimal/docs/runtime profiles omit HNSW. Exactly one existing selector still requests HNSW: `.github/workflows/frontend-nightly.yml`, job `benchmark-contours`, `extras: all`. Full selectors in `ci-selector-census.json`; no workflow was changed. Research/all/cloud selections deliberately keep HNSW capability. A fresh optional extra sync with `--no-build --no-cache` exits2 on hnswlib (`vector-extra-no-build-limit.log`), the measured remaining compiler dependence. No assertion that all CI jobs or all extras install from wheels is made; changing the broad benchmark job's requested capability set requires an architect selection decision, not an invented workflow edit.

Frozen cloud export before/after keeps395/395 selected package identities on macOSarm64 and410/410 on Linuxx86_64 unchanged; ODF source changes to the identical verified wheel. Core package identities remove HNSW and oldregex and add newregex, leaving113selected; no smaller count is claimed as proof without the full set diff. `final-export-identity-diff.json`, `base-cloud.txt`, `final-cloud.txt`, `base-core.txt`, `final-core.txt`. All export commands exited0.

No remaining work is required in the three tracked Row C files for the stated core closure. Remaining limits: optional HNSW source builds, broader all/research CI selection, native Linux runtime not exercised by the cross-target artifact installation, Presidio matching blocked before its subject, and model/recognizer semantic behavior outside the explicitly exercised case sets. These limits are recorded rather than silently generalized away.

### Integrated source checkpoint and provisioning

Root independently reviewed all continuation mechanism files and the complete final
dependency test identity set. The DS9 helper review caught the clock-read regression
before commit; its final explicit scenario-time repair received a second delta review.
The final dependency source/lock/runtime witnesses and installation receipts also
received an independent read-only review, with no concrete blocker found. This
freezes the source before the ordinary two-suite evidence wave.

The primary environment's first frozen offline synchronization returned **1** because
the new regex wheel was not in this product's configured cache. This is local
provisioning **(c)**, not a repository dependency-resolution failure. Its complete
output is `continuation/primary-final-sync.log`. The same required extras were then
synchronized online, exit **0**, with full output at
`continuation/primary-final-sync-online.log`:

```sh
/Users/deniskopylov/.local/bin/uv sync --frozen --extra lint --extra test --extra runtime --extra ml --extra vector-search --group ci
```

The retained complete seven-package version receipt in
`continuation/primary-final-environment.json` verifies Python **3.14.0**, jsonschema
4.25.1, pydantic 2.12.5, FastAPI 0.128.6, pytest 9.0.2, regex 2026.9.3, HNSW 0.8.0
and odfpy 1.4.1. Required test/runtime extras were retained explicitly. This
development environment is separate from the no-build core-install witnesses.

The actual primary environment then passed **7/7** tests across the complete
three-case new runtime witness file and the existing four-case Pillow/cloud
selection witness file, with no failures, skips, or harness traceback:

```sh
.venv/bin/python -m pytest tests/repo_quality/test_dependency_runtime_witnesses.py tests/repo_quality/tools/test_pillow_dependency_selection.py -q --tb=short --junitxml=_cache/commit-not-station/continuation/primary-dependency-gate.xml
```

Its full output and complete JUnit identity enumeration are retained beside the
XML as `primary-dependency-gate.log` and `primary-dependency-gate-identities.json`.
Ruff passed for both changed Python test files; `git diff --check` passed.

The Presidio comparison used an independent frozen core/security/test environment
on Python 3.14.3. Actual `uv pip install --python <that environment>/bin/python`
invocations selected regex 2024.11.6 and then 2026.9.3, each exit 0. The actual
production fallback probe was invoked for each through
`python -m _cache.commit-not-station.continuation.presidio_runtime_probe`, with
`PYTHONPATH=src`; both exited 0. The script, full install/import logs, per-version
JSON/stdout and stderr, and exact finding comparison remain under `continuation/`
and `continuation/row-c/presidio-*`. The failed import itself is preserved in
`presidio-new-regex-import.log`; it is never counted as a zero-finding matching run.

### Continuation closeout at the push boundary

Source checkpoint: **753e0458ad41ef362a5dd9e8ee126621c2cd1c1c**.
The installed pre-commit hook ran normally and passed contrast, reduced-motion,
Prettier and ESLint in 16.89 seconds; all six dashboard files were unchanged by
formatting. No hook was disabled. After commit, root read all **11/11** changed
tracked files back from `codex/commit-not-station`; every file matched the tested
working-tree bytes. The receipt is `continuation/source-checkpoint-readback.json`.

After the frozen environment update and source commit, root replayed the complete
union of B's five importers and six companions, including the named crash and
reservation pair. The sole gate was `.venv/bin/python -m pytest` with exactly the
11 node IDs enumerated in `continuation/integrated-ds9-identities.json`, `-q
--tb=short`, an isolation-local `--basetemp`, and JUnit output. Full stdout and XML
are `integrated-ds9-gate.log` and `integrated-ds9-gate.xml`. Exit **0**, **11/11**
passed, no skipped/error/failure identities or Python traceback. The complete
case-set difference from the earlier five-plus-six wave is empty in both
directions. JUnit records 3.176 seconds; no performance conclusion is drawn from
this separate warm-environment run. This replay was justified by the environment
change after the earlier baseline-comparison wave, not by a larger test scope.

Final disposition for all **3/3** continuation rows:

| Row | Status | Closure and remaining limit |
| --- | --- | --- |
| A — evidence deadlines and timeout causes | **repaired** | Both requested suites pass 61/61 with unchanged case identities and assertions; genuine timeout causes remain visible, and both removal probes are red. The documented finite watchdog remains a liveness bound. |
| B — `ds9-pa2-gateway-rebuild-fixture-uses-expired-mandate-evidence` | **repaired-with-a-limit** | All five importers, the named crash/reservation witnesses and three additional companions pass. Historical replay was performed; positive changed-input overlap defeats inherited attribution. Exported baseline identities survive, but the disappeared detached station's full raw receipts cannot be re-read. |
| C — complete core wheels-only set | **repaired-with-a-limit** | All 113/113 selected core packages install with source builds disabled and an empty compiler PATH; regex, ODS and actual optional HNSW behavior have positive and negative witnesses. Broad all/research selections still build HNSW; Presidio matching remains blocked before its subject; cross-target Linux installation does not prove Linux runtime execution. |

The two proposed incidental rows are recorded above with proposed owners, not
appointments: measurement-receipt retention (`team-devx`) and Presidio/spaCy import
compatibility (`team-devx` with the security owner). The remaining all/research CI
capability-selection limit requires the architect to select the
desired benchmark capability set; there is no verified exact replacement workflow
edit to hand back, so none is invented. Neither of the two excluded capability
construction rows was taken up.

Original Rows 1 and 4 remain closed on the architect's named witnesses. This
continuation changed no production source, schema snapshot, workflow, action,
debt register, generated ledger, or other lane's branch/worktree. The normal
pre-push hook was never invoked. No push, rebase, force operation, stash storage,
GitHub plugin or debt-ledger checker was used. The final journal update is a
separate appended commit after the tested source checkpoint.
