# R1275 — targeted reusable-artifact disk assessment

**Disposition: no safe cleanup target is established.** The exact source frame is HEAD `a746e1b0b1fab1b9ae027c1c4b55eea67f95e02d` / tree `1355896e91789026d21396d2b087c63827ab251b` at `root-author-source-frame-r1267-20261014.json` (`a5403a64bcbac9d3a3038396d828bc018fcd96f348060f2150e38a89f7405803`). The frame records 590 source postimages; tracked worktree and staged counts are both zero.

The direct `df -k .` capture showed 16,930,544 KiB (16.15 GiB) free at 92% capacity, below the 18 GiB threshold. The parent’s earlier 15.3 GiB reading differs; both readings are below threshold. No file was moved, deleted, sent to Trash, or permission-changed.

I followed only the earlier disk receipts and exact paths they named, plus the generated-schema drift fixture documented by R1259. I did not inspect home storage, production data, other worktrees, dependencies, caches, or model payloads. One filename-only `rg --files` query over `LOCAL/raw` expanded to 1,696 fixture path names because “symlink” occurs in many paths; it did not open payload contents. All measurements below were then restricted to receipt-named paths.

## Candidate findings

- **B05 V4 overlay:** `LOCAL/raw/b05-generic-simulation-20261011-v4-final/overlay` is mode `0444`, owned by `501:20`. `du -sk` and `lsof +D` could not establish a complete size or no-user state because the overlay is not traversable. Its exact 233,478-byte patch (`6c4a07cd…`) and manifest (`1cf0e316…`) remain available; the manifest’s pinned base commit `7296a020…` exists and is an ancestor of the current branch, and all nine manifest path states match that old base. However, 0/9 current files match either the old preimages or candidate postimages. Keep it as historical source work and because B05/V6 receipts still cite it; do not change permissions. The manifest-named hidden staging path is absent.
- **`can-candidate`:** current allocated size is 127,772 KiB; the bounded no-follow metadata walk found 5,287 regular files and 613 child directories (119,356,467 logical file bytes). No open PID was observed, but the earlier receipt identifies it as active source work and no exact patch/manifest basis was established. Keep.
- **R1260 generated-snapshot drift fixture:** the copied `snapshots/` tree occupies 28 KiB and has 112 symlinks to existing canonical snapshot files plus one 26,454-byte corrupted schema copy. The current canonical ABMResult schema still matches the recorded original hash; the corrupted copy and failing `--check` output match the R1259 control receipt. No open PID was observed. Keep: it is unique semantic-removal evidence and too small to matter for disk recovery.
- **Worker transport bundles:** the two receipt-cited local bundles are 918,688 bytes and 35,190 bytes (958,464 allocated bytes combined), with hashes matching the prior transport receipts. No open PID was observed for either file, but both remain cited inputs to append-only worker updates. Keep.
- **C05 pytest tree:** allocated size is 124,884 KiB (126,556,082 regular-file logical bytes; 70 symlinks not followed). No open PID was observed. The current replacement replay plan still says `prepared_unrun_prefreeze_composed` and has no completed commands, so this old output remains the deciding fixture. Keep now; it is the top conditional reconsideration after the replacement replay is completed and reviewed.
- **Receipt-named temporary roots:** the exact `pytest-of-deniskopylov` root is 25,088 KiB (24.2 MiB logical regular-file bytes; 54 symlinks not followed), with no open PID but no complete current run ownership map. `policy-engine/_build` is 88,312 KiB, `policy-engine/src/_build` is 3,732 KiB, and `policy-engine/_build/.tmp` is 12 KiB; no open PIDs were observed. The R1221-named `_build/.tmp/last-mile` directory is absent. Keep; their obsolescence and safe recreation are not established.

## Recommendation

There are **zero safe reclaimable bytes now** among the inspected candidates. The largest conditional target is the C05 `pytest-tmp` tree (124,884 KiB), but only after a replacement composed replay is actually completed and reviewed and the retained evidence is confirmed unnecessary. The slightly larger `can-candidate` remains active source work; B05’s full size is unknown and its current users are unproven. The schema drift fixture and transport bundles are tiny. Prior disk receipts report the repository and native Trash are on the same device; no Trash operation was performed.

P40 bucket: this is the same disk-preservation class one level deeper, with exact R1260 drift and transport artifacts added to the bounded target set. It does not support a generic cleanup rule or a broader storage census. `closure_ids: []`.

## Receipt references

- R392 disk-preservation review: `reviews/disk-preservation-proposal-r392-independent-r1-20261013.md` (`aaea7b3d…`) and JSON (`b8a544c8…`).
- Prior owned-scratch audit: `decisions/disk-lifecycle-owned-scratch-20261011.md` (`55e20604…`); worker bundle disposition: `decisions/disk-safe-candidates-20261011-v3.md` (`8a4009be…`).
- R1259 schema-companion review: `reviews/r1259-complete-canonical-schema-companions-independent-20261014.md` (`b25cad01…`).
- Q2 temporary fixture path review: `reviews/q2-filesystem-controls-independent-20261010.md` (`5717ee20…`).
