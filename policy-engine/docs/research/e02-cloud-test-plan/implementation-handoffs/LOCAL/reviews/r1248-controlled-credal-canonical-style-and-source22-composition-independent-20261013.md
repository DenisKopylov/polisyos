# R1248 — Credal style delta and composed-source review

**Decision: GO for root-controlled composition and focused native verification only.** This review qualifies the virtual 22-path source candidate; it does not claim test execution, production-positive evidence, or formal closure. `closure_ids=[]`.

## Exact composition

Bound to `codex/e02-unified-local-20261009` at HEAD `51f1db1a47d17c6ee3ccedbdf3f2cc85eb8d4960`, tree `5a4d54dcfdb37d2b47373326d1747de8d7014082`, and the 575-path R1235 frame `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/root-author-source-frame-r1235-20261013.json` (`e0ee2e79f53de2bb2b975058506307fc3e6973beabffefbb347d93fc994b594d`). The current composed manifest is `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r1247-final-source22-protected-abm-controlled-semantic-composition-20261013/composition.json` (`edc64e373e849e695efe76922c48075f1e9036a8f5061da1ef9436567ca24a11`); the full unified patch is `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r1247-final-source22-protected-abm-controlled-semantic-composition-20261013/net.patch` (`b8697aed6e49444aba102bcc9213873fd02becb964644e50c1d2241f4d996ca6`).

The composition is exactly two stages: the prior independently reviewed 21-path R1240/R1242 slice, followed by the single R1247 test-file style patch. I compared the prior 21 path preimage/postimage hashes against this final manifest: all 21 match. The sole added path is `policy-engine/tests/unit/runtime/quality/test_credal_reference.py`; every one of the 22 current physical preimages matches the manifest, and the unified patch exposes 22 unique target headers. This remains a virtual patch; it has not been applied to source.

## Style delta and validation

R1246's initial root-format attempt recorded one failure on the Credal test despite the author-side zero result. R1247 formats with the product working directory, nearest configured Ruff, and Product-relative filename. Its style readback binds the original preimage `28953fef5fb151328f3e61a57cc0cb94287aa0820124a4ca2442e3f9be679596` to root-formatted postimage `5c742c514a9a4ecbc6ba75b4620ca579aa1044fab4efff838fcfe4aeab8b00b2` and reports AST identity. I independently compared the added code in the R1219 patch with the R1247 style patch: AST, significant Python tokens, and comment tokens are identical. The delta is formatting whitespace only.

The retained root quality JSON `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r1247-final-source22-protected-abm-controlled-semantic-composition-20261013/root-quality-r1093.json` (`78916ab2427fa7916361a1a96d40832da22545177a3b23b1dc95a480afdfac7b`) contains 34 successful Ruff check/format results across 17 Python paths. Both Credal results use the final formatted postimage hash. This is style/type-independent source validation; the native semantic tests remain **UNRUN**.

## Semantic and authority boundary

R1241's qualified semantic review remains applicable to the unchanged test additions. The five original production-positive test bodies are preserved; the six controlled/refusal additions remain separate from them. The generated synthetic source and handcrafted profiles carry candidate authority with authenticity/currentness `not_established`; the genuine default-source vintage refusal remains a separate negative. The companion still supplies no production-positive or served-currentness evidence.

P40 remains **SAME_CLASS — SourceInput vs DataFact**. Root may proceed with the focused native wave against the exact composed source. Do not treat Ruff success, style equivalence, the controlled synthetic reader, or the production refusal as proof that the five production-positive properties hold. No product imports, tests, database queries, source/index/Git writes, or patch application were performed in this review.
