# Verified native Trash transfers — 2026-10-07

59 objects were moved with the macOS native Trash API and verified by inode/device, destination match, and source absence: 12 old C checkouts, nine completed environment leaves, twelve paired worktree-admin directories, 25 mapped source extracts and one redundant audit cache-copy directory. All retained branch refs were read back before/after the old checkout retirement; no branch/history removal, Git prune/gc, Trash empty or production-data census occurred.

Observed allocated tree sizes total **26,153,377,792 bytes** for the 47 source/environment/extract/copy objects; paired admin sizes are outside that total. These are observed allocations, not physical space reclaimed. Free space measured after transfer: **23.53 GiB**. Same-volume Trash holds the bytes until the human empties it; G never does so.

Complete native deciding outputs: [checkout/environment](C-old-and-env-1008-native.json), [paired administration](C-old-admin-1008-native.json), [source extracts/copy](C-extractions-1116-native.json).

Source preservation: 299 retained old-C files (15,523,426 bytes) were rehashed before checkout moves. For 25 mapped extracts, 332,790 source/test/human-doc/config/structured instances matched candidate Git blobs and modes, with no unique delta. Seven package-shaped layouts were bounded explicitly. The nested clean one-commit Git archive exactly matched its candidate subtree. Two uv archive copies and package/timing metadata were classified as generated/recoverable. The 272 large tracked generated JSON copies were not rehashed in that bounded pass; pinned blobs and independently verified sibling source archives were kept. Production payload/symlink targets were not walked.

The unmapped `canon/source`, current A/C roots, active G runtime, raw deciding receipts and sibling source archives remain preserved. Further caches are candidates only, pending active-user checks.

Operational exception: helper risk_canonical mistakenly created two ignored dependency reports in the primary checkout, copied their identical contents to G, then unlinked the two primary copies. That violated the native-Trash-only rule even though their contents remain preserved in G; no tracked source or ref changed. The exact paths and clarification are retained in G ignored provenance. No permanent deletion was used for any of the 59 cleanup objects above; no additional unlink cleanup is authorized.
