# Instrument station independence — investigation and scope stop

Date: 2026-09-07. Owner: instrument-station-independence lane.

## Outcome and stopping decision

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

This journal is to be committed on the attached branch and read back from that branch before
handback. No push is authorized or performed. This is a scope-boundary handback, not a claim
that the six instrument debts are closed.
