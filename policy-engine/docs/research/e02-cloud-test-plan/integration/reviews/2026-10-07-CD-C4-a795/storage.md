# Bounded storage candidate readback

Observed 2026-10-07T16:55:41.758043+00:00. G is attached to `codex/e02-integration` at `6e8725faa42ca28c8fd72e5f8da4ca0f6e6a8f79`, with no tracked changes. `git status` showed three unrelated untracked C/D continuation outputs; I left them untouched. The watch-state records 20.12 GiB available against the 25 GiB soft floor; `df` rounds this to 20 GiB. No physical space recovery is attributed.

## Decision

No new move candidate remains in the bounded set. The three largest completed G test-source checkouts checked here were already moved to native Trash and their original paths are absent. The next-largest was `R/1845-DOE-checks/source` (62,005,248 allocated bytes), also already transferred under the same receipt. Their exact source commits/trees resolve from the existing local `origin/*` tracking refs, and all source entries were previously manifest-bound to those Git trees. This audit did not fetch remotes. The four newer F35/B53 leaves are also already recorded as transferred, so I did not re-nominate them.

| Already-transferred source copy | Allocated bytes at preflight | Retained source | Current disposition |
|---|---:|---|---|
| `R/1800-Bcas-checks/checkout` | 62,795,776 | `5ece606e` / tree `ff36af87`, refs `origin/codex/e02-B-current-cas-generation` and `...-coordination` | Trash receipt `trash-checkpoint12-actions.json`; no non-bytecode extras. |
| `R/1910-A11-checks/checkout-retry` | 62,078,976 | `905820ce` / tree `98405fab`, ref `origin/codex/e02-A-full-queue` | Trash receipt; only three zero-byte `root.lock` extras. Unique A11 deciding evidence remains outside the checkout. |
| `R/1910-A11-checks/checkout` | 62,058,496 | `905820ce` / tree `98405fab`, ref `origin/codex/e02-A-full-queue` | Trash receipt; all manifested files match Git; unique A11 deciding evidence remains outside the checkout. |

`trash-checkpoint12-actions.json` records 14 successful native-Trash actions, including all 12 exact source/archive/fixture leaves, with 2,151,911,424 nominal allocated bytes. Its source-checkout handle checks returned no open handles at that time. This report did not repeat the move or empty Trash. `completed-F35-B53-source-native.json` separately records four already-moved source copies (182,996,992 nominal bytes); these are excluded from the candidate list.

## Worktree and retained-code state

`git worktree list --porcelain` shows only the main checkout, the current A delivery checkout, four current C checkouts, and G; no inactive registered A/C/G checkout remains. The largest older roots in prior inventories (`e02-a-full-queue` ~6.905 GiB, `e02-a-compiler-full` ~2.06 GiB, `e02-a-replay-full` ~1.38 GiB) already have verified native-Trash receipts and are absent at their source paths.

Some earlier retired A/C commits still hold useful differences outside main/G. Local refs `refs/heads/codex/e02-C-catalog` (`dfaadaac`), `refs/heads/codex/e02-A-custody` (`289571b0`), and `refs/heads/codex/e02-C-hygiene` (`b56ec6b1`) resolve and are not ancestors of main or G. The prior workspace audit records the precise deltas: C catalog has seven old installed-consumer receipt files and source/test differences; A custody has a runtime/test delta plus 22 assessment/evidence paths; C hygiene has two old handoff evidence files and remains relevant to held LA-018. Keep these refs and ask the canonical owners to compare/port specific paths from Git if still needed. The checkout is not required to preserve that work; do not delete refs or run `git gc`.

No production payload, symlink target, global scratch/home area, or Codex session inventory was scanned. Exact process/attachment status was not re-enumerated; immediate source paths are absent, and the parent should do a fresh identity/handle check before any future move.

G root correction: перечисленные untracked C/D outputs были текущими owned G review/prompt drafts, созданными родителем, а не чужой пользовательской работой. Они входят в эту документационную публикацию. Ни исходники чужих lanes, ни active worktrees не перемещались.
