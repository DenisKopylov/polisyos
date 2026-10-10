# Independent review: Q2 owned bare-origin patch

**Disposition: READY TO APPLY for the narrow store-identity and transport-size measurement property.** Review was read-only; no helper, source, worker, or Git state was changed, and no tests, builds, installs, or container commands were run.

## Reviewed inputs

- Candidate patch: `LOCAL/linux-profile/raw/q2-owned-bare-origin.patch` SHA-256 `a6423ad48b484bd99e096749815676d99804612feaac17fdc90f1e08992854be`.
- Candidate note: `LOCAL/linux-profile/q2-owned-bare-origin-patch-note.md` SHA-256 `797dd2fd39ccd91d14712a7215c18a277a50a7b401d50d09bbbd780242055090`.
- Exact patch target: `LOCAL/linux-profile/raw/final-source-linux-wave.sh` SHA-256 `cc17a395e38fee53d67fe3c4fb6c69ac56bcaed63c91abca705cd462cc589ffb`.

## Finding and decision

The frozen helper currently measures `"/scratch/e02-$E02_FREEZE_SHA.git"`. The actual Linux bare store is deliberately anchored to the original 7574 import path, `/scratch/e02-7574c864a605c50efc033b966807790cbd8d1781.git`, while its ref has advanced to the 13e411 freeze. Therefore the freeze-derived measurement path does not identify the extant store established by the receipts. The patch replaces it with the attached checkout's effective `origin`, requires that URL to equal the exact receipted bare path, then uses that verified path for `du`.

The inserted checks run before the Q2 `run_root` is created. They fail closed unless the origin is exact, the bare directory exists and is not a symlink, its root is uid/gid `0:0` mode `700`, Git says it is bare, the ref/branch/commit/tree match the requested freeze, its only shallow boundary remains the original 7574 SHA, and the bare object store has no alternates file or symlink. A different origin, network URL, alternate store, wrong freeze/ref, changed boundary, or store indirection fails before output creation. After these checks, the size measurement uses the verified origin and the fixed attached checkout.

The earlier frozen transport helper still supplies the surrounding controls: `q2` validates the source freeze and attempt token, refuses an existing `run_root` before creating it, and does not create or clone any Git store. Before entering the worker heredoc it checks the fixed container/image/mount set, frozen lock-file hashes, the root Python/Hatchling and DoWhy Python/version pins, `uv pip check`, and runner input hashes. Those checks precede the new store preflight; the new patch neither weakens nor bypasses them.

## Existing evidence bound to the property

The source-update receipt is `LOCAL/linux-profile/linux-source-update-13e411da-20261010-receipt.md` SHA-256 `366e34a53efff09651eabd71a7fa40bdf67e120d9e320d8863155c4d0d573a2f`. It records an append-only compare-and-swap from 7574 to 13e411 in the existing bare store and fast-forward of the already attached checkout, with no new clone or cleanup.

The retained actual commands independently establish the current relation:

- `LOCAL/linux-profile/raw/actual-update-13e411da-20261010/03-worker-update.command.json` SHA-256 `92312978c50f931aca0a3cda09700257dbec9dc655d239b28697b6c33c427e08` binds the update operation to `/scratch/e02-7574c864a605c50efc033b966807790cbd8d1781.git` and `/workspace/polisyos`. Its stdout SHA-256 is `815f3748041774c33d973091ecf10047c118610db86c55872d177f652d761fbf`: the bare ref and checkout advance to 13e411, while both shallow files remain exactly 7574; the source update used the existing origin and performed connectivity checks.
- `LOCAL/linux-profile/raw/actual-update-13e411da-20261010/04-post-readback.command.json` SHA-256 `f26d04343523b661127b19a8322aa8264afc77b17e924c999af0447dae41b96d` independently reads back origin, refs, shallow files, alternates, connectivity, locks, manifest, and runtime profiles. Its stdout SHA-256 is `e796ae56e72401dcf8c497618c442a90a7742927c166f1633511ae7a1d73c94d`: it records origin as `/scratch/e02-7574c864a605c50efc033b966807790cbd8d1781.git`, both Git stores at 13e411, both shallow boundaries at 7574, no alternates, clean checkout, all five lock pins, and the expected Python/Hatchling/DoWhy versions with both environments compatible.

Together the patch and these receipts bind the path being measured to the already-owned store that actually backs the checkout, rather than to a path inferred from the newer source SHA. The regression falsifier is a checkout whose origin is changed to a network URL, a different SHA-named store, or any other path: the new preflight must reject before creating the attempt directory. Existing recorded positive evidence covers the exact accepted relation.

## P40 classification and limit

**P40 bucket: SAME store-identity/provenance class, one level deeper.** The earlier transport finding was that a requested clone mode did not identify the actual object store. This finding is the same category: an expected SHA-derived pathname is not proof of the extant store's identity after an append-only source advance. The repair widens the identity mechanism to derive the measurement path from checkout origin and bind it to the receipted existing store; it is not another freeze-specific pathname exception.

This is a source review plus retained receipt review, not a fresh worker preflight. It does not claim that the Q2 wave ran or that the candidate patch was applied. The authorized next step remains applying this exact patch to its stated helper hash, reading the resulting helper hash back, then having the owning lane perform its separately gated worker preflight/wave.
