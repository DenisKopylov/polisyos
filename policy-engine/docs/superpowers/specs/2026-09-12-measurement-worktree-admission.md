# Measurement plane Stage1 — worktree admission (row 4)

**Stage1 research only; root implementation decision pending.** This work is confined to rows 4–5. No source/config changes, pruning, branch/index/commit mutations or push. Root serializes shared Git and any later implementation; at most three workstreams. No row-3 model/helper ownership decision is made here. The two prohibited register/ledger documents were neither opened nor cited; their generator belongs to root.

Source baseline: `307dabcb47bcc0e7659529344d0648cafb840a30` (`307dabcb4`). Session attachment was read back at `/Users/deniskopylov/polisyos/.worktrees/measurement-plane/policy-engine`, branch `codex/measurement-plane`, HEAD `42c09a7a46ac7ec42e39e4cc19a259a10b2c8811`; the delta from baseline is three row-1 documentation files, with no source/config delta. Product-relative source citations below mean `policy-engine/<path>@307dabcb4`. Current Git registrations are explicitly time-bound observations, not facts backdated to that commit.

Raw receipts: `docs/superpowers/journals/measurement-plane/rows45/raw/`; already ignored by `policy-engine/.gitignore:149`. Complete deciding stdout/stderr and failures are retained, not truncated into findings. Raw artifact hashes are in `receipt-index.json`. Exploration failures (wrong guessed tool directories) are retained and superseded by the complete census; they support no absence claim. Every lexical query used case-insensitive matching. AST claims use parsed definitions/calls, not text embedded in logs.

## Findings and complete denominator

**MP4-F01 — prior survey reproduced without the prohibited documents.** The saved survey is `docs/superpowers/specs/2026-09-11-debt-nature-survey-open.md@ae4befeddf9645cccef2dec0d1254a18e2242e9b`, section/finding `stale-worktree-registrations-collide-with-new-lane-names`. Its exact raw receipt was found at `/Users/deniskopylov/polisyos/.worktrees/debt-nature-survey/policy-engine/docs/superpowers/journals/debt-survey/open/raw/worktrees.json`, SHA-256 `35ba83dc952dddafe5cd19ac5a52a63cbdc491a1c3a2f6bd9aa357fd473a2e53` (local copy `prior-worktrees.json`). The prior receipt reports **78 total registrations, 53 absent registered directories, 24 live linked directories plus the main checkout**. Thus 78 = 53 + 24 + 1, not 53 + 24. Its source analysis base was `fc823071a`; the worktree observation was mutable state even then.

**MP4-F02 — current delta is exactly this lane.** At the receipt timestamp, porcelain enumerates **79 registrations = 53 missing + 25 live linked + 1 main**. Independently, all **78 linked admin directories** under `/Users/deniskopylov/polisyos/.git/worktrees/` yield **53 missing gitdir targets + 25 existing targets**. Their full path-identity sets agree with porcelain after excluding the main checkout. Comparing the complete prior linked set against this one gives one addition, `/Users/deniskopylov/polisyos/.worktrees/measurement-plane`, and no removal. No other delta is inferred. Files: `worktree-reconciliation.json`, `worktree-live-readback.json`.

The filesystem denominator is each registered directory and its `.git` marker, each linked admin `gitdir`/`commondir`/`HEAD`/optional `locked` record, and the direct child directories of `/Users/deniskopylov/polisyos/.worktrees` (depth one). Every existing registration was also checked by `git -C <exact-path> rev-parse --show-toplevel`, `symbolic-ref -q HEAD`, and `rev-parse --absolute-git-dir`; all root/branch checks agree. Detached entries remain detached, not fabricated branches. All direct child directories in that bounded root are registered. This is not a recursive home-directory census.

**MP4-F03 — dry-run prediction, not cleanup authorization.** `git worktree prune --dry-run --verbose` exits 0 and predicts the following complete **53-name** set. Every predicted admin record points to a nonexistent target; no live target intersects it; no missing admin target is omitted. Git emits its prediction on stderr. We did not prune and do not claim branch objects are lost, branches are merged, or cleanup is safe merely because a pathname is absent.

```text
ci-repair
ci-targets
dashboard
debt-a-promotion-gate
debt-a2-drift-baseline
debt-a2-drift-detection
debt-academic-producer-repairs
debt-b-epoch-decision-validity
debt-b-extraction-vocabulary
debt-b2-manufactured-design
debt-c-ds10-capability-discovery
debt-d-ds11-trust-posture
debt-e-acquisition-n13b
debt-evidence-class-reachability
debt-f-architecture-imports
debt-g-atlas-residuals
debt-historical-cohorts
debt-i-runtime-authorization
debt-j-acquisition-route-binding
debt-k-first-governed-promotion
debt-l-research-census
debt-m-promotion-corridor-repair
debt-o-instrument-integrity
debt-p-dashboard-evidence
debt-parameter-unsupplied-vs-unknown
debt-q-remeasure-and-typing
debt-r-unowned-producers
debt-s-pgproof-and-def22
debt-unknown-evidence-weight
debt-vocabulary-value-provenance
ds4-decision-grade-regeneration
gy-cr4-denominator-seam
gy-def22-environment-discriminant
gy-pr1a-data-only-promotion
instruments
instruments-base
instruments-check-a
instruments-check-b
instruments2-python3143
instruments2-python3143-final
measuring-base
measuring-instrument
measuring-station-a
measuring-station-b
producers
research-basis-grade-carriers
station-c
toolchain
verify-a
verify-b
verify-c
vintage
watchers
```

**Bounded limitation:** a moved directory outside this bounded search cannot be excluded. An unavailable mount or relocated checkout can make an old gitdir absent while preserving work elsewhere. The dry-run set is a Git prediction, not proof of abandonment. Root must adjudicate any future prune separately; this Stage1 recommends the admission preflight independently of cleanup.

**MP4-F04 — original collision has an actual witness.** The historical incident is the producers lane stopped by a reused branch and path, recorded in commit `a534024ee28dfd9ac4fd21be1ff769b253722d8e`'s commit message (`original-collision-history.txt`), rather than read from the forbidden register. Current independent evidence identifies the concrete pair: branch `refs/heads/codex/missing-producers`, registered directory `/Users/deniskopylov/polisyos/.worktrees/producers`, admin record `/Users/deniskopylov/polisyos/.git/worktrees/producers`, with HEAD naming that branch and gitdir naming the absent directory's `.git`. `git show-ref --verify refs/heads/codex/missing-producers` exits 0. Therefore filesystem nonexistence does not establish availability of either commissioned name. The original failed `git worktree add` stderr was not located; no such mutating command was rerun. Historical causality is supported by that explicit incident account; the two current occupancy predicates are independently reproduced.

## Decision: extend the existing registered doctor

**MP4-D01 — recommendation to root:** extend `tools/devx/workspace/doctor.py@307dabcb4`, not a new unregistered helper or worktree manager. Its existing `_build_parser` and `main` own machine preflight and `CheckResult` already supplies check outcomes. `tools/registry.py@307dabcb4::_discover_specs` parses actual module definitions, constructs `ToolSpec`, and exposes `workspace.doctor`; `tools/cli.py@307dabcb4::_make_category_group` / `_make_tool_command` dispatch it. `workspace-registry.json` and `doctor-registered-help.json` execute those paths. `tools/lib/preflight.py@307dabcb4::run_preflight` checks imports/executables/lifecycle, not commissioned branch/path identity, so adding a disconnected check there would not consume the expected pair.

Proposed surface (does not exist yet):

```text
polisyos-tools workspace doctor --worktree-admission create|resume --branch <exact-branch> --path <exact-absolute-worktree-root>
```

The mode is an early read-only path, avoiding lockfile install checks, browser checks, cleanup and implicit name allocation. Its required inputs are the exact intended branch and worktree root (the prompt also spells out the derived product-root path). No default from cwd, guessed suffix, normalized branch substitute, auto-created branch or alternate path is allowed. Invalid refs, omitted inputs, relative paths or unresolved repository identity fail closed. Read Git and filesystem state from the same known repository; verify linked marker → admin record → common repository agreement.

| Predicate | Recompute/decision |
| --- | --- |
| Create: branch syntax and exact `refs/heads/<branch>` availability | `git check-ref-format` plus exact ref existence; existing branch fails, even if unregistered or merged. Do not use abbreviated/ref-expression aliases. |
| Create: exact directory availability | Reject an existing filesystem object (including a dangling symlink), a registered path, or an admin gitdir naming the path, even if the directory is absent. Compare resolved identity as well as the supplied spelling to expose aliases; never silently substitute the resolved spelling in a prompt. |
| Resume: exact attachment | Require that the requested live directory, its actual symbolic HEAD, porcelain entry, admin record and common repository all match the exact requested branch/path. Detached/mismatched/missing is a failure, not an invitation to select another checkout. |
| Observation completeness | Git errors, missing/unreadable admin records, contradictory enumeration or an indeterminate path produce nonzero/unmeasured, never “available”. An unrelated stale record does not veto an available pair. |
| Freshness | Report observation time and both exact inputs, branch existence, matching registration/admin details and bounded path scope. Root reruns immediately before commissioning/creation, then rechecks exact attachment after creation. The command does not reserve names. |

All deciding observed predicates must be `recomputed` or `independently_reconciled`; requested names are `consumer_asserted` selectors, not proof of their own availability. Lack of wider filesystem knowledge remains `not_established`, so no prune-safe claim is emitted. Current shared-state serial execution by root narrows the race but does not confer an atomic reservation on this read-only command.

## Prompt hygiene options, cost and production consumer

| Option | Cost and limitation | Disposition |
| --- | --- | --- |
| AGENTS-only rule | Lowest implementation cost; requires repeating manual commands and can be skipped. Prose cannot reject an occupied pair. | Keep one short universal commissioning rule linking the executable preflight. |
| New commissioning template | More duplicated prose and a second maintenance location; old/ad-hoc prompts bypass it. | Do not create a standalone template merely for this row. Put one exact invocation example in the workspace README. |
| Registered doctor mode + rule | Small parser/check extension, focused integration tests and existing CLI dispatch; rejects the actual pair and prints evidence. Does not intercept arbitrary external prompt writers. | Selected minimum enforceable check. Root remains the production commissioning consumer. |

**Every commissioning prompt must check the exact branch AND path before naming them; no substitutes.** Before implementation, root uses the explicit Git/ref/admin/filesystem read-only checks above manually; it must not claim the proposed flag exists. After implementation, the prompt must include the exact successful preflight command/receipt and immediate post-create attachment readback. A failed pair stops that commission; root must explicitly re-commission any changed pair after checking it. A placeholder template is not an executed check.

The non-test chain is human/root commissioner → registered `polisyos-tools workspace doctor` → existing CLI/registry → doctor read-only checks → stdout/JSON receipt → commissioner accepts or declines the exact prompt. Persist the complete output in the commissioning journal and consume its measured result. A new `main()` alone or a test import is insufficient. There is no evidence here of a repository-owned universal prompt dispatcher; universal automatic interception is `not_established` and is not promised.

## Proposed root edits and acceptance

Mechanism: extend `tools/devx/workspace/doctor.py`; only extend registry metadata if the existing discovery/dispatch actually requires it. Mandatory companions outside the mechanism budget: `tests/unit/core/phase0/test_workspace_commands.py` (CLI behavior and filesystem/Git adversarial cases), `tools/devx/workspace/README.md`, one short root `AGENTS.md` commissioning rule, and root's own plan/journal/governance record. No prune implementation, cleanup scheduler, new sovereign subsystem or source change is delivered in Stage1.

Root acceptance must use the real registered command, not marker tests:

1. Original pair `codex/missing-producers` + `/Users/deniskopylov/polisyos/.worktrees/producers` yields nonzero with branch occupancy AND stale registered-path evidence. This is a read-only current negative; keep a disposable isolated fixture so later cleanup cannot erase the regression test.
2. Stale-path-only negative: an independently available fixture branch plus a missing-but-registered path still fails. The branch-only check cannot make it green. Conversely, occupied branch + unused fixture path fails.
3. Resume exact pair succeeds; same path with wrong branch, detached HEAD, mismatched admin backlink, unreadable record, dangling symlink and path alias fail. A genuinely available pair succeeds despite unrelated stale records.
4. Remove the branch-check call while retaining its output label; branch-only negative must fail the test. Remove the admin/path check while preserving markers; stale-path-only negative must fail. The commissioner must not receive a positive receipt on either removal.
5. Read back the final branch/path and docs from the implementation branch. Root performs its requested broader closeout once after reviews, preserving all deciding output; it does not rerun the separate ledger generator in this lane.

## Pattern pass / scope labels

P35: full registration/admin identity sets and live checks, not a sample; source command claims parsed and invoked. P37: selectors are not authority; state must be recomputed with completeness recorded. P38: “directory absent” is the wrong proxy for “branch AND registered path available”; MP4-F04 is the divergent case. P39: tests/instructions/journal are mandatory companions, not reasons to split or stop the mechanism. P01/P02/P29: existing registered caller reused, actual negative consumed. P13: choose one doctor mode, not a new orchestration framework.

The admission capability is currently `producer_missing`, `bridge_missing`, `verification_missing`, `semantic_test_missing`; existing machine doctor is not evidence that this new property is implemented. A dashboard/API is `surface_out_of_scope`; the intended external surface is the registered developer CLI. Root implementation remains pending Stage1 readback. No status/closure change is claimed.

## Architect-only command and predicted effect

The exact mutating counterpart of the reproduced dry run is:

```sh
git -C /Users/deniskopylov/polisyos worktree prune --verbose
```

**Do not execute it in this lane.** With the observed state unchanged, Git predicts
removal of precisely the 53 administrative registrations named in MP4-F03, under
`/Users/deniskopylov/polisyos/.git/worktrees/<name>/`. The 25 live linked worktrees
and main checkout are outside the predicted set. This is registration cleanup;
it neither deletes local branch refs nor establishes merge/abandonment status.
The architect must reproduce the dry run immediately before that action because
registrations and mounted/moved directories are mutable. A moved directory beyond
the bounded search remains unresolved by construction.
