# R3 — historical N9 promotion receipt replay

**Property.** A historical N9 receipt keeps the exact serialized field profile and
owner hash of its epoch. Reading it never restores current promotion authority.
New summary fields belong to a new current schema and owner-projection epoch.

**Change.** The current receipt and owner projection advance to v8/v4. Frozen
historical summary serializers cover the original p0 shape, the p1 grounding
detail shape, and the p2 source-hash shape. Historical intake rejects missing,
extra, or coercible fields before a model default can alter a hash. V1 retains
its sparse field projection. The promotion-contract owner translates its
non-authoritative v6 comparison fixture into the new current shape without
restamping the committed fixture. V7 remains a historical comparison rule.

**Corpus and behavioral evidence.** The new corpus test walks all 2,870 tracked
`.json` files in the current repository tree. It classifies 35 complete N9
receipts (7 v1, 14 v3, 14 v6) separately from incomplete projection excerpts,
then compares each parsed historical projection with the original canonical
JSON values. The independent receipt-corpus script also parsed all 13 tracked
`.jsonl` files (4,874 nonblank lines; zero N9 markers), found zero tracked
`.ndjson` files, and parsed the one compressed
v5 receipt embedded in the promotion test. A separate source-reference census
walked 6,381 tracked `.py` files and identified five pinned Git JSON carriers:
the historical generation-cycle blob, the frozen promotion contract at
`504f995cd`, and the N10a census, pack and cycle trace at `d8a8cf076`.
Their complete N9 counts are 2 v3, 3 v6, 0, 0 and 1 v1 respectively. The
promotion-emitter blob and Phase-2 predecessor are source code, not JSON
receipts. Across current tracked JSON, compressed v5, and pinned Git JSON,
the enumerated denominator is **42 complete receipt instances** (8 v1, 16 v3,
1 v5, 17 v6); the three pinned v6 payloads duplicate three current-tree
payloads, so this count is of instances rather than unique contents. The
compressed receipt is exercised by
`test_round1_v5_v2_receipt_round_trips_but_cannot_regain_current_authority`.
The five pinned Git JSON carriers are exercised by
`test_pinned_git_history_receipts_replay_without_current_authority`, and the
JSON corpus test is
`test_historical_receipt_corpus_replays_without_current_authority` in the
same file. Census script and result:
`/Users/deniskopylov/.codex/scratch/e02-r2-r3-receipt-corpus-20260925.py@sha256:ad0636f2e7c0251afcfdf2bc43d0f3284e97f24f1bf1085e2553e8c069561047`
and `/Users/deniskopylov/.codex/scratch/e02-r2-r3-receipt-corpus-20260925.json@sha256:f8473042678669c2d28e5c46b2af269e9f1456dac8d3b116f28f9a428f4c9702`.
The pinned-source census and its machine inventory are
`/Users/deniskopylov/.codex/scratch/e02-r2-r3-pinned-n9-carriers-20260925.md@sha256:6f8743671eeec27b88c313f07f9930864f47325e270d8ba4060c2be8eef07f08`
and `/Users/deniskopylov/.codex/scratch/e02-r2-r3-pinned-n9-carriers-20260925.json@sha256:39086967490651bf1dd3ad8d3e731dab80b0c4b3eb565e5b1e1445286edb6c2a`.
The separate epoch-impact script walked 13,387 tracked paths for epoch tokens;
it does not establish the receipt denominator:
`/Users/deniskopylov/.codex/scratch/e02-r2-r3-epoch-impact-census-20260925.py@sha256:2522030ac15ced13618418829b6b0284facdae56e15685ca59670584b41bbfc2`.

| Check | Outcome | Receipt |
| --- | --- | --- |
| Three named Appendix A/B R3 regressions | 3 pass / 3 | `/Users/deniskopylov/.codex/scratch/e02-r2-r3-tdd-20260925/regressions.junit.xml@sha256:b8eaf63b65d40e8eca9735e611930d8a7ddcced3113ef3a0338471487cdd13` |
| Corpus, sparse v1, lossless-intake tests | 3 pass / 3 | `/Users/deniskopylov/.codex/scratch/e02-r2-r3-tdd-20260925/restored-history.junit.xml@sha256:3eea76d43b4e0337d2cd4b0b3bc8c69c204be62b3d15f332a449b8f34378dbc7` |
| Five pinned Git JSON carriers, including the three added v6 and one v1 receipt | 1 pass / 1 | `/Users/deniskopylov/.codex/scratch/e02-r2-r3-tdd-20260925/pinned-all-committed-v2.junit.xml@sha256:fea47ba948f9b5f2985381a453e1c0c2562683301f0276149d036515db76e29b` |
| Synthetic v7 p0/p1/p2 and current p2 structural control | 4 pass / 4 | `/Users/deniskopylov/.codex/scratch/e02-r2-r3-tdd-20260925/structural-positive.junit.xml@sha256:e372f9f195bbeba29e4a749d93cbe81ec7ad44c0a5d18c115f6aadf7a17d8a35` |
| Remove frozen p0 serializer while keeping epoch markers | corpus and lossless tests red; v1 control green | `/Users/deniskopylov/.codex/scratch/e02-r2-r3-tdd-20260925/p0-mutant.junit.xml@sha256:b7f11e26763302e4868c73d0b6e2d1cb05899a8277960d950633282854853622` |
| Full touched promotion test file, pre-repair Phase-0 versus final R3 corpus | 159 shared identities, zero pass→fail, four fail→pass; eight new tests pass | `/Users/deniskopylov/.codex/scratch/e02-r2-r3-tdd-20260925/p41-full-file-42-diff.json@sha256:1d56e1b9f939ec03ced074c18edd1916690906d2de6988aff9c7979bff48e204` from `compare_junit.py@sha256:0c7e63985a93f55e805b8a1e50055a673f105ed0237c5034b3751a4f7e04b397`; JUnit `/Users/deniskopylov/.codex/scratch/e02-r2-r3-tdd-20260925/post-r3-42-full.junit.xml@sha256:6b769958a788973b4596bfdcc19ad12b71fdc3af2a7cdf13fe67a88baf07355d` |

The final full file has 167 tests: 60 pass, 103 fail, 4 skip. Its 103
failures and four skips were already present among the same 159 test
identities at the Phase-0 integration head; R3 introduces no new red in this
file. The four recovered old tests include all three named historical replay
regressions. The additional recovered v3 history test belongs to the same
versioned-serializer class.

The v7 and current p2 controls use a committed v6 receipt translated by the
contract owner as **comparison custody only**. They assert `promoted=False`
and `consumer_promotable=False`; they do not witness a successful current
promotion or independently validate the translator. The v7 tests backdate
and rehash each historical summary profile and require comparison projection
without current authority.

**P37/P38.** Historical profile identity is recomputed from the supplied
serialized key set and validated without lossy coercion. Owner hashes are
recomputed through their epoch serializer. Before this repair, the v5/v6
validator deserialized with the mutable current `CandidateSummary`: new
default fields appeared on re-dump, so a formerly valid owner hash failed.
The marker-preserving removal probe shows the version label alone cannot
protect history.

Independent final review: `/Users/deniskopylov/.codex/scratch/e02-r2-r3-final-review-20260925.md@sha256:c5ae88f4f61dc5b5792cd25565c0c794b179427f45ff7eaa0966153bcfb8b7c7`
(GO for bounded R3).

**Open checks.** The promotion-contract `--check --output-format json` exits 1
with an untyped `promotion_comparison_admission_manifest_drift` traceback.
Exact replay at R3's parent reproduced that exception: its frozen v6 owner
could not replay after the mutable summary grew. R3 repairs that historical
projection, but now the live owner emits v8 with comparison rule v7 while the
frozen contract contains v6 with rule v5. The checker refuses an unapproved
comparison-epoch transition; that refusal needs a structured FAIL and any
reissue needs its owner-authorized premise. The older pinned E02 head fails
earlier at `promotion_owner_recomputation_drift`. Current stderr:
`/Users/deniskopylov/.codex/scratch/e02-r2-r3-tdd-20260925/promotion-contract-check.stderr@sha256:189de4281146fd7f42d84b38c30e9956d9d6c5af3f3d8d8fd727b1eba15d722a`.
No governed artifact was regenerated or reissued. The promotion and
generation-cycle contracts may require owner-authorized epoch transitions
after source freeze. Four-base post-repair replay and the final release gates
remain open.
