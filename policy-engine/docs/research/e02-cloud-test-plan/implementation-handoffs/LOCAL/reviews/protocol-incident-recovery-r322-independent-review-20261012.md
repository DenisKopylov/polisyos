# Protocol Incident Recovery R322 — Independent Review

Review date: 2026-10-12. Review scope: the attributed wrong-directory patch incident, the 70-path recovery state, the one-file recovery patch, and the root apply/readback helper. This is a bounded recovery review, not E02 closure or R215 acceptance.

## Verdict

**GO for a single root-authorized apply of the protocol-only patch, with two explicit safeguards.** The recovery patch is exact and reconstructs the HEAD bytes. Before invoking the helper, the root invocation must prove that its current directory is the intended checkout root (`/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`); after apply, independently read the 70-path manifest and confirm every entry is at its recorded preimage state. The supplied helper does not enforce either condition for the full manifest by itself.

The helper does enforce the expected branch and HEAD, empty index, exact source preimage, overlay hash, patch hash, `git apply --check`, and target postimage hash. It uses `Path.cwd()` as the repo root without comparing it to `git rev-parse --show-toplevel`, so branch/HEAD alone do not bind the operation to the intended physical worktree. A sibling checkout with the same branch, HEAD, target bytes, and copied packet could pass. Add that root check in the same invocation or enforce it in a wrapper before applying.

## Evidence

- At review time the checkout is on `codex/e02-unified-local-20261009` at `b214e3f5364c6ce0c081d470da8f4e0ed2560de7`; the index is empty. The working tree has broad E02 edits, which were left untouched.
- `attributed-tool-calls.json@fb155603d4d95c1845405b7b7a9354f3810b88cb6092e51542a075d8549fd4f1` records both `patch -p1 --fuzz=0` invocations at 14:19:15Z and 14:21:40Z with the physical checkout as `workdir`. The first call output lists 70 patched paths. The second call redirected patch output; the separately preserved `second-patch-replay.stdout.txt@f0957a93461b14136387f06bedd02937370280e375c0358b83a44d098d47b812` has 69 reverse prompts and shows `protocol.py` being patched forward without a reverse prompt.
- A read-only SHA walk over all rows in `r215-complete-70-path-state.json@ca0be28c1d7afb617ff905e5c0b628fe83ce4bf0298bf67e55ab3963397567b3` found 70 unique paths, all 70 matching the captured current SHA. The same complete path set has 69 entries at their preimage and one outlier: `policy-engine/src/polisyos/core/artifacts/protocol.py`. File-type denominator: 70 paths — 58 `.py`, 7 `.md`, 2 `.ts`, 2 `.toml`, 1 `.json`.
- `proposed-protocol-only-recovery.patch@e938a8512af12d8ce9da25c9982ef6f0142272728a6602e753a532d96773a069` is one path, 0 additions, 48 removals. `git apply --check` passes. Applying its single hunk in memory to the current file yields SHA-256 `a55a20f86ef529f3d81326a617f68981e6f65b9d23d06984ed7fc123b7028c8e`, byte-for-byte equal to `git show HEAD:policy-engine/src/polisyos/core/artifacts/protocol.py`. The current file is `a492819e3c2476878efd7c4695aaead44e7b7ab2bee42ca543ce85b4aaf063ec`.
- The composition packet records the same one-file net patch and postimage. Its `helper_sha256` is `60a37f5ad54c656311636a0e4379f1c1c8718ad66dfc384d19c17e2914e9ad43`, while the inspected apply helper `apply_materialized_composition.py@838d86cef78cdaf985c8260352bb7caa7d681ed6318c82f07ae52c87939cb20f` has a different SHA. The composition field does not identify a path or role, so it is not treated as binding the apply helper.

## Pattern disposition

- **P40: NEW procedural class.** The failure combines applying a patch from the wrong physical working context with patch's per-hunk reverse heuristic: 69 paths reversed while an insertion-only protocol hunk applied forward again. The class-level correction is a root-exclusive, exact-preimage materializer with explicit pre/post hashes. The materializer is close, but its physical-worktree predicate and full-set readback must be supplied at invocation/closeout.
- **P38: bounded proxy gap in the helper.** The intended property is “write the authorized worktree”; the helper tests branch, HEAD, and current-directory-relative bytes. A same-branch/same-HEAD sibling checkout with matching bytes is a divergent case. Bind the expected Git top-level path.
- **P35: the full-set denominator is established.** The complete 70-path walk shows the one non-preimage is the protocol file; the tool-call evidence records both physical-root commands. The packet proposal identifies `/root/rq10_import_oracle` as author and records the command mistake as acknowledged; the tool-call rows themselves establish command, time, and workdir.

## Apply and readback conditions

1. In the same root invocation, assert `git rev-parse --show-toplevel` equals the intended checkout path above, then let the helper enforce branch, HEAD, index, current source SHA, overlay SHA, and patch SHA.
2. Apply only the recorded net patch; do not reset, rebase, or restore other paths.
3. Read back protocol SHA `a55a20f86ef529f3d81326a617f68981e6f65b9d23d06984ed7fc123b7028c8e`, confirm HEAD and branch are unchanged, and re-walk all 70 manifest entries against their `preimage` values (including expected absences).
4. Do not claim E02 closure or R215 acceptance from this recovery.

No product source was changed by this review. No tests or runtime imports were run.
