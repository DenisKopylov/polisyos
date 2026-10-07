# G intake identity queue — 2026-10-06 20:34

Read-only census pinned to `codex/e02-integration` `ff277db7798fc312654704fa51c52e00f53f10f4`; all 35 topic heads and trees are fixed in `queue.json`@sha256:3e6fe563a7dfc0b5b26a535e7bad44e37f49f49c0b30429ce4ec9cbceec036d6 (G-local ignored; full path view reconstructible from the cited Git refs). Read the complete `AGENTS.md` and E02 `HANDOFF.md`; checkout is attached and tracked-clean. No refs, source, archive/worktree, environment or tests were changed.

The intake has 23 refs with a prior review pin and 12 without one. **Correction (2026-10-07):** the earlier resolver was wrong to prefer `watch-state.json.reviewed_head_decisions[*].reviewed_transport_head`. For 16 refs that decision points to a stale earlier transport head; `full-reviewed-head-delta.json.previous_reviewed` agrees with `watch-state.json.reviewed_through_heads` and the later seventh-wave source-review records. The corrected `queue.json` now uses those newer review pins and recomputes each pin→head delta. In particular B coordination is reviewed through `456f349…`, not `b824930…`, and D root through `3c636ff…`, not `9cfe108…`. `last_seen_remote_heads` remains observation only; 16 heads moved since that observation and this does not upgrade them to review. All 23 corrected review pins are ancestors of their current pinned heads. The machine record gives complete `git diff --no-renames` path counts for each pin→head delta, split into `policy-engine/src/**/*.py`, `policy-engine/tests/**/*.py`, and all remaining companion paths; where there is no review pin the values are null, not zero. Some deltas are cumulative multi-topic carriers, so these counts route review and do not assign ownership or acceptance.

## Twelve refs without prior review pins

The base→candidate source inventories below are recomputed from Git and the committed handoffs. Every listed candidate tree matches its receipt; slice base is an ancestor of candidate and candidate is reachable from the pinned topic head. Exact full hashes, receipt blob IDs and declared-vs-actual footprint mismatches are in `queue.json`.

| Pinned topic | Exact source candidate/tree | Full diff: files; product `.py` / test `.py` / companions | Identity disposition |
|---|---|---:|---|
| A selection-full `0c884219` | `b07287c6` / `b3bdbafd` | 2; 1 / 1 / 0 | New source+test candidate; no same-candidate review found. |
| C canon `9f842764` | `3b2ce9d6` / `37e4c01a` | 7; 5 / 1 / 1 | Same exact source candidate as third-wave review: HOLD for dropped write-option fields. No closure. Current receipt identity is still distinct. |
| C catalog `f428b114` | `8dfa7f3c` / `3eac9b5c` | 94; 36 / 15 / 43 | New mixed source carrier. Receipt declares 155 paths: 61 are outside this candidate diff. Candidate incorporates DFI candidate `ab441663`; review its source once in the owner sequence. |
| C client `5f812a34` | `c21584f3` / `70fbd543` | 5; 0 / 1 / 4 | Same exact candidate source as third-wave bounded GO; reuse only that source decision. Current receipt blob is new; G consumer admission remains pending. |
| C continuation `c158689d` | `81a4af18` / `c3423c94`; earlier `495043eb` / `34a9ad32` | 15; 3 / 3 / 9; earlier 5; 0 / 1 / 4 | New ancestry-linked chain. Review final `81a4` once with both receipts. Runtime-dependency receipt declares 0 changed paths but its exact base→candidate diff has 5. |
| C DFI/EMB `40d27423` | `ab441663` / `b1eaa06c` | 60; 23 / 9 / 28 | New source, also an ancestor included in C catalog’s `8dfa` carrier. Avoid duplicate code review. |
| C federation `26ba51d5` | `575e7b16` / `621286c1` | 3; 1 / 2 / 0 | Same exact candidate source as third-wave bounded GO; current receipt blob is new; consumer admission stays separate. |
| E calibration `491562fa` | `45b83453` / `f9abc4e6` | 5; 2 / 1 / 2 | Exact candidate already in E-r2 owner actions: scalar preflight bounded; B195 limited/B197 held. This is not a finding closure. |
| F API `90c72b51` | `0c522b88` / `0b308e5f`; successor `8236d9c3` / `724a77c8` | 2,072; 53 / 63 / 1,956; successor 1,084; 9 / 9 / 1,066 | Cumulative carriers. Receipts declare 14 and 0 paths respectively, omitting 2,058 and 1,084 actual paths. Route by frozen component/source order; do not treat topic title or these full-carrier counts as ownership. Older ABI/CAU/dtype/Fry/Lex components are explicitly in the published base. |
| F DoWhy `c8c2319d` | `42316532` / `191a4c89` | 14; 2 / 3 / 9 | Exact candidate already bounded in F-PR65 review; current receipt blob is new. Reuse only the exact DoWhy source scope. |
| F graph intake `2044260c` | `6321dc33` / `f01888ab` | 8; 2 / 3 / 3 | New exact candidate; no same-source review found in checkpoint-12 records. |
| F installed worker `3dde887e` | `ab56a0f3` / `bcb40387` | 56; 13 / 15 / 28 | Mixed source. F identity-order review establishes reused DoWhy blobs (one release-fragment difference), not the whole installed-worker delta. Review residual; package-build replay remains pending. |

The C DFI receipt candidate `ab441663` is an ancestor of C catalog `8dfa7f3c`; the incremental `ab441..8dfa` diff is 36 paths (14 product Python, 6 tests, 16 companions). C streaming’s `495043eb` runtime-dependency candidate is an ancestor of final `81a4af18`; its incremental diff is 11 paths (3 product Python, 3 tests, 5 companions). These relationships keep duplicated source out of the queue while retaining each receipt’s evidence boundary.

## Routing notes

Prior exact source reviews are carried only for unchanged candidate blobs: C canon HOLD; C client and federation bounded GO; E Gaussian preflight limited/held as stated; F DoWhy bounded. The current handoff JSONs for those candidates are separate newly committed receipts and must be read for current source/input identity. A/C catalog/C continuation/C DFI/F graph-intake are genuinely new source candidates. F API and installed-worker require component-level delta reconciliation because the receipt's declared paths do not describe the full candidate tree or include mixed components. The 23 known-ref path counts and each exact `head/tree/reviewed_pin/last_seen` relationship are in `queue.json`; checkpoint-12's `accepted_slices` and `finding_closures` are empty, so this intake makes neither claim.

The 2026-10-07 pin-resolution correction and exact six-root transfer bindings are in [the correction addendum](identity-queue-addendum-20261007.md) and [compact routing note](compactnew-six-identity.md); machine identities and full path lists are in `six-root-identity.json` (G-local ignored input).


Publication scope: this is a pinned review observation/recommendation. A bounded GO here is not an integrated commit or formal finding closure. The root decisions in the eighth-wave README and newer per-unit audit take precedence for later heads.
