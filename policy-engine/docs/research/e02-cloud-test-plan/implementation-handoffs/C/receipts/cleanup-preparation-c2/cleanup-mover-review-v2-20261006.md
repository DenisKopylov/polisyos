# Cleanup mover static safety review v2

**Verdict: NO-GO for release.** Reviewed `move_released_to_trash.py` SHA-256 `a7cf26e37c2272671974ad589aa1b326b95e0905f9bcaface3145a0c005b450f` and held selection SHA-256 `57433facf86c98a9a6c567422d80a4f0f2b4229122a8d820c544c2b95bf3560f`. No valid release input was used; no Trash target or move was created.

The two authorized fail-before-side-effect controls passed:

- Optimized invocation (`python3.14 -O -B` with no arguments) exited 1 at the explicit optimized-mode guard.
- Normal invocation with the held v2 selection plus synthetic affirmative release metadata exited 1 at the selection-decision gate; the output receipt and unique Trash target remained absent, and the sample candidate inode/device stayed unchanged. Full argv, stdout/stderr, exit/time, and script hash are in [`negative-precondition-controls-v2-0ccb29b1f100.json`](./negative-precondition-controls-v2-0ccb29b1f100.json) with raw streams beside it.

## Remaining blockers

1. **High — extracted source trees can still be released.** The selection contains 23 `source_archive_extraction` items, while the mover has no category allowlist or tree-content/consumer check. An adjacent archive does not preserve edits made after extraction. Keep these preserve-only unless exact content and no-consumer evidence is bound.
2. **High — admitted roots are caller supplied.** Canonical path checks are present, but the mover does not load the source inventory or bind its hash/root list; `exact_admitted_C_roots` comes from release JSON and the path prefix is broad. Bind the current inventory and require its exact admitted root set.
3. **High — audit completion can be declared with incomplete evidence.** Release booleans are self-attested; Git object hashes/bytes are checked but the list only has to be nonempty, and `frozen_topics` has no complete expected set or nonempty check. Compile and validate the complete root-owned topic/output evidence set.
4. **High — receipt path can overwrite arbitrary files.** `output_path` is caller controlled and `save()` truncates it. Confine it to a new unique cleanup receipt with no overlap or symlink ancestry.
5. **Medium — preserve refs are checked by existence only.** `Path.exists()` follows symlinks and does not pin identity; a ref may be a symlink/replacement or another released candidate. Bind lstat/content identity and prove global nonoverlap.
6. **Medium — selection does not pin candidate identity.** The pre-rename inode check catches changes after preflight, but the preflight inode is not compared with the final selection’s recorded identity. Bind device/inode in the selection or hold the candidate.

A crash after rename and before receipt update still leaves an unrecorded move; the object remains recoverable in Trash, but the script cannot reconcile it on retry.

The previous assert/optimized-mode and held-v2 selection escapes are closed at this SHA. Static checks found zero `assert` AST nodes.
