# Q2 output-path confinement patch review (2026-10-10)

## Decision

**GO to apply and run the planned filesystem controls; this is not a closure receipt.** The patch fixes the identified static symlink-redirection class in the Q2 worker before it creates output directories. This is a new class on first finding (P40): it concerns the destination path, distinct from the earlier source/input transport boundary.

## Source boundary reviewed

- Patch: `LOCAL/linux-profile/raw/q2-output-path-confinement.patch` — SHA-256 `b0e10f4258157f592e0fd469e895cc32b52bc68ce9e512d34ea7dd9d5d229c08`.
- Baseline wrapper: `LOCAL/linux-profile/raw/final-source-linux-wave.sh` — SHA-256 `9241d6d695a27e673cd36f6416cfbf03fbc1c383368d642827d7380cfbc71d81`.
- Author note: `LOCAL/linux-profile/q2-output-path-confinement-author-note-20261010.md` — SHA-256 `47947935e0cd1fca28e219fe2f08d2588efc5ccc9958461fd4d25673f149e5c1`.

This was a read-only source review. I did not apply the patch or execute tests, worker commands, or the filesystem controls.

## Findings

The prior `test ! -e "$run_root"` followed by `mkdir -p "$run_root/orchestration"` admits a dangling symlink: `-e` is false for that target, while recursive creation follows its symlinked ancestor. The patch addresses both dangling and resolved symlinks by collecting existence, directory, and symlink predicates for each component and classifying symlinks first as refusal. It examines `/scratch`, `/scratch/e02-q2-runs`, the freeze-SHA directory, and the attempt directory; freeze SHA and attempt values are validated before use, so those variable components cannot add path separators or traversal components.

The same `q2_output_action` implementation is used by the twelve pure decision cases and serialized into the worker's stdin with `declare -f` before the quoted worker heredoc. The actual worker path calls that classifier on filesystem predicate results before output writes. Missing parent components are created individually with `mkdir` (no `-p`) and checked again; the attempt and `orchestration` directories are created exclusively with mode `0700` and checked as real directories. Existing non-directories, output targets, and symlinks are refused. The heredoc remains quoted, and filesystem commands quote the path operands; the `[[ ... ]]` predicate expansions are also not subject to word splitting or pathname expansion. I found no alternate Q2 output-creation path that bypasses this guard in the reviewed worker flow.

The classifier's checks and subsequent `mkdir` calls are not an atomic, race-free path walk. A concurrent privileged process able to rename or replace components between checks could still race the sequence. That is a bounded TOCTOU limitation, distinct from the controlled static symlink case this patch fixes; the present source review does not establish safety against such a concurrent path-replacement adversary.

## Required next evidence

The twelve pure cases establish decision-table behavior only. Before making a filesystem-confinement closure claim, run the planned actual-worker filesystem controls: a real-directory positive case, resolved and dangling symlink refusal at an ancestor and output target, non-directory refusal, and confirmation that refused cases leave the external target untouched. Then run the planned whole Q2 verification once against the frozen source.
