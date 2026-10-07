# Bounded cache/archive refresh — no new candidate

Observed 2026-10-07T17:10:18+00:00. G is at `6e8725faa42ca28c8fd72e5f8da4ca0f6e6a8f79`. Available disk space is 19.88 GiB. This refresh was limited to previously nominated old application-cache and completed C source-archive paths. No files were moved, deleted, or read from production data; Trash was not inspected or emptied.

## Previously large candidates already in native Trash

The four C2 source tar leaves are absent at their original paths. The exact native-Trash receipt `R/cleanup-20261007/C-archives-dist-1158-native.json` records `native_success=true` and `source_exists=false` for each. Their prior measured allocations were 459,878,400 B per wheel archive and 459,911,168 B per sdist archive (1,839,579,136 B total). The archive audit records the corresponding source commits/trees in Git and preserves deciding build outputs/logs separately.

The prior Bifrost cache `/Users/deniskopylov/Library/Caches/bifrost` is also absent at source. `R/cleanup-20261007/cache-trash-actions.json` records native-Trash success and source absence for that 110,092,288-byte cache. `pgrep -x bifrost` found no process; exact-path `lsof` found no matching handles.

## Decision

No fresh candidate remains in this bounded set. I did not repeat the moves. The runtime/Sparkle and Playwright/MCP items remain protected while their updater/clients are active; npm/pnpm install state was not revisited. I did not recheck the low-yield Claude/Cursor cache entries or scan other application caches. Existing modified C/D prompts and untracked C4 review outputs were left untouched.

The machine-readable exact-path checks and receipt locators are in [`cache-candidates.json`](cache-candidates.json).
