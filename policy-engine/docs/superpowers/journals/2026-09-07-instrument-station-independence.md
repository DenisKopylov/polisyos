# Instrument station independence — repairs and local handback

Date: 2026-09-07. Owner: instrument-station-independence lane.

## Current dispositions after the authorized continuation

This table replaces the initial blocked dispositions; the original handback remains below as
history. All eight owned rows are dispositioned: five repaired, three repaired-with-a-limit.
The verified mechanism candidate is `6fa919b744c945f686a42ab746bbb3f5dbaa9b79`; the final
follow-up changes only this journal. This is a local push-boundary handback, not a green claim
for the entire architecture suite.

| Owned row | Current disposition | Result and remaining boundary |
| --- | --- | --- |
| `last-mile-unreadable-input-becomes-an-empty-file` | repaired | Strict input reads and complete tracked census report missing, dangling, undecodable and invalid input as ambiguous; committed removal probes protect the behavior. |
| `last-mile-inventory-baseline-drift-at-ci-candidate` | repaired | Default baseline binds to the selected root; every collector uses one tracked census; enumerated baseline reconciliation and both complete station artifacts agree. Historical inherited attribution stays `not_established`. |
| `last-mile-inventory-treats-evidence-paths-as-live-references` | repaired | Shared role projection excludes documentary evidence and retains live references, including live ZIP containers. Both station inventories agree; live negative controls remain red. |
| `docs-lifecycle-live-references-and-ledger-metadata` | repaired | Tracked reference/ADR enumeration and aggregate-ledger typing pass on both stations with ignored reference debris. The separate expired docs-freshness exception remains separately owned. |
| `shared-git-hook-hardcodes-one-worktree-path` | repaired-with-a-limit | Producer and all recognized generated hooks are checkout-relative and stable across installs. An older checkout can still run its old producer until the repair is integrated there. |
| `shared-hook-binds-its-config-at-install-time-and-validates-nothing` | repaired-with-a-limit | Runtime config/binary binding fails closed; real violating and autofixed commits are refused; stale generated entrypoints are normalized. Older checkout/config rollout remains an architect responsibility. |
| `structure-gate-cli-defaults-to-report-only` | repaired | Documented default is fail-closed and agrees with explicit CI mode on both stations, including the three ignored directories. Tracked negative controls remain red. |
| `generated-freshness-probe-rebinds-caller-venv` | repaired-with-a-limit | Both real consumers preserve caller bindings; the required runner provisions a private interpreter/cache. Final full guardrail still reports the explicit runtime/deep-import/generated-artifact findings below, whose reconciliation is outside this row's edit boundary. |

No owned row is left not-started or blocked without a disposition. Neither the debt register
nor ledger was authored or executed by this lane. The final receipt below distinguishes the
recomputed successes from the remaining reds and their attribution.

## Initial handback: outcome and stopping decision (superseded below)

Stopped under the user's explicit rule: **a repair needs a file outside the allowed list**.
No measuring-instrument repair is claimed. This journal is the only intended tracked change.
The user explicitly required this journal in addition to the allowed mechanism paths.

The decisive dependency is
`policy-engine/apps/runtime-dashboard/package.json:76`:

```json
"prepare": "LEFTHOOK_CONFIG=policy-engine/apps/runtime-dashboard/lefthook.yml lefthook install --force"
```

It regenerates the shared hooks. Editing a generated hook alone would leave the installing
producer able to overwrite the repair on a later install. A durable repair must change the
producer/configuration or establish a per-worktree hook policy; the dashboard package/config
and git configuration are outside this lane's allowed files. The architect and dashboard
toolchain owner must allocate that change. No hook was edited and no install was run.

The shared-hook investigation established this boundary while the other read-only investigations
were underway. They stopped; an already-running inventory command was allowed to finish for
its receipt. Subsequent work only completed measurement receipts and this handback.

| Owned row | Disposition | Reason / remaining work |
| --- | --- | --- |
| `structure-gate-cli-defaults-to-report-only` | blocked-and-why | Both defects reproduced; global scope stop before repair. Needs committed-input semantics and truthful default exit together. |
| `generated-freshness-probe-rebinds-caller-venv` | blocked-and-why | Sharing mechanism traced; global scope stop before isolation repair or hazardous verification. |
| `last-mile-inventory-baseline-drift-at-ci-candidate` | blocked-and-why | Drift observed on one station; global scope stop before reconciliation and paired replay. Inherited attribution remains `not_established`. |
| `last-mile-inventory-treats-evidence-paths-as-live-references` | blocked-and-why | Broad text matcher identified; global scope stop before semantic retyping or injected-evidence probe. Inherited attribution remains `not_established`. |
| `docs-lifecycle-live-references-and-ledger-metadata` | blocked-and-why | Complete command output recorded; global scope stop before role-aware classification and paired replay. Inherited attribution remains `not_established`. |
| `shared-git-hook-hardcodes-one-worktree-path` | blocked-and-why | Durable repair needs an excluded install producer/configuration; this triggered the stop. |

No row is repaired or repaired-with-a-limit. All owned rows received read-only investigation.

## Change contract and pattern pass

Property: an instrument's verdict must be a property of the commit rather than the station;
a tool must not report success while holding findings. The initial execution order was to
reproduce the structure disagreement, investigate inventory/docs and freshness independently,
identify the shared hook's producer, then repair only within tools/baselines/hooks, review,
and verify with focused tests and recomputed gates. The producer investigation triggered the
stop before implementation. No general tooling refactor or baseline refresh was attempted.

Read `CONTRIBUTING.md`, repository `AGENTS.md`, the six owned debt rows, and the
failure/repair register. Relevant patterns: P29 (behavioral evidence), P31 (repair the producer
class), P35 (complete denominators), P37/P38 (truthful predicates rather than proxies), and
P41 (measured red provenance). Re-read the relevant register entries at handback.

Observed proxy divergences:

- Structure checks filesystem existence even for ignored untracked state; identical commits
  differ when a benchmark or tool has run locally. Its default exit then conceals the findings.
- Freshness snapshots a symlink target string and git-visible files, leaving editable binding
  bytes outside its measurement despite sharing the actual environment.
- Inventory/docs reference matchers interpret historical/evidence text as live references.
- A generated shared hook is an output, so editing it does not close its installing producer.

Target pattern, unimplemented: derive structural inputs from the governed source set, classify
reference roles before checking liveness, isolate generator environments, and fix hook generation
at its owner. Relevant missing capability labels at stop are `verification_missing` and
`semantic_test_missing` for the proposed repairs. No new capability is asserted.

Decisive predicates here are `recomputed` for git attachment/tree IDs, structure outputs,
path membership, and hook bytes. Durable repair closure and inherited-red attribution are
`not_established`. No green is inferred from those unknowns.

Contended resource: the shared hook directory. Dependency installation was deliberately not
started because it would mutate that resource. Hazardous freshness execution was also not
started. No pytest directory run, GitHub integration, push, rebase, reset, or stash was used.

## Stations and artifact identity

Setup used ordinary git:

```sh
git worktree add /Users/deniskopylov/polisyos/.worktrees/instruments -b codex/instrument-station-independence main
git worktree add --detach /Users/deniskopylov/polisyos/.worktrees/instruments-base edc104849
```

- Station A: `/Users/deniskopylov/polisyos/.worktrees/instruments`, attached to
  `codex/instrument-station-independence`.
- Station B: `/Users/deniskopylov/polisyos/.worktrees/instruments-base`, detached measurement
  checkout. No commit was made there.
- Measurement base, predating this lane's journal:
  `edc104849a9830dd5249390aa5380bd49836490c`.
- Both measured tree IDs: `c206bc2f1163a6c7543f88a1b74c54bfa5c7ad94`.
- Complete `git ls-files -z` denominator at both stations: **10,565 tracked paths**, all
  tracked file types over the entire repository, no extension filter. SHA-256 of that complete
  NUL-delimited path list at both stations:
  `0462dff2e76c1d44dad7c84fe95b1b371241075e8b909d11f8410d597253da90`.
- Both had empty tracked diffs and clean porcelain status before journal creation.
- Both used `/opt/homebrew/opt/python@3.14/bin/python3.14`, Python 3.14.0, with neither
  `policy-engine/.venv` nor `policy-engine/node_modules` present. No Python or Node dependencies
  were provisioned. The structure command uses the standard library on this Python.
- Station A was deliberately given empty `policy-engine/.benchmarks`,
  `policy-engine/.polisyos-tools`, and `policy-engine/.tmp` directories. Station B had none.
  For each existing path on A, `git check-ignore -q` exited 0 and enumeration of the complete
  tracked path set found no path equal to it or under it.

The structure comparison therefore has identical code, interpreter and dependency provisioning;
its declared differing condition is ignored local directory state. This does not establish
comparability for tools requiring installed dependencies. No TypeScript scanner was trusted.

Every gate below was the only command in its invocation. Exit codes came from the execution
tool's process result, not a trailing echo. Valid structure runs all completed without traceback.

One attempted B run started before `git worktree add` had finished and exited 2 because the
tool file was not yet present. It is **ambiguous / invalid measurement**, not an empty finding
set. The worktree process was then awaited to exit 0, and both B gate modes below were rerun
successfully. That incomplete-checkout attempt is excluded from the comparison.

## Structure gate

Source artifact: `tools/quality/validation/repository_structure_phase0.py`, plus its entire
runtime inventory and rule files at the pinned base. The command scans product source and
test topology, named workspace/product cache/build locations, frontend workspaces, pyproject,
and architecture layout/shim/name/exception rules. The tracked repository denominator is above;
the deliberately varied filesystem inputs are enumerated explicitly.

Root cause: `collect_inventory` records existing cache/build paths and their ignored flag;
`gate_cache_dir` and `gate_build_output` still emit findings for those ignored paths.
`_parse_args` defaults to `report-only`, and `main` returns nonzero only in `fail-closed` mode.

From each station's `policy-engine` directory:

| Sole command | A exit | B exit |
| --- | --- | --- |
| `python3 tools/quality/validation/repository_structure_phase0.py gate --json` | 0 | 0 |
| `python3 tools/quality/validation/repository_structure_phase0.py gate --mode fail-closed --json` | 1 | 0 |

Complete A finding set, identical in both modes:

```json
[
  {
    "gate": "cache_dir_gate",
    "ignored": true,
    "message": "Legacy cache/tool state is outside canonical _cache/ umbrella.",
    "name": ".benchmarks",
    "path": "policy-engine/.benchmarks",
    "severity": "warning"
  },
  {
    "gate": "cache_dir_gate",
    "ignored": true,
    "message": "Legacy cache/tool state is outside canonical _cache/ umbrella.",
    "name": ".polisyos-tools",
    "path": "policy-engine/.polisyos-tools",
    "severity": "warning"
  },
  {
    "gate": "build_output_gate",
    "ignored": true,
    "message": "Generated/build output is outside canonical _build/ umbrella.",
    "path": "policy-engine/.tmp",
    "severity": "warning"
  }
]
```

Complete B finding set, identical in both modes:

```json
[]
```

Identity-set difference A minus B is exactly the three entries above; B minus A is empty.
This is the entire output finding denominator for these commands, not sampled findings.
The default's successful exit with A's findings and the fail-closed station disagreement are
both reproduced. No repair was made. Remaining acceptance: implement committed-input semantics
and truthful default together, repeat this comparison, and prove a genuinely governed finding
still causes the documented hand command to fail.

## Generated freshness environment

Read-only artifacts on A: `tools/devx/architecture/guardrails.py`,
`tools/quality/validation/check_trust_claim_posture.py`,
`architecture/generated_artifacts.toml`, and existing focused architecture/trust tests.
No full guardrail ran, and no `.pth` preservation result is claimed.

`guardrails.py:_copy_isolated_probe_source` excludes `.venv` from copying and then symlinks
the caller's `.venv` into the temporary source. Required generators execute there with inherited
environment. A `uv run` generator can therefore resync the shared editable installation to the
temporary source. `_path_content_state` snapshots the symlink target string, and
`_snapshot_git_visible_worktree` excludes ignored environment contents. Cleanup removes the
temporary source. `check_trust_claim_posture.py` is a second consumer of the copy helper and
expects its linked Python environment; a repair must account for both consumers.

Complete enumeration of the manifest's **61 family entries** identified these required
freshness families: `runtime-openapi-snapshot`, `runtime-api-client`,
`runtime-dashboard-api-types`, and `trust-claim-posture-register`. This is a TOML declaration
census, not successful generator execution.

Possible direction, not a validated design: remove environment sharing, isolate uv environments
from inherited project/environment redirection, preserve source-bound imports for plain Python
generators, and avoid creating an environment inside the source snapshot whose output-escape
check would flag it. No code changed.

Remaining acceptance: provision dedicated throwaway real worktrees identically; enumerate and
capture every caller `.pth` file's bytes; run the full guardrail as a sole command; re-read the
complete `.pth` set; prove the caller still imports its own source without resync; exercise both
copy-helper consumers. Existing focused test owners are under `tests/repo_quality/tools/`,
outside this lane's edit list. No hazardous run should use an environment needed for work.

## Last-mile inventory: baseline drift

Station A only. Sole valid gate command from `policy-engine`:

```sh
python3 -m tools.quality.validation.repository_last_mile_inventory --json-output _build/.tmp/instruments-investigation/last-mile-base.json --check
```

Exit 1, no traceback. Complete gate finding identity set:

```text
baseline drift: architecture/baselines/repository_best_in_class_last_mile/inventory.json
```

The earlier direct-script invocation exited 1 with `ModuleNotFoundError: No module named
'tools'`; it is an invalid measurement, not a finding set. The module invocation above is the
usable receipt. No matched second-station run or frontend provisioning occurred, so inventory
semantic adequacy and cross-station equivalence remain **ambiguous / not_established**.

Artifact pair inspected in full: the committed inventory baseline and the newly emitted JSON.
The latter remains in A's ignored build scratch, SHA-256
`06d4d20b26ae5debbfc41c477f591e14c6b0f79370f65f6e2737f18515a73c6f`.
It is a local diagnostic output, not a committed replacement baseline. Its complete gate
finding set is embedded above so handback does not depend on scratch retention.

The comparison traversed all **26 inventory finding rows** in each JSON artifact. Changed
locations in the serialized artifacts were:

```text
/findings/0/metadata/by_package/common
/findings/10/count
/findings/10/path
/findings/10/paths
/findings/22/count
/findings/22/paths
/findings/24/count
/findings/24/paths
/scientist_parallel_implementations/families/0/current_locations
/summary/path_count
```

No baseline was refreshed. Remaining work: provision comparison stations identically, enumerate
the instrument's complete inputs, reconcile or retype the disputed entries, and compare complete
finding identities. **Inherited attribution remains `not_established`**: this run did not perform
the required paired replay plus zero intersection proof against the complete input denominator.

## Last-mile inventory: evidence references

Read-only artifact on A: `repository_last_mile_inventory.py:_collect_frontend_mentions`.
It searches tracked text for broad `frontend/`, backticked `frontend`, or “frontend path”
matches without classifying evidence artifacts. The current inventory includes the prior
measuring-instrument journal/evidence paths in LM-025. This is a mechanism observation, not a
completed new-journal acceptance probe. No new evidence fixture or rule was introduced.

Measurement command, emitted artifact and complete gate finding set are the same as the baseline
section; these are two owned rows sharing one inventory run, not independent confirmations.
Complete repository input enumeration was not finished before the stop, and no matched replay
was made. **Inherited attribution remains `not_established`.** Remaining acceptance: classify
evidence by an authorized semantic rule, add a previously unseen evidence journal, prove no new
finding, and preserve detection of genuinely live obsolete references.

## Docs lifecycle

Station A only. Sole command: `python3 -m tools.quality.validation.check_docs_lifecycle`.
Exit 1, no traceback. Complete command-output denominator: these **seven finding identities**:

```text
active_plan_metadata | docs/plans/active/LEDGER.md | active plan missing `status` front matter.
active_plan_metadata | docs/plans/active/LEDGER.md | active plan missing `owner` front matter.
removed_stub_reference | architecture/atlas_surfaces/atlas-v15-adoption-ledger.json | stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
removed_stub_reference | architecture/atlas_surfaces/atlas-v15-archive-map.json | stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
removed_stub_reference | docs/reference/frontend/atlas-v15-adjudication.md | stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
removed_stub_reference | docs/research/policy-operations/audits/pao-r0/pao-r0-test-and-fixture-verification.md | stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
removed_stub_reference | docs/superpowers/journals/2026-09-02-gy-pr1a-data-only-promotion.md | stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
```

The full input file denominator was not enumerated before stop; this records complete observed
output, not a claim of station-independent coverage. `_iter_reference_scan_files` walks the
filesystem; local text can therefore participate. `check_active_plans` treats every direct
active-plan Markdown file as a plan, including the generated aggregate `LEDGER.md`.
`check_removed_stub_references` uses substring matching. The Atlas JSON/reference artifacts
retain immutable archive-member paths; the audit and journal describe historical findings.
`_reference_scan_text` has limited support for marked evidence blocks in journal Markdown,
which does not establish a general classification for these artifact roles.

No listed document, ledger, JSON or checker was edited. Remaining acceptance: role-aware
classification, negative live-reference checks, fully enumerated clean-checkout replay.
**Inherited attribution remains `not_established`**; no paired replay and complete-input
intersection proof was completed. The journal itself is in this check's potential input domain,
so its addition must not be treated as disjoint by assertion.

## Shared hooks

Read `git config --show-origin --get core.hooksPath` on A: configuration originates at
`/Users/deniskopylov/polisyos/.git/config` and names `/Users/deniskopylov/polisyos/.git/hooks`.
Complete inspected hook artifact denominator: `pre-commit` and `pre-push`, read in full.

Complete finding identities:

```text
pre-commit:19:absolute-binary-probe
pre-commit:21:absolute-binary-run
pre-push:19:absolute-binary-probe
pre-push:21:absolute-binary-run
```

All target:

```text
/Users/deniskopylov/polisyos/.worktrees/measuring-instrument/policy-engine/node_modules/.pnpm/lefthook-darwin-arm64@2.1.6/node_modules/lefthook-darwin-arm64/bin/lefthook
```

SHA-256 at investigation and coordinator readback:

```text
pre-commit  13c1f9ccbd0deb11211af4451a2e40ca5d3b5b0445e212fcebb397b57615a670
pre-push    66bc32245290ad15c6ff2b0e4d026d31de3c4ab18d1e905e6a485fc2c1600dfb
```

The complete base tracked-path census (10,565 paths, every tracked file type) finds only
`policy-engine/apps/runtime-dashboard/lefthook.yml` among conventional Lefthook configuration
filenames. The row's named `policy-engine/tests/repo_quality/tools/test_repo_hooks.py` is absent
from that same complete set, so its cited closure test cannot run at this base.

Read-only local installed Lefthook 2.1.6 help says `install --force` proceeds even with
`core.hooksPath` set; its package postinstall also invokes `install -f`. The repository's
explicit prepare producer is quoted at the start. No installation/overwrite experiment was
performed on the shared resource. No cross-station hook equivalence is claimed. Remaining
acceptance requires allocating the producer/config repair, testing regeneration after an
install, and verifying calling-worktree resolution and real failure propagation.

## Incidental proposals — not included as repairs

| Proposed row | Proposed owner | Evidence / proposed acceptance |
| --- | --- | --- |
| `last-mile-unreadable-input-becomes-empty` | runtime/quality | `_read_text` catches `OSError` and returns an empty string. Reproduce unreadability and require an explicit ambiguous/error outcome. No unreadable corpus count was inferred. |
| `last-mile-explicit-root-keeps-default-baseline-owner` | runtime/quality | Default baseline path is module-root absolute even when another `--repo-root` is supplied. Confirm through a two-station behavioral probe before adopting a repair. |
| `docs-lifecycle-untracked-text-enters-reference-denominator` | team-architecture | Reference scan walks filesystem rather than a committed-path set. Probe ignored/untracked text against a real detached checkout. |
| `shared-hook-closure-test-target-absent` | team-architecture / dashboard toolchain | Named test path is absent from the complete tracked base census. Allocate its owner or correct the executable acceptance target. |

These are proposals, not new authoritative debt-register entries. The architect transcribes
the owned-row dispositions and decides the out-of-scope allocation. DEBT-REGISTER.md, LEDGER.md,
`.github/**`, `architecture/generated_artifacts.toml`, `src/**`, other lanes and shared hooks
were not edited.

## Delivery

The worktree remains available at A on `codex/instrument-station-independence`; B remains a
detached diagnostic station at the base. The three deliberately created ignored directories
remain on A for reproduction. There is no environment to repair or resync.

The initial journal was committed as `108fde771` after verifying branch attachment and the
staged diff. The ordinary commit hook printed `No config files with names ["lefthook"
".lefthook" ".config/lefthook"] have been found` for A and still allowed the commit to exit 0.
That exit is a commit receipt, **not passing hook validation**. This delivery receipt is an
append-only follow-up; final branch contents must be read back before handback.

No push is authorized or performed. This is a scope-boundary handback, not a claim that the
six instrument debts are closed.

## Continuation: corrected stop rule and repair candidate

The user superseded the lane-wide file-boundary stop: a boundary or architect decision now
stops that row; the lane continues unless a shared systemic blocker or budget stops it.
Ordinary `git merge main` completed at `4102e5db8`, preserving both original journal commits.
The merge brought the architect's register/ledger/tool changes; this lane did not author or
run the debt-ledger tool. The additional dashboard package/config and `tests/repo_quality/**`
grants are explicit. Unit/integration tests, `.github/**`, source, and the generated-artifact
manifest remain excluded. The original freshness and evidence-reference rows remain in scope,
alongside the newly assigned unreadable-input and runtime-hook-config rows.

Repair strategy is extend-existing: strict inventory I/O and repository-relative defaults;
one documentary-reference classifier reused by inventory/docs; tracked input enumeration for
docs and its ADR producer; tracked structure namespace/rule reads and a fail-closed default;
one stable hook producer and runtime dispatcher; disposable uv generator environments.
These changes all serve the original commit-versus-station property.

The implementation candidate now has focused behavioral regression tests. Removal probes retain
the marker strings and test bodies while removing the runtime properties, and go red. This is
P29 evidence, not marker checking. P31/P40 review found that structure membership initially
missed catalog-peer existence, optional rule files and the mandatory pyproject read. These are
the SAME input-membership class. The repair was widened through the namespace predicates,
every TOML rule loader, and a shared required-text reader; this is not a new row or a whitelist
of the three originally reported directories.

Deliberate existing-test changes:

- `test_phase7_structure_gates_run_fail_closed_with_registered_exceptions`: before, passed
  `--mode fail-closed`; now uses the documented default command with the same zero-exit
  assertion. The default itself must enforce the rule. Ignored directories and tracked negative
  controls are covered by the new real-Git station tests.
- `test_quoted_evidence_is_not_a_live_reference`: before, wrote bare path text into `.json`
  fixtures; strict JSON reading correctly rejected that as malformed. The fixture now writes a
  valid JSON string containing the identical live obsolete path; Markdown bytes and all existing
  assertions remain unchanged. The exact test went red before the fixture correction, green
  afterward, and red again when documentary-reference classification was removed.
- No other existing assertions were relaxed. Initial new-fixture setup failures (an uncached
  build backend and Git removing an empty product directory) were corrected without weakening
  assertions. The editable-install fixture now uses a stdlib-only build backend and works offline.

CI interaction for the architect: `corepack pnpm install --frozen-lockfile` still triggers
dashboard prepare. Prepare now writes stable dispatchers rather than native absolute-path shims.
Dependency postinstall may temporarily write native shims; prepare restores the deterministic
dispatchers. Subsequent Git operations explicitly load the calling checkout's dashboard config,
execute its declared commands in dashboard context, and fail closed on missing config/binary.
This intentionally changes clean-CI Git-operation behavior. `.github/**` was not edited.

Local Python provisioning on A: `uv sync --offline --frozen --extra lint --extra test --extra
runtime` failed because pinned dependencies were absent from cache. The same frozen profile was
then provisioned online successfully; source/lockfiles were unchanged. Local shell tools were
Python 3.14.0, uv 0.10.6, Node 22.22.2, and corepack pnpm 10.33.2. No required environment was
used for a hazardous full freshness run. The new uv regression uses a disposable fixture caller.

One long combined architecture/trust importer invocation overlapped later review edits and was
terminated (exit 143, no output); it is a nonreceipt and contributes no finding set or pass.
The old-helper inventory scan terminated during classifier development is also a nonreceipt.
The frozen verification wave and final per-row dispositions will be appended after commit-based
station replay. Baseline drift is still visible at this checkpoint and will be reconciled from
the complete current inventory, not hidden by changing assertions.

### Candidate freeze receipt

Baseline reconciliation subsequently completed. The complete comparison traversed all 26
inventory rows: LM-001 adds existing `common/llm_json.py` metadata; LM-011 records the current
integration-test paths; LM-023 records the existing chronology helper; LM-025 records current
live-reference matches after documentary evidence classification. The Scientist family no
longer records the absent `scientist/methods/workflows` directory. Observation/review statuses
are unchanged. Canonical serialization was checked before writing, so this is a content delta,
not a JSON reformat. The scientist section and inventory baselines are the only baseline edits.
The recomputed `--check` now exits 0 with complete gate finding set `[]`; a corrupted
`summary.path_count` is rejected. The wrong-checkout default is a real bug, but does not by
itself explain historical drift when callers already used their own default checkout.

Structure has five new runtime removal probes, including the mandatory tracked configuration
boundary. Final focused structure-station tests: five passed. Its initial three removal
mutants, catalog/policy mutant, and required-reader mutant each produced assertion failures
with marker text retained. The generated freshness regression passed after comparing the
complete disposable caller `.pth` set and importing its own package again. Restoring the old
environment sharing at runtime made that same test fail while the new source markers remained.

The source/baseline candidate is being committed before provisioning the paired stations.
One existing phase3 importer assertion about a checkpoint security route failed in the broader
targeted run; the expected route is in excluded source. Its base replay and input-intersection
receipt are pending, and it is not being relabeled inherited or changed to obtain green.

### Append-only review correction and disposable candidate receipts

The first implementation candidate was committed as
`5c389e0397e83b1d482d679a3c8bcc6f6c87e9a7` (tree
`db32f9697fbade353d1f7cd8b90a6883ab169918`). Its commit still used the old installed hooks,
which printed the missing-config warning; that was not a hook-validation pass. Review then
found concrete deeper instances of the same input-binding classes. Corrections append to
that candidate rather than rewriting it.

- Inventory: a raw architecture glob admitted an untracked `architecture/local-station-gate.toml`.
  A complete AST census found 36 filesystem membership/enumeration sites across the original
  module's 52 functions, including the explicit baseline check. The correction freezes one
  NUL-delimited Git file census, derives directories from ancestors, and routes every collector
  and optional/default-baseline reader through it. Lexical path identities are retained.
  Explicitly supplied diagnostic baselines remain explicit inputs. The existing selected-root
  test now initializes Git and tracks its fixture baseline; all its assertions are unchanged.
  Seventeen selected inventory cases passed, and all seven newly added delta cases failed under
  runtime removal of their respective properties. The complete fixture artifact is in
  `_build/.tmp/instruments-inventory-probes/census-station-artifacts.json` (SHA-256
  `4c5b1e173160af731e45cd3c7b06271e86d630868dfedbf90afe04facced35d3`), with 12 tracked
  fixture files, 22 enumerated debris files, and a subsequent tracked positive control.
- Documentary references: the ZIP-member projection initially removed the live archive
  container as well. It now removes only the `::member` part. Both Markdown/JSON live-container
  tests failed before correction and under a marker-preserving removal; the complete shared-role
  test file now contains 23 parametrized cases. Its 23 cases plus the existing quoted-evidence
  case passed. Unknown roles and neighboring live fields remain live.
- Hooks: native Lefthook already hides unstaged changes; the staged-violation/unstaged-guard
  falsifier was refused, so the contrary review inference was retracted. A different, real
  escape remained: Prettier accepted staged `{"a":1}` after changing only working bytes to
  `{ "a": 1 }`. One native `fail_on_changes: always` predicate now refuses any pre-commit
  rewrite, with a staged formatted positive control. Changing only that setting to `never`
  made the behavioral test fail again.
- Hook inventory: the complete actual hook directory has 18 regular files. An undeclared,
  generated `prepare-commit-msg` also retained the old config lookup. The installer now
  discovers generated entrypoints by their own filename-bound native invocation or its
  dispatcher marker, and normalizes them alongside the declared hooks. No command was invented
  for the undeclared entrypoint. The actual three managed files are `pre-commit`, `pre-push`,
  and `prepare-commit-msg`; each is 655 bytes with SHA-256
  `45bfd5312ebc736ded74df4131cd00bb41abb0d4c0ddbc2473781d200ad64f66`. The other 15 of
  18 hook files, including `pre-commit.old`, were preserved. Discovery and replacement share
  one generated-ownership predicate so a custom hook merely naming a similar function cannot
  lose its backup.

Two disposable real Git worktrees were created with `git worktree add --detach` at that first
candidate: `/Users/deniskopylov/polisyos/.worktrees/instruments-check-a` and
`/Users/deniskopylov/polisyos/.worktrees/instruments-check-b`. Their product roots were each
provisioned with `uv sync --frozen --extra lint --extra test --extra runtime` after the identical
offline attempt failed on uncached pinned dependencies. Serial
`CI=true corepack pnpm install --frozen-lockfile` succeeded on both. Each had the same complete
166-distribution Python name/version set, three `@polisyos` workspace links, and identical
uv/pnpm lock hashes. Local provisioning manifests are at each product root's
`_build/.tmp/instruments-final/provision.json`. Native pnpm dependency build scripts, including
Lefthook's postinstall, were ignored by the existing lock policy; dashboard prepare did execute.
The producer was also tested after a real native forced install, so its overwrite repair does
not depend on that ignored-postinstall setting. No workflow file changed.

On disposable check-a only, the sole full command
`uv run polisyos-tools architecture guardrails check` finished with exit 1 and no traceback.
Its complete normalized finding identity set at the first candidate was:

```text
deep_import_baseline | drift
deep_import | polisyos.runtime.http.services.acquisition_admission_bundle -> polisyos.core.artifacts.manifest
deep_import | polisyos.runtime.http.services.acquisition_admission_bundle -> polisyos.core.artifacts.signing
deep_import | polisyos.runtime.http.services.acquisition_admission_bundle -> polisyos.core.artifacts.write_contract
generated_artifact | runtime-openapi-snapshot | output_probe_worktree_escape
generated_artifact | runtime-openapi-snapshot | schemas/runtime_api_v1.openapi.json
generated_artifact | runtime-api-client | output_probe_failed
generated_artifact | trust-claim-posture-register | apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json
```

The full log is
`/Users/deniskopylov/polisyos/.worktrees/instruments-check-a/policy-engine/_build/.tmp/instruments-final/guardrails.log`.
It exposed two errors in this lane's first repair: the API-client
generator requires `.venv/bin/python`, and uv's configured cache directory was written inside
the measured source copy. These were not relabeled inherited. The correction prepares a real
private environment and cache beside the source, links only that private environment at the
required source path before snapshots, and provisions the frozen project before any family
can run. The shared copy helper still never links the caller's environment. Preparation failure
is itself a finding. Runtime CAS writes and generated-byte drift are not suppressed.

On disposable check-b, the two specifically selected existing trust-consumer tests finished:
one passed and one failed in 284.01 seconds. The real generator executed; the failing test's
complete failure identity is `generated-family output differs from committed artifact:
apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json`. Its traceback is a failed
assertion path, not a clean measurement and not a cross-station finding-set comparison.
The generated output path is outside the edit grant. Inherited attribution is `not_established`.

Both disposable environments retained their complete two-file `.pth` sets after their respective
real consumers, with changed-identity sets `[]` on check-a and `[]` on check-b. Each set contains
`lib/python3.14/site-packages/_editable_impl_policy_engine.pth` (that station's product root,
newline, then its `src` root) and `lib/python3.14/site-packages/_virtualenv.pth`
(`import _virtualenv`). Direct `.venv/bin/python` imports, without resync, resolved to each
station's own `src/polisyos/__init__.py`. This compares environment preservation, not the two
different consumer finding sets. Before/after bytes are retained in the station receipts.

After the inventory census and ZIP correction, the sole inventory `--check` and sole docs
lifecycle command both exited 0 with complete gate finding sets `[]` and `[]`. The reconciled
inventory baseline required no further edit. The named inventory/docs/ADR/structure test wave
passed 84 of 85 collected cases in 30.93 seconds; the separately proven inherited docs-freshness
case was explicitly deselected. Final candidate/station replay follows below.

### Final paired candidate and recomputed validators

The corrected source candidate is `6fa919b744c945f686a42ab746bbb3f5dbaa9b79`, tree
`f9cb5e06814d6e32ea6f65b530266601c7c9c52a`. Its ordinary commit ran the actual repaired
hook: contrast and reduced-motion checks passed; Prettier reported the dashboard config
unchanged; ESLint had no matching staged source. There was no missing-config warning.
The delivery worktree was attached to `codex/instrument-station-independence` before commit
and clean afterward. Both owned detached diagnostic worktrees were clean before advancing
from the first candidate using `git merge --ff-only`; neither diagnostic advance created a
commit or rewrote history.

Station names for the final comparison:

- C2-A: `/Users/deniskopylov/polisyos/.worktrees/instruments-check-a/policy-engine`.
- C2-B: `/Users/deniskopylov/polisyos/.worktrees/instruments-check-b/policy-engine`.

Both are real detached worktrees at the full candidate SHA above. The same frozen offline
Python sync audited all 166 installed distributions on each. Serial
`CI=true corepack pnpm install --frozen-lockfile` reran prepare successfully on both. The
complete 18-file hook hash sets after each install are equal. All three managed hook bytes
remain identical to the dispatcher hash above. The entire Python name/version sets, Node
and pnpm versions, three workspace-link mappings, both lock hashes, and tracked path sets
were compared and agree. Station-specific editable source paths were recorded separately,
not normalized into an apparent equality of their literal `.pth` bytes.

C2-A contains `.benchmarks`, `.polisyos-tools`, `.tmp`, and the ignored
`.tmp/instrument-reference.md` carrying a live obsolete-reference shape. C2-B lacks that
four-item probe set. Provisioned environments, dependency caches, and ignored measurement
logs exist on both. This is a clean tracked-tree comparison with the declared station delta.

Each cell below is the **complete gate finding identity set**, not a total. Each command was
the sole command in its shell invocation, with its actual tool exit code captured. All eight
invocations exited 0 and none ended in or contained a traceback.

| Sole command from the product root | C2-A complete set | C2-B complete set |
| --- | --- | --- |
| `uv run python tools/quality/validation/repository_structure_phase0.py gate --gate all --json` | `[]` | `[]` |
| `uv run python tools/quality/validation/repository_structure_phase0.py gate --gate all --mode fail-closed --json` | `[]` | `[]` |
| `.venv/bin/python -m tools.quality.validation.check_docs_lifecycle` | `[]` | `[]` |
| `.venv/bin/python -m tools.quality.validation.repository_last_mile_inventory --json-output _build/.tmp/instruments-final/inventory-c2.json --check` | `[]` | `[]` |

The complete inventory objects, not just their summary counts, are byte-identical on both
stations and equal the committed baseline: SHA-256
`d33b3205f8d9b553ff1133bec79cccb0b3c1f0d213e13aa6ccf6b2fb73168a77`.
Each station retains its own `inventory-c2.json` at the path in the command. The complete
structured observation rows are the baseline's 26 rows; their accepted observations are
distinct from the gate's drift/invalid-input findings shown above. Every field participated
in the comparison. The two complete observation-identity sets are also retained together at
the delivery worktree's `_build/.tmp/instruments-final/paired-inventory-finding-sets.json`.
That receipt has SHA-256 `ff7c1ccdd98b57b59593977dcc8ddff056839e6cb1a84e5ffec34df40a616d98`:
each station supplies all 300 path observations across 26 rows plus seven explicit empty-path
row identities. Both directional differences of these complete 307-identity sets are `[]`.

The requested selected-root/default-baseline hypothesis was checked in both directions:
the module loaded on C2-A checked C2-B, and the module loaded on C2-B checked C2-A. For each
direction, a separate invocation of `check_artifacts(selected)` returned `[]`, exit 0, and a
separate invocation of `check_artifacts(selected, selected / DEFAULT_INVENTORY)` returned
`[]`, exit 0. Thus the complete default/resolved sets are A→B `[]`/`[]` and B→A `[]`/`[]`.
The fixture regression distinguishes repositories with different baseline contents, so this
real same-commit reading is not the only protection against module-checkout capture.
An explicit scratch baseline with only `summary.path_count` corrupted was independently
recomputed and refused, exit 1, complete set:

```text
baseline drift: _build/.tmp/instruments-final/inventory-corrupt.json
```

Complete final input denominators were enumerated on **each** station: 10,571 tracked files
of every file type in the whole checkout and 1,273 inferred directories for structure;
10,547 tracked product files for inventory; and 10,265 selected reference-scan files out of
those 10,547 product paths for docs. Complete path lists and distributions are in
`_build/.tmp/instruments-final/structure-denominators.json` on the delivery station and
`_build/.tmp/instruments-final/provision-final.json` on each diagnostic station. The docs
reference file-type denominator at both stations is:

```json
{".cfg":1,".cjs":9,".css":17,".csv":15,".cypher":2,".example":3,".html":3,".ini":11,".js":5,".json":1234,".jsonc":1,".jsonl":5,".lock":1,".md":1663,".mdc":1,".mjs":37,".py":5755,".pyi":5,".rego":23,".reproducible":1,".sh":45,".sql":6,".svg":18,".tf":1,".tmpl":7,".toml":222,".tpl":1,".ts":438,".tsx":577,".txt":5,".typed":2,".yaml":84,".yml":54,"<none>":13}
```

Final hook regression denominator: all eight collected cases in
`tests/repo_quality/tools/test_repo_hooks.py` passed with real pinned Lefthook/Prettier,
no skips. The two final cases protect a custom primary hook whose helper happens to have a
Lefthook-like name: with no backup it is preserved as `.old`; with a preexisting `.old` the
installer refuses and preserves both files. Both failed before central ownership was fixed
and under replacement-only removal while discovery and its markers remained present.
The other six cases cover install stability, real rule refusal across linked stations,
missing config/binary, autofix refusal, and the stale generated entrypoint. No existing
assertions were relaxed.

Final architecture-phase3 test denominator: all 30 collected cases ran, with 29 passing and
the checkpoint-route assertion below failing; exit 1, 42.04 seconds. The three new freshness
cases all passed. Their four runtime removals (caller sharing, missing private interpreter,
source-local cache, bypassed preparation) all went red while markers remained. Preparation
and direct Python consumers are tested behaviorally, not by searching environment-variable
names. No directory-wide pytest or debt-ledger command was run.

### Attribution and incidental proposals for the architect

The original baseline-drift, inventory-evidence, and docs-lifecycle rows retain historical
`not_established` inherited attribution. They were repaired/reconciled, not excused as
inherited. The journal was itself in the old docs scan; the additional continuation finding
was `removed_stub_reference | docs/superpowers/journals/2026-09-07-instrument-station-independence.md`.

A **separate** docs-freshness test was replayed exactly from the original slice base
`edc104849a9830dd5249390aa5380bd49836490c` at `instruments-base/policy-engine`:
`python3 -m pytest tests/repo_quality/tools/test_docs_lifecycle.py::test_phase6_4_docs_freshness_baseline_is_docs_only_and_stable -q --override-ini='addopts='`.
Both the base and current readings failed. Complete base finding set:

```text
docs freshness exception baseline expired
docs freshness violation count changed: expected 0, observed 7
docs freshness baseline hash changed: expected a3030ecf013ab9e3e7ffec891b2743e7dac6f2892361fad35f63774f7e4fe7a2, observed a4133e28a03a4705beaf8aa36616725b0dba76e3fc7713fe7d94e4390da75b2b
```

Complete current finding set:

```text
docs freshness exception baseline expired
docs freshness violation count changed: expected 0, observed 7
docs freshness baseline hash changed: expected a3030ecf013ab9e3e7ffec891b2743e7dac6f2892361fad35f63774f7e4fe7a2, observed a4133e28a03a4705beaf8aa36616725b0dba76e3fc7713fe7d94e4390da75b2b
```

The conservative complete input union has 502 paths: 471 Markdown, six Python, five TOML,
14 YML, two JSON and four extensionless paths, including checker/test implementations and
absent consulted paths. The entire slice-change intersection is `[]`; both commands used
the same system Python/pytest profile. This establishes **inherited** for this separate
failure. Complete receipt: `.tmp/instruments-docs/freshness-inputs.json` on the delivery
station. Proposed row/owner: expired and drifted docs-freshness exception baseline,
team-docs/architecture. This lane did not renew that exception.

The exact checkpoint test was also replayed at the original slice base:
`python3 -m pytest tests/repo_quality/tools/test_architecture_phase3.py::test_checkpoint_scope_uses_candidate_security_route -q --override-ini='addopts='`.
Its complete selected sets at base are `{"observed":[],"expected":["polisyos.core.security"]}`;
at current they are `{"observed":[],"expected":["polisyos.core.security"]}`. Both failed.
Each collector enumerated 2,619 `src/**/*.py` paths, read 2,618 Python artifacts plus the
public-surface TOML contract, and completed without a collector traceback. Artifact inputs
are disjoint from this slice, but conservative implementation/test dependencies intersect at:

```text
policy-engine/tests/repo_quality/tools/test_architecture_phase3.py
policy-engine/tools/devx/architecture/guardrails.py
```

Therefore attribution remains **base-reproduced, `not_established`**, not inherited. The
checkpoint imports a permitted public facade which the deep-import collector intentionally
excludes; the test expects that allowed route among deep-import findings. No assertion was
changed. Proposed row/owner: checkpoint-route test queries the wrong edge class,
team-architecture / Scientist checkpoint maintainer. Full receipts are
`.tmp/instruments-docs/checkpoint-instruments-base.json` and
`.tmp/instruments-docs/checkpoint-instruments.json` on the delivery station.

The original proposals have explicit dispositions: unreadable input became the owned row;
wrong-checkout baseline ownership and untracked docs scanning became mechanisms of existing
rows; the absent named closure test was correctly declined as a row and is now implemented.
The deeper inventory, ZIP, hook, and private-environment findings above are repairs within
those owned mechanisms, not new proposed rows.

### Final full freshness receipt and bounded residual

The corrected full sole command on disposable C2-A was again
`uv run polisyos-tools architecture guardrails check`, with log
`/Users/deniskopylov/polisyos/.worktrees/instruments-check-a/policy-engine/_build/.tmp/instruments-final/guardrails-c2.log`.
It completed with exit 1 and no traceback. The required family denominator is the complete
four-family selection from 61 manifest entries: `runtime-openapi-snapshot`,
`runtime-api-client`, `runtime-dashboard-api-types`, `trust-claim-posture-register`.
The final complete normalized finding identity set is:

```text
deep_import_baseline | drift
deep_import | polisyos.runtime.http.services.acquisition_admission_bundle -> polisyos.core.artifacts.manifest
deep_import | polisyos.runtime.http.services.acquisition_admission_bundle -> polisyos.core.artifacts.signing
deep_import | polisyos.runtime.http.services.acquisition_admission_bundle -> polisyos.core.artifacts.write_contract
generated_artifact | runtime-openapi-snapshot | output_probe_worktree_escape
generated_artifact | runtime-openapi-snapshot | schemas/runtime_api_v1.openapi.json
generated_artifact | trust-claim-posture-register | apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json
```

The complete final escaped-path set is:

```text
isolated-source/.polisyos/cas/artifacts/sha256/6d/7a/6d7a8b8916a5e3ae26d61ec5fb8fe5f2daf5c69682ad35feeb778fc4bde21ab0.blob
isolated-source/.polisyos/cas/artifacts/sha256/6d/7a/6d7a8b8916a5e3ae26d61ec5fb8fe5f2daf5c69682ad35feeb778fc4bde21ab0.manifest.json
```

The complete generated-byte-drift path set is:

```text
schemas/runtime_api_v1.openapi.json
apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json
```

The API-client generator now executes without the missing-private-interpreter failure; the
complete escape set contains no uv cache path. Runtime CAS writes remain findings. This is a
correction of this lane's own first candidate, not an inherited-red claim. No generated output,
exception, source implementation, or excluded manifest was altered to obtain a pass.
There is no cross-station equality claim for the full guardrail: the second station exercised
the other consumer, and its distinct failure is recorded above.

After this final full run, the complete caller `.pth` identity set still contains exactly:

```text
lib/python3.14/site-packages/_editable_impl_policy_engine.pth
lib/python3.14/site-packages/_virtualenv.pth
```

Before and after bytes of the first file are, without a trailing newline:

```text
/Users/deniskopylov/polisyos/.worktrees/instruments-check-a/policy-engine
/Users/deniskopylov/polisyos/.worktrees/instruments-check-a/policy-engine/src
```

Before and after bytes of the second file are `import _virtualenv`, without a trailing newline.
The complete changed-identity set is `[]`. A direct `.venv/bin/python` process, with no uv
resync, imported
`/Users/deniskopylov/polisyos/.worktrees/instruments-check-a/policy-engine/src/polisyos/__init__.py`.
Full receipt: `guardrail-c2-environment-after.json` beside that station's log. The other real
consumer's unchanged two-file caller set and local import were independently recorded on
check-b. The shared helper did not change between its C1 receipt and C2.

This closes caller-environment rebinding while declaring the limit honestly. The smallest
remaining closure work is at the producers/committed generated outputs: route runtime CAS
writes into an assigned output context, reconcile the two generated artifacts, and adjudicate
the acquisition-bundle imports. This lane has no authority to edit the runtime source,
generated manifest, OpenAPI schema or dashboard public artifact. Its instrument already
detects these cases; no available in-scope switch can reconcile them without suppressing
the property. Inherited attribution for this final red is `not_established`; no unsafe or
unprovisioned base replay is presented as proof.

Incidental proposals for architect association/allocation, not authoritative new register rows:

| Proposed issue | Proposed owner | Concrete acceptance |
| --- | --- | --- |
| Runtime OpenAPI output probe writes CAS outside its assigned output root | runtime HTTP / artifact custody owner | The real generator's complete escaped-path set becomes `[]` without excluding CAS from measurement. |
| Runtime OpenAPI and trust-posture committed bytes drift from their generators | runtime API / trust-posture generated-artifact owners | Reconcile the declared outputs and rerun their exact generator-byte checks. |
| Acquisition admission bundle introduces deep imports beyond the baseline | runtime/core facade owner with architecture | Adjudicate the three exact import edges above and recompute the baseline or correct the source. |

These proposals join the separately evidenced docs-freshness and checkpoint-test proposals
above. P40 buckets were supplied during review; no hypothetical general refactor was added.

### Delivery and final readback contract

All 14 changed Python files passed Ruff together after source freeze. The Node installer
passed its syntax check. The committed regression tests and their runtime-removal receipts
are preserved; no assertion was quietly weakened. The source candidate's actual commit
ran the repaired declared checks successfully, with no missing-config warning.
After writing this final journal, the delivery station's sole docs, inventory `--check`, and
documented default structure commands each exited 0 with complete finding sets `[]`, `[]`,
and `[]`; source/baseline bytes were unchanged.

The final follow-up commit records this journal only. Source and baseline bytes remain those
of C2; final branch/file/hook hashes and attachment are read back after that commit. Diagnostic
worktrees and ignored receipts remain available for local review. No other lane's branch or
worktree was modified. No GitHub integration, push, rebase, force-push, reset or stash storage
was used. The architect owns register/ledger transcription and cross-lane rollout.
