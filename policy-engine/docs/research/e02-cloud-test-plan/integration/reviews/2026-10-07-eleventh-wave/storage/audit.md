# C2 installed archives and package outputs: cleanup readback

Snapshot: 2026-10-07T11:52:40Z UTC; G `codex/e02-integration` at `855cb26a7a2c9fea60356663cf81e7d01e20c738`; tracked tree clean.

This is a bounded read-only inventory of the old C `raw/installed` outputs. It does not recheck the 20 candidate.tar or 26 extracted-source leaves already recorded as native-Trash moves. It skips `canon` and never follows symlinks or enters production data.

## Exact remaining source archives

The four source tar files below are two exact duplicate pairs. Their content hashes and the paired extraction comparisons are from the completed prior archive audit; this pass checked current existence/stat identity only. The two candidate trees are different from one another, but each exact source snapshot is retained in Git objects and named refs.

| candidate commit / tree | exact paths | per-file allocated bytes | SHA-256 from prior audit |
|---|---|---:|---|
| `1e8aa374829884fcab9b6eca6616c5a7df4beb16` / `23e5b56e2a42a652770a698a4259a23f4a41277e` | `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene-1e8aa-954078/wheel_source.tar`<br>`/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene-1e8aa-954078/run2/wheel_source.tar` | 459,878,400 each | `0683dc215abd2b9929756992222899b20419a2fb38c8124fb8eaaab72d89ff41` |
| `95407808d90bd7c5c7ca7898a8423fe6d4ee9180` / `77424caabdb0a4e0cdd7b6160de9beacceb944bf` | `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene-1e8aa-954078/sdist_source.tar`<br>`/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene-1e8aa-954078/run2/sdist_source.tar` | 459,911,168 each | `58a2ad52516759e0dfdf9241a1d16c321c6a53d069bf3e2b8c2815555cfd6b98` |

Total for these tar files: **1,839,579,136 allocated bytes**. Recommended disposition: **GO to native Trash**, after parent reads this report. Their role is reproducible source input to package builds; they contain no unique code, docs, or production data. Preserve `hygiene-1e8aa-954078/run2/archive-build-results.json`, its extant archive stderr/build stdout/stderr logs, and test/census receipts. The two archive-command stdout paths named in that JSON are absent; their bytes are still represented by the extant tar files and match the receipt hashes per the prior completed hash pass. If the tar leaves are moved, those original bytes leave local storage; regenerate them from the pinned commits/tree for a later exact test.

## Rebuildable package outputs

The bounded scan found **24 `dist*` directories and 67 regular files**, with **1,699,815,424 allocated bytes** (directory metadata excluded). These are generated `policy_engine-0.1.0` wheel/sdist outputs and one 4 KiB attempt sentinel. They contain no unique source/doc/data; source candidates are pinned in Git. No symlinks were followed.

| exact dist directory | source candidate commit / tree | files | allocated bytes |
|---|---|---:|---:|
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/berl/dist` | `999f56c443e3b4ef74d849828641836a8f335b3d` / `20c78ec995bc8ff8f932cb262dce118283d3322d` | 3 | 80,236,544 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/berl-87999/dist` | `87999f69c5f99d69ee2622ef00cd7f4e04d7d572` / `0280403e6837c5b220ac748a7674f4e5830ba0ab` | 3 | 80,236,544 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/berl-87999/dist-attempt1` | `87999f69c5f99d69ee2622ef00cd7f4e04d7d572` / `0280403e6837c5b220ac748a7674f4e5830ba0ab` | 1 | 4,096 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/cat-180bb/dist` | `180bb931ab96cd5f40c1f91c092d24375456d50f` / `dc073387ab5b08b77c007286079ff695a886d403` | 3 | 80,236,544 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/catalog-8dfa/dist` | `8dfa7f3c544461c0ff081861848fcc5d8523da5b` / `3eac9b5cf816e30f9c1bacc81d80e2dc75d81681` | 3 | 80,293,888 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/dfi-12190/dist` | `12190b1e8a25a6e9c2edc3b9c08f106e76ea5b63` / `fcfe8de3a6cbc0dd1c0df1d02b65cc2d7c1cee04` | 3 | 80,236,544 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/dfi-ab441/dist` | `ab44166335130463178e65dfc29a252c96afe479` / `b1eaa06c81fae89d56ae467e8036d5923b886f3d` | 3 | 80,269,312 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene/dist` | `cf8cb9d74973a63b98cc202425686894a8d1e92e` / `fe4ed5b6e2369a73376f9e66c99f0b99d5013ce9` | 3 | 80,199,680 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene/dist-clean` | `cf8cb9d74973a63b98cc202425686894a8d1e92e` / `fe4ed5b6e2369a73376f9e66c99f0b99d5013ce9` | 3 | 80,199,680 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene/dist-from-sdist` | `cf8cb9d74973a63b98cc202425686894a8d1e92e` / `fe4ed5b6e2369a73376f9e66c99f0b99d5013ce9` | 2 | 15,020,032 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene-1e8aa-954078/run2/dist-sdist` | `95407808d90bd7c5c7ca7898a8423fe6d4ee9180` / `77424caabdb0a4e0cdd7b6160de9beacceb944bf` | 2 | 65,228,800 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene-1e8aa-954078/run2/dist-wheel` | `1e8aa374829884fcab9b6eca6616c5a7df4beb16` / `23e5b56e2a42a652770a698a4259a23f4a41277e` | 2 | 15,020,032 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene-root-followup-f0940f/dist` | `f0940f021f76264c288789e472a9d4681d7f6680` / `a436620d590564c2c8b81761ff4a179e6d68caab` | 3 | 80,207,872 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/ing/dist` | `1eb32f013308de34d77572dd4af8ca048b2b9ee3` / `6a5db17ef6221243869e1d52ca5200f37a015f54` | 3 | 80,211,968 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/ing-successor-68eed/dist` | `68eed6d56f48e9a676edeb3251902300a64d5fad` / `0d0163f817c7b697e18f96c0056076a7360b8e8f` | 3 | 80,216,064 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/mig-004ae11/dist` | `004ae11f1a541e2035f71cefa92f89b71bd8f562` / `5369c0167bc63096a12ee1bea666b42c837ea78b` | 3 | 80,248,832 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/mig-5a72/dist` | `5a72f76b360e2635d06cee791c51f6e7100bc501` / `e18e810747b84a59d6c37453f8eb213438c98850` | 3 | 80,203,776 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/mig-c62/dist` | `c62f5f27c5a165316a5428806993e3f524caae85` / `215ee4ddbe40db5252581556643276b50bd77052` | 3 | 80,224,256 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/mig-cf281/dist` | `cf28194b9fa28bbeb97ac5e2792becbda84f4cc0` / `7d129fcb9f7d3ddfa9dfeaee180284675202c292` | 3 | 80,224,256 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/obs-5a75/dist` | `5a75b004e0d17c80f1d156df84db7a12a9274c9e` / `3602443723a9a57b1a988ae3933b2d1d7c17f2bc` | 3 | 80,203,776 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/plg-a452/dist` | `a452011da3de26d90877ae95ab10a72cce8e0b45` / `d35c3e132b930eb7b9512ab7314a5f94c4733d3a` | 3 | 80,211,968 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/schema-8ac2/dist` | `8ac2c232445eb78b1689fe2f6fb5e1830ccd5b35` / `ec6137a453d3aafdfd46e1c6304e4cf3a9de3da5` | 3 | 80,220,160 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/schema-b8/dist` | `b8d9115cdc6a55920c1e0a3cae2e5f9092010c27` / `467cd6f01ec204767dc60bb939955578428bf102` | 3 | 80,244,736 |
| `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/scl-01c/dist` | `01c303c2a94a1ff281e4fcc9804db60183e65d68` / `7bf3e8dda2bb1179b9960ffb3c5be5a5fb8e101f` | 3 | 80,216,064 |

Recommended disposition: **GO to native Trash for only the exact listed `dist*` directories**. Keep the small `archive-build-results.json`, package census/command-results, all extant stdout/stderr, and deciding test receipts. The special `run2` receipt records package artifact SHA-256 values; hashes preserve identity, while future package tests can regenerate the bytes from the exact candidate and build recipe.

## Active-use and preservation

`lsof` found 0 open file-handle records for all four source tar files and all 67 package files; the process-cwd scan found 0 cwd under `raw/installed` at this snapshot. This does not promise future or cwd-independent access is impossible. No file was moved, deleted, or rehashed here.

Prior receipts show 20 candidate archives and 26 source extraction leaves already moved to native Trash; this pass relied on those receipts and did not revisit their old paths. `canon/source` remains an explicit protected/unmapped boundary. The current C/G worktrees, active fixtures, production inputs, deciding outputs and receipts remain untouched.

Combined metadata allocation for the remaining tar inputs plus the bounded package files: **3,539,394,560 bytes**. This is stat allocation, not a claim about APFS physical-space reclamation. The previous audit’s aggregate `build_outputs` estimate was 1,780,020,674.56 bytes; this exact readback totals 1,699,815,424 file-allocation bytes over 24 roots / 67 files, and does not attribute the difference.

Machine-readable exact inventory: `storage-archives.json`.
