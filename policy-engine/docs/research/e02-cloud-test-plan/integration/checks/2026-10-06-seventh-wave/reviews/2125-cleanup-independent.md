# Independent native-Trash checkpoint 12 readback

Read-only audit of `trash-checkpoint12-actions.json`; no files, refs, or worktrees were changed. The receipt records 14 moved objects. I independently summed the action allocations: **2,151,911,424 bytes**, equal to `allocated_bytes_transferred`. All 14 actions report `MOVED_VERIFIED_NATIVE_TRASH`, `native_exit=0`, and `identity_match=true`; `trash_emptied=false` and `permanent_deletion=false`.

Foundation’s `FileManager.default.urls(for: .trashDirectory, in: .userDomainMask)` resolves to `/Users/deniskopylov/.Trash`. Read-only `lstat` checks found that directory on device `16777231`; every receipt destination is directly inside it, exists, and has the recorded source device and inode. All 14 original paths are absent. For regular-file destinations, `st_blocks * 512` also matches the action’s allocated-byte value. Directory checks used only the moved directory’s inode/device, without recursively scanning the two large session records or source trees.

The 14 objects comprise 12 source/archive/fixture leaves from the prior cleanup plan and two completed superseded session logs (1,133,080,576 B and 418,988,032 B). The receipt’s 10 pre-move source-identity records cover five extracted trees (14,657 manifest-selected files total) and five archives; each reports unchanged hashes/lengths or unchanged archive SHA. The identity-preserving same-device inode checks confirm those exact objects are now in Trash.

Published-receipt readback is internally consistent: current `HEAD` and `origin/codex/e02-integration` are `1a66337192ca765968eca79733ecea4a0bf0148e`; its tree is `1cd27c888f312ef91d9cb708969ba526a7f79b34`, matching the receipt. The receipt records 154 remote-readback files with outcome `PASS`. The integration worktree is clean.

The receipt records `preserved_paths: 22` (not 24), but this field is a number rather than an enumerated path list, so I could verify the recorded count, not independently reconcile each preserved path from this receipt. The unique A11 review test remains at its original path with the expected SHA-256 `b0b02f79fe6a206309c87b849a02ec86d129f4b9458d6a35e1234842417ccf13`.

The reported allocation transfer is not reclaimed free space: the objects remain in same-volume Trash, and the receipt correctly makes no promise about immediate physical recovery.

All 14 pre-move `lsof` receipts exit 1 with empty stdout/stderr, and the receipt records release of source-copy readers. This matches no open handles at move time.

## Delta acknowledgment: preserved-path identities

After the initial readback, the receipt added `preserved_path_identity_readback`. I reconciled all **22 unique entries** to their exact paths: `lstat` existence, kind, device, and inode match for all 22; all 16 regular files also match recorded size and SHA-256. The remaining six entries are directories, for which the receipt records identity without a file hash. There were zero discrepancies. This supersedes the earlier limitation that the receipt exposed only the preserved-path count. The original 14-action count and allocation sum remain 14 and 2,151,911,424 bytes; no move or deletion was performed during this delta check.
