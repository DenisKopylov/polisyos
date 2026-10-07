# C source-extraction delta readback

**Result:** all 25 mapped source leaves contain no unique code or documentation delta. Each exact candidate commit resolves to the candidate tree recorded in the prior audit. I hashed 332,790 source, test, human-documentation, configuration, and structured-file instances against their mapped Git blobs and modes; all 332,790 match. No source patch or unique file needed preservation.

Seven package-shaped extracts are intentionally smaller than a repository root: six contain only `policy-engine/` and omit 28 root-level files; `hygiene/source-from-sdist` contains the package sdist layout and omits 5,106 files outside that package subset. Files within their package scope match their candidate trees.

There are 272 large tracked derived JSON outputs. Their exact Git paths/blob ids/sizes are in `extraction-delta-readback.json`; their local copy bytes were not re-hashed in this bounded source/doc pass. The prior audit verified sibling source archives, and the candidate commits provide the regeneration source.

Untracked files are generated cache/package metadata. Two hygiene leaves each contain a uv `archive-v0` with 3,447 files (67,677,620 logical bytes). Of these, 3,441 files match candidate Git blobs. One TOML resource and the wheel LICENSE are byte-equal to tracked files at their canonical paths; the remaining four files are generated wheel metadata (`RECORD`, `WHEEL`, `entry_points.txt`, `METADATA`). The 14 `.tmpl`, four `.typed`, and two `.retired` source/template markers also match candidate blobs. An additional metadata-only pass found 82 untracked non-source/doc files (812,997 logical bytes), all uv cache/interpreter markers or a generated sdist `PKG-INFO`.

`production_data` was never traversed and no symlink target was followed. The scan pruned 184 `__pycache__` directories and two symlink directories. The single nested `.git` in `schema-b8/source/policy-engine` is a clean, one-commit synthetic archive repo; its tree equals the candidate commit’s `policy-engine` subtree exactly (14,959 packed objects, 98,992 KiB pack). It has no extra history or dirty source. This pass did not inspect active processes/open handles; root should do that before moving the leaves to native Trash.

**Recommendation:** all 25 mapped leaves are eligible for root-managed native Trash once the active-reader/handle check passes. The unmapped 26th leaf is outside this audit and remains governed by its prior identity hold.

Initial extra-file preservation created redundant copies under `preserved-extraction-deltas/` (6,896 files, 134,588,373 logical bytes; observed `du` 146,440 KiB). These copies are generated/recoverable and are not needed to preserve unique source. This audit did not move or delete them; root may move that exact ignored directory to native Trash after reading this report.

Readback detail: `extraction-delta-readback.json`.

Final action: all 25 mapped leaves and the redundant copy directory were subsequently native-Trashed by G after fresh process-path and lsof checks. The original audit JSON and old-C preservation manifest remain in ignored G evidence; the complete native outputs are published alongside this note.
