# Independent live review: Q2 owned bare-origin admission

**Result: READY for the narrow admission/measurement property.** The exact admission block from the applied helper passed against the existing owned worker. Four controlled response substitutions failed closed before the post-admission marker and `du`. No Q2 tests, build, install, output-directory creation, source/config/ref/mount change, or Git mutation was performed.

## Frozen inputs and live target

- Applied helper: `LOCAL/linux-profile/raw/final-source-linux-wave.sh` SHA-256 `86ca3a0dab8ba5187f14ef925724b5e9114b84f0ab9152d3e5b2a2e44cf8ef60` before and after the probes.
- Live worker identity was read before and after: container `88c8824b3970ef929473daf73cda2e50083b2035f5b725071acf8a829fa5b0c6`, image `sha256:dc53af52cf658aa04401244105cd63b25a7dfd42a6c5125683710b553d8d263f`, running. Before/after command and full stream captures are in `LOCAL/linux-profile/raw/q2-owned-bare-origin-admission-20261010/`.
- The source block was extracted byte-for-byte from the applied helper's Q2 worker heredoc, ending immediately before the `handoff` assignment; its SHA-256 is `e7c8eff47b0ece5fede7a52536e5aa0716c9be9901e9af7789ed943426b5e016`. The live request used the receipted 13e411 SHA/tree and branch.

## Results

The positive run exited 0. It observed both checkout origin and selected bare path as `/scratch/e02-7574c864a605c50efc033b966807790cbd8d1781.git`; the checkout and bare store both read back at commit `13e411da7d9e505856fc336b3d25fd0aabdb1f66`, tree `8d8c4082febf1676dd86084106f3266d8b2131a3`, branch `codex/e02-unified-local-20261009`, with shallow boundary `7574c864a605c50efc033b966807790cbd8d1781`. The applied admission checks therefore accepted the store whose identity the append-only transport receipts establish. The exact corrected size command ran read-only and reported 194,755,112 bytes for the bare store and 873,506,042 bytes for the attached checkout. Positive record: `positive-live.command.json` SHA-256 `03bd544b2d09a1463626c0207fdeced18b7efd2c20133fae4a43c70d9e92d234`; stdout SHA-256 `d12e50e85f8aa3904dc1ef35deabbb0bdd718fe8334be14c619e549ed8762090`; exit 0.

The controlled cases used a shell `git` function that substituted only the selected command response; all other commands in the extracted source block delegated to the real Git executable. These are negative controls, not production-state claims:

| Control input | Result | Downstream marker / `du` |
|---|---|---|
| HTTPS origin response | exit 1 at exact-origin check | not reached |
| Confirmed-absent `/scratch/e02-q2-origin-control-not-present.git` origin response | exit 1 at exact-origin check | not reached |
| `core.bare=false` response | exit 1 at bare-config check | not reached |
| all-zero `rev-parse HEAD` response | exit 1 at freeze SHA check | not reached |

The confirmed-absent path control records its in-container absence check before injecting the origin response. Its stdin, argv, complete stdout/stderr, and exit are retained alongside the other cases. An earlier path-like dangling-origin control also appears in the raw directory; its check ordering did not emit the absence assertion, so the separately named `control-dangling-origin-confirmed` run is the evidence for absence. It produced the expected origin mismatch failure.

The complete command/stream inventory is indexed at `LOCAL/linux-profile/raw/q2-owned-bare-origin-admission-20261010/probe-index.json` SHA-256 `37662cc152333709182c4467de04073594369ac5e6cd3bf60493636c43204a1e`. Each per-case command JSON retains its full stdin and argv and hashes its separate complete stream/exit files.

## P40 and boundary

**P40 bucket: SAME store-identity/provenance class, one level deeper.** The applied mechanism now derives the measured path from the checkout's effective origin, binds it to the original owned bare path, and checks the freeze and retained shallow boundary. The live positive and altered-origin/non-bare/wrong-SHA controls exercise that generalized admission property.

This is admission-only evidence. The helper did not create `run_root`, enter the test drivers, or perform any package work; the root-owned serialized Q2 heavy wave remains unrun and requires its separate grant.
