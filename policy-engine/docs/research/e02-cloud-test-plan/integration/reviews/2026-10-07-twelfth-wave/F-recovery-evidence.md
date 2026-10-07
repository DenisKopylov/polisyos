# F recovery/evidence review — 2026-10-07

## Decision

The recovered F evidence is readable and internally hash-consistent for the exact frozen source `519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82` / tree `750d28da94f372848fe6b2db5f88db95b94cb57d`. This is a bounded evidence-readiness GO for G's own review. It is **not** G product-code acceptance and does not close any G finding. Current G is `codex/e02-integration` at `83e7c0e934d0b40644dec8a24264a0602ef013e7` / tree `dc1a7697f506b23f2db0f1c80bf929fd2d6a2e0d`; `519`, F root `cdf61b4500e355a27db14260e80ce673ddf8869e`, and F's ordinary-merge carrier `79895c6758307a56b1613a8d1c19daa3f0d92c25` are **not ancestors** of that G HEAD. The G checkpoint `855cb26a7a2c9fea60356663cf81e7d01e20c738` is an ancestor of current G. The frozen source and F root are available on `origin/codex/e02-F-closeout-20261006`; do not describe them as already integrated into current G.

F's own graph confirms `519` is an ancestor of `cdf`, and `79895` is an ancestor of `cdf`. The ordinary merge carrier `79895` has parents `a7fb790d79207bbb17deaa3f9ea1431a6c40e614` and G checkpoint `855`; its handoff identifies two routine ledger conflicts (`closure-decisions/F.md`, `method-decisions.md`) resolved in that F-side merge. G still needs its own append-only adoption/reconciliation. Product-source diff from `519` to `cdf` is only these three paths: `src/polisyos/scientist/methods/search/README.md`, the B111 release fragment, and `tests/unit/remediation/test_req_01_installed.py`; there is no new F runtime code in that delta. This three-path statement concerns the post-freeze delta only, not the original source patch `072→519`.

## Custody and ledger audit

I read F's committed `continuation-transfer-20261007/{REPORT.md,index.json,full-audit.json}` at `cdf`, the exact receipts named by that index, the F graph recovery review, and G's relevant LA-035 method/closure decisions. The pack covers all **35 findings / 17 bundles / 36 byte-bound original criterion bindings** (LA-016 has two bindings). I independently recomputed SHA-256 and byte lengths for all 35 current per-ID records, all 35 original per-ID carrier records, and all 10 current receipt-registry entries: every check matched the committed manifest.

F's recommendation/check columns must remain separate:

- F outcome and technical recommendation: 33 closed, 2 limited (`B214`, `B56`).
- Recorded check results: 34 PASS, 1 UNRUN (`B56`). `B214` is a bounded PASS with a declared residual, not a universal graph-identification claim.
- Formal G finding closures: **0/35**. Each original row has `G_finding_acceptance=not_issued` and `formal_G_closed=false`.
- Code acceptance is not inferred for 34 rows. `LA-017` alone records source acceptance for existing Lex code `00a6eda114b903bc5abe86902cd8372426f739a1`; that does not accept source `519` wholesale or close LA-017 formally in G.

All 35 current source-record bytes and all 35 original criterion carriers passed the direct Git readback/hash checks. The pack's independent original-35 review is explicitly `independent_review_complete_noncanonical`, not a scientific rerun or G adjudication. Owner/coverage assignments and bounded F recommendations are useful inputs to G; they do not issue G acceptance.

`B214` remains limited to the supported sound partial/conditional graph profile. It is not arbitrary PAG/temporal identification. `B56` is genuinely UNRUN: the exact admitted shared-study/fold workload and common scheduler/resource budget input were unavailable; the attempted route stopped at `execution_context_missing` before fits. A four-study fixture and individually configured folds do not prove the admitted shared budget. The separate current statistical-identification/authority questions also remain outside the original bounded passes.

For LA-035 the current committed F closure/method decisions correctly withdraw the stale extra optimizer/normative approval barrier: preserving or relocating the **unchanged** historical `GlobalState` score with its native guards, aliases, JIT and gradient path requires compatibility evidence, not a new normative owner packet. A named accountable owner is needed only if a future change alters score/ranking or adds an objective. External/computed caller retirement and actual production applicability remain unestablished; do not turn that limitation into an invented approval gate.

## Exact saved evidence verified

- Installed wheel and rebuilt-sdist receipt `de197363d4ba8a86b0e8c2fa0ff31c2858643d1c` binds source/tree `519` exactly. The recorded profile is **91 PASS / 0 FAIL / 0 ERROR / 0 SKIP for each of wheel and sdist**, plus six actual expected FAIL results from the retained property-removal controls. This is a saved, source-bound receipt; I did not rerun either suite.
- I rehashed every output in the published manifest: 135 file records / 98 unique stored files, all 135 stored and decoded hashes and lengths match; 10,303,591 decoded bytes. The separate recovered graph-child manifest at `c4ddc4bcbddc2a7526f541d51196b176e4311362` has 44 records / 39 unique peer files / 3 view aliases; all 44 hashes and lengths match (372,421 decoded bytes).
- The recovered graph test is a distinct additive **wheel-only** witness: registered method job → node → selected persisted CAS graph → isolated `-I` child with different PID. The committed proof reports a 970-origin parent, 83-origin child, zero escapes, exact source/tree `519`, and successful round-trip/content checks. It is not a fresh sdist child, a new 91-case run, or authority/causal-identification evidence. The pre-outage attempt itself remains UNRUN because no saved output was recovered; the new child does not rewrite that history.
- The two receipt/profile outputs do not have the generated raw wheel/tar archive bytes in Git. Their hashes and sizes are recorded, and decoded source/sdist/site manifests plus replayers are present. If G's decision specifically requires byte-level rehash of those raw archives, it needs the archive transfer or a fresh build and new observation; the current receipt must not be called raw-archive availability.
- Historical b5 remains an immutable NO-GO: 130 PASS / 32 FAIL in each profile. The later 519 PASS does not relabel that result. Three reproducible old b5 generated directories (`sdist-extracted`, `dist-source`, `dist-rebuilt`) were already retired after readback; their raw archive/buildtree bytes are now unavailable, while committed receipt/custody evidence remains. No cleanup was performed in this review. Production data was not transferred.

## Remaining bounds

The F pack records scanner first/retry as `ERROR/incomplete` (`-9` twice over 5,957 configured paths, no complete output), Ruff `FAIL103`, public-surface `FAIL38`, format `PASS19`, and release fragments `PASS5`. The whole G merge diff check still records a failure on two unchanged upstream raw-output whitespace lines (`P41=not_established`); F-authored document diff check passed. These are distinct check states, not finding-closure counts.

DoWhy/EconML are not backend passes: Python 3.14 import markers do not substitute for execution in the separately selected DoWhy 0.14/Python 3.12 worker. `175c` historical provenance references are unavailable but explicitly non-deciding for this 35-row pack. No production authority issuer, live law/data authority, or production identification positive is supplied. There is no basis here for a whole-causal-stack or whole-F production-readiness claim.

I ran the mandated result importer read-only check (`results/import_results.py --check` → `ok:true`), then read `verification.json` and ran the failures-only query. The global pack remains source-reported compact evidence: 15 reports / 2,074 primary cells, with 307 FAILED, 88 ERROR, 5 COLLECTION_SKIP, 1 COLLECTION_ERROR; raw source archives are absent and transfer/index validation is not product closure. The query returns 401 candidate failure/skip/error cells and displays only 30; those historical cross-agent results must not be attributed to the exact F source or confused with the F-specific receipt above.

No product source, environment, test, ref, or tracked path was changed. Only this report and its JSON companion are written under ignored `_build/`.
