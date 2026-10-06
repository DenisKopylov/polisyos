# Cleanup mover static safety review v1

**Verdict: NO-GO for execution.** Reviewed `move_released_to_trash.py` SHA-256 `2cdcc07cfea69f7322e0c987c403952f03923ed61fc08a04e46bbab12be974df` against current selection SHA-256 `57433facf86c98a9a6c567422d80a4f0f2b4229122a8d820c544c2b95bf3560f`. The mover was not invoked and no path was moved.

The current v2 selection is held (`NO_ACTION_ALL_CANDIDATES_HELD`, `trash_authorized_now=false`), and the current script rejects it in normal Python at lines 23–24. That guard is not sufficient for release readiness.

## Blocking findings

1. **Critical — optimized Python removes every safety check.** All gates use `assert` (lines 18–34, 47–108). `python -O` or `PYTHONOPTIMIZE` strips them, allowing unchecked target/path values through to `mkdir` and `rename`. Replace all safety asserts with explicit failures and reject optimized mode.
2. **High — source extraction candidates lack provenance and category authorization.** The selection has 23 `source_archive_extraction` candidates; no category allowlist restricts release to repeatable test directories/environments. Sibling archive existence does not prove an extracted tree is unchanged or unused. Keep these preserve-only unless content equality and owner release are proven.
3. **High — exact C-root confinement is not bound.** The mover does not load/verify the source inventory path/SHA. It trusts release-supplied roots and checks only the broad worktrees prefix. Its symlink loop stops before checking `owner.parent` (lines 75–78). Bind the frozen inventory’s exact admitted roots and lstat every path component through the trusted roots.
4. **High — audit completeness remains self-attested.** `owning_audits_complete` and `all_deciding_outputs_and_useful_changes_committed` are booleans; retained Git refs need only be nonempty and hash-valid; `frozen_topics` is not required to be complete/nonempty. Compile and verify the exact expected topic/evidence set against frozen branch/HEAD state.
5. **High — caller-controlled receipt path can overwrite existing data.** `output_path` is unrestricted and `save()` truncates it. Confine it to a fresh unique cleanup receipt path, reject overlaps, and create it exclusively.
6. **Medium — preserve-reference check is path-existence only.** `Path.exists()` follows symlinks and no reference identity/content is bound; a reference could be a symlink/replacement or another released candidate. Use lstat/content binding and a global no-overlap check.

## Bounded recovery residual

A crash after rename but before saving the move record leaves the directory in Trash without a receipt entry; rerun refuses the existing target and cannot reconcile. The item remains recoverable, but the operation needs idempotent reconciliation or a documented manual recovery step.

The script does perform useful normal-mode checks: selection-hash binding, candidate ignored/untracked checks, owner/type/device checks, nested-candidate rejection, and immediate pre/post rename inode checks. These do not close the findings above.
