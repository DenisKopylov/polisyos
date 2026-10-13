# R1241 — Controlled Credal semantic-law and production-boundary review

**Decision: GO to root for composition and focused native verification only.** This is a static review of a virtual test-only patch, not a test-pass or production-acceptance claim. `closure_ids=[]`.

## Binding and scope

The review is bound to branch `codex/e02-unified-local-20261009`, HEAD `51f1db1a47d17c6ee3ccedbdf3f2cc85eb8d4960`, tree `5a4d54dcfdb37d2b47373326d1747de8d7014082`, and current frame `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/root-author-source-frame-r1235-20261013.json` (`e0ee2e79f53de2bb2b975058506307fc3e6973beabffefbb347d93fc994b594d`). R1219 r2 changes one file: `policy-engine/tests/unit/runtime/quality/test_credal_reference.py`. Its current bytes match the declared preimage `28953fef5fb151328f3e61a57cc0cb94287aa0820124a4ca2442e3f9be679596`; the proposed postimage is `847c153de85f1021dd866dd2ce63576a5f56af0ea1c590b33b869cee2be3f9f9`. The immutable patch is `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r1219-controlled-credal-semantic-laws-and-authentic-refusal-r2-20261013/candidate.patch` (`97acf3f0fcbb083135c64e36e7fa927ebc698d55ef090398f34442ce6480a8a2`). The patch appends six tests and helpers; it does not alter the five original production-positive test bodies.

## Semantic review

The synthetic-source case uses the existing `build_synthetic_academic_skg_source` helper with a fresh `tmp_path` database, a real `WorkRecord` carrying `synthetic=True` and explicit `fixture_scope`, then reads with `_iter_l2_edges`. It extracts the profile emitted by that reader and asserts `selection_owner=legacy.default_l2_source`, `authority_band=candidate`, `source_snapshot_authenticity=not_established`, and `currentness_status=not_established`. The unknown key is checked against that source-derived controlled reference. The removal control leaves the `edge-b` sibling in place and revalidates `credal_reference_l2_source_profile`; it therefore avoids the earlier empty-selected-source denominator defect.

The other controlled cases exercise explicit laws without making production claims: contested lifting carries two alternatives and blocks confirmation; five hand-authored edges define the exact count denominator; actual causal/family derivation functions are compared with manually authored payload bodies and a canonical JSON/typed reconstruction; and a scoped content repair changes reference hash/epoch and marks the certificate stale. The payload test computes the expected content hash with the shared `gy_content_hash` protocol, so its payload-body oracle is independent but it does not independently reimplement that hashing primitive.

The production negative is separate: it calls `build_credal_reference(REPO_ROOT)` with the actual default path, expects `not_reproducible_under_current_rule`, and spies on `CredalReferenceSourceProfile.model_validate`, which the current source path uses after the vintage guard. This verifies that the current pinned default refusal occurs before the production profile is validated. The handcrafted/synthetic profile used as a control is not promoted to production evidence.

The five original R1175 production-positive tests remain unchanged and unverified. The candidate does not turn them into skips, use a toy fallback for the default, infer currentness from synthetic bytes, or claim a live serving path. Native execution is pending at root; author reported static parsing, configured Ruff/format and apply-check only.

## Limits and classification

The source-derived controlled profile follows the legacy default reader, not a WMR-selected production release or served instance. The removal and certificate cases prove controlled reference semantics only. The source-positive production facts still need an authentic, custodied release/profile and a fresh reader bound to those same bytes. Live currentness remains `not_established`; production-positive verification is `verification_missing` until an appropriate source receipt and native consumer evidence exist.

P40 is **SAME_CLASS — SourceInput vs DataFact**. The companion widens the fixture boundary across the whole set rather than patching five old cases. Relevant patterns are P04, P05, P14, P32, and P35. No product import, test, database query, patch application, source/index/Git write was performed for this review. Structured evidence and exact input hashes are in the accompanying JSON.
