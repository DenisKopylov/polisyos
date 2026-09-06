# Task 1 — measuring instrument journal

Date: 2026-09-06. Executor branch: `codex/measuring-instrument`.
Slice base: `0373364448f766ecba871f3abae23a2b563e63ac`.
Source repair: `f69400b1f00e58d241aa68acf46c5af269d17057`.

The schema divergence has a reproduced cause and a repair with independent station
evidence. This handback stops at the architect's push decision. The two CI-dependent
rows remain open. No register, workflow, snapshot, or model contract was edited.

The [evidence JSON](2026-09-06-measuring-instrument-evidence.json) contains the full
artifact maps, complete ABI-entry census, complete declared-family audit, station
receipts, and CI job disposition. Raw logs and the preserved defective cache remain
in `/Users/deniskopylov/polisyos/.worktrees/measuring-instrument/policy-engine/_build/measuring-instrument/`.
That ignored scratch directory is evidence storage for this local investigation;
its cache files and environments are not delivery artifacts.

## Stations and interpretation

Every relative product command below runs from the named `policy-engine` directory.
`clean` means `git status -sb` reports branch attachment and no tracked or untracked
changes; ignored virtual environments and tool caches are described separately.

| Station | Absolute product path | Commit and cleanliness | Provisioning |
| --- | --- | --- | --- |
| I, forensic only | `/Users/deniskopylov/polisyos/.worktrees/integration/policy-engine` | `0373364448f766ecba871f3abae23a2b563e63ac`; clean `main`, ahead 366 | Existing `.venv`, Python 3.14.0, Pydantic 2.12.5. No executor sync or venv replacement. |
| R, repair | `/Users/deniskopylov/polisyos/.worktrees/measuring-instrument/policy-engine` | Began clean at slice base; precommit tests ran with owned source/test/plan changes; subsequent CI probes clean at `f69400b1f00e58d241aa68acf46c5af269d17057` | Separate `.venv`, `uv 0.10.6 sync --frozen --extra ml --extra dev --extra test --extra runtime`; own editable package restored after the guardrail incident below. `corepack pnpm install --frozen-lockfile` completed before later frontend results could be trusted. |
| A, independent proof | `/Users/deniskopylov/polisyos/.worktrees/measuring-station-a/policy-engine` | Clean before and after at `f69400b1f00e58d241aa68acf46c5af269d17057` | New local `.venv`, uv 0.9.21, Python 3.14.0, Pydantic 2.12.5; `uv sync --frozen --extra ml`. Original defective integration payload deliberately seeded under A's own cache key. |
| B, independent proof | `/Users/deniskopylov/polisyos/.worktrees/measuring-station-b/policy-engine` | Clean before and after at `f69400b1f00e58d241aa68acf46c5af269d17057` | Independently created local `.venv`, same pinned versions and sync command; initially empty schema cache. |
| BASE, gate replay | `/Users/deniskopylov/polisyos/.worktrees/measuring-base/policy-engine` | Clean before and after at slice base `0373364448f766ecba871f3abae23a2b563e63ac` | New local `.venv`, uv 0.9.21, Python 3.14.0, `uv sync --frozen --extra ml`. |

A, B, and BASE first attempted offline provisioning. Missing cached distributions
were then obtained with ordinary online sync. They share the package download cache,
but have independent virtual environments, editable installations, and schema caches.
Their uv executable is `/Users/deniskopylov/.local/bin/uv`.

The original workspace at `/Users/deniskopylov/polisyos` remained on
`codex/debt-n-register-parser-repair`, `9e23a5669334f26253fdd2490048ef92154dbb8c`.
No product measurements below come from that branch. I is used only to explain and
remove the observed station defect, never to decide a product closure.

## `gen-schema-disagrees-between-worktrees-on-identical-trees`

Disposition: local repair and closure evidence ready for architect transcription.
Owner: `team-polisyos` with runtime/quality. Main still needs the source repair
integrated; changing one live cache file is not the enduring repair.

### Cause: persisted schema payload bound only to its defining file

At the slice base, `gen_schema._entry_cache_key()` binds the ABI entry, defining
source file/hash and Pydantic version. `_load_or_generate_entry_payload()` accepts
the cached result when `schema_payload` is a dictionary, before generating the live
model schema. An imported nested model can change while that defining file stays
identical. Fresh worktrees use another absolute source path in the cache key and
therefore miss the old entry.

Before any probe could rewrite I's cache, the executor copied every file in its
`_cache/polisyos-tools/cache/diagnostics.gen_schema` directory and recorded each
filename, SHA-256, size, and mtime. The complete preserved set is 103 files,
1,156,114 bytes, in `integration-cache-before/`; `integration_cache_before` in the
evidence JSON records the denominator.

The forensic census resolves every entry returned by `select_abi_entries`, reads
its keyed cache file, and compares that payload with
`_load_or_generate_entry_payload(..., cache_root=None)`. On I at the clean slice
base, all 101 selected ABI entries had cached payloads. The complete differing-entry
set was exactly `{context_adaptive_parameter_bundle}`. The evidence JSON preserves
all 101 identities and cached/live hashes; the raw census preserves both payloads.

The defective entry is
`b6893c5c0346889670a2e119f5ed36a2271f4ef64a84e9b656d8e7e3f34a87e3.json`.
Its original file SHA-256 is
`93b962fc0a23459c987318aa6a4dd48b5f0c882d4d7811346bb6b08369d578cf`.
Its full schema hash is
`337d957a126146c874b31e78d5bc58a3e5014bfdede95bd1d1fd5b9d5a3a3172`;
the recomputed hash is
`e1fe6414d57ca8e7325119af5f1a332256f524788e63a67ded870a700ba61787`.

The cached schema lacks `$defs/EvidenceStrengthOrigin` and
`$defs/EvidenceParameter/properties/evidence_strength_origin`. Comparing the
preserved payload with `git show <ref>:policy-engine/schemas/snapshots/ir/context_adaptive_parameter_bundle.schema.json`
established that it equals the premerge `37c20aaa5` snapshot. The defining file,
`src/polisyos/ir/analytics/parameters.py`, has SHA-256
`8cbd6a14e9d68983be381e1c47eb75b435cc99d98b1e3505e490763bad16c539`
at `37c20aaa5`, `8a40ad646`, and the slice base. These are Git-object comparisons
from R, not claims that old pytest runs ran on main.

This explains both directions of error: before regeneration, a stale cached
expectation can agree with a stale snapshot and omit it from the finding set;
after another station regenerates, that same cached expectation falsely disputes
the corrected snapshot and manifest. The historical premerge four-artifact set
in the task was not rerun here. The cache-to-premerge equality and the behavioral
regressions establish the mechanism behind the reported undercount.

### Controlled reproduction, then elimination

On I, same clean slice-base tree and interpreter:

```sh
.venv/bin/python -B tools/quality/diagnostics/gen_schema.py --check
.venv/bin/python -B tools/quality/diagnostics/gen_schema.py --check --cache-dir /Users/deniskopylov/polisyos/.worktrees/measuring-instrument/policy-engine/_build/measuring-instrument/integration-control-cache
```

The default-cache finding set was exactly:

```text
schemas/snapshots/ir/context_adaptive_parameter_bundle.schema.json
schemas/snapshots/ir/_manifest.json
```

The empty-cache control finding set was `[]`. Exit codes were 1 and 0 respectively.
The original cache's added, removed, and changed file sets remained empty throughout
these controls. This established the cause before changing the defective cache.

After preserving the evidence and implementing the source repair, the executor
recomputed and replaced only that one cache entry in I. The replacement file hash
is `ef32784918383ffa45af12cc97ad13dfd0282b990cc0f65b286e7d2ab5700ecd`.
The original command then returned an empty finding set. The final complete cache
comparison has no added or removed files and exactly that one changed filename.
I's source, branch, and virtual environment remain unchanged. This is forensic
corroboration; the deciding repair evidence is A/B below.

### Source repair and regression verification

Commit `f69400b1f00e58d241aa68acf46c5af269d17057` changes the existing generator
to recompute the full runtime schema, version, and hashes before consulting a
persisted payload. Cache equality may avoid a write; it cannot establish the
expected schema. No committed schema bytes were regenerated.

The same class existed in the optional `--changed-only` and
`--skip-if-unchanged` early returns: neither defining-source membership nor a saved
baseline proves that nested schemas and current output bytes agree. Both flags
remain accepted but perform full generation/checking. Invalid Git scope still
fails. The release fragment records the additional full-run cost.

Behavioral subprocess regressions edit a nested model in another real source file,
then exercise warm/cold caches, regeneration elsewhere, generation with each hint,
and corruption of snapshots, manifests, and both generated references. They use
real schema generation and reference rendering with a bounded catalog fixture.
The new regression file failed before the source repair. After the repair, this
targeted command passed in R at the slice-base HEAD plus the owned diff subsequently
committed as `f69400b1f00e58d241aa68acf46c5af269d17057`:

```sh
.venv/bin/python -m pytest -q tests/repo_quality/tools/test_schema_station_independence.py tests/repo_quality/tools/test_phase5_tooling.py tests/repo_quality/tools/test_diagnostics_phase3.py
```

Ruff check passed for the changed Python files, format check passed for the generator
and new regression file, and `git diff --check` passed. No directory-wide pytest was
run. The requested independent code review did not execute because its agent service
returned an out-of-credits error; it is not claimed as a completed review. Source
and test review by the executor is complete. Architecture guardrails have no valid
passing receipt; the environment incident is recorded below.

### Independent worktree proof by complete sets

A and B both ran the declared family command at source repair commit
`f69400b1f00e58d241aa68acf46c5af269d17057`, tree
`d2324ef51a9dfda724163e5c08e8d5483075c8c8`:

```sh
/Users/deniskopylov/.local/bin/uv run --extra ml polisyos-tools diagnostics gen-schema --check
```

A deliberately started with the original bad payload under A's valid cache key;
B started with an empty schema cache. Both remained clean. The command returned
empty finding sets in both stations (exit 0; A 107.316 seconds, B 167.987 seconds).
These concurrent first-run durations describe these stations, not a performance
benchmark.

The scratch observer `full_check_receipt.py` invokes `gen_schema.main(['--check'])`
and wraps the real comparison/rendering functions while retaining their execution.
It records every checked artifact's expected and current hash. The complete map
contains 101 model snapshots, two manifests, and two generated references: 105 paths.
Manifest comparison excludes only `generated_at`, following the existing comparator;
schema and reference comparisons use exact text. This task did not weaken that rule.

```text
A-only artifact paths: []
B-only artifact paths: []
different artifact records: []
A finding set: []
B finding set: []
```

Both full maps are committed in the evidence JSON, and each expected hash equals
its current hash. SHA-256 of either map's sorted, compact JSON is
`01fdf3eb949131444548af0b1645e8c692579c9c8ee49df3459cd6a4d436ea30`.
The observer is supplemental to the unwrapped declared command receipts, not a
replacement check. Its raw source hash is included for audit.
The observer was run with each station's `.venv/bin/python`, the absolute scratch
`full_check_receipt.py` path, the corresponding absolute `station-a-artifacts.json`
or `station-b-artifacts.json` output path, and the station provisioning description
as its second argument. Its CWD was A or B respectively; it explicitly prepends
that CWD to imports. The complete command arguments are recorded in the evidence.

### Generalization across declared families

Parsing every `[[family]]` in `architecture/generated_artifacts.toml` yields 61
tables, 37 with a nonempty `check_command`: the ABI family and 36 others. The
evidence JSON's `family_audit.families` lists every ID, owner, complete command,
resolved entrypoint set, missing target set, and source anchors. No family was
dropped for failing to have a callable target.

The source census read every tracked `.py` file under product `src/` and `tools/`
using the complete `git ls-files` set: 3,052 Python files. Persisted JSON-cache
reader hits are exactly `tools/lib/cache.py`, `gen_schema.py`, and
`tools/quality/lint/lint_imports.py`. The import linter caches per-file syntax/import
extraction bound to the complete file hash, then reevaluates global rules. It does
not reuse a derived nested model schema. Schema-payload hits in Fabric are explicit
contract registry data or live schema comparisons, not this station cache.

The other commands were traced through their CLI/shim entrypoints and data reads:
runtime OpenAPI/client generation uses a fresh app/schema and temporary outputs;
the frontend generator reads the committed OpenAPI input; configs and release
checks reread their declarations/files; GY validators use live builders, committed
content-bound evidence, or process-local caches. None consumes the defective
persisted ABI payload cache.

**Result: the other 36 declared check families were source-inspected for this cache
class; none was additionally affected by it.** This is not an all-family execution
or green claim. The missing S3 test target is a separate availability finding below.
Docs/workspace orchestration that invokes gen-schema benefits from the repair; it
does not constitute another declared family.

## `main-has-not-reached-ci-for-365-commits`

Disposition: **open**, pending architect push decision and reading the resulting
`abi.yml` run. Owner: architect with `team-polisyos`.

Read-only `git ls-remote origin refs/heads/main` returned
`784d020148c56e9bfb3a3631909ba11232210a9f`. At task entry, local main was the
slice base `0373364448f766ecba871f3abae23a2b563e63ac`, one documentation commit
past the supplied measurement. `git rev-list --count origin/main..main` from R
returned 366. The row ID remains unchanged; 365 is the historical measurement,
not today's result. The source repair descends directly from that main. The
documentation handback commit follows the source repair on the same branch.

The prior remote [ABI run 33331986325](https://github.com/DenisKopylov/polisyos/actions/runs/33331986325)
at `784d020148c56e9bfb3a3631909ba11232210a9f` completed with failure on
2026-08-30. The complete API response for that head contained 20 workflow runs;
the ABI run's complete six-job set was read, including failure logs. This is
evidence about the old remote commit only. API head queries returned no runs for
the slice-base main or the source repair. No new-work CI result exists to read yet.

| Complete old ABI job set | Read result | Disposition / expectation for the prepared candidate |
| --- | --- | --- |
| Fast PR / Python quality and unit | Failed in Setup Policy Engine Python; schema step skipped | Bootstrap `click` failure reproduced locally; proposed owner `team-devx`. Expect this setup failure again. After setup repair, local last-mile drift is a further known risk. |
| Fast PR / Docs quality | Failed in Setup Policy Engine Python | Same bootstrap finding. Later docs lifecycle findings reproduced locally, but earlier docs steps remain unmeasured. |
| Fast PR / Workflow governance | Actionlint SC2035 in `.github/workflows/release.yml:98`; summary upload then failed because its producing step did not run | Same actionlint finding reproduced with ShellCheck; proposed owner `team-release` with `team-devx`. Expect this failure again. |
| Fast PR / Dependency review | Skipped | PR-only; skipped on a main push. |
| Fast PR / ABI drift | Skipped | PR-only; skipped on a main push. The schema snapshot check is separately in Python quality. |
| Fast PR / Gate | Failed on failed dependencies | Aggregate consequence of the failures above; expect failure until they are resolved. |

The workflow still triggers on PRs and pushes to main. Pushing only the repair
branch without a PR would not exercise its push trigger. The architect must choose
ordinary integration/publication onto main (or a PR for intermediate evidence);
this executor has not merged or pushed. A PR run alone does not satisfy the row's
requirement that origin/main contain the work.

The exact candidate for that decision is `codex/measuring-instrument` including
this documentation commit; the handback response pins its final SHA after reading
the branch back. Its source change is the separately pinned repair above. CI will
see the accumulated main work, this generator/test repair, its release fragment,
the plan, and this journal/evidence. It will see no workflow repair. Expect a red
ABI workflow for the reproduced bootstrap and actionlint reasons; local schema
agreement does not predict the outcome of unrun jobs or the broad CI pytest suite.

## `gen-schema-check-red-on-main`

Disposition: **open**. Owner: `team-polisyos`.

The supplied clean-worktree merge measurement establishes the symptom's repair.
The fresh R slice-base check also returned an empty finding set before the source
repair; its receipt records a clean starting tree and owned untracked plan/test
files present by the end. A/B establish the instrument repair on their exact source
commit. None of these local results satisfies the real-CI witness conjunct.

The witness commit/CI/revert sequence waits. First integrate/push under the
architect's decision and read that exact SHA's ABI run. Repair or assign each
failure. Once the schema step actually executes, create an isolated witness commit
that changes a selected snapshotted model without regenerating, read the real ABI
run's schema failure and complete artifact set, then revert the witness with an
ordinary new commit and read the follow-up result. An unrelated setup failure is
not evidence that CI caught the witness. No witness has been created or advertised
as caught locally in this handback.

## Additional findings and proposed owners

These are journal findings for architect transcription, **not register edits**.
Each is a new class relative to the persisted schema-payload defect (P40).

| Proposed finding | Evidence and boundary | Proposed owner / remaining work |
| --- | --- | --- |
| `generated-freshness-probe-rebinds-caller-venv` | R's architecture guardrail symlinks the caller `.venv` into a temporary copied source, then runs `uv run` there. The editable `.pth` was rebound to the temporary source and left dangling after cleanup. The worktree snapshot does not inspect the symlink target's site-packages. | `team-architecture` with `team-devx`; give isolated probes an isolated editable installation and verify the caller environment remains bound to its own source. Full architecture guardrails remain `verification_missing`. |
| `generated-artifact-s3-check-target-missing` | Family `policy-design-case-layer2-s3-governed-capability-rows` declares three exact pytest files; its complete missing-target set is `{tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py}` at the source commit. The other two targets exist. | `team-runtime-quality`; reconcile the declared behavioral check with its actual owner/target. Availability is unproved; no same-cache defect was found. |
| `ci-bootstrap-requires-click-before-sync` | Old remote ABI Python/docs jobs fail at `tools/cli.py:12`. At clean R/source commit, a new dependency-free Python 3.14.0 venv running the action's module-bootstrap arguments fails identically with `ModuleNotFoundError: click`, before sync. | `team-devx`; repair bootstrap ordering without weakening checks, then verify clean-runner setup and read the new CI jobs. |
| `workflow-governance-release-glob-shellcheck` | Old CI and clean R/source commit actionlint both report SC2035 for the release checksum glob. Local actionlint 1.7.12 plus ShellCheck 0.11.0 emits exactly this one finding. The first local run without ShellCheck was a parity nonreceipt despite exit 0. | `team-release` with `team-devx`; make the checksum invocation handle filenames beginning with dashes. Summary-upload failure belongs with the stopped producer step. |
| `last-mile-inventory-baseline-drift-at-ci-candidate` | Exact same local check argv replayed at clean BASE and clean R/source commit. Both dispute `architecture/baselines/repository_best_in_class_last_mile/inventory.json`; their complete recomputed JSON reports and finding-path sets are identical. Full baseline/current set differences are in the evidence JSON. | `team-devx` with the task executor; reconcile the measured inventory and baseline after CI. Inherited attribution is `not_established`: a zero intersection with the complete input denominator has not been proved. |
| `last-mile-inventory-treats-evidence-paths-as-live-references` | R at the source commit plus the staged handback adds exactly the two new journal/evidence paths to LM-025. `_collect_frontend_mentions()` matches `frontend/` anywhere in text, including the valid `docs/reference/frontend/atlas-v15-adjudication.md` evidence path. It does not resolve a retired application reference or distinguish evidence. This additional delta belongs to the handback, not the base. | `team-devx` with `team-frontend` and the task executor; distinguish actual stale references from evidence/path substrings. Keep the baseline disagreement visible until the property is adjudicated and repaired. No gate change or evidence-obscuring rewrite was attempted. |
| `docs-lifecycle-live-references-and-ledger-metadata` | Same command on clean BASE and R/source commit emits the same complete seven finding identities below. No base-only or repair-only finding. | `team-architecture` with the task executor; resolve ledger metadata and remaining live/unmarked evidence references. Do not reopen the already-closed quotation-rule row merely because another journal lacks its explicit evidence markers. Inherited attribution remains `not_established` under P41. |

The complete docs finding identity set is:

```text
active_plan_metadata | docs/plans/active/LEDGER.md | missing status
active_plan_metadata | docs/plans/active/LEDGER.md | missing owner
removed_stub_reference | architecture/atlas_surfaces/atlas-v15-adoption-ledger.json
removed_stub_reference | architecture/atlas_surfaces/atlas-v15-archive-map.json
removed_stub_reference | docs/reference/frontend/atlas-v15-adjudication.md
removed_stub_reference | docs/research/policy-operations/audits/pao-r0/pao-r0-test-and-fixture-verification.md
removed_stub_reference | docs/superpowers/journals/2026-09-02-gy-pr1a-data-only-promotion.md
```

Local gate commands, with argv/cwd/provisioning and raw output in the evidence JSON:

```sh
.venv/bin/python tools/quality/validation/repository_last_mile_inventory.py --json-output _build/measuring-instrument/last-mile-live.json --check
.venv/bin/python -m tools.cli validation check-docs-lifecycle
.venv/bin/python tools/quality/lint/lint_imports.py --policy architecture/imports/policy.toml --exceptions architecture/imports/exceptions.toml
.venv/bin/python tools/quality/validation/generate_adr_index.py --check
```

The last two passed on clean R/source commit. These local invocations use the
already-provisioned interpreter; they are not advertised as fresh CI bootstrap.
The last-mile output location differs from CI only in the ignored scratch path.
An initial receipt wrapper accidentally reused its inventory-output filename;
that scratch result was discarded and the command rerun with distinct live-output
and receipt filenames in both R and BASE. The committed comparison uses those
separate, successfully read-back files.

After staging this handback in R (HEAD still the source repair, staged journal,
evidence JSON, and plan update), docs lifecycle was replayed with the same argv:
added/removed finding sets both `[]`. The inventory check was replayed with output
`_build/measuring-instrument/last-mile-handback-live.json`. Its complete finding-set
delta relative to the clean source commit is:

```text
LM-025 added:
docs/superpowers/journals/2026-09-06-measuring-instrument-evidence.json
docs/superpowers/journals/2026-09-06-measuring-instrument.md
All other finding path sets unchanged; no removals.
```

The handback therefore must not inherit the source commit's identical-inventory
claim. These two new paths and the associated count/summary changes are this
documentation change's contribution to the red. They are preserved and assigned
in the evidence-path finding above, rather than removed from the evidence or
silently absorbed into a regenerated baseline.

### Guardrail incident: preserve, explain, restore only the task environment

The command `.venv/bin/python -m tools.cli architecture guardrails check` launched
in R at the slice-base HEAD with the owned source/test/plan diff, before frontend
dependencies were installed. Missing frontend tools and a missing `python` on the
child PATH made that gate run a provisioning nonreceipt; its reported product
findings are not promoted here.

Separately, the run changed R's
`.venv/lib/python3.14/site-packages/_editable_impl_policy_engine.pth` to a deleted
temporary checkout. The preserved damaged file hash is
`f0ec770b225ca33fc0c375423eeddd6d9f44a94416b2a4bcf8d82c3737120660`.
Its receipt's SHA/status was captured after the source commit; it must not be read
as saying the original gate ran clean at that commit. A later no-sync invocation
failed to import `tools`, matching the dangling path.

Source trace: `tools/devx/architecture/guardrails.py`,
`_copy_isolated_probe_source` and `_run_required_generated_artifact_checks`, plus
the worktree snapshot routines. The former symlinks `.venv`; the latter launches
the `uv run` output probe from the copied source. The smallest missing capability
is an isolation-local editable environment for that temporary source. The present
implementation does not provide it. This is distinct from accepting stale schema
payloads and has not been patched under the schema repair commit.

After preserving the damaged `.pth` bytes and explaining the path, ordinary
`uv sync --offline --frozen --extra ml --extra dev --extra test --extra runtime --reinstall-package policy-engine`
restored R's editable installation to its own product root and `src/`; its read-back
SHA-256 is `1def06ae588b25aaebf03a2d6810f7c6f21fb4df5eee1b6bc639b7dcd1473b5b`.
No venv was deleted. The full mutating guardrail was not rerun. I never ran that
guardrail during this task.

## Pattern and handback limits

The failure/repair register was opened before design and again before closeout.
P29/P32/P38: expected schema content is recomputed, not inferred from a source-file
hash or exit status. P31/P33: dependency changes and output corruption cover both
false red and false green, including optional early returns. P35: complete ABI,
artifact, family, and Python-source denominators are recorded. P37: current payload
facts are `recomputed`; A/B agreement is `independently_reconciled`; real CI for the
new work and the witness are `not_established`. P40: the shared-venv, missing-target,
bootstrap, workflow, inventory, and documentation findings are separately owned
classes. P41: matching base reds are recorded without claiming an unproved empty
input intersection or exporting ownership as inherited debt.

No current CI job failed in an unexplained, locally nonreproducing way: the only
read failing CI jobs are the old remote run's reproduced bootstrap/actionlint
failures and their aggregate/upload consequences. No check was weakened. Remaining
work is explicit: architect push decision, exact new-run readback and triage, the
real CI witness/revert sequence, and owner disposition of the additional findings.
