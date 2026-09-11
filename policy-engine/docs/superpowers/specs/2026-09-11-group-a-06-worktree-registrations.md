# Group A / 06 — Stale worktree registrations

## 1. Discrepancy and agreement with the recorded claim

The row `stale-worktree-registrations-collide-with-new-lane-names` claims
**53 missing directories / 72 registrations**, with **43 stale registrations on
branches merged into main**. It describes a historical 2026-09-10 measurement.
That text is the claim being compared, not the source of this census.

At **2026-09-11T12:45:35.389473+00:00**, two enumerations independently give
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
The retained initial snapshot at 12:04:42 UTC and the refreshed snapshot above
have identical registration counts and classifications. The deciding refreshed
snapshot passed before/after metadata equality and pinned-main equality checks.

**No existing directory is in the dry-run removal set: 0 / 24.** The bounded
filesystem scan found no relocated `.git` pointer for any of the 53 selected
registrations. That negative is limited by the explicitly unreadable/excluded
locations below; “no copy exists anywhere” is not established. No prune mutation
has run.

## 2. Commands, complete denominators and receipts

Run from `/Users/deniskopylov/polisyos/.worktrees/group-a-analysis`:

```sh
python3 policy-engine/docs/superpowers/journals/group-a/06-worktrees/census.py --output-subdirectory final
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
`63bdb9640e7b76b49356cba940bab6067f1be512`, not a moving symbolic comparison target.
The full membership is stable across enumeration, dry-run and filesystem search.

Complete deciding output is
`policy-engine/docs/superpowers/journals/group-a/06-worktrees/final/summary.json`.
Full command output and raw administrative records are in
`policy-engine/docs/superpowers/journals/group-a/06-worktrees/final/raw/census.json`,
SHA-256 `048b7dd75ef6e896c9cc375db1fbf2262d31485d072d7113a7faf949e34aaf30`.
The two enumerations reconcile all identities, not just their counts.
The initial measurement remains separately retained at
`policy-engine/docs/superpowers/journals/group-a/06-worktrees/summary.json` and its
SHA-bound raw receipt; refreshing did not overwrite it.

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
| ci-repair | `codex/ci-bootstrap-and-glob-repair` — merged | `df440069e179` | `/Users/deniskopylov/polisyos/.worktrees/ci-repair` |
| ci-targets | `codex/ci-declared-targets` — merged | `f1f21a474d22` | `/Users/deniskopylov/polisyos/.worktrees/ci-targets` |
| dashboard | `codex/dashboard-debt` — merged | `c0aed3270974` | `/Users/deniskopylov/polisyos/.worktrees/dashboard` |
| debt-a-promotion-gate | `codex/debt-a-promotion-gate` — merged | `964bf207a873` | `/Users/deniskopylov/polisyos/.worktrees/debt-a-promotion-gate` |
| debt-a2-drift-baseline | no attached branch; detached HEAD is an ancestor of main | `fac07ffc6281` | `/Users/deniskopylov/polisyos/.worktrees/debt-a2-drift-baseline` |
| debt-a2-drift-detection | `codex/debt-group-a-drift-detection` — merged | `81d059630f04` | `/Users/deniskopylov/polisyos/.worktrees/debt-a2-drift-detection` |
| debt-academic-producer-repairs | `codex/debt-academic-producer-repairs` — merged | `dcb8b0571600` | `/Users/deniskopylov/polisyos/.worktrees/debt-academic-producer-repairs` |
| debt-b-epoch-decision-validity | `codex/debt-b-epoch-decision-validity` — merged | `2d1840e6c543` | `/Users/deniskopylov/polisyos/.worktrees/debt-b-epoch-decision-validity` |
| debt-b-extraction-vocabulary | `codex/debt-b-extraction-vocabulary` — merged | `e0a4f4c070a8` | `/Users/deniskopylov/polisyos/.worktrees/debt-b-extraction-vocabulary` |
| debt-b2-manufactured-design | `codex/debt-b2-manufactured-design` — merged | `65f1fe0b1221` | `/Users/deniskopylov/polisyos/.worktrees/debt-b2-manufactured-design` |
| debt-c-ds10-capability-discovery | `codex/debt-c-ds10-capability-discovery` — merged | `5710d6694fcd` | `/Users/deniskopylov/polisyos/.worktrees/debt-c-ds10-capability-discovery` |
| debt-d-ds11-trust-posture | `codex/debt-d-ds11-trust-posture` — merged | `69de30bfcd0b` | `/Users/deniskopylov/polisyos/.worktrees/debt-d-ds11-trust-posture` |
| debt-e-acquisition-n13b | `codex/debt-e-acquisition-n13b` — merged | `066e1978ac1c` | `/Users/deniskopylov/polisyos/.worktrees/debt-e-acquisition-n13b` |
| debt-evidence-class-reachability | `codex/debt-evidence-class-vocabulary-reachability` — merged | `9bd114d67241` | `/Users/deniskopylov/polisyos/.worktrees/debt-evidence-class-reachability` |
| debt-f-architecture-imports | `codex/debt-f-architecture-imports` — merged | `f203306725f8` | `/Users/deniskopylov/polisyos/.worktrees/debt-f-architecture-imports` |
| debt-g-atlas-residuals | `codex/debt-g-atlas-residuals` — merged | `4b492fcaf1a9` | `/Users/deniskopylov/polisyos/.worktrees/debt-g-atlas-residuals` |
| debt-historical-cohorts | `codex/debt-historical-cohorts` — merged | `84e228fbe363` | `/Users/deniskopylov/polisyos/.worktrees/debt-historical-cohorts` |
| debt-i-runtime-authorization | `codex/debt-i-runtime-authorization` — merged | `7e1883a2d6c5` | `/Users/deniskopylov/polisyos/.worktrees/debt-i-runtime-authorization` |
| debt-j-acquisition-route-binding | `codex/debt-j-acquisition-route-binding` — merged | `9121b149fcb4` | `/Users/deniskopylov/polisyos/.worktrees/debt-j-acquisition-route-binding` |
| debt-k-first-governed-promotion | `codex/debt-k-first-governed-promotion` — merged | `56946feea954` | `/Users/deniskopylov/polisyos/.worktrees/debt-k-first-governed-promotion` |
| debt-l-research-census | `codex/debt-l-research-census` — merged | `8f95c8d800c2` | `/Users/deniskopylov/polisyos/.worktrees/debt-l-research-census` |
| debt-m-promotion-corridor-repair | `codex/debt-m-promotion-corridor-repair` — merged | `252197a7425c` | `/Users/deniskopylov/polisyos/.worktrees/debt-m-promotion-corridor-repair` |
| debt-o-instrument-integrity | `codex/debt-o-instrument-integrity` — merged | `448c2b5a53e9` | `/Users/deniskopylov/polisyos/.worktrees/debt-o-instrument-integrity` |
| debt-p-dashboard-evidence | `codex/debt-p-dashboard-evidence` — merged | `dfb3dd9aea9d` | `/Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence` |
| debt-parameter-unsupplied-vs-unknown | `codex/debt-parameter-unsupplied-vs-unknown` — merged | `2c4f085b075c` | `/Users/deniskopylov/polisyos/.worktrees/debt-parameter-unsupplied-vs-unknown` |
| debt-q-remeasure-and-typing | `codex/debt-q-remeasure-and-typing` — merged | `de3c79540cdd` | `/Users/deniskopylov/polisyos/.worktrees/debt-q-remeasure-and-typing` |
| debt-r-unowned-producers | `codex/debt-r-unowned-producers` — merged | `d12a541ecab3` | `/Users/deniskopylov/polisyos/.worktrees/debt-r-unowned-producers` |
| debt-s-pgproof-and-def22 | `codex/debt-s-pgproof-and-def22` — merged | `e90d11746e9c` | `/Users/deniskopylov/polisyos/.worktrees/debt-s-pgproof-and-def22` |
| debt-unknown-evidence-weight | `codex/debt-unknown-evidence-weight` — merged | `69c98e7eb44b` | `/Users/deniskopylov/polisyos/.worktrees/debt-unknown-evidence-weight` |
| debt-vocabulary-value-provenance | `codex/debt-vocabulary-value-provenance` — merged | `c100ec4d0717` | `/Users/deniskopylov/polisyos/.worktrees/debt-vocabulary-value-provenance` |
| ds4-decision-grade-regeneration | `codex/ds4-decision-grade-regeneration` — merged | `bb6006e046ea` | `/Users/deniskopylov/polisyos/.worktrees/ds4-decision-grade-regeneration` |
| gy-cr4-denominator-seam | `codex/gy-cr4-denominator-seam` — merged | `59aa994e6eca` | `/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam` |
| gy-def22-environment-discriminant | `codex/gy-def22-environment-discriminant` — merged | `5241bcd46025` | `/Users/deniskopylov/polisyos/.worktrees/gy-def22-environment-discriminant` |
| gy-pr1a-data-only-promotion | `codex/gy-pr1a-data-only-promotion` — merged | `59f81a58385d` | `/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion` |
| instruments | `codex/instrument-station-independence` — merged | `9776fe348f70` | `/Users/deniskopylov/polisyos/.worktrees/instruments` |
| instruments-base | no attached branch; detached HEAD is an ancestor of main | `edc104849a98` | `/Users/deniskopylov/polisyos/.worktrees/instruments-base` |
| instruments-check-a | no attached branch; detached HEAD is an ancestor of main | `6fa919b744c9` | `/Users/deniskopylov/polisyos/.worktrees/instruments-check-a` |
| instruments-check-b | no attached branch; detached HEAD is an ancestor of main | `6fa919b744c9` | `/Users/deniskopylov/polisyos/.worktrees/instruments-check-b` |
| instruments2-python3143 | no attached branch; detached HEAD is an ancestor of main | `a8d323a2f63f` | `/Users/deniskopylov/polisyos/.worktrees/instruments2-python3143` |
| instruments2-python3143-final | no attached branch; detached HEAD is an ancestor of main | `fc17e4754d41` | `/Users/deniskopylov/polisyos/.worktrees/instruments2-python3143-final` |
| measuring-base | `codex/measuring-base` — merged | `0373364448f7` | `/Users/deniskopylov/polisyos/.worktrees/measuring-base` |
| measuring-instrument | `codex/measuring-instrument` — merged | `10d84e5ccd98` | `/Users/deniskopylov/polisyos/.worktrees/measuring-instrument` |
| measuring-station-a | `codex/measuring-station-a` — merged | `f69400b1f00e` | `/Users/deniskopylov/polisyos/.worktrees/measuring-station-a` |
| measuring-station-b | `codex/measuring-station-b` — merged | `f69400b1f00e` | `/Users/deniskopylov/polisyos/.worktrees/measuring-station-b` |
| producers | `codex/missing-producers` — merged | `c5389feced8c` | `/Users/deniskopylov/polisyos/.worktrees/producers` |
| research-basis-grade-carriers | `codex/research-basis-grade-carriers` — merged | `e3f9805057f5` | `/Users/deniskopylov/polisyos/.worktrees/research-basis-grade-carriers` |
| station-c | no attached branch; detached HEAD is an ancestor of main | `10d84e5ccd98` | `/private/tmp/station-c` |
| toolchain | `codex/toolchain-inputs` — merged | `8bded557ce84` | `/Users/deniskopylov/polisyos/.worktrees/toolchain` |
| verify-a | no attached branch; detached HEAD is an ancestor of main | `f1f21a474d22` | `/private/tmp/claude-501/-Users-deniskopylov-polisyos/fcedf361-81e2-42b9-8288-9f0dc9a080c7/scratchpad/verify-a` |
| verify-b | no attached branch; detached HEAD is an ancestor of main | `9776fe348f70` | `/private/tmp/claude-501/-Users-deniskopylov-polisyos/fcedf361-81e2-42b9-8288-9f0dc9a080c7/scratchpad/verify-b` |
| verify-c | no attached branch; detached HEAD is an ancestor of main | `c5389feced8c` | `/private/tmp/claude-501/-Users-deniskopylov-polisyos/fcedf361-81e2-42b9-8288-9f0dc9a080c7/scratchpad/verify-c` |
| vintage | `codex/layer-vintage` — merged | `a37254c055f8` | `/Users/deniskopylov/polisyos/.worktrees/vintage` |
| watchers | `codex/watcher-chain` — merged | `3c3db5269be6` | `/Users/deniskopylov/polisyos/.worktrees/watchers` |

### Existing worktrees outside that removal set

The complete live-directory denominator is **24 = main worktree + these 23 linked
worktrees**. Main is `/Users/deniskopylov/polisyos`. Each linked directory and its
expected `.git` file exists. None is selected by the dry-run.

| Registration | Existing directory |
| --- | --- |
| apparatus | `/Users/deniskopylov/polisyos/.worktrees/apparatus` |
| apparatus-base | `/Users/deniskopylov/polisyos/.worktrees/apparatus-base` |
| apparatus-cold | `/Users/deniskopylov/polisyos/.worktrees/apparatus-cold` |
| atlas | `/Users/deniskopylov/polisyos/.worktrees/atlas` |
| atlas-lane-base | `/Users/deniskopylov/polisyos/.worktrees/atlas-lane-base` |
| correspondence-consumers | `/Users/deniskopylov/polisyos/.worktrees/correspondence-consumers` |
| group-a-analysis | `/Users/deniskopylov/polisyos/.worktrees/group-a-analysis` |
| gy | `/Users/deniskopylov/polisyos/.worktrees/gy` |
| gy-builders | `/Users/deniskopylov/polisyos/.worktrees/gy-builders` |
| gy-corr | `/Users/deniskopylov/polisyos/.worktrees/gy-corr` |
| gy-gaps | `/Users/deniskopylov/polisyos/.worktrees/gy-gaps` |
| gy-lattice | `/Users/deniskopylov/polisyos/.worktrees/gy-lattice` |
| gy-measure | `/Users/deniskopylov/polisyos/.worktrees/gy-measure` |
| gy-phase5 | `/Users/deniskopylov/polisyos/.worktrees/gy-phase5` |
| gygaps-lane-base | `/Users/deniskopylov/polisyos/.worktrees/gygaps-lane-base` |
| gyphase5-lane-basecheck | `/Users/deniskopylov/polisyos/.worktrees/gyphase5-lane-basecheck` |
| instrument-honesty | `/Users/deniskopylov/polisyos/.worktrees/instrument-honesty` |
| instruments2 | `/Users/deniskopylov/polisyos/.worktrees/instruments2` |
| integration | `/Users/deniskopylov/polisyos/.worktrees/integration` |
| owner-residuals | `/Users/deniskopylov/polisyos/.worktrees/owner-residuals` |
| premerge | `/private/tmp/claude-501/-Users-deniskopylov-polisyos/fcedf361-81e2-42b9-8288-9f0dc9a080c7/scratchpad/premerge` |
| producers-verification | `/Users/deniskopylov/polisyos/.worktrees/producers-verification` |
| uninvoked | `/Users/deniskopylov/polisyos/.worktrees/uninvoked` |

### Off-path directory search

The search walks `/Users/deniskopylov` and `/private/tmp`, without following
symlinks, reading `.git` files and resolving their `gitdir:` targets against the
exact administrative registration. It inspects **1,537,005
directory entries across 199,035 visited directories**;
the complete visited search is the denominator for the off-path negative, not the
whole disk. It records **11,241 excluded entries/paths**
(including symlinks and excluded directory names), fully listed in the raw
receipt. Excluded directory names: `.Trash`, `.cache`, `.cargo`, `.git`, `.npm`, `.pnpm-store`, `.rustup`, `.venv`, `Library`, `Photos Library.photoslibrary`, `__pycache__`, `node_modules`, `venv`.

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
