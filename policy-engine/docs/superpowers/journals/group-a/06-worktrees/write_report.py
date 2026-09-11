"""Render the temporal worktree measurement; does not execute Git."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[6]
OUT=Path(__file__).resolve().parent
d=json.loads((OUT/'summary.json').read_text());rows=d['registrations']
selected=[r for r in rows if r['dry_run_selected']];live=[r for r in rows if not r['dry_run_selected']]
table='\n'.join('| '+r['registration']+' | '+(('`'+r['branch'].removeprefix('refs/heads/')+'` — merged') if r['branch'] else 'no attached branch; detached HEAD is an ancestor of main')+' | `'+r['tip'][:12]+'` | `'+r['expected_directory']+'` |' for r in selected)
livetable='\n'.join('| '+r['registration']+' | `'+r['expected_directory']+'` |' for r in live)
report=f'''# Group A / 06 — Stale worktree registrations

## 1. Discrepancy and agreement with the recorded claim

The row `stale-worktree-registrations-collide-with-new-lane-names` claims
**53 missing directories / 72 registrations**, with **43 stale registrations on
branches merged into main**. It describes a historical 2026-09-10 measurement.
That text is the claim being compared, not the source of this census.

At **{d['time_utc']}**, two enumerations independently give
**77 registrations = 24 existing directories + 53 missing directories**.
`git worktree prune --dry-run --verbose` selects exactly those **53 / 77**.
Of the selected set, **43 / 53 have an attached branch**, all ancestors of pinned
main; **10 / 53 have detached HEADs**, all also ancestors of pinned main.
There are **0 unmerged and 0 missing branch refs among the 43 attached branches**.
The ten detached registrations must not be mislabeled as ten gone branches:
no branch is recorded for them. All current registration identities are retained
in the receipt.

The stale count and merged-branch count agree; the current total is five larger
than the row's historical total. This analysis worktree is one known new member.
The other historical-to-current additions are not inferred from that arithmetic.
The earlier worker noticed a concurrent `integration` registration and discarded
its exploratory snapshot. The deciding snapshot below passed before/after
metadata equality and pinned-main equality checks.

**No existing directory is in the dry-run removal set: 0 / 24.** The bounded
filesystem scan found no relocated `.git` pointer for any of the 53 selected
registrations. That negative is limited by the explicitly unreadable/excluded
locations below; “no copy exists anywhere” is not established. No prune mutation
has run.

## 2. Commands, complete denominators and receipts

Run from `/Users/deniskopylov/polisyos/.worktrees/group-a-analysis`:

```sh
python3 policy-engine/docs/superpowers/journals/group-a/06-worktrees/census.py
```

Exit **0**. The script executes each Git command separately, records complete
stdout/stderr and exact return codes, and never invokes prune without `--dry-run`.
Its two registration enumerators are:

1. `git worktree list --porcelain -z`: **77 registration records**.
2. Direct reading of every child under `.git/worktrees/`: **76 administrative
   directories**, plus the main worktree record = **77**.

The complete path sets are equal. For every linked member it reads `gitdir`,
`HEAD`, `commondir`, and `locked`, checks expected directory and `.git` existence,
and reconciles the corresponding porcelain record. `git rev-parse --verify`
and `git merge-base --is-ancestor` classify attached branches; detached HEADs
are compared as commits separately. The comparison base is main at
`{d['main']}`, not a moving symbolic comparison target.
The full membership is stable across enumeration, dry-run and filesystem search.

Complete deciding output is
`policy-engine/docs/superpowers/journals/group-a/06-worktrees/summary.json`.
Full command output and raw administrative records are in
`policy-engine/docs/superpowers/journals/group-a/06-worktrees/raw/census.json`,
SHA-256 `{d['raw_receipt']['sha256']}`.
The two enumerations reconcile all identities, not just their counts.

### Exactly what the default prune dry-run selected

For each row below, Git printed `Removing worktrees/<registration>: gitdir file
points to non-existent location`. These are **53 selected administrative
registrations / the complete 77-registration denominator**. Every expected
directory is missing; every off-expected pointer match in the declared search is
empty. Git would remove `.git/worktrees/<registration>` administrative metadata.
It does not delete the branch ref merely because its registration is pruned.
The row's phrase “no data” should be read carefully: administrative files/index/
reflogs are data; this measurement establishes the selected registration set,
not preservation of every historical reflog entry.

| Registration name | Attached branch classification | Compared commit | Expected directory |
| --- | --- | --- | --- |
{table}

### Existing worktrees outside that removal set

The complete live-directory denominator is **24 = main worktree + these 23 linked
worktrees**. Main is `/Users/deniskopylov/polisyos`. Each linked directory and its
expected `.git` file exists. None is selected by the dry-run.

| Registration | Existing directory |
| --- | --- |
{livetable}

### Off-path directory search

The search walks `/Users/deniskopylov` and `/private/tmp`, without following
symlinks, reading `.git` files and resolving their `gitdir:` targets against the
exact administrative registration. It inspects **{d['scan']['directory_entries_inspected']:,}
directory entries across {d['scan']['directories_visited']:,} visited directories**;
the complete visited search is the denominator for the off-path negative, not the
whole disk. It records **{d['scan']['excluded_path_count']:,} excluded entries/paths**
(including symlinks and excluded directory names), fully listed in the raw
receipt. Excluded directory names: {', '.join('`'+x+'`' for x in d['scan']['excluded_names'])}.

Three directories refused enumeration: `/Users/deniskopylov/Documents`,
`/Users/deniskopylov/Movies/TV`, `/Users/deniskopylov/Music/Music`, each with
`Operation not permitted`. They are ambiguous, never counted as empty.
An off-path copy that lost its `.git` file, an arbitrary copied worktree, a
symlink-only location, another user's directory or another mounted volume is
outside this pointer-based search. The current default prune does not use that
search; it follows each administrative `gitdir` pointer.

## 3. Competing readings and their costs

| Reading | What the evidence would license | Cost / residual |
| --- | --- | --- |
| The operational question is the default prune's current removal set | Acting on the 53 named stale administrative entries while leaving the 24 known live directories outside the selected set | Shared Git metadata changes; detached-registration reflogs/index metadata are removed with those administrative directories. This report authorizes no action. |
| The prerequisite is proof that no moved directory could rely on any selected registration | The existing-pointer inventory supplies a bounded check only | Unreadable/excluded locations and copies without pointers require further evidence or an explicitly accepted search boundary. Their absence cannot be assumed. |
| Pruning alone resolves future commissioning collisions | It removes stale worktree registrations | It leaves branch names in place. An existing branch can still fail the required free-name check after its stale registration is gone. |
| Commissioning must establish both names are free | Independent branch-ref and registration/directory checks prevent the specific collision before work starts | The naming policy remains an architect rule; the user's required checks were executed for this lane. A live branch is not made free by deleting its registration. |

## 4. What an architect decision would rest on

The operative facts are the **53-name dry-run set**, the **0 / 24 intersection with
known existing directories**, the separate **43 attached / 10 detached** topology,
and the explicitly bounded off-path search. The architect decides whether that
search boundary is sufficient before any shared metadata mutation. If the repository
changes, the temporal snapshot must be refreshed; no future removal set is implied.

Prune and prompt hygiene address different objects: administrative registration
liveness versus availability of an exact branch and directory name. Neither
measurement decides a prompt rule. Pattern pass: P35 complete denominator; P38
branch availability is not directory liveness; P41 avoids carrying an old count
as a present measurement.

## 5. What was not established

- No proof of absence across unreadable directories, excluded machinery, other
  user roots, external volumes or pointerless copies.
- No claim that pruning retains registration-local reflog/index history; this
  report does not audit reachability of every reflog entry. Selected HEADs alone
  were checked against main.
- No historical reconstruction of exactly which five entries account for the
  72-to-77 change; the counts refer to different times.
- No claim that branch names will become available after prune; branch refs are a
  separate checked object.
- No prune execution, branch deletion, live-worktree mutation, or permission to
  perform one.
'''
(ROOT/'policy-engine/docs/superpowers/specs/2026-09-11-group-a-06-worktree-registrations.md').write_text(report)
print('wrote report from retained measurement; selected',len(selected),'existing linked',len(live))
